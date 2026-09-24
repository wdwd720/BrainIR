"""Adversarial synthetic suite (review G): generic traps that make a mechanism-discovery method confident and wrong, plus a scorer.

Every instance starts from a public-generator instance (:func:`brainir.discovery.synthetic.build_instance`: background and planted
motif) into which a TRAP is wired from repurposed background neurons. Every numeric trap parameter is drawn from the instance seed
inside a documented range (:data:`PARAM_RANGES`), so a fresh seed gives a genuinely different instance; ``AdversarialSpec.knobs`` can
pin any parameter (the draw still happens, so pinning one parameter never shifts the others). :func:`verify_adversarial` checks the
trap's defining properties by simulation and records the measured truth (essential nodes, silencing pass fractions, intact firing
rates, intact pass rate). :func:`export_adversarial` writes the public bundle exactly like :func:`synthetic.export_instance`
(node-order variants ``main``, ``order1``; the public files are indistinguishable in format from the regular synthetic suite) with the
truth under ``root/truth/`` only. :func:`score_adversarial` scores a discovery result against the trap truth.

Traps (``TRAPS``; variants in ``VARIANTS``; design note: research/phase2/reviews/G_adversarial_suite.md)

    latent_backup      a keep-only-sufficient backup that the intact network keeps silent behind an inhibitory gate driven by the planted
                       mechanism; silencing the planted mechanism releases the backup, which takes over (compensation). The backup is
                       smaller than the planted mechanism, so a simplicity preference favours it.
    masked_gate        an inhibitory gate S, essential alone, holds a disruptor relay X silent. X's stimulus-driven (optionally
                       recurrent) drivers D make S unnecessary when they are silenced together with it, so group silencing can clear S.
    distributed_drive  no compact mechanism: N weak parallel relays of which a fraction q is needed; the relays are exchangeable
                       (identical variant) or nearly so (jittered variant).
    subset_of_draws    the function exists on a subset of parameter draws only: c exchangeable marginal copies of a motif, none of
                       which is sufficient on most draws.
    identical_decoy    a structural copy of the planted motif (with a few extra synapses of drive) kept silent by a gate that a latch,
                       switched on by the planted motif, holds on.
    fragile_vs_robust  a smaller implementation that is sufficient on only part of the draws next to a robust larger one that the
                       intact network relies on.

Truth (``inst.truth["adversarial"]`` in canonical nodes; ``truth["networks"][name]["adversarial"]`` in public positions after export)

    mechanism          the set(s) the intact network actually uses: the designed set joined with every measured-essential node
    acceptable         the cores that count as correct (exact match): the designed core joined with every measured-essential node
                       (DEFINITION; the designed sets stay in ``acceptable_designed`` / ``mechanism_designed``); empty for
                       distributed_drive (no compact core exists)
    essential          nodes whose single silencing breaks the intact function (measured: silencing pass fraction <= FAIL_MAX)
    latent_backups     keep-only-sufficient sets that the intact network does not use; ``silent_members`` = their silent nodes
    degenerate         {"flag", "min_set_size", "fraction_needed", "membership_frequency"} (distributed_drive)
    subset_of_draws    {"flag", "intact_pass", "copy_keep_only_pass", "union_keep_only_pass"} (subset_of_draws)
    contested          the named trap nodes {name: node}; ``targets`` gives each one's membership target for calibration
    exchangeable       groups of functionally interchangeable nodes (their probabilities should be equal)

The module imports no method and reads no benchmark data. It is truth-bearing: method code must not import it.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import scipy.sparse as sp

from ..sim.model import Intervention, ModelConfig, Stimulus, sample_neuron_params, simulate
from .criteria import criterion_from_spec
from .synthetic import STIM_CURRENT, BuiltInstance, InstanceSpec, build_instance, export_instance

SUITE_ID = "synthetic-adversarial-v1"
TRAPS = ("latent_backup", "masked_gate", "distributed_drive", "subset_of_draws", "identical_decoy", "fragile_vs_robust")
VARIANTS: dict[str, dict[str, str]] = {
    # variant -> base family of the public generator (background, planted motif, criterion)
    "latent_backup": {"band": "feedforward_driver", "band_overlap": "feedforward_driver", "band_active_head": "feedforward_driver",
                      "rhythm_delayed": "delayed_inhibitory_oscillator", "rhythm_ring": "ring_oscillator"},
    "masked_gate": {"nfc_band": "negative_feedback_controller", "ffd_band": "feedforward_driver", "ei_rhythm": "ei_pair_oscillator",
                    "dio_rhythm": "delayed_inhibitory_oscillator", "integrator_ramp": "integrator", "memory_persistence": "memory_switch",
                    "wta_selectivity": "winner_take_all"},
    "distributed_drive": {"identical": "feedforward_driver", "jittered": "feedforward_driver"},
    "subset_of_draws": {"latch_persistence": "memory_switch", "ei_rhythm": "ei_pair_oscillator"},
    "identical_decoy": {"ei_rhythm": "ei_pair_oscillator", "nfc_band": "negative_feedback_controller", "memory_persistence": "memory_switch",
                        "ffd_band": "feedforward_driver"},
    "fragile_vs_robust": {"two_impl_rhythm": "two_implementations", "band": "feedforward_driver"},
}
PARAM_RANGES: dict[str, dict[str, tuple]] = {
    # ("int", lo, hi) inclusive synapse counts; ("real", lo, hi); ("choice", options). Every range is drawn per instance seed.
    "latent_backup": {
        "backup_size": ("choice", (1, 2)),         # band: backup neurons (head -> [relay] -> readout)
        "backup_drive": ("int", 40, 60),           # stimulus -> backup head
        "backup_relay": ("int", 45, 60),           # head -> relay (two-neuron backups)
        "backup_out": ("int", 25, 35),             # backup output -> each readout neuron (overlap: -> the shared planted member)
        "gate_source": ("choice", "planted excitatory members (variant-specific subset)"),
        "gate_in": ("int", 40, 60),                # planted member (or latch) -> gate
        "gate_out": ("int", 120, 200),             # gate -| each gated backup neuron
        "latch_in": ("int", 50, 70),               # rhythm: planted member -> latch
        "latch_self": ("int", 58, 70),             # rhythm: latch self-excitation (bistable)
        "decoy_self": ("int", 95, 105), "decoy_ei": ("int", 95, 105), "decoy_ie": ("int", 95, 105),  # rhythm: E-I backup
        "decoy_drive": ("int", 46, 54), "decoy_out": ("int", 25, 35),
    },
    "masked_gate": {
        "n_drivers": ("choice", (1, 2, 3)),
        "driver_rec_on": ("choice", (False, True, True)),  # recurrent drivers with probability 2/3 (always for persistence)
        "driver_rec": ("choice+int", (0, 40, 70)),    # recurrence count: 40-70 (persistence 55-70), 0 when driver_rec_on is False
        "driver_drive": ("int", 50, 70),           # stimulus -> each driver
        "driver_to_x": ("int", 30, 50),            # each driver -> relay X
        "gate_drive": ("int", 50, 70),             # stimulus -> gate S
        "gate_factor": ("real", 1.4, 2.2),         # S -| X = round(gate_factor * n_drivers * driver_to_x)
        "x_out": ("int", 30, 60),                  # X -> its target (readout, +/-; readout group b; the motif inhibitor; the latch)
        "gate_from_latch": ("int", 50, 70),        # persistence: latch -> S (keeps S on after the pulse)
    },
    "distributed_drive": {
        "n_relays": ("int", 12, 32),               # capped by the available background neurons
        "relay_drive": ("int", 5, 8),              # stimulus -> each relay
        "relay_out": ("int", 5, 7),                # each relay -> each readout neuron
        "jitter": ("real", 0.1, 0.35),             # jittered variant: relative sd of relay_out (identical variant: 0)
        "fraction_needed": ("real", 0.5, 0.8),     # lo is calibrated so that about this fraction of the relays is needed
    },
    "subset_of_draws": {
        "copies": ("choice", (2, 3)),
        "latch_self": ("int", 36, 37),             # latch_persistence: marginal self-excitation (bistable on part of the draws)
        "ei_self": ("int", 42, 46),                # ei_rhythm: marginal E self-excitation (limit cycle on part of the draws)
    },
    "identical_decoy": {
        "extra_drive": ("int", 0, 12),             # extra stimulus synapses of the decoy's driven members (ei_rhythm: 0-5)
        "gate_source": ("choice", "planted excitatory members"),
        "gate_in": ("int", 40, 60), "gate_out": ("int", 120, 200), "latch_in": ("int", 50, 70), "latch_self": ("int", 58, 70),
    },
    "fragile_vs_robust": {
        "fragile_self": ("int", 46, 53),           # two_impl_rhythm: E self-excitation of the fragile E-I pair
        "fragile_drive": ("int", 40, 60),          # band: stimulus -> fragile relay
        "fragile_out": ("int", 12, 20),            # band: fragile relay -> each readout neuron (dominates the background's readout input)
        "target_pass": ("real", 0.4, 0.7),         # band: lo calibrated so that the network without the chain passes on this fraction
    },
}
PASS_MIN = 0.8        # "works": pass fraction >= PASS_MIN over the verification seeds
FAIL_MAX = 0.2        # "breaks": pass fraction <= FAIL_MAX (also the essential threshold, as in synthetic.verify_instance)
SILENT_HZ = 0.05      # "silent": median over seeds of the mean rate in the analysis window <= SILENT_HZ
ACTIVE_HZ = 1.0       # "active" / participating: median mean rate >= ACTIVE_HZ
CONFIDENT_P = 0.85    # a core is "confident" when every member has inclusion probability >= CONFIDENT_P
VERIFY_SEEDS = tuple(range(8))
CALIBRATION_SEEDS = tuple(range(1000, 1012))  # builder-side threshold calibration (distributed_drive, fragile_vs_robust band)
SCORE_SEEDS = tuple(range(5500, 5508))        # scorer default: outside every method namespace (< 5000) and the tournament's 5000-5003
DEGENERATE_FLAGS = ("degenerate", "distributed", "no_compact_mechanism")
DEFINITION = "acceptable-contains-essential/v2"
"""Truth definition: every acceptable core and every mechanism set contains every measured-essential node (single-silencing pass
<= FAIL_MAX), whatever its role in the trap; essential nodes are membership targets 1. Exported truths from before this rule carry no
``definition`` field; :func:`normalize_truth_network` migrates them and :func:`score_adversarial` applies it to every truth it scores."""
_SALT = {"variant": 11, "params": 23, "nodes": 37, "calibration": 41}


# ---------------------------------------------------------------------------------------------------------------- specification
@dataclass
class AdversarialSpec:
    trap: str
    family: str | None = None
    """Trap variant (a key of ``VARIANTS[trap]``, which fixes the base family and criterion); None: drawn from the seed."""
    n_total: int = 60
    seed: int = 0
    n_readout: int = 12
    density: float = 0.02
    knobs: dict = field(default_factory=dict)
    """Pinned trap parameters {name: value} (names as in PARAM_RANGES); every other parameter is drawn from the seed."""
    complications: tuple[str, ...] = ()
    """Background complications of the public generator; they may add sufficient sets that the adversarial truth does not list."""
    name: str | None = None
    """Label override (use an anonymised token for held-out suites: the default label names the trap and the seed)."""

    def __post_init__(self):
        if self.trap not in TRAPS:
            raise ValueError(f"unknown trap {self.trap!r}; known: {TRAPS}")
        if self.family is not None and self.family not in VARIANTS[self.trap]:
            raise ValueError(f"unknown variant {self.family!r} of {self.trap}; known: {sorted(VARIANTS[self.trap])}")
        if int(self.seed) < 0:
            raise ValueError("seed must be >= 0")

    @property
    def variant(self) -> str:
        if self.family is not None:
            return self.family
        opts = sorted(VARIANTS[self.trap])
        return opts[int(np.random.default_rng([int(self.seed), _SALT["variant"]]).integers(len(opts)))]

    @property
    def base_family(self) -> str:
        return VARIANTS[self.trap][self.variant]

    @property
    def label(self) -> str:
        return self.name or f"adv__{self.trap}__{self.variant}__n{self.n_total}__s{self.seed}"


class _Draw:
    """Seeded parameter draws in a fixed order; a pinned knob replaces the drawn value after the draw (other draws do not shift)."""

    def __init__(self, spec: AdversarialSpec):
        self.rng = np.random.default_rng([int(spec.seed), _SALT["params"]])
        self.knobs = dict(spec.knobs or {})
        self.params: dict = {}

    def _set(self, name: str, v):
        if name in self.knobs:
            v = self.knobs[name]
        self.params[name] = v
        return v

    def int(self, name: str, lo: int, hi: int) -> int:
        return self._set(name, int(self.rng.integers(int(lo), int(hi) + 1)))

    def real(self, name: str, lo: float, hi: float) -> float:
        return self._set(name, round(float(self.rng.uniform(lo, hi)), 3))

    def choice(self, name: str, options):
        options = list(options)
        return self._set(name, options[int(self.rng.integers(len(options)))])


# ---------------------------------------------------------------------------------------------------------------- building
def _base(spec: AdversarialSpec) -> BuiltInstance:
    return build_instance(InstanceSpec(spec.base_family, int(spec.n_total), int(spec.seed), tuple(spec.complications), n_readout=int(spec.n_readout),
                                       density=float(spec.density)))


def _complication_nodes(inst: BuiltInstance) -> set[int]:
    out: set[int] = set()
    for v in (inst.truth.get("complications") or {}).values():
        if isinstance(v, list):
            out |= {int(x) for x in v}
        elif isinstance(v, dict):
            out |= {int(x) for k, x in v.items() if k in ("of", "copy")}
        elif isinstance(v, (int, np.integer)):
            out.add(int(v))
    return out


class _Builder:
    def __init__(self, spec: AdversarialSpec):
        self.spec = spec
        self.inst = _base(spec)
        self.D = _Draw(spec)
        self.rng_nodes = np.random.default_rng([int(spec.seed), _SALT["nodes"]])
        self.used: set[int] = set(_complication_nodes(self.inst))
        self.C = self.inst.C  # unsigned counts (post x pre); the signed matrix is rebuilt from it at the end
        self.signs: dict[int, int] = {}
        self.roles: dict[int, str] = {}

    @property
    def stim(self) -> int:
        return int(self.inst.stim)

    @property
    def readout(self) -> list[int]:
        return [int(r) for r in self.inst.readout]

    def background(self) -> list[int]:
        first = 1 + len(self.inst.motif_nodes) + len(self.inst.readout)
        return [x for x in range(first, self.inst.W.shape[0]) if x not in self.used]

    def take(self, k: int) -> list[int]:
        pool = self.background()
        if len(pool) < k:
            raise ValueError(f"n_total={self.spec.n_total} is too small: the trap needs {k} background neurons, {len(pool)} are free")
        pick = [int(x) for x in self.rng_nodes.choice(pool, size=k, replace=False)]
        for p in pick:
            self.clear(p)
        self.used |= set(pick)
        return pick

    def clear(self, p: int) -> None:
        self.C[p, :] = 0.0
        self.C[:, p] = 0.0

    def edge(self, post, pre, w) -> None:
        """Synapse count pre -> post (magnitude; the presynaptic sign is applied at the end)."""
        posts = post if isinstance(post, (list, tuple, np.ndarray)) else [post]
        for q in posts:
            self.C[int(q), int(pre)] = float(max(0, round(float(w))))

    def core0(self) -> list[int]:
        return [int(x) for x in self.inst.truth["alternatives"][0]]

    def excitatory(self, nodes) -> list[int]:
        return [int(p) for p in nodes if self.inst.signs[int(p)] > 0]

    def inhibitory(self, nodes) -> list[int]:
        return [int(p) for p in nodes if self.inst.signs[int(p)] < 0]

    def to_readout(self, nodes) -> list[int]:
        ro = self.readout
        return [int(p) for p in nodes if (self.C[ro, int(p)] > 0).any()]

    def finish(self, adv: dict, *, alternatives: list[list[int]], description: str) -> BuiltInstance:
        inst = self.inst
        for p, s in self.signs.items():
            inst.signs[p] = s
        inst.C = self.C
        inst.W = self.C * inst.signs[None, :].astype(np.float64)
        roles = {int(k): v for k, v in (inst.truth.get("roles") or {}).items() if k in set(adv.get("_keep_roles", inst.motif_nodes))}
        roles.update(self.roles)
        for p, r in roles.items():
            inst.roles[p] = r
        adv.pop("_keep_roles", None)
        spec = self.spec
        adv = {"suite": SUITE_ID, "trap": spec.trap, "variant": spec.variant, "base_family": spec.base_family, "params": dict(self.D.params),
               "latent_backups": [], "silent_members": [], "fragile_alternatives": [], "exchangeable": [],
               "degenerate": {"flag": False}, "subset_of_draws": {"flag": False}, **adv}
        adv["acceptable_designed"] = [sorted(map(int, a)) for a in adv["acceptable"]]  # before the essential rule (verify_adversarial)
        adv["mechanism_designed"] = [sorted(map(int, a)) for a in adv["mechanism"]]
        adv.setdefault("targets", {})
        for p in {p for a in adv["acceptable"] for p in a} | {p for a in adv["mechanism"] for p in a}:
            adv["targets"].setdefault(int(p), 1.0)
        for p in adv["contested"].values():
            adv["targets"].setdefault(int(p), 0.0)
        adv["essential"] = sorted(int(p) for p in adv.get("essential_designed", []))
        inst.truth = {"family": f"{spec.trap}:{spec.variant}", "alternatives": [sorted(map(int, a)) for a in alternatives],
                      "core": sorted(map(int, alternatives[0])), "roles": roles, "critical_edges": [],
                      "complications": inst.truth.get("complications", {}), "description": description, "adversarial": adv}
        inst.spec = InstanceSpec(f"{spec.trap}:{spec.variant}", int(spec.n_total), int(spec.seed), tuple(spec.complications),
                                 n_readout=int(spec.n_readout), density=float(spec.density), name=spec.label)
        return inst


def _named(prefix: str, nodes) -> dict[str, int]:
    return {f"{prefix}{k}": int(p) for k, p in enumerate(nodes)}


def _latent_backup(b: _Builder) -> BuiltInstance:
    v, D = b.spec.variant, b.D
    m = b.core0()
    exc = b.excitatory(m)
    contested = _named("m", m)
    checks: list[dict] = [_ck("intact", "intact_pass", [], ">=", PASS_MIN), _ck("planted_sufficient", "keep_only_pass", m, ">=", PASS_MIN)]
    if v.startswith("band"):
        size = D.choice("backup_size", (1, 2)) if v == "band" else (2 if v == "band_active_head" else 1)
        drive, relay_w, out = D.int("backup_drive", 40, 60), D.int("backup_relay", 45, 60), D.int("backup_out", 25, 35)
        last = b.to_readout(m)  # the planted output member(s)
        # overlap: the shared output member must stay free to be driven by the backup, so it cannot drive the gate
        sources = [p for p in exc if p not in last] if v == "band_overlap" else exc
        src = sources[int(D.choice("gate_source", range(len(sources))))]
        gate_in, gate_out = D.int("gate_in", 40, 60), D.int("gate_out", 120, 200)
        G = b.take(1)[0]
        b.edge(G, src, gate_in)
        b.signs[G], b.roles[G] = -1, "gain_control"
        if v == "band_overlap":
            (H,) = b.take(1)
            b.edge(H, b.stim, drive)
            b.edge(last, H, out)          # the backup drives the planted output member
            b.edge(H, G, gate_out)
            backup, silent = sorted([H, *last]), [H]
        else:
            nodes = b.take(size)
            b.edge(nodes[0], b.stim, drive)
            for pre, post in zip(nodes[:-1], nodes[1:]):
                b.edge(post, pre, relay_w)
            b.edge(b.readout, nodes[-1], out)
            if v == "band_active_head":   # the head stays active (ungated); only its relay is gated
                b.edge(nodes[-1], G, gate_out)
                silent = [nodes[-1]]
                checks.append(_ck("head_active", "active", [nodes[0]], ">=", ACTIVE_HZ))
            else:
                b.edge(nodes[0], G, gate_out)
                silent = list(nodes)
            backup = sorted(nodes)
        for p in backup:
            if p not in m:
                b.signs[p], b.roles[p] = 1, "redundant_backup"
        contested.update(_named("backup", [p for p in backup if p not in m]))
        contested["gate"] = G
        distinct = [p for p in m if p not in backup]
        checks += [_ck("backup_sufficient", "keep_only_pass", backup, ">=", PASS_MIN), _ck("backup_silent", "silent", silent, "<=", SILENT_HZ),
                   _ck("compensation", "silence_pass", distinct, ">=", PASS_MIN)]
        desc = "planted relay chain; a smaller backup kept silent by a gate that the chain drives; silencing the chain releases it"
    else:  # rhythm: a 2-neuron E-I backup behind a gate driven by a latch that a planted excitatory member switches on
        src = exc[int(D.choice("gate_source", range(len(exc))))]
        latch_in, latch_self = D.int("latch_in", 50, 70), D.int("latch_self", 58, 70)
        gate_in, gate_out = D.int("gate_in", 40, 60), D.int("gate_out", 120, 200)
        ds, dei, die = D.int("decoy_self", 95, 105), D.int("decoy_ei", 95, 105), D.int("decoy_ie", 95, 105)
        ddrive, dout = D.int("decoy_drive", 46, 54), D.int("decoy_out", 25, 35)
        Eb, Ib, L, G = b.take(4)
        b.edge(Eb, Eb, ds); b.edge(Ib, Eb, dei); b.edge(Eb, Ib, die); b.edge(Eb, b.stim, ddrive); b.edge(b.readout, Eb, dout)
        b.edge(L, src, latch_in); b.edge(L, L, latch_self); b.edge(G, L, gate_in); b.edge(Eb, G, gate_out); b.edge(Ib, G, gate_out)
        b.signs.update({Eb: 1, Ib: -1, L: 1, G: -1})
        b.roles.update({Eb: "redundant_backup", Ib: "redundant_backup", L: "modulatory_supporting", G: "gain_control"})
        backup, silent = [Eb, Ib], [Eb, Ib]
        contested.update({"backup_E": Eb, "backup_I": Ib, "latch": L, "gate": G})
        checks += [_ck("backup_sufficient", "keep_only_pass", backup, ">=", PASS_MIN), _ck("backup_silent", "silent", silent, "<=", SILENT_HZ),
                   _ck("compensation", "silence_pass", m, ">=", PASS_MIN)]
        desc = "planted oscillator; an E-I backup kept silent by a latched gate that the oscillator switches on; silencing it releases the backup"
    adv = {"mechanism": [m], "acceptable": [m], "latent_backups": [sorted(backup)], "silent_members": sorted(silent), "contested": contested,
           "checks": checks, "essential_designed": []}
    return b.finish(adv, alternatives=[m], description=desc)


def _masked_gate(b: _Builder) -> BuiltInstance:
    v, D = b.spec.variant, b.D
    m_all = [int(x) for x in b.inst.motif_nodes]
    core = b.core0()
    persistence = v == "memory_persistence"
    k = int(D.choice("n_drivers", (1, 2, 3)))
    rec_on = D.choice("driver_rec_on", (False, True, True)) or persistence
    rec = D.int("driver_rec", 55 if persistence else 40, 70)
    if not rec_on:
        rec = D._set("driver_rec", 0)
    drive, dx, gdrive = D.int("driver_drive", 50, 70), D.int("driver_to_x", 30, 50), D.int("gate_drive", 50, 70)
    factor, xo = D.real("gate_factor", 1.4, 2.2), D.int("x_out", 30, 60)
    g_latch = D.int("gate_from_latch", 50, 70)
    drivers = b.take(k)
    X, S = b.take(2)
    for d in drivers:
        b.edge(d, b.stim, drive)
        b.edge(X, d, dx)
        b.signs[d], b.roles[d] = 1, "unknown"
    if rec:
        if k == 1:
            b.edge(drivers[0], drivers[0], rec)
        else:
            for d in drivers:
                for e in drivers:
                    if d != e:
                        b.edge(d, e, rec)
    b.edge(S, b.stim, gdrive)
    b.edge(X, S, round(factor * k * dx))
    # X's target and sign: overdrive the readout (upper band edge, ramp slope), silence the readout (lower band edge), activate the
    # losing readout group, drive the rhythm's inhibitor tonically, or inhibit the latch after the pulse
    target_kind, x_sign = {"nfc_band": ("readout", 1), "ffd_band": ("readout", -1), "ei_rhythm": ("inhibitor", 1), "dio_rhythm": ("inhibitor", 1),
                           "integrator_ramp": ("readout", 1), "memory_persistence": ("latch", -1), "wta_selectivity": ("readout_b", 1)}[v]
    if target_kind == "readout":
        targets = b.readout
    elif target_kind == "readout_b":
        targets = [int(r) for r in b.inst.readout_groups["b"]]
    elif target_kind == "inhibitor":
        targets = b.inhibitory(core)
    else:  # the self-exciting member (latch); the gate also listens to it so that it stays on after the pulse
        targets = [p for p in core if b.C[p, p] > 0]
        for p in targets:
            b.edge(S, p, g_latch)
    b.edge(targets, X, xo)
    b.signs.update({X: x_sign, S: -1})
    b.roles.update({X: "unknown", S: "gain_control"})
    acceptable = sorted(core + [S])
    contested = {**_named("m", m_all), "gate": S, "relay": X, **_named("driver", drivers)}
    checks = [_ck("intact", "intact_pass", [], ">=", PASS_MIN), _ck("mechanism_sufficient", "keep_only_pass", acceptable, ">=", PASS_MIN),
              _ck("relay_silent", "silent", [X], "<=", SILENT_HZ), _ck("gate_essential", "silence_pass", [S], "<=", FAIL_MAX),
              _ck("masking", "silence_pass", [S, *drivers], ">=", PASS_MIN)]
    adv = {"mechanism": [acceptable], "acceptable": [acceptable], "silent_members": [X], "contested": contested, "checks": checks,
           "essential_designed": [S]}
    desc = f"planted {b.spec.base_family}; an inhibitory gate holds a disruptor relay silent; the relay's drivers mask the gate when silenced with it"
    return b.finish(adv, alternatives=[acceptable], description=desc)


def _distributed_drive(b: _Builder) -> BuiltInstance:
    D = b.D
    for p in b.inst.motif_nodes:  # this instance has no compact mechanism: the planted chain is removed
        b.clear(int(p))
    n_avail = len(b.background())
    n_rel = D.int("n_relays", 12, 32)
    n_rel = int(min(n_rel, max(4, n_avail - 2)))
    D.params["n_relays"] = n_rel
    w_in, w_out, q = D.int("relay_drive", 5, 8), D.int("relay_out", 5, 7), D.real("fraction_needed", 0.5, 0.8)
    jitter = D.real("jitter", 0.1, 0.35)
    if b.spec.variant == "identical":
        jitter = D._set("jitter", 0.0)
    relays = b.take(n_rel)
    outs = {}
    for r in relays:
        w = w_out if jitter == 0 else max(5, round(w_out * (1.0 + jitter * float(b.rng_nodes.normal()))))
        outs[r] = int(w)
        b.edge(r, b.stim, w_in)
        b.edge(b.readout, r, w)
        b.signs[r], b.roles[r] = 1, "output_driver"
    k_star = int(max(2, round(q * n_rel)))
    # calibrate the criterion: lo = median keep-only readout mean with k_star relays (random subsets, calibration seeds)
    inst = b.finish({"mechanism": [relays], "acceptable": [], "contested": {}, "checks": [], "_keep_roles": []}, alternatives=[relays], description="")
    crng = np.random.default_rng([int(b.spec.seed), _SALT["calibration"]])
    means = []
    for s in CALIBRATION_SEEDS[:6]:
        sub = [int(x) for x in crng.choice(relays, size=k_star, replace=False)]
        means.append(_simulate(inst, s, _ko(inst, sub))["readout_mean_hz"])
    lo = round(float(np.median(means)), 3)
    inst.criterion = {**inst.criterion, "lo_hz": lo}
    D.params["lo_hz"] = lo
    few = sorted(relays, key=lambda r: -outs[r])[: max(2, round(0.6 * k_star))]  # the strongest 60 % of the needed number
    checks = [_ck("intact", "intact_pass", [], ">=", PASS_MIN), _ck("all_relays_sufficient", "keep_only_pass", relays, ">=", PASS_MIN),
              _ck("no_compact_subset", "keep_only_pass", few, "<=", FAIL_MAX)]
    checks += [_ck(f"relay_not_essential_{k}", "silence_pass", [r], ">=", PASS_MIN) for k, r in enumerate(relays[:3])]
    identical = jitter == 0
    adv = inst.truth["adversarial"]
    adv.update({"contested": _named("relay", relays), "checks": checks, "params": dict(D.params),
                "degenerate": {"flag": True, "min_set_size": k_star, "fraction_needed": q,
                               "membership_frequency": {int(r): round(k_star / n_rel, 4) for r in relays} if identical else None},
                "exchangeable": [sorted(relays)] if identical else [], "relay_out": {int(r): outs[r] for r in relays},
                "targets": {int(r): (round(k_star / n_rel, 4) if identical else None) for r in relays}})
    inst.truth["description"] = f"no compact mechanism: {n_rel} weak parallel relays, about {k_star} needed"
    return inst


def _subset_of_draws(b: _Builder) -> BuiltInstance:
    v, D = b.spec.variant, b.D
    c = int(D.choice("copies", (2, 3)))
    core = b.core0()
    if v == "latch_persistence":
        w = D.int("latch_self", 36, 37)
        L0 = core[0]
        b.edge(L0, L0, w)
        copies = [[L0]]
        for Lk in b.take(c - 1):
            b.edge(Lk, b.stim, b.C[L0, b.stim]); b.edge(Lk, Lk, w); b.edge(b.readout, Lk, b.C[b.readout[0], L0])
            b.signs[Lk], b.roles[Lk] = 1, "state_memory"
            copies.append([Lk])
        groups = [[cp[0] for cp in copies]]
    else:  # ei_rhythm
        w = D.int("ei_self", 42, 46)
        E0, I0 = core
        b.edge(E0, E0, w)
        copies = [[E0, I0]]
        for _ in range(c - 1):
            Ek, Ik = b.take(2)
            b.edge(Ek, Ek, w); b.edge(Ik, Ek, b.C[I0, E0]); b.edge(Ek, Ik, b.C[E0, I0])
            b.edge(Ek, b.stim, b.C[E0, b.stim]); b.edge(b.readout, Ek, b.C[b.readout[0], E0])
            b.signs.update({Ek: 1, Ik: -1})
            b.roles.update({Ek: "recurrent_excitatory_core", Ik: "inhibitory_feedback"})
            copies.append([Ek, Ik])
        groups = [[cp[0] for cp in copies], [cp[1] for cp in copies]]
    union = sorted(p for cp in copies for p in cp)
    contested = {f"copy{k}_{j}": p for k, cp in enumerate(copies) for j, p in enumerate(cp)}
    checks = [_ck("intact_partial", "intact_pass", [], "between", (0.25, 0.92))]
    checks += [_ck(f"copy{k}_not_sufficient_alone", "keep_only_pass", cp, "<=", 0.65) for k, cp in enumerate(copies[:2])]
    adv = {"mechanism": [union], "acceptable": [union], "contested": contested, "checks": checks, "exchangeable": groups,
           "copies": [sorted(cp) for cp in copies], "subset_of_draws": {"flag": True}, "essential_designed": []}
    return b.finish(adv, alternatives=[union], description=f"function on a subset of draws: {c} exchangeable marginal copies")


def _identical_decoy(b: _Builder) -> BuiltInstance:
    v, D = b.spec.variant, b.D
    m = b.core0()
    exc = b.excitatory(m)
    extra = D.int("extra_drive", 0, 5 if v == "ei_rhythm" else 12)  # more extra drive takes an E-I copy out of its limit cycle
    src = exc[int(D.choice("gate_source", range(len(exc))))]
    gate_in, gate_out = D.int("gate_in", 40, 60), D.int("gate_out", 120, 200)
    latch_in, latch_self = D.int("latch_in", 50, 70), D.int("latch_self", 58, 70)
    copy = dict(zip(m, b.take(len(m))))
    for p, p2 in copy.items():  # the same internal wiring, drive (+ extra) and output counts
        for q, q2 in copy.items():
            if b.C[q, p] > 0:
                b.edge(q2, p2, b.C[q, p])
        if b.C[p, b.stim] > 0:
            b.edge(p2, b.stim, b.C[p, b.stim] + extra)
        ro = [r for r in b.readout if b.C[r, p] > 0]
        for r in ro:
            b.edge(r, p2, b.C[r, p])
        b.signs[p2], b.roles[p2] = int(b.inst.signs[p]), "redundant_backup"
    decoy = sorted(copy.values())
    (G,) = b.take(1)
    b.signs[G], b.roles[G] = -1, "gain_control"
    contested = {**_named("m", m), **{f"decoy{k}": copy[p] for k, p in enumerate(m)}, "gate": G}
    # the planted source switches on a bistable latch that drives the gate: the gate is strong whatever the source's rate (a rhythmic or
    # weakly firing member could not hold the decoy down alone), and it never switches on when the planted mechanism is silenced
    (L,) = b.take(1)
    b.edge(L, src, latch_in); b.edge(L, L, latch_self); b.edge(G, L, gate_in)
    b.signs[L], b.roles[L] = 1, "modulatory_supporting"
    contested["latch"] = L
    for p2 in decoy:
        b.edge(p2, G, gate_out)
    checks = [_ck("intact", "intact_pass", [], ">=", PASS_MIN), _ck("planted_sufficient", "keep_only_pass", m, ">=", PASS_MIN),
              _ck("decoy_sufficient", "keep_only_pass", decoy, ">=", PASS_MIN), _ck("decoy_silent", "silent", decoy, "<=", SILENT_HZ)]
    adv = {"mechanism": [m], "acceptable": [m], "latent_backups": [decoy], "silent_members": decoy, "contested": contested, "checks": checks,
           "essential_designed": []}
    return b.finish(adv, alternatives=[m], description="planted motif + a structurally identical copy kept silent by a gate")


def _fragile_vs_robust(b: _Builder) -> BuiltInstance:
    v, D = b.spec.variant, b.D
    if v == "two_impl_rhythm":
        alts = [[int(x) for x in a] for a in b.inst.truth["alternatives"]]
        fragile, robust = sorted(alts, key=len)[0], sorted(alts, key=len)[-1]
        E = b.excitatory(fragile)[0]
        b.edge(E, E, D.int("fragile_self", 46, 53))
        inst = b.finish({"mechanism": [robust], "acceptable": [robust], "fragile_alternatives": [fragile], "contested": {}, "checks": [],
                         "essential_designed": [], "_keep_roles": robust + fragile}, alternatives=[robust], description="")
    else:  # band: a single strongly driven relay whose readout drive sits near the band's lower edge, next to the planted chain
        robust = b.core0()
        drive, out, tp = D.int("fragile_drive", 40, 60), D.int("fragile_out", 12, 20), D.real("target_pass", 0.4, 0.7)
        (H,) = b.take(1)
        b.edge(H, b.stim, drive)
        b.edge(b.readout, H, out)
        b.signs[H], b.roles[H] = 1, "output_driver"
        fragile = [H]
        inst = b.finish({"mechanism": [robust], "acceptable": [robust], "fragile_alternatives": [fragile], "contested": {}, "checks": []},
                        alternatives=[robust], description="")
        # lo: the (1 - target_pass) quantile of the readout driven by the fragile relay, pooled over keep-only of the relay and the intact
        # network without the chain (which adds the background's input to the readout): the relay alone passes on about target_pass of
        # the draws, and the intact network relies on the chain on about the rest
        means = [_simulate(inst, s, iv)["readout_mean_hz"] for s in CALIBRATION_SEEDS for iv in (_ko(inst, fragile), _sil(robust))]
        lo = round(float(np.quantile(means, 1.0 - tp)), 3)
        inst.criterion = {**inst.criterion, "lo_hz": lo}
        D.params["lo_hz"] = lo
    adv = inst.truth["adversarial"]
    adv.update({"contested": {**_named("robust", robust), **_named("fragile", fragile)}, "params": dict(D.params),
                "checks": [_ck("intact", "intact_pass", [], ">=", PASS_MIN), _ck("robust_sufficient", "keep_only_pass", robust, ">=", 0.9),
                           _ck("fragile_partly_sufficient", "keep_only_pass", fragile, "between", (0.2, 0.9)),
                           _ck("network_relies_on_robust", "silence_pass", robust, "<=", 0.85),
                           _ck("fragile_dispensable", "silence_pass", fragile, ">=", 0.9)]})
    adv["targets"] = {**{int(p): 1.0 for p in robust}, **{int(p): 0.0 for p in fragile}}
    inst.truth["description"] = "a smaller implementation sufficient on part of the draws next to a robust one the intact network relies on"
    return inst


_BUILDERS = {"latent_backup": _latent_backup, "masked_gate": _masked_gate, "distributed_drive": _distributed_drive,
             "subset_of_draws": _subset_of_draws, "identical_decoy": _identical_decoy, "fragile_vs_robust": _fragile_vs_robust}


def build_adversarial(spec: AdversarialSpec) -> BuiltInstance:
    """The trap instance of ``spec`` (canonical node order; truth in ``inst.truth['adversarial']``, measured fields added by
    :func:`verify_adversarial`). Deterministic in the spec."""
    return _BUILDERS[spec.trap](_Builder(spec))


# ---------------------------------------------------------------------------------------------------------------- simulation (canonical frame)
def _ck(name: str, kind: str, nodes, op: str, thr) -> dict:
    return {"name": name, "kind": kind, "nodes": sorted(int(p) for p in nodes), "op": op, "threshold": thr}


def _crit_spec(inst: BuiltInstance) -> dict:
    spec = dict(inst.criterion)
    if inst.readout_groups:
        spec["group_a_positions"] = [int(p) for p in inst.readout_groups["a"]]
        spec["group_b_positions"] = [int(p) for p in inst.readout_groups["b"]]
    return spec


def _window_start(crit: dict) -> float:
    for k in ("analysis_start_s", "during_start_s", "window_start_s"):
        if k in crit:
            return float(crit[k])
    return 0.25


def _ko(inst: BuiltInstance, nodes) -> Intervention:
    return Intervention(keep_only=tuple(sorted(int(p) for p in nodes)), always_keep=tuple(sorted({int(inst.stim), *map(int, inst.readout)})))


def _sil(nodes) -> Intervention:
    return Intervention(silence=tuple(sorted(int(p) for p in nodes)))


def _simulate(inst: BuiltInstance, seed: int, iv: Intervention | None = None, _W: sp.csr_matrix | None = None) -> dict:
    W = _W if _W is not None else sp.csr_matrix(inst.W)
    cfg = ModelConfig(t_end=inst.t_end)
    params = sample_neuron_params(cfg, W.shape[0], int(seed), np.full(W.shape[0], 1e9))
    traj = simulate(W, params, cfg, Stimulus((int(inst.stim),), (STIM_CURRENT,), pulse_end=inst.pulse_end_s), iv)
    crit = _crit_spec(inst)
    ro = np.zeros(W.shape[0], bool)
    ro[list(inst.readout)] = True
    out = criterion_from_spec(crit).evaluate(traj, ro)
    out["mean_rate"] = traj.r[traj.t >= _window_start(crit) - 1e-12].mean(axis=0)
    return out


def verify_adversarial(inst: BuiltInstance, seeds=None, *, max_silenced: int = 40) -> dict:
    """Check the trap's defining properties by simulation on ``seeds`` (default VERIFY_SEEDS) and record the measured truth.

    Returns a dict shaped like :func:`synthetic.verify_instance` (``verified``, ``intact_pass``, ``alternatives``, ``essential``,
    ``necessary_within_core``, ``criterion``) plus ``checks`` (every defining property with its value), ``silence_pass`` (single-silencing
    pass fraction of the mechanism and contested nodes, at most ``max_silenced`` of them) and ``rates_hz`` (median intact mean rate).
    The measured values are also written into ``inst.truth['adversarial']``: ``essential`` (silencing pass <= FAIL_MAX),
    ``non_essential`` (>= PASS_MIN), ``ambiguous`` (between), ``silence_pass``, ``rates_hz`` and, for subset_of_draws, the intact and
    copy pass fractions."""
    seeds = list(seeds) if seeds is not None else list(VERIFY_SEEDS)
    adv = inst.truth["adversarial"]
    W = sp.csr_matrix(inst.W)
    cache: dict[tuple, list[dict]] = {}

    def runs(iv_key: tuple, iv: Intervention | None) -> list[dict]:
        if iv_key not in cache:
            cache[iv_key] = [_simulate(inst, s, iv, W) for s in seeds]
        return cache[iv_key]

    def pf(outs):
        return float(np.mean([o["passed"] for o in outs]))

    intact = runs(("intact",), None)
    rates = np.median(np.stack([o["mean_rate"] for o in intact]), axis=0)
    checks = {}
    for ck in adv["checks"]:
        nodes = ck["nodes"]
        if ck["kind"] == "intact_pass":
            val = pf(intact)
        elif ck["kind"] == "keep_only_pass":
            val = pf(runs(("ko", *nodes), _ko(inst, nodes)))
        elif ck["kind"] == "silence_pass":
            val = pf(runs(("sil", *nodes), _sil(nodes)))
        elif ck["kind"] in ("silent", "active"):
            vals = [float(rates[p]) for p in nodes]
            val = max(vals) if ck["kind"] == "silent" else min(vals)
        else:
            raise ValueError(f"unknown check kind {ck['kind']!r}")
        thr, op = ck["threshold"], ck["op"]
        ok = (val >= thr) if op == ">=" else (val <= thr) if op == "<=" else (thr[0] <= val <= thr[1])
        checks[ck["name"]] = {"value": round(float(val), 6), "op": op, "threshold": thr, "ok": bool(ok), "kind": ck["kind"], "nodes": nodes}
    mech_nodes = sorted({p for a in adv.get("mechanism_designed", adv["mechanism"]) for p in a})
    to_silence = list(dict.fromkeys([*mech_nodes, *sorted(adv["contested"].values())]))[:max_silenced]
    sigma = {int(p): pf(runs(("sil", int(p)), _sil([p]))) for p in to_silence}
    adv["silence_pass"] = {int(p): round(v, 4) for p, v in sigma.items()}
    adv["essential"] = sorted(p for p, v in sigma.items() if v <= FAIL_MAX)
    adv["non_essential"] = sorted(p for p, v in sigma.items() if v >= PASS_MIN)
    adv["ambiguous"] = sorted(p for p, v in sigma.items() if FAIL_MAX < v < PASS_MIN)
    _apply_essential_rule(adv, set(adv["essential"]))  # every acceptable core and mechanism set contains every measured-essential node
    inst.truth["alternatives"] = [list(a) for a in (adv["acceptable"] or adv["mechanism"])]
    inst.truth["core"] = list(inst.truth["alternatives"][0])
    acc0 = adv["acceptable"][0] if adv["acceptable"] else []
    necessary = {int(p): pf(runs(("ko", *[q for q in acc0 if q != p]), _ko(inst, [q for q in acc0 if q != p]))) <= FAIL_MAX for p in acc0}
    alts = []
    for a in inst.truth["alternatives"]:
        outs = runs(("ko", *a), _ko(inst, a))
        alts.append({"nodes": list(map(int, a)), "keep_only_pass": pf(outs), "keep_only_score": float(np.mean([o["score"] for o in outs]))})
    adv["rates_hz"] = {int(p): round(float(rates[p]), 6) for p in sorted({*mech_nodes, *adv["contested"].values()})}
    adv["intact_pass"] = pf(intact)
    if adv["subset_of_draws"].get("flag"):
        adv["subset_of_draws"].update({"intact_pass": pf(intact), "union_keep_only_pass": pf(runs(("ko", *mech_nodes), _ko(inst, mech_nodes))),
                                       "copy_keep_only_pass": [pf(runs(("ko", *cp), _ko(inst, cp))) for cp in adv["copies"]]})
    verified = bool(all(c["ok"] for c in checks.values()))
    return {"seeds": seeds, "trap": adv["trap"], "variant": adv["variant"], "verified": verified, "checks": checks, "intact_pass": pf(intact),
            "intact_score": float(np.mean([o["score"] for o in intact])), "alternatives": alts,
            "essential": {int(p): bool(v <= FAIL_MAX) for p, v in sigma.items()}, "silence_pass": adv["silence_pass"],
            "necessary_within_core": necessary, "rates_hz": adv["rates_hz"], "criterion": _crit_spec(inst)}


def _require(sets, essential: set[int]) -> list[list[int]]:
    """Each set joined with the essential nodes, duplicates removed, order kept."""
    out: list[list[int]] = []
    for a in sets:
        s = sorted({int(p) for p in a} | {int(p) for p in essential})
        if s not in out:
            out.append(s)
    return out


def _apply_essential_rule(adv: dict, essential: set[int]) -> None:
    """The definition (DEFINITION): every acceptable core and every mechanism set contains every measured-essential node, and every
    essential node is a membership target 1. Recomputed from the designed sets, so applying it again is a no-op."""
    adv["acceptable"] = _require(adv.get("acceptable_designed", adv["acceptable"]), essential)
    adv["mechanism"] = _require(adv.get("mechanism_designed", adv["mechanism"]), essential)
    for p in essential:
        adv["targets"][int(p)] = 1.0
    adv["definition"] = DEFINITION


def build_verified(spec: AdversarialSpec, *, seeds=None, max_tries: int = 8, seed_step: int = 1) -> tuple[BuiltInstance, dict, AdversarialSpec]:
    """The first seed spec.seed, spec.seed + seed_step, ... whose instance verifies (the synthetic suites re-draw the same way)."""
    last = None
    for k in range(int(max_tries)):
        s = AdversarialSpec(**{**spec.__dict__, "family": spec.variant, "seed": int(spec.seed) + k * int(seed_step), "knobs": dict(spec.knobs)})
        inst = build_adversarial(s)
        ver = verify_adversarial(inst, seeds)
        if ver["verified"]:
            return inst, ver, s
        last = ver
    failed = {k: v for k, v in (last or {}).get("checks", {}).items() if not v["ok"]}
    raise RuntimeError(f"no verified {spec.trap}/{spec.variant} instance in {max_tries} tries from seed {spec.seed}; last failing checks: {failed}")


# ---------------------------------------------------------------------------------------------------------------- export
def _map_truth(adv: dict, inv: np.ndarray) -> dict:
    """The adversarial truth in the public positions of one exported network."""
    def m(x):
        return int(inv[int(x)])

    def sets(xs):
        return [sorted(m(p) for p in a) for a in xs]

    deg = dict(adv["degenerate"])
    if deg.get("membership_frequency"):
        deg["membership_frequency"] = {m(p): f for p, f in deg["membership_frequency"].items()}
    out = {"trap": adv["trap"], "variant": adv["variant"], "definition": adv.get("definition"), "mechanism": sets(adv["mechanism"]),
           "acceptable": sets(adv["acceptable"]), "mechanism_designed": sets(adv.get("mechanism_designed", adv["mechanism"])),
           "acceptable_designed": sets(adv.get("acceptable_designed", adv["acceptable"])),
           "essential": sorted(m(p) for p in adv["essential"]), "non_essential": sorted(m(p) for p in adv.get("non_essential", [])),
           "ambiguous": sorted(m(p) for p in adv.get("ambiguous", [])), "silence_pass": {m(p): v for p, v in adv.get("silence_pass", {}).items()},
           "latent_backups": sets(adv["latent_backups"]), "silent_members": sorted(m(p) for p in adv["silent_members"]),
           "fragile_alternatives": sets(adv["fragile_alternatives"]), "contested": {k: m(p) for k, p in adv["contested"].items()},
           "targets": {m(p): t for p, t in adv["targets"].items()}, "exchangeable": sets(adv["exchangeable"]), "degenerate": deg,
           "subset_of_draws": dict(adv["subset_of_draws"]), "rates_hz": {m(p): r for p, r in adv.get("rates_hz", {}).items()},
           "intact_pass": adv.get("intact_pass")}
    if "copies" in adv:
        out["copies"] = sets(adv["copies"])
    return out


def export_adversarial(inst: BuiltInstance, ver: dict, root: Path | str, salt: str = "adversarial", *, n_order_variants: int = 2) -> dict:
    """Write the public instance with :func:`synthetic.export_instance` (bundle format, node-order variants ``main``, ``order1``, ...)
    and add the adversarial truth to ``root/truth/<label>.json`` — top level: the spec, the drawn parameters and the checks;
    ``networks[name]['adversarial']``: every node field in that network's public positions. Nothing adversarial is written into the
    public instance directory."""
    root = Path(root)
    info = export_instance(inst, ver, root, n_order_variants=n_order_variants, salt=salt)
    tpath = root / "truth" / f"{inst.spec.label}.json"
    truth = json.loads(tpath.read_text(encoding="utf-8"))
    adv = inst.truth["adversarial"]
    truth["suite"] = SUITE_ID
    truth["adversarial"] = {k: adv[k] for k in ("trap", "variant", "base_family", "params")}
    truth["adversarial"]["checks"] = ver.get("checks")
    truth["adversarial"]["verified"] = ver.get("verified")
    for net in truth["networks"].values():
        perm = np.asarray(net["perm"], dtype=np.int64)
        inv = np.empty_like(perm)
        inv[perm] = np.arange(len(perm))
        net["adversarial"] = _map_truth(adv, inv)
    tpath.write_text(json.dumps(truth, indent=1, default=_json_default) + "\n", encoding="utf-8", newline="\n")
    return {**info, "trap": adv["trap"], "variant": adv["variant"]}


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def readout_count(n_total: int) -> int:
    return 12 if n_total <= 200 else 20 if n_total <= 1000 else 40


def adversarial_specs(n_per_trap: int = 1, sizes=(60, 150, 1500), seed0: int = 0, traps=TRAPS) -> list[AdversarialSpec]:
    """Default design: every variant of every trap at every size, ``n_per_trap`` seeds each (consecutive seeds from ``seed0``). With the
    defaults: 21 variants x 3 sizes = 63 specs, covering activity band, rhythm, ramp, persistence and selectivity criteria."""
    specs, s = [], int(seed0)
    for trap in traps:
        for variant in sorted(VARIANTS[trap]):
            for n in sizes:
                for _ in range(int(n_per_trap)):
                    specs.append(AdversarialSpec(trap, variant, n_total=int(n), seed=s, n_readout=readout_count(int(n))))
                    s += 1
    return specs


# ---------------------------------------------------------------------------------------------------------------- scoring
def _int_keys(d) -> dict:
    return {int(k): v for k, v in (d or {}).items()}


def normalize_truth_network(truth_network: dict) -> dict:
    """A migrated copy of one exported truth network entry (``truth['networks'][name]``, public positions); the input is not changed.

    Applies the current definition (DEFINITION) to entries exported under any earlier one:
    * every acceptable core and every mechanism set is joined with the measured-essential nodes (``adversarial.essential``);
    * every essential node gets membership target 1;
    * the regular scorer's ``alternatives_positions`` and ``core_positions`` follow the new acceptable cores (or, when there is no
      compact core, the mechanism); other alternatives already listed there (e.g. added by a suite audit) are kept after them;
    * the sets as designed are kept in ``acceptable_designed`` / ``mechanism_designed``, and ``definition`` records the rule.
    Idempotent. An entry without an ``adversarial`` part is returned as an unchanged copy."""
    tn = copy.deepcopy(truth_network)
    adv = tn.get("adversarial")
    if adv is None:
        return tn
    old = [sorted(int(p) for p in a) for a in (adv.get("acceptable") or adv.get("mechanism") or [])]
    adv["acceptable_designed"] = [sorted(int(p) for p in a) for a in adv.get("acceptable_designed", adv.get("acceptable", []))]
    adv["mechanism_designed"] = [sorted(int(p) for p in a) for a in adv.get("mechanism_designed", adv.get("mechanism", []))]
    essential = {int(p) for p in adv.get("essential", [])}
    targets = adv.get("targets") or {}
    str_keys = any(isinstance(k, str) for k in targets)  # JSON-loaded truths carry string keys: keep the representation
    adv["targets"] = {int(k): v for k, v in targets.items()}
    _apply_essential_rule(adv, essential)
    if str_keys:
        adv["targets"] = {str(k): v for k, v in adv["targets"].items()}
    new = adv["acceptable"] or adv["mechanism"]
    if new:
        rest = [a for a in tn.get("alternatives_positions", []) if sorted(int(p) for p in a) not in old + new]
        tn["alternatives_positions"] = [list(a) for a in new] + rest
        tn["core_positions"] = list(new[0])
    return tn


def _flagged_degenerate(diag: dict) -> bool:
    diag = diag or {}
    if any(bool(diag.get(k)) for k in DEGENERATE_FLAGS):
        return True
    flags = diag.get("flags")
    if isinstance(flags, dict):
        return any(bool(flags.get(k)) for k in DEGENERATE_FLAGS)
    if isinstance(flags, (list, tuple, set, str)):
        text = " ".join(map(str, flags)) if not isinstance(flags, str) else flags
        return any(k in text for k in DEGENERATE_FLAGS)
    return False


def intact_rates(problem, seeds) -> np.ndarray:
    """Median over ``seeds`` of each neuron's mean rate in the criterion's analysis window of the intact public network."""
    crit = dict(problem.criterion_spec)
    t0 = _window_start(crit)
    out = []
    for s in seeds:
        params = sample_neuron_params(problem.model_cfg, problem.n, int(s), problem.sizes)
        traj = simulate(problem.W, params, problem.model_cfg, problem.stimulus(), None)
        out.append(traj.r[traj.t >= t0 - 1e-12].mean(axis=0))
    return np.median(np.stack(out), axis=0)


def score_adversarial(result, truth_network: dict, problem=None, seeds=None, *, confident: float = CONFIDENT_P,
                      participation_hz: float = ACTIVE_HZ) -> dict:
    """Score one discovery result on one network of an adversarial instance.

    ``result``: a DiscoveryResult or its ``to_dict()`` (positions of this network). ``truth_network``: ``truth['networks'][name]``.
    ``problem`` (the network's DiscoveryProblem) and ``seeds`` (default SCORE_SEEDS) enable the simulation-based fields. Definitions
    (research/phase2/reviews/G_adversarial_suite.md):

    The truth is first brought to the current definition (:func:`normalize_truth_network`: every acceptable core contains every
    measured-essential node), so truths exported before that rule are scored the same way as new ones.

    * ``correct``: the core equals an acceptable core; for a degenerate instance (no compact core) the result must flag degeneracy
      (and, as everywhere, contain every essential node).
    * ``contains_mechanism``: some acceptable core (degenerate: the whole mechanism) is a subset of the core.
    * ``latent_backup_returned``: a latent backup is a subset of the core; ``latent_members_in_core``: silent trap nodes in the core.
    * ``essential_recall``: fraction of the truth-essential nodes in the core.
    * ``participation``: median intact rate of every core member; fraction of members >= ``participation_hz``.
    * ``brier_contested`` / ``calibration_items``: inclusion probability vs membership target over the contested nodes, the acceptable
      cores and the returned core (targets: 1 member, 0 non-member, membership frequency for exchangeable relays; a missing
      probability counts as 0).
    * ``confident`` (every core member >= ``confident``) and ``confident_wrong`` (confident and not correct).
    * ``degenerate_flagged``: the result's diagnostics carry one of DEGENERATE_FLAGS (``diagnostics[flag]`` truthy, or in
      ``diagnostics['flags']``).
    * ``exchangeable_gap``: largest probability difference inside a group of interchangeable nodes.
    * ``essential_claims``: the result's essential claims against the measured silencing pass fractions (ambiguous nodes excluded)."""
    res = result.to_dict() if hasattr(result, "to_dict") else dict(result)
    if truth_network.get("adversarial") is None:
        raise ValueError("truth network has no 'adversarial' entry (not an adversarial instance)")
    adv = normalize_truth_network(truth_network)["adversarial"]
    core = sorted({int(p) for p in res.get("core") or []})
    cs = set(core)
    P = {int(k): float(v) for k, v in (res.get("inclusion_probability") or {}).items()}
    acceptable = [set(map(int, a)) for a in adv["acceptable"]]
    mechanism = [set(map(int, a)) for a in adv["mechanism"]]
    latent = [set(map(int, a)) for a in adv["latent_backups"]]
    essential = set(map(int, adv["essential"]))
    sigma = _int_keys(adv.get("silence_pass"))
    targets = {int(k): v for k, v in _int_keys(adv.get("targets")).items()}
    degenerate = bool(adv["degenerate"].get("flag"))
    flagged = _flagged_degenerate(res.get("diagnostics") or {})
    exact = frozenset(cs) in {frozenset(a) for a in acceptable}
    contains = any(a <= cs for a in (acceptable or mechanism)) if cs else False
    correct = (flagged and essential <= cs) if degenerate else exact  # acceptable cores already contain every essential node
    best = max(acceptable, key=lambda a: len(a & cs) / max(1, len(a | cs))) if acceptable else set()
    member = set().union(*acceptable) if acceptable else set().union(*mechanism) if mechanism else set()
    nodes = sorted(set(map(int, adv["contested"].values())) | member | cs)
    items = []
    for p in nodes:
        t = targets.get(p, 1.0 if (p in member and not degenerate) else (None if p in member else 0.0))
        if t is None:
            continue
        items.append([round(P.get(p, 0.0), 6), float(t), int(p)])
    brier = float(np.mean([(p - t) ** 2 for p, t, _ in items])) if items else None
    is_conf = bool(core) and all(P.get(p, 0.0) >= confident for p in core)
    gaps = [max(P.get(int(p), 0.0) for p in g) - min(P.get(int(p), 0.0) for p in g) for g in adv.get("exchangeable", []) if len(g) > 1]
    claims = {"n": 0, "correct": 0, "wrong": 0, "ambiguous": 0, "unknown": 0}
    for p, v in _int_keys(res.get("essential")).items():
        if v is None:
            continue
        s = sigma.get(p)
        if s is None:
            claims["unknown"] += 1
            continue
        claims["n"] += 1
        if FAIL_MAX < s < PASS_MIN:
            claims["ambiguous"] += 1
        elif bool(v) == (s <= FAIL_MAX):
            claims["correct"] += 1
        else:
            claims["wrong"] += 1
    out = {"trap": adv["trap"], "variant": adv["variant"], "core": core, "correct": bool(correct), "exact": bool(exact),
           "contains_mechanism": bool(contains),
           "extra_members": len(cs - best) if acceptable else None, "missing_members": sorted(best - cs) if acceptable else None,
           "latent_backup_returned": any(lb <= cs for lb in latent) if cs else False,
           "latent_members_in_core": sorted(cs & set(map(int, adv["silent_members"]))),
           "fragile_returned": any(fa <= cs for fa in (set(map(int, a)) for a in adv.get("fragile_alternatives", []))) if cs else False,
           "essential_recall": (len(cs & essential) / len(essential)) if essential else None, "essential_missed": sorted(essential - cs),
           "brier_contested": brier, "calibration_items": items, "confident": is_conf, "confident_wrong": bool(is_conf and not correct),
           "degenerate": degenerate, "degenerate_flagged": flagged, "exchangeable_gap": max(gaps) if gaps else None, "essential_claims": claims,
           "subset_of_draws": bool(adv["subset_of_draws"].get("flag")), "intact_pass_truth": adv.get("intact_pass"),
           "fidelity_claimed": (res.get("fidelity") or {}).get("keep_only_pass_fraction"),
           "participation": None, "core_keep_only_pass": None, "intact_pass": None, "core_frequency_hz": None, "intact_frequency_hz": None}
    if problem is not None and core:
        from .interventions import keep_only
        from .simulator import BudgetedSimulator
        seeds = list(seeds) if seeds is not None else list(SCORE_SEEDS)
        rates = intact_rates(problem, seeds)
        member_rates = {int(p): round(float(rates[p]), 6) for p in core}
        out["participation"] = {"member_rates_hz": member_rates, "min_hz": min(member_rates.values()),
                                "fraction_active": float(np.mean([r >= participation_hz for r in member_rates.values()]))}
        sim = BudgetedSimulator(problem, max_calls=10 ** 9)
        ko = sim.evaluate(keep_only(problem, core), seeds)
        it = sim.evaluate(None, seeds)
        out["core_keep_only_pass"] = float(np.mean([o.passed for o in ko]))
        out["intact_pass"] = float(np.mean([o.passed for o in it]))
        fk = [o.frequency_hz for o in ko if o.passed and o.frequency_hz is not None]
        fi = [o.frequency_hz for o in it if o.passed and o.frequency_hz is not None]
        out["core_frequency_hz"] = float(np.median(fk)) if fk else None
        out["intact_frequency_hz"] = float(np.median(fi)) if fi else None
        if out["fidelity_claimed"] is not None:
            out["fidelity_error"] = float(out["fidelity_claimed"]) - out["core_keep_only_pass"]
    return out


