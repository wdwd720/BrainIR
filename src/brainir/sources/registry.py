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
    bucket: str | None = None
    """Bucket override for sources whose official files span several buckets (None = the dataset's bucket)."""
    local_name: str | None = None
    """Override of the path below raw/<dataset>/<version>/ (default: remote_path minus the version prefix)."""


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
    facts: dict = field(default_factory=dict)
    """Dataset-level facts for manifests: release_date, release_notes, animal (species/sex/n_animals), cns_coverage,
    voxel_size_nm, coordinate_space, documentation_urls."""

    def file(self, key: str) -> RemoteFile:
        for f in self.files:
            if f.key == key:
                return f
        raise KeyError(f"{self.dataset}:{self.version} has no registered file {key!r}")

    def bucket_of(self, f: RemoteFile) -> str:
        return f.bucket or self.bucket

    def url(self, f: RemoteFile) -> str:
        return f"https://storage.googleapis.com/{self.bucket_of(f)}/{quote(f.remote_path)}"

    def metadata_url(self, f: RemoteFile) -> str:
        return f"https://storage.googleapis.com/storage/v1/b/{self.bucket_of(f)}/o/{quote(f.remote_path, safe='')}"

    def local_relpath(self, f: RemoteFile) -> str:
        """Path of the file below raw/<dataset>/<version>/ (Windows-safe)."""
        rel = f.local_name or f.remote_path
        if not f.local_name and self.version_prefix and rel.startswith(self.version_prefix):
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
        "paper": "Berg S, Beckett IR, Costa M, Schlegel P, Januszewski M, et al. (incl. Rubin GM, Jefferis GSXE). "
                 "Sexual dimorphism in the complete Drosophila male central nervous system connectome. Cell (2026). "
                 "doi:10.1016/j.cell.2026.08.015 (PMID 42691995; first published 2026-09-01). Preprint: 'Sexual "
                 "dimorphism in the complete connectome of the Drosophila male central nervous system', bioRxiv "
                 "doi:10.1101/2025.10.09.680999 (v2, 2025-10-30), CC-BY 4.0.",
        "note": "Title/DOI verified via Europe PMC and bioRxiv on 2026-09-22; full Cell author list not re-checked.",
    },
    license={
        "name": "CC-BY-4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/",
        "statement": "The Male CNS dataset is licensed under CC-BY (male-cns.janelia.org footer).",
    },
    facts={
        "release_date": "2026-06-08",
        "release_notes": ["v1.0: minor proofreading changes; refinement of neuron annotations",
                          "v0.9 (2025-10-05): initial release"],
        "animal": {"species": "Drosophila melanogaster", "sex": "male", "n_animals": 1},
        "cns_coverage": "entire CNS: central brain, both optic lobes, ventral nerve cord (VNC)",
        "voxel_size_nm": [8.0, 8.0, 8.0],
        "coordinate_space": "male-cns v1.0 EM space",
        "documentation_urls": ["https://github.com/janelia-flyem/flyem-snapshot",
                               "https://connectome-neuprint.github.io/neuprint-python/docs/",
                               "https://www.biorxiv.org/content/10.1101/2025.10.09.680999v2",
                               "https://doi.org/10.1016/j.cell.2026.08.015"],
    },
)

