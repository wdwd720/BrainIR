"""Surrogate-assisted mechanism search (``surrogate_search``).

A cheap learned model S(subset) -> P(function preserved) steers which keep-only subsets are simulated next; every
candidate the surrogate likes is validated on the true simulator across several parameter seeds before it can be
reported, the surrogate's error is tracked on pre-registered predictions, and the search ends with a discrete
minimality cleanup, essentiality (full-network silencing), alternatives by exclusion search and add-back tests.
Surrogate scores are never reported as simulator results. Full description: research/phase2/methods/surrogate_search.md.

Algorithm
---------
1. **Activity screen and pool.** The intact network is simulated on a few parameter seeds; the candidate pool is the
   union of the candidates active in the analysis window (a silent neuron contributes nothing to the dynamics),
   ordered by a structural relevance score (random-walk reachability from the stimulus x reachability to the
   readout) and capped. The pool is verified by keep-only simulation and expanded (doubling along the relevance
   order) when it fails.
2. **Initial design.** Random "drop" subsets of the pool (adaptive drop fraction targeting a mixed pass/fail rate).
3. **Surrogate.** An ensemble of small "noisy-OR of soft conjunctions" networks over [pool inclusion indicators,
   pool-level aggregates (kept stimulus drive, kept excitatory/inhibitory readout input, kept recurrence, kept E-I
   loop weight, sizes)], trained with bootstrap weights: each unit is a soft sufficient set (a term of a monotone
   DNF, negative weights = inhibitors), the noisy-OR combines alternative implementations, the ensemble spread is the
   epistemic uncertainty. Members with one unit are plain logistic regressions.
4. **Acquisition.** Thompson sampling (greedy elimination from the incumbent under one sampled member), UCB
   elimination, expected improvement over random drop perturbations of the incumbent (EI = P(pass) x size
   reduction), the intersection of passing subsets and the activity-reduced incumbent. Proposals are screened on
   one seed; those that would improve the incumbent are validated on the remaining seeds before acceptance.
5. **Cleanup and evidence.** Chunked then leave-one-out minimality on the incumbent (least-needed first by surrogate
   necessity, every removal validated across seeds), essentiality of every core member by silencing in the FULL
   network, alternatives by exclusion search (keep-only of the pool minus a member, surrogate-guided reduction,
   validation), add-back tests when the core is not robust across seeds, robustness of the final core.
6. **Report.** Inclusion probabilities from validated evidence (core, alternatives) and shrunk surrogate necessity
   for the rest; generic roles from sign, core connectivity and the criterion; the surrogate's error record.

Everything is benchmark-generic: no sizes, ids, names or thresholds refer to any dataset.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from ..discovery.interface import DiscoveryMethod, DiscoveryResult, MethodRegistry
from ..discovery.interventions import keep_only, silence
from ..discovery.problem import DiscoveryProblem
from ..discovery.simulator import BudgetedSimulator, BudgetExhausted, Outcome, SimQuery


# ============================================================================ small numerics
def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.tanh(0.5 * x))


def _finite(x, default=None):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


# ============================================================================ structural relevance (no simulation)
def relevance_scores(problem: DiscoveryProblem, *, hops: int = 4, damping: float = 0.6) -> np.ndarray:
    """Forward random-walk mass from the stimulus times backward mass from the readout (both over synapse counts,
    truncated at ``hops`` steps, geometrically damped); a structural 'on the stimulus -> readout path' score."""
    C = problem.C.tocsr()
    n = problem.n
    out_sum = np.asarray(C.sum(axis=0)).ravel()
    in_sum = np.asarray(C.sum(axis=1)).ravel()
    Pf = (C @ sp.diags(1.0 / np.maximum(out_sum, 1e-12))).tocsr()          # Pf[i, j] = C[i, j] / out_j : forward step
    Pb = (sp.diags(1.0 / np.maximum(in_sum, 1e-12)) @ C).T.tocsr()          # Pb[j, i] = C[i, j] / in_i : backward step
    f = np.zeros(n)
    f[list(problem.stim_positions)] = 1.0 / max(1, len(problem.stim_positions))
    g = problem.readout_mask.astype(np.float64)
    g /= max(1.0, g.sum())
    acc_f = np.zeros(n)
    acc_g = np.zeros(n)
    for step in range(hops):
        f = Pf @ f
        g = Pb @ g
        acc_f += damping ** step * f
        acc_g += damping ** step * g
    return np.sqrt(acc_f * acc_g)


def weighted_degree(problem: DiscoveryProblem) -> np.ndarray:
    C = problem.C
    return np.asarray(C.sum(axis=0)).ravel() + np.asarray(C.sum(axis=1)).ravel()


# ============================================================================ pool features
@dataclass
class _AggState:
    lin: np.ndarray
    Qz: np.ndarray
    Qeiz: np.ndarray
    quad: float
    quad_ei: float
    a: np.ndarray


class _PoolFeatures:
    """Features of a kept subset z in {0,1}^K: the K indicators plus 8 pool-level aggregates in [0, 1]:
    kept fraction, kept stimulus drive, kept excitatory / inhibitory input to the readout, kept excitatory / inhibitory
    fraction, log kept recurrence (z'Qz), log kept E<->I loop weight. Supports O(|S|) evaluation of all single-node
    removals from a subset (used by the acquisition's greedy elimination)."""

    N_AGG = 8

    def __init__(self, problem: DiscoveryProblem, pool: np.ndarray):
        self.pool = np.asarray(pool, dtype=np.int64)
        K = len(self.pool)
        self.K = K
        C = problem.C.tocsr()
        Cd = C[self.pool][:, self.pool].toarray().astype(np.float64)          # post x pre within the pool
        signs = problem.signs[self.pool]
        self.exc = signs > 0
        self.inh = signs < 0
        stim = list(problem.stim_positions)
        self.drive = np.asarray(C[self.pool][:, stim].sum(axis=1)).ravel()
        self.ro = np.asarray(C[problem.readout_positions][:, self.pool].sum(axis=0)).ravel()

        def nrm(v):
            s = v.sum()
            return v / s if s > 0 else v

        self.lin = np.stack([np.full(K, 1.0 / K), nrm(self.drive), nrm(self.ro * self.exc), nrm(self.ro * self.inh),
                             self.exc / K, self.inh / K], axis=1)
        Q = 0.5 * (Cd + Cd.T)
        ei = (self.exc[:, None] & self.inh[None, :]) | (self.inh[:, None] & self.exc[None, :])
        Cei = Cd * ei
        Qei = 0.5 * (Cei + Cei.T)
        self.Q, self.Qei = Q, Qei
        self.dQ, self.dQei = np.diag(Q).copy(), np.diag(Qei).copy()
        self.nrec = max(float(np.log1p(Q.sum())), 1.0)
        self.nei = max(float(np.log1p(Qei.sum())), 1.0)
        self.n_features = K + self.N_AGG

    def aggregates(self, Z: np.ndarray) -> np.ndarray:
        Z = np.asarray(Z, dtype=np.float64)
        lin = Z @ self.lin
        rec = np.log1p(np.maximum(np.einsum("nk,nk->n", Z @ self.Q, Z), 0.0)) / self.nrec
        ei = np.log1p(np.maximum(np.einsum("nk,nk->n", Z @ self.Qei, Z), 0.0)) / self.nei
        return np.column_stack([lin, rec, ei])

    def features(self, Z: np.ndarray) -> np.ndarray:
        Z = np.asarray(Z, dtype=np.float64)
        if Z.ndim == 1:
            Z = Z[None, :]
        return np.hstack([Z, self.aggregates(Z)])

    # incremental single-removal evaluation
    def state(self, z: np.ndarray) -> _AggState:
        zf = z.astype(np.float64)
        Qz = self.Q @ zf
        Qeiz = self.Qei @ zf
        st = _AggState(lin=zf @ self.lin, Qz=Qz, Qeiz=Qeiz, quad=float(zf @ Qz), quad_ei=float(zf @ Qeiz), a=None)
        st.a = self._agg(st.lin, st.quad, st.quad_ei)
        return st

    def _agg(self, lin, quad, quad_ei):
        return np.concatenate([np.atleast_1d(lin), [np.log1p(max(quad, 0.0)) / self.nrec, np.log1p(max(quad_ei, 0.0)) / self.nei]])

    def delta_remove(self, st: _AggState, S: np.ndarray) -> np.ndarray:
        """Change of the aggregate vector when each node of S (positions in the pool) is removed from the current subset."""
        lin_new = st.lin[None, :] - self.lin[S]
        quad_new = np.maximum(st.quad - 2.0 * st.Qz[S] + self.dQ[S], 0.0)
        ei_new = np.maximum(st.quad_ei - 2.0 * st.Qeiz[S] + self.dQei[S], 0.0)
        a_new = np.column_stack([lin_new, np.log1p(quad_new) / self.nrec, np.log1p(ei_new) / self.nei])
        return a_new - st.a[None, :]

    def apply_remove(self, st: _AggState, i: int) -> None:
        st.quad = max(st.quad - 2.0 * st.Qz[i] + self.dQ[i], 0.0)
        st.quad_ei = max(st.quad_ei - 2.0 * st.Qeiz[i] + self.dQei[i], 0.0)
        st.Qz = st.Qz - self.Q[:, i]
        st.Qeiz = st.Qeiz - self.Qei[:, i]
        st.lin = st.lin - self.lin[i]
        st.a = self._agg(st.lin, st.quad, st.quad_ei)


# ============================================================================ the surrogate
class _DnfEnsemble:
    """Ensemble of R "noisy-OR of soft conjunctions" networks: P(pass | x) = 1 - prod_m (1 - sigmoid(w_m . x + b_m)).

    Member r uses 1 + (r mod M) units, so the ensemble mixes plain logistic regressions (1 unit) with multi-term models;
    members differ by initialisation and Poisson bootstrap weights; ensemble spread = epistemic uncertainty. Trained by
    Adam on the weighted cross-entropy + L2; warm-started between refits. The gradient of the noisy-OR output is
    d loss / d u_m = c (q - y) s_m / q, which is bounded and stable.
    """

    def __init__(self, n_features: int, n_members: int, n_units: int, rng: np.random.Generator, *, l2: float = 1e-3, lr: float = 0.05,
                 l1: float = 0.01, n_indicator: int | None = None, init_bias: np.ndarray | None = None):
        self.F, self.R, self.M = int(n_features), int(n_members), int(n_units)
        self.rng = rng
        self.W = rng.normal(0.0, 0.05, size=(self.F, self.R, self.M))
        if init_bias is not None:   # optional prior: shifts the initial weights (fades as data accrue; L1 keeps it honest)
            self.W += np.asarray(init_bias, dtype=np.float64)[:, None, None]
        self.b = np.full((self.R, self.M), -2.0)
        units = 1 + (np.arange(self.R) % self.M)
        self.mask = (np.arange(self.M)[None, :] < units[:, None]).astype(np.float64)
        self.l2, self.lr, self.l1 = float(l2), float(lr), float(l1)
        self.n_indicator = self.F if n_indicator is None else int(n_indicator)
        """L1 (proximal soft-threshold) acts on the first n_indicator features = per-neuron inclusion indicators."""
        self._m = [np.zeros_like(self.W), np.zeros_like(self.W), np.zeros_like(self.b), np.zeros_like(self.b), 0]
        self.boot = np.zeros((0, self.R))
        self.n_fits = 0
        self.last_loss: float | None = None

    # ------------------------------------------------------------------ forward
    @staticmethod
    def _q_from_units(U: np.ndarray, mask: np.ndarray) -> np.ndarray:
        L1 = -np.logaddexp(0.0, U) * mask            # log(1 - s_m); inactive units contribute 0
        q = -np.expm1(L1.sum(-1))                    # 1 - prod (1 - s_m)
        return np.clip(q, 1e-9, 1.0 - 1e-9)

    def _units(self, X: np.ndarray) -> np.ndarray:
        return np.tensordot(X, self.W, axes=(1, 0)) + self.b

    def predict_members(self, X: np.ndarray) -> np.ndarray:
        return self._q_from_units(self._units(np.asarray(X, dtype=np.float64)), self.mask)

    def predict(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        P = self.predict_members(X)
        return P.mean(axis=1), P.std(axis=1)

    # ------------------------------------------------------------------ training
    def _extend_boot(self, n: int) -> None:
        add = n - len(self.boot)
        if add > 0:
            self.boot = np.vstack([self.boot, self.rng.poisson(1.0, size=(add, self.R)).astype(np.float64)])

    def fit(self, X: np.ndarray, y: np.ndarray, w: np.ndarray, steps: int) -> float:
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        w = np.asarray(w, dtype=np.float64)
        n = len(y)
        self._extend_boot(n)
        c = w[:, None] * self.boot[:n]
        cw = c / np.maximum(c.sum(axis=0), 1e-9)
        mW, vW, mb, vb, t = self._m
        b1, b2, eps = 0.9, 0.999, 1e-8
        for _ in range(int(steps)):
            t += 1
            U = self._units(X)
            S = _sigmoid(U) * self.mask
            q = self._q_from_units(U, self.mask)
            g = cw * (q - y[:, None]) / q
            dU = g[:, :, None] * S
            gW = np.tensordot(X, dU, axes=(0, 0)) + 2.0 * self.l2 * self.W
            gb = dU.sum(axis=0)
            mW = b1 * mW + (1 - b1) * gW
            vW = b2 * vW + (1 - b2) * gW * gW
            mb = b1 * mb + (1 - b1) * gb
            vb = b2 * vb + (1 - b2) * gb * gb
            self.W -= self.lr * (mW / (1 - b1 ** t)) / (np.sqrt(vW / (1 - b2 ** t)) + eps)
            self.b -= self.lr * (mb / (1 - b1 ** t)) / (np.sqrt(vb / (1 - b2 ** t)) + eps)
            if self.l1 > 0:  # proximal step: sparse indicator weights (a conjunction names few members)
                k = self.n_indicator
                thr = self.lr * self.l1
                self.W[:k] = np.sign(self.W[:k]) * np.maximum(np.abs(self.W[:k]) - thr, 0.0)
        self._m = [mW, vW, mb, vb, t]
        q = self.predict_members(X)
        ll = -(y[:, None] * np.log(q) + (1 - y[:, None]) * np.log1p(-q))
        self.last_loss = float((cw * ll).sum(axis=0).mean())
        self.n_fits += 1
        return self.last_loss

    def oob_brier(self, X: np.ndarray, y: np.ndarray, w: np.ndarray) -> float | None:
        n = len(y)
        if n == 0 or len(self.boot) < n:
            return None
        P = self.predict_members(X)
        oob = (self.boot[:n] == 0) * np.asarray(w, dtype=np.float64)[:, None]
        if oob.sum() <= 0:
            return None
        return float((((P - np.asarray(y)[:, None]) ** 2) * oob).sum() / oob.sum())

    # ------------------------------------------------------------------ set-level queries used by the acquisition
    def eliminate(self, feat: _PoolFeatures, z0: np.ndarray, *, members: np.ndarray, mode: str, tau: float, kappa: float = 1.0,
                  keep_mask: np.ndarray | None = None, min_size: int = 1) -> tuple[np.ndarray, list[int]]:
        """Greedy backward elimination under the surrogate: repeatedly remove the node whose removal keeps the acquisition
        value (Thompson: one member's P(pass); UCB: mean + kappa std over ``members``) highest, while it stays >= tau."""
        W = self.W[:, members, :]
        b = self.b[members]
        mask = self.mask[members]
        K = feat.K
        Wz, Wa = W[:K], W[K:]
        z = z0.copy()
        st = feat.state(z)
        u = np.tensordot(z.astype(np.float64), Wz, axes=(0, 0)) + np.tensordot(st.a, Wa, axes=(0, 0)) + b
        removed: list[int] = []
        forbid = np.zeros(K, dtype=bool) if keep_mask is None else keep_mask
        while int(z.sum()) > min_size:
            S = np.flatnonzero(z & ~forbid)
            if len(S) == 0:
                break
            da = feat.delta_remove(st, S)
            u_new = u[None] - Wz[S] + np.tensordot(da, Wa, axes=(1, 0))
            q_new = self._q_from_units(u_new, mask)
            val = q_new[:, 0] if mode == "thompson" else q_new.mean(axis=1) + kappa * q_new.std(axis=1)
            j = int(np.argmax(val))
            if val[j] < tau:
                break
            i = int(S[j])
            z[i] = False
            u = u_new[j]
            feat.apply_remove(st, i)
            removed.append(i)
        return z, removed

    def necessity(self, feat: _PoolFeatures, z: np.ndarray) -> tuple[np.ndarray, float, np.ndarray]:
        """Surrogate necessity of every kept node: mean over members of P(pass | z) - P(pass | z without the node)."""
        K = feat.K
        Wz, Wa = self.W[:K], self.W[K:]
        st = feat.state(z)
        u = np.tensordot(z.astype(np.float64), Wz, axes=(0, 0)) + np.tensordot(st.a, Wa, axes=(0, 0)) + self.b
        q0 = self._q_from_units(u, self.mask)
        S = np.flatnonzero(z)
        nec = np.zeros(K)
        sd = np.zeros(K)
        if len(S):
            da = feat.delta_remove(st, S)
            u_new = u[None] - Wz[S] + np.tensordot(da, Wa, axes=(1, 0))
            q_new = self._q_from_units(u_new, self.mask)
            d = q0[None, :] - q_new
            nec[S] = d.mean(axis=1)
            sd[S] = d.std(axis=1)
        return nec, float(q0.mean()), sd


# ============================================================================ bookkeeping
@dataclass
class _SetRecord:
    z: np.ndarray
    outs: dict[int, Outcome] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)

    @property
    def n(self) -> int:
        return len(self.outs)

    @property
    def size(self) -> int:
        return int(self.z.sum())

    def pass_fraction(self) -> float:
        return float(np.mean([o.passed for o in self.outs.values()])) if self.outs else float("nan")

    def mean_score(self) -> float:
        return float(np.mean([o.score for o in self.outs.values()])) if self.outs else float("nan")

    def passed_any(self) -> bool:
        return any(o.passed for o in self.outs.values())


class _SurrogateTracker:
    """Pre-registered surrogate predictions vs simulator outcomes (only real simulations, never pseudo-labels)."""

    def __init__(self):
        self.pred: list[float] = []
        self.actual: list[float] = []
        self.tag: list[str] = []

    def add(self, pred: float, actual: bool, tag: str) -> None:
        self.pred.append(float(pred))
        self.actual.append(1.0 if actual else 0.0)
        self.tag.append(tag)

    def summary(self) -> dict:
        if not self.pred:
            return {"n": 0}
        p = np.clip(np.array(self.pred), 1e-6, 1 - 1e-6)
        a = np.array(self.actual)
        out = {"n": int(len(p)), "brier": float(np.mean((p - a) ** 2)), "log_loss": float(-np.mean(a * np.log(p) + (1 - a) * np.log1p(-p))),
               "accuracy": float(np.mean((p >= 0.5) == (a >= 0.5))), "optimism": float(np.mean(p) - np.mean(a)),
               "base_rate": float(np.mean(a)), "brier_of_base_rate": float(np.mean((np.mean(a) - a) ** 2))}
        bins = np.minimum((p * 5).astype(int), 4)
        out["calibration"] = [{"bin": f"[{k / 5:.1f},{(k + 1) / 5:.1f})", "n": int((bins == k).sum()), "pred_mean": float(p[bins == k].mean()),
                               "actual_rate": float(a[bins == k].mean())} for k in range(5) if (bins == k).any()]
        tags = sorted(set(self.tag))
        t = np.array(self.tag)
        out["by_tag"] = {g: {"n": int((t == g).sum()), "brier": float(np.mean((p[t == g] - a[t == g]) ** 2)), "pass_rate": float(a[t == g].mean()),
                             "pred_mean": float(p[t == g].mean())} for g in tags}
        return out


# ============================================================================ the method
@MethodRegistry.register
class SurrogateSearch(DiscoveryMethod):
    name = "surrogate_search"
    version = "1.0"
    default_config = {
        "replicates": 3,            # validation seeds (screening uses the first)
        "n_intact": 3,              # intact-network seeds for the activity screen (<= replicates)
        "pool_cap": 600,            # first-attempt pool size; exceeded only when the capped pool fails the keep-only check
        "batch": None,              # proposals per round (None: 3..8 from the budget)
        "n_init": 8,                # random drop designs before the surrogate is first fitted
        "ensemble_size": 12, "n_units": 3, "fit_steps": 400, "refit_steps": 120, "l2": 1e-3, "l1": 0.01, "lr": 0.05,
        "tau": 0.5,                 # elimination continues while the acquisition value stays >= tau
        "kappa": 1.0,               # UCB exploration weight
        "patience": 10,             # search rounds without improvement before the cleanup starts
        "pseudo_weight": 0.5,       # weight of activity-reduced pseudo-labels (never reported as results)
        "one_by_one_below": 12,     # cleanup: chunked removal above this size, leave-one-out at or below
        "max_alt_calls": 30,        # exclusion search budget per core member
        "alt_members_max": 6,       # at most this many core members get an exclusion search
        "extra_essential_max": 8,   # non-core pool candidates screened for full-network essentiality
        "robust_check": True,       # widened-parameter robustness of the final core (2 calls)
        "t_end": None,              # optional shorter horizon for every simulation
        "prior": None,              # optional {position: prior inclusion probability}; absent = uniform (never required)
        "prior_strength": 1.0,      # scale of the prior's influence (0 disables it)
    }

    # ------------------------------------------------------------------ orchestration
    def discover(self, problem: DiscoveryProblem, sim: BudgetedSimulator, *, seed: int, config: dict | None = None) -> DiscoveryResult:
        cfg = {**self.default_config, **(config or {})}
        t0 = time.time()
        self.problem, self.sim, self.cfg = problem, sim, cfg
        self.rng = np.random.default_rng(int(seed))
        self.phash = problem.network_hash()
        self.crit = dict(problem.criterion_spec)
        self.crit_type = str(problem.criterion_spec.get("type", "rhythm"))
        self.t_end = cfg.get("t_end")
        n_val = max(1, int(cfg["replicates"]))
        self.seeds = [int(seed) * 1000 + i for i in range(n_val)]
        self.n_val = n_val
        self.screen_seed = self.seeds[0]
        budget = int(sim.max_calls)
        self.batch = int(cfg["batch"]) if cfg.get("batch") else int(max(3, min(8, budget // 120)))
        self.trace: dict = {"phases": {}, "budget_exhausted": False, "stopped_because": None}
        self.tracker = _SurrogateTracker()
        self.rec: dict[bytes, _SetRecord] = {}
        self.pseudo: list[tuple[np.ndarray, float]] = []
        self.ens: _DnfEnsemble | None = None
        self.essential: dict[int, bool | None] = {}
        self.alt_keys: list[bytes] = []
        self.removed_in_cleanup: list[int] = []
        self.needed: dict[int, dict] = {}
        self.addback: list[int] = []
        self.no_alt_in_pool: list[int] = []
        self.extra_essential: list[int] = []
        self.reselected: dict | None = None
        self.pool_check_trace: list = []
        self.intact_outs: list[Outcome] = []
        self.best_key: bytes | None = None
        self.size_trajectory: list[int] = []
        self.prop_stats: dict[str, list[int]] = {}
        self.drop_frac = 0.3
        self.fid_robust = None
        self.prior = self._load_prior(cfg.get("prior"))
        self.prior_strength = float(cfg.get("prior_strength") or 0.0) if self.prior else 0.0
        try:
            self._phase_intact_and_pool()
            if self.feat.K > 0:
                self._phase_design()
                self._phase_search()
                self._phase_cleanup()
                self._phase_essential()
                self._phase_alternatives()
                self._phase_extra_essential()
                self._phase_addback_and_fidelity()
        except BudgetExhausted:
            self.trace["budget_exhausted"] = True
        return self._result(time.time() - t0)

    # ------------------------------------------------------------------ optional prior (cross-network transfer convention)
    @staticmethod
    def _load_prior(pr) -> dict[int, float] | None:
        """{position: p in [0, 1]} (keys may be strings); None or empty = uniform."""
        if not pr or not isinstance(pr, dict):
            return None
        out: dict[int, float] = {}
        for k, v in pr.items():
            try:
                out[int(k)] = float(np.clip(float(v), 0.0, 1.0))
            except (TypeError, ValueError):
                continue
        return out or None

    def _prior_of(self, pos: int) -> float:
        return 0.5 if self.prior is None else self.prior.get(int(pos), 0.5)

    # ------------------------------------------------------------------ simulator access (budget-honest)
    def _calls(self) -> int:
        return int(self.sim.calls)

    def _run(self, queries: list[SimQuery]) -> list[Outcome | None]:
        """Run at most ``sim.remaining`` new simulations (cache hits are free); None for queries that could not be run."""
        sim = self.sim
        seen: set[str] = set()
        runnable = []
        n_new = 0
        for q in queries:
            k = q.key(self.phash, self.crit)
            new = k not in sim.cache and k not in seen
            if new:
                if n_new + 1 > sim.remaining:
                    runnable.append(False)
                    continue
                n_new += 1
                seen.add(k)
            runnable.append(True)
        todo = [q for q, r in zip(queries, runnable) if r]
        if not todo:
            return [None] * len(queries)
        outs = iter(sim.run_many(todo))
        return [next(outs) if r else None for r in runnable]

    def _q(self, iv, s: int, **kw) -> SimQuery:
        return SimQuery(iv, int(s), t_end=self.t_end, **kw)

    def _keep_iv(self, z: np.ndarray):
        return keep_only(self.problem, [int(p) for p in self.feat.pool[z]])

    @staticmethod
    def _key(z: np.ndarray) -> bytes:
        return np.packbits(z.astype(bool)).tobytes()

    def _record(self, z: np.ndarray, s: int, out: Outcome, tag: str) -> _SetRecord:
        k = self._key(z)
        r = self.rec.get(k)
        if r is None:
            r = self.rec[k] = _SetRecord(z=z.astype(bool).copy())
        r.outs[int(s)] = out
        r.tags.add(tag)
        if out.passed:  # activity-reduced pseudo-label: silent kept neurons do not shape the dynamics
            act = np.isin(self.feat.pool, out.active_positions)
            z2 = z & act
            if z2.sum() < z.sum() and z2.sum() > 0 and self._key(z2) not in self.rec:
                self.pseudo.append((z2.copy(), float(self.cfg["pseudo_weight"])))
        return r

    def _simulate_sets(self, zs: list[np.ndarray], seeds: list[int], tag: str, *, preregister: bool = True) -> list[list[Outcome | None]]:
        """Simulate keep-only of every subset on every seed (budget-trimmed); records outcomes and surrogate error."""
        pairs = [(i, s) for i in range(len(zs)) for s in seeds]
        queries = [self._q(self._keep_iv(zs[i]), s) for i, s in pairs]
        preds = None
        if preregister and self.ens is not None and zs:
            preds, _ = self.ens.predict(self.feat.features(np.array(zs)))
        outs = self._run(queries)
        res: list[list[Outcome | None]] = [[None] * len(seeds) for _ in zs]
        for (i, s), o in zip(pairs, outs):
            if o is None:
                continue
            if preds is not None and not o.cached:
                self.tracker.add(float(preds[i]), o.passed, tag)
            self._record(zs[i], s, o, tag)
            res[i][seeds.index(s)] = o
        return res

    # ------------------------------------------------------------------ helpers on records
    def _validated(self, r: _SetRecord) -> bool:
        return r.n >= min(self.n_val, 2) and r.pass_fraction() >= 0.5

    def _best(self) -> _SetRecord:
        return self.rec[self.best_key]

    def _update_best(self) -> bool:
        cands = [r for r in self.rec.values() if self._validated(r)]
        if not cands:
            return False
        cur = self.rec.get(self.best_key) if self.best_key is not None else None
        pick = min(cands, key=lambda r: (r.size, -r.pass_fraction(), -r.n, -r.mean_score(), self._key(r.z)))
        if cur is None or pick.size < cur.size or (pick.size == cur.size and (pick.pass_fraction(), pick.n, pick.mean_score()) >
                                                   (cur.pass_fraction(), cur.n, cur.mean_score())):
            improved = cur is None or pick.size < cur.size
            self.best_key = self._key(pick.z)
            return improved
        return False

    def _validate(self, zs: list[np.ndarray], tag: str) -> None:
        """Run the remaining validation seeds for subsets that passed the screen."""
        if not zs:
            return
        rest = [s for s in self.seeds if s != self.screen_seed]
        if rest:
            self._simulate_sets(zs, rest, tag)

    # ------------------------------------------------------------------ phase A: intact activity screen + pool
    def _phase_intact_and_pool(self) -> None:
        problem, cfg = self.problem, self.cfg
        c0 = self._calls()
        n_int = max(1, min(int(cfg["n_intact"]), self.n_val))
        outs = self._run([self._q(None, s) for s in self.seeds[:n_int]])
        self.intact_outs = [o for o in outs if o is not None]
        cand = problem.candidate_positions()
        cand_set = set(int(p) for p in cand)
        active: set[int] = set()
        for o in self.intact_outs:
            active |= set(int(p) for p in o.active_positions) & cand_set
        rel = relevance_scores(problem)
        deg = weighted_degree(problem)
        if self.prior_strength > 0:   # prior first (ties by structure) when one is given
            key = lambda p: (-round(self._prior_of(p), 6), -rel[p], -deg[p], p)  # noqa: E731
        else:
            key = lambda p: (-rel[p], -deg[p], p)  # noqa: E731
        active_sorted = sorted(active, key=key)
        inactive_sorted = sorted(cand_set - active, key=key)
        ordered = active_sorted + inactive_sorted
        cap = max(1, min(int(cfg["pool_cap"]), len(ordered)))
        self.trace["phases"]["intact"] = self._calls() - c0
        self.trace["intact"] = {"n_seeds": len(self.intact_outs),
                                "pass_fraction": float(np.mean([o.passed for o in self.intact_outs])) if self.intact_outs else None,
                                "n_active_candidates": len(active), "n_candidates": len(cand_set)}
        c1 = self._calls()
        n_act, n_all = len(active_sorted), len(ordered)
        size = min(max(n_act, 1), cap, n_all)
        check_seeds = self.seeds[:min(2, self.n_val)]
        pool = None
        best_pool, best_pf = None, -1.0
        while True:
            P = np.array(ordered[:size], dtype=np.int64)
            outs = self._run([self._q(keep_only(problem, [int(p) for p in P]), s) for s in check_seeds])
            got = [o for o in outs if o is not None]
            pf = float(np.mean([o.passed for o in got])) if got else float("nan")
            self.pool_check_trace.append({"size": int(size), "pass_fraction": pf, "n_seeds": len(got)})
            if got and pf > best_pf:
                best_pool, best_pf = P, pf
            if (got and pf >= 0.5) or size >= n_all or not got:
                pool = P if (got and pf >= 0.5) else (best_pool if best_pool is not None else P)
                break
            # pool_cap is only the first attempt: a failing pool grows to the whole active set, then doubles through the
            # inactive candidates up to all of them (= the intact network), so a passing pool is never given up on
            size = n_act if size < n_act else min(n_all, 2 * size)
        self.trace["phases"]["pool"] = self._calls() - c1
        pool = np.array(sorted(int(p) for p in pool), dtype=np.int64)
        self.feat = _PoolFeatures(problem, pool)
        self.pool_index = {int(p): i for i, p in enumerate(pool)}
        self.pool_rel = rel[pool]
        self.prior_pool = np.array([self._prior_of(int(p)) for p in pool]) if self.prior_strength > 0 else np.full(len(pool), 0.5)
        self.trace["prior"] = None if self.prior is None else {"n_entries": len(self.prior), "n_in_pool": int(sum(int(p) in self.prior for p in pool)),
                                                                 "strength": self.prior_strength}
        self.trace["pool"] = {"size": int(len(pool)), "checks": self.pool_check_trace, "cap": int(cap)}
        # register the pool checks as records
        zP = np.ones(len(pool), dtype=bool)
        for s, o in zip(check_seeds, self._run([self._q(keep_only(problem, [int(p) for p in pool]), s) for s in check_seeds])):
            if o is not None:
                self._record(zP, s, o, "pool")
        self._update_best()

    # ------------------------------------------------------------------ phase B: initial random drop designs
    def _random_drop(self, z: np.ndarray, frac: float) -> np.ndarray:
        S = np.flatnonzero(z)
        if len(S) <= 1:
            return z.copy()
        w = np.ones(len(S))
        if self.prior_strength > 0:   # nodes with a high prior are dropped less often (same expected drop fraction)
            w = 1.0 - self.prior_strength * (self.prior_pool[S] - 0.5)
            w = np.clip(w, 0.05, None)
            w = w / w.mean()
        m = self.rng.random(len(S)) < frac * w
        if not m.any():
            m[self.rng.integers(len(S))] = True
        if m.all():
            m[self.rng.integers(len(S))] = False
        out = z.copy()
        out[S[m]] = False
        return out

    def _phase_design(self) -> None:
        if self.best_key is None:
            return
        c0 = self._calls()
        z0 = self._best().z
        zs, seen = [], set(self.rec)
        for k in range(int(self.cfg["n_init"])):
            frac = 0.15 + 0.5 * (k / max(1, int(self.cfg["n_init"]) - 1))
            z = self._random_drop(z0, frac)
            key = self._key(z)
            if key in seen or z.sum() == 0:
                continue
            seen.add(key)
            zs.append(z)
        if not zs:
            return
        res = self._simulate_sets(zs, [self.screen_seed], "design")
        passed = [z for z, r in zip(zs, res) if r[0] is not None and r[0].passed and z.sum() < z0.sum()]
        self._validate(passed, "design_validate")
        self._update_best()
        self.trace["phases"]["design"] = self._calls() - c0

    # ------------------------------------------------------------------ surrogate fitting
    def _training_data(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        Z, y, w = [], [], []
        for r in self.rec.values():
            for o in r.outs.values():
                Z.append(r.z)
                y.append(1.0 if o.passed else 0.0)
                w.append(1.0)
        for z, wt in self.pseudo:
            Z.append(z)
            y.append(1.0)
            w.append(wt)
        return np.array(Z, dtype=np.float64), np.array(y), np.array(w)

    def _fit(self) -> bool:
        Z, y, w = self._training_data()
        if len(y) < 4 or (y[w >= 1.0] == 1).all() or (y[w >= 1.0] == 0).all():
            return False
        X = self.feat.features(Z)
        if self.ens is None:
            init_bias = None
            if self.prior_strength > 0:   # prior as the surrogate's starting point: centred logit of the prior on the indicators
                lg = np.log(np.clip(self.prior_pool, 0.02, 0.98) / (1 - np.clip(self.prior_pool, 0.02, 0.98)))
                init_bias = np.zeros(self.feat.n_features)
                init_bias[: self.feat.K] = 0.5 * self.prior_strength * (lg - lg.mean())
            self.ens = _DnfEnsemble(self.feat.n_features, int(self.cfg["ensemble_size"]), int(self.cfg["n_units"]), self.rng,
                                    l2=float(self.cfg["l2"]), lr=float(self.cfg["lr"]), l1=float(self.cfg["l1"]), n_indicator=self.feat.K,
                                    init_bias=init_bias)
            self.ens.fit(X, y, w, int(self.cfg["fit_steps"]))
        else:
            self.ens.fit(X, y, w, int(self.cfg["refit_steps"]))
        return True

    # ------------------------------------------------------------------ phase C: surrogate-guided search
    def _reserve(self) -> int:
        """Calls kept back for the evidence phases (cleanup, essentiality, alternatives, extra essential screen, fidelity)."""
        k = self._best().size if self.best_key is not None else 0
        cleanup = int(1.7 * min(k, 15)) + 4
        ess = self.n_val * min(k, 8)
        alt = min(30, 8 * min(k, int(self.cfg["alt_members_max"])))
        extra = self.n_val * min(int(self.cfg["extra_essential_max"]), max(0, self.feat.K - k)) + self.n_val * 2
        return cleanup + ess + alt + extra + 3

    def _propose(self, rnd: int) -> list[tuple[np.ndarray, str]]:
        best = self._best().z
        props: list[tuple[np.ndarray, str]] = []
        seen: set[bytes] = set(self.rec)

        def add(z, tag):
            if z is None or z.sum() == 0:
                return
            k = self._key(z)
            if k in seen:
                return
            seen.add(k)
            props.append((z.astype(bool).copy(), tag))

        ens, feat, tau = self.ens, self.feat, float(self.cfg["tau"])
        if ens is not None:
            R = ens.R
            for t_ in (tau, 0.5 * tau):
                r = int(self.rng.integers(R))
                z, _ = ens.eliminate(feat, best, members=np.array([r]), mode="thompson", tau=t_)
                add(z, "thompson")
            if rnd % 3 == 0:
                r = int(self.rng.integers(R))
                z, _ = ens.eliminate(feat, np.ones(feat.K, dtype=bool), members=np.array([r]), mode="thompson", tau=tau)
                add(z, "thompson_pool")
            z, _ = ens.eliminate(feat, best, members=np.arange(R), mode="ucb", tau=tau, kappa=float(self.cfg["kappa"]))
            add(z, "ucb")
            # expected improvement over random drop perturbations of the incumbent
            n_c = 200
            cands = np.array([self._random_drop(best, float(f)) for f in self.rng.uniform(0.05, 0.6, size=n_c)])
            mu, sd = ens.predict(feat.features(cands))
            ei = (mu + 0.5 * sd) * (best.sum() - cands.sum(axis=1))
            for idx in np.argsort(-ei, kind="stable")[:2]:
                if ei[idx] > 0:
                    add(cands[idx], "ei")
        # intersection of all subsets that passed on any seed
        inter = None
        for r in self.rec.values():
            if r.passed_any():
                inter = r.z.copy() if inter is None else (inter & r.z)
        if inter is not None and 0 < inter.sum() < best.sum():
            add(inter, "intersection")
        # activity-reduced incumbent
        o = self._best().outs.get(self.screen_seed)
        if o is not None and o.passed:
            z = best & np.isin(feat.pool, o.active_positions)
            if 0 < z.sum() < best.sum():
                add(z, "active_reduce")
        n_rand = 1 if ens is not None else 3
        for _ in range(n_rand):
            add(self._random_drop(best, self.drop_frac), "random_drop")
        while len(props) < self.batch:
            before = len(props)
            add(self._random_drop(best, float(self.rng.uniform(0.05, 0.7))), "random_drop")
            if len(props) == before:
                break
        return props[: self.batch]

    def _phase_search(self) -> None:
        if self.best_key is None:
            self.trace["stopped_because"] = "no passing pool"
            return
        c0 = self._calls()
        since_improve, rnd = 0, 0
        self.size_trajectory = [self._best().size]
        recent_random: list[bool] = []
        while True:
            if self._best().size <= 1:
                self.trace["stopped_because"] = "incumbent has one member"
                break
            if self.sim.remaining - self.batch <= self._reserve():
                self.trace["stopped_because"] = "budget reserve reached"
                break
            if since_improve >= int(self.cfg["patience"]):
                self.trace["stopped_because"] = "patience exhausted"
                break
            self._fit()
            props = self._propose(rnd)
            if not props:
                self.trace["stopped_because"] = "no untested proposals"
                break
            zs = [z for z, _ in props]
            tags = [t for _, t in props]
            best_size = self._best().size
            res = []
            for z, t in props:  # tag-specific error tracking
                res.append(self._simulate_sets([z], [self.screen_seed], t)[0])
            passed = []
            for z, t, r in zip(zs, tags, res):
                o = r[0]
                ok = o is not None and o.passed
                self.prop_stats.setdefault(t, [0, 0])
                self.prop_stats[t][0] += 1
                self.prop_stats[t][1] += int(ok)
                if t == "random_drop" and o is not None:
                    recent_random.append(ok)
                if ok and z.sum() < best_size:
                    passed.append(z)
            self._validate(passed, "validate")
            improved = self._update_best()
            since_improve = 0 if improved else since_improve + 1
            self.size_trajectory.append(self._best().size)
            if len(recent_random) >= 4:
                rate = float(np.mean(recent_random[-6:]))
                if rate > 0.6:
                    self.drop_frac = min(0.8, self.drop_frac * 1.3)
                elif rate < 0.3:
                    self.drop_frac = max(0.05, self.drop_frac * 0.7)
            rnd += 1
            if self.sim.remaining <= 0:
                self.trace["stopped_because"] = "budget exhausted"
                break
        self.trace["phases"]["search"] = self._calls() - c0
        self.trace["search"] = {"rounds": rnd, "size_trajectory": self.size_trajectory, "final_drop_frac": round(self.drop_frac, 3),
                                "proposals": {t: {"n": v[0], "passed": v[1]} for t, v in sorted(self.prop_stats.items())}}

    # ------------------------------------------------------------------ phase D: minimality cleanup
    def _necessity_order(self, z: np.ndarray) -> list[int]:
        """Kept pool indices ordered least-needed first (surrogate necessity, then structural relevance ascending)."""
        S = np.flatnonzero(z)
        pr = self.prior_pool
        if self.ens is not None:
            nec, _, _ = self.ens.necessity(self.feat, z)
            return [int(i) for i in sorted(S, key=lambda i: (nec[i], pr[i], self.feat.drive[i] + self.feat.ro[i], i))]
        return [int(i) for i in sorted(S, key=lambda i: (pr[i], self.feat.drive[i] + self.feat.ro[i], i))]

    def _try_remove(self, z: np.ndarray, drop: list[int], tag: str) -> tuple[bool, np.ndarray | None]:
        """Screen z minus drop on one seed; if it passes, validate; accept when the pass fraction stays >= 0.5."""
        z2 = z.copy()
        z2[drop] = False
        if z2.sum() == 0:
            return False, None
        r = self._simulate_sets([z2], [self.screen_seed], tag)[0][0]
        if r is None:
            return False, None
        if not r.passed:
            return False, z2
        self._validate([z2], tag + "_validate")
        rec = self.rec[self._key(z2)]
        return (rec.n >= min(self.n_val, 2) and rec.pass_fraction() >= 0.5), z2

    def _phase_cleanup(self) -> None:
        if self.best_key is None:
            return
        c0 = self._calls()
        self._fit()
        z = self._best().z.copy()
        thr = int(self.cfg["one_by_one_below"])
        end_reserve = self.n_val * min(int(z.sum()), 8) + 3
        # chunked phase (ddmin-like along the surrogate's least-needed order)
        while z.sum() > thr and self.sim.remaining > end_reserve + 3:
            order = self._necessity_order(z)
            chunk = order[: max(1, (len(order) - thr) // 2)]
            accepted = False
            while chunk and self.sim.remaining > end_reserve + 3:
                ok, z2 = self._try_remove(z, chunk, "cleanup_chunk")
                if ok:
                    self.removed_in_cleanup.extend(chunk)
                    z = z2
                    accepted = True
                    break
                chunk = chunk[: len(chunk) // 2]
            if not accepted:
                break
        # leave-one-out phase
        order = self._necessity_order(z)
        for i in order:
            if not z[i] or z.sum() <= 1:
                continue
            if self.sim.remaining <= end_reserve:
                break
            ok, z2 = self._try_remove(z, [i], "cleanup_loo")
            p = int(self.feat.pool[i])
            if ok:
                z = z2
                self.removed_in_cleanup.append(i)
                self.needed[p] = {"needed": False, "pf_without": self.rec[self._key(z2)].pass_fraction()}
            elif z2 is not None:
                rec = self.rec.get(self._key(z2))
                self.needed[p] = {"needed": True, "pf_without": rec.pass_fraction() if rec else None, "n_seeds": rec.n if rec else 0}
        self._update_best()
        # the cleaned set is the incumbent if validated (it is: every accepted removal was validated)
        k = self._key(z)
        if k in self.rec and self._validated(self.rec[k]):
            self.best_key = k
        self.trace["phases"]["cleanup"] = self._calls() - c0
        self.trace["cleanup"] = {"removed": [int(self.feat.pool[i]) for i in self.removed_in_cleanup], "final_size": int(self._best().size)}

    # ------------------------------------------------------------------ phase E: essentiality in the full network
    def _phase_essential(self) -> None:
        if self.best_key is None:
            return
        c0 = self._calls()
        core = [int(p) for p in self.feat.pool[self._best().z]]
        for p in core:
            if self.sim.remaining < self.n_val:
                break
            outs = self._run([self._q(silence([p]), s) for s in self.seeds])
            got = [o for o in outs if o is not None]
            if len(got) >= min(self.n_val, 2):
                self.essential[p] = bool(np.mean([o.passed for o in got]) < 0.5)
        self.trace["phases"]["essential"] = self._calls() - c0

    # ------------------------------------------------------------------ phase F: alternatives by exclusion search
    def _minimize_excluding(self, i: int, cap: int) -> np.ndarray | None:
        """Find a small validated sufficient set that excludes pool index ``i`` within ``cap`` calls: start from the smallest
        passing set without i, jump to the intersection of passing sets without i and to surrogate proposals, then
        ddmin-like chunk removal (surrogate order, random order on failure) and leave-one-out. None when not validated."""
        calls0 = self._calls()
        feat, ens, tau = self.feat, self.ens, float(self.cfg["tau"])
        passing = [r for r in self.rec.values() if r.passed_any() and not r.z[i]]
        if not passing:
            return None
        z = min(passing, key=lambda r: (r.size, self._key(r.z))).z.copy()
        inter = None
        for r in passing:
            inter = r.z.copy() if inter is None else (inter & r.z)

        def left() -> bool:
            return self._calls() - calls0 < cap and self.sim.remaining > 0

        def jump(zc, tag) -> None:
            nonlocal z
            if zc is None or zc[i] or not (0 < zc.sum() < z.sum()) or not left():
                return
            r = self._simulate_sets([zc], [self.screen_seed], tag)[0][0]
            if r is not None and r.passed:
                z = zc.astype(bool).copy()

        jump(inter, "alt_intersection")
        if ens is not None:
            zc, _ = ens.eliminate(feat, z, members=np.arange(ens.R), mode="ucb", tau=tau, kappa=0.0)
            jump(zc, "alt_surrogate")
            for _ in range(2):
                r_ = int(self.rng.integers(ens.R))
                zc, _ = ens.eliminate(feat, z, members=np.array([r_]), mode="thompson", tau=tau)
                jump(zc, "alt_surrogate")
        thr = int(self.cfg["one_by_one_below"])
        # adaptive group removal (approximate binary splitting): drop a chunk of the current size, first in the surrogate's
        # least-needed order, then random re-draws; halve the chunk size after 3 failures at a size, keep it after a success
        chunk_size = max(1, int(z.sum()) // 2)
        attempts = 0
        while z.sum() > thr and chunk_size >= 2 and left():
            order = self._necessity_order(z)
            pick = order[:chunk_size] if attempts == 0 else [int(x) for x in self.rng.permutation(order)[:chunk_size]]
            z2 = z.copy()
            z2[pick] = False
            r = self._simulate_sets([z2], [self.screen_seed], "alt_chunk")[0][0]
            if r is not None and r.passed:
                z = z2
                chunk_size = min(chunk_size, max(1, int(z.sum()) // 2))
                attempts = 0
            else:
                attempts += 1
                if attempts >= 3:
                    chunk_size //= 2
                    attempts = 1
        if z.sum() <= 3 * thr:   # leave-one-out only when the set is small enough to become a reportable alternative
            for j in self._necessity_order(z):
                if not left() or z.sum() <= 1 or not z[j]:
                    continue
                z2 = z.copy()
                z2[j] = False
                r = self._simulate_sets([z2], [self.screen_seed], "alt_loo")[0][0]
                if r is not None and r.passed:
                    z = z2
        if self.sim.remaining > 0 and z.sum() <= 3 * thr:
            self._validate([z], "alt_validate")
        rec = self.rec.get(self._key(z))
        return z if rec is not None and self._validated(rec) else None

    def _alt_size_ok(self, size: int, core_size: int) -> bool:
        return size <= max(2 * core_size, core_size + 3)

    def _phase_alternatives(self) -> None:
        if self.best_key is None:
            return
        c0 = self._calls()
        self._fit()
        best = self._best().z
        core_idx = [int(i) for i in np.flatnonzero(best)]
        # non-essential members first (an essential member has no alternative in the full network), unknown next
        def rank(i: int) -> tuple[int, int]:
            e = self.essential.get(int(self.feat.pool[i]))
            return (0 if e is False else 1 if e is None else 2, i)

        order = sorted(core_idx, key=rank)
        checked = []
        for i in order[: int(self.cfg["alt_members_max"])]:
            p = int(self.feat.pool[i])
            if self.essential.get(p) is True:
                continue
            if self.sim.remaining < 6:
                break
            checked.append(p)
            if not any(r.passed_any() and not r.z[i] for r in self.rec.values()):
                zP = np.ones(self.feat.K, dtype=bool)
                zP[i] = False
                r = self._simulate_sets([zP], [self.screen_seed], "alt_pool_check")[0][0]
                if r is None:
                    break
                if not r.passed:
                    self.no_alt_in_pool.append(p)
                    continue
            start = min((r.size for r in self.rec.values() if r.passed_any() and not r.z[i]), default=self.feat.K)
            cap = int(self.cfg["max_alt_calls"]) + 2 * int(start)                                # larger starts need more splits
            cap = min(cap, max(6, self.sim.remaining - (self.n_val * min(int(self.cfg["extra_essential_max"]), self.feat.K) + 6)))
            z_alt = self._minimize_excluding(i, cap)
            if z_alt is not None:
                k = self._key(z_alt)
                if k != self.best_key and k not in self.alt_keys and self._alt_size_ok(int(z_alt.sum()), int(best.sum())):
                    self.alt_keys.append(k)
        self.trace["phases"]["alternatives"] = self._calls() - c0
        self.trace["alternatives"] = {"checked_members": checked, "no_alternative_in_pool": self.no_alt_in_pool,
                                      "found": [[int(p) for p in self.feat.pool[self.rec[k].z]] for k in self.alt_keys]}

    # ------------------------------------------------------------------ phase F2: essential nodes outside the core, core re-selection
    def _phase_extra_essential(self) -> None:
        """Sufficiency in isolation is not the mechanism in context: screen the most plausible non-core pool nodes by
        full-network silencing; every essential node must belong to the reported core, so the core becomes the smallest
        validated sufficient set containing all essential nodes (an alternative, or the core plus the essential nodes)."""
        if self.best_key is None:
            return
        c0 = self._calls()
        best = self._best()
        m = int(self.cfg["extra_essential_max"])
        alt_members: list[int] = []
        for k in self.alt_keys:
            for i in np.flatnonzero(self.rec[k].z):
                if not best.z[i] and int(i) not in alt_members:
                    alt_members.append(int(i))
        nec = np.zeros(self.feat.K)
        if self.ens is not None:
            for z in sorted([r.z for r in self.rec.values() if self._validated(r)], key=lambda z: int(z.sum()))[:12]:
                n_, _, _ = self.ens.necessity(self.feat, z)
                nec = np.maximum(nec, n_)
        others = sorted([i for i in range(self.feat.K) if not best.z[i] and i not in alt_members],
                        key=lambda i: (-nec[i], -self.prior_pool[i], -self.pool_rel[i], i))
        cands = (alt_members + others)[:m]
        tested = []
        for i in cands:
            p = int(self.feat.pool[i])
            if p in self.essential:
                continue
            if self.sim.remaining < self.n_val:
                break
            outs = self._run([self._q(silence([p]), s) for s in self.seeds])
            got = [o for o in outs if o is not None]
            if len(got) >= min(self.n_val, 2):
                self.essential[p] = bool(np.mean([o.passed for o in got]) < 0.5)
                tested.append(p)
        core_pos = set(int(p) for p in self.feat.pool[best.z])
        ess_pos = {p for p, v in self.essential.items() if v is True}
        extra = sorted(ess_pos - core_pos)
        self.extra_essential = extra
        if extra:
            E_idx = [self.pool_index[p] for p in ess_pos]
            z_union = best.z.copy()
            z_union[[self.pool_index[p] for p in extra]] = True
            cands_r = [r for r in self.rec.values() if self._validated(r) and all(r.z[j] for j in E_idx)]
            new_key = None
            if cands_r:
                pick = min(cands_r, key=lambda r: (r.size, -r.pass_fraction(), -r.n, -r.mean_score(), self._key(r.z)))
                if pick.size <= int(z_union.sum()):
                    new_key = self._key(pick.z)
            if new_key is None and self.sim.remaining >= min(self.n_val, 2):
                self._simulate_sets([z_union], self.seeds, "reselect", preregister=False)
                r = self.rec.get(self._key(z_union))
                if r is not None and self._validated(r):
                    new_key = self._key(z_union)
            if new_key is not None and new_key != self.best_key:
                old = self.best_key
                self.best_key = new_key
                if old not in self.alt_keys:
                    self.alt_keys.insert(0, old)
                self.alt_keys = [k for k in self.alt_keys if k != new_key]
                self.reselected = {"from": sorted(core_pos), "to": [int(p) for p in self.feat.pool[self._best().z]], "essential_outside_core": extra}
                for p in self.feat.pool[self._best().z]:      # essentiality claims for the new members
                    p = int(p)
                    if p in self.essential or self.sim.remaining < self.n_val:
                        continue
                    outs = self._run([self._q(silence([p]), s) for s in self.seeds])
                    got = [o for o in outs if o is not None]
                    if len(got) >= min(self.n_val, 2):
                        self.essential[p] = bool(np.mean([o.passed for o in got]) < 0.5)
        self.trace["phases"]["extra_essential"] = self._calls() - c0
        self.trace["extra_essential"] = {"screened": tested, "essential_outside_core": extra, "reselected": self.reselected}

    # ------------------------------------------------------------------ phase G: add-back tests, final fidelity
    def _phase_addback_and_fidelity(self) -> None:
        if self.best_key is None:
            return
        c0 = self._calls()
        best = self._best()
        # make sure the core has every validation seed
        self._simulate_sets([best.z], self.seeds, "final", preregister=False)
        best = self._best()
        if best.pass_fraction() < 1.0 and self.removed_in_cleanup:
            for i in list(reversed(self.removed_in_cleanup))[:3]:
                if self.sim.remaining < self.n_val:
                    break
                z2 = best.z.copy()
                z2[i] = True
                self._simulate_sets([z2], self.seeds, "addback", preregister=False)
                rec = self.rec.get(self._key(z2))
                if rec is not None and rec.n >= min(self.n_val, 2) and rec.pass_fraction() > best.pass_fraction() and rec.pass_fraction() >= 1.0:
                    self.best_key = self._key(z2)
                    self.addback.append(int(self.feat.pool[i]))
                    best = self._best()
                    break
        self.fid_robust = None
        if self.cfg.get("robust_check") and self.sim.remaining >= 2:
            mc = self.problem.model_cfg
            wide = {"tau_sd": mc.tau_sd * 2, "a_sd": mc.a_sd * 2, "theta_sd": mc.theta_sd * 2, "r_max_sd": mc.r_max_sd * 2}
            outs = self._run([self._q(self._keep_iv(best.z), s, cfg_override=wide) for s in self.seeds[:2]])
            got = [o for o in outs if o is not None]
            if got:
                self.fid_robust = float(np.mean([o.passed for o in got]))
        self.trace["phases"]["addback_fidelity"] = self._calls() - c0

    # ------------------------------------------------------------------ reporting
    def _inclusion(self, core: list[int], alts: list[list[int]]) -> dict[int, float]:
        problem = self.problem
        p: dict[int, float] = {}
        for c in problem.candidate_positions():
            p[int(c)] = 0.01                                        # inactive under the stimulus (activity screen)
        # surrogate necessity over validated passing sets (shrunk by the surrogate's measured error)
        nec = np.zeros(self.feat.K)
        summary = self.tracker.summary()
        rel = 1.0
        if summary.get("n", 0) >= 10 and summary.get("brier") is not None:
            rel = float(np.clip(1.0 - summary["brier"] / max(summary.get("brier_of_base_rate", 0.25), 1e-6), 0.0, 1.0))
        if self.ens is not None:
            sets = [r.z for r in self.rec.values() if self._validated(r)]
            sets = sorted(sets, key=lambda z: int(z.sum()))[:12]
            for z in sets:
                n_, _, _ = self.ens.necessity(self.feat, z)
                nec = np.maximum(nec, n_)
        for i, pos in enumerate(self.feat.pool):
            bump = 1.0 + self.prior_strength * (self.prior_pool[i] - 0.5)          # prior nudges the surrogate part only
            p[int(pos)] = float(np.clip(0.02 + 0.3 * rel * max(nec[i], 0.0) * max(bump, 0.0), 0.02, 0.35))
        alt_members = set(x for a in alts for x in a)
        n_alt = len(alts)
        for pos in alt_members - set(core):
            p[int(pos)] = float(np.clip(0.3 + 0.2 / max(1, n_alt), 0.3, 0.5))
        for pos in core:
            info = self.needed.get(pos, {})
            val = 0.9 if info.get("needed") else 0.6
            if self.essential.get(pos) is True:
                val = max(val, 0.95)
            if pos in self.addback:
                val = 0.5
            if any(pos not in a for a in alts):     # a validated implementation without this member exists
                val = min(val, 0.75)
            p[int(pos)] = val
        return p

    def _roles(self, core: list[int], alts: list[list[int]]) -> tuple[dict[int, tuple[str, float]], list[int], str]:
        problem = self.problem
        crit = self.crit_type
        roles: dict[int, tuple[str, float]] = {}
        if not core:
            return roles, [], None
        core = sorted(core)
        C = problem.C.tocsr()
        sub = C[core][:, core].toarray()                       # post x pre
        A = sp.csr_matrix((sub > 0).T)                         # A[i, j] = edge i -> j
        _, labels = connected_components(A, directed=True, connection="strong")
        comp_size = np.bincount(labels)
        stim = list(problem.stim_positions)
        signs = problem.signs
        drive = np.asarray(C[core][:, stim].sum(axis=1)).ravel()
        ro = np.asarray(C[problem.readout_positions][:, core].sum(axis=0)).ravel()
        ro_total = float(ro.sum())
        loop = []
        n_exc = n_inh = 0
        for k, pos in enumerate(core):
            s = int(signs[pos])
            self_loop = sub[k, k] > 0
            on_cycle = comp_size[labels[k]] > 1 or self_loop
            stim_in = drive[k] > 0
            ro_frac = (ro[k] / ro_total) if ro_total > 0 else 0.0
            in_core = int((sub[k, :] > 0).sum() - int(self_loop))
            out_core = int((sub[:, k] > 0).sum() - int(self_loop))
            if on_cycle:
                loop.append(int(pos))
            if s == 0:
                roles[int(pos)] = ("unknown", 0.5)
                continue
            if s > 0:
                n_exc += 1
                if self_loop and crit in ("persistence", "ramp"):
                    role, q = "state_memory", 0.8
                elif crit == "rhythm" and on_cycle:
                    relay = (not stim_in) and ro_frac < 0.1 and in_core <= 1 and out_core <= 1
                    role, q = ("input_relay", 0.6) if relay else ("recurrent_excitatory_core", 0.7)
                elif ro_frac >= 0.25 or (ro_total > 0 and ro[k] == ro.max()):
                    role, q = "output_driver", 0.7
                elif stim_in:
                    role, q = "input_relay", 0.7
                elif self_loop:
                    role, q = "state_memory", 0.6
                elif on_cycle:
                    role, q = "recurrent_excitatory_core", 0.55
                else:
                    role, q = "input_relay", 0.5
            else:
                n_inh += 1
                if crit == "selectivity":
                    role, q = "lateral_inhibition", 0.7
                elif crit == "rhythm":
                    role, q = ("inhibitory_feedback", 0.75) if on_cycle else (("gain_control", 0.5) if ro[k] > 0 else ("inhibitory_feedback", 0.4))
                elif crit == "activity_band":
                    role, q = "gain_control", 0.75
                elif crit in ("persistence", "ramp"):
                    role, q = ("inhibitory_feedback", 0.5) if on_cycle else ("gain_control", 0.5)
                else:
                    role, q = "unknown", 0.5
            if pos in self.addback:
                role, q = "modulatory_supporting", 0.5
            roles[int(pos)] = (role, q)
        for a in alts:
            for pos in a:
                if int(pos) not in roles:
                    roles[int(pos)] = ("redundant_backup", 0.5)
        parts = [f"{n_exc} excitatory + {n_inh} inhibitory core", "recurrent loop" if loop else "feedforward"]
        if any(sub[k, k] > 0 for k in range(len(core))):
            parts.append("self-excitation")
        n_drivers = int((ro > 0).sum())
        parts.append(f"readout driven by {n_drivers} member(s)")
        parts.append(f"criterion {crit}")
        return roles, sorted(loop), "; ".join(parts)

    def _result(self, wall: float) -> DiscoveryResult:
        have_pool = hasattr(self, "feat") and self.feat.K > 0
        core: list[int] = []
        fid: dict = {}
        if have_pool and self.best_key is not None and self._validated(self._best()):
            best = self._best()
            core = sorted(int(p) for p in self.feat.pool[best.z])
            outs = list(best.outs.values())
            freqs = [o.frequency_hz for o in outs if o.passed and o.frequency_hz is not None]
            fid = {"keep_only_pass_fraction": best.pass_fraction(), "keep_only_score_mean": best.mean_score(), "n_seeds": best.n,
                   "frequency_hz": float(np.median(freqs)) if freqs else None,
                   "n_active_readout": int(np.median([o.n_active_readout for o in outs])) if outs else None,
                   "robust_sd_x2_pass_fraction": getattr(self, "fid_robust", None)}
        alts = [[int(p) for p in self.feat.pool[self.rec[k].z]] for k in self.alt_keys] if have_pool else []
        alts = [sorted(a) for a in alts if sorted(a) != core and self._alt_size_ok(len(a), max(1, len(core)))]
        if have_pool and core:   # necessity within the final core from leave-one-out records (whatever phase produced them)
            zc = self._best().z
            for pos in core:
                z2 = zc.copy()
                z2[self.pool_index[pos]] = False
                r = self.rec.get(self._key(z2))
                if r is not None:
                    self.needed[pos] = {"needed": bool(r.pass_fraction() < 0.5), "pf_without": r.pass_fraction(), "n_seeds": r.n}
                elif pos in self.needed and not self.needed[pos].get("needed"):
                    del self.needed[pos]
        incl = self._inclusion(core, alts) if have_pool else {}
        roles, loop, motif = self._roles(core, alts) if have_pool else ({}, [], None)
        ess = {p: self.essential.get(p) for p in core}
        # dynamics: the intact network's own outcome is the prediction for the benchmark stimulus; keep-only values in fidelity
        ip = [o for o in self.intact_outs if o.passed]
        ifreq = [o.frequency_hz for o in ip if o.frequency_hz is not None]
        pred_f = float(np.median(ifreq)) if ifreq else fid.get("frequency_hz")
        pred_n = int(np.median([o.n_active_readout for o in ip])) if ip else fid.get("n_active_readout")
        surr = self.tracker.summary()
        if self.ens is not None:
            Z, y, w = self._training_data()
            real = w >= 1.0
            surr.update(n_fits=self.ens.n_fits, train_loss=self.ens.last_loss, ensemble_size=self.ens.R, n_units=self.ens.M,
                        n_features=self.feat.n_features, n_training_rows=int(len(y)), n_pseudo_rows=int((~real).sum()),
                        oob_brier=self.ens.oob_brier(self.feat.features(Z[real]), y[real], w[real]) if real.any() else None)
        else:
            surr.update(fitted=False)
        diag = {**self.trace, "surrogate": surr, "n_subsets_simulated": len(self.rec),
                "n_validated_passing": sum(self._validated(r) for r in self.rec.values()),
                "needed_within_core": {int(k): v for k, v in self.needed.items() if k in set(core)}, "addback": list(self.addback),
                "essential_tested": {int(k): v for k, v in self.essential.items()}, "seeds": list(self.seeds), "batch": self.batch,
                "wall_s": round(wall, 1)}
        return DiscoveryResult(core=core, inclusion_probability={int(k): float(v) for k, v in incl.items()}, roles=roles, essential=ess,
                               alternatives=alts, loop=loop, predicted_frequency_hz=pred_f, predicted_n_active_readout=pred_n,
                               predicted_function_preserved=(fid.get("keep_only_pass_fraction", 0.0) >= 0.5) if fid else False, fidelity=fid,
                               budget={**self.sim.report(), "wall_s": round(wall, 1)}, diagnostics=_plain(diag), motif=motif)


def _plain(o):
    """JSON-plain copy (numpy scalars/arrays -> Python)."""
    if isinstance(o, dict):
        return {(int(k) if isinstance(k, (np.integer,)) else k): _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, np.ndarray):
        return [_plain(v) for v in o.tolist()]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o
