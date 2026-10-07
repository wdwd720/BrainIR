"""Level C container-side functions (TRUSTED orchestrator code; benchmarks/causal_state_v1/PROTOCOL.md sections 5.11, 5.13, 5.14 and 9).

These run as the root DRIVER of an ISOLATED container through the iso role "call" of `brainir_causal.isolation.run_iso_payload`
(target "levelc_remote:<function>", resolved from the hash-locked script directory baked into the iso image,
`isolation.ISO_SCRIPT_DIRS`). Every function has the signature fn(job, *, transport, models): `transport` = the job's worker transport
(its own uids; a packed slot's uid block), `models` = {name: fitted model BYTES}. Method models are only ever called through
`isolation.RemoteFresh` (fresh model workers, the safe codec, the phase discipline and the history-digest rule); the driver never
unpickles a model and never gives a worker anything but a call's arguments. Models above Modal's inline limit arrive as STAGED refs
(`resolve_models`: `isolation.read_staged`, hash-verified); the only volume write is `fit_records` staging an oversized output model
(`isolation.stage_blob`, content-addressed, under a root no worker can read).

    stability(job)     5.11 representation stability over the seeds and bootstrap refits of one system (`evaluate_stability`;
                       one model's workers at a time, recorded, the frozen metrics on replays: see the note at the function)
    stability_diag(job) DRY-RUN diagnostic of the 5.11 job (restart cost, shared-uid kills, per-model / per-call timings)
    same_items(job)    PROTOCOL 9: the calibration row of one compressible synthetic system (references fitted on the same data) with
                       the METHOD scored as an extra model on the verdict items the TRUE-STATE reference supports
                       (`calibrate.calibrate_from_inputs(extra_models=...)`): P_t and P_m - P_t on one item set
    fit_records(job)   a fit on FILTERED training records: 5.13 leave-one-intervention-out (`evaluate_transfer.loio_datasets`) or the
                       5.14 subsample of a held-out implementation (`evaluate_transfer.limpo_subsample`), optionally adapted from a shared
                       model (config adapt_from); returns the model bytes and the side record like `isolation.fit_job`
    eval_items(job)    EE units {item: (num, den)} (primary horizon) of one or more models on an ITEM SUBSET of one system (5.13 family
                       items, 5.14 held-out-family items), optionally with the state-mediation score on the same items
    trap_probe(job)    DRY RUN ONLY (`level_c.py trap-probe`, a DUMMY catalog): the trap catalog as this image holds it (path, sha256,
                       root-only, unreadable by a worker uid) and its systems built through `synthadapter.suite_systems("trap", seed)`
                       for a PUBLIC seed

The functions are imported only inside the container (the orchestrator imports this module for its `FUNCTIONS` names and the
tests); they import brainir_causal lazily.
"""

from __future__ import annotations

import inspect
import time
from pathlib import Path

FUNCTIONS = ("stability", "same_items", "fit_records", "eval_items", "trap_probe", "stability_diag")
CALL_TIMEOUT_S = 900.0


# ================================================================================================================ helpers
def _records_with_twins(es, pred) -> list:
    """The records of a lazy experiment set whose row satisfies `pred`, followed by the twins of those records."""
    rows = [r for r in es.rows if pred(r)]
    keys = {r["key"] for r in rows}
    twins = [r for r in es.rows if r.get("split") == "twin" and (r.get("meta") or {}).get("twin_of") in keys]
    return [es.load(r) for r in rows + twins]


def _role(row: dict) -> str:
    return str((row.get("meta") or {}).get("role") or "").split(":", 1)[0]


def resolve_models(models: dict) -> dict:
    """{name: bytes}: a model given as a STAGED ref ({"stage": sha256, "size", "vol"}: above Modal's inline limit on a block_network
    container) is read by this driver from its volume and hash-verified (`isolation.read_staged`); workers never see the volume."""
    from brainir_causal.isolation import read_staged
    return {k: (read_staged(v) if isinstance(v, dict) and "stage" in v else v) for k, v in (models or {}).items()}


def _remote(blob: bytes, transport, job: dict):
    from brainir_causal.isolation import RemoteFresh
    return RemoteFresh(blob, transport, threads=int(job.get("threads", 2)), call_timeout_s=float(job.get("call_timeout_s", CALL_TIMEOUT_S)))


def _iso_summary(rec: dict | None) -> dict:
    rec = rec or {}
    return {"worker_restarts": rec.get("worker_restarts"), "model_class": rec.get("model_class"), "model_bytes": rec.get("model_bytes"),
            "phases": {s: {k: v for k, v in (r or {}).items() if k in ("n_calls", "load_s", "restarts", "closed_s")}
                       for s, r in (rec.get("phases") or {}).items()}}


def _est(e) -> dict | None:
    if e is None:
        return None
    return {"point": float(e.point), "ci95": [float(x) for x in e.ci95], "n_cells": int(e.n_units or 0)}


