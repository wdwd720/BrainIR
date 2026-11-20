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
        AR.write_arm(arm, types, reps, {"source": "authors' type-level screen, run 32818378", "usable": f"{lo} <= nActive <= 1500",
                                        "readout": "authors' 138 module-labelled front-leg MNs", "files": AU.FILES,
                                        "zenodo_configs": AU.ZENODO_CONFIGS},
                     {"type_set_vs_brainir_groups_symmetric_difference": missing})
        print(arm, len(types), "types; never usable", int((types["status"] != "ok").sum()), "; drivers", int((types["band"] == "driver").sum()))
    neur = AU.a0_neurons(fl.table, files)
    t0 = AU.per_type_from_neurons(neur, "A0", "authors_manc_frontleg_2025-08-13")
    AR.write_arm("A0", t0, neur, {"source": "authors' single-neuron screen, 8 runs x 16 = 128 replicates", "usable": "5 <= nActive <= 1500",
                                  "files": AU.FILES}, {})
    print("A0", len(t0), "types from", len(neur), "neurons")


def cmd_b0(a) -> None:
    raw = B0_PATH.read_bytes()
    d = json.loads(raw)
    fl = N.front_leg()
    rows = []
    for c in d["candidates"]:
        rows.append({"row": int(c["candidate"]), "bodyId": int(c["source_id"]), "manc_type": c["cell_type"], "n_usable": c["n_usable"],
                     "mean_score": c["mean_score"]})
    neur = pd.DataFrame(rows)
    assert (fl.table.loc[neur["row"], "bodyId"].to_numpy() == neur["bodyId"].to_numpy()).all()
    t0 = AU.per_type_from_neurons(neur, "B0", "manc_v1.2.1_frontleg")
    reps = pd.DataFrame(d["replicates"])
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
    base = pd.DataFrame({"arm": "S", "network": fl.name, "manc_type": df["manc_type"]})
    out = base.merge(df, on="manc_type")
    out["primary_score"] = out["S1_direct_mn"]
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
        for f in ("types.csv",):
            df = pd.read_csv(PREDICTIONS / dst / f)
            df["arm"] = dst
            df.to_csv(PREDICTIONS / dst / f, index=False, lineterminator="\n", float_format="%.10g")
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
        res = AR.run(name, jobs, {"W": Wc, "sizes": fl.sizes, "readout": fl.readout})
        types, reps = AR.aggregate_group_arm(name, f"{fl.name}+{name}", fl, groups, res, scfg)
        AR.write_arm(name, types, reps, {"model": mcfg.to_dict(), "screen": scfg.to_dict(), "seeds": AR.SEEDS, "control": name,
                                         "construction": stats},
                     {"results_log_sha256": AR.results_log_sha(name), "control_matrix_sha256":
                      hashlib.sha256(Wc.tocsr().data.tobytes() + Wc.tocsr().indices.tobytes() + Wc.tocsr().indptr.tobytes()).hexdigest()})
        print(name, "usable types", int((types["status"] == "ok").sum()), "; drivers", int((types["band"] == "driver").sum()))


def cmd_b5(a) -> None:
    sel = json.loads((PREDICTIONS / "B1" / "selection.json").read_text())
    fl = N.front_leg()
    groups = N.type_groups(fl.table)
    scfg = AR.b1_screen_cfg(int(sel["kept_lower_bound"]))
    mcfg = ModelConfig(t_end=1.0)
    jobs = AR.b5_jobs(groups, scfg, mcfg)
    res = AR.run("B5", jobs, {"W": fl.W, "sizes": fl.sizes, "readout": fl.readout})
    types, reps = AR.aggregate_b5(fl, groups, res)
    AR.write_arm("B5", types, reps, {"model": mcfg.to_dict(), "screen_for_verdicts": scfg.to_dict(), "strengths": AR.B5_STRENGTHS,
                                     "seeds": AR.SEEDS}, {"results_log_sha256": AR.results_log_sha("B5")})
    print("B5", len(types), "types; drivers (max over strengths)", int((types["band"] == "driver").sum()))


def cmd_b4(a) -> None:
    fl = N.front_leg()
    all_groups = N.type_groups(fl.table, excitatory_only=False)
    mcfg = ModelConfig(t_end=2.0)
    scfg = ScreenConfig()
    jobs = AR.b4_jobs(fl, all_groups, mcfg, scfg)
    res = AR.run("B4", jobs, {"W": fl.W, "sizes": fl.sizes, "readout": fl.readout})
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
    res = AR.run("B2", jobs, {"W": net.W, "sizes": net.sizes, "readout": net.readout})
    types, reps = AR.aggregate_group_arm("B2", net.name, net, groups, res, scfg)
    fl = N.front_leg()
    manc = N.type_groups(fl.table)
    dis = [{"manc_type": t, "n_manc_exc": len(manc.get(t, [])), "n_malecns_exc": len(groups.get(t, []))} for t in sorted(set(manc) | set(groups))
           if len(manc.get(t, [])) != len(groups.get(t, []))]
    AR.write_arm("B2", types, reps, {"model": mcfg.to_dict(), "screen": scfg.to_dict(), "seeds": AR.SEEDS, "network": net.meta, **info},
                 {"results_log_sha256": AR.results_log_sha("B2"), "member_count_disagreements": dis})
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["authors", "b0", "baselines", "b1", "select-b1", "controls", "b5", "b4", "b2", "g1"])
    ap.add_argument("--lower", type=int, default=10)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    {"authors": cmd_authors, "b0": cmd_b0, "baselines": cmd_baselines, "b1": cmd_b1, "select-b1": cmd_select_b1, "controls": cmd_controls,
     "b5": cmd_b5, "b4": cmd_b4, "b2": cmd_b2, "g1": cmd_g1}[a.cmd](a)


if __name__ == "__main__":
    main()
