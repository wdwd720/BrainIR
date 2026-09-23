"""Baseline: personalized PageRank seeded at the stimulus on the directed, synapse-count-weighted graph.

Random-walk reachability: a walker restarts at the stimulated neuron(s) and follows outgoing edges in proportion to their
synapse counts (an anatomical estimate used as a transition weight, not a physiological efficacy). The k interneurons
(role_class ``vnc_intrinsic``) with the highest stationary probability form the predicted core. Roles come from the
network's ``sign`` column; no essentiality claim is made.

Clean-room contract (benchmarks/dng100/cleanroom/run_method.py): reads only the public bundle named by BRAINIR_BUNDLE /
BRAINIR_NETWORK, writes BRAINIR_OUT, deterministic (power iteration). ``--k`` (or BRAINIR_TOPK) sets the core size.
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

METHOD_NAME = "baseline_pagerank"
METHOD_VERSION = "1.0"
DESCRIPTION = ("personalized PageRank (alpha 0.85) restarting at the stimulus on the directed synapse-count-weighted graph; top-k "
               "interneurons; roles from the network sign column; no essentiality claims.")
DEFAULT_K = 3
ALPHA = 0.85
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


def directed_graph(neurons: pd.DataFrame, edges: pd.DataFrame) -> nx.DiGraph:
    """Anatomical graph: every observed pair with a positive synapse count (edges whose signed_weight is 0 because the
    presynaptic sign is unknown are still anatomical edges and are kept)."""
    e = edges[edges["synapse_count"] > 0]
    g = nx.DiGraph()
    g.add_nodes_from(int(i) for i in neurons["source_id"])
    g.add_weighted_edges_from(zip((int(i) for i in e["pre_id"]), (int(i) for i in e["post_id"]),
                                  (float(c) for c in e["synapse_count"])), weight="synapse_count")
    return g


# ----------------------------------------------------------------------------- the method (pure, testable)
def personalized_pagerank(neurons: pd.DataFrame, edges: pd.DataFrame, stimulus_ids: list[int], alpha: float = ALPHA) -> pd.Series:
    g = directed_graph(neurons, edges)
    pers = {int(s): 1.0 / len(stimulus_ids) for s in stimulus_ids}
    pr = nx.pagerank(g, alpha=alpha, personalization=pers, weight="synapse_count", tol=1e-12, max_iter=1000)
    return pd.Series(pr, dtype=float)


def select_core(neurons: pd.DataFrame, edges: pd.DataFrame, stimulus_ids: list[int], readout_ids: list[int], k: int,
                seed: int = 0) -> tuple[list[int], dict]:
    exclude = set(map(int, stimulus_ids)) | set(map(int, readout_ids))
    pr = personalized_pagerank(neurons, edges, stimulus_ids)
    tab = pd.DataFrame({"id": interneuron_ids(neurons, exclude)})
    tab["pagerank"] = tab["id"].map(pr).fillna(0.0)
    tab = tab.sort_values(["pagerank", "id"], ascending=[False, True], kind="stable")
    top = tab.head(k)
    return [int(i) for i in top["id"]], {"alpha": ALPHA, "pagerank": {int(i): float(round(v, 8)) for i, v in zip(top["id"], top["pagerank"])}}


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
    pred = build_prediction(data, core, seed=seed, motif="random-walk reachability from the stimulus (personalized PageRank)",
                            notes=json.dumps(detail), compute={"wall_time_s": round(time.time() - t0, 2), "simulations": 0, "backend": "networkx"})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pred.to_json(), encoding="utf-8", newline="\n")
    print(f"{METHOD_NAME}: wrote {out.name} with {len(core)} core neurons {detail}")


if __name__ == "__main__":
    main()
