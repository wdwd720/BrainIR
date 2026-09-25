"""Short progress view of running agents (orchestrator): last assistant messages and tool-call counts from their event streams.

    uv run --no-sync python scripts/p3agent/progress.py [name ...] [--n 2]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

AUDIT = Path(r"C:\Dev\BrainIR_p3audit\agents")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--n", type=int, default=2)
    args = ap.parse_args(argv)
    streams = sorted(AUDIT.glob("*.jsonl"))
    latest = {}
    for s in streams:
        name = s.name.split(".")[0]
        if not args.names or name in args.names:
            latest[name] = s
    for name, s in sorted(latest.items()):
        texts, tools, cost = [], 0, None
        for line in s.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                o = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if o.get("type") == "assistant":
                cost = None                     # activity after a result event (a resumed session replays the old result first)
                for c in o.get("message", {}).get("content", []):
                    if c.get("type") == "text" and c["text"].strip():
                        texts.append(c["text"].strip().replace("\n", " "))
                    elif c.get("type") == "tool_use":
                        tools += 1
            elif o.get("type") == "result" and o.get("num_turns", 1) > 0:
                cost = o.get("total_cost_usd")
        print(f"== {name} ({s.name}): {tools} tool calls{'; FINISHED' if cost is not None else ''}")
        for t in texts[-args.n:]:
            print("   -", t[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
