"""PREREG v6 Parts B4, C (C1-C8), V and F: the third animal (BANC). Written before the freeze (PREREG v6 X4); reads the BANC campaigns'
result logs, the first two animals' locked screens and run 5's locked stability file. Output: `research/ledger/thirdfly_v1/`.

    uv run --project ledger --no-sync python ledger/scripts/thirdfly_v1.py            # all tests whose campaigns are collected
    uv run --project ledger --no-sync python ledger/scripts/thirdfly_v1.py --validity # B4 only (after bt and bs are collected)

A test whose campaign is missing is reported as "not run" with the reason. The words are PREREG v6's and nothing stronger.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger import agree as AG  # noqa: E402
from brainir_ledger import banc as BN  # noqa: E402
from brainir_ledger import overlap6 as O6  # noqa: E402
from brainir_ledger import screens6 as S6  # noqa: E402

OUT = RESEARCH / "thirdfly_v1"
H16 = (list(range(8)), list(range(8, 16)))
H8 = (list(range(4)), list(range(4, 8)))
CUTS = (0.3, 0.4, 0.5, 0.6)
DRIVER = 0.5
SEED_POOL, SEED_NSTAR, SEED_PERM = 20261602, 20261603, 20261604
N_BOOT, N_PERM = 10_000, 100_000
C8_TYPES = ("DNa07", "DNb08", "DNg100", "DNg54", "DNg63", "DNit013", "DNp02", "DNp41", "DNp63", "DNxl101", "DNxl102", "DNxl110", "DNxl121")
MALECNS_DNB08 = (328, 330, 345, 391)
AUTHORS_V2 = ("391", "250")


def _load(fn):
    try:
        return fn()
    except FileNotFoundError:
        return None


# ------------------------------------------------------------------------------------------------ type sets (PREREG v6 G5, B2)
def sets() -> dict[str, list[str]]:
    mc = pd.read_csv(RESEARCH / "pertype_v1" / "match_confidence.csv")
    b1r = set(pd.read_csv(RESEARCH / "pertype_v1" / "B1r.csv")["manc_type"])
    b2r = set(pd.read_csv(RESEARCH / "pertype_v1" / "B2r.csv")["manc_type"])
    bc = BN.match_confidence()
    bg = set(bc["manc_type"])
    bh = set(bc.loc[bc["confidence"] == "high", "manc_type"])
    mh = set(mc.loc[mc["confidence"] == "high", "manc_type"])
    mm = b1r & set(mc["manc_type"])
    return {"three_animal": sorted(b1r & mh & bh), "manc_banc_high": sorted(b1r & bh), "manc_banc_all": sorted(b1r & bg),
            "mcns_banc_high": sorted(b2r & mh & bh), "mcns_banc_all": sorted(b2r & bg), "manc_mcns_high": sorted(mm & mh),
            "manc_mcns_all": sorted(mm)}


def c1_sets() -> dict[str, list[str]]:
    h = BN.halves()
    matched = sorted(set(h["L"]) & set(h["R"]))
    lab = BN.match_confidence().set_index("manc_type")["banc_labels"]
    return {"label_consistent": [t for t in matched if ";" not in str(lab.get(t, ""))], "all_matched": matched}


def no_dng(ts):
    return [t for t in ts if t != "DNg100"]


# ------------------------------------------------------------------------------------------------ resample helpers
def _vecs(screens: dict[str, pd.DataFrame], tl: list[str], halves) -> dict[str, np.ndarray]:
    v = {}
    for name, df in screens.items():
        f, a, b = AG._three(df, tl, list(halves[0]), list(halves[1]))
        v[name], v[f"{name}_h1"], v[f"{name}_h2"] = f.to_numpy(float), a.to_numpy(float), b.to_numpy(float)
    return v


def _boot_pairs(v: dict, pairs, idx) -> dict:
    allp = list(dict.fromkeys(p for x, y in pairs for p in AG._pairs(x, y)))
    rh = AG._resampled_rhos(v, allp, idx)
    out = {}
    for x, y in pairs:
        B = [rh[p] for p in AG._pairs(x, y)]
        rx, c = (B[1] + B[2]) / 2, (B[3] + B[4]) / 2
        with np.errstate(divide="ignore", invalid="ignore"):
            out[(x, y)] = {"rho_x": rx, "c": c, "ratio": rx / c, "keep": ~np.isnan(np.vstack(B)).any(axis=0)}
    return out


def _pct(a):
    a = np.asarray(a, float)
    a = a[~np.isnan(a)]
    return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))] if a.size else [None, None]


def _ts(df: pd.DataFrame, types, seeds=None) -> pd.Series:
    return AG.type_scores(df, seeds, types)


# ------------------------------------------------------------------------------------------------ B4 validity
def validity(bt, bs) -> dict:
    out = {"rule": "PREREG v6 B4"}
    if bt is not None:
        d = bt[bt["type"] == "DNg100"]
        n = int(((d["usable"]) & (d["score"] >= DRIVER)).sum())
        out["tuned"] = {"dng100_seeds_ge_0_5": n, "of": int(len(d)), "valid": bool(n >= 12)}
    if bs is not None:
        d = bs[bs["type"] == "DNg100"]
        n = int((d["score"] >= DRIVER).sum())
        out["sweep"] = {"dng100_seeds_ge_0_5": n, "of": int(len(d)), "valid": bool(n >= 6)}
    tv = out.get("tuned", {}).get("valid")
    sv = out.get("sweep", {}).get("valid")
    out["primary"] = "tuned" if tv else ("sweep" if (tv is False and sv) else ("not judged" if (tv is False and sv is False) else None))
    return out


# ------------------------------------------------------------------------------------------------ C1, C2
def c1(L, R) -> dict:
    s = c1_sets()
    out = {"type_sets": {k: len(v) for k, v in s.items()}}
    for k, ts in s.items():
        out[k] = AG.compare(L, R, ts, H8)
        out[k]["drivers"] = {"L": int((_ts(L, ts) >= DRIVER).sum()), "R": int((_ts(R, ts) >= DRIVER).sum())}
        out[k]["median_score"] = {"L": float(_ts(L, ts).median()), "R": float(_ts(R, ts).median())}
    out["reference_locked"] = {"MANC_L_vs_R": 0.587, "MaleCNS_L_vs_R": 0.642, "source": "reliability_v2/A.json (rulebook v4 A2)"}
    return out


def c2(L, R, c1s, c2s) -> dict:
    out = {}
    for k, ts in c1_sets().items():
        cc = AG.compare(c1s, c2s, ts, H8)
        ob = AG.compare(L, R, ts, H8)
        lo, hi = cc["bootstrap"]["interval"]["rho_x"]
        o = ob["primary"]["rho_x"]
        v = _vecs({"L": L, "R": R, "C1": c1s, "C2": c2s}, AG._type_list(ts), H8)
        b = _boot_pairs(v, [("L", "R"), ("C1", "C2")], AG._draw(len(AG._type_list(ts)), AG.N_BOOT, AG.BOOT_SEED))
        keep = b[("L", "R")]["keep"] & b[("C1", "C2")]["keep"]
        diff = b[("L", "R")]["rho_x"][keep] - b[("C1", "C2")]["rho_x"][keep]
        rep = bool(lo is not None and hi is not None and o is not None and lo <= o <= hi)
        out[k] = {"copy_vs_copy": cc, "observed_left_right": ob, "copy1_vs_L": AG.compare(c1s, L, ts, H8),
                  "copy2_vs_L": AG.compare(c2s, L, ts, H8),
                  "difference_observed_minus_copy": {"point": o - cc["primary"]["rho_x"], "interval": _pct(diff)},
                  "reproduces": rep, "words": "count noise reproduces BANC's left-right agreement" if rep else "does not reproduce it"}
    return out


# ------------------------------------------------------------------------------------------------ C3
def c3(S: dict, primary: str) -> dict:
    """S: {'tuned': (manc, mcns, banc, halves), 'sweep': (...)}"""
    st = sets()
    out = {}
    for proc, tpl in S.items():
        if tpl is None:
            out[proc] = "not run"
            continue
        m, c, b, hv = tpl
        out[proc] = {}
        for label, (X, Y, keys) in {"MANC-BANC": (m, b, ("three_animal", "manc_banc_high", "manc_banc_all")),
                                    "MaleCNS-BANC": (c, b, ("three_animal", "mcns_banc_high", "mcns_banc_all")),
                                    "MANC-MaleCNS (reference, post hoc)": (m, c, ("three_animal", "manc_mcns_high", "manc_mcns_all"))}.items():
            out[proc][label] = {k: AG.compare(X, Y, st[k], hv) for k in keys}
    p = out.get(primary) if primary in ("tuned", "sweep") else None
    if not isinstance(p, dict):
        sentence = "not judged"
    else:
        w = [p["MANC-BANC"]["three_animal"]["words"], p["MaleCNS-BANC"]["three_animal"]["words"]]
        sentence = ("confirmed in the third animal" if all(x == "a real gap" for x in w) else
                    "not confirmed" if any(x == "at the ceiling" for x in w) else "inconclusive")
    out["first_line_words"] = sentence
    return out


# ------------------------------------------------------------------------------------------------ C4
def c4(lists: dict, banc: pd.DataFrame, banc_halves) -> dict:
    st = sets()
    out = {}
    for name, (X, xh, set_keys) in lists.items():
        out[name] = {}
        for sk in set_keys:
            for dng in ("without_DNg100", "with_DNg100"):
                ts = AG._type_list(st[sk] if dng == "with_DNg100" else no_dng(st[sk]))
                sx, sx1, sx2 = (_ts(X, ts).to_numpy(), _ts(X, ts, xh[0]).to_numpy(), _ts(X, ts, xh[1]).to_numpy())
                sy, sy1, sy2 = (_ts(banc, ts).to_numpy(), _ts(banc, ts, banc_halves[0]).to_numpy(), _ts(banc, ts, banc_halves[1]).to_numpy())
                blk = {"n_types": len(ts), "cuts": {}}
                for z in CUTS:
                    blk["cuts"][f"{z:.1f}"] = {"overlap": O6.overlap(sx, sy, sx1, sx2, sy1, sy2, z, names=ts),
                                               "graded": O6.graded(sx, sy, sx1, sx2, sy1, sy2, z)}
                p = blk["cuts"]["0.5"]["overlap"]["point"]["hypergeom_p"]
                blk["words_at_0.5"] = "at chance at the authors' cut" if (p is None or p >= 0.05) else "above chance"
                if dng == "with_DNg100":
                    blk["words_at_0.5"] += " (with DNg100: reported, not the words of record)"
                out[name][f"{sk}|{dng}"] = blk
    return out


# ------------------------------------------------------------------------------------------------ C5
def c5(screens: dict, primary_banc: pd.DataFrame, singles: pd.DataFrame | None, authors_dnb08: dict | None) -> dict:
    dng = _ts(primary_banc, ["DNg100"]).iloc[0]
    out = {"DNg100": {"banc_type_score_primary": float(dng), "words": "pass" if dng >= DRIVER else "fail",
                      "note": "a prediction of the unchanged procedure; never evidence of replication (PREREG v6 G5)"}}
    d8 = {k: (float(_ts(v, ["DNb08"]).iloc[0]) if (v is not None and "DNb08" in set(v["type"])) else None) for k, v in screens.items()}
    sing = {}
    if singles is not None:
        for t in sorted(set(singles["type"])):
            d = singles[singles["type"] == t]
            sing[t] = {"score": float(_ts(singles, [t]).iloc[0]), "n_usable": int(d["usable"].sum()),
                       "seeds_ge_0_5": int((d["usable"] & (d["score"] >= DRIVER)).sum()), "of": int(len(d))}
    out["DNb08"] = {"whole_type": d8, "single_members": {k: v for k, v in sing.items() if k.startswith("DNb08#")},
                    "authors_banc_config": authors_dnb08, "authors_reported": "mean 0.000 in BANC (their single DNb08 neuron; Part Q 3)"}
    out["DNg100_single_members"] = {k: v for k, v in sing.items() if k.startswith("DNg100#")}
    # the driver table
    allt = sorted(set().union(*[set(v["type"]) for v in screens.values() if v is not None]))
    tab = pd.DataFrame({k: (_ts(v).reindex(allt) if v is not None else pd.Series(np.nan, index=allt)) for k, v in screens.items()},
                       index=allt)
    mc = pd.read_csv(RESEARCH / "pertype_v1" / "match_confidence.csv").set_index("manc_type")["confidence"]
    bc = BN.match_confidence().set_index("manc_type")["confidence"]
    keys = [k for k in ("B1r", "A1", "B2r", "BANC_tuned") if k in tab]
    drv = tab[(tab[keys] >= DRIVER).any(axis=1)].copy()
    drv["malecns_match"] = [mc.get(t, "none") for t in drv.index]
    drv["banc_match"] = [bc.get(t, "none") for t in drv.index]
    out["driver_table"] = drv.reset_index(names="manc_type").replace({np.nan: None}).to_dict("records")
    return out


# ------------------------------------------------------------------------------------------------ C6, C7
def c6(m, c, b) -> dict:
    ts = AG._type_list(sets()["three_animal"])
    s = {"M": _ts(m, ts).to_numpy(float), "C": _ts(c, ts).to_numpy(float), "B": _ts(b, ts).to_numpy(float)}
    v = dict(s)
    v["mCB"], v["mMB"], v["mMC"] = (s["C"] + s["B"]) / 2, (s["M"] + s["B"]) / 2, (s["M"] + s["C"]) / 2
    spec = {"M": ("mCB", "C", "B"), "C": ("mMB", "M", "B"), "B": ("mMC", "M", "C")}
    pairs = [(p, t) for t, (pm, a, bb) in spec.items() for p in (pm, a, bb)]
    d_point = {t: AG.spearman(v[pm], v[t]) - (AG.spearman(v[a], v[t]) + AG.spearman(v[bb], v[t])) / 2 for t, (pm, a, bb) in spec.items()}
    D = float(np.mean(list(d_point.values())))
    idx = np.random.default_rng(SEED_POOL).integers(0, len(ts), size=(N_BOOT, len(ts)))
    rh = AG._resampled_rhos(v, pairs, idx)
    dd = np.mean([rh[(pm, t)] - (rh[(a, t)] + rh[(bb, t)]) / 2 for t, (pm, a, bb) in spec.items()], axis=0)
    iv = _pct(dd)
    return {"n_types": len(ts), "d_by_target": {"MANC": d_point["M"], "MaleCNS": d_point["C"], "BANC": d_point["B"]}, "D": D,
            "interval": iv, "n_dropped": int(np.isnan(dd).sum()), "expected_gain_planning": 0.077,
            "words": "pooling helps" if (iv[0] is not None and iv[0] > 0) else "not shown"}


def c7(m, c, b, halves) -> dict:
    tl = AG._type_list(sets()["three_animal"])
    v = _vecs({"M": m, "C": c, "B": b}, tl, halves)
    pts = {p: AG.compare(X, Y, tl, halves)["primary"]["ratio"] for p, (X, Y) in {"MB": (m, b), "CB": (c, b), "MC": (m, c)}.items()}
    rbar = float(np.mean(list(pts.values())))
    nstar = (4 * (1 - rbar) / rbar) if rbar > 0 else float("inf")
    idx = np.random.default_rng(SEED_NSTAR).integers(0, len(tl), size=(N_BOOT, len(tl)))
    bb = _boot_pairs(v, [("M", "B"), ("C", "B"), ("M", "C")], idx)
    keep = bb[("M", "B")]["keep"] & bb[("C", "B")]["keep"] & bb[("M", "C")]["keep"]
    rb = np.mean([bb[p]["ratio"] for p in bb], axis=0)[keep]
    with np.errstate(divide="ignore"):
        ns = np.where(rb > 0, 4 * (1 - rb) / np.where(rb > 0, rb, 1), np.inf)
    return {"ratios": pts, "rbar": rbar, "n_star": nstar, "n_star_rounded_up": (int(np.ceil(nstar)) if np.isfinite(nstar) else None),
            "interval": [float(np.percentile(ns, 2.5)), float(np.percentile(ns, 97.5))], "n_resamples_rbar_le_0": int((rb <= 0).sum()),
            "n_dropped": int((~keep).sum()),
            "label": "an extrapolation (Spearman-Brown): it assumes the animals are exchangeable noisy measurements of one screen, and "
                     "differences in reconstruction and annotation count as differences between animals"}


# ------------------------------------------------------------------------------------------------ C8
def c8(banc: pd.DataFrame) -> dict:
    S = json.loads((RESEARCH / "replication_v1" / "S_tests.json").read_text())
    pt = pd.DataFrame(S["per_type"]).set_index("manc_type")
    b1r = pd.read_csv(RESEARCH / "pertype_v1" / "B1r.csv").set_index("manc_type")["score"]
    have = set(banc["type"])
    out = {"disclosure": "the predictor was chosen because it was nominally positive in run 5 (p = 0.035), on another animal"}
    rng = np.random.default_rng(SEED_PERM)
    for label, types, pred in (("primary", [t for t in C8_TYPES if t != "DNg100"], "mean_copy_score"),
                               ("with_DNg100", list(C8_TYPES), "mean_copy_score"),
                               ("stability_fraction", [t for t in C8_TYPES if t != "DNg100"], "stability")):
        ts = [t for t in types if t in have and t in pt.index]
        x = pt.loc[ts, pred].to_numpy(float)
        y = _ts(banc, ts).reindex(ts).to_numpy(float)
        rho = AG.spearman(x, y)
        perm = np.array([AG.spearman(x, rng.permutation(y)) for _ in range(N_PERM)]) if label == "primary" else None
        rec = {"types": ts, "n": len(ts), "predictor": pred, "rho": rho}
        if perm is not None:
            p = float((1 + np.sum(perm >= rho - 1e-12)) / (1 + N_PERM))
            rec.update({"p_one_sided_permutation": p, "n_perm": N_PERM, "seed": SEED_PERM,
                        "words": "stability under count noise predicts the third animal" if p < 0.05 else "not shown"})
        out[label] = rec
    ts = out["primary"]["types"]
    x, y, z = pt.loc[ts, "mean_copy_score"].to_numpy(float), _ts(banc, ts).reindex(ts).to_numpy(float), b1r.reindex(ts).to_numpy(float)
    rxy, rxz, ryz = AG.spearman(x, y), AG.spearman(x, z), AG.spearman(y, z)
    den = np.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
    out["partial_given_B1r_score"] = {"rho_partial": float((rxy - rxz * ryz) / den) if den > 0 else None, "rho_x_z": rxz, "rho_y_z": ryz}
    return out


# ------------------------------------------------------------------------------------------------ Part V
def part_v(res: dict | None) -> dict:
    if res is None:
        return {"status": "not run (pv-mcns-run6 not collected)"}

    def sc(r):
        return float(r["score"]) if (r.get("solver_success") and r.get("score") is not None) else 0.0

    v1 = np.array([sc(r) for k, r in res.items() if k.startswith("V1|")])
    w1 = bool(v1.mean() >= 0.90 and (v1 >= 0.5).mean() >= 0.90)
    v2 = {}
    for k, r in res.items():
        if k.startswith("V2|"):
            _, who, cur, _s = k.split("|")
            v2.setdefault(who.split("-")[1], {}).setdefault(cur[1:], []).append(sc(r))
    tab, hits = {}, []
    for pos in sorted(v2, key=int):
        for cur in sorted(v2[pos], key=float):
            a = np.array(v2[pos][cur])
            tab.setdefault(pos, {})[cur] = {"mean": float(a.mean()), "frac_ge_0_5": float((a >= 0.5).mean()), "n": int(a.size)}
            if (a >= 0.5).mean() >= 0.5:
                hits.append((pos, cur))
    hits.sort(key=lambda pc: (pc != AUTHORS_V2, int(pc[0]), float(pc[1])))
    words = ("reproduces the authors' reported result at current " + ", ".join(f"{c} (position {p})" for p, c in hits)) if hits else \
        "does not reproduce it at any tested current"
    return {"V1": {"n": int(v1.size), "mean": float(v1.mean()), "frac_ge_0_5": float((v1 >= 0.5).mean()),
                   "words": "reproduces the authors' DNg100 result" if w1 else "does not reproduce it", "authors": {"mean": 0.985, "frac": 1.0}},
            "V2": {"table": tab, "authors_configuration": {"position": 391, "current": 250, **tab.get("391", {}).get("250", {})},
                   "authors_reported": {"mean": 0.803, "frac_ge_0_5": 0.878, "n": 1024}, "members_meeting_bar": hits, "words": words}}


# ------------------------------------------------------------------------------------------------ Part F
def part_f(bt, bs) -> list[dict]:
    sl = pd.read_csv(RESEARCH / "forward_v2" / "SHORTLIST.csv")
    bc = BN.match_confidence().set_index("manc_type")["confidence"]
    rows = []
    for _, r in sl.iterrows():
        t = r["manc_type"]
        rows.append({**{k: r[k] for k in sl.columns}, "banc_match": bc.get(t, "none"),
                     "banc_tuned": (float(_ts(bt, [t]).iloc[0]) if (bt is not None and t in set(bt["type"])) else None),
                     "banc_sweep": (float(_ts(bs, [t]).iloc[0]) if (bs is not None and t in set(bs["type"])) else None)})
    return rows


# ------------------------------------------------------------------------------------------------ main
def authors_dnb08_banc() -> dict | None:
    import glob  # noqa: PLC0415

    from brainir import paths  # noqa: PLC0415

    f = sorted(glob.glob(str(paths.data_root() / "raw" / "external" / "pugliese_2026_zenodo" / "DNb08_Stim_BANC_vncOnly" / "**" / ".hydra" /
                             "config.yaml"), recursive=True))
    if not f:
        return None
    txt = Path(f[0]).read_text()
    import re  # noqa: PLC0415

    st = re.findall(r"stimNeurons:\s*\n\s*- - (\d+)", txt)
    si = re.findall(r"stimI:\s*\n\s*- - ([\d.]+)", txt)
    return {"config": Path(f[0]).name, "stim_position": int(st[0]) if st else None, "stim_current": float(si[0]) if si else None}


def run(validity_only: bool = False) -> dict:
    bt, bs = _load(S6.banc_tuned), _load(S6.banc_sweep)
    val = validity(bt, bs)
    if validity_only:
        return {"B4_validity": val}
    prim = val["primary"]
    bl, br = _load(lambda: S6.banc_side("L")), _load(lambda: S6.banc_side("R"))
    k1, k2 = _load(lambda: S6.banc_copy(1)), _load(lambda: S6.banc_copy(2))
    m_t, c_t, a1 = S6.b1r(), S6.b2r(), S6.a1()
    m_s, c_s = S6.sweep_manc(), _load(S6.sweep_mcns)
    res = {"B4_validity": val, "primary_procedure": prim}
    res["C1"] = c1(bl, br) if (bl is not None and br is not None) else "not run"
    res["C2"] = c2(bl, br, k1, k2) if all(x is not None for x in (bl, br, k1, k2)) else "not run"
    S = {"tuned": (m_t, c_t, bt, H16) if bt is not None else None, "sweep": (m_s, c_s, bs, H8) if (bs is not None and c_s is not None) else None}
    res["C3"] = c3(S, prim or "not judged")
    judged = prim in ("tuned", "sweep")
    if judged:
        m, c, b, hv = S[prim]
        lists = {"B1r (our MANC list)": (m, hv, ("manc_banc_high", "manc_banc_all")),
                 "A1 (the authors' list)": (a1, H16, ("manc_banc_high", "manc_banc_all")),
                 "B2r (our MaleCNS list)": (c, hv, ("mcns_banc_high", "mcns_banc_all"))}
        if prim == "sweep":
            lists = {"MANC sweep list": (m, hv, ("manc_banc_high", "manc_banc_all")), "A1 (the authors' list)": (a1, H16, ("manc_banc_high", "manc_banc_all")),
                     "MaleCNS sweep list": (c, hv, ("mcns_banc_high", "mcns_banc_all"))}
        res["C4"] = c4(lists, b, hv)
        res["C6"] = c6(m, c, b)
        res["C7"] = c7(m, c, b, hv)
        res["C8"] = c8(b)
    else:
        res["C4"] = res["C6"] = res["C7"] = res["C8"] = "not judged (PREREG v6 B4)"
    screens = {"B1r": m_t, "A1": a1, "B2r": c_t, "BANC_tuned": bt, "BANC_sweep": bs, "MANC_sweep": m_s, "MaleCNS_sweep": c_s,
               "MANC_K0": S6.k0_manc(), "MaleCNS_K0": S6.k0_mcns()}
    res["C5"] = c5(screens, S[prim][2] if judged else bt, _load(S6.banc_singles), authors_dnb08_banc()) if bt is not None else "not run"
    res["V"] = part_v(_load(lambda: S6.results("thirdfly_v1", "pv-mcns-run6")))
    res["F"] = part_f(bt, bs)
    sides = BN.dn_sides()
    res["B2_sides"] = {"agreement": sides.attrs.get("agreement"), "n_defined": sides.attrs.get("n_defined"), "reliable": sides.attrs.get("reliable"),
                       "n_matched_types": len(c1_sets()["all_matched"]), "n_label_consistent": len(c1_sets()["label_consistent"])}
    return res


def build() -> None:
    res = run()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "C_tests.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    BN.dn_sides().to_csv(OUT / "banc_dn_sides.csv", index=False)
    pd.DataFrame(res["F"]).to_csv(OUT / "F_forward_banc.csv", index=False)
    camps = [("thirdfly_v1", c) for c in ("bg-banc-run6", "bt-banc-run6", "bs-banc-run6", "bh-banc-run6", "bn-banc-run6", "pv-mcns-run6")]
    unt = [S6.results_path(a, c).relative_to(RESEARCH.parents[1]).as_posix() for a, c in camps if S6.results_path(a, c).exists()]
    man = {"inputs_locked": ["pertype_v1 (LOCK_pertype_v1)", "predictions_v2, predictions (LOCK_predictions_v1/v2)", "replication_v1/S_tests.json (LOCK_replication_v1)",
                             "posthoc_v6 (LOCK_posthoc_v6)", "forward_v2/SHORTLIST.csv (LOCK_forward_v2)"],
           "untracked_inputs": unt, "code": ["ledger/scripts/thirdfly_v1.py", "ledger/src/brainir_ledger/banc.py", "ledger/src/brainir_ledger/screens6.py",
                                             "ledger/src/brainir_ledger/overlap6.py", "ledger/src/brainir_ledger/agree.py"]}
    (OUT / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n")
    print(json.dumps({"B4": res["B4_validity"], "C3_first_line": res["C3"]["first_line_words"] if isinstance(res["C3"], dict) else res["C3"]}, default=str))


if __name__ == "__main__":
    if "--validity" in sys.argv:
        print(json.dumps(run(validity_only=True), indent=1))
    else:
        build()
