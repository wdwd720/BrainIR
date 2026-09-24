"""Meaning-preserving perturbations of a bundle-format instance, for anti-gaming checks (goal3 section 33).

Each transform writes a new bundle directory whose mechanism is, by construction, the same as the source's — so a method's
score on the perturbed copy may only differ if the method depends on something that carries no meaning:

    reorder_edges         the rows of edges.parquet are shuffled (graph representation order)
    resalt_tokens         interneuron type tokens are replaced by fresh random tokens (token values are arbitrary)
    strip_annotations     side / soma_neuromere / hemilineage / sub_class of interneurons are blanked (irrelevant annotations removed)
    add_sink_distractors  new neurons appended at the end that only RECEIVE synapses from existing interneurons (they cannot
                          influence any existing neuron, so the mechanism is unchanged while the candidate set grows; readout and
                          stimulus are never touched; per-seed parameter draws are re-indexed because N changes, the ensemble is not)
    widen_parameters      the parameter-distribution sds in model_config.json are scaled (a different but plausible ensemble; this
                          one CAN change marginal behaviour — it tests robustness, not invariance)

Node positions of existing neurons never change, so the source instance's truth applies unchanged (positions of appended
distractors are new and never part of the truth). Node-order permutations are handled by :mod:`brainir.discovery.reliability`.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .correspondence import TOKEN_PREFIX
from .problem import write_bundle_manifest

TRANSFORMS = ("reorder_edges", "resalt_tokens", "strip_annotations", "add_sink_distractors", "widen_parameters")


def _write(df: pd.DataFrame, path: Path) -> None:
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path, compression="zstd")


def _copy(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


def _is_interneuron(neurons: pd.DataFrame) -> np.ndarray:
    ct = neurons["cell_type"].astype("string")
    return ct.str.startswith(TOKEN_PREFIX, na=False).to_numpy()


def perturb_bundle(src: Path | str, dest: Path | str, transform: str, *, seed: int = 0, n_extra: int | None = None, sd_scale: float = 1.5) -> dict:
    """Write a perturbed copy of the bundle at ``src`` (every network in it) to ``dest``; return a description."""
    src, dest = Path(src), Path(dest)
    if transform not in TRANSFORMS:
        raise ValueError(f"unknown transform {transform!r}; known: {TRANSFORMS}")
    _copy(src, dest)
    rng = np.random.default_rng(seed)
    info: dict = {"transform": transform, "seed": seed}
    if transform == "widen_parameters":
        mc_path = dest / "model_config.json"
        mc = json.loads(mc_path.read_text(encoding="utf-8"))
        for k in list(mc["config"]):
            if k.endswith("_sd"):
                mc["config"][k] = float(mc["config"][k]) * sd_scale
        mc_path.write_text(json.dumps(mc, indent=1) + "\n", encoding="utf-8", newline="\n")
        info["sd_scale"] = sd_scale
    for net_dir in sorted(p for p in (dest / "networks").iterdir() if p.is_dir()):
        neurons = pd.read_parquet(net_dir / "neurons.parquet")
        edges = pd.read_parquet(net_dir / "edges.parquet")
        if transform == "reorder_edges":
            edges = edges.iloc[rng.permutation(len(edges))].reset_index(drop=True)
        elif transform == "resalt_tokens":
            inter = _is_interneuron(neurons)
            old = neurons.loc[inter, "cell_type"].astype(str)
            salt = f"{seed}:{rng.integers(1 << 62)}"
            new = {t: TOKEN_PREFIX + hashlib.sha256(f"{salt}|{t}".encode()).hexdigest()[:10] for t in sorted(set(old))}
            neurons.loc[inter, "cell_type"] = old.map(new).to_numpy()
        elif transform == "strip_annotations":
            inter = _is_interneuron(neurons)
            for c in ("side", "soma_neuromere", "hemilineage", "sub_class", "instance"):
                if c in neurons.columns:
                    neurons[c] = neurons[c].astype(object)
                    neurons.loc[inter, c] = None
        elif transform == "add_sink_distractors":
            n = len(neurons)
            k = int(n_extra if n_extra is not None else max(10, n // 5))
            inter_pos = neurons.loc[_is_interneuron(neurons), "position"].to_numpy()
            new_pos = np.arange(n, n + k)
            template = neurons.iloc[[int(inter_pos[0])]].copy()
            rows = pd.concat([template] * k, ignore_index=True)
            rows["position"] = new_pos
            rows["source_id"] = new_pos if (neurons["source_id"].to_numpy() == neurons["position"].to_numpy()).all() else -new_pos - 1
            rows["cell_type"] = [TOKEN_PREFIX + hashlib.sha256(f"sink|{seed}|{i}".encode()).hexdigest()[:10] for i in range(k)]
            rows["sign"] = rng.choice([-1, 1], size=k).astype(neurons["sign"].dtype)
            rows["nt_label"] = np.where(rows["sign"] > 0, "acetylcholine", "gaba")
            rows["is_stimulus"] = False
            rows["is_readout"] = False
            new_edges = []
            for p in new_pos:  # each distractor receives 3-8 synapses-rich inputs from random existing interneurons; sends nothing
                pre = rng.choice(inter_pos, size=int(rng.integers(3, 9)), replace=False)
                for q in pre:
                    cnt = int(rng.integers(5, 40))
                    new_edges.append({"pre_id": int(neurons.loc[int(q), "source_id"]), "post_id": int(rows.loc[int(p - n), "source_id"]),
                                      "pre_position": int(q), "post_position": int(p), "synapse_count": cnt,
                                      "signed_weight": cnt * int(neurons.loc[int(q), "sign"])})
            ne = pd.DataFrame(new_edges).astype({c: edges[c].dtype for c in edges.columns if c in ("pre_position", "post_position")})
            edges = pd.concat([edges, ne], ignore_index=True).sort_values(["pre_position", "post_position"], ignore_index=True)
            rows["in_pairs"] = [int((ne["post_position"] == p).sum()) for p in new_pos]
            rows["out_pairs"] = 0
            counts = ne.groupby("pre_position").size()
            neurons = pd.concat([neurons, rows], ignore_index=True)
            neurons.loc[counts.index, "out_pairs"] = neurons.loc[counts.index, "out_pairs"].to_numpy() + counts.to_numpy()
            info["n_extra"] = k
            nj = json.loads((net_dir / "network.json").read_text(encoding="utf-8"))
            nj["n_neurons"] = int(len(neurons))
            nj["n_edges"] = int(len(edges))
            (net_dir / "network.json").write_text(json.dumps(nj, indent=1) + "\n", encoding="utf-8", newline="\n")
        _write(neurons, net_dir / "neurons.parquet")
        _write(edges, net_dir / "edges.parquet")
    old_manifest = json.loads((src / "manifest.json").read_text(encoding="utf-8")) if (src / "manifest.json").exists() else {}
    header = {k: v for k, v in old_manifest.items() if k not in ("files", "bundle_sha256")}
    header["perturbation"] = {**info, "derived_from_bundle_sha256": old_manifest.get("bundle_sha256")}
    write_bundle_manifest(dest, header)
    return info


def perturb_suite(suite_root: Path | str, out_root: Path | str, transform: str, *, instances: list[str] | None = None, seed: int = 0,
                  **kw) -> list[str]:
    """Perturbed copy of a synthetic suite: every instance transformed, truth files copied unchanged (positions are preserved)."""
    suite_root, out_root = Path(suite_root), Path(out_root)
    names = [p.name for p in sorted((suite_root / "instances").iterdir()) if p.is_dir() and (not instances or p.name in set(instances))]
    (out_root / "truth").mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(names):
        perturb_bundle(suite_root / "instances" / name, out_root / "instances" / name, transform, seed=seed + i, **kw)
        t = suite_root / "truth" / f"{name}.json"
        if t.exists():
            shutil.copyfile(t, out_root / "truth" / f"{name}.json")
    return names


def null_correspondence(problem, other, *, seed: int = 0):
    """A copy of ``problem`` with every piece of CROSS-NETWORK evidence destroyed and every simulation unchanged (review E, the
    null control of joint discovery and transfer).

    The labels ``problem`` shares with ``other`` (anchor types) are permuted among the neurons that carry them; the stimulus and
    readout neurons keep theirs. Hemilineage, soma neuromere and side are shuffled across all rows. W, signs, sizes, stimulus,
    readout, model and criterion are untouched, so the network hash (and every simulation outcome) is identical."""
    import dataclasses

    rng = np.random.default_rng(seed)
    nd = problem.neurons.copy()
    ct = nd["cell_type"].astype(object).to_numpy().copy()
    other_labels = {str(x) for x in other.neurons["cell_type"].dropna().astype(str)}
    fixed = set(int(p) for p in problem.stim_positions) | set(int(p) for p in problem.readout_positions)
    idx = [i for i, t in enumerate(ct) if isinstance(t, str) and not t.startswith(TOKEN_PREFIX) and t in other_labels and i not in fixed]
    vals = [ct[i] for i in idx]
    for i, j in zip(idx, rng.permutation(len(idx))):
        ct[i] = vals[int(j)]
    nd["cell_type"] = ct
    for c in ("hemilineage", "soma_neuromere", "side"):
        if c in nd:
            nd[c] = nd[c].to_numpy()[rng.permutation(len(nd))]
    out = dataclasses.replace(problem, neurons=nd, extra={**problem.extra, "null_correspondence": {"seed": int(seed), "n_permuted": len(idx)}})
    if out.network_hash() != problem.network_hash():
        raise RuntimeError("null_correspondence changed what the simulator sees")
    return out
