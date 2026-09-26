"""Evaluation inputs (benchmarks/causal_state_v1/PROTOCOL.md sections 4-5): the per-system constants, test items, microstate pools and
truth samples the evaluator scores a fitted model on.

These structures are built ORCHESTRATOR-SIDE from the datasets (`brainir_causal.suites`, fork E7) and never contain anything a model
may not see at the moment it is asked: a model receives only `x_hist`, `u_hist`, `u_future` and `events` of an item (the history up
to and INCLUDING the onset sample, never the readout, never the future microstate). Every other field is evaluator-only truth.

Time conventions. For an item with onset sample i0 (the first event's time; the sample at an instantaneous event's time is the PRE-
event state), the history is x[0..i0] inclusive, which the item and its counterfactual twin share. Future arrays start at the onset
sample: row 0 = time 0 = the onset, row j = j samples later. Events are given relative to the onset (time 0). A horizon of h seconds
covers rows 1..round(h / dt).

Horizons are fractions of the system's default duration (PROTOCOL section 4): short 2.5 %, medium 12.5 % (PRIMARY), long 50 %.
Normalisers come from PUBLIC training data only (`make_eval_system`): the POOLED training variance of the readout (all dimensions
share it) computed without finite blow-ups (a trajectory whose max |x| or |y| exceeds 100x the median over the training
trajectories), and the public PCA basis of x (top q = min(10, N_obs) components) used for the residual microstate.
The effect floor is f_s = 0.05 x the pooled training sd of y (PROTOCOL 5.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

HORIZON_FRACTIONS = {"short": 0.025, "medium": 0.125, "long": 0.5}
PRIMARY = "medium"
FLOOR_FRAC = 0.05
ITEM_CAP = 10.0
BLOWUP_FACTOR = 100.0
N_PCS = 10
#: detectability classes of ES = RMS(true effect over the primary window) / floor (PROTOCOL 5.1)
DETECT_CLASSES = (("below", 0.0, 1.0), ("weak", 1.0, 3.0), ("moderate", 3.0, 10.0), ("strong", 10.0, float("inf")))
#: shift types of a test item (PROTOCOL sections 3-4); OOD / robustness items use "ood:<category>" / "robust:<condition>"
SHIFT_TYPES = ("in", "target", "near", "far", "hidden", "ood", "robust", "passive")


@dataclass
class EvalSystem:
    """Per-system constants of the evaluation (all from public training data)."""
    system_id: str
    kind: str                       # "real" | "synthetic"
    dt: float
    t_end_default: float
    n_obs: int
    n_y: int
    n_u: int
    y_sd: float                     # pooled training sd of the readout (the NMSE / effect normaliser)
    pca_mean: np.ndarray            # (n_obs,)
    pca_comps: np.ndarray           # (q, n_obs) public principal components of x (rows orthonormal)
    lineage: str | None = None      # real systems: builds of one reconstruction share a lineage
    compact_limit: int | None = None   # max k for "compact" (max(1, N_obs / 5)); None = not judged (mechanism systems)
    floor_frac: float = FLOOR_FRAC
    meta: dict = field(default_factory=dict)
    pca_sd: np.ndarray | None = None   # (q,) PUBLIC spread of each principal component (x_res drop rule and common scale, PROTOCOL 5.3)

    @property
    def floor(self) -> float:
        """The effect floor f_s in readout units."""
        return float(self.floor_frac * self.y_sd)

    def horizon_s(self, name: str) -> float:
        return float(HORIZON_FRACTIONS[name] * self.t_end_default)

    def horizon_steps(self, name: str, dt: float | None = None) -> int:
        return max(1, int(round(self.horizon_s(name) / float(dt or self.dt))))

    def horizons(self) -> dict[str, float]:
        return {h: self.horizon_s(h) for h in HORIZON_FRACTIONS}


@dataclass
class TestItem:
    """One test item: an intervention trajectory with its counterfactual twin (or a passive window, `y_twin is None`)."""
    __test__ = False                # not a pytest test class (its name starts with "Test")
    item_id: str
    system_id: str
    dt: float
    x_hist: np.ndarray              # (T_h, n_obs) up to and including the onset sample
    u_hist: np.ndarray              # (T_h, n_u)
    u_future: np.ndarray            # (H+1, n_u) from the onset sample on; common to the item and its twin
    events: list[dict]              # the events the MODEL is told, relative to the onset
    y_future: np.ndarray            # (H+1, n_y) true readout under the events
    y_twin: np.ndarray | None = None        # (H+1, n_y) true readout of the twin (no events); None = passive item
    family: str = "obs.nominal"
    shift: str = "in"               # in | target | near | far | hidden | ood:<cat> | robust:<cond> | passive
    magnitude_class: str = "na"     # below | weak | moderate | strong | hi | na
    target_set: tuple[int, ...] = ()
    onset: float = 0.0              # absolute onset time in the source trajectory (s)
    group: str = ""                 # resampling cluster (items sharing a start state / trajectory); default = item_id
    x_future: np.ndarray | None = None      # (H+1, n_obs) true observed microstate under the events (closure, lift)
    x_twin_future: np.ndarray | None = None
    id_key: str | None = None       # intervention identity (ID features / shortcut); default family|targets|magnitude class
    true_events: list[dict] | None = None   # events actually simulated when they differ from `events` (robustness jitter)
    components: dict | None = None  # composition items: {"a": {"events", "y_future"}, "b": {...}} true single-component futures
    z_true: np.ndarray | None = None        # SYNTHETIC truth: the causal state at the onset
    z_obs: np.ndarray | None = None         # SYNTHETIC truth: the observational shortcut state at the onset (trap types)
    dz_true: np.ndarray | None = None       # SYNTHETIC truth: true latent effect of the first (instantaneous) event
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.group:
            self.group = self.item_id
        for name in ("x_hist", "u_hist", "u_future", "y_future", "y_twin", "x_future", "x_twin_future"):
            v = getattr(self, name)
            if v is not None:
                v = np.asarray(v, dtype=np.float64)
                setattr(self, name, v[:, None] if v.ndim == 1 else v)

    @property
    def is_passive(self) -> bool:
        return self.y_twin is None

    @property
    def horizon_rows(self) -> int:
        """Number of future rows after the onset (H)."""
        return int(len(self.y_future) - 1)

    def identity(self) -> str:
        """The intervention identity the ID features and the ID-shortcut reference see."""
        if self.id_key:
            return self.id_key
        return f"{self.family}|{','.join(str(t) for t in sorted(self.target_set))}|{self.magnitude_class}"

    def shift_kind(self) -> str:
        return self.shift.split(":", 1)[0]


@dataclass
class PoolState:
    """One microstate of a pool (PROTOCOL 4, 5.5-5.6): its observed history and the SIMULATED futures from the exact microstate."""
    state_id: str
    x_hist: np.ndarray              # (T_h, n_obs) history up to and including the state's sample
    u_hist: np.ndarray              # (T_h, n_u)
    y_now: np.ndarray               # (n_y,) readout at the state's sample
    traj: str                       # source trajectory (states of one trajectory are never paired)
    draw: str                       # parameter draw: pairs only within one draw (different draws are different parameters)
    futures: dict[str, np.ndarray]  # sequence id -> (H+1, n_y) future readout under that sequence; "none" = no intervention
    x_futures: dict[str, np.ndarray] | None = None   # sequence id -> (H+1, n_obs) future observed microstate (bisimulation)
    z_true: np.ndarray | None = None
    z_obs: np.ndarray | None = None
    equiv_class: str | None = None  # SYNTHETIC: states generated as truth-equivalent share this id
    floor_div: float | None = None  # numerical floor of this state's future divergence (repeat simulation), if measured
    meta: dict = field(default_factory=dict)


@dataclass
class Pool:
    """Every future of every state must be simulated from the exact microstate with the sequence's events and its COMMON future input
    `u_future` (the same input for all states), so that future differences reflect state differences only."""
    system_id: str
    dt: float
    states: list[PoolState]
    sequences: dict[str, dict]      # sequence id -> {"events": [...] (relative to the state's sample), "u_future": (H+1, n_u),
                                    #                 "family": str, "kind": str}; "none" = the no-intervention future
    floor_div: float | None = None  # pool-level numerical floor of future divergence (mean over repeat simulations)
    meta: dict = field(default_factory=dict)


@dataclass
class StateSample:
    """A held-out encoding point with truth (synthetic latent recovery, PROTOCOL 5.16)."""
    sample_id: str
    x_hist: np.ndarray
    u_hist: np.ndarray
    dt: float
    group: str                      # source trajectory
    z_true: np.ndarray
    z_obs: np.ndarray | None = None


# ------------------------------------------------------------------------------------------------------------ normalisers
def blowup_mask(xs: list[np.ndarray], ys: list[np.ndarray], factor: float = BLOWUP_FACTOR) -> np.ndarray:
    """True for trajectories whose max |x| or max |y| exceeds `factor` x the median over the trajectories (finite blow-ups; kept as
    data, excluded from normalisers)."""
    if not ys:
        return np.zeros(0, bool)
    my = np.array([float(np.nanmax(np.abs(y))) if np.size(y) else 0.0 for y in ys])
    mx = np.array([float(np.nanmax(np.abs(x))) if np.size(x) else 0.0 for x in xs])
    bad = ~(np.isfinite(my) & np.isfinite(mx))
    ry = float(np.median(my[~bad])) if (~bad).any() else 0.0
    rx = float(np.median(mx[~bad])) if (~bad).any() else 0.0
    return bad | (my > factor * max(ry, 1e-12)) | (mx > factor * max(rx, 1e-12))


def pooled_y_sd(train_y: list[np.ndarray], train_x: list[np.ndarray] | None = None) -> float:
    """sqrt of the MEAN per-dimension training variance of y (pooled normaliser), without finite blow-ups."""
    xs = train_x if train_x is not None else [np.zeros((1, 1))] * len(train_y)
    keep = [y for y, b in zip(train_y, blowup_mask(xs, train_y)) if not b] or list(train_y)
    Y = np.concatenate([np.asarray(y, np.float64).reshape(len(y), -1) for y in keep], axis=0)
    var = float(Y.var(axis=0).mean()) if Y.size else 0.0
    return float(np.sqrt(max(var, 1e-12)))


def public_pca_full(train_x: list[np.ndarray], q: int = N_PCS, max_rows: int = 200_000, seed: int = 0
                    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(mean, components (q, n_obs), public spread of each component (q,)) of the observed microstate over public training data
    (rows sub-sampled deterministically)."""
    X = np.concatenate([np.asarray(x, np.float64) for x in train_x], axis=0)
    if len(X) > max_rows:
        X = X[np.random.default_rng(seed).choice(len(X), max_rows, replace=False)]
    mu = X.mean(0)
    q = int(min(q, X.shape[1], max(1, len(X) - 1)))
    _, sv, Vt = np.linalg.svd(X - mu, full_matrices=False)
    return mu, Vt[:q], sv[:q] / np.sqrt(len(X))


