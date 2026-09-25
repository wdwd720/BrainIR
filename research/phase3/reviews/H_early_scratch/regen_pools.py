# Regenerate the DEV microstate pools exactly as extra/scripts/build_synthetic_suites.py::_pool_system does (public seed),
# check them against data/synthetic_dev/micro_futures.npz, and keep the true latent at each restart state (truth-side).
import sys, json, hashlib, pickle, numpy as np
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, 'extra/generator')
SEED, TIER = 20260924, 'dev'
MICRO_DRAWS, MICRO_TRAJ, MICRO_STATES = 4, 8, 4

def pool_system(sid):
    sys.path.insert(0, 'extra/generator')
    from p3synth.core import seed_from
    from p3synth.suite import TEST_PARAMS, Planner
    from p3synth.systems import build_all
    systems = {s.system_id: s for s in build_all(SEED, TIER)}
    s = systems[sid]
    pl = Planner(s, seed_from("pool", SEED, TIER), TIER, 1.0)
    rng = np.random.default_rng(seed_from("pool-rng", SEED, TIER, sid) % (2**32))
    dt = 0.01
    rows, restarts = [], []
    for g, ps in enumerate(TEST_PARAMS[:MICRO_DRAWS]):
        common_noise = int(rng.integers(0, 2**31))
        for j in range(MICRO_TRAJ):
            fam = "init_heldout" if j % 2 == 0 else "stim"
            p = pl.make("test", fam) if fam == "init_heldout" else pl.make("train", "stim")
            p = dict(p, params_seed=int(ps), events=[], weight_noise=None, noise_seed=int(rng.integers(0, 2**31)))
            out = s.simulate(p, full=True)
            key = "pool" + hashlib.sha256(json.dumps({"s": sid, "p": p, "tier": TIER}, sort_keys=True).encode()).hexdigest()[:16]
            rows.append(key)
            idxs = sorted(rng.choice(np.arange(int(round(1.0 / dt)), len(out["t"]) - 1), MICRO_STATES, replace=False))
            for i in idxs:
                vals = {str(n): float(v) for n, v in enumerate(out["x_full"][i])}
                base = {"system": sid, "params_seed": int(ps), "weight_noise": None, "t_end": 1.0, "dt": dt,
                        "stimulus": [[0.0, 1.0 if s.input_dim == 1 else [1.0] * s.input_dim]], "events": [],
                        "r0": {"kind": "state", "values": vals}}
                fut = s.simulate(dict(base, noise_seed=common_noise), full=True)
                flo = s.simulate(dict(base, noise_seed=common_noise + 1))
                # noise-free future from the same state (pure deterministic future)
                det = s.simulate(dict(base, noise_seed=common_noise), noise=False)
                restarts.append({"key": key, "index": int(i), "group": int(ps), "future": fut["y"], "floor": flo["y"], "det": det["y"],
                                 "z_state": out["z"][i], "c_state": out["info"]["truth"]["coords"][i], "z_fut0": fut["z"][0]})
    return sid, s.meta['name'], restarts

if __name__ == '__main__':
    sids = sorted(json.load(open('data/synthetic_dev/manifest.json'))['systems'])
    out = {}
    with ProcessPoolExecutor(3) as ex:
        for sid, name, rs in ex.map(pool_system, sids):
            out[sid] = (name, rs)
            print(sid, name, len(rs), flush=True)
    pickle.dump(out, open('.tmp/H/pools_dev.pkl', 'wb'))
