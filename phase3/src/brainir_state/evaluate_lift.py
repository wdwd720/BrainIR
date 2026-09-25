"""Latent-intervention lifting (goal4 sections 13-14; PROTOCOL.md section 4 "latent-intervention lifting").

For a state model with `lift()`: at a sampled time t_i of a held-out trajectory (protocol P), request a latent shift delta_z; the
model proposes up to 3 DISTINCT microscopic interventions (kicks / currents at t_i). The evaluator applies each in the simulator
(P plus the lifted events, continued for the future horizon), and also runs the counterfactual twin (P without them). It measures

- achieved shift: z_after(lift) - z_after(twin), re-encoded from the SIMULATED microstate, against the requested delta_z
  (relative error ||achieved - delta_z|| / ||delta_z||), measured when the lift has finished acting (1 sample after a kick, at the end
  of a current pulse);
- latent-model fidelity after do(z := z + delta_z): the model's rollout from z + delta_z vs the simulator's readout after the lift
  (NMSE over the future window), next to the model's rollout from the unshifted z vs the twin;
- implementation invariance (goal4 section 14): divergence of the simulated futures across distinct lifts of the SAME delta_z, against
  the divergence across lifts of DIFFERENT delta_z of the same norm (ratio small = the future depends on the abstract state, not the
  microscopic realisation);
- for synthetic systems with truth: the TRUE latent shift produced by each lift (spread across lifts of one delta_z).

Version 3 (pre-lock review B, M4 and m3):
- Shift semantics. A lift requested at t_i for delta_z asks for a COUNTERFACTUAL latent shift. Once every lifted event has acted
  (sample j, `_lift_done_index`), the lifted world's latent should equal the twin's latent AT THE SAME SAMPLE plus delta_z:
  z_lift(j) = z_twin(j) + delta_z. For a kick, j = i + 1, so the shift is effectively immediate. A current pulse acts over
  [t_i, t1), and the shift is judged at its end. The do() test starts the model's rollout at that same sample j from
  z_twin(j) + delta_z. The requested shift and the tested do() therefore refer to one time, j. Version 2 already measured at j,
  and version 3 states this as the definition.
- Distinct lifts. Candidate lifts whose event sets are identical are dropped before simulation. A lift whose ACHIEVED microstate
  change (x_lift(j) - x_twin(j), observed neurons) has cosine similarity above `cos_max` (0.99) with an earlier distinct lift of the
  same requested shift still counts in the shift and fidelity statistics, but not in the implementation-invariance ratio or the
  true-shift spread. Two no-op lifts (zero change) are identical. Without a same-shift pair of distinct lifts, and without distinct
  lifts of both shifts of a case, the ratio is "untestable" (a reason is recorded), never a perfect score.
- Common window. The futures entering the invariance ratio are compared over ONE window per case, starting at the latest completion
  sample among the case's distinct lifts. Lifts that finish at different times are therefore compared at the same absolute times.
- The per-coordinate spread zsd that scales delta_z is estimated from the encodings of ALL cases (version 2 used the first case only).
- For k = 1 the second requested shift is the opposite of the first. Two random directions in one dimension coincide half the time,
  and the "different shift" would then equal the first.
- Rollouts run on fresh copies of the model (`roll`, as in the other families), so nothing encode() stores in the model object can
  reach a prediction.
- A model that does not override `StateModel.lift` is reported as unsupported without any simulation (`lift_supported`).

`simulate(protocol) -> {"t","x","u","y", optional "z"}` is supplied by the orchestrator (the synthetic generator or the real engine).
"""

from __future__ import annotations

import copy
import json
import pickle

import numpy as np

from .api import StateModel
from .evaluate import EvalConfig, _nmse, boot_mean

LIFT_KINDS = ("kick", "current")
COS_MAX = 0.99            # achieved microstate changes more similar than this are one realisation (version 3)


def lift_supported(model) -> bool:
    """True when the model's class overrides StateModel.lift (the default returns [] for every request)."""
    meth = getattr(type(model), "lift", None)
    return meth is not None and meth is not StateModel.lift


class _FreshRoller:
    """Rollouts on fresh copies of a snapshot taken when the evaluation starts (version 3; pre-lock reviews A B1 and B M1): unpickled
    from bytes, or deep-copied when the model cannot be pickled (every StateModel is saved by pickle, so that is a fallback); the
    model itself only when neither works. `mode` records which."""

    def __init__(self, model):
        self._blob = self._snap = self._model = None
        try:
            self._blob, self.mode = pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL), "pickle"
        except Exception:  # noqa: BLE001
            try:
                self._snap, self.mode = copy.deepcopy(model), "deepcopy"
            except Exception:  # noqa: BLE001
                self._model, self.mode = model, "none"

    def rollout(self, *args, **kwargs):
        if self._blob is not None:
            m = pickle.loads(self._blob)
        elif self._snap is not None:
            m = copy.deepcopy(self._snap)
        else:
            m = self._model
        return m.rollout(*args, **kwargs)


