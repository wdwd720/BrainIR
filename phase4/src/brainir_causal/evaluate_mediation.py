"""State mediation score and interventional closure (benchmarks/causal_state_v1/PROTOCOL.md sections 5.3-5.4; goal5 sections 13, 31).

Both are CONDITIONAL-PREDICTION tests on the test intervention items, cross-fitted by resampling group (2 folds x 5 repeats; per-row
squared errors averaged over the repeats), with 95 % CIs by resampling groups (clusters of rows). Readout targets are in units of the
public pooled training sd; the error floor of the gain is 0.01 in those units; gains are clipped at -1.

RESIDUAL MICROSTATE x_res: the top-q public principal components of x at the onset (q = min(10, N_obs), `EvalSystem.pca_comps`)
minus their ridge prediction from (z, u at onset), computed INSIDE each fold (an inner two-fold split by group for the training rows,
a fit on all training rows for the test rows). Components whose PUBLIC spread (over the training trajectories, `EvalSystem.pca_sd`)
is below 1e-6 x the largest are dropped, and the residual is divided by ONE common scale (the public spread of the first component)
and never re-standardised per column, so a residual that is numerical noise stays small (RESOLUTION: dividing each component by its
own spread turned near-silent directions into O(1) noise features, which produced seed-dependent spurious gains of up to 0.3 for an
exact model in the development tests).

PERMUTATION-MATCHED NULL ARM (RESOLUTION of "capacity-matched"): the comparison arm of every gain gets the SAME extra features, built
with the same random weights, but with its items PERMUTED within the training fold and within the test fold. Both arms therefore have
identical capacity and feature distributions; the gain measures only whether the extra information is aligned with the items.
(Matching by feature COUNT alone left seed-dependent differences between two random-feature draws of up to 0.3.)

INTERVENTION IDENTITY features (`id_features`): the item's elementary actions decomposed additively (per action key, e.g. kick|unit,
current|unit, silence|unit, edge|post-pre, param|unit|field: its presence and its SIGNED dose, summed over the events), one-hot family,
one-hot magnitude class, total duration, number of events and onset time. RESOLUTION: the draft lists a one-hot (family x target set),
the magnitude class and the onset; the decomposition carries the same information for single-target families, adds the sign
(magnitude classes carry none; kicks and pulses can be positive or negative) and shares strength across paired, grouped and composite
interventions, whose literal one-hot identities are unique per item (tested: with unique identities a read-in error that depends on
the target is not attributed to the identity at all).

5.3 STATE MEDIATION SCORE (SMS). Rows = (item, lag) at 5 lags round(m j / 5), j = 1..5, m = primary-horizon steps; target = the
    true readout under the intervention. Model A = the model's own prediction (the intervened rollout; for an abstained item its
    no-intervention rollout, i.e. "no effect"). Model B = Model A + a learned correction from the EXTRA features. Correction learner:
    ridge on [lag one-hot (unpenalised) ; extra ; extra x lag] + min(256, max(16, n / 8)) random Fourier features of [extra, lag],
    penalty chosen by an inner split by group. The comparison arm is Model A + the same correction learner on the PERMUTED extra
    features (above), so a per-lag bias of the model and the extra capacity are in both arms and SMS isolates the information aligned
    with the items. SMS = gain(err_null, err_B); SMS_raw = gain(error of Model A with no correction at all, err_B) is reported beside.
    Feature sets reported: {x_res, ID} (primary), {x_res} (state information the latent misses), {ID} (intervention information the
    latent pathway misses: a read-in error).
5.4 INTERVENTIONAL CLOSURE (ICG). Evaluator-fitted regressions on the same items: error(z, u, a) vs error(z, u, a, x_res) for
    (i) y at the end of the primary horizon and (ii) z_future = phi(the TRUE future history) at 2 lags (m / 2 and m), the latter as
    descriptive targets (each coordinate standardised). The base (z, u at onset, mean and last future input to the target, compact
    intervention descriptors: event kinds, arity, log-magnitude, signed log-dose, duration, onset) is fitted WITHOUT shrinkage while it
    has at most 1 column per 4 fitted rows; the identity features and random features are penalised; the comparison arm gets the
    permuted x_res (above). ICG = gain(err_null, err_x_res); linear and random-feature versions; the verdict's ICG_y is the
    random-feature version at the primary horizon.
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
REPEATS = 5
ERR_FLOOR = 0.01
EVENT_KINDS = ("kick", "current", "current_seq", "silence", "edge_scale", "param")


# ------------------------------------------------------------------------------------------------------------ regression toolkit
def _design(Xtr, Xte, keep_scale, n_free: int):
    """Standardised design matrices with the penalty folded into the column scale: ridge with penalty lam n diag(pen) on W is ridge
    with penalty lam n I on W' = W / s for columns scaled by s = pen^-1/2 (so one eigendecomposition serves every lam)."""
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    if keep_scale is not None:
        sd = np.where(keep_scale, 1.0, sd)
    A = (Xtr - mu) / sd
    B = (Xte - mu) / sd
    if n_free and n_free <= FREE_MAX_FRACTION * len(A):
        s = np.ones(A.shape[1])
        s[:n_free] = 1e4                                  # pen = 1e-8 for the unshrunk base
        A, B = A * s, B * s
    return A, B


