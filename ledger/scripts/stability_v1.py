"""PREREG v5 Part S (confirmatory) and Part T (descriptive): stability of whole-type hits under synapse-count noise in MANC, the exact
test of whether it predicts replication in MaleCNS, and the single-copy screen in both flies.

    uv run --project ledger --no-sync python ledger/scripts/stability_v1.py power [--copies 16]   # S7 table (no data)
    uv run --project ledger --no-sync python ledger/scripts/stability_v1.py part-s [--copies 16]  # -> replication_v1/S_*
    uv run --project ledger --no-sync python ledger/scripts/stability_v1.py part-t                # -> replication_v1/T_*

Inputs: the Part S / Part T campaign results (`data/ledger/replication_v1/GHA_<campaign>/results.pkl`, collected from GitHub Actions)
and the locked per-type tables (`pertype_v1/`). Outputs are written once.
"""

from __future__ import annotations

import itertools
import json
import sys
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

PERTYPE = RESEARCH / "pertype_v1"
OUT = RESEARCH / "replication_v1"
DRIVER = 0.5
ALPHA = 0.05
PS_CAMPAIGNS = ("ps-b1-run5", "ps-b2-run5", "ps-b3-run5", "ps-b4-run5")          # copy blocks: 1-4, 5-8, 9-12, 13-16 (--k 1..4)
PT_CAMPAIGNS = ("pt-manc-run5", "pt-mcns-run5")
EPS = 1e-12


def _scores(name: str) -> pd.Series:
    return pd.read_csv(PERTYPE / f"{name}.csv", dtype={"manc_type": str}).set_index("manc_type")["score"]


def results(campaigns, root: Path | None = None) -> list[dict]:
    """The collected results of the campaigns; S8: a packed key still without a result after the re-runs (collection stores no error
    record) is added as an error placeholder, counted as a not-usable seed and listed."""
    import gha as G  # noqa: PLC0415

    out = []
    for c in campaigns:
        p = (root or data_dir()) / "replication_v1" / f"GHA_{c}" / "results.pkl"
        if not p.exists():
            raise SystemExit(f"{p} missing (collect the campaign first)")
        got = [r for r in read_log(p) if "|" in str(r.get("key", ""))]
        have = {r["key"] for r in got}
        man = G.GHA / c / "manifest.json"
        if man.exists():
            got += [{"key": k, "error": "missing after re-runs (S8)"} for k in json.loads(man.read_text())["keys"] if k not in have]
        out += got
    return out


def collected_copy_campaigns(root: Path | None = None) -> list[str]:
    return [c for c in PS_CAMPAIGNS if ((root or data_dir()) / "replication_v1" / f"GHA_{c}" / "results.pkl").exists()]


def type_score(rs: list[dict]) -> float:
    """G5: mean score over the usable replicates, 0 if none."""
    u = [float(r.get("score") or 0.0) for r in rs if r.get("usable")]
    return float(np.mean(u)) if u else 0.0


def copy_scores(res: list[dict], n_copies: int = 16, seeds=range(8)) -> pd.DataFrame:
    """S4: rows (type, copy): the copy score over seeds 0..7 (G1), the number of usable seeds, the fraction rhythmic (PREREG v4 G5) and the
    number of jobs that ended with an error (S8: after the re-runs they count as not usable; they are listed by `part_s`)."""
    by: dict[tuple[str, int], list[dict]] = {}
    for r in res:
        pre, t, s = r["key"].split("|")
        c = int(pre.split("-c")[1])
        if c <= n_copies and int(s[1:]) in set(seeds):
            by.setdefault((t, c), []).append(r)
    rows = []
    for (t, c), rs in sorted(by.items()):
        ok = [r for r in rs if "error" not in r]
        rows.append({"manc_type": t, "copy": c, "n_seeds": len(rs), "n_errors": len(rs) - len(ok), "n_usable": sum(bool(r.get("usable")) for r in ok),
                     "copy_score": type_score(ok), "frac_rhythmic": float(np.mean([bool(r.get("usable")) and float(r.get("score") or 0) >= DRIVER for r in ok] +
                                                                                [False] * (len(rs) - len(ok))))})
    d = pd.DataFrame(rows)
    bad = d[d["n_seeds"] != len(list(seeds))]
    if len(bad):
        raise SystemExit(f"incomplete (type, copy) cells: {bad.head().to_dict('records')}")
    full = d.groupby("manc_type")["copy"].nunique()
    if (full != n_copies).any():
        raise SystemExit(f"types without all {n_copies} copies: {sorted(full[full != n_copies].index)[:5]}")
    return d


