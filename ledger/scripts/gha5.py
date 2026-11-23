"""Run 5 campaigns on GitHub Actions (RUN5_PROMPT hard limit 7; PREREG v5 Part X): registers run 5's builders with the frozen `gha.py`
(pack) and runs them through run 4's runner and workflow unchanged (`gha_runner4.py`, `.github/workflows/ledger-gha4.yml`, tags
`gha4-run-<name>`), published with `publish5` and collected with run 4's `collect4`. No frozen file is edited: run 4's helpers are
used as they are, with module attribute swaps at run time where a name check would refuse a run 5 campaign.

- The trust gate (Stage 0) is run 1's 100 locked jobs packed and published with the frozen `gha.py` (run 2's workflow); `trust-compare`
  writes `gates_v5/TRUST_GATE_v5.json`.
- Hard limit 1 (declare first): every run 5 builder refuses before the tag `ledger-prereg-v5` exists and `LOCK_prereg_v5.json` verifies.
- Hard limit 7: at most 20 GitHub jobs queued or running (the campaign's chunks + its plan job count); `publish5` refuses otherwise.

    uv run --project ledger --no-sync python ledger/scripts/gha5.py trust-compare trust-run5     # -> gates_v5/TRUST_GATE_v5.json
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gha as G  # noqa: E402
import gha4 as G4  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

GATES5 = RESEARCH / "gates_v5"
MAX_JOBS = 20


def _write_once(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as fh:  # written once; never overwritten
        fh.write(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")


def trust_compare(name: str) -> dict:
    """Run 2's trust comparison for a campaign of another name (as `gha4.trust_compare`, written to gates_v5): every re-run job's
    digest against the locked run 1 result it reproduces."""
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    new = {r["key"]: r for r in read_log(data_dir() / man["area"] / f"GHA_{name}" / "results.pkl")}
    items = []
    for f in sorted((G.GHA / name).glob("chunk_*.pkl")):
        items += pickle.loads(f.read_bytes())
    origin = {j["key"]: j["origin"] for _, j in items}
    orig = {o: {r["key"]: r for r in read_log(data_dir() / o / "results.pkl")} for o in sorted(set(origin.values()))}
    ident, bad = 0, []
    for k in man["keys"]:
        a, b = orig[origin[k]].get(k), new.get(k)
        if b is None:
            bad.append((k, "missing on runner"))
        elif a["digest"] == b["digest"]:
            ident += 1
        else:
            bad.append((k, "digest differs"))
    meta = [json.loads(x) for x in (data_dir() / man["area"] / f"GHA_{name}" / "gha_meta.jsonl").read_text().splitlines() if x.strip()]
    out = {"campaign": name, "n": len(man["keys"]), "identical": ident, "different": len(bad), "different_keys": bad,
           "by_origin": {o: sum(1 for k in man["keys"] if origin[k] == o) for o in sorted(set(origin.values()))},
           "numerics_digests": sorted({m["probe"]["numerics_digest"][:12] for m in meta}),
           "cpu_models": sorted({m["probe"]["host"]["cpu"]["cpu_model"] for m in meta}),
           "git_head_packed": man.get("git_head"), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "verdict": "identical" if ident == len(man["keys"]) else "fail"}
    _write_once(GATES5 / ("TRUST_GATE_v5.json" if name == "trust-run5" else f"TRUST_GATE_v5_{name}.json"), out)
    print(json.dumps({k: v for k, v in out.items() if k != "different_keys"}, indent=1))
    return out


def main() -> None:
    cmd, a = sys.argv[1:2], sys.argv[2:]
    if cmd == ["trust-compare"]:
        trust_compare(a[0])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
