"""Orchestrator side of the Phase 4 Modal backend (goal5 sections 62-65, 97). Never imported inside a method room.

    from brainir_causal.p4modal.app import Backend
    with Backend() as be:                                   # an ephemeral app for the duration of the block
        res = be.simulate(items)                            # host-gated real-engine batches, content-addressed volume store
        out = be.call("pkg.mod:function", [[arg1], [arg2]])  # orchestrator functions in fresh subprocesses
        out = be.run_methods(payloads, cls="fit_s")         # guarded method jobs (fit / eval mode), optional per-job simulator
    svc = SimServer(..., remote_backend=be.remote_backend())  # full-network simulations of the local simulation service on Modal

Worker classes (`CLASSES`): each is one Modal function with fixed resources, mounted volumes and host-gate setting; payloads carry
their job kind (`remote.dispatch`). The workspace runs at most about 100 containers at once (measured in Phase 3), so the default
`max_containers` per class is 100 and heavy simulation classes use large containers with a process pool inside.

Isolation (the Phase 3 design, Phase 4 names): the fit volume (`brainir-p4-fit`: fit views, method snapshots) and the store volume
(`brainir-p4-store`: PUBLIC / development trajectory records) are the only volumes fit classes mount; held-out and hidden data live on
the eval volume (`brainir-p4-eval`), which only eval / sim_eval / util classes mount. Every method subprocess installs the guard
(brainir_causal.runguard) before any method code runs. No brainir-p3-* volume is ever mounted.

Reproducibility: CPU classes are host-gated (no AVX-512; the development machine's kernels; gate.py) unless a payload asks otherwise;
refused inputs are re-submitted until they land on an admissible host. GPU classes are not gated (their results are compared with CPU
runs by brainir_causal.equiv).
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import itertools
import json
import pickle
import tarfile
import threading
import time
import uuid
from pathlib import Path

from . import images

APP_NAME = "brainir-p4"
VOLUMES = {"fit": "brainir-p4-fit", "eval": "brainir-p4-eval", "store": "brainir-p4-store"}
MOUNT = {"fit": "/fitvol", "eval": "/evalvol", "store": "/storevol"}
MAX_CONTAINERS = 100

# Modal list prices (modal.com/pricing, read 2026-09-26; standard, preemptible), USD per second; for approximate job records only
CORE_S, GIB_S = 0.0000131, 0.00000222
GPU_S = {"B300": 0.001972, "B200": 0.001736, "H200": 0.001261, "H100": 0.001097, "RTX-PRO-6000": 0.000842, "A100-80GB": 0.000694,
         "A100-40GB": 0.000583, "L40S": 0.000542, "A10": 0.000306, "L4": 0.000222, "T4": 0.000164}

CLASSES = {
    # name: cpu = physical cores, memory in MiB, gpu, volumes, host gate, timeout (s)
    "sim":      {"cpu": 8.0, "memory": 32768, "gpu": None, "volumes": ("store",), "gated": True, "timeout": 3 * 3600},
    "sim_eval": {"cpu": 8.0, "memory": 32768, "gpu": None, "volumes": ("eval",), "gated": True, "timeout": 3 * 3600},
    "fit_s":    {"cpu": 4.0, "memory": 16384, "gpu": None, "volumes": ("fit", "store"), "gated": True, "timeout": 4 * 3600},
    "fit_m":    {"cpu": 8.0, "memory": 32768, "gpu": None, "volumes": ("fit", "store"), "gated": True, "timeout": 6 * 3600},
    "fit_l":    {"cpu": 16.0, "memory": 65536, "gpu": None, "volumes": ("fit", "store"), "gated": True, "timeout": 8 * 3600},
    "fit_xl":   {"cpu": 32.0, "memory": 131072, "gpu": None, "volumes": ("fit", "store"), "gated": True, "timeout": 8 * 3600},
    "eval_s":   {"cpu": 4.0, "memory": 32768, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 4 * 3600},
    "eval_l":   {"cpu": 8.0, "memory": 65536, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 6 * 3600},
    # large TRUSTED classes (reference learners, calibration, active-design MDE; research/phase4/LEVEL_B_EXECUTION.md): several jobs
    # per container through `Backend.call_packed` (one subprocess per job, longest first)
    "eval_xl":  {"cpu": 32.0, "memory": 131072, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 8 * 3600},
    "eval_xxl": {"cpu": 32.0, "memory": 262144, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 8 * 3600},
    # NON-PREEMPTIBLE variants (Modal `nonpreemptible=True`, higher price): for long in-container schedulers that cannot resume a
    # preempted container (E11's MDE packs, ~25 min each; its job subprocesses have no Modal client for a progress store)
    "eval_xl_np":  {"cpu": 32.0, "memory": 131072, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 8 * 3600, "nonpreemptible": True},
    "eval_xxl_np": {"cpu": 32.0, "memory": 262144, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 8 * 3600, "nonpreemptible": True},
    "util":     {"cpu": 2.0, "memory": 8192, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": False, "timeout": 2 * 3600},
    # dataset builds (suites.build_system_job): one system per container, a 16-core process pool, host-gated (bit-reproducible
    # simulation), every volume (public parts -> fit, held-out parts / truth / non-public records -> eval, public records -> store)
    "build":    {"cpu": 16.0, "memory": 65536, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 12 * 3600},
    # the slowest systems of a tier (by their previous build time) on 32 cores with a 32-process pool (build_on_modal.run_builds)
    "build_xl": {"cpu": 32.0, "memory": 131072, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 12 * 3600},
    # GPU classes (research/phase4/GPU_BENCHMARK.md): RTX-PRO-6000 and B200 were the fastest for latency-bound sequential rollouts,
    # H100 / H200 / B200 for large-batch throughput-bound training; L4 is the cheap small class
    "gpu_rtx6000": {"cpu": 8.0, "memory": 65536, "gpu": "RTX-PRO-6000", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600},
    "gpu_l4":   {"cpu": 4.0, "memory": 32768, "gpu": "L4", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600},
    "gpu_l40s": {"cpu": 4.0, "memory": 32768, "gpu": "L40S", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600},
    "gpu_a100": {"cpu": 8.0, "memory": 65536, "gpu": "A100-80GB", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600},
    "gpu_h100": {"cpu": 8.0, "memory": 65536, "gpu": "H100", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600},
    "gpu_h200": {"cpu": 8.0, "memory": 65536, "gpu": "H200", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600},
    "gpu_b200": {"cpu": 8.0, "memory": 65536, "gpu": "B200", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600},
    # ISOLATED classes (research/phase4/EVAL_ARCHITECTURE.md; kind "iso"): the container runs the trusted DRIVER as root and the method
    # code in unprivileged-uid MODEL WORKERS. block_network=True (the worker uid has no route, and no token is in its scrubbed env);
    # sensitive volumes are mounted READ-WRITE so the driver can chmod them 0700 (a read-only mount cannot be locked down).
    # The fit iso classes never mount the eval volume (loop classes do: the loop DRIVER needs the simulation context). The iso image
    # bakes the code with copy=True and locks /repo down.
    "iso_fit_s":  {"cpu": 4.0, "memory": 16384, "gpu": None, "volumes": ("fit", "store"), "gated": True, "timeout": 4 * 3600, "iso": True, "block_network": True},
    "iso_fit_m":  {"cpu": 8.0, "memory": 32768, "gpu": None, "volumes": ("fit", "store"), "gated": True, "timeout": 6 * 3600, "iso": True, "block_network": True},
    "iso_fit_l":  {"cpu": 16.0, "memory": 65536, "gpu": None, "volumes": ("fit", "store"), "gated": True, "timeout": 8 * 3600, "iso": True, "block_network": True},
    "iso_fit_xl": {"cpu": 32.0, "memory": 131072, "gpu": None, "volumes": ("fit", "store"), "gated": True, "timeout": 8 * 3600, "iso": True, "block_network": True},
    "iso_eval_s": {"cpu": 4.0, "memory": 32768, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 4 * 3600, "iso": True, "block_network": True},
    "iso_eval_l": {"cpu": 8.0, "memory": 65536, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 6 * 3600, "iso": True, "block_network": True},
    # loops: the DRIVER needs the system's simulation context (eval volume), as for evaluations; the loop worker cannot read it
    "iso_loop":   {"cpu": 8.0, "memory": 32768, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 8 * 3600, "iso": True, "block_network": True},
    "iso_gpu_rtx6000": {"cpu": 8.0, "memory": 65536, "gpu": "RTX-PRO-6000", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600, "iso": True, "block_network": True},
    "iso_gpu_b200": {"cpu": 8.0, "memory": 65536, "gpu": "B200", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600, "iso": True, "block_network": True},
    "iso_gpu_h100": {"cpu": 8.0, "memory": 65536, "gpu": "H100", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600, "iso": True, "block_network": True},
    "iso_gpu_h200": {"cpu": 8.0, "memory": 65536, "gpu": "H200", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600, "iso": True, "block_network": True},
    "iso_gpu_l40s": {"cpu": 8.0, "memory": 65536, "gpu": "L40S", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600, "iso": True, "block_network": True},
    # PACKED classes (research/phase4/LEVEL_B_EXECUTION.md). "slots" = Modal input concurrency: a container runs up to `slots` inputs at
    # once, each ONE job in its own slot (iso: a child driver with the slot's own uid block, group and per-worker user / network / IPC
    # namespaces, isolation.run_iso_packed; trusted "call": its own subprocess), and pulls the next queued input as soon as a slot is
    # free, so a queue submitted longest-first (`Backend.run_packed`) is a longest-processing-time list schedule over every slot.
    # Numerics are those of the unpacked classes (same image, same host gate, the job's own thread count).
    # NETWORK: every iso class stays block_network (the proven boundary: the container has only lo, so the model workers have no network;
    # on gVisor `unshare --net` does NOT give a clean namespace -- eth0 persists -- so dropping block_network would give the worker the
    # network, P1 2026-09-27). Modal cannot move an INPUT or OUTPUT above 2 MiB (MAX_OBJECT_SIZE_BYTES) through its blob store on a
    # block_network container, so large data (a model, a large evaluation record, a loop's checkpoint files) is STAGED through a mounted
    # VOLUME instead, which works under block_network (P1 volume probe): isolation.run_iso_payload writes it and returns a ref.
    "iso_pack_fit":  {"cpu": 32.0, "memory": 131072, "gpu": None, "volumes": ("fit", "store"), "gated": True, "timeout": 8 * 3600, "iso": True, "block_network": True, "slots": 8},
    "iso_pack_eval": {"cpu": 32.0, "memory": 262144, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 8 * 3600, "iso": True, "block_network": True, "slots": 8},
    "iso_pack_loop": {"cpu": 32.0, "memory": 131072, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 8 * 3600, "iso": True, "block_network": True, "slots": 8},
    "iso_pack_gpu_rtx6000": {"cpu": 16.0, "memory": 131072, "gpu": "RTX-PRO-6000", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600, "iso": True, "block_network": True, "slots": 4},
    "iso_pack_gpu_b200": {"cpu": 16.0, "memory": 131072, "gpu": "B200", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600, "iso": True, "block_network": True, "slots": 4},
    "iso_pack_gpu_h100": {"cpu": 16.0, "memory": 131072, "gpu": "H100", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600, "iso": True, "block_network": True, "slots": 4},
    "iso_pack_gpu_h200": {"cpu": 16.0, "memory": 131072, "gpu": "H200", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600, "iso": True, "block_network": True, "slots": 4},
    "pack_xl":  {"cpu": 32.0, "memory": 131072, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 8 * 3600, "slots": 8},
    "pack_xxl": {"cpu": 32.0, "memory": 262144, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 8 * 3600, "slots": 8},
}
MAX_REFUSALS = 400            # per input; a refusal costs a few seconds of a warm container
MAX_STALE = 8                 # per input: warm packed containers that could not see a staged input (isolation.stale_refusal) before a fresh one
MAX_CALL_FAILS = 4            # per input: calls that raised on Modal (after Modal's own retries) before the input is given up
#: the container-start NUMERICS SELF-TEST (p4modal.selftest; LEVEL_B_EXECUTION.md section 9) refuses a host that passes the flag rule but
#: does not compute the reference bit for bit. Such refusals are bounded apart from the flag gate's: an input refused by the self-test on
#: MAX_SELFTEST_REFUSALS containers, or every waiting input of a class once SELFTEST_BREAKER self-test refusals came with NO container of
#: the class passing it (a systematic fault: a reference from another stack, a changed image), is given up as an INFRASTRUCTURE failure
#: (never charged to a method; the round is incomplete)
MAX_SELFTEST_REFUSALS = 8
SELFTEST_BREAKER = 24
#: refused inputs are collected for RESUBMIT_BATCH_S and re-submitted together as one SYNCHRONOUS map (at most RESUBMIT_MAPS such maps in
#: flight per `Backend.run`). Never `spawn`: an async invocation returns at most 8 KiB inline (modal MAX_ASYNC_OBJECT_SIZE_BYTES) and moves
#: larger outputs through Modal's blob store, which a block_network (iso) container cannot reach (P2's finding; P1's full dry run lost its
#: re-submitted fits to it). Never one call per input either: 64 concurrent `Function.remote` calls in a refusal storm (344 refusals in 8
#: minutes) came with the host's socket-buffer exhaustion (WinError 10055, P1's dev dry run).
RESUBMIT_BATCH_S = 15.0
RESUBMIT_MAPS = 8
#: every function's scale-down window, set EXPLICITLY (Modal's default) so that the cost records know a container's idle tail: a container
#: that ran its last input stays up (and is billed) this long before it exits
SCALEDOWN_S = 60
#: Modal moves any function input or output above this through its blob store over HTTPS from inside the container (blob_utils
#: .MAX_OBJECT_SIZE_BYTES). A block_network container cannot, so a block_network iso class (iso_fit_s / iso_eval_* / iso_loop / iso_gpu_*)
#: is limited to inputs and outputs below it; the packed iso classes are not block_network (the worker's own empty net namespace is the
#: boundary instead) and have no such limit. A margin leaves room for the tags / host record the callable adds.
MAX_INLINE = 2 * 1024 * 1024
INLINE_MARGIN = 64 * 1024


def usd_per_s(cls: str) -> float:
    c = CLASSES[cls]
    np_factor = 3.0 if c.get("nonpreemptible") else 1.0          # Modal bills non-preemptible CPU and memory at 3x the list rate
    return (c["cpu"] * CORE_S + c["memory"] / 1024 * GIB_S) * np_factor + (GPU_S[c["gpu"]] if c["gpu"] else 0.0)


def packed_span_s(recs: list[dict], slots: int) -> tuple[float, int]:
    """(container seconds, containers) of a PACKED wave: per container (`__task`), the length of the union of its inputs' spans (`__span`,
    the container's clock). A result without a span (an older container) counts its wall divided by the slots (the full-container lower
    bound)."""
    by: dict = {}
    loose = 0.0
    for r in recs:
        sp, task = r.get("__span"), r.get("__task")
        if task and isinstance(sp, (list, tuple)) and len(sp) == 2:
            by.setdefault(task, []).append((float(sp[0]), float(sp[1])))
        else:
            loose += float(r.get("container_wall_s") or 0.0) / max(1, int(slots))
    total = 0.0
    for spans in by.values():
        spans.sort()
        cur0, cur1 = spans[0]
        for a, b in spans[1:]:
            if a > cur1:
                total += cur1 - cur0
                cur0, cur1 = a, b
            else:
                cur1 = max(cur1, b)
        total += cur1 - cur0
    return total + loose, len(by)


def _by_task(recs: list[dict]) -> dict:
    by: dict = {}
    for r in recs:
        sp, task = r.get("__span"), r.get("__task")
        if task and isinstance(sp, (list, tuple)) and len(sp) == 2:
            by.setdefault(task, []).append(r)
    return by


def occupancy_shares(recs: list[dict], slots: int) -> list[float]:
    """Each result's share of its container's busy time: the container's timeline is cut at every span start / end, and each slice is
    divided equally among the inputs running in it (so the shares of a container add up to the union of its spans). A result without a
    span gets its wall divided by `slots`."""
    out = [float(r.get("container_wall_s") or 0.0) / max(1, int(slots)) for r in recs]
    idx: dict = {}
    for k, r in enumerate(recs):
        sp, task = r.get("__span"), r.get("__task")
        if task and isinstance(sp, (list, tuple)) and len(sp) == 2:
            idx.setdefault(task, []).append(k)
            out[k] = 0.0
    for ks in idx.values():
        cuts = sorted({float(recs[k]["__span"][j]) for k in ks for j in (0, 1)})
        for a, b in itertools.pairwise(cuts):
            live = [k for k in ks if float(recs[k]["__span"][0]) <= a and float(recs[k]["__span"][1]) >= b]
            for k in live:
                out[k] += (b - a) / len(live)
    return out


def _container_callable(gated: bool, slots: int = 0, block_network: bool = False):
    """The function Modal runs, created as a closure so that it is serialised BY VALUE (a module-level function would be pickled by
    reference to a module the container may not have). Tags travel through so results can be matched in unordered maps. slots > 0: a
    PACKED class (the payload tells the container side how many slots the container has). block_network: a block_network container (Modal
    cannot move an input or output above 2 MiB through its blob store here, so the container side caps oversized iso outputs, MAX_INLINE)."""
    def p4_job(payload):
        import os
        import time
        t_in = time.time()

        def stamp(r: dict) -> dict:
            # the container and the input's span on its clock: a PACKED container runs several inputs at once, so its cost is the union
            # of its inputs' spans at the whole container's price, not the sum of their walls (Backend._cost); a REFUSED input's
            # container is billed too (its start-up and the refusal), so refusals carry the same record
            r["__task"] = os.environ.get("MODAL_TASK_ID")
            r["__span"] = [round(t_in, 3), round(time.time(), 3)]
            try:                                  # the container's start on the same clock (gVisor: /proc/uptime = the sandbox's uptime)
                with open("/proc/uptime") as fh:
                    r["__boot"] = round(time.time() - float(fh.read().split()[0]), 3)
            except (OSError, ValueError, IndexError):
                pass
            return r
        tag = payload.get("__tag")
        if slots:
            payload = dict(payload, __slots=int(slots))
        if block_network:
            payload = dict(payload, __block_network=True)
        from brainir_causal.p4modal import gate
        h = gate.host_cpu()
        if gated and not payload.get("ungated") and not gate.admissible(h):
            r = gate.refusal(h)
            r["__tag"] = tag
            return stamp(r)
        st = None
        if gated and not payload.get("ungated"):
            # the container-start NUMERICS SELF-TEST (once per container, cached): a host that passes the flag rule must also compute the
            # recorded reference bit for bit (p4modal.selftest; HOST_GATE_STUDY.md "Hardening"), else it is refused exactly as above
            st = gate.numerics_selftest()
            if st.get("stale"):
                # the reference was not built by this battery / library stack: a configuration fault, never a host verdict
                return stamp({"__infra__": True, "error": f"InfraFault (numerics reference): {st['stale']}"[:2000], "__tag": tag})
            if not st.get("ok"):
                r = gate.refusal(h)
                r.update({"__tag": tag, "selftest": {k: st.get(k) for k in ("mismatch", "errors", "host_class", "fingerprint", "s",
                                                                            "wall_s")}})
                return stamp(r)
        from brainir_causal.p4modal import remote
        try:
            r = remote.dispatch(payload)
        except Exception as e:  # noqa: BLE001 - a deterministic job error is a RESULT (Modal's retries are for infrastructure faults)
            import traceback
            r = {"error": f"{type(e).__name__}: {e}"[:2000], "traceback": traceback.format_exc()[-6000:]}
        except BaseException as e:
            # an INFRASTRUCTURE fault of the isolation layer (isolation.InfraFault: a model worker that died twice, a packed child
            # driver killed, ...): never the job's own result. Returned as such; the orchestrator re-submits the input, to another
            # container (this one stops taking inputs: its state, e.g. memory pressure from other slots, may be the cause)
            if not any(c.__name__ == "InfraFault" for c in type(e).__mro__):
                raise
            try:
                import modal.experimental as E
                E.stop_fetching_inputs()
            except Exception:  # noqa: BLE001, S110 - outside Modal, or an older client
                pass
            r = {"__infra__": True, "error": f"InfraFault ({type(e).__name__}): {e}"[:2000]}
        if isinstance(r, dict):
            r["__tag"] = tag
            r["__host__"] = h
            if st is not None:
                r["__selftest"] = {"ok": True, "s": st.get("s"), "wall_s": st.get("wall_s"), "cached": st.get("cached"),
                                   "absent": st.get("absent"), "host_class": st.get("host_class"),
                                   "reference_class": st.get("reference_class")}
            stamp(r)
        return r
    return p4_job


def volume(name: str, create: bool = True):
    """A Phase 4 volume (created as a VolumeFS v2 volume on first use: concurrent writers of distinct files, no size limit)."""
    import modal
    try:
        return modal.Volume.from_name(VOLUMES[name], create_if_missing=create, version=2)
    except Exception:  # noqa: BLE001 - an existing v1 volume
        return modal.Volume.from_name(VOLUMES[name], create_if_missing=create)


def make_app(classes: list[str] | None = None, max_containers: int = MAX_CONTAINERS, extra_dirs: dict[str, str] | None = None,
             app_name: str = APP_NAME):
    import modal
    app = modal.App(app_name)
    vols = {k: volume(k) for k in VOLUMES}
    retries = modal.Retries(max_retries=3, initial_delay=2.0, backoff_coefficient=1.0)
    imgs: dict = {}                       # (gpu, iso) -> image, built once
    fns = {}
    for name in classes or list(CLASSES):
        c = CLASSES[name]
        iso = bool(c.get("iso"))
        key = (bool(c["gpu"]), iso)
        if key not in imgs:
            imgs[key] = (images.iso_image(gpu=bool(c["gpu"]), extra_dirs=extra_dirs) if iso
                         else images.full_image(gpu=bool(c["gpu"]), extra_dirs=extra_dirs))
        kw = {"cpu": c["cpu"], "memory": c["memory"], "timeout": c["timeout"], "max_containers": max_containers, "retries": retries,
              "volumes": {MOUNT[v]: vols[v] for v in c["volumes"]}, "serialized": True, "name": f"p4_{name}", "image": imgs[key],
              "scaledown_window": SCALEDOWN_S}
        if c["gpu"]:
            kw["gpu"] = c["gpu"]
        if c.get("block_network"):
            kw["block_network"] = True
        if c.get("nonpreemptible"):
            kw["nonpreemptible"] = True
        call = _container_callable(c["gated"], int(c.get("slots") or 0), bool(c.get("block_network")))
        if c.get("slots"):
            call = modal.concurrent(max_inputs=int(c["slots"]))(call)
        fns[name] = app.function(**kw)(call)
    return app, fns, vols


class Backend:
    """Submits payloads to the worker classes, re-submits host-gate refusals, records approximate costs. Use as a context manager
    (an ephemeral app for the block), or `Backend.deployed()` for the functions of a deployed app (`modal_p4.py deploy`)."""

    def __init__(self, classes: list[str] | None = None, max_containers: int = MAX_CONTAINERS, extra_dirs: dict[str, str] | None = None,
                 app_name: str = APP_NAME, verbose: bool = True):
        self.classes = classes or list(CLASSES)
        self.app, self.fns, self.vols = make_app(self.classes, max_containers, extra_dirs, app_name)
        self.costs: list[dict] = []
        self.refusals: dict[str, int] = {}
        self.infra_faults: dict[str, int] = {}
        self.hosts: dict[str, int] = {}
        self.verbose = verbose
        self._ctx = None
        self.app_id = None

    @classmethod
    def deployed(cls, app_name: str = APP_NAME, classes: list[str] | None = None, verbose: bool = True) -> Backend:
        import modal
        self = cls.__new__(cls)
        self.classes = classes or list(CLASSES)
        self.app, self.vols = None, {k: volume(k) for k in VOLUMES}
        self.fns = {n: modal.Function.from_name(app_name, f"p4_{n}") for n in self.classes}
        self.costs, self.refusals, self.hosts, self.verbose, self._ctx, self.app_id = [], {}, {}, verbose, None, None
        return self

    def __enter__(self):
        import modal
        self._out = modal.enable_output() if self.verbose else None
        if self._out is not None:
            self._out.__enter__()
        self._ctx = self.app.run()
        run = self._ctx.__enter__()
        self.app_id = getattr(run, "app_id", None)
        return self

    def __exit__(self, *exc):
        try:
            self._ctx.__exit__(*exc)
        finally:
            if self._out is not None:
                self._out.__exit__(*exc)
        return False

    # ---------------------------------------------------------------- generic submission
    def run(self, payloads: list[dict], cls: str, label: str = "", on_result=None, poll_s: float = 5.0,
            batch_s: float | None = None) -> list:
        """Results in input order (an Exception for a failed call). All inputs go out as ONE map (results stream back as they complete).
        A REFUSED input (host gate, or a warm packed container that cannot see a staged input yet; the refusing container stops fetching
        inputs) is re-submitted within RESUBMIT_BATCH_S: refused inputs are collected into a batch that goes out as its own SYNCHRONOUS
        map in a client thread (at most RESUBMIT_MAPS at once), so it starts on other containers while the first map's other jobs run;
        it never waits for the first map's slowest job (the earlier waves did: up to 25 min, E11 / P3). Never `spawn` (its output is
        limited to 8 KiB inline, larger outputs go through the blob store, which a block_network container cannot reach) and never one
        call per input (client load). A call that raised on Modal (after Modal's own retries) is re-submitted too, at most
        MAX_CALL_FAILS times. The payloads (incl. a packed wave's generation stamp) are re-sent unchanged, so a re-submission never
        changes what a job computes. on_result(i, result) is called once per input, with its FINAL result (a job's own failure is a
        result; only infrastructure failures are re-submitted), possibly from a client thread (calls are serialised by a lock)."""
        fn = self.fns[cls]
        n = len(payloads)
        batch_s = RESUBMIT_BATCH_S if batch_s is None else float(batch_s)
        out: list = [None] * n
        done = [False] * n
        attempts, stale, fails, st_refused = [0] * n, [0] * n, [0] * n, [0] * n
        stc = self.__dict__.setdefault("selftest_counts", {}).setdefault(cls, {"passed": 0, "refused": 0})
        queued: list = []                      # refused / failed inputs waiting for the next re-submission map
        maps: list = []                        # threads of the re-submission maps in flight
        lock = threading.RLock()
        cond = threading.Condition(lock)
        recs: list = []
        refused: list = []                     # the refusals' container records (their containers are billed too)
        t0 = time.time()
        last = [t0]

        def finish(i: int, r) -> None:         # under the lock
            if done[i]:
                return
            out[i], done[i] = r, True
            if isinstance(r, dict):
                recs.append(r)
                host = (r.get("__host__") or {}).get("model")
                if host:
                    self.hosts[host] = self.hosts.get(host, 0) + 1
            if on_result is not None:
                on_result(i, r)
            cond.notify_all()

        def failed(i: int, e) -> None:         # under the lock: the call raised on Modal (infrastructure)
            fails[i] += 1
            if fails[i] >= MAX_CALL_FAILS:
                finish(i, RuntimeError(f"call failed repeatedly on Modal (infrastructure): {e!r}"[:800]))
            else:
                queued.append(i)

        def handle(i: int, r) -> None:         # under the lock: a result of input i
            if done[i]:
                return                         # a late result of an input already given up (the self-test breaker)
            if isinstance(r, dict) and isinstance(r.get("__selftest"), dict) and r["__selftest"].get("cached") is False:
                stc["passed"] += 1             # a fresh container passed the numerics self-test
            if isinstance(r, dict) and r.get("__infra__"):
                # an infrastructure fault inside the job (isolation.InfraFault): re-submitted like a failed call, never a result
                faults = self.__dict__.setdefault("infra_faults", {})
                faults[cls] = faults.get(cls, 0) + 1
                refused.append({k: r.get(k) for k in ("__task", "__span", "__boot")})
                failed(i, str(r.get("error") or "InfraFault"))
                return
            if isinstance(r, dict) and r.get("__refused__"):
                self.refusals[cls] = self.refusals.get(cls, 0) + 1
                refused.append({k: r.get(k) for k in ("__task", "__span", "__boot")})
                if r.get("selftest"):               # refused by the numerics self-test (the flag rule passed): recorded with the host
                    rec_st = self.__dict__.setdefault("selftest_refusals", [])
                    if len(rec_st) < 200:
                        rec_st.append({"cls": cls, "host": r.get("host"), **(r.get("selftest") or {})})
                    st_refused[i] += 1
                    stc["refused"] += 1
                    breaker = stc["refused"] >= SELFTEST_BREAKER and not stc["passed"]
                    if breaker or st_refused[i] >= MAX_SELFTEST_REFUSALS:
                        st = r.get("selftest") or {}
                        why = (f"{stc['refused']} containers of {cls} refused by it and none passed (systematic: rebuild the reference or "
                               "review the gate)" if breaker else f"input refused by it on {st_refused[i]} containers")
                        err = RuntimeError(f"InfraFault (numerics self-test): {why}; last host {st.get('host_class')!r}, "
                                           f"mismatching items {st.get('mismatch')}, errors {st.get('errors')}"[:1500])
                        for k in (range(n) if breaker else (i,)):
                            if not done[k]:
                                finish(k, err)
                        if breaker:
                            queued.clear()
                        return
                stale[i] += 1 if r.get("stale_staging") else 0
                if attempts[i] >= MAX_REFUSALS:
                    finish(i, RuntimeError(f"no admissible host after {attempts[i]} attempts"))
                elif stale[i] > MAX_STALE:
                    finish(i, RuntimeError(f"staged input {r.get('stale_staging')} not visible after {stale[i]} fresh containers "
                                           f"(was it staged before submission, and not cleared?)"))
                else:
                    queued.append(i)
                return
            finish(i, r)

        def one_map(idx: list, main: bool = False) -> None:
            """One synchronous map over the inputs idx (the first wave, or a re-submission batch)."""
            with lock:
                for i in idx:
                    attempts[i] += 1
            batch = [dict(payloads[i], __tag=i, job_id=uuid.uuid4().hex) for i in idx]
            seen: set = set()
            err: object = "the call raised on Modal"
            try:
                for r in fn.map(batch, order_outputs=False, return_exceptions=True):
                    if isinstance(r, BaseException):
                        # which input failed is unknown here (the exception carries no tag): found after the map, re-submitted then
                        with lock:
                            recs.append({"error": repr(r)[:500]})
                        continue
                    i = int(r.get("__tag"))
                    with lock:
                        seen.add(i)
                        handle(i, r)
            except Exception as e:  # a client-side failure of the map
                if main:
                    raise
                err = e
                import traceback
                print(f"  p4modal {label or cls}: a re-submission map of {len(idx)} inputs failed on the client: {e!r}\n"
                      f"{traceback.format_exc()[-1500:]}", flush=True)
            finally:
                with lock:
                    for i in idx:
                        if i not in seen and not done[i]:
                            failed(i, err)
                    cond.notify_all()

        stop = threading.Event()

        def dispatcher() -> None:
            while not stop.wait(batch_s):
                if self.verbose and time.time() - last[0] > 120:   # progress even while nothing finishes (e.g. a refusal storm)
                    last[0] = time.time()
                    with lock:
                        n_done, n_q, n_maps = sum(done), len(queued), sum(th.is_alive() for th in maps)
                    print(f"  p4modal {label or cls}: {n_done}/{n} done, {n_q} queued and {n_maps} re-submission maps in flight, "
                          f"refusals {self.refusals.get(cls, 0)}, infrastructure faults {getattr(self, 'infra_faults', {}).get(cls, 0)} "
                          f"({time.time() - t0:.0f} s)", flush=True)
                with lock:
                    maps[:] = [th for th in maps if th.is_alive()]
                    if not queued or len(maps) >= RESUBMIT_MAPS:
                        continue
                    idx = sorted(set(queued))
                    queued.clear()
                    th = threading.Thread(target=one_map, args=(idx,), name=f"p4modal-retry-{cls}", daemon=True)
                    maps.append(th)
                th.start()

        disp = threading.Thread(target=dispatcher, name=f"p4modal-dispatch-{cls}", daemon=True)
        disp.start()
        try:
            if n:
                one_map(list(range(n)), main=True)
            with lock:
                while not all(done):
                    cond.wait(timeout=poll_s)
        finally:
            stop.set()
            disp.join(timeout=60)
        self._cost(recs, cls, label, refused=refused)
        if self.verbose:
            print(f"  p4modal {label or cls}: {n} jobs in {time.time() - t0:.0f} s (refusals {self.refusals.get(cls, 0)})", flush=True)
        return out

    def run_eager(self, payloads: list[dict], cls: str, label: str = "", poll_s: float = 2.0) -> list:
        """The earlier eager path (few long jobs, refusals re-submitted at once) is `run` itself now; kept for callers. It used `spawn`,
        whose async output limit (8 KiB inline) failed every larger result on a block_network class."""
        return self.run(payloads, cls, label, poll_s=poll_s)

    def _cost(self, recs: list, cls: str, label: str, refused: list | None = None) -> None:
        """Approximate cost of a wave from CONTAINER time (never the inputs' walls at a whole container's price): per container (the
        `__task` each result carries), the union of its inputs' spans (busy time; a packed container runs up to `slots` inputs at once), plus,
        the first time this Backend sees the container, its start-up before its first input (from `__boot`) and its idle tail
        (SCALEDOWN_S, the scale-down window every function has). REFUSED inputs (`refused`: their container records) are billed too: a
        container that only refused (host gate; it stops fetching inputs and exits) costs its start-up and its refusals' spans, no idle
        tail; a refusal in a container that also ran jobs adds its span to that container's busy time. Each result gets its OCCUPANCY
        share of its container's busy time (`__share_s`: a time slice shared by k inputs counts 1/k for each), so per-job costs add up to
        the container's (refusals are the wave's overhead, recorded separately). A result without a span (an older container) counts its
        wall divided by the class's slots. Reconciled against the workspace billing report in research/phase4/LEVEL_B_EXECUTION.md."""
        recs = [r for r in recs if isinstance(r, dict)]
        refused = [r for r in (refused or []) if isinstance(r, dict) and r.get("__task") and isinstance(r.get("__span"), (list, tuple))]
        walls = sum(float(r.get("container_wall_s") or 0.0) for r in recs)
        slots = int(CLASSES[cls].get("slots") or 1)
        job_tasks = set(_by_task(recs))
        busy, n_cont = packed_span_s(recs + [r for r in refused if r["__task"] in job_tasks], slots)
        seen = self.__dict__.setdefault("_tasks_seen", set())
        startup = idle = 0.0
        for task, rs in _by_task(recs + refused).items():
            if task in seen:
                continue
            seen.add(task)
            first = min(float(r["__span"][0]) for r in rs)
            boots = [float(r["__boot"]) for r in rs if isinstance(r.get("__boot"), (int, float))]
            if boots:
                startup += max(0.0, first - min(boots))
            if task in job_tasks:
                idle += SCALEDOWN_S
        only_refused = [r for r in refused if r["__task"] not in job_tasks]
        refused_s, n_refused_cont = packed_span_s(only_refused, slots)
        for r, share in zip(recs, occupancy_shares(recs, slots)):
            r["__share_s"] = round(share, 2)
        s = busy + refused_s + startup + idle
        peaks = [float(r["peak_container_mb"]) for r in recs if r.get("peak_container_mb") is not None]
        self.costs.append({"label": label or cls, "class": cls, "calls": len(recs), "container_s": round(s, 1), "busy_s": round(busy, 1),
                           "startup_s": round(startup, 1), "idle_tail_s": round(idle, 1), "refusals": len(refused),
                           "refused_only_containers": n_refused_cont, "refused_only_s": round(refused_s, 1),
                           "input_wall_s": round(walls, 1), "containers": n_cont,
                           "peak_container_mb_max": max(peaks) if peaks else None, "usd_approx": round(s * usd_per_s(cls), 4)})

    # ---------------------------------------------------------------- simulation
    def simulate(self, items: list[dict], *, mode: str = "full", store: str | None = "store", batch: int = 8, cls: str | None = None,
                 workers: int | None = None, label: str = "sim", store_sub: str = "store") -> list:
        """items: [{"sysdef": INTERNAL real record, "protocol": dict, "restart_src": {store key: record bytes}?, "meta": {}?}].
        mode 'full' returns each record's bytes (brainir_causal.p4modal.remote.record_from_bytes), 'observed' the observed arrays
        (t, x, u, y) only, 'digest' only keys and array hashes. store: 'store' (public / development records), 'eval' (hidden records:
        class sim_eval) or None (no volume store). Results in item order; each has key, computed, sha (per array) and sim_wall_s."""
        cls = cls or ("sim_eval" if store == "eval" else "sim")
        w = workers or int(CLASSES[cls]["cpu"])
        payloads = [{"kind": "sim", "items": items[i: i + batch], "store": store, "store_sub": store_sub, "mode": mode, "workers": w,
                     "threads": 1} for i in range(0, len(items), batch)]
        res = self.run(payloads, cls, label)
        out = []
        for p, r in zip(payloads, res, strict=True):
            if isinstance(r, BaseException) or not isinstance(r, dict) or "results" not in r:
                err = r if isinstance(r, BaseException) else RuntimeError(f"simulation batch failed: {str(r)[:500]}")
                out += [err] * len(p["items"])
            else:
                out += [RuntimeError(x["error"]) if "error" in x else x for x in r["results"]]
        return out

    def remote_backend(self, *, batch: int = 4, cls: str = "sim"):
        """The `remote_backend` of brainir_causal.simservice.SimServer: jobs -> [finish_remote_job(job, record) | Exception]. The
        record is computed on a gated host (or served from the volume store), checked against the locally computed store key, stored
        in the local store, and its observed arrays are returned."""
        from brainir_causal.simservice import finish_remote_job, real_store_key
        from brainir_causal.store import TrajectoryStore

        from .remote import record_from_bytes

        def backend(jobs: list[dict]) -> list:
            items = []
            for job in jobs:
                q = job["protocol"]
                src = None
                if q.get("r0", {}).get("kind") == "restart":
                    p = TrajectoryStore(job["store_root"]).path(q["r0"]["key"])
                    if p.exists():
                        src = {q["r0"]["key"]: p.read_bytes()}
                items.append({"sysdef": job["sysdef"], "protocol": q, "restart_src": src, "meta": {"source": "simservice-remote"},
                              "fresh": bool(job.get("fresh"))})              # CACHE ISOLATION (brainir_causal.simservice)
            res = self.simulate(items, mode="full", store="store", batch=batch, cls=cls, workers=min(batch, int(CLASSES[cls]["cpu"])),
                                label="simservice")
            out = []
            for job, r in zip(jobs, res, strict=True):
                if isinstance(r, BaseException):
                    out.append(r)
                    continue
                if r["key"] != real_store_key(job):
                    out.append(RuntimeError(f"remote key {r['key'][:12]} != local key {real_store_key(job)[:12]}"))
                    continue
                out.append(finish_remote_job(job, record_from_bytes(r["record"])))
            return out
        return backend

    def fetch(self, keys: list[str], volume_name: str = "store") -> dict:
        """Record bytes of store keys from a store volume (None when absent)."""
        res = self.run([{"kind": "fetch", "keys": keys[i: i + 16], "volume": volume_name} for i in range(0, len(keys), 16)], "util", "fetch")
        out = {}
        for r in res:
            if isinstance(r, dict):
                out.update(r.get("records") or {})
        return out

    # ---------------------------------------------------------------- orchestrator calls and method jobs
    def call(self, target: str, arg_lists: list[list], cls: str = "util", timeout_s: float = 7200, threads: int = 2, eager: bool = False,
             **extra) -> list:
        """Orchestrator functions in fresh subprocesses; eager=True re-submits refused inputs at once (`run_eager`: few long jobs)."""
        payloads = [dict({"kind": "call", "target": target, "args": list(a), "timeout_s": timeout_s, "threads": threads}, **extra)
                    for a in arg_lists]
        return (self.run_eager if eager else self.run)(payloads, cls, f"call:{target}")

    def run_methods(self, payloads: list[dict], cls: str = "fit_s", label: str = "methods") -> list:
        """Guarded method jobs (remote.run_method payloads; `kind` is set here)."""
        return self.run([dict(p, kind="method") for p in payloads], cls, label)

    def run_iso(self, payloads: list[dict], cls: str, label: str = "iso") -> list:
        """ISOLATED jobs (research/phase4/EVAL_ARCHITECTURE.md; remote.run_iso): method code in unprivileged-uid model workers under a
        root driver, on a block_network=True container. Each payload is {"role": "fit"|"eval"|"loop"|"describe", "job": {...},
        "methods_key"|"method_tar", ["model"], ...}; `kind` is set here. The class must be an iso class."""
        if not CLASSES.get(cls, {}).get("iso"):
            raise ValueError(f"{cls!r} is not an isolated class")
        _check_inline(payloads, cls)
        return self.run([dict(p, kind="iso") for p in payloads], cls, label)

    # ---------------------------------------------------------------- packed classes (research/phase4/LEVEL_B_EXECUTION.md)
    def run_packed(self, payloads: list[dict], cls: str, *, expected_s: list[float] | None = None, keys: list[str] | None = None,
                   done_dir: Path | str | None = None, label: str = "", on_result=None) -> list:
        """Jobs on a PACKED class (CLASSES[cls]["slots"] > 0), results in input order. The queue is submitted LONGEST EXPECTED FIRST
        (`expected_s`, ties in input order): every container pulls the next input as a slot frees up, so this is a longest-processing-time
        list schedule over all slots. keys + done_dir make the call IDEMPOTENT: a job whose result file <done_dir>/<key>.pkl exists is
        not submitted again (its stored result is returned), and every result is stored as soon as it arrives, so an interrupted round
        resumes without recomputation. Infrastructure failures (Exceptions) are never stored."""
        if not CLASSES.get(cls, {}).get("slots"):
            raise ValueError(f"{cls!r} is not a packed class")
        n = len(payloads)
        if keys is not None and (len(keys) != n or len(set(keys)) != n):
            raise ValueError("keys must be unique, one per payload")
        out: list = [None] * n
        dd = Path(done_dir) if done_dir is not None else None
        todo = list(range(n))
        if dd is not None and keys is not None:
            dd.mkdir(parents=True, exist_ok=True)
            todo = []
            for i in range(n):
                f = dd / f"{_key_file(keys[i])}.pkl"
                if f.exists():
                    with open(f, "rb") as fh:
                        out[i] = pickle.load(fh)
                else:
                    todo.append(i)
            if self.verbose and n - len(todo):
                print(f"  p4modal {label or cls}: {n - len(todo)} of {n} jobs already done (resumed)", flush=True)
        exp = [float(x or 0.0) for x in expected_s] if expected_s is not None else [0.0] * n
        order = sorted(todo, key=lambda i: (-exp[i], i))
        # the wave's GENERATION: a warm packed container that sees a newer one drains, reloads its volumes once and locks down again
        # (isolation.pack_ready / remote.run_call), so data uploaded or staged after its first reload (e.g. checkpoint models) is visible
        self._gen = max(int(getattr(self, "_gen", 0)) + 1, int(time.time() * 1000))
        payloads = [dict(p, __gen=self._gen) for p in payloads]

        def got(j: int, r) -> None:
            i = order[j]
            if dd is not None and keys is not None and not isinstance(r, BaseException):
                f = dd / f"{_key_file(keys[i])}.pkl"
                tmp = f.with_suffix(f".{uuid.uuid4().hex}.part")
                with open(tmp, "wb") as fh:
                    pickle.dump(r, fh, protocol=pickle.HIGHEST_PROTOCOL)
                tmp.replace(f)
            if on_result is not None:
                on_result(i, r)
        if order:
            res = self.run([payloads[i] for i in order], cls, label or f"packed:{cls}", on_result=got)
            for j, i in enumerate(order):
                out[i] = res[j]
        return out

    def run_iso_packed(self, payloads: list[dict], cls: str, *, expected_s: list[float] | None = None, keys: list[str] | None = None,
                       done_dir: Path | str | None = None, label: str = "iso-packed", on_result=None) -> list:
        """ISOLATED jobs (payloads as for `run_iso`: role fit / eval / loop / describe / call) on a packed iso class; see `run_packed`."""
        if not (CLASSES.get(cls, {}).get("iso") and CLASSES[cls].get("slots")):
            raise ValueError(f"{cls!r} is not a packed isolated class")
        _check_inline(payloads, cls)
        return self.run_packed([dict(p, kind="iso") for p in payloads], cls, expected_s=expected_s, keys=keys, done_dir=done_dir,
                               label=label, on_result=on_result)

    def call_packed(self, target: str, arg_lists: list[list], cls: str = "pack_xl", *, expected_s: list[float] | None = None,
                    keys: list[str] | None = None, done_dir: Path | str | None = None, timeout_s: float = 7200, threads: int = 2,
                    label: str | None = None, on_result=None, **extra) -> list:
        """TRUSTED orchestrator functions (as `call`: each in a fresh subprocess) on a packed class; see `run_packed`."""
        if CLASSES.get(cls, {}).get("iso"):
            raise ValueError(f"{cls!r} is an isolated class; trusted calls go to a packed trusted class")
        payloads = [dict({"kind": "call", "target": target, "args": list(a), "timeout_s": timeout_s, "threads": threads}, **extra)
                    for a in arg_lists]
        return self.run_packed(payloads, cls, expected_s=expected_s, keys=keys, done_dir=done_dir, label=label or f"call:{target}",
                               on_result=on_result)

    # ---------------------------------------------------------------- uploads
    # ---------------------------------------------------------------- large-artefact staging on the STORE volume (block_network > 2 MiB)
    def stage_put(self, data: bytes, vol: str = "store") -> dict:
        """Upload a large blob to a volume's staging area (content-addressed, /_staged/<sha[:2]>/<sha>.bin, as `isolation.stage_blob`)
        and return its ref {"stage": sha, "size": n, "vol": vol}. A large EVAL input model (public-data-derived) goes to the STORE volume;
        the eval payload then carries the ref instead of the bytes (a block_network container cannot receive > 2 MiB inline)."""
        if vol not in ("store", "eval"):
            raise ValueError(f"no staging area on volume {vol!r}")
        sha = hashlib.sha256(data).hexdigest()
        v = self.vols[vol]
        try:
            present = any(Path(e.path).name == f"{sha}.bin" for e in v.listdir(f"_staged/{sha[:2]}"))
        except Exception:  # noqa: BLE001
            present = False
        if not present:
            with v.batch_upload(force=True) as b:
                b.put_file(io.BytesIO(data), f"/_staged/{sha[:2]}/{sha}.bin")
        return {"stage": sha, "size": len(data), "vol": vol}

    def stage_get(self, ref: dict) -> bytes:
        """The bytes a staged ref names, read from its volume and verified against its sha256."""
        sha = str(ref["stage"])
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError(f"malformed staged ref {sha!r}")
        v = self.vols[ref.get("vol", "store")]
        buf = io.BytesIO()
        for chunk in v.read_file(f"_staged/{sha[:2]}/{sha}.bin"):
            buf.write(chunk)
        data = buf.getvalue()
        if hashlib.sha256(data).hexdigest() != sha:
            raise RuntimeError(f"staged blob {sha} is corrupt on download")
        return data

    def stage_clear(self, refs) -> int:
        """RETENTION: remove staged blobs by ref once the orchestrator holds them (a round deletes its staged artefacts after downloading
        them). A blob left behind (an interrupted round) is content-addressed, sits under a root workers cannot read, and is removed by the
        next round's clear or `stage_clear` of the refs recorded in the round directory. Returns the count removed."""
        n = 0
        touched = set()
        for ref in refs or []:
            if not isinstance(ref, dict) or not ref.get("stage"):
                continue
            vol = ref.get("vol", "store")
            sha = ref["stage"]
            with contextlib.suppress(Exception):
                self.vols[vol].remove_file(f"_staged/{sha[:2]}/{sha}.bin")
                n += 1
                touched.add(vol)
        for vol in touched:
            with contextlib.suppress(Exception):
                self.vols[vol].commit()
        return n

    def methods_key(self, mdir: Path) -> str:
        """Deterministic tar of a method snapshot directory, uploaded once to the fit volume (/methods/<key>.tar); key = sha256[:16]."""
        blob = tar_bytes(Path(mdir))
        key = hashlib.sha256(blob).hexdigest()[:16]
        vol = self.vols["fit"]
        try:
            present = {Path(e.path).name for e in vol.listdir("/methods")}
        except Exception:  # noqa: BLE001
            present = set()
        if f"{key}.tar" not in present:
            with vol.batch_upload(force=True) as b:
                b.put_file(io.BytesIO(blob), f"/methods/{key}.tar")
        return key

    def upload_dir(self, volume_name: str, base: Path, dest: str, files: list[Path] | None = None, *, replace: bool = True) -> dict:
        """Pack `files` (default: every file under base) as ONE tar, upload it to /<volume>/_incoming and unpack it in Modal (per-file
        uploads are dominated by round trips on a slow uplink). Returns {n_files, tar_bytes, sha256: {relative path: hash}}.
        replace=True DELETES /<volume>/<dest> first (the destination becomes exactly the upload); replace=False merges into it (use it
        for files added to a directory that holds other data, e.g. tier-level files next to the systems' parts)."""
        base = Path(base)
        files = sorted(files if files is not None else [q for q in base.rglob("*") if q.is_file()])
        name = dest.strip("/").replace("/", "_") + f"_{uuid.uuid4().hex[:8]}.tar"
        buf = io.BytesIO()
        sha = {}
        with tarfile.open(fileobj=buf, mode="w") as tf:
            for q in files:
                data = q.read_bytes()
                rel = q.relative_to(base).as_posix()
                sha[rel] = hashlib.sha256(data).hexdigest()
                ti = tarfile.TarInfo(rel)
                ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
                tf.addfile(ti, io.BytesIO(data))
        blob = buf.getvalue()
        with self.vols[volume_name].batch_upload(force=True) as b:
            b.put_file(io.BytesIO(blob), f"/_incoming/{name}")
        r = self.run([{"kind": "extract", "volume": volume_name, "name": name, "dest": dest, "replace": bool(replace)}], "util", "extract")[0]
        if isinstance(r, BaseException) or (replace and r.get("extracted_files") != len(files)) or                 (not replace and int(r.get("extracted_files") or 0) < len(files)):
            raise RuntimeError(f"extraction of {dest} failed or incomplete: {r!r}"[:1000])
        return {"n_files": len(files), "tar_bytes": len(blob), "sha256": sha}

    def download_dir(self, volume_name: str, remote_dir: str, local_dir: Path, *, replace: bool = True) -> dict:
        """Download /<volume>/<remote_dir> into local_dir: the directory is packed into one tar on the volume (`tar_dir` job, util
        class), streamed down, checked against the container's sha256, extracted (safe members only) and removed from the volume."""
        name = remote_dir.strip("/").replace("/", "_") + f"_{uuid.uuid4().hex[:8]}"
        r = self.run([{"kind": "tar_dir", "volume": volume_name, "dir": remote_dir.strip("/"), "name": name}], "util", "tar_dir")[0]
        if isinstance(r, BaseException) or not isinstance(r, dict) or r.get("error"):
            raise RuntimeError(f"packing {volume_name}:{remote_dir} failed: {r!r}"[:2000])
        local_dir = Path(local_dir)
        local_dir.parent.mkdir(parents=True, exist_ok=True)
        tmp_tar = local_dir.parent / f".{name}.tar"
        h = hashlib.sha256()
        t0 = time.time()
        with open(tmp_tar, "wb") as fh:                       # a real (seekable) file: the client may seek while it retries
            self.vols[volume_name].read_file_into_fileobj(r["path"], fh)
        with open(tmp_tar, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 22), b""):
                h.update(chunk)
        if h.hexdigest() != r["sha256"]:
            tmp_tar.unlink(missing_ok=True)
            raise RuntimeError(f"download of {volume_name}:{remote_dir}: sha256 mismatch")
        if replace and local_dir.exists():
            import shutil
            shutil.rmtree(local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tmp_tar) as tf:
            tf.extractall(local_dir, filter="data")
        tmp_tar.unlink(missing_ok=True)
        try:
            self.vols[volume_name].remove_file(r["path"])
        except Exception:  # noqa: BLE001, S110 - a leftover tar on the volume is harmless
            pass
        return {"volume": volume_name, "dir": remote_dir, "n_files": r["n_files"], "bytes": r["bytes"], "sha256": r["sha256"],
                "download_s": round(time.time() - t0, 1)}

    def cost_summary(self) -> dict:
        return {"app_id": self.app_id, "calls": self.costs, "usd_approx_total": round(sum(c["usd_approx"] for c in self.costs), 4),
                "refusals": self.refusals, "infra_faults": dict(getattr(self, "infra_faults", {}) or {}),
                "selftest_refusals": list(getattr(self, "selftest_refusals", []) or []),
                "selftest_counts": dict(getattr(self, "selftest_counts", {}) or {}), "hosts": self.hosts}


