"""Dimension stability and representation stability (benchmarks/causal_state_v1/PROTOCOL.md sections 5.10-5.11; goal5 sections 35-37).

5.10 DIMENSION
    `bootstrap_interventions(records, n, seed)`   training sets for the dimension-stability refits: the INTERVENTION items (an
                                                  intervention record together with its twin) resampled with replacement, passive
                                                  records kept (a resampled item appears once per draw; a duplicated record is
                                                  copied under a suffixed key so methods see distinct records)
    `dimension_stability(ks, k_range, ...)`       STABLE when the modal k occurs in >= 4 of 5 refits (generally >= 80 %), every refit
                                                  selected a k, and every k lies in the method's reported plausible range (no range
                                                  reported: every k equals the modal k, as `verdict.dimension_status`); otherwise
                                                  "dimension unresolved: min-max". Also k = k_true and k_true within the range
                                                  (synthetic), and COMPACT:
                                                  k <= max(1, N_obs / 5) for full-network and synthetic systems (mechanisms: None, judged
                                                  on the other conditions)

5.11 REPRESENTATION STABILITY (all pairs of fitted models of one method: seeds, bootstrap refits)
    latents are sampled at fixed times of the validation (fit) and test (measure) trajectories; linear maps are FITTED on validation
    data and MEASURED on test data:
    - cross-prediction R^2 in both directions (ridge), the smaller one (r2_min) is the headline;
    - mean canonical correlation PADDED with zeros up to max(k_a, k_b) (a smaller latent is otherwise always found in a larger one);
    - Procrustes residual: orthogonal Procrustes between the two WHITENED latents (padded to a common dimension) after centring,
      residual sum of squares / total, and the affine-map residual 1 - R^2(a -> b);
    - predicted-effect disagreement: sum ||e_a - e_b||^2 / max(sum ||e_true||^2, n f^2) over test intervention items (effects from
      `intervention_effect` with the item's history and events), i.e. relative to the true effect size with the system's floor;
    - vector-field similarity: for test states, each model's passive latent flow over the short horizon (rollout without events),
      the flow of a mapped through the fitted affine map a -> b against the flow of b: 1 - SSE / SST (R^2) and the mean cosine.
All model calls run on fresh copies (`brainir_causal.fresh`).
"""

from __future__ import annotations

import copy
from collections import Counter

import numpy as np

from .fresh import as_fresh, safe_call

STABLE_FRACTION = 0.8


# ------------------------------------------------------------------------------------------------------------ 5.10
def _get(rec, name, default=None):
    return rec.get(name, default) if isinstance(rec, dict) else getattr(rec, name, default)


def intervention_items(records: list) -> tuple[list[list], list]:
    """([intervention record, its twin(s)] per item, passive records that are no twin of any intervention record)."""
    keys = {str(_get(r, "key")): r for r in records}
    twins: dict[str, list] = {}
    for r in records:
        tw = (_get(r, "meta") or {}).get("twin_of")
        if tw:
            twins.setdefault(str(tw), []).append(r)
    items, used = [], set()
    for r in records:
        if (_get(r, "protocol") or {}).get("events"):
            k = str(_get(r, "key"))
            grp = [r] + twins.get(k, [])
            items.append(grp)
            used |= {id(x) for x in grp}
    passive = [r for r in records if id(r) not in used and not (_get(r, "meta") or {}).get("twin_of")]
    passive += [r for r in records if id(r) not in used and (_get(r, "meta") or {}).get("twin_of") and str((_get(r, "meta") or {})["twin_of"]) not in keys]
    return items, passive


def _renamed(rec, suffix: str):
    """A copy of a record under key + suffix (twin links renamed consistently)."""
    if isinstance(rec, dict):
        r2 = dict(rec)
        r2["key"] = f"{rec['key']}{suffix}"
        meta = dict(rec.get("meta") or {})
        if meta.get("twin_of"):
            meta["twin_of"] = f"{meta['twin_of']}{suffix}"
        r2["meta"] = meta
        return r2
    r2 = copy.copy(rec)
    r2.key = f"{rec.key}{suffix}"
    meta = dict(rec.meta or {})
    if meta.get("twin_of"):
        meta["twin_of"] = f"{meta['twin_of']}{suffix}"
    r2.meta = meta
    return r2


