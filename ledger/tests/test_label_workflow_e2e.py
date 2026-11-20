"""End-to-end synthetic run of the label workflow (collect -> pass-2 inputs -> Phase A snapshot -> Phase B -> adjudication
inputs -> finalize) with every module path redirected to a temporary workspace (adapted from review round 3's probe)."""

import csv
import importlib.util
import json
import os
import sys
import time

import pytest

from brainir_ledger import REPO


def _load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "ledger" / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _rec(rid, session, pass_id, **over):
    r = {"record_id": rid, "pass_id": pass_id, "session": session, "doi": "10.7554/eLife.00001", "source_locator": "Fig. 2",
         "quote": "activation evoked walking", "source_type": "targeted_study", "access": "full_text", "name_in_paper": "lineX",
         "manc_type": "DNa05", "mapping_confidence": "medium", "driver_lines": ["SS1"], "effector": "CsChrimson",
         "effector_kind": "optogenetic", "stimulation": "red 5 s", "sex": "male", "preparation": "intact_free",
         "expression": "bilateral", "line_specificity": "clean", "other_cell_types": [], "front_leg_rhythm": "yes",
         "middle_leg_rhythm": "yes", "hind_leg_rhythm": "yes", "behaviour_category": "forward_walking",
         "effect_on_walking": "not_assessed", "labeler_confidence": "high", "saw_simulation_score": False}
    r.update(over)
    return r


def _jl(recs):
    return "".join(json.dumps(r) + "\n" for r in recs)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    lab, rooms = tmp_path / "labels", tmp_path / "rooms"
    raw, work, man = lab / "raw", lab / "work", rooms / "_manifests"
    for d in (raw, work, man):
        d.mkdir(parents=True)
    C, P, R = _load("labels_collect"), _load("labels_prepare"), _load("labels_rooms")
    C.LAB, C.RAW, C.ROOMS = lab, raw, rooms
    P.LAB, P.RAW, P.WORK, P.AUDIT = lab, raw, work, lab / "transcript_audit.json"
    R.ROOMS, R.MANIFESTS, R.RAW, R.WORK = rooms, man, raw, work
    monkeypatch.setattr(P.Path, "home", classmethod(lambda cls: tmp_path / "home"))
    (tmp_path / "home" / "ledger_rooms").mkdir(parents=True)
    os.symlink(rooms, tmp_path / "home" / "ledger_rooms" / "run1")
    spawned = []

    def fake_spawn(cmd, room, session, tag):
        (rooms / f"{session}.{tag}.stream.jsonl").write_text(json.dumps({"type": "system", "session_id": f"sid-{session}"}) + "\n")
        spawned.append((session, tag))
        return 999_991

    R._spawn = fake_spawn

    def room(session, pass_id, family, files):
        d = rooms / session
        (d / "out").mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (d / "out" / name).write_text(content, encoding="utf-8")
        (man / f"{session}.json").write_text(json.dumps({"session": session, "pass": pass_id, "family": family, "room": str(d),
                                                         "runs": [{"tag": "main", "pid": 999_990}]}))
        (rooms / f"{session}.main.stream.jsonl").write_text(json.dumps({"type": "system", "session_id": f"sid-{session}"}) + "\n")

    def audit(breach=None):
        time.sleep(0.02)
        rows = [{"session": m.stem, "issues": [{"kind": "file_outside_room"}] if m.stem == breach else []} for m in man.glob("*.json")]
        (lab / "transcript_audit.json").write_text(json.dumps(rows))

    return {"C": C, "P": P, "R": R, "lab": lab, "raw": raw, "work": work, "rooms": rooms, "room": room, "audit": audit, "spawned": spawned}


