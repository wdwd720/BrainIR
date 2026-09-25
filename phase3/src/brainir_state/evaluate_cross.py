"""Cross-model and cross-system evaluation (PROTOCOL.md section 4 families F, G, I, J; section 8 statistics).

Paired comparisons use the per-unit values that `evaluate.eval_predictive` / `eval_intervention` return under "_units" (unit = test
trajectory, keyed by its dataset key), so two models are always compared on exactly the same held-out data.

    G  reproducibility          models of one method fitted with different seeds: canonical correlations and linear cross-prediction
                                R^2 of their latent states (alignment FITTED on public validation data, MEASURED on hidden test data),
                                agreement of their predicted readouts, k agreement
    I  cross-mechanism          shared-dynamics model vs independent models on the systems of one group: paired differences in A and
                                C, parameter counts, leave-one-implementation-out (encoder-only adaptation vs from scratch)
    J  cross-connectome         the same rule for full systems of different networks
    F  dimension                selected k, range, k / N_obs, the evaluator's k-sweep
"""

from __future__ import annotations

import numpy as np

from .api import StateModel
from .data import Trajectory
from .evaluate import EvalConfig, _nmse, encode_at, idx, strip_units  # noqa: F401


# ------------------------------------------------------------------------------------------------------------ statistics
def _boot_p(b: np.ndarray, point: float) -> float:
    """Two-sided bootstrap p-value of H0: effect = 0: (1 + resamples on the other side of 0) / (1 + B), doubled, capped at 1."""
    b = np.asarray(b, float)
    b = b[np.isfinite(b)]
    if len(b) == 0 or not np.isfinite(point):
        return float("nan")
    cnt = int(np.sum(b <= 0)) if point > 0 else int(np.sum(b >= 0))
    return float(min(1.0, 2 * (1 + cnt) / (1 + len(b))))


def ni_p(b: np.ndarray, margin: float) -> float:
    """One-sided bootstrap p-value of the NON-INFERIORITY null H0: diff >= margin (diff = new - comparator on a lower-is-better
    metric): (1 + resamples with diff >= margin) / (1 + B). Uncomputable (no finite resample or margin) -> 1.0."""
    b = np.asarray(b, float)
    b = b[np.isfinite(b)]
    if len(b) == 0 or not np.isfinite(margin):
        return 1.0
    return float((1 + int(np.sum(b >= margin))) / (1 + len(b)))


def _ci(b) -> list[float]:
    b = np.asarray(b, float)
    b = b[np.isfinite(b)]
    return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))] if len(b) else [float("nan")] * 2


def paired_diff_boot(units_a: dict, units_b: dict, n_boot: int = 2000, seed: int = 0) -> tuple[float, np.ndarray, int]:
    """(mean of a - b over the common units, bootstrap replicates, n)."""
    keys = sorted(set(units_a) & set(units_b))
    d = np.array([units_a[k] - units_b[k] for k in keys], float)
    d = d[np.isfinite(d)]
    if len(d) == 0:
        return float("nan"), np.zeros(0), 0
    rng = np.random.default_rng(seed)
    b = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(n_boot)])
    return float(d.mean()), b, int(len(d))


def paired_diff(units_a: dict, units_b: dict, n_boot: int = 2000, seed: int = 0) -> dict:
    """Mean of (a - b) over the units both models were scored on (e.g. A NMSE per trajectory), bootstrap CI and p-value. Window
    errors are capped by the evaluator (evaluate.NMSE_CAP), so no unit is dropped for being non-finite."""
    m, b, n = paired_diff_boot(units_a, units_b, n_boot, seed)
    if n == 0:
        return {"diff": float("nan"), "ci95": [float("nan")] * 2, "n": 0, "p": float("nan")}
    return {"diff": m, "ci95": _ci(b), "n": n, "p": _boot_p(b, m)}


