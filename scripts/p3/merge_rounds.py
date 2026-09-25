"""Merge per-developer tournament runs of one Level B round into one ranked aggregate, and (with --decide) apply the pre-registered
selection decision (orchestrator; PROTOCOL.md section 9, benchmark version 3).

    uv run --project phase3 python scripts/p3/merge_rounds.py --parts r1_lin,r1_ks,... --out r1 [--decide] [--note "..."]

Each part is a tournament.py run on a subset of the candidates, so candidates can be scored as their developers finish. The parts
must share ONE design (suite, pilot flag, system list, G systems, shared fits, simulation budget, time limit, benchmark version;
review E M6); the merge refuses otherwise. It re-ranks all eligible candidates with the rule of tournament.py
(brainir_state.evaluate_cross.rank_profiles: average ranks for ties, non-finite values last, components non-finite for every candidate
dropped, ties broken by fewer transition parameters), recomputes the selection's bootstrap uncertainty over systems (P(rank 1), rank
interval; in a pilot, P(eliminated)), and writes research/phase3/tournament/<out>/AGGREGATE_developer_facing.json plus links to the
parts' per-candidate files.

--decide (version 3; pre-lock review C M5 and M2) writes <out>/ROUND_DECISION.json (ANSWER-BEARING) with the rules fixed before
round 3 attempt 2:
- SELECTION: the top candidate by mean rank is selected if its bootstrap P(rank 1) >= 0.5. Otherwise the tie set is the top candidate
  plus every candidate with P(rank 1) >= 0.10, and the member with the LOWEST median point k over the fixed list of compressible
  systems is selected (parsimony; only members whose k is available on >= 90 % of the list qualify), remaining ties broken by fewer
  transition parameters, then by mean rank, then by name. If no member qualifies, the top candidate is selected.
- COMPARATOR (the strongest baseline for Level C): among the declared baselines (and their tuned variants <baseline>_t) other than the
  selected method, those with at most 10 % failed fits / evaluations over the fixed list AND the Markov / rollout-consistency check
  passed (verdict markov_ok) on at least 90 % of it are eligible; they are ranked AMONG THEMSELVES on S1-S5 only (the components the
  Level C primary family tests), ties broken by fewer transition parameters, then by name. If none is eligible, the best of all
  declared baselines on S1-S5 is taken and the reason recorded.
- DESCRIPTIVE: the ranking on S1-S5 only and every leave-one-component-out ranking.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))
from brainir_state.evaluate_cross import PROFILE_KEYS, rank_profiles, selection_bootstrap  # noqa: E402

T = ROOT / "research" / "phase3" / "tournament"
DESIGN_KEYS = ("suite", "pilot", "systems", "compressible", "g_systems", "skip_shared", "sim_budget", "timeout_s", "benchmark_version")
BENCHMARK_VERSION = 3

# ---------------------------------------------------------------- the pre-registered decision rules (version 3)
BASELINES = ("lin_pcadyn", "lin_dmdc", "lin_falds", "ks_hankel", "nn_aelin", "nn_rssm", "nn_seqbottleneck")
S1_S5 = ("S1_A_over_full", "S2_C_heldout", "S3_D_micro_gain", "S4_E_ratio", "S5_K_r2_rff")
P_SELECT = 0.5            # P(rank 1) at or above which the top candidate is selected outright
P_TIE = 0.10              # P(rank 1) at or above which a candidate joins the tie set
K_AVAILABLE_MIN = 0.9     # parsimony uses a candidate's median k only if k is available on >= 90 % of the fixed list
COMPARATOR_MAX_FAIL = 0.10
COMPARATOR_MARKOV_MIN = 0.90


def is_baseline(name: str) -> bool:
    """A declared baseline of goal4 section 23 (PROTOCOL.md section 9) or an independently tuned variant of one (<baseline>_t)."""
    return name in BASELINES or (name.endswith("_t") and name[:-2] in BASELINES)


def _num(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v


def k_summary(per_system: dict, compressible: list[str]) -> dict:
    """Median point k over the fixed list and the fraction of the list where k is available (a failed fit has none)."""
    ks = []
    for s in compressible:
        k = _num((per_system.get(s) or {}).get("k"))
        if np.isfinite(k):
            ks.append(k)
    return {"median_k": float(np.median(ks)) if ks else float("nan"), "k_available": len(ks) / max(1, len(compressible))}


def fixed_list_health(per_system: dict, compressible: list[str]) -> dict:
    """Failures (a failed fit or evaluation leaves an error record or no verdict) and Markov-check passes over the fixed list."""
    fail = sum(1 for s in compressible if (per_system.get(s) or {}).get("error") or not (per_system.get(s) or {}).get("verdict"))
    markov = sum(1 for s in compressible if ((per_system.get(s) or {}).get("verdict") or {}).get("markov_ok") is True)
    n = max(1, len(compressible))
    return {"n_systems": len(compressible), "n_failed": fail, "failure_rate": fail / n, "n_markov_ok": markov, "markov_ok_rate": markov / n}


def choose_comparator(per_method: dict[str, dict], compressible: list[str], profiles: dict[str, dict], selected: str | None = None,
                      transition_params: dict | None = None, require_markov: bool = True) -> dict:
    """The Level C comparator (see the module docstring). per_method: {name: per-candidate tournament record (per_system, ...)}.
    require_markov=False only for re-ranking records made before version 3 (their verdicts have no Markov check); never for a
    decision."""
    tp = {m: v for m, v in (transition_params or {}).items() if v is not None}
    cands = sorted(m for m in per_method if is_baseline(m) and m != selected)
    table = {}
    for m in cands:
        h = fixed_list_health(per_method[m].get("per_system") or {}, compressible)
        markov_ok = h["markov_ok_rate"] >= COMPARATOR_MARKOV_MIN if require_markov else True
        if not require_markov:
            h["markov_ok_rate"] = None
        h["eligible"] = bool(h["failure_rate"] <= COMPARATOR_MAX_FAIL and markov_ok)
        h["profile_S1_S5"] = {k: (profiles.get(m) or {}).get(k) for k in S1_S5}
        table[m] = h
    elig = [m for m in cands if table[m]["eligible"]]
    if elig:
        pool, reason = elig, "best eligible baseline on S1-S5, ranked among the eligible baselines only"
    elif cands:
        pool, reason = cands, "no baseline passed eligibility (failures <= 10 % and Markov check >= 90 %): best of all declared baselines on S1-S5"
    else:
        return {"chosen": None, "reason": "no declared baseline in the round", "table": table}
    if not require_markov:
        reason += " (Markov criterion not applied: the records predate the version 3 check)"
    rk = rank_profiles({m: profiles[m] for m in pool}, {m: tp[m] for m in pool if m in tp}, keys=S1_S5)
    for m in pool:
        table[m]["mean_rank_S1_S5_in_pool"] = rk["mean_rank"][m]
    return {"chosen": rk["order"][0], "order": rk["order"], "pool": pool, "reason": reason, "components_used": rk["components_used"],
            "rule": {"max_failure_rate": COMPARATOR_MAX_FAIL, "min_markov_ok_rate": COMPARATOR_MARKOV_MIN, "keys": list(S1_S5),
                     "tie_break": "fewer transition parameters, then name"}, "table": table}


def select_candidate(ranked: dict, boot: dict, per_method: dict[str, dict], compressible: list[str],
                     transition_params: dict | None = None) -> dict:
    """The pre-registered selection rule (see the module docstring). ranked: rank_profiles output over the ELIGIBLE candidates."""
    order = list(ranked.get("order") or [])
    if not order:
        return {"selected": None, "rule_applied": "no eligible candidate"}
    tp = transition_params or {}
    top = order[0]
    p_top = _num((boot.get(top) or {}).get("p_rank1"))
    out = {"top_by_mean_rank": top, "p_rank1_top": p_top, "thresholds": {"p_select": P_SELECT, "p_tie": P_TIE, "k_available_min": K_AVAILABLE_MIN}}
    if np.isfinite(p_top) and p_top >= P_SELECT:
        return {**out, "selected": top, "rule_applied": f"top candidate with P(rank 1) = {p_top:.3f} >= {P_SELECT}"}
    if not boot:
        return {**out, "selected": top, "rule_applied": "no selection bootstrap (fewer than two eligible candidates): top candidate"}
    tie = [top] + [m for m in order[1:] if _num((boot.get(m) or {}).get("p_rank1")) >= P_TIE]
    ks = {m: k_summary(per_method[m].get("per_system") or {}, compressible) for m in tie}
    ok = [m for m in tie if ks[m]["k_available"] >= K_AVAILABLE_MIN and np.isfinite(ks[m]["median_k"])]
    out.update(tie_set=tie, tie_set_k=ks)
    if not ok:
        return {**out, "selected": top, "rule_applied": "tie set without k on >= 90 % of the list: top candidate"}

    def key(m):
        t = _num(tp.get(m))
        return (ks[m]["median_k"], t if np.isfinite(t) else np.inf, ranked["mean_rank"][m], m)
    sel = min(ok, key=key)
    return {**out, "selected": sel, "rule_applied": f"P(rank 1) of the top candidate {p_top:.3f} < {P_SELECT}: parsimony (lowest median k) "
                                                  f"within the tie set (P(rank 1) >= {P_TIE})"}


def descriptive_rankings(profiles: dict[str, dict], transition_params: dict | None = None) -> dict:
    """The ranking on S1-S5 only and every leave-one-component-out ranking (reported, never used for the decision)."""
    tp = transition_params or {}
    s15 = rank_profiles(profiles, tp, keys=S1_S5)
    full = rank_profiles(profiles, tp)
    loo = {}
    for k in full["components_used"]:
        r = rank_profiles(profiles, tp, keys=tuple(x for x in PROFILE_KEYS if x != k))
        loo[f"without_{k}"] = {"order": r["order"], "mean_rank": r["mean_rank"]}
    return {"S1_S5_only": {"order": s15["order"], "mean_rank": s15["mean_rank"], "components_used": s15["components_used"]},
            "leave_one_component_out": loo}


def round_decision(out: dict, per_method: dict[str, dict], note: str | None = None) -> dict:
    """ROUND_DECISION.json content for a merged round (out: the AGGREGATE record written by main)."""
    compressible = list(out["design"]["compressible"])
    elig = [m for m in out["profiles"] if out["eligible"].get(m)]
    tp = {m: per_method[m].get("transition_params_median") for m in out["profiles"]}
    tp = {m: v for m, v in tp.items() if v is not None}
    ranked = {"order": out["rank_order"], "mean_rank": out["mean_rank"]}
    sel = select_candidate(ranked, out["selection_uncertainty"], per_method, compressible, tp)
    comp = choose_comparator(per_method, compressible, out["profiles"], sel.get("selected"), tp)
    return {"round": out["round"], "benchmark_version": out["design"].get("benchmark_version"), "design": out["design"],
            "eligibility_rule": "PROTOCOL.md section 9: at most 10 % of fits and evaluations fail",
            "ineligible": sorted(m for m in out["profiles"] if not out["eligible"].get(m)),
            "rank_order_primary": out["rank_order"], "mean_rank_primary": out["mean_rank"], "rank_components": out["rank_components"],
            "selection_uncertainty": out["selection_uncertainty"], "selection": sel, "best_candidate": sel.get("selected"),
            "comparator": comp, "comparator_baseline": comp.get("chosen"),
            "descriptive": descriptive_rankings({m: out["profiles"][m] for m in elig}, tp) if elig else {},
            "note": note}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--decide", action="store_true", help="also write ROUND_DECISION.json with the pre-registered rules")
    ap.add_argument("--note", default=None, help="free-text note stored in ROUND_DECISION.json")
    ap.add_argument("--benchmark-version", type=int, default=BENCHMARK_VERSION,
                    help="the benchmark version the parts must have been produced under (default: the current one)")
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
    if design.get("benchmark_version") != args.benchmark_version:
        raise SystemExit(f"parts were produced under benchmark version {design.get('benchmark_version')}, not {args.benchmark_version}")
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
    if args.decide:
        dec = round_decision(out, per_method, args.note)
        (T / args.out / "ROUND_DECISION.json").write_text(json.dumps(dec, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"selected: {dec['best_candidate']} ({dec['selection'].get('rule_applied')}); comparator: {dec['comparator_baseline']} "
              f"({dec['comparator'].get('reason')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
