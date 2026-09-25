"""Evaluation harness (orchestrator side): assemble test sets, fit reference controls, evaluate any StateModel on one system.

Used identically for the pre-registered calibration (reference models only), the tournament (Level B) and the final evaluations
(Level B confirmation, Level C). Families are kept separate in the output.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import evaluate as E
from .data import Dataset, Trajectory
from .refmodels import DirectHorizonModel, FullStateModel, ProjectionLinearModel

# pre-registered evaluation configurations (PROTOCOL.md sections 4 and 8)
REAL_CFG = E.EvalConfig()
SYNTH_CFG = E.EvalConfig(horizons_s=(0.1, 0.25, 0.5, 1.0, 2.0), start_times_s=(0.5, 1.0, 1.5, 2.0), primary_horizon_s=1.0,
                         closure_deltas_s=(0.05, 0.25), closure_task_horizon_s=0.5, closure_history_lags_s=(0.05, 0.1), closure_points_per_traj=12,
                         c_windows_s=(0.25, 0.5, 1.0), primary_c_window_s=1.0, rollout_a_s=0.25, rollout_b_s=1.0, micro_future_s=1.0)

# family roles of the REAL hidden test (PROTOCOL.md section 3)
NON_INTERVENTION = ("H_nominal", "H_init_state")
HELDOUT_INTERVENTION = ("H_kick_B", "H_pulse_B", "H_silence1_B", "H_group_silence")
INDIST_INTERVENTION = ("H_kick_A", "H_pulse_A", "H_silence1_A")
OOD = ("H_stim_ood", "H_weight_ood")
# family roles of the synthetic suites' test split (the generator's hold-out design). Version 2: interventions on the STATE or the
# INPUT (kicks, currents, silencing, their group / new-target / combined forms) make up the held-out C of the verdict; STRUCTURAL
# interventions (edge removal changes the dynamics law itself, "where supported" in goal4 section 11) are scored separately and
# reported, not part of the verdict
SYNTH_ROLES = {"non_intervention": ("init_heldout", "param_heldout", "H_micro"),
               "heldout_intervention": ("kick_group", "current_group", "group_silence", "kick_newtarget", "silence_newtarget",
                                        "combined_heldout"),
               "structural_intervention": ("edge_remove",),
               "indist_intervention": (),
               "ood": ("noise_heldout",)}
REAL_ROLES = {"non_intervention": NON_INTERVENTION, "heldout_intervention": HELDOUT_INTERVENTION, "structural_intervention": (),
              "indist_intervention": INDIST_INTERVENTION, "ood": OOD}
# version 3 (pre-lock reviews B B2, D B3): on MECHANISM systems every observed neuron is a public target (PROTOCOL.md section 3.1), so
# the *_B families use the training targets with hidden parameter draws: they are in-distribution there, and the held-out C of the
# verdict is group silencing only
REAL_ROLES_MECH = {"non_intervention": NON_INTERVENTION, "heldout_intervention": ("H_group_silence",), "structural_intervention": (),
                   "indist_intervention": INDIST_INTERVENTION + ("H_kick_B", "H_pulse_B", "H_silence1_B"), "ood": OOD}


def roles_for(kind: str, mode: str | None = None) -> dict:
    """The family-role table of a system: synthetic suites, real full systems, real mechanism systems (mode 'mech')."""
    if kind == "synthetic":
        return SYNTH_ROLES
    return REAL_ROLES_MECH if mode == "mech" else REAL_ROLES


def key_a(cfg: E.EvalConfig) -> str:
    return f"A_nmse_h{int(round(cfg.primary_horizon_s * 1000))}ms"


def key_c(cfg: E.EvalConfig) -> str:
    return f"C_effect_error_w{int(round(cfg.primary_c_window_s * 1000))}ms"


def pca_basis(train: list[Trajectory], n: int = 10) -> tuple[np.ndarray, np.ndarray]:
    X = np.concatenate([t.x for t in train]).astype(np.float64)
    mean = X.mean(0)
    _, _, Vt = np.linalg.svd(X[::10] - mean, full_matrices=False)
    return mean, Vt[: min(n, Vt.shape[0])]


_MICRO_CACHE: dict[str, tuple] = {}


def _micro_files(micro_dir: Path) -> tuple[list, list, list]:
    """micro_index.json + micro_futures.npz; the futures are stored per restart ("future_<i>", "floor_<i>": readout dimensions differ
    between systems)."""
    key = str(micro_dir.resolve())
    if key not in _MICRO_CACHE:
        idx = json.loads((micro_dir / "micro_index.json").read_text(encoding="utf-8"))
        with np.load(micro_dir / "micro_futures.npz") as z:
            fut = [z[f"future_{i}"] for i in range(len(idx))]
            floor = [z[f"floor_{i}"] for i in range(len(idx))]
        _MICRO_CACHE[key] = (idx, fut, floor)
    return _MICRO_CACHE[key]


def hidden_sets(ds: Dataset, sid: str, micro_dir: Path | None = None) -> dict:
    """{'by_family': {fam: [Trajectory]}, 'pairs': {fam: [(traj, twin)]}, 'pool': [micro pool entries]} for one system."""
    rows = ds.select(system_id=sid)
    by_fam: dict[str, list] = {}
    twins: dict[str, Trajectory] = {}
    tests: dict[str, Trajectory] = {}
    pool_rows = []
    for r in rows:
        if r["split"] == "pool":
            pool_rows.append(r)
            if r["family"] == "H_micro" and not (r["protocol"].get("events") or []):
                # event-free pool trajectories are held-out non-intervention trajectories too (synthetic role "H_micro")
                by_fam.setdefault("H_micro", []).append(ds.load(r))
            continue
        tr = ds.load(r)
        pair = (r.get("info") or {}).get("pair")
        if r["split"] == "twin":
            twins[pair] = tr
        else:
            by_fam.setdefault(r["family"], []).append(tr)
            if pair:
                tests[pair] = tr
    pairs: dict[str, list] = {}
    for pair, tr in tests.items():
        if pair in twins:
            pairs.setdefault(tr.family, []).append((tr, twins[pair]))
    pool = []
    if micro_dir is not None and (micro_dir / "micro_index.json").exists():
        idx, fut, floor = _micro_files(Path(micro_dir))
        by_key = {r["key"]: r for r in pool_rows}
        cache: dict[str, Trajectory] = {}
        for j, m in enumerate(idx):
            if m["system_id"] != sid or m["key"] not in by_key:
                continue
            if m["key"] not in cache:
                cache[m["key"]] = ds.load(by_key[m["key"]])
            tr = cache[m["key"]]
            i = m["index"]
            pool.append({"x_hist": tr.x[: i + 1], "u_hist": tr.u[: i + 1], "y_hist": tr.y[: i + 1], "dt": tr.dt, "y_now": tr.y[i],
                         "future_y": fut[j][1:], "floor_future": floor[j][1:], "group": m["group"], "traj": m["key"],
                         "t_index": int(i)})
    return {"by_family": by_fam, "pairs": pairs, "pool": pool}


def fit_references(sid: str, train: list[Trajectory], observed: list[int], k: int, seed: int = 0) -> dict:
    """The reference controls of PROTOCOL.md section 5, fitted on public training trajectories of one system (the orchestrator passes
    train + val, like a method's fit). Finite blow-up trajectories (evaluate.blowup_mask) are left out of the reference fits."""
    train = [t for t, b in zip(train, E.blowup_mask(train)) if not b] or list(train)
    n_y = train[0].y.shape[1]
    return {"full_state": FullStateModel(observed, n_y, seed=seed).fit(sid, train),
            "input_only": DirectHorizonModel("input_only").fit(sid, train),
            "readout_hist": DirectHorizonModel("readout_hist").fit(sid, train),
            "pca_k": ProjectionLinearModel(k, "pca").fit(sid, train, observed),
            "random_k": ProjectionLinearModel(k, "random", seed=seed).fit(sid, train, observed)}


def e_whiteners(model, sid: str, train: list[Trajectory], cfg: E.EvalConfig, pca: tuple, scale: np.ndarray, k: int | None,
                Z: np.ndarray | None = None) -> dict:
    """Whitening of E's distances from PUBLIC training data (PROTOCOL.md section 4): the model's latent encodings, the scaled readout
    and the PCs of x at the encoding times of up to 64 training trajectories (full covariance, eigenvalue floor). Z: the encodings,
    when the caller has them already."""
    Z = E.encodings_for_whitening(model, sid, train, cfg) if Z is None else Z
    out = {}
    if Z.size and np.isfinite(Z).all() and len(Z) >= 3:
        out["z"] = E.whitener(Z, cfg.whiten_eig_floor)
    rows_y, rows_x = [], []
    for tr in train[:64]:
        for t0 in cfg.start_times_s:
            i = E.idx(t0, tr.dt)
            if i < len(tr.t):
                rows_y.append(tr.y[i] / np.sqrt(scale))
                rows_x.append(tr.x[i])
    if len(rows_y) >= 3:
        out["y"] = E.whitener(np.stack(rows_y).astype(np.float64), cfg.whiten_eig_floor)
        mean_x, comps = pca
        k_eff = int(min(k or (Z.shape[1] if Z.size else 1), comps.shape[0]))
        out["pc"] = E.whitener((np.stack(rows_x).astype(np.float64) - mean_x) @ comps[:k_eff].T, cfg.whiten_eig_floor)
    return out


def evaluate_system(model, sid: str, hs: dict, scale: np.ndarray, pca: tuple, cfg: E.EvalConfig = REAL_CFG, k: int | None = None,
                    families: tuple[str, ...] = ("A", "C", "D", "R", "E", "P"), roles: dict | None = None,
                    train: list[Trajectory] | None = None, observed: list[int] | None = None,
                    alt_scales: dict[str, np.ndarray] | None = None, exclude_keys: dict[str, set] | None = None,
                    roll: E.Fresh | None = None) -> dict:
    """All model-level families for one system. A/B on non-intervention hidden families; C on held-out and in-distribution
    intervention families (separately, and per family) and, apart, on structural interventions; D closure; R rollout checks (closure
    gap, Markov consistency, decoy and readout consistency, noise curve); E microstate equivalence (whitened with `train`, the PUBLIC
    training trajectories; the orchestrator always passes them); P parameter-identity probe; plus OOD robustness (A on OOD families).

    Version 3: every rollout / readout runs on a fresh copy of the model as it was before this call (`E.Fresh`); held-out pairs whose
    events act on neurons outside `observed` are scored apart ("C_heldout_unobserved", descriptive; review B M2) and the verdict's C
    ("C_heldout") uses the others; the mean / variance of the model's encodings of the PUBLIC training data give the scrambled-state
    control of C and the latent scale of the Markov checks; `alt_scales` = alternative normalisers of C reported for sensitivity;
    `exclude_keys` = {name: trajectory keys} for descriptive sensitivity versions of the held-out C without those pairs."""
    roles = roles or REAL_ROLES
    roll = roll if roll is not None else E.Fresh(model)
    out = {}
    Z_train = E.encodings_for_whitening(model, sid, train, cfg) if train else np.zeros((0, 0))
    z_ok = bool(Z_train.size and np.isfinite(Z_train).all() and len(Z_train) >= 3)
    z_mean = Z_train.mean(0) if z_ok else None
    z_var = Z_train.var(0) if z_ok else None
    if z_ok:
        out["Z_train_var"] = z_var.tolist()
    nonint = [t for f in roles["non_intervention"] for t in hs["by_family"].get(f, [])]
    if "A" in families and nonint:
        out["A_B"] = E.eval_predictive(model, sid, nonint, scale, cfg, roll=roll)
    if "C" in families:
        held_all = [p for f in roles["heldout_intervention"] for p in hs["pairs"].get(f, [])]
        if observed is not None:
            held = [p for p in held_all if E.events_observed(p[0], observed)]
            held_unobs = [p for p in held_all if not E.events_observed(p[0], observed)]
        else:
            held, held_unobs = held_all, []
        ind = [p for f in roles["indist_intervention"] for p in hs["pairs"].get(f, [])]
        struct = [p for f in roles.get("structural_intervention", ()) for p in hs["pairs"].get(f, [])]
        out["C_heldout"] = E.eval_intervention(model, sid, held, scale, cfg, roll=roll, z_mean=z_mean, alt_scales=alt_scales) if held else {}
        out["C_heldout_unobserved"] = (E.strip_units(E.eval_intervention(model, sid, held_unobs, scale, cfg, roll=roll, checks=False))
                                       if held_unobs else {})
        out["C_heldout_n_unobserved_pairs"] = len(held_unobs)
        out["C_indist"] = E.eval_intervention(model, sid, ind, scale, cfg, roll=roll, checks=False) if ind else {}
        out["C_structural"] = E.eval_intervention(model, sid, struct, scale, cfg, roll=roll, checks=False) if struct else {}
        out["C_per_family"] = {f: E.strip_units(E.eval_intervention(model, sid, hs["pairs"][f], scale, cfg, roll=roll, checks=False))
                               for f in roles["heldout_intervention"] + roles.get("structural_intervention", ()) + roles["indist_intervention"]
                               if hs["pairs"].get(f)}
        sens = {}
        for name, keys in (exclude_keys or {}).items():
            kept = [p for p in held if p[0].key not in keys]
            if len(kept) < len(held):
                sens[name] = {"n_excluded": len(held) - len(kept),
                              "C": E.strip_units(E.eval_intervention(model, sid, kept, scale, cfg, roll=roll, checks=False)) if kept else {}}
        out["C_heldout_sensitivity"] = sens
    if "D" in families and nonint:
        out["D"] = E.eval_closure(model, sid, nonint, pca, scale, cfg)
    if "R" in families and nonint:
        out["R"] = E.eval_rollout_checks(model, sid, nonint, scale, cfg, roll=roll, z_var=z_var)
    if "E" in families and hs.get("pool"):
        pool = [dict(p) for p in hs["pool"]]
        for p in pool:
            p["floor_div"] = float(np.mean((np.asarray(p["future_y"]) - np.asarray(p["floor_future"])) ** 2 / scale))
        wh = e_whiteners(model, sid, train, cfg, pca, scale, k, Z=Z_train if z_ok else None) if train else None
        out["E"] = E.eval_microstate(model, sid, pool, scale, cfg, pca=pca, k_match=k, whiten=wh)
    if "P" in families and hs.get("pool"):
        out["P_param_probe"] = E.eval_param_probe(model, sid, hs["pool"], cfg)
    ood = {}
    for f in roles["ood"]:
        trs = hs["by_family"].get(f, [])
        if trs:
            ood[f] = E.eval_predictive(model, sid, trs, scale, cfg, roll=roll)
    out["H_ood"] = ood
    return out


# ------------------------------------------------------------------------------------------------------------ verdicts (PROTOCOL.md section 7)
def key_d(cfg: E.EvalConfig) -> str:
    return f"D_y_h{int(round(cfg.closure_task_horizon_s * 1000))}ms_rff"


VERDICT_FULL = "compact causal state discovered"
VERDICT_FULL_E_UNTESTABLE = "compact causal state discovered (microstate equivalence untestable)"
VERDICT_PARTIAL = "partially supported"
VERDICT_NONE = "not supported"


def _upper(ci) -> float:
    try:
        v = float(ci[1])
    except Exception:  # noqa: BLE001
        return float("nan")
    return v


def _markov_events_ok(res: dict) -> tuple[bool | None, float | None]:
    """The restart check after interventions (eval_intervention 'markov_events'), z relative to the variance of the model's encodings
    of the public training data."""
    mk = (res.get("C_heldout") or {}).get("markov_events") or {}
    if not mk.get("n"):
        return None, None
    y = mk.get("y_nmse_max")
    zsq = mk.get("z_sq_mean")
    var = res.get("Z_train_var")
    worst = float(y) if y is not None else float("inf")
    if zsq is not None and var is not None and len(zsq) == len(var):
        v = np.asarray(var, float)
        v = np.maximum(v, 1e-6 * float(np.max(v)) + 1e-12)
        worst = max(worst, float(np.max(np.asarray(zsq, float) / v)))
    elif zsq is not None:
        worst = max(worst, float("inf"))
    return bool(np.isfinite(worst) and worst <= E.MARKOV_TOL), worst


def verdict(res: dict, refs: dict, taus: dict, n_observed: int, k: int | None, mode: str, cfg: E.EvalConfig, abstain: dict | None = None,
            n_boot: int = 2000) -> dict:
    """Per-system verdict of a model (PROTOCOL.md section 7, benchmark version 3). res / refs[name]: evaluate_system outputs (with
    "_units"); taus: tau_A, tau_C, tau_D, tau_E, tau_H, tau_gap from the pre-registered calibration. mode 'synthetic' / 'full' judges
    compression, 'mech' does not (too few neurons); 'full' and 'mech' are the REAL systems.
    - markov_ok: the event-free restart and decoy checks (R) and the restart after interventions stay within evaluate.MARKOV_TOL; a
      model that fails carries memory beyond z: its k is invalid (k_valid False), and compact and closed are False;
    - predictive: synthetic: A <= A_full (1 + tau_A) and A below the input-only and readout-history controls (paired CIs of the
      differences below 0). Real (review D B2): A below the input-only control and the persistence floor (paired CIs below 0); the
      readout-history control and the full-state REFERENCE are reported, not judged;
    - interventional: on the held-out STATE / INPUT interventions with OBSERVED targets (real mechanism systems: group silencing only):
      the upper CI of C < 1 (tau_C does not bind: C <= tau_C is kept for the record), the largest leave-one-pair-out C < 1 (the claim
      does not rest on one pair), no pair abstained on; None (untestable) with fewer than 3 pairs in the primary window. The claim is
      "held-out intervention effects predicted better than no effect"; 'state_mediated' (descriptive) = C significantly below C with z0
      replaced by the mean training encoding;
    - closed: markov_ok, the upper CI of the D micro-gain <= tau_D, the upper CI of the D history gain <= tau_H and the closure gap
      (y NMSE, restart from the re-encoded true history) <= tau_gap;
    - microstate-equivalent: the upper CI of E <= tau_E; None when E is untestable (evaluate.eval_microstate);
    - a model that declares causal_equivalence_failed or no_compact_state for the system cannot receive a 'compact causal state'
      verdict."""
    from .evaluate_cross import paired_diff
    ka, kc, kd = key_a(cfg), key_c(cfg), key_d(cfg)
    real = mode in ("full", "mech")
    ab = abstain or {}
    out: dict = {"k": k, "n_observed": n_observed, "benchmark_version": 3, "system_kind": "real" if real else "synthetic"}
    # ---- Markov / state validity
    rr = res.get("R") or {}
    r_ok = rr.get("markov_ok")
    ev_ok, ev_worst = _markov_events_ok(res)
    out["markov_detail"] = {"rollout_z_rel": rr.get("markov_rollout_inconsistency_rel"), "rollout_y_nmse": rr.get("markov_y_inconsistency_nmse"),
                            "decoy_y_nmse": rr.get("decoy_y_inconsistency_nmse"), "events_worst": ev_worst,
                            "readout_nmse": rr.get("readout_inconsistency_nmse")}
    out["markov_ok"] = bool(r_ok is True and ev_ok is not False)
    out["k_valid"] = out["markov_ok"]
    out["compact"] = None if mode == "mech" else bool(k is not None and k <= max(1, n_observed / 5) and out["markov_ok"])
    # ---- predictive
    a = (res.get("A_B") or {}).get(ka, {}).get("mean", float("nan"))
    a_full = (refs.get("full_state", {}).get("A_B") or {}).get(ka, {}).get("mean", float("nan"))
    out["A"], out["A_full"] = a, a_full
    out["A_levelcorr"] = (res.get("A_B") or {}).get(ka.replace("A_nmse", "A_levelcorr_nmse"), {}).get("mean")
    units_a = ((res.get("A_B") or {}).get("_units") or {}).get(ka, {})
    judged = ("input_only", "persistence") if real else ("input_only", "readout_hist")
    shortcut_ok = True
    for name in ("input_only", "readout_hist", "persistence"):
        ref_units = ((refs.get(name, {}).get("A_B") or {}).get("_units") or {}).get(ka, {})
        if not ref_units:
            if name in judged:
                shortcut_ok = False
            continue
        d = paired_diff(units_a, ref_units, n_boot)
        out[f"A_minus_{name}"] = d
        if name in judged:
            shortcut_ok = shortcut_ok and bool(np.isfinite(d["ci95"][1]) and d["ci95"][1] < 0)
    out["predictive_basis"] = ("real: below input-only and persistence (paired CIs); full-state reference and readout-history descriptive"
                               if real else "synthetic: A <= A_full (1 + tau_A), below input-only and readout-history (paired CIs)")
    if real:
        out["predictive"] = bool(np.isfinite(a) and shortcut_ok)
    else:
        out["predictive"] = bool(np.isfinite(a) and np.isfinite(a_full) and a <= a_full * (1 + taus["tau_A"]) and shortcut_ok)
    # ---- interventional
    ch = res.get("C_heldout") or {}
    c = ch.get(kc, {})
    out["C"], out["C_ci95"] = c.get("ratio", float("nan")), c.get("ci95", [float("nan")] * 2)
    n_abst = ch.get("n_abstained_unsupported", 0)
    out["C_abstained_pairs"] = n_abst
    out["C_n_pairs_primary"] = c.get("n", 0)
    out["C_n_eff"] = c.get("n_eff")
    out["C_loo_max"] = c.get("loo_max")
    out["C_null_pairs"] = c.get("n_null")
    out["C_nonnull"] = c.get("ratio_nonnull")
    out["C_scrambled_mean"] = c.get("scrambled_mean")
    out["C_scrambled_perm"] = c.get("scrambled_perm")
    ms = c.get("minus_scrambled_mean") or {}
    out["C_minus_scrambled_mean_ci95"] = ms.get("ci95")
    out["state_mediated"] = (bool(np.isfinite(_upper(ms.get("ci95"))) and _upper(ms.get("ci95")) < 0) if ms else None)
    out["C_alt_scales"] = c.get("alt_scales")
    out["C_unobserved_targets"] = ((res.get("C_heldout_unobserved") or {}).get(kc) or {}).get("ratio")
    out["C_n_unobserved_pairs"] = res.get("C_heldout_n_unobserved_pairs")
    out["C_sensitivity"] = {nm: {"n_excluded": v.get("n_excluded"), "C": ((v.get("C") or {}).get(kc) or {}).get("ratio")}
                            for nm, v in (res.get("C_heldout_sensitivity") or {}).items()}
    out["interventional_closure_gap"] = (ch.get("interventional_closure_gap") or {}).get("ratio")
    out["C_below_tau_C"] = bool(np.isfinite(out["C"]) and out["C"] <= taus["tau_C"])
    if not ch or out["C_n_pairs_primary"] < 3 or ch.get("n_pairs", 0) <= n_abst:
        out["interventional"] = None if n_abst == 0 else False
        out["interventional_reason"] = ("pairs abstained on" if n_abst else "untestable: fewer than 3 held-out pairs in the primary window")
    else:
        upper_ok = bool(np.isfinite(_upper(out["C_ci95"])) and _upper(out["C_ci95"]) < 1)
        loo_ok = bool(out["C_loo_max"] is not None and np.isfinite(out["C_loo_max"]) and out["C_loo_max"] < 1)
        out["interventional"] = bool(out["C_below_tau_C"] and upper_ok and loo_ok and n_abst == 0)
        out["interventional_reason"] = ("ok" if out["interventional"] else
                                        "; ".join(r for r, bad in (("upper CI of C >= 1", not upper_ok), ("leave-one-pair-out C >= 1", not loo_ok),
                                                                   ("pairs abstained on", n_abst > 0), ("C > tau_C", not out["C_below_tau_C"])) if bad))
    cs = (res.get("C_structural") or {}).get(kc, {})
    out["C_structural"], out["C_structural_ci95"] = cs.get("ratio"), cs.get("ci95")
    out["C_structural_abstained_pairs"] = (res.get("C_structural") or {}).get("n_abstained_unsupported")
    # ---- closed
    dres = (res.get("D") or {}).get(kd) or {}
    dg = dres.get("micro_gain", float("nan"))
    out["D_micro_gain"], out["D_ci95"] = dg, dres.get("micro_gain_ci95", [float("nan")] * 2)
    out["D_history_gain"], out["D_history_ci95"] = dres.get("history_gain", float("nan")), dres.get("history_gain_ci95", [float("nan")] * 2)
    out["closure_gap_y"] = rr.get("closure_gap_y_nmse", float("nan"))
    d_ok = bool(np.isfinite(dg) and np.isfinite(_upper(out["D_ci95"])) and _upper(out["D_ci95"]) <= taus["tau_D"])
    h_ok = bool(np.isfinite(_upper(out["D_history_ci95"])) and _upper(out["D_history_ci95"]) <= taus["tau_H"])
    if taus.get("tau_gap") is None:                   # the calibration found no power in the gap: reported, not judged (PROTOCOL 6)
        g_ok = True
    else:
        g_ok = bool(out["closure_gap_y"] is not None and np.isfinite(out["closure_gap_y"]) and out["closure_gap_y"] <= taus["tau_gap"])
    out["closed_parts"] = {"markov_ok": out["markov_ok"], "micro_gain": d_ok, "history_gain": h_ok, "closure_gap": g_ok}
    out["closed"] = bool(out["markov_ok"] and d_ok and h_ok and g_ok)
    # ---- microstate equivalence
    er = res.get("E") or {}
    e = er.get("E_ratio_latent_to_random", float("nan"))
    out["E_ratio"], out["E_ci95"] = e, er.get("E_ratio_ci95", [float("nan")] * 2)
    out["E_testable"] = er.get("E_testable", bool(er))
    out["E_untestable_reason"] = er.get("E_untestable_reason")
    if er and out["E_testable"] is False:
        out["microstate_equivalent"] = None
    else:
        out["microstate_equivalent"] = bool(np.isfinite(e) and np.isfinite(_upper(out["E_ci95"])) and _upper(out["E_ci95"]) <= taus["tau_E"])
    # ---- descriptive robustness
    nc = rr.get("noise_curve") or {}
    out["noise_fragility_0.05"] = (float(nc["0.05"]) / float(nc["0"]) if nc.get("0") and nc.get("0.05") is not None and float(nc["0"]) > 0
                                   else None)
    # ---- verdict
    out["declared_failure"] = bool(ab.get("causal_equivalence_failed") or ab.get("no_compact_state"))
    compact_ok = out["compact"] is not False
    core = [out["predictive"], out["interventional"] is True, out["closed"]]
    if not out["declared_failure"] and compact_ok and all(core) and out["microstate_equivalent"] is True:
        out["verdict"] = VERDICT_FULL
    elif not out["declared_failure"] and compact_ok and all(core) and out["microstate_equivalent"] is None:
        out["verdict"] = VERDICT_FULL_E_UNTESTABLE
    elif out["predictive"] and (out["interventional"] is True or out["closed"]):
        out["verdict"] = VERDICT_PARTIAL
    else:
        out["verdict"] = VERDICT_NONE
    out["abstention"] = ab
    return out
#END_OF_FILE_MARKER
