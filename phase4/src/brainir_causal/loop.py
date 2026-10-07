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
proposal the loop stops early and records why.

Costs per checkpoint (goal5 section 28): experiments, simulator trajectories, simulator calls (computed, not cached), simulated
seconds, unique targets (the `accounting.Ledger`), the MAGNITUDE BUDGET per event kind in its own unit (`magnitude_budget`: kick
magnitudes and current doses SEPARATELY, never summed across kinds; review H, minor 3), learner CPU and wall seconds, designer CPU
seconds, and the model's self-reported training cost (GPU seconds, FLOPs). The experiments file (experiments.jsonl) lists every
executed trajectory with its protocol, so `designers.load_profile` can build the magnitude-matched random control of 5.17.

The simulator `sim` is any object with `run(protocols) -> [{"ok", "error", "t", "x", "u", "y", "key", "cached", "family"}]`: the
room's `SimClient` (the loop then runs inside the method sandbox and the simulation service enforces the policy and budget a second
time), or `DirectSim` (orchestrator side, e.g. tests).

EVALUATED CHECKPOINTS (rows {"system", "designer", "loop_seed", "budget", "EE", ...}; EE = the class-balanced EE of the checkpoint's
model at the primary horizon on the verdict items; lower is better) are analysed by:
- `curves`: quality against experiments and simulator cost per designer (PROTOCOL 5.17; goal5 section 25);
- `budget_ratio`: the budget-to-reach comparison of 5.17 (ii) (review E, M4);
- `active_success`: the pre-registered success rule of 5.17 (each of its two rules one-sided at alpha = 0.025, P4-D20);
- `mde_by_simulation`: the minimum detectable effect of that rule, by simulation from observed curves (dev suite, before the freeze).
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
#: a checkpoint whose evaluation failed (or a loop that produced no checkpoint) is charged the worst admissible class-balanced EE
MISSING_EE = 10.0
ALPHA = 0.05
#: PROTOCOL 5.17 (P4-D20): each of rules (i) and (ii) is tested ONE-SIDED at alpha = 0.025 (Bonferroni over the two rules), so the
#: false-positive rate of "(i) or (ii)" stays at or below 5 %
RULE_ALPHA = 0.025
REF_BUDGET = 100
MAGNITUDE_KEYS = ("kick_magnitude", "current_dose", "silence_unit_s", "edge_scale_depth_s", "param_change_s")


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


