"""Synthetic cross-connectome pairs: the same mechanism family embedded in two independently generated networks.

The two networks of a pair ("a" and "b") play the roles of two connectomes: different distractor backgrounds, different
interneuron tokens, different node orders, but a shared mechanism family whose members correspond one-to-one (or, with
``implementation_shift``, only at the level of roles). What can be compared across them is exactly what the public
blind benchmark offers: **labelled anchors** shared by both networks (the driver ``DNsyn``, the readout ``MNsyn``, silent
source anchors ``SRC#k`` and output-only sink anchors ``SNK#k``) and coarse annotations (``hemilineage``,
``soma_neuromere``, ``side``, ``sign``). Anchor edges are dynamically inert (source anchors receive no input and stay
silent; sink anchors have no outputs), so they change the correspondence problem, never the mechanism.

Each motif node carries an anchor profile drawn once and copied into both networks with per-network perturbation
(``anchor_share`` of its anchor edges survive, counts jittered, spurious edges added); distractors get independent
random profiles; annotations agree across the pair with probability ``1 - meta_noise``. Truth (member correspondence,
role correspondence, per-network cores/alternatives/roles/essentials) is stored separately under ``truth/``.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ..sim.model import ModelConfig
from .synthetic import MOTIFS, STIM_CURRENT, BuiltInstance, InstanceSpec, _json_default, _token, build_instance, verify_instance

PAIR_SUITE_ID = "synthetic-pairs-v1"
N_SOURCE_ANCHORS = 15
N_SINK_ANCHORS = 15
HEMILINEAGES = [f"HL{k:02d}" for k in range(10)]
NEUROMERES = ["T1", "T2", "T3"]


@dataclass
class PairSpec:
    family: str
    n_total_a: int
    n_total_b: int
    seed: int
    complications_a: tuple[str, ...] = ()
    complications_b: tuple[str, ...] = ()
    anchor_share: float = 0.8
    """probability that a motif node's anchor edge survives in each network."""
    meta_noise: float = 0.3
    """probability that an annotation of a motif node disagrees between the networks (or is missing in one)."""
    implementation_shift: bool = False
    """network b implements the family's second alternative when the family has one (role-level correspondence only)."""
    anchor_decoy: bool = False
    """network b contains a distractor that copies a motif node's anchor profile and annotations."""
    n_readout: int = 12
    name: str | None = None

    @property
    def label(self) -> str:
        flags = []
        if self.complications_a or self.complications_b:
            flags.append("c" + "+".join(sorted(set(self.complications_a) | set(self.complications_b))))
        if self.implementation_shift:
            flags.append("shift")
        if self.anchor_decoy:
            flags.append("decoy")
        return self.name or f"pair__{self.family}__n{self.n_total_a}x{self.n_total_b}__{'_'.join(flags) or 'plain'}__s{self.seed}"


@dataclass
class BuiltPair:
    spec: PairSpec
    a: BuiltInstance
    b: BuiltInstance
    anchors_a: dict = field(default_factory=dict)
    anchors_b: dict = field(default_factory=dict)
    meta_a: pd.DataFrame | None = None
    meta_b: pd.DataFrame | None = None
    correspondence: list[tuple[int, int]] = field(default_factory=list)
    """(canonical node of a, canonical node of b) for corresponding mechanism members (empty under implementation_shift)."""
    role_correspondence: dict[str, tuple[list[int], list[int]]] = field(default_factory=dict)
    decoy_b: dict | None = None


# ---------------------------------------------------------------------------- anchors and annotations
def _profile(rng: np.random.Generator, n_anchor: int, k_mean: float = 3.0) -> dict[int, float]:
    k = int(np.clip(rng.poisson(k_mean), 1, n_anchor))
    idx = rng.choice(n_anchor, size=k, replace=False)
    return {int(i): float(rng.integers(8, 41)) for i in idx}


def _perturb(rng: np.random.Generator, prof: dict[int, float], n_anchor: int, share: float) -> dict[int, float]:
    out = {i: max(5.0, round(w * float(np.exp(rng.normal(0, 0.3))))) for i, w in prof.items() if rng.random() < share}
    if rng.random() < 0.5:
        extra = int(rng.integers(0, n_anchor))
        out.setdefault(extra, float(rng.integers(8, 41)))
    return out


def _annotations(rng: np.random.Generator, n: int) -> pd.DataFrame:
    return pd.DataFrame({"hemilineage": rng.choice(HEMILINEAGES, size=n), "soma_neuromere": rng.choice(NEUROMERES, size=n, p=[0.6, 0.25, 0.15]),
                         "side": rng.choice(["L", "R"], size=n)})