# ---------------------------------------------------------------------------
# MANC (Male Adult Nerve Cord), HHMI Janelia FlyEM + Google + MRC LMB.
#
# Two official release lineages exist:
#
# * v1.0 (2023-06): complete neuPrint bulk export in gs://flyem-manc-exports/v1.0/
#   (neo4j input tables as feather, per-body property table, traced-neuron adjacency CSVs, synapse partners).
# * v1.2 (2024-03 segmentation; annotation snapshots v1.2 base 2024-09-16, v1.2.1 2024-09-27, v1.2.3 2025-09/10):
#   gs://manc-seg-v1p2/ holds the synapse-partner table of the v1.2 segmentation plus neuroglancer
#   "segment_properties" annotation snapshots. There is NO neuPrint bulk export for v1.2.x; BrainIR rebuilds
#   connectivity from the partner table and takes annotations from the snapshot that matches the requested
#   annotation version (see brainir.ingest.manc). neuPrint served manc:v1.2.1 from 2024-09 and manc:v1.2.3
#   from 2025-09 (file names manc-v1.2.x-neuprint-layers.json).
#
# Pins observed via the GCS JSON API on 2026-09-22.
# ---------------------------------------------------------------------------
_MANC_CITATION = {
    "dataset": "MANC (Male Adult Nerve Cord) connectome, HHMI Janelia FlyEM Project Team with Google Research and "
               "MRC LMB Cambridge. neuPrint datasets manc:v1.0 / manc:v1.2.1 / manc:v1.2.3. "
               "https://www.janelia.org/project-team/flyem/manc-connectome",
    "paper_reconstruction": "Takemura S-y, Hayworth KJ, Huang GB, Januszewski M, Lu Z, et al. A Connectome of the Male "
                            "Drosophila Ventral Nerve Cord. eLife 13:RP97769 (2024). doi:10.7554/eLife.97769",
    "paper_annotation": "Marin EC, Morris BJ, Stuerner T, Champion AS, Krzeminski D, et al. Systematic annotation of a "
                        "complete adult male Drosophila nerve cord connectome reveals principles of functional "
                        "organisation. eLife 13:RP97766 (2024). doi:10.7554/eLife.97766",
    "paper_premotor": "Cheong HSJ, Boone KN, Bennett MM, Salman F, Ralston JD, et al. Transforming descending input into "
                      "behavior: The organization of premotor circuits in the Drosophila Male Adult Nerve Cord connectome. "
                      "eLife 13:RP96084 (version of record 2026-07-20; reviewed preprint 2024). doi:10.7554/eLife.96084",
    "neuprint": "Plaza SM, Clements J, Dolafi T, Umayam L, Neubarth NN, Scheffer LK, Berg S. neuPrint: An open access tool "
                "for EM connectomics. Front. Neuroinform. 16:896292 (2022). doi:10.3389/fninf.2022.896292",
    "nt_prediction": "Eckstein N, Bates AS, Champion A, et al. Neurotransmitter classification from electron microscopy "
                     "images at synaptic sites in Drosophila melanogaster. Cell 187(10):2574-2594 (2024). "
                     "doi:10.1016/j.cell.2024.03.016 (MANC predictions described in Takemura et al. Methods 2.10)",
    "note": "DOIs verified via Crossref on 2026-09-22 (research/manc_release_notes.md). Takemura and Marin are eLife "
            "reviewed preprints without a version of record as of that date.",
}
_MANC_LICENSE = {
    "name": "CC-BY-4.0",
    "url": "https://creativecommons.org/licenses/by/4.0/",
    "statement": "Janelia MANC release page: 'The MANC is licensed under CC-BY.' (linking to CC BY 4.0); the buckets and "
                 "neuPrint dataset descriptions carry no separate license text.",
}
_MANC_DOCS = {
    "home": "https://www.janelia.org/project-team/flyem/manc-connectome",
    "neuprint": "https://neuprint.janelia.org/",
}
_MANC_FACTS_COMMON = {
    "animal": {"species": "Drosophila melanogaster", "sex": "male", "n_animals": 1},
    "cns_coverage": "ventral nerve cord (VNC) only: thoracic and abdominal neuromeres, cervical connective; no brain",
    "voxel_size_nm": [8.0, 8.0, 8.0],
    "coordinate_space": "manc EM space (v1.0 and v1.2 share the volume alignment)",
    "documentation_urls": ["https://github.com/connectome-neuprint/neuprint-python",
                           "https://doi.org/10.7554/eLife.97769", "https://doi.org/10.7554/eLife.97766",
                           "https://doi.org/10.7554/eLife.96084"],
}
_MANC_FACTS_V1_0 = {**_MANC_FACTS_COMMON, "release_date": "2023-06-12",
                    "release_notes": ["v1.0 (2023-06): first public release; neuPrint manc:v1.0 database export 2023-06-12; "
                                      "per-body property export 2023-06-05; traced-adjacency export 2023-06-02"]}
