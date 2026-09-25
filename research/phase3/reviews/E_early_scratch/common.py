import json, sys, time, numpy as np
sys.path.insert(0, "src")
from pathlib import Path
from brainir_state import evaluate as E
from brainir_state.data import Dataset
from brainir_state.harness import SYNTH_CFG, SYNTH_ROLES, hidden_sets, pca_basis, evaluate_system, key_a, key_c, key_d
from brainir_state.refmodels import ProjectionLinearModel, DirectHorizonModel
DEV = Path("data/synthetic_dev")
ds = Dataset(DEV)
CAL = {r["sid"]: r for r in json.load(open("extra/benchmark/calibration.json"))["per_system"]}
def setup(sid):
    train = [ds.load(r) for r in ds.select(system_id=sid, split="train")]
    hs = hidden_sets(ds, sid, DEV)
    return train, hs, E.readout_scale(train), pca_basis(train)
