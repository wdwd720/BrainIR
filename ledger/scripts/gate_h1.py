"""The unblinding gate of exam 2 (PREREG v3 S5; RUN3_PROMPT section 9), computed from label files and hemilineage names only.
LABEL SIDE: it never reads a prediction value (the lock tools hash files without parsing them).

    uv run --project ledger --no-sync python ledger/scripts/gate_h1.py
        run 1 -> research/ledger/gates_v3/UNBLINDING_GATE_h1_run1.json   (before reviews_v3/GATE_CHECKLIST_h1.md exists)
        run 2 -> research/ledger/gates_v3/UNBLINDING_GATE_h1_run2.json   (after the checklist is committed)

Run 2's design and helpers (`gate_v2.py`, frozen, imported unchanged): refuses while anything under ledger/ or research/ledger/ is
uncommitted or git-ignored; evaluates every condition on ONE temporary clean worktree of HEAD; two runs, each once, never
overwritten; run 2 requires run 1's conditions 1-5 to pass with condition 6 pending, and its conditions 1-5 must equal run 1's.
Exit 0: all six hold (run 2). Exit 1: a condition fails or is pending. Exit 2: refused.

1. Locks: run 2's condition 1 (every v1 and v2 lock, both checkers for v1, archive members, locks before the v2 sessions) plus
   `lock2.py check` on every run 3 lock (prereg v3, label code h1, predictions h1, labels h1; reliability v1 if present), and
   `LOCK_labelcode_h1.json` committed before the first h1 label session started (session manifests in labels_h1/sessions/).
2. Breaches: every session that contributed a final record (`records.csv` column `source_sessions`) is in the transcript audit and
   did not breach; no final record from a breaching session (T7).
3. Label review (`reviews_v3/LABEL_REVIEW_h1.md`, exactly one line `Verdict: usable` or `Verdict: usable with caveats`) and the
   verification error rate (recomputed from the sample, the final records and the verifier's file; verifier not breaching) <= 10 %.
4. Kappa between the two readings (recomputed from `pairs.csv` and the raw readings; primary cells both code yes/no) >= 0.7.
5. At least 20 units with at least 3 coded primary dimensions in `consensus.csv` (every unit name in the unit list).
6. `reviews_v3/GATE_CHECKLIST_h1.md` holds exactly one line `Verdict: confirmed`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "ledger" / "src"))
import gate_v2 as GV  # noqa: E402  (frozen; helpers and condition 1 for the v1/v2 locks)

from brainir_ledger.labels_h1 import core as C  # noqa: E402

GATES = "gates_v3"
REPORTS = {1: f"{GATES}/UNBLINDING_GATE_h1_run1.json", 2: f"{GATES}/UNBLINDING_GATE_h1_run2.json"}
CHECKLIST_REL = "reviews_v3/GATE_CHECKLIST_h1.md"
REVIEW_REL = "reviews_v3/LABEL_REVIEW_h1.md"
LOCKS_H1 = ("LOCK_prereg_v3.json", "LOCK_labelcode_h1.json", "LOCK_predictions_h1.json", "LOCK_labels_h1.json")
LOCKS_H1_IF_PRESENT = ("LOCK_reliability_v1.json",)
KAPPA_MIN, MAX_ERROR, MIN_UNITS = 0.7, 0.10, 20
CONDITIONS = GV.CONDITIONS


def _first_commit_utc(wt: Path, rel: str) -> int | None:
    out = GV._git(wt, "log", "--diff-filter=A", "--format=%ct", "--", rel).strip().splitlines()
    return int(out[-1]) if out else None


def cond1(wt: Path, python: str, data_root: Path | None) -> dict:
    research = wt / "research" / "ledger"
    base = GV.cond1_locks(wt, python, data_root)
    h1, inputs = {}, {}
    for name in LOCKS_H1 + LOCKS_H1_IF_PRESENT:
        p = research / name
        if not p.is_file():
            h1[name] = {"present": False, "pass": name in LOCKS_H1_IF_PRESENT}
            continue
        GV._note(inputs, research, p)
        h1[name] = {"present": True, **GV._run_checker(wt, "lock2.py", name, python)}
    lock_t = _first_commit_utc(wt, "research/ledger/LOCK_labelcode_h1.json")
    starts = []
    for m in sorted((research / "labels_h1" / "sessions").glob("*.json")):
        GV._note(inputs, research, m)
        for run in json.loads(m.read_text(encoding="utf-8")).get("runs", []):
            t = GV._utc(run.get("start_utc"))
            if t is not None:
                starts.append(t)
    before = {"labelcode_h1_first_commit_utc": lock_t, "first_h1_session_start_utc": min(starts) if starts else None,
              "pass": bool(lock_t and starts and lock_t < min(starts))}
    return {"v1_v2": base, "h1_locks": h1, "labelcode_h1_before_sessions": before, "inputs_sha256": {**base.get("inputs_sha256", {}), **inputs},
            "pass": base.get("pass") is True and all(v["pass"] for v in h1.values()) and before["pass"]}


def _audit(research: Path, rel: str, inputs: dict) -> dict[str, dict]:
    p = research / rel
    GV._note(inputs, research, p)
    return {r["session"]: r for r in json.loads(p.read_text(encoding="utf-8"))}


def _final(research: Path, inputs: dict) -> pd.DataFrame:
    p = research / "labels_h1" / "records.csv"
    GV._note(inputs, research, p)
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def cond2(research: Path) -> dict:
    inputs: dict = {}
    audit = _audit(research, "labels_h1/transcript_audit.json", inputs)
    final = _final(research, inputs)
    contributing = sorted({s for v in final["source_sessions"] for s in v.split(";") if s})
    missing = [s for s in contributing if s not in audit]
    breached = [s for s in contributing if s in audit and audit[s]["breach"]]
    return {"n_contributing_sessions": len(contributing), "not_in_audit": missing, "breached": breached,
            "n_audited": len(audit), "pass": bool(contributing) and not missing and not breached, "inputs_sha256": inputs}


def cond3(research: Path) -> dict:
    inputs: dict = {}
    rp = research / REVIEW_REL
    review = {"file": REVIEW_REL, "class": "missing"}
    if rp.is_file():
        GV._note(inputs, research, rp)
        review["class"] = GV.review_class(GV.verdict_phrase(rp.read_text(encoding="utf-8", errors="replace")))
    final = _final(research, inputs)
    final["eligible"] = final["eligible"].map({"True": True, "False": False})
    sample_p = research / "labels_h1" / "verify" / "to_verify.jsonl"
    GV._note(inputs, research, sample_p)
    sample = [json.loads(x) for x in sample_p.read_text(encoding="utf-8").splitlines() if x.strip()]
    vaudit = _audit(research, "labels_h1/verify/transcript_audit_verify.json", inputs)
    verified: dict = {}
    vsessions = []
    for f in sorted((research / "labels_h1" / "raw" / "verify").glob("*/verification.jsonl")):
        GV._note(inputs, research, f)
        vsessions.append(f.parent.name)
        for x in f.read_text(encoding="utf-8").splitlines():
            if x.strip():
                d = json.loads(x)
                verified[d["verify_id"]] = d["cells"]
    ids = {s["verify_id"]: s["record_id"] for s in sample}
    expected = C.verification_sample(final)
    err = C.verification_error(final, {ids[v]: cells for v, cells in verified.items() if v in ids})
    vbreach = [s for s in vsessions if s not in vaudit or vaudit[s]["breach"]]
    ok_v = (sorted(ids.values()) == expected and set(verified) == set(ids) and not vbreach and err["error_rate"] is not None
            and err["error_rate"] <= MAX_ERROR)
    return {"review": review, "verification": {k: v for k, v in err.items() if k != "errors"}, "n_sampled": len(ids),
            "sample_is_the_seeded_draw": sorted(ids.values()) == expected, "all_sampled_verified": set(verified) == set(ids),
            "verifier_sessions_breached_or_unaudited": vbreach,
            "pass": review["class"] in GV.REVIEW_PASS and ok_v, "inputs_sha256": inputs}


def cond4(research: Path) -> dict:
    inputs: dict = {}
    audit = _audit(research, "labels_h1/transcript_audit.json", inputs)
    pp = research / "labels_h1" / "pairs.csv"
    GV._note(inputs, research, pp)
    pairs = pd.read_csv(pp, dtype=str, keep_default_na=False)
    recs = {}
    for f in sorted((research / "labels_h1" / "raw" / "reading").glob("*/records.jsonl")):
        GV._note(inputs, research, f)
        for x in f.read_text(encoding="utf-8").splitlines():
            if x.strip():
                r = json.loads(x)
                recs[r["record_id"]] = r
    use = [(recs[a], recs[b]) for a, b in zip(pairs["record_id_1"], pairs["record_id_2"])
           if a in recs and b in recs and not audit.get(recs[a]["session"], {"breach": True})["breach"]
           and not audit.get(recs[b]["session"], {"breach": True})["breach"]]
    k = C.readings_kappa(use)
    return {"n_pairs": len(use), **k, "threshold": KAPPA_MIN, "pass": k["kappa"] is not None and k["kappa"] >= KAPPA_MIN,
            "inputs_sha256": inputs}


def cond5(research: Path) -> dict:
    inputs: dict = {}
    cp = research / "labels_h1" / "consensus.csv"
    up = research / "hl_units" / "UNITS_v1.csv"
    GV._note(inputs, research, cp)
    GV._note(inputs, research, up)
    cons = pd.read_csv(cp, dtype=str, keep_default_na=False).set_index("unit")
    units = pd.read_csv(up, dtype={"unit": str})["unit"].tolist()
    unknown = sorted(set(cons.index) - set(units))
    n = C.n_units_ge3(cons)
    return {"n_units_ge3_coded_primary": n, "threshold": MIN_UNITS, "unknown_units": unknown,
            "pass": not unknown and n >= MIN_UNITS, "inputs_sha256": inputs}


def cond6(research: Path) -> dict:
    p = research / CHECKLIST_REL
    if not p.is_file():
        return {"file": CHECKLIST_REL, "status": "pending", "pass": None, "inputs_sha256": {}}
    inputs: dict = {}
    GV._note(inputs, research, p)
    ph = GV.verdict_phrases(p.read_text(encoding="utf-8", errors="replace"))
    ok = len(ph) == 1 and ph[0] == "confirmed"
    return {"file": CHECKLIST_REL, "status": "confirmed" if ok else "not_confirmed", "pass": ok, "inputs_sha256": inputs}


def evaluate(repo: Path, python: str = sys.executable, data_root: Path | None = None) -> dict:
    repo = Path(repo)
    dirty = GV.dirty_paths(repo)
    if dirty:
        raise GV.GateRefused(f"{len(dirty)} uncommitted or untracked path(s) under ledger/ or research/ledger/ (first: {dirty[:5]})")
    ignored = GV.ignored_paths(repo)
    if ignored:
        raise GV.GateRefused(f"{len(ignored)} git-ignored path(s) under research/ledger/ (first: {ignored[:5]})")
    res = {"prereg": "research/ledger/PREREG_v3.md S5 (RUN3_PROMPT section 9)", "utc": time.strftime(GV.UTC_FORMAT, time.gmtime()),
           "git_head": GV._git(repo, "rev-parse", "HEAD").strip(), "evaluated_on": "a temporary clean git worktree of HEAD"}
    with GV.clean_checkout(repo) as (wt, state):
        research = wt / "research" / "ledger"
        conds = {CONDITIONS[0]: GV._guarded(lambda: cond1(wt, python, data_root)),
                 CONDITIONS[1]: GV._guarded(lambda: cond2(research)),
                 CONDITIONS[2]: GV._guarded(lambda: cond3(research)),
                 CONDITIONS[3]: GV._guarded(lambda: cond4(research)),
                 CONDITIONS[4]: GV._guarded(lambda: cond5(research)),
                 CONDITIONS[5]: GV._guarded(lambda: cond6(research), {"status": "error"})}
        me = Path(__file__).resolve()
        mine = wt / "ledger" / "scripts" / me.name
        res["gate_script"] = {"sha256": GV.sha(me), "identical_to_head": mine.is_file() and GV.sha(mine) == GV.sha(me)}
        prefixes = sorted({str(wt), os.path.realpath(wt), str(wt.parent), os.path.realpath(wt.parent)}, key=len, reverse=True)
    res["checkout_removed"] = state["removed"]
    conds = GV._scrub(conds, prefixes)
    res["conditions"] = conds
    failed = [k for k in CONDITIONS[:5] if conds[k].get("pass") is not True]
    c6 = conds[CONDITIONS[5]]
    res["conditions_1_to_5_hold"] = not failed
    res["all_conditions_hold"] = not failed and c6.get("pass") is True and res["gate_script"]["identical_to_head"]
    res["decision"] = (f"do not unblind: condition(s) {', '.join(failed)} failed (PREREG v3 S5)" if failed else
                       "conditions 1-5 hold; nothing is unblinded until a fresh reviewer confirms the checklist (condition 6)"
                       if c6.get("status") == "pending" else
                       "all six conditions hold: unblinding may be authorised (UNBLIND_h1.json)" if res["all_conditions_hold"] else
                       "do not unblind: condition 6 is not confirmed")
    return res


def gate_run(repo: Path) -> tuple[int, dict | None]:
    research = Path(repo) / "research" / "ledger"
    r1, r2, cl = research / REPORTS[1], research / REPORTS[2], research / CHECKLIST_REL
    if r2.exists() or GV._ever_committed(repo, f"research/ledger/{REPORTS[2]}"):
        raise GV.GateRefused("the gate has run twice: a third run is refused")
    if r1.exists() or GV._ever_committed(repo, f"research/ledger/{REPORTS[1]}"):
        if not r1.is_file():
            raise GV.GateRefused("run 1's report was committed and is gone: refused")
        prev = json.loads(r1.read_text(encoding="utf-8"))
        conds = prev.get("conditions") or {}
        failed = [k for k in CONDITIONS[:5] if (conds.get(k) or {}).get("pass") is not True]
        if prev.get("gate_run") != 1 or failed or (conds.get(CONDITIONS[5]) or {}).get("status") != "pending":
            raise GV.GateRefused(f"run 2 refused: run 1 did not pass conditions 1-5 with condition 6 pending ({failed})")
        if not cl.is_file():
            raise GV.GateRefused(f"commit {CHECKLIST_REL} before run 2")
        return 2, prev
    if cl.exists() or GV._ever_committed(repo, f"research/ledger/{CHECKLIST_REL}"):
        raise GV.GateRefused("the checklist exists before gate run 1: refused")
    return 1, None


def main(argv=None, repo: Path = REPO, data_root: Path | None = None) -> int:
    try:
        run, prev = gate_run(repo)
        res = evaluate(repo, sys.executable, data_root)
    except GV.GateRefused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    res["gate_run"] = run
    if run == 2:
        same = all(GV._canonical(res["conditions"][k]) == GV._canonical(prev["conditions"][k]) for k in CONDITIONS[:5])
        res["conditions_1_to_5_equal_run1"] = same
        res["run1_report_sha256"] = GV.sha(Path(repo) / "research" / "ledger" / REPORTS[1])
        res["all_conditions_hold"] = bool(res["all_conditions_hold"] and same)
    out = Path(repo) / "research" / "ledger" / REPORTS[run]
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({"gate_run": run, **{k: res["conditions"][k].get("pass") for k in CONDITIONS}, "decision": res["decision"]}))
    return 0 if res["all_conditions_hold"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