def paired_ratio_diff_boot(units_a: dict, units_b: dict, n_boot: int = 2000, seed: int = 0) -> tuple[float, np.ndarray, int, dict]:
    keys = sorted(set(units_a) & set(units_b))
    if not keys:
        return float("nan"), np.zeros(0), 0, {}
    na = np.array([units_a[k][0] for k in keys], float)
    nb = np.array([units_b[k][0] for k in keys], float)
    den = np.array([units_a[k][1] for k in keys], float)
    if den.sum() <= 0:
        return float("nan"), np.zeros(0), len(keys), {}
    rng = np.random.default_rng(seed)
    b = []
    for _ in range(n_boot):
        s = rng.integers(0, len(keys), len(keys))
        if den[s].sum() > 0:
            b.append((na[s].sum() - nb[s].sum()) / den[s].sum())
    extra = {"ratio_a": float(na.sum() / den.sum()), "ratio_b": float(nb.sum() / den.sum())}
    return float((na.sum() - nb.sum()) / den.sum()), np.array(b), len(keys), extra


def paired_ratio_diff(units_a: dict, units_b: dict, n_boot: int = 2000, seed: int = 0) -> dict:
    """Effect-error ratio difference: sum num_a / sum den - sum num_b / sum den on common units (den = the true effect, identical
    for both models); units are (num, den, post_nmse[, family]) tuples as returned by eval_intervention."""
    m, b, n, extra = paired_ratio_diff_boot(units_a, units_b, n_boot, seed)
    if not len(b):
        return {"diff": float("nan"), "ci95": [float("nan")] * 2, "n": n, "p": float("nan")}
    return {"diff": m, "ci95": _ci(b), "n": n, "p": _boot_p(b, m), **extra}


def paired_gain_diff_boot(units_a: dict, units_b: dict, n_boot: int = 2000, seed: int = 0) -> tuple[float, np.ndarray]:
    """D micro-gain difference a - b with a paired trajectory-cluster bootstrap. units: eval_closure's per-point errors
    ({"traj", "e_z", "e_micro"}); both models are evaluated on the same sampled points (the sampling depends only on the data and
    the evaluator seed)."""
    from .evaluate import _gain
    if not units_a or not units_b or units_a.get("traj") != units_b.get("traj"):
        return float("nan"), np.zeros(0)
    tid = np.asarray(units_a["traj"])
    ea = (np.asarray(units_a["e_z"], float), np.asarray(units_a["e_micro"], float))
    eb = (np.asarray(units_b["e_z"], float), np.asarray(units_b["e_micro"], float))
    ug, inv = np.unique(tid, return_inverse=True)
    sums = [np.bincount(inv, v) for v in (*ea, *eb)]
    cnt = np.bincount(inv).astype(float)
    point = _gain(ea[0].mean(), ea[1].mean()) - _gain(eb[0].mean(), eb[1].mean())
    rng = np.random.default_rng(seed)
    b = []
    for _ in range(n_boot):
        w = np.bincount(rng.integers(0, len(ug), len(ug)), minlength=len(ug)).astype(float)
        n = (w * cnt).sum()
        m = [(w * s).sum() / n for s in sums]
        b.append(_gain(m[0], m[1]) - _gain(m[2], m[3]))
    return float(point), np.array(b)


def paired_e_diff_boot(units_a: dict, units_b: dict, q: float, n_boot: int = 2000, seed: int = 0) -> tuple[float, np.ndarray]:
    """E ratio difference a - b on the same pool (the same pairs and futures; different latent distances), paired cluster bootstrap
    (pool trajectories within draw)."""
    from .evaluate import _matched_ratio, e_cluster_boot
    if not units_a or not units_b or units_a.get("div") != units_b.get("div"):
        return float("nan"), np.zeros(0)
    div = np.asarray(units_a["div"], float)
    da, db = np.asarray(units_a["d"], float), np.asarray(units_b["d"], float)
    ones = np.ones(len(div))
    point = _matched_ratio(div, da, ones, q, np.argsort(da, kind="stable")) - _matched_ratio(div, db, ones, q, np.argsort(db, kind="stable"))
    bo = e_cluster_boot(div, [da, db], np.asarray(units_a["ti"]), np.asarray(units_a["tj"]), np.asarray(units_a["traj_draw"]), q, n_boot, seed)
    return float(point), bo[:, 0] - bo[:, 1]


