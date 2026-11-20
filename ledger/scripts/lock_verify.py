"""Post-tag verification of a predictions lock (arms review, finding 2). `lock.py` is frozen and its `check` neither notices a
locked file that git does not track (e.g. a git-ignored parquet) nor an arm without types.csv; either would make the one-shot
scoring refuse. This script checks the TAG, not the working tree:

1. the lock file in the tag equals the working-tree lock file;
2. every file hashed in the lock (arms, gates, reviews, code) is tracked in the tag and its blob hashes to the locked value;
3. every locked arm has types.csv; the prereg lock hash matches;
4. a clean checkout of the tag (temporary git worktree) passes the frozen scoring code's `verify_inputs` for every
   prediction file, against the real predictions lock and a placeholder labels lock (no labels exist; no UNBLIND flag is
   created anywhere: `verify_inputs` takes the flag as an argument).

    uv run --project ledger --no-sync python ledger/scripts/lock_verify.py [--tag ledger-predictions-v1] [--lock LOCK_predictions_v1.json]
Writes research/ledger/<lock stem>.verify.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brainir_ledger import REPO, RESEARCH  # noqa: E402


def git(*args, binary: bool = False):
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout if binary else r.stdout.decode().strip()


def blob_sha(tag: str, path: str) -> str | None:
    try:
        return hashlib.sha256(git("cat-file", "blob", f"{tag}:{path}", binary=True)).hexdigest()
    except RuntimeError:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="ledger-predictions-v1")
    ap.add_argument("--lock", default="LOCK_predictions_v1.json")
    ap.add_argument("--out", default=None, help="report path (default research/ledger/<lock stem>.verify.json)")
    a = ap.parse_args()
    lock_path = RESEARCH / a.lock
    lock_rel = lock_path.relative_to(REPO).as_posix()
    rec = json.loads(lock_path.read_text(encoding="utf-8"))
    out: dict = {"tag": a.tag, "tag_commit": git("rev-list", "-n", "1", a.tag), "lock": lock_rel, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    problems: list[str] = []

    wt_sha = hashlib.sha256(lock_path.read_bytes()).hexdigest()
    if blob_sha(a.tag, lock_rel) != wt_sha:
        problems.append("lock file in the tag differs from the working-tree lock file (or is not in the tag)")
    out["lock_sha256"] = wt_sha

    n_checked = 0
    for sec in ("arms_locked", "gates", "reviews", "code"):
        d = rec.get(sec) or {}
        items = [(k, v) for arm in d.values() for k, v in arm.items()] if sec == "arms_locked" else list(d.items())
        for path, want in items:
            got = blob_sha(a.tag, path)
            n_checked += 1
            if got is None:
                problems.append(f"{sec}: {path} is not tracked in {a.tag}")
            elif got != want:
                problems.append(f"{sec}: {path} in {a.tag} differs from the locked hash")
    out["n_files_checked_in_tag"] = n_checked

    for arm, files in (rec.get("arms_locked") or {}).items():
        if not files:
            problems.append(f"arm {arm} has no files in the lock")
        elif not any(Path(p).name == "types.csv" for p in files):
            problems.append(f"arm {arm} has no types.csv")
    out["arms_locked"] = sorted(rec.get("arms_locked") or {})
    out["arms_not_locked"] = rec.get("arms_not_locked")
    pl = RESEARCH / "LOCK_prereg_v1.json"
    if rec.get("prereg_lock_sha256") and hashlib.sha256(pl.read_bytes()).hexdigest() != rec["prereg_lock_sha256"]:
        problems.append("prereg lock hash differs")

    # clean checkout of the tag -> the TAG's own frozen verify_inputs (run in a subprocess whose import path starts with the
    # checkout, so the scoring code under test is the tagged one), placeholder labels lock
    child = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "import brainir_ledger.scoring.pipeline as P\n"
        "from brainir_ledger.scoring import BlindError\n"
        "a = json.loads(sys.argv[1])\n"
        "mod = str(Path(P.__file__).resolve())\n"
        "if not mod.startswith(str(Path(a['wt']).resolve())):\n"
        "    print(json.dumps({'ok': False, 'error': 'scoring module not imported from the checkout: ' + mod})); raise SystemExit(0)\n"
        "try:\n"
        "    v = P.verify_inputs(a['flag'], Path(a['res']), Path(a['pred']), Path(a['lab']))\n"
        "    print(json.dumps({'ok': True, **v, 'scoring_module_from_checkout': True}))\n"
        "except BlindError as e:\n"
        "    print(json.dumps({'ok': False, 'error': str(e)}))\n"
    )

    tmp = Path(tempfile.mkdtemp(prefix="ledger_lockverify_"))
    wt = tmp / "wt"
    try:
        git("worktree", "add", "--detach", str(wt), a.tag)
        res = tmp / "research"
        lab = tmp / "labels"
        res.mkdir()
        lab.mkdir()
        shutil.copy2(wt / lock_rel, res / lock_path.name)
        (lab / "type_labels.csv").write_text("placeholder\n", encoding="utf-8")
        (lab / "records.jsonl").write_text("{}\n", encoding="utf-8")
        llock = {"labels": {f"research/ledger/labels/{p.name}": hashlib.sha256(p.read_bytes()).hexdigest() for p in lab.iterdir()}}
        (res / "LOCK_labels_v0placeholder.json").write_text(json.dumps(llock), encoding="utf-8")
        flag = {"predictions_lock": lock_path.name, "labels_lock": "LOCK_labels_v0placeholder.json"}
        args = {"wt": str(wt), "flag": flag, "res": str(res), "pred": str(wt / "research" / "ledger" / "predictions"), "lab": str(lab)}
        env = dict(os.environ, PYTHONPATH=str(wt / "ledger" / "src"))
        r = subprocess.run([sys.executable, "-c", child, json.dumps(args)], cwd=tmp, env=env, capture_output=True, text=True)
        try:
            v = json.loads(r.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            v = {"ok": False, "error": f"child failed (exit {r.returncode}): {r.stderr.strip()[-800:]}"}
        out["clean_checkout_verify_inputs"] = v
        if not v.get("ok"):
            problems.append(f"verify_inputs on a clean checkout: {v.get('error')}")
    finally:
        try:
            git("worktree", "remove", "--force", str(wt))
        except RuntimeError:
            pass
        shutil.rmtree(tmp, ignore_errors=True)

    out["problems"] = problems
    out["pass"] = not problems
    dst = Path(a.out) if a.out else RESEARCH / f"{lock_path.stem}.verify.json"
    dst.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": out["pass"], "n_files_checked_in_tag": n_checked, "problems": problems[:10]}, indent=1))
    raise SystemExit(0 if out["pass"] else 1)


if __name__ == "__main__":
    main()
