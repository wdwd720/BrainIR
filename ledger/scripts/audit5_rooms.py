"""Label audit, run 5 (PREREG v5 Part L; RUN5_PROMPT hard limit 4: the orchestrator never authors a label).

Rooms are directories OUTSIDE the repository, `~/ledger_rooms/run5/<session>/`, holding only the task, kit v2's PROTOCOL.md,
type_list.csv, synonyms.csv and driver_lines.csv, the audit kit (`research/ledger/audit_kit_v1/`: AUDIT_NOTE.md, the audit copy of
record_schema.json), the session's list and inputs, and its assigned sources copied from the mechanical download cache
(`data/ledger/sources_v2/`, run 2's). No reader, coder or adjudicator room holds an exam 1 label or record. Sessions run `claude -p`
with run 2's frozen flags and deny rules (`labels2_rooms.flags_v2`; the web kinds may fetch exactly the assigned DOIs whose cached copy
is abstract-only or unreachable) plus deny rules for exam 1's rooms (`~/ledger_rooms/run2/`), inside run 2's macOS sandbox profile
(`labels2_rooms.spawn(..., mode="sandbox")`, which needs LEDGER_SCRATCH set to the orchestrator's temporary folder). A canary checks
the isolation first. Every collected session is checked by run 2's frozen transcript audit; a breaching session's records are excluded.

    audit5_rooms.py kit-manifest            # before the freeze: SHA-256 of every kit file a room can receive (reviews_v5/)
    audit5_rooms.py plan                    # audited types, relevant sources, reader groups -> labels_audit_v1/ASSIGNMENT.json (once)
    audit5_rooms.py canary [--tool-mode]    # isolation canary (L1) -> labels_audit_v1/CANARY.json
    audit5_rooms.py enqueue                 # first batch: forensic F1/F2, atlas coders A/B, readers A/B of every group
    audit5_rooms.py schedule [--max 6] [--tool-mode]
    audit5_rooms.py status | collect | transcript-audit | replace | unread
    audit5_rooms.py adjudicate-f            # F3, if F1 and F2 chose different sets of explanations (L2)
    audit5_rooms.py adjudicate-atlas        # atlas adjudicator for keys on which coders A and B differ (L3)
    audit5_rooms.py adjudicate-types        # type adjudicators for types whose reader labels differ (L3)
    audit5_rooms.py verify                  # verification sessions for primary-set types with a non-clear audited label (L4 b)

Labels, comparison, error rates: `labels_audit_v1.py`.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labels2_rooms as L2R  # noqa: E402  (frozen: flags_v2, spawn, _alive, deny rules and sandbox profile)

from brainir_ledger import RESEARCH  # noqa: E402

REPO = HERE.parents[1]
HOME = Path.home()
ROOMS = HOME / "ledger_rooms" / "run5"
MANIFESTS = ROOMS / "_manifests"
QUEUE = ROOMS / "_queue"
KIT = RESEARCH / "kit_v2"
AKIT = RESEARCH / "audit_kit_v1"
LAB2 = RESEARCH / "labels_v2"
SOURCES = REPO / "data" / "ledger" / "sources_v2"
OUT = RESEARCH / "labels_audit_v1"
SAMPLE_SEED = 20261528                       # PREREG v5 L3 (iii)
MAX_SOURCES, MAX_KB = 4, 300                 # L3: at most 4 sources and 300 KB of source text per reader session
MAX_TYPES = 20                               # L3: at most 20 types per reader session (a longer list is split, same sources)
MAP_FREE = ("atlas_code", "atlas_adj")       # L1: atlas rooms get no type map (PREREG v2 L8: the coders work without the map)
STOP_NAMES = {"web", "sink", "snail", "snake", "mute", "oval", "knees"}   # L3: other names that are common English words
WEB_STATUSES = {"abstract_only", "unreachable"}
FORENSIC_TYPE = "DNg100"
ATLAS_DOI = "10.7554/elife.34275"
KIT_FILES = ("PROTOCOL.md", "type_list.csv", "synonyms.csv", "driver_lines.csv")
KIT_MANIFEST = RESEARCH / "reviews_v5" / "AUDIT_KIT_MANIFEST_v1.json"   # hashed by LOCK_prereg_v5 (reviews_v5); pins audit_kit_v1


def _kit_files() -> dict[str, Path]:
    out = {f"audit_kit_v1/{p.name}": p for p in sorted(AKIT.glob("*")) if p.is_file()}
    out |= {f"kit_v2/{n}": KIT / n for n in (*KIT_FILES, "PROMPT_ATLAS_CODE.md", "PROMPT_VERIFY.md")}
    out |= {"labels_v2/work/atlas/atlas_line_ids.csv": LAB2 / "work" / "atlas" / "atlas_line_ids.csv",
            "ledger/src/brainir_ledger/labels/aggregate.py": REPO / "ledger" / "src" / "brainir_ledger" / "labels" / "aggregate.py"}
    return out


def kit_manifest() -> None:
    """Written once before the freeze: SHA-256 of every file a room can receive from the audit kit and kit v2 (PREREG v5 X5)."""
    _write_once(KIT_MANIFEST, json.dumps({"rule": "PREREG v5 L1-L3, X5: every room file from these kits must match", "sha256":
                                          {k: _sha(p.read_bytes()) for k, p in _kit_files().items()}}, indent=1, sort_keys=True) + "\n")
    print("wrote", KIT_MANIFEST)


def verify_kit() -> None:
    want = json.loads(KIT_MANIFEST.read_text(encoding="utf-8"))["sha256"]
    got = {k: _sha(p.read_bytes()) for k, p in _kit_files().items()}
    bad = sorted(k for k in set(want) | set(got) if want.get(k) != got.get(k))
    if bad:
        raise SystemExit(f"audit kit files differ from the frozen manifest: {bad}; refused")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _write_once(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _jsonl(p: Path) -> list[dict]:
    out = []
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(d, dict):
                    out.append(d)
    return out


# ------------------------------------------------------------------------------------------------------------------ sources
def cache() -> dict[str, dict]:
    """slug -> {doi, status, title, kb} for every folder of the download cache."""
    out = {}
    for m in sorted(SOURCES.glob("*/meta.json")):
        d = json.loads(m.read_text(encoding="utf-8"))
        t = m.parent / "text.txt"
        out[m.parent.name] = {"doi": str(d.get("doi") or ""), "status": d.get("status"), "title": str(d.get("title") or ""),
                              "kb": (t.stat().st_size / 1024) if t.exists() else 0.0}
    return out


def doi_to_slug(c: dict | None = None) -> dict[str, str]:
    c = c or cache()
    return {v["doi"].lower(): k for k, v in c.items() if v["doi"]}


def atlas_slug(c: dict | None = None) -> str:
    return doi_to_slug(c)[ATLAS_DOI]


def names_for(t: str, syn: list[dict] | None = None) -> list[str]:
    syn = syn if syn is not None else list(csv.DictReader(open(KIT / "synonyms.csv", encoding="utf-8")))
    names = {t} | {r["name"].strip() for r in syn if r["manc_type"] == t and r["name"].strip()}
    return sorted(n for n in names if n not in STOP_NAMES)


def pattern(name: str) -> re.Pattern:
    """L3: whole-word match; case-insensitive for names containing a digit, case-sensitive otherwise."""
    flags = re.I if re.search(r"\d", name) else 0
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", flags)


def mentions(types: list[str], c: dict | None = None) -> dict[str, set[str]]:
    c = c or cache()
    syn = list(csv.DictReader(open(KIT / "synonyms.csv", encoding="utf-8")))
    pats = {t: [pattern(n) for n in names_for(t, syn)] for t in types}
    out = {t: set() for t in types}
    for slug in c:
        tp = SOURCES / slug / "text.txt"
        text = tp.read_text(encoding="utf-8", errors="replace") if tp.exists() else ""
        for t in types:
            if any(p.search(text) for p in pats[t]):
                out[t].add(slug)
    return out


def exam1_records() -> list[dict]:
    return _jsonl(LAB2 / "records.jsonl")


def record_sources(types: list[str], c: dict | None = None) -> dict[str, set[str]]:
    d2s = doi_to_slug(c)
    out = {t: set() for t in types}
    for r in exam1_records():
        if r.get("manc_type") in out:
            s = d2s.get(str(r.get("doi") or "").lower())
            if s is None:
                raise SystemExit(f"exam 1 record source not in the cache: {r.get('doi')}")
            out[r["manc_type"]].add(s)
    return out


# ------------------------------------------------------------------------------------------------------------------- plan
def audited_types() -> dict:
    """L3: (i) the v2 exposed types; (ii) Part R types (not 'neither', B1r or A1 version) with an exam 1 front label in {yes, no, unclear,
    conflicting}; (iii) all primary-set types (census), with a seeded sample of 15 among them; (iv) Part R types with a kit line."""
    import numpy as np  # noqa: PLC0415
    import pandas as pd  # noqa: PLC0415

    import forward_v1 as F1  # noqa: PLC0415
    import forward_v2 as F2  # noqa: PLC0415
    import replication_v1 as R  # noqa: PLC0415

    exposed = sorted(F1.exposed_set_v2(RESEARCH))
    lab = pd.read_csv(LAB2 / "type_labels.csv", dtype={"manc_type": str}).set_index("manc_type")
    labelled = set(lab.index[lab["front"].isin(["yes", "no", "unclear", "conflicting"])])
    T = R.tables()
    cat = set()
    for x in ("B1r", "A1"):
        c = R.categories(T, x)
        cat |= set(c.loc[c["category"] != "neither", "manc_type"])
    part_r = sorted(cat & labelled)
    primary = sorted(F1.primary_set().index)
    sample = sorted(np.random.default_rng(SAMPLE_SEED).choice(primary, 15, replace=False).tolist())
    dl = F2.kit_line_rows()
    with_line = set(dl["manc_type"]) - {"", "AMBIGUOUS", "UNMAPPED"}
    part_r_lines = sorted(cat & with_line)
    return {"exposed": exposed, "part_r_labelled": part_r, "primary_census": primary, "random_sample": sample, "part_r_with_kit_line": part_r_lines,
            "all": sorted(set(exposed) | set(part_r) | set(primary) | set(part_r_lines))}


def plan() -> dict:
    if (OUT / "ASSIGNMENT.json").exists():
        raise SystemExit("ASSIGNMENT.json exists; the plan is made once")
    c = cache()
    A = audited_types()
    types = A["all"]
    rel_rec, rel_men = record_sources(types, c), mentions(types, c)
    rel = {t: sorted(rel_rec[t] | rel_men[t]) for t in types}
    at = atlas_slug(c)
    srcs = sorted({s for v in rel.values() for s in v} - {at})
    groups: list[list[str]] = []
    for s in sorted(srcs, key=lambda s: (-c[s]["kb"], s)):                  # first-fit decreasing by size, ties by name
        for g in groups:
            if len(g) < MAX_SOURCES and sum(c[x]["kb"] for x in g) + c[s]["kb"] <= MAX_KB:
                g.append(s)
                break
        else:
            groups.append([s])
    primary = set(A["primary_census"])
    G = []
    for g in groups:
        g = sorted(g)
        tl = sorted(t for t in types if set(rel[t]) & set(g))
        G.append({"sources": g, "types": tl, "web_dois": sorted(c[s]["doi"] for s in g if c[s]["status"] in WEB_STATUSES),
                  "kb": round(sum(c[s]["kb"] for s in g), 1), "has_primary": bool(set(tl) & primary)})
    G.sort(key=lambda g: (not g["has_primary"], g["sources"]))           # X1: groups holding a primary-set type first
    split = []
    for i, g in enumerate(G, 1):
        chunks = [g["types"][j:j + MAX_TYPES] for j in range(0, len(g["types"]), MAX_TYPES)] or [[]]
        for ci, tl in enumerate(chunks):
            split.append(dict(g, types=tl, group=f"g{i:02d}" + ("" if len(chunks) == 1 else "abcdefgh"[ci]), has_primary=bool(set(tl) & primary)))
    G = split
    f_src = sorted((rel_rec.get(FORENSIC_TYPE, set()) | rel_men.get(FORENSIC_TYPE, set())
                    | {s for s in c if L2R.is_dedicated(s) or L2R.is_dedicated(c[s]["doi"])}))
    out = {"rule": "PREREG v5 Part L (L2, L3)", "audited": A, "relevant_sources": rel, "relevant_by_records": {t: sorted(v) for t, v in rel_rec.items()},
           "atlas_slug": at, "atlas_relevant_types": sorted(t for t in types if at in rel[t]),
           "types_without_sources": sorted(t for t in types if not rel[t]), "types_only_atlas": sorted(t for t in types if rel[t] == [at]),
           "groups": G, "forensic_sources": f_src, "stop_names": sorted(STOP_NAMES), "limits": {"max_sources": MAX_SOURCES, "max_kb": MAX_KB},
           "cache_sha256": {s: _sha((SOURCES / s / "text.txt").read_bytes()) for s in sorted(set(srcs) | set(f_src) | {at})
                            if (SOURCES / s / "text.txt").exists()}}
    _write_once(OUT / "ASSIGNMENT.json", json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"n_audited": len(types), **{k: len(v) for k, v in A.items() if k != "all"}, "n_reader_sources": len(srcs),
                      "n_groups": len(G), "web_groups": sum(1 for g in G if g["web_dois"]), "types_without_sources": out["types_without_sources"],
                      "types_only_atlas": len(out["types_only_atlas"]), "n_forensic_sources": len(f_src)}, indent=1))
    return out


# ------------------------------------------------------------------------------------------------------------------- rooms
PROMPTS = {"audit_reader": "PROMPT_REREAD.md", "forensic": "PROMPT_FORENSIC.md", "forensic_adj": "PROMPT_ADJUDICATE_F.md",
           "atlas_code": None, "atlas_adj": "PROMPT_ATLAS_ADJ.md", "type_adj": "PROMPT_TYPE_ADJ.md", "verify": None, "canary": "PROMPT_CANARY.md"}
ATLAS_ADDENDUM = ("\n\nThis is an AUDIT of an earlier coding of the same atlas. `AUDIT_NOTE.md` in your room changes `PROTOCOL.md` for this task "
                  "(read it first; it wins where they differ). `pass_id` is `audit`. You are not told what anyone else coded.\n")
VERIFY_ADDENDUM = ("\n\nThis is an AUDIT. `AUDIT_NOTE.md` in your room changes `PROTOCOL.md` for this task (read it first; it wins where they "
                   "differ; in particular, do not stop reading when you see a simulation score). `verify_sample.csv` also has a `preparation` "
                   "column: code the front-leg rhythm of the experiment in that preparation.\n")


def _type_rows(types: list[str]) -> str:
    tl = {r["manc_type"]: r.get("other_names", "") for r in csv.DictReader(open(KIT / "type_list.csv", encoding="utf-8"))}
    return "\n".join(["manc_type,other_names"] + [f'{t},"{(tl.get(t) or "").replace(chr(34), chr(39))}"' for t in types]) + "\n"


def prompt_for(spec: dict) -> str:
    kind = spec["kind"].removesuffix("_web")
    if kind == "atlas_code":
        t = (KIT / "PROMPT_ATLAS_CODE.md").read_text(encoding="utf-8")
        t = t.replace("{SESSION}", spec["session"]).replace("{PASS_ID}", "audit").replace("{PREFIX}", spec["session"]) + ATLAS_ADDENDUM
    elif kind == "verify":
        t = (KIT / "PROMPT_VERIFY.md").read_text(encoding="utf-8").replace("{SESSION}", spec["session"]) + VERIFY_ADDENDUM
    else:
        t = (AKIT / PROMPTS[kind]).read_text(encoding="utf-8").replace("{SESSION}", spec["session"])
    if spec.get("web_dois"):
        t += ("\n\nThe cached copies of these sources are abstract-only or missing; you MAY fetch exactly these DOIs with WebFetch from the "
              "publisher, PubMed Central, Europe PMC or bioRxiv (never code repositories): " + ", ".join(spec["web_dois"]) + "\n")
    return t


def flags_for(kind: str) -> list[str]:
    """Run 2's frozen flags for the kind (web kinds: `reader_web`), plus deny rules for exam 1's rooms."""
    flags = L2R.flags_v2("reader_web" if kind.endswith("_web") else "reader")
    i = flags.index("--disallowedTools")
    extra = [f"{tool}(/{HOME / 'ledger_rooms' / 'run2'}/**)" for tool in ("Read", "Edit")]
    return flags[: i + 1] + extra + flags[i + 1:]


def build_room(spec: dict) -> Path:
    verify_kit()
    room = ROOMS / spec["session"]
    if room.exists():
        raise SystemExit(f"room {room} exists already; rooms are single-use")
    missing = [s for s in spec.get("sources") or [] if not (SOURCES / s / "meta.json").exists()]
    if missing:
        raise SystemExit(f"{spec['session']}: sources not in the cache: {missing}")
    (room / "out").mkdir(parents=True)
    for name in KIT_FILES:
        if spec["kind"] in MAP_FREE and name != "PROTOCOL.md":
            continue                                                   # L1 / PREREG v2 L8: atlas coders work without the type map
        shutil.copyfile(KIT / name, room / name)
    shutil.copyfile(AKIT / "record_schema.json", room / "record_schema.json")
    shutil.copyfile(AKIT / "AUDIT_NOTE.md", room / "AUDIT_NOTE.md")
    if spec.get("types"):
        (room / "assigned_types.csv").write_text(_type_rows(spec["types"]), encoding="utf-8")
    for name, src in (spec.get("inputs") or {}).items():
        shutil.copyfile(src, room / name)
    rows = ["doi,slug,title,status"]
    for s in spec.get("sources") or []:
        shutil.copytree(SOURCES / s, room / "sources" / s)
        m = json.loads((SOURCES / s / "meta.json").read_text(encoding="utf-8"))
        rows.append(f'{m.get("doi")},{s},"{str(m.get("title") or "").replace(chr(34), chr(39))}",{m.get("status")}')
    (room / "assigned_sources.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (room / "TASK.md").write_text(prompt_for(spec), encoding="utf-8")
    return room


def canary_passed(mode: str) -> bool:
    p = OUT / f"CANARY_{mode}.json"
    return p.exists() and json.loads(p.read_text(encoding="utf-8")).get("verdict") == "pass"


def launch(spec: dict, mode: str = "sandbox") -> dict:
    if mode == "sandbox" and L2R.SCRATCH_HINT is None:
        raise SystemExit("sandbox mode needs LEDGER_SCRATCH (the orchestrator's temporary folder) set before launch; refused")
    if spec["kind"] != "canary" and not canary_passed(mode):
        raise SystemExit(f"no passing canary for mode {mode} (L1); refused")
    room = build_room(spec)
    prompt = prompt_for(spec)
    flags = flags_for(spec["kind"])
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    pid = L2R.spawn(["claude", "-p", prompt, *flags], room, ROOMS / f"{spec['session']}.main.stream.jsonl", mode)
    files = {str(p.relative_to(room)): _sha(p.read_bytes()) for p in sorted(room.rglob("*")) if p.is_file() and p.relative_to(room).parts[0] != "out"}
    man = {"session": spec["session"], "kind": spec["kind"], "group": spec.get("group"), "reader": spec.get("reader"),
           "room": f"~/ledger_rooms/run5/{spec['session']}", "mode": mode, "sources": spec.get("sources") or [], "types": spec.get("types") or [],
           "web_dois": spec.get("web_dois") or [], "flags": [f.replace(str(HOME), "~") for f in flags],
           "runs": [{"tag": "main", "pid": pid, "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "prompt_sha256": _sha(prompt.encode()),
                     "prompt": prompt}], "files": files}
    (MANIFESTS / f"{spec['session']}.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    return man


def _enqueue(specs: list[dict]) -> int:
    QUEUE.mkdir(parents=True, exist_ok=True)
    n = 0
    for i, s in enumerate(specs):
        p = QUEUE / f"{i:03d}_{s['session']}.json"
        if not any(QUEUE.glob(f"*_{s['session']}.json")) and not (MANIFESTS / f"{s['session']}.json").exists():
            p.write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8")
            n += 1
    print(f"enqueued {n} specs")
    return n


def forensic_inputs(tmp: Path) -> dict[str, Path]:
    """L2: every exam 1 record of DNg100 (all fields), verbatim excerpts of the consensus and blind rules, and the frozen aggregate.py."""
    tmp.mkdir(parents=True, exist_ok=True)
    recs = [r for r in exam1_records() if r.get("manc_type") == FORENSIC_TYPE]
    (tmp / "exam1_records_DNg100.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in recs), encoding="utf-8")
    shutil.copyfile(AKIT / "CONSENSUS_RULE.md", tmp / "CONSENSUS_RULE.md")
    shutil.copyfile(AKIT / "BLIND_RULE.md", tmp / "BLIND_RULE.md")
    shutil.copyfile(REPO / "ledger" / "src" / "brainir_ledger" / "labels" / "aggregate.py", tmp / "aggregate.py.txt")
    return {n: tmp / n for n in ("exam1_records_DNg100.jsonl", "CONSENSUS_RULE.md", "BLIND_RULE.md", "aggregate.py.txt")}


def enqueue() -> int:
    """X1's first batch: forensic F1/F2, atlas coders A/B, then readers A/B of every group (groups holding a primary-set type first)."""
    a = json.loads((OUT / "ASSIGNMENT.json").read_text(encoding="utf-8"))
    c = cache()
    specs = []
    fweb = sorted(c[s]["doi"] for s in a["forensic_sources"] if c[s]["status"] in WEB_STATUSES)
    for f in ("F1", "F2"):
        specs.append({"session": f"a5-{f}", "kind": "forensic_web" if fweb else "forensic", "sources": a["forensic_sources"], "web_dois": fweb,
                      "inputs": {k: str(v) for k, v in forensic_inputs(ROOMS / "_inputs" / f).items()}})
    for coder in ("A", "B"):
        specs.append({"session": f"a5-atlas-{coder}", "kind": "atlas_code", "reader": coder, "sources": [a["atlas_slug"]],
                      "inputs": {"atlas_line_ids.csv": str(LAB2 / "work" / "atlas" / "atlas_line_ids.csv")}})
    for g in a["groups"]:
        for rd in ("A", "B"):
            specs.append({"session": f"a5-{g['group']}-{rd}", "kind": "audit_reader_web" if g["web_dois"] else "audit_reader", "group": g["group"],
                          "reader": rd, "sources": g["sources"], "types": g["types"], "web_dois": g["web_dois"]})
    return _enqueue(specs)


