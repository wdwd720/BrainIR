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
import hashlib
import json
import re
import sys
import time
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
VER = LAB / "verify"  # PREREG v2 L11: everything the verification writes, after the labels lock (new files only)
LOCKED = REPO / "research" / "ledger" / "LOCK_labels_v2.json"
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


def _spec(spec: dict, where: Path | None = None) -> Path:
    """Write a session spec; specs are never overwritten (a rerun of a step adds new names, review M3/B5)."""
    d = where or SPECS
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{spec['session']}.json"
    if p.exists():
        raise SystemExit(f"spec {p.name} exists already; specs are never overwritten")
    p.write_text(json.dumps(spec, indent=1) + "\n")
    return p


def _unlocked(what: str) -> None:
    if LOCKED.exists():
        raise SystemExit(f"{what} refused: LOCK_labels_v2.json exists; nothing in labels v2 changes (PREREG v2 L14)")


def _free(base: str, tag: str, where: Path | None = None) -> str:
    k = 1
    while ((where or SPECS) / f"{base}-{tag}{k}.json").exists():
        k += 1
    return f"{base}-{tag}{k}"


is_dedicated = R2.is_dedicated  # the frozen audit's dedicated-source tokens (PREREG v2 L7: dedicated sources only in dedicated rooms)


# --------------------------------------------------------------------------------------------------------- registry
def registry() -> None:
    _unlocked("registry")
    if (WORK / "registry.csv").exists():
        raise SystemExit("registry.csv exists; the registry is built once (search rounds append to it)")
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
        if d in DEDICATED_DOIS or is_dedicated(d):
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


def _meta(s: str) -> dict:
    return json.loads((SOURCES / s / "meta.json").read_text())


def _specs(kinds=None, where: Path | None = None) -> list[dict]:
    kinds = (kinds,) if isinstance(kinds, str) else kinds
    out = []
    for f in sorted((where or SPECS).glob("*.json")):
        s = json.loads(f.read_text())
        if kinds is None or s.get("kind") in kinds:
            out.append(s)
    return out


def _web_slugs() -> set[str]:
    """Sources read by `reader_web` sessions (PREREG v2 C1): their second reading / adjudication get WebFetch-only flags and their
    records are outside the verification frame."""
    return {x for s in _specs("reader_web") for x in s.get("sources") or []}


# --------------------------------------------------------------------------------------------------------- readers
def readers(round_: int) -> None:
    """Reader specs (<= 6 sources per session) for registered sources of this round not yet given to a reader; sources the
    downloader marked `abstract_only` or `unreachable` go to web-enabled `reader_web` sessions; banned-host DOIs are never
    assigned (PREREG v2 C1, L7). Only reader sessions count as assigned: Namiki 2018 and the 2025 catalogue are also read by the
    atlas-map session, but get a first reading like every registered source (review B1); only the atlas is skipped."""
    _unlocked("readers")
    reg = _registry()
    reg = reg[reg["round"].astype(int) == round_]
    assigned = set()
    for m in sorted(R2.MANIFESTS.glob("*.json")):
        man = json.loads(m.read_text())
        if man["kind"] in ("reader", "reader_web"):
            assigned |= set(man.get("sources") or [])
    for s in _specs(("reader", "reader_web")):
        assigned |= set(s.get("sources") or [])
    skip = {slug(ATLAS_DOI)}
    todo = reg[(~reg["slug"].isin(assigned)) & (~reg["slug"].isin(skip))]
    todo = todo[[_downloaded(s) for s in todo["slug"]]]
    banned = sorted(s for s in todo["slug"] if _meta(s).get("banned_host") or _meta(s).get("status") == "banned_host")
    if banned:
        _write_csv(WORK / f"banned_host_sources_round_{round_}.csv", [{"slug": s} for s in banned], ["slug"])
    todo = todo[~todo["slug"].isin(banned)]
    status = {s: _meta(s).get("status") for s in todo["slug"]}
    n = 0
    for fam, g in todo.groupby("family"):
        for kind in ("reader", "reader_web"):
            slugs = [s for s in g["slug"] if (status[s] in ("unreachable", "abstract_only")) == (kind == "reader_web")]
            for i in range(0, len(slugs), 6):
                k = 1
                while (SPECS / f"pass1-{fam}-r{round_}-{k:02d}.json").exists():
                    k += 1
                batch = slugs[i:i + 6]
                if (fam == "dedicated") != all(is_dedicated(s) for s in batch):
                    raise SystemExit(f"dedicated sources must be read only in dedicated sessions: {fam} {batch}")
                _spec({"session": f"pass1-{fam}-r{round_}-{k:02d}", "kind": kind, "family": fam, "pass_id": "pass1", "sources": batch})
                n += 1
    print(json.dumps({"reader_specs": n, "sources": int(len(todo)), "banned_host_not_assigned": len(banned),
                      "to_reader_web": sum(v in ("unreachable", "abstract_only") for v in status.values())}))


