"""The developers' simulation service of a Phase 4 room, on the REFERENCE PLATFORM (ORCHESTRATOR SIDE; LOG P4-D32 / P4-D33;
research/phase4/EVAL_ARCHITECTURE.md, "The developers' simulation service").

    uv run --no-sync --project phase4 python scripts/p4/simservice_docker.py start --room clean [--budget 3000] [--modal]
        [--docker-workers 4 --docker-cpus 4 --docker-mem-gb 8]
    uv run --no-sync --project phase4 python scripts/p4/simservice_docker.py status --room clean
    uv run --no-sync --project phase4 python scripts/p4/simservice_docker.py stop --room clean
    uv run --no-sync --project phase4 python scripts/p4/simservice_docker.py selftest [--system <dev system id>] [--compare-modal]
    uv run --no-sync --project phase4 python scripts/p4/simservice_docker.py build-image      # the worker image (docker/p4simservice)

start: writes, under C:/Dev/BrainIR_p4audit/simservice/<room directory name>/ (outside every room; the agent launcher's token table
tokens.json lives there): systems.json (the INTERNAL records of the room's public systems: the dev tier and the public real
systems), public_keys.json (`simservice.build_public_keys` over the public dataset directories: every public row with its store key
and protocol), then starts `python -m brainir_causal.simservice ... --docker` DETACHED: the host process keeps the room's queue
(simq/<scratch>/), identity tokens, the public policy, budgets, ledgers (ledger/) and, with --modal, the Modal client for real FULL
networks; every local simulation runs in one container of the pinned image (`brainir_causal.simdocker`; store/ and bridge/ are its
only writable mounts). The command, the container's docker command and mounts, the counts and the pids go to launch.json.
status: host process, container, ledger / request / error counts, log tail. stop: stops both.
selftest: the service against the benchmark's own records, end to end on the reference platform: builds the PUBLIC part of one dev
system in the image (the benchmark's build code, into a scratch store), starts the service with an EMPTY store and a fake agent
(token, own queue simq/<scratch>/), and checks that (1) a public row's own protocol returns the benchmark's dataset arrays, (2)
restarts from public trajectories (recomputed on demand) and (3) a fresh protocol equal what the benchmark's SimContext computes in the
image from the build's store. --compare-modal additionally compares the scratch build's rows (keys, store keys, arrays of a sample)
with the dev tier's rows on the Modal fit volume; a real MECHANISM system's public row returns the Modal-built dataset arrays and a
restart from it is served. Writes research/phase4/SIMSERVICE_DOCKER_SELFTEST.json.
build-image: builds docker/p4simservice (the pinned sandbox image + duckdb for the real engine; checks that the sandbox tag is the
pinned id first) and records docker/p4simservice/image.json.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import protocol as P  # noqa: E402
from brainir_causal import suites as SU  # noqa: E402
from brainir_causal import systems as SY  # noqa: E402

AUDIT = Path("C:/Dev/BrainIR_p4audit")
ROOMS = {"clean": Path("C:/Dev/BrainIR_p4clean"), "review": Path("C:/Dev/BrainIR_p4review"), "bench": Path("C:/Dev/BrainIR_p4bench")}
DEV_PUBLIC = ROOT / "data" / "phase4" / "suites" / "dev" / "public"
DEV_INTERNAL = ROOT / "data" / "phase4" / "suites" / "dev" / "internal_records.json"
REAL_PUBLIC = ROOT / "data" / "phase4" / "real" / "real_public" / "public"
SELFTEST_OUT = ROOT / "research" / "phase4" / "SIMSERVICE_DOCKER_SELFTEST.json"


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return bool(ok) and code.value == 259                                        # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _docker_running(name: str) -> bool:
    from brainir_causal.isolation import docker_exe
    r = subprocess.run([docker_exe(), "inspect", "-f", "{{.State.Running}}", name], capture_output=True, text=True, timeout=60, check=False)
    return r.returncode == 0 and r.stdout.strip() == "true"


def room_dir(args) -> Path:
    return Path(args.room_dir) if args.room_dir else ROOMS[args.room]


def service_dir(room: Path) -> Path:
    return AUDIT / "simservice" / room.name


def room_systems() -> dict:
    """{system id: INTERNAL record} of the public systems a room's service serves: the dev tier and the real systems with public data."""
    out = {}
    if DEV_INTERNAL.exists():
        out.update(json.loads(DEV_INTERNAL.read_text(encoding="utf-8")))
    real = SY.load_real_internal()
    for sid, rec in real.items():
        if (REAL_PUBLIC / SU._safe(sid) / "index.jsonl").exists():
            out[sid] = rec
    return out


