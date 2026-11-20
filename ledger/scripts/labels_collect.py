"""Collect, validate and aggregate blind labels (LABEL SIDE: never reads predictions). The orchestrator runs this; it never
writes, edits or adjudicates a label: everything here is deterministic.

    uv run --project ledger --no-sync python ledger/scripts/labels_collect.py collect      # copy room outputs, assign exp_id, validate
    uv run --project ledger --no-sync python ledger/scripts/labels_collect.py finalize     # dedupe, merge passes, consensus, agreement

collect  -> research/ledger/labels/raw/<pass>/<session>/ (verbatim copies of out/*, records.valid.jsonl with exp_id,
            validation.json listing invalid lines and error kinds without label values); for pass 2 the records and the
            not-found list come from the Phase A snapshot taken before the quotes were delivered (a later change is flagged);
            research/ledger/labels/sessions/ (manifests and the models each session actually used).
finalize -> research/ledger/labels/{records.jsonl, type_labels.csv, sources.csv, synonyms.csv, driver_lines.csv, agreement.md,
            agreement.json, merge_log.json, spot_check_sample.csv, search_only_records.jsonl}. Refuses unless the transcript
            audit exists, covers every session and is newer than every session log.
Breach rule (PREREG section 6): records of a pass-1 session whose transcript audit shows a breach, and experiments read by a
breaching pass-2 / adjudication session, are excluded from the consensus and reported.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ledger" / "src"))
from brainir_ledger.labels import aggregate as AGG  # noqa: E402
from brainir_ledger.labels.agreement import agreement  # noqa: E402
from brainir_ledger.labels.schema import validate_record  # noqa: E402

KIT = REPO / "research" / "ledger" / "kit"
LAB = REPO / "research" / "ledger" / "labels"
RAW = LAB / "raw"
ROOMS = Path.home() / "ledger_rooms" / "run1"
SPOT_SEED = 20261126
BREACH_KINDS = ("file_outside_room", "banned_host_fetch", "dedicated_source_outside_dedicated_session", "no_transcript")
TRUE_WORDS = {"true", "t", "yes", "y", "1", "found"}
FALSE_WORDS = {"false", "f", "no", "n", "0", "not found", "not_found"}


def known_types() -> set[str]:
    return set(pd.read_csv(KIT / "type_list.csv")["manc_type"])


def read_csv_rows(path: Path, required: list[str]) -> tuple[list[dict], list[str]]:
    """Tolerant CSV reader: UTF-8 with or without BOM; a file without the expected header is read with `required` as header."""
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return [], []
    head = [h.strip().lower() for h in rows[0]]
    notes = []
    if all(r in head for r in required):
        idx = {h: i for i, h in enumerate(head)}
        body = rows[1:]
    else:
        notes.append(f"{path.name}: no header row; read as {required}")
        idx = {h: i for i, h in enumerate(required)}
        body = rows
    out = []
    for r in body:
        if not any(c.strip() for c in r):
            continue
        out.append({h: (r[i].strip() if i < len(r) else "") for h, i in idx.items()})
    return out, notes


def validate_lines(lines: list[str], kt: set[str], session: str, pass_id: str) -> tuple[list[dict], list[dict]]:
    good, bad, seen = [], [], set()
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            bad.append({"line": i, "errors": ["invalid JSON"]})
            continue
        if not isinstance(r, dict):
            bad.append({"line": i, "errors": ["line is not a JSON object (one record per line)"]})
            continue
        errs = validate_record(r, kt)
        if pass_id in ("pass1", "search"):
            rid = r.get("record_id")
            if rid in seen:
                errs.append("record_id is not unique in this session")
            seen.add(rid)
            r["exp_id"] = f"{session}:{rid}"
        elif not r.get("exp_id"):
            errs.append("exp_id missing (copy it from the input file)")
        (bad.append({"line": i, "errors": errs}) if errs else good.append(r))
    return good, bad


def collect() -> None:
    kt = known_types()
    sess_dir = LAB / "sessions"
    sess_dir.mkdir(parents=True, exist_ok=True)
    for man in sorted((ROOMS / "_manifests").glob("*.json")):
        m = json.loads(man.read_text(encoding="utf-8"))
        shutil.copyfile(man, sess_dir / man.name)
        room, session, pass_id = Path(m["room"]), m["session"], m["pass"]
        dest = RAW / pass_id / session
        dest.mkdir(parents=True, exist_ok=True)
        for f in sorted((room / "out").glob("*")):
            if f.is_file():
                shutil.copyfile(f, dest / f.name)
        info: dict = {}
        src = dest / "records.jsonl"
        snap = dest / "phaseA_snapshot"
        if pass_id == "pass2" and (snap / "records.jsonl").exists():
            h = json.loads((snap / "phaseA_hashes.json").read_text(encoding="utf-8"))["sha256"]
            cur = hashlib.sha256(src.read_bytes()).hexdigest() if src.exists() else None
            info["phase_a_snapshot_used"] = True
            info["phase_a_changed_after_quotes"] = cur != h.get("records.jsonl")
            src = snap / "records.jsonl"
        if not src.exists():
            print(f"{session}: no records")
            continue
        good, bad = validate_lines(src.read_text(encoding="utf-8-sig", errors="replace").splitlines(), kt, session, pass_id)
        with open(dest / "records.valid.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for r in good:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
        (dest / "validation.json").write_text(json.dumps({"n_valid": len(good), "n_invalid": len(bad), "invalid": bad, **info}, indent=1) + "\n",
                                              encoding="utf-8", newline="\n")
        print(f"{session}: {len(good)} valid, {len(bad)} invalid {info if info else ''}")
    status = ROOMS / "_status.json"
    if status.exists():
        shutil.copyfile(status, sess_dir / "_status.json")


def _read(pass_id: str) -> list[dict]:
    out = []
    for sd in sorted((RAW / pass_id).glob("*")):
        p = sd / "records.valid.jsonl"
        if p.exists():
            out += [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return out


def norm_doi(d: str) -> str:
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    return re.sub(r"\.\d+$", "", d) if d.startswith("10.7554/elife.") else d  # eLife reviewed-preprint versions


def capture_recapture(first: list[dict], second: list[dict]) -> dict:
    """Chapman estimator at the (normalised DOI, MANC type) level (PREREG section 6); the dedicated family is excluded (the
    search sessions may not open its sources)."""
    a = {(norm_doi(r["doi"]), r["manc_type"]) for r in first if not r["exp_id"].startswith("pass1-pugliese_dedicated:")}
    b = {(norm_doi(r["doi"]), r["manc_type"]) for r in second}
    m, n1, n2 = len(a & b), len(a), len(b)
    chapman = (n1 + 1) * (n2 + 1) / (m + 1) - 1 if (n1 or n2) else None
    return {"unit": "(normalised doi, manc_type)", "estimator": "Chapman", "n_first": n1, "n_search": n2, "n_both": m,
            "estimated_total": chapman, "estimated_missed_by_both": (chapman - len(a | b)) if chapman is not None else None,
            "n_found_only_by_search": len(b - a)}


def breaching_sessions() -> dict[str, list]:
    p = LAB / "transcript_audit.json"
    if not p.exists():
        raise SystemExit("finalize refused: run ledger/scripts/labels_audit.py first")
    rows = json.loads(p.read_text(encoding="utf-8"))
    audited = {r["session"] for r in rows}
    mans = {m.stem for m in (ROOMS / "_manifests").glob("*.json")}
    if mans - audited:
        raise SystemExit(f"finalize refused: the transcript audit does not cover {sorted(mans - audited)}")
    newest_log = max((f.stat().st_mtime for f in ROOMS.glob("*.stream.jsonl")), default=0)
    if p.stat().st_mtime < newest_log:
        raise SystemExit("finalize refused: the transcript audit is older than a session log; re-run labels_audit.py")
    return {r["session"]: [i for i in r["issues"] if i["kind"] in BREACH_KINDS] for r in rows if any(i["kind"] in BREACH_KINDS for i in r["issues"])}


def quote_checks() -> tuple[dict[str, bool | None], dict]:
    qc, log = {}, {"unrecognised_values": [], "notes": []}
    for sd in sorted((RAW / "pass2").glob("*")):
        rows, notes = read_csv_rows(sd / "quote_checks.csv", ["exp_id", "quote_found", "where", "comment"])
        log["notes"] += notes
        for row in rows:
            v = row.get("quote_found", "").strip().lower()
            if v in TRUE_WORDS:
                qc[row["exp_id"]] = True
            elif v in FALSE_WORDS:
                qc[row["exp_id"]] = False
            else:
                qc[row["exp_id"]] = None
                log["unrecognised_values"].append(row["exp_id"])
    return qc, log


def not_found() -> tuple[set[str], list[str]]:
    out, notes = set(), []
    for sd in sorted((RAW / "pass2").glob("*")):
        src = sd / "phaseA_snapshot" / "not_found.csv" if (sd / "phaseA_snapshot").exists() else sd / "not_found.csv"
        rows, n = read_csv_rows(src, ["exp_id", "reason"])
        notes += n
        out |= {r["exp_id"] for r in rows if r.get("exp_id")}
    return out, notes


def proposals(name: str, required: list[str]) -> tuple[pd.DataFrame, list[str]]:
    frames, notes = [], []
    for p in sorted(RAW.glob(f"*/*/{name}")):
        rows, n = read_csv_rows(p, required)
        notes += n
        if rows:
            frames.append(pd.DataFrame(rows).assign(status="proposed", session=p.parent.name))
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()), notes


def finalize() -> None:
    breach = breaching_sessions()
    p1_all = [r for r in _read("pass1") if r["exp_id"].split(":", 1)[0] not in breach]
    p1, dup_log = AGG.dedupe_pass1(p1_all)
    p2 = _read("pass2")
    adj = _read("adjudication")
    tainted = set()
    for s in (s for s in breach if s.startswith(("pass2", "adjudication"))):
        f = RAW / s.split("-", 1)[0] / s / "records.valid.jsonl"
        if f.exists():
            tainted |= {json.loads(ln)["exp_id"] for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()}
    p1 = [r for r in p1 if r["exp_id"] not in tainted]
    qc, qlog = quote_checks()
    nf, nf_notes = not_found()
    final, log = AGG.merge_passes(p1, p2, adj, qc, nf)
    ex = pd.read_csv(KIT / "exposed_types.csv")
    exposed = {t for s in ex["manc_types"].dropna() for t in str(s).split(";") if t}
    tl = AGG.type_labels(final, exposed=exposed, type_list=sorted(known_types()))
    search = _read("search")
    p1keys = {(norm_doi(r["doi"]), r["manc_type"]) for r in p1}
    search_only = [r for r in search if (norm_doi(r["doi"]), r["manc_type"]) not in p1keys]
    ag = agreement(p1, p2)
    cr = capture_recapture(p1, search)
    syn = pd.read_csv(KIT / "synonyms.csv").assign(status="kit")
    sprops, s_notes = proposals("proposed_synonyms.csv", ["manc_type", "name", "kind", "source_doi", "locator"])
    dl = pd.read_csv(KIT / "driver_lines.csv").assign(status="kit")
    dprops, d_notes = proposals("proposed_driver_lines.csv", ["line_id", "manc_type", "other_cells", "source_doi", "locator"])
    srcs: dict[str, dict] = {}
    for sd in sorted(RAW.glob("*/*")):
        rows, _ = read_csv_rows(sd / "sources.csv", ["doi", "title", "year", "source_type", "access", "n_records", "notes"])
        for row in rows:
            d = norm_doi(row.get("doi") or "")
            if d:
                e = srcs.setdefault(d, {**row, "doi": d, "sessions": set()})
                e["sessions"].add(sd.name)
    # everything computed: write all outputs
    LAB.mkdir(parents=True, exist_ok=True)
    with open(LAB / "records.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in sorted(final, key=lambda r: (r["manc_type"], r["exp_id"])):
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    tl.to_csv(LAB / "type_labels.csv", index=False, lineterminator="\n")
    with open(LAB / "search_only_records.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in search_only:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    summary = {"agreement": ag, "capture_recapture": cr, "merge_log_counts": {k: len(v) for k, v in log.items()},
               "pass1_duplicates_dropped": len(dup_log), "breaching_sessions": breach, "tainted_experiments": len(tainted),
               "quote_check_log": {"n_unrecognised": len(qlog["unrecognised_values"]), "notes": qlog["notes"]},
               "csv_notes": nf_notes + s_notes + d_notes}
    (LAB / "agreement.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
    (LAB / "merge_log.json").write_text(json.dumps({"merge": log, "pass1_duplicates": dup_log, "quote_checks": qlog}, indent=1) + "\n",
                                        encoding="utf-8", newline="\n")
    rows = [{**{k: v for k, v in r.items() if k != "sessions"}, "sessions": ";".join(sorted(r["sessions"])),
             "n_final_records": sum(1 for x in final if norm_doi(x["doi"]) == d)} for d, r in sorted(srcs.items())]
    pd.DataFrame(rows).to_csv(LAB / "sources.csv", index=False, lineterminator="\n")
    pd.concat([syn, sprops], ignore_index=True).to_csv(LAB / "synonyms.csv", index=False, lineterminator="\n")
    pd.concat([dl, dprops], ignore_index=True).to_csv(LAB / "driver_lines.csv", index=False, lineterminator="\n")
    rng = np.random.default_rng(SPOT_SEED)
    pick = sorted(rng.choice(len(final), size=min(20, len(final)), replace=False)) if final else []
    pd.DataFrame([{k: final[i].get(k) for k in ("exp_id", "manc_type", "name_in_paper", "doi", "source_locator", "quote", "driver_lines",
                                                "preparation", "front_leg_rhythm", "middle_leg_rhythm", "hind_leg_rhythm",
                                                "behaviour_category", "effect_on_walking")} for i in pick]) \
        .to_csv(LAB / "spot_check_sample.csv", index=False, lineterminator="\n")
    fp = ag["primary_field_yes_no"]
    md = ["# Label agreement (run 1)", "",
          f"Pass 1 (after excluding breaching sessions and {len(dup_log)} cross-session duplicates): {ag['n_pass1']} records; pass 2: "
          f"{ag['n_pass2']}; matched experiments: {ag['n_matched']}.", "",
          f"**Primary field (front-leg rhythm, both readings yes/no): n = {fp['n']}, raw agreement {fp['raw_agreement']}, "
          f"Cohen's kappa {fp['kappa']}.** All values (incl. unclear / not assessed): {ag['primary_field_all_values']}.", "",
          "| field | raw agreement | kappa |", "|---|---|---|"]
    for f, v in ag["fields"].items():
        md.append(f"| {f} | {v['raw_agreement']} | {v['kappa']} |")
    md += ["", "Merge: " + ", ".join(f"{k} {len(v)}" for k, v in log.items()), "",
           f"Independent search (capture-recapture, {cr['estimator']}, unit {cr['unit']}, dedicated family excluded): first "
           f"{cr['n_first']}, search {cr['n_search']}, both {cr['n_both']}, estimated total {cr['estimated_total']}, found only by the "
           f"search {cr['n_found_only_by_search']}.", "",
           f"Breaching sessions excluded: {sorted(breach) if breach else 'none'}.", "",
           f"Final records: {len(final)}; types with a front-leg yes/no label: {int(tl['front'].isin(['yes', 'no']).sum())}."]
    (LAB / "agreement.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(md))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["collect", "finalize"])
    a = ap.parse_args()
    collect() if a.what == "collect" else finalize()


if __name__ == "__main__":
    main()
