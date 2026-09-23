"""Acquisition of official raw data with integrity verification and provenance.

Guarantees for every acquired file:

* the server-side object metadata (size, CRC32C, MD5 if present, generation)
  is fetched and compared against the pins in :mod:`brainir.sources.registry`;
* the downloaded bytes are verified against the server CRC32C (and MD5 when
  the object has one) *before* the file is moved into ``raw/``;
* a local SHA-256 is computed for long-term provenance;
* the final file is marked read-only (raw data is immutable);
* an acquisition record (JSON, no absolute paths, no secrets) is written.

Downloads are resumable: completed byte ranges are tracked in a sidecar
``.parts.json`` next to the ``.partial`` file.
"""

from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import json
import logging
import os
import stat
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

import google_crc32c
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import paths
from .sources.registry import DatasetSource, RemoteFile

log = logging.getLogger(__name__)

CHUNK_BYTES = 32 * 1024 * 1024
HASH_BLOCK = 8 * 1024 * 1024
ACQUISITION_LOG = "_acquisition.json"


class IntegrityError(RuntimeError):
    """Raised when remote metadata or downloaded bytes fail verification."""


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=8, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset({"GET", "HEAD"}))
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    s.headers["User-Agent"] = "brainir-acquire/0.0.1 (+research data ingestion)"
    return s


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_remote_metadata(source: DatasetSource, f: RemoteFile, session: requests.Session | None = None) -> dict:
    s = session or _session()
    r = s.get(source.metadata_url(f), timeout=60)
    r.raise_for_status()
    m = r.json()
    return {
        "name": m.get("name"),
        "size": int(m["size"]),
        "md5_b64": m.get("md5Hash"),
        "crc32c_b64": m.get("crc32c"),
        "generation": int(m["generation"]),
        "updated": m.get("updated"),
        "etag": m.get("etag"),
        "content_type": m.get("contentType"),
    }


def check_pins(f: RemoteFile, remote: dict) -> list[str]:
    """Compare live remote metadata to registry pins. Returns a list of problems."""
    problems = []
    if remote["size"] != f.size:
        problems.append(f"size {remote['size']} != pinned {f.size}")
    if remote["crc32c_b64"] != f.crc32c_b64:
        problems.append(f"crc32c {remote['crc32c_b64']} != pinned {f.crc32c_b64}")
    if f.md5_b64 is not None and remote["md5_b64"] != f.md5_b64:
        problems.append(f"md5 {remote['md5_b64']} != pinned {f.md5_b64}")
    if remote["generation"] != f.generation:
        problems.append(f"generation {remote['generation']} != pinned {f.generation}")
    return problems


def file_digests(path: Path) -> dict:
    """Compute CRC32C (GCS convention), MD5 and SHA-256 of a local file in one pass."""
    crc = google_crc32c.Checksum()
    md5 = hashlib.md5()
    sha = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(HASH_BLOCK)
            if not block:
                break
            crc.update(block)
            md5.update(block)
            sha.update(block)
    return {
        "crc32c_b64": base64.b64encode(crc.digest()).decode(),
        "md5_b64": base64.b64encode(md5.digest()).decode(),
        "sha256": sha.hexdigest(),
    }


def _download_ranges(url: str, part_path: Path, size: int, n_threads: int, progress_every_s: float = 30.0) -> None:
    """Parallel ranged download into a preallocated file, resumable via a sidecar."""
    sidecar = part_path.with_name(part_path.name + ".parts.json")
    n_chunks = (size + CHUNK_BYTES - 1) // CHUNK_BYTES
    done: set[int] = set()
    if part_path.exists() and sidecar.exists() and part_path.stat().st_size == size:
        try:
            done = set(json.loads(sidecar.read_text())["done"])
        except (ValueError, KeyError):
            done = set()
    else:
        with open(part_path, "wb") as fh:
            fh.truncate(size)
    lock = threading.Lock()
    session = _session()
    bytes_done = [sum(min(CHUNK_BYTES, size - i * CHUNK_BYTES) for i in done)]
    t0 = time.time()
    last_report = [t0]

    def fetch(i: int) -> int:
        start = i * CHUNK_BYTES
        end = min(size, start + CHUNK_BYTES) - 1
        for attempt in range(6):
            try:
                r = session.get(url, headers={"Range": f"bytes={start}-{end}"}, timeout=300)
                if r.status_code != 206:
                    raise IntegrityError(f"expected HTTP 206 for range request, got {r.status_code}")
                data = r.content
                if len(data) != end - start + 1:
                    raise IntegrityError(f"short range read {len(data)} != {end - start + 1}")
                break
            except (requests.RequestException, IntegrityError) as exc:
                if attempt == 5:
                    raise
                log.warning("chunk %d attempt %d failed: %s", i, attempt + 1, exc)
                time.sleep(2 ** attempt)
        with lock:
            with open(part_path, "r+b") as fh:
                fh.seek(start)
                fh.write(data)
            done.add(i)
            sidecar.write_text(json.dumps({"size": size, "chunk_bytes": CHUNK_BYTES, "done": sorted(done)}))
            bytes_done[0] += len(data)
            now = time.time()
            if now - last_report[0] > progress_every_s:
                last_report[0] = now
                rate = bytes_done[0] / max(1e-9, now - t0)
                log.info("  %s: %.1f%% (%.0f/%.0f MB) %.1f MB/s", part_path.name, 100 * bytes_done[0] / size,
                         bytes_done[0] / 1e6, size / 1e6, rate / 1e6)
        return i

    todo = [i for i in range(n_chunks) if i not in done]
    if todo:
        with ThreadPoolExecutor(max_workers=n_threads) as ex:
            for fut in as_completed([ex.submit(fetch, i) for i in todo]):
                fut.result()
    sidecar.unlink(missing_ok=True)


