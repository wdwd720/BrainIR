"""Baseline: statistical enrichment of stimulus input and reciprocity against degree-matched shuffles (no simulation).

Two per-interneuron statistics (role_class ``vnc_intrinsic``), both plain synapse counts:
  S_i = synapses received from the stimulated neuron(s);
  R_i = sum_j min(count(i -> j), count(j -> i)), the neuron's total mutual (2-cycle) synapses.
Null 1 (for S): the stimulus's outgoing edges are re-targeted to random neurons drawn from the weighted in-degree decile of
their real target; the z-score pools the null values of all neurons in the same decile (a per-neuron null is degenerate).
Null 2 (for R): postsynaptic endpoints of ALL edges are permuted within weighted in-degree deciles (a degree-matched
rewiring that keeps every edge's presynaptic neuron and synapse count); z per neuron over the shuffles (sd floored at 1).
Combined score = normal-quantile-transformed rank of z_S + the same for z_R across interneurons (the two z-scales differ by
orders of magnitude, so a raw sum would be decided by reciprocity alone); top-k. ``--shuffles`` (default 100) and ``--bins``
(default 10) control the null. Roles come from the network's ``sign`` column; no essentiality claim is made.

Clean-room contract (benchmarks/dng100/cleanroom/run_method.py): reads only the public bundle named by BRAINIR_BUNDLE /
BRAINIR_NETWORK, writes BRAINIR_OUT, deterministic under BRAINIR_SEED. ``--k`` (or BRAINIR_TOPK) sets the core size.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.stats import norm, rankdata

from brainir.benchmark.prediction import BrainIRMechanismPrediction, DynamicsClaim, MechanismClaim, MethodInfo, NeuronClaim

METHOD_NAME = "baseline_statistical_motif"
METHOD_VERSION = "1.0"
DESCRIPTION = ("z-scores of stimulus input synapses and of mutual 2-cycle synapses against degree-matched endpoint shuffles (100 by "
               "default, in-degree deciles); top-k by the sum of the rank-normal scores of z_S and z_R across interneurons; roles from "
               "the network sign column; no essentiality claims.")
DEFAULT_K = 3
DEFAULT_SHUFFLES = 100
DEFAULT_BINS = 10
INTERNEURON_ROLE = "vnc_intrinsic"


# ----------------------------------------------------------------------------- bundle access (public files only)
def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def load_bundle_network(bundle: Path, net: str) -> dict:
    d = bundle / "networks" / net
    return {"neurons": pd.read_parquet(d / "neurons.parquet"), "edges": pd.read_parquet(d / "edges.parquet"),
            "stimulus": _read_json(d / "stimulus.json"), "readout": _read_json(d / "readout.json"),
            "info": _read_json(d / "network.json"), "manifest": _read_json(bundle / "manifest.json")}


def role_of(sign) -> str:
    s = int(sign)
    return "excitatory" if s > 0 else "inhibitory" if s < 0 else "unknown"


def interneuron_ids(neurons: pd.DataFrame, exclude: set[int]) -> list[int]:
    m = (neurons["role_class"] == INTERNEURON_ROLE) & ~neurons["is_stimulus"].astype(bool) & ~neurons["is_readout"].astype(bool)
    return sorted(int(i) for i in neurons.loc[m, "source_id"] if int(i) not in exclude)


# ----------------------------------------------------------------------------- the method (pure, testable)
def _reciprocal_synapses(counts: sp.csr_matrix) -> np.ndarray:
    c = counts.tocsr(copy=True)
    c.setdiag(0)
    c.eliminate_zeros()
    return np.asarray(c.minimum(c.T).sum(axis=1)).ravel()


def enrichment_z(neurons: pd.DataFrame, edges: pd.DataFrame, stimulus_ids: list[int], seed: int = 0, n_shuffles: int = DEFAULT_SHUFFLES,
                 n_bins: int = DEFAULT_BINS) -> pd.DataFrame:
    """Per neuron: S (stimulus input synapses), R (mutual synapses), z_S, z_R and z = z_S + z_R."""
    ids = neurons["source_id"].to_numpy().astype(np.int64)
    n = len(ids)
    pos = pd.Series(np.arange(n), index=ids)
    pre = pos.loc[edges["pre_id"].to_numpy()].to_numpy()
    post = pos.loc[edges["post_id"].to_numpy()].to_numpy()
    cnt = edges["synapse_count"].to_numpy(dtype=np.float64)
    counts = sp.csr_matrix((cnt, (post, pre)), shape=(n, n))  # post x pre
    in_deg = np.asarray(counts.sum(axis=1)).ravel()
    n_bins = max(1, min(n_bins, n))
    ranks = np.argsort(np.argsort(in_deg, kind="stable"), kind="stable")
    bins = np.minimum((ranks * n_bins) // n, n_bins - 1)
    members = [np.flatnonzero(bins == b) for b in range(n_bins)]
    stim_pos = pos.loc[[int(s) for s in stimulus_ids]].to_numpy()
    s_obs = np.asarray(counts[:, stim_pos].sum(axis=1)).ravel()
    r_obs = _reciprocal_synapses(counts)
    rng = np.random.default_rng(seed)
    # null 1: stimulus out-edges re-targeted within the in-degree bin of the real target
    stim_edge = np.isin(pre, stim_pos)
    s_null = np.zeros((n_shuffles, n))
    for s in range(n_shuffles):
        tgt = np.array([rng.choice(members[bins[p]]) for p in post[stim_edge]], dtype=np.int64)
        np.add.at(s_null[s], tgt, cnt[stim_edge])
    mu_bin = np.array([s_null[:, m].mean() if len(m) else 0.0 for m in members])
    sd_bin = np.array([s_null[:, m].std() if len(m) else 0.0 for m in members])
    z_s = (s_obs - mu_bin[bins]) / np.maximum(sd_bin[bins], 1e-9)
    # null 2: postsynaptic endpoints permuted within in-degree bins (all edges)
    edge_groups = [np.flatnonzero(bins[post] == b) for b in range(n_bins)]
    r_null = np.zeros((n_shuffles, n))
    for s in range(n_shuffles):
        new_post = post.copy()
        for g in edge_groups:
            if len(g) > 1:
                new_post[g] = post[rng.permutation(g)]
        shuffled = sp.csr_matrix((cnt, (new_post, pre)), shape=(n, n))
        shuffled.sum_duplicates()
        r_null[s] = _reciprocal_synapses(shuffled)
    z_r = (r_obs - r_null.mean(axis=0)) / np.maximum(r_null.std(axis=0), 1.0)
    return pd.DataFrame({"id": ids, "in_degree_bin": bins, "S": s_obs.astype(int), "R": r_obs.astype(int), "z_S": z_s, "z_R": z_r}).set_index("id")


def rank_normal(v: np.ndarray) -> np.ndarray:
    """Van der Waerden scores: normal quantiles of the (average-tie) ranks, so two statistics of different scale are commensurable."""
    v = np.nan_to_num(np.asarray(v, dtype=np.float64))
    return norm.ppf((rankdata(v, method="average") - 0.5) / len(v)) if len(v) else v


def select_core(neurons: pd.DataFrame, edges: pd.DataFrame, stimulus_ids: list[int], readout_ids: list[int], k: int, seed: int = 0,
                n_shuffles: int = DEFAULT_SHUFFLES, n_bins: int = DEFAULT_BINS) -> tuple[list[int], dict]:
    exclude = set(map(int, stimulus_ids)) | set(map(int, readout_ids))
    z = enrichment_z(neurons, edges, stimulus_ids, seed=seed, n_shuffles=n_shuffles, n_bins=n_bins)
    tab = z.loc[interneuron_ids(neurons, exclude)].reset_index()
    tab["combined"] = rank_normal(tab["z_S"].to_numpy()) + rank_normal(tab["z_R"].to_numpy())
    tab = tab.sort_values(["combined", "id"], ascending=[False, True], kind="stable")
    top = tab.head(k)
    core = [int(i) for i in top["id"]]
    return core, {"n_shuffles": n_shuffles, "n_bins": n_bins, "seed": int(seed),
                  "z": {int(r.id): {"S": int(r.S), "R": int(r.R), "z_S": round(float(r.z_S), 2), "z_R": round(float(r.z_R), 2),
                                    "combined": round(float(r.combined), 3)} for r in top.itertuples()}}


# ----------------------------------------------------------------------------- prediction
def build_prediction(data: dict, core: list[int], *, seed: int, compute: dict, essential: dict[int, bool | None] | None = None,
                     motif: str | None = None, loop: list[int] = (), notes: str | None = None) -> BrainIRMechanismPrediction:
    neurons = data["neurons"].set_index("source_id")
    net = data["info"]["name"]
    claims = [NeuronClaim(source_id=int(i), role=role_of(neurons.loc[int(i), "sign"]), rank=r + 1, essential=(essential or {}).get(int(i)))
              for r, i in enumerate(core)]
    inputs = [f"networks/{net}/{f}" for f in ("neurons.parquet", "edges.parquet", "stimulus.json", "readout.json", "network.json")] + ["manifest.json"]
    return BrainIRMechanismPrediction(
        benchmark_id=data["manifest"]["benchmark_id"], dataset=data["info"]["dataset"], dataset_version=data["info"]["version"],
        stimulus_source_ids=[int(i) for i in data["stimulus"]["source_ids"]], core_neurons=claims,
        dynamics=DynamicsClaim(rhythmic=True), mechanism=MechanismClaim(motif=motif, loop_neurons=[int(i) for i in loop], notes=notes),
        method=MethodInfo(name=METHOD_NAME, version=METHOD_VERSION, description=DESCRIPTION, inputs_used=inputs, compute=compute,
                          random_seed=int(seed)),
        created_utc=_dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--k", type=int, default=int(os.environ.get("BRAINIR_TOPK", DEFAULT_K)))
    ap.add_argument("--shuffles", type=int, default=DEFAULT_SHUFFLES)
    ap.add_argument("--bins", type=int, default=DEFAULT_BINS)
    args = ap.parse_args(argv)
    t0 = time.time()
    bundle, net, out = Path(os.environ["BRAINIR_BUNDLE"]), os.environ["BRAINIR_NETWORK"], Path(os.environ["BRAINIR_OUT"])
    seed = int(os.environ.get("BRAINIR_SEED", "0"))
    data = load_bundle_network(bundle, net)
    stim = [int(i) for i in data["stimulus"]["source_ids"]]
    readout = [int(i) for i in data["readout"]["source_ids"]]
    core, detail = select_core(data["neurons"], data["edges"], stim, readout, args.k, seed=seed, n_shuffles=args.shuffles, n_bins=args.bins)
    pred = build_prediction(data, core, seed=seed, motif="stimulus-input and reciprocity enrichment vs degree-matched shuffles",
                            notes=json.dumps(detail), compute={"wall_time_s": round(time.time() - t0, 2), "simulations": 0,
                                                               "shuffles": args.shuffles, "backend": "numpy/scipy.sparse"})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pred.to_json(), encoding="utf-8", newline="\n")
    print(f"{METHOD_NAME}: wrote {out.name} with {len(core)} core neurons {detail}")


if __name__ == "__main__":
    main()
