"""Labeler rooms and sessions for labels v2 (LABEL SIDE; never reads predictions). PREREG v2 Part L; LOG L51+.

Rooms are directories OUTSIDE the repository: `~/ledger_rooms/run2/<session>/` holding only kit v2 files, the session's inputs
and the session's assigned sources (copied from the mechanical download cache). Sessions run `claude -p` with run 1's frozen
flags (`labels_rooms.FLAGS`: no shell, `--restricted`, banned hosts denied with every subdomain) plus v2 deny rules for the
repository, every ledger folder outside the room and the orchestrator's temporary folders. `--mode sandbox` additionally
wraps the session in a macOS `sandbox-exec` profile denying those reads (used if the canary shows the tool rules leak).

    labels2_rooms.py launch SPEC.json          # one session from a spec (kind, session, family, sources, inputs)
    labels2_rooms.py enqueue SPEC.json ...     # add specs to the queue
    labels2_rooms.py schedule [--max 7]        # background loop: launch queued specs as slots free up (quota-aware)
    labels2_rooms.py phaseb --session S        # Phase B of a finished second reading (quotes delivered after Phase A)
    labels2_rooms.py repair --session S        # the one repair round for schema-invalid records
    labels2_rooms.py status
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import labels_audit as LA  # noqa: E402  (frozen; only encode/PROJECTS are used)
import labels_rooms as LR  # noqa: E402  (frozen; only FLAGS is used)

HOME = Path.home()
ROOMS = HOME / "ledger_rooms" / "run2"
MANIFESTS = ROOMS / "_manifests"
QUEUE = ROOMS / "_queue"
KIT = REPO / "research" / "ledger" / "kit_v2"
SOURCES = REPO / "data" / "ledger" / "sources_v2"
LOGS = REPO / "data" / "cache" / "ledger_logs"
LAB2_RAW = REPO / "research" / "ledger" / "labels_v2" / "raw"
SCRATCH_HINT = Path(os.environ["LEDGER_SCRATCH"]) if os.environ.get("LEDGER_SCRATCH") else None
KIT_FILES = ["PROTOCOL.md", "record_schema.json", "type_list.csv", "synonyms.csv", "driver_lines.csv"]
PROMPTS = {"reader": "PROMPT_READER.md", "reader_web": "PROMPT_READER_WEB.md", "second": "PROMPT_SECOND.md", "adjudication": "PROMPT_ADJUDICATE.md", "search": "PROMPT_SEARCH.md",
           "atlas_map": "PROMPT_ATLAS_MAP.md", "atlas_code": "PROMPT_ATLAS_CODE.md", "verify": "PROMPT_VERIFY.md"}
PASS_OF = {"reader": "pass1", "reader_web": "pass1", "second": "pass2", "adjudication": "adjudication", "search": "search", "atlas_map": "atlas_map",
           "atlas_code": None, "verify": "verify"}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def deny_paths() -> list[Path]:
    p = [REPO, HOME / "ledger_rooms" / "run1", HOME / "ledger_rooms" / "run1_aux", HOME / "ledger_rooms_review_gates",
         HOME / "ledger_rooms_review_prereg2", HOME / "ledger_rooms" / "run2_canary" / "planted", Path("/private/tmp"), Path("/tmp"),
         LA.PROJECTS / LA.encode(str(REPO)), LA.PROJECTS / (LA.encode(str(HOME / "ledger_rooms" / "run1")) + "-*"),
         LA.PROJECTS / (LA.encode(str(HOME / "ledger_rooms" / "run1_aux")) + "-*")]
    return p + ([SCRATCH_HINT] if SCRATCH_HINT else [])


WEB_KINDS = ("search", "reader_web")
MIRRORS = ("softwareheritage.org", "sourcegraph.com", "archive.org", "gitlab.com", "bitbucket.org", "codeberg.org", "huggingface.co")
NO_WEB_TOOLS = "Read,Write,Edit,Glob,Grep"


def flags_v2(kind: str = "search") -> list[str]:
    """Run 1's frozen flags with the v2 deny rules added to its --disallowedTools list. Only search sessions and the reader of
    unreachable sources keep WebSearch/WebFetch (PREREG v2 L13); every other kind gets file tools only."""
    flags = list(LR.FLAGS)
    if kind not in WEB_KINDS:
        flags = [NO_WEB_TOOLS if (k > 0 and flags[k - 1] in ("--tools", "--allowedTools")) else f for k, f in enumerate(flags)]
    i = flags.index("--disallowedTools")
    j = i + 1
    while j < len(flags) and not flags[j].startswith("--"):
        j += 1
    extra = [f"WebFetch(domain:{d})" for d in MIRRORS] + [f"WebFetch(domain:*.{d})" for d in MIRRORS]
    for p in deny_paths():
        for tool in ("Read", "Edit"):
            extra.append(f"{tool}(/{p}/**)")  # "//abs/path/**" = absolute path pattern
    return flags[:j] + extra + flags[j:]


def sandbox_profile(room: Path) -> str:
    own_proj = LA.PROJECTS / LA.encode(str(room))
    rules = ["(version 1)", "(allow default)"]
    for p in deny_paths() + [HOME / "ledger_rooms", LA.PROJECTS]:
        if str(p) in ("/private/tmp", "/tmp") or "*" in str(p):
            continue  # claude needs its own temp files; the orchestrator's folder is denied via SCRATCH_HINT
        rules.append(f'(deny file-read* (subpath "{p}"))')
    rules += [f'(allow file-read* (subpath "{room}"))', f'(allow file-read* (subpath "{own_proj}"))']
    return "\n".join(rules)


def spawn(cmd: list[str], room: Path, log: Path, mode: str = "tool") -> int:
    err = log.with_suffix(".stderr.txt")
    if mode == "sandbox":
        cmd = ["sandbox-exec", "-p", sandbox_profile(room)] + cmd
    with open(log, "w") as out, open(err, "w") as e:
        proc = subprocess.Popen(cmd, cwd=room, stdout=out, stderr=e, stdin=subprocess.DEVNULL, start_new_session=True,
                                env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
    return proc.pid


def transcripts(room: Path) -> list[Path]:
    d = LA.PROJECTS / LA.encode(str(room))
    return sorted(d.glob("*.jsonl")) if d.exists() else []


def prompt_for(spec: dict) -> str:
    kind = spec["kind"]
    t = (KIT / PROMPTS[kind]).read_text(encoding="utf-8")
    fam = json.loads((KIT / "families_v2.json").read_text(encoding="utf-8"))
    rep = {"{SESSION}": spec["session"], "{PREFIX}": spec["session"]}
    if kind in ("reader", "reader_web"):
        f = fam["reader_families"][spec["family"]]
        rep.update({"{FAMILY_TITLE}": f["title"], "{FAMILY_SCOPE}": f["scope"]})
    if kind == "search":
        rep.update({"{SEARCH_KIND}": spec["search_kind"], "{SEARCH_SCOPE}": fam["search_kinds"][spec["search_kind"]]})
    if kind == "atlas_code":
        rep["{PASS_ID}"] = spec["pass_id"]
    for k, v in rep.items():
        t = t.replace(k, v)
    if spec.get("family") == "dedicated":
        t += "\n" + (KIT / "DEDICATED_PERMISSION.md").read_text(encoding="utf-8")
    return t


def build_room(spec: dict) -> Path:
    room = ROOMS / spec["session"]
    if room.exists():
        raise SystemExit(f"room {room} exists already; rooms are single-use")
    (room / "out").mkdir(parents=True)
    for name in KIT_FILES:
        if spec["kind"] == "search" and name == "record_schema.json":
            continue
        shutil.copyfile(KIT / name, room / name)
    for name, src in (spec.get("inputs") or {}).items():
        shutil.copyfile(src, room / name)
    slugs = spec.get("sources") or []
    if slugs:
        rows = ["doi,slug,title,status"]
        for s in slugs:
            src = SOURCES / s
            shutil.copytree(src, room / "sources" / s)
            m = json.loads((src / "meta.json").read_text())
            title = str(m.get("title") or "").replace('"', "'")
            rows.append(f'{m.get("doi")},{s},"{title}",{m.get("status")}')
        (room / "assigned_sources.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return room


def launch(spec: dict, mode: str = "tool") -> dict:
    room = build_room(spec)
    prompt = prompt_for(spec)
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    pid = spawn(["claude", "-p", prompt, *flags_v2(spec["kind"])], room, ROOMS / f"{spec['session']}.main.stream.jsonl", mode)
    files = {}
    for p in sorted(room.rglob("*")):
        if p.is_file() and "out" not in p.relative_to(room).parts[:1]:
            files[str(p.relative_to(room))] = _sha(p.read_bytes())
    pid_ = spec.get("pass_id") or PASS_OF[spec["kind"]]
    man = {"session": spec["session"], "kind": spec["kind"], "family": spec.get("family"), "pass_id": pid_, "pass": pid_,
           "room": str(room), "mode": mode, "sources": spec.get("sources") or [], "flags": flags_v2(spec["kind"]),
           "runs": [{"tag": "main", "pid": pid, "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "prompt_sha256": _sha(prompt.encode()),
                     "prompt": prompt}], "files": files}
    (MANIFESTS / f"{spec['session']}.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    return man


def _session_id(session: str) -> str | None:
    sid = None
    for log in sorted(ROOMS.glob(f"{session}.*.stream.jsonl")):
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                sid = json.loads(line).get("session_id") or sid
            except json.JSONDecodeError:
                continue
    return sid


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def resume(session: str, tag: str, prompt: str, extra_files: dict[str, Path] | None = None) -> dict:
    mp = MANIFESTS / f"{session}.json"
    man = json.loads(mp.read_text(encoding="utf-8"))
    if any(_alive(r["pid"]) for r in man["runs"]):
        raise SystemExit(f"{session} is still running")
    room = Path(man["room"])
    for name, src in (extra_files or {}).items():
        shutil.copyfile(src, room / name)
    sid = _session_id(session)
    if sid is None:
        raise SystemExit(f"no session id for {session}")
    pid = spawn(["claude", "-p", prompt, "--resume", sid, *flags_v2(man["kind"])], room, ROOMS / f"{session}.{tag}.stream.jsonl", man.get("mode", "tool"))
    man["runs"].append({"tag": tag, "pid": pid, "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "resumed_session": sid,
                        "prompt_sha256": _sha(prompt.encode()), "prompt": prompt,
                        "files_added": {n: _sha(Path(s).read_bytes()) for n, s in (extra_files or {}).items()}})
    mp.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    return man


def status() -> list[dict]:
    rows = []
    for m in sorted(MANIFESTS.glob("*.json")):
        man = json.loads(m.read_text(encoding="utf-8"))
        s, models, results = man["session"], set(), []
        for log in sorted(ROOMS.glob(f"{s}.*.stream.jsonl")):
            for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = d.get("message") if isinstance(d.get("message"), dict) else {}
                if msg.get("model"):
                    models.add(msg["model"])
                if d.get("type") == "result":
                    results.append({"subtype": d.get("subtype"), "turns": d.get("num_turns")})
        out = Path(man["room"]) / "out"
        n_rec = sum(1 for ln in (out / "records.jsonl").read_text(errors="replace").splitlines() if ln.strip()) if (out / "records.jsonl").exists() else 0
        n_disp = max(0, sum(1 for _ in (out / "dispositions.csv").open()) - 1) if (out / "dispositions.csv").exists() else 0
        rows.append({"session": s, "kind": man["kind"], "alive": any(_alive(r["pid"]) for r in man["runs"]), "records": n_rec,
                     "dispositions": n_disp, "n_sources": len(man.get("sources") or []), "results": results, "models": sorted(models)})
    return rows


def quota() -> float | None:
    """Latest seven-day utilization reported to any v2 session (rate_limit_event lines only)."""
    best = None
    for log in ROOMS.glob("*.stream.jsonl"):
        for line in log.read_text(errors="replace").splitlines():
            if '"rate_limit_event"' in line:
                try:
                    u = json.loads(line)["rate_limit_info"]["unifiedWindows"]["seven_day"]["utilization"]
                    best = u if best is None else max(best, u)
                except (KeyError, TypeError, json.JSONDecodeError):
                    pass
    return best


def schedule(max_alive: int, idle_exit_min: float, mode: str) -> None:
    """Launch queued specs (oldest first) while fewer than `max_alive` sessions run; above 85 % quota use at most 3."""
    QUEUE.mkdir(parents=True, exist_ok=True)
    (QUEUE / "launched").mkdir(exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / "labels2_scheduler.log"
    idle_since = time.time()
    while True:
        alive = sum(1 for r in status() if r["alive"])
        q = quota()
        cap = max_alive if (q is None or q < 0.85) else min(3, max_alive)
        pending = sorted(QUEUE.glob("*.json"), key=lambda p: p.stat().st_mtime)
        while pending and alive < cap:
            p = pending.pop(0)
            spec = json.loads(p.read_text())
            try:
                launch(spec, spec.get("mode", mode))
                msg = f"launched {spec['session']}"
            except SystemExit as e:
                msg = f"skipped {spec.get('session')}: {e}"
            p.rename(QUEUE / "launched" / p.name)
            alive += 1
            with open(log, "a") as fh:
                fh.write(f"{time.strftime('%H:%M:%S')} {msg} (alive {alive}, cap {cap}, quota {q})\n")
        if pending or alive:
            idle_since = time.time()
        elif time.time() - idle_since > idle_exit_min * 60:
            with open(log, "a") as fh:
                fh.write(f"{time.strftime('%H:%M:%S')} queue empty and no session alive for {idle_exit_min} min; scheduler exits\n")
            return
        time.sleep(30)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("launch")
    a.add_argument("spec")
    a.add_argument("--mode", default="tool", choices=["tool", "sandbox"])
    e = sub.add_parser("enqueue")
    e.add_argument("specs", nargs="+")
    s = sub.add_parser("schedule")
    s.add_argument("--max", type=int, default=7)
    s.add_argument("--idle-exit-min", type=float, default=240)
    s.add_argument("--mode", default="tool", choices=["tool", "sandbox"])
    pb = sub.add_parser("phaseb")
    pb.add_argument("--session", required=True)
    pb.add_argument("--quotes", required=True)
    rp = sub.add_parser("repair")
    rp.add_argument("--session", required=True)
    rp.add_argument("--errors", required=True)
    sub.add_parser("status")
    sub.add_parser("quota")
    a = ap.parse_args()
    if a.cmd == "launch":
        print(json.dumps({k: v for k, v in launch(json.loads(Path(a.spec).read_text()), a.mode).items() if k in ("session", "room", "mode")}))
    elif a.cmd == "enqueue":
        QUEUE.mkdir(parents=True, exist_ok=True)
        for sp in a.specs:
            d = json.loads(Path(sp).read_text())
            (QUEUE / f"{time.time():.6f}_{d['session']}.json").write_text(json.dumps(d))
        print("queued", len(a.specs))
    elif a.cmd == "schedule":
        schedule(a.max, a.idle_exit_min, a.mode)
    elif a.cmd == "phaseb":
        man = json.loads((MANIFESTS / f"{a.session}.json").read_text(encoding="utf-8"))
        if any(_alive(r["pid"]) for r in man["runs"]):
            raise SystemExit(f"{a.session} is still running; Phase B starts only after Phase A has finished")
        if any(r["tag"] == "phaseb" for r in man["runs"]):
            raise SystemExit(f"{a.session}: Phase B already started")
        # freeze Phase A before the first reader's quotes enter the room (as run 1's labels_rooms.phaseb)
        room = Path(man["room"])
        snap = LAB2_RAW / man["pass"] / a.session / "phaseA_snapshot"
        snap.mkdir(parents=True, exist_ok=True)
        hashes = {}
        for name in ("records.jsonl", "not_found.csv", "notes.md"):
            src = room / "out" / name
            if src.exists():
                shutil.copyfile(src, snap / name)
                hashes[name] = _sha(src.read_bytes())
        (snap / "phaseA_hashes.json").write_text(json.dumps({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sha256": hashes},
                                                            indent=1) + "\n", encoding="utf-8")
        prompt = (KIT / "PROMPT_PHASEB.md").read_text(encoding="utf-8")
        resume(a.session, "phaseb", prompt, {"quotes_to_verify.csv": Path(a.quotes)})
        print("phase B started for", a.session, "; Phase A snapshot", hashes)
    elif a.cmd == "repair":
        prompt = (KIT / "PROMPT_REPAIR.md").read_text(encoding="utf-8").replace("{ERRORS}", Path(a.errors).read_text())
        resume(a.session, "repair", prompt)
        print("repair started for", a.session)
    elif a.cmd == "status":
        for r in status():
            print(json.dumps(r))
    else:
        print(json.dumps({"seven_day_utilization": quota()}))


if __name__ == "__main__":
    main()
