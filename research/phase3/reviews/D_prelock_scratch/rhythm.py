import numpy as np
from brainir_state.data import Dataset
ds = Dataset('data/real_public')
for sid in ds.systems:
    trs = [ds.load(r) for r in ds.index if r['system_id']==sid and r['split']=='train' and r['family']=='nominal'][:10]
    res=[]
    for tr in trs:
        y = tr.y[500:].astype(float); j = int(np.argmax(y.var(0)))
        s = y[:, j]-y[:, j].mean()
        if s.std() < 1e-6: res.append((0,0,0)); continue
        P = np.abs(np.fft.rfft(s))**2; f = np.fft.rfftfreq(len(s), 1e-3)
        k = 1+np.argmax(P[1:]); share = P[k-1:k+2].sum()/P[1:].sum()
        # late-vs-early sd: sustained oscillation?
        res.append((f[k], share, y[-500:, j].std()/max(y[:500, j].std(),1e-9)))
    r = np.array(res)
    print(f"{sid:26s} peak freq (Hz) median {np.median(r[:,0]):5.1f}  power share at peak {np.median(r[:,1]):.2f}  late/early sd ratio {np.median(r[:,2]):.2f}")
