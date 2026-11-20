"""Collect, validate and aggregate blind labels (LABEL SIDE: never reads predictions). The orchestrator runs this; it never
writes, edits or adjudicates a label: everything here is deterministic.

    uv run --project ledger --no-sync python ledger/scripts/labels_collect.py collect      # copy room outputs, assign exp_id, validate
    uv run --project ledger --no-sync python ledger/scripts/labels_collect.py finalize     # dedupe, merge passes, consensus, agreement

collect  -> research/ledger/labels/raw/<pass>/<session>/ (verbatim copies of out/*, records.valid.jsonl with exp_id,
            validation.json listing invalid lines and error kinds without label values)
finalize -> research/ledger/labels/{records.jsonl, type_labels.csv, sources.csv, synonyms.csv, driver_lines.csv, agreement.md,
            agreement.json, merge_log.json, spot_check_sample.csv, search_only_records.jsonl}
Breach rule (PREREG section 6): records of a pass-1 session whose transcript audit shows a breach, and experiments read by a
breaching pass-2 / adjudication session, are excluded from the consensus and reported.
"""

from __future__ import annotations

import argparse
import csv
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
BREACH_KINDS = ("file_outside_room", "banned_host_fetch", "dedicated_source_outside_dedicated_session")


def known_types() -> set[str]:
    return set(pd.read_csv(KIT / "type_list.csv")["manc_type"])


