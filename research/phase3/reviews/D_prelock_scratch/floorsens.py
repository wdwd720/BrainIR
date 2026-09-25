import numpy as np
from brainir_state.data import Dataset
from brainir_state.evaluate import first_event_time, idx, blowup_mask
ds = Dataset('data/real_public')
def scale_with(trs, f):
    keep = [t for t, b in zip(trs, blowup_mask(trs)) if not b] or trs
    var = np.concatenate([t.y for t in keep]).astype(float).var(0)
    return var, np.maximum(var, max(1e-6, f*var.max()))
for sid in ['real:net1:full','real:net2:full','real:net3:full']:
    trs = [ds.load(r) for r in ds.index if r['system_id']==sid and r['split']=='train']
    val = {(r.get('info') or {}).get('pair'): r for r in ds.index if r['system_id']==sid and r['split']=='val' and (r.get('info') or {}).get('pair')}
    tw = [r for r in ds.index if r['system_id']==sid and r['split']=='twin']
    D = []
    for r in tw:
        a, b = ds.load(val[r['info']['pair']]), ds.load(r)
        i0 = idx(first_event_time(a), a.dt); m = idx(0.25, a.dt)
        if i0+m < len(a.t): D.append((val[r['info']['pair']]['family'], (a.y[i0+1:i0+m+1]-b.y[i0+1:i0+m+1]).astype(float)))
    for f in (1e-3, 1e-2):
        var, sc = scale_with(trs, f)
        low = var < f*var.max()
        den = np.array([((d**2)/sc).sum(0) for _, d in D])
        share = den[:, low].sum()/den.sum()
        # absolute size of effects on the low-variance dims vs the others
        mx_low = max((np.abs(d[:, low]).max() if low.any() else 0) for _, d in D); mx_hi = max(np.abs(d[:, ~low]).max() for _, d in D)
        print(f"{sid} floor {f:g}: {low.sum()} low-var dims; share of pooled C denominator (all val pairs) from them {share:.2f}; "
              f"largest |effect| on them {mx_low:.2f} Hz vs {mx_hi:.2f} Hz on the others")
