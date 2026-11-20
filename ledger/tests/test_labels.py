from brainir_ledger.labels import aggregate as AGG
from brainir_ledger.labels import schema as SC
from brainir_ledger.labels.agreement import agreement


def V(record, **kw):
    """an eligible (quote-verified) record"""
    return record(quote_verified=True, **kw)


def test_valid_record_passes(record):
    assert SC.validate_record(record()) == []
    assert SC.validate_record(record(expression="unknown", exp_id="pass1-atlas:r1", frequency_note="9-11 Hz")) == []


def test_vocabulary_and_field_errors(record):
    assert any("front_leg_rhythm" in e for e in SC.validate_record(record(front_leg_rhythm="maybe")))
    assert any("missing field quote" in e for e in SC.validate_record({k: v for k, v in record().items() if k != "quote"}))
    assert any("quote has" in e for e in SC.validate_record(record(quote=" ".join(["w"] * 26))))
    assert any("headless_surface" in e for e in SC.validate_record(record(preparation="headless")))
    assert SC.validate_record(record(preparation="headless", headless_surface="ball")) == []
    assert any("other_cell_types" in e for e in SC.validate_record(record(line_specificity="multi_dn")))
    assert any("unknown fields" in e for e in SC.validate_record(record(score=0.7)))
    assert any("not in the type list" in e for e in SC.validate_record(record(manc_type="DNzz99"), {"DNa01"}))
    assert SC.validate_record(record(manc_type="UNMAPPED"), {"DNa01"}) == []
    assert any("saw_simulation_score" in e for e in SC.validate_record(record(saw_simulation_score="no")))
    assert any("frequency_hz" in e for e in SC.validate_record(record(frequency_hz="10-12")))
    assert any("n_flies" in e for e in SC.validate_record(record(n_flies=True)))


def test_validator_does_not_echo_label_values(record):
    errs = SC.validate_record(record(front_leg_rhythm="definitely_yes_walking"))
    assert errs and not any("definitely_yes_walking" in e for e in errs)


def test_schema_export_matches_validator():
    js = SC.json_schema()
    assert set(js["required"]) == set(SC.REQUIRED)
    assert js["properties"]["front_leg_rhythm"]["enum"] == list(SC.LEG_VALUES)


def test_consensus_headless_outranks_intact(record):
    recs = [V(record, record_id="a", preparation="intact_free", front_leg_rhythm="no"),
            V(record, record_id="b", preparation="headless", headless_surface="ball", front_leg_rhythm="yes")]
    assert AGG.type_labels(recs)["front"].iloc[0] == "yes"


def test_consensus_low_confidence_is_dropped_before_tiering(record):
    # reviewer case (a): one low-confidence headless yes vs three high-confidence clean intact no -> no
    recs = [V(record, record_id="a", preparation="headless", headless_surface="ball", labeler_confidence="low", access="abstract_only",
              front_leg_rhythm="yes")] + [V(record, record_id=f"n{i}", front_leg_rhythm="no") for i in range(3)]
    assert AGG.type_labels(recs)["front"].iloc[0] == "no"
    assert AGG.type_labels(recs[:1])["front"].iloc[0] == "yes"  # alone, it counts


def test_consensus_multi_dn_dropped_when_other_records_exist(record):
    # reviewer case (b): a headless multi-DN "no" must not beat a clean intact "yes"
    recs = [V(record, record_id="a", preparation="headless", headless_surface="ball", line_specificity="multi_dn",
              other_cell_types=["DNa02"], front_leg_rhythm="no"),
            V(record, record_id="b", front_leg_rhythm="yes")]
    assert AGG.type_labels(recs)["front"].iloc[0] == "yes"


def test_consensus_unclear_is_kept_in_the_tier(record):
    # reviewer case (c): a clean headless high-confidence "unclear" is not discarded in favour of a worse "yes"
    recs = [V(record, record_id="a", preparation="headless", headless_surface="ball", front_leg_rhythm="unclear"),
            V(record, record_id="b", line_specificity="multi_dn", other_cell_types=["DNa02"], labeler_confidence="low", front_leg_rhythm="yes")]
    assert AGG.type_labels(recs)["front"].iloc[0] == "unclear"


def test_consensus_conflict_and_specificity(record):
    recs = [V(record, record_id="a", line_specificity="unknown", front_leg_rhythm="no"),
            V(record, record_id="b", line_specificity="clean", front_leg_rhythm="yes")]
    assert AGG.type_labels(recs)["front"].iloc[0] == "yes"
    recs.append(V(record, record_id="c", line_specificity="clean", front_leg_rhythm="no"))
    assert AGG.type_labels(recs)["front"].iloc[0] == "conflicting"


def test_exclusions(record):
    tl = AGG.type_labels([V(record, record_id="a", saw_simulation_score=True)], type_list=["DNa01"])
    assert tl["front"].iloc[0] == "not_assessed" and tl["n_records"].iloc[0] == 0
    assert AGG.type_labels([record(record_id="a")], type_list=["DNa01"])["n_records"].iloc[0] == 0  # quote not verified
    assert AGG.type_labels([V(record, record_id="a", mapping_confidence="low")], type_list=["DNa01"])["n_records"].iloc[0] == 0


