"""Adapter between the benchmark and the synthetic suite generator (ORCHESTRATOR SIDE: the generator holds the ground truth and
never enters a method room).

The synthetic author's generator package implements this interface (research/phase4/contracts/SYNTHETIC_BENCHMARK_CONTRACT.md
section 4; any package name; the benchmark loads it from its hash-locked directory with `load_generator` / `register_generator`):

    build_suite(tier: str, seed: int, n_per_type: int | None = None) -> {system_id: SyntheticSystem}
                                               # module-level; deterministic in (tier, seed); opaque ids; seeded variants

    class SyntheticSystem:
        system_id: str; engine_id: str         # engine_id = generator / simulator version string (enters every store key)
        n_units: int; observed: list[int]; readout_dim: int; input_dim: int; dt: float; t_end_default: float
        def content_hash(self) -> str          # hash of the full system definition (enters every store key)
        def public_record(self) -> dict        # INTERFACES section 3 record WITHOUT the split (the benchmark adds split and the public
                                               #   / hidden target partition): kind "synthetic", dt, t_end_default, n_units, observed,
                                               #   readout_dim, input_dim, targetable units, edges, obs_scale {"x", "y"}, capability,
                                               #   cost_units
        def capability(self) -> dict           # the capability record (contract section 3)
        def simulate(self, protocol, full=False, restart_state=None) -> dict
                                               # protocol: canonical p4-protocol-1 (truth events latent_set / latent_kick allowed;
                                               # params_spread and process_noise honoured; obs_noise IGNORED: the benchmark adds it)
                                               # returns {"t" (T,), "x" (T, n_obs), "u" (T, n_u), "y" (T, n_y), "info": {...}};
                                               # full=True adds "state" (T, n_state) the complete, restartable microstate, "z" (T, k)
                                               # the TRUE causal state and "z_obs" (T, k_obs) the observational shortcut where defined;
                                               # restart_state: a full microstate vector that replaces r0 (the benchmark resolves r0
                                               # 'restart' keys and pool states to it)
        def rest_state(self) -> np.ndarray                      # the microstate of r0 = {"kind": "rest"}
        def true_state(self, state) -> np.ndarray               # z from a full microstate
        def obs_shortcut_state(self, state) -> np.ndarray | None
        def true_latent_effect(self, state, event) -> np.ndarray   # dz of an INSTANTANEOUS microscopic event at this microstate
        def lift_latent(self, state, delta_z, n) -> list[list[dict]]   # n DISTINCT microscopic interventions realising z + dz
        def equivalent_states(self, state, n, rng) -> list[np.ndarray] # microstates with the same z, different microscopic detail
        def pool_states(self, n, rng) -> list[np.ndarray]              # diverse reachable microstates (equivalence tests)
        def truth(self) -> dict                # static description: type, trap label, k (or "none"), f / g / read-in, observation
                                               # map, implementation group, z_obs and why it fails, exposing families, notes, verdict

`SyntheticSystem` below is the abstract form of that interface (the generator may duck-type it). Observation noise is never
simulated by the generator: `observe_synthetic` adds it to the returned observed arrays, like `realsim.observe`. A tiny linear toy
system (`ToySystem`, tier "toy") implements the whole interface, truth methods included, for tests.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import sys
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import protocol as P


class SyntheticSystem(ABC):
    system_id: str
    engine_id: str
    n_units: int
    observed: list[int]
    readout_dim: int
    input_dim: int
    dt: float
    t_end_default: float

    @abstractmethod
    def content_hash(self) -> str: ...

    @abstractmethod
    def public_record(self) -> dict: ...

    @abstractmethod
    def capability(self) -> dict: ...

    @abstractmethod
    def simulate(self, protocol: dict, full: bool = False, restart_state=None) -> dict: ...

    @abstractmethod
    def rest_state(self) -> np.ndarray: ...

    @abstractmethod
    def true_state(self, state) -> np.ndarray: ...

    @abstractmethod
    def obs_shortcut_state(self, state) -> np.ndarray | None: ...

    @abstractmethod
    def true_latent_effect(self, state, event: dict) -> np.ndarray: ...

    @abstractmethod
    def lift_latent(self, state, delta_z, n: int) -> list[list[dict]]: ...

    @abstractmethod
    def equivalent_states(self, state, n: int, rng) -> list[np.ndarray]: ...

    @abstractmethod
    def pool_states(self, n: int, rng) -> list[np.ndarray]: ...

    @abstractmethod
    def truth(self) -> dict: ...


def load_generator(generator_dir: Path | str, package: str):
    """Import the generator package from its (hash-locked) directory."""
    d = str(Path(generator_dir).resolve())
    if d not in sys.path:
        sys.path.insert(0, d)
    return importlib.import_module(package)


_GENERATORS: dict[str, object] = {}
#: review G's trap tier (goal5 sections 41 / 84; research/phase4/review_contracts/REVIEW_G_CONTRACT.md): its systems are
#: `review_g_catalog(seed)` of the module review G delivers as `p4synth/review_g.py`. The module is kept OUTSIDE the frozen generator
#: copy (the benchmark lock refuses new files there) and loaded as the submodule `<package>.review_g` of the registered generator
#: package, so its relative imports resolve. Location: $P4_TRAP_CATALOG, else <repository>/TRAP_CATALOG_REL (baked root-only into the
#: images that build or evaluate the trap tier; it never enters a room).
TRAP_TIER = "trap"
TRAP_CATALOG_REL = "research/phase4/review_g/review_g.py"


def trap_catalog_path() -> Path:
    env = os.environ.get("P4_TRAP_CATALOG")
    return Path(env) if env else Path(__file__).resolve().parents[3] / TRAP_CATALOG_REL


def load_trap_catalog(generator: str = "default"):
    """Review G's catalog module, loaded once as `<generator package>.review_g`."""
    mod = _GENERATORS.get(generator)
    if mod is None:
        raise RuntimeError("no synthetic generator registered (register_generator(dir, package))")
    name = f"{mod.__name__}.review_g"
    if name in sys.modules:
        return sys.modules[name]
    path = trap_catalog_path()
    if not path.is_file():
        raise RuntimeError(f"review G's trap catalog is not delivered ({path}): the trap tier needs it")
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    try:
        spec.loader.exec_module(m)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return m