def public_set_dirs() -> list[Path]:
    return sorted(d for base in (DEV_PUBLIC, REAL_PUBLIC) if base.exists() for d in base.iterdir() if (d / "index.jsonl").exists())


# ================================================================================================================ start / status / stop
def cmd_start(args) -> int:
    from brainir_causal.simservice import build_public_keys
    room = room_dir(args)
    if not room.is_dir():
        raise SystemExit(f"room {room} does not exist")
    svc = service_dir(room)
    launch_p = svc / "launch.json"
    if launch_p.exists():
        old = json.loads(launch_p.read_text(encoding="utf-8"))
        if _alive(old.get("pid")) and not old.get("stopped_utc"):
            raise SystemExit(f"a service for {room.name} is running (pid {old['pid']}); stop it first")
    svc.mkdir(parents=True, exist_ok=True)
    systems = room_systems()
    if not systems:
        raise SystemExit("no public systems (dev internal records / public real data missing)")
    (svc / "systems.json").write_text(json.dumps(systems, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    pk = build_public_keys(public_set_dirs(), systems=set(systems))
    (svc / "public_keys.json").write_text(json.dumps(pk) + "\n", encoding="utf-8", newline="\n")
    name = f"p4simsvc-{room.name.lower()}-{uuid.uuid4().hex[:6]}"
    cmd = [sys.executable, "-m", "brainir_causal.simservice", "--room", str(room), "--systems", str(svc / "systems.json"),
           "--store", str(svc / "store"), "--ledger-dir", str(svc / "ledger"), "--tokens", str(svc / "tokens.json"),
           "--public-keys", str(svc / "public_keys.json"), "--bundle", str(SY.BUNDLE), "--budget", str(args.budget), "--docker",
           "--bridge-dir", str(svc / "bridge"), "--docker-workers", str(args.docker_workers), "--docker-cpus", str(args.docker_cpus),
           "--docker-mem-gb", str(args.docker_mem_gb), "--name", name]
    if any(s.get("kind") == "synthetic" for s in systems.values()):
        cmd += ["--warm", f"dev:{SU.tier_seed('dev')}"]
    if args.modal:
        cmd.append("--modal")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "phase4" / "src"), str(ROOT / "src")]), "PYTHONIOENCODING": "utf-8",
           "PYTHONDONTWRITEBYTECODE": "1"}
    log = open(svc / "service.log", "a", encoding="utf-8")  # noqa: SIM115 - handed to the detached process
    log.write(f"\n==== start {_utc()}\n")
    log.flush()
    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, cwd=str(svc),  # noqa: S603
                            creationflags=flags, start_new_session=(os.name != "nt"))
    t0 = time.time()
    ready = svc / "bridge" / "ready.json"
    while not ready.exists() or ready.stat().st_mtime < t0 - 1:
        if proc.poll() is not None:
            raise SystemExit(f"the service exited during start (code {proc.returncode}); see {svc / 'service.log'}")
        if time.time() - t0 > args.start_timeout:
            raise SystemExit(f"the service did not become ready in {args.start_timeout} s; see {svc / 'service.log'}")
        time.sleep(1.0)
    time.sleep(2.0)                                           # the host part reads the engine ids and enters its loop after the pool
    dock = json.loads((svc / "bridge" / "docker_run.json").read_text(encoding="utf-8"))
    rec = {"room": room.name, "room_dir": str(room), "service_dir": str(svc), "pid": proc.pid, "container": name,
           "host_command": cmd, "docker": dock, "systems": len(systems),
           "synthetic_systems": sum(1 for s in systems.values() if s.get("kind") == "synthetic"),
           "real_systems": sum(1 for s in systems.values() if s.get("kind") == "real"),
           "public_rows": len(pk["entries"]), "public_store_key_aliases": len(pk["aliases"]), "budget_default": args.budget,
           "modal": bool(args.modal), "started_utc": _utc(), "ready_s": round(time.time() - t0, 1)}
    launch_p.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: rec[k] for k in ("room", "pid", "container", "systems", "public_rows", "ready_s")}, indent=1))
    return 0


