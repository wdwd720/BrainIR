"""The causal-state API and result schema (docs/API.md; goal5 sections 1, 14-16, 47-49, 90).

A METHOD (the learner) learns, from passive and interventional experiments on one or more systems, a CAUSAL STATE MODEL:

    encoder     z_t = phi_s(x_{<=t}, u_{<=t})         causal: the observed microstate and the input up to t only; never the readout
                                                      y, never the future. The history length used is part of the model's
                                                      complexity (info()["history"]).
    dynamics    z_{t+dt} = f(z_t, u_t, a_t)           a_t = the physical interventions active at t, acting through the read-in
    read-in     z+ = R(z-, a) / dz = r(z, a)          the latent effect of a physical intervention, with explicit semantics
    readout     y_t = g_s(z_t, u_t)
    lift        a* = argmin_a ||R(z, a) - dz||^2 + cost   native inverse: distinct physical interventions realising a latent shift

A DESIGNER chooses the next experiments (goal5 sections 24-29). The benchmark's experiment loop (`brainir_causal.loop`) couples a
learner with any designer at a fixed budget, so learners and designers are compared separately and together.

Interventions reach a model as protocol events (brainir_causal.protocol, format p4-protocol-1) with times relative to the rollout
start (time 0 = the encoding time). Truth-only events (latent_set / latent_kick) are never passed to a model. A model that cannot
represent an event kind says so (`supports()`); the evaluator then scores abstention, never a silent "no effect".

Every array is float64 unless stated; times are in seconds on the system's output grid.
"""

from __future__ import annotations

import pickle
from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

SCHEMA_VERSION = "brainir-causal-state-model-1"

#: keys of CausalStateModel.info() the evaluator reads (all optional)
INFO_KEYS = ("k", "k_range", "abstain", "history", "n_params", "train_cost", "sharing", "read_in", "lift", "uncertainty",
             "validity_domain", "active_history", "failure_flags", "training_families", "ablation_switches", "ablated")

#: the ABLATION vocabulary (goal5 sections 87-89): a method declares in info()["ablation_switches"] every name it honours (a
#: component it does not have is declared "not_applicable" with a reason) and applies config["ablate"]; the post-lock ablation study
#: runs the locked method once per switch and fails loudly on a switch that is neither honoured nor declared not applicable
ABLATION_SWITCHES = {
    "interventional_training": "train on passive data only: every interventional record (and its twin) is dropped before fitting "
                               "(THE critical ablation, goal5 section 88)",
    "mediation_loss": "drop the state-mediation objective term(s)",
    "closure_loss": "drop the interventional-closure objective term(s)",
    "active_design": "the method's own designer is replaced by the benchmark's random designer",
    "native_lift": "lift() is disabled (returns no lift)",
    "multiple_lift_consistency": "drop the objective / selection that makes distinct lifts consistent",
    "dimension_penalty": "drop the dimension penalty / rule (k from the unpenalised criterion, reported)",
    "history_delay": "the encoder sees only the current sample (no history / delay embedding beyond it)",
    "uncertainty_ensemble": "a single model instead of the ensemble / uncertainty machinery",
    "shared_dynamics": "no shared transition across systems (independent fits)",
    "state_bottleneck": "remove the compact state: predict from the full observed history with the same data (the second critical "
                        "ablation, goal5 section 89)",
}

#: config keys every method must honour (a method that cannot honour one raises NotImplementedError)
CONFIG_KEYS = {
    "k": "int: force this latent dimension (bypass the method's own dimension rule)",
    "sharing": "'auto' (default: the method decides, reported in info()['sharing']), 'independent' (a separate f per system), "
               "'shared' (one f for all systems in the data, system-specific encoders / read-ins / readouts), 'partial'",
    "adapt_from": "a fitted CausalStateModel whose transition law f is FROZEN: fit encoders / read-ins / readouts only for the "
                  "systems in the data (new implementations); report the adaptation cost in info()['train_cost']",
    "budget": "int: intervention experiments the method may request through its designer during the loop (0 = none)",
    "ablate": "list of ABLATION_SWITCHES names to switch off for this fit (default none); every name must be honoured or declared "
              "'not_applicable' in info()['ablation_switches']; info()['ablated'] repeats the applied list",
}


