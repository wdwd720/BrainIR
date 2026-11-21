"""The unblinding gate of run 2 (PREREG v2 S5; RUN2_PROMPT section 8), computed from label files and type names only.

    uv run --project ledger --no-sync python ledger/scripts/gate_v2.py
        run 1 -> research/ledger/gates_v2/UNBLINDING_GATE_run1.json   (before reviews_v2/GATE_CHECKLIST.md exists)
        run 2 -> research/ledger/gates_v2/UNBLINDING_GATE_run2.json   (after the checklist is committed)

Exit 0: all six conditions hold (run 2 only). Exit 1: a condition fails, condition 6 is still pending (run 1), or run 2's
conditions 1-5 differ from run 1's. Exit 2: refused (nothing evaluated, nothing written).

Two runs, each once (PREREG v2 S5.6, L14: "the gate (its script twice, S5.6), runs once. A failed gate ends the collection").
Neither report is ever overwritten (exclusive create). Refusals, from the committed state:
- run 1: refused when the checklist exists or was ever committed (the first run precedes the checklist);
- run 2: refused unless run 1's report exists with conditions 1-5 passing and condition 6 pending (a failed run 1 ends the
  collection), and the checklist exists (run 2 records condition 6);
- a third run is refused (run 2's report exists or was ever committed); so is any run when a report was committed and removed.
Run 2 records run 1's report hash and compares the whole condition 1-5 dicts with run 1's as canonical JSON. They hold no
timestamp of the gate run, and every path inside the temporary checkout is written as `<checkout>`, so nothing volatile is left
to exclude; each condition keeps the SHA-256 of every input it read. Any difference fails the gate.

How it runs. Commit first: the gate refuses while `git status` shows a change or an untracked file under ledger/ or
research/ledger/, or a git-ignored file under research/ledger/ (`git status --ignored`: a clean checkout would lack it). It then
makes ONE clean checkout of HEAD (a temporary `git worktree`, removed at the end, also on error) and evaluates every condition
on that checkout, so the result rests only on committed files; every input file it read is listed with its SHA-256 (this
covers the verification files of L11, which are written after the labels lock). It never reads a prediction score: of the
prediction tables it reads only the `manc_type` column of A1 (condition 5); the lock tools hash files without parsing them.
It prints only counts and pass/fail.

1. Locks (S5.1, L12). In the checkout, with the checkout's own lock tools run by this interpreter: `lock2.py check` on every
   lock (v1: rulebook, predictions, labels v1 (chained from v1.1), labels v1.1; v2: rulebook, label code, scoring, labels,
   predictions if present) and the frozen `lock.py check` on the four v1 locks; a check passes when the tool exits 0.
   lock2.py's amended / snapshot lists and its ignored amendment rows are copied into the report, and so is
   `AMENDMENTS_v2.jsonl` (L12: "the gate report lists every amendment"). The gate also requires, itself:
   - chained lock hashes (top-level `*_lock_sha256`) that match, and on the v2 locks the chains lock2.py writes
     (`REQUIRED_CHAINS`; the labels lock chains the prereg, label-code and scoring locks); an unknown chain key is reported;
   - exactly one commit touching each lock file (`git log --format=%H -- <lock>`: written once, never edited, L12);
   - `utc` of LOCK_labelcode_v2.json and LOCK_scoring_v2.json earlier than the earliest `runs[].start_utc` of the v2 session
     manifests (L12: locked before the first v2 label session). The launcher writes each manifest to
     `~/ledger_rooms/run2/_manifests/<session>.json`; the frozen collector (`labels_collect.collect`, re-pointed by
     labels2_collect.py) copies it verbatim to `labels_v2/sessions/<session>.json`, the committed copy read here (its
     `_status.json` is skipped). No manifest, or a manifest without parseable start times, fails;
   - archive-member keys `<archive>.zip:<member>` of the locks (LOCK_prereg_v1.json `authors_zenodo_configs_pinned`, which
     neither lock tool checks): the member hashed from `<archive>.zip` found under `<data root>/raw/external/` (any depth;
     `brainir.paths.data_root()`), or, when no such archive exists, from the copy `zenodo_remote_zip.py get` extracts to
     `<data root>/raw/external/pugliese_2026_zenodo/<archive stem>/<member>` (the source used is recorded per key). A key with
     neither is a missing archive: the condition fails.
2. Breaches (S5.2, L3). Breach and audit rows: `labels_v2/transcript_audit.json` plus `labels_v2/verify/transcript_audit_verify.json`
   (lists of rows with `session` and `breach`, as `labels2_audit.py` writes them). Sessions that contributed a final record
   (`labels_v2/records.jsonl`):
   - readers: the session prefixes of the final `exp_id`s (`<session>:<record_id>`);
   - atlas (when a final `exp_id` starts with `atlas:`): for each of atlas-map (raw/atlas_map/), atlas-codeA and atlas-codeB
     (raw/pass1/), the session the collector uses: the first of `<base>`, `<base>-r1` that exists and is not breaching
     (`labels2_collect._atlas_session`). If a coder has no such session, or the map has none while a final atlas `exp_id` names a
     mapped type, the atlas records came from a breaching session: the condition fails;
   - second readers / adjudicators: a session folder under raw/pass2/ or raw/adjudication/ whose records.valid.jsonl holds a
     final `exp_id`, except a breaching session ALL of whose final `exp_id`s were also read by a non-breaching session of the
     same pass (the collector drops breaching pass-2 and adjudication sessions: it was excluded and replaced, L3);
   - the verifier: `verifier_session` of `labels_v2/verify/verification.json`.
   Fails if a contributing session breached or has no audit row (L3 kind 4). A literal count (every session folder under
   raw/pass2 and raw/adjudication, every atlas candidate, every audited verifier) is reported beside it, not used.
3. Review and verification (S5.3, L11). `reviews_v2/REVIEW_labels_v2.md` must hold exactly one line `Verdict: <phrase>` whose
   whole phrase is `usable`, `usable with caveats` or `blocked` (case, `*` / backtick emphasis and one trailing full stop are
   ignored; a heading or list marker may precede `Verdict`); usable / usable with caveats pass; blocked, a missing file, no
   verdict line, two or more verdict lines or any other phrase fail. The verification is recomputed, not trusted: from
   `labels_v2/verify/verify_truth.json` and the verifier's collected `labels_v2/verify/raw/<verifier_session>/verification.csv`
   (read by the frozen `labels_collect.read_csv_rows`), an error is a missing row, an empty value, `cannot_verify` or a different
   value (the rule of `labels2_collect.verify_score`); it passes when n > 0, errors * 10 <= n (at most 10 %), n equals the rows
   of `labels_v2/verify/verify_sample.csv` (same exp_ids), `verification.json` states the same n and errors and no blocker, and
   its `verifier_session` is audited non-breaching in `transcript_audit_verify.json`. Every file under `labels_v2/verify/`
   (sample, truth, collected verifier outputs, audit, result) is hashed in the report (L11).
4. Agreement (S5.4): `labels_v2/agreement.json` -> agreement.primary_field_all_values (its `kappa` if it is a dict) >= 0.7.
5. Primary set (S5.5): types of `labels_v2/type_labels.csv` with front in {yes, no}, among the `manc_type` names of
   predictions/A1/types.csv, not in the v2 exposed set (kit_v2/exposed_types.csv + labels_v2/exposed_v2.csv, the scoring's
   own `exposed_set_v2`): at least 20 types, 5 yes, 5 no. A disagreement between the table's `exposed` column and that set is
   reported (the scoring would refuse such a table).
6. Reviewer checklist (S5.6): `reviews_v2/GATE_CHECKLIST.md`; absent -> "pending"; "confirmed" when it holds exactly one verdict
   line and its whole phrase is `confirmed` (same parsing as 3), else "not_confirmed".
"""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "ledger" / "src"))
sys.path.insert(0, str(HERE))
import labels_collect as LC  # noqa: E402  (frozen; only its tolerant CSV reader is used, as labels2_collect.verify_score uses it)

