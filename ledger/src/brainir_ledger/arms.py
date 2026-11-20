"""Stage 1 arms: job builders and aggregation into the PREREG section 11 tables (prediction side; never reads labels)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from brainir.compute import Shared
from brainir.sim import ModelConfig
from brainir.sim.screen import ScreenConfig

from . import PREDICTIONS, REPO, data_dir
from . import networks as N
from .backend import LedgerModalBackend, read_log, run_campaign
from .env import fingerprint
from .jobs import run_job
from .tables import band, finish_types, type_row, write_csv, write_json, write_parquet

SEEDS = list(range(16))
B1_CAP = 200
B4_STRENGTHS = (32.0, 128.0, 512.0)
B4_BACKGROUND = 250.0
B4_MIN_BASE_RHYTHMIC = 8  # a call needs at least 8 of 16 seeds with a rhythmic background
B5_STRENGTHS = (32.0, 64.0, 128.0, 256.0, 512.0)


def git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()


def b1_screen_cfg(lower: int) -> ScreenConfig:
    return ScreenConfig(n_active_lower=int(lower), n_high_fr_upper=B1_CAP)


def group_jobs(arm: str, groups: dict[str, list[int]], screen_cfg: ScreenConfig, model_cfg: ModelConfig, seeds=SEEDS,
               extras: dict | None = None) -> list[dict]:
    return [{"key": f"{arm}|{t}|s{s}", "kind": "group", "W": Shared("W"), "sizes": Shared("sizes"), "readout": Shared("readout"),
             "members": list(m), "seed": int(s), "model": model_cfg.to_dict(), "screen": screen_cfg.to_dict(),
             "extras": extras or {"readout_traces": True}} for t, m in sorted(groups.items()) for s in seeds]


def run(arm: str, jobs: list[dict], shared: dict, *, memory_mb: int = 3072, max_containers: int = 100, timeout_s: int = 3600,
        campaign: str | None = None) -> dict[str, dict]:
    be = LedgerModalBackend(cpu=1.0, memory_mb=memory_mb, max_containers=max_containers, timeout_s=timeout_s)
    run_dir = data_dir() / "arms" / (campaign or arm)
    for attempt in range(3):  # resume after infrastructure errors / usage-limit stalls
        res = run_campaign(run_dir, jobs, be, run_job, shared=shared)
        missing = [j["key"] for j in jobs if j["key"] not in res or "error" in res[j["key"]]]
        if not missing:
            break
        print(f"  {arm}: {len(missing)} jobs missing or failed after attempt {attempt + 1}; resuming", flush=True)
    return res


def _final(r: dict, screen_cfg: ScreenConfig) -> str:
    return "weak" if r.get("n_active_all", 0) < screen_cfg.n_active_lower else "strong"


def aggregate_group_arm(arm: str, network: str, net: N.LedgerNetwork, groups: dict[str, list[int]], res: dict[str, dict],
                        screen_cfg: ScreenConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, reps = [], []
    ids = net.table["bodyId"].to_numpy()
    for t, members in sorted(groups.items()):
        rr = []
        for s in SEEDS:
            r = res.get(f"{arm}|{t}|s{s}")
            if r is None or "error" in r:
                raise RuntimeError(f"{arm}: missing result for {t} seed {s}")
            rr.append({"usable": r["usable"], "score": r["score"], "frequency_hz": r["frequency_hz"], "current": r["current"],
                       "n_active_readout": r["n_active_readout"], "final": None if r["usable"] else _final(r, screen_cfg)})
            ex = r.get("extras") or {}
            reps.append({"manc_type": t, "seed": s, "usable": r["usable"], "score": r["score"], "frequency_hz": r["frequency_hz"],
                         "current": r["current"], "n_tuning_runs": r["n_tuning_runs"], "n_active_all": r["n_active_all"],
                         "n_high_fr": r["n_high_fr"], "n_active_readout": r["n_active_readout"],
                         "n_active_notebook": ex.get("n_active_notebook"), "final_verdict": None if r["usable"] else _final(r, screen_cfg),
                         "digest": r["digest"], "host_avx512": bool(r["host"]["cpu"].get("avx512f")), "job_wall_s": r["job_wall_s"]})
        rows.append(type_row(arm, network, t, [int(ids[m]) for m in members], rr))
    return finish_types(rows), pd.DataFrame(reps)


def write_arm(arm: str, types: pd.DataFrame, reps: pd.DataFrame | None, config: dict, provenance: dict,
              legs: pd.DataFrame | None = None) -> dict:
    d = PREDICTIONS / arm
    d.mkdir(parents=True, exist_ok=True)
    h = {"types.csv": write_csv(types, d / "types.csv")}
    if reps is not None:
        h["replicates.parquet"] = write_parquet(reps, d / "replicates.parquet")
    if legs is not None:
        h["legs.csv"] = write_csv(legs, d / "legs.csv")
    h["config.json"] = write_json(config, d / "config.json")
    provenance = {**provenance, "files_sha256": dict(h), "code_commit": git_commit(), "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                                                                  time.gmtime())}
    h["provenance.json"] = write_json(provenance, d / "provenance.json")
    return h


def results_log_sha(campaign: str) -> str | None:
    p = data_dir() / "arms" / campaign / "results.pkl"
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


# ---------------------------------------------------------------- B5: fixed-strength grid
def b5_jobs(groups, screen_cfg, model_cfg) -> list[dict]:
    return [{"key": f"B5|{t}|I{c:g}|s{s}", "kind": "fixed", "W": Shared("W"), "sizes": Shared("sizes"), "readout": Shared("readout"),
             "stim_indices": list(m), "currents": [float(c)] * len(m), "seed": int(s), "model": model_cfg.to_dict(),
             "screen": screen_cfg.to_dict(), "extras": {}} for t, m in sorted(groups.items()) for c in B5_STRENGTHS for s in SEEDS]


def aggregate_b5(net, groups, res) -> tuple[pd.DataFrame, pd.DataFrame]:
    ids = net.table["bodyId"].to_numpy()
    rows, reps = [], []
    for t, members in sorted(groups.items()):
        row = {"arm": "B5", "network": net.name, "manc_type": t, "n_members": len(members),
               "member_ids": ";".join(str(int(ids[m])) for m in members), "n_replicates": len(SEEDS) * len(B5_STRENGTHS)}
        best = 0.0
        for c in B5_STRENGTHS:
            rs = [res[f"B5|{t}|I{c:g}|s{s}"] for s in SEEDS]
            if any("error" in r for r in rs):
                raise RuntimeError(f"B5 missing {t} {c}")
            sc = np.array([r["score"] for r in rs])
            row[f"score_I{c:g}"] = float(sc.mean())
            row[f"frac_ge_0_5_I{c:g}"] = float((sc >= 0.5).mean())
            row[f"frac_in_bounds_I{c:g}"] = float(np.mean([r["verdict"] == "ok" for r in rs]))
            best = max(best, float(sc.mean()))
            for s, r in zip(SEEDS, rs):
                reps.append({"manc_type": t, "current": c, "seed": s, "score": r["score"], "frequency_hz": r["frequency_hz"],
                             "verdict": r["verdict"], "n_active_all": r["n_active_all"], "n_high_fr": r["n_high_fr"],
                             "n_active_readout": r["n_active_readout"], "digest": r["digest"]})
        row.update({"n_usable": None, "mean_score": best, "median_score": None, "frac_ge_0_5": None, "best_score": best, "median_freq_hz": None,
                    "median_current": None, "median_n_active_readout": None, "status": "ok", "band": band(best), "primary_score": best})
        rows.append(row)
    return finish_types(rows), pd.DataFrame(reps)


# ---------------------------------------------------------------- B4: walking background
def b4_jobs(net, all_groups, model_cfg, screen_cfg) -> list[dict]:
    dng = [int(i) for i in net.table.index[net.table["type"] == "DNg100"]]
    jobs = [{"key": f"B4|__background__|I0|s{s}", "kind": "fixed", "W": Shared("W"), "sizes": Shared("sizes"), "readout": Shared("readout"),
             "stim_indices": dng, "currents": [B4_BACKGROUND] * len(dng), "seed": s, "model": model_cfg.to_dict(),
             "screen": screen_cfg.to_dict(), "extras": {}} for s in SEEDS]
    for t, members in sorted(all_groups.items()):
        for c in B4_STRENGTHS:
            cur = {i: B4_BACKGROUND for i in dng}
            for m in members:
                cur[int(m)] = cur.get(int(m), 0.0) + c
            idx = sorted(cur)
            for s in SEEDS:
                jobs.append({"key": f"B4|{t}|I{c:g}|s{s}", "kind": "fixed", "W": Shared("W"), "sizes": Shared("sizes"),
                             "readout": Shared("readout"), "stim_indices": idx, "currents": [cur[i] for i in idx], "seed": s,
                             "model": model_cfg.to_dict(), "screen": screen_cfg.to_dict(), "extras": {}})
    return jobs


def b4_call(bg: list[dict], tr: list[dict]) -> tuple[str, dict]:
    base_ok = [i for i, b in enumerate(bg) if b["score"] >= 0.5]
    halts = [tr[i]["score"] < 0.5 for i in base_ok]
    both = [i for i in base_ok if tr[i]["score"] >= 0.5 and bg[i]["frequency_hz"] and tr[i]["frequency_hz"]]
    rel = [(tr[i]["frequency_hz"] - bg[i]["frequency_hz"]) / bg[i]["frequency_hz"] for i in both]
    info = {"n_base_rhythmic": len(base_ok), "frac_halt": float(np.mean(halts)) if halts else None, "n_both": len(both),
            "median_rel_freq_change": float(np.median(rel)) if rel else None}
    if len(base_ok) < B4_MIN_BASE_RHYTHMIC:
        return "background_not_rhythmic", info
    if np.mean(halts) >= 0.75:
        return "halts", info
    if len(both) < 4:
        return "no_effect_low_n", info
    if np.median(rel) > 0.15:
        return "speeds_up", info
    if np.median(rel) < -0.15:
        return "slows_down", info
    return "no_effect", info


def aggregate_b4(net, all_groups, res) -> tuple[pd.DataFrame, pd.DataFrame]:
    ids = net.table["bodyId"].to_numpy()
    bg = [res[f"B4|__background__|I0|s{s}"] for s in SEEDS]
    rows, reps = [], []
    for s, b in zip(SEEDS, bg):
        reps.append({"manc_type": "__background__", "current": 0.0, "seed": s, "score": b["score"], "frequency_hz": b["frequency_hz"],
                     "verdict": b["verdict"], "n_active_readout": b["n_active_readout"], "digest": b["digest"]})
    for t, members in sorted(all_groups.items()):
        row = {"arm": "B4", "network": net.name, "manc_type": t, "n_members": len(members),
               "member_ids": ";".join(str(int(ids[m])) for m in members), "n_replicates": len(SEEDS)}
        for c in B4_STRENGTHS:
            tr = [res[f"B4|{t}|I{c:g}|s{s}"] for s in SEEDS]
            call, info = b4_call(bg, tr)
            row[f"call_{c:g}"] = call
            for k, v in info.items():
                row[f"{k}_{c:g}"] = v
            for s, r in zip(SEEDS, tr):
                reps.append({"manc_type": t, "current": c, "seed": s, "score": r["score"], "frequency_hz": r["frequency_hz"],
                             "verdict": r["verdict"], "n_active_readout": r["n_active_readout"], "digest": r["digest"]})
        row.update({"n_usable": None, "mean_score": None, "median_score": None, "frac_ge_0_5": None, "best_score": None,
                    "median_freq_hz": None, "median_current": None, "median_n_active_readout": None, "status": "ok",
                    "band": None, "primary_score": None})
        rows.append(row)
    return finish_types(rows), pd.DataFrame(reps)


# ---------------------------------------------------------------- B2: MaleCNS
def malecns_network() -> tuple[N.LedgerNetwork, dict[str, list[int]], dict]:
    """The authors' MaleCNS front-leg network (signed matrix and table as published) and MANC-type groups."""
    import glob
    import sys

    import pyarrow.feather as feather
    from brainir import paths

    sys.path.insert(0, str(REPO / "benchmarks" / "dng100_walking_cpg"))
    from reproduce_manc_connectivity import authors_mcns, fetch_external  # noqa: PLC0415

    wt, pairs = authors_mcns(fetch_external())
    wt = wt.reset_index(drop=True)
    ids = wt["bodyId"].to_numpy().astype(np.int64)
    pos = {int(b): i for i, b in enumerate(ids)}
    W = sp.csr_matrix((pairs["w_signed"].to_numpy().astype(np.float64),
                       (np.array([pos[int(x)] for x in pairs["post_id"]]), np.array([pos[int(x)] for x in pairs["pre_id"]]))),
                      shape=(len(ids), len(ids)))
    W.eliminate_zeros()
    readout = ((wt["superclass"] == "vnc_motor") & (wt["subclass"] == "fl")).to_numpy()
    ann = feather.read_table(glob.glob(str(paths.data_root() / "raw" / "external" / "malecns_v1.0_body_annotations" / "*.feather"))[0]) \
        .to_pandas().set_index("bodyId")
    # MANC type through the curated body match (mancBodyid -> the body's type in the MANC front-leg / full-cord tables)
    ft = N.front_leg().table
    fc_types = dict(zip(N.full_cord().table["bodyId"].astype(int), N.full_cord().table["type"]))
    body2type = {**fc_types, **dict(zip(ft["bodyId"].astype(int), ft["type"]))}
    mt = []
    for b in ids:
        r = ann.loc[int(b)] if int(b) in ann.index else None
        t = None
        if r is not None and pd.notna(r.get("mancBodyid")) and int(r["mancBodyid"]) in body2type:
            t = body2type[int(r["mancBodyid"])]
        elif r is not None and pd.notna(r.get("mancType")):
            t = str(r["mancType"])
        mt.append(t)
    wt["manc_type_mapped"] = mt
    exc = (wt["superclass"] == "descending_neuron") & (wt["consensusNt"] == "acetylcholine") & wt["manc_type_mapped"].notna()
    groups: dict[str, list[int]] = {}
    for i in np.flatnonzero(exc.to_numpy()):
        groups.setdefault(str(wt.loc[i, "manc_type_mapped"]), []).append(int(i))
    net = N.LedgerNetwork("malecns_v1.0_frontleg_authors", W.tocsr(), wt["size"].astype(float).to_numpy(), wt, readout,
                          {"network": "authors' MaleCNS front-leg network (W_20260210_vncRoisOnly)", "n": int(len(ids)),
                           "n_readout": int(readout.sum())})
    # every mapped MaleCNS DN with its transmitter, for the per-type disagreement record (PREREG 3.8)
    dn = (wt["superclass"] == "descending_neuron") & wt["manc_type_mapped"].notna()
    nt_by_type: dict[str, dict[str, int]] = {}
    for i in np.flatnonzero(dn.to_numpy()):
        d = nt_by_type.setdefault(str(wt.loc[i, "manc_type_mapped"]), {})
        nt = str(wt.loc[i, "consensusNt"])
        d[nt] = d.get(nt, 0) + 1
    info = {"n_malecns_exc_dn_mapped": int(exc.sum()), "n_groups": len(groups), "malecns_dn_transmitters_by_manc_type": nt_by_type}
    return net, groups, info


def env_record(backend_settings: dict | None = None) -> dict:
    return {"local": fingerprint(), "modal_image": LedgerModalBackend().image_spec(), "backend_settings": backend_settings}


def load_results(campaign: str) -> dict[str, dict]:
    out = {}
    for r in read_log(data_dir() / "arms" / campaign / "results.pkl"):
        if isinstance(r, dict) and "key" in r:
            out[r["key"]] = r
    return out


def json_dump(obj) -> str:
    return json.dumps(obj, indent=1, default=str)
