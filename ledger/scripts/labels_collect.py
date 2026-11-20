"""Collect, validate and aggregate blind labels (LABEL SIDE: never reads predictions). The orchestrator runs this; it never
writes, edits or adjudicates a label: everything below is deterministic.

    uv run --project ledger --no-sync python ledger/scripts/labels_collect.py collect      # copy room outputs, validate
    uv run --project ledger --no-sync python ledger/scripts/labels_collect.py finalize     # merge passes, consensus, agreement

collect  -> research/ledger/labels/raw/<pass>/<session>/ (verbatim copies of out/*, records.valid.jsonl, validation.json)
finalize -> research/ledger/labels/{records.jsonl, type_labels.csv, sources.csv, synonyms.csv, driver_lines.csv, agreement.md,
            agreement.json, merge_log.json, spot_check_sample.csv}
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ledger" / "src"))
from brainir_ledger.labels import aggregate as AGG  # noqa: E402
from brainir_ledger.labels.agreement import agreement  # noqa: E402
from brainir_ledger.labels.schema import experiment_key, validate_file  # noqa: E402

KIT = REPO / "research" / "ledger" / "kit"
LAB = REPO / "research" / "ledger" / "labels"
RAW = LAB / "raw"
ROOMS = Path.home() / "ledger_rooms" / "run1"
SPOT_SEED = 20261126


def known_types() -> set[str]:
    return set(pd.read_csv(KIT / "type_list.csv")["manc_type"])


def collect() -> None:
    kt = known_types()
    for man in sorted((ROOMS / "_manifests").glob("*.json")):
        m = json.loads(man.read_text(encoding="utf-8"))
        room = Path(m["room"])
        dest = RAW / m["pass"] / m["session"]
        dest.mkdir(parents=True, exist_ok=True)
        for f in sorted((room / "out").glob("*")):
            if f.is_file():
                shutil.copyfile(f, dest / f.name)
        rec = dest / "records.jsonl"
        if rec.exists():
            good, bad = validate_file(rec, kt)
            with open(dest / "records.valid.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                for r in good:
                    fh.write(json.dumps(r, sort_keys=True) + "\n")
            (dest / "validation.json").write_text(json.dumps({"n_valid": len(good), "n_invalid": len(bad),
                                                              "invalid": [{"line": i, "errors": e} for i, e in bad]}, indent=1) + "\n",
                                                  encoding="utf-8", newline="\n")
            print(f"{m['session']}: {len(good)} valid, {len(bad)} invalid")
        else:
            print(f"{m['session']}: no records")


def _read(pass_id: str) -> list[dict]:
    out = []
    for sd in sorted((RAW / pass_id).glob("*")):
        p = sd / "records.valid.jsonl"
        if p.exists():
            out += [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return out


def _quote_checks() -> dict[str, bool]:
    out = {}
    for sd in sorted((RAW / "pass2").glob("*")):
        p = sd / "quote_checks.csv"
        if p.exists():
            for row in csv.DictReader(open(p, encoding="utf-8")):
                v = str(row.get("quote_found", "")).strip().lower()
                out[row["experiment_key"]] = v == "true"
    return out


def _dedupe(recs: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in recs:
        k = r.get("experiment_key") or experiment_key(r)
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def capture_recapture(first: list[dict], second: list[dict]) -> dict:
    a = {(r["doi"].lower(), r["manc_type"]) for r in first}
    b = {(r["doi"].lower(), r["manc_type"]) for r in second}
    m = len(a & b)
    n1, n2 = len(a), len(b)
    chapman = (n1 + 1) * (n2 + 1) / (m + 1) - 1 if (n1 or n2) else None
    return {"unit": "(doi, manc_type)", "n_first": n1, "n_search": n2, "n_both": m, "chapman_estimate_total": chapman,
            "estimated_missed_by_first": (chapman - len(a | b)) if chapman is not None else None,
            "found_only_by_search": sorted(f"{d}|{t}" for d, t in (b - a))}


def finalize() -> None:
    p1 = _dedupe(_read("pass1"))
    p2 = _read("pass2")
    adj = _read("adjudication")
    search = _read("search")
    qc = _quote_checks()
    final, log = AGG.merge_passes(p1, p2, adj, qc)
    ex = pd.read_csv(KIT / "exposed_types.csv")
    exposed = {t for s in ex["manc_types"].dropna() for t in str(s).split(";") if t}
    tl = AGG.type_labels(final, exposed=exposed, type_list=sorted(known_types()))
    LAB.mkdir(parents=True, exist_ok=True)
    with open(LAB / "records.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in sorted(final, key=lambda r: (r["manc_type"], r["experiment_key"])):
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    tl.to_csv(LAB / "type_labels.csv", index=False, lineterminator="\n")
    ag = agreement(p1, p2)
    cr = capture_recapture(p1 + p2, search)
    (LAB / "agreement.json").write_text(json.dumps({"agreement": ag, "capture_recapture": cr,
                                                    "merge_log_counts": {k: len(v) for k, v in log.items()}}, indent=1) + "\n",
                                        encoding="utf-8", newline="\n")
    (LAB / "merge_log.json").write_text(json.dumps(log, indent=1) + "\n", encoding="utf-8", newline="\n")
    # sources registry
    srcs = {}
    for sd in sorted(RAW.glob("*/*")):
        p = sd / "sources.csv"
        if p.exists():
            for row in csv.DictReader(open(p, encoding="utf-8")):
                d = (row.get("doi") or "").strip().lower()
                if d:
                    srcs.setdefault(d, {**row, "sessions": set()})["sessions"].add(sd.name)
    rows = [{**{k: v for k, v in r.items() if k != "sessions"}, "sessions": ";".join(sorted(r["sessions"])),
             "n_final_records": sum(1 for x in final if x["doi"].strip().lower() == d)} for d, r in sorted(srcs.items())]
    pd.DataFrame(rows).to_csv(LAB / "sources.csv", index=False, lineterminator="\n")
    # name maps: kit maps plus labeler proposals (marked as proposed)
    syn = pd.read_csv(KIT / "synonyms.csv").assign(status="kit")
    props = [pd.read_csv(p).assign(status="proposed", session=p.parent.name) for p in RAW.glob("*/*/proposed_synonyms.csv")
             if p.stat().st_size > 0]
    pd.concat([syn, *props], ignore_index=True).to_csv(LAB / "synonyms.csv", index=False, lineterminator="\n")
    dl = pd.read_csv(KIT / "driver_lines.csv").assign(status="kit")
    dprops = [pd.read_csv(p).assign(status="proposed", session=p.parent.name) for p in RAW.glob("*/*/proposed_driver_lines.csv")
              if p.stat().st_size > 0]
    pd.concat([dl, *dprops], ignore_index=True).to_csv(LAB / "driver_lines.csv", index=False, lineterminator="\n")
    # spot-check sample for the user
    rng = np.random.default_rng(SPOT_SEED)
    pick = rng.choice(len(final), size=min(20, len(final)), replace=False) if final else []
    pd.DataFrame([{k: final[i].get(k) for k in ("manc_type", "name_in_paper", "doi", "source_locator", "quote", "driver_lines",
                                                "preparation", "front_leg_rhythm", "middle_leg_rhythm", "hind_leg_rhythm",
                                                "behaviour_category", "effect_on_walking")} for i in sorted(pick)]) \
        .to_csv(LAB / "spot_check_sample.csv", index=False, lineterminator="\n")
    fp = ag["primary_field_yes_no"]
    md = ["# Label agreement (run 1)", "",
          f"Pass 1: {ag['n_pass1']} records; pass 2: {ag['n_pass2']}; matched experiments: {ag['n_matched']}.", "",
          f"**Primary field (front-leg rhythm, both readings yes/no): n = {fp['n']}, raw agreement {fp['raw_agreement']}, "
          f"Cohen's kappa {fp['kappa']}.**", "", "| field | raw agreement | kappa |", "|---|---|---|"]
    for f, v in ag["fields"].items():
        md.append(f"| {f} | {v['raw_agreement']} | {v['kappa']} |")
    md += ["", "Merge: " + ", ".join(f"{k} {len(v)}" for k, v in log.items()), "",
           f"Independent search (capture-recapture at the (DOI, MANC type) level): {json.dumps({k: v for k, v in cr.items() if k != 'found_only_by_search'})}",
           "", f"Final records: {len(final)}; types with a front-leg yes/no label: {int(tl['front'].isin(['yes', 'no']).sum())}."]
    (LAB / "agreement.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(md))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["collect", "finalize"])
    a = ap.parse_args()
    collect() if a.what == "collect" else finalize()


if __name__ == "__main__":
    main()