def _noisy_copy(rng: np.random.Generator, row: pd.Series, noise: float) -> dict:
    out = {}
    for c, pool in (("hemilineage", HEMILINEAGES), ("soma_neuromere", NEUROMERES), ("side", ["L", "R"])):
        if rng.random() < noise:
            out[c] = None if rng.random() < 0.5 else str(rng.choice([p for p in pool if p != row[c]]))
        else:
            out[c] = row[c]
    return out


def build_pair(spec: PairSpec) -> BuiltPair:
    rng = np.random.default_rng(spec.seed * 7 + 12345)
    motif = MOTIFS[spec.family]()
    inst_a = build_instance(InstanceSpec(spec.family, spec.n_total_a, spec.seed, spec.complications_a, n_readout=spec.n_readout))
    inst_b = build_instance(InstanceSpec(spec.family, spec.n_total_b, spec.seed + 100_003, spec.complications_b, n_readout=spec.n_readout))
    m = motif.n
    # shared anchor profiles of the motif nodes (motif node j is canonical node 1 + j in both instances)
    src_prof = {j: _profile(rng, N_SOURCE_ANCHORS) for j in range(m)}
    snk_prof = {j: _profile(rng, N_SINK_ANCHORS) for j in range(m)}
    meta_a = _annotations(rng, inst_a.W.shape[0])
    meta_b = _annotations(rng, inst_b.W.shape[0])
    shift = spec.implementation_shift and len(motif.alternatives) > 1
    # under an implementation shift the b network keeps only the second alternative's nodes as the mechanism
    alt_b = motif.alternatives[1] if shift else motif.alternatives[0]
    corr: list[tuple[int, int]] = []
    role_corr: dict[str, tuple[list[int], list[int]]] = {}
    for j in range(m):
        in_b = (j in alt_b) if shift else True
        if not shift:
            corr.append((1 + j, 1 + j))
        r = motif.roles[j]
        role_corr.setdefault(r, ([], []))
        role_corr[r][0].append(1 + j)
        if in_b:
            role_corr[r][1].append(1 + j)
    if shift:
        # remove the first alternative's exclusive nodes from b (they become plain distractors with no motif edges)
        drop = [1 + j for j in motif.alternatives[0] if j not in alt_b]
        for v in drop:
            inst_b.W[v, :] = 0.0; inst_b.W[:, v] = 0.0; inst_b.C[v, :] = 0.0; inst_b.C[:, v] = 0.0
        inst_b.truth["alternatives"] = [[1 + j for j in alt_b]]
        inst_b.truth["core"] = [1 + j for j in alt_b]
        inst_b.truth["roles"] = {1 + j: motif.roles[j] for j in alt_b}
        inst_b.roles = [("unknown" if (i in drop) else r) for i, r in enumerate(inst_b.roles)]
    anchors_a = _anchor_edges(rng, inst_a, src_prof, snk_prof, spec.anchor_share, m)
    anchors_b = _anchor_edges(rng, inst_b, src_prof, snk_prof, spec.anchor_share, m)
    # annotations: motif nodes agree across the pair up to meta_noise; the driver/readout classes agree exactly
    for j in range(m):
        meta_b.iloc[1 + j] = pd.Series(_noisy_copy(rng, meta_a.iloc[1 + j], spec.meta_noise))
    decoy = None
    if spec.anchor_decoy:
        dis_b = [i for i in range(inst_b.W.shape[0]) if inst_b.node_class[i] == "vnc_intrinsic" and i not in inst_b.motif_nodes]
        j = int(rng.integers(0, m))
        d = int(rng.choice(dis_b))
        anchors_b["source"][d] = dict(anchors_b["source"].get(1 + j, {}))
        anchors_b["sink"][d] = dict(anchors_b["sink"].get(1 + j, {}))
        meta_b.iloc[d] = meta_a.iloc[1 + j]
        inst_b.signs[d] = inst_a.signs[1 + j]
        decoy = {"copies_motif_node": 1 + j, "decoy": d}
    return BuiltPair(spec, inst_a, inst_b, anchors_a, anchors_b, meta_a, meta_b, corr, role_corr, decoy)


