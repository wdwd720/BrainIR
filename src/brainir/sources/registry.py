"""Registry of official data sources.

Every remote file BrainIR may acquire is declared here with the server-side
metadata observed when the source was registered (size, checksums, GCS
generation). The acquisition code refuses to silently accept a different
object under the same release name: if Janelia re-uploads a "v1.0" file, the
generation/checksum pins fail and a human must review the change (and bump the
registry deliberately).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import quote

_WINDOWS_UNSAFE = re.compile(r'[<>:"|?*]')


@dataclass(frozen=True)
class RemoteFile:
    key: str
    """Stable identifier used by code (never changes even if file names do)."""
    remote_path: str
    """Object path inside the bucket."""
    tier: str
    """Acquisition tier: 'core', 'synapses', 'metadata', or 'optional'."""
    description: str
    size: int
    """Expected size in bytes."""
    crc32c_b64: str
    """GCS CRC32C (base64, big-endian) — available for every object."""
    generation: int
    """GCS object generation observed at registration time."""
    md5_b64: str | None = None
    """GCS MD5 (base64). Absent for composite uploads."""
    updated: str | None = None
    """Server-side 'updated' timestamp at registration time."""


@dataclass(frozen=True)
class DatasetSource:
    dataset: str
    version: str
    bucket: str
    version_prefix: str
    neuprint_server: str
    neuprint_dataset: str
    files: tuple[RemoteFile, ...]
    doc_pages: dict[str, str] = field(default_factory=dict)
    citation: dict = field(default_factory=dict)
    license: dict = field(default_factory=dict)
    registered_on: str = ""

    def file(self, key: str) -> RemoteFile:
        for f in self.files:
            if f.key == key:
                return f
        raise KeyError(f"{self.dataset}:{self.version} has no registered file {key!r}")

    def url(self, f: RemoteFile) -> str:
        return f"https://storage.googleapis.com/{self.bucket}/{quote(f.remote_path)}"

    def metadata_url(self, f: RemoteFile) -> str:
        return f"https://storage.googleapis.com/storage/v1/b/{self.bucket}/o/{quote(f.remote_path, safe='')}"

    def local_relpath(self, f: RemoteFile) -> str:
        """Path of the file below raw/<dataset>/<version>/ (Windows-safe)."""
        rel = f.remote_path
        if rel.startswith(self.version_prefix):
            rel = rel[len(self.version_prefix):]
        return _WINDOWS_UNSAFE.sub("_", rel)

    def files_in_tiers(self, tiers: set[str] | None) -> list[RemoteFile]:
        return [f for f in self.files if tiers is None or f.tier in tiers]


# ---------------------------------------------------------------------------
# MaleCNS v1.0 (HHMI Janelia FlyEM + Cambridge + MRC LMB + Google)
# Pins observed via the GCS JSON API on 2026-09-22.
# ---------------------------------------------------------------------------
_FLAT = "v1.0/connectome-data/flat-connectome/"
_NPI = "v1.0/database/neuprint-inputs/"

MALECNS_V1_0 = DatasetSource(
    dataset="male-cns",
    version="v1.0",
    bucket="flyem-male-cns",
    version_prefix="v1.0/",
    neuprint_server="https://neuprint.janelia.org",
    neuprint_dataset="male-cns:v1.0",
    registered_on="2026-09-22",
    files=(
        # ---------------- metadata (small) ----------------
        RemoteFile(
            key="neuprint_meta_json",
            remote_path=_NPI + "Neuprint_Meta_debug.json",
            tier="metadata",
            description="neuPrint :Meta node for male-cns:v1.0 as JSON (ROI hierarchy, primary ROIs, "
                        "confidence thresholds, DVID uuid, totals).",
            size=1747811, crc32c_b64="ntczkQ==", generation=1780895254976045,
            md5_b64="0+slZvtwFbIsxqwZ8/Qa5Q==", updated="2026-06-08T05:07:35.037Z"),
        RemoteFile(
            key="neuprint_meta_csv",
            remote_path=_NPI + "Neuprint_Meta.csv",
            tier="metadata",
            description="neuPrint :Meta node as neo4j-import CSV (same content as the JSON variant).",
            size=1247784, crc32c_b64="qW0Qsg==", generation=1780895254951696,
            md5_b64="7p5VAAp+gYE8lZqIy8R4hg==", updated="2026-06-08T05:07:35.015Z"),
        RemoteFile(
            key="neuroglancer_scene",
            remote_path="v1.0/male-cns-v1.0.json",
            tier="metadata",
            description="Official neuroglancer scene; records the URLs of EM/segmentation/ROI/skeleton layers.",
            size=60253, crc32c_b64="52JkWQ==", generation=1778032077888581,
            md5_b64="Lvbruhomiy9TLfXFy2EK9g==", updated="2026-05-06T01:47:57.958Z"),
        # ---------------- core structured connectome ----------------
        RemoteFile(
            key="body_annotations",
            remote_path=_FLAT + "body-annotations-male-cns-v1.0-minconf-0.5.feather",
            tier="core",
            description="Curated body annotations (types, classes, sides, status, cross-dataset matches). "
                        "Excludes neurotransmitter properties.",
            size=14483314, crc32c_b64="vjz9cg==", generation=1780494878811468,
            md5_b64="UKdxh3DFciDxYLpPQxq4ng==", updated="2026-06-03T13:54:38.876Z"),
        RemoteFile(
            key="body_neurotransmitters",
            remote_path=_FLAT + "body-neurotransmitters-male-cns-v1.0.feather",
            tier="core",
            description="Aggregate neurotransmitter predictions per body and per cell type, "
                        "ground-truth labels where known, and consensus NT.",
            size=43282834, crc32c_b64="jcpNFg==", generation=1780894899156750,
            md5_b64="PYQrEv5cSe763lKNfdJKHw==", updated="2026-06-08T05:01:39.227Z"),
        RemoteFile(
            key="neuprint_neurons",
            remote_path=_NPI + "Neuprint_Neurons.feather",
            tier="core",
            description="All synaptic segments exactly as loaded into neuPrint (properties, per-ROI "
                        "pre/post roiInfo, :Segment/:Neuron labels).",
            size=4648794426, crc32c_b64="53OdcQ==", generation=1780895325252595,
            md5_b64=None, updated="2026-06-08T05:08:45.320Z"),
        RemoteFile(
            key="neuprint_connections",
            remote_path=_NPI + "Neuprint_Neuron_Connections.feather",
            tier="core",
            description="All segment->segment :ConnectsTo relationships as loaded into neuPrint "
                        "(weight, weightHP, weightHR, per-ROI roiInfo keyed by postsynaptic location).",
            size=3530452946, crc32c_b64="0I3Jjg==", generation=1780895322833388,
            md5_b64=None, updated="2026-06-08T05:08:42.989Z"),
        RemoteFile(
            key="flat_connectome_weights",
            remote_path=_FLAT + "connectome-weights-male-cns-v1.0-minconf-0.5.feather",
            tier="core",
            description="Flat segment->segment synapse-pair counts (independent official export; "
                        "used to cross-check the neuPrint connection table).",
            size=1051241946, crc32c_b64="dKRPVQ==", generation=1780494887545976,
            md5_b64="8w6dzKJc/QIb8eez2XVZng==", updated="2026-06-03T13:54:47.629Z"),
        # ---------------- synapse-level ----------------
        RemoteFile(
            key="syn_partners",
            remote_path=_FLAT + "syn-partners-male-cns-v1.0-minconf-0.5.feather",
            tier="synapses",
            description="Every pre->post synaptic partner pair (T-bar -> PSD) with coordinates (8 nm voxels), "
                        "confidences, body IDs and primary ROI of the postsynaptic point.",
            size=6777179098, crc32c_b64="jTlNIA==", generation=1780494942562468,
            md5_b64="WO/PcS+MTU3l8q1R6X3vdg==", updated="2026-06-03T13:55:42.664Z"),
        RemoteFile(
            key="tbar_neurotransmitters",
            remote_path=_FLAT + "tbar-neurotransmitters-male-cns-v1.0.feather",
            tier="synapses",
            description="Per-T-bar neurotransmitter prediction probabilities (7 classes) with location, "
                        "body, and ROI.",
            size=2651680218, crc32c_b64="RrR5/g==", generation=1780894927871192,
            md5_b64="UbAsEWkGYq7e8o+G05T/DQ==", updated="2026-06-08T05:02:07.977Z"),
        # ---------------- registered but not acquired by default ----------------
        RemoteFile(
            key="flat_connectome_weights_traced",
            remote_path=_FLAT + "connectome-weights-male-cns-v1.0-minconf-0.5-traced-only.feather",
            tier="optional",
            description="Flat weights restricted to bodies with statusLabel >= 'Leaves' (derivable from core).",
            size=508025642, crc32c_b64="iakIVA==", generation=1780494884279095,
            md5_b64="ZgHUrQr6mf0D6wh5Ze8kIw==", updated="2026-06-03T13:54:44.346Z"),
        RemoteFile(
            key="flat_connectome_weights_significant",
            remote_path=_FLAT + "connectome-weights-male-cns-v1.0-minconf-0.5-significant-only.feather",
            tier="optional",
            description="Flat weights restricted to bodies with statusLabel >= 'Sensory Anchor' (derivable from core).",
            size=502169298, crc32c_b64="RNohUA==", generation=1780494884449936,
            md5_b64="CfL4M/cWGkatM81vnJBy9g==", updated="2026-06-03T13:54:44.523Z"),
        RemoteFile(
            key="body_stats",
            remote_path=_FLAT + "body-stats-male-cns-v1.0-minconf-0.5.feather",
            tier="optional",
            description="Per-segment synapse count summary (redundant with neuprint_neurons).",
            size=778062826, crc32c_b64="MGOCPQ==", generation=1780494888472305,
            md5_b64="QEwzScKFgBSOFoFeuZ84Kg==", updated="2026-06-03T13:54:48.544Z"),
        RemoteFile(
            key="syn_points",
            remote_path=_FLAT + "syn-points-male-cns-v1.0-minconf-0.5.feather",
            tier="optional",
            description="Every synapse point (pre and post rows) with ROIs (13 GB; redundant for Phase 0).",
            size=13061489098, crc32c_b64="1E7gRw==", generation=1780494991007477,
            md5_b64="xp0IdY3gdYIDXMiENXRJOg==", updated="2026-06-03T13:56:31.123Z"),
    ),
    doc_pages={
        "download_page": "https://male-cns.janelia.org/download/",
        "release_notes": "https://male-cns.janelia.org/release/",
        "home": "https://male-cns.janelia.org/",
    },
    citation={
        "dataset": "MaleCNS v1.0 connectome (neuPrint dataset male-cns:v1.0), HHMI Janelia FlyEM, "
                   "University of Cambridge, MRC LMB and Google Research. https://male-cns.janelia.org/",
        "paper": "Berg S, Beckett IR, Costa M, Schlegel P, Januszewski M, et al. Sexual dimorphism in the "
                 "complete connectome of the Drosophila male central nervous system. "
                 "Cell (2026), published 2026-09-03, https://www.cell.com/cell/fulltext/S0092-8674(26)00942-6 ; "
                 "preprint bioRxiv 10.1101/2025.10.09.680999 (v2, 2025-10-30).",
        "note": "Verify the final author list/DOI against the Cell article before formal citation.",
    },
    license={
        "name": "CC-BY-4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/",
        "statement": "The Male CNS dataset is licensed under CC-BY (male-cns.janelia.org footer).",
    },
)

SOURCES: dict[tuple[str, str], DatasetSource] = {
    (MALECNS_V1_0.dataset, MALECNS_V1_0.version): MALECNS_V1_0,
}


def get_source(dataset: str, version: str) -> DatasetSource:
    try:
        return SOURCES[(dataset, version)]
    except KeyError:
        known = ", ".join(f"{d}:{v}" for d, v in SOURCES)
        raise KeyError(f"Unknown source {dataset}:{version}. Known: {known}") from None
