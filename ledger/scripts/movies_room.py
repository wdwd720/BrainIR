"""Atlas-movie availability check (prompt section 9, "Movies": report whether the Cande et al. 2018 movies are downloadable,
how large they are, and whether pose tracking looks feasible; do NOT analyse them).

The orchestrator has seen the predictions, so it must not read pages that describe per-line behaviour. The check therefore
runs as a separate headless session in its own room OUTSIDE the labeler rooms (`~/ledger_rooms/run1_aux/movies/`), with the
labelers' frozen tool flags (`labels_rooms.FLAGS`: no shell, file tools confined to the room, GitHub/Zenodo fetches denied).
It writes only `out/movies_report.md`, which must contain no behavioural information; the orchestrator reads only that file.

    uv run --project ledger --no-sync python ledger/scripts/movies_room.py launch
    uv run --project ledger --no-sync python ledger/scripts/movies_room.py status
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labels_rooms as LR  # noqa: E402  (frozen label-side module; only its FLAGS constant is read)

BASE = Path.home() / "ledger_rooms" / "run1_aux"
ROOM = BASE / "movies"
PROMPT = """You are helping plan future work on a public video dataset. Your only task is to find out whether the behaviour
movies of Cande et al. 2018 (eLife, "Optogenetic dissection of descending behavioral control in Drosophila") are publicly
downloadable, and what they are like as files.

Report, with the URLs of the hosting pages or archives you used:
- where the movies are hosted, and whether they can be downloaded without an account;
- how many movie files there are, the typical size of one file and the total size (from listings or metadata);
- container/codec, resolution, frame rate, clip duration, number and kind of camera views, lighting;
- the licence;
- whether markerless pose tracking of the legs (e.g. DeepLabCut, SLEAP, Anipose) looks feasible on these files, and why
  (pixels per fly, view angle, occlusion, motion blur, frame rate relative to stepping, number of flies per frame).

Strict rules:
- Do NOT download any movie file. Read only web pages, file listings, sizes and metadata.
- Do NOT describe, summarise or mention the behaviour, phenotype or result shown for any driver line or neuron, and do
  not list driver-line or neuron names. Your report must contain no behavioural information about any line or neuron.
- Do not access github.com, githubusercontent.com or zenodo.org.
- Write your report, at most 400 words, to out/movies_report.md, then stop.
"""


def launch() -> None:
    if ROOM.exists():
        raise SystemExit(f"{ROOM} exists already (single-use room)")
    (ROOM / "out").mkdir(parents=True)
    (ROOM / "PROMPT.md").write_text(PROMPT, encoding="utf-8")
    log = BASE / "movies.stream.jsonl"
    with open(log, "w", encoding="utf-8") as fh:
        p = subprocess.Popen(["claude", "-p", PROMPT, *LR.FLAGS], cwd=ROOM, stdout=fh, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
    man = {"session": "movies", "room": str(ROOM), "pid": p.pid, "flags": LR.FLAGS,
           "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (BASE / "movies.manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    print(json.dumps({"launched": True, "pid": p.pid}))


def status() -> None:
    log = BASE / "movies.stream.jsonl"
    res = []
    if log.exists():
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "result":
                res.append({"subtype": d.get("subtype"), "cost": d.get("total_cost_usd"), "turns": d.get("num_turns")})
    rep = ROOM / "out" / "movies_report.md"
    print(json.dumps({"results": res, "report_exists": rep.exists(), "report_words": len(rep.read_text().split()) if rep.exists() else 0}))


if __name__ == "__main__":
    {"launch": launch, "status": status}[sys.argv[1]]()
