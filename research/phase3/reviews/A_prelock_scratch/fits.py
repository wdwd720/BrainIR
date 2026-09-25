"""Reviewer A: fit brainir_state_v1 with seeds 0-2 on dev systems; record k, R checks, D, G. Output: .tmp/A/fits.jsonl"""
import json, pickle, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, "src")
from brainir_state import evaluate as E
from brainir_state.data import Dataset
from brainir_state.harness import SYNTH_CFG, SYNTH_ROLES, hidden_sets, pca_basis, key_d
from brainir_state.evaluate_cross import eval_reproducibility
from brainir_state.methods.brainir_state_v1 import BrainIRStateV1

DEV = Path("data/synthetic_dev")
OUT = Path(".tmp/A"); (OUT / "models").mkdir(parents=True, exist_ok=True)
ds = Dataset(DEV)
CAL = {r["sid"]: r for r in json.load(open("extra/benchmark/calibration.json"))["per_system"]}
sids = sys.argv[1].split(",")
seeds = [int(s) for s in sys.argv[2].split(",")]
cfg = SYNTH_CFG
for sid in sids:
    tr = [ds.load(r) for r in ds.select(system_id=sid, split="train")]
    va = [ds.load(r) for r in ds.select(system_id=sid, split="val")]
    hs = hidden_sets(ds, sid, DEV)
    nonint = [t for f in SYNTH_ROLES["non_intervention"] for t in hs["by_family"].get(f, [])]
    scale, pca = E.readout_scale(tr), pca_basis(tr)
    models = []
    for seed in seeds:
        p = OUT / "models" / f"{sid}_s{seed}.pkl"
        t0 = time.time()
        if p.exists():
            m = pickle.load(open(p, "rb"))
        else:
            m = BrainIRStateV1().fit(tr + va, systems=ds.systems, seed=seed)
            pickle.dump(m, open(p, "wb"))
        models.append(m)
        info = m.info()
        row = {"sid": sid, "seed": seed, "k": info["k"][sid], "k_range": info["k_range"][sid], "k_true": CAL.get(sid, {}).get("k"),
               "abstain": info["abstain"][sid].get("no_compact_state"), "fit_s": time.time() - t0,
               "k_nn": info["config"][sid]["k_nn_rule"], "k_ks": info["config"][sid]["k_ks_rule"],
               "curve": [(c["k"], round(c["val_nmse"], 4)) for c in info["dim_curve"][sid]],
               "lags": info["config"][sid]["lags"], "deg": info["config"][sid]["deg"]}
        R = E.eval_rollout_checks(m, sid, nonint, scale, cfg)
        row["R"] = R
        if seed == seeds[0]:
            D = E.eval_closure(m, sid, nonint, pca, scale, cfg)
            d = D.get(key_d(cfg), {})
            row["D"] = {kk: d.get(kk) for kk in ("micro_gain", "micro_gain_ci95", "history_gain", "history_gain_ci95")}
            dz = D.get("D_z_d250ms_rff", {})
            row["Dz250"] = {kk: dz.get(kk) for kk in ("micro_gain", "micro_gain_ci95")}
        print(json.dumps(row), flush=True)
        with open(OUT / "fits.jsonl", "a") as fh:
            fh.write(json.dumps(row) + "\n")
    if len(models) > 1:
        G = eval_reproducibility(models, sid, va, nonint, scale, cfg)
        g = {"sid": sid, "G": {kk: G[kk] for kk in ("k", "k_agree", "cca_mean", "r2_min_mean", "prediction_disagreement_nmse")}}
        print(json.dumps(g), flush=True)
        with open(OUT / "fits.jsonl", "a") as fh:
            fh.write(json.dumps(g) + "\n")
