"""Evaluation harness (ORCHESTRATOR SIDE): evaluate one fitted model on one system's held-out data with every metric family of
benchmarks/causal_state_v1/PROTOCOL.md section 5, fit and evaluate the benchmark references (section 8), and assemble the verdict
inputs (section 9). Used identically by the calibration (references only), the Level B tournament and the Level C evaluation.

    inputs = suites.load_eval_inputs(sid, heldout_dirs=..., public_dirs=...)       # EvalSystem, items, pool, samples, lift cases
    res = evaluate_model(model, inputs, simulate_many=sim_fn, truth_system=obj)     # every family, COMPLETE (never only verdicts)
    refs = reference_results(sid, inputs, cache_dir=..., k=res["k"], ...)            # fitted once per system, cached
    v = system_verdict_for(res, refs, tol, fullbound=...)                            # criteria A-H and the category

Families are kept separate and each family runs in its own guard: a failing family is recorded as {"error": ...} and never hides the
others. Model calls go through `brainir_causal.fresh` (fresh copies) inside E5 / E6's evaluators. Per-item units (`_units`, needed for
paired comparisons) stay in the result under private keys and are stripped by `public_view`.

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


def attach_states(items: list, store) -> int:
    """meta['state'] = the full microstate at each item's onset (synthetic truth; from the store record of the item). Returns the
    number of items that got one."""
    n = 0
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
    from .suites import normalize_capability
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
def evaluate_model(model, inputs: dict, *, simulate_many=None, truth_system=None, internal: dict | None = None, lift: bool = True,
                   n_boot: int = 2000, seed: int = 0, families: tuple[str, ...] | None = None) -> dict:
    """Every metric family of PROTOCOL 5 on one system (the complete result; `public_view` strips per-unit payloads)."""
    from . import evaluate as EV
    from . import evaluate_mediation as EM
    from . import evaluate_micro as EMI
    from .fresh import as_fresh
    sysc, items = inputs["system"], inputs["items"]
    sid = sysc.system_id
    want = set(families) if families else None
    res: dict = {"system_id": sid, "kind": sysc.kind, "n_items": len(items), "compact_limit": sysc.compact_limit,
                 "compact_judged": sysc.compact_limit is not None}
    t_all = time.time()
    F = as_fresh(model)
    if truth_system is not None and (want is None or "truth" in want):
        from .evaluate_truth import attach_truth
        res["truth_attach"] = _guard(lambda: (attach_truth(truth_system, items, inputs.get("samples")), {"ok": True})[1])
    info = {}
    try:
        info = F.get().info() or {}
    except Exception as e:  # noqa: BLE001 - a failing info() is recorded
        info = {"info_error": repr(e)}
    k = (info.get("k") or {}).get(sid)
    k_range = (info.get("k_range") or {}).get(sid)
    abst = (info.get("abstain") or {}).get(sid) or {}
    res.update({"k": k, "k_range": k_range, "abstain": abst, "info": {kk: info.get(kk) for kk in ("k", "k_range", "abstain", "history",
                                                                                               "n_params", "train_cost", "sharing")}})
    preds = EV.predict_items(F, sysc, items)
    if want is None or "items" in want:
        out = _guard(EV.evaluate_items, F, sysc, items, n_boot=n_boot, seed=seed, preds=preds)
        out.pop("_preds", None)
        res["items"] = out
    if want is None or "mediation" in want:
        res["mediation"] = _guard(EM.eval_mediation, sysc, items, preds, n_boot=n_boot, seed=seed)
    if want is None or "closure" in want:
        res["closure"] = _guard(EM.eval_closure, F, sysc, items, preds, n_boot=n_boot, seed=seed)
    pool = inputs.get("pool")
    if pool is not None and (want is None or "micro" in want):
        hists = whiten_histories(inputs)
        wz = _guard(lambda: {"w": EMI.latent_whitener(F, sid, hists)})
        w = wz.get("w") if "error" not in wz else None
        res["micro"] = _guard(EMI.eval_microstate, F, sysc, pool, whiten_z=w, k_model=k, n_boot=n_boot, seed=seed)
        res["bisimulation"] = _guard(EMI.eval_bisimulation, F, sysc, pool, whiten_z=w, seed=seed)
    if lift and simulate_many is not None and (want is None or "lift" in want):
        from .evaluate_lift import LiftConfig, eval_native_lift
        cases = lift_cases_for(inputs)
        res["lift"] = _guard(eval_native_lift, F, sid, cases, simulate_many, horizon_s=sysc.horizon_s("medium"), floor=sysc.floor,
                             whiten_trajs=None, validator=lift_validator(internal) if internal else None,
                             truth=bool(sysc.kind == "synthetic"), cfg=LiftConfig(n_boot=n_boot, seed=seed))
    if sysc.kind == "synthetic" and (want is None or "truth" in want):
        from .evaluate_truth import eval_dimension_truth, eval_latent_recovery, eval_readin_truth
        truth = dict(getattr(truth_system, "truth", dict)() or {}) if truth_system is not None else dict(inputs.get("truth") or {})
        res["truth"] = {"latent_recovery": _guard(eval_latent_recovery, F, sid, inputs.get("samples") or [], seed=seed),
                        "dimension": _guard(eval_dimension_truth, k, tuple(k_range) if k_range else None,
                                            {kk: truth.get(kk) for kk in ("k", "type", "trap") if kk in truth},
                                            bool(abst.get("no_compact_state"))),
                        "read_in": _guard(eval_readin_truth, F, sid, items, preds, inputs.get("samples") or [])}
    if want is None or "capacity" in want:
        from .capacity import capacity_record
        res["capacity"] = _guard(capacity_record, F.get(), [sid])
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
    """{"z": {key: (T, k)}, "z_obs": {...}} of the training records (synthetic; from the truth store) or None."""
    if truth_dir is None:
        return None
    z, zo = {}, {}
    for r in records:
        p = Path(truth_dir) / "traj" / f"{r.key}.npz"
        if not p.exists():
            continue
        with np.load(p) as a:
            if "z" in a.files:
                z[r.key] = a["z"]
            if "z_obs" in a.files:
                zo[r.key] = a["z_obs"]
    out = {}
    if z:
        out["z"] = z
    if zo:
        out["z_obs"] = zo
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


def reference_results(sid: str, inputs: dict, *, cache_dir: Path | str, k: int | None, truth_dir: Path | None = None,
                      names: tuple[str, ...] = REF_EVAL_NAMES, simulate_many=None, internal: dict | None = None, n_boot: int = 2000,
                      seed: int = 0, lift: bool = False) -> dict:
    """Evaluate the references on the system's held-out data (results cached as JSON next to the fitted models, keyed by k)."""
    models, errors = fit_system_references(sid, inputs, cache_dir=cache_dir, k=k, truth_dir=truth_dir, names=names)
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
    if not res:
        return None
    it = res.get("items") or {}
    eff = it.get("effects")
    return eff if eff and "_units" in eff else None


