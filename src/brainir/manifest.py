"""Machine-readable dataset manifests (committed to git under data/manifests/).

A manifest answers: exactly which official files (by URL, GCS generation and
checksum) entered the processed tables, how they were transformed, what the
outputs are (by checksum/row count/schema), what validation found, and how to
cite/licence the data.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pyarrow.dataset as pads

from . import paths
from .io import schema_record
from .sources.registry import DatasetSource

MANIFEST_SCHEMA_VERSION = "1.0"

TRANSFORMATIONS = [
    {"step": "acquire", "code_ref": "brainir.acquire.acquire_dataset",
     "description": "HTTPS ranged download from the public GCS bucket; bytes verified against server CRC32C (and MD5 "
                    "where available); GCS generation pinned in brainir.sources.registry; SHA-256 recorded; raw files "
                    "set read-only."},
    {"step": "neuropils", "code_ref": "brainir.ingest.malecns.build_neuropils",
     "description": "ROI catalogue from the neuPrint :Meta roiHierarchy/roiInfo; primary ROIs = neuPrint primaryRois."},
    {"step": "annotations", "code_ref": "brainir.ingest.malecns.load_annotations",
     "description": "Flat body annotations loaded verbatim; float-encoded integer columns (group, mancBodyid, ...) "
                    "cast to int64 only after verifying every value is integral and < 2^53."},
    {"step": "neuron_definition", "code_ref": "brainir.ingest.malecns.build",
     "description": "neurons = bodies with a non-null superclass (source paper's definition). Other bodies = fragments."},
    {"step": "neuron_properties", "code_ref": "brainir.ingest.malecns.scan_neuprint_neurons",
     "description": "pre/post/downstream/upstream/size/:Neuron label taken from the neuPrint neuron table; per-neuron "
                    "roiInfo exploded to primary ROIs with an explicit '<unassigned>' remainder."},
    {"step": "connections", "code_ref": "brainir.ingest.malecns.scan_connections",
     "description": "neuPrint :ConnectsTo table filtered to neuron->neuron pairs; weight -> synapse_count, "
                    "weightHP -> synapse_count_hp; weightHR dropped only if identical to weight (validated). "
                    "Autapses kept and flagged. Edge roiInfo (postsynaptic location) exploded to primary ROIs with an "
                    "'<unassigned>' remainder so per-edge neuropil counts sum exactly to synapse_count."},
    {"step": "neurotransmitters", "code_ref": "brainir.ingest.malecns.assemble_neurons",
     "description": "Body- and type-level NT predictions, literature label and consensus copied verbatim from the "
                    "flat NT export (ML predictions; not physiology). Sign hypotheses are NOT stored; they are "
                    "computed on demand by the graph layer under rule brainir.sign.conventional-v1."},
    {"step": "validate", "code_ref": "brainir.ingest.malecns (checks) + brainir.validation",
     "description": "IDs, uniqueness, duplicates, referential integrity, edge values, type/schema conformance, "
                    "annotation coverage, directionality (exact edge-sum conservation + biological polarity), graph "
                    "statistics, provenance, cross-source agreement (flat vs neuPrint exports), synapse-level "
                    "recomputation on a seeded random neuron sample."},
    {"step": "write", "code_ref": "brainir.io.write_canonical",
     "description": "Rows sorted by primary key, dictionaries normalised, Parquet (zstd level 3, 1M-row groups) -> "
                    "byte-identical outputs for identical inputs and library versions (see uv.lock)."},
]


def raw_file_profile(path: Path) -> dict:
    """Schema + row count of a raw file (Arrow IPC or JSON/CSV)."""
    if path.suffix == ".feather":
        ds = pads.dataset(str(path), format="ipc")
        return {"format": "arrow-ipc (feather v2)", "rows": int(ds.count_rows()), "schema": schema_record(ds.schema)}
    if path.suffix == ".json":
        return {"format": "json"}
    if path.suffix == ".csv":
        return {"format": "csv"}
    return {"format": path.suffix.lstrip(".") or "unknown"}


def build_manifest(source: DatasetSource, build_info: dict, report_dict: dict, out_dir: Path) -> dict:
    raw = paths.raw_dir(source.dataset, source.version)
    acq_path = raw / "_acquisition.json"
    acq = json.loads(acq_path.read_text()) if acq_path.exists() else {"files": [], "doc_snapshots": []}
    files = []
    for rec in acq["files"]:
        local = raw / source.local_relpath(source.file(rec["key"]))
        prof = raw_file_profile(local) if local.exists() else {"missing": True}
        files.append({
            "key": rec["key"], "tier": rec["tier"], "description": rec["description"],
            "remote_url": rec["remote_url"], "remote_path": rec["remote_path"],
            "gcs_generation": rec["remote_metadata"]["generation"], "gcs_updated": rec["remote_metadata"]["updated"],
            "size_bytes": rec["size_bytes"], "crc32c_b64": rec["local_digests"]["crc32c_b64"],
            "md5_b64": rec["local_digests"]["md5_b64"], "sha256": rec["local_digests"]["sha256"],
            "local_path": rec["local_path"], "acquired_at_utc": rec["acquired_at_utc"],
            "used_by_pipeline": rec["key"] in build_info.get("inputs", {}),
            **prof,
        })
    warn_fail = [{"check_id": c["check_id"], "status": c["status"], "observed": c["observed"], "expected": c["expected"],
                  "description": c["description"]}
                 for c in report_dict["checks"] if c["status"] in ("fail", "warn")]
    acquired = sorted(f["acquired_at_utc"] for f in files) if files else []
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset": source.dataset,
        "version": source.version,
        "neuprint_dataset": source.neuprint_dataset,
        "neuprint_server": source.neuprint_server,
        "animal": {"species": "Drosophila melanogaster", "sex": "male", "n_animals": 1,
                   "cns_coverage": "entire CNS: central brain, both optic lobes, ventral nerve cord (VNC)"},
        "release": {"date": "2026-06-08", "notes": ["v1.0: minor proofreading changes; refinement of neuron annotations",
                                                     "v0.9 (2025-10-05): initial release"],
                    "neuprint_snapshot": build_info.get("neuprint_meta")},
        "official_source": {"bucket": f"gs://{source.bucket}/{source.version_prefix}", "landing_page": source.doc_pages.get("home"),
                            "download_page": source.doc_pages.get("download_page"),
                            "release_notes": source.doc_pages.get("release_notes")},
        "documentation_urls": sorted(set(source.doc_pages.values()) | {
            "https://github.com/janelia-flyem/flyem-snapshot",
            "https://connectome-neuprint.github.io/neuprint-python/docs/",
            "https://www.biorxiv.org/content/10.1101/2025.10.09.680999v2",
            "https://doi.org/10.1016/j.cell.2026.08.015"}),
        "documentation_snapshots": acq.get("doc_snapshots", []),
        "citation": source.citation,
        "license": source.license,
        "acquisition": {"method": TRANSFORMATIONS[0]["description"],
                        "first_acquired_utc": acquired[0] if acquired else None,
                        "last_acquired_utc": acquired[-1] if acquired else None,
                        "files": files},
        "definitions": {
            "neuron": "body with non-null superclass (Berg et al. Methods: 'Bodies in the dataset are defined as neurons "
                      "if they have a superclass. Bodies without one are fragments of neurons.')",
            "synapse_count": "number of T-bar->PSD pairs (synaptic connections) with conf_pre>=0.5 and conf_post>=0.5; "
                             "polyadic: one T-bar can contribute several pairs. Equals neuPrint ConnectsTo.weight.",
            "synapse_count_hp": "subset with conf_post>=0.7 (neuPrint weightHP).",
            "edge_neuropil": "primary ROI containing the POSTsynaptic density (neuPrint convention).",
            "autapse": "pre_id == post_id; retained and flagged, not dropped.",
            "coordinates": "8 nm isotropic voxels in the MaleCNS EM space (voxelSize 8,8,8 nm).",
        },
        "transformations": TRANSFORMATIONS,
        "processed_outputs": build_info.get("outputs", {}),
        "graph_statistics": build_info.get("graph_statistics"),
        "annotation_coverage": build_info.get("coverage"),
        "validation": {"summary": report_dict["summary"], "report_json": f"data/manifests/{source.dataset}_{source.version}.validation.json",
                       "report_markdown": f"data/manifests/{source.dataset}_{source.version}.validation.md",
                       "fail_and_warn_checks": warn_fail},
        "build": {k: build_info.get(k) for k in ("pipeline", "pipeline_version", "brainir_version", "schema_version",
                                                  "config", "git", "environment", "timings_s", "total_s")},
    }


def write_manifest(source: DatasetSource, build_info: dict, report_dict: dict, out_dir: Path) -> Path:
    mdir = paths.manifests_dir()
    mdir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(source, build_info, report_dict, out_dir)
    stem = f"{source.dataset}_{source.version}"
    path = mdir / f"{stem}.manifest.json"
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    for ext in ("json", "md"):
        src = out_dir / f"validation_report.{ext}"
        if src.exists():
            shutil.copyfile(src, mdir / f"{stem}.validation.{ext}")
    return path
