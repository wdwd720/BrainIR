"""Budgeted simulation service for Phase 4 rooms (ORCHESTRATOR SIDE; research/phase4/INTERFACES.md section 8; goal5 sections 28, 61).

Developers never get simulator code: they drop request files into their own queue <room>/simq/<scratch>/requests/
(`brainir_causal.simclient.SimClient`; trusted callers and tests may use <room>/simq/requests/) and read results from the same
queue's results/. This server
  1. validates every protocol (format p4-protocol-1) against the PUBLIC POLICY of its system (`check_public`): the system's split
     record (only `families_train`; held-out, hidden-only, unclassified and truth-event protocols are refused), its public targets
     and edges, the development magnitude / duration ranges of its capability record, the public seed range, the public input
     range, the initial-state rules (observed units within range, or a restart from a trajectory this agent was served or that is
     public) and the development timing and noise limits;
  2. charges the agent's budget in the system's units (`cost_units`) and keeps a cost ledger per agent (`brainir_causal.accounting`:
     experiments, trajectories, simulator calls, simulated seconds, unique targets, magnitude per kind), plus one JSONL line per
     request;
  3. serves identical protocols from the content-addressed store (`brainir_causal.store`), simulating only new microstates: real
     mechanism and synthetic systems in a local process pool; real FULL networks through a pluggable `remote_backend` when one is
     given (a callable jobs -> engine records, e.g. Modal), else locally;
  4. writes back the OBSERVED arrays only (t, x, u, y; observation noise added per protocol), never the full microstate or truth.

Restarts: r0 {"kind": "restart", "key": k, "t": t} accepts the trajectory keys the service returned to this agent and the keys of
the public datasets (`public_keys`, built by `build_public_keys` from the public dataset directories: trajectory keys and their store
keys, each with its system, sampling and PUBLIC PROTOCOL); the server rewrites them to store keys before simulating. A public source
that is not in the request's store namespace is RECOMPUTED from its public protocol (`SimServer._ensure_source`, recursively for sources that
restart themselves, not charged to the agent): on the reference platform the recomputed record is the benchmark's record bit for bit,
and its store key (canonical protocol, system content hash, engine) must equal the public record's, else the request is refused. A
REAL FULL-network job whose restart source is not in the local store goes to the remote backend when one is configured (its container
reads the source from the volume store, where the benchmark's remote builds publish the public records).

REFERENCE PLATFORM (LOG P4-D32 / P4-D33). The synthetic generator is bit-identical across Linux environments with the pinned stack
(the Modal containers and the local sandbox image) but not on the Windows host. For rooms the service therefore runs with
`pool=simdocker.DockerPool(...)` (CLI `--docker`): this host process keeps the queue, identity, policy, budgets, ledgers and the Modal
client; every local simulation (synthetic systems, real mechanisms) runs in one network-less container of the pinned image that sees
only the repository code read-only, the service store and a bridge directory (`brainir_causal.simdocker`). Engine ids of synthetic
systems are then read from the container (`DockerPool.describe`), so the host never builds a generator system.

SYNTHETIC systems are simulated through the hash-locked generator, which must be registered in EVERY worker process:
`SimServer(..., generators={name: (directory, package)})` registers them in this process and, through the default pool's
initializer, in every worker (a synthetic system record names its generator in "generator", default "default"). A pool passed in
by the caller must register them itself (`register_generators` as its initializer).

IDENTITY (review F, M4; round 2, N-M1). Identity is bound OUTSIDE the request: the launcher issues each agent (and each experiment
loop) a secret token (`issue_token`, a table {sha256(token): {agent, budget, kind, queue}} in a file OUTSIDE every room), BOUND to
the agent's own queue simq/<scratch>/ (the queue is the directory the request file arrived in; the sandbox shows an agent only its
own queue and the host guard refuses writes into another agent's), and hands the token to the agent's sandbox only (a file outside
the room that the sandbox wrapper forwards into the container as P4_SIM_TOKEN; never the agent's host environment); `SimClient`
sends it. With a token table (`tokens=`; the CLI requires one) the server charges the token's identity and its budget; an unknown or
missing token, or a queue-bound token arriving through any other queue, is refused, and a request's "agent" field is ignored.
Without a token table (orchestrator-internal services whose clients are orchestrator code) names are taken from the request, but
only from the CLOSED set declared in `budgets` when one is given. Clients never learn whether a trajectory was cached (the
computed / cached split stays in the orchestrator ledger), see only their OWN ledger (`{"op": "ledger"}`), and get served keys that
are keyed by the engine and a per-service secret (review H, minor 8; never an oracle of system hashes). Restarts must come from a
trajectory of the SAME system (served or public), at one of its sample times (review H, M6). Errors are generic ("simulation failed
(reference ...)"); their details are logged in the ledger directory, outside the room (review F, minor 5). Records that failed or hold
non-finite values are never stored (review H, M4); real systems are simulated only on gated hosts (review H, M5).

CACHE ISOLATION (review F round 2, N-M1: a trajectory another agent had already asked for came back in 3-5 ms, a new one in about
270 ms). Every token-identified agent has its OWN store namespace (`SimServer.store_for`: <store>/agents/<name>-<hash>/, a complete
TrajectoryStore): its requests read and write only there, so what another agent asked never changes which files a request touches
or how long it takes; each agent's repeats of its OWN requests are served from its namespace. Public restart sources are
recomputed into each agent's namespace on its first restart from them (`_ensure_source`). Real FULL networks go to the remote
backend with the shared volume store neither read nor written for an agent's job (job["fresh"]); their restart sources travel
from the agent's namespace in the payload (public ones are read from the volume store, which every build fills). Trusted in-process
callers (`agent=`) share the service store. Cost: one extra simulation and one extra record per (agent, trajectory) that several
agents request, charged to nobody and bounded by the agents' budgets.

    uv run --project phase4 python -m brainir_causal.simservice --room <room> --systems <internal systems JSON> --store <dir>
        --tokens <token table JSON, outside the room> --ledger-dir <outside the room> --public-keys <build_public_keys JSON>
        --docker [--warm dev:<seed>] [--modal]                  # rooms: scripts/p4/simservice_docker.py start / status / stop
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import time
import traceback
import uuid
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from . import families as F
from . import protocol as P
from .accounting import Ledger, experiment_cost

PUBLIC_SEED_MAX = 10**9
DEFAULT_BUDGET = 3000
PUBLIC_KEYS_FORMAT = "p4-public-keys-2"
MAX_SOURCE_DEPTH = 8                 # longest chain of public restart sources the service recomputes
TOKEN_ENV = "P4_SIM_TOKEN"
#: the ledger fields a client may see (never the computed / cached split: a cross-agent cache-membership oracle, review F M4)
CLIENT_LEDGER_KEYS = ("experiments", "trajectories", "simulated_s", "units", "unique_targets", "magnitude", "magnitude_total")


# ------------------------------------------------------------------------------------------------ identity tokens
def token_hash(token: str) -> str:
    return hashlib.sha256(("p4-sim-token|" + str(token)).encode()).hexdigest()


def load_tokens(path: Path | str) -> dict:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def issue_token(tokens_path: Path | str, agent: str, budget: int | None = None, *, kind: str = "agent", queue: str | None = None,
                revoke_queue: bool = False) -> str:
    """LAUNCHER SIDE (never inside a room): a fresh secret token for one agent, or one experiment loop (kind 'loop', its own budget),
    recorded by its sha256 in the service's token table; hand the token to that process only. `queue`: the agent's queue name (its
    scratch name: requests arrive in simq/<queue>/); the service accepts the token ONLY through that queue (review F round 2, N-M1).
    `revoke_queue`: drop the earlier tokens bound to the same queue (one live token per queue; a relaunch replaces its token)."""
    if queue is not None and not (isinstance(queue, str) and queue and all(c.isalnum() or c in "_.-" for c in queue)
                                  and not queue.startswith(".")):
        raise ValueError(f"invalid queue name {queue!r}")
    token = secrets.token_hex(32)
    p = Path(tokens_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    table = load_tokens(p)
    if revoke_queue and queue is not None:
        table = {h: e for h, e in table.items() if e.get("queue") != queue}
    table[token_hash(token)] = {"agent": str(agent), "budget": None if budget is None else int(budget), "kind": kind, "queue": queue,
                                "issued": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    tmp = p.with_name(f"{p.name}.{uuid.uuid4().hex[:8]}.tmp")
    tmp.write_text(json.dumps(table, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, p)
    return token


def client_ledger(led: Ledger) -> dict:
    d = led.to_dict()
    return {k: d[k] for k in CLIENT_LEDGER_KEYS if k in d}


# ------------------------------------------------------------------------------------------------ public restart sources
def build_public_keys(set_dirs, *, systems=None) -> dict:
    """The service's table of PUBLIC restart sources from public dataset directories (p4-dataset-1; ORCHESTRATOR SIDE): {"format",
    "entries": {trajectory key: {"store_key", "system", "dt", "t_end", "protocol"}}, "aliases": {store key: trajectory key}}.
    Every row of index.jsonl (items, twins, components, pool sources) is a source; `systems` restricts it to the served systems. The
    row's protocol is what the benchmark simulated for it, so the service can recompute a source its store lacks."""
    entries: dict[str, dict] = {}
    aliases: dict[str, str] = {}
    for d in set_dirs:
        idx = Path(d) / "index.jsonl"
        if not idx.exists():
            continue
        for line in idx.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if systems is not None and r["system_id"] not in systems:
                continue
            sk = (r.get("meta") or {}).get("store_key")
            if not sk:
                continue
            q = r["protocol"]
            entries[r["key"]] = {"store_key": str(sk), "system": r["system_id"], "dt": float(q["dt"]), "t_end": float(q["t_end"]),
                                 "protocol": q}
            traj = Path(d) / "traj" / f"{r['key']}.npz"
            if traj.exists():            # the public arrays a recomputed source must reproduce (review H round 3, NEW-1)
                entries[r["key"]]["traj"] = str(traj)
            aliases.setdefault(str(sk), r["key"])
    return {"format": PUBLIC_KEYS_FORMAT, "entries": entries, "aliases": {k: v for k, v in sorted(aliases.items()) if k not in entries}}