_MANC_FACTS_V1_2 = {**_MANC_FACTS_COMMON, "release_date": "2024-03-11",
                    "release_notes": ["v1.2 segmentation and synapse-partner table (2024-03-11)",
                                      "v1.2.1 annotation snapshot (2024-09-27; neuPrint manc:v1.2.1)",
                                      "v1.2.3 annotation snapshot (2025-09-26 / 2025-10-26; neuPrint manc:v1.2.3)",
                                      "no neuPrint bulk export exists for v1.2.x; BrainIR rebuilds connectivity from the partner table"]}

_M10 = "v1.0/neuprint_manc_v1.0/neuprint_manc_v1.0_ftr/"

MANC_V1_0 = DatasetSource(
    dataset="manc",
    version="v1.0",
    bucket="flyem-manc-exports",
    version_prefix="v1.0/",
    neuprint_server="https://neuprint.janelia.org",
    neuprint_dataset="manc:v1.0",
    registered_on="2026-09-22",
    files=(
        # ---------------- metadata (small) ----------------
        RemoteFile(
            key="neuprint_readme",
            remote_path="v1.0/neuprint_manc_v1.0/README",
            tier="metadata",
            description="README of the neuPrint bulk export (CSV tarball + feather representations).",
            size=287, crc32c_b64="rVbbXg==", generation=1685999328996099,
            md5_b64="rvY0KaEkKDMsLIJZMCdpbg==", updated="2023-06-05T21:08:49.062Z"),
        RemoteFile(
            key="neuprint_meta",
            remote_path=_M10 + "Neuprint_Meta_manc_v1.ftr",
            tier="metadata",
            description="neuPrint :Meta node for manc:v1.0 (ROI hierarchy, primary/neuropil/nerve ROIs, confidence "
                        "thresholds, DVID uuid, totals) as a one-row feather table.",
            size=28146, crc32c_b64="5OV4pg==", generation=1685999470391208,
            md5_b64="5trku1Xgkb0ya+U2IbWhGw==", updated="2023-06-05T21:11:10.431Z"),
        RemoteFile(
            key="neuprint_all_rois",
            remote_path=_M10 + "all_ROIs.txt",
            tier="metadata",
            description="List of every ROI name used in the neuPrint manc:v1.0 database.",
            size=594, crc32c_b64="02SVDQ==", generation=1685999470203866,
            md5_b64="Wc4sCLnP9AB9kRRxcVSq/A==", updated="2023-06-05T21:11:10.243Z"),
        RemoteFile(
            key="traced_readme",
            remote_path="v1.0/manc-traced-adjacencies-v1.0/README",
            tier="metadata",
            description="README of the traced-neuron adjacency export (documents the neuprint-python call used).",
            size=1195, crc32c_b64="BFv0hw==", generation=1685678226604719,
            md5_b64="E5cOjhEvloMhpfNggdjRcg==", updated="2023-06-02T03:57:06.650Z"),
        # ---------------- core structured connectome ----------------
        RemoteFile(
            key="neuron_properties",
            remote_path="v1.0/manc-v1.0-neuron-properties.feather",
            tier="core",
            description="Per-body properties of all 102,369 synaptic bodies (types, classes, hemilineage, soma side/"
                        "neuromere, status, body-level NT probabilities, per-ROI roiInfo).",
            size=17188218, crc32c_b64="Lrg1Eg==", generation=1685939278333965,
            md5_b64="9GcxF1WcxyfhvvywIrahQw==", updated="2023-06-05T04:27:58.376Z"),
        RemoteFile(
            key="neuprint_neurons",
            remote_path=_M10 + "Neuprint_Neurons_manc_v1.ftr",
            tier="core",
            description="All segments exactly as loaded into neuPrint manc:v1.0 (properties, per-ROI roiInfo, "
                        ":Segment/:Neuron labels).",
            size=917907106, crc32c_b64="pTYB+w==", generation=1686604209780762,
            md5_b64="DF3xT62WEdxGfh5Qu7hgXg==", updated="2023-06-12T21:10:09.932Z"),
        RemoteFile(
            key="neuprint_connections",
            remote_path=_M10 + "Neuprint_Neuron_Connections_manc_v1.ftr",
            tier="core",
            description="All segment->segment :ConnectsTo relationships as loaded into neuPrint manc:v1.0 (weight, "
                        "weightHP, weightHR, per-ROI roiInfo keyed by postsynaptic location).",
            size=736271930, crc32c_b64="jgFf3g==", generation=1685999379563263,
            md5_b64="+zriE/4pr2alW+TwX22zFw==", updated="2023-06-05T21:09:39.608Z"),
        RemoteFile(
            key="traced_neurons",
            remote_path="v1.0/manc-traced-adjacencies-v1.0/traced-neurons.csv",
            tier="core",
            description="Independent export of the traced neurons (bodyId, type, instance) via neuprint-python "
                        "fetch_traced_adjacencies.",
            size=629548, crc32c_b64="2OSg2w==", generation=1685678226631730,
            md5_b64="aaeazrfgVIhfTkc2TyOcag==", updated="2023-06-02T03:57:06.672Z"),
        RemoteFile(
            key="traced_connections",
            remote_path="v1.0/manc-traced-adjacencies-v1.0/traced-connections.csv",
            tier="core",
            description="Independent export of traced-neuron connection weights (used to cross-check the neuPrint "
                        "connection table).",
            size=75262163, crc32c_b64="HtjDiw==", generation=1685678227570342,
            md5_b64="xUPcmgw2fZ98iJAdiS14oA==", updated="2023-06-02T03:57:07.625Z"),
        RemoteFile(
            key="traced_connections_per_roi",
            remote_path="v1.0/manc-traced-adjacencies-v1.0/traced-connections-per-roi.csv",
            tier="core",
            description="Traced-neuron connections split by primary ROI (NotPrimary remainder).",
            size=159195790, crc32c_b64="z2Zc/Q==", generation=1685678228693057,
            md5_b64="+L2c7fki+XSRoL8sVv7A/g==", updated="2023-06-02T03:57:08.733Z"),
        # ---------------- synapse-level ----------------
        RemoteFile(
            key="syn_partners",
            remote_path="v1.0/manc-synapse-partners-2023-05-03-215e08-minconf-0.0.feather.bz2",
            tier="synapses",
            description="Every pre->post synaptic partner pair with coordinates, confidences and body IDs at minconf 0.0 "
                        "(bzip2-compressed feather).",
            size=1117661989, crc32c_b64="4d2EIw==", generation=1685678232545414,
            md5_b64="XC2FAlJnU/cHHGNSPsHnmw==", updated="2023-06-02T03:57:12.604Z"),
        # ---------------- registered but not acquired by default ----------------
        RemoteFile(
            key="neuprint_synapses",
            remote_path=_M10 + "Neuprint_Synapses_manc_v1.ftr",
            tier="optional",
            description="All :Synapse nodes as loaded into neuPrint (3.9 GB; redundant with syn_partners).",
            size=3885378106, crc32c_b64="ircDWw==", generation=1685999438226620,
            md5_b64="1+V41R18S9TtCnfQYSwuiw==", updated="2023-06-05T21:10:38.279Z"),
        RemoteFile(
            key="neuprint_synapse_connections",
            remote_path=_M10 + "Neuprint_Synapse_Connections_manc_v1.ftr",
            tier="optional",
            description="Synapse->synapse :SynapsesTo relationships (redundant with syn_partners).",
            size=619827626, crc32c_b64="9sjMJA==", generation=1685999395351716,
            md5_b64="3Mn0VNZq7X4CIbs6KA+3Ww==", updated="2023-06-05T21:09:55.399Z"),
        RemoteFile(
            key="neuprint_csv_tarball",
            remote_path="v1.0/neuprint_manc_v1.0/neuprint_manc_v1.0_csv.tar.gz",
            tier="optional",
            description="neo4j import CSVs of the whole database (5.3 GB; redundant with the feather files).",
            size=5291966339, crc32c_b64="H+b1sA==", generation=1686604888626480,
            md5_b64="+Z405JuaZlKGKdsOzRMYCA==", updated="2023-06-12T21:21:28.789Z"),
    ),
    doc_pages=_MANC_DOCS,
    citation=_MANC_CITATION,
    license=_MANC_LICENSE,
    facts=_MANC_FACTS_V1_0,
)

