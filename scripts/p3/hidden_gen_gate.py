"""Host-gated Modal execution of the FROZEN real hidden-data generator (orchestrator; LOG P3-D26). Not hashed by the benchmark lock:
it changes no hashed file and no computation, only WHERE the frozen generator's calls run.

    uv run --project phase3 --no-sync python scripts/p3/hidden_gen_gate.py verify-public [--n 60] [--containers 60]
    uv run --project phase3 --no-sync python scripts/p3/hidden_gen_gate.py generate [--containers 300]
    uv run --project phase3 --no-sync python scripts/p3/hidden_gen_gate.py crosscheck

Why. After the OpenBLAS core-type pin was dropped (it crashed workers on some hosts), Modal hosts with AVX-512 run other BLAS kernels
than the development machine, and the real engine's records are then not bit-identical to the stored public ones (13 of 20 in the
post-lock `generate_real_hidden.py verify-public`). Hosts without AVX-512 run the same kernels as the development machine.

What. Every call of `scripts/p3/generate_real_hidden.py`'s Modal backend (`run_modal`: simulation batches, microstate restarts,
assembly, tar) goes through `gated()`. In the container's worker process it reads the CPU flags from /proc/cpuinfo:
- on a host with AVX-512 it returns a refusal BEFORE any computation, and the orchestrator re-submits that input at once (spawn);
  the container stays up;
- on a host without AVX-512 it calls the frozen function unchanged and returns its value with the host's CPU description.

A first version ended its worker with SIGKILL on AVX-512 hosts, so that the frozen crash handling moved the input to a fresh
container. It passed the public check (60 of 60 bit-identical), but Modal throttles the scale-up of a function whose containers exit
(parallelism about 1.3), so it is kept only as mode 'exit'.

Everything else is the frozen generator's code, called as is (`run_modal` with its `_modal_calls` replaced): salt, protocols, job
order, record keys, microstate selection, assembly and the transfer check of the local copy.

verify-public repeats `verify_public` of the frozen script on the gated path, restricted to PUBLIC records of the store (the store
index also lists hidden records after a partial local generation); crosscheck compares the generated dataset with any local store
record of the same key (the stopped local generation of 2026-09-25), array by array.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "p3"))
REC_DIR = ROOT / "research" / "phase3" / "level_c"
MAX_ROUNDS = 40


# ------------------------------------------------------------------------------------------------ container side
def host_cpu(cpuinfo: str | None = None) -> dict:
    """Model name, vendor and the SIMD flags that decide the BLAS kernels, from /proc/cpuinfo (or the given text)."""
    if cpuinfo is None:
        try:
            cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
        except OSError:
            cpuinfo = ""
    model, vendor, flags = "", "", set()
    for line in cpuinfo.splitlines():
        key, _, val = line.partition(":")
        key = key.strip()
        if key == "model name" and not model:
            model = val.strip()
        elif key == "vendor_id" and not vendor:
            vendor = val.strip()
        elif key == "flags" and not flags:
            flags = set(val.split())
    return {"model": model, "vendor": vendor, "avx512f": "avx512f" in flags, "avx2": "avx2" in flags, "fma": "fma" in flags}


def gated(target: str, args: list, tag: int | None = None, mode: str = "refuse"):
    """Run generate_real_hidden.<target>(*args) only on a host without AVX-512 (see the module docstring). On another host, before
    computing anything: mode 'refuse' returns a refusal (the orchestrator re-submits the input; the container stays up), mode 'exit'
    ends the worker with SIGKILL (the frozen crash handling then moves the input to a fresh container; slow, because Modal throttles
    the scale-up of a function whose containers exit)."""
    h = host_cpu()
    if h["avx512f"] or not h["avx2"]:
        if mode == "exit":
            os.kill(os.getpid(), signal.SIGKILL)
        return {"tag": tag, "refused": True, "host": h}
    import generate_real_hidden as G
    return {"tag": tag, "refused": False, "host": h, "value": getattr(G, target)(*args)}


# ------------------------------------------------------------------------------------------------ orchestrator side
_HOSTS: list = []


MAX_ATTEMPTS = 400          # per input; a refusal costs a few seconds of a warm container


def _not_ready(e: BaseException) -> bool:
    return "timeout" in type(e).__name__.lower()          # FunctionCall.get(timeout=0) before the output exists


def gated_modal_calls(module_func: str, arg_lists: list, commit: bool) -> list:
    """Drop-in replacement of generate_real_hidden._modal_calls: the same payload kind, links and timeout, the frozen function called
    through gated() (mode 'refuse'). All inputs go out as one map (outputs as they complete); an input refused by an AVX-512 host is
    re-submitted at once with spawn, and so is an input whose call failed on Modal. A worker ERROR (an exception in the frozen
    function) stops the run as in the frozen code. Returns the frozen function's values in input order."""
    import generate_real_hidden as G
    import modal_tournament as MT
    fn = MT._STATE["eval_fn"]
    n = len(arg_lists)
    out: list = [None] * n
    have = [False] * n
    attempts = [0] * n
    side: dict = {}
    recs: list = []
    stats = {"refused": 0, "failed_calls": 0}
    t0 = time.time()

    def payload(i: int) -> dict:
        attempts[i] += 1
        if attempts[i] > MAX_ATTEMPTS:
            raise SystemExit(f"remote {module_func}: input {i} not placed on a host without AVX-512 after {MAX_ATTEMPTS} attempts")
        return {"job_id": uuid.uuid4().hex, "kind": "call_commit" if commit else "call", "module": "hidden_gen_gate", "func": "gated",
                "args": [module_func, list(arg_lists[i]), i, "refuse"], "links": G.REMOTE_LINKS, "timeout_s": 7200}

    def handle(r) -> None:
        if not isinstance(r, dict) or "result" not in r or not isinstance(r["result"], dict):
            raise SystemExit(f"remote {module_func} failed: {(r or {}).get('error')} {((r or {}).get('stderr') or '')[-2000:]}")
        recs.append(r)
        res = r["result"]
        i = int(res["tag"])
        if res.get("refused"):
            stats["refused"] += 1
            side[i] = fn.spawn(payload(i))
            return
        if not have[i]:
            out[i], have[i] = res["value"], True
            _HOSTS.append({"func": module_func, "attempt": attempts[i], "host": res["host"], "signal_crashes": len(r.get("signal_crashes") or [])})

    def poll_side() -> None:
        for i, call in list(side.items()):
            try:
                r = call.get(timeout=0)
            except Exception as e:  # noqa: BLE001
                if _not_ready(e):
                    continue
                stats["failed_calls"] += 1
                side[i] = fn.spawn(payload(i))
                continue
            del side[i]
            handle(r)

    last = time.time()
    for r in fn.map([payload(i) for i in range(n)], order_outputs=False, return_exceptions=True):
        if isinstance(r, BaseException):
            stats["failed_calls"] += 1          # which input is unknown here: re-submitted after the map
        else:
            handle(r)
        if side and time.time() - last > 5:
            poll_side()
            last = time.time()
    for i in range(n):
        if not have[i] and i not in side:
            side[i] = fn.spawn(payload(i))
    while side:
        poll_side()
        if side:
            time.sleep(2)
        if time.time() - last > 60:
            print(f"  gated {module_func}: {sum(have)} of {n} done, {len(side)} re-submitted in flight ({time.time() - t0:.0f} s)", flush=True)
            last = time.time()
    print(f"  gated {module_func}: {n} done in {time.time() - t0:.0f} s; refusals {stats['refused']}, failed calls {stats['failed_calls']}, "
          f"max attempts {max(attempts) if attempts else 0}", flush=True)
    MT._cost(recs, f"call:{module_func} (gated)")
    _STATS.append({"func": module_func, "n": n, **stats, "max_attempts": max(attempts) if attempts else 0, "wall_s": round(time.time() - t0, 1)})
    return out