def system_verdict_for(res: dict, refs: dict | None, tol, *, fullbound_eff: dict | None = None, dimension: dict | None = None,
                       truth_noncompressible: bool | None = None, n_boot: int = 2000, seed: int = 0) -> dict:
    """PROTOCOL 9 for one system: collect_metrics + system_verdict. The full-state bound defaults to the FULL-STATE reference (the
    tournament passes the Level B-fixed bound)."""
    from .verdict import Tolerances, collect_metrics, dimension_status, system_verdict
    eff = _effects(res)
    if eff is None:
        return {"error": "no effect results", "category": "unsupported"}
    rr = (refs or {}).get("results") or {}
    idsc = _effects(rr.get("id_shortcut"))
    full = fullbound_eff if fullbound_eff is not None else _effects(rr.get("full_state"))
    it = res.get("items") or {}
    dim = dimension if dimension is not None else dimension_status(res.get("k"), res.get("compact_limit"), None,
                                                                    tuple(res["k_range"]) if res.get("k_range") else None)
    m = collect_metrics(eff, eff_idshortcut=idsc, eff_fullbound=full, mediation=res.get("mediation"), closure=res.get("closure"),
                        micro=res.get("micro"), calibration=it.get("calibration"), dimension=dim,
                        declared_no_compact=bool((res.get("abstain") or {}).get("no_compact_state")),
                        truth_noncompressible=truth_noncompressible, n_boot=n_boot, seed=seed)
    tol = tol if not isinstance(tol, dict) else Tolerances.from_dict(tol)
    v = system_verdict(m, tol, compact_judged=res.get("compact_judged", True))
    return {"metrics": public_view(m), "verdict": v}


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
        ctx = SU.SimContext(internal, store_root=job["store_root"], synthetic_system=truth_obj)
    else:
        ctx = SU.SimContext(internal, store_root=job["store_root"])
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


