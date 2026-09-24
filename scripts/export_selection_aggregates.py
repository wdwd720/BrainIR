"""Aggregate-only export of selection results for the oracle-free clean room (SELECTION_PROTOCOL.md section 4).

    uv run python scripts/export_selection_aggregates.py --tournament research/phase2/tournament/sel_mech_b1000_part1.json [...] \
        --curve research/phase2/tournament/sel_curve_part1_curve.json [...] --pairs research/phase2/tournament/<pairs>.json [...] \
        --out C:/Dev/BrainIR_p2clean/research/phase2/selection_results

Writes selection_aggregates.json and SELECTION_RESULTS.md: per method (and per mode for pairs) the summary statistics, the per-family
breakdown, identity consistency and the budget curve. Never exported: per-run records, instance names, truth, per-instance scores.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from brainir.discovery.tournament import run_calls

DROP_KEYS = {"records", "rows", "instances", "configs"}


def _clean(obj):
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if k not in DROP_KEYS}
    if isinstance(obj, list):
        return [_clean(x) for x in obj]
    return obj


def _by_size(records: list[dict]) -> dict:
    """Aggregate by method and graph-size class (no instance identity leaves this function)."""
    import numpy as np

    out: dict = {}
    for r in records:
        if "structure" not in r:
            continue
        n = int(r.get("truth_n") or 0)
        sc = "small" if n <= 100 else "medium" if n <= 800 else "large"
        out.setdefault(r["method"], {}).setdefault(sc, []).append(r)
    res: dict = {}
    for m, per in out.items():
        res[m] = {}
        for sc, rs in per.items():
            causal = [float((r.get("function") or {}).get("functional_success_causal")) for r in rs
                      if "functional_success_causal" in (r.get("function") or {})]
            res[m][sc] = {"n": len(rs), "success": float(np.mean([r["structure"]["success"] for r in rs])),
                          "causal_functional": float(np.mean(causal)) if causal else None,
                          "calls_median": float(np.median([run_calls(r) or 0 for r in rs])),
                          "wall_median": float(np.median([r.get("wall_s", 0.0) for r in rs])),
                          "size_median": float(np.median([len(r["result"]["core"]) for r in rs]))}
    return res


def _fmt(x) -> str:
    if x is None:
        return "–"
    if isinstance(x, float):
        return f"{x:.2f}"
    return str(x)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tournament", nargs="*", default=[], type=Path)
    ap.add_argument("--curve", nargs="*", default=[], type=Path)
    ap.add_argument("--pairs", nargs="*", default=[], type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    agg: dict = {"note": "aggregate-only export of the held-out selection suite; no per-instance information", "tournaments": [], "curves": [],
                 "pairs": []}
    md = ["# Selection results (held-out synthetic suite, aggregates only)", "",
          "Scored by the orchestrator on anonymised held-out instances you have never seen (fresh salt). Per method: success with 95 % "
          "bootstrap CIs, reliability across 2 node orders x 3 seeds per instance, calls, robustness, minimality, calibration, roles; "
          "per family: success and median calls.", ""]
    for p in args.tournament:
        d = json.loads(p.read_text(encoding="utf-8"))
        t = {k: d.get(k) for k in ("label", "budget", "seeds", "networks", "n_jobs", "score_seeds")}
        t["summary"] = _clean(d["summary"])
        t["by_size_class"] = _by_size(d.get("records", []))
        agg["tournaments"].append(t)
        md += [f"## Tournament `{d['label']}` — budget {d['budget']} calls, seeds {d['seeds']}, networks {d['networks']}", "",
               "| method | runs | structural success [CI] | functional success [CI] | causal functional | planted | identity Jaccard / identical | "
               "calls med / mean | sim s med | size med | nominal / robust pass | removable frac | role acc | essential acc | Brier |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for m, s in d["summary"].items():
            ic = s.get("identity_consistency") or {}
            ci, fci = s.get("success_ci95", [None, None]), s.get("functional_success_ci95", [None, None])
            md.append(f"| {m} | {s['n_runs']} | {_fmt(s['success_rate'])} [{_fmt(ci[0])}, {_fmt(ci[1])}] | {_fmt(s.get('functional_success_rate'))} "
                      f"[{_fmt(fci[0])}, {_fmt(fci[1])}] | {_fmt(s.get('functional_success_causal_rate'))} | {_fmt(s.get('success_planted_rate'))} | "
                      f"{_fmt(ic.get('pairwise_jaccard_mean'))} / {_fmt(ic.get('identical_fraction'))} | {_fmt(s.get('calls_median'))} / "
                      f"{_fmt(s.get('calls_mean'))} | {_fmt(s.get('simulated_seconds_median'))} | "
                      f"{_fmt(s.get('size_median'))} | {_fmt(s.get('functional_nominal_mean'))} / {_fmt(s.get('functional_robust_mean'))} | "
                      f"{_fmt(s.get('removable_fraction'))} | {_fmt(s.get('role_accuracy_mean'))} | {_fmt(s.get('essential_accuracy_mean'))} | "
                      f"{_fmt(s.get('brier_mean'))} |")
        md += ["", "By graph size (small n <= 100, medium n <= 800, large n > 800): runs / structural success / causal functional / "
               "median calls / median wall s / median core size", "", "| method | small | medium | large |", "|---|---|---|---|"]
        for m, per in t["by_size_class"].items():
            cells = []
            for sc in ("small", "medium", "large"):
                v = per.get(sc)
                cells.append("–" if not v else f"{v['n']} / {_fmt(v['success'])} / {_fmt(v['causal_functional'])} / {v['calls_median']:.0f} / "
                                              f"{v['wall_median']:.0f} / {v['size_median']:.0f}")
            md.append(f"| {m} | " + " | ".join(cells) + " |")
        fams = sorted({f for s in d["summary"].values() for f in s.get("by_family", {})})
        md += ["", "Per family (structural / functional success, median calls):", "", "| family | " + " | ".join(d["summary"]) + " |",
               "|---|" + "---|" * len(d["summary"])]
        for f in fams:
            cells = []
            for s in d["summary"].values():
                b = s.get("by_family", {}).get(f)
                cells.append("–" if not b else f"{_fmt(b['success_rate'])} / {_fmt(b.get('functional_success_rate'))} / {b['calls_median']:.0f}")
            md.append(f"| {f} | " + " | ".join(cells) + " |")
        md.append("")
    for p in args.curve:
        d = json.loads(p.read_text(encoding="utf-8"))
        agg["curves"].append({"label": d.get("label"), "curve": d.get("curve")})
        md += [f"## Budget curve `{d.get('label')}` (seed 0, both node orders, n <= 600)", "", "| method | budgets | success | functional pass mean | "
               "AUC (log budget) |", "|---|---|---|---|---|"]
        for m, c in d["curve"].items():
            succ, func = [_fmt(x) for x in c["success"]], [_fmt(x) for x in c["functional"]]
            md.append(f"| {m} | {c['budgets']} | {succ} | {func} | {_fmt(c.get('auc_log_budget'))} |")
        md.append("")
    for p in args.pairs:
        d = json.loads(p.read_text(encoding="utf-8"))
        agg["pairs"].append({k: d.get(k) for k in ("label", "methods", "modes", "budget_a", "budget_b", "seeds")} | {"summary": _clean(d["summary"])})
        md += [f"## Pair tournament `{d['label']}` — budgets a {d['budget_a']} / b {d['budget_b']}", "",
               "| method/mode | n | success a | success b | both [CI] | corr P/R | role align | role-graph sim | calls a/b/adapt/total | shift | decoy |",
               "|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, v in d["summary"].items():
            md.append(f"| {k} | {v['n_runs']} | {_fmt(v['success_a'])} | {_fmt(v['success_b'])} | {_fmt(v['both_success'])} [{_fmt(v['both_ci95'][0])}, "
                      f"{_fmt(v['both_ci95'][1])}] | {_fmt(v['corr_precision'])}/{_fmt(v['corr_recall'])} | {_fmt(v['role_alignment_accuracy'])} | "
                      f"{_fmt(v['role_graph_similarity_ab'])} | {_fmt(v['calls_a'])}/{_fmt(v['calls_b'])}/{_fmt(v['calls_adaptation'])}/"
                      f"{_fmt(v['calls_total'])} | {_fmt(v['shift_both_success'])} | {_fmt(v['decoy_both_success'])} |")
        md.append("")
    text = json.dumps(agg, indent=1)
    for bad in ('"instance"', '"core_positions"', '"truth', "alternatives_positions"):
        if bad in text:
            raise SystemExit(f"refusing to export: {bad} found in the aggregate")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "selection_aggregates.json").write_text(text + "\n", encoding="utf-8", newline="\n")
    (args.out / "SELECTION_RESULTS.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.out / 'selection_aggregates.json'} and SELECTION_RESULTS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
