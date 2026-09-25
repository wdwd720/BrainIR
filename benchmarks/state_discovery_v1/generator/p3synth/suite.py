"""Suite builder: systems with opaque ids, rich protocol sets with train/val/test splits and hold-outs, public dataset +
separate truth.

    build_suite(out_public, out_truth, seed, tier)

Hold-outs of the test split (CONTRACT section 5):
  * initial states   : test initial latent states come from a region never used in train/val (latent radius 1-1.5 x the
                       training range, or the opposite well / other cycle etc.) plus fresh draws;
  * parameter draws  : params_seed in train/val is from TRAIN_PARAMS, test uses TEST_PARAMS (disjoint);
  * noise            : weight_noise sd 0.05 (seeds < 10^4) in train, sd 0.12 with seeds >= 10^4 in test; every trajectory
                       has its own process/observation noise realisation (seeded by the canonical protocol);
  * intervention TYPES: train/val only have single-neuron kicks, single-neuron currents and single-neuron silencing;
                       test has group kicks, group currents, group silencing and edge removal;
  * intervention TARGETS: neurons are split per system into train targets (60%, stratified by role) and held-out targets;
                       every train/val intervention acts on train targets only, every test intervention on held-out
                       targets only.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from . import dataset
from . import truth as truth_writer
from .core import SIM_VERSION, seed_from
from .protocol import validate
from .systems import build_system, catalog

DT = 0.01
SPLITS = ("train", "val", "test", "twin")
TRAIN_PARAMS = list(range(0, 8))
TEST_PARAMS = list(range(1000, 1008))

# counts per (split, family) at scale 1 (tier "dev"); other tiers scale these
PLAN = {
    "train": {"nominal": 3, "init": 7, "stim": 5, "param_draw": 5, "weight_noise": 2, "kick": 4, "current": 3,
              "silence_single": 3},
    "val": {"nominal": 1, "init": 2, "stim": 1, "kick": 1, "current": 1, "silence_single": 1},
    "test": {"init_heldout": 2, "param_heldout": 2, "noise_heldout": 1, "kick_group": 2, "current_group": 1,
             "group_silence": 2, "edge_remove": 1, "kick_newtarget": 1, "silence_newtarget": 1, "combined_heldout": 1},
}
TIER_SCALE = {"dev": 1.0, "heldout": 2.0, "final": 3.0}

FAMILY_DOC = {
    "nominal": "default rest start, the system's nominal stimulus schedule (scaled), train parameter draws",
    "init": "random initial microstate (r0 sets every neuron), random stimulus",
    "stim": "rest start, random pulses / steps of the input",
    "param_draw": "other parameter draws (params_seed) of the same system",
    "weight_noise": "structural perturbation of synaptic weights (weight_noise sd 0.05)",
    "kick": "single-neuron instantaneous state offset",
    "current": "single-neuron injected current over a window",
    "silence_single": "single-neuron silencing over a window (or to the end)",
    "init_heldout": "initial states from a held-out region of state space",
    "param_heldout": "held-out parameter draws",
    "noise_heldout": "held-out structural noise level and seeds (weight_noise sd 0.12)",
    "kick_group": "simultaneous kicks to a group of held-out neurons",
    "current_group": "currents into a group of held-out neurons",
    "group_silence": "silencing of a group of held-out neurons",
    "edge_remove": "removal of couplings among held-out neurons",
    "kick_newtarget": "single kicks on neurons never intervened in train/val",
    "silence_newtarget": "single silencing of neurons never intervened in train/val",
    "combined_heldout": "held-out parameter draw + held-out initial state + group silencing",
}


# ------------------------------------------------------------------------------------------------ stimuli
def _chan_value(rng, kind, amp):
    if kind == "binary":
        return float(rng.random() < 0.6) * amp
    if kind == "positive":
        return round(float(rng.uniform(0.2, 1.0) * amp), 4)
    return round(float(rng.uniform(-1.0, 1.0) * amp), 4)


def random_stimulus(lat, rng, t_end):
    n_seg = int(rng.integers(1, 4))
    stim = [[0.0, 0.0 if lat.n_u == 1 else [0.0] * lat.n_u]]
    for _ in range(n_seg):
        t0 = float(rng.uniform(0.2, t_end - 0.6))
        dur = float(rng.choice([rng.uniform(0.05, 0.3), rng.uniform(0.3, 1.2)]))
        if lat.n_u == 1:
            kind, amp = lat.channels[0]
            val = _chan_value(rng, kind, amp * 1.5)
        else:
            val = [_chan_value(rng, kind, amp) for kind, amp in lat.channels]
        stim.append([t0, val])
        stim.append([min(t0 + dur, t_end), 0.0 if lat.n_u == 1 else [0.0] * lat.n_u])
    stim.sort(key=lambda s: s[0])
    # keep the last value for identical times
    out = {}
    for t, v in stim:
        out[round(round(t / DT) * DT, 9)] = v
    return [[t, v] for t, v in sorted(out.items())]


def scaled_nominal(lat, rng, t_end, shift=0.0, amp=(0.7, 1.3)):
    a = round(float(rng.uniform(*amp)), 4)
    out = []
    for t, v in lat.nominal_stimulus(t_end):
        tt = min(max(0.0, t + shift if t > 0 else 0.0), t_end)
        vv = [round(a * x, 6) for x in v] if isinstance(v, list) else round(a * v, 6)
        out.append([round(round(tt / DT) * DT, 9), vv])
    ded = {}
    for t, v in out:
        ded[t] = v
    return [[t, v] for t, v in sorted(ded.items())]


# ------------------------------------------------------------------------------------------------ planning
class Planner:
    def __init__(self, system, seed, tier, scale):
        self.s = system
        self.lat = system.model.latent
        self.rng = np.random.default_rng(seed_from("plan", seed, tier, system.meta["name"]) % (2 ** 32))
        self.scale = scale
        self.t_end = float(system.meta.get("t_end", 4.0))
        self.time_locked = system.meta.get("stim_mode") == "time_locked"
        N = system.n
        roles = system.impl.roles
        tr, te = [], []
        for r in sorted(set(roles)):
            ids = [i for i in range(N) if roles[i] == r]
            ids = list(self.rng.permutation(ids))
            n_tr = int(round(0.6 * len(ids)))
            if len(ids) >= 2:
                n_tr = min(max(n_tr, 1), len(ids) - 1)
            tr += ids[:n_tr]
            te += ids[n_tr:]
        self.train_targets = sorted(int(i) for i in tr)
        self.test_targets = sorted(int(i) for i in te)
        self.sd_v = np.zeros(N)  # pilot initial states lie on the manifold
        self._pilot()

    def _pilot(self):
        xs, vs = [], []
        for j in range(2):
            p = self.base("nominal" if j == 0 else "init", heldout=False)
            o = self.s.simulate(p, full=True)
            xs.append(o["x_full"])
            vs.append(o["v_full"])
        xs, vs = np.concatenate(xs), np.concatenate(vs)
        sx, sv = xs.std(0), vs.std(0)
        self.sd_x = np.maximum(sx, 0.1 * np.median(sx) + 1e-3)
        self.sd_v = np.maximum(sv, 0.1 * np.median(sv) + 1e-3)

    # -- protocol pieces
    def stim(self, split):
        r = self.rng
        if self.time_locked and split != "test":
            return scaled_nominal(self.lat, r, self.t_end)
        if self.time_locked:
            return scaled_nominal(self.lat, r, self.t_end, shift=float(r.uniform(-0.4, 1.5)))
        c = r.random()
        if c < 0.35:
            return scaled_nominal(self.lat, r, self.t_end, shift=float(r.uniform(-0.3, 0.8)))
        if c < 0.9:
            return random_stimulus(self.lat, r, self.t_end)
        return [[0.0, 0.0 if self.lat.n_u == 1 else [0.0] * self.lat.n_u]]

    def r0_random(self, params_seed, heldout):
        s, m, im = self.s, self.s.model, self.s.impl
        th = self.lat.draw(params_seed)
        z0 = np.asarray(self.lat.sample_init(self.rng, th, heldout), float)
        parts = [z0] + [np.asarray(b.init(self.rng, z0, th, m, heldout), float) for b in m.blocks]
        c0 = np.concatenate(parts)
        w = self.rng.standard_normal(s.n) * 0.1 * self.sd_v
        w = w - im.E @ (im.D @ w)                          # off-manifold only: D w = 0
        x0 = im.phi.clip(im.phi.fwd(im.b + im.E @ c0 + w))
        return {"kind": "state", "values": {str(i): float(np.format_float_positional(v, 6, unique=False, fractional=False, trim="-"))
                                            for i, v in enumerate(x0)}}

    def base(self, family, heldout=False, split="train", params_seed=None):
        ps = params_seed if params_seed is not None else (0 if family == "nominal" else int(self.rng.choice(TRAIN_PARAMS)))
        p = {"system": self.s.system_id, "params_seed": int(ps), "weight_noise": None, "r0": {"kind": "zero"},
             "t_end": self.t_end, "dt": DT, "stimulus": self.stim(split), "events": []}
        if family == "nominal":
            p["stimulus"] = scaled_nominal(self.lat, self.rng, self.t_end)
            p["params_seed"] = int(self.rng.choice(TRAIN_PARAMS[:3]))
        elif family in ("init", "init_heldout"):
            p["r0"] = self.r0_random(ps, heldout)
        return p

    def t_rand(self, lo=0.2, hi=0.7):
        return round(round(float(self.rng.uniform(lo, hi) * self.t_end) / DT) * DT, 9)

    def kick(self, targets, n):
        ids = self.rng.choice(targets, min(n, len(targets)), replace=False)
        return {"kind": "kick", "t": self.t_rand(),
                "delta": {str(int(j)): float(round(self.rng.choice([-1, 1]) * self.rng.uniform(1.5, 3.0) * self.sd_x[j], 6)) for j in ids}}

    def current(self, targets, n):
        ids = self.rng.choice(targets, min(n, len(targets)), replace=False)
        t0 = self.t_rand(0.15, 0.6)
        t1 = min(self.t_end, round(t0 + float(self.rng.uniform(0.2, 0.6)), 2))
        lam = self.s.impl.lam
        return {"kind": "current", "t0": t0, "t1": t1,
                "targets": {str(int(j)): float(round(self.rng.choice([-1, 1]) * self.rng.uniform(1.0, 3.0) * self.sd_v[j] * lam, 6)) for j in ids}}

    def silence(self, targets, n):
        ids = self.rng.choice(targets, min(n, len(targets)), replace=False)
        t0 = self.t_rand(0.15, 0.6)
        t1 = None if self.rng.random() < 0.2 else min(self.t_end, round(t0 + float(self.rng.uniform(0.3, 1.2)), 2))
        return {"kind": "silence", "t0": t0, "t1": t1, "targets": [int(j) for j in ids]}

    def edges(self, targets):
        s = self.s
        tg = np.asarray(targets)
        pre = [j for j in tg if np.any(s.impl.D[:, j] != 0)]
        post = [i for i in tg if np.any(s.impl.E[i] != 0)]
        cand = [(int(i), int(j)) for i in post for j in pre if i != j]
        if not cand:
            return None
        n = min(len(cand), int(self.rng.integers(20, 80)))
        sel = self.rng.choice(len(cand), n, replace=False)
        t0 = self.t_rand(0.15, 0.5)
        t1 = None if self.rng.random() < 0.3 else min(self.t_end, round(t0 + float(self.rng.uniform(0.5, 1.5)), 2))
        return {"kind": "edge_remove", "t0": t0, "t1": t1, "edges": [list(cand[q]) for q in sel]}

    def make(self, split, family):
        r = self.rng
        trT, teT = self.train_targets, self.test_targets
        if family in ("nominal", "init", "stim"):
            return self.base(family, split=split)
        if family == "param_draw":
            return self.base("stim", split=split, params_seed=int(r.choice(TRAIN_PARAMS[1:])))
        if family == "weight_noise":
            p = self.base("stim", split=split)
            p["weight_noise"] = {"sd": 0.05, "seed": int(r.integers(0, 10_000))}
            return p
        maybe_init = "init" if r.random() < 0.4 else "stim"
        if family == "kick":
            p = self.base(maybe_init, split=split); p["events"] = [self.kick(trT, 1)]; return p
        if family == "current":
            p = self.base(maybe_init, split=split); p["events"] = [self.current(trT, 1)]; return p
        if family == "silence_single":
            p = self.base(maybe_init, split=split); p["events"] = [self.silence(trT, 1)]; return p
        # ---- test families
        if family == "init_heldout":
            return self.base("init_heldout", heldout=True, split=split)
        if family == "param_heldout":
            fam = "init" if r.random() < 0.5 else "stim"
            return self.base(fam, split=split, params_seed=int(r.choice(TEST_PARAMS)))
        if family == "noise_heldout":
            p = self.base("stim", split=split)
            p["weight_noise"] = {"sd": 0.12, "seed": int(r.integers(10_000, 20_000))}
            return p
        grp = max(3, int(round(len(teT) * r.uniform(0.15, 0.4))))
        if family == "kick_group":
            p = self.base(maybe_init, split=split); p["events"] = [self.kick(teT, int(r.integers(3, 16)))]; return p
        if family == "current_group":
            p = self.base(maybe_init, split=split); p["events"] = [self.current(teT, int(r.integers(3, 16)))]; return p
        if family == "group_silence":
            p = self.base(maybe_init, split=split); p["events"] = [self.silence(teT, grp)]; return p
        if family == "edge_remove":
            p = self.base(maybe_init, split=split)
            ev = self.edges(teT)
            p["events"] = [ev] if ev else [self.silence(teT, grp)]
            return p
        if family == "kick_newtarget":
            p = self.base(maybe_init, split=split); p["events"] = [self.kick(teT, 1)]; return p
        if family == "silence_newtarget":
            p = self.base(maybe_init, split=split); p["events"] = [self.silence(teT, 1)]; return p
        if family == "combined_heldout":
            ps = int(r.choice(TEST_PARAMS))
            p = self.base("init_heldout", heldout=True, split=split, params_seed=ps)
            p["events"] = [self.silence(teT, grp)]
            return p
        raise ValueError(family)

    def plan(self):
        """All protocols of this system; duplicates (identical canonical protocols) are redrawn."""
        out, seen = [], set()
        for split, fams in PLAN.items():
            for fam, n in fams.items():
                for _ in range(max(1, int(round(n * self.scale)))):
                    for _try in range(50):
                        p = self.make(split, fam)
                        key = json.dumps(validate(p), sort_keys=True)
                        if key not in seen:
                            break
                    seen.add(key)
                    out.append((split, fam, p))
        # explicit noise seeds, drawn after all protocols so the protocol draws themselves are unchanged
        used: set = set()
        for _, _, p in out:
            ns = int(self.rng.integers(0, 2 ** 31))
            while ns in used:
                ns = int(self.rng.integers(0, 2 ** 31))
            used.add(ns)
            p["noise_seed"] = ns
        return out


def _traj_key(system_id, protocol, salt):
    blob = json.dumps({"s": system_id, "p": validate(protocol), "salt": salt}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:20]


def _run_system(args):
    name, seed, tier, scale, out_public, out_truth = args
    defn = {d.name: d for d in catalog()}[name]
    s = build_system(defn, seed, tier)
    t0 = time.perf_counter()
    pl = Planner(s, seed, tier, scale)
    t_plan = time.perf_counter() - t0
    rows, trows = [], []
    t_sim = 0.0
    n_samples = 0
    def run(split, fam, p, pair=None):
        nonlocal t_sim, n_samples
        p = validate(p, n=s.n, input_dim=s.input_dim, k=s.k, allow_latent=False)
        t1 = time.perf_counter()
        out = s.simulate(p)
        t_sim += time.perf_counter() - t1
        n_samples += len(out["t"])
        key = _traj_key(s.system_id, p, f"{tier}:{seed}")
        dataset.write_traj(out_public, key, {k_: out[k_] for k_ in dataset.PUBLIC_ARRAYS})
        tinfo = truth_writer.write_latent(out_truth, key, out)
        info = dict(out["info"]["public"])
        if pair is not None:
            info["pair"] = pair
        rows.append({"key": key, "system_id": s.system_id, "split": split, "family": fam, "protocol": p, "info": info})
        trows.append({"key": key, "system_id": s.system_id, "split": split, "family": fam, **tinfo})
        return key, p

    for split, fam, p in pl.plan():
        if split == "test" and p["events"]:
            # intervened test trajectory + its counterfactual twin (no events, same noise realisation)
            key = _traj_key(s.system_id, validate(p), f"{tier}:{seed}")
            _, pv = run(split, fam, p, pair=key)
            run("twin", fam, dict(pv, events=[]), pair=key)
        else:
            run(split, fam, p)
    design = {"train_targets": pl.train_targets, "test_targets": pl.test_targets, "train_params": TRAIN_PARAMS,
              "test_params": TEST_PARAMS, "train_weight_noise": {"sd": 0.05, "seeds": "[0, 10000)"},
              "test_weight_noise": {"sd": 0.12, "seeds": "[10000, 20000)"},
              "train_intervention_types": ["kick (single)", "current (single)", "silence (single)"],
              "test_intervention_types": ["kick (group)", "current (group)", "silence (group)", "edge_remove",
                                          "kick/silence (single) on held-out targets"],
              "time_locked_training_stimuli": pl.time_locked}
    timing = {"n_traj": len(rows), "sim_seconds": t_sim, "plan_seconds": t_plan, "n_samples": n_samples, "n": s.n,
              "K": s.model.K}
    return name, rows, trows, design, timing


def build_suite(out_public: Path, out_truth: Path, seed: int, tier: str, *, scale: float | None = None,
                workers: int | None = None, names: list[str] | None = None) -> dict:
    """Build a suite. Public data -> out_public (data_format.md); truth -> out_truth (truth writer only)."""
    out_public, out_truth = Path(out_public), Path(out_truth)
    if out_public.resolve() == out_truth.resolve() or out_truth.resolve().is_relative_to(out_public.resolve()):
        raise ValueError("truth must be written outside the public dataset directory")
    if tier not in TIER_SCALE:
        raise ValueError(f"unknown tier {tier!r}")
    scale = TIER_SCALE[tier] if scale is None else float(scale)
    defs = [d for d in catalog() if names is None or d.name in names]
    out_public.mkdir(parents=True, exist_ok=True)
    out_truth.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    jobs = [(d.name, seed, tier, scale, str(out_public), str(out_truth)) for d in defs]
    workers = workers or min(len(jobs), os.cpu_count() or 1)
    # one BLAS thread per worker process (the matrices are small; oversubscription only slows things down)
    for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(var, "1")
    # biggest systems first for load balance
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_run_system, jobs))
    else:
        results = [_run_system(j) for j in jobs]
    wall = time.perf_counter() - t0
    cache: dict = {}
    systems = [build_system(d, seed, tier, cache) for d in defs]
    by_name = {s.meta["name"]: s for s in systems}
    rows, trows, design, timing = [], [], {}, {}
    for name, r, tr, dsg, tm in results:
        rows += r
        trows += tr
        design[by_name[name].system_id] = dsg
        timing[by_name[name].system_id] = {"name": name, **tm}
    order = {s.system_id: i for i, s in enumerate(sorted(systems, key=lambda s: s.system_id))}
    rows.sort(key=lambda r: (order[r["system_id"]], SPLITS.index(r["split"]), r["key"]))
    trows.sort(key=lambda r: (order[r["system_id"]], SPLITS.index(r["split"]), r["key"]))
    dataset_id = f"p3synth-{tier}-" + hashlib.sha256(f"{tier}|{seed}".encode()).hexdigest()[:8]
    manifest = {
        "dataset_id": dataset_id, "version": SIM_VERSION, "dt": DT,
        "systems": {s.system_id: {"observed": list(map(int, s.observed)), "readout": [], "input_dim": s.input_dim,
                                  "readout_dim": s.readout_dim, "n": s.n, "kind": "synthetic", "network": None, "group": None,
                                  "targets_public": sorted(int(j) for j in design[s.system_id]["train_targets"])}
                    for s in sorted(systems, key=lambda s: s.system_id)},
        "splits": list(SPLITS),
        "families": FAMILY_DOC,
        "notes": "Synthetic systems: neuron ids are 0..n-1; x holds the observed neurons (columns in manifest order). "
                 "Neuron states are signed activations; r0 values may be negative. A scalar stimulus value scales the "
                 "system's nominal input pattern; a list gives the input vector. Every protocol carries a noise_seed: "
                 "protocols sharing it share one noise realisation. Split 'twin': the counterfactual of an intervened "
                 "test trajectory (same protocol and noise_seed, no events); both rows carry info.pair = key of the "
                 "intervened trajectory. targets_public: the neurons train/val events may touch.",
    }
    dataset.write_index_and_manifest(out_public, manifest, rows)
    groups = {}
    for s in systems:
        if s.meta.get("group"):
            groups.setdefault(f"grp-{s.meta['group']}", []).append(s.system_id)
    pairs = {}
    for s in systems:
        if s.meta.get("pair"):
            pairs.setdefault(s.meta["pair"], []).append(s.system_id)
    suite = {"seed": seed, "tier": tier, "dataset_id": dataset_id, "scale": scale, "simulator": SIM_VERSION,
             "implementation_groups": groups, "unrelated_pairs": list(pairs.values()), "split_design": design,
             "timing": {"wall_seconds": wall, "workers": workers, "per_system": timing}}
    truth_writer.write_truth(out_truth, systems, suite, trows)
    return {"dataset_id": dataset_id, "n_systems": len(systems), "n_traj": len(rows), "wall_seconds": wall,
            "sim_seconds": sum(t["sim_seconds"] for t in timing.values()),
            "n_samples": sum(t["n_samples"] for t in timing.values()), "workers": workers}
