"""Post-lock drivers (scripts/p4/ablations_p4.py, counterexamples_p4.py, robustness_p4.py, counterfactual_p4.py, self_audit_p4.py and the
shared package scripts/p4/p4post): the ablation contract, the hidden-data guard and the run ledger, paired statistics, the item-set
planners, the trusted iso "call" roles run locally over the LocalUnsafe transport (trusted toy methods only), the execution layer with a
fake backend, and the self-audit executor on empty inputs. No Modal call, no hidden data."""

from __future__ import annotations

import json
import pickle
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p4"))

from p4post import common as C  # noqa: E402
from p4post import declare as D  # noqa: E402
from p4post import execute as X  # noqa: E402
from p4post import isojob as J  # noqa: E402
from p4post import itemsets as IS  # noqa: E402
from p4post import pairstats as PS  # noqa: E402

from brainir_causal import isolation as I  # noqa: E402
from brainir_causal import protocol as P  # noqa: E402
from brainir_causal import suites as S  # noqa: E402
from brainir_causal.api import ABLATION_SWITCHES  # noqa: E402


# ================================================================================================================ the ablation contract
def _decl(**over):
    d = {n: "honoured" for n in ABLATION_SWITCHES}
    d.update(over)
    return d


def test_parse_switch_spellings():
    assert D.parse_switch("honoured") == (D.HONOURED, "")
    assert D.parse_switch("honored") == (D.HONOURED, "")
    assert D.parse_switch(True) == (D.HONOURED, "")
    assert D.parse_switch({"status": "not_applicable", "reason": "no designer"}) == (D.NOT_APPLICABLE, "no designer")
    assert D.parse_switch(["not_applicable", "single system"]) == (D.NOT_APPLICABLE, "single system")
    assert D.parse_switch("not_applicable: no ensemble") == (D.NOT_APPLICABLE, "no ensemble")
    assert D.parse_switch("not applicable (no lift)")[0] == D.NOT_APPLICABLE
    for bad in ("not_applicable", {"status": "not_applicable"}, ["not_applicable", ""], "maybe", 3, None, {"status": "off"}):
        with pytest.raises(ValueError):
            D.parse_switch(bad)


def test_declaration_fails_loudly_on_every_problem():
    ok = D.check_declaration({"ablation_switches": _decl(active_design={"status": "not_applicable", "reason": "none"})}, "m")
    assert ok["active_design"]["status"] == D.NOT_APPLICABLE and ok["state_bottleneck"]["status"] == D.HONOURED
    with pytest.raises(D.AblationContractError, match="missing"):
        D.check_declaration({}, "m")                                          # the frozen Phase 3 baseline declares nothing
    d = _decl()
    del d["closure_loss"]
    d["not_a_switch"] = "honoured"
    d["mediation_loss"] = "not_applicable"
    with pytest.raises(D.AblationContractError) as e:
        D.check_declaration({"ablation_switches": d}, "m")
    msg = str(e.value)
    assert "closure_loss" in msg and "not_a_switch" in msg and "without a reason" in msg


def test_application_must_match_the_request():
    decl = D.check_declaration({"ablation_switches": _decl(shared_dynamics="not_applicable: one system")}, "m")
    D.check_applied({"ablated": ["mediation_loss"]}, ["mediation_loss"], decl, "m")
    with pytest.raises(D.AblationContractError, match="requested but not applied"):
        D.check_applied({"ablated": []}, ["mediation_loss"], decl, "m")          # declared honoured, not applied
    with pytest.raises(D.AblationContractError, match="applied but not requested"):
        D.check_applied({"ablated": ["mediation_loss", "closure_loss"]}, ["mediation_loss"], decl, "m")
    with pytest.raises(D.AblationContractError, match="not declared honoured"):
        D.check_applied({"ablated": ["shared_dynamics"]}, ["shared_dynamics"], decl, "m")
    with pytest.raises(D.AblationContractError, match="missing or not a list"):
        D.check_applied({}, ["mediation_loss"], decl, "m")
    plan = D.switch_plan({"s1": decl, "s2": decl})
    assert plan["shared_dynamics"]["not_applicable_on"] == {"s1": "one system", "s2": "one system"}
    assert plan["closure_loss"]["honoured_on"] == ["s1", "s2"]


def test_standin_declaration_follows_the_contract():
    sys.path.insert(0, str(ROOT / "scripts" / "p4"))
    from brainir_causal import runner as RN
    RN.mount_methods(ROOT / "scripts" / "p4" / "standin_methods")
    import importlib
    mod = importlib.import_module("brainir_causal.methods.p3stand.refstand")
    decl = D.check_declaration({"ablation_switches": mod.declaration()}, "stand-in")
    assert {n for n, v in decl.items() if v["status"] == D.HONOURED} == set(mod.HONOURED)
    assert "interventional_training" in mod.HONOURED and "state_bottleneck" in mod.HONOURED


# ================================================================================================================ guard / ledger / log
def test_guard_refuses_hidden_tiers_before_the_lock(monkeypatch, tmp_path):
    """The OFFICIAL rule (no dry-run flag): dev / toy / public real data only before the lock; val never; conf / real C need the lock."""
    monkeypatch.setattr(S, "METHOD_LOCK", tmp_path / "METHOD_LOCK.json")
    g = C.guard("dev", None, what="t")
    assert g["hidden"] is False and g["dry_run"] is True and g["dry_run_on_val"] is False
    assert C.guard("dev", "public", what="t")["hidden"] is False
    for tier, real in (("conf", None), (None, "C"), ("dev", "C")):
        with pytest.raises(PermissionError):
            C.guard(tier, real, what="t")                                    # an official run on hidden data, pre-lock: refused
    with pytest.raises(PermissionError, match="selection tier"):
        C.guard("val", None, what="t")                                       # val is never opened without the dry-run flag
    with pytest.raises(PermissionError, match="selection tier"):
        C.guard("val", None, what="t", methods=["p3stand.refstand:p3stand_ref"], methods_dir=C.STANDIN_METHODS)   # nor by stand-ins alone
    with pytest.raises(PermissionError):
        C.guard("dev", "B", what="t")


STANDIN = "p3stand.refstand:p3stand_ref"


