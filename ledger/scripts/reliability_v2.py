"""Reliability v2 analyses (PREREG v4 Parts A0 and A; Blocks and fixes are added as their data arrive). Descriptive; no label.

    uv run --project ledger --no-sync python ledger/scripts/reliability_v2.py a0      # -> reliability_v2/A0.json
    uv run --project ledger --no-sync python ledger/scripts/reliability_v2.py a       # -> reliability_v2/A.json, WIRING_A.json, ANALYSED_SET.json

Every output is written once (mode "x"); a re-run refuses. Every command refuses before the tag ledger-prereg-v4.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.stats import wilcoxon

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))
import gha4  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import agree as AG  # noqa: E402
from brainir_ledger import mirror as MR  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

REL2 = RESEARCH / "reliability_v2"
P1 = RESEARCH / "predictions"
P2 = RESEARCH / "predictions_v2"
H16 = (list(range(8)), list(range(8, 16)))
H8 = (list(range(4)), list(range(4, 8)))
SEED_BOOT = 20261401
SEED_SAMPLE = 20261402


def _f(x) -> float:
    """None (agree's undefined) -> NaN, so arithmetic on undefined values gives NaN instead of a TypeError."""
    return float("nan") if x is None else float(x)


def _out(name: str, obj) -> None:
    REL2.mkdir(parents=True, exist_ok=True)
    with open(REL2 / name, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, indent=1, default=lambda x: None if isinstance(x, float) and np.isnan(x) else str(x)) + "\n")
    print("wrote", name, flush=True)


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


# ------------------------------------------------------------------------------------------------------------------ Part A0
def _neuron_scores(rep: pd.DataFrame, col: str, subset) -> pd.Series:
    """Per neuron (bodyId): mean score over usable replicates in `subset` (values of `col`), 0 if none (G5 / PREREG v1 3.2)."""
    r = rep[rep[col].isin(list(subset))]
    m = r[r["usable"]].groupby("bodyId")["score"].mean()
    return m.reindex(sorted(rep["bodyId"].unique())).fillna(0.0)


def _side_scores(neur: pd.Series, members: dict[str, list[int]]) -> pd.Series:
    return pd.Series({t: float(np.mean([neur[b] for b in bs])) for t, bs in members.items()})


def cmd_a0() -> None:
    gha4.require_freeze("Part A0")
    root = N.full_cord().table.set_index("bodyId")["rootSide"].map({"LHS": "L", "RHS": "R"})
    out = {"note": "PREREG v4 Part A0: this screen stimulates one neuron and reads out both front legs together, unlike Part A.",
           "marking": "pre-registered (PREREG v4 Part A0)"}
    for arm, col, halves, path in (("A0", "replicate", (range(64), range(64, 128)), P1 / "A0" / "replicates.parquet"),
                                   ("B0", "seed", (range(8), range(8, 16)), P1 / "B0" / "replicates.parquet")):
        rep = pd.read_parquet(path)
        if arm == "A0":
            wide = rep.pivot(index="bodyId", columns="replicate", values="score").to_numpy()
            dup = sum(1 for i in range(wide.shape[1]) for j in range(i + 1, wide.shape[1]) if np.allclose(wide[:, i], wide[:, j], equal_nan=True))
            out["A0_identical_replicate_columns"] = int(dup)
        bt = rep.drop_duplicates("bodyId").set_index("bodyId")["manc_type"]
        side = {int(b): root.get(int(b)) for b in bt.index}
        by_type: dict[str, dict[str, list[int]]] = {}
        for b, t in bt.items():
            s = side[int(b)]
            if s in ("L", "R"):
                by_type.setdefault(str(t), {"L": [], "R": []})[s].append(int(b))
        matched = {t: d for t, d in by_type.items() if d["L"] and d["R"]}
        one = {t: d for t, d in matched.items() if len(d["L"]) == 1 and len(d["R"]) == 1}
        res = {"types_total": int(bt.nunique()), "matched": len(matched), "one_member_each_side": len(one),
               "unsided_members": int(sum(1 for b in bt.index if side[int(b)] not in ("L", "R")))}
        full = _neuron_scores(rep, col, list(halves[0]) + list(halves[1]))
        h1, h2 = _neuron_scores(rep, col, halves[0]), _neuron_scores(rep, col, halves[1])
        for label, sub in (("primary_one_member_each_side", one), ("all_matched_types", matched)):
            types = sorted(sub)
            L = {t: sub[t]["L"] for t in types}
            R = {t: sub[t]["R"] for t in types}
            vec = {k: (_side_scores(v, L).reindex(types), _side_scores(v, R).reindex(types)) for k, v in (("full", full), ("1", h1), ("2", h2))}
            mc = {t: (len(sub[t]["L"]), len(sub[t]["R"])) for t in types}
            r = AG.compare_vectors(vec["full"][0], vec["full"][1], vec["1"][0], vec["2"][0], vec["1"][1], vec["2"][1], member_counts=mc,
                                   n_boot=10000, seed=SEED_BOOT)
            res[label] = r
        out[arm] = res
    a = out["A0"]["primary_one_member_each_side"]
    out["decision"] = {"rule": "PREREG v4 A0 decision (G7 words on A0's primary comparison)", "words": a.get("words"),
                       "authors_data_agree_at_ceiling": a.get("words") == "at the ceiling"}
    _out("A0.json", _clean(out))


