"""Scoring v2 and the unblinding gate v2 (PREREG v2 Part S) on SYNTHETIC data in temporary folders only.

No real label or prediction file is read. Every UNBLIND.json is written inside a pytest temporary folder. The gate runs only on
temporary git repositories built here (never on the real tree, whose gate runs once), with BRAINIR_DATA_DIR pointing at a
temporary folder. The fixtures and builders here are shared with test_gate_v2.py."""

import hashlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess

import numpy as np
import pandas as pd
import pytest

from brainir_ledger import REPO
from brainir_ledger.labels.aggregate import read_records, type_labels
from brainir_ledger.scoring import BlindError
from brainir_ledger.scoring.pipeline import PREREGISTERED_SECONDARY
from brainir_ledger.scoring.stats import auroc
from brainir_ledger.scoring_v2 import pipeline_v2 as P2

from .conftest import _types_frame, make_record

N = 200  # bootstrap / permutation resamples in tests
LOCK_UTC = "2026-11-21T00:00:00Z"  # utc of the synthetic label-code and scoring locks
SESSION_START = "2026-11-21T01:00:00Z"  # start of the first synthetic v2 label session
SCORING_COPIES = ("ledger/scripts/score_v2.py", "ledger/src/brainir_ledger/scoring_v2/pipeline_v2.py")


def _load_script(name):
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", REPO / "ledger" / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = _load_script("gate_v2")
SC = _load_script("score_v2")


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _hashes(research, rels):
    return {f"research/ledger/{r}": _sha(research / r) for r in rels}


def _dump(research, name, rec):
    (research / name).write_text(json.dumps(rec, indent=1, sort_keys=True))


def _relock_labels_v2(research, extra=None):
    lab = research / "labels_v2"
    top = sorted(f"labels_v2/{p.name}" for p in lab.iterdir() if p.is_file())
    raw = sorted(p.relative_to(research).as_posix() for p in (lab / "raw").rglob("*") if p.is_file()) if (lab / "raw").exists() else []
    ses = sorted(p.relative_to(research).as_posix() for p in (lab / "sessions").glob("*") if p.is_file()) if (lab / "sessions").exists() else []
    _dump(research, "LOCK_labels_v2.json", {"labels": _hashes(research, top), "raw": _hashes(research, raw), "sessions": _hashes(research, ses),
                                            "kit_v2": _hashes(research, ["kit_v2/exposed_types.csv"]), **(extra or {})})


def _relock_predictions_v2(research, arms=("B1r", "B2r", "B4v2"), extra=None):
    pv2 = research / "predictions_v2"
    _dump(research, "LOCK_predictions_v2.json", {
        "arms_locked": {a: {f"research/ledger/predictions_v2/{a}/{f.name}": _sha(f) for f in sorted((pv2 / a).iterdir()) if f.is_file()}
                        for a in arms},
        "arms_not_locked": {"B3": "G3 v2 item 4' failed (PREREG v2 P2)", "B6": "depends on B3"},
        "v1_locks": {"research/ledger/LOCK_predictions_v1.json": _sha(research / "LOCK_predictions_v1.json")},
        "marking": "locked after labels v1 existed, before any unblinding", **(extra or {})})


def _write_flags(research, runs=("P", "S-a", "S-b", "S-c"), **override):
    entries = {}
    for r in runs:
        d = P2.RUNS[r]
        entries[r] = {"predictions_lock": d["predictions_lock"], "labels_lock": d["labels_lock"],
                      "predictions_lock_sha256": _sha(research / d["predictions_lock"]), "labels_lock_sha256": _sha(research / d["labels_lock"])}
        entries[r].update(override.get(r, {}))
    flag = research / "UNBLIND.json"  # inside the pytest temporary folder only
    flag.write_text(json.dumps({"runs": entries, "authorised_by": "test", "utc": "2026-11-20T00:00:00Z"}))
    return flag


def _records_v2(types, y, dedicated):
    recs = []
    for i, (t, yi) in enumerate(zip(types, y)):
        sess = "pass1-dedicated-r0-01" if i in dedicated else "pass1-walking_stopping-r0-01"
        front = "yes" if yi else "no"
        recs.append(make_record(record_id=f"r{i}", exp_id=f"{sess}:r{i}", session=sess, manc_type=t, quote_verified=True,
                                front_leg_rhythm=front, middle_leg_rhythm=front, hind_leg_rhythm=front if i % 3 == 0 else "no",
                                effect_on_walking="stops" if i % 5 == 0 else ("speeds" if i % 7 == 0 else "none"),
                                frequency_hz=8.0 + i if yi else None, preparation="headless" if i % 2 else "intact_free",
                                headless_surface="ball" if i % 2 else None))
    return recs


@pytest.fixture
def v2_world(synthetic_world):
    """The frozen fixture's predictions v1 + labels v1, plus: kit lists (type 0 exposed), labels v1.1 (= v1), labels v2 (type 5
    only from a dedicated session, i.e. exposed by nature; type 10's front label flipped), predictions v2 (B1r on all 40 types, B2r
    on the first 30, B4v2 with every call value) and their locks. No flag file, no gate report, no scoring lock."""
    w = synthetic_world
    research, types = w["research"], w["types"]
    for kit in ("kit", "kit_v2"):
        (research / kit).mkdir()
        pd.DataFrame({"name_as_given": ["X"], "manc_types": [types[0]], "resolved": [True]}).to_csv(research / kit / "exposed_types.csv", index=False)
    shutil.copytree(w["labels"], research / "labels_v1_1")
    _dump(research, "LOCK_labels_v1_1.json", {"labels": _hashes(research, ["labels_v1_1/records.jsonl", "labels_v1_1/type_labels.csv"]),
                                              "kit": _hashes(research, ["kit/exposed_types.csv"])})
    y1 = np.array([1] * 12 + [0] * 28)  # the frozen fixture's labels
    y2 = y1.copy()
    y2[10] = 0
    recs = _records_v2(types, y2, dedicated={5})
    lab = research / "labels_v2"
    lab.mkdir()
    with open(lab / "records.jsonl", "w") as fh:
        fh.writelines(json.dumps(r, sort_keys=True) + "\n" for r in recs)
    pd.DataFrame({"manc_type": [types[5]], "reason": "eligible records only from dedicated sessions"}).to_csv(lab / "exposed_v2.csv", index=False)
    type_labels(recs, exposed={types[0], types[5]}, type_list=types).to_csv(lab / "type_labels.csv", index=False)
    _relock_labels_v2(research)
    a1 = pd.read_csv(research / "predictions" / "A1" / "types.csv").set_index("manc_type")["primary_score"].reindex(types).to_numpy()
    rng = np.random.default_rng(5)
    b1r = np.clip(a1 + rng.normal(0, 0.1, 40), 0, 1)
    b2r = np.clip(a1[:30][::-1] + rng.normal(0, 0.1, 30), 0, 1)
    pv2 = research / "predictions_v2"
    for arm, ts, sc in (("B1r", types, b1r), ("B2r", types[:30], b2r)):
        (pv2 / arm).mkdir(parents=True)
        _types_frame(arm, ts, sc).to_csv(pv2 / arm / "types.csv", index=False)
    (pv2 / "B4v2").mkdir()
    pd.DataFrame({"manc_type": types, "call_32": "no_effect", "call_128": [P2.B4V2_CALLS[i % 8] for i in range(40)],
                  "call_512": "no_effect"}).to_csv(pv2 / "B4v2" / "types.csv", index=False)
    _relock_predictions_v2(research)
    keep = np.array([i not in (0, 5) for i in range(40)])
    return {**w, "y2": y2, "a1": a1, "b1r": b1r, "keep_v2": keep, "expected_auroc_v2": auroc(a1[keep], y2[keep]),
            "expected_b1r_auroc": auroc(b1r[keep], y2[keep])}


