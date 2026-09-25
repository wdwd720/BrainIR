import json, numpy as np
c = json.load(open("extra/benchmark/calibration.json"))
rows = c["per_system"]
rng = np.random.default_rng(0)
gap = np.array(c["relative_A_gap_truelatent_vs_full"])
def v(m, k):
    a = np.array([r[m][k] for r in rows if r[m][k] is not None], float); return a[np.isfinite(a)]
stats = {"tau_A": (gap, 90, True), "tau_C": (v("true_latent","C"), 75, False), "tau_D": (v("true_latent","D"), 90, False), "tau_E": (v("true_latent","E"), 90, False)}
for name, (x, q, clip) in stats.items():
    pt = np.percentile(x, q); pt = max(0, pt) if clip else pt
    b = np.array([np.percentile(x[rng.integers(0, len(x), len(x))], q) for _ in range(4000)])
    if clip: b = np.maximum(0, b)
    print(f"{name}: n={len(x)} point={pt:.4g}  bootstrap-over-systems 95% [{np.percentile(b,2.5):.4g}, {np.percentile(b,97.5):.4g}]  (median {np.median(b):.4g})")
print("sorted top-6 of the A gap:", np.sort(gap)[-6:])
# how often would the ORACLE (true latent) itself pass each rule at the calibrated tau? and the full-state ceiling?
taus = c["tolerances"]
for m in ("true_latent", "full_state", "pca_k"):
    D, E = np.array([r[m]["D"] if r[m]["D"] is not None else np.nan for r in rows]), np.array([r[m]["E"] if r[m]["E"] is not None else np.nan for r in rows])
    Cc = np.array([r[m]["C"] if r[m]["C"] is not None else np.nan for r in rows])
    print(f"{m:12s} pass D<=tau_D {np.mean(D<=taus['tau_D']):.2f}  pass E<=tau_E {np.mean(E<=taus['tau_E']):.2f}  C<1 (point) {np.mean(Cc<1):.2f}  C abstained pairs>0: {np.mean([ (r[m].get('C_abstained') or 0)>0 for r in rows]):.2f}")
