"""Run 5 Stage 0 (RUN5_PROMPT section 4): one tidy per-type table per screen, each shown to reproduce the locked aggregate it came from.

Outputs `research/ledger/pertype_v1/`:
  A0_copies.csv                     the authors' single-neuron screen (A0), one row per copy (933)
  MANC_L.csv MANC_R.csv             Part A's one-sided half-fly screens, one row per matched type (308 / 250)
  MaleCNS_L.csv MaleCNS_R.csv
  B1r.csv B2r.csv A1.csv            the whole-type screens, one row per type (321 / 328 / 321)
  match_confidence.csv              the cross-fly type match of every MaleCNS type (328): evidence and confidence
  VERIFY.json                       every reproduction check (exact equality with the locked aggregates)
  MANIFEST.json, README.md
Read-only on every locked file; no simulation. Type score = G5 (PREREG v4): mean score over usable replicates, 0 if none; halves =
replicates 0-63 / 64-127 (A0) and seeds 0-7 / 8-15 (the 16-seed screens). Sides: A0 as Part A0 (the full-cord root side); the half-fly
and whole-type tables as G3 (run 4's mirror module). Match confidence rule: LOG L160.

    uv run --project ledger --no-sync python ledger/scripts/pertype_v1.py build
"""

from __future__ import annotations

import glob
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "ledger" / "src"))
sys.path.insert(0, str(REPO / "src"))
import gha4  # noqa: E402
import reliability_v2 as R  # noqa: E402
from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import agree as AG  # noqa: E402
from brainir_ledger import mirror as MR  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402

OUT = RESEARCH / "pertype_v1"
P1, P2 = RESEARCH / "predictions", RESEARCH / "predictions_v2"
FMT = "%.17g"
CSV_TOL = 1e-9   # the locked CSVs print scores to 10 significant digits (|error| <= 5e-11 for scores in [0, 1])
H16 = (list(range(8)), list(range(8, 16)))
ANN = sorted(glob.glob(str(REPO / "data" / "raw" / "external" / "malecns_v1.0_body_annotations" / "*.feather")))
CONF_RULE = ("high = every MaleCNS member mapped by the curated body match (mancBodyid), no member whose body match conflicts with its "
             "mancType string, and one-to-one naming (the type's MaleCNS label(s) map only to this MANC type, and this MANC type receives "
             "only one MaleCNS label); low = any conflict; medium = the rest; none = the MANC type has no MaleCNS group. Per-side member "
             "count equality is reported as its own column, not used (LOG L160).")


def band(x: float) -> str:
    return "driver" if x >= 0.5 else ("non_driver" if x < 0.05 else "indeterminate")


def _max_diff(a: dict, b: dict, keys) -> float:
    return max(abs(float(a[k]) - float(b[k])) for k in keys)


def _boot_diff(a: dict, b: dict) -> float:
    """Largest difference between two bootstrap blocks' intervals (all numeric leaves)."""
    out = 0.0

    def walk(x, y):
        nonlocal out
        if isinstance(x, dict):
            for k in x:
                if k in y:
                    walk(x[k], y[k])
        elif isinstance(x, (list, tuple)):
            for u, v in zip(x, y):
                walk(u, v)
        elif isinstance(x, (int, float)) and not isinstance(x, bool) and isinstance(y, (int, float)) and x is not None and y is not None:
            if not (np.isnan(x) and np.isnan(y)):
                out = max(out, abs(float(x) - float(y)))
    walk(a, b)
    return out


