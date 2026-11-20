"""Labels v1.1: a NEW VERSION of the locked labels v1 (prompt section 11: "a bug after a lock -> a new version with a changelog;
never edit the locked one"). LOG L47; label review round 1, finding 2. Labels v1 existed (and were locked) when this was made;
no prediction is read.

Fixes, and nothing else:
  1. the frozen `labels_collect.norm_doi` strips the article number from unversioned eLife DOIs (it meant to strip only a
     version suffix), so every eLife paper became one unit in the completeness statistic, in `sources.csv` and in the
     search-only matching;
  2. the breaching search session (transcript audit, PREREG 6) is excluded like every other breaching session; the frozen code
     dropped only breaching pass-1/2/adjudication sessions.
Search records never enter the consensus, so `records.jsonl` and `type_labels.csv` (the scoring inputs) must come out
byte-identical to v1; `build` checks that and refuses otherwise.

Mechanics: the frozen `labels_collect.finalize` is run unchanged, with (a) its output folder pointed at
research/ledger/labels_v1_1/ (its raw inputs stay those of v1), (b) `norm_doi` replaced by the fixed function, (c) the
breaching search session filtered from its search records. The frozen files themselves are not modified.

    uv run --project ledger --no-sync python ledger/scripts/labels_v1_1.py build    # -> research/ledger/labels_v1_1/
    uv run --project ledger --no-sync python ledger/scripts/labels_v1_1.py lock     # -> research/ledger/LOCK_labels_v1_1.json
    uv run --project ledger --no-sync python ledger/scripts/lock.py check research/ledger/LOCK_labels_v1_1.json
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labels_collect as LC  # noqa: E402  (frozen module; run unchanged, two names rebound)
import lock as LK  # noqa: E402  (frozen module; helpers only)

REPO = HERE.parents[1]
RES = REPO / "research" / "ledger"
V1 = RES / "labels"
V11 = RES / "labels_v1_1"
LOCK = RES / "LOCK_labels_v1_1.json"
MUST_MATCH_V1 = ("records.jsonl", "type_labels.csv", "spot_check_sample.csv", "merge_log.json", "synonyms.csv", "driver_lines.csv")

CHANGELOG = """# Labels v1.1 changelog

| version | date | change | labels existing at the time | scoring inputs |
|---|---|---|---|---|
| 1 | 2026-11-20 | initial (`LOCK_labels_v1.json`, tag `ledger-labels-v1`) | - | - |
| 1.1 | 2026-11-20 | (1) eLife DOIs normalised correctly (version suffix stripped, article number kept); (2) the breaching search session excluded from the search-only records and the completeness statistic, like every breaching session (PREREG 6). Source: independent label review round 1, finding 2 (`final/REVIEW_labels_round1.md`). | yes: labels v1 were locked; the orchestrator had seen only aggregate label counts; no label was ever joined to a prediction | `records.jsonl` and `type_labels.csv` byte-identical to v1 |

Changed files relative to v1: `agreement.md`, `agreement.json` (capture-recapture), `sources.csv` (eLife sources no longer merged),
`search_only_records.jsonl`. Built by `ledger/scripts/labels_v1_1.py` from the v1 raw inputs.
"""


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def norm_doi_fixed(d: str) -> str:
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    return re.sub(r"^(10\.7554/elife\.\d+)\.\d+$", r"\1", d)


def build() -> None:
    if V11.exists():
        raise SystemExit(f"{V11} exists; a version is written once")
    V11.mkdir(parents=True)
    (V11 / ".gitattributes").write_text("# stored byte for byte (hashes in LOCK_labels_v1_1.json)\n* -text\n", encoding="utf-8")
    shutil.copy2(V1 / "transcript_audit.json", V11 / "transcript_audit.json")  # the (redacted) v1 audit, unchanged
    LC.LAB = V11                       # outputs and the audit lookup; LC.RAW stays at v1's raw inputs
    LC.norm_doi = norm_doi_fixed       # fix 1
    breach = LC.breaching_sessions()
    orig_read = LC._read
    LC._read = lambda pid: [r for r in orig_read(pid)
                            if not (pid == "search" and r["exp_id"].split(":", 1)[0] in breach)]  # fix 2
    LC.finalize()
    (V11 / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8", newline="\n")
    diff = {n: sha(V1 / n) == sha(V11 / n) for n in MUST_MATCH_V1}
    print("identical to v1:", diff)
    if not all(diff.values()):
        raise SystemExit("REFUSED: a file that must not change differs from v1")


def lock() -> None:
    rec = LK.base_record("labels_v1_1")
    if rec["git_dirty_ledger_paths"]:
        raise SystemExit(f"commit first: {rec['git_dirty_ledger_paths']}")
    rec["version"] = "1.1"
    rec["labels"] = LK.hashes(V11.glob("*"))  # top-level files; the frozen scoring reads them by name from the folder it is given
    rec["raw"] = LK.hashes(list(V1.glob("raw/*/*/*")) + list(V1.glob("raw/*/*/*/*")))  # the v1 raw inputs it was built from
    rec["kit"] = LK.hashes((RES / "kit").glob("*"))
    rec["labels_v1_lock_sha256"] = sha(RES / "LOCK_labels_v1.json")
    rec["prereg_lock_sha256"] = sha(RES / "LOCK_prereg_v1.json")
    LOCK.write_text(json.dumps(rec, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    print(LOCK, sha(LOCK))


if __name__ == "__main__":
    {"build": build, "lock": lock}[sys.argv[1]]()
