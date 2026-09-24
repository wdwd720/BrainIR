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
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ..sim.model import ModelConfig
from .problem import write_bundle_manifest
from .synthetic import MOTIFS, STIM_CURRENT, BuiltInstance, InstanceSpec, _json_default, _token, build_instance, verify_instance

PAIR_SUITE_ID = "synthetic-pairs-v1"
PAIR_SUITE_ID_V2 = "synthetic-pairs-v2"  # the harder design of review E (hard_pair_specs)
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
    # ---- harder settings (review E finding 5); every default reproduces the v1 design exactly. Their random draws come from a
    # separate stream, so switching one on never changes the draws of the v1 design.
    anchor_count_noise: float = 0.3
    """log-sd of the per-network jitter of a motif node's anchor counts."""
    motif_count_jitter: float = 0.0
    """log-sd of a multiplicative jitter of the synapse counts among motif nodes of network b (a keeps the reference counts)."""
    motif_edge_dropout: float = 0.0
    """probability that a non-critical edge among motif nodes is removed in network b (function re-verified; unverifiable pairs are
    rebuilt)."""
    motif_extra_edges: int = 0
    """weak (5-10 synapse) edges added among motif nodes of network b."""
    structural_decoy: bool = False
    """network b contains a wired copy of its mechanism among distractors (same internal wiring and signs, perturbed copies of the
    members' anchor profiles and annotations); the copy receives no input and has no output outside itself."""
    homologous_background: bool = False
    """distractors of b carry perturbed copies of the anchor profiles and annotations of distinct distractors of a, so anchor
    similarity is no membership signal."""
    blank_hemilineage: bool = False
    """interneuron hemilineage is blank in both networks (as in the real tier-A bundle)."""
    decoy_sign_consistent: bool = False
    """the anchor decoy is chosen among distractors whose sign already equals the copied member's (no sign/wiring inconsistency)."""
    null_family: str | None = None
    """null pair: network b implements this other family with its own independent anchor profiles and annotations; no neuron of a
    has an identity counterpart in b."""

    @property
    def label(self) -> str:
        flags = []
        if self.complications_a or self.complications_b:
            flags.append("c" + "+".join(sorted(set(self.complications_a) | set(self.complications_b))))
        if self.implementation_shift:
            flags.append("shift")
        if self.anchor_decoy:
            flags.append("decoy")
        if self.null_family:
            flags.append(f"null-{self.null_family}")
        if self.motif_count_jitter or self.motif_edge_dropout or self.motif_extra_edges:
            flags.append("wiring")
        if self.structural_decoy:
            flags.append("sdecoy")
        if self.homologous_background:
            flags.append("homolog")
        if self.blank_hemilineage:
            flags.append("nohl")
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
    identities: list[tuple[int, int]] = field(default_factory=list)
    """(canonical node of a, canonical node of b) that are the same neuron: every corresponding mechanism member, and under an
    implementation shift the members of the alternative both networks retain; empty for a null pair."""
    homologs: list[tuple[int, int]] = field(default_factory=list)
    """(a, b) distractor pairs that share a (perturbed) anchor profile and annotations (``homologous_background``)."""
    structural_decoy_b: dict | None = None
    """{"nodes": decoy nodes of b, "copies": the member each one copies} (``structural_decoy``)."""


# ---------------------------------------------------------------------------- anchors and annotations
def _profile(rng: np.random.Generator, n_anchor: int, k_mean: float = 3.0) -> dict[int, float]:
    k = int(np.clip(rng.poisson(k_mean), 1, n_anchor))
    idx = rng.choice(n_anchor, size=k, replace=False)
    return {int(i): float(rng.integers(8, 41)) for i in idx}


