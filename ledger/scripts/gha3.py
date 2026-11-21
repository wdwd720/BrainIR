"""Run 3 campaigns on GitHub Actions (RUN3_PROMPT section 3 item 5): a new file that registers run 3's builders with the frozen
`gha.py` (P4b, LOCK_prereg_v2) and hands over to its command line, as `gha_det.py` does. Before `ledger-prereg-v3` is tagged,
only the trust gate (run 1's locked jobs) and DNg100 / DNb08 / random synthetic groups may be built (hard limit 2).

    uv run --project ledger --no-sync python ledger/scripts/gha3.py pack trust-run3 --chunk-jobs 20
    uv run --project ledger --no-sync python ledger/scripts/gha.py publish trust-run3
    uv run --project ledger --no-sync python ledger/scripts/gha.py collect trust-run3 --wait
    uv run --project ledger --no-sync python ledger/scripts/gha3.py trust-compare trust-run3   # -> research/ledger/gates_v3/TRUST_GATE_v3.json
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gha as G  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

GATES3 = RESEARCH / "gates_v3"


def trust_compare(name: str) -> dict:
    """The run-2 trust comparison (`gha.trust_compare`) for a campaign of another name: every re-run job's digest against the
    locked run-1 result it reproduces."""
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
           "verdict": "identical" if ident == len(man["keys"]) else "fail"}
    GATES3.mkdir(parents=True, exist_ok=True)
    (GATES3 / "TRUST_GATE_v3.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in out.items() if k != "different_keys"}, indent=1))
    return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["trust-compare"]:
        trust_compare(sys.argv[2])
    else:
        G.main()
