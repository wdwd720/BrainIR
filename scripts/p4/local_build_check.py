"""LOCAL build == Modal build, file for file (ORCHESTRATOR SIDE; research/phase4/LOCAL_EXECUTION_PLAN.md). Plans and builds ONE
synthetic system with the benchmark's own code (`suites.plan_remote_job`, `suites.build_system_job`) in the pinned Linux image on this
machine, into SCRATCH volumes, and compares the sha256 of every file it wrote with the manifest the Modal build recorded
(research/phase4/build_manifests/syn_<tier>_<system>.json). Nothing of the real volumes, records or manifests is touched.

    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py run --local --vol-root C:/Dev/BrainIR_p4run/vol_check \
        --memory-gb 4 --cpus 8 scripts/p4/local_build_check.py --tier dev --system <sid> --workers 8 \
        --out research/phase4/LOCAL_BUILD_CHECK.json

Exit 0 when every part's file set and every hash equal the Modal manifest."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="dev")
    ap.add_argument("--system", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="research/phase4/LOCAL_BUILD_CHECK.json")
    args = ap.parse_args(argv)
    if os.environ.get("P4_LOCAL_VOLUMES") != "1":
        raise SystemExit("run in the local driver container with a scratch --vol-root")
    from brainir_causal import suites as SU
    from brainir_causal.p4modal import gate
    h = gate.host_cpu()
    st = gate.numerics_selftest()
    if not gate.admissible(h) or not st.get("ok"):
        raise SystemExit(f"not the reference platform: gate {gate.admissible(h)}, self-test {st.get('ok')}")
    man_p = ROOT / "research" / "phase4" / "build_manifests" / f"syn_{args.tier}_{SU._safe(args.system)}.json"
    modal_manifest = json.loads(man_p.read_text(encoding="utf-8"))
    t0 = time.time()
    job = SU.plan_remote_job("synthetic", args.system, tier=args.tier, generator=(str(ROOT / SU.GENERATOR_REL), "p4synth"),
                             workers=int(args.workers))
    t1 = time.time()
    r = SU.build_system_job(job)
    t2 = time.time()
    local_manifest = r["manifest"]
    parts = {}
    ok = True
    for part, mm in modal_manifest.items():
        lm = local_manifest.get(part) or {}
        mfiles = mm.get("files") if isinstance(mm, dict) and "files" in mm else mm
        lfiles = lm.get("files") if isinstance(lm, dict) and "files" in lm else lm
        mk, lk = set(mfiles or {}), set(lfiles or {})
        diff = sorted(k for k in mk & lk if mfiles[k] != lfiles[k])
        parts[part] = {"modal_files": len(mk), "local_files": len(lk), "only_modal": sorted(mk - lk)[:10], "only_local": sorted(lk - mk)[:10],
                       "hash_differs": diff[:10], "n_hash_differs": len(diff)}
        ok = ok and mk == lk and not diff
    rec = {"what": "local build vs Modal build manifest (one system)", "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "tier": args.tier, "system": args.system, "workers": args.workers, "host": h.get("model"), "selftest_ok": st.get("ok"),
           "plan_s": round(t1 - t0, 1), "build_s": round(t2 - t1, 1), "build_result": {k: r.get(k) for k in ("wall_s", "workers", "published")},
           "peak_container_mb": r.get("peak_container_mb"), "parts": parts, "identical": ok}
    out = ROOT / args.out
    out.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"identical": ok, "plan_s": rec["plan_s"], "build_s": rec["build_s"],
                      "parts": {p: (v["modal_files"], v["local_files"], v["n_hash_differs"]) for p, v in parts.items()}}), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