def acquire_file(source: DatasetSource, f: RemoteFile, *, n_threads: int = 4, allow_pin_mismatch: bool = False) -> dict:
    """Download (or re-verify) one registered file. Returns its acquisition record."""
    raw = paths.raw_dir(source.dataset, source.version)
    dest = raw / source.local_relpath(f)
    dest.parent.mkdir(parents=True, exist_ok=True)
    session = _session()
    remote = fetch_remote_metadata(source, f, session)
    problems = check_pins(f, remote)
    if problems and not allow_pin_mismatch:
        raise IntegrityError(
            f"Remote object {f.remote_path} no longer matches the registry pins: {problems}. "
            "The upstream release may have been modified; review before re-pinning.")

    if dest.exists():
        log.info("verifying existing %s", dest.name)
        digests = file_digests(dest)
        _verify(digests, remote, f)
        status = "verified-existing"
    else:
        part = dest.with_name(dest.name + ".partial")
        log.info("downloading %s (%.1f MB)", f.remote_path, remote["size"] / 1e6)
        t0 = time.time()
        _download_ranges(source.url(f), part, remote["size"], n_threads)
        elapsed = time.time() - t0
        digests = file_digests(part)
        _verify(digests, remote, f, part_path=part)
        os.replace(part, dest)
        log.info("  done in %.0fs (%.1f MB/s)", elapsed, remote["size"] / 1e6 / max(elapsed, 1e-9))
        status = "downloaded"
    os.chmod(dest, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)  # immutable raw data

    return {
        "key": f.key,
        "tier": f.tier,
        "remote_url": source.url(f),
        "remote_path": f.remote_path,
        "local_path": paths.relpath_for_record(dest),
        "status": status,
        "acquired_at_utc": utc_now(),
        "size_bytes": dest.stat().st_size,
        "remote_metadata": remote,
        "pin_problems": problems,
        "local_digests": digests,
        "description": f.description,
    }


def _verify(digests: dict, remote: dict, f: RemoteFile, part_path: Path | None = None) -> None:
    errors = []
    if digests["crc32c_b64"] != remote["crc32c_b64"]:
        errors.append(f"crc32c local {digests['crc32c_b64']} != remote {remote['crc32c_b64']}")
    if remote.get("md5_b64") and digests["md5_b64"] != remote["md5_b64"]:
        errors.append(f"md5 local {digests['md5_b64']} != remote {remote['md5_b64']}")
    if errors:
        if part_path is not None:
            part_path.unlink(missing_ok=True)
        raise IntegrityError(f"{f.remote_path}: " + "; ".join(errors))


def snapshot_doc_pages(source: DatasetSource) -> list[dict]:
    """Save the official documentation pages as they looked at acquisition time."""
    out_dir = paths.raw_dir(source.dataset, source.version) / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    session = _session()
    records = []
    for name, url in source.doc_pages.items():
        r = session.get(url, timeout=60)
        r.raise_for_status()
        stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")
        dest = out_dir / f"{name}_{stamp}.html"
        if dest.exists():
            os.chmod(dest, stat.S_IWRITE | stat.S_IREAD)
        dest.write_bytes(r.content)
        os.chmod(dest, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        records.append({"name": name, "url": url, "local_path": paths.relpath_for_record(dest),
                        "retrieved_at_utc": utc_now(), "sha256": hashlib.sha256(r.content).hexdigest(),
                        "size_bytes": len(r.content)})
    return records


def acquire_dataset(source: DatasetSource, tiers: set[str] | None, *, n_threads: int = 4,
                    allow_pin_mismatch: bool = False, docs: bool = True) -> Path:
    """Acquire all files of the requested tiers and write/update the acquisition log."""
    raw = paths.raw_dir(source.dataset, source.version)
    raw.mkdir(parents=True, exist_ok=True)
    log_path = raw / ACQUISITION_LOG
    existing = json.loads(log_path.read_text()) if log_path.exists() else {}
    records = {r["key"]: r for r in existing.get("files", [])}
    for f in source.files_in_tiers(tiers):
        rec = acquire_file(source, f, n_threads=n_threads, allow_pin_mismatch=allow_pin_mismatch)
        prev = records.get(f.key)
        if prev and prev.get("status") == "downloaded" and rec["status"] == "verified-existing":
            # keep the original download timestamp; note re-verification separately
            rec = {**prev, "last_verified_at_utc": rec["acquired_at_utc"], "local_digests": rec["local_digests"]}
        records[f.key] = rec
        _write_log(log_path, source, records, existing.get("doc_snapshots", []))
    doc_records = existing.get("doc_snapshots", [])
    if docs:
        doc_records = doc_records + snapshot_doc_pages(source)
    _write_log(log_path, source, records, doc_records)
    return log_path


def _write_log(log_path: Path, source: DatasetSource, records: dict, doc_records: list) -> None:
    body = {
        "dataset": source.dataset,
        "version": source.version,
        "neuprint_dataset": source.neuprint_dataset,
        "bucket": source.bucket,
        "registry_registered_on": source.registered_on,
        "files": [records[k] for k in sorted(records)],
        "doc_snapshots": doc_records,
        "citation": source.citation,
        "license": source.license,
    }
    if log_path.exists():
        os.chmod(log_path, stat.S_IWRITE | stat.S_IREAD)
    tmp = log_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, indent=2, sort_keys=False))
    os.replace(tmp, log_path)


def registry_as_dict(source: DatasetSource) -> dict:
    return {**{k: v for k, v in asdict(source).items() if k != "files"},
            "files": [asdict(f) | {"url": source.url(f), "local_relpath": source.local_relpath(f)}
                      for f in source.files]}
