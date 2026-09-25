import sys; sys.path.insert(0, ".tmp/E")
from common import *
sid = sorted(CAL)[0]
t=time.time(); train, hs, scale, pca = setup(sid); print("setup", time.time()-t)
t=time.time(); m = ProjectionLinearModel(CAL[sid]["k"], "pca").fit(sid, train, ds.systems[sid]["observed"]); print("fit", time.time()-t)
t=time.time(); r = evaluate_system(m, sid, hs, scale, pca, SYNTH_CFG, k=CAL[sid]["k"], families=("A","C","D","E"), roles=SYNTH_ROLES); print("eval", time.time()-t)
t=time.time(); io = DirectHorizonModel("input_only").fit(sid, train); print("fit io", time.time()-t)
print(E.strip_units(r)["A_B"][key_a(SYNTH_CFG)], r["C_heldout"]["n_pairs"], r["C_heldout"]["n_abstained_unsupported"], r["C_heldout"][key_c(SYNTH_CFG)], r["D"][key_d(SYNTH_CFG)]["micro_gain"], r["E"]["E_ratio_latent_to_random"])
print("cal pca_k", CAL[sid]["pca_k"])
