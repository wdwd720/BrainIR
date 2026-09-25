# The shortcut controls (refmodels.DirectHorizonModel) predict y(t0 + j dt) with the ridge model of the NEAREST trained horizon.
# Compare, at intermediate steps j, the nearest-horizon prediction with a model trained at exactly j.
import sys, numpy as np
sys.path.insert(0, 'src')
from brainir_state.data import Dataset
from brainir_state import evaluate as E
from brainir_state.refmodels import DirectHorizonModel, _ridge, _ridge_apply
from brainir_state.harness import REAL_CFG
ds = Dataset('data/real_public')
for sid in ('real:net2:full', 'real:net1:full'):
    train = [ds.load(r) for r in ds.select(system_id=sid, split='train')]
    val = [ds.load(r) for r in ds.select(system_id=sid, split='val') if not r['protocol']['events']]
    scale = E.readout_scale(train)
    for kind in ('readout_hist', 'input_only'):
        m = DirectHorizonModel(kind).fit(sid, train)
        print(sid, kind, 'trained horizons (steps):', m.hs)
        T = min(len(t.t) for t in train); stride = max(1, T // 80)
        for j in (30, 75, 175, 225):
            X, Y = [], []
            for tr in train:
                for i in range(m.lags[-1], len(tr.t) - j, stride):
                    X.append(np.concatenate([m._feat(tr.u, tr.y, i), tr.u[i + j]])); Y.append(tr.y[i + j])
            exact = _ridge(np.array(X), np.array(Y), 1e-2)
            hs = np.array(m.hs); near = int(hs[np.argmin(np.abs(hs - j))])
            e_near, e_exact = [], []
            for tr in val:
                for t0 in REAL_CFG.start_times_s:
                    i0 = E.idx(t0, tr.dt)
                    f = np.concatenate([m._feat(tr.u, tr.y, i0), tr.u[i0 + j]])[None, :]
                    e_near.append(E._nmse(_ridge_apply(m.models[near], f), tr.y[i0 + j][None, :], scale))
                    e_exact.append(E._nmse(_ridge_apply(exact, f), tr.y[i0 + j][None, :], scale))
            print(f"   step j={j:3d} ms: NMSE with nearest trained horizon ({near} ms) {np.mean(e_near):.4f}  vs trained at j {np.mean(e_exact):.4f}", flush=True)
