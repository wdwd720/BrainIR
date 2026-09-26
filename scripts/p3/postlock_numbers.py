"""Post-lock review numbers (ANSWER-BEARING). ORCHESTRATOR SIDE; reporting only.

Re-derives from the stored result files every number that the post-lock reviews S, C, Y and R (research/phase3/reviews/POSTLOCK_*.md)
flagged, so that each correction in PHASE3_REPORT.md is reproducible from a script instead of a reviewer's scratch file. It reads result
files only and changes nothing; the locked method, the evaluator and every hashed file are untouched.

    uv run --project phase3 --no-sync python scripts/p3/postlock_numbers.py   ->  research/phase3/reviews/POSTLOCK_NUMBERS.json

Inputs: research/phase3/level_c/01/level_c_results.json, the Level C fit records (C:/Dev/BrainIR_p3run/level_c_01, git-ignored run
directory), research/phase3/tournament/{final_b,r3v3}/, research/phase3/counterexamples/*/, research/phase3/ablations/*/,
research/phase3/SELF_AUDIT.json, benchmarks/state_discovery_v1/calibration.json and the public real training data (data/phase3/real_public)
for the descriptive count of observed neurons peaking above 1 Hz.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))
from brainir_state.evaluate_cross import paired_diff, rank_profiles  # noqa: E402

P3 = ROOT / "research" / "phase3"
RUN = Path(r"C:\Dev\BrainIR_p3run")
OUT = P3 / "reviews" / "POSTLOCK_NUMBERS.json"
HORIZONS = (10, 50, 100, 250, 500)
PRIMARY_H = 250
M, B = "brainir_state_v1", "lin_dmdc_t"
COMPACT = ("compact causal state discovered", "compact causal state discovered (microstate equivalence untestable)")


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def fnum(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def r(x, n=4):
    x = fnum(x)
    return None if x is None else float(f"{x:.{n}g}")


def boot_ci(values, stat=np.mean, n_boot=2000, seed=0):
    v = np.asarray(values, float)
    rng = np.random.default_rng(seed)
    b = [stat(v[rng.integers(0, len(v), len(v))]) for _ in range(n_boot)]
    return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return float(min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n))


# ------------------------------------------------------------------------------------------------------------------------ Level C
def level_c() -> dict:
    LC = load(P3 / "level_c" / "01" / "level_c_results.json")
    S = LC["systems"]
    out = {"systems": {}, "pca_vs_method": {}, "ood": {}, "sharing": {}, "primary_C": {}, "counts": {}}

    # PCA-k against the method, paired over the same hidden trajectories (the evaluator's paired_diff: mean of per-trajectory
    # differences, bootstrap B = 2000, seed 0), at every horizon
    counts = {h: Counter() for h in HORIZONS}
    for sid, s in S.items():
        m = s[M]
        rows = {}
        for h in HORIZONS:
            key = f"A_nmse_h{h}ms"
            ua, ub = m["res"]["A_B"]["_units"][key], m["references"]["pca_k"]["A_B"]["_units"][key]
            pd = paired_diff(ua, ub)
            ma, mb = m["res"]["A_B"][key]["mean"], m["references"]["pca_k"]["A_B"][key]["mean"]
            rows[key] = {"method": r(ma), "pca_k": r(mb), "diff_method_minus_pca": r(pd["diff"]), "ci95": [r(x) for x in pd["ci95"]],
                         "n": pd["n"]}
            counts[h]["pca_better_point"] += mb < ma
            counts[h]["pca_better_sig"] += pd["ci95"][0] > 0
            counts[h]["method_better_sig"] += pd["ci95"][1] < 0
        out["pca_vs_method"][sid] = rows
    out["pca_vs_method_counts"] = {f"h{h}ms": dict(counts[h]) for h in HORIZONS}
    out["pca_vs_method_note"] = ("self_audit.py Q16 compared PCA-k's FIRST A key (10 ms) with the method's verdict A (250 ms); these rows "
                                 "compare matched horizons")

    # fit records (seed 0) of the locked method: oscillation flag, event support, training cost
    fitrec = {}
    for sid in S:
        f = RUN / "level_c_01" / M / "indep" / f"{sid.replace(':', '_')}_s0.json"
        if f.exists():
            rec = load(f)
            info = rec.get("info") or {}
            chk = (info.get("checks") or {}).get(sid) or {}
            ev = (info.get("events") or {}).get(sid) or {}
            fitrec[sid] = {"oscillation_flag": (chk.get("oscillation") or {}).get("flag"),
                           "oscillation_k_min": (chk.get("oscillation") or {}).get("k_min"),
                           "event_kinds_supported": sorted(k for k, v in ev.items() if isinstance(v, dict) and v.get("supported")),
                           "event_gains": {k: v.get("gain") for k, v in ev.items() if isinstance(v, dict) and "gain" in v},
                           "train_cost": info.get("train_cost"), "n_params": info.get("n_params")}

    # observed neurons peaking above 1 Hz in the PUBLIC nominal training trajectories (descriptive proxy for PROTOCOL F's probe set)
    peaks = defaultdict(lambda: None)
    idx = ROOT / "data" / "phase3" / "real_public" / "index.jsonl"
    if idx.exists():
        for ln in idx.read_text(encoding="utf-8").splitlines():
            row = json.loads(ln)
            if row.get("split") != "train" or row.get("family") != "nominal":
                continue
            z = np.load(ROOT / "data" / "phase3" / "real_public" / "traj" / f"{row['key']}.npz")
            pk = z["x"].max(axis=0)
            sid = row["system_id"]
            peaks[sid] = pk if peaks[sid] is None else np.maximum(peaks[sid], pk)

    for sid, s in S.items():
        rowsys = {"network": s["network"], "mode": s["mode"], "reconstruction": s["reconstruction"],
                  "mechanism_family": s["mechanism_family"], "n_observed": s["n_observed"],
                  "n_observed_peak_above_1Hz_public_train": (int((peaks[sid] > 1.0).sum()) if peaks[sid] is not None else None)}
        for mod in (M, B):
            m = s[mod]
            v, res = m["verdict"], m["res"]
            fam = {f: {"n_pairs": d.get("n_pairs"), "n_abstained": d.get("n_abstained_unsupported")}
                   for f, d in (res.get("C_per_family") or {}).items()}
            ch = res.get("C_heldout") or {}
            c250 = ch.get("C_effect_error_w250ms") or {}
            ab = {}
            for h in (100, 250):
                ab[f"A_h{h}ms"] = r(res["A_B"][f"A_nmse_h{h}ms"]["mean"])
                ab[f"A_full_h{h}ms"] = r(m["references"]["full_state"]["A_B"][f"A_nmse_h{h}ms"]["mean"])
                ab[f"A_input_only_h{h}ms"] = r(m["references"]["input_only"]["A_B"][f"A_nmse_h{h}ms"]["mean"])
            rowsys[mod] = {
                "k": m["k"], "k_range_descriptive": m.get("k_range"), "verdict": v["verdict"], "compact": v["compact"],
                "predictive": v["predictive"], "interventional": v["interventional"], "interventional_reason": v["interventional_reason"],
                "closed": v["closed"], "closed_parts": v["closed_parts"], "microstate_equivalent": v["microstate_equivalent"],
                "E_testable": v["E_testable"], "markov_ok": v["markov_ok"], "events_worst": v["markov_detail"].get("events_worst"),
                "markov_events_n": (ch.get("markov_events") or {}).get("n"), "declared_failure": v["declared_failure"],
                "abstention": v["abstention"], "A": r(v["A"]), "A_full": r(v["A_full"]), **ab,
                "A_minus_input_only": v["A_minus_input_only"], "A_minus_persistence": v["A_minus_persistence"],
                "C": r(v["C"]), "C_ci95": [r(x) for x in (v["C_ci95"] or [])], "C_n_pairs_primary": v["C_n_pairs_primary"],
                "C_abstained_pairs": v["C_abstained_pairs"], "C_null_pairs": v["C_null_pairs"], "C_n_eff": r(v["C_n_eff"], 3),
                "C_nonnull": r(v["C_nonnull"]), "C_loo_max": r(v["C_loo_max"]), "C_scrambled_mean": r(v["C_scrambled_mean"]),
                "C_minus_scrambled_mean_ci95": [r(x) for x in (v["C_minus_scrambled_mean_ci95"] or [])],
                "state_mediated": v["state_mediated"], "C_alt_scales": v["C_alt_scales"],
                "C_den_share_by_dim_max": r(max(c250.get("den_share_by_dim") or [float("nan")])),
                "C_max_share_pair": r(c250.get("max_share")), "C_per_family": fam,
                "interventional_closure_gap": r(v["interventional_closure_gap"]),
                "interventional_closure_gap_no_effect": r((ch.get("interventional_closure_gap") or {}).get("ratio_no_effect")),
                "D_micro_gain": r(v["D_micro_gain"]), "D_ci95": v["D_ci95"], "E_ratio": r(v["E_ratio"]), "E_ci95": v["E_ci95"],
            }
        rowsys[M]["fit_record_seed0"] = fitrec.get(sid)
        g = (LC["G"].get(sid) or {}).get("G") or {}
        pairs = g.get("pairs") or []
        r2min = [min(p["r2_a_to_b"], p["r2_b_to_a"]) for p in pairs if fnum(p.get("r2_a_to_b")) is not None]
        pdis = [p["prediction_disagreement_nmse"] for p in pairs if fnum(p.get("prediction_disagreement_nmse")) is not None]
        ks = g.get("k") or []
        rowsys["G_seeds"] = {"k": ks, "modal_k": Counter(ks).most_common(1)[0][0] if ks else None, "k_agree": g.get("k_agree"),
                             "r2_min_mean": r(g.get("r2_min_mean")), "r2_min_pair_median": r(np.median(r2min)) if r2min else None,
                             "r2_min_pair_worst": r(min(r2min)) if r2min else None,
                             "prediction_disagreement_mean": r(g.get("prediction_disagreement_nmse")),
                             "prediction_disagreement_max_pair": r(max(pdis)) if pdis else None}
        gr = LC["G_resample"]["per_system"].get(sid) or {}
        rowsys["G_half_samples_descriptive"] = {"k": gr.get("k"), "k_agree": gr.get("k_agree"), "r2_min_mean": r(gr.get("r2_min_mean")),
                                                "prediction_disagreement": r(gr.get("prediction_disagreement_nmse"))}
        out["systems"][sid] = rowsys

    # out-of-distribution families at the primary and the 100 ms horizon, with capped windows and the input-only control
    for sid in ("real:net1:full", "real:net2:full", "real:net3:full"):
        s = S[sid]
        rows = {}
        for who, src in (("method", s[M]["res"]), ("comparator", s[B]["res"]), ("input_only", s[M]["references"]["input_only"]),
                         ("full_state", s[M]["references"]["full_state"])):
            for h in (100, 250):
                key = f"A_nmse_h{h}ms"
                ind = src["A_B"][key]
                rows.setdefault(who, {})[f"in_dist_h{h}ms"] = r(ind["mean"])
                for fam, d in (src.get("H_ood") or {}).items():
                    rows[who][f"{fam}_h{h}ms"] = r(d[key]["mean"])
                    rows[who][f"{fam}_h{h}ms_capped_windows"] = d[key].get("n_windows_capped")
                    rows[who][f"{fam}_h{h}ms_fold"] = r(d[key]["mean"] / ind["mean"], 3) if ind["mean"] else None
        out["ood"][sid] = rows

    # sharing within networks (I) and across connectomes (J): parameter counts, the method's internal test, LOIO and transfers
    for n, d in LC["I"].items():
        c = d["comparison"]
        out["sharing"][f"I:{n}"] = {"verdict": d["verdict"], "shared_params": c.get("shared_params"),
                                    "independent_params": c.get("independent_params"), "fewer_parameters": c.get("fewer_parameters"),
                                    "method_own_verdict": {k: v for k, v in d["method_own_verdict"].items() if k != "test"},
                                    "method_own_transition_params": (d["method_own_verdict"].get("test") or {}).get("transition_params"),
                                    "loio": [{"held": x["held"], "A_diff": x["A_diff"], "C_diff": x["C_diff"],
                                              "adapted_beats_scratch": x["adapted_beats_scratch"]} for x in d.get("loio") or []]}
    for n, d in LC["J"].items():
        c = d["comparison"]
        out["sharing"][f"J:{n}"] = {"verdict": d["verdict"], "note": d["note"], "shared_params": c.get("shared_params"),
                                    "independent_params": c.get("independent_params"), "fewer_parameters": c.get("fewer_parameters"),
                                    "shared_equals_independent": d["model3_shared"] == d["model1_independent"],
                                    "model4_partial": d["model4_partial"],
                                    "transfer": [{"held": x["held"], "A_diff": x["A_diff"], "C_diff": x["C_diff"],
                                                  "adapted_beats_scratch": x["adapted_beats_scratch"]} for x in d.get("transfer") or []]}

    for sid, pc in LC["primary_comparisons"].items():
        if "C" in pc:
            c = pc["C"]
            out["primary_C"][sid] = {k: c.get(k) for k in ("diff", "ci95", "margin", "p_noninferiority", "p_two_sided", "ratio_a",
                                                           "ratio_b", "method_C", "method_C_ci95", "claim", "n")}
    out["primary_holm"] = LC["primary_holm"]
    out["secondary_superiority_holm"] = LC["secondary_superiority_holm"]

    rows = out["systems"]
    out["counts"] = {
        "no_compact_state": sorted(s for s, x in rows.items() if x[M]["abstention"].get("no_compact_state")),
        "all_kick_pulse_abstained_full": sorted(s for s, x in rows.items() if x["mode"] == "full" and all(
            (x[M]["C_per_family"].get(f) or {}).get("n_abstained") == (x[M]["C_per_family"].get(f) or {}).get("n_pairs")
            for f in ("H_kick_A", "H_kick_B", "H_pulse_A", "H_pulse_B"))),
        "C_untestable_all_abstained": sorted(s for s, x in rows.items() if not x[M]["C_n_pairs_primary"]),
        "events_markov_untested": sorted(s for s, x in rows.items() if x[M]["events_worst"] is None),
        "comparator_no_compact_state": sorted(s for s, x in rows.items() if x[B]["abstention"].get("no_compact_state")),
        "comparator_abstained_pairs_total": sum(x[B]["C_abstained_pairs"] or 0 for x in rows.values()),
        "k_ge_n_observed": sorted(s for s, x in rows.items() if x[M]["k"] >= x["n_observed"]),
        "seed_k_agree": sorted(s for s, x in rows.items() if x["G_seeds"]["k_agree"]),
        "half_sample_k_agree": sorted(s for s, x in rows.items() if x["G_half_samples_descriptive"]["k_agree"]),
        "microstate_equivalent": sorted(s for s, x in rows.items() if x[M]["microstate_equivalent"]),
        "closed": sorted(s for s, x in rows.items() if x[M]["closed"]),
        "not_state_mediated_where_C_defined": sorted(s for s, x in rows.items() if x[M]["C"] is not None and not x[M]["state_mediated"]),
    }
    return out


# ------------------------------------------------------------------------------------------------------------------------ FINAL suite
def final_suite() -> dict:
    fb = P3 / "tournament" / "final_b"
    FB = load(fb / f"{M}.json")
    CB = load(fb / f"{B}.json")
    AG = load(fb / "AGGREGATE_developer_facing.json")
    comp = list(AG["design"]["compressible"])
    ps, pc = FB["per_system"], CB["per_system"]
    out = {"verdict_counts_compressible": FB["verdict_counts_compressible"], "abstention": FB["abstention"]}

    wrong_k = []
    for s in comp:
        v = ps[s]["verdict"]
        if v["verdict"] in COMPACT and ps[s]["k"] != ps[s]["k_true"]:
            wrong_k.append({"system": s, "k": ps[s]["k"], "k_true": ps[s]["k_true"], "trap": ps[s]["trap"], "verdict": v["verdict"],
                            "state_mediated": v.get("state_mediated")})
    out["compact_with_wrong_k"] = wrong_k
    out["compact_not_state_mediated"] = [{"system": s, "trap": ps[s]["trap"], "diff_ci95": ps[s]["verdict"].get("C_minus_scrambled_mean_ci95")}
                                         for s in comp if ps[s]["verdict"]["verdict"] in COMPACT and not ps[s]["verdict"].get("state_mediated")]
    out["compact_E_untestable"] = [{"system": s, "trap": ps[s]["trap"], "k": ps[s]["k"], "k_true": ps[s]["k_true"],
                                    "reason": ps[s]["verdict"].get("E_untestable_reason"),
                                    "K_min": r(min(ps[s]["K"]["r2_true_from_model_rff"], ps[s]["K"]["r2_model_from_true_rff"]))}
                                   for s in comp if ps[s]["verdict"]["verdict"] == COMPACT[1]]

    kmin = {s: min(ps[s]["K"]["r2_true_from_model_rff"], ps[s]["K"]["r2_model_from_true_rff"]) for s in comp
            if isinstance(ps[s].get("K"), dict) and fnum(ps[s]["K"].get("r2_true_from_model_rff")) is not None}
    kv = np.array(list(kmin.values()))
    low = sorted(kmin.items(), key=lambda x: x[1])[:5]
    out["K_min_both_ways"] = {"n": len(kv), "median": r(np.median(kv)), "mean": r(kv.mean()), "n_below_0.9": int((kv < 0.9).sum()),
                              "n_below_0.5": int((kv < 0.5).sum()),
                              "lowest": [{"system": s, "K": r(x), "trap": ps[s]["trap"], "k": ps[s]["k"], "k_true": ps[s]["k_true"]} for s, x in low]}

    ex_m = {s: bool(ps[s]["K_dim"]["exact"]) for s in comp}
    ex_c = {s: bool((pc.get(s) or {}).get("K_dim", {}).get("exact")) for s in comp}
    b_ = sum(ex_m[s] and not ex_c[s] for s in comp)
    c_ = sum(ex_c[s] and not ex_m[s] for s in comp)
    d = np.array([ex_m[s] - ex_c[s] for s in comp], float)
    out["S6_exact_k_vs_comparator"] = {"method_exact": sum(ex_m.values()), "comparator_exact": sum(ex_c.values()), "only_method": b_,
                                       "only_comparator": c_, "mcnemar_exact_p": r(mcnemar_exact(b_, c_), 3),
                                       "paired_rate_diff": r(d.mean(), 3), "ci95": [r(x, 3) for x in boot_ci(d)]}
    under = [s for s in comp if ps[s]["k"] is not None and ps[s]["k"] < ps[s]["k_true"]]
    over = [s for s in comp if ps[s]["k"] is not None and ps[s]["k"] > ps[s]["k_true"]]
    out["k_errors"] = {"exact": sum(ex_m.values()), "under": [(s, ps[s]["k"], ps[s]["k_true"]) for s in under], "n_over": len(over)}

    # kick-clip sensitivity (PROTOCOL section 2.2): S2 = median held-out C with and without the kick-clip pairs. As in the profile, a
    # non-finite C counts as the worst value (+inf).
    c_all, c_noclip, n_pairs_clip = [], [], []
    for s in comp:
        v = ps[s]["verdict"]
        c = fnum(v.get("C"))
        sens = (v.get("C_sensitivity") or {}).get("kick_clip") or {}
        c_all.append(c if c is not None else np.inf)
        if sens:
            n_pairs_clip.append(sens.get("n_excluded"))
            ce = fnum(sens.get("C"))
            c_noclip.append(ce if ce is not None else np.inf)
        else:
            c_noclip.append(c if c is not None else np.inf)
    out["kick_clip_sensitivity"] = {"systems_with_excluded_pairs": len(n_pairs_clip), "excluded_pairs_range": [min(n_pairs_clip), max(n_pairs_clip)],
                                    "S2_all_pairs": r(np.median(c_all)), "S2_without_kick_clip": r(np.median(c_noclip)),
                                    "n_C_nonfinite": int(sum(not np.isfinite(x) for x in c_all))}

    out["interventional_fails_only_by_abstention"] = sorted(s for s in comp if not ps[s]["verdict"]["interventional"]
                                                            and ps[s]["verdict"].get("interventional_reason") == "pairs abstained on")
    out["interventional_reasons"] = dict(Counter(ps[s]["verdict"].get("interventional_reason") for s in comp))
    out["systems_with_abstained_heldout_pairs"] = sorted(s for s in comp if (ps[s]["verdict"].get("C_abstained_pairs") or 0) > 0)
    out["events_markov_untested"] = sorted(s for s in ps if ps[s]["verdict"]["markov_detail"].get("events_worst") is None)
    out["interventional_closure_gap_median"] = {"method": r(np.median([fnum(ps[s]["verdict"].get("interventional_closure_gap")) for s in comp
                                                                       if fnum(ps[s]["verdict"].get("interventional_closure_gap")) is not None])),
                                                "comparator": r(np.median([fnum(pc[s]["verdict"].get("interventional_closure_gap")) for s in comp
                                                                           if s in pc and fnum(pc[s]["verdict"].get("interventional_closure_gap")) is not None]))}
    grp = [g for g in FB["I"] if g.get("kind") == "group"]
    out["groups"] = [{"members": g["members"], "verdict": g["verdict"], "k": [ps[s]["k"] for s in g["members"]],
                      "k_true": [ps[s]["k_true"] for s in g["members"]],
                      "shared_params": g["comparison"].get("shared_params"), "independent_params": g["comparison"].get("independent_params")}
                     for g in grp]
    noncomp = [s for s in AG["design"]["systems"] if s not in comp]
    out["noncompressible_controls"] = [{"system": s, "k": ps[s]["k"], "verdict": ps[s]["verdict"]["verdict"],
                                        "abstention": ps[s]["verdict"].get("abstention")} for s in noncomp]
    out["G_synthetic"] = {"n": len(FB["G"]), "k_agree": sum(bool(g.get("k_agree")) for g in FB["G"].values()),
                          "r2_min_mean": {s: r(g.get("r2_min_mean")) for s, g in FB["G"].items()},
                          "prediction_disagreement_max": max(((s, r(g.get("prediction_disagreement_nmse"))) for s, g in FB["G"].items()
                                                              if fnum(g.get("prediction_disagreement_nmse")) is not None), key=lambda x: x[1]),
                          "k": {s: g.get("k") for s, g in FB["G"].items()}}

    # descriptive rankings on the FINAL suite (the pre-registered S1-S5 ranking; PROTOCOL section 9)
    spec = importlib.util.spec_from_file_location("merge_rounds", ROOT / "scripts" / "p3" / "merge_rounds.py")
    mr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mr)
    elig = {mm: AG["profiles"][mm] for mm in AG["profiles"] if AG["eligible"].get(mm)}
    tp = {}
    for mm in elig:
        f = fb / f"{mm}.json"
        if f.exists():
            t = load(f).get("transition_params_median")
            if t is not None:
                tp[mm] = t
    out["final_descriptive_rankings"] = mr.descriptive_rankings(elig, tp)

    # lifting (goal4 sections 45-49) for every model that implements lift(): medians over the compressible systems of the per-system
    # means; the implementation-invariance ratio = future divergence between implementations of the SAME shift / between DIFFERENT
    # shifts, over the systems where it is testable and finite
    lift = {}
    for mm in sorted(AG["profiles"]):
        f = fb / f"{mm}.json"
        if not f.exists():
            continue
        pps = load(f)["per_system"]
        rows = [pps[s]["lift"] for s in comp if isinstance((pps.get(s) or {}).get("lift"), dict) and pps[s]["lift"].get("supported")]
        if not rows:
            continue

        def mean_of(x, key):
            v = x.get(key)
            return fnum(v.get("mean")) if isinstance(v, dict) else fnum(v)

        def inv(x):
            ii = x.get("implementation_invariance")
            if isinstance(ii, dict):
                return fnum(ii.get("ratio")) if ii.get("testable", True) else None
            return fnum(x.get("implementation_invariance_ratio"))
        ach = [v for v in (mean_of(x, "achieved_shift_rel_error") for x in rows) if v is not None]
        aft = [v for v in (mean_of(x, "model_nmse_after_lift") for x in rows) if v is not None]
        twn = [v for v in (mean_of(x, "model_nmse_twin") for x in rows) if v is not None]
        ivs = [v for v in (inv(x) for x in rows) if v is not None]
        lift[mm] = {"systems_lifted": len(rows), "achieved_shift_rel_error_median": r(np.median(ach), 3) if ach else None,
                    "nmse_after_lift_median": r(np.median(aft), 3) if aft else None, "nmse_twin_median": r(np.median(twn), 3) if twn else None,
                    "invariance_ratio_median": r(np.median(ivs), 3) if ivs else None, "invariance_n_testable_finite": len(ivs),
                    "invariance_frac_below_1": r(np.mean(np.array(ivs) < 1), 3) if ivs else None}
    out["lifting"] = lift
    return out


# ------------------------------------------------------------------------------------------------------------------------ round 3 / comparator
def round3() -> dict:
    rd = load(P3 / "tournament" / "r3v3" / "ROUND_DECISION.json")
    comp = rd["comparator"]
    tab = comp["table"]
    pool6 = {m: tab[m]["profile_S1_S5"] for m in comp["pool"] if not m.startswith("ks_hankel")}
    tp = {}
    for m in comp["pool"]:
        f = P3 / "tournament" / f"r3v3_{m}" / f"{m}.json"
        if f.exists():
            t = load(f).get("transition_params_median")
            if t is not None:
                tp[m] = t
    rk6 = rank_profiles(pool6, tp, keys=tuple(comp["components_used"]))
    return {"comparator_pool": comp["pool"], "comparator_order": comp["order"],
            "pool_without_ks_hankel": {"order": rk6["order"], "mean_rank": rk6["mean_rank"], "transition_params": {m: tp.get(m) for m in pool6}},
            "descriptive": rd.get("descriptive"), "selection": rd.get("selection")}


# ------------------------------------------------------------------------------------------------------------------------ counterexamples
def counterexamples() -> dict:
    out = {}
    for d in sorted((P3 / "counterexamples").iterdir()):
        sf = d / "SUMMARY.json"
        if not sf.exists():
            continue
        summ = load(sf)
        systems = summ["systems"]
        rows = defaultdict(list)
        for jf in sorted((d / "jobs").glob("*.json")):
            j = load(jf)
            for row in j["rows"]:
                rows[j["job"]["system"]].append({**row, "strategy": j["job"]["strategy"]})
        cand_all, n_rows = [], Counter()
        worst_small_den, sys_infam, searchable, unsearchable = 0, 0, 0, []
        typical = {}
        for sid, info in systems.items():
            thr = info.get("threshold")
            if not info.get("kinds_supported"):
                unsearchable.append(sid)
            if thr is None or not info.get("kinds_supported"):
                continue
            searchable += 1
            typical[sid] = r(info.get("random_median"))
            rs = rows.get(sid, [])
            rnd = [x for x in rs if x["strategy"] == "random" and fnum(x.get("err")) is not None and x.get("effect_den") is not None]
            if not rnd:
                continue
            mden = float(np.median([x["effect_den"] for x in rnd])) if summ.get("objective") == "effect" else None
            mnum = float(np.median([x["effect_num"] for x in rnd])) if summ.get("objective") == "effect" else None
            cands = [x for x in rs if fnum(x.get("err")) is not None and x["err"] >= thr]
            for x in cands:
                cand_all.append({"small_den": (mden is not None and x["effect_den"] < 0.01 * mden),
                                 "small_num": (mnum is not None and x["effect_num"] <= 10 * mnum),
                                 "post_ok": fnum(x.get("err_post")) is not None and x["err_post"] < 1,
                                 "in_family": all(x["in_family"]), "init": bool(x["init_state"])})
            if cands and mden is not None:
                w = max(cands, key=lambda x: x["err"])
                worst_small_den += w["effect_den"] < 0.01 * mden
            sys_infam += any(all(x["in_family"]) for x in cands)
            for x in rs:
                if fnum(x.get("err")) is None:
                    continue
                isc = x["err"] >= thr
                fam = "in" if all(x["in_family"]) else "out"
                n_rows[f"rows_{fam}"] += 1
                n_rows[f"cand_{fam}"] += isc
                n_rows[f"rows_init_{bool(x['init_state'])}"] += 1
                n_rows[f"cand_init_{bool(x['init_state'])}"] += isc
        n = len(cand_all)
        frac = (lambda key: r(sum(c[key] for c in cand_all) / n, 3) if n else None)
        ov = summ["overall"]
        out[d.name] = {
            "objective": summ.get("objective"), "overall": ov, "n_systems": len(systems), "searchable_systems": searchable,
            "unsearchable_systems": unsearchable, "broken_immediately": ov.get("systems_broken_immediately"),
            "broken_immediately_fraction_all": r(ov.get("systems_broken_immediately", 0) / len(systems), 3),
            "broken_immediately_fraction_searchable": r(ov.get("systems_broken_immediately", 0) / searchable, 3) if searchable else None,
            "candidates": n, "frac_true_effect_below_1pct_of_typical": frac("small_den"),
            "frac_num_le_10x_typical": frac("small_num"), "frac_post_nmse_below_1": frac("post_ok"),
            "frac_all_in_family": frac("in_family"), "worst_per_system_with_small_den": worst_small_den,
            "systems_with_in_family_candidate": sys_infam,
            "candidate_rate_in_family": r(n_rows["cand_in"] / n_rows["rows_in"], 3) if n_rows["rows_in"] else None,
            "candidate_rate_out_of_family": r(n_rows["cand_out"] / n_rows["rows_out"], 3) if n_rows["rows_out"] else None,
            "candidate_rate_init_perturbed": r(n_rows["cand_init_True"] / n_rows["rows_init_True"], 3) if n_rows["rows_init_True"] else None,
            "candidate_rate_init_nominal": r(n_rows["cand_init_False"] / n_rows["rows_init_False"], 3) if n_rows["rows_init_False"] else None,
            "typical_error_random_median": typical,
            "kinds_supported": {sid: info.get("kinds_supported") for sid, info in systems.items()} if d.name.startswith("real") else None,
            "thresholds_real": {sid: r(info.get("threshold")) for sid, info in systems.items()} if d.name.startswith("real") else None,
            "worst_range": [r(min(fnum(i.get("worst")) for i in systems.values() if fnum(i.get("worst")) is not None)),
                            r(max(fnum(i.get("worst")) for i in systems.values() if fnum(i.get("worst")) is not None))],
        }
    v1 = [k for k in out if f"_{M}_" in k]
    tot_b = sum(out[k]["broken_immediately"] for k in v1)
    out["_Q19"] = {"sweeps": v1, "pooled_all": r(tot_b / sum(out[k]["n_systems"] for k in v1), 3),
                   "pooled_searchable": r(tot_b / sum(out[k]["searchable_systems"] for k in v1), 3),
                   "per_sweep": {k: out[k]["broken_immediately_fraction_all"] for k in v1}, "threshold_fail_if_ge": 0.5}
    return out


# ------------------------------------------------------------------------------------------------------------------------ ablations
def _component(ps: dict, s: str, key: str):
    x = ps.get(s) or {}
    v = x.get("verdict") or {}
    if key == "S1":
        return fnum(x.get("A_over_full"))
    if key == "S2":
        return fnum(v.get("C"))
    if key == "S3":                                       # PROTOCOL.md section 9: S3 = max(0, upper 95 % CI of the D micro-gain)
        ci = v.get("D_ci95") or []
        up = fnum(ci[1]) if len(ci) == 2 else None
        return max(0.0, up) if up is not None else None
    if key == "S4":
        return fnum(v.get("E_ratio"))
    if key == "S5":
        k = x.get("K") or {}
        a, b = fnum(k.get("r2_true_from_model_rff")), fnum(k.get("r2_model_from_true_rff"))
        return min(a, b) if a is not None and b is not None else None
    if key == "S6":
        return float(bool((x.get("K_dim") or {}).get("exact")))
    return None


def ablations() -> dict:
    """Per switch: verdict counts (compact split as registered), S7, failures, and MEAN-based paired differences with system-bootstrap
    CIs (descriptive; the pre-registered summary is the median, SUMMARY.md). No multiplicity correction."""
    out = {}
    for run in ("ablations_final", "ablations_dev"):
        d = P3 / "ablations" / run
        summ = load(d / "SUMMARY.json")
        full = load(d / "full.json") if (d / "full.json").exists() else None
        comp = [s for s, x in (full or {}).get("per_system", {}).items() if x.get("k_true") not in (None, "none")]
        rows = {}
        for sw, v in summ["variants"].items():
            vf = load(d / f"{sw}.json") if (d / f"{sw}.json").exists() else {}
            means = {}
            if full and sw != "full" and vf.get("per_system"):
                for key in ("S1", "S2", "S3", "S5", "S6"):
                    dd = []
                    for s in comp:
                        a, b = _component(vf["per_system"], s, key), _component(full["per_system"], s, key)
                        if a is not None and b is not None:
                            dd.append(a - b)
                    if dd:
                        ci = boot_ci(dd)
                        means[key] = {"mean": r(np.mean(dd), 3), "ci95": [r(x, 3) for x in ci], "n": len(dd),
                                      "excludes_0": bool(ci[0] > 0 or ci[1] < 0)}
            stored = {k: {"mean_diff": x.get("mean_diff"), "mean_ci95": x.get("mean_ci95")}
                      for k, x in (v.get("paired_vs_full") or {}).items() if isinstance(x, dict) and "mean_ci95" in x}
            rows[sw] = {"verdict_counts_compressible": v.get("verdict_counts_compressible"), "S7": r(v["profile"].get("S7_abstention")),
                        "abstention": v.get("abstention"), "failures": v.get("failures") or {"fits": vf.get("n_fit_failures"),
                                                                                            "evaluations": vf.get("n_evaluation_failures")},
                        "mean_paired_vs_full_descriptive": means,
                        "stored_summary_mean_ci95": stored}   # the frozen ablation summariser's own mean-based CIs (the ones the report cites)
        out[run] = rows
    return out


def self_audit() -> dict:
    SA = load(P3 / "SELF_AUDIT.json")
    ch = {c["id"]: c for c in SA["checks"]}
    q14 = ch["Q14"]["evidence"]["real_post_over_unperturbed"]
    fin = sorted(v for v in q14.values() if fnum(v) is not None)
    q8 = ch["Q8"]["evidence"]
    q6 = ch["Q6"]["evidence"]["real_closed"]
    return {"Q14_finite_ratios": {k: r(v) for k, v in q14.items()}, "Q14_median_finite": r(np.median(fin)), "Q14_n_finite": len(fin),
            "Q14_n_above_3": sum(v > 3 for v in fin), "Q6_real_not_closed": sum(not v for v in q6.values()),
            "Q8_real_windows_note": "Q8's real CIs are read at the first window key (100 ms); the verdict uses 250 ms",
            "Q8_synthetic_fraction": q8["synthetic_heldout_no_better_than_null_fraction"],
            "thresholds": SA["thresholds"], "counts": SA["counts"]}


def main() -> int:
    rec = {"script": "scripts/p3/postlock_numbers.py", "answer_bearing": True,
           "level_c": level_c(), "final": final_suite(), "round3": round3(), "counterexamples": counterexamples(),
           "ablations": ablations(), "self_audit": self_audit(),
           "calibration_closure_power": load(ROOT / "benchmarks" / "state_discovery_v1" / "calibration.json").get("closure_power")}
    OUT.write_text(json.dumps(rec, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)) + "\n", encoding="utf-8",
                   newline="\n")
    print("wrote", OUT.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
