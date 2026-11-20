"""Transcript audit of the labels v2 sessions (LABEL SIDE; PREREG v2 L3). Runs the FROZEN `labels_audit.audit_session` on every
v2 session (its dedicated rule applies to the v2 `dedicated` family) and then applies the single v2 exception: a successful
read of a file in the session's OWN `<project>/<session-id>/tool-results/` folder that the session's own WebFetch saved from
an allowed host is not a breach. Everything else the frozen audit calls a breach stays a breach.

    uv run --project ledger --no-sync python ledger/scripts/labels2_audit.py            # every session except the verifier
                                                                                    # -> research/ledger/labels_v2/transcript_audit.{json,md}
    uv run --project ledger --no-sync python ledger/scripts/labels2_audit.py --verify   # verifier sessions only (after the labels lock)
                                                                                    # -> research/ledger/labels_v2/verify/transcript_audit_verify.{json,md}
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labels_audit as LA  # noqa: E402  (frozen)
import labels_collect as LC  # noqa: E402  (frozen; BREACH_KINDS)
import labels2_rooms as R2  # noqa: E402

OUT = HERE.parents[1] / "research" / "ledger" / "labels_v2"


def _banned(host: str) -> bool:
    host = (host or "").lower()
    return any(host == b or host.endswith("." + b) or b in host for b in LA.BANNED_HOSTS)


MIRRORS = ("softwareheritage.org", "sourcegraph.com", "archive.org", "gitlab.com", "bitbucket.org", "codeberg.org", "huggingface.co",
           "nbviewer.jupyter.org")
TOKENS = re.compile(r"wdwd720|smpuglie|BrainIR", re.I)


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, list):
        for y in x:
            yield from _strings(y)
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)


def scan(room: str) -> tuple[list[str], list[dict]]:
    """(the raw text of the session's own tool results, excluding WebFetch results from banned hosts; review B3: exemption paths
    are matched verbatim in it, not extracted by a pattern) and v2-only breach issues: successful fetches of the v2 mirrors
    (L3 kind 2; a WebFetch answer starting with a fetch-failure message is not a success) and WebSearch/WebFetch results or
    reads/greps of the session's own tool-results files whose text names the repository, its owner or the authors' code
    (L3 kind 5)."""
    calls, texts, issues = {}, [], []
    for f in R2.transcripts(Path(room)):
        for line in f.read_text(errors="replace").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = (d.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                if c.get("type") == "tool_use":
                    calls[c["id"]] = (c.get("name"), c.get("input") or {})
                elif c.get("type") == "tool_result" and c.get("tool_use_id") in calls:
                    name, inp = calls[c["tool_use_id"]]
                    raw = "\n".join(list(_strings(c.get("content"))) + list(_strings(d.get("toolUseResult"))))
                    host = (urlparse(inp.get("url", "")).hostname or "") if name == "WebFetch" else ""
                    ok = not c.get("is_error") and not (name == "WebFetch" and raw.lstrip().startswith(LA.FETCH_FAIL_PREFIXES))
                    if name == "WebFetch" and _banned(host):
                        continue
                    if name == "WebFetch" and ok and any(host == m or host.endswith("." + m) for m in MIRRORS):
                        issues.append({"kind": "banned_host_fetch", "url": inp.get("url", "")})
                    target = str(inp.get("file_path") or inp.get("path") or "")
                    own_tr = name in ("Read", "Grep") and "/tool-results/" in target
                    if ok and (name in ("WebSearch", "WebFetch") or own_tr) and TOKENS.search(raw):
                        issues.append({"kind": "forbidden_token_in_tool_result", "tool": name, "token": TOKENS.search(raw).group(0)})
                    texts.append(raw)
    return texts, issues


def audit(verify: bool = False) -> list[dict]:
    """PREREG v2 L3/L11: the main audit covers every session except the verifier and is never rewritten after the labels lock;
    the verifier is audited separately into new files under `labels_v2/verify/`."""
    out, stem = (OUT / "verify", "transcript_audit_verify") if verify else (OUT, "transcript_audit")
    if not verify and (OUT.parent / "LOCK_labels_v2.json").exists():
        raise SystemExit("LOCK_labels_v2.json exists: the main audit is locked; use --verify for the verifier")
    rows = []
    home = str(Path.home())
    for m in sorted(R2.MANIFESTS.glob("*.json")):
        man = json.loads(m.read_text(encoding="utf-8"))
        if (man["kind"] == "verify") != verify:
            continue
        v1man = dict(man, family="pugliese_dedicated" if man.get("family") == "dedicated" else man.get("family"))
        r = LA.audit_session(v1man)
        own_dir = str(LA.PROJECTS / LA.encode(man["room"]))
        texts, extra = scan(man["room"])
        breaches, own_reads = list(extra), 0
        if not r["transcripts"]:
            breaches.append({"kind": "no_transcript"})  # L3 kind 4
        for i in r["issues"]:
            p = str(i.get("path") or "")
            if i["kind"] == "file_outside_room" and p.startswith(own_dir + "/") and "/tool-results/" in p and any(p in x for x in texts):
                own_reads += 1
                continue
            if i["kind"] in LC.BREACH_KINDS:
                breaches.append({k: (str(v).replace(home, "$HOME").replace(LA.encode(home), "-HOME") if isinstance(v, str) else v)
                                 for k, v in i.items()})
        rows.append({"session": man["session"], "kind": man["kind"], "family": man.get("family"), "breach": bool(breaches),
                     "issues": breaches, "own_tool_result_reads": own_reads, "blocked_attempts": len(r["blocked_attempts"]),
                     "n_tool_calls": r["n_tool_calls"], "n_fetches": r["n_fetches"], "n_searches": r["n_searches"],
                     "n_phrase_hits": r["n_phrase_hits"], "transcripts": len(r["transcripts"])})
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{stem}.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    md = ["# Labels v2 transcript audit (frozen audit + the v2 own-tool-results exception)", "",
          "| session | kind | breach | issues | own tool-result reads | blocked attempts | tool calls | fetches |", "|---|---|---|---|---|---|---|---|"]
    md += [f"| {r['session']} | {r['kind']} | {'YES' if r['breach'] else 'no'} | {len(r['issues'])} | {r['own_tool_result_reads']} | "
           f"{r['blocked_attempts']} | {r['n_tool_calls']} | {r['n_fetches']} |" for r in rows]
    (out / f"{stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"sessions": len(rows), "breaching": [r["session"] for r in rows if r["breach"]],
                      "own_tool_result_reads": sum(r["own_tool_result_reads"] for r in rows)}))
    return rows


if __name__ == "__main__":
    audit(verify="--verify" in sys.argv[1:])