def public_pca(train_x: list[np.ndarray], q: int = N_PCS, max_rows: int = 200_000, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """(mean, components (q, n_obs)) of the observed microstate over public training data (rows sub-sampled deterministically)."""
    mu, comps, _ = public_pca_full(train_x, q, max_rows, seed)
    return mu, comps


def make_eval_system(system_id: str, kind: str, dt: float, t_end_default: float, train_x: list[np.ndarray],
                     train_y: list[np.ndarray], n_u: int, *, lineage: str | None = None, compact: bool = True,
                     q: int = N_PCS, meta: dict | None = None) -> EvalSystem:
    """Build the per-system constants from PUBLIC training data (x and y of the training trajectories)."""
    keep = [i for i, b in enumerate(blowup_mask(train_x, train_y)) if not b] or list(range(len(train_x)))
    n_obs = int(np.asarray(train_x[0]).shape[1])
    mu, comps, pc_sd = public_pca_full([train_x[i] for i in keep], q=min(q, n_obs))
    return EvalSystem(system_id=system_id, kind=kind, dt=float(dt), t_end_default=float(t_end_default), n_obs=n_obs,
                      n_y=int(np.asarray(train_y[0]).reshape(len(train_y[0]), -1).shape[1]), n_u=int(n_u),
                      y_sd=pooled_y_sd([train_y[i] for i in keep], [train_x[i] for i in keep]), pca_mean=mu, pca_comps=comps,
                      lineage=lineage, compact_limit=(max(1, n_obs // 5) if compact else None), meta=dict(meta or {}),
                      pca_sd=pc_sd)


def detect_class(es: float) -> str:
    for name, lo, hi in DETECT_CLASSES:
        if lo <= es < hi:
            return name
    return "below" if not np.isfinite(es) else "strong"


def check_item(item: TestItem, sysc: EvalSystem) -> list[str]:
    """Shape / convention problems of an item (empty list = fine)."""
    probs = []
    if item.x_hist.shape[1] != sysc.n_obs:
        probs.append(f"x_hist has {item.x_hist.shape[1]} columns, expected {sysc.n_obs}")
    if len(item.u_hist) != len(item.x_hist):
        probs.append("u_hist and x_hist lengths differ")
    if item.y_future.shape[1] != sysc.n_y:
        probs.append(f"y_future has {item.y_future.shape[1]} columns, expected {sysc.n_y}")
    if len(item.u_future) != len(item.y_future):
        probs.append("u_future and y_future lengths differ")
    if item.y_twin is not None and item.y_twin.shape != item.y_future.shape:
        probs.append("y_twin shape differs from y_future")
    for e in item.events:
        if e.get("kind") in ("latent_set", "latent_kick"):
            probs.append("truth events must never reach a model")
    return probs
