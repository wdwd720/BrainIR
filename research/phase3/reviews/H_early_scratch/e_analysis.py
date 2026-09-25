import sys, json, pickle, numpy as np
sys.path.insert(0, 'src')
from brainir_state.data import Dataset
from brainir_state import evaluate as E
from brainir_state.harness import SYNTH_CFG, hidden_sets, _micro_files
from pathlib import Path
cfg = SYNTH_CFG._replace(n_boot=50) if hasattr(SYNTH_CFG, '_replace') else SYNTH_CFG
import dataclasses; cfg = dataclasses.replace(SYNTH_CFG, n_boot=20)
pools = pickle.load(open('.tmp/H/pools_dev.pkl', 'rb'))
ds = Dataset('data/synthetic_dev')
idx, fut, flo = _micro_files(Path('data/synthetic_dev'))
stored = {(m['key'], m['index']): (fut[j], flo[j]) for j, m in enumerate(idx)}
maxdiff = 0.0; nmatch = 0
for sid, (name, rs) in pools.items():
    for r in rs:
        f, fl = stored[(r['key'], r['index'])]
        maxdiff = max(maxdiff, np.abs(f - r['future']).max(), np.abs(fl - r['floor']).max()); nmatch += 1
print('regenerated pool restarts', nmatch, 'of stored', len(idx), '; max |regenerated - stored| future/floor:', maxdiff)

class Z:
    uses_readout = False
    def __init__(self, table): self.t = table
    def encode(self, sid, x_hist, u_hist, dt): return self.t[np.asarray(x_hist[-1], np.float32).tobytes()]

truth = {}
rows = []
for sid, (name, rs) in sorted(pools.items(), key=lambda kv: kv[1][0]):
    train = [ds.load(r) for r in ds.select(system_id=sid, split='train')]
    scale = E.readout_scale(train)
    hs = hidden_sets(ds, sid, Path('data/synthetic_dev'))
    pool = hs['pool']
    zt = {(r['key'], r['index']): np.asarray(r['z_state'], float) for r in rs}
    det = {(r['key'], r['index']): r['det'] for r in rs}
    tab = {np.asarray(p['x_hist'][-1], np.float32).tobytes(): zt[(p['traj'], p['t_index'])] for p in pool}
    def run(pl, table=tab):
        pl = [dict(p) for p in pl]
        for p in pl: p['floor_div'] = float(np.mean((np.asarray(p['future_y']) - np.asarray(p['floor_future'])) ** 2 / scale))
        return E.eval_microstate(Z(table), sid, pl, scale, cfg)
    r1 = run(pool)
    # the same pools with the future truncated to 0.25 s (25 samples; the REAL design's E window is 0.25 s)
    r2 = run([dict(p, future_y=p['future_y'][:25], floor_future=p['floor_future'][:25]) for p in pool])
    # noise-free futures from the same states
    r3 = run([dict(p, future_y=det[(p['traj'], p['t_index'])][1:]) for p in pool])
    # the true latent plus ONE extra latent coordinate carrying tiny noise (sd 1e-6 of sd(z)): standardisation amplifies it
    rng = np.random.default_rng(0)
    sdz = np.std(np.stack(list(tab.values())), 0).mean()
    tab2 = {k: np.r_[v, 1e-6 * sdz * rng.standard_normal()] for k, v in tab.items()}
    r4 = run(pool, tab2)
    fl = r1.get('E_numerical_floor', {}).get('mean_div', np.nan)
    rows.append((name, r1['E_ratio_latent_to_random'], r2['E_ratio_latent_to_random'], r3['E_ratio_latent_to_random'],
                 r4['E_ratio_latent_to_random'], fl / r1['E_random_pairs']['mean_div'], r1['E_random_pairs']['mean_div']))
    print(f"{name:22s} E_true(1s) {rows[-1][1]:.2e}  E_true(0.25s) {rows[-1][2]:.2e}  E_true(noise-free fut) {rows[-1][3]:.2e}  "
          f"E_true+tiny-dim {rows[-1][4]:.2e}  floor/random {rows[-1][5]:.2e}  random div {rows[-1][6]:.2e}", flush=True)
pickle.dump(rows, open('.tmp/H/e_rows.pkl', 'wb'))
a = np.array([r[1:] for r in rows], float)
print('median over systems: E_true(1s) %.2e  E_true(0.25s) %.2e  noise-free %.2e  +tiny dim %.2e  floor/random %.2e' % tuple(np.nanmedian(a[:, :5], 0)))
print('systems where E_true+tiny-dim > tau_E=0.0039 while E_true <= tau_E:', int(((a[:, 3] > 0.0039) & (a[:, 0] <= 0.0039)).sum()))
print('systems where floor/random > tau_E:', int((a[:, 4] > 0.0039).sum()), 'of', len(a))
