# D (closure) on real public val data with a PCA-k control: does standardising near-constant readout dims by their TEST sd dilute the gain?
import sys, os, copy, numpy as np
sys.path.insert(0, 'src')
from brainir_state.data import Dataset
from brainir_state import evaluate as E
from brainir_state.harness import REAL_CFG, pca_basis
from brainir_state.refmodels import ProjectionLinearModel
ds = Dataset('data/real_public')
cfg = REAL_CFG
for sid in ('real:net1:full', 'real:net3:full', 'real:net2:full'):
    train = [ds.load(r) for r in ds.select(system_id=sid, split='train')]
    val = [ds.load(r) for r in ds.select(system_id=sid, split='val') if not r['protocol']['events']]
    scale = E.readout_scale(train); pca = pca_basis(train)
    obs = ds.systems[sid]['observed']
    for k in (2, 4):
        m = ProjectionLinearModel(k, 'pca').fit(sid, train, obs)
        r_all = E.eval_closure(m, sid, val, pca, scale, cfg)
        # the same, keeping only readout dims whose sd at the D sample points exceeds 1e-3 (normalised units)
        Y = np.concatenate([t.y[370:1900:37] for t in val]).astype(float) / np.sqrt(scale)
        keep = Y.std(0) > 1e-3
        val2 = [copy.copy(t) for t in val]
        for t in val2: t.y = t.y[:, keep]
        r_keep = E.eval_closure(m, sid, val2, pca, scale[keep], cfg)
        kk = 'D_y_h100ms_rff'
        print(f"{sid} k={k}: n_val={len(val)}, readout dims {keep.size} (near-constant {int((~keep).sum())}); "
              f"micro_gain all dims {r_all[kk]['micro_gain']:.4f} (e1 {r_all[kk]['err_z']:.4f}) | informative dims only {r_keep[kk]['micro_gain']:.4f} (e1 {r_keep[kk]['err_z']:.4f})", flush=True)