_TPC = None                         # threadpoolctl controller (it scans the loaded BLAS libraries: rebuilt only after new imports)
_TPC_NMOD = -1


def single_blas_thread():
    """A context in which every BLAS library of this process uses ONE thread: the reference numerics of the synthetic generator. Its
    system construction and simulation are bit-identical across processes only at a fixed thread count (with more threads 3 of the 50
    development systems of the round-2 generator get another content hash, and an evaluation process running 2-4 BLAS threads
    computed another hash for a validation system and refused the restarts from its stored records; LOG P4-D50)."""
    global _TPC, _TPC_NMOD
    from threadpoolctl import ThreadpoolController
    n = len(sys.modules)
    if _TPC is None or n != _TPC_NMOD:              # rescan after new imports (e.g. scipy's own OpenBLAS loads with scipy.linalg)
        _TPC, _TPC_NMOD = ThreadpoolController(), n
    return _TPC.limit(limits=1)


class SingleThreadedSystem:
    """A generator system whose every method call runs with ONE BLAS thread (`single_blas_thread`), whatever the calling process's
    thread settings (evaluation jobs run 2-4 BLAS threads). Data attributes pass through unchanged."""
    __slots__ = ("_obj",)

    def __init__(self, obj):
        object.__setattr__(self, "_obj", obj)

    def __getattr__(self, name):
        if name == "_obj":
            raise AttributeError(name)
        v = getattr(self._obj, name)
        if callable(v) and not isinstance(v, type):
            def call(*a, **k):
                with single_blas_thread():
                    return v(*a, **k)
            call.__name__ = getattr(v, "__name__", name)
            call.__doc__ = getattr(v, "__doc__", None)
            return call
        return v

    def __reduce__(self):
        return (SingleThreadedSystem, (self._obj,))

    def __repr__(self) -> str:
        return f"SingleThreadedSystem({self._obj!r})"


