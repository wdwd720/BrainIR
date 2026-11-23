"""t2. Which procedure carries each hit-list sentence, and why the tuned procedure failed its positive control in BANC.

Reads: the replicate tables and collected result logs (read only), posthoc_v6/H_posthoc.json, gates_v6/BANC_GATE.json,
gates_v6/TYPE_SETS_v6.json. Post hoc and descriptive.
(a) Hit-list overlap at the authors' cut 0.5 for every pair under each procedure, with chance-corrected forms beside the
    overlap coefficient: k / E and (k - E) / (min(n_x, n_y) - E), E = n_x n_y / N.
(b) DNg100's 16 tuned BANC replicates: accepted current and active read-out motor neurons, against the gate at the authors' 400.
(c) Does the sweep depend on the tuner's setting K (>= 1 active read-out motor neuron)? Recompute every sweep replicate without
    that requirement and count changed scores.
"""

from __future__ import annotations

import numpy as np

from _common import H, H8, H16, LEDGER, O6, S6, SETS, jload, screens, show, ts

S = screens()


def ov(X, xh, Y, yh, set_key, cut=0.5):
    tl = SETS[set_key]
    sx, sx1, sx2 = ts(X, tl).to_numpy(), ts(X, tl, xh[0]).to_numpy(), ts(X, tl, xh[1]).to_numpy()
    sy, sy1, sy2 = ts(Y, tl).to_numpy(), ts(Y, tl, yh[0]).to_numpy(), ts(Y, tl, yh[1]).to_numpy()
    o = O6.overlap(sx, sy, sx1, sx2, sy1, sy2, cut, n_boot=2000, names=tl)
    p, b = o["point"], o["bootstrap_95"]
    E = p["chance_expectation"]
    m = min(p["n_x"], p["n_y"])
    return {"N": p["N"], "n_x": p["n_x"], "n_y": p["n_y"], "k": p["k"], "E": round(E, 2), "p": round(p["hypergeom_p"], 4),
            "k/E": round(p["k"] / E, 2) if E else None, "(k-E)/(min-E)": round((p["k"] - E) / (m - E), 2) if m > E else None,
            "OC_ratio": None if p["OC_ratio"] is None else round(p["OC_ratio"], 2),
            "OC_ratio_95": [None if b["OC_ratio"]["lo"] is None else round(b["OC_ratio"]["lo"], 2),
                            None if b["OC_ratio"]["hi"] is None else round(b["OC_ratio"]["hi"], 2)]}


rows = {
    "MANC->MaleCNS tuned (B1r x B2r; abstract's 'at chance')": ov(S["B1r"], H16, S["B2r"], H16, "manc_mcns_high_noDNg100"),
    "MANC->MaleCNS sweep (DX x MS)": ov(S["DX"], H8, S["MS"], H8, "manc_mcns_high_noDNg100"),
    "MANC->BANC tuned (B1r x BT)": ov(S["B1r"], H16, S["BT"], H16, "manc_banc_high_noDNg100"),
    "MANC->BANC sweep (DX x BS; C4 of record)": ov(S["DX"], H8, S["BS"], H8, "manc_banc_high_noDNg100"),
    "MaleCNS->BANC tuned (B2r x BT)": ov(S["B2r"], H16, S["BT"], H16, "mcns_banc_high_noDNg100"),
    "MaleCNS->BANC sweep (MS x BS; C4 of record)": ov(S["MS"], H8, S["BS"], H8, "mcns_banc_high_noDNg100"),
    "A1->BANC sweep (C4 of record)": ov(S["A1"], H16, S["BS"], H8, "manc_banc_high_noDNg100"),
    "A1->BANC tuned": ov(S["A1"], H16, S["BT"], H16, "manc_banc_high_noDNg100"),
    "MANC->BANC sweep, same-name subset": ov(S["DX"], H8, S["BS"], H8, "three_animal_same_name_noDNg100"),
    "MaleCNS->BANC sweep, same-name subset": ov(S["MS"], H8, S["BS"], H8, "three_animal_same_name_noDNg100"),
    "MANC->MaleCNS sweep, same-name subset": ov(S["DX"], H8, S["MS"], H8, "three_animal_same_name_noDNg100"),
}
show("(a) overlap at 0.5 by pair and procedure (OC-ratio intervals from 2,000 type resamples)", rows)
lk = H["pairs"]["sweep_dx1_x_ms"]["high|without_DNg100"]["cuts"]["0.5"]["overlap"]["point"]
show("check against the locked post hoc sweep pair (H_posthoc)", {"k": lk["k"], "n_x": lk["n_x"], "n_y": lk["n_y"], "OC_ratio": round(lk["OC_ratio"], 3)})
hits = {k: int((ts(S[k], SETS["three_animal_noDNg100"]) >= 0.5).sum()) for k in ("B1r", "B2r", "BT", "DX", "MS", "BS")}
show("hits (>= 0.5) among the 181 three-animal types, per screen", hits)

