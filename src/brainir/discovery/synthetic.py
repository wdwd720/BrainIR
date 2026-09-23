"""Synthetic mechanism-discovery suite: known hidden mechanisms embedded in distracting graphs (goal3 section 7).

Every instance is written in the public-bundle format a discovery method already understands (``model_config.json``,
``networks/<name>/{neurons,edges}.parquet``, ``stimulus.json``, ``readout.json``, ``network.json``, plus
``criterion.json``), and its ground truth — mechanism members, roles, essential members, alternatives, critical edges,
complications — is written SEPARATELY under ``truth/`` so that discovery code never sees it. Ground truth is verified
by simulation at generation time (the intact network and each sufficient set pass the criterion on an ensemble of
parameter draws; essential members are those whose silencing fails it), so it is exact under the simulator, not
merely intended.

Mechanism families (all under the benchmark's rate model and parameter distributions):

    ei_pair_oscillator            E with self-excitation + inhibitory feedback (Wilson-Cowan limit cycle)
    ring_oscillator               three mutually inhibiting neurons under unequal drive + an excitatory output relay
    delayed_inhibitory_oscillator excitatory relay chain closed by one inhibitory neuron
    redundant_oscillator          two independent E-I pairs, either sufficient (alternatives; nothing essential)
    two_implementations           an E-I pair and a ring, both sufficient (different alternative implementations)
    feedforward_driver            relay chain that drives the readout to an activity band
    negative_feedback_controller  driver + inhibitory gain control holding the readout inside a band
    integrator                    near-critical self-excitation: readout ramps up through the window
    memory_switch                 self-sustaining neuron: activity persists after the stimulus pulse ends
    winner_take_all               two competing pools; readout group A active, group B silenced

Complications (flags per instance): hub distractors with strong irrelevant edges (incl. onto the readout), misleading
centrality (a non-causal node on many stimulus->readout paths), backup copies of a core neuron, a weak critical edge,
a low-degree critical neuron, an irrelevant autonomous oscillator module, weight jitter, unknown-sign distractors.
Sizes: small (~50), medium (~500), large (~2,500-4,000). Node positions are randomly permuted; ``order variants``
of the same instance test node-order sensitivity.
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

from ..sim.model import Intervention, ModelConfig, Stimulus, sample_neuron_params, simulate
from .criteria import criterion_from_spec

SUITE_ID = "synthetic-mechanisms-v1"
STIM_CURRENT = 250.0
DN_RATE = 167.5
"""Rate of the stimulated driver neuron at I = 250 (r_max tanh((250 - theta)/r_max)); b * w * DN_RATE = effective current."""
B = 0.03
FAMILIES = ("ei_pair_oscillator", "ring_oscillator", "delayed_inhibitory_oscillator", "redundant_oscillator", "two_implementations",
            "feedforward_driver", "negative_feedback_controller", "integrator", "memory_switch", "winner_take_all")
COMPLICATIONS = ("hub_distractor", "misleading_centrality", "backup_copy", "weak_critical_edge", "low_degree_critical", "autonomous_module",
                 "weight_jitter", "unknown_signs")


def _w_for_current(c: float) -> float:
    """Synapse count from the driver that delivers an effective current c (b * w * DN_RATE = c)."""
    return max(5.0, round(c / (B * DN_RATE)))


@dataclass
class Motif:
    family: str
    W: np.ndarray
    """post x pre signed counts among motif nodes (excitatory columns positive, inhibitory negative)."""
    roles: list[str]
    drive: dict[int, float]
    """motif node -> synapse count from the stimulated driver."""
    output: dict[int, float]
    """motif node -> synapse count onto every readout neuron."""
    alternatives: list[list[int]]
    """sufficient subsets of motif nodes (the first is the canonical core)."""
    critical_edges: list[tuple[int, int]]
    """(pre, post) motif edges whose removal breaks the function (documented, verified where cheap)."""
    criterion: dict
    t_end: float = 1.0
    pulse_end_s: float | None = None
    readout_groups: dict[str, list[int]] | None = None
    """for selectivity: motif output node -> which readout group it drives (group name -> motif nodes)."""
    description: str = ""

    @property
    def n(self) -> int:
        return int(self.W.shape[0])


# ---------------------------------------------------------------------------- motif builders
def _rhythm(**kw) -> dict:
    return {"type": "rhythm", "analysis_start_s": 0.25, "active_rate_hz": 0.01, "prominence": 0.05, "score_threshold": 0.5, "amplitude_min_hz": 0.25, **kw}


def ei_pair_oscillator() -> Motif:
    W = np.array([[100.0, -100.0], [100.0, 0.0]])
    return Motif("ei_pair_oscillator", W, ["recurrent_excitatory_core", "inhibitory_feedback"], drive={0: _w_for_current(250)}, output={0: 30.0},
                 alternatives=[[0, 1]], critical_edges=[(0, 0), (0, 1), (1, 0)], criterion=_rhythm(), t_end=1.0,
                 description="E (self 100) -> I (100) -| E (-100): 11.7 Hz Wilson-Cowan cycle; E drives the readout.")


def ring_oscillator() -> Motif:
    # 0,1,2 inhibitory ring under unequal driver weights; 3 = excitatory output relay driven by the driver, inhibited by ring node 0
    W = np.zeros((4, 4))
    W[1, 0] = W[2, 1] = W[0, 2] = -100.0
    W[3, 0] = -60.0
    return Motif("ring_oscillator", W, ["inhibitory_feedback", "inhibitory_feedback", "inhibitory_feedback", "output_driver"],
                 drive={0: 40.0, 1: 36.0, 2: 32.0, 3: 30.0}, output={3: 30.0}, alternatives=[[0, 1, 2, 3]],
                 critical_edges=[(0, 1), (1, 2), (2, 0), (0, 3)], criterion=_rhythm(), t_end=1.0,
                 description="Repressilator-like inhibitory ring (rotating wave 13.7 Hz) gating an excitatory output relay.")


def delayed_inhibitory_oscillator() -> Motif:
    n = 5
    W = np.zeros((n, n))
    for k in range(1, n):
        W[k, k - 1] = 50.0
    W[0, n - 1] = -100.0
    roles = ["recurrent_excitatory_core", "input_relay", "input_relay", "input_relay", "inhibitory_feedback"]
    return Motif("delayed_inhibitory_oscillator", W, roles, drive={0: _w_for_current(250)}, output={0: 30.0}, alternatives=[list(range(n))],
                 critical_edges=[(k - 1, k) for k in range(1, n)] + [(n - 1, 0)], criterion=_rhythm(), t_end=1.5,
                 description="Excitatory relay chain closed by one inhibitory neuron: 5.7 Hz relaxation cycle.")


def redundant_oscillator() -> Motif:
    a = ei_pair_oscillator().W
    W = np.zeros((4, 4))
    W[:2, :2] = a
    W[2:, 2:] = a
    return Motif("redundant_oscillator", W, ["recurrent_excitatory_core", "inhibitory_feedback", "redundant_backup", "redundant_backup"],
                 drive={0: _w_for_current(250), 2: _w_for_current(250)}, output={0: 30.0, 2: 30.0}, alternatives=[[0, 1], [2, 3]],
                 critical_edges=[], criterion=_rhythm(), t_end=1.0,
                 description="Two independent E-I pairs, each sufficient: no single neuron is essential.")


def two_implementations() -> Motif:
    a = ei_pair_oscillator().W
    r = ring_oscillator().W
    W = np.zeros((6, 6))
    W[:2, :2] = a
    W[2:, 2:] = r
    return Motif("two_implementations", W, ["recurrent_excitatory_core", "inhibitory_feedback", "inhibitory_feedback", "inhibitory_feedback",
                                            "inhibitory_feedback", "output_driver"],
                 drive={0: _w_for_current(250), 2: 40.0, 3: 36.0, 4: 32.0, 5: 30.0}, output={0: 30.0, 5: 30.0},
                 alternatives=[[0, 1], [2, 3, 4, 5]], critical_edges=[], criterion=_rhythm(), t_end=1.0,
                 description="An E-I pair and an inhibitory ring, each a sufficient implementation of the rhythm.")


def feedforward_driver() -> Motif:
    n = 3
    W = np.zeros((n, n))
    for k in range(1, n):
        W[k, k - 1] = 50.0
    return Motif("feedforward_driver", W, ["input_relay", "input_relay", "output_driver"], drive={0: _w_for_current(250)}, output={2: 30.0},
                 alternatives=[list(range(n))], critical_edges=[(0, 1), (1, 2)],
                 criterion={"type": "activity_band", "analysis_start_s": 0.25, "lo_hz": 20.0, "hi_hz": 400.0, "active_rate_hz": 0.01}, t_end=0.8,
                 description="Three-stage excitatory relay chain that drives the readout above 20 Hz.")


def negative_feedback_controller() -> Motif:
    # E (0) drives the readout and I (1); I inhibits E: the loop holds E (and the readout) in a band well below saturation
    W = np.array([[0.0, -100.0], [60.0, 0.0]])
    return Motif("negative_feedback_controller", W, ["output_driver", "gain_control"], drive={0: _w_for_current(250)}, output={0: 30.0},
                 alternatives=[[0, 1]], critical_edges=[(0, 1), (1, 0)],
                 criterion={"type": "activity_band", "analysis_start_s": 0.25, "lo_hz": 5.0, "hi_hz": 60.0, "active_rate_hz": 0.01}, t_end=0.8,
                 description="Driver + inhibitory gain control: without the feedback the readout saturates above the band.")


def integrator() -> Motif:
    # near-critical self-excitation (b*w = 0.96 -> slow approach to the saturating fixed point) on a weak drive: the readout ramps for
    # hundreds of ms (calibrated: relative slope 1.2-2.0 /s over 0.1-0.6 s across parameter draws; threshold 0.6)
    W = np.array([[32.0]])
    return Motif("integrator", W, ["state_memory"], drive={0: 5.0}, output={0: 30.0}, alternatives=[[0]], critical_edges=[(0, 0)],
                 criterion={"type": "ramp", "window_start_s": 0.1, "window_end_s": 0.6, "min_relative_slope": 0.6, "min_rate_hz": 0.5,
                            "active_rate_hz": 0.01}, t_end=0.8,
                 description="Leaky integrator: near-critical self-excitation makes the readout ramp over hundreds of ms.")


def memory_switch() -> Motif:
    # self-excitation above criticality: once switched on by the pulse, activity is self-sustained after the stimulus ends
    W = np.array([[60.0]])
    return Motif("memory_switch", W, ["state_memory"], drive={0: _w_for_current(150)}, output={0: 30.0}, alternatives=[[0]], critical_edges=[(0, 0)],
                 criterion={"type": "persistence", "stimulus_off_s": 0.5, "settle_s": 0.15, "during_start_s": 0.15, "min_fraction": 0.5,
                            "min_rate_hz": 1.0, "active_rate_hz": 0.01}, t_end=1.5, pulse_end_s=0.5,
                 description="Bistable self-exciting neuron: the readout stays active after the 0.5 s stimulus pulse.")


def winner_take_all() -> Motif:
    # excitatory pools A (0) and B (1) compete through dedicated inhibitory interneurons IA (2), IB (3): A -> IA -| B, B -> IB -| A
    # (one sign per neuron, as in the model). A gets the stronger drive and wins; A -> readout group a, B -> readout group b.
    W = np.zeros((4, 4))
    W[2, 0] = 80.0   # A -> IA
    W[3, 1] = 80.0   # B -> IB
    W[1, 2] = -80.0  # IA -| B
    W[0, 3] = -80.0  # IB -| A
    return Motif("winner_take_all", W, ["output_driver", "competitor", "lateral_inhibition", "lateral_inhibition"],
                 drive={0: _w_for_current(120), 1: _w_for_current(90)}, output={0: 30.0, 1: 30.0}, alternatives=[[0, 2]], critical_edges=[(0, 2), (2, 1)],
                 criterion={"type": "selectivity", "analysis_start_s": 0.25, "min_selectivity": 0.8, "min_rate_hz": 1.0, "active_rate_hz": 0.01},
                 t_end=0.8, readout_groups={"a": [0], "b": [1]},
                 description="Competition through inhibitory interneurons: the more strongly driven pool silences the other via its interneuron; "
                             "only readout group A stays active. The mechanism is A plus its interneuron IA (B and IB are the losing side).")


MOTIFS = {f.__name__: f for f in (ei_pair_oscillator, ring_oscillator, delayed_inhibitory_oscillator, redundant_oscillator, two_implementations,
                                  feedforward_driver, negative_feedback_controller, integrator, memory_switch, winner_take_all)}


# ---------------------------------------------------------------------------- instance assembly
@dataclass
class InstanceSpec:
    family: str
    n_total: int
    seed: int
    complications: tuple[str, ...] = ()
    n_readout: int = 12
    density: float = 0.02
    name: str | None = None

    @property
    def label(self) -> str:
        comp = "+".join(self.complications) if self.complications else "plain"
        return self.name or f"{self.family}__n{self.n_total}__{comp}__s{self.seed}"


@dataclass
class BuiltInstance:
    spec: InstanceSpec
    W: np.ndarray            # signed counts post x pre (canonical order: [driver, motif..., readout..., distractors...])
    C: np.ndarray            # unsigned counts
    signs: np.ndarray
    roles: list[str]         # per canonical node
    stim: int
    readout: list[int]
    motif_nodes: list[int]
    truth: dict = field(default_factory=dict)
    criterion: dict = field(default_factory=dict)
    t_end: float = 1.0
    pulse_end_s: float | None = None
    readout_groups: dict[str, list[int]] | None = None
    node_class: list[str] = field(default_factory=list)


def build_instance(spec: InstanceSpec) -> BuiltInstance:
    rng = np.random.default_rng(spec.seed)
    motif = MOTIFS[spec.family]()
    m = motif.n
    n_ro = spec.n_readout
    n_dis = max(0, spec.n_total - 1 - m - n_ro)
    n = 1 + m + n_ro + n_dis
    stim = 0
    motif_nodes = list(range(1, 1 + m))
    readout = list(range(1 + m, 1 + m + n_ro))
    dis = list(range(1 + m + n_ro, n))
    W = np.zeros((n, n))
    signs = np.zeros(n, dtype=np.int8)
    roles = ["input_relay"] + list(motif.roles) + ["output_driver"] * n_ro + ["unknown"] * n_dis
    node_class = ["descending"] + ["vnc_intrinsic"] * m + ["vnc_motor"] * n_ro + ["vnc_intrinsic"] * n_dis
    signs[stim] = 1
    # motif block + signs from the motif columns
    for j in range(m):
        col = motif.W[:, j]
        s = 1 if (col > 0).any() else -1 if (col < 0).any() else 1
        signs[1 + j] = s
        for i in range(m):
            if motif.W[i, j] != 0:
                W[1 + i, 1 + j] = motif.W[i, j]
    for j, w in motif.drive.items():
        W[1 + j, stim] = w
    # readout groups (selectivity): split the readout population between output nodes; otherwise every output node drives all
    groups: dict[str, list[int]] | None = None
    if motif.readout_groups:
        names = list(motif.readout_groups)
        chunks = np.array_split(np.array(readout), len(names))
        groups = {}
        for name, chunk in zip(names, chunks):
            groups[name] = [int(x) for x in chunk]
            for j in motif.readout_groups[name]:
                for r_ in chunk:
                    W[int(r_), 1 + j] = motif.output[j]
    else:
        for j, w in motif.output.items():
            for r_ in readout:
                W[r_, 1 + j] = w
    signs[readout] = 1  # motor neurons: cholinergic, no outputs
    # ---- background distractors: sparse random signed connectivity among distractors, weak inputs to the readout, driver fan-out
    if n_dis:
        dis_arr = np.array(dis)
        signs[dis_arr] = np.where(rng.random(n_dis) < 0.6, 1, -1).astype(np.int8)
        # target mean in-degree ~ density * n_dis but never above ~12 so the background stays in a healthy regime
        p = min(spec.density, 12.0 / max(n_dis, 1))
        mask = rng.random((n_dis, n_dis)) < p
        np.fill_diagonal(mask, False)
        counts = np.exp(rng.normal(np.log(12.0), 0.6, size=(n_dis, n_dis)))
        counts = np.clip(np.round(counts), 5, 60)
        blk = mask * counts * signs[dis_arr][None, :]
        # cap total excitatory input per distractor (b * sum <= 1.2) to avoid runaway
        exc_in = np.where(blk > 0, blk, 0).sum(axis=1)
        scale = np.minimum(1.0, 40.0 / np.maximum(exc_in, 1e-9))
        blk = np.where(blk > 0, blk * scale[:, None], blk)
        blk = np.where(blk != 0, np.sign(blk) * np.maximum(np.abs(np.round(blk)), 5), 0)
        W[np.ix_(dis_arr, dis_arr)] = blk
        # driver fan-out to ~15% of distractors (weights 10-30)
        fan = rng.random(n_dis) < 0.15
        W[dis_arr[fan], stim] = rng.integers(10, 31, size=int(fan.sum()))
        # distractors -> readout: sparse and weak (5-12), both signs
        for r_ in readout:
            src = dis_arr[rng.random(n_dis) < min(0.05, 4.0 / max(n_dis, 1))]
            W[r_, src] = rng.integers(5, 13, size=len(src)) * signs[src]
    # ---- complications
    truth_comp: dict = {}
    if "hub_distractor" in spec.complications and n_dis >= 3:
        hubs = rng.choice(dis, size=min(3, n_dis), replace=False)
        for h in hubs:
            signs[h] = 1
            W[h, stim] = 80.0
            targets = rng.choice([x for x in dis if x != h], size=min(40, n_dis - 1), replace=False)
            W[targets, h] = 50.0
            W[readout, h] = 20.0 if rng.random() < 0.5 else 0.0
        truth_comp["hub_distractor"] = [int(h) for h in hubs]
    if "misleading_centrality" in spec.complications and n_dis >= 1:
        c = int(rng.choice(dis))
        signs[c] = 1
        W[c, stim] = 60.0
        W[readout, c] = 6.0   # on many stimulus->readout paths, negligible effect
        truth_comp["misleading_centrality"] = c
    if "backup_copy" in spec.complications and n_dis >= 1:
        src = 1 + int(rng.integers(0, m))   # a core neuron
        b_ = int(rng.choice(dis))
        W[b_, :] = W[src, :] * 0.5
        W[:, b_] = W[:, src] * 0.5
        W[b_, b_] = W[src, src] * 0.5
        signs[b_] = signs[src]
        W[np.abs(W) < 5] = 0.0
        truth_comp["backup_copy"] = {"of": src, "copy": b_}
    if "weak_critical_edge" in spec.complications:
        # the mechanism's output edges (motif -> readout) become weak (6 synapses, below every distractor edge) while remaining the
        # only route by which the function reaches the readout: a weak edge the whole mechanism depends on
        weak = []
        for j in motif.output:
            col = 1 + j
            tgt = np.flatnonzero(W[readout, col] != 0)
            for k in tgt:
                W[readout[k], col] = np.sign(W[readout[k], col]) * 6.0
            weak.append(col)
        truth_comp["weak_critical_edge"] = {"output_nodes": weak, "count_now": 6.0, "was": {int(1 + j): float(w) for j, w in motif.output.items()}}
    if "autonomous_module" in spec.complications and n_dis >= 4:
        nodes = rng.choice(dis, size=4, replace=False)
        r = ring_oscillator().W  # 4-node ring + relay, driven by the stimulus, connected to nothing else
        W[np.ix_(nodes, nodes)] = r
        for k, wdr in ((0, 40.0), (1, 36.0), (2, 32.0), (3, 30.0)):
            W[nodes[k], stim] = wdr
        signs[nodes[:3]] = -1
        signs[nodes[3]] = 1
        W[:, nodes] = np.where(np.isin(np.arange(n), nodes)[:, None], W[:, nodes], 0.0)  # no outputs outside the module
        truth_comp["autonomous_module"] = [int(x) for x in nodes]
    if "weight_jitter" in spec.complications:
        jit = 1.0 + rng.normal(0, 0.15, size=W.shape)
        W = np.where(W != 0, np.sign(W) * np.maximum(np.abs(np.round(W * jit)), 5), 0.0)
    if "unknown_signs" in spec.complications and n_dis >= 1:
        unk = np.array(dis)[rng.random(n_dis) < 0.1]
        signs[unk] = 0
        truth_comp["unknown_sign_nodes"] = [int(x) for x in unk]
    # low_degree_critical: the motif's inhibitory feedback neuron keeps only its motif edges (already the case) - document
    if "low_degree_critical" in spec.complications:
        inh = [1 + j for j in range(m) if signs[1 + j] < 0]
        truth_comp["low_degree_critical"] = inh
    # sign consistency: every column carries one sign (unknown-sign columns get signed_weight 0 but counts stay)
    C = np.abs(W)
    Ws = np.zeros_like(W)
    for j in range(n):
        Ws[:, j] = C[:, j] * signs[j]
    return BuiltInstance(spec=spec, W=Ws, C=C, signs=signs, roles=roles, stim=stim, readout=readout, motif_nodes=motif_nodes,
                         truth={"family": spec.family, "alternatives": [[1 + j for j in alt] for alt in motif.alternatives],
                                "core": [1 + j for j in motif.alternatives[0]], "roles": {1 + j: motif.roles[j] for j in range(m)},
                                "critical_edges": [(1 + a, 1 + b) for a, b in motif.critical_edges], "complications": truth_comp,
                                "description": motif.description},
                         criterion=dict(motif.criterion), t_end=motif.t_end, pulse_end_s=motif.pulse_end_s, readout_groups=groups,
                         node_class=node_class)


# ---------------------------------------------------------------------------- verification by simulation
def _sim_pass(inst: BuiltInstance, cfg: ModelConfig, seeds: list[int], iv: Intervention | None, readout_mask: np.ndarray, crit) -> list[dict]:
    import scipy.sparse as sp
    W = sp.csr_matrix(inst.W)
    stim = Stimulus((inst.stim,), (STIM_CURRENT,), pulse_end=inst.pulse_end_s)
    sizes = np.full(inst.W.shape[0], 1e9)
    out = []
    for s in seeds:
        params = sample_neuron_params(cfg, W.shape[0], int(s), sizes)
        traj = simulate(W, params, cfg, stim, iv)
        out.append(crit.evaluate(traj, readout_mask))
    return out


def verify_instance(inst: BuiltInstance, seeds: list[int] | None = None) -> dict:
    """Simulation-based truth: intact / keep-only alternatives pass; per-node essentiality by silencing; necessity within the core."""
    seeds = seeds if seeds is not None else list(range(6))
    cfg = ModelConfig(t_end=inst.t_end)
    n = inst.W.shape[0]
    readout_mask = np.zeros(n, bool)
    readout_mask[inst.readout] = True
    crit_spec = dict(inst.criterion)
    if inst.readout_groups:
        crit_spec["group_a_positions"] = inst.readout_groups["a"]
        crit_spec["group_b_positions"] = inst.readout_groups["b"]
    crit = criterion_from_spec(crit_spec)
    always = tuple(sorted({inst.stim, *inst.readout}))

    def frac(iv):
        res = _sim_pass(inst, cfg, seeds, iv, readout_mask, crit)
        return float(np.mean([r["passed"] for r in res])), float(np.mean([r["score"] for r in res]))

    intact_f, intact_s = frac(None)
    alts = []
    for alt in inst.truth["alternatives"]:
        f, s = frac(Intervention(keep_only=tuple(alt), always_keep=always))
        alts.append({"nodes": alt, "keep_only_pass": f, "keep_only_score": s})
    core = inst.truth["core"]
    essential = {}
    necessary_in_core = {}
    for v in sorted(set(x for alt in inst.truth["alternatives"] for x in alt)):
        f_sil, _ = frac(Intervention(silence=(v,)))
        essential[v] = f_sil < 0.2
    for v in core:
        f_wo, _ = frac(Intervention(keep_only=tuple(x for x in core if x != v), always_keep=always))
        necessary_in_core[v] = f_wo < 0.2
    ok = intact_f >= 0.8 and all(a["keep_only_pass"] >= 0.8 for a in alts)
    return {"seeds": seeds, "intact_pass": intact_f, "intact_score": intact_s, "alternatives": alts,
            "essential": {int(k): bool(v) for k, v in essential.items()},
            "necessary_within_core": {int(k): bool(v) for k, v in necessary_in_core.items()}, "criterion": crit_spec, "verified": bool(ok)}


# ---------------------------------------------------------------------------- export
def _token(salt: str, name: str, i: int) -> str:
    return "T#" + hashlib.sha256(f"{salt}|{name}|{i}".encode()).hexdigest()[:10]


def export_instance(inst: BuiltInstance, verification: dict, root: Path, *, n_order_variants: int = 2, salt: str = "synthetic") -> dict:
    """Write the public instance (bundle format) under root/instances/<label>/ and its truth under root/truth/<label>.json."""
    label = inst.spec.label
    inst_dir = root / "instances" / label
    truth_dir = root / "truth"
    inst_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    n = inst.W.shape[0]
    cfg = ModelConfig(t_end=inst.t_end)
    crit_spec = dict(verification["criterion"])
    mc = {"model_id": "brainir.sim.pugliese_rate_v1", "config": cfg.to_dict(),
          "metric": {"score": "criterion.json per network", "analysis_start_s": crit_spec.get("analysis_start_s", 0.25), "active_rate_hz": 0.01,
                     "prominence": 0.05, "rhythmic_threshold": 0.5},
          "parameter_distributions": "truncated normals, see ModelConfig fields *_mean/*_sd; size scaling a/s, theta*s (all sizes equal here)"}
    (inst_dir / "model_config.json").write_text(json.dumps(mc, indent=1) + "\n", encoding="utf-8", newline="\n")
    rng = np.random.default_rng(inst.spec.seed + 7919)
    variants = {}
    files = {}
    for v in range(n_order_variants):
        perm = np.arange(n) if v == 0 and False else rng.permutation(n)  # every variant is a random order (canonical order never exposed)
        # perm[p] = canonical node at public position p
        inv = np.empty(n, dtype=np.int64)
        inv[perm] = np.arange(n)
        name = "main" if v == 0 else f"order{v}"
        d = inst_dir / "networks" / name
        d.mkdir(parents=True, exist_ok=True)
        Wp = inst.W[np.ix_(perm, perm)]
        Cp = inst.C[np.ix_(perm, perm)]
        signs = inst.signs[perm]
        roles_cls = np.array(inst.node_class)[perm]
        is_stim = np.zeros(n, bool); is_stim[inv[inst.stim]] = True
        is_ro = np.zeros(n, bool); is_ro[inv[inst.readout]] = True
        cell_type = [("DNsyn" if is_stim[p] else "MNsyn" if is_ro[p] else _token(salt, label, int(perm[p]))) for p in range(n)]
        pre_idx, post_idx = np.nonzero(Cp.T)  # Cp[post, pre] -> iterate pre-major
        pre_idx, post_idx = post_idx, pre_idx
        # recompute properly: nonzero of Cp gives (post, pre)
        post_idx, pre_idx = np.nonzero(Cp)
        counts = Cp[post_idx, pre_idx]
        signed = Wp[post_idx, pre_idx]
        out_pairs = np.bincount(pre_idx, minlength=n); in_pairs = np.bincount(post_idx, minlength=n)
        neurons = pd.DataFrame({"position": np.arange(n), "source_id": np.arange(n), "cell_type": cell_type, "instance": [None] * n,
                                "super_class": ["descending_neuron" if c == "descending" else "motor_neuron" if c == "vnc_motor" else "intrinsic_neuron"
                                                for c in roles_cls],
                                "sub_class": ["fl" if is_ro[p] else None for p in range(n)], "role_class": roles_cls, "side": ["L"] * n,
                                "soma_neuromere": ["T1"] * n, "hemilineage": [None] * n,
                                "nt_label": ["acetylcholine" if s > 0 else "gaba" if s < 0 else "unknown" for s in signs], "sign": signs.astype(np.int8),
                                "size_voxels": np.full(n, 1e9), "is_stimulus": is_stim, "is_readout": is_ro,
                                "out_pairs": out_pairs.astype(np.int64), "in_pairs": in_pairs.astype(np.int64)})
        edges = pd.DataFrame({"pre_id": pre_idx.astype(np.int64), "post_id": post_idx.astype(np.int64), "pre_position": pre_idx.astype(np.int32),
                              "post_position": post_idx.astype(np.int32), "synapse_count": counts.astype(np.int32),
                              "signed_weight": signed.astype(np.int32)})
        edges = edges.sort_values(["pre_position", "post_position"], ignore_index=True)
        pq.write_table(pa.Table.from_pandas(neurons, preserve_index=False), d / "neurons.parquet", compression="zstd")
        pq.write_table(pa.Table.from_pandas(edges, preserve_index=False), d / "edges.parquet", compression="zstd")
        stim_json = {"cell_type": "DNsyn", "source_ids": [int(inv[inst.stim])], "positions": [int(inv[inst.stim])], "current": STIM_CURRENT,
                     "pulse_start_s": cfg.pulse_start, "pulse_end_s": inst.pulse_end_s, "rule": "the synthetic driver neuron",
                     "id_semantics": "positional (tier A)"}
        ro_json = {"rule": "synthetic readout population (motor neurons)", "n": len(inst.readout), "source_ids": [int(inv[r]) for r in inst.readout],
                   "positions": sorted(int(inv[r]) for r in inst.readout)}
        crit = dict(crit_spec)
        if inst.readout_groups:
            crit["group_a_positions"] = sorted(int(inv[r]) for r in inst.readout_groups["a"])
            crit["group_b_positions"] = sorted(int(inv[r]) for r in inst.readout_groups["b"])
        (d / "stimulus.json").write_text(json.dumps(stim_json, indent=1) + "\n", encoding="utf-8", newline="\n")
        (d / "readout.json").write_text(json.dumps(ro_json, indent=1) + "\n", encoding="utf-8", newline="\n")
        (d / "criterion.json").write_text(json.dumps(crit, indent=1) + "\n", encoding="utf-8", newline="\n")
        info = {"name": name, "dataset": "synthetic", "version": SUITE_ID, "tier": "A", "benchmark_id": SUITE_ID, "n_neurons": n,
                "n_edges": int(len(edges)),
                "total_synapses": int(counts.sum()), "floor": 5, "remove_autapses": False, "sign_rule": "synthetic (one sign per column)",
                "sign_basis": "synthetic", "orientation": "edges.parquet lists pre -> post; W[post, pre] = signed_weight (post x pre) for the model",
                "id_semantics": "positional (tier A)", "order_variant": v}
        (d / "network.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8", newline="\n")
        variants[name] = {"perm": [int(x) for x in perm], "core_positions": sorted(int(inv[c]) for c in inst.truth["core"]),
                          "alternatives_positions": [sorted(int(inv[c]) for c in alt) for alt in inst.truth["alternatives"]],
                          "roles_positions": {int(inv[k]): r for k, r in inst.truth["roles"].items()},
                          "essential_positions": {int(inv[k]): v_ for k, v_ in verification["essential"].items()},
                          "necessary_within_core_positions": {int(inv[k]): v_ for k, v_ in verification["necessary_within_core"].items()},
                          "critical_edges_positions": [[int(inv[a]), int(inv[b])] for a, b in inst.truth["critical_edges"]],
                          "complication_positions": _remap(inst.truth["complications"], inv), "stimulus_position": int(inv[inst.stim]),
                          "readout_positions": sorted(int(inv[r]) for r in inst.readout)}
        for f in ("neurons.parquet", "edges.parquet", "stimulus.json", "readout.json", "criterion.json", "network.json"):
            files[f"networks/{name}/{f}"] = hashlib.sha256((d / f).read_bytes()).hexdigest()
    files["model_config.json"] = hashlib.sha256((inst_dir / "model_config.json").read_bytes()).hexdigest()
    manifest = {"benchmark_id": SUITE_ID, "format_version": "1.0.0", "tier": "A", "instance": label, "created_utc": _now(),
                "networks": [{"name": k, "n_neurons": n, "n_edges": int(inst.C.astype(bool).sum())} for k in variants], "files": files}
    manifest["bundle_sha256"] = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    (inst_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    truth = {"instance": label, "suite": SUITE_ID, "spec": {"family": inst.spec.family, "n_total": inst.spec.n_total, "seed": inst.spec.seed,
             "complications": list(inst.spec.complications), "n_readout": inst.spec.n_readout, "density": inst.spec.density},
             "description": inst.truth["description"], "verification": verification, "networks": variants, "bundle_sha256": manifest["bundle_sha256"]}
    (truth_dir / f"{label}.json").write_text(json.dumps(truth, indent=1, default=_json_default) + "\n", encoding="utf-8", newline="\n")
    return {"instance": label, "dir": str(inst_dir), "verified": verification["verified"], "n": n, "bundle_sha256": manifest["bundle_sha256"]}


def _remap(comp: dict, inv: np.ndarray) -> dict:
    out = {}
    for k, v in comp.items():
        if isinstance(v, list):
            out[k] = [int(inv[x]) for x in v]
        elif isinstance(v, dict):
            out[k] = {kk: (int(inv[vv]) if kk in ("of", "copy", "pre", "post") else vv) for kk, vv in v.items()}
        elif isinstance(v, (int, np.integer)):
            out[k] = int(inv[v])
        else:
            out[k] = v
    return out


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_specs() -> list[InstanceSpec]:
    """The v1 suite: every family at small size (plain + complications), medium and large sizes for a subset."""
    specs: list[InstanceSpec] = []
    seed = 0
    for fam in FAMILIES:
        specs.append(InstanceSpec(fam, 50, seed)); seed += 1
        specs.append(InstanceSpec(fam, 60, seed, ("hub_distractor", "misleading_centrality"))); seed += 1
        specs.append(InstanceSpec(fam, 60, seed, ("weight_jitter", "unknown_signs"))); seed += 1
    for fam in ("ei_pair_oscillator", "delayed_inhibitory_oscillator", "redundant_oscillator", "two_implementations", "negative_feedback_controller",
                "memory_switch", "winner_take_all"):
        specs.append(InstanceSpec(fam, 60, seed, ("backup_copy",))); seed += 1
        specs.append(InstanceSpec(fam, 60, seed, ("weak_critical_edge", "low_degree_critical"))); seed += 1
        specs.append(InstanceSpec(fam, 60, seed, ("autonomous_module",))); seed += 1
    for fam in FAMILIES:
        specs.append(InstanceSpec(fam, 500, seed, ("hub_distractor", "misleading_centrality", "autonomous_module"), n_readout=20)); seed += 1
    for fam in ("ei_pair_oscillator", "ring_oscillator", "two_implementations", "negative_feedback_controller", "winner_take_all"):
        specs.append(InstanceSpec(fam, 3000, seed, ("hub_distractor", "misleading_centrality", "backup_copy", "autonomous_module"), n_readout=40,
                                  density=0.004)); seed += 1
    return specs
