"""Collect, prepare and assemble labels v2 (LABEL SIDE; never reads predictions). PREREG v2 Part L; LOG L51+.

Run 1's frozen label code is reused unchanged by pointing its folders at v2 (`labels_collect.collect` for copying and
validating, `aggregate.dedupe_pass1 / merge_passes / type_labels`, `agreement.agreement`, `labels_prepare.add_siblings`).
New here: atlas pairing by line ID with the type map applied by script (C4), dispositions and reassignment (L5), search leads
and recall rounds (L9), second-reading and adjudication batches of at most 6 sources, the verification sample (L11), the
line-specificity fill (L10) and `v1_vs_v2.md`. The orchestrator reads only counts printed by these commands.

    labels2_collect.py registry                 # registry v2 from v1.1 sources, every run-1 record DOI and the leads
    labels2_collect.py readers [--round N]      # reader specs (<= 6 sources per session) for registered, downloaded, unread DOIs
    labels2_collect.py collect                  # copy + validate every v2 session's outputs (frozen collect)
    labels2_collect.py leads --round N          # new DOIs from search round N -> registry; recall fraction
    labels2_collect.py reassign                 # sources without a disposition -> new reader specs (<= 2 attempts)
    labels2_collect.py second                   # second-reading specs + quotes kept aside
    labels2_collect.py adjudication             # disagreements -> adjudication specs
    labels2_collect.py verify-sample            # 30 random final records -> verification spec
    labels2_collect.py finalize                 # merge, fill, consensus, agreement, recall, tables
    labels2_collect.py v1-vs-v2
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "ledger" / "src"))
import labels_collect as LC  # noqa: E402  (frozen; module paths are re-pointed at v2 below)
import labels_prepare as LP  # noqa: E402  (frozen; add_siblings, ID_FIELDS)
import labels2_rooms as R2  # noqa: E402
from brainir_ledger.labels import aggregate as AGG  # noqa: E402
from brainir_ledger.labels.agreement import agreement  # noqa: E402

LAB = REPO / "research" / "ledger" / "labels_v2"
RAW = LAB / "raw"
WORK = LAB / "work"
SPECS = WORK / "specs"
KIT = REPO / "research" / "ledger" / "kit_v2"
SOURCES = R2.SOURCES
ATLAS_DOI = "10.7554/elife.34275"
NAMIKI_DOI = "10.7554/elife.34272"
CATALOGUE_DOI = "10.7554/elife.107450"
DEDICATED_DOIS = {"10.1038/s41586-026-11195-y", "10.1101/2025.09.12.675944", "10.64898/2026.04.29.721658"}
FAMILY_PRIORITY = ["walking_stopping", "grooming", "steering", "escape_landing", "driver_line_resources", "recent_broad"]
V1_FAMILY = {"catalogue": "driver_line_resources", "pugliese_dedicated": "dedicated"}
VERIFY_SEED, ADJ_SEED, SPOT_SEED = 20261203, 20261206, 20261126

# re-point the frozen collector at v2
LC.LAB, LC.RAW, LC.KIT, LC.ROOMS = LAB, RAW, KIT, R2.ROOMS


def norm_doi(d: str) -> str:
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    return re.sub(r"^(10\.7554/elife\.\d+)\.\d+$", r"\1", d)


def slug(doi: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", norm_doi(doi)).strip("_")


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _spec(spec: dict) -> Path:
    SPECS.mkdir(parents=True, exist_ok=True)
    p = SPECS / f"{spec['session']}.json"
    p.write_text(json.dumps(spec, indent=1) + "\n")
    return p


# --------------------------------------------------------------------------------------------------------- registry
def registry() -> None:
    reg: dict[str, dict] = {}

    def add(doi, family, prov):
        d = norm_doi(doi)
        if not d.startswith("10."):
            return
        r = reg.setdefault(d, {"doi": d, "slug": slug(d), "families": set(), "provenance": set()})
        if family:
            r["families"].add(family)
        r["provenance"].add(prov)

    v11 = pd.read_csv(REPO / "research" / "ledger" / "labels_v1_1" / "sources.csv")
    dcol = "doi" if "doi" in v11.columns else v11.columns[0]
    for _, row in v11.iterrows():
        fams = {V1_FAMILY.get(s.split("-", 1)[1], s.split("-", 1)[1]) for s in str(row.get("sessions") or "").split(";") if s.startswith("pass1-")}
        for f in fams or {None}:
            add(row[dcol], f, "v1.1_registry")
    for p in sorted((REPO / "research" / "ledger" / "labels" / "raw").glob("*/*/records.valid.jsonl")):
        sess = p.parent.name
        fam = V1_FAMILY.get(sess.split("-", 1)[1], sess.split("-", 1)[1]) if sess.startswith("pass1-") else None
        for r in _jsonl(p):
            add(r.get("doi", ""), fam, f"run1:{sess}")
    for d in (ATLAS_DOI, NAMIKI_DOI, CATALOGUE_DOI):
        add(d, None, "atlas_or_mapping_source")
    for d in DEDICATED_DOIS:
        add(d, "dedicated", "dedicated_source")
    rows = []
    for d, r in sorted(reg.items()):
        if d in DEDICATED_DOIS:
            fam = "dedicated"
        elif d == ATLAS_DOI:
            fam = "atlas"
        else:
            fs = [f for f in FAMILY_PRIORITY if f in r["families"]]
            fam = fs[0] if fs else "recent_broad"
        rows.append({"doi": d, "slug": r["slug"], "family": fam, "provenance": ";".join(sorted(r["provenance"])), "round": 0})
    _write_csv(WORK / "registry.csv", rows, ["doi", "slug", "family", "provenance", "round"])
    print(json.dumps({"registered": len(rows), "by_family": dict(collections.Counter(r["family"] for r in rows))}))


def _registry() -> pd.DataFrame:
    return pd.read_csv(WORK / "registry.csv", dtype=str).fillna("")


def _downloaded(s: str) -> bool:
    return (SOURCES / s / "meta.json").exists()


# --------------------------------------------------------------------------------------------------------- readers
def readers(round_: int) -> None:
    reg = _registry()
    reg = reg[reg["round"].astype(int) == round_]
    assigned = set()
    for m in sorted(R2.MANIFESTS.glob("*.json")):
        assigned |= set(json.loads(m.read_text()).get("sources") or [])
    todo = reg[(~reg["slug"].isin(assigned)) & (reg["family"] != "atlas")]
    todo = todo[[_downloaded(s) for s in todo["slug"]]]
    specs = []
    for fam, g in todo.groupby("family"):
        slugs = list(g["slug"])
        for i in range(0, len(slugs), 6):
            n = len(list(SPECS.glob(f"pass1-{fam}-r{round_}-*.json"))) + 1
            specs.append(_spec({"session": f"pass1-{fam}-r{round_}-{n:02d}", "kind": "reader", "family": fam, "pass_id": "pass1",
                                "sources": slugs[i:i + 6]}))
    print(json.dumps({"reader_specs": len(specs), "sources": int(len(todo))}))


def atlas_ids() -> None:
    """PREREG v2 L7: the atlas line IDs from the kit's Cande rows (line IDs only, read by OCR in run 1); no paper is opened."""
    rows = [r for r in csv.DictReader(open(KIT / "driver_lines.csv", encoding="utf-8")) if norm_doi(r["source_doi"]) == ATLAS_DOI]
    ids = sorted({re.sub(r"\s+", "", r["line_id"]).upper() for r in rows if r["line_id"].strip()})
    _write_csv(WORK / "atlas" / "atlas_line_ids.csv", [{"line_id": x} for x in ids], ["line_id"])
    src_map = [slug(ATLAS_DOI), slug(NAMIKI_DOI), slug(CATALOGUE_DOI)]
    inp = {"atlas_line_ids.csv": str(WORK / "atlas" / "atlas_line_ids.csv")}
    _spec({"session": "atlas-map", "kind": "atlas_map", "pass_id": "atlas_map", "sources": src_map, "inputs": inp})
    _spec({"session": "atlas-codeA", "kind": "atlas_code", "pass_id": "pass1", "sources": [slug(ATLAS_DOI)], "inputs": inp})
    _spec({"session": "atlas-codeB", "kind": "atlas_code", "pass_id": "pass1", "sources": [slug(ATLAS_DOI)], "inputs": inp})
    print(json.dumps({"atlas_line_ids": len(ids), "specs": ["atlas-map", "atlas-codeA", "atlas-codeB"]}))


