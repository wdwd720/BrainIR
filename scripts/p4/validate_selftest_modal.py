"""Validate the container-start numerics self-test on Modal (research/phase4/LEVEL_B_EXECUTION.md section 9). ORCHESTRATOR ONLY; run
it from the Linux driver container:

    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py run scripts/p4/validate_selftest_modal.py [--sleep 30]

The OFFICIAL app classes (p4modal.app.Backend, the synthetic generator baked as in the tournament) run trivial trusted jobs (`time.sleep`
through the "call" kind: the job itself computes nothing), all submitted at once so that each lands on a container of its own: the
full image unpacked (fit_s), the iso image unpacked (iso_fit_s) and a packed class (pack_xl: 8 inputs per container share ONE self-test).
Every container that passes the flag gate runs the self-test before its first input. Recorded: the containers that passed it (and
their host classes), every self-test refusal (0 expected: each would be a FALSE refusal of a host that computes the reference), the flag
gate's refusals, the self-test's wall time per container and its cost (wall x the class's list price per second), and the Backend's
cost records. Writes research/phase4/numerics_selftest/validation_<utc>.json.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

OUT_DIR = ROOT / "research" / "phase4" / "numerics_selftest"
GENERATOR = {"benchmarks/causal_state_v1/generator/src": "/repo/benchmarks/causal_state_v1/generator/src"}
#: class -> inputs
PLAN = {"fit_s": 36, "iso_fit_s": 36, "pack_xl": 24}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sleep", type=float, default=30.0, help="seconds each trivial job holds its container")
    ap.add_argument("--scale", type=float, default=1.0, help="multiply the inputs per class")
    args = ap.parse_args(argv)
    from brainir_causal.p4modal import app as A
    plan = {cls: max(1, round(n * args.scale)) for cls, n in PLAN.items()}
    results: dict = {cls: [] for cls in plan}
    utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()
    with A.Backend(classes=list(plan), extra_dirs=GENERATOR, app_name="brainir-p4-selftest-val") as be:
        def one(cls: str) -> None:
            payloads = [{"kind": "call", "target": "time:sleep", "args": [float(args.sleep)], "threads": 1, "timeout_s": 600}
                        for _ in range(plan[cls])]
            results[cls] = be.run(payloads, cls, label=f"selftest-val:{cls}")
        ths = [threading.Thread(target=one, args=(cls,), name=f"val-{cls}") for cls in plan]   # bounded: one client thread per class
        for th in ths:
            th.start()
        for th in ths:
            th.join()
        summary = be.cost_summary()
    rec: dict = {"utc": utc, "wall_s": round(time.time() - t0, 1), "app_id": summary.get("app_id"), "plan": plan, "sleep_s": args.sleep,
                 "classes": {}}
    for cls, res in results.items():
        oks = [r for r in res if isinstance(r, dict) and isinstance(r.get("__selftest"), dict)]
        fails = [repr(r)[:300] if isinstance(r, BaseException) else r.get("error") for r in res
                 if isinstance(r, BaseException) or (isinstance(r, dict) and r.get("error"))]
        first = [r["__selftest"] for r in oks if r["__selftest"].get("cached") is False]     # one per container that passed
        tasks = {r.get("__task") for r in oks}
        walls = [float(s["wall_s"]) for s in first if s.get("wall_s") is not None]
        price = A.usd_per_s(cls)
        rec["classes"][cls] = {
            "inputs": len(res), "inputs_ok": len(oks), "job_failures": fails[:5], "containers_with_jobs": len(tasks),
            "containers_passed_selftest": len(first), "host_classes_passed": dict(Counter(s.get("host_class") for s in first)),
            "reference_class_passed": dict(Counter(bool(s.get("reference_class")) for s in first)),
            "selftest_wall_s": {"median": round(statistics.median(walls), 3) if walls else None, "max": max(walls) if walls else None,
                                "min": min(walls) if walls else None},
            "usd_per_container_s": price,
            "selftest_usd_per_container": {"median": round(statistics.median(walls) * price, 6) if walls else None,
                                           "max": round(max(walls) * price, 6) if walls else None},
            "flag_gate_and_selftest_refusals": summary["refusals"].get(cls, 0),
            "selftest_refusals": [s for s in summary.get("selftest_refusals") or [] if s.get("cls") == cls],
            "selftest_counts": (summary.get("selftest_counts") or {}).get(cls),
            "infra_faults": (summary.get("infra_faults") or {}).get(cls, 0)}
    rec["totals"] = {"containers_passed_selftest": sum(c["containers_passed_selftest"] for c in rec["classes"].values()),
                     "selftest_refusals": sum(len(c["selftest_refusals"]) for c in rec["classes"].values()),
                     "flag_gate_refusals": sum(c["flag_gate_and_selftest_refusals"] for c in rec["classes"].values())
                     - sum(len(c["selftest_refusals"]) for c in rec["classes"].values()),
                     "usd_approx_total": summary.get("usd_approx_total")}
    rec["cost_records"] = summary.get("calls")
    rec["hosts"] = summary.get("hosts")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"validation_{utc.replace(':', '').replace('-', '')}.json"
    out.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: rec[k] for k in ("app_id", "wall_s", "totals")}, indent=1), flush=True)
    for cls, c in rec["classes"].items():
        print(cls, json.dumps({k: c[k] for k in ("inputs_ok", "containers_passed_selftest", "host_classes_passed", "selftest_wall_s",
                                                 "selftest_usd_per_container", "flag_gate_and_selftest_refusals", "infra_faults")}),
              flush=True)
    print(f"wrote {out.relative_to(ROOT).as_posix()}", flush=True)
    ok = rec["totals"]["selftest_refusals"] == 0 and rec["totals"]["containers_passed_selftest"] >= 30
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
