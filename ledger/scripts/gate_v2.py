"""The unblinding gate of run 2 (PREREG v2 S5; RUN2_PROMPT section 8), computed from label files and type names only.

    uv run --project ledger --no-sync python ledger/scripts/gate_v2.py      # -> research/ledger/gates_v2/UNBLINDING_GATE.json

Exit 0: all six conditions hold. Exit 1: a condition fails, or condition 6 is still pending. Exit 2: refused (nothing
evaluated, nothing written).

How it runs. Commit first: the gate refuses while `git status` shows a change or an untracked file under ledger/ or
research/ledger/. It then makes ONE clean checkout of HEAD (a temporary `git worktree`, removed at the end, also on error) and
evaluates every condition on that checkout, so the result rests only on committed files; every input file it read is listed
with its SHA-256 (this covers the verification files of L11, which are written after the labels lock). It never reads a
prediction score: of the prediction tables it reads only the `manc_type` column of A1 (condition 5); the lock tools hash
files without parsing them. It prints only counts and pass/fail. The gate runs once before the reviewer's checklist and once
after it, only to record condition 6 (PREREG v2 S5.6): the second run records the SHA-256 of the first output and fails the
gate unless conditions 1-5 (pass values and input hashes) are identical.

1. Locks (S5.1, L12). In the checkout, with the checkout's own lock tools run by this interpreter: `lock2.py check` on every
   lock (v1: rulebook, predictions, labels v1 (chained from v1.1), labels v1.1; v2: rulebook, label code, scoring, labels,
   predictions if present) and the frozen `lock.py check` on the four v1 locks (it covers the archive-member keys lock2.py
   skips); a check passes when the tool exits 0. lock2.py's amended / snapshot / archive lists are copied into the report, and
   so is `AMENDMENTS_v2.jsonl` (L12: "the gate report lists every amendment"). The gate also re-checks the chained lock hashes
   (top-level `*_lock_sha256`) itself; an unknown chain key is reported, not failed. Tools per lock: `CHECKERS`.
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
3. Review and verification (S5.3, L11). The verdict line of `reviews_v2/REVIEW_labels_v2.md` ("Verdict: <phrase>", or a
   "Verdict" heading and the next line), classified by its first words: usable / usable with caveats pass; blocked, a missing
   file or an unparseable verdict fail. `labels_v2/verify/verification.json`: integers n > 0 and errors with errors * 10 <= n
   (at most 10 %), `blocker` not true, and `verifier_session` audited non-breaching in `transcript_audit_verify.json`. Every
   file under `labels_v2/verify/` (sample, collected verifier outputs, audit, result) is hashed in the report (L11).
4. Agreement (S5.4): `labels_v2/agreement.json` -> agreement.primary_field_all_values (its `kappa` if it is a dict) >= 0.7.
5. Primary set (S5.5): types of `labels_v2/type_labels.csv` with front in {yes, no}, among the `manc_type` names of
   predictions/A1/types.csv, not in the v2 exposed set (kit_v2/exposed_types.csv + labels_v2/exposed_v2.csv, the scoring's
   own `exposed_set_v2`): at least 20 types, 5 yes, 5 no. A disagreement between the table's `exposed` column and that set is
   reported (the scoring would refuse such a table).
6. Reviewer checklist (S5.6): `reviews_v2/GATE_CHECKLIST.md`; absent -> "pending"; signed when its verdict line starts with
   "confirmed" or "signed" (e.g. "**Verdict: confirmed.**"), else "not_confirmed".
"""

from __future__ import annotations

import argparse
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
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "ledger" / "src"))
from brainir_ledger.scoring_v2.pipeline_v2 import exposed_set_v2  # noqa: E402

