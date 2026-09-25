"""Reviewer A: does the verdict's closure condition (micro-gain of x_t PCs) see non-Markov projections? D micro-gain vs history gain for
the PCA-k and random-k reference models (k = true k) and the seed-0 brainir model."""
import json, pickle, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, "src")
from brainir_state import evaluate as E
from brainir_state.data import Dataset
from brainir_state.harness import SYNTH_CFG, SYNTH_ROLES, hidden_sets, pca_basis, key_d
from brainir_state.refmodels import ProjectionLinearModel

DEV = Path("data/synthetic_dev")
ds = Dataset(DEV)
cfg = SYNTH_CFG
CAL = {r["sid"]: r for r in json.load(open("extra/benchmark/calibration.json"))["per_system"]}
tau_D = json.load(open("extra/benchmark/calibration.json"))["tolerances"]["tau_D"]
for sid in sys.argv[1].split(","):
    tr = [ds.load(r) for r in ds.select(system_id=sid, split="train")]
    va = [ds.load(r) for r in ds.select(system_id=sid, split="val")]
    hs = hidden_sets(ds, sid, DEV)
    nonint = [t for f in SYNTH_ROLES["non_intervention"] for t in hs["by_family"].get(f, [])]
    scale, pca = E.readout_scale(tr), pca_basis(tr)
    obs = ds.systems[sid]["observed"]
    kt = int(CAL[sid]["k"])
    models = {f"pca_k{kt}": ProjectionLinearModel(kt, "pca").fit(sid, tr + va, obs),
              f"random_k{kt}": ProjectionLinearModel(kt, "random", seed=0).fit(sid, tr + va, obs)}
    p = Path(f".tmp/A/models/{sid}_s0.pkl")
    if p.exists():
        models["brainir_s0"] = pickle.load(open(p, "rb"))
    for name, m in models.items():
        D = E.eval_closure(m, sid, nonint, pca, scale, cfg).get(key_d(cfg), {})
        row = {"sid": sid, "trap": CAL[sid]["trap"], "family": CAL[sid]["family"], "model": name,
               "micro": D.get("micro_gain"), "micro_ci": D.get("micro_gain_ci95"), "hist": D.get("history_gain"), "hist_ci": D.get("history_gain_ci95"),
               "closed_verdict": bool(D.get("micro_gain_ci95", [0, 9])[1] <= tau_D)}
        print(json.dumps(row), flush=True)
        with open(".tmp/A/hist.jsonl", "a") as fh:
            fh.write(json.dumps(row) + "\n")
