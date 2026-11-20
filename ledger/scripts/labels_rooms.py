"""Build labeler rooms and launch blind labeler sessions (LABEL SIDE: never reads predictions).

    uv run --project ledger --no-sync python ledger/scripts/labels_rooms.py launch pass1 --family atlas | --all
    uv run --project ledger --no-sync python ledger/scripts/labels_rooms.py launch pass2 --family atlas | --all   # Phase A
    uv run --project ledger --no-sync python ledger/scripts/labels_rooms.py phaseb --session pass2-atlas           # Phase B
    uv run --project ledger --no-sync python ledger/scripts/labels_rooms.py launch search --name search_names | --all
    uv run --project ledger --no-sync python ledger/scripts/labels_rooms.py launch adjudication --name general | dedicated
    uv run --project ledger --no-sync python ledger/scripts/labels_rooms.py repair --session pass1-atlas           # one round
    uv run --project ledger --no-sync python ledger/scripts/labels_rooms.py status

A room is a directory OUTSIDE the repository (~/ledger_rooms/run1/<session>/) holding only the kit files in ROOM_FILES plus
the pass-specific inputs. Sessions run `claude -p` there with the frozen FLAGS: no shell, no MCP servers, file tools
confined to the room (`--restricted`), web fetches to GitHub / GitHub content / Zenodo denied at tool level. Each launch
writes a manifest (files + SHA-256, flags, model, prompt and its hash, PID, start time) under ~/ledger_rooms/run1/_manifests/;
`status` also records the model(s) each session actually used (from its stream log).
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
WORK = REPO / "research" / "ledger" / "labels" / "work"
RAW = REPO / "research" / "ledger" / "labels" / "raw"
ROOMS = Path.home() / "ledger_rooms" / "run1"
MANIFESTS = ROOMS / "_manifests"
ROOM_FILES = ["PROTOCOL.md", "record_schema.json", "type_list.csv", "synonyms.csv", "driver_lines.csv"]
PASS1_EXTRA = ["sources_seed.csv"]
MODEL = "opus"
FALLBACK = "sonnet"  # used only when the main model is busy or unavailable; the model actually used is recorded per session
TOOLS = "Read,Write,Edit,Glob,Grep,WebSearch,WebFetch"
DENY = ["WebFetch(domain:github.com)", "WebFetch(domain:api.github.com)", "WebFetch(domain:gist.github.com)",
        "WebFetch(domain:codeload.github.com)", "WebFetch(domain:raw.githubusercontent.com)", "WebFetch(domain:githubusercontent.com)",
        "WebFetch(domain:objects.githubusercontent.com)", "WebFetch(domain:github.io)", "WebFetch(domain:zenodo.org)"]
FLAGS = ["--restricted", "--strict-mcp-config", "--tools", TOOLS, "--allowedTools", TOOLS, "--disallowedTools", *DENY,
         "--permission-mode", "acceptEdits", "--permission-prompts", "none", "--disable-slash-commands", "--no-chrome",
         "--model", MODEL, "--fallback-model", FALLBACK, "--output-format", "stream-json", "--verbose"]
PREFIX = {"pass1": "p1", "pass2": "p2", "search": "s", "adjudication": "adj"}
PROMPT_FILE = {"pass1": "PROMPT_PASS1.md", "pass2": "PROMPT_PASS2.md", "search": "PROMPT_SEARCH.md", "adjudication": "PROMPT_ADJUDICATE.md"}
DEDICATED = "pugliese_dedicated"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def families() -> dict:
    return json.loads((KIT / "families.json").read_text(encoding="utf-8"))


def prompt_for(pass_id: str, session: str, family: str | None, search_name: str | None = None) -> str:
    fam = families()
    tmpl = (KIT / PROMPT_FILE[pass_id]).read_text(encoding="utf-8")
    rep = {"{SESSION}": session, "{PREFIX}": f"{PREFIX[pass_id]}-{session.split('-', 1)[-1]}"}
    if pass_id == "pass1":
        f = fam["pass1_families"][family]
        rep.update({"{FAMILY_TITLE}": f["title"], "{FAMILY_SCOPE}": f["scope"]})
    if pass_id == "search":
        rep["{SEARCH_SCOPE}"] = fam["search_sessions"][search_name]
    for k, v in rep.items():
        tmpl = tmpl.replace(k, v)
    if family == DEDICATED and pass_id in ("pass2", "adjudication"):
        tmpl += "\n" + (KIT / "DEDICATED_PERMISSION.md").read_text(encoding="utf-8")
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


def _spawn(cmd: list[str], room: Path, session: str, tag: str) -> int:
    log = ROOMS / f"{session}.{tag}.stream.jsonl"
    err = ROOMS / f"{session}.{tag}.stderr.txt"
    with open(log, "w") as out, open(err, "w") as e:
        proc = subprocess.Popen(cmd, cwd=room, stdout=out, stderr=e, stdin=subprocess.DEVNULL, start_new_session=True,
                                env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
    return proc.pid


def launch(pass_id: str, session: str, family: str | None = None, inputs: dict[str, Path] | None = None,
           search_name: str | None = None) -> dict:
    room = build_room(session, pass_id, inputs or {})
    prompt = prompt_for(pass_id, session, family, search_name)
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    pid = _spawn(["claude", "-p", prompt, *FLAGS], room, session, "main")
    man = {"session": session, "pass": pass_id, "family": family, "room": str(room), "runs": [{"tag": "main", "pid": pid,
           "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "prompt_sha256": _sha(prompt.encode()), "prompt": prompt}],
           "model": MODEL, "fallback": FALLBACK, "flags": FLAGS,
           "files": {p.name: _sha(p.read_bytes()) for p in sorted(room.iterdir()) if p.is_file()}}
    (MANIFESTS / f"{session}.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    return man


def _session_id(session: str) -> str | None:
    sid = None
    for log in sorted(ROOMS.glob(f"{session}.*.stream.jsonl")):
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            sid = d.get("session_id") or sid
    return sid


def resume(session: str, tag: str, prompt: str, extra_files: dict[str, Path] | None = None) -> dict:
    mp = MANIFESTS / f"{session}.json"
    man = json.loads(mp.read_text(encoding="utf-8"))
    room = Path(man["room"])
    for name, src in (extra_files or {}).items():
        shutil.copyfile(src, room / name)
    sid = _session_id(session)
    if sid is None:
        raise SystemExit(f"no session id found for {session}")
    pid = _spawn(["claude", "-p", prompt, "--resume", sid, *FLAGS], room, session, tag)
    man["runs"].append({"tag": tag, "pid": pid, "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "resumed_session": sid,
                        "prompt_sha256": _sha(prompt.encode()), "prompt": prompt,
                        "files_added": {n: _sha(Path(s).read_bytes()) for n, s in (extra_files or {}).items()}})
    mp.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    return man


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def status() -> list[dict]:
    rows = []
    for m in sorted(MANIFESTS.glob("*.json")):
        man = json.loads(m.read_text(encoding="utf-8"))
        session = man["session"]
        models, results = set(), []
        for log in sorted(ROOMS.glob(f"{session}.*.stream.jsonl")):
            for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("type") == "system" and d.get("model"):
                    models.add(d["model"])
                msg = d.get("message") if isinstance(d.get("message"), dict) else {}
                if msg.get("model"):
                    models.add(msg["model"])
                if d.get("type") == "result":
                    results.append({"subtype": d.get("subtype"), "cost": d.get("total_cost_usd"), "turns": d.get("num_turns")})
                    models.update((d.get("modelUsage") or {}).keys())
        rp = Path(man["room"]) / "out" / "records.jsonl"
        n_rec = sum(1 for ln in rp.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()) if rp.exists() else 0
        rows.append({"session": session, "alive": any(_alive(r["pid"]) for r in man["runs"]), "records": n_rec, "results": results,
                     "models_used": sorted(models)})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    la = sub.add_parser("launch")
    la.add_argument("pass_id", choices=["pass1", "pass2", "search", "adjudication"])
    la.add_argument("--family")
    la.add_argument("--all", action="store_true")
    la.add_argument("--name")
    pb = sub.add_parser("phaseb")
    pb.add_argument("--session", required=True)
    rp = sub.add_parser("repair")
    rp.add_argument("--session", required=True)
    sub.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "status":
        rows = status()
        for r in rows:
            print(json.dumps(r))
        (ROOMS / "_status.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
        return
    if a.cmd == "phaseb":
        fam = a.session.removeprefix("pass2-")
        q = WORK / "pass2_inputs" / fam / "quotes_to_verify.csv"
        resume(a.session, "phaseb", (KIT / "PROMPT_PASS2_PHASEB.md").read_text(encoding="utf-8"), {"quotes_to_verify.csv": q})
        print("phase B started for", a.session)
        return
    if a.cmd == "repair":
        pass_id = a.session.split("-", 1)[0]
        v = json.loads((RAW / pass_id / a.session / "validation.json").read_text(encoding="utf-8"))
        errs = "\n".join(f"- line {x['line']}: " + "; ".join(x["errors"]) for x in v["invalid"])
        prompt = (KIT / "PROMPT_REPAIR.md").read_text(encoding="utf-8").replace("{ERRORS}", errs)
        resume(a.session, "repair", prompt)
        print("repair round started for", a.session)
        return
    fam = families()
    if a.pass_id == "pass1":
        for f in (list(fam["pass1_families"]) if a.all else [a.family]):
            m = launch("pass1", f"pass1-{f}", f)
            print("launched", m["session"], m["runs"][0]["pid"])
    elif a.pass_id == "pass2":
        for f in (list(fam["pass1_families"]) if a.all else [a.family]):
            d = WORK / "pass2_inputs" / f
            if not (d / "experiments_to_label.csv").exists():
                print("skip", f, "(no experiments)")
                continue
            m = launch("pass2", f"pass2-{f}", f, {"experiments_to_label.csv": d / "experiments_to_label.csv"})
            print("launched", m["session"], m["runs"][0]["pid"])
    elif a.pass_id == "search":
        for n in (list(fam["search_sessions"]) if a.all else [a.name]):
            m = launch("search", f"search-{n}", None, search_name=n)
            print("launched", m["session"], m["runs"][0]["pid"])
    else:
        d = WORK / "adjudication_inputs" / a.name
        m = launch("adjudication", f"adjudication-{a.name}", DEDICATED if a.name == "dedicated" else None,
                   {"disagreements.csv": d / "disagreements.csv"})
        print("launched", m["session"], m["runs"][0]["pid"])


if __name__ == "__main__":
    main()