def bootstrap_interventions(records: list, n: int = 5, seed: int = 0) -> list[list]:
    """n training sets: intervention items resampled with replacement (passive records kept)."""
    items, passive = intervention_items(records)
    rng = np.random.default_rng(seed)
    out = []
    for b in range(n):
        draw = rng.integers(0, len(items), len(items)) if items else np.zeros(0, int)
        seen: Counter = Counter()
        recs = list(passive)
        for i in draw:
            c = seen[int(i)]
            seen[int(i)] += 1
            recs += [x if c == 0 else _renamed(x, f"~b{b}r{c}") for x in items[int(i)]]
        out.append(recs)
    return out


def dimension_stability(ks: list[int | None], k_range: list[int] | tuple[int, int] | None = None, *, k_true: int | str | None = None,
                        n_obs: int | None = None, mode: str = "synthetic") -> dict:
    """PROTOCOL 5.10 on the selected k of each refit (None = the method abstained / failed on that refit). mode: 'synthetic', 'full'
    or 'mech' (mechanisms are judged on the other conditions: compact None)."""
    vals = [int(k) for k in ks if k is not None]
    n = len(ks)
    out: dict = {"ks": [None if k is None else int(k) for k in ks], "n_refits": n, "n_valid": len(vals), "k_range": k_range}
    if not vals:
        out.update(stable=False, verdict="dimension unresolved: no refit selected a dimension", modal_k=None, modal_fraction=0.0)
        return out
    modal, cnt = Counter(vals).most_common(1)[0]
    frac = cnt / n
    # without a reported range the range is the point k (the same reading as verdict.dimension_status)
    in_range = all(k == modal for k in vals) if k_range is None else all(k_range[0] <= k <= k_range[1] for k in vals)
    stable = bool(frac >= STABLE_FRACTION - 1e-12 and in_range and len(vals) == n)
    out.update(modal_k=int(modal), modal_fraction=float(frac), all_in_range=bool(in_range), stable=stable,
               verdict=f"stable: k = {modal}" if stable else f"dimension unresolved: {min(vals)}-{max(vals)}")
    if k_true is not None and k_true != "none":
        kt = int(k_true)
        out["k_true"] = kt
        out["modal_equals_true"] = bool(modal == kt)
        out["true_in_range"] = None if k_range is None else bool(k_range[0] <= kt <= k_range[1])
    if mode == "mech":
        out["compact"] = None
    elif n_obs is not None:
        out["compact"] = bool(modal <= max(1, n_obs / 5.0))
    return out


# ------------------------------------------------------------------------------------------------------------ latent samples
def _dt(rec) -> float:
    t = np.asarray(_get(rec, "t"), float)
    return float(t[1] - t[0]) if len(t) > 1 else float(_get(rec, "protocol")["dt"])


def latent_samples(model, sid: str, records: list, n_times: int = 8, t_min_frac: float = 0.15) -> tuple[np.ndarray, list]:
    """Encodings at n_times evenly spaced samples of each record: (n, k) (rows with failed / non-finite encodings dropped) and the
    (record index, sample) of each row. The SAME sample positions are used for every model (they depend only on the records)."""
    F = as_fresh(model)
    Z, where = [], []
    for ri, r in enumerate(records):
        x, u = np.asarray(_get(r, "x")), np.asarray(_get(r, "u"))
        T = len(x)
        for i in np.unique(np.linspace(max(1, int(t_min_frac * T)), T - 1, n_times).astype(int)):
            z, err = safe_call(F.encode, sid, x[: i + 1], u[: i + 1], _dt(r))
            if err is None and z is not None and np.all(np.isfinite(z)):
                Z.append(np.asarray(z, float))
                where.append((ri, int(i)))
    return (np.stack(Z) if Z else np.zeros((0, 0))), where


def _common(Za, wa, Zb, wb):
    """Rows present for both models (same record and sample)."""
    ia = {w: i for i, w in enumerate(wa)}
    ib = {w: i for i, w in enumerate(wb)}
    keys = [w for w in wa if w in ib]
    return Za[[ia[w] for w in keys]], Zb[[ib[w] for w in keys]]


