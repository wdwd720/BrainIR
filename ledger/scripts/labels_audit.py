"""Audit labeler session transcripts (LABEL SIDE: reads only Claude Code transcripts of the labeler rooms).

    uv run --project ledger --no-sync python ledger/scripts/labels_audit.py   # -> research/ledger/labels/transcript_audit.{json,md}

For every labeler session (manifests in ~/ledger_rooms/run1/_manifests/) it reads the session transcript(s) in
~/.claude/projects/<encoded room path>/*.jsonl and reports:
* file-tool calls (Read/Glob/Grep/Write/Edit) whose path is outside the session's room;
* WebFetch URLs on banned hosts (GitHub, raw GitHub, Zenodo) or of the two dedicated-session sources outside that session;
* WebSearch queries and fetched URLs that mention the repository, the authors' code or simulation scores;
* any tool result text containing model/simulation phrases (a possible sight of a score).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOMS = Path.home() / "ledger_rooms" / "run1"
PROJECTS = Path.home() / ".claude" / "projects"
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "ledger" / "labels"
BANNED_HOSTS = ("github.com", "githubusercontent.com", "zenodo.org")
DEDICATED = ("10.1038/s41586-026-11195-y", "2025.09.12.675944", "2026.04.29.721658", "s41586-026-11195")
PHRASES = re.compile(r"rhythmicity score|motor rhythmicity|activation screen|connectome simulation|simulated activation|BrainIR|"
                     r"wdwd720|smpuglie|Pugliese", re.I)


def encode(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def transcripts(room: str) -> list[Path]:
    d = PROJECTS / encode(room)
    return sorted(d.glob("*.jsonl")) if d.exists() else []


def audit_session(man: dict) -> dict:
    room = man["room"]
    dedicated = man.get("family") == "pugliese_dedicated"
    issues, fetches, searches, phrase_hits = [], [], [], []
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
                    name, inp = c.get("name"), c.get("input") or {}
                    if name in ("Read", "Write", "Edit", "Glob", "Grep"):
                        p = str(inp.get("file_path") or inp.get("path") or "")
                        if p and not (p.startswith(room) or not p.startswith("/")):
                            issues.append({"kind": "file_outside_room", "tool": name, "path": p})
                    if name == "WebFetch":
                        url = str(inp.get("url", ""))
                        fetches.append(url)
                        if any(h in url for h in BANNED_HOSTS):
                            issues.append({"kind": "banned_host_fetch", "url": url})
                        if not dedicated and any(x in url for x in DEDICATED):
                            issues.append({"kind": "dedicated_source_outside_dedicated_session", "url": url})
                    if name == "WebSearch":
                        q = str(inp.get("query", ""))
                        searches.append(q)
                        if PHRASES.search(q):
                            issues.append({"kind": "search_mentions_model", "query": q})
                if c.get("type") == "tool_result":
                    txt = json.dumps(c.get("content"))
                    for m in PHRASES.finditer(txt):
                        s = max(0, m.start() - 80)
                        phrase_hits.append(txt[s: m.end() + 80])
    return {"session": man["session"], "pass": man["pass"], "family": man.get("family"), "transcripts": [f.name for f in files],
            "n_fetches": len(fetches), "n_searches": len(searches), "issues": issues, "n_phrase_hits_in_tool_results": len(phrase_hits),
            "phrase_hit_examples": phrase_hits[:5]}


def main() -> None:
    rows = [audit_session(json.loads(m.read_text(encoding="utf-8"))) for m in sorted((ROOMS / "_manifests").glob("*.json"))]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "transcript_audit.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8", newline="\n")
    md = ["# Labeler transcript audit", "", "| session | transcripts | fetches | searches | issues | phrase hits in tool results |",
          "|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['session']} | {len(r['transcripts'])} | {r['n_fetches']} | {r['n_searches']} | {len(r['issues'])} | "
                  f"{r['n_phrase_hits_in_tool_results']} |")
    md += ["", "Issues (all sessions):", ""]
    for r in rows:
        for i in r["issues"]:
            md.append(f"- {r['session']}: {json.dumps(i)}")
    (OUT / "transcript_audit.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
