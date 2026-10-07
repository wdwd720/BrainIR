"""Pre-freeze MDE of the active-design success rule on the synthetic DEV tier (ORCHESTRATOR SIDE; PROTOCOL.md section 5.17; the logic
and its rationale are in `brainir_causal.active_mde`).

    uv run --no-sync --project phase4 python scripts/p4/active_mde.py run            # THE full run (one command; see below)
        [--cls eval_xl_np | eval_xl] [--workers P] [--threads T] [--containers 96] [--mem-budget-gb 112] [--learners ...]
        [--designers random,fixed] [--loop-seeds 0,1,2] [--budget 200] [--systems s1,s2 --out FILE] [--n-sim 1000] [--n-boot 1000]
        [--summary-cls eval_xl | --summary-local] [--force] [--run-id ID] [--verify-sample 0|1] [--verify-budget 10]
        [--tier dev] [--allow-no-draw]                                                # another tier: smoke runs only
    uv run --no-sync --project phase4 python scripts/p4/active_mde.py preflight [--systems s1,s2] [--tier dev] [--allow-no-draw]
    uv run --no-sync --project phase4 python scripts/p4/active_mde.py profile --systems s1,s2 [--packings 16x2,8x4,4x8] [--out FILE]
    uv run --no-sync --project phase4 python scripts/p4/active_mde.py analyze-profile [--out PROFILE_FILE] [--containers 96]
    uv run --no-sync --project phase4 python scripts/p4/active_mde.py resummarize [--out FILE] [--summary-cls eval_xl | --summary-local]

RUN. Every (system, learner, designer, loop seed) loop of PROTOCOL 5.17 with the benchmark reference learners (FULL-STATE on every
system, TRUE-STATE on the compressible ones; designers random and fixed; loop seeds 0-2; checkpoints 10, 25, 50, 100, 200), PACKED:
`plan_packs` assigns the loops to `--containers` containers of class `--cls` (data streams longest first, then a local search of
loop moves and swaps on `pack_makespan`, the cost model of the container schedule); each container runs
`active_mde.reference_pack_job` (phase 1 once per data stream, then one fit + evaluation task per (loop, checkpoint) on P worker
processes x T threads, longest eligible first, admitted within the memory budget; every finished task goes to the run's progress
store, a modal.Dict, so that a preempted and restarted container, or a whole run resumed with `--run-id`, runs only unfinished
tasks. CURRENT LIMIT: P1's run_call starts job subprocesses without the Modal client or credentials, so the store is unavailable in
the containers and the packs run without it. The default class is therefore the NON-PREEMPTIBLE eval_xl_np (3 x the list price); with
`--cls eval_xl` a preempted pack reruns all its tasks). Beside the packs, two loops of the
run are ALSO run unpacked (`verification_sample`) and their checkpoint rows are compared with the packed ones bit for bit
(`compare_rows`). Then the summary: `active_mde.summary_specs` (learner x
scenario x chunk of 100 simulated suites) spread over up to 8 containers of `--summary-cls` and merged here (or `--summary-local`).
A readiness check refuses to start unless the dev tier's latest build covers the whole tier without failures and is newer than every
generator source file (the tier was built from the generator the image bakes; the containers check the system hashes again);
`--force` skips it for smoke runs. DRAWS (reference learner v2: TRUE-STATE encodes [z, draw]; `active_mde` module docstring): before
the packs, `active_mde.draw_preflight` runs on every system with TRUE-STATE loops (host-gated `PRE_CLS` containers: it constructs
the synthetic system, whose content hash is checked, so it needs the reference numerics) and `draw_verdict` refuses the run
when the tier's truth carries draws but a system lacks them for some D0 or held-out record, D0's draws differ in length or are not
finite, or its generator gives no draw_effective, and when the tier carries no draws at all (`--allow-no-draw` for smoke tiers);
after the packs, `draw_violations` refuses to publish an MDE when any TRUE-STATE fit whose training draws VARY ran without its draw
context, or any draw was missing or inconsistent (the rows are kept for diagnosis). A fit whose training draws are all constant runs
without the context legitimately (z alone is exact given that draw): recorded as draw_context False, reason "constant draws", not
refused. Writes research/phase4/ACTIVE_MDE.json
(rows, loops, packs, plan, draw preflight, verification, cost, summary) and ACTIVE_MDE.md, and adds a row to MODAL_RUNS.md (E11
section).

PREFLIGHT. The run's draw preflight alone (`draw_check`: host-gated `PRE_CLS` containers, cents): the verdict and every system's counts, printed
and recorded in MODAL_RUNS.md. Run it on the rebuilt tier before `run`.

PROFILE. The same loops under several packings (PxT in one container of --cls each), plus small verification loops run both packed
and UNPACKED (`active_mde.reference_loop_job`, one loop per container at the same thread count): per packing the pack's wall time,
every task's fit / evaluation wall time and peak memory, and whether every verification row is bit-identical to its unpacked twin.

COST MODEL (the planner's; calibrated from the profile, research/phase4/ACTIVE_MDE.md): task seconds = s0 + s1 x n_obs, task memory
GiB = g0 + g1 x the float64 size in GiB of the task's n_records x rows x n_obs table, per learner (they order and admit tasks; results
never depend on them).
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import active_mde as AM  # noqa: E402
from brainir_causal import calibrate as CAL  # noqa: E402
from brainir_causal import suites as SU  # noqa: E402

OUT = ROOT / "research" / "phase4" / "ACTIVE_MDE.json"
MODAL_RUNS = ROOT / "research" / "phase4" / "MODAL_RUNS.md"
BUILD_RECORD = ROOT / "research" / "phase4" / "SYNTHETIC_DATA_BUILD.json"
TIER = "dev"
REMOTE_EVAL, REMOTE_FIT = "/evalvol/data/suites", "/fitvol/data/suites"
CHECKPOINTS = (10, 25, 50, 100, 200)
#: per learner: task seconds = s0 + s1 x n_obs; task GiB = g0 + g1 x (n_records x rows x n_obs x 8 bytes / 2^30). Seconds: the
#: profile at 16 workers x 2 threads on eval_xl (research/phase4/ACTIVE_MDE_PROFILE.json, packing 16x2: mean task wall of the five
#: checkpoints on systems of 66 and 230 observed units); GiB: the profile's container peak (54 GB for 16 concurrent tasks) with margin
COST = {"full_state": {"s0": 569.0, "s1": 1.914, "g0": 2.5, "g1": 2.0},
        "true_state": {"s0": 380.0, "s1": 0.333, "g0": 2.5, "g1": 2.0}}
#: packing chosen by the profile (16 x 2 threads: 1.7 x the throughput per core of 8 x 4; both bit-identical to unpacked loops) on the
#: NON-PREEMPTIBLE eval_xl_np (P1; billed at 3 x the list rate): a preempted pack would rerun all its tasks, because the progress store
#: is unavailable in job subprocesses. `--cls eval_xl` runs at a third of the price with that risk. The summary (about a minute; a
#: preempted summary container just reruns its input) stays on the preemptible eval_xl.
DEFAULTS = {"cls": "eval_xl_np", "summary_cls": "eval_xl", "workers": 16, "threads": 2, "containers": 96, "mem_budget_gb": 112.0}
# the draw preflight constructs each synthetic system (sim_context checks its content hash), so it runs on a HOST-GATED class: on an
# ungated host (AVX-512) the construction differs in the last bits and the hash check refuses the system (2026-09-27, 19 of 46)
PRE_CLS = "eval_s"
#: phase-1 seconds of a stream at budget b: (p0 + p1 x n_obs) x b / 200 (profile: 97 s at 66 and 265 s at 230 observed units)
PHASE1 = {"p0": 30.0, "p1": 1.02}
PROGRESS_DICT = "brainir-p4-mde-{run}"          # the modal.Dict of a run's finished tasks (resume after preemption; removed on success)
#: LOCAL execution (P4_BACKEND=local; research/phase4/LOCAL_EXECUTION_PLAN.md): the progress store is a directory on the local eval
#: volume (active_mde.ProgressStore "dir"), kept after the run (its rows are in the run record); a stopped or interrupted local run
#: resumes with --run-id and runs only its unfinished tasks
PROGRESS_DIR_LOCAL = "/evalvol/_mde_progress/{run}"
VERIFY_FIELDS = ("EE", "EE_ci95", "EE_pooled", "n_cells", "n_items", "n_abstained", "n_failed", "n_records", "experiments", "trajectories",
                 "spent", "n_probe_encodes")


# ================================================================================================================ planning
def loop_job(sid: str, learner: str, designer: str, seed: int, budget: int, threads: int, info: dict, *, tag: str = "",
             tier: str = TIER) -> dict:
    """One loop job (the keys of `active_mde.reference_loop_job` / `loop_phase1`) with the planner's cost features."""
    n_obs = len(info["observed"])
    rows = int(round(float(info["t_end_default"]) / float(info["dt"]))) + 1
    job = {"sid": sid, "learner": learner, "designer": designer, "seed": int(seed), "budget": int(budget),
           "checkpoints": [c for c in CHECKPOINTS if c <= budget] or [int(budget)], "learner_cfg": {"threads": int(threads)},
           "heldout_root": REMOTE_EVAL, "heldout_tier": tier, "public_root": REMOTE_FIT, "public_tier": tier,
           "internal_path": f"{REMOTE_EVAL}/{tier}/internal_records.json",
           "store_root": f"/tmp/p4mde{tag}/{SU._safe(sid)}_{learner}_{designer}_s{seed}/store", "store_read_roots": ["/evalvol/store"],
           "generator": [SU.GENERATOR_CONTAINER, "p4synth"]}
    job["pred"] = {**COST[learner], "n_obs": n_obs, "rows": rows}
    return job


