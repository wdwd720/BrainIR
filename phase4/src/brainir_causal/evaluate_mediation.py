"""State mediation score and interventional closure (benchmarks/causal_state_v1/PROTOCOL.md sections 5.3-5.4; goal5 sections 13, 31).

Both are CONDITIONAL-PREDICTION tests on the VERDICT test items (roles in / target / near / far / hidden; PROTOCOL 9: OOD and
robustness items never enter a verdict criterion), with readouts in units of the public pooled training sd, cross-fitted in 2 folds,
with per-row errors averaged over N_SEEDS = 20 cross-fitting seeds (fold assignments). Gains: gain(e_null, e_B) = (e_null - e_B) /
max(e_null, 0.01), clipped at -1.

FOLDS (`cell_stratified_folds`; RESOLUTION of "cross-fitted by identity cell"): the folds split ITEMS (an item's rows always stay
together), STRATIFIED by identity cell: the states of every cell are divided between the two folds, so every intervention identity
of the test fold also occurs in the training fold. With whole cells as the fold unit, the identity correction of a test cell must
extrapolate to an identity never seen in training; on review E's layout (cells of one unit x one magnitude class) that made SMS about
0.03 [-0.69, 0.59] for a gross read-in error (read-in gain 0.5 on one family), whereas the stratified folds give 0.75 [0.56, 0.94] and
0.0 for the exact model. Items of one cell share the intervention identity only (each has its own parameter draw and history), so
nothing of a test item enters its training fold; the identity cell stays the RESAMPLING unit of every CI (below). The inner penalty
split of the ridge is by item.

CI (review E, B2): identity-cell bootstrap with the fold assignment REDRAWN in every replicate: each replicate resamples cells with
replacement and draws one of the 20 cross-fitting seeds, and uses that seed's out-of-fold errors, so the CI contains the cross-fitting
variability (the between-seed sd of the gain is reported beside it).

UNUSABLE AND LATENT-MISSING ITEMS (review E, B3 / N3). An item is UNUSABLE when the model's call failed or its prediction over the
primary horizon is non-finite (or has another shape): there is no Model A to correct. When more than MAX_UNUSABLE = 1 % of the verdict
items are unusable, SMS and ICG FAIL (charged the worst admissible value +1, `failed_unusable`); otherwise `n_unusable` is reported
beside the scores. An item whose PREDICTION exists but whose LATENT at the onset failed (an encode error, a non-finite or wrongly
shaped z0) is LATENT-MISSING and STAYS in both regressions: its identity features need no latent, its residual microstate is computed
from a u -> PC map instead of the (z, u) -> PC map (so the part of the microstate a latent would explain stays in its residual), and in
the closure base its latent columns are zero with a latent-missing indicator column. A failed latent therefore only gives the
correction more to explain, and can never hide an item's read-in error (a read-in error on 8 of 120 items hidden behind 6 NaN latents
used to move SMS from 0.75 to 0.00). `n_latent_missing` is reported. Items with non-finite TRUE arrays (failed simulations) are
dropped and counted.

HORIZONS (review H, M1): the primary horizon m_i = round(0.125 T / dt_i) is taken per item with the item's own dt; the 5 lags of an
item are L_ij = max(1, round(m_i j / 5)), j = 1..5, and the lag enters as the lag index (one-hot) and the fraction L_ij / m_i.

RESIDUAL MICROSTATE x_res: the top-q public principal components of x at the onset (q = min(10, N_obs)), components with near-zero
PUBLIC spread dropped, minus their ridge prediction from (z, u at onset); the (z, u) -> PC map is fitted on the OUTER training fold only
(penalty by an inner split by item) and the SAME map is applied to that fold's training and test rows (review E, B2: residuals of the
training rows from inner half-fits and of the test rows from the full fit had different distributions, which destroyed the arm);
divided by ONE common scale (the public spread of the first component) and never re-standardised per column.

INTERVENTION IDENTITY features (`id_features`), built INSIDE each fold from the training items (review E, B1): per action key
(event kind x unit or edge, or param x unit x field) its presence and its signed dose, one-hot family, one-hot magnitude class, total
duration, number of events, onset time; test items get the training columns (keys never seen in training carry no column).

DESIGN MATRICES (`_design`, review E, B1): columns are standardised with TRAINING-fold statistics; a column whose training-fold sd is
at most COL_REL_TOL x its largest training magnitude (constant, all-zero or floating-point residue) is DROPPED in the training AND the
test rows; no constant is ever added to a standard deviation used as a divisor. (An identity key present only in the test fold
used to get a training sd of 1e-16 after a global standardisation; dividing by 1e-16 + 1e-9 turned it into test values of 4e9 and
made SMS a random +-1.)

PERMUTATION-MATCHED NULL ARM: the comparison arm of every gain gets the WHOLE block of extra-feature columns (linear, lag
interactions and random features, the same random weights) built from the same extra features with the items PERMUTED within the
training fold and within the test fold. Both arms have identical capacity and feature distributions.

5.3 STATE MEDIATION SCORE (SMS). Rows = (item, lag); target R = true readout minus Model A (the model's intervened prediction; for an
    abstained item its no-intervention prediction). Correction: ridge on [lag one-hot (unpenalised) ; extra ; extra x lag] +
    min(256, max(16, n / 8)) random Fourier features of [extra, lag], penalty by an inner split by item. SMS = gain(err_null, err_B)
    with extra = {x_res, ID} (primary), {x_res} (state information the latent misses), {ID} (intervention information the latent
    pathway misses: a read-in error); SMS_raw = gain(error of Model A with no correction at all, err_B).
5.4 INTERVENTIONAL CLOSURE (ICG). Evaluator-fitted regressions of the readout at the END of the primary horizon (y(t0 + m_i),
    SINGLE-TIME rows: one row per item) on (z, u, a) with and without x_res: base = z, u at onset, mean and last future input over the
    primary horizon, compact intervention descriptors + the identity features (penalised) + x_res (aligned, or permuted in the null
    arm). The base columns are unpenalised only while they are at most one per FREE_MAX_FRACTION^-1 = 4 fitted rows (`_design`); with
    one row per item a fold has about half the items as training rows, so for the benchmark's item counts the base is usually
    ridge-penalised like the other columns, with the penalty chosen by the inner split (review E, m3; `unshrunk_base` is reported).
    x_res is residualised on (z, u) inside the fold, so a penalised base cannot hand its z-effects to x_res. The VERDICT ICG_y is the LINEAR gain (review E, B2: the random-feature
    version changed sign across cross-fitting seeds); the random-feature version (+ random Fourier features of the base and of [base,
    x_res]) is reported. RESOLUTION of "rows = items x the 5 lags": a base shared across lags (with lag-fraction interactions) cannot
    represent y(t0 + L) = G exp(A L) z + ... (a different linear map per lag): on the toy with a model missing one state coordinate,
    adding even the TRUE missing coordinate to that base did not lower its out-of-fold error, and the gain varied from 0.03 to 0.80
    across seeds; with single-time rows the same model gives 0.41-0.60 on 8 of 8 seeds and the exact model 0.00. (Per-lag interaction
    columns would restore the fit but multiply the columns by 5, which removes the reason for item x lag rows.) Descriptive
    z-targets: phi(true future history) at m_i / 2 and m_i (item rows, linear).
    Also the model's OWN interventional closure gap: its latent a short horizon after the onset (rollout under the events) against
    the encoding of the intervened history at that time, relative to the distance between the encodings of the intervened and twin
    histories; and the same for its no-intervention rollout (a model that ignores the intervention scores about 1 there).
"""

