"""Provenance: registry pins, integrity verification (offline), manifests."""

from __future__ import annotations

import base64
import hashlib
import json
import re

import google_crc32c
import pytest

from brainir import paths
from brainir.acquire import IntegrityError, _verify, check_pins, file_digests
from brainir.manifest import build_manifest, dataset_version_record
from brainir.sources.registry import BUILD_VERSIONS, MALECNS_V1_0, SOURCES, RemoteFile, get_source, resolve_build

TIERS = {"metadata", "core", "synapses", "optional"}


@pytest.mark.parametrize("source", sorted(SOURCES.values(), key=lambda s: (s.dataset, s.version)), ids=lambda s: f"{s.dataset}:{s.version}")
def test_registry_entries_are_fully_pinned(source):
    keys = [f.key for f in source.files]
    assert len(keys) == len(set(keys))
    rels = set()
    for f in source.files:
        assert f.tier in TIERS
        assert f.size > 0 and f.generation > 0
        assert len(base64.b64decode(f.crc32c_b64)) == 4
        if f.md5_b64:
            assert len(base64.b64decode(f.md5_b64)) == 16
        assert f.remote_path.startswith(source.version_prefix)  # no cross-version mixing inside one registry entry
        rel = source.local_relpath(f)
        assert not re.search(r'[<>:"|?*]', rel), rel  # Windows-safe local names
        assert rel not in rels, rel  # distinct local paths
        rels.add(rel)
        assert source.url(f).startswith(f"https://storage.googleapis.com/{source.bucket_of(f)}/")
    assert source.citation and source.license.get("name") and source.facts.get("animal")


def test_build_versions_resolve_to_registered_sources():
    for (ds, ver), (src, build_ver) in BUILD_VERSIONS.items():
        assert src is SOURCES[(src.dataset, src.version)] and ds == src.dataset and build_ver == ver
        assert get_source(ds, ver) is src and resolve_build(ds, ver) == (src, ver)
    with pytest.raises(KeyError):
        resolve_build("manc", "v9.9")


def test_colon_in_remote_name_is_sanitised():
    f = RemoteFile(key="x", remote_path="v1.0/database/neuprint-inputs/male-cns:v1.0.json", tier="optional",
                   description="", size=1, crc32c_b64="AAAAAA==", generation=1)
    assert MALECNS_V1_0.local_relpath(f) == "database/neuprint-inputs/male-cns_v1.0.json"


def test_file_digests_match_reference_implementations(tmp_path):
    data = b"BrainIR provenance test\n" * 1000
    p = tmp_path / "f.bin"
    p.write_bytes(data)
    d = file_digests(p)
    assert d["sha256"] == hashlib.sha256(data).hexdigest()
    assert d["md5_b64"] == base64.b64encode(hashlib.md5(data).digest()).decode()
    assert d["crc32c_b64"] == base64.b64encode(google_crc32c.Checksum(data).digest()).decode()


def test_verify_rejects_corrupted_bytes(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"abc")
    good = file_digests(p)
    f = RemoteFile(key="k", remote_path="v1.0/k", tier="core", description="", size=3,
                   crc32c_b64=good["crc32c_b64"], generation=1, md5_b64=good["md5_b64"])
    _verify(good, {"crc32c_b64": good["crc32c_b64"], "md5_b64": good["md5_b64"]}, f)  # passes
    part = tmp_path / "f.bin.partial"
    part.write_bytes(b"abd")
    with pytest.raises(IntegrityError):
        _verify(file_digests(part), {"crc32c_b64": good["crc32c_b64"], "md5_b64": good["md5_b64"]}, f, part_path=part)
    assert not part.exists()  # corrupted partial download is discarded


def test_check_pins_detects_upstream_changes():
    f = MALECNS_V1_0.file("body_annotations")
    same = {"size": f.size, "crc32c_b64": f.crc32c_b64, "md5_b64": f.md5_b64, "generation": f.generation}
    assert check_pins(f, same) == []
    changed = dict(same, generation=f.generation + 1, crc32c_b64="AAAAAA==")
    probs = check_pins(f, changed)
    assert any("generation" in p for p in probs) and any("crc32c" in p for p in probs)


