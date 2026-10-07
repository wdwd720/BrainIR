"""Modal smoke of the worker-uid fix (P2's finding, 2026-09-27; research/phase4/EVAL_ARCHITECTURE.md section 6). ORCHESTRATOR SIDE.

    uv run --no-sync --project phase4 python scripts/p4/smoke_uids_modal.py [--slots 3] [--out <json>]

Runs `uid_probe_call:interleave_call` (scripts/p4/uid_probe_call.py) in `--slots` concurrent slots of ONE packed iso_pack_eval
container: in each, two models interleaved through two RemoteFresh (every call must succeed; two live workers, two uids), a digest
restart of one model while the other is live, the other's worker killed from outside (served again by a fresh process: one
infrastructure restart), the cost of a worker restart by part, and a restart-heavy sequence without / with pre-started spares
(identical outputs). The method (`uid_probe`: encode returns [pid, uid, tag, the history's sum]) travels
as the job's method snapshot; nothing held out is read. PASS when every slot passes.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import tarfile
import tempfile
import textwrap
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

UID_PROBE = textwrap.dedent("""
    import os
    import numpy as np
    from brainir_causal.api import CausalStateMethod, CausalStateModel, register

    class UidProbe(CausalStateModel):
        def __init__(self, tag):
            self.tag = float(tag)
            self.k = {"toy": 4}
        def encode(self, sid, x, u, dt):
            return np.array([float(os.getpid()), float(os.getuid()), self.tag, float(np.sum(np.asarray(x, float)))])
        def rollout(self, sid, z0, u_future, events, dt):
            Z = np.tile(np.asarray(z0, float), (len(u_future), 1))
            return {"z": Z, "y": Z[:, :1]}
        def readout(self, sid, z, u):
            return np.atleast_2d(z)[:, :1]
        def supports(self, sid, kind):
            return False
        def info(self):
            return {"k": dict(self.k)}

    @register
    class UidProbeMethod(CausalStateMethod):
        name = "uid_probe"
        def fit(self, data, *, systems, config=None, seed=0):
            return UidProbe((config or {}).get("tag", 0))
""")


def _tar(pkg: dict) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, src in pkg.items():
            data = src.encode("utf-8")
            ti = tarfile.TarInfo(name)
            ti.size, ti.mode = len(data), 0o644
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slots", type=int, default=3)
    ap.add_argument("--out", default=None)
    ap.add_argument("--deadline", type=float, default=600.0, help="per-slot DIAGNOSTIC deadline (stacks + process table returned)")
    args = ap.parse_args(argv)
    from brainir_causal.p4modal.app import Backend
    tar = _tar({"__init__.py": "", "uid_probe.py": UID_PROBE})
    payloads = [{"role": "call", "target": "uid_probe_call:interleave_call", "job": {"seed": i, "rounds": 6, "timing_n": 5, "deadline_s": args.deadline},
                 "method_tar": tar, "reload": ["fit"]} for i in range(args.slots)]
    snap = Path(tempfile.mkdtemp(prefix="p4uidsmoke_"))      # bake ONLY the trusted call script, from a private snapshot
    shutil.copy2(ROOT / "scripts" / "p4" / "uid_probe_call.py", snap / "uid_probe_call.py")
    t0 = time.time()
    with Backend(classes=["iso_pack_eval"], extra_dirs={str(snap): "/repo/scripts/p4"}, app_name="brainir-p4-uid-smoke") as be:
        res = be.run_iso_packed(payloads, "iso_pack_eval", expected_s=[1.0] * args.slots, label="uid-smoke")
        cost = be.cost_summary()
    reports = [(r.get("result") if isinstance(r, dict) and "result" in r else {"error": (r.get("error") if isinstance(r, dict) else repr(r))})
               for r in res]
    out = {"what": "worker-uid smoke (two interleaved RemoteFresh per packed slot; a killed worker; restart cost by part)",
           "slots": args.slots, "wall_s": round(time.time() - t0, 1), "pass": all(bool((r or {}).get("pass")) for r in reports),
           "reports": reports, "packs": [((r.get("iso") or {}).get("pack") if isinstance(r, dict) else None) for r in res], "cost": cost}
    txt = json.dumps(out, indent=1, default=str)
    if args.out:
        Path(args.out).write_text(txt + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": out["pass"], "wall_s": out["wall_s"],
                      "checks": [(r or {}).get("checks") for r in reports], "errors": [(r or {}).get("errors") or (r or {}).get("error")
                                                                                         for r in reports],
                      "restart_parts": [(r or {}).get("restart_parts") for r in reports],
                      "spare_timing": [(r or {}).get("spare_timing") for r in reports]}, indent=1, default=str))
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
