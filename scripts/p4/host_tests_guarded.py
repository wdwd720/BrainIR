"""Run the HOST-BOUND test files one at a time under a hard memory guard (ORCHESTRATOR SIDE; the user's local-resource rule: the PC
holds one agent sandbox plus orchestration; everything equivalent runs on Modal via scripts/p4/modal_pytest.py).

    uv run --no-sync --project phase4 python scripts/p4/host_tests_guarded.py [files...]      # default: modal_pytest.HOST_ONLY
        [--min-free-start-gb 8] [--kill-below-gb 6] [--no-wait-sandbox] [--max-wait-s 21600] [--out DIR]

For each file, in order:
1. WAIT until the host has at least --min-free-start-gb of free RAM and (unless --no-wait-sandbox) no agent sandbox container
   (`p4sbx-*`) is running; give up on the file after --max-wait-s ("not started", never a pass).
2. RUN `python -m pytest -q -p no:cacheprovider -rfE phase4/tests/<file>` alone, its output to a log file, and poll the free RAM every
   second. If it falls below --kill-below-gb, the whole pytest process tree is killed and the file is recorded "interrupted by the
   memory guard": never a pass, to be rerun when memory allows.
3. RECORD <out>/<file>.json: status (passed / failed / no tests / interrupted by the memory guard / not started), return code, pytest
   counts, start / wait / run seconds, the minimum free RAM observed, and the log's tail; <out>/summary.json covers the run.
Exit code: 0 all passed; 1 a file failed; 3 a file was interrupted or not started (nothing failed).
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "phase4" / "tests"
COUNT = re.compile(r"(\d+) (passed|failed|skipped|error|errors|xfailed|xpassed|deselected)")


# ------------------------------------------------------------------------------------------------ probes (injectable in tests)
def free_ram_gb() -> float:
    """The host's available physical memory in GiB (Windows: GlobalMemoryStatusEx; POSIX: MemAvailable)."""
    if sys.platform == "win32":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            raise OSError("GlobalMemoryStatusEx failed")
        return st.ullAvailPhys / 1024 ** 3
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024 ** 2
    raise OSError("no MemAvailable in /proc/meminfo")


def agent_sandbox_running() -> bool:
    """True when an agent sandbox container (p4sbx-*) is running. A Docker that does not answer runs no sandbox."""
    try:
        r = subprocess.run(["docker", "ps", "--filter", "name=p4sbx-", "--format", "{{.Names}}"], capture_output=True, text=True,
                           timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and any(n.strip().startswith("p4sbx-") for n in r.stdout.splitlines())


def pytest_command(test_file: str) -> list[str]:
    return [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfE", str(TESTS / test_file)]


def kill_tree(proc: subprocess.Popen) -> None:
    """Kill the process and every child (Windows: taskkill /T; POSIX: the process group)."""
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=60)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


def _counts(text: str) -> dict:
    last = [ln for ln in text.splitlines() if re.search(r"\b(passed|failed|error|skipped|no tests ran)\b", ln)]
    out: dict = {}
    for n, k in COUNT.findall(last[-1] if last else ""):
        out["errors" if k.startswith("error") else k] = int(n)
    return out


# ------------------------------------------------------------------------------------------------ the guarded run of one file
def run_one(test_file: str, out_dir: Path, *, min_free_start_gb: float = 8.0, kill_below_gb: float = 6.0, wait_sandbox: bool = True,
            max_wait_s: float = 6 * 3600, poll_s: float = 1.0, start_poll_s: float = 15.0, free_gb=free_ram_gb,
            sandbox_running=agent_sandbox_running, command_for=pytest_command, now=time.monotonic, sleep=time.sleep) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rec: dict = {"file": test_file, "min_free_start_gb": min_free_start_gb, "kill_below_gb": kill_below_gb}
    t0 = now()
    while True:                                           # 1. wait for memory (and for no agent sandbox)
        free = free_gb()
        busy = wait_sandbox and sandbox_running()
        if free >= min_free_start_gb and not busy:
            break
        if now() - t0 >= max_wait_s:
            rec.update(status="not started", reason=f"free RAM {free:.1f} GB" + (", an agent sandbox is running" if busy else ""),
                       wait_s=round(now() - t0, 1))
            return _write(out_dir, rec)
        sleep(start_poll_s)
    rec["wait_s"] = round(now() - t0, 1)
    rec["free_gb_at_start"] = round(free, 2)
    log = out_dir / f"{Path(test_file).stem}.log"
    t1 = now()
    ram_min = free
    killed = False
    with open(log, "wb") as fh:                           # 2. run alone, polling the free RAM
        kw = {"start_new_session": True} if sys.platform != "win32" else {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
        proc = subprocess.Popen(command_for(test_file), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT,
                                env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}, **kw)
        while proc.poll() is None:
            free = free_gb()
            ram_min = min(ram_min, free)
            if free < kill_below_gb:
                kill_tree(proc)
                killed = True
                break
            sleep(poll_s)
    text = log.read_text(encoding="utf-8", errors="replace")
    rec.update(run_s=round(now() - t1, 1), ram_min_gb=round(ram_min, 2), rc=proc.returncode, counts=_counts(text), log=log.name,
               tail=text[-2000:])
    if killed:
        rec["status"] = "interrupted by the memory guard"
    elif proc.returncode == 0:
        rec["status"] = "passed"
    elif proc.returncode == 5:
        rec["status"] = "no tests"
    else:
        rec["status"] = "failed"
    return _write(out_dir, rec)


def _write(out_dir: Path, rec: dict) -> dict:
    (out_dir / f"{Path(rec['file']).stem}.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--min-free-start-gb", type=float, default=8.0)
    ap.add_argument("--kill-below-gb", type=float, default=6.0)
    ap.add_argument("--no-wait-sandbox", action="store_true")
    ap.add_argument("--max-wait-s", type=float, default=6 * 3600)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    files = args.files
    if not files:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from modal_pytest import HOST_ONLY
        files = list(HOST_ONLY)
    out = Path(args.out) if args.out else ROOT / "research" / "phase4" / "host_tests" / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    recs = []
    for f in files:
        r = run_one(f, out, min_free_start_gb=args.min_free_start_gb, kill_below_gb=args.kill_below_gb,
                    wait_sandbox=not args.no_wait_sandbox, max_wait_s=args.max_wait_s)
        recs.append(r)
        print(f"{r['status']:32s} {f}  {json.dumps(r.get('counts', {}))}  ram_min {r.get('ram_min_gb')} GB", flush=True)
    summ = {"out": str(out), "files": [{k: r.get(k) for k in ("file", "status", "rc", "counts", "run_s", "ram_min_gb")} for r in recs]}
    (out / "summary.json").write_text(json.dumps(summ, indent=1) + "\n", encoding="utf-8", newline="\n")
    if any(r["status"] == "failed" for r in recs):
        return 1
    return 0 if all(r["status"] in ("passed", "no tests") for r in recs) else 3


if __name__ == "__main__":
    raise SystemExit(main())