class CausalStateModel(ABC):
    """An executable, serialisable causal state model (goal5 section 49)."""

    #: latent dimension per system
    k: dict[str, int]

    # ------------------------------------------------------------------------------------------------ required
    @abstractmethod
    def encode(self, system_id: str, x_hist: np.ndarray, u_hist: np.ndarray, dt: float) -> np.ndarray:
        """Latent state at the LAST sample of the history. x_hist (T, N_obs), u_hist (T, n_u) -> z (k,)."""

    @abstractmethod
    def rollout(self, system_id: str, z0: np.ndarray, u_future: np.ndarray, events: list[dict], dt: float) -> dict[str, np.ndarray]:
        """Predict from z0 at time 0 under inputs u_future (H+1, n_u) (row 0 = the input at time 0) and the physical intervention
        events (times relative to time 0). Returns {"z": (H+1, k), "y": (H+1, n_y)} and optionally "y_sd": (H+1, n_y), the
        predictive standard deviation. Row 0 is time 0."""

    @abstractmethod
    def readout(self, system_id: str, z: np.ndarray, u: np.ndarray) -> np.ndarray:
        """y for latent states z (..., k) and inputs u (..., n_u)."""

    # ------------------------------------------------------------------------------------------------ intervention semantics
    def supports(self, system_id: str, event_kind: str) -> bool:
        """Whether rollout() / read_in() model this event kind for this system (else the evaluator scores abstention)."""
        return False

    def step(self, system_id: str, z: np.ndarray, u: np.ndarray, events_active: list[dict], dt: float) -> np.ndarray:
        """One controlled latent step z(t) -> z(t + dt) with the given events active (times relative to t). Default: a two-sample
        rollout."""
        u2 = np.vstack([np.atleast_2d(u), np.atleast_2d(u)])
        return np.asarray(self.rollout(system_id, z, u2, events_active, dt)["z"][1], dtype=float)

    def read_in(self, system_id: str, z: np.ndarray, event: dict) -> dict:
        """R(z, a): the latent effect of ONE physical intervention at latent state z. Instantaneous kinds: {"dz": (k,)}; finite /
        persistent kinds: {"operator": {...}} describing how the model's latent dynamics change while the event is active (e.g.
        {"type": "affine", "B": ..., "c": ...}). {} = not represented explicitly."""
        return {}

    def lift(self, system_id: str, x_hist: np.ndarray, u_hist: np.ndarray, delta_z: np.ndarray, n_candidates: int = 3,
             constraints: dict | None = None) -> list[dict]:
        """NATIVE lift (goal5 sections 15-16): up to n_candidates DISTINCT physical interventions, each {"events": [...] (times
        relative to the end of the history, kinds the system's capability allows), "predicted_dz": (k,), "cost": float,
        "dz_sd": (k,) optional}, that should move the latent state from phi(history) to phi(history) + delta_z. constraints may
        restrict kinds, targets and magnitudes. [] = not supported (scored as failing every lift case)."""
        return []

    # ------------------------------------------------------------------------------------------------ counterfactual API
    def intervention_effect(self, system_id: str, x_hist: np.ndarray, u_hist: np.ndarray, u_future: np.ndarray, events: list[dict],
                            dt: float) -> dict:
        """Counterfactual prediction (goal5 section 90) for the observed history and a candidate intervention sequence: the
        predicted future readout with and without the events, the effect, the latent trajectories, the uncertainty, the validity and
        an abstention flag ("insufficient evidence"). Default: encode once, two rollouts; abstain when an event kind is unsupported."""
        z0 = self.encode(system_id, x_hist, u_hist, dt)
        abstain = not all(self.supports(system_id, e["kind"]) for e in events)
        r1 = self.rollout(system_id, z0, u_future, events, dt)
        r0 = self.rollout(system_id, z0, u_future, [], dt)
        out = {"y_int": np.asarray(r1["y"], float), "y_base": np.asarray(r0["y"], float),
               "z_int": np.asarray(r1["z"], float), "z_base": np.asarray(r0["z"], float), "abstain": bool(abstain),
               "validity": self.validity(system_id, x_hist, u_hist, events)}
        out["effect"] = out["y_int"] - out["y_base"]
        if "y_sd" in r1:
            out["y_sd"] = np.asarray(r1["y_sd"], float)
        unc = self.uncertainty(system_id, x_hist, u_hist, u_future, events, dt)
        if unc:
            out["uncertainty"] = unc
        return out

    def uncertainty(self, system_id: str, x_hist: np.ndarray, u_hist: np.ndarray, u_future: np.ndarray, events: list[dict],
                    dt: float) -> dict:
        """Optional: {"y_sd": (H+1, n_y), "effect_sd": (H+1, n_y), "p_detectable": float, "p_sign_pos": (n_y,)}. {} = the model
        reports no uncertainty and is treated as confident everywhere."""
        return {}

    def validity(self, system_id: str, x_hist: np.ndarray, u_hist: np.ndarray, events: list[dict]) -> dict:
        """Optional: {"in_domain": bool, "score": float (higher = more trustworthy), "reasons": [str]}."""
        return {"in_domain": True, "score": 1.0, "reasons": []}

    # ------------------------------------------------------------------------------------------------ description
    def info(self) -> dict[str, Any]:
        """Self-reported properties (keys in INFO_KEYS): "k": {sid: int}, "k_range": {sid: [lo, hi]}, "abstain": {sid:
        {"no_compact_state": bool, "dimension_unresolved": [lo, hi] | None, "causal_equivalence_failed": bool, "reason": str}},
        "history": {sid: int samples}, "n_params": {"encoder": {sid: int}, "transition": int, "read_in": {sid: int}, "readout":
        {sid: int}}, "train_cost": {"cpu_s", "gpu_s", "flops", "sim_calls", "experiments"}, "sharing": {"mode", "verdict"}, ..."""
        return {}

    def schema(self) -> BrainIRCausalStateModel:
        """The versioned description (goal5 section 48). Default: assembled from info()."""
        inf = self.info() or {}
        ks = inf.get("k") or dict(getattr(self, "k", {}) or {})
        sel = None if len(set(ks.values())) != 1 else int(next(iter(ks.values())))
        rng = inf.get("k_range") or {}
        pr = None
        if rng and len({tuple(v) for v in rng.values()}) == 1:
            pr = tuple(int(v) for v in next(iter(rng.values())))
        return BrainIRCausalStateModel(
            method=str(inf.get("method", type(self).__name__)), method_version=str(inf.get("method_version", "0")),
            systems=sorted(ks), latent_dimension=LatentDimension(selected=sel, plausible_range=pr, rule=str(inf.get("k_rule", ""))),
            encoder={"history": inf.get("history", {})}, intervention_read_in=dict(inf.get("read_in") or {}),
            latent_lift=dict(inf.get("lift") or {}), training_intervention_families=list(inf.get("training_families") or []),
            validity_domain=dict(inf.get("validity_domain") or {}), failure_flags=list(inf.get("failure_flags") or []),
            abstention=dict(inf.get("abstain") or {}), active_experiment_history=list(inf.get("active_history") or []),
            provenance={"n_params": inf.get("n_params", {}), "train_cost": inf.get("train_cost", {})})

    def save(self, path) -> None:
        """Serialise the executable model (pickle of the whole object; the method module must be importable when loading)."""
        with open(path, "wb") as fh:
            pickle.dump(self, fh, protocol=pickle.HIGHEST_PROTOCOL)


