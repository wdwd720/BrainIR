"""Paired comparison of pair-tournament arms (SELECTION_PROTOCOL.md §7.4, review E finding 4).

    uv run python scripts/compare_pair_arms.py research/phase2/tournament/<label>.json [more.json ...] \
        --compare joint:joint_null joint:independent_pooled independent_pooled:independent --out research/phase2/tournament/<label>_arms

For every base method and every requested pair of arms (A:B), runs are paired on (suite, instance, seed). Reported per comparison:
success of A and B on both networks, the paired success difference A - B, and the paired difference of total calls B - A (positive =
A is cheaper), each with a 95 % bootstrap CI that resamples INSTANCES (the seeds of an instance stay together), plus run-level
wins / losses and a two-sided sign-test p-value. A failed run counts as unsuccessful, and its calls count as the full limit.
Pre-registered reading: an efficiency gain needs the calls CI of joint vs joint_null entirely above 0; a success gain needs the
success CI entirely above 0 against both independent_pooled and joint_null.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


def _load(paths: list[Path]) -> list[dict]:
    recs = []
    for p in paths:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        for r in d["records"]:
            r = dict(r)
            r.setdefault("suite", d.get("suite"))
            r["_limit"] = int(d.get("budget_a", 0)) + int(d.get("budget_b", 0))
            recs.append(r)
    return recs


def _outcome(r: dict) -> tuple[float, float]:
    if "score" not in r:
        return 0.0, float(r["_limit"])
    return float(r["score"]["both_success"]), float((r["score"].get("budget") or {}).get("total", r["_limit"]))


def sign_test(wins: int, losses: int) -> float | None:
    n = wins + losses
    if n == 0:
        return None
    k = min(wins, losses)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def compare(recs: list[dict], method: str, arm_a: str, arm_b: str, *, n_boot: int = 4000, seed: int = 0) -> dict | None:
    idx = {}
    for r in recs:
        if r.get("method") == method and r.get("mode") in (arm_a, arm_b):
            idx[(r.get("suite"), r["instance"], r.get("seed"), r["mode"])] = r
    keys = sorted({(s, i, sd) for (s, i, sd, _m) in idx})
    pairs = [(k, idx.get((*k, arm_a)), idx.get((*k, arm_b))) for k in keys]
    pairs = [(k, a, b) for k, a, b in pairs if a is not None and b is not None]
    if not pairs:
        return None
    by_inst: dict[tuple, list] = {}
    for (s, i, _sd), a, b in pairs:
        (sa, ca), (sb, cb) = _outcome(a), _outcome(b)
        by_inst.setdefault((s, i), []).append((sa, sb, sa - sb, cb - ca))
    insts = sorted(by_inst)
    arr = [np.array(by_inst[k]) for k in insts]
    rng = np.random.default_rng(seed)
    boot_s, boot_c = [], []
    for _ in range(n_boot):
        pick = rng.integers(0, len(arr), len(arr))
        cat = np.concatenate([arr[j] for j in pick])
        boot_s.append(cat[:, 2].mean())
        boot_c.append(cat[:, 3].mean())
    allr = np.concatenate(arr)
    wins, losses = int((allr[:, 2] > 0).sum()), int((allr[:, 2] < 0).sum())
    return {"method": method, "a": arm_a, "b": arm_b, "n_runs": int(len(allr)), "n_instances": len(insts),
            "success_a": float(allr[:, 0].mean()), "success_b": float(allr[:, 1].mean()),
            "success_diff": float(allr[:, 2].mean()), "success_diff_ci95": [float(np.percentile(boot_s, 2.5)), float(np.percentile(boot_s, 97.5))],
            "calls_saved": float(allr[:, 3].mean()), "calls_saved_ci95": [float(np.percentile(boot_c, 2.5)), float(np.percentile(boot_c, 97.5))],
            "wins": wins, "losses": losses, "sign_test_p": sign_test(wins, losses)}


def to_markdown(rows: list[dict], sources: list[str]) -> str:
    lines = ["# Pair-tournament arms: paired comparisons", "", "Sources: " + ", ".join(f"`{s}`" for s in sources), "",
             "Pairs = (suite, instance, seed); CIs resample instances. Success = both networks solved. Calls saved = calls(B) - calls(A) "
             "(positive: A is cheaper). Failed runs count as unsuccessful at the full call limit.", "",
             "| method | A vs B | runs (instances) | success A / B | success A - B [95% CI] | calls saved by A [95% CI] | wins / losses (sign p) |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        p = "n/a" if r["sign_test_p"] is None else f"{r['sign_test_p']:.3f}"
        lines.append(f"| {r['method']} | {r['a']} vs {r['b']} | {r['n_runs']} ({r['n_instances']}) | {r['success_a']:.2f} / {r['success_b']:.2f} | "
                     f"{r['success_diff']:+.3f} [{r['success_diff_ci95'][0]:+.3f}, {r['success_diff_ci95'][1]:+.3f}] | "
                     f"{r['calls_saved']:+.1f} [{r['calls_saved_ci95'][0]:+.1f}, {r['calls_saved_ci95'][1]:+.1f}] | {r['wins']} / {r['losses']} ({p}) |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="+", type=Path)
    ap.add_argument("--compare", nargs="+", default=["joint:joint_null", "joint:independent_pooled", "joint:independent",
                                                      "independent_pooled:independent"])
    ap.add_argument("--out", type=Path, required=True, help="output stem (.json and .md are written)")
    args = ap.parse_args(argv)
    recs = _load(args.results)
    rows = []
    for m in sorted({r["method"] for r in recs if "method" in r}):
        for c in args.compare:
            a, b = c.split(":")
            row = compare(recs, m, a, b)
            if row is not None:
                rows.append(row)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".json").write_text(json.dumps({"sources": [str(p.name) for p in args.results], "rows": rows}, indent=1) + "\n",
                                             encoding="utf-8", newline="\n")
    args.out.with_suffix(".md").write_text(to_markdown(rows, [p.name for p in args.results]), encoding="utf-8", newline="\n")
    print(to_markdown(rows, [p.name for p in args.results]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
