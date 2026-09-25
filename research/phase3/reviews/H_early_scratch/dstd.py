import sys, numpy as np
sys.path.insert(0, 'src')
from brainir_state.data import Dataset
from brainir_state.evaluate import readout_scale
ds = Dataset('data/real_public')
for sid in ('real:net1:full', 'real:net2:full', 'real:net3:full', 'real:net2:mech:3aa95ab7'):
    tr = [ds.load(r) for r in ds.select(system_id=sid, split='train')]
    sc = readout_scale(tr)
    va = [ds.load(r) for r in ds.select(system_id=sid, split='val') if not r['protocol']['events']]
    Y = np.concatenate([t.y[370:1900:37] for t in va]).astype(float) / np.sqrt(sc)   # D-like sample points (t+100 ms)
    sd = Y.std(0)
    print(sid, 'n pts', len(Y), 'test-point sd of y/sqrt(scale) per dim:', np.array2string(sd, precision=4, max_line_width=250))