_SP123 = "manc-seg-v1.2/segment_properties_v1.2.3/"

MANC_V1_2 = DatasetSource(
    dataset="manc",
    version="v1.2",
    bucket="manc-seg-v1p2",
    version_prefix="",
    neuprint_server="https://neuprint.janelia.org",
    neuprint_dataset="manc:v1.2.1 / manc:v1.2.3 (rebuilt from public files; no bulk export exists)",
    registered_on="2026-09-22",
    files=(
        # ---------------- core: synapses of the v1.2 segmentation ----------------
        RemoteFile(
            key="syn_partners",
            remote_path="manc-v1.2-synapse-partners-minconf-0.0.feather",
            tier="core",
            description="Every pre->post synaptic partner pair of the v1.2 segmentation with coordinates (8 nm voxels), "
                        "pre/post confidences, body IDs and primary ROI of the postsynaptic point, at minconf 0.0.",
            size=1937212010, crc32c_b64="iIVTBA==", generation=1710183071419668,
            md5_b64="B2Np+rqyLEhmTIhWvNyesQ==", updated="2026-08-20T17:23:00.319Z"),
        # ---------------- core: annotation snapshots ----------------
        RemoteFile(
            key="segprops_v1_2_1_info",
            remote_path="manc-seg-v1.2/segment_properties_v1.2.1/info",
            tier="core",
            description="v1.2.1 annotation snapshot (2024-09-27): type, PreSyn, PostSyn and tagged properties for "
                        "24,143 bodies - the annotation state served by neuPrint manc:v1.2.1.",
            size=1736018, crc32c_b64="36wfNA==", generation=1727452318850851,
            md5_b64="KCOpMbGDP7bVMdSd/gMr8w==", updated="2026-08-02T18:44:48.914Z"),
        RemoteFile(
            key="segprops_v1_2_3_combined",
            remote_path=_SP123 + "combined_properties/info",
            tier="core",
            description="v1.2.3 annotations: type, group, serial, cluster, origin, VFB id, synapse counts and tagged "
                        "categorical properties (class, hemilineage, soma side, cell-type predicted NT, nerves, ...).",
            size=3019993, crc32c_b64="WhEV8A==", generation=1761508981164722,
            md5_b64="XYoI7RtD/sZt/ZaMw+BCSg==", updated="2026-08-20T17:17:49.000Z"),
        RemoteFile(
            key="segprops_v1_2_3_type",
            remote_path=_SP123 + "type_property/info",
            tier="core",
            description="v1.2.3 cell types per body.",
            size=490152, crc32c_b64="iYTqMQ==", generation=1761508982184485,
            md5_b64="oaOUH3diSt/afPncP+bA2A==", updated="2025-10-26T20:03:02.292Z"),
        RemoteFile(
            key="segprops_v1_2_3_type_and_group",
            remote_path=_SP123 + "type_and_group_property/info",
            tier="core",
            description="v1.2.3 cell type + group per body.",
            size=655101, crc32c_b64="xL8bHA==", generation=1761508979557500,
            md5_b64="Lc2GabzjEVpIak1g8r8jLQ==", updated="2025-10-26T20:02:59.688Z"),
        RemoteFile(
            key="segprops_v1_2_3_instance",
            remote_path=_SP123 + "instance_property/info",
            tier="core",
            description="v1.2.3 instance names per body.",
            size=630118, crc32c_b64="TPnw/g==", generation=1761508983605612,
            md5_b64="Xi03EqQ88Wf7mrBwQne/jQ==", updated="2026-04-17T15:53:28.333Z"),
        RemoteFile(
            key="segprops_v1_2_3_tags",
            remote_path=_SP123 + "tags_property/info",
            tier="core",
            description="v1.2.3 tagged categorical annotations per body.",
            size=1106590, crc32c_b64="1ttRxg==", generation=1761508981744200,
            md5_b64="1qiyThMFgc8vpCl3bVtVuw==", updated="2025-10-26T20:03:01.853Z"),
        RemoteFile(
            key="segprops_v1_2_3_numeric",
            remote_path=_SP123 + "numeric_properties/info",
            tier="core",
            description="v1.2.3 per-body synapse counts (syn_pre, syn_post, syn_downstream, syn_connections).",
            size=736706, crc32c_b64="az5xbA==", generation=1761508980077797,
            md5_b64="AyVeVRB6gA6B1u912xGXLg==", updated="2026-04-17T15:53:28.333Z"),
        # ---------------- metadata ----------------
        RemoteFile(
            key="segmentation_info",
            remote_path="manc-seg-v1.2/info",
            tier="metadata",
            description="neuroglancer info of the v1.2 segmentation (declares segment_properties_v1.2.3 as the current "
                        "annotation set).",
            size=4785, crc32c_b64="A+ctaA==", generation=1758852898970323,
            md5_b64="bOP8JRrB7j+YZtI74hwzYw==", updated="2025-09-26T02:14:59.141Z"),
        RemoteFile(
            key="segprops_v1_2_3_info",
            remote_path=_SP123 + "info",
            tier="metadata",
            description="v1.2.3 segment properties (single-file variant, 2025-09-26).",
            size=3903950, crc32c_b64="t4IvGg==", generation=1758852423072514,
            md5_b64="ieqXnF6xpiUgh31oo8lvag==", updated="2025-09-26T02:07:03.121Z"),
        RemoteFile(
            key="segprops_v1_2_3_clio_combined",
            remote_path=_SP123 + "clio/combined_properties_clio/info",
            tier="metadata",
            description="Clio variant of the v1.2.3 combined properties.",
            size=3020153, crc32c_b64="e8EyYQ==", generation=1761508983155410,
            md5_b64="clWK7fcKDbToAOcluOGCTQ==", updated="2026-09-11T17:49:33.088Z"),
        RemoteFile(
            key="segprops_v1_2_base_info",
            remote_path="manc-seg-v1.2/segment_properties/info",
            tier="metadata",
            description="Initial v1.2 segment properties (2024-09-16) for 27,046 bodies.",
            size=1939689, crc32c_b64="bA2zYw==", generation=1726519902371262,
            md5_b64="5F8FS0O8dyl9qg8M5en8Dg==", updated="2026-08-20T17:25:12.394Z"),
        RemoteFile(
            key="numeric_properties_all",
            remote_path="manc-seg-v1.2/numeric_properties/info",
            tier="metadata",
            description="Synapse counts for all 102,158 synaptic bodies of the v1.2 segmentation (2025-09-26).",
            size=2869784, crc32c_b64="wlWGIA==", generation=1758853523914512,
            md5_b64="O+cPbDtdodRP5HKAaQ5A6Q==", updated="2025-09-26T02:25:23.954Z"),
        RemoteFile(
            key="clio_info",
            remote_path="manc-seg-v1.2/clio/info",
            tier="metadata",
            description="neuroglancer info of the Clio view of the v1.2 segmentation.",
            size=4848, crc32c_b64="VIRvpg==", generation=1760972143713311,
            md5_b64="g59V4qsqX9wmq3tOgiUQig==", updated="2025-10-20T14:55:43.755Z"),
        RemoteFile(
            key="scene_v1_2_1_neuprint_layers",
            remote_path="manc-v1.2.1-neuprint-layers.json",
            tier="metadata",
            description="neuroglancer layers used by neuPrint manc:v1.2.1 (2024-09-27).",
            size=11633, crc32c_b64="8RUNLQ==", generation=1727452870346236,
            md5_b64="U1M6vpxfrv6ucE98iyqTQQ==", updated="2024-09-27T16:01:10.447Z"),
        RemoteFile(
            key="scene_v1_2_3_neuprint_layers",
            remote_path="manc-v1.2.3-neuprint-layers.json",
            tier="metadata",
            description="neuroglancer layers used by neuPrint manc:v1.2.3 (2025-09-26).",
            size=10898, crc32c_b64="tJCwAw==", generation=1758856596600762,
            md5_b64="ED613PnWWkqDk+rJKJMvDg==", updated="2025-09-26T03:16:36.690Z"),
        RemoteFile(
            key="scene_v1_2_3",
            remote_path="manc-v1.2.3.json",
            tier="metadata",
            description="Official neuroglancer scene for MANC v1.2.3 (2025-10-20).",
            size=11054, crc32c_b64="owIFNw==", generation=1760978784827499,
            md5_b64="qCrCyNNdPidoflzqTog9/Q==", updated="2025-10-20T16:46:24.921Z"),
        RemoteFile(
            key="scene_v1_2_3_clio",
            remote_path="manc-v1.2.3-clio.json",
            tier="metadata",
            description="Official Clio scene for MANC v1.2.3 (2025-10-20).",
            size=10174, crc32c_b64="a6Ri0Q==", generation=1760978773568458,
            md5_b64="KCNsWwyDk0gLGyryeiwD9Q==", updated="2025-10-20T16:46:13.663Z"),
    ),
    doc_pages=_MANC_DOCS,
    citation=_MANC_CITATION,
    license=_MANC_LICENSE,
    facts=_MANC_FACTS_V1_2,
)

