"""Runs INSIDE the Phase 3 regeneration room (goal4 section 5): the locked BrainIR v1.2 on the public blind bundle, with the
public no-gate rhythm criterion, then keep-only validation of every returned candidate on fresh public parameter seeds.

    python regen_in_room.py <room> <out.json>

Only the room's copy of the library, the locked method and the public bundle are used; a Python audit hook (PYTHONPATH pyguard)
refuses every other location. Nothing here reads truth or an oracle.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from brainir.discovery.problem import DiscoveryProblem
from brainir.discovery.reliability import functional_fidelity
from brainir.discovery.run import run_method

NETWORKS = ("manc_v1.2.1", "male-cns_v1.0", "manc_v1.2.3")
SEED, BUDGET = 0, 1000
VALIDATION_SEEDS = list(range(9000, 9008))


def _as_set(a) -> list[int]:
    if isinstance(a, dict):
        for k in ("members", "set", "core"):
            if k in a:
                return sorted(int(x) for x in a[k])
        raise ValueError(f"unrecognised alternative record {sorted(a)}")
    return sorted(int(x) for x in a)


def main() -> int:
    room, out = Path(sys.argv[1]), Path(sys.argv[2])
    nets = sys.argv[3:] or list(NETWORKS)
    bundle = room / "bundle"
    report = {"method": "brainir_v1", "seed": SEED, "budget": BUDGET, "criterion": "public (amplitude gate 0)", "validation_seeds": VALIDATION_SEEDS,
              "networks": {}}
    for net in nets:
        t0 = time.time()
        pred, res = run_method("brainir_v1", bundle, net, budget=BUDGET, seed=SEED)
        problem = DiscoveryProblem.from_bundle(bundle, net)
        pos_of = {int(i): k for k, i in enumerate(problem.public_ids)}
        cands = [("final_core", sorted(int(p) for p in res.core))]
        for j, a in enumerate(res.alternatives or []):
            cands.append((f"alternative_{j}", _as_set(a)))
        seen, rows = set(), []
        for label, members in cands:
            key = tuple(members)
            if not members or key in seen:
                continue
            seen.add(key)
            positions = [pos_of[int(m)] for m in members if int(m) in pos_of]
            fid = functional_fidelity(problem, positions, VALIDATION_SEEDS, workers=1)
            rows.append({"label": label, "members": members, "size": len(members), "keep_only_pass_fraction": float(fid),
                         "validated": bool(fid >= 0.5)})
        report["networks"][net] = {"criterion_spec": problem.criterion_spec, "n": problem.n, "candidates": rows,
                                   "inclusion_probability_top": dict(sorted(((str(k), round(float(v), 4)) for k, v in res.inclusion_probability.items()
                                                                            if v >= 0.05), key=lambda kv: -kv[1])),
                                   "method_budget": res.budget, "flags": (res.diagnostics or {}).get("flags"), "wall_s": round(time.time() - t0, 1),
                                   "prediction": json.loads(pred.model_dump_json())}
        print(f"{net}: {len(rows)} candidates; validated {sum(r['validated'] for r in rows)}; {time.time() - t0:.0f}s", flush=True)
    out.write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
