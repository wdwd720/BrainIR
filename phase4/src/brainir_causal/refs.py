"""Benchmark references (benchmarks/causal_state_v1/PROTOCOL.md section 8; goal5 sections 21-23). ORCHESTRATOR / EVALUATOR SIDE:
trusted code (the evaluator does not copy these models), trained on the benchmark's public training data (D0 + D1) like a method.

    NO-EFFECT      NoEffectModel(base): the base model's passive predictions with every event ignored -> predicted effect exactly 0
    TRUE-STATE     TruthStateModel("z"): encoder = the TRUE causal state (synthetic truth), the generic controlled learner for dynamics,
                   read-in and readout
    OBS-SHORTCUT   TruthStateModel("z_obs"): encoder = the observational shortcut state z_obs of trap types, same learner
    FULL-STATE     FullStateModel: encoder = the observed microstate with a short delay embedding (x_t and two exponential traces of
                   x); the same learner, with per-unit intervention inputs (the predictability anchor of goal5 section 23)
    RANDOM-k       ProjectionStateModel("random", k): a random orthonormal projection of x, same learner
    PCA-k          ProjectionStateModel("pca", k): the top-k principal components of the public training x, same learner
    ID-SHORTCUT    IdShortcutModel: future readout = h(intervention identity, stimulus, readout history); NO state (goal5 section 22)

THE GENERIC CONTROLLED LEARNER, version 2 (one design for every state-based reference, so they differ only in the state s;
research/phase4/REFERENCE_LEARNER_V2.md gives the diagnosis that led to it):

    state            s = the reference's state: z / z_obs (TRUE-STATE / OBS-SHORTCUT), a projection of x (PCA-k / RANDOM-k), or, for
                     FULL-STATE, [x_t, two causal exponential traces of x] (time constants 1/4 and 1 x the short horizon, at least 2
                     samples: the short delay embedding in Markov form, updated in rollouts). cfg.state_traces adds the same traces to
                     the compact states (off by default: they destabilised long rollouts on the dev suite)
    kick read-in     K (d_dyn x N_obs): LEARNED from the training kicks against their counterfactual twins (ridge on the observed
                     one-step effect s_int(j+1) - s_twin(j+1), relative penalty cfg.kick_lambda) around a structural prior: identity for
                     the observed microstate (FULL-STATE), ZERO for a compact state. A correlational probe x -> s is never used as a
                     read-in: a unit that encodes the state without driving it (a follower) would get a large, false read-in
    channels         per step, a per-unit descriptor A (N_obs x 7): current I (current + current_seq), silence drive m * x_hat, silence
                     mask m, edge drive sum over active scaled edges into the unit of (F - 1) * x_hat_pre (F = product of active
                     factors; unobserved presynaptic units contribute 0), gain drive (G - 1) * x_hat, threshold offset D, time-constant
                     drive (C - 1) * x_hat (x_hat = the ridge decoding s -> x; the observed state itself for FULL-STATE). They act
                     CONTROL-AFFINELY with a learned per-(unit, channel) read-in R (d_dyn x N_obs x 7; FULL-STATE: each unit on its own
                     coordinate), initialised in closed form (ridge on the one-step residuals of every row with an active descriptor)
                     after the one-step phase and refined jointly with the dynamics in the paired phase. Effects are linear in the
                     descriptors, so magnitudes outside the training range extrapolate linearly
    abstention       a KIND whose channels were never active in training is unsupported (supports() False); an EVENT on a unit never
                     intervened in training with that kind (for a compact state: a kick on a unit never kicked) is not covered
                     (covers() False) and intervention_effect abstains; the (unit, channel) read-ins never trained are exactly zero
    dynamics         s_dyn(t+1) = s_dyn(t)^+ + [f0([s_norm, u_norm]) + R . (A / scale)] * dsd (f0: MLP depth 2, width 128 (compact) /
                     256 (full), GELU, float64). ONE-STEP phase (cfg.one_step_mode 'auto'): a compact state trains f0 on the rows
                     WITHOUT an active channel (passive rows, kick rows and the rows after interventions; half of every batch from the
                     RESPONSE rows: the short horizon after an event), then fits R in closed form on the channel rows (so f0 cannot
                     absorb the channel effects), then continues f0 on ALL rows with R fixed for half the steps (it learns the states
                     of long channel windows); FULL-STATE trains f0 and R jointly on all rows, then fits R in closed form (its per-unit
                     read-in cannot carry a channel's effect on the other units of a latent-driven system; REFERENCE_LEARNER_V2.md
                     sections 11 and 13). Then a PAIRED multi-step
                     phase: an intervention record and its twin are unrolled together from the same teacher-forced state at most one
                     short horizon before the onset THROUGH max(cfg.window, cfg.window_frac x the short horizon) steps AFTER the onset
                     (default: the whole primary horizon; clipped at the trajectory's end); loss = both
                     trajectory errors (in state sd) + cfg.paired_weight x the error of the predicted EFFECT (intervention minus twin) in
                     units of the typical training effect (the scored quantity, small next to the natural increments)
    readout          y = MLP_g([s_norm, u_norm]) (batches balanced with response rows like the dynamics)
    effect calibration  beta(tau) in [0, 1] per horizon: the least-squares factor of the predicted readout effect against the true one
                     on up to cfg.shrink_pairs training pairs (predicted from the true state at the onset, over the long horizon;
                     smoothed); intervention_effect multiplies the predicted effect by it. Every trajectory has its own parameter draw,
                     so late parts of an effect (e.g. an oscillation's phase) are not predictable from the state alone; the calibration
                     shrinks them towards 0 instead of predicting a coherent, wrongly timed effect
    lift             bounded least squares over kick vectors on up to three distinct subsets of the observed units kicked in training
                     (all; the columns of K with the largest norms; a seeded random half): min ||K dx - dz||^2 + 1e-6 ||dx||^2 subject to
                     the admissible range (dx >= -x_now for non-negative observed data, |dx| <= max_kick if given)
    budget           LearnerConfig defaults: 2,000 one-step Adam steps (batch 1,024, lr 1e-3, cosine), 300 paired steps (32 pairs, lr
                     3e-4, windows of the PRIMARY horizon = 5 short horizons), 1,500 readout steps; torch on CPU; deterministic given
                     the seed (dev suite, 4 threads: TRUE-STATE about 260 s, FULL-STATE about 480 s per system)
    option           cfg.context_adapt (off): an in-context ridge correction of f0 fitted on the item's own history (it destabilised
                     rollouts on the dev suite; kept for the record)

Training data exclude finite blow-ups (max |x| or |y| above 100x the training median); every training record must share one output
dt (the TRAINING dt). TRUE-STATE / OBS-SHORTCUT need the truth of the training trajectories (`truth={"z": {key: (T, k)}}`); at
evaluation the harness REGISTERS the truth of every history it will encode (`register_truth` / `register_records`): encode then returns
the exact state for a registered history and falls back to a ridge probe from [x(t), x(t - dt_train), x(t - 2 dt_train)] otherwise
(interpolated in time; counted in info()["n_probe_encodes"]). The ID-SHORTCUT needs the readout history: the harness registers
(x, u, y) of the evaluation records (`register_readout`), or calls `encode_with_readout`.

TIME (review H, M2). Every reference is dt-aware. Its learned dynamics are a map per TRAINING dt; a rollout at output dt integrates
them round(dt / dt_train) times per output row (sub-steps; the input held constant over each output interval, events placed on the
internal grid), and REFUSES (raises ValueError, a failed prediction) a dt that is not a positive integer multiple of the training dt.
The FULL-STATE traces have time constants in SECONDS: their per-sample factor is 1 - exp(-dt / tau) for the dt of the history being
encoded (the zero-order-hold discretisation), and the internal factor at the training dt in rollouts. The ID-SHORTCUT reads its lag
features at lag TIMES (linear interpolation between samples) and maps output rows to its training grid by time, with the same
integer-ratio rule.

POWER-TABLE CORRUPTIONS (PROTOCOL 7; calibration only): `TruthStateModel("z", drop=(j,))` = the TRUE-STATE reference with one true
state coordinate removed (a missing state); `ReadinGainModel(true_state, family, sysrec, gain=0.5)` = the TRUE-STATE reference whose
read-in of one trained family is scaled by 0.5 (a read-in error).
"""

from __future__ import annotations

import hashlib
import itertools
import time
import dataclasses
from dataclasses import dataclass, field

import numpy as np
from scipy.special import erf

from . import families as F
from . import protocol as P
from .accounting import experiment_cost
from .api import CausalStateModel

N_CH = 7
SHORT_FRAC = 0.025               # the short horizon as a fraction of the default duration (PROTOCOL section 4)
CH_NAMES = ("current", "silence_drive", "silence_mask", "edge_drive", "gain_drive", "threshold", "tau_drive")
KIND_CHANNELS = {"current": {0}, "silence": {1, 2}, "edge_scale": {3}, "param": {4, 5, 6}}
BLOWUP_FACTOR = 100.0


@dataclass(frozen=True)
class LearnerConfig:
    hidden: int = 128
    hidden_full: int = 256
    depth: int = 2
    steps_one: int = 2000
    steps_multi: int = 300            # PAIRED multi-step phase (intervention record and twin unrolled together)
    window: int = 8
    batch: int = 1024
    pair_batch: int = 32
    lr: float = 1e-3
    lr_multi: float = 3e-4
    readout_steps: int = 1500
    max_passive_rows: int = 200_000
    trace_fracs: tuple[float, ...] = (0.25, 1.0)
    window_frac: float = 5.0          # paired windows of max(window, window_frac x the short horizon) steps = the PRIMARY horizon
                                      # (candidate C3 of research/phase4/REFERENCE_LEARNER_V2.md, selected by its stated rule)
    resp_share: float = 0.5
    probe_lambda: float = 1e-4
    kick_lambda: float = 1e-3         # relative ridge penalty of the kick read-in (towards its prior)
    readin_lambda: float = 1e-6       # L2 penalty of the per-unit channel read-in R (normalised units)
    readin_ls_lambda: float = 1e-4    # relative ridge penalty of the closed-form read-in fit (after the one-step phase)
    paired_weight: float = 1.0        # weight of the EFFECT term of the paired loss
    state_traces: bool = False        # traces for the compact references too (off: they destabilised long rollouts on the dev
                                      # suite; FULL-STATE always has its traces)
    one_step_mode: str = "two_stage"  # the rule stated BEFORE the whole-suite comparison, for every reference (LOG P4-D51);
                                      # "joint": f0 and R fitted together on all rows, then the closed-form R (C3); "passive": f0 on
                                      # the rows WITHOUT an active channel only, then the closed-form R; "two_stage": "passive", then
                                      # f0 continued on ALL rows for steps_one // 2 steps with R (and the context gain) FIXED, so f0
                                      # also learns the states of long channel windows without absorbing the channel effects;
                                      # "auto": "joint" for the observed microstate (FULL-STATE), "two_stage" for a compact state
                                      # (REFERENCE_LEARNER_V2.md sections 11 and 13)
    context_linear: bool = False      # False: the static context is an INPUT of the passive field and the readout; True: it enters
                                      # them linearly, f = F0([s, u]) + sum_j c_j F_j([s, u]) (first order in the context). With the
                                      # passive-field rows (above) the input form was 3x more accurate on the draw toy
                                      # (REFERENCE_LEARNER_V2.md section 10); the linear form is kept as the ablation
    context_gain: bool = True         # a STATIC CONTEXT (TRUE-STATE / OBS-SHORTCUT: the trajectory's effective draw parameters)
                                      # modulates the size of the channel effect per latent coordinate: max(0, 1 + W c_norm) *
                                      # (R . A), W (d_dyn x d_context) fitted in closed form with R, refined in the paired phase
    context_adapt: bool = False       # in-context identification: a ridge linear correction of the passive field fitted on the
                                      # item's own observed history before each prediction (intervention_effect)
    context_lambda: float = 1e-3      # its relative ridge penalty
    context_max_rows: int = 2000      # the most recent history rows it uses
    effect_shrinkage: bool = True     # per-horizon least-squares calibration of the predicted effect on training pairs
    shrink_pairs: int = 48            # training intervention / twin pairs used for it
    shrink_horizon_frac: float = 0.5  # its horizon as a fraction of the default duration (the long horizon)
    threads: int = 2
    seed: int = 0


DEFAULT_CFG = LearnerConfig()


# ------------------------------------------------------------------------------------------------------------ record access
def _get(rec, name, default=None):
    if isinstance(rec, dict):
        return rec.get(name, default)
    return getattr(rec, name, default)


def _arr(rec, name) -> np.ndarray:
    return np.asarray(_get(rec, name))


def _rec_dt(rec) -> float:
    t = np.asarray(_get(rec, "t"), float)
    return float(t[1] - t[0]) if len(t) > 1 else float(_get(rec, "protocol")["dt"])


def _events(rec) -> list[dict]:
    return list((_get(rec, "protocol") or {}).get("events") or [])


def blowup_mask(records: list) -> np.ndarray:
    """True for finite blow-ups: max |x| or max |y| above 100x the median over the records."""
    if not records:
        return np.zeros(0, bool)
    mx = np.array([float(np.nanmax(np.abs(_arr(r, "x")))) if _arr(r, "x").size else 0.0 for r in records])
    my = np.array([float(np.nanmax(np.abs(_arr(r, "y")))) if _arr(r, "y").size else 0.0 for r in records])
    bx = mx > BLOWUP_FACTOR * max(float(np.median(mx)), 1e-12)
    by = my > BLOWUP_FACTOR * max(float(np.median(my)), 1e-12)
    return bx | by | ~np.isfinite(mx) | ~np.isfinite(my)


def is_reference(model) -> bool:
    return type(model).__module__ == __name__


# ------------------------------------------------------------------------------------------------------------ history index
class HistoryIndex:
    """Exact lookup of registered histories: key = the digest of the LAST row of [x, u] (float32 bytes); a candidate matches when its
    prefix length equals the query length and its first and last rows are equal. Returns the payload row at the last sample."""

    def __init__(self):
        self.arrays: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        self._dig: list[np.ndarray] = []
        self._built: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None

    @staticmethod
    def _rows(x: np.ndarray, u: np.ndarray) -> np.ndarray:
        x = np.asarray(x, np.float32).reshape(len(x), -1)
        u = np.asarray(u, np.float32).reshape(len(u), -1)
        return np.ascontiguousarray(np.hstack([x, u]))

    @staticmethod
    def _digest(row: np.ndarray) -> int:
        return int.from_bytes(hashlib.blake2b(row.tobytes(), digest_size=8).digest(), "little")

    def add(self, x, u, payload) -> None:
        R = self._rows(x, u)
        self.arrays.append((R, np.asarray(payload), R[0].copy()))
        self._dig.append(np.array([self._digest(r) for r in R], dtype=np.uint64))
        self._built = None

    def _build(self) -> None:
        if self._built is None:
            if not self._dig:
                self._built = (np.zeros(0, np.uint64), np.zeros(0, np.int64), np.zeros(0, np.int64))
                return
            d = np.concatenate(self._dig)
            a = np.concatenate([np.full(len(v), i, np.int64) for i, v in enumerate(self._dig)])
            ii = np.concatenate([np.arange(len(v), dtype=np.int64) for v in self._dig])
            o = np.argsort(d, kind="stable")
            self._built = (d[o], a[o], ii[o])

    def get(self, x_hist, u_hist, prefix: bool = False):
        """The payload row at the history's last sample (prefix=True: the payload rows of the whole prefix)."""
        if not self._dig:
            return None
        self._build()
        d, a, ii = self._built
        R = self._rows(x_hist, u_hist)
        n = len(R)
        key = np.uint64(self._digest(R[-1]))
        lo, hi = np.searchsorted(d, key, "left"), np.searchsorted(d, key, "right")
        for p in range(lo, hi):
            arr, pay, first = self.arrays[int(a[p])]
            i = int(ii[p])
            if i + 1 != n or not np.array_equal(first, R[0]):
                continue
            m = min(n, 4)
            if np.array_equal(arr[i + 1 - m: i + 1], R[n - m:]):
                return pay[: i + 1] if prefix else pay[i]
        return None

    def __len__(self) -> int:
        return int(sum(len(v) for v in self._dig))


