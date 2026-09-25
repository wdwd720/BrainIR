import os, sys, json, pickle
os.environ["OMP_NUM_THREADS"]="3"
sys.path.insert(0,'runs/brainir'); sys.path.insert(0,'src')
import numpy as np
import evalkit as K
from brainir_state import evaluate as E, harness as H
from brainir_state.api import get_method
K.import_methods()
sid=sys.argv[1]
truth=json.load(open('.tmp/review_c/work/dev_truth.json'))[sid]
ds,train,hs,cfg,roles=K.load_system(sid)
entry=ds.systems[sid]; obs=entry['observed']
model=get_method('brainir_state_v1').fit(train, systems={sid:entry}, seed=0)
pickle.dump(model,open(f'.tmp/review_c/work/model_{sid}.pkl','wb'))
S=model.sys[sid]; k=model.k[sid]
print("k",k,"lags",S['lags'],"gain",S['gain'],"mode",S['silence_mode'])
D=np.asarray(truth['D']); kt=truth['k']; roles_=truth['roles']
Dz=D[:kt]                                     # causal latent rows
col=S['prep'].col if hasattr(S['prep'],'col') else None
# model latent shift per unit kick (raw units) on each observed neuron: dz_j = e_j/sd @ Ck0
sd=S['prep'].sd
dz_model=(np.eye(len(obs))/sd[None,:]) @ S['Ck0']   # (N_obs,k)
# scale-free comparison: model shift in units of latent sd, true shift in units of true-latent sd (approx via D norms)
zc=np.sqrt(np.diag(S['z_cov']))
m_norm=np.linalg.norm(dz_model/zc,axis=1)
t_norm=np.linalg.norm(Dz[:,obs],axis=0)
rl=np.array([roles_[j] for j in obs])
for r in sorted(set(rl)):
    msk=rl==r
    print(f"role {r:16s} n={msk.sum():3d}  model |dz|/sd(z) median {np.median(m_norm[msk]):.4f}  true |D col| median {np.median(t_norm[msk]):.4f}  frac D==0 {np.mean(t_norm[msk]==0):.2f}")
causal=t_norm>0
print("corr(model |dz|, true |D col|) over observed neurons: %.3f"%np.corrcoef(m_norm,t_norm)[0,1])
print("ratio median model |dz| carriers-with-D=0 / causal: %.3f"%(np.median(m_norm[~causal])/np.median(m_norm[causal]) if (~causal).any() else float('nan')))
# per pair C split by whether ALL kicked/current/silenced targets are non-causal
pairs=hs['C_heldout'] if 'C_heldout' in hs else None
print("hidden set keys",list(hs.keys()))