def test_val_dry_run_allowance_is_narrow(monkeypatch, tmp_path):
    """The coordinator's constraints (2026-09-27): (1) pre-lock only, (2) stand-in methods only (never the locked package, never a
    developer's method), (3) the val tier only (never conf / real_levelc)."""
    monkeypatch.setattr(S, "METHOD_LOCK", tmp_path / "METHOD_LOCK.json")
    ok = C.guard("val", None, what="t", dry_run_on_val=True, methods=[STANDIN, "frozen_brainir_state_v1"], methods_dir=C.STANDIN_METHODS)
    assert ok["dry_run"] and ok["dry_run_on_val"] and not ok["hidden"] and ok["tier"] == "val"          # val dry run with a stand-in: allowed
    assert ok["stand_in"]["standin_package"] == "scripts/p4/standin_methods"
    # (2) a non-stand-in method is refused, whatever the directory
    for bad in ("li.ssm:li_ssm", "some_method", "p3stand.refstand:not_registered"):
        with pytest.raises(PermissionError, match="stand-in methods only"):
            C.guard("val", None, what="t", dry_run_on_val=True, methods=[STANDIN, bad], methods_dir=C.STANDIN_METHODS)
    with pytest.raises(PermissionError, match="stand-in methods only"):
        C.guard("val", None, what="t", dry_run_on_val=True, methods=[], methods_dir=C.STANDIN_METHODS)
    # (2) the locked methods package, a room-like directory or a modified copy of the stand-ins is refused
    with pytest.raises(PermissionError, match="locked methods package"):
        C.guard("val", None, what="t", dry_run_on_val=True, methods=[STANDIN], methods_dir=C.LOCKED_METHODS)
    room = tmp_path / "room_methods" / "dev1"
    room.mkdir(parents=True)
    (room / "m.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(PermissionError, match="stand-in package"):
        C.guard("val", None, what="t", dry_run_on_val=True, methods=[STANDIN], methods_dir=room.parent)
    with pytest.raises(PermissionError, match="stand-in package"):
        C.guard("val", None, what="t", dry_run_on_val=True, methods=[STANDIN], methods_dir=None)
    import shutil
    snap = tmp_path / "snap"
    shutil.copytree(C.STANDIN_METHODS, snap, ignore=shutil.ignore_patterns("__pycache__"))
    assert C.guard("val", None, what="t", dry_run_on_val=True, methods=[STANDIN], methods_dir=snap)["dry_run_on_val"]   # a byte-identical snapshot
    (snap / "p3stand" / "refstand.py").write_text((snap / "p3stand" / "refstand.py").read_text(encoding="utf-8") + "\n# edited\n",
                                                   encoding="utf-8")
    with pytest.raises(PermissionError, match="stand-in package"):
        C.guard("val", None, what="t", dry_run_on_val=True, methods=[STANDIN], methods_dir=snap)          # a modified copy is not
    # (3) the flag never opens another tier or a real level
    for tier, real in (("conf", None), ("dev", None), ("val", "C"), ("val", "public"), (None, "C"), ("real_levelc", None)):
        with pytest.raises(PermissionError, match="val tier only"):
            C.guard(tier, real, what="t", dry_run_on_val=True, methods=[STANDIN], methods_dir=C.STANDIN_METHODS)
    # (1) after the lock the flag is refused outright (and the official rule refuses val as before)
    (tmp_path / "METHOD_LOCK.json").write_text("{}", encoding="utf-8")
    with pytest.raises(PermissionError, match="pre-lock"):
        C.guard("val", None, what="t", dry_run_on_val=True, methods=[STANDIN], methods_dir=C.STANDIN_METHODS)
    with pytest.raises(PermissionError, match="selection tier"):
        C.guard("val", None, what="t")


def test_dry_runs_write_only_dry_run_locations_and_record_their_marks(monkeypatch, tmp_path):
    """(4) outputs of a dry run only under the dry-run roots; (5) the run record carries the flag, the tier and the stand-in."""
    monkeypatch.setattr(S, "METHOD_LOCK", tmp_path / "METHOD_LOCK.json")
    monkeypatch.setattr(C, "RUN_DRY_ROOT", tmp_path / "run_dry")
    monkeypatch.setattr(C, "DRY_ROOT", tmp_path / "out_dry")
    monkeypatch.setattr(C, "DRY_ROOTS", (tmp_path / "out_dry", tmp_path / "run_dry"))
    rd = C.RunDirs("ablations", "v1", hidden=False)
    assert rd.run == tmp_path / "run_dry" / "ablations" / "v1" and rd.out == tmp_path / "out_dry" / "ablations" / "v1"
    with pytest.raises(PermissionError, match="dry-run roots"):
        C.RunDirs("ablations", "v2", hidden=False, out_root=C.OUT_ROOT)       # never the official summaries location
    with pytest.raises(PermissionError, match="dry-run roots"):
        C.RunDirs("ablations", "v3", hidden=False, run_root=C.RUN_ROOT)       # never the official bulky location
    g = C.guard("val", None, what="t", dry_run_on_val=True, methods=[STANDIN], methods_dir=C.STANDIN_METHODS)
    marks = C.run_marks(g, "val", None)
    assert marks["dry_run"] and marks["dry_run_on_val"] and marks["tier"] == "val" and marks["stand_in"]["methods"] == [STANDIN]
    assert "not a result" in marks["not_a_result"]
    assert C.dry_banner(marks)[0].startswith("**DRY RUN** (val tier")
    official = C.run_marks({"hidden": True, "lock": {"method": "m"}}, "conf", "C")
    assert official["dry_run"] is False and "stand_in" not in official and C.dry_banner(official) == []
    # a dry run's custom item sets live in their own tiers: an official run never reads items a dry run built
    assert C.custom_tier("ce", "x1", "r1", hidden=False) == "pl_dry_ce_x1_r1" and C.custom_tier("ce", "x1", "r1", hidden=True) == "pl_ce_x1_r1"


def test_self_audit_dry_run_output_must_be_a_dry_location(monkeypatch, tmp_path):
    import self_audit_p4 as SA
    monkeypatch.setattr(S, "METHOD_LOCK", tmp_path / "METHOD_LOCK.json")
    cfg = {"tier": None, "real_level": None, "method": "m", "dirs": {}, "out_dir": str(C.ROOT / "research" / "phase4")}
    cp = tmp_path / "cfg.json"
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(PermissionError, match="dry-run roots"):
        SA.main(["run", "--config", str(cp)])                                 # research/phase4 is the OFFICIAL SELF_AUDIT location


class _Stop(Exception):
    """Raised by the patched backend: the run stops before any Modal call."""


DRIVERS = {"ablations_p4": "ablations", "counterexamples_p4": "counterexamples", "robustness_p4": "robustness",
           "counterfactual_p4": "counterfactual"}


def _driver_world(monkeypatch, tmp_path):
    """Pre-lock; every root in tmp_path; fake systems, plan records, fitted models and item plans; a backend that stops the run."""
    monkeypatch.setattr(S, "METHOD_LOCK", tmp_path / "METHOD_LOCK.json")
    monkeypatch.setattr(C, "RUN_ROOT", tmp_path / "run_official")
    monkeypatch.setattr(C, "OUT_ROOT", tmp_path / "out_official")
    monkeypatch.setattr(C, "RUN_DRY_ROOT", tmp_path / "run_dry")
    monkeypatch.setattr(C, "DRY_ROOT", tmp_path / "out_dry")
    monkeypatch.setattr(C, "DRY_ROOTS", (tmp_path / "out_dry", tmp_path / "run_dry"))
    monkeypatch.setattr(C, "resolve_systems", lambda tier, real, sel=None: {"sys_a": {"kind": "synthetic", "tier": tier}})
    monkeypatch.setattr(C, "plan_records", lambda tier, real, sids: {s: {"pub": {}, "internal": {}} for s in sids})
    from p4post import levelc_io
    monkeypatch.setattr(levelc_io, "model_source", lambda *a, **k: tmp_path / "model.pkl")
    monkeypatch.setattr(IS, "search_families", lambda pub, internal, exclude=(): ["fam.a"])
    monkeypatch.setattr(IS, "robustness_specs", lambda *a, **k: ([], {}))
    monkeypatch.setattr(IS, "build_job", lambda *a, **k: {"job": "stub"})

    def stop(*a, **k):
        raise _Stop()
    monkeypatch.setattr(C, "backend", stop)


def _written(tmp_path) -> list[str]:
    return sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())