# --------------------------------------------------------------------------------------------------------- collect / leads / reassign
def collect() -> None:
    LC.collect()


def leads(round_: int) -> None:
    reg = _registry()
    known = set(reg["doi"])
    units_before = _units_known()
    new_rows, units_round = [], set()
    breach = _breaching() if (LAB / "transcript_audit.json").exists() else set()
    for sd in sorted((RAW / "search").glob(f"search-*-r{round_}")):
        if sd.name in breach:
            continue
        rows, _ = LC.read_csv_rows(sd / "leads.csv", ["doi", "title", "year", "name_in_paper", "manc_type", "family_hint", "locator"])
        for r in rows:
            d = norm_doi(r.get("doi", ""))
            if not d.startswith("10."):
                continue
            if r.get("manc_type"):
                units_round.add((d, r["manc_type"].strip()))
            if d not in known and d not in DEDICATED_DOIS:
                fam = r.get("family_hint") if r.get("family_hint") in FAMILY_PRIORITY else "recent_broad"
                new_rows.append({"doi": d, "slug": slug(d), "family": fam, "provenance": f"search_round_{round_}", "round": round_})
                known.add(d)
    if new_rows:
        reg = pd.concat([reg, pd.DataFrame(new_rows)], ignore_index=True)
        reg.to_csv(WORK / "registry.csv", index=False, lineterminator="\n")
    new_units = units_round - units_before
    (WORK / f"recall_units_round_{round_}.json").write_text(json.dumps(sorted(units_round)) + "\n")
    out = {"round": round_, "new_dois": len(new_rows), "units_in_round": len(units_round), "new_units": len(new_units),
           "units_known_before": len(units_before), "fraction_new": (len(new_units) / len(units_before)) if units_before else None}
    (WORK / f"recall_round_{round_}.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out))


def _units_known() -> set:
    u = set()
    for sd in sorted((RAW / "pass1").glob("*")):
        u |= {(norm_doi(r["doi"]), r["manc_type"]) for r in _jsonl(sd / "records.valid.jsonl")}
    for p in sorted(WORK.glob("recall_units_round_*.json")):
        u |= {tuple(x) for x in json.loads(p.read_text())}
    return u


def reassign() -> None:
    specs = []
    for m in sorted(R2.MANIFESTS.glob("*.json")):
        man = json.loads(m.read_text())
        if man["kind"] != "reader" or any(R2._alive(r["pid"]) for r in man["runs"]):
            continue
        rows, _ = LC.read_csv_rows(Path(man["room"]) / "out" / "dispositions.csv", ["doi", "disposition", "n_records", "reason"])
        done = {norm_doi(r["doi"]) for r in rows if r.get("disposition") in ("records", "no_qualifying_experiment", "unreachable")}
        missing = [s for s in man.get("sources") or [] if norm_doi(json.loads((SOURCES / s / "meta.json").read_text())["doi"]) not in done]
        attempt = int(re.search(r"-a(\d)$", man["session"]).group(1)) if re.search(r"-a(\d)$", man["session"]) else 0
        if missing and attempt < 2:
            base = re.sub(r"-a\d$", "", man["session"])
            specs.append(_spec({"session": f"{base}-a{attempt + 1}", "kind": "reader", "family": man["family"], "pass_id": "pass1",
                                "sources": missing}))
    print(json.dumps({"reassigned_sessions": len(specs)}))


# --------------------------------------------------------------------------------------------------------- atlas
def atlas_map() -> dict[str, tuple[list[str], str, str]]:
    rows, _ = LC.read_csv_rows(RAW / "atlas_map" / "atlas-map" / "atlas_line_map.csv", ["line_id", "manc_types", "mapping_confidence", "mapping_basis"])
    kt = LC.known_types()
    out = {}
    for r in rows:
        types = sorted({t.strip() for t in r.get("manc_types", "").split(";") if t.strip() in kt})
        out[r["line_id"].strip().upper()] = (types, r.get("mapping_confidence") or "low", r.get("mapping_basis") or "")
    return out


def _atlas_side(session: str, use_snapshot: bool) -> list[dict]:
    sd = RAW / "pass1" / session
    recs = _jsonl(sd / "records.valid.jsonl")
    if use_snapshot and (sd / "phaseA_snapshot" / "records.jsonl").exists():
        kt = LC.known_types()
        good, _ = LC.validate_lines((sd / "phaseA_snapshot" / "records.jsonl").read_text().splitlines(), kt, session, "pass1")
        recs = good
    return recs


def atlas_pairs() -> tuple[list[dict], list[dict], dict, dict]:
    """Coder A = first reading, coder B = second reading; keyed by line ID; expanded to one record per mapped type."""
    amap = atlas_map()
    sides = {}
    for tag, sess in (("A", "atlas-codeA"), ("B", "atlas-codeB")):
        by_line = {}
        for r in sorted(_atlas_side(sess, tag == "B"), key=lambda x: str(x.get("record_id"))):
            line = re.sub(r"\s+", "", str((r.get("driver_lines") or [r.get("name_in_paper", "")])[0])).upper()
            by_line.setdefault(line, r)
        sides[tag] = by_line
    p1, p2, info = [], [], {"lines_A": len(sides["A"]), "lines_B": len(sides["B"]), "mapped_lines": 0}
    for line, ra in sorted(sides["A"].items()):
        types, conf, basis = amap.get(line, ([], "low", ""))
        if types:
            info["mapped_lines"] += 1
        for t in (types or ["UNMAPPED"]):
            for tag, src, dst in (("A", ra, p1), ("B", sides["B"].get(line), p2)):
                if src is None:
                    continue
                r = dict(src, exp_id=f"atlas:{line}:{t}", manc_type=t, mapping_confidence=conf if types else "low",
                         mapping_basis=f"atlas line map: {basis}"[:300])
                if len(types) > 1:
                    r["line_specificity"] = "multi_dn"
                    r["other_cell_types"] = sorted(set(r.get("other_cell_types") or []) | (set(types) - {t}))
                dst.append(r)
    qc = {}
    rows, _ = LC.read_csv_rows(RAW / "pass1" / "atlas-codeB" / "quote_checks.csv", ["exp_id", "quote_found", "where", "comment"])
    for row in rows:
        v = row.get("quote_found", "").strip().lower()
        line = row["exp_id"].split(":")[1].upper() if row["exp_id"].startswith("atlas:") else row["exp_id"].upper()
        for t in (amap.get(line, ([], "", ""))[0] or ["UNMAPPED"]):
            qc[f"atlas:{line}:{t}"] = True if v in LC.TRUE_WORDS else (False if v in LC.FALSE_WORDS else None)
    return p1, p2, qc, info


# --------------------------------------------------------------------------------------------------------- second reading / adjudication
def _breaching() -> set[str]:
    p = LAB / "transcript_audit.json"
    if not p.exists():
        raise SystemExit("run ledger/scripts/labels2_audit.py first")
    return {r["session"] for r in json.loads(p.read_text()) if r.get("breach")}


V2_ORDER = ["atlas", "driver_line_resources", "grooming", "walking_stopping", "steering", "escape_landing", "recent_broad", "dedicated"]


def _fam_of_session(s: str) -> str:
    m = re.match(r"pass1-([a-z_]+?)-r\d", s)
    return m.group(1) if m else s


def dedupe_v2(recs: list[dict]) -> tuple[list[dict], list[dict]]:
    """PREREG v2 L8: identical frozen content signature -> kept once, from the session earliest in V2_ORDER (ties: name)."""
    def rank(r):
        s = r["exp_id"].split(":", 1)[0]
        f = _fam_of_session(s)
        return (V2_ORDER.index(f) if f in V2_ORDER else len(V2_ORDER), s, r["exp_id"])
    seen, kept, dropped = {}, [], []
    for r in sorted(recs, key=rank):
        sig = AGG.content_signature(r)
        if sig in seen:
            dropped.append({"dropped": r["exp_id"], "kept": seen[sig]})
            continue
        seen[sig] = r["exp_id"]
        kept.append(r)
    return kept, dropped


def _pass1_generic() -> list[dict]:
    breach = _breaching()
    recs = []
    for sd in sorted((RAW / "pass1").glob("pass1-*")):
        if sd.name not in breach:
            recs += _jsonl(sd / "records.valid.jsonl")
    kept, _ = dedupe_v2(recs)
    return kept


NEUTRAL_WORDS = ["walk", "walking", "stop", "stopping", "halt", "halting", "groom", "grooming", "turn", "turning", "steer", "steering",
                 "escape", "takeoff", "take-off", "jump", "landing", "flight", "backward", "forward", "rhythm", "rhythmic", "locomotion",
                 "leg", "legs", "posture", "freeze", "freezing"]
NEUTRAL_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(NEUTRAL_WORDS, key=len, reverse=True)) + r")\b", re.I)


