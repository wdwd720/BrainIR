"""Baseline: the k interneurons sharing the most synapses with the stimulus (direct targets by synapse count).

Ranks interneurons (role_class ``vnc_intrinsic``) by the total synapse count of their edges with the stimulated neuron(s)
(stimulus -> neuron plus neuron -> stimulus), ties broken by total weighted degree (synapse count in + out), then by id.
Synapse counts are anatomical estimates; the ranking says nothing about physiological efficacy. Roles come from the
network's ``sign`` column; no essentiality claim is made.

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

import pandas as pd

from brainir.benchmark.prediction import BrainIRMechanismPrediction, DynamicsClaim, MechanismClaim, MethodInfo, NeuronClaim

METHOD_NAME = "baseline_degree_topk"
METHOD_VERSION = "1.0"
DESCRIPTION = ("top-k interneurons by total synapse count of edges shared with the stimulus (direct targets), ties by total weighted "
               "degree; roles from the network sign column; no essentiality claims.")
DEFAULT_K = 3
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


# ----------------------------------------------------------------------------- the method (pure, testable)
def stimulus_contact(edges: pd.DataFrame, stimulus_ids: list[int]) -> pd.Series:
    """Synapse count of edges between each neuron and the stimulus, both directions summed."""
    stim = {int(s) for s in stimulus_ids}
    to = edges.loc[edges["pre_id"].isin(stim)].groupby("post_id")["synapse_count"].sum()
    fro = edges.loc[edges["post_id"].isin(stim)].groupby("pre_id")["synapse_count"].sum()
    return to.add(fro, fill_value=0)


def select_core(neurons: pd.DataFrame, edges: pd.DataFrame, stimulus_ids: list[int], readout_ids: list[int], k: int,
                seed: int = 0) -> tuple[list[int], dict]:
    exclude = set(map(int, stimulus_ids)) | set(map(int, readout_ids))
    tab = pd.DataFrame({"id": interneuron_ids(neurons, exclude)})
    tab["stimulus_synapses"] = tab["id"].map(stimulus_contact(edges, stimulus_ids)).fillna(0).astype(int)
    tab["total_synapses"] = tab["id"].map(weighted_degree(edges)).fillna(0).astype(int)
    tab = tab.sort_values(["stimulus_synapses", "total_synapses", "id"], ascending=[False, False, True], kind="stable")
    top = tab.head(k)
    core = [int(i) for i in top["id"]]
    return core, {"n_direct_targets": int((tab["stimulus_synapses"] > 0).sum()),
                  "stimulus_synapses": {int(i): int(c) for i, c in zip(top["id"], top["stimulus_synapses"])}}


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
    pred = build_prediction(data, core, seed=seed, motif="direct stimulus targets ranked by synapse count", notes=json.dumps(detail),
                            compute={"wall_time_s": round(time.time() - t0, 2), "simulations": 0, "backend": "pandas"})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pred.to_json(), encoding="utf-8", newline="\n")
    print(f"{METHOD_NAME}: wrote {out.name} with {len(core)} core neurons {detail}")


if __name__ == "__main__":
    main()