def _gate_report(research, **over):
    """A synthetic run-2 gate report (PREREG v2 S5.6) inside the pytest temporary folder."""
    p = research / "gates_v2" / "UNBLINDING_GATE_run2.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"gate_run": 2, "all_conditions_hold": True, "git_head": "0" * 40, **over}))
    return p


@pytest.fixture
def scoring_world(tmp_path, v2_world):
    """v2_world moved to <repo>/research/ledger, plus what scoring v2 requires before it opens anything (PREREG v2 S5, L12): a
    synthetic gate run-2 report holding all six conditions and a passing LOCK_scoring_v2.json, which hashes copies of the scoring
    code inside that repo; and LOCK_prereg_v1.json, so that amendment rows can be checked against all four v1 locks."""
    repo = tmp_path / "srepo"
    research = repo / "research" / "ledger"
    research.parent.mkdir(parents=True)
    shutil.move(str(v2_world["research"]), str(research))
    (research / "PREREG.md").write_text("rulebook v1\n")
    _dump(research, "LOCK_prereg_v1.json", {"prereg": _hashes(research, ["PREREG.md"])})
    (research / "PREREG_v2.md").write_text("rulebook v2\n")
    _dump(research, "LOCK_prereg_v2.json", {"prereg_v2": _hashes(research, ["PREREG_v2.md"])})
    code = {}
    for rel in SCORING_COPIES:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, repo / rel)
        code[rel] = _sha(repo / rel)
    _dump(research, "LOCK_scoring_v2.json", {"stage": "scoring_v2", "utc": LOCK_UTC, "scoring_code": code,
                                             "prereg_v2_lock_sha256": _sha(research / "LOCK_prereg_v2.json")})
    _gate_report(research)
    return {**v2_world, "research": research, "repo": repo, "pred": research / "predictions", "labels": research / "labels"}


def _p_ended(research):
    """Run P has ended (its result file exists; a placeholder: only its existence is read)."""
    d = research / "results" / "run2"
    d.mkdir(parents=True, exist_ok=True)
    (d / "P.json").write_text(json.dumps({"run": "P", "synthetic_placeholder": True}))


