"""Synthetic tests of the run-2 label collector (`ledger/scripts/labels2_collect.py`). No real label, source or session is read:
every folder is redirected into pytest's tmp_path; only the kit's type list is used (to pick a valid type name)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import labels2_collect as L2  # noqa: E402
import labels_collect as LC  # noqa: E402

DEAD_PID = 999_999


@pytest.fixture
def sb(tmp_path, monkeypatch):
    lab = tmp_path / "labels_v2"
    for k, v in dict(LAB=lab, RAW=lab / "raw", WORK=lab / "work", SPECS=lab / "work" / "specs", VER=lab / "verify",
                     LOCKED=tmp_path / "LOCK_labels_v2.json", SOURCES=tmp_path / "sources").items():
        monkeypatch.setattr(L2, k, v)
    monkeypatch.setattr(LC, "LAB", lab)
    monkeypatch.setattr(LC, "RAW", lab / "raw")
    monkeypatch.setattr(L2.R2, "MANIFESTS", tmp_path / "manifests")
    monkeypatch.setattr(L2.R2, "ROOMS", tmp_path / "rooms")
    monkeypatch.setattr(L2.R2, "transcripts", lambda room: [])
    (tmp_path / "manifests").mkdir()
    (lab / "work" / "specs").mkdir(parents=True)
    return tmp_path


TYPES = sorted(LC.known_types())
T0, T1, T2 = TYPES[0], TYPES[1], TYPES[2]


def rec(session: str, n: int, doi: str = "10.1234/abc", **kw) -> dict:
    r = {"record_id": f"{session}-{n:04d}", "pass_id": "pass1", "session": session, "doi": doi, "source_locator": "Fig. 1",
         "quote": "flies groomed", "source_type": "targeted_study", "access": "full_text", "name_in_paper": T0, "manc_type": T0,
         "mapping_confidence": "high", "driver_lines": ["SS1"], "effector": "CsChrimson", "effector_kind": "optogenetic",
         "stimulation": "red light", "sex": "male", "preparation": "intact_free", "expression": "bilateral", "line_specificity": "clean",
         "other_cell_types": [], "front_leg_rhythm": "yes", "middle_leg_rhythm": "no", "hind_leg_rhythm": "no",
         "behaviour_category": "anterior_grooming", "effect_on_walking": "not_assessed", "labeler_confidence": "high",
         "saw_simulation_score": False}
    r.update(kw)
    r["exp_id"] = f"{session}:{r['record_id']}"
    return r


def jsonl(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))


def manifest(sb: Path, session: str, kind: str, sources: list[str], family=None) -> None:
    room = sb / "rooms" / session
    (room / "out").mkdir(parents=True, exist_ok=True)
    (sb / "manifests" / f"{session}.json").write_text(json.dumps({"session": session, "kind": kind, "family": family, "room": str(room),
                                                                  "sources": sources, "pass": "pass1", "runs": [{"tag": "main", "pid": DEAD_PID}]}))


def audit(sb: Path, breach=()) -> None:
    rows = [{"session": json.loads(m.read_text())["session"], "breach": json.loads(m.read_text())["session"] in breach}
            for m in (sb / "manifests").glob("*.json")]
    p = L2.LAB / "transcript_audit.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows))


def source(sb: Path, doi: str, status: str = "full_text") -> str:
    s = L2.slug(doi)
    (sb / "sources" / s).mkdir(parents=True, exist_ok=True)
    (sb / "sources" / s / "meta.json").write_text(json.dumps({"doi": doi, "status": status}))
    return s


def registry(rows: list[tuple[str, str]]) -> None:
    p = L2.WORK / "registry.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["doi", "slug", "family", "provenance", "round"])
        for d, fam in rows:
            w.writerow([d, L2.slug(d), fam, "test", 0])


# ------------------------------------------------------------------------------------------------------------------------ tests
def test_spec_is_never_overwritten(sb):
    L2._spec({"session": "x", "kind": "reader"})
    with pytest.raises(SystemExit):
        L2._spec({"session": "x", "kind": "reader"})


def test_readers_count_only_reader_assignments(sb):
    """Review B1: Namiki and the catalogue are in the atlas-map spec but still get a first reading; the atlas does not."""
    registry([(L2.ATLAS_DOI, "atlas"), (L2.NAMIKI_DOI, "driver_line_resources"), ("10.1234/other", "grooming")])
    for d in (L2.ATLAS_DOI, L2.NAMIKI_DOI, "10.1234/other"):
        source(sb, d)
    L2._spec({"session": "atlas-map", "kind": "atlas_map", "sources": [L2.slug(L2.ATLAS_DOI), L2.slug(L2.NAMIKI_DOI)]})
    L2.readers(0)
    got = {x for s in L2._specs(("reader", "reader_web")) for x in s["sources"]}
    assert got == {L2.slug(L2.NAMIKI_DOI), L2.slug("10.1234/other")}


def test_readers_route_abstract_only_to_reader_web(sb):
    registry([("10.1234/a", "grooming"), ("10.1234/b", "grooming")])
    source(sb, "10.1234/a")
    source(sb, "10.1234/b", status="abstract_only")
    L2.readers(0)
    kinds = {s["sources"][0]: s["kind"] for s in L2._specs(("reader", "reader_web"))}
    assert kinds == {L2.slug("10.1234/a"): "reader", L2.slug("10.1234/b"): "reader_web"}


def test_breaching_requires_a_current_audit(sb):
    """Review B4: a finished session missing from the audit stops the step."""
    manifest(sb, "pass1-grooming-r0-01", "reader", [])
    audit(sb)
    manifest(sb, "pass1-grooming-r0-02", "reader", [])
    with pytest.raises(SystemExit):
        L2._breaching()
    audit(sb)
    assert L2._breaching() == set()


def test_records_tied_to_assigned_sources(sb):
    """Review M1: a record of a DOI the session was not given is not used; a preprint version suffix still matches."""
    s = "pass1-grooming-r0-01"
    src = source(sb, "10.1101/2025.01.01.123456")
    registry([("10.1101/2025.01.01.123456", "grooming")])
    L2._spec({"session": s, "kind": "reader", "family": "grooming", "sources": [src]})
    manifest(sb, s, "reader", [src], "grooming")
    jsonl(L2.RAW / "pass1" / s / "records.valid.jsonl",
          [rec(s, 1, doi="10.1101/2025.01.01.123456v2"), rec(s, 2, doi="10.9999/elsewhere", manc_type=T1, name_in_paper=T1)])
    audit(sb)
    log: dict = {}
    kept = L2._pass1_generic(L2._breaching(), log)
    assert [r["record_id"] for r in kept] == [f"{s}-0001"]
    assert kept[0]["doi"] == "10.1101/2025.01.01.123456"
    assert log["records_outside_assigned_sources"] == [f"{s}:{s}-0002"]


def test_not_found_of_replaced_breaching_second_reader_is_ignored(sb):
    """Review B2: the breaching session's not-found row does not drop the record its replacement found and verified."""
    s1 = "pass1-grooming-r0-01"
    src = source(sb, "10.1234/abc")
    registry([("10.1234/abc", "grooming")])
    L2._spec({"session": s1, "kind": "reader", "family": "grooming", "sources": [src]})
    manifest(sb, s1, "reader", [src], "grooming")
    r1 = rec(s1, 1)
    jsonl(L2.RAW / "pass1" / s1 / "records.valid.jsonl", [r1])
    L2._spec({"session": "pass2-general-01", "kind": "second", "sources": [src], "exp_ids": [r1["exp_id"]]})
    L2._spec({"session": "pass2-general-01-r1", "kind": "second", "sources": [src], "exp_ids": [r1["exp_id"]], "replaces": "pass2-general-01"})
    manifest(sb, "pass2-general-01", "second", [src])
    manifest(sb, "pass2-general-01-r1", "second", [src])
    nf = L2.RAW / "pass2" / "pass2-general-01" / "not_found.csv"
    nf.parent.mkdir(parents=True)
    nf.write_text(f"exp_id,reason\n{r1['exp_id']},x\n")
    jsonl(L2.RAW / "pass2" / "pass2-general-01-r1" / "records.valid.jsonl", [dict(r1, pass_id="pass2", session="pass2-general-01-r1")])
    (L2.RAW / "pass2" / "pass2-general-01-r1" / "quote_checks.csv").write_text(f"exp_id,quote_found,where,comment\n{r1['exp_id']},true,Fig 1,\n")
    audit(sb, breach=("pass2-general-01",))
    final, _, _, _ = L2.merged(L2._breaching())
    assert [r["exp_id"] for r in final] == [r1["exp_id"]]


