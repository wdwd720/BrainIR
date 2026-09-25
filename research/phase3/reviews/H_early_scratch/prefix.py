# Does a synthetic trajectory's shared prefix depend on t_end (same protocol and noise_seed)?
import sys, json, numpy as np
sys.path.insert(0, 'extra/generator')
from p3synth.systems import build_all
S = {s.meta['name']: s for s in build_all(20260924, 'dev')}
for name in ('linear_k3', 'hopf', 'hidden_exogenous', 'nuisance_ou'):
    s = S[name]
    p = {"system": s.system_id, "params_seed": 1000, "weight_noise": None, "r0": {"kind": "zero"}, "t_end": 1.52, "dt": 0.01,
         "stimulus": [[0.0, 1.0 if s.input_dim == 1 else [1.0] * s.input_dim]], "events": [], "noise_seed": 7}
    a = s.simulate(p); b = s.simulate(dict(p, t_end=1.82))
    n = len(a['t'])
    print(f"{name:18s} max|x_a - x_b| over the common 1.52 s: {np.abs(a['x'] - b['x'][:n]).max():.3g}   "
          f"|z| diff {np.abs(a['z'] - b['z'][:n]).max():.3g}   sd(x) {a['x'].std():.3g}")
