"""Write the benchmark's merged PUBLIC system records (ORCHESTRATOR SIDE; research/phase4/PREFREEZE_TODO.md item 12).

    uv run --no-sync --project phase4 python scripts/p4/merge_public_systems.py [--check]

benchmarks/causal_state_v1/public/systems_public.json = {system id: public record} for every system a developer may use: the
development tier's synthetic systems (the "systems" entry of each downloaded public part's manifest.json,
data/phase4/suites/dev/public/<system>/manifest.json) and the real public systems (public/systems_real_public.json). Every record
passes `suites.assert_public_record` (whitelisted fields only, no per-unit lists) before it is written; a system present twice with
different records, a dev system without a downloaded public part, or a record failing the check stops the script. --check compares
the file with what would be written (exit 1 on a difference).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import suites as SU  # noqa: E402

BENCH = ROOT / "benchmarks" / "causal_state_v1"
OUT = BENCH / "public" / "systems_public.json"
DEV = ROOT / "data" / "phase4" / "suites" / "dev"


def merged() -> dict:
    dev_ids = sorted(json.loads((DEV / "internal_records.json").read_text(encoding="utf-8")))
    out: dict[str, dict] = {}
    for sid in dev_ids:
        man = DEV / "public" / SU._safe(sid) / "manifest.json"
        if not man.exists():
            raise SystemExit(f"no downloaded public part for {sid} ({man.relative_to(ROOT)}): download the dev public part first")
        recs = json.loads(man.read_text(encoding="utf-8"))["systems"]
        if set(recs) != {sid}:
            raise SystemExit(f"{man.relative_to(ROOT)} describes {sorted(recs)}, expected only {sid}")
        out[sid] = recs[sid]
    for sid, rec in json.loads((BENCH / "public" / "systems_real_public.json").read_text(encoding="utf-8")).items():
        if sid in out and out[sid] != rec:
            raise SystemExit(f"{sid} appears twice with different records")
        out[sid] = rec
    for sid, rec in out.items():
        SU.assert_public_record(rec)
        if rec.get("system_id") != sid:
            raise SystemExit(f"record under {sid} names {rec.get('system_id')}")
    return dict(sorted(out.items()))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    text = json.dumps(merged(), indent=1, sort_keys=True) + "\n"
    if args.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("systems_public.json is current" if same else "systems_public.json DIFFERS from the current public parts")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    n = json.loads(text)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(n)} systems ({sum(1 for r in n.values() if r.get('kind') == 'synthetic')} synthetic, "
          f"{sum(1 for r in n.values() if r.get('kind') == 'real')} real)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
