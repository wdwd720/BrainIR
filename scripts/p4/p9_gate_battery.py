"""Host-gate study battery (ORCHESTRATOR ONLY; fork P9; research/phase4/HOST_GATE_STUDY.md).

    python scripts/p4/p9_gate_battery.py --threads N --sysdefs <json> [--quick]      (inside a Modal container, one fresh process
                                                                                      per pin set: the pins are the process's environment)

Deterministic workloads (fixed seeds) that exercise every numeric path of the official runs, and the sha256 of every output array:
- gen:   the synthetic generator (one system per type of the development tier; construction single-threaded as in the benchmark):
         nominal and kick simulations with the full state, true_state and true_latent_effect;
- real:  the real engine on a mechanism system and (briefly) a full network;
- refs:  reference learner v2 (torch, float64): FULL-STATE and TRUE-STATE fits on the toy system, encodings and rollouts;
- eval:  the evaluator's linear algebra on the toy evaluation data: effects (class-balanced jackknife), mediation (ridge / cross-fitting),
         closure, microstate (whitening, matching, SVD);
- v1:    the frozen earlier method's fit on the toy system, encodings and rollouts.
Prints ONE JSON line: {"libs": dispatch info, "workloads": {name: {"hashes": {array: sha256}, "summ": {array: [sum, abs sum, 8
samples]}, "error": str | None, "s": seconds}}}. The host gate is bypassed IN THIS PROCESS ONLY (the study runs the same code on
non-admissible hosts to compare it); nothing here is an official record.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import sys
import time
import traceback

for p in ("/repo/phase4/tests", "/repo/src", "/repo/phase3/src", "/repo/phase4/src"):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402


def _sha(a) -> str:
    arr = np.ascontiguousarray(np.asarray(a))
    return hashlib.sha256(arr.dtype.str.encode() + repr(arr.shape).encode() + arr.tobytes()).hexdigest()


def _summ(a) -> list:
    arr = np.asarray(a, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        return [0.0, 0.0]
    idx = np.linspace(0, arr.size - 1, num=min(8, arr.size)).astype(int)
    return [float(np.sum(arr)), float(np.sum(np.abs(arr)))] + [float(arr[i]) for i in idx]


def _canon(o):
    """A canonical, bit-exact text of a nested result (floats by their hex form)."""
    if isinstance(o, dict):
        return "{" + ",".join(f"{k!s}:{_canon(o[k])}" for k in sorted(o, key=str)) + "}"
    if isinstance(o, (list, tuple)):
        return "[" + ",".join(_canon(v) for v in o) + "]"
    if isinstance(o, (float, np.floating)):
        return float(o).hex()
    if isinstance(o, (int, np.integer, bool, np.bool_)) or o is None:
        return repr(o if not isinstance(o, np.generic) else o.item())
    if isinstance(o, np.ndarray):
        return "nd:" + _sha(o)
    return repr(str(o))


class Rec:
    def __init__(self):
        self.hashes: dict[str, str] = {}
        self.summ: dict[str, list] = {}

    def arr(self, name: str, a) -> None:
        if a is None:
            return
        self.hashes[name] = _sha(a)
        try:
            self.summ[name] = _summ(a)
        except Exception:  # noqa: BLE001, S110 - non-numeric arrays: hash only
            pass

    def obj(self, name: str, o) -> None:
        self.hashes[name] = hashlib.sha256(_canon(o).encode()).hexdigest()


def _bypass_gate() -> None:
    """The study runs the benchmark's numerics on every host kind; the gate would refuse the non-admissible ones."""
    from brainir_causal.p4modal import gate as G
    G.require_admissible = lambda what: None
    G.admissible = lambda h=None: True


