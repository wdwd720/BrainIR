"""Transcript audit: a breach is a SUCCESSFUL forbidden access; denied attempts and harness no-content results are not."""

import importlib.util
import json

from brainir_ledger import REPO

spec = importlib.util.spec_from_file_location("labels_audit", REPO / "ledger" / "scripts" / "labels_audit.py")
LA = importlib.util.module_from_spec(spec)
spec.loader.exec_module(LA)


def _transcript(tmp_path, room, calls):
    """calls: list of (name, input, is_error, result_text)."""
    d = tmp_path / "projects" / LA.encode(room)
    d.mkdir(parents=True)
    lines = []
    for i, (name, inp, err, txt) in enumerate(calls):
        lines.append({"message": {"content": [{"type": "tool_use", "id": f"t{i}", "name": name, "input": inp}]}})
        res = {"type": "tool_result", "tool_use_id": f"t{i}", "content": txt}
        if err:
            res["is_error"] = True
        lines.append({"message": {"content": [res]}})
    (d / "s.jsonl").write_text("\n".join(json.dumps(x) for x in lines))
    return tmp_path / "projects"


def test_audit_classification(tmp_path, monkeypatch):
    room = str(tmp_path / "rooms" / "pass1-atlas")
    calls = [
        ("WebFetch", {"url": "https://www.nature.com/articles/s41586-026-11195-y"}, False,
         "Summary: expression restricted to DNs; walking was blocked by silencing; permission statement."),   # success -> breach
        ("WebFetch", {"url": "https://www.biorxiv.org/content/10.1101/2025.09.12.675944v2"}, False,
         "The server returned HTTP 429 Too Many Requests. The response body was not retrieved."),            # no content -> blocked
        ("WebFetch", {"url": "https://github.com/x"}, True, "WebFetch denied access to domain:github.com."),  # denied -> blocked
        ("Grep", {"pattern": "DNa0..", "path": room}, False, "matches"),                                       # regex, in room -> ok
        ("Glob", {"pattern": room + "/**/*.csv"}, False, "files"),                                             # absolute, in room -> ok
        ("Read", {"file_path": "~/.claude/settings.json"}, False, "{...}"),                                    # success outside -> breach
        ("Read", {"file_path": "/etc/hosts"}, True, "/etc/hosts is outside the room; --restricted"),           # denied -> blocked
    ]
    monkeypatch.setattr(LA, "PROJECTS", _transcript(tmp_path, room, calls))
    r = LA.audit_session({"room": room, "session": "pass1-atlas", "pass": "pass1", "family": "atlas"})
    kinds = sorted(i["kind"] for i in r["issues"])
    assert kinds == ["dedicated_source_outside_dedicated_session", "file_outside_room"], r["issues"]
    assert len(r["blocked_attempts"]) == 3
    # the same successful fetch inside the dedicated session is not a breach
    r2 = LA.audit_session({"room": room, "session": "pass1-pugliese_dedicated", "pass": "pass1", "family": "pugliese_dedicated"})
    assert [i["kind"] for i in r2["issues"]] == ["file_outside_room"]


def test_audit_flags_missing_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(LA, "PROJECTS", tmp_path / "none")
    r = LA.audit_session({"room": str(tmp_path / "r"), "session": "pass1-x", "pass": "pass1", "family": "x"})
    assert [i["kind"] for i in r["issues"]] == ["no_transcript"]
