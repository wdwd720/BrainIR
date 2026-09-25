import sys, numpy as np, collections
sys.path.insert(0, 'src')
from brainir_state.data import Dataset
from brainir_state.evaluate import first_event_time, idx
for root in ('data/synthetic_dev', 'data/real_public'):
    ds = Dataset(root)
    twins = {}; tests = []
    for r in ds.index:
        pair = (r.get('info') or {}).get('pair')
        if not pair: continue
        if r['split'] == 'twin': twins[(r['system_id'], pair)] = r
        else: tests.append(r)
    stats = collections.Counter(); pre_max = collections.defaultdict(float); lag = collections.Counter()
    for r in tests:
        if (r['system_id'], r['info']['pair']) not in twins: continue
        a, b = ds.load(r), ds.load(twins[(r['system_id'], r['info']['pair'])])
        t_int = first_event_time(a); i0 = idx(t_int, a.dt)
        kind = sorted(e['kind'] for e in a.events())[0]
        dx = np.abs(a.x.astype(float) - b.x).max(1); dy = np.abs(a.y.astype(float) - b.y).max(1); du = np.abs(a.u.astype(float) - b.u).max()
        pre_max[kind] = max(pre_max[kind], dx[: i0 + 1].max(), dy[: i0 + 1].max(), du)
        nz = np.flatnonzero((dx > 0) | (dy > 0))
        first = nz[0] - i0 if len(nz) else None
        lag[(kind, first if first is None or first <= 3 else '>3')] += 1
    print(root, 'max |test - twin| up to and incl. the event sample (and u anywhere):', dict(pre_max))
    print('  first differing sample minus event sample:', dict(lag))