def holm(pvals: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni adjusted p-values over the WHOLE pre-registered family: a p-value that could not be computed (NaN) stays in
    the family as p = 1 (it can never be rejected and it is never dropped)."""
    items = sorted(((k, (float(v) if np.isfinite(v) else 1.0)) for k, v in pvals.items()), key=lambda kv: kv[1])
    m = len(items)
    out, running = {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


# ------------------------------------------------------------------------------------------------------------ latent samples
def latent_samples(model: StateModel, sid: str, trajs: list[Trajectory], times_s: tuple[float, ...] = (0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5),
                   ) -> tuple[np.ndarray, list[tuple[str, int]]]:
    """Encodings at fixed times of each trajectory: (n, k) and the (key, index) of every row."""
    Z, where = [], []
    for tr in trajs:
        for t in times_s:
            i = idx(t, tr.dt)
            if i < len(tr.t):
                Z.append(encode_at(model, sid, tr, i))
                where.append((tr.key, i))
    return (np.stack(Z) if Z else np.zeros((0, 0))), where


def _whiten(Z: np.ndarray, ridge: float = 1e-6) -> tuple[np.ndarray, np.ndarray]:
    mu = Z.mean(0)
    C = np.cov((Z - mu).T) if Z.shape[1] > 1 else np.array([[np.var(Z[:, 0])]])
    C = np.atleast_2d(C) + ridge * (np.trace(np.atleast_2d(C)) / max(1, Z.shape[1]) + 1e-12) * np.eye(Z.shape[1])
    w, V = np.linalg.eigh(C)
    return mu, V @ np.diag(1.0 / np.sqrt(np.maximum(w, 1e-12))) @ V.T


def cca_fit_apply(Za_fit, Zb_fit, Za_eval, Zb_eval) -> list[float]:
    """Canonical correlations: directions fitted on (Za_fit, Zb_fit), correlations measured on (Za_eval, Zb_eval)."""
    ma, Wa = _whiten(Za_fit)
    mb, Wb = _whiten(Zb_fit)
    A, B = (Za_fit - ma) @ Wa, (Zb_fit - mb) @ Wb
    U, _, Vt = np.linalg.svd(A.T @ B / len(A), full_matrices=False)
    r = min(Za_fit.shape[1], Zb_fit.shape[1])
    ca = ((Za_eval - ma) @ Wa @ U)[:, :r]
    cb = ((Zb_eval - mb) @ Wb @ Vt.T)[:, :r]
    out = []
    for j in range(r):
        a, b = ca[:, j] - ca[:, j].mean(), cb[:, j] - cb[:, j].mean()
        den = np.sqrt((a @ a) * (b @ b))
        out.append(float(abs(a @ b) / den) if den > 0 else float("nan"))
    return out


def cross_r2(Z_from_fit, Z_to_fit, Z_from_eval, Z_to_eval, ridge: float = 1e-3) -> float:
    """R^2 (variance-weighted) of a ridge map Z_from -> Z_to fitted on the fit set, measured on the eval set."""
    mu, sd = Z_from_fit.mean(0), Z_from_fit.std(0) + 1e-9
    A = (Z_from_fit - mu) / sd
    ym = Z_to_fit.mean(0)
    W = np.linalg.solve(A.T @ A + ridge * len(A) * np.eye(A.shape[1]), A.T @ (Z_to_fit - ym))
    P = ((Z_from_eval - mu) / sd) @ W + ym
    sst = float(((Z_to_eval - Z_to_eval.mean(0)) ** 2).sum())
    return float(1 - ((P - Z_to_eval) ** 2).sum() / sst) if sst > 0 else float("nan")


# ------------------------------------------------------------------------------------------------------------ G
def eval_reproducibility(models: list[StateModel], sid: str, val: list[Trajectory], test: list[Trajectory], scale: np.ndarray,
                         cfg: EvalConfig = EvalConfig(), horizon_s: float | None = None) -> dict:
    """G: all pairs of models (same method, different seeds). Alignment (CCA directions, ridge maps) is fitted on PUBLIC validation
    trajectories and measured on the hidden test trajectories (goal4 sections 44, 65). Latent states are sampled every half
    start-time spacing from the first start time on."""
    horizon_s = cfg.primary_horizon_s if horizon_s is None else horizon_s
    step = (cfg.start_times_s[1] - cfg.start_times_s[0]) / 2 if len(cfg.start_times_s) > 1 else cfg.start_times_s[0]
    t_last = min(float(tr.t[-1]) for tr in list(val) + list(test))
    times = tuple(float(t) for t in np.arange(cfg.start_times_s[0], t_last - 1e-9, step))
    Zv = [latent_samples(m, sid, val, times)[0] for m in models]
    Zt = [latent_samples(m, sid, test, times)[0] for m in models]
    ks = [int(z.shape[1]) for z in Zv]
    preds = []
    for m in models:
        rows = []
        for tr in test:
            for t0 in cfg.start_times_s:
                i0, n = idx(t0, tr.dt), idx(horizon_s, tr.dt)
                if i0 + n < len(tr.t):
                    z0 = encode_at(m, sid, tr, i0)
                    rows.append(np.asarray(m.rollout(sid, z0, tr.u[i0: i0 + n + 1], [], tr.dt)["y"], float)[1:])
        preds.append(rows)
    pairs = []
    for a in range(len(models)):
        for b in range(a + 1, len(models)):
            cc = cca_fit_apply(Zv[a], Zv[b], Zt[a], Zt[b])
            agree = [_nmse(pa, pb, scale) for pa, pb in zip(preds[a], preds[b])]
            pairs.append({"a": a, "b": b, "cca_mean": float(np.nanmean(cc)), "cca": cc,
                          "r2_a_to_b": cross_r2(Zv[a], Zv[b], Zt[a], Zt[b]), "r2_b_to_a": cross_r2(Zv[b], Zv[a], Zt[b], Zt[a]),
                          "prediction_disagreement_nmse": float(np.mean(agree)) if agree else float("nan")})
    return {"k": ks, "k_agree": len(set(ks)) == 1, "pairs": pairs,
            "cca_mean": float(np.nanmean([p["cca_mean"] for p in pairs])) if pairs else float("nan"),
            "r2_min_mean": float(np.nanmean([min(p["r2_a_to_b"], p["r2_b_to_a"]) for p in pairs])) if pairs else float("nan"),
            "prediction_disagreement_nmse": float(np.nanmean([p["prediction_disagreement_nmse"] for p in pairs])) if pairs else float("nan")}


# ------------------------------------------------------------------------------------------------------------ I / J
def n_params(model: StateModel, sids: list[str]) -> dict:
    """Parameter counts from the model's self-report: encoder + readout of the given systems + the transition law."""
    npar = (model.info() or {}).get("n_params") or {}
    enc = sum(int((npar.get("encoder") or {}).get(s, 0)) for s in sids)
    ro = sum(int((npar.get("readout") or {}).get(s, 0)) for s in sids)
    tr = int(npar.get("transition", 0) or 0)
    return {"encoder": enc, "readout": ro, "transition": tr, "total": enc + ro + tr, "reported": bool(npar)}


SHARING_A_MARGIN_REL = 0.2      # non-inferiority margins of the sharing rule (PROTOCOL.md section 7, version 2)
SHARING_C_MARGIN_REL = 0.2
SHARING_C_MARGIN_MIN = 0.05


def sharing_comparison(shared_res: dict[str, dict], indep_res: dict[str, dict], shared_params: dict, indep_params: dict,
                       tau_a: float | None = None, *, a_key: str, c_key: str, n_boot: int = 2000, seed: int = 0) -> dict:
    """I / J (PROTOCOL.md section 7): per system, paired differences shared - independent in A (per trajectory) and C (effect error on
    held-out intervention pairs). Non-inferiority (version 2, margins on the scale of the quantities): the upper CI of the A
    difference <= 0.2 x the independent model's A; the upper CI of the C difference <= max(0.05, 0.2 x the independent model's C).
    `tau_a` is accepted for compatibility and not used (version 1 used tau_A as the A margin). shared_res / indep_res: {system_id:
    {"A": eval_predictive result, "C": eval_intervention result}} (with "_units")."""
    per = {}
    ok_all = True
    for sid in sorted(set(shared_res) & set(indep_res)):
        sa, ia = shared_res[sid].get("A") or {}, indep_res[sid].get("A") or {}
        da = paired_diff((sa.get("_units") or {}).get(a_key, {}), (ia.get("_units") or {}).get(a_key, {}), n_boot, seed)
        a_ind = (ia.get(a_key) or {}).get("mean", float("nan"))
        a_margin = SHARING_A_MARGIN_REL * a_ind
        a_ok = bool(np.isfinite(da["ci95"][1]) and np.isfinite(a_margin) and da["ci95"][1] <= a_margin)
        sc, ic = shared_res[sid].get("C") or {}, indep_res[sid].get("C") or {}
        dc = paired_ratio_diff((sc.get("_units") or {}).get(c_key, {}), (ic.get("_units") or {}).get(c_key, {}), n_boot, seed)
        c_ind = dc.get("ratio_b", float("nan"))
        c_margin = max(SHARING_C_MARGIN_MIN, SHARING_C_MARGIN_REL * c_ind) if np.isfinite(c_ind) else SHARING_C_MARGIN_MIN
        c_ok = bool(dc["n"] == 0 or (np.isfinite(dc["ci95"][1]) and dc["ci95"][1] <= c_margin))
        per[sid] = {"A_diff": da, "A_independent": a_ind, "A_margin": a_margin, "A_noninferior": a_ok, "C_diff": dc, "C_margin": c_margin,
                    "C_noninferior": c_ok}
        ok_all = ok_all and a_ok and c_ok
    fewer = shared_params["total"] < indep_params["total"] if shared_params["reported"] and indep_params["reported"] else None
    return {"per_system": per, "noninferior_all": ok_all, "shared_params": shared_params, "independent_params": indep_params,
            "fewer_parameters": fewer}


def loio_comparison(adapted_res: dict, scratch_res: dict, *, a_key: str, c_key: str, n_boot: int = 2000, seed: int = 0) -> dict:
    """Leave-one-implementation-out (goal4 section 19): encoder-only adaptation to a held-out implementation (f frozen, fitted on the
    other implementations) vs a from-scratch model on the SAME limited data of the held-out implementation. Negative differences
    favour the adapted model."""
    da = paired_diff((adapted_res.get("A") or {}).get("_units", {}).get(a_key, {}), (scratch_res.get("A") or {}).get("_units", {}).get(a_key, {}),
                     n_boot, seed)
    dc = paired_ratio_diff((adapted_res.get("C") or {}).get("_units", {}).get(c_key, {}), (scratch_res.get("C") or {}).get("_units", {}).get(c_key, {}),
                           n_boot, seed)
    beats = bool(np.isfinite(da["ci95"][1]) and da["ci95"][1] < 0) or bool(dc["n"] and np.isfinite(dc["ci95"][1]) and dc["ci95"][1] < 0)
    worse = bool(np.isfinite(da["ci95"][0]) and da["ci95"][0] > 0) or bool(dc["n"] and np.isfinite(dc["ci95"][0]) and dc["ci95"][0] > 0)
    return {"A_diff": da, "C_diff": dc, "adapted_beats_scratch": beats and not worse, "adapted_worse": worse}


def sharing_verdict(comparison: dict, loio: list[dict] | None) -> str:
    """'supported' when the shared model is non-inferior on A and C with fewer parameters AND encoder-only adaptation beats a
    from-scratch model for at least half of the held-out implementations (and is worse for none); 'rejected' otherwise;
    'untestable' when the method cannot fit shared dynamics or parameter counts are missing."""
    if comparison is None or comparison.get("fewer_parameters") is None:
        return "untestable"
    if loio is not None and len(loio) == 0:
        return "untestable"          # no leave-one-implementation-out result (e.g. the method cannot adapt an encoder)
    loio_ok = bool(loio) and sum(r["adapted_beats_scratch"] for r in loio) * 2 >= len(loio) and not any(r["adapted_worse"] for r in loio)
    return "supported" if (comparison["noninferior_all"] and comparison["fewer_parameters"] and loio_ok) else "rejected"


# ------------------------------------------------------------------------------------------------------------ selection (PROTOCOL.md section 9)
PROFILE_KEYS = ("S1_A_over_full", "S2_C_heldout", "S3_D_micro_gain", "S4_E_ratio", "S5_K_r2_rff", "S6_dim_rate", "S7_abstention",
                "S8_sharing_correct")
LOWER_IS_BETTER = {"S1_A_over_full", "S2_C_heldout", "S3_D_micro_gain", "S4_E_ratio"}


def _worst(key: str) -> float:
    return float("inf") if key in LOWER_IS_BETTER else float("-inf")


def system_values(per_sys: dict, sid: str) -> dict:
    """The per-system quantities behind S1-S6 for one method's per-system record (tournament format); a failed fit / evaluation or a
    non-finite value is imputed as the WORST value (version 2: a failure never improves a median)."""
    r = per_sys.get(sid) or {}
    v = r.get("verdict") or {}

    def val(x, key):
        try:
            x = float(x)
        except (TypeError, ValueError):
            return _worst(key)
        return x if np.isfinite(x) else _worst(key)

    e = v.get("E_ratio")
    if v and v.get("E_testable") is False:
        e = None                                        # untestable: not a value of the method (left out of S4, never imputed)
    return {"S1_A_over_full": val(r.get("A_over_full"), "S1_A_over_full"),
            "S2_C_heldout": val(v.get("C"), "S2_C_heldout"),
            "S3_D_micro_gain": val(v.get("D_micro_gain"), "S3_D_micro_gain"),
            "S4_E_ratio": (val(e, "S4_E_ratio") if (e is not None or not v) else None),
            "S5_K_r2_rff": val((r.get("K") or {}).get("r2_true_from_model_rff"), "S5_K_r2_rff"),
            "S6_dim_ok": bool((r.get("K_dim") or {}).get("in_range"))}


def profile_from_systems(per_sys: dict, compressible: list[str], abstention: dict, i_rows: list[dict]) -> dict:
    """S1-S8 over the FIXED list of the suite's compressible systems (paired across methods; failures imputed as worst values).
    S4 leaves out the systems where the method's E is untestable (reported as a count). S7 from the abstention summary
    (abstention_recall, false_alarm_rate). S8 = balanced accuracy of the sharing verdicts: the mean of the correct rates over the
    implementation groups and over the unrelated pairs."""
    vals = [system_values(per_sys, s) for s in compressible]

    def med(key):
        x = [v[key] for v in vals if v[key] is not None]
        return float(np.median(x)) if x else float("nan")

    ls = abstention or {}
    s7 = [x for x in (ls.get("abstention_recall"), (1 - ls["false_alarm_rate"]) if ls.get("false_alarm_rate") is not None else None)
          if x is not None and np.isfinite(x)]
    groups = [r for r in i_rows if r.get("kind") == "group"]
    pairs = [r for r in i_rows if r.get("kind") == "pair"]
    rates = [float(np.mean([bool(r.get("correct")) for r in x])) for x in (groups, pairs) if x]
    return {"S1_A_over_full": med("S1_A_over_full"), "S2_C_heldout": med("S2_C_heldout"), "S3_D_micro_gain": med("S3_D_micro_gain"),
            "S4_E_ratio": med("S4_E_ratio"), "S5_K_r2_rff": med("S5_K_r2_rff"),
            "S6_dim_rate": float(np.mean([v["S6_dim_ok"] for v in vals])) if vals else float("nan"),
            "S7_abstention": float(np.mean(s7)) if s7 else float("nan"),
            "S8_sharing_correct": float(np.mean(rates)) if rates else float("nan"),
            "n_systems": len(vals), "n_E_untestable": sum(1 for v in vals if v["S4_E_ratio"] is None)}


def rank_profiles(profiles: dict[str, dict], transition_params: dict[str, float] | None = None) -> dict:
    """Mean rank over S1-S8 (PROTOCOL.md section 9, version 2): average ranks for ties; a non-finite value ranks last (tied with the
    other non-finite values); a component that is non-finite for EVERY candidate is dropped; ties in the mean rank are broken by
    fewer transition parameters, then by name. The result does not depend on the order of the candidates."""
    from scipy.stats import rankdata
    names = sorted(profiles)
    used, ranks = [], {m: [] for m in names}
    for key in PROFILE_KEYS:
        v = np.array([float(profiles[m].get(key, float("nan"))) for m in names], float)
        if not np.isfinite(v).any():
            continue
        used.append(key)
        s = np.where(np.isfinite(v), v if key in LOWER_IS_BETTER else -v, np.inf)
        for m, r in zip(names, rankdata(s, method="average")):
            ranks[m].append(float(r))
    mean = {m: (float(np.mean(ranks[m])) if ranks[m] else float("nan")) for m in names}
    tp = transition_params or {}
    order = sorted(names, key=lambda m: (mean[m], float(tp.get(m, np.inf)) if np.isfinite(tp.get(m, np.inf)) else np.inf, m))
    return {"mean_rank": mean, "order": order, "components_used": used, "ranks": ranks}


def selection_bootstrap(per_method: dict[str, dict], compressible: list[str], n_boot: int = 1000, seed: int = 0,
                        eliminate_fraction: float | None = None, transition_params: dict | None = None) -> dict:
    """Uncertainty of the selection (review E M5): resample the systems with replacement, recompute S1-S6 (S7 and S8 are kept at
    their point values: they rest on few rows), re-rank. per_method: {method: {"per_system", "abstention_rows", "i_rows", "profile"}}.
    Returns per method P(rank 1), the 5-95 % interval of its rank and, with eliminate_fraction, P(eliminated)."""
    rng = np.random.default_rng(seed)
    names = sorted(per_method)
    first = {m: 0 for m in names}
    elim = {m: 0 for m in names}
    pos = {m: [] for m in names}
    cut = None if eliminate_fraction is None else len(names) - int(np.floor(len(names) * eliminate_fraction))
    for _ in range(n_boot):
        s = [compressible[i] for i in rng.integers(0, len(compressible), len(compressible))]
        profs = {}
        for m in names:
            pm = per_method[m]
            vals = [system_values(pm["per_system"], sid) for sid in s]
            p = dict(pm["profile"])
            for key in ("S1_A_over_full", "S2_C_heldout", "S3_D_micro_gain", "S4_E_ratio", "S5_K_r2_rff"):
                x = [v[key] for v in vals if v[key] is not None]
                p[key] = float(np.median(x)) if x else float("nan")
            p["S6_dim_rate"] = float(np.mean([v["S6_dim_ok"] for v in vals]))
            profs[m] = p
        order = rank_profiles(profs, transition_params)["order"]
        first[order[0]] += 1
        for r, m in enumerate(order):
            pos[m].append(r + 1)
            if cut is not None and r + 1 > cut:
                elim[m] += 1
    out = {m: {"p_rank1": first[m] / n_boot, "rank_p05": float(np.percentile(pos[m], 5)), "rank_p95": float(np.percentile(pos[m], 95))}
           for m in names}
    if cut is not None:
        for m in names:
            out[m]["p_eliminated"] = elim[m] / n_boot
    return out


# ------------------------------------------------------------------------------------------------------------ F
def dimension_summary(model: StateModel, sid: str, n_observed: int) -> dict:
    info = model.info() or {}
    k = (info.get("k") or {}).get(sid)
    rng = (info.get("k_range") or {}).get(sid)
    ab = (info.get("abstain") or {}).get(sid) or {}
    return {"k": k, "k_range": rng, "n_observed": int(n_observed), "compression": (float(k) / n_observed if k and n_observed else None),
            "abstain": ab, "lipschitz_bound": info.get("lipschitz_bound")}
