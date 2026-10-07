"""Dataset manifests for the causal_state_v1 benchmark lock (ORCHESTRATOR SIDE; LOG P4-D33).

    uv run --no-sync --project phase4 python scripts/p4/freeze_manifests.py --verify-local
    uv run --no-sync --project phase4 python scripts/p4/freeze_manifests.py --remote [--cls eval_s]      # optional independent re-hash

SOURCE OF TRUTH. Every build container returns the sha256 and size of every file it wrote, per part ({part: {path: [sha256,
bytes]}}); `build_on_modal.py` stores them as research/phase4/build_manifests/{real_public,real_B,syn_dev,syn_val}_<system>.json
(one per system and tier). The lock (`freeze_benchmark_p4.py`) hashes those manifest files, so every dataset file on the volumes
is covered by a hash taken where it was written.

--verify-local re-hashes the LOCAL copies (the dev tier's public part and the public real data: the only datasets that enter
rooms) and requires each system directory to equal the "public" part of its build manifest file for file.

--remote (optional) re-hashes every dataset directory WHERE IT LIVES (suites.hash_tree in containers with the volumes mounted,
one call per system directory) and compares with the build manifests: an independent check that nothing on the volumes changed
after the builds. Results go to research/phase4/build_manifests/remote_check/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import suites as SU  # noqa: E402

MAN = ROOT / "research" / "phase4" / "build_manifests"
LOCAL = {"syn_dev": ROOT / "data" / "phase4" / "suites" / "dev" / "public",
         "real_public": ROOT / "data" / "phase4" / "real" / "real_public" / "public"}


def local_manifest(d: Path) -> dict:
    out = {}
    for p in sorted(d.rglob("*")):
        if p.is_file():
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 22), b""):
                    h.update(chunk)
            out[p.relative_to(d).as_posix()] = [h.hexdigest(), p.stat().st_size]
    return out


def verify_local() -> list[str]:
    mism = []
    for prefix, root in LOCAL.items():
        if not root.exists():
            mism.append(f"{prefix}: local copy missing ({root})")
            continue
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            mf = MAN / f"{prefix}_{d.name}.json"
            if not mf.exists():
                mism.append(f"{prefix}/{d.name}: no build manifest")
                continue
            want = json.loads(mf.read_text(encoding="utf-8")).get("public") or {}
            have = local_manifest(d)
            if have != want:
                diff = sorted(set(have) ^ set(want)) + sorted(k for k in set(have) & set(want) if have[k] != want[k])
                mism.append(f"{prefix}/{d.name}: {len(diff)} differing files, e.g. {diff[:3]}")
    return mism


def remote_targets(only: tuple[str, ...] = ()) -> list[tuple[str, str, str]]:
    """(manifest file stem, part, container directory) for every system directory of every built tier (only: manifest-stem prefixes,
    e.g. ("real_B",) to check the cached real Level B sets alone)."""
    out = []
    for tier in ("dev", "val"):
        rd = SU.remote_dirs(tier, kind="synthetic")
        for mf in sorted(MAN.glob(f"syn_{tier}_*.json")):
            sd = mf.stem[len(f"syn_{tier}_"):]
            for part in json.loads(mf.read_text(encoding="utf-8")):
                out.append((mf.stem, part, f"{rd[part]}/{sd}"))
    for level in ("public", "B"):
        rd = SU.remote_dirs(SU.REAL_TIERS[level], kind="real")
        for mf in sorted(MAN.glob(f"real_{level}_*.json")):
            sd = mf.stem[len(f"real_{level}_"):]
            for part in json.loads(mf.read_text(encoding="utf-8")):
                out.append((mf.stem, part, f"{rd[part]}/{sd}"))
    return [t for t in out if not only or t[0].startswith(tuple(only))]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-local", action="store_true")
    ap.add_argument("--remote", action="store_true")
    ap.add_argument("--cls", default="eval_s")
    ap.add_argument("--only", default="", help="comma-separated manifest-stem prefixes for --remote (e.g. real_B)")
    args = ap.parse_args(argv)
    rc = 0
    if args.verify_local:
        mism = verify_local()
        print(json.dumps({"local_copies_equal_build_manifests": not mism, "mismatches": mism[:20]}, indent=1), flush=True)
        rc |= int(bool(mism))
    if args.remote:
        from brainir_causal.p4modal.app import Backend
        tg = remote_targets(tuple(x for x in args.only.split(",") if x))
        t0 = time.time()
        with Backend(classes=[args.cls], app_name="brainir-p4-freeze") as be:
            res = be.call("brainir_causal.suites:hash_tree", [[d] for _, _, d in tg], cls=args.cls, threads=1, reload=["fit", "eval"],
                          timeout_s=4 * 3600)
            cost = be.cost_summary()
        out_dir = MAN / "remote_check"
        out_dir.mkdir(parents=True, exist_ok=True)
        bad = []
        for (stem, part, d), r in zip(tg, res):
            have = r.get("result") if isinstance(r, dict) else None
            want = json.loads((MAN / f"{stem}.json").read_text(encoding="utf-8")).get(part) or {}
            if not isinstance(have, dict) or have != want:
                bad.append(f"{stem}:{part}")
        rec = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "directories": len(tg), "mismatch": bad,
               "wall_s": round(time.time() - t0, 1), "modal_cost": cost}
        (out_dir / "REMOTE_CHECK.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({k: rec[k] for k in ("directories", "mismatch", "wall_s")}, indent=1), flush=True)
        rc |= int(bool(bad))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
