"""Generic calibration protocols (a stand-in for the benchmark's dataset generator, PROTOCOL.md section 4) and the calibration
report (ref/calibstats.py).

Per system (all seeded by the system id), following the record design of docs/CALIBRATION_TARGETS.md version 3 (no explicit
initial states: initial-condition variability comes only from RESTARTS of nominal passive trajectories of the same system and
parameter draw). Every record below is passed to calibstats.compute_all (no subsample; compute_all itself uses at most 40 records
per record kind for its per-trajectory statistics). With the default n_int = 200 (the synthetic B_main), 713 records:
  D0 passive (40): 8 nominal trajectories over parameter draws (seeds 0-7); 12 stimulus schedules over the capability's input
     range (6 single steps, 6 multi-step schedules); 12 initial-condition changes, each a restart at 25-90 % of one of the 8
     nominal trajectories (its draw), continuing under the nominal input; 8 weight-noise draws (sd 0.02-0.1);
  D1 reference interventions (n_int, each with its counterfactual twin): drawn over the system's rotation families (PROTOCOL.md
     section 3) x public targets (a seeded half of the targetable units) x magnitude classes (0.1, 0.3, 1, 3 m_s, jittered by
     0.8-1.25, never above 3 m_s) x onset times (uniform in [0.15, 0.5] t_end); pulses 20-150 ms; silencing temporary;
  validation: 9 passive (2 nominal, 3 stimulus schedules, 3 restarts from the 2 validation nominals, 1 weight-noise draw) and
     n_int / 5 interventions with twins;
  test: n_test = 24 interventions with twins; 16 passive tests (8 nominal trajectories over new draws; 8 restarts, each from the
     nominal test trajectory two positions before it);
  pool sources (120): 8 parameter draws x 15 sources: the first a nominal trajectory, 5 restarts from it ('init' sources), 5
     stimulus schedules and 4 single-event intervention trajectories of the trained families (no twins).
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

from . import protocol as P

ROTATIONS = {"R1": ("sil.1", "pulse.1"), "R2": ("kick.1", "act.1", "edge.w"), "R3": ("pulse.1", "param.1", "seq.train"),
             "R4": ("kick.1", "pulse.1", "sil.1", "sil.2")}
MAG_CLASSES = (0.1, 0.3, 1.0, 3.0)
RESTART_RANGE = (0.25, 0.9)       # restarts at 25-90 % of the source trajectory


def _seed(*keys) -> int:
    return int.from_bytes(hashlib.sha256(repr(keys).encode()).digest()[:8], "little")


def public_targets(s, rng) -> list[int]:
    tg = list(s.targetable)
    m = max(1, len(tg) // 2)
    return sorted(int(u) for u in rng.choice(tg, size=m, replace=False))


def rotation_of(s) -> str:
    return sorted(ROTATIONS)[_seed("rot", s.system_id) % 4]


def _event(fam, s, cap, rng, targets, t_on, mult):
    dt = s.dt
    snap = lambda t: P.snap(t, dt)  # noqa: E731
    u = int(rng.choice(targets))
    sgn = float(rng.choice([-1.0, 1.0]))
    mk, mc = cap["kick"]["moderate"], cap["current"]["moderate"]
    t_end = s.t_end_default
    if fam == "kick.1":
        return [{"kind": "kick", "t": t_on, "delta": {str(u): sgn * mult * mk}}]
    if fam == "pulse.1":
        d = snap(rng.uniform(0.02, 0.15))
        return [{"kind": "current", "t0": t_on, "t1": snap(t_on + max(d, 2 * dt)), "targets": {str(u): sgn * mult * mc}}]
    if fam in ("act.1", "inh.1"):
        sg = 1.0 if fam == "act.1" else -1.0
        t1 = None if rng.random() < 0.5 else snap(min(t_on + rng.uniform(0.3, 0.6), t_end))
        return [{"kind": "current", "t0": t_on, "t1": t1, "targets": {str(u): sg * mult * mc}}]
    if fam == "sil.1":
        t1 = snap(min(t_on + rng.uniform(0.05, 0.3), t_end))          # temporary silencing (no persistent silencing)
        return [{"kind": "silence", "t0": t_on, "t1": t1, "targets": [u]}]
    if fam == "sil.2":
        v = int(rng.choice([x for x in targets if x != u] or [u]))
        return [{"kind": "silence", "t0": t_on, "t1": snap(min(t_on + rng.uniform(0.05, 0.3), t_end)), "targets": sorted({u, v})}]
    if fam == "edge.w":
        edges = [e for e in s.edges if e[0] in targets] or s.edges
        if not edges:
            return None
        e = edges[int(rng.integers(0, len(edges)))]
        depth = min(0.95, 0.5 * mult)
        return [{"kind": "edge_scale", "t0": t_on, "t1": snap(min(t_on + rng.uniform(0.1, 0.4), t_end)), "edges": [e],
                 "factor": round(1.0 - depth, 6)}]
    if fam == "param.1":
        fields = cap["param"].get("fields") or []
        if not fields:
            return None
        fld = str(rng.choice(fields))
        m = cap["param"]["moderate"][fld]
        if fld == "threshold":
            val = sgn * mult * m
        else:
            val = max(0.05, 1.0 + sgn * mult * m) if sgn < 0 else 1.0 + mult * m
        return [{"kind": "param", "t0": t_on, "t1": snap(min(t_on + rng.uniform(0.1, 0.4), t_end)), "targets": {str(u): {fld: val}}}]
    if fam == "seq.train":
        npl = int(rng.integers(3, 6))
        w = snap(0.02)
        gap = snap(rng.uniform(0.02, 0.06))
        amp = sgn * mult * mc
        return [{"kind": "current", "t0": snap(t_on + i * (w + gap)), "t1": snap(t_on + i * (w + gap) + w), "targets": {str(u): amp}}
                for i in range(npl)]
    raise ValueError(fam)


class _Builder:
    def __init__(self, s):
        self.s = s
        self.rng = np.random.default_rng(_seed("calib", s.system_id))
        self.cap = s.capability()
        self.base = s.base_protocol()
        self.lo, self.hi = self.cap["stimulus"]["range"]
        self.max_on = self.cap["stimulus"]["max_onset"]
        self.out: list[tuple[dict, dict]] = []
        self.pt = public_targets(s, np.random.default_rng(_seed("targets", s.system_id)))
        # the benchmark never draws a kind the capability does not publish: the rotation is reduced (edge.w without edge_scale,
        # param.1 without parameter fields)
        need = {"edge.w": self.cap["edge_scale"].get("supported", False), "param.1": self.cap["param"].get("supported", False)}
        self.fams = [f for f in ROTATIONS[rotation_of(s)] if need.get(f, True)] or ["kick.1"]
        self.n_fam = 0

    def lvl(self, a):
        return [a] * self.s.input_dim if self.s.input_dim > 1 else a

    def seed(self) -> int:
        return int(self.rng.integers(0, 10 ** 9))

    def add(self, p, meta) -> int:
        self.out.append((p, meta))
        return len(self.out) - 1

    def nominal(self, seed, st) -> int:
        return self.add(dict(self.base, params_seed=seed), {"kind": "obs.nominal", "set": st})

    def stim(self, st, multi) -> int:
        s, rng = self.s, self.rng
        on = P.snap(rng.uniform(0.02, self.max_on), s.dt)
        sch = [[0.0, self.lvl(0.0)], [on, self.lvl(float(rng.uniform(self.lo, self.hi)))]]
        if multi:                                          # 1-2 further level changes
            t = on
            for _ in range(int(rng.integers(1, 3))):
                t = P.snap(t + rng.uniform(0.3, 0.7) * s.t_end_default / 2.0, s.dt)
                if t >= s.t_end_default - 10 * s.dt:
                    break
                sch.append([t, self.lvl(float(rng.uniform(self.lo, self.hi)))])
        return self.add(dict(self.base, params_seed=self.seed(), stimulus=sch), {"kind": "obs.stim", "set": st})

    def restart(self, src: int, st) -> int:
        """A nominal restart: from a random sample at 25-90 % of the (nominal) source record, same draw, nominal input."""
        s = self.s
        q_src = self.out[src][0]
        t_s = P.snap(self.rng.uniform(*RESTART_RANGE) * s.t_end_default, s.dt)
        key = hashlib.sha256(f"{s.system_id}:{src}:{q_src['params_seed']}".encode()).hexdigest()[:24]
        p = dict(self.base, params_seed=q_src["params_seed"], stimulus=[[0.0, self.lvl(1.0)]],
                 r0={"kind": "restart", "key": key, "t": t_s})
        return self.add(p, {"kind": "obs.init", "set": st, "restart_from": (src, t_s)})

    def wnoise(self, st, i) -> int:
        sd = round(float(self.rng.uniform(0.02, 0.1)), 4)
        return self.add(dict(self.base, params_seed=self.seed(), weight_noise={"sd": sd, "seed": int(_seed("wn", st, i) % 10 ** 6)}),
                        {"kind": "obs.wnoise", "set": st})

    def intervention(self, st, twin=True, seed=None) -> bool:
        s, rng = self.s, self.rng
        for _ in range(10):
            fam = self.fams[self.n_fam % len(self.fams)]
            mult = min(float(MAG_CLASSES[int(rng.integers(0, 4))]) * float(rng.uniform(0.8, 1.25)), 3.0)
            t_on = P.snap(rng.uniform(0.15, 0.5) * s.t_end_default, s.dt)
            ev = _event(fam, s, self.cap, rng, self.pt, t_on, mult)
            if ev is None:
                self.fams = [f for f in self.fams if f != fam] or ["kick.1"]
                continue
            sd = self.seed() if seed is None else seed
            p_int = dict(self.base, params_seed=sd, events=ev)
            try:
                P.validate(p_int)
            except P.ProtocolError:
                continue
            i = self.add(p_int, {"kind": "int", "family": fam, "mult": mult, "set": st})
            if twin:
                self.add(dict(self.base, params_seed=sd), {"kind": "twin", "twin_of": i, "set": st})
            self.n_fam += 1
            return True
        return False


def calibration_protocols(s, n_int: int = 200, n_val: int | None = None, n_test: int = 24) -> list[tuple[dict, dict]]:
    """[(protocol, meta)] for one system; meta: {"kind", "set", "twin_of" (index) or "restart_from" ((source index, time)), ...}.
    n_int = 0 gives the passive records only (D0, validation, passive tests and the event-free pool sources)."""
    b = _Builder(s)
    n_val = n_int // 5 if n_val is None else n_val
    if n_int == 0:
        n_test = 0
    # D0
    nom = [b.nominal(seed, "D0") for seed in range(8)]
    for i in range(12):
        b.stim("D0", multi=i >= 6)
    for i in range(12):
        b.restart(nom[int(b.rng.integers(0, 8))], "D0")
    for i in range(8):
        b.wnoise("D0", i)
    # D1
    for _ in range(n_int):
        b.intervention("D1")
    # validation
    vn = [b.nominal(b.seed(), "val") for _ in range(2)]
    for i in range(3):
        b.stim("val", multi=i >= 1)
    for i in range(3):
        b.restart(vn[i % 2], "val")
    b.wnoise("val", 0)
    for _ in range(n_val):
        b.intervention("val")
    # test
    for _ in range(n_test):
        b.intervention("test")
    tn = []
    for j in range(4):                                     # N, N, I(N-2), I(N-2), ... : each restart from the nominal two before
        a, c = b.nominal(b.seed(), "test.passive"), b.nominal(b.seed(), "test.passive")
        b.restart(a, "test.passive")
        b.restart(c, "test.passive")
        tn += [a, c]
    # pool sources
    for _ in range(8):
        sd = b.seed()
        src = b.nominal(sd, "pool")
        for _ in range(5):
            b.restart(src, "pool")
        for i in range(5):
            b.stim("pool", multi=i >= 2)
        if n_int:
            for _ in range(4):
                b.intervention("pool", twin=False, seed=sd)
    return b.out


def calibration_records(s, n_int: int = 200, *, store=np.float32) -> list[dict]:
    """Simulate every calibration protocol. Restart sources are simulated first (full microstate kept only at the restart times);
    trajectories are stored as float32 like the benchmark's public records."""
    prots = calibration_protocols(s, n_int)
    need: dict[int, set] = {}
    for _, meta in prots:
        if meta.get("restart_from") is not None:
            src, t_s = meta["restart_from"]
            need.setdefault(src, set()).add(int(round(t_s / s.dt)))
    states: dict[tuple, np.ndarray] = {}
    recs, keys = [], []
    for i, (p, meta) in enumerate(prots):
        q = P.validate(p)
        rs = None
        if meta.get("restart_from") is not None:
            src, t_s = meta["restart_from"]
            rs = states[(src, int(round(t_s / s.dt)))]
        if i in need:
            o = s.simulate(q, full=True, restart_state=rs)
            for n in need[i]:
                states[(i, n)] = o["state"][n].copy()
            o = {k: o[k] for k in ("t", "x", "u", "y")}
        else:
            o = s.simulate(q, restart_state=rs)
        key = hashlib.sha256(json.dumps(q, sort_keys=True).encode() + str(len(recs)).encode()).hexdigest()[:24]
        keys.append(key)
        rec = {"t": o["t"], "x": np.asarray(o["x"], dtype=store), "u": o["u"], "y": np.asarray(o["y"], dtype=store), "protocol": q,
               "key": key, "meta": {}, "split": meta.get("set")}
        if meta.get("twin_of") is not None:
            rec["meta"]["twin_of"] = keys[meta["twin_of"]]
        recs.append(rec)
    return recs


def sysrec_of(s) -> dict:
    return {"observed": list(s.observed), "targets_public": public_targets(s, np.random.default_rng(_seed("targets", s.system_id))),
            "capability": s.capability()}
