"""Trusted driver function for the worker-uid smoke (scripts/p4/smoke_uids_modal.py; P2's finding of 2026-09-27), baked into the iso
image under /repo/scripts/p4 and reached by an iso "call" job (target "uid_probe_call:interleave_call"). It runs in the CHILD DRIVER
of one packed slot with the slot's real `isolation.LinuxUidTransport` (real uids, setpriv + unshare, gVisor):

  1. two models of the `uid_probe` method (tags 1 and 2) fitted in this slot, then called INTERLEAVED through two `RemoteFresh`: every
     call must succeed (called directly, never through safe_call), each model keeps one live process, the two live workers hold two
     different uids;
  2. a digest-rule restart of model A while model B is live: B's process is untouched;
  3. model B's worker killed from outside (SIGKILL by the root driver, as the out-of-memory killer would): B's next call is served by
     a fresh process (one infrastructure restart recorded), never a failed call;
  4. the cost of one worker restart, by part: process start until the worker answers (boot), init (the environment's scientific stack
     imported before the tripwire; no method code), model load (the first method code), close;
  5. PRE-STARTED SPARES (`RemoteFresh(spares=...)`): a restart-heavy sequence (the digest rule before every call) without and with 3
     spares: seconds per restart, and identical outputs.
Nothing a worker produced is unpickled: replies cross the safe codec (floats, dicts)."""

from __future__ import annotations

import os
import pickle
import signal
import time

import numpy as np

from brainir_causal import isolation as I
from brainir_causal import worker as W


def _frame(proc, rid: int, op: str, **kw):
    W.write_frame(proc.stdin, pickle.dumps({"id": rid, "op": op, **kw}, protocol=pickle.HIGHEST_PROTOCOL))
    fr = W.read_frame(proc.stdout, max_frame=I.MAX_REPLY_BYTES)
    if fr is None:
        raise RuntimeError(f"no reply to {op}")
    msg = W.decode_safe(fr, I.MAX_REPLY_BYTES)
    if "error" in msg:
        raise RuntimeError(f"{op}: {msg['error'][:300]}")
    return msg.get("ok")


def restart_parts(transport, blob: bytes, n: int = 5) -> dict:
    """Seconds per part of a worker (re)start, n times: boot (spawn until a ping is answered), init, load_model, close."""
    parts: dict = {"boot": [], "init": [], "load": [], "close": []}
    for _ in range(n):
        t = time.time()
        proc = transport.start("C", threads=1)
        try:
            _frame(proc, 1, "ping")
            parts["boot"].append(time.time() - t)
            t = time.time()
            _frame(proc, 2, "init", method_dir=getattr(transport, "method_dir_in_worker", None), threads=1, allowed=[], tripwire=True,
                   preimport=True)
            parts["init"].append(time.time() - t)
            t = time.time()
            _frame(proc, 3, "load_model", blob=blob)
            parts["load"].append(time.time() - t)
            t = time.time()
            _frame(proc, 4, "shutdown")
            proc.wait(10)
        finally:
            proc.finish()
        parts["close"].append(time.time() - t)
    return {k: {"mean_s": round(float(np.mean(v)), 3), "max_s": round(float(np.max(v)), 3)} for k, v in parts.items() if v}


def spare_timing(transport, blob: bytes, X, U, k: int = 12) -> dict:
    """k calls whose histories get SHORTER (the digest rule restarts before every call after the first, as on systems at exact
    fixed points), once without spares and once with 3: seconds per restart, and the outputs (length, tag) of both runs."""
    out: dict = {}
    for spares in (0, 3):
        rf = I.RemoteFresh(blob, transport, threads=1, spares=spares)
        vals, t_first = [], None
        try:
            t0 = time.time()
            for j, n in enumerate(range(40, 40 - k, -1)):
                z = rf.encode("toy", X[:n], U[:n], 0.01)
                vals.append([float(z[3]), float(z[2])])          # deterministic: the history's sum and the model's tag
                if j == 0:
                    t_first = time.time()
            wall = time.time() - (t_first or t0)
        finally:
            rec = rf.close()
        out[f"spares_{spares}"] = {"restarts": rec.get("worker_restarts"), "spares_used": rec.get("spares_used"),
                                   "s_per_restart": round(wall / max(1, k - 1), 3), "outputs": vals}
    out["outputs_identical"] = out["spares_0"]["outputs"] == out["spares_3"]["outputs"]
    return out


