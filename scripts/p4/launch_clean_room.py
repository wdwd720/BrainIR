"""Post-freeze runbook: clean room, services and developers in one command (ORCHESTRATOR SIDE; research/phase4/CRITICAL_PATH_PLAN.md
stage 1). Refuses to run before the benchmark freeze.

    uv run --no-sync --project phase4 python scripts/p4/launch_clean_room.py [--developers li,sy,nn,od,ko,is,ad,bl] [--dry-run]

Steps (each logged to research/phase4/CLEAN_ROOM_LAUNCH.json; a failing step stops the run):
1. check the benchmark lock (`freeze_benchmark_p4.py --check` must pass: the room is built from the frozen benchmark only);
2. build the clean room (`make_phase4_cleanroom.py --room clean --build`), then `--check` and `--audit`;
3. in parallel: seed the remote runner's dev-data volume server-side (`devdata_seed.py`) and then verify / complete it against the
   room's data/ (`devrun4.py sync-data`); start the simulation service on the reference platform (`simservice_docker.py start --room
   clean --modal`);
4. start the remote runner's daemon (`devrun4.py daemon`, detached);
5. launch every developer as its own isolated session (`scripts/p4agent/launch.py --name dev_<prefix> --scratch <prefix>`, prompt =
   agent_prompts/_common.txt + agent_prompts/<prefix>.txt, 2 CPUs / 3 GB sandbox, detached) through a MEMORY-GATED QUEUE (the
   machine owner's rule, 2026-09-27/28: the PC holds one agent sandbox plus orchestration; LOG P4-D64): the next developer starts
   only while fewer than --max-sessions developer sessions run and the host has at least --min-free-gb GB free; the runbook polls
   every 60 s until every developer has started. All sessions share the machine's single sandbox slot (the sandbox wrapper), so
   their heavy work goes to the remote runner.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UV = os.environ.get("UV_EXE") or str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" /
                                     "astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe" / "uv.exe")
ROOM = Path(r"C:\Dev\BrainIR_p4clean")
AUDIT = Path(r"C:\Dev\BrainIR_p4audit")
PROMPTS = ROOT / "research" / "phase4" / "contracts" / "agent_prompts"
RECORD = ROOT / "research" / "phase4" / "CLEAN_ROOM_LAUNCH.json"
DEVELOPERS = ("li", "sy", "nn", "od", "ko", "is", "ad", "bl")


def py(*args: str) -> list[str]:
    return [UV, "run", "--no-sync", "--project", str(ROOT / "phase4"), "python", *args]


def run(step: str, cmd: list[str], rec: dict, timeout: float = 7200, dry: bool = False) -> None:
    t0 = time.time()
    if dry:
        rec["steps"].append({"step": step, "cmd": cmd[4:], "dry_run": True})
        return
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    rec["steps"].append({"step": step, "cmd": cmd[4:], "rc": r.returncode, "s": round(time.time() - t0, 1),
                         "tail": (r.stdout[-1500:] + r.stderr[-1500:])})
    if r.returncode != 0:
        RECORD.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
        raise SystemExit(f"step {step} failed (rc {r.returncode}); see {RECORD}")


def detach(step: str, cmd: list[str], log: Path, rec: dict, dry: bool = False):
    if dry:
        rec["steps"].append({"step": step, "cmd": cmd[4:], "detached": True, "dry_run": True})
        return None
    fh = open(log, "ab")
    p = subprocess.Popen(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT,
                         env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"},
                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    rec["steps"].append({"step": step, "cmd": cmd[4:], "detached": True, "pid": p.pid, "log": str(log)})
    return p


def free_gb() -> float:
    """The host's available physical memory (the host test guard's measurement)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("p4_host_guard", ROOT / "scripts" / "p4" / "host_tests_guarded.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return float(mod.free_gb())


def gated_queue(devs: list[str], start, *, max_sessions: int, min_free_gb: float, poll_s: float = 60.0, settle_s: float = 30.0,
                free=free_gb, sleep=time.sleep, log=print) -> list[dict]:
    """Start `start(d)` (returns a Popen-like object with poll()) for each developer in order, never more than max_sessions alive and
    only while free() >= min_free_gb; returns one record per start (developer, time, free GB, sessions alive before it)."""
    alive: list = []
    out: list[dict] = []
    todo = list(devs)
    while todo:
        alive = [p for p in alive if p.poll() is None]
        fg = free()
        if len(alive) < max_sessions and fg >= min_free_gb:
            d = todo.pop(0)
            out.append({"developer": d, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "free_gb": round(fg, 2),
                        "sessions_alive_before": len(alive)})
            alive.append(start(d))
            log(f"started developer {d} ({len(alive)} sessions, {fg:.1f} GB free)")
            if todo:
                sleep(settle_s)             # let the new session settle before the next memory reading
            continue
        log(f"queue: {len(todo)} developer(s) waiting ({len(alive)} sessions alive, {fg:.1f} GB free; need fewer than {max_sessions} "
            f"sessions and >= {min_free_gb} GB)")
        sleep(poll_s)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--developers", default=",".join(DEVELOPERS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sbx-mem-gb", default="3")
    ap.add_argument("--max-sessions", type=int, default=4, help="developer sessions alive at once (memory-gated queue)")
    ap.add_argument("--min-free-gb", type=float, default=8.0, help="start the next developer only with this much free RAM")
    # the simulation service's ONE local worker container (synthetic systems and real mechanisms; real full networks on Modal): capped
    # small under the machine owner's rule (LOG P4-D64 / P4-D65); its measured footprint is in SIMSERVICE_DOCKER_SELFTEST.json
    ap.add_argument("--svc-workers", default="1")
    ap.add_argument("--svc-cpus", default="2")
    ap.add_argument("--svc-mem-gb", default="3")
    args = ap.parse_args(argv)
    devs = [d for d in args.developers.split(",") if d]
    rec = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "developers": devs, "steps": []}
    run("benchmark lock check", py("scripts/p4/freeze_benchmark_p4.py", "--check"), rec, dry=args.dry_run)
    run("build clean room", py("scripts/make_phase4_cleanroom.py", "--room", "clean", "--build"), rec, timeout=4 * 3600, dry=args.dry_run)
    run("check clean room", py("scripts/make_phase4_cleanroom.py", "--room", "clean", "--check"), rec, timeout=3600, dry=args.dry_run)
    run("audit clean room", py("scripts/make_phase4_cleanroom.py", "--room", "clean", "--audit"), rec, timeout=3600, dry=args.dry_run)

    def data_volume():
        run("seed dev-data volume", py("scripts/p4/devdata_seed.py"), rec, timeout=3 * 3600, dry=args.dry_run)
        run("verify dev-data volume", py("scripts/p4/devrun4.py", "sync-data", "--room", str(ROOM)), rec, timeout=3 * 3600,
            dry=args.dry_run)

    def service():
        run("start simulation service", py("scripts/p4/simservice_docker.py", "start", "--room", "clean", "--modal", "--docker-workers",
                                           args.svc_workers, "--docker-cpus", args.svc_cpus, "--docker-mem-gb", args.svc_mem_gb),
            rec, timeout=3600, dry=args.dry_run)
    with ThreadPoolExecutor(2) as ex:
        for f in [ex.submit(data_volume), ex.submit(service)]:
            f.result()
    detach("remote runner daemon", py("scripts/p4/devrun4.py", "daemon", "--room", str(ROOM)), AUDIT / "devrun4_daemon_clean.log", rec,
           dry=args.dry_run)
    common = (PROMPTS / "_common.txt").read_text(encoding="utf-8")

    def start_dev(d):
        prompt = AUDIT / f"prompt_dev_{d}.txt"
        if not args.dry_run:
            prompt.write_text(common + "\n\n" + (PROMPTS / f"{d}.txt").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        return detach(f"developer {d}", py("scripts/p4agent/launch.py", "--name", f"dev_{d}", "--room", str(ROOM), "--prompt-file",
                                           str(prompt), "--model", "opus", "--scratch", d, "--sbx-cpus", "2", "--sbx-mem-gb",
                                           args.sbx_mem_gb), AUDIT / f"dev_{d}_launch.log", rec, dry=args.dry_run)
    if args.dry_run:
        for d in devs:
            start_dev(d)
    else:
        rec["developer_queue"] = gated_queue(devs, start_dev, max_sessions=args.max_sessions, min_free_gb=args.min_free_gb)
    rec["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    RECORD.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"steps": [s["step"] for s in rec["steps"]], "record": str(RECORD)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
