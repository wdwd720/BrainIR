"""state_discovery benchmark version 3: the PRE-REGISTERED calibration of the verdict tolerances (PROTOCOL.md section 6; goal4
section 7).

    uv run --project phase3 python scripts/p3/calibrate.py [--workers 8] [--backend local|modal]

Runs on the synthetic DEV suite only (never on real hidden data, never with a candidate method):
- the reference controls of PROTOCOL.md section 5 (full-state reference, input-only, readout-history, PCA-k, random-k with k = the
  true dimension), fitted on the public train + val trajectories (finite blow-ups left out),
- PCA-(k-1) (version 3, power check of the closure condition; systems with k >= 2), and
- the TRUE-LATENT reference (brainir_state.refmodels.TrueLatentModel: the true latent as encoder, learned transition / readout of the
  full-state reference's class, events through a learned linear probe),
on every dev system whose truth says it is compressible (integer k) and closed (no hidden exogenous input). Tolerances (version 3):
    tau_A   = max(0, 90th percentile of (A_truelatent - A_full) / A_full)
    tau_C   = 75th percentile of the true-latent reference's held-out effect error (observed-target state / input interventions);
              it does not bind (the interventional condition is decided by the upper CI of C < 1, PROTOCOL.md section 7)
    tau_D   = 90th percentile of the UPPER 95 % CI bound of the true-latent reference's task micro-gain (closure)
    tau_H   = 90th percentile of the UPPER 95 % CI bound of the true-latent reference's task HISTORY gain (version 3)
    tau_gap = 90th percentile of the true-latent reference's closure gap (y NMSE, restart from the re-encoded history; version 3)
    tau_E   = 90th percentile of the UPPER 95 % CI bound of the true-latent reference's microstate ratio, over the systems where its E
              is testable
Each tolerance gets a 95 % CI by resampling the calibration systems. Recorded: the verdict distributions of the true-latent reference
and of the full-state reference under the calibrated tolerances, the true-latent verdicts at every tolerance's CI ends, the POWER of
the closure condition (pass rates of 'closed' and of each of its parts for random-k, PCA-k, PCA-(k-1), the full-state reference and
the true latent; pre-registered wording rule: if random-k passes 'closed' on more than 25 % of the systems, reports call the condition
"no large microstate or history gain detected"), the Markov checks of every reference, and the effective-pair / null-pair counts of
the held-out C. Writes benchmarks/state_discovery_v1/calibration.json; only the tolerance values are public.
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
TAU_KEYS = ("tau_A", "tau_C", "tau_D", "tau_H", "tau_gap", "tau_E")
NEUTRAL = {k: np.inf for k in TAU_KEYS}
CLOSED_POWER_MAX = 0.25
RETRIED: list = []        # infrastructure retries of this run (recorded in calibration.json)
GAP_POWER_MIN = 0.2      # the closure gap enters 'closed' only if random-k passes it at least 20 points less often than the true latent


def _verdict_inputs(res: dict, refs_res: dict, n_observed: int, k: int, cfg) -> dict:
    """The tolerance-independent parts of a verdict (harness.verdict with neutral tolerances), for re-judging with the calibrated
    tolerances later."""
    from brainir_state.harness import verdict
    v = verdict(res, refs_res, dict(NEUTRAL), n_observed, k, "synthetic", cfg)
    sc = [v.get(f"A_minus_{n}") for n in ("input_only", "readout_hist")]
    return {"A": v["A"], "A_full": v["A_full"],
            "shortcut_ok": bool(all(d is not None and np.isfinite(d["ci95"][1]) and d["ci95"][1] < 0 for d in sc)),
            "C": v["C"], "C_upper": v["C_ci95"][1], "C_loo_max": v.get("C_loo_max"), "C_n_primary": v.get("C_n_pairs_primary"),
            "C_abstained": v["C_abstained_pairs"], "D": v["D_micro_gain"], "D_upper": v["D_ci95"][1], "H_upper": v["D_history_ci95"][1],
            "gap": v["closure_gap_y"], "markov_ok": v["markov_ok"], "E": v["E_ratio"], "E_upper": v["E_ci95"][1],
            "E_testable": v["E_testable"], "compact": v["compact"], "C_n_eff": v.get("C_n_eff"), "C_null_pairs": v.get("C_null_pairs")}


def _calibrate_system(sid: str) -> dict:
    from brainir_state.suite_eval import limit_threads
    limit_threads(2)
    from brainir_state import evaluate as E
    from brainir_state.harness import SYNTH_CFG, SYNTH_ROLES, evaluate_system, fit_references, key_a, key_c, key_d, pca_basis
    from brainir_state.refmodels import ProjectionLinearModel, TrueLatentModel
    from brainir_state.suite_eval import SuiteData
    sd = SuiteData(DATA / "synthetic_dev", kind="synthetic", truth_dir=DATA / "synthetic_truth" / "dev")
    tr = sd.truth_system(sid)
    k = int(tr["k"])
    train = sd.train_only(sid)
    full = sd.train(sid)
    fit = [t for t, b in zip(full, E.blowup_mask(full)) if not b] or list(full)
    info = sd.sysinfo(sid)
    hs = sd.hidden(sid)
    scale = sd.scale(sid)
    pca = pca_basis(train)
    cfg = SYNTH_CFG
    refs = fit_references(sid, fit, info["observed"], k, seed=0)
    if k >= 2:
        refs["pca_km1"] = ProjectionLinearModel(k - 1, "pca").fit(sid, fit, info["observed"])
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
        kk = k - 1 if name == "pca_km1" else k
        res = evaluate_system(m, sid, hs, scale, pca, cfg, k=kk, families=fam, roles=SYNTH_ROLES, train=train, observed=sd.observed(sid))
        results[name] = res
        d = (res.get("D") or {}).get(key_d(cfg)) or {}
        e = res.get("E") or {}
        c = (res.get("C_heldout") or {}).get(key_c(cfg), {})
        r_ = res.get("R") or {}
        out[name] = {"A": (res.get("A_B") or {}).get(key_a(cfg), {}).get("mean"),
                     "C": c.get("ratio"), "C_ci95": c.get("ci95"), "C_n_eff": c.get("n_eff"), "C_n": c.get("n"), "C_null": c.get("n_null"),
                     "C_loo_max": c.get("loo_max"), "C_scrambled_mean": c.get("scrambled_mean"),
                     "C_unobserved": ((res.get("C_heldout_unobserved") or {}).get(key_c(cfg)) or {}).get("ratio"),
                     "C_n_unobserved_pairs": res.get("C_heldout_n_unobserved_pairs"),
                     "C_structural": (res.get("C_structural") or {}).get(key_c(cfg), {}).get("ratio"),
                     "D": d.get("micro_gain"), "D_ci95": d.get("micro_gain_ci95"), "H": d.get("history_gain"), "H_ci95": d.get("history_gain_ci95"),
                     "gap": r_.get("closure_gap_y_nmse"), "markov_ok": r_.get("markov_ok"),
                     "markov": {k_: r_.get(k_) for k_ in ("markov_rollout_inconsistency_rel", "markov_y_inconsistency_nmse",
                                                          "decoy_y_inconsistency_nmse", "readout_inconsistency_nmse")},
                     "E": e.get("E_ratio_latent_to_random"), "E_ci95": e.get("E_ratio_ci95"), "E_testable": e.get("E_testable"),
                     "E_resolution": e.get("E_resolution"),
                     "C_abstained": (res.get("C_heldout") or {}).get("n_abstained_unsupported"),
                     "C_structural_abstained": (res.get("C_structural") or {}).get("n_abstained_unsupported")}
    refs_res = {n: results[n] for n in ("full_state", "input_only", "readout_hist")}
    for name in ("true_latent", "full_state", "pca_k", "random_k", "pca_km1"):
        if name in results:
            out[name]["verdict_inputs"] = _verdict_inputs(results[name], refs_res, len(info["observed"]), k - (name == "pca_km1"), cfg)
    return out


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _fin(x) -> bool:
    return x is not None and np.isfinite(x)


def _closed_parts(vi: dict, taus: dict) -> dict:
    return {"markov_ok": bool(vi["markov_ok"]),
            "micro_gain": bool(_fin(vi["D"]) and _fin(vi["D_upper"]) and vi["D_upper"] <= taus["tau_D"]),
            "history_gain": bool(_fin(vi["H_upper"]) and vi["H_upper"] <= taus["tau_H"]),
            "closure_gap": True if taus.get("tau_gap") is None else bool(_fin(vi["gap"]) and vi["gap"] <= taus["tau_gap"])}


def _judge(vi: dict, taus: dict) -> str:
    """harness.verdict (synthetic mode, version 3) re-applied to the recorded tolerance-independent inputs."""
    from brainir_state.harness import VERDICT_FULL, VERDICT_FULL_E_UNTESTABLE, VERDICT_NONE, VERDICT_PARTIAL
    pred = bool(_fin(vi["A"]) and _fin(vi["A_full"]) and vi["A"] <= vi["A_full"] * (1 + taus["tau_A"]) and vi["shortcut_ok"])
    if not vi.get("C_n_primary") or vi["C_n_primary"] < 3:
        intv = None if not vi["C_abstained"] else False
    else:
        intv = bool(_fin(vi["C"]) and vi["C"] <= taus["tau_C"] and _fin(vi["C_upper"]) and vi["C_upper"] < 1
                    and _fin(vi["C_loo_max"]) and vi["C_loo_max"] < 1 and not vi["C_abstained"])
    closed = all(_closed_parts(vi, taus).values())
    micro = None if vi["E_testable"] is False else bool(_fin(vi["E"]) and _fin(vi["E_upper"]) and vi["E_upper"] <= taus["tau_E"])
    compact_ok = vi["compact"] is not False
    if compact_ok and pred and intv is True and closed and micro is True:
        return VERDICT_FULL
    if compact_ok and pred and intv is True and closed and micro is None:
        return VERDICT_FULL_E_UNTESTABLE
    if pred and (intv is True or closed):
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
    h_up = fin([(r["true_latent"]["H_ci95"] or [None, None])[1] for r in rows])
    gap = fin([r["true_latent"]["gap"] for r in rows])
    e_up = fin([(r["true_latent"]["E_ci95"] or [None, None])[1] for r in rows if r["true_latent"]["E_testable"]])

    def rule(ag, c, d, h, g, e):
        return {"tau_A": float(max(0.0, np.percentile(ag, 90))) if len(ag) else float("nan"),
                "tau_C": float(np.percentile(c, 75)) if len(c) else float("nan"),
                "tau_D": float(np.percentile(d, 90)) if len(d) else float("nan"),
                "tau_H": float(np.percentile(h, 90)) if len(h) else float("nan"),
                "tau_gap": float(np.percentile(g, 90)) if len(g) else float("nan"),
                "tau_E": float(np.percentile(e, 90)) if len(e) else float("nan")}

    arrs = (np.array(a_gap), c_true, d_up, h_up, gap, e_up)
    taus = rule(*arrs)
    rng = np.random.default_rng(0)
    boot = {k: [] for k in taus}
    for _ in range(N_BOOT_TAU):
        res = rule(*[a[rng.integers(0, len(a), len(a))] if len(a) else a for a in arrs])
        for k, v in res.items():
            boot[k].append(v)
    ci = {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in boot.items()}
    return taus, ci, a_gap


def power(rows: list[dict], taus: dict) -> dict:
    """Pass rates of 'closed' and of each of its parts, per reference (version 3; pre-lock review A B2)."""
    out = {}
    for name in ("true_latent", "full_state", "pca_k", "random_k", "pca_km1"):
        vis = [r[name]["verdict_inputs"] for r in rows if name in r and "verdict_inputs" in r[name]]
        if not vis:
            continue
        parts = [_closed_parts(vi, taus) for vi in vis]
        out[name] = {"n": len(vis), "closed": float(np.mean([all(p.values()) for p in parts])),
                     **{k: float(np.mean([p[k] for p in parts])) for k in parts[0]}}
    rk = out.get("random_k", {}).get("closed")
    out["closed_wording"] = ("closed" if rk is not None and rk <= CLOSED_POWER_MAX
                             else "no large microstate or history gain detected (low power against random projections)")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--backend", choices=("local", "modal"), default="local")
    ap.add_argument("--systems", default=None, help="comma list (smoke tests only; the calibration uses every eligible system)")
    ap.add_argument("--out", default=None, help="write here instead of the benchmark (smoke tests)")
    args = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT / "phase3" / "src"))
    truth = json.loads((DATA / "synthetic_truth" / "dev" / "truth.json").read_text(encoding="utf-8"))
    sids = sorted(s for s, t in truth["systems"].items() if t["k"] != "none" and t.get("closed_dynamics", True))
    if args.systems:
        sids = [s for s in sids if s in set(args.systems.split(","))]
    print(f"calibrating on {len(sids)} compressible, closed dev systems ({args.backend})", flush=True)
    if args.backend == "modal":
        sys.path.insert(0, str(ROOT / "scripts" / "p3"))
        from modal_tournament import call_remote
        rows = call_remote("calibrate", "_calibrate_system", [[s] for s in sids], tier="dev")
        # infrastructure failures (a crashed worker process, a lost container) are retried ONCE and recorded; a Python error is a
        # scientific failure and is not retried
        crashed = [i for i, r in enumerate(rows) if isinstance(r, dict) and "error" in r
                   and ("worker exit -" in str(r.get("error")) or "modal call failed" in str(r.get("error")))]
        if crashed:
            print(f"retrying {len(crashed)} crashed systems once: {[sids[i] for i in crashed]}", flush=True)
            again = call_remote("calibrate", "_calibrate_system", [[sids[i]] for i in crashed], tier="dev")
            for i, r in zip(crashed, again):
                RETRIED.append({"sid": sids[i], "first_error": str(rows[i].get("error"))[:300],
                                "first_stderr_tail": str(rows[i].get("stderr") or "")[-1500:], "retry_ok": "error" not in r})
                rows[i] = r
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            rows = list(ex.map(_calibrate_system, sids))
    bad = [r for r in rows if not isinstance(r, dict) or "error" in r]
    if bad:
        raise SystemExit(f"{len(bad)} calibration systems failed: {str(bad[0])[:2000]}")

    def vals(model, key):
        v = np.array([r[model][key] for r in rows if model in r and r[model][key] is not None], float)
        return v[np.isfinite(v)]

    taus_num, taus_ci, a_gap = tolerances(rows)
    # pre-registered (version 3): the closure gap is judged only if it has power against random projections; otherwise it is reported
    # (a model whose rollouts forget their initial state has a small gap whatever its latent)
    pw_num = power(rows, taus_num)
    gap_power = (pw_num.get("true_latent", {}).get("closure_gap", 0.0) - pw_num.get("random_k", {}).get("closure_gap", 1.0))
    gap_in_verdict = bool(gap_power >= GAP_POWER_MIN)
    taus = dict(taus_num) if gap_in_verdict else dict(taus_num, tau_gap=None)
    dist = {m: {k: {"median": float(np.median(vals(m, k))) if len(vals(m, k)) else None,
                    "p10": float(np.percentile(vals(m, k), 10)) if len(vals(m, k)) else None,
                    "p90": float(np.percentile(vals(m, k), 90)) if len(vals(m, k)) else None} for k in ("A", "C", "D", "H", "gap", "E")}
            for m in ("full_state", "true_latent", "pca_k", "pca_km1", "random_k")}
    dist.update({m: {"A": {"median": float(np.median(vals(m, "A"))) if len(vals(m, "A")) else None}} for m in ("input_only", "readout_hist")})
    verdicts = {}
    for name in ("true_latent", "full_state", "pca_k", "random_k", "pca_km1"):
        counts = {}
        for r in rows:
            if name in r and "verdict_inputs" in r[name]:
                v = _judge(r[name]["verdict_inputs"], taus)
                counts[v] = counts.get(v, 0) + 1
        verdicts[name] = counts
    sens = {}
    for key in TAU_KEYS:
        if taus.get(key) is None:
            continue
        for end, val in zip(("low", "high"), taus_ci[key]):
            t2 = dict(taus, **{key: val})
            counts = {}
            for r in rows:
                v = _judge(r["true_latent"]["verdict_inputs"], t2)
                counts[v] = counts.get(v, 0) + 1
            sens[f"{key}_{end}"] = counts
    markov = {m: int(sum(1 for r in rows if m in r and r[m].get("markov_ok"))) for m in ("true_latent", "full_state", "pca_k", "random_k", "pca_km1")}
    c_design = {"n_eff": {q: float(np.percentile(vals("true_latent", "C_n_eff"), q)) for q in (10, 25, 50, 75, 90)} if len(vals("true_latent", "C_n_eff")) else None,
                "pairs_primary_median": float(np.median(vals("true_latent", "C_n"))) if len(vals("true_latent", "C_n")) else None,
                "null_pairs_total": int(sum(vals("true_latent", "C_null"))) if len(vals("true_latent", "C_null")) else 0,
                "systems_with_unobserved_target_pairs": int(sum(1 for r in rows if (r["true_latent"].get("C_n_unobserved_pairs") or 0) > 0))}
    code = {p: _sha(ROOT / p) for p in ("scripts/p3/calibrate.py", "phase3/src/brainir_state/refmodels.py", "phase3/src/brainir_state/evaluate.py",
                                          "phase3/src/brainir_state/harness.py", "phase3/src/brainir_state/evaluate_cross.py",
                                          "phase3/src/brainir_state/suite_eval.py")}
    rec = {"protocol_section": "PROTOCOL.md section 6 (benchmark version 3)", "suite": "synthetic dev", "n_systems": len(rows),
           "backend": args.backend, "tolerances": taus, "tolerances_numeric": taus_num, "closure_gap_in_verdict": gap_in_verdict,
           "closure_gap_power": gap_power, "closure_power_numeric_taus": pw_num,
           "tolerances_ci95_over_systems": taus_ci, "relative_A_gap_truelatent_vs_full": a_gap,
           "baseline_distributions": dist, "verdicts_under_calibrated_tolerances": verdicts,
           "true_latent_verdicts_at_tolerance_ci_ends": sens, "closure_power": power(rows, taus), "markov_ok_counts": markov,
           "heldout_C_design": c_design, "infrastructure_retries": RETRIED,
           "true_latent_E_testable": int(sum(1 for r in rows if r["true_latent"]["E_testable"])), "per_system": rows, "code_sha256": code,
           "dev_suite": json.loads((BENCH / "public" / "synthetic_dev_suite.json").read_text(encoding="utf-8"))}
    if args.out:
        Path(args.out).write_text(json.dumps(rec, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    else:
        (BENCH / "calibration.json").write_text(json.dumps(rec, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
        (BENCH / "public" / "tolerances.json").write_text(json.dumps(taus, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"tolerances": taus, "tolerances_numeric": taus_num, "closure_gap_in_verdict": gap_in_verdict, "ci95": taus_ci,
                      "verdicts": verdicts, "closure_power": rec["closure_power"],
                      "markov_ok_counts": markov, "heldout_C_design": c_design}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
