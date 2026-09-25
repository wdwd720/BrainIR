"""Phase 3 compute summary (goal4 sections 58-59; the acceleration directive's compute report). ORCHESTRATOR SIDE.

    uv run --project phase3 --no-sync python scripts/p3/compute_summary.py [--out-dir research/phase3]

Aggregates what the jobs recorded themselves, so nothing is estimated twice:
- the Modal records of every round and post-lock run: research/phase3/{tournament,ablations,counterexamples,level_c}/*/modal_costs.json,
  plus the equivalence probes in research/phase3/postlock_infra/*.json;
- the hand-kept rows of research/phase3/COSTS_LEDGER.md for jobs without a record file (calibration, uploads, smoke tests). A ledger
  row whose text names a round that has its own record is not counted twice;
- simulation-cache reuse from the simulation services' result records (`cached` per trajectory) in the clean room and the run
  directories, and the reference-control cache (files per suite);
- fit wall time per method from the round result files (container seconds are already in the Modal records).
Writes COMPUTE_SUMMARY.json and COMPUTE_SUMMARY.md.

GPUs: every method is frozen, CPU-coded code (numpy / scipy / CPU torch with set_num_threads). A GPU could only be used by changing
method code, which the method lock forbids (and which would change the fitted models). So no workload was profiled on GPU, and
none runs there. Modal CPU containers (2 physical cores, 6 GiB) carry the parallel work.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P3 = ROOT / "research" / "phase3"
RUN = Path(r"C:\Dev\BrainIR_p3run")
ROOM = Path(r"C:\Dev\BrainIR_p3clean")
PRICE = {"core_h": 0.192, "gib_h": 0.024}
# ledger rows that describe a run which also has its own record file (text fragment -> the record's task name)
LEDGER_COVERED = {"dev-suite smoke tournaments": "tournament:smoke_modal_dev"}


def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def modal_records() -> list[dict]:
    rows = []
    for kind in ("tournament", "ablations", "counterexamples", "level_c"):
        for f in sorted((P3 / kind).glob("*/modal_costs.json")):
            r = _json(f) or {}
            calls = r.get("calls")
            if isinstance(calls, list):
                n_calls = sum(int(c.get("calls", 0)) for c in calls)
                cs = sum(float(c.get("container_s", 0.0)) for c in calls)
                usd = sum(float(c.get("usd_approx", 0.0)) for c in calls)
            else:
                n_calls, cs, usd = int(calls or 0), float(r.get("container_s", 0.0)), float(r.get("usd_approx", 0.0))
            rows.append({"source": f.relative_to(ROOT).as_posix(), "task": f"{kind}:{f.parent.name}", "backend": "Modal CPU",
                         "suite": r.get("suite"), "containers": n_calls, "container_s": round(cs, 1), "wall_s": r.get("wall_s"),
                         "usd": round(usd, 3), "app_id": r.get("app_id")})
    for f in sorted((P3 / "postlock_infra").glob("*.json")):
        r = _json(f) or {}
        m = r.get("modal") or {}
        if m or r.get("app_id"):
            cs = float(m.get("container_s") or r.get("modal_container_s") or 0.0)
            usd = float(m.get("usd_approx") or cs * (2 * PRICE["core_h"] + 6 * PRICE["gib_h"]) / 3600)
            rows.append({"source": f.relative_to(ROOT).as_posix(), "task": f"equivalence:{f.stem}", "backend": "Modal CPU", "suite": "dev/public",
                         "containers": int(m.get("calls") or 1), "container_s": round(cs, 1), "wall_s": m.get("wall_s") or r.get("modal_wall_s"),
                         "usd": round(usd, 3), "app_id": m.get("app_id") or r.get("app_id")})
    return rows


def ledger_rows(covered_tasks: set[str]) -> tuple[list[dict], list[str]]:
    f = P3 / "COSTS_LEDGER.md"
    if not f.exists():
        return [], []
    rows, local, in_local = [], [], False
    for ln in f.read_text(encoding="utf-8").splitlines():
        if ln.startswith("## "):
            in_local = ln.strip().lower().startswith("## local")
            continue
        if in_local and ln.strip().startswith("-"):
            local.append(ln.strip()[2:])
        if not ln.startswith("|") or set(ln.replace("|", "").strip()) <= set("-: "):
            continue
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) < 6 or c[0].startswith("time"):
            continue
        job = c[1]
        if any(t.split(":", 1)[1] in job for t in covered_tasks if ":" in t):
            continue
        if any(frag in job and task in covered_tasks for frag, task in LEDGER_COVERED.items()):
            continue

        def num(s):
            m = re.search(r"[-+]?[0-9][0-9,]*\.?[0-9]*", s)
            return float(m.group(0).replace(",", "")) if m else 0.0
        rows.append({"source": "COSTS_LEDGER.md", "task": job[:120], "backend": "Modal CPU", "time": c[0], "app_id": c[2][:60],
                     "containers": int(num(c[3])), "container_s": num(c[4]), "usd": num(c[5])})
    return rows, local


def sim_cache() -> dict:
    """Simulation-service records: trajectories served from the content-addressed store (cached) vs computed."""
    out = {}
    roots = {"clean_room": ROOM / "simq" / "results"}
    for d in sorted(RUN.glob("*/sim/simq/results")) if RUN.exists() else []:
        roots[f"run:{d.parents[2].name}"] = d
    for name, d in roots.items():
        if not d.exists():
            continue
        n = cached = failed = 0
        for f in d.glob("*.json"):
            r = _json(f) or {}
            for it in r.get("items") or []:
                if not it.get("ok"):
                    failed += 1
                    continue
                n += 1
                cached += bool(it.get("cached"))
        if n or failed:
            out[name] = {"trajectories": n, "served_from_cache": cached, "cache_hit_rate": round(cached / n, 3) if n else None,
                         "refused_or_failed": failed}
    return out


def ref_cache() -> dict:
    d = P3 / "tournament" / "_refcache"
    return {p.name: len(list(p.glob("*.json"))) for p in sorted(d.iterdir()) if p.is_dir()} if d.exists() else {}


def fit_times() -> list[dict]:
    rows = []
    for f in sorted((P3 / "tournament").glob("*/*.json")):
        if f.name.startswith(("AGGREGATE", "ROUND_DECISION", "modal_costs")):
            continue
        r = _json(f) or {}
        if "fit_wall_s_total" in r:
            rows.append({"round": f.parent.name, "method": f.stem, "n_fits": r.get("n_fits"), "fit_wall_s_total": r.get("fit_wall_s_total"),
                         "fit_wall_s_median": r.get("fit_wall_s_median")})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(P3))
    a = ap.parse_args(argv)
    modal = modal_records()
    led, local = ledger_rows({r["task"] for r in modal})
    allrows = led + modal
    tot = {"usd": round(sum(r["usd"] for r in allrows), 2), "container_h": round(sum(r["container_s"] for r in allrows) / 3600, 2),
           "containers": sum(r["containers"] for r in allrows)}
    rec = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "totals_modal": tot, "rows": allrows, "local": local,
           "simulation_cache": sim_cache(), "reference_cache_files": ref_cache(), "fit_times": fit_times(),
           "gpu": "not used: all methods are frozen CPU code; GPU use would require changing method code (forbidden by the lock)",
           "prices": PRICE}
    out = Path(a.out_dir)
    (out / "COMPUTE_SUMMARY.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Phase 3 compute summary (goal4 sections 58-59)", "", f"Generated {rec['generated_utc']} by scripts/p3/compute_summary.py.",
             f"Modal list prices: ${PRICE['core_h']} per physical core-hour, ${PRICE['gib_h']} per GiB-hour; containers 2 cores / 6 GiB.", "",
             f"**Modal total: about ${tot['usd']}** over {tot['containers']} container calls ({tot['container_h']} container-hours).", "",
             "| task | backend | containers | container-s | wall-s | ~USD | source |", "|---|---|---|---|---|---|---|"]
    for r in allrows:
        lines.append(f"| {r['task']} | {r['backend']} | {r['containers']} | {r['container_s']:.0f} | {r.get('wall_s') or '-'} | {r['usd']:.2f} | "
                     f"{r['source']} |")
    lines += ["", "## Simulation cache (content-addressed trajectory store)", "", "| service | trajectories | from cache | hit rate |",
              "|---|---|---|---|"]
    for k, v in rec["simulation_cache"].items():
        lines.append(f"| {k} | {v['trajectories']} | {v['served_from_cache']} | {v['cache_hit_rate']} |")
    lines += ["", f"Reference-control cache files per suite: {json.dumps(rec['reference_cache_files'])}", "", "## Local machine", ""]
    lines += [f"- {x}" for x in local]
    lines += ["", "## GPUs", "", rec["gpu"] + ".", ""]
    (out / "COMPUTE_SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"totals_modal": tot, "n_rows": len(allrows), "sim_cache": rec["simulation_cache"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