@pytest.mark.parametrize("mod", sorted(DRIVERS))
def test_every_driver_applies_the_val_allowance_and_records_its_marks(mod, monkeypatch, tmp_path):
    """Each CLI driver, end to end up to its first Modal call: an official run on hidden data pre-lock is refused; val is refused without
    the flag; a val dry run with a non-stand-in method or on another tier is refused; nothing is written by a refused run; the allowed
    val dry run with a stand-in writes its run record under the dry-run roots only, with the flag, the tier and the stand-in (conditions
    1-5); after the lock the flag is refused."""
    import importlib
    drv = importlib.import_module(mod)
    _driver_world(monkeypatch, tmp_path)
    base = ["run", "--methods-dir", str(C.STANDIN_METHODS), "--run-id", "t1"] + ([] if mod == "ablations_p4" else ["--fits-from", str(tmp_path / "fits")])
    ok = [*base, "--method", STANDIN]
    with pytest.raises(PermissionError):
        drv.main([*ok, "--tier", "conf"])                                    # official run on hidden data, pre-lock
    with pytest.raises(PermissionError, match="selection tier"):
        drv.main([*ok, "--tier", "val"])                                     # val without the flag
    with pytest.raises(PermissionError, match="stand-in methods only"):
        drv.main([*base, "--method", "li.ssm:li_ssm", "--tier", "val", "--dry-run-on-val"])   # a developer's method
    with pytest.raises(PermissionError, match="locked methods package"):
        drv.main(["run", "--methods-dir", str(C.LOCKED_METHODS), "--method", STANDIN, "--tier", "val", "--dry-run-on-val"])
    for tier in ("conf", "dev"):
        with pytest.raises(PermissionError, match="val tier only"):
            drv.main([*ok, "--tier", tier, "--dry-run-on-val"])
    with pytest.raises(PermissionError, match="val tier only"):
        drv.main([*ok, "--real", "C", "--dry-run-on-val"])
    assert _written(tmp_path) == []
    with pytest.raises(_Stop):
        drv.main([*ok, "--tier", "val", "--dry-run-on-val"])                 # allowed: stops at the backend
    rec = json.loads((tmp_path / "out_dry" / DRIVERS[mod] / "t1" / "RUN.json").read_text(encoding="utf-8"))
    assert rec["dry_run"] is True and rec["dry_run_on_val"] is True and rec["hidden"] is False and rec["tier"] == "val"
    assert rec["stand_in"]["methods"][0] == STANDIN and rec["stand_in"]["standin_package"] == "scripts/p4/standin_methods"
    assert "not a result" in rec["not_a_result"] and rec["lock"] == {}
    assert not (tmp_path / "run_official").exists() and not (tmp_path / "out_official").exists()
    assert all(p.startswith(("out_dry/", "run_dry/")) for p in _written(tmp_path))
    (tmp_path / "METHOD_LOCK.json").write_text("{}", encoding="utf-8")
    with pytest.raises(PermissionError, match="pre-lock"):
        drv.main([*ok, "--tier", "val", "--dry-run-on-val"])


def test_self_audit_commands_apply_the_val_allowance_and_record_their_marks(monkeypatch, tmp_path):
    import self_audit_p4 as SA
    _driver_world(monkeypatch, tmp_path)
    monkeypatch.setattr(S, "tier_dirs", lambda tier, root: {"base": tmp_path / "no_suite"})
    out = tmp_path / "out_dry" / "self_audit" / "t1"
    cfg = {"tier": "val", "real_level": None, "dry_run_on_val": True, "method": STANDIN, "methods_dir": str(C.STANDIN_METHODS),
           "prep_methods_dir": str(C.STANDIN_METHODS), "role_methods": {"id_baseline": "p3stand.refstand:p3stand_idshortcut"},
           "dirs": {}, "prep_run_dir": str(tmp_path / "run_dry" / "self_audit"), "probes_dir": str(tmp_path / "run_dry" / "probes"),
           "out_dir": str(out)}
    cp = tmp_path / "cfg" / "c.json"
    cp.parent.mkdir()

    def refused(c, match):
        cp.write_text(json.dumps(c), encoding="utf-8")
        for cmd in ("prep", "probes", "run"):
            with pytest.raises(PermissionError, match=match):
                SA.main([cmd, "--config", str(cp)])
    refused(dict(cfg, role_methods={"id_baseline": "li.ssm:li_ssm"}), "stand-in methods only")
    refused(dict(cfg, tier="conf"), "val tier only")
    refused(dict(cfg, dry_run_on_val=False), "selection tier")
    refused(dict(cfg, out_dir=str(C.ROOT / "research" / "phase4"), prep_run_dir=str(C.RUN_ROOT / "x"), probes_dir=str(C.OUT_ROOT / "x")),
            "dry-run")
    assert not (tmp_path / "out_dry").exists() and not (tmp_path / "run_dry").exists()
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    assert SA.main(["run", "--config", str(cp)]) == 0
    rec = json.loads((out / "SELF_AUDIT.json").read_text(encoding="utf-8"))
    assert rec["dry_run"] and rec["dry_run_on_val"] and rec["tier"] == "val" and rec["hidden"] is False
    assert rec["stand_in"]["methods"] == [STANDIN, "p3stand.refstand:p3stand_idshortcut"] and "not a result" in rec["not_a_result"]
    assert (out / "SELF_AUDIT.md").read_text(encoding="utf-8").splitlines()[2].startswith("**DRY RUN** (val tier")
    (tmp_path / "METHOD_LOCK.json").write_text("{}", encoding="utf-8")
    refused(cfg, "pre-lock")


