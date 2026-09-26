"""The experiment loop for active experiment design (research/phase4/INTERFACES.md section 7; benchmarks/causal_state_v1/PROTOCOL.md
section 5.17; goal5 sections 24-29, 60, 73).

    result = run_loop(learner, designer, system_id, sysrec, d0_records, sim, budget=200, checkpoints=CHECKPOINTS, seed=0, out_dir=...)

For one system: start from the benchmark's passive set D0 and fit the learner; then repeat {the designer proposes up to `batch`
experiments -> every proposal is canonicalised and checked against the system's PUBLIC policy (`simservice.check_public`: only
families_train on public targets / edges within the development ranges, public seeds) -> the counterfactual twin of every
intervention is added -> the simulator runs them (content-addressed cache) -> the learner updates} until the budget is spent. The
model is checkpointed after 10, 25, 50, 100 and 200 experiments (real full networks: 10, 25, 50, 100).

Budget unit = one EXPERIMENT = one intervention trajectory and its twin (2 simulator trajectories). A passive proposal costs half an
experiment, so the `passive` designer spends the same simulator trajectories on passive data. Proposals the policy refuses are
dropped and counted (never replaced by another designer's experiments); after `max_bad_rounds` consecutive rounds without a valid
proposal the loop stops early and records why (later checkpoints are missing; `curves` carries the last model's quality forward).

Costs per checkpoint (goal5 section 28): experiments, simulator trajectories, simulator calls (computed, not cached), simulated
seconds, unique targets, magnitude budget per kind (`brainir_causal.accounting`), learner CPU and wall seconds, designer CPU seconds,
and the model's self-reported training cost (GPU seconds, FLOPs).

The simulator `sim` is any object with `run(protocols) -> [{"ok", "error", "t", "x", "u", "y", "key", "cached", "family"}]`: the
room's `SimClient` (the loop then runs inside the method sandbox and the simulation service enforces the policy and budget a second
time), or `DirectSim` (orchestrator side, e.g. tests).

`active_success(rows, own=...)` applies the pre-registered success rule of PROTOCOL 5.17 to evaluated checkpoints.
"""

from __future__ import annotations

import json
import math
import pickle
import time
from pathlib import Path

import numpy as np

from . import protocol as P
from .accounting import Ledger, experiment_cost
from .data import Trajectory

CHECKPOINTS = (10, 25, 50, 100, 200)
CHECKPOINTS_FULL = (10, 25, 50, 100)
DEFAULT_BATCH = 5
LOOP_SEEDS = (0, 1, 2)
PASSIVE_COST = 0.5
MISSING_EE = 1.0          # a checkpoint without a model is scored as predicting no effect (never better than abstaining)


# ================================================================================================================ simulators
class DirectSim:
    """Orchestrator-side simulator with the SimClient interface (tests; loops run by the orchestrator itself). Restart keys may be
    dataset keys of records it produced or was given (`known`)."""

    def __init__(self, ctx, known: list | None = None):
        self.ctx = ctx
        self.keymap: dict[str, str] = {}
        for r in known or []:
            if getattr(r, "meta", {}).get("store_key"):
                self.keymap[r.key] = r.meta["store_key"]

    def run(self, protocols: list[dict]) -> list[dict]:
        out = []
        for p in protocols:
            try:
                q = P.validate(p)
                if q["r0"]["kind"] == "restart":
                    q["r0"]["key"] = self.keymap.get(q["r0"]["key"], q["r0"]["key"])
                had = self.ctx.store.has(self.ctx.store_key(q))
                r = self.ctx.run(q)
                self.keymap[r["key"]] = r["store_key"]
                out.append({"ok": True, "error": None, "t": r["t"], "x": r["x"], "u": r["u"], "y": r["y"], "key": r["key"], "cached": had,
                            "store_key": r["store_key"]})
            except Exception as e:  # noqa: BLE001 - reported per protocol
                out.append({"ok": False, "error": f"{type(e).__name__}: {e}", "key": None, "cached": None})
        return out


# ================================================================================================================ the loop
def _record(res: dict, q: dict, sid: str, sysrec: dict, *, provenance: str, meta: dict) -> Trajectory:
    from .families import family_of
    try:
        fam = res.get("family") or family_of(q, sysrec)
    except Exception:  # noqa: BLE001
        fam = "other"
    m = dict(meta)
    if res.get("store_key"):
        m["store_key"] = res["store_key"]
    return Trajectory(key=res["key"], system_id=sid, split="train", family=fam, protocol=q, t=np.asarray(res["t"]),
                      x=np.asarray(res["x"]), u=np.asarray(res["u"]), y=np.asarray(res["y"]), meta=m, provenance=provenance)


