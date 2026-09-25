import os, sys, json, pickle
os.environ["OMP_NUM_THREADS"]="3"
sys.path.insert(0,'runs/brainir'); sys.path.insert(0,'src')
import numpy as np
import evalkit as K
from brainir_state import evaluate as E, harness as H
K.import_methods()
sid=sys.argv[1]
truth=json.load(open('.tmp/review_c/work/dev_truth.json'))[sid]
ds,train,hs,cfg,roles=K.load_system(sid)
model=pickle.load(open(f'.tmp/review_c/work/model_{sid}.pkl','rb'))
D=np.asarray(truth['D'])[:truth['k']]; causal=np.linalg.norm(D,axis=0)>0
scale=E.readout_scale(train)
pairs=hs['pairs']
print(type(pairs), len(pairs))
rows=[]
for fam,pl in (pairs.items() if isinstance(pairs,dict) else [("all",pairs)]):
    for tr,tw in pl:
        ev=tr.events()
        tg=sorted({int(n) for e in ev for n in (e.get('neurons') or e.get('targets') or [])})
        kinds={e['kind'] for e in ev}
        r=E.eval_intervention(model,sid,[(tr,tw)],scale,cfg,windows_s=(1.0,))
        u=list(r['_units']['C_w1000ms'].values())
        if not u: continue
        num,den=u[0][0],u[0][1]
        rows.append((fam,tuple(sorted(kinds)),tg,any(causal[t] for t in tg) if tg else None,num,den))
print("example event",pairs[list(pairs)[0]][0][0].events()[:1] if isinstance(pairs,dict) else None)
import collections
agg=collections.defaultdict(lambda:[0,0.0,0.0])
for fam,kinds,tg,c,num,den in rows:
    key=(fam,"causal" if c else ("noncausal" if c is False else "?"))
    a=agg[key]; a[0]+=1; a[1]+=num; a[2]+=den
for k_,(n,num,den) in sorted(agg.items()): print(k_, n, "num %.3g den %.3g ratio %.2f"%(num,den,num/den if den>0 else float('nan')))