SOURCES: dict[tuple[str, str], DatasetSource] = {
    (s.dataset, s.version): s for s in (MALECNS_V1_0, MANC_V1_0, MANC_V1_2)
}

BUILD_VERSIONS: dict[tuple[str, str], tuple[DatasetSource, str]] = {
    # processed build (dataset, version) -> (raw source, build version). Raw MANC v1.2 yields two builds that differ only
    # in the annotation snapshot (see brainir.ingest.manc.ANNOTATION_SNAPSHOTS).
    ("male-cns", "v1.0"): (MALECNS_V1_0, "v1.0"),
    ("manc", "v1.0"): (MANC_V1_0, "v1.0"),
    ("manc", "v1.2.1"): (MANC_V1_2, "v1.2.1"),
    ("manc", "v1.2.3"): (MANC_V1_2, "v1.2.3"),
}


def get_source(dataset: str, version: str) -> DatasetSource:
    """Raw source registered under (dataset, version); build versions (e.g. manc v1.2.1) resolve to their raw source."""
    if (dataset, version) in SOURCES:
        return SOURCES[(dataset, version)]
    if (dataset, version) in BUILD_VERSIONS:
        return BUILD_VERSIONS[(dataset, version)][0]
    known = ", ".join(f"{d}:{v}" for d, v in sorted(set(SOURCES) | set(BUILD_VERSIONS)))
    raise KeyError(f"Unknown source {dataset}:{version}. Known: {known}")


def resolve_build(dataset: str, version: str) -> tuple[DatasetSource, str]:
    """(raw source, build version) for a processed dataset version."""
    if (dataset, version) in BUILD_VERSIONS:
        return BUILD_VERSIONS[(dataset, version)]
    known = ", ".join(f"{d}:{v}" for d, v in sorted(BUILD_VERSIONS))
    raise KeyError(f"No processed build is defined for {dataset}:{version}. Known builds: {known}")
