"""Scoring v2 and the unblinding gate v2 (PREREG v2 Part S) on SYNTHETIC data in temporary folders only.

No real label or prediction file is read. Every UNBLIND.json is written inside a pytest temporary folder. The gate runs only on
temporary git repositories built here (never on the real tree, whose gate runs once)."""

import hashlib
import importlib.util
import json
import shutil
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
    _dump(research, "LOCK_labels_v2.json", {"labels": _hashes(research, top), "raw": _hashes(research, raw),
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
    on the first 30, B4v2 with every call value) and their locks. No flag file."""
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


# ---------------------------------------------------------------------------------------------------------------- refusals
def test_refuses_without_flag_file(v2_world):
    r = v2_world["research"]
    for name in P2.RUNS:
        with pytest.raises(BlindError, match="does not exist"):
            P2.run(name, r, r / "UNBLIND.json", n_boot=N, n_perm=N)
    assert not (r / "results").exists()


def test_refuses_unlisted_or_unknown_run(v2_world):
    r = v2_world["research"]
    flags = _write_flags(r, runs=("P",))
    for name in ("S-a", "S-b", "S-c"):
        with pytest.raises(BlindError, match="not listed"):
            P2.run(name, r, flags, n_boot=N, n_perm=N)
    with pytest.raises(BlindError, match="unknown run"):
        P2.run("X", r, flags, n_boot=N, n_perm=N)
    assert not (r / "results").exists()


def test_refuses_wrong_pairing_hash_name_or_missing_field(v2_world):
    r = v2_world["research"]
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


# ---------------------------------------------------------------------------------------------------------------- the four runs
def test_run_P_primary_on_labels_v2_once(v2_world):
    w = v2_world
    r = w["research"]
    flags = _write_flags(r)
    res = P2.run("P", r, flags, n_boot=N, n_perm=N)
    p = res["primary"]
    assert p["status"] == "ok", p
    assert (p["result"]["n"], p["result"]["n_pos"], p["result"]["n_neg"]) == (38, 9, 29)  # kit type 0 and by-nature type 5 excluded
    assert p["result"]["auroc"] == pytest.approx(w["expected_auroc_v2"])
    assert p["result"]["best_baseline"] in p["result"]["baselines_auroc"] and "decision" in p["result"]
    assert res["exposed_set"]["n_types"] == 2 and res["inputs"]["arms_locked"][0] == "A0"
    saved = json.loads((r / "results" / "run2" / "P.json").read_text())
    assert saved["primary"]["result"]["n"] == 38 and saved["unblind_flag"]["labels_lock"] == "LOCK_labels_v2.json"
    with pytest.raises(BlindError, match="once"):
        P2.run("P", r, flags, n_boot=N, n_perm=N)


def test_exposed_by_nature_set_comes_from_its_file(v2_world):
    w = v2_world
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


def test_run_S_a_primary_on_labels_v1_1_with_the_v1_list(v2_world):
    w = v2_world
    r = w["research"]
    res = P2.run("S-a", r, _write_flags(r), n_boot=N, n_perm=N)
    assert res["primary"]["status"] == "ok"
    assert res["primary"]["result"]["n"] == 39 and res["primary"]["result"]["auroc"] == pytest.approx(w["expected_auroc"])
    assert "kit/exposed_types.csv" in res["exposed_set"]["definition"]


def test_run_S_b_secondary_on_labels_v2(v2_world):
    r = v2_world["research"]
    res = P2.run("S-b", r, _write_flags(r), n_boot=N, n_perm=N)
    A = res["analyses"]
    assert "analyses_missing_from_code" not in res and "analyses_error" not in res
    assert set(PREREGISTERED_SECONDARY) <= set(A)
    for k in PREREGISTERED_SECONDARY:
        assert A[k]["status"] in ("ok", "not_locked", "input_missing"), (k, A[k])
    assert A["exposed_included"]["result"]["n"] == 40 and A["exposed_only"]["result"]["n"] == 2
    assert A["B1"]["status"] == "ok" and A["B4_stop"]["status"] == "ok" and A["B3_pairs"]["status"] == "not_locked"


def test_run_S_c_new_arms(v2_world):
    w = v2_world
    r = w["research"]
    res = P2.run("S-c", r, _write_flags(r), n_boot=N, n_perm=N)
    A = res["analyses"]
    assert set(P2.PREREGISTERED_S3) <= set(A) and "analyses_missing_from_code" not in res
    assert res["inputs"]["arms_locked"] == ["B1r", "B2r", "B4v2"] and "A1" in res["inputs"]["v1_arms_verified"]
    assert A["B1r"]["status"] == "ok" and A["B1r"]["result"]["n"] == 38
    assert A["B1r"]["result"]["auroc"] == pytest.approx(w["expected_b1r_auroc"])
    assert A["B2r"]["status"] == "ok" and A["B2r"]["result"]["n"] == 28  # first 30 types minus the two exposed
    tf = A["B1r_vs_B2r"]["result"]
    assert tf["n_common_types"] == 30 and 0 <= tf["top10_overlap"] <= 10 and tf["n_band_disagreements"] == len(tf["types_band_disagree"])
    assert A["B3_segment_pairs"]["status"] == "not_locked" and "G3" in A["B3_segment_pairs"]["reason"]
    ex, nh = A["B4v2_stop_lost_excluded"]["result"], A["B4v2_stop_lost_as_non_halts"]["result"]
    assert (ex["n"], ex["n_saturates"], ex["n_rhythm_lost_other"], ex["n_excluded_non_calls"]) == (18, 5, 5, 10)
    assert nh["n"] == 28 and sum(sum(col.values()) for col in nh["confusion"].values()) == 28
    mod = A["B4v2_modulation"]
    assert mod["status"] == "ok" and mod["result"]["n"] == 18 and mod["result"]["n_excluded_saturates_or_rhythm_lost_other"] == 10
    assert res["not_analysed"] == {"B6": "PREREG v2 S3: B6 is not analysed in run 2"}


def test_S_c_B3_segment_pairs_from_legs_csv(v2_world):
    w = v2_world
    r, types = w["research"], w["types"]
    d = r / "predictions_v2" / "B3"
    d.mkdir()
    _types_frame("B3", types, w["a1"]).to_csv(d / "types.csv", index=False)
    rows = [{"manc_type": t, "leg": leg, "score": (np.nan if (leg == "front" and i == 3) else float(w["a1"][i])), "frequency_hz": 10.0,
             "n_active": 3, "low_confidence": False} for i, t in enumerate(types) for leg in ("T1L", "front", "middle", "hind")]
    pd.DataFrame(rows).to_csv(d / "legs.csv", index=False)
    _relock_predictions_v2(r, arms=("B1r", "B2r", "B3", "B4v2"))
    res = P2.run("S-c", r, _write_flags(r), n_boot=N, n_perm=N)
    b3 = res["analyses"]["B3_segment_pairs"]
    assert b3["status"] == "ok", b3
    assert (b3["result"]["front"]["n"], b3["result"]["front"]["n_dropped_nonfinite"]) == (37, 1)
    assert b3["result"]["middle"]["n"] == 38 and b3["result"]["hind"]["n"] == 38


def test_S_c_refuses_a_broken_v1_chain_or_a_changed_v2_arm(v2_world):
    r = v2_world["research"]
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
    assert not (r / "results").exists()


def test_score_v2_cli(v2_world, capsys):
    r = v2_world["research"]
    assert SC.main(["--run", "P"], research=r) == 2  # no flag file
    _write_flags(r)
    assert SC.main(["--run", "P"], research=r) == 0
    assert "primary: ok" in capsys.readouterr().out and (r / "results" / "run2" / "P.json").exists()
    assert SC.main(["--run", "P"], research=r) == 2  # each run once


# ---------------------------------------------------------------------------------------------------------------- the gate
def _write_ids(path, ids):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps({"exp_id": e}) + "\n" for e in ids))


def _label_side(research, *, final=None, pass2=None, adjudication=None, atlas=(), breach=(), unaudited=(), verifiers=("verify-01",),
                verifier="verify-01", n=30, errors=1, kappa=0.8, verdict="**Verdict: labels usable with caveats, no blocker.**"):
    """The label-side files the gate reads (synthetic): records (exp_ids only when `final` is given), raw pass-2 /
    adjudication / atlas session folders, both transcript audits, verification, agreement and the label review."""
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
    (lab / "verify").mkdir(parents=True)
    (lab / "verify" / "transcript_audit_verify.json").write_text(json.dumps([{"session": s, "kind": "verify", "breach": s in breach}
                                                                             for s in verifiers if s not in unaudited]))
    (lab / "verify" / "verification.json").write_text(json.dumps({"n": n, "errors": errors, "error_rate": errors / n if n else None,
                                                                  "blocker": (errors / n > 0.10) if n else True, "verifier_session": verifier}))
    (lab / "verify" / "verify_sample.csv").write_text("exp_id,doi,source_locator,driver_lines,name_in_paper,quote\n")
    if verifier:
        (lab / "verify" / "raw" / verifier).mkdir(parents=True)
        (lab / "verify" / "raw" / verifier / "verification.csv").write_text("exp_id,quote_found,front_leg_rhythm,locator,comment\n")
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
    for verdict, ok in (("**Verdict: labels usable with caveats, no blocker.**", True), ("Verdict: usable", True),
                        ("**Verdict: blocked** (two blockers)", False), ("## Verdict\n\nBlocked: the atlas could not be read.", False),
                        ("No verdict line here.", False)):
        _label_side(r, final=final, verdict=verdict)
        assert G.cond3_review_and_verification(r)["review"]["pass"] is ok, verdict
    _label_side(r, errors=3, n=30)
    assert G.cond3_review_and_verification(r)["pass"]
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


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def _worktrees(repo):
    return [ln for ln in _git(repo, "worktree", "list", "--porcelain").splitlines() if ln.startswith("worktree ")]


def _commit(repo, msg):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--no-verify", "-m", msg)


@pytest.fixture
def gate_repo(tmp_path, v2_world):
    """A throwaway git repository holding a synthetic research/ledger (every lock, chained) and copies of the lock tools."""
    repo = tmp_path / "repo"
    research = repo / "research" / "ledger"
    shutil.copytree(v2_world["research"], research)
    for rel in ("ledger/scripts/lock.py", "ledger/scripts/lock2.py", "ledger/src/brainir_ledger/__init__.py"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, repo / rel)
    dummy = repo / "ledger" / "scripts" / "labels2_dummy.py"
    dummy.write_text("X = 1\n")
    _label_side(research)
    shutil.rmtree(research / "labels_v2" / "verify")  # written after the labels lock (PREREG v2 L11)
    (research / "PREREG.md").write_text("rulebook v1\n")
    (research / "PREREG_v2.md").write_text("rulebook v2\n")
    _dump(research, "LOCK_prereg_v1.json", {"prereg": _hashes(research, ["PREREG.md"]),
                                            "frozen_code": {"ledger/scripts/lock.py": _sha(repo / "ledger" / "scripts" / "lock.py")}})
    for name, keys in (("LOCK_predictions_v1.json", ("prereg_lock_sha256",)), ("LOCK_labels_v1_1.json", ("prereg_lock_sha256", "labels_v1_lock_sha256"))):
        rec = json.loads((research / name).read_text())
        rec.update({k: _sha(research / G.CHAINED[k]) for k in keys})
        _dump(research, name, rec)
    v1 = {f"research/ledger/{n}": _sha(research / n) for n in G.LOCKS_V1}
    _dump(research, "LOCK_prereg_v2.json", {"prereg_v2": _hashes(research, ["PREREG_v2.md"]), "v1_locks": v1})
    chain = {"prereg_v2_lock_sha256": _sha(research / "LOCK_prereg_v2.json")}
    _dump(research, "LOCK_labelcode_v2.json", {"label_code": {"ledger/scripts/labels2_dummy.py": _sha(dummy),
                                                              "ledger/scripts/lock2.py": _sha(repo / "ledger" / "scripts" / "lock2.py")},
                                               "v1_locks": v1, **chain})
    _dump(research, "LOCK_scoring_v2.json", {"scoring_code": {"ledger/scripts/lock.py": _sha(repo / "ledger" / "scripts" / "lock.py")},
                                             "v1_locks": v1, **chain})
    _relock_labels_v2(research, {"v1_locks": v1, **chain, "labelcode_v2_lock_sha256": _sha(research / "LOCK_labelcode_v2.json")})
    _relock_predictions_v2(research, extra=chain)
    _label_side(research)  # the verification files arrive after the labels lock (same content as locked for the rest)
    # an amendment (PREREG v2 L12): a bug fix of a locked code file, recorded before it is committed
    old = _sha(dummy)
    dummy.write_text("X = 2\n")
    (research / "AMENDMENTS_v2.jsonl").write_text(json.dumps({"path": "ledger/scripts/labels2_dummy.py", "old": old, "new": _sha(dummy),
                                                              "reason": "synthetic bug fix"}) + "\n")
    _git(repo, "init", "-q")
    for k, v in (("user.name", "test"), ("user.email", "test@example.invalid"), ("core.autocrlf", "false"), ("commit.gpgsign", "false")):
        _git(repo, "config", k, v)
    _commit(repo, "synthetic ledger")
    assert _git(repo, "status", "--porcelain", "--untracked-files=all") == "", "a synthetic file was not committed (global ignore rule?)"
    return repo


def test_gate_end_to_end_on_a_temporary_repository(gate_repo):
    repo = gate_repo
    worktrees = _worktrees(repo)
    res = G.evaluate(repo)
    c = res["conditions"]
    for k in G.CONDITIONS[:5]:
        assert c[k]["pass"] is True, (k, c[k])
    assert len(c["1_locks"]["locks"]) == 9 and c["1_locks"]["n_locks_present"] == 9
    assert c["1_locks"]["locks"]["LOCK_labels_v1_1.json"]["checks"].keys() == {"lock2.py", "lock.py"}
    assert c["1_locks"]["n_amended"] == 1 and res["amendments"][0]["path"] == "ledger/scripts/labels2_dummy.py"
    assert c["2_breaches"]["n_contributing"] == 5 and c["5_primary_set"]["n_types"] == 38
    assert c["6_reviewer_checklist"]["status"] == "pending" and res["conditions_1_to_5_hold"] and not res["all_conditions_hold"]
    for f in ("verification.json", "transcript_audit_verify.json", "verify_sample.csv", "raw/verify-01/verification.csv"):
        assert f"research/ledger/labels_v2/verify/{f}" in res["inputs_sha256"], f  # L11: everything the verification wrote
    assert c["3_review_and_verification"]["verification"]["n_files_under_labels_v2_verify_hashed"] == 4
    assert res["checkout_removed"] and _worktrees(repo) == worktrees
    # the script writes its report into the repository it is given; condition 6 pending -> exit 1
    assert G.main([], repo=repo) == 1
    out = repo / "research" / "ledger" / "gates_v2" / "UNBLINDING_GATE.json"
    assert json.loads(out.read_text())["conditions_1_to_5_hold"] is True
    # an uncommitted file (here the report itself): refused, nothing evaluated
    with pytest.raises(G.GateRefused):
        G.evaluate(repo)
    assert G.main([], repo=repo) == 2
    # the reviewer signs the checklist; everything committed -> all six hold
    (repo / "research" / "ledger" / "reviews_v2" / "GATE_CHECKLIST.md").write_text("# Gate checklist\n\n**Verdict: confirmed.** 1-5 hold; nothing joined.\n")
    _commit(repo, "gate report and checklist")
    first = _sha(out)
    assert G.main([], repo=repo) == 0
    rep = json.loads(out.read_text())
    assert rep["all_conditions_hold"] is True and rep["previous_output_sha256"] == first
    # a committed change to a locked label file fails condition 1
    p = repo / "research" / "ledger" / "labels_v2" / "type_labels.csv"
    p.write_text(p.read_text() + "\n")
    _commit(repo, "tamper")
    res = G.evaluate(repo)
    lk = res["conditions"]["1_locks"]
    assert lk["pass"] is False and lk["locks"]["LOCK_labels_v2.json"]["pass"] is False and not res["all_conditions_hold"]
    assert _worktrees(repo) == worktrees
