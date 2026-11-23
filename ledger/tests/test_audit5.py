"""PREREG v5 Part L tooling: name matching (L3) and the scripted quote check, on hand-made inputs (no reader session)."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import audit5_rooms as A  # noqa: E402


def test_name_patterns():
    assert A.pattern("DNg100").search("activating dng100 (BDN2)") is not None      # names with a digit: case-insensitive
    assert A.pattern("DNg10").search("DNg100") is None                            # whole word only
    assert A.pattern("GF").search("GFP-positive") is None and A.pattern("GF").search("the GF fires") is not None
    assert A.pattern("MDN").search("mdn") is None                                 # names without a digit: case-sensitive
    syn = [{"manc_type": "DNx", "name": "web"}, {"manc_type": "DNx", "name": "BDNx1"}, {"manc_type": "DNy", "name": "zz"}]
    assert A.names_for("DNx", syn) == ["BDNx1", "DNx"]                            # common-word names dropped


def test_quote_status(tmp_path, monkeypatch):
    src = tmp_path / "src1"
    (src / "supp").mkdir(parents=True)
    (src / "text.txt").write_text("Optogenetic activation of BDN2 in head-\nless flies elicited “robust” forward walking.\n", encoding="utf-8")
    (src / "supp" / "table.csv").write_text("line,effect\nSS1,front leg stepping\n", encoding="utf-8")
    monkeypatch.setattr(A, "SOURCES", tmp_path)
    d2s = {"10.1/x": "src1"}
    c: dict = {}
    assert A.quote_status({"doi": "10.1/X", "quote": "activation of BDN2 in headless flies elicited \"robust\" forward walking"}, c, d2s) == "found"
    assert A.quote_status({"doi": "10.1/x", "quote": "front leg stepping"}, c, d2s) == "found"
    assert A.quote_status({"doi": "10.1/x", "quote": "backward walking was seen"}, c, d2s) == "not_found"
    assert A.quote_status({"doi": "10.1/x", "quote": "Fig 2 panel", "notes": "figure: Fig. 2c"}, c, d2s) == "figure"


def test_audited_types_on_synthetic_part_r(tmp_path, monkeypatch):
    """L3 (i)-(iv) code path with synthetic Part R categories (no real Part R result is computed)."""
    import pandas as pd

    import forward_v1 as F1
    import replication_v1 as R

    ex1 = pd.read_csv(A.RESEARCH / "labels_v2" / "type_labels.csv", dtype={"manc_type": str})
    labelled = sorted(ex1.loc[ex1["front"].isin(["yes", "no"]), "manc_type"])[:6]
    fake = pd.DataFrame([{"manc_type": t, "category": c} for t, c in zip(labelled + ["DNg43"], ["replicated", "neither", "stable_non_driver", "neither",
                                                                                                 "single_fly_manc", "neither", "single_fly_malecns"])])
    monkeypatch.setattr(R, "tables", lambda pertype=None: {})
    monkeypatch.setattr(R, "categories", lambda T, x="B1r", confidence=None: fake)
    out = A.audited_types()
    assert len(out["exposed"]) == 18 and set(out["exposed"]) <= set(out["all"])
    assert set(out["part_r_labelled"]) == {labelled[0], labelled[2], labelled[4]}
    assert out["primary_census"] == sorted(F1.primary_set().index) and len(out["primary_census"]) == 39
    assert len(out["random_sample"]) == 15 and set(out["random_sample"]) <= set(out["primary_census"])
    assert "DNg43" in out["part_r_with_kit_line"] and set(out["part_r_with_kit_line"]) <= set(out["all"])


def test_flags_deny_exam1_rooms():
    f = A.flags_for("audit_reader")
    i = f.index("--disallowedTools")
    assert any("ledger_rooms/run2/**" in x and x.startswith("Read(") for x in f[i + 1:i + 4])
    assert "WebFetch" not in f[f.index("--tools") + 1]
    assert "WebFetch" in A.flags_for("audit_reader_web")[A.flags_for("audit_reader_web").index("--tools") + 1]


def test_label_pipeline_end_to_end(tmp_path, monkeypatch):
    """L3-L4 on fabricated sessions: atlas A/B agreement and dispute, reader A/B labels, an adjudicated dispute, the error table."""
    import json

    import pandas as pd

    import labels_audit_v1 as LV

    ex1 = pd.read_csv(A.RESEARCH / "labels_v2" / "type_labels.csv", dtype={"manc_type": str}).set_index("manc_type")
    base = next(r for r in A.exam1_records() if r.get("manc_type") == "DNg100")
    prim = sorted(ex1.index[(ex1["front"].isin(["yes", "no"])) & (~ex1["exposed"].astype(bool))])[:3]
    out = tmp_path / "labels_audit_v1"
    for d in ("sessions", "rooms"):
        (out / d).mkdir(parents=True)
    types = ["DNg100", "DNp04", *prim]
    asg = {"audited": {"exposed": ["DNg100"], "part_r_labelled": [], "primary_census": prim, "random_sample": prim[:2], "part_r_with_kit_line": [],
                       "all": sorted(set(types))}}
    (out / "ASSIGNMENT.json").write_text(json.dumps(asg))
    (out / "TRANSCRIPT_AUDIT.json").write_text(json.dumps({"breaching_sessions": []}))

    def rec(t, prep, front, i, notes="figure: Fig. 1", line=None):
        r = {k: v for k, v in base.items() if k not in ("exp_id", "quote_verified")}
        r.update(manc_type=t, preparation=prep, front_leg_rhythm=front, middle_leg_rhythm=front, hind_leg_rhythm=front, record_id=f"r{i}",
                 notes=notes, labeler_confidence="high", line_specificity="clean", other_cell_types=[], mapping_confidence="high",
                 headless_surface="ball" if prep == "headless" else None, saw_simulation_score=False)
        if line:
            r.update(driver_lines=[line], name_in_paper=line, manc_type="UNMAPPED", mapping_confidence="low")
        return r

    def session(name, recs, reader=None):
        (out / "sessions" / name).mkdir()
        (out / "sessions" / name / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
        (out / "rooms" / f"{name}.json").write_text(json.dumps({"session": name, "reader": reader, "group": "g01"}))

    # readers: DNg100 headless yes (both); prim[0] intact: A yes, B no -> disputed -> adjudicator says yes
    session("a5-g01-A", [rec("DNg100", "headless", "yes", 1), rec(prim[0], "intact_free", "yes", 2)], "A")
    session("a5-g01-B", [rec("DNg100", "headless", "yes", 1), rec(prim[0], "intact_free", "no", 2)], "B")
    # atlas: SS00725 (DNp04) intact: A yes, B yes (agreed); SS00726 (DNp01) intact: A yes, B no (disputed) -> C no
    session("a5-atlas-A", [rec("x", "intact_free", "yes", 1, line="SS00725"), rec("x", "intact_free", "yes", 2, line="SS00726")], "A")
    session("a5-atlas-B", [rec("x", "intact_free", "yes", 1, line="SS00725"), rec("x", "intact_free", "no", 2, line="SS00726")], "B")
    session("a5-atlas-C", [rec("x", "intact_free", "no", 1, line="SS00726")])
    monkeypatch.setattr(LV, "OUT", out)
    monkeypatch.setattr(A, "unread_types", lambda: [])
    sides, dis = LV.atlas_sides()
    assert dis == [("SS00726", "intact")]
    fa, log = LV.final_atlas_records()
    assert log["agreed"] == 1 and log["adjudicated"] == 1
    assert {(r["manc_type"], r["front_leg_rhythm"]) for r in fa} >= {("DNp04", "yes"), ("DNp01", "no")}
    sc0 = LV.scope_of(prim[0], LV.exam1_labels())
    assert (prim[0] in LV.disputed_types()) == (sc0 == "intact")
    session("a5-adj-01", [rec(prim[0], "intact_free", "yes", 9)])
    LV.labels()
    aud = pd.read_csv(out / "audited_type_labels.csv").set_index("manc_type")
    assert aud.loc["DNg100", "front_headless"] == "yes" and aud.loc["DNp04", "front_intact"] == "yes"
    if sc0 == "intact":
        assert aud.loc[prim[0], "front_intact"] == "yes" and bool(aud.loc[prim[0], "disputed"])
    LV.errors()
    er = json.loads((out / "ERROR_RATES.json").read_text())
    assert er["census_39"]["all"]["n"] == 3 and er["sample_15"]["all"]["n"] == 2
    cmp_ = pd.read_csv(out / "comparison_with_exam1.csv").set_index("manc_type")
    assert bool(cmp_.loc["DNg100", "strict_differs"]) == (ex1.loc["DNg100", "front"] != "yes")


def test_atlas_rooms_get_no_type_map(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "ROOMS", tmp_path / "rooms")
    monkeypatch.setattr(A, "verify_kit", lambda: None)
    c = A.cache()
    at = A.atlas_slug(c)
    room = A.build_room({"session": "a5-atlas-T", "kind": "atlas_code", "sources": [at],
                         "inputs": {"atlas_line_ids.csv": str(A.LAB2 / "work" / "atlas" / "atlas_line_ids.csv")}})
    names = {p.name for p in room.iterdir()}
    assert "PROTOCOL.md" in names and "atlas_line_ids.csv" in names
    assert not names & {"type_list.csv", "synonyms.csv", "driver_lines.csv"}
    room2 = A.build_room({"session": "a5-g99-A", "kind": "audit_reader", "sources": [at], "types": ["DNg100"]})
    assert {"type_list.csv", "synonyms.csv", "driver_lines.csv"} <= {p.name for p in room2.iterdir()}


def test_launch_refuses_without_canary(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setattr(A, "OUT", tmp_path)
    monkeypatch.setattr(A.L2R, "SCRATCH_HINT", tmp_path)
    with pytest.raises(SystemExit, match="canary"):
        A.launch({"session": "a5-g01-A", "kind": "audit_reader", "sources": []}, "sandbox")


def test_web_agreed_quote_rule(monkeypatch):
    import labels_audit_v1 as LV

    c = A.cache()
    web = next(s for s, v in c.items() if v["status"] in A.WEB_STATUSES)
    doi = c[web]["doi"]
    base = {"doi": doi, "preparation": "headless", "manc_type": "DNg100", "front_leg_rhythm": "yes", "schema_errors": [], "quote_status": "not_found",
            "exp_id": "x", "driver_lines": [], "line_specificity": "clean"}
    a = dict(base, reader="A", exp_id="a1")
    b = dict(base, reader="B", exp_id="b1")
    b_other = dict(base, reader="B", exp_id="b2", front_leg_rhythm="no")
    got = LV.counted([a], pool=[a, b])
    assert len(got) == 1 and got[0]["quote_status"] == "web_agreed"
    assert LV.counted([a], pool=[a, b_other]) == []
    assert LV.counted([a], pool=[a]) == []


def test_rescore_reads_the_comparison_columns(tmp_path, monkeypatch):
    import json

    import pandas as pd

    import rescore_audit_v1 as RS
    from brainir_ledger.scoring import pipeline as P

    out = tmp_path / "labels_audit_v1"
    out.mkdir()
    pd.DataFrame([{"manc_type": "DNa02", "audited": "no"}, {"manc_type": "DNb05", "audited": "unclear"}]).to_csv(out / "comparison_with_exam1.csv", index=False)
    monkeypatch.setattr(RS, "OUT", out)
    calls = []
    monkeypatch.setattr(P, "primary", lambda pred, tl, locked, n_boot, n_perm: calls.append(tl) or {"auroc": 0.5})
    RS.rescore()
    res = json.loads((out / "RESCORE_exploratory.json").read_text())
    assert len(calls) == 2 and "EXPLORATORY" in res["label"]


def test_unread_types_uses_dispositions(tmp_path, monkeypatch):
    import json

    c = A.cache()
    s1, s2 = sorted(c)[:2]
    out = tmp_path / "labels_audit_v1"
    (out / "sessions" / "a5-g01-A").mkdir(parents=True)
    (out / "sessions" / "a5-g01-B").mkdir(parents=True)
    (out / "sessions" / "a5-g01-A" / "dispositions.csv").write_text(f"doi,disposition,n_records,reason\n{c[s1]['doi']},records,1,\n")
    (out / "sessions" / "a5-g01-B" / "dispositions.csv").write_text(f"doi,disposition,n_records,reason\n{c[s2]['doi']},no_qualifying_experiment,0,\n")
    (out / "ASSIGNMENT.json").write_text(json.dumps({"audited": {"all": ["T1", "T2", "T3"]}, "relevant_sources": {"T1": [s1], "T2": [s1, s2], "T3": [s2, "zz_missing"]}}))
    (out / "TRANSCRIPT_AUDIT.json").write_text(json.dumps({"breaching_sessions": []}))
    monkeypatch.setattr(A, "OUT", out)
    c["zz_missing"] = {"doi": "10.0/none", "status": "full_text", "title": "", "kb": 1}
    monkeypatch.setattr(A, "cache", lambda: c)
    assert A.unread_types() == ["T3"]
    (out / "TRANSCRIPT_AUDIT.json").write_text(json.dumps({"breaching_sessions": ["a5-g01-B"]}))
    assert A.unread_types() == ["T2", "T3"]