from brainir_ledger.scoring_v2.pipeline_v2 import GATE_REPORTS, exposed_set_v2  # noqa: E402

CHECKLIST_REL = "reviews_v2/GATE_CHECKLIST.md"
LOCKS_V1 = ("LOCK_prereg_v1.json", "LOCK_predictions_v1.json", "LOCK_labels_v1.json", "LOCK_labels_v1_1.json")
LOCKS_V2 = ("LOCK_prereg_v2.json", "LOCK_labelcode_v2.json", "LOCK_scoring_v2.json", "LOCK_labels_v2.json")
LOCKS_IF_PRESENT = ("LOCK_predictions_v2.json",)
CHECKERS = {**{n: ("lock2.py", "lock.py") for n in LOCKS_V1}, **{n: ("lock2.py",) for n in LOCKS_V2 + LOCKS_IF_PRESENT}}
CHAINED = {"prereg_lock_sha256": "LOCK_prereg_v1.json", "labels_v1_lock_sha256": "LOCK_labels_v1.json",
           "prereg_v2_lock_sha256": "LOCK_prereg_v2.json", "labelcode_v2_lock_sha256": "LOCK_labelcode_v2.json",
           "scoring_v2_lock_sha256": "LOCK_scoring_v2.json"}
REQUIRED_CHAINS = {"LOCK_labelcode_v2.json": ("prereg_v2_lock_sha256",), "LOCK_scoring_v2.json": ("prereg_v2_lock_sha256",),
                   "LOCK_labels_v2.json": ("prereg_v2_lock_sha256", "labelcode_v2_lock_sha256", "scoring_v2_lock_sha256"),
                   "LOCK_predictions_v2.json": ("prereg_v2_lock_sha256",)}
LOCKED_BEFORE_SESSIONS = ("LOCK_labelcode_v2.json", "LOCK_scoring_v2.json")
LIST_KEYS = ("changed", "missing", "amended", "snapshot_changed_reported_only")
ZENODO_EXTRACTED = "pugliese_2026_zenodo"  # where `zenodo_remote_zip.py get` writes extracted members
ATLAS_BASES = (("atlas_map", "atlas-map"), ("pass1", "atlas-codeA"), ("pass1", "atlas-codeB"))
VERIFY_COLS = ["exp_id", "quote_found", "front_leg_rhythm", "locator", "comment"]  # as labels2_collect.verify_score reads it
KAPPA_MIN = 0.7
MIN_TYPES, MIN_PER_CLASS = 20, 5
REVIEW_VERDICTS = {"usable": "usable", "usable with caveats": "usable_with_caveats", "blocked": "blocked"}
REVIEW_PASS = ("usable", "usable_with_caveats")
CONDITIONS = ("1_locks", "2_breaches", "3_review_and_verification", "4_kappa", "5_primary_set", "6_reviewer_checklist")
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class GateRefused(RuntimeError):
    """The gate was not evaluated; nothing was written."""


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _is_sha(v) -> bool:
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def _utc(s) -> int | None:
    try:
        return calendar.timegm(time.strptime(s, UTC_FORMAT)) if isinstance(s, str) else None
    except ValueError:
        return None


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[-500:]}")
    return r.stdout


def dirty_paths(repo: Path) -> list[str]:
    try:
        out = _git(repo, "status", "--porcelain", "--untracked-files=all", "--", "ledger", "research/ledger")
    except RuntimeError as e:
        raise GateRefused(f"not a usable git repository: {e}") from None
    return [ln[3:] for ln in out.splitlines() if ln.strip()]


def ignored_paths(repo: Path) -> list[str]:
    """Git-ignored files under research/ledger (`git status --ignored`): a clean checkout lacks them (PREREG v2 S5.1)."""
    try:
        out = _git(repo, "status", "--ignored", "--porcelain", "--", "research/ledger")
    except RuntimeError as e:
        raise GateRefused(f"not a usable git repository: {e}") from None
    return [ln[3:] for ln in out.splitlines() if ln.startswith("!! ")]