def _amend_row(research, path, utc, *, old="a" * 64, new="b" * 64, crash_fix=True, after_unblinding=True, **over):
    """An AMENDMENTS_v2.jsonl row as `lock2.py amend` writes it."""
    row = {"utc": utc, "path": path, "old": old, "new": new, "reason": "synthetic crash fix", "old_rev": "0" * 40,
           "v2_sessions_started": True, "v2_records_existed": True, "crash_fix": crash_fix, "after_unblinding": after_unblinding, **over}
    with open(research / "AMENDMENTS_v2.jsonl", "a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------------------------------------------- refusals
def test_refuses_without_flag_file(scoring_world):
    r = scoring_world["research"]
    for name in P2.RUNS:
        with pytest.raises(BlindError, match="does not exist"):
            P2.run(name, r, r / "UNBLIND.json", n_boot=N, n_perm=N)
    assert not (r / "results").exists()


def test_refuses_unlisted_or_unknown_run(scoring_world):
    r = scoring_world["research"]
    flags = _write_flags(r, runs=("P",))
    for name in ("S-a", "S-b", "S-c"):
        with pytest.raises(BlindError, match="not listed"):
            P2.run(name, r, flags, n_boot=N, n_perm=N)
    with pytest.raises(BlindError, match="unknown run"):
        P2.run("X", r, flags, n_boot=N, n_perm=N)
    assert not (r / "results").exists()


def test_refuses_wrong_pairing_hash_name_or_missing_field(scoring_world):
    r = scoring_world["research"]
    for over in ({"labels_lock": "LOCK_labels_v1_1.json", "labels_lock_sha256": _sha(r / "LOCK_labels_v1_1.json")},  # S4 pairing
                 {"labels_lock_sha256": "0" * 64}, {"predictions_lock": "../LOCK_predictions_v1.json"},
                 {"predictions_lock_sha256": None}):
        flags = _write_flags(r, P=over)
        with pytest.raises(BlindError):
            P2.run("P", r, flags, n_boot=N, n_perm=N)
    d = json.loads(flags.read_text())
    d.pop("authorised_by")
    flags.write_text(json.dumps(d))
    with pytest.raises(BlindError, match="authorised_by"):
        P2.run("S-a", r, flags, n_boot=N, n_perm=N)
    assert not (r / "results").exists()


def test_refuses_without_a_passing_gate_report(scoring_world):
    """PREREG v2 S5: 'If any condition fails, nothing is unblinded' -> the gate's run-2 report must hold all six conditions."""
    r = scoring_world["research"]
    flags = _write_flags(r)
    rep = r / "gates_v2" / "UNBLINDING_GATE_run2.json"
    rep.unlink()
    with pytest.raises(BlindError, match="UNBLINDING_GATE_run2"):
        P2.run("P", r, flags, n_boot=N, n_perm=N)
    for over in ({"all_conditions_hold": False}, {"gate_run": 1}, {"all_conditions_hold": "true"}):
        _gate_report(r, **over)
        with pytest.raises(BlindError, match="all_conditions_hold"):
            P2.run("P", r, flags, n_boot=N, n_perm=N)
    rep.write_text("not json")
    with pytest.raises(BlindError):
        P2.run("P", r, flags, n_boot=N, n_perm=N)
    assert not (r / "results").exists()
    _gate_report(r)
    res = P2.run("P", r, flags, n_boot=N, n_perm=N)
    assert res["gate_report_sha256"] == _sha(rep) == res["preconditions"]["gate_report"]["sha256"]


def test_refuses_a_missing_or_failing_scoring_lock(scoring_world):
    """PREREG v2 L12: the scoring code is bound by LOCK_scoring_v2.json; lock2.check runs in-process before anything is read."""
    w = scoring_world
    r, repo = w["research"], w["repo"]
    flags = _write_flags(r)
    lock = r / "LOCK_scoring_v2.json"
    lock.rename(r / "scoring_lock.moved")
    with pytest.raises(BlindError, match="LOCK_scoring_v2.json is missing"):
        P2.run("P", r, flags, n_boot=N, n_perm=N)
    (r / "scoring_lock.moved").rename(lock)
    rel = "ledger/src/brainir_ledger/scoring_v2/pipeline_v2.py"
    code = repo / rel
    locked = _sha(code)
    code.write_text(code.read_text() + "# changed after the lock\n")
    with pytest.raises(BlindError, match=r"lock2\.check\(LOCK_scoring_v2\.json\) fails"):
        P2.run("P", r, flags, n_boot=N, n_perm=N)
    _amend_row(r, "ledger/scripts/gate_v2.py", "2026-11-22T00:00:00Z", old=locked, new=_sha(code))  # wrong path: no effect
    _amend_row(r, rel, "2026-11-22T00:00:00Z", old=locked, new=_sha(code), crash_fix=False)  # after unblinding, not a crash fix
    with pytest.raises(BlindError, match="fails"):
        P2.run("P", r, flags, n_boot=N, n_perm=N)
    (r / "LOCK_prereg_v2.json").write_text("{}")  # a broken chain fails the check as well
    with pytest.raises(BlindError, match="fails"):
        P2.run("P", r, flags, n_boot=N, n_perm=N)
    _dump(r, "LOCK_prereg_v2.json", {"prereg_v2": _hashes(r, ["PREREG_v2.md"])})
    assert not (r / "results").exists()
    _amend_row(r, rel, "2026-11-22T00:00:00Z", old=locked, new=_sha(code))  # a crash fix recorded after unblinding: counts
    res = P2.run("P", r, _write_flags(r), n_boot=N, n_perm=N)
    chk = res["preconditions"]["scoring_lock_check"]["check"]
    assert chk["amended"] == [rel] and chk["changed"] == [] and len(chk["amendment_rows_ignored"]) == 2


def test_sensitivity_runs_wait_for_run_P(scoring_world):
    """RUN2_PROMPT Stage 4: the primary analysis first; S-a, S-b, S-c only after P ended (completed, or crashed twice)."""
    r = scoring_world["research"]
    flags = _write_flags(r)
    for name in ("S-a", "S-b", "S-c"):
        with pytest.raises(BlindError, match="run P"):
            P2.run(name, r, flags, n_boot=N, n_perm=N)
    assert not (r / "results").exists()
    d = r / "results" / "run2"
    d.mkdir(parents=True)
    (d / "P.started.json").write_text(json.dumps({"run": "P", "utc": LOCK_UTC, "exception": "RuntimeError: x"}))  # one crash
    with pytest.raises(BlindError, match="run P"):
        P2.run("S-a", r, flags, n_boot=N, n_perm=N)
    (d / "P.started.json").rename(d / "P.crashed-1.json")
    (d / "P.started.json").write_text(json.dumps({"run": "P", "utc": LOCK_UTC, "interrupted_by": "KeyboardInterrupt"}))
    with pytest.raises(BlindError, match="run P"):  # the repeat was interrupted: P has not ended
        P2.run("S-a", r, flags, n_boot=N, n_perm=N)
    (d / "P.started.json").write_text(json.dumps({"run": "P", "utc": LOCK_UTC, "exception": "RuntimeError: y"}))
    assert P2.primary_run_state(r) == "crashed twice"
    res = P2.run("S-a", r, flags, n_boot=N, n_perm=N)
    assert res["primary"]["status"] == "ok" and res["preconditions"]["primary_run_P"] == "crashed twice"


def test_refuses_a_research_folder_outside_research_ledger(v2_world):
    r = v2_world["research"]  # <tmp>/research
    _gate_report(r)
    with pytest.raises(BlindError, match="research/ledger"):
        P2.run("P", r, _write_flags(r), n_boot=N, n_perm=N)
    assert not (r / "results").exists()


# ---------------------------------------------------------------------------------------------------------------- the four runs
def test_run_P_primary_on_labels_v2_once(scoring_world):
    w = scoring_world
    r = w["research"]
    flags = _write_flags(r)
    res = P2.run("P", r, flags, n_boot=N, n_perm=N)
    p = res["primary"]
    assert p["status"] == "ok", p
    assert (p["result"]["n"], p["result"]["n_pos"], p["result"]["n_neg"]) == (38, 9, 29)  # kit type 0 and by-nature type 5 excluded
    assert p["result"]["auroc"] == pytest.approx(w["expected_auroc_v2"])
    assert p["result"]["best_baseline"] in p["result"]["baselines_auroc"] and "decision" in p["result"]
    assert res["exposed_set"]["n_types"] == 2 and res["inputs"]["arms_locked"][0] == "A0"
    assert res["preconditions"]["scoring_lock_check"]["check"]["changed"] == [] and res["prior_attempts"] == []
    saved = json.loads((r / "results" / "run2" / "P.json").read_text())
    assert saved["primary"]["result"]["n"] == 38 and saved["unblind_flag"]["labels_lock"] == "LOCK_labels_v2.json"
    assert saved["gate_report_sha256"] == _sha(r / "gates_v2" / "UNBLINDING_GATE_run2.json")
    with pytest.raises(BlindError, match="once"):
        P2.run("P", r, flags, n_boot=N, n_perm=N)


def test_exposed_by_nature_set_comes_from_its_file(scoring_world):
    w = scoring_world
    r, types = w["research"], w["types"]
    lab = r / "labels_v2"
    # exposed_v2.csv emptied (header only) while type_labels.csv still marks the by-nature type exposed: refused
    pd.DataFrame({"manc_type": [], "reason": []}).to_csv(lab / "exposed_v2.csv", index=False)
    _relock_labels_v2(r)
    with pytest.raises(BlindError, match="differs"):
        P2.run("P", r, _write_flags(r), n_boot=N, n_perm=N)
    # consistent tables without it: the type enters the primary set
    type_labels(read_records(lab / "records.jsonl"), exposed={types[0]}, type_list=types).to_csv(lab / "type_labels.csv", index=False)
    _relock_labels_v2(r)
    res = P2.run("P", r, _write_flags(r), n_boot=N, n_perm=N)
    assert res["primary"]["result"]["n"] == 39 and res["exposed_set"]["n_types"] == 1
    # a missing file is an error, never an empty set
    (lab / "exposed_v2.csv").unlink()
    with pytest.raises(BlindError, match="exposed_v2.csv"):
        P2.exposed_set_v2(r)


def test_run_S_a_primary_on_labels_v1_1_with_the_v1_list(scoring_world):
    w = scoring_world
    r = w["research"]
    _p_ended(r)
    res = P2.run("S-a", r, _write_flags(r), n_boot=N, n_perm=N)
    assert res["primary"]["status"] == "ok" and res["preconditions"]["primary_run_P"] == "completed"
    assert res["primary"]["result"]["n"] == 39 and res["primary"]["result"]["auroc"] == pytest.approx(w["expected_auroc"])
    assert "kit/exposed_types.csv" in res["exposed_set"]["definition"]


def test_run_S_b_secondary_on_labels_v2(scoring_world):
    r = scoring_world["research"]
    _p_ended(r)
    res = P2.run("S-b", r, _write_flags(r), n_boot=N, n_perm=N)
    A = res["analyses"]
    assert "analyses_missing_from_code" not in res and "analyses_error" not in res
    assert set(PREREGISTERED_SECONDARY) <= set(A)
    for k in PREREGISTERED_SECONDARY:
        assert A[k]["status"] in ("ok", "not_locked", "input_missing"), (k, A[k])
    assert A["exposed_included"]["result"]["n"] == 40 and A["exposed_only"]["result"]["n"] == 2
    assert A["B1"]["status"] == "ok" and A["B4_stop"]["status"] == "ok" and A["B3_pairs"]["status"] == "not_locked"


def test_run_S_c_new_arms(scoring_world):
    w = scoring_world
    r = w["research"]
    _p_ended(r)
    res = P2.run("S-c", r, _write_flags(r), n_boot=N, n_perm=N)
    A = res["analyses"]
    assert set(P2.PREREGISTERED_S3) <= set(A) and "analyses_missing_from_code" not in res
    assert res["inputs"]["arms_locked"] == ["B1r", "B2r", "B4v2"] and "A1" in res["inputs"]["v1_arms_verified"]
    assert A["B1r"]["status"] == "ok" and A["B1r"]["result"]["n"] == 38
    assert A["B1r"]["result"]["auroc"] == pytest.approx(w["expected_b1r_auroc"])
    assert A["B2r"]["status"] == "ok" and A["B2r"]["result"]["n"] == 28  # first 30 types minus the two exposed
    tf = A["B1r_vs_B2r"]["result"]
    assert tf["n_common_types"] == 30 and 0 <= tf["top10_overlap"] <= 10 and tf["n_band_disagreements"] == len(tf["types_band_disagree"])
    assert not any(k.startswith("B3") for k in A)  # PREREG v2 S3: B3 and B6 are not analysed in run 2
    ex, nh = A["B4v2_stop_lost_excluded"]["result"], A["B4v2_stop_lost_as_non_halts"]["result"]
    assert (ex["n"], ex["n_saturates"], ex["n_rhythm_lost_other"], ex["n_excluded_non_calls"]) == (18, 5, 5, 10)
    assert nh["n"] == 28 and sum(sum(col.values()) for col in nh["confusion"].values()) == 28
    mod = A["B4v2_modulation"]
    assert mod["status"] == "ok" and mod["result"]["n"] == 18 and mod["result"]["n_excluded_saturates_or_rhythm_lost_other"] == 10
    assert set(res["not_analysed"]) == {"B3", "B6"} and all("not analysed in run 2" in v for v in res["not_analysed"].values())


def test_S_c_does_not_analyse_B3_even_when_a_lock_lists_it(scoring_world):
    """PREREG v2 S3: 'B3 and B6 are not analysed in run 2'; a locked B3 is verified with the other arms, never analysed."""
    w = scoring_world
    r, types = w["research"], w["types"]
    d = r / "predictions_v2" / "B3"
    d.mkdir()
    _types_frame("B3", types, w["a1"]).to_csv(d / "types.csv", index=False)
    pd.DataFrame([{"manc_type": t, "leg": leg, "score": float(w["a1"][i])} for i, t in enumerate(types)
                  for leg in ("front", "middle", "hind")]).to_csv(d / "legs.csv", index=False)
    _relock_predictions_v2(r, arms=("B1r", "B2r", "B3", "B4v2"))
    _p_ended(r)
    res = P2.run("S-c", r, _write_flags(r), n_boot=N, n_perm=N)
    assert "B3" in res["inputs"]["arms_locked"] and not any(k.startswith("B3") for k in res["analyses"])
    assert "B3" in res["not_analysed"] and "analyses_missing_from_code" not in res


def test_S_c_refuses_a_broken_v1_chain_or_a_changed_v2_arm(scoring_world):
    r = scoring_world["research"]
    _p_ended(r)
    lock = json.loads((r / "LOCK_predictions_v2.json").read_text())
    lock["v1_locks"]["research/ledger/LOCK_predictions_v1.json"] = "0" * 64
    _dump(r, "LOCK_predictions_v2.json", lock)
    with pytest.raises(BlindError, match="v1_locks"):
        P2.run("S-c", r, _write_flags(r), n_boot=N, n_perm=N)
    _relock_predictions_v2(r)
    flags = _write_flags(r)
    p = r / "predictions_v2" / "B1r" / "types.csv"
    df = pd.read_csv(p)
    df.loc[0, "primary_score"] = 0.99
    df.to_csv(p, index=False)
    with pytest.raises(BlindError, match="B1r"):
        P2.run("S-c", r, flags, n_boot=N, n_perm=N)
    assert not (r / "results" / "run2" / "S-c.json").exists()


# ---------------------------------------------------------------------------------------------------------------- score_v2.py
def _fast(real):
    return lambda *a, **k: real(*a, **{**k, "n_boot": 50, "n_perm": 50})


def _set_marker_utc(marker, utc):
    m = json.loads(marker.read_text())
    m["utc"] = utc
    marker.write_text(json.dumps(m))


def test_score_v2_cli(scoring_world, capsys):
    r = scoring_world["research"]
    assert SC.main(["--run", "P"], research=r) == 2  # no flag file
    assert not (r / "results" / "run2" / "P.started.json").exists()  # a refusal leaves no marker
    _write_flags(r)
    assert SC.main(["--run", "P"], research=r) == 0
    assert "primary: ok" in capsys.readouterr().out and (r / "results" / "run2" / "P.json").exists()
    assert SC.main(["--run", "P"], research=r) == 2  # each run once
    assert SC.main(["--run", "P", "--after-crash-fix"], research=r) == 2


def test_crash_marker_and_the_one_repeat_after_a_crash_fix(scoring_world, monkeypatch):
    """PREREG v2 S4: a crash (uncaught exception) is recorded in the marker; one repeat, after a crash fix of the scoring v2 code
    recorded (lock2.py amend --crash-fix) later than the marker's own utc."""
    r = scoring_world["research"]
    _write_flags(r)
    real = SC.run

    def crash(*a, **k):
        raise RuntimeError("synthetic crash")
    monkeypatch.setattr(SC, "run", crash)
    with pytest.raises(RuntimeError):
        SC.main(["--run", "P"], research=r)
    marker = r / "results" / "run2" / "P.started.json"
    m = json.loads(marker.read_text())
    assert m["exception"] == "RuntimeError: synthetic crash" and m["utc"] and m["pid"] == os.getpid() and "interrupted_by" not in m
    assert SC.main(["--run", "P"], research=r) == 2  # a crash is repeated only after a fix
    assert SC.main(["--run", "P", "--after-interruption"], research=r) == 2  # a crash is not an interruption
    assert SC.main(["--run", "P", "--after-crash-fix"], research=r) == 2  # no crash-fix amendment yet
    _set_marker_utc(marker, "2026-11-21T00:00:00Z")
    _amend_row(r, "ledger/src/brainir_ledger/scoring_v2/pipeline_v2.py", "2026-11-20T23:59:59Z")  # recorded before the attempt
    _amend_row(r, "ledger/scripts/gate_v2.py", "2026-11-21T00:00:05Z")  # not the scoring v2 code
    _amend_row(r, "ledger/scripts/score_v2.py", "2026-11-21T00:00:05Z", crash_fix=False)  # not a crash fix
    _amend_row(r, "ledger/scripts/score_v2.py", "2026-11-21T00:00:05Z", v2_sessions_started=None)  # not a row amend writes
    assert SC.main(["--run", "P", "--after-crash-fix"], research=r) == 2
    assert not (r / "results" / "run2" / "P.crashed-1.json").exists()
    _amend_row(r, "ledger/src/brainir_ledger/scoring_v2/pipeline_v2.py", "2026-11-21T00:00:05Z")  # the crash fix
    with pytest.raises(RuntimeError):  # the one repeat crashes again
        SC.main(["--run", "P", "--after-crash-fix"], research=r)
    assert (r / "results" / "run2" / "P.crashed-1.json").exists() and json.loads(marker.read_text())["exception"]
    assert P2.primary_run_state(r) == "crashed twice"
    monkeypatch.setattr(SC, "run", _fast(real))
    assert SC.main(["--run", "P", "--after-crash-fix"], research=r) == 2  # a second repeat: refused
    assert SC.main(["--run", "P"], research=r) == 2
    assert not (r / "results" / "run2" / "P.json").exists()
    assert SC.main(["--run", "S-a"], research=r) == 0  # P has ended (crashed twice): the sensitivity runs may go


def test_crash_fix_repeat_succeeds_once_and_is_logged(scoring_world, monkeypatch):
    r = scoring_world["research"]
    _write_flags(r)
    real = SC.run
    monkeypatch.setattr(SC, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("synthetic crash")))
    with pytest.raises(RuntimeError):
        SC.main(["--run", "P"], research=r)
    marker = r / "results" / "run2" / "P.started.json"
    _set_marker_utc(marker, "2026-11-21T00:00:00Z")
    _amend_row(r, "ledger/scripts/score_v2.py", "2026-11-21T00:00:05Z")
    monkeypatch.setattr(SC, "run", _fast(real))
    assert SC.main(["--run", "P", "--after-crash-fix"], research=r) == 0
    res = json.loads((r / "results" / "run2" / "P.json").read_text())
    assert not marker.exists() and (r / "results" / "run2" / "P.crashed-1.json").exists()
    assert [a["exception"] for a in res["prior_attempts"]] == ["RuntimeError: synthetic crash"]
    assert SC.main(["--run", "P"], research=r) == 2