# ================================================================================================================ magnitude budget
def magnitude_budget(protocols: list[dict]) -> dict:
    """The intervention magnitude spent by a list of protocols, per event kind in its own unit (never summed across kinds; review H,
    minor 3): kick_magnitude = sum of |delta| over kicked units (state units; independent of dt); current_dose = sum over targets of
    |I| x duration for currents (until t_end when persistent) and |I_j| x seg for current sequences; silence_unit_s = silenced units
    x duration; edge_scale_depth_s = scaled edges x |1 - factor| x duration; param_change_s = sum over targets of (|gain - 1| +
    |tau - 1| + |threshold|) x duration. Also the counts of intervention protocols and events."""
    out = dict.fromkeys(MAGNITUDE_KEYS, 0.0)
    n_prot = n_ev = 0
    for p in protocols:
        q = P.validate(p)
        if not q["events"]:
            continue
        n_prot += 1
        t_end = q["t_end"]
        for e in q["events"]:
            n_ev += 1
            k = e["kind"]
            if k == "kick":
                out["kick_magnitude"] += sum(abs(float(v)) for v in e["delta"].values())
            elif k == "current_seq":
                out["current_dose"] += sum(abs(float(v)) for lst in e["targets"].values() for v in lst) * float(e["seg"])
            elif k in ("current", "silence", "edge_scale", "param"):
                dur = (t_end if e["t1"] is None else e["t1"]) - e["t0"]
                if k == "current":
                    out["current_dose"] += sum(abs(float(v)) for v in e["targets"].values()) * dur
                elif k == "silence":
                    out["silence_unit_s"] += len(e["targets"]) * dur
                elif k == "edge_scale":
                    out["edge_scale_depth_s"] += len(e["edges"]) * abs(1.0 - float(e["factor"])) * dur
                else:
                    out["param_change_s"] += sum(abs(float(v.get("gain", 1.0)) - 1.0) + abs(float(v.get("tau", 1.0)) - 1.0)
                                                 + abs(float(v.get("threshold", 0.0))) for v in e["targets"].values()) * dur
    return {**{k: float(v) for k, v in out.items()}, "n_intervention_protocols": n_prot, "n_events": n_ev}


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
    executed: list[dict] = []              # the intervention (and passive-design) protocols the designer spent budget on
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
        for (j, what), q, r in zip(owners, sims, res, strict=True):
            if not r.get("ok"):
                rec["sim_errors"] += 1
                if what == "item":
                    item_keys[j] = None
                continue
            ledger.add(system_id, experiment_cost(q, sysrec), computed=not bool(r.get("cached")))
            meta = {"designer": dname, "round": rec["rounds"]}
            if what == "item":
                item_keys[j] = r["key"]
                executed.append(q)
            else:
                if item_keys.get(j) is None:
                    continue
                meta["twin_of"] = item_keys[j]
            new.append(_record(r, q, system_id, sysrec, provenance=prov, meta=meta))
        spent += sum(c for j, c in enumerate(costs) if item_keys.get(j) is not None)
        data += new
        if new:
            c0, w0 = time.process_time(), time.time()
            model = learner.update(model, new, data_all=data, systems={system_id: sysrec}, config=dict(config or {}), seed=int(seed))
            cpu_learn += time.process_time() - c0
            wall_learn += time.time() - w0
        while ci < len(cps) and spent >= cps[ci] - 1e-9:
            b = cps[ci]
            entry = {"budget": b, "spent": spent, "n_records": len(data), "ledger": ledger.to_dict(),
                     "magnitude_budget": magnitude_budget(executed), "learner_cpu_s": round(cpu_learn, 3),
                     "learner_wall_s": round(wall_learn, 3), "designer_cpu_s": round(cpu_design, 3), "model_cost": _model_cost(model)}
            if out is not None:
                entry["model"] = _save_model(model, out / f"ckpt_{b:04d}.pkl")
            else:
                models[b] = model
            rec["checkpoints"].append(entry)
            ci += 1
    rec["spent"] = spent
    rec["ledger"] = ledger.to_dict()
    rec["magnitude_budget"] = magnitude_budget(executed)
    rec["learner_cpu_s"], rec["designer_cpu_s"] = round(cpu_learn, 3), round(cpu_design, 3)
    if out is not None:
        (out / "loop_record.json").write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
        lines = [{"key": r.key, "provenance": r.provenance, "family": r.family, "twin_of": r.meta.get("twin_of"),
                  "protocol": r.protocol if not r.meta.get("twin_of") else None} for r in data[len(d0):]]
        (out / "experiments.jsonl").write_text("".join(json.dumps(k) + "\n" for k in lines), encoding="utf-8", newline="\n")
    else:
        rec["models"] = models
        rec["data"] = data
        rec["executed"] = executed
    return rec


# ================================================================================================================ evaluated checkpoints
def _bounds(reps: np.ndarray | None, alpha: float = ALPHA) -> tuple[float, float]:
    """(one-sided lower, one-sided upper) (1 - alpha) bootstrap percentile bounds (the alpha and 1 - alpha percentiles)."""
    if reps is None or len(reps) == 0:
        return float("nan"), float("nan")
    r = np.asarray(reps, np.float64)
    if not np.isfinite(r).all():
        raise ValueError("non-finite bootstrap replicates (charge failures first)")
    return float(np.percentile(r, 100 * alpha)), float(np.percentile(r, 100 * (1 - alpha)))