def _alive_sessions() -> list[str]:
    out = []
    for m in sorted(MANIFESTS.glob("*.json")):
        man = json.loads(m.read_text(encoding="utf-8"))
        if any(L2R._alive(r["pid"]) for r in man["runs"]):
            out.append(man["session"])
    return out


def quota() -> float | None:
    """Latest seven-day utilisation reported to any run 5 session (rate_limit_event lines; as run 2's `labels2_rooms.quota`)."""
    best = None
    for log in ROOMS.glob("*.stream.jsonl"):
        for line in log.read_text(errors="replace").splitlines():
            if '"rate_limit_event"' in line:
                try:
                    u = json.loads(line)["rate_limit_info"]["unifiedWindows"]["seven_day"]["utilization"]
                    best = u if best is None else max(best, u)
                except (KeyError, TypeError, json.JSONDecodeError):
                    pass
    return best


def schedule(max_alive: int = 6, mode: str = "sandbox") -> None:
    """Launch queued specs in queue order while fewer than `max_alive` run (at most 3 above 85 % of the seven-day quota, as run 2)."""
    while True:
        alive = _alive_sessions()
        queued = sorted(QUEUE.glob("*.json"))
        if not queued and not alive:
            print("queue empty and nothing running; scheduler exits", flush=True)
            return
        q = quota()
        cap = max_alive if (q is None or q < 0.85) else min(3, max_alive)
        for qf in queued[: max(0, cap - len(alive))]:
            spec = json.loads(qf.read_text(encoding="utf-8"))
            try:
                launch(spec, mode)
                msg = "launched"
                qf.unlink()
            except SystemExit as e:
                msg = f"refused, spec kept in _queue_failed ({e})"
                (ROOMS / "_queue_failed").mkdir(parents=True, exist_ok=True)
                qf.rename(ROOMS / "_queue_failed" / qf.name)
            print(time.strftime("%H:%M:%S"), msg, spec["session"], f"(cap {cap}, quota {q})", flush=True)
            time.sleep(5)
        time.sleep(30)