def test_a_refused_repeat_restores_the_crashed_marker(scoring_world, monkeypatch):
    r = scoring_world["research"]
    _write_flags(r)
    monkeypatch.setattr(SC, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("synthetic crash")))
    with pytest.raises(RuntimeError):
        SC.main(["--run", "P"], research=r)
    marker = r / "results" / "run2" / "P.started.json"
    _set_marker_utc(marker, "2026-11-21T00:00:00Z")
    _amend_row(r, "ledger/scripts/score_v2.py", "2026-11-21T00:00:05Z")
    monkeypatch.undo()
    (r / "gates_v2" / "UNBLINDING_GATE_run2.json").unlink()  # the repeat is refused (nothing computed) ...
    assert SC.main(["--run", "P", "--after-crash-fix"], research=r) == 2
    assert json.loads(marker.read_text())["exception"] and not (r / "results" / "run2" / "P.crashed-1.json").exists()  # ... and spent nothing


def test_interruption_allows_one_repeat_without_an_amendment(scoring_world, monkeypatch):
    """Ctrl-C is recorded as an interruption, not a crash: one repeat with --after-interruption, no amendment, logged."""
    r = scoring_world["research"]
    _write_flags(r)
    real = SC.run

    def interrupt(*a, **k):
        raise KeyboardInterrupt
    monkeypatch.setattr(SC, "run", interrupt)
    with pytest.raises(KeyboardInterrupt):
        SC.main(["--run", "P"], research=r)
    marker = r / "results" / "run2" / "P.started.json"
    m = json.loads(marker.read_text())
    assert m["interrupted_by"] == "KeyboardInterrupt" and "exception" not in m and m["utc"]
    assert SC.main(["--run", "P"], research=r) == 2  # the repeat is deliberate
    assert SC.main(["--run", "P", "--after-crash-fix"], research=r) == 2  # not a crash
    monkeypatch.setattr(SC, "run", _fast(real))
    assert SC.main(["--run", "S-a"], research=r) == 2  # P has not ended
    assert not (r / "results" / "run2" / "S-a.started.json").exists()
    assert SC.main(["--run", "P", "--after-interruption"], research=r) == 0
    res = json.loads((r / "results" / "run2" / "P.json").read_text())
    assert [a.get("interrupted_by") for a in res["prior_attempts"]] == ["KeyboardInterrupt"]
    assert (r / "results" / "run2" / "P.interrupted-1.json").exists() and not marker.exists()