# ------------------------------------------------------------------------------------------------ cross-fly match confidence
def match_confidence(fm, fc) -> tuple[pd.DataFrame, dict]:
    import pyarrow.feather as feather  # noqa: PLC0415

    ann = feather.read_table(ANN[0]).to_pandas().set_index("bodyId")
    t = fc.net.table
    dn = t[(t["superclass"] == "descending_neuron") & t["manc_type_mapped"].notna()]
    a = ann.reindex(dn["bodyId"].astype(int))
    body = a["mancBodyid"].notna().to_numpy()
    conflict_n = body & a["mancType"].notna().to_numpy() & (a["mancType"].astype(str).to_numpy() != dn["manc_type_mapped"].astype(str).to_numpy())
    neuron_level = {"n_dn_mapped": int(len(dn)), "n_via_body_match": int(body.sum()), "n_via_mancType_string": int((~body).sum()),
                    "n_body_match_disagreeing_with_mancType_string": int(conflict_n.sum())}
    lab_to_manc, manc_to_lab = {}, {}
    for _, r in dn.iterrows():
        lab_to_manc.setdefault(r["type"], set()).add(r["manc_type_mapped"])
        manc_to_lab.setdefault(r["manc_type_mapped"], set()).add(r["type"])
    rows = []
    for mt, idx in sorted(fc.groups.items()):
        bids = [int(t.iloc[i]["bodyId"]) for i in idx]
        aa = ann.reindex(bids)
        vb = aa["mancBodyid"].notna().to_numpy()
        cf = vb & aa["mancType"].notna().to_numpy() & (aa["mancType"].astype(str).to_numpy() != mt)
        labels = sorted({str(t.iloc[i]["type"]) for i in idx})
        one = len(manc_to_lab.get(mt, ())) == 1 and all(len(lab_to_manc[lab]) == 1 for lab in labels)
        mL, mR = sum(fc.side[i] == "L" for i in idx), sum(fc.side[i] == "R" for i in idx)
        g = fm.groups.get(mt)
        aL = sum(fm.side[i] == "L" for i in g) if g else 0
        aR = sum(fm.side[i] == "R" for i in g) if g else 0
        conf = "low" if cf.any() else ("high" if (vb.all() and one) else "medium")
        rows.append({"manc_type": mt, "malecns_labels": ";".join(labels), "n_malecns_members": len(idx), "malecns_L": mL, "malecns_R": mR,
                     "manc_L": aL, "manc_R": aR, "in_manc": g is not None, "all_body_matched": bool(vb.all()), "n_body_matched": int(vb.sum()),
                     "n_conflicts": int(cf.sum()), "one_to_one_naming": bool(one), "same_name": all(lab == mt for lab in labels),
                     "per_side_counts_equal": bool(g is not None and (mL, mR) == (aL, aR)), "confidence": conf})
    return pd.DataFrame(rows), neuron_level


# ------------------------------------------------------------------------------------------------ A0 by copy
def a0_copies(prim_manc: set, conf: dict) -> tuple[pd.DataFrame, dict]:
    root = N.full_cord().table.set_index("bodyId")["rootSide"].map({"LHS": "L", "RHS": "R"})
    rep = pd.read_parquet(P1 / "A0" / "replicates.parquet")
    neur = pd.read_csv(P1 / "A0" / "neurons.csv")
    full = R._neuron_scores(rep, "replicate", list(range(128)))
    h1, h2 = R._neuron_scores(rep, "replicate", range(64)), R._neuron_scores(rep, "replicate", range(64, 128))
    use = rep.groupby("bodyId")["usable"].sum()
    use1 = rep[rep["replicate"] < 64].groupby("bodyId")["usable"].sum()
    use2 = rep[rep["replicate"] >= 64].groupby("bodyId")["usable"].sum()
    bt = rep.drop_duplicates("bodyId").set_index("bodyId")["manc_type"]
    side = {int(b): (root.get(int(b)) if root.get(int(b)) in ("L", "R") else "unsided") for b in bt.index}
    by_type: dict = {}
    for b, ty in bt.items():
        by_type.setdefault(str(ty), {"L": [], "R": [], "unsided": []})[side[int(b)]].append(int(b))
    nmeta = neur.set_index("bodyId")
    rows = []
    for b, ty in bt.items():
        d = by_type[str(ty)]
        rows.append({"manc_type": ty, "bodyId": int(b), "side": side[int(b)], "members_L": len(d["L"]), "members_R": len(d["R"]),
                     "members_unsided": len(d["unsided"]), "n_replicates": 128, "n_usable": int(use[b]), "n_usable_h1": int(use1[b]),
                     "n_usable_h2": int(use2[b]), "score": float(full[b]), "score_h1": float(h1[b]), "score_h2": float(h2[b]),
                     "n_weak": int(nmeta.loc[b, "n_weak"]), "n_strong": int(nmeta.loc[b, "n_strong"]),
                     "type_matched": bool(d["L"] and d["R"]), "type_one_each_side": len(d["L"]) == 1 and len(d["R"]) == 1,
                     "type_primary_run4": str(ty) in prim_manc, "cross_fly_match": conf.get(str(ty), "none")})
    df = pd.DataFrame(rows).sort_values(["manc_type", "side", "bodyId"]).reset_index(drop=True)
    return df, by_type


