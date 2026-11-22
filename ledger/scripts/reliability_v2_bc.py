"""Reliability v2 analyses of Parts B and C (PREREG v4 B1-B6, C4-C6). Descriptive; no label. Each output written once (mode "x").

    uv run --project ledger --no-sync python ledger/scripts/reliability_v2_bc.py b1 MANC|MaleCNS     # -> reliability_v2/B1_<fly>.json
    uv run --project ledger --no-sync python ledger/scripts/reliability_v2_bc.py b2 MANC|MaleCNS     # -> reliability_v2/B2_<fly>.json
    uv run --project ledger --no-sync python ledger/scripts/reliability_v2_bc.py b3 MANC|MaleCNS     # -> reliability_v2/B3_<fly>.json (+ B3_MALECNS_CHOICE.json)
    uv run --project ledger --no-sync python ledger/scripts/reliability_v2_bc.py noise               # -> reliability_v2/NOISE.json
    uv run --project ledger --no-sync python ledger/scripts/reliability_v2_bc.py c                   # -> reliability_v2/C.json
    uv run --project ledger --no-sync python ledger/scripts/reliability_v2_bc.py rescue              # -> reliability_v2/RESCUE.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))
import gha4  # noqa: E402
import reliability_v2 as R2  # noqa: E402

from brainir_ledger import agree as AG  # noqa: E402
from brainir_ledger import data_dir  # noqa: E402
from brainir_ledger import mirror as MR  # noqa: E402
from brainir_ledger import pooled  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

REL2 = R2.REL2
H8 = R2.H8
NB = 10000
SEED = 20261401
TAG = {"MANC": "MANC", "MaleCNS": "MCNS"}


# ----------------------------------------------------------------------------------------------------------------- helpers
def _load(campaign: str) -> dict[str, dict]:
    p = data_dir() / "reliability_v2" / f"GHA_{campaign}" / "results.pkl"
    if not p.is_file():
        raise SystemExit(f"{campaign}: no results collected")
    return {r["key"]: r for r in read_log(p) if "error" not in r}


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["type", "seed", "usable", "score"])


def _rep(res: dict, arm: str, score=None) -> pd.DataFrame:
    """Per-replicate table of the results whose key starts with `arm|`; `score(r)` overrides the score (usable unchanged)."""
    rows = []
    for k, r in res.items():
        a, t, s = k.split("|")
        if a != arm:
            continue
        rows.append({"type": t, "seed": int(s[1:]), "usable": bool(r.get("usable")),
                     "score": (score(r) if score is not None else r.get("score"))})
    return _df(rows)


def _vectors(df: pd.DataFrame, types, halves=H8) -> tuple[pd.Series, pd.Series, pd.Series]:
    full = AG.type_scores(df, list(halves[0]) + list(halves[1]), types)
    return full, AG.type_scores(df, halves[0], types), AG.type_scores(df, halves[1], types)


def _rank_rows(a: np.ndarray) -> np.ndarray:
    return rankdata(a, axis=1)


def _rho_rows(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ra, rb = _rank_rows(a), _rank_rows(b)
    ra = ra - ra.mean(axis=1, keepdims=True)
    rb = rb - rb.mean(axis=1, keepdims=True)
    den = np.sqrt((ra ** 2).sum(axis=1) * (rb ** 2).sum(axis=1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, (ra * rb).sum(axis=1) / den, np.nan)


def closure_df(xb: pd.DataFrame, yb: pd.DataFrame, xa: pd.DataFrame, ya: pd.DataFrame, types) -> dict:
    """G7 closure when an intervention turns the pair (X, Y) into (X', Y') (both may change), via agree.closure_vectors."""
    b, y, a, z = (_vectors(d, types) for d in (xb, yb, xa, ya))
    return AG.closure_vectors(b[0], b[1], b[2], a[0], a[1], a[2], y[0], y[1], y[2], ya_full=z[0], ya1=z[1], ya2=z[2], n_boot=NB, seed=SEED)


def _paired(dfa, dfb, types, seeds=range(8)) -> float:
    return AG.paired_agreement(dfa, dfb, types, list(seeds))


def _flips(dl: pd.DataFrame, dr: pd.DataFrame, types, seeds=range(8)) -> list[str]:
    sl, sr = AG.type_scores(dl, list(seeds), types), AG.type_scores(dr, list(seeds), types)
    fl, fr = AG.frac_rhythmic(dl, list(seeds), types), AG.frac_rhythmic(dr, list(seeds), types)
    bl, br = AG.bands(sl), AG.bands(sr)
    return sorted(t for t in types if bl[t] != br[t] and abs(fl[t] - fr[t]) >= 0.5)


def _rescued(dx: pd.DataFrame, dr: pd.DataFrame, flips, seeds=range(8)) -> list[str]:
    if not flips:
        return []
    still = set(_flips(dx, dr, flips, seeds))
    return sorted(set(flips) - still)


def _types_for(fly: str) -> list[str]:
    f = MR.fly(fly)
    return [t for t in gha4.analysed_set()["analysed"] if t in f.halves()["L"]]


# ------------------------------------------------------------------------------------------------------------------ Block 1
def cmd_b1(fly: str) -> None:
    gha4.require_freeze("Block 1 analysis")
    tag = TAG[fly]
    types = _types_for(fly)
    sw = _load(f"b1s-{tag.lower()}-run4")
    pa = gha4.part_a_results(fly)
    tuned = {s: _df([{"type": t, "seed": se, "usable": bool(r.get("usable")), "score": r.get("score")}
                     for (side, t, se), r in pa.items() if side == s and se < 8]) for s in ("L", "R")}
    ng = len(gha4.GRID)
    rows = {s: [] for s in ("L", "R")}
    for k, r in sw.items():
        a, t, se = k.split("|")
        rows[a[-1]].append((t, int(se[1:]), r))
    out = {"marking": "pre-registered (PREREG v4 Block 1); unpaired, Part A design, seeds 0..7, analysed set", "fly": fly,
           "n_types": len(types), "grid": list(gha4.GRID)}
    # matched-current agreement
    per_cur = {}
    for ci, c in enumerate(gha4.GRID):
        d = {s: _df([{"type": t, "seed": se, "usable": True, "score": r["runs"][ci]["score"]} for t, se, r in rows[s]]) for s in ("L", "R")}
        per_cur[f"{c:g}"] = AG.compare(d["L"], d["R"], types, H8, n_boot=2000, seed=SEED)
        per_cur[f"{c:g}"]["share_in_bounds"] = {s: float(np.mean([r["runs"][ci]["in_bounds"] for _t, _s, r in rows[s]])) for s in ("L", "R")}
    out["matched_current"] = per_cur

    def best(r):
        ib = [x["score"] for x in r["runs"][:ng] if x["in_bounds"]]
        return max(ib) if ib else 0.0

    def frac(r):
        ib = [x["score"] for x in r["runs"][:ng] if x["in_bounds"]]
        return float(np.mean([v >= 0.5 for v in ib])) if ib else 0.0
    tf = {}
    for name, fn in (("best_in_bounds", best), ("fraction_rhythmic_in_bounds", frac)):
        d = {s: _df([{"type": t, "seed": se, "usable": True, "score": fn(r)} for t, se, r in rows[s]]) for s in ("L", "R")}
        cmp_ = AG.compare(d["L"], d["R"], types, H8, n_boot=NB, seed=SEED)
        tf[name] = {"left_vs_right": cmp_, "closure_vs_tuned": closure_df(tuned["L"], tuned["R"], d["L"], d["R"], types), "data": d}
    out["tuner_free"] = {k: {kk: vv for kk, vv in v.items() if kk != "data"} for k, v in tf.items()}
    # transplant
    tr = {}
    for s, o in (("L", "R"), ("R", "L")):
        tr[s] = {}
        for t, se, r in rows[s]:
            own, oth = r.get("transplant", {}).get("own"), r.get("transplant", {}).get("other")
            extra = r["runs"][ng:]
            i = 0
            if own is not None:
                tr[s][(t, se, "own")] = extra[i]
                i += 1
            if oth is not None:
                tr[s][(t, se, "other")] = extra[i]
    repro, n_rep = 0, 0
    for s in ("L", "R"):
        for (t, se, kind), x in tr[s].items():
            if kind == "own":
                p = pa[(s, t, se)]
                n_rep += 1
                repro += int(abs((x["score"] or 0) - (p.get("score") or 0)) < 1e-12 and x["n_active_all"] == p.get("n_active_all"))
    out["transplant_own_current_reproduces_accepted_run"] = {"n": n_rep, "identical": repro}

    def tdf(side, kind):
        return _df([{"type": t, "seed": se, "usable": True, "score": x["score"]} for (t, se, k), x in tr[side].items() if k == kind])
    both_r = sorted(t for t in types if all(((t, se, "own") in tr["R"]) and ((t, se, "other") in tr["L"]) for se in range(8)))
    both_l = sorted(t for t in types if all(((t, se, "own") in tr["L"]) and ((t, se, "other") in tr["R"]) for se in range(8)))
    tro = {}
    for label, xs, ys, ts in (("at_right_current", ("L", "other"), ("R", "own"), both_r), ("at_left_current", ("L", "own"), ("R", "other"), both_l)):
        if len(ts) < 10:
            tro[label] = {"n_types": len(ts), "note": "fewer than 10 types accepted on both sides in all 8 seeds"}
            continue
        X, Y = tdf(*xs), tdf(*ys)
        tro[label] = {"left_vs_right": AG.compare(X, Y, ts, H8, n_boot=NB, seed=SEED),
                      "closure_vs_tuned": closure_df(tuned["L"], tuned["R"], X, Y, ts)}
    out["transplant"] = tro
    cands = {"best_in_bounds": out["tuner_free"]["best_in_bounds"]["closure_vs_tuned"]["closure"],
             "fraction_rhythmic_in_bounds": out["tuner_free"]["fraction_rhythmic_in_bounds"]["closure_vs_tuned"]["closure"]}
    for k, v in tro.items():
        if "closure_vs_tuned" in v:
            cands[f"transplant_{k}"] = v["closure_vs_tuned"]["closure"]
    fin = {k: v for k, v in cands.items() if v is not None and np.isfinite(v)}
    out["procedure_share_of_gap"] = {"candidates": cands, "largest": max(fin.items(), key=lambda kv: kv[1]) if fin else None}
    closes = [v["closure_vs_tuned"]["closes_whole_gap"] for v in list(out["tuner_free"].values()) + [x for x in tro.values() if "closure_vs_tuned" in x]]
    out["block1_closes_whole_gap"] = bool(any(closes))
    # flips and rescue (Part A seeds 0..7)
    flips = _flips(tuned["L"], tuned["R"], types)
    out["flips"] = flips
    resc = {"best_in_bounds": _rescued(tf["best_in_bounds"]["data"]["L"], tf["best_in_bounds"]["data"]["R"], flips),
            "fraction_rhythmic_in_bounds": _rescued(tf["fraction_rhythmic_in_bounds"]["data"]["L"], tf["fraction_rhythmic_in_bounds"]["data"]["R"], flips)}
    if both_r:
        ts = [t for t in flips if t in both_r]
        resc["transplant_at_right_current"] = _rescued(tdf("L", "other"), tuned["R"], ts)
    out["rescue"] = {k: {"rescued": v, "share_of_flips": (len(v) / len(flips) if flips else None)} for k, v in resc.items()}
    R2._out(f"B1_{fly}.json", R2._clean(out))


# ------------------------------------------------------------------------------------------------------------------ Block 2
def _b2_frames(fly: str) -> tuple[dict, list[str]]:
    tag = TAG[fly]
    res = _load(f"b2-{tag.lower()}-run4")
    types = _types_for(fly)
    arms = {a: _rep(res, f"B2-{tag}-{a}") for a in ("LW", "RW", "LM", "OWN", "REST", "PERM", "ID")}
    return {"res": res, "arms": arms}, types


def _same_outcome_share(res: dict, a: str, b: str) -> dict:
    keys_a = {k.split("|", 1)[1]: v for k, v in res.items() if k.split("|")[0] == a}
    keys_b = {k.split("|", 1)[1]: v for k, v in res.items() if k.split("|")[0] == b}
    common = sorted(set(keys_a) & set(keys_b))
    same = sum(1 for k in common if all(keys_a[k].get(f) == keys_b[k].get(f) for f in ("usable", "current", "n_tuning_runs")))
    return {"n": len(common), "identical_usable_current_runs": same, "share": same / len(common) if common else None}


def cmd_b2(fly: str) -> None:
    gha4.require_freeze("Block 2 analysis")
    tag = TAG[fly]
    d, types = _b2_frames(fly)
    res, A = d["res"], d["arms"]
    # sanity (i): identity hybrid digests equal L on W
    ids = {k.split("|", 1)[1]: v for k, v in res.items() if k.startswith(f"B2-{tag}-ID|")}
    lw = {k.split("|", 1)[1]: v for k, v in res.items() if k.startswith(f"B2-{tag}-LW|")}
    id_ok = sum(1 for k, v in ids.items() if k in lw and v["digest"] == lw[k]["digest"])
    relab = _same_outcome_share(res, f"B2-{tag}-PERM", f"B2-{tag}-LW")
    trans = _same_outcome_share(res, f"B2-{tag}-LM", f"B2-{tag}-RW")
    rho_relab = AG.spearman(AG.type_scores(A["PERM"], list(range(8)), types).to_numpy(), AG.type_scores(A["LW"], list(range(8)), types).to_numpy())
    rho_trans = AG.spearman(AG.type_scores(A["LM"], list(range(8)), types).to_numpy(), AG.type_scores(A["RW"], list(range(8)), types).to_numpy())
    ok_i = len(ids) > 0 and id_ok == len(ids)
    ok_ii = (trans["share"] is not None and relab["share"] is not None and trans["share"] >= relab["share"] - 0.02
             and rho_trans >= rho_relab - 0.01 and rho_trans >= 0.95)
    out = {"marking": "pre-registered (PREREG v4 Block 2); paired draws, seeds 0..7, analysed set", "fly": fly, "n_types": len(types),
           "sanity": {"i_identity_hybrid": {"n": len(ids), "digests_identical": id_ok, "pass": ok_i},
                      "ii_full_transplant": {"L_on_M_vs_R_on_W": trans, "full_seed_rho": rho_trans, "pass": bool(ok_ii)},
                      "relabelling_control": {**relab, "full_seed_rho": rho_relab}},
           "sanity_pass": bool(ok_i and ok_ii)}
    if not out["sanity_pass"]:
        out["note"] = "a sanity check failed: no other Block 2 number is read (PREREG v4 B2.3)"
        R2._out(f"B2_{fly}.json", R2._clean(out))
        return
    before = AG.compare(A["LW"], A["RW"], types, H8, n_boot=NB, seed=SEED)
    out["before_L_on_W_vs_R_on_W"] = before
    r_ref = _paired(A["PERM"], A["LW"], types)
    out["paired"] = {"r_ref_relabelling": r_ref, "LW_vs_RW": _paired(A["LW"], A["RW"], types)}
    for arm in ("OWN", "REST"):
        xb = _vectors(A["LW"], types)
        xa = _vectors(A[arm], types)
        y = _vectors(A["RW"], types)
        cl = AG.closure_vectors(xb[0], xb[1], xb[2], xa[0], xa[1], xa[2], y[0], y[1], y[2], n_boot=NB, seed=SEED)
        rp = _paired(A[arm], A["RW"], types)
        out[f"H_{arm.lower()}"] = {"closure": cl, "paired_rho": rp,
                                   "paired_closure": (rp - out["paired"]["LW_vs_RW"]) / (r_ref - out["paired"]["LW_vs_RW"])
                                   if r_ref != out["paired"]["LW_vs_RW"] else None}
    flips = _flips(A["LW"], A["RW"], types)
    out["flips_paired_baseline"] = flips
    out["rescue"] = {arm: _rescued(A[arm], A["RW"], flips) for arm in ("OWN", "REST")}
    R2._out(f"B2_{fly}.json", R2._clean(out))


# ------------------------------------------------------------------------------------------------------------------ Block 3
def cmd_b3(fly: str) -> None:
    gha4.require_freeze("Block 3 analysis")
    tag = TAG[fly]
    b2 = json.loads((REL2 / f"B2_{fly}.json").read_text())
    if not b2.get("sanity_pass"):
        raise SystemExit(f"Block 2 sanity failed for {fly}: Block 3 is not read (B2.3)")
    d, types = _b2_frames(fly)
    A = d["arms"]
    res = _load(f"b3-{tag.lower()}-run4")
    variants = sorted({k.split("|")[0].split("-")[-1] for k in res})
    xb, y = _vectors(A["LW"], types), _vectors(A["RW"], types)
    r_ref = _paired(A["PERM"], A["LW"], types)
    rp0 = _paired(A["LW"], A["RW"], types)
    out = {"marking": "pre-registered (PREREG v4 Block 3); paired draws, seeds 0..7, analysed set", "fly": fly, "variants": variants}
    for v in variants:
        H = _rep(res, f"B3-{tag}-{v}")
        ts = sorted(set(types) & set(H["type"]))
        xa = _vectors(H, ts)
        xbt, yt = _vectors(A["LW"], ts), _vectors(A["RW"], ts)
        cl = AG.closure_vectors(xbt[0], xbt[1], xbt[2], xa[0], xa[1], xa[2], yt[0], yt[1], yt[2], n_boot=NB, seed=SEED)
        rp = _paired(H, A["RW"], ts)
        fl_ = [t for t in _flips(A["LW"], A["RW"], types) if t in ts]
        out[v] = {"n_types": len(ts), "closure": cl, "paired_rho": rp,
                  "paired_closure": (rp - rp0) / (r_ref - rp0) if r_ref != rp0 else None,
                  "rescued_flips": _rescued(H, A["RW"], fl_)}
    if fly == "MANC":
        A_c = {c: out[f"A{c}"]["closure"]["closure"] for c in range(1, 6) if f"A{c}" in out}
        O_c = {c: out[f"O{c}"]["closure"]["closure"] for c in range(1, 6) if f"O{c}" in out}
        reading = {}
        for c in range(1, 6):
            a, o = out.get(f"A{c}", {}).get("closure", {}), out.get(f"O{c}", {}).get("closure", {})
            ai, oi = (a.get("closure_interval") or [None, None]), (o.get("closure_interval") or [None, None])
            reading[c] = {"suffices": bool(a.get("closes_whole_gap")), "needed": (o.get("after") or {}).get("words") == "a real gap",
                          "contributes": bool((ai[0] is not None and ai[0] > 0) or (oi[1] is not None and oi[1] < 1))}
        tot = sum(v for v in A_c.values() if v is not None and np.isfinite(v))
        out["reading"] = {"per_class": reading, "sum_alone": tot, "interact": abs(tot - 1) > 0.2}
        fin_a = {c: v for c, v in A_c.items() if v is not None and np.isfinite(v)}
        fin_o = {c: v for c, v in O_c.items() if v is not None and np.isfinite(v)}
        choice = []
        if fin_a:
            ca = max(fin_a, key=lambda c: (fin_a[c], -c))
            choice.append(f"A{ca}")
        if fin_o:
            co = min(fin_o, key=lambda c: (fin_o[c], c))
            choice.append(f"O{co}")
            if fin_a and co == ca and len(fin_a) > 1:
                second = sorted(fin_a, key=lambda c: (-fin_a[c], c))[1]
                choice.append(f"A{second}")
        out["malecns_choice"] = choice
        R2._out("B3_MALECNS_CHOICE.json", {"rule": "PREREG v4 B3.4", "variants": choice})
    R2._out(f"B3_{fly}.json", R2._clean(out))


# ------------------------------------------------------------------------------------------------------------- count noise
def cmd_noise() -> None:
    gha4.require_freeze("count-noise analysis")
    b2 = json.loads((REL2 / "B2_MANC.json").read_text())
    if not b2.get("sanity_pass"):
        raise SystemExit("Block 2 sanity failed (MANC): the noise models are not read (B2.3)")
    d, types = _b2_frames("MANC")
    A = d["arms"]
    obs = AG.compare(A["LW"], A["RW"], types, H8, n_boot=NB, seed=SEED)
    out = {"marking": "pre-registered (PREREG v4 B4); MANC only (pre-floor counts), paired draws, seeds 0..7, analysed set",
           "observed_left_right_paired_design": obs,
           "nb_dispersion": json.loads((gha4.GATES4 / "NB_DISPERSION.json").read_text())}
    cn = _load("cn-run4")
    for model, (a, b) in (("poisson", ("P1", "P2")), ("negative_binomial", ("N1", "N2"))):
        X, Y = _rep(cn, f"CN-{a}"), _rep(cn, f"CN-{b}")
        ts = sorted(set(types) & set(X["type"]) & set(Y["type"]))
        cc = AG.compare(X, Y, ts, H8, n_boot=NB, seed=SEED)
        lo, hi = cc["bootstrap"]["interval"]["rho_x"]
        out[model] = {"copy_vs_copy": cc, "paired_copy_vs_copy": _paired(X, Y, ts),
                      "copy1_vs_L_on_W": AG.compare(X, A["LW"], ts, H8, n_boot=2000, seed=SEED),
                      "reproduces_left_right": bool(lo is not None and hi is not None and obs["primary"]["rho_x"] is not None
                                                    and lo <= obs["primary"]["rho_x"] <= hi)}
    flips = _flips(A["LW"], A["RW"], types)
    floors = {}
    for f in (1, 3, 10):
        try:
            fr = _load(f"fl-{f}-run4")
        except SystemExit:
            floors[f] = {"note": "not run"}
            continue
        X, Y = _rep(fr, f"FL-{f}-LW"), _rep(fr, f"FL-{f}-LM")
        ts = sorted(set(types) & set(X["type"]) & set(Y["type"]))
        floors[f] = {"left_vs_right": AG.compare(X, Y, ts, H8, n_boot=NB, seed=SEED), "closure_vs_floor5": closure_df(A["LW"], A["RW"], X, Y, ts),
                     "rescued_flips": _rescued(X, Y, [t for t in flips if t in ts])}
    out["floors"] = floors
    out["flips_paired_baseline"] = flips
    R2._out("NOISE.json", R2._clean(out))


# ------------------------------------------------------------------------------------------------------------------- Part C
NET = ("3a", "3b", "4", "5a", "5b", "6", "7", "8")
SIDES_DISTINCT = {"1", "2", "3a", "3b", "5a", "6", "7"}


def _half_flies_fix(fix: str) -> dict[str, pd.DataFrame]:
    """Per-replicate tables (seeds 0..7) of the four half-flies and the rewired control (left) under a fix ('0' = unfixed)."""
    out = {}
    if fix in ("0", "2"):
        sc = pooled.pooled_score if fix == "2" else None
        for fly in ("MANC", "MaleCNS"):
            pa = gha4.part_a_results(fly)
            for s in ("L", "R"):
                out[f"{TAG[fly]}-{s}"] = _df([{"type": t, "seed": se, "usable": bool(r.get("usable")),
                                              "score": (sc(r) if sc else r.get("score"))} for (side, t, se), r in pa.items() if side == s and se < 8])
        crw = _load("crw-run4")
        out["RW-MANC-L"] = _rep(crw, "CRW-MANC-L", score=sc)
        return out
    if fix == "1":
        ng = len(gha4.GRID)

        def best(r):
            ib = [x["score"] for x in r["runs"][:ng] if x["in_bounds"]]
            return max(ib) if ib else 0.0
        for fly in ("MANC", "MaleCNS"):
            sw = _load(f"b1s-{TAG[fly].lower()}-run4")
            for s in ("L", "R"):
                out[f"{TAG[fly]}-{s}"] = _df([{"type": k.split("|")[1], "seed": int(k.split("|")[2][1:]), "usable": True, "score": best(r)}
                                             for k, r in sw.items() if k.split("|")[0] == f"B1-{TAG[fly]}-{s}"])
        cx = _load("cx-1-run4")
        out["RW-MANC-L"] = _df([{"type": k.split("|")[1], "seed": int(k.split("|")[2][1:]), "usable": True, "score": best(r)}
                                for k, r in cx.items() if k.split("|")[0] == "CX-1-RW-MANC-L"])
        return out
    cx = _load(f"cx-{fix}-run4")
    for tag in ("MANC", "MCNS"):
        for s in ("L", "R"):
            df = _rep(cx, f"CX-{fix}-{tag}-{s}")
            if len(df):
                out[f"{tag}-{s}"] = df
    rw = _rep(cx, f"CX-{fix}-RW-MANC-L")
    if len(rw):
        out["RW-MANC-L"] = rw
    return out


def _sr(hf: dict, types, n_boot=NB, seed=SEED) -> dict:
    """C6.4: SR = rho_x(MANC-L, MaleCNS-L) - rho_x(MANC-L, rewired MANC-L), one bootstrap over types."""
    v = {k: (_vectors(hf[k], types)[1].to_numpy(), _vectors(hf[k], types)[2].to_numpy()) for k in ("MANC-L", "MCNS-L", "RW-MANC-L")}

    def rx(a, b, idx):
        return (_rho_rows(v[a][0][idx], v[b][1][idx]) + _rho_rows(v[a][1][idx], v[b][0][idx])) / 2
    n = len(types)
    p_idx = np.arange(n)[None, :]
    point = float((rx("MANC-L", "MCNS-L", p_idx) - rx("MANC-L", "RW-MANC-L", p_idx))[0])
    idx = np.random.default_rng(seed).integers(0, n, size=(n_boot, n))
    bs = rx("MANC-L", "MCNS-L", idx) - rx("MANC-L", "RW-MANC-L", idx)
    bs = bs[np.isfinite(bs)]
    return {"SR": point, "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], "n_types": n, "n_boot_used": int(len(bs))}


def _drivers(df: pd.DataFrame, types) -> int:
    return int((AG.type_scores(df, list(range(8)), types) >= 0.5).sum())


def _evaluate_fix(fix: str, unfixed_drivers: float | None, gains: dict) -> dict:
    hf = _half_flies_fix(fix)
    fm, fc = MR.fly("MANC"), MR.fly("MaleCNS")
    ana = gha4.analysed_set()["analysed"]
    tm = [t for t in ana if t in fm.halves()["L"]]
    tc = [t for t in ana if t in fc.halves()["L"]]
    common = sorted(set(tm) & set(tc))
    rec = {"fix": fix}
    g = gains.get(fix) if fix != "0" else {"gain": 1.0, "verdict": "pass"}
    rec["control_DNg100"] = g
    c1 = g is not None and g.get("verdict") == "pass"
    if fix in ("3a", "3b"):
        rec["cross_fly"] = {"note": "not evaluable: no pre-floor MaleCNS counts (PREREG v4 C2.3)"}
        c2x = False
    else:
        pl = AG.compare(hf["MANC-L"], hf["MCNS-L"], common, H8, n_boot=NB, seed=SEED)
        pr = AG.compare(hf["MANC-R"], hf["MCNS-R"], common, H8, n_boot=NB, seed=SEED)
        rx = (R2._f(pl["primary"]["rho_x"]) + R2._f(pr["primary"]["rho_x"])) / 2
        c = (R2._f(pl["primary"]["c"]) + R2._f(pr["primary"]["c"])) / 2
        rec["cross_fly"] = {"L": pl, "R": pr, "rho_x_mean": rx, "c_mean": c, "ratio": rx / c if c else None}
        c2x = bool(np.isfinite(rx) and np.isfinite(c) and c > 0 and rx / c >= 0.80)
    lr = {"MANC": AG.compare(hf["MANC-L"], hf["MANC-R"], tm, H8, n_boot=NB, seed=SEED)}
    if "MCNS-L" in hf:
        lr["MaleCNS"] = AG.compare(hf["MCNS-L"], hf["MCNS-R"], tc, H8, n_boot=NB, seed=SEED)
    rxl = float(np.mean([R2._f(v["primary"]["rho_x"]) for v in lr.values()]))
    cl = float(np.mean([R2._f(v["primary"]["c"]) for v in lr.values()]))
    rec["left_right"] = {**lr, "rho_x_mean": rxl, "c_mean": cl, "ratio": rxl / cl if cl else None,
                         "required": fix in SIDES_DISTINCT}
    c2lr = (not rec["left_right"]["required"]) or bool(np.isfinite(rxl) and np.isfinite(cl) and cl > 0 and rxl / cl >= 0.80)
    dr = {k: _drivers(hf[k], tm if k.startswith("MANC") else tc) for k in ("MANC-L", "MANC-R", "MCNS-L", "MCNS-R") if k in hf}
    mean_dr = float(np.mean(list(dr.values())))
    rec["drivers"] = {"per_half_fly": dr, "mean": mean_dr, "unfixed_mean": unfixed_drivers}
    c3 = unfixed_drivers is None or (0.5 * unfixed_drivers <= mean_dr <= 2 * unfixed_drivers)
    if "MCNS-L" in hf and "RW-MANC-L" in hf:
        rec["specific_reproducibility"] = _sr(hf, common)
        c4a = rec["specific_reproducibility"]["ci95"][0] > 0
    else:
        rec["specific_reproducibility"] = {"note": "not evaluable without MaleCNS"}
        c4a = False
    if "RW-MANC-L" in hf and len(hf["RW-MANC-L"]):
        rw = _drivers(hf["RW-MANC-L"], tm)
        rec["rewired_drivers"] = {"n": rw, "few_limit": 2}
        c4 = c4a and rw <= 2
    else:
        rec["rewired_drivers"] = {"note": "no rewired control (floors: a rewired network has no pre-floor counts, C2.3)"}
        c4 = False
    rec["criteria"] = {"1_control": bool(c1), "2_agreement_cross_fly": bool(c2x), "2_agreement_left_right": bool(c2lr),
                       "3_still_informative": bool(c3), "4_still_about_wiring": bool(c4)}
    rec["passes"] = bool(c1 and c2x and c2lr and c3 and c4) if fix != "0" else None
    return rec


def cmd_c() -> None:
    gha4.require_freeze("Part C analysis")
    gains = json.loads((gha4.GATES4 / "C_GAINS.json").read_text())["fixes"]
    out = {"marking": "pre-registered (PREREG v4 Part C); analysed set, seeds 0..7, unpaired draws"}
    un = _evaluate_fix("0", None, gains)
    out["unfixed"] = un
    ud = un["drivers"]["mean"]
    for fix in ("1", "2") + NET:
        if gains.get(fix, {}).get("verdict") != "pass":
            out[fix] = {"fix": fix, "control_DNg100": gains.get(fix), "passes": False, "note": "failed its DNg100 control at every gain (C4)"}
            continue
        try:
            out[fix] = _evaluate_fix(fix, ud, gains)
        except SystemExit as e:
            out[fix] = {"fix": fix, "passes": False, "note": f"not evaluated: {e}"}
    passing = [f for f in ("1", "2") + NET if out[f].get("passes")]
    sr = {f: out[f]["specific_reproducibility"]["SR"] for f in passing}
    proc = [f for f in passing if f in ("1", "2")]
    net = [f for f in passing if f in NET]
    out["passing"] = passing
    out["best_procedure"] = max(proc, key=lambda f: sr[f]) if proc else None
    out["best_network"] = max(net, key=lambda f: sr[f]) if net else None
    out["robust_model_before_fix9"] = max(passing, key=lambda f: sr[f]) if passing else None
    R2._out("C.json", R2._clean(out))


def cmd_rescue() -> None:
    """B6 rescue table from the written Block 1-3 and noise outputs: per flipped type the single interventions that rescue it, per
    intervention the share of flips it rescues alone (separately for the unpaired Part A design and the paired design)."""
    gha4.require_freeze("rescue table")
    out = {"marking": "pre-registered (PREREG v4 B6)"}
    for fly in ("MANC", "MaleCNS"):
        rec = {}
        p1 = REL2 / f"B1_{fly}.json"
        if p1.is_file():
            b1 = json.loads(p1.read_text())
            fl = b1.get("flips", [])
            rec["unpaired_part_a_design"] = {"flips": fl, "by_intervention": {k: v for k, v in b1.get("rescue", {}).items()},
                                             "by_type": {t: [k for k, v in b1.get("rescue", {}).items() if t in v.get("rescued", [])] for t in fl}}
        inter = {}
        fl = None
        p2 = REL2 / f"B2_{fly}.json"
        if p2.is_file():
            b2 = json.loads(p2.read_text())
            fl = b2.get("flips_paired_baseline")
            for k, v in (b2.get("rescue") or {}).items():
                inter[f"block2_{k.lower()}"] = v
        p3 = REL2 / f"B3_{fly}.json"
        if p3.is_file():
            b3 = json.loads(p3.read_text())
            for v in b3.get("variants", []):
                if v.startswith("A"):
                    inter[f"block3_class{v[1:]}_alone"] = b3[v].get("rescued_flips", [])
        pn = REL2 / "NOISE.json"
        if fly == "MANC" and pn.is_file():
            nz = json.loads(pn.read_text())
            for f_, v in (nz.get("floors") or {}).items():
                if "rescued_flips" in v:
                    inter[f"floor_{f_}"] = v["rescued_flips"]
        if fl is not None:
            rec["paired_design"] = {"flips": fl,
                                    "by_intervention": {k: {"rescued": v, "share_of_flips": (len(v) / len(fl) if fl else None)} for k, v in inter.items()},
                                    "by_type": {t: [k for k, v in inter.items() if t in v] for t in fl}}
        out[fly] = rec
    R2._out("RESCUE.json", R2._clean(out))


def main() -> None:
    cmd, args = sys.argv[1:2], sys.argv[2:]
    if cmd == ["b1"]:
        cmd_b1(args[0])
    elif cmd == ["b2"]:
        cmd_b2(args[0])
    elif cmd == ["b3"]:
        cmd_b3(args[0])
    elif cmd == ["noise"]:
        cmd_noise()
    elif cmd == ["c"]:
        cmd_c()
    elif cmd == ["rescue"]:
        cmd_rescue()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