def test_interruption_repeat_is_allowed_once(scoring_world, monkeypatch):
    r = scoring_world["research"]
    _write_flags(r)
    monkeypatch.setattr(SC, "run", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        SC.main(["--run", "P"], research=r)
    with pytest.raises(KeyboardInterrupt):
        SC.main(["--run", "P", "--after-interruption"], research=r)
    assert SC.main(["--run", "P", "--after-interruption"], research=r) == 2


def test_killed_attempt_repeat_waits_for_its_process(scoring_world, monkeypatch):
    """A kill leaves the marker with neither an exception nor an interruption; the repeat is refused while its pid lives."""
    r = scoring_world["research"]
    _write_flags(r)
    d = r / "results" / "run2"
    d.mkdir(parents=True)
    marker = d / "P.started.json"
    marker.write_text(json.dumps({"run": "P", "utc": LOCK_UTC, "pid": os.getppid(), "host": socket.gethostname(), "attempt": 1}))
    assert SC.main(["--run", "P", "--after-interruption"], research=r) == 2  # its process (here: pytest's parent) still runs
    proc = subprocess.Popen(["true"])
    proc.wait()
    marker.write_text(json.dumps({"run": "P", "utc": LOCK_UTC, "pid": proc.pid, "host": socket.gethostname(), "attempt": 1}))
    monkeypatch.setattr(SC, "run", _fast(SC.run))
    assert SC.main(["--run", "P", "--after-interruption"], research=r) == 0
    assert json.loads((d / "P.json").read_text())["prior_attempts"][0]["pid"] == proc.pid


# ---------------------------------------------------------------------------------------------------------------- the gate
def _write_ids(path, ids):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps({"exp_id": e}) + "\n" for e in ids))


