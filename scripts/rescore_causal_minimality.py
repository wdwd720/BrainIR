"""Add the clarified causal-minimality metric to finished tournament results (see tournament.causal_minimality).

    uv run python scripts/rescore_causal_minimality.py research/phase2/tournament/sel_mech_b1000_part1.json [...] \
        --suite data/synthetic/mechanisms_v1_heldout [--workers 3]

For every scored record whose core was sufficient, the members that keep-only could remove are silenced one at a time in the
intact network with the record's own score seeds; `function.functional_success_causal` and the summaries are rewritten (the
pre-registered `functional_success` is left untouched). The markdown table is regenerated.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from brainir.discovery.problem import DiscoveryProblem
from brainir.discovery.simulator import BudgetedSimulator
from brainir.discovery.tournament import _json_default, causal_minimality, summarize, to_markdown


def _job(args) -> tuple[int, dict]:
    i, inst_dir, network, removable, seeds, sufficient = args
    problem = DiscoveryProblem.from_bundle(inst_dir, network)
    sim = BudgetedSimulator(problem, max_calls=10 ** 9)
    return i, causal_minimality(problem, sim, removable, seeds, sufficient=sufficient)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+", type=Path)
    ap.add_argument("--suite", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args(argv)
    for path in args.results:
        d = json.loads(path.read_text(encoding="utf-8"))
        seeds = [int(s) for s in d.get("score_seeds", [5000, 5001, 5002, 5003])]
        jobs = []
        for i, r in enumerate(d["records"]):
            f = r.get("function") or {}
            if "structure" not in r or f.get("minimality") is None:
                continue
            removable = [int(p) for p in f["minimality"]["removable_members"]]
            sufficient = (f.get("nominal") or 0) >= 0.5
            if not removable:
                f.update({"context_members": [], "unjustified_members": [], "functional_success_causal": bool(sufficient)})
                continue
            jobs.append((i, str(args.suite / "instances" / r["instance"]), r["network"], removable, seeds, sufficient))
        if args.workers > 1 and len(jobs) > 1:
            with ProcessPoolExecutor(max_workers=args.workers) as ex:
                results = list(ex.map(_job, jobs))
        else:
            results = [_job(j) for j in jobs]
        for i, extra in results:
            d["records"][i]["function"].update(extra)
        d["summary"] = summarize(d["records"])
        d["rescored"] = {"causal_minimality": True, "n_rechecked": len(jobs)}
        path.write_text(json.dumps(d, indent=1, default=_json_default) + "\n", encoding="utf-8", newline="\n")
        path.with_suffix(".md").write_text(to_markdown(d), encoding="utf-8", newline="\n")
        print(f"{path.name}: {len(jobs)} records re-checked; causal functional success:",
              {m: round(s.get("functional_success_causal_rate") or 0, 3) for m, s in d["summary"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