def checkpoint_grid(rows: list[dict], metric: str = "EE", designers: list[str] | None = None) -> tuple[dict, dict]:
    """(grid, counts). grid[(system, designer, loop_seed)] = {budget: value} on the FULL grid of the rows: every system with the
    budgets and loop seeds observed for it (over all designers) and every designer (default: all designers in the rows). Failures are
    charged, never dropped (review E, M7): a missing budget of an existing loop (stopped early) carries the loop's last value forward;
    a non-finite value (a failed evaluation) and a missing loop (no row at all) are charged MISSING_EE. counts: the charged cells in
    total and per (system, designer) under "by_pair" (callers exclude systems where a BENCHMARK designer was charged: charging a
    comparator would favour the designer it is compared with)."""
    designers = sorted(designers or {r["designer"] for r in rows})
    obs: dict[tuple, dict[int, float]] = {}
    sys_budgets: dict[str, set] = {}
    sys_seeds: dict[str, set] = {}
    for r in rows:
        s, sd, b = r["system"], int(r.get("loop_seed", 0)), int(r["budget"])
        v = r.get(metric)
        v = float(v) if v is not None and np.isfinite(float(v)) else float("nan")
        obs.setdefault((s, r["designer"], sd), {})[b] = v
        sys_budgets.setdefault(s, set()).add(b)
        sys_seeds.setdefault(s, set()).add(sd)
    grid: dict[tuple, dict[int, float]] = {}
    counts = {"carried_forward": 0, "failed_evaluation": 0, "missing_loop": 0, "missing_before_first": 0, "by_pair": {}}
    for s in sorted(sys_budgets):
        bs = sorted(sys_budgets[s])
        for d in designers:
            for sd in sorted(sys_seeds[s]):
                vals = obs.get((s, d, sd))
                if vals is None:
                    grid[(s, d, sd)] = dict.fromkeys(bs, MISSING_EE)
                    counts["missing_loop"] += 1
                    counts["by_pair"][f"{s}|{d}"] = counts["by_pair"].get(f"{s}|{d}", 0) + len(bs)
                    continue
                curve, last = {}, None
                for b in bs:
                    if b in vals:
                        v = vals[b]
                        if not np.isfinite(v):
                            v = MISSING_EE
                            counts["failed_evaluation"] += 1
                            counts["by_pair"][f"{s}|{d}"] = counts["by_pair"].get(f"{s}|{d}", 0) + 1
                    elif last is not None:
                        v = last
                        counts["carried_forward"] += 1
                    else:
                        v = MISSING_EE
                        counts["missing_before_first"] += 1
                        counts["by_pair"][f"{s}|{d}"] = counts["by_pair"].get(f"{s}|{d}", 0) + 1
                    curve[b] = v
                    last = v
                grid[(s, d, sd)] = curve
    return grid, counts


def _system_means(grid: dict) -> dict[tuple, dict[int, float]]:
    """{(system, designer): {budget: mean over loop seeds}}."""
    acc: dict[tuple, dict[int, list]] = {}
    for (s, d, _sd), curve in grid.items():
        for b, v in curve.items():
            acc.setdefault((s, d), {}).setdefault(b, []).append(v)
    return {k: {b: float(np.mean(v)) for b, v in bb.items()} for k, bb in acc.items()}


def curves(rows: list[dict], metric: str = "EE", n_boot: int = 2000, seed: int = 0) -> dict:
    """Per designer and budget: the mean over systems of the per-system mean over loop seeds with a two-sided 95 % CI (unstratified,
    rescaled system bootstrap), the median, and the mean costs (simulator calls, simulated seconds, learner CPU seconds, kick magnitude
    and current dose separately, when the rows carry them) for the quality vs experiments vs simulator-cost plots of goal5 section 25."""
    from .select import rescaled_boot_mean
    grid, counts = checkpoint_grid(rows, metric)
    means = _system_means(grid)
    designers = sorted({d for _, d in means})
    out: dict = {"_charged": counts}
    for d in designers:
        out[d] = {}
        budgets = sorted({b for (s, dd), v in means.items() if dd == d for b in v})
        for b in budgets:
            vals = {s: v[b] for (s, dd), v in means.items() if dd == d and b in v}
            est = rescaled_boot_mean(vals, None, n_boot, seed)
            cost = [r for r in rows if r["designer"] == d and int(r["budget"]) == b]

            def mean_of(key: str, cost=cost):
                xs = [float(r[key]) for r in cost if r.get(key) is not None and np.isfinite(float(r[key]))]
                return float(np.mean(xs)) if xs else None
            out[d][b] = {"mean": est.point, "ci95": est.ci95, "median": float(np.median(list(vals.values()))), "n_systems": len(vals),
                         **{k: mean_of(k) for k in ("sim_calls", "simulated_s", "learner_cpu_s", "kick_magnitude", "current_dose")}}
    return out


def passage_budget(curve: dict[int, float], target: float) -> tuple[float, bool]:
    """(budget, reached): the first checkpoint budget at which the curve is at or below the target, log-linearly interpolated with the
    previous checkpoint (the first checkpoint's budget when the curve is already there); (largest budget, False) when the curve never
    reaches the target (right-censored at the end of the design range)."""
    bs = sorted(curve)
    for i, b in enumerate(bs):
        if curve[b] <= target:
            if i == 0:
                return float(b), True
            b0, v0, v1 = bs[i - 1], curve[bs[i - 1]], curve[b]
            if v0 == v1:
                return float(b), True
            f = (v0 - target) / (v0 - v1)
            return float(math.exp(math.log(b0) + f * (math.log(b) - math.log(b0)))), True
    return float(bs[-1]), False