def cmd_status(args) -> int:
    svc = service_dir(room_dir(args))
    launch_p = svc / "launch.json"
    if not launch_p.exists():
        print(json.dumps({"running": False, "why": "never started"}))
        return 1
    rec = json.loads(launch_p.read_text(encoding="utf-8"))
    led = json.loads((svc / "ledger" / "ledger.json").read_text(encoding="utf-8")) if (svc / "ledger" / "ledger.json").exists() else {}

    def lines(p: Path) -> list:
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []
    reqs = lines(svc / "ledger" / "requests.jsonl")
    errs = lines(svc / "ledger" / "errors.jsonl")
    tail = (svc / "service.log").read_text(encoding="utf-8", errors="replace").splitlines()[-8:] if (svc / "service.log").exists() else []
    out = {"room": rec["room"], "host_process": _alive(rec.get("pid")), "container": _docker_running(rec["container"]),
           "started_utc": rec.get("started_utc"), "stopped_utc": rec.get("stopped_utc"), "agents": {a: {"units": d.get("units"),
                                                                                                          "trajectories": d.get("trajectories")}
                                                                                                      for a, d in led.items()},
           "requests": len(reqs), "public_sources_recomputed": sum(int(r.get("public_sources_recomputed") or 0) for r in reqs),
           "errors": len(errs), "log_tail": tail}
    print(json.dumps(out, indent=1))
    return 0 if out["host_process"] and out["container"] else 1


def cmd_stop(args) -> int:
    from brainir_causal.isolation import docker_exe
    svc = service_dir(room_dir(args))
    launch_p = svc / "launch.json"
    if not launch_p.exists():
        raise SystemExit("no launch record")
    rec = json.loads(launch_p.read_text(encoding="utf-8"))
    if _alive(rec.get("pid")):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(rec["pid"]), "/T", "/F"], capture_output=True, text=True, timeout=60, check=False)
        else:
            os.kill(int(rec["pid"]), 15)
    subprocess.run([docker_exe(), "stop", "-t", "5", rec["container"]], capture_output=True, text=True, timeout=120, check=False)
    rec["stopped_utc"] = _utc()
    launch_p.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"room": rec["room"], "host_process": _alive(rec.get("pid")), "container": _docker_running(rec["container"])}))
    return 0


# ================================================================================================================ selftest
BUILD_ONE = r'''
import json, sys
from pathlib import Path
sys.path.insert(0, "/repo/phase4/src")
from brainir_causal import suites as SU
sid = sys.argv[1]
summ = SU.build_tier("dev", generator=(SU.GENERATOR_CONTAINER, "p4synth"), workers=4, systems=[sid], root=Path("/work/bench/suites"),
                     store_root=Path("/work/bench/store"), parts=(("public", ("public",), "public"),))
print(json.dumps(summ["systems"][sid]))
'''

REFERENCE = r'''
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, "/repo/phase4/src")
from brainir_causal import suites as SU
from brainir_causal.synthadapter import register_generator, suite_systems
req = json.loads(Path("/work/reference_requests.json").read_text(encoding="utf-8"))
register_generator(SU.GENERATOR_CONTAINER, "p4synth")
internal = req["internal"]
obj = suite_systems("dev", int(internal["suite_seed"]))[internal["system_id"]]
ctx = SU.SimContext(internal, store_root=Path("/work/bench/store"), synthetic_system=obj)
arrays = {}
for i, q in enumerate(req["protocols"]):
    r = ctx.run(q, {"no_store": True})
    for k in ("t", "x", "u", "y"):
        arrays[f"i{i}_{k}"] = np.asarray(r[k])
np.savez("/work/reference.npz", **arrays)
print("ok", len(req["protocols"]))
'''


