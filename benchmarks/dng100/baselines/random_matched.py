"""Baseline: sign-matched random interneurons within two hops downstream of the stimulus.

Chance level for a structural method that already knows where to look: k interneurons (role_class ``vnc_intrinsic``) drawn
uniformly at random among those reachable from the stimulated neuron(s) in at most two directed hops, with a fixed sign
composition (``round(k / 3)`` inhibitory, the rest excitatory: 2 E + 1 I for k = 3). Roles are read from the network's own
``sign`` column (a rule applied to a neurotransmitter prediction, not a measurement); no essentiality claim is made.

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

from brainir.benchmark.prediction import BrainIRMechanismPrediction, DynamicsClaim, MechanismClaim, MethodInfo, NeuronClaim

METHOD_NAME = "baseline_random_matched"
METHOD_VERSION = "1.0"
DESCRIPTION = ("k random interneurons among those within two directed hops downstream of the stimulus, sign composition fixed to "
               "round(k/3) inhibitory + the rest excitatory; roles from the network sign column; no essentiality claims.")
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


def downstream_within(edges: pd.DataFrame, sources: list[int], hops: int) -> set[int]:
    """Neurons reachable from ``sources`` in 1..hops directed steps (sources excluded)."""
    src = {int(s) for s in sources}
    frontier, seen = set(src), set()
    for _ in range(hops):
        nxt = {int(i) for i in edges.loc[edges["pre_id"].isin(frontier), "post_id"]} - seen - src
        seen |= nxt
        frontier = nxt
    return seen


# ----------------------------------------------------------------------------- the method (pure, testable)
def sign_composition(k: int) -> tuple[int, int]:
    """(n_excitatory, n_inhibitory): one inhibitory slot per three core neurons, at least one when k >= 2."""
    n_inh = max(1, round(k / 3)) if k >= 2 else 0
    return k - n_inh, n_inh


def select_core(neurons: pd.DataFrame, edges: pd.DataFrame, stimulus_ids: list[int], readout_ids: list[int], k: int,
                seed: int = 0) -> tuple[list[int], dict]:
    exclude = set(map(int, stimulus_ids)) | set(map(int, readout_ids))
    inter = set(interneuron_ids(neurons, exclude))
    pool = sorted(downstream_within(edges, stimulus_ids, 2) & inter)
    if len(pool) < k:
        pool = sorted(inter)
    sign = neurons.set_index("source_id")["sign"]
    exc = [i for i in pool if int(sign.loc[i]) > 0]
    inh = [i for i in pool if int(sign.loc[i]) < 0]
    n_exc, n_inh = sign_composition(k)
    rng = np.random.default_rng(seed)
    core = [int(i) for i in rng.choice(exc, size=min(n_exc, len(exc)), replace=False)] if exc else []
    core += [int(i) for i in rng.choice(inh, size=min(n_inh, len(inh)), replace=False)] if inh else []
    rest = [i for i in pool if i not in core]
    if len(core) < k and rest:
        core += [int(i) for i in rng.choice(rest, size=min(k - len(core), len(rest)), replace=False)]
    return core, {"pool_size": len(pool), "composition": {"excitatory": n_exc, "inhibitory": n_inh}, "seed": int(seed)}


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
    pred = build_prediction(data, core, seed=seed, motif="random draw (chance level)", notes=json.dumps(detail),
                            compute={"wall_time_s": round(time.time() - t0, 2), "simulations": 0, "backend": "numpy/pandas"})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pred.to_json(), encoding="utf-8", newline="\n")
    print(f"{METHOD_NAME}: wrote {out.name} with {len(core)} core neurons {detail}")


if __name__ == "__main__":
    main()
