import numpy as np
from brainir_state.data import Dataset
from brainir_state.evaluate import readout_scale
ds = Dataset('data/real_public')
for sid in ds.systems:
    trs = [ds.load(r) for r in ds.index if r['system_id']==sid and r['split']=='train']
    sc = readout_scale(trs); var = np.concatenate([t.y for t in trs]).astype(float).var(0); low = var < 1e-3*var.max()
    # persistence-style and training-mean-level predictor errors on val non-intervention windows
    val = [ds.load(r) for r in ds.index if r['system_id']==sid and r['split']=='val' and r['family'] in ('nominal','init_state')]
    ym = np.concatenate([t.y for t in trs]).astype(float).mean(0)
    E = []
    for t in val:
        for t0 in (0.3,0.6,0.9,1.2):
            i0 = int(t0*1000); w = t.y[i0+1:i0+251].astype(float)
            E.append(((w - t.y[i0].astype(float))**2/sc).mean(0))   # persistence per dim
    E = np.array(E).mean(0)
    print(f"{sid:26s} persistence A {E.mean():.3f}; share from {low.sum()} floor dims: {E[low].sum()/E.sum():.2f}")
