import sys; sys.path.insert(0, ".tmp/E")
from common import *
from dataclasses import replace
out = {}
sids = sorted(CAL)
for sid in sids:
    k = CAL[sid]["k"]
    train, hs, scale, pca = setup(sid)
    m = ProjectionLinearModel(k, "pca").fit(sid, train, ds.systems[sid]["observed"])
    rec = {"k": k}
    # ---- C: units, CI, family shares of the denominator
    held = [p for f in SYNTH_ROLES["heldout_intervention"] for p in hs["pairs"].get(f, [])]
    rc = E.eval_intervention(m, sid, held, scale, SYNTH_CFG)
    u = rc["_units"]["C_w1000ms"]
    fam = {tr.key: tr.family for tr, _ in held}
    den = {}
    for kk, (n_, d_, _) in u.items():
        den[fam[kk]] = den.get(fam[kk], 0) + d_
    tot = sum(den.values())
    rec["C"] = {"ratio": rc[key_c(SYNTH_CFG)]["ratio"], "ci": rc[key_c(SYNTH_CFG)]["ci95"], "n": rc[key_c(SYNTH_CFG)]["n"],
                "abst": rc["n_abstained_unsupported"], "max_family_share": max(den.values()) / tot if tot > 0 else None,
                "max_unit_share": max(d_ for _, d_, _ in u.values()) / tot if tot > 0 else None}
    # ---- D: seed sensitivity of the point estimate (the verdict thresholds it without a CI)
    nonint = [t for f in SYNTH_ROLES["non_intervention"] for t in hs["by_family"].get(f, [])]
    ds_ = []
    for seed in range(6):
        r = E.eval_closure(m, sid, nonint, pca, scale, replace(SYNTH_CFG, seed=seed))
        ds_.append(r[key_d(SYNTH_CFG)]["micro_gain"])
    rec["D_seeds"] = ds_
    # ---- E: point ratio and a bootstrap that resamples POOL TRAJECTORIES within draw (the protocol's real-data unit)
    pool = [dict(p) for p in hs["pool"]]
    for p in pool:
        p["floor_div"] = float(np.mean((np.asarray(p["future_y"]) - np.asarray(p["floor_future"])) ** 2 / scale))
    re_ = E.eval_microstate(m, sid, pool, scale, SYNTH_CFG, pca=pca, k_match=k)
    trajs = sorted({p["traj"] for p in pool}); grp = {p["traj"]: p["group"] for p in pool}
    rng = np.random.default_rng(1); bs = []
    cfgE = replace(SYNTH_CFG, n_boot=10)
    for b in range(100):
        newpool = []
        for g in sorted(set(grp.values())):
            tg = [t for t in trajs if grp[t] == g]
            pick = rng.choice(len(tg), len(tg))
            for j, ti in enumerate(pick):
                for p in pool:
                    if p["traj"] == tg[ti]:
                        newpool.append(dict(p))  # original trajectory id kept: copies of one trajectory never pair
        rr = E.eval_microstate(m, sid, newpool, scale, cfgE, pca=None, k_match=k)
        bs.append(rr.get("E_ratio_latent_to_random", np.nan))
    rec["E"] = {"ratio": re_["E_ratio_latent_to_random"], "n_matched_pairs": re_["E_latent_matched"]["n_pairs"],
                "pair_ci_of_matched_mean": re_["E_latent_matched"]["ci95"], "traj_boot_ratio_ci": [float(np.nanpercentile(bs, 2.5)), float(np.nanpercentile(bs, 97.5))]}
    out[sid] = rec
    print(sid, k, json.dumps(rec, default=float)[:400], flush=True)
json.dump(out, open(".tmp/E/exp3.json", "w"), indent=1, default=float)
