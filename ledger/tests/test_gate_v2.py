"""The unblinding gate v2: its two runs (PREREG v2 S5.6, L14), the lock rules of condition 1 (L12, S5.1), git-ignored files and
archive members, on throwaway git repositories built from synthetic data by test_scoring_v2's builders. BRAINIR_DATA_DIR points
at a temporary folder; no real label, prediction or data file is read and the real tree's gate is never run."""

import hashlib
import json
import subprocess
import sys
import zipfile

import pandas as pd
import pytest

from .test_scoring_v2 import G, _commit, _dump, _git, _sha, build_gate_repo, gate_repo, v2_world  # noqa: F401 (fixtures)


def _research(repo):
    return repo / "research" / "ledger"


def _report(repo, run):
    return _research(repo) / "gates_v2" / f"UNBLINDING_GATE_run{run}.json"


def _review(repo, verdict):
    (_research(repo) / "reviews_v2" / "REVIEW_labels_v2.md").write_text(f"# Labels v2 review\n\n{verdict}\n")


def _checklist(repo, verdict="**Verdict: confirmed.**"):
    (_research(repo) / "reviews_v2" / "GATE_CHECKLIST.md").write_text(
        f"# Gate checklist\n\n{verdict}\n\nConditions 1-5 confirmed from the run-1 report; each amendment is a bug fix; nothing joined.\n")


# ---------------------------------------------------------------------------------------------------------------- two runs, each once
def test_a_failed_first_run_ends_the_collection(gate_repo):
    """Review probe A turned around (L14: 'A failed gate ends the collection'): rewriting the review after a failed run 1 and
    running again cannot produce a passing pair of reports."""
    repo = gate_repo
    _review(repo, "**Verdict: blocked.**")
    _commit(repo, "review: blocked")
    assert G.main([], repo=repo) == 1
    r1 = json.loads(_report(repo, 1).read_text())
    assert r1["gate_run"] == 1 and r1["conditions"]["3_review_and_verification"]["pass"] is False
    _commit(repo, "run-1 report")
    _review(repo, "**Verdict: usable.**")
    _checklist(repo)
    _commit(repo, "review rewritten + checklist")
    first = _sha(_report(repo, 1))
    assert G.main([], repo=repo) == 2  # run 2 refused: run 1 failed
    assert G.main([], repo=repo) == 2
    assert not _report(repo, 2).exists() and _sha(_report(repo, 1)) == first


def test_first_run_refused_when_a_checklist_exists_or_existed(gate_repo):
    """Review probe A2 turned around (S5.6: the first run precedes the checklist)."""
    repo = gate_repo
    _checklist(repo)
    _commit(repo, "checklist before any gate run")
    assert G.main([], repo=repo) == 2 and not _report(repo, 1).exists()
    (_research(repo) / "reviews_v2" / "GATE_CHECKLIST.md").unlink()
    _commit(repo, "checklist removed")
    assert G.main([], repo=repo) == 2 and not _report(repo, 1).exists()  # its history counts


def test_second_run_needs_the_checklist_and_a_third_run_is_refused(gate_repo):
    repo = gate_repo
    assert G.main([], repo=repo) == 1
    _commit(repo, "gate run 1")
    assert G.main([], repo=repo) == 2 and not _report(repo, 2).exists()  # no checklist yet: refused, nothing written
    _checklist(repo)
    _commit(repo, "checklist")
    assert G.main([], repo=repo) == 0
    r2 = json.loads(_report(repo, 2).read_text())
    assert r2["gate_run"] == 2 and r2["conditions_1_to_5_identical_to_run1"] is True and r2["conditions_differing_from_run1"] == []
    _commit(repo, "gate run 2")
    before = (_sha(_report(repo, 1)), _sha(_report(repo, 2)))
    assert G.main([], repo=repo) == 2 and (_sha(_report(repo, 1)), _sha(_report(repo, 2))) == before


def test_a_removed_report_does_not_reopen_the_gate(gate_repo):
    repo = gate_repo
    assert G.main([], repo=repo) == 1
    _commit(repo, "gate run 1")
    _report(repo, 1).unlink()
    _commit(repo, "run-1 report removed")
    assert G.main([], repo=repo) == 2 and not _report(repo, 1).exists()


