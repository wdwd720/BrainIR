import sys, json, numpy as np, pickle
sys.path.insert(0, 'src')
from brainir_state.data import Dataset
from brainir_state import evaluate as E
ds = Dataset('data/synthetic_dev')
names = {sid: v[0] for sid, v in pickle.load(open('.tmp/H/pools_dev.pkl', 'rb')).items()}
print('system, readout_scale (train), robust scale (median-traj var), ratio, worst train traj family / |y|max / |x|max')
for sid in sorted(ds.systems):
    tr = [ds.load(r) for r in ds.select(system_id=sid, split='train')]
    sc = E.readout_scale(tr)
    v = np.array([t.y.var(0).max() for t in tr]); ymax = np.array([np.abs(t.y).max() for t in tr])
    j = int(ymax.argmax())
    rob = E.readout_scale([t for i, t in enumerate(tr) if i != j])
    ratio = (sc / rob).max()
    if ratio > 3:
        t = tr[j]
        print(f"{names[sid]:18s} {sid}  scale {sc.max():.3g}  without that one traj {rob.max():.3g}  ratio {ratio:.3g}   {t.family} wn={t.protocol.get('weight_noise')} "
              f"|y|max {ymax[j]:.3g} |x|max {np.abs(t.x).max():.3g}  (next |y|max {np.sort(ymax)[-2]:.3g})")
# the same check on every split / every test trajectory: finite but huge values
big = []
for r in ds.index:
    if r['split'] in ('train', 'val', 'test', 'twin'):
        t = ds.load(r)
        m = max(np.abs(t.x).max(), np.abs(t.y).max())
        if m > 1e3: big.append((names[r['system_id']], r['split'], r['family'], f"{m:.3g}"))
print('trajectories with |x| or |y| > 1e3:', len(big)); [print('  ', b) for b in big]