OUT_REL = "research/ledger/gates_v2/UNBLINDING_GATE.json"
LOCKS_V1 = ("LOCK_prereg_v1.json", "LOCK_predictions_v1.json", "LOCK_labels_v1.json", "LOCK_labels_v1_1.json")
LOCKS_V2 = ("LOCK_prereg_v2.json", "LOCK_labelcode_v2.json", "LOCK_scoring_v2.json", "LOCK_labels_v2.json")
LOCKS_IF_PRESENT = ("LOCK_predictions_v2.json",)
CHECKERS = {**{n: ("lock2.py", "lock.py") for n in LOCKS_V1}, **{n: ("lock2.py",) for n in LOCKS_V2 + LOCKS_IF_PRESENT}}
CHAINED = {"prereg_lock_sha256": "LOCK_prereg_v1.json", "labels_v1_lock_sha256": "LOCK_labels_v1.json",
           "prereg_v2_lock_sha256": "LOCK_prereg_v2.json", "labelcode_v2_lock_sha256": "LOCK_labelcode_v2.json"}
LIST_KEYS = ("changed", "missing", "amended", "snapshot_changed_reported_only")
ATLAS_BASES = (("atlas_map", "atlas-map"), ("pass1", "atlas-codeA"), ("pass1", "atlas-codeB"))
KAPPA_MIN = 0.7
MIN_TYPES, MIN_PER_CLASS = 20, 5
REVIEW_PASS = ("usable", "usable_with_caveats")
CONDITIONS = ("1_locks", "2_breaches", "3_review_and_verification", "4_kappa", "5_primary_set", "6_reviewer_checklist")


class GateRefused(RuntimeError):
    """The gate was not evaluated; nothing was written."""


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


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
    for k in LIST_KEYS:
        if k in out:
            rec[k] = list(out.get(k) or [])
    if "archive_members_skipped" in out:
        rec["archive_members_skipped"] = out["archive_members_skipped"]
    return rec


def _chain(research: Path, rec: dict) -> dict:
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
    return {"verified": ok, "mismatched_or_missing": bad, "unknown_keys_not_checked": unknown}


def cond1_locks(wt: Path, python: str = sys.executable) -> dict:
    research = wt / "research" / "ledger"
    locks, inputs = {}, {}
    for name, tools in CHECKERS.items():
        p = research / name
        if not p.is_file():
            optional = name in LOCKS_IF_PRESENT
            locks[name] = {"present": False, "pass": optional,
                           "note": "absent and not required (no predictions v2)" if optional else "required lock missing"}
            continue
        _note(inputs, research, p)
        chain = _chain(research, json.loads(p.read_text(encoding="utf-8")))
        checks = {tool: _run_checker(wt, tool, name, python) for tool in tools}
        locks[name] = {"present": True, "checks": checks, "chain": chain,
                       "pass": all(c["pass"] for c in checks.values()) and not chain["mismatched_or_missing"]}
    amend_p = research / "AMENDMENTS_v2.jsonl"
    amendments = []
    if amend_p.is_file():
        _note(inputs, research, amend_p)
        amendments = [json.loads(ln) for ln in amend_p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    checks = [c for v in locks.values() for c in (v.get("checks") or {}).values()]
    counts = {f"n_{k}": sum(len(c.get(k) or []) for c in checks) for k in LIST_KEYS}
    return {"locks": locks, "n_locks_present": sum(v["present"] for v in locks.values()), **counts,
            "n_checker_failures": sum(not c["pass"] for c in checks),
            "n_chain_mismatches": sum(len(v["chain"]["mismatched_or_missing"]) for v in locks.values() if v.get("chain")),
            "amendments": amendments, "n_amendments": len(amendments),
            "pass": all(v["pass"] for v in locks.values()), "inputs": inputs}


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
            "inputs": inputs}


# ------------------------------------------------------------------------------------------------------------- 3 review, verification
VERDICT_LINE = re.compile(r"\bverdict\b\s*[:–—-]\s*(.*)$", re.IGNORECASE)
VERDICT_HEADING = re.compile(r"^\W*verdict\W*$", re.IGNORECASE)


