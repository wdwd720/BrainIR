"""Run registry scan (PREREG v3 Part D item 3, P9.5): every results.pkl under the data directory and every GitHub campaign manifest,
searched for keys of hemilineage jobs or run 3 arms. The code that produced gates_v3/REGISTRY_BEFORE_FREEZE.json (run inline before
the freeze; kept here so the counts can be reproduced). Writes gates_v3/REGISTRY_<suffix>.json once.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/registry_scan.py SUFFIX [--before ISO_TIME]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402


def main() -> None:
    suffix = sys.argv[1]
    units = [l.split(",")[0] for l in (RESEARCH / "hl_units" / "UNITS_v1.csv").read_text().splitlines()[1:]]
    pat = re.compile(r"^(H-|hm|hd|hc|hsens|R3|R4)|\|(" + "|".join(re.escape(u) for u in units) + r")\|")
    n_files = n_keys = 0
    hits: list[str] = []
    for p in sorted(data_dir().rglob("results.pkl")):
        try:
            ks = [r.get("key", "") for r in read_log(p)]
        except Exception as e:  # noqa: BLE001
            hits.append(f"{p.relative_to(data_dir())}: unreadable {e}")
            continue
        n_files += 1
        n_keys += len(ks)
        hits += [f"{p.relative_to(data_dir())}: {k}" for k in ks if isinstance(k, str) and pat.search(k)]
    mans = sorted((data_dir() / "gha").glob("*/manifest.json"))
    mk = 0
    camp = {}
    for m in mans:
        man = json.loads(m.read_text())
        mk += len(man["keys"])
        n_hit = sum(1 for k in man["keys"] if pat.search(k))
        hits += [f"{m.parent.name}: {k}" for k in man["keys"] if pat.search(k)][:3]
        camp[m.parent.name] = {"utc": man.get("utc"), "git_head": man.get("git_head"), "n_keys": len(man["keys"]), "n_run3_arm_keys": n_hit}
    out = {"results_files": n_files, "result_keys": n_keys, "gha_manifests": len(mans), "manifest_keys": mk,
           "hemilineage_or_run3_arm_keys": len(hits), "examples": hits[:5], "campaigns": camp}
    with open(RESEARCH / "gates_v3" / f"REGISTRY_{suffix}.json", "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "campaigns"}))


if __name__ == "__main__":
    main()
