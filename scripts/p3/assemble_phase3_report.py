"""Assemble PHASE3_REPORT.md (ANSWER-BEARING). ORCHESTRATOR SIDE; reporting only.

Sources: research/phase3/REPORT_SUMMARY.md, REPORT_INDEX.md, REPORT_WORKING.md (sections "## N."), SELF_AUDIT.json (+
REPORT_AUDIT_NOTES.md), COMPUTE_SUMMARY.json and MODAL_BILLING.json. The working draft keeps its historical section numbers; the final
order moves working sections 21 (lifting) and 22 (uncertainty) to 19 and 20, inserts the self-audit (21) and compute (22), and puts
the conclusion (working 19) and the next-phase recommendation (working 20) last as 23 and 24. Cross-references in the working text
already use the final numbers, so no text is rewritten.

    uv run --project phase3 --no-sync python scripts/p3/assemble_phase3_report.py
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P3 = ROOT / "research" / "phase3"
ORDER = [(i, i) for i in range(1, 19)] + [(21, 19), (22, 20), ("audit", 21), ("compute", 22), (19, 23), (20, 24)]


def renum(text: str, old: int, new: int) -> str:
    text = re.sub(rf"(?m)^## {old}\. ", f"## {new}. ", text, count=1)
    return re.sub(rf"(?m)^### {old}\.(\d+) ", lambda m: f"### {new}.{m.group(1)} ", text)


def audit_section() -> str:
    a = json.loads((P3 / "SELF_AUDIT.json").read_text(encoding="utf-8"))
    rows = ["| id | status (as computed) | reported | question / check | orchestrator note (not check output) |", "|---|---|---|---|---|"]
    for c in a["checks"]:
        note = str(c.get("orchestrator_note") or "").replace("|", "/")
        rows.append(f"| {c['id']} | {c['status']} | {c.get('reported_status', c['status'])} | {c['title']} | {note} |")
    notes = (P3 / "REPORT_AUDIT_NOTES.md").read_text(encoding="utf-8") if (P3 / "REPORT_AUDIT_NOTES.md").exists() else ""
    return ("## 21. Self-audit: the 19 questions of goal4 section 87, TESTED (`research/phase3/SELF_AUDIT.{json,md}`)\n\n"
            "Every question maps to an executable test on the post-lock evidence, with thresholds fixed before that evidence existed. "
            "'fail' weakens the central claim and is reported; 'pass' means the claim survived that test; the integrity checks I1-I15 "
            f"support the acceptance criteria. Counts as computed: {json.dumps(a['counts'])}; as reported after the post-lock reviews: "
            f"{json.dumps(a.get('counts_reported', a['counts']))}.\n\n" + "\n".join(rows) + "\n\n" + notes)


def compute_section() -> str:
    cs = json.loads((P3 / "COMPUTE_SUMMARY.json").read_text(encoding="utf-8"))
    bill = json.loads((P3 / "MODAL_BILLING.json").read_text(encoding="utf-8"))
    est = cs["totals_modal"]
    stage = bill["by_stage_usd"]
    apps = bill["by_app_name_usd"]
    res = bill["by_resource_usd"]
    ds = cs["datasets_simulated"]
    cx = cs["counterexample_protocols"]
    lc = cs["level_c_fits"]
    fin = cs["final_confirmation_fit_time"]
    refusals = lc.get("host_gate_refusals") or {}
    n_ref = sum(refusals.values()) if isinstance(refusals, dict) else refusals
    pre = next((v for k, v in stage.items() if k.startswith("pre-lock")), 0.0)
    lockh = next((v for k, v in stage.items() if k.startswith("lock hour")), 0.0)
    post = next((v for k, v in stage.items() if k.startswith("post-lock")), 0.0)
    sim_rows = "; ".join(f"{k} {v['trajectories']:,} ({v['simulated_seconds']:,.0f} s" + (f", {v['restart_index_entries']:,} restart entries)" if v.get("restart_index_entries") else ")")
                         for k, v in ds.items())
    cx_total = sum(v["protocols_scored"] for v in cx.values())
    return (
        "## 22. Compute (goal4 sections 58-59)\n\n"
        f"- **Modal, billed:** ${bill['total_usd']:.2f} over {bill.get('n_apps', len(bill.get('apps') or []))} apps, from Modal's billing report for the "
        f"Phase 3 window ({bill['start_utc'][:16]} UTC, the Phase 3 start, to the hour {bill['last_hour']}; `research/phase3/MODAL_BILLING.{{json,md}}`, "
        f"`scripts/p3/modal_billing.py`). By stage: pre-lock development, calibration and Level B ${pre:.0f}; the lock hour (end of round 3 "
        f"and start of the FINAL confirmation) ${lockh:.0f}; post-lock ${post:.0f}. By app: "
        + ", ".join(f"{k} ${v:.1f}" for k, v in apps.items() if v >= 0.05)
        + f". By resource: CPU ${res.get('CPU', 0):.0f}, memory ${res.get('Memory', 0):.0f}, GPU $0. The billed amount includes the {n_ref:,} "
        "containers of Level C that started on an AVX-512 host and stopped at once (host gate); the job records do not price them.\n"
        f"- **Job-record estimate:** ${est['usd']:.0f} over {est['containers']:,} container calls and {est['container_h']:.0f} container-hours "
        "(`research/phase3/COMPUTE_SUMMARY.{json,md}`, `COSTS_LEDGER.md`). It prices every container as 2 cores and 6 GiB at list price, "
        "while Modal bills measured usage, so the bill is about half. The first draft's total ($312) counted Level B rounds 1-2 and round-3 "
        "attempt 1 twice (post-lock review R); `scripts/p3/compute_summary_postlock.py` removes the duplicates. The estimate is kept only to "
        "attribute cost to tasks: Level B rounds 1-3 about $65, the FINAL confirmation $55, Level C $42 at its real container sizes, the "
        "ablations (dev $24, FINAL $28), the six Modal counterexample sweeps $11, the remote runner for development $14, the hidden-data "
        "generation and its checks about $13.\n"
        f"- **Simulation:** trajectories and simulated seconds per dataset: {sim_rows}. The counterexample searches scored {cx_total:,} "
        "protocols over 7 sweeps. The clean-room simulation service served 476 trajectories to the developers (36 refused by the public "
        "policy or failed). The locked method's fits made 0 simulator calls.\n"
        f"- **Fits:** Level C, the locked method: {lc['brainir_state_v1']['fit_records']} fit records, {lc['brainir_state_v1']['fit_cpu_h']:.1f} "
        f"CPU-hours ({lc['brainir_state_v1']['fit_wall_h']:.1f} h of fit wall time); the comparator: {lc['lin_dmdc_t']['fit_records']} fits, "
        f"{lc['lin_dmdc_t']['fit_cpu_h']:.2f} CPU-hours. FINAL confirmation: {fin['brainir_state_v1']['fit_wall_s_total']:,.0f} s of fit wall time "
        f"for the locked method (median {fin['brainir_state_v1']['fit_wall_s_median']:.0f} s per fit) against "
        f"{fin['lin_dmdc_t']['fit_wall_s_total']:,.0f} s ({fin['lin_dmdc_t']['fit_wall_s_median']:.0f} s) for the comparator. The locked method "
        "needs about 13 times the comparator's fit time, for significant gains on prediction and exact k only, and it does not outrank the "
        "comparator on the FINAL suite.\n"
        "- **GPU:** none. All methods are frozen CPU code; the only torch code (ks_share's joint training) runs small CPU tensors, and a GPU "
        "would require changing locked code.\n"
        "- **Wall-clock of the post-lock stage (UTC; `COSTS_LEDGER.md` times are Pacific Daylight Time, UTC-7):**\n"
        "  - method lock 2026-09-26 01:32; Level B confirmation done 02:49;\n"
        "  - the orchestrating session was stopped for low local memory until 05:45;\n"
        "  - hidden data verified 07:29; Level C done 09:04 (94 min, 57 min of it the first fit stage, bounded by single joint fits at "
        "the locked 3 threads, under a 100-container workspace limit);\n"
        "  - last sweep and the self-audit done about 10:15; post-lock reviews, the family-H extraction and the report corrections "
        f"until {time.strftime('%H:%M', time.gmtime())}.\n"
        "- **Local machine:** orchestration; the pre-registered local hidden-draw counterexample sweep (3,340 s on 6 workers at "
        "below-normal priority, at most about 5.6 CPU-hours); the test suites; the self-audit probes. Local CPU-hours were not metered.\n"
        "- **Not recorded:** training samples and optimisation steps per fit (the locked method's fits are closed-form least squares; "
        "no per-fit step counter is stored).\n"
        f"- **Job ids:** the billing record lists every Modal app id with its cost ({bill.get('n_apps', len(bill.get('apps') or []))} apps); "
        "the job records carry app ids for 32 of their 85 rows.\n\n")


def main() -> int:
    W = (P3 / "REPORT_WORKING.md").read_text(encoding="utf-8")
    parts = re.split(r"(?m)^(?=## )", W)
    secs = {}
    for p in parts[1:]:
        m = re.match(r"## (\d+)\. ", p)
        if m:
            secs[int(m.group(1))] = p
    header = ("# PHASE 3 REPORT: Causal State-Variable Discovery (synthetic benchmark and connectome-constrained rate-model simulations)\n\n"
              "**ANSWER-BEARING.** This report contains the hidden Phase 3 results (the Level B confirmation on the synthetic FINAL suite and "
              "Level C on the hidden real test). Never copy it, or anything derived from it, into any later clean room (Phase 4 or any other "
              "clean development room).\n\n"
              "BrainIR State v1 (`brainir_state_v1`), locked 2026-09-26 (tag `brainir-state-v1-preblind`); benchmark `state_discovery_v1` "
              "version 3. Specification: goal4.md.\n\n")
    out = [header, (P3 / "REPORT_SUMMARY.md").read_text(encoding="utf-8"), (P3 / "REPORT_INDEX.md").read_text(encoding="utf-8")]
    for old, new in ORDER:
        if old == "audit":
            out.append(audit_section())
        elif old == "compute":
            out.append(compute_section())
        else:
            out.append(renum(secs[old], old, new))
    text = "\n".join(s.rstrip("\n") + "\n" for s in out if s)
    bad = re.findall(r"C:[\\/]Dev[\\/]BrainIR", text)
    assert not bad, f"absolute paths left: {len(bad)}"
    (ROOT / "PHASE3_REPORT.md").write_text(text, encoding="utf-8", newline="\n")
    print("wrote PHASE3_REPORT.md", len(text), "chars;", "sections", sorted(secs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