from __future__ import annotations

import numpy as np

from . import stats as S
from .evalio import PRIMARY, EvalSystem, TestItem
from .evaluate import Prediction, _rows
from .fresh import as_fresh, safe_call

RIDGE_GRID = (1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0)
FREE_MAX_FRACTION = 0.25
N_LAGS = 5
N_SEEDS = 20                 # cross-fitting seeds of SMS / ICG (PROTOCOL 5.3-5.4)
REPEATS = 5                  # cross-fitting repeats of the DESCRIPTIVE truth regressions (evaluate_truth)
ERR_FLOOR = 0.01
MAX_UNUSABLE = 0.01          # review E, N3: below one identity cell of the smallest verdict item sets
COL_REL_TOL = 1e-8
PC_REL_FLOOR = 1e-6
UNPEN_SCALE = 1e4            # an unpenalised column is scaled by this factor (penalty lam / 1e8)
EVENT_KINDS = ("kick", "current", "current_seq", "silence", "edge_scale", "param")


# ------------------------------------------------------------------------------------------------------------ regression toolkit
def _live_columns(Xtr: np.ndarray) -> np.ndarray:
    """Columns that vary in the training rows: training sd > COL_REL_TOL x the largest training magnitude of the column."""
    if Xtr.shape[0] == 0:
        return np.zeros(Xtr.shape[1], bool)
    sd = Xtr.std(0)
    mag = np.abs(Xtr).max(0)
    return sd > COL_REL_TOL * mag


def _design(Xtr, Xte, keep_scale, n_free: int):
    """Standardised design matrices from TRAINING statistics (columns flagged in keep_scale are centred only). Columns that do not
    vary in the training rows are dropped in both matrices (no constant is added to a divisor). The live columns among the first
    n_free are unpenalised while they are at most FREE_MAX_FRACTION of the rows (their scale is multiplied by UNPEN_SCALE, which is
    ridge with the penalty divided by UNPEN_SCALE^2 on them)."""
    Xtr, Xte = np.asarray(Xtr, np.float64), np.asarray(Xte, np.float64)
    live = _live_columns(Xtr)
    mu = Xtr.mean(0)
    sd = Xtr.std(0)
    div = np.where(keep_scale, 1.0, sd) if keep_scale is not None else sd
    A = (Xtr[:, live] - mu[live]) / div[live]
    B = (Xte[:, live] - mu[live]) / div[live]
    n_free_live = int(live[:n_free].sum()) if n_free else 0
    if n_free_live and n_free_live <= FREE_MAX_FRACTION * len(A):
        s = np.ones(A.shape[1])
        s[:n_free_live] = UNPEN_SCALE
        A, B = A * s, B * s
    return A, B


def _ridge_path(A: np.ndarray, Y: np.ndarray, lams) -> list[np.ndarray]:
    """Coefficients for every penalty in lams (Y centred; penalty lam * n). Primal (p x p Gram) when p <= n, dual (n x n kernel,
    W = A^T alpha) when p > n: the same solutions, the cheaper decomposition."""
    n, p = A.shape
    if p == 0:
        return [np.zeros((0, Y.shape[1])) for _ in lams]
    if p <= n:
        e, V = np.linalg.eigh(A.T @ A)
        Vb = V.T @ (A.T @ Y)
        return [V @ (Vb / np.maximum(e + lam * n, 1e-300)[:, None]) for lam in lams]
    e, U = np.linalg.eigh(A @ A.T)
    Uy = U.T @ Y
    return [A.T @ (U @ (Uy / np.maximum(e + lam * n, 1e-300)[:, None])) for lam in lams]


def ridge_fit_predict(Xtr, Ytr, Xte, lam, keep_scale: np.ndarray | None = None, n_free: int = 0):
    """Ridge with training-standardised features (see `_design`)."""
    Ytr = np.asarray(Ytr, np.float64)
    Y2 = Ytr[:, None] if Ytr.ndim == 1 else Ytr
    A, B = _design(Xtr, Xte, keep_scale, n_free)
    ym = Y2.mean(0)
    W = _ridge_path(A, Y2 - ym, [lam])[0]
    out = B @ W + ym
    return out[:, 0] if Ytr.ndim == 1 else out