def neutral(s: str) -> str:
    return NEUTRAL_RE.sub("[...]", s or "")


def second() -> None:
    p1 = _pass1_generic()
    done = {x.stem for x in SPECS.glob("pass2-*.json")}
    covered = set()
    for f in done:
        covered |= set(json.loads((SPECS / f"{f}.json").read_text()).get("exp_ids") or [])
    todo = [r for r in p1 if r["exp_id"] not in covered]
    p1_type = {r["exp_id"]: r["manc_type"] for r in todo}
    rows = LP.add_siblings([{k: (";".join(r[k]) if isinstance(r.get(k), list) else r.get(k, "")) for k in LP.ID_FIELDS if k not in ("sibling_index", "n_siblings")}
                            for r in todo], p1_type)
    for r in rows:
        r["source_locator"], r["stimulation"] = neutral(r.get("source_locator", "")), neutral(r.get("stimulation", ""))
    by_doi = collections.defaultdict(list)
    for r in rows:
        by_doi[norm_doi(r["doi"])].append(r)
    recs = {r["exp_id"]: r for r in todo}
    fam_of = {norm_doi(d): f for d, f in zip(_registry()["doi"], _registry()["family"])}
    groups = collections.defaultdict(list)
    for d in sorted(by_doi):
        groups["dedicated" if fam_of.get(d) == "dedicated" else "general"].append(d)
    n_specs = 0
    for grp, dois in groups.items():
        for i in range(0, len(dois), 6):
            batch = dois[i:i + 6]
            exps = [r for d in batch for r in by_doi[d]]
            n = len(list(SPECS.glob(f"pass2-{grp}-*.json"))) + 1
            name = f"pass2-{grp}-{n:02d}"
            ex_path, q_path = WORK / "second" / name / "experiments_to_label.csv", WORK / "second" / name / "quotes_to_verify.csv"
            _write_csv(ex_path, exps, LP.ID_FIELDS)
            _write_csv(q_path, [{"exp_id": r["exp_id"], "doi": recs[r["exp_id"]]["doi"], "source_locator": recs[r["exp_id"]]["source_locator"],
                                 "quote": recs[r["exp_id"]]["quote"]} for r in exps], ["exp_id", "doi", "source_locator", "quote"])
            _spec({"session": name, "kind": "second", "family": "dedicated" if grp == "dedicated" else None, "pass_id": "pass2",
                   "sources": [slug(d) for d in batch], "inputs": {"experiments_to_label.csv": str(ex_path)},
                   "quotes": str(q_path), "exp_ids": [r["exp_id"] for r in exps]})
            n_specs += 1
    print(json.dumps({"second_reading_specs": n_specs, "experiments": len(todo)}))


