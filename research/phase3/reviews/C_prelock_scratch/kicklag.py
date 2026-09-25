import os, sys, json, pickle
os.environ["OMP_NUM_THREADS"]="3"
sys.path.insert(0,'runs/brainir'); sys.path.insert(0,'src')
import numpy as np
import evalkit as K
from brainir_state import evaluate as E
from brainir_state.api import get_method
K.import_methods()
sid=sys.argv[1]
ds,train,hs,cfg,roles=K.load_system(sid)
p=f'.tmp/review_c/work/model_{sid}.pkl'
if os.path.exists(p): model=pickle.load(open(p,'rb'))
else:
    model=get_method('brainir_state_v1').fit(train, systems={sid:ds.systems[sid]}, seed=0); pickle.dump(model,open(p,'wb'))
S=model.sys[sid]; lags=S['lags']; print("k",model.k[sid],"lags",lags,"gain",S['gain'])
L=(max(lags) if lags else 0)
for fam,pl in hs['pairs'].items():
    for tr,tw in pl:
        ev=tr.events()
        if not ev or ev[0]['kind']!='kick': continue
        t0=E.first_event_time(tr); i0=E.idx(t0,tr.dt)
        # kick at sample i0 (first event); compare after 1 step and after L+2 steps
        for h in (1, L+2, L+10):
            if i0+h>=len(tr.t): continue
            z_int=E.encode_at(model,sid,tr,i0+h); z_tw=E.encode_at(model,sid,tw,i0+h)
            evs=E.shift_events(ev,tr.t[i0],h*tr.dt)
            zi=np.asarray(model.rollout(sid,E.encode_at(model,sid,tr,i0),tr.u[i0:i0+h+1],evs,tr.dt)['z'])[-1]
            zc=np.asarray(model.rollout(sid,E.encode_at(model,sid,tr,i0),tr.u[i0:i0+h+1],[],tr.dt)['z'])[-1]
            d_enc=z_int-z_tw; d_mod=zi-zc
            print(f"{fam:16s} h={h:3d}  |encoder effect|={np.linalg.norm(d_enc):.3f}  |model effect|={np.linalg.norm(d_mod):.3f}  cos={d_enc@d_mod/(np.linalg.norm(d_enc)*np.linalg.norm(d_mod)+1e-12):+.2f}")
        print(" event",{k:v for k,v in ev[0].items()})