def collect() -> None:
    kt = known_types()
    for man in sorted((ROOMS / "_manifests").glob("*.json")):
        m = json.loads(man.read_text(encoding="utf-8"))
        room, session, pass_id = Path(m["room"]), m["session"], m["pass"]
        dest = RAW / pass_id / session
        dest.mkdir(parents=True, exist_ok=True)
        for f in sorted((room / "out").glob("*")):
            if f.is_file():
                shutil.copyfile(f, dest / f.name)
        rec = dest / "records.jsonl"
        if not rec.exists():
            print(f"{session}: no records")
            continue
        good, bad, seen = [], [], set()
        for i, line in enumerate(rec.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                bad.append({"line": i, "errors": ["invalid JSON"]})
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
            if errs:
                bad.append({"line": i, "errors": errs})
            else:
                good.append(r)
        with open(dest / "records.valid.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for r in good:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
        (dest / "validation.json").write_text(json.dumps({"n_valid": len(good), "n_invalid": len(bad), "invalid": bad}, indent=1) + "\n",
                                              encoding="utf-8", newline="\n")
        print(f"{session}: {len(good)} valid, {len(bad)} invalid")


def _read(pass_id: str) -> list[dict]:
    out = []
    for sd in sorted((RAW / pass_id).glob("*")):
        p = sd / "records.valid.jsonl"
        if p.exists():
            out += [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return out


def _csv_rows(name: str, pass_id: str) -> list[dict]:
    rows = []
    for sd in sorted((RAW / pass_id).glob("*")):
        p = sd / name
        if p.exists() and p.stat().st_size:
            rows += list(csv.DictReader(open(p, encoding="utf-8")))
    return rows


def norm_doi(d: str) -> str:
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    return re.sub(r"\.\d+$", "", d) if d.startswith("10.7554/elife.") else d  # eLife reviewed-preprint versions


def capture_recapture(first: list[dict], second: list[dict]) -> dict:
    """Chapman estimator at the (normalised DOI, MANC type) level (PREREG section 6)."""
    a = {(norm_doi(r["doi"]), r["manc_type"]) for r in first}
    b = {(norm_doi(r["doi"]), r["manc_type"]) for r in second}
    m, n1, n2 = len(a & b), len(a), len(b)
    chapman = (n1 + 1) * (n2 + 1) / (m + 1) - 1 if (n1 or n2) else None
    return {"unit": "(normalised doi, manc_type)", "estimator": "Chapman", "n_first": n1, "n_search": n2, "n_both": m,
            "estimated_total": chapman, "estimated_missed_by_both": (chapman - len(a | b)) if chapman is not None else None,
            "n_found_only_by_search": len(b - a)}


def breaching_sessions() -> dict[str, list]:
    p = LAB / "transcript_audit.json"
    if not p.exists():
        return {}
    out = {}
    for r in json.loads(p.read_text(encoding="utf-8")):
        bad = [i for i in r["issues"] if i["kind"] in BREACH_KINDS]
        if bad:
            out[r["session"]] = bad
    return out


def finalize() -> None:
    breach = breaching_sessions()
    p1_all = _read("pass1")
    p1_all = [r for r in p1_all if r["exp_id"].split(":", 1)[0] not in breach]
    p1, dup_log = AGG.dedupe_pass1(p1_all)
    p2 = _read("pass2")
    adj = _read("adjudication")
    bad_readers = {s for s in breach if s.startswith(("pass2", "adjudication"))}
    tainted = set()
    for s in bad_readers:
        pass_id = s.split("-", 1)[0]
        for r in [json.loads(ln) for ln in (RAW / pass_id / s / "records.valid.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()] \
                if (RAW / pass_id / s / "records.valid.jsonl").exists() else []:
            tainted.add(r["exp_id"])
    p1 = [r for r in p1 if r["exp_id"] not in tainted]
    qc = {row["exp_id"]: str(row.get("quote_found", "")).strip().lower() == "true" for row in _csv_rows("quote_checks.csv", "pass2")}
    nf = {row["exp_id"] for row in _csv_rows("not_found.csv", "pass2")}
    final, log = AGG.merge_passes(p1, p2, adj, qc, nf)
    ex = pd.read_csv(KIT / "exposed_types.csv")
    exposed = {t for s in ex["manc_types"].dropna() for t in str(s).split(";") if t}
    tl = AGG.type_labels(final, exposed=exposed, type_list=sorted(known_types()))
    LAB.mkdir(parents=True, exist_ok=True)
    with open(LAB / "records.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in sorted(final, key=lambda r: (r["manc_type"], r["exp_id"])):
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    tl.to_csv(LAB / "type_labels.csv", index=False, lineterminator="\n")
    search = _read("search")
    with open(LAB / "search_only_records.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        p1keys = {(norm_doi(r["doi"]), r["manc_type"]) for r in p1}
        for r in search:
            if (norm_doi(r["doi"]), r["manc_type"]) not in p1keys:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    ag = agreement(p1, p2)
    cr = capture_recapture(p1, search)
    summary = {"agreement": ag, "capture_recapture": cr, "merge_log_counts": {k: len(v) for k, v in log.items()},
               "pass1_duplicates_dropped": len(dup_log), "breaching_sessions": breach, "tainted_experiments": len(tainted)}
    (LAB / "agreement.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
    (LAB / "merge_log.json").write_text(json.dumps({"merge": log, "pass1_duplicates": dup_log}, indent=1) + "\n", encoding="utf-8", newline="\n")
    srcs: dict[str, dict] = {}
    for sd in sorted(RAW.glob("*/*")):
        p = sd / "sources.csv"
        if p.exists() and p.stat().st_size:
            for row in csv.DictReader(open(p, encoding="utf-8")):
                d = norm_doi(row.get("doi") or "")
                if d:
                    e = srcs.setdefault(d, {**row, "doi": d, "sessions": set()})
                    e["sessions"].add(sd.name)
    rows = [{**{k: v for k, v in r.items() if k != "sessions"}, "sessions": ";".join(sorted(r["sessions"])),
             "n_final_records": sum(1 for x in final if norm_doi(x["doi"]) == d)} for d, r in sorted(srcs.items())]
    pd.DataFrame(rows).to_csv(LAB / "sources.csv", index=False, lineterminator="\n")
    syn = pd.read_csv(KIT / "synonyms.csv").assign(status="kit")
    props = [pd.read_csv(p).assign(status="proposed", session=p.parent.name) for p in RAW.glob("*/*/proposed_synonyms.csv") if p.stat().st_size]
    pd.concat([syn, *props], ignore_index=True).to_csv(LAB / "synonyms.csv", index=False, lineterminator="\n")
    dl = pd.read_csv(KIT / "driver_lines.csv").assign(status="kit")
    dprops = [pd.read_csv(p).assign(status="proposed", session=p.parent.name) for p in RAW.glob("*/*/proposed_driver_lines.csv")
              if p.stat().st_size]
    pd.concat([dl, *dprops], ignore_index=True).to_csv(LAB / "driver_lines.csv", index=False, lineterminator="\n")
    rng = np.random.default_rng(SPOT_SEED)
    pick = sorted(rng.choice(len(final), size=min(20, len(final)), replace=False)) if final else []
    pd.DataFrame([{k: final[i].get(k) for k in ("exp_id", "manc_type", "name_in_paper", "doi", "source_locator", "quote", "driver_lines",
                                                "preparation", "front_leg_rhythm", "middle_leg_rhythm", "hind_leg_rhythm",
                                                "behaviour_category", "effect_on_walking")} for i in pick]) \
        .to_csv(LAB / "spot_check_sample.csv", index=False, lineterminator="\n")
    fp = ag["primary_field_yes_no"]
    md = ["# Label agreement (run 1)", "",
          f"Pass 1 (after cross-session de-duplication, {len(dup_log)} duplicates dropped): {ag['n_pass1']} records; pass 2: "
          f"{ag['n_pass2']}; matched experiments: {ag['n_matched']}.", "",
          f"**Primary field (front-leg rhythm, both readings yes/no): n = {fp['n']}, raw agreement {fp['raw_agreement']}, "
          f"Cohen's kappa {fp['kappa']}.** All values (incl. unclear / not assessed): {ag['primary_field_all_values']}.", "",
          "| field | raw agreement | kappa |", "|---|---|---|"]
    for f, v in ag["fields"].items():
        md.append(f"| {f} | {v['raw_agreement']} | {v['kappa']} |")
    md += ["", "Merge: " + ", ".join(f"{k} {len(v)}" for k, v in log.items()), "",
           f"Independent search (capture-recapture, {cr['estimator']}, unit {cr['unit']}): first {cr['n_first']}, search {cr['n_search']}, "
           f"both {cr['n_both']}, estimated total {cr['estimated_total']}, found only by the search {cr['n_found_only_by_search']}.", "",
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
