"""PREREG v5 Part L after the sessions (LABEL SIDE): quote checks and the line-specificity fill (L3), the atlas codings (A/B/C, mapped
by exam 1's atlas map), reader labels and disputes, audited labels, the comparison with exam 1, the verification of non-clear outcomes,
the error rates (L4) and the by-design counts (L5). The orchestrator writes no label: every record comes from a session, and labels are
computed by the frozen consensus (`brainir_ledger.labels.aggregate.type_labels`). The exploratory re-score of exam 1 (L7) reads the
prediction lock, so it lives in `rescore_audit_v1.py`, outside the label side.

    uv run --project ledger --no-sync python ledger/scripts/labels_audit_v1.py disputes   # after readers and atlas coders: what goes to C
    uv run --project ledger --no-sync python ledger/scripts/labels_audit_v1.py labels     # after adjudication: audited labels (writes once)
    uv run --project ledger --no-sync python ledger/scripts/labels_audit_v1.py errors     # after verification: comparison and rates (writes once)
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit5_rooms as AR  # noqa: E402

from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger.labels import aggregate as AGG  # noqa: E402
from brainir_ledger.labels.schema import validate_record  # noqa: E402

OUT = RESEARCH / "labels_audit_v1"
LAB2 = RESEARCH / "labels_v2"
INTACT = ("intact_free", "intact_tethered")
SCOPES = {"headless": lambda r: r.get("preparation") == "headless", "intact": lambda r: r.get("preparation") in INTACT}
LEGS = ("front_leg_rhythm", "middle_leg_rhythm", "hind_leg_rhythm")


def _assignment() -> dict:
    return json.loads((OUT / "ASSIGNMENT.json").read_text(encoding="utf-8"))


def _breaching() -> set[str]:
    p = OUT / "TRANSCRIPT_AUDIT.json"
    if not p.exists():
        raise SystemExit("run `audit5_rooms.py transcript-audit` first (L1)")
    return set(json.loads(p.read_text(encoding="utf-8"))["breaching_sessions"])


def _session_records(pattern: str) -> list[tuple[str, dict]]:
    """(session, record) for every collected, non-breaching session matching the glob."""
    br = _breaching()
    out = []
    for sd in sorted((OUT / "sessions").glob(pattern)):
        if sd.name in br:
            continue
        for r in AR._jsonl(sd / "records.jsonl"):
            out.append((sd.name, r))
    return out


def _fill(recs: list[dict]) -> list[dict]:
    """L3: PREREG v2 L10's frozen line-specificity fill, applied before any consensus (it logs by `exp_id`)."""
    import labels2_collect as L2C  # noqa: PLC0415  (frozen)

    L2C.line_spec_fill(recs)
    return recs


def reader_records() -> tuple[list[dict], list[dict]]:
    """Every record of the reader sessions (a5-gNN-A/B), with session, reader, group, quote status and schema errors; and a log."""
    d2s = AR.doi_to_slug()
    corpus: dict[str, str] = {}
    man = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (OUT / "rooms").glob("a5-g*.json")}
    recs, log = [], []
    for s, r in _session_records("a5-g*"):
        m = man.get(s, {})
        rr = dict(r, session=s, reader=m.get("reader"), group=m.get("group"), exp_id=f"{s}:{r.get('record_id')}")
        rr["quote_status"] = AR.quote_status(rr, corpus, d2s)
        rr["schema_errors"] = validate_record(dict(r, pass_id="pass1"))   # the frozen validator has no 'audit' pass
        recs.append(rr)
    return recs, log


def counted(recs: list[dict], pool: list[dict] | None = None) -> list[dict]:
    """L3: schema-valid records whose quote is found, or that are marked as read from a figure, or (re-check 14) that cite a source whose
    cached copy is abstract-only or unreachable and are matched by a record of another reader (same DOI, preparation, type and front-leg
    value); the L10 fill is applied; sightings do not exclude in this audit. `pool` = the records searched for that match."""
    import collections  # noqa: PLC0415

    pool = recs if pool is None else pool
    c = AR.cache()
    d2s = AR.doi_to_slug(c)
    web = {sl for sl, v in c.items() if v["status"] in AR.WEB_STATUSES}

    def key(r):
        return (AR._norm_doi(r.get("doi")), r.get("preparation"), r.get("manc_type"), r.get("front_leg_rhythm"))

    by_reader = collections.defaultdict(set)
    for r in pool:
        if not r.get("schema_errors"):
            by_reader[r.get("reader")].add(key(r))
    keep = []
    for r in recs:
        if r["schema_errors"]:
            continue
        st = r["quote_status"]
        if st == "not_found" and d2s.get(AR._norm_doi(r.get("doi"))) in web and any(key(r) in ks for rd, ks in by_reader.items() if rd != r.get("reader")):
            st = "web_agreed"
        if st == "not_found":
            continue
        keep.append(dict(r, quote_status=st, quote_verified=True, saw_simulation_score=False))
    return _fill(keep)