def _ridge_path(A: np.ndarray, Y: np.ndarray, lams) -> list[np.ndarray]:
    """Coefficients for every penalty in lams (Y centred; penalty lam * n). Primal (p x p Gram) when p <= n, dual (n x n kernel,
    W = A^T alpha) when p > n: the same solutions, the cheaper decomposition."""
    n, p = A.shape
    if p <= n:
        e, V = np.linalg.eigh(A.T @ A)
        Vb = V.T @ (A.T @ Y)
        return [V @ (Vb / np.maximum(e + lam * n, 1e-300)[:, None]) for lam in lams]
    e, U = np.linalg.eigh(A @ A.T)
    Uy = U.T @ Y
    return [A.T @ (U @ (Uy / np.maximum(e + lam * n, 1e-300)[:, None])) for lam in lams]


def ridge_fit_predict(Xtr, Ytr, Xte, lam, keep_scale: np.ndarray | None = None, n_free: int = 0):
    """Ridge with standardised features (columns flagged in keep_scale are centred only). The first n_free columns are NOT penalised
    while they are at most FREE_MAX_FRACTION of the fitted rows (the base of a closure regression; extra columns that merely repeat
    the base must not "help" by undoing its shrinkage)."""
    A, B = _design(Xtr, Xte, keep_scale, n_free)
    ym = Ytr.mean(0)
    W = _ridge_path(A, Ytr - ym, [lam])[0]
    return B @ W + ym


def ridge_cv_fit_predict(Xtr, Ytr, Xte, gtr, keep_scale=None, grid=RIDGE_GRID, seed: int = 0, n_free: int = 0):
    """Ridge whose penalty is chosen by an inner two-fold split of the training rows by group, then refitted on all training rows.
    Each half is standardised on its own rows (as a separate fit would be); one eigendecomposition per fitted set serves the grid."""
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
            ym = Ytr[a].mean(0)
            for j, W in enumerate(_ridge_path(A, Ytr[a] - ym, grid)):
                errs[j] += float(np.mean((B @ W + ym - Ytr[~a]) ** 2))
        if np.isfinite(errs).any():
            best = grid[int(np.argmin(errs))]
    return ridge_fit_predict(Xtr, Ytr, Xte, best, keep_scale, n_free)