def verify_a0(df: pd.DataFrame) -> dict:
    """A0.json (run 4, locked): both comparisons' point estimates and bootstrap intervals, from this table only."""
    locked = json.load(open(RESEARCH / "reliability_v2" / "A0.json"))["A0"]
    neur = pd.read_csv(P1 / "A0" / "neurons.csv").set_index("bodyId")["mean_score"].fillna(0.0)
    score_diff = float((df.set_index("bodyId")["score"] - neur.reindex(df["bodyId"]).to_numpy()).abs().max())
    s = df.set_index("bodyId")
    out = {"per_copy_score_vs_neurons_csv_max_abs_diff": score_diff}
    groups: dict = {}
    for _, r in df.iterrows():
        if r["side"] in ("L", "R"):
            groups.setdefault(r["manc_type"], {"L": [], "R": []})[r["side"]].append(int(r["bodyId"]))
    matched = {t: d for t, d in groups.items() if d["L"] and d["R"]}
    one = {t: d for t, d in matched.items() if len(d["L"]) == 1 and len(d["R"]) == 1}
    out["counts"] = {"types_total": int(df["manc_type"].nunique()), "matched": len(matched), "one_member_each_side": len(one),
                     "unsided_members": int((df["side"] == "unsided").sum())}
    out["counts_locked"] = {k: locked[k] for k in ("types_total", "matched", "one_member_each_side", "unsided_members")}
    for label, sub in (("primary_one_member_each_side", one), ("all_matched_types", matched)):
        types = sorted(sub)
        v = {}
        for col in ("score", "score_h1", "score_h2"):
            v[col] = tuple(pd.Series({t: float(np.mean([s.loc[b, col] for b in sub[t][side]])) for t in types}).reindex(types) for side in ("L", "R"))
        mc = {t: (len(sub[t]["L"]), len(sub[t]["R"])) for t in types}
        r = AG.compare_vectors(v["score"][0], v["score"][1], v["score_h1"][0], v["score_h2"][0], v["score_h1"][1], v["score_h2"][1],
                               member_counts=mc, n_boot=10000, seed=R.SEED_BOOT)
        out[label] = {"point_max_abs_diff": _max_diff(r["primary"], locked[label]["primary"], ("rho_full", "rho_x", "c", "ratio")),
                      "bootstrap_max_abs_diff": _boot_diff(r.get("bootstrap", {}), locked[label].get("bootstrap", {})),
                      "words": r.get("words"), "words_locked": locked[label].get("words")}
    out["per_copy_score_tolerance"] = CSV_TOL
    out["pass"] = (score_diff <= CSV_TOL and out["counts"] == out["counts_locked"]
                   and all(out[k]["point_max_abs_diff"] == 0 and out[k]["bootstrap_max_abs_diff"] == 0 and out[k]["words"] == out[k]["words_locked"]
                           for k in ("primary_one_member_each_side", "all_matched_types")))
    return out


# ------------------------------------------------------------------------------------------------ half-fly screens
def halffly_tables(ts: dict, fm, fc, conf: dict) -> dict[str, pd.DataFrame]:
    hf = R.half_flies()
    halves = {"MANC": fm.halves(), "MCNS": fc.halves()}
    out = {}
    for key, name in (("MANC-L", "MANC_L"), ("MANC-R", "MANC_R"), ("MCNS-L", "MaleCNS_L"), ("MCNS-R", "MaleCNS_R")):
        fly = "MANC" if key.startswith("MANC") else "MaleCNS"
        types = sorted(ts[fly]["matched"])
        df = hf[key]
        full, s1, s2 = AG.type_scores(df, None, types), AG.type_scores(df, H16[0], types), AG.type_scores(df, H16[1], types)
        fr = AG.frac_rhythmic(df, None, types)
        use = df[df["type"].isin(types)].groupby("type")["usable"].sum()
        nrep = df[df["type"].isin(types)].groupby("type")["usable"].size()
        h = halves["MANC" if fly == "MANC" else "MCNS"]
        prim = set(ts[fly]["primary_homolog_consistent"])
        rows = [{"manc_type": t, "screen": key, "members_L": len(h["L"][t]), "members_R": len(h["R"][t]), "n_seeds": int(nrep[t]),
                 "n_usable": int(use[t]), "score": float(full[t]), "score_h1": float(s1[t]), "score_h2": float(s2[t]),
                 "frac_rhythmic": float(fr[t]), "band": band(float(full[t])), "primary_run4": t in prim,
                 "cross_fly_match": conf.get(t, "none")} for t in types]
        out[name] = pd.DataFrame(rows)
    return out


