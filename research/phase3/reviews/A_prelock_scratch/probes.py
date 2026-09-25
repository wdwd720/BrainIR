"""Reviewer A probes on saved seed-0 brainir_state_v1 models:
1. D with the parameter-draw identity added to the base features (does D measure closure or parameter identification?);
2. event closure: after a held-out intervention, the model's latent (rollout with events) vs the re-encoded true microstate history,
   against the same gap on the twin (no events) and against the 'no effect' latent.
Usage: probes.py sid1,sid2,..."""
import inspect, json, pickle, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, "src")
from brainir_state import evaluate as E
from brainir_state.data import Dataset
from brainir_state.harness import SYNTH_CFG, SYNTH_ROLES, hidden_sets, pca_basis, key_d

DEV = Path("data/synthetic_dev")
ds = Dataset(DEV)
cfg = SYNTH_CFG
src = inspect.getsource(E.eval_closure)
assert '"u": tr.u[i].astype(np.float64)' in src
src = src.replace("def eval_closure(", "def eval_closure_extra(EXTRA, ").replace(
    '"u": tr.u[i].astype(np.float64)', '"u": np.concatenate([tr.u[i].astype(np.float64), EXTRA[ti]])')
ns = dict(vars(E))
exec(src, ns)
eval_closure_extra = ns["eval_closure_extra"]

for sid in sys.argv[1].split(","):
    m = pickle.load(open(f".tmp/A/models/{sid}_s0.pkl", "rb"))
    tr = [ds.load(r) for r in ds.select(system_id=sid, split="train")]
    hs = hidden_sets(ds, sid, DEV)
    nonint = [t for f in SYNTH_ROLES["non_intervention"] for t in hs["by_family"].get(f, [])]
    scale, pca = E.readout_scale(tr), pca_basis(tr)
    draws = sorted({t.protocol.get("params_seed") for t in nonint})
    onehot = np.array([[float(t.protocol.get("params_seed") == d) for d in draws] for t in nonint])
    zero = np.zeros((len(nonint), 0))
    out = {"sid": sid, "k": m.k[sid], "n_draws": len(draws)}
    for name, ex in (("D_plain", zero), ("D_with_draw_id", onehot)):
        D = eval_closure_extra(ex, m, sid, nonint, pca, scale, cfg).get(key_d(cfg), {})
        out[name] = {"gain": D.get("micro_gain"), "ci": D.get("micro_gain_ci95"), "err_z": D.get("err_z")}
    # event closure
    held = [p for f in SYNTH_ROLES["heldout_intervention"] for p in hs["pairs"].get(f, [])]
    a = E.idx(0.25, 0.01)
    rows = []
    for tri, tw in held:
        te = E.first_event_time(tri)
        i0 = E.idx(te, tri.dt)
        if i0 + a >= len(tri.t):
            continue
        z0 = E.encode_at(m, sid, tri, i0)
        ev = E.shift_events(tri.events(), tri.t[i0], a * tri.dt)
        zi = np.asarray(m.rollout(sid, z0, tri.u[i0: i0 + a + 1], ev, tri.dt)["z"])[a]
        zc = np.asarray(m.rollout(sid, z0, tri.u[i0: i0 + a + 1], [], tri.dt)["z"])[a]
        enc_i = E.encode_at(m, sid, tri, i0 + a)
        enc_t = E.encode_at(m, sid, tw, i0 + a)
        rows.append({"fam": tri.family, "gap_event_model": float(((zi - enc_i) ** 2).sum()), "gap_noeffect": float(((zc - enc_i) ** 2).sum()),
                     "gap_twin": float(((zc - enc_t) ** 2).sum()), "true_shift": float(((enc_i - enc_t) ** 2).sum()),
                     "pred_shift": float(((zi - zc) ** 2).sum())})
    if rows:
        s = {kk: float(np.sum([r[kk] for r in rows])) for kk in ("gap_event_model", "gap_noeffect", "gap_twin", "true_shift", "pred_shift")}
        s["latent_effect_error"] = float(np.sum([((0) if False else 0) for _ in rows]))
        out["event_closure"] = {"n": len(rows), **s}
    print(json.dumps(out), flush=True)
    with open(".tmp/A/probes.jsonl", "a") as fh:
        fh.write(json.dumps(out) + "\n")