def units_primary(eff: dict) -> tuple[dict, dict]:
    """({item: (num, den)} at the primary horizon, {item: family}) from `evaluate.eval_effects(...)["_units"]` (the item-level inputs
    of `evaluate_transfer`)."""
    from brainir_causal.evalio import PRIMARY
    u = eff["_units"]
    units = {str(it): (float(u[f"num_{PRIMARY}"][j]), float(u[f"den_{PRIMARY}"][j])) for j, it in enumerate(u["item"])}
    fams = {str(it): str(u["family"][j]) for j, it in enumerate(u["item"])}
    return units, fams


# ================================================================================================================ 5.11
#: WHY 5.11 IS ORCHESTRATED HERE (dry runs S3 / D1, research/phase4/LEVEL_C_DRIVER.md section 9). `representation_stability` interleaves
#: its models (all models' validation latents, then all test latents, effects, flows). Every RemoteFresh of one job starts its workers
#: under the SAME role uid of the job's slot, and a worker start SIGKILLs every process of that uid (`isolation.LinuxUidTransport.start`),
#: so each model's worker killed the previous model's: that model's next calls failed (silently: `safe_call`) until a digest-rule
#: restart revived it, and 5.11 ran on a reduced, model-independent sample (real:A:full: 14 of 24 effect items). And on systems whose
#: records sit on exact fixed points (the real mechanisms) the digest rule restarts a worker about 100 times per model, which in a
#: packed iso slot never finished. Here each model's calls run to completion in ITS OWN RemoteFresh (one live model at a time; the
#: digest rule unchanged), are RECORDED, and the frozen `representation_stability` then runs on REPLAYS of the recordings: the same
#: calls in the same per-model order, the same metric code, no second evaluation of anything.
STABILITY_OPS = ("encode", "rollout", "intervention_effect")


class ReplayMismatch(BaseException):
    """A replayed call differs from the recorded one (a BaseException: `fresh.safe_call` must not score it as a model failure)."""


class DeadlineReached(BaseException):
    """The diagnostic's deadline passed (a BaseException so `safe_call` does not swallow it)."""


def call_key(op: str, args: tuple) -> str:
    """A digest of one model call (operation, arrays by dtype / shape / bytes, everything else by repr)."""
    import hashlib

    import numpy as np
    h = hashlib.blake2b(op.encode(), digest_size=16)
    for a in args:
        if isinstance(a, np.ndarray) or (hasattr(a, "__array__") and not isinstance(a, (list, tuple, dict, str))):
            arr = np.ascontiguousarray(np.asarray(a))
            h.update(f"{arr.dtype}{arr.shape}".encode())
            h.update(arr.tobytes())
        else:
            h.update(repr(a).encode())
        h.update(b"|")
    return h.hexdigest()


def _fresh_base():
    from brainir_causal.fresh import Fresh
    return Fresh


class _RecordingMixin:
    """Forwards the stability calls to one model's RemoteFresh and records them: (op, key, ok, result or error message); per-op counts
    and seconds, the calls that restarted a worker, the slowest calls; optionally stops at a deadline (the diagnostic)."""

    def _init_recording(self, rf, deadline: float | None = None):
        self._rf, self._deadline = rf, deadline
        self._same = None
        self.calls: list = []
        self.stats = {op: {"n": 0, "s": 0.0, "max_s": 0.0, "errors": 0} for op in STABILITY_OPS}
        self.restart_calls: list = []
        self.slow: list = []
        self.errors: dict = {}

    def get(self):
        raise RuntimeError("the recording wrapper has no local model")

    def _do(self, op: str, args: tuple):
        if self._deadline is not None and time.time() > self._deadline:
            raise DeadlineReached(f"deadline before {op} (call {len(self.calls)})")
        key = call_key(op, args)
        r0 = int(getattr(self._rf, "n_restarts", 0))
        t0 = time.perf_counter()
        err = None
        try:
            val = getattr(self._rf, op)(*args)
        except Exception as e:  # noqa: BLE001 - recorded, then re-raised to the frozen helper (scored as a failed call there)
            val, err = None, e
        dt = time.perf_counter() - t0
        st = self.stats[op]
        st["n"] += 1
        st["s"] += dt
        st["max_s"] = max(st["max_s"], dt)
        if int(getattr(self._rf, "n_restarts", 0)) > r0:
            self.restart_calls.append({"op": op, "call": len(self.calls), "s": round(dt, 3)})
        if dt > 5.0 and len(self.slow) < 50:
            self.slow.append({"op": op, "call": len(self.calls), "s": round(dt, 2), "error": None if err is None else type(err).__name__})
        if err is not None:
            st["errors"] += 1
            name = type(err).__name__
            self.errors[name] = self.errors.get(name, 0) + 1
            self.calls.append((op, key, False, f"{name}: {str(err)[:300]}"))
            raise err
        self.calls.append((op, key, True, val))
        return val

    def encode(self, sid, x_hist, u_hist, dt):
        return self._do("encode", (sid, x_hist, u_hist, dt))

    def rollout(self, sid, z0, u_future, events, dt):
        return self._do("rollout", (sid, z0, u_future, events, dt))

    def intervention_effect(self, sid, x_hist, u_hist, u_future, events, dt):
        return self._do("intervention_effect", (sid, x_hist, u_hist, u_future, events, dt))

    def summary(self) -> dict:
        normal = [c for c in self.calls]
        return {"n_calls": len(normal), "ops": {op: {k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items()}
                                                for op, s in self.stats.items()},
                "errors": dict(self.errors), "restarts": len(self.restart_calls),
                "restart_call_s_mean": (round(sum(c["s"] for c in self.restart_calls) / len(self.restart_calls), 3)
                                        if self.restart_calls else None),
                "slowest": sorted(self.slow, key=lambda c: -c["s"])[:10]}


