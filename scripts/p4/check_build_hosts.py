"""Host-gate verification of built real sets (ORCHESTRATOR SIDE; review H N6 / M5; LOG P4-D36).

    uv run --no-sync --project phase4 python scripts/p4/check_build_hosts.py --local data/phase4/real/real_public/public
    uv run --no-sync --project phase4 python scripts/p4/check_build_hosts.py --remote-level B

Every row of every system directory must carry a host fingerprint that the gate admits (`suites.host_summary`: flagged admissible,
AVX2 present, no AVX-512F). --local scans local copies; --remote-level scans the volume directories of a real level on Modal (one
`util` call per system directory; reading needs no gated host). Appends the result to research/phase4/REAL_DATA_BUILD.json; exit
code 1 if any row lacks an admissible fingerprint.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import suites as SU  # noqa: E402

BUILD_RECORD = ROOT / "research" / "phase4" / "REAL_DATA_BUILD.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--local", type=Path)
    g.add_argument("--remote-level", choices=sorted(SU.REAL_TIERS))
    args = ap.parse_args(argv)
    from brainir_causal.systems import load_real_internal
    sids = sorted(load_real_internal())
    t0 = time.time()
    cost = None
    if args.local is not None:
        rr = args.local.resolve()
        where = ("$DATA/" + rr.relative_to(ROOT / "data").as_posix()) if (ROOT / "data") in rr.parents else rr.name
        res = {s: SU.host_summary(str(args.local / SU._safe(s))) for s in sids}
    else:
        from brainir_causal.p4modal.app import Backend
        part = "public" if args.remote_level == "public" else "eval"
        base = SU.remote_dirs(SU.REAL_TIERS[args.remote_level], kind="real")[part]
        where = f"volume:{base}"
        with Backend(classes=["util"], app_name="brainir-p4-util") as be:
            out = be.call("brainir_causal.suites:host_summary", [[f"{base}/{SU._safe(s)}"] for s in sids], cls="util", threads=1,
                          reload=["fit", "eval"], timeout_s=3600)
            cost = be.cost_summary()
        res = {s: (r.get("result") if isinstance(r, dict) and "result" in r else {"error": repr(r)[:500]}) for s, r in zip(sids, out)}
    bad = [s for s, r in res.items() if r.get("_missing") or "error" in r or r.get("rows", 0) == 0 or r.get("admissible") != r.get("rows")]
    hosts: dict[str, int] = {}
    for r in res.values():
        for k, n in (r.get("hosts") or {}).items():
            hosts[k] = hosts.get(k, 0) + n
    rec = {"what": f"host fingerprints of the built real rows ({'local' if args.local is not None else 'level ' + args.remote_level})",
           "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "where": where, "systems": res,
           "rows": sum(r.get("rows", 0) for r in res.values()), "admissible": sum(r.get("admissible", 0) for r in res.values()),
           "hosts": hosts, "failing_systems": bad, "ok": not bad, "wall_s": round(time.time() - t0, 1), "modal_cost": cost}
    runs = json.loads(BUILD_RECORD.read_text(encoding="utf-8"))["runs"] if BUILD_RECORD.exists() else []
    BUILD_RECORD.write_text(json.dumps({"runs": runs + [rec]}, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: rec[k] for k in ("where", "rows", "admissible", "hosts", "failing_systems", "ok", "wall_s")}, indent=1))
    if cost:
        print(json.dumps({"usd_approx_total": cost.get("usd_approx_total")}))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
