"""Run the Phase 4 test suites LOCALLY on the pinned Linux stack, one test file at a time (ORCHESTRATOR SIDE; the user's directive of
2026-09-28: no further Modal spend; research/phase4/LOCAL_EXECUTION_PLAN.md). The local replacement of scripts/p4/modal_pytest.py:
same suites, same files (modal_pytest.HOST_ONLY stay on the Windows host: scripts/p4/host_tests_guarded.py), same result JSON
(files_passing / files_failing / totals / collect_problems / per-file records), so prefreeze_check.py reads either.

    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py run --memory-gb 4 --cpus 8 scripts/p4/local_pytest.py \
        --suite phase4 [--files a.py,b.py] [--timeout-s 5400] --out research/phase4/local_pytest_phase4.json

Runs inside the pinned driver image (its numerics equal the Modal reference, 15 / 15 self-test items); the container's memory cap is the
hard limit for every file. Each file runs `python -m pytest -q -p no:cacheprovider -o addopts= -rfE -m "not modal" <file>` in a fresh
process, alone; a file already recorded as passing in --out with an unchanged content hash (and unchanged package sources) is skipped
(resume), so an interrupted run continues where it stopped."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p4"))

COUNT = re.compile(r"(\d+) (passed|failed|skipped|error|errors|xfailed|xpassed|deselected)")
SUITES = {"phase4": (ROOT / "phase4", ROOT / "phase4" / "tests"),
          "generator": (ROOT / "benchmarks" / "causal_state_v1" / "generator", ROOT / "benchmarks" / "causal_state_v1" / "generator" / "tests")}


def _counts(text: str) -> dict:
    last = [ln for ln in text.splitlines() if re.search(r"\b(passed|failed|error|skipped|no tests ran)\b", ln)]
    out: dict = {}
    for n, k in COUNT.findall(last[-1] if last else ""):
        out["errors" if k.startswith("error") else k] = int(n)
    return out


def _failures(text: str) -> list[str]:
    return [ln[:400] for ln in text.splitlines() if ln.startswith(("FAILED ", "ERROR "))]


def _code_hash(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for base in paths:
        for f in sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts):
            h.update(f.relative_to(ROOT).as_posix().encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", choices=sorted(SUITES), default="phase4")
    ap.add_argument("--files", default="")
    ap.add_argument("--marker", default="not modal")
    ap.add_argument("--timeout-s", type=int, default=5400)
    ap.add_argument("--out", required=True)
    ap.add_argument("--include-host-only", action="store_true")
    args = ap.parse_args(argv)
    from modal_pytest import HOST_ONLY
    cwd, tdir = SUITES[args.suite]
    files = [f for f in args.files.split(",") if f] or sorted(p.name for p in tdir.glob("test_*.py"))
    host_only = sorted(f for f in files if args.suite == "phase4" and f in HOST_ONLY and not args.include_host_only)
    files = [f for f in files if f not in host_only]
    out_p = ROOT / args.out
    prev = json.loads(out_p.read_text(encoding="utf-8")) if out_p.exists() else {}
    code = _code_hash([ROOT / "phase4" / "src", ROOT / "benchmarks" / "causal_state_v1" / "generator" / "src", ROOT / "scripts" / "p4"])
    per_file: dict = {} if prev.get("code_hash") != code else dict(prev.get("per_file") or {})
    t0 = time.time()

    def save(done: bool) -> dict:
        failing = {f: v["failures"] or [f"rc {v['rc']} (see tail)"] for f, v in per_file.items() if not v["ok"]}
        totals: dict = {}
        for v in per_file.values():
            for k, n in v["counts"].items():
                totals[k] = totals.get(k, 0) + n
        rec = {"suite": args.suite, "runner": "local (pinned Linux image, one file at a time)", "code_hash": code, "complete": done,
               "files": len(files), "files_run": len(per_file), "totals": totals, "collect_problems": [],
               "files_failing": failing, "files_passing": sorted(f for f, v in per_file.items() if v["ok"]), "per_file": per_file,
               "marker": args.marker, "host_only": {f: HOST_ONLY[f] for f in host_only},
               "host_command": ("uv run --no-sync --project phase4 python scripts/p4/host_tests_guarded.py " + " ".join(host_only)) if host_only else None,
               "wall_s": round(time.time() - t0, 1), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
        return rec

    for f in files:
        fh = hashlib.sha256((tdir / f).read_bytes()).hexdigest()[:16]
        old = per_file.get(f)
        if old and old.get("ok") and old.get("file_hash") == fh:
            continue
        marker = ["-m", args.marker] if args.marker else []
        t1 = time.time()
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "-rfE", *marker,
                                f"{tdir.name}/{f}"], cwd=str(cwd), capture_output=True, text=True, timeout=args.timeout_s,
                               env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
            text, rc = r.stdout + "\n" + r.stderr, r.returncode
        except subprocess.TimeoutExpired as e:
            text, rc = f"TIMEOUT after {args.timeout_s} s\n{(e.stdout or '')[-3000:] if isinstance(e.stdout, str) else ''}", -9
        counts = _counts(text if rc != -9 else "")
        fails = _failures(text)
        ok = rc in (0, 5) and not fails
        per_file[f] = {"ok": ok, "rc": rc, "counts": counts, "failures": fails, "seconds": round(time.time() - t1, 1), "file_hash": fh,
                       "tail": "" if ok else text[-5000:]}
        print(f"{'PASS' if ok else 'FAIL'} {f} {counts} {per_file[f]['seconds']} s", flush=True)
        save(False)
    rec = save(True)
    print(json.dumps({k: rec[k] for k in ("suite", "files", "files_run", "totals", "files_failing", "wall_s")})[:6000], flush=True)
    return 0 if not rec["files_failing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
