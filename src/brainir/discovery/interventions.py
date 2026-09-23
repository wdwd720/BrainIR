"""Intervention constructors and group designs for causal probing (positional indices)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

from ..sim.model import Intervention
from .problem import DiscoveryProblem


def silence(positions: Iterable[int], *, weight_noise_sd: float = 0.0, weight_noise_seed: int | None = None) -> Intervention:
    """Remove the given neurons (rows and columns zeroed) from an otherwise intact network."""
    return Intervention(silence=tuple(sorted({int(p) for p in positions})), weight_noise_sd=weight_noise_sd, weight_noise_seed=weight_noise_seed)


def keep_only(problem: DiscoveryProblem, positions: Iterable[int], *, weight_noise_sd: float = 0.0,
              weight_noise_seed: int | None = None) -> Intervention:
    """Keep only the given neurons plus the problem's stimulus and readout population; everything else is removed."""
    return Intervention(keep_only=tuple(sorted({int(p) for p in positions})), always_keep=problem.always_keep(),
                        weight_noise_sd=weight_noise_sd, weight_noise_seed=weight_noise_seed)


def intact(*, weight_noise_sd: float = 0.0, weight_noise_seed: int | None = None) -> Intervention | None:
    return None if weight_noise_sd == 0 else Intervention(weight_noise_sd=weight_noise_sd, weight_noise_seed=weight_noise_seed)


def canonical(iv: Intervention | None) -> dict:
    """JSON-able canonical form (used for cache keys and logs)."""
    if iv is None:
        return {"kind": "intact"}
    return {"kind": "keep_only" if iv.keep_only is not None else "silence" if iv.silence else "intact",
            "silence": list(iv.silence), "keep_only": None if iv.keep_only is None else list(iv.keep_only), "always_keep": list(iv.always_keep),
            "weight_noise_sd": iv.weight_noise_sd, "weight_noise_seed": iv.weight_noise_seed}


def random_partition(candidates: Sequence[int], n_groups: int, rng: np.random.Generator) -> list[list[int]]:
    """Split candidates into n_groups random groups of near-equal size (group-testing designs)."""
    c = np.array(list(candidates), dtype=np.int64)
    rng.shuffle(c)
    return [sorted(int(x) for x in g) for g in np.array_split(c, max(1, n_groups)) if len(g)]


def bisect(group: Sequence[int], rng: np.random.Generator | None = None) -> tuple[list[int], list[int]]:
    """Split a group into two halves (random order if rng given, else by position)."""
    g = np.array(list(group), dtype=np.int64)
    if rng is not None:
        rng.shuffle(g)
    k = len(g) // 2
    return sorted(int(x) for x in g[:k]), sorted(int(x) for x in g[k:])


def random_subsets(candidates: Sequence[int], n_subsets: int, include_prob: float, rng: np.random.Generator) -> list[list[int]]:
    """Bernoulli(include_prob) random subsets (compressive / group-testing designs)."""
    c = np.array(list(candidates), dtype=np.int64)
    out = []
    for _ in range(n_subsets):
        m = rng.random(len(c)) < include_prob
        out.append(sorted(int(x) for x in c[m]))
    return out