# ------------------------------------------------------------------------------------------------------------ event timelines
class Timeline:
    """Per-step intervention descriptors of one event list on steps 0 .. T-1 (event times relative to step 0; index = round(t / dt)).
    Segments = maximal step ranges with a constant set of active windowed events; kicks = step -> {col: delta}."""

    def __init__(self, events: list[dict], T: int, dt: float, col: dict[int, int]):
        self.T, self.col = int(T), col
        self.kicks: dict[int, dict[int, float]] = {}
        wins = []
        for e in events:
            k = e["kind"]
            if k == "kick":
                j = round(float(e["t"]) / dt)
                if 0 <= j < T:
                    dd = self.kicks.setdefault(j, {})
                    for n, v in e["delta"].items():
                        if int(n) in col:
                            dd[col[int(n)]] = dd.get(col[int(n)], 0.0) + float(v)
            elif k == "current_seq":
                vals = {int(n): list(v) for n, v in e["targets"].items()}
                m = len(next(iter(vals.values())))
                seg = float(e["seg"])
                for jj in range(m):
                    a = round((float(e["t0"]) + jj * seg) / dt)
                    b = round((float(e["t0"]) + (jj + 1) * seg) / dt)
                    wins.append(("current", a, b, {n: float(v[jj]) for n, v in vals.items()}))
            elif k in ("current", "silence", "edge_scale", "param"):
                a = round(float(e["t0"]) / dt)
                b = T if e.get("t1") is None else round(float(e["t1"]) / dt)
                if k == "current":
                    wins.append(("current", a, b, {int(n): float(v) for n, v in e["targets"].items()}))
                elif k == "silence":
                    wins.append(("silence", a, b, [int(n) for n in e["targets"]]))
                elif k == "edge_scale":
                    wins.append(("edge", a, b, ([(int(p), int(q)) for p, q in e["edges"]], float(e["factor"]))))
                else:
                    wins.append(("param", a, b, {int(n): dict(v) for n, v in e["targets"].items()}))
        self.wins = [(kd, max(0, a), min(T, b), pay) for kd, a, b, pay in wins if b > 0 and a < T and b > a]
        cuts = sorted({0, T} | {w[1] for w in self.wins} | {w[2] for w in self.wins})
        self.segments = []                     # (a, b, static descriptor)
        for a, b in itertools.pairwise(cuts):
            act = [w for w in self.wins if w[1] <= a and b <= w[2]]
            if act:
                self.segments.append((a, b, self._static(act)))

    def _static(self, act: list) -> dict:
        col = self.col
        cur: dict[int, float] = {}
        sil: set[int] = set()
        gain: dict[int, float] = {}
        thr: dict[int, float] = {}
        tau: dict[int, float] = {}
        edges: dict[tuple[int, int], float] = {}
        for kd, _, _, pay in act:
            if kd == "current":
                for n, v in pay.items():
                    if n in col:
                        cur[col[n]] = cur.get(col[n], 0.0) + v
            elif kd == "silence":
                sil |= {col[n] for n in pay if n in col}
            elif kd == "edge":
                ed, f = pay
                for e in ed:
                    edges[e] = edges.get(e, 1.0) * f
            else:
                for n, v in pay.items():
                    if n not in col:
                        continue
                    c = col[n]
                    gain[c] = gain.get(c, 1.0) * float(v.get("gain", 1.0))
                    tau[c] = tau.get(c, 1.0) * float(v.get("tau", 1.0))
                    thr[c] = thr.get(c, 0.0) + float(v.get("threshold", 0.0))
        e2 = [(col[p], col.get(q), f) for (p, q), f in edges.items() if p in col]
        return {"cur": cur, "sil": sorted(sil), "gain": gain, "thr": thr, "tau": tau, "edges": e2}

    def static_at(self, j: int) -> dict | None:
        for a, b, st in self.segments:
            if a <= j < b:
                return st
        return None


# ------------------------------------------------------------------------------------------------------------ small numerics
def _ema(X: np.ndarray, alpha: float) -> np.ndarray:
    """Causal exponential moving average along axis 0 initialised at the first row: y[0] = X[0], y[n] = y[n-1] + alpha (X[n] - y[n-1])."""
    from scipy.signal import lfilter
    X = np.asarray(X, float)
    if len(X) == 0:
        return X.copy()
    X2 = X.reshape(len(X), -1)
    y, _ = lfilter([alpha], [1.0, -(1.0 - alpha)], X2, axis=0, zi=((1.0 - alpha) * X2[0])[None, :])
    return y.reshape(X.shape)


def _at_lag(X: np.ndarray, dt: float, lag_s: float) -> np.ndarray:
    """The row of X (sampled every dt, the LAST row at time 0) at time -lag_s, linearly interpolated between samples and clamped to the
    first row. On the sampling grid it returns the sample itself."""
    X = np.asarray(X, float)
    pos = (len(X) - 1) - float(lag_s) / float(dt)
    if pos <= 0:
        return X[0].copy()
    r = round(pos)
    if abs(pos - r) < 1e-6:
        return X[int(r)].copy()
    i = int(np.floor(pos))
    w = pos - i
    return (1.0 - w) * X[i] + w * X[min(i + 1, len(X) - 1)]


def n_substeps(dt: float, dt_train: float) -> int:
    """Internal steps of the training dt per output step of dt: a positive integer, else ValueError (review H, M2)."""
    r = float(dt) / float(dt_train)
    n = round(r)
    if n < 1 or abs(r - n) > 1e-6 * max(1.0, r):
        raise ValueError(f"the reference refuses dt = {float(dt):g} s: not a positive integer multiple of its training dt {float(dt_train):g} s")
    return int(n)


def _check_one_dt(recs: list) -> float:
    dts = sorted({round(_rec_dt(r), 12) for r in recs})
    if len(dts) != 1:
        raise ValueError(f"training records must share one output dt; found {dts}")
    return float(dts[0])


def _ridge_fit(X: np.ndarray, Y: np.ndarray, lam: float) -> tuple:
    mu, sd = X.mean(0), X.std(0) + 1e-9
    A = (X - mu) / sd
    ym = Y.mean(0)
    W = np.linalg.solve(A.T @ A + lam * len(A) * np.eye(A.shape[1]), A.T @ (Y - ym))
    return mu, sd, W, ym


def _ridge_apply(p: tuple, X: np.ndarray) -> np.ndarray:
    mu, sd, W, ym = p
    return ((np.atleast_2d(X) - mu) / sd) @ W + ym


def _ridge_linear(p: tuple) -> np.ndarray:
    """The linear map of a fitted ridge (dY = dX @ M)."""
    _, sd, W, _ = p
    return W / sd[:, None]


class _NumpyMLP:
    """Float64 numpy copy of a torch MLP (Linear, GELU, ..., Linear) for fast single-sample rollouts."""

    def __init__(self, net):
        self.layers = [(m.weight.detach().double().numpy().T.copy(), m.bias.detach().double().numpy().copy())
                       for m in net if hasattr(m, "weight")]

    def __call__(self, X: np.ndarray) -> np.ndarray:
        h = np.atleast_2d(X)
        for i, (W, b) in enumerate(self.layers):
            h = h @ W + b
            if i < len(self.layers) - 1:
                h = 0.5 * h * (1.0 + erf(h / np.sqrt(2.0)))
        return h

    def n_params(self) -> int:
        return int(sum(W.size + b.size for W, b in self.layers))


def _make_mlp(n_in: int, n_out: int, hidden: int, depth: int):
    import torch
    layers, d = [], n_in
    for _ in range(depth):
        layers += [torch.nn.Linear(d, hidden), torch.nn.GELU()]
        d = hidden
    layers.append(torch.nn.Linear(d, n_out))
    return torch.nn.Sequential(*layers)


class _TorchThreads:
    def __init__(self, n: int):
        self.n = n

    def __enter__(self):
        import torch
        self.old = torch.get_num_threads()
        torch.set_num_threads(max(1, self.n))

    def __exit__(self, *exc):
        import torch
        torch.set_num_threads(self.old)