def expand_public_keys(pk: dict | None) -> dict:
    """The flat lookup table {key: entry} of a `build_public_keys` table (a store-key alias shares its trajectory's entry); a legacy
    flat table {trajectory key: store key | entry} is returned unchanged."""
    if not pk:
        return {}
    if pk.get("format") != PUBLIC_KEYS_FORMAT:
        return dict(pk)
    flat = dict(pk["entries"])
    for sk, tk in (pk.get("aliases") or {}).items():
        if tk in flat:
            flat.setdefault(sk, flat[tk])
    return flat


# ------------------------------------------------------------------------------------------------ public policy
def _units_of(e: dict) -> list[int]:
    k = e["kind"]
    if k == "kick":
        return [int(u) for u in e["delta"]]
    if k in ("current", "current_seq", "param"):
        return [int(u) for u in e["targets"]]
    if k == "silence":
        return [int(u) for u in e["targets"]]
    return []


def check_public(q: dict, sysrec: dict, *, allowed_restart_keys=None) -> str | None:
    """None if the canonical protocol q may be simulated for development on this system, else the reason."""
    cap = sysrec.get("capability") or {}
    split = sysrec.get("split") or {}
    tim = cap.get("timing") or {}
    seed_max = int((cap.get("params") or {}).get("public_seed_max", PUBLIC_SEED_MAX))
    if not (0 <= int(q["params_seed"]) < seed_max):
        return f"params_seed outside the public range [0, {seed_max})"
    dev_spread = float((cap.get("params") or {}).get("dev_spread", 1.0))
    if abs(float(q["params_spread"]) - dev_spread) > 1e-12:
        return f"params_spread must be {dev_spread:g} in development"
    pn = q["process_noise"]
    if pn is not None:
        pcap = cap.get("process_noise") or {}
        dmax = pcap.get("dev_max_sd")
        if not pcap.get("supported") or dmax is None:
            return "process noise is not a development condition on this system"
        if pn["sd"] > float(dmax) + 1e-12 or not (0 <= pn["seed"] < seed_max):
            return f"process_noise needs sd <= {dmax} and a public seed"
    if sysrec.get("dt") is not None and abs(q["dt"] - float(sysrec["dt"])) > 1e-12:
        return f"dt must be the nominal dt ({float(sysrec['dt']):g} s) in development"      # review H, M3
    if tim.get("dt_allowed") and not any(abs(q["dt"] - d) < 1e-12 for d in tim["dt_allowed"]):
        return f"dt must be one of {tim['dt_allowed']}"
    if tim.get("t_end_max") is not None and q["t_end"] > float(tim["t_end_max"]) + 1e-9:
        return f"t_end must be <= {tim['t_end_max']} s"
    wn = q["weight_noise"]
    if wn is not None:
        mx = float((cap.get("weight_noise") or {}).get("max_sd", 0.0))
        if wn["sd"] > mx + 1e-12 or not (0 <= wn["seed"] < seed_max):
            return f"weight_noise needs sd <= {mx} and a public seed"
    on = q["obs_noise"]
    if on is not None:
        mx = float((cap.get("obs_noise") or {}).get("max_sd", 0.0))
        if on["sd"] > mx + 1e-12 or not (0 <= on["seed"] < seed_max):
            return f"obs_noise needs sd <= {mx} and a public seed"
    st = cap.get("stimulus") or {}
    lo, hi = (st.get("range") or [-P.MAX_ABS_STIM, P.MAX_ABS_STIM])
    chans = int(st.get("channels", 1))
    for _, v in q["stimulus"]:
        vals = v if isinstance(v, list) else [v]
        if isinstance(v, list) and len(vals) != chans:
            return f"stimulus needs {chans} channel(s)"
        for s in vals:
            if s == 0.0 and st.get("allow_zero", True):
                continue
            if not (lo - 1e-12 <= s <= hi + 1e-12):
                return f"stimulus value {s} outside the public range [{lo}, {hi}] (or 0)"
    r0 = q["r0"]
    ini = cap.get("init") or {}
    if r0["kind"] == "state":
        if not ini.get("state"):
            return "explicit initial states are not a development protocol on this system"
        allowed = {int(u) for u in (sysrec.get("observed") or [])} if ini.get("units", "observed") == "observed" else None
        vmax = float(ini.get("max_value", float("inf")))
        vmin = float(ini.get("min_value", 0.0))
        for k, v in r0["values"].items():
            if allowed is not None and int(k) not in allowed:
                return "initial states may set observed units only"
            if not (vmin - 1e-12 <= v <= vmax + 1e-12):
                return f"initial state values must be in [{vmin}, {vmax}]"
    elif r0["kind"] == "restart":
        if not ini.get("restart"):
            return "restarts are not a development protocol on this system"
        if allowed_restart_keys is None or r0["key"] not in allowed_restart_keys:
            return "restart keys must be trajectories served to you or public trajectories"
    if any(e["kind"] in P.TRUTH_KINDS for e in q["events"]):
        return "latent (truth) events are evaluator-only"
    fam = F.family_of(q, sysrec)
    if fam not in (split.get("families_train") or []):
        if fam in (split.get("families_heldout") or []):
            return f"family {fam!r} is held out on this system"
        if fam in (split.get("hidden_only") or []) or fam in F.HIDDEN_ONLY:
            return f"family {fam!r} is never a development family"
        return f"protocol family {fam!r} is not a development family on this system"
    targets = {int(u) for u in sysrec.get("targets_public") or []}
    edges = {(int(a), int(b)) for a, b in sysrec.get("edges_public") or []}
    for e in q["events"]:
        k = e["kind"]
        bad = [u for u in _units_of(e) if u not in targets]
        if bad:
            return f"{k}: targets must be public targets (not {bad[:5]})"
        if k == "edge_scale":
            if any((int(a), int(b)) not in edges for a, b in e["edges"]):
                return "edge_scale: edges must be public edges"
            mod = float((cap.get("edge_scale") or {}).get("moderate", 1.0 / 3.0))
            if e["factor"] > 0 and 1.0 - e["factor"] > 3 * mod + 1e-12:
                return f"edge_scale: weakening depth 1 - factor must be <= {3 * mod:g} (or factor 0)"
        if k == "kick":
            mx = float((cap.get("kick") or {}).get("max", float("inf")))
            if any(abs(v) > mx + 1e-12 for v in e["delta"].values()):
                return f"kick: |delta| must be <= {mx:g}"
        if k in ("current", "current_seq"):
            mx = float((cap.get(k) or cap.get("current") or {}).get("max", float("inf")))
            vals = e["targets"].values() if k == "current" else [v for lst in e["targets"].values() for v in lst]
            if any(abs(v) > mx + 1e-12 for v in vals):
                return f"{k}: |I| must be <= {mx:g}"
        if k == "param":
            mod = (cap.get("param") or {}).get("moderate") or {}
            for v in e["targets"].values():
                for fld, x in v.items():
                    m = 3 * float(mod.get(fld, 1.0 / 3.0))
                    dev = abs(x - 1.0) if fld in ("gain", "tau") else abs(x)
                    if dev > m + 1e-12:
                        return f"param: {fld} change must be within the development range ({m:g})"
    return None