#: review E, N8: the estimator is conservative (biased toward 1 by the checkpoint grid and the censoring at the largest budget)
RATIO_NOTE = ("conservative: the checkpoint grid and the censoring at the largest budget bias the ratio toward 1 (in simulation a true "
              "0.50 is estimated as about 0.63, a true 0.33 as about 0.46), so 'the designer needs X % of the reference's budget' is an "
              "UPPER bound on the true fraction")


def ratio_t_bounds(b_own: np.ndarray, b_ref: np.ndarray, alpha: float) -> tuple[float, float, list[float], float]:
    """(one-sided lower, one-sided upper (1 - alpha) bound, two-sided 95 % CI, SE of log R) of R = sum(b_own) / sum(b_ref) over n
    paired systems: log R with the delta-method SE from the per-system linearisation d_s = b_own_s / mean(b_own) - b_ref_s /
    mean(b_ref) (sample variance, ddof 1) and t quantiles with n - 1 degrees of freedom, back-transformed (review E, N6)."""
    from scipy.stats import t as tdist
    bo, br = np.asarray(b_own, np.float64), np.asarray(b_ref, np.float64)
    n = len(bo)
    lr = math.log(bo.sum() / br.sum())
    d = bo / bo.mean() - br / br.mean()
    se = float(np.sqrt(d.var(ddof=1) / n)) if n > 1 else float("nan")
    q1, q2 = tdist.ppf(1.0 - alpha, n - 1), tdist.ppf(0.975, n - 1)
    return (float(math.exp(lr - q1 * se)), float(math.exp(lr + q1 * se)),
            [float(math.exp(lr - q2 * se)), float(math.exp(lr + q2 * se))], se)