def _check_inline(payloads: list[dict], cls: str) -> None:
    """Refuse, BEFORE submission, an iso payload whose inline data exceed what a block_network container can receive (2 MiB through
    Modal's inline path; above it Modal would need its blob store, which block_network blocks). Every iso class is block_network, so a
    large model must travel by REF: `Backend.stage_put(model)` and {"model_ref": ref} in the payload (the tournament does this)."""
    if not CLASSES.get(cls, {}).get("block_network"):
        return
    for i, p in enumerate(payloads):
        n = _payload_bytes(p)
        if n > MAX_INLINE - INLINE_MARGIN:
            raise ValueError(f"iso payload {i} ({p.get('role')}) carries {n} bytes inline, above the {MAX_INLINE}-byte limit of the "
                             f"block_network class {cls!r}; pass large data by ref (Backend.stage_put -> {{'model_ref': ref}})")


def _payload_bytes(p: dict) -> int:
    """The payload's size as Modal ships it: its serialisation by Modal's own serializer (the same call Modal makes for an input; the
    earlier estimate measured nested bytes by their TEXT form, about 3.6x too large: a 1.14 MB model inside "models" was refused as
    4.08 MB, P3's report). Falls back to pickle when Modal's serializer is not importable."""
    try:
        from modal._serialization import serialize
        return len(serialize(p))
    except ImportError:
        return len(pickle.dumps(p, protocol=pickle.HIGHEST_PROTOCOL))


