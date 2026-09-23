"""Reliability sweeps: run a method many times on the same public problem under different random seeds and node orderings.

A *node-order variant* of a bundle network is the same graph with positions permuted by a seeded random permutation
(exactly what tier A does at export); the permutation is kept in a private side file so predictions can be mapped back
to a common frame. Reliability is then measured WITHOUT any oracle:

    identity consistency   pairwise Jaccard of the predicted cores across runs (in the common frame), the modal core
                           and its frequency, the per-neuron selection frequency
    size distribution      |core| across runs
    functional fidelity    keep-only of each predicted core on the true simulator with fresh parameter seeds (pass fraction)
    budget                 simulator calls / wall time per run

Hidden-oracle scoring of the same predictions is a separate, explicitly logged step (``scripts/reliability_sweep.py
--hidden-eval``), never used to design a method.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ..benchmark.prediction import BrainIRMechanismPrediction
from .interventions import keep_only
from .problem import DiscoveryProblem, pack_bundle, path_basename, unpack_bundle, write_bundle_manifest
from .simulator import BudgetedSimulator

FROZEN_NAME = "greedy_prune_sim_frozen"


# ---------------------------------------------------------------------------- permuted variants
def make_permuted_bundle(src_root: Path, network: str, seed: int | None, dest_root: Path, private_dir: Path | None = None) -> dict:
    """Copy one network of a bundle into dest_root with positions permuted (seeded; ``seed=None`` = identity, i.e. the bundle's
    own order). Returns {'perm': ..., 'dir': ..., 'positional': ...}.

    perm[p] = source position at new position p. Works for positional-id bundles (tier A / synthetic); for body-id bundles
    (tier B) the ids stay but positions/edge positions are permuted, so the id semantics are unchanged. The variant gets its own
    verifiable manifest; the permutation is written to ``private_dir`` (default ``dest_root/../_private``), never inside the
    variant."""
    src = Path(src_root) / "networks" / network
    d = Path(dest_root) / "networks" / network
    d.mkdir(parents=True, exist_ok=True)
    neurons = pd.read_parquet(src / "neurons.parquet").sort_values("position").reset_index(drop=True)
    edges = pd.read_parquet(src / "edges.parquet")
    n = len(neurons)
    perm = np.arange(n) if seed is None else np.random.default_rng(seed).permutation(n)
    inv = np.empty(n, dtype=np.int64)
    inv[perm] = np.arange(n)
    positional = json.loads((src / "network.json").read_text(encoding="utf-8")).get("id_semantics", "").startswith("positional")
    nn = neurons.iloc[perm].reset_index(drop=True)
    nn["position"] = np.arange(n)
    if positional:
        nn["source_id"] = np.arange(n)
    ee = edges.copy()
    ee["pre_position"] = inv[edges["pre_position"].to_numpy()].astype(np.int32)
    ee["post_position"] = inv[edges["post_position"].to_numpy()].astype(np.int32)
    if positional:
        ee["pre_id"] = ee["pre_position"].astype(np.int64)
        ee["post_id"] = ee["post_position"].astype(np.int64)
    ee = ee.sort_values(["pre_position", "post_position"], ignore_index=True)
    pq.write_table(pa.Table.from_pandas(nn, preserve_index=False), d / "neurons.parquet", compression="zstd")
    pq.write_table(pa.Table.from_pandas(ee, preserve_index=False), d / "edges.parquet", compression="zstd")
    for f in ("stimulus.json", "readout.json"):
        j = json.loads((src / f).read_text(encoding="utf-8"))
        j["positions"] = [int(inv[p]) for p in j["positions"]]
        if positional:
            j["source_ids"] = list(j["positions"])
        (d / f).write_text(json.dumps(j, indent=1) + "\n", encoding="utf-8", newline="\n")
    if (src / "criterion.json").exists():
        c = json.loads((src / "criterion.json").read_text(encoding="utf-8"))
        for k in ("group_a_positions", "group_b_positions"):
            if k in c:
                c[k] = [int(inv[p]) for p in c[k]]
        (d / "criterion.json").write_text(json.dumps(c, indent=1) + "\n", encoding="utf-8", newline="\n")
    info = json.loads((src / "network.json").read_text(encoding="utf-8"))
    info["order_variant_seed"] = None if seed is None else int(seed)
    (d / "network.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8", newline="\n")
    for f in ("model_config.json", "README.md"):
        if (Path(src_root) / f).exists():
            shutil.copyfile(Path(src_root) / f, Path(dest_root) / f)
    # a fresh manifest (the variant's files differ from the source's) that records where it came from
    src_manifest_path = Path(src_root) / "manifest.json"
    src_manifest = json.loads(src_manifest_path.read_text(encoding="utf-8")) if src_manifest_path.exists() else {}
    header = {k: v for k, v in src_manifest.items() if k not in ("files", "bundle_sha256", "networks")}
    header["networks"] = [x for x in src_manifest.get("networks", []) if isinstance(x, dict) and x.get("name") == network]
    header["node_order_variant"] = {"derived_from_bundle_sha256": src_manifest.get("bundle_sha256"), "network": network,
                                    "seed": None if seed is None else int(seed)}
    write_bundle_manifest(dest_root, header)
    # the permutation is kept OUTSIDE the variant bundle: a method reading its bundle must not be able to undo the reordering
    priv = Path(private_dir) if private_dir is not None else Path(dest_root).parent / "_private"
    priv.mkdir(parents=True, exist_ok=True)
    (priv / f"perm_{Path(dest_root).name}_{network}.json").write_text(
        json.dumps({"seed": None if seed is None else int(seed), "perm": [int(x) for x in perm]}) + "\n", encoding="utf-8", newline="\n")
    return {"dir": str(dest_root), "perm": perm, "positional": positional}


def prediction_to_common_frame(pred: BrainIRMechanismPrediction, perm: np.ndarray, positional: bool) -> dict:
    """The prediction as a JSON dict with every neuron id mapped from the permuted variant back to the source bundle's ids."""
    d = pred.model_dump(mode="json")
    if not positional:
        return d

    def m(i):
        return int(perm[int(i)])

    d["stimulus_source_ids"] = [m(i) for i in d["stimulus_source_ids"]]
    for c in d["core_neurons"]:
        c["source_id"] = m(c["source_id"])
    d["mechanism"]["loop_neurons"] = [m(i) for i in d["mechanism"]["loop_neurons"]]
    for c in d.get("cross_connectome", []):
        c["source_id"] = m(c["source_id"])
    return d