# ------------------------------------------------------------------------------------------------------------ workloads
def w_gen(rec: Rec, quick: bool) -> None:
    from brainir_causal import protocol as P
    from brainir_causal import suites as SU
    from brainir_causal import synthadapter as SA
    SA.register_generator(SU.GENERATOR_CONTAINER, "p4synth")
    systems = SA.suite_systems("dev", SU.DEV_SEED, "default", n_per_type=1)
    sids = sorted(systems)[: (3 if quick else len(systems))]
    for sid in sids:
        s = systems[sid]
        pub = s.public_record()
        dt, t_end = float(pub["dt"]), min(1.0, float(pub.get("t_end_default", 1.0)))
        q0 = P.validate({"system": sid, "params_seed": 3, "t_end": t_end, "dt": dt, "stimulus": [[0.0, 1.0]]})
        r0 = s.simulate(q0, full=True)
        for k in ("x", "y", "z", "state"):
            if k in r0:
                rec.arr(f"{sid}/nominal/{k}", r0[k])
        st = np.asarray(r0["state"])[len(r0["state"]) // 2] if "state" in r0 else None
        cap = (pub.get("capability") or {}).get("kick") or {}
        targets = pub.get("targets") or pub.get("targetable") or pub.get("observed") or [0]
        unit = int(targets[0])
        mag = float(cap.get("moderate", 1.0))
        ev = {"kind": "kick", "t": round(0.3 * t_end, 6), "delta": {str(unit): mag}}
        try:
            q1 = P.validate({"system": sid, "params_seed": 3, "t_end": t_end, "dt": dt, "stimulus": [[0.0, 1.0]], "events": [ev]})
            r1 = s.simulate(q1, full=True)
            for k in ("x", "y", "z"):
                if k in r1:
                    rec.arr(f"{sid}/kick/{k}", r1[k])
        except Exception as exc:  # noqa: BLE001 - recorded (must be identical across hosts too)
            rec.obj(f"{sid}/kick/error", f"{type(exc).__name__}: {exc}"[:200])
        if st is not None:
            for fn, args in (("true_state", (st,)), ("true_latent_effect", (st, {"kind": "kick", "t": 0.0, "delta": {str(unit): mag}}))):
                if hasattr(s, fn):
                    try:
                        rec.arr(f"{sid}/{fn}", getattr(s, fn)(*args))
                    except Exception as exc:  # noqa: BLE001
                        rec.obj(f"{sid}/{fn}/error", f"{type(exc).__name__}: {exc}"[:200])


def w_real(rec: Rec, quick: bool, sysdefs: dict) -> None:
    from brainir_causal import protocol as P
    from brainir_causal.realsim import RealEngine, RealSystem
    from brainir_causal.systems import BUNDLE
    engines: dict = {}
    for sid, d in sorted(sysdefs.items()):
        full = d.get("mode") == "full"
        if quick and full:
            continue
        net = d["network"]
        if net not in engines:
            engines[net] = RealEngine(BUNDLE, net)
        t_end = 0.05 if full else 0.5
        base = {"system": sid, "params_seed": 3, "t_end": t_end, "dt": 0.001, "stimulus": [[0.0, 0.0], [0.02, 1.0]]}
        runs = [("nominal", base)]
        if not full:
            runs.append(("kick", dict(base, events=[{"kind": "kick", "t": 0.1, "delta": {str(d["targets_public"][0]): 20.0}}])))
        for tag, p in runs:
            r = engines[net].run(RealSystem.from_record(d), P.validate(p))
            for k in ("t", "x", "y", "state", "rates"):
                if k in r and r[k] is not None and not isinstance(r[k], dict):
                    rec.arr(f"{sid}/{tag}/{k}", r[k])


def w_refs(rec: Rec, quick: bool, threads: int) -> None:
    import test_lift_toysys as TL
    import torch
    from brainir_causal import refs as R
    torch.set_num_threads(threads)
    s = TL.ToyLinear()
    train, truth = TL.make_records(s, n_passive=6, n_kick=8, n_pulse=4, seed=0)
    test, _ = TL.make_records(s, n_passive=2, n_kick=2, n_pulse=0, seed=1, full=False)
    cfg = R.LearnerConfig(steps_one=150 if quick else 300, steps_multi=20 if quick else 40, readout_steps=150 if quick else 300)
    for name in ("full_state", "true_state"):
        m = R.fit_reference(name, "toy", train, s.record(), truth=truth, cfg=cfg)
        for i, r in enumerate(test[:4]):
            n = len(r["x"]) // 2
            z = m.encode("toy", r["x"][: n + 1], r["u"][: n + 1], float(r["protocol"]["dt"]))
            rec.arr(f"{name}/z{i}", z)
            ro = m.rollout("toy", z, r["u"][n: n + 50], [], float(r["protocol"]["dt"]))
            rec.arr(f"{name}/rollout{i}/y", ro["y"])


def w_eval(rec: Rec, quick: bool) -> None:
    import test_eval_core as TE
    from brainir_causal.evaluate import eval_effects, predict_items
    from brainir_causal.evaluate_mediation import eval_closure, eval_mediation
    from brainir_causal.evaluate_micro import eval_microstate, latent_whitener
    sysc, items = TE.make_data(n_traj=12 if quick else 24, seed=0)
    for mname, model in (("exact", TE.ExactModel()), ("missing", TE.MissingModel())):
        preds = predict_items(model, sysc, items)
        rec.obj(f"{mname}/effects", eval_effects(sysc, items, preds, n_boot=100))
        rec.obj(f"{mname}/mediation", eval_mediation(sysc, items, preds, n_boot=100, n_seeds=2))
        rec.obj(f"{mname}/closure", eval_closure(model, sysc, items, preds, n_boot=100, n_seeds=2))
    pool = TE.make_pool(n_traj=8 if quick else 12, per=3)
    hists = [(it.x_hist, it.u_hist, it.dt) for it in items if it.is_passive]          # as test_eval_core.test_microstate_equivalence
    for mname, model in (("exact", TE.ExactModel()), ("missing", TE.MissingModel())):
        wz = latent_whitener(model, TE.SID, hists)
        rec.obj(f"{mname}/microstate", eval_microstate(model, sysc, pool, whiten_z=wz, n_boot=100))


def w_v1(rec: Rec, quick: bool) -> None:
    import test_lift_toysys as TL
    from brainir_causal.data import Trajectory
    from brainir_causal.frozen_v1 import FrozenV1Baseline
    s = TL.ToyLinear()
    train, _ = TL.make_records(s, n_passive=6, n_kick=6 if quick else 10, n_pulse=2 if quick else 4, seed=0, full=False)
    trajs = [Trajectory(key=r["key"], system_id="toy", split=r["split"], family=r["family"] or "obs.nominal", protocol=r["protocol"],
                        t=np.asarray(r["t"]), x=np.asarray(r["x"]), u=np.asarray(r["u"]), y=np.asarray(r["y"]), meta=r.get("meta") or {})
             for r in train]
    m = FrozenV1Baseline().fit(trajs, systems={"toy": s.record()}, config={}, seed=0)
    test, _ = TL.make_records(s, n_passive=2, n_kick=2, n_pulse=0, seed=1, full=False)
    for i, r in enumerate(test[:4]):
        n = len(r["x"]) // 2
        z = m.encode("toy", r["x"][: n + 1], r["u"][: n + 1], float(r["protocol"]["dt"]))
        rec.arr(f"z{i}", z)
        ro = m.rollout("toy", z, r["u"][n: n + 50], [], float(r["protocol"]["dt"]))
        rec.arr(f"rollout{i}/y", ro["y"])


def libs_info() -> dict:
    out: dict = {"env": {k: os.environ.get(k) for k in ("NPY_DISABLE_CPU_FEATURES", "ATEN_CPU_CAPABILITY", "OPENBLAS_CORETYPE",
                                                         "MKL_ENABLE_INSTRUCTIONS", "MKL_CBWR", "ONEDNN_MAX_CPU_ISA", "OMP_NUM_THREADS",
                                                         "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}}
    try:
        import threadpoolctl
        out["blas"] = [{k: d.get(k) for k in ("internal_api", "version", "architecture", "threading_layer", "num_threads")}
                       | {"lib": os.path.basename(d.get("filepath") or "")} for d in threadpoolctl.threadpool_info()]
    except Exception as exc:  # noqa: BLE001
        out["blas"] = f"unavailable: {exc}"
    try:
        from numpy._core._multiarray_umath import __cpu_features__ as cf
        out["numpy_features_on"] = sorted(k for k, v in cf.items() if v)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            np.show_runtime()
        out["numpy_runtime"] = buf.getvalue()[:3000]
    except Exception as exc:  # noqa: BLE001
        out["numpy_runtime"] = f"unavailable: {exc}"
    try:
        import torch
        out["torch"] = {"version": torch.__version__, "cpu_capability": torch.backends.cpu.get_cpu_capability(),
                        "mkl": bool(torch.backends.mkl.is_available()), "mkldnn": bool(torch.backends.mkldnn.is_available()),
                        "threads": torch.get_num_threads()}
    except Exception as exc:  # noqa: BLE001
        out["torch"] = f"unavailable: {exc}"
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--sysdefs", default="")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args(argv)
    _bypass_gate()
    sysdefs = json.loads(open(args.sysdefs, encoding="utf-8").read()) if args.sysdefs else {}
    want = [w for w in args.only.split(",") if w] or ["gen", "real", "refs", "eval", "v1"]
    try:
        import scipy.linalg  # noqa: F401 - load scipy's OpenBLAS too, so the dispatch record lists both libraries
        import torch
        torch.set_num_threads(args.threads)                  # every workload at the job's thread count
    except Exception:  # noqa: BLE001, S110
        pass
    out = {"libs": libs_info(), "threads": args.threads, "workloads": {}}
    for name in want:
        rec, t0, err = Rec(), time.time(), None
        try:
            if name == "gen":
                w_gen(rec, args.quick)
            elif name == "real":
                w_real(rec, args.quick, sysdefs)
            elif name == "refs":
                w_refs(rec, args.quick, args.threads)
            elif name == "eval":
                w_eval(rec, args.quick)
            elif name == "v1":
                w_v1(rec, args.quick)
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"[:500] + " | " + traceback.format_exc()[-800:]
        out["workloads"][name] = {"hashes": rec.hashes, "summ": rec.summ, "error": err, "s": round(time.time() - t0, 2)}
    out["libs_after"] = libs_info()                        # dispatch after every workload loaded its libraries
    out["libs_after"].pop("numpy_runtime", None)
    print("P9RESULT " + json.dumps(out), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
