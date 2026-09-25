"""Reviewer B: state-dependence of C, unobserved held-out targets, and a stateful side-channel control."""
import os, sys, json, time
os.environ["OMP_NUM_THREADS"]="3"; os.environ["MKL_NUM_THREADS"]="3"; os.environ["OPENBLAS_NUM_THREADS"]="3"
import numpy as np
sys.path.insert(0,"src"); sys.path.insert(0,"runs/brainir")
import torch; torch.set_num_threads(3)
from brainir_state import evaluate as E, harness as H
from brainir_state.refmodels import ProjectionLinearModel
import evalkit as K
K.import_methods()
from brainir_state.api import get_method, StateModel

class Scrambled(StateModel):
    """wraps a model: rollout ignores the given z0 and uses another pair's z0 (state-scrambled control)."""
    def __init__(s, m, zmap): s.m, s.zmap, s.k = m, zmap, m.k
    def encode(s, sid, x, u, dt):
        z = s.m.encode(sid, x, u, dt); return s.zmap(z)
    def rollout(s, *a): return s.m.rollout(*a)
    def readout(s, *a): return s.m.readout(*a)
    def supports(s, *a): return s.m.supports(*a)

class Cheat(StateModel):
    """reports a 1-D latent; encode() caches the full PCA state of the history; rollout() uses the cache (side channel)."""
    def __init__(s, inner): s.inner, s.k, s._last = inner, {sid: 1 for sid in inner.k}, None
    def encode(s, sid, x, u, dt):
        s._last = s.inner.encode(sid, x, u, dt); return s._last[:1].copy()
    def rollout(s, sid, z0, uf, ev, dt):
        zf = s._last.copy(); zf[0] = z0[0]
        out = s.inner.rollout(sid, zf, uf, ev, dt); return {"z": out["z"][:, :1], "y": out["y"]}
    def readout(s, sid, z, u):
        zf = np.array(s._last, float); zf[0] = np.ravel(z)[0]; return s.inner.readout(sid, zf, u)
    def supports(s, sid, kind): return s.inner.supports(sid, kind)

def ckey(res): return (res.get("C_effect_error_w1000ms") or {})
sids = sys.argv[1:]
out = open(".tmp/B/cexp.jsonl","a")
for sid in sids:
    t0=time.time()
    ds, train, hs, cfg, roles = K.load_system(sid)
    trn=[t for t in train if t.split=="train"]; scale=E.readout_scale(trn)
    obs=set(ds.systems[sid]["observed"])
    m = get_method("brainir_state_v1").fit(train, systems={sid: ds.systems[sid]}, config={}, seed=0)
    held=[p for f in roles["heldout_intervention"] for p in hs["pairs"].get(f,[])]
    def touches_unobs(tr):
        for e in tr.events():
            ids=[int(j) for j in (e.get("delta") or e.get("targets") or {})] if e["kind"]!="edge_remove" else [int(a) for ed in e["edges"] for a in ed]
            if any(j not in obs for j in ids): return True
        return False
    r_all=E.eval_intervention(m,sid,held,scale,cfg)
    uo=[p for p in held if touches_unobs(p[0])]; oo=[p for p in held if not touches_unobs(p[0])]
    r_o=E.eval_intervention(m,sid,oo,scale,cfg) if oo else {}
    r_u=E.eval_intervention(m,sid,uo,scale,cfg) if uo else {}
    # zero-effect predictions (event silently dropped?)
    n_zero=0
    for tr,tw in uo:
        i0=E.idx(E.first_event_time(tr),tr.dt); z0=E.encode_at(m,sid,tr,i0); mm=100
        ev=E.shift_events(tr.events(),tr.t[i0],1.0)
        a=m.rollout(sid,z0,tr.u[i0:i0+mm+1],ev,tr.dt)["y"]; b=m.rollout(sid,z0,tr.u[i0:i0+mm+1],[],tr.dt)["y"]
        n_zero+= bool(np.allclose(a,b))
    # state-scrambled: z0 replaced by the mean training encoding / a random other test encoding
    Ztr=E.encodings_for_whitening(m,sid,train,cfg); zbar=Ztr.mean(0)
    rng=np.random.default_rng(1)
    r_mean=E.eval_intervention(Scrambled(m,lambda z: zbar.copy()),sid,held,scale,cfg)
    r_rand=E.eval_intervention(Scrambled(m,lambda z: Ztr[rng.integers(len(Ztr))].copy()),sid,held,scale,cfg)
    # side channel: honest PCA-1, PCA-N, cheat(PCA-N) reporting k=1
    N=len(ds.systems[sid]["observed"]); kN=min(N,30)
    p1=ProjectionLinearModel(1,"pca").fit(sid,[t for t,b in zip(train,E.blowup_mask(train)) if not b],ds.systems[sid]["observed"])
    pN=ProjectionLinearModel(kN,"pca").fit(sid,[t for t,b in zip(train,E.blowup_mask(train)) if not b],ds.systems[sid]["observed"])
    ch=Cheat(pN)
    nonint=[t for f in roles["non_intervention"] for t in hs["by_family"].get(f,[])]
    ka=H.key_a(cfg)
    res={"sid":sid,"k_v1":int(m.k[sid]),"N":N,"n_pairs":len(held),"n_pairs_unobs_target":len(uo),"n_unobs_pred_zero_effect":n_zero,
         "C_v1":ckey(r_all).get("ratio"),"C_v1_ci":ckey(r_all).get("ci95"),"n_eff":ckey(r_all).get("n_eff"),
         "C_v1_obs_targets":ckey(r_o).get("ratio"),"C_v1_unobs_targets":ckey(r_u).get("ratio"),
         "den_share_unobs": (sum(v[1] for v in r_u.get("_units",{}).get("C_w1000ms",{}).values())/max(1e-12,sum(v[1] for v in r_all["_units"]["C_w1000ms"].values()))) if uo else 0.0,
         "C_v1_z0_mean":ckey(r_mean).get("ratio"),"C_v1_z0_random":ckey(r_rand).get("ratio"),
         "C_pca1":ckey(E.eval_intervention(p1,sid,held,scale,cfg)).get("ratio"),
         "C_pcaN":ckey(E.eval_intervention(pN,sid,held,scale,cfg)).get("ratio"),
         "C_cheat_k1":ckey(E.eval_intervention(ch,sid,held,scale,cfg)).get("ratio"),
         "A_pca1":E.eval_predictive(p1,sid,nonint,scale,cfg)[ka]["mean"],
         "A_pcaN":E.eval_predictive(pN,sid,nonint,scale,cfg)[ka]["mean"],
         "A_cheat_k1":E.eval_predictive(ch,sid,nonint,scale,cfg)[ka]["mean"],
         "kN":kN,"secs":time.time()-t0}
    fam={}
    for f in roles["heldout_intervention"]:
        if hs["pairs"].get(f):
            fam[f]=[ckey(E.eval_intervention(m,sid,hs["pairs"][f],scale,cfg)).get("ratio"),
                    ckey(E.eval_intervention(Scrambled(m,lambda z: zbar.copy()),sid,hs["pairs"][f],scale,cfg)).get("ratio")]
    res["per_family_C_v1_vs_meanz0"]=fam
    print(json.dumps(res),flush=True); out.write(json.dumps(res)+"\n"); out.flush()