def test_relpath_for_record_never_leaks_absolute_paths(tmp_path):
    rec = paths.relpath_for_record(tmp_path / "x.parquet")
    assert rec == "$EXTERNAL/x.parquet"
    rec2 = paths.relpath_for_record(paths.repo_root() / "pyproject.toml")
    assert rec2 == "$REPO/pyproject.toml"


def test_manifest_structure_from_synthetic_build(synthetic_build):
    m = build_manifest(MALECNS_V1_0, synthetic_build["build_info"], synthetic_build["report"].to_dict(),
                       synthetic_build["out_dir"])
    for key in ("dataset", "version", "official_source", "citation", "license", "acquisition", "definitions",
                "transformations", "processed_outputs", "validation", "build", "annotation_coverage"):
        assert key in m, key
    assert m["license"]["name"] == "CC-BY-4.0"
    assert m["validation"]["summary"]["fail"] == 0
    for rec in m["processed_outputs"].values():
        assert {"path", "sha256", "size_bytes", "rows", "schema"} <= set(rec)
    json.dumps(m)  # serialisable
    dv = dataset_version_record(m)  # the typed DatasetVersion model validates from a manifest
    assert dv.key == "male-cns:v1.0" and dv.animal_sex == "male" and dv.voxel_size_nm == (8.0, 8.0, 8.0)


MANIFESTS = {  # committed manifest -> (raw source key, expected weight threshold, expected HP threshold)
    ("male-cns", "v1.0"): (("male-cns", "v1.0"), 0.5, 0.7),
    ("manc", "v1.0"): (("manc", "v1.0"), 0.4, 0.7),
    ("manc", "v1.2.1"): (("manc", "v1.2"), 0.4, 0.7),
    ("manc", "v1.2.3"): (("manc", "v1.2"), 0.4, 0.7),
}


@pytest.mark.parametrize("ds,ver", sorted(MANIFESTS), ids=lambda x: str(x))
def test_committed_manifest_is_consistent_with_registry(ds, ver):
    path = paths.manifests_dir() / f"{ds}_{ver}.manifest.json"
    if not path.exists():
        pytest.skip("manifest not built yet")
    (src_key, thr, thr_hp) = MANIFESTS[(ds, ver)]
    source = SOURCES[src_key]
    m = json.loads(path.read_text())
    assert (m["dataset"], m["version"]) == (ds, ver) and m["source_version"] == source.version
    pins = {f.key: f for f in source.files}
    assert m["acquisition"]["files"], "no acquired files recorded"
    for rec in m["acquisition"]["files"]:
        f = pins[rec["key"]]
        assert rec["gcs_generation"] == f.generation and rec["crc32c_b64"] == f.crc32c_b64
        assert rec["size_bytes"] == f.size and len(rec["sha256"]) == 64
        assert not rec["local_path"].startswith(("C:", "/"))
    for sec in m["acquisition"].get("secondary_sources", []):
        sec_src = SOURCES[(sec["dataset"], sec["version"])]
        sec_pins = {f.key: f for f in sec_src.files}
        for rec in sec["files"]:
            assert rec["gcs_generation"] == sec_pins[rec["key"]].generation
    assert m["validation"]["summary"]["fail"] == 0
    assert m["build"]["git"]["commit"], "manifest must record the code commit that produced it"
    assert m["build"]["schema_version"] == "0.2.0"
    txt = json.dumps(m)
    assert "C:\\" not in txt and "Users/" not in txt, "manifest must not contain machine-specific paths"
    dv = dataset_version_record(m)
    assert dv.key == f"{ds}:{ver}" and all(len(c.sha256) == 64 for c in dv.checksums)
    assert dv.synapse_confidence_threshold == thr and dv.synapse_confidence_threshold_hp == thr_hp
    assert dv.voxel_size_nm == (8.0, 8.0, 8.0)
