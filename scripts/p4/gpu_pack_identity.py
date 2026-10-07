"""GPU packing bit-identity (research/phase4/LEVEL_B_EXECUTION.md section 5; fork P1). ORCHESTRATOR SIDE.

    uv run --no-sync --project phase4 python scripts/p4/gpu_pack_identity.py --room <stand-in room> --system <sid> [--tier val]
        [--gpu rtx6000] [--out <json>]

The GPU stand-in (a method declaring device 'cuda', seed 0) fitted UNPACKED (iso_gpu_<gpu>: one fit per GPU, twice) and PACKED
(iso_pack_gpu_<gpu>: 4 fits on ONE GPU at once) must give the same model: every parameter array and the final training loss equal bit
for bit (its own train_s timing excluded). FITS ONLY (public training data). The fitted models are loaded here to compare them: the
stand-in is our own trusted dry-run code (never a candidate's model); the room's methods package is added to brainir_causal's path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "p4"))

from brainir_causal import suites as SU  # noqa: E402


def fit_payload(method: str, sid: str, tier: str, key: str) -> dict:
    import tournament as T
    kind = "real" if sid.startswith("real:") else "synthetic"
    return {"role": "fit", "job": {"method": method, "systems": [sid], "data": [T.modal_system_paths(sid, kind, tier)["fit_data"]], "seed": 0,
                                   "config": {}, "threads": 3, "timeout_s": 3600}, "methods_key": key, "reload": ["fit"]}


def model_bytes(be, r) -> bytes | None:
    if not isinstance(r, dict) or r.get("error"):
        return None
    if isinstance(r.get("model"), (bytes, bytearray)):
        return bytes(r["model"])
    if isinstance(r.get("model_ref"), dict):
        return be.stage_get(r["model_ref"])
    return None


def fingerprint(blob: bytes) -> dict:
    """The scientific content of a fitted stand-in model: sha256 of every parameter array, of the readout and the final loss."""
    import numpy as np
    m = pickle.loads(blob)
    arrs = {k: np.ascontiguousarray(v) for k, v in sorted(m.p.items())}
    arrs["Wy"] = np.ascontiguousarray(m.Wy)
    return {"arrays": {k: hashlib.sha256(v.tobytes()).hexdigest()[:16] for k, v in arrs.items()},
            "final_loss": repr(m.stats.get("final_loss")), "device": m.stats.get("device"), "gpu_name": m.stats.get("gpu_name"),
            "train_s": m.stats.get("train_s")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", required=True)
    ap.add_argument("--system", required=True)
    ap.add_argument("--tier", default="val")
    ap.add_argument("--method", default="p1_standin_torch_gpu")
    ap.add_argument("--gpu", default="rtx6000")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    from brainir_causal.p4modal.app import CLASSES, Backend
    unpacked, packed = f"iso_gpu_{args.gpu}", f"iso_pack_gpu_{args.gpu}"
    mdir = Path(args.room) / "src" / "brainir_causal" / "methods"
    import brainir_causal                                     # the stand-in's package (the room's brainir_causal.methods), to load its models
    brainir_causal.__path__.append(str(Path(args.room) / "src" / "brainir_causal"))
    extra = {SU.GENERATOR_REL: SU.GENERATOR_CONTAINER} if not args.system.startswith("real:") else None
    rep: dict = {"what": "GPU packing bit-identity (fits on public data only)", "system": args.system, "tier": args.tier,
                 "classes": [unpacked, packed], "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    from concurrent.futures import ThreadPoolExecutor
    with Backend(classes=[unpacked, packed], extra_dirs=extra, app_name="brainir-p4-p1-gpuid") as be:
        key = be.methods_key(mdir)
        pl = fit_payload(args.method, args.system, args.tier, key)
        n_slots = int(CLASSES[packed]["slots"])
        with ThreadPoolExecutor(max_workers=2) as ex:            # bounded: one thread per class kind
            fu = ex.submit(be.run_iso, [dict(pl), dict(pl)], unpacked, "gpuid:unpacked")
            fp = ex.submit(be.run_iso_packed, [dict(pl) for _ in range(n_slots)], packed, expected_s=[1.0] * n_slots, label="gpuid:packed")
            ru, rp = fu.result(), fp.result()
        blobs = {"unpacked": [model_bytes(be, r) for r in ru], "packed": [model_bytes(be, r) for r in rp]}
        errors = {kind: [str((r or {}).get("error") if isinstance(r, dict) else r)[:500] for r, b in zip(res, blobs[kind]) if b is None]
                  for kind, res in (("unpacked", ru), ("packed", rp))}
        rep["cost"] = be.cost_summary()
    if args.out:                                               # the models first: a local failure below must not lose the Modal work
        md = Path(args.out).with_suffix(".models")
        md.mkdir(parents=True, exist_ok=True)
        for kind, bl in blobs.items():
            for i, b in enumerate(bl):
                if b is not None:
                    (md / f"{kind}_{i}.pkl").write_bytes(b)
    fps = {kind: [fingerprint(b) for b in bl if b is not None] + [{"error": e} for e in errors[kind]] for kind, bl in blobs.items()}
    rep["fingerprints"] = fps
    sci = [json.dumps({k: v for k, v in f.items() if k not in ("train_s", "gpu_name")}, sort_keys=True) for f in fps["unpacked"] + fps["packed"]]
    rep["n_models"] = len(sci)
    rep["all_identical"] = bool(sci and all("error" not in json.loads(s) for s in sci) and len(set(sci)) == 1)
    rep["gpus"] = sorted({str(f.get("gpu_name")) for f in fps["unpacked"] + fps["packed"]})
    txt = json.dumps(rep, indent=1, default=str)
    if args.out:
        Path(args.out).write_text(txt + "\n", encoding="utf-8", newline="\n")
    print(txt)
    return 0 if rep["all_identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
