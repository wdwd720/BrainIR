"""lock2.py (PREREG v2 L12, S5.1) on throwaway git repositories: a copy of the real tool runs by subprocess inside the temporary
repository (its REPO is that repository), with HOME pointing at a temporary folder (`amend` reads ~/ledger_rooms/run2/_manifests)
and no global git configuration; `check` and the amendment predicate are also called in-process with an explicit repository.
The writers are never called in-process (their module paths point at the real tree). Every UNBLIND.json is written inside a
pytest temporary folder."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import pytest

from brainir_ledger import REPO

SRC = REPO / "ledger" / "scripts" / "lock2.py"
_spec = importlib.util.spec_from_file_location("lock2_under_test", SRC)
L2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(L2)

FILES = {
    "ledger/scripts/run_arms.py": "# prediction side\n",
    "ledger/scripts/gha.py": "# prediction side (P4b)\n",
    "ledger/scripts/b4v2.py": "# prediction side (P4b)\n",
    "ledger/scripts/labels2_collect.py": "# v2 label side\n",
    "ledger/scripts/labels_collect.py": "# frozen label side (hashed by the v1 prereg lock)\n",
    "ledger/scripts/gate_v2.py": "# the gate\n",
    "ledger/scripts/score_v2.py": "# scoring v2\n",
    "ledger/src/brainir_ledger/typescreen_v2.py": "# prediction side\n",
    "ledger/src/brainir_ledger/scoring/pipeline.py": "# scoring v1\n",
    "ledger/src/brainir_ledger/scoring_v2/pipeline_v2.py": "# scoring v2\n",
    "ledger/src/brainir_ledger/labels/aggregate.py": "# label side\n",
    "ledger/tests/test_typescreen.py": "# a prediction-side test\n",
    "ledger/tests/test_scoring_v2.py": "# a scoring test\n",
    "ledger/tests/test_gate_v2.py": "# a gate test\n",
    "ledger/tests/test_lock2.py": "# a lock-tool test\n",
    "ledger/tests/test_labels2_collect.py": "# a label-side test\n",
    "ledger/tests/test_audit.py": "# a label-side test (labels_audit)\n",
    "research/ledger/PREREG.md": "rulebook v1\n",
    "research/ledger/PREREG_v2.md": "rulebook v2\n",
    "research/ledger/RUN2_PROMPT.md": "spec\n",
    "research/ledger/IMPLEMENTATION_v2.md": "rule -> code\n",
    "research/ledger/kit_v2/PROMPT_READER.md": "reader prompt\n",
    "research/ledger/kit_v2/CHANGELOG.md": "kit changelog\n",
    "research/ledger/kit_v2/exposed_types.csv": "name_as_given,manc_types,resolved\n",
    "research/ledger/labels/records.jsonl": "{}\n",
    ".gitignore": "*.parquet\n*.log\n",
}


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git(w, *args):
    return subprocess.run(["git", *args], cwd=w["repo"], capture_output=True, text=True, check=True, env=w["env"]).stdout


def _commit(w, msg):
    _git(w, "add", "-A")
    _git(w, "commit", "-q", "--no-verify", "-m", msg)


def _lock2(w, *args):
    return subprocess.run([sys.executable, str(w["repo"] / "ledger" / "scripts" / "lock2.py"), *args], cwd=w["repo"],
                          capture_output=True, text=True, env=w["env"], check=False)


@pytest.fixture
def lock_repo(tmp_path):
    repo, home = tmp_path / "repo", tmp_path / "home"
    home.mkdir()
    res = repo / "research" / "ledger"
    for rel, text in {**FILES, "ledger/scripts/lock2.py": SRC.read_text()}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)

    def h(rel):
        return {rel: _sha(repo / rel)}
    for name, rec in (("LOCK_prereg_v1.json", {"prereg": h("research/ledger/PREREG.md"), "frozen_code": h("ledger/scripts/labels_collect.py")}),
                      ("LOCK_predictions_v1.json", {"arms_locked": {}}),
                      ("LOCK_labels_v1.json", {"labels": h("research/ledger/labels/records.jsonl")}),
                      ("LOCK_labels_v1_1.json", {"labels": {}})):
        (res / name).write_text(json.dumps(rec))
    w = {"repo": repo, "res": res, "home": home, "env": {**os.environ, "HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1"}}
    _git(w, "init", "-q")
    for k, v in (("user.name", "test"), ("user.email", "test@example.invalid"), ("core.autocrlf", "false"), ("commit.gpgsign", "false")):
        _git(w, "config", k, v)
    _commit(w, "synthetic repository")
    return w


def _last_json(capsys):
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


# ---------------------------------------------------------------------------------------------------------------- writers
def test_writers_write_each_lock_once(lock_repo):
    """L12: 'the lock file is never edited' -> every writer refuses an existing (or once committed) lock file."""
    w = lock_repo
    res = w["res"]
    for stage, name in (("prereg", "LOCK_prereg_v2.json"), ("labelcode", "LOCK_labelcode_v2.json"), ("scoring", "LOCK_scoring_v2.json")):
        r = _lock2(w, stage)
        assert r.returncode == 0, r.stderr
        before = (res / name).read_bytes()
        r = _lock2(w, stage)
        assert r.returncode != 0 and "never edited" in r.stderr and (res / name).read_bytes() == before, stage
    sc = json.loads((res / "LOCK_scoring_v2.json").read_text())
    assert set(sc["scoring_code"]) == {"ledger/scripts/gate_v2.py", "ledger/scripts/score_v2.py", "ledger/src/brainir_ledger/scoring/pipeline.py",
                                       "ledger/src/brainir_ledger/scoring_v2/pipeline_v2.py", "ledger/tests/test_scoring_v2.py",
                                       "ledger/tests/test_gate_v2.py", "ledger/tests/test_lock2.py"}
    lc = json.loads((res / "LOCK_labelcode_v2.json").read_text())
    assert set(lc["label_code"]) == {"ledger/scripts/labels2_collect.py", "ledger/scripts/labels_collect.py", "ledger/scripts/lock2.py",
                                     "ledger/scripts/gate_v2.py", "ledger/src/brainir_ledger/labels/aggregate.py",
                                     "ledger/tests/test_labels2_collect.py", "ledger/tests/test_audit.py"}
    for rec in (sc, lc):
        assert rec["prereg_v2_lock_sha256"] == _sha(res / "LOCK_prereg_v2.json") and rec["utc"]
    _commit(w, "locks")
    (res / "LOCK_scoring_v2.json").unlink()
    _commit(w, "scoring lock removed")
    r = _lock2(w, "scoring")  # a lock committed once is not written again
    assert r.returncode != 0 and "committed before" in r.stderr and not (res / "LOCK_scoring_v2.json").exists()


def test_labels_lock_needs_both_code_locks_chains_them_and_refuses_untracked_files(lock_repo, capsys):
    """B2 / M2: the labels lock chains the prereg, label-code and scoring locks, and hashes nothing git does not track."""
    w = lock_repo
    res = w["res"]
    assert _lock2(w, "prereg").returncode == 0 and _lock2(w, "labelcode").returncode == 0
    lab = res / "labels_v2"
    for rel, text in (("records.jsonl", "{}\n"), ("type_labels.csv", "manc_type,front\n"), ("raw/pass1/s1/records.valid.jsonl", "{}\n"),
                      ("raw/pass1/s1/session.log", "a log\n"), ("sessions/s1.json", json.dumps({"runs": [{"start_utc": "2026-11-21T01:00:00Z"}]}))):
        (lab / rel).parent.mkdir(parents=True, exist_ok=True)
        (lab / rel).write_text(text)
    r = _lock2(w, "labels")
    assert r.returncode != 0 and "LOCK_scoring_v2.json is missing" in r.stderr
    assert _lock2(w, "scoring").returncode == 0
    r = _lock2(w, "labels")
    assert r.returncode != 0 and "git add -f" in r.stderr and not (res / "LOCK_labels_v2.json").exists()
    _git(w, "add", "research/ledger/labels_v2")  # a plain add leaves the git-ignored log out
    r = _lock2(w, "labels")
    assert r.returncode != 0 and "research/ledger/labels_v2/raw/pass1/s1/session.log" in r.stderr and "*.log" in r.stderr
    _git(w, "add", "-f", "research/ledger/labels_v2/raw/pass1/s1/session.log")
    r = _lock2(w, "labels")
    assert r.returncode == 0, r.stderr
    rec = json.loads((res / "LOCK_labels_v2.json").read_text())
    for key, name in (("prereg_v2_lock_sha256", "LOCK_prereg_v2.json"), ("labelcode_v2_lock_sha256", "LOCK_labelcode_v2.json"),
                      ("scoring_v2_lock_sha256", "LOCK_scoring_v2.json")):
        assert rec[key] == _sha(res / name), key
    assert "research/ledger/labels_v2/raw/pass1/s1/session.log" in rec["raw"] and "research/ledger/labels_v2/sessions/s1.json" in rec["sessions"]
    assert L2.check(res / "LOCK_labels_v2.json", repo=w["repo"]) == 0
    capsys.readouterr()
    (res / "LOCK_scoring_v2.json").write_text("{}")  # the chained scoring lock changes: the labels lock fails
    assert L2.check(res / "LOCK_labels_v2.json", repo=w["repo"]) == 1
    assert _last_json(capsys)["changed"] == ["LOCK_scoring_v2.json"]


def test_predictions_lock_refuses_ignored_files_and_binds_prediction_code_only(lock_repo):
    """M2: a git-ignored arm file (the frozen write_arm writes replicates.parquet) is refused until `git add -f`; the binding
    `code` section holds prediction-side code only (label and scoring code are bound by their own locks)."""
    w = lock_repo
    res = w["res"]
    assert _lock2(w, "prereg").returncode == 0
    arm = res / "predictions_v2" / "B1r"
    arm.mkdir(parents=True)
    (arm / "types.csv").write_text("manc_type,primary_score\n")
    (arm / "replicates.parquet").write_bytes(b"PAR1 synthetic")
    _commit(w, "B1r tables (a plain git add leaves the parquet out)")
    args = ("predictions", "B1r", "B3=G3 v2 item 4' failed", "--platform", "test")
    r = _lock2(w, *args)
    assert r.returncode != 0 and "replicates.parquet" in r.stderr and "git add -f" in r.stderr
    assert not (res / "LOCK_predictions_v2.json").exists()
    _git(w, "add", "-f", "research/ledger/predictions_v2/B1r/replicates.parquet")
    r = _lock2(w, *args)
    assert r.returncode == 0, r.stderr
    rec = json.loads((res / "LOCK_predictions_v2.json").read_text())
    assert set(rec["arms_locked"]["B1r"]) == {"research/ledger/predictions_v2/B1r/types.csv", "research/ledger/predictions_v2/B1r/replicates.parquet"}
    assert rec["arms_not_locked"] == {"B3": "G3 v2 item 4' failed"} and rec["prereg_v2_lock_sha256"] == _sha(res / "LOCK_prereg_v2.json")
    assert set(rec["code"]) == {"ledger/scripts/run_arms.py", "ledger/scripts/gha.py", "ledger/scripts/b4v2.py",
                                "ledger/src/brainir_ledger/typescreen_v2.py", "ledger/tests/test_typescreen.py"}


# ---------------------------------------------------------------------------------------------------------------- amendments
def _row(path, old, new, **over):
    """A row as `lock2.py amend` writes it (before the first v2 session, before unblinding, not a crash fix), with overrides."""
    return {"utc": "2026-11-21T02:00:00Z", "path": path, "old": old, "new": new, "reason": "bug fix", "old_rev": "0" * 40,
            "v2_sessions_started": False, "v2_records_existed": False, "crash_fix": False, "after_unblinding": False, **over}


def test_check_honours_only_allowed_amendment_rows(lock_repo, capsys):
    """Review M1 turned around (PREREG v2 L12): a row counts only for a path `amend` accepts that no v1 lock hashes, written by
    `amend` (its flags), and allowed when written; every successor of a hash is followed."""
    w = lock_repo
    repo, res = w["repo"], w["res"]
    (res / "labels_v2").mkdir()
    (res / "labels_v2" / "type_labels.csv").write_text("manc_type,front\nDNa01,no\n")
    files = ["ledger/scripts/run_arms.py", "ledger/scripts/gha.py", "ledger/scripts/b4v2.py", "ledger/scripts/score_v2.py",
             "ledger/scripts/gate_v2.py", "ledger/scripts/labels_collect.py", "research/ledger/kit_v2/PROMPT_READER.md",
             "research/ledger/kit_v2/CHANGELOG.md", "research/ledger/labels_v2/type_labels.csv"]
    locked = {f: _sha(repo / f) for f in files}
    (res / "LOCK_example_v2.json").write_text(json.dumps({"binding": locked}))
    for f in files:
        (repo / f).write_text((repo / f).read_text() + "changed\n")
    now = {f: _sha(repo / f) for f in files}

    def row(f, **over):
        return _row(f, locked[f], now[f], **over)
    no_flags = row("ledger/scripts/b4v2.py")
    for k in L2.AMEND_FLAGS:
        no_flags.pop(k)
    rows = [row("ledger/scripts/run_arms.py"),  # a code bug fix: counts
            no_flags,  # not a row amend writes
            row("ledger/scripts/score_v2.py", crash_fix=True, after_unblinding=True),  # a crash fix after unblinding: counts
            row("ledger/scripts/gate_v2.py", crash_fix=True, after_unblinding=True),  # after unblinding, not the scoring v2 code
            row("ledger/scripts/labels_collect.py"),  # hashed by a v1 lock
            row("research/ledger/kit_v2/PROMPT_READER.md", v2_sessions_started=True),  # a kit prompt after the first session
            row("research/ledger/kit_v2/CHANGELOG.md"),  # the kit changelog before the first session: counts
            row("research/ledger/labels_v2/type_labels.csv"),  # labels are never amended
            row("ledger/scripts/gha.py"), _row("ledger/scripts/gha.py", locked["ledger/scripts/gha.py"], "c" * 64)]  # two successors
    (res / "AMENDMENTS_v2.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows) + "not json\n")
    assert L2.check(res / "LOCK_example_v2.json", repo=repo) == 1
    out = _last_json(capsys)
    assert set(out["amended"]) == {"ledger/scripts/run_arms.py", "ledger/scripts/score_v2.py", "research/ledger/kit_v2/CHANGELOG.md",
                                   "ledger/scripts/gha.py"}
    assert set(out["changed"]) == {"ledger/scripts/b4v2.py", "ledger/scripts/gate_v2.py", "ledger/scripts/labels_collect.py",
                                   "research/ledger/kit_v2/PROMPT_READER.md", "research/ledger/labels_v2/type_labels.csv"}
    assert len(out["amendment_rows_ignored"]) == 6 and {"line": 11, "path": None, "problem": "invalid JSON"} in out["amendment_rows_ignored"]
    (res / "LOCK_labels_v1_1.json").unlink()  # a v1 lock missing: no row can be shown to be allowed
    assert L2.check(res / "LOCK_example_v2.json", repo=repo) == 1
    out = _last_json(capsys)
    assert out["amended"] == [] and len(out["changed"]) == len(files)


def test_amend_writes_only_rows_the_shared_predicate_accepts(lock_repo):
    w = lock_repo
    repo, res = w["repo"], w["res"]
    amend = res / "AMENDMENTS_v2.jsonl"
    (repo / "ledger" / "scripts" / "run_arms.py").write_text("# fixed\n")
    r = _lock2(w, "amend", "ledger/scripts/run_arms.py", "--reason", "bug fix")
    assert r.returncode == 0, r.stderr
    row = json.loads(amend.read_text().splitlines()[-1])
    assert L2.amendment_row_problem(row, L2._v1_hashed(repo)) is None
    assert (row["v2_sessions_started"], row["crash_fix"], row["after_unblinding"]) == (False, False, False)
    (res / "kit_v2" / "exposed_types.csv").write_text("changed\n")
    (repo / "ledger" / "scripts" / "labels_collect.py").write_text("changed\n")
    for path in ("research/ledger/kit_v2/exposed_types.csv",  # a kit file other than the prompts and the changelog
                 "ledger/scripts/labels_collect.py",  # hashed by a v1 lock
                 "ledger/scripts/gate_v2.py",  # unchanged
                 "research/ledger/labels/records.jsonl"):  # records are never amended
        assert _lock2(w, "amend", path, "--reason", "x").returncode != 0, path
    (repo / "research" / "ledger" / "kit_v2" / "PROMPT_READER.md").write_text("restated\n")
    manifests = w["home"] / "ledger_rooms" / "run2" / "_manifests"
    manifests.mkdir(parents=True)
    (manifests / "pass1-x.json").write_text("{}")  # the first v2 label session has started
    r = _lock2(w, "amend", "research/ledger/kit_v2/PROMPT_READER.md", "--reason", "x")
    assert r.returncode != 0 and "first v2 label session" in r.stderr
    (res / "UNBLIND.json").write_text("{}")  # inside the pytest temporary folder only
    assert _lock2(w, "amend", "ledger/scripts/run_arms.py", "--reason", "x").returncode != 0  # after unblinding: no bug fix
    (repo / "ledger" / "scripts" / "score_v2.py").write_text("# crash fixed\n")
    assert _lock2(w, "amend", "ledger/scripts/score_v2.py", "--reason", "x").returncode != 0  # not marked --crash-fix
    r = _lock2(w, "amend", "ledger/scripts/score_v2.py", "--reason", "crash", "--crash-fix")
    assert r.returncode == 0, r.stderr
    rows = amend.read_text().splitlines()
    row = json.loads(rows[-1])
    assert len(rows) == 2 and row["crash_fix"] and row["after_unblinding"] and row["v2_sessions_started"]
    assert L2.amendment_row_problem(row, L2._v1_hashed(repo)) is None
