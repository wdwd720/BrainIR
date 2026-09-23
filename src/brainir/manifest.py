"""Machine-readable dataset manifests (committed to git under data/manifests/).

A manifest answers: exactly which official files (by URL, GCS generation and
checksum) entered the processed tables, how they were transformed, what the
outputs are (by checksum/row count/schema), what validation found, and how to
cite/licence the data. Dataset-level facts (release dates, coverage, voxel size)
come from the source registry; build-level facts (neuron definition, count rule,
annotation snapshot) come from the adapter's ``build_info``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pyarrow.dataset as pads

from . import paths
from .io import schema_record
from .sources.registry import SOURCES, DatasetSource

MANIFEST_SCHEMA_VERSION = "1.1"

ACQUIRE_STEP = {
    "step": "acquire", "code_ref": "brainir.acquire.acquire_dataset",
    "description": "HTTPS ranged download from the public GCS bucket; bytes verified against server CRC32C (and MD5 "
                   "where available); GCS generation pinned in brainir.sources.registry; SHA-256 recorded; raw files "
                   "set read-only."}

WRITE_STEP = {
    "step": "write", "code_ref": "brainir.io.write_canonical",
    "description": "Rows sorted by primary key, dictionaries normalised, Parquet (zstd level 3, 1M-row groups) -> "
                   "byte-identical outputs for identical inputs and library versions (see uv.lock)."}

VALIDATE_STEP = {
    "step": "validate", "code_ref": "brainir.ingest.common (checks) + adapter checks + brainir.validation",
    "description": "IDs, uniqueness, duplicates, referential integrity, edge values, type/schema conformance, "
                   "annotation coverage, directionality (exact edge-sum conservation + biological polarity), graph "
                   "statistics, provenance, cross-source agreement between independent official exports, synapse-level "
                   "recomputation on a seeded random neuron sample."}

TRANSFORMATIONS_MALECNS = [
    ACQUIRE_STEP,
    {"step": "neuropils", "code_ref": "brainir.ingest.common.build_neuropils",
     "description": "ROI catalogue from the neuPrint :Meta roiHierarchy/roiInfo; primary ROIs = neuPrint primaryRois."},
    {"step": "annotations", "code_ref": "brainir.ingest.malecns.load_annotations",
     "description": "Flat body annotations loaded verbatim; float-encoded integer columns (group, mancBodyid, ...) "
                    "cast to int64 only after verifying every value is integral and < 2^53."},
    {"step": "neuron_definition", "code_ref": "brainir.ingest.malecns.build",
     "description": "neurons = bodies with a non-null superclass (source paper's definition). Other bodies = fragments."},
    {"step": "neuron_properties", "code_ref": "brainir.ingest.malecns.scan_neuprint_neurons",
     "description": "pre/post/downstream/upstream/size/:Neuron label taken from the neuPrint neuron table; per-neuron "
                    "roiInfo exploded to primary ROIs with an explicit '<unassigned>' remainder."},
    {"step": "connections", "code_ref": "brainir.ingest.common.scan_connections",
     "description": "neuPrint :ConnectsTo table filtered to neuron->neuron pairs; weight -> synapse_count, "
                    "weightHP -> synapse_count_hp; weightHR dropped only if identical to weight (validated). "
                    "Autapses kept and flagged. Edge roiInfo (postsynaptic location) exploded to primary ROIs with an "
                    "'<unassigned>' remainder so per-edge neuropil counts sum exactly to synapse_count."},
    {"step": "neurotransmitters", "code_ref": "brainir.ingest.malecns.assemble_neurons",
     "description": "Body- and type-level NT predictions, literature label and consensus copied verbatim from the "
                    "flat NT export (ML predictions; not physiology). Sign hypotheses are NOT stored; they are "
                    "computed on demand by the graph layer under rule brainir.sign.conventional-v1."},
    VALIDATE_STEP, WRITE_STEP,
]

TRANSFORMATIONS_MANC_V1_0 = [
    ACQUIRE_STEP,
    {"step": "neuropils", "code_ref": "brainir.ingest.common.build_neuropils",
     "description": "ROI catalogue from the neuPrint :Meta roiInfo/primaryRois/nerveRois (the Meta roiHierarchy is stale: it "
                    "lists IntNp(T*)/AMNp instead of LegNp(T*)/Ov and is not treated as authoritative; the roiInfo parent "
                    "typo 'ventral nerve core' is aliased to 'ventral nerve cord'). top_level_region = 'VNC' for every ROI."},
    {"step": "annotations", "code_ref": "brainir.ingest.manc.load_properties_v10",
     "description": "Per-body property export (2023-06-05) loaded verbatim; literal 'None'/'TBD'/'NA' placeholders -> null; "
                    "float-encoded integers (group, serial, subcluster) cast to int64 after an integrality check; 'class' "
                    "normalised to underscores in super_class; MANC hemilineage -> hemilineage_truman; RHS/LHS -> R/L."},
    {"step": "neuron_definition", "code_ref": "brainir.ingest.manc.build_v10",
     "description": "neurons = neuPrint :Neuron bodies with neuPrint status 'Traced' (23,514 in the 2023-06-12 database "
                    "export). 314 of them are 'RT Orphan' in the property export (recorded); typed non-Traced bodies "
                    "(e.g. PRT Orphan) are excluded."},
    {"step": "neuron_properties", "code_ref": "brainir.ingest.manc.scan_neuprint_neurons_v10",
     "description": "pre/post/downstream/upstream/size/status from the neuPrint neuron table; per-neuron roiInfo exploded to "
                    "primary ROIs with an explicit '<unassigned>' remainder; cross-checked field by field against the "
                    "property export and the traced-adjacency CSVs."},
    {"step": "connections", "code_ref": "brainir.ingest.common.scan_connections",
     "description": "neuPrint :ConnectsTo table filtered to neuron->neuron pairs; weight -> synapse_count, weightHP -> "
                    "synapse_count_hp. Rows with weight 0 (high-recall-only pairs) are dropped and counted. Autapses kept "
                    "and flagged. Edge roiInfo exploded to primary ROIs with an '<unassigned>' remainder."},
    {"step": "count_rule_inference", "code_ref": "brainir.ingest.manc.infer_count_rule",
     "description": "The confidence rule behind neuPrint weight/weightHP/weightHR is inferred from the raw minconf-0.0 "
                    "partner table on a seeded neuron sample (weight: conf_post >= 0.4; weightHP: conf_post >= 0.7; "
                    "weightHR: every pair) and compared with the rule the v1.2.x builds apply."},
    {"step": "neurotransmitters", "code_ref": "brainir.ingest.manc.assemble_neurons_v10",
     "description": "Body-level predictedNt/predictedNtProb copied verbatim (ML prediction; 'unknown' is the classifier's own "
                    "class). MANC v1.0 publishes no cell-type-level or consensus NT: nt_type_* and nt_consensus are null. "
                    "Signs are computed on demand under brainir.sign.conventional-v1."},
    VALIDATE_STEP, WRITE_STEP,
]

TRANSFORMATIONS_MANC_V1_2 = [
    ACQUIRE_STEP,
    {"step": "neuropils", "code_ref": "brainir.ingest.common.build_neuropils",
     "description": "ROI catalogue taken from the manc:v1.0 neuPrint Meta (same ROI volumes); every roi_post value of the "
                    "v1.2 partner table is checked to be a v1.0 primary ROI. n_post_total recomputed under the count rule; "
                    "n_pre_total null (T-bar ROIs are not published for v1.2)."},
    {"step": "annotations", "code_ref": "brainir.ingest.manc.load_snapshot",
     "description": "neuroglancer segment_properties snapshot of the requested annotation version parsed into one row per "
                    "body (label/string/number properties + one column per tag prefix, camelCase prefixes normalised to "
                    "snake_case); '~'/'None'/'TBD' placeholders -> null."},
    {"step": "neuron_definition", "code_ref": "brainir.ingest.manc.build_v12",
     "description": "neurons = bodies listed in the annotation snapshot. No proofreading status exists for v1.2.x: status, "
                    "is_traced and neuprint_neuron_label are null."},
    {"step": "connections", "code_ref": "brainir.ingest.manc.scan_partners_v12",
     "description": "Connections recounted from the raw v1.2 T-bar->PSD partner table under the explicit count rule "
                    "(build_info.count_rule, inferred on v1.0): synapse_count = pairs passing the rule, synapse_count_hp = "
                    "pairs passing the high-precision rule; per-edge neuropil = roi_post (exact); per-neuron n_pre "
                    "approximated by the ROI of a T-bar's PSDs (no T-bar ROI is published). Autapses kept and flagged."},
    {"step": "neurotransmitters", "code_ref": "brainir.ingest.manc.assemble_neurons_v12",
     "description": "Body-level NT predictions carried over from the manc:v1.0 property export by body ID (same segmentation "
                    "lineage; neurons absent from v1.0 get null). Cell-type-level NT from the snapshot's celltypePredictedNt "
                    "tag (v1.2.3 only). No consensus NT exists."},
    VALIDATE_STEP, WRITE_STEP,
]


def transformations_for(pipeline: str, version: str) -> list[dict]:
    if pipeline == "brainir.ingest.malecns":
        return TRANSFORMATIONS_MALECNS
    if pipeline == "brainir.ingest.manc":
        return TRANSFORMATIONS_MANC_V1_0 if version == "v1.0" else TRANSFORMATIONS_MANC_V1_2
    return [ACQUIRE_STEP, VALIDATE_STEP, WRITE_STEP]


def raw_file_profile(path: Path) -> dict:
    """Schema + row count of a raw file (Arrow IPC or JSON/CSV)."""
    if path.suffix in (".feather", ".ftr"):
        try:
            ds = pads.dataset(str(path), format="ipc")
            return {"format": "arrow-ipc (feather v2)", "rows": int(ds.count_rows()), "schema": schema_record(ds.schema)}
        except Exception as exc:  # noqa: BLE001 - profile is informational
            return {"format": "arrow-ipc (feather v2)", "profile_error": str(exc)[:200]}
    if path.suffix == ".json" or path.name == "info":
        return {"format": "json"}
    if path.suffix == ".csv":
        return {"format": "csv"}
    if path.name.endswith(".feather.bz2"):
        return {"format": "arrow-ipc (feather v2), bzip2-compressed"}
    return {"format": path.suffix.lstrip(".") or "text"}


def _acquisition_files(source: DatasetSource, raw: Path, used_keys: set[str]) -> tuple[list[dict], list[dict]]:
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
            "used_by_pipeline": rec["key"] in used_keys,
            **prof,
        })
    return files, acq.get("doc_snapshots", [])


def build_manifest(source: DatasetSource, build_info: dict, report_dict: dict, out_dir: Path) -> dict:
    version = build_info.get("version", source.version)
    facts = source.facts or {}
    raw = paths.raw_dir(source.dataset, source.version)
    files, docs = _acquisition_files(source, raw, set(build_info.get("inputs", {})))
    secondary = []
    for key, sec_inputs in ((k, v) for k, v in build_info.items() if k.startswith("inputs_") and isinstance(v, dict)):
        sec_version = key[len("inputs_"):].replace("_", ".")
        sec_src = SOURCES.get((source.dataset, sec_version))
        if sec_src is not None:
            sec_files, _ = _acquisition_files(sec_src, paths.raw_dir(sec_src.dataset, sec_src.version), set(sec_inputs))
            secondary.append({"dataset": sec_src.dataset, "version": sec_src.version,
                              "bucket": f"gs://{sec_src.bucket}/{sec_src.version_prefix}",
                              "files": [f for f in sec_files if f["used_by_pipeline"]]})
    warn_fail = [{"check_id": c["check_id"], "status": c["status"], "observed": c["observed"], "expected": c["expected"],
                  "description": c["description"]}
                 for c in report_dict["checks"] if c["status"] in ("fail", "warn")]
    acquired = sorted(f["acquired_at_utc"] for f in files) if files else []
    animal = facts.get("animal", {"species": "Drosophila melanogaster", "sex": "male", "n_animals": 1})
    neuprint_snapshot = build_info.get("neuprint_meta") or build_info.get("neuprint_meta_v1_0")
    release = {"date": facts.get("release_date"), "notes": facts.get("release_notes", []), "neuprint_snapshot": neuprint_snapshot}
    if build_info.get("annotation_snapshot"):
        release["annotation_snapshot"] = build_info["annotation_snapshot"]
    definitions = dict(build_info.get("definitions") or {})
    if build_info.get("count_rule"):
        definitions["count_rule"] = build_info["count_rule"]
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset": source.dataset,
        "version": version,
        "source_version": source.version,
        "neuprint_dataset": (build_info.get("annotation_snapshot") or {}).get("neuprint_dataset", source.neuprint_dataset),
        "neuprint_server": source.neuprint_server,
        "animal": {**animal, "cns_coverage": facts.get("cns_coverage")},
        "coordinates": {"space": facts.get("coordinate_space"), "voxel_size_nm": facts.get("voxel_size_nm")},
        "release": release,
        "official_source": {"bucket": f"gs://{source.bucket}/{source.version_prefix}", "landing_page": source.doc_pages.get("home"),
                            "download_page": source.doc_pages.get("download_page"),
                            "release_notes": source.doc_pages.get("release_notes")},
        "documentation_urls": sorted(set(source.doc_pages.values()) | set(facts.get("documentation_urls", []))),
        "documentation_snapshots": docs,
        "citation": source.citation,
        "license": source.license,
        "acquisition": {"method": ACQUIRE_STEP["description"],
                        "first_acquired_utc": acquired[0] if acquired else None,
                        "last_acquired_utc": acquired[-1] if acquired else None,
                        "files": files, "secondary_sources": secondary},
        "definitions": definitions,
        "transformations": transformations_for(build_info.get("pipeline", ""), version),
        "processed_outputs": build_info.get("outputs", {}),
        "graph_statistics": build_info.get("graph_statistics"),
        "annotation_coverage": build_info.get("coverage"),
        "validation": {"summary": report_dict["summary"], "report_json": f"data/manifests/{source.dataset}_{version}.validation.json",
                       "report_markdown": f"data/manifests/{source.dataset}_{version}.validation.md",
                       "fail_and_warn_checks": warn_fail},
        "build": {k: build_info.get(k) for k in ("pipeline", "pipeline_version", "brainir_version", "schema_version",
                                                  "config", "git", "environment", "timings_s", "total_s", "inferred_count_rule")
                  if k in build_info},
    }


def write_manifest(source: DatasetSource, build_info: dict, report_dict: dict, out_dir: Path) -> Path:
    mdir = paths.manifests_dir()
    mdir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(source, build_info, report_dict, out_dir)
    stem = f"{manifest['dataset']}_{manifest['version']}"
    path = mdir / f"{stem}.manifest.json"
    path.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    for ext in ("json", "md"):
        src = out_dir / f"validation_report.{ext}"
        if src.exists():
            shutil.copyfile(src, mdir / f"{stem}.validation.{ext}")
    return path


def dataset_version_record(manifest: dict):
    """Typed :class:`~brainir.schema.models.DatasetVersion` built from a manifest dict."""
    from .schema.models import DatasetVersion, FileChecksum, Transformation

    snap = (manifest.get("release") or {}).get("neuprint_snapshot") or {}
    rule = (manifest.get("definitions") or {}).get("count_rule") or {}
    files = manifest.get("acquisition", {}).get("files", [])
    for sec in manifest.get("acquisition", {}).get("secondary_sources", []):
        files = files + sec.get("files", [])
    coords = manifest.get("coordinates") or {}
    vox = coords.get("voxel_size_nm")
    thr = rule.get("conf_post_min", snap.get("postHighAccuracyThreshold"))
    thr_hp = rule.get("hp_conf_post_min", snap.get("postHPThreshold"))
    return DatasetVersion(
        dataset=manifest["dataset"], version=manifest["version"],
        release_date=(manifest.get("release") or {}).get("date"),
        animal_sex=manifest["animal"]["sex"], n_animals=manifest["animal"]["n_animals"],
        cns_coverage=manifest["animal"].get("cns_coverage") or "unknown",
        acquisition_source=manifest["official_source"]["bucket"],
        acquisition_method=manifest["acquisition"]["method"],
        acquired_at_utc=manifest["acquisition"].get("first_acquired_utc"),
        access_urls={k: v for k, v in {"landing_page": manifest["official_source"].get("landing_page"),
                                       "download_page": manifest["official_source"].get("download_page"),
                                       "neuprint": manifest.get("neuprint_server")}.items() if v},
        checksums=[FileChecksum(path=f["local_path"], size_bytes=f["size_bytes"], sha256=f["sha256"],
                                crc32c_b64=f.get("crc32c_b64"), md5_b64=f.get("md5_b64")) for f in files],
        transformations=[Transformation(step=t["step"], description=t["description"], code_ref=t["code_ref"])
                         for t in manifest.get("transformations", [])],
        synapse_confidence_threshold=thr,
        synapse_confidence_threshold_hp=thr_hp,
        coordinate_space=coords.get("space") or f"{manifest['dataset']} {manifest['version']} EM space",
        voxel_size_nm=tuple(float(v) for v in vox) if vox else None,
        citation=manifest.get("citation", {}), license=manifest.get("license", {}),
        documentation_urls=manifest.get("documentation_urls", []),
        notes=[f"{k}: {v}" for k, v in (manifest.get("definitions") or {}).items()],
    )