def test_second_run_fails_when_conditions_1_to_5_differ(gate_repo):
    """S5.6: conditions 1-5 must come out identical (whole dicts, inputs included): a review rewritten between the runs with
    the same verdict changes condition 3."""
    repo = gate_repo
    assert G.main([], repo=repo) == 1
    _commit(repo, "gate run 1")
    _review(repo, "**Verdict: usable with caveats.**\n\nRewritten after the gate's first run.")
    _checklist(repo)
    _commit(repo, "review rewritten + checklist")
    assert G.main([], repo=repo) == 1
    r2 = json.loads(_report(repo, 2).read_text())
    assert r2["conditions_1_to_5_hold"] is True and r2["conditions"]["6_reviewer_checklist"]["pass"] is True
    assert r2["conditions_1_to_5_identical_to_run1"] is False and r2["conditions_differing_from_run1"] == ["3_review_and_verification"]
    assert r2["all_conditions_hold"] is False and "differ" in r2["decision"]


def test_second_run_records_a_checklist_that_is_not_exactly_confirmed(gate_repo):
    repo = gate_repo
    assert G.main([], repo=repo) == 1
    _commit(repo, "gate run 1")
    _checklist(repo, "**Verdict: signed.**")
    _commit(repo, "checklist")
    assert G.main([], repo=repo) == 1
    r2 = json.loads(_report(repo, 2).read_text())
    assert r2["conditions_1_to_5_identical_to_run1"] is True and r2["conditions"]["6_reviewer_checklist"]["status"] == "not_confirmed"
    assert r2["all_conditions_hold"] is False
    _commit(repo, "gate run 2")
    assert G.main([], repo=repo) == 2  # no third run to repair it


def test_conditions_1_to_5_hold_nothing_volatile(gate_repo):
    """Two evaluations in two temporary checkouts give identical condition 1-5 dicts (canonical JSON), even when a condition's
    error message names a file inside the checkout: checkout paths are written as `<checkout>`."""
    repo = gate_repo
    (_research(repo) / "labels_v2" / "agreement.json").unlink()
    _commit(repo, "agreement removed")
    a, b = G.evaluate(repo), G.evaluate(repo)
    err = a["conditions"]["4_kappa"]["error"]
    assert "<checkout>/research/ledger/labels_v2/agreement.json" in err and "ledger_gate_v2_" not in err
    assert all(G._canonical(a["conditions"][k]) == G._canonical(b["conditions"][k]) for k in G.CONDITIONS[:5])
    assert "ledger_gate_v2_" not in json.dumps(a["conditions"]) and a["utc"] and a["git_head"] == b["git_head"]


@pytest.mark.parametrize("text, ok", [
    ("Verdict: confirmed", True), ("**Verdict: Confirmed.**", True), ("- Verdict: confirmed", True), ("**Verdict:** confirmed", True),
    ("Verdict: not confirmed", False), ("**Verdict: signed.**", False), ("Verdict: confirmed, with two remarks", False),
    ("Fill in. Verdict: confirmed / not confirmed\n\nVerdict: not confirmed", False), ("Verdict: confirmed / not confirmed", False),
    ("Verdict: confirmed\n\nVerdict: confirmed", False), ("## Verdict\n\nconfirmed", False), ("No verdict.", False)])
def test_checklist_verdict_is_exactly_confirmed(tmp_path, text, ok):
    r = tmp_path / "research"
    (r / "reviews_v2").mkdir(parents=True)
    (r / "reviews_v2" / "GATE_CHECKLIST.md").write_text(f"# Gate checklist\n\n{text}\n")
    c6 = G.cond6_checklist(r)
    assert c6["pass"] is ok and c6["status"] == ("confirmed" if ok else "not_confirmed")


def test_verdict_phrases_take_the_whole_line():
    """Review probe E turned around: no prefix match, no template line, no second verdict line."""
    assert G.review_class(G.verdict_phrase("Verdict: usable only after the two blockers below are fixed")) == "unparsed"
    assert G.review_class(G.verdict_phrase("Verdict: usable? no: blocked")) == "unparsed"
    assert G.verdict_phrase("Verdict: confirmed / not confirmed\n\nVerdict: not confirmed") is None
    assert G.review_class(G.verdict_phrase("**Verdict: usable with caveats.**")) == "usable_with_caveats"
    assert G.review_class(G.verdict_phrase("> Verdict: `blocked`")) == "blocked"
    assert G.review_class(None) == "no_single_verdict_line"


