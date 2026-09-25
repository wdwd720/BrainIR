import sys, json, pickle, dataclasses, numpy as np
sys.path.insert(0, 'src')
from pathlib import Path
from brainir_state.data import Dataset
from brainir_state import evaluate as E
from brainir_state.harness import SYNTH_CFG, hidden_sets
cfg = dataclasses.replace(SYNTH_CFG, n_boot=10)
pools = pickle.load(open('.tmp/H/pools_dev.pkl', 'rb'))
cal = {r['sid']: r for r in json.load(open('extra/benchmark/calibration.json'))['per_system']}
ds = Dataset('data/synthetic_dev')
class Z:
    uses_readout = False
    def __init__(self, t): self.t = t
    def encode(self, sid, x_hist, u_hist, dt): return self.t[np.asarray(x_hist[-1], np.float32).tobytes()]
tau = 0.003909120967901428
flip = {'mix': 0, 'tiny': 0}; n = 0; rows = []
for sid in sorted(cal):
    name, rs = pools[sid]
    if cal[sid]['k'] < 2: continue
    train = [ds.load(r) for r in ds.select(system_id=sid, split='train')]
    scale = E.readout_scale(train)
    pool = hidden_sets(ds, sid, Path('data/synthetic_dev'))['pool']
    zt = {(r['key'], r['index']): np.asarray(r['z_state'], float) for r in rs}
    base = {np.asarray(p['x_hist'][-1], np.float32).tobytes(): zt[(p['traj'], p['t_index'])] for p in pool}
    k = cal[sid]['k']; rng = np.random.default_rng(1)
    # an invertible linear reparametrisation with condition number 10 (rotation - anisotropic scaling - rotation)
    Q1, _ = np.linalg.qr(rng.standard_normal((k, k))); Q2, _ = np.linalg.qr(rng.standard_normal((k, k)))
    A = Q1 @ np.diag(np.geomspace(1, 0.1, k)) @ Q2
    e0 = E.eval_microstate(Z(base), sid, pool, scale, cfg)['E_ratio_latent_to_random']
    e1 = E.eval_microstate(Z({kk: A @ v for kk, v in base.items()}), sid, pool, scale, cfg)['E_ratio_latent_to_random']
    n += 1; flip['mix'] += (e0 <= tau) != (e1 <= tau)
    rows.append((name, k, e0, e1))
    print(f"{name:22s} k={k}  E(true z) {e0:.2e}   E(A z, cond(A)=10) {e1:.2e}   ratio {e1 / e0:.1f}", flush=True)
print(f"pass/fail flips under the reparametrisation: {flip['mix']} of {n} calibration systems with k >= 2")
r = np.array([x[3] / x[2] for x in rows]); print('median E(Az)/E(z): %.2f, max %.1f' % (np.median(r), r.max()))