def test_ledger_resumes_and_refuses_a_second_run(tmp_path):
    led = tmp_path / "LEDGER.json"
    a = C.ledger_claim("ablations", "r1", ledger=led)
    assert C.ledger_claim("ablations", "r1", ledger=led) == a
    with pytest.raises(PermissionError, match="already ran"):
        C.ledger_claim("ablations", "r2", ledger=led)
    assert C.ledger_claim("ablations", "r2", new_run_reason="infrastructure: app killed", ledger=led)["reason"].startswith("infra")
    C.ledger_claim("robustness", "r9", ledger=led)                           # another study is independent


def test_hidden_log_rows_only_for_hidden_runs(tmp_path):
    log = tmp_path / "H.md"
    with C.HiddenRunLog(False, "ablations", "dry", "x", log=log):
        pass
    assert not log.exists()
    with C.HiddenRunLog(True, "ablations", "r1", "m|x", log=log):
        pass
    with pytest.raises(RuntimeError):
        with C.HiddenRunLog(True, "ablations", "r1", "m", log=log):
            raise RuntimeError("boom")
    rows = [r for r in log.read_text(encoding="utf-8").splitlines() if r.startswith("| 20")]
    assert [r.split(" | ")[1] for r in rows] == ["START", "DONE", "START", "FAILED"]
    assert all(r.count(" | ") == 4 for r in rows)                           # the Level C log's five columns
    assert "m/x" in rows[0]


# ================================================================================================================ statistics
def test_suite_paired_charges_missing_values_and_is_one_sided():
    sids = [f"s{i}" for i in range(12)]
    rng = np.random.default_rng(0)
    full = {s: 0.5 + 0.05 * rng.standard_normal() for s in sids}
    worse = {s: v + 0.3 for s, v in full.items()}
    r = PS.suite_paired(worse, full, sids, worst=10.0, direction="lower", n_boot=500)
    assert r["point"] == pytest.approx(0.3, abs=1e-9) and r["lower95"] > 0 and r["p_a_worse"] <= 0.05 and r["p_a_better"] > 0.5
    miss = dict(worse)
    miss.pop("s0")
    r2 = PS.suite_paired(miss, full, sids, worst=10.0, direction="lower", n_boot=500)
    assert r2["n_charged_a"] == 1 and r2["point"] > r["point"]                # a missing ablated value counts against the ablation
    same = PS.suite_paired(full, full, sids, worst=10.0, n_boot=500)
    assert same["point"] == 0.0 and same["p_a_worse"] > 0.5
    hi = PS.suite_paired({s: 0.9 for s in sids}, {s: 0.5 for s in sids}, sids, worst=0.0, direction="higher", n_boot=200)
    assert hi["p_a_better"] <= 0.05                                          # higher-is-better metrics flip the direction


def test_critical_ablations_charge_missing_values_against_the_claim(monkeypatch, tmp_path):
    """Q20 ("the passive-only ablation is worse"): a missing ablated value is neutral, a missing full-method value at its worst; no
    compressible system -> NOT TESTABLE (never FAIL). Q21's difference: a missing locked-method value at its worst, a missing direct
    value neutral."""
    import ablations_p4 as AB
    vals = {"abl_interventional_training": {"s1": 0.9, "s2": None, "s3": 0.95}, "full": {"s1": 0.5, "s2": 0.4, "s3": None},
            "abl_state_bottleneck": {"s1": 0.3, "s2": None, "s3": 0.6}}
    monkeypatch.setattr(AB, "_vals", lambda run, variant, sids, seed, metric: {s: vals[variant].get(s) for s in sids})
    sp = AB.q20(tmp_path, ["s1", "s2", "s3"], [], 0, ["interventional_training"], 200)["suite"]
    assert sp["n_charged_a"] == 1 and sp["n_charged_b"] == 1
    assert sp["per_system"]["s2"] == 0.0 and sp["per_system"]["s3"] == pytest.approx(0.95 - 10.0)
    assert AB.q20(tmp_path, [], [], 0, ["interventional_training"], 200)["status"] == "NOT TESTABLE"
    assert AB.q20(tmp_path, ["s1"], [], 0, [], 200)["status"] == "NOT TESTABLE"
    q = AB.q21(tmp_path, ["s1", "s2", "s3"], [], 0, ["state_bottleneck"], {"delta_A": 0.2}, {"delta_C_suite": 0.05},
               {"extra_methods": {}}, 200)
    d = q["direct_variant"]["EE_M_minus_direct_suite"]["per_system"]
    assert d["s2"] == 0.0 and d["s3"] == pytest.approx(10.0 - 0.6)          # direct missing: neutral; locked method missing: worst


def test_metric_reads_full_results():
    res = {"items": {"effects": {"EE_medium": {"point": 0.7}, "post_nmse_medium": {"point": 0.2}}, "calibration": {"coverage": 0.9,
           "false_confidence_verdict": {"rate": 0.1}}, "observational": {"obs_nmse_medium": {"point": 0.3}}},
           "mediation": {"SMS": {"point": 0.05}, "SMS_id": {"failed": True}}, "closure": {"ICG_y": {"point": 0.02}},
           "micro": {"testable": False, "MEV": {"point": 0.1}}, "lift": {"success_rate": 0.25, "consistency": {"testable": False}}, "k": 3}
    assert PS.metric(res, "EE_pooled") == 0.7 and PS.metric(res, "post_nmse") == 0.2 and PS.metric(res, "obs_nmse") == 0.3
    assert PS.metric(res, "SMS") == 0.05 and PS.metric(res, "SMS_id") == 1.0 and PS.metric(res, "ICG_y") == 0.02
    assert PS.metric(res, "MEV") is None and PS.metric(res, "lift_success") == 0.25 and PS.metric(res, "lift_consistency") is None
    assert PS.metric(res, "false_confidence") == 0.1 and PS.metric(res, "k") == 3.0 and PS.metric(None, "EE") is None


# ================================================================================================================ item sets
def _toy():
    pubs, ints, _ = S.synthetic_tier_records("toy", S.DEV_SEED)
    sid = sorted(pubs)[0]
    return sid, pubs[sid], ints[sid]


def test_counterexample_genomes_realise_valid_items():
    sid, pub, internal = _toy()
    fams = IS.search_families(pub, internal)
    assert fams and all(f not in ("kick.hi", "pulse.hi") for f in fams)
    rng = np.random.default_rng(1)
    seed_fn = IS.seed_function(False, "t", sid)
    g = IS.random_genome(pub, internal, fams, rng, seed_fn, "r1c0")
    sp = IS.realize(g, pub, internal, role="ce:r1")
    assert sp.twin and sp.split == "test" and sp.role == "ce:r1" and sp.meta["p4post"]["cid"] == "r1c0"
    P.validate(sp.protocol)
    assert IS.realize(g, pub, internal, role="ce:r1").protocol == sp.protocol                  # deterministic in the genome
    for j in range(30):
        c = IS.mutate(g, pub, internal, fams, rng, seed_fn, f"r2c{j}")
        assert IS.MULT_RANGE[0] <= c["mult"] <= IS.MULT_RANGE[1] and IS.ONSET_RANGE[0] <= c["onset_frac"] <= IS.ONSET_RANGE[1]
        assert c["parent"] == "r1c0"
        P.validate(IS.realize(c, pub, internal, role="ce:r2").protocol)
    cap = S.FamilySampler(pub, rng, seed_fn, targets=pub["targets_public"]).cap
    ev = IS._scale_events([{"kind": "kick", "t": 0.1, "delta": {"0": 1.0}}], 1e9, cap)[0]
    assert abs(ev["delta"]["0"]) <= float(cap["kick"]["max"]) + 1e-12                          # clipped to the capability


