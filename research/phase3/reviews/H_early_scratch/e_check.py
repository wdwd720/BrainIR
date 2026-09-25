import json, pickle, numpy as np
cal = json.load(open('extra/benchmark/calibration.json'))
pools = pickle.load(open('.tmp/H/pools_dev.pkl', 'rb'))
name = {sid: v[0] for sid, v in pools.items()}
rows = {r[0]: r for r in pickle.load(open('.tmp/H/e_rows.pkl', 'rb'))}
d = []
for r in cal['per_system']:
    n = name[r['sid']]; e_cal = r['true_latent']['E']; e_me = rows[n][1]
    d.append(abs(e_cal - e_me) / max(e_cal, 1e-30))
    if n in ('linear_k1', 'linear_k3', 'linear_k6', 'nonmarkov', 'wta', 'parameter_trap'):
        print(f"{n:16s} k={r['k']} calibration true-latent E {e_cal:.3e}  mine {e_me:.3e}  pca_k E {r['pca_k']['E']:.3e}  full_state E {r['full_state']['E']:.3e}")
print('max relative difference to calibration over', len(d), 'systems:', max(d))
print('calibration systems:', sorted(name[r['sid']] for r in cal['per_system']) == sorted(name[r['sid']] for r in cal['per_system']), len(cal['per_system']))