def _label_side(research, *, final=None, pass2=None, adjudication=None, atlas=(), breach=(), unaudited=(), verifiers=("verify-01",),
                verifier="verify-01", n=30, errors=1, kappa=0.8, verdict="**Verdict: usable with caveats.**", file_n=None,
                file_errors=None, n_sample=None):
    """The label-side files the gate reads (synthetic): records (exp_ids only when `final` is given), raw pass-2 /
    adjudication / atlas session folders, both transcript audits, the verification (sample, truth, the verifier's collected
    verification.csv with `errors` wrong rows, verification.json stating `file_n` / `file_errors`, by default the true values),
    agreement and the label review."""
    lab = research / "labels_v2"
    shutil.rmtree(lab / "raw", ignore_errors=True)
    shutil.rmtree(lab / "verify", ignore_errors=True)
    if final is not None:
        _write_ids(lab / "records.jsonl", final)
    final = [json.loads(x)["exp_id"] for x in (lab / "records.jsonl").read_text().splitlines() if x.strip()]
    generic = [e for e in final if not e.startswith("atlas:")]
    pass2 = {"pass2-general-01": generic} if pass2 is None else pass2
    adjudication = {"adjudication-general-01": generic[:3]} if adjudication is None else adjudication
    for sub, sessions in (("pass2", pass2), ("adjudication", adjudication)):
        for s, ids in sessions.items():
            _write_ids(lab / "raw" / sub / s / "records.valid.jsonl", ids)
    for s in atlas:
        _write_ids(lab / "raw" / ("atlas_map" if s.startswith("atlas-map") else "pass1") / s / "records.valid.jsonl", [])
    sessions = {e.split(":", 1)[0] for e in generic} | set(pass2) | set(adjudication) | set(atlas)
    (lab / "transcript_audit.json").write_text(json.dumps([{"session": s, "kind": "x", "breach": s in breach}
                                                           for s in sorted(sessions - set(unaudited))]))
    v = lab / "verify"
    v.mkdir(parents=True)
    (v / "transcript_audit_verify.json").write_text(json.dumps([{"session": s, "kind": "verify", "breach": s in breach}
                                                                for s in verifiers if s not in unaudited]))
    truth = {f"pass1-walking_stopping-r0-01:v{i:02d}": ("yes" if i % 3 == 0 else "no") for i in range(n)}
    (v / "verify_truth.json").write_text(json.dumps(truth, indent=1))
    keys = list(truth)[: n if n_sample is None else n_sample]
    (v / "verify_sample.csv").write_text("exp_id,doi,source_locator,driver_lines,name_in_paper,quote\n"
                                         + "".join(f"{k},10.1000/x,Fig. 1,SS00001,DNx,a quote\n" for k in keys))
    if verifier:
        def wrong(i, val):
            return "cannot_verify" if i % 2 else ("no" if val == "yes" else "yes")
        rows = [f"{k},yes,{wrong(i, val) if i < errors else val},Fig. 1,\n" for i, (k, val) in enumerate(truth.items())]
        (v / "raw" / verifier).mkdir(parents=True)
        (v / "raw" / verifier / "verification.csv").write_text("exp_id,quote_found,front_leg_rhythm,locator,comment\n" + "".join(rows))
    fn, fe = (n if file_n is None else file_n), (errors if file_errors is None else file_errors)
    (v / "verification.json").write_text(json.dumps({"n": fn, "errors": fe if verifier else None, "error_rate": fe / fn if fn else None,
                                                     "blocker": (fe / fn > 0.10) if (fn and verifier) else True, "verifier_session": verifier}))
    (lab / "agreement.json").write_text(json.dumps({"n_final": len(final), "agreement": {"primary_field_all_values": {
        "n": 50, "raw_agreement": 0.9, "kappa": kappa}}}))
    (research / "reviews_v2").mkdir(parents=True, exist_ok=True)
    (research / "reviews_v2" / "REVIEW_labels_v2.md").write_text(f"# Labels v2 review\n\n{verdict}\n\nDetails follow.\n")
    return final


def test_gate_condition5_counts_from_names_and_labels(v2_world):
    w = v2_world
    r, types = w["research"], w["types"]
    a1 = r / "predictions" / "A1" / "types.csv"
    pd.DataFrame({"manc_type": types}).to_csv(a1, index=False)  # names only: the gate needs no score column
    c5 = G.cond5_primary_set(r)
    assert (c5["n_types"], c5["n_yes"], c5["n_no"], c5["pass"]) == (38, 9, 29, True)
    assert c5["exposed_column_mismatches_reported_only"] == 0 and c5["n_exposed_v2"] == 2
    pd.DataFrame({"manc_type": types[:25]}).to_csv(a1, index=False)  # only A1's types count
    c5 = G.cond5_primary_set(r)
    assert (c5["n_types"], c5["n_yes"], c5["n_no"], c5["pass"]) == (23, 9, 14, True)
    tl = pd.read_csv(r / "labels_v2" / "type_labels.csv")
    tl.loc[tl["manc_type"].isin([types[i] for i in (6, 7, 8, 9, 11)]), "front"] = "unclear"  # 4 yes left
    tl.to_csv(r / "labels_v2" / "type_labels.csv", index=False)
    c5 = G.cond5_primary_set(r)
    assert (c5["n_yes"], c5["pass"]) == (4, False)


def test_gate_condition2_contributing_sessions(tmp_path):
    r = tmp_path / "research"
    final = [f"pass1-walking_stopping-r0-01:r{i}" for i in range(6)] + ["pass1-grooming-r0-01:r0"]
    _label_side(r, final=final)
    c = G.cond2_breaches(r)
    assert c["pass"] and c["contributing_by_role"] == {"reader": 2, "atlas_map_or_coder": 0, "second_reader": 1, "adjudicator": 1, "verifier": 1}
    # L3: a breaching second reader replaced by `-r1` with the same inputs did not contribute (the collector drops it) ...
    _label_side(r, pass2={"pass2-general-01": final[:3], "pass2-general-01-r1": final[:3], "pass2-general-02": final[3:]},
                breach={"pass2-general-01"})
    c = G.cond2_breaches(r)
    assert c["pass"] and c["breaching_excluded_and_replaced"]["second_reader"] == ["pass2-general-01"]
    assert c["literal_rule_reported_only"]["breaching"] == ["pass2-general-01"]
    # ... but without a replacement its readings are the only ones: fail
    _label_side(r, pass2={"pass2-general-01": final[:3], "pass2-general-02": final[3:]}, breach={"pass2-general-01"})
    assert G.cond2_breaches(r)["breaching_contributing"] == ["pass2-general-01"]
    _label_side(r, adjudication={"adjudication-general-01": final[:2], "adjudication-general-01-r1": final[:2]}, breach={"adjudication-general-01"})
    assert G.cond2_breaches(r)["pass"]
    _label_side(r, adjudication={"adjudication-general-01": final[:2]}, breach={"adjudication-general-01"})
    assert not G.cond2_breaches(r)["pass"]
    _label_side(r, breach={"pass1-grooming-r0-01"})  # a breaching reader whose record is final
    assert G.cond2_breaches(r)["breaching_contributing"] == ["pass1-grooming-r0-01"]
    _label_side(r, unaudited={"pass1-grooming-r0-01"})  # no audit row (L3 kind 4)
    c = G.cond2_breaches(r)
    assert not c["pass"] and c["unaudited_contributing"] == ["pass1-grooming-r0-01"]
    _label_side(r, breach={"verify-01"})  # the verifier
    assert G.cond2_breaches(r)["breaching_contributing"] == ["verify-01"]
    _label_side(r, verifiers=("verify-01", "verify-01-r1"), verifier="verify-01-r1", breach={"verify-01"})
    assert G.cond2_breaches(r)["pass"]


def test_gate_condition2_atlas_sessions(tmp_path):
    r = tmp_path / "research"
    generic = ["pass1-walking_stopping-r0-01:r1"]
    final = generic + ["atlas:SS01:intact:DNa01", "atlas:SS02:headless:UNMAPPED"]
    atlas = ("atlas-map", "atlas-codeA", "atlas-codeB")
    _label_side(r, final=final, atlas=atlas)
    c = G.cond2_breaches(r)
    assert c["pass"] and c["contributing_by_role"]["atlas_map_or_coder"] == 3 and c["contributing_by_role"]["reader"] == 1
    _label_side(r, atlas=atlas + ("atlas-codeA-r1",), breach={"atlas-codeA"})  # replaced coder: the replacement is used
    assert G.cond2_breaches(r)["pass"]
    _label_side(r, atlas=atlas, breach={"atlas-codeB"})  # breaching coder, no replacement: the atlas records came from it
    c = G.cond2_breaches(r)
    assert not c["pass"] and c["atlas_problems"]
    _label_side(r, atlas=atlas, breach={"atlas-map"})  # breaching map, no replacement, a mapped type is final
    assert not G.cond2_breaches(r)["pass"]
    _label_side(r, final=generic + ["atlas:SS02:headless:UNMAPPED"], atlas=atlas, breach={"atlas-map"})  # no map was used
    assert G.cond2_breaches(r)["pass"]


