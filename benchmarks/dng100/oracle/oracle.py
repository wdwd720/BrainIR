"""ORACLE of the DNg100 benchmark — evaluation only. Never import from discovery code.

`oracle.json` holds every fact the evaluator may compare a prediction against, each tagged with an evidence level:

    paper_simulation     result of the published model analysis (Pugliese et al. 2026) — a model-derived hypothesis
    brainir_simulation   result reproduced/extended with BrainIR's independent simulator on BrainIR's rebuilt networks
    wet_lab              experimental measurement (only DN-level optogenetics exists; no interneuron manipulation)
    expert_interpretation  a reading of the paper/data by the BrainIR team (weakest)

The oracle is versioned and hashed into BENCHMARK_LOCK.json; changing it means a new benchmark version.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORACLE_PATH = HERE / "oracle.json"
EVIDENCE_LEVELS = ("paper_simulation", "brainir_simulation", "wet_lab", "expert_interpretation")


@dataclass(frozen=True)
class OracleNetwork:
    name: str
    dataset: str
    version: str
    stimulus_source_ids: tuple[int, ...]
    core: dict[str, int]
    """label -> source_id for the published core mechanism in this network (E1, E2, I1, I2, E3, ...)."""
    roles: dict[str, str]
    """label -> 'excitatory' | 'inhibitory'."""
    essential: dict[str, bool | None]
    """label -> silencing abolishes the rhythm (paper_simulation)."""
    modal_circuit: tuple[str, ...]
    modal_prevalence: float
    inhibitory_slot: tuple[str, ...]
    """labels of which at least one fills the inhibitory position in published minimal circuits."""
    frequency_hz: tuple[float, float]
    """plausible MN rhythm frequency range under the benchmark stimulus (paper + BrainIR reproduction)."""
    evidence: dict[str, str]
    """fact -> evidence level."""

    def core_ids(self, labels: tuple[str, ...] | None = None) -> set[int]:
        labels = labels or tuple(self.core)
        return {self.core[k] for k in labels if k in self.core}

    def label_of(self, source_id: int) -> str | None:
        for k, v in self.core.items():
            if v == source_id:
                return k
        return None


def load_oracle(path: Path = ORACLE_PATH) -> tuple[dict, dict[str, OracleNetwork]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    nets = {}
    for name, n in raw["networks"].items():
        nets[name] = OracleNetwork(
            name=name, dataset=n["dataset"], version=n["version"], stimulus_source_ids=tuple(n["stimulus_source_ids"]),
            core={k: int(v) for k, v in n["core"].items()}, roles=n["roles"], essential=n["essential"],
            modal_circuit=tuple(n["modal_circuit"]), modal_prevalence=float(n["modal_prevalence"]),
            inhibitory_slot=tuple(n["inhibitory_slot"]), frequency_hz=tuple(n["frequency_hz"]), evidence=n["evidence"])
    return raw, nets


def oracle_sha256(path: Path = ORACLE_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