def _docker_image_run(work: Path, script: str, args: list[str], timeout: int = 3600) -> str:
    from brainir_causal.isolation import docker_exe
    from brainir_causal.p4modal.images import CPU_PINS
    from brainir_causal.simdocker import worker_image
    (work / "_script.py").write_text(script, encoding="utf-8", newline="\n")
    cmd = [docker_exe(), "run", "--rm", "--network", "none", "--pull", "never", "--user", "1000:1000", "--read-only", "--tmpfs", "/tmp:rw,size=2g",
           "--cpus", "4", "--memory", "8g"]
    for k, v in {"PYTHONPATH": "/repo/phase4/src:/repo/src", "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/tmp", "OMP_NUM_THREADS": "1",
                 "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", **CPU_PINS}.items():
        cmd += ["-e", f"{k}={v}"]
    for src, dst, mode in ((ROOT / "phase4" / "src", "/repo/phase4/src", "ro"), (ROOT / "src", "/repo/src", "ro"),
                           (ROOT / SU.GENERATOR_REL, SU.GENERATOR_CONTAINER, "ro"), (work, "/work", "rw")):
        cmd += ["-v", f"{str(src).replace(chr(92), '/')}:{dst}:{mode}"]
    cmd += [worker_image(), "python", "/work/_script.py", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"in-image step failed:\n{r.stdout[-2000:]}\n{r.stderr[-4000:]}")
    return r.stdout


def _serve(server, stop: threading.Event) -> None:
    while not stop.is_set():
        for p in server.pending():
            try:
                server.handle(p)
            except Exception:  # noqa: BLE001
                import traceback
                traceback.print_exc()
        time.sleep(0.05)