def budget_ratio(rows: list[dict] | None = None, *, own: str, ref: str = "random", ref_budget: int = REF_BUDGET, metric: str = "EE",
                 n_boot: int = 2000, seed: int = 0, grid: dict | None = None, exclude: dict[str, str] | None = None,
                 alpha: float = RULE_ALPHA) -> dict:
    """PROTOCOL 5.17 (ii) (review E, M4). Per system s and loop seed j: the target T_sj = the mean of the REFERENCE designer's EE at
    `ref_budget` over its OTHER loop seeds (leave-one-loop-seed-out; all of its seeds when it has no seed j); the budgets-to-reach of
    the own designer's seed-j curve and of the reference designer's seed-j curve against T_sj with the SAME estimator
    (`passage_budget`). A curve that never reaches its target is right-censored at the largest budget tau_s; the per-system value is
    the RESTRICTED MEAN budget-to-reach over the loop seeds (the Kaplan-Meier restricted mean, which equals the mean of min(b, tau_s)
    when censoring happens only at tau_s), so no penalty value is invented for censored curves. Statistic: the ratio of sums over
    systems sum_s b_own(s) / sum_s b_ref(s). DECISION (review E, N6): the log-ratio delta-method bound with t quantiles and n - 1
    degrees of freedom (`ratio_t_bounds`; the rescaled paired percentile bootstrap was liberal at 25 systems and is reported beside
    it); success iff the one-sided upper bound at `alpha` (0.025 under PROTOCOL 5.17) is < 1. The ratio itself is conservative
    (biased toward 1; RATIO_NOTE, review E, N8). Systems where the reference has fewer than 2 loop seeds, or no
    checkpoint at `ref_budget`, or where the reference designer's cells were charged (a failed benchmark loop must not favour the
    own designer), are excluded and counted; `exclude` adds systems excluded by the caller."""
    if grid is None:
        grid, counts = checkpoint_grid(rows or [], metric)
        exclude = {**(exclude or {}), **{k.split("|")[0]: f"{ref} loop charged" for k in counts["by_pair"] if k.split("|")[1] == ref}}
    systems = sorted({s for s, _, _ in grid})
    per_sys: dict[str, dict] = {}
    excluded: dict[str, str] = {}
    for s in systems:
        if s in (exclude or {}):
            excluded[s] = exclude[s]
            continue
        ref_seeds = sorted(sd for (ss, d, sd) in grid if ss == s and d == ref)
        own_seeds = sorted(sd for (ss, d, sd) in grid if ss == s and d == own)
        if len(ref_seeds) < 2:
            excluded[s] = "reference designer has fewer than 2 loop seeds"
            continue
        if ref_budget not in grid[(s, ref, ref_seeds[0])]:
            excluded[s] = f"no checkpoint at {ref_budget}"
            continue
        if not own_seeds:
            excluded[s] = "no own-designer loop"
            continue
        ref_at = {sd: grid[(s, ref, sd)][ref_budget] for sd in ref_seeds}
        rows_s = []
        for sd in sorted(set(own_seeds) | set(ref_seeds)):
            others = [ref_at[i] for i in ref_seeds if i != sd] or list(ref_at.values())
            target = float(np.mean(others))
            rec = {"loop_seed": sd, "target": target}
            if sd in own_seeds:
                rec["b_own"], rec["own_reached"] = passage_budget(grid[(s, own, sd)], target)
            if sd in ref_seeds:
                rec["b_ref"], rec["ref_reached"] = passage_budget(grid[(s, ref, sd)], target)
            rows_s.append(rec)
        b_own = [r["b_own"] for r in rows_s if "b_own" in r]
        b_ref = [r["b_ref"] for r in rows_s if "b_ref" in r]
        per_sys[s] = {"b_own": float(np.mean(b_own)), "b_ref": float(np.mean(b_ref)), "tau": float(max(grid[(s, ref, ref_seeds[0])])),
                      "own_censored": sum(1 for r in rows_s if r.get("own_reached") is False),
                      "ref_censored": sum(1 for r in rows_s if r.get("ref_reached") is False), "seeds": rows_s}
    out = {"own": own, "ref": ref, "ref_budget": ref_budget, "metric": metric, "n_systems": len(per_sys), "excluded": excluded,
           "estimator": "leave-one-loop-seed-out targets; restricted mean budget-to-reach (censored at the largest budget); ratio of sums"}
    if len(per_sys) < 2:
        out.update({"ratio": float("nan"), "ci95": [float("nan")] * 2, "alpha": alpha, "upper_bound": float("nan"), "success": False,
                    "per_system": per_sys, "note": "fewer than 2 systems"})
        return out
    sids = sorted(per_sys)
    bo = np.array([per_sys[s]["b_own"] for s in sids])
    br = np.array([per_sys[s]["b_ref"] for s in sids])
    n = len(sids)
    ratio = float(bo.sum() / br.sum())
    lo, hi, ci, se = ratio_t_bounds(bo, br, alpha)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    reps = bo[idx].sum(axis=1) / br[idx].sum(axis=1)
    reps = ratio + math.sqrt(n / (n - 1)) * (reps - ratio)
    out.update({"ratio": ratio, "ci95": ci, "alpha": alpha, "lower_bound": lo, "upper_bound": hi, "success": bool(hi < 1.0),
                "interval": "log-ratio delta method with a t quantile (n - 1 df) (review E, N6: the rescaled percentile bootstrap was "
                            "liberal at 25 systems); the rescaled bootstrap CI is reported beside it",
                "se_log_ratio": se, "bootstrap_ci95": [float(np.percentile(reps, 2.5)), float(np.percentile(reps, 97.5))],
                "interpretation": RATIO_NOTE, "sum_own": float(bo.sum()), "sum_ref": float(br.sum()),
                "censored_own": int(sum(per_sys[s]["own_censored"] for s in sids)),
                "censored_ref": int(sum(per_sys[s]["ref_censored"] for s in sids)), "per_system": per_sys})
    return out