def test_hidden_seed_stream_needs_the_lock(monkeypatch, tmp_path):
    monkeypatch.setattr(S, "METHOD_LOCK", tmp_path / "METHOD_LOCK.json")
    with pytest.raises(PermissionError):
        IS.seed_function(True, "x")
    fn = IS.seed_function(False, "x")
    assert 0 <= fn() < S.HIDDEN_SEED_BASE


def test_robustness_grid_levels_and_untold_jitter():
    sid, pub, internal = _toy()
    specs, counts = IS.robustness_specs(pub, internal, IS.seed_function(False, "rb", sid), items_per_level=2)
    roles = {sp.role for sp in specs}
    assert "robust:nominal@0" in roles and "robust:obs_noise@0.2" in roles and "robust:timing_jitter@8" in roles
    for sp in specs:
        P.validate(sp.protocol)
        assert sp.twin
        cond = sp.role.split(":", 1)[1].split("@")[0]
        if cond in ("amplitude_jitter", "timing_jitter"):
            assert sp.meta.get("model_events") and sp.meta["model_events"] != sp.protocol["events"]
        else:
            assert "model_events" not in sp.meta
    assert sum(counts["levels"].values()) == len(specs)
    job = IS.build_job(sid, "synthetic", "pl_rb_t_grid", pub, internal, specs)
    assert job["parts"][0]["dest"] == "eval" and job["dirs"]["eval"].startswith("/evalvol/") and job["publish_store"].startswith("/evalvol")


# ================================================================================================================ iso "call" roles (local)
def _toy_method():
    from test_isolation_local import TOY_METHOD
    return TOY_METHOD


@pytest.fixture(scope="module")
def local_room(tmp_path_factory):
    from test_isolation_memo import MEMO_METHOD
    work = tmp_path_factory.mktemp("p4post_room")
    mdir = work / "methods"
    mdir.mkdir()
    (mdir / "__init__.py").write_text("", encoding="utf-8")
    (mdir / "toy_method.py").write_text(_toy_method(), encoding="utf-8")
    (mdir / "memo_method.py").write_text(MEMO_METHOD, encoding="utf-8")
    (mdir / "passive_probe.py").write_text(PASSIVE_PROBE, encoding="utf-8")
    I.build_pubdir(work / "pub")
    return I.LocalUnsafeTransport(pubdir=work / "pub", method_dir=mdir)


PASSIVE_PROBE = textwrap.dedent("""
    import numpy as np
    from brainir_causal.api import CausalStateMethod, CausalStateModel, register

    class Seen(CausalStateModel):
        def __init__(self, n_events, n_twins, n):
            self.k = {"s": 1}; self.stats = (n_events, n_twins, n)
        def encode(self, sid, x, u, dt): return np.zeros(1)
        def rollout(self, sid, z0, u, events, dt): return {"z": np.zeros((len(u), 1)), "y": np.zeros((len(u), 1))}
        def readout(self, sid, z, u): return np.zeros((np.atleast_2d(z).shape[0], 1))
        def info(self): return {"k": dict(self.k), "seen": list(self.stats), "ablated": []}

    @register
    class PassiveProbe(CausalStateMethod):
        name = "passive_probe"
        def fit(self, data, *, systems, config=None, seed=0):
            ev = sum(1 for r in data if r.protocol.get("events"))
            tw = sum(1 for r in data if (r.meta or {}).get("twin_of"))
            return Seen(ev, tw, len(data))
""")


def _toy_inputs():
    from test_calibrate_toyinputs import toy_inputs
    from test_isolation_local import _Pub
    inp = toy_inputs(seed=0, n_test_kick=6, n_test_pulse=3, n_pool_src=4)

    class _Held:
        rows = []
    inputs = {"system": inp["sysc"], "items": inp["items"], "pool": inp["pool"], "samples": [], "public": _Pub(inp["train"]),
              "record": inp["pub"], "heldout": _Held()}
    return inputs


def _blob(tr, method):
    return I.fit_records(tr, method=method, records=[], systems={"toy": {}}, config={})["model"]


def test_predict_detail_rows_probe_and_closure(local_room, monkeypatch):
    inputs = _toy_inputs()
    monkeypatch.setattr(J, "_inputs", lambda job: (inputs, {"kind": "synthetic"}, None, None))
    out = J.predict_detail({"sid": "toy", "n_boot": 100, "n_probe": 3, "closure": True, "threads": 1}, local_room, _blob(local_room, "toy_method"))
    n_int = sum(1 for it in inputs["items"] if not it.is_passive)
    assert out["n_items"] == n_int and len(out["items"]) == out["n_scored"] > 0
    row = out["items"][0]
    for k in ("ee_i", "es", "dclass", "abstain", "validity_in_domain", "validity_score", "has_z_int", "pred_sd", "rmse"):
        assert k in row
    assert row["validity_in_domain"] is True and row["has_z_int"] is True
    pr = out["api_probe"]
    assert pr["n"] == 3 and pr["shape_ok_y"] == 3 and pr["effect_consistent"] == 3 and pr["shape_ok_z"] == 3
    assert "EE_medium" in out["effects"] and "_units" in out["effects"] and out["closure"] is not None
    assert out["isolation"]["phases"]["A"]["n_calls"] > 0 and "C" in out["isolation"]["phases"]


@pytest.mark.slow
def test_memo_probe_detects_a_memorising_model(local_room, monkeypatch):
    inputs = _toy_inputs()
    monkeypatch.setattr(J, "_inputs", lambda job: (inputs, {"kind": "synthetic"}, None, None))
    monkeypatch.setattr(I, "kill_uids", lambda *a, **k: 0)                  # no uid workers on the development machine
    clean = J.memo_probe({"sid": "toy", "n_items": 1, "n_decoys": 1, "threads": 1}, local_room, _blob(local_room, "toy_method"))
    assert clean["a_all_equal"] and clean["b_all_equal"] and not clean["errors"]
    memo = J.memo_probe({"sid": "toy", "n_items": 1, "n_decoys": 1, "threads": 1}, local_room, _blob(local_room, "memo_method"))
    assert memo["a_all_equal"] is False                                     # it read the continuation it had seen


