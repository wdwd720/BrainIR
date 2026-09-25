"""Paired comparison of two reliability sweeps on the same network, orders and seeds (goal3 sections 20, 21, 30).

    uv run python scripts/compare_reliability.py --a research/phase2/reliability/<baseline>.json \
        --b research/phase2/reliability/<method>.json --label <name>

Runs are paired by (node-order variant, seed). Reported with bootstrap 95 % CIs that resample NODE-ORDER VARIANTS (clusters: the
seeds of one order share its permutation; review C finding C8), all runs of a drawn variant together:
    functional fidelity (keep-only pass fraction on fresh seeds) and pass rate, core size, calls, simulated seconds
    identity consistency (pairwise Jaccard of cores in the common frame) of each sweep and their difference; a pair of a run with
    its own bootstrap copy is never counted (no self-pairs)
    with --hidden (only after the method lock): structural success of each run from the logged hidden evaluation of both sweeps,
    paired difference, an exact McNemar test on runs, and an exact sign test on node-order clusters with a net difference.
A failed run counts as a failure: fidelity 0, pass 0, calls = the budget, an empty core in the Jaccard.
Output: research/phase2/reliability/compare_<label>.{json,md}.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _runs(path: Path) -> tuple[dict, dict]:
    d = json.loads(path.read_text(encoding="utf-8"))
    runs = {(r["variant"], int(r["seed"])): r for r in d["runs"] if "variant" in r and "seed" in r}
    return d, runs


def _failed(r: dict) -> bool:
    return "core_common" not in r


def _sim_seconds(r: dict) -> float | None:
    c = r.get("compute") or {}
    if c.get("simulated_seconds") is not None:
        return float(c["simulated_seconds"])
    sims = c.get("simulations")
    if sims is None:
        return None
    return float(sims) * float(c.get("t_end_s") or 1.0)


def _jaccard_mean(items: list[tuple[int, frozenset]]) -> float:
    """Mean pairwise Jaccard over pairs of DIFFERENT runs (bootstrap copies of one run are not paired with each other)."""
    vals = [len(a & b) / len(a | b) if (a | b) else 0.0 for i, (ka, a) in enumerate(items) for kb, b in items[i + 1:] if ka != kb]
    return float(np.mean(vals)) if vals else 1.0


def _ci(vals: list[float]) -> list[float]:
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def _binom_two_sided(k: int, n: int) -> float:
    if n == 0:
        return 1.0
    k = min(k, n - k)
    return float(min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=Path, required=True, help="reference sweep (e.g. the frozen baseline)")
    ap.add_argument("--b", type=Path, required=True, help="compared sweep (e.g. the locked method)")
    ap.add_argument("--label", required=True)
    ap.add_argument("--hidden", action="store_true", help="include the logged hidden structural evaluation of both sweeps")
    ap.add_argument("--n-boot", type=int, default=4000)
    args = ap.parse_args(argv)
    da, ra = _runs(args.a)
    db, rb = _runs(args.b)
    if da["summary"]["network"] != db["summary"]["network"]:
        raise SystemExit("the two sweeps are on different networks")
    keys = sorted(set(ra) & set(rb))
    if not keys:
        raise SystemExit("no paired runs")
    variants = sorted({k[0] for k in keys})
    by_var = {v: [i for i, k in enumerate(keys) if k[0] == v] for v in variants}
    rng = np.random.default_rng(0)
    draws = [[i for v in rng.choice(variants, len(variants)) for i in by_var[v]] for _ in range(args.n_boot)]
    budget_a, budget_b = da["summary"].get("budget"), db["summary"].get("budget")

    def metric(name: str, r: dict, budget):
        if _failed(r):
            return {"functional_fidelity": 0.0, "functional_pass": 0.0, "core_size": None, "calls": None if budget is None else float(budget),
                    "simulated_seconds": None}[name]
        return {"functional_fidelity": lambda: r.get("functional_fidelity"),
                "functional_pass": lambda: None if r.get("functional_fidelity") is None else float(r["functional_fidelity"] >= 0.5),
                "core_size": lambda: float(r["n_core"]), "calls": lambda: None if r.get("calls") is None else float(r["calls"]),
                "simulated_seconds": lambda: _sim_seconds(r)}[name]()

    out: dict = {"label": args.label, "network": da["summary"]["network"], "a": {"method": da["summary"]["method"], "file": args.a.name},
                 "b": {"method": db["summary"]["method"], "file": args.b.name}, "n_paired": len(keys), "n_order_clusters": len(variants),
                 "n_failed": {"a": sum(_failed(ra[k]) for k in keys), "b": sum(_failed(rb[k]) for k in keys)},
                 "resampling_unit": "node-order variant", "metrics": {}}
    for name in ("functional_fidelity", "functional_pass", "core_size", "calls", "simulated_seconds"):
        va = [metric(name, ra[k], budget_a) for k in keys]
        vb = [metric(name, rb[k], budget_b) for k in keys]
        d = np.array([np.nan if (x is None or y is None) else y - x for x, y in zip(va, vb)], dtype=float)
        if np.isnan(d).all():
            continue
        boot = [float(np.nanmean(d[s])) for s in draws if not np.isnan(d[s]).all()]
        ok = ~np.isnan(d)
        out["metrics"][name] = {"n": int(ok.sum()), "a_mean": float(np.mean([x for x, o in zip(va, ok) if o])),
                                "b_mean": float(np.mean([y for y, o in zip(vb, ok) if o])), "diff_mean": float(np.nanmean(d)), "diff_ci95": _ci(boot)}
    ca = [frozenset(ra[k].get("core_common") or ()) for k in keys]
    cb = [frozenset(rb[k].get("core_common") or ()) for k in keys]
    boot_a, boot_b, boot_d = [], [], []
    for s in draws[:min(args.n_boot, 2000)]:
        ja, jb = _jaccard_mean([(i, ca[i]) for i in s]), _jaccard_mean([(i, cb[i]) for i in s])
        boot_a.append(ja)
        boot_b.append(jb)
        boot_d.append(jb - ja)
    everything = list(range(len(keys)))
    ja, jb = _jaccard_mean([(i, ca[i]) for i in everything]), _jaccard_mean([(i, cb[i]) for i in everything])
    out["identity_consistency"] = {"a": ja, "b": jb, "a_ci95": _ci(boot_a), "b_ci95": _ci(boot_b), "diff": jb - ja, "diff_ci95": _ci(boot_d),
                                   "a_modal_frequency": max(ca.count(c) for c in set(ca)) / len(ca),
                                   "b_modal_frequency": max(cb.count(c) for c in set(cb)) / len(cb)}
    # run-by-run agreement of the two sweeps (same order and seed): e.g. one method under two problem definitions (review D, D4)
    same = [float(a == b and bool(a)) for a, b in zip(ca, cb)]
    pj = [len(a & b) / len(a | b) if (a | b) else 0.0 for a, b in zip(ca, cb)]
    out["paired_core_agreement"] = {"identical_rate": float(np.mean(same)), "n_identical": int(sum(same)), "jaccard_mean": float(np.mean(pj)),
                                    "a_modal_core_equals_b_modal_core": max(set(ca), key=ca.count) == max(set(cb), key=cb.count)}
    if args.hidden:
        ha, hb = da["summary"].get("hidden_eval"), db["summary"].get("hidden_eval")
        if not ha or not hb:
            raise SystemExit("--hidden needs both sweeps to carry a logged hidden evaluation")
        # a run without a scored row (e.g. failed) counts as unsuccessful
        sa = {(r["variant"], int(r["seed"])): bool(r.get("e_core_recall") == 1.0 and r.get("inhibitory_slot")) for r in ha["rows"] if "e_core_recall" in r}
        sb = {(r["variant"], int(r["seed"])): bool(r.get("e_core_recall") == 1.0 and r.get("inhibitory_slot")) for r in hb["rows"] if "e_core_recall" in r}
        x = np.array([float(sa.get(k, False)) for k in keys])
        y = np.array([float(sb.get(k, False)) for k in keys])
        d = y - x
        boot = [float(d[s].mean()) for s in draws]
        b01, b10 = int(((x == 0) & (y == 1)).sum()), int(((x == 1) & (y == 0)).sum())
        net = {v: float(d[by_var[v]].sum()) for v in variants}
        cl_b, cl_a = sum(1 for v in net.values() if v > 0), sum(1 for v in net.values() if v < 0)
        out["hidden_structural_success"] = {"n": len(keys), "a_rate": float(x.mean()), "b_rate": float(y.mean()), "diff": float(d.mean()),
                                            "diff_ci95": _ci(boot), "b_only": b01, "a_only": b10, "mcnemar_exact_p": _binom_two_sided(b01, b01 + b10),
                                            "order_clusters_favouring_b": cl_b, "order_clusters_favouring_a": cl_a,
                                            "order_clusters_tied": len(variants) - cl_b - cl_a,
                                            "cluster_sign_test_p": _binom_two_sided(cl_b, cl_b + cl_a)}
    dest = ROOT / "research" / "phase2" / "reliability" / f"compare_{args.label}.json"
    dest.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    lines = [f"# Paired reliability comparison — {args.label}", "", f"network `{out['network']}`; A = `{out['a']['method']}`, B = `{out['b']['method']}`; "
             f"{out['n_paired']} paired runs (node order x seed) in {len(variants)} node-order clusters; failed runs A / B: "
             f"{out['n_failed']['a']} / {out['n_failed']['b']} (counted as failures); 95 % CIs resample node orders", "",
             "| metric | A | B | B - A [95% CI] |", "|---|---|---|---|"]
    for name, m in out["metrics"].items():
        lines.append(f"| {name} | {m['a_mean']:.3f} | {m['b_mean']:.3f} | {m['diff_mean']:+.3f} [{m['diff_ci95'][0]:+.3f}, {m['diff_ci95'][1]:+.3f}] |")
    ic = out["identity_consistency"]
    lines.append(f"| identity consistency (pairwise Jaccard, no self-pairs) | {ic['a']:.3f} | {ic['b']:.3f} | {ic['diff']:+.3f} "
                 f"[{ic['diff_ci95'][0]:+.3f}, {ic['diff_ci95'][1]:+.3f}] |")
    lines.append(f"| modal-core frequency | {ic['a_modal_frequency']:.2f} | {ic['b_modal_frequency']:.2f} | |")
    pa = out["paired_core_agreement"]
    lines.append(f"| same core in the paired run (A vs B, same order and seed) | {pa['n_identical']} of {out['n_paired']} | | paired Jaccard "
                 f"{pa['jaccard_mean']:.3f}; modal cores {'equal' if pa['a_modal_core_equals_b_modal_core'] else 'differ'} |")
    if "hidden_structural_success" in out:
        h = out["hidden_structural_success"]
        lines.append(f"| HIDDEN structural success | {h['a_rate']:.2f} | {h['b_rate']:.2f} | {h['diff']:+.2f} [{h['diff_ci95'][0]:+.2f}, "
                     f"{h['diff_ci95'][1]:+.2f}] (runs: {h['b_only']} B-only / {h['a_only']} A-only, McNemar p = {h['mcnemar_exact_p']:.3g}; "
                     f"order clusters {h['order_clusters_favouring_b']} B / {h['order_clusters_favouring_a']} A / {h['order_clusters_tied']} tied, "
                     f"sign test p = {h['cluster_sign_test_p']:.3g}) |")
    (dest.with_suffix(".md")).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