def summarize_adversarial(scores: list[dict]) -> dict:
    """Pooled summary of score_adversarial outputs: per trap (rates of correct, confident_wrong, latent backup returned, mean essential
    recall, participation and contested Brier) and a reliability table of the pooled calibration items."""
    def mean(xs):
        xs = [x for x in xs if x is not None]
        return float(np.mean(xs)) if xs else None

    by: dict[str, list[dict]] = {}
    for s in scores:
        by.setdefault(s["trap"], []).append(s)
    per = {t: {"n": len(ss), "correct": mean([float(s["correct"]) for s in ss]), "confident_wrong": mean([float(s["confident_wrong"]) for s in ss]),
               "latent_backup_returned": mean([float(s["latent_backup_returned"]) for s in ss]),
               "essential_recall": mean([s["essential_recall"] for s in ss]),
               "participation_fraction": mean([(s["participation"] or {}).get("fraction_active") for s in ss]),
               "brier_contested": mean([s["brier_contested"] for s in ss]), "exchangeable_gap": mean([s["exchangeable_gap"] for s in ss])}
           for t, ss in sorted(by.items())}
    items = [(p, t) for s in scores for p, t, _ in s["calibration_items"]]
    bins = [(0.0, 0.05), (0.05, 0.3), (0.3, 0.6), (0.6, 0.85), (0.85, 1.0001)]
    table = []
    for lo, hi in bins:
        xs = [(p, t) for p, t in items if lo <= p < hi]
        if xs:
            table.append({"bin": [lo, min(hi, 1.0)], "n": len(xs), "mean_p": float(np.mean([p for p, _ in xs])),
                          "observed": float(np.mean([t for _, t in xs]))})
    return {"per_trap": per, "n_runs": len(scores), "confident_wrong": mean([float(s["confident_wrong"]) for s in scores]),
            "correct": mean([float(s["correct"]) for s in scores]), "reliability": table,
            "brier_contested": float(np.mean([(p - t) ** 2 for p, t in items])) if items else None}
