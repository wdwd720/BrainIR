"""Budgeted simulation service for Phase 4 rooms (ORCHESTRATOR SIDE; research/phase4/INTERFACES.md section 8; goal5 sections 28, 61).

Developers never get simulator code: they drop request files into <room>/simq/requests/ (`brainir_causal.simclient.SimClient`) and
read results from <room>/simq/results/. This server
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
the public datasets (`public_keys`: trajectory key -> store key); the server rewrites them to store keys before simulating.

    uv run --project phase4 python -m brainir_causal.simservice --room <room> --systems <internal systems JSON> --store <dir>
"""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from . import families as F
from . import protocol as P
from .accounting import Ledger, experiment_cost

PUBLIC_SEED_MAX = 10**9
DEFAULT_BUDGET = 3000


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


def run_job(job: dict) -> dict:
    """Simulate one validated job in this process. job: {"sysdef": internal record, "protocol": canonical, "store_root": str,
    "bundle": str | None}. Returns the observed arrays and the store bookkeeping."""
    from .store import TrajectoryStore
    sysdef, q = job["sysdef"], job["protocol"]
    store = TrajectoryStore(job["store_root"])
    if sysdef.get("kind") == "synthetic":
        from .synthadapter import observe_synthetic, suite_systems
        sysobj = suite_systems(sysdef["tier"], int(sysdef["suite_seed"]), sysdef.get("generator", "default"))[sysdef["system_id"]]
        engine_id = f"{sysobj.engine_id}"
        key = store.key(q, sysobj.content_hash(), engine_id)

        def compute():
            restart = None
            if q["r0"]["kind"] == "restart":
                src = store.get(q["r0"]["key"])
                if src is None or "state" not in src:
                    raise P.ProtocolError("restart source not in the store (or stored without its full state)")
                i = int(round(q["r0"]["t"] / float(src["t"][1] - src["t"][0])))
                restart = np.asarray(src["state"][i], dtype=np.float64)
            return sysobj.simulate(q, full=True, restart_state=restart)

        key, rec, computed = store.get_or_compute(key, compute, {"system_id": sysdef["system_id"], "system_hash": sysobj.content_hash(),
                                                                  "protocol": P.microstate_protocol(q), "source": "simservice"})
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
    computed = not store.has(key)
    if computed:
        store.put(key, record, {"system_id": sysdef["system_id"], "system_hash": sysdef["system_hash"],
                                "protocol": P.microstate_protocol(q), "source": "simservice-remote"})
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
    'suite_seed' and the public fields}. public_keys: {trajectory key: store key} of the public datasets (restart sources).
    pool: an executor (default: a process pool of `workers`; 'inline' = synchronous). remote_backend: see `finish_remote_job`;
    used only for real FULL networks whose microstate is not stored yet."""

    def __init__(self, room: Path, systems: dict, store_root: Path, *, bundle: Path | None = None, budgets: dict[str, int] | None = None,
                 default_budget: int = DEFAULT_BUDGET, workers: int = 4, public_keys: dict[str, str] | None = None,
                 remote_backend: Callable[[list[dict]], list] | None = None, ledger_dir: Path | None = None, pool=None):
        self.q = Path(room) / "simq"
        for d in ("requests", "results"):
            (self.q / d).mkdir(parents=True, exist_ok=True)
        self.systems, self.store_root, self.bundle = systems, Path(store_root), bundle
        self.budgets, self.default_budget = dict(budgets or {}), default_budget
        self.public_keys = dict(public_keys or {})
        self.remote_backend = remote_backend
        self.ledger_dir = Path(ledger_dir) if ledger_dir else self.store_root / "simservice"
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.ledger_dir / "ledger.json"
        self.keys_path = self.ledger_dir / "served_keys.json"
        self.log_path = self.ledger_dir / "requests.jsonl"
        raw = json.loads(self.ledger_path.read_text(encoding="utf-8")) if self.ledger_path.exists() else {}
        self.ledgers = {a: Ledger.from_dict(d) for a, d in raw.items()}
        self.served = json.loads(self.keys_path.read_text(encoding="utf-8")) if self.keys_path.exists() else {}
        if pool == "inline":
            pool = _Inline()
        self.pool = pool if pool is not None else ProcessPoolExecutor(max_workers=workers)

    # ---------------------------------------------------------------- bookkeeping
    def _save(self) -> None:
        tmp = self.ledger_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({a: led.to_dict() for a, led in self.ledgers.items()}, indent=1), encoding="utf-8")
        os.replace(tmp, self.ledger_path)
        tmp = self.keys_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.served), encoding="utf-8")
        os.replace(tmp, self.keys_path)

    def _write_result(self, rid: str, arrays: dict, meta: dict) -> None:
        np.savez_compressed(self.q / "results" / f"{rid}.tmp.npz", **arrays)
        os.replace(self.q / "results" / f"{rid}.tmp.npz", self.q / "results" / f"{rid}.npz")
        (self.q / "results" / f"{rid}.tmp.json").write_text(json.dumps(meta), encoding="utf-8")
        os.replace(self.q / "results" / f"{rid}.tmp.json", self.q / "results" / f"{rid}.json")

    def _job(self, sysdef: dict, q: dict) -> dict:
        return {"sysdef": sysdef, "protocol": q, "store_root": str(self.store_root), "bundle": str(self.bundle) if self.bundle else None}

    def _is_remote(self, sysdef: dict, job: dict) -> bool:
        if self.remote_backend is None or sysdef.get("kind") != "real" or sysdef.get("mode") != "full":
            return False
        from .store import TrajectoryStore
        return not TrajectoryStore(self.store_root).has(real_store_key(job))

    # ---------------------------------------------------------------- one request
    def handle_request(self, req: dict) -> tuple[dict, dict]:
        """(arrays, meta) for one request dict {"agent", "protocols"} (no file I/O on the queue)."""
        agent = str(req.get("agent", "unknown"))
        protos = req.get("protocols") or []
        budget = int(self.budgets.get(agent, self.default_budget))
        led = self.ledgers.setdefault(agent, Ledger())
        served = self.served.setdefault(agent, {})
        allowed_restart = set(self.public_keys) | set(served)
        items, pending = [], {}
        charge = 0
        for j, p in enumerate(protos):
            try:
                sysdef = self.systems.get(str((p or {}).get("system")))
                if sysdef is None:
                    raise P.ProtocolError(f"unknown or non-public system {(p or {}).get('system')!r}")
                q = P.validate(p)
                why = check_public(q, sysdef, allowed_restart_keys=allowed_restart)
                if why:
                    raise P.ProtocolError(why)
                traj_key = P.protocol_hash(q)
                qq = q
                if q["r0"]["kind"] == "restart":
                    src = self.public_keys.get(q["r0"]["key"]) or served.get(q["r0"]["key"])
                    qq = json.loads(json.dumps(q))
                    qq["r0"]["key"] = src
                cost = experiment_cost(q, sysdef)
                if led.units + charge + cost["units"] > budget:
                    raise P.ProtocolError(f"simulation budget exhausted ({budget} units; this system costs {cost['units']} per trajectory)")
                charge += cost["units"]
                items.append({"i": j, "ok": True, "key": traj_key, "family": F.family_of(q, sysdef), "cost_units": cost["units"],
                              "experiment": cost["experiment"]})
                pending[j] = (sysdef, qq, cost, traj_key)
            except Exception as e:  # noqa: BLE001
                items.append({"i": j, "ok": False, "error": str(e)})
        results: dict[int, dict] = {}
        dedupe: dict[str, list[int]] = {}
        for j, (sysdef, qq, _, _) in pending.items():
            dedupe.setdefault(json.dumps([sysdef["system_id"], qq], sort_keys=True), []).append(j)
        remote_jobs, local_futs = [], []
        for js in dedupe.values():
            j0 = js[0]
            sysdef, qq, _, _ = pending[j0]
            job = self._job(sysdef, qq)
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
            if isinstance(out, Exception) or out is None:
                it.update(ok=False, error=f"simulation failed: {out}")
                continue
            for k in ("t", "x", "u", "y"):
                arrays[f"i{j}_{k}"] = out[k]
            computed = bool(out.get("computed")) and out["store_key"] not in first_seen
            first_seen.add(out["store_key"])
            it.update(cached=not computed)
            served[traj_key] = out["store_key"]
            led.add(sysdef["system_id"], cost, computed)
        self._save()
        meta = {"status": "done", "agent": agent, "items": items, "budget": budget, "used": led.units, "ledger": {
            k: v for k, v in led.to_dict().items() if k != "targets"}, "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with open(self.log_path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"agent": agent, "n": len(protos), "ok": sum(1 for i in items if i["ok"]),
                                 "refused": [i.get("error") for i in items if not i["ok"]][:20], "finished": meta["finished"]}) + "\n")
        return arrays, meta

    def handle(self, path: Path) -> None:
        rid = path.stem
        try:
            req = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            self._write_result(rid, {}, {"status": "error", "error": f"unreadable request: {e}"})
            path.unlink(missing_ok=True)
            return
        try:
            arrays, meta = self.handle_request(req)
        except Exception as e:  # noqa: BLE001
            arrays, meta = {}, {"status": "error", "error": f"service error: {e}"}
            traceback.print_exc()
        self._write_result(rid, arrays, meta)
        path.unlink(missing_ok=True)

    def serve_forever(self, poll: float = 0.5) -> None:
        print(f"simservice: {len(self.systems)} public systems; queue {self.q}", flush=True)
        while True:
            for p in sorted((self.q / "requests").glob("*.json")):
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
    ap.add_argument("--public-keys", type=Path, default=None, help="JSON {trajectory key: store key} of the public datasets")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--ledger-dir", type=Path, default=None, help="where the ledger lives (outside the room)")
    args = ap.parse_args(argv)
    systems = json.loads(args.systems.read_text(encoding="utf-8"))
    pk = json.loads(args.public_keys.read_text(encoding="utf-8")) if args.public_keys else {}
    SimServer(args.room, systems, args.store, bundle=args.bundle, default_budget=args.budget, workers=args.workers, public_keys=pk,
              ledger_dir=args.ledger_dir).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