def pred_task_s(job: dict) -> float:
    p = job["pred"]
    return float(p["s0"]) + float(p["s1"]) * float(p["n_obs"])


def _slots_makespan(task_s: list[float], workers: int) -> float:
    """Longest-first list schedule of task durations on `workers` slots: the finishing time of the last slot."""
    slots = [0.0] * max(1, int(workers))
    for t in sorted(task_s, reverse=True):
        k = slots.index(min(slots))
        slots[k] += t
    return max(slots)


def _pack_tasks(p: list[dict]) -> list[float]:
    return [pred_task_s(j) for j in p for _ in j["checkpoints"]]


def phase1_s(job: dict) -> float:
    return (PHASE1["p0"] + PHASE1["p1"] * float(job["pred"]["n_obs"])) * float(job["budget"]) / 200.0


def pack_makespan(p: list[dict], workers: int) -> float:
    """The container schedule of `active_mde.reference_pack_job` on the cost model: every stream's phase 1 on a slot first (longest
    first), then its tasks, released when that phase 1 ends, longest eligible first on the earliest free slot."""
    streams: dict[str, list[dict]] = {}
    for j in p:
        streams.setdefault(AM.stream_id(j), []).append(j)
    slots = [0.0] * max(1, int(workers))
    pending = []
    for k in sorted(streams, key=lambda k_: -phase1_s(streams[k_][0])):
        i = slots.index(min(slots))
        slots[i] += phase1_s(streams[k][0])
        pending += [(slots[i], pred_task_s(j)) for j in streams[k] for _ in j["checkpoints"]]
    while pending:
        i = slots.index(min(slots))
        t = slots[i]
        ready = [x for x in pending if x[0] <= t + 1e-9]
        if not ready:
            slots[i] = min(x[0] for x in pending)
            continue
        pick = max(ready, key=lambda x: x[1])
        pending.remove(pick)
        slots[i] = t + pick[1]
    return max(slots)


def plan_packs(jobs: list[dict], containers: int, workers: int = 16, max_moves: int = 4000) -> list[list[dict]]:
    """Assignment of loops to containers. First the DATA STREAMS (`active_mde.stream_id`: the loops of both learners that share one
    phase 1) longest-processing-time first by predicted work (the sum over its loops of checkpoints x the task time); then a local
    search over single LOOPS (300 streams on ~96 containers leave some containers a whole stream heavier): a loop moves out of the
    container with the largest predicted makespan (`pack_makespan`: phase 1 and the released tasks on `workers` slots) while that
    lowers the larger of the two makespans involved. A stream split across two containers runs its phase 1 in both."""
    streams: dict[str, list[dict]] = {}
    for j in jobs:
        streams.setdefault(AM.stream_id(j), []).append(j)
    n = max(1, min(int(containers), len(jobs)))
    heap = [(0.0, i) for i in range(n)]
    groups: list[list[dict]] = [[] for _ in range(n)]

    def work(grp):
        return sum(pred_task_s(j) * len(j["checkpoints"]) for j in grp)
    for k in sorted(streams, key=lambda k_: (-work(streams[k_]), k_)):
        load, i = heapq.heappop(heap)
        groups[i] += streams[k]
        heapq.heappush(heap, (load + work(streams[k]), i))

    def ms(g: list[dict]) -> float:
        return pack_makespan(g, workers) if g else 0.0
    cur = [ms(g) for g in groups]
    for _ in range(int(max_moves)):
        i = max(range(n), key=lambda x: cur[x])
        best = None
        for j in sorted(range(n), key=lambda x: cur[x])[:12]:
            if j == i:
                continue
            for idx, jb in enumerate(groups[i]):
                gi = groups[i][:idx] + groups[i][idx + 1:]
                a_, b_ = ms(gi), ms(groups[j] + [jb])                        # move one loop i -> j
                if max(a_, b_) < cur[i] - 1e-6 and (best is None or max(a_, b_) < best[0]):
                    best = (max(a_, b_), j, idx, None, a_, b_)
                for jdx, kb in enumerate(groups[j]):                          # swap a loop of i with one of j
                    if kb["learner"] == jb["learner"] and kb["pred"]["n_obs"] == jb["pred"]["n_obs"]:
                        continue
                    a_, b_ = ms(gi + [kb]), ms(groups[j][:jdx] + groups[j][jdx + 1:] + [jb])
                    if max(a_, b_) < cur[i] - 1e-6 and (best is None or max(a_, b_) < best[0]):
                        best = (max(a_, b_), j, idx, jdx, a_, b_)
        if best is None:
            break
        _, j, idx, jdx, a_, b_ = best
        moved = groups[i].pop(idx)
        if jdx is not None:
            groups[i].append(groups[j].pop(jdx))
        groups[j].append(moved)
        cur[i], cur[j] = a_, b_
    return [g for g in groups if g]


def predicted_makespan(packs: list[list[dict]], workers: int) -> float:
    """The slowest container on the cost model (`pack_makespan`: phase 1 and the released tasks; memory ignored)."""
    return max((pack_makespan(p, workers) for p in packs), default=0.0)