def stability(d: pd.DataFrame) -> pd.DataFrame:
    g = d.groupby("manc_type")
    return pd.DataFrame({"stability": g["copy_score"].apply(lambda x: float(np.mean(x >= DRIVER))), "mean_copy_score": g["copy_score"].mean(),
                         "mean_frac_rhythmic": g["frac_rhythmic"].mean(), "n_driver_copies": g["copy_score"].apply(lambda x: int(np.sum(x >= DRIVER))),
                         "n_copies": g["copy"].nunique(), "mean_usable_seeds": g["n_usable"].mean(), "n_errors": g["n_errors"].sum()})


def b1r_reference(seeds=range(8)) -> pd.Series:
    """S5 (v): the real network's B1r type score over the given seeds (G1), from the locked per-seed table."""
    b = pd.read_parquet(RESEARCH / "predictions_v2" / "B1r" / "replicates.parquet")
    b = b[b["seed"].isin(list(seeds))]
    return b.groupby("manc_type").apply(lambda g: float(g.loc[g["usable"].astype(bool), "score"].mean()) if g["usable"].astype(bool).any() else 0.0)


def exact_test(values: dict[str, float], replicated: list[str]) -> dict:
    """S5: exact one-sided rank test (Wilcoxon-Mann-Whitney rank-sum, midranks for ties): the statistic is the sum of the midranks of R
    among the drivers; p = the share of all C(n, |R|) subsets of the drivers whose rank sum is >= R's (ties count as >=)."""
    from scipy.stats import rankdata  # noqa: PLC0415

    names = sorted(values)
    k = len(replicated)
    if k == 0 or k == len(names):
        return {"n": len(names), "k": k, "p": None, "note": "test undefined (no replicated type, or every driver replicated)"}
    v = np.array([values[t] for t in names], float)
    rk = rankdata(v, method="average")
    pos = {t: i for i, t in enumerate(names)}
    obs = float(sum(rk[pos[t]] for t in replicated))
    total = comb(len(names), k)
    ge = sum(1 for idx in itertools.combinations(range(len(names)), k) if rk[list(idx)].sum() >= obs - 1e-9)
    return {"n": len(names), "k": k, "replicated": sorted(replicated), "observed_rank_sum": obs,
            "observed_mean_value": float(np.mean([values[t] for t in replicated])), "n_subsets": total, "n_subsets_ge": ge, "p": ge / total,
            "values": {t: values[t] for t in names}, "midranks": {t: float(rk[pos[t]]) for t in names}}


def min_p_table(n: int, k: int = 3, t_max: int = 8) -> dict:
    """S7: the smallest attainable p when t drivers (the k replicated among them) share the top value: C(t, k) / C(n, k)."""
    return {str(t): comb(t, k) / comb(n, k) for t in range(k, min(t_max, n) + 1)}


def clopper_pearson(x: int, n: int, a: float = 0.05) -> list[float]:
    from scipy.stats import beta  # noqa: PLC0415

    lo = 0.0 if x == 0 else float(beta.ppf(a / 2, x, n - x + 1))
    hi = 1.0 if x == n else float(beta.ppf(1 - a / 2, x + 1, n - x))
    return [lo, hi]