def atlas_ids() -> None:
    """PREREG v2 L7: the atlas line IDs from the kit's Cande rows (line IDs only, read by OCR in run 1); no paper is opened."""
    _unlocked("atlas-ids")
    rows = [r for r in csv.DictReader(open(KIT / "driver_lines.csv", encoding="utf-8")) if norm_doi(r["source_doi"]) == ATLAS_DOI]
    ids = sorted({re.sub(r"\s+", "", r["line_id"]).upper() for r in rows if r["line_id"].strip()})
    _write_csv(WORK / "atlas" / "atlas_line_ids.csv", [{"line_id": x} for x in ids], ["line_id"])
    src_map = [slug(ATLAS_DOI), slug(NAMIKI_DOI), slug(CATALOGUE_DOI)]
    inp = {"atlas_line_ids.csv": str(WORK / "atlas" / "atlas_line_ids.csv")}
    _spec({"session": "atlas-map", "kind": "atlas_map", "pass_id": "atlas_map", "sources": src_map, "inputs": inp})
    _spec({"session": "atlas-codeA", "kind": "atlas_code", "pass_id": "pass1", "sources": [slug(ATLAS_DOI)], "inputs": inp})
    _spec({"session": "atlas-codeB", "kind": "atlas_code", "pass_id": "pass1", "sources": [slug(ATLAS_DOI)], "inputs": inp})
    print(json.dumps({"atlas_line_ids": len(ids), "specs": ["atlas-map", "atlas-codeA", "atlas-codeB"]}))


