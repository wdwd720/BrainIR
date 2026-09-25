"""Counterexample search against fitted state models (goal4 sections 52-54, 87; acceptance criterion 37). ORCHESTRATOR SIDE.

A search looks for protocols (initial state, input schedule, interventions) where a fitted state model disagrees most with the
simulator. Objective:
- 'post' (default): the normalised post-event readout error. The model encodes the history at the first event time and rolls out
  under the protocol's inputs and events; the window NMSE is taken against the simulated readout over the horizon.
- 'effect': the counterfactual EFFECT error of family C (goal4 section 52). The predicted effect (rollout with events minus rollout
  without) is compared with the simulated effect (intervened run minus its event-free twin), as sum ||d_pred - d_true||^2 /
  sum ||d_true||^2 (1 = predicting no effect).
Normalisers are the public training readout variances (the evaluator's readout_scale).

Search strategies (each deterministic given (system, strategy, seed); no gradients: simulator and model are black boxes here):
    random      `budget` random protocols: the model's reference error distribution on the protocol domain
    evolve      half random, then (mu, lambda) mutation of the current worst five (evolutionary search)
    structured  a quarter random, then single-target probes swept over the observed neurons (seeded order) at the top of the
                amplitude ranges: kick up / kick down / current up / current down / silencing (structured intervention search)
    bo          two restarts, each with a fixed event structure (kinds, targets, signs, parameter draw) and continuous design
                parameters (event time, amplitudes, durations, second-event offset, stimulus scale and onset) searched by Bayesian
                optimisation: a Gaussian process on the log error, expected improvement over 256 random candidates per step, a
                quarter of each restart's budget as random initialisation
Protocol domain: a stimulus step (scale 0.5-1.5) and 1-2 events. The events are kicks on 1-3 observed neurons (real: 5-30 Hz; synthetic:
1.5-3 public sd of the neuron), current pulses on 1-2 neurons (real 5-40, synthetic 0.5-3, either sign) or silencing of 1-4 neurons.
With --init-state, half of the random protocols also start from a perturbed microstate on 1-5 observed neurons (public training mean +
U(-2, 2) sd; rates clipped at 0 on real systems). Each event records whether it lies inside the public protocol families' ranges
(PROTOCOL.md section 3; the search domain is deliberately wider).
Only event kinds the model supports are drawn. A model that abstains on every kind cannot be searched, and this is reported.

Commands:
    single search (the original interface):
        counterexamples.py --method-dir DIR --model PKL --system SID --kind real|synthetic [--tier heldout] [--budget 60] [--seed 0]
                           [--strategy evolve] [--objective post] [--init-state] [--hidden --reason TEXT] --out FILE
    sweep: independent searches (systems x seeds x strategies) run concurrently, then aggregated and deduplicated:
        counterexamples.py sweep --method-dir DIR --model-pattern ".../indep/{sid}_s0.pkl" --kind synthetic --tier final
                           [--systems all|s1,s2] [--seeds 0,1,2] [--strategies random,evolve,structured,bo] [--budget 60]
                           [--objective post|effect] [--init-state] [--backend local|modal] [--workers 6] [--containers 200]
                           [--hidden] [--reason TEXT] --out-dir DIR
    equivalence of the local and Modal backends on one public dev system:
        counterexamples.py equiv --method-dir DIR --model PKL --system SID [--budget 12] [--strategies random,evolve,structured,bo]
{sid} in --model-pattern is the system id, {sid_} the id with ':' replaced by '_'.

Isolation: every search runs in a fresh process (local: a process pool with one task per process; Modal: a fresh subprocess in the
container, scripts/p3/p3modal/postlock.py). It runs under the method EVAL guard: method code cannot touch files, processes or the
network while its frames are on the stack. Every rollout runs on a fresh unpickled copy of the model as loaded, so nothing an encode
call stores in the model object can reach a prediction.

Hidden material:
- The synthetic heldout / final suites and --hidden (real: parameter draws derived from the benchmark salt; synthetic: the held-out
  draws 1000-1007) are hidden evaluation material. The run is appended to research/phase3/HIDDEN_EVALUATIONS.md and its outputs are
  ANSWER-BEARING.
- Only after the method lock (research/phase3/METHOD_LOCK.json); the command refuses otherwise.
- The public dev suite and public real draws are development material.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pickle
import sys
import time
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "p3"))

BENCH = ROOT / "benchmarks" / "state_discovery_v1"
BUNDLE = ROOT / "benchmarks" / "dng100" / "public_blind"
DATA = ROOT / "data" / "phase3"
STRATEGIES = ("random", "evolve", "structured", "bo")
SETTINGS = {"real": {"t_end": 1.2, "dt": 0.001, "horizon_s": 0.25, "kick": (5.0, 30.0), "current": (5.0, 40.0)},
            "synthetic": {"t_end": 4.0, "dt": 0.01, "horizon_s": 1.0, "kick_sd": (1.5, 3.0), "current": (0.5, 3.0)}}
# the public protocol families' ranges (PROTOCOL.md section 3), for the in-family flag of each event
FAMILY_RANGES = {"real": {"kick": (5.0, 30.0), "current": (5.0, 40.0), "current_sign": 1},
                 "synthetic": {"kick_sd": (1.5, 3.0), "current": (0.0, 5.0), "current_sign": 0}}
TOP_PER_SEARCH = 5


# ------------------------------------------------------------------------------------------------ small helpers
def phash(p: dict) -> str:
    return hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()[:16]


def job_rng(job: dict) -> np.random.Generator:
    """Deterministic across processes and platforms (never Python's salted hash())."""
    return np.random.default_rng([int(job["seed"]), zlib.crc32(job["system"].encode()), STRATEGIES.index(job["strategy"])])


def event_targets(e: dict) -> list[int]:
    if e["kind"] == "kick":
        return sorted(int(k) for k in e["delta"])
    if e["kind"] == "current":
        return sorted(int(k) for k in e["targets"])
    if e["kind"] == "silence":
        return sorted(int(k) for k in e["targets"])
    return sorted({int(v) for pair in e.get("edges", []) for v in pair})


def signature(p: dict) -> list:
    """The event structure of a protocol: sorted (kind, targets) pairs (amplitudes and times excluded)."""
    return sorted([e["kind"], event_targets(e)] for e in p["events"])


def in_family(e: dict, kind: str, x_sd: dict) -> bool:
    fr = FAMILY_RANGES[kind]
    if e["kind"] == "kick":
        for k, d in e["delta"].items():
            a = abs(float(d))
            if kind == "real":
                if not (fr["kick"][0] - 1e-9 <= a <= fr["kick"][1] + 1e-9):
                    return False
            else:
                sd = float(x_sd.get(str(k), 0.0)) or 1.0
                if not (fr["kick_sd"][0] * (1 - 1e-3) <= a / sd <= fr["kick_sd"][1] * (1 + 1e-3)):     # amplitudes are rounded to 1e-6
                    return False
        return len(e["delta"]) == 1
    if e["kind"] == "current":
        for v in e["targets"].values():
            if fr["current_sign"] and np.sign(v) != fr["current_sign"]:
                return False
            if not (fr["current"][0] - 1e-9 <= abs(float(v)) <= fr["current"][1] + 1e-9):
                return False
        return len(e["targets"]) == 1
    if e["kind"] == "silence":
        return len(e["targets"]) == 1
    return False


# ------------------------------------------------------------------------------------------------ protocols
class Domain:
    """Protocol generation for one search job (all randomness from the job's rng)."""

    def __init__(self, job: dict, rng: np.random.Generator, kinds: list[str]):
        self.job, self.rng, self.kinds = job, rng, list(kinds)
        self.kind = job["kind"]
        self.st = SETTINGS[self.kind]
        self.obs = [int(n) for n in job["info"]["observed"]]
        self.input_dim = int(job["info"].get("input_dim", 1))
        xs = job.get("x_stats") or {}
        self.x_mean = {str(k): float(v) for k, v in zip(self.obs, xs.get("mean", []))}
        self.x_sd = {str(k): float(v) for k, v in zip(self.obs, xs.get("sd", []))}
        self._hidden_seeds = list(job.get("hidden_seeds") or [])
        self._n_seed = 0

    # --- parameter draws
    def params_seed(self) -> int:
        src = self.job["seed_source"]
        if src == "hidden_real":
            s = self._hidden_seeds[self._n_seed % len(self._hidden_seeds)]
            self._n_seed += 1
            return int(s)
        if src == "hidden_synthetic":
            return int(1000 + self.rng.integers(0, 8))
        if src == "public_real":
            return int(self.rng.integers(0, 10**9))
        return int(self.rng.integers(0, 8))

    def snap(self, t: float) -> float:
        return round(round(float(t) / self.st["dt"]) * self.st["dt"], 6)

    def kick_amp(self, n: int, u: float | None = None) -> float:
        lo_hi = self.st.get("kick") or self.st["kick_sd"]
        u = self.rng.random() if u is None else u
        a = lo_hi[0] + u * (lo_hi[1] - lo_hi[0])
        if self.kind == "synthetic":
            a *= (self.x_sd.get(str(n)) or 1.0)
        return float(a)

    def current_amp(self, u: float | None = None) -> float:
        lo, hi = self.st["current"]
        u = self.rng.random() if u is None else u
        return float(lo + u * (hi - lo))

    def stimulus(self, scale: float, onset_frac: float):
        t_on = self.snap(onset_frac * self.st["t_end"])
        if self.kind == "synthetic" and self.input_dim > 1:
            return [[0.0, [0.0] * self.input_dim], [t_on, [scale] * self.input_dim]]
        return [[0.0, 0.0], [t_on, scale]]

    def finish(self, events: list[dict], scale: float, onset_frac: float, r0: dict | None = None, params_seed: int | None = None,
               noise_seed: int | None = None) -> dict:
        p = {"system": self.job["system"], "params_seed": self.params_seed() if params_seed is None else int(params_seed),
             "t_end": self.st["t_end"], "dt": self.st["dt"], "stimulus": self.stimulus(scale, onset_frac),
             "events": sorted(events, key=lambda e: e.get("t", e.get("t0"))), "r0": r0 or {"kind": "zero"}}
        if self.kind == "real":
            p["weight_noise"] = None
        else:
            p["noise_seed"] = int(self.rng.integers(0, 2**31)) if noise_seed is None else int(noise_seed)
        return p

    def init_state(self) -> dict:
        k = int(self.rng.integers(1, min(5, len(self.obs)) + 1))
        tg = [int(v) for v in self.rng.choice(self.obs, k, replace=False)]
        vals = {}
        for n in tg:
            v = self.x_mean.get(str(n), 0.0) + float(self.rng.uniform(-2, 2)) * (self.x_sd.get(str(n)) or 1.0)
            vals[str(n)] = round(max(0.0, v) if self.kind == "real" else v, 6)
        return {"kind": "state", "values": vals}

    def event(self, kind: str, t: float, targets: list[int], sign: float | None = None, amp_u: float | None = None,
              dur_u: float | None = None) -> dict:
        t_end = self.st["t_end"]
        sign = float(self.rng.choice([-1, 1])) if sign is None else float(sign)
        if kind == "kick":
            return {"kind": "kick", "t": self.snap(t), "delta": {str(n): round(sign * self.kick_amp(n, amp_u), 6) for n in targets[:3]}}
        if kind == "current":
            dur = (0.02 + (self.rng.random() if dur_u is None else dur_u) * 0.13) * t_end
            return {"kind": "current", "t0": self.snap(t), "t1": self.snap(t + dur),
                    "targets": {str(n): round(sign * self.current_amp(amp_u), 6) for n in targets[:2]}}
        dur = (0.05 + (self.rng.random() if dur_u is None else dur_u) * 0.25) * t_end
        return {"kind": "silence", "t0": self.snap(t), "t1": self.snap(t + dur), "targets": [int(n) for n in targets[:4]]}

    def random_protocol(self, init_state: bool = False) -> dict:
        t_end = self.st["t_end"]
        t_ev = self.snap(float(self.rng.uniform(0.3, 0.6)) * t_end)
        events = []
        for j in range(int(self.rng.integers(1, 3))):
            kind = self.kinds[int(self.rng.integers(0, len(self.kinds)))]
            tj = t_ev + j * float(self.rng.uniform(0.0, 0.15)) * t_end
            tg = [int(v) for v in self.rng.choice(self.obs, min(len(self.obs), int(self.rng.integers(1, 5))), replace=False)]
            events.append(self.event(kind, tj, tg))
        scale, onset = float(self.rng.uniform(0.5, 1.5)), float(self.rng.uniform(0.01, 0.1))
        r0 = self.init_state() if (init_state and self.rng.random() < 0.5) else None
        return self.finish(events, scale, onset, r0)

    def mutate(self, p: dict) -> dict:
        q = json.loads(json.dumps(p))
        t_end = self.st["t_end"]
        for e in q["events"]:
            if e["kind"] == "kick":
                for k in e["delta"]:
                    e["delta"][k] = round(e["delta"][k] * float(np.exp(self.rng.normal(0, 0.3))), 6)
            elif e["kind"] == "current":
                for k in e["targets"]:
                    e["targets"][k] = round(e["targets"][k] * float(np.exp(self.rng.normal(0, 0.3))), 6)
            key = "t" if "t" in e else "t0"
            shift = float(self.rng.normal(0, 0.03)) * t_end
            new = self.snap(min(max(0.2 * t_end, e[key] + shift), 0.7 * t_end))
            if e.get("t1") is not None:
                e["t1"] = self.snap(min(max(new + self.st["dt"], e["t1"] + (new - e[key])), 0.95 * t_end))
            e[key] = new
        if self.kind == "synthetic":
            q["noise_seed"] = int(self.rng.integers(0, 2**31))
        q["events"] = sorted(q["events"], key=lambda e: e.get("t", e.get("t0")))
        return q


# ------------------------------------------------------------------------------------------------ model access and scoring
class ModelHandle:
    """Encodes on the working model; every rollout runs on a FRESH unpickled copy of the model as it was loaded."""

    def __init__(self, model):
        self.model = model
        try:
            self._blob = pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL)
            self._pristine = None
        except Exception:  # noqa: BLE001 - an unpicklable model still gets fresh copies
            self._blob = None
            self._pristine = copy.deepcopy(model)

    def fresh(self):
        return pickle.loads(self._blob) if self._blob is not None else copy.deepcopy(self._pristine)

    def supports(self, sid: str, kind: str) -> bool:
        try:
            return bool(self.model.supports(sid, kind))
        except Exception:  # noqa: BLE001
            return False