# ------------------------------------------------------------------------------------------------ worker side
_ENGINES: dict = {}


def register_generators(generators: dict | None) -> None:
    """Register synthetic generators {name: (directory, package)} in THIS process (idempotent)."""
    if not generators:
        return
    from .synthadapter import register_generator
    for name, (gdir, pkg) in generators.items():
        register_generator(str(gdir), str(pkg), str(name))


def worker_init(generators: dict | None = None, threads: int = 1) -> None:
    """Initializer of the service's worker processes: BLAS thread limits and the synthetic generators."""
    os.environ.setdefault("OMP_NUM_THREADS", str(threads))
    try:
        import threadpoolctl
        threadpoolctl.threadpool_limits(int(threads))
    except Exception:  # noqa: BLE001, S110 - thread limits are an optimisation only
        pass
    register_generators(generators)


#: the arrays a FRESH recomputation must reproduce exactly when the store already holds its key
COMPARED_ARRAYS = ("t", "x", "u", "y", "state", "rates", "z", "z_obs")


def _require_same(old: dict, new: dict, key: str) -> None:
    for k in COMPARED_ARRAYS:
        if k in old and k in new and old[k] is not None and new[k] is not None:
            a, b = np.asarray(old[k]), np.asarray(new[k])
            if a.shape != b.shape or not np.array_equal(a, b):
                raise RuntimeError(f"store record {key[:12]} not reproduced by a fresh computation ({k})")


