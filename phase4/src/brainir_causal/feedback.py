"""Developer-facing tournament feedback (PROTOCOL.md section 10; the covert-channel hardening of review F, F-M5): AGGREGATES ONLY,
never per-system values or system ids.

    from brainir_causal.feedback import aggregate, write_markdown
    agg = aggregate(round_report)          # round_report: the tournament driver's report (answer-bearing, orchestrator side)
    write_markdown([agg, ...], path)       # the file copied into the clean room as docs/TOURNAMENT_FEEDBACK.md

For every candidate: eligibility and the gate fractions (A, D, E), the pass RATES of every criterion A-H over the synthetic and the
real validation systems separately, COARSENED medians of the primary metrics (EE, SMS, ICG_y, MEV, passive NMSE, lift success), the
verdict-category counts, the rank and, as BOOLEANS (F-M5), whether any fit / evaluation failed. Cells over fewer than MIN_CELL systems
are suppressed. To limit the covert-channel capacity (F-M5), medians are rounded to 2 significant digits, pass rates to steps of 0.05,
at most MAX_CANDIDATES candidates are released per round, and `release` (the only release path) enforces, ACROSS calls through a
persistent log (RELEASE_LOG, orchestrator side; review F round 2, M5), at most MAX_ROUNDS released rounds, one fixed system set for
all of them (every round carries its fingerprint) and the validation tier only, with no override. The residual channel (the coarsened
aggregates a developer sees each round) is documented in research/phase4/EVAL_ARCHITECTURE.md.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

MIN_CELL = 3
MAX_ROUNDS = 4                 # F-M5: at most 4 public tournament rounds of feedback
MAX_CANDIDATES = 12            # F-M5: at most this many candidates released per round (>= 4 submitted per developer x a few developers)
RATE_STEP = 0.05              # pass rates are reported in steps of 0.05
MED_SIGFIG = 2               # medians are reported to 2 significant digits
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


def _pass_frac(x) -> float:
    """A criterion pass value as a fraction: True -> 1, False / None -> 0, a seed-averaged float -> itself (the coordinator's note:
    seed-averaged pass values are floats)."""
    if x is True:
        return 1.0
    if x is None or x is False:
        return 0.0
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    return v if math.isfinite(v) else 0.0


def _coarsen_rate(x: float) -> float:
    return round(round(x / RATE_STEP) * RATE_STEP, 3)


def _sig(x: float, n: int = MED_SIGFIG) -> float:
    if x == 0 or not math.isfinite(x):
        return float(x)
    from math import floor, log10
    return round(x, -int(floor(log10(abs(x)))) + (n - 1))


def _med(vals: list) -> float | None:
    v = [float(x) for x in vals if x is not None and isinstance(x, (int, float)) and math.isfinite(float(x))]
    return _sig(float(np.median(v))) if len(v) >= MIN_CELL else None


def aggregate(report: dict) -> dict:
    """Aggregate a round report {"round", "results": {method: {"per_system": {sid: {"kind", "verdict", "selection", "result"}}},
    "eligibility", "order", ...} into the developer-facing summary. Pass rates are coarsened to steps of 0.05 and medians to 2
    significant digits; failures are booleans (F-M5). At most MAX_CANDIDATES candidates are released (by rank order when present)."""
    out = {"round": report.get("round"), "suite": report.get("suite"), "candidates": {}, "order": report.get("order"),
           "n_systems": {"synthetic": 0, "real": 0}, "system_ids_hash": None}
    results = report.get("results") or {}
    order = report.get("order") or sorted(results)
    ordered = [m for m in order if m in results] + [m for m in sorted(results) if m not in order]
    all_sids = sorted({s for r in results.values() for s in (r.get("per_system") or {})})
    import hashlib
    out["system_ids_hash"] = hashlib.sha256("|".join(all_sids).encode()).hexdigest()[:16]   # a stable fingerprint of the system set
    for m in ordered[:MAX_CANDIDATES]:
        r = results[m]
        ps = r.get("per_system") or {}
        row = {"eligible": (report.get("eligibility") or {}).get(m, {}).get("eligible"),
               "any_fit_failure": bool(r.get("n_fit_failures")), "any_eval_failure": bool(r.get("n_eval_failures"))}
        for kind in ("synthetic", "real"):
            sub = {s: v for s, v in ps.items() if v.get("kind") == kind}
            out["n_systems"][kind] = max(out["n_systems"][kind], len(sub))
            if len(sub) < MIN_CELL:
                row[kind] = {"n_systems": len(sub), "suppressed": True}
                continue
            rates = {c: _coarsen_rate(sum(_pass_frac((v.get("selection") or {}).get(c)) for v in sub.values()) / len(sub)) for c in CRITERIA}
            cats: dict[str, int] = {}
            for v in sub.values():
                cat = (v.get("selection") or {}).get("category") or "failed"
                cats[cat] = cats.get(cat, 0) + 1
            meds = {name: _med([_get(v.get("result") or {}, path) for v in sub.values()]) for name, path in METRICS}
            row[kind] = {"n_systems": len(sub), "pass_rates": rates, "categories": cats, "medians": meds}
        out["candidates"][m] = row
    if len(ordered) > MAX_CANDIDATES:
        out["candidates_suppressed"] = len(ordered) - MAX_CANDIDATES
    return out


def check_release(aggs: list[dict], *, tiers: set[str] | None = None, allow_changed_systems: bool = False) -> None:
    """The in-call release rules of F-M5: feedback is for the validation tier only, at most MAX_ROUNDS rounds, every round carries
    its system-set fingerprint and the system set is fixed across a tier's rounds (the same `system_ids_hash`). Raises on a
    violation. The rules ACROSS calls (rounds released earlier) are enforced by `release`, the only way to release feedback."""
    if tiers is not None and not tiers <= {"val"}:
        raise ValueError(f"feedback is released for the validation tier only (F-M5); got tiers {sorted(tiers)}")
    if len(aggs) > MAX_ROUNDS:
        raise ValueError(f"feedback is capped at {MAX_ROUNDS} rounds (F-M5); got {len(aggs)}")
    if not allow_changed_systems and any(not a.get("system_ids_hash") for a in aggs):
        raise ValueError("every released round needs its system-set fingerprint (F-M5, round 2)")
    hashes = {a.get("system_ids_hash") for a in aggs if a.get("system_ids_hash")}
    if len(hashes) > 1 and not allow_changed_systems:
        raise ValueError("the released rounds use different system sets (F-M5: differencing across rounds); fix the tier's system set "
                         "or pass allow_changed_systems")


#: the persistent record of released feedback (ORCHESTRATOR SIDE, answer-bearing directory; never in a room): review F round 2, M5
RELEASE_LOG = Path(__file__).resolve().parents[3] / "research" / "phase4" / "tournament" / "FEEDBACK_RELEASES.json"
RELEASE_FORMAT = "p4-feedback-releases-1"


def load_release_log(log_path: Path | str | None = None) -> dict:
    p = Path(log_path) if log_path else RELEASE_LOG
    if not p.exists():
        return {"format": RELEASE_FORMAT, "rounds": [], "events": []}
    log = json.loads(p.read_text(encoding="utf-8"))
    if log.get("format") != RELEASE_FORMAT:
        raise ValueError(f"{p} is not a feedback release log")
    return log


def _content_sha(agg: dict) -> str:
    """sha256 of one round's released aggregate (canonical JSON)."""
    import hashlib
    return hashlib.sha256(json.dumps(agg, sort_keys=True, default=str).encode()).hexdigest()


def release(aggs: list[dict], out_path: Path | str, *, tiers: set[str], log_path: Path | str | None = None) -> dict:
    """Release developer feedback (the ONLY release path; review F round 2, M5): the in-call rules of `check_release` plus the same
    rules ACROSS calls through a persistent log (default RELEASE_LOG): at most MAX_ROUNDS distinct rounds over ALL releases, one
    system-set fingerprint for all of them (a round's fingerprint never changes), validation tier only; no override. Writes the
    markdown, then records the rounds and the file's sha256. Returns the log entry of this release."""
    import hashlib
    import os
    import time
    log_p = Path(log_path) if log_path else RELEASE_LOG
    if not tiers or not set(tiers) <= {"val"}:
        raise ValueError(f"feedback is released for the validation tier only (F-M5); got tiers {sorted(tiers or [])}")
    check_release(aggs, tiers=set(tiers))
    log = load_release_log(log_p)
    known = {r["round"]: r["system_ids_hash"] for r in log["rounds"]}
    known_content = {r["round"]: r.get("content_sha256") for r in log["rounds"]}
    for a in aggs:
        if a.get("round") is None:
            raise ValueError("every released round needs its round id (F-M5, round 2)")
        if a["round"] in known and known[a["round"]] != a["system_ids_hash"]:
            raise ValueError(f"round {a['round']!r} was released before with another system set (F-M5, round 2)")
        # a round id is released with ONE content only (review F round 3, M5): a re-release must repeat the recorded aggregate exactly,
        # so the cap on rounds cannot be bypassed by re-using a round id with other candidates or values
        if a["round"] in known and known_content.get(a["round"]) not in (None, _content_sha(a)):
            raise ValueError(f"round {a['round']!r} was released before with different content (F-M5, round 3)")
    fps = set(known.values()) | {a["system_ids_hash"] for a in aggs}
    if len(fps) > 1:
        raise ValueError("these rounds use a different system set from the rounds released before (F-M5, round 2: differencing "
                         "across releases)")
    rounds = set(known) | {a["round"] for a in aggs}
    if len(rounds) > MAX_ROUNDS:
        raise ValueError(f"feedback is capped at {MAX_ROUNDS} rounds over all releases (F-M5, round 2); this release would make "
                         f"{len(rounds)}")
    write_markdown(aggs, out_path)
    sha = hashlib.sha256(Path(out_path).read_bytes()).hexdigest()
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for a in aggs:
        if a["round"] not in known:
            log["rounds"].append({"round": a["round"], "system_ids_hash": a["system_ids_hash"], "tier": "val", "first_released_utc": now,
                                  "content_sha256": _content_sha(a)})
    ev = {"released_utc": now, "rounds": [a["round"] for a in aggs], "file_sha256": sha, "file_name": Path(out_path).name}
    log["events"].append(ev)
    log_p.parent.mkdir(parents=True, exist_ok=True)
    tmp = log_p.with_name(f".{log_p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(log, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, log_p)
    return ev


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