def test_fit_passive_hands_the_worker_passive_records_only(local_room, monkeypatch):
    from brainir_causal import runner as RN
    from brainir_causal.data import Trajectory

    def tr(key, events, twin_of=None):
        return Trajectory(key=key, system_id="s", split="twin" if twin_of else "train", family="kick.1" if events else "obs.nominal",
                          protocol={"events": events, "dt": 0.01}, t=np.zeros(3), x=np.zeros((3, 2)), u=np.zeros((3, 1)),
                          y=np.zeros((3, 1)), meta={"twin_of": twin_of} if twin_of else {})
    recs = [tr("p0", []), tr("p1", []), tr("p2", [])]
    for i in range(4):
        recs += [tr(f"i{i}", [{"kind": "kick", "t": 0.01, "delta": {"0": 1.0}}]), tr(f"t{i}", [], twin_of=f"i{i}")]
    monkeypatch.setattr(RN, "load_records", lambda d, s, sp: (list(recs), {"s": {"system_id": "s"}}))
    out = J.fit_passive({"method": "passive_probe", "systems": ["s"], "data": ["x"], "seed": 0, "config": {"ablate": ["interventional_training"]},
                         "threads": 1}, local_room)
    assert out["side"]["info"]["seen"] == [0, 0, 3]                          # no event record, no twin reached the method
    pv = out["side"]["passive_view"]
    assert pv["n_all"] == 11 and pv["n_kept"] == 3 and pv["n_dropped_events_or_twins"] == 8 and pv["n_kept_with_events"] == 0


def test_iso_call_targets_resolve_to_the_forwarders(monkeypatch):
    monkeypatch.setattr(I, "ISO_SCRIPT_DIRS", (str(ROOT / "scripts" / "p4"),))
    for role in ("fit_c", "fit_passive", "eval_c", "predict_detail", "encodings", "readin_probe", "memo_probe", "lift_jitter"):
        fn = I.resolve_iso_target(f"{C.ISO_TARGET}:{role}")
        assert callable(fn)
    p = C.iso_call_payload("predict_detail", {"sid": "x"}, "k", model=b"m")
    assert p["role"] == "call" and p["target"] == "p4post_iso:predict_detail" and p["models"] == {"model": b"m"}


# ================================================================================================================ execution layer
class FakeVolume:
    def __init__(self):
        self.files = {}

    def listdir(self, path):
        class E:
            def __init__(self, p):
                self.path = p
        return [E(k.lstrip("/")) for k in self.files if k.startswith(path)]

    def batch_upload(self, force=False):
        vol = self

        class B:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def put_file(self, fh, path):
                vol.files[path] = fh.read()
        return B()

    def read_file_into_fileobj(self, path, fh):
        fh.write(self.files[path])


BIG = b"B" * 1_600_000                                                       # above the inline limit


class FakeBackend:
    """The Backend surface the execution layer uses (run_iso_packed / run with on_result, the fit volume)."""

    def __init__(self):
        self.calls = []
        self.vols = {"fit": FakeVolume()}
        self.costs, self.verbose, self.refusals = [], False, {}

    def _answer(self, p, packed: bool):
        import hashlib
        job = p.get("job") or {}
        tgt = p.get("target", "")
        if p.get("role") == "describe":
            return {"describe": {"device": "cpu"}}
        if tgt.endswith(":fit_c"):
            if job.get("method") == "big":
                sha = hashlib.sha256(BIG).hexdigest()
                if job.get("model_dir"):
                    assert not packed and p.get("commit") == ["fit"]           # only an UNPACKED job may write (and commit) the volume
                    self.vols["fit"].files[f"/p4post/models/{sha}.bin"] = BIG
                    return {"result": {"model_ref": f"/fitvol/p4post/models/{sha}.bin", "sha256": sha, "n_bytes": len(BIG),
                                       "side": {"info": {"k": {"s": 9}}}}}
                assert packed and not p.get("commit")
                return {"result": {"too_large": len(BIG), "sha256": sha, "side": {}}}
            if job.get("passive"):
                return {"result": {"model": b"PASSIVE", "side": {"passive_view": {"n_kept_with_events": 0}}}}
            return {"result": {"model": b"MODEL", "side": {"info": {"k": {"s": 2}}}}}
        if tgt.endswith(":eval_c"):
            import p4post_iso
            if job.get("model_path"):
                assert "models" not in p and job.get("model_sha256")         # a large model travels by the fit volume
            return {"result": p4post_iso.pack_output({"sid": job["sid"], "result": {"items": {}}})}
        return {"result": {"sid": job["sid"], "items": []}}

    def run_iso_packed(self, payloads, cls, *, expected_s=None, keys=None, done_dir=None, label="", on_result=None):
        assert keys is not None and len(set(keys)) == len(keys)
        self.calls.append((cls, [dict(p) for p in payloads], list(expected_s or [])))
        out = []
        for p in payloads:
            out.append(self._answer(p, True))
            if on_result is not None:                                         # as Backend.run: each final result as it arrives
                on_result(len(out) - 1, out[-1])
        return out

    def run(self, payloads, cls, label="", on_result=None):
        self.calls.append((cls, [dict(p) for p in payloads], []))
        out = []
        for p in payloads:
            out.append(self._answer(p, False))
            if on_result is not None:
                on_result(len(out) - 1, out[-1])
        return out


def _sysd(sid, kind="synthetic"):
    return C.system_paths(sid, kind, tier="dev") if kind == "synthetic" else C.system_paths(sid, kind, real_level="public")


def test_run_fits_and_evals_with_a_fake_backend(tmp_path):
    be = FakeBackend()
    specs = [{"variant": "full", "method": "m", "sid": "syn-a", "sysd": _sysd("syn-a"), "seed": 0, "config": {}},
             {"variant": "abl_interventional_training", "method": "m", "sid": "syn-a", "sysd": _sysd("syn-a"), "seed": 0,
              "config": {"ablate": ["interventional_training"]}, "passive": True},
             {"variant": "full", "method": "m", "sid": "real:A:full", "sysd": _sysd("real:A:full", "real"), "seed": 0, "config": {}}]
    out = X.run_fits(be, specs, key="k", run=tmp_path)
    assert all(v["ok"] for v in out.values())
    cls, pls, exp = be.calls[0]
    assert cls == X.PACK_FIT and exp[0] >= exp[-1]                          # longest expected (the real full network) first
    assert pls[0]["job"]["systems"] == ["real:A:full"]
    assert all(p["role"] == "call" and p["target"] == "p4post_iso:fit_c" and not p.get("commit") for p in pls)
    assert [p["job"]["passive"] for p in pls].count(True) == 1
    assert X.model_path(tmp_path, "abl_interventional_training", "syn-a", 0).read_bytes() == b"PASSIVE"
    assert X.fit_side(tmp_path, "full", "syn-a", 0)["variant"] == "full"
    again = X.run_fits(be, specs, key="k", run=tmp_path)                    # resumable: nothing resubmitted
    assert len(be.calls) == 1 and all(v.get("cached") for v in again.values())
    ev = X.run_evals(be, [{"variant": "full", "sid": "syn-a", "sysd": _sysd("syn-a"), "seed": 0}], key="k", run=tmp_path)
    assert ev[("full", "syn-a", 0)]["ok"] and be.calls[-1][0] == X.PACK_EVAL
    assert X.load_eval(tmp_path, "full", "syn-a", 0)["result"] == {"items": {}}
    assert be.calls[-1][1][0]["models"] == {"model": b"MODEL"}              # the fitted bytes travel to the evaluation unopened
    res = X.run_custom(be, "predict_detail", [{"sid": "syn-a", "sysd": _sysd("syn-a"), "job": {"sid": "syn-a"},
                                               "model_path": X.model_path(tmp_path, "full", "syn-a", 0)}], key="k")
    assert res[0][0] == {"sid": "syn-a", "items": []} and be.calls[-1][1][0]["models"] == {"model": b"MODEL"}


