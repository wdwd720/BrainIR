"""Budgeted simulation service for clean-room agents (ORCHESTRATOR SIDE; goal4 sections 3, 28, 29, 51).

Agents never get simulator code: they drop request files into <clean>/simq/requests/ and read results from <clean>/simq/results/.
This server validates every protocol against the PUBLIC policy of state_discovery_v1 (public systems, public seed range, public
stimulus range, microscopic event kinds and targets allowed for development), charges the agent's budget, serves from the
content-addressed store, and writes the observed arrays back. What the policy refuses (hidden seeds, held-out targets, group
silencing, out-of-distribution inputs, edge removal) is exactly what the hidden test holds out, so it cannot be trained on.

    uv run --project phase3 python -m brainir_state.simservice --clean C:\\Dev\\BrainIR_p3clean --systems <systems.json>
"""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from . import protocol as P
from .realgen import HIDDEN_SEED_BASE

PUBLIC_STIM_RANGE = (0.55, 1.45)
MAX_KICK, MAX_CURRENT, MAX_PULSE_S, MAX_T_END = 50.0, 60.0, 0.5, 4.0
ALLOWED_DT = (0.001, 0.002, 0.005)
MAX_WEIGHT_NOISE = 0.1


def check_public(q: dict, sysdef: dict) -> str | None:
    """None if the canonical protocol q is allowed for development on this system, else the reason."""
    if q["params_seed"] < 0 or q["params_seed"] >= HIDDEN_SEED_BASE:
        return "params_seed outside the public range [0, 1e9)"
    wn = q["weight_noise"]
    if wn is not None and (wn["sd"] > MAX_WEIGHT_NOISE or not (0 <= wn["seed"] < HIDDEN_SEED_BASE)):
        return f"weight_noise must have sd <= {MAX_WEIGHT_NOISE} and a public seed"
    if q["t_end"] > MAX_T_END or not any(abs(q["dt"] - d) < 1e-12 for d in ALLOWED_DT):
        return f"t_end <= {MAX_T_END} s and dt in {ALLOWED_DT} only"
    for _, s in q["stimulus"]:
        if s != 0.0 and not (PUBLIC_STIM_RANGE[0] <= s <= PUBLIC_STIM_RANGE[1]):
            return f"stimulus scale {s} outside the public range {PUBLIC_STIM_RANGE} (or 0)"
    observed = {int(n) for n in sysdef["observed"]}
    targets_A = {int(n) for n in sysdef["targets_public"]}
    if q["r0"]["kind"] == "state":
        bad = [k for k, v in q["r0"]["values"].items() if int(k) not in observed or v > 200]
        if bad:
            return "initial state may set observed neurons only, with rates <= 200 Hz"
    silence_windows = []
    for e in q["events"]:
        if e["kind"] == "edge_remove":
            return "edge removal is not a development intervention"
        if e["kind"] == "kick":
            if not set(int(n) for n in e["delta"]) <= targets_A or any(abs(v) > MAX_KICK for v in e["delta"].values()):
                return "kicks: public targets only, |delta| <= 50"
        if e["kind"] == "current":
            if not set(int(n) for n in e["targets"]) <= targets_A or any(abs(v) > MAX_CURRENT for v in e["targets"].values()) \
                    or e["t1"] - e["t0"] > MAX_PULSE_S:
                return "currents: public targets only, |I| <= 60, duration <= 0.5 s"
        if e["kind"] == "silence":
            if len(e["targets"]) != 1 or int(e["targets"][0]) not in targets_A:
                return "silencing: one public target per event"
            silence_windows.append((e["t0"], q["t_end"] if e["t1"] is None else e["t1"]))
    silence_windows.sort()
    for (a0, a1), (b0, _) in zip(silence_windows, silence_windows[1:]):
        if b0 < a1:
            return "overlapping silencing windows (group silencing) are held out"
    return None


# ------------------------------------------------------------------------------------------------ worker side
_ENGINES: dict = {}


def _synth_worker(sysdef: dict, proto: dict) -> dict:
    from .synthsim import simulate
    out = simulate(sysdef["tier"], int(sysdef["suite_seed"]), sysdef["system_id"], proto)
    return {"key": None, "computed": True, "t": out["t"], "x": out["x"], "y": out["y"], "u": out["u"], "engine": "p3synth"}


def _worker(args):
    bundle, sysdef, proto, store_root = args
    if sysdef.get("kind") == "synthetic":
        return _synth_worker(sysdef, proto)
    from .realsim import ENGINE_VERSION, RealEngine, RealSystem, dense
    from .store import TrajectoryStore
    net = sysdef["network"]
    if net not in _ENGINES:
        _ENGINES[net] = RealEngine(bundle, net)
    eng = _ENGINES[net]
    system = RealSystem(system_id=sysdef["system_id"], network=net, mode=sysdef["mode"], keep=tuple(sysdef.get("keep", [])),
                        observed=tuple(sysdef["observed"]), readout=tuple(sysdef["readout"]), stimulus=tuple(sysdef["stimulus"]))
    store = TrajectoryStore(store_root)
    key, rec, computed = store.get_or_run(eng, system, proto, sysdef["system_hash"], meta={"source": "simservice"})
    return {"key": key, "computed": computed, "t": rec["t"], "x": dense(rec, list(system.observed)), "y": dense(rec, list(system.readout)),
            "u": rec["u"], "engine": ENGINE_VERSION}


