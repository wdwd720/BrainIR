# Synthetic kicks: x_j + delta is clipped into the bijection's open range (eps 1e-6) and inverted. How often does a kick leave the range,
# and how large is the resulting jump in the activation v / the latent c, compared with the intended (unclipped-range) kick?
import sys, json, numpy as np
sys.path.insert(0, 'extra/generator'); sys.path.insert(0, 'src')
from p3synth.systems import build_all
from brainir_state.data import Dataset
S = {s.system_id: s for s in build_all(20260924, 'dev')}
ds = Dataset('data/synthetic_dev')
n_k = n_out = 0; worst = []
for r in ds.index:
    kicks = [e for e in (r['protocol'].get('events') or []) if e['kind'] == 'kick']
    if not kicks or r['split'] == 'twin': continue
    s = S[r['system_id']]; ph = s.impl.phi
    p = dict(r['protocol']); p['events'] = []
    out = s.simulate(p, full=True)
    for e in kicks:
        i = int(round(e['t'] / p['dt']))
        x = out['x_full'][i].copy(); v = out['v_full'][i].copy()
        x2 = x.copy()
        for j, d in e['delta'].items(): x2[int(j)] += d
        v2 = ph.inv(ph.clip(x2))
        dc = s.impl.D @ (v2 - v)
        for j, d in e['delta'].items():
            j = int(j); n_k += 1
            k = ph.kind[j]; sc = ph.scale[j]
            outside = (k == 1 and abs(x2[j]) >= sc * (1 - 1e-6)) or (k == 2 and not (sc * 1e-6 < x2[j] < sc * (1 - 1e-6)))
            if outside:
                n_out += 1
                worst.append((abs(v2[j] - v[j]) / sc, s.meta['name'], r['split'], r['family'], float(np.linalg.norm(dc)),
                              float(np.std(out['z'], 0).mean())))
print(f"kicked neurons: {n_k}; kicks that leave the bijection range (clipped at eps=1e-6): {n_out}")
worst.sort(reverse=True)
for w in worst[:12]:
    print(f"  {w[1]:18s} {w[2]:5s} {w[3]:15s} |dv|/scale {w[0]:.2f}  |dc| {w[4]:.3g}  (sd of z over the trajectory {w[5]:.3g})")