# ----------------------------------------------------------------------------------------------------------------- atlas
def _atlas_key(r: dict) -> tuple[str, str]:
    """Exam 1's key (PREREG v2 L8): the line ID upper-cased without spaces, and headless or intact."""
    line = re.sub(r"\s+", "", str((r.get("driver_lines") or [r.get("name_in_paper", "")])[0])).upper()
    return line, ("headless" if r.get("preparation") == "headless" else "intact")


def atlas_sides() -> tuple[dict[str, dict], list[tuple[str, str]]]:
    """Coder A's and coder B's records keyed as exam 1 (a duplicate key keeps the first record_id); disputed = a key coded by one coder
    only, or with any leg field different."""
    sides = {}
    for tag in ("A", "B"):
        by = {}
        for _, r in sorted(_session_records(f"a5-atlas-{tag}"), key=lambda x: str(x[1].get("record_id"))):
            by.setdefault(_atlas_key(r), r)
        sides[tag] = by
    keys = sorted(set(sides["A"]) | set(sides["B"]))
    disputed = [k for k in keys if k not in sides["A"] or k not in sides["B"] or any(sides["A"][k].get(f) != sides["B"][k].get(f) for f in LEGS)]
    return sides, disputed


def final_atlas_records() -> tuple[list[dict], dict]:
    """Agreed keys: coder A's record; disputed keys: the adjudicator's (a5-atlas-C), else dropped (logged). Mapped to types by exam 1's
    locked atlas map with exam 1's rule (a line mapped to two or more types -> multi_dn)."""
    import labels2_collect as L2C  # noqa: PLC0415  (frozen: the single-reading atlas map of exam 1)

    sides, disputed = atlas_sides()
    adj = {}
    for _, r in sorted(_session_records("a5-atlas-C"), key=lambda x: str(x[1].get("record_id"))):
        adj.setdefault(_atlas_key(r), r)
    amap, mlog = L2C.atlas_map(set())
    out, log = [], {"agreed": 0, "adjudicated": 0, "dropped_disputed_without_adjudication": [], "map": mlog}
    for k in sorted(set(sides["A"]) | set(sides["B"])):
        if k in disputed:
            r = adj.get(k)
            if r is None:
                log["dropped_disputed_without_adjudication"].append(":".join(k))
                continue
            log["adjudicated"] += 1
        else:
            r = sides["A"][k]
            log["agreed"] += 1
        types, conf, basis = amap.get(k[0], ([], "low", ""))
        for t in (types or ["UNMAPPED"]):
            rr = dict(r, exp_id=f"atlas5:{k[0]}:{k[1]}:{t}", manc_type=t, mapping_confidence=conf if types else "low",
                      mapping_basis=f"atlas line map: {basis}"[:300], quote_verified=True, saw_simulation_score=False, source_kind="atlas")
            if len(types) > 1:
                rr["line_specificity"] = "multi_dn"
                rr["other_cell_types"] = sorted(set(rr.get("other_cell_types") or []) | (set(types) - {t}))
            out.append(rr)
    return _fill(out), log


# -------------------------------------------------------------------------------------------------------------- labels
def exam1_labels() -> pd.DataFrame:
    return pd.read_csv(LAB2 / "type_labels.csv", dtype={"manc_type": str}).set_index("manc_type")


def scope_of(t: str, ex1: pd.DataFrame) -> str | None:
    """L4: exam 1's scope for a type with an exam 1 front label (headless if its best preparation is headless, else intact); None if none."""
    if t in ex1.index and ex1.loc[t, "front"] in ("yes", "no", "unclear", "conflicting"):
        return "headless" if ex1.loc[t, "best_preparation"] == "headless" else "intact"
    return None