def _model_cost(model) -> dict:
    try:
        tc = (model.info() or {}).get("train_cost") or {}
        return {k: tc.get(k) for k in ("cpu_s", "gpu_s", "flops", "sim_calls", "experiments") if k in tc}
    except Exception:  # noqa: BLE001
        return {}


def _save_model(model, path: Path) -> str | None:
    try:
        if hasattr(model, "save"):
            model.save(path)
        else:
            with open(path, "wb") as fh:
                pickle.dump(model, fh, protocol=pickle.HIGHEST_PROTOCOL)
        return path.name
    except Exception as e:  # noqa: BLE001 - an unpicklable model is recorded, not hidden
        return f"unsaved: {type(e).__name__}: {e}"


def run_loop(learner, designer, system_id: str, sysrec: dict, d0: list, sim, *, budget: int, checkpoints=CHECKPOINTS,
             batch: int = DEFAULT_BATCH, seed: int = 0, out_dir: Path | str | None = None, config: dict | None = None, policy=None,
             max_bad_rounds: int = 3, designer_name: str | None = None) -> dict:
    """Run one experiment loop (see the module docstring). Returns the loop record; checkpoint models are saved under out_dir (or
    kept in the record's 'models' when out_dir is None)."""
    if policy is None:
        from .simservice import check_public as policy
    cps = sorted(int(c) for c in checkpoints if int(c) <= int(budget))
    if not cps or cps[-1] != int(budget):
        cps.append(int(budget))
    dname = designer_name or getattr(designer, "name", type(designer).__name__)
    prov = f"designer:{dname}"
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 7_919]))
    out = Path(out_dir) if out_dir is not None else None
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
    data = list(d0)
    ledger = Ledger()
    rec = {"system_id": system_id, "designer": dname, "seed": int(seed), "budget": int(budget), "batch": int(batch), "checkpoints": [],
           "refused": 0, "refusals": [], "sim_errors": 0, "stopped_early": None, "rounds": 0}
    models: dict[int, object] = {}
    cpu_learn = wall_learn = cpu_design = 0.0
    c0, w0 = time.process_time(), time.time()
    model = learner.fit(data, systems={system_id: sysrec}, config=dict(config or {}), seed=int(seed))
    cpu_learn += time.process_time() - c0
    wall_learn += time.time() - w0
    spent = 0.0
    bad = 0
    ci = 0
    while spent < budget - 1e-9 and ci < len(cps):
        need = cps[ci] - spent
        n = max(1, min(int(batch), math.ceil(need)))
        c0 = time.process_time()
        try:
            props = list(designer.propose(system_id, sysrec, model, data, n, math.ceil(budget - spent), rng) or [])
        except Exception as e:  # noqa: BLE001 - a crashing designer stops its loop (recorded)
            rec["stopped_early"] = f"designer error: {type(e).__name__}: {e}"
            break
        cpu_design += time.process_time() - c0
        rec["rounds"] += 1
        known = {r.key for r in data}
        batch_q, costs = [], []
        for p in props:
            try:
                q = P.validate(p)
            except P.ProtocolError as e:
                rec["refused"] += 1
                rec["refusals"].append(str(e)[:200])
                continue
            why = policy(q, sysrec, allowed_restart_keys=known)
            if why:
                rec["refused"] += 1
                rec["refusals"].append(why[:200])
                continue
            c = 1.0 if q["events"] else PASSIVE_COST
            if spent + sum(costs) + c > cps[ci] + 1e-9:
                continue
            batch_q.append(q)
            costs.append(c)
        rec["refusals"] = rec["refusals"][-50:]
        if not batch_q:
            bad += 1
            if bad >= max_bad_rounds:
                rec["stopped_early"] = f"no valid proposal in {bad} consecutive rounds"
                break
            continue
        bad = 0
        sims, owners = [], []
        for j, q in enumerate(batch_q):
            sims.append(q)
            owners.append((j, "item"))
            if q["events"]:
                sims.append(P.counterfactual(q))
                owners.append((j, "twin"))
        res = sim.run(sims)
        new: list[Trajectory] = []
        item_keys: dict[int, str | None] = {}
        for (j, what), q, r in zip(owners, sims, res):
            if not r.get("ok"):
                rec["sim_errors"] += 1
                if what == "item":
                    item_keys[j] = None
                continue
            ledger.add(system_id, experiment_cost(q, sysrec), computed=not bool(r.get("cached")))
            meta = {"designer": dname, "round": rec["round"] if "round" in rec else rec["rounds"]}
            if what == "item":
                item_keys[j] = r["key"]
            else:
                if item_keys.get(j) is None:
                    continue
                meta["twin_of"] = item_keys[j]
            new.append(_record(r, q, system_id, sysrec, provenance=prov, meta=meta))
        spent += sum(c for (j, what), c in zip([(j, "item") for j in range(len(batch_q))], costs) if item_keys.get(j) is not None)
        data += new
        if new:
            c0, w0 = time.process_time(), time.time()
            model = learner.update(model, new, data_all=data, systems={system_id: sysrec}, config=dict(config or {}), seed=int(seed))
            cpu_learn += time.process_time() - c0
            wall_learn += time.time() - w0
        while ci < len(cps) and spent >= cps[ci] - 1e-9:
            b = cps[ci]
            entry = {"budget": b, "spent": spent, "n_records": len(data), "ledger": ledger.to_dict(), "learner_cpu_s": round(cpu_learn, 3),
                     "learner_wall_s": round(wall_learn, 3), "designer_cpu_s": round(cpu_design, 3), "model_cost": _model_cost(model)}
            if out is not None:
                entry["model"] = _save_model(model, out / f"ckpt_{b:04d}.pkl")
            else:
                models[b] = model
            rec["checkpoints"].append(entry)
            ci += 1
    rec["spent"] = spent
    rec["ledger"] = ledger.to_dict()
    rec["learner_cpu_s"], rec["designer_cpu_s"] = round(cpu_learn, 3), round(cpu_design, 3)
    if out is not None:
        (out / "loop_record.json").write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
        keys = [{"key": r.key, "provenance": r.provenance, "family": r.family, "twin_of": r.meta.get("twin_of")} for r in data[len(d0):]]
        (out / "experiments.jsonl").write_text("".join(json.dumps(k) + "\n" for k in keys), encoding="utf-8", newline="\n")
    else:
        rec["models"] = models
        rec["data"] = data
    return rec


