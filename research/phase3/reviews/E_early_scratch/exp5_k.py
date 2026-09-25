"""S5 (median K random-feature R^2 of the true latent from z) rewards large k. Truth regenerated from the PUBLIC dev seed."""
import sys; sys.path.insert(0, ".tmp/E"); sys.path.insert(0, "extra/generator"); sys.path.insert(0, "extra/orchestrator")
from common import *
from p3synth.systems import build_all
import importlib.util
spec = importlib.util.spec_from_file_location("es", "extra/orchestrator/brainir_state/evaluate_synth.py", submodule_search_locations=None)
# evaluate_synth uses relative imports -> load it as part of the installed package
import brainir_state, types
spec = importlib.util.spec_from_file_location("brainir_state.evaluate_synth", "extra/orchestrator/brainir_state/evaluate_synth.py")
es = importlib.util.module_from_spec(spec); sys.modules["brainir_state.evaluate_synth"] = es; spec.loader.exec_module(es)
systems = {s.system_id: s for s in build_all(20260924, "dev")}
res = []
for sid in sorted(CAL)[:12]:
    k = CAL[sid]["k"]; train, hs, scale, pca = setup(sid); obs = ds.systems[sid]["observed"]
    trajs = [t for f in ("init_heldout", "param_heldout") for t in hs["by_family"].get(f, [])] + hs["by_family"]["H_micro"][:12]
    zt = {}
    for t in trajs:
        sim = systems[sid].simulate(t.protocol)
        assert np.allclose(sim["x"], t.x, atol=1e-3), "regeneration mismatch"
        zt[t.key] = np.asarray(sim["z"], float)
    row = [sid, k, len(obs)]
    for kk in (k, max(k, min(len(obs), 5 * k)), len(obs)):
        m = ProjectionLinearModel(kk, "pca").fit(sid, train, obs)
        r = es.eval_latent_recovery(m, sid, trajs, zt, SYNTH_CFG)
        row += [kk, round(r["r2_true_from_model_rff"], 3)]
    print(row, flush=True)