def _perturb(rng: np.random.Generator, prof: dict[int, float], n_anchor: int, share: float, sd: float = 0.3) -> dict[int, float]:
    out = {i: max(5.0, round(w * float(np.exp(rng.normal(0, sd))))) for i, w in prof.items() if rng.random() < share}
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
    null = spec.null_family is not None
    if null and spec.null_family == spec.family:
        raise ValueError("a null pair needs a different family in network b")
    inst_a = build_instance(InstanceSpec(spec.family, spec.n_total_a, spec.seed, spec.complications_a, n_readout=spec.n_readout))
    inst_b = build_instance(InstanceSpec(spec.null_family or spec.family, spec.n_total_b, spec.seed + 100_003, spec.complications_b,
                                         n_readout=spec.n_readout))
    m = motif.n
    # shared anchor profiles of the motif nodes (motif node j is canonical node 1 + j in both instances)
    src_prof = {j: _profile(rng, N_SOURCE_ANCHORS) for j in range(m)}
    snk_prof = {j: _profile(rng, N_SINK_ANCHORS) for j in range(m)}
    meta_a = _annotations(rng, inst_a.W.shape[0])
    meta_b = _annotations(rng, inst_b.W.shape[0])
    shift = spec.implementation_shift and len(motif.alternatives) > 1 and not null
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
    anchors_a = _anchor_edges(rng, inst_a, src_prof, snk_prof, spec.anchor_share, m, spec.anchor_count_noise)
    anchors_b = _anchor_edges(rng, inst_b, src_prof, snk_prof, spec.anchor_share, m, spec.anchor_count_noise)
    # annotations: motif nodes agree across the pair up to meta_noise; the driver/readout classes agree exactly
    for j in range(m):
        meta_b.iloc[1 + j] = pd.Series(_noisy_copy(rng, meta_a.iloc[1 + j], spec.meta_noise))
    decoy = None
    if spec.anchor_decoy and not null:
        dis_b = [i for i in range(inst_b.W.shape[0]) if inst_b.node_class[i] == "vnc_intrinsic" and i not in inst_b.motif_nodes]
        j = int(rng.integers(0, m))
        if spec.decoy_sign_consistent:  # a decoy whose own sign already matches: its wiring does not give it away (review E finding 11)
            dis_b = [i for i in dis_b if int(inst_b.signs[i]) == int(inst_a.signs[1 + j])] or dis_b
        d = int(rng.choice(dis_b))
        anchors_b["source"][d] = dict(anchors_b["source"].get(1 + j, {}))
        anchors_b["sink"][d] = dict(anchors_b["sink"].get(1 + j, {}))
        meta_b.iloc[d] = meta_a.iloc[1 + j]
        inst_b.signs[d] = inst_a.signs[1 + j]
        if spec.decoy_sign_consistent:
            inst_b.W[:, d] = inst_b.C[:, d] * int(inst_b.signs[d])
        decoy = {"copies_motif_node": 1 + j, "decoy": d}
    if null:
        corr, role_corr = [], {}
        identities: list[tuple[int, int]] = []
    elif shift:
        identities = [(1 + j, 1 + j) for j in alt_b]  # the alternative both networks retain: same neurons, same wiring
    else:
        identities = list(corr)
    pair = BuiltPair(spec, inst_a, inst_b, anchors_a, anchors_b, meta_a, meta_b, corr, role_corr, decoy, identities=identities)
    _harder_settings(pair, src_prof, snk_prof)
    return pair


def _harder_settings(pair: BuiltPair, src_prof: dict, snk_prof: dict) -> None:
    """Apply the harder settings of ``pair.spec`` (review E finding 5) in place, from a random stream of their own."""
    spec = pair.spec
    rng = np.random.default_rng([int(spec.seed), 20260923])
    a, b = pair.a, pair.b
    if spec.null_family is not None:  # b's own mechanism gets independent anchor profiles and annotations
        pair.anchors_b = _independent_anchors(rng, b, spec.anchor_count_noise)
        pair.meta_b = _annotations(rng, b.W.shape[0])
    if spec.motif_count_jitter > 0:  # b's internal counts differ from a's (a keeps the reference wiring)
        _jitter_motif(rng, b, spec.motif_count_jitter)
    if spec.motif_edge_dropout > 0 or spec.motif_extra_edges > 0:
        _rewire_motif(rng, b, spec.motif_edge_dropout, spec.motif_extra_edges)
    if spec.structural_decoy:
        pair.structural_decoy_b = _structural_decoy(rng, pair)
    if spec.homologous_background:
        pair.homologs = _homologous_background(rng, pair)
    if spec.blank_hemilineage:
        for inst, meta in ((a, pair.meta_a), (b, pair.meta_b)):
            rows = [i for i in range(inst.W.shape[0]) if inst.node_class[i] == "vnc_intrinsic"]
            meta.loc[rows, "hemilineage"] = None


