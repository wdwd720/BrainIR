"""Job entry points executed locally or on Modal (module-level functions, importable inside the container).

Every job is a dict with a unique ``key`` and returns a dict that carries the same key. A job never raises: errors come back as
``{"key": ..., "error": ...}`` so a streamed, unordered campaign can always attribute every result (and resume the rest).

Job kinds
---------
``group``  auto-tuned activation of a set of neurons (`typescreen.screen_group`): arms B1, B1-controls, B2, B3, B6, G1.
``fixed``  one simulation at fixed currents (`typescreen.fixed_run`): arms B4, B5, gate G3.
"""

from __future__ import annotations

import hashlib
import json
import time
import traceback

import numpy as np
from brainir.sim.model import ModelConfig, sample_neuron_params
from brainir.sim.screen import ScreenConfig

from . import legs as L
from .env import fingerprint
from .typescreen import fixed_run, screen_group


def _model_cfg(d: dict) -> ModelConfig:
    return ModelConfig(**d)


def _screen_cfg(d: dict) -> ScreenConfig:
    d = dict(d)
    d.pop("algorithm", None)
    return ScreenConfig(**d)


def _extras_fn(spec: dict, readout: np.ndarray, model_cfg: ModelConfig, screen_cfg: ScreenConfig):
    """Build the read-out function applied to the accepted (or fixed) trajectory."""

    def fn(traj) -> dict:
        out: dict = {}
        r = traj.r
        out["n_active_notebook"] = int((r.max(axis=0) > 0.01).sum())  # authors' notebook definition (whole run)
        win = traj.window(screen_cfg.analysis_start_s)
        peak = win.max(axis=0)
        act_ro = np.flatnonzero((peak > screen_cfg.active_rate_hz) & readout)
        out["active_readout_positions"] = act_ro.tolist()
        if spec.get("readout_traces"):
            out["readout_traces"] = L.pack_traces(r[:, act_ro])
        if spec.get("watch") is not None:  # small named sets of neurons whose traces are always kept (e.g. stimulated members)
            w = np.asarray(spec["watch"], dtype=np.int64)
            out["watch_traces"] = L.pack_traces(r[:, w])
        legs_spec = spec.get("legs")
        if legs_spec is not None:
            masks = legs_spec["masks"]
            groups = legs_spec["groups"]
            e1 = legs_spec["e1"]  # leg -> position of that leg's copy of the core excitatory interneuron
            out["legs"] = L.per_leg_scores(win, masks, active_rate_hz=screen_cfg.active_rate_hz, prominence=screen_cfg.prominence,
                                           dt=model_cfg.dt_out)
            sig_v1 = {leg: win[:, int(e1[leg])] for leg in L.LEGS}
            sig_v2, src_v2 = {}, {}
            for leg in L.LEGS:
                sig_v2[leg], src_v2[leg] = L.motor_leg_signal(win, groups[leg], active_rate_hz=screen_cfg.active_rate_hz)
            out["offsets_v1"] = L.pairwise_offsets(sig_v1)
            out["offsets_v2"] = L.pairwise_offsets(sig_v2)
            out["leg_signal_v2_source"] = src_v2
            out["e1_peak_hz"] = {leg: float(sig_v1[leg].max()) for leg in L.LEGS}
            out["leg_signals"] = L.pack_traces(np.column_stack([sig_v1[leg] for leg in L.LEGS] + [sig_v2[leg] for leg in L.LEGS]))
        return out

    return fn


def _digest(d: dict) -> str:
    """SHA-256 of the numerical result fields (determinism checks compare these)."""
    keep = {k: d.get(k) for k in ("usable", "score", "frequency_hz", "n_active_readout", "current", "n_tuning_runs", "n_active_all",
                                  "n_high_fr", "verdict")}
    ex = d.get("extras") or {}
    keep["extras_scalar"] = {k: ex.get(k) for k in ("n_active_notebook", "active_readout_positions", "legs", "offsets_v1", "offsets_v2")}
    for k in ("readout_traces", "leg_signals", "watch_traces"):
        if k in ex:
            keep[k] = hashlib.sha256(ex[k]["zlib"]).hexdigest()
    return hashlib.sha256(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()


def run_job(job: dict) -> dict:
    t0 = time.time()
    key = job.get("key")
    try:
        W = job["W"]
        n = W.shape[0]
        model_cfg = _model_cfg(job["model"])
        screen_cfg = _screen_cfg(job["screen"])
        readout = np.asarray(job["readout"], bool)
        params = sample_neuron_params(model_cfg, n, int(job["seed"]), job.get("sizes"))
        extras = _extras_fn(job.get("extras") or {}, readout, model_cfg, screen_cfg)
        if job["kind"] == "group":
            rep = screen_group(W, params, model_cfg, job["members"], readout, seed=int(job["seed"]), cfg=screen_cfg, extras=extras)
            res = rep.to_dict()
        elif job["kind"] == "fixed":
            res = fixed_run(W, params, model_cfg, job["stim_indices"], job["currents"], readout, cfg=screen_cfg, extras=extras)
            res["seed"] = int(job["seed"])
        else:
            raise ValueError(f"unknown job kind {job['kind']!r}")
        res["key"] = key
        res["digest"] = _digest(res)
        res["host"] = fingerprint()
        res["job_wall_s"] = round(time.time() - t0, 2)
        return res
    except Exception as e:  # noqa: BLE001 - a job never raises
        return {"key": key, "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-4000:], "host": fingerprint(),
                "job_wall_s": round(time.time() - t0, 2)}


def run_batch(batch: dict) -> list[dict]:
    """Run several jobs in parallel worker processes inside one container (same code and environment for every job, one
    process per job, results in input order). Throughput only: each job's numerics are those of `run_job` alone (checked by
    gate G4, which re-runs jobs unbatched on other containers)."""
    import multiprocessing as mp
    import os

    items = list(batch["items"])
    n = max(1, min(len(items), int(batch.get("workers") or 1)))
    if n == 1:
        return [run_job(it) for it in items]
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    with mp.get_context("fork").Pool(processes=n, maxtasksperchild=1) as pool:
        return pool.map(run_job, items, chunksize=1)


def probe(job: dict) -> dict:
    """Container probe: host fingerprint plus a fixed numerical workload (tanh, dot, sparse matvec) hashed bit for bit."""
    import scipy.sparse as sp

    rng = np.random.default_rng(12345)
    x = rng.normal(size=200_000)
    t = np.tanh(x * 0.37)
    d = float(np.dot(x, t))
    nrm = float(np.linalg.norm(t))
    A = sp.random(3000, 3000, density=0.01, random_state=7, format="csr")
    v = A @ t[:3000]
    h = hashlib.sha256(t.tobytes() + np.float64(d).tobytes() + np.float64(nrm).tobytes() + v.tobytes()).hexdigest()
    return {"key": job.get("key"), "host": fingerprint(), "numerics_digest": h}