def verify_halffly(tabs: dict, ts: dict) -> dict:
    """A.json (run 4, locked): the six agreements on the primary and on all matched types, point estimates and intervals."""
    locked = json.load(open(RESEARCH / "reliability_v2" / "A.json"))
    key = {"MANC-L": "MANC_L", "MANC-R": "MANC_R", "MCNS-L": "MaleCNS_L", "MCNS-R": "MaleCNS_R"}

    def vecs(name, types):
        d = tabs[name].set_index("manc_type")
        return d["score"].reindex(types), d["score_h1"].reindex(types), d["score_h2"].reindex(types)

    out = {}
    for section, tm, tc in (("six_agreements_primary_homolog_consistent", ts["MANC"]["primary_homolog_consistent"], ts["MaleCNS"]["primary_homolog_consistent"]),
                            ("six_agreements_all_matched_types", ts["MANC"]["matched"], ts["MaleCNS"]["matched"])):
        common = sorted(set(tm) & set(tc))
        mcm = {t: (int(r.members_L), int(r.members_R)) for r in tabs["MANC_L"].itertuples() for t in [r.manc_type]}
        mcc = {t: (int(r.members_L), int(r.members_R)) for r in tabs["MaleCNS_L"].itertuples() for t in [r.manc_type]}
        pairs = {"MANC-L vs MANC-R": ("MANC-L", "MANC-R", list(tm), {t: mcm[t] for t in tm}),
                 "MaleCNS-L vs MaleCNS-R": ("MCNS-L", "MCNS-R", list(tc), {t: mcc[t] for t in tc}),
                 "MANC-L vs MaleCNS-L": ("MANC-L", "MCNS-L", common, None), "MANC-R vs MaleCNS-R": ("MANC-R", "MCNS-R", common, None),
                 "MANC-L vs MaleCNS-R": ("MANC-L", "MCNS-R", common, None), "MANC-R vs MaleCNS-L": ("MANC-R", "MCNS-L", common, None)}
        res = {}
        for pname, (a, b, types, mc) in pairs.items():
            xf, x1, x2 = vecs(key[a], types)
            yf, y1, y2 = vecs(key[b], types)
            r = AG.compare_vectors(xf, yf, x1, x2, y1, y2, member_counts=mc, n_boot=10000, seed=R.SEED_BOOT)
            lk = locked[section][pname]
            res[pname] = {"point_max_abs_diff": _max_diff(r["primary"], lk["primary"], ("rho_full", "rho_x", "c", "ratio")),
                          "bootstrap_max_abs_diff": _boot_diff(r.get("bootstrap", {}), lk.get("bootstrap", {})),
                          "words": r.get("words"), "words_locked": lk.get("words")}
        out[section] = res
    tc_lock = locked["type_counts"]
    out["type_counts"] = {"MANC_matched": len(tabs["MANC_L"]), "MaleCNS_matched": len(tabs["MaleCNS_L"]),
                          "locked_MANC_matched": tc_lock["MANC"]["matched"], "locked_MaleCNS_matched": tc_lock["MaleCNS"]["matched"]}
    out["pass"] = (all(v["point_max_abs_diff"] == 0 and v["bootstrap_max_abs_diff"] == 0 and v["words"] == v["words_locked"]
                       for s in ("six_agreements_primary_homolog_consistent", "six_agreements_all_matched_types") for v in out[s].values())
                   and out["type_counts"]["MANC_matched"] == out["type_counts"]["locked_MANC_matched"]
                   and out["type_counts"]["MaleCNS_matched"] == out["type_counts"]["locked_MaleCNS_matched"])
    return out


