import sys, numpy as np
sys.path.insert(0, 'src')
from brainir_state.data import Dataset
from brainir_state import evaluate as E
from brainir_state.refmodels import DirectHorizonModel, _ridge, _ridge_apply
from brainir_state.harness import REAL_CFG
ds = Dataset('data/real_public')
H = 250
for sid in ('real:net1:full', 'real:net2:full', 'real:net3:full'):
    train = [ds.load(r) for r in ds.select(system_id=sid, split='train')]
    val = [ds.load(r) for r in ds.select(system_id=sid, split='val') if not r['protocol']['events']]
    scale = E.readout_scale(train)
    m = DirectHorizonModel('readout_hist').fit(sid, train)
    base = E.eval_predictive(m, sid, val, scale, REAL_CFG)['A_nmse_h250ms']['mean']
    T = min(len(t.t) for t in train); stride = max(1, T // 80)
    feats = {id(tr): {} for tr in train}
    models = {}
    for j in range(1, H + 1):
        X, Y = [], []
        for tr in train:
            for i in range(m.lags[-1], len(tr.t) - j, stride):
                f = feats[id(tr)].get(i)
                if f is None: f = feats[id(tr)][i] = m._feat(tr.u, tr.y, i)
                X.append(np.concatenate([f, tr.u[i + j]])); Y.append(tr.y[i + j])
        models[j] = _ridge(np.array(X), np.array(Y), 1e-2)
    per = []
    for tr in val:
        rows = []
        for t0 in REAL_CFG.start_times_s:
            i0 = E.idx(t0, tr.dt); f = m._feat(tr.u, tr.y, i0)
            yp = np.stack([_ridge_apply(models[j], np.concatenate([f, tr.u[i0 + j]])[None, :])[0] for j in range(1, H + 1)])
            rows.append(E._nmse(yp, tr.y[i0 + 1: i0 + H + 1], scale))
        per.append(np.mean(rows))
    print(f"{sid}: readout_hist A_nmse_h250ms as implemented {base:.4f}  vs trained at every step {np.mean(per):.4f}  (ratio {base / np.mean(per):.2f})", flush=True)