def _model_used(session: str) -> list[str]:
    models = set()
    for log in sorted(ROOMS.glob(f"{session}.*.stream.jsonl")):
        for d in _jsonl(log):
            m = d.get("model") or ((d.get("message") or {}).get("model") if isinstance(d.get("message"), dict) else None)
            if isinstance(m, str):
                models.add(m)
    return sorted(models)


def status() -> list[dict]:
    rows = []
    for m in sorted(MANIFESTS.glob("*.json")):
        man = json.loads(m.read_text(encoding="utf-8"))
        room = ROOMS / man["session"]
        rows.append({"session": man["session"], "alive": any(L2R._alive(r["pid"]) for r in man["runs"]), "done": (room / "out" / "DONE").exists(),
                     "n_records": len(_jsonl(room / "out" / "records.jsonl")), "files_out": sorted(p.name for p in (room / "out").glob("*"))})
    print(json.dumps({"queued": len(list(QUEUE.glob("*.json"))), "alive": sum(r["alive"] for r in rows), "done": sum(r["done"] for r in rows),
                      "sessions": rows}, indent=1))
    return rows


def collect() -> None:
    for m in sorted(MANIFESTS.glob("*.json")):
        man = json.loads(m.read_text(encoding="utf-8"))
        s = man["session"]
        dest = OUT / "sessions" / s
        if dest.exists() or any(L2R._alive(r["pid"]) for r in man["runs"]):
            continue
        room = ROOMS / s
        shutil.copytree(room / "out", dest)
        logs = {p.name: _sha(p.read_bytes()) for p in sorted(ROOMS.glob(f"{s}.*"))}
        man2 = dict(man, out_sha256={str(p.relative_to(dest)): _sha(p.read_bytes()) for p in sorted(dest.rglob("*")) if p.is_file()},
                    logs_sha256=logs, models_used=_model_used(s), collected_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    done=(room / "out" / "DONE").exists())
        _write_once(OUT / "rooms" / f"{s}.json", json.dumps(man2, indent=1) + "\n")
        print("collected", s, "models", man2["models_used"], "done", man2["done"])