class SimServer:
    def __init__(self, clean: Path, systems: dict, bundle: Path, store_root: Path, budgets: dict[str, int], default_budget: int = 3000,
                 workers: int = 6):
        self.q = clean / "simq"
        for d in ("requests", "results"):
            (self.q / d).mkdir(parents=True, exist_ok=True)
        self.systems, self.bundle, self.store_root = systems, bundle, store_root
        self.budgets, self.default_budget = budgets, default_budget
        self.ledger_path = store_root / "simservice_ledger.json"
        self.used = json.loads(self.ledger_path.read_text()) if self.ledger_path.exists() else {}
        self.pool = ProcessPoolExecutor(max_workers=workers)

    def _write_result(self, rid: str, arrays: dict, meta: dict) -> None:
        np.savez_compressed(self.q / "results" / f"{rid}.tmp.npz", **arrays)
        os.replace(self.q / "results" / f"{rid}.tmp.npz", self.q / "results" / f"{rid}.npz")
        (self.q / "results" / f"{rid}.tmp.json").write_text(json.dumps(meta), encoding="utf-8")
        os.replace(self.q / "results" / f"{rid}.tmp.json", self.q / "results" / f"{rid}.json")

    def handle(self, path: Path) -> None:
        rid = path.stem
        try:
            req = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            self._write_result(rid, {}, {"status": "error", "error": f"unreadable request: {e}"})
            path.unlink(missing_ok=True)
            return
        agent = str(req.get("agent", "unknown"))
        protos = req.get("protocols") or []
        budget = self.budgets.get(agent, self.default_budget)
        used = self.used.get(agent, 0)
        items, jobs = [], []
        charge = 0          # budget units: a system definition's "cost" per trajectory (real circuits cost more than synthetic ones)
        for j, p in enumerate(protos):
            try:
                sysdef = self.systems.get(str((p or {}).get("system")))
                if sysdef is None:
                    raise P.ProtocolError(f"unknown or non-public system {(p or {}).get('system')!r}")
                if sysdef.get("kind") == "synthetic":
                    from .synthsim import check_public_synth, p3synth
                    p3synth()
                    from p3synth.protocol import validate as synth_validate
                    q = synth_validate(p, n=int(sysdef["n"]), input_dim=int(sysdef["input_dim"]), allow_latent=False)
                    why = check_public_synth(q, sysdef)
                else:
                    q = P.validate(p)
                    why = check_public(q, sysdef)
                if why:
                    raise P.ProtocolError(why)
                cost = int(sysdef.get("cost", 1))
                if used + charge + cost > budget:
                    raise P.ProtocolError(f"simulation budget exhausted ({budget} units; this system costs {cost} per trajectory)")
                charge += cost
                jobs.append((j, self.pool.submit(_worker, (str(self.bundle), sysdef, q, str(self.store_root)))))
                items.append({"i": j, "ok": True, "cost": cost})
            except Exception as e:  # noqa: BLE001
                items.append({"i": j, "ok": False, "error": str(e)})
        arrays = {}
        for j, fut in jobs:
            try:
                r = fut.result()
                for k in ("t", "x", "u", "y"):
                    arrays[f"i{j}_{k}"] = r[k]
                next(it for it in items if it["i"] == j).update(key=r["key"], cached=not r["computed"])
            except Exception as e:  # noqa: BLE001
                next(it for it in items if it["i"] == j).update(ok=False, error=f"simulation failed: {e}")
        n_ok = sum(it.get("cost", 1) for it in items if it["ok"])
        self.used[agent] = used + n_ok
        self.ledger_path.write_text(json.dumps(self.used, indent=1), encoding="utf-8")
        self._write_result(rid, arrays, {"status": "done", "agent": agent, "items": items, "budget": budget, "used": self.used[agent],
                                         "finished": time.strftime("%Y-%m-%dT%H:%M:%S")})
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
    ap.add_argument("--clean", type=Path, required=True)
    ap.add_argument("--systems", type=Path, required=True, help="public system definitions (JSON: system_id -> definition)")
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--store", type=Path, required=True)
    ap.add_argument("--budget", type=int, default=3000)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args(argv)
    systems = json.loads(args.systems.read_text(encoding="utf-8"))
    SimServer(args.clean, systems, args.bundle, args.store, {}, args.budget, args.workers).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