def load_model(path) -> CausalStateModel:
    with open(path, "rb") as fh:
        return pickle.load(fh)


class Designer(ABC):
    """An experiment-design policy (goal5 sections 24-29, 38)."""
    name: str = "abstract"

    @abstractmethod
    def propose(self, system_id: str, system: dict, model: CausalStateModel | None, data: list, n: int, budget_left: int,
                rng: np.random.Generator) -> list[dict]:
        """Up to n protocols (p4-protocol-1) for this system, within its split record's families_train and its capability. `data`
        is the experiment set so far (records with t, x, u, y, protocol, family), `model` the learner's current model (None before
        the first fit)."""


class CausalStateMethod(ABC):
    """A learner: experiments in, CausalStateModel out. Registered by name (`register`)."""
    name: str = "abstract"
    version: str = "0"
    default_config: dict = {}
    supported_sharing: tuple[str, ...] = ("auto", "independent")
    supports_adaptation: bool = False

    @abstractmethod
    def fit(self, data: list, *, systems: dict[str, dict], config: dict | None = None, seed: int = 0) -> CausalStateModel:
        """data: trajectory records (`brainir_causal.data`) of one or more systems (passive and interventional, with twins);
        systems: the public system records; config: hyper-parameters plus CONFIG_KEYS; seed: all randomness derives from it."""

    def update(self, model: CausalStateModel, new_data: list, *, data_all: list, systems: dict[str, dict], config: dict | None = None,
               seed: int = 0) -> CausalStateModel:
        """Incorporate new experiments during the loop. Default: refit on everything."""
        return self.fit(data_all, systems=systems, config=config, seed=seed)

    def designer(self) -> Designer | None:
        """The method's own experiment-design policy, if any."""
        return None