def to_common_frame(pred: BrainIRMechanismPrediction, perm: np.ndarray | None, positional: bool) -> list[int]:
    """Predicted core in the canonical frame (source positions of the unpermuted bundle, or body ids for tier B)."""
    ids = pred.core_ids()
    if perm is None or not positional:
        return sorted(int(i) for i in ids)
    return sorted(int(perm[int(i)]) for i in ids)


# ---------------------------------------------------------------------------- running
def run_frozen_baseline(script: Path, bundle: Path, network: str, out: Path, seed: int, args: list[str], timeout_s: int = 7200) -> dict:
    """Run a frozen clean-room-contract method script directly (no sandbox: this is a sweep, not a submission)."""
    env = {**os.environ, "BRAINIR_BUNDLE": str(bundle), "BRAINIR_NETWORK": network, "BRAINIR_OUT": str(out), "BRAINIR_SEED": str(seed),
           "PYTHONIOENCODING": "utf-8"}
    t0 = time.time()
    proc = subprocess.run([sys.executable, str(script), *args], env=env, capture_output=True, text=True, timeout=timeout_s, cwd=str(bundle))
    return {"returncode": proc.returncode, "wall_s": round(time.time() - t0, 1), "stderr_tail": proc.stderr[-800:], "stdout_tail": proc.stdout[-400:]}


