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

THE GENERIC CONTROLLED LEARNER (one design for every state-based reference, so they differ only in the state s):

    state            s = [s_dyn, traces]: s_dyn = the reference's state (compact references: s_dyn = z, no traces; FULL-STATE:
                     s_dyn = x_t and two causal exponential traces of x with time constants 1/4 and 1 x the short horizon (at least 2
                     samples): the short delay embedding in Markov form, so rollouts update it without storing a history)
    read-in matrix   K (d_dyn x N_obs): maps an observed-space perturbation to s_dyn. Compact references: K = P + dK, where P is the
                     ridge probe x -> s_dyn fitted on training samples and dK a ridge correction (shrunk towards 0) fitted on the
                     training KICKS against their counterfactual twins (the observed one-step effect s_int(i+1) - s_twin(i+1) - P dx);
                     units never kicked in training keep the probe. FULL-STATE: K = identity (exact).
    decoder          x_hat = D(s): ridge s_dyn -> x (compact); x_hat = s_dyn (full)
    interventions    per step, a per-unit descriptor A (N_obs x 7): current I (current + current_seq), silence drive m * x_hat, silence
                     mask m, edge drive sum over active scaled edges into the unit of (F - 1) * x_hat_pre (F = product of active factors;
                     unobserved presynaptic units contribute 0), gain drive (G - 1) * x_hat, threshold offset D, time-constant drive
                     (C - 1) * x_hat. The dynamics receive c = K A (d_dyn x 7, flattened): a target that is observed is representable
                     even if it was never intervened in training; unobserved targets act only through their effect on observed units.
                     An intervention KIND whose channels were never active in training is not supported (supports() False: the
                     evaluator scores abstention) and the weights of never-active channel features are exactly zero.
                     Kicks are instantaneous jumps s_dyn += K dx (clipped at 0 for non-negative data; the recorded sample at a kick's
                     time is the pre-kick state, the jump acts before the step, as in the simulators)
    dynamics         s_dyn(t+1) = s_dyn(t)^+ + MLP_f([s_norm, u_norm, c_norm]) * dsd  (MLP: depth 2, width 128 (compact) / 256 (full),
                     GELU); trained one-step (all event rows + a seeded subsample of passive rows; half of every batch drawn from the
                     RESPONSE rows: intervention windows and the short horizon after them, so passive rows do not dominate the
                     intervention-effect fit), then an unrolled multi-step phase (windows of max(8, 1/4 short horizon) steps, half of
                     them starting in response rows; intervention inputs teacher-forced) against rollout drift
    readout          y = MLP_g([s_norm, u_norm]) (batches balanced with response rows like the dynamics)
    lift             bounded least squares over kick vectors on up to three distinct subsets of the targetable observed units (all;
                     the columns of K with the largest norms; a seeded random half): min ||K dx - dz||^2 + 1e-6 ||dx||^2 subject to the
                     admissible range (dx >= -x_now for non-negative data, |dx| <= max_kick if given)
    budget           LearnerConfig defaults: 2,000 one-step Adam steps (batch 1,024, lr 1e-3, cosine), 600 multi-step steps (lr 3e-4),
                     1,500 readout steps; torch on CPU with 2 threads; deterministic given the seed