def rff_raw(Xs: np.ndarray, n_feat: int, rng: np.random.Generator, gamma: float = 1.0) -> np.ndarray:
    """Random Fourier features of already-scaled inputs."""
    if n_feat <= 0:
        return np.zeros((len(Xs), 0))
    W = rng.standard_normal((Xs.shape[1], n_feat)) * np.sqrt(2 * gamma / max(1, Xs.shape[1]))
    b = rng.uniform(0, 2 * np.pi, n_feat)
    return np.sqrt(2.0 / n_feat) * np.cos(Xs @ W + b)


def standardise(X: np.ndarray) -> np.ndarray:
    return (X - X.mean(0)) / (X.std(0) + 1e-9)


def n_rff(n_rows: int) -> int:
    return int(min(256, max(16, n_rows // 8)))


def fold_masks(groups: np.ndarray, rep: int, seed: int) -> tuple[np.ndarray, np.ndarray] | None:
    uniq = np.unique(groups)
    if len(uniq) < 4:
        return None
    rr = np.random.default_rng(seed + 1009 * (rep + 1))
    fold = np.isin(groups, uniq[rr.permutation(len(uniq))[: len(uniq) // 2]])
    return fold, ~fold


def residual_microstate(PC: np.ndarray, ZU: np.ndarray, groups: np.ndarray, tr_m: np.ndarray, sd_pc: np.ndarray, seed: int
                        ) -> tuple[np.ndarray, np.ndarray]:
    """(x_res for the training rows, x_res for the test rows) of one fold direction (see the module docstring); sd_pc is the COMMON
    scale of `_pcs`."""
    itr, ite = np.flatnonzero(tr_m), np.flatnonzero(~tr_m)
    if PC.shape[1] == 0:
        return np.zeros((len(itr), 0)), np.zeros((len(ite), 0))
    r_te = PC[ite] - ridge_cv_fit_predict(ZU[itr], PC[itr], ZU[ite], groups[itr], seed=seed)
    g_tr = groups[itr]
    ut = np.unique(g_tr)
    r_tr = np.zeros((len(itr), PC.shape[1]))
    rr = np.random.default_rng(seed + 17)
    inner = np.isin(g_tr, ut[rr.permutation(len(ut))[: len(ut) // 2]]) if len(ut) >= 4 else None
    if inner is not None and inner.sum() >= 5 and (~inner).sum() >= 5:
        for a in (inner, ~inner):
            r_tr[~a] = PC[itr][~a] - ridge_cv_fit_predict(ZU[itr][a], PC[itr][a], ZU[itr][~a], g_tr[a], seed=seed)
    else:
        r_tr = PC[itr] - ridge_cv_fit_predict(ZU[itr], PC[itr], ZU[itr], g_tr, seed=seed)
    return r_tr / sd_pc, r_te / sd_pc


# ------------------------------------------------------------------------------------------------------------ item features
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


def id_features(items: list[TestItem], horizon_s: float | None = None) -> tuple[np.ndarray, list[str]]:
    """The INTERVENTION IDENTITY as the mediation / closure regressions see it, decomposed ADDITIVELY over the item's elementary
    actions (`event_keys`): per action key its presence and its signed dose, summed over the events; plus one-hot family, one-hot
    magnitude class, total duration, number of events and onset time. RESOLUTION: the draft lists a one-hot (family x target set),
    the magnitude class and the onset. The decomposition carries the same information for single-target families, adds the SIGN
    (magnitude classes have none; kicks and pulses can be positive or negative) and shares statistical strength across paired,
    grouped and composite interventions, whose literal one-hot identities are unique per item and uninformative."""
    hs = float(horizon_s) if horizon_s is not None else 1.0
    per_item = [[kk for e in it.events for kk in event_keys(e, hs)] for it in items]
    keys = sorted({kk[0] for row in per_item for kk in row})
    col = {k: j for j, k in enumerate(keys)}
    P = np.zeros((len(items), len(keys)))
    D = np.zeros((len(items), len(keys)))
    for i, row in enumerate(per_item):
        for k, dose, _ in row:
            P[i, col[k]] += 1.0
            D[i, col[k]] += dose
    fams = [it.family for it in items]
    mags = [it.magnitude_class for it in items]
    u1, i1 = np.unique(fams, return_inverse=True)
    u2, i2 = np.unique(mags, return_inverse=True)
    H1 = np.zeros((len(items), len(u1)))
    H1[np.arange(len(items)), i1] = 1.0
    H2 = np.zeros((len(items), len(u2)))
    H2[np.arange(len(items)), i2] = 1.0
    glob = np.array([[sum(d for _, _, d in row), float(len(it.events)), float(it.onset)] for row, it in zip(per_item, items)], float)
    names = ([f"has:{k}" for k in keys] + [f"dose:{k}" for k in keys] + [f"family:{v}" for v in u1] + [f"mag:{v}" for v in u2]
             + ["duration", "n_events", "onset"])
    return np.hstack([P, D, H1, H2, glob]), names


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


PC_REL_FLOOR = 1e-6


def _pcs(items: list[TestItem], sysc: EvalSystem) -> tuple[np.ndarray, float]:
    """(public principal components of x at the onsets, their COMMON scale), from PUBLIC training data (`EvalSystem.pca_sd`, the
    spread of each component over the training trajectories): components whose public spread is below PC_REL_FLOOR x the largest
    carry only numerical noise and are dropped; the residual microstate is divided by the public spread of the FIRST (largest)
    component, never per component, so a near-silent direction cannot be amplified into an O(1) feature. Fallback for an EvalSystem
    without `pca_sd` (built by an older constructor): the same rule on the spread over the items (model-independent, reported)."""
    X = np.stack([it.x_hist[-1] for it in items]).astype(np.float64)
    PC = (X - sysc.pca_mean) @ sysc.pca_comps.T
    sd = np.asarray(sysc.pca_sd, np.float64)[: PC.shape[1]] if sysc.pca_sd is not None else PC.std(0)
    top = float(sd.max()) if sd.size else 0.0
    if top <= 0:
        return PC[:, :0], 1.0
    return PC[:, sd > PC_REL_FLOOR * top], top


def _usable(items: list[TestItem], preds: dict[str, Prediction], sysc: EvalSystem) -> tuple[list[TestItem], int]:
    """Intervention items with a finite latent at the onset and a usable prediction over the primary horizon."""
    m = sysc.horizon_steps(PRIMARY)
    out, dropped = [], 0
    for it in items:
        if it.is_passive or it.item_id not in preds or len(it.y_future) <= m:
            continue
        p = preds[it.item_id]
        y = _rows(p.y_base if p.abstain else p.y_int, m)
        if p.error is not None or p.z0 is None or not np.isfinite(p.z0).all() or y is None or y.shape != it.y_future[1: m + 1].shape:
            dropped += 1
            continue
        out.append(it)
    return out, dropped


# ------------------------------------------------------------------------------------------------------------ permutation null
def fold_permutation(tr_items: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """An item permutation that shuffles items WITHIN the training fold and WITHIN the test fold (the null arm of a permutation-
    matched comparison: the same extra features, the same distribution per fold, no alignment with the items)."""
    n = len(tr_items)
    perm = np.arange(n)
    for mask in (tr_items, ~tr_items):
        idx = np.flatnonzero(mask)
        perm[idx] = idx[rng.permutation(len(idx))]
    return perm


# ------------------------------------------------------------------------------------------------------------ 5.3 SMS
def eval_mediation(sysc: EvalSystem, items: list[TestItem], preds: dict[str, Prediction], n_boot: int = S.N_BOOT, seed: int = 0,
                   repeats: int = REPEATS) -> dict:
    """5.3: state mediation score (see the module docstring)."""
    use, dropped = _usable(items, preds, sysc)
    res: dict = {"n_items": len(use), "n_dropped_failed": dropped, "repeats": repeats}
    if len(use) < 8:
        res["note"] = "too few usable items"
        return res
    m = sysc.horizon_steps(PRIMARY)
    lags = sorted({max(1, int(round(m * j / N_LAGS))) for j in range(1, N_LAGS + 1)})
    sd = sysc.y_sd
    Z = np.stack([preds[it.item_id].z0 for it in use])
    U0 = np.stack([it.u_hist[-1] for it in use]).astype(np.float64)
    ZU = np.hstack([Z, U0])
    PC, sd_pc = _pcs(use, sysc)
    IDF, _ = id_features(use, sysc.horizon_s(PRIMARY))
    groups_item = np.array([it.group for it in use])
    rows_item, rows_lag, Y, YA = [], [], [], []
    for j, it in enumerate(use):
        p = preds[it.item_id]
        yp = p.y_base if p.abstain else p.y_int
        for L in lags:
            rows_item.append(j)
            rows_lag.append(L / m)
            Y.append(it.y_future[L] / sd)
            YA.append(yp[L] / sd)
    ri, rl = np.array(rows_item), np.array(rows_lag)[:, None]
    R = np.asarray(Y) - np.asarray(YA)
    groups = groups_item[ri]
    lag_oh = np.zeros((len(ri), len(lags)))
    lag_oh[np.arange(len(ri)), np.searchsorted(np.array(lags) / m, rl[:, 0])] = 1.0
    n_lag = lag_oh.shape[1]
    nf = n_rff(len(ri))
    arms = {"x_res+id": (True, True), "x_res": (True, False), "id": (False, True)}
    acc = {name: np.zeros((2, len(ri))) for name in arms}
    acc_raw = np.zeros(len(ri))
    n_rep_ok = 0
    for rep in range(repeats):
        fm = fold_masks(groups, rep, seed)
        if fm is None:
            break
        e_null = {name: np.zeros(len(ri)) for name in arms}
        e_arm = {name: np.zeros(len(ri)) for name in arms}
        ok = True
        for d, tr_m in enumerate(fm):
            te_m = ~tr_m
            if tr_m.sum() < 10 or te_m.sum() < 10:
                ok = False
                break
            # x_res per ITEM inside this fold (items are wholly in one fold because folds split by group)
            item_tr = np.isin(np.arange(len(use)), np.unique(ri[tr_m]))
            xr_tr, xr_te = residual_microstate(PC, ZU, groups_item, item_tr, sd_pc, seed + rep)
            XR = np.zeros((len(use), PC.shape[1]))
            XR[np.flatnonzero(item_tr)] = xr_tr
            XR[np.flatnonzero(~item_tr)] = xr_te
            perm = fold_permutation(item_tr, np.random.default_rng(seed + 5003 * rep + 17 * d))
            IDs = standardise(IDF)
            for arm_i, (name, (use_x, use_id)) in enumerate(arms.items()):
                x_items = XR if use_x else np.zeros((len(use), 0))
                id_items = IDs if use_id else np.zeros((len(use), 0))
                s_rff = seed + 7 + 1009 * rep + 101 * arm_i
                errs = []
                for order in (perm, np.arange(len(use))):          # null arm (permuted within folds), then the aligned arm
                    Ex, Ei = x_items[order][ri], id_items[order][ri]
                    rf = rff_raw(np.hstack([Ex, Ei, (rl - 0.5) * 2.0]), nf, np.random.default_rng(s_rff))
                    feats = np.hstack([lag_oh, Ex, Ex * rl, Ei, Ei * rl, rf])
                    # x_res columns keep the common scale (never re-standardised); the rest is standardised by the ridge
                    ks = np.r_[np.zeros(n_lag, bool), np.ones(2 * Ex.shape[1], bool), np.zeros(2 * Ei.shape[1] + rf.shape[1], bool)]
                    pr = ridge_cv_fit_predict(feats[tr_m], R[tr_m], feats[te_m], groups[tr_m], keep_scale=ks, seed=seed + rep,
                                              n_free=n_lag)
                    errs.append(((R[te_m] - pr) ** 2).mean(1))
                e_null[name][te_m], e_arm[name][te_m] = errs
        if not ok:
            continue
        n_rep_ok += 1
        for name in arms:
            acc[name][0] += e_null[name]
            acc[name][1] += e_arm[name]
        acc_raw += (R ** 2).mean(1)
    if n_rep_ok == 0:
        res["note"] = "too few groups for two folds"
        return res
    for name in arms:
        e1, e2 = acc[name][0] / n_rep_ok, acc[name][1] / n_rep_ok
        est = S.boot_gain(e1, e2, groups, n_boot, seed, ERR_FLOOR)
        key = "SMS" if name == "x_res+id" else f"SMS_{name.replace('+', '_')}"
        res[key] = {"point": est.point, "ci95": est.ci95, "err_A_null": float(e1.mean()), "err_B": float(e2.mean()), "n_groups": est.n_units}
        if name == "x_res+id":
            er = acc_raw / n_rep_ok
            est_raw = S.boot_gain(er, e2, groups, n_boot, seed + 1, ERR_FLOOR)
            res["SMS_raw"] = {"point": est_raw.point, "ci95": est_raw.ci95, "err_A_raw": float(er.mean())}
            res["_units"] = {"group": groups.tolist(), "e_A": e1.tolist(), "e_B": e2.tolist()}
    res["n_rows"] = len(ri)
    res["lags"] = lags
    return res


# ------------------------------------------------------------------------------------------------------------ 5.4 ICG
def eval_closure(model, sysc: EvalSystem, items: list[TestItem], preds: dict[str, Prediction], n_boot: int = S.N_BOOT, seed: int = 0,
                 repeats: int = REPEATS) -> dict:
    """5.4: interventional closure gain from the residual microstate, and the model's own interventional closure gap."""
    F = as_fresh(model)
    sid = sysc.system_id
    use, dropped = _usable(items, preds, sysc)
    res: dict = {"n_items": len(use), "n_dropped_failed": dropped, "repeats": repeats}
    m = sysc.horizon_steps(PRIMARY)
    if len(use) >= 8:
        Z = np.stack([preds[it.item_id].z0 for it in use])
        U0 = np.stack([it.u_hist[-1] for it in use]).astype(np.float64)
        UF = np.stack([np.concatenate([it.u_future[1: m + 1].mean(0), it.u_future[m]]) for it in use]).astype(np.float64)
        DESC = descriptor_features(use, sysc.horizon_s(PRIMARY))
        IDF, _ = id_features(use, sysc.horizon_s(PRIMARY))
        base = np.hstack([Z, U0, UF, DESC])
        n_base = base.shape[1]
        ZU = np.hstack([Z, U0])
        PC, sd_pc = _pcs(use, sysc)
        groups = np.array([it.group for it in use])
        targets = {f"y_h{PRIMARY}": np.stack([it.y_future[m] for it in use]) / sysc.y_sd}
        zlags = sorted({max(1, m // 2), m})
        if all(it.x_future is not None and len(it.x_future) > m for it in use):
            zf = {L: [] for L in zlags}
            ok = True
            for it in use:
                for L in zlags:
                    xh = np.vstack([it.x_hist, it.x_future[1: L + 1]])
                    uh = np.vstack([it.u_hist, it.u_future[1: L + 1]])
                    z, err = safe_call(F.encode, sid, xh, uh, it.dt)
                    if err or z is None or not np.isfinite(np.asarray(z, float)).all():
                        ok = False
                        break
                    zf[L].append(np.asarray(z, float).reshape(-1))
                if not ok:
                    break
            if ok:
                for L in zlags:
                    A = np.stack(zf[L])
                    targets[f"z_lag{L}"] = (A - A.mean(0)) / (A.std(0) + 1e-9)
            else:
                res["z_targets_note"] = "encoding of a future history failed"
        else:
            res["z_targets_note"] = "items carry no future microstate"
        nf = n_rff(len(use))
        n_pc = PC.shape[1]
        acc = {(name, kind): np.zeros((2, len(use))) for name in targets for kind in ("linear", "rff")}
        n_ok = {key: 0 for key in acc}
        bs = standardise(base)
        for rep in range(repeats):
            fm = fold_masks(groups, rep, seed)
            if fm is None:
                break
            s0 = seed + 7 + 1009 * rep
            rffb = rff_raw(bs, nf, np.random.default_rng(s0))
            errs = {key: [np.zeros(len(use)), np.zeros(len(use))] for key in acc}
            ok = True
            for d, tr_m in enumerate(fm):
                te_m = ~tr_m
                if tr_m.sum() < 5 or te_m.sum() < 5:
                    ok = False
                    break
                xr_tr, xr_te = residual_microstate(PC, ZU, groups, tr_m, sd_pc, seed + rep)
                XR = np.zeros((len(use), n_pc))
                XR[np.flatnonzero(tr_m)] = xr_tr
                XR[np.flatnonzero(~tr_m)] = xr_te
                perm = fold_permutation(tr_m, np.random.default_rng(seed + 5003 * rep + 17 * d))
                ks = np.r_[np.zeros(base.shape[1] + IDF.shape[1], bool), np.ones(n_pc, bool)]
                for name, Y in targets.items():
                    Y = Y[:, None] if Y.ndim == 1 else Y
                    Yc = Y - Y.mean(0)
                    for j, X_extra in enumerate((XR[perm], XR)):          # null arm (permuted within folds), then the aligned arm
                        X1 = np.hstack([base, IDF, X_extra])
                        p1 = ridge_cv_fit_predict(X1[tr_m], Yc[tr_m], X1[te_m], groups[tr_m], keep_scale=ks, seed=seed + rep,
                                                  n_free=n_base)
                        errs[(name, "linear")][j][te_m] = ((Yc[te_m] - p1) ** 2).mean(1)
                        rx = rff_raw(np.hstack([bs, X_extra]), nf, np.random.default_rng(s0 + 1))
                        X2 = np.hstack([base, IDF, rffb, X_extra, rx])
                        ks2 = np.r_[np.zeros(base.shape[1] + IDF.shape[1] + rffb.shape[1], bool), np.ones(n_pc, bool),
                                    np.zeros(rx.shape[1], bool)]
                        p2 = ridge_cv_fit_predict(X2[tr_m], Yc[tr_m], X2[te_m], groups[tr_m], keep_scale=ks2, seed=seed + rep,
                                                  n_free=n_base)
                        errs[(name, "rff")][j][te_m] = ((Yc[te_m] - p2) ** 2).mean(1)
            if not ok:
                continue
            for key in acc:
                acc[key][0] += errs[key][0]
                acc[key][1] += errs[key][1]
                n_ok[key] += 1
        for (name, kind), E in acc.items():
            if n_ok[(name, kind)] == 0:
                res[f"ICG_{name}_{kind}"] = {"note": "too few groups for two folds"}
                continue
            e1, e2 = E[0] / n_ok[(name, kind)], E[1] / n_ok[(name, kind)]
            est = S.boot_gain(e1, e2, groups, n_boot, seed, ERR_FLOOR)
            res[f"ICG_{name}_{kind}"] = {"point": est.point, "ci95": est.ci95, "err_null": float(e1.mean()), "err_xres": float(e2.mean())}
        prim = res.get(f"ICG_y_h{PRIMARY}_rff", {})
        res["ICG_y"] = {"point": prim.get("point", float("nan")), "ci95": prim.get("ci95", [float("nan")] * 2), "regressor": "rff"}
    else:
        res["note"] = "too few usable items"
    res["own_closure_gap"] = own_closure_gap(F, sysc, use, preds)
    return res


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
