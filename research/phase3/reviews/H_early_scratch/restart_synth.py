# Restart equivalence of the synthetic pools: restart from recorded x_full[i] vs continuing the original trajectory (noise-free).
import sys, json, numpy as np
sys.path.insert(0, 'extra/generator')
from p3synth.systems import build_all
from p3synth.core import seed_from
from p3synth.suite import TEST_PARAMS, Planner
systems = build_all(20260924, 'dev')
dev = json.load(open('data/synthetic_dev/manifest.json'))['systems']
print('ids match dev manifest:', set(s.system_id for s in systems) == set(dev))
dt = 0.01
res = []
for s in systems:
    pl = Planner(s, seed_from("pool", 20260924, 'dev'), 'dev', 1.0)
    rng = np.random.default_rng(0)
    worst = {}
    for j in range(2):
        fam = "init_heldout" if j % 2 == 0 else "stim"
        p = pl.make("test", fam) if fam == "init_heldout" else pl.make("train", "stim")
        p = dict(p, params_seed=TEST_PARAMS[0], events=[], weight_noise=None, noise_seed=1)
        out = s.simulate(p, full=True, noise=False)
        for i in sorted(rng.choice(np.arange(100, len(out['t']) - 101), 3, replace=False)):
            vals = {str(n): float(v) for n, v in enumerate(out["x_full"][i])}
            ti = i * dt
            # continuation input: the pool trajectory's own stimulus schedule shifted to the restart time
            st = [[0.0, None]]
            for t, v in p['stimulus']:
                if t <= ti + 1e-9: st[0][1] = v
                else: st.append([round(t - ti, 9), v])
            st = [x for x in st if x[0] <= 1.0]
            q = {"system": s.system_id, "params_seed": p['params_seed'], "weight_noise": None, "t_end": 1.0, "dt": dt,
                 "stimulus": st, "events": [], "r0": {"kind": "state", "values": vals}, "noise_seed": 1}
            r = s.simulate(q, noise=False, full=True)
            z0err = np.abs(r['z'][0] - out['z'][i]).max()
            zerr = np.abs(r['z'] - out['z'][i:i + 101]).max()
            yerr = np.abs(r['y'] - out['y'][i:i + 101]).max()
            verr = np.abs(r['v_full'][0] - out['v_full'][i]).max()
            ysc = out['y'].std() + 1e-12
            for k_, v_ in (('z0', z0err), ('z', zerr), ('y_rel', yerr / ysc), ('v0', verr)):
                worst[k_] = max(worst.get(k_, 0), float(v_))
    res.append((s.meta['name'], s.system_id, worst))
    print(f"{s.meta['name']:24s} z0 {worst['z0']:.2e}  z(1s) {worst['z']:.2e}  y/sd(y) {worst['y_rel']:.2e}  v0 {worst['v0']:.2e}", flush=True)
json.dump(res, open('.tmp/H/restart_synth.json', 'w'), indent=1)