def active_success(rows: list[dict], *, own: str, comparators: tuple[str, ...] = ("random", "fixed"), metric: str = "EE",
                   ref_designer: str = "random", ref_budget: int = REF_BUDGET, matched: str | None = "random_matched",
                   n_boot: int = 2000, seed: int = 0, alpha: float = RULE_ALPHA) -> dict:
    """The success rule of PROTOCOL 5.17. rows: evaluated checkpoints {"system", "designer", "loop_seed", "budget", metric} (lower is
    better); failures are charged by `checkpoint_grid` (never dropped).
    (i) FIXED BUDGET, ONE TEST PER COMPARATOR (review E, N6: "better at >= 2 of 5 correlated budgets" was not a level-alpha test):
        for each comparator, the per-system statistic = the mean over the system's checkpoint budgets of (own - comparator), each the
        mean over loop seeds; its mean over systems gets a paired, unstratified, rescaled system bootstrap; the own designer is BETTER
        than the comparator when the one-sided upper bound at `alpha` is below 0. Rule (i) holds when it is better than EVERY
        comparator (an intersection-union test: level alpha overall) and SIGNIFICANTLY WORSE than none at any single budget (the
        one-sided lower bound of that budget's difference at `alpha` above 0; this condition only makes success harder). The
        per-budget differences, bounds and "better" flags are reported (descriptive; n_budgets_better counts them).
    (ii) BUDGET RATIO: `budget_ratio(own, ref=ref_designer, alpha=alpha)` succeeds (ratio of sums of restricted-mean budgets-to-reach,
        one-sided upper bound at `alpha` < 1).
    Each rule is tested one-sided at alpha = 0.025 (P4-D20: Bonferroni over the two rules), so the false-positive rate of the union
    stays at or below 5 %. SUCCESS = (i) or (ii). Reported beside, NOT part of the rule: the same two comparisons against the
    magnitude-MATCHED random design (`matched`, when present in the rows), a control for large-effect selection."""
    from .select import rescaled_boot_mean
    present = {r["designer"] for r in rows}
    missing = [d for d in (*comparators, ref_designer) if d not in present]
    if missing:
        raise ValueError(f"the comparison design is incomplete: no loops of {missing} (PROTOCOL 5.17 runs every reference designer)")
    use_matched = bool(matched) and matched in present
    designers = sorted({own, *comparators, ref_designer} | ({matched} if use_matched else set()))
    grid, counts = checkpoint_grid(rows, metric, designers)
    means = _system_means(grid)
    bench = {*comparators, ref_designer} | ({matched} if use_matched else set())
    exclude = {k.split("|")[0]: f"benchmark designer {k.split('|')[1]} charged" for k in counts["by_pair"] if k.split("|")[1] in bench}
    systems = sorted({s for s, _ in means} - set(exclude))

    def fixed_budget(comps: tuple[str, ...]) -> dict:
        budgets = sorted({b for (s, d), v in means.items() if d == own for b in v})
        per_budget, n_better, any_worse = {}, 0, False
        for b in budgets:
            row, better_all = {}, True
            for c in comps:
                diff = {s: means[(s, own)][b] - means[(s, c)][b] for s in systems if b in means.get((s, own), {}) and b in means.get((s, c), {})}
                est = rescaled_boot_mean(diff, None, n_boot, seed)
                lo, hi = _bounds(est.reps, alpha) if est.reps is not None else (float("nan"), float("nan"))
                better = bool(np.isfinite(hi) and hi < 0)
                worse = bool(np.isfinite(lo) and lo > 0)
                row[c] = {"diff": est.point, "ci95": est.ci95, "lower_bound": lo, "upper_bound": hi, "n_systems": est.n_units,
                          "better": better, "worse": worse}
                better_all &= better
                any_worse |= worse
            row["better_than_all"] = better_all
            n_better += int(better_all)
            per_budget[b] = row
        tests = {}
        for c in comps:
            avg = {}
            for s in systems:
                bo, bc = means.get((s, own), {}), means.get((s, c), {})
                common = sorted(set(bo) & set(bc))
                if common:
                    avg[s] = float(np.mean([bo[b] - bc[b] for b in common]))
            est = rescaled_boot_mean(avg, None, n_boot, seed + 1)
            lo, hi = _bounds(est.reps, alpha) if est.reps is not None else (float("nan"), float("nan"))
            tests[c] = {"diff_mean_over_budgets": est.point, "ci95": est.ci95, "lower_bound": lo, "upper_bound": hi,
                        "n_systems": est.n_units, "better": bool(np.isfinite(hi) and hi < 0)}
        success = bool(tests and all(v["better"] for v in tests.values()) and not any_worse)
        return {"per_budget": per_budget, "n_budgets_better": n_better, "any_budget_worse": any_worse, "alpha": alpha,
                "tests": tests, "rule": "mean over budgets of own - comparator, better than every comparator (intersection-union), "
                                        "worse at no single budget", "success": success}

    fb = fixed_budget(tuple(comparators))
    br = budget_ratio(own=own, ref=ref_designer, ref_budget=ref_budget, metric=metric, n_boot=n_boot, seed=seed, grid=grid, exclude=exclude,
                      alpha=alpha)
    out = {"own": own, "comparators": list(comparators), "metric": metric, "alpha_per_rule": alpha, "charged": counts,
           "excluded_systems": exclude,
           "n_systems": len(systems), "fixed_budget": fb,
           "per_budget": fb["per_budget"], "n_budgets_better": fb["n_budgets_better"], "any_budget_worse": fb["any_budget_worse"],
           "success_fixed_budget": fb["success"], "budget_ratio": br, "success_fewer_experiments": br["success"],
           "success": bool(fb["success"] or br["success"])}
    if use_matched:
        out["matched_control"] = {"designer": matched, "fixed_budget": fixed_budget((matched,)),
                                  "budget_ratio": budget_ratio(own=own, ref=matched, ref_budget=ref_budget, metric=metric, n_boot=n_boot,
                                                               seed=seed, grid=grid, exclude=exclude, alpha=alpha)}
    return out