# ------------------------------------------------------------------------------------------------ whole-type screens
def wholetype_table(arm: str, path: Path, col: str, f, conf: dict) -> pd.DataFrame:
    rep = pd.read_parquet(path / "replicates.parquet")
    rep = rep.rename(columns={col: "seed", "manc_type": "type"})
    types = sorted(rep["type"].unique())
    full = AG.type_scores(rep, None, types)
    s1, s2 = AG.type_scores(rep, H16[0], types), AG.type_scores(rep, H16[1], types)
    fr = AG.frac_rhythmic(rep, None, types)
    use = rep.groupby("type")["usable"].sum()
    nrep = rep.groupby("type")["usable"].size()
    tc = pd.read_csv(path / "types.csv", dtype={"manc_type": str}).set_index("manc_type")
    rows = []
    for t in types:
        idx = f.groups.get(t, [])
        rows.append({"manc_type": t, "screen": arm, "n_members": int(tc.loc[t, "n_members"]), "members_L": sum(f.side[i] == "L" for i in idx),
                     "members_R": sum(f.side[i] == "R" for i in idx), "members_other": sum(f.side[i] not in ("L", "R") for i in idx),
                     "n_replicates": int(nrep[t]), "n_usable": int(use[t]), "score": float(full[t]), "score_h1": float(s1[t]),
                     "score_h2": float(s2[t]), "frac_rhythmic": float(fr[t]), "band": band(float(full[t])), "cross_fly_match": conf.get(t, "none")})
    return pd.DataFrame(rows)


def verify_wholetype(df: pd.DataFrame, path: Path) -> dict:
    tc = pd.read_csv(path / "types.csv", dtype={"manc_type": str}).set_index("manc_type")
    d = df.set_index("manc_type")
    ps = tc["primary_score"].astype(float).reindex(d.index)
    out = {"n_types": len(d), "n_types_locked": len(tc), "score_vs_primary_score_max_abs_diff": float((d["score"] - ps).abs().max()),
           "band_mismatches": int((d["band"] != tc["band"].reindex(d.index)).sum()),
           "n_usable_mismatches": int((d["n_usable"] != tc["n_usable"].reindex(d.index)).sum()),
           "n_members_mismatches": int((d["n_members"] != tc["n_members"].reindex(d.index)).sum())}
    out["score_tolerance"] = CSV_TOL
    out["pass"] = (out["n_types"] == out["n_types_locked"] and out["score_vs_primary_score_max_abs_diff"] <= CSV_TOL and out["band_mismatches"] == 0
                   and out["n_usable_mismatches"] == 0 and out["n_members_mismatches"] == 0)
    return out


