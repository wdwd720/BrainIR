import sys, json, numpy as np
sys.path.insert(0,'extra/generator')
from p3synth.systems import build_all
sy=build_all(20260924,'dev')
man=json.load(open('data/synthetic_dev/manifest.json'))
out={}
for s in sy:
    if s.system_id not in man['systems']: continue
    im=s.impl
    roles=list(im.roles)
    D=np.asarray(s.synaptic_readout(None))
    out[s.system_id]={"name":s.meta['name'],"k":int(s.k) if hasattr(s,'k') else None,"roles":roles,"D":D.tolist(),
                      "observed":list(map(int,s.observed))}
print(len(out))
json.dump(out,open('.tmp/review_c/work/dev_truth.json','w'))
for sid,v in sorted(out.items()):
    from collections import Counter
    print(sid,v['name'],v['k'],dict(Counter(v['roles'])), np.asarray(v['D']).shape)
