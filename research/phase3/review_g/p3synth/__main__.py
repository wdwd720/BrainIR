"""CLI: uv run python -m p3synth --public out/public --truth out/truth --seed 0 --tier dev"""

import argparse
import json
from pathlib import Path

from .suite import build_suite


def main():
    ap = argparse.ArgumentParser(prog="p3synth")
    ap.add_argument("--public", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tier", default="dev", choices=["dev", "heldout", "final"])
    ap.add_argument("--scale", type=float, default=None)
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()
    res = build_suite(Path(a.public), Path(a.truth), a.seed, a.tier, scale=a.scale, workers=a.workers)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
