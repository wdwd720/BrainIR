import numpy as np, collections
from brainir_state.data import Dataset
from brainir_state.evaluate import readout_scale
ds = Dataset('data/real_public')
for sid in ds.systems:
    rows = [r for r in ds.index if r['system_id']==sid and r['split']=='train']
    trs = [ds.load(r) for r in rows]
    sc = readout_scale(trs)
    fams = collections.defaultdict(list)
    for tr in trs: fams[tr.family].append(tr)
    # variance contribution per family (pooled around global mean), weighted by var normaliser
    Y = np.concatenate([t.y for t in trs]).astype(float); mu = Y.mean(0)
    tot = ((Y-mu)**2/sc).sum()
    share = {f: float(sum((((t.y-mu)**2)/sc).sum() for t in L)/tot) for f, L in fams.items()}
    frac = {f: len(L)/len(trs) for f, L in fams.items()}
    # skill-free predictor on val nominal: per window, predict y(t0) held constant (persistence) and training mean
    val = [ds.load(r) for r in ds.index if r['system_id']==sid and r['split']=='val' and r['family'] in ('nominal','init_state')]
    e_mean, e_osc = [], []
    for tr in val:
        for t0 in (0.3,0.6,0.9,1.2):
            i0=int(t0*1000); w=tr.y[i0+1:i0+251].astype(float)
            e_mean.append(np.mean((w - w.mean(0))**2/sc))   # oracle window-mean (constant) predictor
    print(f"{sid:26s} init_state: {frac.get('init_state',0):.2f} of traj, {share.get('init_state',0):.2f} of normalised variance | "
          f"NMSE of an ORACLE constant (window mean) on val nominal/init windows: {np.mean(e_mean):.3f}")