def _anchor_edges(rng, inst: BuiltInstance, src_prof, snk_prof, share: float, m: int) -> dict:
    """Per network: {'source': {node: {anchor: count}}, 'sink': {node: {anchor: count}}} — motif nodes perturbed copies, distractors random."""
    n = inst.W.shape[0]
    source: dict[int, dict[int, float]] = {}
    sink: dict[int, dict[int, float]] = {}
    for j in range(m):
        source[1 + j] = _perturb(rng, src_prof[j], N_SOURCE_ANCHORS, share)
        sink[1 + j] = _perturb(rng, snk_prof[j], N_SINK_ANCHORS, share)
    for i in range(n):
        if inst.node_class[i] != "vnc_intrinsic" or i in inst.motif_nodes:
            continue
        if rng.random() < 0.7:
            source[i] = _profile(rng, N_SOURCE_ANCHORS, 2.0)
        if rng.random() < 0.7:
            sink[i] = _profile(rng, N_SINK_ANCHORS, 2.0)
    return {"source": source, "sink": sink}


# ---------------------------------------------------------------------------- verification
def verify_pair(pair: BuiltPair, seeds: list[int] | None = None) -> dict:
    va = verify_instance(pair.a, seeds)
    vb = verify_instance(pair.b, seeds)
    return {"a": va, "b": vb, "verified": bool(va["verified"] and vb["verified"])}


# ---------------------------------------------------------------------------- export
def _assemble(inst: BuiltInstance, anchors: dict, meta: pd.DataFrame, rng: np.random.Generator, salt: str, label: str, net: str) -> dict:
    """Full node set of one network = instance nodes + anchor nodes; returns permuted public tables plus the permutation."""
    n0 = inst.W.shape[0]
    n_src, n_snk = N_SOURCE_ANCHORS, N_SINK_ANCHORS
    n = n0 + n_src + n_snk
    W = np.zeros((n, n)); C = np.zeros((n, n))
    W[:n0, :n0] = inst.W; C[:n0, :n0] = inst.C
    signs = np.zeros(n, dtype=np.int8); signs[:n0] = inst.signs
    src0, snk0 = n0, n0 + n_src
    signs[src0:src0 + n_src] = 1; signs[snk0:snk0 + n_snk] = 1
    for node, prof in anchors["source"].items():
        for k, w in prof.items():
            C[node, src0 + k] = w; W[node, src0 + k] = w  # source anchors are excitatory, silent (no input)
    for node, prof in anchors["sink"].items():
        for k, w in prof.items():
            C[snk0 + k, node] = w; W[snk0 + k, node] = w * int(signs[node] if signs[node] != 0 else 0)
    node_class = list(inst.node_class) + ["descending"] * n_src + ["ascending"] * n_snk
    cell_type_canon = ["DNsyn" if i == inst.stim else "MNsyn" if i in set(inst.readout) else None for i in range(n0)]
    cell_type_canon += [f"SRC#{k:02d}" for k in range(n_src)] + [f"SNK#{k:02d}" for k in range(n_snk)]
    hemi = list(meta["hemilineage"]) + [None] * (n_src + n_snk)
    neuromere = list(meta["soma_neuromere"]) + ["T1"] * (n_src + n_snk)
    side = list(meta["side"]) + list(rng.choice(["L", "R"], size=n_src + n_snk))
    perm = rng.permutation(n)
    inv = np.empty(n, dtype=np.int64); inv[perm] = np.arange(n)
    Wp, Cp = W[np.ix_(perm, perm)], C[np.ix_(perm, perm)]
    sp_ = signs[perm]
    is_stim = np.zeros(n, bool); is_stim[inv[inst.stim]] = True
    is_ro = np.zeros(n, bool); is_ro[inv[inst.readout]] = True
    cls = [node_class[perm[p]] for p in range(n)]
    ctype = [cell_type_canon[perm[p]] or _token(salt, f"{label}/{net}", int(perm[p])) for p in range(n)]
    post_idx, pre_idx = np.nonzero(Cp)
    neurons = pd.DataFrame({"position": np.arange(n), "source_id": np.arange(n), "cell_type": ctype, "instance": [None] * n,
                            "super_class": [{"descending": "descending_neuron", "vnc_motor": "motor_neuron", "ascending": "ascending_neuron"}
                                            .get(c, "intrinsic_neuron") for c in cls],
                            "sub_class": ["fl" if is_ro[p] else None for p in range(n)], "role_class": cls,
                            "side": [side[perm[p]] for p in range(n)], "soma_neuromere": [neuromere[perm[p]] for p in range(n)],
                            "hemilineage": [hemi[perm[p]] for p in range(n)],
                            "nt_label": ["acetylcholine" if s > 0 else "gaba" if s < 0 else "unknown" for s in sp_], "sign": sp_.astype(np.int8),
                            "size_voxels": np.full(n, 1e9), "is_stimulus": is_stim, "is_readout": is_ro,
                            "out_pairs": np.bincount(pre_idx, minlength=n).astype(np.int64),
                            "in_pairs": np.bincount(post_idx, minlength=n).astype(np.int64)})
    edges = pd.DataFrame({"pre_id": pre_idx.astype(np.int64), "post_id": post_idx.astype(np.int64), "pre_position": pre_idx.astype(np.int32),
                          "post_position": post_idx.astype(np.int32), "synapse_count": Cp[post_idx, pre_idx].astype(np.int32),
                          "signed_weight": Wp[post_idx, pre_idx].astype(np.int32)}).sort_values(["pre_position", "post_position"], ignore_index=True)
    return {"neurons": neurons, "edges": edges, "perm": perm, "inv": inv, "n": n}