def _pass2_records() -> list[dict]:
    breach = _breaching()
    out = []
    for sd in sorted((RAW / "pass2").glob("pass2-*")):
        if sd.name not in breach:
            out += _jsonl(sd / "records.valid.jsonl")
    return out


def adjudication() -> None:
    p1 = _pass1_generic()
    p2 = {r["exp_id"]: r for r in _pass2_records()}
    a1, a2, _, _ = atlas_pairs() if (RAW / "pass1" / "atlas-codeA").exists() else ([], [], {}, {})
    p2.update({r["exp_id"]: r for r in a2})
    rng = np.random.default_rng(ADJ_SEED)
    sib = {}
    for f in sorted((WORK / "second").glob("*/experiments_to_label.csv")):
        for row in csv.DictReader(open(f, encoding="utf-8")):
            sib[row["exp_id"]] = row
    groups = collections.defaultdict(list)
    fam_of = dict(zip(_registry()["doi"], _registry()["family"]))
    for a in p1 + a1:
        b = p2.get(a["exp_id"])
        if b is None:
            continue
        for f in AGG.COMPARED_FIELDS:
            if a.get(f) != b.get(f):
                ra, rb = (a.get(f), b.get(f)) if rng.random() < 0.5 else (b.get(f), a.get(f))
                g = "dedicated" if fam_of.get(norm_doi(a["doi"])) == "dedicated" else "general"
                groups[g].append({**{k: (";".join(a[k]) if isinstance(a.get(k), list) else a.get(k, "")) for k in LP.ID_FIELDS
                                     if k not in ("sibling_index", "n_siblings")}, "sibling_index": sib.get(a["exp_id"], {}).get("sibling_index", 1),
                                  "n_siblings": sib.get(a["exp_id"], {}).get("n_siblings", 1),
                                  "field": f, "reading_A": json.dumps(ra), "reading_B": json.dumps(rb)})
    n_specs = 0
    for g, rows in groups.items():
        dois = sorted({norm_doi(r["doi"]) for r in rows})
        for i in range(0, len(dois), 6):
            batch = set(dois[i:i + 6])
            name = f"adjudication-{g}-{i // 6 + 1:02d}"
            path = WORK / "adjudication" / name / "disagreements.csv"
            _write_csv(path, [r for r in rows if norm_doi(r["doi"]) in batch], LP.ID_FIELDS + ["field", "reading_A", "reading_B"])
            _spec({"session": name, "kind": "adjudication", "family": "dedicated" if g == "dedicated" else None, "pass_id": "adjudication",
                   "sources": [slug(d) for d in sorted(batch)], "inputs": {"disagreements.csv": str(path)}})
            n_specs += 1
    print(json.dumps({"adjudication_specs": n_specs, "disputed_fields": {g: len(r) for g, r in groups.items()}}))


