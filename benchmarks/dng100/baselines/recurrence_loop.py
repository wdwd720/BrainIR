"""Baseline: reciprocal (2-cycle) partners of the stimulus's heaviest direct interneuron target.

The hub is the interneuron (role_class ``vnc_intrinsic``) receiving the most synapses from the stimulated neuron(s). Every
other interneuron j is scored by its mutual 2-cycle with the hub, ``min(count(hub -> j), count(j -> hub))`` (0 without a
reciprocal pair), with the one-directional maximum as tie-break. The predicted core is the hub plus its best-scoring
partners filled so that it contains an excitatory pair and an inhibitory member (for k = 3: hub + best excitatory partner +
best inhibitory partner); further slots go to the next partners regardless of sign. Synapse counts are anatomical
estimates, used here as a graph score only. Roles come from the ``sign`` column; no essentiality claim is made.

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

METHOD_NAME = "baseline_recurrence_loop"
METHOD_VERSION = "1.0"
DESCRIPTION = ("hub = interneuron receiving the most synapses from the stimulus; partners scored by the mutual 2-cycle synapse count "
               "min(hub->j, j->hub); core = hub + partners completing an excitatory pair and an inhibitory slot; roles from the "
               "network sign column; no essentiality claims.")
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
def heaviest_direct_target(edges: pd.DataFrame, stimulus_ids: list[int], candidates: set[int]) -> int | None:
    """The candidate receiving the most synapses from the stimulus (ties -> smallest id); None when no candidate is a target."""
    to = edges[edges["pre_id"].isin({int(s) for s in stimulus_ids}) & edges["post_id"].isin(candidates)]
    if to.empty:
        return None
    counts = to.groupby("post_id")["synapse_count"].sum().reset_index().sort_values(["synapse_count", "post_id"], ascending=[False, True])
    return int(counts.iloc[0]["post_id"])


def reciprocal_partners(edges: pd.DataFrame, hub: int, candidates: set[int]) -> pd.DataFrame:
    """Per candidate: synapses hub->j, j->hub, loop = min of both, one_way = max of both; sorted by (loop, one_way, id)."""
    out_c = edges[edges["pre_id"] == hub].groupby("post_id")["synapse_count"].sum()
    in_c = edges[edges["post_id"] == hub].groupby("pre_id")["synapse_count"].sum()
    ids = sorted((set(int(i) for i in out_c.index) | set(int(i) for i in in_c.index)) & candidates - {hub})
    tab = pd.DataFrame({"id": ids})
    tab["hub_to"] = tab["id"].map(out_c).fillna(0).astype(int)
    tab["to_hub"] = tab["id"].map(in_c).fillna(0).astype(int)
    tab["loop"] = tab[["hub_to", "to_hub"]].min(axis=1)
    tab["one_way"] = tab[["hub_to", "to_hub"]].max(axis=1)
    return tab.sort_values(["loop", "one_way", "id"], ascending=[False, False, True], kind="stable").reset_index(drop=True)


def select_core(neurons: pd.DataFrame, edges: pd.DataFrame, stimulus_ids: list[int], readout_ids: list[int], k: int,
                seed: int = 0) -> tuple[list[int], dict]:
    exclude = set(map(int, stimulus_ids)) | set(map(int, readout_ids))
    inter = set(interneuron_ids(neurons, exclude))
    sign = neurons.set_index("source_id")["sign"]
    deg = weighted_degree(edges)
    hub = heaviest_direct_target(edges, stimulus_ids, inter)
    if hub is None:  # no direct interneuron target: fall back to the highest weighted-degree interneurons
        core = [int(v) for v in sorted(inter, key=lambda v: (-float(deg.get(v, 0)), v))[:k]]
        return core, {"hub": None, "fallback": "weighted degree"}
    partners = reciprocal_partners(edges, hub, inter)
    partners["sign"] = partners["id"].map(sign).astype(int)
    hub_sign = int(sign.loc[hub])
    core = [hub]
    slots = {"excitatory": 2 - (1 if hub_sign > 0 else 0), "inhibitory": 1 - (1 if hub_sign < 0 else 0)}
    for role, cond in (("excitatory", partners["sign"] > 0), ("inhibitory", partners["sign"] < 0)):
        for i in partners.loc[cond, "id"]:
            if slots[role] <= 0 or len(core) >= k:
                break
            core.append(int(i))
            slots[role] -= 1
    for i in partners["id"]:
        if len(core) >= k:
            break
        if int(i) not in core:
            core.append(int(i))
    if len(core) < k:  # too few partners: fill with the highest weighted-degree interneurons
        core += [int(v) for v in sorted(inter - set(core), key=lambda v: (-float(deg.get(v, 0)), v))[: k - len(core)]]
    loop_members = [hub] + [int(i) for i in core[1:] if int(partners.set_index("id")["loop"].get(int(i), 0)) > 0 and int(sign.loc[int(i)]) > 0]
    detail = {"hub": hub, "hub_sign": hub_sign, "n_reciprocal_partners": int((partners["loop"] > 0).sum()),
              "loop_synapses": {int(r.id): int(r.loop) for r in partners.itertuples() if int(r.id) in core}, "loop_members": loop_members}
    return core, detail


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
    loop = detail.get("loop_members", []) if len(detail.get("loop_members", [])) >= 2 else []
    motif = "reciprocal excitation between the heaviest direct target and its excitatory 2-cycle partner, plus an inhibitory partner"
    pred = build_prediction(data, core, seed=seed, loop=loop, notes=json.dumps(detail), motif=motif,
                            compute={"wall_time_s": round(time.time() - t0, 2), "simulations": 0, "backend": "pandas"})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pred.to_json(), encoding="utf-8", newline="\n")
    print(f"{METHOD_NAME}: wrote {out.name} with {len(core)} core neurons {detail}")


if __name__ == "__main__":
    main()
