"""Arm B1-controls: null networks (PREREG section 3.6). Generators are the benchmark's own, imported read-only from
``benchmarks/dng100_walking_cpg/robustness_experiments.py`` (degree-preserving rewiring; class shuffle with the authors' five
classes)."""

from __future__ import annotations

import numpy as np

from . import networks as N  # noqa: F401  (puts the benchmark directory on sys.path)

REWIRE_SEEDS = (101, 102, 103, 104, 105)
SHUFFLE_SEEDS = (201, 202, 203, 204, 205)


def control_names() -> list[str]:
    return [f"B1-ctl-rewire-{s}" for s in REWIRE_SEEDS] + [f"B1-ctl-classshuffle-{s}" for s in SHUFFLE_SEEDS]


def build(net, name: str):
    """(matrix, construction statistics) of a named control network built from the front-leg network ``net``."""
    from robustness_experiments import build_control, paper_shuffle_classes  # noqa: PLC0415

    kind, seed = name.split("-")[2], int(name.split("-")[3])
    if kind == "rewire":
        return build_control(net.W, "degree_rewire", seed, swaps_per_edge=10.0)
    if kind == "classshuffle":
        labels = paper_shuffle_classes(net.btable["super_class"].to_numpy(), np.asarray(net.btable["sign"].to_numpy()))
        return build_control(net.W, "class_shuffle", seed, labels=labels)
    raise ValueError(name)
