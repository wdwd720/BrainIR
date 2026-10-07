"""Evaluation harness (ORCHESTRATOR SIDE): evaluate one fitted model on one system's held-out data with every metric family of
benchmarks/causal_state_v1/PROTOCOL.md section 5, fit and evaluate the benchmark references (section 8), and assemble the verdict
inputs (section 9). Used identically by the calibration (references only), the Level B tournament and the Level C evaluation.

    inputs = suites.load_eval_inputs(sid, heldout_dirs=..., public_dirs=...)       # EvalSystem, items, pool, samples, lift cases
    res = evaluate_model(model, inputs, simulate_many=sim_fn, truth_system=obj)     # every family, COMPLETE (never only verdicts)
    refs = reference_results(sid, inputs, cache_dir=..., k=res["k"], ...)            # fitted once per system, cached
    v = assemble_verdict(ev, refs, tol, fullbound_eff=..., k_refits=[...])           # criteria A-H, the category, selection values

METHOD MODELS ARE NEVER LOADED HERE (research/phase4/EVAL_ARCHITECTURE.md; review F, F-B3): `evaluate_job` receives a fitted model
as BYTES and evaluates it through model workers (`brainir_causal.isolation.RemoteFresh`); only the benchmark's own trusted references
(`brainir_causal.refs`) are evaluated in-process. `evaluate_model` calls the model in the isolation PHASE ORDER: A (predictions from
pasts, public whitening histories, pool histories, truth samples, capacity), lift (native lift requests, then their simulated
outcomes), C (encodings of true future histories: closure, bisimulation).

VERDICT ITEMS (PROTOCOL 9): only the roles in-family, target shift, near shift, far shift and hidden-only enter verdict inputs
(`verdict_items`: effects, calibration, SMS, ICG); OOD and robustness items are scored for the 5.12 report only (res["items"]["ood"]).
Lift whitening uses the model's encodings of PUBLIC training histories only (never test data).

Families are kept separate and each family runs in its own guard: a failing family is recorded as {"error": ...} and never hides the
others. Per-item units (`_units`, needed for paired comparisons) stay in the result under private keys and are stripped by
`public_view`.

Truth (synthetic only) never reaches a model: items carry z_true / z_obs from the truth store and meta["state"] (the full microstate at
the onset) for `evaluate_truth.attach_truth`, which computes the exact true latent effect with the generator.
"""

from __future__ import annotations

import json
import pickle
import time
import traceback
from pathlib import Path

import numpy as np

REF_EVAL_NAMES = ("no_effect", "true_state", "full_state", "obs_shortcut", "random_k", "pca_k", "id_shortcut")
#: the references a verdict or a selection gate needs; they do not depend on a method's k, so a Level B round on Modal fits and
#: evaluates them ONCE per system (`references_job`) and the evaluation jobs read the cache (RANDOM-k / PCA-k are descriptive and
#: depend on k: evaluation jobs compute them only when asked, in their own container)
K_FREE_REFS = ("no_effect", "true_state", "full_state", "obs_shortcut", "id_shortcut")
N_WHITEN_HISTS = 64


