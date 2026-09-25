"""Reviewer A: does the evaluator detect a model that carries memory beyond its reported z?
Base = the saved seed-0 brainir_state_v1 model of a system (k_b). Two wrappers report k = 1:
- Hidden: rollout carries the other k_b - 1 coordinates internally (initialised at their training mean);
- Stash: encode() stores the full k_b-dim encoding in the object; rollout() uses it when z0 matches (a side channel).
Honest = brainir_state_v1 forced to k = 1. Compare A, D (verdict key), R (closure gap, Markov inconsistency), verdict-relevant parts."""
import json, pickle, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, "src")
from brainir_state import evaluate as E
from brainir_state.api import StateModel
from brainir_state.data import Dataset
from brainir_state.harness import SYNTH_CFG, SYNTH_ROLES, hidden_sets, pca_basis, key_a, key_d, evaluate_system
from brainir_state.methods.brainir_state_v1 import BrainIRStateV1

DEV = Path("data/synthetic_dev")
ds = Dataset(DEV)
cfg = SYNTH_CFG
sid = sys.argv[1]
base = pickle.load(open(f".tmp/A/models/{sid}_s0.pkl", "rb"))
kb = base.k[sid]
tr = [ds.load(r) for r in ds.select(system_id=sid, split="train")]
va = [ds.load(r) for r in ds.select(system_id=sid, split="val")]
zmean = np.mean([E.encode_at(base, sid, t, i) for t in tr for i in (50, 100, 150, 200)], axis=0)


class Hidden(StateModel):
    def __init__(self, stash=False):
        self.k = {sid: 1}
        self.stash = stash
        self._s = None

    def encode(self, s, x, u, dt):
        z = base.encode(s, x, u, dt)
        if self.stash:
            self._s = z.copy()
        return z[:1]

    def _full(self, z0):
        if self.stash and self._s is not None and np.allclose(z0, self._s[:1]):
            return self._s
        return np.concatenate([z0, zmean[1:]])

    def rollout(self, s, z0, u, ev, dt):
        out = base.rollout(s, self._full(np.asarray(z0, float)), u, ev, dt)
        return {"z": np.asarray(out["z"])[:, :1], "y": out["y"]}

    def readout(self, s, z, u):
        z = np.asarray(z, float)
        pad = np.broadcast_to(zmean[1:], z.shape[:-1] + (kb - 1,))
        return base.readout(s, np.concatenate([z, pad], -1), u)

    def supports(self, s, kind):
        return base.supports(s, kind)

    def info(self):
        return {"k": {sid: 1}}


p1 = Path(f".tmp/A/models/{sid}_k1.pkl")
if p1.exists():
    honest = pickle.load(open(p1, "rb"))
else:
    honest = BrainIRStateV1().fit(tr + va, systems=ds.systems, config={"k": 1}, seed=0)
    pickle.dump(honest, open(p1, "wb"))
hs = hidden_sets(ds, sid, DEV)
scale, pca = E.readout_scale(tr), pca_basis(tr)
for name, m in (("base_k%d" % kb, base), ("honest_k1", honest), ("hidden_k1", Hidden(False)), ("stash_k1", Hidden(True))):
    r = evaluate_system(m, sid, hs, scale, pca, cfg, k=1, families=("A", "C", "D", "R"), roles=SYNTH_ROLES, train=tr)
    d = r["D"].get(key_d(cfg), {})
    c = (r.get("C_heldout") or {}).get("C_effect_error_w1000ms", {})
    row = {"sid": sid, "model": name, "A": r["A_B"][key_a(cfg)]["mean"], "C": c.get("ratio"), "C_ci": c.get("ci95"),
           "D": d.get("micro_gain"), "D_ci": d.get("micro_gain_ci95"),
           "gap_y": r["R"]["closure_gap_y_nmse"], "gap_z": r["R"]["closure_gap_z_rel"], "markov_incons": r["R"]["markov_rollout_inconsistency_rel"]}
    print(json.dumps(row), flush=True)
    with open(".tmp/A/stash.jsonl", "a") as fh:
        fh.write(json.dumps(row) + "\n")