def make_simulator(job: dict):
    """simulate(protocol) -> {t, x (observed), u, y}; orchestrator code only (built before the guard is installed)."""
    if job["kind"] == "synthetic":
        from brainir_state.synthsim import simulate
        tier, seed, sid = job["tier"], int(job["suite_seed"]), job["system"]
        return lambda p: simulate(tier, seed, sid, p)
    from brainir_state.realsim import RealEngine, RealSystem, dense
    d = job["sysdef"]
    eng = RealEngine(job.get("bundle") or str(BUNDLE), d["network"])
    system = RealSystem(system_id=job["system"], network=d["network"], mode=d["mode"], keep=tuple(d["keep"]), observed=tuple(d["observed"]),
                        readout=tuple(d["readout"]), stimulus=tuple(d["stimulus"]))

    def run(p):
        rec = eng.run(system, p)
        return {"t": rec["t"], "x": dense(rec, list(system.observed)), "u": rec["u"], "y": dense(rec, list(system.readout))}
    return run


def twin_of(p: dict, kind: str) -> dict:
    if kind == "real":
        from brainir_state.realgen import counterfactual
        return counterfactual(p)
    q = json.loads(json.dumps(p))
    q["events"] = []
    return q


def score(handle: ModelHandle, job: dict, p: dict, sim, scale: np.ndarray) -> dict | None:
    """Post-event window NMSE (per readout dimension and mean) of the model's rollout encoded at the first event time, and with
    objective 'effect' also the counterfactual effect error. None if the model abstains on one of the protocol's event kinds."""
    from brainir_state.evaluate import shift_events
    sid = job["system"]
    if not all(handle.supports(sid, e["kind"]) for e in p["events"]):
        return None
    out = sim(p)
    dt = float(p["dt"])
    t_ev = min(e.get("t", e.get("t0")) for e in p["events"])
    i0 = int(round(t_ev / dt))
    n = int(round(float(job["horizon_s"]) / dt))
    n = min(n, len(out["t"]) - i0 - 1)
    x, u, y = np.asarray(out["x"], float), np.asarray(out["u"], float), np.asarray(out["y"], float)
    z0 = np.asarray(handle.model.encode(sid, x[: i0 + 1], u[: i0 + 1], dt), float)
    ev = shift_events(p["events"], t_ev, n * dt)
    yp = np.asarray(handle.fresh().rollout(sid, z0, u[i0: i0 + n + 1], ev, dt)["y"], float)[1: n + 1]
    yt = y[i0 + 1: i0 + n + 1]
    with np.errstate(all="ignore"):
        dims = np.mean((yp - yt) ** 2, axis=0) / scale if yp.shape == yt.shape else np.full(len(scale), np.inf)
    dims = np.where(np.isfinite(dims), dims, np.inf)
    row = {"err_post": float(np.mean(dims)), "err_dims": [float(v) for v in dims], "n": int(n)}
    if job.get("objective", "post") == "effect":
        tw = sim(twin_of(p, job["kind"]))
        yc = np.asarray(handle.fresh().rollout(sid, z0, u[i0: i0 + n + 1], [], dt)["y"], float)[1: n + 1]
        d_pred = (yp - yc) / np.sqrt(scale)
        d_true = (yt - np.asarray(tw["y"], float)[i0 + 1: i0 + n + 1]) / np.sqrt(scale)
        den = float((d_true ** 2).sum())
        num = float(((d_pred - d_true) ** 2).sum())
        row.update(effect_num=num, effect_den=den, null_effect=bool(den <= 1e-12 * max(1, d_true.size)))
        row["err"] = (num / den) if (den > 0 and not row["null_effect"] and np.isfinite(num)) else float("nan")
    else:
        row["err"] = row["err_post"]
    return row


