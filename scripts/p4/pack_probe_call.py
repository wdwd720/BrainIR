"""Trusted driver function for the packed-isolation smoke test (scripts/p4/smoke_pack_modal.py), baked into the iso image under
/repo/scripts/p4 and reached by an iso "call" job (target "pack_probe_call:probe_call"; isolation.ISO_SCRIPT_DIRS). It runs in the
CHILD DRIVER of one slot: it fits the adversarial `pack_probe` method (from the job's method snapshot) in a model worker of this slot,
runs one encode, and returns the worker's channel report. Nothing a worker produced is unpickled: the report crosses the safe codec as
a plain dict through info()."""

from __future__ import annotations

import os
import time

import numpy as np

from brainir_causal import isolation as I


def probe_call(job, *, transport, models=None):
    """The worker runs with the TRIPWIRE OFF so the probe reaches the OS boundary (as scripts/p4/smoke_isolation_modal.py's OS-only
    adversary): the point of the packed test is that even a method that defeats the in-process tripwire (F-B2) is still isolated from
    the other slots and the driver by the OS (uid, group, 0710 job dir, per-worker user / net / ipc namespaces)."""
    t0 = time.time()
    blob = I.fit_records(transport, method="pack_probe", records=[], systems={"toy": {}}, config={})["model"]
    w = I.WorkerClient(transport, "A", method_dir=getattr(transport, "method_dir_in_worker", None), threads=1, tripwire=False)
    try:
        w.request("load_model", blob=blob)
        report = (w.request("call", name="info", args=[], kwargs={}) or {}).get("report")
    finally:
        w.close()
    out = {"slot_driver_uid": os.getuid(), "worker_report": report, "wall_s": round(time.time() - t0, 2)}
    # Modal's >2 MiB data path (inputs and outputs travel through its blob store): the job's input pad arrived intact, and a large
    # output goes back (a block_network container could do neither)
    pad = job.get("pad")
    if isinstance(pad, (bytes, bytearray)):
        import hashlib
        out["pad_len"], out["pad_sha"] = len(pad), hashlib.sha256(pad).hexdigest()
    if job.get("big_out"):
        out["big_out"] = bytes(int(job["big_out"]))
    return out
