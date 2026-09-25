import json, numpy as np, collections
from brainir_state.data import Dataset
ds = Dataset('data/real_public')
rows = ds.index
print(collections.Counter((r['system_id'].replace('real:',''), r['split']) for r in rows))
for sid, s in ds.systems.items():
    tr = [r for r in rows if r['system_id']==sid and r['split']=='train' and r['family']=='nominal'][:20]
    X = [ds.load(r) for r in tr]
    xpk = np.max([t.x.max(0) for t in X],0)
    ypk = np.max([t.y.max(0) for t in X],0)
    ysd = np.mean([t.y[300:].std(0) for t in X],0)
    ymean = np.mean([t.y[300:].mean(0) for t in X],0)
    # oscillation: fraction of y power at nonzero freq vs mean
    y0 = X[0].y
    print(f"\n{sid}: N_obs {len(s['observed'])} n_y {len(s['readout'])}")
    print("  x peak rate quantiles (Hz) [min,10,50,90,max]:", np.round(np.percentile(xpk,[0,10,50,90,100]),3))
    print("  frac observed with peak<1Hz:", np.mean(xpk<1).round(3), " <0.1Hz:", np.mean(xpk<0.1).round(3))
    print("  y peak (Hz):", np.round(ypk,3))
    print("  y sd over t>0.3s (mean over traj):", np.round(ysd,3))
    print("  y mean t>0.3:", np.round(ymean,2))