def _key_file(key: str) -> str:
    """A job key as a file name (keys are free text; the file name is readable and collision-free)."""
    safe = "".join(ch if ch.isalnum() or ch in "-_.=" else "_" for ch in key)[:120]
    return f"{safe}~{hashlib.sha256(key.encode('utf-8')).hexdigest()[:12]}"


def tar_bytes(d: Path, prefix: str = "") -> bytes:
    """A deterministic tar of a directory (sorted names, zero mtimes; no __pycache__ / .pyc)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for p in sorted(q for q in Path(d).rglob("*") if q.is_file() and "__pycache__" not in q.parts and q.suffix != ".pyc"):
            data = p.read_bytes()
            ti = tarfile.TarInfo(prefix + p.relative_to(d).as_posix())
            ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def write_cost_record(path: Path, be: Backend, extra: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(be.cost_summary(), **(extra or {})), indent=1) + "\n", encoding="utf-8", newline="\n")


# LOCAL execution (the user's directive of 2026-09-28: no further Modal spend; research/phase4/LOCAL_EXECUTION_PLAN.md): with
# P4_BACKEND=local every driver's `from brainir_causal.p4modal.app import Backend` gets the local backend (same interface, same
# container-side code, local volumes; p4modal.local)
if __import__("os").environ.get("P4_BACKEND") == "local":
    from .local import LocalBackend as Backend  # noqa: E402, F811
