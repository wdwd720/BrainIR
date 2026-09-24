"""A mechanism-discovery problem loaded from a public-bundle-format network directory.

The format is the frozen dng100 bundle format (``networks/<name>/{neurons,edges}.parquet``, ``stimulus.json``,
``readout.json``, ``network.json``) plus the bundle-level ``model_config.json``; synthetic instances use exactly the
same layout and may add ``networks/<name>/criterion.json`` (functional criterion other than the rhythm score). Only
public information is loaded; there is no path to any oracle here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

from ..sim.model import ModelConfig, Stimulus


@dataclass
class DiscoveryProblem:
    root: Path
    """Bundle root (contains model_config.json and networks/)."""
    name: str
    dataset: str
    version: str
    benchmark_id: str
    neurons: pd.DataFrame
    """Public neuron table (position-indexed rows; ``source_id`` are the ids predictions must use)."""
    edges: pd.DataFrame
    W: sp.csr_matrix
    """Signed synapse counts, post x pre, positional indices (the model's matrix)."""
    C: sp.csr_matrix
    """Observed (unsigned) synapse counts, post x pre — anatomy independent of the sign hypothesis."""
    signs: np.ndarray
    sizes: np.ndarray | None
    stim_positions: tuple[int, ...]
    stim_current: float
    readout_mask: np.ndarray
    model_cfg: ModelConfig
    criterion_spec: dict
    files_read: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ construction
    @classmethod
    def from_bundle(cls, root: Path | str, network: str) -> DiscoveryProblem:
        root = Path(root)
        d = root / "networks" / network
        info = json.loads((d / "network.json").read_text(encoding="utf-8"))
        stim = json.loads((d / "stimulus.json").read_text(encoding="utf-8"))
        readout = json.loads((d / "readout.json").read_text(encoding="utf-8"))
        mc = json.loads((root / "model_config.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8")) if (root / "manifest.json").exists() else {}
        neurons = pd.read_parquet(d / "neurons.parquet")
        edges = pd.read_parquet(d / "edges.parquet")
        n = len(neurons)
        neurons = neurons.sort_values("position").reset_index(drop=True)
        if not (neurons["position"].to_numpy() == np.arange(n)).all():
            raise ValueError(f"{d}: positions are not 0..N-1")
        post = edges["post_position"].to_numpy(); pre = edges["pre_position"].to_numpy()
        W = sp.csr_matrix((edges["signed_weight"].to_numpy(dtype=np.float64), (post, pre)), shape=(n, n))
        W.eliminate_zeros()
        C = sp.csr_matrix((edges["synapse_count"].to_numpy(dtype=np.float64), (post, pre)), shape=(n, n))
        C.eliminate_zeros()
        sizes = neurons["size_voxels"].to_numpy(dtype=np.float64) if "size_voxels" in neurons else None
        if sizes is not None and not np.isfinite(sizes).any():
            sizes = None
        readout_mask = np.zeros(n, dtype=bool)
        readout_mask[[int(p) for p in readout["positions"]]] = True
        cfg = ModelConfig(**{k: v for k, v in mc["config"].items() if k in ModelConfig.__dataclass_fields__})
        crit_path = d / "criterion.json"
        if crit_path.exists():
            crit = json.loads(crit_path.read_text(encoding="utf-8"))
        else:
            m = mc.get("metric", {})
            crit = {"type": "rhythm", "analysis_start_s": m.get("analysis_start_s", 0.25), "active_rate_hz": m.get("active_rate_hz", 0.01),
                    "prominence": m.get("prominence", 0.05), "score_threshold": m.get("rhythmic_threshold", 0.5), "amplitude_min_hz": 0.25}
        files = [f"networks/{network}/{f}" for f in ("neurons.parquet", "edges.parquet", "stimulus.json", "readout.json", "network.json")]
        files.append("model_config.json")
        if crit_path.exists():
            files.append(f"networks/{network}/criterion.json")
        return cls(root=root, name=network, dataset=info["dataset"], version=info["version"],
                   benchmark_id=manifest.get("benchmark_id", info.get("benchmark_id", "unknown")), neurons=neurons, edges=edges, W=W, C=C,
                   signs=neurons["sign"].to_numpy(dtype=np.int8), sizes=sizes, stim_positions=tuple(int(p) for p in stim["positions"]),
                   stim_current=float(stim["current"]), readout_mask=readout_mask, model_cfg=cfg, criterion_spec=crit, files_read=files,
                   extra={"stimulus": stim, "readout": readout, "network_info": info})

    # ------------------------------------------------------------------ derived quantities
    @property
    def n(self) -> int:
        return int(len(self.neurons))

    @property
    def public_ids(self) -> np.ndarray:
        """The identifiers a prediction must use (positions in tier A, body ids in tier B, whatever the bundle says)."""
        return self.neurons["source_id"].to_numpy(dtype=np.int64)

    @property
    def readout_positions(self) -> np.ndarray:
        return np.flatnonzero(self.readout_mask)

    def stimulus(self, current: float | None = None) -> Stimulus:
        """The problem's stimulus (constant pulse; ``pulse_end_s`` in stimulus.json, when present, ends it early)."""
        st = self.extra.get("stimulus", {})
        return Stimulus(self.stim_positions, (float(self.stim_current if current is None else current),),
                        pulse_start=st.get("pulse_start_s"), pulse_end=st.get("pulse_end_s"))

    def always_keep(self) -> tuple[int, ...]:
        """Positions a keep-only intervention never removes: the stimulus and the readout population."""
        return tuple(sorted(set(self.stim_positions) | set(int(p) for p in self.readout_positions)))

    def candidate_positions(self) -> np.ndarray:
        """Default candidate set for mechanism membership: everything except stimulus and readout neurons."""
        m = np.ones(self.n, dtype=bool)
        m[list(self.stim_positions)] = False
        m[self.readout_mask] = False
        return np.flatnonzero(m)

    def network_hash(self) -> str:
        """Content hash of what the simulator sees (matrix, sizes, stimulus, readout, model config, criterion)."""
        h = hashlib.sha256()
        h.update(f"n={self.n}|".encode())  # the size matters even when no neuron sizes are given (isolated neurons)
        Wc = self.W.tocoo()
        for arr in (Wc.row.astype(np.int64), Wc.col.astype(np.int64), Wc.data.astype(np.float64)):
            h.update(np.ascontiguousarray(arr).tobytes())
        h.update(b"|sizes|" + (np.ascontiguousarray(self.sizes).tobytes() if self.sizes is not None else b"none"))
        st = self.extra.get("stimulus", {})
        h.update(json.dumps({"stim": list(self.stim_positions), "current": self.stim_current, "readout": self.readout_positions.tolist(),
                             "pulse": [st.get("pulse_start_s"), st.get("pulse_end_s")], "cfg": self.model_cfg.to_dict(),
                             "criterion": self.criterion_spec}, sort_keys=True, default=str).encode())
        return h.hexdigest()

    def public_summary(self) -> dict:
        return {"name": self.name, "dataset": self.dataset, "version": self.version, "benchmark_id": self.benchmark_id, "n": self.n,
                "n_edges": int(self.C.nnz), "n_stimulus": len(self.stim_positions), "n_readout": int(self.readout_mask.sum()),
                "criterion": self.criterion_spec.get("type"), "network_hash": self.network_hash()[:16]}


# ---------------------------------------------------------------------------- shipping bundles to remote workers
def pack_bundle(root: Path | str, network: str, extra: dict[str, bytes] | None = None) -> dict[str, bytes]:
    """The files of one bundle network as {relative path: bytes}, for remote workers that have no access to the filesystem.

    Includes ``model_config.json`` / ``manifest.json`` at the root and every file of ``networks/<network>/``."""
    root = Path(root)
    pack: dict[str, bytes] = {}
    for f in ("model_config.json", "manifest.json"):
        if (root / f).exists():
            pack[f] = (root / f).read_bytes()
    for f in sorted((root / "networks" / network).iterdir()):
        if f.is_file():
            pack[f"networks/{network}/{f.name}"] = f.read_bytes()
    if extra:
        pack.update(extra)
    return pack


def unpack_bundle(pack: dict[str, bytes], dest: Path | str) -> Path:
    """Write a :func:`pack_bundle` dict under ``dest`` and return ``dest``."""
    dest = Path(dest)
    for rel, data in pack.items():
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return dest


def path_basename(p: Path | str) -> str:
    """Last path component whatever the separator (a Windows path shipped to a Linux worker keeps its backslashes)."""
    s = str(p).rstrip("\\").rstrip("/")
    return s.replace("\\", "/").rsplit("/", 1)[-1]


def write_bundle_manifest(root: Path | str, header: dict) -> dict:
    """(Re)write ``root/manifest.json`` in the benchmark bundle format: every file under ``root`` except the manifest, with its
    SHA-256 and size, and ``bundle_sha256`` = SHA-256 of the sorted file table — so any bundle-format directory (synthetic
    instances, node-order variants) verifies with :func:`brainir.benchmark.bundle.verify_bundle` and can run through the
    frozen clean-room runner. ``header`` supplies the descriptive fields (benchmark_id, tier, networks, ...)."""
    root = Path(root)
    files = {}
    for p in sorted(q for q in root.rglob("*") if q.is_file() and q.name != "manifest.json"):
        files[p.relative_to(root).as_posix()] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "size_bytes": p.stat().st_size}
    manifest = {"bundle_format_version": "1.0.0", **header, "files": files}
    manifest["bundle_sha256"] = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    (root / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    return manifest