def part_s(res: list[dict], n_copies: int = 16) -> dict:
    import gha5  # noqa: PLC0415  (the frozen type sets: drivers of B1r or A1, and the 40 sampled non-drivers)

    types = gha5.part_s_types()
    d = copy_scores(res, n_copies)
    st = stability(d)
    missing = sorted(set(types["drivers"] + types["nondriver_sample"]) - set(st.index))
    if missing:
        raise SystemExit(f"Part S types without results: {missing}")
    b2 = _scores("B2r")
    conf = pd.read_csv(PERTYPE / "match_confidence.csv", dtype={"manc_type": str}).set_index("manc_type")["confidence"]
    out = {"rule": "PREREG v5 Part S (S4-S7)", "n_copies": n_copies, "copy_seeds": list(gha5.COPY_SEEDS[:n_copies]), "seeds": list(range(8)),
           "per_type": json.loads(st.reset_index().to_json(orient="records")), "tests": {}}
    b1n = pd.read_csv(PERTYPE / "B1r.csv", dtype={"manc_type": str}).set_index("manc_type")["n_usable"]
    ref8, ref16 = b1r_reference(range(8)), _scores("B1r")
    low_usable = sorted(t for t in types["b1r_drivers"] if int(b1n.get(t, 16)) < 12)
    for lst in ("b1r_drivers", "a1_drivers"):
        drivers = types[lst]
        rep = [t for t in drivers if t in b2.index and b2[t] >= DRIVER]

        def col(c, ts):
            return {t: float(st.loc[t, c]) for t in ts}

        sec = {"drivers": drivers, "replicated_from_locked_B2r": rep,
               "primary_stability": exact_test(col("stability", drivers), rep),
               "sensitivity_ii_mean_copy_score": exact_test(col("mean_copy_score", drivers), rep),
               "sensitivity_iii_mean_frac_rhythmic": exact_test(col("mean_frac_rhythmic", drivers), rep),
               "reference_v_B1r_score_seeds0to7": exact_test({t: float(ref8.get(t, 0.0)) for t in drivers}, rep),
               "reference_v_B1r_score_seeds0to15": exact_test({t: float(ref16.get(t, 0.0)) for t in drivers}, rep),
               "min_p_if_tied_at_top": min_p_table(len(drivers), len(rep)) if rep else None}
        keep = [t for t in drivers if t not in low_usable]
        sec["sensitivity_iv_without_low_usable"] = dict(exact_test(col("stability", keep), [t for t in rep if t in keep]), excluded=low_usable)
        hi = [t for t in drivers if conf.get(t) == "high"]
        rep_hi = [t for t in rep if t in hi]
        sec["sensitivity_i_high_confidence"] = (exact_test(col("stability", hi), rep_hi) if len(rep_hi) >= 2
                                                else {"note": f"not run: {len(rep_hi)} replicated type(s) with a high-confidence match (needs at least 2)"})
        out["tests"][lst] = sec
    p = out["tests"]["b1r_drivers"]["primary_stability"]["p"]
    out["verdict_words"] = "Stability predicts replication" if (p is not None and p < ALPHA) else "not shown"
    r8 = out["tests"]["b1r_drivers"]["reference_v_B1r_score_seeds0to7"].get("p")
    r16 = out["tests"]["b1r_drivers"]["reference_v_B1r_score_seeds0to15"].get("p")
    out["reading_vs_score"] = ("adds to the score" if (p is not None and p < ALPHA and r8 is not None and r16 is not None and r8 >= ALPHA and r16 >= ALPHA)
                               else "not distinguishable from the score itself") if (p is not None and p < ALPHA) else "not applicable (S1 not shown)"
    nd = types["nondriver_sample"]
    dn = d[d["manc_type"].isin(nd)]
    n_pairs = int((dn["copy_score"] >= DRIVER).sum())
    any_t = int((st.loc[nd, "n_driver_copies"] >= 1).sum())
    half_t = int((st.loc[nd, "stability"] >= 0.5).sum())
    out["S2_false_hits"] = {"n_types": len(nd), "n_type_copy_pairs": len(dn), "pairs_with_copy_score_ge_0.5": n_pairs,
                            "rate_per_copy": n_pairs / len(dn), "types_with_any_driver_copy": any_t, "types_with_any_driver_copy_ci95": clopper_pearson(any_t, len(nd)),
                            "types_with_stability_ge_0.5": half_t, "types_with_stability_ge_0.5_ci95": clopper_pearson(half_t, len(nd)),
                            "types_with_any_driver_copy_list": sorted(st.loc[nd][st.loc[nd, "n_driver_copies"] >= 1].index)}
    b1s = _scores("B1r")
    for band, sel in (("B1r_non_driver_lt_0.05", lambda t: b1s.get(t, 0) < 0.05), ("B1r_indeterminate_0.05_to_0.5", lambda t: b1s.get(t, 0) >= 0.05)):
        ts = [t for t in nd if sel(t)]
        dd = d[d["manc_type"].isin(ts)]
        out["S2_false_hits"][band] = {"n_types": len(ts), "pairs_ge_0.5": int((dd["copy_score"] >= DRIVER).sum()), "n_pairs": len(dd),
                                      "types_with_any_driver_copy": int((st.loc[ts, "n_driver_copies"] >= 1).sum()) if ts else 0}
    out["errored_jobs_counted_unusable"] = int(d["n_errors"].sum())
    out["power_statement"] = ("Stated before the test ran (PREREG v5 S7): only 3 replicated types; the smallest attainable p is 1/C(15,3) = 0.0022 "
                              "(A1: 1/165); ties at the top raise it, and with seven or more B1r drivers perfectly stable p cannot fall below 0.05; "
                              "a null result is uninformative; a positive result rests on three types, two of them the confirmed drivers and one "
                              "(DNit013) on a low-confidence match.")
    return out, d


