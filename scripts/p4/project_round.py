"""Projected wall time of a Level B round on Modal (research/phase4/LEVEL_B_EXECUTION.md section 7; fork P1).

    uv run --no-sync --project phase4 python scripts/p4/project_round.py --spec spec.json

A PROJECTION from measured job durations: every job group {"name", "stage", "n", "seconds", "cls"} is expanded to n jobs of the given
duration, each stage's jobs are list-scheduled LONGEST FIRST onto the earliest-free slot of `containers x slots` (the same greedy
order Modal's queue gives a longest-first submission to packed containers), and stages run in sequence unless they share a "concurrent"
group (the tournament's fits and references). Container start-up is added once per stage. Prints the makespan per stage and in total.
spec: {"containers": {cls: n}, "slots": {cls: n}, "startup_s": 90, "groups": [...], "concurrent": [["fits", "references"]]}.
"""

from __future__ import annotations

import argparse
import heapq
import json
from pathlib import Path


def makespan(durations: list[float], machines: int) -> float:
    """Greedy list scheduling, longest first, onto the earliest-free machine (LPT; within 4/3 of optimal)."""
    if not durations:
        return 0.0
    heap = [0.0] * max(1, int(machines))
    heapq.heapify(heap)
    for d in sorted(durations, reverse=True):
        t = heapq.heappop(heap)
        heapq.heappush(heap, t + float(d))
    return max(heap)


def project(spec: dict) -> dict:
    stages: dict = {}
    for g in spec["groups"]:
        stages.setdefault(g["stage"], []).append(g)
    out = {}
    for st, groups in stages.items():
        per_cls: dict = {}
        for g in groups:
            per_cls.setdefault(g["cls"], []).extend([float(g["seconds"])] * int(g["n"]))
        ms = {c: makespan(d, int(spec["containers"].get(c, 1)) * int(spec["slots"].get(c, 1))) for c, d in per_cls.items()}
        out[st] = {"per_class_s": {c: round(v, 1) for c, v in ms.items()}, "makespan_s": round(max(ms.values()) + float(spec.get("startup_s", 90)), 1),
                   "n_jobs": sum(len(d) for d in per_cls.values())}
    total, done = 0.0, set()
    for grp in spec.get("concurrent") or []:
        present = [s for s in grp if s in out]
        if present:
            total += max(out[s]["makespan_s"] for s in present)
            done.update(present)
    for st, v in out.items():
        if st not in done:
            total += v["makespan_s"]
    return {"stages": out, "total_s": round(total, 1), "total_h": round(total / 3600.0, 2)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True, type=Path)
    args = ap.parse_args(argv)
    res = project(json.loads(args.spec.read_text(encoding="utf-8")))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
