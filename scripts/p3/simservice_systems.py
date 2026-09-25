"""Write the system definitions the simulation service serves (orchestrator; PROTOCOL.md section 3).

    uv run --project phase3 python scripts/p3/simservice_systems.py --suite dev      -> hidden/simservice_systems_dev.json
    uv run --project phase3 python scripts/p3/simservice_systems.py --suite heldout  -> hidden/simservice_systems_heldout.json

dev: the real public systems (internal definitions) + the synthetic DEV systems (method development, Level A).
heldout / final: the synthetic systems of that suite only (sandboxed tournament fits that use the simulator, Level B).
Synthetic definitions carry the suite's tier and seed (never shown to a method), the public targets, and event-magnitude bounds of
twice the largest magnitude used in the suite's public training protocols.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "benchmarks" / "state_discovery_v1"
DATA = ROOT / "data" / "phase3"


def synthetic_defs(tier: str) -> dict:
    rec = json.loads((BENCH / "hidden" / "synthetic_suites.json").read_text(encoding="utf-8"))[tier]
    pub = DATA / "synthetic_dev" if tier == "dev" else DATA / "synthetic" / tier / "public"
    man = json.loads((pub / "manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (pub / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    kmax, cmax = {}, {}
    for r in rows:
        if r["split"] not in ("train", "val"):
            continue
        for e in r["protocol"].get("events") or []:
            if e["kind"] == "kick":
                kmax[r["system_id"]] = max(kmax.get(r["system_id"], 0.0), max(abs(v) for v in e["delta"].values()))
            elif e["kind"] == "current":
                cmax[r["system_id"]] = max(cmax.get(r["system_id"], 0.0), max(abs(v) for v in e["targets"].values()))
    out = {}
    for sid, d in man["systems"].items():
        out[sid] = {"system_id": sid, "kind": "synthetic", "tier": tier, "suite_seed": int(rec["seed"]), "n": int(d["n"]),
                    "input_dim": int(d["input_dim"]), "observed": d["observed"], "targets_public": d["targets_public"],
                    "kick_max": 2.0 * kmax.get(sid, 1.0), "current_max": 2.0 * cmax.get(sid, 1.0)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="dev")
    args = ap.parse_args(argv)
    systems = {}
    if args.suite == "dev":
        real = json.loads((BENCH / "hidden" / "systems_internal.json").read_text(encoding="utf-8"))
        # budget units per trajectory: a real full circuit takes ~10-30 CPU-s, a keep-only mechanism ~1-5 s, a synthetic system ~0.1 s
        systems.update({sid: dict(d, cost=10 if d["mode"] == "full" else 3) for sid, d in real.items()})
    systems.update({sid: dict(d, cost=1) for sid, d in synthetic_defs(args.suite).items()})
    out = BENCH / "hidden" / f"simservice_systems_{args.suite}.json"
    out.write_text(json.dumps(systems, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{out.relative_to(ROOT)}: {len(systems)} systems")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