def references_job(job: dict) -> dict:
    """Fit and evaluate the references of one system (cached under job['ref_cache']); k = the dimension of RANDOM-k / PCA-k."""
    inputs, internal, ctx, truth_obj = system_context(job)
    if truth_obj is not None:
        attach_states(inputs["items"], ctx.store)
        from .evaluate_truth import attach_truth
        attach_truth(truth_obj, inputs["items"], inputs.get("samples"))
    with _locked(Path(job["ref_cache"]) / job["sid"].replace(":", "_") / f".lock_k{job.get('k')}"):
        refs = reference_results(job["sid"], inputs, cache_dir=job["ref_cache"], k=job.get("k"), truth_dir=inputs.get("truth_dir"),
                                 internal=internal, n_boot=int(job.get("n_boot", 2000)), seed=int(job.get("seed", 0)))
    return {"sid": job["sid"], "k": job.get("k"), "errors": refs["errors"], "references": sorted(refs["results"])}


def evaluate_job(job: dict) -> dict:
    """Evaluate one fitted model on one system: every metric family, the references (cached), the verdict and the selection values.
    job: {"sid", "method_dir", "model_path", "heldout_root", "heldout_tier", ["public_root", "public_tier"], "store_root", "ref_cache",
    ["internal_path"], ["generator": [dir, package]], ["tolerances"], ["lift"], ["n_boot"], ["seed"], ["families"], ["fit_side"],
    ["out"]}. The caller runs it in a process whose method code is guarded (`runguard.install_eval_guard`)."""
    from . import runner as RN
    from . import select as SEL
    t0 = time.time()
    inputs, internal, ctx, truth_obj = system_context(job)
    if truth_obj is not None:
        attach_states(inputs["items"], ctx.store)
    model = RN.load_model(job["method_dir"], job["model_path"])
    res = evaluate_model(model, inputs, simulate_many=simulate_many_for(ctx), truth_system=truth_obj, internal=internal,
                         lift=bool(job.get("lift", True)), n_boot=int(job.get("n_boot", 2000)), seed=int(job.get("seed", 0)),
                         families=tuple(job["families"]) if job.get("families") else None)
    k_ref = res.get("k") or 2
    with _locked(Path(job["ref_cache"]) / job["sid"].replace(":", "_") / f".lock_k{k_ref}"):
        refs = reference_results(job["sid"], inputs, cache_dir=job["ref_cache"], k=k_ref, truth_dir=inputs.get("truth_dir"),
                                 internal=internal, n_boot=int(job.get("n_boot", 2000)), seed=int(job.get("seed", 0)))
    tol, calibrated = tolerances_or_provisional(job.get("tolerances"))
    truth = dict(truth_obj.truth() or {}) if truth_obj is not None else {}
    nc = (str(truth.get("k")) == "none") if truth else None
    ver = system_verdict_for(res, refs, tol, truth_noncompressible=nc, n_boot=int(job.get("n_boot", 2000)), seed=int(job.get("seed", 0)))
    ver["tolerances_calibrated"] = calibrated
    side = json.loads(Path(job["fit_side"]).read_text(encoding="utf-8")) if job.get("fit_side") and Path(job["fit_side"]).exists() else {}
    sel = SEL.per_system_values(ver, res, truth_k=truth.get("k"), kind=internal.get("kind", "synthetic"), fit_compute=side.get("compute"))
    out = {"sid": job["sid"], "kind": internal.get("kind"), "result": res, "verdict": ver, "selection": sel,
           "reference_errors": refs["errors"], "eval_job_wall_s": round(time.time() - t0, 1)}
    if job.get("out"):
        with open(job["out"], "wb") as fh:
            pickle.dump(out, fh, protocol=pickle.HIGHEST_PROTOCOL)
        dump({k: (public_view(v) if k == "result" else v) for k, v in out.items()}, Path(job["out"]).with_suffix(".json"))
    return {"sid": job["sid"], "category": (ver.get("verdict") or {}).get("category"), "wall_s": out["eval_job_wall_s"],
            "out": job.get("out")}