# ---------------------------------------------------------------------------------------------------------------- locks (L12)
def test_relocking_is_refused_and_a_relocked_lock_fails_condition_1(gate_repo):
    """Review probe H turned around (L12: 'the lock file is never edited'): lock2.py's writers refuse an existing lock, and a
    lock rewritten by hand and committed again has two commits, which fails condition 1."""
    repo = gate_repo
    research = _research(repo)
    p = research / "labels_v2" / "type_labels.csv"
    tl = pd.read_csv(p)
    i = tl.index[(tl["front"] == "no") & ~tl["exposed"]][0]
    tl.loc[i, "front"] = "yes"  # a label changed after the lock ...
    tl.to_csv(p, index=False)
    before = _sha(research / "LOCK_labels_v2.json")
    for stage in ("labels", "scoring", "labelcode", "prereg"):
        r = subprocess.run([sys.executable, str(repo / "ledger" / "scripts" / "lock2.py"), stage], cwd=repo, capture_output=True, text=True,
                           check=False)
        assert r.returncode != 0 and "never edited" in r.stderr, stage
    assert _sha(research / "LOCK_labels_v2.json") == before
    rec = json.loads((research / "LOCK_labels_v2.json").read_text())
    rec["labels"]["research/ledger/labels_v2/type_labels.csv"] = _sha(p)  # ... and re-locked by hand
    _dump(research, "LOCK_labels_v2.json", rec)
    _commit(repo, "relabel + relock")
    c1 = G.evaluate(repo)["conditions"]["1_locks"]
    lk = c1["locks"]["LOCK_labels_v2.json"]
    assert lk["checks"]["lock2.py"]["pass"] is True and lk["commits"]["n_commits"] == 2 and lk["pass"] is False and c1["pass"] is False


def test_label_code_and_scoring_locks_precede_the_first_v2_session(tmp_path, v2_world, monkeypatch):
    repo = build_gate_repo(tmp_path, v2_world, monkeypatch, session_starts=("2026-11-21T03:00:00Z", "2026-11-20T23:59:59Z"))
    c1 = G.evaluate(repo)["conditions"]["1_locks"]
    bf = c1["locked_before_first_v2_session"]
    assert bf["earliest_session_start_utc"] == "2026-11-20T23:59:59Z" and bf["n_session_manifests"] == 2  # _status.json skipped
    assert bf["pass"] is False and not any(v["pass"] for v in bf["locks"].values()) and c1["pass"] is False


def test_session_manifests_are_required(tmp_path, v2_world, monkeypatch):
    repo = build_gate_repo(tmp_path, v2_world, monkeypatch, session_starts=())
    c1 = G.evaluate(repo)["conditions"]["1_locks"]
    assert c1["locked_before_first_v2_session"]["pass"] is False and c1["locked_before_first_v2_session"]["problems"]
    assert c1["pass"] is False


def test_v2_locks_must_carry_their_chains(gate_repo):
    research = _research(gate_repo)
    rec = json.loads((research / "LOCK_labels_v2.json").read_text())
    assert G._chain(research, "LOCK_labels_v2.json", rec)["required_keys_absent"] == []
    rec.pop("scoring_v2_lock_sha256")
    assert G._chain(research, "LOCK_labels_v2.json", rec)["required_keys_absent"] == ["scoring_v2_lock_sha256"]


def test_an_amendment_row_for_a_label_file_does_not_count(gate_repo):
    """Review probe C turned around (L12: 'Rules, records, labels and predictions are never amended')."""
    repo = gate_repo
    research = _research(repo)
    p = research / "labels_v2" / "type_labels.csv"
    old = _sha(p)
    p.write_text(p.read_text().replace(",no,", ",yes,", 1))
    with open(research / "AMENDMENTS_v2.jsonl", "a") as fh:
        fh.write(json.dumps({"utc": "2026-11-21T02:00:00Z", "path": "research/ledger/labels_v2/type_labels.csv", "old": old, "new": _sha(p),
                             "reason": "x", "old_rev": "0" * 40, "v2_sessions_started": True, "v2_records_existed": True,
                             "crash_fix": False, "after_unblinding": False}) + "\n")
    _commit(repo, "a label table changed, with an amendment row")
    c1 = G.evaluate(repo)["conditions"]["1_locks"]
    lk = c1["locks"]["LOCK_labels_v2.json"]["checks"]["lock2.py"]
    assert "research/ledger/labels_v2/type_labels.csv" in lk["changed"] and lk["amended"] == []
    assert [r["path"] for r in c1["amendment_rows_ignored"]] == ["research/ledger/labels_v2/type_labels.csv"] and c1["pass"] is False


