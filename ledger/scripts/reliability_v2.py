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


def cmd_a() -> None:
    gha4.require_freeze("Part A analysis")
    hf = half_flies()
    fm, fc = MR.fly("MANC"), MR.fly("MaleCNS")
    hm, hc = fm.halves(), fc.halves()
    tm, tc = sorted(hm["L"]), sorted(hc["L"])
    for k, df in hf.items():
        _check_complete(df, tm if k.startswith("MANC") else tc, range(16), k)
    common = sorted(set(tm) & set(tc))
    corrected_types = sorted(t for t in tc if any(fc.corrected[i] for i in hc["L"][t] + hc["R"][t]))
    unc = sorted(set(tc) - set(corrected_types))

    def cmp(a, b, types, mc=None):
        return AG.compare(hf[a], hf[b], types, H16, member_counts=mc, n_boot=10000, seed=SEED_BOOT)

    mc_m = {t: (len(hm["L"][t]), len(hm["R"][t])) for t in tm}
    mc_c = {t: (len(hc["L"][t]), len(hc["R"][t])) for t in tc}
    six = {"MANC-L vs MANC-R": cmp("MANC-L", "MANC-R", tm, mc_m), "MaleCNS-L vs MaleCNS-R": cmp("MCNS-L", "MCNS-R", tc, mc_c),
           "MANC-L vs MaleCNS-L": cmp("MANC-L", "MCNS-L", common), "MANC-R vs MaleCNS-R": cmp("MANC-R", "MCNS-R", common),
           "MANC-L vs MaleCNS-R": cmp("MANC-L", "MCNS-R", common), "MANC-R vs MaleCNS-L": cmp("MANC-R", "MCNS-L", common)}
    extra = {"MaleCNS-L vs MaleCNS-R, uncorrected types": cmp("MCNS-L", "MCNS-R", unc, {t: mc_c[t] for t in unc}) if len(unc) >= 10 else None,
             "n_uncorrected_types": len(unc), "n_corrected_types": len(corrected_types)}
    # reference: run 3's R1 (whole type, B1r vs B2r, 16 seeds) in the cross-half form
    b1 = pd.read_parquet(P2 / "B1r" / "replicates.parquet").rename(columns={"manc_type": "type"})
    b2 = pd.read_parquet(P2 / "B2r" / "replicates.parquet").rename(columns={"manc_type": "type"})
    wc = sorted(set(b1["type"]) & set(b2["type"]))
    ref = AG.compare(b1, b2, wc, H16, n_boot=10000, seed=SEED_BOOT)
    # same-side minus opposite-side cross-fly agreement (point estimate and bootstrap over common types)
    same = (six["MANC-L vs MaleCNS-L"]["rho_x"] + six["MANC-R vs MaleCNS-R"]["rho_x"]) / 2
    opp = (six["MANC-L vs MaleCNS-R"]["rho_x"] + six["MANC-R vs MaleCNS-L"]["rho_x"]) / 2
    ssd = _same_minus_opposite(hf, common)
    # A3 one bad side
    a3 = {}
    for fly, tag, types in (("MANC", "MANC", tm), ("MaleCNS", "MCNS", tc)):
        L, R = hf[f"{tag}-L"], hf[f"{tag}-R"]
        sl, sr = AG.type_scores(L, None, types), AG.type_scores(R, None, types)
        d = (sl - sr)
        nz = d[d != 0]
        w = wilcoxon(nz) if len(nz) >= 10 else None
        fav = (nz > 0).mean() if len(nz) else float("nan")
        a3[fly] = {"L": _dist(sl, L), "R": _dist(sr, R), "n_types": len(types), "nonzero_differences": int(len(nz)),
                   "share_favouring_L": float(fav), "wilcoxon_p": float(w.pvalue) if w is not None else None,
                   "weaker_everywhere": (None if w is None else
                                         ("R" if (w.pvalue < 0.01 and fav >= 0.6) else "L" if (w.pvalue < 0.01 and fav <= 0.4) else "neither"))}
    out = {"marking": "pre-registered (PREREG v4 Part A)", "seeds": "0..15; halves 0..7 / 8..15",
           "type_counts": {"MANC": fm.type_counts(), "MaleCNS": fc.type_counts(), "common": len(common)},
           "six_agreements": six, "extra": extra, "reference_R1_whole_type_cross_fly": ref,
           "same_side_minus_opposite_side_cross_fly": {"same": same, "opposite": opp, **ssd},
           "one_bad_side": a3}
    _out("A.json", _clean(out))
    # G9 informative and analysed sets
    nonzero = set()
    for k, df in hf.items():
        types = tm if k.startswith("MANC") else tc
        s = AG.type_scores(df, None, types)
        nonzero |= set(s.index[s > 0])
    both = sorted(set(tm) & set(tc))
    inf = sorted(t for t in nonzero if t in both)
    rest = sorted(set(both) - set(inf))
    rng = np.random.default_rng(SEED_SAMPLE)
    extra50 = sorted(rng.choice(rest, size=min(50, len(rest)), replace=False).tolist()) if rest else []
    _out("ANALYSED_SET.json", {"rule": "PREREG v4 G9: informative (score > 0 in at least one half-fly, 16 seeds) among types matched in "
                                       "both flies, plus 50 others drawn with default_rng(20261402)",
                               "informative": inf, "random_extra": extra50, "analysed": sorted(inf + extra50),
                               "n_informative": len(inf), "n_analysed": len(inf) + len(extra50),
                               "informative_not_in_both_flies": sorted(nonzero - set(both))})


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


def main() -> None:
    cmd = sys.argv[1:2]
    if cmd == ["a0"]:
        cmd_a0()
    elif cmd == ["a"]:
        cmd_a()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