def atlas_quotes() -> None:
    """Phase B input for atlas coder B: coder A's quotes keyed `atlas:<LINE>:<headless|intact>` (PREREG v2 L8). The A session
    whose quotes B checks is recorded in a sidecar (not given to B): B's checks count only for that A session (review M2a)."""
    _unlocked("atlas-quotes")
    meta = WORK / "atlas" / "quotes_to_verify_B.meta.json"
    if meta.exists():
        raise SystemExit("coder B's quotes were written already (one Phase B)")
    cands = [s["session"] for s in _specs("atlas_code") if s["session"].startswith("atlas-codeA")]
    breach = _breaching(sessions=cands)
    a = _atlas_session("atlas-codeA", breach)
    if a is None:
        raise SystemExit("no usable atlas coder A session yet")
    rows, seen = [], set()
    for r in sorted(_jsonl(RAW / "pass1" / a / "records.valid.jsonl"), key=lambda x: str(x.get("record_id"))):
        line, prep = _atlas_key(r)
        if (line, prep) not in seen:
            seen.add((line, prep))
            rows.append({"exp_id": f"atlas:{line}:{prep}", "doi": r["doi"], "source_locator": r["source_locator"], "quote": r["quote"]})
    _write_csv(WORK / "atlas" / "quotes_to_verify_B.csv", rows, ["exp_id", "doi", "source_locator", "quote"])
    meta.write_text(json.dumps({"a_session": a, "n_quotes": len(rows), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")
    print(json.dumps({"atlas_quotes_for_B": len(rows), "a_session": a}))


# --------------------------------------------------------------------------------------------------------- collect / leads / reassign
def collect() -> None:
    if LOCKED.exists():
        raise SystemExit("LOCK_labels_v2.json exists: labels v2 are locked (the verifier is collected by `verify-score`)")
    LC.collect()


def searches(round_: int) -> None:
    """PREREG v2 L8/L9: one fresh search session per search kind for this round (rounds 1-3; run after the first complete reading
    of the registry, and after each round whose leads added >= 10 % new units)."""
    _unlocked("searches")
    if not 1 <= round_ <= 3:
        raise SystemExit("search rounds are 1, 2 or 3 (PREREG v2 L9)")
    kinds = json.loads((KIT / "families_v2.json").read_text(encoding="utf-8"))["search_kinds"]
    names = []
    for k in kinds:
        name = f"search-{k.replace('_', '')}-r{round_}"
        if (SPECS / f"{name}.json").exists():
            continue
        _spec({"session": name, "kind": "search", "search_kind": k, "pass_id": "search", "sources": []})
        names.append(name)
    print(json.dumps({"search_specs": names}))


def leads(round_: int) -> None:
    """Leads of search round N -> new registry rows (never dedicated sources) and the round's units (PREREG v2 L8, L9)."""
    _unlocked("leads")
    if round_ < 1:
        raise SystemExit("search rounds start at 1")
    breach = _breaching()  # every session finished and audited; leads of breaching searches are dropped (L3)
    reg = _registry()
    known = set(reg["doi"])
    units_before = _units_known(round_, breach)
    new_rows, units_round = [], set()
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
            if d not in known and d not in DEDICATED_DOIS and not is_dedicated(d):
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


def _units_known(round_: int, breach: set[str]) -> set:
    """Units known before search round N (PREREG v2 L9): first readings (non-breaching, as used) incl. the mapped atlas records,
    plus the leads of earlier rounds only (review M4)."""
    u = {(norm_doi(r["doi"]), r["manc_type"]) for r in _pass1_generic(breach)}
    a1, _, _, _ = atlas_pairs(breach)
    u |= {(norm_doi(r["doi"]), r["manc_type"]) for r in a1 if r["manc_type"] != "UNMAPPED"}
    for p in sorted(WORK.glob("recall_units_round_*.json")):
        if int(re.search(r"round_(\d+)", p.name).group(1)) < round_:
            u |= {tuple(x) for x in json.loads(p.read_text())}
    return u


def reassign() -> None:
    """PREREG v2 L3/L5/C1. Readers: sources without a disposition and all sources of a breaching reader go to a new session of the
    same kind; sources a (non-web) reader marks `unreachable` go to a `reader_web` session; at most two reassignments per source
    across all chains, then the source is reported as unreached. Each new spec names the session it `replaces` for those
    sources; the earlier session's records of them are dropped (`_pass1_generic`). Other tasks (second reading, adjudication,
    atlas coding, atlas map) that end without a disposition for every assigned source are given once to a new session
    (`<session>-a1`, same inputs); the collector then uses the new session instead (review M3)."""
    _unlocked("reassign")
    mans = [json.loads(m.read_text()) for m in sorted(R2.MANIFESTS.glob("*.json"))]
    done = [m for m in mans if not any(R2._alive(r["pid"]) for r in m["runs"]) and m["kind"] != "verify"]
    breach = _breaching(sessions=[m["session"] for m in done])
    n_assign = collections.Counter(x for s in _specs(("reader", "reader_web")) for x in s.get("sources") or [])
    taken = {(s.get("replaces"), x) for s in _specs(("reader", "reader_web")) if s.get("replaces") for x in s.get("sources") or []}
    sup = _superseded()
    specs, unreached = [], set()
    for man in done:
        kind, sess = man["kind"], man["session"]
        rows, _ = LC.read_csv_rows(Path(man["room"]) / "out" / "dispositions.csv", ["doi", "disposition", "n_records", "reason"])
        disp = {norm_doi(r["doi"]): (r.get("disposition") or "").strip() for r in rows}
        if kind in ("reader", "reader_web"):
            srcs = [s for s in man.get("sources") or [] if (sess, s) not in taken]
            doi_of = {s: norm_doi(_meta(s)["doi"]) for s in srcs}
            missing = list(srcs) if sess in breach else \
                [s for s in srcs if disp.get(doi_of[s]) not in ("records", "no_qualifying_experiment", "unreachable")]
            again = [s for s in missing if n_assign[s] < 3]  # the first assignment plus at most two reassignments (L5)
            unreached |= {s for s in missing if n_assign[s] >= 3}
            if again:
                specs.append(_spec({"session": _free(sess, "a"), "kind": kind, "family": man["family"], "pass_id": "pass1",
                                    "sources": again, "replaces": sess}))
                n_assign.update(again)
            if kind == "reader" and sess not in breach:
                unreach = [s for s in srcs if disp.get(doi_of[s]) == "unreachable" and not _meta(s).get("banned_host")]
                web = [s for s in unreach if n_assign[s] < 3]
                unreached |= set(unreach) - set(web)
                if web:
                    specs.append(_spec({"session": _free(sess, "w"), "kind": "reader_web", "family": man["family"], "pass_id": "pass1",
                                        "sources": web, "replaces": sess}))
                    n_assign.update(web)
        elif kind in REDO_KINDS and sess not in breach and sess not in sup and not re.search(r"-(a|r)\d+$", sess):
            srcs = man.get("sources") or []
            if any(norm_doi(_meta(s)["doi"]) not in disp for s in srcs):
                spec = json.loads((SPECS / f"{sess}.json").read_text())
                specs.append(_spec(dict(spec, session=f"{sess}-a1", replaces=sess)))
    _write_csv(WORK / "unreached_sources.csv", [{"slug": s} for s in sorted(unreached)], ["slug"])
    print(json.dumps({"new_sessions": len(specs), "unreached_sources": len(unreached)}))


# --------------------------------------------------------------------------------------------------------- atlas
def atlas_map(breach: set[str]) -> tuple[dict[str, tuple[list[str], str, str]], dict]:
    """The single-reading atlas line map (PREREG v2 L8): key = line ID upper-cased without spaces; `manc_types` split on `;` or
    `,`; names not in the type list logged and dropped; `mapping_confidence` lower-cased, anything outside high/medium/low ->
    low; a duplicate line keeps its first row (logged)."""
    s = _atlas_session("atlas-map", breach)
    log = {"map_session": s, "duplicate_rows": [], "unknown_type_names": [], "confidence_set_to_low": 0}
    if s is None:
        return {}, log
    rows, _ = LC.read_csv_rows(RAW / "atlas_map" / s / "atlas_line_map.csv", ["line_id", "manc_types", "mapping_confidence", "mapping_basis"])
    kt = LC.known_types()
    out = {}
    for r in rows:
        key = re.sub(r"\s+", "", r.get("line_id") or "").upper()
        if not key:
            continue
        names = [x.strip() for x in re.split(r"[;,]", r.get("manc_types") or "") if x.strip()]
        unknown = [x for x in names if x not in kt and x.upper() != "UNMAPPED"]
        if unknown:
            log["unknown_type_names"].append({"line_id": key, "names": unknown})
        conf = (r.get("mapping_confidence") or "").strip().lower()
        if conf not in ("high", "medium", "low"):
            conf = "low"
            log["confidence_set_to_low"] += 1
        if key in out:
            log["duplicate_rows"].append(key)
            continue
        out[key] = (sorted({x for x in names if x in kt}), conf, r.get("mapping_basis") or "")
    return out, log


def _atlas_side(session: str, use_snapshot: bool) -> list[dict]:
    """Coder B's first reading is its Phase A snapshot once Phase B has started (absent from the snapshot = no records, the
    frozen rule); before that, its records (review M2b)."""
    sd = RAW / "pass1" / session
    if use_snapshot and (sd / "phaseA_snapshot").exists():
        f = sd / "phaseA_snapshot" / "records.jsonl"
        if not f.exists():
            return []
        good, _ = LC.validate_lines(f.read_text().splitlines(), LC.known_types(), session, "pass1")
        return good
    return _jsonl(sd / "records.valid.jsonl")


def _atlas_key(r: dict) -> tuple[str, str]:
    """PREREG v2 L8: (line ID upper-cased without spaces, headless or intact): a line tested headless and intact = two experiments."""
    line = re.sub(r"\s+", "", str((r.get("driver_lines") or [r.get("name_in_paper", "")])[0])).upper()
    return line, ("headless" if r.get("preparation") == "headless" else "intact")


def atlas_pairs(breach: set[str]) -> tuple[list[dict], list[dict], dict, dict]:
    """Coder A = first reading, coder B = second reading; keyed by (line, headless|intact); expanded to one record per mapped
    type (PREREG v2 L8). Duplicate keys keep the first `record_id` and are logged. B's quote checks count only if B checked the
    quotes of the A session in use."""
    amap, mlog = atlas_map(breach)
    sess_of = {"A": _atlas_session("atlas-codeA", breach), "B": _atlas_session("atlas-codeB", breach)}
    info = {"sessions": sess_of, "map": mlog, "duplicate_keys": {"A": [], "B": []}, "keys_A": 0, "keys_B": 0, "mapped_keys": 0}
    if sess_of["A"] is None:
        return [], [], {}, info
    sides = {}
    for tag, sess in sess_of.items():
        by_key = {}
        for r in sorted(_atlas_side(sess, tag == "B") if sess else [], key=lambda x: str(x.get("record_id"))):
            k = _atlas_key(r)
            if k in by_key:
                info["duplicate_keys"][tag].append(f"{k[0]}:{k[1]}:{r.get('record_id')}")
                continue
            by_key[k] = r
        sides[tag] = by_key
    info["keys_A"], info["keys_B"] = len(sides["A"]), len(sides["B"])
    p1, p2 = [], []
    for (line, prep), ra in sorted(sides["A"].items()):
        types, conf, basis = amap.get(line, ([], "low", ""))
        if types:
            info["mapped_keys"] += 1
        for t in (types or ["UNMAPPED"]):
            for src, dst in ((ra, p1), (sides["B"].get((line, prep)), p2)):
                if src is None:
                    continue
                r = dict(src, exp_id=f"atlas:{line}:{prep}:{t}", manc_type=t, mapping_confidence=conf if types else "low",
                         mapping_basis=f"atlas line map: {basis}"[:300])
                if len(types) > 1:
                    r["line_specificity"] = "multi_dn"
                    r["other_cell_types"] = sorted(set(r.get("other_cell_types") or []) | (set(types) - {t}))
                dst.append(r)
    qc = {}
    meta = WORK / "atlas" / "quotes_to_verify_B.meta.json"
    a_seen = json.loads(meta.read_text()).get("a_session") if meta.exists() else None
    if sess_of["B"] and a_seen == sess_of["A"]:
        rows, _ = LC.read_csv_rows(RAW / "pass1" / sess_of["B"] / "quote_checks.csv", ["exp_id", "quote_found", "where", "comment"])
        for row in rows:
            v = row.get("quote_found", "").strip().lower()
            parts = row["exp_id"].split(":")
            if len(parts) < 3 or parts[0] != "atlas":
                continue
            line, prep = re.sub(r"\s+", "", parts[1]).upper(), parts[2].lower()
            for t in (amap.get(line, ([], "", ""))[0] or ["UNMAPPED"]):
                qc[f"atlas:{line}:{prep}:{t}"] = True if v in LC.TRUE_WORDS else (False if v in LC.FALSE_WORDS else None)
    else:
        info["quote_checks_not_used"] = {"a_session_quoted": a_seen, "a_session_used": sess_of["A"]}
    return p1, p2, qc, info


# --------------------------------------------------------------------------------------------------------- second reading / adjudication
def _session_logs_mtime(man: dict) -> float:
    ts = [f.stat().st_mtime for f in R2.ROOMS.glob(f"{man['session']}.*.stream.jsonl")]
    ts += [f.stat().st_mtime for f in R2.transcripts(Path(man["room"]))]
    return max(ts, default=0.0)


def _breaching(sessions=None) -> set[str]:
    """PREREG v2 L3 timing (v1's coverage and freshness checks, ported; review B4): every session (all of them, or the given ones)
    must have finished, be in the audit, and have no log newer than its audit. The verifier is checked against its own audit."""
    p = LAB / "transcript_audit.json"
    if not p.exists():
        raise SystemExit("run ledger/scripts/labels2_audit.py first")
    rows = json.loads(p.read_text())
    when = {r["session"]: p.stat().st_mtime for r in rows}
    vp = VER / "transcript_audit_verify.json"
    vrows = json.loads(vp.read_text()) if vp.exists() else []
    when.update({r["session"]: vp.stat().st_mtime for r in vrows})
    mans = {}
    for m in R2.MANIFESTS.glob("*.json"):
        man = json.loads(m.read_text())
        mans[man["session"]] = man
    need = set(mans) if sessions is None else set(sessions) & set(mans)
    problems = []
    for s in sorted(need):
        man = mans[s]
        if any(R2._alive(r["pid"]) for r in man["runs"]):
            problems.append(f"{s}: still running")
        elif s not in when:
            problems.append(f"{s}: not in the transcript audit")
        elif _session_logs_mtime(man) > when[s]:
            problems.append(f"{s}: a log is newer than its audit")
    if problems:
        raise SystemExit("the transcript audit is not current (PREREG v2 L3): " + "; ".join(problems[:6])
                         + ("; ..." if len(problems) > 6 else "") + " -> let the sessions finish and re-run labels2_audit.py")
    return {r["session"] for r in rows + vrows if r.get("breach")}


def _superseded() -> set[str]:
    """Tasks given to a new session (`replaces`: a breaching one, L3, or one without every disposition, L5): their outputs are
    not used."""
    return {s["replaces"] for s in _specs(REDO_KINDS) if s.get("replaces")}


def _atlas_session(base: str, breach: set[str]) -> str | None:
    """The atlas coder / map session in use: the one of `<base>` and its replacements that exists, is not breaching and was not
    replaced (PREREG v2 L3, L5)."""
    area = RAW / ("atlas_map" if base == "atlas-map" else "pass1")
    sup = _superseded()
    chain = [base] + sorted(s["session"] for s in _specs(("atlas_code", "atlas_map")) if s["session"].startswith(base + "-"))
    for s in chain:
        if (area / s).exists() and s not in breach and s not in sup:
            return s
    return None


REDO_KINDS = ("second", "second_web", "adjudication", "adjudication_web", "atlas_code", "atlas_map", "verify")


def redo_breaching() -> None:
    """PREREG v2 L3: the task of a breaching second reader, adjudicator, atlas coder, atlas-map session or verifier is given ONCE
    to a new session (`<session>-r1`, same inputs); a replacement is not replaced again. After the labels lock only the verifier
    (L11)."""
    post = LOCKED.exists()
    mans = {}
    for m in R2.MANIFESTS.glob("*.json"):
        man = json.loads(m.read_text())
        mans[man["session"]] = man
    n = 0
    if post:
        vp = VER / "transcript_audit_verify.json"
        if not vp.exists():
            raise SystemExit("run ledger/scripts/labels2_audit.py --verify first")
        breach = {r["session"] for r in json.loads(vp.read_text()) if r.get("breach")}
        for s in _specs("verify", where=VER / "specs"):
            name = s["session"]
            if name in breach and not re.search(r"-(a|r)\d+$", name) and not (VER / "specs" / f"{name}-r1.json").exists():
                _spec(dict(s, session=f"{name}-r1", replaces=name), where=VER / "specs")
                n += 1
    else:
        specs = [s for s in _specs(REDO_KINDS) if s["session"] in mans]
        finished = [s["session"] for s in specs if not any(R2._alive(r["pid"]) for r in mans[s["session"]]["runs"])]
        breach = _breaching(sessions=finished)
        for s in specs:
            name = s["session"]
            if name in breach and not re.search(r"-(a|r)\d+$", name) and not (SPECS / f"{name}-r1.json").exists():
                _spec(dict(s, session=f"{name}-r1", replaces=name))
                n += 1
    print(json.dumps({"replacement_specs": n}))


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


def _assigned_sources() -> dict[str, set[str]]:
    return {s["session"]: set(s.get("sources") or []) for s in _specs(("reader", "reader_web"))}


def _match_source(rec: dict, srcs: set[str]) -> str | None:
    """The assigned source a record belongs to: its DOI's slug, or that slug without a preprint version suffix."""
    s = slug(rec.get("doi", ""))
    if s in srcs:
        return s
    s2 = re.sub(r"_?v\d+$", "", s)
    return s2 if s2 in srcs else None


def _pass1_generic(breach: set[str], log: dict | None = None) -> list[dict]:
    """First readings used (PREREG v2 L3, L5, L8, C1): records of non-breaching reader sessions whose DOI is one of the session's
    assigned sources (the task is the assigned sources only; others are logged and not used; review M1), minus a replaced
    session's records of the reassigned sources, deduplicated in the v2 order."""
    assigned = _assigned_sources()
    doi_by_slug = dict(zip(_registry()["slug"], _registry()["doi"]))
    recs = []
    for sd in sorted((RAW / "pass1").glob("pass1-*")):
        if sd.name in breach:
            continue
        srcs = assigned.get(sd.name, set())
        for r in _jsonl(sd / "records.valid.jsonl"):
            m = _match_source(r, srcs)
            if m is None:
                if log is not None:
                    log.setdefault("records_outside_assigned_sources", []).append(r["exp_id"])
                continue
            if slug(r["doi"]) != m:
                if log is not None:
                    log.setdefault("doi_matched_without_version_suffix", []).append(r["exp_id"])
                r = dict(r, doi=doi_by_slug.get(m, r["doi"]))
            recs.append(r)
    repl = {(s["replaces"], x) for s in _specs(("reader", "reader_web")) if s.get("replaces") for x in s.get("sources") or []}
    recs = [r for r in recs if (r["exp_id"].split(":", 1)[0], slug(r["doi"])) not in repl]
    kept, dropped = dedupe_v2(recs)
    if log is not None:
        log["dedupe_v2_dropped"] = dropped
    return kept


NEUTRAL_WORDS = ["walk", "walking", "stop", "stopping", "halt", "halting", "groom", "grooming", "turn", "turning", "steer", "steering",
                 "escape", "takeoff", "take-off", "jump", "landing", "flight", "backward", "forward", "rhythm", "rhythmic", "locomotion",
                 "leg", "legs", "posture", "freeze", "freezing"]
NEUTRAL_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(NEUTRAL_WORDS, key=len, reverse=True)) + r")\b", re.I)


def neutral(s: str) -> str:
    return NEUTRAL_RE.sub("[...]", s or "")


def second() -> None:
    _unlocked("second")
    breach = _breaching()  # L3: the audit covers every session and is newer than every log before second-reading inputs
    p1 = _pass1_generic(breach)
    covered = set()
    for s in _specs(("second", "second_web")):
        covered |= set(s.get("exp_ids") or [])
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
    web = _web_slugs()
    for d in sorted(by_doi):
        groups[("dedicated" if fam_of.get(d) == "dedicated" or is_dedicated(d) else "general", slug(d) in web)].append(d)
    n_specs = 0
    for (grp, is_web), dois in groups.items():
        tag = grp + ("-web" if is_web else "")
        for i in range(0, len(dois), 6):
            batch = dois[i:i + 6]
            exps = [r for d in batch for r in by_doi[d]]
            n = 1
            while (SPECS / f"pass2-{tag}-{n:02d}.json").exists():
                n += 1
            name = f"pass2-{tag}-{n:02d}"
            ex_path, q_path = WORK / "second" / name / "experiments_to_label.csv", WORK / "second" / name / "quotes_to_verify.csv"
            _write_csv(ex_path, exps, LP.ID_FIELDS)
            _write_csv(q_path, [{"exp_id": r["exp_id"], "doi": recs[r["exp_id"]]["doi"], "source_locator": recs[r["exp_id"]]["source_locator"],
                                 "quote": recs[r["exp_id"]]["quote"]} for r in exps], ["exp_id", "doi", "source_locator", "quote"])
            _spec({"session": name, "kind": "second_web" if is_web else "second", "family": "dedicated" if grp == "dedicated" else None, "pass_id": "pass2",
                   "sources": [slug(d) for d in batch], "inputs": {"experiments_to_label.csv": str(ex_path)},
                   "quotes": str(q_path), "exp_ids": [r["exp_id"] for r in exps]})
            n_specs += 1
    print(json.dumps({"second_reading_specs": n_specs, "experiments": len(todo)}))


def _pass2_records(breach: set[str]) -> list[dict]:
    skip = breach | _superseded()
    out = []
    for sd in sorted((RAW / "pass2").glob("pass2-*")):
        if sd.name not in skip:
            out += _jsonl(sd / "records.valid.jsonl")
    return out


def adjudication() -> None:
    """Disagreements -> adjudication specs (PREREG v2 L8), incremental: a disputed field already given to an adjudicator is not
    given again; new disputes get new session names (review B5). Reading order: a coin per dispute from seed 20261206."""
    _unlocked("adjudication")
    breach = _breaching()
    p1 = _pass1_generic(breach)
    p2 = {r["exp_id"]: r for r in _pass2_records(breach)}
    a1, a2, _, _ = atlas_pairs(breach)
    p2.update({r["exp_id"]: r for r in a2})
    covered = {tuple(x) for s in _specs(("adjudication", "adjudication_web")) for x in s.get("disputes") or []}
    sib = {}
    for f in sorted((WORK / "second").glob("*/experiments_to_label.csv")):
        for row in csv.DictReader(open(f, encoding="utf-8")):
            sib[row["exp_id"]] = row
    groups = collections.defaultdict(list)
    web = _web_slugs()
    fam_of = dict(zip(_registry()["doi"], _registry()["family"]))
    for a in p1 + a1:
        b = p2.get(a["exp_id"])
        if b is None:
            continue
        for f in AGG.COMPARED_FIELDS:
            if a.get(f) == b.get(f) or (a["exp_id"], f) in covered:
                continue
            coin = np.random.default_rng([ADJ_SEED, int(hashlib.sha256(f"{a['exp_id']}|{f}".encode()).hexdigest()[:12], 16)]).random()
            ra, rb = (a.get(f), b.get(f)) if coin < 0.5 else (b.get(f), a.get(f))
            d = norm_doi(a["doi"])
            g = ("dedicated" if fam_of.get(d) == "dedicated" or is_dedicated(d) else "general", slug(a["doi"]) in web)
            groups[g].append({**{k: (";".join(a[k]) if isinstance(a.get(k), list) else a.get(k, "")) for k in LP.ID_FIELDS
                                 if k not in ("sibling_index", "n_siblings")}, "sibling_index": sib.get(a["exp_id"], {}).get("sibling_index", 1),
                              "n_siblings": sib.get(a["exp_id"], {}).get("n_siblings", 1),
                              "field": f, "reading_A": json.dumps(ra), "reading_B": json.dumps(rb)})
    n_specs = 0
    for (g, is_web), rows in groups.items():
        tag = f"{g}{'-web' if is_web else ''}"
        dois = sorted({norm_doi(r["doi"]) for r in rows})
        for i in range(0, len(dois), 6):
            batch = set(dois[i:i + 6])
            k = 1
            while (SPECS / f"adjudication-{tag}-{k:02d}.json").exists():
                k += 1
            name = f"adjudication-{tag}-{k:02d}"
            mine = [r for r in rows if norm_doi(r["doi"]) in batch]
            path = WORK / "adjudication" / name / "disagreements.csv"
            _write_csv(path, mine, LP.ID_FIELDS + ["field", "reading_A", "reading_B"])
            _spec({"session": name, "kind": "adjudication_web" if is_web else "adjudication", "family": "dedicated" if g == "dedicated" else None,
                   "pass_id": "adjudication", "sources": [slug(d) for d in sorted(batch)], "inputs": {"disagreements.csv": str(path)},
                   "disputes": [[r["exp_id"], r["field"]] for r in mine]})
            n_specs += 1
    print(json.dumps({"adjudication_specs": n_specs, "disputed_fields": {f"{g}{'-web' if w else ''}": len(r) for (g, w), r in groups.items()}}))


# --------------------------------------------------------------------------------------------------------- merge / finalize
def _quote_checks_generic(breach: set[str]) -> dict:
    qc = {}
    skip = breach | _superseded()
    for sd in sorted((RAW / "pass2").glob("pass2-*")):
        if sd.name in skip:
            continue
        rows, _ = LC.read_csv_rows(sd / "quote_checks.csv", ["exp_id", "quote_found", "where", "comment"])
        for row in rows:
            v = row.get("quote_found", "").strip().lower()
            qc[row["exp_id"]] = True if v in LC.TRUE_WORDS else (False if v in LC.FALSE_WORDS else None)
    return qc


def _not_found_v2(breach: set[str]) -> set[str]:
    """The frozen `not_found` (Phase A snapshot rule) over the second readings in use only: an excluded or replaced session's
    not-found rows do not count (review B2)."""
    out, skip = set(), breach | _superseded()
    for sd in sorted((RAW / "pass2").glob("*")):
        if sd.name in skip:
            continue
        hp = sd / "phaseA_snapshot" / "phaseA_hashes.json"
        if hp.exists():
            h = json.loads(hp.read_text(encoding="utf-8"))["sha256"]
            src = sd / "phaseA_snapshot" / "not_found.csv" if "not_found.csv" in h else None
        else:
            src = sd / "not_found.csv"
        if src is None:
            continue
        rows, _ = LC.read_csv_rows(src, ["exp_id", "reason"])
        out |= {r["exp_id"] for r in rows if r.get("exp_id")}
    return out


def merged(breach: set[str]) -> tuple[list[dict], dict, list[dict], list[dict]]:
    clog: dict = {}
    p1, p2 = _pass1_generic(breach, clog), _pass2_records(breach)
    qc = _quote_checks_generic(breach)
    nf = _not_found_v2(breach)
    a1, a2, aqc, ainfo = atlas_pairs(breach)
    adj, skip = [], breach | _superseded()
    for sd in sorted((RAW / "adjudication").glob("adjudication-*")):
        if sd.name not in skip:
            adj += _jsonl(sd / "records.valid.jsonl")
    final, log = AGG.merge_passes(p1 + a1, p2 + a2, adj, {**qc, **aqc}, nf)
    log["atlas"] = ainfo
    log["collector_v2"] = clog
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


def _sightings_check(final: list[dict]) -> list[dict]:
    """L4: `sightings.csv` rows of sessions whose records of that DOI carry no `saw_simulation_score` (logged for the review)."""
    out = []
    flagged = {(r["exp_id"].split(":", 1)[0], slug(r["doi"])) for r in final if r.get("saw_simulation_score")}
    for f in sorted(RAW.glob("*/*/sightings.csv")):
        rows, _ = LC.read_csv_rows(f, ["doi", "locator", "what_was_seen", "types_as_printed"])
        for r in rows:
            if (f.parent.name, slug(r.get("doi", ""))) not in flagged:
                out.append({"session": f.parent.name, "doi": norm_doi(r.get("doi", "")), "locator": r.get("locator", "")})
    return out


def _chapman(p1: list[dict]) -> dict:
    """PREREG v2 L9: Chapman between the first reading's units and search round 1's units, dedicated family excluded."""
    a = {(norm_doi(r["doi"]), r["manc_type"]) for r in p1 if r.get("manc_type") not in (None, "", "UNMAPPED") and not is_dedicated(r["doi"])
         and _fam_of_session(r["exp_id"].split(":", 1)[0]) != "dedicated"}
    f = WORK / "recall_units_round_1.json"
    if not f.exists():
        return {"status": "no search round 1"}
    b = {tuple(x) for x in json.loads(f.read_text()) if not is_dedicated(x[0])}
    m, n1, n2 = len(a & b), len(a), len(b)
    est = (n1 + 1) * (n2 + 1) / (m + 1) - 1
    return {"unit": "(normalised doi, manc_type)", "estimator": "Chapman", "n_first": n1, "n_round1": n2, "n_both": m,
            "estimated_total": est, "estimated_missed_by_both": est - len(a | b),
            "assumptions": "closed population, independent lists, equal catchability; both lists come from the same model family, so the estimate is likely low"}


def finalize() -> None:
    _unlocked("finalize")
    breach = _breaching()  # L3: every session finished, audited, audit newer than every log
    final, log, p1, p2 = merged(breach)
    fill_log = line_spec_fill(final)
    ex = pd.read_csv(KIT / "exposed_types.csv")
    exposed = {t for s in ex["manc_types"].dropna() for t in str(s).split(";") if t}
    ded = {r["exp_id"] for r in final if _fam_of_session(r["exp_id"].split(":", 1)[0]) == "dedicated"}
    elig = [r for r in final if AGG.eligible(r)]
    by_nature = sorted({r["manc_type"] for r in elig} - {r["manc_type"] for r in elig if r["exp_id"] not in ded})
    pd.DataFrame({"manc_type": by_nature, "reason": "eligible records only from dedicated sessions"}).to_csv(LAB / "exposed_v2.csv", index=False, lineterminator="\n")
    tl = AGG.type_labels(final, exposed=exposed | set(by_nature), type_list=sorted(LC.known_types()))
    ag = agreement(p1, p2)
    with open(LAB / "records.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in final:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    tl.to_csv(LAB / "type_labels.csv", index=False, lineterminator="\n")
    unreached = list(csv.DictReader(open(WORK / "unreached_sources.csv", encoding="utf-8"))) if (WORK / "unreached_sources.csv").exists() else []
    (LAB / "merge_log.json").write_text(json.dumps({"merge": log, "line_spec_fill": fill_log, "recall_chapman": _chapman(p1),
                                                    "unreached_sources": [r["slug"] for r in unreached],
                                                    "sightings_without_flagged_records": _sightings_check(final)},
                                                   indent=1, default=str) + "\n")
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
    web = _web_slugs()
    frame = sorted([r for r in final if AGG.eligible(r) and not r["exp_id"].split(":", 1)[0].startswith("pass1-dedicated")
                    and slug(r["doi"]) not in web], key=lambda r: r["exp_id"])
    return frame


def verify_sample() -> None:
    """PREREG v2 L11: once, after LOCK_labels_v2.json, on the locked records; new files under labels_v2/verify/ only."""
    if not LOCKED.exists():
        raise SystemExit("the verification runs after LOCK_labels_v2.json (PREREG v2 L11)")
    want = json.loads(LOCKED.read_text())["labels"].get("research/ledger/labels_v2/records.jsonl")
    if hashlib.sha256((LAB / "records.jsonl").read_bytes()).hexdigest() != want:
        raise SystemExit("labels_v2/records.jsonl differs from the locked file")
    if (VER / "verify_sample.csv").exists():
        raise SystemExit("the verification sample exists already (drawn once)")
    frame = _verify_frame()
    idx = np.random.default_rng(VERIFY_SEED).choice(len(frame), min(30, len(frame)), replace=False)
    pick = [frame[i] for i in idx]
    path = VER / "verify_sample.csv"
    cols = ["exp_id", "doi", "source_locator", "driver_lines", "name_in_paper", "quote"]  # no recorded value (blind, L11)
    _write_csv(path, [{k: (";".join(r[k]) if isinstance(r.get(k), list) else r.get(k, "")) for k in cols} for r in pick], cols)
    (VER / "verify_truth.json").write_text(json.dumps({r["exp_id"]: r["front_leg_rhythm"] for r in pick}, indent=1) + "\n")
    _spec({"session": "verify-01", "kind": "verify", "pass_id": "verify", "sources": sorted({slug(r["doi"]) for r in pick}),
           "inputs": {"verify_sample.csv": str(path)}}, where=VER / "specs")
    print(json.dumps({"verify_sample": len(pick), "frame": len(frame)}))


def verify_score() -> None:
    """Collect the verifier's outputs into labels_v2/verify/raw/<session>/ (hashed), then score. The verifier used is `verify-01`,
    or `verify-01-r1` if `verify-01` breached (audit: `labels2_audit.py --verify`); if both breached, gate 3 fails."""
    aud = VER / "transcript_audit_verify.json"
    if not aud.exists():
        raise SystemExit("run ledger/scripts/labels2_audit.py --verify first")
    vrows = json.loads(aud.read_text())
    breach = {r["session"] for r in vrows if r.get("breach")}
    audited = {r["session"] for r in vrows}
    for s in ("verify-01", "verify-01-r1"):
        mp = R2.MANIFESTS / f"{s}.json"
        if not mp.exists():
            continue
        man = json.loads(mp.read_text())
        if any(R2._alive(r["pid"]) for r in man["runs"]):
            raise SystemExit(f"{s} is still running")
        if s not in audited or _session_logs_mtime(man) > aud.stat().st_mtime:
            raise SystemExit(f"{s}: not audited after it finished; run labels2_audit.py --verify")
    sess = next((s for s in ("verify-01", "verify-01-r1") if (R2.MANIFESTS / f"{s}.json").exists() and s not in breach), None)
    truth = json.loads((VER / "verify_truth.json").read_text())
    out = {"n": len(truth), "verifier_session": sess, "breaching_verifiers": sorted(breach)}
    if sess is None:
        out.update({"errors": None, "error_rate": None, "blocker": True, "reason": "no non-breaching verifier (L3, L11)"})
    else:
        man = json.loads((R2.MANIFESTS / f"{sess}.json").read_text())
        dst = VER / "raw" / sess
        dst.mkdir(parents=True, exist_ok=True)
        hashes = {}
        for f in sorted((Path(man["room"]) / "out").glob("*")):
            if f.is_file():
                (dst / f.name).write_bytes(f.read_bytes())
                hashes[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
        (dst / "out_sha256.json").write_text(json.dumps(hashes, indent=1) + "\n")
        rows, _ = LC.read_csv_rows(dst / "verification.csv", ["exp_id", "quote_found", "front_leg_rhythm", "locator", "comment"])
        got = {r["exp_id"]: r for r in rows}
        errors = [k for k, v in truth.items() if k not in got or got[k].get("front_leg_rhythm", "").strip().lower() in ("", "cannot_verify")
                  or got[k]["front_leg_rhythm"].strip().lower() != str(v).lower()]
        quotes_found = sum(1 for k in truth if k in got and got[k].get("quote_found", "").strip().lower() in LC.TRUE_WORDS)
        out.update({"errors": len(errors), "error_rate": len(errors) / len(truth) if truth else None, "quotes_found": quotes_found,
                    "blocker": (len(errors) / len(truth) > 0.10) if truth else True})
    (VER / "verification.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "breaching_verifiers"}))


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
    ap.add_argument("cmd", choices=["registry", "atlas-ids", "atlas-quotes", "redo-breaching", "searches", "readers", "collect", "leads", "reassign", "second", "adjudication", "verify-sample",
                                    "verify-score", "finalize", "v1-vs-v2"])
    ap.add_argument("--round", type=int, default=0)
    a = ap.parse_args()
    {"registry": registry, "atlas-ids": atlas_ids, "atlas-quotes": atlas_quotes, "redo-breaching": redo_breaching, "collect": collect, "reassign": reassign, "second": second, "adjudication": adjudication,
     "verify-sample": verify_sample, "verify-score": verify_score, "finalize": finalize, "v1-vs-v2": v1_vs_v2}.get(a.cmd, lambda: None)()
    if a.cmd == "readers":
        readers(a.round)
    if a.cmd == "leads":
        leads(a.round)
    if a.cmd == "searches":
        searches(a.round)


if __name__ == "__main__":
    main()