def _labels(recs: list[dict], types: list[str]) -> dict[tuple[str, str], str]:
    out = {}
    for scope, flt in SCOPES.items():
        tl = AGG.type_labels(recs, flt=flt, type_list=types).set_index("manc_type")
        for t in types:
            out[(t, scope)] = tl.loc[t, "front"] if t in tl.index else "not_assessed"
    return out


def reader_labels() -> tuple[pd.DataFrame, list[dict], list[dict]]:
    """L3: reader A's and B's labels per audited type and scope, each on its own counted records plus the final atlas records."""
    types = _assignment()["audited"]["all"]
    recs = counted(reader_records()[0])
    atlas, _ = final_atlas_records()
    la = _labels([r for r in recs if r.get("reader") == "A"] + atlas, types)
    lb = _labels([r for r in recs if r.get("reader") == "B"] + atlas, types)
    rows = [{"manc_type": t, "scope": sc, "A": la[(t, sc)], "B": lb[(t, sc)]} for t in types for sc in SCOPES]
    return pd.DataFrame(rows), recs, atlas


def disputed_types() -> list[str]:
    """L3: types whose reader labels differ at the scope that matters (exam 1's scope; either scope for a type without an exam 1 label)."""
    rl, _, _ = reader_labels()
    ex1 = exam1_labels()
    out = []
    for t, g in rl.groupby("manc_type"):
        sc = scope_of(t, ex1)
        g = g.set_index("scope")
        scopes = [sc] if sc else list(SCOPES)
        if any(g.loc[s, "A"] != g.loc[s, "B"] for s in scopes):
            out.append(t)
    return sorted(out)


def labels() -> None:
    """L3: audited labels (common label where A and B agree; else the consensus on the adjudicator's counted records plus the final atlas
    records), the final record set (for F1) and the logs. Written once."""
    for f in ("audited_type_labels.csv", "final_records.jsonl", "LABELS_LOG.json"):
        if (OUT / f).exists():
            raise SystemExit(f"{OUT / f} exists; written once")
    A = _assignment()["audited"]
    types = A["all"]
    rl, recs, atlas = reader_labels()
    disputed = set(disputed_types())
    d2s, corpus = AR.doi_to_slug(), {}
    adj_raw = []
    for s, r in _session_records("a5-adj-*"):
        rr = dict(r, session=s, exp_id=f"{s}:{r.get('record_id')}", reader="C")
        rr["quote_status"] = AR.quote_status(rr, corpus, d2s)
        rr["schema_errors"] = validate_record(dict(r, pass_id="pass1"))   # the record as the session wrote it (the frozen validator has no 'audit' pass)
        adj_raw.append(rr)
    adj = counted(adj_raw, pool=adj_raw + reader_records()[0])
    adj_types = {r.get("manc_type") for r in adj}
    lc = _labels(adj + atlas, types)
    rows, final = [], []
    for t in types:
        g = rl[rl["manc_type"] == t].set_index("scope")
        row = {"manc_type": t, "disputed": t in disputed, "adjudicated": t in disputed and t in adj_types}
        for sc in SCOPES:
            a, b = g.loc[sc, "A"], g.loc[sc, "B"]
            row[f"front_{sc}_A"], row[f"front_{sc}_B"] = a, b
            row[f"front_{sc}"] = a if a == b else lc[(t, sc)]
        rows.append(row)
        src = (adj + atlas) if t in disputed else (recs + atlas)
        final += [r for r in src if r.get("manc_type") == t]
    pd.DataFrame(rows).to_csv(OUT / "audited_type_labels.csv", index=False, lineterminator="\n", mode="x")
    with open(OUT / "final_records.jsonl", "x", encoding="utf-8", newline="\n") as fh:
        for r in final:
            fh.write(json.dumps({k: v for k, v in r.items() if k != "schema_errors"}, sort_keys=True) + "\n")
    raw, _ = reader_records()
    qs = pd.Series([r["quote_status"] for r in raw]).value_counts().to_dict() if raw else {}
    _, alog = final_atlas_records()
    log = {"n_reader_records": len(raw), "quote_status": qs, "schema_invalid": sum(1 for r in raw if r["schema_errors"]), "n_counted": len(recs),
           "n_atlas_final_records": len(atlas), "atlas": alog, "disputed_types": sorted(disputed), "n_adjudicator_records": len(adj_raw),
           "disputed_without_adjudicator_records": sorted(disputed - adj_types), "breaching_sessions_excluded": sorted(_breaching())}
    AR._write_once(OUT / "LABELS_LOG.json", json.dumps(log, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: v for k, v in log.items() if k != "atlas"}, indent=1, default=str))