def test_gate_conditions_3_and_4(tmp_path):
    r = tmp_path / "research"
    final = ["pass1-walking_stopping-r0-01:r1"]
    for verdict, ok in (("**Verdict: usable with caveats.**", True), ("Verdict: usable", True), ("Verdict: Usable With Caveats", True),
                        ("## Verdict: usable", True), ("**Verdict:** usable with caveats", True),
                        ("**Verdict: blocked** (two blockers)", False), ("Verdict: blocked", False),
                        ("## Verdict\n\nBlocked: the atlas could not be read.", False), ("No verdict line here.", False),
                        ("**Verdict: labels usable with caveats, no blocker.**", False),  # not the whole phrase
                        ("Verdict: usable only after the two blockers below are fixed", False),  # review probe E
                        ("Verdict: usable? no: blocked", False), ("Verdict: usable\n\nVerdict: usable", False),  # two verdict lines
                        ("Verdict: usable with caveats; see section 3", False)):
        _label_side(r, final=final, verdict=verdict)
        assert G.cond3_review_and_verification(r)["review"]["pass"] is ok, verdict
    _label_side(r, errors=3, n=30)
    c3 = G.cond3_review_and_verification(r)
    assert c3["pass"] and c3["verification"]["recomputed"]["errors"] == 3
    _label_side(r, errors=4, n=30)
    assert not G.cond3_review_and_verification(r)["verification"]["pass"]
    _label_side(r, breach={"verify-01"})
    assert G.cond3_review_and_verification(r)["verification"]["verifier_audited_non_breaching"] is False
    _label_side(r, verifier=None)
    assert not G.cond3_review_and_verification(r)["pass"]
    _label_side(r)
    (r / "reviews_v2" / "REVIEW_labels_v2.md").unlink()
    assert G.cond3_review_and_verification(r)["review"]["verdict_class"] == "missing"
    for kappa, ok in ((0.7, True), (0.69, False), (float("nan"), False), (None, False)):
        _label_side(r, kappa=kappa)
        assert G.cond4_kappa(r)["pass"] is ok, kappa
    (r / "labels_v2" / "agreement.json").write_text(json.dumps({"agreement": {"primary_field_all_values": 0.75}}))  # a bare number
    assert G.cond4_kappa(r)["pass"]


def test_gate_condition3_recomputes_the_verification(tmp_path):
    """PREREG v2 L11: errors recomputed from verify_truth.json and the verifier's verification.csv (labels2_collect.verify_score's
    rule), n checked against verify_sample.csv; verification.json is not trusted."""
    r = tmp_path / "research"
    _label_side(r, final=["pass1-walking_stopping-r0-01:r1"], errors=4, n=30, file_errors=3)  # the file understates the errors
    v = G.cond3_review_and_verification(r)["verification"]
    assert (v["recomputed"]["errors"], v["error_rate_pass"], v["file_agrees_with_recomputation"], v["pass"]) == (4, False, False, False)
    _label_side(r, errors=1, n=30, file_errors=0)  # passing either way, but the file disagrees
    assert not G.cond3_review_and_verification(r)["verification"]["pass"]
    _label_side(r, errors=1, n=30, n_sample=29)  # the sample has fewer rows than the truth
    v = G.cond3_review_and_verification(r)["verification"]
    assert v["n_equals_sample"] is False and not v["pass"]
    _label_side(r, errors=1, n=30)
    vc = r / "labels_v2" / "verify" / "raw" / "verify-01" / "verification.csv"
    lines = vc.read_text().splitlines(keepends=True)
    vc.write_text("".join(lines[:-2]))  # two rows missing -> two more errors (3 of 30: still at most 10 %)
    v = G.cond3_review_and_verification(r)["verification"]
    assert v["recomputed"]["errors"] == 3 and v["error_rate_pass"] and not v["file_agrees_with_recomputation"]
    upper = [ln.split(",") for ln in lines[1:]]
    vc.write_text(lines[0] + "".join(",".join(p[:2] + [p[2].upper()] + p[3:]) for p in upper))  # the value's case is ignored
    assert G.cond3_review_and_verification(r)["verification"]["recomputed"]["errors"] == 1
    vc.unlink()
    v = G.cond3_review_and_verification(r)["verification"]
    assert v["recomputed"]["verifier_csv_present"] is False and v["recomputed"]["errors"] == 30 and not v["pass"]
    (r / "labels_v2" / "verify" / "verify_truth.json").unlink()
    assert G._guarded(lambda: G.cond3_review_and_verification(r))["pass"] is False


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def _worktrees(repo):
    return [ln for ln in _git(repo, "worktree", "list", "--porcelain").splitlines() if ln.startswith("worktree ")]


def _commit(repo, msg):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--no-verify", "-m", msg)


def _write_sessions(research, starts):
    """Synthetic copies of the launcher manifests, as the collector leaves them in labels_v2/sessions/ (+ its _status.json)."""
    sdir = research / "labels_v2" / "sessions"
    sdir.mkdir(parents=True, exist_ok=True)
    for i, s in enumerate(starts):
        name = f"pass1-walking_stopping-r0-{i + 1:02d}"
        (sdir / f"{name}.json").write_text(json.dumps({"session": name, "kind": "reader", "pass": "pass1",
                                                       "runs": [{"tag": "main", "pid": 1, "start_utc": s}]}, indent=1))
    (sdir / "_status.json").write_text(json.dumps([{"session": "pass1-walking_stopping-r0-01", "alive": False}]))


