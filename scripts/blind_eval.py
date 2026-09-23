"""Blind evaluation of the LOCKED Phase 2 method (goal3 sections 27-29; benchmarks/dng100/PROTOCOL.md sections 3-4).

    uv run python scripts/blind_eval.py --reason "first preregistered blind evaluation of brainir_v1"

Every step refuses to continue on failure:
 1. `scripts/method_lock.py check` passes, and the git tag `brainir-v1-preblind` holds the same METHOD_LOCK.json as the tree;
 2. attempt bookkeeping: outputs go to research/phase2/blind_eval/attempt_<k>/; a second attempt for the same lock needs
    --new-attempt (a changed method is a new method version with its own lock, goal3 section 29);
 3. the locked entry runs through the FROZEN clean-room runner on the blind bundle for every locked network, with the locked
    arguments and seed (the runner copies the bundle, strips the environment and sandboxes file access);
 4. FREEZE: prediction hashes, the run record hash and the lock hash are written to FROZEN.json before the evaluator runs;
 5. the frozen evaluator scores all predictions together (`--run-record` re-verifies the hashes; frozen defaults: 16 replicates,
    2 s protocol);
 6. one row is appended to research/phase2/HIDDEN_EVAL_LOG.md.

Nothing produced here may be copied into the Phase 2 clean development directory.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import method_lock  # noqa: E402

RUNNER = ROOT / "benchmarks" / "dng100" / "cleanroom" / "run_method.py"
EVALUATOR = ROOT / "benchmarks" / "dng100" / "evaluator" / "evaluate.py"
OUT_ROOT = ROOT / "research" / "phase2" / "blind_eval"
LOG = ROOT / "research" / "phase2" / "HIDDEN_EVAL_LOG.md"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _tag_lock_matches(tag: str) -> bool:
    proc = subprocess.run(["git", "show", f"{tag}:research/phase2/METHOD_LOCK.json"], cwd=ROOT, capture_output=True)
    if proc.returncode != 0:
        return False
    return proc.stdout.replace(b"\r\n", b"\n") == method_lock.LOCK_PATH.read_bytes().replace(b"\r\n", b"\n")


def _previous_attempts() -> list[dict]:
    out = []
    for d in sorted(OUT_ROOT.glob("attempt_*")):
        f = d / "FROZEN.json"
        if f.exists():
            out.append({"dir": d.name, **json.loads(f.read_text(encoding="utf-8"))})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reason", required=True, help="why this hidden evaluation is run (logged)")
    ap.add_argument("--new-attempt", action="store_true", help="allow another attempt with the SAME lock (e.g. the first crashed)")
    ap.add_argument("--workers", type=int, default=4, help="evaluator worker processes")
    ap.add_argument("--timeout", type=int, default=14400, help="clean-room timeout per network (s)")
    ap.add_argument("--dry-run", action="store_true", help="run steps 1-4 only (no evaluator, nothing logged); for rehearsals")
    args = ap.parse_args(argv)

    problems = method_lock.check(verbose=True)
    if problems:
        print("refusing: the method lock does not verify")
        return 1
    if not _tag_lock_matches(method_lock.TAG):
        print(f"refusing: tag {method_lock.TAG} is missing or holds a different METHOD_LOCK.json")
        return 1
    lock = json.loads(method_lock.LOCK_PATH.read_text(encoding="utf-8"))
    prev = [a for a in _previous_attempts() if a.get("lock_sha256") == lock["lock_sha256"] and not a.get("dry_run")]
    if prev and not args.new_attempt:
        print(f"refusing: {len(prev)} attempt(s) already exist for this lock ({', '.join(a['dir'] for a in prev)}); see goal3 section 29")
        return 1
    k = len(list(OUT_ROOT.glob("attempt_*"))) + 1
    att = OUT_ROOT / (f"attempt_{k:02d}" + ("_dryrun" if args.dry_run else ""))
    runs = att / "runs"
    att.mkdir(parents=True, exist_ok=False)
    rp = lock["run_protocol"]
    cmd = [sys.executable, str(RUNNER), "--method", str(ROOT / rp["entry"]), "--bundle", str(ROOT / rp["bundle"]), "--out", str(runs),
           "--seed", str(rp["seed"]), "--method-args", rp["method_args"], "--timeout", str(args.timeout)]
    for net in rp["networks"]:
        cmd += ["--network", net]
    started = _now()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    (att / "runner_stdout.txt").write_text(proc.stdout[-20000:], encoding="utf-8", newline="\n")
    (att / "runner_stderr.txt").write_text(proc.stderr[-20000:], encoding="utf-8", newline="\n")
    record_path = runs / "run_record.json"
    if proc.returncode != 0 or not record_path.exists():
        print(f"clean-room runner failed (rc {proc.returncode}); see {att}")
        return 1
    record = json.loads(record_path.read_text(encoding="utf-8"))
    preds = {r["network"]: runs / r["prediction"] for r in record["runs"] if r.get("returncode") == 0 and r.get("prediction")}
    failed = [r["network"] for r in record["runs"] if r.get("returncode") != 0 or not r.get("prediction")]
    frozen = {"attempt": k, "dry_run": bool(args.dry_run), "reason": args.reason, "started_utc": started, "frozen_utc": _now(),
              "method": lock["method"]["name"], "method_version": lock["method"]["version"], "lock_sha256": lock["lock_sha256"],
              "source_tree_sha256": lock["source_tree_sha256"], "git_commit": lock["git"]["commit"],
              "bundle_sha256": record["bundle"]["bundle_sha256"], "run_record_sha256": _sha(record_path),
              "predictions": {net: {"file": p.name, "sha256": _sha(p)} for net, p in preds.items()}, "failed_networks": failed,
              "compute": {r["network"]: {"wall_time_s": r.get("wall_time_s")} for r in record["runs"]}}
    (att / "FROZEN.json").write_text(json.dumps(frozen, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"frozen {len(preds)} prediction(s) in {att.relative_to(ROOT)} (failed: {failed or 'none'})")
    if args.dry_run:
        print("dry run: evaluator not invoked, nothing logged")
        return 0
    if not preds:
        return 1
    ev_dir = att / "eval"
    ev_dir.mkdir()
    ecmd = [sys.executable, str(EVALUATOR), *[str(p) for p in preds.values()], "--bundle", str(ROOT / rp["bundle"]), "--out",
            str(ev_dir / "evaluation.json"), "--run-record", str(record_path), "--workers", str(args.workers)]
    eproc = subprocess.run(ecmd, cwd=ROOT, capture_output=True, text=True)
    (ev_dir / "evaluator_stdout.txt").write_text(eproc.stdout[-50000:], encoding="utf-8", newline="\n")
    (ev_dir / "evaluator_stderr.txt").write_text(eproc.stderr[-20000:], encoding="utf-8", newline="\n")
    outcome = "evaluator failed"
    if eproc.returncode == 0 and (ev_dir / "evaluation.json").exists():
        ev = json.loads((ev_dir / "evaluation.json").read_text(encoding="utf-8"))
        parts = []
        for net, r in ev.get("networks", {}).items():
            s, f = r.get("structural", {}), r.get("functional", {})
            parts.append(f"{net}: E-recall {s.get('excitatory_core_recall')}, I-slot {s.get('inhibitory_slot_filled')}, "
                         f"sufficiency pass {f.get('sufficiency_pass')}")
        outcome = "; ".join(parts)
    with open(LOG, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"| {_now()} | blind evaluation attempt {k} (lock `{lock['lock_sha256'][:16]}`) | `{lock['method']['name']}` "
                 f"{lock['method']['version']} | {', '.join(rp['networks'])} | {len(preds)} | {outcome} | {args.reason} |\n")
    print(f"evaluation written to {ev_dir.relative_to(ROOT)}; logged in {LOG.relative_to(ROOT)}")
    return 0 if eproc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