# --------------------------------------------------------------------------------------------------------- merge / finalize
def _quote_checks_generic() -> dict:
    qc = {}
    for sd in sorted((RAW / "pass2").glob("pass2-*")):
        rows, _ = LC.read_csv_rows(sd / "quote_checks.csv", ["exp_id", "quote_found", "where", "comment"])
        for row in rows:
            v = row.get("quote_found", "").strip().lower()
            qc[row["exp_id"]] = True if v in LC.TRUE_WORDS else (False if v in LC.FALSE_WORDS else None)
    return qc


def merged() -> tuple[list[dict], dict, list[dict], list[dict]]:
    p1, p2 = _pass1_generic(), _pass2_records()
    qc = _quote_checks_generic()
    nf, _ = LC.not_found()
    a1, a2, aqc, ainfo = atlas_pairs() if (RAW / "pass1" / "atlas-codeA").exists() else ([], [], {}, {})
    adj = []
    breach = _breaching()
    for sd in sorted((RAW / "adjudication").glob("adjudication-*")):
        if sd.name not in breach:
            adj += _jsonl(sd / "records.valid.jsonl")
    final, log = AGG.merge_passes(p1 + a1, p2 + a2, adj, {**qc, **aqc}, nf)
    log["atlas"] = ainfo
    return final, log, p1 + a1, p2 + a2