def ridge_cv_fit_predict(Xtr, Ytr, Xte, gtr, keep_scale=None, grid=RIDGE_GRID, seed: int = 0, n_free: int = 0):
    """Ridge whose penalty is chosen by an inner two-fold split of the training rows by group (cell), then refitted on all training
    rows. Each half is standardised on its own rows (as a separate fit would be); one eigendecomposition per fitted set serves the
    grid."""
    Xtr, Ytr = np.asarray(Xtr, np.float64), np.asarray(Ytr, np.float64)
    Y2 = Ytr[:, None] if Ytr.ndim == 1 else Ytr
    u = np.unique(gtr)
    best = 1e-2
    if len(u) >= 2:
        r = np.random.default_rng(seed)
        half = np.isin(gtr, u[r.permutation(len(u))[: len(u) // 2]])
        errs = np.zeros(len(grid))
        for a in (half, ~half):
            if a.sum() < 3 or (~a).sum() < 3:
                errs[:] = np.inf
                break
            A, B = _design(Xtr[a], Xtr[~a], keep_scale, n_free)
            ym = Y2[a].mean(0)
            for j, W in enumerate(_ridge_path(A, Y2[a] - ym, grid)):
                errs[j] += float(np.mean((B @ W + ym - Y2[~a]) ** 2))
        if np.isfinite(errs).any():
            best = grid[int(np.argmin(errs))]
    return ridge_fit_predict(Xtr, Ytr, Xte, best, keep_scale, n_free)


def rff_raw(Xs: np.ndarray, n_feat: int, rng: np.random.Generator, gamma: float = 1.0) -> np.ndarray:
    """Random Fourier features of already-scaled inputs."""
    if n_feat <= 0 or Xs.shape[1] == 0:
        return np.zeros((len(Xs), 0))
    W = rng.standard_normal((Xs.shape[1], n_feat)) * np.sqrt(2 * gamma / max(1, Xs.shape[1]))
    b = rng.uniform(0, 2 * np.pi, n_feat)
    return np.sqrt(2.0 / n_feat) * np.cos(Xs @ W + b)


def standardise(X: np.ndarray, rows: np.ndarray | None = None) -> np.ndarray:
    """Columns standardised with the statistics of `rows` (default all rows); columns that do not vary there are dropped (never
    divided by a tiny sd)."""
    X = np.asarray(X, np.float64)
    ref = X if rows is None else X[rows]
    live = _live_columns(ref)
    return (X[:, live] - ref[:, live].mean(0)) / ref[:, live].std(0)


def n_rff(n_rows: int) -> int:
    return int(min(256, max(16, n_rows // 8)))


def cell_stratified_folds(cells: np.ndarray, rep: int, seed: int) -> tuple[np.ndarray, np.ndarray] | None:
    """Two complementary training masks over ITEMS, stratified by identity cell: in every cell the (shuffled) items alternate between
    the folds, starting at a random fold, so each cell's states are divided (a single-state cell goes to a random fold). None with
    fewer than 8 items."""
    cells = np.asarray(cells)
    if len(cells) < 8:
        return None
    rr = np.random.default_rng(seed + 1009 * (rep + 1))
    fold = np.zeros(len(cells), bool)
    for c in np.unique(cells):
        idx = np.flatnonzero(cells == c)
        idx = idx[rr.permutation(len(idx))]
        fold[idx[int(rr.integers(0, 2))::2]] = True
    if fold.all() or not fold.any():
        return None
    return fold, ~fold


def fold_masks(groups: np.ndarray, rep: int, seed: int) -> tuple[np.ndarray, np.ndarray] | None:
    """Two complementary training masks of a random split of the GROUPS (whole groups per fold; used by the descriptive truth
    regressions, grouped by source trajectory); None with fewer than 4 groups."""
    uniq = np.unique(groups)
    if len(uniq) < 4:
        return None
    rr = np.random.default_rng(seed + 1009 * (rep + 1))
    fold = np.isin(groups, uniq[rr.permutation(len(uniq))[: len(uniq) // 2]])
    return fold, ~fold


def fold_permutation(tr_items: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """An item permutation that shuffles items WITHIN the training fold and WITHIN the test fold (the null arm)."""
    n = len(tr_items)
    perm = np.arange(n)
    for mask in (tr_items, ~tr_items):
        idx = np.flatnonzero(mask)
        perm[idx] = idx[rng.permutation(len(idx))]
    return perm


def residual_map(PC: np.ndarray, ZU: np.ndarray, groups: np.ndarray, tr_items: np.ndarray, scale: float, seed: int,
                 z_ok: np.ndarray | None = None, U: np.ndarray | None = None) -> np.ndarray:
    """x_res of EVERY item from ONE (z, u) -> PC map fitted on the training items (review E, B2), divided by the common scale.
    LATENT-MISSING items (z_ok False: the model's encoding failed or is non-finite while its prediction exists; review E, N3) get
    their residual from a u -> PC map fitted on the training items (u = U), so the part of the microstate a latent would explain stays
    in their residual: a failed latent can only give the correction MORE to explain, never hide an item."""
    if PC.shape[1] == 0:
        return np.zeros((len(PC), 0))
    if z_ok is None or bool(np.all(z_ok)):
        pred = ridge_cv_fit_predict(ZU[tr_items], PC[tr_items], ZU, groups[tr_items], seed=seed)
        return (PC - pred) / scale
    z_ok = np.asarray(z_ok, bool)
    out = np.empty_like(np.asarray(PC, np.float64))
    tr_z = tr_items & z_ok
    if tr_z.sum() >= 5 and len(np.unique(groups[tr_z])) >= 4 and z_ok.any():
        out[z_ok] = PC[z_ok] - ridge_cv_fit_predict(ZU[tr_z], PC[tr_z], ZU[z_ok], groups[tr_z], seed=seed)
    else:                                          # too few training items with a latent: every residual from u alone
        z_ok = np.zeros(len(PC), bool)
    miss = ~z_ok
    out[miss] = PC[miss] - ridge_cv_fit_predict(U[tr_items], PC[tr_items], U[miss], groups[tr_items], seed=seed + 1)
    return out / scale


# ------------------------------------------------------------------------------------------------------------ item features
def _event_amp(e: dict) -> float:
    k = e.get("kind")
    if k == "kick":
        return float(sum(abs(float(v)) for v in (e.get("delta") or {}).values()))
    if k == "current":
        return float(sum(abs(float(v)) for v in (e.get("targets") or {}).values()))
    if k == "current_seq":
        return float(sum(np.abs(np.asarray(v, float)).mean() for v in (e.get("targets") or {}).values()))
    if k == "edge_scale":
        return float(abs(1.0 - float(e.get("factor", 1.0))) * len(e.get("edges") or []))
    if k == "param":
        tot = 0.0
        for v in (e.get("targets") or {}).values():
            tot += abs(float(v.get("gain", 1.0)) - 1.0) + abs(float(v.get("tau", 1.0)) - 1.0) + abs(float(v.get("threshold", 0.0)))
        return tot
    if k == "silence":
        return float(len(e.get("targets") or []))
    return 0.0


def _event_arity(e: dict) -> int:
    k = e.get("kind")
    if k == "kick":
        return len(e.get("delta") or {})
    if k in ("current", "current_seq", "param"):
        return len(e.get("targets") or {})
    if k == "silence":
        return len(e.get("targets") or [])
    if k == "edge_scale":
        return len(e.get("edges") or [])
    return 0


def _event_duration(e: dict, horizon_s: float) -> float:
    if "t" in e:
        return 0.0
    t0, t1 = float(e.get("t0", 0.0)), e.get("t1")
    if e.get("kind") == "current_seq":
        segs = max((len(v) for v in (e.get("targets") or {}).values()), default=0)
        return float(segs * float(e.get("seg", 0.0)))
    return float((horizon_s if t1 is None else float(t1)) - t0)


def signed_dose(it: TestItem) -> float:
    """Sum over the item's events of the SIGNED amplitude (kick deltas, currents, mean current of a sequence; silencing counts its
    targets, edge and parameter events their deviation from no change)."""
    tot = 0.0
    for e in it.events:
        k = e.get("kind")
        if k == "kick":
            tot += float(sum(float(v) for v in (e.get("delta") or {}).values()))
        elif k == "current":
            tot += float(sum(float(v) for v in (e.get("targets") or {}).values()))
        elif k == "current_seq":
            tot += float(sum(np.asarray(v, float).mean() for v in (e.get("targets") or {}).values()))
        else:
            tot += _event_amp(e)
    return tot


def event_keys(e: dict, horizon_s: float) -> list[tuple[str, float, float]]:
    """(key, signed dose, duration) per elementary action of one event: kick|unit, current|unit, current_seq|unit, silence|unit,
    edge|post-pre, param|unit|field."""
    k = e.get("kind")
    dur = _event_duration(e, horizon_s)
    out = []
    if k == "kick":
        out = [(f"kick|{u}", float(v), 0.0) for u, v in (e.get("delta") or {}).items()]
    elif k == "current":
        out = [(f"current|{u}", float(v), dur) for u, v in (e.get("targets") or {}).items()]
    elif k == "current_seq":
        out = [(f"current_seq|{u}", float(np.mean(np.asarray(v, float))), dur) for u, v in (e.get("targets") or {}).items()]
    elif k == "silence":
        out = [(f"silence|{u}", 1.0, dur) for u in (e.get("targets") or [])]
    elif k == "edge_scale":
        out = [(f"edge|{a}-{b}", float(e.get("factor", 1.0)) - 1.0, dur) for a, b in (e.get("edges") or [])]
    elif k == "param":
        for u, v in (e.get("targets") or {}).items():
            for f, val in (v or {}).items():
                out.append((f"param|{u}|{f}", float(val) - (0.0 if f == "threshold" else 1.0), dur))
    return out


def id_features(items: list[TestItem], horizon_s: float | None = None, train_mask: np.ndarray | None = None) -> tuple[np.ndarray, list[str]]:
    """The INTERVENTION IDENTITY features (raw, unstandardised) of every item, with the columns defined by the TRAINING items
    (`train_mask`, default all): per action key its presence and signed dose (summed over the events), one-hot family, one-hot
    magnitude class, total duration, number of events, onset time. Keys, families and classes absent from the training items carry
    no column (review E, B1: identity columns are built inside each fold)."""
    hs = float(horizon_s) if horizon_s is not None else 1.0
    tr = np.ones(len(items), bool) if train_mask is None else np.asarray(train_mask, bool)
    per_item = [[kk for e in it.events for kk in event_keys(e, hs)] for it in items]
    keys = sorted({kk[0] for i, row in enumerate(per_item) if tr[i] for kk in row})
    col = {k: j for j, k in enumerate(keys)}
    P = np.zeros((len(items), len(keys)))
    D = np.zeros((len(items), len(keys)))
    for i, row in enumerate(per_item):
        for k, dose, _ in row:
            if k in col:
                P[i, col[k]] += 1.0
                D[i, col[k]] += dose
    fams = sorted({items[i].family for i in range(len(items)) if tr[i]})
    mags = sorted({items[i].magnitude_class for i in range(len(items)) if tr[i]})
    H1 = np.array([[float(it.family == f) for f in fams] for it in items]).reshape(len(items), len(fams))
    H2 = np.array([[float(it.magnitude_class == m) for m in mags] for it in items]).reshape(len(items), len(mags))
    glob = np.array([[sum(d for _, _, d in row), float(len(it.events)), float(it.onset)] for row, it in zip(per_item, items)], float)
    names = ([f"has:{k}" for k in keys] + [f"dose:{k}" for k in keys] + [f"family:{v}" for v in fams] + [f"mag:{v}" for v in mags]
             + ["duration", "n_events", "onset"])
    return np.hstack([P, D, H1, H2, glob.reshape(len(items), 3)]), names


def descriptor_features(items: list[TestItem], horizon_s: float) -> np.ndarray:
    """Compact intervention descriptors (generic across targets): event-kind counts, total arity, log-magnitude, signed log-dose,
    total duration, number of events, onset time."""
    rows = []
    for it in items:
        kinds = [e.get("kind") for e in it.events]
        cnt = [float(kinds.count(k)) for k in EVENT_KINDS]
        amp = sum(_event_amp(e) for e in it.events)
        dose = signed_dose(it)
        rows.append(cnt + [float(sum(_event_arity(e) for e in it.events)), float(np.log1p(amp)), float(np.sign(dose) * np.log1p(abs(dose))),
                           float(sum(_event_duration(e, horizon_s) for e in it.events)), float(len(it.events)), float(it.onset)])
    return np.asarray(rows, float) if rows else np.zeros((0, len(EVENT_KINDS) + 6))


def _pcs(items: list[TestItem], sysc: EvalSystem) -> tuple[np.ndarray, float]:
    """(public principal components of x at the onsets, their COMMON scale), from PUBLIC training data (`EvalSystem.pca_sd`):
    components whose public spread is below PC_REL_FLOOR x the largest are dropped; the residual microstate is divided by the public
    spread of the FIRST (largest) component, never per component. Fallback for an EvalSystem without `pca_sd`: the same rule on the
    spread over the items (model-independent, reported)."""
    X = np.stack([it.x_hist[-1] for it in items]).astype(np.float64)
    PC = (X - sysc.pca_mean) @ sysc.pca_comps.T
    sd = np.asarray(sysc.pca_sd, np.float64)[: PC.shape[1]] if sysc.pca_sd is not None else PC.std(0)
    top = float(sd.max()) if sd.size else 0.0
    if top <= 0:
        return PC[:, :0], 1.0
    return PC[:, sd > PC_REL_FLOOR * top], top


# ------------------------------------------------------------------------------------------------------------ item selection
def select_items(sysc: EvalSystem, items: list[TestItem], preds: dict[str, Prediction]) -> dict:
    """The verdict items of 5.3 / 5.4 split into usable and unusable (see the module docstring), with the counts."""
    cand = [it for it in items if it.is_verdict() and it.item_id in preds]
    bad_truth = [it for it in cand if not it.truth_ok()]
    cand = [it for it in cand if it.truth_ok()]
    short = [it for it in cand if len(it.y_future) <= sysc.horizon_steps(PRIMARY, it.dt)]
    cand = [it for it in cand if len(it.y_future) > sysc.horizon_steps(PRIMARY, it.dt)]
    dims = [np.size(preds[it.item_id].z0) for it in cand if preds[it.item_id].z0 is not None]
    k = int(np.bincount(dims).argmax()) if dims else 0
    usable, unusable, z_ok = [], [], []
    for it in cand:
        p = preds[it.item_id]
        m = sysc.horizon_steps(PRIMARY, it.dt)
        y = _rows(p.y_base if p.abstain else p.y_int, m)
        pred_ok = (p.error is None and y is not None and y.shape == it.y_future[1: m + 1].shape
                   and bool(np.isfinite(np.asarray(y, np.float64)).all()))
        lat_ok = (getattr(p, "encode_error", None) is None and p.z0 is not None and np.size(p.z0) == k and k > 0
                  and bool(np.isfinite(np.asarray(p.z0, np.float64)).all()))
        if pred_ok:
            usable.append(it)
            z_ok.append(lat_ok)
        else:
            unusable.append(it)
    n = len(usable) + len(unusable)
    return {"usable": usable, "z_ok": np.array(z_ok, bool), "unusable": unusable, "n_items": n, "n_unusable": len(unusable),
            "n_latent_missing": int(len(z_ok) - sum(z_ok)), "unusable_fraction": (len(unusable) / n) if n else 0.0,
            "n_dropped_nonfinite_truth": len(bad_truth), "n_short_future": len(short), "k": k}


def _latent_matrix(use: list[TestItem], preds: dict[str, Prediction], z_ok: np.ndarray, k: int) -> np.ndarray:
    """(n_items, k) latents at the onsets; zeros for latent-missing items (their residual comes from u alone, `residual_map`)."""
    Z = np.zeros((len(use), max(k, 0)))
    for i, it in enumerate(use):
        if z_ok[i]:
            Z[i] = np.asarray(preds[it.item_id].z0, float).reshape(-1)
    return Z


def _failed(value_keys: tuple[str, ...], sel: dict, note: str) -> dict:
    """The result of a failed SMS / ICG: the worst admissible value +1 for every verdict key."""
    worst = {"point": 1.0, "ci95": [1.0, 1.0], "failed": True}
    return {**{k: dict(worst) for k in value_keys}, "failed_unusable": True, "note": note,
            **{k: sel[k] for k in ("n_items", "n_unusable", "unusable_fraction", "n_dropped_nonfinite_truth", "n_short_future")}}


def _lag_rows(items: list[TestItem], sysc: EvalSystem) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(item index, lag index 0..4, lag sample L, lag fraction L / m_i) of the (item, lag) rows (per-item dt)."""
    ri, rj, rL, rf = [], [], [], []
    for i, it in enumerate(items):
        m = sysc.horizon_steps(PRIMARY, it.dt)
        for j in range(1, N_LAGS + 1):
            L = max(1, int(round(m * j / N_LAGS)))
            ri.append(i)
            rj.append(j - 1)
            rL.append(L)
            rf.append(L / m)
    return np.array(ri), np.array(rj), np.array(rL), np.array(rf, float)


def _bootstrap_seeds(E1: np.ndarray, E2: np.ndarray, row_cell: np.ndarray, n_cells: int, n_boot: int, seed: int,
                     rows: np.ndarray | None = None) -> tuple[float, S.Estimate, list[float]]:
    """Gain point estimate (errors averaged over seeds) and its CI with the fold assignment redrawn per replicate. E1, E2: (n_seeds,
    n_rows) out-of-fold errors of the null and the tested arm; rows: an optional subset of rows (e.g. the last lag)."""
    if rows is not None:
        E1, E2, row_cell = E1[:, rows], E2[:, rows], row_cell[rows]
    ok = np.isfinite(E1).all(1) & np.isfinite(E2).all(1)
    E1, E2 = E1[ok], E2[ok]
    if len(E1) == 0:
        return float("nan"), S.Estimate(float("nan"), [float("nan")] * 2, n_cells), []
    point = S.gain(float(E1.mean(0).mean()), float(E2.mean(0).mean()), ERR_FLOOR)
    per_seed = [S.gain(float(a.mean()), float(b.mean()), ERR_FLOOR) for a, b in zip(E1, E2)]
    S1 = np.stack([np.bincount(row_cell, weights=e, minlength=n_cells) for e in E1])
    S2 = np.stack([np.bincount(row_cell, weights=e, minlength=n_cells) for e in E2])
    cnt = np.bincount(row_cell, minlength=n_cells).astype(float)
    rng = np.random.default_rng(seed + 7919)
    present = np.flatnonzero(cnt > 0)
    W = np.zeros((n_boot, n_cells))
    W[:, present] = rng.multinomial(len(present), np.full(len(present), 1.0 / len(present)), size=n_boot)
    sb = rng.integers(0, len(E1), n_boot)
    n = W @ cnt
    m1 = np.where(n > 0, (W * S1[sb]).sum(1) / np.where(n > 0, n, 1.0), np.nan)
    m2 = np.where(n > 0, (W * S2[sb]).sum(1) / np.where(n > 0, n, 1.0), np.nan)
    est = S.make_estimate(point, S.gain_vec(m1, m2, ERR_FLOOR), len(present), worst=1.0, n_seeds=len(E1),
                          seed_sd=float(np.std(per_seed)) if len(per_seed) > 1 else 0.0)
    return point, est, per_seed


def _summary(est: S.Estimate, per_seed: list[float], e1: np.ndarray, e2: np.ndarray) -> dict:
    return {"point": est.point, "ci95": est.ci95, "n_cells": est.n_units, "n_nonfinite_reps": est.n_nonfinite_reps,
            "seed_sd": float(np.std(per_seed)) if len(per_seed) > 1 else 0.0, "n_seeds": len(per_seed),
            "err_null": float(np.nanmean(e1)), "err_B": float(np.nanmean(e2))}


# ------------------------------------------------------------------------------------------------------------ 5.3 SMS
def eval_mediation(sysc: EvalSystem, items: list[TestItem], preds: dict[str, Prediction], n_boot: int = S.N_BOOT, seed: int = 0,
                   n_seeds: int = N_SEEDS, repeats: int | None = None) -> dict:
    """5.3: state mediation score (see the module docstring). `repeats` is an alias of n_seeds (older callers)."""
    n_seeds = int(repeats) if repeats is not None else int(n_seeds)
    sel = select_items(sysc, items, preds)
    base_info = {k: sel[k] for k in ("n_items", "n_unusable", "n_latent_missing", "unusable_fraction", "n_dropped_nonfinite_truth",
                                     "n_short_future")}
    if sel["n_items"] and sel["unusable_fraction"] > MAX_UNUSABLE:
        return _failed(("SMS", "SMS_x_res", "SMS_id", "SMS_raw"), sel,
                       f"{sel['n_unusable']} of {sel['n_items']} verdict items unusable (> {MAX_UNUSABLE:.0%}): SMS fails")
    use, z_ok = sel["usable"], sel["z_ok"]
    res: dict = {**base_info, "n_seeds": n_seeds}
    if len(use) < 8:
        res["note"] = "too few usable items"
        return res
    sd = sysc.y_sd
    Z = _latent_matrix(use, preds, z_ok, sel["k"])
    U0 = np.stack([it.u_hist[-1] for it in use]).astype(np.float64)
    ZU = np.hstack([Z, U0])
    PC, pc_scale = _pcs(use, sysc)
    cells = np.array([it.cell() for it in use])
    item_ids = np.arange(len(use))
    _, cell_idx = np.unique(cells, return_inverse=True)
    n_cells = int(cell_idx.max()) + 1
    ri, rj, rL, rf = _lag_rows(use, sysc)
    Y = np.stack([use[i].y_future[L] for i, L in zip(ri, rL)]) / sd
    YA = np.stack([(preds[use[i].item_id].y_base if preds[use[i].item_id].abstain else preds[use[i].item_id].y_int)[L]
                   for i, L in zip(ri, rL)]) / sd
    R = Y - YA
    row_cell = cell_idx[ri]
    groups_rows = item_ids[ri]
    lag_oh = np.zeros((len(ri), N_LAGS))
    lag_oh[np.arange(len(ri)), rj] = 1.0
    rl = rf[:, None]
    nf = n_rff(len(ri))
    hs = sysc.horizon_s(PRIMARY)
    arms = {"x_res+id": (True, True), "x_res": (True, False), "id": (False, True)}
    E_null = {a: np.full((n_seeds, len(ri)), np.nan) for a in arms}
    E_B = {a: np.full((n_seeds, len(ri)), np.nan) for a in arms}
    for s in range(n_seeds):
        fm = cell_stratified_folds(cells, s, seed)
        if fm is None:
            res["note"] = "too few items for two folds"
            return res
        for d, tr_items in enumerate(fm):
            tr_rows = tr_items[ri]
            te_rows = ~tr_rows
            if tr_rows.sum() < 10 or te_rows.sum() < 10:
                continue
            XR = residual_map(PC, ZU, item_ids, tr_items, pc_scale, seed + 31 * s + d, z_ok=z_ok, U=U0)
            IDF, _ = id_features(use, hs, tr_items)
            perm = fold_permutation(tr_items, np.random.default_rng(seed + 5003 * s + 17 * d))
            for arm_i, (name, (use_x, use_id)) in enumerate(arms.items()):
                s_rff = seed + 7 + 1009 * s + 101 * arm_i + 13 * d
                errs = []
                for order in (perm, np.arange(len(use))):            # null arm (permuted within folds), then the aligned arm
                    Ex = XR[order][ri] if use_x else np.zeros((len(ri), 0))
                    Ei = IDF[order][ri] if use_id else np.zeros((len(ri), 0))
                    Eis = standardise(Ei, tr_rows) if Ei.shape[1] else Ei
                    rf_in = np.hstack([Ex, Eis, (rl - 0.5) * 2.0])
                    rfe = rff_raw(rf_in, nf, np.random.default_rng(s_rff))
                    feats = np.hstack([lag_oh, Ex, Ex * rl, Ei, Ei * rl, rfe])
                    ks = np.r_[np.zeros(N_LAGS, bool), np.ones(2 * Ex.shape[1], bool), np.zeros(2 * Ei.shape[1] + rfe.shape[1], bool)]
                    pr = ridge_cv_fit_predict(feats[tr_rows], R[tr_rows], feats[te_rows], groups_rows[tr_rows], keep_scale=ks,
                                              seed=seed + s, n_free=N_LAGS)
                    errs.append(((R[te_rows] - pr) ** 2).mean(1))
                E_null[name][s, te_rows], E_B[name][s, te_rows] = errs
    raw = np.tile((R ** 2).mean(1), (n_seeds, 1))
    ests = {}
    for name in arms:
        key = "SMS" if name == "x_res+id" else f"SMS_{name.replace('+', '_')}"
        _, est, per_seed = _bootstrap_seeds(E_null[name], E_B[name], row_cell, n_cells, n_boot, seed)
        res[key] = _summary(est, per_seed, E_null[name], E_B[name])
        ests[key] = est
    _, est_raw, per_raw = _bootstrap_seeds(raw, E_B["x_res+id"], row_cell, n_cells, n_boot, seed + 1)
    res["SMS_raw"] = _summary(est_raw, per_raw, raw, E_B["x_res+id"])
    res["n_rows"] = int(len(ri))
    res["n_cells"] = n_cells
    res["_estimates"] = ests
    return res


# ------------------------------------------------------------------------------------------------------------ 5.4 ICG
def eval_closure(model, sysc: EvalSystem, items: list[TestItem], preds: dict[str, Prediction], n_boot: int = S.N_BOOT, seed: int = 0,
                 n_seeds: int = N_SEEDS, repeats: int | None = None) -> dict:
    """5.4: interventional closure gains from the residual microstate (the verdict ICG_y is LINEAR, at the end of the primary
    horizon), and the model's own interventional closure gap."""
    n_seeds = int(repeats) if repeats is not None else int(n_seeds)
    F = as_fresh(model)
    sid = sysc.system_id
    sel = select_items(sysc, items, preds)
    base_info = {k: sel[k] for k in ("n_items", "n_unusable", "n_latent_missing", "unusable_fraction", "n_dropped_nonfinite_truth",
                                     "n_short_future")}
    if sel["n_items"] and sel["unusable_fraction"] > MAX_UNUSABLE:
        out = _failed(("ICG_y", "ICG_y_rff"), sel,
                      f"{sel['n_unusable']} of {sel['n_items']} verdict items unusable (> {MAX_UNUSABLE:.0%}): ICG fails")
        out["own_closure_gap"] = own_closure_gap(F, sysc, [it for it, ok in zip(sel["usable"], sel["z_ok"]) if ok], preds)
        return out
    use, z_ok = sel["usable"], sel["z_ok"]
    use_lat = [it for it, ok in zip(use, z_ok) if ok]
    res: dict = {**base_info, "n_seeds": n_seeds}
    if len(use) < 8:
        res["note"] = "too few usable items"
        res["own_closure_gap"] = own_closure_gap(F, sysc, use_lat, preds)
        return res
    sd = sysc.y_sd
    hs = sysc.horizon_s(PRIMARY)
    # latent-missing items (review E, N3): zeros in the latent columns plus an indicator column in the base, and their residual
    # microstate from u alone, so the missing latent is charged to the model, never free
    Z = _latent_matrix(use, preds, z_ok, sel["k"])
    Zmiss = (~z_ok).astype(np.float64)[:, None]
    U0 = np.stack([it.u_hist[-1] for it in use]).astype(np.float64)
    UF, Y = [], []
    for it in use:
        m = sysc.horizon_steps(PRIMARY, it.dt)            # per item, with the item's own dt (review H, M1)
        UF.append(np.concatenate([it.u_future[1: m + 1].mean(0), it.u_future[m]]))
        Y.append(it.y_future[m] / sd)
    base = np.hstack([Z, Zmiss, U0, np.stack(UF).astype(np.float64), descriptor_features(use, hs)])
    Y = np.stack(Y)
    n_free = base.shape[1]
    ZU = np.hstack([Z, U0])
    PC, pc_scale = _pcs(use, sysc)
    cells = np.array([it.cell() for it in use])
    item_ids = np.arange(len(use))
    _, cell_idx = np.unique(cells, return_inverse=True)
    n_cells = int(cell_idx.max()) + 1
    nf = n_rff(len(use))
    E = {k: np.full((n_seeds, len(use)), np.nan) for k in ("lin_null", "lin_x", "rff_null", "rff_x")}
    zt = _future_encodings(F, sid, use, sysc) if bool(np.all(z_ok)) else {}   # descriptive z-targets (item rows, linear)
    Ez = {name: {k: np.full((n_seeds, len(use)), np.nan) for k in ("null", "x")} for name in zt}
    for s in range(n_seeds):
        fm = cell_stratified_folds(cells, s, seed)
        if fm is None:
            res["note"] = "too few items for two folds"
            res["own_closure_gap"] = own_closure_gap(F, sysc, use_lat, preds)
            return res
        for d, tr in enumerate(fm):
            te = ~tr
            if tr.sum() < 5 or te.sum() < 5:
                continue
            XR = residual_map(PC, ZU, item_ids, tr, pc_scale, seed + 31 * s + d, z_ok=z_ok, U=U0)
            IDF, _ = id_features(use, hs, tr)
            perm = fold_permutation(tr, np.random.default_rng(seed + 5003 * s + 17 * d))
            bs = standardise(base, tr)
            rfb = rff_raw(bs, nf, np.random.default_rng(seed + 7 + 1009 * s + 13 * d))
            for tag, order in (("null", perm), ("x", item_ids)):
                Ex = XR[order]
                lin = np.hstack([base, IDF, Ex])
                ks = np.r_[np.zeros(n_free + IDF.shape[1], bool), np.ones(Ex.shape[1], bool)]
                p1 = ridge_cv_fit_predict(lin[tr], Y[tr], lin[te], item_ids[tr], keep_scale=ks, seed=seed + s, n_free=n_free)
                E[f"lin_{tag}"][s, te] = ((Y[te] - p1) ** 2).mean(1)
                rfx = rff_raw(np.hstack([bs, Ex]), nf, np.random.default_rng(seed + 8 + 1009 * s + 13 * d))
                X2 = np.hstack([lin, rfb, rfx])
                ks2 = np.r_[ks, np.zeros(rfb.shape[1] + rfx.shape[1], bool)]
                p2 = ridge_cv_fit_predict(X2[tr], Y[tr], X2[te], item_ids[tr], keep_scale=ks2, seed=seed + s, n_free=n_free)
                E[f"rff_{tag}"][s, te] = ((Y[te] - p2) ** 2).mean(1)
                for name, T in zt.items():
                    pz = ridge_cv_fit_predict(lin[tr], T[tr], lin[te], item_ids[tr], keep_scale=ks, seed=seed + s, n_free=n_free)
                    Ez[name][tag][s, te] = ((T[te] - pz) ** 2).mean(1)
    ests = {}
    for key, (a_, b_) in {"ICG_y": ("lin_null", "lin_x"), "ICG_y_rff": ("rff_null", "rff_x")}.items():
        _, est, per_seed = _bootstrap_seeds(E[a_], E[b_], cell_idx, n_cells, n_boot, seed)
        res[key] = {**_summary(est, per_seed, E[a_], E[b_]), "regressor": "linear" if a_.startswith("lin") else "rff"}
        ests[key] = est
    for name in zt:
        _, est, per_seed = _bootstrap_seeds(Ez[name]["null"], Ez[name]["x"], cell_idx, n_cells, n_boot, seed)
        res[f"ICG_{name}"] = {**_summary(est, per_seed, Ez[name]["null"], Ez[name]["x"]), "regressor": "linear"}
    if not zt:
        res["z_targets_note"] = "items carry no future microstate, or an encoding of a future history failed"
    res["n_cells"] = n_cells
    res["unshrunk_base"] = bool(n_free <= FREE_MAX_FRACTION * 0.5 * len(use))
    res["_estimates"] = ests
    res["own_closure_gap"] = own_closure_gap(F, sysc, use_lat, preds)
    return res


def _future_encodings(F, sid: str, use: list[TestItem], sysc: EvalSystem) -> dict[str, np.ndarray]:
    """{"z_half": ..., "z_end": ...}: the model's encodings of the TRUE future histories at m_i / 2 and m_i, each coordinate
    standardised (descriptive targets); {} when an item has no future microstate or an encoding fails."""
    if not all(it.x_future is not None for it in use):
        return {}
    out = {"z_half": [], "z_end": []}
    for it in use:
        m = sysc.horizon_steps(PRIMARY, it.dt)
        if len(it.x_future) <= m:
            return {}
        for name, L in (("z_half", max(1, m // 2)), ("z_end", m)):
            xh = np.vstack([it.x_hist, it.x_future[1: L + 1]])
            uh = np.vstack([it.u_hist, it.u_future[1: L + 1]])
            z, err = safe_call(F.encode, sid, xh, uh, it.dt)
            if err or z is None or not np.isfinite(np.asarray(z, float)).all():
                return {}
            out[name].append(np.asarray(z, float).reshape(-1))
    res = {}
    for name, v in out.items():
        A = np.stack(v)
        live = _live_columns(A)
        res[name] = (A[:, live] - A[:, live].mean(0)) / A[:, live].std(0) if live.any() else A[:, :0]
    return {k: v for k, v in res.items() if v.shape[1]}


def own_closure_gap(model, sysc: EvalSystem, items: list[TestItem], preds: dict[str, Prediction]) -> dict:
    """The model's latent a short horizon after the onset (its rollout under the events) against the encoding of the intervened
    history at that time, relative to the squared distance between the encodings of the intervened and the twin histories."""
    F = as_fresh(model)
    sid = sysc.system_id
    num = noeff = den = 0.0
    n = 0
    for it in items:
        p = preds.get(it.item_id)
        if p is None or p.z_int is None or p.z_base is None or it.x_future is None or it.x_twin_future is None:
            continue
        a = sysc.horizon_steps("short", it.dt)
        if len(p.z_int) <= a or len(p.z_base) <= a or len(it.x_future) <= a or len(it.x_twin_future) <= a:
            continue
        xi = np.vstack([it.x_hist, it.x_future[1: a + 1]])
        xt = np.vstack([it.x_hist, it.x_twin_future[1: a + 1]])
        uh = np.vstack([it.u_hist, it.u_future[1: a + 1]])
        zi, e1 = safe_call(F.encode, sid, xi, uh, it.dt)
        zt, e2 = safe_call(F.encode, sid, xt, uh, it.dt)
        if e1 or e2 or not (np.isfinite(zi).all() and np.isfinite(zt).all()) or np.shape(zi) != np.shape(p.z_int[a]):
            continue
        num += float(np.sum((p.z_int[a] - zi) ** 2))
        noeff += float(np.sum((p.z_base[a] - zi) ** 2))
        den += float(np.sum((zt - zi) ** 2))
        n += 1
    return {"ratio": num / den if den > 0 else float("nan"), "ratio_no_effect": noeff / den if den > 0 else float("nan"), "n": n}
