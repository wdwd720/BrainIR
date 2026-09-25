import numpy as np
from brainir_state.data import Dataset
from brainir_state.evaluate import readout_scale, first_event_time, idx
ds = Dataset('data/real_public')
rows = ds.index
for sid in ds.systems:
    tr = [ds.load(r) for r in rows if r['system_id']==sid and r['split']=='train']
    sc = readout_scale(tr)
    Y = np.concatenate([t.y for t in tr]).astype(float); var = Y.var(0)
    atfloor = var <= sc*(1+1e-9) - 0 
    atfloor = np.isclose(sc, sc.min()) & (var < sc)
    print(f"\n{sid}: n_y {len(sc)}; dims at floor (var<floor): {int(atfloor.sum())}; floor={sc.min():.3g}; max var={var.max():.3g}")
    print("   var/maxvar:", np.array2string(var/var.max(), precision=4))
    # C effect denominator on val intervention pairs (250 ms window)
    val = {(r.get("info") or {}).get("pair"): r for r in rows if r["system_id"]==sid and r["split"]=="val" and (r.get("info") or {}).get("pair")}
    tw = [r for r in rows if r['system_id']==sid and r['split']=='twin']
    per_fam = {}
    for r in tw:
        pk = r['info'].get('pair');
        if pk not in val: continue
        a, b = ds.load(val[pk]), ds.load(r)
        t0 = first_event_time(a); i0 = idx(t0, a.dt); m = idx(0.25, a.dt)
        if i0 + m >= len(a.t): continue
        d = (a.y[i0+1:i0+m+1]-b.y[i0+1:i0+m+1]).astype(float)/np.sqrt(sc)
        pre = (a.y[:i0+1]-b.y[:i0+1]).astype(float)/np.sqrt(sc)
        dd = (d**2).sum(0)
        f = per_fam.setdefault(val[pk]['family'], {'den':0,'den_floor':0,'n':0,'pre':[], 'dens':[]})
        f['den'] += dd.sum(); f['den_floor'] += dd[atfloor].sum(); f['n']+=1; f['pre'].append(np.abs(a.y[:i0+1]-b.y[:i0+1]).max()); f['dens'].append(dd.sum())
    for fam, f in per_fam.items():
        dens = np.array(f['dens'])
        print(f"   {fam:11s} n={f['n']:2d} effect-denominator share from floor dims = {f['den_floor']/max(f['den'],1e-30):.3f};"
              f" n_eff={dens.sum()**2/max((dens**2).sum(),1e-30):.1f}; max pair share={dens.max()/max(dens.sum(),1e-30):.2f};"
              f" pre-event max|dy| (Hz)={max(f['pre']):.3g}; pairs with den<1e-3: {(dens<1e-3).sum()}")