def _whiten(Z: np.ndarray, floor: float = 1e-8) -> tuple[np.ndarray, np.ndarray]:
    mu = Z.mean(0)
    C = np.atleast_2d(np.cov((Z - mu).T)) if Z.shape[1] > 1 else np.array([[np.var(Z[:, 0])]])
    w, V = np.linalg.eigh(C)
    w = np.maximum(w, floor * max(float(w.max()), 1e-300))
    return mu, V @ np.diag(1.0 / np.sqrt(w)) @ V.T


def cross_r2(Z_from_fit, Z_to_fit, Z_from_eval, Z_to_eval, ridge: float = 1e-3) -> float:
    """Variance-weighted R^2 of a ridge map Z_from -> Z_to fitted on the fit set, measured on the eval set."""
    if len(Z_from_fit) < 3 or len(Z_from_eval) < 2:
        return float("nan")
    mu, sd = Z_from_fit.mean(0), Z_from_fit.std(0) + 1e-9
    A = (Z_from_fit - mu) / sd
    ym = Z_to_fit.mean(0)
    W = np.linalg.solve(A.T @ A + ridge * len(A) * np.eye(A.shape[1]), A.T @ (Z_to_fit - ym))
    Pr = ((Z_from_eval - mu) / sd) @ W + ym
    sst = float(((Z_to_eval - Z_to_eval.mean(0)) ** 2).sum())
    return float(1 - ((Pr - Z_to_eval) ** 2).sum() / sst) if sst > 0 else float("nan")


def affine_map(Z_from: np.ndarray, Z_to: np.ndarray, ridge: float = 1e-6) -> tuple[np.ndarray, np.ndarray]:
    """Least-squares affine map z_to ~ z_from @ M + c (tiny ridge)."""
    X = np.hstack([Z_from, np.ones((len(Z_from), 1))])
    W = np.linalg.solve(X.T @ X + ridge * len(X) * np.eye(X.shape[1]), X.T @ Z_to)
    return W[:-1], W[-1]


def cca_padded(Za_fit, Zb_fit, Za_eval, Zb_eval) -> dict:
    """Canonical correlations: directions fitted on the fit set, measured on the eval set; padded with zeros to max(k_a, k_b)."""
    ma, Wa = _whiten(Za_fit)
    mb, Wb = _whiten(Zb_fit)
    A, B = (Za_fit - ma) @ Wa, (Zb_fit - mb) @ Wb
    U, _, Vt = np.linalg.svd(A.T @ B / len(A), full_matrices=False)
    r = min(Za_fit.shape[1], Zb_fit.shape[1])
    ca = ((Za_eval - ma) @ Wa @ U)[:, :r]
    cb = ((Zb_eval - mb) @ Wb @ Vt.T)[:, :r]
    cc = []
    for j in range(r):
        a, b = ca[:, j] - ca[:, j].mean(), cb[:, j] - cb[:, j].mean()
        den = np.sqrt((a @ a) * (b @ b))
        cc.append(float(abs(a @ b) / den) if den > 0 else 0.0)
    padded = cc + [0.0] * (max(Za_fit.shape[1], Zb_fit.shape[1]) - r)
    return {"cca": cc, "cca_mean_padded": float(np.mean(padded)) if padded else float("nan"),
            "cca_mean_unpadded": float(np.mean(cc)) if cc else float("nan")}


def procrustes_residual(Za_fit, Zb_fit, Za_eval, Zb_eval) -> dict:
    """Orthogonal Procrustes between the WHITENED latents (whitening and rotation fitted on the fit set, zero-padded to a common
    dimension), residual SS / total SS on the eval set; plus the affine-map residual 1 - R^2(a -> b) on the eval set."""
    ma, Wa = _whiten(Za_fit)
    mb, Wb = _whiten(Zb_fit)
    k = max(Za_fit.shape[1], Zb_fit.shape[1])

    def pad(M):
        return np.hstack([M, np.zeros((len(M), k - M.shape[1]))])

    A, B = pad((Za_fit - ma) @ Wa), pad((Zb_fit - mb) @ Wb)
    U, _, Vt = np.linalg.svd(A.T @ B)
    R = U @ Vt
    Ae, Be = pad((Za_eval - ma) @ Wa), pad((Zb_eval - mb) @ Wb)
    ss = float(((Ae @ R - Be) ** 2).sum())
    tot = float(((Be - Be.mean(0)) ** 2).sum())
    M, c = affine_map(Za_fit, Zb_fit)
    Pe = Za_eval @ M + c
    sst = float(((Zb_eval - Zb_eval.mean(0)) ** 2).sum())
    return {"procrustes_residual": ss / tot if tot > 0 else float("nan"),
            "affine_residual": float(((Pe - Zb_eval) ** 2).sum() / sst) if sst > 0 else float("nan")}