def _ever_committed(repo: Path, rel: str) -> bool:
    try:
        return bool(_git(repo, "log", "--format=%H", "--", rel).strip())
    except RuntimeError as e:
        raise GateRefused(f"not a usable git repository: {e}") from None


@contextmanager
def clean_checkout(repo: Path):
    """A temporary `git worktree` of HEAD; removed (and pruned) on exit, also on error."""
    tmp = Path(tempfile.mkdtemp(prefix="ledger_gate_v2_"))
    wt = tmp / "checkout"
    state = {"removed": False}
    try:
        _git(repo, "worktree", "add", "--detach", str(wt), "HEAD")
        state["real_path"] = os.path.realpath(wt)
        yield wt, state
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=repo, capture_output=True, check=False)
        shutil.rmtree(tmp, ignore_errors=True)
        subprocess.run(["git", "worktree", "prune"], cwd=repo, capture_output=True, check=False)
        listed = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=repo, capture_output=True, text=True, check=False).stdout
        state["removed"] = not wt.exists() and state.get("real_path", str(wt)) not in listed and str(wt) not in listed


def _scrub(obj, prefixes: list[str]):
    """Every checkout path in a string (error messages) written as `<checkout>`, the longest prefix first (on macOS both
    /var/... and /private/var/... occur), so that the two runs' conditions compare equal."""
    if isinstance(obj, dict):
        return {k: _scrub(v, prefixes) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_scrub(v, prefixes) for v in obj]
    if isinstance(obj, str):
        for p in prefixes:
            obj = obj.replace(p, "<checkout>")
    return obj


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def _note(inputs: dict, research: Path, p: Path) -> None:
    inputs[f"research/ledger/{p.relative_to(research).as_posix()}"] = sha(p)


def _guarded(fn, failed: dict | None = None) -> dict:
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 - a condition that cannot be evaluated fails; the others still run
        return {**(failed or {}), "pass": False, "error": f"{type(e).__name__}: {e}"[:600]}


# ------------------------------------------------------------------------------------------------------------- 1 locks
def _run_checker(wt: Path, tool: str, lock_name: str, python: str) -> dict:
    r = subprocess.run([python, str(wt / "ledger" / "scripts" / tool), "check", str(wt / "research" / "ledger" / lock_name)],
                       cwd=wt, capture_output=True, text=True, timeout=3600, check=False)
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    try:
        out = json.loads(lines[-1])
    except (IndexError, ValueError):
        return {"exit_code": r.returncode, "pass": False, "error": f"unparsed output: {(r.stdout + r.stderr).strip()[-400:]}"}
    rec = {"exit_code": r.returncode, "n_checked": out.get("n_checked"), "pass": r.returncode == 0}
    for k in LIST_KEYS + ("amendment_rows_ignored",):
        if k in out:
            rec[k] = list(out.get(k) or [])
    if "archive_members_skipped" in out:
        rec["archive_members_skipped"] = out["archive_members_skipped"]
    return rec


def _chain(research: Path, name: str, rec: dict) -> dict:
    ok, bad, unknown = [], [], []
    for k, v in sorted(rec.items()):
        if not (k.endswith("_lock_sha256") and isinstance(v, str)):
            continue
        fname = CHAINED.get(k)
        if fname is None:
            unknown.append(k)
            continue
        p = research / fname
        (ok if p.is_file() and sha(p) == v else bad).append(fname)
    absent = [k for k in REQUIRED_CHAINS.get(name, ()) if not isinstance(rec.get(k), str)]
    return {"verified": ok, "mismatched_or_missing": bad, "required_keys_absent": absent, "unknown_keys_not_checked": unknown}


def _lock_commits(wt: Path, name: str) -> dict:
    """PREREG v2 L12: a lock file is written once and never edited -> exactly one commit touches it."""
    commits = [c for c in _git(wt, "log", "--format=%H", "--", f"research/ledger/{name}").split() if c]
    return {"n_commits": len(commits), "commits": commits, "pass": len(commits) == 1}


def locked_before_sessions(research: Path, inputs: dict) -> dict:
    """PREREG v2 L12: label code and scoring code are locked before the first v2 label session. Session start times: the
    collector's verbatim copies of the launcher manifests, labels_v2/sessions/<session>.json, `runs[].start_utc`."""
    sdir = research / "labels_v2" / "sessions"
    manifests = sorted(p for p in sdir.glob("*.json") if not p.name.startswith("_")) if sdir.is_dir() else []
    starts, problems = [], []
    for p in manifests:
        _note(inputs, research, p)
        try:
            runs = json.loads(p.read_text(encoding="utf-8")).get("runs")
        except (ValueError, AttributeError):
            runs = None
        times = [(_utc(r.get("start_utc")), r.get("start_utc")) if isinstance(r, dict) else (None, None)
                 for r in (runs if isinstance(runs, list) else [])]
        if not times or any(t is None for t, _ in times):
            problems.append(f"{p.name}: runs[].start_utc missing or unparseable")
        starts += [(t, s, p.stem) for t, s in times if t is not None]
    if not manifests:
        problems.append("no v2 session manifest in labels_v2/sessions/ (the collector's copies of the launcher manifests)")
    first = min(starts) if starts else None
    locks = {}
    for name in LOCKED_BEFORE_SESSIONS:
        p = research / name
        try:
            u = json.loads(p.read_text(encoding="utf-8")).get("utc") if p.is_file() else None
        except (ValueError, AttributeError):
            u = None
        t = _utc(u)
        locks[name] = {"lock_utc": u, "pass": t is not None and first is not None and t < first[0]}
    return {"rule": "lock utc earlier than the earliest runs[].start_utc of labels_v2/sessions/*.json (PREREG v2 L12)",
            "earliest_session_start_utc": first[1] if first else None, "earliest_session": first[2] if first else None,
            "n_session_manifests": len(manifests), "locks": locks, "problems": problems,
            "pass": not problems and all(v["pass"] for v in locks.values())}