# ------------------------------------------------------------------------------------------------ build
def build() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise SystemExit(f"{OUT} exists and is not empty: the per-type tables are written once; refused")
    OUT.mkdir(parents=True, exist_ok=True)
    ts = gha4.type_sets()
    fm, fc = MR.fly("MANC"), MR.fly("MaleCNS")
    mc_df, neuron_level = match_confidence(fm, fc)
    conf = dict(zip(mc_df["manc_type"], mc_df["confidence"]))
    verify = {}
    b2 = json.load(open(P1 / "B2" / "provenance.json"))["type_mapping"]
    verify["match_confidence"] = {"neuron_level": neuron_level, "locked_B2_type_mapping": b2,
                                  "pass": all(neuron_level[k] == b2[k] for k in neuron_level),
                                  "confidence_counts": mc_df["confidence"].value_counts().to_dict()}
    a0, _ = a0_copies(set(ts["MANC"]["primary_homolog_consistent"]), conf)
    verify["A0_copies"] = verify_a0(a0)
    tabs = halffly_tables(ts, fm, fc, conf)
    verify["halffly"] = verify_halffly(tabs, ts)
    whole = {"B1r": wholetype_table("B1r", P2 / "B1r", "seed", fm, conf), "B2r": wholetype_table("B2r", P2 / "B2r", "seed", fc, conf),
             "A1": wholetype_table("A1", P1 / "A1", "replicate", fm, conf)}
    for arm, path in (("B1r", P2 / "B1r"), ("B2r", P2 / "B2r"), ("A1", P1 / "A1")):
        verify[arm] = verify_wholetype(whole[arm], path)
    verify["all_pass"] = all(v["pass"] for v in verify.values() if isinstance(v, dict) and "pass" in v)
    files = {"A0_copies.csv": a0, "match_confidence.csv": mc_df, **{f"{k}.csv": v for k, v in tabs.items()}, **{f"{k}.csv": v for k, v in whole.items()}}
    for name, df in files.items():
        df.to_csv(OUT / name, index=False, float_format=FMT, lineterminator="\n")
    (OUT / "VERIFY.json").write_text(json.dumps(verify, indent=1, sort_keys=True, default=str) + "\n")
    untracked = [str(Path(p).relative_to(REPO)) for p in ANN]
    for camp in ("pa-manc-run4", "pa-mcns-run4"):
        for pre in ("GHA_", "MODAL_"):
            p = data_dir() / "reliability_v2" / f"{pre}{camp}" / "results.pkl"
            if p.is_file():
                untracked.append(str(p.relative_to(REPO)))
    untracked.append(str((data_dir() / "reliability" / "GHA_r4-run3" / "results.pkl").relative_to(REPO)))
    from reproduce_manc_connectivity import EXTERNAL, EXT_DIR  # noqa: PLC0415
    ext = sorted(str((EXT_DIR / Path(rel).name).relative_to(REPO)) for rel, _ in EXTERNAL.values() if (EXT_DIR / Path(rel).name).is_file())
    man = {"stage": "run 5 Stage 0: per-type tables (RUN5_PROMPT section 4)",
           "tables": {n: list(df.columns) for n, df in files.items()},
           "rows": {n: len(df) for n, df in files.items()},
           "locked_sources": {"A0_copies.csv": ["predictions/A0/replicates.parquet", "predictions/A0/neurons.csv (LOCK_predictions_v1)"],
                              "MANC_L/R, MaleCNS_L/R": ["Part A replicate results (untracked; reproduce reliability_v2/A.json, LOCK_reliability_v2)"],
                              "B1r.csv / B2r.csv": ["predictions_v2/<arm>/replicates.parquet, types.csv (LOCK_predictions_v2)"],
                              "A1.csv": ["predictions/A1/replicates.parquet, types.csv (LOCK_predictions_v1)"],
                              "match_confidence.csv": ["MaleCNS body annotations (untracked raw file); reproduces predictions/B2/provenance.json type_mapping"],
                              "type sets": ["gates_v4/TYPE_SETS.json (LOCK_reliability_v2)"]},
           "rules": {"type_score": "G5 (PREREG v4): mean score over usable replicates, 0 if none (A0 per copy: the same over the copy's replicates)",
                     "halves": "A0 replicates 0-63 / 64-127; the 16-seed screens seeds 0-7 / 8-15", "band": "driver >= 0.5, non_driver < 0.05, else indeterminate",
                     "sides": "A0: Part A0's full-cord root side; half-fly and whole-type tables: G3 via run 4's mirror module",
                     "match_confidence": CONF_RULE},
           "untracked_inputs": sorted(set(untracked)) + ext,
           "verify_all_pass": verify["all_pass"]}
    (OUT / "MANIFEST.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n")
    (OUT / "README.md").write_text(README)
    print(json.dumps({k: (v.get("pass") if isinstance(v, dict) else v) for k, v in verify.items()}, indent=1))


README = """# Per-type tables (run 5, Stage 0; RUN5_PROMPT section 4)

One tidy table per screen, made by `ledger/scripts/pertype_v1.py` from locked files (and, for Part A's half-fly screens, from the
replicate results whose summary statistics run 4 locked). `VERIFY.json` shows that each table reproduces the locked aggregate it came
from exactly: A0_copies.csv gives `reliability_v2/A0.json` (both comparisons, point estimates and bootstrap intervals); the four
half-fly tables give `reliability_v2/A.json`'s six agreements (primary and all matched types); B1r/B2r/A1 equal the locked
`types.csv` scores (to the 10 significant digits the CSV prints), bands, usable counts and member counts; match_confidence.csv reproduces the B2 arm's locked mapping counts.

- Type score: mean score over usable replicates, 0 if none (G5). `score_h1` / `score_h2`: the same on the two halves of the seeds
  (A0: replicates 0-63 / 64-127). Band: driver >= 0.5, non_driver < 0.05, else indeterminate.
- Sides and member counts: A0 by the full-cord root side (as Part A0); the half-fly and whole-type tables by G3 (MaleCNS sides are
  output sides, PREREG v4 G3). `members_other` counts members with no L/R side.
- `cross_fly_match`: the confidence of the MaleCNS -> MANC type match (match_confidence.csv; rule in MANIFEST.json and LOG L160):
  high = all members body-matched, no conflict with the `mancType` string, one-to-one naming; low = any conflict; medium = the rest;
  none = no MaleCNS group for this MANC type.
- `primary_run4` / `type_primary_run4`: run 4's primary (homolog-consistent) type set (`gates_v4/TYPE_SETS.json`).
"""


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        build()
    else:
        raise SystemExit(__doc__)
