"""Export the PUBLIC part of the DNg100 benchmark: networks, stimulus, readout, model configuration, manifest.

The bundle is everything a discovery method may see. It is derived from BrainIR's processed datasets plus a node list
per network (the set of neurons that constitutes the simulated network), and it carries provenance hashes so that the
evaluator can verify a prediction was made against the frozen bundle. It contains NO oracle information: no answer
neurons, no published circuit, no hints in text. The leakage audit (benchmarks/dng100/LEAKAGE_AUDIT.md) scans it.

Two tiers are exported from the same data:

* tier ``B`` (labelled): cell types and instances as in the connectome release.
* tier ``A`` (blind): cell types/instances of VNC interneurons replaced by salted hash tokens (``T#xxxxxxxx``); the
  salt is written OUTSIDE the bundle (``--salt-out``) and must be kept with the oracle. Descending neurons, motor
  neurons and sensory neurons keep their labels (they define stimulus/readout and are not the answer).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .. import __version__, paths
from ..graph import Connectome
from ..metrics.rhythm import ACTIVE_RATE_HZ, DEFAULT_PROMINENCE
from ..sim.experiments import ANALYSIS_START_S
from ..sim.model import MODEL_ID, ModelConfig
from ..sim.weights import Network, signed_matrix, vnc_neuropils

BENCHMARK_ID = "dng100-benchmark-v1"
BUNDLE_FORMAT_VERSION = "1.0.0"
STIMULUS_TYPE = "DNg100"
READOUT_RULE = "motor neurons (super_class == motor_neuron / vnc_motor) with sub_class 'fl' (front leg)"
BLIND_ROLES = ("vnc_intrinsic", "unknown", None)
"""Roles whose cell_type/instance are tokenised in tier A (interneurons and unclassified bodies)."""


@dataclass(frozen=True)
class NetworkSpec:
    name: str
    dataset: str
    version: str
    nodes_file: Path | None
    """CSV/parquet with a 'bodyId' or 'source_id' column defining the network; None = rule-based node set."""
    stim_current: float
    sizes_from: tuple[str, str] | None = None
    """(dataset, version) whose size_voxels are used when the build carries none (e.g. manc v1.0 for v1.2.x)."""
    roi_restrict_vnc: bool = False
    sign_basis: str = "auto"
    node_rule_note: str = ""


def _git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=paths.repo_root(), capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 24), b""):
            h.update(block)
    return h.hexdigest()


def _read_nodes(path: Path) -> np.ndarray:
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    col = "bodyId" if "bodyId" in df.columns else "source_id"
    return df[col].to_numpy().astype(np.int64)


def choose_stimulus(cx: Connectome, ids: np.ndarray) -> list[int]:
    """The stimulated neuron: the DNg100 body with the most synaptic output into the LEFT front-leg neuropil
    (the paper drove the DNg100 that innervates the left leg neuropils). Ties -> both."""
    dn = [int(i) for i in cx.ids_of_type(STIMULUS_TYPE) if int(i) in set(ids.tolist())]
    if not dn:
        raise ValueError(f"no {STIMULUS_TYPE} neuron in the network of {cx.dataset}:{cx.version}")
    cn = cx.connection_neuropils(dn, None)
    left = cn[cn["neuropil"] == "LegNp(T1)(L)"].groupby("pre_id")["synapse_count"].sum().reindex(dn).fillna(0)
    best = left.max()
    return sorted(int(i) for i in left.index[left == best])


def _blind_token(salt: str, dataset: str, version: str, source_id: int) -> str:
    return "T#" + hashlib.sha256(f"{salt}|{dataset}|{version}|{source_id}".encode()).hexdigest()[:10]


def export_network(spec: NetworkSpec, out_dir: Path, *, tier: str, salt: str | None) -> dict:
    cx = Connectome.open(spec.dataset, spec.version)
    if spec.nodes_file is not None:
        ids = _read_nodes(spec.nodes_file)
        node_rule = f"network membership from node list {spec.nodes_file.name} ({spec.node_rule_note or 'as published'})"
    else:
        raise NotImplementedError("rule-based node sets are not part of benchmark v1")
    ids = np.array([i for i in ids if cx.has(int(i))], dtype=np.int64)
    sizes, size_source = None, None
    if spec.sizes_from is not None:
        scx = Connectome.open(*spec.sizes_from)
        sizes = scx.neurons["size_voxels"].reindex(ids).astype("float64").to_dict()
        size_source = f"{spec.sizes_from[0]}:{spec.sizes_from[1]} size_voxels by body ID"
    roi = vnc_neuropils(cx) if spec.roi_restrict_vnc else None
    net: Network = signed_matrix(cx, ids, floor=5, sign_basis=spec.sign_basis, sign_rule="paper", remove_autapses=True,
                                 roi_restrict=roi, sizes=sizes, size_source=size_source)
    stim = choose_stimulus(cx, ids)
    tab = net.table.copy()
    readout = (tab["super_class"].isin(["motor_neuron", "vnc_motor"]) & (tab["sub_class"] == "fl")).to_numpy()
    tab["position"] = np.arange(net.n)
    tab["is_stimulus"] = tab["source_id"].isin(stim)
    tab["is_readout"] = readout
    neurons_full = cx.neurons.loc[ids]
    tab["side"] = neurons_full["side"].to_numpy()
    tab["soma_neuromere"] = neurons_full["soma_neuromere"].to_numpy()
    tab["hemilineage"] = neurons_full["hemilineage_truman"].to_numpy()
    id_map = None
    if tier == "A":
        if not salt:
            raise ValueError("tier A export needs a salt")
        blind = tab["role_class"].isin([r for r in BLIND_ROLES if r is not None]) | tab["role_class"].isna()
        tokens = [_blind_token(salt, spec.dataset, spec.version, int(i)) for i in tab["source_id"]]
        tab.loc[blind, "cell_type"] = np.array(tokens, dtype=object)[blind.to_numpy()]
        tab.loc[blind, "instance"] = None
        tab.loc[blind, "hemilineage"] = None
        # neuron identifiers become positional so that dataset body IDs (which appear in publications) are not visible
        id_map = pd.DataFrame({"position": np.arange(net.n), "source_id": net.ids})
        tab["source_id"] = tab["position"].to_numpy()
    public_ids = tab["source_id"].to_numpy()  # real IDs (tier B) or positions (tier A)
    cols = ["position", "source_id", "cell_type", "instance", "super_class", "sub_class", "role_class", "side", "soma_neuromere",
            "hemilineage", "nt_used", "sign", "size", "is_stimulus", "is_readout", "out_pairs", "in_pairs"]
    out_dir.mkdir(parents=True, exist_ok=True)
    ntab = pa.Table.from_pandas(tab[cols].rename(columns={"nt_used": "nt_label", "size": "size_voxels"}), preserve_index=False)
    pq.write_table(ntab, out_dir / "neurons.parquet", compression="zstd")
    W = net.W.tocoo()
    edges = pd.DataFrame({"pre_id": public_ids[W.col], "post_id": public_ids[W.row], "pre_position": W.col, "post_position": W.row,
                          "synapse_count": np.abs(W.data).astype(np.int32), "signed_weight": W.data.astype(np.int32)})
    edges = edges.sort_values(["pre_position", "post_position"], ignore_index=True)
    pq.write_table(pa.Table.from_pandas(edges, preserve_index=False), out_dir / "edges.parquet", compression="zstd")
    stim_pos = [int(np.flatnonzero(net.ids == s)[0]) for s in stim]
    stimulus = {"cell_type": STIMULUS_TYPE, "source_ids": [int(public_ids[p]) for p in stim_pos], "positions": stim_pos,
                "current": spec.stim_current, "pulse_start_s": ModelConfig().pulse_start,
                "rule": "the DNg100 body with the most synaptic output into LegNp(T1)(L); constant current pulse",
                "id_semantics": "positional (tier A)" if tier == "A" else "dataset body IDs"}
    readout_j = {"rule": READOUT_RULE, "n": int(readout.sum()), "source_ids": [int(i) for i in public_ids[readout]],
                 "positions": [int(p) for p in np.flatnonzero(readout)]}
    (out_dir / "stimulus.json").write_text(json.dumps(stimulus, indent=1) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "readout.json").write_text(json.dumps(readout_j, indent=1) + "\n", encoding="utf-8", newline="\n")
    manifest_path = paths.manifests_dir() / f"{spec.dataset}_{spec.version}.manifest.json"
    info = {
        "name": spec.name, "dataset": spec.dataset, "version": spec.version, "tier": tier,
        "node_rule": node_rule, "n_neurons": net.n, "n_edges": int(net.W.nnz), "total_synapses": net.meta["total_synapses"],
        "floor": 5, "remove_autapses": True, "sign_rule": net.meta["sign_rule"], "sign_basis": net.meta["sign_basis"],
        "nt_label_source": {"manc": "body-level predictedNt (v1.0 predictions carried by body ID)", "male-cns": "consensusNt"}.get(spec.dataset),
        "roi_restrict": net.meta["roi_restrict"], "size_source": net.meta["size_source"],
        "sign_rows": {"positive": int((net.signs > 0).sum()), "negative": int((net.signs < 0).sum()), "zero": int((net.signs == 0).sum())},
        "orientation": "edges.parquet lists pre -> post; W[post, pre] = signed_weight (post x pre) for the model",
        "source_tables": {"processed_dir": paths.relpath_for_record(paths.processed_dir(spec.dataset, spec.version)),
                          "build_info_sha256": _sha256(paths.processed_dir(spec.dataset, spec.version) / "build_info.json"),
                          "connections_sha256": _sha256(paths.processed_dir(spec.dataset, spec.version) / "connections.parquet"),
                          "neurons_sha256": _sha256(paths.processed_dir(spec.dataset, spec.version) / "neurons.parquet"),
                          "manifest_sha256": _sha256(manifest_path) if manifest_path.exists() else None},
    }
    info["id_semantics"] = stimulus["id_semantics"]
    (out_dir / "network.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8", newline="\n")
    if id_map is not None:
        info["_id_map"] = id_map  # returned to the caller (export_bundle) which stores it OUTSIDE the bundle
    return info


def export_network_ids(info: dict, private_dir: Path, name: str) -> Path | None:
    """Write the tier-A position -> body ID map next to the oracle (never into the bundle)."""
    m = info.pop("_id_map", None)
    if m is None:
        return None
    private_dir.mkdir(parents=True, exist_ok=True)
    p = private_dir / f"ids_{name}.csv"
    m.to_csv(p, index=False, lineterminator="\n")
    return p


def model_config_record() -> dict:
    cfg = ModelConfig()
    return {"model_id": MODEL_ID, "config": cfg.to_dict(),
            "metric": {"score": "brainir.metrics.rhythm.network_oscillation_score (published autocorrelation score)",
                       "analysis_start_s": ANALYSIS_START_S, "active_rate_hz": ACTIVE_RATE_HZ, "prominence": DEFAULT_PROMINENCE,
                       "rhythmic_threshold": 0.5},
            "parameter_distributions": "truncated normals, see ModelConfig fields *_mean/*_sd; size scaling a/s, theta*s",
            "reference_implementation": "brainir.sim.model.simulate; brainir.sim.experiments.stimulation_experiment"}


def write_readme(root: Path, tier: str, networks: list[dict]) -> None:
    lines = [f"# {BENCHMARK_ID} — public bundle (tier {tier})", "",
             "## Task", "",
             "Each network below is a signed synapse-count matrix derived from a Drosophila connectome, a constant-current stimulus",
             "into one descending neuron (`stimulus.json`) and a readout population of front-leg motor neurons (`readout.json`).",
             "Under the firing-rate model in `model_config.json`, the stimulus produces rhythmic motor output in most parameter",
             "replicates. **Identify the mechanism**: the set of interneurons through which the stimulus generates the rhythm, the",
             "role (excitatory/inhibitory) of each, which of them are individually essential, the rhythm's frequency, and — across",
             "the networks — which neurons correspond to each other. Submit one `BrainIRMechanismPrediction` per network",
             "(`brainir.benchmark.prediction`, schema 1.0.0).", "",
             "## Rules", "",
             "- Use only the files in this bundle plus the `brainir` library (simulator, metrics, prediction schema).",
             "- Do not consult literature, external databases or any file outside this bundle about these circuits.",
             "- Record every input you used and your compute in `MethodInfo`.", "",
             "## Files", "", "| path | content |", "|---|---|",
             "| `manifest.json` | bundle id, format version, creation time, code commit, SHA-256 of every file |",
             "| `model_config.json` | the rate model, its parameter distributions, integration settings and the rhythm metric |",
             "| `networks/<name>/neurons.parquet` | one row per neuron: position, source_id, labels, role class, NT label used for "
             "the sign, sign, size, stimulus/readout flags |",
             "| `networks/<name>/edges.parquet` | pre -> post pairs with synapse_count and signed_weight (>= 5 synapses, autapses removed) |",
             "| `networks/<name>/network.json` | how the network was derived from the connectome release (provenance hashes) |",
             "| `networks/<name>/stimulus.json`, `readout.json` | stimulated neuron(s) and current; readout neurons |", ""]
    if tier == "A":
        lines += ["## Tier A (blind)", "", "Cell types and instances of interneurons are replaced by opaque tokens (`T#...`). Descending, motor and",
                  "sensory neurons keep their labels. Tokens are consistent within a network but NOT across networks. Neuron",
                  "identifiers (`source_id`, `pre_id`, `post_id`, stimulus/readout ids) are positional indices 0..N-1 of this",
                  "network, not dataset body IDs; predictions must use these positional ids.", ""]
    lines += ["## Networks", "", "| name | dataset | neurons | edges | Σ synapses | stimulus | readout |", "|---|---|---|---|---|---|---|"]
    for n in networks:
        lines.append(f"| {n['name']} | {n['dataset']}:{n['version']} | {n['n_neurons']} | {n['n_edges']} | {n['total_synapses']} | "
                     f"{n['stimulus']['source_ids']} @ {n['stimulus']['current']} | {n['readout_n']} MNs |")
    lines += ["", "## Anatomy is not physiology", "",
              "Synapse counts are anatomical estimates from EM; neurotransmitter labels are machine predictions; signs follow a",
              "stated rule (cholinergic +, GABAergic/glutamatergic −, others 0). The model is a hypothesis, not a measurement.", ""]
    (root / "README.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def export_bundle(specs: list[NetworkSpec], root: Path, *, tier: str = "B", salt: str | None = None,
                  private_dir: Path | None = None) -> dict:
    """``private_dir`` (tier A): where the position -> body ID maps are written; must be outside ``root``."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if tier == "A" and private_dir is None:
        raise ValueError("tier A export needs private_dir for the id maps")
    (root / "model_config.json").write_text(json.dumps(model_config_record(), indent=1) + "\n", encoding="utf-8", newline="\n")
    nets = []
    for spec in specs:
        d = root / "networks" / spec.name
        info = export_network(spec, d, tier=tier, salt=salt)
        if tier == "A":
            export_network_ids(info, Path(private_dir), spec.name)
        info["stimulus"] = json.loads((d / "stimulus.json").read_text())
        info["readout_n"] = json.loads((d / "readout.json").read_text())["n"]
        nets.append(info)
    write_readme(root, tier, nets)
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "manifest.json")
    manifest = {
        "benchmark_id": BENCHMARK_ID, "bundle_format_version": BUNDLE_FORMAT_VERSION, "tier": tier,
        "created_utc": _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "brainir_version": __version__, "code_commit": _git_commit(),
        "networks": [{k: v for k, v in n.items() if k not in ("stimulus",)} | {"stimulus_source_ids": n["stimulus"]["source_ids"]}
                     for n in nets],
        "files": {p.relative_to(root).as_posix(): {"sha256": _sha256(p), "size_bytes": p.stat().st_size} for p in files},
    }
    manifest["bundle_sha256"] = hashlib.sha256(json.dumps(manifest["files"], sort_keys=True).encode()).hexdigest()
    (root / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    return manifest


def verify_bundle(root: Path) -> dict:
    """Recompute every file hash and compare with manifest.json."""
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    bad = {}
    for rel, rec in manifest["files"].items():
        p = root / rel
        if not p.exists():
            bad[rel] = "missing"
        elif _sha256(p) != rec["sha256"]:
            bad[rel] = "sha256 differs"
    extra = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
                   and p.relative_to(root).as_posix() not in manifest["files"] and p.name != "manifest.json")
    return {"ok": not bad and not extra, "problems": bad, "unlisted_files": extra, "bundle_sha256": manifest.get("bundle_sha256")}


