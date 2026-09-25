import numpy as np
from brainir_state.data import Dataset
from brainir_state.evaluate import blowup_mask
ds = Dataset('data/real_public')
for sid in ds.systems:
    rows = [r for r in ds.index if r['system_id']==sid]
    trs = [ds.load(r) for r in rows]
    m = blowup_mask(trs)
    mx = np.array([t.x.max() for t in trs]); my = np.array([t.y.max() for t in trs])
    if m.any():
        bad = [(rows[i]['split'], rows[i]['family'], round(float(mx[i]),1), round(float(my[i]),1), rows[i]['protocol'].get('weight_noise'), rows[i]['protocol']['stimulus']) for i in np.flatnonzero(m)]
        print(sid, f"n={len(trs)} blowups={m.sum()} median max x={np.median(mx):.1f} Hz", bad[:6])
    else:
        print(sid, f"n={len(trs)} blowups=0 median max x={np.median(mx):.1f}, overall max x={mx.max():.1f} Hz")