def _proc_table() -> list:
    rows = []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            st = open(f"/proc/{d}/status").read().splitlines()
            get = {ln.split(":", 1)[0]: ln.split(":", 1)[1].strip() for ln in st if ":" in ln}
            cmd = open(f"/proc/{d}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="replace")[:120]
            rows.append([int(d), get.get("PPid"), (get.get("Uid") or "").split()[:1], get.get("State"), cmd])
        except Exception:  # noqa: BLE001, S112
            continue
    return sorted(rows)


def _arm_watchdog(deadline_s: float, state: dict):
    """DIAGNOSTIC: if the smoke is not done after deadline_s, write every thread's stack, the process table and the last step into
    this child driver's result file (its --out argument) and exit, so a hang comes back as data instead of a silent wait."""
    import sys
    import threading
    import traceback

    def fire():
        if state.get("done"):
            return
        stacks = {str(tid): "".join(traceback.format_stack(fr))[-3500:] for tid, fr in sys._current_frames().items()}
        diag = {"pass": False, "error": f"DIAGNOSTIC: not done after {deadline_s:.0f} s", "step": state.get("step"),
                "stacks": stacks, "procs": _proc_table()}
        try:
            out_path = sys.argv[sys.argv.index("--out") + 1]
            tmp = out_path + ".diag"
            with open(tmp, "wb") as fh:
                pickle.dump({"result": diag}, fh, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, out_path)
        finally:
            os._exit(0)
    t = threading.Timer(float(deadline_s), fire)
    t.daemon = True
    t.start()
    return t


def interleave_call(job, *, transport, models=None):
    t0 = time.time()
    state: dict = {"step": "start"}
    if job.get("deadline_s"):
        _arm_watchdog(float(job["deadline_s"]), state)
    n_rounds = int(job.get("rounds", 6))
    blobs = [I.fit_records(transport, method="uid_probe", records=[], systems={"toy": {}}, config={"tag": tag})["model"] for tag in (1, 2)]
    rng = np.random.default_rng(int(job.get("seed", 0)))
    X, U = rng.standard_normal((80, 2)), np.zeros((80, 1))
    ra, rb = I.RemoteFresh(blobs[0], transport, threads=1), I.RemoteFresh(blobs[1], transport, threads=1)
    rows, errors, checks = [], [], {}

    def call(name, rf, n):
        try:
            z = rf.encode("toy", X[:n], U[:n], 0.01)
            rows.append({"model": name, "n": n, "pid": int(z[0]), "uid": int(z[1]), "tag": float(z[2])})
            return rows[-1]
        except BaseException as e:  # noqa: BLE001 - recorded: a failed call fails the smoke (never swallowed silently)
            errors.append(f"{name} n={n}: {type(e).__name__}: {str(e)[:300]}")
            return None
    try:
        state["step"] = "interleave"
        for n in range(10, 10 + n_rounds):
            call("a", ra, n)
            call("b", rb, n)
        a_rows, b_rows = [r for r in rows if r["model"] == "a"], [r for r in rows if r["model"] == "b"]
        checks["one_process_each"] = len({r["pid"] for r in a_rows}) == 1 and len({r["pid"] for r in b_rows}) == 1
        checks["distinct_uids"] = bool(a_rows and b_rows) and a_rows[0]["uid"] != b_rows[0]["uid"]
        checks["live_uids"] = transport.live_uids()
        pid_b = b_rows[-1]["pid"] if b_rows else None
        # 2. a digest-rule restart of A while B is live
        state["step"] = "a digest restart"
        ra_restarts = ra.n_restarts
        call("a", ra, 5)
        rb_after = call("b", rb, 10 + n_rounds)
        checks["a_restarted"] = ra.n_restarts == ra_restarts + 1
        checks["b_untouched"] = bool(rb_after and rb_after["pid"] == pid_b)
        # 3. B's worker killed from outside
        state["step"] = "kill b"
        if pid_b is not None:
            os.kill(pid_b, signal.SIGKILL)
            time.sleep(0.5)
        rb_new = call("b", rb, 11 + n_rounds)
        checks["b_served_by_a_fresh_process"] = bool(rb_new and rb_new["pid"] != pid_b)
        checks["b_infra_restarts"] = rb.n_infra
        checks["a_infra_restarts"] = ra.n_infra
    finally:
        state["step"] = "close a, b"
        reca, recb = ra.close(), rb.close()
    checks["no_live_uid_left"] = transport.live_uids() == []
    state["step"] = "restart parts"
    parts = restart_parts(transport, blobs[0], int(job.get("timing_n", 5)))
    state["step"] = "spare timing"
    spares = spare_timing(transport, blobs[0], X, U, int(job.get("spare_k", 12)))
    state["done"] = True
    checks["spares_outputs_identical"] = spares["outputs_identical"]
    checks["spares_used"] = spares["spares_3"]["spares_used"]
    ok = (checks["spares_outputs_identical"] and checks["spares_used"] >= 1 and not errors and checks.get("one_process_each") and checks.get("distinct_uids") and checks.get("a_restarted")
          and checks.get("b_untouched") and checks.get("b_served_by_a_fresh_process") and checks.get("b_infra_restarts") == 1
          and checks.get("a_infra_restarts") == 0 and checks.get("no_live_uid_left"))
    return {"pass": bool(ok), "checks": checks, "errors": errors, "rows": rows, "restart_parts": parts,
            "spare_timing": {k: ({kk: vv for kk, vv in v.items() if kk != "outputs"} if isinstance(v, dict) else v) for k, v in spares.items()},
            "records": {"a": {k: reca.get(k) for k in ("worker_restarts", "infra_restarts")},
                        "b": {k: recb.get(k) for k in ("worker_restarts", "infra_restarts")},
                        "b_infra": ((recb.get("phases") or {}).get("A") or {}).get("infra")},
            "slot": getattr(transport, "slot", None), "driver_uid": os.getuid(), "wall_s": round(time.time() - t0, 2)}