def export_pair(pair: BuiltPair, verification: dict, root: Path, *, salt: str = "synthetic-pairs") -> dict:
    """Write root/instances/<label>/networks/{a,b}/ (+ model_config, manifest) and root/truth/<label>.json."""
    label = pair.spec.label
    inst_dir = root / "instances" / label
    truth_dir = root / "truth"
    inst_dir.mkdir(parents=True, exist_ok=True); truth_dir.mkdir(parents=True, exist_ok=True)
    cfg = ModelConfig(t_end=pair.a.t_end)
    mc = {"model_id": "brainir.sim.pugliese_rate_v1", "config": cfg.to_dict(),
          "metric": {"score": "criterion.json per network", "analysis_start_s": 0.25, "active_rate_hz": 0.01, "prominence": 0.05,
                     "rhythmic_threshold": 0.5},
          "parameter_distributions": "truncated normals, see ModelConfig fields *_mean/*_sd; size scaling a/s, theta*s (all sizes equal here)"}
    (inst_dir / "model_config.json").write_text(json.dumps(mc, indent=1) + "\n", encoding="utf-8", newline="\n")
    rng = np.random.default_rng(pair.spec.seed + 4242)
    nets: dict[str, dict] = {}
    files: dict[str, str] = {}
    assembled = {}
    parts = (("a", pair.a, pair.anchors_a, pair.meta_a, verification["a"]), ("b", pair.b, pair.anchors_b, pair.meta_b, verification["b"]))
    for net, inst, anchors, meta, ver in parts:
        asm = _assemble(inst, anchors, meta, rng, salt, label, net)
        assembled[net] = asm
        inv, n = asm["inv"], asm["n"]
        d = inst_dir / "networks" / net
        d.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pandas(asm["neurons"], preserve_index=False), d / "neurons.parquet", compression="zstd")
        pq.write_table(pa.Table.from_pandas(asm["edges"], preserve_index=False), d / "edges.parquet", compression="zstd")
        stim_json = {"cell_type": "DNsyn", "source_ids": [int(inv[inst.stim])], "positions": [int(inv[inst.stim])], "current": STIM_CURRENT,
                     "pulse_start_s": cfg.pulse_start, "pulse_end_s": inst.pulse_end_s, "rule": "the synthetic driver neuron",
                     "id_semantics": "positional (tier A)"}
        ro_json = {"rule": "synthetic readout population (motor neurons)", "n": len(inst.readout), "source_ids": [int(inv[r]) for r in inst.readout],
                   "positions": sorted(int(inv[r]) for r in inst.readout)}
        crit = dict(ver["criterion"])
        if inst.readout_groups:
            crit["group_a_positions"] = sorted(int(inv[r]) for r in inst.readout_groups["a"])
            crit["group_b_positions"] = sorted(int(inv[r]) for r in inst.readout_groups["b"])
        (d / "stimulus.json").write_text(json.dumps(stim_json, indent=1) + "\n", encoding="utf-8", newline="\n")
        (d / "readout.json").write_text(json.dumps(ro_json, indent=1) + "\n", encoding="utf-8", newline="\n")
        (d / "criterion.json").write_text(json.dumps(crit, indent=1) + "\n", encoding="utf-8", newline="\n")
        info = {"name": net, "dataset": f"synthetic-{net}", "version": PAIR_SUITE_ID, "tier": "A", "benchmark_id": PAIR_SUITE_ID, "n_neurons": n,
                "n_edges": int(len(asm["edges"])), "total_synapses": int(asm["edges"]["synapse_count"].sum()), "floor": 5, "remove_autapses": False,
                "sign_rule": "synthetic (one sign per column)", "sign_basis": "synthetic",
                "orientation": "edges.parquet lists pre -> post; W[post, pre] = signed_weight (post x pre) for the model",
                "id_semantics": "positional (tier A)",
                "anchors": "labelled SRC#/SNK#/DNsyn/MNsyn neurons are shared across the pair; interneuron tokens are not"}
        (d / "network.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8", newline="\n")
        nets[net] = {"perm": [int(x) for x in asm["perm"]], "core_positions": sorted(int(inv[c]) for c in inst.truth["core"]),
                     "alternatives_positions": [sorted(int(inv[c]) for c in alt) for alt in inst.truth["alternatives"]],
                     "roles_positions": {int(inv[k]): r for k, r in inst.truth["roles"].items()},
                     "essential_positions": {int(inv[k]): v for k, v in ver["essential"].items()},
                     "necessary_within_core_positions": {int(inv[k]): v for k, v in ver["necessary_within_core"].items()},
                     "stimulus_position": int(inv[inst.stim]), "readout_positions": sorted(int(inv[r]) for r in inst.readout),
                     "n_instance_nodes": int(inst.W.shape[0]), "n_anchor_nodes": N_SOURCE_ANCHORS + N_SINK_ANCHORS}
        for f in ("neurons.parquet", "edges.parquet", "stimulus.json", "readout.json", "criterion.json", "network.json"):
            files[f"networks/{net}/{f}"] = hashlib.sha256((d / f).read_bytes()).hexdigest()
    files["model_config.json"] = hashlib.sha256((inst_dir / "model_config.json").read_bytes()).hexdigest()
    manifest = {"benchmark_id": PAIR_SUITE_ID, "format_version": "1.0.0", "tier": "A", "instance": label, "created_utc": _now(),
                "networks": [{"name": k, "n_neurons": assembled[k]["n"], "n_edges": int(len(assembled[k]["edges"]))} for k in nets], "files": files}
    manifest["bundle_sha256"] = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    (inst_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    inv_a, inv_b = assembled["a"]["inv"], assembled["b"]["inv"]
    truth = {"instance": label, "suite": PAIR_SUITE_ID, "spec": pair.spec.__dict__ | {"complications_a": list(pair.spec.complications_a),
             "complications_b": list(pair.spec.complications_b)},
             "verification": verification, "networks": nets,
             "correspondence_positions": [[int(inv_a[x]), int(inv_b[y])] for x, y in pair.correspondence],
             "role_correspondence_positions": {r: [[int(inv_a[x]) for x in xs], [int(inv_b[y]) for y in ys]]
                                               for r, (xs, ys) in pair.role_correspondence.items()},
             "decoy_b_positions": (None if pair.decoy_b is None else {"copies_motif_node": int(inv_a[pair.decoy_b["copies_motif_node"]]),
                                                                       "decoy": int(inv_b[pair.decoy_b["decoy"]])}),
             "bundle_sha256": manifest["bundle_sha256"]}
    (truth_dir / f"{label}.json").write_text(json.dumps(truth, indent=1, default=_json_default) + "\n", encoding="utf-8", newline="\n")
    return {"instance": label, "dir": str(inst_dir), "verified": verification["verified"], "bundle_sha256": manifest["bundle_sha256"]}


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_pair_specs() -> list[PairSpec]:
    specs: list[PairSpec] = []
    seed = 0
    for fam in ("ei_pair_oscillator", "ring_oscillator", "delayed_inhibitory_oscillator", "negative_feedback_controller", "memory_switch",
                "winner_take_all", "feedforward_driver", "integrator"):
        specs.append(PairSpec(fam, 60, 80, seed)); seed += 1
        specs.append(PairSpec(fam, 60, 80, seed, meta_noise=0.6, anchor_share=0.6)); seed += 1
        specs.append(PairSpec(fam, 80, 60, seed, ("hub_distractor",), ("misleading_centrality", "backup_copy"), anchor_decoy=True)); seed += 1
    for fam in ("two_implementations", "redundant_oscillator"):
        specs.append(PairSpec(fam, 60, 80, seed)); seed += 1
        specs.append(PairSpec(fam, 60, 80, seed, implementation_shift=True)); seed += 1
    for fam in ("ei_pair_oscillator", "ring_oscillator", "negative_feedback_controller", "winner_take_all"):
        specs.append(PairSpec(fam, 500, 600, seed, ("hub_distractor", "misleading_centrality"), ("hub_distractor", "autonomous_module"), n_readout=20,
                              anchor_decoy=True)); seed += 1
    return specs
