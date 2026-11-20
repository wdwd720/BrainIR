"""Write research/ledger/gates/ENVIRONMENT.json: the platform, Python, library versions, numerics environment and host mix
of every simulated campaign, read from the job results themselves (each result carries its host fingerprint).

    uv run --project ledger --no-sync python ledger/scripts/environment_report.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger.backend import LedgerModalBackend, read_log  # noqa: E402
from brainir_ledger.env import fingerprint  # noqa: E402


def main() -> None:
    out = {"local_orchestrator": fingerprint(), "modal_image_spec": LedgerModalBackend().image_spec(), "campaigns": {}}
    for d in sorted((data_dir() / "arms").glob("*")):
        log = d / "results.pkl"
        if not log.exists() or d.name.startswith(("DRYRUN", "BATCHTEST", "PILOT")):
            continue
        res = [r for r in read_log(log) if isinstance(r, dict) and "host" in r]
        if not res:
            continue
        hosts = [r["host"] for r in res]
        keyset = Counter(json.dumps({k: h.get(k) for k in ("python", "platform", "numpy", "scipy", "pandas", "pyarrow")}, sort_keys=True)
                         for h in hosts)
        envs = Counter(json.dumps(h.get("env"), sort_keys=True) for h in hosts)
        feats = Counter(",".join(sorted(h.get("numpy_cpu_features_enabled") or {})) for h in hosts)
        stats = []
        sp = d / "backend_stats.jsonl"
        if sp.exists():
            for line in sp.read_text(encoding="utf-8").splitlines():
                s = json.loads(line).get("stats") or {}
                stats.append({"cpu": (s.get("settings") or {}).get("cpu"), "memory_mb": (s.get("settings") or {}).get("memory_mb"),
                              "batch_size": (s.get("settings") or {}).get("batch_size", 1), "n_items": s.get("n_items")})
        out["campaigns"][d.name] = {
            "n_results": len(res), "n_errors": sum("error" in r for r in res),
            "software": {json.loads(k)["python"] + " | " + json.loads(k)["platform"]: v for k, v in keyset.items()},
            "library_versions": sorted({k for k in keyset}),
            "numerics_env": {k: v for k, v in envs.items()},
            "avx512_hosts": sum(bool((h.get("cpu") or {}).get("avx512f")) for h in hosts),
            "numpy_dispatched_features": {k: v for k, v in feats.most_common()},
            "container_settings": stats,
        }
    p = RESEARCH / "gates" / "ENVIRONMENT.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    for k, v in out["campaigns"].items():
        print(k, v["n_results"], "errors", v["n_errors"], "avx512", v["avx512_hosts"], list(v["software"])[:1])


if __name__ == "__main__":
    main()