def audit_one(man: dict) -> dict:
    """PREREG v5 L1: run 1's frozen `labels_audit.audit_session` with run 2's single exception (`labels2_audit`): a successful read of a
    file in the session's OWN tool-results folder that its own WebFetch saved is not a breach; run 2's fetches of mirrors stay breaches.
    Run 2's forbidden-token rule (v2 L3 kind 5) does not apply: this audit's sessions may read everything about the simulations (hard
    limit 4). Dedicated sources are allowed in every room (family set to the dedicated one)."""
    import labels2_audit as L2A  # noqa: PLC0415  (frozen: scan)
    import labels_audit as LA  # noqa: PLC0415  (frozen)
    import labels_collect as LC  # noqa: PLC0415  (frozen: BREACH_KINDS)

    room = str(ROOMS / man["session"])
    r = LA.audit_session({**man, "room": room, "pass": "audit", "family": "pugliese_dedicated"})
    texts, extra = L2A.scan(room)
    breaches = [i for i in extra if i["kind"] == "banned_host_fetch"]
    if not r["transcripts"]:
        breaches.append({"kind": "no_transcript"})
    own_dir, own_reads = str(LA.PROJECTS / LA.encode(room)), 0
    for i in r["issues"]:
        p = str(i.get("path") or "")
        if i["kind"] == "file_outside_room" and p.startswith(own_dir + "/") and "/tool-results/" in p and any(p in x for x in texts):
            own_reads += 1
            continue
        if i["kind"] in LC.BREACH_KINDS:
            breaches.append({k: (str(v).replace(str(HOME), "~") if isinstance(v, str) else v) for k, v in i.items()})
    return {"session": man["session"], "kind": man["kind"], "breach": bool(breaches), "issues": breaches, "own_tool_result_reads": own_reads,
            "blocked_attempts": len(r["blocked_attempts"]), "n_tool_calls": r["n_tool_calls"], "n_fetches": r["n_fetches"], "transcripts": len(r["transcripts"])}