_STATS: list = []


def _host_summary() -> dict:
    from collections import Counter
    return {"calls": len(_HOSTS), "models": dict(Counter(h["host"]["model"] for h in _HOSTS)),
            "any_avx512": any(h["host"]["avx512f"] for h in _HOSTS), "all_avx2": all(h["host"]["avx2"] for h in _HOSTS),
            "by_func": dict(Counter(h["func"] for h in _HOSTS)), "stages": _STATS}


def verify_public(n: int, containers: int) -> int:
    """The frozen verify_public on the gated path, PUBLIC store records only; every array compared bit for bit (sha256)."""
    import numpy as np
    import generate_real_hidden as G
    import modal_tournament as MT
    from brainir_state.store import TrajectoryStore
    systems = json.loads((G.BENCH / "hidden" / "systems_internal.json").read_text(encoding="utf-8"))
    store = TrajectoryStore(G.DATA / "store")
    rows = [json.loads(line) for line in open(store.index_path, encoding="utf-8")]
    rows = [r for r in rows if r.get("source") == "public"]
    rng = np.random.default_rng(0)
    picked, seen = [], {}
    for r in [rows[i] for i in rng.permutation(len(rows))]:
        if r.get("system_id") not in systems or not store.has(r["key"]):
            continue
        if seen.get(r["system_id"], 0) >= max(2, n // len(systems)):
            continue
        seen[r["system_id"]] = seen.get(r["system_id"], 0) + 1
        picked.append(r)
        if len(picked) >= n:
            break
    items = [(systems[r["system_id"]], r["protocol"], {}) for r in picked]
    app = MT._open_app(containers)
    t0 = time.time()
    with MT._output(), app.run():
        res = [x for b in gated_modal_calls("remote_sim_batch", [[[it], "/tmp/verify_store", True] for it in items], commit=False) for x in b]
    bad = []
    for r, row in zip(res, picked):
        rec = store.get(row["key"])
        local = {k: hashlib.sha256(np.ascontiguousarray(rec[k]).tobytes()).hexdigest() for k in ("t", "neurons", "rates", "u")}
        if r["key"] != row["key"] or r["sha"] != local:
            bad.append({"system_id": row["system_id"], "key": row["key"], "remote_key": r["key"],
                        "arrays_differing": [k for k in local if r["sha"].get(k) != local[k]]})
    rep = {"n": len(picked), "systems": sorted(seen), "n_mismatch": len(bad), "mismatches": bad, "source_filter": "public",
           "memory_mb": MT.MEM_MB, "cpu": MT.CPU, "wall_s": round(time.time() - t0, 1), "hosts": _host_summary(), "host_calls": _HOSTS,
           "costs": MT._STATE["costs"]}
    (REC_DIR / "hidden_generator_modal_gated_verification.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in rep.items() if k not in ("mismatches", "host_calls", "costs")}, indent=1), flush=True)
    return 0 if not bad else 1


def _remote_exists(path: str) -> bool:
    import modal
    vol = modal.Volume.from_name("brainir-p3-eval")
    try:
        return bool(list(vol.listdir(path)))
    except Exception:  # noqa: BLE001 - not found
        return False


def generate(containers: int) -> int:
    """The frozen generate_real_hidden.py --backend modal (build_jobs with its default per-family count, run_modal) on the gated
    path. Refuses before the method lock, and when a hidden dataset or a remote build already exists."""
    import generate_real_hidden as G
    import modal_tournament as MT
    if not (ROOT / "research" / "phase3" / "METHOD_LOCK.json").exists():
        raise SystemExit("refusing: the Level C hidden test is generated only after research/phase3/METHOD_LOCK.json exists")
    if (G.DATA / "real_hidden").exists():
        raise SystemExit("refusing: data/phase3/real_hidden exists (a hidden dataset is never overwritten silently)")
    for p in ("/real_hidden_build", "/suites/real/hidden"):
        if _remote_exists(p):
            raise SystemExit(f"refusing: the eval volume already holds {p}; inspect it first")
    per_family = 30                                   # the frozen CLI default (generate_real_hidden.py --per-family)
    systems, public, jobs, meta = G.build_jobs(per_family)
    print(f"{len(systems)} systems; {len(jobs)} hidden trajectories (modal, host-gated; {MT.CPU:g} CPU / {MT.MEM_MB} MB containers)", flush=True)
    G._modal_calls = gated_modal_calls
    t0 = time.time()
    rep = G.run_modal(systems, public, jobs, meta, containers)
    rec = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "backend": "modal, host-gated (no AVX-512)",
           "per_family": per_family, "n_jobs": len(jobs), "memory_mb": MT.MEM_MB, "cpu": MT.CPU, "wall_s": round(time.time() - t0, 1),
           "n_items": rep.get("n_items"), "n_micro": rep.get("n_micro"), "sha256": rep.get("sha256"), "tar_sha256": rep.get("tar_sha256"),
           "hosts": _host_summary(), "costs": rep.get("costs")}
    (REC_DIR / "hidden_generation_record.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "costs"}, indent=1), flush=True)
    return 0


def crosscheck() -> int:
    """Compare every generated hidden trajectory with a local store record of the same key (when one exists): t, u, and the dense
    observed / readout arrays, bit for bit. A numerical check only (no method is involved)."""
    import numpy as np
    import generate_real_hidden as G
    from brainir_state import data as D
    from brainir_state.realsim import dense
    from brainir_state.store import TrajectoryStore
    systems = json.loads((G.BENCH / "hidden" / "systems_internal.json").read_text(encoding="utf-8"))
    ds = D.Dataset(G.DATA / "real_hidden")
    store = TrajectoryStore(G.DATA / "store")
    n = same = 0
    diff = []
    for r in ds.index:
        rec = store.get(r["key"])
        if rec is None:
            continue
        n += 1
        tr = ds.load(r)
        d = systems[r["system_id"]]
        ok = (np.array_equal(np.asarray(rec["t"]), np.asarray(tr.t)) and np.array_equal(np.asarray(rec["u"]), np.asarray(tr.u))
              and np.array_equal(dense(rec, d["observed"]), tr.x) and np.array_equal(dense(rec, d["readout"]), tr.y))
        same += ok
        if not ok and len(diff) < 20:
            diff.append({"key": r["key"], "system_id": r["system_id"], "family": r["family"],
                         "x_max_abs": float(np.max(np.abs(dense(rec, d["observed"]) - tr.x))) if dense(rec, d["observed"]).shape == tr.x.shape else None})
    rep = {"n_dataset": len(ds.index), "n_with_local_record": n, "n_identical": same, "first_differences": diff}
    (REC_DIR / "hidden_generation_crosscheck.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rep, indent=1), flush=True)
    return 0 if same == n else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify-public")
    v.add_argument("--n", type=int, default=60)
    v.add_argument("--containers", type=int, default=60)
    g = sub.add_parser("generate")
    g.add_argument("--containers", type=int, default=300)
    sub.add_parser("crosscheck")
    a = ap.parse_args(argv)
    if a.cmd == "verify-public":
        return verify_public(a.n, a.containers)
    if a.cmd == "generate":
        return generate(a.containers)
    return crosscheck()


if __name__ == "__main__":
    raise SystemExit(main())