def default_specs(nodes: dict[str, Path]) -> list[NetworkSpec]:
    """Benchmark v1 networks. ``nodes`` maps network name -> node-list file."""
    specs = []
    if "manc_v1.2.1" in nodes:
        specs.append(NetworkSpec("manc_v1.2.1", "manc", "v1.2.1", nodes["manc_v1.2.1"], 250.0, sizes_from=("manc", "v1.0"),
                                 sign_basis="nt_body_prediction", node_rule_note="front-leg network as published"))
    if "manc_v1.2.3" in nodes:
        specs.append(NetworkSpec("manc_v1.2.3", "manc", "v1.2.3", nodes["manc_v1.2.3"], 250.0, sizes_from=("manc", "v1.0"),
                                 sign_basis="nt_body_prediction", node_rule_note="front-leg network as published"))
    if "male-cns_v1.0" in nodes:
        specs.append(NetworkSpec("male-cns_v1.0", "male-cns", "v1.0", nodes["male-cns_v1.0"], 400.0, roi_restrict_vnc=True,
                                 sign_basis="nt_consensus", node_rule_note="front-leg network as published; VNC synapses only"))
    return specs


def spec_records(specs: list[NetworkSpec]) -> list[dict]:
    return [{**asdict(s), "nodes_file": s.nodes_file.name if s.nodes_file else None} for s in specs]
