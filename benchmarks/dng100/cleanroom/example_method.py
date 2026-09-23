"""Smoke-test discovery method for the clean-room runner: NOT a baseline, NOT a result.

Picks the k strongest direct targets of the stimulus neuron among interneurons and calls them the mechanism, with roles
from the network's own sign column and no essentiality claims. It exists only to exercise the runner/evaluator plumbing.
Reads the bundle through the environment contract documented in run_method.py; imports nothing from benchmarks/.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path

import pandas as pd

from brainir.benchmark.prediction import BrainIRMechanismPrediction, DynamicsClaim, MechanismClaim, MethodInfo, NeuronClaim


def main() -> None:
    bundle = Path(os.environ["BRAINIR_BUNDLE"])
    net = os.environ["BRAINIR_NETWORK"]
    out = Path(os.environ["BRAINIR_OUT"])
    k = int(os.environ.get("BRAINIR_TOPK", "3"))
    d = bundle / "networks" / net
    info = json.loads((d / "network.json").read_text(encoding="utf-8"))
    stim = json.loads((d / "stimulus.json").read_text(encoding="utf-8"))
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    neurons = pd.read_parquet(d / "neurons.parquet").set_index("source_id")
    edges = pd.read_parquet(d / "edges.parquet")
    targets = edges[edges["pre_id"].isin(stim["source_ids"])].groupby("post_id")["synapse_count"].sum().sort_values(ascending=False)
    inter = [int(i) for i in targets.index if neurons.loc[i, "role_class"] == "vnc_intrinsic"][:k]
    claims = [NeuronClaim(source_id=i, role="excitatory" if neurons.loc[i, "sign"] > 0 else "inhibitory" if neurons.loc[i, "sign"] < 0 else "unknown",
                          rank=r + 1) for r, i in enumerate(inter)]
    pred = BrainIRMechanismPrediction(
        benchmark_id=manifest["benchmark_id"], dataset=info["dataset"], dataset_version=info["version"],
        stimulus_source_ids=[int(i) for i in stim["source_ids"]], core_neurons=claims,
        dynamics=DynamicsClaim(rhythmic=True), mechanism=MechanismClaim(motif="strongest direct stimulus targets (smoke test)"),
        method=MethodInfo(name="example_topk_targets", version="0", inputs_used=["networks/*/edges.parquet", "networks/*/neurons.parquet"],
                          random_seed=int(os.environ.get("BRAINIR_SEED", "0"))),
        created_utc=_dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"))
    out.write_text(pred.to_json(), encoding="utf-8", newline="\n")
    print(f"wrote {out} with {len(claims)} claims")


if __name__ == "__main__":
    main()
