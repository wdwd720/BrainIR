"""Build labeler rooms and launch blind labeler sessions (LABEL SIDE: never reads predictions).

    uv run --project ledger --no-sync python ledger/scripts/labels_rooms.py launch pass1 --family atlas
    uv run --project ledger --no-sync python ledger/scripts/labels_rooms.py launch pass1 --all
    uv run --project ledger --no-sync python ledger/scripts/labels_rooms.py launch pass2 --family atlas      # needs labels_prepare.py pass2
    uv run --project ledger --no-sync python ledger/scripts/labels_rooms.py launch search --name search_names
    uv run --project ledger --no-sync python ledger/scripts/labels_rooms.py launch adjudication --name adj1  # needs labels_prepare.py adjudication
    uv run --project ledger --no-sync python ledger/scripts/labels_rooms.py status

A room is a directory OUTSIDE the repository (~/ledger_rooms/run1/<session>/) holding only the labeler kit files listed in
ROOM_FILES plus the pass-specific inputs; the session runs `claude -p` there with the frozen flags below (no shell, no MCP
servers, file tools confined to the room, web fetches to GitHub / raw GitHub / Zenodo denied at tool level). Each launch writes
a manifest (files + SHA-256, flags, model, prompt hash, PID, start time) under ~/ledger_rooms/run1/_manifests/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
KIT = REPO / "research" / "ledger" / "kit"
ROOMS = Path.home() / "ledger_rooms" / "run1"
MANIFESTS = ROOMS / "_manifests"
ROOM_FILES = ["PROTOCOL.md", "record_schema.json", "type_list.csv", "synonyms.csv", "driver_lines.csv"]
PASS1_EXTRA = ["sources_seed.csv"]
MODEL = "opus"
TOOLS = "Read,Write,Edit,Glob,Grep,WebSearch,WebFetch"
DENY = ["WebFetch(domain:github.com)", "WebFetch(domain:raw.githubusercontent.com)", "WebFetch(domain:githubusercontent.com)",
        "WebFetch(domain:zenodo.org)"]
FLAGS = ["--restricted", "--strict-mcp-config", "--tools", TOOLS, "--allowedTools", TOOLS, "--disallowedTools", *DENY,
         "--permission-mode", "acceptEdits", "--permission-prompts", "none", "--disable-slash-commands", "--no-chrome",
         "--model", MODEL, "--output-format", "stream-json", "--verbose"]
PREFIX = {"pass1": "p1", "pass2": "p2", "search": "s", "adjudication": "adj"}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def prompt_for(pass_id: str, session: str, family: str | None, extra: dict) -> str:
    fam = json.loads((KIT / "families.json").read_text(encoding="utf-8"))
    tmpl = (KIT / {"pass1": "PROMPT_PASS1.md", "pass2": "PROMPT_PASS2.md", "search": "PROMPT_SEARCH.md",
                   "adjudication": "PROMPT_ADJUDICATE.md"}[pass_id]).read_text(encoding="utf-8")
    pre = f"{PREFIX[pass_id]}-{session.split('-', 1)[-1]}"
    rep = {"{SESSION}": session, "{PREFIX}": pre}
    if pass_id == "pass1":
        f = fam["pass1_families"][family]
        rep.update({"{FAMILY_TITLE}": f["title"], "{FAMILY_SCOPE}": f["scope"]})
    if pass_id == "search":
        rep["{SEARCH_SCOPE}"] = fam["search_sessions"][extra["name"]]
    for k, v in rep.items():
        tmpl = tmpl.replace(k, v)
    return tmpl


def build_room(session: str, pass_id: str, inputs: dict[str, Path]) -> Path:
    room = ROOMS / session
    if room.exists():
        raise SystemExit(f"room {room} exists already; refusing to overwrite (rooms are single-use)")
    (room / "out").mkdir(parents=True)
    for name in ROOM_FILES + (PASS1_EXTRA if pass_id == "pass1" else []):
        shutil.copyfile(KIT / name, room / name)
    for name, src in inputs.items():
        shutil.copyfile(src, room / name)
    return room


def launch(pass_id: str, session: str, family: str | None = None, inputs: dict[str, Path] | None = None, extra: dict | None = None) -> dict:
    inputs = inputs or {}
    extra = extra or {}
    room = build_room(session, pass_id, inputs)
    prompt = prompt_for(pass_id, session, family, extra)
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    log = ROOMS / f"{session}.stream.jsonl"
    err = ROOMS / f"{session}.stderr.txt"
    cmd = ["claude", "-p", prompt, *FLAGS]
    with open(log, "w") as out, open(err, "w") as e:
        proc = subprocess.Popen(cmd, cwd=room, stdout=out, stderr=e, stdin=subprocess.DEVNULL, start_new_session=True,
                                env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
    man = {"session": session, "pass": pass_id, "family": family, "room": str(room), "pid": proc.pid,
           "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "model": MODEL, "flags": FLAGS,
           "prompt_sha256": _sha(prompt.encode()), "prompt": prompt,
           "files": {p.name: _sha(p.read_bytes()) for p in sorted(room.iterdir()) if p.is_file()},
           "stream_log": str(log)}
    (MANIFESTS / f"{session}.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    return man


def status() -> list[dict]:
    rows = []
    for m in sorted(MANIFESTS.glob("*.json")):
        man = json.loads(m.read_text(encoding="utf-8"))
        alive = True
        try:
            os.kill(man["pid"], 0)
        except OSError:
            alive = False
        res = None
        log = Path(man["stream_log"])
        if log.exists():
            for line in log.read_text(encoding="utf-8", errors="replace").splitlines()[-5:]:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("type") == "result":
                    res = {"subtype": d.get("subtype"), "cost": d.get("total_cost_usd"), "turns": d.get("num_turns"),
                           "session_id": d.get("session_id")}
        n_rec = 0
        rp = Path(man["room"]) / "out" / "records.jsonl"
        if rp.exists():
            n_rec = sum(1 for ln in rp.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip())
        rows.append({"session": man["session"], "alive": alive, "records": n_rec, "result": res})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    la = sub.add_parser("launch")
    la.add_argument("pass_id", choices=["pass1", "pass2", "search", "adjudication"])
    la.add_argument("--family")
    la.add_argument("--all", action="store_true")
    la.add_argument("--name")
    la.add_argument("--inputs-dir", type=Path, help="directory with the pass-specific input files (pass2/adjudication)")
    sub.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "status":
        for r in status():
            print(json.dumps(r))
        return
    fam = json.loads((KIT / "families.json").read_text(encoding="utf-8"))
    if a.pass_id == "pass1":
        fams = list(fam["pass1_families"]) if a.all else [a.family]
        for f in fams:
            m = launch("pass1", f"pass1-{f}", f)
            print("launched", m["session"], m["pid"])
    elif a.pass_id == "pass2":
        fams = list(fam["pass1_families"]) if a.all else [a.family]
        for f in fams:
            d = a.inputs_dir / f
            if not (d / "experiments_to_label.csv").exists():
                print("skip", f, "(no experiments)")
                continue
            m = launch("pass2", f"pass2-{f}", f, {"experiments_to_label.csv": d / "experiments_to_label.csv",
                                                   "quotes_to_verify.csv": d / "quotes_to_verify.csv"})
            print("launched", m["session"], m["pid"])
    elif a.pass_id == "search":
        names = list(fam["search_sessions"]) if a.all else [a.name]
        for n in names:
            m = launch("search", f"search-{n}", None, extra={"name": n})
            print("launched", m["session"], m["pid"])
    else:
        m = launch("adjudication", f"adjudication-{a.name}", None, {"disagreements.csv": a.inputs_dir / "disagreements.csv"})
        print("launched", m["session"], m["pid"])


if __name__ == "__main__":
    main()
