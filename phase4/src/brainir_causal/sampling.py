"""The PUBLIC-POLICY SAMPLER and the capability rules of the benchmark (benchmarks/causal_state_v1/PROTOCOL.md sections 3-4; public:
model workers and method rooms import it). Moved verbatim from the orchestrator module `suites` (which imports it back; review H round
3, NEW-3): `normalize_capability` (every threshold the family rules and the samplers need), the magnitude classes, `FamilySampler`
(protocols of every vocabulary family for one system, capability-aware, deterministic given the rng), `intervention_families`,
`feasible`, `Spec` and the public seed function. Nothing here reads a salt or a hidden file."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

import numpy as np

from . import families as F
from . import protocol as P

HIDDEN_SEED_BASE = 10**9
MAG_MULT = {"below": 0.1, "weak": 0.3, "moderate": 1.0, "strong": 3.0}
MAG_CLASSES = tuple(MAG_MULT)
JITTER = (0.8, 1.25)
ONSET_FRAC = (0.15, 0.5)
HORIZON_FRACTIONS = {"short": 0.025, "medium": 0.125, "long": 0.5}
EDGE_DEPTH_MAX = 0.95
P_PERSIST = 0.3
#: the restart time of an 'obs.init' trajectory in its nominal source, as a fraction of the source's duration (LOG P4-D36)
INIT_T_FRAC = (0.25, 0.9)
N_TARGETS_NEEDED = {"kick.2": 2, "pulse.2": 2, "sil.2": 2, "kick.g": 3, "pulse.g": 3, "sil.g": 3}


def public_seed_of(*parts) -> int:
    """A deterministic PUBLIC-range seed from the parts (no salt)."""
    return int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12], 16) % HIDDEN_SEED_BASE


def normalize_capability(cap: dict | None, *, t_end: float, dt: float, input_dim: int = 1) -> dict:
    """The capability record with every threshold the family rules and the samplers need; an explicit value always wins."""
    c = json.loads(json.dumps(cap or {}))
    for kind in ("kick", "current", "current_seq"):
        k = c.setdefault(kind, {})
        k.setdefault("supported", kind != "current_seq" or bool(c.get("current", {}).get("supported")))
        if "moderate" not in k and "max" in k:
            k["moderate"] = float(k["max"]) / 3.0
        k.setdefault("moderate", 1.0)
        k.setdefault("max", 3.0 * float(k["moderate"]))
        k.setdefault("hi_range", [1.5 * float(k["max"]), 3.0 * float(k["max"])])
    cur = c["current"]
    cur.setdefault("pulse_max_duration", round(0.075 * t_end, 9))
    cur.setdefault("sustained_min_duration", max(float(cur["pulse_max_duration"]), round(0.15 * t_end, 9)))
    c["current_seq"].setdefault("min_seg_steps", P.MIN_SEG_STEPS)
    c.setdefault("silence", {}).setdefault("supported", False)
    e = c.setdefault("edge_scale", {})
    e.setdefault("supported", False)
    e.setdefault("moderate", 0.3)
    e.setdefault("max", min(EDGE_DEPTH_MAX, 3.0 * float(e["moderate"])))     # weakening DEPTH (1 - factor), development maximum
    e.setdefault("factor_range", [0.0, 2.0])
    pm = c.setdefault("param", {})
    pm.setdefault("supported", False)
    pm.setdefault("fields", ["gain", "threshold", "tau"])
    mod = pm.setdefault("moderate", {})
    for fld, v in (("gain", 0.3), ("threshold", 1.0), ("tau", 0.3)):
        mod.setdefault(fld, v)
    init = c.setdefault("init", {})
    # an explicit initial state IS a kick at t = 0 (bit-identical; review T, B3): never a development / public-policy protocol on any
    # system (LOG P4-D36); restarts stay allowed. A generator's per-unit list of settable units never enters a record (review T, M1)
    init["state"] = False
    init.setdefault("restart", True)
    init["units"] = "observed"
    st = c.setdefault("stimulus", {})
    st.setdefault("channels", int(input_dim))
    st.setdefault("nominal_level", 1.0)
    st.setdefault("max_onset", round(0.075 * t_end, 9))
    st.setdefault("range", [0.55, 1.45])
    st.setdefault("allow_zero", True)
    pr = c.setdefault("params", {})
    pr["public_seed_max"] = HIDDEN_SEED_BASE   # the benchmark's public range for EVERY system (a generator's own narrower default is replaced; LOG P4-D27)
    pr.setdefault("nominal_seed", None)
    c.setdefault("weight_noise", {}).setdefault("max_sd", 0.1)
    c.setdefault("obs_noise", {}).setdefault("max_sd", 0.5)
    tm = c.setdefault("timing", {})
    tm["dt_allowed"] = [float(dt)]            # development dt = the nominal dt ONLY (review H, M3: coarser sampling is a Level C OOD shift)
    tm.setdefault("t_end_max", 2.0 * float(t_end))
    c.setdefault("latent", {}).setdefault("supported", False)
    pn = c.setdefault("process_noise", {})
    pn.setdefault("supported", False)
    # per-unit fields reveal unit roles (review T, M1: role decoded at 93-100 % from admissible ranges and noise scales): one
    # system-wide value instead, for every system (LOG P4-D36); `assert_public_record` refuses any per-unit list left
    ar = c.get("admissible_range")
    if isinstance(ar, dict) and (isinstance(ar.get("lo"), list) or isinstance(ar.get("hi"), list)):
        lo, hi = ar.get("lo"), ar.get("hi")
        c["admissible_range"] = {"lo": float(np.min(lo)) if isinstance(lo, list) else lo,
                                 "hi": float(np.max(hi)) if isinstance(hi, list) else hi}
    per_unit_sd = pn.pop("unit_sd_per_sqrt_s", None)
    if isinstance(per_unit_sd, list) and per_unit_sd:
        pn["sd_per_sqrt_s"] = float(np.median(np.asarray(per_unit_sd, dtype=np.float64)))
        if isinstance(pn.get("units"), str):
            pn["units"] = ("the increment per substep of a unit is sd * sd_per_sqrt_s * sqrt(h) * xi (sd_per_sqrt_s: the system's median "
                           "unit noise scale; per-unit scales are not public)")
    return c


def per_unit_lists(obj, path: str = "capability", min_len: int = 3) -> list[str]:
    """Paths of numeric lists of length >= min_len (per-unit vectors) inside a record part (review T, M1)."""
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += per_unit_lists(v, f"{path}.{k}", min_len)
    elif isinstance(obj, list):
        if len(obj) >= min_len and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in obj):
            out.append(path)
        else:
            for i, v in enumerate(obj):
                if isinstance(v, (dict, list)):
                    out += per_unit_lists(v, f"{path}[{i}]", min_len)
    return out


def moderate_value(cap: dict, kind: str, fld: str | None = None) -> float:
    if kind == "param":
        return float(cap["param"]["moderate"][fld])
    return float(cap[kind]["moderate"])


def class_value(cap: dict, kind: str, mclass: str, rng: np.random.Generator, fld: str | None = None) -> float:
    """A positive magnitude of class `mclass` for this kind (and parameter field). The strong class is jittered DOWNWARD only
    (U(0.8, 1.0)), so it never exceeds the development maximum 3 m_s (which would make it a `*.hi` family)."""
    if mclass == "hi":
        lo, hi = cap[kind]["hi_range"]
        return float(rng.uniform(lo, hi))
    jit = rng.uniform(JITTER[0], 1.0) if mclass == "strong" else rng.uniform(*JITTER)
    v = float(MAG_MULT[mclass] * moderate_value(cap, kind, fld) * jit)
    mx = cap.get(kind, {}).get("max") if kind != "param" else None
    return min(v, float(mx)) if mx is not None else v


def _shift_events(events: list[dict], shift: float) -> list[dict]:
    out = []
    for e in events:
        e2 = json.loads(json.dumps(e))
        for key in ("t", "t0", "t1"):
            if e2.get(key) is not None:
                e2[key] = round(float(e2[key]) + shift, 9)
        out.append(e2)
    return out


def relative_events(events: list[dict], onset: float) -> list[dict]:
    """Events with times relative to the onset (time 0 = the onset sample)."""
    return _shift_events(events, -float(onset))


@dataclass
class Spec:
    """One planned trajectory: its protocol and its role in the benchmark."""
    protocol: dict
    split: str                              # train | val | twin | test | pool_src | component
    role: str = ""                          # d0 | d1 | in | target | near | far | hidden | ood:<cat> | robust:<cond> | passive | pool_src
    family: str = ""                        # the planned family (the stored label is always families.family_of)
    mclass: str = "na"
    target_set: tuple = ()
    cell: str = ""                          # identity cell of test items
    state: int = 0
    twin: bool = False                      # simulate the counterfactual twin too
    meta: dict = field(default_factory=dict)
    spares: list = field(default_factory=list)  # replacement parameter seeds, used in order when the simulation fails (review H, M4)


def _runs(on: list[bool]) -> tuple[list[int], list[int], list[int]]:
    starts, lengths = [], []
    i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]:
                j += 1
            starts.append(i)
            lengths.append(j - i)
            i = j
        else:
            i += 1
    gaps = [starts[k + 1] - (starts[k] + lengths[k]) for k in range(len(starts) - 1)]
    return starts, lengths, gaps


class FamilySampler:
    """Protocols of every vocabulary family for one system (capability-aware; deterministic given the rng)."""

    def __init__(self, sysrec: dict, rng: np.random.Generator, seed_fn, *, targets: list[int], edges: list | None = None,
                 onset_frac: tuple[float, float] = ONSET_FRAC, stim_range: tuple[float, float] | None = None, t_end: float | None = None):
        self.rec = sysrec
        self.rng = rng
        self.seed_fn = seed_fn
        self.targets = sorted(int(t) for t in targets)
        self.edges = [list(map(int, e)) for e in (edges or [])]
        self.T = float(sysrec["t_end_default"] if t_end is None else t_end)
        self.dt = float(sysrec["dt"])
        self.cap = normalize_capability(sysrec.get("capability"), t_end=float(sysrec["t_end_default"]), dt=self.dt,
                                        input_dim=int(sysrec.get("input_dim", 1)))
        self.n_u = int(sysrec.get("input_dim", 1))
        self.onset_frac = onset_frac
        st = self.cap["stimulus"]
        self.stim_range = tuple(stim_range or st["range"])
        lev = st["nominal_level"]
        self.level = float(lev[0]) if isinstance(lev, (list, tuple)) else float(lev)

    # ------------------------------------------------------------------ basics
    def snap(self, t: float) -> float:
        return P.snap(t, self.dt)

    def horizon(self, name: str) -> float:
        return HORIZON_FRACTIONS[name] * float(self.rec["t_end_default"])

    def value(self, level) -> float | list:
        if self.n_u == 1:
            return float(level[0]) if isinstance(level, (list, tuple)) else float(level)
        if isinstance(level, (list, tuple)):
            return [float(v) for v in level]
        return [float(level)] * self.n_u

    def base(self, *, level=None, t_on: float | None = None, params_seed: int | None = None) -> dict:
        max_on = float(self.cap["stimulus"]["max_onset"])
        t_on = self.snap(self.rng.uniform(self.dt, max(self.dt, max_on))) if t_on is None else self.snap(t_on)
        lev = self.level if level is None else level
        return {"system": self.rec["system_id"], "params_seed": int(self.seed_fn() if params_seed is None else params_seed),
                "weight_noise": None, "r0": {"kind": "rest"}, "t_end": self.T, "dt": self.dt,
                "stimulus": [[0.0, self.value(0.0)], [t_on, self.value(lev)]], "events": [], "obs_noise": None}

    def onset(self, lo: float | None = None, hi: float | None = None) -> float:
        a = self.onset_frac[0] * self.T if lo is None else lo
        b = self.onset_frac[1] * self.T if hi is None else hi
        return self.snap(self.rng.uniform(a, b))

    def pick_targets(self, n: int, pool: list[int] | None = None) -> list[int]:
        pool = self.targets if pool is None else pool
        if len(pool) < n:
            raise ValueError(f"needs {n} targets, the system has {len(pool)}")
        return sorted(int(x) for x in self.rng.choice(pool, size=n, replace=False))

    def sign(self, p_pos: float = 0.5) -> float:
        return 1.0 if self.rng.random() < p_pos else -1.0

    def d_pulse(self) -> float:
        return float(self.cap["current"]["pulse_max_duration"])

    def d_sustain(self) -> float:
        return float(self.cap["current"]["sustained_min_duration"])

    def pulse_duration(self) -> float:
        dp = self.d_pulse()
        lo = max(5 * self.dt, 0.1 * dp)
        return max(self.dt, self.snap(self.rng.uniform(lo, max(lo, dp))))

    def window_duration(self) -> float:
        lo = self.d_pulse()
        hi = max(lo, min(3.0 * self.d_sustain(), 0.4 * self.T))
        return max(self.dt, self.snap(self.rng.uniform(lo, hi)))

    def end_or_none(self, t0: float, dur: float, p_persist: float = P_PERSIST) -> float | None:
        if self.rng.random() < p_persist:
            return None
        return min(self.T, self.snap(t0 + dur))

    def init_t_frac(self) -> float:
        """The restart time (fraction of the source's duration) of an 'obs.init' trajectory in its nominal source."""
        return round(float(self.rng.uniform(*INIT_T_FRAC)), 6)

    # ------------------------------------------------------------------ observational families
    def obs(self, family: str, *, params_seed: int | None = None) -> dict:
        if family in ("obs.nominal", "obs.param"):
            return self.base(params_seed=params_seed)
        if family == "obs.stim":
            lo, hi = self.stim_range
            p = self.base(level=float(self.rng.uniform(lo, hi)), params_seed=params_seed)
            if self.rng.random() < 0.5:
                p["stimulus"].append([self.snap(self.rng.uniform(0.3, 0.6) * self.T), self.value(float(self.rng.uniform(lo, hi)))])
            if self.rng.random() < 0.4:
                p["stimulus"].append([self.snap(self.rng.uniform(0.62, 0.9) * self.T), self.value(0.0)])
            p["stimulus"] = sorted(p["stimulus"], key=lambda r: r[0])
            if F.is_nominal_stimulus(P.validate(p)["stimulus"], {"capability": self.cap}):
                p["stimulus"].append([self.snap(0.5 * self.T), self.value(lo)])
            return p
        if family == "obs.init":
            # a restart from a NOMINAL passive trajectory of the same system (LOG P4-D36): it needs its source, so it is planned with
            # `init_spec` (the protocol is completed by `run_specs` once the source is simulated)
            raise ValueError("obs.init is a restart from a nominal passive trajectory: plan it with suites.init_spec(sampler, src)")
        if family == "obs.wnoise":
            p = self.base(params_seed=params_seed)
            p["weight_noise"] = {"sd": round(float(self.rng.uniform(0.02, float(self.cap["weight_noise"]["max_sd"]))), 4),
                                 "seed": int(self.seed_fn())}
            return p
        raise ValueError(family)

    # ------------------------------------------------------------------ single-event families
    def event(self, family: str, t0: float, targets: list[int], mclass: str, edges: list | None = None) -> dict:
        cap = self.cap
        if family in ("kick.1", "kick.2", "kick.g", "kick.hi"):
            return {"kind": "kick", "t": t0, "delta": {str(u): round(self.sign() * class_value(cap, "kick", mclass, self.rng), 6)
                                                        for u in targets}}
        if family in ("pulse.1", "pulse.2", "pulse.g", "pulse.hi"):
            s = self.sign(0.75)
            return {"kind": "current", "t0": t0, "t1": min(self.T, self.snap(t0 + self.pulse_duration())),
                    "targets": {str(u): round(s * class_value(cap, "current", mclass, self.rng), 6) for u in targets}}
        if family in ("act.1", "inh.1"):
            s = 1.0 if family == "act.1" else -1.0
            dur = self.snap(self.rng.uniform(self.d_sustain(), 2.5 * self.d_sustain()))
            t1 = self.end_or_none(t0, dur)
            if t1 is not None and t1 - t0 < self.d_sustain() - 1e-9:
                t1 = None
            return {"kind": "current", "t0": t0, "t1": t1,
                    "targets": {str(u): round(s * class_value(cap, "current", mclass, self.rng), 6) for u in targets}}
        if family in ("sil.1", "sil.2", "sil.g", "sil.1p"):
            if family == "sil.1p":
                t1 = None
            elif family == "sil.1":
                t1 = min(self.T, self.snap(t0 + self.window_duration()))
            else:
                t1 = self.end_or_none(t0, self.window_duration())
            return {"kind": "silence", "t0": t0, "t1": t1, "targets": [int(u) for u in targets]}
        if family in ("edge.w", "edge.rm"):
            if family == "edge.rm":
                f = 0.0
            else:
                depth = min(EDGE_DEPTH_MAX, class_value(cap, "edge_scale", mclass if mclass in MAG_MULT else "moderate", self.rng))
                f = round(1.0 - depth, 6)
            return {"kind": "edge_scale", "t0": t0, "t1": self.end_or_none(t0, self.window_duration()), "edges": [list(e) for e in edges],
                    "factor": f}
        if family == "param.1":
            fields = list(cap["param"]["fields"])
            fld = fields[int(self.rng.integers(len(fields)))]
            v = class_value(cap, "param", mclass, self.rng, fld)
            change = {fld: round(max(0.05, 1.0 + self.sign() * v), 6)} if fld in ("gain", "tau") else {fld: round(self.sign() * v, 6)}
            return {"kind": "param", "t0": t0, "t1": self.end_or_none(t0, self.window_duration()), "targets": {str(targets[0]): change}}
        raise ValueError(family)

    # ------------------------------------------------------------------ patterns
    def sequence(self, family: str, t0: float, target: int, mclass: str) -> dict:
        min_seg = int(self.cap["current_seq"].get("min_seg_steps", P.MIN_SEG_STEPS))
        seg = self.snap(max(min_seg * self.dt, self.d_pulse() / 4.0))
        amp = round(class_value(self.cap, "current", mclass, self.rng), 6)
        if family == "seq.train":
            on, off, n = int(self.rng.integers(1, 3)), int(self.rng.integers(2, 4)), int(self.rng.integers(3, 6))
            vals = ([amp] * on + [0.0] * off) * n
            vals = vals[: len(vals) - off]
        elif family == "seq.pp":
            on1, gap, on2 = int(self.rng.integers(1, 3)), int(self.rng.integers(3, 8)), int(self.rng.integers(1, 3))
            vals = [amp] * on1 + [0.0] * gap + [amp] * on2
        elif family == "seq.prbs":
            vals = [amp, 0.0, amp, amp, 0.0, 0.0, amp]
            for _ in range(200):
                m = int(self.rng.integers(12, 25))
                bits = self.rng.random(m) < 0.5
                bits[0] = True
                cand = [amp if b else 0.0 for b in bits]
                while cand and cand[-1] == 0.0:
                    cand.pop()
                st, ln, gp = _runs([v != 0.0 for v in cand])
                if len(st) >= 3 and not (len(set(ln)) == 1 and len(set(gp)) == 1):
                    vals = cand
                    break
        elif family == "seq.chirp":
            m = int(self.rng.integers(20, 41))
            f0, f1 = 1.0 / (m * seg), 6.0 / (m * seg)
            tt = np.arange(m) * seg
            ph = 2 * np.pi * (f0 * tt + 0.5 * (f1 - f0) / (m * seg) * tt ** 2)
            vals = [round(float(amp * math.sin(p_)), 6) for p_ in ph]
            if len({round(v, 12) for v in vals}) < 3:
                vals = [round(amp * (j % 3 - 1), 6) for j in range(m)]
        else:
            raise ValueError(family)
        span = seg * len(vals)
        if t0 + span > self.T - self.dt:
            # too long for the window: shortest segments first, then trailing segments dropped; the family must survive
            seg = self.snap(min_seg * self.dt)
            max_len = int((self.T - self.dt - t0) / seg)
            if len(vals) > max_len:
                vals = vals[:max_len]
                while vals and vals[-1] == 0.0:
                    vals.pop()
            span = seg * len(vals)
            if not vals or t0 + span > self.T:
                raise ValueError(f"{family} does not fit into the window")
            st, ln, gp = _runs([v != 0.0 for v in vals])
            ok = {"seq.train": len(st) >= 3 and len(set(ln)) == 1 and len(set(gp)) == 1, "seq.pp": len(st) == 2,
                  "seq.prbs": len(st) >= 3 and not (len(set(ln)) == 1 and len(set(gp)) == 1),
                  "seq.chirp": len({round(v, 12) for v in vals}) >= 3}[family]
            if not ok:
                raise ValueError(f"{family} does not fit into the window")
        return {"kind": "current_seq", "t0": t0, "seg": seg, "targets": {str(int(target)): [float(v) for v in vals]}}

    def composition(self, family: str, t0: float, targets: list[int]) -> tuple[list[dict], dict]:
        """Two different single interventions: `comp.seq` = b starts after a ended; `comp.sim` = b overlaps a. Returns the events and
        the components {"a": [...], "b": [...], "families": [fa, fb]} (absolute times)."""
        kinds = [f for k, f in (("kick", "kick.1"), ("current", "pulse.1"), ("silence", "sil.1"), ("param", "param.1"))
                 if self.cap.get(k, {}).get("supported")]
        if len(kinds) < 2:
            raise ValueError("composition needs two supported kinds")
        fa, fb = [kinds[i] for i in self.rng.choice(len(kinds), size=2, replace=False)]
        if family == "comp.sim" and fa == "kick.1":
            fa, fb = fb, fa                                  # the first (windowed) component must be able to overlap the second
        ta = targets[0]
        tb = targets[1] if len(targets) > 1 else targets[0]
        ea = self.event(fa, t0, [ta], "moderate")
        if ea["kind"] != "kick" and ea.get("t1") is None:
            ea["t1"] = min(self.T, self.snap(t0 + self.window_duration()))
        end_a = t0 + self.dt if ea["kind"] == "kick" else float(ea["t1"])
        if family == "comp.seq":
            tb0 = self.snap(end_a + self.rng.uniform(self.dt, max(2 * self.dt, self.d_pulse())))
        else:
            tb0 = self.snap(t0 + self.rng.uniform(0.0, max(self.dt, 0.8 * (end_a - t0))))
            tb0 = min(tb0, self.snap(end_a - self.dt))
        tb0 = min(max(t0, tb0), self.snap(self.T - 2 * self.dt))
        eb = self.event(fb, tb0, [tb], "moderate")
        if eb["kind"] != "kick" and eb.get("t1") is None:
            eb["t1"] = min(self.T, self.snap(eb["t0"] + self.window_duration()))
        return [ea, eb], {"a": [ea], "b": [eb], "families": [fa, fb]}

    # ------------------------------------------------------------------ one protocol of a family
    def make(self, family: str, *, targets: list[int] | None = None, edges: list | None = None, mclass: str | None = None,
             onset: float | None = None, params_seed: int | None = None, level=None) -> tuple[dict, dict]:
        """(protocol, spec info) of one trajectory of `family`; interventions start at `onset`. Explicit `targets` / `edges` are
        used exactly (identity cells)."""
        if family in F.OBS:
            return self.obs(family, params_seed=params_seed), {"family": family, "targets": (), "mclass": "na", "onset": None}
        p = self.base(level=self.level if level is None else level, params_seed=params_seed)
        t0 = self.onset() if onset is None else self.snap(onset)
        if family in ("edge.w", "edge.rm"):
            if edges is None:
                if not self.edges:
                    raise ValueError("no scalable edges")
                k = min(len(self.edges), int(self.rng.integers(1, 3)))
                edges = [list(self.edges[i]) for i in sorted(self.rng.choice(len(self.edges), size=k, replace=False))]
            mc = "na" if family == "edge.rm" else (mclass or "moderate")
            p["events"] = [self.event(family, t0, [], mc, edges=edges)]
            return p, {"family": family, "targets": tuple(sorted({int(x) for e in edges for x in e})), "edges": edges, "mclass": mc,
                       "onset": t0}
        n_t = {"kick.2": 2, "pulse.2": 2, "sil.2": 2, "kick.g": int(self.rng.integers(3, 5)), "pulse.g": int(self.rng.integers(3, 5)),
               "sil.g": int(self.rng.integers(3, 5))}.get(family, 1)
        tg = sorted(int(t) for t in targets) if targets is not None else self.pick_targets(n_t)
        mc = "hi" if family in ("kick.hi", "pulse.hi") else ("na" if family.startswith("sil.") else (mclass or "moderate"))
        if family in F.SEQ:
            p["events"] = [self.sequence(family, t0, tg[0], "moderate" if mc in ("na",) else mc)]
        elif family in F.COMP:
            p["events"], comp = self.composition(family, t0, tg)
            return p, {"family": family, "targets": tuple(tg), "mclass": "na", "onset": t0, "components": comp}
        else:
            p["events"] = [self.event(family, t0, tg, mc)]
        return p, {"family": family, "targets": tuple(tg), "mclass": mc, "onset": t0}


def intervention_families(split: dict) -> list[str]:
    return [f for f in split["families_train"] if f in F.INTERVENTION_FAMILIES]


def feasible(family: str, targets: list[int], edges: list) -> bool:
    if family in ("edge.w", "edge.rm"):
        return bool(edges)
    return len(targets) >= N_TARGETS_NEEDED.get(family, 1)