def archive_members(lock_recs: dict[str, dict], data_root: Path) -> dict:
    """Archive-member keys `<archive>.zip:<member>` (outside the repository; S5.1): hashed from the archive under
    <data root>/raw/external/, else from the member `zenodo_remote_zip.py get` extracted; a key with neither fails."""
    pinned: dict[str, str] = {}
    conflicts: list[str] = []

    def walk(d):
        for k, v in d.items():
            if isinstance(v, dict):
                walk(v)
            elif isinstance(k, str) and ".zip:" in k and _is_sha(v) and pinned.setdefault(k, v) != v:
                conflicts.append(k)
    for rec in lock_recs.values():
        walk(rec)
    data_root = Path(data_root)
    ext = data_root / "raw" / "external"
    found: dict[str, list[Path]] = {}
    members = {}
    for key, want in sorted(pinned.items()):
        archive, member = key.split(":", 1)
        if archive not in found:
            found[archive] = sorted(ext.rglob(archive)) if ext.is_dir() else []
        zips = [z for z in found[archive] if z.is_file()]
        if zips:
            got = []
            for z in zips:
                try:
                    with zipfile.ZipFile(z) as zf:
                        got.append(hashlib.sha256(zf.read(member)).hexdigest())
                except (KeyError, zipfile.BadZipFile, OSError):
                    got.append(None)
            members[key] = {"source": "zip", "archives": [z.relative_to(data_root).as_posix() for z in zips],
                            "member_found": all(g is not None for g in got), "pass": all(g == want for g in got)}
            continue
        extracted = ext / ZENODO_EXTRACTED / archive.removesuffix(".zip") / member
        if extracted.is_file():
            members[key] = {"source": "extracted_member", "path": extracted.relative_to(data_root).as_posix(),
                            "pass": sha(extracted) == want}
        else:
            members[key] = {"source": None, "pass": False}
    missing = sorted({k.split(":", 1)[0] for k, v in members.items() if v["source"] is None})
    return {"n_pinned": len(pinned), "members": members, "archives_missing": missing, "conflicting_pins": sorted(set(conflicts)),
            "pass": all(v["pass"] for v in members.values()) and not conflicts}


def cond1_locks(wt: Path, python: str = sys.executable, data_root: Path | None = None) -> dict:
    research = wt / "research" / "ledger"
    locks, inputs, recs, commits = {}, {}, {}, {}
    for name, tools in CHECKERS.items():
        p = research / name
        if not p.is_file():
            optional = name in LOCKS_IF_PRESENT
            locks[name] = {"present": False, "pass": optional,
                           "note": "absent and not required (no predictions v2)" if optional else "required lock missing"}
            continue
        _note(inputs, research, p)
        recs[name] = json.loads(p.read_text(encoding="utf-8"))
        chain = _chain(research, name, recs[name])
        checks = {tool: _run_checker(wt, tool, name, python) for tool in tools}
        commits[name] = _lock_commits(wt, name)
        locks[name] = {"present": True, "checks": checks, "chain": chain, "commits": commits[name],
                       "pass": all(c["pass"] for c in checks.values()) and not chain["mismatched_or_missing"]
                       and not chain["required_keys_absent"] and commits[name]["pass"]}
    amend_p = research / "AMENDMENTS_v2.jsonl"
    amendments = []
    if amend_p.is_file():
        _note(inputs, research, amend_p)
        for ln in amend_p.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                try:
                    amendments.append(json.loads(ln))
                except ValueError:
                    amendments.append({"unparsed_line": ln[:300]})
    before = _guarded(lambda: locked_before_sessions(research, inputs))
    if data_root is None:
        from brainir import paths
        data_root = paths.data_root()
    archives = _guarded(lambda: archive_members(recs, data_root))
    checks = [c for v in locks.values() for c in (v.get("checks") or {}).values()]
    counts = {f"n_{k}": sum(len(c.get(k) or []) for c in checks) for k in LIST_KEYS}
    ignored = {(r.get("line"), r.get("problem")): r for c in checks for r in (c.get("amendment_rows_ignored") or [])}
    return {"locks": locks, "n_locks_present": sum(v["present"] for v in locks.values()), **counts,
            "n_checker_failures": sum(not c["pass"] for c in checks),
            "n_chain_mismatches": sum(len(v["chain"]["mismatched_or_missing"]) for v in locks.values() if v.get("chain")),
            "n_locks_not_committed_exactly_once": sum(not c["pass"] for c in commits.values()),
            "locked_before_first_v2_session": before, "archive_members": archives,
            "amendments": amendments, "n_amendments": len(amendments), "amendment_rows_ignored": list(ignored.values()),
            "pass": all(v["pass"] for v in locks.values()) and before.get("pass") is True and archives.get("pass") is True,
            "inputs_sha256": inputs}


# ------------------------------------------------------------------------------------------------------------- 2 breaches
def _dirs(p: Path) -> list[str]:
    return sorted(d.name for d in p.iterdir() if d.is_dir()) if p.is_dir() else []


def _exp_ids(p: Path, inputs: dict, research: Path) -> set[str]:
    if not p.is_file():
        return set()
    _note(inputs, research, p)
    return {str(json.loads(ln)["exp_id"]) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()}


def _audit_rows(p: Path, inputs: dict, research: Path) -> list[dict]:
    if not p.is_file():
        return []
    _note(inputs, research, p)
    rows = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not all(isinstance(r, dict) and "session" in r for r in rows):
        raise ValueError(f"{p.name} is not a list of rows with 'session' and 'breach'")
    return rows


def _verification(lab: Path, inputs: dict, research: Path) -> dict | None:
    p = lab / "verify" / "verification.json"
    if not p.is_file():
        return None
    _note(inputs, research, p)
    return json.loads(p.read_text(encoding="utf-8"))


