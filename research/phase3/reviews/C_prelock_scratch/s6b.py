import json, numpy as np
cal=json.load(open('extra/benchmark/calibration.json'))
truth={r['sid']:r for r in cal['per_system']}
fin={}
for f in ['fitonly.jsonl','fitonly_v2.jsonl']:
    for l in open('runs/brainir/res/'+f):
        r=json.loads(l); fin[r['sid']]=r
ex=inr=0;n=0;rng_only=[];ab=[]
for sid,r in sorted(fin.items()):
    t=truth.get(sid)
    if t is None or not isinstance(t['k'],int): 
        print("non-calib/none:",sid,r['k'],r['k_range'],r['abstain'].get('no_compact_state')); continue
    n+=1; k=r['k']; lo,hi=r['k_range']; kt=t['k']
    ex+=k==kt; hit=(lo<=kt<=hi) or k==kt; inr+=hit
    if hit and k!=kt: rng_only.append((sid,t['family'],kt,k,[lo,hi]))
    if r['abstain'].get('no_compact_state'): ab.append((sid,t['family'],kt))
    # point-only S6 if range were [k,k]
print("final v1 on %d compressible dev systems: exact %d, in-range %d"%(n,ex,inr))
print("range-only hits:",len(rng_only)); [print(" ",x) for x in rng_only]
print("false alarms:",ab)