def transcript_audit() -> dict:
    """L1 on every collected session; written (and rewritten) to labels_audit_v1/TRANSCRIPT_AUDIT.json as sessions are added."""
    rows = {}
    for m in sorted((OUT / "rooms").glob("*.json")):
        man = json.loads(m.read_text(encoding="utf-8"))
        rows[man["session"]] = audit_one(man)
    out = {"rule": "PREREG v5 L1 (run 1's frozen audit with run 2's own-tool-results exception)", "sessions": rows,
           "breaching_sessions": sorted(s for s, a in rows.items() if a["breach"]), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT / "TRANSCRIPT_AUDIT.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"n": len(rows), "breaching": out["breaching_sessions"],
                      "blocked_attempts": {s: a["blocked_attempts"] for s, a in rows.items() if a["blocked_attempts"]}}, indent=1))
    return out


# ------------------------------------------------------------------------------------------------------------- replacements
def _norm_doi(d: str) -> str:
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", str(d or "").strip().lower())


def disposed(session: str) -> set[str]:
    """Normalised DOIs to which the session's `out/dispositions.csv` gives any disposition (records, no_qualifying_experiment,
    unreachable)."""
    p = OUT / "sessions" / session / "dispositions.csv"
    if not p.exists():
        return set()
    return {_norm_doi(r.get("doi")) for r in csv.DictReader(open(p, encoding="utf-8")) if (r.get("disposition") or "").strip()}


