"""Re-rank the Level B rounds r1-r3 under the benchmark version 3 profile rules, from the STORED per-system records (orchestrator; for the
record only: the rounds' decisions stand as made, PROTOCOL.md section 10.1).

    uv run --project phase3 --no-sync python scripts/p3/rerank_v3.py [--rounds r1,r2,r3] [--n-boot 1000]

Version 3 changes three profile components (brainir_state.evaluate_cross.system_values): S3 = max(0, upper CI of the D micro-gain),
S5 = min(R^2 true <- model, R^2 model <- true), S6 = the point k equals the true k. Both R^2 directions, the D CIs and the exact-k flag
are in the stored records, so these are recomputed exactly. What the stored records CANNOT give:
- S2 under version 3 (held-out C over observed-target pairs only): the records keep the version 2 pooled C, not per-pair data, so S2
  stays the version 2 value;
- the Markov / rollout-consistency check (the version 2 evaluator did not run it): the comparator rule is applied without it.
Output: research/phase3/tournament/RERANK_V3.json and RERANK_V3.md (ANSWER-BEARING: never into a room).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from brainir_state.evaluate_cross import profile_from_systems, rank_profiles, selection_bootstrap  # noqa: E402
from merge_rounds import S1_S5, choose_comparator, descriptive_rankings, select_candidate  # noqa: E402

T = ROOT / "research" / "phase3" / "tournament"
CHANGED = ("S3_D_micro_gain", "S5_K_r2_rff", "S6_dim_rate")
NOT_RECOMPUTABLE = ["S2 keeps the version 2 value (the version 3 observed-target C needs per-pair data that the records do not keep)",
                    "the version 3 Markov / rollout-consistency check is not in the records: the comparator rule is applied without it"]


def rerank_round(rnd: str, n_boot: int = 1000) -> dict:
    agg = json.loads((T / rnd / "AGGREGATE_developer_facing.json").read_text(encoding="utf-8"))
    design = agg["design"]
    compressible = list(design["compressible"])
    per_method = {m: json.loads((ROOT / f).read_text(encoding="utf-8")) for m, f in agg["per_candidate_files"].items()}
    prof3 = {m: profile_from_systems(pm["per_system"], compressible, pm.get("abstention") or {}, pm.get("I") or []) for m, pm in per_method.items()}
    eligible = {m: bool(agg["eligible"].get(m)) for m in per_method}
    elig = sorted(m for m in per_method if eligible[m])
    tp = {m: per_method[m].get("transition_params_median") for m in elig}
    tp = {m: v for m, v in tp.items() if v is not None}
    rk = rank_profiles({m: prof3[m] for m in elig}, tp) if elig else {"mean_rank": {}, "order": [], "components_used": []}
    boot = selection_bootstrap({m: {"per_system": per_method[m]["per_system"], "profile": prof3[m]} for m in elig}, compressible,
                               n_boot=n_boot, eliminate_fraction=(0.5 if design.get("pilot") else None), transition_params=tp) \
        if len(elig) >= 2 and compressible else {}
    sel = select_candidate(rk, boot, per_method, compressible, tp)
    tp_all = {m: per_method[m].get("transition_params_median") for m in per_method}
    comp = choose_comparator(per_method, compressible, prof3, sel.get("selected"), {m: v for m, v in tp_all.items() if v is not None},
                             require_markov=False)
    return {"round": rnd, "design_benchmark_version": design.get("benchmark_version"), "n_candidates": len(per_method),
            "n_compressible": len(compressible), "eligible": eligible,
            "v2": {"order": agg["rank_order"], "mean_rank": agg["mean_rank"],
                   "p_rank1": {m: (agg.get("selection_uncertainty") or {}).get(m, {}).get("p_rank1") for m in agg["rank_order"]}},
            "v3": {"order": rk["order"], "mean_rank": rk["mean_rank"], "components_used": rk["components_used"],
                   "p_rank1": {m: boot.get(m, {}).get("p_rank1") for m in rk["order"]}, "selection_uncertainty": boot,
                   "selection_rule": sel, "comparator_rule": comp,
                   "descriptive": descriptive_rankings({m: prof3[m] for m in elig}, tp) if elig else {}},
            "profiles_changed_components": {m: {k: {"v2": (agg["profiles"].get(m) or {}).get(k), "v3": prof3[m].get(k)} for k in CHANGED}
                                            for m in per_method},
            "not_recomputable": NOT_RECOMPUTABLE}


def _md(res: dict) -> str:
    L = ["# Re-ranking of Level B rounds 1-3 under the benchmark version 3 profile rules (ANSWER-BEARING)", "",
         "For the record only: the rounds' decisions stand as made (PROTOCOL.md section 10.1). Recomputed exactly from the stored",
         "per-system records: S3 = max(0, upper CI of the D micro-gain), S5 = min(R^2 true <- model, R^2 model <- true), S6 = exact point k.",
         "", "Not recomputable from the records:", ""] + [f"- {x}" for x in NOT_RECOMPUTABLE] + [""]
    for rnd, r in res.items():
        L += [f"## {rnd} ({r['n_candidates']} candidates, {r['n_compressible']} compressible systems)", "",
              "| candidate | v2 mean rank | v2 P(rank 1) | v3 mean rank | v3 P(rank 1) | S3 v2 -> v3 | S5 v2 -> v3 | S6 v2 -> v3 |",
              "|---|---|---|---|---|---|---|---|"]
        for m in r["v3"]["order"] + sorted(set(r["v2"]["order"]) - set(r["v3"]["order"])):
            ch = r["profiles_changed_components"].get(m, {})

            def f(x, nd=3):
                try:
                    return f"{float(x):.{nd}f}"
                except (TypeError, ValueError):
                    return "-"
            L.append(f"| {m} | {f(r['v2']['mean_rank'].get(m), 2)} | {f(r['v2']['p_rank1'].get(m), 2)} | {f(r['v3']['mean_rank'].get(m), 2)} | "
                     f"{f(r['v3']['p_rank1'].get(m), 2)} | {f(ch.get('S3_D_micro_gain', {}).get('v2'))} -> {f(ch.get('S3_D_micro_gain', {}).get('v3'))} | "
                     f"{f(ch.get('S5_K_r2_rff', {}).get('v2'))} -> {f(ch.get('S5_K_r2_rff', {}).get('v3'))} | "
                     f"{f(ch.get('S6_dim_rate', {}).get('v2'), 2)} -> {f(ch.get('S6_dim_rate', {}).get('v3'), 2)} |")
        sel, comp = r["v3"]["selection_rule"], r["v3"]["comparator_rule"]
        s15 = (r["v3"].get("descriptive") or {}).get("S1_S5_only") or {}
        L += ["", f"- Version 3 selection rule: **{sel.get('selected')}** ({sel.get('rule_applied')}).",
              f"- Version 3 comparator rule (without the Markov criterion): **{comp.get('chosen')}** ({comp.get('reason')}).",
              f"- Descriptive ranking on S1-S5 only: {', '.join(s15.get('order') or [])}.", ""]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", default="r1,r2,r3")
    ap.add_argument("--n-boot", type=int, default=1000)
    args = ap.parse_args(argv)
    res = {r: rerank_round(r, args.n_boot) for r in args.rounds.split(",") if r}
    (T / "RERANK_V3.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    (T / "RERANK_V3.md").write_text(_md(res), encoding="utf-8", newline="\n")
    for rnd, r in res.items():
        print(rnd, "v2:", r["v2"]["order"][:4], "v3:", r["v3"]["order"][:4], "selected:", r["v3"]["selection_rule"].get("selected"),
              "comparator:", r["v3"]["comparator_rule"].get("chosen"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
