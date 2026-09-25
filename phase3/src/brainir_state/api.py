"""The state-discovery method API and result schema (goal4 sections 8, 42, 47-48).

A METHOD learns, from training trajectories of one or more systems, a STATE MODEL:

    encoder    z_t = phi_s(x_{<=t}, u_{<=t})          causal: sees only the past of the observed microstate and the input,
                                                        never the readout y (output leakage) and never the future
    dynamics   z_{t+dt} = f(z_t, u_t, e_t)            e_t = the microscopic interventions acting at t (as descriptors)
    readout    y_t = g_s(z_t, u_t)

per system s (implementation-specific encoders / readouts may share one f). The evaluator only ever calls the methods below, with
held-out data the method has never seen. Every array is float; times are in seconds on the system's output grid.

Interventions reach the model as the protocol's event descriptors (kick / current / silence / edge_remove, with neuron ids),
shifted so that time 0 is the rollout start; a model that cannot represent an event kind must say so (`supports()`), and is then
scored as abstaining on that event family, never silently as "no effect".
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

SCHEMA_VERSION = "brainir-state-model-1"


class StateModel(ABC):
    """An executable, serialisable state model (goal4 section 48)."""

    #: latent dimension per system (usually one k for all systems of a shared model)
    k: dict[str, int]

    @abstractmethod
    def encode(self, system_id: str, x_hist: np.ndarray, u_hist: np.ndarray, dt: float) -> np.ndarray:
        """Latent state at the LAST sample of the history. x_hist (T, N_obs), u_hist (T, n_u) -> z (k,)."""

    @abstractmethod
    def rollout(self, system_id: str, z0: np.ndarray, u_future: np.ndarray, events: list[dict], dt: float) -> dict[str, np.ndarray]:
        """Predict from z0 at time 0 under inputs u_future (H+1, n_u) (u_future[0] is the input at time 0) and the events (times
        relative to time 0). Returns {"z": (H+1, k), "y": (H+1, n_y)}; row 0 is time 0."""

    @abstractmethod
    def readout(self, system_id: str, z: np.ndarray, u: np.ndarray) -> np.ndarray:
        """y for latent states z (..., k) and inputs u (..., n_u)."""

    def supports(self, system_id: str, event_kind: str) -> bool:
        """Whether rollout() models this event kind for this system (else the evaluator scores abstention)."""
        return False

    def lift(self, system_id: str, x: np.ndarray, z: np.ndarray, delta_z: np.ndarray, n_candidates: int = 3) -> list[list[dict]]:
        """Optional (goal4 sections 13-14): up to n_candidates DISTINCT microscopic interventions (lists of events at time 0,
        kinds 'kick' or 'current') that should move the latent state from z to z + delta_z. [] = not supported."""
        return []

    def info(self) -> dict[str, Any]:
        """Self-reported properties. Keys the evaluator reads (all optional; see INFO_KEYS):
        "k": {system_id: int}, "k_range": {system_id: [lo, hi]}, "abstain": {system_id: {"no_compact_state": bool,
        "dimension_unresolved": [lo, hi] | None, "causal_equivalence_failed": bool, "reason": str}}, "n_params": {"encoder":
        {system_id: int}, "transition": int, "readout": {system_id: int}}, "sharing": {"mode": str, "verdict": str | None},
        "train_cost": {"cpu_s": float, "sim_calls": int, ...}, "lipschitz_bound": float | None."""
        return {}

    def save(self, path) -> None:
        """Serialise the executable model (goal4 section 48). Default: pickle of the whole object (the method module must be
        importable when loading)."""
        import pickle
        with open(path, "wb") as fh:
            pickle.dump(self, fh, protocol=pickle.HIGHEST_PROTOCOL)


def load_model(path) -> StateModel:
    import pickle
    with open(path, "rb") as fh:
        return pickle.load(fh)


#: keys of StateModel.info() the evaluator reads
INFO_KEYS = ("k", "k_range", "abstain", "n_params", "sharing", "train_cost", "lipschitz_bound")

#: config keys every method must honour (the evaluator uses them for the dimension sweep, the shared-vs-independent comparisons of
#: goal4 sections 17-19 and the leave-one-implementation-out test); a method that cannot honour one raises NotImplementedError
CONFIG_KEYS = {
    "k": "int: force this latent dimension (bypass the method's own dimension rule)",
    "sharing": "'auto' (default: the method decides and reports info()['sharing']), 'independent' (a separate f per system), "
               "'shared' (one f for all systems in train, system-specific encoders / readouts), 'partial' (partially shared f)",
    "adapt_from": "a fitted StateModel whose transition law f is FROZEN: fit only encoders / readouts for the systems in train "
                  "(new implementations); report the adaptation cost in info()['train_cost']",
}


class StateMethod(ABC):
    """A state-discovery method: training data in, StateModel out. Registered by name (`register`)."""
    name: str = "abstract"
    version: str = "0"
    default_config: dict = {}
    #: which values of config['sharing'] the method supports, and whether config['adapt_from'] is supported
    supported_sharing: tuple[str, ...] = ("auto", "independent")
    supports_adaptation: bool = False

    @abstractmethod
    def fit(self, train: list, *, systems: dict[str, dict], config: dict | None = None, sim=None, seed: int = 0) -> StateModel:
        """train: list of `brainir_state.data.Trajectory` (possibly of several systems, for shared models); systems: the dataset
        manifest entries of those systems; config: method hyper-parameters plus the evaluator keys of CONFIG_KEYS; sim: an optional
        budgeted simulation client (public protocol families only); seed: all randomness of the fit derives from it."""


_REGISTRY: dict[str, type[StateMethod]] = {}


def register(cls: type[StateMethod]) -> type[StateMethod]:
    _REGISTRY[cls.name] = cls
    return cls


def get_method(name: str) -> StateMethod:
    return _REGISTRY[name]()


def registered() -> list[str]:
    return sorted(_REGISTRY)


# ---------------------------------------------------------------------------------------------------------------- result schema
class LatentDimension(BaseModel):
    selected: int | None = Field(None, description="the selected k; None when the method abstains")
    plausible_range: tuple[int, int] | None = None
    rule: str = Field("", description="the generic, pre-registered selection rule that produced it")
    curve: list[dict] = Field(default_factory=list, description="per candidate k: validation metrics used by the rule")


class BrainIRStateModel(BaseModel):
    """Structured, versioned description of a learned state model (the executable model is stored alongside)."""
    schema_version: str = SCHEMA_VERSION
    method: str
    method_version: str
    source_datasets: list[str]
    systems: list[str]
    shared_dynamics: bool
    latent_dimension: LatentDimension
    encoder: dict = Field(default_factory=dict, description="specification and content hash per system")
    transition: dict = Field(default_factory=dict, description="specification, parameter count and content hash")
    readout: dict = Field(default_factory=dict)
    valid_input_domain: dict = Field(default_factory=dict)
    training_intervention_classes: list[str] = Field(default_factory=list)
    heldout_intervention_classes: list[str] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict, description="filled by the evaluator: families A-L, kept separate")
    latent_uncertainty: dict = Field(default_factory=dict)
    physical_to_latent: dict = Field(default_factory=dict, description="per latent dimension: supporting neurons, contributions, uncertainty")
    cross_mechanism_equivalence: dict = Field(default_factory=dict)
    cross_connectome_equivalence: dict = Field(default_factory=dict)
    failure_cases: list[dict] = Field(default_factory=list)
    abstention: dict = Field(default_factory=dict, description="e.g. {'no_compact_state': bool, 'dimension_unresolved': [a, b], ...}")
    provenance: dict = Field(default_factory=dict)
