"""Read members of a Zenodo zip archive over HTTP range requests (no full download).

    uv run --project ledger --no-sync python ledger/scripts/zenodo_remote_zip.py list DNg100_Stim_fullManc.zip
    uv run --project ledger --no-sync python ledger/scripts/zenodo_remote_zip.py get DNg100_Stim_fullManc.zip <member> [<member> ...]

Record: Pugliese et al. 2026 data, doi 10.5281/zenodo.22260924. Extracted members are written under
<data>/raw/external/pugliese_2026_zenodo/<archive>/<member> with a provenance JSON (URL, member CRC from the zip directory,
SHA-256 of the extracted bytes).
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import time
import zipfile
from pathlib import Path

import requests
from brainir import paths

RECORD = "22260924"


class HTTPRangeFile(io.RawIOBase):
    def __init__(self, url: str):
        self.url = url
        self.session = requests.Session()
        h = self.session.head(url, allow_redirects=True, timeout=60)
        h.raise_for_status()
        self.url = h.url
        self.size = int(h.headers["Content-Length"])
        self.pos = 0
        self.n_requests = 0
        self.n_bytes = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else (self.pos + offset if whence == 1 else self.size + offset)
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b""
        end = min(self.size, self.pos + n) - 1
        for attempt in range(5):
            try:
                r = self.session.get(self.url, headers={"Range": f"bytes={self.pos}-{end}"}, timeout=300)
                r.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 4:
                    raise
                time.sleep(2 * (attempt + 1))
        data = r.content
        self.n_requests += 1
        self.n_bytes += len(data)
        self.pos += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[: len(data)] = data
        return len(data)


def open_archive(name: str) -> tuple[zipfile.ZipFile, HTTPRangeFile]:
    url = f"https://zenodo.org/records/{RECORD}/files/{name}?download=1"
    f = HTTPRangeFile(url)
    return zipfile.ZipFile(io.BufferedReader(f, buffer_size=1 << 20)), f


def main() -> None:
    cmd, name, *members = sys.argv[1:]
    z, f = open_archive(name)
    if cmd == "list":
        for i in z.infolist():
            print(f"{i.file_size:>14,d}  {i.compress_size:>14,d}  {i.filename}")
        print(f"# {len(z.infolist())} members; archive {f.size:,d} bytes; {f.n_requests} range requests, {f.n_bytes:,d} bytes read")
        return
    out = paths.data_root() / "raw" / "external" / "pugliese_2026_zenodo" / name.removesuffix(".zip")
    for m in members:
        info = z.getinfo(m)
        data = z.read(m)
        dest = out / m
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        prov = {"record": f"10.5281/zenodo.{RECORD}", "archive": name, "member": m, "zip_crc32": f"{info.CRC:08x}",
                "size": info.file_size, "sha256": hashlib.sha256(data).hexdigest(), "url": f.url.split("?")[0],
                "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        dest.with_name(dest.name + ".provenance.json").write_text(json.dumps(prov, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(prov))
    print(f"# {f.n_requests} range requests, {f.n_bytes:,d} bytes read")


if __name__ == "__main__":
    main()
