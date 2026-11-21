"""Tuner v2 arms B1r / B2r (PREREG v2 P1): tables and gates from the GitHub campaigns. PREDICTION SIDE (no fly data).

    uv run --project ledger --no-sync python ledger/scripts/b12r_gates.py regress    # K = 0 vs B1's locked digests -> gates_v2/REGRESSION_v2.json
    uv run --project ledger --no-sync python ledger/scripts/b12r_gates.py tables     # -> research/ledger/predictions_v2/B1r, B2r
    uv run --project ledger --no-sync python ledger/scripts/b12r_gates.py controls   # positive control + DNb08 -> gates_v2/B12R_CONTROLS.json

The tables use run 1's frozen table builder (`arms.aggregate_group_arm`, `arms.write_arm`) unchanged, writing to
`predictions_v2/` instead of `predictions/`.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from brainir.sim.model import ModelConfig  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import arms as AR  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402
from brainir_ledger import tables as TB  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

G = RESEARCH / "gates_v2"
PLATFORM = "GitHub Actions hosted runners (ubuntu-24.04, Linux x64), run 1's Python/library pins and numerics environment"


def _log(name: str) -> tuple[dict, Path]:
    p = data_dir() / "arms" / f"GHA_{name}" / "results.pkl"
    return {r["key"]: r for r in read_log(p)}, p


def regress() -> None:
    """P1 tuner regression: K = 0 on 30 random types (seed 20261204) x 16 seeds reproduces B1's locked digests."""
    res, p = _log("regress")
    reps = pd.read_parquet(RESEARCH / "predictions" / "B1" / "replicates.parquet")
    locked = {f"B1-lo10|{t}|s{int(s)}": d for t, s, d in zip(reps["manc_type"], reps["seed"], reps["digest"])}
    rows = {"n_results": len(res), "errors": sorted(k for k, r in res.items() if "error" in r), "identical": 0, "different": [],
            "not_in_B1": []}
    for k, r in sorted(res.items()):
        if "error" in r:
            continue
        if k not in locked:
            rows["not_in_B1"].append(k)
        elif r["digest"] == locked[k]:
            rows["identical"] += 1
        else:
            rows["different"].append(k)
    rows["n_types"] = len({k.split("|")[1] for k in res})
    rows["pass"] = rows["n_results"] == 480 and rows["identical"] == 480
    rows.update({"rule": "PREREG v2 P1: K = 0 reproduces B1's digests on 30 random types (seed 20261204) x 16 seeds",
                 "source_sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    G.mkdir(parents=True, exist_ok=True)
    (G / "REGRESSION_v2.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in rows.items()}))


def _arms():
    fl = N.front_leg()
    g1 = N.type_groups(fl.table)
    net2, g2, _info = AR.malecns_network()
    return (("B1r", fl, g1, "b1r"), ("B2r", net2, g2, "b2r"))


def _k_reasons(types: pd.DataFrame, reps: pd.DataFrame, scfg) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """P1: "a run inside the activity bounds with fewer [than K active front-leg MNs] counts as too weak". The frozen
    `arms._final` knows only v1's reason (weak = fewer than n_active_lower active), so for a final run inside the bounds that the
    tuner rejected only for K it writes "strong" (prediction review, major). Recompute that reason code and each type's `status`
    (`tables.status_from`); every other column stays byte-identical (asserted)."""
    reps = reps.copy()
    un = ~reps["usable"].astype(bool)
    inb = (reps["n_active_all"] >= scfg.n_active_lower) & (reps["n_active_all"] <= scfg.n_active_upper) & (reps["n_high_fr"] <= scfg.n_high_fr_upper)
    new = np.where(reps["n_active_all"] < scfg.n_active_lower, "weak", np.where(inb, "weak", "strong"))
    old = reps["final_verdict"].copy()
    reps.loc[un, "final_verdict"] = new[un.to_numpy()]
    n_changed = int((old[un] != reps.loc[un, "final_verdict"]).sum())
    st = {}
    for typ, g in reps.groupby("manc_type"):
        u = g["usable"].astype(bool)
        st[typ] = TB.status_from(int(u.sum()), int((~u & (g["final_verdict"] == "weak")).sum()), int((~u & (g["final_verdict"] != "weak")).sum()))
    before = types.drop(columns=["status"]).copy()
    types = types.copy()
    types["status"] = types["manc_type"].map(st)
    assert types.drop(columns=["status"]).equals(before)
    return types, reps, n_changed


def _campaign(name: str) -> dict:
    man = json.loads((data_dir() / "gha" / name / "manifest.json").read_text())
    meta = [json.loads(x) for x in (data_dir() / "arms" / f"GHA_{name}" / "gha_meta.jsonl").read_text().splitlines() if x.strip()]
    tag = f"gha-run-{name}"
    import subprocess
    commit = subprocess.run(["git", "rev-parse", f"{tag}^{{commit}}"], capture_output=True, text=True, cwd=RESEARCH.parents[1]).stdout.strip()
    return {"campaign": name, "runner_commit": commit, "tag": tag, "specs_packed_at": man.get("git_head"), "manifest_keys_sha256": man.get("keys_sha256"),
            "numerics_digests": sorted({m["probe"]["numerics_digest"][:12] for m in meta}),
            "cpu_models": sorted({m["probe"]["host"]["cpu"]["cpu_model"] for m in meta}), "n_chunks": len(meta)}


def tables() -> None:
    k = json.loads((G / "CALIBK.json").read_text())["k_chosen"]
    if k is None:
        raise SystemExit("no K was chosen (P1 fallback needed)")
    scfg, mcfg = AR.b1_screen_cfg(10), ModelConfig(t_end=1.0)
    AR.PREDICTIONS = RESEARCH / "predictions_v2"  # the frozen writer, pointed at the v2 folder
    for arm, net, groups, camp in _arms():
        res, p = _log(camp)
        types, reps = AR.aggregate_group_arm(arm, net.name, net, groups, res, scfg)
        types, reps, n_changed = _k_reasons(types, reps, scfg)
        runs = {"b1r": 44831777087, "b2r": 44831808385}
        AR.write_arm(arm, types, reps, {"model": mcfg.to_dict(), "screen": scfg.to_dict(), "seeds": AR.SEEDS, "k_min": int(k),
                                        "tuner": "tuner v2 (PREREG v2 P1): B1's procedure plus >= K active front-leg MNs in the accepted run",
                                        "groups": "B1's groups" if arm == "B1r" else "B2's groups and mapping"},
                     {"results_log_sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "platform": PLATFORM, "network_meta": net.meta,
                      "calibration": "gates_v2/CALIBK.json (DNg100 only)", "github_run_id": runs[camp], **_campaign(camp),
                      "k_reason_codes_recomputed": n_changed,
                      "note": "final_verdict / status recomputed for K-rejected runs inside the bounds (P1: too weak); scores and bands untouched"})
        print(arm, len(types), "types; usable", int((types["status"] == "ok").sum()), "; drivers", int((types["band"] == "driver").sum()),
              "; reason codes recomputed", n_changed, "; status", types["status"].value_counts().to_dict())


def controls() -> None:
    """P1: positive control DNg100 >= 0.5 in >= 12 of 16 seeds in B1r and B2r (tautological by construction, reported) and
    DNb08 reported as the non-tautological check (not a gate, never tuned on)."""
    out = {}
    for arm in ("B1r", "B2r"):
        t = pd.read_csv(RESEARCH / "predictions_v2" / arm / "types.csv").set_index("manc_type")
        reps = pd.read_parquet(RESEARCH / "predictions_v2" / arm / "replicates.parquet")
        row = {}
        for typ in ("DNg100", "DNb08"):
            r = reps[reps["manc_type"] == typ]
            row[typ] = {"n_seeds": int(len(r)), "n_seeds_score_ge_0_5": int((r["usable"] & (r["score"] >= 0.5)).sum()),
                        "band": None if typ not in t.index else t.loc[typ, "band"],
                        "primary_score": None if typ not in t.index else float(t.loc[typ, "primary_score"])}
        row["positive_control_pass"] = row["DNg100"]["n_seeds_score_ge_0_5"] >= 12
        out[arm] = row
    out["pass"] = all(out[a]["positive_control_pass"] for a in ("B1r", "B2r"))
    out["note"] = "DNg100 is the calibration neuron (tautological); DNb08 is reported, not a gate, and was never tuned on."
    (G / "B12R_CONTROLS.json").write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    {"regress": regress, "tables": tables, "controls": controls}[sys.argv[1]]()