def _p(x: dict) -> str:
    return f"{x['p']:.4g}" if isinstance(x, dict) and x.get("p") is not None else (x.get("note", "n/a") if isinstance(x, dict) else "n/a")


def report_s(out: dict) -> str:
    t = out["tests"]["b1r_drivers"]
    L = ["# Part S: does stability under synapse-count noise inside MANC predict replication in MaleCNS? (pre-registered, PREREG v5)", "",
         f"**Verdict (S1, B1r list, exact one-sided rank test): {out['verdict_words']}** (p = {_p(t['primary_stability'])}; "
         f"{t['primary_stability'].get('n_subsets_ge')} of {t['primary_stability'].get('n_subsets')} subsets).", "",
         f"Reading against the real-network score (S5): {out.get('reading_vs_score')}. Ranks run upward (rank 1 = least stable).", "",
         out["power_statement"], "", f"Copies: {out['n_copies']} Poisson copies of MANC's raw counts (floor 5 after resampling), seeds 0..7 each; "
         f"errored jobs counted as not usable: {out.get('errored_jobs_counted_unusable', 0)}.", "",
         "| p values (exact rank test) | B1r list (S1, words) | A1 list (secondary) |", "|---|---|---|"]
    rows = (("S1: stability", "primary_stability"), ("(i) high-confidence matches only", "sensitivity_i_high_confidence"),
            ("(ii) mean copy score", "sensitivity_ii_mean_copy_score"), ("(iii) mean fraction rhythmic", "sensitivity_iii_mean_frac_rhythmic"),
            ("(iv) without low-usability drivers", "sensitivity_iv_without_low_usable"),
            ("(v) reference: real-network B1r score, seeds 0..7", "reference_v_B1r_score_seeds0to7"),
            ("(v) reference: real-network B1r score, seeds 0..15", "reference_v_B1r_score_seeds0to15"))
    for lab, k in rows:
        L.append(f"| {lab} | {_p(out['tests']['b1r_drivers'].get(k))} | {_p(out['tests']['a1_drivers'].get(k))} |")
    L += ["", f"Replicated (locked B2r): {', '.join(t['replicated_from_locked_B2r'])}. Excluded in (iv): "
          f"{', '.join(t['sensitivity_iv_without_low_usable'].get('excluded', [])) or 'none'}.", "",
          "| type | stability | mean copy score | mean fraction rhythmic | mean usable seeds | B1r driver | A1 driver | replicated |",
          "|---|---|---|---|---|---|---|---|"]
    b1, a1 = set(out["tests"]["b1r_drivers"]["drivers"]), set(out["tests"]["a1_drivers"]["drivers"])
    rep = set(t["replicated_from_locked_B2r"]) | set(out["tests"]["a1_drivers"]["replicated_from_locked_B2r"])
    for r in sorted(out["per_type"], key=lambda r: (-r["stability"], r["manc_type"])):
        if r["manc_type"] in b1 | a1:
            L.append(f"| {r['manc_type']} | {r['stability']:.3f} | {r['mean_copy_score']:.3f} | {r['mean_frac_rhythmic']:.3f} | {r['mean_usable_seeds']:.1f} | "
                     f"{'yes' if r['manc_type'] in b1 else ''} | {'yes' if r['manc_type'] in a1 else ''} | {'yes' if r['manc_type'] in rep else ''} |")
    f = out["S2_false_hits"]
    L += ["", f"**S2 (40 sampled non-hits):** {f['pairs_with_copy_score_ge_0.5']} of {f['n_type_copy_pairs']} (type, copy) pairs scored >= 0.5 "
          f"(rate {f['rate_per_copy']:.4f} per copy); {f['types_with_any_driver_copy']} of 40 types had at least one driver copy (95 % CI "
          f"{f['types_with_any_driver_copy_ci95'][0]:.3f}-{f['types_with_any_driver_copy_ci95'][1]:.3f}); {f['types_with_stability_ge_0.5']} had "
          f"stability >= 0.5. By B1r band: " + "; ".join(f"{k}: {v['pairs_ge_0.5']} of {v['n_pairs']} pairs, {v['types_with_any_driver_copy']} of "
                                                       f"{v['n_types']} types" for k, v in f.items() if isinstance(v, dict)) + ".", ""]
    return "\n".join(L)