def test_label_workflow_end_to_end(ws):
    C, P, R, room, audit = ws["C"], ws["P"], ws["R"], ws["room"], ws["audit"]
    MULTI = dict(line_specificity="multi_dn", name_in_paper="lineX")
    p1a = [_rec("p1-atlas-0001", "pass1-atlas", "pass1", manc_type="DNa02", other_cell_types=["DNa01"], **MULTI),
           _rec("p1-atlas-0002", "pass1-atlas", "pass1", manc_type="DNa01", other_cell_types=["DNa02"], **MULTI),
           _rec("p1-atlas-0003", "pass1-atlas", "pass1", manc_type="DNa03", name_in_paper="DNa03", driver_lines=["SS3"], source_locator="Fig. 3"),
           _rec("p1-atlas-0004", "pass1-atlas", "pass1", manc_type="DNa04", name_in_paper="DNa04", driver_lines=["SS4"], source_locator="Fig. 4")]
    p1c = [_rec("p1-catalogue-0001", "pass1-catalogue", "pass1", manc_type="DNa01", other_cell_types=["DNa02"], **MULTI),  # duplicate
           _rec("p1-catalogue-0002", "pass1-catalogue", "pass1", manc_type="DNa09", name_in_paper="DNa09", driver_lines=["SS9"],
                source_locator="Fig. 9")]
    room("pass1-atlas", "pass1", "atlas", {"records.jsonl": "﻿" + _jl(p1a) + "[1, 2]\n",
                                            "proposed_synonyms.csv": "DNa01,foo,literature,10.1/x,Fig 1\n"})
    room("pass1-catalogue", "pass1", "catalogue", {"records.jsonl": _jl(p1c)})
    room("search-search_names", "search", None, {"records.jsonl": _jl([_rec("s-0001", "search-search_names", "search", manc_type="DNa10",
                                                                            doi="https://doi.org/10.7554/eLife.00001.2")])})
    audit()
    C.collect()
    v = json.loads((ws["raw"] / "pass1" / "pass1-atlas" / "validation.json").read_text())
    assert v["n_valid"] == 4 and v["n_invalid"] == 1                       # BOM tolerated, non-object line rejected
    P.pass2_inputs()
    atlas_rows = list(csv.DictReader(open(ws["work"] / "pass2_inputs" / "atlas" / "experiments_to_label.csv")))
    sib = sorted((r["sibling_index"], r["n_siblings"]) for r in atlas_rows if r["name_in_paper"] == "lineX")
    assert sib == [("1", "2"), ("2", "2")]                                  # the two types of one line, alphabetical order
    assert all("manc_type" not in r for r in atlas_rows)                    # pass 2 never sees the MANC type
    dedupe = json.loads((ws["work"] / "pass1_dedupe_log.json").read_text())
    assert dedupe["dropped"] == [{"exp_id": "pass1-catalogue:p1-catalogue-0001", "duplicate_of": "pass1-atlas:p1-atlas-0002"}]
    A = "pass1-atlas:p1-atlas-"
    p2a = [_rec("p2-atlas-0001", "pass2-atlas", "pass2", exp_id=A + "0002", manc_type="DNa01", other_cell_types=["DNa02"], **MULTI),
           _rec("p2-atlas-0002", "pass2-atlas", "pass2", exp_id=A + "0001", manc_type="DNa02", other_cell_types=["DNa01"], **MULTI),
           _rec("p2-atlas-0003", "pass2-atlas", "pass2", exp_id=A + "0003", manc_type="DNa03", name_in_paper="DNa03", driver_lines=["SS3"],
                source_locator="Fig. 3", front_leg_rhythm="no")]
    room("pass2-atlas", "pass2", "atlas", {"records.jsonl": _jl(p2a), "not_found.csv": "﻿exp_id,reason\n" + A + "0004,absent\n"})
    room("pass2-catalogue", "pass2", "catalogue", {"not_found.csv": "exp_id,reason\n"})  # Phase A wrote no records
    for s in ("pass2-atlas", "pass2-catalogue"):
        sys.argv = ["labels_rooms.py", "phaseb", "--session", s]
        R.main()
    with pytest.raises(SystemExit):
        sys.argv = ["labels_rooms.py", "phaseb", "--session", "pass2-atlas"]
        R.main()
    with pytest.raises(SystemExit):
        sys.argv = ["labels_rooms.py", "repair", "--session", "pass2-atlas"]
        R.main()
    # Phase B: atlas edits a Phase-A record after seeing the quotes; catalogue writes records only after the quotes
    changed = [dict(r) for r in p2a]
    changed[2]["front_leg_rhythm"] = "yes"
    (ws["rooms"] / "pass2-atlas" / "out" / "records.jsonl").write_text(_jl(changed))
    (ws["rooms"] / "pass2-atlas" / "out" / "quote_checks.csv").write_text(
        "exp_id,quote_found,where,comment\n" + "".join(f"{A}000{i},{q},Fig,\n" for i, q in ((1, "TRUE"), (2, "yes"), (3, "true"))))
    (ws["rooms"] / "pass2-catalogue" / "out" / "records.jsonl").write_text(_jl([_rec("p2-catalogue-0001", "pass2-catalogue", "pass2",
                                                                                     exp_id="pass1-catalogue:p1-catalogue-0002",
                                                                                     manc_type="DNa09", name_in_paper="DNa09",
                                                                                     driver_lines=["SS9"], source_locator="Fig. 9")]))
    (ws["rooms"] / "pass2-catalogue" / "out" / "quote_checks.csv").write_text("pass1-catalogue:p1-catalogue-0002,true,Fig 9,\n")
    C.collect()
    va = json.loads((ws["raw"] / "pass2" / "pass2-atlas" / "validation.json").read_text())
    vc = json.loads((ws["raw"] / "pass2" / "pass2-catalogue" / "validation.json").read_text())
    assert va["phase_a_changed_after_quotes"] == ["records.jsonl"] and va["n_valid"] == 3   # snapshot used, change flagged
    assert vc["n_valid"] == 0 and "records.jsonl" in vc["phase_a_changed_after_quotes"]     # Phase-B-only records ignored
    audit()
    P.adjudication_inputs()
    dis = list(csv.DictReader(open(ws["work"] / "adjudication_inputs" / "general" / "disagreements.csv")))
    assert [(d["exp_id"], d["field"]) for d in dis] == [(A + "0003", "front_leg_rhythm")]
    room("adjudication-general", "adjudication", None, {"records.jsonl": _jl([_rec("adj-0001", "adjudication-general", "adjudication",
                                                                                   exp_id=A + "0003", manc_type="DNa03", name_in_paper="DNa03",
                                                                                   driver_lines=["SS3"], source_locator="Fig. 3",
                                                                                   front_leg_rhythm="no", labeler_confidence="medium")])})
    C.collect()
    with pytest.raises(SystemExit):        # the audit is older than the newest session log
        C.finalize()
    audit()
    C.finalize()
    log = json.loads((ws["lab"] / "merge_log.json").read_text())["merge"]
    assert sorted(log["agreed"]) == [A + "0001", A + "0002"] and log["adjudicated"] == [A + "0003"]
    assert log["not_found_by_pass2"] == [A + "0004"] and "pass1-catalogue:p1-catalogue-0002" in log["no_pass2"]
    final = [json.loads(x) for x in (ws["lab"] / "records.jsonl").read_text().splitlines()]
    by = {r["exp_id"]: r for r in final}
    assert by[A + "0003"]["front_leg_rhythm"] == "no" and by[A + "0003"]["labeler_confidence"] == "medium"
    cr = json.loads((ws["lab"] / "agreement.json").read_text())["capture_recapture"]
    assert cr["n_search"] == 1 and cr["n_found_only_by_search"] == 1
