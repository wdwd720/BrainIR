import sys, numpy as np, collections
sys.path.insert(0, 'src')
from brainir_state.data import Dataset
from brainir_state.evaluate import first_event_time, idx, readout_scale
ds = Dataset('data/real_public')
twins, tests = {}, []
for r in ds.index:
    pair = (r.get('info') or {}).get('pair')
    if not pair: continue
    (twins.__setitem__((r['system_id'], pair), r) if r['split'] == 'twin' else tests.append(r))
scales = {}
rows = []
for r in tests:
    sid = r['system_id']
    if sid not in scales:
        scales[sid] = readout_scale([ds.load(q) for q in ds.select(system_id=sid, split='train')])
    a, b = ds.load(r), ds.load(twins[(sid, r['info']['pair'])])
    i0 = idx(first_event_time(a), a.dt); m = 250
    dy = (a.y.astype(float) - b.y) / np.sqrt(scales[sid])
    pre = dy[max(0, i0 - 30): i0 + 1]
    eff = (dy[i0 + 1: i0 + m + 1] ** 2).sum()
    pre_rate = (pre ** 2).mean()                       # per-sample squared solver discrepancy (normalised units)
    rows.append((sid, sorted(e['kind'] for e in a.events())[0], eff, pre_rate * m, np.abs(a.y.astype(float) - b.y)[:i0 + 1].max(),
                 np.abs(a.x.astype(float) - b.x)[:i0 + 1].max()))
rows = np.array(rows, dtype=object)
eff = rows[:, 2].astype(float); noise = rows[:, 3].astype(float)
print('n pairs', len(rows))
print('max pre-event |dy| (Hz):', rows[:, 4].astype(float).max(), ' max pre-event |dx| (Hz):', rows[:, 5].astype(float).max())
print('effect energy sum d_true^2 over 250 ms: quantiles 0/10/25/50%:', np.percentile(eff, [0, 10, 25, 50]))
print('pairs with effect energy < 10x the solver-noise energy scale:', int((eff < 10 * noise).sum()), ' <1e-6:', int((eff < 1e-6).sum()))
for sid in sorted(set(rows[:, 0])):
    s = rows[:, 0] == sid
    print(f"  {sid:28s} n={s.sum():3d} median eff {np.median(eff[s]):.3g}  min eff {eff[s].min():.3g}  pre-event solver energy (x250) median {np.median(noise[s]):.3g}")