# ------------------------------------------------------------------------------------------------------------------- Part A
def _rep_df(results) -> pd.DataFrame:
    rows = [{"type": r["key"].split("|")[1], "seed": int(r["seed"]), "usable": bool(r.get("usable")), "score": r.get("score"),
             "n_active_all": r.get("n_active_all"), "n_high_fr": r.get("n_high_fr"), "current": r.get("current")}
            for r in results if "error" not in r]
    return pd.DataFrame(rows)


def half_flies() -> dict[str, pd.DataFrame]:
    out = {}
    for fly, tag in (("MANC", "MANC"), ("MaleCNS", "MCNS")):
        pa = gha4.part_a_results(fly)
        for s in ("L", "R"):
            out[f"{tag}-{s}"] = _rep_df([r for (side, _t, _s), r in pa.items() if side == s])
    return out


def _outcome(r) -> str:
    if r["usable"]:
        return "accepted"
    return "too_strong" if (r["n_active_all"] or 0) > 1500 or (r["n_high_fr"] or 0) > 200 else "too_weak"


def _check_complete(df: pd.DataFrame, types, seeds, name) -> None:
    have = set(zip(df["type"], df["seed"]))
    miss = [(t, s) for t in types for s in seeds if (t, s) not in have]
    if miss:
        raise SystemExit(f"{name}: {len(miss)} replicates missing, e.g. {miss[:3]}; refused")


def _a3(hf: dict, tag: str, types: list[str]) -> dict:
    """A3: per-type distributions, drivers, tuner outcomes; Wilcoxon signed-rank over types with a non-zero L - R difference (only
    with at least 10 such types); 'weaker everywhere' if p < 0.01 and at least 60 % of the non-tied types favour the other side."""
    L, R = hf[f"{tag}-L"], hf[f"{tag}-R"]
    sl, sr = AG.type_scores(L, None, types), AG.type_scores(R, None, types)
    d = (sl - sr)
    nz = d[d != 0]
    w = wilcoxon(nz) if len(nz) >= 10 else None
    fav = (nz > 0).mean() if len(nz) else float("nan")
    return {"L": _dist(sl, L[L["type"].isin(types)]), "R": _dist(sr, R[R["type"].isin(types)]), "n_types": len(types),
            "nonzero_differences": int(len(nz)), "share_favouring_L": float(fav), "wilcoxon_p": float(w.pvalue) if w is not None else None,
            "weaker_everywhere": (None if w is None else
                                  ("R" if (w.pvalue < 0.01 and fav >= 0.6) else "L" if (w.pvalue < 0.01 and fav <= 0.4) else "neither"))}