# ------------------------------------------------------------------------------------------------------- verification / errors
def _exam1_behind(t: str) -> list[dict]:
    """Exam 1's records behind its front label at its scope: eligible (frozen), front value yes/no/unclear, after the frozen tiers."""
    recs = [r for r in AR.exam1_records() if r.get("manc_type") == t and AGG.eligible(r) and r.get("front_leg_rhythm") in ("yes", "no", "unclear")]
    return AGG._tier(recs) if recs else []


def verification_rows() -> list[dict]:
    """L4 (b): for primary-set types whose audited label at exam 1's scope is not yes or no, exam 1's records behind the label, without
    any leg field."""
    A = _assignment()["audited"]
    aud = pd.read_csv(OUT / "audited_type_labels.csv", dtype={"manc_type": str}).set_index("manc_type")
    ex1 = exam1_labels()
    rows = []
    for t in A["primary_census"]:
        sc = scope_of(t, ex1)
        if aud.loc[t, f"front_{sc}"] in ("yes", "no"):
            continue
        for r in _exam1_behind(t):
            rows.append({"exp_id": r["exp_id"], "doi": r["doi"], "source_locator": r.get("source_locator", ""), "driver_lines": ";".join(r.get("driver_lines") or []),
                         "name_in_paper": r.get("name_in_paper", ""), "quote": r.get("quote", ""), "preparation": r.get("preparation", ""), "manc_type": t})
    return rows


def _verifier_values() -> dict[str, str]:
    out = {}
    br = _breaching()
    for sd in sorted((OUT / "sessions").glob("a5-verify[12]-*")):
        if sd.name in br or not (sd / "verification.csv").exists():
            continue
        for row in csv.DictReader(open(sd / "verification.csv", encoding="utf-8")):
            v = (row.get("front_leg_rhythm") or "").strip().lower()
            if v and row.get("exp_id") and row["exp_id"] not in out:      # round 1 first; round 2 fills only what is missing
                out[row["exp_id"]] = v
    return out


def _unanimity(vals: list[str]) -> str:
    v = {x for x in vals if x in ("yes", "no", "unclear")}
    if not v:
        return "not_assessed"
    return "yes" if v == {"yes"} else "no" if v == {"no"} else "conflicting" if {"yes", "no"} <= v else "unclear"


def clopper_pearson(x: int, n: int, a: float = 0.05) -> list[float]:
    from scipy.stats import beta  # noqa: PLC0415

    return [0.0 if x == 0 else float(beta.ppf(a / 2, x, n - x + 1)), 1.0 if x == n else float(beta.ppf(1 - a / 2, x + 1, n - x))]


def _by_design(types: list[str], ex1: pd.DataFrame) -> dict:
    """L5: audited types whose exam 1 front label the frozen tiers decide (unanimity over all eligible records would differ), and whose
    label the sighting exclusion decides (the frozen consensus with sightings allowed would differ)."""
    allr = AR.exam1_records()
    tiers, sight = [], []
    for t in types:
        if t not in ex1.index:
            continue
        lab = ex1.loc[t, "front"]
        el = [r for r in allr if r.get("manc_type") == t and AGG.eligible(r)]
        alt = _unanimity([r.get("front_leg_rhythm") for r in el])
        if el and alt != lab:
            tiers.append({"manc_type": t, "exam1": lab, "without_tiers": alt})
        withs = [dict(r, saw_simulation_score=False) for r in allr if r.get("manc_type") == t]
        tl = AGG.type_labels(withs, type_list=[t]).set_index("manc_type")
        s = tl.loc[t, "front"] if t in tl.index else "not_assessed"
        if s != lab:
            sight.append({"manc_type": t, "exam1": lab, "with_sightings": s})
    return {"decided_by_tiers": tiers, "decided_by_sighting_exclusion": sight}