def test_adjudication_is_incremental(sb):
    """Review B5: a second run adds new sessions for new disputes and leaves earlier specs untouched."""
    s1 = "pass1-grooming-r0-01"
    a_src, b_src = source(sb, "10.1234/a"), source(sb, "10.1234/b")
    registry([("10.1234/a", "grooming"), ("10.1234/b", "grooming")])
    L2._spec({"session": s1, "kind": "reader", "family": "grooming", "sources": [a_src, b_src]})
    manifest(sb, s1, "reader", [a_src, b_src], "grooming")
    ra = rec(s1, 1, doi="10.1234/a")
    rb = rec(s1, 2, doi="10.1234/b", manc_type=T1, name_in_paper=T1)
    jsonl(L2.RAW / "pass1" / s1 / "records.valid.jsonl", [ra, rb])
    jsonl(L2.RAW / "pass2" / "pass2-general-01" / "records.valid.jsonl", [dict(ra, front_leg_rhythm="no", pass_id="pass2")])
    manifest(sb, "pass2-general-01", "second", [a_src])
    audit(sb)
    L2.adjudication()
    first = (L2.SPECS / "adjudication-general-01.json").read_text()
    jsonl(L2.RAW / "pass2" / "pass2-general-02" / "records.valid.jsonl", [dict(rb, front_leg_rhythm="no", pass_id="pass2")])
    manifest(sb, "pass2-general-02", "second", [b_src])
    audit(sb)
    L2.adjudication()
    assert (L2.SPECS / "adjudication-general-01.json").read_text() == first
    second = json.loads((L2.SPECS / "adjudication-general-02.json").read_text())
    assert second["disputes"] == [[rb["exp_id"], "front_leg_rhythm"]]