def _compare_modal(sid: str, bench_dir: Path, n_arrays: int = 12) -> dict:
    """The scratch build's rows vs the dev tier's rows of the same system on the Modal fit volume (read-only)."""
    import io

    import modal
    from brainir_causal.p4modal.remote import VOLUME_NAMES
    vol = modal.Volume.from_name(VOLUME_NAMES["fit"])
    base = f"/data/suites/dev/public/{SU._safe(sid)}"
    buf = io.BytesIO()
    vol.read_file_into_fileobj(f"{base}/index.jsonl", buf)
    modal_rows = {r["key"]: r for r in (json.loads(x) for x in buf.getvalue().decode("utf-8").splitlines() if x.strip())}
    bench_rows = {r["key"]: r for r in (json.loads(x) for x in (bench_dir / "index.jsonl").read_text(encoding="utf-8").splitlines() if x.strip())}
    # the image builds only the training set of the public part; the Modal public part also holds the public test / pool sets
    subset = set(bench_rows) <= set(modal_rows)
    same_store = subset and all(modal_rows[k]["meta"]["store_key"] == bench_rows[k]["meta"]["store_key"] for k in bench_rows)
    same_proto = subset and all(modal_rows[k]["protocol"] == bench_rows[k]["protocol"] for k in bench_rows)
    sample = sorted(bench_rows)[:: max(1, len(bench_rows) // n_arrays)][:n_arrays]
    eq = {}
    for k in sample:
        b = io.BytesIO()
        vol.read_file_into_fileobj(f"{base}/traj/{k}.npz", b)
        b.seek(0)
        with np.load(b, allow_pickle=False) as zm, np.load(bench_dir / "traj" / f"{k}.npz", allow_pickle=False) as zb:
            eq[k[:12]] = all(np.array_equal(zm[a], zb[a]) for a in ("t", "x", "u", "y"))
    return {"rows_modal": len(modal_rows), "rows_image": len(bench_rows), "image_rows_in_modal": subset, "same_store_keys": same_store,
            "same_protocols": same_proto,
            "arrays_equal": eq}


def cmd_selftest(args) -> int:
    from brainir_causal.simclient import SimClient
    from brainir_causal.simdocker import DockerPool
    from brainir_causal.simservice import SimServer, build_public_keys, issue_token
    work = AUDIT / "simservice" / "_selftest"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    t0 = time.time()
    rec: dict = {"what": "simulation service on the reference platform vs the benchmark's own records (selftest)", "created_utc": _utc()}
    # 1. the benchmark's build of one dev system's public part, in the image
    sid = args.system
    if not sid:
        ints = json.loads(DEV_INTERNAL.read_text(encoding="utf-8")) if DEV_INTERNAL.exists() else {}
        sid = sorted(ints)[0] if ints else None
    if not sid:
        raise SystemExit("no dev system id (pass --system)")
    out = _docker_image_run(work, BUILD_ONE, [sid])
    rec["system"] = sid
    rec["image_build"] = json.loads(out.strip().splitlines()[-1])
    internal = json.loads((work / "bench" / "suites" / "dev" / "internal_records.json").read_text(encoding="utf-8"))[sid]
    bench_dir = work / "bench" / "suites" / "dev" / "public" / SU._safe(sid)
    rows = [json.loads(x) for x in (bench_dir / "index.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    pub = json.loads((bench_dir / "manifest.json").read_text(encoding="utf-8"))["systems"][sid]
    # 2. the service: host part here, simulations in the Docker pool, an EMPTY store, a fake agent with a token and its own queue
    room = work / "room"
    (room / "simq").mkdir(parents=True)
    tokens = work / "svc" / "tokens.json"
    token = issue_token(tokens, "selftest", 10**6)
    # a real MECHANISM system with local public data (built on Modal): its engine runs in the container too
    real_int = SY.load_real_internal()
    real_sid = next((s for s in sorted(real_int) if real_int[s].get("mode") != "full" and (REAL_PUBLIC / SU._safe(s) / "index.jsonl").exists()), None)
    served = {sid: internal, **({real_sid: real_int[real_sid]} if real_sid else {})}
    real_dir = REAL_PUBLIC / SU._safe(real_sid) if real_sid else None
    pk = build_public_keys([bench_dir] + ([real_dir] if real_dir else []), systems=set(served))
    pool = DockerPool(store_root=work / "svc" / "store", bridge_dir=work / "svc" / "bridge", workers=2, cpus=2, mem_gb=4, bundle=SY.BUNDLE,
                      warm=[("dev", int(internal["suite_seed"]))]).start()
    stop = threading.Event()
    try:
        server = SimServer(room, served, work / "svc" / "store", pool=pool, ledger_dir=work / "svc" / "ledger", public_keys=pk,
                           tokens=tokens, bundle=SY.BUNDLE)
        th = threading.Thread(target=_serve, args=(server, stop), daemon=True)
        th.start()
        client = SimClient(queue=room / "simq" / "selftest", token=token)
        train = set(pub["split"]["families_train"])
        plain = [r for r in rows if r["split"] == "train" and not r["protocol"]["events"] and r["protocol"]["r0"]["kind"] == "rest"]
        evented = [r for r in rows if r["split"] == "train" and r["protocol"]["events"] and r["family"] in train]
        src = plain[0]
        dt, T = float(src["protocol"]["dt"]), float(src["protocol"]["t_end"])
        t_mid = round(round(0.5 * T / dt) * dt, 9)
        ask, ref_q, what = [], [], []
        # (1) a public row's own protocol: the service must return the benchmark's dataset arrays
        ask.append(src["protocol"])
        ref_q.append(None)
        what.append("public row protocol")
        # (2) restarts from public trajectories: no event (trajectory key), and the store key of an interventional row with its events
        rq = dict(src["protocol"], t_end=round(0.25 * T, 9), r0={"kind": "restart", "key": src["key"], "t": t_mid})
        ask.append(rq)
        ref_q.append(dict(rq, r0={"kind": "restart", "key": src["meta"]["store_key"], "t": t_mid}))
        what.append("restart from a public trajectory (recomputed source)")
        if evented:
            ev = evented[0]
            q2 = dict(ev["protocol"], r0={"kind": "restart", "key": ev["meta"]["store_key"], "t": t_mid})
            ask.append(q2)
            ref_q.append(q2)
            what.append(f"restart from a public store key with the row's own events ({ev['family']})")
        # (3) a fresh protocol (another public parameter draw)
        fq = dict(src["protocol"], params_seed=int(src["protocol"]["params_seed"]) + 1)
        ask.append(fq)
        ref_q.append(fq)
        what.append("fresh protocol")
        real_row = None
        if real_dir is not None:
            rrows = [json.loads(x) for x in (real_dir / "index.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
            real_row = next(r for r in rrows if r["split"] == "train" and not r["protocol"]["events"] and r["protocol"]["r0"]["kind"] == "rest")
            rdt, rT = float(real_row["protocol"]["dt"]), float(real_row["protocol"]["t_end"])
            # (4) a real mechanism row's own protocol (the public real data were built on Modal) and a restart from it
            ask.append(real_row["protocol"])
            ref_q.append(None)
            what.append("real mechanism: public row protocol")
            ask.append(dict(real_row["protocol"], t_end=round(0.25 * rT, 9),
                            r0={"kind": "restart", "key": real_row["key"], "t": round(round(0.5 * rT / rdt) * rdt, 9)}))
            ref_q.append(None)
            what.append("real mechanism: restart from a public trajectory (recomputed source)")
        res = client.run(ask, timeout=3600, poll=0.2)
        rec["service_items"] = [{"what": w, "ok": r["ok"], "error": r.get("error")} for w, r in zip(what, res, strict=True)]
        rec["public_sources_recomputed"] = server.n_sources_recomputed
        rec["ledger"] = client.ledger()
    finally:
        stop.set()
        pool.shutdown()
    rec["container_stopped"] = not pool.running()
    # 3. the benchmark's own computations: dataset arrays and SimContext on the build's store, in the image
    checks = {}
    with np.load(bench_dir / "traj" / f"{src['key']}.npz", allow_pickle=False) as z:
        checks["public row protocol == dataset arrays"] = bool(res[0]["ok"]) and all(np.array_equal(res[0][k], z[k]) for k in ("t", "x", "u", "y"))
    if real_row is not None:
        i_real = what.index("real mechanism: public row protocol")
        with np.load(real_dir / "traj" / f"{real_row['key']}.npz", allow_pickle=False) as z:
            checks["real mechanism: public row protocol == dataset arrays (built on Modal)"] = bool(res[i_real]["ok"]) and all(
                np.array_equal(res[i_real][k], z[k]) for k in ("t", "x", "u", "y"))
        checks["real mechanism: restart from a public trajectory served"] = bool(res[i_real + 1]["ok"])
        rec["real_system"] = real_sid
    ref_protocols = [q for q in ref_q if q is not None]
    (work / "reference_requests.json").write_text(json.dumps({"internal": internal, "protocols": [P.validate(q) for q in ref_protocols]}),
                                                  encoding="utf-8")
    _docker_image_run(work, REFERENCE, [])
    with np.load(work / "reference.npz", allow_pickle=False) as z:
        j = 0
        for i, q in enumerate(ref_q):
            if q is None:
                continue
            checks[f"{what[i]} == benchmark SimContext"] = bool(res[i]["ok"]) and all(np.array_equal(res[i][k], z[f"i{j}_{k}"])
                                                                                     for k in ("t", "x", "u", "y"))
            j += 1
    rec["checks"] = checks
    if args.compare_modal:
        try:
            rec["modal_comparison"] = _compare_modal(sid, bench_dir)
        except Exception as e:  # noqa: BLE001
            rec["modal_comparison"] = {"error": f"{type(e).__name__}: {e}"[:500]}
    mc = rec.get("modal_comparison") or {}
    modal_ok = (mc.get("image_rows_in_modal") is True and mc.get("same_store_keys") is True and mc.get("same_protocols") is True
                and bool(mc.get("arrays_equal")) and all(mc["arrays_equal"].values()))
    rec["passed"] = (bool(checks) and all(checks.values()) and rec["public_sources_recomputed"] >= 1
                     and all(x["ok"] for x in rec["service_items"]) and (not args.compare_modal or modal_ok))
    rec["wall_s"] = round(time.time() - t0, 1)
    SELFTEST_OUT.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: rec[k] for k in ("system", "checks", "public_sources_recomputed", "passed", "wall_s")}, indent=1))
    if args.compare_modal:
        print(json.dumps(rec["modal_comparison"], indent=1))
    return 0 if rec["passed"] else 1


def cmd_build_image(args) -> int:
    from brainir_causal.isolation import docker_exe, sandbox_image
    exe = docker_exe()
    pinned = sandbox_image()
    r = subprocess.run([exe, "image", "inspect", "brainir-p4-sandbox:1", "--format", "{{.Id}}"], capture_output=True, text=True, timeout=120, check=False)
    if r.stdout.strip() != pinned:
        raise SystemExit(f"brainir-p4-sandbox:1 is {r.stdout.strip() or 'missing'}, not the pinned {pinned}: refusing to build on it")
    d = ROOT / "docker" / "p4simservice"
    b = subprocess.run([exe, "build", "-t", "brainir-p4-simsvc:1", str(d)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=3600, check=False)
    if b.returncode != 0:
        raise SystemExit(f"docker build failed:\n{b.stdout[-3000:]}\n{b.stderr[-3000:]}")
    img = subprocess.run([exe, "image", "inspect", "brainir-p4-simsvc:1", "--format", "{{.Id}} {{.Size}}"], capture_output=True, text=True,
                         timeout=120, check=True).stdout.split()
    freeze = subprocess.run([exe, "run", "--rm", "--network", "none", "brainir-p4-simsvc:1", "cat", "/opt/p4sandbox/pip-freeze-simsvc.txt"],
                            capture_output=True, text=True, timeout=300, check=True).stdout
    base_freeze = subprocess.run([exe, "run", "--rm", "--network", "none", "brainir-p4-sandbox:1", "cat", "/opt/p4sandbox/pip-freeze.txt"],
                                 capture_output=True, text=True, timeout=300, check=True).stdout
    added = sorted(set(freeze.split()) - set(base_freeze.split()))
    removed = sorted(set(base_freeze.split()) - set(freeze.split()))
    if removed or [a for a in added if not a.lower().startswith("duckdb==")]:
        raise SystemExit(f"the worker image changed other packages: added {added}, removed {removed}")
    rec = {"tag": "brainir-p4-simsvc:1", "id": img[0], "size_bytes": int(img[1]), "base": {"tag": "brainir-p4-sandbox:1", "id": pinned},
           "added": added, "built_utc": _utc(),
           "notes": "Simulation-service workers only (brainir_causal.simdocker; never an agent image). The pinned sandbox stack plus duckdb "
                    "(--no-deps) for the real engine's graph loader; every other package identical to the base (checked by pip freeze)."}
    (d / "image.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rec, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The developers' simulation service of a room, on the reference platform.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("start", "status", "stop"):
        s = sub.add_parser(name)
        s.add_argument("--room", choices=sorted(ROOMS), default="clean")
        s.add_argument("--room-dir", default=None, help="override the room directory (tests / scratch rooms)")
        if name == "start":
            s.add_argument("--budget", type=int, default=3000)
            s.add_argument("--modal", action="store_true", help="real FULL networks through Modal (restart sources from the volume store)")
            s.add_argument("--docker-workers", type=int, default=4)
            s.add_argument("--docker-cpus", type=float, default=4.0)
            s.add_argument("--docker-mem-gb", type=int, default=8)
            s.add_argument("--start-timeout", type=float, default=1200.0)
    sub.add_parser("build-image")
    t = sub.add_parser("selftest")
    t.add_argument("--system", default=None)
    t.add_argument("--compare-modal", action="store_true")
    args = ap.parse_args(argv)
    return {"start": cmd_start, "status": cmd_status, "stop": cmd_stop, "selftest": cmd_selftest, "build-image": cmd_build_image}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