_METHODS: dict[str, type[CausalStateMethod]] = {}
_DESIGNERS: dict[str, type[Designer]] = {}


def register(cls: type[CausalStateMethod]) -> type[CausalStateMethod]:
    _METHODS[cls.name] = cls
    return cls


def register_designer(cls: type[Designer]) -> type[Designer]:
    _DESIGNERS[cls.name] = cls
    return cls


def get_method(name: str) -> CausalStateMethod:
    return _METHODS[name]()


def get_designer(name: str) -> Designer:
    return _DESIGNERS[name]()


def registered() -> list[str]:
    return sorted(_METHODS)


def registered_designers() -> list[str]:
    return sorted(_DESIGNERS)


# -------------------------------------------------------------------------------------------------------------------- schema
class LatentDimension(BaseModel):
    selected: int | None = Field(None, description="the selected k; None when the method abstains or k differs by system")
    plausible_range: tuple[int, int] | None = None
    rule: str = Field("", description="the generic, pre-registered selection rule that produced it")
    curve: list[dict] = Field(default_factory=list, description="per candidate k: the validation metrics the rule used")
    uncertainty: dict = Field(default_factory=dict, description="e.g. bootstrap distribution of the selected k")


class BrainIRCausalStateModel(BaseModel):
    """Versioned description of a learned causal state model (goal5 section 48); the executable model is stored alongside."""
    schema_version: str = SCHEMA_VERSION
    method: str
    method_version: str
    source_datasets: list[str] = Field(default_factory=list)
    systems: list[str] = Field(default_factory=list)
    mechanism: dict = Field(default_factory=dict, description="system -> physical mechanism / implementation description")
    latent_dimension: LatentDimension = Field(default_factory=LatentDimension)
    encoder: dict = Field(default_factory=dict, description="specification, history length and content hash per system")
    latent_dynamics: dict = Field(default_factory=dict, description="transition specification, parameter count, content hash")
    intervention_read_in: dict = Field(default_factory=dict, description="read-in form and semantics per event kind")
    latent_lift: dict = Field(default_factory=dict, description="lift procedure, constraints, cost function")
    readout: dict = Field(default_factory=dict)
    intervention_domain: dict = Field(default_factory=dict, description="event kinds, targets and magnitude ranges supported")
    observability_diagnostics: dict = Field(default_factory=dict)
    training_intervention_families: list[str] = Field(default_factory=list)
    heldout_intervention_families: list[str] = Field(default_factory=list)
    prediction_metrics: dict = Field(default_factory=dict)
    mediation_metrics: dict = Field(default_factory=dict)
    closure_metrics: dict = Field(default_factory=dict)
    lift_metrics: dict = Field(default_factory=dict)
    microstate_equivalence: dict = Field(default_factory=dict)
    dimension_uncertainty: dict = Field(default_factory=dict)
    intervention_uncertainty: dict = Field(default_factory=dict)
    active_experiment_history: list[dict] = Field(default_factory=list)
    validity_domain: dict = Field(default_factory=dict)
    failure_flags: list[str] = Field(default_factory=list)
    abstention: dict = Field(default_factory=dict)
    provenance: dict = Field(default_factory=dict)
    hashes: dict = Field(default_factory=dict)