def test_atlas_key_map_and_expansion(sb):
    """N3 / review M2: headless and intact tests of one line are two experiments; the map's confidence is normalised, types split
    on ',' or ';', unknown names logged, a duplicate row logged; a two-type line becomes multi_dn."""
    for s, kind in (("atlas-codeA", "atlas_code"), ("atlas-codeB", "atlas_code"), ("atlas-map", "atlas_map")):
        manifest(sb, s, kind, [])
    mp = L2.RAW / "atlas_map" / "atlas-map" / "atlas_line_map.csv"
    mp.parent.mkdir(parents=True)
    mp.write_text(f"line_id,manc_types,mapping_confidence,mapping_basis\n SS 01 ,\"{T1}, {T2}, NotAType\",High,fig\nSS01,{T0},low,dup\n")
    a = [rec("atlas-codeA", 1, doi=L2.ATLAS_DOI, driver_lines=["SS01"], manc_type="UNMAPPED", mapping_confidence="low", preparation="headless"),
         rec("atlas-codeA", 2, doi=L2.ATLAS_DOI, driver_lines=["SS01"], manc_type="UNMAPPED", mapping_confidence="low", preparation="intact_free")]
    jsonl(L2.RAW / "pass1" / "atlas-codeA" / "records.valid.jsonl", a)
    jsonl(L2.RAW / "pass1" / "atlas-codeB" / "records.valid.jsonl", [dict(a[0], session="atlas-codeB")])
    audit(sb)
    p1, p2, qc, info = L2.atlas_pairs(L2._breaching())
    ids = sorted(r["exp_id"] for r in p1)
    assert ids == sorted(f"atlas:SS01:{p}:{t}" for p in ("headless", "intact") for t in (T1, T2))
    assert {r["mapping_confidence"] for r in p1} == {"high"}
    assert all(r["line_specificity"] == "multi_dn" for r in p1)
    assert sorted(r["exp_id"] for r in p2) == sorted(f"atlas:SS01:headless:{t}" for t in (T1, T2))
    assert info["map"]["duplicate_rows"] == ["SS01"] and info["map"]["unknown_type_names"][0]["names"] == ["NotAType"]
    assert qc == {} and "quote_checks_not_used" in info  # B checked no quotes of this A session


def test_reassign_limits_and_unreached(sb):
    """L5: at most two reassignments per source, then reported as unreached."""
    src = source(sb, "10.1234/abc")
    registry([("10.1234/abc", "grooming")])
    names = ["pass1-grooming-r0-01", "pass1-grooming-r0-01-a1", "pass1-grooming-r0-01-a1-a1"]
    L2._spec({"session": names[0], "kind": "reader", "family": "grooming", "sources": [src]})
    for i, s in enumerate(names):
        manifest(sb, s, "reader", [src], "grooming")
        audit(sb)
        L2.reassign()
        made = [x["session"] for x in L2._specs("reader")]
        if i < 2:
            assert names[i + 1] in made
    assert [r["slug"] for r in csv.DictReader(open(L2.WORK / "unreached_sources.csv"))] == [src]