def _guard(fn, *args, **kwargs) -> dict:
    t0 = time.time()
    try:
        out = fn(*args, **kwargs)
        if isinstance(out, dict):
            out = dict(out)
            out.setdefault("_wall_s", round(time.time() - t0, 3))
        return out
    except Exception as e:  # noqa: BLE001 - recorded, never silently dropped
        return {"error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-2000:], "_wall_s": round(time.time() - t0, 3)}


def public_view(res):
    """A result without the private per-unit payloads (keys starting with '_'), JSON-safe."""
    if isinstance(res, dict):
        return {k: public_view(v) for k, v in res.items() if not str(k).startswith("_") and k != "traceback"}
    if isinstance(res, (list, tuple)):
        return [public_view(v) for v in res]
    if isinstance(res, np.ndarray):
        return res.tolist()
    if isinstance(res, (np.floating, np.integer)):
        return res.item()
    return res


def to_jsonable(res):
    """A result with numpy types converted (private keys kept; answer-bearing on held-out data)."""
    if isinstance(res, dict):
        return {str(k): to_jsonable(v) for k, v in res.items()}
    if isinstance(res, (list, tuple)):
        return [to_jsonable(v) for v in res]
    if isinstance(res, np.ndarray):
        return res.tolist()
    if isinstance(res, (np.floating, np.integer)):
        return res.item()
    if hasattr(res, "__dataclass_fields__"):
        return to_jsonable({k: getattr(res, k) for k in res.__dataclass_fields__})
    return res


# ================================================================================================================ inputs
def whiten_histories(inputs: dict, n: int = N_WHITEN_HISTS) -> list[tuple]:
    """(x_hist, u_hist, dt) of up to n PUBLIC training histories (fixed times of the training trajectories) for latent whitening."""
    pub = inputs["public"]
    rows = [r for r in pub.rows if r.get("split") == "train"] if hasattr(pub, "rows") else []
    rng = np.random.default_rng(0)
    out = []
    for r in [rows[i] for i in sorted(rng.choice(len(rows), size=min(len(rows), max(1, n // 4)), replace=False))] if rows else []:
        tr = pub.load(r)
        m = len(tr.t)
        for fr in (0.3, 0.45, 0.6, 0.75):
            i = int(fr * (m - 1))
            out.append((tr.x[: i + 1], tr.u[: i + 1], float(tr.protocol["dt"])))
    return out[:n]


def attach_states(items: list, store, truth_dir: Path | str | None = None) -> int:
    """meta['state'] = the full microstate at each item's onset (synthetic truth). Read from the build's onset states
    (truth/<system>/onset_states.npz, keyed by the item's record key) when present, else from the store record of the item. Returns
    the number of items that got one."""
    n = 0
    onset_path = Path(truth_dir) / "onset_states.npz" if truth_dir else None
    if onset_path is not None and onset_path.exists():
        with np.load(onset_path) as z:
            have = set(z.files)
            for it in items:
                k = (it.meta or {}).get("key")
                if k in have:
                    it.meta["state"] = np.asarray(z[k], np.float64)
                    n += 1
        return n
    cache: dict[str, dict] = {}
    for it in items:
        sk = (it.meta or {}).get("store_key")
        if not sk:
            continue
        rec = cache.get(sk)
        if rec is None:
            rec = store.get(sk)
            cache.clear()
            cache[sk] = rec
        if rec is None or "state" not in rec:
            continue
        t = np.asarray(rec["t"], float)
        i = round((it.onset - t[0]) / (t[1] - t[0]))
        if 0 <= i < len(rec["state"]):
            it.meta["state"] = np.asarray(rec["state"][i], np.float64)
            n += 1
    return n


def lift_reach_fn(F, sid: str, truth_system, internal: dict, samples: list, items: list | None = None, preds: dict | None = None,
                  pool=None):
    """Synthetic systems (review T round 3, N4): (reach_fn, info). reach_fn(state) -> the KICK-REACHABLE latent shifts at a case's
    microstate in the MODEL's coordinates (rows): the true latent effect of a unit kick on every PUBLIC target (`true_latent_effect`),
    mapped by the affine map z ~ z_true @ M + b fitted, as the true read-in accuracy's map, on states that SPAN the true state (the
    truth samples, every item's onset state with the model's onset encoding, the pool states; `evaluate_truth._truth_map`, review H
    round 3b NEW-5). reach_fn is None (the requests then stay unrestricted) without public targets, with fewer than 8 fitting states,
    failed encodings or an unidentifiable map; info says which."""
    from .evalio import StateSample
    from .evaluate_truth import _truth_map, encode_samples
    units = [int(u) for u in (internal.get("targets_public") or [])]
    if not units:
        return None, {"reach": "no public targets"}
    zt_fit, z_fit = [], []
    samples = [s for s in samples if getattr(s, "z_true", None) is not None]
    if samples:
        Z, _ = encode_samples(F, sid, samples)
        if Z is None:
            return None, {"reach": "failed encodings"}
        zt_fit += [s.z_true for s in samples]
        z_fit += list(Z)
    for it in items or []:
        p = (preds or {}).get(it.item_id)
        if it.z_true is not None and p is not None and p.z0 is not None and np.isfinite(np.asarray(p.z0, float)).all():
            zt_fit.append(it.z_true)
            z_fit.append(np.asarray(p.z0, float).reshape(-1))
    if pool is not None and getattr(pool, "states", None):
        extra = [StateSample(sample_id=st.state_id, x_hist=st.x_hist, u_hist=st.u_hist, dt=float(pool.dt), group=st.traj, z_true=st.z_true)
                 for st in pool.states if st.z_true is not None]
        Zp, _ = encode_samples(F, sid, extra) if extra else (None, 0)
        if Zp is not None:
            zt_fit += [s.z_true for s in extra]
            z_fit += list(Zp)
    if len(zt_fit) < 8 or len({np.asarray(a).size for a in z_fit}) != 1:
        return None, {"reach": "too few fitting states or encodings of different sizes", "n_states": len(zt_fit)}
    M, rank, dim = _truth_map(zt_fit, z_fit)
    if M is None:
        return None, {"reach": "unidentifiable: the fitting states do not span the true state", "rank": rank, "dim": dim,
                      "n_states": len(zt_fit)}

    def fn(state: np.ndarray) -> np.ndarray:
        rows = [np.asarray(truth_system.true_latent_effect(state, {"kind": "kick", "t": 0.0, "delta": {str(u): 1.0}}),
                           float).reshape(-1) @ M for u in units]
        return np.stack(rows)
    return fn, {"reach": "restricted", "n_states": len(zt_fit), "rank": rank, "dim": dim, "n_public_targets": len(units)}


def lift_cases_for(inputs: dict) -> list[dict]:
    """evaluate_lift cases [{"protocol": passive held-out protocol, "t": t_c, "id"}] from the builder's lift cases."""
    held = inputs["heldout"]
    by_key = {r["key"]: r for r in held.rows}
    out = []
    for c in inputs.get("lift_cases") or []:
        row = by_key.get(c["key"])
        if row is None:
            continue
        out.append({"protocol": row["protocol"], "t": float(c["t"]), "id": c["case_id"], "store_key": c.get("store_key")})
    return out


def lift_validator(internal: dict):
    """Validator of lift events: supported kinds of the system's capability, units among the targetable units (synthetic) or the
    public + hidden targets (real), magnitudes up to the upper end of the 'hi' ranges, no persistent events."""
    from .sampling import normalize_capability
    cap = normalize_capability(internal.get("capability"), t_end=float(internal["t_end_default"]), dt=float(internal["dt"]),
                               input_dim=int(internal.get("input_dim", 1)))
    units = {int(u) for u in (internal.get("targetable") or [])} or ({int(u) for u in internal.get("targets_public") or []}
                                                                          | {int(u) for u in internal.get("targets_heldout") or []})
    edges = {tuple(map(int, e)) for e in (internal.get("edges") or [])} or {tuple(map(int, e)) for e in (internal.get("edges_public") or [])}

    def validate(events_abs: list[dict], protocol: dict) -> str | None:
        for e in events_abs:
            k = e.get("kind")
            if not cap.get(k, {}).get("supported"):
                return f"event kind {k!r} is not supported by this system"
            if e.get("t1", 0) is None:
                return "persistent events cannot realise a latent shift"
            if k == "kick":
                if any(int(u) not in units for u in e["delta"]) or any(abs(float(v)) > cap["kick"]["hi_range"][1] for v in e["delta"].values()):
                    return "kick outside the targetable units or the admissible magnitude"
            elif k in ("current", "current_seq"):
                tg = e["targets"]
                vals = tg.values() if k == "current" else [v for lst in tg.values() for v in lst]
                if any(int(u) not in units for u in tg) or any(abs(float(v)) > cap["current"]["hi_range"][1] for v in vals):
                    return "current outside the targetable units or the admissible magnitude"
            elif k == "silence":
                if any(int(u) not in units for u in e["targets"]):
                    return "silencing outside the targetable units"
            elif k == "param":
                if any(int(u) not in units for u in e["targets"]):
                    return "parameter change outside the targetable units"
            elif k == "edge_scale" and edges and any(tuple(map(int, x)) not in edges for x in e["edges"]):
                return "edge scaling of an unknown edge"
        return None
    return validate


def simulate_many_for(ctx):
    """evaluate_lift's simulate_many(protocols, full=False) on a suites.SimContext (records: t, x, u, y; with full: 'z' and 'state'
    for synthetic systems)."""
    def fn(protocols: list[dict], full: bool = False) -> list[dict]:
        out = []
        for p in protocols:
            r = ctx.run(p)
            rec = {"t": r["t"], "x": r["x"], "u": r["u"], "y": r["y"]}
            if full and ctx.kind == "synthetic":
                if (r.get("truth") or {}).get("draw") is not None:       # the trajectory's effective draw (TRUE-STATE's context)
                    rec["draw"] = np.asarray(r["truth"]["draw"], np.float64)
                src = ctx.store.get(r["store_key"])
                if src is not None:
                    if "z" in src:
                        rec["z"] = np.asarray(src["z"], np.float64)
                    if "state" in src:
                        rec["state"] = np.asarray(src["state"], np.float64)
            out.append(rec)
        return out
    return fn


# ================================================================================================================ one model
def verdict_items(items: list) -> list:
    """The items whose roles enter verdict criteria (PROTOCOL 9): in-family, target shift, near shift, far shift and hidden-only.
    OOD and robustness items are reported by 5.12 only."""
    from .evalio import VERDICT_KINDS
    return [it for it in items if str(it.shift).split(":", 1)[0] in VERDICT_KINDS]


def _phase(F, name: str) -> None:
    """Advance a RemoteFresh to the next isolation phase (a no-op for in-process trusted models)."""
    set_phase = getattr(F, "set_phase", None)
    if set_phase is not None:
        set_phase(name)


def compact_limit_for(sysc, truth_system=None) -> tuple[int | None, str | None]:
    """PROTOCOL 5.10 compactness limit of one system: max(1, N_obs / 5) (the EvalSystem's; None where compactness is not judged: real
    mechanisms), raised on SYNTHETIC systems by the draw allowance d_draw of the truth record (verdict.compact_limit_given_truth;
    LOG P4-D62). Returns (limit, note)."""
    from .verdict import compact_limit_given_truth
    if truth_system is None or not hasattr(truth_system, "truth"):
        return sysc.compact_limit, None
    tr = dict(truth_system.truth() or {})
    return compact_limit_given_truth(sysc.compact_limit, sysc.kind, tr.get("k"), tr.get("d_draw"))


def evaluate_model(model, inputs: dict, *, simulate_many=None, truth_system=None, internal: dict | None = None, lift: bool = True,
                   n_boot: int = 2000, seed: int = 0, families: tuple[str, ...] | None = None) -> dict:
    """Every metric family of PROTOCOL 5 on one system (the complete result; `public_view` strips per-unit payloads). `model` is a
    trusted in-process model (a benchmark reference), a `fresh.Fresh`, or an `isolation.RemoteFresh` (method models: model workers);
    the calls follow the isolation phase order A -> lift -> C."""
    from . import evaluate as EV
    from . import evaluate_mediation as EM
    from . import evaluate_micro as EMI
    from .fresh import as_fresh
    sysc, items = inputs["system"], inputs["items"]
    sid = sysc.system_id
    want = set(families) if families else None

    def on(fam: str) -> bool:
        return want is None or fam in want
    items_v = verdict_items(items)
    compact_limit, compact_note = compact_limit_for(sysc, truth_system)
    res: dict = {"system_id": sid, "kind": sysc.kind, "n_items": len(items), "n_verdict_items": len(items_v),
                 "compact_limit": compact_limit, "compact_judged": compact_limit is not None}
    if compact_note:
        res["compact_note"] = compact_note
    t_all = time.time()
    F = as_fresh(model)
    _phase(F, "A")
    # ---------------------------------------------------------------- phase A: predictions from pasts only
    if truth_system is not None and on("truth"):
        from .evaluate_truth import attach_truth
        res["truth_attach"] = _guard(lambda: (attach_truth(truth_system, items, inputs.get("samples")), {"ok": True})[1])
    info = {}
    try:
        info = F.info() or {}
    except Exception as e:  # noqa: BLE001 - a failing info() is recorded
        info = {"info_error": repr(e)}
    k = (info.get("k") or {}).get(sid)
    k_range = (info.get("k_range") or {}).get(sid)
    abst = (info.get("abstain") or {}).get(sid) or {}
    res.update({"k": k, "k_range": k_range, "abstain": abst, "info": {kk: info.get(kk) for kk in ("k", "k_range", "abstain", "history",
                                                                                               "n_params", "train_cost", "sharing")}})
    preds = EV.predict_items(F, sysc, items)
    if on("items"):
        # eval_effects keeps per-item units for every role; the verdict metrics (verdict.collect_metrics / evaluate.ee_cb) select the
        # VERDICT roles from them, and eval_ood (inside evaluate_items) reports OOD / robustness for the 5.12 report
        out = _guard(EV.evaluate_items, F, sysc, items, n_boot=n_boot, seed=seed, preds=preds)
        out.pop("_preds", None)
        res["items"] = out
    if on("mediation"):
        # eval_mediation / eval_closure select the verdict items themselves (E5): pass all items
        res["mediation"] = _guard(EM.eval_mediation, sysc, items, preds, n_boot=n_boot, seed=seed)
    pool = inputs.get("pool")
    hists = whiten_histories(inputs) if ((pool is not None and on("micro")) or (lift and simulate_many is not None and on("lift"))) else []
    w = None
    if pool is not None and on("micro"):
        wz = _guard(lambda: {"w": EMI.latent_whitener(F, sid, hists)})
        w = wz.get("w") if "error" not in wz else None
        res["micro"] = _guard(EMI.eval_microstate, F, sysc, pool, whiten_z=w, k_model=k, n_boot=n_boot, seed=seed)
    if sysc.kind == "synthetic" and on("truth"):
        from .evaluate_truth import eval_dimension_truth, eval_latent_recovery, eval_readin_truth
        truth = dict(getattr(truth_system, "truth", dict)() or {}) if truth_system is not None else dict(inputs.get("truth") or {})
        res["truth"] = {"latent_recovery": _guard(eval_latent_recovery, F, sid, inputs.get("samples") or [], seed=seed),
                        "dimension": _guard(eval_dimension_truth, k, tuple(k_range) if k_range else None,
                                            {kk: truth.get(kk) for kk in ("k", "type", "trap", "d_draw") if kk in truth},
                                            bool(abst.get("no_compact_state"))),
                        "read_in": _guard(eval_readin_truth, F, sid, items, preds, inputs.get("samples") or [],
                                              inputs.get("pool"))}
    if on("capacity"):
        from .capacity import capacity_record
        res["capacity"] = _guard(F.capacity, [sid]) if hasattr(F, "capacity") else _guard(capacity_record, F.get(), [sid])
    # ---------------------------------------------------------------- lift: requests, then (new worker) their simulated outcomes
    if lift and simulate_many is not None and on("lift"):
        from .evaluate_lift import LiftConfig, encodings_from_histories, eval_native_lift
        zpub = None
        try:
            zpub = encodings_from_histories(F, sid, hists)          # PUBLIC training histories (phase A); never test data
        except Exception:  # noqa: BLE001 - eval_native_lift reports the missing whitening
            zpub = None
        reach_fn = None
        if truth_system is not None and internal and hasattr(truth_system, "true_latent_effect"):
            rr = _guard(lift_reach_fn, F, sid, truth_system, internal, inputs.get("samples") or [], items, preds, pool)
            reach_fn = rr[0] if isinstance(rr, tuple) else None
            res["lift_reach"] = rr[1] if isinstance(rr, tuple) else rr         # how the reach map was fitted (or why not)
        _phase(F, "lift")
        cases = lift_cases_for(inputs)
        wkw = {"whiten_z": zpub} if zpub is not None and len(zpub) else {"whiten_histories": hists}
        cap = None
        if internal:
            from .sampling import normalize_capability
            cap = normalize_capability(internal.get("capability"), t_end=float(internal["t_end_default"]), dt=float(internal["dt"]),
                                       input_dim=int(internal.get("input_dim", 1)))
        res["lift"] = _guard(eval_native_lift, F, sid, cases, simulate_many, horizon_s=sysc.horizon_s("medium"), floor=sysc.floor,
                             validator=lift_validator(internal) if internal else None, truth=bool(sysc.kind == "synthetic"),
                             cfg=LiftConfig(n_boot=n_boot, seed=seed), capability=cap, reach_fn=reach_fn, **wkw)
    # ---------------------------------------------------------------- phase C: encodings of TRUE FUTURE histories
    _phase(F, "C")
    if on("closure"):
        res["closure"] = _guard(EM.eval_closure, F, sysc, items, preds, n_boot=n_boot, seed=seed)
    if pool is not None and on("micro"):
        res["bisimulation"] = _guard(EMI.eval_bisimulation, F, sysc, pool, whiten_z=w, seed=seed)
    res["eval_wall_s"] = round(time.time() - t_all, 2)
    res["_preds_errors"] = sum(1 for p in preds.values() if getattr(p, "error", None))
    return res


# ================================================================================================================ references
def training_records(inputs: dict, splits: tuple[str, ...] = ("train",)) -> list:
    """The fit data of the main comparison (PROTOCOL 4): the records of the given splits (D0 and D1 = 'train') and the twins of
    their intervention trajectories. The public validation set is for development only."""
    pub = inputs["public"]
    rows = pub.rows
    keys = {r["key"] for r in rows if r.get("split") in splits}
    return [pub.load(r) for r in rows if r.get("split") in splits or (r.get("split") == "twin" and (r.get("meta") or {}).get("twin_of") in keys)]


def training_truth(records: list, truth_dir: Path | None) -> dict | None:
    """{"z": {key: (T, k)}, "z_obs": {...}, "draw": {key: (d_draw,)}} of the training records (synthetic; from the truth store;
    "draw" = the effective draw parameters the TRUE-STATE / OBS-SHORTCUT references encode with z, LOG P4-D43) or None."""
    if truth_dir is None:
        return None
    z, zo, dr = {}, {}, {}
    for r in records:
        p = Path(truth_dir) / "traj" / f"{r.key}.npz"
        if not p.exists():
            continue
        with np.load(p) as a:
            if "z" in a.files:
                z[r.key] = a["z"]
            if "z_obs" in a.files:
                zo[r.key] = a["z_obs"]
            if "draw" in a.files:
                dr[r.key] = a["draw"]
    out = {}
    if z:
        out["z"] = z
    if zo:
        out["z_obs"] = zo
    if dr:
        out["draw"] = dr
    return out or None


def fit_system_references(sid: str, inputs: dict, *, cache_dir: Path | str, k: int | None, truth_dir: Path | None = None,
                          names: tuple[str, ...] = REF_EVAL_NAMES, cfg=None) -> tuple[dict, dict]:
    """(models, errors) of the benchmark references for one system, fitted on its training records (D0 + D1 and D1 twins) and cached
    as pickles under cache_dir/<sid>/<name>[_k<k>].pkl."""
    from .refs import LearnerConfig, fit_reference
    cfg = cfg or LearnerConfig()
    d = Path(cache_dir) / sid.replace(":", "_")
    d.mkdir(parents=True, exist_ok=True)
    records = training_records(inputs)
    truth = training_truth(records, truth_dir)
    models, errors = {}, {}
    order = ["full_state"] + [n for n in names if n != "full_state"]
    for name in order:
        if name not in names and name != "full_state":
            continue
        tag = f"{name}_k{k}" if name in ("pca_k", "random_k") else name
        path = d / f"{tag}.pkl"
        if path.exists():
            try:
                with open(path, "rb") as fh:
                    models[name] = pickle.load(fh)
                continue
            except Exception:  # noqa: BLE001 - refit a corrupt cache entry
                path.unlink(missing_ok=True)
        if name in ("true_state", "obs_shortcut") and not (truth or {}).get("z" if name == "true_state" else "z_obs"):
            continue
        if name in ("pca_k", "random_k") and not k:
            continue
        try:
            base = models.get("full_state") if name == "no_effect" else None
            m = fit_reference(name, sid, records, inputs["record"], k=k, truth=truth, base=base, cfg=cfg)
            models[name] = m
            with open(path, "wb") as fh:
                pickle.dump(m, fh, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:  # noqa: BLE001 - recorded per reference
            errors[name] = f"{type(e).__name__}: {str(e)[:300]}"
    return {n: m for n, m in models.items() if n in names}, errors


def register_heldout(models: dict, inputs: dict, truth_dir: Path | None) -> dict:
    """Register every held-out history of the system with the references that need it (in place): TRUE-STATE / OBS-SHORTCUT get the
    true state / the observational shortcut of each held-out record and its effective draw parameters (synthetic truth store: 'z',
    'z_obs', 'draw'), ID-SHORTCUT its readout history. Returns the number of records registered per reference."""
    held = inputs.get("heldout")
    counts = {n: 0 for n in models}
    if held is None:
        return counts
    need_truth = [(n, key) for n, key in (("true_state", "z"), ("obs_shortcut", "z_obs")) if n in models and hasattr(models[n], "register_truth")]
    idsc = models.get("id_shortcut") if hasattr(models.get("id_shortcut"), "register_readout") else None
    if not need_truth and idsc is None:
        return counts
    for row in held.rows:
        rec = held.load(row)
        dt = float(rec.protocol["dt"])
        if need_truth and truth_dir is not None:
            p = Path(truth_dir) / "traj" / f"{rec.key}.npz"
            if p.exists():
                with np.load(p) as a:
                    draw = a["draw"] if "draw" in a.files else None
                    for n, key in need_truth:
                        if key in a.files:
                            models[n].register_truth(rec.x, rec.u, a[key], dt, draw=draw)
                            counts[n] += 1
        if idsc is not None:
            idsc.register_readout(rec.x, rec.u, rec.y)
            counts["id_shortcut"] += 1
    return counts


def read_reference_results(sid: str, *, cache_dir: Path | str, names: tuple[str, ...] = K_FREE_REFS) -> dict:
    """The cached reference results of one system (read-only; `reference_results` / `references_job` wrote them). A missing
    k-free reference is reported in 'errors'."""
    d = Path(cache_dir) / sid.replace(":", "_")
    out = {"errors": {}, "results": {}}
    for name in names:
        if name in ("pca_k", "random_k"):
            continue
        path = d / f"{name}.result.pkl"
        if path.exists():
            with open(path, "rb") as fh:
                out["results"][name] = pickle.load(fh)
        elif name not in ("true_state", "obs_shortcut"):            # truth-based references exist only where truth does
            out["errors"][name] = "not in the round's reference cache"
    return out


def reference_results(sid: str, inputs: dict, *, cache_dir: Path | str, k: int | None, truth_dir: Path | None = None,
                      names: tuple[str, ...] = REF_EVAL_NAMES, simulate_many=None, internal: dict | None = None, n_boot: int = 2000,
                      seed: int = 0, lift: bool = False) -> dict:
    """Evaluate the references on the system's held-out data (results cached as JSON next to the fitted models, keyed by k). The
    held-out histories are REGISTERED first (TRUE-STATE / OBS-SHORTCUT: their true state; ID-SHORTCUT: their readout), as the
    calibration does: without it TRUE-STATE would fall back to its delay probe and ID-SHORTCUT could not encode."""
    models, errors = fit_system_references(sid, inputs, cache_dir=cache_dir, k=k, truth_dir=truth_dir, names=names)
    register_heldout(models, inputs, truth_dir)
    out = {"errors": errors, "results": {}}
    d = Path(cache_dir) / sid.replace(":", "_")
    for name, m in models.items():
        tag = f"{name}_k{k}" if name in ("pca_k", "random_k") else name
        path = d / f"{tag}.result.pkl"
        if path.exists():
            with open(path, "rb") as fh:
                out["results"][name] = pickle.load(fh)
            continue
        r = evaluate_model(m, inputs, simulate_many=simulate_many, internal=internal, lift=lift, n_boot=n_boot, seed=seed,
                           families=("items", "mediation", "closure", "micro", "truth"))
        with open(path, "wb") as fh:
            pickle.dump(r, fh, protocol=pickle.HIGHEST_PROTOCOL)
        out["results"][name] = r
    return out


# ================================================================================================================ verdict
def _effects(res: dict | None) -> dict | None:
    """The per-item effects (with private units) of an evaluation result; verdict.collect_metrics / evaluate.ee_cb select the VERDICT
    roles from the units themselves (PROTOCOL 9)."""
    if not res:
        return None
    eff = (res.get("items") or {}).get("effects")
    return eff if eff and "_units" in eff else None


def verdict_effects(res: dict | None) -> dict | None:
    """The effects (with private units) a Level B-fixed bound or comparator contributes to a paired verdict comparison."""
    return _effects(res)


def system_verdict_for(res: dict, refs: dict | None, tol, *, fullbound_eff: dict | None = None, idshortcut_eff: dict | None = None,
                       k_values: list[int] | None = None, level: str = "C", truth_noncompressible: bool | None = None,
                       n_boot: int = 2000, seed: int = 0) -> dict:
    """PROTOCOL 9 for one system: verdict.collect_metrics (which selects the verdict roles and builds the dimension from k_values +
    level) + system_verdict. The full-state bound and the ID-shortcut comparator default to the FULL-STATE / ID-SHORTCUT references;
    the tournament passes the choices FIXED at Level B (`fullbound_eff` / `idshortcut_eff`, from BOUNDS.json). k_values = the Level B
    seeds' or Level C refits' k (criterion F; without them F is missing and nothing can be SUPPORTED)."""
    from .verdict import Tolerances, collect_metrics, system_verdict
    eff = _effects(res)
    if eff is None:
        return {"error": "no effect results", "category": "unsupported"}
    rr = (refs or {}).get("results") or {}
    idsc = idshortcut_eff if idshortcut_eff is not None else _effects(rr.get("id_shortcut"))
    full = fullbound_eff if fullbound_eff is not None else _effects(rr.get("full_state"))
    m = collect_metrics(eff, eff_idshortcut=idsc, eff_fullbound=full, mediation=res.get("mediation"), closure=res.get("closure"),
                        micro=res.get("micro"), calibration=(res.get("items") or {}).get("calibration"),
                        declared_no_compact=bool((res.get("abstain") or {}).get("no_compact_state")),
                        truth_noncompressible=truth_noncompressible, n_boot=n_boot, seed=seed, k=res.get("k"),
                        k_range=tuple(res["k_range"]) if res.get("k_range") else None, compact_limit=res.get("compact_limit"),
                        k_values=list(k_values) if k_values else None, level=level)
    tol = tol if not isinstance(tol, dict) else Tolerances.from_dict(tol)
    v = system_verdict(m, tol, compact_judged=res.get("compact_judged", True))
    return {"metrics": public_view({kk: vv for kk, vv in m.items() if kk != "_estimates"}), "verdict": v,
            "_estimates": m.get("_estimates"),
            "bounds": {"fullbound": "given" if fullbound_eff is not None else "full_state reference",
                       "idshortcut": "given" if idshortcut_eff is not None else "id_shortcut reference"}}


def assemble_verdict(ev: dict, refs: dict | None, tol, *, calibrated: bool = True, fullbound_eff: dict | None = None,
                     idshortcut_eff: dict | None = None, k_refits: list[int] | None = None, level: str = "C",
                     fit_compute: dict | None = None, efficiency: float | None = None, n_boot: int = 2000, seed: int = 0) -> dict:
    """The verdict and the selection values of one evaluation (ORCHESTRATOR SIDE, after the evaluation): ev = `evaluate_job`'s output
    ({"sid", "kind", "result", "truth_k", "truth_noncompressible"}); k_refits = the criterion-F k list of PROTOCOL 5.10 (Level B: the k
    of the round's 3 fit seeds; Level C: the 5 bootstrap refits of the training interventions); fullbound_eff / idshortcut_eff = the
    Level B-fixed bound and comparator (None: the references)."""
    from . import select as SEL
    res = ev.get("result") or {}
    if not res or res.get("error"):
        return {"verdict": {"error": str(res.get("error") or "no result")}, "selection": SEL.failed_system_values(ev.get("kind") or "synthetic")}
    ver = system_verdict_for(res, refs, tol, fullbound_eff=fullbound_eff, idshortcut_eff=idshortcut_eff, k_values=k_refits, level=level,
                             truth_noncompressible=ev.get("truth_noncompressible"), n_boot=n_boot, seed=seed)
    ver["tolerances_calibrated"] = bool(calibrated)
    ver["k_refits"] = list(k_refits) if k_refits else None
    sel = SEL.per_system_values(ver, res, truth_k=ev.get("truth_k"), efficiency=efficiency, kind=ev.get("kind") or "synthetic",
                                fit_compute=fit_compute, truth_d_draw=ev.get("truth_d_draw"))
    return {"verdict": {k: v for k, v in ver.items() if k != "_estimates"}, "selection": sel}


def load_tolerances(path: Path | str | None = None):
    from .verdict import Tolerances
    p = Path(path) if path else Path(__file__).resolve().parents[3] / "benchmarks" / "causal_state_v1" / "public" / "tolerances.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    return Tolerances.from_dict(d.get("tolerances", d))


def dump(obj, path: Path | str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(to_jsonable(obj), indent=1, default=str) + "\n", encoding="utf-8", newline="\n")


# ================================================================================================================ jobs (local pools / Modal)
#: provisional tolerances used only until the dev calibration exists (verdicts computed with them are flagged "uncalibrated")
PROVISIONAL_TOLERANCES = {"delta_A": 0.1, "delta_C": 0.05, "tau_SMS": 0.1, "tau_ICG": 0.1, "tau_MEV": 0.3, "delta_H": 0.1, "tau_FC": 0.2}


def tolerances_or_provisional(path: Path | str | None = None) -> tuple:
    """(Tolerances, calibrated?)."""
    from .verdict import Tolerances
    try:
        return load_tolerances(path), True
    except (FileNotFoundError, KeyError, ValueError):
        return Tolerances.from_dict(PROVISIONAL_TOLERANCES), False


def system_context(job: dict):
    """(inputs, internal record, SimContext, truth system object | None) of an evaluation job's system (see `evaluate_job`)."""
    from . import suites as SU
    sid = job["sid"]
    held = SU.tier_dirs(job["heldout_tier"], Path(job["heldout_root"]))
    pubd = SU.tier_dirs(job.get("public_tier", job["heldout_tier"]), Path(job.get("public_root", job["heldout_root"])))
    inputs = SU.load_eval_inputs(sid, heldout_dirs=held, public_dirs=pubd, part=job.get("part", "eval"))
    truth_obj = None
    if job.get("internal_path"):
        internal = json.loads(Path(job["internal_path"]).read_text(encoding="utf-8"))[sid]
    else:
        internal = inputs["record"]
    if internal.get("kind") == "synthetic":
        from .synthadapter import register_generator, suite_systems
        if job.get("generator"):
            register_generator(job["generator"][0], job["generator"][1])
        truth_obj = suite_systems(internal["tier"], int(internal["suite_seed"]))[sid]
        ctx = SU.SimContext(internal, store_root=job["store_root"], synthetic_system=truth_obj, read_roots=job.get("store_read_roots") or ())
    else:
        ctx = SU.SimContext(internal, store_root=job["store_root"], read_roots=job.get("store_read_roots") or ())
    inputs["truth_dir"] = held["truth"] / SU._safe(sid) if (held["truth"] / SU._safe(sid)).exists() else None
    return inputs, internal, ctx, truth_obj


def _locked(path: Path):
    from .store import _acquire

    class _L:
        def __enter__(self):
            path.parent.mkdir(parents=True, exist_ok=True)
            _acquire(path, 7200.0, poll=0.2)
            return self

        def __exit__(self, *exc):
            path.unlink(missing_ok=True)
            return False
    return _L()


def _truth_summary(truth_obj) -> dict:
    truth = dict(truth_obj.truth() or {}) if truth_obj is not None else {}
    return {"truth_k": truth.get("k"), "truth_d_draw": truth.get("d_draw"),
            "truth_noncompressible": (str(truth.get("k")) == "none") if truth else None}


def references_job(job: dict) -> dict:
    """Fit and evaluate the references of one system (cached under job['ref_cache']); k = the dimension of RANDOM-k / PCA-k;
    job['ref_names'] restricts the references (default: all); job['return_results'] adds the reference results (trusted code, for
    the orchestrator's verdict assembly). The references are the benchmark's own trusted models and run in this process."""
    inputs, internal, ctx, truth_obj = system_context(job)
    if truth_obj is not None:
        attach_states(inputs["items"], ctx.store, inputs.get("truth_dir"))
        from .evaluate_truth import attach_truth
        attach_truth(truth_obj, inputs["items"], inputs.get("samples"))
    names = tuple(job.get("ref_names") or REF_EVAL_NAMES)
    t0 = time.time()
    with _locked(Path(job["ref_cache"]) / job["sid"].replace(":", "_") / f".lock_k{job.get('k')}"):
        refs = reference_results(job["sid"], inputs, cache_dir=job["ref_cache"], k=job.get("k"), truth_dir=inputs.get("truth_dir"),
                                 names=names, internal=internal, n_boot=int(job.get("n_boot", 2000)), seed=int(job.get("seed", 0)))
    out = {"sid": job["sid"], "k": job.get("k"), "kind": internal.get("kind"), "errors": refs["errors"], "references": sorted(refs["results"]),
           "wall_s": round(time.time() - t0, 1), **_truth_summary(truth_obj)}
    if job.get("return_results"):
        out["results"] = refs["results"]
    return out


def evaluate_job(job: dict, *, transport=None, model_bytes: bytes | None = None) -> dict:
    """Evaluate one fitted model on one system through MODEL WORKERS (`isolation.RemoteFresh`): every metric family of PROTOCOL 5.
    The model arrives as BYTES (model_bytes, or the file job['model_path']) and is never loaded in this process; `transport` says
    where the workers run (`isolation.LinuxUidTransport` in a container, `isolation.DockerTransport` on the development machine).
    job: {"sid", "heldout_root", "heldout_tier", ["public_root", "public_tier"], "store_root", ["store_read_roots"], ["internal_path"],
    ["generator": [dir, package]], ["lift"], ["n_boot"], ["seed"], ["families"], ["threads"], ["call_timeout_s"], ["out"]}. Returns
    {"sid", "kind", "result", "truth_k", "truth_noncompressible", "eval_job_wall_s"}: no verdict (`assemble_verdict` combines the
    result with the references, the Level B-fixed bounds and the dimension refits, orchestrator side)."""
    if transport is None:
        raise ValueError("evaluate_job runs method models only through model workers: pass an isolation transport")
    from .isolation import evaluate_remote
    t0 = time.time()
    inputs, internal, ctx, truth_obj = system_context(job)
    if truth_obj is not None:
        attach_states(inputs["items"], ctx.store, inputs.get("truth_dir"))
    blob = model_bytes if model_bytes is not None else Path(job["model_path"]).read_bytes()
    res = evaluate_remote(blob, inputs, transport, threads=int(job.get("threads", 2)), call_timeout_s=float(job.get("call_timeout_s", 900)),
                          simulate_many=simulate_many_for(ctx), truth_system=truth_obj, internal=internal, lift=bool(job.get("lift", True)),
                          n_boot=int(job.get("n_boot", 2000)), seed=int(job.get("seed", 0)),
                          families=tuple(job["families"]) if job.get("families") else None)
    out = {"sid": job["sid"], "kind": internal.get("kind"), "result": res, **_truth_summary(truth_obj),
           "eval_job_wall_s": round(time.time() - t0, 1)}
    if job.get("out"):
        with open(job["out"], "wb") as fh:
            pickle.dump(out, fh, protocol=pickle.HIGHEST_PROTOCOL)
        dump({k: (public_view(v) if k == "result" else v) for k, v in out.items()}, Path(job["out"]).with_suffix(".json"))
    return out
