"""Stage 1: produce the prediction arms (PREREG section 3). Prediction side; never reads labels.

    uv run --project ledger --no-sync python ledger/scripts/run_arms.py authors       # A1, A1-lo10, A0 (no simulation)
    uv run --project ledger --no-sync python ledger/scripts/run_arms.py b0            # B0 frozen copy, per type
    uv run --project ledger --no-sync python ledger/scripts/run_arms.py baselines     # S
    uv run --project ledger --no-sync python ledger/scripts/run_arms.py b1 --lower 5  # B1-lo5 campaign (then --lower 10)
    uv run --project ledger --no-sync python ledger/scripts/run_arms.py select-b1     # PREREG 3.4 rule -> B1, B1-alt
    uv run --project ledger --no-sync python ledger/scripts/run_arms.py controls      # ten null networks, kept B1 procedure
    uv run --project ledger --no-sync python ledger/scripts/run_arms.py b5 | b4 | b2
    uv run --project ledger --no-sync python ledger/scripts/run_arms.py g1 | g4
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brainir.sim import ModelConfig  # noqa: E402
from brainir.sim.screen import ScreenConfig  # noqa: E402

from brainir_ledger import PREDICTIONS, REPO, RESEARCH  # noqa: E402
from brainir_ledger import arms as AR  # noqa: E402
from brainir_ledger import authors as AU  # noqa: E402
from brainir_ledger import baselines as BL  # noqa: E402
from brainir_ledger import controls as CT  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402
from brainir_ledger.scoring.stats import spearman  # noqa: E402
from brainir_ledger.tables import write_json  # noqa: E402

B0_PATH = REPO / "benchmarks" / "dng100_walking_cpg" / "results" / "dn_screen_manc_v1.2.1_nt-paper_r16.json"
GATES = RESEARCH / "gates"


def cmd_authors(a) -> None:
    files = AU.fetch()
    fl = N.front_leg()
    for lo, arm in ((5, "A1"), (10, "A1-lo10")):
        types = AU.a1_types(lo, files)
        reps = AU.a1_replicates(lo, files)
        groups = N.type_groups(fl.table)
        ids = fl.table["bodyId"].to_numpy()
        types["n_members"] = types["manc_type"].map(lambda t: len(groups.get(t, [])))
        types["member_ids"] = types["manc_type"].map(lambda t: ";".join(str(int(ids[m])) for m in groups.get(t, [])))
        missing = sorted(set(types["manc_type"]) ^ set(groups))
        if missing:
            raise RuntimeError(f"{arm}: type names differ from the authors' excitatory type groups: {missing}")
        AR.write_arm(arm, types, reps, {"source": "authors' type-level screen, run 32818378", "usable": f"{lo} <= nActive <= 1500",
                                        "readout": "authors' 138 module-labelled front-leg MNs", "files": AU.FILES,
                                        "zenodo_configs": AU.ZENODO_CONFIGS},
                     {"type_set_vs_brainir_groups_symmetric_difference": missing})
        print(arm, len(types), "types; never usable", int((types["status"] != "ok").sum()), "; drivers", int((types["band"] == "driver").sum()))
    neur = AU.a0_neurons(fl.table, files)
    t0 = AU.per_type_from_neurons(neur, "A0", "authors_manc_frontleg_2025-08-13")
    # long table: one row per neuron and replicate (PREREG 11), with the type key
    sc = pd.read_csv(files["a0_score"], index_col=0)
    ac = pd.read_csv(files["a0_activity"], index_col=0)
    long = sc.stack().rename("score").to_frame().join(ac.stack().rename("n_active_notebook"))
    long.index.names = ["row", "replicate"]
    long = long.reset_index()
    long["row"] = long["row"].astype(int)
    long["replicate"] = long["replicate"].astype(int)
    long["bodyId"] = fl.table.loc[long["row"], "bodyId"].to_numpy().astype(int)
    long["manc_type"] = fl.table.loc[long["row"], "type"].to_numpy()
    long["usable"] = (long["n_active_notebook"] >= AU.USABLE_LO) & (long["n_active_notebook"] <= AU.USABLE_HI)
    AR.write_arm("A0", t0, long[["manc_type", "bodyId", "row", "replicate", "score", "n_active_notebook", "usable"]],
                 {"source": "authors' single-neuron screen, 8 runs x 16 = 128 replicates", "usable": "5 <= nActive <= 1500",
                  "files": AU.FILES, "replicates_layout": "one row per neuron and replicate (933 x 128)"}, {})
    from brainir_ledger.tables import write_csv
    write_csv(neur, PREDICTIONS / "A0" / "neurons.csv")
    print("A0", len(t0), "types from", len(neur), "neurons")


def cmd_b0(a) -> None:
    raw = B0_PATH.read_bytes()
    d = json.loads(raw)
    fl = N.front_leg()
    reps_raw = pd.DataFrame(d["replicates"])
    unusable = reps_raw[~reps_raw["usable"]]
    weak = unusable[unusable["n_active_all"] < 5].groupby("candidate").size()
    strong = unusable[unusable["n_active_all"] >= 5].groupby("candidate").size()
    rows = []
    for c in d["candidates"]:
        k = int(c["candidate"])
        rows.append({"row": k, "bodyId": int(c["source_id"]), "manc_type": c["cell_type"], "n_usable": c["n_usable"],
                     "mean_score": c["mean_score"], "n_weak": int(weak.get(k, 0)), "n_strong": int(strong.get(k, 0))})
    neur = pd.DataFrame(rows)
    assert (fl.table.loc[neur["row"], "bodyId"].to_numpy() == neur["bodyId"].to_numpy()).all()
    t0 = AU.per_type_from_neurons(neur, "B0", "manc_v1.2.1_frontleg")
    reps = pd.DataFrame(d["replicates"])
    reps.insert(0, "manc_type", fl.table.loc[reps["candidate"], "type"].to_numpy())
    reps.insert(1, "bodyId", fl.table.loc[reps["candidate"], "bodyId"].to_numpy().astype(int))
    AR.write_arm("B0", t0, reps, {"source": "benchmarks/dng100_walking_cpg/results/dn_screen_manc_v1.2.1_nt-paper_r16.json (frozen as is)",
                                  "screen_config": d["summary"]["screen_config"]},
                 {"b0_file_sha256": hashlib.sha256(raw).hexdigest()})
    print("B0", len(t0), "types from", len(neur), "neurons")


def cmd_baselines(a) -> None:
    fl = N.front_leg()
    groups = N.type_groups(fl.table)
    oracle = json.loads((REPO / "benchmarks" / "dng100" / "oracle" / "oracle.json").read_text(encoding="utf-8"))
    core_ids = list(oracle["networks"]["manc_v1.2.1"]["core"].values())
    pos = {int(b): i for i, b in enumerate(fl.table["bodyId"])}
    core = [pos[int(b)] for b in core_ids]
    df = BL.compute(fl.C, fl.W, fl.readout, groups, core)
    ids = fl.table["bodyId"].to_numpy()
    base = pd.DataFrame({"arm": "S", "network": fl.name, "manc_type": df["manc_type"],
                         "n_members": df["manc_type"].map(lambda t: len(groups[t])),
                         "member_ids": df["manc_type"].map(lambda t: ";".join(str(int(ids[m])) for m in groups[t]))})
    for c in ("n_replicates", "n_usable", "mean_score", "median_score", "frac_ge_0_5", "best_score", "median_freq_hz", "median_current",
              "median_n_active_readout"):
        base[c] = None
    base["status"] = "ok"
    base["band"] = None
    out = base.merge(df, on="manc_type")
    out["primary_score"] = out["S1_direct_mn"]  # convenience only; the analysis uses each S column (PREREG 3.5)
    AR.write_arm("S", out, None, {"definitions": "PREREG section 3.5", "core_positions": core, "core_source": "benchmarks/dng100/oracle/oracle.json"},
                 {})
    print("S", len(out), "types")


def cmd_b1(a) -> None:
    fl = N.front_leg()
    groups = N.type_groups(fl.table)
    scfg = AR.b1_screen_cfg(a.lower)
    mcfg = ModelConfig(t_end=1.0)
    arm = f"B1-lo{a.lower}"
    jobs = AR.group_jobs(arm, groups, scfg, mcfg)
    res = AR.run(arm, jobs, {"W": fl.W, "sizes": fl.sizes, "readout": fl.readout})
    types, reps = AR.aggregate_group_arm(arm, fl.name, fl, groups, res, scfg)
    AR.write_arm(arm, types, reps, {"model": mcfg.to_dict(), "screen": scfg.to_dict(), "seeds": AR.SEEDS, "groups": "authors' excitatory type groups",
                                    "readout": "144 front-leg MNs"},
                 {"results_log_sha256": AR.results_log_sha(arm), "env": AR.env_record(), "network_meta": fl.meta})
    print(arm, len(types), "types; usable types", int((types["status"] == "ok").sum()), "; drivers", int((types["band"] == "driver").sum()))


def cmd_select_b1(a) -> None:
    a1 = pd.read_csv(PREDICTIONS / "A1" / "types.csv").set_index("manc_type")["primary_score"]
    rho = {}
    for lo in (5, 10):
        b = pd.read_csv(PREDICTIONS / f"B1-lo{lo}" / "types.csv").set_index("manc_type")["primary_score"]
        common = a1.index.intersection(b.index)
        rho[lo] = spearman(a1.loc[common], b.loc[common])
    keep = 10 if abs(rho[5] - rho[10]) < 0.01 else max(rho, key=rho.get)
    other = 5 if keep == 10 else 10
    for src, dst in ((keep, "B1"), (other, "B1-alt")):
        if (PREDICTIONS / dst).exists():
            shutil.rmtree(PREDICTIONS / dst)
        shutil.copytree(PREDICTIONS / f"B1-lo{src}", PREDICTIONS / dst)
        df = pd.read_csv(PREDICTIONS / dst / "types.csv")
        df["arm"] = dst
        df.to_csv(PREDICTIONS / dst / "types.csv", index=False, lineterminator="\n", float_format="%.10g")
        prov = json.loads((PREDICTIONS / dst / "provenance.json").read_text())
        prov["selected_from"] = f"B1-lo{src}"
        prov["files_sha256"] = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((PREDICTIONS / dst).glob("*"))
                                if f.is_file() and f.name != "provenance.json"}
        write_json(prov, PREDICTIONS / dst / "provenance.json")
    sel = {"rule": "PREREG 3.4: larger Spearman with A1 over all 321 types (primary scores); |diff| < 0.01 -> 10", "spearman": rho,
           "kept_lower_bound": keep, "B1-alt_lower_bound": other}
    write_json(sel, PREDICTIONS / "B1" / "selection.json")
    print(json.dumps(sel))


def cmd_controls(a) -> None:
    sel = json.loads((PREDICTIONS / "B1" / "selection.json").read_text())
    lower = int(sel["kept_lower_bound"])
    fl = N.front_leg()
    groups = N.type_groups(fl.table)
    scfg = AR.b1_screen_cfg(lower)
    mcfg = ModelConfig(t_end=1.0)
    names = CT.control_names() if not a.only else [a.only]
    for name in names:
        Wc, stats = CT.build(fl, name)
        jobs = AR.group_jobs(name, groups, scfg, mcfg)
        res = AR.run(name, jobs, {"W": Wc, "sizes": fl.sizes, "readout": fl.readout}, batched=True)
        types, reps = AR.aggregate_group_arm(name, f"{fl.name}+{name}", fl, groups, res, scfg)
        AR.write_arm(name, types, reps, {"model": mcfg.to_dict(), "screen": scfg.to_dict(), "seeds": AR.SEEDS, "control": name,
                                         "construction": stats},
                     {"results_log_sha256": AR.results_log_sha(name), "control_matrix_sha256":
                      hashlib.sha256(Wc.tocsr().data.tobytes() + Wc.tocsr().indices.tobytes() + Wc.tocsr().indptr.tobytes()).hexdigest()})
        print(name, "usable types", int((types["status"] == "ok").sum()), "; drivers", int((types["band"] == "driver").sum()))


def cmd_controls_pilot(a) -> None:
    """Cost pilot before the control campaign: one rewired and one class-shuffled network, 20 random types x 4 seeds."""
    import time as _time

    sel = json.loads((PREDICTIONS / "B1" / "selection.json").read_text())
    fl = N.front_leg()
    groups = N.type_groups(fl.table)
    rng = np.random.default_rng(7)
    pick = sorted(rng.choice(sorted(groups), 20, replace=False))
    scfg, mcfg = AR.b1_screen_cfg(int(sel["kept_lower_bound"])), ModelConfig(t_end=1.0)
    out = {}
    for name in ("B1-ctl-rewire-101", "B1-ctl-classshuffle-201"):
        Wc, _ = CT.build(fl, name)
        jobs = AR.group_jobs(f"PILOT-{name}", {t: groups[t] for t in pick}, scfg, mcfg, seeds=[0, 1, 2, 3])
        t0 = _time.time()
        res = AR.run(f"PILOT-{name}", jobs, {"W": Wc, "sizes": fl.sizes, "readout": fl.readout}, campaign=f"PILOT_{name}")
        walls = [r["job_wall_s"] for r in res.values() if "error" not in r]
        runs = [r["n_tuning_runs"] for r in res.values() if "error" not in r]
        out[name] = {"n": len(walls), "mean_job_s": float(np.mean(walls)), "p95_job_s": float(np.percentile(walls, 95)),
                     "mean_tuning_runs": float(np.mean(runs)), "usable_frac": float(np.mean([r["usable"] for r in res.values() if "error" not in r])),
                     "campaign_wall_s": round(_time.time() - t0, 1)}
    per_job = float(np.mean([v["mean_job_s"] for v in out.values()]))
    est_core_h = per_job * 10 * 321 * 16 / 3600
    out["estimate_full_campaign"] = {"jobs": 10 * 321 * 16, "container_hours": est_core_h,
                                     "usd_at_list_price": est_core_h * (0.0473 + 3 * 0.008)}
    write_json(out, GATES / "controls_pilot.json")
    print(json.dumps(out, indent=1))


def cmd_b5(a) -> None:
    sel = json.loads((PREDICTIONS / "B1" / "selection.json").read_text())
    fl = N.front_leg()
    groups = N.type_groups(fl.table)
    scfg = AR.b1_screen_cfg(int(sel["kept_lower_bound"]))
    mcfg = ModelConfig(t_end=1.0)
    jobs = AR.b5_jobs(groups, scfg, mcfg)
    res = AR.run("B5", jobs, {"W": fl.W, "sizes": fl.sizes, "readout": fl.readout})
    types, reps = AR.aggregate_b5(fl, groups, res)
    types["mean_score"] = None   # the summary is the maximum over strengths (primary_score, best_score), not a mean
    AR.write_arm("B5", types, reps, {"model": mcfg.to_dict(), "screen_for_verdicts": scfg.to_dict(), "strengths": AR.B5_STRENGTHS,
                                     "seeds": AR.SEEDS}, {"results_log_sha256": AR.results_log_sha("B5")})
    print("B5", len(types), "types; drivers (max over strengths)", int((types["band"] == "driver").sum()))


def cmd_b4(a) -> None:
    fl = N.front_leg()
    all_groups = N.type_groups(fl.table, excitatory_only=False)
    mcfg = ModelConfig(t_end=2.0)
    scfg = ScreenConfig()
    jobs = AR.b4_jobs(fl, all_groups, mcfg, scfg)
    res = AR.run("B4", jobs, {"W": fl.W, "sizes": fl.sizes, "readout": fl.readout}, batched=True)
    types, reps = AR.aggregate_b4(fl, all_groups, res)
    AR.write_arm("B4", types, reps, {"model": mcfg.to_dict(), "background": "both DNg100 at 250", "strengths": AR.B4_STRENGTHS,
                                     "seeds": AR.SEEDS, "groups": "all members of every DN type (any transmitter)"},
                 {"results_log_sha256": AR.results_log_sha("B4")})
    print("B4", len(types), "types;", types["call_128"].value_counts().to_dict())


def cmd_b2(a) -> None:
    sel = json.loads((PREDICTIONS / "B1" / "selection.json").read_text())
    net, groups, info = AR.malecns_network()
    scfg = AR.b1_screen_cfg(int(sel["kept_lower_bound"]))
    mcfg = ModelConfig(t_end=1.0)
    jobs = AR.group_jobs("B2", groups, scfg, mcfg)
    res = AR.run("B2", jobs, {"W": net.W, "sizes": net.sizes, "readout": net.readout}, batched=True)
    types, reps = AR.aggregate_group_arm("B2", net.name, net, groups, res, scfg)
    fl = N.front_leg()
    manc = N.type_groups(fl.table)
    nts = info.pop("malecns_dn_transmitters_by_manc_type")
    dis = []
    for t in sorted(set(manc) | set(groups) | set(nts)):
        n_m, n_c = len(manc.get(t, [])), len(groups.get(t, []))
        other_nt = {k: v for k, v in nts.get(t, {}).items() if k != "acetylcholine"}
        kinds = []
        if n_m and not nts.get(t):
            kinds.append("no_malecns_member")
        if n_m != n_c:
            kinds.append("member_count")
        if n_m and other_nt:
            kinds.append("transmitter")
        if kinds:
            dis.append({"manc_type": t, "kinds": kinds, "n_manc_exc": n_m, "n_malecns_exc": n_c, "malecns_other_transmitters": other_nt})
    # mapping provenance: how each MaleCNS DN got its MANC type (body match first, string fallback), and conflicts
    wt = net.table
    dn = wt[(wt["superclass"] == "descending_neuron") & wt["manc_type_mapped"].notna()]
    import glob as _glob

    import pyarrow.feather as _feather
    from brainir import paths as _paths
    ann = _feather.read_table(_glob.glob(str(_paths.data_root() / "raw" / "external" / "malecns_v1.0_body_annotations" / "*.feather"))[0]) \
        .to_pandas().set_index("bodyId")
    a = ann.reindex(dn["bodyId"].astype(int))
    body_matched = a["mancBodyid"].notna().to_numpy()
    string_conflict = body_matched & a["mancType"].notna().to_numpy() & (a["mancType"].astype(str).to_numpy() != dn["manc_type_mapped"].astype(str).to_numpy())
    mapping = {"n_dn_mapped": int(len(dn)), "n_via_body_match": int(body_matched.sum()), "n_via_mancType_string": int((~body_matched).sum()),
               "n_body_match_disagreeing_with_mancType_string": int(string_conflict.sum()),
               "n_groups_not_in_A1": int(len(set(groups) - set(manc)))}
    AR.write_arm("B2", types, reps, {"model": mcfg.to_dict(), "screen": scfg.to_dict(), "seeds": AR.SEEDS, "network": net.meta, **info},
                 {"results_log_sha256": AR.results_log_sha("B2"), "type_disagreements_between_animals": dis, "type_mapping": mapping})
    print("B2", len(types), "types; usable", int((types["status"] == "ok").sum()), "; disagreements", len(dis))


def cmd_g1(a) -> None:
    fl = N.front_leg()
    cands = np.flatnonzero(N.exc_dn_mask(fl.table))
    pick = np.random.default_rng(20261124).choice(len(cands), 30, replace=False)
    neurons = sorted(int(cands[i]) for i in pick)
    groups = {f"n{c}": [c] for c in neurons}
    scfg = ScreenConfig()                       # B0's configuration (lower 5, cap 100)
    mcfg = ModelConfig(t_end=1.0)
    jobs = AR.group_jobs("G1", groups, scfg, mcfg)
    res = AR.run("G1", jobs, {"W": fl.W, "sizes": fl.sizes, "readout": fl.readout})
    b0 = {(r["candidate"], r["seed"]): r for r in json.loads(B0_PATH.read_text())["replicates"]}
    rows = []
    for c in neurons:
        for s in AR.SEEDS:
            r = res[f"G1|n{c}|s{s}"]
            ref = b0[(c, s)]
            rows.append({"candidate": c, "type": fl.table.loc[c, "type"], "seed": s, "usable": r["usable"], "b0_usable": ref["usable"],
                         "current": r["current"], "b0_current": ref["current"], "score": r["score"], "b0_score": ref["score"],
                         "n_runs": r["n_tuning_runs"], "b0_n_runs": ref["n_tuning_runs"]})
    df = pd.DataFrame(rows)
    both = df.dropna(subset=["score", "b0_score"])
    diff = (both["score"] - both["b0_score"]).abs()
    summ = {"n_jobs": len(df), "neurons": neurons, "usable_flag_equal": int((df["usable"] == df["b0_usable"]).sum()),
            "current_equal": int((df["current"] == df["b0_current"]).sum()), "n_runs_equal": int((df["n_runs"] == df["b0_n_runs"]).sum()),
            "score_exact": int((diff == 0).sum()), "score_compared": int(len(both)), "max_abs_score_diff": float(diff.max()) if len(diff) else None,
            "n_abs_diff_gt_0_01": int((diff > 0.01).sum()), "n_abs_diff_gt_0_05": int((diff > 0.05).sum())}
    GATES.mkdir(parents=True, exist_ok=True)
    df.to_csv(GATES / "G1_rows.csv", index=False, lineterminator="\n")
    write_json(summ, GATES / "G1_summary.json")
    print(json.dumps(summ))


def cmd_g1_cause(a) -> None:
    """PREREG 9 G1: re-run the jobs whose result differs from B0 WITHOUT the numerics environment, 8 times each (spread over
    containers and host types), and test whether hosts of one kind reproduce B0 exactly (B0 ran unpinned on mixed hosts)."""
    from brainir_ledger.backend import LedgerModalBackend, run_campaign
    from brainir_ledger.jobs import run_job

    rows = pd.read_csv(GATES / "G1_rows.csv")
    diff = rows[(rows["usable"] != rows["b0_usable"]) | (rows["current"] != rows["b0_current"]) |
                ((rows["score"] - rows["b0_score"]).abs().fillna(0) > 0)]
    fl = N.front_leg()
    scfg, mcfg = ScreenConfig(), ModelConfig(t_end=1.0)
    jobs = []
    for _, r in diff.iterrows():
        for k in range(8):
            j = AR.group_jobs("G1C", {f"n{int(r.candidate)}": [int(r.candidate)]}, scfg, mcfg, seeds=[int(r.seed)])[0]
            j["key"] = f"G1C|n{int(r.candidate)}|s{int(r.seed)}|r{k}"
            jobs.append(j)
    be = LedgerModalBackend(numerics=False, cpu=1.0, memory_mb=3072, max_containers=100, timeout_s=3600)
    res = run_campaign(AR.data_dir() / "arms" / "G1_cause_unpinned", jobs, be, run_job,
                       shared={"W": fl.W, "sizes": fl.sizes, "readout": fl.readout})
    out = []
    for _, r in diff.iterrows():
        for k in range(8):
            x = res.get(f"G1C|n{int(r.candidate)}|s{int(r.seed)}|r{k}")
            if x is None or "error" in x:
                continue
            out.append({"candidate": int(r.candidate), "seed": int(r.seed), "rep": k, "avx512": bool(x["host"]["cpu"].get("avx512f")),
                        "score": x["score"], "current": x["current"], "usable": x["usable"], "b0_score": r.b0_score,
                        "pinned_score": r.score, "equals_b0": (x["score"] == r.b0_score and x["current"] == r.b0_current
                                                              and x["usable"] == r.b0_usable),
                        "equals_pinned": x["score"] == r.score})
    df = pd.DataFrame(out)
    summ = {"n_differing_jobs": int(len(diff)), "n_reruns": int(len(df))}
    if len(df):
        g = df.groupby("avx512")
        summ["by_host"] = {("avx512" if k else "no_avx512"): {"n": int(len(v)), "equals_b0": int(v["equals_b0"].sum()),
                                                              "equals_pinned": int(v["equals_pinned"].sum())} for k, v in g}
        per_job = df.groupby(["candidate", "seed"]).agg(any_equals_b0=("equals_b0", "any")).reset_index()
        summ["jobs_reproduced_by_some_host"] = int(per_job["any_equals_b0"].sum())
    df.to_csv(GATES / "G1_cause_rows.csv", index=False, lineterminator="\n")
    write_json(summ, GATES / "G1_cause_summary.json")
    print(json.dumps(summ))


def _jobs_for(campaign: str) -> tuple[list[dict], dict]:
    """Rebuild the job list and shared payload of a finished campaign (for G4)."""
    mcfg1, mcfg2 = ModelConfig(t_end=1.0), ModelConfig(t_end=2.0)
    fl = N.front_leg()
    groups = N.type_groups(fl.table)
    shared = {"W": fl.W, "sizes": fl.sizes, "readout": fl.readout}
    if campaign.startswith("B1-lo"):
        return AR.group_jobs(campaign, groups, AR.b1_screen_cfg(int(campaign[5:])), mcfg1), shared
    sel = json.loads((PREDICTIONS / "B1" / "selection.json").read_text())
    scfg = AR.b1_screen_cfg(int(sel["kept_lower_bound"]))
    if campaign.startswith("B1-ctl-"):
        Wc, _ = CT.build(fl, campaign)
        return AR.group_jobs(campaign, groups, scfg, mcfg1), {**shared, "W": Wc}
    if campaign == "B5":
        return AR.b5_jobs(groups, scfg, mcfg1), shared
    if campaign == "B4":
        return AR.b4_jobs(fl, N.type_groups(fl.table, excitatory_only=False), mcfg2, ScreenConfig()), shared
    if campaign == "B2":
        net, g2, _ = AR.malecns_network()
        return AR.group_jobs("B2", g2, scfg, mcfg1), {"W": net.W, "sizes": net.sizes, "readout": net.readout}
    raise ValueError(campaign)


def cmd_g4(a) -> None:
    """Re-run 100 random jobs of a finished campaign in a separate campaign (other containers); digests must be identical."""
    jobs, shared = _jobs_for(a.only)
    orig = AR.load_results(a.only)
    rng = np.random.default_rng(20261127)
    pick = sorted(rng.choice(len(jobs), min(100, len(jobs)), replace=False))
    sub = [dict(jobs[i]) for i in pick]
    res = AR.run(f"G4-{a.only}", sub, shared, campaign=f"G4_{a.only}")
    same = sum(res[j["key"]]["digest"] == orig[j["key"]]["digest"] for j in sub)
    out = {"campaign": a.only, "n": len(sub), "identical_digests": int(same), "pass": same == len(sub),
           "differing": [j["key"] for j in sub if res[j["key"]]["digest"] != orig[j["key"]]["digest"]]}
    GATES.mkdir(parents=True, exist_ok=True)
    write_json(out, GATES / f"G4_{a.only}.json")
    print(json.dumps(out))


def cmd_g2(a) -> None:
    """B1 (and B1-alt, B0 per-type max) against A1: Spearman, top-10 overlap, the ten largest rank disagreements."""
    a1 = pd.read_csv(PREDICTIONS / "A1" / "types.csv").set_index("manc_type")
    out = {}
    for arm in ("B1", "B1-alt", "A1-lo10", "B0", "A0"):
        p = PREDICTIONS / arm / "types.csv"
        if not p.exists():
            continue
        b = pd.read_csv(p).set_index("manc_type")
        common = a1.index.intersection(b.index)
        x, y = a1.loc[common, "primary_score"], b.loc[common, "primary_score"]
        rx, ry = x.rank(ascending=False), y.rank(ascending=False)
        top_a = set(x.sort_values(ascending=False).index[:10])
        top_b = set(y.sort_values(ascending=False).index[:10])
        dis = (rx - ry).abs().sort_values(ascending=False).index[:10]
        out[arm] = {"n_common": int(len(common)), "spearman": spearman(x, y), "top10_overlap": len(top_a & top_b),
                    "band_agreement": float((a1.loc[common, "band"] == b.loc[common, "band"]).mean()),
                    "largest_rank_disagreements": [{"manc_type": t, "a1_score": float(x[t]), "arm_score": float(y[t]), "a1_rank": float(rx[t]),
                                                    "arm_rank": float(ry[t]), "a1_status": a1.loc[t, "status"], "arm_status": b.loc[t, "status"]}
                                                   for t in dis]}
    GATES.mkdir(parents=True, exist_ok=True)
    write_json(out, GATES / "G2_agreement.json")
    for k, v in out.items():
        print(k, "spearman", round(v["spearman"], 3), "top10", v["top10_overlap"], "band agreement", round(v["band_agreement"], 3))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["authors", "b0", "baselines", "b1", "select-b1", "controls", "controls-pilot", "b5", "b4", "b2", "g1",
                                    "g1-cause", "g2", "g4"])
    ap.add_argument("--lower", type=int, default=10)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    {"authors": cmd_authors, "b0": cmd_b0, "baselines": cmd_baselines, "b1": cmd_b1, "select-b1": cmd_select_b1, "controls": cmd_controls,
     "b5": cmd_b5, "b4": cmd_b4, "b2": cmd_b2, "g1": cmd_g1, "g1-cause": cmd_g1_cause, "g2": cmd_g2, "g4": cmd_g4, "controls-pilot": cmd_controls_pilot}[a.cmd](a)


if __name__ == "__main__":
    main()
