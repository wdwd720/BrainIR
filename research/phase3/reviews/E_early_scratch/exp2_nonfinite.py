"""A drops non-finite per-trajectory values (evaluate.boot_mean filters isfinite; paired_diff drops non-finite d). A model that
returns NaN on its hardest trajectories gets a BETTER A, a better A/A_full (S1) and still passes the shortcut tests."""
import sys; sys.path.insert(0, ".tmp/E")
from common import *
from brainir_state.evaluate_cross import paired_diff
class Dodger:
    def __init__(self, m, thr): self.m, self.thr = m, thr
    def encode(self, *a): return self.m.encode(*a)
    def readout(self, *a): return self.m.readout(*a)
    def supports(self, *a): return self.m.supports(*a)
    def rollout(self, sid, z0, u, ev, dt):
        out = self.m.rollout(sid, z0, u, ev, dt)
        if np.linalg.norm(z0) > self.thr:              # "hard" (far-from-training) start states: return NaN instead of a bad guess
            out = {"z": out["z"] * np.nan, "y": out["y"] * np.nan}
        return out
for sid in sorted(CAL)[:8]:
    k = CAL[sid]["k"]; train, hs, scale, pca = setup(sid)
    m = ProjectionLinearModel(k, "pca").fit(sid, train, ds.systems[sid]["observed"])
    nonint = [t for f in SYNTH_ROLES["non_intervention"] for t in hs["by_family"].get(f, [])]
    Z = np.concatenate([[m.encode(sid, t.x[: E.idx(s, t.dt) + 1], None, t.dt) for s in SYNTH_CFG.start_times_s] for t in nonint])
    thr = np.percentile(np.linalg.norm(Z, axis=1), 70)
    io = DirectHorizonModel("input_only").fit(sid, train)
    ra = E.eval_predictive(m, sid, nonint, scale, SYNTH_CFG); rd = E.eval_predictive(Dodger(m, thr), sid, nonint, scale, SYNTH_CFG)
    ri = E.eval_predictive(io, sid, nonint, scale, SYNTH_CFG)
    ka = key_a(SYNTH_CFG)
    pa = paired_diff(ra["_units"][ka], ri["_units"][ka]); pdd = paired_diff(rd["_units"][ka], ri["_units"][ka])
    print(f"{sid} honest A={ra[ka]['mean']:.4f} (n={ra[ka]['n']}), NaN-dodger A={rd[ka]['mean']:.4f} (n={rd[ka]['n']}/{len(nonint)}); "
          f"shortcut diff CI honest {np.round(pa['ci95'],4)} dodger {np.round(pdd['ci95'],4)} n={pdd['n']}")
