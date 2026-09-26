"""Evaluator-side latent-intervention lifting for the LOCKED brainir_state_v1 (goal4 sections 13-14; acceptance criterion 26).
ORCHESTRATOR SIDE; the output is ANSWER-BEARING (FINAL suite).

The locked method has no `lift()`, so the pre-registered lifting test (PROTOCOL.md section 4, "scored where a model implements
lift()") could not test its latent interventions. goal4 section 13 defines lifting through the ENCODER: find a low-level intervention
delta_x with phi(x + delta_x) ~ z + delta_z at minimum cost, then compare the latent model's prediction after do(z := z + delta_z)
with the simulator after the lifted intervention. `EncoderLift` builds that lift from the model's own public `encode()`, without
changing the model: nothing of v1 is edited, refitted or re-selected, and every other method call is delegated unchanged.

The lift, fixed before any result (logged START row in research/phase3/HIDDEN_EVALUATIONS.md):
- J = d phi / d x_t, the encoder's sensitivity to the CURRENT observed microstate, by central finite differences through encode() on
  a constant history of the current sample (v1's encoder is linear in its features, so J is exact; the script checks linearity);
- intervention class: instantaneous kicks at the requested time on the observed public intervention targets, as the baselines' lifts;
- candidates: minimum-norm kicks J[:, cols]^+ delta_z for the baselines' rule (lin_core.lift): all targets; the max(k, min(n, 3k))
  targets with the largest Jacobian column norms; a random half of the targets (seed 0) when n > 2k.
Evaluation: the frozen `evaluate_lift.eval_lifting` with the cases, shift size, number of lifts, seed and fresh-copy rollouts of the
FINAL confirmation's own lifting evaluation (`suite_eval.evaluate_model_job`), on the stored seed-0 FINAL fits (46 compressible
systems). Post hoc and descriptive: not pre-registered, no selection or tuning, v1 itself still has no lift().

    uv run --project phase3 --no-sync python scripts/p3/lift_v1_encoder.py [--workers 3] [--systems ...]
        -> research/phase3/tournament/final_b_lift_v1/LIFT_V1.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p3"))
sys.path.insert(0, str(ROOT / "phase3" / "src"))

P3 = ROOT / "research" / "phase3"
RUN = Path(r"C:\Dev\BrainIR_p3run")
PART = RUN / "final_b_brainir_state_v1"
OUT = P3 / "tournament" / "final_b_lift_v1" / "LIFT_V1.json"
HIST = 64                 # length of the constant history used to differentiate the encoder at the current sample


class EncoderLift:
    """A fitted state model, unchanged, plus a lift() computed from its own encoder (goal4 section 13)."""

    def __init__(self, model, targets: dict, dt: dict, n_u: dict):
        self._m = model
        self._targets = targets        # sid -> [(column in x, neuron id)] of the observed public targets
        self._dt = dt
        self._n_u = n_u

    def __getattr__(self, name):
        m = self.__dict__.get("_m")                   # during unpickling _m does not exist yet: no recursion through __getattr__
        if m is None or name.startswith("__"):
            raise AttributeError(name)
        return getattr(m, name)

    def encode(self, sid, x_hist, u_hist, dt):
        return self._m.encode(sid, x_hist, u_hist, dt)

    def rollout(self, sid, z0, u_future, events, dt):
        return self._m.rollout(sid, z0, u_future, events, dt)

    def readout(self, sid, z, u):
        return self._m.readout(sid, z, u)

    def supports(self, sid, kind):
        return self._m.supports(sid, kind)

    def info(self):
        return self._m.info()

    def jacobian(self, sid, x):
        """J (k, n_obs) = d phi / d x_t at a constant history of x (central differences)."""
        x = np.asarray(x, float)
        u = np.zeros((HIST, self._n_u[sid]))
        H = np.tile(x, (HIST, 1))
        eps = 1e-3 * (1.0 + np.abs(x))
        cols = []
        for j in range(len(x)):
            Hp, Hm = H.copy(), H.copy()
            Hp[-1, j] += eps[j]
            Hm[-1, j] -= eps[j]
            zp = np.asarray(self._m.encode(sid, Hp, u, self._dt[sid]), float)
            zm = np.asarray(self._m.encode(sid, Hm, u, self._dt[sid]), float)
            cols.append((zp - zm) / (2 * eps[j]))
        return np.stack(cols, axis=1)

    def lift(self, sid, x, z, delta_z, n_candidates=3):
        J = self.jacobian(sid, x)
        tg = self._targets[sid]
        cols_all = np.array([c for c, _ in tg])
        ids = {c: n for c, n in tg}
        k = len(np.atleast_1d(z))
        rng = np.random.default_rng(0)
        cands = [cols_all]
        norms = np.linalg.norm(J[:, cols_all], axis=0)
        m = max(k, min(len(cols_all), 3 * k))
        cands.append(cols_all[np.argsort(norms)[::-1][:m]])
        if len(cols_all) > 2 * k:
            cands.append(np.sort(rng.choice(cols_all, size=max(k, len(cols_all) // 2), replace=False)))
        out = []
        for cols in cands[:n_candidates]:
            dx = np.linalg.lstsq(J[:, cols], np.asarray(delta_z, float), rcond=None)[0]
            out.append([{"kind": "kick", "t": 0.0, "delta": {str(ids[c]): float(v) for c, v in zip(cols, dx) if abs(v) > 1e-12}}])
        return out


def _one(sid: str) -> dict:
    import tournament as T
    from brainir_state import evaluate as E
    from brainir_state.evaluate_lift import eval_lifting
    from brainir_state.harness import pca_basis  # noqa: F401  (imported by the frozen job as well)
    from brainir_state.runguard import install_eval_guard
    from brainir_state.runner import load_model
    from brainir_state.suite_eval import _simulator, limit_threads, suite_from_spec
    limit_threads(2)
    t0 = time.time()
    spec = T.suite_spec("final")
    sd = suite_from_spec(spec)
    mdir = PART / "methods"
    path = PART / "brainir_state_v1" / "indep" / f"{sid}_s0.pkl"
    # the method package may read its own source files (imports of sibling modules); everything else stays refused
    install_eval_guard([str(mdir.resolve())], allowed=[str(path.resolve().parent), str(mdir.resolve())])
    try:
        model = load_model(str(mdir), str(path))
        info = sd.sysinfo(sid)
        obs = [int(n) for n in info["observed"]]
        col = {n: i for i, n in enumerate(obs)}
        tg = [(col[int(n)], int(n)) for n in info.get("targets_public", []) if int(n) in col] or [(i, n) for i, n in enumerate(obs)]
        hs = sd.hidden(sid)
        roles = sd.roles_for(sid)
        test_trajs = [t for fam in roles["non_intervention"] for t in hs["by_family"].get(fam, [])]
        dt = float(test_trajs[0].protocol["dt"])
        wrapped = EncoderLift(model, {sid: tg}, {sid: dt}, {sid: int(info.get("input_dim") or 1)})
        roll = E.Fresh(wrapped)                          # fresh copies before any encode call, as in the frozen evaluation job
        # linearity check of the encoder at the current sample (two base points)
        x0 = np.asarray(test_trajs[0].x[len(test_trajs[0].x) // 2], float)
        J0 = wrapped.jacobian(sid, x0)
        J1 = wrapped.jacobian(sid, x0 + 0.1 * np.random.default_rng(1).standard_normal(len(x0)))
        lin = float(np.max(np.abs(J0 - J1)) / (np.max(np.abs(J0)) + 1e-12))
        cases = []
        for t in test_trajs[:6]:
            for ts in sd.cfg.start_times_s[1:3]:
                cases.append({"protocol": dict(t.protocol, events=[]), "t": ts})
        res = eval_lifting(wrapped, sid, cases, _simulator(spec, sid), sd.scale(sid), sd.cfg, future_s=sd.cfg.micro_future_s, roll=roll)
        return {"sid": sid, "lift": res, "encoder_linearity_rel_diff": lin, "n_targets": len(tg), "k": int(J0.shape[0]),
                "wall_s": round(time.time() - t0, 1)}
    except Exception as e:  # noqa: BLE001
        import traceback
        return {"sid": sid, "error": repr(e), "traceback": traceback.format_exc()[-3000:], "wall_s": round(time.time() - t0, 1)}


def _summary(rows: dict) -> dict:
    def mean_of(x, key):
        v = x.get(key)
        return float(v["mean"]) if isinstance(v, dict) and v.get("mean") is not None and np.isfinite(v["mean"]) else None

    def inv(x):
        ii = x.get("implementation_invariance")
        if isinstance(ii, dict):
            return float(ii["ratio"]) if ii.get("testable", True) and ii.get("ratio") is not None and np.isfinite(ii["ratio"]) else None
        return None
    L = [r["lift"] for r in rows.values() if isinstance(r.get("lift"), dict) and r["lift"].get("supported", True) and r["lift"].get("n_lifted")]
    ach = [v for v in (mean_of(x, "achieved_shift_rel_error") for x in L) if v is not None]
    aft = [v for v in (mean_of(x, "model_nmse_after_lift") for x in L) if v is not None]
    twn = [v for v in (mean_of(x, "model_nmse_twin") for x in L) if v is not None]
    ivs = [v for v in (inv(x) for x in L) if v is not None]
    return {"systems_lifted": len(L), "achieved_shift_rel_error_median": float(np.median(ach)) if ach else None,
            "nmse_after_lift_median": float(np.median(aft)) if aft else None, "nmse_twin_median": float(np.median(twn)) if twn else None,
            "invariance_ratio_median": float(np.median(ivs)) if ivs else None, "invariance_n_testable_finite": len(ivs),
            "invariance_frac_below_1": float(np.mean(np.array(ivs) < 1)) if ivs else None,
            "encoder_linearity_max_rel_diff": max((r.get("encoder_linearity_rel_diff") or 0.0) for r in rows.values()),
            "n_errors": sum(1 for r in rows.values() if "error" in r)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--systems", nargs="*", default=None)
    a = ap.parse_args(argv)
    ag = json.loads((P3 / "tournament" / "final_b" / "AGGREGATE_developer_facing.json").read_text(encoding="utf-8"))
    sids = a.systems or list(ag["design"]["compressible"])
    t0 = time.time()
    rows = {}
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for r in ex.map(_one, sids):
            rows[r["sid"]] = r
            print(r["sid"], "error" if "error" in r else "ok", r.get("wall_s"), flush=True)
    rec = {"script": "scripts/p3/lift_v1_encoder.py", "answer_bearing": True, "suite": "final", "model": "brainir_state_v1 (locked, unchanged)",
           "note": "post-hoc, descriptive evaluator-side lift through v1's encoder (goal4 section 13); not pre-registered; v1 has no lift()",
           "wall_s": round(time.time() - t0, 1), "summary": _summary(rows), "per_system": rows,
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if not a.systems:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rec["summary"]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
