"""Download ONE pinned MaleCNS v1.0 file, the curated body annotations (14.5 MB), verified against the BrainIR registry pins
(size, CRC32C, MD5, GCS generation), into <data>/raw/external/malecns_v1.0_body_annotations/ (read-only).

    uv run --project ledger --no-sync python ledger/scripts/fetch_malecns_annotations.py

Why not `brainir acquire`: the full MaleCNS acquisition is 18.7 GB and the ingest needs ~16 GB of free RAM; this machine has
neither to spare (ledger LOG L9). The annotations carry the curated cross-dataset names (MANC type, FlyWire type, hemibrain
type, synonyms) that the synonym map and arm B2 need.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import time
from pathlib import Path

import google_crc32c
import requests
from brainir import paths
from brainir.sources.registry import MALECNS_V1_0

BUCKET = "flyem-male-cns"


def main() -> None:
    f = next(x for x in MALECNS_V1_0.files if x.key == "body_annotations")
    dest_dir = paths.data_root() / "raw" / "external" / "malecns_v1.0_body_annotations"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / Path(f.remote_path).name
    if not dest.exists():
        url = f"https://storage.googleapis.com/{BUCKET}/{f.remote_path}"
        r = requests.get(url, params={"generation": f.generation} if f.generation else None, timeout=600)
        r.raise_for_status()
        data = r.content
        if len(data) != f.size:
            raise RuntimeError(f"size {len(data)} != pinned {f.size}")
        crc = base64.b64encode(google_crc32c.Checksum(data).digest()).decode()
        md5 = base64.b64encode(hashlib.md5(data).digest()).decode()
        if crc != f.crc32c_b64 or (f.md5_b64 and md5 != f.md5_b64):
            raise RuntimeError(f"checksum mismatch: crc {crc} vs {f.crc32c_b64}, md5 {md5} vs {f.md5_b64}")
        tmp = dest.with_suffix(".partial")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
        os.chmod(dest, stat.S_IREAD)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    prov = {"remote": f"gs://{BUCKET}/{f.remote_path}", "generation": f.generation, "size": f.size, "crc32c_b64": f.crc32c_b64,
            "md5_b64": f.md5_b64, "sha256": sha, "local_path": "$DATA/raw/external/malecns_v1.0_body_annotations/" + dest.name,
            "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (dest_dir / "_provenance.json").write_text(json.dumps(prov, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(prov, indent=1))


if __name__ == "__main__":
    main()