def _six(hf: dict, tm: list[str], tc: list[str], mc_m: dict, mc_c: dict) -> dict:
    common = sorted(set(tm) & set(tc))

    def cmp(a, b, types, mc=None):
        return AG.compare(hf[a], hf[b], types, H16, member_counts=mc, n_boot=10000, seed=SEED_BOOT)
    return {"MANC-L vs MANC-R": cmp("MANC-L", "MANC-R", tm, {t: mc_m[t] for t in tm}),
            "MaleCNS-L vs MaleCNS-R": cmp("MCNS-L", "MCNS-R", tc, {t: mc_c[t] for t in tc}),
            "MANC-L vs MaleCNS-L": cmp("MANC-L", "MCNS-L", common), "MANC-R vs MaleCNS-R": cmp("MANC-R", "MCNS-R", common),
            "MANC-L vs MaleCNS-R": cmp("MANC-L", "MCNS-R", common), "MANC-R vs MaleCNS-L": cmp("MANC-R", "MCNS-L", common),
            "n_types": {"MANC": len(tm), "MaleCNS": len(tc), "common": len(common)}}


def cmd_a() -> None:
    """PREREG v4 A2-A3 on the primary type sets (homolog-consistent matched types, G9) and, as secondary, on all matched types; with
    the sensitivity sets of G3 (MaleCNS types without a corrected member; MANC types without a member whose root side differs from
    its output side)."""
    gha4.require_freeze("Part A analysis")
    hf = half_flies()
    fm, fc = MR.fly("MANC"), MR.fly("MaleCNS")
    hm, hc = fm.halves(), fc.halves()
    tm_all, tc_all = sorted(hm["L"]), sorted(hc["L"])
    for k, df in hf.items():
        _check_complete(df, tm_all if k.startswith("MANC") else tc_all, range(16), k)
    ts_ = gha4.type_sets()   # fixed before the freeze (re-check finding 6)
    tm, tc = ts_["MANC"]["primary_homolog_consistent"], ts_["MaleCNS"]["primary_homolog_consistent"]
    if sorted(ts_["MANC"]["matched"]) != tm_all or sorted(ts_["MaleCNS"]["matched"]) != tc_all:
        raise SystemExit("the matched types differ from gates_v4/TYPE_SETS.json; refused")
    mc_m = {t: (len(hm["L"][t]), len(hm["R"][t])) for t in tm_all}
    mc_c = {t: (len(hc["L"][t]), len(hc["R"][t])) for t in tc_all}
    unc = sorted(set(tc) & set(ts_["MaleCNS"]["uncorrected"]))
    conc = sorted(set(tm) & set(ts_["MANC"]["side_concordant"]))
    six = _six(hf, tm, tc, mc_m, mc_c)
    six_all = _six(hf, tm_all, tc_all, mc_m, mc_c)
    sens = {"n_maleCNS_uncorrected_primary_types": len(unc), "n_MANC_side_concordant_primary_types": len(conc)}
    if len(unc) >= 10:
        c_unc = sorted(set(tm) & set(unc))
        sens["MaleCNS_uncorrected"] = {
            "MaleCNS-L vs MaleCNS-R": AG.compare(hf["MCNS-L"], hf["MCNS-R"], unc, H16, member_counts={t: mc_c[t] for t in unc}, n_boot=10000, seed=SEED_BOOT),
            **({f"{a} vs {b}": AG.compare(hf[x], hf[y], c_unc, H16, n_boot=10000, seed=SEED_BOOT)
                for (a, b, x, y) in (("MANC-L", "MaleCNS-L", "MANC-L", "MCNS-L"), ("MANC-R", "MaleCNS-R", "MANC-R", "MCNS-R"),
                                     ("MANC-L", "MaleCNS-R", "MANC-L", "MCNS-R"), ("MANC-R", "MaleCNS-L", "MANC-R", "MCNS-L"))}
               if len(c_unc) >= 10 else {})}
    if len(conc) >= 10:
        sens["MANC_side_concordant"] = {"MANC-L vs MANC-R": AG.compare(hf["MANC-L"], hf["MANC-R"], conc, H16, member_counts={t: mc_m[t] for t in conc},
                                                                       n_boot=10000, seed=SEED_BOOT),
                                        "one_bad_side": _a3(hf, "MANC", conc)}
    # reference: run 3's R1 (whole type, B1r vs B2r, 16 seeds) in the cross-half form
    b1 = pd.read_parquet(P2 / "B1r" / "replicates.parquet").rename(columns={"manc_type": "type"})
    b2 = pd.read_parquet(P2 / "B2r" / "replicates.parquet").rename(columns={"manc_type": "type"})
    wc = sorted(set(b1["type"]) & set(b2["type"]))
    ref = AG.compare(b1, b2, wc, H16, n_boot=10000, seed=SEED_BOOT)
    common = sorted(set(tm) & set(tc))
    same = (_f(six["MANC-L vs MaleCNS-L"]["primary"]["rho_x"]) + _f(six["MANC-R vs MaleCNS-R"]["primary"]["rho_x"])) / 2
    opp = (_f(six["MANC-L vs MaleCNS-R"]["primary"]["rho_x"]) + _f(six["MANC-R vs MaleCNS-L"]["primary"]["rho_x"])) / 2
    ssd = _same_minus_opposite(hf, common)
    a3 = {"MANC": _a3(hf, "MANC", tm), "MaleCNS": _a3(hf, "MCNS", tc)}
    a3_all = {"MANC": _a3(hf, "MANC", tm_all), "MaleCNS": _a3(hf, "MCNS", tc_all)}
    words = six["MANC-L vs MANC-R"]["words"]
    out = {"marking": "pre-registered (PREREG v4 Part A)", "seeds": "0..15; halves 0..7 / 8..15",
           "type_counts": {"MANC": fm.type_counts(), "MaleCNS": fc.type_counts(), "MANC_homolog_consistent": len(tm),
                           "MaleCNS_homolog_consistent": len(tc), "common_primary": len(common)},
           "six_agreements_primary_homolog_consistent": six, "six_agreements_all_matched_types": six_all, "sensitivity_sets": sens,
           "reference_R1_whole_type_cross_fly": ref,
           "same_side_minus_opposite_side_cross_fly": {"same": same, "opposite": opp, **ssd},
           "one_bad_side": a3, "one_bad_side_all_matched_types": a3_all,
           "A7_branch": {"MANC_left_right_words": words,
                         "blocks_on": "cross-fly gap (B5)" if words == "at the ceiling" else "left-right gap"}}
    _out("A.json", _clean(out))
    # G9 informative and analysed sets
    nonzero = set()
    for k, df in hf.items():
        types = tm_all if k.startswith("MANC") else tc_all
        s = AG.type_scores(df, None, types)
        nonzero |= set(s.index[s > 0])
    both = sorted(set(tm_all) & set(tc_all))
    inf = sorted(nonzero)
    rest = sorted(set(both) - set(inf))
    rng = np.random.default_rng(SEED_SAMPLE)
    extra50 = sorted(rng.choice(rest, size=min(50, len(rest)), replace=False).tolist()) if rest else []
    ana = sorted(set(inf) | set(extra50))
    _out("ANALYSED_SET.json", {"rule": "PREREG v4 G9: informative = score > 0 in at least one half-fly (16 seeds); analysed = informative "
                                       "plus 50 of the remaining types matched in both flies, drawn with default_rng(20261402); each fly "
                                       "uses the analysed types matched in it",
                               "informative": inf, "random_extra": extra50, "analysed": ana,
                               "n_informative": len(inf), "n_analysed": len(ana),
                               "n_analysed_matched_MANC": len(set(ana) & set(tm_all)), "n_analysed_matched_MaleCNS": len(set(ana) & set(tc_all)),
                               "n_analysed_matched_both": len(set(ana) & set(both)),
                               "n_analysed_primary_MANC": len(set(ana) & set(tm)), "n_analysed_primary_MaleCNS": len(set(ana) & set(tc))})


