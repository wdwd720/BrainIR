"""Pre-registered calibration of the verdict tolerances (benchmarks/causal_state_v1/PROTOCOL.md section 7; review E, M3).
ORCHESTRATOR SIDE.

Runs on the synthetic DEV tier only, never on validation, confirmation or real hidden data, and never with a candidate method. On every
dev system whose truth is COMPRESSIBLE (integer k), the references of PROTOCOL section 8 (`brainir_causal.refs`) are fitted on the
system's public D0 + D1 (splits 'train' and 'twin'; finite blow-ups left out):

    TRUE-STATE (k_true), FULL-STATE, OBS-SHORTCUT (where the system defines z_obs: the trap types), RANDOM-k and PCA-k (k = k_true),
    NO-EFFECT (the FULL-STATE's passive predictions), ID-SHORTCUT,
    and, for the POWER TABLE, two corruptions of the TRUE-STATE reference: READ-IN ERROR (`refs.ReadinGainModel`: gain 0.5 on one
    trained family, the trained amplitude family with the most supported verdict items; ties by name) and MISSING STATE
    (`refs.TruthStateModel(drop=(j,))`: the true coordinate j with the largest training variance removed; k_true >= 2 only).

ITEMS. The VERDICT items (PROTOCOL 9: roles in, target, near, far, hidden) that the TRUE-STATE reference SUPPORTS (every event kind of
the item; it abstains on kinds never trained): every model is scored on this same item set, so the tolerances measure the sampling
variability of a correct state, not the reference's structural abstention; the abstention share of the true state over all verdict
items is recorded (with its class-balanced EE over all verdict items, descriptive). The metric families are those of the frozen
evaluator (E5's modules: the class-balanced verdict EE, the linear ICG_y, the MEV with its testability rules, whitened by the model's
encodings of PUBLIC training histories), assembled into verdict inputs by `verdict.collect_metrics` (the FULL-STATE reference as the
full-state bound, the ID-SHORTCUT reference as the shortcut). The references' dimension criterion F is STABLE BY CONSTRUCTION (their k
is fixed; `evaluate_stability.REFERENCE_DIMENSION`), and compact where N_obs permits: an asymmetry against methods, recorded.

TOLERANCES at a percentile p over systems (true-state reference):
    delta_A = max(0.1, P_p of (upper CI - point) of its class-balanced EE)
    delta_C = max(0.05, P_p of the UPPER CI of the paired difference EE_truestate - EE_fullstate)   (the quantity the verdict tests)
    tau_SMS = P_p of the upper CI of its SMS
    tau_ICG = P_p of the upper CI of its LINEAR ICG_y
    tau_MEV = P_p of the upper CI of its MEV over the systems where the MEV is testable
    delta_H = max(0.1, P_p of its (EE_heldout - EE_infamily), point estimates)
    tau_FC  = 0.2 (fixed)
POWER RULE (D; the ICG part of E; the MEV part of E) at the same tolerances: a criterion BINDS only if a one-sided Fisher exact test
(alpha 0.05) shows that the TRUE-STATE reference passes it more often than EACH null on the SAME systems: the OBS-SHORTCUT reference on
the trap systems (at least 6, else the power cannot be shown and the criterion does not bind) and RANDOM-k on all calibration systems.
"Passes" = the criterion's own pass flag in `verdict.system_verdict` with every criterion binding.
COMMON PERCENTILE p (`common_percentile`; binding flags fixed at p = 90): the smallest of {90, 95, 97.5, 99} for which the TRUE-STATE
reference meets every BINDING criterion jointly on at least 80 % of the calibration systems. NOT ATTAINABLE (the synthetic part of the
conclusion is then at most PARTIAL, as PROTOCOL 7 declares) when no p reaches 80 % (p = 99 is used), when a criterion binding at p =
90 has no power at the chosen p, or when D and at least one part of E do not bind (review E round 3, N-new-2: "causal state
supported" asserts mediation and closure; `verdict.mediation_closure_binding`). SUITE MARGINS (`suite_margins`, review E, N9): the
margins of the primary family's suite-level H3 / H4, from the true state's suite-level bound.
Recorded (calibration.json): the percentile table (tolerances, power and support rate at every candidate p), the chosen p, the POWER
TABLE (pass rates of D, E_icg, E_mev and E for the true state and the two corruptions, one-sided Fisher exact tests: a criterion is
declared able to detect a corruption only when the corruption fails it significantly more often), the verdict distributions of every
reference, the verdicts at BOTH CI ENDS of every tolerance (binding flags fixed), DESCRIPTIVE tolerance CIs (unstratified resampling
of the calibration systems at the chosen p), abstention shares, code hashes. Only the tolerance values and binding flags go to
`public/tolerances.json`.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import math
import time
import traceback
from pathlib import Path

import numpy as np

TOL_KEYS = ("delta_A", "delta_C", "tau_SMS", "tau_ICG", "tau_MEV", "delta_H")
BIND_KEYS = {"D": "sms_binds", "E_icg": "icg_binds", "E_mev": "mev_binds"}
REFS = ("true_state", "full_state", "obs_shortcut", "random_k", "pca_k", "no_effect", "id_shortcut")
CORRUPTIONS = ("true_state_readin", "true_state_missing")
MODELS = REFS + CORRUPTIONS
PERCENTILES = (90.0, 95.0, 97.5, 99.0)
TARGET_SUPPORTED = 0.8
FISHER_ALPHA = 0.05
MIN_TRAP_SYSTEMS = 6
TAU_FC = 0.2
N_BOOT_TAU = 2000
DELTA_A_MIN, DELTA_C_MIN, DELTA_H_MIN = 0.1, 0.05, 0.1
READIN_GAIN = 0.5
AMPLITUDE_PREFIXES = ("kick.", "pulse.", "act.", "inh.", "seq.", "edge.w", "param.")
N_WHITEN_HISTS = 64
ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / "benchmarks" / "causal_state_v1"


# ------------------------------------------------------------------------------------------------------------ data helpers
def _truth_arrays(truth_dir: Path | None, key: str) -> dict:
    if truth_dir is None:
        return {}
    p = Path(truth_dir) / "traj" / f"{key}.npz"
    if not p.exists():
        return {}
    with np.load(p) as z:
        return {k: z[k] for k in z.files}


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def system_truth_summaries(tier_root: Path, tier: str = "dev") -> dict:
    from .suites import tier_dirs
    p = tier_dirs(tier, Path(tier_root))["truth"] / "systems_truth.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def compressible(summary: dict) -> int | None:
    """k_true of a compressible system (integer k), else None."""
    k = (summary or {}).get("k")
    try:
        return int(k) if k is not None and str(k).lower() != "none" else None
    except (TypeError, ValueError):
        return None


def _get(rec, name, default=None):
    return rec.get(name, default) if isinstance(rec, dict) else getattr(rec, name, default)


def whiten_histories_from(records: list, n: int = N_WHITEN_HISTS) -> list[tuple]:
    """(x_hist, u_hist, dt) of up to n PUBLIC training histories: the harness's rule (`harness.whiten_histories`) on a list of
    training records (split 'train'; a seeded subset of n/4 records, 4 fixed fractions of each)."""
    rows = [r for r in records if _get(r, "split") == "train"]
    rng = np.random.default_rng(0)
    out = []
    pick = sorted(rng.choice(len(rows), size=min(len(rows), max(1, n // 4)), replace=False)) if rows else []
    for i in pick:
        tr = rows[int(i)]
        x, u = np.asarray(_get(tr, "x")), np.asarray(_get(tr, "u"))
        m = len(x)
        dt = float(_get(tr, "protocol")["dt"])
        for fr in (0.3, 0.45, 0.6, 0.75):
            j = int(fr * (m - 1))
            out.append((x[: j + 1], u[: j + 1], dt))
    return out[:n]


def is_verdict_item(it) -> bool:
    if hasattr(it, "is_verdict"):
        return bool(it.is_verdict())
    from .evalio import VERDICT_KINDS
    return (getattr(it, "y_twin", None) is not None) and str(it.shift).split(":", 1)[0] in VERDICT_KINDS


def supported_items(model, sid: str, items: list) -> list:
    """The items whose every event kind the model supports and whose every targeted unit it covers (the true-state reference
    abstains on kinds never trained and on units never intervened in training: `refs.*.covers`)."""
    return [it for it in items if all(model.supports(sid, e["kind"]) for e in it.events)
            and (not hasattr(model, "covers") or model.covers(sid, it.events))]


def readin_family(pub: dict, items: list) -> str | None:
    """The trained amplitude family with the most items among `items` (ties by name): the family the read-in corruption scales."""
    trained = set(((pub or {}).get("split") or {}).get("families_train") or [])
    counts: dict[str, int] = {}
    for it in items:
        f = str(it.family)
        if f in trained and f.startswith(AMPLITUDE_PREFIXES):
            counts[f] = counts.get(f, 0) + 1
    if not counts:
        return None
    return min(counts, key=lambda f: (-counts[f], f))


def missing_coordinate(truth_z: dict) -> int:
    """The true coordinate with the largest variance over the training records (ties: the lowest index)."""
    Z = np.concatenate([np.asarray(v, float) for v in truth_z.values()], axis=0)
    return int(np.argmax(np.round(Z.var(0), 12)))


# ------------------------------------------------------------------------------------------------------------ one system
def evaluate_reference(model, sysc, items: list, pool, *, whiten_hists: list, n_boot: int, seed: int, preds: dict | None = None) -> dict:
    """The metric families the tolerances and the verdict need, for one model, on `items` (predictions reused when given).
    A model with `set_phase` (an `isolation.RemoteFresh`: e.g. the locked method scored by the Level C driver through `extra_models`)
    is called in the ISOLATION PHASE ORDER of `harness.evaluate_model`: phase A = predictions, effects and calibration, the MEV
    whitener (public training histories) and the microstate (pool encodings); then set_phase("C") and the closure (encodings of TRUE
    FUTURE histories), so no future history reaches the worker before every phase-A output exists. Trusted in-process references
    (no phases) keep the order below."""
    from .evaluate import evaluate_items, predict_items
    from .evaluate_mediation import eval_closure, eval_mediation
    from .evaluate_micro import eval_microstate, latent_whitener
    set_phase = getattr(model, "set_phase", None)
    phased = callable(set_phase)

    def micro() -> dict:
        if pool is None:
            return {"testable": False, "untestable_reason": "no pool", "MEV": {"point": float("nan"), "ci95": [float("nan")] * 2}}
        w = latent_whitener(model, sysc.system_id, whiten_hists) if whiten_hists else None
        k = ((model.info() or {}).get("k") or {}).get(sysc.system_id)
        return eval_microstate(model, sysc, pool, whiten_z=w, k_model=k, n_boot=n_boot, seed=seed)
    if phased:
        set_phase("A")
    preds = preds if preds is not None else predict_items(model, sysc, items)
    ev = evaluate_items(model, sysc, items, composition=False, n_boot=n_boot, seed=seed, preds=preds)
    out = {"eff": ev["effects"], "cal": ev["calibration"]}
    out["med"] = eval_mediation(sysc, items, preds, n_boot=n_boot, seed=seed)          # predictions only: no model call
    if phased:
        out["mic"] = micro()
        set_phase("C")
        out["clo"] = eval_closure(model, sysc, items, preds, n_boot=n_boot, seed=seed)
    else:
        out["clo"] = eval_closure(model, sysc, items, preds, n_boot=n_boot, seed=seed)
        out["mic"] = micro()
    return out


def calibrate_system(sid: str, tier_root: str, tier: str = "dev", n_boot: int = 2000, seed: int = 0, learner: dict | None = None,
                     summary: dict | None = None, public_root: str | None = None, extra_models: dict | None = None) -> dict:
    """Load one dev system through `suites.load_eval_inputs` (public training records with their truth, test items, pool) and run
    `calibrate_from_inputs`. Returns a JSON-serialisable row (no arrays). `learner`: LearnerConfig overrides (tests only); `summary`:
    the system's truth summary (default: the tier's systems_truth.json); `public_root`: where the tier's PUBLIC part lives when it is
    not under tier_root (the remote-build layout: public parts on the fit volume, eval / truth on the eval volume); `extra_models`:
    passed through to `calibrate_from_inputs` (the Level C driver scores the locked method on the true state's item set)."""
    ld = _calib_load(sid, tier_root, tier, summary=summary, public_root=public_root)
    if ld.get("skipped"):
        return ld["skipped"]
    inp = ld["inp"]
    return calibrate_from_inputs(sid, pub=inp["record"], sysc=inp["system"], train=ld["train"], items=inp["items"], pool=inp["pool"],
                                 k_true=ld["k_true"], truth=ld["truth"], register=ld["registrations"](), summary=ld["summary"],
                                 n_boot=n_boot, seed=seed, learner=learner, whiten_hists=ld["whiten"], extra_models=extra_models)


def _calib_load(sid: str, tier_root: str, tier: str = "dev", *, summary: dict | None = None, public_root: str | None = None) -> dict:
    """The inputs of one dev system's calibration (`calibrate_system` and the split jobs): {"k_true", "summary", "inp", "train", "truth",
    "whiten", "registrations" (a function returning a fresh generator)}, or {"skipped": row} for a system that is not compressible."""
    from .suites import load_eval_inputs, tier_dirs
    root = Path(tier_root)
    dirs = tier_dirs(tier, root)
    summary = summary if summary is not None else system_truth_summaries(root, tier).get(sid, {})
    k_true = compressible(summary)
    if k_true is None:
        return {"skipped": {"sid": sid, "type": summary.get("type"), "k_true": None, "skipped": "not compressible", "errors": {}}}
    inp = load_eval_inputs(sid, heldout_dirs=dirs, public_dirs=tier_dirs(tier, Path(public_root)) if public_root else None)
    tdir = dirs["truth"] / sid.replace(":", "_")
    tdir = tdir if tdir.exists() else None
    pset, held = inp["public"], inp["heldout"]
    train = [pset.load(r) for r in pset.rows if r.get("split") in ("train", "twin")]
    z, zo, dr = {}, {}, {}
    for r in train:
        tr = _truth_arrays(tdir, r.key)
        if "z" in tr:
            z[r.key] = tr["z"]
        if "z_obs" in tr:
            zo[r.key] = tr["z_obs"]
        if "draw" in tr:                                  # the effective draw parameters (TRUE-STATE encodes [z, draw]; P4-D43)
            dr[r.key] = tr["draw"]
    truth = {"z": z if len(z) == len(train) else None, "z_obs": zo if len(zo) == len(train) else None,
             "draw": dr if len(dr) == len(train) else None}
    try:
        from .harness import whiten_histories
        whiten = whiten_histories(inp)
    except Exception:  # noqa: BLE001 - the same rule on the loaded training records
        whiten = whiten_histories_from(train)

    def registrations():
        for rr in held.rows:
            rec = held.load(rr)
            tr = _truth_arrays(tdir, rec.key)
            yield {"x": rec.x, "u": rec.u, "y": rec.y, "z": tr.get("z"), "z_obs": tr.get("z_obs"), "draw": tr.get("draw"),
                   "dt": float(rec.protocol["dt"])}

    return {"k_true": k_true, "summary": summary, "inp": inp, "train": train, "truth": truth, "whiten": whiten,
            "registrations": registrations}


def calibrate_from_inputs(sid: str, *, pub: dict, sysc, train: list, items: list, pool, k_true: int, truth: dict | None = None,
                          register=(), summary: dict | None = None, n_boot: int = 2000, seed: int = 0, learner: dict | None = None,
                          whiten_hists: list | None = None, refs: tuple[str, ...] = REFS, corruptions: bool = True,
                          extra_models: dict | None = None) -> dict:
    """Fit the references (and the power-table corruptions) on `train` (D0 + D1 records), register the evaluator-side truth / readouts
    of every held-out history the evaluation will encode (`register`: dicts {"x", "u", "y", "z" | None, "z_obs" | None}), score every
    model on the verdict items the TRUE-STATE reference supports (and the pool), and return the per-model verdict inputs
    (JSON-serialisable). truth: {"z": {key: (T, k)} | None, "z_obs": ... | None}; whiten_hists: PUBLIC training histories
    [(x, u, dt)] for the MEV whitening (default: the harness's rule on `train`). extra_models: {name: model or (model, dimension)}
    scored on the SAME items (review E, N5: the method's verdict on P_t's item set; its dimension criterion is the given dict, from its
    fit seeds / refits, else missing, which blocks SUPPORTED).

    EXECUTION (research/phase4/LEVEL_B_EXECUTION.md): the fitting / registration / item-set stage (`_calib_build`) and the per-model
    evaluation + assembly stage (`_calib_evaluate`) are factored out; this runs them back to back (unchanged results). A split driver can
    run them in separate jobs (fit stage per system, then the evaluation), pickling `models` between them; the two paths are bit-identical
    (`split_from_inputs`)."""
    built = _calib_build(sid, pub=pub, sysc=sysc, train=train, items=items, pool=pool, k_true=k_true, truth=truth, register=register,
                         summary=summary, learner=learner, whiten_hists=whiten_hists, refs=refs, corruptions=corruptions,
                         extra_models=extra_models)
    return _calib_evaluate(sid, sysc=sysc, pool=pool, n_boot=n_boot, seed=seed, **built)


def _calib_build(sid: str, *, pub: dict, sysc, train: list, items: list, pool, k_true: int, truth: dict | None = None, register=(),
                 summary: dict | None = None, learner: dict | None = None, whiten_hists: list | None = None,
                 refs: tuple[str, ...] = REFS, corruptions: bool = True, extra_models: dict | None = None, prefit: dict | None = None) -> dict:
    """Stage A of the calibration (module docstring; the statements of `calibrate_from_inputs` up to the evaluation loop): fit the
    references and corruptions (`_calib_fit`; or take `prefit`, the per-(system, reference) fit jobs merged by `calib_merge_fits`),
    register the held-out truth / readouts, choose the TRUE-STATE-supported item set. Returns the context the evaluation stage consumes
    ({row, models, items_s, verdict_items, whiten_hists, extra_dims, t0})."""
    from . import refs as R
    t0 = time.time()
    summary = summary or {}
    truth = truth or {}
    whiten_hists = whiten_hists if whiten_hists is not None else whiten_histories_from(train)
    verdict_items = [it for it in items if is_verdict_item(it)]
    row: dict = {"sid": sid, "type": summary.get("type"), "k_true": int(k_true), "d_draw": summary.get("d_draw"), "trap": summary.get("trap"),
                 "errors": {},
                 "has_z_obs": truth.get("z_obs") is not None, "n_train": len(train), "n_items": len(items),
                 "n_verdict_items": len(verdict_items), "n_pool": (len(pool.states) if pool is not None else 0),
                 "compact_judged": getattr(sysc, "compact_limit", None) is not None, "n_whiten_hists": len(whiten_hists)}
    fit = prefit if prefit is not None else _calib_fit(sid, pub=pub, train=train, k_true=k_true, truth=truth, learner=learner,
                                                       refs=refs, corruptions=corruptions)
    row["errors"].update(dict(fit["errors"]))
    models = dict(fit["models"])
    if fit.get("missing_coordinate") is not None:
        row["missing_coordinate"] = fit["missing_coordinate"]
    if models.get("true_state") is not None:
        # TRUE-STATE encodes [z, draw] when the truth provides the effective draw parameters (P4-D43): record whether the fitted model
        # does, and REFUSE the system when the truth has draws but the model fell back to z only (it would weaken the calibration
        # silently; E13's report, 2026-09-27). Same rule in the direct and the split path (both build here).
        try:
            dctx = bool((models["true_state"].info() or {}).get("draw_context"))
        except Exception:  # noqa: BLE001 - a model without the record: unknown, refused below only when draws exist
            dctx = None
        row["true_state_draw_context"] = dctx
        if truth.get("draw") is not None and not dctx:
            raise ValueError(f"{sid}: the truth provides draw parameters but the fitted TRUE-STATE has draw_context {dctx} (a z-only "
                             "TRUE-STATE would weaken the calibration); refusing to calibrate this system")
    for reg in register:
        for name, key in (("true_state", "z"), ("obs_shortcut", "z_obs"), ("true_state_missing", "z")):
            if name in models and reg.get(key) is not None:
                models[name].register_truth(reg["x"], reg["u"], reg[key], reg.get("dt"), draw=reg.get("draw"))
        if "id_shortcut" in models:
            models["id_shortcut"].register_readout(reg["x"], reg["u"], reg["y"])
    # the item set: verdict items the TRUE-STATE reference supports (all verdict items when there is no true-state reference)
    ts = models.get("true_state")
    items_s = supported_items(ts, sid, verdict_items) if ts is not None else list(verdict_items)
    row["n_supported_items"] = len(items_s)
    row["abstention_share"] = (1.0 - len(items_s) / len(verdict_items)) if verdict_items else None
    unsup: dict[str, int] = {}
    sup_ids = {id(it) for it in items_s}
    for it in verdict_items:
        if id(it) not in sup_ids:
            unsup[str(it.family)] = unsup.get(str(it.family), 0) + 1
    row["unsupported_families"] = unsup
    if corruptions and ts is not None:
        fam = readin_family(pub, items_s)
        if fam is not None:
            models["true_state_readin"] = R.ReadinGainModel(ts, fam, pub, gain=READIN_GAIN)
            row["readin_family"] = fam
        else:
            row["readin_family"] = "not applicable (no trained amplitude family among the supported items)"
    extra_dims: dict = {}
    for name, spec in (extra_models or {}).items():
        models[name], extra_dims[name] = spec if isinstance(spec, tuple) else (spec, None)
    return {"row": row, "models": models, "items_s": items_s, "verdict_items": verdict_items, "whiten_hists": whiten_hists,
            "extra_dims": extra_dims, "t0": t0}


def _calib_fit(sid: str, *, pub: dict, train: list, k_true: int, truth: dict | None = None, learner: dict | None = None,
               refs: tuple[str, ...] = REFS, corruptions: bool = True, only: str | None = None) -> dict:
    """The fits of one system's calibration: {"models" (the fitted references in `refs.fit_references` order, then
    "true_state_missing"), "errors", "missing_coordinate" (j, "not applicable (k = 1)" or None)}. only: ONE fit job's name (a reference
    of `refs` or "true_state_missing"; `calib_fit_job`)."""
    from . import refs as R
    truth = truth or {}
    cfg = R.LearnerConfig(**(learner or {}))
    names = tuple(refs) if only is None else ((only,) if only in refs else ())
    fitted = R.fit_references(sid, train, pub, names=names, k=int(k_true), truth=truth, cfg=cfg) if names else R.FittedRefs()
    fit = {"models": dict(fitted.models), "errors": dict(fitted.errors), "missing_coordinate": None}
    if corruptions and truth.get("z") and only in (None, "true_state_missing"):
        if int(k_true) >= 2:
            j = missing_coordinate(truth["z"])
            try:
                fit["models"]["true_state_missing"] = R.fit_reference("true_state", sid, train, pub, truth=truth, cfg=cfg, drop=(j,))
                fit["missing_coordinate"] = j
            except Exception as exc:  # noqa: BLE001
                fit["errors"]["true_state_missing"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        else:
            fit["missing_coordinate"] = "not applicable (k = 1)"
    return fit


def calib_fit_names(refs: tuple[str, ...] = REFS, corruptions: bool = True) -> list[str]:
    """The per-(system, reference) fit jobs of one system: every reference of `refs` but NO-EFFECT (the assembly wraps the FULL-STATE
    fit, as `refs.fit_references` does), plus the missing-state corruption."""
    return [n for n in refs if n != "no_effect"] + (["true_state_missing"] if corruptions else [])


def calib_fit_job(sid: str, name: str, *, pub: dict, train: list, k_true: int, truth: dict | None = None, learner: dict | None = None,
                  refs: tuple[str, ...] = REFS) -> dict:
    """ONE per-(system, reference) fit job of the split calibration: {"name", "model" (pickled, or None when the reference is skipped
    or failed), "error", "missing_coordinate"}. The fit is `_calib_fit(only=name)`: `refs.fit_references` for this one name (its skip and
    error rules unchanged), or the missing-state corruption."""
    fit = _calib_fit(sid, pub=pub, train=train, k_true=k_true, truth=truth, learner=learner, refs=refs,
                     corruptions=(name == "true_state_missing"), only=name)
    m = fit["models"].get(name)
    return {"name": name, "model": pickle.dumps(m, protocol=pickle.HIGHEST_PROTOCOL) if m is not None else None,
            "error": fit["errors"].get(name), "missing_coordinate": fit["missing_coordinate"] if name == "true_state_missing" else None}


def calib_merge_fits(sid: str, jobs: dict, *, pub: dict, train: list, k_true: int, truth: dict | None = None, learner: dict | None = None,
                     refs: tuple[str, ...] = REFS) -> dict:
    """The assembly's fit of one system from its fit jobs (`calib_fit_job` results keyed by name), in the insertion order
    `refs.fit_references` produces (the fitted references in `refs` order, NO-EFFECT wrapping the FULL-STATE fit last, then the corruption):
    the `prefit` of `_calib_build`, equal to what `_calib_fit` returns in one process."""
    from . import refs as R
    models, errors = {}, {}
    for name in refs:
        if name == "no_effect":
            continue
        j = jobs.get(name) or {}
        if j.get("model") is not None:
            models[name] = pickle.loads(j["model"])
        if j.get("error"):
            errors[name] = j["error"]
    if "no_effect" in refs:
        base = models.get("full_state")
        if base is not None:
            try:
                models["no_effect"] = R.NoEffectModel(base)          # as refs.fit_references: NO-EFFECT reuses the FULL-STATE fit
            except Exception as exc:  # noqa: BLE001
                errors["no_effect"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        else:                                                           # its own fallback (a FULL-STATE refit inside), unchanged
            fb = R.fit_references(sid, train, pub, names=("no_effect",), k=int(k_true), truth=truth or {},
                                  cfg=R.LearnerConfig(**(learner or {})))
            models.update(fb.models)
            errors.update(fb.errors)
    tm = jobs.get("true_state_missing") or {}
    if tm.get("model") is not None:
        models["true_state_missing"] = pickle.loads(tm["model"])
    if tm.get("error"):
        errors["true_state_missing"] = tm["error"]
    return {"models": models, "errors": errors, "missing_coordinate": tm.get("missing_coordinate")}


def calibrate_system_fit_job(sid: str, name: str, tier_root: str, tier: str = "dev", learner: dict | None = None,
                             summary: dict | None = None, public_root: str | None = None) -> dict:
    """Container side of one per-(system, reference) fit job (scripts/p4/calibrate.py --split, wave 1). Returns `calib_fit_job`'s
    record (the model travels back as bytes to the orchestrator, never through a volume)."""
    ld = _calib_load(sid, tier_root, tier, summary=summary, public_root=public_root)
    if ld.get("skipped"):
        return {"name": name, "skipped": True}
    return calib_fit_job(sid, name, pub=ld["inp"]["record"], train=ld["train"], k_true=ld["k_true"], truth=ld["truth"], learner=learner)


def calibrate_system_assemble(sid: str, jobs: dict, tier_root: str, tier: str = "dev", n_boot: int = 2000, seed: int = 0,
                              learner: dict | None = None, summary: dict | None = None, public_root: str | None = None,
                              extra_models: dict | None = None) -> dict:
    """Container side of one system's ASSEMBLY (scripts/p4/calibrate.py --split, wave 2): merge its fit jobs, register the held-out truth,
    choose the item set, evaluate every model and assemble the row. Bit-identical to `calibrate_system` (test_calibrate_split)."""
    ld = _calib_load(sid, tier_root, tier, summary=summary, public_root=public_root)
    if ld.get("skipped"):
        return ld["skipped"]
    inp = ld["inp"]
    prefit = calib_merge_fits(sid, jobs, pub=inp["record"], train=ld["train"], k_true=ld["k_true"], truth=ld["truth"], learner=learner)
    built = _calib_build(sid, pub=inp["record"], sysc=inp["system"], train=ld["train"], items=inp["items"], pool=inp["pool"],
                         k_true=ld["k_true"], truth=ld["truth"], register=ld["registrations"](), summary=ld["summary"], learner=learner,
                         whiten_hists=ld["whiten"], extra_models=extra_models, prefit=prefit)
    return _calib_evaluate(sid, sysc=inp["system"], pool=inp["pool"], n_boot=n_boot, seed=seed, **built)


def calibrate_system_assemble_from_file(sid: str, fits_path: str, tier_root: str, tier: str = "dev", n_boot: int = 2000, seed: int = 0,
                                        learner: dict | None = None, summary: dict | None = None, public_root: str | None = None) -> dict:
    """`calibrate_system_assemble` with the fit-job records read from a pickle file the ORCHESTRATOR wrote into the job directory (a
    "call" job's arguments are JSON, so the model bytes travel as a job input file; the file holds trusted reference models only)."""
    with open(fits_path, "rb") as fh:
        jobs = pickle.load(fh)
    return calibrate_system_assemble(sid, jobs, tier_root, tier, n_boot=n_boot, seed=seed, learner=learner, summary=summary,
                                     public_root=public_root)


def _calib_evaluate(sid: str, *, sysc, pool, n_boot: int, seed: int, row: dict, models: dict, items_s: list, verdict_items: list,
                    whiten_hists: list, extra_dims: dict, t0: float) -> dict:
    """Stage B of the calibration (module docstring; the evaluation loop and row assembly of `calibrate_from_inputs`): score every model
    on the TRUE-STATE-supported item set and the pool, assemble the per-model verdict inputs. Returns the JSON-serialisable row."""
    from .evaluate import predict_items
    from .evaluate_stability import REFERENCE_DIMENSION
    from .verdict import collect_metrics
    ev: dict = {}
    for name, m in models.items():
        try:
            preds = None
            if name == "true_state":
                # predictions on EVERY verdict item (reused on the supported ones): the descriptive EE with abstention
                preds = predict_items(m, sysc, verdict_items)
                from .evaluate import evaluate_items
                allv = evaluate_items(m, sysc, verdict_items, composition=False, n_boot=n_boot, seed=seed, preds=preds)["effects"]
                row["true_state_all_verdict_items"] = {"EE_cb": _jsonable(allv.get("EE_cb_medium") or allv.get("EE_medium")),
                                                       "n_items": allv.get("n_items"), "n_abstained": allv.get("n_abstained")}
            ev[name] = evaluate_reference(m, sysc, items_s, pool, whiten_hists=whiten_hists, n_boot=n_boot, seed=seed, preds=preds)
        except Exception as exc:  # noqa: BLE001
            row["errors"][name] = f"evaluation: {type(exc).__name__}: {str(exc)[:300]}"
            row.setdefault("tracebacks", {})[name] = traceback.format_exc()[-3000:]
    from .verdict import compact_limit_given_truth
    compact_limit, compact_note = compact_limit_given_truth(getattr(sysc, "compact_limit", None), getattr(sysc, "kind", None),
                                                            row.get("k_true"), row.get("d_draw"))
    if compact_note:
        row["compact_note"] = compact_note
    for name, e in ev.items():
        mk = ((models[name].info() or {}).get("k") or {}).get(sid) if name != "no_effect" else None
        compact = None if compact_limit is None or mk is None else bool(mk <= compact_limit)
        if name in extra_dims:
            dim = extra_dims[name] or {"k": mk, "compact": compact, "stable": None, "note": "dimension criterion not given: missing"}
        else:
            dim = {"k": mk, "compact": compact, **REFERENCE_DIMENSION}
        m = collect_metrics(e["eff"], eff_idshortcut=(ev["id_shortcut"]["eff"] if "id_shortcut" in ev and name != "id_shortcut" else None),
                            eff_fullbound=(ev["full_state"]["eff"] if "full_state" in ev and name != "full_state" else None),
                            mediation=e["med"], closure=e["clo"], micro=e["mic"], calibration=e["cal"], dimension=dim,
                            n_boot=n_boot, seed=seed)
        row[name] = {"verdict_inputs": _jsonable(m), "k": mk, "n_items": e["eff"].get("n_items"), "n_abstained": e["eff"].get("n_abstained"),
                     "n_failed": e["eff"].get("n_failed"), "EE_pooled": _jsonable(e["eff"].get("EE_medium")),
                     "ICG_regressor": (e["clo"].get("ICG_y") or {}).get("regressor"),
                     "MEV_untestable_reason": e["mic"].get("untestable_reason"),
                     "info": _jsonable({k: v for k, v in (models[name].info() or {}).items()
                                        if k in ("train_cost", "fit_notes", "n_probe_encodes", "corrupted_family", "dropped_true_coordinates")})}
    row["seconds"] = round(time.time() - t0, 1)
    return _jsonable(row)


def split_from_inputs(sid: str, *, pub: dict, sysc, train: list, items: list, pool, k_true: int, truth: dict | None = None,
                      register=(), summary: dict | None = None, n_boot: int = 2000, seed: int = 0, learner: dict | None = None,
                      whiten_hists: list | None = None, refs: tuple[str, ...] = REFS, corruptions: bool = True,
                      extra_models: dict | None = None) -> dict:
    """The SPLIT calibration of one system in one process (research/phase4/LEVEL_B_EXECUTION.md): every per-(system, reference) fit
    job (`calib_fit_names`) fitted ALONE and returned PICKLED (`calib_fit_job`: the boundary a fit job crosses on Modal), merged
    (`calib_merge_fits`) and assembled (`_calib_build(prefit=...)` + `_calib_evaluate`). Bit-identical to `calibrate_from_inputs` except
    the timing fields (`test_calibrate_split`)."""
    jobs = {name: calib_fit_job(sid, name, pub=pub, train=train, k_true=k_true, truth=truth, learner=learner, refs=refs)
            for name in calib_fit_names(refs, corruptions)}
    prefit = calib_merge_fits(sid, jobs, pub=pub, train=train, k_true=k_true, truth=truth, learner=learner, refs=refs)
    built = _calib_build(sid, pub=pub, sysc=sysc, train=train, items=items, pool=pool, k_true=k_true, truth=truth, register=register,
                         summary=summary, learner=learner, whiten_hists=whiten_hists, refs=refs, corruptions=corruptions,
                         extra_models=extra_models, prefit=prefit)
    return _calib_evaluate(sid, sysc=sysc, pool=pool, n_boot=n_boot, seed=seed, **built)


# ------------------------------------------------------------------------------------------------------------ tolerances
def _upper(e) -> float:
    try:
        v = float((e or {})["ci95"][1])
    except (TypeError, KeyError, IndexError, ValueError):
        return float("nan")
    return v


def _point(e) -> float:
    try:
        return float((e or {})["point"])
    except (TypeError, KeyError, ValueError):
        return float("nan")


def _pct(vals, p: float) -> float:
    v = np.asarray([x for x in vals if x is not None and np.isfinite(x)], float)
    return float(np.percentile(v, p)) if len(v) else float("nan")


def _vi(row: dict, model: str) -> dict | None:
    return (row.get(model) or {}).get("verdict_inputs")


def tolerance_rule(rows: list[dict], p: float = 90.0) -> dict:
    """The tolerances of PROTOCOL section 7 at percentile p, from the true-state reference's verdict inputs."""
    ms = [m for m in (_vi(r, "true_state") for r in rows) if m]
    ee_w = [_upper(m.get("EE")) - _point(m.get("EE")) for m in ms]
    c_up = [_upper(m.get("EE_vs_fullbound")) for m in ms]
    sms = [_upper(m.get("SMS")) for m in ms]
    icg = [_upper(m.get("ICG_y")) for m in ms]
    mev = [_upper(m.get("MEV")) for m in ms if m.get("MEV_testable")]
    hgap = [_point(m.get("EE_heldout")) - _point(m.get("EE_infamily")) for m in ms]

    def floor(v, lo):
        return max(lo, v) if np.isfinite(v) else lo

    return {"delta_A": floor(_pct(ee_w, p), DELTA_A_MIN), "delta_C": floor(_pct(c_up, p), DELTA_C_MIN), "tau_SMS": _pct(sms, p),
            "tau_ICG": _pct(icg, p), "tau_MEV": _pct(mev, p), "delta_H": floor(_pct(hgap, p), DELTA_H_MIN), "tau_FC": TAU_FC}


def _verdict(m: dict, tol: dict, compact_judged: bool) -> dict:
    from .verdict import Tolerances, system_verdict
    T = Tolerances.from_dict(tol)
    for k, v in tol.items():                   # binding flags the verdict module may not declare yet (e.g. mev_binds)
        if k not in T.__dataclass_fields__:
            setattr(T, k, v)
    return system_verdict(m, T, compact_judged=compact_judged)


def pass_flags(m: dict, tol: dict, compact_judged: bool = True) -> dict:
    """Pass flags of the power-rule criteria with every criterion binding: D, the ICG part of E, the MEV part of E, and E jointly
    (None counted as not passed)."""
    t = dict(tol, sms_binds=True, icg_binds=True, mev_binds=True)
    c = _verdict(m, t, compact_judged)["criteria"]
    e = c.get("E") or {}
    return {"D": bool((c.get("D") or {}).get("pass") is True), "E_icg": bool(e.get("icg_pass") is True),
            "E_mev": bool(e.get("mev_pass") is True), "E": bool(e.get("pass") is True)}


def fisher_greater(a_pass: int, a_n: int, b_pass: int, b_n: int) -> float:
    """One-sided Fisher exact p-value that group a passes more often than group b."""
    from scipy.stats import fisher_exact
    if a_n == 0 or b_n == 0:
        return 1.0
    return float(fisher_exact([[a_pass, a_n - a_pass], [b_pass, b_n - b_pass]], alternative="greater").pvalue)


def _compare(rows: list[dict], a: str, b: str, tol: dict, crits=("D", "E_icg", "E_mev", "E")) -> dict:
    """Pass counts of models a and b on the SAME systems (both present) and the one-sided Fisher test per criterion."""
    both = [r for r in rows if _vi(r, a) and _vi(r, b)]
    out: dict = {"n_systems": len(both)}
    fa = [pass_flags(_vi(r, a), tol, r.get("compact_judged", True)) for r in both]
    fb = [pass_flags(_vi(r, b), tol, r.get("compact_judged", True)) for r in both]
    for c in crits:
        pa, pb = sum(f[c] for f in fa), sum(f[c] for f in fb)
        pv = fisher_greater(pa, len(both), pb, len(both))
        out[c] = {"pass_a": int(pa), "pass_b": int(pb), "rate_a": pa / len(both) if both else None, "rate_b": pb / len(both) if both else None,
                  "p_fisher": pv, "significant": bool(both and pv < FISHER_ALPHA)}
    return out


def power_rule(rows: list[dict], tol: dict) -> dict:
    """PROTOCOL 7: a criterion (D, E_icg, E_mev) binds only if the true state passes it significantly more often (one-sided Fisher
    exact, alpha 0.05) than the OBS-SHORTCUT reference on the trap systems (at least 6) AND than RANDOM-k on all systems."""
    obs = _compare(rows, "true_state", "obs_shortcut", tol)
    rnd = _compare(rows, "true_state", "random_k", tol)
    out: dict = {"obs_shortcut": obs, "random_k": rnd, "min_trap_systems": MIN_TRAP_SYSTEMS, "alpha": FISHER_ALPHA}
    for c, flag in BIND_KEYS.items():
        enough = obs["n_systems"] >= MIN_TRAP_SYSTEMS
        out[flag] = bool(enough and obs[c]["significant"] and rnd[c]["significant"])
        out[f"{c}_reason"] = ("binding" if out[flag] else
                              f"fewer than {MIN_TRAP_SYSTEMS} trap systems ({obs['n_systems']})" if not enough else
                              "no significant excess over the observational shortcut" if not obs[c]["significant"] else
                              "no significant excess over random-k")
    return out


def judge(rows: list[dict], tol: dict, models=MODELS) -> dict:
    """Verdict category counts per model under tolerances tol (with its binding flags)."""
    out = {}
    for name in models:
        counts: dict[str, int] = {}
        for r in rows:
            m = _vi(r, name)
            if not m:
                continue
            v = _verdict(m, tol, r.get("compact_judged", True))["category"]
            counts[v] = counts.get(v, 0) + 1
        if counts:
            out[name] = counts
    return out


def supported_rate(rows: list[dict], tol: dict) -> tuple[float, int]:
    """Fraction of calibration systems on which the TRUE-STATE reference meets EVERY BINDING criterion jointly (`system_verdict`'s
    all_binding_criteria_hold: the category CAUSAL STATE SUPPORTED whenever the flags include a binding mediation / closure criterion;
    without one the category cannot be issued, and `common_percentile` declares the calibration not attainable, review E, N-new-2)."""
    hold = [bool(_verdict(_vi(r, "true_state"), tol, r.get("compact_judged", True)).get("all_binding_criteria_hold"))
            for r in rows if _vi(r, "true_state")]
    return (float(np.mean(hold)) if hold else float("nan")), len(hold)


def true_state_categories(rows: list[dict], tol: dict) -> dict[str, str]:
    """{system: category} of the TRUE-STATE reference under tolerances `tol` (values and binding flags), from calibration-style rows
    (`calibrate_system` / `calibrate_from_inputs` on any tier: the reference is evaluated on the verdict items IT SUPPORTS). This is the
    ONE item-set definition of the true state's verdict (review E, N5): the calibration's 80 % target and the conclusion's P_t
    (`verdict.phase4_conclusion`, syn["truestate"]) both use it. A row without a true-state reference gives no entry (the conclusion
    charges it)."""
    return model_categories(rows, tol, "true_state")


def model_categories(rows: list[dict], tol: dict, model: str) -> dict[str, str]:
    """{system: category} of `model` under tolerances `tol` from calibration-style rows: a reference, or an extra model scored by
    `calibrate_from_inputs(extra_models=...)` (the method at Level C). Every model of a row is scored on the SAME item set (the verdict
    items the true-state reference supports), so these are the method's verdicts on P_t's item set (review E, N5:
    `verdict.phase4_conclusion` syn["method_same_items"])."""
    out = {}
    for r in rows:
        m = _vi(r, model)
        if m and not r.get("skipped"):
            out[str(r["sid"])] = _verdict(m, tol, r.get("compact_judged", True))["category"]
    return out


BASE_PERCENTILE = 90.0          # the binding flags are decided ONCE, at this percentile (review E, N4)


def calibrate_at(rows: list[dict], p: float, binds: dict | None = None) -> dict:
    """Tolerances, the power rule (at p's tolerances, recorded) and the true state's support rate at percentile p. binds: the binding
    flags to judge with (fixed at BASE_PERCENTILE by `common_percentile`); None = the power rule's own flags at p (the base itself)."""
    tol = tolerance_rule(rows, p)
    pw = power_rule(rows, tol)
    flags = {flag: pw[flag] for flag in BIND_KEYS.values()} if binds is None else {flag: bool(binds[flag]) for flag in BIND_KEYS.values()}
    tol.update(flags)
    rate, n = supported_rate(rows, tol)
    return {"p": p, "tolerances": tol, "power": pw, "power_flags_at_p": {flag: pw[flag] for flag in BIND_KEYS.values()},
            "true_state_supported_rate": rate, "n_systems": n}


def common_percentile(rows: list[dict], percentiles=PERCENTILES, target: float = TARGET_SUPPORTED,
                      base: float = BASE_PERCENTILE) -> dict:
    """PROTOCOL 7 (review E, N4). The BINDING FLAGS are decided once, by the power rule at the base percentile (p = 90), and stay fixed
    at every candidate p: raising p only loosens the tolerances, so the support rate can rise only because the true state passes,
    never because a criterion stopped binding. The chosen p = the smallest p in `percentiles` whose tolerances (with the fixed flags)
    make the true state SUPPORTED on >= target of the systems. ATTAINABLE requires in addition that every criterion binding at the base
    still has POWER at the chosen p (the power rule re-run at the chosen p's tolerances still finds the true state passing significantly
    more often than each null); if a criterion binding at the base loses its power at the chosen p, or no p reaches the target, the
    calibration is NOT ATTAINABLE (the largest p is used when no p reaches the target) and the synthetic part of the conclusion is at
    most PARTIAL. MEDIATION / CLOSURE (review E round 3, N-new-2): the calibration is also NOT ATTAINABLE unless the fixed flags make D
    bind AND at least one part of E (ICG or MEV) bind (`verdict.mediation_closure_binding`): "causal state supported" asserts both, so
    without them no system can be SUPPORTED (the per-system rule) and the synthetic part is at most PARTIAL. The flags the power rule
    gives at every p and the reason of the choice are recorded."""
    from .verdict import mediation_closure_binding
    base_row = calibrate_at(rows, base)
    fixed = {flag: bool(base_row["power_flags_at_p"][flag]) for flag in BIND_KEYS.values()}
    table = [calibrate_at(rows, p, fixed) for p in percentiles]
    reach = [t for t in table if np.isfinite(t["true_state_supported_rate"]) and t["true_state_supported_rate"] >= target - 1e-12]
    chosen = reach[0] if reach else table[-1]
    lost = sorted(flag for flag, b in fixed.items() if b and not chosen["power_flags_at_p"][flag])
    from types import SimpleNamespace
    mc = mediation_closure_binding(SimpleNamespace(**fixed))
    attainable = bool(reach) and not lost and mc
    if not mc:
        note = (f"no binding MEDIATION and CLOSURE criterion at p = {base:g} (D binds: {fixed['sms_binds']}, E_icg: "
                f"{fixed['icg_binds']}, E_mev: {fixed['mev_binds']}; SUPPORTED needs D and at least one part of E): the verdict "
                "'causal state supported' cannot be issued; not attainable, the synthetic part of the conclusion can be at most "
                "PARTIAL (PROTOCOL 7; review E, N-new-2)")
    elif not reach:
        note = (f"the true-state reference is CAUSAL STATE SUPPORTED on fewer than {target:.0%} of the calibration systems even at "
                f"p = {percentiles[-1]:g} (binding flags fixed at p = {base:g}): the full verdict is not attainable for the true state "
                "with a generic learner; the synthetic part of the conclusion can be at most PARTIAL (PROTOCOL 7)")
    elif lost:
        one = len(lost) == 1
        note = (f"the target is reached at p = {chosen['p']:g}, but {', '.join(lost)} (binding at p = {base:g}) {'has' if one else 'have'} "
                f"no power at that p's tolerances (the nulls pass {'it' if one else 'them'} about as often as the true state): not "
                "attainable with powerful criteria; the synthetic part of the conclusion can be at most PARTIAL (PROTOCOL 7)")
    else:
        note = None
    return {"chosen": chosen, "attainable": attainable, "target": target, "percentiles": list(percentiles), "base_percentile": base,
            "binding_flags_fixed_at_base": fixed, "binding_lost_at_chosen": lost, "mediation_closure_binding": mc,
            "table": [{"p": t["p"], "tolerances": t["tolerances"], "true_state_supported_rate": t["true_state_supported_rate"],
                       "binds": fixed, "power_flags_at_p": t["power_flags_at_p"]} for t in table],
            "reason": (f"smallest p reaching {target:.0%} with the flags of p = {base:g}" if reach else "no p reaches the target"),
            "note": note}


def tolerance_cis(rows: list[dict], p: float, n_boot: int = N_BOOT_TAU, seed: int = 0) -> dict:
    """DESCRIPTIVE 95 % CIs of the tolerances at percentile p: unstratified resampling of the calibration systems."""
    rng = np.random.default_rng(seed)
    boot = {k: [] for k in TOL_KEYS}
    for _ in range(n_boot):
        t = tolerance_rule([rows[i] for i in rng.integers(0, len(rows), len(rows))], p)
        for k in TOL_KEYS:
            boot[k].append(t[k])
    out = {}
    for k, v in boot.items():
        a = np.asarray(v, float)
        a = a[np.isfinite(a)]
        out[k] = [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))] if len(a) else [float("nan")] * 2
    return out


def suite_margins(rows: list[dict], p: float, n_suite: int | None = None, n_outer: int = N_BOOT_TAU, seed: int = 0,
                  alpha: float = 0.05) -> dict:
    """The SUITE-level margins of the primary family (PROTOCOL 11; review E, N9), the analogue of the per-system rule at the level of a
    MEAN over systems: for H4 (mean SMS) and H3 (mean EE_M - EE_FB), the p-th percentile, over n_outer suites of n_suite systems drawn
    with replacement from the calibration systems, of the TRUE-STATE reference's one-sided (1 - alpha) upper bound of its suite MEAN
    (mean + t_{1-alpha, n-1} sd / sqrt(n), the bound the suite test computes). So the true state itself would reject H0 on about p %
    of confirmation-sized suites, exactly as the per-system tolerances let it pass D / C on p % of systems; a percentile of per-system
    upper bounds (tau_SMS, delta_C) is a lenient boundary for a mean. delta_C_suite keeps the floor DELTA_C_MIN. SMS values of a
    failed SMS (unusable items) are left out and counted. n_suite: the number of compressible confirmation systems (default: the
    calibration systems)."""
    from scipy.stats import t as tdist
    ms = [m for m in (_vi(r, "true_state") for r in rows) if m]
    sms = np.array([_point(m.get("SMS")) for m in ms if not (m.get("SMS") or {}).get("failed")], float)
    cdf = np.array([_point(m.get("EE_vs_fullbound")) for m in ms], float)
    n = int(n_suite) if n_suite else len(ms)
    rng = np.random.default_rng(seed)

    def margin(vals: np.ndarray, floor: float | None) -> float:
        v = vals[np.isfinite(vals)]
        if len(v) < 2 or n < 2:
            return float("nan")
        q = float(tdist.ppf(1.0 - alpha, n - 1))
        S_ = v[rng.integers(0, len(v), size=(n_outer, n))]
        bounds = S_.mean(1) + q * S_.std(1, ddof=1) / math.sqrt(n)
        m = float(np.percentile(bounds, p))
        return max(floor, m) if floor is not None else m
    return {"p": p, "n_suite": n, "alpha": alpha, "tau_SMS_suite": margin(sms, None), "delta_C_suite": margin(cdf, DELTA_C_MIN),
            "n_systems": len(ms), "n_sms_failed_left_out": int(len(ms) - len(sms)),
            "true_state_mean_SMS": float(np.nanmean(sms)) if len(sms) else float("nan"),
            "true_state_mean_EE_minus_FB": float(np.nanmean(cdf)) if len(cdf) else float("nan"),
            "rule": "P_p over resampled suites of the true state's one-sided upper bound of its suite mean (review E, N9)"}


def power_table(rows: list[dict], tol: dict) -> dict:
    """PROTOCOL 7 POWER TABLE: pass rates of D, E_icg, E_mev and E for the true state and each corruption on the same systems; a
    criterion is declared able to detect a corruption only when the corruption fails it significantly more often (one-sided Fisher
    exact, alpha 0.05)."""
    out: dict = {}
    for cor in CORRUPTIONS:
        cmp = _compare(rows, "true_state", cor, tol)
        if cmp["n_systems"] == 0:
            out[cor] = {"n_systems": 0, "note": "corruption not fitted on any system"}
            continue
        out[cor] = {**cmp, "detects": {c: cmp[c]["significant"] for c in ("D", "E_icg", "E_mev", "E")}}
    return out


def calibrate_rows(rows: list[dict], n_boot: int = N_BOOT_TAU, seed: int = 0, n_suite: int | None = None) -> dict:
    """Everything calibration.json records, from the per-system rows (compressible systems with a true-state reference); n_suite: the
    number of compressible confirmation systems, for the suite margins (default: the calibration systems)."""
    ok = [r for r in rows if not r.get("skipped") and _vi(r, "true_state")]
    cp = common_percentile(ok)
    ch = cp["chosen"]
    tol = dict(ch["tolerances"])
    ci = tolerance_cis(ok, ch["p"], n_boot, seed)
    sens = {}
    for key in TOL_KEYS:
        for end, val in zip(("low", "high"), ci[key]):
            if np.isfinite(val):
                sens[f"{key}_{end}"] = judge(ok, dict(tol, **{key: val}))
    abst = [r.get("abstention_share") for r in ok if r.get("abstention_share") is not None]
    from .evaluate_stability import REFERENCE_DIMENSION
    fixed = cp["binding_flags_fixed_at_base"]
    power = {**{k: v for k, v in ch["power"].items() if k not in fixed}, **fixed,
             "flags_decided_at_percentile": cp["base_percentile"], "power_flags_at_chosen_p": ch["power_flags_at_p"],
             "binding_lost_at_chosen": cp["binding_lost_at_chosen"], "mediation_closure_binding": cp["mediation_closure_binding"]}
    return {"tolerances": tol, "percentile": {k: v for k, v in cp.items() if k != "chosen"} | {"chosen_p": ch["p"]},
            "attainable": cp["attainable"], "power_rule": power, "true_state_supported_rate": ch["true_state_supported_rate"],
            "suite_margins": suite_margins(ok, ch["p"], n_suite=n_suite, seed=seed),
            "tolerances_ci95_over_systems": ci, "tolerance_ci_note": "descriptive: unstratified resampling of the calibration systems",
            "verdicts_under_calibrated_tolerances": judge(ok, tol), "verdicts_at_tolerance_ci_ends": sens,
            "power_table": power_table(ok, tol), "abstention": {"mean_share": float(np.mean(abst)) if abst else None,
                                                                "per_system": {r["sid"]: r.get("abstention_share") for r in ok}},
            "reference_dimension": REFERENCE_DIMENSION, "n_systems": len(ok),
            "n_trap_systems": int(sum(1 for r in ok if _vi(r, "obs_shortcut")))}


def mde_paired(diffs_by_system: dict[str, float], alpha: float = 0.05, power: float = 0.8, one_sided: bool = True) -> dict:
    """Minimum detectable mean paired difference (normal approximation) for n systems with the dev-suite standard deviation of the
    paired differences: (z_{1-alpha} + z_{power}) x sd / sqrt(n). A one-budget approximation (review E, M4: the active-design success
    rule's MDE is computed by simulation elsewhere)."""
    from scipy.stats import norm
    d = np.asarray([v for v in diffs_by_system.values() if v is not None and np.isfinite(v)], float)
    if len(d) < 3:
        return {"n": len(d), "mde": float("nan")}
    za = norm.ppf(1 - alpha if one_sided else 1 - alpha / 2)
    zb = norm.ppf(power)
    sd = float(d.std(ddof=1))
    return {"n": len(d), "sd": sd, "mde": float((za + zb) * sd / math.sqrt(len(d))), "alpha": alpha, "power": power,
            "one_sided": one_sided}


def code_hashes() -> dict:
    files = ("calibrate.py", "refs.py", "evaluate.py", "evaluate_mediation.py", "evaluate_micro.py", "verdict.py", "evalio.py", "stats.py",
             "fresh.py", "suites.py", "evaluate_stability.py")
    here = Path(__file__).resolve().parent
    return {f: hashlib.sha256((here / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for f in files if (here / f).exists()}


def write_outputs(rec: dict, out: Path | None = None) -> None:
    """calibration.json (full record) and public/tolerances.json (values and binding flags only)."""
    target = Path(out) if out else BENCH / "calibration.json"
    target.write_text(json.dumps(_jsonable(rec), indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    if out is None:
        (BENCH / "public").mkdir(parents=True, exist_ok=True)
        (BENCH / "public" / "tolerances.json").write_text(json.dumps(_jsonable(rec["tolerances"]), indent=1) + "\n", encoding="utf-8",
                                                           newline="\n")


# ------------------------------------------------------------------------------------------------------------ diagnostics
def reference_breakdown(sid: str, tier_root: str, tier: str = "dev", public_root: str | None = None,
                        refs: tuple[str, ...] = ("true_state", "full_state", "no_effect", "id_shortcut"), n_boot: int = 200) -> dict:
    """DESCRIPTIVE diagnostic (dev tier only, orchestrator side): the references' EE on EVERY verdict item of one dev system with the
    5.1 breakdowns (family, shift kind, magnitude class, detectability; pooled ratio of sums per group, with the number of capped
    items), plus the training data's family counts. Used to understand the calibration; never an input to it."""
    from . import refs as R
    from .evaluate import evaluate_items
    from .suites import load_eval_inputs, tier_dirs
    root = Path(tier_root)
    dirs = tier_dirs(tier, root)
    summary = system_truth_summaries(root, tier).get(sid, {})
    k_true = compressible(summary)
    inp = load_eval_inputs(sid, heldout_dirs=dirs, public_dirs=tier_dirs(tier, Path(public_root)) if public_root else None)
    tdir = dirs["truth"] / sid.replace(":", "_")
    tdir = tdir if tdir.exists() else None
    pset, held = inp["public"], inp["heldout"]
    train = [pset.load(r) for r in pset.rows if r.get("split") in ("train", "twin")]
    z = {r.key: _truth_arrays(tdir, r.key).get("z") for r in train}
    dr = {r.key: _truth_arrays(tdir, r.key).get("draw") for r in train}
    truth = {"z": z if all(v is not None for v in z.values()) else None, "z_obs": None,
             "draw": dr if all(v is not None for v in dr.values()) else None}
    fam_train: dict[str, int] = {}
    for r in train:
        fam_train[str(r.family)] = fam_train.get(str(r.family), 0) + 1
    fitted = R.fit_references(sid, train, inp["record"], names=tuple(n for n in refs if n != "true_state" or truth["z"] is not None),
                              k=int(k_true or 2), truth=truth, cfg=R.LearnerConfig())
    models = dict(fitted.models)
    for rr in held.rows:
        rec = held.load(rr)
        tr = _truth_arrays(tdir, rec.key)
        if "true_state" in models and tr.get("z") is not None:
            models["true_state"].register_truth(rec.x, rec.u, tr["z"], float(rec.protocol["dt"]), draw=tr.get("draw"))
        if "id_shortcut" in models:
            models["id_shortcut"].register_readout(rec.x, rec.u, rec.y)
    verdict_items = [it for it in inp["items"] if is_verdict_item(it)]
    out = {"sid": sid, "type": summary.get("type"), "k_true": k_true, "n_train": len(train), "train_families": fam_train,
           "n_verdict_items": len(verdict_items), "fit_errors": dict(fitted.errors), "models": {}}
    keep = ("by_family", "by_shift_kind", "by_magnitude_class", "by_detectability")
    for name, m in models.items():
        try:
            eff = evaluate_items(m, inp["system"], verdict_items, composition=False, n_boot=n_boot, seed=0)["effects"]
            out["models"][name] = {"EE_cb_medium": eff.get("EE_cb_medium"), "EE_medium": eff.get("EE_medium"),
                                   "n_abstained": eff.get("n_abstained"), "sign_accuracy": eff.get("sign_accuracy"),
                                   **{k: {g: {"EE": v.get("point"), "n": v.get("n_items"), "capped": v.get("n_capped"),
                                              "abstained": v.get("n_abstained")} for g, v in (eff.get(k) or {}).items()} for k in keep}}
        except Exception as exc:  # noqa: BLE001 - a diagnostic reports, never raises
            out["models"][name] = {"error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    return json.loads(json.dumps(out, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