def _live_motif_nodes(inst: BuiltInstance) -> list[int]:
    """Motif nodes that still carry wiring (an implementation shift cuts the dropped alternative's nodes)."""
    return [v for v in inst.motif_nodes if inst.C[v, :].any() or inst.C[:, v].any()]


def _set_count(inst: BuiltInstance, post: int, pre: int, count: float) -> None:
    inst.C[post, pre] = count
    inst.W[post, pre] = count * int(inst.signs[pre])


def _jitter_motif(rng: np.random.Generator, inst: BuiltInstance, sd: float) -> None:
    """Multiply every synapse count on an edge AMONG motif nodes by exp(N(0, sd)) (at least 5). The drive and output edges keep
    their counts, so the mechanism's interface to the stimulus and the readout is unchanged."""
    mot = _live_motif_nodes(inst)
    for i in mot:
        for j in mot:
            if inst.C[i, j] > 0:
                _set_count(inst, i, j, float(max(5.0, round(inst.C[i, j] * float(np.exp(rng.normal(0.0, sd)))))))


def _rewire_motif(rng: np.random.Generator, inst: BuiltInstance, dropout: float, extra: int) -> None:
    """Remove each non-critical edge among motif nodes with probability ``dropout`` (the family's documented critical edges stay);
    add ``extra`` weak edges among them."""
    mot = _live_motif_nodes(inst)
    critical = {(int(post), int(pre)) for pre, post in inst.truth.get("critical_edges", [])}  # stored as (pre, post)
    for i in mot:
        for j in mot:
            if inst.C[i, j] > 0 and (i, j) not in critical and rng.random() < dropout:
                _set_count(inst, i, j, 0.0)
    free = [(i, j) for i in mot for j in mot if i != j and inst.C[i, j] == 0]
    for k in rng.permutation(len(free))[:extra]:
        i, j = free[int(k)]
        _set_count(inst, i, j, float(rng.integers(5, 11)))


def _complication_nodes(inst: BuiltInstance) -> set[int]:
    out: set[int] = set()
    for v in (inst.truth.get("complications") or {}).values():
        if isinstance(v, dict):
            out |= {int(x) for x in v.values() if isinstance(x, (int, np.integer))}
            out |= {int(x) for x in v.get("output_nodes", [])}
        elif isinstance(v, (list, tuple)):
            out |= {int(x) for x in v}
        elif isinstance(v, (int, np.integer)):
            out.add(int(v))
    return out


def _pure_distractors(inst: BuiltInstance, exclude: set[int] = frozenset()) -> list[int]:
    busy = set(inst.motif_nodes) | _complication_nodes(inst) | set(exclude)
    return [i for i in range(inst.W.shape[0]) if inst.node_class[i] == "vnc_intrinsic" and i not in busy]


def _structural_decoy(rng: np.random.Generator, pair: BuiltPair) -> dict | None:
    """A wired copy of b's mechanism among b's distractors: the same internal wiring and signs, perturbed copies of the members'
    anchor profiles and annotations, and no edge to or from the rest of the network (it is never driven and never read out)."""
    spec, b = pair.spec, pair.b
    members = [v for v in _live_motif_nodes(b)]
    taken = {pair.decoy_b["decoy"]} if pair.decoy_b else set()
    pool = _pure_distractors(b, taken)
    if len(pool) < len(members) or not members:
        return None
    nodes = [int(x) for x in rng.choice(pool, size=len(members), replace=False)]
    for d in nodes:  # isolate: no drive, no route to the readout, no background edges
        b.W[d, :] = 0.0; b.W[:, d] = 0.0; b.C[d, :] = 0.0; b.C[:, d] = 0.0
    for x, d in zip(members, nodes):
        b.signs[d] = b.signs[x]
    for x, d in zip(members, nodes):
        for y, e in zip(members, nodes):
            if b.C[x, y] > 0:
                _set_count(b, d, e, float(b.C[x, y]))
    for x, d in zip(members, nodes):
        for kind in ("source", "sink"):
            prof = pair.anchors_b[kind].get(x)
            if prof:
                pair.anchors_b[kind][d] = _perturb(rng, prof, N_SOURCE_ANCHORS if kind == "source" else N_SINK_ANCHORS, spec.anchor_share,
                                                   spec.anchor_count_noise)
            else:
                pair.anchors_b[kind].pop(d, None)
        pair.meta_b.iloc[d] = pd.Series(_noisy_copy(rng, pair.meta_b.iloc[x], spec.meta_noise))
    return {"nodes": nodes, "copies": members}


