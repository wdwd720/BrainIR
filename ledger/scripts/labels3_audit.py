"""Transcript audit of the exam 2 label sessions (LABEL SIDE; PREREG v3 T7, T8). Run 2's audit as it stands (`labels2_audit.py`:
the frozen `labels_audit.audit_session` plus run 2's single exception for the session's own WebFetch tool-result files, and its scan
for mirror fetches and forbidden tokens), applied to run 3's sessions (`labels3_rooms` re-points the launcher's manifests) and
written under `labels_h1/`. A session breached when any issue remains (T7); all its records are then excluded.

    uv run --project ledger --no-sync python ledger/scripts/labels3_audit.py            # every session except verifiers
    uv run --project ledger --no-sync python ledger/scripts/labels3_audit.py --verify   # verifier sessions only
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labels3_rooms as R3  # noqa: E402  (re-points labels2_rooms)
import labels2_audit as A2  # noqa: E402

LA, LC, R2 = A2.LA, A2.LC, R3.R2
OUT = R3.REPO / "research" / "ledger" / "labels_h1"


def audit(verify: bool = False) -> list[dict]:
    out, stem = (OUT / "verify", "transcript_audit_verify") if verify else (OUT, "transcript_audit")
    if not verify and (OUT.parent / "LOCK_labels_h1.json").exists():
        raise SystemExit("LOCK_labels_h1.json exists: the main audit is locked; use --verify for the verifier")
    rows, home = [], str(Path.home())
    for m in sorted(R2.MANIFESTS.glob("*.json")):
        man = json.loads(m.read_text(encoding="utf-8"))
        if (man["kind"] == "verify") != verify:
            continue
        r = LA.audit_session(dict(man))
        own_dir = str(LA.PROJECTS / LA.encode(man["room"]))
        texts, extra = A2.scan(man["room"])
        breaches, own_reads = list(extra), 0
        if not r["transcripts"]:
            breaches.append({"kind": "no_transcript"})
        for i in r["issues"]:
            p = str(i.get("path") or "")
            if i["kind"] == "file_outside_room" and p.startswith(own_dir + "/") and "/tool-results/" in p and any(p in x for x in texts):
                own_reads += 1
                continue
            if i["kind"] in LC.BREACH_KINDS:
                breaches.append({k: (str(v).replace(home, "$HOME").replace(LA.encode(home), "-HOME") if isinstance(v, str) else v)
                                 for k, v in i.items()})
        rows.append({"session": man["session"], "kind": man["kind"], "breach": bool(breaches), "issues": breaches,
                     "own_tool_result_reads": own_reads, "blocked_attempts": len(r["blocked_attempts"]), "n_tool_calls": r["n_tool_calls"],
                     "n_fetches": r["n_fetches"], "n_searches": r["n_searches"], "transcripts": len(r["transcripts"])})
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{stem}.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8", newline="\n")
    md = ["# Labels h1 transcript audit (run 2's audit applied to run 3's sessions)", "",
          "| session | kind | breach | issues | own tool-result reads | blocked attempts | tool calls | fetches |", "|---|---|---|---|---|---|---|---|"]
    md += [f"| {r['session']} | {r['kind']} | {'YES' if r['breach'] else 'no'} | {len(r['issues'])} | {r['own_tool_result_reads']} | "
           f"{r['blocked_attempts']} | {r['n_tool_calls']} | {r['n_fetches']} |" for r in rows]
    (out / f"{stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"sessions": len(rows), "breaching": [r["session"] for r in rows if r["breach"]]}))
    return rows


if __name__ == "__main__":
    audit(verify="--verify" in sys.argv[1:])