def _dist(s: pd.Series, df: pd.DataFrame) -> dict:
    oc = df.apply(_outcome, axis=1).value_counts().to_dict()
    return {"median": float(s.median()), "mean": float(s.mean()), "share_nonzero": float((s > 0).mean()),
            "drivers": int((s >= 0.5).sum()), "tuner_outcomes": {k: int(v) for k, v in oc.items()}}


def _same_minus_opposite(hf, types, n_boot=10000) -> dict:
    v = {k: {h: AG.type_scores(hf[k], H16[i], types).to_numpy() for i, h in enumerate("12")} for k in ("MANC-L", "MANC-R", "MCNS-L", "MCNS-R")}

    def rx(a, b, idx):
        return (AG.spearman(v[a]["1"][idx], v[b]["2"][idx]) + AG.spearman(v[a]["2"][idx], v[b]["1"][idx])) / 2

    def stat(idx):
        return (rx("MANC-L", "MCNS-L", idx) + rx("MANC-R", "MCNS-R", idx)) / 2 - (rx("MANC-L", "MCNS-R", idx) + rx("MANC-R", "MCNS-L", idx)) / 2
    n = len(types)
    point = stat(np.arange(n))
    rng = np.random.default_rng(SEED_BOOT)
    bs = [stat(ix) for ix in rng.integers(0, n, size=(n_boot, n))]
    bs = np.array([b for b in bs if np.isfinite(b)])
    return {"difference": point, "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], "n_boot_used": int(len(bs))}


# ----------------------------------------------------------------------------------------------------------- Part A4 wiring
def _rho_pair(a: pd.Series, b: pd.Series, types) -> dict:
    return {"n": len(types), "spearman": AG.spearman(a.reindex(types).to_numpy(), b.reindex(types).to_numpy())}


def _log_stats(a: np.ndarray, b: np.ndarray) -> dict:
    both = (a > 0) & (b > 0)
    la, lb = np.log(a[both]), np.log(b[both])
    one = (a > 0) ^ (b > 0)
    return {"pairs": int(((a > 0) | (b > 0)).sum()), "present_both": int(both.sum()), "present_one_side_only": int(one.sum()),
            "share_one_side_only": float(one.sum() / max(1, ((a > 0) | (b > 0)).sum())),
            "spearman_log_both": AG.spearman(la, lb), "pearson_log_both": float(np.corrcoef(la, lb)[0, 1]) if both.sum() > 2 else None}


def _mncs_manc_types(fc) -> np.ndarray:
    import glob  # noqa: PLC0415

    import pyarrow.feather as feather  # noqa: PLC0415

    from brainir import paths  # noqa: PLC0415

    ann = feather.read_table(glob.glob(str(paths.data_root() / "raw" / "external" / "malecns_v1.0_body_annotations" / "*.feather"))[0],
                             columns=["bodyId", "mancBodyid", "mancType"]).to_pandas().set_index("bodyId")
    fl = N.front_leg().table
    body2type = {**dict(zip(N.full_cord().table["bodyId"].astype(int), N.full_cord().table["type"])), **dict(zip(fl["bodyId"].astype(int), fl["type"]))}
    out = []
    for b in fc.net.table["bodyId"].astype(np.int64):
        t = None
        if int(b) in ann.index:
            r = ann.loc[int(b)]
            if pd.notna(r["mancBodyid"]) and int(r["mancBodyid"]) in body2type and pd.notna(body2type[int(r["mancBodyid"])]):
                t = str(body2type[int(r["mancBodyid"])])
            elif pd.notna(r["mancType"]):
                t = str(r["mancType"])
        out.append(t)
    return np.array(out, dtype=object)


def _type_blocks(C: sp.csr_matrix, types: np.ndarray, side: np.ndarray) -> dict:
    Cc = C.tocoo()
    out: dict = {}
    for i, j, v in zip(Cc.row, Cc.col, Cc.data):
        a, b = types[j], types[i]
        if a is None or b is None:
            continue
        si, sj = side[i], side[j]
        rel = "same" if (si in ("L", "R") and si == sj) else ("opposite" if (si in ("L", "R") and sj in ("L", "R")) else "unsided")
        out[(a, b, rel)] = out.get((a, b, rel), 0.0) + float(v)
    return out


def _compare_blocks(x: dict, y: dict) -> dict:
    keys = sorted(set(x) | set(y))
    a = np.array([x.get(k, 0.0) for k in keys])
    b = np.array([y.get(k, 0.0) for k in keys])
    return _log_stats(a, b)


def cmd_a4() -> None:
    gha4.require_freeze("Part A4")
    from brainir_ledger import baselines as BL  # noqa: PLC0415
    from brainir_ledger import fixes as FX  # noqa: PLC0415

    fm, fc = MR.fly("MANC"), MR.fly("MaleCNS")
    hm, hc = fm.halves(), fc.halves()
    tm, tc = sorted(hm["L"]), sorted(hc["L"])
    common = sorted(set(tm) & set(tc))
    sv = {}
    for f, h, tag in ((fm, hm, "MANC"), (fc, hc, "MCNS")):
        W = sp.csr_matrix(f.net.W, dtype=np.float64)
        for s in ("L", "R"):
            sv[f"{tag}-{s}"] = BL.compute(f.C, W, f.readout_side(s), h[s], []).set_index("manc_type")
    cols = [c for c in BL.BASELINES if c != "S8_informed"]
    pairs = {"MANC-L vs MANC-R": ("MANC-L", "MANC-R", tm), "MaleCNS-L vs MaleCNS-R": ("MCNS-L", "MCNS-R", tc),
             "MANC-L vs MaleCNS-L": ("MANC-L", "MCNS-L", common), "MANC-R vs MaleCNS-R": ("MANC-R", "MCNS-R", common),
             "MANC-L vs MaleCNS-R": ("MANC-L", "MCNS-R", common), "MANC-R vs MaleCNS-L": ("MANC-R", "MCNS-L", common)}
    summaries = {p: {c: _rho_pair(sv[a][c], sv[b][c], ts) for c in cols} for p, (a, b, ts) in pairs.items()}
    single = {}
    for f, tag in ((fm, "MANC"), (fc, "MaleCNS")):
        mm = MR.mirror_map(f)
        m = mm.m[: f.n]
        matched = np.isin(mm.status[: f.n], MR.MATCHED)
        C = sp.csr_matrix(f.C)
        # the mirror image on the real neurons only: an unmatched neuron's partner is a ghost slot (index >= n), and unmatched
        # neurons are left out below anyway (amendment: indexing C with ghost indices raised IndexError)
        mreal = np.where(matched, m, np.arange(f.n))
        Cm = C[mreal][:, mreal].tocsr()
        U = (C + Cm).tocoo()
        keep = matched[U.row] & matched[U.col]
        r, c = U.row[keep], U.col[keep]
        mr, mc = m[r], m[c]
        canon = (r < mr) | ((r == mr) & (c < mc))   # each unordered pair once
        r, c, mr, mc = r[canon], c[canon], mr[canon], mc[canon]
        a = np.asarray(C[r, c]).ravel()
        b = np.asarray(C[mr, mc]).ravel()
        rec = _log_stats(a, b)
        if tag == "MANC":
            C1 = FX.manc_raw_counts()
            one = (a > 0) ^ (b > 0)
            ar, ac = np.where(a[one] > 0, mr[one], r[one]), np.where(a[one] > 0, mc[one], c[one])
            raw = np.asarray(C1[ar, ac]).ravel()
            rec["one_sided_absent_partner_raw_1_to_4"] = int(((raw >= 1) & (raw <= 4)).sum())
            rec["one_sided_absent_partner_raw_0"] = int((raw == 0).sum())
            rec["share_one_sided_only_because_of_floor"] = float(((raw >= 1) & (raw <= 4)).mean()) if len(raw) else None
        single[tag] = rec
    tmanc = np.array([None if pd.isna(x) else str(x) for x in fm.net.table["type"]], dtype=object)
    tmc = _mncs_manc_types(fc)
    bm, bc = _type_blocks(fm.C, tmanc, fm.side), _type_blocks(fc.C, tmc, fc.side)
    by_rel = {rel: _compare_blocks({k: v for k, v in bm.items() if k[2] == rel}, {k: v for k, v in bc.items() if k[2] == rel})
              for rel in ("same", "opposite", "unsided")}
    pm, pc = {}, {}
    for k, v in bm.items():
        pm[(k[0], k[1])] = pm.get((k[0], k[1]), 0.0) + v
    for k, v in bc.items():
        pc[(k[0], k[1])] = pc.get((k[0], k[1]), 0.0) + v
    out = {"marking": "pre-registered (PREREG v4 A4); wiring only, deterministic (no ceiling)",
           "summaries_S1_S7_full_spearman": summaries, "single_connections": single,
           "type_to_type_across_flies": {"pooled_sides": _compare_blocks(pm, pc), "by_side_relation": by_rel,
                                         "malecns_neurons_with_manc_type": int(sum(t is not None for t in tmc)), "malecns_neurons": int(len(tmc))}}
    _out("WIRING_A4.json", _clean(out))


# ------------------------------------------------------------------------------------------------------- Part A5 descriptive
def cmd_a5() -> None:
    gha4.require_freeze("Part A5")
    import gha3  # noqa: PLC0415
    import predict_h1 as PH  # noqa: PLC0415

    from brainir_ledger import authors as AU  # noqa: PLC0415
    from brainir_ledger import groups_h1 as GH  # noqa: PLC0415
    from brainir_ledger import legs as L  # noqa: PLC0415

    res, _ = PH._results("hsens-run3")
    prim, _ = PH._results("hm-run3")
    masks, _ = PH._masks("hsens-run3")
    fc_ = N.full_cord()
    units = GH.load_units()
    plan = gha3.sens_plan(fc_)
    dims_by = {}
    for v in ("L", "R"):
        arm = f"H-M-S-{v}"
        gv = gha3._unit_groups(fc_, v)
        nm = {u: len(g) for u, g in gv.items()}
        for label, seeds in (("full", {0, 1, 2, 3}), ("1", {0, 1}), ("2", {2, 3})):
            by, byp = PH._by_arm(res, seeds), PH._by_arm(prim, seeds)["H-M"]
            ra = {u: (by[arm].get(u, []) if plan[v][u] == "run" else byp.get(u, []) if plan[v][u] == "same_as_primary" else []) for u in units}
            pred, _ = GH.arm_tables(ra, units, masks, nm)
            dims_by[(v, label)] = pred.set_index("unit")[list(GH.DIMS)]
    cells = lambda d: d.to_numpy().ravel()  # noqa: E731
    full = AG.spearman(cells(dims_by[("L", "full")]), cells(dims_by[("R", "full")]))
    rx = (AG.spearman(cells(dims_by[("L", "1")]), cells(dims_by[("R", "2")])) + AG.spearman(cells(dims_by[("L", "2")]), cells(dims_by[("R", "1")]))) / 2
    c = (AG.spearman(cells(dims_by[("L", "1")]), cells(dims_by[("L", "2")])) + AG.spearman(cells(dims_by[("R", "1")]), cells(dims_by[("R", "2")]))) / 2
    per_dim = {d: AG.spearman(dims_by[("L", "full")][d].to_numpy(), dims_by[("R", "full")][d].to_numpy()) for d in GH.DIMS}
    hl = {"cells": int(dims_by[("L", "full")].size), "full_spearman_cells": full, "cross_half_cells": rx, "ceiling_cells": c,
          "ratio": rx / c if c else None, "per_dimension_full_spearman": per_dim, "seeds": "0..3; halves {0,1} / {2,3}"}
    # DNg100 per-leg asymmetry: authors' full-cord replicates and run 1's G3 runs (both DNg100 at 380, T = 2 s)
    files = AU.fetch()
    a_sc = pd.read_csv(files["full_scores_alllegs"], index_col=0)
    g3 = sorted([r for r in read_log(data_dir() / "calibration" / "g3_v1" / "results.pkl") if "error" not in r],
                key=lambda r: int(r["key"].rsplit("s", 1)[1]))
    ours = pd.DataFrame({leg: [r["extras"]["legs"][leg]["score"] for r in g3] for leg in L.LEGS})
    asym = {}
    for who, df in (("authors_33195857", a_sc), ("ours_g3_v1", ours)):
        rec = {"n_replicates": int(len(df))}
        for seg in ("T1", "T2", "T3"):
            l, r = df[f"{seg}L"].to_numpy(float), df[f"{seg}R"].to_numpy(float)
            d = l - r
            nz = d[d != 0]
            w = wilcoxon(nz) if len(nz) >= 6 else None
            rec[seg] = {"median_L": float(np.median(l)), "median_R": float(np.median(r)), "frac_ge_0_5_L": float((l >= 0.5).mean()),
                        "frac_ge_0_5_R": float((r >= 0.5).mean()), "median_L_minus_R": float(np.median(d)),
                        "wilcoxon_p": float(w.pvalue) if w is not None else None}
        asym[who] = rec
    _out("A5.json", _clean({"marking": "pre-registered (PREREG v4 A5); descriptive, existing locked runs", "hemilineage_L_vs_R": hl,
                            "dng100_per_leg_asymmetry": asym}))


def main() -> None:
    cmd = sys.argv[1:2]
    if cmd == ["a0"]:
        cmd_a0()
    elif cmd == ["a"]:
        cmd_a()
    elif cmd == ["a4"]:
        cmd_a4()
    elif cmd == ["a5"]:
        cmd_a5()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