#: synthetic tiers of the unit tests (no benchmark system): simulated on any host. Every other system, synthetic or real, is simulated
#: on the reference platform only (`run_job`).
TEST_TIERS = ("toy", "toyC", "fake")


def needs_reference_platform(sysdef: dict) -> bool:
    return not (sysdef.get("kind") == "synthetic" and sysdef.get("tier") in TEST_TIERS)


def run_job(job: dict) -> dict:
    """Simulate one validated job in this process. job: {"sysdef": internal record, "protocol": canonical, "store_root": str (the
    requester's store namespace, SimServer.store_for), "bundle": str | None, "fresh": bool (remote backends only)}. Returns the
    observed arrays and the store bookkeeping. Benchmark systems are simulated on the reference platform only (the service's Docker
    pool, the Modal images; review H round 3, NEW-1)."""
    from .store import TrajectoryStore
    sysdef, q = job["sysdef"], job["protocol"]
    if needs_reference_platform(sysdef):
        from .p4modal.gate import require_reference_platform
        require_reference_platform("a benchmark simulation")
    store = TrajectoryStore(job["store_root"])
    if sysdef.get("kind") == "synthetic":
        from .suites import check_restart_source, restart_index
        from .synthadapter import observe_synthetic, suite_systems
        sysobj = suite_systems(sysdef["tier"], int(sysdef["suite_seed"]), sysdef.get("generator", "default"))[sysdef["system_id"]]
        engine_id = f"{sysobj.engine_id}"
        system_hash = sysobj.content_hash()
        key = store.key(q, system_hash, engine_id)

        def compute():
            restart = None
            if q["r0"]["kind"] == "restart":
                src = store.get(q["r0"]["key"])
                check_restart_source(src, sysdef["system_id"], system_hash)            # same system, full state (review H, M6)
                restart = np.asarray(src["state"][restart_index(src, q["r0"]["t"])], dtype=np.float64)
            rec = sysobj.simulate(q, full=True, restart_state=restart)
            rec["info"] = {**(rec.get("info") or {}), "system_id": sysdef["system_id"], "system_hash": system_hash, "engine": engine_id}
            return rec

        meta = {"system_id": sysdef["system_id"], "system_hash": system_hash, "protocol": P.microstate_protocol(q), "source": "simservice"}
        key, rec, computed = store.get_or_compute(key, compute, meta)
        obs = observe_synthetic(rec, sysdef, q)
        return {"store_key": key, "computed": computed, **obs}
    from .realsim import RealEngine, RealSystem, observe
    net = sysdef["network"]
    if net not in _ENGINES:
        _ENGINES[net] = RealEngine(job["bundle"], net)
    system = RealSystem.from_record(sysdef)
    key, rec, computed = store.get_or_run(_ENGINES[net], system, q, sysdef["system_hash"], meta={"source": "simservice"})
    return {"store_key": key, "computed": computed, **observe(rec, system, q, sysdef.get("obs_scale"))}


def real_store_key(job: dict) -> str:
    """The store key of a real job (without simulating)."""
    from brainir.sim.model import MODEL_ID

    from .realsim import ENGINE_VERSION
    from .store import TrajectoryStore
    return TrajectoryStore.key(job["protocol"], job["sysdef"]["system_hash"], f"{ENGINE_VERSION}|{MODEL_ID}")


def finish_remote_job(job: dict, record: dict) -> dict:
    """For REMOTE backends: store a full engine record computed elsewhere (e.g. on Modal) in the local store and return what
    `run_job` returns. A remote backend is a callable jobs -> [this dict | Exception] (one per job, same order)."""
    from .realsim import RealSystem, observe
    from .store import TrajectoryStore
    store = TrajectoryStore(job["store_root"])
    sysdef, q = job["sysdef"], job["protocol"]
    key = real_store_key(job)
    old = store.get(key)
    computed = old is None
    if computed:
        store.put(key, record, {"system_id": sysdef["system_id"], "system_hash": sysdef["system_hash"],
                                "protocol": P.microstate_protocol(q), "source": "simservice-remote"})
    elif job.get("fresh"):
        _require_same(old, record, key)               # a fresh remote recomputation must reproduce the stored record exactly
        computed = True
    return {"store_key": key, "computed": computed, **observe(store.get(key), RealSystem.from_record(sysdef), q, sysdef.get("obs_scale"))}


class _Inline:
    """A synchronous executor (tests, or a service without worker processes)."""

    def submit(self, fn, *a, **kw):
        from concurrent.futures import Future
        f = Future()
        try:
            f.set_result(fn(*a, **kw))
        except Exception as e:  # noqa: BLE001
            f.set_exception(e)
        return f


