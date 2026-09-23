"""Standard in-silico experiments on a :class:`~brainir.sim.weights.Network`.

* :func:`stimulation_experiment` — stimulate a set of neurons with a constant current across independent parameter
  replicates and score the readout population's rhythmicity (the paper's "DN activation" protocol).
* :func:`silencing_experiment` — the same with a set of neurons removed (rows and columns zeroed).

Results are plain dataclasses that serialise to JSON (see :meth:`ExperimentResult.to_dict`); every run records the
model configuration, the network provenance, the seeds and the metric parameters, so a result can be reproduced or
audited without the Python objects.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field

import numpy as np

from ..metrics.rhythm import ACTIVE_RATE_HZ, DEFAULT_PROMINENCE, network_oscillation_score
from .model import MODEL_ID, Intervention, ModelConfig, Stimulus, Trajectory, sample_neuron_params, simulate
from .weights import Network

ANALYSIS_START_S = 0.25
"""The paper scores t >= 250 ms (sample 250 on the 1 ms grid)."""


@dataclass
class ReplicateResult:
    seed: int
    score: float
    mean_frequency_hz: float | None
    n_active_readout: int
    n_active_all: int
    n_high_rate: int
    max_rate_hz: float
    peak_rates: np.ndarray = field(repr=False)
    """Per-neuron peak rate over the analysis window (Hz)."""
    readout_scores: np.ndarray = field(repr=False)
    readout_frequencies_hz: np.ndarray = field(repr=False)
    readout_range_median_hz: float = 0.0
    """Median peak-to-trough range of the scored readout neurons over the window (Hz): the amplitude the score ignores."""
    readout_peak_median_hz: float = 0.0
    solver_success: bool = True
    wall_time_s: float = 0.0

    def to_dict(self, *, arrays: bool = False) -> dict:
        d = {"seed": self.seed, "score": self.score, "mean_frequency_hz": self.mean_frequency_hz,
             "n_active_readout": self.n_active_readout, "n_active_all": self.n_active_all, "n_high_rate": self.n_high_rate,
             "max_rate_hz": self.max_rate_hz, "readout_range_median_hz": self.readout_range_median_hz,
             "readout_peak_median_hz": self.readout_peak_median_hz, "solver_success": self.solver_success, "wall_time_s": self.wall_time_s}
        if arrays:
            d.update(peak_rates=self.peak_rates.tolist(), readout_scores=self.readout_scores.tolist(),
                     readout_frequencies_hz=self.readout_frequencies_hz.tolist())
        return d


@dataclass
class ExperimentResult:
    name: str
    model_id: str
    config: dict
    network_meta: dict
    stimulus: dict
    intervention: dict | None
    readout: dict
    seeds: list[int]
    replicates: list[ReplicateResult]
    trajectories: list[Trajectory] = field(default_factory=list, repr=False)

    @property
    def scores(self) -> np.ndarray:
        return np.array([r.score for r in self.replicates])

    @property
    def frequencies_hz(self) -> np.ndarray:
        return np.array([np.nan if r.mean_frequency_hz is None else r.mean_frequency_hz for r in self.replicates])

    def summary(self, threshold: float = 0.5) -> dict:
        s = self.scores
        f = self.frequencies_hz
        act = np.array([r.n_active_readout for r in self.replicates])
        return {"n_replicates": int(len(s)), "score_mean": float(s.mean()) if len(s) else None,
                "score_median": float(np.median(s)) if len(s) else None,
                "fraction_ge_threshold": float((s >= threshold).mean()) if len(s) else None, "threshold": threshold,
                "frequency_median_hz": float(np.nanmedian(f)) if np.isfinite(f).any() else None,
                "active_readout_median": float(np.median(act)) if len(act) else None,
                "active_readout_range": [int(act.min()), int(act.max())] if len(act) else None,
                "solver_failures": int(sum(not r.solver_success for r in self.replicates)),
                "wall_time_s": float(sum(r.wall_time_s for r in self.replicates))}

    def to_dict(self, *, arrays: bool = False) -> dict:
        return {"name": self.name, "model_id": self.model_id, "config": self.config, "network": self.network_meta,
                "stimulus": self.stimulus, "intervention": self.intervention, "readout": self.readout, "seeds": self.seeds,
                "summary": self.summary(), "replicates": [r.to_dict(arrays=arrays) for r in self.replicates]}


def score_trajectory(traj: Trajectory, readout_mask: np.ndarray, *, t_start: float = ANALYSIS_START_S,
                     active_rate_hz: float = ACTIVE_RATE_HZ, prominence: float = DEFAULT_PROMINENCE,
                     high_rate_hz: float = 100.0) -> dict:
    """Paper protocol: readout neurons active (peak > 0.01 Hz after t_start) are scored and averaged."""
    win = traj.window(t_start)
    peak = win.max(axis=0)
    active = peak > active_rate_hz
    mask = active & readout_mask
    score, f, per, freqs = network_oscillation_score(win, mask, prominence)
    dt = float(traj.t[1] - traj.t[0])
    # amplitude-aware statistics travel with the (amplitude-blind) published score: the peak-to-trough range of the scored
    # readout neurons over the analysis window, so a sub-Hz ripple with a perfect autocorrelation is recognisable as such
    rng = (win[:, mask].max(axis=0) - win[:, mask].min(axis=0)) if mask.any() else np.zeros(0)
    return {"score": score, "mean_frequency_hz": (f / dt) if f > 0 else None, "n_active_readout": int(mask.sum()),
            "n_active_all": int((traj.r.max(axis=0) > active_rate_hz).sum()), "n_high_rate": int((traj.r.max(axis=0) > high_rate_hz).sum()),
            "max_rate_hz": float(traj.r.max()), "readout_range_median_hz": float(np.median(rng)) if rng.size else 0.0,
            "readout_peak_median_hz": float(np.median(peak[mask])) if mask.any() else 0.0,
            "peak_rates": peak, "readout_scores": per, "readout_frequencies_hz": freqs / dt}


def _run_replicate(args) -> tuple[ReplicateResult, Trajectory | None]:
    W, cfg, stim, intervention, sizes, readout_mask, seed, keep = args
    t0 = time.time()
    params = sample_neuron_params(cfg, W.shape[0], int(seed), sizes)
    traj = simulate(W, params, cfg, stim, intervention)
    sc = score_trajectory(traj, readout_mask, prominence=DEFAULT_PROMINENCE)
    rep = ReplicateResult(seed=int(seed), solver_success=bool(traj.info.get("success", True)),
                          wall_time_s=round(time.time() - t0, 3), **sc)
    return rep, (traj if keep else None)


def stimulation_experiment(net: Network, stim_positions: Sequence[int], current: float, cfg: ModelConfig, seeds: Sequence[int],
                           readout_mask: np.ndarray, *, intervention: Intervention | None = None, name: str = "stimulation",
                           keep_trajectories: bool = False, sizes: np.ndarray | None = None,
                           readout_description: str = "", n_workers: int = 1, backend=None) -> ExperimentResult:
    """Constant-current stimulation of ``stim_positions`` across parameter replicates (one seed = one replicate).

    ``n_workers > 1`` runs replicates in a process pool (results are identical to the serial run; order = seeds).
    ``backend`` (a :mod:`brainir.compute` backend) runs them there instead, shipping W/sizes/readout once as a shared payload."""
    stim = Stimulus(tuple(int(i) for i in stim_positions), (float(current),))
    sizes = net.sizes if sizes is None else sizes
    mask = np.asarray(readout_mask, bool)
    if backend is not None:
        from ..compute.backend import Shared, split_failures
        jobs = [(Shared("W"), cfg, stim, intervention, Shared("sizes"), Shared("readout"), int(s), keep_trajectories) for s in seeds]
        out, failed = split_failures(backend.map(_run_replicate, jobs, shared={"W": net.W, "sizes": sizes, "readout": mask}))
        if failed:
            raise RuntimeError(f"{len(failed)} of {len(jobs)} replicates failed on {backend.name}; first: {failed[0]}")
    else:
        jobs = [(net.W, cfg, stim, intervention, sizes, mask, int(s), keep_trajectories) for s in seeds]
        if n_workers > 1 and len(jobs) > 1:
            from concurrent.futures import ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=int(n_workers)) as ex:
                out = list(ex.map(_run_replicate, jobs, chunksize=1))
        else:
            out = [_run_replicate(j) for j in jobs]
    reps = [r for r, _ in out]
    trajs = [t for _, t in out if t is not None]
    return ExperimentResult(
        name=name, model_id=MODEL_ID, config=cfg.to_dict(), network_meta=dict(net.meta),
        stimulus={"positions": [int(i) for i in stim_positions], "source_ids": [int(net.ids[i]) for i in stim_positions],
                  "current": float(current)},
        intervention=None if intervention is None else {k: v for k, v in asdict(intervention).items() if k != "scale_by_nt"},
        readout={"n": int(readout_mask.sum()), "description": readout_description}, seeds=[int(s) for s in seeds],
        replicates=reps, trajectories=trajs)


def silencing_experiment(net: Network, stim_positions: Sequence[int], current: float, cfg: ModelConfig, seeds: Sequence[int],
                         readout_mask: np.ndarray, silence_positions: Sequence[int], **kw) -> ExperimentResult:
    iv = Intervention(silence=tuple(int(i) for i in silence_positions))
    return stimulation_experiment(net, stim_positions, current, cfg, seeds, readout_mask, intervention=iv,
                                  name=kw.pop("name", "silencing"), **kw)
