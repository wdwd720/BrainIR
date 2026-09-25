import numpy as np, collections
from brainir_state.data import Dataset
ds = Dataset('data/real_public')
for sid in ['real:net1:full','real:net2:full','real:net3:full']:
    c = collections.Counter(); n = collections.Counter(); late = collections.Counter()
    for r in ds.index:
        if r['system_id']!=sid or r['split']=='twin': continue
        t = ds.load(r); n[r['family']] += 1
        if t.x.max() > 60: c[r['family']] += 1
        if t.x[-200:].max() > 60: late[r['family']] += 1
    print(sid, {f: f"{c[f]}/{n[f]} (still >60 Hz at end: {late[f]})" for f in n})