# ================================================================================================================ readiness
def generator_state() -> dict:
    """sha256 over the generator's source files (sorted relative paths and contents) and their newest modification time (UTC)."""
    src = ROOT / SU.GENERATOR_REL
    files = sorted(p for p in src.rglob("*.py") if "__pycache__" not in p.parts)
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(src).as_posix().encode() + b"\0" + p.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    newest = max(p.stat().st_mtime for p in files)
    return {"sha256": h.hexdigest(), "n_files": len(files),
            "newest_utc": datetime.fromtimestamp(newest, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}


def readiness(systems: list[str] | None = None) -> dict:
    """Whether every requested dev system (default: the whole tier) has a SUCCESSFUL build newer than every generator source file,
    each system's LATEST build record counting (module docstring). A tier built in one run passes exactly as before; a STREAMED tier
    (built in batches of systems; LOCAL_EXECUTION_PLAN.md section 7) passes for the systems its batches built."""
    gen = generator_state()
    runs = json.loads(BUILD_RECORD.read_text(encoding="utf-8"))["runs"] if BUILD_RECORD.exists() else []
    devs = [r for r in runs if r.get("what") == f"synthetic tier {TIER}"]
    out = {"generator": gen, "ok": False}
    if not devs:
        out["why"] = "no dev build recorded"
        return out
    latest: dict = {}
    for r in devs:                                       # in recording order: a later record of a system replaces an earlier one
        for s, v in (r.get("systems") or {}).items():
            latest[s] = (str(r.get("created_utc")), isinstance(v, dict) and "error" not in v)
    base = SU.tier_dirs(TIER, SU.SUITES)["base"]
    tier_ids = sorted(json.loads((base / "internal_records.json").read_text(encoding="utf-8"))) if (base / "internal_records.json").exists() else []
    want = sorted(systems) if systems else tier_ids
    missing = [s for s in want if s not in latest]
    failed = [s for s in want if s in latest and not latest[s][1]]
    stale = [s for s in want if s in latest and latest[s][0] <= gen["newest_utc"]]
    out.update({"dev_build_utc": max((latest[s][0] for s in want if s in latest), default=None), "n_systems": len(want) - len(missing),
                "n_tier_systems": len(tier_ids), "failed": failed, "internal_records": bool(tier_ids)})
    if not tier_ids:
        out["why"] = "data/phase4/suites/dev/internal_records.json is missing"
    elif missing:
        out["why"] = f"{len(missing)} requested dev systems have no build ({missing[:5]})"
    elif failed:
        out["why"] = f"dev systems whose latest build failed: {failed[:5]}"
    elif stale:
        out["why"] = f"dev systems built before the generator sources changed ({gen['newest_utc']}): {stale[:5]}"
    else:
        out["ok"] = True
    return out


# ================================================================================================================ Modal
def _backend(classes: list[str]):
    from brainir_causal.p4modal.app import Backend
    return Backend(classes=sorted(set(classes)), extra_dirs={SU.GENERATOR_REL: SU.GENERATOR_CONTAINER})


def _unwrap(r) -> tuple[dict | None, str | None]:
    """(the job's result, None) or (None, the error); a pack's result gets the container's peak memory and wall time."""
    if isinstance(r, BaseException) or not isinstance(r, dict) or "result" not in r:
        return None, str(r)[:3000]
    out = r["result"]
    if isinstance(out, dict) and isinstance(out.get("pack"), dict):
        out["pack"]["peak_container_mb"] = r.get("peak_container_mb")
        out["pack"]["container_wall_s"] = r.get("container_wall_s")
        out["pack"]["host"] = (r.get("__host__") or {}).get("model")
    return out, None


def run_packs(be, packs: list[list[dict]], *, cls: str, workers: int, threads: int, mem_budget_gb: float, timeout_s: float,
              n_boot: int | None = None, progress: dict | None = None) -> list[tuple[dict | None, str | None]]:
    payloads = [[{"loops": p, "workers": int(workers), "threads": int(threads), "mem_budget_gb": float(mem_budget_gb),
                  "work_dir": f"/tmp/p4mde_pack{i}", **({"n_boot": int(n_boot)} if n_boot else {}),
                  **({"progress": progress} if progress else {})}] for i, p in enumerate(packs)]
    res = be.call("brainir_causal.active_mde:reference_pack_job", payloads, cls=cls, threads=int(threads),
                  reload=["fit", "eval", "store"], timeout_s=timeout_s, eager=True)
    return [_unwrap(r) for r in res]


def verification_sample(info: dict, comp: set, learners: list[str], threads: int, *, budget: int = 10, tier: str = TIER,
                        systems: list[str] | None = None) -> list[dict]:
    """Loops of the run that are ALSO run unpacked (`active_mde.reference_loop_job`, one per container) to check the packed rows bit
    for bit: both learners of the random-design stream, loop seed 0, on the compressible system of median size among `systems`, at
    a short `budget` (default 10: about 13 minutes, so the check never outlasts the packs). The random and fixed designers ignore
    the remaining budget, so the rows at the checkpoints up to `budget` are those of the full-budget loop (tested)."""
    pool = [s for s in (systems or sorted(info)) if s in comp]
    cand = sorted((len(info[s]["observed"]), s) for s in pool)
    if not cand:
        return []
    s = cand[len(cand) // 2][1]
    return [loop_job(s, ln, "random", 0, int(budget), threads, info[s], tag="_ver", tier=tier) for ln in learners
            if ln != "true_state" or s in comp]


def drop_progress(run_id: str) -> None:
    """Remove a finished run's progress store (its rows are in the run record). Absent when the packs could not reach Modal from
    their job subprocess (P1's run_call gives job subprocesses no Modal client or credentials): nothing to remove then. A LOCAL
    run keeps its directory store (disk only)."""
    if os.environ.get("P4_BACKEND") == "local":
        return
    try:
        import modal
        modal.Dict.objects.delete(PROGRESS_DICT.format(run=run_id))
    except Exception as exc:  # noqa: BLE001 - a leftover dictionary is harmless (recorded)
        if "NotFound" not in type(exc).__name__:
            print(f"note: the progress store of run {run_id} was not removed: {type(exc).__name__}: {exc}", flush=True)


def run_unpacked(be, jobs: list[dict], *, cls: str, threads: int, timeout_s: float) -> list[tuple[dict | None, str | None]]:
    res = be.call("brainir_causal.active_mde:reference_loop_job", [[j] for j in jobs], cls=cls, threads=int(threads),
                  reload=["fit", "eval", "store"], timeout_s=timeout_s, eager=True)
    return [_unwrap(r) for r in res]


def run_summary(rows: list[dict], *, n_sim: int, n_boot: int, cls: str | None, be=None, max_containers: int = 8) -> dict:
    """`active_mde.summarize` with its independent calls (`active_mde.summary_specs`: learner x scenario x chunk) spread over up to
    `max_containers` containers of `cls` (all their cores), merged here (`active_mde.summarize_from_parts`); locally (cls None) on 4
    processes. The result does not depend on the layout."""
    kw = {"n_sim": int(n_sim), "n_boot": int(n_boot)}
    if cls is None:
        return AM.summarize(rows, workers=4, **kw)
    from brainir_causal.p4modal.app import CLASSES
    specs = AM.summary_specs(rows, **kw)
    ncpu = int(CLASSES[cls]["cpu"])
    k = max(1, min(int(max_containers), -(-len(specs) // ncpu)))
    groups = [specs[i::k] for i in range(k)]
    res = be.call("brainir_causal.active_mde:summary_parts_job", [[{"rows": rows, "specs": g, "workers": ncpu}] for g in groups], cls=cls,
                  threads=1, timeout_s=4 * 3600, eager=True)
    parts: dict = {}
    for r in res:
        out, err = _unwrap(r)
        if out is None:
            raise RuntimeError(f"a summary container failed: {err}")
        parts.update(out)
    return AM.summarize_from_parts(rows, specs, parts, **kw)


# ================================================================================================================ records
def next_e11_number() -> int:
    nums = []
    for line in MODAL_RUNS.read_text(encoding="utf-8").splitlines():
        if line.startswith("| E11-"):
            try:
                nums.append(int(line.split("|")[1].strip().split("-")[1].split()[0]))
            except (IndexError, ValueError):
                continue
    return max(nums, default=0) + 1


def add_modal_row(purpose: str, app: str, resources: str, cost: str, notes: str) -> str:
    """Insert one row after the last E11 row of MODAL_RUNS.md (the E11 section's table)."""
    lines = MODAL_RUNS.read_text(encoding="utf-8").splitlines()
    idx = max((i for i, ln in enumerate(lines) if ln.startswith("| E11-")), default=None)
    if idx is None:
        raise RuntimeError("no E11 section in MODAL_RUNS.md")
    tag = f"E11-{next_e11_number()}"
    app = f"brainir-p4 ({app})" if app.startswith("ap-") else app             # the log's app column: name (app id)
    row = f"| {tag} | {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())} | {app} | {purpose} | {resources} | {cost} | {notes} |"
    lines.insert(idx + 1, row)
    MODAL_RUNS.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return tag


def _draw_line(rec: dict) -> str:
    d = rec.get("draw_context") or {}
    v = ((rec.get("draw_preflight") or {}).get("verdict") or {})
    warn = v.get("warnings") or {}
    return (f"the tier's truth carries draws: {v.get('draws')}; {d.get('n_draw_context')} of {d.get('n_fits')} fits used the draw "
            f"context ({d.get('n_draw_required')} required it; {d.get('n_constant_draws')} ran without it because their training draws "
            f"were constant, so z alone is exact); registrations without a draw: {d.get('n_registered_without_draw')}; "
            f"probe encodes: {d.get('n_probe_encodes')}"
            + (f"; preflight warnings (draws constant over D0): {', '.join(sorted(warn))}" if warn else ""))


def _verification_line(v: dict | None) -> str:
    if not v:
        return "not run"
    return (f"{v.get('verdict')} ({v.get('n_identical')} of {v.get('n_rows')} checkpoint rows of the loops {', '.join(v.get('loops') or [])} "
            f"at budgets {v.get('budgets')} equal to their unpacked runs bit for bit)")


def _fmt(v, nd: int = 3) -> str:
    if v is None:
        return "not reached"
    return f"{float(v):.{nd}f}" if isinstance(v, float) else str(v)


def write_md(rec: dict, path: Path) -> None:
    s = rec["summary"]
    pk = rec.get("packing") or {}
    lines = ["# Active-design success rule: minimum detectable effect on the dev suite (pre-freeze)", "",
             "PROTOCOL.md section 5.17 requires the minimum detectable effect (MDE) of the active-design success rule to be computed by "
             "simulation on the dev suite before the freeze. Code: `brainir_causal.active_mde` (reference-learner adapter, packed loops, "
             "checkpoint EE, summary) and `scripts/p4/active_mde.py` (Modal driver). Tests: `phase4/tests/test_active_mde.py`.", "",
             "## What was run", "",
             f"- Tier: synthetic dev ({rec['n_systems']} systems; TRUE-STATE on the {rec['n_compressible']} compressible ones), dev build "
             f"{rec.get('readiness', {}).get('dev_build_utc')}, generator sha256 {str(rec.get('readiness', {}).get('generator', {}).get('sha256'))[:16]}.",
             f"- Learners: the benchmark references {', '.join(rec['learners'])} (no method exists before the freeze), refitted from scratch "
             "on D0 + all loop data at every checkpoint, seed = the loop seed.",
             f"- Designers: {', '.join(rec['designers'])}; loop seeds {rec['loop_seeds']}; budget {rec['budget']} experiments, checkpoints "
             f"{rec['checkpoints']}; batch 5; {rec['n_loops']} loops, {len(rec['rows'])} checkpoint rows.",
             "- Quality per checkpoint: the class-balanced EE at the primary horizon on the verdict items of the system's dev eval part "
             "(the verdict's EE code path), abstentions scored as no effect.",
             f"- TRUE-STATE draw context (reference learner v2: the state is [z, draw]): {_draw_line(rec)}.",
             f"- Execution: {len(rec.get('packs') or [])} containers of class {pk.get('cls')} ({pk.get('workers')} worker processes x "
             f"{pk.get('threads')} threads each, memory budget {pk.get('mem_budget_gb')} GiB), (loop, checkpoint) tasks longest first, "
             f"phase 1 once per data stream; verification of this run: {_verification_line(rec.get('verification'))}.",
             f"- MDE: `loop.mde_by_simulation` per learner, scenarios in parallel with independent seeds ({s['n_sim']} simulated suites "
             f"each, bootstrap {s['n_boot']}, alpha {s['alpha_per_rule']} per rule, power target {s['power_target']}): simulated suites "
             "with the observed per-system curves and noise; the method's designer reaches at budget b what `random` reaches at e x b "
             "(efficiency e). The e = 1 row is the false-positive rate; the weaker-fixed nulls shift the fixed design's curve up by "
             f"{', '.join(str(o) for o in s['null_fixed_offsets'])} EE (only the random comparison binds rule (i)).", "", "## Results", ""]
    for ln, m in s["per_learner"].items():
        mm = m["mde"]
        fp = mm["false_positive_rate"] or {}
        lines += [f"### Learner: {ln}", "",
                  f"Systems used {mm['n_systems']}; excluded {mm['n_excluded_systems']}"
                  + (": " + "; ".join(f"{k} ({v})" for k, v in sorted(m["excluded"].items())) if m["excluded"] else "")
                  + f". Checkpoint errors: {m['n_checkpoint_errors']}. Noise medians: per-seed offset {mm['noise_medians']['sd_offset']:.4g}, "
                  f"per-budget residual {mm['noise_medians']['sd_residual']:.4g} (EE units).", "",
                  "| | rule (i) fixed budget | rule (ii) budget ratio | union (i) or (ii) |", "|---|---|---|---|",
                  f"| MDE (smallest efficiency with power >= {mm['power_target']}) | {_fmt(mm['mde']['fixed_budget'], 2)} | "
                  f"{_fmt(mm['mde']['budget_ratio'], 2)} | {_fmt(mm['mde']['either'], 2)} |",
                  f"| false-positive rate at e = 1 | {_fmt(fp.get('fixed_budget'))} | {_fmt(fp.get('budget_ratio'))} | {_fmt(fp.get('either'))} |"]
        for o, row in sorted(mm["false_positive_rate_weaker_fixed"].items(), key=lambda kv: float(kv[0])):
            lines.append(f"| false-positive rate, fixed curve +{float(o):g} EE | {_fmt(row.get('fixed_budget'))} | {_fmt(row.get('budget_ratio'))} | "
                         f"{_fmt(row.get('either'))} |")
        lines += ["", "Power by efficiency e (the own designer reaches at budget b what `random` reaches at e x b):", "",
                  "| e | ~true budget ratio 1/e | rule (i) | rule (ii) | union | mean estimated ratio |", "|---|---|---|---|---|---|"]
        for e, row in sorted(mm["table"].items(), key=lambda kv: float(kv[0])):
            lines.append(f"| {float(e):g} | {row['true_ratio_approx']:.3f} | {row['fixed_budget']:.3f} | {row['budget_ratio']:.3f} | "
                         f"{row['either']:.3f} | {row['mean_estimated_ratio']:.3f} |")
        lines += ["", f"Budget-ratio note: {mm.get('ratio_interpretation')}", ""]
    cost = rec.get("modal_cost") or {}
    lines += ["## Caveats", "",
              "- The MDE depends on the learner; before the freeze only the benchmark references exist. A method whose EE curves are "
              "noisier (between loop seeds or budgets) has a larger MDE, a smoother one a smaller MDE.",
              "- The simulation models the method's designer as a pure acceleration of `random`'s curve (the same curve reached e times "
              "sooner); real designers may change the curve's shape.",
              "- `fixed` is independent of the loop seed: its three loops differ only in the learner's seed.",
              f"- Failed loops: {rec['n_failed_loops']}; failed packs: {len(rec.get('failed_packs') or [])}; checkpoint errors: "
              f"{rec['n_checkpoint_errors']}. Failed checkpoints are charged (never dropped); systems with a charged benchmark-designer "
              "cell are excluded (listed above and in ACTIVE_MDE.json).", "",
              f"Cost: {cost.get('usd_approx_total')} USD (list-price estimate from container seconds); wall {rec['wall_s']} s "
              f"(loops {rec.get('loops_wall_s')} s, summary {rec.get('summary_wall_s')} s); Modal app {cost.get('app_id')}.", ""]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


# ================================================================================================================ commands
def _systems(args) -> tuple[list[str], dict, dict, set]:
    tier = getattr(args, "tier", TIER) or TIER
    base = SU.tier_dirs(tier, SU.SUITES)["base"]
    info = json.loads((base / "internal_records.json").read_text(encoding="utf-8"))
    summaries = CAL.system_truth_summaries(SU.SUITES, tier)
    sids = sorted(info)
    if getattr(args, "systems", ""):
        want = [s for s in args.systems.split(",") if s]
        missing = [s for s in want if s not in info]
        if missing:
            raise SystemExit(f"unknown {tier} systems {missing}")
        sids = want
    comp = {s for s in sids if CAL.compressible(summaries.get(s, {})) is not None}
    return sids, info, summaries, comp


def preflight_jobs(sids: list[str], comp: set, info: dict, learners: list[str], tier: str) -> list[dict]:
    """One `draw_preflight` job per system with TRUE-STATE loops."""
    return [loop_job(s, "true_state", "random", 0, 10, 1, info[s], tag="_pre", tier=tier) for s in sids
            if s in comp and "true_state" in learners]


def draw_check(be, pre_jobs: list[dict], *, allow_no_draw: bool) -> tuple[list[dict], dict]:
    """(`active_mde.draw_preflight` of every job on host-gated PRE_CLS containers, the run's `draw_verdict`)."""
    if not pre_jobs:
        return [], {"ok": True, "draws": None, "why": "no TRUE-STATE loops", "systems": {}, "warnings": {}}
    res = be.call("brainir_causal.active_mde:draw_preflight", [[j] for j in pre_jobs], cls=PRE_CLS, threads=1,
                  reload=["fit", "eval", "store"], timeout_s=1800, eager=True)
    pre = []
    for j, r in zip(pre_jobs, res):
        out_, err_ = _unwrap(r)
        pre.append(out_ if out_ is not None else {"sid": j["sid"], "error": err_})
    return pre, AM.draw_verdict(pre, allow_no_draw=allow_no_draw)


def cmd_preflight(args) -> int:
    """The draw preflight alone (module docstring, PREFLIGHT). Exit code 0 when the run would pass it, 2 when it would be refused."""
    sids, info, _summaries, comp = _systems(args)
    jobs = preflight_jobs(sids, comp, info, ["true_state"], args.tier)
    with _backend([PRE_CLS]) as be:
        pre, verdict = draw_check(be, jobs, allow_no_draw=args.allow_no_draw)
        cost = be.cost_summary()
    print(json.dumps({"tier": args.tier, "verdict": verdict, "systems": pre}, indent=1))
    add_modal_row(f"draw preflight only (`active_mde.py preflight`, tier {args.tier}, {len(jobs)} compressible systems)",
                  str(cost.get("app_id")), f"{len(jobs)} x {PRE_CLS}", f"~${cost.get('usd_approx_total')}",
                  ("passes" if verdict["ok"] else f"REFUSED: {verdict['why']}")
                  + (f"; warnings: {len(verdict.get('warnings') or {})}" if verdict.get("warnings") else ""))
    return 0 if verdict["ok"] else 2


def cmd_run(args) -> int:
    out = args.out or OUT
    smoke = (bool(args.systems) or args.budget != 200 or args.loop_seeds != "0,1,2" or args.learners != "full_state,true_state"
             or args.designers != "random,fixed" or args.tier != TIER)
    if smoke and args.out is None:
        raise SystemExit("smoke runs (--systems, another tier, budget, loop seeds, learners or designers) must give --out")
    if args.tier != TIER and not args.force:
        raise SystemExit(f"the MDE is computed on the {TIER} tier; --tier {args.tier} is for smoke runs only (add --force)")
    ready = (readiness([x for x in args.systems.split(",") if x] or None) if args.tier == TIER
             else {"ok": False, "why": f"smoke run on tier {args.tier} (not checked)"})
    if not ready["ok"] and not args.force:
        raise SystemExit(f"not ready: {ready.get('why')} (use --force for a smoke run on the current tier)")
    sids, info, _summaries, comp = _systems(args)
    learners = [x for x in args.learners.split(",") if x]
    designers = [x for x in args.designers.split(",") if x]
    seeds = [int(x) for x in args.loop_seeds.split(",") if x]
    jobs = [loop_job(s, ln, d, sd, args.budget, args.threads, info[s], tier=args.tier) for s in sids for ln in learners
            if ln != "true_state" or s in comp for d in designers for sd in seeds]
    packs = plan_packs(jobs, args.containers, args.workers)
    est = predicted_makespan(packs, args.workers)
    run_id = args.run_id or uuid.uuid4().hex[:12]
    progress = ({"dir": PROGRESS_DIR_LOCAL.format(run=run_id), "run": run_id} if os.environ.get("P4_BACKEND") == "local"
                else {"dict": PROGRESS_DICT.format(run=run_id), "run": run_id})
    ver_jobs = (verification_sample(info, comp, learners, args.threads, budget=min(args.verify_budget, args.budget), tier=args.tier,
                                    systems=sids) if args.verify_sample and "random" in designers and 0 in seeds else [])
    ver_cls = "eval_s" if args.threads <= 4 else "eval_l"
    print(f"run {run_id} (resume with --run-id {run_id}): {len(jobs)} loops ({len(sids)} systems, {len(comp)} compressible) in "
          f"{len(packs)} containers of {args.cls} ({args.workers} x {args.threads} threads); predicted phase-2 makespan {est / 60:.0f} "
          f"min; {len(ver_jobs)} unpacked verification loops on {ver_cls}", flush=True)
    t0 = time.time()
    classes = list(dict.fromkeys([args.cls, PRE_CLS] + ([args.summary_cls] if args.summary_cls and not args.summary_local else [])
                                 + ([ver_cls] if ver_jobs else [])))
    pre_jobs = preflight_jobs(sids, comp, info, learners, args.tier)
    with _backend(classes) as be:
        pre, verdict = draw_check(be, pre_jobs, allow_no_draw=args.allow_no_draw)
        print(f"draw preflight: {json.dumps({k: v for k, v in verdict.items() if k != 'systems'})}", flush=True)
        if not verdict["ok"]:
            cost = be.cost_summary()
            for sid_, why in sorted(verdict["systems"].items())[:20]:
                print(f"  {sid_}: {why}", flush=True)
            add_modal_row(f"REFUSED by the draw preflight: {verdict['why']}", str(cost.get("app_id")), f"{len(pre_jobs)} x {PRE_CLS}",
                          f"~${cost.get('usd_approx_total')}", "no pack was started")
            return 2
        with ThreadPoolExecutor(max_workers=2) as tp:
            fp = tp.submit(run_packs, be, packs, cls=args.cls, workers=args.workers, threads=args.threads,
                           mem_budget_gb=args.mem_budget_gb, timeout_s=args.timeout, progress=progress)
            fv = tp.submit(run_unpacked, be, ver_jobs, cls=ver_cls, threads=args.threads, timeout_s=args.timeout) if ver_jobs else None
            res = fp.result()
            try:
                ver_res = fv.result() if fv is not None else []
            except Exception as exc:  # noqa: BLE001 - a failed verification never costs the run's rows (recorded)
                ver_res = [(None, f"verification call failed: {type(exc).__name__}: {exc}"[:2000])]
        t_loops = time.time()
        rows, loops, pack_recs, failed_packs = [], [], [], []
        for p, (r, err) in zip(packs, res):
            if r is None:
                failed_packs.append({"loops": [AM.loop_id(j) for j in p], "error": err})
                continue
            rows += r["rows"]
            loops += r["loops"]
            pack_recs.append({**r["pack"], "loops": [AM.loop_id(j) for j in p]})
        planned = {AM.loop_id(j) for j in jobs}
        with_rows = {f"{r['system']}|{r['learner']}|{r['designer']}|s{r['loop_seed']}" for r in rows}
        violations = AM.draw_violations(rows, loops)
        verification = None
        if ver_jobs:
            ver_ids = {AM.loop_id(j) for j in ver_jobs}
            cap = max(c for j in ver_jobs for c in j["checkpoints"])
            packed_s = [r for r in rows if f"{r['system']}|{r['learner']}|{r['designer']}|s{r['loop_seed']}" in ver_ids
                        and int(r["budget"]) <= cap]
            unpacked_s = [row for (u_, _e) in ver_res if u_ for row in u_["rows"]]
            verification = {"loops": sorted(ver_ids), "budgets": sorted({int(r["budget"]) for r in unpacked_s}), "cls": ver_cls,
                            "unpacked_errors": [e for (_u, e) in ver_res if e], **compare_rows(packed_s, unpacked_s)}
        summary = {}
        if violations:
            summary = {"error": "REFUSED: draw-rule violations (TRUE-STATE fits whose training draws vary without their draw context, "
                                "or missing / inconsistent draws; draw_violations); no MDE computed"}
        elif rows:
            try:
                summary = run_summary(rows, n_sim=args.n_sim, n_boot=args.n_boot, cls=None if args.summary_local else args.summary_cls, be=be)
            except Exception as exc:  # noqa: BLE001 - the rows are written anyway (resummarize redoes the summary)
                summary = {"error": f"{type(exc).__name__}: {exc}"[:2000]}
        cost = be.cost_summary()
    t_end = time.time()
    rec = {"what": "pre-freeze MDE of the active-design success rule (PROTOCOL 5.17) on the dev tier with benchmark reference learners",
           "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tier": args.tier, "smoke": smoke, "readiness": ready,
           "systems": list(sids), "n_systems": len(sids), "n_compressible": len(comp), "learners": learners, "designers": designers, "loop_seeds": seeds,
           "budget": args.budget, "checkpoints": [c for c in CHECKPOINTS if c <= args.budget], "n_loops": len(jobs),
           "packing": {"cls": args.cls, "workers": args.workers, "threads": args.threads, "mem_budget_gb": args.mem_budget_gb,
                       "containers": len(packs), "cost_model": COST, "predicted_makespan_s": round(est, 1)},
           "run_id": run_id, "verification": verification, "draw_preflight": {"verdict": verdict, "systems": pre},
           "draw_context": draw_tally(rows), "draw_violations": violations,
           "n_failed_loops": len(planned - with_rows), "failed_loops": sorted(planned - with_rows), "failed_packs": failed_packs,
           "n_checkpoint_errors": sum(1 for r in rows if r.get("error")), "wall_s": round(t_end - t0, 1),
           "loops_wall_s": round(t_loops - t0, 1), "summary_wall_s": round(t_end - t_loops, 1), "modal_cost": cost,
           "code_sha256": CAL.code_hashes(), "summary": summary, "packs": pack_recs, "loops": loops, "rows": rows}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    if summary.get("per_learner") and not violations:
        write_md(rec, out.with_suffix(".md"))
    if violations:
        print(f"REFUSED: {len(violations)} draw-rule violations (no MDE computed; rows kept in {out.name}): {violations[:5]}", flush=True)
    if not failed_packs and rec["n_failed_loops"] == 0:
        drop_progress(run_id)
    what = "SMOKE run (not the MDE)" if smoke else "full MDE run"
    add_modal_row(f"{what}: {len(jobs)} loops on {len(sids)} {args.tier} systems packed as (loop, checkpoint) tasks, then the summary",
                  str(cost.get("app_id")), f"{len(packs)} x {args.cls} ({args.workers} x {args.threads} threads)",
                  f"~${cost.get('usd_approx_total')}", f"wall {rec['wall_s']:.0f} s; {rec['n_failed_loops']} failed loops, "
                  f"{rec['n_checkpoint_errors']} checkpoint errors; verification {(verification or {}).get('verdict')}; progress store "
                  f"{sorted({str(p_.get('progress')) for p_ in pack_recs})}; {out.name}")
    print(json.dumps({"loops": len(jobs), "failed_loops": rec["n_failed_loops"], "failed_packs": len(failed_packs),
                      "checkpoint_errors": rec["n_checkpoint_errors"], "wall_s": rec["wall_s"], "usd_approx": cost.get("usd_approx_total"),
                      "mde": {ln: m["mde"]["mde"] for ln, m in (summary.get("per_learner") or {}).items()}}, indent=1, default=str), flush=True)
    if violations:
        return 2
    return 0 if not failed_packs and rec["n_failed_loops"] == 0 else 1


def draw_tally(rows: list[dict]) -> dict:
    """TRUE-STATE fits of the run: how many, how many with draws required, with the draw context, without it because their training
    draws were constant (legitimate, CONSTANT_DRAWS), and the registrations without a draw (recorded with every run; module
    docstring, DRAWS)."""
    ts = [r for r in rows if r.get("learner") == "true_state" and not r.get("error")]
    return {"n_fits": len(ts), "n_draw_required": sum(1 for r in ts if r.get("draw_required")),
            "n_draw_context": sum(1 for r in ts if r.get("draw_context")),
            "n_constant_draws": sum(1 for r in ts if r.get("draw_context_reason") == AM.CONSTANT_DRAWS),
            "n_registered_without_draw": sum(int(r.get("n_registered_without_draw") or 0) for r in ts),
            "n_probe_encodes": sum(int(r.get("n_probe_encodes") or 0) for r in ts)}


def compare_rows(packed: list[dict], unpacked: list[dict]) -> dict:
    """Field-by-field equality (exact, NaN = NaN) of packed and unpacked checkpoint rows keyed by (system, learner, designer, seed,
    budget). Three outcomes are kept APART so an infrastructure failure is never reported as a row difference (review of P1, E15's
    load-dependent failure, 2026-09-27):
      diffs           value differences between two rows that BOTH completed (a genuine nondeterminism);
      infrastructure  rows where either side carries an "error" (a worker killed, e.g. out of memory under machine load, a broken pool,
                      crash retries exhausted, a failed evaluation): the two sides cannot be compared;
      missing         rows present on one side only (a failed loop on that side, or a different checkpoint set).
    rows_identical = no diffs among the completed rows; bit_identical = rows_identical AND nothing missing or failed (complete);
    verdict = "identical" | "value difference" | "infrastructure failure" | "missing rows" (a value difference takes precedence)."""
    def key(r):
        return (r["system"], r["learner"], r["designer"], int(r["loop_seed"]), int(r["budget"]))

    def same(a, b):
        if isinstance(a, float) and isinstance(b, float) and a != a and b != b:
            return True
        return a == b
    pk, uk = {key(r): r for r in packed}, {key(r): r for r in unpacked}
    diffs, infra, missing, n_eq = [], [], [], 0
    for k in sorted(set(pk) | set(uk)):
        a, b = pk.get(k), uk.get(k)
        if a is None or b is None:
            missing.append({"row": list(k), "missing": "packed" if a is None else "unpacked"})
            continue
        if a.get("error") or b.get("error"):
            infra.append({"row": list(k), "packed_error": a.get("error"), "unpacked_error": b.get("error")})
            continue
        bad = {f: [a.get(f), b.get(f)] for f in VERIFY_FIELDS if not same(a.get(f), b.get(f))}
        if bad:
            diffs.append({"row": list(k), "fields": bad})
        else:
            n_eq += 1
    rows_identical = not diffs and n_eq > 0
    verdict = ("value difference" if diffs else "infrastructure failure" if infra else "missing rows" if missing
               else "identical" if n_eq > 0 else "nothing compared")
    return {"n_rows": len(set(pk) | set(uk)), "n_identical": n_eq, "rows_identical": rows_identical,
            "bit_identical": rows_identical and not infra and not missing, "diffs": diffs, "infrastructure": infra, "missing": missing,
            "verdict": verdict}


def cmd_profile(args) -> int:
    if not args.systems:
        raise SystemExit("profile needs --systems (2-4 dev systems)")
    sids, info, _summaries, comp = _systems(args)
    packings = [tuple(int(x) for x in p.split("x")) for p in args.packings.split(",") if p]
    ts = sorted({t for _, t in packings})
    prof_jobs = {t: [loop_job(s, ln, "random", 0, 200, t, info[s], tag=f"_prof{t}") for s in sids
                     for ln in ("full_state", "true_state") if ln != "true_state" or s in comp] for t in ts}
    vs = sids[-1]
    ver = {t: [loop_job(vs, ln, "fixed", 1, args.verify_budget, t, info[vs], tag=f"_ver{t}") for ln in ("full_state", "true_state")
               if ln != "true_state" or vs in comp] for t in ts}
    unpacked_cls = {t: ("eval_s" if t <= 4 else "eval_l" if t <= 8 else args.cls) for t in ts}
    t0 = time.time()
    with _backend([args.cls, *unpacked_cls.values()]) as be:
        with ThreadPoolExecutor(max_workers=len(packings) + len(ts)) as tp:
            fp = {(w, t): tp.submit(run_packs, be, [prof_jobs[t] + ver[t]], cls=args.cls, workers=w, threads=t,
                                     mem_budget_gb=args.mem_budget_gb, timeout_s=args.timeout) for w, t in packings}
            fu = {t: tp.submit(run_unpacked, be, ver[t], cls=unpacked_cls[t], threads=t, timeout_s=args.timeout) for t in ts}
            packed = {k: f.result()[0] for k, f in fp.items()}
            unpacked = {t: f.result() for t, f in fu.items()}
        cost = be.cost_summary()
    rep = {"what": "E11 profile: packings of the MDE loops and the packed / unpacked bit-identity check",
           "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "systems": sids, "verify_system": vs,
           "verify_budget": args.verify_budget, "cls": args.cls, "unpacked_cls": unpacked_cls, "mem_budget_gb": args.mem_budget_gb,
           "wall_s": round(time.time() - t0, 1), "modal_cost": cost, "packings": {}}
    for (w, t), (r, err) in packed.items():
        name = f"{w}x{t}"
        if r is None:
            rep["packings"][name] = {"error": err}
            continue
        ver_ids = {AM.loop_id(j) for j in ver[t]}
        prof_rows = [r_ for r_ in r["rows"] if f"{r_['system']}|{r_['learner']}|{r_['designer']}|s{r_['loop_seed']}" not in ver_ids]
        ver_rows = [r_ for r_ in r["rows"] if f"{r_['system']}|{r_['learner']}|{r_['designer']}|s{r_['loop_seed']}" in ver_ids]
        un_rows = [row for (u, _e) in unpacked[t] if u for row in u["rows"]]
        rep["packings"][name] = {"pack": r["pack"], "loops": r["loops"],
                                 "tasks": [{k: x.get(k) for k in ("system", "learner", "designer", "loop_seed", "budget", "n_records",
                                                                   "fit_wall_s", "fit_cpu_s", "eval_ctx_s", "eval_wall_s", "task_wall_s",
                                                                   "peak_gb", "EE", "error")} for x in prof_rows + ver_rows],
                                 "verification": compare_rows(ver_rows, un_rows),
                                 "unpacked_errors": [e for (_u, e) in unpacked[t] if e]}
    out = args.out or (ROOT / "research" / "phase4" / "ACTIVE_MDE_PROFILE.json")
    out.write_text(json.dumps(rep, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    add_modal_row(f"packing profile ({args.packings}) on {len(sids)} dev systems + packed / unpacked bit-identity check",
                  str(cost.get("app_id")), f"{len(packings)} x {args.cls}, unpacked on {sorted(set(unpacked_cls.values()))}",
                  f"~${cost.get('usd_approx_total')}", f"wall {rep['wall_s']:.0f} s; see {out.name}")
    for name, p in rep["packings"].items():
        if "error" in p:
            print(name, "ERROR", p["error"][:500])
            continue
        v = p["verification"]
        print(f"{name}: pack wall {p['pack']['wall_s']} s (phase 1 {p['pack']['phase1_s']} s), bit-identical {v['bit_identical']} "
              f"({v['n_identical']}/{v['n_rows']}; {v.get('verdict')}), max task peak "
              f"{max((x['peak_gb'] or 0) for x in p['tasks']):.1f} GB", flush=True)
    print(json.dumps({"usd_approx": cost.get("usd_approx_total"), "wall_s": rep["wall_s"]}), flush=True)
    return 0


def _lsq(x: list[float], y: list[float]) -> tuple[float, float]:
    """(intercept >= 0, slope >= 0) of the least-squares line y = a + b x."""
    import numpy as np
    X = np.column_stack([np.ones(len(x)), np.asarray(x, float)])
    a, b = np.linalg.lstsq(X, np.asarray(y, float), rcond=None)[0]
    if b < 0:
        a, b = float(np.mean(y)), 0.0
    if a < 0:
        a, b = 0.0, float(np.sum(np.asarray(x) * np.asarray(y)) / max(1e-12, np.sum(np.asarray(x) ** 2)))
    return float(a), float(b)


def analyze_profile(rep: dict, info: dict, comp: set, containers: int, safety: float = 1.2) -> dict:
    """Per packing of a profile record: the fitted cost model (task seconds and peak GiB per learner), the predicted phase-2 makespan
    and container-seconds of the full run with it, and the per-task extra work the fresh-subprocess alternative (P1's
    Backend.call_packed: each (loop, checkpoint) job alone) would add: its loop's design + simulation up to the checkpoint, the
    evaluation context and the process start."""
    out = {}
    for name, p in rep["packings"].items():
        if "error" in p:
            out[name] = {"error": p["error"][:300]}
            continue
        w, t = (int(v) for v in name.split("x"))
        tasks = [x for x in p["tasks"] if not x.get("error") and x.get("task_wall_s")]
        cost = {}
        for ln in ("full_state", "true_state"):
            tl = [x for x in tasks if x["learner"] == ln and x["budget"] in CHECKPOINTS and x["loop_seed"] == 0]
            if not tl:
                continue
            nobs = [len(info[x["system"]]["observed"]) for x in tl]
            s0, s1 = _lsq(nobs, [x["task_wall_s"] for x in tl])
            size = [x["n_records"] * (round(info[x["system"]]["t_end_default"] / info[x["system"]]["dt"]) + 1)
                    * len(info[x["system"]]["observed"]) * 8 / 2 ** 30 for x in tl]
            peaks = [x["peak_gb"] for x in tl if x.get("peak_gb")]
            g0, g1 = _lsq(size[: len(peaks)], peaks) if peaks else (COST[ln]["g0"], COST[ln]["g1"])
            worst = max((pk / max(1e-9, g0 + g1 * sz) for pk, sz in zip(peaks, size, strict=False)), default=1.0)
            k = max(1.0, worst) * safety
            cost[ln] = {"s0": round(s0, 1), "s1": round(s1, 3), "g0": round(g0 * k, 3), "g1": round(g1 * k, 3),
                        "n_tasks": len(tl), "max_peak_gb": max(peaks) if peaks else None}
        saved = {k_: dict(v) for k_, v in COST.items()}
        try:
            for ln, c in cost.items():
                COST[ln].update({k_: c[k_] for k_ in ("s0", "s1", "g0", "g1")})
            jobs = [loop_job(s, ln, d, sd, 200, t, info[s]) for s in sorted(info) for ln in ("full_state", "true_state")
                    if ln != "true_state" or s in comp for d in ("random", "fixed") for sd in (0, 1, 2)]
            packs = plan_packs(jobs, containers, w)
            mk = predicted_makespan(packs, w)
            busy = sum(pred_task_s(j) * len(j["checkpoints"]) for j in jobs)
        finally:
            for k_, v in saved.items():
                COST[k_].clear()
                COST[k_].update(v)
        loops = {lp["loop_id"]: lp for lp in p["loops"] if "error" not in lp}
        ph1 = [lp["wall_s"] for lid, lp in loops.items() if lid.endswith("|s0")]
        ctx = [x["eval_ctx_s"] for x in tasks if x.get("eval_ctx_s")]
        out[name] = {"workers": w, "threads": t, "pack_wall_s": p["pack"]["wall_s"], "phase1_s": p["pack"]["phase1_s"],
                     "cost_model": cost, "predicted_full_phase2_makespan_s": round(mk, 1),
                     "predicted_full_wall_s": round(mk + p["pack"]["phase1_s"], 1),
                     "predicted_task_core_hours": round(busy * t / 3600, 1), "containers": len(packs),
                     "verification_bit_identical": p["verification"]["bit_identical"],
                     "fresh_subprocess_extra_per_task_s": {"phase1_loop_wall_s_median": sorted(ph1)[len(ph1) // 2] if ph1 else None,
                                                           "eval_context_load_s_max": max(ctx) if ctx else None}}
    ok = {k: v for k, v in out.items() if "error" not in v and v["verification_bit_identical"]}
    best = min(ok, key=lambda k: ok[k]["predicted_full_wall_s"]) if ok else None
    return {"packings": out, "recommended": best}


def cmd_analyze(args) -> int:
    rep = json.loads((args.out or (ROOT / "research" / "phase4" / "ACTIVE_MDE_PROFILE.json")).read_text(encoding="utf-8"))
    args.systems = ""
    _sids, info, _summaries, comp = _systems(args)
    res = analyze_profile(rep, info, comp, args.containers)
    print(json.dumps(res, indent=1, default=str))
    return 0


def cmd_resummarize(args) -> int:
    out = args.out or OUT
    rec = json.loads(out.read_text(encoding="utf-8"))
    t0 = time.time()
    if args.summary_local:
        rec["summary"] = run_summary(rec["rows"], n_sim=args.n_sim, n_boot=args.n_boot, cls=None)
    else:
        with _backend([args.summary_cls]) as be:
            rec["summary"] = run_summary(rec["rows"], n_sim=args.n_sim, n_boot=args.n_boot, cls=args.summary_cls, be=be)
    rec["summary_wall_s"] = round(time.time() - t0, 1)
    out.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    write_md(rec, out.with_suffix(".md"))
    print(json.dumps({ln: m["mde"]["mde"] for ln, m in rec["summary"]["per_learner"].items()}, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze-profile")
    a.add_argument("--out", type=Path, default=None, help="the profile record (default research/phase4/ACTIVE_MDE_PROFILE.json)")
    a.add_argument("--containers", type=int, default=DEFAULTS["containers"])
    f = sub.add_parser("preflight")
    f.add_argument("--systems", default="")
    f.add_argument("--tier", default=TIER)
    f.add_argument("--allow-no-draw", action="store_true")
    for name in ("run", "profile", "resummarize"):
        p = sub.add_parser(name)
        p.add_argument("--out", type=Path, default=None)
        p.add_argument("--n-sim", type=int, default=1000)
        p.add_argument("--n-boot", type=int, default=1000)
        p.add_argument("--summary-cls", default=DEFAULTS["summary_cls"])
        p.add_argument("--summary-local", action="store_true")
        if name == "resummarize":
            continue
        p.add_argument("--systems", default="")
        p.add_argument("--cls", default=DEFAULTS["cls"])
        p.add_argument("--mem-budget-gb", type=float, default=DEFAULTS["mem_budget_gb"])
        p.add_argument("--timeout", type=float, default=4 * 3600)
        if name == "run":
            p.add_argument("--workers", type=int, default=DEFAULTS["workers"])
            p.add_argument("--threads", type=int, default=DEFAULTS["threads"])
            p.add_argument("--containers", type=int, default=DEFAULTS["containers"])
            p.add_argument("--learners", default="full_state,true_state")
            p.add_argument("--designers", default="random,fixed")
            p.add_argument("--loop-seeds", default="0,1,2")
            p.add_argument("--budget", type=int, default=200)
            p.add_argument("--force", action="store_true", help="skip the readiness check (smoke runs on the current tier)")
            p.add_argument("--run-id", default="", help="resume the run with this id (its progress store keeps the finished tasks)")
            p.add_argument("--verify-sample", type=int, default=1, help="1: run the unpacked verification loops beside the packs")
            p.add_argument("--verify-budget", type=int, default=10, help="budget of the unpacked verification loops")
            p.add_argument("--tier", default=TIER, help="smoke runs only (with --force and --out): another staged tier, e.g. toyC")
            p.add_argument("--allow-no-draw", action="store_true",
                           help="run although the tier's truth carries no effective draws (smoke tiers; TRUE-STATE is then z alone)")
        else:
            p.add_argument("--packings", default="16x2,8x4,4x8", help="workers x threads per container, comma separated")
            p.add_argument("--verify-budget", type=int, default=25)
    m = sub.add_parser("merge")
    m.add_argument("batches", nargs="+", type=Path, help="run records of the batches of a STREAMED dev tier (run --systems ... --out ...)")
    m.add_argument("--out", type=Path, default=None)
    m.add_argument("--n-sim", type=int, default=1000)
    m.add_argument("--n-boot", type=int, default=1000)
    m.add_argument("--summary-cls", default=DEFAULTS["summary_cls"])
    m.add_argument("--summary-local", action="store_true")
    args = ap.parse_args(argv)
    return {"run": cmd_run, "profile": cmd_profile, "resummarize": cmd_resummarize, "analyze-profile": cmd_analyze,
            "preflight": cmd_preflight, "merge": cmd_merge}[args.cmd](args)


def cmd_merge(args) -> int:
    """The official MDE record from the run records of a STREAMED dev tier's batches (LOCAL_EXECUTION_PLAN.md section 7): each batch
    ran the full design (learners, designers, loop seeds, budget) on its systems; together they must cover every system of the tier
    exactly once (compressible ones for TRUE-STATE) with the SAME design, else the merge refuses. Rows, loops, packs, preflights and
    verification records are concatenated; the summary is then computed once over all rows, as a single run would."""
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in args.batches]
    keys = ("learners", "designers", "loop_seeds", "budget", "checkpoints")
    design = {k: recs[0].get(k) for k in keys}
    for p, r in zip(args.batches, recs):
        if {k: r.get(k) for k in keys} != design:
            raise SystemExit(f"{p}: another design than {args.batches[0]}")
    sys_sets = [set(r.get("systems") or []) for r in recs]
    allsys = set().union(*sys_sets)
    if sum(len(s) for s in sys_sets) != len(allsys):
        raise SystemExit("a system appears in more than one batch")
    base = SU.tier_dirs(TIER, SU.SUITES)["base"]
    tier_ids = set(json.loads((base / "internal_records.json").read_text(encoding="utf-8")))
    if allsys != tier_ids:
        raise SystemExit(f"the batches cover {len(allsys & tier_ids)} of the tier's {len(tier_ids)} systems; missing {sorted(tier_ids - allsys)[:5]}")
    rec = dict(recs[0])
    for k in ("rows", "loops", "packs", "failed_packs"):
        rec[k] = [x for r in recs for x in (r.get(k) or [])]
    rec["systems"] = sorted(allsys)
    rec["n_systems"] = len(allsys)
    rec["n_compressible"] = sum(int(r.get("n_compressible") or 0) for r in recs)
    rec["n_loops"] = sum(int(r.get("n_loops") or 0) for r in recs)
    rec["n_failed_loops"] = sum(int(r.get("n_failed_loops") or 0) for r in recs)
    rec["n_checkpoint_errors"] = sum(int(r.get("n_checkpoint_errors") or 0) for r in recs)
    rec["draw_preflight"] = {"batches": [r.get("draw_preflight") for r in recs]}
    rec["draw_context"] = draw_tally(rec["rows"])
    rec["draw_violations"] = [v for r in recs for v in (r.get("draw_violations") or [])]
    rec["failed_loops"] = sorted(x for r in recs for x in (r.get("failed_loops") or []))
    rec["smoke"] = False
    rec["streamed_batches"] = len(recs)
    rec["readiness"] = {"batches": [r.get("readiness") for r in recs]}
    rec["verification"] = {"batches": [r.get("verification") for r in recs]}
    rec["merged_from"] = [str(p) for p in args.batches]
    rec["wall_s"] = sum(float(r.get("wall_s") or 0) for r in recs)
    t0 = time.time()
    if args.summary_local:
        rec["summary"] = run_summary(rec["rows"], n_sim=args.n_sim, n_boot=args.n_boot, cls=None)
    else:
        with _backend([args.summary_cls]) as be:
            rec["summary"] = run_summary(rec["rows"], n_sim=args.n_sim, n_boot=args.n_boot, cls=args.summary_cls, be=be)
    rec["summary_wall_s"] = round(time.time() - t0, 1)
    out = args.out or OUT
    out.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    write_md(rec, out.with_suffix(".md"))
    print(json.dumps({ln: m["mde"]["mde"] for ln, m in rec["summary"]["per_learner"].items()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