def test_stop_call_uses_only_records_with_stop_information(record):
    recs = [V(record, record_id="a", front_leg_rhythm="no", effect_on_walking="stops", behaviour_category="halting")]
    assert AGG.type_labels(recs)["stop_call"].iloc[0] == "stops"
    # a headless record without stop information does not hide intact "stops" records (reviewer minor)
    recs.append(V(record, record_id="b", preparation="headless", headless_surface="ball", front_leg_rhythm="not_assessed",
                  behaviour_category="other", effect_on_walking="not_assessed"))
    assert AGG.type_labels(recs)["stop_call"].iloc[0] == "stops"
    assert AGG.type_labels([V(record, record_id="c", front_leg_rhythm="yes", effect_on_walking="none")])["stop_call"].iloc[0] == "no_stop"
    assert AGG.type_labels([V(record, record_id="d", effect_on_walking="slows")])["walking_effect"].iloc[0] == "slows"


def _p1(record, n):
    return [record(record_id=f"r{i}", exp_id=f"pass1-atlas:r{i}", manc_type=f"DNa0{i + 1}", name_in_paper="line X") for i in range(n)]


def test_merge_by_exp_id_keeps_records_with_identical_content_keys(record):
    # a two-type line: same doi/locator/line/name, two MANC types (reviewer blocker 1)
    p1 = _p1(record, 2)
    p2 = [dict(r, pass_id="pass2") for r in p1]
    final, log = AGG.merge_passes(p1, p2, [], {r["exp_id"]: True for r in p1})
    assert sorted(r["manc_type"] for r in final) == ["DNa01", "DNa02"] and len(log["agreed"]) == 2
    ag = agreement(p1, p2)
    assert ag["fields"]["front_leg_rhythm"]["raw_agreement"] == 1.0 and ag["n_matched"] == 2


def test_merge_outcomes_and_adjudication_groups(record):
    p1 = _p1(record, 5)
    p2 = [dict(p1[0], pass_id="pass2"),
          dict(p1[1], pass_id="pass2", front_leg_rhythm="no", labeler_confidence="medium"),
          dict(p1[2], pass_id="pass2"),
          dict(p1[3], pass_id="pass2", manc_type="DNa09", mapping_confidence="medium", mapping_basis="via line")]
    adj = [dict(p1[1], pass_id="adjudication", front_leg_rhythm="no", labeler_confidence="low"),
           dict(p1[3], pass_id="adjudication", manc_type="DNa09", mapping_confidence="medium", mapping_basis="adjudicated", saw_simulation_score=True)]
    qc = {p1[0]["exp_id"]: True, p1[1]["exp_id"]: True, p1[2]["exp_id"]: False, p1[3]["exp_id"]: True}
    final, log = AGG.merge_passes(p1, p2, adj, qc, not_found=[p1[4]["exp_id"]])
    by = {r["exp_id"]: r for r in final}
    assert set(by) == {p1[0]["exp_id"], p1[1]["exp_id"], p1[3]["exp_id"]}
    assert by[p1[1]["exp_id"]]["front_leg_rhythm"] == "no" and by[p1[1]["exp_id"]]["labeler_confidence"] == "low"  # lowest reader
    m = by[p1[3]["exp_id"]]
    assert m["manc_type"] == "DNa09" and m["mapping_basis"] == "adjudicated" and m["saw_simulation_score"] is True
    assert log["quote_unverified"] == [p1[2]["exp_id"]] and log["not_found_by_pass2"] == [p1[4]["exp_id"]]
    assert all(r["quote_verified"] is True for r in final)


def test_merge_revalidates_and_requires_adjudication(record):
    p1 = _p1(record, 1)
    p2 = [dict(p1[0], pass_id="pass2", line_specificity="multi_dn", other_cell_types=["DNa05"])]
    final, log = AGG.merge_passes(p1, p2, [], {p1[0]["exp_id"]: True})
    assert final == [] and log["disagreed_unadjudicated"] == [p1[0]["exp_id"]]
    # an adjudicated value that breaks a cross-field rule is dropped, not kept invalid
    adj = [{**p1[0], "line_specificity": "multi_dn", "other_cell_types": []}]
    final, log = AGG.merge_passes(p1, p2, adj, {p1[0]["exp_id"]: True})
    assert final == [] and len(log["invalid_after_merge"]) == 1


def test_dedupe_pass1_keeps_the_earliest_family(record):
    a = record(record_id="x1", exp_id="pass1-grooming:x1")
    b = record(record_id="y7", exp_id="pass1-atlas:y7")
    c = record(record_id="y8", exp_id="pass1-atlas:y8", preparation="headless", headless_surface="ball")
    kept, dropped = AGG.dedupe_pass1([a, b, c])
    assert {r["exp_id"] for r in kept} == {"pass1-atlas:y7", "pass1-atlas:y8"}
    assert dropped == [{"exp_id": "pass1-grooming:x1", "duplicate_of": "pass1-atlas:y7"}]


def test_kit_schema_file_equals_code():
    import json

    from brainir_ledger import KIT

    assert json.loads((KIT / "record_schema.json").read_text(encoding="utf-8")) == SC.json_schema()
