"""Actual Modal billing for Phase 3 (goal4 sections 58-59). ORCHESTRATOR SIDE; reporting only.

The job records (COMPUTE_SUMMARY, COSTS_LEDGER) price container-seconds at list price for a 2-core / 6 GiB reservation, which is an
upper-bound ESTIMATE. Modal bills measured usage, so this script pulls the workspace billing report (hourly, per app) for the Phase 3
window and writes the billed amounts:

    uv run --project phase3 --no-sync python scripts/p3/modal_billing.py [--start 2026-09-25T03:00] [--end 2026-09-26T11:00]
        -> research/phase3/MODAL_BILLING.json and MODAL_BILLING.md

Phase 3 started 2026-09-24 20:00 PDT = 2026-09-25 03:00 UTC (research/LOG.md section 11.3); earlier hours in the workspace belong to
Phase 2. The method was locked at 2026-09-26 01:32 UTC, so the 01:00 UTC hour holds the end of Level B round 3 and the start of the
FINAL confirmation. Partial hours are excluded by the billing API. Costs only; no credentials are read or written by this script.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[2]
P3 = ROOT / "research" / "phase3"
LOCK_HOUR = dt.datetime(2026, 9, 26, 1, tzinfo=dt.timezone.utc)


def _utc(s: str) -> dt.datetime:
    t = dt.datetime.fromisoformat(s)
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def known_app_ids() -> dict[str, str]:
    """app id -> task, from the job records and the hand-kept ledger."""
    out = {}
    for f in P3.glob("*/*/modal_costs.json"):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if r.get("app_id"):
            out[r["app_id"]] = f"{f.parent.parent.name}:{f.parent.name}"
    led = P3 / "COSTS_LEDGER.md"
    if led.exists():
        for ln in led.read_text(encoding="utf-8").splitlines():
            c = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(c) >= 3 and c[2].startswith("ap-"):
                out.setdefault(c[2][:40], c[1][:100])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-09-25T03:00")
    ap.add_argument("--end", default=None, help="exclusive; default: now (partial hours are excluded by the API)")
    a = ap.parse_args(argv)
    start = _utc(a.start)
    end = _utc(a.end) if a.end else None
    ws = modal.Workspace.from_context() if hasattr(modal.Workspace, "from_context") else modal.Workspace()
    rows = ws.billing.report(start=start, end=end, resolution="h")
    per_hour = defaultdict(lambda: defaultdict(Decimal))
    per_app = defaultdict(lambda: {"cost": Decimal(0), "hours": set(), "description": None, "by_resource": defaultdict(Decimal)})
    stage = defaultdict(Decimal)
    for r in rows:
        t = r["interval_start"]
        c = Decimal(str(r["cost"]))
        per_hour[t.strftime("%Y-%m-%dT%H:00Z")][r["description"]] += c
        a_ = per_app[r["object_id"]]
        a_["cost"] += c
        a_["hours"].add(t.strftime("%m-%d %H"))
        a_["description"] = r["description"]
        for k, v in (getattr(r, "cost_by_resource", None) or {}).items():
            a_["by_resource"][k] += Decimal(str(v))
        stage["pre-lock (development, calibration, Level B)" if t < LOCK_HOUR else
              ("lock hour 01:00 UTC (end of round 3 + start of the FINAL confirmation)" if t == LOCK_HOUR else
               "post-lock (FINAL, hidden data, Level C, sweeps, ablations, reviews G)")] += c
    known = known_app_ids()
    total = sum(x["cost"] for x in per_app.values())
    by_desc = defaultdict(Decimal)
    for x in per_app.values():
        by_desc[x["description"]] += x["cost"]
    by_res = defaultdict(Decimal)
    for x in per_app.values():
        for k, v in x["by_resource"].items():
            by_res[k] += v
    rec = {"source": "Modal workspace billing report (workspace.billing.report, resolution 'h')", "start_utc": start.isoformat(),
           "end_utc": end.isoformat() if end else None, "last_hour": max(per_hour) if per_hour else None,
           "total_usd": round(float(total), 2), "by_stage_usd": {k: round(float(v), 2) for k, v in stage.items()},
           "by_app_name_usd": {k: round(float(v), 2) for k, v in sorted(by_desc.items(), key=lambda x: -x[1])},
           "by_resource_usd": {k: round(float(v), 2) for k, v in by_res.items()},
           "per_hour_usd": {h: {k: round(float(v), 3) for k, v in d.items()} for h, d in sorted(per_hour.items())},
           "apps": sorted(({"app_id": k, "name": v["description"], "usd": round(float(v["cost"]), 3), "hours_utc": sorted(v["hours"]),
                            "task_from_records": known.get(k)} for k, v in per_app.items()), key=lambda x: -x["usd"]),
           "note": "Billed amounts (measured usage). The job records' list-price estimates assume a 2-core / 6 GiB reservation per "
                   "container and overstate the bill; they remain the per-task attribution."}
    (P3 / "MODAL_BILLING.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    md = ["# Phase 3 Modal billing (billed, not estimated)", "",
          f"Source: Modal workspace billing report, hourly, {rec['start_utc']} to the last complete hour {rec['last_hour']} "
          "(`scripts/p3/modal_billing.py`).", "", f"**Total billed: ${rec['total_usd']:.2f}** over {len(per_app)} apps.", "",
          "| stage | USD |", "|---|---|"] + [f"| {k} | {v:.2f} |" for k, v in rec["by_stage_usd"].items()] + [
          "", "| app name | USD |", "|---|---|"] + [f"| {k} | {v:.2f} |" for k, v in rec["by_app_name_usd"].items()] + [
          "", "| hour (UTC) | USD by app name |", "|---|---|"] + [
          f"| {h} | {', '.join(f'{k} {v:.2f}' for k, v in d.items())} |" for h, d in rec["per_hour_usd"].items()] + ["", rec["note"], ""]
    (P3 / "MODAL_BILLING.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
    print(json.dumps({k: rec[k] for k in ("total_usd", "by_stage_usd", "by_app_name_usd", "by_resource_usd", "last_hour")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