def line_spec_fill(final: list[dict]) -> list[dict]:
    """PREREG v2 L10 (literal): only `unknown` records with a driver line in kit_v2/driver_lines.csv; `other_cells` naming a MANC DN
    type -> multi_dn, other non-empty `other_cells` -> minor_offtarget; never `clean`; candidate-type ambiguity ignored."""
    kt = LC.known_types()
    rows = list(csv.DictReader(open(KIT / "driver_lines.csv", encoding="utf-8")))
    by_line = collections.defaultdict(list)
    for r in rows:
        by_line[r["line_id"].strip().lower()].append(r)
    log = []
    for rec in final:
        if rec.get("line_specificity") != "unknown":
            continue
        lines = [str(x).strip().lower() for x in (rec.get("driver_lines") or []) if str(x).strip()]
        hits = [r for x in lines for r in by_line.get(x, [])]
        cells = sorted({c.strip() for r in hits for c in re.split(r"[;,]", r.get("other_cells") or "") if c.strip()})
        if not cells:
            continue
        new = "multi_dn" if any(c in kt for c in cells) else "minor_offtarget"
        rec["line_specificity"] = new
        rec["other_cell_types"] = sorted(set(rec.get("other_cell_types") or []) | set(cells))
        log.append({"exp_id": rec["exp_id"], "filled": new, "cells": cells})
    return log


