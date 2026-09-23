"""Baseline: interneurons on the most stimulus-to-readout shortest paths (subset betweenness).

On the directed graph of edges with at least ``min_synapses`` synapses, restricted to the neurons within three hops downstream
of the stimulus plus the readout population, each edge gets length 1 / synapse_count (more synapses = shorter). The k
interneurons (role_class ``vnc_intrinsic``) with the highest betweenness restricted to (stimulus -> readout neuron) pairs
(fraction of shortest paths passing through the neuron, summed over readout targets) form the predicted core. Synapse
counts are anatomical estimates; path length here is a graph heuristic, not conduction. Roles come from the network's
``sign`` column; no essentiality claim is made.

Clean-room contract (benchmarks/dng100/cleanroom/run_method.py): reads only the public bundle named by BRAINIR_BUNDLE /
BRAINIR_NETWORK, writes BRAINIR_OUT, deterministic (no randomness). ``--k`` (or BRAINIR_TOPK) sets the core size.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import time
from pathlib import Path

import networkx as nx
import pandas as pd

from brainir.benchmark.prediction import BrainIRMechanismPrediction, DynamicsClaim, MechanismClaim, MethodInfo, NeuronClaim

METHOD_NAME = "baseline_betweenness_stim_to_readout"
METHOD_VERSION = "1.0"
DESCRIPTION = ("betweenness restricted to stimulus->readout pairs on the 3-hop downstream subgraph (edge length 1/synapse_count, "
               ">= 5 synapses); top-k interneurons; roles from the network sign column; no essentiality claims.")
DEFAULT_K = 3
HOPS = 3
MIN_SYNAPSES = 5
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


def downstream_within(edges: pd.DataFrame, sources: list[int], hops: int) -> set[int]:
    """Neurons reachable from ``sources`` in 1..hops directed steps (sources excluded)."""
    src = {int(s) for s in sources}
    frontier, seen = set(src), set()
    for _ in range(hops):
        nxt = {int(i) for i in edges.loc[edges["pre_id"].isin(frontier), "post_id"]} - seen - src
        seen |= nxt
        frontier = nxt
    return seen


def weighted_degree(edges: pd.DataFrame) -> pd.Series:
    """Total synapse count in + out per neuron id."""
    return edges.groupby("pre_id")["synapse_count"].sum().add(edges.groupby("post_id")["synapse_count"].sum(), fill_value=0)


# ----------------------------------------------------------------------------- the method (pure, testable)
def stim_readout_betweenness(edges: pd.DataFrame, stimulus_ids: list[int], readout_ids: list[int], hops: int = HOPS,
                             min_synapses: int = MIN_SYNAPSES) -> pd.Series:
    e = edges[edges["synapse_count"] >= max(1, int(min_synapses))]  # positive counts only: the edge length is 1 / count
    stim = [int(s) for s in stimulus_ids]
    nodes = downstream_within(e, stim, hops) | set(stim) | {int(r) for r in readout_ids}
    sub = e[e["pre_id"].isin(nodes) & e["post_id"].isin(nodes)]
    g = nx.DiGraph()
    g.add_nodes_from(nodes)
    g.add_edges_from((int(a), int(b), {"length": 1.0 / float(c)}) for a, b, c in zip(sub["pre_id"], sub["post_id"], sub["synapse_count"]))
    targets = [int(r) for r in readout_ids if int(r) in g and int(r) not in stim]
    bc = nx.betweenness_centrality_subset(g, sources=stim, targets=targets, normalized=False, weight="length")
    return pd.Series(bc, dtype=float)


def select_core(neurons: pd.DataFrame, edges: pd.DataFrame, stimulus_ids: list[int], readout_ids: list[int], k: int,
                seed: int = 0) -> tuple[list[int], dict]:
    exclude = set(map(int, stimulus_ids)) | set(map(int, readout_ids))
    bc = stim_readout_betweenness(edges, stimulus_ids, readout_ids)
    tab = pd.DataFrame({"id": interneuron_ids(neurons, exclude)})
    tab["betweenness"] = tab["id"].map(bc).fillna(0.0)
    tab["total_synapses"] = tab["id"].map(weighted_degree(edges)).fillna(0).astype(int)
    tab = tab.sort_values(["betweenness", "total_synapses", "id"], ascending=[False, False, True], kind="stable")
    top = tab.head(k)
    return [int(i) for i in top["id"]], {"hops": HOPS, "min_synapses": MIN_SYNAPSES, "n_in_subgraph": int(len(bc)),
                                         "betweenness": {int(i): float(round(v, 4)) for i, v in zip(top["id"], top["betweenness"])}}


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
    args = ap.parse_args(argv)
    t0 = time.time()
    bundle, net, out = Path(os.environ["BRAINIR_BUNDLE"]), os.environ["BRAINIR_NETWORK"], Path(os.environ["BRAINIR_OUT"])
    seed = int(os.environ.get("BRAINIR_SEED", "0"))
    data = load_bundle_network(bundle, net)
    stim = [int(i) for i in data["stimulus"]["source_ids"]]
    readout = [int(i) for i in data["readout"]["source_ids"]]
    core, detail = select_core(data["neurons"], data["edges"], stim, readout, args.k, seed=seed)
    pred = build_prediction(data, core, seed=seed, motif="feed-forward relay on stimulus->readout shortest paths", notes=json.dumps(detail),
                            compute={"wall_time_s": round(time.time() - t0, 2), "simulations": 0, "backend": "networkx"})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pred.to_json(), encoding="utf-8", newline="\n")
    print(f"{METHOD_NAME}: wrote {out.name} with {len(core)} core neurons {detail}")


if __name__ == "__main__":
    main()