# ------------------------------------------------------------------------------------------------------------ the learner
class _LearnedStateModel(CausalStateModel):
    """Shared generic controlled learner, version 2 (module docstring; research/phase4/REFERENCE_LEARNER_V2.md). Subclasses define the
    state: `_dyn_states(rec)` (T, d_dyn) for a training record, `_encode_dyn(x_hist, u_hist)` for evaluation, the auxiliary trace
    blocks (`n_aux`, FULL-STATE only) and whether the state is the observed microstate itself (`_exact_readin`: per-unit channels act
    on the unit's own coordinate; kick prior = identity)."""

    ref_name = "abstract"
    n_aux = 0
    _exact_readin = False
    trace_mode = "evolve"      # "evolve": the traces are Markov state, updated in rollouts; "context": frozen at the encoding time

    def __init__(self, cfg: LearnerConfig = DEFAULT_CFG):
        self.cfg = cfg
        self.k: dict[str, int] = {}
        self.sid = None
        self.train_cost: dict = {}
        self.fit_notes: dict = {}
        self.alphas: list[float] = []
        self.trace_taus_s: list[float] = []
        self.n_aux = len(cfg.trace_fracs) if cfg.state_traces else 0
        self.d_stat = 0                    # static context coordinates (appended after the dynamic state and the traces)
        self.ctx_lin = False               # the context enters F and G linearly (cfg.context_linear)
        self.stat_keep = None
        self.stat_fill = None
        self.Wg = None

    # ---------------------------------------------------------------- hooks
    def _dyn_states(self, rec) -> np.ndarray:
        raise NotImplementedError

    def _static_raw(self, rec) -> np.ndarray | None:
        """The static context vector of a training record (constant along it), or None (no static context: the default)."""
        return None

    def _state_history(self, sid, x_hist, u_hist, dt) -> np.ndarray:
        """The state over the whole history (T_h, d_dyn), for the traces at encoding time."""
        raise NotImplementedError

    def _prepare(self, records: list, sysrec: dict) -> None:
        """Fit the encoder-side pieces (projections, probes) before the dynamics."""

    def _encode_dyn(self, sid, x_hist, u_hist, dt) -> np.ndarray:
        raise NotImplementedError

    def _set_traces(self, short_s: float) -> None:
        """Auxiliary trace blocks: exponential moving averages of the dynamic state with time constants (SECONDS) cfg.trace_fracs x
        the short horizon, at least 2 training samples (the short causal delay embedding in Markov form; with per-trajectory
        parameter draws it lets a generic learner infer the draw's dynamics from the recent course of the state)."""
        if not self.n_aux:
            self.trace_taus_s = []
            return
        self.trace_taus_s = [max(2.0 * self.dt, float(f) * float(short_s)) for f in self.cfg.trace_fracs[: self.n_aux]]
        self.fit_notes["trace_taus_s"] = list(self.trace_taus_s)
        self.fit_notes["trace_taus_steps"] = [t_ / self.dt for t_ in self.trace_taus_s]

    def _alphas(self, dt: float) -> list[float]:
        """Per-sample trace factors 1 - exp(-dt / tau) at sampling interval dt (seconds)."""
        return [float(1.0 - np.exp(-float(dt) / t)) for t in self.trace_taus_s]

    # ---------------------------------------------------------------- traces
    def _aux_rows(self, S_dyn: np.ndarray) -> np.ndarray | None:
        if not self.n_aux:
            return None
        return np.hstack([_ema(S_dyn, a) for a in self.alphas])

    # ---------------------------------------------------------------- static context
    def _setup_static(self, recs: list) -> None:
        """STATIC CONTEXT (TRUE-STATE / OBS-SHORTCUT: the trajectory's effective draw parameters; LOG P4-D43, review E round 3,
        N-new-1): one vector per training record (`_static_raw`), constant along the trajectory. Coordinates that are constant over
        the training records carry nothing learnable and are dropped (recorded); the rest are appended to the state after the
        dynamic part and the traces, with ZERO dynamics: rollouts carry them unchanged and no intervention moves them. Without a
        vector for EVERY training record the context is off and the state is the dynamic part alone (fit_notes['static_context']
        records why)."""
        self.d_stat, self.stat_keep, self.stat_fill = 0, None, None
        raw = [self._static_raw(r) for r in recs]
        if all(v is None for v in raw):
            return
        n_miss = sum(v is None for v in raw)
        if n_miss:
            self.fit_notes["static_context"] = f"off: no static context for {n_miss} of {len(raw)} training records"
            return
        vecs = [np.asarray(v, np.float64).reshape(-1) for v in raw]
        if len({v.size for v in vecs}) != 1:
            self.fit_notes["static_context"] = "off: static context vectors of different lengths"
            return
        M = np.stack(vecs)
        mu, sd = M.mean(0), M.std(0)
        keep = np.isfinite(M).all(0) & (sd > 1e-9 * (1.0 + np.abs(mu)))
        if not keep.any():
            self.fit_notes["static_context"] = f"off: all {M.shape[1]} static coordinates constant over the training records"
            return
        self.stat_keep, self.d_stat = keep, int(keep.sum())
        self.stat_fill = M[:, keep].mean(0)
        self.fit_notes["static_context"] = {"dims": int(M.shape[1]), "kept": self.d_stat, "dropped_constant": int((~keep).sum())}

    def _static_of(self, raw) -> np.ndarray:
        """The kept static coordinates of a raw context vector; None -> the training mean (an unknown context)."""
        if raw is None:
            return self.stat_fill.copy()
        v = np.asarray(raw, np.float64)
        v = v[0] if v.ndim == 2 else v.reshape(-1)
        return v[self.stat_keep]

    def _i_stat(self) -> int:
        """Index of the first static coordinate in the state vector [dynamic, traces, static]."""
        return self.d_dyn * (1 + self.n_aux)

    def _gain_np(self, stat: np.ndarray) -> np.ndarray | float:
        """max(0, 1 + W c_norm) per latent coordinate for static rows stat (n, d_stat) or one row (d_stat,); 1 without a context
        gain (never negative: a context cannot flip the sign of an intervention's effect)."""
        if self.Wg is None:
            return 1.0
        i0 = self._i_stat()
        cn = (np.asarray(stat, float) - self.s_mu[i0: i0 + self.d_stat]) / self.s_sd[i0: i0 + self.d_stat]
        return np.maximum(1.0 + cn @ self.Wg.T, 0.0)

    # ---------------------------------------------------------------- fitting
    def fit(self, sid: str, records: list, sysrec: dict):
        import scipy.sparse as sp
        import torch
        t_start, c_start = time.perf_counter(), time.process_time()
        cfg = self.cfg
        self.sid = sid
        keep = ~blowup_mask(records)
        recs = [r for r, k_ in zip(records, keep) if k_]
        self.fit_notes["n_records"], self.fit_notes["n_blowups_left_out"] = len(records), int((~keep).sum())
        if not recs:
            raise ValueError("no training records left after the blow-up exclusion")
        self.observed = [int(n) for n in sysrec["observed"]]
        self.col = {n: i for i, n in enumerate(self.observed)}
        self.N = len(self.observed)
        self.dt = _check_one_dt(recs)                        # the TRAINING dt
        self.n_u = int(np.atleast_2d(_arr(recs[0], "u")).shape[1]) if _arr(recs[0], "u").ndim > 1 else 1
        self.n_y = int(_arr(recs[0], "y").shape[1])
        t_def = float(sysrec.get("t_end_default") or (len(_arr(recs[0], "t")) - 1) * self.dt)
        short_s = SHORT_FRAC * t_def
        short_steps = max(1.0, short_s / self.dt)
        self._set_traces(short_s)
        self.alphas = self._alphas(self.dt)                  # trace factors at the training dt (training rows and rollout sub-steps)
        self.fit_notes["dt_train"] = self.dt
        allx = np.concatenate([_arr(r, "x") for r in recs]).astype(np.float64)
        self.nonneg = bool((allx >= -1e-9).all())
        del allx
        self._setup_static(recs)
        self.ctx_lin = bool(self.d_stat and cfg.context_linear)
        self._prepare(recs, sysrec)
        S = [np.asarray(self._dyn_states(r), np.float64) for r in recs]
        self.d_dyn = S[0].shape[1]
        # k = the dimension of the encoding: dynamic state, traces and the static context (a method carrying draw coordinates
        # counts them too; info() also reports the dynamic and the context part)
        self.k[sid] = int(self.d_dyn * (1 + self.n_aux) + self.d_stat)
        U = [np.asarray(_arr(r, "u"), np.float64).reshape(len(_arr(r, "u")), -1) for r in recs]
        Y = [np.asarray(_arr(r, "y"), np.float64) for r in recs]
        # decoder (state -> observed microstate, for the state-dependent descriptors) and the KICK read-in (learned from training
        # kicks against their twins; prior = identity for the observed microstate, 0 for a compact state: never a correlational probe)
        if self._exact_readin:
            self.dec = None
            prior = np.eye(self.d_dyn, self.N)
        else:
            Xs = np.concatenate([np.asarray(_arr(r, "x"), np.float64) for r in recs])
            Ss = np.concatenate(S)
            sub = np.random.default_rng(cfg.seed).permutation(len(Xs))[:60_000]
            self.dec = _ridge_fit(Ss[sub], Xs[sub], cfg.probe_lambda)
            del Xs, Ss
            prior = np.zeros((self.d_dyn, self.N))
        self.K = prior + self._kick_correction(recs, S, prior)
        # per-record timelines, kick jumps and teacher-forced per-unit descriptors; one global table (rows of all records)
        tls = [Timeline(_events(r), len(s), self.dt, self.col) for r, s in zip(recs, S)]
        J, Dk, A, AUX = [], [], [], []
        for s, tl in zip(S, tls):
            Jr = np.zeros_like(s)
            Dr = np.zeros((len(s), self.N))
            for j, kk in tl.kicks.items():
                Jr[j] = self._jump(kk)
                for c, v in kk.items():
                    Dr[j, c] += v
            J.append(sp.csr_matrix(Jr))
            Dk.append(sp.csr_matrix(Dr))
            A.append(self._descriptor_rows(self._post(s + Jr), tl))
            if self.n_aux:
                AUX.append(self._aux_rows(s).astype(np.float32))
        STAT_cat = (np.concatenate([np.repeat(self._static_of(self._static_raw(r))[None, :], len(s), 0) for r, s in zip(recs, S)])
                    if self.d_stat else None)
        lens = np.array([len(s) for s in S])
        offs = np.concatenate([[0], np.cumsum(lens)])
        S_cat = np.concatenate(S)
        U_cat = np.concatenate(U)
        Y_cat = np.concatenate(Y)
        del U, Y
        J_cat = sp.vstack(J).tocsr()
        Dk_cat = sp.vstack(Dk).tocsr()
        A_cat = sp.vstack(A).tocsr()
        AUX_cat = np.concatenate(AUX) if AUX else None
        del J, Dk, A, AUX
        n_rows = len(S_cat)
        start = np.repeat(offs[:-1], lens)
        last = np.repeat(offs[1:] - 1, lens)
        # normalisation
        mu, sd = S_cat.mean(0), S_cat.std(0) + 1e-6
        if AUX_cat is not None:
            mu = np.concatenate([mu, AUX_cat.mean(0).astype(np.float64)])
            sd = np.concatenate([sd, AUX_cat.std(0).astype(np.float64) + 1e-6])
        if STAT_cat is not None:
            mu = np.concatenate([mu, STAT_cat.mean(0)])
            sd = np.concatenate([sd, STAT_cat.std(0) + 1e-6])
        self.s_mu, self.s_sd = mu, sd
        self.u_mu, self.u_sd = U_cat.mean(0), U_cat.std(0) + 1e-6
        n_a = self.N * N_CH
        self.ch_scale = np.ones(n_a)
        Ac = A_cat.tocsc()
        for f_ in range(n_a):
            v = Ac.data[Ac.indptr[f_]: Ac.indptr[f_ + 1]]
            if v.size:
                self.ch_scale[f_] = float(np.sqrt(np.mean(v ** 2))) + 1e-12
        seen = np.zeros(n_a, bool)
        seen[np.unique(A_cat.indices)] = True
        self.seen_cols = seen                                # (unit, channel) pairs active in training: the rest is abstained on
        self.kick_units = sorted({int(c) for c in np.unique(Dk_cat.indices)})
        valid = np.flatnonzero(np.arange(n_rows) < last)
        post_v = self._post(S_cat[valid] + J_cat[valid].toarray())
        Dall = S_cat[valid + 1] - post_v
        self.d_sd = Dall.std(0) + 1e-9 * (np.abs(Dall).max() + 1e-12)
        self.y_mu, self.y_sd = Y_cat.mean(0), Y_cat.std(0) + 1e-9
        del post_v, Dall
        # rows: every event row + a seeded subsample of passive rows; RESPONSE rows = event rows and the short horizon after them
        rng = np.random.default_rng(cfg.seed)
        ev = (np.asarray(A_cat.getnnz(axis=1)).ravel() > 0) | (np.asarray(J_cat.getnnz(axis=1)).ravel() > 0)
        n_short = round(short_steps)
        cs = np.concatenate([[0], np.cumsum(ev)])
        lo = np.maximum(np.arange(n_rows) - n_short, start)
        resp = (cs[np.arange(n_rows) + 1] - cs[lo]) > 0
        ev_v = ev[valid]
        n_pass = int((~ev_v).sum())
        frac = min(1.0, cfg.max_passive_rows / max(1, n_pass))
        sel = valid[ev_v | (rng.random(len(valid)) < frac)]
        resp_rows = valid[resp[valid]]
        pairs = self._twin_pairs(recs, offs, lens)
        self.fit_notes.update(one_step_rows=len(sel), event_rows=int(ev_v.sum()), response_rows=len(resp_rows),
                              short_steps=float(short_steps), trace_alphas=list(self.alphas), twin_pairs=len(pairs),
                              n_seen_unit_channels=int(seen.sum()), n_kick_units=len(self.kick_units))
        tab = {"S": S_cat, "U": U_cat, "Y": Y_cat, "J": J_cat, "A": A_cat, "AUX": AUX_cat, "STAT": STAT_cat, "start": start,
               "last": last, "resp": resp}
        ch_seen = {int(c) for c in np.flatnonzero(seen) % N_CH}
        # kicks: a compact state needs a LEARNED kick read-in (some unit kicked in training); the observed microstate has the
        # structural identity prior (a kick moves the unit's own coordinate)
        self.kinds_seen = sorted({k for k, chs in KIND_CHANNELS.items() if chs & ch_seen}
                                 | ({"kick"} if (self.kick_units or self._exact_readin) else set()))
        self.fit_notes["kinds_seen"] = list(self.kinds_seen)
        with _TorchThreads(cfg.threads):
            torch.manual_seed(int(cfg.seed))
            n_in = self.d_dyn * (1 + self.n_aux) + (0 if self.ctx_lin else self.d_stat) + self.n_u
            n_mult = 1 + self.d_stat if self.ctx_lin else 1          # outputs per coordinate: F0 and one F_j per context coordinate
            hid = cfg.hidden_full if self._exact_readin else cfg.hidden
            net = _make_mlp(n_in, self.d_dyn * n_mult, hid, cfg.depth).double()
            R = torch.nn.Parameter(torch.zeros((self.d_dyn, self.N, N_CH) if not self._exact_readin else (self.N, N_CH), dtype=torch.float64))
            Wg = (torch.nn.Parameter(torch.zeros((self.d_dyn, self.d_stat), dtype=torch.float64))
                  if (self.d_stat and cfg.context_gain and not self._exact_readin) else None)
            mode = cfg.one_step_mode
            if mode == "auto":
                mode = "joint" if self._exact_readin else "two_stage"
            if mode not in ("joint", "passive", "two_stage"):
                raise ValueError(f"unknown one_step_mode {mode!r}")
            self.fit_notes["one_step_mode"] = mode
            if mode == "joint":
                self._train_one_step(net, R, sel, resp_rows, tab, torch)
                self._fit_readin_ls(net, R, tab, torch, Wg=Wg)
            else:
                chan_row = np.asarray(A_cat.getnnz(axis=1)).ravel() > 0
                sel_f, resp_f = sel[~chan_row[sel]], resp_rows[~chan_row[resp_rows]]
                self.fit_notes["one_step_rows_passive_field"] = len(sel_f)
                self._train_one_step(net, R, sel_f, resp_f, tab, torch, readin="none")
                self._fit_readin_ls(net, R, tab, torch, Wg=Wg)
                if mode == "two_stage":
                    self._train_one_step(net, R, sel, resp_rows, tab, torch, readin="fixed", Wg=Wg, steps=max(1, cfg.steps_one // 2),
                                         seed_offset=17, note="one_step_loss_stage2")
            m = max(int(cfg.window), round(cfg.window_frac * short_steps))
            self.fit_notes["window"] = m
            if cfg.steps_multi > 0 and m > 1 and len(pairs):
                self._train_paired(net, R, tab, pairs, m, short_steps, torch, Wg=Wg)
            self.f = _NumpyMLP(net.eval())
            Rn = R.detach().numpy().copy()
            Rn[..., ~seen.reshape(self.N, N_CH)] = 0.0              # never-active (unit, channel) pairs: exactly zero
            self.R = Rn
            self.Wg = Wg.detach().numpy().copy() if Wg is not None else None
            ro = _make_mlp(n_in, self.n_y * n_mult, hid, cfg.depth).double()
            self._train_readout(ro, tab, torch)
            self.g = _NumpyMLP(ro.eval())
        self.beta = self._fit_effect_shrinkage(recs, tab, pairs, t_def) if cfg.effect_shrinkage else None
        self.train_cost = {"cpu_s": float(time.process_time() - c_start), "wall_s": float(time.perf_counter() - t_start),
                           "gpu_s": 0.0, "sim_calls": 0, "experiments": int(sum(1 for r in recs if _events(r)))}
        return self

    def _fit_effect_shrinkage(self, recs, tab: dict, pairs: list, t_def: float) -> np.ndarray | None:
        """EFFECT CALIBRATION per horizon: on up to cfg.shrink_pairs training intervention / twin pairs (seeded choice), the model
        predicts the readout effect from the TRUE state at the onset (rollouts with and without the events) and beta(l) = clip(sum
        <e_hat, e> / sum <e_hat, e_hat>, 0, 1) per lag l on the training grid (a running mean over +-2 % of the horizon smooths it).
        The predicted effect of intervention_effect is multiplied by beta: the least-squares factor that shrinks late, poorly
        predictable parts of an effect (e.g. the phase of an oscillation under a trajectory's own parameter draw) towards 0."""
        if not pairs:
            return None
        rng = np.random.default_rng(self.cfg.seed + 41)
        pick = sorted(rng.permutation(len(pairs))[: self.cfg.shrink_pairs].tolist())
        H = max(1, round(self.cfg.shrink_horizon_frac * t_def / self.dt))
        num, den = np.zeros(H + 1), np.zeros(H + 1)
        U, Y = tab["U"], tab["Y"]
        starts = np.concatenate([[0], np.cumsum([len(_arr(r, "t")) for r in recs])])
        start_to_rec = {int(s_): recs[i] for i, s_ in enumerate(starts[:-1])}
        jobs = []
        for pi in pick:
            gi, gt, j0, n = pairs[pi]
            h = min(H, n - 1 - j0)
            rec = start_to_rec.get(int(gi))
            if h < 2 or rec is None:
                continue
            t0 = j0 * self.dt
            evs = []
            for e in _events(rec):
                e2 = dict(e)
                if "t" in e2:
                    e2["t"] = float(e2["t"]) - t0
                else:
                    e2["t0"] = float(e2["t0"]) - t0
                    if e2.get("t1") is not None:
                        e2["t1"] = float(e2["t1"]) - t0
                evs.append(e2)
            z0 = self._z0_row(tab, gi + j0)
            jobs.append((z0, U[gi + j0: gi + j0 + h + 1], evs, Y[gi + j0: gi + j0 + h + 1] - Y[gt + j0: gt + j0 + h + 1]))
        if not jobs:
            return None
        Yi = self._rollout_batch([j[0] for j in jobs], [j[1] for j in jobs], [j[2] for j in jobs])
        Yb = self._rollout_batch([j[0] for j in jobs], [j[1] for j in jobs], [[] for _ in jobs])
        for (z0, uf, evs, et), yi, yb in zip(jobs, Yi, Yb):
            eh = yi - yb
            h = len(et) - 1
            num[: h + 1] += np.sum(eh * et, axis=1)
            den[: h + 1] += np.sum(eh * eh, axis=1)
        ok = den > 0
        if not ok.any():
            return None
        beta = np.ones(H + 1)
        beta[ok] = np.clip(num[ok] / den[ok], 0.0, 1.0)
        w = max(1, round(0.02 * H))
        ker = np.ones(2 * w + 1) / (2 * w + 1)
        pad = np.concatenate([np.full(w, beta[0]), beta, np.full(w, beta[-1])])
        beta = np.convolve(pad, ker, mode="valid")[: H + 1]
        beta[0] = 1.0
        self.fit_notes["effect_beta_at"] = {f"{f}": float(beta[min(H, round(f * H))]) for f in (0.05, 0.25, 0.5, 1.0)}
        return beta

    def _z0_row(self, tab: dict, g: int) -> np.ndarray:
        """The full state vector [dynamic, traces, static] of global training row g."""
        parts = [tab["S"][g]]
        if tab["AUX"] is not None:
            parts.append(tab["AUX"][g].astype(np.float64))
        if tab.get("STAT") is not None:
            parts.append(tab["STAT"][g])
        return np.hstack(parts)

    def _rollout_batch(self, z0s: list, Us: list, events_list: list) -> list[np.ndarray]:
        """Readout rollouts of several (z0, input, events) at the TRAINING dt, the batch stepped together (the same numerics as
        `rollout`; used by the effect calibration)."""
        B = len(z0s)
        dd = self.d_dyn
        Hs = [len(u) - 1 for u in Us]
        Hm = max(Hs)
        s = np.stack([np.asarray(z, float)[:dd] for z in z0s])
        aux = [np.stack([np.asarray(z, float)[dd * (j + 1): dd * (j + 2)] for z in z0s]) for j in range(self.n_aux)]
        i0 = self._i_stat()
        stat = [np.stack([np.asarray(z, float)[i0: i0 + self.d_stat] for z in z0s])] if self.d_stat else []
        gain = self._gain_np(stat[0]) if stat else 1.0
        tls = [Timeline([e for e in ev if e["kind"] in P.EVENT_KINDS], max(h, 1), self.dt, self.col) for ev, h in zip(events_list, Hs)]
        Upad = np.stack([np.vstack([np.asarray(u, float).reshape(len(u), -1), np.repeat(np.asarray(u, float).reshape(len(u), -1)[-1:], Hm + 1 - len(u), 0)])
                         for u in Us])
        Z = [np.hstack([s] + aux + stat)]
        for j in range(Hm):
            for b, tl in enumerate(tls):
                if j in tl.kicks:
                    s[b] = self._post(s[b] + self._jump(tl.kicks[j]))
            full = np.hstack([s] + aux + stat)
            X, C = self._net_in(full, Upad[:, j])
            ds = self._ctx_out(self.f(X), C, dd)
            for b, tl in enumerate(tls):
                st = tl.static_at(j)
                if st is None:
                    continue
                units, A = self._seg_channels(st, self._decode(s[b])[None, :])
                if units:
                    a = np.zeros(self.N * N_CH)
                    cols = (np.asarray(units)[:, None] * N_CH + np.arange(N_CH)[None, :]).reshape(-1)
                    a[cols] = A.reshape(-1)
                    g_b = gain[b] if isinstance(gain, np.ndarray) else gain
                    ds[b] = ds[b] + g_b * self._chan_np(a[None, :])[0]
            s = self._post(s + ds * self.d_sd)
            if self.trace_mode == "evolve":
                aux = [a_ + al * (s - a_) for a_, al in zip(aux, self.alphas)]
            Z.append(np.hstack([s] + aux + stat))
        Zs = np.stack(Z, axis=1)                                    # (B, Hm + 1, k)
        out = []
        for b in range(B):
            zb = Zs[b, : Hs[b] + 1]
            out.append(self.readout(self.sid, zb, Upad[b, : Hs[b] + 1]))
        return out

    def _beta_rows(self, n_rows: int, dt: float) -> np.ndarray:
        """beta at the rows of a prediction at output dt (row r = lag r x dt; beyond the fitted horizon: its last value)."""
        b = getattr(self, "beta", None)
        if b is None:
            return np.ones(n_rows)
        idx = np.minimum(np.round(np.arange(n_rows) * float(dt) / self.dt).astype(int), len(b) - 1)
        return b[idx]

    def _twin_pairs(self, recs, offs, lens) -> list[tuple[int, int, int, int]]:
        """(global start of the intervention record, global start of its twin, onset step, length) for every training intervention
        record whose twin is in the training data (the twin is bit-identical before the first event)."""
        by_key = {str(_get(r, "key")): i for i, r in enumerate(recs)}
        out = []
        for i, r in enumerate(recs):
            tw = (_get(r, "meta") or {}).get("twin_of")
            if not tw or tw not in by_key:
                continue
            ii = by_key[tw]                                  # r is the TWIN of recs[ii]
            ev = _events(recs[ii])
            if not ev:
                continue
            j0 = round(min(P.event_start(e) for e in ev) / self.dt)
            n = int(min(lens[i], lens[ii]))
            if 0 <= j0 < n - 1:
                out.append((int(offs[ii]), int(offs[i]), int(j0), n))
        return out

    def _kick_correction(self, recs, S, prior) -> np.ndarray:
        """The kick read-in's correction to `prior` from training kicks against their twins: ridge on the observed one-step effect
        s_int(j+1) - s_twin(j+1) - prior dx, shrunk towards 0 (relative penalty cfg.kick_lambda). Units never kicked keep the prior."""
        by_key = {str(_get(r, "key")): i for i, r in enumerate(recs)}
        Xk, Rk = [], []
        for i, r in enumerate(recs):
            tw = (_get(r, "meta") or {}).get("twin_of")
            if not tw or tw not in by_key:
                continue
            ii = by_key[tw]
            rint = recs[ii]
            for e in _events(rint):
                if e["kind"] != "kick":
                    continue
                j = round(float(e["t"]) / self.dt)
                if j + 1 >= len(S[ii]) or j + 1 >= len(S[i]):
                    continue
                dx = np.zeros(self.N)
                for n, v in e["delta"].items():
                    if int(n) in self.col:
                        dx[self.col[int(n)]] += float(v)
                if not dx.any():
                    continue
                Xk.append(dx)
                Rk.append(S[ii][j + 1] - S[i][j + 1] - prior @ dx)
        self.fit_notes["kick_pairs"] = len(Xk)
        if not Xk:
            return np.zeros_like(prior)
        Xk, Rk = np.stack(Xk), np.stack(Rk)
        G = Xk.T @ Xk
        used = np.diag(G) > 0
        lam = self.cfg.kick_lambda * max(float(np.mean(np.diag(G)[used])) if used.any() else 1.0, 1e-12)
        return np.linalg.solve(G + lam * np.eye(self.N), Xk.T @ Rk).T

    # ---------------------------------------------------------------- state helpers
    def _jump(self, kk: dict[int, float]) -> np.ndarray:
        dx = np.zeros(self.N)
        for c, v in kk.items():
            dx[c] += v
        return self.K @ dx

    def _post(self, s_dyn: np.ndarray) -> np.ndarray:
        """Admissible-range clip of a post-jump / post-step dynamic state (FULL-STATE with non-negative data only)."""
        return np.maximum(s_dyn, 0.0) if (self._exact_readin and self.nonneg) else s_dyn

    def _decode(self, s_dyn: np.ndarray) -> np.ndarray:
        if self.dec is None:
            return s_dyn
        return _ridge_apply(self.dec, s_dyn[None, :])[0]

    def _decode_rows(self, S_dyn: np.ndarray) -> np.ndarray:
        if self.dec is None:
            return S_dyn
        return _ridge_apply(self.dec, S_dyn)

    def _seg_channels(self, st: dict, xhat: np.ndarray) -> tuple[list[int], np.ndarray]:
        """Descriptor tensor A (n, U, 7) of one static segment for decoded observed states xhat (n, N), over the units it involves."""
        units = sorted(set(st["cur"]) | set(st["sil"]) | {p for p, _, _ in st["edges"]} | set(st["gain"]) | set(st["thr"]) | set(st["tau"]))
        n = len(xhat)
        A = np.zeros((n, len(units), N_CH))
        ui = {u_: i_ for i_, u_ in enumerate(units)}
        for c, v in st["cur"].items():
            A[:, ui[c], 0] += v
        for c in st["sil"]:
            A[:, ui[c], 1] += xhat[:, c]
            A[:, ui[c], 2] += 1.0
        for post, pre, f in st["edges"]:
            if pre is not None and f != 1.0:
                A[:, ui[post], 3] += (f - 1.0) * xhat[:, pre]
        for c, g in st["gain"].items():
            A[:, ui[c], 4] += (g - 1.0) * xhat[:, c]
        for c, v in st["thr"].items():
            A[:, ui[c], 5] += v
        for c, g in st["tau"].items():
            A[:, ui[c], 6] += (g - 1.0) * xhat[:, c]
        return units, A

    def _descriptor_rows(self, s_post: np.ndarray, tl: Timeline):
        """Teacher-forced per-unit descriptors of one record as a CSR matrix (T, N * 7) (column = unit * 7 + channel; all-zero rows
        outside intervention windows)."""
        import scipy.sparse as sp
        T = len(s_post)
        R_, C_, V_ = [], [], []
        for a, b, st in tl.segments:
            b = min(b, T)
            if b <= a:
                continue
            units, A = self._seg_channels(st, self._decode_rows(s_post[a:b]))
            if not units:
                continue
            cols = (np.asarray(units)[:, None] * N_CH + np.arange(N_CH)[None, :]).reshape(-1)
            rr = np.repeat(np.arange(a, b), len(cols))
            cc = np.tile(cols, b - a)
            vv = A.reshape(-1)
            m = vv != 0
            R_.append(rr[m])
            C_.append(cc[m])
            V_.append(vv[m])
        if not R_:
            return sp.csr_matrix((T, self.N * N_CH))
        return sp.csr_matrix((np.concatenate(V_), (np.concatenate(R_), np.concatenate(C_))), shape=(T, self.N * N_CH))

    def _chan_np(self, a: np.ndarray) -> np.ndarray:
        """The control-affine channel term (normalised increment units, (n, d_dyn)) of descriptor rows a (n, N * 7)."""
        an = (np.atleast_2d(a) / self.ch_scale).reshape(-1, self.N, N_CH)
        if self._exact_readin:
            return np.einsum("snc,nc->sn", an, self.R)
        return np.einsum("snc,knc->sk", an, self.R)

    def _chan_torch(self, R, a_norm, torch):
        """The same in torch for normalised descriptor rows a_norm (n, N, 7)."""
        if self._exact_readin:
            return torch.einsum("snc,nc->sn", a_norm, R)
        return torch.einsum("snc,knc->sk", a_norm, R)

    def _net_in(self, s_full: np.ndarray, u: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
        """(MLP input, context) of state rows s_full (n, k) or one row (k,) and inputs u: the normalised state and input; with a
        linear context (`ctx_lin`) the normalised static context is split off (it multiplies the extra MLP outputs, `_ctx_out`),
        otherwise it stays in the input."""
        Z = (np.atleast_2d(np.asarray(s_full, float)) - self.s_mu) / self.s_sd
        Un = (np.atleast_2d(np.asarray(u, float)) - self.u_mu) / self.u_sd
        if self.ctx_lin:
            i0 = self._i_stat()
            return np.hstack([Z[:, :i0], Un]), Z[:, i0: i0 + self.d_stat]
        return np.hstack([Z, Un]), None

    def _ctx_out(self, out: np.ndarray, C: np.ndarray | None, d: int) -> np.ndarray:
        """An MLP output (n, d x (1 + d_context)) combined with the context C: F0 + sum_j c_j F_j (first order in the context);
        unchanged without a linear context."""
        if C is None:
            return out
        o = out.reshape(len(out), d, 1 + self.d_stat)
        return o[..., 0] + np.einsum("nkj,nj->nk", o[..., 1:], C)

    def _net_in_t(self, full, u, smu, ssd, umu, usd, torch):
        """`_net_in` in torch (training)."""
        Z = (full - smu) / ssd
        Un = (u - umu) / usd
        if self.ctx_lin:
            i0 = self._i_stat()
            return torch.cat([Z[:, :i0], Un], dim=1), Z[:, i0: i0 + self.d_stat]
        return torch.cat([Z, Un], dim=1), None

    def _ctx_out_t(self, out, C, d: int, torch):
        """`_ctx_out` in torch (training)."""
        if C is None:
            return out
        o = out.reshape(out.shape[0], d, 1 + self.d_stat)
        return o[..., 0] + torch.einsum("nkj,nj->nk", o[..., 1:], C)

    # ---------------------------------------------------------------- training loops (vectorised gathers on the global table)
    def _full(self, post: np.ndarray, tab: dict, idx: np.ndarray) -> np.ndarray:
        parts = [post]
        if tab["AUX"] is not None:
            parts.append(tab["AUX"][idx])
        if tab.get("STAT") is not None:
            parts.append(tab["STAT"][idx])
        return np.hstack(parts) if len(parts) > 1 else post

    def _batch_rows(self, rng, sel: np.ndarray, resp_rows: np.ndarray, bs: int) -> np.ndarray:
        """A batch with cfg.resp_share of its rows from the RESPONSE rows (interventions and the short horizon after them)."""
        nb = round(self.cfg.resp_share * bs) if len(resp_rows) else 0
        parts = [sel[rng.integers(0, len(sel), bs - nb)]]
        if nb:
            parts.append(resp_rows[rng.integers(0, len(resp_rows), nb)])
        return np.concatenate(parts)

    def _a_norm(self, tab: dict, idx: np.ndarray, torch):
        a = tab["A"][idx].toarray() / self.ch_scale
        return torch.tensor(a.reshape(len(idx), self.N, N_CH), dtype=torch.float64)

    def _readin_penalty(self, R, torch):
        return self.cfg.readin_lambda * torch.sum(R ** 2)

    def _train_one_step(self, net, R, sel: np.ndarray, resp_rows: np.ndarray, tab: dict, torch, readin: str = "train", Wg=None,
                        steps: int | None = None, seed_offset: int = 11, note: str = "one_step_loss") -> None:
        """One-step fit of the passive field f0: (s(t+1) - s(t)^+) / d_sd = f0([s, u]) + channel term, where the channel term is
        R a(t) trained jointly (readin 'train'), absent (readin 'none': the rows must carry no active channel) or FIXED (readin
        'fixed': R and the context gain as fitted, not updated; f0 learns only what the read-in leaves)."""
        cfg = self.cfg
        n_steps = int(steps if steps is not None else cfg.steps_one)
        opt = torch.optim.Adam(list(net.parameters()) + ([R] if readin == "train" else []), lr=cfg.lr)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, max(1, n_steps))
        rng = np.random.default_rng(cfg.seed + seed_offset)
        bs = min(cfg.batch, len(sel))
        losses = []
        STAT = tab.get("STAT")
        i0 = self._i_stat()
        for step in range(n_steps):
            idx = self._batch_rows(rng, sel, resp_rows, bs)
            post = self._post(tab["S"][idx] + tab["J"][idx].toarray())
            X, C = self._net_in(self._full(post, tab, idx), tab["U"][idx])
            Xb = torch.tensor(X, dtype=torch.float64)
            Cb = torch.tensor(C, dtype=torch.float64) if C is not None else None
            Yb = torch.tensor((tab["S"][idx + 1] - post) / self.d_sd, dtype=torch.float64)
            pred = self._ctx_out_t(net(Xb), Cb, self.d_dyn, torch)
            if readin == "train":
                pred = pred + self._chan_torch(R, self._a_norm(tab, idx, torch), torch)
            elif readin == "fixed":
                with torch.no_grad():
                    chan = self._chan_torch(R, self._a_norm(tab, idx, torch), torch)
                    if Wg is not None and STAT is not None:
                        cn = torch.tensor((STAT[idx] - self.s_mu[i0: i0 + self.d_stat]) / self.s_sd[i0: i0 + self.d_stat], dtype=torch.float64)
                        chan = torch.clamp(1.0 + cn @ Wg.T, min=0.0) * chan
                pred = pred + chan
            loss = torch.mean((pred - Yb) ** 2) + (self._readin_penalty(R, torch) if readin == "train" else 0.0)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            if step % 200 == 0 or step == n_steps - 1:
                losses.append(float(loss.detach()))
        self.fit_notes[note] = losses

    def _fit_readin_ls(self, net, R, tab: dict, torch, Wg=None) -> None:
        """Closed-form per-unit read-in given the passive field f0: on every row with an active descriptor, the one-step residual
        (s(t+1) - s(t)^+) / d_sd - f0([s, u]) is regressed (ridge, relative penalty cfg.readin_ls_lambda) on the normalised
        descriptors of the (unit, channel) pairs active in training. Each unit's read-in is otherwise fitted from its few rows by
        stochastic gradients only (a unit is active in about 1 % of the rows), which leaves it under-fitted."""
        A = tab["A"]
        rows = np.flatnonzero((np.asarray(A.getnnz(axis=1)).ravel() > 0) & (np.arange(A.shape[0]) < tab["last"]))
        if not len(rows):
            return
        post = self._post(tab["S"][rows] + tab["J"][rows].toarray())
        X, C = self._net_in(self._full(post, tab, rows), tab["U"][rows])
        with torch.no_grad():
            f0 = self._ctx_out(net(torch.tensor(X, dtype=torch.float64)).numpy(), C, self.d_dyn)
        r = (tab["S"][rows + 1] - post) / self.d_sd - f0
        An = (A[rows].multiply(1.0 / self.ch_scale)).tocsc()
        cols = np.flatnonzero(self.seen_cols)
        if self._exact_readin:
            Rn = np.zeros((self.N, N_CH))
            Acsr = An.tocsr()
            for unit in sorted({int(c) // N_CH for c in cols}):
                cc = [c for c in range(unit * N_CH, unit * N_CH + N_CH) if self.seen_cols[c]]
                sub_rows = np.flatnonzero(np.asarray(Acsr[:, cc].getnnz(axis=1)).ravel() > 0)
                if not len(sub_rows):
                    continue
                F = Acsr[sub_rows][:, cc].toarray()
                y = r[sub_rows, unit]
                G = F.T @ F
                lam = self.cfg.readin_ls_lambda * max(float(np.mean(np.diag(G))), 1e-12)
                Rn[unit, [c - unit * N_CH for c in cc]] = np.linalg.solve(G + lam * np.eye(len(cc)), F.T @ y)
            with torch.no_grad():
                R.copy_(torch.tensor(Rn, dtype=torch.float64))
        else:
            F = An[:, cols]
            G = (F.T @ F).toarray()
            lam = self.cfg.readin_ls_lambda * max(float(np.mean(np.diag(G))), 1e-12)
            W = np.linalg.solve(G + lam * np.eye(len(cols)), np.asarray(F.T @ r))        # (n_cols, d_dyn)
            if Wg is not None and tab.get("STAT") is not None:
                W, Wgn = self._fit_context_gain_ls(F, r, W, tab["STAT"][rows], lam)
                with torch.no_grad():
                    Wg.copy_(torch.tensor(Wgn, dtype=torch.float64))
            Rn = np.zeros((self.d_dyn, self.N * N_CH))
            Rn[:, cols] = W.T
            with torch.no_grad():
                R.copy_(torch.tensor(Rn.reshape(self.d_dyn, self.N, N_CH), dtype=torch.float64))
        self.fit_notes["readin_ls_rows"] = len(rows)

    def _fit_context_gain_ls(self, F, r: np.ndarray, W: np.ndarray, stat_rows: np.ndarray, lam: float, n_iter: int = 3):
        """CONTEXT GAIN in closed form, alternating with the read-in (compact states with a static context): the channel term is
        max(0, 1 + W_g c_norm) * (R . a) per latent coordinate. Given R, each coordinate's gain regression is linear in W_g
        (features c_norm * (R . a)_k, target the one-step residual minus (R . a)_k; ridge, relative penalty 1e-3); given the gains,
        R is refitted per coordinate on the gain-scaled descriptors (the same ridge as the gain-free fit). n_iter alternations;
        the paired phase refines both. Returns (W (n_cols, d_dyn), W_g (d_dyn, d_stat))."""
        import scipy.sparse as sp
        i0 = self._i_stat()
        cn = (np.asarray(stat_rows, float) - self.s_mu[i0: i0 + self.d_stat]) / self.s_sd[i0: i0 + self.d_stat]
        Fr = F.tocsr()
        W = np.array(W, dtype=float, copy=True)
        Wg = np.zeros((self.d_dyn, self.d_stat))
        for _ in range(int(n_iter)):
            chan = np.asarray(Fr @ W)
            for k in range(self.d_dyn):
                Phi = cn * chan[:, k:k + 1]
                A_ = Phi.T @ Phi
                lg = 1e-3 * max(float(np.mean(np.diag(A_))), 1e-12)
                Wg[k] = np.linalg.solve(A_ + lg * np.eye(self.d_stat), Phi.T @ (r[:, k] - chan[:, k]))
            for k in range(self.d_dyn):
                g = np.maximum(1.0 + cn @ Wg[k], 0.0)
                Fk = sp.diags(g) @ Fr
                Gk = (Fk.T @ Fk).toarray()
                W[:, k] = np.linalg.solve(Gk + lam * np.eye(W.shape[0]), np.asarray(Fk.T @ r[:, k]).ravel())
        gains = np.maximum(1.0 + cn @ Wg.T, 0.0)
        self.fit_notes["context_gain_ls"] = {"iterations": int(n_iter), "gain_p5": [float(v) for v in np.percentile(gains, 5, axis=0)],
                                             "gain_p95": [float(v) for v in np.percentile(gains, 95, axis=0)]}
        return W, Wg

    @staticmethod
    def _paired_lengths(j0: np.ndarray, st: np.ndarray, nn: np.ndarray, m: int) -> np.ndarray:
        """Steps unrolled per pair: from the start st (at most one short horizon before the onset j0) through m steps AFTER the onset,
        clipped at the trajectory's end (reviewer H round 3, NEW-2: the window covers the whole scored horizon after the onset)."""
        return np.maximum(1, np.minimum(int(m) + (np.asarray(j0) - np.asarray(st)), np.asarray(nn) - 1 - np.asarray(st)))

    def _train_paired(self, net, R, tab: dict, pairs: list, m: int, short_steps: float, torch, Wg=None) -> None:
        """PAIRED multi-step phase: from a teacher-forced start at most one short horizon before the onset, the intervention record
        (its kicks and teacher-forced descriptors) and its twin are unrolled from the same state through m steps AFTER the onset
        (`_paired_lengths`; clipped at the trajectory's end; a pair whose window is over is frozen and masked while the rest of the
        batch continues); loss = the two trajectory errors (in units of the state sd) + cfg.paired_weight x the error of the
        predicted EFFECT (intervention minus twin) in units of the typical training effect (per coordinate), averaged over the
        unrolled (pair, step) cells: the effect is the scored quantity and is small next to the natural increments, so it gets its
        own scale. With a static context, both unrolls carry their record's context unchanged and `Wg` (the context gain of the
        channel term, initialised in closed form by `_fit_readin_ls`) is refined here."""
        cfg = self.cfg
        dd = self.d_dyn
        S = tab["S"]
        eff = []
        for gi, gt, j0, n in pairs:
            b = min(n, j0 + m + 1)
            eff.append(S[gi + j0: gi + b, :dd] - S[gt + j0: gt + b, :dd])
        e_all = np.concatenate(eff) if eff else np.zeros((1, dd))
        sig_s = self.s_sd[:dd]
        sig_e = np.maximum(np.sqrt(np.mean(e_all ** 2, axis=0)), 1e-3 * sig_s)
        self.fit_notes["effect_scale_over_state_sd"] = [float(v) for v in sig_e / sig_s]
        params = list(net.parameters()) + [R] + ([Wg] if Wg is not None else [])
        opt = torch.optim.Adam(params, lr=cfg.lr_multi)
        rng = np.random.default_rng(cfg.seed + 13)
        bs = min(cfg.pair_batch, len(pairs))
        STAT = tab.get("STAT")
        i0 = self._i_stat()
        cmu = torch.tensor(self.s_mu[i0: i0 + self.d_stat], dtype=torch.float64)
        csd = torch.tensor(self.s_sd[i0: i0 + self.d_stat], dtype=torch.float64)
        sd_t = torch.tensor(self.d_sd, dtype=torch.float64)
        smu, ssd = torch.tensor(self.s_mu, dtype=torch.float64), torch.tensor(self.s_sd, dtype=torch.float64)
        umu, usd = torch.tensor(self.u_mu, dtype=torch.float64), torch.tensor(self.u_sd, dtype=torch.float64)
        sig_s_t, sig_e_t = torch.tensor(sig_s, dtype=torch.float64), torch.tensor(sig_e, dtype=torch.float64)
        alphas = [float(a) for a in self.alphas]
        clip = self._exact_readin and self.nonneg
        pre = max(1, round(short_steps))
        losses = []
        cov_min, n_short = None, 0
        for step in range(cfg.steps_multi):
            pick = rng.integers(0, len(pairs), bs)
            gi = np.array([pairs[p][0] for p in pick])
            gt = np.array([pairs[p][1] for p in pick])
            j0 = np.array([pairs[p][2] for p in pick])
            nn = np.array([pairs[p][3] for p in pick])
            st = np.maximum(0, j0 - rng.integers(0, pre + 1, bs))
            Li = self._paired_lengths(j0, st, nn, m)
            L = int(Li.max())
            long_ = (nn - 1 - j0) >= m                      # trajectories long enough for m steps after the onset
            if long_.any():
                c = int((Li - (j0 - st))[long_].min())
                cov_min = c if cov_min is None else min(cov_min, c)
            n_short += int((~long_).sum())
            ri, rt = gi + st, gt + st
            s_i = torch.tensor(S[ri], dtype=torch.float64)
            s_t = torch.tensor(S[rt], dtype=torch.float64)
            aux_i = ([torch.tensor(tab["AUX"][ri][:, j * dd:(j + 1) * dd], dtype=torch.float64) for j in range(self.n_aux)]
                     if tab["AUX"] is not None else [])
            aux_t = [a.clone() for a in aux_i]
            stat_i = [torch.tensor(STAT[ri], dtype=torch.float64)] if STAT is not None else []
            stat_t = [torch.tensor(STAT[rt], dtype=torch.float64)] if STAT is not None else []
            gain_i = torch.clamp(1.0 + ((stat_i[0] - cmu) / csd) @ Wg.T, min=0.0) if (Wg is not None and stat_i) else 1.0
            num, cnt = 0.0, 0.0
            for q in range(L):
                qi = np.minimum(q, Li - 1)                  # a pair past its window repeats its last row, frozen and masked
                act = torch.tensor(q < Li)
                w_q = act.to(torch.float64)
                rows_i, rows_t = ri + qi, rt + qi
                post_i = s_i + torch.tensor(tab["J"][rows_i].toarray(), dtype=torch.float64)
                post_t = s_t
                if clip:
                    post_i = torch.clamp(post_i, min=0.0)
                full_i = torch.cat([post_i] + aux_i + stat_i, dim=1) if (aux_i or stat_i) else post_i
                full_t = torch.cat([post_t] + aux_t + stat_t, dim=1) if (aux_t or stat_t) else post_t
                u = torch.tensor(tab["U"][rows_i], dtype=torch.float64)
                X_i, C_i = self._net_in_t(full_i, u, smu, ssd, umu, usd, torch)
                X_t, C_t = self._net_in_t(full_t, u, smu, ssd, umu, usd, torch)
                f_i = self._ctx_out_t(net(X_i), C_i, dd, torch)
                f_t = self._ctx_out_t(net(X_t), C_t, dd, torch)
                nxt_i = post_i + (f_i + gain_i * self._chan_torch(R, self._a_norm(tab, rows_i, torch), torch)) * sd_t
                nxt_t = post_t + f_t * sd_t
                if clip:
                    nxt_i, nxt_t = torch.clamp(nxt_i, min=0.0), torch.clamp(nxt_t, min=0.0)
                tg_i = torch.tensor(S[rows_i + 1], dtype=torch.float64)
                tg_t = torch.tensor(S[rows_t + 1], dtype=torch.float64)
                cell = (torch.mean(((nxt_i - tg_i) / sig_s_t) ** 2, dim=1) + torch.mean(((nxt_t - tg_t) / sig_s_t) ** 2, dim=1)
                        + cfg.paired_weight * torch.mean((((nxt_i - nxt_t) - (tg_i - tg_t)) / sig_e_t) ** 2, dim=1))
                num = num + torch.sum(w_q * cell)
                cnt += float(w_q.sum())
                keep = act[:, None]
                if self.trace_mode == "evolve":
                    aux_i = [torch.where(keep, a_ + al * (nxt_i - a_), a_) for a_, al in zip(aux_i, alphas)]
                    aux_t = [torch.where(keep, a_ + al * (nxt_t - a_), a_) for a_, al in zip(aux_t, alphas)]
                s_i, s_t = torch.where(keep, nxt_i, s_i), torch.where(keep, nxt_t, s_t)
            loss = num / max(cnt, 1.0) + self._readin_penalty(R, torch) + (cfg.readin_lambda * torch.sum(Wg ** 2) if Wg is not None
                                                                            else 0.0)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 10.0)
            opt.step()
            if step % 50 == 0 or step == cfg.steps_multi - 1:
                losses.append(float(loss.detach()))
        self.fit_notes["paired_loss"] = losses
        # the post-onset steps every sampled window of a long-enough trajectory covered (= m by construction), and how many sampled
        # pairs ended before m steps after their onset (clipped windows)
        self.fit_notes["paired_post_onset"] = {"window": int(m), "min_steps_long_pairs": cov_min, "n_clipped_short_pairs": n_short}

    def _train_readout(self, ro, tab: dict, torch) -> None:
        """Readout MLP; batches balanced like the dynamics (cfg.resp_share of the rows from response rows), so the map is fitted
        where interventions move the state, not only on passive states."""
        cfg = self.cfg
        n = len(tab["S"])
        opt = torch.optim.Adam(ro.parameters(), lr=cfg.lr)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, max(1, cfg.readout_steps))
        rng = np.random.default_rng(cfg.seed + 19)
        bs = min(cfg.batch * 2, n)
        all_rows = np.arange(n)
        resp_rows = np.flatnonzero(tab["resp"])
        for _ in range(cfg.readout_steps):
            idx = self._batch_rows(rng, all_rows, resp_rows, bs)
            X, C = self._net_in(self._full(tab["S"][idx], tab, idx), tab["U"][idx])
            Yb = (tab["Y"][idx] - self.y_mu) / self.y_sd
            pred = self._ctx_out_t(ro(torch.tensor(X, dtype=torch.float64)), torch.tensor(C, dtype=torch.float64) if C is not None else None,
                                   self.n_y, torch)
            loss = torch.mean((pred - torch.tensor(Yb, dtype=torch.float64)) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()

    # ---------------------------------------------------------------- API
    def encode(self, sid, x_hist, u_hist, dt):
        if not self.n_aux:
            z = np.asarray(self._encode_dyn(sid, x_hist, u_hist, dt), float)
        else:
            Sh = np.asarray(self._state_history(sid, x_hist, u_hist, dt), float)
            # traces in time units: the factor of the history's own sampling interval (review H, M2)
            z = np.hstack([Sh[-1]] + [_ema(Sh, a)[-1] for a in self._alphas(float(dt) if dt else self.dt)])
        # a static context the model cannot read from an observed history: the training mean (TruthStateModel overrides encode)
        return np.hstack([z, self.stat_fill]) if self.d_stat else z

    def supports(self, sid, kind):
        """A kind is supported when some unit received it in training (kicks: some unit was kicked); a kind never seen has no
        represented effect: the evaluator scores abstention, never a silent 'no effect'. Per event, `covers` also requires every
        targeted (unit, channel) to have been intervened in training."""
        if kind == "current_seq":
            kind = "current"
        return kind in getattr(self, "kinds_seen", P.EVENT_KINDS)

    def covers(self, sid, events) -> bool:
        """Every event's targeted (unit, channel) pairs were active in training (kicks: the unit was kicked); an event on a unit that
        is not observed, or was never intervened with that kind, has no learned read-in: the model abstains (it never guesses a
        read-in from correlations)."""
        seen = getattr(self, "seen_cols", None)
        if seen is None:
            return True
        kicked = set(getattr(self, "kick_units", []))

        def ok(unit, chs) -> bool:
            c = self.col.get(int(unit))
            return c is not None and all(seen[c * N_CH + ch] for ch in chs)
        for e in events:
            k = e.get("kind")
            if k not in P.EVENT_KINDS:
                continue
            if k == "kick":
                if not all(int(n) in self.col and (self._exact_readin or self.col[int(n)] in kicked) for n in e["delta"]):
                    return False
            elif k in ("current", "current_seq"):
                if not all(ok(n, (0,)) for n in e["targets"]):
                    return False
            elif k == "silence":
                if not all(ok(n, (1, 2)) for n in e["targets"]):
                    return False
            elif k == "edge_scale":
                if not all(ok(p, (3,)) and int(q) in self.col for p, q in e["edges"]):
                    return False
            elif k == "param":
                for n, d in e["targets"].items():
                    chs = tuple(ch for fld, ch in (("gain", 4), ("threshold", 5), ("tau", 6)) if fld in d)
                    if not ok(n, chs):
                        return False
        return True

    def _context_fit(self, sid, x_hist, u_hist, dt) -> np.ndarray | None:
        """IN-CONTEXT IDENTIFICATION: every trajectory has its own parameter draw, and the state is closed only given the draw. On the
        item's own history (the most recent cfg.context_max_rows rows, at the training dt only) the residual of the learned passive
        field, (s(t+1) - s(t)) / d_sd - f0([s(t), u(t)]), is regressed by ridge on [s_norm, u_norm, 1]; the correction W (n_in + 1,
        d_dyn) is added to f0 in this prediction's rollouts. None when the history is too short or not on the training grid."""
        if not self.cfg.context_adapt or abs(float(dt) - self.dt) > 1e-9 * max(1.0, self.dt):
            return None
        try:
            Sh = np.asarray(self._state_history(sid, x_hist, u_hist, dt), float)
        except NotImplementedError:
            return None
        Uh = np.asarray(u_hist, float).reshape(len(u_hist), -1)
        n = min(len(Sh), len(Uh))
        if n < 8:
            return None
        Sh, Uh = Sh[n - min(n, self.cfg.context_max_rows + 1):n], Uh[n - min(n, self.cfg.context_max_rows + 1):n]
        dd = self.d_dyn
        full = Sh
        if self.n_aux:
            full = np.hstack([Sh[:, :dd]] + [_ema(Sh[:, :dd], a) for a in self._alphas(dt)]) if Sh.shape[1] == dd else Sh
        if self.d_stat:
            stat = np.asarray(self.encode(sid, x_hist, u_hist, dt), float)[-self.d_stat:]
            full = np.hstack([full, np.repeat(stat[None, :], len(full), 0)])
        X, C = self._net_in(full[:-1], Uh[:-1])
        r = (Sh[1:, :dd] - Sh[:-1, :dd]) / self.d_sd - self._ctx_out(self.f(X), C, dd)
        A = np.hstack([X, np.ones((len(X), 1))])
        ok = np.isfinite(A).all(1) & np.isfinite(r).all(1)
        if ok.sum() < 8:
            return None
        A, r = A[ok], r[ok]
        lam = self.cfg.context_lambda * len(A)
        return np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]), A.T @ r)

    def intervention_effect(self, system_id, x_hist, u_hist, u_future, events, dt):
        self._ctx_W = self._context_fit(system_id, x_hist, u_hist, dt)
        try:
            out = super().intervention_effect(system_id, x_hist, u_hist, u_future, events, dt)
        finally:
            self._ctx_W = None
        if getattr(self, "beta", None) is not None:
            b = self._beta_rows(len(out["y_int"]), float(dt) if dt else self.dt)[:, None]
            out["y_int"] = out["y_base"] + b * (out["y_int"] - out["y_base"])
            out["effect"] = out["y_int"] - out["y_base"]
        if not self.covers(system_id, events):
            out["abstain"] = True
        return out

    def rollout(self, sid, z0, u_future, events, dt):
        """Rows at the output dt; the learned map is applied n = dt / dt_train times per row (sub-steps on the training grid, the
        input of the row held over its interval, events placed on the internal grid); a non-integer ratio is refused."""
        dt = float(dt) if dt else self.dt
        n_sub = n_substeps(dt, self.dt)
        U = np.asarray(u_future, float).reshape(len(u_future), -1)
        H = len(U) - 1
        dd = self.d_dyn
        z0 = np.asarray(z0, float)
        s = z0[:dd].copy()
        aux = [z0[dd * (j + 1): dd * (j + 2)].copy() for j in range(self.n_aux)]
        i0 = self._i_stat()
        stat = [z0[i0: i0 + self.d_stat].copy()] if self.d_stat else []     # static context: zero dynamics
        gain = self._gain_np(stat[0]) if stat else 1.0
        tl = Timeline([e for e in events if e["kind"] in P.EVENT_KINDS], max(H * n_sub, 1), self.dt, self.col)
        out = [z0.copy()]
        for j in range(H * n_sub):
            if j in tl.kicks:
                s = self._post(s + self._jump(tl.kicks[j]))
            st = tl.static_at(j)
            full = np.hstack([s] + aux + stat)
            X, C = self._net_in(full, U[j // n_sub])
            ds = self._ctx_out(self.f(X), C, dd)[0]
            if getattr(self, "_ctx_W", None) is not None:
                ds = ds + np.hstack([X[0], 1.0]) @ self._ctx_W
            if st is not None:
                units, A = self._seg_channels(st, self._decode(s)[None, :])
                if units:
                    a = np.zeros(self.N * N_CH)
                    cols = (np.asarray(units)[:, None] * N_CH + np.arange(N_CH)[None, :]).reshape(-1)
                    a[cols] = A.reshape(-1)
                    ds = ds + gain * self._chan_np(a[None, :])[0]
            s = self._post(s + ds * self.d_sd)
            if self.trace_mode == "evolve":
                aux = [a_ + al * (s - a_) for a_, al in zip(aux, self.alphas)]
            if (j + 1) % n_sub == 0:
                out.append(np.hstack([s] + aux + stat))
        Z = np.stack(out)
        return {"z": Z, "y": self.readout(sid, Z, U[: len(Z)])}

    def readout(self, sid, z, u):
        z = np.atleast_2d(np.asarray(z, float))
        u = np.asarray(u, float).reshape(len(z), -1) if np.size(u) else np.zeros((len(z), self.n_u))
        X, C = self._net_in(z, u)
        return self._ctx_out(self.g(X), C, self.n_y) * self.y_sd + self.y_mu

    def read_in(self, sid, z, event):
        if event["kind"] == "kick":
            dx = np.zeros(self.N)
            for n, v in event["delta"].items():
                if int(n) in self.col:
                    dx[self.col[int(n)]] += float(v)
            dz = self.K @ dx
            return {"dz": np.hstack([dz, np.zeros(self.d_dyn * self.n_aux + self.d_stat)])}
        if event["kind"] in P.EVENT_KINDS:
            return {"operator": {"type": "control_affine_per_unit", "kind": event["kind"], "channels": list(CH_NAMES),
                                 "read_in": "R (d_dyn x N_obs x 7), learned per (unit, channel) from training interventions",
                                 "context_gain": self.Wg is not None,
                                 "note": "ds / d_sd = f0(s, u) + (1 + W c_norm) * R . (descriptors / scale); untrained (unit, "
                                         "channel) pairs abstain"}}
        return {}

    def lift(self, sid, x_hist, u_hist, delta_z, n_candidates=3, constraints=None):
        """Kick lifts of the dynamic part of delta_z over units KICKED in training (their read-in is learned; trace and static context
        coordinates cannot be set by an instantaneous intervention; their requested part is part of the miss)."""
        from scipy.optimize import lsq_linear
        cons = constraints or {}
        dz = np.asarray(delta_z, float)[: self.d_dyn]
        allowed = cons.get("targets")
        kicked = set(range(self.N)) if self._exact_readin else set(getattr(self, "kick_units", range(self.N)))
        cols = [self.col[int(n)] for n in (allowed if allowed is not None else self.observed) if int(n) in self.col
                and self.col[int(n)] in kicked]
        if not cols or not np.any(dz):
            return []
        x_now = np.asarray(x_hist, float)[-1]
        max_kick = float(cons.get("max_kick", np.inf))
        norms = np.linalg.norm(self.K[:, cols], axis=0)
        m = max(self.d_dyn, min(len(cols), 3 * self.d_dyn))
        top = [cols[i] for i in np.argsort(-norms, kind="stable")[:m]]
        rng = np.random.default_rng(self.cfg.seed + 23)
        half = sorted(rng.permutation(cols)[: max(1, len(cols) // 2)].tolist()) if len(cols) > 2 * self.d_dyn else None
        subsets = [sorted(cols), sorted(top)] + ([half] if half else [])
        out, seen = [], []
        for S_ in subsets:
            Ks = self.K[:, S_]
            lo = np.full(len(S_), -max_kick)
            hi = np.full(len(S_), max_kick)
            if self.nonneg and self._exact_readin:
                lo = np.maximum(lo, -x_now[S_])
            lam = 1e-6 * max(float(np.sum(Ks ** 2)), 1e-12)
            A = np.vstack([Ks, np.sqrt(lam) * np.eye(len(S_))])
            bvec = np.concatenate([dz, np.zeros(len(S_))])
            sol = lsq_linear(A, bvec, bounds=(lo, np.maximum(hi, lo + 1e-12)), method="bvls" if len(S_) <= 400 else "trf")
            dx = np.asarray(sol.x, float)
            keep = np.abs(dx) > 1e-9 * max(1.0, float(np.abs(dx).max()))
            if not keep.any():
                continue
            full_dx = np.zeros(self.N)
            full_dx[np.asarray(S_)[keep]] = dx[keep]
            if any(np.allclose(full_dx, q, atol=1e-12) for q in seen):
                continue
            seen.append(full_dx)
            delta = {str(self.observed[c]): float(full_dx[c]) for c in np.flatnonzero(full_dx)}
            pdz = np.hstack([self.K @ full_dx, np.zeros(self.d_dyn * self.n_aux + self.d_stat)])
            out.append({"events": [{"kind": "kick", "t": 0.0, "delta": delta}], "predicted_dz": pdz,
                        "cost": float(np.abs(full_dx).sum())})              # kick magnitude (PROTOCOL 5.7: not scaled by dt)
            if len(out) >= n_candidates:
                break
        return out

    def info(self):
        npar_f = self.f.n_params() if hasattr(self, "f") else 0
        npar_g = self.g.n_params() if hasattr(self, "g") else 0
        n_rin = int(self.K.size + (np.count_nonzero(self.R) if hasattr(self, "R") else 0)) if hasattr(self, "K") else 0
        n_rin += int(self.Wg.size) if self.Wg is not None else 0
        enc = 0 if self._exact_readin else int(self.d_dyn * self.N)
        hist = 1 if not self.trace_taus_s else int(np.ceil(3.0 * max(self.trace_taus_s) / self.dt))
        k_dyn = int(self.d_dyn * (1 + self.n_aux)) if hasattr(self, "d_dyn") else None
        return {"k": dict(self.k), "k_range": {s: [v, v] for s, v in self.k.items()}, "method": f"ref:{self.ref_name}",
                "method_version": "5", "history": {s: hist for s in self.k}, "dt_train": getattr(self, "dt", None),
                "k_dynamic": {s: k_dyn for s in self.k}, "k_context": {s: int(self.d_stat) for s in self.k},
                "context_gain": self.Wg is not None, "context_linear": bool(self.ctx_lin), "trace_taus_s": list(self.trace_taus_s),
                "n_params": {"encoder": {s: enc for s in self.k}, "transition": npar_f, "read_in": {s: n_rin for s in self.k},
                             "readout": {s: npar_g for s in self.k}},
                "train_cost": dict(self.train_cost), "fit_notes": dict(self.fit_notes)}


# ------------------------------------------------------------------------------------------------------------ concrete references
class FullStateModel(_LearnedStateModel):
    """FULL-STATE: s = [x_t, EMA_tau1(x)_t, EMA_tau2(x)_t] (causal exponential traces of the observed microstate, tau = cfg.trace_fracs x
    the short horizon in SECONDS, at least 2 training samples; the 'short delay embedding' in Markov form), K = identity."""
    ref_name = "full_state"
    _exact_readin = True

    def __init__(self, cfg: LearnerConfig = DEFAULT_CFG):
        super().__init__(cfg)
        self.n_aux = len(cfg.trace_fracs)

    def _dyn_states(self, rec):
        return np.asarray(_arr(rec, "x"), np.float64)

    def _encode_dyn(self, sid, x_hist, u_hist, dt):
        return np.asarray(x_hist, float)[-1]

    def _state_history(self, sid, x_hist, u_hist, dt):
        return np.asarray(x_hist, float)


class ProjectionStateModel(_LearnedStateModel):
    """PCA-k / RANDOM-k: s = V^T (x - mu) with V the top-k principal axes of the public training x or a random orthonormal basis."""

    def __init__(self, kind: str, k: int, cfg: LearnerConfig = DEFAULT_CFG):
        super().__init__(cfg)
        assert kind in ("pca", "random")
        self.kind, self.kk = kind, int(k)
        self.ref_name = f"{kind}_k"

    def _prepare(self, recs, sysrec):
        X = np.concatenate([_arr(r, "x") for r in recs]).astype(np.float64)
        self.mu = X.mean(0)
        kk = max(1, min(self.kk, X.shape[1]))
        if self.kind == "pca":
            _, _, Vt = np.linalg.svd(X[:: max(1, len(X) // 40_000)] - self.mu, full_matrices=False)
            self.V = Vt[:kk].T
        else:
            q, _ = np.linalg.qr(np.random.default_rng(self.cfg.seed + 29).standard_normal((X.shape[1], kk)))
            self.V = q[:, :kk]

    def _dyn_states(self, rec):
        return (np.asarray(_arr(rec, "x"), np.float64) - self.mu) @ self.V

    def _encode_dyn(self, sid, x_hist, u_hist, dt):
        return (np.asarray(x_hist, float)[-1] - self.mu) @ self.V

    def _state_history(self, sid, x_hist, u_hist, dt):
        return (np.asarray(x_hist, float) - self.mu) @ self.V


class TruthStateModel(_LearnedStateModel):
    """TRUE-STATE ("z") / OBS-SHORTCUT ("z_obs"): the state is a truth array per training record, followed by the trajectory's
    EFFECTIVE DRAW PARAMETERS as static context coordinates (review E round 3, N-new-1; LOG P4-D43): every trajectory has its own
    parameter draw and z is closed only given it, so the complete reference state is [z, draw] (zero dynamics for the draw; no
    intervention moves it). Without draw information for every training record the state is z alone and
    fit_notes['static_context'] says why; `use_draw=False` gives the descriptive z-only reference. Evaluation histories must be
    registered (`register_truth(x, u, z, dt, draw)`, `register_records`); unregistered histories fall back to a ridge probe from
    [x(t), x(t - dt_train), x(t - 2 dt_train)] (interpolated in time) with the training-mean draw. `drop`: true coordinates REMOVED
    from z (the missing-state corruption of the calibration's power table), in training and in every registered history; the draw
    stays."""

    trace_mode = "context"     # the state is closed given the trajectory's parameter draw; the traces only identify the draw

    def __init__(self, which: str = "z", cfg: LearnerConfig = DEFAULT_CFG, drop: tuple[int, ...] = (), use_draw: bool = True):
        super().__init__(cfg)
        assert which in ("z", "z_obs")
        self.which = which
        self.drop = tuple(sorted({int(j) for j in drop}))
        self.use_draw = bool(use_draw)
        self.ref_name = (("true_state" if which == "z" else "obs_shortcut") + ("" if self.use_draw else "_zonly")
                         + (f"_minus{'_'.join(map(str, self.drop))}" if self.drop else ""))
        self.index = HistoryIndex()
        self.n_probe_encodes = 0
        self.n_registered_without_draw = 0
        self.truth_train: dict[str, np.ndarray] = {}
        self.draw_train: dict[str, np.ndarray] = {}

    def _cut(self, z) -> np.ndarray:
        z = np.asarray(z, np.float64)
        if not self.drop:
            return z
        z = np.delete(np.atleast_2d(z) if z.ndim == 1 else z, list(self.drop), axis=-1)
        if z.shape[-1] == 0:
            raise ValueError("no true coordinate left after the removal")
        return z

    def fit_truth(self, sid: str, records: list, sysrec: dict, truth_by_key: dict[str, np.ndarray],
                  draw_by_key: dict[str, np.ndarray] | None = None):
        """Fit on training records with their true state (truth_by_key) and, when given, their effective draw parameters
        (draw_by_key: {key: (d_draw,)} from the truth store's 'draw'; the context is used only if EVERY record has one)."""
        missing = [str(_get(r, "key")) for r in records if str(_get(r, "key")) not in truth_by_key]
        if missing:
            raise ValueError(f"truth missing for {len(missing)} training records (e.g. {missing[0]})")
        self.truth_train = {str(_get(r, "key")): self._cut(truth_by_key[str(_get(r, "key"))]) for r in records}
        self.draw_train = {}
        if self.use_draw and draw_by_key:
            self.draw_train = {str(_get(r, "key")): np.asarray(draw_by_key[str(_get(r, "key"))], np.float64)
                               for r in records if draw_by_key.get(str(_get(r, "key"))) is not None}
        elif self.use_draw:
            self.fit_notes["static_context"] = "off: no draw information for this system (the state is z alone)"
        else:
            self.fit_notes["static_context"] = "off: z-only reference (use_draw=False)"
        return self.fit(sid, records, sysrec)

    def _static_raw(self, rec) -> np.ndarray | None:
        if not self.use_draw or not self.draw_train:
            return None
        return self.draw_train.get(str(_get(rec, "key")))

    def _prepare(self, recs, sysrec):
        # the delay probe (fallback encoder)
        Xl, Zl = [], []
        for r in recs:
            x = np.asarray(_arr(r, "x"), np.float64)
            z = self.truth_train[str(_get(r, "key"))]
            lag1 = np.vstack([x[:1], x[:-1]])
            lag2 = np.vstack([x[:1], x[:1], x[:-2]])[: len(x)]
            Xl.append(np.hstack([x, lag1, lag2]))
            Zl.append(z)
            self.index.add(x, _arr(r, "u"), self._payload(z, self.dt, self._static_raw(r)))
        Xl, Zl = np.concatenate(Xl), np.concatenate(Zl)
        sub = np.random.default_rng(self.cfg.seed + 31).permutation(len(Xl))[:60_000]
        self.delay_probe = _ridge_fit(Xl[sub], Zl[sub], 1e-3)

    def _dyn_states(self, rec):
        return self.truth_train[str(_get(rec, "key"))]

    def _payload(self, z, dt: float, draw=None) -> np.ndarray:
        """Rows [z, traces of z, draw] of a (cut) true-state trajectory sampled every dt (traces initialised at its first row, like
        the training rows; the draw, when the model uses one, repeated on every row; draw None -> the training-mean draw)."""
        Z = np.asarray(z, np.float64)
        parts = [Z] + ([_ema(Z, a) for a in self._alphas(dt)] if self.n_aux else [])
        if self.d_stat:
            parts.append(np.repeat(self._static_of(draw)[None, :], len(Z), 0))
        return np.hstack(parts) if len(parts) > 1 else Z

    def register_truth(self, x, u, z, dt: float | None = None, draw=None) -> None:
        """Evaluator-side: the exact state (its traces, and the trajectory's draw when the model uses one) at every prefix of this
        (x, u) history, sampled every dt (default: the training dt); the removed coordinates are dropped here too. Call after fit
        (the trace time constants and the kept draw coordinates are set there). A model with a draw context registered without a
        draw uses the training-mean draw (counted: info()['n_registered_without_draw'])."""
        if self.d_stat and draw is None:
            self.n_registered_without_draw += 1
        self.index.add(x, u, self._payload(self._cut(z), float(dt) if dt else self.dt, draw))

    def register_records(self, records: list, truth_by_key: dict[str, np.ndarray],
                         draw_by_key: dict[str, np.ndarray] | None = None) -> int:
        n = 0
        for r in records:
            z = truth_by_key.get(str(_get(r, "key")))
            if z is not None:
                self.register_truth(_arr(r, "x"), _arr(r, "u"), z, _rec_dt(r), (draw_by_key or {}).get(str(_get(r, "key"))))
                n += 1
        return n

    def _probe_rows(self, x: np.ndarray, dth: float) -> np.ndarray:
        """The delay probe's state estimate at every row of an observed history (lags in TIME: the training grid's 1 and 2
        samples)."""
        rows = []
        for i in range(len(x)):
            xi = x[: i + 1]
            rows.append(np.hstack([xi[-1], _at_lag(xi, dth, self.dt), _at_lag(xi, dth, 2.0 * self.dt)]))
        return _ridge_apply(self.delay_probe, np.asarray(rows))

    def encode(self, sid, x_hist, u_hist, dt):
        z = self.index.get(x_hist, u_hist)
        if z is not None:
            return np.asarray(z, float).copy()
        self.n_probe_encodes += 1
        x = np.asarray(x_hist, float)
        dth = float(dt) if dt else self.dt
        if not self.n_aux:
            zp = _ridge_apply(self.delay_probe, np.hstack([x[-1], _at_lag(x, dth, self.dt), _at_lag(x, dth, 2.0 * self.dt)])[None, :])[0]
            return np.hstack([zp, self.stat_fill]) if self.d_stat else zp
        return self._payload(self._probe_rows(x, dth), dth)[-1]

    def _encode_dyn(self, sid, x_hist, u_hist, dt):
        return np.asarray(self.encode(sid, x_hist, u_hist, dt), float)[: self.d_dyn]

    def _state_history(self, sid, x_hist, u_hist, dt):
        """The (registered) state over the whole history: the payload prefix (z and, with traces, its traces); unregistered: the
        delay probe's estimate at every row."""
        z = self.index.get(x_hist, u_hist, prefix=True)
        if z is not None:
            return np.asarray(z, float)[:, : self.d_dyn]
        return self._probe_rows(np.asarray(x_hist, float), float(dt) if dt else self.dt)

    def info(self):
        d = super().info()
        d["n_probe_encodes"] = int(self.n_probe_encodes)
        d["n_registered_samples"] = len(self.index)
        d["dropped_true_coordinates"] = list(self.drop)
        d["draw_context"] = bool(self.d_stat)
        d["n_registered_without_draw"] = int(self.n_registered_without_draw)
        return d


class NoEffectModel(CausalStateModel):
    """NO-EFFECT: the base model's passive predictions; every event is ignored, so the predicted effect is exactly 0. Supports every
    kind (it predicts "no effect", it does not abstain)."""
    ref_name = "no_effect"

    def __init__(self, base: CausalStateModel):
        self.base = base
        self.k = dict(getattr(base, "k", {}) or {})

    def encode(self, sid, x_hist, u_hist, dt):
        return self.base.encode(sid, x_hist, u_hist, dt)

    def rollout(self, sid, z0, u_future, events, dt):
        return self.base.rollout(sid, z0, u_future, [], dt)

    def readout(self, sid, z, u):
        return self.base.readout(sid, z, u)

    def supports(self, sid, kind):
        return kind in P.EVENT_KINDS

    def register_truth(self, x, u, z, dt: float | None = None, draw=None) -> None:
        if hasattr(self.base, "register_truth"):
            self.base.register_truth(x, u, z, dt, draw)

    def info(self):
        d = dict(self.base.info() or {})
        d["method"] = "ref:no_effect"
        return d


class ReadinGainModel(CausalStateModel):
    """CALIBRATION POWER TABLE (PROTOCOL 7): the TRUE-STATE reference with a READ-IN ERROR. Every event list whose family
    (`families.family_of` under the system record, from the events alone) is `family` reaches the base model with its amplitudes
    scaled by `gain`: kick deltas, currents, sequence values, the edge-scale depth 1 - f, parameter changes (g - 1, c - 1, threshold);
    everything else is delegated unchanged. Trusted (module refs), so it shares the base's registered truth."""
    ref_name = "true_state_readin"

    def __init__(self, base: CausalStateModel, family: str, sysrec: dict, gain: float = 0.5):
        self.base, self.family, self.sysrec, self.gain = base, str(family), sysrec, float(gain)
        self.k = dict(getattr(base, "k", {}) or {})
        self.n_scaled = 0

    def _family(self, sid: str, events: list[dict], t_hint: float, dt: float) -> str | None:
        evs = [e for e in events if e.get("kind") in P.EVENT_KINDS]
        if not evs:
            return None
        ends = []
        for e in evs:
            if "t" in e:
                ends.append(float(e["t"]))
            elif e["kind"] == "current_seq":
                ends.append(float(e["t0"]) + float(e["seg"]) * len(next(iter(e["targets"].values()))))
            else:
                ends.append(float(e["t0"] if e.get("t1") is None else e["t1"]))
        t_end = max(float(t_hint), max(ends) + dt, 10 * dt)
        try:
            return F.family_of({"system": sid, "params_seed": 0, "t_end": t_end, "dt": dt, "events": evs}, self.sysrec)
        except Exception:  # noqa: BLE001 - unclassifiable: not the corrupted family
            return None

    def _scale(self, e: dict) -> dict:
        g = self.gain
        e2 = dict(e)
        k = e["kind"]
        if k == "kick":
            e2["delta"] = {n: g * float(v) for n, v in e["delta"].items()}
        elif k == "current":
            e2["targets"] = {n: g * float(v) for n, v in e["targets"].items()}
        elif k == "current_seq":
            e2["targets"] = {n: [g * float(v) for v in lst] for n, lst in e["targets"].items()}
        elif k == "edge_scale":
            e2["factor"] = 1.0 + g * (float(e["factor"]) - 1.0)
        elif k == "param":
            e2["targets"] = {n: {f: (1.0 + g * (float(v) - 1.0) if f in ("gain", "tau") else g * float(v)) for f, v in d.items()}
                             for n, d in e["targets"].items()}
        return e2

    def _events(self, sid: str, events: list[dict], n_rows: int, dt: float) -> list[dict]:
        if self._family(sid, events, (n_rows - 1) * dt, dt) != self.family:
            return list(events)
        self.n_scaled += 1
        return [self._scale(e) for e in events]

    def encode(self, sid, x_hist, u_hist, dt):
        return self.base.encode(sid, x_hist, u_hist, dt)

    def rollout(self, sid, z0, u_future, events, dt):
        return self.base.rollout(sid, z0, u_future, self._events(sid, events, len(u_future), float(dt)), dt)

    def intervention_effect(self, sid, x_hist, u_hist, u_future, events, dt):
        """The base's own counterfactual prediction (its effect calibration and abstention included) for the scaled events."""
        return self.base.intervention_effect(sid, x_hist, u_hist, u_future, self._events(sid, events, len(u_future), float(dt)), dt)

    def readout(self, sid, z, u):
        return self.base.readout(sid, z, u)

    def supports(self, sid, kind):
        return self.base.supports(sid, kind)

    def covers(self, sid, events) -> bool:
        return self.base.covers(sid, events) if hasattr(self.base, "covers") else True

    def read_in(self, sid, z, event):
        dt = getattr(self.base, "dt", 0.01)
        return self.base.read_in(sid, z, self._events(sid, [event], 11, dt)[0])

    def register_truth(self, x, u, z, dt: float | None = None, draw=None) -> None:
        if hasattr(self.base, "register_truth"):
            self.base.register_truth(x, u, z, dt, draw)

    def info(self):
        d = dict(self.base.info() or {})
        d.update(method="ref:true_state_readin", corrupted_family=self.family, readin_gain=self.gain, n_scaled_calls=self.n_scaled)
        return d


# ------------------------------------------------------------------------------------------------------------ ID shortcut
class IdShortcutModel(CausalStateModel):
    """ID-SHORTCUT (goal5 section 22): y(t0 + h) - y(t0) = W_h f for every step h up to the long horizon, one multi-output ridge
    (penalty by a 2-fold split of the training records over a small grid), with features f = [readout history (lags), stimulus
    history (lags), time since input onset, future stimulus (16 points over the horizon), intervention identity]. The identity is a
    one-hot of (family, target set) seen in training, the same one-hot scaled by the event's signed magnitude (so a seen identity's
    effect can grow with its amplitude and flip with its sign), generic descriptors per event kind (presence, |magnitude| and signed
    magnitude over the kind's training maximum, number of targets), the number of units and events, first onset, last end, and an
    "unseen identity" flag. NO neural state:
    z = the history features. Training samples: every intervention record at its first event, its twin at the same step (identity
    none), and 4 onsets per passive record. The readout history comes from `register_readout` (the harness registers the evaluation
    records) or `encode_with_readout`. dt-aware: lag features at lag TIMES (interpolated), output rows mapped to the training grid by
    time (integer ratio dt / dt_train, else refused), future-stimulus features read at their times."""
    ref_name = "id_shortcut"
    uses_readout = True
    LAGS_S = (0.0, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2)
    N_FUT = 16
    KINDS = P.EVENT_KINDS

    def __init__(self, horizon_frac: float = 0.5, seed: int = 0):
        self.horizon_frac, self.seed = horizon_frac, seed
        self.k: dict[str, int] = {}
        self.index = HistoryIndex()
        self.train_cost: dict = {}

    def fit(self, sid: str, records: list, sysrec: dict):
        t0c, c0 = time.perf_counter(), time.process_time()
        keep = ~blowup_mask(records)
        recs = [r for r, k_ in zip(records, keep) if k_]
        self.sid, self.sysrec = sid, sysrec
        self.dt = _check_one_dt(recs)
        self.lags = sorted({round(L / self.dt) for L in self.LAGS_S})
        self.lag_s = [L * self.dt for L in self.lags]                 # lag TIMES on the training grid
        T_def = float(sysrec.get("t_end_default") or (len(_arr(recs[0], "t")) * self.dt))
        self.H = max(1, round(self.horizon_frac * T_def / self.dt))
        self.n_y = int(_arr(recs[0], "y").shape[1])
        by_key = {str(_get(r, "key")): r for r in recs}
        ids, kmax = {}, {k: 1e-12 for k in self.KINDS}
        samples = []
        for r in recs:
            evs = _events(r)
            T = len(_arr(r, "t"))
            meta = _get(r, "meta") or {}
            if evs:
                i0 = round(min(P.event_start(e) for e in evs) / self.dt)
                rel = self._relative(evs, i0 * self.dt)
                idk = self._id_key(rel)
                ids.setdefault(idk, len(ids))
                mag = experiment_cost(self._proto(rel))["magnitude"]
                for kd in self.KINDS:
                    kmax[kd] = max(kmax[kd], float(mag.get(kd, 0.0)))
                samples.append((r, i0, rel))
            elif meta.get("twin_of") and meta["twin_of"] in by_key:
                ints = _events(by_key[meta["twin_of"]])
                i0 = round(min(P.event_start(e) for e in ints) / self.dt) if ints else T // 3
                samples.append((r, i0, []))
            else:
                for fr in (0.2, 0.35, 0.5, 0.65):
                    samples.append((r, int(fr * T), []))
        self.ids, self.kmax = ids, kmax
        Fm, Ym, grp = [], [], []
        for gi, (r, i0, rel) in enumerate(samples):
            T = len(_arr(r, "t"))
            if i0 < self.lags[-1] or i0 + self.H >= T:
                continue
            y, u = np.asarray(_arr(r, "y"), float), np.asarray(_arr(r, "u"), float).reshape(T, -1)
            f = np.hstack([self._hist_feat(y[: i0 + 1], u[: i0 + 1], self.dt), self._future_feat(u[i0: i0 + self.H + 1], self.dt),
                           self._id_feat(rel)])
            Fm.append(f)
            Ym.append((y[i0 + 1: i0 + self.H + 1] - y[i0]).reshape(-1))
            grp.append(str(_get(r, "key")) if not (_get(r, "meta") or {}).get("twin_of") else (_get(r, "meta") or {})["twin_of"])
        if not Fm:
            raise ValueError("no training sample with a full horizon")
        Fm, Ym = np.stack(Fm), np.stack(Ym)
        # penalty by a 2-fold split of the sample groups (an intervention record and its twin together)
        ug = sorted(set(grp))
        perm = np.random.default_rng(self.seed).permutation(len(ug))
        fold = {g: int(perm[i] % 2) for i, g in enumerate(ug)}
        fo = np.array([fold[g] for g in grp])
        best, best_err = 1e-2, np.inf
        for lam in (1e-4, 1e-3, 1e-2, 1e-1, 1.0):
            err = 0.0
            for f_ in (0, 1):
                tr, te = fo != f_, fo == f_
                if tr.sum() < 2 or te.sum() < 1:
                    continue
                p = _ridge_fit(Fm[tr], Ym[tr], lam)
                err += float(np.sum((_ridge_apply(p, Fm[te]) - Ym[te]) ** 2))
            if err < best_err:
                best, best_err = lam, err
        self.lam = best
        self.W = _ridge_fit(Fm, Ym, best)
        self.k[sid] = len(self._hist_feat(np.zeros((self.lags[-1] + 1, self.n_y)), np.zeros((self.lags[-1] + 1, 1)), self.dt))
        self.train_cost = {"cpu_s": float(time.process_time() - c0), "wall_s": float(time.perf_counter() - t0c), "gpu_s": 0.0,
                           "sim_calls": 0, "experiments": sum(1 for r in recs if _events(r)), "n_samples": len(Fm)}
        return self

    # ---------------------------------------------------------------- features
    def _relative(self, evs, t0):
        return [dict(e, **({"t": float(e["t"]) - t0} if "t" in e else {}), **({"t0": float(e["t0"]) - t0} if "t0" in e else {}),
                     **({"t1": (None if e.get("t1") is None else float(e["t1"]) - t0)} if "t1" in e else {})) for e in evs]

    def _proto(self, rel):
        t_end = max(self.H * self.dt, 10 * self.dt)
        evs = []
        for e in rel:
            e2 = dict(e)
            for key in ("t", "t0"):
                if key in e2:
                    e2[key] = min(max(0.0, float(e2[key])), t_end)
            if e2.get("t1") is not None:
                e2["t1"] = min(max(float(e2["t1"]), 0.0), t_end)
                if e2.get("t0") is not None and e2["t1"] <= e2["t0"]:
                    e2["t1"] = min(t_end, e2["t0"] + self.dt)
            evs.append(e2)
        return {"system": self.sid, "params_seed": 0, "t_end": t_end, "dt": self.dt, "events": evs}

    def _id_key(self, rel) -> str:
        if not rel:
            return "none"
        try:
            fam = F.family_of(self._proto(rel), self.sysrec)
        except Exception:  # noqa: BLE001
            fam = "other"
        targets = sorted(P.intervened_units(self._proto(rel)))
        return f"{fam}|{','.join(str(t) for t in targets)}"

    def _hist_feat(self, y_hist, u_hist, dt: float):
        """Readout and input at the lag TIMES (interpolated; on the training grid the samples themselves) and the time since the
        input's onset (seconds, capped at 1)."""
        y_hist = np.asarray(y_hist, float)
        u_hist = np.asarray(u_hist, float).reshape(len(u_hist), -1)
        i = len(y_hist) - 1
        f = [_at_lag(y_hist, dt, L) for L in self.lag_s] + [_at_lag(u_hist, dt, L) for L in self.lag_s]
        on = np.flatnonzero(np.abs(u_hist[: i + 1]).sum(axis=1) > 1e-9)
        f.append(np.array([0.0 if len(on) == 0 else min(1.0, (i - on[0]) * float(dt))]))
        return np.concatenate(f)

    def _future_feat(self, u_future, dt: float):
        """The input at N_FUT times spread over the training horizon (H training steps), read from rows at interval dt (the last row
        repeated when the given future is shorter)."""
        u = np.asarray(u_future, float).reshape(len(u_future), -1)
        times = np.linspace(0, self.H, self.N_FUT).round() * self.dt
        idx = np.minimum(np.round(times / float(dt)).astype(int), len(u) - 1)
        return u[idx].reshape(-1)

    def _signed_mag(self, rel) -> dict[str, float]:
        """Signed amplitude x duration per kind (kick: sum delta x dt; current: sum I x duration; current_seq: sum I_j x seg); the
        other kinds carry their unsigned magnitude (accounting.experiment_cost)."""
        q = P.validate(self._proto(rel))
        out = {k: 0.0 for k in self.KINDS}
        for e in q["events"]:
            k = e["kind"]
            if k == "kick":
                out[k] += sum(float(v) for v in e["delta"].values()) * q["dt"]
            elif k == "current":
                dur = (q["t_end"] if e["t1"] is None else e["t1"]) - e["t0"]
                out[k] += sum(float(v) for v in e["targets"].values()) * dur
            elif k == "current_seq":
                out[k] += sum(float(v) for lst in e["targets"].values() for v in lst) * float(e["seg"])
        mag = experiment_cost(q)["magnitude"]
        for k in ("silence", "edge_scale", "param"):
            out[k] = float(mag.get(k, 0.0))
        return out

    def _id_feat(self, rel):
        """[one-hot identity (+ unseen flag), one-hot x signed magnitude, generic descriptors (per kind: presence, |magnitude|,
        signed magnitude, number of targets; number of units, events, first onset, last end)]."""
        n_id = len(self.ids)
        oh = np.zeros(n_id + 1)
        ohs = np.zeros(n_id)
        gen = np.zeros(4 * len(self.KINDS) + 4)
        if rel:
            key = self._id_key(rel)
            q = self._proto(rel)
            try:
                mag = experiment_cost(q)["magnitude"]
                smag = self._signed_mag(rel)
            except Exception:  # noqa: BLE001
                mag, smag = {}, {}
            s_total = float(sum(smag.get(kd, 0.0) / self.kmax.get(kd, 1.0) for kd in self.KINDS))
            if key in self.ids:
                oh[self.ids[key]] = 1.0
                ohs[self.ids[key]] = s_total
            else:
                oh[-1] = 1.0
            for i, kd in enumerate(self.KINDS):
                evk = [e for e in rel if e["kind"] == kd]
                gen[4 * i] = 1.0 if evk else 0.0
                gen[4 * i + 1] = float(mag.get(kd, 0.0)) / self.kmax.get(kd, 1.0)
                gen[4 * i + 2] = float(smag.get(kd, 0.0)) / self.kmax.get(kd, 1.0)
                gen[4 * i + 3] = float(sum(len(e.get("targets") or e.get("delta") or e.get("edges") or []) for e in evk))
            starts = [P.event_start(e) for e in rel]
            ends = [(P.event_start(e) + self.dt) if "t" in e else (self.H * self.dt if e.get("t1") is None and e["kind"] != "current_seq"
                    else (float(e["t1"]) if e["kind"] != "current_seq" else float(e["t0"]) + float(e["seg"]) * len(next(iter(e["targets"].values())))))
                    for e in rel]
            gen[-4] = float(len(P.intervened_units(q)))
            gen[-3] = float(len(rel))
            gen[-2] = float(min(starts))
            gen[-1] = float(max(ends))
        return np.hstack([oh, ohs, gen])

    # ---------------------------------------------------------------- API
    def register_readout(self, x, u, y) -> None:
        self.index.add(x, u, np.asarray(y, np.float64))

    def register_records(self, records: list) -> int:
        for r in records:
            self.register_readout(_arr(r, "x"), _arr(r, "u"), _arr(r, "y"))
        return len(records)

    def encode_with_readout(self, sid, x_hist, u_hist, y_hist, dt):
        return np.hstack([self._hist_feat(y_hist, u_hist, float(dt) if dt else self.dt), np.asarray(y_hist, float)[-1]])

    def encode(self, sid, x_hist, u_hist, dt):
        x_hist = np.asarray(x_hist)
        dth = float(dt) if dt else self.dt
        need = min(len(x_hist), int(np.ceil(self.lag_s[-1] / dth - 1e-9)) + 2)
        ys = []
        for i in range(len(x_hist) - need, len(x_hist)):
            y = self.index.get(x_hist[: i + 1], np.asarray(u_hist)[: i + 1])
            if y is None:
                raise KeyError("ID-SHORTCUT: readout history not registered for this history (register_readout)")
            ys.append(np.asarray(y, float))
        y_hist = np.vstack([np.repeat(ys[:1], len(x_hist) - need, 0), np.stack(ys)]) if len(x_hist) > need else np.stack(ys)
        return self.encode_with_readout(sid, x_hist, u_hist, y_hist, dt)

    def supports(self, sid, kind):
        return kind in P.EVENT_KINDS

    def rollout(self, sid, z0, u_future, events, dt):
        """Output row h (time h dt) = y0 + the predicted change at training step min(h n, H), n = dt / dt_train (integer, else
        refused)."""
        dth = float(dt) if dt else self.dt
        n_sub = n_substeps(dth, self.dt)
        U = np.asarray(u_future, float).reshape(len(u_future), -1)
        H = len(U) - 1
        z0 = np.asarray(z0, float)
        y0 = z0[-self.n_y:]
        hist = z0[: -self.n_y]
        f = np.hstack([hist, self._future_feat(U, dth), self._id_feat([e for e in events if e["kind"] in P.EVENT_KINDS])])
        dy = _ridge_apply(self.W, f[None, :])[0].reshape(self.H, self.n_y)
        rows = [y0]
        for h in range(1, H + 1):
            rows.append(y0 + dy[min(h * n_sub, self.H) - 1])
        return {"z": np.tile(z0, (H + 1, 1)), "y": np.stack(rows)}

    def readout(self, sid, z, u):
        z = np.atleast_2d(np.asarray(z, float))
        return z[:, -self.n_y:]

    def info(self):
        return {"k": dict(self.k), "method": "ref:id_shortcut", "method_version": "2", "history": {s: self.lags[-1] + 1 for s in self.k},
                "dt_train": getattr(self, "dt", None),
                "n_params": {"encoder": {s: 0 for s in self.k}, "transition": int(self.W[2].size), "read_in": {s: 0 for s in self.k},
                             "readout": {s: 0 for s in self.k}},
                "train_cost": dict(self.train_cost), "ridge_lambda": self.lam, "n_ids": len(self.ids)}


# ------------------------------------------------------------------------------------------------------------ entry point
REF_NAMES = ("no_effect", "true_state", "full_state", "obs_shortcut", "random_k", "pca_k", "id_shortcut")
#: extra CANDIDATES for the Level B full-state bound only (never a calibration reference): FULL-STATE with the joint one-step fit. The
#: bound is one choice per system kind by the pre-registered rule (lowest median EE; PROTOCOL section 8), so an extra candidate can only
#: make the comparator stronger (LOG P4-D51)
BOUND_EXTRA_REFS = ("full_state_joint",)


@dataclass
class FittedRefs:
    models: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)


def fit_reference(name: str, sid: str, records: list, sysrec: dict, *, k: int | None = None, truth: dict | None = None,
                  base: CausalStateModel | None = None, cfg: LearnerConfig = DEFAULT_CFG, drop: tuple[int, ...] = ()) -> CausalStateModel:
    """Fit one reference on the training records of one system. truth: {"z": {key: (T, k)}, "z_obs": {...}, "draw": {key: (d,)}}
    (synthetic only; "draw" = the effective draw parameters: TRUE-STATE / OBS-SHORTCUT encode [z, draw], LOG P4-D43);
    'true_state_zonly' / 'obs_shortcut_zonly' = the descriptive references on z / z_obs alone; k: the dimension of RANDOM-k / PCA-k;
    base: the passive model of NO-EFFECT (default: a FULL-STATE reference fitted here); drop: true coordinates removed from
    TRUE-STATE (the missing-state corruption)."""
    if name == "full_state":
        return FullStateModel(cfg).fit(sid, records, sysrec)
    if name == "full_state_joint":
        m = FullStateModel(dataclasses.replace(cfg, one_step_mode="joint"))
        m.ref_name = "full_state_joint"
        return m.fit(sid, records, sysrec)
    if name in ("true_state", "obs_shortcut", "true_state_zonly", "obs_shortcut_zonly"):
        which = "z" if name.startswith("true_state") else "z_obs"
        tb = (truth or {}).get(which)
        if not tb:
            raise ValueError(f"{name} needs truth['{which}']")
        use_draw = not name.endswith("_zonly")
        return TruthStateModel(which, cfg, drop=drop if which == "z" else (), use_draw=use_draw).fit_truth(
            sid, records, sysrec, tb, (truth or {}).get("draw") if use_draw else None)
    if name in ("pca_k", "random_k"):
        if not k:
            raise ValueError(f"{name} needs k")
        return ProjectionStateModel(name.split("_")[0], int(k), cfg).fit(sid, records, sysrec)
    if name == "id_shortcut":
        return IdShortcutModel(seed=cfg.seed).fit(sid, records, sysrec)
    if name == "no_effect":
        return NoEffectModel(base if base is not None else FullStateModel(cfg).fit(sid, records, sysrec))
    raise KeyError(name)


def fit_references(sid: str, records: list, sysrec: dict, *, names=REF_NAMES, k: int | None = None, truth: dict | None = None,
                   cfg: LearnerConfig = DEFAULT_CFG) -> FittedRefs:
    """Fit several references; failures are recorded (never silently dropped). NO-EFFECT reuses the FULL-STATE fit."""
    out = FittedRefs()
    for name in names:
        if name == "no_effect":
            continue
        if name in ("true_state", "obs_shortcut", "true_state_zonly", "obs_shortcut_zonly") and not (truth or {}).get(
                "z" if name.startswith("true_state") else "z_obs"):
            continue
        if name in ("pca_k", "random_k") and not k:
            continue
        try:
            out.models[name] = fit_reference(name, sid, records, sysrec, k=k, truth=truth, cfg=cfg)
        except Exception as exc:  # noqa: BLE001
            out.errors[name] = f"{type(exc).__name__}: {str(exc)[:300]}"
    if "no_effect" in names:
        base = out.models.get("full_state")
        try:
            out.models["no_effect"] = NoEffectModel(base if base is not None else FullStateModel(cfg).fit(sid, records, sysrec))
        except Exception as exc:  # noqa: BLE001
            out.errors["no_effect"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    return out