# ================================================================================================================ MDE by simulation
def _interp_log(bs: np.ndarray, vs: np.ndarray, b: float) -> float:
    """A curve at budget b by linear interpolation in log(budget), extended beyond the observed range by the end segments' slopes
    (never increasing past the last observed value: learning curves are not extrapolated upwards)."""
    lb = np.log(bs)
    x = math.log(b)
    if x <= lb[0]:
        s = (vs[1] - vs[0]) / (lb[1] - lb[0]) if len(bs) > 1 else 0.0
        return float(vs[0] + s * (x - lb[0]))
    if x >= lb[-1]:
        s = (vs[-1] - vs[-2]) / (lb[-1] - lb[-2]) if len(bs) > 1 else 0.0
        return float(vs[-1] + min(s, 0.0) * (x - lb[-1]))
    return float(np.interp(x, lb, vs))


def _noise_params(curves: list[np.ndarray]) -> tuple[float, float]:
    """(sd of the per-seed offset, sd of the per-budget residual) of replicate curves (rows = loop seeds, columns = budgets), by the
    method of moments of a one-way random-effects model; (0, 0) with fewer than 2 replicates."""
    Y = np.vstack(curves)
    if Y.shape[0] < 2:
        return 0.0, 0.0
    r = Y - Y.mean(axis=0, keepdims=True)
    off = r.mean(axis=1)
    w = r - off[:, None]
    n_s, n_b = Y.shape
    sd_w = math.sqrt(float((w ** 2).sum()) / max(1, (n_s - 1) * (n_b - 1)))
    var_o = float(np.var(off, ddof=1)) - sd_w ** 2 / n_b
    return math.sqrt(max(0.0, var_o)), sd_w