def _lift_done_index(events: list[dict], dt: float) -> int:
    """The first sample at which every lifted event has fully acted: a kick at t acts between samples idx(t) and idx(t) + 1; a
    current on [t0, t1) has acted fully in sample idx(t1) (version 2, review H m2)."""
    js = []
    for e in events:
        if e["kind"] == "kick":
            js.append(int(round(e["t"] / dt)) + 1)
        else:
            js.append(int(round(float(e.get("t1", e.get("t0", 0.0))) / dt)))
    return max(js) if js else 0


def _shift_to(events: list[dict], t0: float) -> list[dict]:
    out = []
    for e in events:
        e2 = dict(e)
        if "t" in e2:
            e2["t"] = round(e2["t"] + t0, 6)
        if "t0" in e2:
            e2["t0"] = round(e2["t0"] + t0, 6)
        if e2.get("t1") is not None:
            e2["t1"] = round(e2["t1"] + t0, 6)
        out.append(e2)
    return out


def _canonical(events: list[dict]) -> str:
    """Order-free canonical form of an event set (identical sets give identical strings)."""
    return json.dumps(sorted(json.dumps(e, sort_keys=True, default=str) for e in events))


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two achieved microstate changes; two zero changes (no-op lifts) are identical, one zero change is
    unrelated to any other."""
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na <= 1e-12 and nb <= 1e-12:
        return 1.0
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return float(a @ b / (na * nb))


def eval_lifting(model: StateModel, sid: str, cases: list[dict], simulate, scale: np.ndarray, cfg: EvalConfig = EvalConfig(),
                 future_s: float = 0.25, shift_sd: float = 0.5, n_lifts: int = 3, seed: int = 0, roll=None,
                 cos_max: float = COS_MAX) -> dict:
    """cases: [{"protocol": P (a held-out protocol without events), "t": t_i}]. The evaluator draws delta_z = shift_sd x sd(z) along
    two random directions per case (two different shifts of equal norm, for the invariance ratio). `roll`: any object with the
    StateModel rollout signature that runs on fresh model copies (the evaluation's own, when it has one); by default a snapshot of the
    model taken here."""
    if not lift_supported(model):
        return {"n_requested": 0, "n_lifted": 0, "supported": False, "reason": "lift() is not implemented (the StateModel default)"}
    roll = roll if roll is not None else _FreshRoller(model)
    rng = np.random.default_rng(seed)
    # pass 1: the base runs and the encodings; zsd from the encodings of every case
    prepared, zs = [], []
    for c in cases:
        P, ti = c["protocol"], float(c["t"])
        dt = float(P["dt"])
        base = simulate(dict(P))
        i = int(round(ti / dt))
        z_now = np.asarray(model.encode(sid, base["x"][: i + 1], base["u"][: i + 1], dt), float)
        zs += [np.asarray(model.encode(sid, base["x"][: j + 1], base["u"][: j + 1], dt), float)
               for j in range(max(1, i // 2), i + 1, max(1, i // 20))]
        prepared.append((P, ti, dt, base, i, z_now))
    counts = {"n_candidates": 0, "n_invalid_kind": 0, "n_duplicate_events": 0, "n_too_late": 0, "n_near_identical": 0, "n_distinct": 0}
    if not prepared:
        return {"n_requested": 0, "n_lifted": 0, "supported": False, "reason": "no lifting cases", **counts}
    zsd = np.stack(zs).std(0) + 1e-9
    ach, fid_lift, fid_twin, same_div, diff_div, true_spread = [], [], [], [], [], []
    n_req = n_ok = 0
    for P, ti, dt, base, i, z_now in prepared:
        # one common t_end (the protocol's own) for the base run, every lift and every twin: noise realisations of the synthetic
        # simulator depend on t_end, so all runs of a case must share it (version 2, review H M6)
        n_total = int(round(float(P["t_end"]) / dt))
        n_f = int(round(future_s / dt))
        twin = base                                   # P without the lifted events, same t_end: the counterfactual twin
        dirs = rng.standard_normal((2, len(z_now)))
        dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
        if len(z_now) == 1:
            dirs[1] = -dirs[0]        # k = 1: two random signs coincide half the time; the other shift of equal norm is the opposite
        per_shift = []
        for d in dirs:
            dz = shift_sd * zsd * d
            n_req += 1
            raw = list(model.lift(sid, base["x"][i], z_now, dz, n_candidates=n_lifts) or [])[:n_lifts]
            counts["n_candidates"] += len(raw)
            valid = [lf for lf in raw if lf and all(e.get("kind") in LIFT_KINDS for e in lf)]
            counts["n_invalid_kind"] += len(raw) - len(valid)
            if valid:
                n_ok += 1
            seen, recs, true_d = set(), [], []
            for lf in valid:
                key = _canonical(lf)
                if key in seen:
                    counts["n_duplicate_events"] += 1
                    continue
                seen.add(key)
                ev = _shift_to(lf, ti)
                j = _lift_done_index(ev, dt)
                if j + n_f > n_total:
                    counts["n_too_late"] += 1         # the lift ends too late for a full future window inside the protocol
                    continue
                sim = simulate(dict(P, events=list(P.get("events") or []) + ev))
                dx = np.asarray(sim["x"][j], float) - np.asarray(twin["x"][j], float)
                distinct = all(_cos(dx, r["dx"]) <= cos_max for r in recs if r["distinct"])
                counts["n_distinct" if distinct else "n_near_identical"] += 1
                z_l = np.asarray(model.encode(sid, sim["x"][: j + 1], sim["u"][: j + 1], dt), float)
                z_t = np.asarray(model.encode(sid, twin["x"][: j + 1], twin["u"][: j + 1], dt), float)
                ach.append(float(np.linalg.norm((z_l - z_t) - dz) / (np.linalg.norm(dz) + 1e-12)))
                u_f = sim["u"][j: j + n_f + 1]
                y_model_l = np.asarray(roll.rollout(sid, z_t + dz, u_f, [], dt)["y"], float)[1:]
                y_model_t = np.asarray(roll.rollout(sid, z_t, u_f, [], dt)["y"], float)[1:]
                fid_lift.append(_nmse(y_model_l, sim["y"][j + 1: j + n_f + 1], scale))
                fid_twin.append(_nmse(y_model_t, twin["y"][j + 1: j + n_f + 1], scale))
                recs.append({"sim": sim, "j": j, "dx": dx, "distinct": distinct})
                if distinct and "z" in sim and "z" in twin:
                    true_d.append(np.asarray(sim["z"][j], float) - np.asarray(twin["z"][j], float))
            if len(true_d) >= 2:
                # relative spread of the TRUE latent shift across distinct lifts of one requested shift
                pair = [np.linalg.norm(true_d[a] - true_d[b]) for a in range(len(true_d)) for b in range(a + 1, len(true_d))]
                true_spread.append(float(np.mean(pair) / (np.mean([np.linalg.norm(v) for v in true_d]) + 1e-12)))
            per_shift.append([r for r in recs if r["distinct"]])
        distinct_all = [r for rs in per_shift for r in rs]
        if not distinct_all:
            continue
        # futures over ONE window per case, after every distinct lift of the case has acted (common absolute times)
        J = max(r["j"] for r in distinct_all)
        fut = [[np.asarray(r["sim"]["y"][J + 1: J + n_f + 1], float) for r in rs] for rs in per_shift]
        for fs in fut:
            for a in range(len(fs)):
                for b in range(a + 1, len(fs)):
                    same_div.append(_nmse(fs[a], fs[b], scale))
        if len(fut) == 2 and fut[0] and fut[1]:
            for fa in fut[0]:
                for fb in fut[1]:
                    diff_div.append(_nmse(fa, fb, scale))
    res = {"n_requested": n_req, "n_lifted": n_ok, "supported": n_ok > 0, **counts,
           "rollout_isolation": getattr(roll, "mode", "caller")}
    if not n_ok:
        res["reason"] = "lift() returned no usable candidate (kinds 'kick' / 'current') for any request"
    if not ach:
        res["implementation_invariance"] = {"testable": False, "reason": "no lift could be simulated"}
        return res
    res["achieved_shift_rel_error"] = dict(zip(("mean", "ci95"), boot_mean(np.array(ach), cfg.n_boot, cfg.seed)))
    res["model_nmse_after_lift"] = dict(zip(("mean", "ci95"), boot_mean(np.array(fid_lift), cfg.n_boot, cfg.seed)))
    res["model_nmse_twin"] = dict(zip(("mean", "ci95"), boot_mean(np.array(fid_twin), cfg.n_boot, cfg.seed)))
    if same_div and diff_div:
        ratio = float(np.mean(same_div) / max(np.mean(diff_div), 1e-12))
        res["future_div_same_shift"] = float(np.mean(same_div))
        res["future_div_different_shift"] = float(np.mean(diff_div))
        res["implementation_invariance_ratio"] = ratio
        res["implementation_invariance"] = {"testable": True, "ratio": ratio, "n_same_shift_pairs": len(same_div),
                                            "n_different_shift_pairs": len(diff_div)}
    else:
        reason = ("fewer than two distinct lifts of any requested shift" if not same_div
                  else "no case with distinct lifts of both requested shifts")
        res["implementation_invariance"] = {"testable": False, "reason": reason, "n_same_shift_pairs": len(same_div),
                                            "n_different_shift_pairs": len(diff_div)}
    if true_spread:
        res["true_latent_shift_spread_rel"] = float(np.mean(true_spread))
    return res
