"""Labeler rooms and sessions for exam 2 (labels h1; LABEL SIDE, never reads predictions). PREREG v3 Part T; RUN3_PROMPT section 7.

Run 2's machinery as it stands (`labels2_rooms.py`: room builder, `claude -p` launcher with run 1's frozen flags and run 2's deny
rules, single-use rooms, manifests, queue scheduler with the quota rule, transcripts), re-pointed at run 3's rooms, kit and sources
by setting its module attributes in this process (the run 2 file is unchanged). Additions: run 3's kit files and prompts, a scope
placeholder for readers, the run 2 rooms and run 3's canary plant in the deny list, and image conversion (WebP/TIFF -> PNG) when a
room is built, because the reader can only open common image formats.

    labels3_rooms.py launch SPEC.json [--mode tool|sandbox]
    labels3_rooms.py enqueue SPEC.json ...
    labels3_rooms.py schedule [--max 6] [--idle-exit-min 30]
    labels3_rooms.py status
    labels3_rooms.py repair --session S      # the one repair round for schema-invalid records
SPEC: {"kind": "reader"|"adjudication"|"search"|"cheong"|"verify", "session": "...", "sources": [slug, ...], "scope": [names],
       "search_kind": "...", "inputs": {"name in room": "path"}}
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labels2_rooms as R2  # noqa: E402

HOME = Path.home()
REPO = R2.REPO
ROOMS = HOME / "ledger_rooms" / "run3"
KIT = REPO / "research" / "ledger" / "kit_v3"
SOURCES = REPO / "data" / "ledger" / "sources_h1"
LAB_RAW = REPO / "research" / "ledger" / "labels_h1" / "raw"
KIT_FILES = ["PROTOCOL.md", "record_schema.json", "hemilineage_names.csv"]
PROMPTS = {"reader": "PROMPT_READER.md", "adjudication": "PROMPT_ADJUDICATE.md", "search": "PROMPT_SEARCH.md",
           "cheong": "PROMPT_CHEONG.md", "verify": "PROMPT_VERIFY.md"}
PASS_OF = {"reader": "reading", "adjudication": "adjudication", "search": "search", "cheong": "cheong", "verify": "verify"}
SEARCH_KINDS = {
    "by_name": "search by hemilineage name: every name in hemilineage_names.csv and its other spellings, with words such as "
               "activation, CsChrimson, TrpA1, optogenetic, thermogenetic, behavior, ventral nerve cord.",
    "by_driver": "search by driver: hemilineage-specific GAL4 / split-GAL4 / LexA lines and lineage driver libraries of the ventral "
                 "nerve cord, and studies that used such lines for activation in adult flies.",
    "by_citation": "search by citation: papers that cite Harris et al. 2015 (eLife, doi 10.7554/eLife.04493) or Soffers et al. 2025 "
                   "(eLife, doi 10.7554/eLife.106042) and activate hemilineages in adult flies.",
}
CANARY_PLANT = HOME / "ledger_rooms" / "run3_canary" / "planted"


def deny_paths_v3() -> list[Path]:
    extra = [HOME / "ledger_rooms" / "run2", HOME / "ledger_rooms" / "run2_canary", CANARY_PLANT, HOME / "ledger_rooms_hl_search",
             R2.LA.PROJECTS / (R2.LA.encode(str(HOME / "ledger_rooms" / "run2")) + "*")]
    return _DENY2() + extra


def prompt_for_v3(spec: dict) -> str:
    t = (KIT / PROMPTS[spec["kind"]]).read_text(encoding="utf-8")
    rep = {"{SESSION}": spec["session"], "{PREFIX}": spec["session"]}
    if spec["kind"] == "reader":
        rep["{HL_SCOPE}"] = ", ".join(spec["scope"])
    if spec["kind"] == "search":
        rep.update({"{SEARCH_KIND}": spec["search_kind"], "{SEARCH_SCOPE}": SEARCH_KINDS[spec["search_kind"]]})
    for k, v in rep.items():
        t = t.replace(k, v)
    left = [k for k in ("{SESSION}", "{PREFIX}", "{HL_SCOPE}", "{SEARCH_KIND}", "{SEARCH_SCOPE}") if k in t]
    if left:
        raise SystemExit(f"{spec['session']}: unfilled placeholders {left}")
    return t


def convert_images(room: Path) -> int:
    """WebP / TIFF / GIF figure images -> PNG copies next to them (ffmpeg), so every figure can be opened."""
    n = 0
    for p in list(room.rglob("*")):
        if p.suffix.lower() in (".webp", ".tif", ".tiff", ".gif") and p.is_file():
            out = p.with_suffix(".png")
            if not out.exists():
                r = subprocess.run(["/opt/homebrew/bin/ffmpeg", "-v", "error", "-i", str(p), "-frames:v", "1", "-y", str(out)],
                                   capture_output=True)
                n += int(r.returncode == 0)
    return n


def build_room_v3(spec: dict) -> Path:
    room = _BUILD2(spec)
    convert_images(room)
    return room


def repoint() -> None:
    """Point run 2's launcher at run 3's rooms, kit and sources (this process only)."""
    R2.ROOMS, R2.MANIFESTS, R2.QUEUE = ROOMS, ROOMS / "_manifests", ROOMS / "_queue"
    R2.KIT, R2.SOURCES, R2.LAB2_RAW = KIT, SOURCES, LAB_RAW
    R2.KIT_FILES, R2.PROMPTS, R2.PASS_OF = KIT_FILES, PROMPTS, PASS_OF
    R2.WEB_TOOLS = {"search": "Read,Write,Edit,Glob,Grep,WebSearch,WebFetch"}
    R2.WEB_KINDS = tuple(R2.WEB_TOOLS)
    R2.deny_paths = deny_paths_v3
    R2.prompt_for = prompt_for_v3
    R2.build_room = build_room_v3


_DENY2 = R2.deny_paths
_BUILD2 = R2.build_room
repoint()


def repair(session: str) -> None:
    """The one repair round for schema-invalid records (run 2's design): resume the session with the line numbers and problems
    only (never the coded values). Refused if the session already had a repair round."""
    sys.path.insert(0, str(REPO / "ledger" / "src"))
    from brainir_ledger.labels_h1 import core as C  # noqa: PLC0415

    man = json.loads((R2.MANIFESTS / f"{session}.json").read_text())
    if any(r["tag"] == "repair" for r in man["runs"]):
        raise SystemExit(f"{session}: the repair round was used")
    lines = (Path(man["room"]) / "out" / "records.jsonl").read_text(encoding="utf-8").splitlines()
    errs = []
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            probs = C.validate(json.loads(line))
        except ValueError:
            probs = ["not valid JSON"]
        if probs:
            errs.append(f"line {i}: " + "; ".join(probs))
    if not errs:
        print(f"{session}: every record is valid; no repair")
        return
    prompt = (KIT / "PROMPT_REPAIR.md").read_text(encoding="utf-8").replace("{ERRORS}", "\n".join(errs))
    m = R2.resume(session, "repair", prompt)
    print("repair launched", session, len(errs), "lines", m["runs"][-1]["pid"])


def enqueue(paths: list[str]) -> None:
    R2.QUEUE.mkdir(parents=True, exist_ok=True)
    for p in paths:
        spec = json.loads(Path(p).read_text())
        prompt_for_v3(spec)  # fail early on a bad spec
        shutil.copyfile(p, R2.QUEUE / f"{int(time.time() * 1000)}_{spec['session']}.json")
        time.sleep(0.01)
    print("queued", len(paths))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("launch")
    a.add_argument("spec")
    a.add_argument("--mode", default="tool", choices=["tool", "sandbox"])
    e = sub.add_parser("enqueue")
    e.add_argument("specs", nargs="+")
    s = sub.add_parser("schedule")
    s.add_argument("--max", type=int, default=6)
    s.add_argument("--idle-exit-min", type=float, default=30.0)
    s.add_argument("--mode", default="tool", choices=["tool", "sandbox"])
    sub.add_parser("status")
    r = sub.add_parser("repair")
    r.add_argument("--session", required=True)
    args = ap.parse_args()
    if args.cmd == "launch":
        m = R2.launch(json.loads(Path(args.spec).read_text()), args.mode)
        print("launched", m["session"], m["runs"][0]["pid"])
    elif args.cmd == "enqueue":
        enqueue(args.specs)
    elif args.cmd == "schedule":
        R2.schedule(args.max, args.idle_exit_min, args.mode)
    elif args.cmd == "repair":
        repair(args.session)
    else:
        print(json.dumps(R2.status(), indent=1, default=str))


if __name__ == "__main__":
    main()