# ================================================================================================================ curves / success
def _by(rows: list[dict], metric: str) -> dict:
    """{(system, designer): {budget: [values over loop seeds]}} with missing checkpoints carried forward from the seed's previous
    checkpoint (MISSING_EE when there is none)."""
    seeds: dict[tuple, dict[int, float]] = {}
    budgets = sorted({int(r["budget"]) for r in rows})
    for r in rows:
        v = r.get(metric)
        seeds.setdefault((r["system"], r["designer"], r.get("loop_seed", 0)), {})[int(r["budget"])] = (
            float(v) if v is not None and np.isfinite(v) else np.nan)
    out: dict[tuple, dict[int, list]] = {}
    for (s, d, _sd), vals in seeds.items():
        last = np.nan
        for b in budgets:
            v = vals.get(b, np.nan)
            if not np.isfinite(v):
                v = last if np.isfinite(last) else MISSING_EE
            last = v
            out.setdefault((s, d), {}).setdefault(b, []).append(v)
    return out


def curves(rows: list[dict], metric: str = "EE", strata: dict | None = None, n_boot: int = 2000, seed: int = 0) -> dict:
    """Per designer and budget: the mean over systems of the per-system mean over loop seeds, with a stratified system-bootstrap CI,
    plus the mean simulator costs (for the quality vs experiments vs simulator-cost plots of goal5 section 25)."""
    from .stats import stratified_system_boot
    by = _by(rows, metric)
    designers = sorted({d for _, d in by})
    budgets = sorted({b for v in by.values() for b in v})
    out: dict[str, dict] = {}
    for d in designers:
        out[d] = {}
        for b in budgets:
            vals = {s: float(np.mean(v[b])) for (s, dd), v in by.items() if dd == d and b in v}
            if not vals:
                continue
            est = stratified_system_boot(vals, strata, np.mean, n_boot, seed)
            cost = [r for r in rows if r["designer"] == d and int(r["budget"]) == b]
            out[d][b] = {"mean": est.point, "ci95": est.ci95, "median": float(np.median(list(vals.values()))), "n_systems": len(vals),
                         "sim_calls": float(np.mean([r.get("sim_calls", np.nan) for r in cost])) if cost else None,
                         "simulated_s": float(np.mean([r.get("simulated_s", np.nan) for r in cost])) if cost else None,
                         "learner_cpu_s": float(np.mean([r.get("learner_cpu_s", np.nan) for r in cost])) if cost else None}
    return out


