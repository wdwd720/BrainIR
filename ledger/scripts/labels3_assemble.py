"""Exam 2 label assembly (LABEL SIDE; PREREG v3 T2-T5, T7, T8; never reads a prediction file).

    labels3_assemble.py collect [SESSION ...]     # room out/ -> labels_h1/raw/<kind>/<session>/, manifests -> labels_h1/sessions/
    labels3_assemble.py disputes SLUG             # pair reading 1 and 2 of a source (T3) -> labels_h1/work/disputes_<slug>.jsonl
    labels3_assemble.py finalize                  # final records, consensus, per-source and external tables, agreement
    labels3_assemble.py verify-sample             # the verification sample (T8) -> labels_h1/verify/to_verify.jsonl + room input
    labels3_assemble.py verify-score              # -> labels_h1/verification.json

`labels_h1/plan.json` names the sessions: {"readings": {slug: {"1": [sessions], "2": [sessions]}}, "adjudication": {slug:
[sessions]}, "cheong": [sessions], "search": [sessions], "verify": [sessions], "harris_slug": slug}. A session listed in a reading
that breached (transcript audit) contributes nothing (T7); its scope must be re-read by a new session added to the plan.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))
import labels3_rooms as R3  # noqa: E402  (re-points labels2_rooms: run 3 rooms and manifests)

from brainir_ledger.labels_h1 import core as C  # noqa: E402

R2 = R3.R2
LAB = R3.REPO / "research" / "ledger" / "labels_h1"
UNITS_CSV = R3.REPO / "research" / "ledger" / "hl_units" / "UNITS_v1.csv"
OUT_FILES = ("records.jsonl", "dispositions.csv", "coverage.csv", "notes.md", "sightings.csv", "adjudications.jsonl", "leads.csv",
             "verification.jsonl")


def units() -> list[str]:
    return pd.read_csv(UNITS_CSV, dtype={"unit": str})["unit"].tolist()


def plan() -> dict:
    return json.loads((LAB / "plan.json").read_text(encoding="utf-8"))


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.is_file() else []


def _write_jsonl(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8", newline="\n")


def _scrub(s: str) -> str:
    home = str(Path.home())
    return s.replace(home, "~").replace(R2.LA.encode(home), "-HOME")


# ------------------------------------------------------------------------------------------------ collect
def collect(sessions: list[str]) -> None:
    mans = {json.loads(m.read_text())["session"]: json.loads(m.read_text()) for m in sorted(R2.MANIFESTS.glob("*.json"))}
    for s in sessions or sorted(mans):
        man = mans[s]
        kind = man["kind"] if man["kind"] != "reader" else "reading"
        dest = LAB / "raw" / kind / s
        dest.mkdir(parents=True, exist_ok=True)
        out = Path(man["room"]) / "out"
        for name in OUT_FILES:
            if (out / name).is_file():
                shutil.copyfile(out / name, dest / name)
        rep = {"session": s, "kind": man["kind"], "files": sorted(p.name for p in dest.iterdir())}
        if (dest / "records.jsonl").is_file():
            recs = _jsonl(dest / "records.jsonl")
            bad = {r.get("record_id", f"line{i}"): C.validate(r) for i, r in enumerate(recs)}
            bad = {k: v for k, v in bad.items() if v}
            own = [r.get("record_id") for r in recs if not str(r.get("record_id", "")).startswith(s + "-") or r.get("session") != s]
            rep.update({"n_records": len(recs), "invalid": bad, "foreign_ids": own})
        (dest / "VALIDATION.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
        sm = LAB / "sessions" / f"{s}.json"
        sm.parent.mkdir(parents=True, exist_ok=True)
        sm.write_text(_scrub(json.dumps(man, indent=1)) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in rep.items()}))


# ------------------------------------------------------------------------------------------------ readings and disputes
def _audit() -> dict[str, dict]:
    p = LAB / "transcript_audit.json"
    return {r["session"]: r for r in json.loads(p.read_text())} if p.is_file() else {}


def reading(slug: str, which: str, doi: str | None = None) -> list[dict]:
    """Records of one reading of a source: every listed session's valid records of that source, de-duplicated (a record that
    two scope halves both wrote is kept once). Sessions that breached contribute nothing."""
    aud = _audit()
    out, seen = [], set()
    for s in plan()["readings"][slug][which]:
        if aud.get(s, {}).get("breach"):
            continue
        for r in _jsonl(LAB / "raw" / "reading" / s / "records.jsonl"):
            if C.validate(r):
                continue
            if doi and r["doi"].lower().strip() != doi.lower():
                continue
            k = (r["doi"].lower().strip(), r["hemilineage_as_named"].strip().lower(), C.driver_norm(r["driver"]), r["preparation"],
                 C.effector_class(r["effector"]))
            if k not in seen:
                seen.add(k)
                out.append(r)
    return out


def source_doi(slug: str) -> str:
    return json.loads((R3.SOURCES / slug / "meta.json").read_text())["doi"]


def disputes(slug: str) -> None:
    U = units()
    doi = source_doi(slug)
    a, b = reading(slug, "1", doi), reading(slug, "2", doi)
    pairs, ua, ub = C.pair_readings(a, b, U)
    rows, idx = [], 0
    coin = C.coin_order([f"{slug}:{x['record_id']}:{y['record_id']}" for x, y in pairs if C.disputed_fields(x, y)]
                        + [f"{slug}:{r['record_id']}" for r in ua + ub])
    for x, y in pairs:
        f = C.disputed_fields(x, y)
        if not f:
            continue
        did = f"{slug}:{x['record_id']}:{y['record_id']}"
        first, second = (y, x) if coin[did] else (x, y)
        idx += 1
        rows.append({"dispute_id": f"D{idx:04d}", "key": did, "kind": "cells", "hemilineage_as_named": x["hemilineage_as_named"],
                     "driver": x["driver"], "preparation": x["preparation"], "effector": x["effector"],
                     "cells": {k: {"reading_1": first[k], "reading_2": second[k]} for k in f},
                     "locators": [first["locator"], second["locator"]], "quotes": [first["quote"], second["quote"]]})
    for r in ua + ub:
        did = f"{slug}:{r['record_id']}"
        idx += 1
        rows.append({"dispute_id": f"D{idx:04d}", "key": did, "kind": "unmatched",
                     "record": {k: v for k, v in r.items() if k not in ("record_id", "session")}})
    room_rows = [{k: v for k, v in r.items() if k != "key"} for r in rows]
    _write_jsonl(LAB / "work" / f"disputes_{slug}.jsonl", rows)
    _write_jsonl(LAB / "work" / f"disputes_{slug}_room.jsonl", room_rows)
    pj = {"slug": slug, "doi": doi, "n_reading_1": len(a), "n_reading_2": len(b), "pairs": [[x["record_id"], y["record_id"]] for x, y in pairs],
          "unmatched_1": [r["record_id"] for r in ua], "unmatched_2": [r["record_id"] for r in ub], "n_disputes": len(rows)}
    (LAB / "work" / f"pairing_{slug}.json").write_text(json.dumps(pj, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in pj.items()}))


# ------------------------------------------------------------------------------------------------ final records
def _adjudications(slug: str) -> tuple[dict, list[str]]:
    out, sess = {}, []
    aud = _audit()
    for s in plan().get("adjudication", {}).get(slug, []):
        if aud.get(s, {}).get("breach"):
            continue
        sess.append(s)
        for d in _jsonl(LAB / "raw" / "adjudication" / s / "adjudications.jsonl"):
            out[d["dispute_id"]] = {**d, "_session": s}
    return out, sess


def finalize() -> None:
    U = units()
    aud = _audit()
    finals, pair_rows = [], []
    for slug in sorted(plan()["readings"]):
        pj = json.loads((LAB / "work" / f"pairing_{slug}.json").read_text())
        doi = pj["doi"]
        recs = {r["record_id"]: r for w in ("1", "2") for r in reading(slug, w, doi)}
        disp = {d["key"]: d for d in _jsonl(LAB / "work" / f"disputes_{slug}.jsonl")}
        adj, adj_sessions = _adjudications(slug)
        for id1, id2 in pj["pairs"]:
            x, y = recs[id1], recs[id2]
            key = f"{slug}:{id1}:{id2}"
            cells = None
            if key in disp:
                a = adj.get(disp[key]["dispute_id"])
                if a is None:
                    raise SystemExit(f"{slug} {disp[key]['dispute_id']}: not adjudicated")
                cells = a["cells"]
            f = C.final_from_pair(x, y, cells)
            f["source_sessions"] = ";".join(sorted({x["session"], y["session"]} | ({adj[disp[key]["dispute_id"]]["_session"]} if key in disp else set())))
            f["origin"] = "pair"
            finals.append(f)
            pair_rows.append({"record_id_1": id1, "record_id_2": id2, "doi": doi})
        for rid in pj["unmatched_1"] + pj["unmatched_2"]:
            d = disp[f"{slug}:{rid}"]
            a = adj.get(d["dispute_id"])
            if a is None:
                raise SystemExit(f"{slug} {d['dispute_id']}: not adjudicated")
            if a.get("exists") and a.get("record"):
                r = dict(a["record"])
                problems = C.validate(r)
                if problems:
                    raise SystemExit(f"{slug} {d['dispute_id']}: adjudicated record invalid: {problems}")
                r["source_sessions"] = ";".join(sorted({recs[rid]["session"], a["_session"]}))
                r["origin"] = "adjudicated_unmatched"
                r["saw_model_prediction"] = bool(r["saw_model_prediction"] or recs[rid]["saw_model_prediction"])
                finals.append(r)
    df = pd.DataFrame(finals)
    mapped = [C.unit_of(r, U) for r in finals]
    df["unit"] = [m[0] for m in mapped]
    df["unit_mapping"] = [m[1] for m in mapped]
    df["d7p"] = [C.d7p(r) for r in finals]
    df["eligible"] = [(not r["saw_model_prediction"]) and not any(aud.get(s, {}).get("breach", True) for s in r["source_sessions"].split(";"))
                      for r in finals]
    cols = ["record_id", "doi", "unit", "unit_mapping", "hemilineage_as_named", "hemilineages_listed", "driver", "record_type", "preparation",
            "preparation_detail", "effector", "penetrance", "coverage_notes"] + C.D15 + ["d7p", "eligible", "saw_model_prediction",
                                                                                           "source_sessions", "origin", "paired_with", "locator", "quote", "other_observation"]
    df = df.reindex(columns=cols).sort_values(["doi", "unit", "record_id"], na_position="last")
    LAB.mkdir(parents=True, exist_ok=True)
    df.to_csv(LAB / "records.csv", index=False, lineterminator="\n")
    pd.DataFrame(pair_rows).to_csv(LAB / "pairs.csv", index=False, lineterminator="\n")
    df[df["unit"].isna()][["record_id", "doi", "hemilineage_as_named", "hemilineages_listed", "unit_mapping"]].to_csv(
        LAB / "unmapped_records.csv", index=False, lineterminator="\n")
    fin = df.copy()
    cons, per = C.consensus(fin, U)
    sec, _ = C.consensus(fin, U, record_types=("clonal", "one_sided", "partial_or_mixed"))
    cons.reset_index().to_csv(LAB / "consensus.csv", index=False, lineterminator="\n")
    sec.reset_index().to_csv(LAB / "consensus_secondary.csv", index=False, lineterminator="\n")
    slug_of = {source_doi(s).lower(): s for s in plan()["readings"]}
    for doi, t in per.items():
        t.reset_index().to_csv(LAB / f"lab_{slug_of.get(doi.lower(), doi.replace('/', '_'))}.csv", index=False, lineterminator="\n")
    # external check (T5): the Cheong session's coding of the published summary, never truth
    ext = []
    for s in plan().get("cheong", []):
        if not aud.get(s, {}).get("breach"):
            ext += [r for r in _jsonl(LAB / "raw" / "cheong" / s / "records.jsonl") if not C.validate(r)]
    prs = list(_pairs_records(pair_rows))
    full: list[bool] = []
    for a, b in prs:
        a2, b2 = {**a, "d7p": C.d7p(a)}, {**b, "d7p": C.d7p(b)}
        full += [a2[d] == b2[d] for d in C.PRIMARY]
    match = {}
    for slug in sorted(plan()["readings"]):
        pj = json.loads((LAB / "work" / f"pairing_{slug}.json").read_text())
        n = len(pj["pairs"]) + len(pj["unmatched_1"]) + len(pj["unmatched_2"])
        match[slug] = {"pairs": len(pj["pairs"]), "unmatched_1": len(pj["unmatched_1"]), "unmatched_2": len(pj["unmatched_2"]),
                       "match_rate": (len(pj["pairs"]) / n) if n else None}
    agreement = {"readings": C.readings_kappa(prs), "n_final_records": len(df),
                 "readings_full_vocabulary_agreement": (sum(full) / len(full)) if full else None, "record_match": match,
                 "n_eligible_whole_two_sided": int((df["eligible"] & (df["record_type"] == "whole_two_sided")).sum()),
                 "n_units_ge3_coded_primary": C.n_units_ge3(cons)}
    if ext:
        e = pd.DataFrame(ext)
        e["unit"] = [C.unit_of(r, U)[0] for r in ext]
        e["d7p"] = [C.d7p(r) for r in ext]
        e["eligible"] = ~e["saw_model_prediction"].astype(bool)
        e["doi"] = "cheong_summary"
        ec, _ = C.consensus(e, U, record_types=tuple(C.RECORD_TYPES))
        ec.reset_index().to_csv(LAB / "external_cheong_summary.csv", index=False, lineterminator="\n")
        hs = plan().get("harris_slug")
        if hs and source_doi(hs).lower() in per:
            h = per[source_doi(hs).lower()]
            both = sorted(set(h.index) & set(ec.index))
            agreement["harris_vs_cheong_summary"] = C.cohen_kappa([h.loc[u, d] for u in both for d in C.PRIMARY],
                                                                   [ec.loc[u, d] for u in both for d in C.PRIMARY])
    srcs = sorted(per)
    agreement["between_sources"] = {f"{a} vs {b}": C.cohen_kappa(
        [per[a].loc[u, d] for u in sorted(set(per[a].index) & set(per[b].index)) for d in C.PRIMARY],
        [per[b].loc[u, d] for u in sorted(set(per[a].index) & set(per[b].index)) for d in C.PRIMARY])
        for i, a in enumerate(srcs) for b in srcs[i + 1:]}
    (LAB / "agreement.json").write_text(json.dumps(agreement, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"final_records": len(df), "unmapped": int(df["unit"].isna().sum()), "units_in_consensus": len(cons),
                      **{k: v for k, v in agreement.items() if k.startswith("n_")}}))


def _pairs_records(pair_rows: list[dict]):
    recs = {}
    for f in (LAB / "raw" / "reading").glob("*/records.jsonl"):
        for r in _jsonl(f):
            recs[r["record_id"]] = r
    aud = _audit()
    for p in pair_rows:
        a, b = recs[p["record_id_1"]], recs[p["record_id_2"]]
        if not aud.get(a["session"], {"breach": True})["breach"] and not aud.get(b["session"], {"breach": True})["breach"]:
            yield a, b


# ------------------------------------------------------------------------------------------------ verification
def verify_sample() -> None:
    df = pd.read_csv(LAB / "records.csv", dtype=str, keep_default_na=False)
    df["eligible"] = df["eligible"].map({"True": True, "False": False})
    ids = C.verification_sample(df)
    rows, room = [], []
    by = df.set_index("record_id")
    for i, rid in enumerate(ids, 1):
        r = by.loc[rid]
        v = {"verify_id": f"V{i:03d}", "doi": r["doi"], "hemilineage_as_named": r["hemilineage_as_named"], "driver": r["driver"],
             "preparation": r["preparation"], "effector": r["effector"], "locator": r["locator"]}
        room.append(v)
        rows.append({**v, "record_id": rid})
    _write_jsonl(LAB / "verify" / "to_verify.jsonl", rows)
    _write_jsonl(LAB / "work" / "to_verify_room.jsonl", room)
    print(json.dumps({"sampled": len(ids), "dois": sorted({r["doi"] for r in rows})}))


def verify_score() -> None:
    df = pd.read_csv(LAB / "records.csv", dtype=str, keep_default_na=False)
    sample = {r["verify_id"]: r["record_id"] for r in _jsonl(LAB / "verify" / "to_verify.jsonl")}
    got = {}
    for s in plan().get("verify", []):
        for d in _jsonl(LAB / "raw" / "verify" / s / "verification.jsonl"):
            got[d["verify_id"]] = d["cells"]
    res = C.verification_error(df, {sample[v]: c for v, c in got.items() if v in sample})
    res["n_sampled"], res["n_verified"] = len(sample), len(set(got) & set(sample))
    (LAB / "verification.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in res.items() if k != "errors"}))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("sessions", nargs="*")
    d = sub.add_parser("disputes")
    d.add_argument("slug")
    for n in ("finalize", "verify-sample", "verify-score"):
        sub.add_parser(n)
    a = ap.parse_args()
    if a.cmd == "collect":
        collect(a.sessions)
    elif a.cmd == "disputes":
        disputes(a.slug)
    else:
        {"finalize": finalize, "verify-sample": verify_sample, "verify-score": verify_score}[a.cmd]()


if __name__ == "__main__":
    main()
