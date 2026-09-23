"""The discovery method interface and its result type.

    result = method.discover(problem, simulator, seed=0, config={...})
    prediction = result.to_prediction(problem, method_info)

A method receives only the public problem and the budgeted simulator. Its result carries the mechanism as a set of
positions with per-neuron inclusion probabilities, generic functional roles with probabilities, essentiality claims,
alternative mechanisms and a budget report — everything the frozen prediction schema can hold is mapped into it;
what it cannot hold (generic roles, alternatives, inclusion probabilities of non-core neurons) goes into
``MechanismClaim.notes`` as JSON so it is preserved in the prediction file.
"""

from __future__ import annotations

import datetime as _dt
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from ..benchmark.prediction import BrainIRMechanismPrediction, DynamicsClaim, MechanismClaim, MethodInfo, NeuronClaim
from .problem import DiscoveryProblem
from .simulator import BudgetedSimulator

GENERIC_ROLES = ("input_relay", "recurrent_excitatory_core", "inhibitory_feedback", "gain_control", "state_memory", "output_driver",
                 "lateral_inhibition", "competitor", "redundant_backup", "modulatory_supporting", "unknown")
"""Generic functional roles a method may infer (goal3 §16); none refers to any specific circuit."""


@dataclass
class DiscoveryResult:
    core: list[int]
    """Positions of the predicted mechanism (excluding stimulus and readout)."""
    inclusion_probability: dict[int, float] = field(default_factory=dict)
    """p(z_i = 1 | data) for every candidate the method assessed (positions -> probability)."""
    roles: dict[int, tuple[str, float]] = field(default_factory=dict)
    """position -> (generic role, probability)."""
    essential: dict[int, bool | None] = field(default_factory=dict)
    """position -> predicted: silencing it alone destroys the function (True) / does not (False) / unknown (None)."""
    alternatives: list[list[int]] = field(default_factory=list)
    """Other mechanisms the method considers functionally equivalent (positions), most probable first."""
    loop: list[int] = field(default_factory=list)
    """Positions forming the predicted recurrent loop (if any)."""
    predicted_frequency_hz: float | None = None
    predicted_n_active_readout: int | None = None
    predicted_function_preserved: bool | None = None
    fidelity: dict = field(default_factory=dict)
    """Method's own estimates: keep-only pass fraction (nominal / robust), etc."""
    budget: dict = field(default_factory=dict)
    diagnostics: dict = field(default_factory=dict)
    motif: str | None = None

    def sign_role(self, problem: DiscoveryProblem, p: int) -> str:
        s = int(problem.signs[p])
        return "excitatory" if s > 0 else "inhibitory" if s < 0 else "unknown"

    def to_prediction(self, problem: DiscoveryProblem, method: MethodInfo, *, max_alternatives: int = 5) -> BrainIRMechanismPrediction:
        ids = problem.public_ids
        ranked = sorted(self.core, key=lambda p: -self.inclusion_probability.get(p, 1.0))
        claims = []
        for r, p in enumerate(ranked):
            prob = self.inclusion_probability.get(p)
            claims.append(NeuronClaim(source_id=int(ids[p]), role=self.sign_role(problem, p), essential=self.essential.get(p),
                                      rank=r + 1, confidence=None if prob is None else float(min(1.0, max(0.0, prob)))))
        notes = {
            "generic_roles": {int(ids[p]): {"role": r, "p": round(float(q), 4)} for p, (r, q) in self.roles.items() if p in set(self.core)},
            "inclusion_probability_top": {int(ids[p]): round(float(q), 4)
                                          for p, q in sorted(self.inclusion_probability.items(), key=lambda kv: -kv[1])[:25]},
            "alternatives": [[int(ids[p]) for p in alt] for alt in self.alternatives[:max_alternatives]],
            "fidelity": self.fidelity, "budget": self.budget,
        }
        text = json.dumps(notes, default=float, separators=(",", ":"))
        if len(text) > 2000:  # schema limit: keep the most important part
            notes.pop("inclusion_probability_top", None)
            text = json.dumps(notes, default=float, separators=(",", ":"))[:2000]
        return BrainIRMechanismPrediction(
            benchmark_id=problem.benchmark_id, dataset=problem.dataset, dataset_version=problem.version,
            stimulus_source_ids=[int(ids[p]) for p in problem.stim_positions], core_neurons=claims,
            dynamics=DynamicsClaim(frequency_hz=self.predicted_frequency_hz, n_active_readout=self.predicted_n_active_readout,
                                   rhythmic=self.predicted_function_preserved if problem.criterion_spec.get("type") == "rhythm" else None),
            mechanism=MechanismClaim(motif=self.motif, loop_neurons=[int(ids[p]) for p in self.loop], notes=text),
            method=method, created_utc=_dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"))

    def to_dict(self) -> dict:
        return {"core": [int(p) for p in self.core], "inclusion_probability": {int(k): float(v) for k, v in self.inclusion_probability.items()},
                "roles": {int(k): [r, float(q)] for k, (r, q) in self.roles.items()}, "essential": {int(k): v for k, v in self.essential.items()},
                "alternatives": [[int(p) for p in a] for a in self.alternatives], "loop": [int(p) for p in self.loop],
                "predicted_frequency_hz": self.predicted_frequency_hz, "predicted_n_active_readout": self.predicted_n_active_readout,
                "predicted_function_preserved": self.predicted_function_preserved, "fidelity": self.fidelity, "budget": self.budget,
                "diagnostics": {k: v for k, v in self.diagnostics.items() if not isinstance(v, np.ndarray)}, "motif": self.motif}


class DiscoveryMethod(ABC):
    name: str = "abstract"
    version: str = "0"
    default_config: dict = {}

    @abstractmethod
    def discover(self, problem: DiscoveryProblem, sim: BudgetedSimulator, *, seed: int, config: dict | None = None) -> DiscoveryResult:
        ...

    def method_info(self, problem: DiscoveryProblem, sim: BudgetedSimulator, seed: int, config: dict, *, wall_s: float,
                    code_commit: str | None = None, extra: dict | None = None) -> MethodInfo:
        return MethodInfo(name=self.name, version=self.version, description=(self.__doc__ or "").strip()[:4000] or None, code_commit=code_commit,
                          inputs_used=list(problem.files_read), random_seed=int(seed),
                          compute={"simulations": sim.calls, "simulated_seconds": round(sim.simulated_seconds, 3), "simulator": sim.report(),
                                   "wall_s": round(wall_s, 1), "config": config, **(extra or {})})


class MethodRegistry:
    _methods: dict[str, type[DiscoveryMethod]] = {}

    @classmethod
    def register(cls, method_cls: type[DiscoveryMethod]) -> type[DiscoveryMethod]:
        cls._methods[method_cls.name] = method_cls
        return method_cls

    @classmethod
    def get(cls, name: str) -> DiscoveryMethod:
        if name not in cls._methods:
            import importlib
            importlib.import_module("brainir.methods")  # registers the built-in methods
        if name not in cls._methods:
            raise KeyError(f"unknown discovery method {name!r}; known: {sorted(cls._methods)}")
        return cls._methods[name]()

    @classmethod
    def names(cls) -> list[str]:
        import importlib
        importlib.import_module("brainir.methods")
        return sorted(cls._methods)


def budget_report(sim: BudgetedSimulator, wall_s: float) -> dict:
    return {**sim.report(), "wall_s": round(wall_s, 2)}
