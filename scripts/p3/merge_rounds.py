"""Merge per-developer tournament runs of one Level B round into one ranked aggregate (orchestrator; PROTOCOL.md section 9, benchmark
version 2).

    uv run --project phase3 python scripts/p3/merge_rounds.py --parts r1_lin,r1_ks,... --out r1

Each part is a tournament.py run on a subset of the candidates, so candidates can be scored as their developers finish. The parts
must share ONE design (suite, pilot flag, system list, G systems, shared fits, simulation budget, time limit; review E M6); the merge
refuses otherwise. It re-ranks all eligible candidates with the rule of tournament.py (brainir_state.evaluate_cross.rank_profiles:
average ranks for ties, non-finite values last, components non-finite for every candidate dropped, ties broken by fewer transition
parameters), recomputes the selection's bootstrap uncertainty over systems (P(rank 1), rank interval; in a pilot, P(eliminated)),
and writes research/phase3/tournament/<out>/AGGREGATE_developer_facing.json plus links to the parts' per-candidate files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))
from brainir_state.evaluate_cross import rank_profiles, selection_bootstrap  # noqa: E402

T = ROOT / "research" / "phase3" / "tournament"
DESIGN_KEYS = ("suite", "pilot", "systems", "compressible", "g_systems", "skip_shared", "sim_budget", "timeout_s", "benchmark_version")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-boot", type=int, default=1000)
    args = ap.parse_args(argv)
    profiles, verdicts, eligible, files, designs, per_method = {}, {}, {}, {}, {}, {}
    for part in [p for p in args.parts.split(",") if p]:
        agg = json.loads((T / part / "AGGREGATE_developer_facing.json").read_text(encoding="utf-8"))
        d = agg.get("design") or {}
        designs[part] = {k: d.get(k) for k in DESIGN_KEYS}
        for m, prof in agg["profiles"].items():
            if m in profiles:
                raise SystemExit(f"candidate {m} appears in two parts")
            profiles[m], verdicts[m], eligible[m] = prof, agg["verdict_counts"].get(m, {}), agg["eligible"].get(m)
            files[m] = f"research/phase3/tournament/{part}/{m}.json"
            per_method[m] = json.loads((T / part / f"{m}.json").read_text(encoding="utf-8"))
    distinct = {json.dumps(v, sort_keys=True) for v in designs.values()}
    if len(distinct) != 1:
        raise SystemExit("parts have different designs:\n" + "\n".join(f"  {p}: {json.dumps(v, sort_keys=True)}" for p, v in designs.items()))
    design = next(iter(designs.values()))
    if design.get("benchmark_version") != 2:
        raise SystemExit("parts were not produced under benchmark version 2")
    elig = sorted(m for m in profiles if eligible[m])
    tp = {m: per_method[m].get("transition_params_median") for m in elig}
    tp = {m: v for m, v in tp.items() if v is not None}
    rk = rank_profiles({m: profiles[m] for m in elig}, tp) if elig else {"mean_rank": {}, "order": [], "components_used": []}
    compressible = list(design["compressible"])
    boot = selection_bootstrap({m: {"per_system": per_method[m]["per_system"], "profile": profiles[m]} for m in elig}, compressible,
                               n_boot=args.n_boot, eliminate_fraction=(0.5 if design.get("pilot") else None), transition_params=tp) \
        if len(elig) >= 2 and compressible else {}
    out = {"round": args.out, "suite": design["suite"], "design": design, "parts": args.parts.split(","), "profiles": profiles,
           "verdict_counts": verdicts, "eligible": eligible, "mean_rank": rk["mean_rank"], "rank_order": rk["order"],
           "rank_components": rk["components_used"], "selection_uncertainty": boot, "per_candidate_files": files}
    (T / args.out).mkdir(parents=True, exist_ok=True)
    (T / args.out / "AGGREGATE_developer_facing.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    for m in rk["order"]:
        u = boot.get(m, {})
        print(f"{rk['mean_rank'][m]:5.2f}  {m:28s} P(rank1)={u.get('p_rank1', float('nan')):.2f} "
              f"rank90=[{u.get('rank_p05', float('nan')):.0f},{u.get('rank_p95', float('nan')):.0f}]"
              + (f" P(elim)={u['p_eliminated']:.2f}" if "p_eliminated" in u else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