# ------------------------------------------------------------------------------------------------------------ effects and flows
def _items(records: list) -> list[tuple]:
    """(intervention record, its twin, onset index, relative events) for every intervention record with a twin."""
    by = {str(_get(r, "key")): r for r in records}
    out = []
    for r in records:
        tw = (_get(r, "meta") or {}).get("twin_of")
        if not tw or str(tw) not in by:
            continue
        ri = by[str(tw)]
        ev = list((_get(ri, "protocol") or {}).get("events") or [])
        if not ev:
            continue
        dt = _dt(ri)
        t0 = min(float(e["t"] if "t" in e else e["t0"]) for e in ev)
        rel = []
        for e in ev:
            e2 = dict(e)
            for key in ("t", "t0"):
                if key in e2 and e2[key] is not None:
                    e2[key] = float(e2[key]) - t0
            if e2.get("t1") is not None:
                e2["t1"] = float(e2["t1"]) - t0
            rel.append(e2)
        out.append((ri, r, round(t0 / dt), rel))
    return out


def predicted_effects(model, sid: str, records: list, horizon_s: float) -> dict:
    """{intervention key: predicted effect (n_h, n_y)} over the horizon after onset (None when the call fails or abstains)."""
    F = as_fresh(model)
    out = {}
    for ri, _tw, i0, rel in _items(records):
        dt = _dt(ri)
        n_h = max(1, round(horizon_s / dt))
        x, u = np.asarray(_get(ri, "x")), np.asarray(_get(ri, "u"))
        if i0 + n_h >= len(x):
            continue
        res, err = safe_call(F.intervention_effect, sid, x[: i0 + 1], u[: i0 + 1], u[i0: i0 + n_h + 1], rel, dt)
        out[str(_get(ri, "key"))] = None if (err or res is None) else np.asarray(res["effect"], float)[1: n_h + 1]
    return out


def effect_disagreement(eff_a: dict, eff_b: dict, records: list, horizon_s: float, floor: float) -> dict:
    """sum ||e_a - e_b||^2 / max(sum ||e_true||^2, n f^2) over the common, finite items."""
    num = den = 0.0
    n = 0
    for ri, tw, i0, _rel in _items(records):
        k = str(_get(ri, "key"))
        ea, eb = eff_a.get(k), eff_b.get(k)
        if ea is None or eb is None or ea.shape != eb.shape or not (np.all(np.isfinite(ea)) and np.all(np.isfinite(eb))):
            continue
        n_h = len(ea)
        et = np.asarray(_get(ri, "y"), float)[i0 + 1: i0 + n_h + 1] - np.asarray(_get(tw, "y"), float)[i0 + 1: i0 + n_h + 1]
        num += float(np.sum((ea - eb) ** 2))
        den += float(max(np.sum(et ** 2), et.size * floor ** 2))
        n += 1
    return {"disagreement": num / den if den > 0 else float("nan"), "n_items": n}


def latent_flows(model, sid: str, records: list, where: list, horizon_s: float) -> np.ndarray:
    """Passive latent flow z(t + h) - z(t) from each sampled state (rollout without events on the record's own future input)."""
    F = as_fresh(model)
    out = []
    for ri, i in where:
        r = records[ri]
        dt = _dt(r)
        n_h = max(1, round(horizon_s / dt))
        x, u = np.asarray(_get(r, "x")), np.asarray(_get(r, "u"))
        uf = u[i: i + n_h + 1]
        if len(uf) < n_h + 1:
            uf = np.vstack([uf, np.repeat(uf[-1:], n_h + 1 - len(uf), 0)])
        z0, e1 = safe_call(F.encode, sid, x[: i + 1], u[: i + 1], dt)
        ro, e2 = (safe_call(F.rollout, sid, z0, uf, [], dt) if e1 is None else (None, e1))
        if e2 is None and ro is not None:
            Z = np.asarray(ro["z"], float)
            out.append(Z[-1] - Z[0])
        else:
            out.append(np.full(np.shape(z0) if z0 is not None else (1,), np.nan))
    return np.stack(out) if out else np.zeros((0, 0))


