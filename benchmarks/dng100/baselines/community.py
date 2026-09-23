"""Baseline: hubs of the Louvain community that contains the stimulus's heaviest direct interneuron target.

Louvain modularity communities are computed on the undirected graph whose edge weights are the synapse counts summed over
both directions (anatomical estimates used as graph weights). The community containing the interneuron that receives the
most synapses from the stimulated neuron(s) is selected, and its interneurons (role_class ``vnc_intrinsic``) are ranked by
weighted degree within that community. Roles come from the network's ``sign`` column; no essentiality claim is made.

Clean-room contract (benchmarks/dng100/cleanroom/run_method.py): reads only the public bundle named by BRAINIR_BUNDLE /
BRAINIR_NETWORK, writes BRAINIR_OUT, deterministic under BRAINIR_SEED (Louvain is seeded). ``--k`` (or BRAINIR_TOPK) sets the
core size; ``--resolution`` the Louvain resolution (default 1.0).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import time
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from brainir.benchmark.prediction import BrainIRMechanismPrediction, DynamicsClaim, MechanismClaim, MethodInfo, NeuronClaim

METHOD_NAME = "baseline_community"
METHOD_VERSION = "1.0"
DESCRIPTION = ("Louvain communities of the undirected synapse-count-weighted graph; the community holding the interneuron receiving the "
               "most synapses from the stimulus; its interneurons ranked by within-community weighted degree; roles from the network sign "
               "column; no essentiality claims.")
DEFAULT_K = 3
DEFAULT_RESOLUTION = 1.0
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


def weighted_degree(edges: pd.DataFrame) -> pd.Series:
    """Total synapse count in + out per neuron id."""
    return edges.groupby("pre_id")["synapse_count"].sum().add(edges.groupby("post_id")["synapse_count"].sum(), fill_value=0)


def undirected_graph(neurons: pd.DataFrame, edges: pd.DataFrame) -> nx.Graph:
    """Anatomical graph with synapse counts summed over both directions (pairs with a positive count; a signed_weight of 0
    from an unknown presynaptic sign does not remove an edge)."""
    e = edges[edges["synapse_count"] > 0]
    a = np.minimum(e["pre_id"].to_numpy(), e["post_id"].to_numpy())
    b = np.maximum(e["pre_id"].to_numpy(), e["post_id"].to_numpy())
    agg = pd.DataFrame({"a": a, "b": b, "w": e["synapse_count"].to_numpy()}).groupby(["a", "b"])["w"].sum()
    g = nx.Graph()
    g.add_nodes_from(int(i) for i in neurons["source_id"])
    g.add_weighted_edges_from(((int(x), int(y), float(w)) for (x, y), w in agg.items()), weight="weight")
    return g


def heaviest_direct_target(edges: pd.DataFrame, stimulus_ids: list[int], candidates: set[int]) -> int | None:
    to = edges[edges["pre_id"].isin({int(s) for s in stimulus_ids}) & edges["post_id"].isin(candidates)]
    if to.empty:
        return None
    counts = to.groupby("post_id")["synapse_count"].sum().reset_index().sort_values(["synapse_count", "post_id"], ascending=[False, True])
    return int(counts.iloc[0]["post_id"])


# ----------------------------------------------------------------------------- the method (pure, testable)
def select_core(neurons: pd.DataFrame, edges: pd.DataFrame, stimulus_ids: list[int], readout_ids: list[int], k: int,
                seed: int = 0, resolution: float = DEFAULT_RESOLUTION) -> tuple[list[int], dict]:
    exclude = set(map(int, stimulus_ids)) | set(map(int, readout_ids))
    inter = set(interneuron_ids(neurons, exclude))
    deg = weighted_degree(edges)
    hub = heaviest_direct_target(edges, stimulus_ids, inter)
    if hub is None:
        core = [int(v) for v in sorted(inter, key=lambda v: (-float(deg.get(v, 0)), v))[:k]]
        return core, {"hub": None, "fallback": "weighted degree"}
    g = undirected_graph(neurons, edges)
    comms = nx.community.louvain_communities(g, weight="weight", resolution=resolution, seed=int(seed))
    comm = next(c for c in comms if hub in c)
    sub = g.subgraph(comm)
    wdeg = dict(sub.degree(weight="weight"))
    members = sorted((v for v in comm if v in inter), key=lambda v: (-float(wdeg.get(v, 0.0)), v))
    core = [int(v) for v in members[:k]]
    if len(core) < k:  # tiny community: fill with the highest weighted-degree interneurons of the whole network
        core += [int(v) for v in sorted(inter - set(core), key=lambda v: (-float(deg.get(v, 0)), v))[: k - len(core)]]
    return core, {"hub": hub, "n_communities": len(comms), "community_size": len(comm), "community_interneurons": len(members),
                  "resolution": resolution, "within_community_weighted_degree": {int(v): float(round(wdeg.get(v, 0.0), 1)) for v in core}}


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
    ap.add_argument("--resolution", type=float, default=DEFAULT_RESOLUTION)
    args = ap.parse_args(argv)
    t0 = time.time()
    bundle, net, out = Path(os.environ["BRAINIR_BUNDLE"]), os.environ["BRAINIR_NETWORK"], Path(os.environ["BRAINIR_OUT"])
    seed = int(os.environ.get("BRAINIR_SEED", "0"))
    data = load_bundle_network(bundle, net)
    stim = [int(i) for i in data["stimulus"]["source_ids"]]
    readout = [int(i) for i in data["readout"]["source_ids"]]
    core, detail = select_core(data["neurons"], data["edges"], stim, readout, args.k, seed=seed, resolution=args.resolution)
    pred = build_prediction(data, core, seed=seed, motif="hubs of the modularity community around the heaviest direct stimulus target",
                            notes=json.dumps(detail), compute={"wall_time_s": round(time.time() - t0, 2), "simulations": 0, "backend": "networkx louvain"})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pred.to_json(), encoding="utf-8", newline="\n")
    print(f"{METHOD_NAME}: wrote {out.name} with {len(core)} core neurons {detail}")


if __name__ == "__main__":
    main()
