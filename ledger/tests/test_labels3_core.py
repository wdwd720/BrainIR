"""Exam 2 label core (PREREG v3 U5, V2, T3, T4, T8, S5.4) on hand-made records with known answers. LABEL SIDE: no prediction."""

import pandas as pd
import pytest

from brainir_ledger.labels_h1 import core as C

UNITS = ["01A", "09A", "09B", "12A", "20A.22A", "20B.21B.22B", "21A", "24B.25B", "17X"]


def rec(**kw):
    r = {"record_id": "S1-0001", "session": "S1", "doi": "10.1/x", "hemilineage_as_named": "9A", "hemilineages_listed": "09A",
         "driver": "R1-GAL4", "record_type": "whole_two_sided", "preparation": "decapitated", "preparation_detail": "",
         "effector": "UAS-dTrpA1, 30 C", "penetrance": "", "coverage_notes": "", "locator": "Fig 2", "quote": "legs flex",
         "other_observation": "", "saw_model_prediction": False, "notes": ""}
    r.update({d: "not_assessed" for d in C.D15})
    r.update(kw)
    return r


def test_validate():
    assert C.validate(rec()) == []
    bad = rec(d3="maybe", record_type="whole", quote=" ".join(["w"] * 26))
    bad.pop("notes")
    msgs = " ".join(C.validate(bad))
    assert "d3" in msgs and "record_type" in msgs and "25 words" in msgs and "missing" in msgs


def test_d7p_rule():
    assert C.d7p({"d7": "no", "d8": "yes"}) == "yes" and C.d7p({"d7": "no", "d8": "no"}) == "no"
    assert C.d7p({"d7": "unclear", "d8": "no"}) == "unclear" and C.d7p({"d7": "no", "d8": "not_assessed"}) == "not_assessed"


@pytest.mark.parametrize("listed,named,unit", [("09A", "", "09A"), ("", "hemilineage 9A", "09A"), ("", "HL9a", "09A"),
                                               ("", "lineage 9 A", "09A"), ("20A; 22A", "", "20A.22A"), ("", "20A/22A", "20A.22A"),
                                               ("21B", "", "20B.21B.22B"), ("", "21A", "21A"), ("", "17X", "17X"),
                                               ("", "17A", None), ("09A; 09B", "", None), ("", "lineage 9", None), ("", "5A", None)])
def test_unit_mapping(listed, named, unit):
    u, how = C.unit_of({"hemilineages_listed": listed, "hemilineage_as_named": named}, UNITS)
    assert u == unit, how


def test_pairing_and_disputes():
    a = [rec(record_id="A-0001", d2="yes"), rec(record_id="A-0002", hemilineage_as_named="12A", hemilineages_listed="12A", driver="X"),
         rec(record_id="A-0003", hemilineage_as_named="21A", hemilineages_listed="21A")]
    b = [rec(record_id="B-0001", d2="no", driver="r1 gal4", effector="dTrpA1 at 31 C"),
         rec(record_id="B-0002", hemilineage_as_named="12A", hemilineages_listed="12A", driver="Y"),
         rec(record_id="B-0003", hemilineage_as_named="01A", hemilineages_listed="01A")]
    pairs, ua, ub = C.pair_readings(a, b, UNITS)
    ids = {(x["record_id"], y["record_id"]) for x, y in pairs}
    assert ids == {("A-0001", "B-0001"), ("A-0002", "B-0002")}  # driver match; then the single leftover pair in a key
    assert [r["record_id"] for r in ua] == ["A-0003"] and [r["record_id"] for r in ub] == ["B-0003"]
    assert C.disputed_fields(a[0], b[0]) == ["d2"]
    f = C.final_from_pair(a[0], b[0], {"d2": "yes"})
    assert f["d2"] == "yes" and f["paired_with"] == "B-0001"
    with pytest.raises(ValueError):
        C.final_from_pair(a[0], b[0], {})
    assert C.effector_class("CsChrimson, 617 nm light") == "optogenetic" and C.effector_class("UAS-TrpA1 heat") == "thermogenetic"


