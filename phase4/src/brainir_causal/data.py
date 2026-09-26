"""Trajectory records and experiment sets (research/phase4/INTERFACES.md section 4; shared by the orchestrator, the evaluator and
methods; contains no truth).

A trajectory record (`Trajectory`):
    t (T,) float64       output grid (s)
    x (T, N_obs) float32 the system's OBSERVED microstate (the encoder input; never the readout)
    u (T, n_u) float32   exogenous input
    y (T, n_y) float32   readout
    protocol             canonical protocol (brainir_causal.protocol, format p4-protocol-1)
    family               brainir_causal.families label
    split                'train' | 'val' | 'twin' | 'pool' | 'test' | ... (free text, set by the producer)
    key                  content hash of the full protocol (protocol.protocol_hash; differs from the store's microstate key when
                         the protocol carries observation noise)
    meta                 e.g. {"twin_of": key} on the counterfactual twin of an intervention trajectory (same parameters, noise,
                         initial state and input; no events), {"pool": id}, ...
    provenance           who chose the experiment: 'benchmark' | 'designer:<name>' | 'service:<agent>' ...
    info                 engine bookkeeping

An `ExperimentSet` is an ordered list of records. On disk it is a directory:
    manifest.json   {"format", "dataset_id", "systems": {system_id: public record}, ...}
    index.jsonl     one line per record: {"key", "system_id", "split", "family", "protocol", "meta", "provenance", "info"}
    traj/<key>.npz  t, x, u, y
Protocol events name units by public id; `observed_index(system)` maps unit ids to columns of x.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

DATASET_FORMAT = "p4-dataset-1"


@dataclass
class Trajectory:
    key: str
    system_id: str
    split: str
    family: str
    protocol: dict
    t: np.ndarray
    x: np.ndarray
    u: np.ndarray
    y: np.ndarray
    meta: dict = field(default_factory=dict)
    provenance: str = "benchmark"
    info: dict = field(default_factory=dict)

    @property
    def dt(self) -> float:
        return float(self.t[1] - self.t[0]) if len(self.t) > 1 else float(self.protocol.get("dt", 0.0))

    def events(self) -> list[dict]:
        return list(self.protocol.get("events") or [])

    @property
    def is_intervention(self) -> bool:
        return bool(self.protocol.get("events"))

    def row(self) -> dict:
        return {"key": self.key, "system_id": self.system_id, "split": self.split, "family": self.family, "protocol": self.protocol,
                "meta": self.meta, "provenance": self.provenance, "info": self.info}


def _save_arrays(path: Path, tr: Trajectory) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".tmp.npz")
    np.savez_compressed(tmp, t=np.asarray(tr.t, dtype=np.float64), x=np.asarray(tr.x, dtype=np.float32),
                        u=np.asarray(tr.u, dtype=np.float32), y=np.asarray(tr.y, dtype=np.float32))
    tmp.replace(path)


class ExperimentSet:
    """An ordered collection of trajectory records, in memory; `save` / `load` for directories."""

    def __init__(self, records: Iterable[Trajectory] | None = None, systems: dict | None = None, dataset_id: str = ""):
        self.records: list[Trajectory] = list(records or [])
        self.systems: dict = dict(systems or {})
        self.dataset_id = dataset_id

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self) -> Iterator[Trajectory]:
        return iter(self.records)

    def __getitem__(self, i):
        return self.records[i]

    def add(self, tr: Trajectory) -> None:
        self.records.append(tr)

    def extend(self, trs: Iterable[Trajectory]) -> None:
        self.records.extend(trs)

    def select(self, *, system_id: str | None = None, split: str | None = None, family: str | None = None,
               interventions: bool | None = None) -> list[Trajectory]:
        return [r for r in self.records if (system_id is None or r.system_id == system_id) and (split is None or r.split == split)
                and (family is None or r.family == family) and (interventions is None or r.is_intervention == interventions)]

    def twins(self) -> dict[str, Trajectory]:
        """{key of an intervention trajectory: its counterfactual twin}."""
        return {r.meta["twin_of"]: r for r in self.records if r.meta.get("twin_of")}

    def observed_index(self, system_id: str) -> dict[int, int]:
        return {int(n): i for i, n in enumerate(self.systems[system_id]["observed"])}

    def by_key(self) -> dict[str, Trajectory]:
        return {r.key: r for r in self.records}

    # ---------------------------------------------------------------- disk
    def save(self, root: Path | str, extra_manifest: dict | None = None) -> None:
        root = Path(root)
        (root / "traj").mkdir(parents=True, exist_ok=True)
        with open(root / "index.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for r in self.records:
                p = root / "traj" / f"{r.key}.npz"
                if not p.exists():
                    _save_arrays(p, r)
                fh.write(json.dumps(r.row(), sort_keys=True) + "\n")
        man = {"format": DATASET_FORMAT, "dataset_id": self.dataset_id, "systems": self.systems, **(extra_manifest or {})}
        (root / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    @classmethod
    def load(cls, root: Path | str, *, lazy: bool = False) -> ExperimentSet | LazyExperimentSet:
        root = Path(root)
        man = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        rows = [json.loads(line) for line in (root / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        if lazy:
            return LazyExperimentSet(root, man, rows)
        return cls([load_row(root, r) for r in rows], systems=man.get("systems") or {}, dataset_id=man.get("dataset_id", ""))


def load_row(root: Path | str, row: dict) -> Trajectory:
    with np.load(Path(root) / "traj" / f"{row['key']}.npz") as z:
        return Trajectory(key=row["key"], system_id=row["system_id"], split=row.get("split", ""), family=row.get("family", ""),
                          protocol=row["protocol"], t=z["t"], x=z["x"], u=z["u"], y=z["y"], meta=row.get("meta") or {},
                          provenance=row.get("provenance", "benchmark"), info=row.get("info") or {})


class LazyExperimentSet:
    """Read access to a saved set without loading arrays until needed."""

    def __init__(self, root: Path, manifest: dict, rows: list[dict]):
        self.root, self.manifest, self.rows = root, manifest, rows
        self.systems = manifest.get("systems") or {}

    def __len__(self) -> int:
        return len(self.rows)

    def select(self, **kw) -> list[dict]:
        return [r for r in self.rows if all(r.get(k) == v for k, v in kw.items() if v is not None)]

    def load(self, row: dict) -> Trajectory:
        return load_row(self.root, row)

    def iter(self, **kw) -> Iterator[Trajectory]:
        for r in self.select(**kw):
            yield self.load(r)

    def materialise(self) -> ExperimentSet:
        return ExperimentSet([self.load(r) for r in self.rows], systems=self.systems, dataset_id=self.manifest.get("dataset_id", ""))