def mde_by_simulation(rows: list[dict], *, metric: str = "EE", ref: str = "random", fixed: str = "fixed",
                      efficiencies: tuple[float, ...] = (1.0, 1.25, 1.5, 2.0, 3.0), n_sim: int = 200, n_seeds: int = 3,
                      ref_budget: int = REF_BUDGET, n_boot: int = 1000, power: float = 0.8, seed: int = 0,
                      alpha: float = RULE_ALPHA, null_fixed_offsets: tuple[float, ...] = (0.05, 0.10)) -> dict:
    """Minimum detectable effect of the 5.17 success rule by simulation (review E, M4), from OBSERVED loop curves of the reference
    designers (e.g. a benchmark reference learner on the dev suite before the freeze). Per system: the mean curve of `ref` over its loop
    seeds (and of `fixed`, else the `ref` curve), and the noise of the curves (a per-seed offset plus per-budget residuals, pooled over
    the two designers; each sd floored at 10 % of its median over systems). A simulated suite draws n_seeds loops per designer per system:
    ref = m_ref(b) + noise, fixed = m_fixed(b) + noise, own = m_ref(e x b) + noise (the own designer reaches at budget b what `ref`
    reaches at e x b; e = the efficiency), and `active_success` decides at the rule's alpha (0.025 per rule, P4-D20). Returns per
    efficiency the rates of rule (i), rule (ii) and
    either over n_sim suites (the e = 1 row is the false-positive rate) and the MDE = the smallest efficiency whose power >= `power`.
    The SIZE of the union is also checked under nulls with a WEAKER fixed design (review E, N6): e = 1 with the fixed curve shifted up
    by each of `null_fixed_offsets` (in EE units), where only the random comparison binds rule (i); reported under
    "false_positive_rate_weaker_fixed"."""
    grid, counts = checkpoint_grid(rows, metric, [ref] + ([fixed] if any(r["designer"] == fixed for r in rows) else []))
    has_fixed = any(d == fixed for (_, d, _) in grid)
    bad = {k.split("|")[0] for k in counts["by_pair"]}
    systems = sorted({s for s, _, _ in grid} - bad)
    model: dict[str, dict] = {}
    for s in systems:
        bs = np.array(sorted(grid[next(k for k in grid if k[0] == s)]), dtype=float)
        ref_c = [np.array([grid[k][int(b)] for b in bs]) for k in sorted(grid) if k[0] == s and k[1] == ref]
        fix_c = [np.array([grid[k][int(b)] for b in bs]) for k in sorted(grid) if k[0] == s and k[1] == fixed] if has_fixed else []
        so_r, sw_r = _noise_params(ref_c)
        so_f, sw_f = _noise_params(fix_c) if len(fix_c) >= 2 else (so_r, sw_r)
        model[s] = {"bs": bs, "m_ref": np.mean(ref_c, axis=0), "m_fix": np.mean(fix_c, axis=0) if fix_c else np.mean(ref_c, axis=0),
                    "sd_o": math.sqrt((so_r ** 2 + so_f ** 2) / 2), "sd_w": math.sqrt((sw_r ** 2 + sw_f ** 2) / 2)}
    med_o = float(np.median([m["sd_o"] for m in model.values()])) if model else 0.0
    med_w = float(np.median([m["sd_w"] for m in model.values()])) if model else 0.0
    for m in model.values():
        m["sd_o"] = max(m["sd_o"], 0.1 * med_o)
        m["sd_w"] = max(m["sd_w"], 0.1 * med_w)
    rng = np.random.default_rng(seed)
    table = {}
    null_weaker = {}
    scenarios = [(float(e), 0.0) for e in efficiencies] + [(1.0, float(o)) for o in null_fixed_offsets]
    for e, off_fix in scenarios:
        wins = {"fixed_budget": 0, "budget_ratio": 0, "either": 0}
        ratios = []
        for k in range(n_sim):
            sim_rows = []
            for s, m in model.items():
                bs = m["bs"]
                for sd in range(n_seeds):
                    for d, curve in (("ref", m["m_ref"]), ("fixed", m["m_fix"] + off_fix),
                                     ("own", np.array([_interp_log(bs, m["m_ref"], b * e) for b in bs]))):
                        off = rng.normal(0.0, m["sd_o"])
                        vals = np.clip(curve + off + rng.normal(0.0, m["sd_w"], size=len(bs)), 0.0, MISSING_EE)
                        sim_rows += [{"system": s, "designer": d, "loop_seed": sd, "budget": int(b), metric: float(v)}
                                     for b, v in zip(bs, vals, strict=True)]
            res = active_success(sim_rows, own="own", comparators=("ref", "fixed"), metric=metric, ref_designer="ref", ref_budget=ref_budget,
                                 matched=None, n_boot=n_boot, seed=seed + k, alpha=alpha)
            wins["fixed_budget"] += int(res["success_fixed_budget"])
            wins["budget_ratio"] += int(res["success_fewer_experiments"])
            wins["either"] += int(res["success"])
            if np.isfinite(res["budget_ratio"].get("ratio", float("nan"))):
                ratios.append(res["budget_ratio"]["ratio"])
        row = {k: v / n_sim for k, v in wins.items()}
        if off_fix:
            null_weaker[off_fix] = row
            continue
        table[float(e)] = row
        table[float(e)]["mean_estimated_ratio"] = float(np.mean(ratios)) if ratios else float("nan")
        table[float(e)]["true_ratio_approx"] = 1.0 / float(e)

    def mde(key: str):
        ok = [e for e in efficiencies if e > 1.0 and table[float(e)][key] >= power]
        return float(min(ok)) if ok else None
    return {"n_systems": len(model), "n_excluded_systems": len(bad), "n_sim": n_sim, "n_seeds": n_seeds, "n_boot": n_boot, "alpha_per_rule": alpha,
            "power_target": power, "table": table,
            "false_positive_rate": table.get(1.0), "false_positive_rate_weaker_fixed": null_weaker,
            "mde": {k: mde(k) for k in ("fixed_budget", "budget_ratio", "either")}, "ratio_interpretation": RATIO_NOTE,
            "noise_medians": {"sd_offset": med_o, "sd_residual": med_w}}