def test_large_models_travel_by_the_fit_volume(tmp_path):
    """A model above the inline limit: the packed fit reports it too large, the UNPACKED fit writes it to the fit volume (committed),
    the driver downloads it (sha256-checked); its evaluation reads it from the volume (staged before the wave), never inline."""
    be = FakeBackend()
    spec = {"variant": "abl_state_bottleneck", "method": "big", "sid": "syn-b", "sysd": _sysd("syn-b"), "seed": 0, "config": {}}
    out = X.run_fits(be, [spec], key="k", run=tmp_path)
    assert out[("abl_state_bottleneck", "syn-b", 0)]["ok"]
    assert [c[0] for c in be.calls] == [X.PACK_FIT, "iso_fit_s"]           # packed first, then the unpacked large-model tier
    assert be.calls[1][1][0]["job"]["model_dir"] == C.MODEL_DIR_CONTAINER
    assert X.model_path(tmp_path, "abl_state_bottleneck", "syn-b", 0).read_bytes() == BIG
    assert X.fit_side(tmp_path, "abl_state_bottleneck", "syn-b", 0)["model_ref"].startswith(C.MODEL_DIR_CONTAINER)
    ev = X.run_evals(be, [{"variant": "abl_state_bottleneck", "sid": "syn-b", "sysd": _sysd("syn-b"), "seed": 0}], key="k", run=tmp_path)
    assert ev[("abl_state_bottleneck", "syn-b", 0)]["ok"]
    p = be.calls[-1][1][0]
    assert "models" not in p and p["job"]["model_path"].startswith(C.MODEL_DIR_CONTAINER)
    n = len(be.calls)
    X.run_fits(be, [spec], key="k", run=tmp_path, refit=True)
    assert [c[0] for c in be.calls[n:]] == ["iso_fit_s"]                    # the too-large mark routes a refit straight to the volume tier


def test_unpacked_fits_are_one_tier(tmp_path):
    """Unpacked fits may write the fit volume, so they carry model_dir from the start: no packed tier, no refit of large models."""
    be = FakeBackend()
    specs = [{"variant": "abl_state_bottleneck", "method": "big", "sid": "syn-b", "sysd": _sysd("syn-b"), "seed": 0, "config": {}},
             {"variant": "full", "method": "m", "sid": "syn-a", "sysd": _sysd("syn-a"), "seed": 0, "config": {}}]
    out = X.run_fits(be, specs, key="k", run=tmp_path, packed=False)
    assert all(v["ok"] for v in out.values())
    assert [c[0] for c in be.calls] == ["iso_fit_s", "iso_fit_s"] and all(len(c[1]) == 1 for c in be.calls)   # one job per map
    assert all(c[1][0]["job"]["model_dir"] == C.MODEL_DIR_CONTAINER and c[1][0]["commit"] == ["fit"] for c in be.calls)
    assert X.model_path(tmp_path, "abl_state_bottleneck", "syn-b", 0).read_bytes() == BIG
    assert X.model_path(tmp_path, "full", "syn-a", 0).read_bytes() == b"MODEL"


def test_input_models_above_the_staging_limit_travel_by_the_fit_volume():
    """Input models above MODEL_INLINE_MAX go by the fit volume, so no payload the drivers build trips the backend's pre-submission
    check, which measures a payload as Modal's serializer ships it (P1, 2026-09-27; it first sized nested bytes by their JSON repr)."""
    be = FakeBackend()
    big, small = b"\x00\x81" * 1_250_000, b"s" * 1000                      # 2.5 MB: above the 2 MiB inline limit, measured correctly
    st = C.ModelStager(be).stage_many([big, small])
    assert "model_path" in st[0] and st[1] == {"inline": small}
    from brainir_causal.p4modal import app as A
    p = C.iso_call_payload("eval_c", {"sid": "x", "model_path": st[0]["model_path"]}, "k", model=st[1]["inline"])
    assert A._payload_bytes(p) < A.MAX_INLINE - A.INLINE_MARGIN
    assert A._payload_bytes(C.iso_call_payload("eval_c", {"sid": "x"}, "k", model=big)) > A.MAX_INLINE - A.INLINE_MARGIN   # why


def test_fit_output_uses_the_volume_only_above_the_inline_limit(tmp_path):
    import p4post_iso
    small = p4post_iso._fit_out({"model": b"abc", "side": {}}, {"model_dir": str(tmp_path)})
    assert small["model"] == b"abc" and not list(tmp_path.iterdir())
    big = p4post_iso._fit_out({"model": BIG, "side": {}}, {"model_dir": str(tmp_path)})
    assert big["model_ref"].endswith(".bin") and Path(big["model_ref"]).read_bytes() == BIG and big["side"]["model_bytes"] == len(BIG)
    assert p4post_iso._fit_out({"model": BIG, "side": {}}, {})["too_large"] == len(BIG)


def test_eager_unpacked_submission_runs_one_job_per_map_and_merges_costs():
    import threading

    class B:
        def __init__(self):
            self.costs, self.verbose, self.refusals, self.p4post_max_containers = [], True, {}, 3
            self.maps, self.active, self.peak, self.lock = [], 0, 0, threading.Lock()

        def run(self, payloads, cls, label="", on_result=None):
            import time as _t
            assert len(payloads) == 1 and on_result is None and self.verbose is False
            with self.lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            _t.sleep(0.02)
            with self.lock:
                self.active -= 1
                self.maps.append(payloads[0]["i"])
                self.costs.append({"label": label, "class": cls, "calls": 1, "container_s": 2.0,
                                   "peak_container_mb_max": 10.0 * payloads[0]["i"], "usd_approx": 0.01})
            return [{"r": payloads[0]["i"] * 2}]
    be = B()
    seen = []
    out = X.run_eager(be, [{"i": i} for i in range(9)], "iso_eval_s", "lab", lambda j, r: seen.append((j, r["r"])))
    assert out == [{"r": 2 * i} for i in range(9)] and sorted(seen) == [(i, 2 * i) for i in range(9)]
    assert sorted(be.maps) == list(range(9)) and be.verbose is True and 1 < be.peak <= 3 + X.EAGER_SLACK
    assert be.costs == [{"label": "lab", "class": "iso_eval_s", "calls": 9, "container_s": 18.0, "peak_container_mb_max": 80.0,
                         "usd_approx": 0.09, "eager": True}]


