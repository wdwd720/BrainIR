"""Developer-facing tournament feedback (PROTOCOL.md section 10): AGGREGATES ONLY, never per-system values or system ids.

    from brainir_causal.feedback import aggregate, write_markdown
    agg = aggregate(round_report)          # round_report: the tournament driver's report (answer-bearing, orchestrator side)
    write_markdown([agg, ...], path)       # the file copied into the clean room as docs/TOURNAMENT_FEEDBACK.md

For every candidate: eligibility and the gate fractions (A, D, E), the pass rates of every criterion A-H over the synthetic validation
systems and over the real validation systems separately, medians of the primary metrics (EE at the primary horizon, SMS, ICG_y, MEV,
passive NMSE, lift success), the verdict-category counts, the rank and the number of failed fits / evaluations. Counts smaller than
MIN_CELL systems are suppressed (a median over one or two systems would reveal per-system values).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

MIN_CELL = 3
CRITERIA = ("A", "B", "C", "D", "E", "F", "G", "H")
METRICS = (("EE", ("items", "effects", "EE_medium", "point")), ("SMS", ("mediation", "SMS", "point")),
           ("ICG_y", ("closure", "ICG_y", "point")), ("MEV", ("micro", "MEV", "point")),
           ("passive_NMSE", ("items", "observational", "obs_nmse_medium", "point")), ("lift_success", ("lift", "success_rate")))


def _get(d, path):
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def _med(vals: list) -> float | None:
    v = [float(x) for x in vals if x is not None and isinstance(x, (int, float)) and math.isfinite(float(x))]
    return float(np.median(v)) if len(v) >= MIN_CELL else None


def aggregate(report: dict) -> dict:
    """Aggregate a round report {"round", "results": {method: {"per_system": {sid: {"kind", "verdict", "selection", "result"}}},
    "eligibility", "order", ...} into the developer-facing summary."""
    out = {"round": report.get("round"), "suite": report.get("suite"), "candidates": {}, "order": report.get("order"),
           "n_systems": {"synthetic": 0, "real": 0}}
    for m, r in (report.get("results") or {}).items():
        ps = r.get("per_system") or {}
        row = {"eligible": (report.get("eligibility") or {}).get(m, {}).get("eligible"),
               "gate_fractions": (report.get("eligibility") or {}).get(m, {}).get("fractions"),
               "n_fit_failures": r.get("n_fit_failures"), "n_eval_failures": r.get("n_eval_failures")}
        for kind in ("synthetic", "real"):
            sub = {s: v for s, v in ps.items() if v.get("kind") == kind}
            out["n_systems"][kind] = max(out["n_systems"][kind], len(sub))
            if len(sub) < MIN_CELL:
                row[kind] = {"n_systems": len(sub), "suppressed": True}
                continue
            rates = {}
            for c in CRITERIA:
                vals = [((v.get("selection") or {}).get(c)) for v in sub.values()]
                rates[c] = round(sum(1 for x in vals if x is True) / len(vals), 3)
            cats: dict[str, int] = {}
            for v in sub.values():
                cat = (v.get("selection") or {}).get("category") or "failed"
                cats[cat] = cats.get(cat, 0) + 1
            meds = {name: _med([_get(v.get("result") or {}, path) for v in sub.values()]) for name, path in METRICS}
            row[kind] = {"n_systems": len(sub), "pass_rates": rates, "categories": cats, "medians": meds}
        out["candidates"][m] = row
    return out


def write_markdown(aggs: list[dict], path: Path | str) -> None:
    lines = ["# Tournament feedback (aggregate Level B results; PROTOCOL.md section 10)", "",
             ("Every value aggregates held-out validation systems you have never seen. Per-system results are not released; cells over "
             f"fewer than {MIN_CELL} systems are suppressed."), "",
             "- **eligible**: passes criterion A on >= 50 % of the systems, D on >= 40 % and E on >= 40 %.",
             "- **A-H**: pass rates of the verdict criteria of PROTOCOL.md section 9.",
             ("- **EE**: median effect error at the primary horizon (1 = predicting no effect); **SMS** state mediation score; **ICG_y** "
             "interventional closure gain; **MEV** microstate-equivalence ratio; **passive_NMSE** passive prediction error; "
             "**lift_success** native lift success rate (all lower is better except lift_success)."), ""]
    for agg in aggs:
        lines += [f"## Round {agg.get('round')}", ""]
        order = agg.get("order") or []
        for kind in ("synthetic", "real"):
            lines += [f"### {kind} validation systems", "",
                      "| candidate | rank | eligible | " + " | ".join(CRITERIA) + " | EE | SMS | ICG_y | MEV | passive_NMSE | lift_success |",
                      "|---|---|---|" + "---|" * len(CRITERIA) + "---|---|---|---|---|---|"]
            for m, row in sorted(agg["candidates"].items(), key=lambda kv: (order.index(kv[0]) if kv[0] in order else 999, kv[0])):
                cell = row.get(kind) or {}
                if cell.get("suppressed") or not cell:
                    lines.append(f"| {m} | {order.index(m) + 1 if m in order else '-'} | {row.get('eligible')} | " + " | ".join("-" for _ in CRITERIA)
                                 + " | - | - | - | - | - | - |")
                    continue
                pr, md = cell["pass_rates"], cell["medians"]

                def f(x):
                    return "-" if x is None else (f"{x:.3g}" if isinstance(x, float) else str(x))
                lines.append(f"| {m} | {order.index(m) + 1 if m in order else '-'} | {row.get('eligible')} | "
                             + " | ".join(f(pr[c]) for c in CRITERIA) + " | "
                             + " | ".join(f(md[n]) for n, _ in METRICS) + " |")
            lines.append("")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def dump_json(agg: dict, path: Path | str) -> None:
    Path(path).write_text(json.dumps(agg, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
