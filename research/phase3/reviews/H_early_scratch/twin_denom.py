import sys, numpy as np
sys.path.insert(0, 'src')
from brainir_state.data import Dataset
from brainir_state.evaluate import first_event_time, idx, readout_scale
ds = Dataset('data/real_public')
twins, tests = {}, []
for r in ds.index:
    pair = (r.get('info') or {}).get('pair')
    if not pair: continue
    (twins.__setitem__((r['system_id'], pair), r) if r['split'] == 'twin' else tests.append(r))
for sid in ('real:net1:full', 'real:net2:full', 'real:net3:full'):
    sc = readout_scale([ds.load(q) for q in ds.select(system_id=sid, split='train')])
    den, mx = [], []
    for r in tests:
        if r['system_id'] != sid: continue
        a, b = ds.load(r), ds.load(twins[(sid, r['info']['pair'])])
        i0 = idx(first_event_time(a), a.dt)
        d = (a.y[i0 + 1:i0 + 251].astype(float) - b.y[i0 + 1:i0 + 251])
        den.append(((d / np.sqrt(sc)) ** 2).sum()); mx.append(np.abs(d).max())
    den, mx = np.array(den), np.array(mx)
    small = mx < 0.07
    print(f"{sid}: pairs below 0.07 Hz: {small.sum()}/{len(mx)}, their share of sum d_true^2: {den[small].sum() / den.sum():.2e}; "
          f"share of the largest 3 pairs: {np.sort(den)[-3:].sum() / den.sum():.2f}")
