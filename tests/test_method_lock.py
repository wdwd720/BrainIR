"""The Phase 2 method lock records code, configuration and evidence hashes and detects any later change (goal3 section 27).
Uses the always-registered greedy_reference method and temporary evidence files; never touches the real lock."""

from __future__ import annotations

import importlib.util
import json

from brainir import paths


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, paths.repo_root() / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_lock_records_and_detects_changes(tmp_path):
    ml = _load("method_lock")
    evidence = tmp_path / "tournament.json"
    evidence.write_text(json.dumps({"label": "t", "summary": {"greedy_reference": {"success_rate": 0.5, "by_family": {}}}}), encoding="utf-8")
    doc = tmp_path / "METHOD.md"
    doc.write_text("# method\n", encoding="utf-8")
    tests_log = tmp_path / "pytest.txt"
    tests_log.write_text("....\n12 passed, 3 deselected in 4.00s\n", encoding="utf-8")
    out = tmp_path / "METHOD_LOCK.json"
    rc = ml.main(["write", "--method", "greedy_reference", "--budget", "300", "--config", '{"k": 2}', "--synthetic", str(evidence),
                  "--doc", str(doc), "--tests-log", str(tests_log), "--allow-dirty", "--out", str(out)])
    assert rc == 0
    lock = json.loads(out.read_text(encoding="utf-8"))
    assert lock["method"]["config"]["k"] == 2 and lock["method"]["config_overrides"] == {"k": 2}
    assert lock["run_protocol"]["method_args"] == "--method greedy_reference --budget 300 --config k=2"
    assert "src/brainir/discovery/simulator.py" in lock["source_hashes"] and lock["run_protocol"]["entry"] in lock["source_hashes"]
    assert lock["tests"]["passed"] == 12 and lock["synthetic_results"][0]["summary"]["greedy_reference"] == {"success_rate": 0.5}
    assert lock["expected_output"]["prediction_schema_version"] == "1.0.0" and len(lock["lock_sha256"]) == 64
    assert ml.check(out, verbose=False) == []
    doc.write_text("# method, edited after the lock\n", encoding="utf-8")
    evidence.write_text("{}", encoding="utf-8")
    problems = ml.check(out, verbose=False)
    assert any("documentation" in p for p in problems) and any("synthetic evidence" in p for p in problems)


def test_blind_eval_refuses_without_a_valid_lock(tmp_path, monkeypatch):
    be = _load("blind_eval")
    monkeypatch.setattr(be.method_lock, "LOCK_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(be.method_lock, "check", lambda *a, **k: ["no lock"])
    assert be.main(["--reason", "test"]) == 1
