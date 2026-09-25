"""Real-circuit systems and protocol generators for state_discovery_v1 (ORCHESTRATOR SIDE; locked before method development).

Systems (per public network d):
    real:<d>:full            the intact network
    real:<d>:mech:<h8>       keep-only network of each candidate mechanism regenerated from public evidence by the locked Phase 2
                             method (research/phase3/candidates), h8 = first 8 hex of sha256 of the sorted member ids
Observed population (encoder input): neurons (not readout, not stimulus) with peak rate > 0.01 Hz in any PUBLIC probe trajectory of
the system. Readout: the network's readout neurons active in any probe trajectory of its full system (the same list for every system
of the network). Input u: the stimulus current (one channel per stimulus neuron).

Intervention targets: the full system's observed population is split by a PUBLIC seeded permutation into A (public: development
interventions) and B (held out: hidden tests only). Mechanism systems: A = every member.

Seeds: public protocols use params seeds < 10**9; hidden protocols derive seeds >= 10**9 from a SECRET salt (committed by hash
before development; revealed after the hidden evaluation). The simulation service refuses hidden-range seeds and non-public families.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .realsim import ACTIVE_HZ, RealEngine, RealSystem

T_END, DT = 2.0, 0.001
HIDDEN_SEED_BASE = 10**9
PUBLIC_SPLIT_SEED = 20260925
PROBE_SCALES = (0.6, 1.0, 1.4)
PROBE_SEEDS = (101, 102, 103)

PUBLIC_FAMILIES = ("nominal", "stim_amp", "init_state", "kick_A", "pulse_A", "silence1_A", "weight_noise")
HIDDEN_FAMILIES = ("H_nominal", "H_init_state", "H_kick_A", "H_pulse_A", "H_silence1_A", "H_kick_B", "H_pulse_B", "H_silence1_B",
                   "H_group_silence", "H_stim_ood", "H_weight_ood")
# counterfactual twins (same seed, state and inputs, no events) are generated for every hidden intervention family
INTERVENTION_FAMILIES = ("kick_A", "pulse_A", "silence1_A", "H_kick_A", "H_pulse_A", "H_silence1_A", "H_kick_B", "H_pulse_B", "H_silence1_B",
                         "H_group_silence")
# microstate-equivalence pools (H_micro): per hidden parameter draw, several trajectories from different initial states and kicks,
# whose states the evaluator restarts under a common future input (brainir_state.realgen.micro_pool_protocols)
MICRO_POOL_DRAWS, MICRO_POOL_TRAJ = 6, 8


def mech_id(network: str, members: list[int]) -> str:
    return f"real:{network}:mech:" + hashlib.sha256(json.dumps(sorted(int(m) for m in members)).encode()).hexdigest()[:8]


def hidden_seed(salt: str, *parts) -> int:
    h = hashlib.sha256((salt + "|" + "|".join(str(p) for p in parts)).encode()).hexdigest()
    return HIDDEN_SEED_BASE + int(h[:12], 16) % HIDDEN_SEED_BASE


def _probe_protocols(system_id: str) -> list[dict]:
    return [{"system": system_id, "params_seed": s, "t_end": T_END, "dt": DT, "stimulus": [[0.0, 0.0], [0.02, sc]]}
            for s in PROBE_SEEDS for sc in PROBE_SCALES]


def build_systems(bundle: Path | str, network: str, candidates: list[list[int]], engine: RealEngine | None = None) -> list[RealSystem]:
    """The systems of one network, with observed / readout populations from the public probe rule (deterministic)."""
    eng = engine or RealEngine(bundle, network)
    pr = eng.problem
    readout_all = [int(i) for i in pr.readout_positions]
    stim = [int(i) for i in pr.stim_positions]
    excluded = set(readout_all) | set(stim)
    full0 = RealSystem(system_id=f"real:{network}:full", network=network, mode="full", readout=tuple(readout_all), stimulus=tuple(stim))
    active_full: set[int] = set()
    for proto in _probe_protocols(full0.system_id):
        rec = eng.run(full0, proto)
        peak = rec["rates"].max(axis=0)
        active_full |= {int(n) for n, p in zip(rec["neurons"], peak) if p > ACTIVE_HZ}
    readout = tuple(sorted(n for n in active_full if n in set(readout_all)))
    observed = tuple(sorted(n for n in active_full if n not in excluded))
    systems = [RealSystem(system_id=full0.system_id, network=network, mode="full", observed=observed, readout=readout, stimulus=tuple(stim),
                          meta={"n_network": pr.n})]
    for members in candidates:
        sid = mech_id(network, members)
        base = RealSystem(system_id=sid, network=network, mode="mech", keep=tuple(sorted(int(m) for m in members)), readout=tuple(readout_all),
                          stimulus=tuple(stim))
        active: set[int] = set()
        for proto in _probe_protocols(sid):
            rec = eng.run(base, proto)
            peak = rec["rates"].max(axis=0)
            active |= {int(n) for n, p in zip(rec["neurons"], peak) if p > ACTIVE_HZ}
        obs = tuple(sorted(n for n in active if n not in excluded) or sorted(int(m) for m in members))
        systems.append(RealSystem(system_id=sid, network=network, mode="mech", keep=base.keep, observed=obs, readout=readout, stimulus=tuple(stim),
                                  meta={"members": sorted(int(m) for m in members), "n_network": pr.n}))
    return systems


def split_targets(system: RealSystem) -> tuple[list[int], list[int]]:
    """(A, B): public vs held-out intervention targets."""
    obs = list(system.observed)
    if system.mode == "mech":
        return sorted(obs), []
    rng = np.random.default_rng(PUBLIC_SPLIT_SEED + int(hashlib.sha256(system.network.encode()).hexdigest()[:8], 16))
    perm = [obs[i] for i in rng.permutation(len(obs))]
    half = len(perm) // 2
    return sorted(perm[:half]), sorted(perm[half:])


@dataclass
class Sampler:
    system: RealSystem
    rng: np.random.Generator
    seed_fn: callable            # () -> params seed (public or hidden range)
    state_pool: list[dict] | None = None

    def _base(self, t_on: float | None = None, scale: float = 1.0) -> dict:
        t_on = float(self.rng.uniform(0.01, 0.15)) if t_on is None else t_on
        return {"system": self.system.system_id, "params_seed": int(self.seed_fn()), "t_end": T_END, "dt": DT,
                "stimulus": [[0.0, 0.0], [round(t_on, 3), round(scale, 4)]], "events": []}

    def nominal(self) -> dict:
        return self._base()

    def stim_amp(self, lo: float = 0.6, hi: float = 1.4) -> dict:
        p = self._base(scale=float(self.rng.uniform(lo, hi)))
        if self.rng.random() < 0.3:
            p["stimulus"].append([round(float(self.rng.uniform(0.6, 1.2)), 3), round(float(self.rng.uniform(lo, hi)), 4)])
        if self.rng.random() < 0.5:
            p["stimulus"].append([round(float(self.rng.uniform(1.25, 1.8)), 3), 0.0])
        p["stimulus"] = sorted(p["stimulus"])
        return p

    def init_state(self) -> dict:
        p = self._base(t_on=0.0, scale=float(self.rng.uniform(0.8, 1.2)))
        obs = list(self.system.observed)
        if self.state_pool and self.rng.random() < 0.7:
            st = self.state_pool[int(self.rng.integers(len(self.state_pool)))]
            vals = {int(k): max(0.0, float(v) * float(1.0 + 0.2 * self.rng.standard_normal())) for k, v in st.items()}
        else:
            vals = {n: float(self.rng.uniform(0, 20)) for n in obs if self.rng.random() < 0.5}
        p["r0"] = {"kind": "state", "values": {str(k): round(v, 4) for k, v in vals.items() if v > 0}}
        return p

    def kick(self, targets: list[int]) -> dict:
        p = self._base()
        for _ in range(int(self.rng.integers(1, 4))):
            t = round(float(self.rng.uniform(0.3, 1.7)), 3)
            ns = self.rng.choice(targets, size=min(len(targets), int(self.rng.integers(1, 4))), replace=False)
            p["events"].append({"kind": "kick", "t": t, "delta": {str(int(n)): round(float(self.rng.choice([-1, 1]) * self.rng.uniform(5, 30)), 3)
                                                                   for n in ns}})
        return p

    def pulse(self, targets: list[int]) -> dict:
        p = self._base()
        for _ in range(int(self.rng.integers(1, 3))):
            t0 = round(float(self.rng.uniform(0.3, 1.6)), 3)
            ns = self.rng.choice(targets, size=min(len(targets), int(self.rng.integers(1, 3))), replace=False)
            p["events"].append({"kind": "current", "t0": t0, "t1": round(t0 + float(self.rng.uniform(0.01, 0.15)), 3),
                                "targets": {str(int(n)): round(float(self.rng.uniform(5, 40)), 3) for n in ns}})
        return p

    def silence(self, targets: list[int], group: tuple[int, int] = (1, 1)) -> dict:
        p = self._base()
        k = int(self.rng.integers(group[0], group[1] + 1))
        ns = [int(n) for n in self.rng.choice(targets, size=min(len(targets), k), replace=False)]
        t0 = round(float(self.rng.uniform(0.3, 1.5)), 3)
        t1 = None if self.rng.random() < 0.5 else round(t0 + float(self.rng.uniform(0.1, 0.5)), 3)
        p["events"].append({"kind": "silence", "t0": t0, "t1": t1, "targets": ns})
        return p

    def weight_noise(self, lo: float = 0.02, hi: float = 0.1) -> dict:
        p = self._base()
        p["weight_noise"] = {"sd": round(float(self.rng.uniform(lo, hi)), 4), "seed": int(self.seed_fn())}
        return p


def family_protocol(fam: str, smp: Sampler, A: list[int], B: list[int]) -> dict:
    allt = sorted(set(A) | set(B))
    if fam in ("nominal", "H_nominal"):
        return smp.nominal()
    if fam == "stim_amp":
        return smp.stim_amp()
    if fam in ("init_state", "H_init_state"):
        return smp.init_state()
    if fam in ("kick_A", "H_kick_A"):
        return smp.kick(A)
    if fam in ("pulse_A", "H_pulse_A"):
        return smp.pulse(A)
    if fam in ("silence1_A", "H_silence1_A"):
        return smp.silence(A)
    if fam == "weight_noise":
        return smp.weight_noise()
    if fam == "H_kick_B":
        return smp.kick(B or A)
    if fam == "H_pulse_B":
        return smp.pulse(B or A)
    if fam == "H_silence1_B":
        return smp.silence(B or A)
    if fam == "H_group_silence":
        return smp.silence(allt, group=(2, min(4, len(allt))))
    if fam == "H_stim_ood":
        return smp.stim_amp(*((1.5, 2.0) if smp.rng.random() < 0.5 else (0.3, 0.5)))
    if fam == "H_weight_ood":
        return smp.weight_noise(0.15, 0.25)
    raise ValueError(fam)


def micro_pool_protocols(system: RealSystem, salt: str, A: list[int], state_pool: list[dict]) -> list[dict]:
    """H_micro: MICRO_POOL_DRAWS hidden parameter draws x MICRO_POOL_TRAJ trajectories each (different initial states, an optional
    kick), all with the nominal stimulus from t = 0, so that states within one draw can be compared and restarted."""
    out = []
    for g in range(MICRO_POOL_DRAWS):
        seed = hidden_seed(salt, system.system_id, "H_micro", g)
        rng = np.random.default_rng(seed % (2**32))
        smp = Sampler(system, rng, seed_fn=lambda s=seed: s, state_pool=state_pool)
        for _ in range(MICRO_POOL_TRAJ):
            p = smp.init_state()
            p["params_seed"] = seed
            p["stimulus"] = [[0.0, 1.0]]
            if A and rng.random() < 0.5:
                p["events"] = smp.kick(A)["events"][:1]
            p["group"] = g
            out.append(p)
    return out


def applied_kick_totals(info: dict | None) -> dict | None:
    """Requested against APPLIED kick offsets of one intervention trajectory (benchmark version 3; pre-lock review D, M1), from its
    index info["kicks_applied"] (written for the hidden real data by scripts/p3/generate_real_hidden.py; the engine clips rates at 0,
    so a negative kick on a quiet neuron is applied only partly, or not at all). None when nothing is recorded (no kicks, or data
    generated before version 3). A kicked neuron is "clipped" when its applied offset differs from the requested one, and "null" when
    the applied offset is 0 (a negative kick on a silent neuron: a no-op). The function only reads the info dict, but importing
    brainir_state.realgen also imports the real engine (not in the clean room): evaluator code shared with the room imports it lazily."""
    ka = (info or {}).get("kicks_applied")
    if not ka:
        return None
    req = [float(v) for k in ka for v in k["requested"].values()]
    app = [float(k["applied"][n]) for k in ka for n in k["requested"]]
    req_abs, app_abs = sum(abs(v) for v in req), sum(abs(v) for v in app)
    return {"n_kick_events": len(ka), "n_kicked_neurons": len(req),
            "requested_abs_total": req_abs, "applied_abs_total": app_abs,
            "requested_signed_total": sum(req), "applied_signed_total": sum(app),
            "applied_over_requested_abs": (app_abs / req_abs) if req_abs > 0 else None,
            "n_clipped": sum(1 for r, a in zip(req, app) if abs(a - r) > 1e-9),
            "n_null": sum(1 for a in app if abs(a) <= 1e-9),
            "source": ka[0].get("source", "engine"), "ambiguous": any(k.get("ambiguous") for k in ka)}


def counterfactual(p: dict) -> dict:
    """The same trajectory without its events (the no-intervention twin). Version 2 (review H m1): the twin keeps the intervened run's
    BREAKPOINTS as no-op stimulus steps (the stimulus value in force at each event time), so the piecewise integration is identical
    to the intervened run's up to the first event and the twins differ from it only after the event."""
    q = json.loads(json.dumps(p))
    times = set()
    for e in q.get("events") or []:
        for key in ("t", "t0", "t1"):
            if e.get(key) is not None:
                times.add(float(e[key]))
    q["events"] = []
    stim = sorted(([float(t), float(s)] for t, s in (q.get("stimulus") or [[0.0, 1.0]])), key=lambda x: x[0])
    for t in sorted(times):
        if 0.0 < t < float(q["t_end"]) and not any(abs(t - s[0]) < 1e-9 for s in stim):
            in_force = [s for ts, s in stim if ts <= t + 1e-9]
            stim.append([t, in_force[-1] if in_force else 0.0])
    q["stimulus"] = sorted(stim, key=lambda x: x[0])
    return q
