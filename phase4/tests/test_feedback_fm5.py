"""The developer-facing feedback hardening of review F, F-M5 (brainir_causal.feedback): coarsened rates / medians, boolean failures,
the fixed-system-set fingerprint, and the release caps (validation tier only, <= 4 rounds, <= 12 candidates)."""

from __future__ import annotations

import pytest

from brainir_causal import feedback as FB


def _sys(cat, passes, kind="synthetic", ee=0.3):
    return {"kind": kind, "verdict": {}, "selection": {**{c: (c in passes) for c in FB.CRITERIA}, "category": cat},
            "result": {"items": {"effects": {"EE_medium": {"point": ee}}, "observational": {"obs_nmse_medium": {"point": 0.4}}},
                       "mediation": {"SMS": {"point": 0.12}}, "closure": {"ICG_y": {"point": 0.08}}, "micro": {"MEV": {"point": 0.2}},
                       "lift": {"success_rate": 0.5}}}


def _report(round_id="r1", n=4, methods=("m1", "m2")):
    results = {}
    for i, m in enumerate(methods):
        ps = {f"syn:{j}": _sys("partially supported" if j % 2 else "unsupported", ("A", "D") if i == 0 else ("A",)) for j in range(n)}
        results[m] = {"per_system": ps, "n_fit_failures": (1 if i else 0), "n_eval_failures": 0}
    return {"round": round_id, "suite": "val", "order": list(methods),
            "eligibility": {m: {"eligible": m == "m1"} for m in methods}, "results": results}


def test_aggregate_coarsens_and_uses_booleans():
    agg = FB.aggregate(_report())
    c = agg["candidates"]["m1"]["synthetic"]
    assert c["n_systems"] == 4
    for r in c["pass_rates"].values():
        assert abs(r / FB.RATE_STEP - round(r / FB.RATE_STEP)) < 1e-9      # rates are on the 0.05 grid
    assert agg["candidates"]["m2"]["any_fit_failure"] is True and agg["candidates"]["m1"]["any_fit_failure"] is False
    assert isinstance(agg["system_ids_hash"], str) and len(agg["system_ids_hash"]) == 16


def test_seed_averaged_float_pass_values_count():
    rep = _report()
    for v in rep["results"]["m1"]["per_system"].values():
        v["selection"]["A"] = 0.5                                          # a seed-averaged fraction, not True
    agg = FB.aggregate(rep)
    assert agg["candidates"]["m1"]["synthetic"]["pass_rates"]["A"] == pytest.approx(0.5, abs=FB.RATE_STEP)


def test_small_cells_are_suppressed():
    agg = FB.aggregate(_report(n=2))
    assert agg["candidates"]["m1"]["synthetic"].get("suppressed") is True


def test_candidate_cap():
    many = tuple(f"m{i}" for i in range(FB.MAX_CANDIDATES + 3))
    agg = FB.aggregate(_report(methods=many))
    assert len(agg["candidates"]) == FB.MAX_CANDIDATES and agg["candidates_suppressed"] == 3


def test_check_release_rules():
    a1, a2 = FB.aggregate(_report("r1")), FB.aggregate(_report("r2"))
    FB.check_release([a1, a2], tiers={"val"})                              # ok
    with pytest.raises(ValueError):
        FB.check_release([a1], tiers={"conf"})                            # non-validation tier
    with pytest.raises(ValueError):
        FB.check_release([a1] * (FB.MAX_ROUNDS + 1), tiers={"val"})       # too many rounds
    a_changed = FB.aggregate(_report("r3", n=5))                          # a different system set -> different fingerprint
    assert a_changed["system_ids_hash"] != a1["system_ids_hash"]
    with pytest.raises(ValueError):
        FB.check_release([a1, a_changed], tiers={"val"})
    FB.check_release([a1, a_changed], tiers={"val"}, allow_changed_systems=True)


def test_write_markdown_round_trips(tmp_path):
    FB.write_markdown([FB.aggregate(_report())], tmp_path / "fb.md")
    txt = (tmp_path / "fb.md").read_text(encoding="utf-8")
    assert "Tournament feedback" in txt and "synthetic validation systems" in txt


# ------------------------------------------------------------------------------------------------ across calls (review F round 2, M5)
def test_a_round_without_a_fingerprint_is_refused():
    a1 = FB.aggregate(_report("r1"))
    a_none = dict(FB.aggregate(_report("r2")), system_ids_hash=None)
    with pytest.raises(ValueError, match="fingerprint"):
        FB.check_release([a1, a_none], tiers={"val"})


def test_release_caps_rounds_and_fixes_the_system_set_across_calls(tmp_path):
    log = tmp_path / "outside" / "FEEDBACK_RELEASES.json"
    out = tmp_path / "fb.md"
    rounds = [FB.aggregate(_report(f"r{i}")) for i in range(1, 6)]
    FB.release(rounds[:2], out, tiers={"val"}, log_path=log)
    FB.release(rounds[:3], out, tiers={"val"}, log_path=log)                # re-releasing r1-r2 with r3: 3 distinct rounds
    FB.release([rounds[3]], out, tiers={"val"}, log_path=log)               # r4 alone in a later call: 4 rounds in total
    with pytest.raises(ValueError, match="capped"):
        FB.release([rounds[4]], out, tiers={"val"}, log_path=log)           # r5 in yet another call: refused (was released before)
    other = FB.aggregate(_report("r1", n=5))                                # another system set
    log2 = tmp_path / "outside" / "second.json"
    FB.release([rounds[0]], out, tiers={"val"}, log_path=log2)
    with pytest.raises(ValueError, match="system set"):
        FB.release([FB.aggregate(_report("r2", n=5))], out, tiers={"val"}, log_path=log2)
    with pytest.raises(ValueError, match="another system set"):
        FB.release([other], out, tiers={"val"}, log_path=log2)              # the same round id with another fingerprint
    with pytest.raises(ValueError, match="validation tier"):
        FB.release([rounds[0]], out, tiers={"conf"}, log_path=tmp_path / "third.json")
    with pytest.raises(ValueError, match="validation tier"):
        FB.release([rounds[0]], out, tiers=set(), log_path=tmp_path / "third.json")
    rec = FB.load_release_log(log)
    assert [r["round"] for r in rec["rounds"]] == ["r1", "r2", "r3", "r4"] and len(rec["events"]) == 3
    assert all(len(e["file_sha256"]) == 64 for e in rec["events"])


def test_release_log_default_lives_outside_every_room():
    parts = FB.RELEASE_LOG.as_posix().split("/")
    assert parts[-3:] == ["phase4", "tournament", "FEEDBACK_RELEASES.json"] and "research" in parts


def test_a_round_id_is_released_with_one_content_only(tmp_path):
    """Review F round 3, M5: re-releasing a known round id with other candidates (same system set) is refused; an identical
    re-release is allowed (it reveals nothing new)."""
    log = tmp_path / "outside" / "FEEDBACK_RELEASES.json"
    out = tmp_path / "fb.md"
    r1 = FB.aggregate(_report("r1"))
    FB.release([r1], out, tiers={"val"}, log_path=log)
    FB.release([r1], out, tiers={"val"}, log_path=log)                          # identical: allowed
    other = FB.aggregate(_report("r1", methods=("m1", "m3")))                   # same round id and systems, other candidates
    assert other["system_ids_hash"] == r1["system_ids_hash"]
    with pytest.raises(ValueError, match="different content"):
        FB.release([other], out, tiers={"val"}, log_path=log)