def _budget_to_reach(curve: dict[int, float], target: float, cap: float) -> float:
    """The (log-linearly interpolated) budget at which a curve first reaches <= target; `cap` when it never does."""
    bs = sorted(curve)
    for i, b in enumerate(bs):
        if curve[b] <= target:
            if i == 0:
                return float(b)
            b0, v0, v1 = bs[i - 1], curve[bs[i - 1]], curve[b]
            if v0 == v1:
                return float(b)
            f = (v0 - target) / (v0 - v1)
            return float(math.exp(math.log(b0) + f * (math.log(b) - math.log(b0))))
    return float(cap)


def active_success(rows: list[dict], *, own: str, comparators: tuple[str, ...] = ("random", "fixed"), metric: str = "EE",
                   ref_designer: str = "random", ref_budget: int = 100, strata: dict | None = None, n_boot: int = 2000,
                   seed: int = 0) -> dict:
    """PROTOCOL 5.17. rows: evaluated checkpoints {"system", "designer", "loop_seed", "budget", metric, ...} (lower = better).
    (i) at >= 2 budgets the own designer's EE is below BOTH comparators' (paired stratified system-bootstrap CI of the difference
        below 0) and at no budget significantly above either;
    (ii) the budget the own designer needs to reach the EE the reference designer reaches at `ref_budget` is significantly smaller:
         the ratio sum_s b_own(s) / sum_s ref_budget has an upper CI < 1 (systems resampled within strata; a curve that never
         reaches the target is charged twice the largest budget).
    SUCCESS = (i) or (ii)."""
    from .stats import paired_system_boot, stratified_system_boot
    by = _by(rows, metric)
    budgets = sorted({b for v in by.values() for b in v})
    systems = sorted({s for s, _ in by})
    mean = {(s, d): {b: float(np.mean(v)) for b, v in vals.items()} for (s, d), vals in by.items()}
    per_budget = {}
    n_better = 0
    any_worse = False
    for b in budgets:
        row = {}
        better_all = True
        for c in comparators:
            a = {s: mean[(s, own)][b] for s in systems if (s, own) in mean and b in mean[(s, own)] and (s, c) in mean}
            bb = {s: mean[(s, c)][b] for s in a if b in mean[(s, c)]}
            est = paired_system_boot(a, bb, strata, n_boot, seed)
            better = bool(np.isfinite(est.ci95[1]) and est.ci95[1] < 0)
            worse = bool(np.isfinite(est.ci95[0]) and est.ci95[0] > 0)
            row[c] = {"diff": est.point, "ci95": est.ci95, "n_systems": est.n_units, "better": better, "worse": worse}
            better_all &= better
            any_worse |= worse
        row["better_than_all"] = better_all
        n_better += int(better_all)
        per_budget[b] = row
    success_i = n_better >= 2 and not any_worse
    ratio = {}
    cap = 2.0 * max(budgets) if budgets else float("nan")
    for s in systems:
        if (s, own) not in mean or (s, ref_designer) not in mean or ref_budget not in mean[(s, ref_designer)]:
            continue
        target = mean[(s, ref_designer)][ref_budget]
        ratio[s] = _budget_to_reach(mean[(s, own)], target, cap) / float(ref_budget)
    est = stratified_system_boot(ratio, strata, np.mean, n_boot, seed) if ratio else None
    success_ii = bool(est is not None and np.isfinite(est.ci95[1]) and est.ci95[1] < 1.0)
    return {"own": own, "comparators": list(comparators), "metric": metric, "per_budget": per_budget, "n_budgets_better": n_better,
            "any_budget_worse": any_worse, "success_fixed_budget": success_i,
            "budget_ratio": (None if est is None else {"mean_ratio": est.point, "ci95": est.ci95, "n_systems": est.n_units,
                                                       "ref_designer": ref_designer, "ref_budget": ref_budget}),
            "success_fewer_experiments": success_ii, "success": bool(success_i or success_ii)}