def register_generator(generator_dir: Path | str, package: str, name: str = "default") -> None:
    """Register (or replace) the generator `name`. Re-registering the same module is a no-op, so the suites built from it stay cached
    (planning a tier registers the generator once per system)."""
    mod = load_generator(generator_dir, package)
    if _GENERATORS.get(name) is mod:
        return
    _GENERATORS[name] = mod
    suite_systems.cache_clear()


@lru_cache(maxsize=16)
def suite_systems(tier: str, seed: int, generator: str = "default", n_per_type: int | None = None) -> dict:
    """{system_id: SyntheticSystem} of one suite (tier 'toy' is built in: two ToySystems)."""
    if tier == "toy":
        return {s.system_id: s for s in (ToySystem(int(seed), j) for j in range(2))}
    mod = _GENERATORS.get(generator)
    if mod is None:
        raise RuntimeError("no synthetic generator registered (register_generator(dir, package))")
    if tier == TRAP_TIER:               # review G's new trap systems (hidden, after the lock; see TRAP_TIER)
        cat = load_trap_catalog(generator)
        with single_blas_thread():
            built = {s.system_id: s for s in cat.review_g_catalog(int(seed))}
        return {sid: SingleThreadedSystem(s) for sid, s in built.items()}
    with single_blas_thread():          # construction and every later call at the reference numerics (one BLAS thread; LOG P4-D50)
        built = dict(mod.build_suite(tier, int(seed))) if n_per_type is None else \
            dict(mod.build_suite(tier, int(seed), n_per_type=int(n_per_type)))
    return {sid: SingleThreadedSystem(s) for sid, s in built.items()}


def observe_synthetic(record: dict, sysrec: dict, proto: dict, *, allow_truth: bool = False) -> dict:
    """{t, x, u, y} of a synthetic record, with the protocol's observation noise (seeded; sd x obs_scale)."""
    q = P.validate(proto, allow_truth=allow_truth)
    x = np.asarray(record["x"], dtype=np.float32)
    y = np.asarray(record["y"], dtype=np.float32)
    on = q["obs_noise"]
    if on is not None and float(on["sd"]) > 0:
        sc = sysrec.get("obs_scale") or {}
        rng = np.random.default_rng(int(on["seed"]))
        x = (x.astype(np.float64) + float(on["sd"]) * float(sc["x"]) * rng.standard_normal(x.shape)).astype(np.float32)
        y = (y.astype(np.float64) + float(on["sd"]) * float(sc["y"]) * rng.standard_normal(y.shape)).astype(np.float32)
    return {"t": np.asarray(record["t"], dtype=np.float64), "x": x, "u": np.asarray(record["u"], dtype=np.float32), "y": y}


# ------------------------------------------------------------------------------------------------ toy system (tests only)
TOY_CAPABILITY = {
    "kick": {"supported": True, "moderate": 0.5, "max": 1.5, "hi_range": [2.25, 4.5]},
    "current": {"supported": True, "moderate": 0.5, "max": 1.5, "hi_range": [2.25, 4.5], "pulse_max_duration": 0.2,
                "sustained_min_duration": 0.4},
    "current_seq": {"supported": True, "moderate": 0.5, "max": 1.5, "min_seg_steps": 5},
    "silence": {"supported": True},
    "edge_scale": {"supported": True, "moderate": 0.3, "factor_range": [0.0, 2.0]},
    "param": {"supported": True, "fields": ["gain", "threshold", "tau"], "moderate": {"gain": 0.3, "threshold": 0.3, "tau": 0.3}},
    "init": {"state": True, "restart": True, "units": "observed", "max_value": 10.0, "min_value": -10.0},
    "stimulus": {"channels": 1, "nominal_level": 1.0, "max_onset": 0.5, "range": [0.5, 1.5], "allow_zero": True},
    "params": {"public_seed_max": 10**9, "nominal_seed": 0, "dev_spread": 1.0, "spread_range": [0.0, 3.0]},
    "process_noise": {"supported": True, "dev_max_sd": 0.1, "units": "state units per sqrt(s)"},
    "weight_noise": {"max_sd": 0.1},
    "obs_noise": {"max_sd": 0.5},
    "timing": {"dt_allowed": [0.01, 0.02], "t_end_max": 8.0},
    "latent": {"supported": True},
    "time_scale_s": 0.2, "detection_floor": {"y": 0.01}, "admissible_range": [-10.0, 10.0],
}


