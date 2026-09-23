"""Blind causal mechanism discovery (Phase 2): generic, benchmark-agnostic infrastructure.

A discovery method receives a :class:`~brainir.discovery.problem.DiscoveryProblem` (a public bundle network or a
synthetic instance in the same format: signed count graph, stimulus, readout, model configuration, functional
criterion) and a :class:`~brainir.discovery.simulator.BudgetedSimulator` (the expensive black-box oracle with a hard
query budget, caching and accounting), and returns a :class:`~brainir.discovery.interface.DiscoveryResult` that
converts to the frozen ``BrainIRMechanismPrediction`` schema.

Nothing in this package knows any benchmark answer: no neuron identities, no expected mechanism size, no cell-type
names. Methods live in :mod:`brainir.methods`.
"""

from .criteria import CRITERIA, Criterion, criterion_from_spec
from .interface import DiscoveryMethod, DiscoveryResult, MethodRegistry, budget_report
from .interventions import keep_only, silence
from .problem import DiscoveryProblem
from .simulator import BudgetedSimulator, BudgetExhausted, Outcome, SimQuery

__all__ = ["CRITERIA", "BudgetExhausted", "BudgetedSimulator", "Criterion", "DiscoveryMethod", "DiscoveryProblem", "DiscoveryResult",
           "MethodRegistry", "Outcome", "SimQuery", "budget_report", "criterion_from_spec", "keep_only", "silence"]
