"""Atlas-movie INVENTORY (RUN2_PROMPT section 7 "Movies"): download the Dryad archive of Cande et al. 2018 (doi:10.5061/dryad.fr89c0c),
list it, and report the number of clips, how file names map to driver lines, and the resolution, frame rate and codec read from
the container headers. No frame is decoded or looked at (no analysis, no viewing).

    uv run --project ledger --no-sync --with av==14.4.0 python ledger/scripts/movies_inventory.py   # -> research/ledger/movies/INVENTORY_v2.json
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "cache" / "atlas_movies"
FILES_API = "https://datadryad.org/api/v2/versions/16720/files"
UA = {"User-Agent": "brainir-ledger-inventory/1.0"}


def get(url: str) -> bytes:
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception:  # noqa: BLE001
            time.sleep(5 * (k + 1))
    raise RuntimeError(url)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    meta = json.loads(get(FILES_API))
    files = meta.get("_embedded", {}).get("stash:files", [])
    f = next(x for x in files if x.get("path", "").endswith(".zip"))
    zpath = OUT / f["path"]
    if not zpath.exists() or zpath.stat().st_size != int(f.get("size", -1)):
        href = f["_links"]["stash:download"]["href"]
        url = href if href.startswith("http") else "https://datadryad.org" + href
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=600) as r, open(zpath, "wb") as fh:
            while True:
                b = r.read(1 << 22)
                if not b:
                    break
                fh.write(b)
    h = hashlib.sha256()
    with open(zpath, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    with zipfile.ZipFile(zpath) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        clips = [n for n in names if n.lower().endswith((".avi", ".mp4", ".mov", ".mkv", ".mpg", ".mpeg", ".wmv"))]
        line_re = re.compile(r"((?:SS|MB|SC)\d{4,5}[A-Z]?|R\d{2}[A-H]\d{2}|VT\d{6})", re.I)
        lines = collections.Counter()
        unmatched = 0
        for n in clips:
            m = line_re.search(n)
            if m:
                lines[m.group(1).upper()] += 1
            else:
                unmatched += 1
        probe = []
        try:
            import av  # container headers only
            for n in clips[:: max(1, len(clips) // 12)][:12]:
                tmp = OUT / "probe_tmp" / Path(n).name
                tmp.parent.mkdir(exist_ok=True)
                tmp.write_bytes(z.read(n))
                with av.open(str(tmp)) as c:
                    s = c.streams.video[0]
                    probe.append({"file": Path(n).name, "codec": s.codec_context.name, "width": s.codec_context.width,
                                  "height": s.codec_context.height, "fps": float(s.average_rate) if s.average_rate else None,
                                  "frames": s.frames, "duration_s": float(c.duration / 1e6) if c.duration else None})
                tmp.unlink()
        except Exception as e:  # noqa: BLE001
            probe.append({"error": f"{type(e).__name__}: {e}"})
    folders = collections.Counter(str(Path(n).parent) for n in clips)
    out = {"archive": f["path"], "bytes": zpath.stat().st_size, "sha256": h.hexdigest(), "n_files": len(names), "n_clips": len(clips),
           "extensions": dict(collections.Counter(Path(n).suffix.lower() for n in names)), "n_folders": len(folders),
           "clips_per_line": {"n_lines_in_names": len(lines), "median_clips_per_line": (sorted(lines.values())[len(lines) // 2] if lines else None),
                              "clips_without_line_id_in_name": unmatched},
           "filename_examples": [Path(n).name for n in clips[:5]], "header_probe": probe,
           "note": "inventory only: names and container headers; no frame decoded or viewed"}
    d = REPO / "research" / "ledger" / "movies"
    d.mkdir(parents=True, exist_ok=True)
    (d / "INVENTORY_v2.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k not in ("header_probe",)}, indent=1)[:2500])


if __name__ == "__main__":
    main()
