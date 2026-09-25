import json, numpy as np
cal=json.load(open('extra/benchmark/calibration.json'))
truth={r['sid']:r for r in cal['per_system']}
rows=[json.loads(l) for l in open('runs/brainir/res/dimexp.jsonl')]
seen={}
for r in rows:
    if r.get('config'): continue   # ablated refits
    seen[r['sid']]=r
print(len(seen),"v1 dev fits;", len(truth),"calibration systems")
ex=inr=inr_ks=ex_ks=n=0; widths=[]; tab=[]
for sid,r in sorted(seen.items()):
    t=truth.get(sid)
    if t is None: continue
    kt=t['k']
    if not isinstance(kt,int): continue
    n+=1
    k=r['k']; lo,hi=r['k_range']; sc=r['sys_config']
    kk=sc['k_ks_rule']['k']; klo,khi=sc['k_ks_rule']['range']
    ab=r['abstain']['no_compact_state']
    ex+= (k==kt); inr+= (lo<=kt<=hi) or k==kt
    ex_ks+=(kk==kt); inr_ks+=(klo<=kt<=khi) or kk==kt
    widths.append(hi-lo)
    tab.append((sid,t['family'],t.get('trap'),kt,k,[lo,hi],kk,[klo,khi],ab))
print("n compressible",n)
print("v1  exact %d in-range %d  median width %.1f"%(ex,inr,np.median(widths)))
print("ks  exact %d in-range %d"%(ex_ks,inr_ks))
under=sum(1 for x in tab if x[4]<x[3]); over=sum(1 for x in tab if x[4]>x[3])
print("v1 k<k_true",under,"k>k_true",over)
under=sum(1 for x in tab if x[6]<x[3]); over=sum(1 for x in tab if x[6]>x[3])
print("ks k<k_true",under,"k>k_true",over)
for x in tab: print(x)
# range-only gain: in range but not exact
print("v1 in-range-but-not-exact", sum(1 for x in tab if x[5][0]<=x[3]<=x[5][1] and x[4]!=x[3]))
