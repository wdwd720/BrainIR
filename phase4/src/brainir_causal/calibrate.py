"""Pre-registered calibration of the verdict tolerances (benchmarks/causal_state_v1/PROTOCOL.md section 7). ORCHESTRATOR SIDE.

Runs on the synthetic DEV tier only, never on validation, confirmation or real hidden data, and never with a candidate method. On every
dev system whose truth is COMPRESSIBLE (integer k), the references of PROTOCOL section 8 (`brainir_causal.refs`) are fitted on the
system's public D0 + D1 (splits 'train' and 'twin'; finite blow-ups left out) and scored by the frozen evaluator on the system's test
items and pool (`suites.load_eval_inputs`; `evaluate.evaluate_items`, `evaluate_mediation.eval_mediation` / `eval_closure`,
`evaluate_micro.eval_microstate`):

    TRUE-STATE (k_true), FULL-STATE, OBS-SHORTCUT (where the system defines z_obs: the trap types), RANDOM-k and PCA-k (k = k_true),
    NO-EFFECT (the FULL-STATE's passive predictions), ID-SHORTCUT.

Tolerances (PROTOCOL section 7; percentiles over the calibration systems, each with a 95 % CI by resampling the systems, 2,000 draws):
    delta_A = max(0.1, P90 of (upper CI - point) of the TRUE-STATE EE)
    delta_C = max(0.05, P90 of (EE_TRUE-STATE - EE_FULL-STATE))           (point estimates)
    tau_SMS = P90 of the upper CI of the TRUE-STATE SMS
    tau_ICG = P90 of the upper CI of the TRUE-STATE ICG_y
    tau_MEV = P90 of the upper CI of the TRUE-STATE MEV, over the systems where its MEV is testable
    delta_H = max(0.1, P90 of (EE_heldout - EE_infamily) of the TRUE-STATE (points))
    tau_FC  = 0.2 (fixed)
POWER RULE (SMS and ICG; the reading of "the nulls fail it on >= 20 percentage points more systems than the true-state reference
passes"): a criterion BINDS only if pass_rate(TRUE-STATE) - pass_rate(null) >= 0.20, where "pass" = upper CI <= tau, for the null
OBS-SHORTCUT (on the trap systems, where it exists) AND for the null RANDOM-k (on all systems). A missing null (no trap system, no fit)
means the power cannot be established: the criterion is then reported, not binding (conservative). The binding flags are part of
`public/tolerances.json` (`sms_binds`, `icg_binds`, the fields of `verdict.Tolerances`).

Also recorded: per-system reference quantities; the verdict distributions of every reference under the calibrated tolerances
(`verdict.system_verdict`, with the FULL-STATE reference as the full-state bound and the ID-SHORTCUT reference as the shortcut; the
references' dimension is fixed by construction, so F is taken as stable, and compact where N_obs permits); the TRUE-STATE verdicts at
both CI ends of every tolerance (sensitivity); pass-rate tables; the minimum detectable paired effect helper for the active-design
comparison (`mde_paired`); code hashes. Only the tolerance values go to `public/tolerances.json`.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import traceback
from pathlib import Path

import numpy as np

TOL_KEYS = ("delta_A", "delta_C", "tau_SMS", "tau_ICG", "tau_MEV", "delta_H")
REFS = ("true_state", "full_state", "obs_shortcut", "random_k", "pca_k", "no_effect", "id_shortcut")
VERDICT_REFS = ("true_state", "full_state", "obs_shortcut", "random_k", "pca_k", "no_effect", "id_shortcut")
POWER_MIN = 0.20
TAU_FC = 0.2
N_BOOT_TAU = 2000
DELTA_A_MIN, DELTA_C_MIN, DELTA_H_MIN = 0.1, 0.05, 0.1
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


def _est(d: dict | None) -> dict | None:
    if not d or "point" not in d:
        return None
    return {"point": float(d["point"]), "ci95": [float(d["ci95"][0]), float(d["ci95"][1])]}


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


# ------------------------------------------------------------------------------------------------------------ one system
def evaluate_reference(model, sysc, items: list, pool, *, n_boot: int, seed: int) -> dict:
    """The metric families the tolerances and the verdict need, for one reference model."""
    from .evaluate import evaluate_items
    from .evaluate_mediation import eval_closure, eval_mediation
    from .evaluate_micro import eval_microstate
    ev = evaluate_items(model, sysc, items, composition=False, n_boot=n_boot, seed=seed)
    preds = ev["_preds"]
    out = {"eff": ev["effects"], "cal": ev["calibration"]}
    out["med"] = eval_mediation(sysc, items, preds, n_boot=n_boot, seed=seed)
    out["clo"] = eval_closure(model, sysc, items, preds, n_boot=n_boot, seed=seed)
    out["mic"] = (eval_microstate(model, sysc, pool, n_boot=n_boot, seed=seed) if pool is not None
                  else {"testable": False, "untestable_reason": "no pool", "MEV": {"point": float("nan"), "ci95": [float("nan")] * 2}})
    return out


def calibrate_system(sid: str, tier_root: str, tier: str = "dev", n_boot: int = 2000, seed: int = 0, learner: dict | None = None,
                     summary: dict | None = None) -> dict:
    """Load one dev system through `suites.load_eval_inputs` (public training records with their truth, test items, pool) and run
    `calibrate_from_inputs`. Returns a JSON-serialisable row (no arrays). `learner`: LearnerConfig overrides (tests only); `summary`:
    the system's truth summary (default: the tier's systems_truth.json)."""
    from .suites import load_eval_inputs, tier_dirs
    root = Path(tier_root)
    dirs = tier_dirs(tier, root)
    summary = summary if summary is not None else system_truth_summaries(root, tier).get(sid, {})
    k_true = compressible(summary)
    if k_true is None:
        return {"sid": sid, "type": summary.get("type"), "k_true": None, "skipped": "not compressible", "errors": {}}
    inp = load_eval_inputs(sid, heldout_dirs=dirs)
    tdir = dirs["truth"] / sid.replace(":", "_")
    tdir = tdir if tdir.exists() else None
    pset, held = inp["public"], inp["heldout"]
    train = [pset.load(r) for r in pset.rows if r.get("split") in ("train", "twin")]
    z, zo = {}, {}
    for r in train:
        tr = _truth_arrays(tdir, r.key)
        if "z" in tr:
            z[r.key] = tr["z"]
        if "z_obs" in tr:
            zo[r.key] = tr["z_obs"]
    truth = {"z": z if len(z) == len(train) else None, "z_obs": zo if len(zo) == len(train) else None}

    def registrations():
        for rr in held.rows:
            rec = held.load(rr)
            tr = _truth_arrays(tdir, rec.key)
            yield {"x": rec.x, "u": rec.u, "y": rec.y, "z": tr.get("z"), "z_obs": tr.get("z_obs")}

    return calibrate_from_inputs(sid, pub=inp["record"], sysc=inp["system"], train=train, items=inp["items"], pool=inp["pool"],
                                 k_true=k_true, truth=truth, register=registrations(), summary=summary, n_boot=n_boot, seed=seed,
                                 learner=learner)


def calibrate_from_inputs(sid: str, *, pub: dict, sysc, train: list, items: list, pool, k_true: int, truth: dict | None = None,
                          register=(), summary: dict | None = None, n_boot: int = 2000, seed: int = 0, learner: dict | None = None,
                          refs: tuple[str, ...] = REFS) -> dict:
    """Fit the references on `train` (D0 + D1 records), register the evaluator-side truth / readouts of every held-out history the
    evaluation will encode (`register`: dicts {"x", "u", "y", "z" | None, "z_obs" | None}), score them on `items` / `pool` and return
    the per-reference quantities and verdict inputs (JSON-serialisable). truth: {"z": {key: (T, k)} | None, "z_obs": ... | None}."""
    from . import refs as R
    from .verdict import collect_metrics
    t0 = time.time()
    summary = summary or {}
    truth = truth or {}
    row: dict = {"sid": sid, "type": summary.get("type"), "k_true": int(k_true), "trap": summary.get("trap"), "errors": {},
                 "has_z_obs": truth.get("z_obs") is not None, "n_train": len(train), "n_items": len(items),
                 "n_pool": (len(pool.states) if pool is not None else 0)}
    cfg = R.LearnerConfig(**(learner or {}))
    fitted = R.fit_references(sid, train, pub, names=refs, k=int(k_true), truth=truth, cfg=cfg)
    row["errors"].update(dict(fitted.errors))
    models = fitted.models
    for reg in register:
        for name, key in (("true_state", "z"), ("obs_shortcut", "z_obs")):
            if name in models and reg.get(key) is not None:
                models[name].register_truth(reg["x"], reg["u"], reg[key])
        if "id_shortcut" in models:
            models["id_shortcut"].register_readout(reg["x"], reg["u"], reg["y"])
    ev: dict = {}
    for name, m in models.items():
        try:
            ev[name] = evaluate_reference(m, sysc, items, pool, n_boot=n_boot, seed=seed)
        except Exception as exc:  # noqa: BLE001
            row["errors"][name] = f"evaluation: {type(exc).__name__}: {str(exc)[:300]}"
            row.setdefault("tracebacks", {})[name] = traceback.format_exc()[-3000:]
    compact_limit = getattr(sysc, "compact_limit", None)
    for name, e in ev.items():
        mk = (models[name].info() or {}).get("k", {}).get(sid) if name != "no_effect" else None
        dim = {"k": mk, "compact": (None if compact_limit is None or mk is None else bool(mk <= compact_limit)), "stable": True,
               "note": "reference: k fixed by construction"}
        m = collect_metrics(e["eff"], eff_idshortcut=(ev["id_shortcut"]["eff"] if "id_shortcut" in ev and name != "id_shortcut" else None),
                            eff_fullbound=(ev["full_state"]["eff"] if "full_state" in ev and name != "full_state" else None),
                            mediation=e["med"], closure=e["clo"], micro=e["mic"], calibration=e["cal"], dimension=dim,
                            n_boot=n_boot, seed=seed)
        row[name] = {"EE": _est(e["eff"].get("EE_medium")), "EE_heldout": _est(m.get("EE_heldout")), "EE_infamily": _est(m.get("EE_infamily")),
                     "SMS": _est(e["med"].get("SMS")), "ICG_y": _est(e["clo"].get("ICG_y")), "MEV": _est(e["mic"].get("MEV")),
                     "MEV_testable": bool(e["mic"].get("testable", False)), "false_confidence": _jsonable(e["cal"].get("false_confidence")),
                     "n_items": e["eff"].get("n_items"), "n_abstained": e["eff"].get("n_abstained"), "n_failed": e["eff"].get("n_failed"),
                     "k": mk, "verdict_inputs": _jsonable(m),
                     "info": _jsonable({k: v for k, v in (models[name].info() or {}).items() if k in ("train_cost", "fit_notes", "n_probe_encodes")})}
    row["seconds"] = round(time.time() - t0, 1)
    return _jsonable(row)


# ------------------------------------------------------------------------------------------------------------ tolerances
def _p90(v) -> float:
    v = np.asarray([x for x in v if x is not None and np.isfinite(x)], float)
    return float(np.percentile(v, 90)) if len(v) else float("nan")


def _vals(rows: list[dict], ref: str, fn) -> list:
    out = []
    for r in rows:
        d = r.get(ref)
        if not d:
            continue
        try:
            v = fn(d)
        except (TypeError, KeyError, IndexError):
            v = None
        if v is not None and np.isfinite(v):
            out.append(float(v))
    return out


def tolerance_rule(rows: list[dict]) -> dict:
    """The point tolerances of PROTOCOL section 7 from per-system rows."""
    ee_w = _vals(rows, "true_state", lambda d: d["EE"]["ci95"][1] - d["EE"]["point"])
    c_gap = [float(r["true_state"]["EE"]["point"] - r["full_state"]["EE"]["point"]) for r in rows
             if r.get("true_state", {}).get("EE") and r.get("full_state", {}).get("EE")
             and np.isfinite(r["true_state"]["EE"]["point"]) and np.isfinite(r["full_state"]["EE"]["point"])]
    sms_u = _vals(rows, "true_state", lambda d: d["SMS"]["ci95"][1])
    icg_u = _vals(rows, "true_state", lambda d: d["ICG_y"]["ci95"][1])
    mev_u = _vals(rows, "true_state", lambda d: d["MEV"]["ci95"][1] if d.get("MEV_testable") else None)
    h_gap = _vals(rows, "true_state", lambda d: d["EE_heldout"]["point"] - d["EE_infamily"]["point"])
    return {"delta_A": max(DELTA_A_MIN, _p90(ee_w)) if ee_w else DELTA_A_MIN,
            "delta_C": max(DELTA_C_MIN, _p90(c_gap)) if c_gap else DELTA_C_MIN,
            "tau_SMS": _p90(sms_u), "tau_ICG": _p90(icg_u), "tau_MEV": _p90(mev_u),
            "delta_H": max(DELTA_H_MIN, _p90(h_gap)) if h_gap else DELTA_H_MIN}


def tolerance_cis(rows: list[dict], n_boot: int = N_BOOT_TAU, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    boot = {k: [] for k in TOL_KEYS}
    for _ in range(n_boot):
        sample = [rows[i] for i in rng.integers(0, len(rows), len(rows))]
        t = tolerance_rule(sample)
        for k in TOL_KEYS:
            boot[k].append(t[k])
    out = {}
    for k, v in boot.items():
        a = np.asarray(v, float)
        a = a[np.isfinite(a)]
        out[k] = [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))] if len(a) else [float("nan")] * 2
    return out


def _passes(d: dict | None, key: str, tau: float) -> bool | None:
    if not d or not d.get(key):
        return None
    u = d[key]["ci95"][1]
    return bool(np.isfinite(u) and u <= tau) if np.isfinite(tau) else None


def power_rule(rows: list[dict], key: str, tau: float) -> dict:
    """Pass rates (upper CI <= tau) of the TRUE-STATE, OBS-SHORTCUT (trap systems) and RANDOM-k references, and whether the criterion
    binds: pass_rate(true) - pass_rate(null) >= POWER_MIN for BOTH nulls (a missing null -> not binding)."""
    rates, ns = {}, {}
    for ref in ("true_state", "obs_shortcut", "random_k", "full_state", "pca_k"):
        p = [_passes(r.get(ref), key, tau) for r in rows]
        p = [x for x in p if x is not None]
        rates[ref], ns[ref] = (float(np.mean(p)) if p else None), len(p)
    rt = rates["true_state"]
    gaps = {null: (None if rt is None or rates[null] is None else rt - rates[null]) for null in ("obs_shortcut", "random_k")}
    binds = all(g is not None and g >= POWER_MIN for g in gaps.values())
    return {"pass_rate": rates, "n": ns, "gap": gaps, "binds": bool(binds), "power_min": POWER_MIN}


def judge(rows: list[dict], tol: dict) -> dict:
    """Verdict category counts per reference under tolerances tol (`verdict.system_verdict`)."""
    from .verdict import Tolerances, system_verdict
    T = Tolerances.from_dict(tol)
    out = {}
    for ref in VERDICT_REFS:
        counts: dict[str, int] = {}
        for r in rows:
            m = (r.get(ref) or {}).get("verdict_inputs")
            if not m:
                continue
            cj = (m.get("dimension") or {}).get("compact") is not None
            v = system_verdict(m, T, compact_judged=cj)["category"]
            counts[v] = counts.get(v, 0) + 1
        out[ref] = counts
    return out


def tolerances_from_rows(rows: list[dict], n_boot: int = N_BOOT_TAU, seed: int = 0) -> dict:
    """Everything calibration.json records, from the per-system rows."""
    ok = [r for r in rows if not r.get("skipped") and r.get("true_state")]
    taus = tolerance_rule(ok)
    ci = tolerance_cis(ok, n_boot, seed)
    sms_pw = power_rule(ok, "SMS", taus["tau_SMS"])
    icg_pw = power_rule(ok, "ICG_y", taus["tau_ICG"])
    tol = dict(taus, tau_FC=TAU_FC, sms_binds=sms_pw["binds"], icg_binds=icg_pw["binds"])
    sens = {}
    for key in TOL_KEYS:
        for end, val in zip(("low", "high"), ci[key]):
            if np.isfinite(val):
                sens[f"{key}_{end}"] = judge(ok, dict(tol, **{key: val})).get("true_state", {})
    extra_pw = {"A": {ref: _rate(ok, ref, lambda d: d["EE"]["ci95"][1] < 1 - tol["delta_A"]) for ref in REFS},
                "MEV": {ref: _rate(ok, ref, lambda d: d.get("MEV_testable") and d["MEV"]["ci95"][1] <= tol["tau_MEV"]) for ref in REFS}}
    return {"tolerances": tol, "tolerances_ci95_over_systems": ci, "power": {"SMS": sms_pw, "ICG_y": icg_pw, **extra_pw},
            "verdicts_under_calibrated_tolerances": judge(ok, tol), "true_state_verdicts_at_tolerance_ci_ends": sens,
            "n_systems": len(ok), "n_trap_systems": int(sum(1 for r in ok if r.get("obs_shortcut"))),
            "mev_testable_true_state": int(sum(1 for r in ok if (r.get("true_state") or {}).get("MEV_testable")))}


def _rate(rows, ref, fn) -> float | None:
    vals = []
    for r in rows:
        d = r.get(ref)
        if not d:
            continue
        try:
            vals.append(bool(fn(d)))
        except (TypeError, KeyError, IndexError):
            continue
    return float(np.mean(vals)) if vals else None


def mde_paired(diffs_by_system: dict[str, float], alpha: float = 0.05, power: float = 0.8, one_sided: bool = True) -> dict:
    """Minimum detectable mean paired difference (normal approximation) for n systems with the dev-suite standard deviation of the
    paired differences: (z_{1-alpha} + z_{power}) x sd / sqrt(n)."""
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
             "fresh.py", "suites.py")
    here = Path(__file__).resolve().parent
    return {f: hashlib.sha256((here / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for f in files if (here / f).exists()}


def write_outputs(rec: dict, out: Path | None = None) -> None:
    """calibration.json (full record) and public/tolerances.json (values only)."""
    target = Path(out) if out else BENCH / "calibration.json"
    target.write_text(json.dumps(_jsonable(rec), indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    if out is None:
        (BENCH / "public").mkdir(parents=True, exist_ok=True)
        (BENCH / "public" / "tolerances.json").write_text(json.dumps(_jsonable(rec["tolerances"]), indent=1) + "\n", encoding="utf-8",
                                                           newline="\n")