def cond2_breaches(research: Path) -> dict:
    lab, inputs = research / "labels_v2", {}
    raw = lab / "raw"
    for need in ("transcript_audit.json", "records.jsonl"):
        if not (lab / need).is_file():
            raise FileNotFoundError(f"labels_v2/{need}")
    main_rows = _audit_rows(lab / "transcript_audit.json", inputs, research)
    verify_rows = _audit_rows(lab / "verify" / "transcript_audit_verify.json", inputs, research)
    rows = main_rows + verify_rows
    audited = {str(r["session"]) for r in rows}
    breaching = {str(r["session"]) for r in rows if r.get("breach")}
    final = _exp_ids(lab / "records.jsonl", inputs, research)
    prefixes = {e.split(":", 1)[0] for e in final}
    roles: dict[str, list[str]] = {"reader": sorted(prefixes - {"atlas"}), "atlas_map_or_coder": []}
    problems, atlas_candidates = [], []
    if "atlas" in prefixes:
        mapped = any(e.rsplit(":", 1)[-1] != "UNMAPPED" for e in final if e.startswith("atlas:"))
        for area, base in ATLAS_BASES:
            cands = [s for s in (base, f"{base}-r1") if (raw / area / s).is_dir()]
            atlas_candidates += cands
            used = next((s for s in cands if s not in breaching), None)
            if used:
                roles["atlas_map_or_coder"].append(used)
            elif base != "atlas-map" or mapped:
                problems.append(f"atlas records are final but {base} has no non-breaching session ({len(cands)} candidates)")
    replaced: dict[str, list[str]] = {}
    for role, sub in (("second_reader", "pass2"), ("adjudicator", "adjudication")):
        read = {s: _exp_ids(raw / sub / s / "records.valid.jsonl", inputs, research) & final for s in _dirs(raw / sub)}
        clean = set().union(*[ids for s, ids in read.items() if s not in breaching])
        roles[role] = sorted(s for s, ids in read.items() if ids and not (s in breaching and ids <= clean))
        replaced[role] = sorted(s for s, ids in read.items() if ids and s in breaching and ids <= clean)
    ver = _verification(lab, inputs, research)
    roles["verifier"] = [str(ver["verifier_session"])] if ver and ver.get("verifier_session") else []
    contributing = sorted({s for v in roles.values() for s in v})
    bad = sorted(s for s in contributing if s in breaching)
    unaudited = sorted(s for s in contributing if s not in audited)
    literal = (set(roles["reader"]) | set(atlas_candidates) | set(_dirs(raw / "pass2")) | set(_dirs(raw / "adjudication"))
               | {str(r["session"]) for r in verify_rows} | set(roles["verifier"]))
    return {"pass": not bad and not unaudited and not problems, "n_final_records": len(final), "n_sessions_in_audits": len(audited),
            "n_breaching_in_audits": len(breaching), "contributing_by_role": {k: len(v) for k, v in roles.items()},
            "n_contributing": len(contributing), "breaching_contributing": bad, "unaudited_contributing": unaudited,
            "atlas_problems": problems, "breaching_excluded_and_replaced": replaced,
            "literal_rule_reported_only": {"definition": "readers + every atlas candidate + every session folder under raw/pass2 and "
                                                         "raw/adjudication + every audited verifier",
                                           "n_sessions": len(literal), "breaching": sorted(literal & breaching)},
            "inputs_sha256": inputs}


# ------------------------------------------------------------------------------------------------------------- 3 review, verification
VERDICT_LINE = re.compile(r"^\s*(?:[#>+-]+\s*)*verdict\s*:\s*(.*?)\s*$", re.IGNORECASE)


def verdict_phrases(text: str) -> list[str]:
    """The phrase of every line of the form `Verdict: <phrase>`: `*` and backtick emphasis removed, whitespace collapsed,
    lower case, one trailing full stop dropped. A heading or list marker may precede `Verdict`."""
    out = []
    for line in text.splitlines():
        m = VERDICT_LINE.match(re.sub(r"[*`]", "", line))
        if m:
            p = re.sub(r"\s+", " ", m.group(1)).strip().lower()
            out.append(p[:-1].rstrip() if p.endswith(".") else p)
    return out


def verdict_phrase(text: str) -> str | None:
    """The phrase of the one verdict line; None when the text has no verdict line or more than one."""
    phrases = verdict_phrases(text)
    return phrases[0] if len(phrases) == 1 else None


def review_class(phrase: str | None) -> str:
    """usable / usable_with_caveats / blocked when the WHOLE phrase is one of them, else unparsed (or no_single_verdict_line)."""
    if phrase is None:
        return "no_single_verdict_line"
    return REVIEW_VERDICTS.get(phrase, "unparsed")


def _recompute_verification(lab: Path, sess, inputs: dict, research: Path) -> dict:
    """PREREG v2 L11 recomputed with the rule of labels2_collect.verify_score: an error is a missing row, an empty value,
    `cannot_verify` or a value different from the recorded one."""
    vdir = lab / "verify"
    truth_p, sample_p = vdir / "verify_truth.json", vdir / "verify_sample.csv"
    for p in (truth_p, sample_p):
        if not p.is_file():
            raise FileNotFoundError(f"labels_v2/verify/{p.name}")
        _note(inputs, research, p)
    truth = json.loads(truth_p.read_text(encoding="utf-8"))
    if not isinstance(truth, dict):
        raise TypeError("verify_truth.json is not an object {exp_id: recorded front-leg value}")
    sample = [r["exp_id"] for r in LC.read_csv_rows(sample_p, ["exp_id"])[0]]
    csv_p = vdir / "raw" / str(sess) / "verification.csv" if sess else None
    present = bool(csv_p and csv_p.is_file())
    rows = LC.read_csv_rows(csv_p, VERIFY_COLS)[0] if present else []
    got = {r["exp_id"]: r for r in rows}
    errors = [k for k, v in truth.items() if k not in got or got[k].get("front_leg_rhythm", "").strip().lower() in ("", "cannot_verify")
              or got[k]["front_leg_rhythm"].strip().lower() != str(v).lower()]
    return {"n": len(truth), "errors": len(errors), "verifier_csv": f"labels_v2/verify/raw/{sess}/verification.csv" if sess else None,
            "verifier_csv_present": present, "n_verifier_rows": len(rows), "n_sample_rows": len(sample),
            "sample_matches_truth": len(sample) == len(set(sample)) and set(sample) == set(truth)}


