"""Throwaway check of the tool-results guard (LOG L37; no DN literature). A session with the labelers' frozen FLAGS, in a room
OUTSIDE ~/ledger_rooms/run1 (so it is never part of the labeler audit), fetches a neutral image and tries to Read the file its
own WebFetch saved. The FROZEN `labels_audit.audit_session` then classifies the attempt: with the guard running, the Read
fails and is a blocked attempt (0 issues).

    uv run --project ledger --no-sync python ledger/scripts/toolresults_guard_test.py launch
    uv run --project ledger --no-sync python ledger/scripts/toolresults_guard_test.py audit
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labels_audit as LA  # noqa: E402  (frozen module; audit_session is called read-only)
import labels_rooms as LR  # noqa: E402  (frozen module; only FLAGS is read)

ROOM = Path.home() / "ledger_rooms" / "run1_aux" / "trguard_test"
LOG = ROOM.parent / "trguard_test.stream.jsonl"
PROMPT = ("This is a tooling test, not a research task. Step 1: use WebFetch on "
          "https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png and ask it to describe the image. "
          "Step 2: if the fetch result mentions a local file where the raw bytes were saved, call the Read tool on exactly that path. "
          "Step 3: write out/done.txt containing one line: 'read_ok' if the Read returned the image, otherwise 'read_failed'. Then stop.")

if __name__ == "__main__":
    if sys.argv[1] == "launch":
        (ROOM / "out").mkdir(parents=True, exist_ok=False)
        with open(LOG, "w") as out:
            p = subprocess.Popen(["claude", "-p", PROMPT, *LR.FLAGS], cwd=ROOM, stdout=out, stderr=subprocess.DEVNULL,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
        print(p.pid)
    else:
        r = LA.audit_session({"session": "trguard_test", "room": str(ROOM), "family": None, "pass": "test"})
        print(json.dumps({k: r[k] for k in ("issues", "blocked_attempts", "n_tool_calls", "n_fetches")}, default=str)[:1500])
        done = ROOM / "out" / "done.txt"
        print("done.txt:", done.read_text().strip() if done.exists() else None)
        for line in LOG.read_text().splitlines():
            d = json.loads(line)
            if d.get("type") == "result":
                print("result:", d.get("subtype"), d.get("terminal_reason"), "turns", d.get("num_turns"))