class _ReplayMixin:
    """Serves one model's recorded calls in order; a call that differs from the recording raises ReplayMismatch."""

    def _init_replay(self, calls: list):
        self._calls, self._i = list(calls), 0
        self._same = None

    def get(self):
        raise RuntimeError("the replay wrapper has no local model")

    def _next(self, op: str, args: tuple):
        if self._i >= len(self._calls):
            raise ReplayMismatch(f"replay exhausted at call {self._i} ({op})")
        rop, key, ok, val = self._calls[self._i]
        if rop != op or key != call_key(op, args):
            raise ReplayMismatch(f"call {self._i}: replayed {op} differs from the recorded {rop}")
        self._i += 1
        if not ok:
            from brainir_causal.fresh import ModelCallError
            raise ModelCallError(str(val))
        return val

    def encode(self, sid, x_hist, u_hist, dt):
        import numpy as np
        return np.asarray(self._next("encode", (sid, x_hist, u_hist, dt)), dtype=np.float64).reshape(-1)

    def rollout(self, sid, z0, u_future, events, dt):
        return self._next("rollout", (sid, z0, u_future, events, dt))

    def intervention_effect(self, sid, x_hist, u_hist, u_future, events, dt):
        return self._next("intervention_effect", (sid, x_hist, u_hist, u_future, events, dt))

    def exhausted(self) -> bool:
        return self._i == len(self._calls)


def recording(rf, deadline: float | None = None):
    """A `fresh.Fresh` (so `as_fresh` passes it through) that records one model's stability calls."""
    cls = type("RecordingFresh", (_RecordingMixin, _fresh_base()), {})
    obj = cls.__new__(cls)
    obj._init_recording(rf, deadline)
    return obj


def replay(calls: list):
    """A `fresh.Fresh` that replays recorded calls."""
    cls = type("ReplayFresh", (_ReplayMixin, _fresh_base()), {})
    obj = cls.__new__(cls)
    obj._init_replay(calls)
    return obj


def record_stability_calls(model, sid: str, val: list, test: list, *, n_times: int, horizon_s: float, horizon_short_s: float):
    """Every call `representation_stability` makes for ONE model, in its per-model order (validation latents, test latents, predicted
    effects, flows at the model's own test samples); `model` is a Fresh (a RecordingFresh around the model's RemoteFresh)."""
    from brainir_causal import evaluate_stability as ES
    ES.latent_samples(model, sid, val, n_times)
    zt = ES.latent_samples(model, sid, test, n_times)
    ES.predicted_effects(model, sid, test, horizon_s)
    ES.latent_flows(model, sid, test, zt[1], horizon_short_s)


def _stability_inputs(job: dict):
    from brainir_causal import harness as H
    from brainir_causal.evalio import VERDICT_KINDS
    inputs, _internal, _ctx, _truth = H.system_context(job)
    sysc = inputs["system"]
    val = _records_with_twins(inputs["public"], lambda r: r.get("split") == "val")
    test = _records_with_twins(inputs["heldout"], lambda r: r.get("split") == "test" and _role(r) in (*VERDICT_KINDS, "passive"))
    return sysc, val, test