def cond3_review_and_verification(research: Path) -> dict:
    inputs: dict = {}
    lab = research / "labels_v2"
    rp = research / "reviews_v2" / "REVIEW_labels_v2.md"
    n_lines = None
    if rp.is_file():
        _note(inputs, research, rp)
        phrases = verdict_phrases(rp.read_text(encoding="utf-8", errors="replace"))
        n_lines = len(phrases)
        cls = review_class(phrases[0] if n_lines == 1 else None)
    else:
        cls = "missing"
    review = {"file": "reviews_v2/REVIEW_labels_v2.md", "verdict_class": cls, "n_verdict_lines": n_lines,
              "rule": "exactly one line `Verdict: <phrase>`, the whole phrase usable / usable with caveats / blocked",
              "pass": cls in REVIEW_PASS}
    v = _verification(lab, inputs, research)
    if v is None:
        verification = {"file": "labels_v2/verify/verification.json", "present": False, "pass": False}
    else:
        sess = v.get("verifier_session")
        vrows = _audit_rows(lab / "verify" / "transcript_audit_verify.json", inputs, research)
        vrow = next((r for r in vrows if str(r["session"]) == str(sess)), None) if sess else None
        verifier_ok = vrow is not None and not vrow.get("breach")
        rc = _recompute_verification(lab, sess, inputs, research)
        n, err = rc["n"], rc["errors"]
        rate_ok = n > 0 and err * 10 <= n and rc["verifier_csv_present"]
        sample_ok = rc["n_sample_rows"] == n and rc["sample_matches_truth"]
        file_ok = v.get("n") == n and v.get("errors") == err and v.get("blocker") is not True
        verification = {"file": "labels_v2/verify/verification.json", "recomputed": rc, "n": n, "errors": err,
                        "rule": "errors recomputed from verify_truth.json and the verifier's verification.csv; errors * 10 <= n",
                        "error_rate_pass": rate_ok, "n_equals_sample": sample_ok,
                        "file_states": {"n": v.get("n"), "errors": v.get("errors"), "blocker": v.get("blocker")},
                        "file_agrees_with_recomputation": file_ok, "verifier_session": sess,
                        "verifier_audited_non_breaching": verifier_ok, "pass": rate_ok and sample_ok and file_ok and verifier_ok}
    # PREREG v2 L11: everything the verification wrote (sample, truth, collected verifier outputs, audit, result) is hashed
    vdir = lab / "verify"
    files = sorted(p for p in vdir.rglob("*") if p.is_file()) if vdir.is_dir() else []
    for p in files:
        _note(inputs, research, p)
    verification["n_files_under_labels_v2_verify_hashed"] = len(files)
    return {"review": review, "verification": verification, "pass": review["pass"] and verification["pass"], "inputs_sha256": inputs}


# ------------------------------------------------------------------------------------------------------------- 4 kappa
def cond4_kappa(research: Path) -> dict:
    inputs: dict = {}
    p = research / "labels_v2" / "agreement.json"
    _note(inputs, research, p)
    d = json.loads(p.read_text(encoding="utf-8"))
    pf = (d.get("agreement") or {}).get("primary_field_all_values") if isinstance(d, dict) else None
    k = pf.get("kappa") if isinstance(pf, dict) else pf
    ok = isinstance(k, (int, float)) and not isinstance(k, bool) and math.isfinite(k) and k >= KAPPA_MIN
    return {"kappa": k, "n_pairs": pf.get("n") if isinstance(pf, dict) else None,
            "raw_agreement": pf.get("raw_agreement") if isinstance(pf, dict) else None, "threshold": KAPPA_MIN, "pass": bool(ok),
            "inputs_sha256": inputs}


# ------------------------------------------------------------------------------------------------------------- 5 primary set
def cond5_primary_set(research: Path) -> dict:
    inputs: dict = {}
    tlp, a1p = research / "labels_v2" / "type_labels.csv", research / "predictions" / "A1" / "types.csv"
    for p in (tlp, a1p, research / "kit_v2" / "exposed_types.csv", research / "labels_v2" / "exposed_v2.csv"):
        if p.is_file():
            _note(inputs, research, p)
    tl = pd.read_csv(tlp, usecols=["manc_type", "front", "exposed"], dtype=str, keep_default_na=False)
    a1 = set(pd.read_csv(a1p, usecols=["manc_type"], dtype=str, keep_default_na=False)["manc_type"])  # names only, never a score
    exposed = exposed_set_v2(research)
    clear = tl[tl["front"].isin(["yes", "no"])]
    prim = clear[clear["manc_type"].isin(a1) & ~clear["manc_type"].isin(exposed)]
    n, n_yes = len(prim), int((prim["front"] == "yes").sum())
    n_no = n - n_yes
    mism = int(((tl["exposed"].str.strip().str.lower() == "true") != tl["manc_type"].isin(exposed)).sum())
    return {"n_types": n, "n_yes": n_yes, "n_no": n_no, "thresholds": {"types": MIN_TYPES, "per_class": MIN_PER_CLASS},
            "pass": n >= MIN_TYPES and n_yes >= MIN_PER_CLASS and n_no >= MIN_PER_CLASS, "n_a1_type_names": len(a1),
            "n_exposed_v2": len(exposed), "exposed_column_mismatches_reported_only": mism, "inputs_sha256": inputs}