def _final(rows):
    df = pd.DataFrame(rows)
    df["d7p"] = [C.d7p(r) for r in rows]
    df["eligible"] = df["eligible"].fillna(True).astype(bool) if "eligible" in df else True
    return df


def test_consensus_rules():
    rows = [
        # unit 09A: Harris decapitated yes on d2; Soffers intact no on d2 -> decapitated precedence -> yes (no conflict)
        dict(rec(doi="harris", unit="09A", d2="yes", preparation="decapitated")),
        dict(rec(doi="soffers", unit="09A", d2="no", preparation="intact")),
        # unit 12A: both decapitated, disagree on d3 -> conflicting; agree on d4 -> yes
        dict(rec(doi="harris", unit="12A", d3="yes", d4="yes")),
        dict(rec(doi="soffers", unit="12A", d3="no", d4="yes")),
        # unit 21A: one source, two drivers disagree on d15 -> source conflicting -> conflicting
        dict(rec(doi="soffers", unit="21A", d15="yes")),
        dict(rec(doi="soffers", unit="21A", d15="no", driver="other")),
        # unit 01A: only intact records -> used; unclear stays unclear
        dict(rec(doi="soffers", unit="01A", d2="unclear", preparation="intact")),
        # ineligible (sighting) and clonal records never enter the primary consensus
        dict(rec(doi="harris", unit="09B", d2="yes"), eligible=False),
        dict(rec(doi="harris", unit="17X", d2="yes", record_type="clonal")),
    ]
    cons, per = C.consensus(_final(rows), UNITS)
    assert cons.loc["09A", "d2"] == "yes" and cons.loc["12A", "d3"] == "conflicting" and cons.loc["12A", "d4"] == "yes"
    assert cons.loc["21A", "d15"] == "conflicting" and cons.loc["01A", "d2"] == "unclear"
    assert "09B" not in cons.index and "17X" not in cons.index
    assert per["soffers"].loc["09A", "d2"] == "no" and per["harris"].loc["09A", "d2"] == "yes"
    sec, _ = C.consensus(_final(rows), UNITS, record_types=("clonal", "one_sided", "partial_or_mixed"))
    assert list(sec.index) == ["17X"] and sec.loc["17X", "d2"] == "yes"
    with pytest.raises(ValueError):
        C.consensus(_final([dict(rec(unit="99Z"))]), UNITS)


def test_ge3_and_kappa():
    cons = pd.DataFrame({d: ["yes", "no", "not_assessed"] for d in C.PRIMARY}, index=["a", "b", "c"])
    cons.loc["b", C.PRIMARY[3:]] = "unclear"
    assert C.n_units_ge3(cons) == 2
    k = C.cohen_kappa(["yes", "yes", "no", "no", "unclear"], ["yes", "no", "no", "no", "yes"])
    assert k["n"] == 4 and k["agreement"] == 0.75 and k["kappa"] == pytest.approx(0.5)
    assert C.cohen_kappa(["unclear"], ["yes"])["kappa"] is None
    x = rec(d1="yes", d2="yes", d7="yes")
    y = rec(d1="yes", d2="no", d8="yes")
    rk = C.readings_kappa([(x, y)])
    assert rk["n"] == 3  # d1 (yes/yes), d2 (yes/no), d7p (yes/yes)


def test_verification():
    rows = [dict(rec(record_id=f"S1-{i:04d}", unit="09A", d2="yes", d3="no")) for i in range(1, 41)]
    final = _final(rows)
    s = C.verification_sample(final)
    assert len(s) == 30 and s == C.verification_sample(final)
    v = {rid: {"d2": "yes", "d3": "no"} for rid in s}
    v[s[0]] = {"d2": "no", "d3": "cannot_verify"}
    e = C.verification_error(final, v)
    assert e["cells_checked"] == 60 and e["cells_in_error"] == 2 and e["error_rate"] == pytest.approx(2 / 60)
