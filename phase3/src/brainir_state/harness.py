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
# family roles of the synthetic suites' test split (the generator's hold-out design)
SYNTH_ROLES = {"non_intervention": ("init_heldout", "param_heldout", "H_micro"),
               "heldout_intervention": ("kick_group", "current_group", "group_silence", "edge_remove", "kick_newtarget",
                                        "silence_newtarget", "combined_heldout"),
               "indist_intervention": (),
               "ood": ("noise_heldout",)}
REAL_ROLES = {"non_intervention": NON_INTERVENTION, "heldout_intervention": HELDOUT_INTERVENTION,
              "indist_intervention": INDIST_INTERVENTION, "ood": OOD}


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
    """The reference controls of PROTOCOL.md section 5, fitted on public training trajectories of one system."""
    n_y = train[0].y.shape[1]
    return {"full_state": FullStateModel(observed, n_y, seed=seed).fit(sid, train),
            "input_only": DirectHorizonModel("input_only").fit(sid, train),
            "readout_hist": DirectHorizonModel("readout_hist").fit(sid, train),
            "pca_k": ProjectionLinearModel(k, "pca").fit(sid, train, observed),
            "random_k": ProjectionLinearModel(k, "random", seed=seed).fit(sid, train, observed)}


def evaluate_system(model, sid: str, hs: dict, scale: np.ndarray, pca: tuple, cfg: E.EvalConfig = REAL_CFG, k: int | None = None,
                    families: tuple[str, ...] = ("A", "C", "D", "R", "E", "P"), roles: dict | None = None) -> dict:
    """All model-level families for one system. A/B on non-intervention hidden families; C on held-out and in-distribution
    intervention families (separately, and per family); D closure; R rollout checks (closure gap, Markov consistency, noise
    curve); E microstate equivalence; P parameter-identity probe; plus OOD robustness (A and C on OOD families)."""
    roles = roles or REAL_ROLES
    out = {}
    nonint = [t for f in roles["non_intervention"] for t in hs["by_family"].get(f, [])]
    if "A" in families and nonint:
        out["A_B"] = E.eval_predictive(model, sid, nonint, scale, cfg)
    if "C" in families:
        held = [p for f in roles["heldout_intervention"] for p in hs["pairs"].get(f, [])]
        ind = [p for f in roles["indist_intervention"] for p in hs["pairs"].get(f, [])]
        out["C_heldout"] = E.eval_intervention(model, sid, held, scale, cfg) if held else {}
        out["C_indist"] = E.eval_intervention(model, sid, ind, scale, cfg) if ind else {}
        out["C_per_family"] = {f: E.strip_units(E.eval_intervention(model, sid, hs["pairs"][f], scale, cfg))
                               for f in roles["heldout_intervention"] + roles["indist_intervention"] if hs["pairs"].get(f)}
    if "D" in families and nonint:
        out["D"] = E.eval_closure(model, sid, nonint, pca, scale, cfg)
    if "R" in families and nonint:
        out["R"] = E.eval_rollout_checks(model, sid, nonint, scale, cfg)
    if "E" in families and hs.get("pool"):
        pool = [dict(p) for p in hs["pool"]]
        for p in pool:
            p["floor_div"] = float(np.mean((np.asarray(p["future_y"]) - np.asarray(p["floor_future"])) ** 2 / scale))
        out["E"] = E.eval_microstate(model, sid, pool, scale, cfg, pca=pca, k_match=k)
    if "P" in families and hs.get("pool"):
        out["P_param_probe"] = E.eval_param_probe(model, sid, hs["pool"], cfg)
    ood = {}
    for f in roles["ood"]:
        trs = hs["by_family"].get(f, [])
        if trs:
            ood[f] = E.eval_predictive(model, sid, trs, scale, cfg)
    out["H_ood"] = ood
    return out


# ------------------------------------------------------------------------------------------------------------ verdicts (PROTOCOL.md section 7)
def key_d(cfg: E.EvalConfig) -> str:
    return f"D_y_h{int(round(cfg.closure_task_horizon_s * 1000))}ms_rff"


def verdict(res: dict, refs: dict, taus: dict, n_observed: int, k: int | None, mode: str, cfg: E.EvalConfig, abstain: dict | None = None,
            n_boot: int = 2000) -> dict:
    """Per-system verdict of a model. res / refs[name]: evaluate_system outputs (with "_units"); taus: tau_A, tau_C, tau_D, tau_E from
    the pre-registered calibration. mode 'full' / 'synthetic' judges compression, 'mech' does not (too few neurons)."""
    from .evaluate_cross import paired_diff
    ka, kc, kd = key_a(cfg), key_c(cfg), key_d(cfg)
    out: dict = {"k": k, "n_observed": n_observed}
    a = (res.get("A_B") or {}).get(ka, {}).get("mean", float("nan"))
    a_full = (refs.get("full_state", {}).get("A_B") or {}).get(ka, {}).get("mean", float("nan"))
    out["compact"] = None if mode == "mech" else bool(k is not None and k <= max(1, n_observed / 5))
    shortcut_ok = True
    for name in ("input_only", "readout_hist"):
        d = paired_diff(((res.get("A_B") or {}).get("_units") or {}).get(ka, {}), ((refs.get(name, {}).get("A_B") or {}).get("_units") or {}).get(ka, {}),
                        n_boot)
        out[f"A_minus_{name}"] = d
        shortcut_ok = shortcut_ok and bool(np.isfinite(d["ci95"][1]) and d["ci95"][1] < 0)
    out["A"], out["A_full"] = a, a_full
    out["predictive"] = bool(np.isfinite(a) and np.isfinite(a_full) and a <= a_full * (1 + taus["tau_A"]) and shortcut_ok)
    c = (res.get("C_heldout") or {}).get(kc, {})
    out["C"], out["C_ci95"] = c.get("ratio", float("nan")), c.get("ci95", [float("nan")] * 2)
    n_abst = (res.get("C_heldout") or {}).get("n_abstained_unsupported", 0)
    out["C_abstained_pairs"] = n_abst
    out["interventional"] = bool(np.isfinite(out["C"]) and out["C"] <= taus["tau_C"] and np.isfinite(out["C_ci95"][1]) and out["C_ci95"][1] < 1
                                 and n_abst == 0)
    dg = ((res.get("D") or {}).get(kd) or {}).get("micro_gain", float("nan"))
    out["D_micro_gain"] = dg
    out["closed"] = bool(np.isfinite(dg) and dg <= taus["tau_D"])
    e = (res.get("E") or {}).get("E_ratio_latent_to_random", float("nan"))
    out["E_ratio"] = e
    out["microstate_equivalent"] = bool(np.isfinite(e) and e <= taus["tau_E"])
    conds = [out["predictive"], out["interventional"], out["closed"], out["microstate_equivalent"]]
    compact_ok = out["compact"] is not False
    if compact_ok and all(conds):
        out["verdict"] = "compact causal state discovered"
    elif out["predictive"] and (out["interventional"] or out["closed"]):
        out["verdict"] = "partially supported"
    else:
        out["verdict"] = "not supported"
    out["abstention"] = abstain or {}
    return out