Training data exclude finite blow-ups (max |x| or |y| above 100x the training median). TRUE-STATE / OBS-SHORTCUT need the truth of the
training trajectories (`truth={"z": {key: (T, k)}}`); at evaluation the harness REGISTERS the truth of every history it will encode
(`register_truth` / `register_records`): encode then returns the exact state for a registered history and falls back to a ridge probe
from [x_t, x_{t-1}, x_{t-2}] otherwise (counted in info()["n_probe_encodes"]). The ID-SHORTCUT needs the readout history: the harness
registers (x, u, y) of the evaluation records (`register_readout`), or calls `encode_with_readout`.
"""

from __future__ import annotations

import hashlib
import itertools
import time
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
    steps_multi: int = 600
    window: int = 8
    batch: int = 1024
    lr: float = 1e-3
    lr_multi: float = 3e-4
    readout_steps: int = 1500
    max_passive_rows: int = 200_000
    trace_fracs: tuple[float, ...] = (0.25, 1.0)
    window_frac: float = 0.25
    resp_share: float = 0.5
    probe_lambda: float = 1e-4
    kick_lambda: float = 1.0
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

    def get(self, x_hist, u_hist):
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
                return pay[i]
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
    """Shared generic controlled learner (module docstring). Subclasses define the state: `_dyn_states(rec)` (T, d_dyn) for a training
    record, `_encode_dyn(x_hist, u_hist)` for evaluation, the auxiliary trace blocks (`n_aux`, FULL-STATE only) and whether K is exact
    (`_exact_readin`)."""

    ref_name = "abstract"
    n_aux = 0
    _exact_readin = False

    def __init__(self, cfg: LearnerConfig = DEFAULT_CFG):
        self.cfg = cfg
        self.k: dict[str, int] = {}
        self.sid = None
        self.train_cost: dict = {}
        self.fit_notes: dict = {}
        self.alphas: list[float] = []

    # ---------------------------------------------------------------- hooks
    def _dyn_states(self, rec) -> np.ndarray:
        raise NotImplementedError

    def _prepare(self, records: list, sysrec: dict) -> None:
        """Fit the encoder-side pieces (projections, probes) before the dynamics."""

    def _encode_dyn(self, sid, x_hist, u_hist, dt) -> np.ndarray:
        raise NotImplementedError

    def _set_traces(self, short_steps: float) -> None:
        """Auxiliary trace blocks (FULL-STATE): exponential moving averages of the dynamic state with time constants
        cfg.trace_fracs x the short horizon (at least 2 samples)."""
        self.alphas = []

    # ---------------------------------------------------------------- traces
    def _aux_rows(self, S_dyn: np.ndarray) -> np.ndarray | None:
        if not self.n_aux:
            return None
        return np.hstack([_ema(S_dyn, a) for a in self.alphas])

    # ---------------------------------------------------------------- fitting
    def fit(self, sid: str, records: list, sysrec: dict):
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
        self.dt = _rec_dt(recs[0])
        self.n_u = int(np.atleast_2d(_arr(recs[0], "u")).shape[1]) if _arr(recs[0], "u").ndim > 1 else 1
        self.n_y = int(_arr(recs[0], "y").shape[1])
        t_def = float(sysrec.get("t_end_default") or (len(_arr(recs[0], "t")) - 1) * self.dt)
        short_steps = max(1.0, SHORT_FRAC * t_def / self.dt)
        self._set_traces(short_steps)
        allx = np.concatenate([_arr(r, "x") for r in recs]).astype(np.float64)
        self.nonneg = bool((allx >= -1e-9).all())
        del allx
        self._prepare(recs, sysrec)
        S = [np.asarray(self._dyn_states(r), np.float64) for r in recs]
        self.d_dyn = S[0].shape[1]
        self.k[sid] = int(self.d_dyn * (1 + self.n_aux))
        U = [np.asarray(_arr(r, "u"), np.float64).reshape(len(_arr(r, "u")), -1) for r in recs]
        Y = [np.asarray(_arr(r, "y"), np.float64) for r in recs]
        # probe, decoder and read-in matrix
        if self._exact_readin:
            self.K = np.eye(self.d_dyn, self.N)
            self.dec = None
        else:
            Xs = np.concatenate([np.asarray(_arr(r, "x"), np.float64) for r in recs])
            Ss = np.concatenate(S)
            sub = np.random.default_rng(cfg.seed).permutation(len(Xs))[:60_000]
            self.probe = _ridge_fit(Xs[sub], Ss[sub], cfg.probe_lambda)
            Pm = _ridge_linear(self.probe).T                       # d_dyn x N
            self.dec = _ridge_fit(Ss[sub], Xs[sub], cfg.probe_lambda)
            self.K = Pm + self._kick_correction(recs, S, Pm)
            del Xs, Ss
        # per-record timelines, jumps, teacher-forced channels and traces; one global table (rows of all records)
        import scipy.sparse as sp
        n_c = self.d_dyn * N_CH
        tls = [Timeline(_events(r), len(s), self.dt, self.col) for r, s in zip(recs, S)]
        J, C, A = [], [], []
        for s, tl in zip(S, tls):
            Jr = np.zeros_like(s)
            for j, kk in tl.kicks.items():
                Jr[j] = self._jump(kk)
            J.append(sp.csr_matrix(Jr))
            C.append(self._channel_rows(self._post(s + Jr), tl))
            if self.n_aux:
                A.append(self._aux_rows(s).astype(np.float32))
        lens = np.array([len(s) for s in S])
        offs = np.concatenate([[0], np.cumsum(lens)])
        S_cat = np.concatenate(S)
        del S
        U_cat = np.concatenate(U)
        Y_cat = np.concatenate(Y)
        del U, Y
        J_cat = sp.vstack(J).tocsr()
        C_cat = sp.vstack(C).tocsr()
        AUX = np.concatenate(A) if A else None
        del J, C, A
        n_rows = len(S_cat)
        start = np.repeat(offs[:-1], lens)
        last = np.repeat(offs[1:] - 1, lens)
        # normalisation
        mu, sd = S_cat.mean(0), S_cat.std(0) + 1e-6
        if AUX is not None:
            mu = np.concatenate([mu, AUX.mean(0).astype(np.float64)])
            sd = np.concatenate([sd, AUX.std(0).astype(np.float64) + 1e-6])
        self.s_mu, self.s_sd = mu, sd
        self.u_mu, self.u_sd = U_cat.mean(0), U_cat.std(0) + 1e-6
        self.ch_scale = np.ones(n_c)
        Cc = C_cat.tocsc()
        for f_ in range(n_c):
            v = Cc.data[Cc.indptr[f_]: Cc.indptr[f_ + 1]]
            if v.size:
                self.ch_scale[f_] = float(np.sqrt(np.mean(v ** 2))) + 1e-9
        valid = np.flatnonzero(np.arange(n_rows) < last)
        post_v = self._post(S_cat[valid] + J_cat[valid].toarray())
        Dall = S_cat[valid + 1] - post_v
        self.d_sd = Dall.std(0) + 1e-9 * (np.abs(Dall).max() + 1e-12)
        self.y_mu, self.y_sd = Y_cat.mean(0), Y_cat.std(0) + 1e-9
        del post_v, Dall
        # rows: every event row + a seeded subsample of passive rows; RESPONSE rows = event rows and the short horizon after them
        rng = np.random.default_rng(cfg.seed)
        ev = (np.asarray(C_cat.getnnz(axis=1)).ravel() > 0) | (np.asarray(J_cat.getnnz(axis=1)).ravel() > 0)
        n_short = round(short_steps)
        cs = np.concatenate([[0], np.cumsum(ev)])
        lo = np.maximum(np.arange(n_rows) - n_short, start)
        resp = (cs[np.arange(n_rows) + 1] - cs[lo]) > 0
        ev_v = ev[valid]
        n_pass = int((~ev_v).sum())
        frac = min(1.0, cfg.max_passive_rows / max(1, n_pass))
        sel = valid[ev_v | (rng.random(len(valid)) < frac)]
        resp_rows = valid[resp[valid]]
        self.fit_notes.update(one_step_rows=len(sel), event_rows=int(ev_v.sum()), response_rows=len(resp_rows),
                              short_steps=float(short_steps), trace_alphas=list(self.alphas))
        tab = {"S": S_cat, "U": U_cat, "Y": Y_cat, "J": J_cat, "C": C_cat, "A": AUX, "start": start, "last": last, "resp": resp}
        active = np.zeros(n_c, bool)
        active[np.unique(C_cat.indices)] = True
        ch_seen = {int(c) for c in np.flatnonzero(active) % N_CH}
        self.kinds_seen = sorted({k for k, chs in KIND_CHANNELS.items() if chs & ch_seen} | {"kick"})
        self.fit_notes["kinds_seen"] = list(self.kinds_seen)
        with _TorchThreads(cfg.threads):
            torch.manual_seed(int(cfg.seed))
            n_state = self.d_dyn * (1 + self.n_aux) + self.n_u
            n_in = n_state + n_c
            hid = cfg.hidden_full if self._exact_readin else cfg.hidden
            net = _make_mlp(n_in, self.d_dyn, hid, cfg.depth)
            with torch.no_grad():
                net[0].weight[:, n_state:][:, torch.tensor(~active)] = 0.0
            self._train_one_step(net, sel, resp_rows, tab, torch)
            m = max(int(cfg.window), round(cfg.window_frac * short_steps))
            self.fit_notes["window"] = m
            if cfg.steps_multi > 0 and m > 1:
                self._train_multi(net, tab, m, torch)
            with torch.no_grad():
                # a channel feature never active in training has an untrained weight: exactly zero (no represented effect)
                net[0].weight[:, n_state:][:, torch.tensor(~active)] = 0.0
            self.f = _NumpyMLP(net.eval())
            ro = _make_mlp(self.d_dyn * (1 + self.n_aux) + self.n_u, self.n_y, hid, cfg.depth)
            self._train_readout(ro, tab, torch)
            self.g = _NumpyMLP(ro.eval())
        self.train_cost = {"cpu_s": float(time.process_time() - c_start), "wall_s": float(time.perf_counter() - t_start),
                           "gpu_s": 0.0, "sim_calls": 0, "experiments": int(sum(1 for r in recs if _events(r)))}
        return self

    def _kick_correction(self, recs, S, Pm) -> np.ndarray:
        """dK from training kicks against their twins (ridge, shrunk towards 0; relative penalty cfg.kick_lambda)."""
        by_key = {str(_get(r, "key")): i for i, r in enumerate(recs)}
        Xk, Rk = [], []
        for i, r in enumerate(recs):
            tw = (_get(r, "meta") or {}).get("twin_of")
            if not tw or tw not in by_key:
                continue
            # r is the TWIN of by_key[tw]: the intervention record is recs[by_key[tw]]
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
                Rk.append(S[ii][j + 1] - S[i][j + 1] - Pm @ dx)
        self.fit_notes["kick_pairs"] = len(Xk)
        if not Xk:
            return np.zeros_like(Pm)
        Xk, Rk = np.stack(Xk), np.stack(Rk)
        G = Xk.T @ Xk
        lam = self.cfg.kick_lambda * max(float(np.mean(np.diag(G))), 1e-12)
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

    def _seg_c(self, units: list[int], A: np.ndarray) -> np.ndarray:
        """Channel rows (n, d_dyn * 7) = (K A) flattened row-major (latent coordinate major, channel minor)."""
        n = A.shape[0]
        if not units:
            return np.zeros((n, self.d_dyn * N_CH))
        if self._exact_readin:
            c = np.zeros((n, self.d_dyn, N_CH))
            c[:, units, :] = A
            return c.reshape(n, -1)
        return np.einsum("kn,snc->skc", self.K[:, units], A).reshape(n, -1)

    def _channel_rows(self, s_post: np.ndarray, tl: Timeline):
        """Teacher-forced channel rows of one record as a CSR matrix (T, d_dyn * 7) (all-zero rows outside intervention windows)."""
        import scipy.sparse as sp
        T = len(s_post)
        n_c = self.d_dyn * N_CH
        R_, C_, V_ = [], [], []
        for a, b, st in tl.segments:
            b = min(b, T)
            if b <= a:
                continue
            units, A = self._seg_channels(st, self._decode_rows(s_post[a:b]))
            if not units:
                continue
            if self._exact_readin:
                rr = np.repeat(np.arange(a, b), len(units) * N_CH)
                cc = np.tile((np.asarray(units)[:, None] * N_CH + np.arange(N_CH)[None, :]).reshape(-1), b - a)
                vv = A.reshape(-1)
            else:
                cm = self._seg_c(units, A)
                rr = np.repeat(np.arange(a, b), n_c)
                cc = np.tile(np.arange(n_c), b - a)
                vv = cm.reshape(-1)
            m = vv != 0
            R_.append(rr[m])
            C_.append(cc[m])
            V_.append(vv[m])
        if not R_:
            return sp.csr_matrix((T, n_c))
        return sp.csr_matrix((np.concatenate(V_), (np.concatenate(R_), np.concatenate(C_))), shape=(T, n_c))

    def _inputs(self, s_full: np.ndarray, u: np.ndarray, c: np.ndarray) -> np.ndarray:
        return np.hstack([(s_full - self.s_mu) / self.s_sd, (u - self.u_mu) / self.u_sd, c / self.ch_scale])

    # ---------------------------------------------------------------- training loops (vectorised gathers on the global table)
    def _full(self, post: np.ndarray, tab: dict, idx: np.ndarray) -> np.ndarray:
        return np.hstack([post, tab["A"][idx]]) if tab["A"] is not None else post

    def _gather(self, tab: dict, idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Network inputs and post-jump dynamic states for global rows idx (teacher-forced)."""
        post = self._post(tab["S"][idx] + tab["J"][idx].toarray())
        return self._inputs(self._full(post, tab, idx), tab["U"][idx], tab["C"][idx].toarray()), post

    def _batch_rows(self, rng, sel: np.ndarray, resp_rows: np.ndarray, bs: int) -> np.ndarray:
        """A batch with cfg.resp_share of its rows from the RESPONSE rows (interventions and the short horizon after them)."""
        nb = round(self.cfg.resp_share * bs) if len(resp_rows) else 0
        parts = [sel[rng.integers(0, len(sel), bs - nb)]]
        if nb:
            parts.append(resp_rows[rng.integers(0, len(resp_rows), nb)])
        return np.concatenate(parts)

    def _train_one_step(self, net, sel: np.ndarray, resp_rows: np.ndarray, tab: dict, torch) -> None:
        cfg = self.cfg
        opt = torch.optim.Adam(net.parameters(), lr=cfg.lr)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, max(1, cfg.steps_one))
        rng = np.random.default_rng(cfg.seed + 11)
        bs = min(cfg.batch, len(sel))
        losses = []
        for step in range(cfg.steps_one):
            idx = self._batch_rows(rng, sel, resp_rows, bs)
            Xb, post = self._gather(tab, idx)
            Yb = (tab["S"][idx + 1] - post) / self.d_sd
            loss = torch.mean((net(torch.tensor(Xb, dtype=torch.float32)) - torch.tensor(Yb, dtype=torch.float32)) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            if step % 200 == 0 or step == cfg.steps_one - 1:
                losses.append(float(loss.detach()))
        self.fit_notes["one_step_loss"] = losses

    def _train_multi(self, net, tab: dict, m: int, torch) -> None:
        """Unrolled windows of m steps from teacher-forced starts (half of them in response rows); intervention inputs teacher-
        forced, dynamic states and traces predicted."""
        cfg = self.cfg
        n = len(tab["S"])
        ok = np.arange(n) + m <= tab["last"]
        starts = np.flatnonzero(ok)
        if not len(starts):
            return
        starts_r = np.flatnonzero(ok & tab["resp"])
        opt = torch.optim.Adam(net.parameters(), lr=cfg.lr_multi)
        rng = np.random.default_rng(cfg.seed + 13)
        bs = min(max(64, cfg.batch // m), len(starts))
        dd = self.d_dyn
        sd_t = torch.tensor(self.d_sd, dtype=torch.float32)
        smu, ssd = torch.tensor(self.s_mu, dtype=torch.float32), torch.tensor(self.s_sd, dtype=torch.float32)
        umu, usd = torch.tensor(self.u_mu, dtype=torch.float32), torch.tensor(self.u_sd, dtype=torch.float32)
        csc = torch.tensor(self.ch_scale, dtype=torch.float32)
        dsc = torch.tensor(self.s_sd[:dd], dtype=torch.float32)
        alphas = [float(a) for a in self.alphas]
        clip = self._exact_readin and self.nonneg
        losses = []
        for step in range(cfg.steps_multi):
            idx = self._batch_rows(rng, starts, starts_r, bs)
            s = torch.tensor(tab["S"][idx], dtype=torch.float32)
            aux = ([torch.tensor(tab["A"][idx][:, j * dd:(j + 1) * dd], dtype=torch.float32) for j in range(self.n_aux)]
                   if tab["A"] is not None else [])
            loss = 0.0
            for q in range(m):
                rows = idx + q
                post = s + torch.tensor(tab["J"][rows].toarray(), dtype=torch.float32)
                if clip:
                    post = torch.clamp(post, min=0.0)
                full = torch.cat([post] + aux, dim=1) if aux else post
                u = torch.tensor(tab["U"][rows], dtype=torch.float32)
                c = torch.tensor(tab["C"][rows].toarray(), dtype=torch.float32)
                nxt = post + net(torch.cat([(full - smu) / ssd, (u - umu) / usd, c / csc], dim=1)) * sd_t
                if clip:
                    nxt = torch.clamp(nxt, min=0.0)
                tgt = torch.tensor(tab["S"][rows + 1], dtype=torch.float32)
                loss = loss + torch.mean(((nxt - tgt) / dsc) ** 2)
                aux = [a_ + al * (nxt - a_) for a_, al in zip(aux, alphas)]
                s = nxt
            loss = loss / m
            opt.zero_grad()
            loss.backward()
            opt.step()
            if step % 100 == 0 or step == cfg.steps_multi - 1:
                losses.append(float(loss.detach()))
        self.fit_notes["multi_step_loss"] = losses

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
            full = self._full(tab["S"][idx], tab, idx)
            Xb = np.hstack([(full - self.s_mu) / self.s_sd, (tab["U"][idx] - self.u_mu) / self.u_sd])
            Yb = (tab["Y"][idx] - self.y_mu) / self.y_sd
            loss = torch.mean((ro(torch.tensor(Xb, dtype=torch.float32)) - torch.tensor(Yb, dtype=torch.float32)) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()

    # ---------------------------------------------------------------- API
    def encode(self, sid, x_hist, u_hist, dt):
        dyn = np.asarray(self._encode_dyn(sid, x_hist, u_hist, dt), float)
        if not self.n_aux:
            return dyn
        X = np.asarray(x_hist, float)
        return np.hstack([dyn] + [_ema(X, a)[-1] for a in self.alphas])

    def supports(self, sid, kind):
        """Kicks always (they act through the read-in matrix K); other kinds only when their channels were active in training (a
        kind never seen has no represented effect: the evaluator scores abstention, never a silent 'no effect')."""
        if kind == "current_seq":
            kind = "current"
        return kind in getattr(self, "kinds_seen", P.EVENT_KINDS)

    def rollout(self, sid, z0, u_future, events, dt):
        dt = float(dt) if dt else self.dt
        U = np.asarray(u_future, float).reshape(len(u_future), -1)
        H = len(U) - 1
        dd = self.d_dyn
        z0 = np.asarray(z0, float)
        s = z0[:dd].copy()
        aux = [z0[dd * (j + 1): dd * (j + 2)].copy() for j in range(self.n_aux)]
        tl = Timeline([e for e in events if e["kind"] in P.EVENT_KINDS], max(H, 1), dt, self.col)
        out = [z0.copy()]
        zero_c = np.zeros(dd * N_CH)
        for j in range(H):
            if j in tl.kicks:
                s = self._post(s + self._jump(tl.kicks[j]))
            st = tl.static_at(j)
            c = zero_c if st is None else self._seg_c(*self._seg_channels(st, self._decode(s)[None, :]))[0]
            full = np.hstack([s] + aux) if aux else s
            ds = self.f(self._inputs(full, U[j], c)[None, :])[0] * self.d_sd
            s = self._post(s + ds)
            aux = [a_ + al * (s - a_) for a_, al in zip(aux, self.alphas)]
            out.append(np.hstack([s] + aux) if aux else s.copy())
        Z = np.stack(out)
        return {"z": Z, "y": self.readout(sid, Z, U[: len(Z)])}

    def readout(self, sid, z, u):
        z = np.atleast_2d(np.asarray(z, float))
        u = np.asarray(u, float).reshape(len(z), -1) if np.size(u) else np.zeros((len(z), self.n_u))
        inp = np.hstack([(z - self.s_mu) / self.s_sd, (u - self.u_mu) / self.u_sd])
        return self.g(inp) * self.y_sd + self.y_mu

    def read_in(self, sid, z, event):
        if event["kind"] == "kick":
            dx = np.zeros(self.N)
            for n, v in event["delta"].items():
                if int(n) in self.col:
                    dx[self.col[int(n)]] += float(v)
            dz = self.K @ dx
            return {"dz": np.hstack([dz, np.zeros(self.d_dyn * self.n_aux)])}
        if event["kind"] in P.EVENT_KINDS:
            return {"operator": {"type": "mlp_channels", "kind": event["kind"], "channels": list(CH_NAMES),
                                 "read_in_matrix": "K (d_dyn x N_obs)", "note": "per-unit descriptors projected by K enter the dynamics MLP"}}
        return {}

    def lift(self, sid, x_hist, u_hist, delta_z, n_candidates=3, constraints=None):
        """Kick lifts of the dynamic part of delta_z (trace coordinates cannot be set by an instantaneous intervention; their
        requested part is part of the miss)."""
        from scipy.optimize import lsq_linear
        cons = constraints or {}
        dz = np.asarray(delta_z, float)[: self.d_dyn]
        allowed = cons.get("targets")
        cols = [self.col[int(n)] for n in (allowed if allowed is not None else self.observed) if int(n) in self.col]
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
            if self.nonneg:
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
            pdz = np.hstack([self.K @ full_dx, np.zeros(self.d_dyn * self.n_aux)])
            out.append({"events": [{"kind": "kick", "t": 0.0, "delta": delta}], "predicted_dz": pdz,
                        "cost": float(np.abs(full_dx).sum() * self.dt)})
            if len(out) >= n_candidates:
                break
        return out

    def info(self):
        npar_f = self.f.n_params() if hasattr(self, "f") else 0
        npar_g = self.g.n_params() if hasattr(self, "g") else 0
        enc = 0 if self._exact_readin else int(self.K.size)
        hist = 1 if not self.alphas else int(np.ceil(3.0 / min(self.alphas)))
        return {"k": dict(self.k), "k_range": {s: [v, v] for s, v in self.k.items()}, "method": f"ref:{self.ref_name}",
                "method_version": "2", "history": {s: hist for s in self.k},
                "n_params": {"encoder": {s: enc for s in self.k}, "transition": npar_f, "read_in": {s: int(self.K.size) for s in self.k},
                             "readout": {s: npar_g for s in self.k}},
                "train_cost": dict(self.train_cost), "fit_notes": dict(self.fit_notes)}


# ------------------------------------------------------------------------------------------------------------ concrete references
class FullStateModel(_LearnedStateModel):
    """FULL-STATE: s = [x_t, EMA_tau1(x)_t, EMA_tau2(x)_t] (causal exponential traces of the observed microstate, tau = cfg.trace_fracs x
    the short horizon, at least 2 samples; the 'short delay embedding' in Markov form), K = identity."""
    ref_name = "full_state"
    _exact_readin = True

    def __init__(self, cfg: LearnerConfig = DEFAULT_CFG):
        super().__init__(cfg)
        self.n_aux = len(cfg.trace_fracs)

    def _set_traces(self, short_steps: float) -> None:
        taus = [max(2.0, float(f) * short_steps) for f in self.cfg.trace_fracs]
        self.alphas = [float(1.0 - np.exp(-1.0 / t)) for t in taus]
        self.fit_notes["trace_taus_steps"] = taus

    def _dyn_states(self, rec):
        return np.asarray(_arr(rec, "x"), np.float64)

    def _encode_dyn(self, sid, x_hist, u_hist, dt):
        return np.asarray(x_hist, float)[-1]


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


class TruthStateModel(_LearnedStateModel):
    """TRUE-STATE ("z") / OBS-SHORTCUT ("z_obs"): the state is a truth array per training record; evaluation histories must be
    registered (`register_truth`, `register_records`); unregistered histories fall back to a ridge probe from [x_t, x_{t-1}, x_{t-2}]."""

    def __init__(self, which: str = "z", cfg: LearnerConfig = DEFAULT_CFG):
        super().__init__(cfg)
        assert which in ("z", "z_obs")
        self.which = which
        self.ref_name = "true_state" if which == "z" else "obs_shortcut"
        self.index = HistoryIndex()
        self.n_probe_encodes = 0
        self.truth_train: dict[str, np.ndarray] = {}

    def fit_truth(self, sid: str, records: list, sysrec: dict, truth_by_key: dict[str, np.ndarray]):
        missing = [str(_get(r, "key")) for r in records if str(_get(r, "key")) not in truth_by_key]
        if missing:
            raise ValueError(f"truth missing for {len(missing)} training records (e.g. {missing[0]})")
        self.truth_train = {str(_get(r, "key")): np.asarray(truth_by_key[str(_get(r, "key"))], np.float64) for r in records}
        return self.fit(sid, records, sysrec)

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
            self.index.add(x, _arr(r, "u"), z)
        Xl, Zl = np.concatenate(Xl), np.concatenate(Zl)
        sub = np.random.default_rng(self.cfg.seed + 31).permutation(len(Xl))[:60_000]
        self.delay_probe = _ridge_fit(Xl[sub], Zl[sub], 1e-3)

    def _dyn_states(self, rec):
        return self.truth_train[str(_get(rec, "key"))]

    def register_truth(self, x, u, z) -> None:
        """Evaluator-side: the exact state of every prefix of this (x, u) history."""
        self.index.add(x, u, np.asarray(z, np.float64))

    def register_records(self, records: list, truth_by_key: dict[str, np.ndarray]) -> int:
        n = 0
        for r in records:
            z = truth_by_key.get(str(_get(r, "key")))
            if z is not None:
                self.register_truth(_arr(r, "x"), _arr(r, "u"), z)
                n += 1
        return n

    def _encode_dyn(self, sid, x_hist, u_hist, dt):
        z = self.index.get(x_hist, u_hist)
        if z is not None:
            return np.asarray(z, float).copy()
        self.n_probe_encodes += 1
        x = np.asarray(x_hist, float)
        l1 = x[-2] if len(x) > 1 else x[-1]
        l2 = x[-3] if len(x) > 2 else l1
        return _ridge_apply(self.delay_probe, np.hstack([x[-1], l1, l2])[None, :])[0]

    def info(self):
        d = super().info()
        d["n_probe_encodes"] = int(self.n_probe_encodes)
        d["n_registered_samples"] = len(self.index)
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

    def register_truth(self, x, u, z) -> None:
        if hasattr(self.base, "register_truth"):
            self.base.register_truth(x, u, z)

    def info(self):
        d = dict(self.base.info() or {})
        d["method"] = "ref:no_effect"
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
    records) or `encode_with_readout`."""
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
        self.dt = _rec_dt(recs[0])
        self.lags = sorted({round(L / self.dt) for L in self.LAGS_S})
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
            f = np.hstack([self._hist_feat(y[: i0 + 1], u[: i0 + 1]), self._future_feat(u[i0: i0 + self.H + 1]), self._id_feat(rel)])
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
        self.k[sid] = len(self._hist_feat(np.zeros((self.lags[-1] + 1, self.n_y)), np.zeros((self.lags[-1] + 1, 1))))
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

    def _hist_feat(self, y_hist, u_hist):
        y_hist = np.asarray(y_hist, float)
        u_hist = np.asarray(u_hist, float).reshape(len(u_hist), -1)
        i = len(y_hist) - 1
        f = [y_hist[max(0, i - L)] for L in self.lags] + [u_hist[max(0, i - L)] for L in self.lags]
        on = np.flatnonzero(np.abs(u_hist[: i + 1]).sum(axis=1) > 1e-9)
        f.append(np.array([0.0 if len(on) == 0 else min(1.0, (i - on[0]) * self.dt)]))
        return np.concatenate(f)

    def _future_feat(self, u_future):
        u = np.asarray(u_future, float).reshape(len(u_future), -1)
        idx = np.linspace(0, len(u) - 1, self.N_FUT).round().astype(int)
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
        return np.hstack([self._hist_feat(y_hist, u_hist), np.asarray(y_hist, float)[-1]])

    def encode(self, sid, x_hist, u_hist, dt):
        x_hist = np.asarray(x_hist)
        need = min(len(x_hist), self.lags[-1] + 1)
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
        U = np.asarray(u_future, float).reshape(len(u_future), -1)
        H = len(U) - 1
        z0 = np.asarray(z0, float)
        y0 = z0[-self.n_y:]
        hist = z0[: -self.n_y]
        Up = U if len(U) >= self.H + 1 else np.vstack([U, np.repeat(U[-1:], self.H + 1 - len(U), 0)])
        f = np.hstack([hist, self._future_feat(Up[: self.H + 1]), self._id_feat([e for e in events if e["kind"] in P.EVENT_KINDS])])
        dy = _ridge_apply(self.W, f[None, :])[0].reshape(self.H, self.n_y)
        rows = [y0]
        for h in range(1, H + 1):
            rows.append(y0 + dy[min(h, self.H) - 1])
        return {"z": np.tile(z0, (H + 1, 1)), "y": np.stack(rows)}

    def readout(self, sid, z, u):
        z = np.atleast_2d(np.asarray(z, float))
        return z[:, -self.n_y:]

    def info(self):
        return {"k": dict(self.k), "method": "ref:id_shortcut", "method_version": "1", "history": {s: self.lags[-1] + 1 for s in self.k},
                "n_params": {"encoder": {s: 0 for s in self.k}, "transition": int(self.W[2].size), "read_in": {s: 0 for s in self.k},
                             "readout": {s: 0 for s in self.k}},
                "train_cost": dict(self.train_cost), "ridge_lambda": self.lam, "n_ids": len(self.ids)}


# ------------------------------------------------------------------------------------------------------------ entry point
REF_NAMES = ("no_effect", "true_state", "full_state", "obs_shortcut", "random_k", "pca_k", "id_shortcut")


@dataclass
class FittedRefs:
    models: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)


def fit_reference(name: str, sid: str, records: list, sysrec: dict, *, k: int | None = None, truth: dict | None = None,
                  base: CausalStateModel | None = None, cfg: LearnerConfig = DEFAULT_CFG) -> CausalStateModel:
    """Fit one reference on the training records of one system. truth: {"z": {key: (T, k)}, "z_obs": {...}} (synthetic only);
    k: the dimension of RANDOM-k / PCA-k; base: the passive model of NO-EFFECT (default: a FULL-STATE reference fitted here)."""
    if name == "full_state":
        return FullStateModel(cfg).fit(sid, records, sysrec)
    if name in ("true_state", "obs_shortcut"):
        which = "z" if name == "true_state" else "z_obs"
        tb = (truth or {}).get(which)
        if not tb:
            raise ValueError(f"{name} needs truth['{which}']")
        return TruthStateModel(which, cfg).fit_truth(sid, records, sysrec, tb)
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
        if name in ("true_state", "obs_shortcut") and not (truth or {}).get("z" if name == "true_state" else "z_obs"):
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