def _base(session: str) -> str:
    return re.sub(r"-r[12]$", "", session)


def replace() -> int:
    """L1/L3: for every reader, atlas-coder, adjudicator or verifier lineage whose non-breaching sessions leave assigned sources without a
    disposition (a breaching session counts as giving none), a replacement session (-r1, then -r2) with exactly those sources."""
    br = set(json.loads((OUT / "TRANSCRIPT_AUDIT.json").read_text(encoding="utf-8"))["breaching_sessions"])
    c = cache()
    mans = {json.loads(m.read_text(encoding="utf-8"))["session"]: json.loads(m.read_text(encoding="utf-8")) for m in sorted((OUT / "rooms").glob("*.json"))}
    specs = []
    for base in sorted({_base(s) for s in mans if not s.startswith(("a5-canary", "a5-F"))}):
        lineage = [s for s in (base, f"{base}-r1", f"{base}-r2") if s in mans]
        if len(lineage) == 3 or any(any(L2R._alive(r["pid"]) for r in json.loads((MANIFESTS / f"{s}.json").read_text(encoding="utf-8"))["runs"])
                                    for s in (base, f"{base}-r1", f"{base}-r2") if (MANIFESTS / f"{s}.json").exists()):
            continue
        first = mans[base]
        done = set().union(*[disposed(s) for s in lineage if s not in br])
        left = [s for s in first["sources"] if _norm_doi(c[s]["doi"]) not in done]
        if not left:
            continue
        nxt = f"{base}-r{len(lineage)}"
        spec = {k: first.get(k) for k in ("kind", "group", "reader")} | {"session": nxt, "sources": left}
        if first.get("types"):
            spec["types"] = first["types"]
        web = sorted(c[s]["doi"] for s in left if c[s]["status"] in WEB_STATUSES)
        spec["web_dois"] = web
        spec["kind"] = spec["kind"].removesuffix("_web") + ("_web" if web and not spec["kind"].startswith(("atlas", "canary")) else "")
        inputs = {}
        for name in first.get("files", {}):
            if "/" not in name and name not in ("TASK.md", "assigned_sources.csv", "assigned_types.csv", "record_schema.json", "AUDIT_NOTE.md", *KIT_FILES):
                inputs[name] = str(ROOMS / base / name)
        spec["inputs"] = inputs
        specs.append(spec)
    return _enqueue(specs)


def unread_types() -> list[str]:
    """L4 (c): audited types with a relevant source that no non-breaching session (any reader or atlas-coder lineage) gave a disposition."""
    a = json.loads((OUT / "ASSIGNMENT.json").read_text(encoding="utf-8"))
    br = set(json.loads((OUT / "TRANSCRIPT_AUDIT.json").read_text(encoding="utf-8"))["breaching_sessions"])
    c = cache()
    done = set()
    for sd in (OUT / "sessions").glob("a5-*"):
        if sd.name not in br and (sd.name.startswith("a5-g") or sd.name.startswith("a5-atlas-")):
            done |= disposed(sd.name)
    return sorted(t for t in a["audited"]["all"] if any(_norm_doi(c[s]["doi"]) not in done for s in a["relevant_sources"][t]))


# ------------------------------------------------------------------------------------------------------------------- canary
def canary(mode: str = "sandbox") -> dict:
    """L1: a canary session in the readers' mode tries to read a planted file in another run 5 room, a run 2 room's records, the repository
    and the orchestrator's folder; it must fail on all of them (transcript audit: no successful access outside its room)."""
    token = secrets.token_hex(8)
    planted = ROOMS / "_canary_planted" / "planted.txt"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_text(f"canary token {token}\n", encoding="utf-8")
    run2 = sorted((HOME / "ledger_rooms" / "run2").glob("*/out/records.jsonl"))
    # sandbox: every target must be blocked; tool mode: only what its deny rules cover (run 2 rooms, the repository, the orchestrator's
    # folder); sibling run 5 rooms are then policed by the transcript audit (L1)
    targets = ([str(planted)] if mode == "sandbox" else []) + [str(run2[0]) if run2 else str(HOME / "ledger_rooms" / "run2"), str(REPO / "README.md")]
    if L2R.SCRATCH_HINT:
        targets.append(str(L2R.SCRATCH_HINT))
    tf = ROOMS / "_inputs" / "canary_targets.txt"
    tf.parent.mkdir(parents=True, exist_ok=True)
    tf.write_text("\n".join(targets) + "\n", encoding="utf-8")
    sess = f"a5-canary-{time.strftime('%H%M%S')}"
    launch({"session": sess, "kind": "canary", "inputs": {"targets.txt": str(tf)}}, mode)
    print("canary launched:", sess, "(wait for it to finish, then: audit5_rooms.py canary-check", sess, ")")
    return {"session": sess, "token_sha256": _sha(token.encode())}