def build_gate_repo(tmp_path, world, monkeypatch, *, session_starts=(SESSION_START,), zenodo=None, name="repo"):
    """A throwaway git repository holding a synthetic research/ledger (every lock, chained, committed once; the label-code and
    scoring locks dated before the first session manifest) and copies of the lock tools. BRAINIR_DATA_DIR -> a temporary folder."""
    monkeypatch.setenv("BRAINIR_DATA_DIR", str(tmp_path / "data"))  # never the real data root
    repo = tmp_path / name
    research = repo / "research" / "ledger"
    shutil.copytree(world["research"], research)
    for rel in ("ledger/scripts/lock.py", "ledger/scripts/lock2.py", "ledger/src/brainir_ledger/__init__.py"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, repo / rel)
    dummy = repo / "ledger" / "scripts" / "labels2_dummy.py"
    dummy.write_text("X = 1\n")
    _label_side(research)
    shutil.rmtree(research / "labels_v2" / "verify")  # written after the labels lock (PREREG v2 L11)
    _write_sessions(research, session_starts)
    (research / "PREREG.md").write_text("rulebook v1\n")
    (research / "PREREG_v2.md").write_text("rulebook v2\n")
    _dump(research, "LOCK_prereg_v1.json", {"prereg": _hashes(research, ["PREREG.md"]),
                                            "frozen_code": {"ledger/scripts/lock.py": _sha(repo / "ledger" / "scripts" / "lock.py")},
                                            **({"authors_zenodo_configs_pinned": zenodo} if zenodo else {})})
    for lname, keys in (("LOCK_predictions_v1.json", ("prereg_lock_sha256",)), ("LOCK_labels_v1_1.json", ("prereg_lock_sha256", "labels_v1_lock_sha256"))):
        rec = json.loads((research / lname).read_text())
        rec.update({k: _sha(research / G.CHAINED[k]) for k in keys})
        _dump(research, lname, rec)
    v1 = {f"research/ledger/{n}": _sha(research / n) for n in G.LOCKS_V1}
    _dump(research, "LOCK_prereg_v2.json", {"prereg_v2": _hashes(research, ["PREREG_v2.md"]), "v1_locks": v1})
    chain = {"prereg_v2_lock_sha256": _sha(research / "LOCK_prereg_v2.json")}
    _dump(research, "LOCK_labelcode_v2.json", {"label_code": {"ledger/scripts/labels2_dummy.py": _sha(dummy),
                                                              "ledger/scripts/lock2.py": _sha(repo / "ledger" / "scripts" / "lock2.py")},
                                               "utc": LOCK_UTC, "v1_locks": v1, **chain})
    _dump(research, "LOCK_scoring_v2.json", {"scoring_code": {"ledger/scripts/lock.py": _sha(repo / "ledger" / "scripts" / "lock.py")},
                                             "utc": LOCK_UTC, "v1_locks": v1, **chain})
    _relock_labels_v2(research, {"v1_locks": v1, **chain, "labelcode_v2_lock_sha256": _sha(research / "LOCK_labelcode_v2.json"),
                                 "scoring_v2_lock_sha256": _sha(research / "LOCK_scoring_v2.json")})
    _relock_predictions_v2(research, extra=chain)
    _label_side(research)  # the verification files arrive after the labels lock (same content as locked for the rest)
    # an amendment (PREREG v2 L12): a bug fix of a locked code file, recorded (as lock2.py amend writes it) before it is committed
    old = _sha(dummy)
    dummy.write_text("X = 2\n")
    (research / "AMENDMENTS_v2.jsonl").write_text(json.dumps({
        "utc": "2026-11-21T02:00:00Z", "path": "ledger/scripts/labels2_dummy.py", "old": old, "new": _sha(dummy),
        "reason": "synthetic bug fix", "old_rev": "0" * 40, "v2_sessions_started": True, "v2_records_existed": True,
        "crash_fix": False, "after_unblinding": False}, sort_keys=True) + "\n")
    _git(repo, "init", "-q")
    for k, v in (("user.name", "test"), ("user.email", "test@example.invalid"), ("core.autocrlf", "false"), ("commit.gpgsign", "false")):
        _git(repo, "config", k, v)
    _commit(repo, "synthetic ledger")
    assert _git(repo, "status", "--porcelain", "--untracked-files=all") == "", "a synthetic file was not committed (global ignore rule?)"
    return repo


@pytest.fixture
def gate_repo(tmp_path, v2_world, monkeypatch):
    return build_gate_repo(tmp_path, v2_world, monkeypatch)


def test_gate_end_to_end_on_a_temporary_repository(gate_repo):
    repo = gate_repo
    research = repo / "research" / "ledger"
    worktrees = _worktrees(repo)
    res = G.evaluate(repo)
    c = res["conditions"]
    for k in G.CONDITIONS[:5]:
        assert c[k]["pass"] is True, (k, c[k])
    c1 = c["1_locks"]
    assert len(c1["locks"]) == 9 and c1["n_locks_present"] == 9
    assert c1["locks"]["LOCK_labels_v1_1.json"]["checks"].keys() == {"lock2.py", "lock.py"}
    assert c1["n_amended"] == 1 and res["amendments"][0]["path"] == "ledger/scripts/labels2_dummy.py" and c1["amendment_rows_ignored"] == []
    assert all(v["commits"]["n_commits"] == 1 for v in c1["locks"].values() if v["present"])
    assert c1["locks"]["LOCK_labels_v2.json"]["chain"]["verified"] == ["LOCK_labelcode_v2.json", "LOCK_prereg_v2.json", "LOCK_scoring_v2.json"]
    bf = c1["locked_before_first_v2_session"]
    assert bf["pass"] and bf["earliest_session_start_utc"] == SESSION_START and bf["n_session_manifests"] == 1
    assert c1["archive_members"] == {"n_pinned": 0, "members": {}, "archives_missing": [], "conflicting_pins": [], "pass": True}
    assert c["2_breaches"]["n_contributing"] == 5 and c["5_primary_set"]["n_types"] == 38
    assert c["6_reviewer_checklist"]["status"] == "pending" and res["conditions_1_to_5_hold"] and not res["all_conditions_hold"]
    for f in ("verification.json", "transcript_audit_verify.json", "verify_sample.csv", "verify_truth.json", "raw/verify-01/verification.csv"):
        assert f"research/ledger/labels_v2/verify/{f}" in res["inputs_sha256"], f  # L11: everything the verification wrote
    assert c["3_review_and_verification"]["verification"]["n_files_under_labels_v2_verify_hashed"] == 5
    assert res["checkout_removed"] and _worktrees(repo) == worktrees
    # run 1: the report goes to its own file; condition 6 pending -> exit 1
    assert G.main([], repo=repo) == 1
    r1, r2 = research / "gates_v2" / "UNBLINDING_GATE_run1.json", research / "gates_v2" / "UNBLINDING_GATE_run2.json"
    rep1 = json.loads(r1.read_text())
    assert rep1["gate_run"] == 1 and rep1["conditions_1_to_5_hold"] and rep1["conditions"]["6_reviewer_checklist"]["status"] == "pending"
    # an uncommitted file (here the report itself): refused, nothing evaluated
    with pytest.raises(G.GateRefused):
        G.evaluate(repo)
    _commit(repo, "gate run 1")
    assert G.main([], repo=repo) == 2 and not r2.exists()  # run 2 before the checklist: refused
    # the reviewer signs the checklist; everything committed -> all six hold
    (research / "reviews_v2" / "GATE_CHECKLIST.md").write_text("# Gate checklist\n\n**Verdict: confirmed.**\n\n1-5 hold; nothing joined.\n")
    _commit(repo, "checklist")
    first = _sha(r1)
    assert G.main([], repo=repo) == 0
    rep2 = json.loads(r2.read_text())
    assert rep2["all_conditions_hold"] is True and rep2["gate_run"] == 2 and rep2["run1_report_sha256"] == first == _sha(r1)
    assert rep2["conditions_1_to_5_identical_to_run1"] is True and rep2["conditions"]["6_reviewer_checklist"]["status"] == "confirmed"
    _commit(repo, "gate run 2")
    second = _sha(r2)
    assert G.main([], repo=repo) == 2 and _sha(r1) == first and _sha(r2) == second  # a third run: refused, nothing overwritten
    # a committed change to a locked label file fails condition 1
    p = research / "labels_v2" / "type_labels.csv"
    p.write_text(p.read_text() + "\n")
    _commit(repo, "tamper")
    res = G.evaluate(repo)
    lk = res["conditions"]["1_locks"]
    assert lk["pass"] is False and lk["locks"]["LOCK_labels_v2.json"]["pass"] is False and not res["all_conditions_hold"]
    assert _worktrees(repo) == worktrees