def errors() -> None:
    """L4-L6: the comparison with exam 1, the error rates (sample of 15, census of 39; atlas-only and other; strict and lenient), the
    by-design counts and the errata. Written once."""
    for f in ("comparison_with_exam1.csv", "ERROR_RATES.json"):
        if (OUT / f).exists():
            raise SystemExit(f"{OUT / f} exists; written once")
    A = _assignment()["audited"]
    ex1 = exam1_labels()
    aud = pd.read_csv(OUT / "audited_type_labels.csv", dtype={"manc_type": str}).set_index("manc_type")
    ver = _verifier_values()
    allr = AR.exam1_records()
    unread_set = set(AR.unread_types())
    rows = []
    for t in A["all"]:
        sc = scope_of(t, ex1)
        if sc is None:
            continue
        e1 = ex1.loc[t, "front"]
        au = aud.loc[t, f"front_{sc}"]
        el = [r for r in allr if r.get("manc_type") == t and AGG.eligible(r)]
        atlas_only = bool(el) and all(str(r.get("doi", "")).lower() == AR.ATLAS_DOI for r in el)
        vlab = None
        if au not in ("yes", "no"):
            vals = [ver.get(r["exp_id"], "") for r in _exam1_behind(t)]
            vlab = _unanimity(vals) if any(vals) else "not_verified"
        unread = t in unread_set                                          # L4 (c): a relevant source never given a disposition
        err = (au in ("yes", "no") and au != e1) or (au not in ("yes", "no") and vlab != e1) or unread
        rows.append({"manc_type": t, "exam1_front": e1, "exam1_best_preparation": ex1.loc[t, "best_preparation"], "scope": sc, "audited": au,
                     "reader_A": aud.loc[t, f"front_{sc}_A"], "reader_B": aud.loc[t, f"front_{sc}_B"], "disputed": bool(aud.loc[t, "disputed"]),
                     "verifier": vlab or "", "unread": unread, "error": bool(err), "strict_differs": au != e1, "yes_no_flip": {au, e1} == {"yes", "no"},
                     "atlas_only": atlas_only, "in_sample": t in A["random_sample"], "in_census": t in A["primary_census"], "exposed": t in A["exposed"]})
    cmp_ = pd.DataFrame(rows)
    cmp_.to_csv(OUT / "comparison_with_exam1.csv", index=False, lineterminator="\n", mode="x")

    def rate(d: pd.DataFrame) -> dict:
        n, e = len(d), int(d["error"].sum())
        return {"n": n, "errors": e, "rate": e / n if n else None, "ci95": clopper_pearson(e, n) if n else None, "strict": int(d["strict_differs"].sum()),
                "lenient_flips": int(d["yes_no_flip"].sum()), "types_with_error": sorted(d.loc[d["error"], "manc_type"])}

    out = {"rule": "PREREG v5 L4-L6"}
    for name, sel in (("sample_15", cmp_["in_sample"]), ("census_39", cmp_["in_census"])):
        d = cmp_[sel]
        out[name] = {"all": rate(d), "atlas_only": rate(d[d["atlas_only"]]), "other": rate(d[~d["atlas_only"]])}
    s, c = out["sample_15"]["all"], out["census_39"]["all"]
    out["above_threshold"] = {"sample": s["rate"] is not None and s["rate"] > 0.10, "census": c["rate"] is not None and c["rate"] > 0.10}
    out["by_design_L5"] = _by_design(sorted(cmp_["manc_type"]), ex1)
    out["errata_exposed"] = json.loads(cmp_[cmp_["exposed"] & cmp_["strict_differs"]][["manc_type", "exam1_front", "scope", "audited"]].to_json(orient="records"))
    AR._write_once(OUT / "ERROR_RATES.json", json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: out[k] for k in ("sample_15", "census_39", "above_threshold")}, indent=1, default=str))
    print(cmp_[cmp_["strict_differs"]][["manc_type", "exam1_front", "scope", "audited", "reader_A", "reader_B", "verifier", "error", "exposed"]].to_string())


if __name__ == "__main__":
    cmd = sys.argv[1:2]
    if cmd == ["disputes"]:
        sides, dis = atlas_sides()
        print(json.dumps({"atlas_keys_A": len(sides["A"]), "atlas_keys_B": len(sides["B"]), "atlas_disputed": len(dis)}, indent=1))
    elif cmd == ["types-disputed"]:
        print(json.dumps(disputed_types(), indent=1))
    elif cmd == ["labels"]:
        labels()
    elif cmd == ["errors"]:
        errors()
    else:
        raise SystemExit(__doc__)