def _homologous_background(rng: np.random.Generator, pair: BuiltPair) -> list[tuple[int, int]]:
    """Give distractors of b perturbed copies of the anchor profiles and annotations of distinct distractors of a."""
    spec = pair.spec
    taken = set()
    if pair.decoy_b:
        taken.add(pair.decoy_b["decoy"])
    if pair.structural_decoy_b:
        taken |= set(pair.structural_decoy_b["nodes"])
    dis_a = _pure_distractors(pair.a)
    dis_b = _pure_distractors(pair.b, taken)
    order_a = [dis_a[int(k)] for k in rng.permutation(len(dis_a))]
    order_b = [dis_b[int(k)] for k in rng.permutation(len(dis_b))]
    out = []
    for x, y in zip(order_a, order_b):
        for kind, n_anchor in (("source", N_SOURCE_ANCHORS), ("sink", N_SINK_ANCHORS)):
            prof = pair.anchors_a[kind].get(x)
            if prof:
                pair.anchors_b[kind][y] = _perturb(rng, prof, n_anchor, spec.anchor_share, spec.anchor_count_noise)
            else:
                pair.anchors_b[kind].pop(y, None)
        pair.meta_b.iloc[y] = pd.Series(_noisy_copy(rng, pair.meta_a.iloc[x], spec.meta_noise))
        out.append((int(x), int(y)))
    return out


def _independent_anchors(rng: np.random.Generator, inst: BuiltInstance, sd: float) -> dict:
    """Anchor profiles of a network whose mechanism has no counterpart: members get fresh motif-like profiles."""
    source: dict[int, dict[int, float]] = {}
    sink: dict[int, dict[int, float]] = {}
    for i in range(inst.W.shape[0]):
        if inst.node_class[i] != "vnc_intrinsic":
            continue
        if i in inst.motif_nodes:
            source[i] = _perturb(rng, _profile(rng, N_SOURCE_ANCHORS), N_SOURCE_ANCHORS, 1.0, sd)
            sink[i] = _perturb(rng, _profile(rng, N_SINK_ANCHORS), N_SINK_ANCHORS, 1.0, sd)
            continue
        if rng.random() < 0.7:
            source[i] = _profile(rng, N_SOURCE_ANCHORS, 2.0)
        if rng.random() < 0.7:
            sink[i] = _profile(rng, N_SINK_ANCHORS, 2.0)
    return {"source": source, "sink": sink}


def _anchor_edges(rng, inst: BuiltInstance, src_prof, snk_prof, share: float, m: int, sd: float = 0.3) -> dict:
    """Per network: {'source': {node: {anchor: count}}, 'sink': {node: {anchor: count}}} — motif nodes perturbed copies, distractors random."""
    n = inst.W.shape[0]
    source: dict[int, dict[int, float]] = {}
    sink: dict[int, dict[int, float]] = {}
    for j in range(m):
        source[1 + j] = _perturb(rng, src_prof[j], N_SOURCE_ANCHORS, share, sd)
        sink[1 + j] = _perturb(rng, snk_prof[j], N_SINK_ANCHORS, share, sd)
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