def stability(job: dict, *, transport, models: dict) -> dict:
    """PROTOCOL 5.11 on one system: `evaluate_stability.representation_stability` over the given models (job["model_order"]: the fit
    seeds and the bootstrap refits; a failed fit is absent and reported). Maps are fitted on the PUBLIC validation records (split
    'val' with their twins) and measured on the held-out test trajectories (verdict items with their twins, and the passive test
    trajectories). Each model's calls run to completion in its own RemoteFresh, one model at a time (the models share their slot's
    role uid; see the note above), and are recorded; the frozen function then computes every metric on replays of the recordings.
    Within a model the digest rule is unchanged (the latent samples of held-out trajectories precede the predicted effects in one
    worker, a descriptive metric; research/phase4/LEVEL_C_DRIVER.md)."""
    from brainir_causal.evaluate_stability import representation_stability
    t0 = time.time()
    models = resolve_models(models)
    sysc, val, test = _stability_inputs(job)
    sid = job["sid"]
    order = [n for n in job["model_order"]]
    names = [n for n in order if n in models]
    n_times = int(job.get("n_times", 8))
    hs, hm = sysc.horizon_s("short"), sysc.horizon_s("medium")
    recs, iso, per_model = [], [], {}
    for n in names:
        t1 = time.time()
        rf = _remote(models[n], transport, job)
        rec = recording(rf)
        try:
            record_stability_calls(rec, sid, val, test, n_times=n_times, horizon_s=hm, horizon_short_s=hs)
        finally:
            iso.append(rf.close())
        recs.append(rec)
        per_model[n] = {**rec.summary(), "wall_s": round(time.time() - t1, 1)}
    t2 = time.time()
    if len(recs) >= 2:
        reps = [replay(r.calls) for r in recs]
        rep = representation_stability(reps, sid, val, test, horizon_short_s=hs, horizon_s=hm, floor=sysc.floor, n_times=n_times)
        if not all(r.exhausted() for r in reps):
            raise ReplayMismatch("representation_stability made fewer calls than were recorded")
    else:
        rep = {"error": f"fewer than 2 models ({len(recs)})"}
    rep.update({"sid": sid, "models": names, "missing_models": [n for n in order if n not in models], "n_val_records": len(val),
                "n_test_records": len(test), "isolation": [_iso_summary(r) for r in iso], "per_model": per_model,
                "orchestration": "one model at a time (recorded), metrics by the frozen representation_stability on the recordings",
                "pairs_s": round(time.time() - t2, 1), "wall_s": round(time.time() - t0, 1)})
    return rep