# (b) DNg100 in the tuned BANC screen
res, _, _ = S6.merged("thirdfly_v1", "bt")
recs = sorted((r for k, r in res.items() if k.startswith("BT|DNg100|")), key=lambda r: r["seed"])
cur = [r["current"] for r in recs]
fail = [{"seed": r["seed"], "score": round(r["score"], 2), "current": r["current"], "active_readout_MNs": r["n_active_readout"]}
        for r in recs if not (r["usable"] and r["score"] >= 0.5)]
gate = jload("gates_v6/BANC_GATE.json")["conditions"]["intact"]
show("(b) DNg100, tuned BANC screen (whole type, K = 1)", {
    "accepted currents": {str(c): cur.count(c) for c in sorted(set(cur))},
    "active read-out MNs (median, range)": [float(np.median([r["n_active_readout"] for r in recs])),
                                             min(r["n_active_readout"] for r in recs), max(r["n_active_readout"] for r in recs)],
    "failing seeds": fail,
    "gate at the authors' current 400 (one copy, 2-s runs)": {"mean": round(gate["mean"], 3), "frac_ge_0_5": gate["frac_ge_0_5"],
                                                               "active_MN_median": gate["active_mn_median"]}})

# (c) K-independence of the sweep
out = {}
for label, (area, prefix, src) in {"MANC dx-1-run4": ("reliability_v2", None, "MODAL"), "MaleCNS ms-mcns-run6": ("posthoc_v6", "ms", None),
                                   "BANC bs-banc-run6": ("thirdfly_v1", "bs", None)}.items():
    rs = S6.results(area, "dx-1-run4", src) if prefix is None else S6.merged(area, prefix)[0]
    n_rep = changed = ok_no_mn_pos = 0
    for r in rs.values():
        runs = r.get("runs") or []
        if not runs:
            continue
        n_rep += 1
        with_k = max([x["score"] for x in runs if x.get("in_bounds") and x.get("score") is not None] or [0.0])
        without_k = max([x["score"] for x in runs if x.get("verdict") == "ok" and x.get("score") is not None] or [0.0])
        changed += int(abs(with_k - without_k) > 1e-12)
        ok_no_mn_pos += sum(1 for x in runs if x.get("verdict") == "ok" and x.get("n_active_readout", 1) == 0 and (x.get("score") or 0) > 0)
    out[label] = {"replicates": n_rep, "replicate scores changed without the K requirement": changed,
                  "in-bounds runs with 0 active read-out MNs and a positive score": ok_no_mn_pos}
show("(c) the sweep's score with and without the >= 1 active read-out MN requirement", out)

# (d) the same neuron, same network, 1-s runs, same seeds 0-7: DNg100 (whole type) in the BANC sweep log at fixed currents, against the
# tuner's accepted runs (15 of 16 at 256). Does a stronger fixed current rescue the tuner's failing draws?
rs, _, _ = S6.merged("thirdfly_v1", "bs")
tab = {}
for k in sorted((k for k in rs if k.startswith("BS|DNg100|")), key=lambda s: int(s.split("|")[2][1:])):
    r = rs[k]
    tab[f"seed {r['seed']}"] = {f"{x['current']:g}": [round(x["score"], 2), x["n_active_readout"], bool(x["in_bounds"])]
                                for x in r["runs"] if 181 <= x["current"] <= 1024}
show("(d) DNg100 in BANC, sweep log: [score, active read-out MNs, in bounds] at currents 181-1,024 (tuned seeds 0, 7 failed)", tab)
summ = {}
for c in ("256", "362.039", "512", "724.077"):
    v = [tab[s][c] for s in tab if c in tab[s]]
    summ[c] = {"draws >= 0.5": sum(1 for x in v if x[0] >= 0.5), "of": len(v), "median active MNs": float(np.median([x[1] for x in v]))}
show("(d) summary per current (seeds 0-7)", summ)