def export_pair(pair: BuiltPair, verification: dict, root: Path, *, salt: str = "synthetic-pairs", suite_id: str = PAIR_SUITE_ID) -> dict:
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
        info = {"name": net, "dataset": f"synthetic-{net}", "version": suite_id, "tier": "A", "benchmark_id": suite_id, "n_neurons": n,
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
    manifest = write_bundle_manifest(inst_dir, {"benchmark_id": suite_id, "tier": "A", "instance": label, "created_utc": _now(),
                                                "networks": [{"name": k, "n_neurons": assembled[k]["n"], "n_edges": int(len(assembled[k]["edges"]))}
                                                             for k in nets]})
    inv_a, inv_b = assembled["a"]["inv"], assembled["b"]["inv"]
    truth = {"instance": label, "suite": suite_id, "spec": pair.spec.__dict__ | {"complications_a": list(pair.spec.complications_a),
             "complications_b": list(pair.spec.complications_b)},
             "verification": verification, "networks": nets,
             "correspondence_positions": [[int(inv_a[x]), int(inv_b[y])] for x, y in pair.correspondence],
             "role_correspondence_positions": {r: [[int(inv_a[x]) for x in xs], [int(inv_b[y]) for y in ys]]
                                               for r, (xs, ys) in pair.role_correspondence.items()},
             "decoy_b_positions": (None if pair.decoy_b is None else {"copies_motif_node": int(inv_a[pair.decoy_b["copies_motif_node"]]),
                                                                       "decoy": int(inv_b[pair.decoy_b["decoy"]])}),
             # identity truth for scoring identity claims (review E finding 1): same neuron in both networks
             "identity_positions": [[int(inv_a[x]), int(inv_b[y])] for x, y in pair.identities],
             "homolog_positions": [[int(inv_a[x]), int(inv_b[y])] for x, y in pair.homologs],
             "structural_decoy_b_positions": (None if pair.structural_decoy_b is None else
                                              {"nodes": [int(inv_b[x]) for x in pair.structural_decoy_b["nodes"]],
                                               "copies": [int(inv_b[x]) for x in pair.structural_decoy_b["copies"]]}),
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


BASE_FAMILIES = ("ei_pair_oscillator", "ring_oscillator", "delayed_inhibitory_oscillator", "negative_feedback_controller", "memory_switch",
                 "winner_take_all", "feedforward_driver", "integrator")


def hard_pair_specs() -> list[PairSpec]:
    """The harder pair design of review E (finding 5), suite id ``synthetic-pairs-v2``.

    Every pair has blank interneuron hemilineage (as in the real tier A), weaker and noisier anchors, homologous backgrounds (anchor
    similarity is no membership signal) and jittered synapse counts among the motif nodes of b. Per base family: one pair whose b wiring
    also loses and gains motif edges; one with a structural decoy (a wired, silent copy of b's mechanism carrying the members' anchor
    profiles) plus a sign-consistent anchor decoy; one NULL pair (b implements another family: every identity claim is false).
    Implementation shifts of both alternative families, and large pairs (2,000-2,500 neurons)."""
    hard = dict(anchor_share=0.5, anchor_count_noise=0.6, meta_noise=0.4, motif_count_jitter=0.3, homologous_background=True,
                blank_hemilineage=True)
    specs: list[PairSpec] = []
    seed = 500
    for k, fam in enumerate(BASE_FAMILIES):
        specs.append(PairSpec(fam, 150, 200, seed, motif_edge_dropout=0.15, motif_extra_edges=1, **hard)); seed += 1
        specs.append(PairSpec(fam, 200, 150, seed, ("hub_distractor",), ("misleading_centrality",), structural_decoy=True, anchor_decoy=True,
                              decoy_sign_consistent=True, **hard)); seed += 1
        other = BASE_FAMILIES[(k + 3) % len(BASE_FAMILIES)]
        specs.append(PairSpec(fam, 150, 150, seed, null_family=other, **hard)); seed += 1
    for fam in ("two_implementations", "redundant_oscillator"):
        specs.append(PairSpec(fam, 150, 200, seed, implementation_shift=True, **hard)); seed += 1
        specs.append(PairSpec(fam, 200, 150, seed, implementation_shift=True, structural_decoy=True, **hard)); seed += 1
    for fam in ("ei_pair_oscillator", "ring_oscillator", "negative_feedback_controller", "winner_take_all"):
        specs.append(PairSpec(fam, 2000, 2500, seed, ("hub_distractor", "misleading_centrality"), ("hub_distractor", "autonomous_module"),
                              n_readout=20, structural_decoy=True, **hard)); seed += 1
    return specs