def stability_diag(job: dict, *, transport, models: dict) -> dict:
    """DRY-RUN DIAGNOSTIC of the 5.11 job (`level_c.py diag-stability`), bounded by job["deadline_s"]; never official data.
      restart  the cost of a digest-rule worker restart: `_restart_sub` + the next call's worker start (spawn, init, model load), timed
               job["n_restart_probes"] times on one model
      kill     do two RemoteFresh of one job share a worker uid? model 0's worker, then model 1's start, then model 0's next call
      replay   the digest-rule restarts of each model's call sequence (records only, no worker; `isolation.history_digests`)
      run      the fixed orchestration (`stability`'s: one model at a time, recorded), instrumented per model and per call, up to the
               deadline; then the frozen representation_stability on the replays (timed) and each pair's metrics (timed per pair)"""
    import numpy as np

    from brainir_causal import evaluate_stability as ES
    from brainir_causal.evaluate_stability import representation_stability
    from brainir_causal.isolation import history_digests
    t0 = time.time()
    deadline = t0 + float(job.get("deadline_s", 2100))
    models = resolve_models(models)
    sysc, val, test = _stability_inputs(job)
    sid = job["sid"]
    names = [n for n in job["model_order"] if n in models]
    n_times = int(job.get("n_times", 8))
    hs, hm = sysc.horizon_s("short"), sysc.horizon_s("medium")
    out: dict = {"sid": sid, "models": names, "n_val_records": len(val), "n_test_records": len(test), "events": []}

    def ev(what, **kw):
        out["events"].append({"t": round(time.time() - t0, 1), "what": what, **kw})

    # ---- restart: the cost of a worker restart
    rf = _remote(models[names[0]], transport, job)
    try:
        t1 = time.perf_counter()
        rf.supports(sid, "kick")
        first = time.perf_counter() - t1
        costs = []
        for _ in range(int(job.get("n_restart_probes", 5))):
            t1 = time.perf_counter()
            rf._restart_sub("A")
            t2 = time.perf_counter()
            rf.supports(sid, "kick")
            costs.append({"close_s": round(t2 - t1, 3), "start_s": round(time.perf_counter() - t2, 3)})
        t1 = time.perf_counter()
        rf.supports(sid, "kick")
        warm = time.perf_counter() - t1
    finally:
        rf.close()
    out["restart"] = {"first_start_s": round(first, 3), "warm_call_s": round(warm, 4), "probes": costs,
                      "restart_s_mean": round(float(np.mean([c["close_s"] + c["start_s"] for c in costs])), 3) if costs else None}
    ev("restart probes done")
    # ---- kill: two RemoteFresh of one job
    r = test[0]
    x, u = np.asarray(ES._get(r, "x")), np.asarray(ES._get(r, "u"))
    h = max(2, len(x) // 2)
    ra, rb = _remote(models[names[0]], transport, job), _remote(models[names[1 % len(names)]], transport, job)
    kill: dict = {}
    try:
        for label, m in (("a_first", ra), ("b_starts", rb), ("a_again", ra)):
            t1 = time.perf_counter()
            try:
                m.encode(sid, x[:h], u[:h], ES._dt(r))
                kill[label] = {"ok": True, "s": round(time.perf_counter() - t1, 3)}
            except Exception as e:  # noqa: BLE001 - the observation
                kill[label] = {"ok": False, "s": round(time.perf_counter() - t1, 3), "error": f"{type(e).__name__}: {str(e)[:200]}"}
    finally:
        kill["a_close"] = {k: v for k, v in (ra.close().get("phases", {}).get("A") or {}).items() if k in ("n_calls", "restarts")}
        rb.close()
    out["kill"] = {**kill, "shared_uid_kills_idle_worker": bool(kill.get("a_first", {}).get("ok") and not kill.get("a_again", {}).get("ok"))}
    ev("kill check done")
    # ---- replay of the digest rule on the records (no worker)
    seen: dict = {}
    restarts, n_calls = [], 0

    def dig(op, hist):
        nonlocal n_calls
        n_calls += 1
        whole, last, rows = history_digests(hist)
        if last is not None and seen and (seen.get(last, set()) - {whole}):
            restarts.append(op)
            seen.clear()
        for rr in rows:
            seen.setdefault(rr, set()).add(whole)
    for recs_ in (val, test):
        for rr in recs_:
            xx = np.asarray(ES._get(rr, "x"))
            for i in np.unique(np.linspace(max(1, int(0.15 * len(xx))), len(xx) - 1, n_times).astype(int)):
                dig("encode", xx[: i + 1])
    for ri, _tw, i0, _rel in ES._items(test):
        xx = np.asarray(ES._get(ri, "x"))
        if i0 + max(1, round(hm / ES._dt(ri))) < len(xx):
            dig("intervention_effect", xx[: i0 + 1])
    out["digest_replay"] = {"calls_before_flows": n_calls, "restarts_before_flows": len(restarts)}
    ev("digest replay done")
    # ---- run: the fixed orchestration, instrumented, up to the deadline
    recs, per_model = [], {}
    for n in names:
        t1 = time.time()
        rfm = _remote(models[n], transport, job)
        rec = recording(rfm, deadline=deadline)
        stopped = None
        try:
            record_stability_calls(rec, sid, val, test, n_times=n_times, horizon_s=hm, horizon_short_s=hs)
        except DeadlineReached as e:
            stopped = str(e)
        finally:
            closed = rfm.close()
        per_model[n] = {**rec.summary(), "wall_s": round(time.time() - t1, 1), "stopped": stopped,
                        "isolation": _iso_summary(closed)}
        ev("model done" if stopped is None else "model stopped at the deadline", model=n, wall_s=per_model[n]["wall_s"])
        if stopped is not None:
            break
        recs.append(rec)
    out["per_model"] = per_model
    out["models_completed"] = len(recs)
    if len(recs) >= 2:
        t1 = time.time()
        reps = [replay(r.calls) for r in recs]
        rep = representation_stability(reps, sid, val, test, horizon_short_s=hs, horizon_s=hm, floor=sysc.floor, n_times=n_times)
        out["replayed_representation_stability_s"] = round(time.time() - t1, 2)
        out["replays_exhausted"] = all(r.exhausted() for r in reps)
        out["metrics"] = {k: v for k, v in rep.items() if k != "pairs"}
        out["pair_counts"] = [(p["a"], p["b"], p.get("n_items"), p.get("flow_n")) for p in rep.get("pairs") or []][:10]
        # per-pair timings of the frozen pair metrics (the same helpers representation_stability calls)
        t1 = time.time()
        reps2 = [replay(r.calls) for r in recs]
        Zv = [ES.latent_samples(m, sid, val, n_times) for m in reps2]
        Zt = [ES.latent_samples(m, sid, test, n_times) for m in reps2]
        effs = [ES.predicted_effects(m, sid, test, hm) for m in reps2]
        flows = [ES.latent_flows(m, sid, test, Zt[i][1], hs) for i, m in enumerate(reps2)]
        pair_s = []
        for a in range(len(reps2)):
            for b in range(a + 1, len(reps2)):
                tp = time.perf_counter()
                Zva, Zvb = ES._common(Zv[a][0], Zv[a][1], Zv[b][0], Zv[b][1])
                Zta, Ztb = ES._common(Zt[a][0], Zt[a][1], Zt[b][0], Zt[b][1])
                if len(Zva) >= 5 and len(Zta) >= 3:
                    ES.cross_r2(Zva, Zvb, Zta, Ztb)
                    ES.cca_padded(Zva, Zvb, Zta, Ztb)
                    ES.procrustes_residual(Zva, Zvb, Zta, Ztb)
                    ES.effect_disagreement(effs[a], effs[b], test, hm, sysc.floor)
                    ES.affine_map(Zva, Zvb)
                pair_s.append(round(time.perf_counter() - tp, 4))
        out["pair_s"] = {"n": len(pair_s), "max": max(pair_s) if pair_s else None, "sum": round(sum(pair_s), 3),
                         "replay_rebuild_s": round(time.time() - t1, 2), "n_flows": [int(f.shape[0]) for f in flows]}
    done = [v for v in per_model.values() if not v.get("stopped")]
    if done:
        mean_s = float(np.mean([v["wall_s"] for v in done]))
        out["projection_all_models_s"] = round(mean_s * len(names), 0)
    out["wall_s"] = round(time.time() - t0, 1)
    ev("done")
    return out


# ================================================================================================================ PROTOCOL 9 item set
def _calibrate_system_extra(sid: str, tier_root: str, tier: str, *, n_boot: int, seed: int, summary: dict | None,
                            public_root: str | None, extra_models: dict) -> dict:
    """`calibrate.calibrate_system` with extra models (its loader, unchanged, used until calibrate_system takes `extra_models`)."""
    from brainir_causal import calibrate as CAL
    from brainir_causal.suites import load_eval_inputs, tier_dirs
    root = Path(tier_root)
    dirs = tier_dirs(tier, root)
    summary = summary if summary is not None else CAL.system_truth_summaries(root, tier).get(sid, {})
    k_true = CAL.compressible(summary)
    if k_true is None:
        return {"sid": sid, "type": summary.get("type"), "k_true": None, "skipped": "not compressible", "errors": {}}
    inp = load_eval_inputs(sid, heldout_dirs=dirs, public_dirs=tier_dirs(tier, Path(public_root)) if public_root else None)
    tdir = dirs["truth"] / sid.replace(":", "_")
    tdir = tdir if tdir.exists() else None
    pset, held = inp["public"], inp["heldout"]
    train = [pset.load(r) for r in pset.rows if r.get("split") in ("train", "twin")]
    z, zo = {}, {}
    for r in train:
        tr = CAL._truth_arrays(tdir, r.key)
        if "z" in tr:
            z[r.key] = tr["z"]
        if "z_obs" in tr:
            zo[r.key] = tr["z_obs"]
    truth = {"z": z if len(z) == len(train) else None, "z_obs": zo if len(zo) == len(train) else None}
    try:
        from brainir_causal.harness import whiten_histories
        whiten = whiten_histories(inp)
    except Exception:  # noqa: BLE001 - the same rule on the loaded training records
        whiten = CAL.whiten_histories_from(train)

    def registrations():
        for rr in held.rows:
            rec = held.load(rr)
            tr = CAL._truth_arrays(tdir, rec.key)
            yield {"x": rec.x, "u": rec.u, "y": rec.y, "z": tr.get("z"), "z_obs": tr.get("z_obs")}

    return CAL.calibrate_from_inputs(sid, pub=inp["record"], sysc=inp["system"], train=train, items=inp["items"], pool=inp["pool"],
                                     k_true=k_true, truth=truth, register=registrations(), summary=summary, n_boot=n_boot, seed=seed,
                                     whiten_hists=whiten, extra_models=extra_models)


def same_items(job: dict, *, transport, models: dict) -> dict:
    """The calibration-style row of one compressible synthetic system at Level C: the references fitted on the system's training
    data and scored on the verdict items the TRUE-STATE reference supports (P_t: `calibrate.true_state_categories`), and the METHOD
    (models["method"], a RemoteFresh) scored on the SAME items as the extra model "method" (P_m - P_t on one item set:
    `calibrate.model_categories(rows, tol, "method")`). The method's dimension criterion is its Level C one: `verdict.dimension_status`
    over the 5 bootstrap refits' k (job["k_refits"]), compactness against the system's compact limit."""
    from brainir_causal import calibrate as CAL
    from brainir_causal.data import ExperimentSet
    from brainir_causal.suites import _safe, eval_system_from_public, tier_dirs
    from brainir_causal.verdict import dimension_status
    t0 = time.time()
    models = resolve_models(models)
    sid = job["sid"]
    pdirs = tier_dirs(job["tier"], Path(job.get("public_root") or job["tier_root"]))
    pub_set = ExperimentSet.load(pdirs["public"] / _safe(sid), lazy=True)
    sysc = eval_system_from_public(pub_set.systems[sid], pub_set)
    rf = _remote(models["method"], transport, job)
    try:
        info = rf.info() or {}
        k = (info.get("k") or {}).get(sid)
        kr = (info.get("k_range") or {}).get(sid)
        from brainir_causal.verdict import compact_limit_given_truth
        lim, _note = compact_limit_given_truth(sysc.compact_limit, sysc.kind, job.get("k_true"), job.get("d_draw"))
        dim = dimension_status(None if k is None else int(k), lim, job.get("k_refits"), tuple(kr) if kr else None,
                               level=str(job.get("level", "C")))
        if _note:
            dim["compact_note"] = _note
        extra = {"method": (rf, dim)}
        kw = {"n_boot": int(job.get("n_boot", 2000)), "seed": int(job.get("seed", 0)), "summary": job.get("summary"),
              "public_root": job.get("public_root")}
        if "extra_models" in inspect.signature(CAL.calibrate_system).parameters:
            row = CAL.calibrate_system(sid, job["tier_root"], job["tier"], extra_models=extra, **kw)
            row["loader"] = "calibrate.calibrate_system"
        else:
            row = _calibrate_system_extra(sid, job["tier_root"], job["tier"], extra_models=extra, **kw)
            row["loader"] = "levelc_remote._calibrate_system_extra (calibrate_system without extra_models)"
    finally:
        rec = rf.close()
    row["method_dimension"] = dim
    row["method_isolation"] = _iso_summary(rec)
    row["wall_s_job"] = round(time.time() - t0, 1)
    return row


# ================================================================================================================ 5.13 / 5.14 fits
def fit_records(job: dict, *, transport, models: dict) -> dict:
    """A method fit on FILTERED training records (the records `isolation.fit_job` would load: splits + the twins of their
    intervention records). job["select"]: {"kind": "loio", "family": f} (every record of family f's intervention items and their
    twins removed: `evaluate_transfer.loio_datasets`), {"kind": "limpo", "frac": 0.25, "seed": s} (`evaluate_transfer.limpo_subsample`),
    or absent (all records). models["adapt_from"] (optional): the shared model the fit adapts from (config adapt_from: the transition
    law frozen). Returns {"model": bytes, "side": {...}} or {"skipped": reason}."""
    from brainir_causal import evaluate_transfer as ET
    from brainir_causal.isolation import fit_records as iso_fit_records
    from brainir_causal.runner import load_records
    t0 = time.time()
    models = resolve_models(models)
    splits = str(job.get("splits", "train"))
    recs, sysinfo = load_records(list(job["data"]), list(job["systems"]), set(splits.split(",")))
    n_all = len(recs)
    sel = dict(job.get("select") or {})
    if sel.get("kind") == "loio":
        sid = job["systems"][0]
        views = ET.loio_datasets(recs, sysinfo[sid], families=[str(sel["family"])])
        if str(sel["family"]) not in views:
            return {"skipped": f"family {sel['family']} has no intervention item in the training records", "n_train_all": n_all}
        recs = views[str(sel["family"])]
    elif sel.get("kind") == "limpo":
        recs = ET.limpo_subsample(recs, float(sel.get("frac", 0.25)), int(sel.get("seed", 0)))
    elif sel:
        raise ValueError(f"unknown record selection {sel!r}")
    out = iso_fit_records(transport, method=job["method"], records=recs, systems=sysinfo, config=job.get("config"),
                          seed=int(job.get("seed", 0)), adapt_from=models.get("adapt_from"), threads=int(job.get("threads", 3)),
                          timeout_s=float(job.get("timeout_s", 4 * 3600)))
    side = out["side"]
    side.update({"systems": list(job["systems"]), "seed": int(job.get("seed", 0)), "config": dict(job.get("config") or {}),
                 "adapted": models.get("adapt_from") is not None, "splits": splits, "select": sel, "n_train": len(recs),
                 "n_train_all": n_all, "job_wall_s": round(time.time() - t0, 2),
                 "isolation": {"transport": getattr(transport, "kind", "?"),
                               "worker": {k: v for k, v in (out.get("worker") or {}).items() if k != "stderr_tail"}}})
    from brainir_causal.isolation import MAX_INLINE_OUTPUT, stage_blob
    if len(out["model"]) > MAX_INLINE_OUTPUT - 64 * 1024:
        # above the inline limit of a block_network container: STAGE it on the store volume (a public-data-derived model). The runner
        # commits the volumes an iso "call" result lists under "staged" (requested of P1); until then keep models small in dry runs
        return {"model_ref": stage_blob(out["model"], vol="store"), "side": side, "staged": ["store"]}
    return {"model": out["model"], "side": side}


# ================================================================================================================ item subsets
def eval_items(job: dict, *, transport, models: dict) -> dict:
    """EE units of every model in job["model_order"] on an item SUBSET of one system: the verdict items whose family is in
    job["items"]["families"] and / or whose role is in job["items"]["roles"]. Per model: {"units": {item: [num, den]}, "families":
    {item: family}, "EE_cb" (class-balanced, primary horizon), "EE_pooled", counts, "k", "n_params"} and, with job["mediation"], the
    state-mediation score on the same items (`evaluate_mediation.eval_mediation`). Predictions only (isolation phase A)."""
    from brainir_causal import evaluate as EV
    from brainir_causal import evaluate_mediation as EM
    from brainir_causal import harness as H
    from brainir_causal.evalio import PRIMARY, VERDICT_KINDS
    t0 = time.time()
    models = resolve_models(models)
    inputs, _internal, _ctx, _truth = H.system_context(job)
    sid, sysc = job["sid"], inputs["system"]
    sel = dict(job.get("items") or {})
    fams, roles = set(sel.get("families") or []), set(sel.get("roles") or [])
    items = [it for it in H.verdict_items(inputs["items"]) if (not fams or str(it.family) in fams)
             and (not roles or str(it.shift).split(":", 1)[0] in roles)]
    n_boot, seed = int(job.get("n_boot", 2000)), int(job.get("seed", 0))
    out: dict = {"sid": sid, "n_items": len(items), "selection": {"families": sorted(fams), "roles": sorted(roles)}, "models": {}}
    for name in job["model_order"]:
        if name not in models:
            out["models"][name] = {"error": "no model (the fit failed or was skipped)"}
            continue
        rf = _remote(models[name], transport, job)
        r: dict = {}
        try:
            info = rf.info() or {}
            r["k"] = (info.get("k") or {}).get(sid)
            r["n_params"] = info.get("n_params")
            preds = EV.predict_items(rf, sysc, items)
            eff = EV.eval_effects(sysc, items, preds, n_boot, seed)
            units, famof = units_primary(eff)
            r.update({"units": {k: [v[0], v[1]] for k, v in units.items()}, "families": famof,
                      "EE_cb": _est(EV.ee_cb(eff["_units"], PRIMARY, VERDICT_KINDS, "class", n_boot, seed)),
                      "EE_pooled": {k: (eff.get(f"EE_{PRIMARY}") or {}).get(k) for k in ("point", "ci95")},
                      "n_abstained": int(eff.get("n_abstained") or 0), "n_failed": int(eff.get("n_failed") or 0)})
            if job.get("mediation"):
                med = EM.eval_mediation(sysc, items, preds, n_boot=n_boot, seed=seed)
                sms = med.get("SMS") or {}
                r["SMS"] = {k: sms.get(k) for k in ("point", "ci95", "failed") if k in sms} if sms else {"error": str(med.get("error"))}
        except Exception as e:  # noqa: BLE001 - one model's failure is recorded, the others still run
            import traceback
            r["error"] = f"{type(e).__name__}: {e}"[:1000]
            r["traceback"] = traceback.format_exc()[-2000:]
        finally:
            r["isolation"] = _iso_summary(rf.close())
        out["models"][name] = r
    out["wall_s"] = round(time.time() - t0, 1)
    return out


# ================================================================================================================ trap tier probe
def trap_probe(job: dict, *, transport=None, models=None) -> dict:
    """DRY RUN ONLY (`level_c.py trap-probe`): the container path of review G's trap tier checked with a DUMMY catalog baked where an
    official run bakes the real one (levelc_lib.TRAP_CATALOG_CONTAINER). Reports the catalog as `synthadapter.trap_catalog_path()`
    resolves it here (sha256, owner, mode; root-only after the iso lockdown; `setpriv` as a worker uid must fail to read it) and builds
    its systems through `synthadapter.suite_systems("trap", seed)` (the code path of the official builds and evaluations) for the
    PUBLIC seed job["seed"]: ids, trap labels, k, the expected verdict, content hashes. The official trap tier's seed is salted."""
    import hashlib
    import subprocess

    from brainir_causal import synthadapter as SA
    gen = job.get("generator")
    if gen:
        SA.register_generator(gen[0], gen[1])
    path = SA.trap_catalog_path()
    st = path.stat()
    out: dict = {"catalog_path": str(path), "catalog_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "owner_uid": int(st.st_uid),
                 "mode": oct(st.st_mode & 0o777), "root_only": bool(st.st_uid == 0 and (st.st_mode & 0o077) == 0),
                 "repo_mode": oct(Path("/repo").stat().st_mode & 0o777)}
    uid = int(job.get("worker_uid", 10001))
    try:
        r = subprocess.run(["setpriv", f"--reuid={uid}", f"--regid={uid}", "--clear-groups", "cat", str(path)], capture_output=True,
                           timeout=30)
        out["worker_read_denied"] = bool(r.returncode != 0)
        out["worker_read_stderr"] = r.stderr.decode(errors="replace")[-300:]
    except Exception as e:  # noqa: BLE001 - reported
        out["worker_read_denied"] = None
        out["worker_read_error"] = f"{type(e).__name__}: {e}"[:300]
    t0 = time.time()
    systems = SA.suite_systems(SA.TRAP_TIER, int(job.get("seed", 0)))
    out["build_s"] = round(time.time() - t0, 2)
    rows = {}
    for sid, s in sorted(systems.items()):
        tr = s.truth() or {}
        rows[sid] = {"trap": tr.get("trap"), "trap_grade": tr.get("trap_grade"), "type": tr.get("type"), "k": tr.get("k"),
                     "expected_verdict": tr.get("expected_verdict"), "content_hash": s.content_hash(),
                     "single_threaded": type(s).__name__ == "SingleThreadedSystem"}
    out["systems"] = rows
    out["n_systems"] = len(rows)
    return out
