"""state_discovery benchmark version 2: the PRE-REGISTERED calibration of the verdict tolerances (PROTOCOL.md section 6; goal4
section 7).

    uv run --project phase3 python scripts/p3/calibrate.py [--workers 8] [--backend local|modal]

Runs on the synthetic DEV suite only (never on real hidden data, never with a candidate method):
- the reference controls of PROTOCOL.md section 5 (full-state ceiling, input-only, readout-history, PCA-k, random-k with k = the true
  dimension), fitted on the public train + val trajectories (finite blow-ups left out), and
- the TRUE-LATENT reference (brainir_state.refmodels.TrueLatentModel: the true latent as encoder, learned transition / readout of the
  ceiling's class, events through a learned linear probe),
on every dev system whose truth says it is compressible (integer k) and closed (no hidden exogenous input). Tolerances (version 2):
    tau_A = max(0, 90th percentile of (A_truelatent - A_full) / A_full)
    tau_C = 75th percentile of the true-latent reference's held-out effect error (state / input interventions)
    tau_D = 90th percentile of the UPPER 95 % CI bound of the true-latent reference's task micro-gain (closure)
    tau_E = 90th percentile of the UPPER 95 % CI bound of the true-latent reference's microstate ratio, over the systems where its E
            is testable
Each tolerance also gets a 95 % CI by resampling the calibration systems (review E M1). The verdict distributions of the true-latent
reference and of the full-state ceiling under the calibrated tolerances are recorded (review E M2). Writes
benchmarks/state_discovery_v1/calibration.json (tolerances, their CIs, per-system values of every reference = the baseline
distributions, verdict distributions, code hashes). Only the tolerance values are public.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "phase3"
BENCH = ROOT / "benchmarks" / "state_discovery_v1"
N_BOOT_TAU = 2000


def _verdict_inputs(res: dict, refs_res: dict, n_observed: int, k: int, cfg) -> dict:
    """The tolerance-independent parts of a verdict (harness.verdict with neutral tolerances), for re-judging with the calibrated
    tolerances later."""
    from brainir_state.harness import verdict
    v = verdict(res, refs_res, {"tau_A": np.inf, "tau_C": np.inf, "tau_D": np.inf, "tau_E": np.inf}, n_observed, k, "synthetic", cfg)
    return {"A": v["A"], "A_full": v["A_full"], "shortcut_ok": bool(v["A_minus_input_only"]["ci95"][1] < 0 and v["A_minus_readout_hist"]["ci95"][1] < 0),
            "C": v["C"], "C_upper": v["C_ci95"][1], "C_abstained": v["C_abstained_pairs"], "D": v["D_micro_gain"], "D_upper": v["D_ci95"][1],
            "E": v["E_ratio"], "E_upper": v["E_ci95"][1], "E_testable": v["E_testable"], "compact": v["compact"]}


def _calibrate_system(sid: str) -> dict:
    from brainir_state.suite_eval import limit_threads
    limit_threads(2)
    from brainir_state import evaluate as E
    from brainir_state.harness import SYNTH_CFG, SYNTH_ROLES, evaluate_system, fit_references, key_a, key_c, key_d, pca_basis
    from brainir_state.refmodels import TrueLatentModel
    from brainir_state.suite_eval import SuiteData
    sd = SuiteData(DATA / "synthetic_dev", kind="synthetic", truth_dir=DATA / "synthetic_truth" / "dev")
    tr = sd.truth_system(sid)
    k = int(tr["k"])
    train = sd.train_only(sid)
    full = sd.train(sid)
    fit = [t for t, b in zip(full, E.blowup_mask(full)) if not b] or list(full)
    info = sd.sysinfo(sid)
    hs = sd.hidden(sid)
    scale = E.readout_scale(train)
    pca = pca_basis(train)
    cfg = SYNTH_CFG
    refs = fit_references(sid, fit, info["observed"], k, seed=0)
    zfit = sd.z_true([t.key for t in fit])
    tl = TrueLatentModel(info["observed"], seed=0).fit(sid, fit, zfit)
    # exact encoder on every public and held-out trajectory / twin / pool state of this system
    all_rows = [r for r in sd.pub.select(system_id=sid) if r["split"] in ("train", "val", "test", "twin", "pool")]
    zt = sd.z_true([r["key"] for r in all_rows if r["split"] != "pool"])
    pool_lat = {}
    pl = sd.truth_dir / "pools" / "pool_latents.npz"
    if pl.exists():
        with np.load(pl) as z:
            pool_lat = {k_: z[k_] for k_ in z.files if k_ in {r["key"] for r in all_rows if r["split"] == "pool"}}
    for r in all_rows:
        zz = zt.get(r["key"]) if r["split"] != "pool" else pool_lat.get(r["key"])
        if zz is not None:
            t = sd.pub.load(r)
            tl.register(t.x, zz)
    models = dict(refs)
    models["true_latent"] = tl
    out = {"sid": sid, "k": k, "trap": tr.get("trap"), "family": tr.get("family"), "n_observed": len(info["observed"])}
    results = {}
    for name, m in models.items():
        fam = ("A",) if name in ("input_only", "readout_hist") else ("A", "C", "D", "R", "E")
        res = evaluate_system(m, sid, hs, scale, pca, cfg, k=k, families=fam, roles=SYNTH_ROLES, train=train)
        results[name] = res
        d = (res.get("D") or {}).get(key_d(cfg)) or {}
        e = res.get("E") or {}
        out[name] = {"A": (res.get("A_B") or {}).get(key_a(cfg), {}).get("mean"),
                     "C": (res.get("C_heldout") or {}).get(key_c(cfg), {}).get("ratio"),
                     "C_structural": (res.get("C_structural") or {}).get(key_c(cfg), {}).get("ratio"),
                     "D": d.get("micro_gain"), "D_ci95": d.get("micro_gain_ci95"),
                     "E": e.get("E_ratio_latent_to_random"), "E_ci95": e.get("E_ratio_ci95"), "E_testable": e.get("E_testable"),
                     "E_resolution": e.get("E_resolution"),
                     "C_abstained": (res.get("C_heldout") or {}).get("n_abstained_unsupported"),
                     "C_structural_abstained": (res.get("C_structural") or {}).get("n_abstained_unsupported")}
    refs_res = {n: results[n] for n in ("full_state", "input_only", "readout_hist")}
    for name in ("true_latent", "full_state"):
        out[name]["verdict_inputs"] = _verdict_inputs(results[name], refs_res, len(info["observed"]), k, cfg)
    return out


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _judge(vi: dict, taus: dict) -> str:
    from brainir_state.harness import VERDICT_FULL, VERDICT_FULL_E_UNTESTABLE, VERDICT_NONE, VERDICT_PARTIAL
    fin = lambda x: x is not None and np.isfinite(x)  # noqa: E731
    pred = bool(fin(vi["A"]) and fin(vi["A_full"]) and vi["A"] <= vi["A_full"] * (1 + taus["tau_A"]) and vi["shortcut_ok"])
    intv = bool(fin(vi["C"]) and vi["C"] <= taus["tau_C"] and fin(vi["C_upper"]) and vi["C_upper"] < 1 and not vi["C_abstained"])
    closed = bool(fin(vi["D"]) and fin(vi["D_upper"]) and vi["D_upper"] <= taus["tau_D"])
    micro = None if vi["E_testable"] is False else bool(fin(vi["E"]) and fin(vi["E_upper"]) and vi["E_upper"] <= taus["tau_E"])
    compact_ok = vi["compact"] is not False
    if compact_ok and pred and intv and closed and micro is True:
        return VERDICT_FULL
    if compact_ok and pred and intv and closed and micro is None:
        return VERDICT_FULL_E_UNTESTABLE
    if pred and (intv or closed):
        return VERDICT_PARTIAL
    return VERDICT_NONE


def tolerances(rows: list[dict]) -> tuple[dict, dict, list[float]]:
    """Point tolerances, their bootstrap CIs over systems, and the relative A gaps."""
    def fin(v):
        v = np.array([x for x in v if x is not None], float)
        return v[np.isfinite(v)]

    a_gap = []
    for r in rows:
        at, af = r["true_latent"]["A"], r["full_state"]["A"]
        if at is not None and af is not None and np.isfinite(at) and np.isfinite(af) and af > 0:
            a_gap.append((at - af) / af)
    c_true = fin([r["true_latent"]["C"] for r in rows])
    d_up = fin([(r["true_latent"]["D_ci95"] or [None, None])[1] for r in rows])
    e_up = fin([(r["true_latent"]["E_ci95"] or [None, None])[1] for r in rows if r["true_latent"]["E_testable"]])

    def rule(ag, c, d, e):
        return {"tau_A": float(max(0.0, np.percentile(ag, 90))) if len(ag) else float("nan"),
                "tau_C": float(np.percentile(c, 75)) if len(c) else float("nan"),
                "tau_D": float(np.percentile(d, 90)) if len(d) else float("nan"),
                "tau_E": float(np.percentile(e, 90)) if len(e) else float("nan")}

    taus = rule(np.array(a_gap), c_true, d_up, e_up)
    rng = np.random.default_rng(0)
    boot = {k: [] for k in taus}
    arrs = (np.array(a_gap), c_true, d_up, e_up)
    for _ in range(N_BOOT_TAU):
        res = rule(*[a[rng.integers(0, len(a), len(a))] if len(a) else a for a in arrs])
        for k, v in res.items():
            boot[k].append(v)
    ci = {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in boot.items()}
    return taus, ci, a_gap


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--backend", choices=("local", "modal"), default="local")
    args = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT / "phase3" / "src"))
    truth = json.loads((DATA / "synthetic_truth" / "dev" / "truth.json").read_text(encoding="utf-8"))
    sids = sorted(s for s, t in truth["systems"].items() if t["k"] != "none" and t.get("closed_dynamics", True))
    print(f"calibrating on {len(sids)} compressible, closed dev systems ({args.backend})", flush=True)
    if args.backend == "modal":
        sys.path.insert(0, str(ROOT / "scripts" / "p3"))
        from modal_tournament import call_remote
        rows = call_remote("calibrate", "_calibrate_system", [[s] for s in sids], tier="dev")
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            rows = list(ex.map(_calibrate_system, sids))
    bad = [r for r in rows if not isinstance(r, dict) or "error" in r]
    if bad:
        raise SystemExit(f"{len(bad)} calibration systems failed: {str(bad[0])[:2000]}")

    def vals(model, key):
        v = np.array([r[model][key] for r in rows if r[model][key] is not None], float)
        return v[np.isfinite(v)]

    taus, taus_ci, a_gap = tolerances(rows)
    dist = {m: {k: {"median": float(np.median(vals(m, k))) if len(vals(m, k)) else None,
                    "p10": float(np.percentile(vals(m, k), 10)) if len(vals(m, k)) else None,
                    "p90": float(np.percentile(vals(m, k), 90)) if len(vals(m, k)) else None} for k in ("A", "C", "D", "E")}
            for m in ("full_state", "true_latent", "pca_k", "random_k", "input_only", "readout_hist")}
    verdicts = {}
    for name in ("true_latent", "full_state"):
        counts = {}
        for r in rows:
            v = _judge(r[name]["verdict_inputs"], taus)
            counts[v] = counts.get(v, 0) + 1
        verdicts[name] = counts
    sens = {}
    for key in ("tau_A", "tau_C", "tau_D", "tau_E"):
        for end, val in zip(("low", "high"), taus_ci[key]):
            t2 = dict(taus, **{key: val})
            counts = {}
            for r in rows:
                v = _judge(r["true_latent"]["verdict_inputs"], t2)
                counts[v] = counts.get(v, 0) + 1
            sens[f"{key}_{end}"] = counts
    code = {p: _sha(ROOT / p) for p in ("scripts/p3/calibrate.py", "phase3/src/brainir_state/refmodels.py", "phase3/src/brainir_state/evaluate.py",
                                          "phase3/src/brainir_state/harness.py", "phase3/src/brainir_state/evaluate_cross.py",
                                          "phase3/src/brainir_state/suite_eval.py")}
    rec = {"protocol_section": "PROTOCOL.md section 6 (benchmark version 2)", "suite": "synthetic dev", "n_systems": len(rows),
           "backend": args.backend, "tolerances": taus, "tolerances_ci95_over_systems": taus_ci, "relative_A_gap_truelatent_vs_full": a_gap,
           "baseline_distributions": dist, "verdicts_under_calibrated_tolerances": verdicts,
           "true_latent_verdicts_at_tolerance_ci_ends": sens,
           "true_latent_E_testable": int(sum(1 for r in rows if r["true_latent"]["E_testable"])), "per_system": rows, "code_sha256": code,
           "dev_suite": json.loads((BENCH / "public" / "synthetic_dev_suite.json").read_text(encoding="utf-8"))}
    (BENCH / "calibration.json").write_text(json.dumps(rec, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    (BENCH / "public" / "tolerances.json").write_text(json.dumps(taus, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"tolerances": taus, "ci95": taus_ci, "verdicts": verdicts}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
