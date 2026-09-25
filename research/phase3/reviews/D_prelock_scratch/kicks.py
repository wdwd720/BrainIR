import numpy as np, collections
from brainir_state.data import Dataset
ds = Dataset('data/real_public')
tot = collections.Counter()
for sid, s in ds.systems.items():
    oi = ds.observed_index(sid)
    rows = [r for r in ds.index if r['system_id']==sid and r['split'] in ('train','val') and r['family']=='kick_A']
    req, eff, pre = [], [], []
    for r in rows:
        tr = ds.load(r)
        for e in tr.events():
            i = int(round(e['t']/tr.dt))
            for n, d in e['delta'].items():
                j = oi[int(n)]
                req.append(d); pre.append(float(tr.x[i, j])); eff.append(float(tr.x[i+1, j]-tr.x[i, j]))
    req, eff, pre = map(np.array, (req, eff, pre))
    neg = req < 0
    clipped = neg & (pre < -req)
    null = neg & (pre < 0.5)
    ratio = np.abs(eff)/np.abs(req)
    print(f"{sid:26s} kicks={len(req):4d} neg={neg.mean():.2f}  neg&clipped={clipped.sum()/len(req):.2f}  neg on neuron<0.5Hz (≈null)={null.sum()/len(req):.2f}"
          f"  median pre-kick rate={np.median(pre):.2f} Hz  median |achieved|/|requested| (after 1 ms): {np.median(ratio):.2f}")