class SimServer:
    """File-queue server for one room. systems: {system_id: INTERNAL record (real) or synthetic descriptor with 'tier',
    'suite_seed' and the public fields}. public_keys: {trajectory key: store key, or {"store_key", "system"}} of the public datasets
    (restart sources). pool: an executor (default: a process pool of `workers`; 'inline' = synchronous). remote_backend: see
    `finish_remote_job`; used only for real FULL networks whose microstate is not stored yet. tokens: the token table (a path, re-read
    when it changes, or a dict {sha256(token): {"agent", "budget"}}), kept OUTSIDE the room; see the module docstring (IDENTITY)."""

    def __init__(self, room: Path, systems: dict, store_root: Path, *, bundle: Path | None = None, budgets: dict[str, int] | None = None,
                 default_budget: int = DEFAULT_BUDGET, workers: int = 4, public_keys: dict | None = None,
                 remote_backend: Callable[[list[dict]], list] | None = None, ledger_dir: Path | None = None, pool=None,
                 generators: dict | None = None, tokens: Path | str | dict | None = None):
        self.q = Path(room) / "simq"
        for d in ("requests", "results"):
            (self.q / d).mkdir(parents=True, exist_ok=True)
        self.systems, self.store_root, self.bundle = systems, Path(store_root), bundle
        # synthetic generators: registered here (inline pools, bookkeeping) and in every worker of the default pool
        self.generators = {str(k): (str(v[0]), str(v[1])) for k, v in (generators or {}).items()}
        register_generators(self.generators)
        missing = sorted({str(s.get("generator", "default")) for s in systems.values() if s.get("kind") == "synthetic"
                          and s.get("tier") not in ("toy", "toyC")} - set(self.generators))
        if missing and pool in (None, "inline"):
            from .synthadapter import _GENERATORS
            missing = [m for m in missing if m not in _GENERATORS]
            if missing:
                raise ValueError(f"synthetic systems need generators {missing}: pass generators={{name: (directory, package)}}")
        self.budgets, self.default_budget = dict(budgets or {}), default_budget
        self.public_keys = expand_public_keys(public_keys)
        #: store key -> public entry with its protocol (the sources `_ensure_source` can recompute)
        self._public_src = {e["store_key"]: e for e in self.public_keys.values() if isinstance(e, dict) and e.get("protocol")}
        self.n_sources_recomputed = 0
        self.n_sources_verified = 0          # recomputed sources whose arrays were compared with the public data
        self.remote_backend = remote_backend
        self.tokens = tokens
        self._tok_cache: tuple[float, dict] | None = None
        self.ledger_dir = Path(ledger_dir) if ledger_dir else self.store_root / "simservice"
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.ledger_dir / "ledger.json"
        self.keys_path = self.ledger_dir / "served_keys.json"
        self.log_path = self.ledger_dir / "requests.jsonl"
        self.errors_path = self.ledger_dir / "errors.jsonl"
        salt_path = self.ledger_dir / "served_key_salt.txt"
        if not salt_path.exists():
            salt_path.write_text(secrets.token_hex(16), encoding="utf-8")
        self.key_salt = salt_path.read_text(encoding="utf-8").strip()
        raw = json.loads(self.ledger_path.read_text(encoding="utf-8")) if self.ledger_path.exists() else {}
        self.ledgers = {a: Ledger.from_dict(d) for a, d in raw.items()}
        self.served = json.loads(self.keys_path.read_text(encoding="utf-8")) if self.keys_path.exists() else {}
        self._engines: dict[str, str] = {}
        if pool == "inline":
            pool = _Inline()
        self.pool = pool if pool is not None else ProcessPoolExecutor(max_workers=workers, initializer=worker_init,
                                                                      initargs=(self.generators, 1))
        describe = getattr(self.pool, "describe", None)                  # a reference-platform pool knows the synthetic engine ids
        syn = [s for s in systems.values() if s.get("kind") == "synthetic"]
        if describe is not None and syn:
            self._engines.update(describe([{k: s[k] for k in ("system_id", "tier", "suite_seed")} for s in syn]))

    # ---------------------------------------------------------------- identity
    def _token_table(self) -> dict | None:
        if self.tokens is None:
            return None
        if isinstance(self.tokens, dict):
            return self.tokens
        p = Path(self.tokens)
        mt = p.stat().st_mtime if p.exists() else -1.0
        if self._tok_cache is None or self._tok_cache[0] != mt:
            self._tok_cache = (mt, load_tokens(p))
        return self._tok_cache[1]

    def identity(self, req: dict, agent: str | None = None, queue: str | None = None) -> tuple[str, int]:
        """(identity, budget) of a request. `agent`: a TRUSTED in-process caller's identity (orchestrator code, tests); otherwise the
        token (token table) or, without a token table, the request's name from the closed set of `budgets` (when given). `queue`: the
        agent queue the request arrived in (None = the shared queue simq/requests of trusted callers); a token bound to a queue is
        refused in any other queue (review F round 2, N-M1: tokens are not portable)."""
        if agent is not None:
            return str(agent), int(self.budgets.get(str(agent), self.default_budget))
        table = self._token_table()
        if table is not None:
            ent = table.get(token_hash(req.get("token"))) if req.get("token") else None
            if ent and ent.get("queue") is not None and ent.get("queue") != queue:
                ent = None                                  # the same generic refusal as an unknown token (no oracle)
            if not ent:
                raise PermissionError("missing or unknown simulation token (the sandbox passes yours as P4_SIM_TOKEN; it is valid only "
                                      "in your own queue)")
            name = str(ent["agent"])
            b = ent.get("budget")
            return name, int(b if b is not None else self.budgets.get(name, self.default_budget))
        name = str(req.get("agent") or "default")
        if self.budgets and name not in self.budgets:
            raise PermissionError("unknown agent (this service serves only the agents declared by its owner)")
        return name, int(self.budgets.get(name, self.default_budget))

    # ---------------------------------------------------------------- bookkeeping
    def _save(self) -> None:
        tmp = self.ledger_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({a: led.to_dict() for a, led in self.ledgers.items()}, indent=1), encoding="utf-8")
        os.replace(tmp, self.ledger_path)
        tmp = self.keys_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.served), encoding="utf-8")
        os.replace(tmp, self.keys_path)

    def _log_error(self, ref: str, who: str, what: str, err) -> None:
        """Details of a failure, OUTSIDE the room (the client gets the reference only; review F, minor 5)."""
        tb = "".join(traceback.format_exception(err)) if isinstance(err, BaseException) else str(err)
        with open(self.errors_path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"ref": ref, "agent": who, "what": what, "error": f"{type(err).__name__}: {err}"[:2000],
                                 "traceback": tb[-4000:], "time": time.strftime("%Y-%m-%dT%H:%M:%S")}) + "\n")

    def _write_result(self, rid: str, arrays: dict, meta: dict, qdir: Path | None = None) -> None:
        """Write a result into the queue the request came from (`qdir`: simq/ or an agent's simq/<scratch>/)."""
        res = Path(qdir or self.q) / "results"
        res.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(res / f"{rid}.tmp.npz", **arrays)
        os.replace(res / f"{rid}.tmp.npz", res / f"{rid}.npz")
        (res / f"{rid}.tmp.json").write_text(json.dumps(meta), encoding="utf-8")
        os.replace(res / f"{rid}.tmp.json", res / f"{rid}.json")

    def store_for(self, ns: str | None) -> Path:
        """The store a request reads and writes (CACHE ISOLATION): every token-identified agent has its OWN namespace
        <store>/agents/<name>-<hash>/ (a complete TrajectoryStore), trusted in-process callers (ns None) share the service store."""
        if ns is None:
            return self.store_root
        safe = re.sub(r"[^a-z0-9_.-]", "_", ns.lower())[:40].lstrip(".") or "_"
        return self.store_root / "agents" / f"{safe}-{hashlib.sha256(ns.encode()).hexdigest()[:8]}"

    def _job(self, sysdef: dict, q: dict, ns: str | None = None) -> dict:
        """run_job's argument in the store namespace `ns`; `fresh` (an agent's job) tells remote backends to neither read nor write
        the shared volume store."""
        return {"sysdef": sysdef, "protocol": q, "store_root": str(self.store_for(ns)), "bundle": str(self.bundle) if self.bundle else None,
                "fresh": ns is not None}

    def _engine_id(self, sysdef: dict) -> str:
        sid = sysdef["system_id"]
        if sid not in self._engines:
            if sysdef.get("kind") == "synthetic":
                from .synthadapter import suite_systems
                self._engines[sid] = str(suite_systems(sysdef["tier"], int(sysdef["suite_seed"]), sysdef.get("generator", "default"))[sid].engine_id)
            else:
                from brainir.sim.model import MODEL_ID

                from .realsim import ENGINE_VERSION
                self._engines[sid] = f"{ENGINE_VERSION}|{MODEL_ID}"
        return self._engines[sid]

    def served_key(self, q: dict, sysdef: dict) -> str:
        """The key a client gets for a served trajectory: the canonical protocol, the engine (review H, minor 8) and this service's
        secret salt (so it is never an oracle of engine strings or system hashes)."""
        return P.protocol_hash(q, system_hash=f"served|{self.key_salt}", simulator=self._engine_id(sysdef))

    def _restart_source(self, key: str, t: float, served: dict, system_id: str) -> str:
        """The store key of an allowed restart source of the same system, restarted at one of its sample times (review H, M6), else
        a ProtocolError (the workers check again against the stored record)."""
        ent = served.get(key)
        if ent is None:
            ent = self.public_keys.get(key)
        if ent is None:
            raise P.ProtocolError("restart keys must be trajectories served to you or public trajectories")
        if not isinstance(ent, dict):
            return str(ent)
        if ent.get("system") not in (None, system_id):
            raise P.ProtocolError("r0 'restart' must come from a trajectory of the same system")
        if ent.get("dt"):
            dt_src = float(ent["dt"])
            i = round(float(t) / dt_src)
            if abs(i * dt_src - float(t)) > 1e-12 + 1e-6 * dt_src or not (0 <= float(t) <= float(ent.get("t_end", float("inf"))) + 1e-9):
                raise P.ProtocolError(f"r0.t={t} is not a sample time of the restart source")
        return str(ent["store_key"])

    def _ensure_source(self, sysdef: dict, store_key: str, depth: int = 0, ns: str | None = None) -> None:
        """Recompute a PUBLIC restart source from its public protocol (recursively for a source that restarts itself) when it is
        missing from the request's store namespace `ns` (SimServer.store_for: every agent recomputes a public source once, in its own
        namespace, whatever other agents did). The recomputed store key must equal the public record's (same canonical protocol,
        system content hash and engine: the reference platform reproduces the benchmark's record bit for bit), else RuntimeError. Not
        charged to the agent. Sources the service does not know stay missing (the simulation then reports it); real FULL networks
        with a remote backend are left to it (their records are read from the volume store, which holds every public record)."""
        from .store import TrajectoryStore
        if TrajectoryStore(self.store_for(ns)).has(store_key):
            return
        ent = self._public_src.get(store_key)
        if ent is None or ent.get("system") not in (None, sysdef["system_id"]):
            return
        if sysdef.get("kind") == "real" and sysdef.get("mode") == "full" and self.remote_backend is not None:
            return
        if depth >= MAX_SOURCE_DEPTH:
            raise RuntimeError(f"public restart source chain deeper than {MAX_SOURCE_DEPTH}")
        q = P.validate(ent["protocol"])
        if q["r0"]["kind"] == "restart":
            self._ensure_source(sysdef, str(q["r0"]["key"]), depth + 1, ns)
        out = self.pool.submit(run_job, self._job(sysdef, q, ns)).result()
        if out["store_key"] != store_key:
            raise RuntimeError(f"public restart source {store_key[:12]} not reproduced (recomputed key {str(out['store_key'])[:12]})")
        # the store key hashes the PROTOCOL; the arrays must match too, bit for bit (a misconfigured engine would otherwise serve data
        # that silently differ from the public set; review H round 3, NEW-1). A record that does not match is removed from the
        # namespace, so a later request recomputes and checks it again instead of finding it stored.
        # FAIL CLOSED (review H round 3b, NEW-6): a source without readable public arrays, or with any array missing, is refused too
        traj = ent.get("traj")
        why = None
        try:
            if not traj or not Path(traj).is_file():
                why = "no public arrays to verify against"
            else:
                with np.load(traj, allow_pickle=False) as z:
                    for name in ("t", "x", "u", "y"):
                        if name not in z.files or name not in out:
                            why = f"{name} missing"
                            break
                        a, b = np.asarray(z[name]), np.asarray(out[name])
                        if a.shape != b.shape or not np.array_equal(a.astype(b.dtype, copy=False), b):
                            why = f"{name} differs from the public data"
                            break
        except Exception as exc:  # noqa: BLE001 - an unreadable public file is a refusal, never a pass
            why = f"public arrays unreadable ({type(exc).__name__})"
        if why:
            TrajectoryStore(self.store_for(ns)).path(store_key).unlink(missing_ok=True)
            raise RuntimeError(f"public restart source {store_key[:12]} not reproduced ({why})")
        self.n_sources_verified += 1
        self.n_sources_recomputed += 1

    def _is_remote(self, sysdef: dict, job: dict) -> bool:
        """Real FULL networks whose microstate is not stored in the job's store namespace, and any real job whose restart source is
        not there (the remote side reads it from the volume store), go to the remote backend when one is configured."""
        if self.remote_backend is None or sysdef.get("kind") != "real":
            return False
        from .store import TrajectoryStore
        store = TrajectoryStore(job["store_root"])
        if store.has(real_store_key(job)):
            return False
        q = job["protocol"]
        if q.get("r0", {}).get("kind") == "restart" and not store.has(str(q["r0"]["key"])):
            return True
        return sysdef.get("mode") == "full"

    # ---------------------------------------------------------------- one request
    def handle_request(self, req: dict, *, agent: str | None = None, queue: str | None = None) -> tuple[dict, dict]:
        """(arrays, meta) for one request dict {"token", "protocols"} or {"token", "op": "ledger"} (no file I/O on the queue). `agent`
        is for TRUSTED in-process callers only; queue requests are identified by their token, which must be bound to the request's
        `queue` when it is bound at all (module docstring, IDENTITY)."""
        who, budget = self.identity(req, agent, queue)
        led = self.ledgers.setdefault(who, Ledger())
        served = self.served.setdefault(who, {})
        if req.get("op") == "ledger":
            return {}, {"status": "done", "budget": budget, "used": led.units, "ledger": client_ledger(led),
                        "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}
        protos = req.get("protocols") or []
        items, pending = [], {}
        charge = 0
        for j, p in enumerate(protos):
            try:
                sysdef = self.systems.get(str((p or {}).get("system")))
                if sysdef is None:
                    raise P.ProtocolError(f"unknown or non-public system {(p or {}).get('system')!r}")
                q = P.validate(p)
                allowed_restart = set(self.public_keys) | set(served)
                why = check_public(q, sysdef, allowed_restart_keys=allowed_restart)
                if why:
                    raise P.ProtocolError(why)
                traj_key = self.served_key(q, sysdef)
                qq = q
                if q["r0"]["kind"] == "restart":
                    qq = json.loads(json.dumps(q))
                    qq["r0"]["key"] = self._restart_source(q["r0"]["key"], q["r0"]["t"], served, sysdef["system_id"])
                cost = experiment_cost(q, sysdef)
                if led.units + charge + cost["units"] > budget:
                    raise P.ProtocolError(f"simulation budget exhausted ({budget} units; this system costs {cost['units']} per trajectory)")
                charge += cost["units"]
                items.append({"i": j, "ok": True, "key": traj_key, "family": F.family_of(q, sysdef), "cost_units": cost["units"],
                              "experiment": cost["experiment"]})
                pending[j] = (sysdef, qq, cost, traj_key)
            except P.ProtocolError as e:                       # the public policy's own reasons (review F: they leak nothing)
                items.append({"i": j, "ok": False, "error": str(e)})
            except Exception as e:  # noqa: BLE001 - details outside the room only
                ref = uuid.uuid4().hex[:12]
                self._log_error(ref, who, "validate", e)
                items.append({"i": j, "ok": False, "error": f"protocol refused (reference {ref})"})
        results: dict[int, dict] = {}
        dedupe: dict[str, list[int]] = {}
        for j, (sysdef, qq, _, _) in pending.items():
            dedupe.setdefault(json.dumps([sysdef["system_id"], qq], sort_keys=True), []).append(j)
        remote_jobs, local_futs = [], []
        n_rec0 = self.n_sources_recomputed
        ns = None if agent is not None else who                # CACHE ISOLATION: the agent's own store namespace (trusted: shared)
        for js in dedupe.values():
            j0 = js[0]
            sysdef, qq, _, _ = pending[j0]
            job = self._job(sysdef, qq, ns)
            if qq["r0"]["kind"] == "restart":
                try:
                    self._ensure_source(sysdef, str(qq["r0"]["key"]), ns=ns)
                except Exception as e:  # noqa: BLE001 - reported per item below (generic error; details logged outside the room)
                    for j in js:
                        results[j] = e
                    continue
            if self._is_remote(sysdef, job):
                remote_jobs.append((js, job))
            else:
                local_futs.append((js, self.pool.submit(run_job, job)))
        if remote_jobs:
            try:
                outs = self.remote_backend([job for _, job in remote_jobs])
            except Exception as e:  # noqa: BLE001
                outs = [e] * len(remote_jobs)
            for (js, _), out in zip(remote_jobs, outs):
                for j in js:
                    results[j] = out
        for js, fut in local_futs:
            try:
                out = fut.result()
            except Exception as e:  # noqa: BLE001
                out = e
            for j in js:
                results[j] = out
        arrays = {}
        first_seen: set[str] = set()
        for j, (sysdef, qq, cost, traj_key) in pending.items():
            out = results.get(j)
            it = next(i for i in items if i["i"] == j)
            if isinstance(out, BaseException) or out is None or not all(k in out for k in ("t", "x", "u", "y")):
                ref = uuid.uuid4().hex[:12]
                self._log_error(ref, who, f"simulate {sysdef['system_id']}", out if out is not None else "no result")
                it.pop("key", None)
                it.update(ok=False, error=f"simulation failed (reference {ref})")
                continue
            for k in ("t", "x", "u", "y"):
                arrays[f"i{j}_{k}"] = out[k]
            computed = bool(out.get("computed")) and out["store_key"] not in first_seen
            first_seen.add(out["store_key"])
            served[traj_key] = {"store_key": out["store_key"], "system": sysdef["system_id"], "t_end": qq["t_end"], "dt": qq["dt"]}
            led.add(sysdef["system_id"], cost, computed)          # the computed / cached split stays in this (orchestrator) ledger
        self._save()
        meta = {"status": "done", "items": items, "budget": budget, "used": led.units, "ledger": client_ledger(led),
                "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with open(self.log_path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"agent": who, "n": len(protos), "ok": sum(1 for i in items if i["ok"]),
                                 "refused": [i.get("error") for i in items if not i["ok"]][:20],
                                 "public_sources_recomputed": self.n_sources_recomputed - n_rec0, "finished": meta["finished"]}) + "\n")
        return arrays, meta

    def handle(self, path: Path) -> None:
        """Answer one request file <queue>/requests/<id>.json into <queue>/results/ (the same queue: simq/ or simq/<scratch>/)."""
        rid = path.stem
        qdir = path.parent.parent
        # the queue the request arrived in: None for the shared queue simq/requests (trusted callers), else the agent's scratch name
        queue = None if os.path.normcase(os.path.abspath(qdir)) == os.path.normcase(os.path.abspath(self.q)) else qdir.name
        try:
            req = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            self._write_result(rid, {}, {"status": "error", "error": "unreadable request"}, qdir)
            path.unlink(missing_ok=True)
            return
        try:
            arrays, meta = self.handle_request(req, queue=queue)
        except PermissionError as e:
            arrays, meta = {}, {"status": "error", "error": str(e)}
        except Exception as e:  # noqa: BLE001
            ref = uuid.uuid4().hex[:12]
            self._log_error(ref, "?", "request", e)
            arrays, meta = {}, {"status": "error", "error": f"service error (reference {ref})"}
        self._write_result(rid, arrays, meta, qdir)
        path.unlink(missing_ok=True)

    def pending(self) -> list[Path]:
        """Request files of the shared queue (simq/requests, trusted callers and tests) and of every agent's own queue
        (simq/<scratch>/requests: the sandbox shows an agent only its own simq/<scratch>; launcher --scratch)."""
        found = list((self.q / "requests").glob("*.json"))
        for d in sorted(self.q.iterdir()):
            if d.is_dir() and not d.is_symlink() and d.name not in ("requests", "results") and (d / "requests").is_dir():
                found += list((d / "requests").glob("*.json"))
        return sorted(found, key=lambda p: (p.stat().st_mtime, str(p)))

    def serve_forever(self, poll: float = 0.5) -> None:
        print(f"simservice: {len(self.systems)} public systems; queue {self.q}", flush=True)
        while True:
            for p in self.pending():
                try:
                    self.handle(p)
                except Exception:  # noqa: BLE001
                    traceback.print_exc()
            time.sleep(poll)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", type=Path, required=True)
    ap.add_argument("--systems", type=Path, required=True, help="internal system records (JSON: system_id -> record)")
    ap.add_argument("--store", type=Path, required=True)
    ap.add_argument("--bundle", type=Path, default=None)
    ap.add_argument("--public-keys", type=Path, default=None, help="the public restart-source table (build_public_keys JSON)")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--ledger-dir", type=Path, required=True, help="where the ledger and the error log live (OUTSIDE the room)")
    ap.add_argument("--tokens", type=Path, required=True, help="the token table written by the launcher (issue_token; OUTSIDE the room)")
    ap.add_argument("--generator-dir", type=Path, default=None, help="the hash-locked synthetic generator directory")
    ap.add_argument("--generator-package", default="p4synth")
    ap.add_argument("--generator-name", default="default")
    ap.add_argument("--modal", action="store_true", help="real full networks (and restarts from volume-stored records) on Modal")
    ap.add_argument("--docker", action="store_true", help="every local simulation on the reference platform (simdocker.DockerPool)")
    ap.add_argument("--bridge-dir", type=Path, default=None, help="the Docker pool's bridge directory (default: <ledger-dir>/../bridge)")
    ap.add_argument("--docker-workers", type=int, default=4)
    ap.add_argument("--docker-cpus", type=float, default=4.0)
    ap.add_argument("--docker-mem-gb", type=int, default=8)
    ap.add_argument("--warm", action="append", default=[], metavar="TIER:SEED", help="synthetic suites the container builds at start")
    ap.add_argument("--name", default=None, help="the worker container's name")
    args = ap.parse_args(argv)
    room = args.room.resolve()
    for p in (args.ledger_dir.resolve(), args.tokens.resolve()):
        if p == room or room in p.parents:
            raise SystemExit(f"{p} lies inside the room: the ledger and the token table must stay outside it")
    systems = json.loads(args.systems.read_text(encoding="utf-8"))
    if not args.docker and any(needs_reference_platform(s) for s in systems.values()):
        from .p4modal.gate import reference_platform_problems
        bad = reference_platform_problems()
        if bad:        # every local simulation of these systems would be refused (run_job): say so at start, not per request
            raise SystemExit("benchmark systems are simulated on the reference platform only: start the service with --docker ("
                             + "; ".join(bad) + ")")
    pk = json.loads(args.public_keys.read_text(encoding="utf-8")) if args.public_keys else {}
    gens = {args.generator_name: (str(args.generator_dir.resolve()), args.generator_package)} if args.generator_dir else None
    kw = {"bundle": args.bundle, "default_budget": args.budget, "workers": args.workers, "public_keys": pk, "ledger_dir": args.ledger_dir,
          "generators": gens, "tokens": args.tokens}
    pool = None
    if args.docker:
        from .simdocker import DockerPool
        for p in (args.store.resolve(), (args.bridge_dir or args.ledger_dir.parent / "bridge").resolve()):
            if p == room or room in p.parents:
                raise SystemExit(f"{p} lies inside the room: the store and the bridge must stay outside it")
        warm = [(w.rsplit(":", 1)[0], int(w.rsplit(":", 1)[1])) for w in args.warm]
        pool = DockerPool(store_root=args.store, bridge_dir=args.bridge_dir or args.ledger_dir.parent / "bridge", bundle=args.bundle,
                          workers=args.docker_workers, cpus=args.docker_cpus, mem_gb=args.docker_mem_gb, warm=warm, name=args.name,
                          generator_dir=args.generator_dir).start()
        kw.update(pool=pool, generators=None)
    try:
        if args.modal:
            from .p4modal.app import Backend
            with Backend(classes=["sim"]) as be:
                SimServer(args.room, systems, args.store, remote_backend=be.remote_backend(), **kw).serve_forever()
            return 0
        SimServer(args.room, systems, args.store, **kw).serve_forever()
        return 0
    finally:
        if pool is not None:
            pool.shutdown()


if __name__ == "__main__":
    # run the PACKAGE module's main: under `python -m` this file is also `__main__`, and a second copy of SimServer / run_job would
    # not be the objects a worker pool recognises (simdocker.DockerPool; pickling for process pools)
    from brainir_causal.simservice import main as _package_main
    raise SystemExit(_package_main())