def vector_field_similarity(Fa: np.ndarray, Fb: np.ndarray, M: np.ndarray) -> dict:
    """Flows of a mapped by the linear part M of the affine map a -> b against the flows of b on the same states."""
    ok = np.all(np.isfinite(Fa), 1) & np.all(np.isfinite(Fb), 1)
    if ok.sum() < 3:
        return {"r2": float("nan"), "cos_mean": float("nan"), "n": int(ok.sum())}
    A, B = Fa[ok] @ M, Fb[ok]
    sst = float(((B - B.mean(0)) ** 2).sum())
    num = np.sum(A * B, 1)
    den = np.linalg.norm(A, axis=1) * np.linalg.norm(B, axis=1)
    cos = num[den > 0] / den[den > 0]
    return {"r2": float(1 - ((A - B) ** 2).sum() / sst) if sst > 0 else float("nan"),
            "cos_mean": float(np.mean(cos)) if len(cos) else float("nan"), "n": int(ok.sum())}


def representation_stability(models: list, sid: str, val: list, test: list, *, horizon_short_s: float, horizon_s: float,
                             floor: float, n_times: int = 8) -> dict:
    """PROTOCOL 5.11 over all pairs of models (seeds / refits of one method). val: public validation records (maps are fitted
    here); test: held-out records (measured here; intervention records need their twins for the effect disagreement)."""
    Zv = [latent_samples(m, sid, val, n_times) for m in models]
    Zt = [latent_samples(m, sid, test, n_times) for m in models]
    ks = [int(z[0].shape[1]) if z[0].size else None for z in Zv]
    effs = [predicted_effects(m, sid, test, horizon_s) for m in models]
    flows = [latent_flows(m, sid, test, Zt[i][1], horizon_short_s) for i, m in enumerate(models)]
    pairs = []
    for a in range(len(models)):
        for b in range(a + 1, len(models)):
            row: dict = {"a": a, "b": b, "k_a": ks[a], "k_b": ks[b]}
            if ks[a] is None or ks[b] is None:
                row["error"] = "no encodable validation sample"
                pairs.append(row)
                continue
            Zva, Zvb = _common(Zv[a][0], Zv[a][1], Zv[b][0], Zv[b][1])
            Zta, Ztb = _common(Zt[a][0], Zt[a][1], Zt[b][0], Zt[b][1])
            if len(Zva) < 5 or len(Zta) < 3:
                row["error"] = "too few common latent samples"
                pairs.append(row)
                continue
            row["r2_a_to_b"] = cross_r2(Zva, Zvb, Zta, Ztb)
            row["r2_b_to_a"] = cross_r2(Zvb, Zva, Ztb, Zta)
            row["r2_min"] = float(np.nanmin([row["r2_a_to_b"], row["r2_b_to_a"]]))
            row.update(cca_padded(Zva, Zvb, Zta, Ztb))
            row.update(procrustes_residual(Zva, Zvb, Zta, Ztb))
            row.update(effect_disagreement(effs[a], effs[b], test, horizon_s, floor))
            M, _ = affine_map(Zva, Zvb)
            ia = {w: i for i, w in enumerate(Zt[a][1])}
            ib = {w: i for i, w in enumerate(Zt[b][1])}
            common = [w for w in Zt[a][1] if w in ib]
            if common and flows[a].size and flows[b].size:
                vf = vector_field_similarity(flows[a][[ia[w] for w in common]], flows[b][[ib[w] for w in common]], M)
                row.update({f"flow_{k}": v for k, v in vf.items()})
            pairs.append(row)

    def mean(key):
        v = [p[key] for p in pairs if key in p and p[key] is not None and np.isfinite(p[key])]
        return float(np.mean(v)) if v else float("nan")

    return {"k": ks, "k_agree": len({k for k in ks if k is not None}) == 1 and None not in ks, "pairs": pairs,
            "r2_min_mean": mean("r2_min"), "cca_mean_padded": mean("cca_mean_padded"), "procrustes_residual_mean": mean("procrustes_residual"),
            "affine_residual_mean": mean("affine_residual"), "effect_disagreement_mean": mean("disagreement"),
            "flow_r2_mean": mean("flow_r2"), "flow_cos_mean": mean("flow_cos_mean")}