def verdict_phrase(text: str) -> str | None:
    """The phrase after the first "Verdict:" (or the first non-empty line after a "Verdict" heading), lower case, without
    markdown emphasis."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = VERDICT_LINE.search(line)
        phrase = m.group(1) if m else (next((x for x in lines[i + 1:] if x.strip()), "") if VERDICT_HEADING.match(line) else None)
        if phrase is not None:
            p = re.sub(r"\s+", " ", re.sub(r"[*_`#>]", "", phrase)).strip().lower()
            if p:
                return p
    return None


def review_class(phrase: str | None) -> str:
    if not phrase:
        return "no_verdict_line"
    p = re.sub(r"^(the\s+)?(labels?\s+)?((are|is)\s+)?", "", phrase)
    if p.startswith("blocked"):
        return "blocked"
    if p.startswith("usable with caveats"):
        return "usable_with_caveats"
    if p.startswith("usable"):
        return "usable"
    return "unparsed"


def cond3_review_and_verification(research: Path) -> dict:
    inputs: dict = {}
    lab = research / "labels_v2"
    rp = research / "reviews_v2" / "REVIEW_labels_v2.md"
    if rp.is_file():
        _note(inputs, research, rp)
        cls = review_class(verdict_phrase(rp.read_text(encoding="utf-8", errors="replace")))
    else:
        cls = "missing"
    review = {"file": "reviews_v2/REVIEW_labels_v2.md", "verdict_class": cls, "pass": cls in REVIEW_PASS}
    v = _verification(lab, inputs, research)
    if v is None:
        verification = {"file": "labels_v2/verify/verification.json", "present": False, "pass": False}
    else:
        n, err, sess = v.get("n"), v.get("errors"), v.get("verifier_session")
        ints = all(isinstance(x, int) and not isinstance(x, bool) for x in (n, err))
        rate_ok = bool(ints and n > 0 and 0 <= err <= n and err * 10 <= n) and v.get("blocker") is not True
        vrows = _audit_rows(lab / "verify" / "transcript_audit_verify.json", inputs, research)
        vrow = next((r for r in vrows if str(r["session"]) == str(sess)), None) if sess else None
        verifier_ok = vrow is not None and not vrow.get("breach")
        verification = {"file": "labels_v2/verify/verification.json", "n": n, "errors": err, "error_rate_in_file": v.get("error_rate"),
                        "blocker_in_file": v.get("blocker"), "rule": "errors * 10 <= n (at most 10 %)", "error_rate_pass": rate_ok,
                        "verifier_session": sess, "verifier_audited_non_breaching": verifier_ok, "pass": rate_ok and verifier_ok}
    # PREREG v2 L11: everything the verification wrote (sample, collected verifier outputs, audit, result) is hashed in the report
    vdir = lab / "verify"
    files = sorted(p for p in vdir.rglob("*") if p.is_file()) if vdir.is_dir() else []
    for p in files:
        _note(inputs, research, p)
    verification["n_files_under_labels_v2_verify_hashed"] = len(files)
    return {"review": review, "verification": verification, "pass": review["pass"] and verification["pass"], "inputs": inputs}


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
            "inputs": inputs}


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
            "n_exposed_v2": len(exposed), "exposed_column_mismatches_reported_only": mism, "inputs": inputs}


# ------------------------------------------------------------------------------------------------------------- 6 checklist
def cond6_checklist(research: Path) -> dict:
    p = research / "reviews_v2" / "GATE_CHECKLIST.md"
    if not p.is_file():
        return {"file": "reviews_v2/GATE_CHECKLIST.md", "status": "pending", "pass": None, "inputs": {}}
    inputs: dict = {}
    _note(inputs, research, p)
    phrase = verdict_phrase(p.read_text(encoding="utf-8", errors="replace"))
    signed = bool(phrase) and re.match(r"(confirmed|signed)\b", phrase) is not None
    return {"file": "reviews_v2/GATE_CHECKLIST.md", "status": "signed" if signed else "not_confirmed", "pass": signed, "inputs": inputs}


# ------------------------------------------------------------------------------------------------------------- the gate
def evaluate(repo: Path, python: str = sys.executable) -> dict:
    repo = Path(repo)
    dirty = dirty_paths(repo)
    if dirty:
        raise GateRefused(f"{len(dirty)} uncommitted change(s) or untracked file(s) under ledger/ or research/ledger/ "
                          f"(first: {dirty[:5]}); commit first. Nothing was evaluated.")
    res: dict = {"prereg": "research/ledger/PREREG_v2.md S5 (RUN2_PROMPT section 8)",
                 "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_head": _git(repo, "rev-parse", "HEAD").strip(),
                 "evaluated_on": "a temporary clean git worktree of HEAD"}
    me = Path(__file__).resolve()
    with clean_checkout(repo) as (wt, state):
        research = wt / "research" / "ledger"
        conds = {"1_locks": _guarded(lambda: cond1_locks(wt, python)),
                 "2_breaches": _guarded(lambda: cond2_breaches(research)),
                 "3_review_and_verification": _guarded(lambda: cond3_review_and_verification(research)),
                 "4_kappa": _guarded(lambda: cond4_kappa(research)),
                 "5_primary_set": _guarded(lambda: cond5_primary_set(research)),
                 "6_reviewer_checklist": _guarded(lambda: cond6_checklist(research), {"status": "error"})}
        mine = wt / "ledger" / "scripts" / me.name
        res["gate_script"] = {"path": f"ledger/scripts/{me.name}", "sha256": sha(me), "identical_to_head": mine.is_file() and sha(mine) == sha(me)}
    res["checkout_removed"] = state["removed"]
    inputs: dict = {}
    for c in conds.values():
        inputs.update(c.pop("inputs", None) or {})
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


def _pf(c: dict) -> str:
    return "PASS" if c.get("pass") is True else ("PENDING" if c.get("pass") is None else "FAIL")


def summary_lines(res: dict) -> list[str]:
    c = res["conditions"]
    lines = [f"unblinding gate v2 on HEAD {res['git_head'][:12]}; clean checkout removed: {res['checkout_removed']}"]

    def err(label: str, k: str) -> str:
        return f"{label}: error ({c[k]['error'][:160]}) -> FAIL"
    c1 = c["1_locks"]
    lines.append(err("1 locks", "1_locks") if "error" in c1 else
                 f"1 locks: {c1['n_locks_present']} present, {c1['n_changed']} changed, {c1['n_missing']} missing, "
                 f"{c1['n_checker_failures']} checker failures, {c1['n_chain_mismatches']} chain mismatches, {c1['n_amended']} amended "
                 f"({c1['n_amendments']} amendments recorded) -> {_pf(c1)}")
    c2 = c["2_breaches"]
    lines.append(err("2 breaches", "2_breaches") if "error" in c2 else
                 f"2 breaches: {c2['n_contributing']} contributing sessions {c2['contributing_by_role']}; "
                 f"{len(c2['breaching_contributing'])} breaching, {len(c2['unaudited_contributing'])} unaudited, "
                 f"{len(c2['atlas_problems'])} atlas problems -> {_pf(c2)} "
                 f"(literal rule: {len(c2['literal_rule_reported_only']['breaching'])} breaching)")
    c3 = c["3_review_and_verification"]
    lines.append(err("3 review/verification", "3_review_and_verification") if "error" in c3 else
                 f"3 review: {c3['review']['verdict_class']} -> {_pf(c3['review'])}; verification: "
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
    lines.append(f"decision: {res['decision']}")
    return lines


def main(argv: list[str] | None = None, repo: Path = REPO) -> int:
    ap = argparse.ArgumentParser(description="PREREG v2 S5 unblinding gate (label files and type names only)")
    ap.parse_args(argv)
    out = Path(repo) / OUT_REL
    try:
        res = evaluate(Path(repo))
    except GateRefused as e:
        print(f"gate refused: {e}", file=sys.stderr)
        return 2
    res["previous_output_sha256"] = sha(out) if out.exists() else None
    if out.exists():  # PREREG v2 S5.6: the second run only records condition 6; conditions 1-5 must come out identical
        prev = json.loads(out.read_text(encoding="utf-8"))
        keep = lambda d: {k: v for k, v in (d or {}).items() if "GATE_CHECKLIST" not in k}  # noqa: E731
        same = ({k: (prev.get("conditions") or {}).get(k, {}).get("pass") for k in CONDITIONS[:5]}
                == {k: res["conditions"][k].get("pass") for k in CONDITIONS[:5]}
                and keep(prev.get("inputs_sha256")) == keep(res["inputs_sha256"]))
        res["conditions_1_to_5_identical_to_previous_run"] = same
        if not same:
            res["all_conditions_hold"] = False
            res["decision"] = "do not unblind: conditions 1-5 differ from the previous gate run (PREREG v2 S5.6)"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(summary_lines(res)))
    print(f"-> {OUT_REL}")
    return 0 if res["all_conditions_hold"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