# ------------------------------------------------------------------------------------------------------------- 6 checklist
def cond6_checklist(research: Path) -> dict:
    p = research / CHECKLIST_REL
    if not p.is_file():
        return {"file": CHECKLIST_REL, "status": "pending", "pass": None, "inputs_sha256": {}}
    inputs: dict = {}
    _note(inputs, research, p)
    phrases = verdict_phrases(p.read_text(encoding="utf-8", errors="replace"))
    ok = len(phrases) == 1 and phrases[0] == "confirmed"
    return {"file": CHECKLIST_REL, "status": "confirmed" if ok else "not_confirmed", "n_verdict_lines": len(phrases),
            "rule": "exactly one line `Verdict: confirmed` (PREREG v2 S5.6)", "pass": ok, "inputs_sha256": inputs}


# ------------------------------------------------------------------------------------------------------------- the gate
def evaluate(repo: Path, python: str = sys.executable, data_root: Path | None = None) -> dict:
    repo = Path(repo)
    dirty = dirty_paths(repo)
    if dirty:
        raise GateRefused(f"{len(dirty)} uncommitted change(s) or untracked file(s) under ledger/ or research/ledger/ "
                          f"(first: {dirty[:5]}); commit first. Nothing was evaluated.")
    ignored = ignored_paths(repo)
    if ignored:
        raise GateRefused(f"{len(ignored)} git-ignored path(s) under research/ledger/ (first: {ignored[:5]}): a clean checkout lacks "
                          "them; commit them with `git add -f` or remove them. Nothing was evaluated.")
    res: dict = {"prereg": "research/ledger/PREREG_v2.md S5 (RUN2_PROMPT section 8)",
                 "utc": time.strftime(UTC_FORMAT, time.gmtime()), "git_head": _git(repo, "rev-parse", "HEAD").strip(),
                 "evaluated_on": "a temporary clean git worktree of HEAD"}
    me = Path(__file__).resolve()
    with clean_checkout(repo) as (wt, state):
        research = wt / "research" / "ledger"
        conds = {"1_locks": _guarded(lambda: cond1_locks(wt, python, data_root)),
                 "2_breaches": _guarded(lambda: cond2_breaches(research)),
                 "3_review_and_verification": _guarded(lambda: cond3_review_and_verification(research)),
                 "4_kappa": _guarded(lambda: cond4_kappa(research)),
                 "5_primary_set": _guarded(lambda: cond5_primary_set(research)),
                 "6_reviewer_checklist": _guarded(lambda: cond6_checklist(research), {"status": "error"})}
        mine = wt / "ledger" / "scripts" / me.name
        res["gate_script"] = {"path": f"ledger/scripts/{me.name}", "sha256": sha(me), "identical_to_head": mine.is_file() and sha(mine) == sha(me)}
        prefixes = sorted({str(wt), os.path.realpath(wt), str(wt.parent), os.path.realpath(wt.parent)}, key=len, reverse=True)
    res["checkout_removed"] = state["removed"]
    conds = _scrub(conds, prefixes)
    inputs: dict = {}
    for c in conds.values():
        inputs.update(c.get("inputs_sha256") or {})
    res["amendments"] = conds["1_locks"].get("amendments", [])
    res["conditions"] = conds
    res["inputs_sha256"] = dict(sorted(inputs.items()))
    failed = [k for k in CONDITIONS[:5] if conds[k].get("pass") is not True]
    c6 = conds["6_reviewer_checklist"]
    res["conditions_1_to_5_hold"] = not failed
    res["all_conditions_hold"] = not failed and c6.get("pass") is True
    if failed:
        res["decision"] = f"do not unblind: condition(s) {', '.join(failed)} failed (PREREG v2 S5)"
    elif c6.get("status") == "pending":
        res["decision"] = "conditions 1-5 hold; nothing is unblinded until a fresh reviewer signs reviews_v2/GATE_CHECKLIST.md (condition 6)"
    elif c6.get("pass") is True:
        res["decision"] = "all six conditions hold: unblinding may be authorised (UNBLIND.json, by the authorising person)"
    else:
        res["decision"] = "do not unblind: condition 6 (reviewer checklist) is not confirmed"
    res["unblind_flag_exists_at_gate_time"] = (repo / "research" / "ledger" / "UNBLIND.json").exists()
    return res


def _run1_problem(prev) -> str | None:
    if not isinstance(prev, dict) or prev.get("gate_run") != 1:
        return "run 1's report does not record gate run 1"
    conds = prev.get("conditions") or {}
    failed = [k for k in CONDITIONS[:5] if (conds.get(k) or {}).get("pass") is not True]
    if failed:
        return f"gate run 1 failed condition(s) {', '.join(failed)}"
    if (conds.get(CONDITIONS[5]) or {}).get("status") != "pending":
        return "gate run 1 did not record condition 6 as pending"
    return None


def gate_run(repo: Path) -> tuple[int, dict | None]:
    """Which of the two runs this is (PREREG v2 S5.6, L14), with run 1's report for run 2; raises GateRefused otherwise."""
    research = Path(repo) / "research" / "ledger"
    r1, r2, cl = research / GATE_REPORTS[1], research / GATE_REPORTS[2], research / CHECKLIST_REL
    committed = {k: _ever_committed(repo, f"research/ledger/{v}") for k, v in GATE_REPORTS.items()}
    if r2.exists() or committed[2]:
        raise GateRefused("the gate has run twice (once before and once after the checklist, PREREG v2 S5.6): a third run is "
                          "refused (L14: the gate runs once)")
    if r1.exists() or committed[1]:
        if not r1.is_file():
            raise GateRefused(f"{GATE_REPORTS[1]} was committed and is gone: refused (the gate runs once, L14)")
        try:
            prev = json.loads(r1.read_text(encoding="utf-8"))
        except ValueError:
            prev = None
        problem = _run1_problem(prev)
        if problem:
            raise GateRefused(f"run 2 refused: {problem}. A failed gate ends the collection (PREREG v2 L14).")
        if not cl.is_file():
            raise GateRefused(f"run 2 records condition 6 and runs once, after the reviewer's checklist (PREREG v2 S5.6): commit "
                              f"{CHECKLIST_REL} first")
        return 2, prev
    if cl.exists() or _ever_committed(repo, f"research/ledger/{CHECKLIST_REL}"):
        raise GateRefused(f"{CHECKLIST_REL} exists (or was committed) before the first gate run: the first run precedes the "
                          "checklist (PREREG v2 S5.6)")
    return 1, None


