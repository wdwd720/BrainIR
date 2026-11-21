"""Exam 2 label flow on synthetic readings (PREREG v3 T3, T4, S5.2, S5.4, S5.5): two readings -> disputes -> adjudication -> final
records -> consensus, per-source tables, pairs, agreement; then the gate's conditions 2, 4 and 5 on the same files. LABEL SIDE."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from brainir_ledger.labels_h1 import core as C  # noqa: E402

UNITS = [f"{i:02d}A" for i in range(1, 25)]


def rec(rid, session, unit, **cells):
    r = {"record_id": rid, "session": session, "doi": "10.1/src", "hemilineage_as_named": unit, "hemilineages_listed": unit,
         "driver": f"R{unit}-GAL4", "record_type": "whole_two_sided", "preparation": "decapitated", "preparation_detail": "",
         "effector": "UAS-dTrpA1", "penetrance": "", "coverage_notes": "", "locator": "Fig 1", "quote": "they moved",
         "other_observation": "", "saw_model_prediction": False, "notes": ""}
    r.update({d: "no" for d in C.D15})
    r.update(cells)
    return r


@pytest.fixture()
def world(tmp_path, monkeypatch):
    import gate_h1 as GH1
    import labels3_assemble as LA3
    import labels3_rooms as R3

    research = tmp_path / "research" / "ledger"
    lab = research / "labels_h1"
    (research / "hl_units").mkdir(parents=True)
    pd.DataFrame({"unit": UNITS}).to_csv(research / "hl_units" / "UNITS_v1.csv", index=False)
    src = tmp_path / "sources" / "srcA"
    src.mkdir(parents=True)
    (src / "meta.json").write_text(json.dumps({"doi": "10.1/src"}))
    monkeypatch.setattr(LA3, "LAB", lab)
    monkeypatch.setattr(LA3, "UNITS_CSV", research / "hl_units" / "UNITS_v1.csv")
    monkeypatch.setattr(R3, "SOURCES", tmp_path / "sources")
    lab.mkdir(parents=True)
    (lab / "plan.json").write_text(json.dumps({"readings": {"srcA": {"1": ["S1"], "2": ["S2"]}}, "adjudication": {"srcA": ["ADJ1"]},
                                               "harris_slug": "srcA"}))
    r1, r2 = [], []
    for i, u in enumerate(UNITS, 1):
        cells = {"d1": "yes", "d2": "yes", "d3": "yes" if i % 2 else "no", "d4": "yes" if i % 3 else "no", "d7": "yes" if i % 4 else "no"}
        r1.append(rec(f"S1-{i:04d}", "S1", u, **cells))
        c2 = dict(cells)
        if i == 5:
            c2["d3"] = "no"  # one disputed cell
        r2.append(rec(f"S2-{i:04d}", "S2", u, **c2))
    r1.append(rec("S1-0099", "S1", "24A", driver="extra-line"))  # only in reading 1 -> unmatched -> adjudicated as not existing
    for s, rows in (("S1", r1), ("S2", r2)):
        d = lab / "raw" / "reading" / s
        d.mkdir(parents=True)
        (d / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (lab / "transcript_audit.json").write_text(json.dumps([{"session": s, "breach": False} for s in ("S1", "S2", "ADJ1")]))
    return research, lab, LA3, GH1


def _run_flow(lab, LA3):
    LA3.disputes("srcA")
    disp = [json.loads(x) for x in (lab / "work" / "disputes_srcA.jsonl").read_text().splitlines()]
    adj = []
    for d in disp:
        if d["kind"] == "cells":
            adj.append({"dispute_id": d["dispute_id"], "cells": {"d3": "yes"}, "locator": "Fig 1", "quote": "x", "reason": "r"})
        else:
            adj.append({"dispute_id": d["dispute_id"], "exists": False, "record": None, "reason": "not in source"})
    a = lab / "raw" / "adjudication" / "ADJ1"
    a.mkdir(parents=True, exist_ok=True)
    (a / "adjudications.jsonl").write_text("".join(json.dumps(x) + "\n" for x in adj))
    LA3.finalize()


def test_assembled_labels_load_in_the_scorer(world):
    """Audit 10: the files the assembly writes are the files the scorer reads (formats, columns, unit names)."""
    import hashlib

    from brainir_ledger.scoring_h1 import pipeline_h1 as PL

    research, lab, LA3, GH1 = world
    _run_flow(lab, LA3)
    repo = research.parents[1]
    rels = ["research/ledger/labels_h1/consensus.csv", "research/ledger/labels_h1/lab_srcA.csv",
            "research/ledger/labels_h1/consensus_secondary.csv"]
    locks = {"labels": {"labels": {r: hashlib.sha256((repo / r).read_bytes()).hexdigest() for r in rels}}}
    for r in rels:
        c = PL._cons(repo, locks, r, UNITS)
        assert list(c.index) == UNITS
    O = PL.observed(PL._cons(repo, locks, rels[0], UNITS))
    assert int(O.notna().sum(axis=1).ge(3).sum()) == 24


def test_flow(world):
    research, lab, LA3, GH1 = world
    LA3.disputes("srcA")
    disp = [json.loads(x) for x in (lab / "work" / "disputes_srcA.jsonl").read_text().splitlines()]
    kinds = sorted(d["kind"] for d in disp)
    assert kinds == ["cells", "unmatched"]
    room = (lab / "work" / "disputes_srcA_room.jsonl").read_text()
    assert '"key"' not in room  # the adjudicator never sees which reading is which
    adj = []
    for d in disp:
        if d["kind"] == "cells":
            adj.append({"dispute_id": d["dispute_id"], "cells": {"d3": "yes"}, "locator": "Fig 1", "quote": "x", "reason": "r"})
        else:
            adj.append({"dispute_id": d["dispute_id"], "exists": False, "record": None, "reason": "not in source"})
    a = lab / "raw" / "adjudication" / "ADJ1"
    a.mkdir(parents=True)
    (a / "adjudications.jsonl").write_text("".join(json.dumps(x) + "\n" for x in adj))
    LA3.finalize()
    final = pd.read_csv(lab / "records.csv", dtype=str, keep_default_na=False)
    assert len(final) == 24 and set(final["unit"]) == set(UNITS) and (final["eligible"] == "True").all()
    assert final.set_index("unit").loc["05A", "d3"] == "yes" and "ADJ1" in final.set_index("unit").loc["05A", "source_sessions"]
    cons = pd.read_csv(lab / "consensus.csv", dtype=str).set_index("unit")
    assert cons.loc["04A", "d7p"] == "no" and cons.loc["05A", "d7p"] == "yes" and list(cons.columns)[-1] == "d7p"
    assert (lab / "lab_srcA.csv").is_file() and len(pd.read_csv(lab / "pairs.csv")) == 24
    ag = json.loads((lab / "agreement.json").read_text())
    assert ag["readings"]["n"] == 24 * 12 and ag["readings"]["kappa"] > 0.9
    # the gate's label conditions on these files
    c2 = GH1.cond2(research)
    assert c2["pass"] and c2["n_contributing_sessions"] == 3
    c4 = GH1.cond4(research)
    assert c4["pass"] and c4["n_pairs"] == 24
    c5 = GH1.cond5(research)
    assert c5["pass"] and c5["n_units_ge3_coded_primary"] == 24


def test_breached_session_blocks(world):
    research, lab, LA3, GH1 = world
    (lab / "transcript_audit.json").write_text(json.dumps([{"session": "S1", "breach": True}, {"session": "S2", "breach": False}]))
    LA3.disputes("srcA")
    pj = json.loads((lab / "work" / "pairing_srcA.json").read_text())
    assert pj["n_reading_1"] == 0 and len(pj["pairs"]) == 0  # a breaching session contributes nothing (T7)
