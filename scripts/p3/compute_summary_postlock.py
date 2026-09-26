"""Post-lock correction and completion of the Phase 3 compute summary (post-lock review R, B2 and M9). ORCHESTRATOR SIDE.

`scripts/p3/compute_summary.py` is hashed in the benchmark lock, so it is not edited. This wrapper runs it unchanged except for its
module-level LEDGER_COVERED table, which gains the three ledger rows that duplicate per-part job records (Level B rounds 1 and 2 and
round 3 attempt 1; review R found them counted twice). It then adds what goal4 section 59 asks for and the first summary lacked:
the BILLED Modal amount (research/phase3/MODAL_BILLING.json, from scripts/p3/modal_billing.py), simulated trajectories and simulated
seconds per dataset, counterexample protocols, fit CPU time, simulator calls by the locked method, host-gate refusals and the local
machine's post-lock jobs.

    uv run --project phase3 --no-sync python scripts/p3/compute_summary_postlock.py
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P3 = ROOT / "research" / "phase3"
DATA = ROOT / "data" / "phase3"
RUN = Path(r"C:\Dev\BrainIR_p3run")
DUPLICATE_LEDGER_ROWS = {"Level B round 1 (pilot": "tournament:r1_cb", "Level B round 2 (10 survivors": "tournament:r2_ks_sindy",
                         "Level B round 3 attempt 1": "tournament:r3_brainir_state_v1"}


def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def datasets() -> dict:
    out = {}
    for name, d in (("real_public", DATA / "real_public"), ("real_hidden", DATA / "real_hidden"), ("synthetic_dev", DATA / "synthetic_dev"),
                    ("synthetic_heldout", DATA / "synthetic" / "heldout" / "public"), ("synthetic_final", DATA / "synthetic" / "final" / "public"),
                    ("synthetic_review_g", DATA / "synthetic" / "review_g" / "public")):
        idx = d / "index.jsonl"
        if not idx.exists():
            continue
        n = 0
        secs = 0.0
        for ln in idx.read_text(encoding="utf-8").splitlines():
            row = json.loads(ln)
            n += 1
            p = row.get("protocol") or {}
            if p.get("t_end") is not None:
                secs += float(p["t_end"])
            elif (row.get("info") or {}).get("n_samples") and p.get("dt"):
                secs += (int(row["info"]["n_samples"]) - 1) * float(p["dt"])
        mi = _json(d / "micro_index.json")
        out[name] = {"trajectories": n, "simulated_seconds": round(secs, 1), "restart_index_entries": len(mi) if isinstance(mi, list) else None}
    return out


def counterexample_protocols() -> dict:
    out = {}
    for f in sorted((P3 / "counterexamples").glob("*/SUMMARY.json")):
        s = _json(f) or {}
        out[f.parent.name] = {"protocols_scored": sum(int(v.get("n_scored") or 0) for v in (s.get("systems") or {}).values()),
                              "searches": s.get("n_jobs"), "wall_s": s.get("wall_s"), "backend": s.get("backend")}
    return out


def level_c_fit_cost() -> dict:
    out = {}
    base = RUN / "level_c_01"
    for m in ("brainir_state_v1", "lin_dmdc_t"):
        cpu = wall = 0.0
        n = sims = 0
        for f in (base / m).rglob("*.json") if (base / m).exists() else []:
            if f.name.endswith(".error.json"):
                continue
            r = _json(f) or {}
            tc = (r.get("info") or {}).get("train_cost") or {}
            if r.get("fit_wall_s") is not None or tc:
                n += 1
                cpu += float(tc.get("cpu_s") or r.get("fit_cpu_s") or 0.0)
                wall += float(tc.get("wall_s") or r.get("fit_wall_s") or 0.0)
                sims += int(tc.get("sim_calls") or 0)
        out[m] = {"fit_records": n, "fit_cpu_h": round(cpu / 3600, 2), "fit_wall_h": round(wall / 3600, 2), "simulator_calls_during_fits": sims}
    mc = _json(P3 / "level_c" / "01" / "modal_costs.json") or {}
    ref = mc.get("refusals")
    out["host_gate_refusals"] = len(ref) if isinstance(ref, list) else ref
    return out


def main() -> int:
    spec = importlib.util.spec_from_file_location("compute_summary", ROOT / "scripts" / "p3" / "compute_summary.py")
    cs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cs)
    before = _json(P3 / "COMPUTE_SUMMARY.json") or {}
    cs.LEDGER_COVERED.update(DUPLICATE_LEDGER_ROWS)
    cs.main(["--out-dir", str(P3)])
    rec = _json(P3 / "COMPUTE_SUMMARY.json")
    bill = _json(P3 / "MODAL_BILLING.json") or {}
    fin = {m: {"fit_wall_s_total": (_json(P3 / "tournament" / "final_b" / f"{m}.json") or {}).get("fit_wall_s_total"),
               "fit_wall_s_median": (_json(P3 / "tournament" / "final_b" / f"{m}.json") or {}).get("fit_wall_s_median")}
           for m in ("brainir_state_v1", "lin_dmdc_t")}
    rec["postlock_correction"] = {
        "by": "scripts/p3/compute_summary_postlock.py (post-lock review R, B2)",
        "duplicate_ledger_rows_removed": list(DUPLICATE_LEDGER_ROWS),
        "totals_before": before.get("totals_modal"), "totals_after": rec["totals_modal"],
    }
    rec["billed_modal"] = {k: bill.get(k) for k in ("source", "start_utc", "last_hour", "total_usd", "by_stage_usd", "by_app_name_usd",
                                                    "by_resource_usd", "note")}
    rec["billed_modal"]["n_apps"] = len(bill.get("apps") or [])
    rec["datasets_simulated"] = datasets()
    rec["counterexample_protocols"] = counterexample_protocols()
    rec["level_c_fits"] = level_c_fit_cost()
    rec["final_confirmation_fit_time"] = fin
    rec["not_recorded"] = ["training samples and optimisation steps per fit (the locked method's fits are closed-form least squares; the "
                           "joint shared fits use a fixed optimiser schedule; no per-fit step counter is stored)",
                           "local CPU-hours (the local machine was not metered; wall-clock and worker counts are listed under 'local')"]
    (P3 / "COMPUTE_SUMMARY.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    md = (P3 / "COMPUTE_SUMMARY.md").read_text(encoding="utf-8")
    add = ["", "## Post-lock correction and billed amount", "",
           f"- Duplicate ledger rows removed ({', '.join(DUPLICATE_LEDGER_ROWS)}): estimate {json.dumps(before.get('totals_modal'))} -> "
           f"{json.dumps(rec['totals_modal'])}.",
           f"- **Billed by Modal: ${bill.get('total_usd')}** ({rec['billed_modal']['n_apps']} apps, {bill.get('start_utc')} to the hour "
           f"{bill.get('last_hour')}; `research/phase3/MODAL_BILLING.md`). The list-price estimate above assumes a 2-core / 6 GiB "
           "reservation per container; Modal bills measured usage, including the containers that refused non-gated hosts.",
           f"- By stage (billed): {json.dumps(bill.get('by_stage_usd'))}.", "",
           "## Simulated data", "", "| dataset | trajectories | simulated seconds | restart index entries |", "|---|---|---|---|"]
    add += [f"| {k} | {v['trajectories']} | {v['simulated_seconds']} | {v['restart_index_entries']} |" for k, v in rec["datasets_simulated"].items()]
    add += ["", "## Counterexample protocols", "", "| sweep | protocols scored | searches | wall-s | backend |", "|---|---|---|---|---|"]
    add += [f"| {k} | {v['protocols_scored']} | {v['searches']} | {v['wall_s']} | {v['backend']} |" for k, v in rec["counterexample_protocols"].items()]
    lc = rec["level_c_fits"]
    add += ["", "## Fits", "",
            f"- Level C: brainir_state_v1 {json.dumps(lc['brainir_state_v1'])}; lin_dmdc_t {json.dumps(lc['lin_dmdc_t'])}; host-gate "
            f"refusals {lc['host_gate_refusals']}.",
            f"- FINAL confirmation fit wall time: {json.dumps(fin)}.", "", "## Not recorded", ""] + [f"- {x}" for x in rec["not_recorded"]] + [""]
    (P3 / "COMPUTE_SUMMARY.md").write_text(md.rstrip("\n") + "\n" + "\n".join(add), encoding="utf-8", newline="\n")
    print(json.dumps({"totals_after": rec["totals_modal"], "totals_before": before.get("totals_modal"), "billed": bill.get("total_usd"),
                      "datasets": rec["datasets_simulated"], "level_c_fits": lc}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
