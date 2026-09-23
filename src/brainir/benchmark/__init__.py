"""Benchmark support that is safe for discovery code to import: the prediction schema and the public-bundle builder.

Nothing under ``brainir.benchmark`` knows the answer. The oracle and the evaluator live under ``benchmarks/dng100/``
(outside the library) and are never imported here (enforced by tests/test_leakage_guard.py).
"""

from .prediction import (
    PREDICTION_SCHEMA_VERSION,
    BrainIRMechanismPrediction,
    CrossConnectomeClaim,
    DynamicsClaim,
    MechanismClaim,
    MethodInfo,
    NeuronClaim,
)

__all__ = ["PREDICTION_SCHEMA_VERSION", "BrainIRMechanismPrediction", "CrossConnectomeClaim", "DynamicsClaim",
           "MechanismClaim", "MethodInfo", "NeuronClaim"]
