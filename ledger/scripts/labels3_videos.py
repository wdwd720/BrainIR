"""Supplementary-video frame montages for exam 2 label rooms (LABEL SIDE; RUN3_PROMPT section 7 "Sources into rooms"; PREREG v3
T1). No language model in the loop, and the orchestrator does not look at the output.

For each source folder made by the mechanical downloader (`labels2_download.py`, which never downloads videos but lists them in
`meta.json` `skipped`), this script downloads each distinct supplementary video once (preferring .mp4; only from the PMC open-access
bucket or the eLife CDN), samples 24 frames evenly over its duration, and writes `videos/<stem>_montage_<k>.png` (2 images of 12
frames, 4 x 3 tiles, frame time stamped on each tile) plus `videos/<stem>_legend.txt` (the video's label and caption from the
article XML, verbatim) into the source folder. The video file itself is deleted after the montage is made.

    uv run --project ledger --no-sync python ledger/scripts/labels3_videos.py data/ledger/sources_h1/<slug> [...]
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_HOSTS = {"pmc-oa-opendata.s3.amazonaws.com", "cdn.elifesciences.org"}
N_FRAMES, PER_IMAGE, COLS = 24, 12, 4
FFMPEG, FFPROBE = "/opt/homebrew/bin/ffmpeg", "/opt/homebrew/bin/ffprobe"
UA = "ledger-labels3-videos/1.0 (research; montage of open-access supplementary videos)"
XLINK = "{http://www.w3.org/1999/xlink}href"


def stem_of(name: str) -> str:
    """The video's own name: PMC's web transcode `<stem>-pmcvs_normal.mp4` and the original `<stem>.<ext>` share it."""
    s = re.sub(r"^[0-9a-f]{10}_", "", Path(name).stem)  # a content-hash prefix, if any
    return re.sub(r"-pmcvs_normal$", "", s)


MAX_ORIGINAL_BYTES = 40_000_000  # larger originals are replaced by PMC's web transcode of the same video


def legends(xml_path: Path) -> dict[str, str]:
    """media/supplementary-material href stem -> 'label. caption' (verbatim text), from the JATS XML."""
    out: dict[str, str] = {}
    if not xml_path.exists():
        return out
    root = ET.parse(xml_path).getroot()
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ("media", "supplementary-material"):
            continue
        href = el.get(XLINK) or ""
        if not href:
            for m in el.iter():
                if m.tag.split("}")[-1] == "media" and m.get(XLINK):
                    href = m.get(XLINK)
                    break
        if not href:
            continue
        parts = []
        for child in el:
            ct = child.tag.split("}")[-1]
            if ct in ("label", "caption"):
                parts.append(" ".join("".join(child.itertext()).split()))
        out[Path(href).stem.lower()] = " ".join(p for p in parts if p)
    return out


def fetch(url: str, dest: Path) -> None:
    if urlparse(url).netloc not in ALLOWED_HOSTS:
        raise ValueError(f"host not allowed: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as fh:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            fh.write(b)


def duration(path: Path) -> float:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], capture_output=True,
                         text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def montage(video: Path, outdir: Path, stem: str) -> list[str]:
    dur = duration(video)
    times = [dur * (i + 0.5) / N_FRAMES for i in range(N_FRAMES)]
    made = []
    with tempfile.TemporaryDirectory() as td:
        frames = []
        for i, t in enumerate(times):
            f = Path(td) / f"f{i:02d}.png"
            subprocess.run([FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-vf",
                            f"scale=480:-2,drawtext=text='t={t:.1f}s':x=8:y=8:fontsize=22:fontcolor=yellow:box=1:boxcolor=black@0.6",
                            "-y", str(f)], check=True, capture_output=True)
            frames.append(f)
        for k in range(0, N_FRAMES, PER_IMAGE):
            out = outdir / f"{stem}_montage_{k // PER_IMAGE + 1}.png"
            lst = Path(td) / f"list{k}.txt"
            lst.write_text("".join(f"file '{p}'\n" for p in frames[k:k + PER_IMAGE]))
            rows = PER_IMAGE // COLS
            subprocess.run([FFMPEG, "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", f"tile={COLS}x{rows}:padding=4",
                            "-frames:v", "1", "-y", str(out)], check=True, capture_output=True)
            made.append(out.name)
    return made


def process(src: Path) -> dict:
    meta = json.loads((src / "meta.json").read_text())
    vids = [s for s in meta.get("skipped", []) if s.get("reason") == "video or audio"]
    by_stem: dict[str, list[dict]] = {}
    for s in vids:
        by_stem.setdefault(stem_of(s["name"]).lower(), []).append(s)
    for k, opts in by_stem.items():  # the original if small enough, else the web transcode, else the smallest
        orig = [s for s in opts if "-pmcvs_normal" not in s["name"] and int(s.get("bytes") or 0) <= MAX_ORIGINAL_BYTES]
        web = [s for s in opts if "-pmcvs_normal" in s["name"]]
        by_stem[k] = (orig or web or sorted(opts, key=lambda s: int(s.get("bytes") or 0)))[0]
    leg = legends(src / "fulltext.xml")
    outdir = src / "videos"
    outdir.mkdir(exist_ok=True)
    report = {"source": src.name, "n_listed": len(vids), "n_distinct": len(by_stem), "made": [], "failed": []}
    for stem, s in sorted(by_stem.items()):
        if (outdir / f"{stem}_montage_1.png").exists():
            report["made"].append(stem)
            continue
        try:
            with tempfile.TemporaryDirectory() as td:
                v = Path(td) / ("v" + Path(s["name"]).suffix.lower())
                fetch(s["url"], v)
                montage(v, outdir, stem)
            (outdir / f"{stem}_legend.txt").write_text((leg.get(stem) or "(no legend found in the article XML)") + "\n", encoding="utf-8")
            report["made"].append(stem)
        except Exception as e:  # noqa: BLE001
            report["failed"].append({"stem": stem, "error": f"{type(e).__name__}: {e}"[:300]})
        time.sleep(1.0)
    (outdir / "MONTAGES.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return {k: (len(v) if isinstance(v, list) else v) for k, v in report.items()}


if __name__ == "__main__":
    for a in sys.argv[1:]:
        print(json.dumps(process(Path(a))), flush=True)
