import sys, numpy as np, collections
sys.path.insert(0, 'extra/generator'); sys.path.insert(0, 'src')
from p3synth.systems import build_all
from brainir_state.data import Dataset
S = {s.system_id: s for s in build_all(20260924, 'dev')}
ds = Dataset('data/synthetic_dev')
aff = collections.Counter(); tot = collections.Counter(); ratios = []
for r in ds.index:
    kicks = [e for e in (r['protocol'].get('events') or []) if e['kind'] == 'kick']
    if not kicks or r['split'] == 'twin': continue
    s = S[r['system_id']]; ph = s.impl.phi
    p = dict(r['protocol']); p['events'] = []
    out = s.simulate(p, full=True)
    hit = False
    for e in kicks:
        i = int(round(e['t'] / p['dt'])); x = out['x_full'][i]; v = out['v_full'][i]
        x2 = x.copy()
        for j, d in e['delta'].items(): x2[int(j)] += d
        dc6 = s.impl.D @ (ph.inv(ph.clip(x2, 1e-6), 1e-6) - v)
        dc3 = s.impl.D @ (ph.inv(ph.clip(x2, 1e-3), 1e-3) - v)
        if np.linalg.norm(dc6 - dc3) > 1e-3 * max(np.linalg.norm(dc6), 1e-12):
            hit = True; ratios.append(np.linalg.norm(dc6) / max(np.linalg.norm(dc3), 1e-12))
    key = (r['split'], r['family']); tot[key] += 1; aff[key] += hit
for k in sorted(tot): print(f"  {k[0]:5s} {k[1]:15s} trajectories with a kick whose latent jump depends on the clip eps: {aff[k]}/{tot[k]}")
print('latent jump |dc| with eps=1e-6 over |dc| with eps=1e-3 (affected kicks): median %.2f, max %.2f' % (np.median(ratios), np.max(ratios)))
