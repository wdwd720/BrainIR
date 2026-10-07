"""Run test suites on Modal, sharded, on the pinned Linux stack (ORCHESTRATOR SIDE; research/phase4/PREFREEZE_TODO.md items 3 / 14).

    uv run --no-sync --project phase4 python scripts/p4/modal_pytest.py --suite phase4 [--files a.py,b.py] [--chunk 8] [--marker EXPR]
    uv run --no-sync --project phase4 python scripts/p4/modal_pytest.py --suite generator [--chunk 4]
        [--cpu 8] [--mem-gb 32] [--timeout-s 5400] [--out <json>]

The host machine is shared with agents and the user's services, and a full local run of the Phase 4 suite has been killed for memory.
So the suites run here: every test FILE is collected in its own container, its test nodes are cut into chunks of --chunk nodes, and
every chunk runs in its own container (`python -m pytest <node ids> -p no:cacheprovider`), all at once (Modal's ~100 containers are
the limit). Longest files first (the slowest file's chunks are submitted first).

Image: `p4modal.images.full_image` (the pinned numerical stack, CPU pins, python 3.12, the repository's brainir / brainir_state /
brainir_causal code and the previous public bundle) + pytest at the sandbox image's version + the repository parts the tests read:
phase4/tests, scripts/p4, scripts/p4agent, scripts/p4config, scripts/make_phase4_cleanroom.py, research/phase4, docker (image records)
and benchmarks/causal_state_v1 (incl. the hash-locked generator and its tests). Nothing answer-bearing of Phases 1-3 is uploaded.

Suites: `phase4` = phase4/tests (from /repo/phase4); `generator` = benchmarks/causal_state_v1/generator/tests (from the generator
directory, the delivered layout). Platform-bound tests (the host guard's Windows path rules, NTFS ACLs, the local Docker pool) cannot
pass on Linux; the result lists every failing node with its error line, and the orchestrator runs those files on the Windows host
(the record says which). The JSON result: per chunk {file, nodes, rc, counts, seconds, failures, tail}; totals; files by outcome.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

PYTEST = "pytest==9.1.1"                     # the sandbox image's pytest (docker/p4sandbox/image.json)
DIRS = {"phase4/tests": "/repo/phase4/tests", "scripts/p4": "/repo/scripts/p4", "scripts/p4agent": "/repo/scripts/p4agent",
        "scripts/p4config": "/repo/scripts/p4config", "research/phase4": "/repo/research/phase4", "docker": "/repo/docker",
        "benchmarks/causal_state_v1": "/repo/benchmarks/causal_state_v1"}
FILES = {"scripts/make_phase4_cleanroom.py": "/repo/scripts/make_phase4_cleanroom.py", "phase4/pyproject.toml": "/repo/phase4/pyproject.toml"}
SUITES = {"phase4": ("/repo/phase4", "tests", ROOT / "phase4" / "tests"),
          "generator": ("/repo/benchmarks/causal_state_v1/generator", "tests", ROOT / "benchmarks" / "causal_state_v1" / "generator" / "tests")}
COUNT = re.compile(r"(\d+) (passed|failed|skipped|error|errors|xfailed|xpassed|deselected)")
#: phase4 test files that run on the WINDOWS HOST, never here (each with its reason); `--include-host-only` overrides for diagnosis
HOST_ONLY = {
    "test_guard_p4.py": "the host guard's Windows path rules and _winapi",
    "test_room_builder.py": "room builder scans with Windows paths and _winapi",
    "test_room_acl.py": "NTFS ACLs",
    "test_eval_isolation_docker.py": "the local Docker daemon (the agents' sandbox image)",
    "test_runguard_sandbox.py": "the runner's local Docker sandbox transport",
    "test_realsim.py": "bit-identity against the earlier engine on records held with that phase's hidden data (never uploaded)",
    "test_systems_store_data.py": "reads the earlier phase's hidden system records (never uploaded)",
}
#: run these on the host ONE AT A TIME under the memory guard: scripts/p4/host_tests_guarded.py (the user's local-resource rule)
MAX_WAVES = 24                               # host-gate re-submissions (an AVX-512 host refuses; LOG P3-D26 / P4-D32)


def _image():
    from brainir_causal.p4modal import images
    img = images.full_image(gpu=False, extra_pip=[PYTEST])
    ignore = images.IGNORE + ["**/.pytest_cache/**", "**/hidden/salt*", "**/*.tmp.npz"]
    for rel, dest in DIRS.items():
        img = img.add_local_dir(str(ROOT / rel), dest, ignore=ignore)
    for rel, dest in FILES.items():
        img = img.add_local_file(str(ROOT / rel), dest)
    return img


def _counts(text: str) -> dict:
    last = [ln for ln in text.splitlines() if re.search(r"\b(passed|failed|error|skipped|no tests ran)\b", ln)]
    out: dict = {}
    for n, k in COUNT.findall(last[-1] if last else ""):
        out["errors" if k.startswith("error") else k] = int(n)
    return out


def _failures(text: str) -> list[str]:
    """The short-summary lines (FAILED / ERROR node - message) of a pytest run with -rfE."""
    return [ln[:400] for ln in text.splitlines() if ln.startswith(("FAILED ", "ERROR "))]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", choices=sorted(SUITES), default="phase4")
    ap.add_argument("--files", default="", help="comma-separated test file names (default: every test_*.py of the suite)")
    ap.add_argument("--chunk", type=int, default=10, help="test nodes per container")
    ap.add_argument("--marker", default="not modal", help="pytest -m expression ('' for none)")
    ap.add_argument("--cpu", type=float, default=32.0)          # large containers land on gated (admissible) hosts far more often
    ap.add_argument("--mem-gb", type=int, default=64)
    ap.add_argument("--timeout-s", type=int, default=5400)
    ap.add_argument("--out", default="")
    ap.add_argument("--include-host-only", action="store_true", help="also run the HOST_ONLY files here (diagnosis only)")
    args = ap.parse_args(argv)
    import modal

    cwd, tdir, local_tdir = SUITES[args.suite]
    files = [f for f in args.files.split(",") if f] or sorted(p.name for p in local_tdir.glob("test_*.py"))
    host_only = sorted(f for f in files if args.suite == "phase4" and f in HOST_ONLY and not args.include_host_only)
    files = [f for f in files if f not in host_only]
    app = modal.App(f"brainir-p4-pytest-{args.suite}")
    marker = ["-m", args.marker] if args.marker else []

    @app.function(image=_image(), cpu=args.cpu, memory=args.mem_gb * 1024, timeout=args.timeout_s, max_containers=100,
                  serialized=True, name="p4_pytest")
    def run(job: dict) -> dict:
        import os
        import subprocess
        import time as _t
        t0 = _t.time()
        from brainir_causal.p4modal import gate as _g
        if not _g.admissible():                  # gated code paths refuse this host: re-submitted elsewhere by the driver
            _g.refusal(_g.this_host())           # and this container stops taking inputs, so the retry lands on a fresh host
            return {"refused": True, "file": job["file"], "cpu": _g.this_host().get("model")}
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        if job["kind"] == "collect":
            r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *job["marker"],
                                f"{job['tdir']}/{job['file']}"], cwd=job["cwd"], capture_output=True, text=True, env=env, timeout=1800)
            nodes = [ln.strip() for ln in r.stdout.splitlines() if "::" in ln and not ln.startswith(("=", " "))]
            return {"file": job["file"], "rc": r.returncode, "nodes": nodes, "tail": (r.stdout[-3000:] + r.stderr[-3000:]) if not nodes else ""}
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "-rfE", *job["marker"],
                            *job["nodes"]], cwd=job["cwd"], capture_output=True, text=True, env=env, timeout=job["timeout"])
        text = r.stdout + "\n" + r.stderr
        return {"file": job["file"], "nodes": job["nodes"], "rc": r.returncode, "counts": _counts(r.stdout), "failures": _failures(r.stdout),
                "seconds": round(_t.time() - t0, 1), "tail": text[-5000:] if r.returncode not in (0, 5) else ""}

    t0 = time.time()
    with modal.enable_output(), app.run() as run_ctx:
        def gated_map(jobs_in):
            """run.map with host-gate re-submission (results in input order)."""
            out, todo, waves = [None] * len(jobs_in), list(range(len(jobs_in))), 0
            while todo and waves < MAX_WAVES:
                waves += 1
                got = list(run.map([jobs_in[i] for i in todo], return_exceptions=True))
                nxt = []
                for i, r in zip(todo, got):
                    if isinstance(r, dict) and r.get("refused"):
                        nxt.append(i)
                    else:
                        out[i] = r
                todo = nxt
            for i in todo:
                out[i] = RuntimeError(f"refused by the host gate in {MAX_WAVES} waves")
            return out

        cols = gated_map([{"kind": "collect", "file": f, "cwd": cwd, "tdir": tdir, "marker": marker} for f in files])
        jobs, collect_problems = [], []
        for c in cols:
            if isinstance(c, Exception) or not c.get("nodes"):
                collect_problems.append(c if isinstance(c, dict) else {"error": repr(c)[:500]})
                continue
            nodes = c["nodes"]
            for i in range(0, len(nodes), args.chunk):
                jobs.append({"kind": "run", "file": c["file"], "cwd": cwd, "marker": marker, "nodes": nodes[i: i + args.chunk],
                             "timeout": args.timeout_s - 120})
        # longest first: the files with the most nodes (a proxy until timings exist) lead the submission order
        size = {c["file"]: len(c["nodes"]) for c in cols if isinstance(c, dict) and c.get("nodes")}
        jobs.sort(key=lambda j: -size.get(j["file"], 0))
        res = gated_map(jobs)
        app_id = getattr(run_ctx, "app_id", None)
    chunks, totals, by_file = [], {}, {}
    for j, r in zip(jobs, res):
        if isinstance(r, Exception):
            r = {"file": j["file"], "nodes": j["nodes"], "rc": -1, "counts": {}, "failures": [f"INFRA {type(r).__name__}: {str(r)[:300]}"],
                 "seconds": None, "tail": ""}
        chunks.append(r)
        for k, v in r["counts"].items():
            totals[k] = totals.get(k, 0) + v
        f = by_file.setdefault(r["file"], {"failed_nodes": [], "ok": True, "seconds": 0.0})
        f["seconds"] += r["seconds"] or 0.0
        if r["rc"] not in (0, 5) or r["failures"]:
            f["ok"] = False
            f["failed_nodes"] += r["failures"] or [f"rc {r['rc']} (see tail)"]
    rec = {"suite": args.suite, "app_id": app_id, "wall_s": round(time.time() - t0, 1), "files": len(files), "chunks": len(jobs),
           "totals": totals, "collect_problems": collect_problems,
           "files_failing": {f: v["failed_nodes"] for f, v in sorted(by_file.items()) if not v["ok"]},
           "files_passing": sorted(f for f, v in by_file.items() if v["ok"]), "per_chunk": chunks,
           "resources": {"cpu": args.cpu, "mem_gb": args.mem_gb, "chunk": args.chunk}, "marker": args.marker,
           "host_only": {f: HOST_ONLY[f] for f in host_only},
           "host_command": ("uv run --no-sync --project phase4 python scripts/p4/host_tests_guarded.py "
                            + " ".join(host_only)) if host_only else None}
    out = Path(args.out) if args.out else None
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: rec[k] for k in ("suite", "app_id", "wall_s", "files", "chunks", "totals", "files_failing")}, indent=1)[:12000])
    print(f"collect problems: {len(collect_problems)}" + (f" {json.dumps(collect_problems)[:3000]}" if collect_problems else ""))
    if host_only:
        print(f"{len(host_only)} host-only files NOT run here; run on the Windows host:\n  {rec['host_command']}")
    return 0 if not rec["files_failing"] and not collect_problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
