"""Audit labeler session transcripts (LABEL SIDE: reads only Claude Code transcripts of the labeler rooms).

    uv run --project ledger --no-sync python ledger/scripts/labels_audit.py   # -> research/ledger/labels/transcript_audit.{json,md}

For every labeler session (manifests in ~/ledger_rooms/run1/_manifests/) it reads the session transcript(s) in
~/.claude/projects/<encoded room path>/*.jsonl, pairs every tool call with its result, and reports
* BREACHES (PREREG section 6; they exclude the session's records): a file-tool call outside the room that SUCCEEDED; a web
  fetch that SUCCEEDED on a banned host (GitHub and its content hosts and mirrors, Zenodo) or, outside the dedicated
  sessions, of the two dedicated sources; a session without any transcript (it cannot be audited);
* blocked attempts (denied by the tool permissions; reported, not breaches);
* web searches that mention the model, the authors' code or the repository, and model/simulation phrases seen in tool
  results (a possible sight of a score; reported).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOMS = Path.home() / "ledger_rooms" / "run1"
PROJECTS = Path.home() / ".claude" / "projects"
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "ledger" / "labels"
BANNED_HOSTS = ("github.com", "githubusercontent.com", "github.io", "zenodo.org", "jsdelivr.net", "nbviewer", "githack.com",
                "statically.io", "gitee.com")
BANNED_URL_TOKENS = ("smpuglie", "pugliese_2026", "wdwd720", "brainir")
DEDICATED = ("10.1038/s41586-026-11195-y", "2025.09.12.675944", "2026.04.29.721658", "s41586-026-11195")
PHRASES = re.compile(r"rhythmicity score|motor rhythmicity|activation screen|connectome simulation|simulated activation|BrainIR|"
                     r"wdwd720|smpuglie|Pugliese", re.I)
DENIAL = re.compile(r"denied|not allowed|outside (of )?the (allowed )?working director|permission|restricted|blocked|"
                    r"does not have access|is not permitted", re.I)


def encode(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def transcripts(room: str) -> list[Path]:
    d = PROJECTS / encode(room)
    return sorted(d.glob("*.jsonl")) if d.exists() else []


def _outside(p: str, room: str) -> bool:
    if not p:
        return False
    if p.startswith("~") or ".." in Path(p).parts:
        return True
    return p.startswith("/") and not (p == room or p.startswith(room + "/"))


def audit_session(man: dict) -> dict:
    room = man["room"]
    dedicated = man.get("family") == "pugliese_dedicated"
    calls: dict[str, dict] = {}
    results: dict[str, dict] = {}
    files = transcripts(room)
    for f in files:
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = d.get("message") if isinstance(d.get("message"), dict) else {}
            for c in msg.get("content") or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_use":
                    calls[c.get("id")] = {"name": c.get("name"), "input": c.get("input") or {}}
                elif c.get("type") == "tool_result":
                    results[c.get("tool_use_id")] = {"is_error": bool(c.get("is_error")), "text": json.dumps(c.get("content"))}
    issues, blocked, searches, phrase_hits = [], [], [], []
    n_fetch = 0
    for cid, call in calls.items():
        res = results.get(cid, {"is_error": True, "text": "no result"})
        failed = res["is_error"] or bool(DENIAL.search(res["text"][:400]))
        name, inp = call["name"], call["input"]
        if name in ("Read", "Write", "Edit", "Glob", "Grep"):
            p = str(inp.get("file_path") or inp.get("path") or "")
            pat = str(inp.get("pattern") or "") if name in ("Glob", "Grep") else ""
            if _outside(p, room) or pat.startswith("/") or pat.startswith("~") or ".." in pat:
                (blocked if failed else issues).append({"kind": "file_outside_room", "tool": name, "path": p or pat})
        elif name == "WebFetch":
            url = str(inp.get("url", ""))
            n_fetch += 1
            low = url.lower()
            if any(h in low for h in BANNED_HOSTS) or any(t in low for t in BANNED_URL_TOKENS):
                (blocked if failed else issues).append({"kind": "banned_host_fetch", "url": url})
            if not dedicated and any(x in low for x in DEDICATED):
                (blocked if failed else issues).append({"kind": "dedicated_source_outside_dedicated_session", "url": url})
        elif name == "WebSearch":
            q = str(inp.get("query", ""))
            searches.append(q)
            if PHRASES.search(q):
                phrase_hits.append(f"search: {q}")
        txt = res["text"]
        if name in ("WebFetch", "WebSearch", "Read"):
            for m in PHRASES.finditer(txt):
                s = max(0, m.start() - 80)
                phrase_hits.append(txt[s: m.end() + 80])
    if not files:
        issues.append({"kind": "no_transcript", "room": room})
    return {"session": man["session"], "pass": man["pass"], "family": man.get("family"), "transcripts": [f.name for f in files],
            "n_tool_calls": len(calls), "n_fetches": n_fetch, "n_searches": len(searches), "issues": issues, "blocked_attempts": blocked,
            "n_phrase_hits": len(phrase_hits), "phrase_hit_examples": phrase_hits[:8]}


def main() -> None:
    rows = [audit_session(json.loads(m.read_text(encoding="utf-8"))) for m in sorted((ROOMS / "_manifests").glob("*.json"))]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "transcript_audit.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8", newline="\n")
    md = ["# Labeler transcript audit", "", "| session | transcripts | tool calls | fetches | searches | BREACHES | blocked attempts | "
          "model/score phrases |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['session']} | {len(r['transcripts'])} | {r['n_tool_calls']} | {r['n_fetches']} | {r['n_searches']} | {len(r['issues'])} | "
                  f"{len(r['blocked_attempts'])} | {r['n_phrase_hits']} |")
    md += ["", "Breaches (exclude the session's records, PREREG 6):", ""]
    for r in rows:
        for i in r["issues"]:
            md.append(f"- {r['session']}: {json.dumps(i)}")
    md += ["", "Blocked attempts (denied by the tool permissions; not breaches):", ""]
    for r in rows:
        for i in r["blocked_attempts"]:
            md.append(f"- {r['session']}: {json.dumps(i)}")
    md += ["", "Model/simulation phrases seen in tool results (reported only; records are excluded only through the readers' own saw_simulation_score flag or a breach):", ""]
    for r in rows:
        for h in r["phrase_hit_examples"]:
            md.append(f"- {r['session']}: {h[:240]!r}")
    (OUT / "transcript_audit.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(md[: 4 + len(rows)]))


if __name__ == "__main__":
    main()