class ToySystem(SyntheticSystem):
    """A 6-unit linear rate network with a KNOWN 2-D causal state (tests only).

        tau dx_i/dt = -x_i + g_i (sum_j W_ij x_j + b_i u + I_i(t) - theta_i),   W = Q diag(lam) Q^T symmetric, lam = (0.95, 0.8,
                                                                                -0.5, -1, -2, -3), one time constant tau per trajectory
        z = C x with C = the two slow eigenvectors (rows of Q^T);  y = G z (G = [1, 0.5]);  units 0-4 observed, unit 5 hidden.

    Because tau is common to all units and W is symmetric, the slow subspace is exactly invariant: z' = ((lam_s - 1) z + C (b u + I))
    / tau with g = 1 and theta = 0. Hence z is EXACTLY causal (readout futures determined by z, future inputs and future additive
    interventions: kick, current, current_seq, latent events) and states with equal z are equivalent under them. Structural
    interventions (silence, edge_scale, param) and weight noise change W / g / tau per unit, so the slow subspace is no longer
    invariant: under them z is only approximately sufficient (declared in truth()). No clipping; process noise is an Euler-Maruyama
    increment once per output step (sd per sqrt(s)); params_spread scales the spread of tau's draw."""

    engine_id = "toy-linear-2"
    N = 6
    dt = 0.01
    t_end_default = 4.0
    readout_dim = 1
    input_dim = 1

    def __init__(self, seed: int, j: int = 0):
        self.seed, self.j = int(seed), int(j)
        self.system_id = f"syn:toy:{j}"
        self.n_units = self.N
        rng = np.random.default_rng(1000 + 7 * self.seed + self.j)
        Q, _ = np.linalg.qr(rng.standard_normal((self.N, self.N)))
        self.lam = np.array([0.95, 0.8, -0.5, -1.0, -2.0, -3.0])
        self.W = Q @ np.diag(self.lam) @ Q.T
        self.b = rng.standard_normal(self.N) * 0.5
        self.C = Q[:, :2].T.copy()                              # the slow subspace (orthonormal rows)
        self.Cp = self.C.T.copy()                               # its pseudo-inverse (orthonormal rows)
        self.Nul = Q[:, 2:].copy()                              # a basis of the null space of C
        self.G = np.array([[1.0, 0.5]])
        self.observed = [0, 1, 2, 3, 4]
        # distinct unit subsets for the lifts (each C[:, S] has full row rank for a generic Q)
        self._lift_sets = [tuple(range(self.N)), (0, 1, 2), (3, 4, 5), (0, 2, 4), (1, 3, 5), (0, 1), (2, 3), (4, 5)]
        self._lift_sets = [S for S in self._lift_sets if np.linalg.matrix_rank(self.C[:, list(S)]) == 2]

    # ---------------------------------------------------------------- description
    def content_hash(self) -> str:
        return hashlib.sha256(json.dumps({"toy": self.engine_id, "seed": self.seed, "j": self.j}).encode()).hexdigest()

    def capability(self) -> dict:
        return json.loads(json.dumps(TOY_CAPABILITY))

    def public_record(self) -> dict:
        return {"system_id": self.system_id, "kind": "synthetic", "dt": self.dt, "t_end_default": self.t_end_default,
                "horizons_s": {"short": 0.1, "medium": 0.5, "long": 2.0}, "n_units": self.N, "observed": list(self.observed),
                "readout_dim": 1, "input_dim": 1, "targetable": list(range(self.N)),
                "edges": [[i, j] for i in range(self.N) for j in range(self.N) if i != j],
                "obs_scale": {"x": 1.0, "y": 1.0}, "capability": self.capability(), "cost_units": 1}

    def truth(self) -> dict:
        return {"type": "toy_linear", "trap": None, "k": 2, "C": self.C.tolist(), "G": self.G.tolist(),
                "f": "z' = ((lam_s - 1) z + C (b u + I)) / tau, lam_s = (0.95, 0.8)", "read_in": "kick dx -> dz = C dx; current I -> C I / tau",
                "observation_map": "x = units 0-4 of the microstate; z = C x_full", "implementation_group": None, "z_obs": None,
                "exact_for": ["kick", "current", "current_seq", "latent_set", "latent_kick"],
                "approximate_for": ["silence", "edge_scale", "param", "weight_noise"],
                "expected_verdict": "compact causal state, k = 2 (exact under additive interventions)"}

    # ---------------------------------------------------------------- truth methods
    def rest_state(self) -> np.ndarray:
        return np.zeros(self.N)

    def true_state(self, state) -> np.ndarray:
        return self.C @ np.asarray(state, dtype=np.float64)

    def obs_shortcut_state(self, state) -> np.ndarray | None:
        return None

    def true_latent_effect(self, state, event: dict) -> np.ndarray:
        state = np.asarray(state, dtype=np.float64)
        k = event.get("kind")
        if k == "kick":
            dx = np.zeros(self.N)
            for u, d in event["delta"].items():
                dx[int(u)] += float(d)
            return self.C @ dx
        if k == "latent_kick":
            return np.asarray(event["dz"], dtype=np.float64)
        if k == "latent_set":
            return np.asarray(event["z"], dtype=np.float64) - self.C @ state
        raise ValueError(f"{k!r} is not an instantaneous event")

    def lift_latent(self, state, delta_z, n: int) -> list[list[dict]]:
        dz = np.asarray(delta_z, dtype=np.float64)
        out = []
        for S in self._lift_sets[: int(n)]:
            dxS = np.linalg.pinv(self.C[:, list(S)]) @ dz
            out.append([{"kind": "kick", "t": 0.0, "delta": {str(u): float(v) for u, v in zip(S, dxS)}}])
        return out

    def equivalent_states(self, state, n: int, rng) -> list[np.ndarray]:
        state = np.asarray(state, dtype=np.float64)
        return [state + self.Nul @ rng.normal(0.0, 0.5, self.N - 2) for _ in range(int(n))]

    def pool_states(self, n: int, rng) -> list[np.ndarray]:
        return [rng.normal(0.0, 1.0, self.N) for _ in range(int(n))]

    # ---------------------------------------------------------------- simulation
    def _params(self, seed: int, spread: float = 1.0):
        rng = np.random.default_rng(int(seed))
        tau = abs(0.1 * (1.0 + 0.05 * float(spread) * rng.standard_normal()))
        return {"tau": np.full(self.N, tau), "gain": np.ones(self.N), "theta": np.zeros(self.N)}

    def simulate(self, protocol: dict, full: bool = False, restart_state=None) -> dict:
        q = P.validate(protocol, allow_truth=True)
        dt, t_end = q["dt"], q["t_end"]
        prm = self._params(q["params_seed"], q["params_spread"])
        pn = q["process_noise"]
        prng = np.random.default_rng(int(pn["seed"])) if pn is not None else None
        W0 = self.W.copy()
        if q["weight_noise"] is not None and q["weight_noise"]["sd"] > 0:
            rng = np.random.default_rng(int(q["weight_noise"]["seed"]))
            W0 = W0 * (1.0 + float(q["weight_noise"]["sd"]) * rng.standard_normal(W0.shape))
        grid = np.round(np.arange(0.0, t_end + dt / 2, dt), 9)
        grid = grid[grid <= t_end + 1e-12]
        x = self.rest_state()
        if restart_state is not None:
            x = np.asarray(restart_state, dtype=np.float64).copy()
        elif q["r0"]["kind"] == "state":
            for k, v in q["r0"]["values"].items():
                x[int(k)] = float(v)
        elif q["r0"]["kind"] == "restart":
            raise P.ProtocolError("r0 'restart' must be resolved to restart_state by the caller")
        X = np.zeros((len(grid), self.N))
        U = np.zeros((len(grid), 1))
        X[0] = x
        bps = P.breakpoints(q, allow_truth=True)
        seqb = {id(e): P.seq_boundaries(e, dt) for e in q["events"] if e["kind"] == "current_seq"}
        for a, b in zip(bps[:-1], bps[1:]):
            ia, ib = round(a / dt), round(b / dt)
            X[ia] = x
            for e in q["events"]:
                t = e.get("t")
                if t is not None and abs(t - a) < 1e-9:
                    if e["kind"] == "kick":
                        for k, d in e["delta"].items():
                            x[int(k)] += d
                    elif e["kind"] == "latent_kick":
                        x = x + self.Cp @ np.asarray(e["dz"])
                    elif e["kind"] == "latent_set":
                        x = x + self.Cp @ (np.asarray(e["z"]) - self.C @ x)
            if ib <= ia:
                continue
            s = [v for tt, v in q["stimulus"] if tt <= a + 1e-9][-1]
            s = float(s[0]) if isinstance(s, list) else float(s)
            I = np.zeros(self.N)
            W = W0.copy()
            g, th, tau = prm["gain"].copy(), prm["theta"].copy(), prm["tau"].copy()
            for e in q["events"]:
                k = e["kind"]
                if k == "current_seq":
                    bnd = seqb[id(e)]
                    if bnd[0] <= a + 1e-9 and b <= bnd[-1] + 1e-9:
                        jj = int(np.searchsorted(bnd, a + 1e-9, side="right") - 1)
                        for kk, lst in e["targets"].items():
                            I[int(kk)] += lst[jj]
                    continue
                if k not in ("current", "silence", "edge_scale", "param"):
                    continue
                if not (e["t0"] <= a + 1e-9 and (e["t1"] is None or b <= e["t1"] + 1e-9)):
                    continue
                if k == "current":
                    for kk, v in e["targets"].items():
                        I[int(kk)] += v
                elif k == "silence":
                    for n in e["targets"]:
                        W[n, :] = 0.0
                        W[:, n] = 0.0
                elif k == "edge_scale":
                    for p_, r_ in e["edges"]:
                        W[p_, r_] *= float(e["factor"])
                else:
                    for kk, v in e["targets"].items():
                        g[int(kk)] *= v.get("gain", 1.0)
                        th[int(kk)] += v.get("threshold", 0.0)
                        tau[int(kk)] *= v.get("tau", 1.0)

            def rhs(xx, g=g, W=W, s=s, I=I, th=th, tau=tau):
                return (-xx + g * (W @ xx + self.b * s + I - th)) / tau

            h = dt / 10.0
            for i in range(ia, ib):
                for _ in range(10):
                    k1 = rhs(x)
                    k2 = rhs(x + h / 2 * k1)
                    k3 = rhs(x + h / 2 * k2)
                    k4 = rhs(x + h * k3)
                    x = x + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
                if prng is not None:            # Euler-Maruyama increment once per output step: sd per sqrt(s)
                    x = x + float(pn["sd"]) * np.sqrt(dt) * prng.standard_normal(self.N)
                X[i + 1] = x
                U[i, 0] = s
        U[-1] = U[-2] if len(U) > 1 else U[-1]
        Z = X @ self.C.T
        out = {"t": grid, "x": X[:, self.observed].astype(np.float32), "u": U.astype(np.float32),
               "y": (Z @ self.G.T).astype(np.float32), "info": {"engine": self.engine_id, "system_id": self.system_id}}
        if full:
            out["state"] = X.astype(np.float64)
            out["z"] = Z.astype(np.float64)
        return out


def suite_content_hashes(tier: str, seed: int, generator_dir: str, package: str = "p4synth") -> dict:
    """{system_id: content_hash} of a synthetic suite built in THIS process (cross-platform identity checks, LOG P4-D32)."""
    register_generator(generator_dir, package, "hashcheck")
    return {sid: s.content_hash() for sid, s in suite_systems(tier, int(seed), "hashcheck").items()}