# ------------------------------------------------------------------------------------------------ strategies
def _record(rows: list, top: list, phase: str, p: dict, r: dict | None, x_sd: dict, kind: str) -> dict | None:
    if r is None:
        rows.append({"phase": phase, "unsupported": True, "hash": phash(p)})
        return None
    rec = {"phase": phase, "hash": phash(p), "err": r["err"], "err_post": r["err_post"], "err_dims": r["err_dims"],
           "signature": signature(p), "in_family": [in_family(e, kind, x_sd) for e in p["events"]],
           "init_state": p["r0"]["kind"] == "state"}
    for k in ("effect_num", "effect_den", "null_effect"):
        if k in r:
            rec[k] = r[k]
    rows.append(rec)
    if np.isfinite(rec["err"]):
        top.append((rec["err"], rec["hash"], p))
        top.sort(key=lambda t: (-t[0], t[1]))
        del top[TOP_PER_SEARCH:]
    return rec


def search_random(dom: Domain, evaluate, n: int, phase: str = "random") -> list[tuple[float, dict]]:
    out = []
    for _ in range(n):
        p = dom.random_protocol(init_state=bool(dom.job.get("init_state")))
        rec = evaluate(phase, p)
        if rec is not None and np.isfinite(rec["err"]):
            out.append((rec["err"], p))
    return out


