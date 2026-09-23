"""Run a registered discovery method on one bundle network (also the clean-room method entry point).

Clean-room usage (the frozen runner sets the BRAINIR_* variables and passes extra argv to the method file):

    python -m brainir.discovery.run --method brainir_v1 --budget 1000 [--config key=value ...]

Programmatic:

    prediction, result = run_method("greedy_reference", bundle_root, "manc_v1.2.1", budget=500, seed=0)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from ..benchmark.prediction import BrainIRMechanismPrediction
from .interface import DiscoveryResult, MethodRegistry
from .problem import DiscoveryProblem
from .simulator import BudgetedSimulator


def _parse_kv(items: list[str]) -> dict:
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def run_method(method_name: str, bundle_root: Path | str, network: str, *, budget: int, seed: int, config: dict | None = None,
               workers: int = 1, backend=None, code_commit: str | None = None) -> tuple[BrainIRMechanismPrediction, DiscoveryResult]:
    problem = DiscoveryProblem.from_bundle(bundle_root, network)
    sim = BudgetedSimulator(problem, max_calls=budget, workers=workers, backend=backend)
    method = MethodRegistry.get(method_name)
    cfg = {**method.default_config, **(config or {})}
    t0 = time.time()
    result = method.discover(problem, sim, seed=seed, config=cfg)
    wall = time.time() - t0
    result.budget = {**sim.report(), "wall_s": round(wall, 2)}
    info = method.method_info(problem, sim, seed, cfg, wall_s=wall, code_commit=code_commit)
    return result.to_prediction(problem, info), result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--method", required=True)
    ap.add_argument("--budget", type=int, default=1000, help="hard simulator-call budget")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--config", nargs="*", default=[], help="key=value overrides (JSON values)")
    ap.add_argument("--bundle", type=Path, default=None, help="default: $BRAINIR_BUNDLE")
    ap.add_argument("--network", default=None, help="default: $BRAINIR_NETWORK")
    ap.add_argument("--out", type=Path, default=None, help="default: $BRAINIR_OUT")
    ap.add_argument("--seed", type=int, default=None, help="default: $BRAINIR_SEED or 0")
    ap.add_argument("--result-json", type=Path, default=None, help="also write the full DiscoveryResult")
    args = ap.parse_args(argv)
    bundle = args.bundle or Path(os.environ["BRAINIR_BUNDLE"])
    network = args.network or os.environ["BRAINIR_NETWORK"]
    out = args.out or Path(os.environ["BRAINIR_OUT"])
    seed = args.seed if args.seed is not None else int(os.environ.get("BRAINIR_SEED", "0"))
    pred, result = run_method(args.method, bundle, network, budget=args.budget, seed=seed, config=_parse_kv(args.config), workers=args.workers)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pred.to_json(), encoding="utf-8", newline="\n")
    if args.result_json is not None:
        args.result_json.write_text(json.dumps(result.to_dict(), indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    print(f"{args.method}: core {result.core} calls {result.budget.get('calls')} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
