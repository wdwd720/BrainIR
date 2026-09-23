"""Executable circuit models (Phase 1: the Pugliese et al. firing-rate network).

The simulator is a MODEL LAYER: it consumes anatomy (signed synapse counts, sizes) and explicit, versioned model
parameters and produces trajectories. Nothing here is written back into anatomy tables, and nothing here knows about
benchmark answers.

    from brainir.sim import build_network, ModelConfig, sample_neuron_params, simulate, Stimulus
"""

from .model import (
    MODEL_ID,
    Intervention,
    ModelConfig,
    NeuronParams,
    Stimulus,
    Trajectory,
    sample_neuron_params,
    sample_trunc_normal,
    simulate,
    size_scaling,
)
from .weights import Network, build_network, signed_matrix

__all__ = ["MODEL_ID", "Intervention", "ModelConfig", "Network", "NeuronParams", "Stimulus", "Trajectory", "build_network",
           "sample_neuron_params", "sample_trunc_normal", "signed_matrix", "simulate", "size_scaling"]
