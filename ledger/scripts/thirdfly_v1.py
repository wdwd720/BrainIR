"""PREREG v6 Parts B4, C (C1-C8 and C3's wiring check), V and F: the third animal (BANC). Committed before the freeze and hashed by
`LOCK_prereg_v6.json` (PREREG v6 X4). Reads the BANC campaigns' result logs, the first two animals' locked screens, run 5's locked
stability file and the annotation-only type sets frozen in `gates_v6/TYPE_SETS_v6.json`. Output: `research/ledger/thirdfly_v1/`.

    uv run --project ledger --no-sync python ledger/scripts/thirdfly_v1.py            # every test whose campaigns are collected
    uv run --project ledger --no-sync python ledger/scripts/thirdfly_v1.py --validity # B4 only (after bt and bs are collected)

Rules carried here (PREREG v6): the words of C1-C4 and C6-C8 rest on the type sets WITHOUT DNg100 (G5); the with-DNg100 versions are
computed beside them without words; C5 is judged on the tuned screen only; a test whose campaign is missing is "not run"; a pair that
is "not judged" makes C3's sentence "not judged" and C7's estimate "not computed"; an undefined statistic never gives positive words.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

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
WIRING_FLOOR = 0.71
AUTHORS_V2 = ("391", "250")


def _load(fn):
    try:
        return fn()
    except FileNotFoundError:
        return None


# ------------------------------------------------------------------------------------------------ type sets (G5, B2)
def sets() -> dict:
    """The frozen annotation-only sets (gates_v6/TYPE_SETS_v6.json); `_noDNg100` sets carry the words."""
    return json.loads((RESEARCH / "gates_v6" / "TYPE_SETS_v6.json").read_text())


def c1_sets() -> dict[str, list[str]]:
    """B2: types with >= 1 member on each side (side rule computed after the freeze); label-consistent = one BANC label."""
    h = BN.halves()
    matched = sorted(set(h["L"]) & set(h["R"]))
    lab = BN.match_confidence().set_index("manc_type")["banc_labels"]
    lc = [t for t in matched if ";" not in str(lab.get(t, ""))]
    return {"label_consistent": lc, "label_consistent_noDNg100": [t for t in lc if t != "DNg100"], "all_matched": matched,
            "all_matched_noDNg100": [t for t in matched if t != "DNg100"]}


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


def _not_record(d: dict) -> dict:
    """Audit re-check N5: a block outside the word-bearing set keeps its words only under a marked name."""
    if isinstance(d, dict) and "words" in d:
        d["words_not_of_record"] = d.pop("words")
    return d


def _pct(a):
    a = np.asarray(a, float)
    a = a[~np.isnan(a)]
    return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))] if a.size else [None, None]


def _ts(df: pd.DataFrame, types=None, seeds=None) -> pd.Series:
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
    out = {"type_sets": {k: len(v) for k, v in s.items()}, "words_on": "label_consistent_noDNg100"}
    for k, ts in s.items():
        if len(ts) < 3:
            out[k] = "not judged (fewer than 3 types)"
            continue
        out[k] = AG.compare(L, R, ts, H8)
        out[k]["drivers"] = {"L": int((_ts(L, ts) >= DRIVER).sum()), "R": int((_ts(R, ts) >= DRIVER).sum())}
        out[k]["median_score"] = {"L": float(_ts(L, ts).median()), "R": float(_ts(R, ts).median())}
    w = out.get("label_consistent_noDNg100")
    out["words"] = w["words"] if isinstance(w, dict) else "not judged"
    for k in s:
        if k != "label_consistent_noDNg100":
            _not_record(out[k])
    out["reference_locked"] = {"MANC_L_vs_R": 0.587, "MaleCNS_L_vs_R": 0.642, "source": "reliability_v2/A.json (rulebook v4 A2)"}
    return out


def c2(L, R, c1s, c2s) -> dict:
    out = {"words_on": "label_consistent_noDNg100"}
    for k, ts in c1_sets().items():
        if len(ts) < 3:
            out[k] = "not judged (fewer than 3 types)"
            continue
        cc = AG.compare(c1s, c2s, ts, H8)
        ob = AG.compare(L, R, ts, H8)
        lo, hi = cc["bootstrap"]["interval"]["rho_x"]
        o = ob["primary"]["rho_x"]
        tl = AG._type_list(ts)
        v = _vecs({"L": L, "R": R, "C1": c1s, "C2": c2s}, tl, H8)
        b = _boot_pairs(v, [("L", "R"), ("C1", "C2")], AG._draw(len(tl), AG.N_BOOT, AG.BOOT_SEED))
        keep = b[("L", "R")]["keep"] & b[("C1", "C2")]["keep"]
        diff = b[("L", "R")]["rho_x"][keep] - b[("C1", "C2")]["rho_x"][keep]
        ok = lo is not None and hi is not None and o is not None and np.isfinite(o)
        rep = bool(ok and lo <= o <= hi)
        out[k] = {"copy_vs_copy": cc, "observed_left_right": ob, "copy1_vs_L": AG.compare(c1s, L, ts, H8),
                  "copy2_vs_L": AG.compare(c2s, L, ts, H8),
                  "difference_observed_minus_copy": {"point": (o - cc["primary"]["rho_x"]) if ok else None, "interval": _pct(diff)},
                  "reproduces": rep, "words": "count noise reproduces BANC's left-right agreement" if rep else "does not reproduce it"}
    w = out.get("label_consistent_noDNg100")
    out["words"] = w["words"] if isinstance(w, dict) else "not judged"
    for k in c1_sets():
        if k != "label_consistent_noDNg100" and isinstance(out.get(k), dict):
            _not_record(out[k])
            for sub in ("copy_vs_copy", "observed_left_right", "copy1_vs_L", "copy2_vs_L"):
                _not_record(out[k][sub])
    if isinstance(w, dict):
        for sub in ("copy_vs_copy", "observed_left_right", "copy1_vs_L", "copy2_vs_L"):
            _not_record(w[sub])
    return out


# ------------------------------------------------------------------------------------------------ C3 and its wiring check
def c3(S: dict, primary: str) -> dict:
    """S: {'tuned': (manc, mcns, banc, halves) or None, 'sweep': ...}. Words on three_animal_noDNg100 under the primary procedure."""
    st = sets()
    out = {"words_on": "three_animal_noDNg100"}
    keys = {"MANC-BANC": ("three_animal_noDNg100", "three_animal", "three_animal_same_name_noDNg100", "manc_banc_high_noDNg100",
                          "manc_banc_all_noDNg100"),
            "MaleCNS-BANC": ("three_animal_noDNg100", "three_animal", "three_animal_same_name_noDNg100", "mcns_banc_high_noDNg100",
                             "mcns_banc_all_noDNg100"),
            "MANC-MaleCNS (reference, post hoc)": ("three_animal_noDNg100", "three_animal", "manc_mcns_high_noDNg100", "manc_mcns_all_noDNg100")}
    for proc, tpl in S.items():
        if tpl is None:
            out[proc] = "not run"
            continue
        m, c, b, hv = tpl
        out[proc] = {}
        for label, (X, Y) in {"MANC-BANC": (m, b), "MaleCNS-BANC": (c, b), "MANC-MaleCNS (reference, post hoc)": (m, c)}.items():
            out[proc][label] = {k: AG.compare(X, Y, st[k], hv) for k in keys[label]}
    p = out.get(primary) if primary in ("tuned", "sweep") else None
    if not isinstance(p, dict):
        sentence, ratios = "not judged", None
    else:
        w = [p["MANC-BANC"]["three_animal_noDNg100"]["words"], p["MaleCNS-BANC"]["three_animal_noDNg100"]["words"]]
        if any(x == "not judged" for x in w):
            sentence = "not judged"
        elif all(x == "a real gap" for x in w):
            sentence = "confirmed in the third animal"
        elif any(x == "at the ceiling" for x in w):
            sentence = "not confirmed"
        else:
            sentence = "inconclusive"
        ratios = {lab: {"ratio": p[lab]["three_animal_noDNg100"]["primary"]["ratio"],
                        "interval": p[lab]["three_animal_noDNg100"]["bootstrap"]["interval"]["ratio"],
                        ("words" if lab != "MANC-MaleCNS (reference, post hoc)" else "words_not_of_record"): p[lab]["three_animal_noDNg100"]["words"]}
                  for lab in p}
    out["first_line_words"] = sentence
    out["first_line_ratios"] = ratios
    for proc, blk in out.items():
        if not isinstance(blk, dict) or proc in ("first_line_ratios",):
            continue
        for lab, sets_ in blk.items():
            if not isinstance(sets_, dict):
                continue
            for k, d in sets_.items():
                if not (proc == primary and k == "three_animal_noDNg100" and lab in ("MANC-BANC", "MaleCNS-BANC")):
                    _not_record(d)
    return out


def c3_wiring() -> dict:
    """Audit finding 7 (descriptive, after the freeze): the two-step signed count per type (run 3's S2), BANC against MANC and against
    MaleCNS, on three_animal_noDNg100; a fixed caveat if either Spearman is below 0.71."""
    import scipy.sparse as sp  # noqa: PLC0415

    from brainir_ledger import baselines as BL  # noqa: PLC0415
    from brainir_ledger import mirror as MR  # noqa: PLC0415

    from brainir_ledger import fixes as FX  # noqa: PLC0415

    BN.require_unblind("BANC wiring check")
    ts = sets()["three_animal_noDNg100"]
    fm, fc = MR.fly("MANC"), MR.fly("MaleCNS")
    net = BN.network()
    C0 = BN.raw_counts()
    C5 = FX.at_floor(C0, 5)
    s2 = {"MANC": BL.compute(fm.C, sp.csr_matrix(fm.net.W, dtype=float), fm.readout, fm.groups, []),
          "MaleCNS": BL.compute(fc.C, sp.csr_matrix(fc.net.W, dtype=float), fc.readout, fc.groups, []),
          "BANC": BL.compute(C0, sp.csr_matrix(net.W, dtype=float), net.readout, BN.groups(), []),
          "BANC_floor5": BL.compute(C5, FX.signed(C5, BN.row_sign()), net.readout, BN.groups(), [])}
    v = {k: d.set_index("manc_type")["S2_twohop_signed"].reindex(ts).to_numpy(float) for k, d in s2.items()}
    r = {"MANC-BANC": AG.spearman(v["MANC"], v["BANC"]), "MaleCNS-BANC": AG.spearman(v["MaleCNS"], v["BANC"]),
         "MANC-BANC_floor5": AG.spearman(v["MANC"], v["BANC_floor5"]), "MaleCNS-BANC_floor5": AG.spearman(v["MaleCNS"], v["BANC_floor5"]),
         "MANC-MaleCNS": AG.spearman(v["MANC"], v["MaleCNS"])}
    low = [k for k in ("MANC-BANC_floor5", "MaleCNS-BANC_floor5") if not (np.isfinite(r[k]) and r[k] >= WIRING_FLOOR)]
    return {"spearman": r, "n_types": len(ts), "floor": WIRING_FLOOR, "caveat_rests_on": "the 5-synapse-floor BANC companion (like for like)",
            "floor_source": "0.71 = the lowest value of this statistic in run 4 (0.713, MANC-R vs MaleCNS-L, WIRING_A4.json)", "below_floor": low,
            "caveat": ("BANC's wiring of these types agrees with the other animals' less than the first two animals' wiring agreed, so part "
                       "of the gap may come from the build or the type match") if low else None}


# ------------------------------------------------------------------------------------------------ C4
AT_CHANCE_NOTE = ("'At chance' means the overlap could not be told apart from chance by this test, whose power is low (PREREG v6 C4); it "
                  "does not show that the hits fail to recur.")


def c4(lists: dict, banc: pd.DataFrame, banc_halves) -> dict:
    st = sets()
    out = {"words_on": "the high sets without DNg100", "note": AT_CHANCE_NOTE}
    for name, (X, xh, set_keys) in lists.items():
        out[name] = {}
        for sk in set_keys:
            ts = AG._type_list(st[sk])
            sx, sx1, sx2 = (_ts(X, ts).to_numpy(), _ts(X, ts, xh[0]).to_numpy(), _ts(X, ts, xh[1]).to_numpy())
            sy, sy1, sy2 = (_ts(banc, ts).to_numpy(), _ts(banc, ts, banc_halves[0]).to_numpy(), _ts(banc, ts, banc_halves[1]).to_numpy())
            blk = {"n_types": len(ts), "cuts": {}}
            for z in CUTS:
                blk["cuts"][f"{z:.1f}"] = {"overlap": O6.overlap(sx, sy, sx1, sx2, sy1, sy2, z, names=ts),
                                           "graded": O6.graded(sx, sy, sx1, sx2, sy1, sy2, z)}
            pt = blk["cuts"]["0.5"]["overlap"]["point"]
            if pt["n_x"] == 0 or pt["n_y"] == 0:
                w = "not judged (an empty driver list)"
            else:
                w = "at chance at the authors' cut" if pt["hypergeom_p"] >= 0.05 else "above chance"
            blk["words_at_0.5"] = w if sk.endswith("high_noDNg100") else f"{w} (beside the words of record, not words)"
            out[name][sk] = blk
    return out


# ------------------------------------------------------------------------------------------------ C5 (tuned screen only)
def c5(screens: dict, bt: pd.DataFrame, bs: pd.DataFrame | None, singles: pd.DataFrame | None, authors_dnb08: dict | None) -> dict:
    dng = float(_ts(bt, ["DNg100"]).iloc[0])
    d = bt[bt["type"] == "DNg100"]
    out = {"DNg100": {"tuned_type_score": dng, "tuned_seeds_ge_0_5": int((d["usable"] & (d["score"] >= DRIVER)).sum()),
                      "words": "pass" if dng >= DRIVER else "fail",
                      "sweep_type_score_beside": (float(_ts(bs, ["DNg100"]).iloc[0]) if bs is not None else None),
                      "note": "judged on the tuned screen only; B4 counts seeds (12 of 16) and C5 the type score, so they can differ; never "
                              "evidence of replication (G5)"}}
    d8 = {k: (float(_ts(v, ["DNb08"]).iloc[0]) if (v is not None and "DNb08" in set(v["type"])) else None) for k, v in screens.items()}
    sing = {}
    if singles is not None:
        for t in sorted(set(singles["type"])):
            g = singles[singles["type"] == t]
            sing[t] = {"score": float(_ts(singles, [t]).iloc[0]), "n_usable": int(g["usable"].sum()),
                       "seeds_ge_0_5": int((g["usable"] & (g["score"] >= DRIVER)).sum()), "of": int(len(g))}
    out["DNb08"] = {"whole_type": d8, "single_members": {k: v for k, v in sing.items() if k.startswith("DNb08#")},
                    "authors_banc_config": authors_dnb08, "authors_reported": "mean 0.000 in BANC (their single DNb08 neuron; Part Q 3)"}
    out["DNg100_single_members"] = {k: v for k, v in sing.items() if k.startswith("DNg100#")}
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


# ------------------------------------------------------------------------------------------------ C6 (revised, audit finding 1)
def c6(m, c, b, key: str = "three_animal_noDNg100") -> dict:
    ts = AG._type_list(sets()[key])
    v = {"M": _ts(m, ts).to_numpy(float), "C": _ts(c, ts).to_numpy(float), "B": _ts(b, ts).to_numpy(float)}
    v["P"] = (v["M"] + v["C"]) / 2
    v["mCB"], v["mMB"] = (v["C"] + v["B"]) / 2, (v["M"] + v["B"]) / 2
    idx = np.random.default_rng(SEED_POOL).integers(0, len(ts), size=(N_BOOT, len(ts)))
    pairs = [("P", "B"), ("M", "B"), ("C", "B"), ("mCB", "M"), ("C", "M"), ("mMB", "C")]
    rh = AG._resampled_rhos(v, pairs, idx)
    dM_pt = AG.spearman(v["P"], v["B"]) - AG.spearman(v["M"], v["B"])
    dC_pt = AG.spearman(v["P"], v["B"]) - AG.spearman(v["C"], v["B"])
    iM, iC = _pct(rh[("P", "B")] - rh[("M", "B")]), _pct(rh[("P", "B")] - rh[("C", "B")])
    defined = all(x is not None for x in (*iM, *iC)) and np.isfinite(dM_pt) and np.isfinite(dC_pt)
    helps = bool(defined and iM[0] > 0 and iC[0] > 0)
    # the prompt's D (all three targets), beside it without words
    spec = {"M": ("mCB", "C", "B"), "C": ("mMB", "M", "B"), "B": ("P", "M", "C")}
    dpt = {t: AG.spearman(v[pm], v[t]) - (AG.spearman(v[a], v[t]) + AG.spearman(v[bb], v[t])) / 2 for t, (pm, a, bb) in spec.items()}
    rh2 = AG._resampled_rhos(v, [(p, t) for t, (pm, a, bb) in spec.items() for p in (pm, a, bb)], idx)
    dd = np.mean([rh2[(pm, t)] - (rh2[(a, t)] + rh2[(bb, t)]) / 2 for t, (pm, a, bb) in spec.items()], axis=0)
    return {"n_types": len(ts), "set": key, "d_M": {"point": dM_pt, "interval": iM}, "d_C": {"point": dC_pt, "interval": iC},
            "words": "pooling helps" if helps else "not shown", "expected_gain_planning": "0.053 / 0.079 / 0.106 if BANC agrees with each "
            "animal at r = 0.25 / 0.37 / 0.5 (PLANNING_v6.json)",
            "prompt_D_without_words": {"by_target": {"MANC": dpt["M"], "MaleCNS": dpt["C"], "BANC": dpt["B"]}, "D": float(np.mean(list(dpt.values()))),
                                       "interval": _pct(dd), "note": "positive by construction when the sources agree (audit finding 1)"}}


# ------------------------------------------------------------------------------------------------ C7
def _q(a: np.ndarray, p: float) -> float:
    s = np.sort(a)
    return float(s[min(len(s) - 1, max(0, int(np.floor(p * (len(s) - 1)))))]) if len(s) else float("nan")


def c7(m, c, b, halves, key: str = "three_animal_noDNg100") -> dict:
    tl = AG._type_list(sets()[key])
    cmp = {p: AG.compare(X, Y, tl, halves) for p, (X, Y) in {"MB": (m, b), "CB": (c, b), "MC": (m, c)}.items()}
    if any(x["words"] == "not judged" for x in cmp.values()):
        return {"set": key, "n_star": None, "words": "not computed (a pair is not judged)", "ratios": {p: x["primary"]["ratio"] for p, x in cmp.items()}}
    pts = {p: x["primary"]["ratio"] for p, x in cmp.items()}
    rbar = float(np.mean(list(pts.values())))

    def nstar(r):
        return 1.0 if r >= 0.8 else (4 * (1 - r) / r if r > 0 else float("inf"))

    v = _vecs({"M": m, "C": c, "B": b}, tl, halves)
    idx = np.random.default_rng(SEED_NSTAR).integers(0, len(tl), size=(N_BOOT, len(tl)))
    bb = _boot_pairs(v, [("M", "B"), ("C", "B"), ("M", "C")], idx)
    keep = bb[("M", "B")]["keep"] & bb[("C", "B")]["keep"] & bb[("M", "C")]["keep"]
    rb = np.mean([bb[p]["ratio"] for p in bb], axis=0)[keep]
    ns = np.array([nstar(r) for r in rb])
    n0 = nstar(rbar)
    return {"set": key, "ratios": pts, "rbar": rbar, "n_star": n0, "n_star_rounded_up": (int(np.ceil(n0)) if np.isfinite(n0) else None),
            "interval": [_q(ns, 0.025), _q(ns, 0.975)], "n_resamples_rbar_le_0": int((rb <= 0).sum()), "n_dropped": int((~keep).sum()),
            "label": "an extrapolation (Spearman-Brown): it assumes the animals are exchangeable noisy measurements of one screen, and "
                     "differences in reconstruction and annotation count as differences between animals"}


# ------------------------------------------------------------------------------------------------ C8
def c8(banc: pd.DataFrame) -> dict:
    S = json.loads((RESEARCH / "replication_v1" / "S_tests.json").read_text())
    pt = pd.DataFrame(S["per_type"]).set_index("manc_type")
    b1r = pd.read_csv(RESEARCH / "pertype_v1" / "B1r.csv").set_index("manc_type")["score"]
    have = set(banc["type"])
    C8 = sets()["C8"]
    out = {"disclosure": "the predictor was chosen because it was nominally positive in run 5 (p = 0.035), on another animal; DNb08 is one "
                         "of the 12 and the authors' single DNb08 scored 0.000 in BANC (a secondary analysis leaves it out)"}
    rng = np.random.default_rng(SEED_PERM)
    for label, key, pred in (("primary", "primary", "mean_copy_score"), ("with_DNg100", "with_DNg100", "mean_copy_score"),
                             ("without_DNb08", "without_DNb08", "mean_copy_score"), ("stability_fraction", "primary", "stability")):
        ts = [t for t in C8[key] if t in have and t in pt.index]
        x = pt.loc[ts, pred].to_numpy(float)
        y = _ts(banc, ts).reindex(ts).to_numpy(float)
        rho = AG.spearman(x, y)
        rec = {"types": ts, "n": len(ts), "predictor": pred, "rho": rho if np.isfinite(rho) else None}
        if label == "primary":
            if not np.isfinite(rho):
                rec.update({"p_one_sided_permutation": None, "words": "not shown (rho undefined: an outcome or predictor is constant)"})
            else:
                perm = np.array([AG.spearman(x, rng.permutation(y)) for _ in range(N_PERM)])
                ge = np.sum(np.where(np.isnan(perm), True, perm >= rho - 1e-12))
                p = float((1 + ge) / (1 + N_PERM))
                rec.update({"p_one_sided_permutation": p, "n_perm": N_PERM, "seed": SEED_PERM,
                            "words": "stability under count noise predicts the third animal" if p < 0.05 else "not shown"})
        out[label] = rec
    ts = out["primary"]["types"]
    x, y, z = pt.loc[ts, "mean_copy_score"].to_numpy(float), _ts(banc, ts).reindex(ts).to_numpy(float), b1r.reindex(ts).to_numpy(float)
    rxy, rxz, ryz = AG.spearman(x, y), AG.spearman(x, z), AG.spearman(y, z)
    den = np.sqrt((1 - rxz ** 2) * (1 - ryz ** 2)) if np.isfinite(rxz) and np.isfinite(ryz) else 0.0
    out["partial_given_B1r_score"] = {"rho_partial": float((rxy - rxz * ryz) / den) if (den > 0 and np.isfinite(rxy)) else None,
                                      "rho_x_z": rxz, "rho_y_z": ryz}
    return out


# ------------------------------------------------------------------------------------------------ Part V
def part_v(res: dict | None, keys: list[str] | None = None) -> dict:
    """Every seed counts; the screen bounds are ignored; a solver failure, or a packed key without a result, scores 0 (PREREG v6 V, X3)."""
    if res is None:
        return {"status": "not run (pv-mcns-run6 not collected)"}
    res = {**{k: {"solver_success": False, "score": None} for k in (keys or []) if k not in res}, **res}

    def sc(r):
        return float(r["score"]) if (r.get("solver_success") and r.get("score") is not None) else 0.0

    v1 = np.array([sc(r) for k, r in res.items() if k.startswith("V1|")])
    w1 = bool(v1.size and v1.mean() >= 0.90 and (v1 >= 0.5).mean() >= 0.90)
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
    au = tab.get(AUTHORS_V2[0], {}).get(AUTHORS_V2[1])
    au_words = None if au is None else (
        f"at the authors' configuration (position 391, current 250) it {'reproduces' if au['frac_ge_0_5'] >= 0.5 else 'does not reproduce'} "
        f"their result ({round(au['frac_ge_0_5'] * au['n'])} of {au['n']} seeds >= 0.5, mean {au['mean']:.2f})")
    others = [h for h in hits if h != AUTHORS_V2]
    words = ("reproduces the authors' reported result at current " + ", ".join(f"{c} (position {p})" for p, c in
             ([AUTHORS_V2] if AUTHORS_V2 in hits else []) + others)) if hits else "does not reproduce it at any tested current"
    return {"V1": {"n": int(v1.size), "mean": float(v1.mean()) if v1.size else None, "frac_ge_0_5": float((v1 >= 0.5).mean()) if v1.size else None,
                   "words": "reproduces the authors' DNg100 result" if w1 else "does not reproduce it", "authors": {"mean": 0.985, "frac": 1.0}},
            "V2": {"table": tab, "authors_configuration_sentence": au_words, "authors_reported": {"mean": 0.803, "frac_ge_0_5": 0.878, "n": 1024},
                   "cells_meeting_bar": hits, "words": words}}


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
    import re  # noqa: PLC0415

    from brainir import paths  # noqa: PLC0415

    f = sorted(glob.glob(str(paths.data_root() / "raw" / "external" / "pugliese_2026_zenodo" / "DNb08_Stim_BANC_vncOnly" / "**" / ".hydra" /
                             "config.yaml"), recursive=True))
    if not f:
        return None
    txt = Path(f[0]).read_text()
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
    res = {"B4_validity": val, "primary_procedure": prim, "missing_keys": S6.missing_report()}
    res["C1"] = c1(bl, br) if (bl is not None and br is not None) else "not run"
    res["C2"] = c2(bl, br, k1, k2) if all(x is not None for x in (bl, br, k1, k2)) else "not run"
    S = {"tuned": (m_t, c_t, bt, H16) if bt is not None else None, "sweep": (m_s, c_s, bs, H8) if (bs is not None and c_s is not None) else None}
    res["C3"] = c3(S, prim or "not judged")
    res["C3_wiring"] = c3_wiring()
    res["C3"]["first_line_caveat"] = res["C3_wiring"]["caveat"]     # audit re-check N3: the first line cannot be quoted without it
    judged = prim in ("tuned", "sweep")
    if judged:
        m, c, b, hv = S[prim]
        lists = {("B1r (our MANC list)" if prim == "tuned" else "MANC sweep list"): (m, hv, ("manc_banc_high_noDNg100", "manc_banc_high",
                                                                                          "manc_banc_all_noDNg100", "three_animal_same_name_noDNg100")),
                 "A1 (the authors' list; 16-replicate halves under either procedure)": (a1, H16, ("manc_banc_high_noDNg100", "manc_banc_high",
                                                                                                  "manc_banc_all_noDNg100", "three_animal_same_name_noDNg100")),
                 ("B2r (our MaleCNS list)" if prim == "tuned" else "MaleCNS sweep list"): (c, hv, ("mcns_banc_high_noDNg100", "mcns_banc_high",
                                                                                                "mcns_banc_all_noDNg100", "three_animal_same_name_noDNg100"))}
        res["C4"] = c4(lists, b, hv)
        res["C6"] = c6(m, c, b)
        res["C6_with_DNg100"] = _not_record(c6(m, c, b, "three_animal"))
        res["C7"] = c7(m, c, b, hv)
        res["C7_with_DNg100"] = c7(m, c, b, hv, "three_animal")
        res["C8"] = c8(b)
    else:
        res["C4"] = res["C6"] = res["C7"] = res["C8"] = "not judged (PREREG v6 B4)"
    screens = {"B1r": m_t, "A1": a1, "B2r": c_t, "BANC_tuned": bt, "BANC_sweep": bs, "MANC_sweep": m_s, "MaleCNS_sweep": c_s,
               "MANC_K0": S6.k0_manc(), "MaleCNS_K0": S6.k0_mcns()}
    res["C5"] = c5(screens, bt, bs, _load(S6.banc_singles), authors_dnb08_banc()) if bt is not None else "not run"
    pv = _load(S6.partv_results)
    res["V"] = part_v(None if pv is None else pv[0], None if pv is None else pv[1])
    res["F"] = part_f(bt, bs)
    sides = BN.dn_sides()
    cs = c1_sets()
    res["B2_sides"] = {"agreement": sides.attrs.get("agreement"), "n_defined": sides.attrs.get("n_defined"), "reliable": sides.attrs.get("reliable"),
                       **{f"n_{k}": len(v) for k, v in cs.items()}}
    return res


def build() -> None:
    res = run()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "C_tests.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    BN.dn_sides().to_csv(OUT / "banc_dn_sides.csv", index=False)
    pd.DataFrame(res["F"]).to_csv(OUT / "F_forward_banc.csv", index=False)
    unt = sorted(p.relative_to(RESEARCH.parents[1]).as_posix() for p in (S6.data_dir() / "thirdfly_v1").glob("GHA_*-run6/results.pkl"))
    man = {"inputs_locked": ["pertype_v1 (LOCK_pertype_v1)", "predictions_v2, predictions (LOCK_predictions_v1/v2)", "replication_v1/S_tests.json (LOCK_replication_v1)",
                             "gates_v6/TYPE_SETS_v6.json (LOCK_prereg_v6)", "posthoc_v6 (LOCK_posthoc_v6)", "forward_v2/SHORTLIST.csv (LOCK_forward_v2)"],
           "untracked_inputs": unt, "code": ["ledger/scripts/thirdfly_v1.py", "ledger/src/brainir_ledger/banc.py", "ledger/src/brainir_ledger/screens6.py",
                                             "ledger/src/brainir_ledger/overlap6.py", "ledger/src/brainir_ledger/agree.py"]}
    (OUT / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n")
    print(json.dumps({"B4": res["B4_validity"], "C3_first_line": res["C3"]["first_line_words"]}, default=str))


if __name__ == "__main__":
    if "--validity" in sys.argv:
        print(json.dumps(run(validity_only=True), indent=1))
    else:
        build()