def _pf(c: dict) -> str:
    return "PASS" if c.get("pass") is True else ("PENDING" if c.get("pass") is None else "FAIL")


def summary_lines(res: dict) -> list[str]:
    c = res["conditions"]
    lines = [(f"unblinding gate v2, run {res.get('gate_run', '?')}, on HEAD {res['git_head'][:12]}; clean checkout removed: "
              f"{res['checkout_removed']}")]

    def err(label: str, k: str) -> str:
        return f"{label}: error ({c[k]['error'][:160]}) -> FAIL"
    c1 = c["1_locks"]
    if "error" in c1:
        lines.append(err("1 locks", "1_locks"))
    else:
        bf, ar = c1["locked_before_first_v2_session"], c1["archive_members"]
        lines.append(f"1 locks: {c1['n_locks_present']} present, {c1['n_changed']} changed, {c1['n_missing']} missing, "
                     f"{c1['n_checker_failures']} checker failures, {c1['n_chain_mismatches']} chain mismatches, "
                     f"{c1['n_locks_not_committed_exactly_once']} not committed exactly once, {c1['n_amended']} amended "
                     f"({c1['n_amendments']} amendments recorded, {len(c1['amendment_rows_ignored'])} rows ignored); label-code and "
                     f"scoring locks before the first v2 session: {_pf(bf)}; archive members: {ar.get('n_pinned')} pinned, "
                     f"{len(ar.get('archives_missing') or [])} archives missing, {_pf(ar)} -> {_pf(c1)}")
    c2 = c["2_breaches"]
    lines.append(err("2 breaches", "2_breaches") if "error" in c2 else
                 f"2 breaches: {c2['n_contributing']} contributing sessions {c2['contributing_by_role']}; "
                 f"{len(c2['breaching_contributing'])} breaching, {len(c2['unaudited_contributing'])} unaudited, "
                 f"{len(c2['atlas_problems'])} atlas problems -> {_pf(c2)} "
                 f"(literal rule: {len(c2['literal_rule_reported_only']['breaching'])} breaching)")
    c3 = c["3_review_and_verification"]
    lines.append(err("3 review/verification", "3_review_and_verification") if "error" in c3 else
                 f"3 review: {c3['review']['verdict_class']} -> {_pf(c3['review'])}; verification (recomputed): "
                 f"{c3['verification'].get('errors')} errors of {c3['verification'].get('n')}, verifier non-breaching: "
                 f"{c3['verification'].get('verifier_audited_non_breaching')} -> {_pf(c3['verification'])}")
    c4 = c["4_kappa"]
    kap = c4.get("kappa")
    if "error" in c4:
        lines.append(err("4 kappa", "4_kappa"))
    elif isinstance(kap, (int, float)) and not isinstance(kap, bool):
        lines.append(f"4 kappa (front leg, all values): {kap:.3f} on {c4['n_pairs']} pairs -> {_pf(c4)}")
    else:
        lines.append(f"4 kappa: {kap} -> {_pf(c4)}")
    c5 = c["5_primary_set"]
    lines.append(err("5 primary set", "5_primary_set") if "error" in c5 else
                 f"5 primary set: {c5['n_types']} types ({c5['n_yes']} yes, {c5['n_no']} no) -> {_pf(c5)}")
    lines.append(f"6 reviewer checklist: {c['6_reviewer_checklist'].get('status')} -> {_pf(c['6_reviewer_checklist'])}")
    if "conditions_1_to_5_identical_to_run1" in res:
        lines.append(f"conditions 1-5 identical to run 1: {res['conditions_1_to_5_identical_to_run1']}")
    lines.append(f"decision: {res['decision']}")
    return lines


def main(argv: list[str] | None = None, repo: Path = REPO, data_root: Path | None = None) -> int:
    ap = argparse.ArgumentParser(description="PREREG v2 S5 unblinding gate (label files and type names only); runs twice, S5.6")
    ap.parse_args(argv)
    repo = Path(repo)
    research = repo / "research" / "ledger"
    try:
        run, prev = gate_run(repo)
        res = evaluate(repo, data_root=data_root)
    except GateRefused as e:
        print(f"gate refused: {e}", file=sys.stderr)
        return 2
    res["gate_run"] = run
    if run == 1:
        res["run_rule"] = "run 1 of 2 (PREREG v2 S5.6): before the reviewer's checklist, which records condition 6 as pending"
    else:
        res["run_rule"] = "run 2 of 2 (PREREG v2 S5.6): after the checklist, only to record condition 6; conditions 1-5 must equal run 1's"
        res["run1_report"] = f"research/ledger/{GATE_REPORTS[1]}"
        res["run1_report_sha256"] = sha(research / GATE_REPORTS[1])
        diff = [k for k in CONDITIONS[:5] if _canonical((prev.get("conditions") or {}).get(k)) != _canonical(res["conditions"][k])]
        res["conditions_1_to_5_identical_to_run1"] = not diff
        res["conditions_differing_from_run1"] = diff
        if diff:
            res["all_conditions_hold"] = False
            res["decision"] = f"do not unblind: condition(s) {', '.join(diff)} differ from gate run 1 (PREREG v2 S5.6)"
    out = research / GATE_REPORTS[run]
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(out, "x", encoding="utf-8", newline="\n") as fh:  # never overwritten
            fh.write(json.dumps(res, indent=1, sort_keys=True, default=str) + "\n")
    except FileExistsError:
        print(f"gate refused: {GATE_REPORTS[run]} appeared during the run; nothing written", file=sys.stderr)
        return 2
    print("\n".join(summary_lines(res)))
    print(f"-> research/ledger/{GATE_REPORTS[run]}")
    return 0 if res["all_conditions_hold"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