def search_evolve(dom: Domain, evaluate, budget: int) -> None:
    scored = search_random(dom, evaluate, budget // 2)
    pop = sorted(scored, key=lambda t: -t[0])[:5]
    n = budget // 2
    while n < budget and pop:
        parent = pop[int(dom.rng.integers(0, len(pop)))][1]
        q = dom.mutate(parent)
        rec = evaluate("search", q)
        n += 1
        if rec is not None and np.isfinite(rec["err"]):
            pop = sorted(pop + [(rec["err"], q)], key=lambda t: -t[0])[:5]


def search_structured(dom: Domain, evaluate, budget: int) -> None:
    n_ref = max(1, budget // 4)
    search_random(dom, evaluate, n_ref)
    cycle = [(k, s) for k, s in (("kick", 1.0), ("kick", -1.0), ("current", 1.0), ("current", -1.0), ("silence", None)) if k in dom.kinds]
    order = [int(v) for v in dom.rng.permutation(dom.obs)]
    n = n_ref
    t_end = dom.st["t_end"]
    for neuron in order:
        for kind, sign in cycle:
            if n >= budget:
                return
            e = dom.event(kind, 0.45 * t_end, [neuron], sign=(sign if sign is not None else 1.0), amp_u=1.0, dur_u=0.5)
            evaluate("structured", dom.finish([e], 1.0, 0.05))
            n += 1


def search_bo(dom: Domain, evaluate, budget: int) -> None:
    from scipy.stats import norm
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
    t_end = dom.st["t_end"]
    restarts = 2
    for r in range(restarts):
        per = budget // restarts + (budget % restarts if r == restarts - 1 else 0)
        n_ev = int(dom.rng.integers(1, 3))
        struct = []
        for _ in range(n_ev):
            kind = dom.kinds[int(dom.rng.integers(0, len(dom.kinds)))]
            tg = [int(v) for v in dom.rng.choice(dom.obs, min(len(dom.obs), int(dom.rng.integers(1, 5))), replace=False)]
            struct.append((kind, tg, float(dom.rng.choice([-1, 1]))))
        pseed = dom.params_seed()
        nseed = int(dom.rng.integers(0, 2**31))
        d = 3 + 3 * n_ev           # t_ev, stimulus scale, onset; per event: amplitude, duration, offset

        def proto(th, struct=struct, pseed=pseed, nseed=nseed):
            t_ev = (0.3 + 0.3 * th[0]) * t_end
            events = []
            for j, (kind, tg, sign) in enumerate(struct):
                a, du, off = th[3 + 3 * j: 6 + 3 * j]
                events.append(dom.event(kind, t_ev + j * 0.15 * off * t_end, tg, sign=sign, amp_u=float(a), dur_u=float(du)))
            return dom.finish(events, 0.5 + float(th[1]), 0.01 + 0.09 * float(th[2]), params_seed=pseed, noise_seed=nseed)

        X, Y = [], []
        n_init = max(3, per // 4)
        for i in range(per):
            if i < n_init or len(X) < 3:
                th = dom.rng.random(d)
                phase = "bo_init"
            else:
                gp = GaussianProcessRegressor(kernel=ConstantKernel(1.0, (1e-3, 1e3)) * Matern(length_scale=np.full(d, 0.3),
                                                                                                 length_scale_bounds=(1e-2, 10.0), nu=2.5)
                                              + WhiteKernel(1e-3, (1e-6, 1.0)), normalize_y=True, n_restarts_optimizer=1,
                                              random_state=int(dom.rng.integers(0, 2**31)))
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")          # kernel-bound convergence notes of the GP fit
                    gp.fit(np.array(X), np.array(Y))
                cand = dom.rng.random((256, d))
                mu, sd = gp.predict(cand, return_std=True)
                best = max(Y)
                zz = (mu - best) / np.maximum(sd, 1e-9)
                ei = (mu - best) * norm.cdf(zz) + sd * norm.pdf(zz)
                th = cand[int(np.argmax(ei))]
                phase = "bo"
            rec = evaluate(phase, proto(th))
            if rec is not None and np.isfinite(rec["err"]):
                X.append(np.asarray(th, float))
                Y.append(float(np.log(max(rec["err"], 1e-12))))


# ------------------------------------------------------------------------------------------------ one search job
def _limit_threads(n: int) -> None:
    try:
        from brainir_state.suite_eval import limit_threads
        limit_threads(n)
    except Exception:  # noqa: BLE001
        pass


def cex_worker(job: dict) -> dict:
    """One search. job: {system, kind, tier, suite_seed | sysdef, strategy, seed, budget, objective, init_state, horizon_s,
    seed_source, hidden_seeds, info, x_stats, scale, method_dir, model_path, guard ('local' | 'none'), threads}."""
    t0 = time.time()
    _limit_threads(int(job.get("threads", 2)))
    sim = make_simulator(job)                       # orchestrator code, before the guard
    if job.get("guard", "local") == "local":
        from brainir_state.runguard import install_eval_guard
        install_eval_guard([job["method_dir"]], allowed=[str(Path(job["model_path"]).resolve().parent)])
    from brainir_state.runner import load_model
    handle = ModelHandle(load_model(job["method_dir"], job["model_path"]))
    sid = job["system"]
    kinds = [k for k in ("kick", "current", "silence") if handle.supports(sid, k)]
    base = {k: job[k] for k in ("system", "kind", "tier", "strategy", "seed", "budget", "objective", "init_state", "seed_source")
            if k in job}
    if not kinds:
        return {"job": base, "kinds_supported": [], "rows": [], "top": [], "note": "the model abstains on every event kind",
                "wall_s": round(time.time() - t0, 1)}
    scale = np.asarray(job["scale"], float)
    rng = job_rng(job)
    dom = Domain(job, rng, kinds)
    rows, top, errors = [], [], []

    def evaluate(phase, p):
        try:
            return _record(rows, top, phase, p, score(handle, job, p, sim, scale), dom.x_sd, job["kind"])
        except Exception as e:  # noqa: BLE001 - a failed simulation / rollout is recorded, never retried silently
            errors.append({"phase": phase, "hash": phash(p), "error": repr(e)[:500]})
            rows.append({"phase": phase, "hash": phash(p), "error": True})
            return None

    b = int(job["budget"])
    {"random": lambda: search_random(dom, evaluate, b), "evolve": lambda: search_evolve(dom, evaluate, b),
     "structured": lambda: search_structured(dom, evaluate, b), "bo": lambda: search_bo(dom, evaluate, b)}[job["strategy"]]()
    return {"job": base, "kinds_supported": kinds, "rows": rows, "errors": errors,
            "top": [{"err": e, "hash": h, "protocol": p} for e, h, p in top], "wall_s": round(time.time() - t0, 1)}


# ------------------------------------------------------------------------------------------------ aggregation and deduplication
def dedup(cands: list[dict], cos_min: float = 0.98, rel_tol: float = 0.1) -> list[dict]:
    """Greedy clustering in order of decreasing error. A candidate joins the first cluster whose representative has the same event
    signature (kinds and target sets), an error profile over readout dimensions with cosine similarity >= cos_min, and an error
    within rel_tol x max of the representative's. Returns the clusters (representative + member count)."""
    clusters: list[dict] = []
    for c in sorted(cands, key=lambda c: (-c["err"], c["hash"])):
        v = np.asarray(c["err_dims"], float)
        v = np.where(np.isfinite(v), v, 1e12)
        placed = False
        for cl in clusters:
            r = cl["rep"]
            if r["signature"] != c["signature"]:
                continue
            w = np.asarray(r["err_dims"], float)
            w = np.where(np.isfinite(w), w, 1e12)
            den = float(np.linalg.norm(v) * np.linalg.norm(w))
            cos = float(v @ w / den) if den > 0 else 1.0
            if cos >= cos_min and abs(c["err"] - r["err"]) <= rel_tol * max(abs(c["err"]), abs(r["err"])):
                cl["n_members"] += 1
                cl["members"].append(c["hash"])
                placed = True
                break
        if not placed:
            clusters.append({"rep": c, "n_members": 1, "members": [c["hash"]]})
    return clusters


def aggregate(results: list[dict], abs_threshold: float = 1.0, rel_factor: float = 2.0, immediate_n: int = 10) -> dict:
    """Per system: the random-protocol reference distribution, the worst errors, counterexample candidates (err >= max(abs_threshold,
    rel_factor x the system's random p90)), 'broken immediately' (a candidate among a search's first immediate_n scored protocols),
    and the deduplicated distinct counterexamples."""
    by_sys: dict[str, list[dict]] = {}
    for r in results:
        by_sys.setdefault(r["job"]["system"], []).append(r)
    out = {"criteria": {"abs_threshold": abs_threshold, "rel_factor": rel_factor, "immediate_n": immediate_n}, "systems": {}}
    for sid, rs in sorted(by_sys.items()):
        scored = [row for r in rs for row in r.get("rows", []) if "err" in row and row["err"] is not None and np.isfinite(row["err"])]
        rand = np.array([row["err"] for row in scored if row["phase"] in ("random", "bo_init")])
        thr = max(abs_threshold, rel_factor * float(np.percentile(rand, 90))) if len(rand) else abs_threshold
        cands = [row for row in scored if row["err"] >= thr]
        immediate = []
        for r in rs:
            first = [row for row in r.get("rows", []) if "err" in row and row["err"] is not None and np.isfinite(row["err"])][:immediate_n]
            immediate.append(any(row["err"] >= thr for row in first))
        clusters = dedup(cands)
        protos = {t["hash"]: t["protocol"] for r in rs for t in r.get("top", [])}
        worst = max((row["err"] for row in scored), default=None)
        kinds_count: dict[str, int] = {}
        for cl in clusters:
            for kind, _ in cl["rep"]["signature"]:
                kinds_count[kind] = kinds_count.get(kind, 0) + 1
        out["systems"][sid] = {
            "n_searches": len(rs), "n_scored": len(scored),
            "n_unsupported": sum(1 for r in rs for row in r.get("rows", []) if row.get("unsupported")),
            "n_errors": sum(len(r.get("errors") or []) for r in rs),
            "kinds_supported": sorted({k for r in rs for k in r.get("kinds_supported", [])}),
            "random_median": float(np.median(rand)) if len(rand) else None, "random_p90": float(np.percentile(rand, 90)) if len(rand) else None,
            "worst": worst,
            "worst_over_random_median": (worst / float(np.median(rand))) if (worst is not None and len(rand) and np.median(rand) > 0) else None,
            "threshold": thr, "n_candidates": len(cands), "n_distinct": len(clusters),
            "broken_immediately_fraction": float(np.mean(immediate)) if immediate else None,
            "distinct_kinds": kinds_count,
            "distinct": [{"err": cl["rep"]["err"], "err_post": cl["rep"].get("err_post"), "signature": cl["rep"]["signature"],
                          "n_members": cl["n_members"], "in_family": cl["rep"]["in_family"], "init_state": cl["rep"]["init_state"],
                          "phase": cl["rep"]["phase"], "hash": cl["rep"]["hash"], "protocol": protos.get(cl["rep"]["hash"])}
                         for cl in clusters[:20]],
            "by_strategy": {s: {"n": sum(1 for r in rs if r["job"]["strategy"] == s),
                                "worst": max((row["err"] for r in rs if r["job"]["strategy"] == s for row in r.get("rows", [])
                                              if "err" in row and row["err"] is not None and np.isfinite(row["err"])), default=None)}
                            for s in sorted({r["job"]["strategy"] for r in rs})}}
    vals = list(out["systems"].values())
    out["overall"] = {"n_systems": len(vals), "n_systems_with_counterexamples": sum(1 for v in vals if v["n_distinct"] > 0),
                      "n_distinct_total": sum(v["n_distinct"] for v in vals),
                      "median_worst_over_random_median": float(np.median([v["worst_over_random_median"] for v in vals
                                                                          if v["worst_over_random_median"] is not None])) if vals else None,
                      "systems_broken_immediately": sum(1 for v in vals if (v["broken_immediately_fraction"] or 0) >= 0.5)}
    return out


# ------------------------------------------------------------------------------------------------ job construction (driver side)
def _readout_scale(train, kind: str) -> np.ndarray:
    """The evaluator's normaliser (benchmark version 3 may pool the real readout normalisation: used when available)."""
    import inspect

    from brainir_state import evaluate as E
    if kind == "real" and "pooled" in inspect.signature(E.readout_scale).parameters:
        return E.readout_scale(train, pooled=True)
    return E.readout_scale(train)


def suite_seed(tier: str) -> int:
    rec = json.loads((BENCH / "hidden" / "synthetic_suites.json").read_text(encoding="utf-8"))[tier]
    return int(rec["seed"])


def suite_data(kind: str, tier: str):
    from brainir_state.suite_eval import SuiteData
    if kind == "real":
        return SuiteData(DATA / "real_public", kind="real")
    pub = DATA / "synthetic_dev" if tier == "dev" else DATA / "synthetic" / tier / "public"
    return SuiteData(pub, kind="synthetic")


def hidden_seed_list(system: str, strategy: str, seed: int, n: int) -> list[int]:
    """Real hidden parameter draws for one search, derived from the benchmark salt (never printed; hidden range >= 10^9)."""
    salt = (DATA / "hidden" / "salt.txt").read_text(encoding="utf-8").strip()
    return [int(hashlib.sha256(f"{salt}|cex|{system}|{strategy}|{seed}|{i}".encode()).hexdigest()[:12], 16) % (2**31) + 10**9
            for i in range(n)]


def build_jobs(kind: str, tier: str, systems: list[str], strategies: list[str], seeds: list[int], budget: int, objective: str,
               init_state: bool, hidden: bool, method_dir: str, model_for: dict[str, str], threads: int = 2) -> list[dict]:
    sd = suite_data(kind, tier)
    st = SETTINGS[kind]
    real_defs = json.loads((BENCH / "hidden" / "systems_internal.json").read_text(encoding="utf-8")) if kind == "real" else {}
    s_seed = suite_seed(tier) if kind == "synthetic" else None
    jobs = []
    for sid in systems:
        train = sd.train_only(sid)
        info = sd.sysinfo(sid)
        X = np.concatenate([t.x for t in train]).astype(np.float64)
        x_stats = {"mean": X.mean(0).tolist(), "sd": (X.std(0) + 1e-9).tolist()}
        scale = _readout_scale(train, kind)
        for strategy in strategies:
            for seed in seeds:
                job = {"system": sid, "kind": kind, "tier": tier, "strategy": strategy, "seed": int(seed), "budget": int(budget),
                       "objective": objective, "init_state": bool(init_state), "horizon_s": st["horizon_s"],
                       "info": {"observed": list(info["observed"]), "input_dim": int(info.get("input_dim", 1))},
                       "x_stats": x_stats, "scale": [float(v) for v in scale], "method_dir": str(method_dir), "model_path": str(model_for[sid]),
                       "threads": threads, "guard": "local"}
                if kind == "synthetic":
                    job["suite_seed"] = s_seed
                    job["seed_source"] = "hidden_synthetic" if hidden else "public_synthetic"
                else:
                    job["sysdef"] = {k: real_defs[sid][k] for k in ("network", "mode", "keep", "observed", "readout", "stimulus")}
                    job["seed_source"] = "hidden_real" if hidden else "public_real"
                    if hidden:
                        job["hidden_seeds"] = hidden_seed_list(sid, strategy, seed, budget)
                jobs.append(job)
    return jobs


# ------------------------------------------------------------------------------------------------ backends
def run_local(jobs: list[dict], workers: int) -> list[dict]:
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor
    if not jobs:
        return []
    with ProcessPoolExecutor(max_workers=max(1, workers), mp_context=mp.get_context("spawn"), max_tasks_per_child=1) as ex:
        futs = [ex.submit(cex_worker, j) for j in jobs]
        out = []
        for j, f in zip(jobs, futs):
            try:
                out.append(f.result())
            except Exception as e:  # noqa: BLE001
                out.append({"job": {k: j[k] for k in ("system", "kind", "tier", "strategy", "seed", "budget")}, "error": repr(e)[:2000],
                            "rows": [], "top": []})
        return out


def _modal_backend(containers: int):
    import modal
    import modal_tournament as MT
    img = MT.image().add_local_dir(str(BUNDLE), "/repo/benchmarks/dng100/public_blind", ignore=["**/__pycache__/**"])
    app = modal.App("brainir-p3-postlock", image=img)
    fitvol = modal.Volume.from_name(MT.FIT_VOLUME, create_if_missing=True)

    def p3_cex_call(payload):
        import p3modal.postlock as PL
        return PL.run_cex(payload)

    fn = app.function(cpu=MT.CPU, memory=MT.MEM_MB, timeout=3 * 3600, max_containers=containers,
                      retries=modal.Retries(max_retries=1, initial_delay=5.0, backoff_coefficient=1.0), volumes={"/fitvol": fitvol},
                      serialized=True, name="p3_cex")(p3_cex_call)
    return app, fn, fitvol


def _model_key(path: Path, fitvol, cache: dict) -> str:
    """Upload a fitted model once to the fit volume (/models/<sha16>.pkl + side file); key = its content hash."""
    path = Path(path)
    if str(path) in cache:
        return cache[str(path)]
    blob = path.read_bytes()
    key = hashlib.sha256(blob).hexdigest()[:16]
    try:
        present = {Path(e.path).name for e in fitvol.listdir("/models")}
    except Exception:  # noqa: BLE001
        present = set()
    if f"{key}.pkl" not in present:
        import io
        with fitvol.batch_upload(force=True) as b:
            b.put_file(io.BytesIO(blob), f"/models/{key}.pkl")
            if path.with_suffix(".json").exists():
                b.put_file(io.BytesIO(path.with_suffix(".json").read_bytes()), f"/models/{key}.json")
    cache[str(path)] = key
    return key


def run_modal(jobs: list[dict], containers: int) -> tuple[list[dict], dict]:
    import uuid

    import modal
    import modal_tournament as MT
    app, fn, fitvol = _modal_backend(containers)
    t0 = time.time()
    mcache: dict = {}
    payloads = []
    for j in jobs:
        payloads.append({"job_id": uuid.uuid4().hex, "methods_key": MT._methods_key(Path(j["method_dir"]), fitvol),
                         "model_key": _model_key(Path(j["model_path"]), fitvol, mcache),
                         "job": {k: v for k, v in j.items() if k not in ("method_dir", "model_path", "guard")},
                         "timeout_s": 3 * 3600 - 300, "threads": int(j.get("threads", 2))})
    app_id = None
    with modal.enable_output(), app.run():
        app_id = getattr(app, "app_id", None)
        res = list(fn.map(payloads, order_outputs=True, return_exceptions=True))
    out = []
    for j, r in zip(jobs, res):
        if isinstance(r, BaseException):
            r = {"job": {k: j[k] for k in ("system", "kind", "tier", "strategy", "seed", "budget")}, "error": f"modal call failed: {r!r}"[:2000],
                 "rows": [], "top": []}
        out.append(r)
    cs = sum(float(r.get("container_wall_s") or 0.0) for r in out)
    cost = {"app_id": app_id, "calls": len(payloads), "container_s": round(cs, 1), "wall_s": round(time.time() - t0, 1), "cpu": MT.CPU,
            "memory_mb": MT.MEM_MB, "usd_approx": round(cs * (MT.CPU * MT.PRICE_PER_CORE_S + MT.MEM_MB / 1024 * MT.PRICE_PER_GIB_S), 3)}
    return out, cost


# ------------------------------------------------------------------------------------------------ logging and outputs
def _hidden_material(kind: str, tier: str, hidden: bool) -> bool:
    return bool(hidden) or (kind == "synthetic" and tier in ("heldout", "final"))


def log_hidden(run: str, what: str, method: str, reason: str, outputs: str) -> None:
    log = ROOT / "research" / "phase3" / "HIDDEN_EVALUATIONS.md"
    if not log.exists():
        log.write_text("# Phase 3 hidden evaluation log (Level C and Level B confirmation; PROTOCOL.md section 10)\n\n| time (UTC) | "
                       "attempt | what | method / baseline | reason | outputs |\n|---|---|---|---|---|---|\n", encoding="utf-8", newline="\n")
    with open(log, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"| {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | {run} | {what} | {method} | {reason} | {outputs} |\n")


def _require_lock() -> None:
    if not (ROOT / "research" / "phase3" / "METHOD_LOCK.json").exists():
        raise SystemExit("refusing: searches on hidden material run only after research/phase3/METHOD_LOCK.json exists")


def _models_for(pattern: str, systems: list[str]) -> dict[str, str]:
    out = {}
    for s in systems:
        p = Path(pattern.format(sid=s, sid_=s.replace(":", "_")))
        if not p.exists():
            raise SystemExit(f"no fitted model for {s}: {p}")
        out[s] = str(p)
    return out


def _write_outputs(out_dir: Path, results: list[dict], summary: dict, extra: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "jobs").mkdir(exist_ok=True)
    for r in results:
        j = r.get("job") or {}
        name = f"{str(j.get('system', 'x')).replace(':', '_')}_{j.get('strategy')}_s{j.get('seed')}.json"
        (out_dir / "jobs" / name).write_text(json.dumps(r, default=float) + "\n", encoding="utf-8", newline="\n")
    rec = {**extra, **summary}
    (out_dir / "SUMMARY.json").write_text(json.dumps(rec, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    lines = [f"# Counterexample search: {extra.get('run')}", "", f"- method: {extra.get('method')}; suite: {extra.get('kind')} / "
             f"{extra.get('tier')}; hidden material: {extra.get('hidden_material')}; objective: {extra.get('objective')}",
             f"- strategies {extra.get('strategies')}, seeds {extra.get('seeds')}, budget {extra.get('budget')} per search, init-state "
             f"{extra.get('init_state')}; backend {extra.get('backend')}", "",
             "| system | searches | scored | random median | worst | worst / median | candidates | distinct | broken immediately |",
             "|---|---|---|---|---|---|---|---|---|"]
    for sid, v in summary["systems"].items():
        def f(x):
            return "-" if x is None else f"{x:.3g}"
        lines.append(f"| {sid} | {v['n_searches']} | {v['n_scored']} | {f(v['random_median'])} | {f(v['worst'])} | "
                     f"{f(v['worst_over_random_median'])} | {v['n_candidates']} | {v['n_distinct']} | {f(v['broken_immediately_fraction'])} |")
    lines += ["", f"Overall: {json.dumps(summary['overall'])}", ""]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _legacy_record(res: dict, budget: int) -> dict:
    """The original single-search output keys (plus the new ones)."""
    rows = [r for r in res.get("rows", []) if "err" in r and r["err"] is not None and np.isfinite(r["err"])]
    rand = np.array([r["err"] for r in rows if r["phase"] in ("random", "bo_init")])
    worst = sorted(res.get("top", []), key=lambda t: -t["err"])
    j = res.get("job", {})
    return {"system": j.get("system"), "kind": j.get("kind"), "hidden": j.get("seed_source", "").startswith("hidden"), "budget": budget,
            "strategy": j.get("strategy"), "objective": j.get("objective"), "n_scored": len(rows),
            "random_median": float(np.median(rand)) if len(rand) else None, "random_p90": float(np.percentile(rand, 90)) if len(rand) else None,
            "worst": [{"err": t["err"], "events": [e["kind"] for e in t["protocol"]["events"]],
                       "n_targets": [len(event_targets(e)) for e in t["protocol"]["events"]], "protocol": t["protocol"]} for t in worst],
            "worst_over_random_median": (worst[0]["err"] / float(np.median(rand))) if (worst and len(rand) and np.median(rand) > 0) else None,
            "kinds_supported": res.get("kinds_supported"), "errors": res.get("errors"), "wall_s": res.get("wall_s")}


# ------------------------------------------------------------------------------------------------ CLI
def cmd_single(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method-dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--system", required=True)
    ap.add_argument("--kind", choices=("real", "synthetic"), required=True)
    ap.add_argument("--tier", default="heldout")
    ap.add_argument("--budget", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--strategy", choices=STRATEGIES, default="evolve")
    ap.add_argument("--objective", choices=("post", "effect"), default="post")
    ap.add_argument("--init-state", action="store_true")
    ap.add_argument("--hidden", action="store_true")
    ap.add_argument("--reason", default="post-lock counterexample search")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    hm = _hidden_material(a.kind, a.tier, a.hidden)
    if hm:
        _require_lock()
    jobs = build_jobs(a.kind, a.tier, [a.system], [a.strategy], [a.seed], a.budget, a.objective, a.init_state, a.hidden, a.method_dir,
                      {a.system: a.model})
    res = run_local(jobs, 1)[0]
    rec = _legacy_record(res, a.budget)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(rec, indent=1, default=float) + "\n", encoding="utf-8")
    if hm:
        log_hidden(Path(a.out).stem, f"counterexample search ({a.kind} {a.tier}, {a.strategy}, budget {a.budget})", Path(a.model).name,
                   a.reason, str(Path(a.out)))
    print(json.dumps({k: v for k, v in rec.items() if k not in ("worst", "errors")}))
    return 0


def cmd_sweep(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method-dir", required=True)
    ap.add_argument("--method", default="")
    ap.add_argument("--model-pattern", required=True)
    ap.add_argument("--kind", choices=("real", "synthetic"), required=True)
    ap.add_argument("--tier", default="final")
    ap.add_argument("--systems", default="all")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--strategies", default=",".join(STRATEGIES))
    ap.add_argument("--budget", type=int, default=60)
    ap.add_argument("--objective", choices=("post", "effect"), default="post")
    ap.add_argument("--init-state", action="store_true")
    ap.add_argument("--hidden", action="store_true")
    ap.add_argument("--reason", default="post-lock counterexample search (goal4 sections 53, 87)")
    ap.add_argument("--backend", choices=("local", "modal"), default="modal")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--containers", type=int, default=200)
    ap.add_argument("--abs-threshold", type=float, default=1.0)
    ap.add_argument("--rel-factor", type=float, default=2.0)
    ap.add_argument("--run", default="")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    hm = _hidden_material(a.kind, a.tier, a.hidden)
    if hm:
        _require_lock()
    if a.hidden and a.kind == "real" and a.backend == "modal":
        # LEAKAGE_POLICY section 3.1: no real hidden material on Modal (the salt-derived draws stay on the local machine)
        raise SystemExit("refusing: real --hidden searches run with --backend local")
    sd = suite_data(a.kind, a.tier)
    # every system of the suite is searched, the non-compressible controls included (their claims are judged by family L)
    systems = sd.systems if a.systems == "all" else [s for s in a.systems.split(",") if s]
    models = _models_for(a.model_pattern, systems)
    strategies = [s for s in a.strategies.split(",") if s]
    seeds = [int(s) for s in a.seeds.split(",") if s]
    jobs = build_jobs(a.kind, a.tier, systems, strategies, seeds, a.budget, a.objective, a.init_state, a.hidden, a.method_dir, models)
    run = a.run or Path(a.out_dir).name
    if hm:
        log_hidden(run, f"counterexample search START ({a.kind} {a.tier}; {len(systems)} systems x {len(strategies)} strategies x "
                        f"{len(seeds)} seeds, budget {a.budget}, objective {a.objective})", a.method or Path(a.method_dir).name, a.reason,
                   str(Path(a.out_dir)))
    t0 = time.time()
    print(f"{len(jobs)} searches on {a.backend}", flush=True)
    cost = None
    if a.backend == "modal":
        results, cost = run_modal(jobs, a.containers)
    else:
        results = run_local(jobs, a.workers)
    summary = aggregate(results, a.abs_threshold, a.rel_factor)
    extra = {"run": run, "method": a.method or Path(a.method_dir).name, "kind": a.kind, "tier": a.tier, "hidden_material": hm,
             "objective": a.objective, "strategies": strategies, "seeds": seeds, "budget": a.budget, "init_state": a.init_state,
             "backend": a.backend, "wall_s": round(time.time() - t0, 1), "n_jobs": len(jobs),
             "n_job_failures": sum(1 for r in results if r.get("error")), "modal": cost}
    _write_outputs(Path(a.out_dir), results, summary, extra)
    if cost:
        (Path(a.out_dir) / "modal_costs.json").write_text(json.dumps(cost, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"overall": summary["overall"], "wall_s": extra["wall_s"], "failures": extra["n_job_failures"], "modal": cost}))
    return 0


def compare_results(a: list[dict], b: list[dict], rtol: float = 1e-6, atol: float = 1e-9) -> dict:
    """Local vs Modal: the same protocols (hash sequence) and errors within tolerance, per search."""
    rows = []
    for ra, rb in zip(a, b):
        ha = [r.get("hash") for r in ra.get("rows", [])]
        hb = [r.get("hash") for r in rb.get("rows", [])]
        ea = np.array([r.get("err", np.nan) if r.get("err") is not None else np.nan for r in ra.get("rows", [])], float)
        eb = np.array([r.get("err", np.nan) if r.get("err") is not None else np.nan for r in rb.get("rows", [])], float)
        same_seq = ha == hb
        n = min(len(ea), len(eb))
        both = np.isfinite(ea[:n]) & np.isfinite(eb[:n])
        diff = np.abs(ea[:n] - eb[:n])[both]
        rel = diff / np.maximum(np.abs(ea[:n][both]), atol)
        rows.append({"system": ra.get("job", {}).get("system"), "strategy": ra.get("job", {}).get("strategy"), "n_local": len(ha),
                     "n_modal": len(hb), "same_protocol_sequence": same_seq,
                     "same_nan_pattern": bool(np.array_equal(np.isfinite(ea[:n]), np.isfinite(eb[:n]))),
                     "max_abs_diff": float(diff.max()) if diff.size else 0.0, "max_rel_diff": float(rel.max()) if rel.size else 0.0,
                     "within_tolerance": bool(same_seq and (not rel.size or float(rel.max()) <= rtol or float(diff.max()) <= atol)),
                     "errors_local": ra.get("error"), "errors_modal": rb.get("error")})
    return {"rtol": rtol, "atol": atol, "searches": rows, "all_equivalent": bool(rows and all(r["within_tolerance"] for r in rows))}


def cmd_equiv(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method-dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--system", required=True)
    ap.add_argument("--budget", type=int, default=12)
    ap.add_argument("--strategies", default=",".join(STRATEGIES))
    ap.add_argument("--objective", choices=("post", "effect"), default="post")
    ap.add_argument("--kind", choices=("real", "synthetic"), default="synthetic", help="public material only: the dev suite / public real draws")
    ap.add_argument("--out", default=str(ROOT / "research" / "phase3" / "postlock_infra" / "cex_equivalence.json"))
    a = ap.parse_args(argv)
    strategies = [s for s in a.strategies.split(",") if s]
    jobs = build_jobs(a.kind, "dev", [a.system], strategies, [0], a.budget, a.objective, True, False, a.method_dir, {a.system: a.model})
    t0 = time.time()
    loc = run_local(jobs, min(4, len(jobs)))
    t_loc = time.time() - t0
    rem, cost = run_modal(jobs, len(jobs))
    rec = compare_results(loc, rem)
    rec.update({"system": a.system, "kind": a.kind, "tier": "dev" if a.kind == "synthetic" else "real_public", "budget": a.budget,
                "strategies": strategies, "objective": a.objective,
                "local_wall_s": round(t_loc, 1), "modal": cost,
                "local_job_wall_s": [r.get("wall_s") for r in loc], "modal_job_wall_s": [r.get("wall_s") for r in rem]})
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(rec, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "searches"}, default=float))
    for r in rec["searches"]:
        print(json.dumps(r))
    return 0 if rec["all_equivalent"] else 1


def cmd_simequiv(argv) -> int:
    """Simulator-only equivalence (no model): the same public protocols simulated locally and in a Modal container; reports the
    readout differences relative to the public readout sd (goal4 section 62; the acceleration directive's numerical-equivalence rule)."""
    import modal
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True)
    ap.add_argument("--kind", choices=("real", "synthetic"), default="real")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--out", default=str(ROOT / "research" / "phase3" / "postlock_infra" / "sim_equivalence.json"))
    a = ap.parse_args(argv)
    job = build_jobs(a.kind, "dev", [a.system], ["random"], [0], a.n, "post", True, False, "-", {a.system: "-"})[0]
    dom = Domain(job, job_rng(job), ["kick", "current", "silence"])
    protos = [dom.random_protocol(init_state=True) for _ in range(a.n)]
    t0 = time.time()
    sim = make_simulator(job)
    y_loc = [np.asarray(sim(q)["y"], np.float64) for q in protos]
    t_loc = time.time() - t0
    app, _, _ = _modal_backend(1)

    def p3_sim_call(payload):
        import p3modal.postlock as PL
        return PL.run_sim(payload)

    fn = app.function(cpu=2.0, memory=6144, timeout=3600, serialized=True, name="p3_sim_probe")(p3_sim_call)
    t1 = time.time()
    with modal.enable_output(), app.run():
        app_id = getattr(app, "app_id", None)
        rem = fn.remote({"job": {k: v for k, v in job.items() if k not in ("method_dir", "model_path")}, "protocols": protos})
    sd = np.sqrt(np.asarray(job["scale"], float))
    rows = []
    for q, yl, yr in zip(protos, y_loc, rem["y"]):
        d = np.abs(yl - yr)
        rows.append({"hash": phash(q), "events": [e["kind"] for e in q["events"]], "max_abs_diff": float(d.max()),
                     "max_diff_over_sd": float((d / sd).max()), "rel_l2": float(np.linalg.norm(yl - yr) / max(np.linalg.norm(yl), 1e-12))})
    rec = {"system": a.system, "kind": a.kind, "n": a.n, "local_wall_s": round(t_loc, 1), "modal_wall_s": round(time.time() - t1, 1),
           "modal_container_s": rem.get("container_wall_s"), "app_id": app_id,
           "max_diff_over_sd": max(r["max_diff_over_sd"] for r in rows), "max_rel_l2": max(r["rel_l2"] for r in rows), "protocols": rows}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "protocols"}))
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "sweep":
        return cmd_sweep(argv[1:])
    if argv and argv[0] == "equiv":
        return cmd_equiv(argv[1:])
    if argv and argv[0] == "simequiv":
        return cmd_simequiv(argv[1:])
    return cmd_single(argv)


if __name__ == "__main__":
    raise SystemExit(main())