def sweep_job(args) -> dict:
    """One reliability run (module-level so backends can import it).

    ``args`` = dict(method, variant_dir, network, seed, budget, config, perm, positional, frozen_args, frozen_script, packs).
    On a remote worker the variant directory is rebuilt from ``packs[variant name]`` (a :func:`pack_bundle` dict) and the frozen
    script is written from ``frozen_script`` (its source text); predictions are returned in the result instead of on disk."""
    from .run import run_method

    method, network, seed = args["method"], args["network"], int(args["seed"])
    variant_dir = Path(args["variant_dir"])
    variant_name = path_basename(variant_dir)
    packs = args.get("packs")
    remote = not variant_dir.exists()
    if remote:
        tmp = Path(tempfile.mkdtemp(prefix="brainir_rel_"))
        variant_dir = unpack_bundle(packs[variant_name], tmp / variant_name)
    # outputs live next to the variant, never inside it (a method must not see other runs' predictions in its bundle)
    run_dir = variant_dir.parent / "_runs" / variant_name
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / f"pred_{method}_s{seed}.json"
    t0 = time.time()
    result = None
    if method == FROZEN_NAME:
        script = Path(args["frozen_script_path"]) if args.get("frozen_script_path") and Path(args["frozen_script_path"]).exists() else None
        if script is None:
            script = run_dir / "frozen_method.py"
            script.write_text(args["frozen_script"], encoding="utf-8", newline="\n")
        r = run_frozen_baseline(script, variant_dir, network, out, seed, list(args.get("frozen_args") or []))
        if r["returncode"] != 0 or not out.exists():
            return {"seed": seed, "variant": variant_name, "error": r["stderr_tail"][-400:], "wall_s": r["wall_s"]}
        pred = BrainIRMechanismPrediction.from_json(out.read_text(encoding="utf-8"))
        comp = pred.method.compute or {}
        calls = comp.get("n_simulations") or comp.get("simulations") or comp.get("calls")
    else:
        pred, result = run_method(method, variant_dir, network, budget=int(args["budget"]), seed=seed, config=args.get("config") or {}, workers=1)
        out.write_text(pred.to_json(), encoding="utf-8", newline="\n")
        calls = result.budget.get("calls")
    perm_arr = np.array(args["perm"])
    positional = bool(args["positional"])
    common = prediction_to_common_frame(pred, perm_arr, positional)
    rec = {"seed": seed, "variant": variant_name, "core_common": to_common_frame(pred, perm_arr, positional), "core_public": pred.core_ids(),
           "n_core": len(pred.core_ids()), "calls": calls, "wall_s": round(time.time() - t0, 1), "prediction_sha256": pred.digest(),
           "compute": pred.method.compute, "result_budget": (result.budget if result is not None else None), "prediction": json.loads(pred.to_json()),
           "prediction_common_frame": common}
    fidelity_seeds = args.get("fidelity_seeds")
    if fidelity_seeds:  # oracle-free functional fidelity, computed where the run happened (keep-only in the variant's own frame)
        problem = DiscoveryProblem.from_bundle(variant_dir, network)
        pos_of = {int(i): p for p, i in enumerate(problem.public_ids)}
        core_pos = [pos_of[int(i)] for i in pred.core_ids() if int(i) in pos_of]
        rec["functional_fidelity"] = functional_fidelity(problem, core_pos, list(fidelity_seeds), workers=1)
    if remote:
        shutil.rmtree(variant_dir.parent, ignore_errors=True)
    return rec


def pack_variants(variants: list[Path], network: str) -> dict[str, dict[str, bytes]]:
    return {v.name: pack_bundle(v, network) for v in variants}


# ---------------------------------------------------------------------------- summarising
def consistency(cores: list[list[int]]) -> dict:
    sets = [frozenset(c) for c in cores]
    if not sets:
        return {}
    pair = [len(a & b) / len(a | b) if (a | b) else 1.0 for a, b in combinations(sets, 2)]
    freq: dict[int, int] = {}
    for s in sets:
        for p in s:
            freq[p] = freq.get(p, 0) + 1
    modal = max(set(sets), key=lambda s: sum(1 for t in sets if t == s))
    modal_freq = sum(1 for t in sets if t == modal) / len(sets)
    return {"n_runs": len(sets), "pairwise_jaccard_mean": float(np.mean(pair)) if pair else 1.0,
            "pairwise_jaccard_min": float(np.min(pair)) if pair else 1.0, "modal_core": sorted(modal), "modal_core_frequency": modal_freq,
            "selection_frequency": {int(k): v / len(sets) for k, v in sorted(freq.items(), key=lambda kv: -kv[1])[:30]},
            "size_mean": float(np.mean([len(s) for s in sets])), "size_min": int(min(len(s) for s in sets)), "size_max": int(max(len(s) for s in sets))}


def functional_fidelity(problem: DiscoveryProblem, core_positions: list[int], seeds: list[int], workers: int = 1) -> float:
    if not core_positions:
        return 0.0
    sim = BudgetedSimulator(problem, max_calls=10 ** 9, workers=workers)
    return sim.pass_fraction(keep_only(problem, core_positions), seeds)