def part_t(res: list[dict]) -> dict:
    """Part T: every copy's single-copy score (seeds 0..15) per type and fly; concordance; MANC single-copy vs A0 per copy."""
    from scipy.stats import spearmanr  # noqa: PLC0415

    errs = [r["key"] for r in res if "error" in r]
    if errs:
        raise SystemExit(f"{len(errs)} Part T jobs ended with an error, e.g. {errs[:3]}")
    by: dict[tuple[str, str, int], list[dict]] = {}
    for r in res:
        pre, grp, _ = r["key"].split("|")
        t, b = grp.split("#")
        by.setdefault((pre.split("-")[1], t, int(b)), []).append(r)
    rows = [{"fly": f, "manc_type": t, "bodyId": b, "n_seeds": len(rs), "score": type_score(rs)} for (f, t, b), rs in sorted(by.items())]
    d = pd.DataFrame(rows)
    conc = {}
    for (f, t), g in d.groupby(["fly", "manc_type"]):
        drv = g["score"] >= DRIVER
        conc.setdefault(f, {})[t] = {"n_copies": len(g), "n_driver_copies": int(drv.sum()), "all": bool(drv.all()), "any": bool(drv.any()),
                                     "copies": [[int(b), float(s)] for b, s in zip(g["bodyId"], g["score"])]}
    a0 = pd.read_csv(PERTYPE / "A0_copies.csv", dtype={"manc_type": str}).set_index("bodyId")["score"]
    m = d[(d["fly"] == "MANC") & d["bodyId"].isin(a0.index)]
    rho = spearmanr(m["score"], a0.loc[m["bodyId"]].to_numpy()).correlation if len(m) > 2 else None
    summ = {f: {"n_types": len(v), "n_with_driver_copy": sum(x["any"] for x in v.values()), "n_all_copies_drivers": sum(x["all"] and x["n_copies"] >= 2 for x in v.values()),
                "concordant_multi_copy_types": sorted(t for t, x in v.items() if x["all"] and x["n_copies"] >= 2)} for f, v in conc.items()}
    return {"rule": "PREREG v5 Part T (descriptive)", "per_copy": json.loads(d.to_json(orient="records")), "concordance": conc, "summary": summ,
            "manc_single_copy_vs_A0_spearman": rho, "n_manc_copies_compared": int(len(m)),
            "focus": {t: {f: conc.get(f, {}).get(t) for f in conc} for t in ("DNg100", "DNb08")}}


def _write_once(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def main() -> None:
    a = sys.argv[1:]
    n = int(a[a.index("--copies") + 1]) if "--copies" in a else 16
    if a[:1] == ["power"]:
        print(json.dumps({"B1r_list_n15_k3": min_p_table(15, 3), "A1_list_n11_k3": min_p_table(11, 3)}, indent=1))
    elif a[:1] == ["part-s"]:
        have = collected_copy_campaigns()
        if 4 * len(have) != n or have != list(PS_CAMPAIGNS[: len(have)]):
            raise SystemExit(f"S8: every collected copy is analysed; collected campaigns {have} hold {4 * len(have)} copies, --copies {n}; refused")
        camps = PS_CAMPAIGNS[: (n + 3) // 4]
        out, d = part_s(results(camps), n)
        out["campaigns"] = list(camps)
        out["missing_or_errored_keys"] = sorted(r["key"] for r in results(camps) if "error" in r)
        _write_once(OUT / "S_stability.csv", d.to_csv(index=False, lineterminator="\n"))
        _write_once(OUT / "S_tests.json", json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
        _write_once(OUT / "S_report.md", report_s(out))
        print(report_s(out))
    elif a[:1] == ["part-t"]:
        out = part_t(results(PT_CAMPAIGNS))
        _write_once(OUT / "T_singlecopy.json", json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
        print(json.dumps(out["summary"], indent=1), "\nfocus:", json.dumps(out["focus"], indent=1)[:3000])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
