import numpy as np
from scipy.stats import rankdata
K=["S1","S2","S3","S4","S5","S6","S7","S8"]; low={"S1","S2","S3","S4"}
r2={"lin_subspace":[0.999,0.564,-0.0827,0.00175,0.996,0.674,0.457,0.5],
"lin_falds":[1.16,0.55,-0.0052,0.00105,0.997,0.587,0.891,0.5],
"nn_closed":[0.938,0.746,-0.00831,0.00226,0.991,0.783,0.978,0.5],
"lin_dmdc":[1.08,0.613,-0.0488,0.00159,0.995,0.565,0.902,0.5],
"ks_sindy":[0.969,0.585,-0.0354,0.00173,0.995,0.652,0.696,0.167],
"nn_aelin":[1.09,0.983,-0.071,0.00277,0.991,0.783,0.989,0.5],
"lin_balanced":[1.03,0.68,-0.0459,0.00236,0.997,0.543,0.5,0.5]}
def rank(P,keys=K):
    names=sorted(P); R={m:[] for m in names}
    for j,k in enumerate(K):
        if k not in keys: continue
        v=np.array([P[m][j] for m in names]); s=v if k in low else -v
        for m,r in zip(names,rankdata(s)): R[m].append(r)
    mr={m:np.mean(R[m]) for m in names}
    return sorted(names,key=lambda m:(mr[m],m)),mr
o,mr=rank(r2); print("all",[(m,round(mr[m],2)) for m in o])
for drop in K:
    o,mr=rank(r2,[k for k in K if k!=drop]); print("drop",drop,[(m,round(mr[m],2)) for m in o][:4])
base={"lin_falds","lin_dmdc","nn_aelin"}
for rm in r2:
    P={m:v for m,v in r2.items() if m!=rm}; o,mr=rank(P); print("without",rm,"-> top",o[:3], "strongest baseline",[m for m in o if m in base][0])
for s6,s7 in [(0.65,0.97),(0.70,0.97),(0.75,0.97)]:
    h=list(r2["ks_sindy"]); h[5]=s6; h[6]=s7; h[7]=0.5
    P=dict(r2); P["brainir_state_v1"]=h; o,mr=rank(P); print("with hybrid",s6,s7,[(m,round(mr[m],2)) for m in o])
# rounding sensitivity: S5 rounded to 2 decimals
P={m:[*v[:4],round(v[4],2),*v[5:]] for m,v in r2.items()}; o,mr=rank(P); print("S5 rounded",[(m,round(mr[m],2)) for m in o])
