import pickle, numpy as np, sys
sys.path.insert(0, 'src')
from brainir_state.data import Dataset
from brainir_state import evaluate as E
pools = pickle.load(open('.tmp/H/pools_dev.pkl', 'rb'))
ds = Dataset('data/synthetic_dev')
for sid, (name, rs) in pools.items():
    if name not in ('nonmarkov', 'parameter_trap'): continue
    F = np.stack([r['future'] for r in rs]); Z = np.stack([r['z_state'] for r in rs])
    sc = E.readout_scale([ds.load(r) for r in ds.select(system_id=sid, split='train')])
    print(name, sid, 'readout train var', sc, ' future y range', F.min(), F.max(), ' sd over states at t=0.01s', F[:, 1].std(0),
          ' at 1 s', F[:, -1].std(0), ' sd(z_state)', Z.std(0))
    Fd = np.stack([r['det'] for r in rs]); print('   noise-free futures: sd over states at t=0.01 s', Fd[:, 1].std(0), 'at 1 s', Fd[:, -1].std(0))