def canary_check(sess: str) -> dict:
    import labels_audit as LA  # noqa: PLC0415

    man = json.loads((MANIFESTS / f"{sess}.json").read_text(encoding="utf-8"))
    if any(L2R._alive(r["pid"]) for r in man["runs"]):
        raise SystemExit("canary still running")
    a = LA.audit_session({**man, "room": str(ROOMS / sess), "pass": "audit", "family": "pugliese_dedicated"})
    token = (ROOMS / "_canary_planted" / "planted.txt").read_text(encoding="utf-8").split()[-1]
    leaked = any(token in p.read_text(encoding="utf-8", errors="replace") for p in (ROOMS / sess / "out").rglob("*") if p.is_file())
    leaked |= any(token in p.read_text(encoding="utf-8", errors="replace") for p in ROOMS.glob(f"{sess}.*.stream.jsonl"))
    ran = bool(a["transcripts"]) and a["n_tool_calls"] > 0
    out = {"session": sess, "mode": man["mode"], "ran": ran, "successful_outside_accesses": a["issues"], "blocked_attempts": a["blocked_attempts"],
           "token_leaked": leaked, "verdict": "pass" if ran and not a["issues"] and not leaked else ("did_not_run" if not ran else "fail"),
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    p = OUT / f"CANARY_{man['mode']}.json"
    (OUT / p.name).parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1))
    return out


# ------------------------------------------------------------------------------------------------- adjudication / verification
def adjudicate_f() -> None:
    """L2: F3 gets both forensic reports and the same inputs and sources (run only if F1 and F2 chose different sets of explanations)."""
    a = json.loads((OUT / "ASSIGNMENT.json").read_text(encoding="utf-8"))
    rep = {f"report_{f}.md": OUT / "sessions" / f"a5-{f}" / "forensic.md" for f in ("F1", "F2")}
    if not all(p.exists() for p in rep.values()):
        raise SystemExit("collect F1 and F2 first (both forensic.md files are needed)")
    sets = []
    for f in ("F1", "F2"):
        ex = OUT / "sessions" / f"a5-{f}" / "explanations.csv"
        rows = list(csv.DictReader(open(ex, encoding="utf-8"))) if ex.exists() else []
        sets.append({(r.get("explanation") or "").strip().lower() for r in rows if (r.get("chosen") or "").strip().lower() == "yes"} if rows else None)
    if sets[0] is not None and sets[0] == sets[1]:
        print(f"F1 and F2 chose the same explanations {sorted(sets[0])}; no F3 (L2)")
        return
    c = cache()
    fweb = sorted(c[s]["doi"] for s in a["forensic_sources"] if c[s]["status"] in WEB_STATUSES)
    inputs = {k: str(v) for k, v in forensic_inputs(ROOMS / "_inputs" / "F3").items()} | {k: str(v) for k, v in rep.items()}
    _enqueue([{"session": "a5-F3", "kind": "forensic_adj_web" if fweb else "forensic_adj", "sources": a["forensic_sources"], "web_dois": fweb,
               "inputs": inputs}])


def adjudicate_atlas() -> None:
    """L3: keys (line, headless|intact) on which atlas coders A and B differ in any leg field go to an atlas adjudicator with both codings."""
    import labels_audit_v1 as LV  # noqa: PLC0415

    a = json.loads((OUT / "ASSIGNMENT.json").read_text(encoding="utf-8"))
    sides, disputed = LV.atlas_sides()
    if not disputed:
        print("no atlas key in dispute; no adjudicator needed")
        return
    d = ROOMS / "_inputs" / "atlas_adj"
    d.mkdir(parents=True, exist_ok=True)
    for tag in ("A", "B"):
        (d / f"coder_{tag}.jsonl").write_text("".join(json.dumps(sides[tag][k], sort_keys=True) + "\n" for k in disputed if k in sides[tag]), encoding="utf-8")
    (d / "disputed_keys.csv").write_text("line_id,preparation\n" + "".join(f"{k[0]},{k[1]}\n" for k in disputed), encoding="utf-8")
    _enqueue([{"session": "a5-atlas-C", "kind": "atlas_adj", "sources": [a["atlas_slug"]],
               "inputs": {"coder_A.jsonl": str(d / "coder_A.jsonl"), "coder_B.jsonl": str(d / "coder_B.jsonl"),
                          "disputed_keys.csv": str(d / "disputed_keys.csv"), "atlas_line_ids.csv": str(LAB2 / "work" / "atlas" / "atlas_line_ids.csv")}}])


