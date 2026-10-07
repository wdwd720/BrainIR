"""SyntheticSystem: the public interface of one synthetic system (docs/SYNTHETIC_BENCHMARK_CONTRACT.md section 4)."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import OrderedDict

import numpy as np

import dataclasses

from . import protocol as P
from .engine import CORE, ENGINE_ID, FOL, GEN, NOMINAL_SEED, OBS_NAMES, RELAY, Spec, compile_draw
from .integrate import core_kick, simulate as _simulate

try:                                  # BLAS single-threaded inside simulate: the products are small; spinning worker threads
    from threadpoolctl import ThreadpoolController     # would only burn CPU (measured 4x CPU for the same wall time)
    _TPC = ThreadpoolController()
except Exception:                     # pragma: no cover
    _TPC = None

NOMINAL_ONSET = 0.1
PULSE_MAX = 0.15
SUSTAINED_MIN = 0.3
PROBE_PULSE = 0.05
PARAM_REF = 0.1            # reference window of param / edge_scale probes (s): the moderate is defined for this duration
ES_WINDOW = (3.0, 10.0)    # the "moderate" detectability class: a published moderate must give a median ES in [3, 10)
PROBE_UNITS = 10 ** 6      # probe targets: EVERY targetable core unit (the population the benchmark draws core items from)
PUBLISHED_PARAM_FIELDS = ("threshold",)
TARGET_ES = 8.0            # "moderate": median detectability ES = RMS(effect) / (0.05 sd(y)) of about 8 (class moderate [3, 10))
LIFT_D = 5                 # lifts complete LIFT_D samples after their start (one common completion sample for every lift)
LIFT_TOL = 1e-3            # stated miss tolerance of returned lifts: ||z(j) - z_twin(j) - dz|| / ||dz|| (z_scale-whitened)

# PUBLIC UNITS (review round 3, B1). Every published magnitude and scale is a draw from ONE type-independent distribution: each
# system has its own unit of state (kicks, thresholds, the admissible range, process noise), of current, of x and of y, chosen so
# that its moderate kick / moderate current / obs_scale.x / obs_scale.y equal log-uniform draws in the ranges below (seeded by the
# opaque system id). The admissible range and the process-noise scale are the same constants in public units for every system.
# Internally (spec, microstates, truth) the model keeps its own units; `units()` gives the factors (public = factor x internal).
UNIT_RANGES = {"kick": (3.0, 10.0), "current": (3.0, 10.0), "x": (10.0, 100.0), "y": (5.0, 50.0)}
RANGE_PUB = 500.0          # admissible range [-500, 500] in public state units, every system
NOISE_PUB = 100.0          # process-noise scale per sqrt(s) in public state units, every system


def _jsonable(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    return o


def _arr_hash(a) -> str:
    a = np.ascontiguousarray(np.asarray(a, dtype=np.float64))
    return hashlib.sha256(a.tobytes() + str(a.shape).encode()).hexdigest()[:16]


class SyntheticSystem:
    def __init__(self, spec: Spec, meta: dict, info: dict, *, system_id: str, dt: float = 0.001, t_end_default: float = 2.0):
        self.spec = spec
        self.meta = meta
        self.info = info                      # truth-side description (type, variant, trap, ...)
        self.system_id = system_id
        self.engine_id = ENGINE_ID
        self.n_units = spec.N
        self.observed = list(spec.observed)
        self.readout_dim = spec.latent.ro.n_y
        self.input_dim = spec.n_u
        self.dt = float(dt)
        self.t_end_default = float(t_end_default)
        self.targetable = sorted(int(u) for u in meta["targetable"])
        self.edges = [list(e) for e in meta["edges"]]
        self._draws: OrderedDict = OrderedDict()
        self._cap = None
        self._obs_scale = None
        self._hash = None
        self._dsens = None
        self._units = None
        self._pr = None
        spec.lo = np.full(spec.N, -np.inf)          # set in public units by units(); unbounded while the probes run
        spec.hi = np.full(spec.N, np.inf)
        spec.noise_scale = np.full(spec.N, NOISE_PUB)

    # ------------------------------------------------------------------------------------------------ public units
    def units(self) -> dict:
        """Public-unit factors (public value = factor x internal value): "v" state (kicks, thresholds, range, process noise, r0
        values), "I" current, "x" observations, "y" readout. Computed once from the internal probe (moderate magnitudes) and the
        nominal trajectory (obs scales); it also fixes the internal admissible range +-RANGE_PUB / v and noise NOISE_PUB / v."""
        if self._units is None:
            pr = self._probe()
            nom = self._simulate_internal(self.base_protocol())
            ox = max(float(np.percentile(np.abs(nom["x"]), 99)), 1e-3)
            oy = max(float(np.sqrt(np.mean(np.var(nom["y"], axis=0)))), 1e-6)
            r = np.random.default_rng(int.from_bytes(hashlib.sha256(("units:" + self.system_id).encode()).digest()[:8], "little"))
            pub = {k: round(float(np.exp(r.uniform(math.log(a), math.log(b)))), 4) for k, (a, b) in sorted(UNIT_RANGES.items())}
            # the readout unit is drawn from the implementation-group key: members of a group share the internal readout and so
            # keep identical public readouts (for other systems the group key is unique)
            ry = np.random.default_rng(int.from_bytes(hashlib.sha256(("units-y:" + self.spec.group_key).encode()).digest()[:8], "little"))
            pub["y"] = round(float(np.exp(ry.uniform(math.log(UNIT_RANGES["y"][0]), math.log(UNIT_RANGES["y"][1])))), 4)
            u = {"v": pub["kick"] / pr["kick"]["moderate"], "I": pub["current"] / pr["current"]["moderate"], "x": pub["x"] / ox,
                 "y": pub["y"] / oy}
            self.spec.lo = np.full(self.spec.N, -RANGE_PUB / u["v"])
            self.spec.hi = np.full(self.spec.N, RANGE_PUB / u["v"])
            self.spec.noise_scale = np.full(self.spec.N, NOISE_PUB / u["v"])
            self.spec.kick_strong = 2.0 * pr["kick"]["moderate"]      # refine after kicks of 2 m_s and more (strong and kick.hi classes)
            self._units = {"factors": u, "public": pub, "internal": {"kick_moderate": pr["kick"]["moderate"],
                           "current_moderate": pr["current"]["moderate"], "obs_x_p99": ox, "y_sd": oy}}
        return dict(self._units["factors"])

    def _to_internal(self, q: dict) -> dict:
        """A canonical PUBLIC protocol in internal units (kicks, currents, thresholds and r0 values divided by their factors)."""
        u = self.units()
        sv, sI = u["v"], u["I"]
        q = copy.deepcopy(q)
        for e in q["events"]:
            k = e["kind"]
            if k == "kick":
                e["delta"] = {a: float(d) / sv for a, d in e["delta"].items()}
            elif k == "current":
                e["targets"] = {a: float(I) / sI for a, I in e["targets"].items()}
            elif k == "current_seq":
                e["targets"] = {a: [float(I) / sI for I in lst] for a, lst in e["targets"].items()}
            elif k == "param":
                for fl in e["targets"].values():
                    if "threshold" in fl:
                        fl["threshold"] = float(fl["threshold"]) / sv
        if q["r0"]["kind"] == "state":
            q["r0"]["values"] = {a: float(v) / sv for a, v in q["r0"]["values"].items()}
        return q

    def events_to_public(self, events: list[dict]) -> list[dict]:
        """Internal-unit events (kicks, currents) in public units."""
        u = self.units()
        out = []
        for e in copy.deepcopy(events):
            if e["kind"] == "kick":
                e["delta"] = {a: float(d) * u["v"] for a, d in e["delta"].items()}
            elif e["kind"] == "current":
                e["targets"] = {a: float(I) * u["I"] for a, I in e["targets"].items()}
            out.append(e)
        return out

    def _raw(self, qi, d, full, restart_state, nsub=None):
        if _TPC is not None:
            with _TPC.limit(limits=1, user_api="blas"):
                return _simulate(self.spec, d, qi, full=full, restart_state=restart_state, nsub=nsub, process_noise=qi["process_noise"])
        return _simulate(self.spec, d, qi, full=full, restart_state=restart_state, nsub=nsub, process_noise=qi["process_noise"])

    def _run(self, q, d, full=False, restart_state=None, nsub=None) -> dict:
        """Simulate a canonical PUBLIC protocol with draw d; outputs in public units (x, y, x_all, realized kicks)."""
        u = self.units()
        out = self._raw(self._to_internal(q), d, full, restart_state, nsub)
        out["x"] = out["x"] * u["x"]
        out["y"] = out["y"] * u["y"]
        if full:
            out["x_all"] = out["x_all"] * u["x"]
            for r in out["info"].get("kicks_applied", []):
                r["units"] = {a: v * u["v"] for a, v in r["units"].items()}
                r["requested"] = {int(a): float(v) for a, v in q["events"][r["event_index"]]["delta"].items()}
        else:
            for key in ("zh", "x_all"):
                out.pop(key, None)
        out["info"]["system"] = self.system_id
        return out

    def _simulate_internal(self, protocol: dict, full: bool = False, restart_state=None) -> dict:
        """Simulation in INTERNAL units (magnitudes of the protocol and outputs), for the probes and truth functions."""
        q = P.validate(protocol, allow_truth=True)
        d = self._draw(q["params_seed"], q["params_spread"], q["weight_noise"])
        return self._raw(q, d, full, restart_state)

    # ------------------------------------------------------------------------------------------------ identity
    def content_hash(self) -> str:
        if self._hash is None:
            self.units()                              # the public-unit factors and the ranges they fix are part of the system
            blob = self._structure_blob()
            blob["units"] = {k: repr(v) for k, v in sorted(self._units["factors"].items())}
            self._hash = hashlib.sha256(json.dumps(blob, sort_keys=True).encode()).hexdigest()
        return self._hash

    def construction_hash(self) -> str:
        """Hash of the constructed structure (content_hash without the public-unit probe): cheap, for the thread-count test."""
        return hashlib.sha256(json.dumps(self._structure_blob(), sort_keys=True).encode()).hexdigest()

    def _structure_blob(self) -> dict:
        if True:
            s = self.spec
            blob = {"engine": ENGINE_ID, "latent": _jsonable(s.latent.spec()), "k": s.k, "n_u": s.n_u, "role": s.role.tolist(),
                    "loc": s.loc.tolist(), "E": _arr_hash(s.E), "L": _arr_hash(s.L), "b": _arr_hash(s.b), "tau_c": s.tau_c,
                    "tau_c_sd": s.tau_c_sd, "gen": {k: (_arr_hash(v) if isinstance(v, np.ndarray) else v) for k, v in sorted(s.gen.items())},
                    "fol": [_arr_hash(a) if a is not None else None for a in (s.tau_f, s.b_f, s.W_fc, s.W_fg, s.B_f, s.tau_r, s.b_r, s.B_r, s.W_fr,
                                                                              s.W_ff, s.fol_layer, s.W_rc)],
                    "fol_sd": [s.tau_f_sd, s.fol_in_sd],
                    "obs": [_arr_hash(a) for a in (s.obs_kind, s.obs_th, s.obs_s, s.obs_w, s.obs_p)],
                    "observed": s.observed, "h_max": s.h_max, "group": s.group_key, "impl": s.impl_key, "dt": self.dt,
                    "t_end": self.t_end_default, "targetable": self.targetable, "edges": self.edges}
            return blob

    # ------------------------------------------------------------------------------------------------ simulation
    def _draw(self, seed, spread, wn):
        key = (int(seed), float(spread), None if wn is None else (float(wn["sd"]), int(wn["seed"])))
        d = self._draws.get(key)
        if d is None:
            if _TPC is not None:
                with _TPC.limit(limits=1, user_api="blas"):
                    d = compile_draw(self.spec, int(seed), float(spread), wn)
            else:
                d = compile_draw(self.spec, int(seed), float(spread), wn)
            self._draws[key] = d
            if len(self._draws) > 48:
                self._draws.popitem(last=False)
        else:
            self._draws.move_to_end(key)
        return d

    def base_protocol(self, **kw) -> dict:
        p = {"system": self.system_id, "params_seed": NOMINAL_SEED, "t_end": self.t_end_default, "dt": self.dt,
             "stimulus": self.nominal_stimulus(), "events": []}
        p.update(kw)
        return p

    def nominal_stimulus(self, level=1.0):
        v = [level] * self.input_dim if self.input_dim > 1 else level
        z = [0.0] * self.input_dim if self.input_dim > 1 else 0.0
        return [[0.0, z], [NOMINAL_ONSET, v]]

    def simulate(self, protocol: dict, full: bool = False, restart_state=None, *, nsub: int | None = None) -> dict:
        q = P.validate(protocol, allow_truth=True)
        if q["system"] != self.system_id:
            raise P.ProtocolError(f"protocol is for system {q['system']!r}, not {self.system_id!r}")
        d = self._draw(q["params_seed"], q["params_spread"], q["weight_noise"])
        return self._run(q, d, full, restart_state, nsub)

    # ------------------------------------------------------------------------------------------------ parameter draws (truth side)
    # Every trajectory has its own draw (params_seed, params_spread, weight_noise); z is closed GIVEN the draw. The draw reaches z
    # and y only through the latent / readout parameters (Latent.PARAMS, ro_gain included), tau_c (currents, silence and param
    # interventions act through it) and, under weight noise, M_F = L E_F (dz/dt = M_F F(z, u) + ...); generator, relay and follower
    # draws are nuisance (x only).
    DRAW_TOL = 0.5              # f_s: the neglected draw directions jointly change the readout by at most half the floor (RMS)
    DRAW_BASES = 4              # base draws of the pooled sensitivity (nominal + 3 random public draws)
    DRAW_WN_SAMPLES = 8         # weight-noise draws (sd = capability max) sampled to measure their effective dimension

    def _draw_names(self) -> list[str]:
        lat = self.spec.latent
        names = [nm for nm in sorted(lat.params) if float(lat.params[nm][1]) > 0]
        return names + (["tau_c"] if self.spec.tau_c_sd > 0 else [])

    def _eta_of(self, d) -> np.ndarray:
        lat = self.spec.latent
        out = []
        for nm in self._draw_names():
            if nm == "tau_c":
                out.append(math.log(d.tau_c / self.spec.tau_c) / self.spec.tau_c_sd)
                continue
            nom, sd, kind = lat.params[nm]
            v = float(d.P[nm])
            out.append(math.log(v / nom) / sd if kind == "log" else (v - nom) / sd)
        return np.array(out, dtype=float)

    def _draw_from_eta(self, eta, base):
        """`base` (a compiled draw) with its z / readout parameters replaced by the standardized coordinates eta."""
        lat = self.spec.latent
        Pz = dict(base.P)
        tau = base.tau_c
        for nm, e in zip(self._draw_names(), np.asarray(eta, dtype=float)):
            if nm == "tau_c":
                tau = self.spec.tau_c * math.exp(self.spec.tau_c_sd * float(e))
                continue
            nom, sd, kind = lat.params[nm]
            Pz[nm] = nom * math.exp(sd * float(e)) if kind == "log" else nom + sd * float(e)
        return dataclasses.replace(base, P=Pz, f=lat.field(Pz), tau_c=tau)

    def _sim_draw(self, q, d, restart_state=None, full=False):
        return self._run(q, d, full, restart_state)

    def draw_parameters(self, protocol: dict) -> np.ndarray:
        """Standardized coordinates eta of the protocol's draw, one per parameter that can reach z or y (`draw_sensitivity()["names"]`:
        the drawn latent / readout parameters in sorted order, then log tau_c): eta = params_spread * xi with xi the draw's standard
        normal deviate (log-normal parameters: log(p / p_nom) / sd; normal ones: (p - p_nom) / sd); 0 for the nominal draw."""
        q = P.validate(protocol, allow_truth=True)
        return self._eta_of(self._draw(q["params_seed"], q["params_spread"], q["weight_noise"]))

    def simulate_draw(self, protocol: dict, eta, *, restart_state=None, full: bool = False) -> dict:
        """Truth-side: simulate the protocol with the z / readout parameters of its draw replaced by eta (everything else, incl.
        weight noise and the nuisance draws, from the protocol's own draw)."""
        q = P.validate(protocol, allow_truth=True)
        d = self._draw_from_eta(eta, self._draw(q["params_seed"], q["params_spread"], q["weight_noise"]))
        return self._sim_draw(q, d, restart_state, full)

    def _draw_probes(self) -> list[dict]:
        cap = self.capability()
        tg = self.core_targets() or list(self.targetable)
        mk, mc = cap["kick"]["moderate"], cap["current"]["moderate"]
        u1, u2 = int(tg[0]), int(tg[len(tg) // 2])
        lvl = lambda a: [a] * self.input_dim if self.input_dim > 1 else a  # noqa: E731
        u3 = int(tg[-1])
        base = self.base_protocol()
        ev1 = [{"kind": "kick", "t": 0.6, "delta": {str(u1): 2.0 * mk}},
               {"kind": "current", "t0": 1.2, "t1": 1.25, "targets": {str(u2): 2.0 * mc}},
               {"kind": "silence", "t0": 1.5, "t1": 1.6, "targets": [u1]}]
        ev2 = [{"kind": "kick", "t": 0.4, "delta": {str(u2): -3.0 * mk}},
               {"kind": "current", "t0": 0.8, "t1": 0.85, "targets": {str(u1): -2.0 * mc}},
               {"kind": "kick", "t": 1.3, "delta": {str(u3): 3.0 * mk}}]
        ev3 = [{"kind": "kick", "t": 0.9, "delta": {str(u1): 2.0 * mk}},
               {"kind": "current", "t0": 1.5, "t1": 1.55, "targets": {str(u3): -2.0 * mc}}]
        return [base, dict(base, stimulus=[[0.0, lvl(0.0)], [0.1, lvl(0.6)], [1.0, lvl(1.4)]], events=ev1),
                dict(base, stimulus=[[0.0, lvl(0.0)], [0.1, lvl(1.4)], [1.0, lvl(0.6)]], events=ev2),
                dict(base, stimulus=[[0.0, lvl(0.0)], [0.1, lvl(1.0)], [1.0, lvl(1.4)]], events=ev3)]

    @staticmethod
    def _eff_dim(s: np.ndarray, floor: float) -> int:
        """Smallest d such that the directions after the d-th change the readout by at most `floor` (RMS over the distribution)."""
        tail = np.sqrt(np.concatenate([np.cumsum((s ** 2)[::-1])[::-1], [0.0]]))
        return int(np.nonzero(tail <= floor)[0][0])

    def draw_sensitivity(self) -> dict:
        """Effective draw dimension (cached; 15-90 s per system). Method: readout trajectories of four probe protocols, 2 s each
        from rest (the nominal protocol; 0.6 -> 1.4, 1.4 -> 0.6 and 1.0 -> 1.4 input schedules with kicks of 2-3 m_s, 2 m_c
        pulses and a temporary silencing on core targets), at DRAW_BASES base draws (the nominal draw and random public draws at spread 1).
        J_b[:, i] = y(eta_b + e_i) - y(eta_b): the secant change for a ONE-SD move of draw parameter i (the draw distribution at the
        nominal spread 1), in units of f_s = 0.05 sd(y) (nominal) and RMS over samples and channels. Pooled Gram G = mean_b J_b^T J_b
        = V S^2 V^T; for eta ~ N(0, I) the RMS readout change along the directions after the d-th is sqrt(sum_{j>d} s_j^2)
        (linearised). d_draw = the smallest d with that tail <= DRAW_TOL (0.5 f_s: half the floor, a margin for the nonlinearity);
        draw_effective = V[:, :d_draw]^T eta. Weight noise (sd = capability max 0.1): the singular values of DRAW_WN_SAMPLES sampled
        readout changes / sqrt(M) (nominal parameters), same rule (a lower bound when it reaches M)."""
        if self._dsens is not None:
            return self._dsens
        names = self._draw_names()
        n = len(names)
        probes = [P.validate(p, allow_truth=True) for p in self._draw_probes()]
        nom = self._draw(NOMINAL_SEED, 1.0, None)
        outs0 = [self._sim_draw(q, nom)["y"] for q in probes]
        y0n = np.concatenate([o.ravel() for o in outs0])
        f_s = 0.05 * max(float(np.sqrt(np.mean(np.var(outs0[0], axis=0)))), 1e-6)
        norm = f_s * math.sqrt(y0n.size)

        def Y(d):
            return np.concatenate([self._sim_draw(q, d)["y"].ravel() for q in probes])

        brng = np.random.default_rng(int(self.content_hash()[:12], 16))
        bases = [nom] + [self._draw(int(a), 1.0, None) for a in brng.integers(1, 10 ** 9, self.DRAW_BASES - 1)]
        G = np.zeros((n, n))
        for bi, bd in enumerate(bases):
            eta0 = self._eta_of(bd)
            y0 = y0n if bi == 0 else Y(bd)
            J = np.zeros((y0.size, n))
            for i in range(n):
                e = eta0.copy()
                e[i] += 1.0
                J[:, i] = (Y(self._draw_from_eta(e, bd)) - y0) / norm
            G += J.T @ J / len(bases)
        w, V = np.linalg.eigh(G) if n else (np.zeros(0), np.zeros((0, 0)))
        o = np.argsort(w)[::-1]
        s, V = np.sqrt(np.maximum(w[o], 0.0)), V[:, o]
        for j in range(V.shape[1]):                          # deterministic sign: largest-magnitude entry positive
            if V[np.argmax(np.abs(V[:, j])), j] < 0:
                V[:, j] = -V[:, j]
        d_draw = self._eff_dim(s, self.DRAW_TOL)
        M = self.DRAW_WN_SAMPLES
        sd_w = float(self.capability()["weight_noise"]["max_sd"])
        W = np.stack([(Y(self._draw(NOMINAL_SEED, 1.0, {"sd": sd_w, "seed": 1000 + m})) - y0n) / norm for m in range(M)], axis=1)
        s_w = np.linalg.svd(W / math.sqrt(M), compute_uv=False)
        self._dsens = {
            "names": names, "singular_values_fs": s, "V": V, "d_draw": d_draw,
            "param_effect_fs": {nm: float(math.sqrt(max(G[i, i], 0.0))) for i, nm in enumerate(names)},
            "tail_fs": [float(np.sqrt(np.sum(s[d:] ** 2))) for d in range(len(s) + 1)],
            "d_draw_at_spread": {str(a): self._eff_dim(a * s, self.DRAW_TOL) for a in (1.5, 2.0)},
            "d_draw_floor_1fs": self._eff_dim(s, 1.0),
            "weight_noise_singular_values_fs": s_w, "d_draw_weight_noise": self._eff_dim(s_w, self.DRAW_TOL),
            "weight_noise_rms_fs": float(np.sqrt(np.sum(s_w ** 2))), "f_s": f_s,
        }
        return self._dsens

    def draw_effective(self, protocol: dict, *, include_weight_noise: bool = False) -> np.ndarray:
        """Truth-side: the trajectory's draw in its d_draw effective coordinates, V[:, :d_draw]^T eta (deterministic in params_seed,
        params_spread and weight noise; length d_draw). With include_weight_noise=True, vec(L E_F - I) (k^2 entries: the exact
        z-level effect of the weight-noise draw, zero without weight noise) is appended."""
        sens = self.draw_sensitivity()
        eff = sens["V"][:, :sens["d_draw"]].T @ self.draw_parameters(protocol)
        if include_weight_noise:
            q = P.validate(protocol, allow_truth=True)
            d = self._draw(q["params_seed"], q["params_spread"], q["weight_noise"])
            eff = np.concatenate([eff, (self.spec.L @ d.EF - np.eye(self.spec.k)).ravel()])
        return eff

    def eta_from_effective(self, eff) -> np.ndarray:
        """The standardized draw coordinates that the effective coordinates determine (the neglected directions at 0)."""
        sens = self.draw_sensitivity()
        eff = np.asarray(eff, dtype=float)[:sens["d_draw"]]
        return sens["V"][:, :sens["d_draw"]] @ eff

    @property
    def n_state(self) -> int:
        """Length of the full microstate: the n_units unit state variables + the k-dimensional internal copy of z (a numerical mirror
        of L (v_core - b) carried by the integrator so restarts are bit-exact)."""
        return self.spec.N + self.spec.k

    def rest_state(self) -> np.ndarray:
        return np.concatenate([self.spec.rest, np.zeros(self.spec.k)])

    def true_state(self, state) -> np.ndarray:
        s = np.asarray(state, float)
        c = self.spec.units_of(CORE)
        return (s[..., c] - self.spec.b) @ self.spec.L.T

    def _z_of(self, state) -> np.ndarray:
        """z as the integrator reads it from a full microstate: the internal copy when it agrees with the units, else L (v_c - b)."""
        s = np.asarray(state, float).reshape(-1)
        zu = self.true_state(s)
        if s.size == self.n_state:
            z0 = s[self.spec.N:].copy()
            if np.abs(z0 - zu).max() <= 1e-9 * max(1.0, float(np.abs(zu).max())):
                return z0
        return zu

    def obs_shortcut_state(self, state):
        z = self.true_state(state)
        zo = self.spec.latent.zobs(np.atleast_2d(z))
        if zo is None:
            return None
        return zo[0] if np.ndim(state) == 1 else zo

    def _set_z(self, state, z_new) -> np.ndarray:
        """Exact microscopic realisation of do(z := z_new): shift the core along the nominal embedding (L E = I)."""
        s = np.array(state, float)
        c = self.spec.units_of(CORE)
        dz = np.asarray(z_new, float) - self.true_state(s)
        s[c] += self.spec.E @ dz
        if s.size == self.n_state:
            s[self.spec.N:] = self.true_state(s)
        return s

    # ------------------------------------------------------------------------------------------------ truth functions
    def true_latent_effect(self, state, event: dict, *, params_seed: int = NOMINAL_SEED, u_level: float = 1.0) -> np.ndarray:
        """dz of an event at this microstate. Instantaneous events (kick, latent_set, latent_kick): the exact jump (kick
        clipping included). Finite events: z(end) - z_twin(end) at the completion sample (one sample after the end of the event),
        simulated from the state with the nominal parameter draw and a constant input u_level."""
        s = np.asarray(state, float)
        k = event["kind"]
        if k == "latent_kick":
            return np.asarray(event["dz"], float)
        if k == "latent_set":
            return np.asarray(event["z"], float) - self.true_state(s)
        if k == "kick":
            # the same arithmetic as the integrator: the admissible range acts on the on-manifold potential b_c + E_c z,
            # z += L[:, c] (clip(vhat_c + d) - vhat_c), core targets in canonical order (as protocol.validate)
            sp = self.spec
            z = self._z_of(s)
            z0 = z.copy()
            for u, d in sorted(event["delta"].items(), key=lambda kv: int(kv[0])):
                u = int(u)
                if sp.role[u] != CORE:
                    continue
                c = sp.loc[u]
                _, z, _ = core_kick(z, sp.E[c], sp.L[:, c], sp.b[c], float(d) / self.units()["v"], sp.lo[u], sp.hi[u])
            return z - z0
        ev = copy.deepcopy(event)
        dur = self._event_duration(ev)
        ev = self._shift_event(ev, 0.0)
        t_end = P.snap(dur + self.dt, self.dt)
        base = self.base_protocol(t_end=max(t_end, 10 * self.dt), params_seed=params_seed,
                                  stimulus=[[0.0, [u_level] * self.input_dim if self.input_dim > 1 else u_level]])
        a = self.simulate(dict(base, events=[ev]), full=True, restart_state=s)
        b = self.simulate(base, full=True, restart_state=s)
        j = int(round(t_end / self.dt))
        return a["z"][j] - b["z"][j]

    @staticmethod
    def _event_duration(e) -> float:
        if e["kind"] == "current_seq":
            m = len(next(iter(e["targets"].values())))
            return m * float(e["seg"])
        if e.get("t1") is None:
            return 0.1
        return float(e["t1"]) - float(e["t0"])

    def _shift_event(self, e, t0):
        e = copy.deepcopy(e)
        if "t" in e:
            e["t"] = t0
        else:
            dur = self._event_duration(e)
            e["t0"] = t0
            if "t1" in e:
                e["t1"] = t0 + dur
        return e

    def core_targets(self) -> list[int]:
        return [u for u in self.targetable if self.spec.role[u] == CORE]

    def _lift_base(self, j: int, base: dict | None) -> dict:
        """The protocol template of lift simulations: `base` (stimulus, parameter draw, noise of the case) or the nominal draw at a
        constant nominal input; duration j samples."""
        if base is None:
            base = self.base_protocol(stimulus=[[0.0, [1.0] * self.input_dim if self.input_dim > 1 else 1.0]])
        return dict(base, system=self.system_id, t_end=round(max(j, 10) * self.dt, 9), events=[], r0={"kind": "rest"})

    def _lift_z(self, s, base, events, j):
        return self._simulate_internal(dict(base, events=events), full=True, restart_state=s)["z"][j]

    def lift_latent(self, state, delta_z, n: int, *, t0: float = 0.0, base: dict | None = None, report: bool = False):
        """Up to n DISTINCT microscopic interventions realising z(j) = z_twin(j) + delta_z at ONE common completion sample
        j = t0 + LIFT_D (the twin: the same restart without events). Candidates: kicks at t0 + LIFT_D - dt on different subsets of
        the targetable core units (min-norm solutions of L_S delta = dz, Newton-corrected for the one sample of dynamics before j),
        then current pulses on [t0, t0 + LIFT_D) (Gauss-Newton on the simulated completion shift). Every candidate is simulated and
        returned only when its achieved miss ||z(j) - z_twin(j) - dz|| / ||dz|| (z_scale-whitened) is <= LIFT_TOL, so all returned
        lifts reach the same z at the same sample and have the same futures (z is the exact causal state); fewer than n (possibly
        none) are returned when the request is not reachable. Simulated with `base` (a protocol template of the case: stimulus,
        params_seed, ...) or the nominal draw at a constant nominal input. report=True returns [{"events", "miss"}]."""
        s = np.asarray(state, float)
        dz = np.asarray(delta_z, float).reshape(-1)
        tg = self.core_targets()
        out = []
        if not tg or n <= 0 or not np.any(dz != 0):
            return out
        sp = self.spec
        zs = np.asarray(sp.latent.z_scale, float)
        nw = lambda v: float(np.linalg.norm(v / zs))  # noqa: E731
        D = LIFT_D * self.dt
        j = int(round((t0 + D) / self.dt))
        bp = self._lift_base(j, base)
        target = self._lift_z(s, bp, [], j) + dz
        rng = np.random.default_rng(int.from_bytes(hashlib.sha256((self.system_id + str(dz.round(9).tolist())).encode()).digest()[:4], "little"))
        cols = {u: sp.loc[u] for u in tg}
        subsets = [list(tg)]
        perm = list(rng.permutation(tg))
        if len(tg) >= 2 * sp.k + 2:
            half = len(perm) // 2
            subsets += [sorted(perm[:half]), sorted(perm[half:])]
        if len(tg) >= sp.k + 2:
            for _ in range(4):
                m = max(sp.k + 1, len(tg) // 3)
                subsets.append(sorted(rng.choice(tg, size=m, replace=False).tolist()))
        if len(tg) >= sp.k + 1:
            for u in perm[:4]:                                      # leave-one-out subsets
                subsets.append(sorted(x for x in tg if x != u))
        tk = round(t0 + D - self.dt, 9)
        seen = []
        NV = (LIFT_D + 1) * self.n_units          # distinctness vector: kicks per sample slot, then pulse currents

        def accept(events, vec):
            miss = nw(self._lift_z(s, bp, events, j) - target) / nw(dz)
            if miss <= LIFT_TOL and not any(abs(float(vec @ w) / (np.linalg.norm(vec) * np.linalg.norm(w) + 1e-300)) > 0.99 for w in seen):
                seen.append(vec)
                out.append({"events": events, "miss": miss})
        # kicks at j - dt: the read-in is exact (dz(tk+) = L_S delta); the one sample of dynamics before j is handled with its
        # Jacobian Phi = dz(j) / dz(tk+) (finite differences of truth-level latent kicks), then Newton on the simulated shift
        z_ref = self._lift_z(s, bp, [], j)
        Phi = np.empty((sp.k, sp.k))
        for i in range(sp.k):
            e = np.zeros(sp.k)
            e[i] = 1e-4 * zs[i] * max(1.0, nw(dz))
            Phi[:, i] = (self._lift_z(s, bp, [{"kind": "latent_kick", "t": tk, "dz": e.tolist()}], j) - z_ref) / e[i]
        for sub in subsets:
            if len(out) >= n:
                break
            A = Phi @ sp.L[:, [cols[u] for u in sub]]
            Pinv = np.linalg.pinv(A)
            if nw(A @ (Pinv @ dz) - dz) > LIFT_TOL * nw(dz):
                continue                                          # this subset cannot reach the direction at j
            delta = Pinv @ dz
            for _ in range(6):
                ev = [{"kind": "kick", "t": tk, "delta": {str(u): float(d) for u, d in zip(sub, delta) if d != 0.0}}]
                r = target - self._lift_z(s, bp, ev, j)
                if nw(r) <= 1e-10 * nw(dz) or not np.all(np.isfinite(r)):
                    break
                delta = delta + Pinv @ r
            vec = np.zeros(NV)
            vec[sub] = delta
            accept(ev, vec)
        # kick trains: kicks at every sample t0 .. j - dt (LIFT_D samples), the min-norm solution of
        # [Phi_m L_S]_m (d_m) = dz (Phi_m = dz(j) / dz(j - m dt)), then Newton; distinct from the single kicks (the minimum-norm
        # solution spreads over the samples) and exact also when the targets are fewer than k
        if len(out) < n:
            Phis = [Phi]
            for m_ in range(2, LIFT_D + 1):
                tm = round(t0 + D - m_ * self.dt, 9)
                Pm = np.empty((sp.k, sp.k))
                for i in range(sp.k):
                    e = np.zeros(sp.k)
                    e[i] = 1e-4 * zs[i] * max(1.0, nw(dz))
                    Pm[:, i] = (self._lift_z(s, bp, [{"kind": "latent_kick", "t": tm, "dz": e.tolist()}], j) - z_ref) / e[i]
                Phis.append(Pm)
            for sub in subsets:
                if len(out) >= n:
                    break
                Ls = sp.L[:, [cols[u] for u in sub]]
                A = np.hstack([Pm_ @ Ls for Pm_ in Phis])
                Pinv = np.linalg.pinv(A)
                if nw(A @ (Pinv @ dz) - dz) > LIFT_TOL * nw(dz):
                    continue
                dd = Pinv @ dz
                ns_ = len(sub)
                for _ in range(6):
                    ev = [{"kind": "kick", "t": round(t0 + D - (m_ + 1) * self.dt, 9),
                           "delta": {str(u): float(d) for u, d in zip(sub, dd[m_ * ns_:(m_ + 1) * ns_]) if d != 0.0}}
                          for m_ in range(LIFT_D)]
                    ev = sorted([e_ for e_ in ev if e_["delta"]], key=lambda e_: e_["t"])
                    r = target - self._lift_z(s, bp, ev, j)
                    if nw(r) <= 1e-10 * nw(dz) or not np.all(np.isfinite(r)):
                        break
                    dd = dd + Pinv @ r
                vec = np.zeros(NV)
                for m_ in range(LIFT_D):
                    vec[m_ * self.n_units + np.asarray(sub)] = dd[m_ * ns_:(m_ + 1) * ns_]
                accept(ev, vec)
        # current pulses on [t0, t0 + D): Gauss-Newton in the min-norm family I = pinv(L_S) w tau_c / D
        for sub in subsets:
            if len(out) >= n:
                break
            I = self._pulse_lift(s, bp, target, sub, t0, D, j, nw(dz))
            if I is not None:
                vec = np.zeros(NV)
                vec[LIFT_D * self.n_units + np.asarray(sub)] = I
                accept([{"kind": "current", "t0": t0, "t1": round(t0 + D, 9), "targets": {str(u): float(a) for u, a in zip(sub, I)}}],
                       vec)
        out = [{"events": self.events_to_public(o["events"]), "miss": o["miss"]} for o in out[:n]]
        return out if report else [o["events"] for o in out]

    def _pulse_lift(self, s, bp, target, sub, t0, D, j, scale, iters=6):
        Ls = self.spec.L[:, [self.spec.loc[u] for u in sub]]
        B = np.linalg.pinv(Ls) * self.spec.tau_c / D
        zs = np.asarray(self.spec.latent.z_scale, float)

        def ev(Ivec):
            return [{"kind": "current", "t0": t0, "t1": round(t0 + D, 9), "targets": {str(u): float(a) for u, a in zip(sub, Ivec)}}]

        z_tw = self._lift_z(s, bp, [], j)
        I = B @ (target - z_tw)
        k = target.size
        for _ in range(iters):
            a = self._lift_z(s, bp, ev(I), j)
            miss = target - a
            if not np.all(np.isfinite(miss)):
                return None
            if np.linalg.norm(miss / zs) <= 1e-9 * scale:
                break
            J = np.empty((k, k))
            for i in range(k):
                e = np.zeros(k)
                e[i] = 1e-4 * max(scale, 1e-3) * zs[i]
                J[:, i] = (self._lift_z(s, bp, ev(I + B @ e), j) - a) / e[i]
            try:
                w = np.linalg.lstsq(J, miss, rcond=None)[0]
            except np.linalg.LinAlgError:
                return None
            I = I + B @ w
        return I if np.all(np.isfinite(I)) else None

    def equivalent_states(self, state, n: int, rng) -> list[np.ndarray]:
        """Microstates with the same z but different microscopic detail, of the kind interventions actually leave (review round 3,
        B3): the off-manifold core detail is what a real group kick with NO latent effect leaves: offsets on k + 1..k + 3 targetable
        core units in the null space of L_S (largest 0.5-1.5 x the moderate kick: the moderate class), aged by U(0.5, 3) tau_c (the detail relaxes
        exactly with tau_c: it has no synaptic output), w_S = d exp(-age / tau_c), L w = 0; the generator /
        relay / follower units are copied from another reachable state (a pool state). The readout future under every intervention
        sequence is unchanged; the observed microstate differs and stays within the range of reachable trajectories (tested)."""
        s = np.asarray(state, float)
        sp = self.spec
        self.units()
        c = sp.units_of(CORE)
        nuis = np.concatenate([sp.units_of(FOL), sp.units_of(GEN), sp.units_of(RELAY)]).astype(int)
        mk = self._units["internal"]["kick_moderate"]
        kick_units = [int(sp.loc[u]) for u in self.core_targets()] or list(range(sp.Nc))
        if nuis.size and getattr(self, "_eq_pool", None) is None:
            self._eq_pool = self.pool_states(12, np.random.default_rng(
                int.from_bytes(hashlib.sha256(("eqpool:" + self.system_id).encode()).digest()[:8], "little")))
        out = []
        for _ in range(n):
            s2 = s.copy()
            w = np.zeros(sp.Nc)
            if len(kick_units) > sp.k:
                # a real group kick with no latent effect: offsets d on m = k + 1..k + 3 targetable core units in the null space of
                # L_S (L_S d = 0: z unchanged), the largest 0.5-1.5 m_s, aged U(0.5, 3) tau_c; it leaves exactly d on those units
                # and nothing anywhere else, so the equivalent state is a reachable state with the same z
                m = min(len(kick_units), sp.k + int(rng.integers(1, 4)))
                S = [int(i) for i in rng.choice(kick_units, size=m, replace=False)]
                _, _, Vt = np.linalg.svd(sp.L[:, S])
                N_ = Vt[np.linalg.matrix_rank(sp.L[:, S]):]
                d = N_.T @ rng.normal(size=N_.shape[0])
                d *= float(rng.uniform(0.5, 1.5)) * mk / max(float(np.abs(d).max()), 1e-300)
                w[S] = d * math.exp(-float(rng.uniform(0.5, 3.0)))
            else:                                  # too few targetable core units: one aged single-unit kick, projected off z
                i = int(kick_units[int(rng.integers(0, len(kick_units)))])
                d = float(rng.choice([-1.0, 1.0])) * float(rng.uniform(0.5, 1.5)) * mk
                e = np.zeros(sp.Nc)
                e[i] = d
                w = (e - sp.E @ (sp.L[:, i] * d)) * math.exp(-float(rng.uniform(0.5, 3.0)))
            s2[c] = s[c] + w
            if nuis.size:
                donor = self._eq_pool[int(rng.integers(0, len(self._eq_pool)))]
                s2[nuis] = donor[nuis]
            if s2.size == self.n_state:
                s2[sp.N:] = self._z_of(s)                                 # the internal copy of z is unchanged
            out.append(s2)
        return out

    def pool_states(self, n: int, rng) -> list[np.ndarray]:
        """Diverse reachable microstates: samples at random times of nominal, input-scaled and intervention trajectories (nominal
        parameter draw), including post-intervention states."""
        protos = [self.base_protocol(), self.base_protocol(stimulus=self.nominal_stimulus(0.7)),
                  self.base_protocol(stimulus=self.nominal_stimulus(1.3))]
        tg = self.core_targets() or self.targetable
        cap = self.capability()
        for i in range(5):
            u = int(rng.choice(tg))
            t = float(np.round(rng.uniform(0.3, 0.6) * self.t_end_default, 3))
            kind = i % 3
            if kind == 0:
                ev = {"kind": "kick", "t": t, "delta": {str(u): float(rng.choice([-1, 1]) * cap["kick"]["moderate"] * rng.uniform(0.5, 3))}}
            elif kind == 1:
                ev = {"kind": "current", "t0": t, "t1": t + PROBE_PULSE,
                      "targets": {str(u): float(rng.choice([-1, 1]) * cap["current"]["moderate"] * rng.uniform(0.5, 3))}}
            else:
                ev = {"kind": "silence", "t0": t, "t1": t + 0.1, "targets": [u]}
            protos.append(self.base_protocol(events=[ev]))
        states = []
        trajs = [self.simulate(p, full=True)["state"] for p in protos]
        T = trajs[0].shape[0]
        lo = int(round(NOMINAL_ONSET / self.dt)) + 5
        for i in range(n):
            tr = trajs[int(rng.integers(0, len(trajs)))]
            states.append(tr[int(rng.integers(lo, T))].copy())
        return states

    # ------------------------------------------------------------------------------------------------ capability / record
    def obs_scale(self) -> dict:
        """Public observation scales: x = the 99th percentile of |x| on the nominal trajectory, y = the RMS temporal sd of y (so the
        readout floor is 0.05 obs_scale.y); both are type-independent draws by the choice of the public units (units())."""
        self.units()
        return {"x": self._units["public"]["x"], "y": self._units["public"]["y"]}

    def _probe(self):
        """The probe (moderates, floors) — deterministic in the constructed structure; cached on disk when P4SYNTH_CACHE_DIR is set
        (key: construction hash and engine id), which only saves time when test processes rebuild the same suites."""
        if self._pr is None:
            import os
            d = os.environ.get("P4SYNTH_CACHE_DIR")
            f = None
            if d:
                key = hashlib.sha256((self.construction_hash() + ENGINE_ID + "probe").encode()).hexdigest()[:32]
                f = os.path.join(d, f"probe_{key}.json")
                if os.path.exists(f):
                    try:
                        self._pr = json.load(open(f))
                        return self._pr
                    except Exception:
                        pass
            self._pr = self._probe_run()
            if f:
                try:
                    os.makedirs(d, exist_ok=True)
                    json.dump(self._pr, open(f, "w"))
                except (OSError, TypeError):
                    pass
        return self._pr

    def _probe_run(self):
        """Moderate magnitudes and detection floors from probe interventions at a typical state (mid-trajectory, nominal input,
        nominal draw): readout-effect detectability ES = RMS(e) / (0.05 sd(y)) over the primary horizon (12.5 % of t_end)."""
        nom = self._simulate_internal(self.base_protocol(), full=True)
        sd_y = float(np.sqrt(np.mean(np.var(nom["y"], axis=0))))
        f_s = 0.05 * max(sd_y, 1e-6)
        j0 = int(round(0.5 * self.t_end_default / self.dt))
        s0 = nom["state"][j0]
        H = P.snap(0.125 * self.t_end_default, self.dt)
        base = self.base_protocol(t_end=H, stimulus=[[0.0, [1.0] * self.input_dim if self.input_dim > 1 else 1.0]])
        twin = self._simulate_internal(base, restart_state=s0)["y"]
        tg = self.core_targets()
        rng = np.random.default_rng(int.from_bytes(hashlib.sha256(("probe:" + self.system_id).encode()).digest()[:8], "little"))
        probe_units = sorted(rng.choice(tg, size=min(PROBE_UNITS, len(tg)), replace=False).tolist()) if tg else []
        kap = np.median([self.meta["kappa"].get(u, 5.0) for u in tg]) if tg else 5.0

        def es(kind, mag):
            vals = []
            for u in probe_units:
                for sgn in (1.0, -1.0):
                    if kind == "kick":
                        ev = {"kind": "kick", "t": 0.0, "delta": {str(u): sgn * mag}}
                    else:
                        ev = {"kind": "current", "t0": 0.0, "t1": PROBE_PULSE, "targets": {str(u): sgn * mag}}
                    y = self._simulate_internal(dict(base, events=[ev]), restart_state=s0)["y"]
                    vals.append(float(np.sqrt(np.mean((y - twin) ** 2))) / f_s)
            return float(np.median(vals)) if vals else 0.0

        out = {}
        for kind, m0 in (("kick", 1.0 * kap), ("current", 1.0 * kap * self.spec.tau_c / PROBE_PULSE * 1.5)):
            m = m0
            e = es(kind, m)
            for _ in range(4):
                if e <= 1e-9:
                    break
                if ES_WINDOW[0] <= e < ES_WINDOW[1] and abs(e - TARGET_ES) <= 2.5:
                    break
                m_new = float(np.clip(m * TARGET_ES / e, 0.05 * m0, 20.0 * m0))
                if abs(m_new / m - 1) < 0.02:
                    break
                m = m_new
                e = es(kind, m)
            m = float(np.clip(m, 0.05 * m0, 20.0 * m0))
            floor = m / e if e > 1e-9 else float("inf")
            out[kind] = {"moderate": round(m, 4), "es_at_moderate": round(e, 3), "detection_floor": round(min(floor, 1e6), 4)}
        # review v3.3 (N7): every other kind / parameter field gets a PROBED moderate (median ES ~ 8 over the probe units, both signs,
        # window PARAM_REF from the mid-trajectory state) wherever an admissible magnitude reaches the window [3, 10); a kind / field
        # whose largest admissible magnitude stays below ES 3 is not published (it would be an inert "moderate")
        def es_param(field, mag):
            vals = []
            for u in probe_units:
                for sgn in (1.0, -1.0):
                    val = sgn * mag if field == "threshold" else 1.0 + sgn * mag
                    ev = {"kind": "param", "t0": 0.0, "t1": PARAM_REF, "targets": {str(u): {field: val}}}
                    y = self._simulate_internal(dict(base, events=[ev]), restart_state=s0)["y"]
                    vals.append(float(np.sqrt(np.mean((y - twin) ** 2))) / f_s)
            return float(np.median(vals)) if vals else 0.0

        def es_edge(depth):
            vals = []
            for e_ in probe_edges:
                ev = {"kind": "edge_scale", "t0": 0.0, "t1": PARAM_REF, "edges": [list(e_)], "factor": round(1.0 - depth, 6)}
                y = self._simulate_internal(dict(base, events=[ev]), restart_state=s0)["y"]
                vals.append(float(np.sqrt(np.mean((y - twin) ** 2))) / f_s)
            return float(np.median(vals)) if vals else 0.0

        def tune(f, m0, lo, hi):
            """(magnitude, ES): first the largest admissible magnitude; if it reaches ES 3, iterate towards ES = 8."""
            e_hi = f(hi)
            if e_hi < ES_WINDOW[0]:
                return None, e_hi
            m, e = hi, e_hi
            m_try = float(np.clip(m0, lo, hi))
            for _ in range(5):
                if m_try != m:
                    m, e = m_try, f(m_try)
                if ES_WINDOW[0] <= e < ES_WINDOW[1] and abs(e - TARGET_ES) <= 2.5:
                    break
                if e <= 1e-9:
                    break
                m_try = float(np.clip(m * TARGET_ES / e, lo, hi))
                if abs(m_try / m - 1.0) < 0.02:
                    break
            return m, e

        mk_i = out["kick"]["moderate"]
        par = {}
        for field, m0, lo, hi in (("threshold", 0.5 * mk_i, 0.005 * mk_i, 20.0 * mk_i), ("gain", 0.5, 0.02, 0.9), ("tau", 0.5, 0.02, 0.9)):
            m, e = tune(lambda mag, fl=field: es_param(fl, mag), m0, lo, hi)
            par[field] = {"moderate": None if m is None else round(m, 4), "es": round(e, 3), "max": hi}
        out["param"] = par
        erng = np.random.default_rng(int.from_bytes(hashlib.sha256(("probe-edges:" + self.system_id).encode()).digest()[:8], "little"))
        probe_edges = [self.edges[int(i)] for i in erng.choice(len(self.edges), size=min(8, len(self.edges)), replace=False)] if self.edges else []
        m, e = tune(es_edge, 0.5, 0.05, 1.0) if probe_edges else (None, 0.0)
        out["edge_scale"] = {"moderate": None if m is None else round(m, 4), "es": round(e, 3)}
        # natural time scale (measured, not declared): median 1/e decay time of the readout effect of the moderate probe kicks
        taus = []
        for u in probe_units:
            y = self._simulate_internal(dict(base, events=[{"kind": "kick", "t": 0.0, "delta": {str(u): out["kick"]["moderate"]}}]),
                              restart_state=s0)["y"]
            e_t = np.sqrt(np.mean((y - twin) ** 2, axis=1))
            ip = int(np.argmax(e_t))
            if e_t[ip] <= 1e-12:
                continue
            below = np.nonzero(e_t[ip:] < e_t[ip] / math.e)[0]
            taus.append((ip + (below[0] if below.size else e_t.size - ip)) * self.dt)
        out["time_scale"] = round(float(np.median(taus)) if taus else H, 4)
        out["kappa"] = float(kap)
        out["f_s"] = f_s
        return out

    def capability(self) -> dict:
        if self._cap is not None:
            return copy.deepcopy(self._cap)
        self.units()
        pub = self._units["public"]
        mk, mc = pub["kick"], pub["current"]
        pr = self._probe()
        # published only where the decision is the SAME for every system (a per-system support flag would be a type-dependent public
        # field): threshold reaches the ES window on every dev system; gain only on about half (type-dependent), tau on 3 / 50 and
        # edge scaling on 1 / 50 dev systems (seed 20260926), so gain, tau and edge_scale are not published for any system (they
        # stay implemented for orchestrator use); the probed values are in truth()["probe"]
        fields = [f for f in PUBLISHED_PARAM_FIELDS if pr["param"][f]["moderate"] is not None
                  and ES_WINDOW[0] <= pr["param"][f]["es"] < ES_WINDOW[1]]
        edge_ok = False
        lo, hi = -RANGE_PUB, RANGE_PUB
        cap = {
            "kick": {"supported": True, "moderate": mk, "max": 3 * mk, "hi_range": [4.5 * mk, 9 * mk],
                     "detection_floor": round(mk / TARGET_ES, 4), "units": "public state units of the target (system-specific unit, section 3)"},
            "current": {"supported": True, "moderate": mc, "max": 3 * mc, "hi_range": [4.5 * mc, 9 * mc],
                        "pulse_max_duration": PULSE_MAX, "sustained_min_duration": SUSTAINED_MIN,
                        "detection_floor": round(mc / TARGET_ES, 4), "moderate_reference_duration": PROBE_PULSE,
                        "units": "public current units (added to the target's input; tau dv/dt += I)"},
            "current_seq": {"supported": True, "moderate": mc, "max": 3 * mc, "min_seg_steps": P.MIN_SEG_STEPS},
            "silence": {"supported": True, "semantics": "synaptic inputs (recurrent, stimulus, background) and all outputs of the "
                        "targets removed during the window; electrode currents still act; the unit relaxes to its rest potential"},
            "edge_scale": ({"supported": True, "moderate": pr["edge_scale"]["moderate"], "factor_range": [0.0, 1.0],
                            "moderate_semantics": "weakening depth: factor 1 - moderate",
                            "moderate_reference_duration": PARAM_REF} if edge_ok else
                           {"supported": False, "reason": "not published: removing one listed synapse changes the readout by less than "
                                                              "the detection floor in almost every system (implemented for orchestrator use)"}),
            "param": {"supported": bool(fields), "fields": fields,
                      "moderate": {f: (round(pr["param"][f]["moderate"] * self.units()["v"], 4) if f == "threshold"
                                       else pr["param"][f]["moderate"]) for f in fields},
                      "moderate_reference_duration": PARAM_REF,
                      "moderate_semantics": "threshold: shift +- moderate (public state units), probed to a median readout "
                                            "detectability ES ~ 8 over moderate_reference_duration; gain and tau changes are "
                                            "implemented but not published (not detectable at any admissible factor in many systems)"},
            "init": {"state": True, "restart": True, "units": list(range(self.n_units)), "max_value": hi, "min_value": lo},
            "stimulus": {"channels": self.input_dim, "nominal_level": 1.0, "max_onset": 0.15, "range": [0.6, 1.4],
                         "allow_zero": True, "nominal": self.nominal_stimulus()},
            "params": {"public_seed_max": 999, "nominal_seed": NOMINAL_SEED},
            "weight_noise": {"max_sd": 0.1},
            "obs_noise": {"max_sd": 0.1},
            "timing": {"dt_allowed": [self.dt, 2 * self.dt], "t_end_max": max(self.t_end_default, 2.0) * 1.5},
            "process_noise": {"supported": True, "support": "every unit state variable (additive; RK4 step followed by the "
                              "Euler-Maruyama increment, strong order 1 for additive noise)",
                              "units": "the increment per substep of every unit is sd * sd_per_sqrt_s * sqrt(h) * xi; the noise sd "
                                       "per sqrt(s) is sd * sd_per_sqrt_s, the same for every unit of the system",
                              "sd_per_sqrt_s": NOISE_PUB,
                              "stream": "counter-based normals keyed by (seed, absolute output step, substep, unit); the absolute step "
                                        "of a restart is r0['t'] / dt, so restarts and split integrations reproduce the noise exactly",
                              "moderate": 0.05, "max": 0.5, "dev_range": None},
            "readout_floor": round(0.05 * pub["y"], 6),
            "time_scale": round(self.spec.tau_c, 3),
            "time_scale_definition": "time constant of the units (s): the natural time scale of a single unit's integration",
            "pulse_duration_scale": PROBE_PULSE,
            "sustained_duration_scale": SUSTAINED_MIN,
            "admissible_range": {"lo": lo, "hi": hi, "applies_to": "every unit (one system-wide range; a kick on a unit is "
                                 "clipped so the unit's potential stays inside it; a kick never moves a unit against its own "
                                 "sign, so a unit already outside the range is not moved further out)"},
            "moderate_definition": f"median readout detectability ES = RMS(y_int - y_twin) / (0.05 sd(y)) ~ {TARGET_ES} over "
                                   "12.5 % of t_end for single targets at a mid-trajectory state; some targets have no readout "
                                   "effect at any magnitude; detection_floor = moderate / " + str(TARGET_ES) + " (nominal)",
        }
        self._cap = cap
        return copy.deepcopy(cap)

    def public_record(self) -> dict:
        return {"system_id": self.system_id, "kind": "synthetic", "dt": self.dt, "t_end_default": self.t_end_default,
                "n_units": self.n_units, "observed": list(self.observed), "readout_dim": self.readout_dim,
                "input_dim": self.input_dim, "targets": list(self.targetable), "edges": [list(e) for e in self.edges],
                "obs_scale": self.obs_scale(), "capability": self.capability(),
                "cost_units": round(self.t_end_default / self.dt / 1000.0 * (1.0 + self.n_units / 200.0), 3),
                "public_graph": None, "engine_id": self.engine_id, "content_hash": self.content_hash()}

    def truth(self, include_draw: bool = True) -> dict:
        """The truth record. include_draw=False skips the draw analysis ("d_draw", "draw"; 15-90 s on the first call, cached)."""
        s = self.spec
        lat = s.latent
        roles = {int(u): {CORE: "core", GEN: "generator", FOL: "follower", RELAY: "relay"}[int(s.role[u])] for u in range(s.N)}
        obs_kinds = {}
        for u in s.observed:
            obs_kinds.setdefault(OBS_NAMES[int(s.obs_kind[u])], 0)
            obs_kinds[OBS_NAMES[int(s.obs_kind[u])]] += 1
        t = dict(self.info)
        t.update({
            "system_id": self.system_id, "engine_id": self.engine_id, "content_hash": self.content_hash(),
            "k": self.info.get("k", s.k), "k_state": s.k, "z_scale": list(lat.z_scale),
            "latent": lat.describe(), "latent_spec": _jsonable(lat.spec()),
            "readin": "kick d on core unit i: dz = L[:, i] (clip(vhat_i + d) - vhat_i), vhat_i = b_i + E_i z (the admissible range "
                      "acts on the on-manifold potential); current I on core unit i: dz/dt += a_i L[:, i] I / tau_c (a_i = 1 / tau "
                      "factor); silence / gain / threshold / edge_scale on core units change the synaptic outputs o = g (E z - dtheta) "
                      "and the inputs, and the time-constant factor scales the unit's integration (k x k terms of dz/dt); "
                      "interventions on generator / relay / follower units never change z or y",
            "true_state": "z = L (v_core - b); L = pinv(E), L E = I; the exact causal state of EVERY microstate under EVERY supported "
                          "intervention kind and sequence (synaptic outputs are functions of z; off-manifold detail is output-less)",
            "implementation": {"n_core": s.Nc, "n_generator": s.Ng, "n_followers": s.Nf, "n_relays": s.Nr, "tau_c": s.tau_c,
                               "core_units": [int(u) for u in s.units_of(CORE)], "generator_units": [int(u) for u in s.units_of(GEN)],
                               "follower_units": [int(u) for u in s.units_of(FOL)], "relay_units": [int(u) for u in s.units_of(RELAY)],
                               "unit_tag": self.meta["unit_tag"],
                               "unit_dims": self.meta["unit_dims"], "roles": roles},
            "observation_map": {"n_observed": len(s.observed), "n_units": s.N, "kinds": obs_kinds,
                                "observed_core": int(sum(s.role[u] == CORE for u in s.observed)),
                                "observed_generator": int(sum(s.role[u] == GEN for u in s.observed)),
                                "observed_followers": int(sum(s.role[u] == FOL for u in s.observed))},
            "closure": "exact for every microstate: two microstates with equal z have identical z and readout futures under every "
                       "supported intervention kind and sequence (tested bit for bit on every dev system with off-manifold core detail "
                       "of the size a moderate kick leaves); the off-manifold detail v_c - b - E z has no synaptic output, is visible in "
                       "the observations of core units and relaxes with tau_c",
            "noise": "deterministic; process noise only when requested (declared in the capability record)",
        })
        pr = self._probe()
        t["public_units"] = {"factors": self.units(), "public_values": dict(self._units["public"]),
                             "internal_values": dict(self._units["internal"]),
                             "note": "public = factor x internal: v (state: kicks, thresholds, range, process noise, r0 values), I "
                                     "(current), x, y; microstates (state, restart_state, rest_state, pool / equivalent states) and z "
                                     "are in internal units"}
        t["probe"] = {"es_at_moderate": {k: pr[k]["es_at_moderate"] for k in ("kick", "current")},
                      "param": pr["param"], "edge_scale": pr["edge_scale"],
                      "readout_effect_time_scale": pr["time_scale"],
                      "note": "measured readout detectability of the published moderate magnitudes and the median 1/e decay time of "
                              "the readout effect of moderate probe kicks (truth side; the capability publishes tau_c and m / 8)"}
        if not include_draw:
            return _jsonable(t)
        sens = self.draw_sensitivity()
        t["d_draw"] = sens["d_draw"]
        t["draw"] = {
            "closure": "z is the exact causal state GIVEN the trajectory's parameter draw (params_seed, params_spread, weight_noise): "
                       "every trajectory has its own draw, so across draws a history-based model may carry static coordinates that "
                       "identify it; (z, draw_effective(protocol)) determines the readout futures up to the tolerance below "
                       "(z with the full coordinates draw_parameters(protocol): exactly)",
            "parameters": sens["names"],
            "parameter_semantics": "standardized coordinates eta = params_spread * xi of the drawn latent / readout parameters (sorted "
                                   "names) and of log tau_c; generator, relay and follower draws never reach z or y",
            "method": "readout trajectories of four 2 s probe protocols from rest (nominal; 0.6 -> 1.4, 1.4 -> 0.6 and 1.0 -> 1.4 "
                      "inputs with kicks of 2-3 m_s, pulses and a temporary silencing on core targets) at 4 base draws (nominal + 3 random, spread "
                      "1); J_b[:, i] = the secant readout change for a one-sd move of parameter i at base b (the draw distribution at "
                      "the nominal spread 1), in f_s = 0.05 sd(y) and RMS over samples and channels; pooled Gram mean_b J_b^T J_b = "
                      "V S^2 V^T; d_draw = the smallest d with sqrt(sum_{j>d} s_j^2) <= 0.5 f_s (the RMS readout change left in the "
                      "neglected directions for eta ~ N(0, I), linearised; half the floor as a margin for the nonlinearity); "
                      "draw_effective(protocol) = V[:, :d_draw]^T eta",
            "tolerance_fs": self.DRAW_TOL,
            "d_draw_at_floor_1fs": sens["d_draw_floor_1fs"],
            "singular_values_fs": [round(float(a), 4) for a in sens["singular_values_fs"]],
            "param_effect_fs": {k: round(v, 4) for k, v in sens["param_effect_fs"].items()},
            "d_draw_at_spread": sens["d_draw_at_spread"],
            "weight_noise": {"d_draw_weight_noise": sens["d_draw_weight_noise"], "samples": self.DRAW_WN_SAMPLES,
                             "sd": float(self.capability()["weight_noise"]["max_sd"]),
                             "rms_readout_change_fs": round(sens["weight_noise_rms_fs"], 3),
                             "note": "weight noise changes M_F = L E_F (k x k): draw_effective(protocol, include_weight_noise=True) "
                                     "appends vec(M_F - I); d_draw_weight_noise counts the directions of DRAW_WN_SAMPLES sampled "
                                     "weight-noise readout changes (same tail rule; a lower bound when it equals the sample count)"},
        }
        return _jsonable(t)
