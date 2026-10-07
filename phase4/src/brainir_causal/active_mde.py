"""Pre-freeze minimum detectable effect (MDE) of the active-design success rule (benchmarks/causal_state_v1/PROTOCOL.md section
5.17: "The minimum detectable effect of this rule is computed by simulation on the dev suite before the freeze and reported"; review
E, M4). ORCHESTRATOR SIDE; trusted code only; the synthetic DEV tier only.

    out = reference_pack_job(pack)      # container side: several loops, packed as (loop, checkpoint) tasks on worker processes
    out = reference_loop_job(job)       # container side: ONE loop with its fits inside the loop (the unpacked reference)
    rep = summarize(rows)               # loop.mde_by_simulation per learner (chunked; `summary_parts_job` spreads it over containers)

WHY REFERENCE LEARNERS. The power of the rule depends on the EE curves of the learner the designers feed; before the freeze no method
exists, so the curves come from the benchmark's own references, the only learners fixed before any method (PROTOCOL 8,
`brainir_causal.refs`): the FULL-STATE reference (every system; the predictability anchor) and the TRUE-STATE reference (compressible
systems only: it needs the true causal state). Both are trusted code, so the loops run without model workers.

THE LEARNER ADAPTER (`ReferenceLearner`). run_loop's learner interface (`fit(data, systems=, config=, seed=)` and
`update(model, new_data, data_all=, ...)`): every call returns a `LazyReference` that REFITS the reference from scratch on ALL the
loop's data at that point (D0 + every executed experiment with its twin), seed = the loop seed. The refit happens on the model's first
use; the reference designers of the MDE (`random`, `fixed`) never query the model, so only the checkpoint models (queried by run_loop
for their cost record, then evaluated) are ever fitted. A reference fit depends only on (records, seed, thread count), so a lazy
checkpoint model is exactly the model an eager refit after every batch would hold at that checkpoint. The TRUE-STATE learner receives
the true state of every training record: D0 records from the tier's truth store, loop records from the simulator's full records
(`_TruthCtx`).

PACKING (the full run: minimum wall time without changing any result). Because a reference fit depends only on (its records, the seed,
the thread count) and the random / fixed designers never query the model, a loop splits into
    phase 1  `loop_phase1`: the loop's design and simulation with every fit DEFERRED (`DeferredLearner`); run_loop's data (D0 + the
             loop's records in order), the true states and each checkpoint's record count are pickled on the container's disk. The
             loops of both learners of one DATA STREAM (`stream_id`: system, designer, seed, loop settings) run identical experiments,
             so phase 1 runs once per stream;
    phase 2  `checkpoint_task`, one per checkpoint: the reference fitted on the loop's first n_records records (exactly the records
             the in-loop LazyReference holds at that checkpoint) and evaluated.
`reference_pack_job` runs several loops in one container on ONE pool of spawned worker processes (`workers` x `threads` BLAS / torch
threads each: the thread settings of `p4modal.jobproc`) scheduled by `schedule`: the phase-1 jobs first, and a stream's tasks as soon
as its own phase 1 ends, longest predicted first, admitted only while the predicted memory of the running tasks fits
`mem_budget_gb`. A crashed pool (e.g. a worker killed for memory) is rebuilt and its lost jobs retried once with doubled memory
predictions; a second crash is an error row. Every finished task goes to the pack's `ProgressStore`, so that a pack Modal preempts
and restarts (the same input) runs only its unfinished tasks. CURRENT LIMIT: on Modal the store is a modal.Dict, and P1's run_call
starts job subprocesses without the Modal client or credentials, so the store is unavailable there (recorded as the pack's
progress_error; the pack runs normally and a restarted pack reruns all its tasks) until the container's function process relays
progress or the class is non-preemptible. The unpacked
`reference_loop_job` (fits inside run_loop, one process) is the reference the packed results must equal bit for bit
(`scripts/p4/active_mde.py`: the profile, and a verification sample inside every run).

SUMMARY. `summary_specs` splits `loop.mde_by_simulation` into independent calls (learner x scenario x chunk of MDE_CHUNK simulated
suites, each with its own seed), `summary_parts` runs any subset of them (processes or containers), `summarize_from_parts` merges the
chunks (size-weighted rates) into the function's own output format and MDE rule; `summarize` does all three in one process.

CHECKPOINT EVALUATION (the quality of PROTOCOL 5.17): the class-balanced EE at the primary horizon on the VERDICT items (roles in,
target, near, far, hidden) of the system's dev EVAL part, computed exactly as the verdict computes its EE (`evaluate.predict_items`,
`evaluate.eval_effects`, `evaluate.ee_cb(units, PRIMARY, VERDICT_KINDS, "class")`, the path of `verdict.collect_metrics`):
abstentions scored as no effect, failures at the cap. The TRUE-STATE model gets the truth of every held-out history registered first
(as in the calibration, `calibrate.calibrate_system`). Only the verdict items are predicted (the EE selects them anyway).

GENERATOR CHECK. New loop experiments are simulated by the generator baked into the container image; both paths refuse to run when
that generator does not reproduce the system the tier was built from (its content hash differs from the internal record's).

DRAW CONTEXT (reference learner v2, LOG P4-D43). Every trajectory has its own parameter draw and z is closed only given it, so
TRUE-STATE encodes [z, draw]: its fits get the effective draw of every training record (`draw_by_key`: D0 from the tier's truth store,
the loop's records from the simulator's `truth["draw"]`) and every registered held-out history gets its own draw. When the tier's
truth carries draws (`draw_requirement`), these are ERRORS, never a silent fallback to z alone or to the training-mean draw: a loop
record the simulator returned without a draw (a generator without `draw_effective`), draws of different lengths or with a
non-finite value, a held-out record with a true state but no draw, and a TRUE-STATE fit whose training draws VARY but which reports
`info()['draw_context']` False (`check_draw_context`). A fit whose training draws are CONSTANT (every coordinate, by the learner's
own criterion) legitimately runs without the context, because z alone is exact given that draw: it is recorded as draw_context
False with the reason CONSTANT_DRAWS and is not refused (the orchestrator's decision of 2026-09-27). `draw_preflight` checks every
system before the run (complete, finite draws of one length over D0 and a generator with `draw_effective`; draws constant over D0
are a note, `draw_verdict`). The rows record draw_required, draw_context, draw_context_reason, training_draws,
n_registered_without_draw and the learner's static_context note.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import shutil
import tempfile
import time
import traceback
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path

import numpy as np

LEARNERS = ("full_state", "true_state")
DESIGNERS = ("random", "fixed")
N_BOOT_EE = 200                 # bootstrap replicates of each checkpoint's EE CI (the MDE uses the point estimate only)
EFFICIENCIES = (1.0, 1.1, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0)
NULL_FIXED_OFFSETS = (0.05, 0.10)
SCENARIO_SEED_STRIDE = 7919     # scenario s of the summary uses seed + SCENARIO_SEED_STRIDE x (s + 1) + CHUNK_SEED_STRIDE x chunk
CHUNK_SEED_STRIDE = 1_000_003
MDE_CHUNK = 100                 # simulated suites per summary call (the summary's parallel unit)
ROW_KEYS = ("system", "learner", "designer", "loop_seed", "budget", "spent", "n_records", "experiments", "trajectories")


# ================================================================================================================ the learner adapter
class LazyReference:
    """A reference model fitted on first use (see the module docstring). `materialize()` returns the fitted trusted model."""

    def __init__(self, learner: ReferenceLearner, records: list, seed: int):
        self._learner = learner
        self._records = list(records)
        self._seed = int(seed)
        self._model = None
        self.fit_s = None

    def materialize(self):
        if self._model is None:
            t0 = time.process_time()
            self._model = self._learner.fit_now(self._records, self._seed)
            self.fit_s = round(time.process_time() - t0, 3)
            self._records = []                        # the fitted model no longer needs the list
        return self._model

    def info(self):
        inf = dict(self.materialize().info() or {})
        tc = dict(inf.get("train_cost") or {})
        tc.setdefault("cpu_s", self.fit_s)
        inf["train_cost"] = tc
        return inf

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.materialize(), name)


class ReferenceLearner:
    """run_loop learner: a benchmark reference refitted on all the loop's data at every update (lazily; module docstring).
    name: 'full_state' | 'true_state'. truth_z / truth_draw: {record key: (T, k) true state} / {record key: (d,) effective draw
    parameters} (true_state), completed with the loop's records by the simulator wrapper that shares the same dicts. draw_required:
    the tier's truth carries draws (module docstring, DRAW CONTEXT): every TRUE-STATE fit then gets them and must pass
    `check_draw_context` (its result is kept on the model as `mde_draw_check`), else it raises."""

    def __init__(self, name: str, sid: str, sysrec: dict, *, truth_z: dict | None = None, truth_draw: dict | None = None,
                 draw_required: bool = False, cfg=None):
        from .refs import DEFAULT_CFG
        if name not in LEARNERS:
            raise ValueError(f"unknown reference learner {name!r}")
        if name == "true_state" and truth_z is None:
            raise ValueError("the true-state learner needs the true state of its training records")
        self.name, self.sid, self.sysrec = name, sid, sysrec
        self.truth_z, self.truth_draw, self.draw_required = truth_z, truth_draw, bool(draw_required)
        self.cfg = cfg or DEFAULT_CFG
        self.n_fits = 0

    def fit_now(self, records: list, seed: int):
        from .refs import fit_reference
        cfg = replace(self.cfg, seed=int(seed))
        self.n_fits += 1
        if self.name == "full_state":
            return fit_reference("full_state", self.sid, records, self.sysrec, cfg=cfg)
        missing = [r.key for r in records if r.key not in self.truth_z]
        if missing:
            raise ValueError(f"true state missing for {len(missing)} training records (e.g. {missing[0]})")
        draws = None
        have = {r.key: self.truth_draw[r.key] for r in records if r.key in (self.truth_draw or {})}
        if have and len(have) == len(records):
            draws = have
        elif self.draw_required:
            raise ValueError(f"effective draw missing for {len(records) - len(have)} of {len(records)} training records although the "
                             "tier's truth carries draws")
        model = fit_reference("true_state", self.sid, records, self.sysrec,
                              truth={"z": {r.key: self.truth_z[r.key] for r in records}, "draw": draws}, cfg=cfg)
        if self.draw_required:
            model.mde_draw_check = check_draw_context(model, [draws[r.key] for r in records])      # read by evaluate_checkpoint
        return model

    # run_loop's interface
    def fit(self, data, *, systems=None, config=None, seed=0):
        return LazyReference(self, data, seed)

    def update(self, model, new_data, *, data_all, systems=None, config=None, seed=0):
        return LazyReference(self, data_all, seed)


class _DeferredModel:
    """Phase 1's model handle (module docstring, PACKING): never fitted. run_loop asks only info() (its checkpoint cost record); a
    designer that queried the model would get an error (the MDE's random / fixed designers never do)."""

    def info(self):
        return {"train_cost": {"deferred": True}}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        raise RuntimeError(f"phase 1 defers the fits: the model's {name!r} is not available (a designer that queries the model cannot "
                           "run in phase 1)")


class DeferredLearner:
    """Phase 1's learner: fits nothing (module docstring, PACKING)."""

    def fit(self, data, *, systems=None, config=None, seed=0):
        return _DeferredModel()

    def update(self, model, new_data, *, data_all, systems=None, config=None, seed=0):
        return _DeferredModel()


class _TruthCtx:
    """A SimContext wrapper that keeps the true state and the effective draw of every trajectory it simulates ({dataset key: z},
    {dataset key: draw}) for the TRUE-STATE learner (DirectSim uses only store, store_key and run)."""

    def __init__(self, ctx, truth_z: dict, truth_draw: dict | None = None):
        self.ctx = ctx
        self.truth_z = truth_z
        self.truth_draw = truth_draw if truth_draw is not None else {}
        self.store = ctx.store

    def store_key(self, q):
        return self.ctx.store_key(q)

    def run(self, q, meta=None):
        r = self.ctx.run(q, meta)
        tr = r.get("truth") or {}
        if tr.get("z") is not None:
            self.truth_z[r["key"]] = np.asarray(tr["z"], np.float64)
        if tr.get("draw") is not None:
            self.truth_draw[r["key"]] = np.asarray(tr["draw"], np.float64).reshape(-1)
        return r


# ================================================================================================================ shared pieces
def _truth_of(truth_dir: Path | None, keys) -> tuple[dict, dict]:
    """({key: z}, {key: effective draw}) of the records with that truth in the tier's truth store (the arrays calibrate.py loads)."""
    z, dr = {}, {}
    if truth_dir is None:
        return z, dr
    for k in keys:
        p = Path(truth_dir) / "traj" / f"{k}.npz"
        if p.exists():
            with np.load(p) as a:
                if "z" in a.files:
                    z[k] = np.asarray(a["z"], np.float64)
                if "draw" in a.files:
                    dr[k] = np.asarray(a["draw"], np.float64).reshape(-1)
    return z, dr


def draw_requirement(keys, draws: dict) -> bool:
    """Whether the tier's truth carries the effective draws (module docstring, DRAW CONTEXT): True when every record of `keys` has
    one, False when none has; a truth store with draws for only some of them is an error (an incomplete tier)."""
    keys = list(keys)
    n = sum(1 for k in keys if k in draws)
    if n and n != len(keys):
        raise RuntimeError(f"the truth store has the effective draw for {n} of {len(keys)} records (an incomplete tier)")
    return bool(n)


#: the reason a TRUE-STATE fit legitimately runs without its draw context (module docstring, DRAW CONTEXT); "no draws" = a tier
#: whose truth carries none (smoke tiers, `--allow-no-draw`)
CONSTANT_DRAWS, NO_DRAWS = "constant draws", "no draws"


def draw_variation(draws) -> dict:
    """{"n", "sizes" (the distinct lengths), "finite" (every value), "varying" (the number of coordinates that vary, by refs'
    `_setup_static` criterion for a kept static coordinate: finite and sd > 1e-9 (1 + |mean|); None unless one length)} of a set of
    effective draws."""
    vecs = [np.asarray(v, np.float64).reshape(-1) for v in draws]
    sizes = sorted({v.size for v in vecs})
    out = {"n": len(vecs), "sizes": sizes, "finite": all(bool(np.isfinite(v).all()) for v in vecs), "varying": None}
    if len(sizes) == 1:
        M = np.stack(vecs)
        mu, sd = M.mean(0), M.std(0)
        out["varying"] = int((np.isfinite(M).all(0) & (sd > 1e-9 * (1.0 + np.abs(mu)))).sum())
    return out


def check_draw_context(model, train_draws) -> dict:
    """The draw rule of one TRUE-STATE fit on a tier whose truth carries draws (module docstring, DRAW CONTEXT): {"draw_context",
    "training_draws": "varying" | "constant", "reason": None | CONSTANT_DRAWS}. Training draws of different lengths or with a
    non-finite value raise. Draws that VARY over the fit's records with the context off raise. Draws whose every coordinate is
    constant over them switch the context off legitimately (z alone is exact given that draw): recorded as CONSTANT_DRAWS."""
    dv = draw_variation(train_draws)
    if len(dv["sizes"]) != 1:
        raise RuntimeError(f"TRUE-STATE fit whose training draws have lengths {dv['sizes']} (one length required)")
    if not dv["finite"]:
        raise RuntimeError("TRUE-STATE fit with a non-finite training draw")
    on = bool((model.info() or {}).get("draw_context"))
    if not on and dv["varying"]:
        note = (getattr(model, "fit_notes", None) or {}).get("static_context")
        raise RuntimeError(f"TRUE-STATE fit without its draw context although its training draws vary ({dv['varying']} of "
                           f"{dv['sizes'][0]} coordinates; static_context: {note})")
    return {"draw_context": on, "training_draws": "varying" if dv["varying"] else "constant", "reason": None if on else CONSTANT_DRAWS}


def checkpoint_ee(model, sysc, items_v: list, *, n_boot: int = N_BOOT_EE, seed: int = 0) -> dict:
    """The verdict EE of one checkpoint model (module docstring): class-balanced, primary horizon, verdict items."""
    from . import evaluate as EV
    from .evalio import PRIMARY, VERDICT_KINDS
    preds = EV.predict_items(model, sysc, items_v)
    eff = EV.eval_effects(sysc, items_v, preds, n_boot, seed)
    est = EV.ee_cb(eff["_units"], PRIMARY, VERDICT_KINDS, "class", n_boot, seed)
    return {"EE": float(est.point), "EE_ci95": [float(x) for x in est.ci95], "n_cells": int(est.n_units or 0),
            "n_items": int(eff.get("n_items") or 0), "n_abstained": int(eff.get("n_abstained") or 0),
            "n_failed": int(eff.get("n_failed") or 0), "EE_pooled": float((eff.get(f"EE_{PRIMARY}") or {}).get("point", float("nan")))}


def check_generator(internal: dict, truth_obj) -> None:
    """Refuse a container whose generator does not reproduce the system the tier was built from (module docstring)."""
    if internal.get("kind") != "synthetic" or truth_obj is None:
        return
    have, want = str(truth_obj.content_hash()), str(internal.get("system_hash"))
    if have != want:
        raise RuntimeError(f"generator mismatch for {internal.get('system_id')}: the container's generator builds system hash "
                           f"{have[:12]}, the tier was built with {want[:12]} (rebuild the tier or bake the generator it was built with)")


def _tiers(job: dict) -> tuple[dict, dict]:
    from . import suites as SU
    held = SU.tier_dirs(job["heldout_tier"], Path(job["heldout_root"]))
    pubd = SU.tier_dirs(job.get("public_tier", job["heldout_tier"]), Path(job.get("public_root", job["heldout_root"])))
    return held, pubd


def _d0_rows(job: dict):
    """(the system's public experiment set (lazy), its D0 index rows): D0 exactly as isolation.loop_job selects it (the passive 'd0'
    training records of the system's public part)."""
    from . import suites as SU
    from .data import ExperimentSet
    sid = job["sid"]
    _held, pubd = _tiers(job)
    es = ExperimentSet.load(pubd["public"] / SU._safe(sid), lazy=True)
    rows = [r for r in es.rows if r["system_id"] == sid and r.get("split") == "train" and not (r["protocol"].get("events") or [])
            and (r.get("meta") or {}).get("role", "d0") == "d0"]
    return es, rows


def load_d0(job: dict) -> tuple[dict, list]:
    """(public system record, D0) of the job's system (`_d0_rows`); only those records are loaded (the reference designers never
    restart from other public records)."""
    es, rows = _d0_rows(job)
    return es.systems[job["sid"]], [es.load(r) for r in rows]


def _truth_dir(job: dict) -> Path | None:
    from . import suites as SU
    held, _pubd = _tiers(job)
    d = held["truth"] / SU._safe(job["sid"])
    return d if d.exists() else None


def _loop_truth(job: dict, ctx, d0: list):
    """(truth_z, truth_draw, draw_required, simulation context) of a TRUE-STATE loop: D0's truth from the tier's truth store, the
    loop's own records captured from the simulator (`_TruthCtx`)."""
    tz, tdr = _truth_of(_truth_dir(job), [r.key for r in d0])
    req = draw_requirement([r.key for r in d0], tdr)
    return tz, tdr, req, _TruthCtx(ctx, tz, tdr)


def _check_loop_draws(data: list, truth_draw: dict) -> None:
    """With draws required: every record of the loop (D0 and the simulator's new trajectories) has its effective draw."""
    lacking = [r.key for r in data if r.key not in truth_draw]
    if lacking:
        raise RuntimeError(f"the tier's truth carries effective draws but {len(lacking)} of {len(data)} loop records have none (the "
                           "simulator returns no draw for new trajectories: a generator without draw_effective?)")
    dv = draw_variation([truth_draw[r.key] for r in data])
    if len(dv["sizes"]) != 1 or not dv["finite"]:
        raise RuntimeError(f"the loop's effective draws are inconsistent: lengths {dv['sizes']}, all finite {dv['finite']} (D0 from "
                           "the tier's truth store, new trajectories from the simulator)")


def sim_context(job: dict):
    """(internal record, SimContext, generator system) for the loop's new experiments, WITHOUT the evaluation inputs (phase 1; the
    same context `harness.system_context` builds). Checks the generator (`check_generator`)."""
    from . import suites as SU
    sid = job["sid"]
    internal = json.loads(Path(job["internal_path"]).read_text(encoding="utf-8"))[sid]
    truth_obj = None
    if internal.get("kind") == "synthetic":
        from .synthadapter import register_generator, suite_systems
        if job.get("generator"):
            register_generator(job["generator"][0], job["generator"][1])
        truth_obj = suite_systems(internal["tier"], int(internal["suite_seed"]))[sid]
        ctx = SU.SimContext(internal, store_root=job["store_root"], synthetic_system=truth_obj, read_roots=job.get("store_read_roots") or ())
    else:
        ctx = SU.SimContext(internal, store_root=job["store_root"], read_roots=job.get("store_read_roots") or ())
    check_generator(internal, truth_obj)
    return internal, ctx, truth_obj


def eval_context_from_inputs(inputs: dict, truth_dir: Path | None, with_truth: bool, draw_required: bool = False) -> dict:
    """{"sysc", "items_v", "held_reg"}: the evaluation context of `checkpoint_ee` (held_reg = (x, u, z, dt, draw) of every held-out
    record with a true state, registered into TRUE-STATE models before they encode, as calibrate.py registers them; None without
    truth). With draws required, a held-out record with a true state but no draw is an error."""
    from .harness import verdict_items
    held_reg = None
    if with_truth:
        held = inputs["heldout"]
        hz, hd = _truth_of(truth_dir, [rr["key"] for rr in held.rows])
        if draw_required:
            lacking = [k for k in hz if k not in hd]
            if lacking:
                raise RuntimeError(f"the tier's truth carries draws but {len(lacking)} of {len(hz)} held-out records with a true state "
                                   "have none")
        held_reg = []
        for rr in held.rows:
            if rr["key"] in hz:
                r = held.load(rr)
                held_reg.append((np.asarray(r.x), np.asarray(r.u), hz[rr["key"]], float(r.protocol["dt"]), hd.get(rr["key"])))
    return {"sysc": inputs["system"], "items_v": verdict_items(inputs["items"]), "held_reg": held_reg}


def evaluate_checkpoint(model, learner: str, ectx: dict, *, n_boot: int = N_BOOT_EE, draw_required: bool = False) -> dict:
    """Register the held-out truth with each history's dt and draw (TRUE-STATE) and score one checkpoint model (`checkpoint_ee`).
    TRUE-STATE rows record draw_required, draw_context, draw_context_reason (None with the context; CONSTANT_DRAWS when the fit's
    training draws were constant, from `check_draw_context`; NO_DRAWS on a tier without draws), training_draws, n_registered_without_draw,
    n_probe_encodes and the static_context note; with draws required, a registration without a draw is an error."""
    if learner == "true_state":
        for x, u, z, dt, draw in ectx["held_reg"] or []:
            model.register_truth(x, u, z, dt, draw)
    out = checkpoint_ee(model, ectx["sysc"], ectx["items_v"], n_boot=n_boot, seed=0)
    if learner == "true_state":
        inf = model.info() or {}
        chk = getattr(model, "mde_draw_check", None) or {}
        on = bool(inf.get("draw_context"))
        out.update({"draw_required": bool(draw_required), "draw_context": on,
                    "draw_context_reason": None if on else (chk.get("reason") if draw_required else NO_DRAWS),
                    "training_draws": chk.get("training_draws"),
                    "n_registered_without_draw": int(inf.get("n_registered_without_draw") or 0),
                    "n_probe_encodes": int(inf.get("n_probe_encodes") or 0),
                    "static_context": (getattr(model, "fit_notes", None) or {}).get("static_context")})
        if draw_required and out["n_registered_without_draw"]:
            raise RuntimeError(f"{out['n_registered_without_draw']} held-out histories registered without their draw although the "
                               "tier's truth carries draws")
    return out


def _row_base(job: dict, cp: dict) -> dict:
    return {"system": job["sid"], "learner": job["learner"], "designer": job["designer"], "loop_seed": int(job["seed"]),
            "budget": int(cp["budget"]), "spent": cp.get("spent"), "n_records": cp.get("n_records"), "experiments": cp.get("experiments"),
            "trajectories": cp.get("trajectories")}


def _checkpoint_meta(entry: dict) -> dict:
    led = entry.get("ledger") or {}
    return {"budget": int(entry["budget"]), "spent": entry.get("spent"), "n_records": entry.get("n_records"),
            "experiments": led.get("experiments"), "trajectories": led.get("trajectories")}


def _loop_info(rec: dict, n_d0: int) -> dict:
    loop = {k: rec.get(k) for k in ("refused", "sim_errors", "stopped_early", "rounds", "spent", "magnitude_budget")}
    loop["refusals_tail"] = (rec.get("refusals") or [])[-5:]
    loop["n_d0"] = n_d0
    return loop


# ================================================================================================================ unpacked (one loop)
def reference_loop_job(job: dict) -> dict:
    """One experiment loop of a reference learner and its evaluated checkpoints, fits INSIDE the loop (the unpacked reference of the
    packed path). job: {"sid", "learner", "designer", "seed", "budget", ["checkpoints"], ["batch"], the system-context keys of
    `harness.system_context` ("heldout_root", "heldout_tier", "public_root", "public_tier", "internal_path", "store_root",
    ["store_read_roots"], "generator"), ["n_boot"], ["learner_cfg"] (LearnerConfig overrides)}. Returns {"rows": [...], "loop": {...},
    "wall_s"}: one row per checkpoint {"system", "learner", "designer", "loop_seed", "budget", "EE", ...}; a failed checkpoint
    evaluation is a row with EE NaN and its error (charged downstream, never dropped)."""
    from . import designers as _designers  # noqa: F401 - registers the reference designers
    from .api import get_designer
    from .harness import system_context
    from .loop import CHECKPOINTS, DirectSim, run_loop
    from .refs import LearnerConfig
    t0 = time.time()
    sid, lname, dname, seed = job["sid"], job["learner"], job["designer"], int(job["seed"])
    inputs, internal, ctx, truth_obj = system_context(job)
    check_generator(internal, truth_obj)
    sysrec, d0 = load_d0(job)
    truth_dir = inputs.get("truth_dir")
    truth_z = truth_draw = None
    draw_req = False
    sim_ctx = ctx
    if lname == "true_state":
        truth_z, truth_draw, draw_req, sim_ctx = _loop_truth(job, ctx, d0)
    cfg = LearnerConfig(**(job.get("learner_cfg") or {}))
    learner = ReferenceLearner(lname, sid, sysrec, truth_z=truth_z, truth_draw=truth_draw, draw_required=draw_req, cfg=cfg)
    sim = DirectSim(sim_ctx, known=d0)
    cps = tuple(int(x) for x in job.get("checkpoints") or CHECKPOINTS)
    rec = run_loop(learner, get_designer(dname), sid, sysrec, d0, sim, budget=int(job["budget"]), checkpoints=cps,
                   batch=int(job.get("batch", 5)), seed=seed, out_dir=None, designer_name=dname)
    if draw_req:
        _check_loop_draws(rec["data"], truth_draw)
    ectx = eval_context_from_inputs(inputs, truth_dir, lname == "true_state", draw_req)
    rows = []
    for e in rec["checkpoints"]:
        b = int(e["budget"])
        row = _row_base(job, _checkpoint_meta(e))
        lazy = rec["models"].get(b)
        te = time.time()
        try:
            model = lazy.materialize() if isinstance(lazy, LazyReference) else lazy
            row["fit_cpu_s"] = getattr(lazy, "fit_s", None)
            row.update(evaluate_checkpoint(model, lname, ectx, n_boot=int(job.get("n_boot", N_BOOT_EE)), draw_required=draw_req))
        except Exception as exc:  # noqa: BLE001 - a failed checkpoint is a row with EE NaN (charged downstream, never dropped)
            row.update({"EE": float("nan"), "error": f"{type(exc).__name__}: {exc}"[:500], "traceback": traceback.format_exc()[-2000:]})
            if lname == "true_state":
                row["draw_required"] = draw_req
        row["eval_wall_s"] = round(time.time() - te, 2)
        rec["models"][b] = None                      # free the checkpoint model (and its registered histories)
        rows.append(row)
    loop = _loop_info(rec, len(d0))
    loop["n_fits"] = learner.n_fits
    loop["n_verdict_items"] = len(ectx["items_v"])
    return {"rows": rows, "loop": loop, "wall_s": round(time.time() - t0, 1)}


# ================================================================================================================ packed (several loops)
def loop_id(job: dict) -> str:
    return f"{job['sid']}|{job['learner']}|{job['designer']}|s{int(job['seed'])}"


def planned_budgets(job: dict) -> list[int]:
    """The checkpoints run_loop will record for the job (its checkpoints up to the budget, plus the budget itself)."""
    from .loop import CHECKPOINTS
    b = int(job["budget"])
    return sorted({int(c) for c in (job.get("checkpoints") or CHECKPOINTS) if int(c) <= b} | {b})


def stream_id(job: dict) -> str:
    """The DATA STREAM of a loop: its system, designer, seed and loop settings. Loops of one stream (the two learners) run identical
    experiments (the designers never query the model), so phase 1 runs once per stream (`reference_pack_job`)."""
    cps = ",".join(str(c) for c in planned_budgets(job))
    return f"{job['sid']}|{job['designer']}|s{int(job['seed'])}|b{int(job['budget'])}|{cps}|n{int(job.get('batch', 5))}"


def loop_phase1(job: dict, work_dir: str, capture_truth: bool | None = None) -> dict:
    """Phase 1 of one loop or stream (module docstring, PACKING): run_loop with the fits deferred; the loop's data, the true states
    (captured when `capture_truth`, default: a TRUE-STATE job) and the system record are pickled under work_dir; the loop's own
    simulation store is removed afterwards. Returns {"loop_id", "path", "checkpoints": [{"budget", "n_records", "spent",
    "experiments", "trajectories"}], "loop", "wall_s"}."""
    from . import designers as _designers  # noqa: F401 - registers the reference designers
    from .api import get_designer
    from .loop import DirectSim, run_loop
    t0 = time.time()
    sid, lname, dname, seed = job["sid"], job["learner"], job["designer"], int(job["seed"])
    capture = (lname == "true_state") if capture_truth is None else bool(capture_truth)
    _internal, ctx, _truth_obj = sim_context(job)
    sysrec, d0 = load_d0(job)
    truth_z = truth_draw = None
    draw_req = False
    sim_ctx = ctx
    if capture:
        truth_z, truth_draw, draw_req, sim_ctx = _loop_truth(job, ctx, d0)
    sim = DirectSim(sim_ctx, known=d0)
    rec = run_loop(DeferredLearner(), get_designer(dname), sid, sysrec, d0, sim, budget=int(job["budget"]),
                   checkpoints=tuple(planned_budgets(job)), batch=int(job.get("batch", 5)), seed=seed, out_dir=None, designer_name=dname)
    data = rec["data"]
    if draw_req:
        _check_loop_draws(data, truth_draw)
    path = Path(work_dir) / (hashlib.sha256(stream_id(job).encode()).hexdigest()[:24] + ".pkl")
    tz = None if truth_z is None else {r.key: truth_z[r.key] for r in data if r.key in truth_z}
    tdr = None if truth_draw is None else {r.key: truth_draw[r.key] for r in data if r.key in truth_draw}
    with open(path, "wb") as fh:
        pickle.dump({"records": data, "truth_z": tz, "truth_draw": tdr, "draw_required": draw_req, "sysrec": sysrec}, fh,
                    protocol=pickle.HIGHEST_PROTOCOL)
    if job.get("store_root") and job.get("drop_store", True):
        shutil.rmtree(job["store_root"], ignore_errors=True)
    return {"loop_id": loop_id(job), "path": str(path), "checkpoints": [_checkpoint_meta(e) for e in rec["checkpoints"]],
            "loop": _loop_info(rec, len(d0)), "wall_s": round(time.time() - t0, 1)}


class ProgressStore:
    """Durable per-task results of a pack (module docstring, PACKING): Modal preempts containers and re-runs the SAME input, so a
    restarted pack reads the rows its tasks already produced and runs only the rest. spec {"dict": name, "run": id} (a modal.Dict)
    or {"dir": path, "run": id} (a local directory; tests); no spec = no persistence. A store that cannot be reached is recorded
    (`error`) and the pack runs without it."""

    def __init__(self, spec: dict | None):
        self.spec = dict(spec or {})
        self.run = str(self.spec.get("run", ""))
        self.kind, self.error, self._d = None, None, None
        if not spec:
            return
        try:
            if spec.get("dict"):
                import modal
                self._d = modal.Dict.from_name(str(spec["dict"]), create_if_missing=True)
                self.kind = "modal.Dict"
            elif spec.get("dir"):
                self._d = Path(spec["dir"])
                self._d.mkdir(parents=True, exist_ok=True)
                self.kind = "dir"
        except Exception as exc:  # noqa: BLE001 - the pack still runs (without resume)
            self.kind, self.error = None, f"{type(exc).__name__}: {exc}"[:300]

    def key(self, loop: str, budget: int) -> str:
        return f"{self.run}|{loop}|{int(budget)}"

    def _file(self, k: str) -> Path:
        return self._d / (hashlib.sha256(k.encode()).hexdigest() + ".json")

    def get(self, loop: str, budget: int) -> dict | None:
        if self.kind is None:
            return None
        k = self.key(loop, budget)
        try:
            if self.kind == "dir":
                f = self._file(k)
                return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
            return self._d.get(k)
        except Exception as exc:  # noqa: BLE001 - treated as not done
            self.error = f"get: {type(exc).__name__}: {exc}"[:300]
            return None

    def put(self, loop: str, budget: int, row: dict) -> None:
        if self.kind is None:
            return
        k = self.key(loop, budget)
        try:
            if self.kind == "dir":
                f = self._file(k)
                tmp = f.with_suffix(f".{os.getpid()}.tmp")
                tmp.write_text(json.dumps(row, default=str), encoding="utf-8")
                os.replace(tmp, f)
            else:
                self._d.put(k, row)
        except Exception as exc:  # noqa: BLE001 - the row is still returned by the pack
            self.error = f"put: {type(exc).__name__}: {exc}"[:300]


_ECTX: OrderedDict = OrderedDict()           # per worker process: the last evaluation contexts (LRU, `_ECTX_MAX` systems)
_ECTX_MAX = 2


def _eval_context_cached(job: dict, with_truth: bool, draw_required: bool = False) -> dict:
    from . import suites as SU
    key = (job["sid"], job["heldout_root"], job["heldout_tier"], job.get("public_root"), job.get("part", "eval"))
    ent = _ECTX.get(key)
    if ent is None or (with_truth and ent["held_reg"] is None):
        held, pubd = _tiers(job)
        inputs = SU.load_eval_inputs(job["sid"], heldout_dirs=held, public_dirs=pubd, part=job.get("part", "eval"))
        tdir = held["truth"] / SU._safe(job["sid"])
        ent = eval_context_from_inputs(inputs, tdir if tdir.exists() else None, with_truth, draw_required)
        _ECTX[key] = ent
        while len(_ECTX) > _ECTX_MAX:
            _ECTX.popitem(last=False)
    _ECTX.move_to_end(key)
    return ent


def _rss_kib() -> int | None:
    """This process's resident set (Linux /proc/self/status VmRSS, KiB); None where unavailable."""
    try:
        with open("/proc/self/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except OSError:
        pass
    return None


class RssPeak:
    """Peak resident set of this process while a block runs, sampled every `period` s (the peak counters cannot be reset in every
    sandbox, e.g. Modal's). `gib` is None where /proc is unavailable."""

    def __init__(self, period: float = 0.2):
        import threading
        self.period, self.peak, self._stop = period, 0, threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self.gib = None

    def _loop(self):
        while not self._stop.is_set():
            v = _rss_kib()
            if v is not None:
                self.peak = max(self.peak, v)
            self._stop.wait(self.period)

    def __enter__(self):
        if _rss_kib() is not None:
            self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join()
            v = _rss_kib()
            self.peak = max(self.peak, v or 0)
            self.gib = round(self.peak / 1024 ** 2, 3)
        return False


def checkpoint_task(task: dict) -> dict:
    """Phase 2 task (module docstring, PACKING): fit the reference on the loop's first n_records records and evaluate it. task:
    {"job", "path", "checkpoint" (phase 1's meta), ["n_boot"]}. Returns the checkpoint row (the fields of `reference_loop_job`'s rows
    plus task timings and the task's peak memory)."""
    from .refs import LearnerConfig
    t0 = time.perf_counter()
    if task.get("crash_for_test") and int(task.get("attempt", 0)) < int(task["crash_for_test"]):
        os._exit(3)                                  # tests of the crashed-pool path only (a worker killed mid-task)
    job, cp = task["job"], task["checkpoint"]
    row = _row_base(job, cp)
    mem = RssPeak().__enter__()
    try:
        with open(task["path"], "rb") as fh:
            blob = pickle.load(fh)
        records = blob["records"][: int(cp["n_records"])]
        draw_req = bool(blob.get("draw_required"))
        if job["learner"] == "true_state":
            row["draw_required"] = draw_req
        learner = ReferenceLearner(job["learner"], job["sid"], blob["sysrec"], truth_z=blob.get("truth_z"), truth_draw=blob.get("truth_draw"),
                                   draw_required=draw_req, cfg=LearnerConfig(**(job.get("learner_cfg") or {})))
        del blob
        c0, w0 = time.process_time(), time.perf_counter()
        model = learner.fit_now(records, int(job["seed"]))
        row["fit_cpu_s"] = round(time.process_time() - c0, 3)
        row["fit_wall_s"] = round(time.perf_counter() - w0, 2)
        del records
        te = time.perf_counter()
        ectx = _eval_context_cached(job, job["learner"] == "true_state", draw_req)
        row["eval_ctx_s"] = round(time.perf_counter() - te, 2)
        te = time.perf_counter()
        row.update(evaluate_checkpoint(model, job["learner"], ectx, n_boot=int(task.get("n_boot") or job.get("n_boot", N_BOOT_EE)),
                                       draw_required=draw_req))
        row["eval_wall_s"] = round(time.perf_counter() - te, 2)
    except Exception as exc:  # noqa: BLE001 - a failed checkpoint is a row with EE NaN (charged downstream, never dropped)
        row.update({"EE": float("nan"), "error": f"{type(exc).__name__}: {exc}"[:500], "traceback": traceback.format_exc()[-2000:]})
    mem.__exit__(None, None, None)
    row["task_wall_s"] = round(time.perf_counter() - t0, 2)
    row["peak_gb"] = mem.gib                         # the task's peak resident set (GiB; sampled), incl. the worker's cached contexts
    row["worker_pid"] = os.getpid()
    return row


def pool_init(threads: int) -> None:
    """Worker initializer: the thread settings of `p4modal.jobproc` (BLAS pools and torch), so a packed task runs exactly as an
    unpacked job with the same thread count."""
    n = int(threads)
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[var] = str(n)
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(n)
    except Exception:  # noqa: BLE001, S110 - the environment variables still apply
        pass
    try:
        import torch
        torch.set_num_threads(n)
    except Exception:  # noqa: BLE001, S110 - no torch: nothing to limit
        pass


def _sched_key(t: dict) -> tuple:
    return (0 if t.get("kind") == "phase1" else 1, -float(t["pred_s"]), -float(t["pred_gb"]))


def schedule(tasks: list[dict], submit, wait_any, *, slots: int, mem_budget_gb: float, is_fatal=lambda res: False,
             on_done=None) -> tuple[list[tuple[dict, object]], list[dict]]:
    """Memory-aware list scheduling with released work (module docstring, PACKING). tasks: dicts with "pred_s" and "pred_gb" (and
    "kind": "phase1" for jobs that release others; they go first); submit(task) -> handle; wait_any(handles) -> (done handles,
    {handle: exception or result}); on_done(task, result) -> new tasks now eligible (e.g. a stream's checkpoint tasks once its phase
    1 is done). Among the eligible tasks the phase-1 jobs first, then the longest predicted; a task is admitted only while the running
    tasks' predicted memory plus its own fits `mem_budget_gb` (with nothing running, the smallest waiting task runs even over the
    budget). After a result for which is_fatal(result) holds (a broken pool) nothing more is submitted or released; the running
    tasks are drained. Returns ([(task, result or exception)] in completion order, the tasks never submitted)."""
    pending = sorted(tasks, key=_sched_key)
    running: dict = {}
    mem = 0.0
    out = []
    fatal = False
    while (pending and not fatal) or running:
        while not fatal and len(running) < slots and pending:
            pick = next((t_ for t_ in pending if mem + float(t_["pred_gb"]) <= mem_budget_gb), None)
            if pick is None:
                if running:
                    break
                pick = min(pending, key=lambda t_: float(t_["pred_gb"]))
            pending.remove(pick)
            running[submit(pick)] = pick
            mem += float(pick["pred_gb"])
        if not running:
            break
        done, results = wait_any(list(running))
        for h in done:
            t_ = running.pop(h)
            mem -= float(t_["pred_gb"])
            out.append((t_, results[h]))
            if is_fatal(results[h]):
                fatal = True
            elif on_done is not None and not fatal:
                new = on_done(t_, results[h]) or []
                if new:
                    pending = sorted(pending + list(new), key=_sched_key)
    return out, (pending if fatal else [])


def reference_pack_job(pack: dict) -> dict:
    """Several loops in one container (module docstring, PACKING). pack: {"loops": [loop jobs, each with "pred": {"s0", "s1", "g0",
    "g1", "n_obs", "rows"} (the planner's cost model: seconds = s0 + s1 x n_obs, GiB = g0 + g1 x the float64 size in GiB of the
    task's n_records x rows x n_obs table)], "workers", "threads", "mem_budget_gb" (GiB), ["work_dir"], ["n_boot"], ["progress"]
    (`ProgressStore` spec)}. Phase 1 runs once per data stream (`stream_id`: the loops of both learners share it; the true states
    are captured when any of them is a TRUE-STATE loop), only for streams with a task not yet in the progress store, and on the SAME
    pool as the tasks (`schedule`): a stream's tasks become eligible the moment its own phase 1 ends (no barrier behind the slowest
    simulation). Returns {"rows", "loops", "pack"}: every checkpoint row (errors included; rows read back from the progress store
    carry "resumed": True), per loop its stream's phase-1 record (or its error), and the pack's timings."""
    import multiprocessing as mp
    from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
    from concurrent.futures.process import BrokenProcessPool
    t0 = time.time()
    P, T = int(pack["workers"]), int(pack["threads"])
    budget = float(pack.get("mem_budget_gb") or 1e12)
    work = Path(pack["work_dir"]) if pack.get("work_dir") else Path(tempfile.mkdtemp(prefix="p4mde_"))
    work.mkdir(parents=True, exist_ok=True)
    store = ProgressStore(pack.get("progress"))
    mpc = mp.get_context("spawn")

    def new_pool():
        return ProcessPoolExecutor(max_workers=P, mp_context=mpc, initializer=pool_init, initargs=(T,))
    loops_out, rows = [], []
    n_crash_retries = n_resumed = 0
    streams: dict[str, list[dict]] = {}
    for job in pack["loops"]:
        todo = False
        for b_ in planned_budgets(job):
            r = store.get(loop_id(job), b_)
            if r is None:
                todo = True
            else:
                rows.append({**r, "resumed": True})
                n_resumed += 1
        if todo:
            streams.setdefault(stream_id(job), []).append(job)
        else:
            loops_out.append({"loop_id": loop_id(job), "stream": stream_id(job), "resumed": "every checkpoint row from the progress store"})
    done_keys = {(r["system"], r["learner"], r["designer"], int(r["loop_seed"]), int(r["budget"])) for r in rows}
    p1_wall: dict[str, float] = {}
    first_task_start: list[float] = []

    def phase1_task(sid_: str) -> dict:
        grp = streams[sid_]
        n_obs = float((grp[0].get("pred") or {}).get("n_obs", 0))
        return {"kind": "phase1", "stream": sid_, "attempt": 0, "pred_s": 1e6 + n_obs, "pred_gb": 1.0}

    def release(task: dict, res) -> list[dict]:
        if task.get("kind") != "phase1":
            return []
        sid_ = task["stream"]
        if isinstance(res, BaseException):
            err = {"error": f"{type(res).__name__}: {res}"[:800]}
            for job in streams[sid_]:
                loops_out.append({"loop_id": loop_id(job), "stream": sid_, **err})
            return []
        p1_wall[sid_] = float(res.get("wall_s") or 0.0)
        meta = {k: v for k, v in res.items() if k not in ("path", "loop_id")}
        new = []
        for job in streams[sid_]:
            loops_out.append({"loop_id": loop_id(job), "stream": sid_, **meta})
            pr = job.get("pred") or {}
            for cp in res["checkpoints"]:
                if (job["sid"], job["learner"], job["designer"], int(job["seed"]), int(cp["budget"])) in done_keys:
                    continue
                size_gb = float(cp["n_records"] or 0) * float(pr.get("rows", 0)) * float(pr.get("n_obs", 0)) * 8.0 / 2 ** 30
                new.append({"kind": "task", "job": job, "path": res["path"], "checkpoint": cp, "n_boot": pack.get("n_boot"), "attempt": 0,
                            "crash_for_test": (job.get("crash_for_test") or {}).get(str(cp["budget"])),
                            "pred_s": float(pr.get("s0", 1.0)) + float(pr.get("s1", 0.0)) * float(pr.get("n_obs", 0)),
                            "pred_gb": float(pr.get("g0", 0.0)) + float(pr.get("g1", 0.0)) * size_gb})
        return new

    def finish(task, row):
        rows.append(row)
        store.put(loop_id(task["job"]), int(task["checkpoint"]["budget"]), row)
    ex = new_pool() if streams else None
    tasks = [phase1_task(s_) for s_ in streams]
    try:
        while tasks:
            lost = []
            pool_now = ex

            def submit(task, pool_now=pool_now):
                try:
                    if task.get("kind") == "phase1":
                        grp = streams[task["stream"]]
                        return pool_now.submit(loop_phase1, grp[0], str(work), any(j["learner"] == "true_state" for j in grp))
                    if not first_task_start:
                        first_task_start.append(time.time())
                    return pool_now.submit(checkpoint_task, task)
                except BrokenProcessPool as exc:        # the pool broke between two results: this task never started
                    f = Future()
                    f.set_exception(exc)
                    task["_not_started"] = True
                    return f

            def wait_any(handles):
                done, _ = wait(handles, return_when=FIRST_COMPLETED)
                res = {}
                for h in done:
                    try:
                        res[h] = h.result()
                    except BaseException as exc:  # noqa: BLE001 - reported per task below
                        res[h] = exc
                return done, res
            done_list, unsubmitted = schedule(tasks, submit, wait_any, slots=P, mem_budget_gb=budget,
                                              is_fatal=lambda r: isinstance(r, BrokenProcessPool), on_done=release)
            tasks = list(unsubmitted)
            for task, res in done_list:
                if isinstance(res, BrokenProcessPool):
                    if task.pop("_not_started", False):
                        tasks.append(task)
                    else:
                        lost.append(task)
                elif task.get("kind") == "phase1":
                    continue                           # handled by release()
                elif isinstance(res, BaseException):
                    finish(task, {**_row_base(task["job"], task["checkpoint"]), "EE": float("nan"),
                                  "error": f"{type(res).__name__}: {res}"[:500]})
                else:
                    finish(task, res)
            if lost or tasks:                          # a crashed pool (e.g. a worker killed for memory): rebuild, retry once
                ex.shutdown(wait=False, cancel_futures=True)
                ex = new_pool()
                for task in lost:
                    if task["attempt"] >= 1:
                        if task.get("kind") == "phase1":
                            release(task, RuntimeError("worker process crashed twice during phase 1 (memory?)"))
                        else:
                            finish(task, {**_row_base(task["job"], task["checkpoint"]), "EE": float("nan"),
                                          "error": "worker process crashed twice (memory?)"})
                    else:
                        n_crash_retries += 1
                        tasks.append(dict(task, attempt=1, pred_gb=2.0 * float(task["pred_gb"])))
    finally:
        if ex is not None:
            ex.shutdown(wait=True, cancel_futures=True)
        shutil.rmtree(work, ignore_errors=True)
    t2 = time.time()
    return {"rows": rows, "loops": loops_out,
            "pack": {"workers": P, "threads": T, "mem_budget_gb": budget, "n_loops": len(pack["loops"]), "n_streams_run": len(streams),
                     "n_rows": len(rows), "n_resumed_rows": n_resumed, "progress": store.kind, "progress_error": store.error,
                     "phase1_wall_s": p1_wall, "first_task_after_s": round(first_task_start[0] - t0, 1) if first_task_start else None,
                     "wall_s": round(t2 - t0, 1), "crash_retries": n_crash_retries, "cpu_count": os.cpu_count()}}


def draw_preflight(job: dict) -> dict:
    """Before the run (the driver calls it for every system with TRUE-STATE loops): whether the tier's truth carries the effective
    draws for the system's D0 records and for its held-out records with a true state, and whether the container's generator system
    provides `draw_effective` (the draws of the loop's new trajectories); with D0's draws, their length and how many coordinates vary
    over D0 (refs' criterion for a kept static coordinate). Reads index rows and truth files only (no arrays of the records); checks
    the generator hash (`sim_context`)."""
    from . import suites as SU
    from .data import ExperimentSet
    _internal, _ctx, truth_obj = sim_context(job)
    _es, rows = _d0_rows(job)
    tdir = _truth_dir(job)
    d0_keys = [r["key"] for r in rows]
    held, _pubd = _tiers(job)
    hdir = held[job.get("part", "eval")] / SU._safe(job["sid"])
    hkeys = [r["key"] for r in ExperimentSet.load(hdir, lazy=True).rows] if (hdir / "index.jsonl").exists() else []

    def scan(keys, keep_draws):
        n_z = n_draw = 0
        draws = []
        for k in keys:
            f = (tdir / "traj" / f"{k}.npz") if tdir is not None else None
            if f is not None and f.exists():
                with np.load(f) as a:
                    n_z += int("z" in a.files)
                    if "draw" in a.files:
                        n_draw += 1
                        if keep_draws:
                            draws.append(np.asarray(a["draw"], np.float64).reshape(-1))
        return n_z, n_draw, draws
    nz0, nd0, dr0 = scan(d0_keys, True)
    nzh, ndh, _ = scan(hkeys, False)
    dv = draw_variation(dr0)
    return {"sid": job["sid"], "n_d0": len(d0_keys), "n_d0_with_z": nz0, "n_d0_with_draw": nd0, "d0_draw_sizes": dv["sizes"],
            "d0_draw_finite": dv["finite"], "d0_draw_varying": dv["varying"], "n_held": len(hkeys), "n_held_with_z": nzh,
            "n_held_with_draw": ndh, "generator_draws": bool(truth_obj is not None and hasattr(truth_obj, "draw_effective"))}


def draw_verdict(pre: list[dict], *, allow_no_draw: bool) -> dict:
    """The run's draw decision from `draw_preflight` results: {"ok", "draws": bool, "why", "systems": {sid: reason}, "warnings":
    {sid: note}}. With draws in the tier's truth, every system must have them for all its D0 records and all its held-out records with
    a true state, D0's draws must have one length and finite values, and its generator must provide draw_effective; without any
    draws the run is refused unless `allow_no_draw` (smoke tiers without draws: TRUE-STATE is then z alone, with its error floor). A
    system whose draws are constant over D0 is a note only: a fit whose training draws are all constant legitimately runs without
    the context (CONSTANT_DRAWS, `check_draw_context`)."""
    draws = any(int(p.get("n_d0_with_draw") or 0) > 0 or int(p.get("n_held_with_draw") or 0) > 0 for p in pre)
    bad: dict[str, str] = {}
    warn: dict[str, str] = {}
    for p in pre:
        if p.get("error"):
            bad[p.get("sid", "?")] = f"preflight failed: {p['error']}"[:300]
            continue
        if draws:
            why = []
            if p["n_d0_with_draw"] != p["n_d0"]:
                why.append(f"D0 draws {p['n_d0_with_draw']} of {p['n_d0']}")
            if len(p.get("d0_draw_sizes") or [0]) > 1:
                why.append(f"D0 draws of different lengths {p['d0_draw_sizes']}")
            if p.get("d0_draw_finite") is False:
                why.append("a non-finite D0 draw")
            if p["n_held_with_draw"] != p["n_held_with_z"]:
                why.append(f"held-out draws {p['n_held_with_draw']} of {p['n_held_with_z']} records with a true state")
            if not p["generator_draws"]:
                why.append("the generator provides no draw_effective (new loop trajectories would have no draw)")
            if why:
                bad[p["sid"]] = "; ".join(why)
            elif p.get("d0_draw_varying") == 0:
                warn[p["sid"]] = (f"all {p['d0_draw_sizes'][0]} draw coordinates constant over D0 (fits on constant draws run without "
                                  "the context: CONSTANT_DRAWS)")
    if bad:
        return {"ok": False, "draws": draws, "why": f"{len(bad)} systems fail the draw preflight", "systems": bad, "warnings": warn}
    if not draws and not allow_no_draw:
        return {"ok": False, "draws": False, "systems": {}, "warnings": warn,
                "why": "the tier's truth carries no effective draws: TRUE-STATE would be z alone (an error floor); the final tier must "
                       "carry truth['draw'] (--allow-no-draw for smoke runs)"}
    return {"ok": True, "draws": draws, "why": None, "systems": {}, "warnings": warn}


def draw_violations(rows: list[dict], loops: list[dict] | None = None) -> list[str]:
    """After the run: the TRUE-STATE rows and loops that break the draw rule (module docstring, DRAW CONTEXT): a fit without the draw
    context (unless its training draws were constant, CONSTANT_DRAWS) or a registration without a draw while draws are required, and
    every error that names the draws."""
    out = []
    for r in rows:
        if r.get("learner") != "true_state":
            continue
        tag = f"{r.get('system')}|{r.get('designer')}|s{r.get('loop_seed')}|b{r.get('budget')}"
        if (r.get("draw_required") and not r.get("error") and not r.get("draw_context")
                and r.get("draw_context_reason") != CONSTANT_DRAWS):
            out.append(f"{tag}: fit without draw context")
        if r.get("draw_required") and int(r.get("n_registered_without_draw") or 0):
            out.append(f"{tag}: {r['n_registered_without_draw']} registrations without draw")
        if "draw" in str(r.get("error") or ""):
            out.append(f"{tag}: {str(r['error'])[:200]}")
    for lp in loops or []:
        if "draw" in str(lp.get("error") or ""):
            out.append(f"{lp.get('loop_id')}: {str(lp['error'])[:200]}")
    return out


def static_reference_ee(job: dict) -> dict:
    """Sanity anchor of the checkpoint EE path: the references fitted on the system's main-comparison data (public D0 + D1 with
    their twins, as the calibration fits them) and NO-EFFECT (EE <= 1 by construction), scored by `checkpoint_ee` on the same verdict
    items. job: the system-context keys of `reference_loop_job` plus ["learner_cfg"]. Returns {"rows": [...]}."""
    from .harness import system_context, verdict_items
    from .refs import LearnerConfig, NoEffectModel, fit_reference
    t0 = time.time()
    sid = job["sid"]
    inputs, _internal, _ctx, _truth_obj = system_context(job)
    pset = inputs["public"]
    train = [pset.load(r) for r in pset.rows if r.get("split") in ("train", "twin")]
    truth_dir = inputs.get("truth_dir")
    tz, tdr = _truth_of(truth_dir, [r.key for r in train])
    draw_req = draw_requirement([r.key for r in train], tdr)
    cfg = LearnerConfig(**(job.get("learner_cfg") or {}))
    items_v = verdict_items(inputs["items"])
    rows = []
    models = {}
    try:
        models["full_state"] = fit_reference("full_state", sid, train, inputs["record"], cfg=cfg)
        models["no_effect"] = NoEffectModel(models["full_state"])
    except Exception as exc:  # noqa: BLE001
        rows.append({"system": sid, "model": "full_state", "error": f"{type(exc).__name__}: {exc}"[:500]})
    if len(tz) == len(train):
        try:
            models["true_state"] = fit_reference("true_state", sid, train, inputs["record"],
                                                 truth={"z": tz, "draw": tdr if draw_req else None}, cfg=cfg)
            if draw_req:
                models["true_state"].mde_draw_check = check_draw_context(models["true_state"], [tdr[r.key] for r in train])
            held = inputs["heldout"]
            hz, hd = _truth_of(truth_dir, [rr["key"] for rr in held.rows])
            for rr in held.rows:
                if rr["key"] in hz:
                    r = held.load(rr)
                    models["true_state"].register_truth(np.asarray(r.x), np.asarray(r.u), hz[rr["key"]], float(r.protocol["dt"]),
                                                        hd.get(rr["key"]))
        except Exception as exc:  # noqa: BLE001
            rows.append({"system": sid, "model": "true_state", "error": f"{type(exc).__name__}: {exc}"[:500]})
    for name, m in models.items():
        te = time.time()
        try:
            on = bool((m.info() or {}).get("draw_context"))
            extra = ({"draw_required": draw_req, "draw_context": on,
                      "draw_context_reason": None if on else ((getattr(m, "mde_draw_check", None) or {}).get("reason") if draw_req
                                                              else NO_DRAWS)} if name == "true_state" else {})
            rows.append({"system": sid, "model": name, "n_train": len(train), **extra, **checkpoint_ee(m, inputs["system"], items_v),
                         "eval_wall_s": round(time.time() - te, 1)})
        except Exception as exc:  # noqa: BLE001
            rows.append({"system": sid, "model": name, "error": f"{type(exc).__name__}: {exc}"[:500]})
    return {"rows": rows, "wall_s": round(time.time() - t0, 1)}


# ================================================================================================================ the MDE (summary)
def exclusions(rows: list[dict], designers=("random", "fixed")) -> dict[str, str]:
    """{system: reason} of the systems `loop.mde_by_simulation` leaves out: a cell of a benchmark designer charged by
    `loop.checkpoint_grid` (a missing loop, a failed evaluation, or a missing budget before the first checkpoint)."""
    from .loop import checkpoint_grid
    present = [d for d in designers if any(r["designer"] == d for r in rows)]
    _grid, counts = checkpoint_grid(rows, "EE", present)
    out: dict[str, str] = {}
    for k, n in sorted(counts["by_pair"].items()):
        s, d = k.split("|", 1)
        out[s] = (out.get(s, "") + "; " if s in out else "") + f"{d}: {n} charged cells"
    return out


def _mde_scenario(arg: tuple) -> dict:
    rows, kw = arg
    from .loop import mde_by_simulation
    return mde_by_simulation(rows, **kw)


def summary_specs(rows: list[dict], *, n_sim: int = 1000, n_boot: int = 1000, seed: int = 0, efficiencies=EFFICIENCIES,
                  null_fixed_offsets=NULL_FIXED_OFFSETS, power: float = 0.8, n_seeds: int = 3, chunk: int = MDE_CHUNK) -> list[dict]:
    """The summary as independent calls of `loop.mde_by_simulation` (for any number of processes or containers): per learner, per
    scenario s (the efficiencies in order, then the weaker-fixed nulls) and per chunk c of at most `chunk` simulated suites, the
    call's keyword arguments with seed = seed + SCENARIO_SEED_STRIDE x (s + 1) + CHUNK_SEED_STRIDE x c (independent random streams;
    the strides make every (s, c) seed distinct and keep each chunk's bootstrap seeds seed .. seed + chunk - 1 disjoint)."""
    base = {"metric": "EE", "ref": "random", "fixed": "fixed", "n_boot": int(n_boot), "n_seeds": int(n_seeds), "power": float(power)}
    effs, nulls = [float(e) for e in efficiencies], [float(o) for o in null_fixed_offsets]
    scen = [("e", e) for e in effs] + [("null", o) for o in nulls]
    out = []
    for ln in sorted({r["learner"] for r in rows}):
        for s, (kind, v) in enumerate(scen):
            for c in range((int(n_sim) + chunk - 1) // chunk):
                n_c = min(chunk, int(n_sim) - c * chunk)
                kw = {**base, "n_sim": n_c, "seed": int(seed) + SCENARIO_SEED_STRIDE * (s + 1) + CHUNK_SEED_STRIDE * c,
                      "efficiencies": (v,) if kind == "e" else (), "null_fixed_offsets": (v,) if kind == "null" else ()}
                out.append({"id": f"{ln}|{s}|{c}", "learner": ln, "scenario": s, "kind": kind, "value": v, "chunk": c, "kw": kw})
    return out


def summary_parts(rows: list[dict], specs: list[dict], workers: int = 1) -> dict[str, dict]:
    """{spec id: mde_by_simulation result} of the specs (a spawned process pool of `workers` processes)."""
    by_l: dict[str, list[dict]] = {}
    for r in rows:
        by_l.setdefault(r["learner"], []).append(r)
    args = [(by_l[sp["learner"]], sp["kw"]) for sp in specs]
    if workers > 1 and len(args) > 1:
        import multiprocessing as mp
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=min(int(workers), len(args)), mp_context=mp.get_context("spawn")) as pool:
            res = list(pool.map(_mde_scenario, args))
    else:
        res = [_mde_scenario(a_) for a_ in args]
    return {sp["id"]: r for sp, r in zip(specs, res, strict=True)}


def summary_parts_job(payload: dict) -> dict:
    """Container target: payload {"rows", "specs", "workers"} -> `summary_parts`."""
    return summary_parts(payload["rows"], payload["specs"], int(payload.get("workers") or 1))


def summarize_from_parts(rows: list[dict], specs: list[dict], parts: dict[str, dict], *, n_sim: int, n_boot: int, seed: int = 0,
                         efficiencies=EFFICIENCIES, null_fixed_offsets=NULL_FIXED_OFFSETS, power: float = 0.8, n_seeds: int = 3) -> dict:
    """Per learner: the chunks of every scenario merged (each rate is a mean over simulated suites, so the merged rate is the chunks'
    rates weighted by their sizes, exactly the rate over all the scenario's suites; the descriptive mean estimated ratio is weighted
    the same way), `loop.mde_by_simulation`'s output format and MDE rule (the smallest efficiency > 1 whose power reaches `power`),
    the systems it excluded and why (`exclusions`) and the observed curves (`loop.curves`)."""
    from .loop import RULE_ALPHA, curves
    out: dict = {"alpha_per_rule": RULE_ALPHA, "n_sim": n_sim, "n_boot": n_boot, "power_target": power, "efficiencies": list(efficiencies),
                 "null_fixed_offsets": list(null_fixed_offsets), "chunk": max((sp["kw"]["n_sim"] for sp in specs), default=0),
                 "per_learner": {}}
    effs, nulls = [float(e) for e in efficiencies], [float(o) for o in null_fixed_offsets]
    for ln in sorted({r["learner"] for r in rows}):
        mine = [sp for sp in specs if sp["learner"] == ln]
        table, weaker, first = {}, {}, None
        for s in sorted({sp["scenario"] for sp in mine}):
            chunks = [sp for sp in mine if sp["scenario"] == s]
            res = [parts[sp["id"]] for sp in chunks]
            first = first or res[0]
            w = [sp["kw"]["n_sim"] for sp in chunks]
            kind, v = chunks[0]["kind"], float(chunks[0]["value"])
            rows_c = [(r_["table"][v] if kind == "e" else r_["false_positive_rate_weaker_fixed"][v]) for r_ in res]
            merged = {k: float(np.average([rc[k] for rc in rows_c], weights=w)) for k in ("fixed_budget", "budget_ratio", "either")}
            if kind == "e":
                ratios = [(rc.get("mean_estimated_ratio"), wi) for rc, wi in zip(rows_c, w, strict=True)]
                fin = [(x, wi) for x, wi in ratios if x is not None and np.isfinite(x)]
                merged["mean_estimated_ratio"] = float(np.average([x for x, _ in fin], weights=[wi for _, wi in fin])) if fin else float("nan")
                merged["true_ratio_approx"] = 1.0 / v
                table[v] = merged
            else:
                weaker[v] = merged

        def mde(key: str, table=table):
            ok = [e for e in effs if e > 1.0 and e in table and table[e][key] >= power]
            return float(min(ok)) if ok else None
        rl = [r for r in rows if r["learner"] == ln]
        mm = {"n_systems": first["n_systems"], "n_excluded_systems": first["n_excluded_systems"], "n_sim": int(n_sim),
              "n_seeds": int(n_seeds), "n_boot": int(n_boot), "alpha_per_rule": first["alpha_per_rule"], "power_target": float(power),
              "table": {e: table[e] for e in effs if e in table}, "false_positive_rate": table.get(1.0),
              "false_positive_rate_weaker_fixed": {o: weaker[o] for o in nulls if o in weaker},
              "mde": {k: mde(k) for k in ("fixed_budget", "budget_ratio", "either")},
              "ratio_interpretation": first.get("ratio_interpretation"), "noise_medians": first["noise_medians"],
              "seeding": (f"scenario s (efficiencies in order, then the weaker-fixed nulls), chunk c of <= {out['chunk']} suites: seed {seed} "
                          f"+ {SCENARIO_SEED_STRIDE} x (s + 1) + {CHUNK_SEED_STRIDE} x c")}
        out["per_learner"][ln] = {"mde": mm, "excluded": exclusions(rl), "curves": curves(rl, metric="EE", n_boot=n_boot, seed=seed),
                                  "n_rows": len(rl), "n_systems_with_rows": len({r["system"] for r in rl}),
                                  "n_checkpoint_errors": sum(1 for r in rl if r.get("error"))}
    return json.loads(json.dumps(out, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


def summarize(rows: list[dict], *, n_sim: int = 1000, n_boot: int = 1000, seed: int = 0, efficiencies=EFFICIENCIES,
              null_fixed_offsets=NULL_FIXED_OFFSETS, power: float = 0.8, n_seeds: int = 3, workers: int = 1, chunk: int = MDE_CHUNK) -> dict:
    """The whole summary in this process (`summary_specs` -> `summary_parts` on `workers` processes -> `summarize_from_parts`); the
    driver distributes the same specs over several containers instead. The result does not depend on the process layout."""
    kw = {"n_sim": n_sim, "n_boot": n_boot, "seed": seed, "efficiencies": efficiencies, "null_fixed_offsets": null_fixed_offsets,
          "power": power, "n_seeds": n_seeds}
    specs = summary_specs(rows, chunk=chunk, **kw)
    return summarize_from_parts(rows, specs, summary_parts(rows, specs, workers), **kw)


def summarize_job(payload: dict) -> dict:
    """Container target of the whole summary in one container: payload {"rows", "kwargs"} -> `summarize(rows, **kwargs)`."""
    return summarize(payload["rows"], **(payload.get("kwargs") or {}))
