"""Replace the user's home-directory prefix in label-side outputs before they are committed (LOG L40; CLAUDE.md rule 4: no
absolute paths in committed files). Only two literal substitutions are made:

    "<home>/"            -> "$HOME/"     (e.g. the room path in a session manifest, a transcript path in the audit)
    "-<encoded home>-"   -> "-HOME-"     (Claude Code's encoded project-folder names, e.g. "-Users-<name>-ledger-rooms-...")

No label value, classification or count changes. The originals are copied first to data/cache/ledger_labels_unredacted/
(git-ignored), and research/ledger/labels/REDACTION.json records, per file, the SHA-256 before and after.

    uv run --project ledger --no-sync python ledger/scripts/redact_home_paths.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LAB = REPO / "research" / "ledger" / "labels"
KEEP = REPO / "data" / "cache" / "ledger_labels_unredacted"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> None:
    home = str(Path.home())
    enc = "-" + home.strip("/").replace("/", "-").replace("_", "-") + "-"
    subs = [(home + "/", "$HOME/"), (enc, "-HOME-")]
    out = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "substitutions": ["<home>/ -> $HOME/", "-<encoded home>- -> -HOME-"], "files": {}}
    for p in sorted(LAB.rglob("*")):
        if not p.is_file() or p.name == "REDACTION.json":
            continue
        raw = p.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        new = text
        for a, b in subs:
            new = new.replace(a, b)
        if new == text:
            continue
        rel = p.relative_to(LAB)
        (KEEP / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, KEEP / rel)
        p.write_text(new, encoding="utf-8", newline="")
        out["files"][rel.as_posix()] = {"sha256_original": sha(raw), "sha256_redacted": sha(new.encode("utf-8"))}
    (LAB / "REDACTION.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"redacted {len(out['files'])} files; originals kept in data/cache/ledger_labels_unredacted/")


if __name__ == "__main__":
    main()
