"""Post-lock review room builder (scripts/p3/make_postlock_review_room.py) on a FAKE repository tree.

Covered: only explicit sources enter; the denylist; redaction (code still parses, JSON stays valid); the name, content,
answer-token and guard-readability layers; staging (a failed build leaves no room); --check; --update; the reviewer prompts.
The real oracle, results and rooms are never read. Forbidden tokens are assembled at run time, so this file carries none.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p3"))
import make_postlock_review_room as PR  # noqa: E402

BENCH = "dng" + "100"
DATASET = "male" + "-cns"
FAKE_TOKEN = "Zq" + "Tok7"          # a stand-in answer token; the real ones are never used here

# (path in the fake repository, text) of every source the room must contain, and where it lands
SOURCES = {
    "benchmarks/state_discovery_v1/PROTOCOL.md": ("# Protocol v3\n", "docs/PROTOCOL.md"),
    "research/phase3/review_contracts/POSTLOCK_COMMON.txt": ("COMMON CONTRACT: read results/HIDDEN_EVALUATIONS.md\n",
                                                             "docs/review_contracts/POSTLOCK_COMMON.txt"),
    **{f"research/phase3/review_contracts/POSTLOCK_{x}_TASK.txt": (f"TASK {x}\n", f"docs/review_contracts/POSTLOCK_{x}_TASK.txt")
       for x in "SCYRV"},
    "research/phase3/METHOD_LOCK.json": ('{"method": "brainir_state_v1"}\n', "METHOD_LOCK.json"),
    "phase3/src/brainir_state/__init__.py": ('"""pkg"""\n', "src/brainir_state/__init__.py"),
    "phase3/src/brainir_state/evaluate.py": (f'NAME = "{DATASET}:v1"\n\n\ndef f(x):\n    return x\n', "src/brainir_state/evaluate.py"),
    "phase3/src/brainir_state/methods/brainir_state_v1.py": ("def fit():\n    return 1\n", "src/brainir_state/methods/brainir_state_v1.py"),
    "scripts/p3/level_c.py": ("print('level c')\n", "scripts/level_c.py"),
    "scripts/p3/devrun_site/sitecustomize.py": ("import sys\n", "scripts/devrun_site/sitecustomize.py"),
    "scripts/p3/p3modal/remote.py": ("X = 1\n", "scripts/p3modal/remote.py"),
    "research/phase3/tournament/r3v3_x/AGGREGATE_developer_facing.json": ('{"rank": 1}\n',
                                                                          "results/tournament/r3v3_x/AGGREGATE_developer_facing.json"),
    "research/phase3/tournament/r3v3_x/method.json": ('{"k": 3, "wall_s": 4242}\n', "results/tournament/r3v3_x/method.json"),
    "research/phase3/tournament/final_b/ROUND_DECISION.json": ('{"winner": "m"}\n', "results/tournament/final_b/ROUND_DECISION.json"),
    "research/phase3/tournament/_failed/r3_attempt2/x.json": ('{"failed": true}\n', "results/tournament/_failed/r3_attempt2/x.json"),
    "research/phase3/tournament/RERANK_V3.md": ("# rerank\n", "results/tournament/RERANK_V3.md"),
    "research/phase3/level_c/01/level_c_results.json": (json.dumps({"system": f"{DATASET} net", "C": 0.5}) + "\n",
                                                        "results/level_c/01/level_c_results.json"),
    "research/phase3/ablations/final/SUMMARY.json": ('{"ablation": "no_markov"}\n', "results/ablations/final/SUMMARY.json"),
    "research/phase3/counterexamples/final_real/SUMMARY.json": ('{"found": 0}\n', "results/counterexamples/final_real/SUMMARY.json"),
    "research/phase3/counterexamples/final_real/jobs/j1.json": ('{"job": 1}\n', "results/counterexamples/final_real/jobs/j1.json"),
    "research/phase3/postlock_infra/sim_equivalence.json": ('{"equal": true}\n', "results/postlock_infra/sim_equivalence.json"),
    "research/phase3/review_g/results_v1.json": ('{"traps": 3}\n', "results/review_g/results_v1.json"),
    "research/phase3/review_g/REVIEW_G_TRAPS.md": ("# traps\n", "results/review_g/REVIEW_G_TRAPS.md"),
    "benchmarks/state_discovery_v1/calibration.json": ('{"tau_D": 0.092}\n', "results/benchmark/calibration.json"),
    "benchmarks/state_discovery_v1/public/tolerances.json": ('{"markov": 1e-4}\n', "results/benchmark/tolerances.json"),
    "benchmarks/state_discovery_v1/public/systems_public.json": ('{"net1": {}}\n', "results/benchmark/systems_public.json"),
    "benchmarks/state_discovery_v1/public/synthetic_dev_suite.json": ('{"dev": []}\n', "results/benchmark/synthetic_dev_suite.json"),
    "benchmarks/state_discovery_v1/BENCHMARK_LOCK.json": ('{"files": {}}\n', "results/benchmark/BENCHMARK_LOCK.json"),
    "research/phase3/SELF_AUDIT.json": ('{"checks": []}\n', "results/SELF_AUDIT.json"),
    "research/phase3/SELF_AUDIT.md": ("# self-audit\n", "results/SELF_AUDIT.md"),
    "research/phase3/COMPUTE_SUMMARY.json": ('{"usd": 1}\n', "results/COMPUTE_SUMMARY.json"),
    "research/phase3/COMPUTE_SUMMARY.md": ("# compute\n", "results/COMPUTE_SUMMARY.md"),
    "research/phase3/HIDDEN_EVALUATIONS.md": ("| time | run |\n", "results/EVALUATION_LOG.md"),
    "research/phase3/LEVELB_LOG.md": ("# Level B log\n", "results/LEVELB_LOG.md"),
    "research/phase3/COSTS_LEDGER.md": ("# costs\n", "results/COSTS_LEDGER.md"),
    # reviewer V's inputs: the one file of research/phase3/reviews/ that may enter, the billed costs, the snapshot provenance
    "research/phase3/reviews/POSTLOCK_RESOLUTION.md": ("# resolution\n", "docs/POSTLOCK_RESOLUTION.md"),
    "research/phase3/MODAL_BILLING.json": ('{"total_usd": 1}\n', "results/MODAL_BILLING.json"),
    "research/phase3/MODAL_BILLING.md": ("# billing\n", "results/MODAL_BILLING.md"),
    "research/phase3/POSTLOCK_PROVENANCE.json": ('{"key": "k"}\n', "results/POSTLOCK_PROVENANCE.json"),
    "research/phase3/REPORT_WORKING.md": ("# Draft report\n", "PHASE3_REPORT.md"),
    "phase3/cleanroom/pyproject.toml": ('[project]\nname = "room"\n', "pyproject.toml"),
    ".python-version": ("3.12.14\n", ".python-version"),
}
GENERATED = {"docs/goal4.md", "CLAUDE.md", "README.md", "MANIFEST.json"}
# files that must never enter: outside the explicit list, or inside an included directory but denied
DECOYS = [
    "PHASE2_REPORT.md", "research/phase2/HIDDEN_EVAL_LOG.md", "research/LOG.md", "CLAUDE.md", f"benchmarks/{BENCH}_walking_cpg/answer.md",
    f"benchmarks/{BENCH}/oracle/oracle.json", f"benchmarks/{BENCH}/evaluator/evaluate.py", "data/phase3/hidden/index.jsonl",
    "benchmarks/state_discovery_v1/hidden/salt.json", "benchmarks/state_discovery_v1/generator/truth/t.json",
    "research/phase3/reviews/F_leakage.md", "research/phase3/reviews/POSTLOCK_L.md", "research/phase3/review_contracts/POSTLOCK_L_TASK.txt", "research/phase3/REVIEW_PLAN.md",
    "research/phase3/review_g/suite_record.json", "research/phase3/tournament/_refcache/net1.json", "research/phase3/level_c/01/truth/t.json",
    "research/phase3/counterexamples/final_real/salt_record.json",
]
EXCLUDED_PREFIXES = {"research/phase3/tournament/_refcache/", "research/phase3/level_c/01/truth/",
                     "research/phase3/counterexamples/final_real/salt_record.json", "phase3/src/brainir_state/__pycache__/"}


def _w(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    return p


def _goal4(sections=range(93)) -> str:
    parts = [f"# Phase 3 specification (follows the {BENCH} benchmark)\n"]
    for n in sections:
        body = f"body of section {n}\n1. a numbered item, not a section header\n"
        if n == 84:
            body += f"keep {DATASET} material separate\n"
        if n == 5:
            body += "SECRET-SECTION-5\n"
        parts.append(f"=====\n{n}. TITLE {n}\n=====\n{body}")
    return "\n".join(parts)


def make_repo(root: Path) -> Path:
    for rel, (text, _dest) in SOURCES.items():
        _w(root, rel, text)
    _w(root, "goal4.md", _goal4())
    for i, rel in enumerate(DECOYS):
        _w(root, rel, f"DECOY-{i}\n")
    (root / "phase3/src/brainir_state/__pycache__").mkdir(parents=True)
    (root / "phase3/src/brainir_state/__pycache__/evaluate.cpython-312.pyc").write_bytes(b"\x00DECOY-PYC\x00")
    (root / "research/phase3/level_c/01/fit.pkl").write_bytes(b"\x80\x04binary model")
    return root


def _manifest(repo: Path, name: str = "room", failed: bool = False) -> dict:
    suffix = ".FAILED.json" if failed else ".json"
    return json.loads((repo / "research" / "phase3" / f"POSTLOCK_REVIEW_ROOM_MANIFEST_{name}{suffix}").read_text(encoding="utf-8"))


def _build(repo: Path, room: Path, *extra: str) -> int:
    return PR.main(["--root", str(repo), "--dest", str(room), "--no-answer-scan", *extra])


@pytest.fixture()
def built(tmp_path):
    repo, room = make_repo(tmp_path / "repo"), tmp_path / "room"
    assert _build(repo, room, "--prompts", str(tmp_path / "prompts")) == 0
    return repo, room, tmp_path / "prompts"


# ------------------------------------------------------------------------------------------------ build
def test_room_holds_exactly_the_contract_files(built):
    repo, room, _ = built
    files = set(PR._walk(room))
    assert files == {dest for _text, dest in SOURCES.values()} | GENERATED
    assert (room / "reviews").is_dir() and (room / ".tmp").is_dir()
    blob = "\n".join((room / f).read_bytes().decode("utf-8", "ignore") for f in files)
    for i in range(len(DECOYS)):
        assert f"DECOY-{i}\n" not in blob
    assert "DECOY-PYC" not in blob and "SECRET-SECTION-5" not in blob
    assert BENCH not in blob.lower() and DATASET not in blob.lower()
    assert not (room.parent / "room.staging").exists()


def test_redaction_keeps_code_and_json_valid(built):
    repo, room, _ = built
    code = (room / "src/brainir_state/evaluate.py").read_text(encoding="utf-8")
    assert 'NAME = "REDACTED:v1"' in code
    compile(code, "evaluate.py", "exec")
    assert json.loads((room / "results/level_c/01/level_c_results.json").read_text(encoding="utf-8"))["system"] == "REDACTED net"
    man = _manifest(repo)
    assert man["files"]["results/level_c/01/level_c_results.json"]["redactions"] == 1
    assert man["files"]["src/brainir_state/evaluate.py"]["redactions"] == 1
    assert "redactions" not in man["files"]["results/LEVELB_LOG.md"]


def test_goal4_holds_only_the_cited_sections(built):
    repo, room, _ = built
    lines = set((room / "docs/goal4.md").read_text(encoding="utf-8").splitlines())
    for n in PR.GOAL4_SECTIONS:
        assert f"{n}. TITLE {n}" in lines
    assert not {f"{n}. TITLE {n}" for n in range(93) if n not in PR.GOAL4_SECTIONS} & lines
    assert "keep REDACTED material separate" in lines
    assert _manifest(repo)["goal4_sections"] == list(PR.GOAL4_SECTIONS)


def test_manifest_is_complete_hashed_and_path_free(built):
    repo, room, _ = built
    man = _manifest(repo)
    assert man["status"] == "ok" and man["scan_problems"] == []
    assert set(man["files"]) == set(PR._walk(room)) - {"MANIFEST.json"}
    for rel, e in man["files"].items():
        assert e["sha256"] == PR._sha(room / rel)
        assert e["source"].startswith("$REPO/") or e["source"] == "generated"
    assert man["files"]["results/EVALUATION_LOG.md"]["source"] == "$REPO/research/phase3/HIDDEN_EVALUATIONS.md"
    assert man["files"]["PHASE3_REPORT.md"]["source"] == "$REPO/research/phase3/REPORT_WORKING.md"
    assert man["skipped_binary"] == ["$REPO/research/phase3/level_c/01/fit.pkl"]
    assert set(man["excluded_sources"]) == EXCLUDED_PREFIXES
    assert man["guard_unreadable_code"] == ["scripts/devrun_site/sitecustomize.py"]
    assert man["answer_scan"] == {"status": "skipped"} and man["absent_sources"] == []
    for text in ((repo / "research/phase3/POSTLOCK_REVIEW_ROOM_MANIFEST_room.json").read_text(encoding="utf-8"),
                 (room / "MANIFEST.json").read_text(encoding="utf-8")):
        assert re.search(r"[A-Za-z]:[\\/]", text) is None and "Users" not in text


def test_prompts_and_room_notes(built):
    repo, room, prompts = built
    for x in "SCYRV":
        text = (prompts / f"postlock_{x}.txt").read_text(encoding="utf-8")
        assert text.startswith("COMMON CONTRACT") and f"TASK {x}" in text and "results/EVALUATION_LOG.md" in text
    assert sorted(p.name for p in prompts.iterdir()) == sorted(f"postlock_{x}.txt" for x in "SCYRV")
    claude = (room / "CLAUDE.md").read_text(encoding="utf-8")
    assert "reviews/POSTLOCK_<your letter>.md" in claude and "results/EVALUATION_LOG.md" in claude
    assert "scripts/devrun_site/sitecustomize.py" in (room / "README.md").read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------------ check / update
def test_check_passes_and_allows_the_work_areas(built):
    repo, room, _ = built
    _w(room, "reviews/POSTLOCK_S.md", "# review S\n")
    _w(room, ".tmp/postlock_S/scratch.txt", "x\n")
    _w(room, "uv.lock", "version = 1\n")
    assert _build(repo, room, "--check") == 0


def test_check_flags_tampering_unexpected_and_forbidden_files(built):
    repo, room, _ = built
    _w(room, "results/LEVELB_LOG.md", "# edited\n")
    _w(room, "results/extra.json", "{}\n")
    _w(room, "reviews/oracle_notes.md", "x\n")
    _w(room, "reviews/POSTLOCK_C.md", f"the {DATASET} circuit\n")
    (room / "MANIFEST.json").write_text("{}\n", encoding="utf-8")
    probs = PR.check(repo, room, answer_tokens={FAKE_TOKEN})
    assert "modified: results/LEVELB_LOG.md" in probs
    assert "unexpected: results/extra.json" in probs
    assert "forbidden name: reviews/oracle_notes.md" in probs
    assert "forbidden content class in reviews/POSTLOCK_C.md" in probs
    assert any(p.startswith("MANIFEST.json in the room differs") for p in probs)
    _w(room, "reviews/POSTLOCK_Y.md", f"type {FAKE_TOKEN}\n")
    assert any(p.startswith("answer tokens in 1 file") for p in PR.check(repo, room, answer_tokens={FAKE_TOKEN}))
    assert _build(repo, room, "--check") == 1


def test_update_rebuilds_content_and_keeps_reviews(built):
    repo, room, _ = built
    _w(room, "reviews/POSTLOCK_S.md", "# review S\n")
    _w(room, ".tmp/postlock_S/scratch.txt", "x\n")
    _w(repo, "research/phase3/tournament/final_b/extra_seed.json", '{"seed": 1}\n')
    (repo / "research/phase3/tournament/r3v3_x/method.json").unlink()
    _w(repo, "research/phase3/REPORT_WORKING.md", "# Draft report v2\n")
    with pytest.raises(SystemExit):
        _build(repo, room)                                           # an existing room is only rebuilt with --update
    assert _build(repo, room, "--update") == 0
    assert (room / "results/tournament/final_b/extra_seed.json").exists()
    assert not (room / "results/tournament/r3v3_x/method.json").exists()
    assert (room / "PHASE3_REPORT.md").read_text(encoding="utf-8") == "# Draft report v2\n"
    assert (room / "reviews/POSTLOCK_S.md").read_text(encoding="utf-8") == "# review S\n"
    assert (room / ".tmp/postlock_S/scratch.txt").exists()
    man = _manifest(repo)
    assert man["update"] and man["removed_on_update"] == ["results/tournament/r3v3_x/method.json"]
    assert _build(repo, room, "--check") == 0


# ------------------------------------------------------------------------------------------------ failing builds
def test_answer_tokens_fail_the_build_and_leave_no_room(tmp_path):
    repo, room = make_repo(tmp_path / "repo"), tmp_path / "room"
    _w(repo, "research/phase3/tournament/r3v3_x/method.json", json.dumps({"note": f"type {FAKE_TOKEN} kept", "wall_s": 4242}) + "\n")
    with pytest.raises(SystemExit):
        PR.build(repo, room, answer_tokens={FAKE_TOKEN, "4242"})
    assert not room.exists() and not (tmp_path / "room.staging").exists()
    bad = _manifest(repo, failed=True)
    assert bad["status"] == "FAILED" and bad["answer_scan"]["status"] == "FAIL"
    assert bad["answer_scan"]["failing_files"] == ["results/tournament/r3v3_x/method.json"]
    assert bad["answer_scan"]["classes"]["non-numeric"] == 1
    manifest_text = (repo / "research/phase3/POSTLOCK_REVIEW_ROOM_MANIFEST_room.FAILED.json").read_text(encoding="utf-8")
    assert FAKE_TOKEN not in manifest_text
    # short numeric coincidences are counted, not failed; a clean rebuild removes the failure record
    _w(repo, "research/phase3/tournament/r3v3_x/method.json", '{"wall_s": 4242}\n')
    man = PR.build(repo, room, answer_tokens={FAKE_TOKEN, "4242"})
    assert man["answer_scan"]["status"] == "clean" and man["answer_scan"]["classes"] == {"numeric-4-digits": 1}
    assert json.loads((room / "MANIFEST.json").read_text(encoding="utf-8"))["answer_scan"] == {"status": "clean"}
    assert not (repo / "research/phase3/POSTLOCK_REVIEW_ROOM_MANIFEST_room.FAILED.json").exists()
    assert PR.check(repo, room, answer_tokens={FAKE_TOKEN, "4242"}) == []


@pytest.mark.parametrize("rel, text, problem", [
    ("research/phase3/tournament/r9/oracle_copy.json", "{}\n", "forbidden name: results/tournament/r9/oracle_copy.json"),
    ("research/phase3/level_c/01/hidden/traj.json", "{}\n", "forbidden name: results/level_c/01/hidden/traj.json"),
    ("research/phase3/tournament/r9/pyguard.json", "{}\n",
     "not readable through the agents' tool guard: results/tournament/r9/pyguard.json"),
    ("phase3/src/brainir_state/broken.py", "def f(:\n", "src/brainir_state/broken.py does not parse after redaction (line 1)"),
])
def test_second_layer_catches_what_the_denylist_misses(tmp_path, rel, text, problem):
    repo, room = make_repo(tmp_path / "repo"), tmp_path / "room"
    _w(repo, rel, text)
    with pytest.raises(SystemExit):
        _build(repo, room)
    assert not room.exists() and not (tmp_path / "room.staging").exists()
    assert problem in _manifest(repo, failed=True)["scan_problems"]


def test_a_failed_update_leaves_the_existing_room_intact(built):
    repo, room, _ = built
    before = {rel: PR._sha(room / rel) for rel in PR._walk(room)}
    _w(repo, "research/phase3/tournament/r9/oracle_copy.json", "{}\n")
    with pytest.raises(SystemExit):
        _build(repo, room, "--update")
    assert {rel: PR._sha(room / rel) for rel in PR._walk(room)} == before
    assert _build(repo, room, "--check") == 0


def test_required_sources_goal4_sections_and_prompt_location(tmp_path):
    repo, room = make_repo(tmp_path / "repo"), tmp_path / "room"
    (repo / "research/phase3/METHOD_LOCK.json").unlink()
    with pytest.raises(SystemExit, match="required source missing: research/phase3/METHOD_LOCK.json"):
        _build(repo, room)
    assert not room.exists() and not (tmp_path / "room.staging").exists()
    with pytest.raises(SystemExit, match="outside the room"):
        _build(repo, room, "--allow-missing", "--prompts", str(room / "prompts"))
    assert _build(repo, room, "--allow-missing") == 0
    assert "research/phase3/METHOD_LOCK.json" in _manifest(repo)["absent_sources"]
    _w(repo, "research/phase3/METHOD_LOCK.json", "{}\n")
    _w(repo, "goal4.md", _goal4(sections=[n for n in range(93) if n != 87]))
    with pytest.raises(SystemExit, match=r"sections \[87\] not found"):
        _build(repo, tmp_path / "room2")
    assert not (tmp_path / "room2").exists()


# ------------------------------------------------------------------------------------------------ classes
def test_name_deny_and_redaction_classes():
    for s in ["PHASE2_REPORT.md", "oracle.json", "x/truth/y", "salt.json", "goal2.md", "x/HIDDEN_EVALUATIONS.md", "data/hidden/x",
              "tier_a_ids/a.csv", f"x/{BENCH}_walking_cpg/y"]:
        assert PR.POSTLOCK_FORBIDDEN_NAMES.search(s), s
    for s in ["METHOD_LOCK.json", "results/benchmark/BENCHMARK_LOCK.json", "docs/goal4.md", "results/EVALUATION_LOG.md",
              "src/brainir_state/realsim.py", "results/benchmark/calibration.json", "scripts/generate_real_hidden.py"]:
        assert not PR.POSTLOCK_FORBIDDEN_NAMES.search(s), s
    for s in ["PHASE2_REPORT.md", "research/phase2/x.md", "research/LOG.md", "CLAUDE.md", f"benchmarks/{BENCH}_walking_cpg/a",
              f"benchmarks/{BENCH}/oracle/o.json", "data/phase3/x", "research/phase3/tournament/_refcache/a.npz", "research/phase3/reviews/F.md",
              "research/phase3/review_contracts/POSTLOCK_L_TASK.txt", "scripts/p3/__pycache__/a.pyc", "benchmarks/state_discovery_v1/hidden/x"]:
        assert PR.DENY.search(s), s
    for s in ["PHASE3_REPORT.md", "research/phase3/REPORT_WORKING.md", "research/phase3/HIDDEN_EVALUATIONS.md", "scripts/p3/level_c.py"]:
        assert not PR.DENY.search(s), s
    names = ["neu" + "Print", "Droso" + "phila", "walking " + "CPG", DATASET, BENCH, "Pug" + "liese"]
    red, n = PR._redact(" | ".join(names))
    assert n == len(names) and red == " | ".join(["REDACTED"] * len(names))
    assert PR._alternatives(r"(?i)(a|(^|[\\/])b([\\/]|$)|c[|])") == ["a", r"(^|[\\/])b([\\/]|$)", "c[|]"]
