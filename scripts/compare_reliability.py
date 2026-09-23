"""Paired comparison of two reliability sweeps on the same network, orders and seeds (goal3 sections 20, 21, 30).

    uv run python scripts/compare_reliability.py --a research/phase2/reliability/<baseline>.json \
        --b research/phase2/reliability/<method>.json --label <name>

Runs are paired by (node-order variant, seed). Reported with bootstrap 95 % CIs (runs resampled in pairs):
    functional fidelity (keep-only pass fraction on fresh seeds) and pass rate, core size, calls, simulated seconds
    identity consistency (pairwise Jaccard of cores in the common frame) of each sweep and their difference
    with --hidden (only after the method lock): structural success of each run from the logged hidden evaluation of both sweeps,
    paired difference and an exact McNemar test.
Output: research/phase2/reliability/compare_<label>.{json,md}.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _runs(path: Path) -> tuple[dict, dict]:
    d = json.loads(path.read_text(encoding="utf-8"))
    runs = {(r["variant"], int(r["seed"])): r for r in d["runs"] if "core_common" in r}
    return d, runs


def _sim_seconds(r: dict) -> float | None:
    c = r.get("compute") or {}
    if c.get("simulated_seconds") is not None:
        return float(c["simulated_seconds"])
    sims = c.get("simulations")
    if sims is None:
        return None
    return float(sims) * float(c.get("t_end_s") or 1.0)


def _jaccard_mean(cores: list[frozenset]) -> float:
    pairs = list(combinations(cores, 2))
    return float(np.mean([len(a & b) / len(a | b) if (a | b) else 1.0 for a, b in pairs])) if pairs else 1.0


def _ci(vals: list[float]) -> list[float]:
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def _mcnemar_exact(b01: int, b10: int) -> float:
    n = b01 + b10
    if n == 0:
        return 1.0
    k = min(b01, b10)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return float(min(1.0, 2 * p))


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
    rng = np.random.default_rng(0)
    metrics = {"functional_fidelity": lambda r: r.get("functional_fidelity"),
               "functional_pass": lambda r: None if r.get("functional_fidelity") is None else float(r["functional_fidelity"] >= 0.5),
               "core_size": lambda r: float(r["n_core"]), "calls": lambda r: None if r.get("calls") is None else float(r["calls"]),
               "simulated_seconds": _sim_seconds}
    out: dict = {"label": args.label, "network": da["summary"]["network"], "a": {"method": da["summary"]["method"], "file": args.a.name},
                 "b": {"method": db["summary"]["method"], "file": args.b.name}, "n_paired": len(keys), "metrics": {}}
    idx = np.arange(len(keys))
    for name, f in metrics.items():
        va = [f(ra[k]) for k in keys]
        vb = [f(rb[k]) for k in keys]
        ok = [i for i in idx if va[i] is not None and vb[i] is not None]
        if not ok:
            continue
        a = np.array([va[i] for i in ok], dtype=float)
        b = np.array([vb[i] for i in ok], dtype=float)
        d = b - a
        boot = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(args.n_boot)]
        out["metrics"][name] = {"n": len(ok), "a_mean": float(a.mean()), "b_mean": float(b.mean()), "diff_mean": float(d.mean()), "diff_ci95": _ci(boot)}
    ca = [frozenset(ra[k]["core_common"]) for k in keys]
    cb = [frozenset(rb[k]["core_common"]) for k in keys]
    boot_a, boot_b, boot_d = [], [], []
    for _ in range(min(args.n_boot, 2000)):
        s = rng.integers(0, len(keys), len(keys))
        ja, jb = _jaccard_mean([ca[i] for i in s]), _jaccard_mean([cb[i] for i in s])
        boot_a.append(ja)
        boot_b.append(jb)
        boot_d.append(jb - ja)
    ja, jb = _jaccard_mean(ca), _jaccard_mean(cb)
    out["identity_consistency"] = {"a": ja, "b": jb, "a_ci95": _ci(boot_a), "b_ci95": _ci(boot_b), "diff": jb - ja, "diff_ci95": _ci(boot_d),
                                   "a_modal_frequency": max(ca.count(c) for c in set(ca)) / len(ca),
                                   "b_modal_frequency": max(cb.count(c) for c in set(cb)) / len(cb)}
    if args.hidden:
        ha, hb = da["summary"].get("hidden_eval"), db["summary"].get("hidden_eval")
        if not ha or not hb:
            raise SystemExit("--hidden needs both sweeps to carry a logged hidden evaluation")
        sa = {(r["variant"], int(r["seed"])): bool(r.get("e_core_recall") == 1.0 and r.get("inhibitory_slot")) for r in ha["rows"] if "e_core_recall" in r}
        sb = {(r["variant"], int(r["seed"])): bool(r.get("e_core_recall") == 1.0 and r.get("inhibitory_slot")) for r in hb["rows"] if "e_core_recall" in r}
        hk = sorted(set(sa) & set(sb))
        x = np.array([sa[k] for k in hk], dtype=float)
        y = np.array([sb[k] for k in hk], dtype=float)
        d = y - x
        boot = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(args.n_boot)]
        b01, b10 = int(((x == 0) & (y == 1)).sum()), int(((x == 1) & (y == 0)).sum())
        out["hidden_structural_success"] = {"n": len(hk), "a_rate": float(x.mean()), "b_rate": float(y.mean()), "diff": float(d.mean()),
                                            "diff_ci95": _ci(boot), "b_only": b01, "a_only": b10, "mcnemar_exact_p": _mcnemar_exact(b01, b10)}
    dest = ROOT / "research" / "phase2" / "reliability" / f"compare_{args.label}.json"
    dest.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    lines = [f"# Paired reliability comparison — {args.label}", "", f"network `{out['network']}`; A = `{out['a']['method']}`, B = `{out['b']['method']}`; "
             f"{out['n_paired']} paired runs (node order x seed)", "", "| metric | A | B | B - A [95% CI] |", "|---|---|---|---|"]
    for name, m in out["metrics"].items():
        lines.append(f"| {name} | {m['a_mean']:.3f} | {m['b_mean']:.3f} | {m['diff_mean']:+.3f} [{m['diff_ci95'][0]:+.3f}, {m['diff_ci95'][1]:+.3f}] |")
    ic = out["identity_consistency"]
    lines.append(f"| identity consistency (pairwise Jaccard) | {ic['a']:.3f} | {ic['b']:.3f} | {ic['diff']:+.3f} [{ic['diff_ci95'][0]:+.3f}, "
                 f"{ic['diff_ci95'][1]:+.3f}] |")
    lines.append(f"| modal-core frequency | {ic['a_modal_frequency']:.2f} | {ic['b_modal_frequency']:.2f} | |")
    if "hidden_structural_success" in out:
        h = out["hidden_structural_success"]
        lines.append(f"| HIDDEN structural success | {h['a_rate']:.2f} | {h['b_rate']:.2f} | {h['diff']:+.2f} [{h['diff_ci95'][0]:+.2f}, "
                     f"{h['diff_ci95'][1]:+.2f}] (McNemar p = {h['mcnemar_exact_p']:.3g}) |")
    (dest.with_suffix(".md")).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