def finalize() -> None:
    final, log, p1, p2 = merged()
    fill_log = line_spec_fill(final)
    ex = pd.read_csv(KIT / "exposed_types.csv")
    exposed = {t for s in ex["manc_types"].dropna() for t in str(s).split(";") if t}
    ded = {r["exp_id"] for r in final if _fam_of_session(r["exp_id"].split(":", 1)[0]) == "dedicated"
           or r["exp_id"].split(":", 1)[0].startswith("pass1-dedicated")}
    elig = [r for r in final if AGG.eligible(r)]
    by_nature = sorted({r["manc_type"] for r in elig} - {r["manc_type"] for r in elig if r["exp_id"] not in ded})
    pd.DataFrame({"manc_type": by_nature, "reason": "eligible records only from dedicated sessions"}).to_csv(LAB / "exposed_v2.csv", index=False, lineterminator="\n")
    tl = AGG.type_labels(final, exposed=exposed | set(by_nature), type_list=sorted(LC.known_types()))
    ag = agreement(p1, p2)
    with open(LAB / "records.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in final:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    tl.to_csv(LAB / "type_labels.csv", index=False, lineterminator="\n")
    (LAB / "merge_log.json").write_text(json.dumps({"merge": log, "line_spec_fill": fill_log}, indent=1, default=str) + "\n")
    rng = np.random.default_rng(SPOT_SEED)
    pick = sorted(rng.choice(len(final), size=min(20, len(final)), replace=False)) if final else []
    pd.DataFrame([{k: final[i].get(k) for k in ("exp_id", "manc_type", "name_in_paper", "doi", "source_locator", "quote", "driver_lines",
                                                "preparation", "front_leg_rhythm", "middle_leg_rhythm", "hind_leg_rhythm")} for i in pick]) \
        .to_csv(LAB / "spot_check_sample.csv", index=False, lineterminator="\n")
    summary = {"n_final": len(final), "agreement": ag, "merge_counts": {k: (len(v) if isinstance(v, list) else v) for k, v in log.items()},
               "line_spec_filled": len(fill_log), "types_clear_front": int(tl["front"].isin(["yes", "no"]).sum())}
    (LAB / "agreement.json").write_text(json.dumps(summary, indent=1, default=str) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "agreement"} | {"kappa_front_all_values": ag.get("primary_field_all_values")}, default=str))


def _verify_frame() -> list[dict]:
    final = _jsonl(LAB / "records.jsonl")
    frame = sorted([r for r in final if AGG.eligible(r) and not r["exp_id"].split(":", 1)[0].startswith("pass1-dedicated")],
                   key=lambda r: r["exp_id"])
    return frame


