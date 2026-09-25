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
    Y = np.concatenate([ds.load(q).y for q in ds.select(system_id=sid, split='train')])
    print(sid, 'readout var per dim:', np.round(Y.var(0), 3), ' floor-hit dims:', int((sc > Y.var(0) + 1e-12).sum()))
    mx, pre, kinds = [], [], []
    for r in tests:
        if r['system_id'] != sid: continue
        a, b = ds.load(r), ds.load(twins[(sid, r['info']['pair'])])
        i0 = idx(first_event_time(a), a.dt)
        d = np.abs(a.y.astype(float) - b.y)
        mx.append(d[i0 + 1: i0 + 251].max()); pre.append(d[: i0 + 1].max()); kinds.append(a.events()[0]['kind'])
    mx = np.array(mx); pre = np.array(pre)
    print('   max |y_int - y_twin| in the 250 ms window (Hz), sorted:', np.round(np.sort(mx), 4))
    print('   pairs with window effect < 0.07 Hz (frozen-solver tolerance per PROTOCOL 2.1):', int((mx < 0.07).sum()), 'of', len(mx),
          '; < 0.04 Hz:', int((mx < 0.04).sum()), '; max pre-event diff', pre.max().round(4))
