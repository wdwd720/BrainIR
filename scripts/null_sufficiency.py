"""Matched random null for a predicted mechanism (goal3 section 53: "could a random matched method achieve this?"), oracle-free.

    uv run python scripts/null_sufficiency.py --bundle benchmarks/dng100/public_blind --network manc_v1.2.1 \
        --prediction <prediction.json> [--n-null 50] [--pool active] --label <name>

For the core of a prediction (or --core positions), random interneuron sets of the SAME size and sign composition are drawn
(pool `all` = every candidate interneuron; pool `active` = interneurons active in the intact network on the reference seeds,
the harder null) and tested for keep-only sufficiency on fresh parameter seeds with the public simulator. Reported: the
prediction's own pass fraction, the null pass-rate distribution, and the empirical p-value (fraction of null sets passing at
least as often). Writes research/phase2/nulls/<label>.{json,md}.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from brainir.benchmark.prediction import BrainIRMechanismPrediction
from brainir.discovery.interventions import keep_only
from brainir.discovery.problem import DiscoveryProblem
from brainir.discovery.simulator import BudgetedSimulator

ROOT = Path(__file__).resolve().parents[1]
FRESH = (9100, 9101, 9102, 9103)
REF = (9200, 9201)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, default=ROOT / "benchmarks" / "dng100" / "public_blind")
    ap.add_argument("--network", required=True)
    ap.add_argument("--prediction", type=Path, default=None)
    ap.add_argument("--core", nargs="*", type=int, default=None, help="core positions (instead of --prediction)")
    ap.add_argument("--n-null", type=int, default=50)
    ap.add_argument("--pool", choices=["all", "active"], default="active")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "research" / "phase2" / "nulls")
    args = ap.parse_args(argv)
    p = DiscoveryProblem.from_bundle(args.bundle, args.network)
    if args.prediction is not None:
        pred = BrainIRMechanismPrediction.from_json(args.prediction.read_text(encoding="utf-8"))
        pos_of = {int(i): k for k, i in enumerate(p.public_ids)}
        core = sorted(pos_of[int(i)] for i in pred.core_ids())
    else:
        core = sorted(int(x) for x in args.core or [])
    if not core:
        raise SystemExit("empty core")
    sim = BudgetedSimulator(p, max_calls=10 ** 9, workers=args.workers)
    cand = set(int(x) for x in p.candidate_positions())
    if args.pool == "active":
        act = set()
        for o in sim.evaluate(None, list(REF)):
            act |= set(int(x) for x in o.active_positions)
        pool = sorted(cand & act)
    else:
        pool = sorted(cand)
    signs = [int(p.signs[c]) for c in core]
    by_sign = {s: [q for q in pool if int(p.signs[q]) == s] for s in set(signs)}
    rng = np.random.default_rng(args.seed)
    own = sim.pass_fraction(keep_only(p, core), list(FRESH))
    nulls, sets = [], []
    for _ in range(args.n_null):
        pick: set[int] = set()
        for s in signs:
            options = [q for q in by_sign.get(s, []) if q not in pick and q not in core] or [q for q in pool if q not in pick and q not in core]
            pick.add(int(rng.choice(options)))
        sets.append(sorted(pick))
    ivs = [keep_only(p, s) for s in sets]
    from brainir.discovery.simulator import SimQuery
    outs = sim.run_many([SimQuery(iv, s) for iv in ivs for s in FRESH])
    k = len(FRESH)
    for i in range(len(sets)):
        nulls.append(float(np.mean([o.passed for o in outs[i * k:(i + 1) * k]])))
    nulls_arr = np.array(nulls)
    res = {"label": args.label, "network": args.network, "core": core, "size": len(core), "signs": signs, "pool": args.pool, "pool_size": len(pool),
           "own_pass_fraction": own, "null_pass_rate": float(np.mean(nulls_arr >= 0.5)), "null_pass_fraction_mean": float(nulls_arr.mean()),
           "empirical_p": float((1 + np.sum(nulls_arr >= own)) / (1 + len(nulls_arr))), "n_null": len(nulls), "fresh_seeds": list(FRESH),
           "calls": sim.calls}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{args.label}.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    md = [f"# Matched random null — {args.label}", "", f"network `{args.network}`; core size {len(core)} (signs {signs}); pool `{args.pool}` "
          f"({len(pool)} interneurons); {len(nulls)} random sign-matched sets x {len(FRESH)} fresh seeds", "",
          f"- core keep-only pass fraction: {own:.2f}", f"- null: {res['null_pass_rate']:.2f} of random sets pass (mean pass fraction "
          f"{res['null_pass_fraction_mean']:.2f}); empirical p = {res['empirical_p']:.3f}"]
    (args.out / f"{args.label}.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