def verify_sample() -> None:
    frame = _verify_frame()
    idx = np.random.default_rng(VERIFY_SEED).choice(len(frame), min(30, len(frame)), replace=False)
    pick = [frame[i] for i in idx]
    path = WORK / "verify" / "verify_sample.csv"
    cols = ["exp_id", "doi", "source_locator", "driver_lines", "name_in_paper", "quote"]  # no recorded value (blind, L11)
    _write_csv(path, [{k: (";".join(r[k]) if isinstance(r.get(k), list) else r.get(k, "")) for k in cols} for r in pick], cols)
    (WORK / "verify" / "verify_truth.json").write_text(json.dumps({r["exp_id"]: r["front_leg_rhythm"] for r in pick}, indent=1) + "\n")
    _spec({"session": "verify-01", "kind": "verify", "pass_id": "verify", "sources": sorted({slug(r["doi"]) for r in pick}),
           "inputs": {"verify_sample.csv": str(path)}})
    print(json.dumps({"verify_sample": len(pick), "frame": len(frame)}))


def verify_score() -> None:
    truth = json.loads((WORK / "verify" / "verify_truth.json").read_text())
    rows, _ = LC.read_csv_rows(RAW / "verify" / "verify-01" / "verification.csv", ["exp_id", "quote_found", "front_leg_rhythm", "locator", "comment"])
    got = {r["exp_id"]: r for r in rows}
    errors = [k for k, v in truth.items() if k not in got or got[k].get("front_leg_rhythm", "").strip().lower() in ("", "cannot_verify")
              or got[k]["front_leg_rhythm"].strip().lower() != str(v).lower()]
    quotes_found = sum(1 for k in truth if k in got and got[k].get("quote_found", "").strip().lower() in LC.TRUE_WORDS)
    out = {"n": len(truth), "errors": len(errors), "error_rate": len(errors) / len(truth) if truth else None, "quotes_found": quotes_found,
           "blocker": (len(errors) / len(truth) > 0.10) if truth else None}
    (LAB / "verification.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out))


def v1_vs_v2() -> None:
    v1 = _jsonl(REPO / "research" / "ledger" / "labels_v1_1" / "records.jsonl")
    v2 = _jsonl(LAB / "records.jsonl")
    key = lambda r: (norm_doi(r["doi"]), r.get("manc_type"), r.get("preparation"))  # noqa: E731
    a = {key(r): r for r in v1}
    b = {key(r): r for r in v2}
    shared = sorted(set(a) & set(b))
    out = {"v1_1_records": len(v1), "v2_records": len(v2), "shared_experiments": len(shared)}
    for f in ("front_leg_rhythm", "middle_leg_rhythm", "hind_leg_rhythm", "effect_on_walking"):
        out[f"agree_{f}"] = (sum(a[k].get(f) == b[k].get(f) for k in shared) / len(shared)) if shared else None
    (LAB / "v1_vs_v2.json").write_text(json.dumps(out, indent=1) + "\n")
    (LAB / "v1_vs_v2.md").write_text("# Labels v1.1 vs v2 (labels only)\n\nExperiments matched on (normalised DOI, MANC type, preparation).\n\n"
                                     + "\n".join(f"- {k}: {v}" for k, v in out.items()) + "\n")
    print(json.dumps(out))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["registry", "atlas-ids", "readers", "collect", "leads", "reassign", "second", "adjudication", "verify-sample",
                                    "verify-score", "finalize", "v1-vs-v2"])
    ap.add_argument("--round", type=int, default=0)
    a = ap.parse_args()
    {"registry": registry, "atlas-ids": atlas_ids, "collect": collect, "reassign": reassign, "second": second, "adjudication": adjudication,
     "verify-sample": verify_sample, "verify-score": verify_score, "finalize": finalize, "v1-vs-v2": v1_vs_v2}.get(a.cmd, lambda: None)()
    if a.cmd == "readers":
        readers(a.round)
    if a.cmd == "leads":
        leads(a.round)


if __name__ == "__main__":
    main()