def test_large_outputs_are_compressed_or_refused():
    import p4post_iso
    small = {"a": 1}
    assert p4post_iso.pack_output(small) is small
    rng = np.random.default_rng(0)
    big = {"result": {"items": {"x": [0.5] * 400_000}, "micro": {"_units": {"dz": [1.0] * 10}}}}   # compressible
    packed = p4post_iso.pack_output(big)
    assert set(packed) >= {"lzma_pickle", "n_bytes"} and len(packed["lzma_pickle"]) < p4post_iso.OUT_MAX
    assert C.decode_output(packed) == big
    noise = {"result": {"micro": {"_units": {"dz": rng.standard_normal(400_000).tolist()}}, "items": {}}}   # incompressible, droppable
    p2 = p4post_iso.pack_output(noise)
    dec = C.decode_output(p2)
    assert "_units" not in dec["result"]["micro"] and dec["_transport"]["dropped"] == ["micro._units"]
    hopeless = {"result": {"items": {"x": rng.standard_normal(600_000).tolist()}}}
    assert "too large" in p4post_iso.pack_output(hopeless)["error"]


def test_unpacked_runs_reuse_stored_results_and_skip_scientific_failures(tmp_path):
    """Resuming on the unpacked classes: a stored custom result (any class) is reused; a persisted scientific fit failure is final,
    an infrastructure failure (e.g. the packed namespace refusal) is resubmitted."""
    be = FakeBackend()
    spec = [{"sid": "syn-a", "sysd": _sysd("syn-a"), "job": {"sid": "syn-a"}, "model_path": None}]
    done = tmp_path / "done"
    r1 = X.run_custom(be, "predict_detail", spec, key="k", packed=False, done_dir=done)
    n = len(be.calls)
    r2 = X.run_custom(be, "predict_detail", spec, key="k", packed=False, done_dir=done)
    assert r1 == r2 and len(be.calls) == n                                  # nothing resubmitted
    base = X._paths(tmp_path, "abl_x", "syn-a", 0, "fits")
    C.dump_json({"error": "RemoteCallError: ValueError: switch declared not applicable"}, base.with_suffix(".fitlog.json"))
    base2 = X._paths(tmp_path, "abl_y", "syn-a", 0, "fits")
    C.dump_json({"error": "RuntimeError: packed isolation needs per-worker user/network/IPC namespaces; refusing to run model workers"},
                base2.with_suffix(".fitlog.json"))
    specs = [{"variant": v, "method": "m", "sid": "syn-a", "sysd": _sysd("syn-a"), "seed": 0, "config": {}} for v in ("abl_x", "abl_y")]
    out = X.run_fits(be, specs, key="k", run=tmp_path, packed=False)
    assert out[("abl_x", "syn-a", 0)] == {"ok": False, "error": "RemoteCallError: ValueError: switch declared not applicable", "cached": True}
    assert out[("abl_y", "syn-a", 0)]["ok"] is True                           # the infrastructure failure was resubmitted
    assert [p["job"]["systems"] for p in be.calls[-1][1]] == [["syn-a"]]


def test_bootstrap_refits_store_side_records(tmp_path):
    be = FakeBackend()
    specs = [{"variant": "full", "method": "m", "sid": "syn-a", "sysd": _sysd("syn-a"), "seed": 0, "config": {}, "bootstrap": b}
             for b in range(2)]
    X.run_fits(be, specs, key="k", run=tmp_path, label="refits")
    assert (tmp_path / "full" / "refits" / "syn-a_b1.json").exists()
    assert be.calls[0][1][0]["job"]["bootstrap"] == 0


# ================================================================================================================ counterexamples / audit
def test_counterexample_definition():
    import counterexamples_p4 as CE
    base = {"es": 2.0, "abstain": False, "validity_in_domain": True, "ee_i": 1.5}
    assert CE.is_counterexample(base)
    assert CE.is_counterexample(dict(base, validity_in_domain=None))          # no validity reported: the model claims everything
    for over in ({"es": 0.5}, {"abstain": True}, {"validity_in_domain": False}, {"ee_i": 0.9}):
        assert not CE.is_counterexample(dict(base, **over))
    assert CE.fitness(dict(base, abstain=True)) == 0.5 and CE.fitness(base) == 1.5 and CE.fitness(None) == -1.0


def test_code_audit_finds_global_state(tmp_path):
    import self_audit_p4 as SA
    m = tmp_path / "methods" / "dev"
    m.mkdir(parents=True)
    (m / "clean.py").write_text("X = 3\ndef f(a):\n    return a + X\n", encoding="utf-8")
    (m / "dirty.py").write_text(textwrap.dedent("""
        import functools
        CACHE = {}
        SEEN = []
        def f(x):
            global CACHE
            CACHE[x] = 1
            SEEN.append(x)
        @functools.lru_cache(None)
        def g(y):
            return y
    """), encoding="utf-8")
    kinds = sorted({f["kind"] for f in SA._audit_source(tmp_path / "methods")})
    assert kinds == ["global statement", "memoisation (lru_cache)", "module-level container item assigned", "module-level container mutated"]
    assert all(f["file"].endswith("dirty.py") for f in SA._audit_source(tmp_path / "methods"))


def test_self_audit_runs_on_empty_inputs(tmp_path):
    import self_audit_p4 as SA
    out = C.DRY_ROOT / "_pytest_self_audit"
    cfg = {"tier": None, "real_level": None, "method": "m", "dirs": {}, "out_dir": str(out)}
    cp = tmp_path / "cfg.json"
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    try:
        assert SA.main(["run", "--config", str(cp)]) == 0
        rec = json.loads((out / "SELF_AUDIT.json").read_text(encoding="utf-8"))
        md = (out / "SELF_AUDIT.md").read_text(encoding="utf-8")
    finally:
        import shutil
        shutil.rmtree(out, ignore_errors=True)
    assert rec["dry_run"] is True and "**DRY RUN**" in md
    assert sorted(rec["checks"], key=lambda q: int(q[1:])) == [f"Q{i}" for i in range(1, 22)]
    assert all(r["status"] != "PASS" for r in rec["checks"].values())         # nothing passes without evidence
