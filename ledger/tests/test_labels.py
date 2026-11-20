from brainir_ledger.labels import aggregate as AGG
from brainir_ledger.labels import schema as SC


def test_valid_record_passes(record):
    assert SC.validate_record(record()) == []


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


def test_schema_export_matches_validator():
    js = SC.json_schema()
    assert set(js["required"]) == set(SC.REQUIRED)
    assert js["properties"]["front_leg_rhythm"]["enum"] == list(SC.LEG_VALUES)


def test_consensus_headless_outranks_intact(record):
    recs = [record(record_id="a", preparation="intact_free", front_leg_rhythm="no"),
            record(record_id="b", preparation="headless", headless_surface="ball", front_leg_rhythm="yes")]
    assert AGG.type_labels(recs)["front"].iloc[0] == "yes"


def test_consensus_clean_outranks_nonspecific_and_conflicts(record):
    recs = [record(record_id="a", line_specificity="multi_dn", other_cell_types=["DNa02"], front_leg_rhythm="no"),
            record(record_id="b", line_specificity="clean", front_leg_rhythm="yes")]
    assert AGG.type_labels(recs)["front"].iloc[0] == "yes"
    recs.append(record(record_id="c", line_specificity="clean", front_leg_rhythm="no"))
    assert AGG.type_labels(recs)["front"].iloc[0] == "conflicting"


def test_low_confidence_dropped_only_when_better_exists(record):
    recs = [record(record_id="a", labeler_confidence="low", front_leg_rhythm="no"),
            record(record_id="b", labeler_confidence="medium", front_leg_rhythm="yes")]
    assert AGG.type_labels(recs)["front"].iloc[0] == "yes"
    assert AGG.type_labels(recs[:1])["front"].iloc[0] == "no"


def test_exclusions_and_unclear(record):
    recs = [record(record_id="a", saw_simulation_score=True, front_leg_rhythm="yes")]
    tl = AGG.type_labels(recs, type_list=["DNa01"])
    assert tl["front"].iloc[0] == "not_assessed" and tl["n_records"].iloc[0] == 0
    recs = [record(record_id="a", mapping_confidence="low", front_leg_rhythm="yes"), record(record_id="b", front_leg_rhythm="unclear")]
    assert AGG.type_labels(recs)["front"].iloc[0] == "unclear"


def test_stop_call(record):
    recs = [record(record_id="a", front_leg_rhythm="no", effect_on_walking="stops", behaviour_category="halting")]
    assert AGG.type_labels(recs)["stop_call"].iloc[0] == "stops"
    recs = [record(record_id="a", front_leg_rhythm="yes", effect_on_walking="none")]
    assert AGG.type_labels(recs)["stop_call"].iloc[0] == "no_stop"


def test_merge_passes(record):
    p1 = [record(record_id="a", manc_type="DNa01", name_in_paper="x1"), record(record_id="b", manc_type="DNa02", name_in_paper="x2"),
          record(record_id="c", manc_type="DNa03", name_in_paper="x3"), record(record_id="d", manc_type="DNa04", name_in_paper="x4")]
    p2 = [dict(p1[0], pass_id="pass2", quote_verified=True),
          dict(p1[1], pass_id="pass2", quote_verified=True, front_leg_rhythm="no"),
          dict(p1[2], pass_id="pass2", quote_verified=False)]
    adj = [dict(p1[1], pass_id="adjudication", front_leg_rhythm="no")]
    final, log = AGG.merge_passes(p1, p2, adj)
    assert [r["manc_type"] for r in final] == ["DNa01", "DNa02"]
    assert final[1]["front_leg_rhythm"] == "no"
    assert len(log["no_pass2"]) == 1 and len(log["quote_unverified"]) == 1 and len(log["adjudicated"]) == 1
    final2, log2 = AGG.merge_passes(p1[:2], p2[:2], [])
    assert len(final2) == 1 and len(log2["disagreed_unadjudicated"]) == 1


def test_experiment_key_normalises(record):
    a = record(doi="10.1/X", source_locator="Fig 1", driver_lines=["SS2", "SS1"])
    b = record(doi="10.1/x", source_locator="fig  1", driver_lines=["ss1", "ss2"])
    assert SC.experiment_key(a) == SC.experiment_key(b)