# ---------------------------------------------------------------------------------------------------------------- git-ignored files
def test_gate_refuses_git_ignored_files_under_research_ledger(gate_repo):
    """Review probe B turned around: a git-ignored file is invisible to `git status --porcelain` and absent from the clean
    checkout; the gate refuses (exit 2) until it is committed with `git add -f` (or removed)."""
    repo = gate_repo
    research = _research(repo)
    (repo / ".gitignore").write_text("*.parquet\n")
    (research / "predictions_v2" / "B1r" / "replicates.parquet").write_bytes(b"PAR1 synthetic")
    _commit(repo, "a parquet left out by a plain git add")
    assert G.dirty_paths(repo) == [] and G.ignored_paths(repo) == ["research/ledger/predictions_v2/B1r/replicates.parquet"]
    with pytest.raises(G.GateRefused, match="git-ignored"):
        G.evaluate(repo)
    assert G.main([], repo=repo) == 2 and not _report(repo, 1).exists()
    _git(repo, "add", "-f", "research/ledger/predictions_v2/B1r/replicates.parquet")
    _commit(repo, "force-added")
    assert G.ignored_paths(repo) == []


# ---------------------------------------------------------------------------------------------------------------- archive members
def _zip(path, members):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)


def test_archive_members(tmp_path):
    """S5.1: `<archive>.zip:<member>` keys, outside the repository: from the archive under <data root>/raw/external/ (any depth),
    else from the copy zenodo_remote_zip.py extracted; neither -> a missing archive, which fails."""
    data = tmp_path / "data"
    member = b"model: synthetic\n"
    good = hashlib.sha256(member).hexdigest()
    recs = {"LOCK_prereg_v1.json": {"authors_zenodo_configs_pinned": {"A.zip:sim/run_config.yaml": good, "B.zip:sim/x.yaml": good}}}
    res = G.archive_members(recs, data)
    assert res["pass"] is False and res["archives_missing"] == ["A.zip", "B.zip"] and res["n_pinned"] == 2
    _zip(data / "raw" / "external" / "deep" / "A.zip", {"sim/run_config.yaml": member})
    ext = data / "raw" / "external" / "pugliese_2026_zenodo" / "B" / "sim" / "x.yaml"
    ext.parent.mkdir(parents=True)
    ext.write_bytes(member)
    res = G.archive_members(recs, data)
    a, b = res["members"]["A.zip:sim/run_config.yaml"], res["members"]["B.zip:sim/x.yaml"]
    assert res["pass"] is True and (a["source"], b["source"]) == ("zip", "extracted_member") and a["archives"] == ["raw/external/deep/A.zip"]
    ext.write_bytes(b"changed\n")
    assert G.archive_members(recs, data)["pass"] is False
    ext.write_bytes(member)
    _zip(data / "raw" / "external" / "deep" / "A.zip", {"sim/other.yaml": member})  # the member is not in the archive
    res = G.archive_members(recs, data)
    assert res["pass"] is False and res["members"]["A.zip:sim/run_config.yaml"]["member_found"] is False
    _zip(data / "raw" / "external" / "deep" / "A.zip", {"sim/run_config.yaml": b"other bytes\n"})
    assert G.archive_members(recs, data)["pass"] is False
    two = {"L1": {"s": {"A.zip:sim/run_config.yaml": good}}, "L2": {"s": {"A.zip:sim/run_config.yaml": "f" * 64}}}
    assert G.archive_members(two, data)["conflicting_pins"] == ["A.zip:sim/run_config.yaml"]


def test_archive_members_in_condition_1(tmp_path, v2_world, monkeypatch):
    member = b"model: synthetic\n"
    repo = build_gate_repo(tmp_path, v2_world, monkeypatch, zenodo={"A.zip:sim/run_config.yaml": hashlib.sha256(member).hexdigest()})
    c1 = G.evaluate(repo)["conditions"]["1_locks"]
    assert c1["archive_members"]["archives_missing"] == ["A.zip"] and c1["pass"] is False
    assert c1["locks"]["LOCK_prereg_v1.json"]["pass"] is True  # neither lock tool checks the key: only the gate's own check fails
    _zip(tmp_path / "data" / "raw" / "external" / "A.zip", {"sim/run_config.yaml": member})  # BRAINIR_DATA_DIR = tmp_path/data
    c1 = G.evaluate(repo)["conditions"]["1_locks"]
    assert c1["archive_members"]["pass"] is True and c1["pass"] is True
