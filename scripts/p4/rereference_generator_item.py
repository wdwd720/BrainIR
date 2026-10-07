"""Re-reference ONE item of the numerics self-test, `generator`, after a generator code change (ORCHESTRATOR ONLY; LOG P4-D71).

    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py run --local scripts/p4/rereference_generator_item.py [--runs 5] [--write]

Why: the `generator` item hashes the synthetic generator's own output, so a new generator version (v3.3, LOG P4-D71) changes it by
construction; the other 14 items (numpy / scipy / torch / real engine numerics) do not depend on the generator. The Modal reference
(scripts/p4/build_numerics_reference.py) cannot be rebuilt: zero further Modal spend (the user, 2026-09-28; LOG P4-D68). Every run
of Phase 4 now happens on this machine's pinned images, which reproduced ALL 15 items of the Modal reference before the change.

Rule (the builder's, restricted to one item): `--runs` FRESH batteries (`selftest.run_battery`, fresh processes, the container's pins)
must (a) reproduce every OTHER item of the current reference exactly, with the same battery id and library stack, with no errors, and
(b) all compute the same `generator` hash. Only then does --write replace that one item and append a provenance entry
(`rereferenced`: old and new hash, the generator source tree's sha256, the host class, the runs, the time). Run it in EACH pinned image
that runs generator code (driver and simulation service); a second image must reproduce the value the first one wrote (no --write
change then)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

ITEM = "generator"


def tree_sha256(base: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(q for q in base.rglob("*") if q.is_file() and "__pycache__" not in q.parts):
        h.update(p.relative_to(base).as_posix().encode() + b"\0")
        h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def main(argv=None) -> int:
    from brainir_causal.p4modal import gate
    from brainir_causal.p4modal import selftest as S
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--image", default="?", help="label of the image this runs in (recorded)")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    ref = S.load_reference()
    runs = [S.run_battery() for _ in range(args.runs)]
    problems = []
    for i, r in enumerate(runs):
        if r.get("errors"):
            problems.append(f"run {i}: errors {r['errors']}")
        if r.get("battery_id") != ref["battery_id"] or S.stack(r.get("versions")) != S.stack(ref["versions"]):
            problems.append(f"run {i}: battery / library stack differs from the reference")
        other = sorted(k for k in ref["items"] if k != ITEM and r["items"].get(k) != ref["items"][k])
        if other:
            problems.append(f"run {i}: items other than {ITEM} differ from the reference: {other}")
        if not r["items"].get(ITEM):
            problems.append(f"run {i}: {ITEM} absent (generator not in this image)")
    values = sorted({r["items"].get(ITEM) for r in runs})
    if len(values) != 1:
        problems.append(f"the runs disagree on {ITEM}: {values}")
    gen_src = Path(S.GENERATOR_DIRS[0])
    out = {"runs": args.runs, "image": args.image, "values": values, "old": ref["items"].get(ITEM), "problems": problems,
           "generator_tree_sha256": tree_sha256(gen_src) if gen_src.is_dir() else None, "host_class": gate.host_class().get("key")}
    print(json.dumps(out, indent=1), flush=True)
    if problems:
        return 1
    new = values[0]
    if new == ref["items"].get(ITEM):
        print(f"{ITEM}: this image reproduces the reference", flush=True)
        return 0
    if not args.write:
        print(f"{ITEM}: would change {out['old']} -> {new} (--write)", flush=True)
        return 0
    ref["items"][ITEM] = new
    ref.setdefault("rereferenced", []).append({"item": ITEM, "old": out["old"], "new": new, "image": args.image, "runs": args.runs,
                                               "generator_tree_sha256": out["generator_tree_sha256"], "host_class": out["host_class"],
                                               "reason": "generator v3.3 (code change); Modal reference not rebuildable (LOG P4-D68, P4-D71)",
                                               "builder": "scripts/p4/rereference_generator_item.py",
                                               "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    S.REFERENCE.write_text(json.dumps(ref, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {S.REFERENCE}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
