import numpy as np
from brainir_state.data import Dataset
from brainir_state.evaluate import readout_scale
ds = Dataset('data/real_public')
LAGS = (0, 5, 10, 20, 40)
def feats(tr, sl):
    X = tr.x.astype(float); cols=[]
    for L in LAGS:
        idx = np.maximum(np.arange(len(X))-L, 0)
        cols.append(X[idx])
    cols.append(tr.u.astype(float))
    return np.hstack(cols)[sl]
for sid in ds.systems:
    tr_rows = [r for r in ds.index if r['system_id']==sid and r['split']=='train' and not r['protocol']['events']]
    va_rows = [r for r in ds.index if r['system_id']==sid and r['split']=='val' and not r['protocol']['events']]
    trs = [ds.load(r) for r in tr_rows]; vas=[ds.load(r) for r in va_rows]
    sc = readout_scale([ds.load(r) for r in ds.index if r['system_id']==sid and r['split']=='train'])
    sl = slice(300, 2000, 2)
    X = np.vstack([feats(t, sl) for t in trs]); Y = np.vstack([t.y[sl] for t in trs]).astype(float)
    mu, sd = X.mean(0), X.std(0)+1e-9; A=(X-mu)/sd; ym=Y.mean(0)
    W = np.linalg.solve(A.T@A + 1e-2*len(A)*np.eye(A.shape[1]), A.T@(Y-ym))
    tot, lvl = 0.0, 0.0; errs=[]
    for t in vas:
        P = ((feats(t, sl)-mu)/sd)@W+ym; R = (t.y[sl]-P)/np.sqrt(sc)
        tot += (R**2).sum(); lvl += (len(R)*R.mean(0)**2).sum(); errs.append(np.mean(R**2))
    print(f"{sid:26s} ridge x(+lags)->y on val event-free, t>=0.3 s: NMSE {np.mean(errs):.3f}; share of error that is a per-trajectory constant offset: {lvl/tot:.2f}")