def adjudicate_types() -> None:
    """L3: every audited type whose reader-A and reader-B labels differ at the scope that matters goes to a type adjudicator (blind to exam
    1), given both readers' records of the type and the sources those records cite (atlas excluded), at most 4 sources (one type) per
    session; a type whose records cite more is split over sessions."""
    import labels_audit_v1 as LV  # noqa: PLC0415

    a = json.loads((OUT / "ASSIGNMENT.json").read_text(encoding="utf-8"))
    c = cache()
    d2s = doi_to_slug(c)
    disputed = LV.disputed_types()
    if not disputed:
        print("no type in dispute")
        return
    recs = LV.counted(LV.reader_records()[0])
    specs, k = [], 0
    for t in disputed:
        mine = [r for r in recs if r.get("manc_type") == t]
        cited = sorted({d2s[_norm_doi(r.get("doi"))] for r in mine if _norm_doi(r.get("doi")) in d2s} - {a["atlas_slug"]})
        if not cited:
            print(f"{t}: the readers' records cite no non-atlas cached source; no adjudicator (its label goes to verification if not clear)")
            continue
        for j0 in range(0, len(cited), MAX_SOURCES):
            k += 1
            srcs = cited[j0:j0 + MAX_SOURCES]
            dois = {_norm_doi(c[x]["doi"]) for x in srcs}
            d = ROOMS / "_inputs" / f"type_adj_{k:02d}"
            d.mkdir(parents=True, exist_ok=True)
            for tag in ("A", "B"):
                rows = [{kk: v for kk, v in r.items() if kk not in ("schema_errors", "quote_status", "audit_line", "group", "reader", "session")}
                        for r in mine if r.get("reader") == tag and _norm_doi(r.get("doi")) in dois]
                (d / f"reader_{tag}_records.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
            web = sorted(c[x]["doi"] for x in srcs if c[x]["status"] in WEB_STATUSES)
            specs.append({"session": f"a5-adj-{k:02d}", "kind": "type_adj_web" if web else "type_adj", "types": [t], "sources": srcs, "web_dois": web,
                          "inputs": {"reader_A_records.jsonl": str(d / "reader_A_records.jsonl"), "reader_B_records.jsonl": str(d / "reader_B_records.jsonl")}})
    _enqueue(specs)


def verify() -> None:
    """L4 (b): for every primary-set type whose audited label at exam 1's scope is not yes or no (including nothing recorded), a verifier gets
    exam 1's records behind the label (DOI, locator, quote, driver lines, preparation, name in the paper; no leg field) and its sources,
    at most 8 records per session. A second call sends the records without a verifier answer once more (round 2); after that a type
    without a verifier answer counts as an error."""
    import labels_audit_v1 as LV  # noqa: PLC0415

    c = cache()
    d2s = doi_to_slug(c)
    rows = LV.verification_rows()
    have = LV._verifier_values()
    round_ = 2 if any((OUT / "sessions").glob("a5-verify1-*")) else 1
    if round_ == 2:
        if any((OUT / "sessions").glob("a5-verify2-*")) or any(QUEUE.glob("*a5-verify2-*")):
            print("verification already ran twice; nothing more")
            return
        rows = [r for r in rows if not have.get(r["exp_id"])]
    if not rows:
        print("nothing to verify")
        return
    specs = []
    for i in range(0, len(rows), 8):
        chunk = rows[i:i + 8]
        d = ROOMS / "_inputs" / f"verify{round_}_{i // 8 + 1:02d}"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "verify_sample.csv", "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["exp_id", "doi", "source_locator", "driver_lines", "name_in_paper", "quote", "preparation"])
            w.writeheader()
            for r in chunk:
                w.writerow({k: r[k] for k in w.fieldnames})
        srcs = sorted({d2s[_norm_doi(r["doi"])] for r in chunk})
        web = sorted(c[x]["doi"] for x in srcs if c[x]["status"] in WEB_STATUSES)
        specs.append({"session": f"a5-verify{round_}-{i // 8 + 1:02d}", "kind": "verify_web" if web else "verify", "sources": srcs, "web_dois": web,
                      "inputs": {"verify_sample.csv": str(d / "verify_sample.csv")}})
    _enqueue(specs)


# ---------------------------------------------------------------------------------------------------------------- quotes
def norm_text(s: str) -> str:
    """Quote check normalisation: NFKC, lower case, soft hyphens and line-break hyphenation removed, every non-alphanumeric run -> one space."""
    s = unicodedata.normalize("NFKC", s or "").replace("­", "")
    s = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", s)
    return re.sub(r"[^0-9a-z]+", " ", s.lower()).strip()


def source_corpus(slug: str) -> str:
    parts = []
    for p in [SOURCES / slug / "text.txt", *sorted((SOURCES / slug / "supp").glob("*"))]:
        if p.is_file() and p.suffix.lower() in (".txt", ".csv", ".tsv", ".md", ""):
            parts.append(p.read_text(encoding="utf-8", errors="replace"))
    return norm_text("\n".join(parts))


def quote_status(rec: dict, corpus: dict[str, str], d2s: dict[str, str]) -> str:
    """'found' (normalised quote of at least 8 characters inside the source's text or text supplements), 'figure' (notes start 'figure:'),
    else 'not_found'."""
    slug = d2s.get(str(rec.get("doi") or "").lower())
    q = norm_text(str(rec.get("quote") or ""))
    if slug and q and len(q) >= 8:
        if slug not in corpus:
            corpus[slug] = source_corpus(slug)
        if q in corpus[slug]:
            return "found"
    if str(rec.get("notes") or "").strip().lower().startswith("figure:"):
        return "figure"
    return "not_found"


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[:1]
    mode = "tool" if "--tool-mode" in a else "sandbox"
    if cmd == ["plan"]:
        plan()
    elif cmd == ["kit-manifest"]:
        kit_manifest()
    elif cmd == ["canary"]:
        canary(mode)
    elif cmd == ["canary-check"]:
        canary_check(a[1])
    elif cmd == ["enqueue"]:
        enqueue()
    elif cmd == ["schedule"]:
        schedule(int(a[a.index("--max") + 1]) if "--max" in a else 6, mode)
    elif cmd == ["status"]:
        status()
    elif cmd == ["collect"]:
        collect()
    elif cmd == ["transcript-audit"]:
        transcript_audit()
    elif cmd == ["replace"]:
        replace()
    elif cmd == ["unread"]:
        print(json.dumps(unread_types(), indent=1))
    elif cmd == ["adjudicate-f"]:
        adjudicate_f()
    elif cmd == ["adjudicate-atlas"]:
        adjudicate_atlas()
    elif cmd == ["adjudicate-types"]:
        adjudicate_types()
    elif cmd == ["verify"]:
        verify()
    else:
        raise SystemExit(__doc__)
