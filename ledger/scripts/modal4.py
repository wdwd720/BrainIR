"""Run 4 campaigns on Modal (user's chat authorisation, 2026-11-21 ~17:50 PST: Modal allowed for speed, about $15 of compute; a
departure from RUN4_PROMPT hard limit 7, LOG L110). Same trust gate as GitHub: run 2's 100 locked jobs must reproduce their digests
here (gates_v4/TRUST_GATE_v4_modal.json) before any run 4 campaign runs on Modal.

Uses run 1's pinned Modal backend (`brainir_ledger.backend.LedgerModalBackend`: pinned libraries, numerics environment, shared
payload in a volume) unchanged, with run 4's job entry point (`jobs_v4.run_job`, which passes run 1-3 kinds to their own entry
points), one job per container call (cpu 1). A campaign packed for GitHub (`gha4.py pack`) is run from its packed chunks and payloads
into its own append-only log `data/ledger/<area>/MODAL_<name>/results.pkl` (resumable: keys already there are skipped).

    uv run --project ledger --no-sync python ledger/scripts/modal4.py trust            # -> gates_v4/TRUST_GATE_v4_modal.json
    uv run --project ledger --no-sync python ledger/scripts/modal4.py run pa-manc-run4 [--max-containers 100] [--budget-usd 6]
    uv run --project ledger --no-sync python ledger/scripts/modal4.py estimate pa-manc-run4 --s-per-job 21
"""

from __future__ import annotations

import json
import pickle
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))
import gha as G  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger.backend import LedgerModalBackend, read_log  # noqa: E402
from brainir_ledger.jobs_v4 import run_job  # noqa: E402

GATES4 = RESEARCH / "gates_v4"
SPEND_LOG = data_dir() / "modal_run4_spend.jsonl"
CAP_USD = 15.0
PRICE_CORE_H = 0.0473
PRICE_GIB_H = 0.008
MEM_GIB = 2.0


def _items(name: str) -> tuple[dict, list[tuple[str, dict]], dict]:
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    items = []
    for f in sorted((G.GHA / name).glob("chunk_*.pkl")):
        items += pickle.loads(f.read_bytes())
    payloads = {k: pickle.loads(zlib.decompress((G.GHA / name / f"payload_{k}.bin").read_bytes())) for k in man["payload_keys"]}
    return man, items, payloads


def spent() -> float:
    if not SPEND_LOG.exists():
        return 0.0
    return float(sum(json.loads(x)["est_usd"] for x in SPEND_LOG.read_text().splitlines() if x.strip()))


def estimate(name: str, s_per_job: float) -> float:
    man, _, _ = _items(name)
    usd = man["n_jobs"] * s_per_job / 3600 * (PRICE_CORE_H + MEM_GIB * PRICE_GIB_H)
    print(json.dumps({"campaign": name, "n_jobs": man["n_jobs"], "s_per_job": s_per_job, "est_usd": round(usd, 2), "spent_so_far": round(spent(), 2)}))
    return usd


def run(name: str, max_containers: int = 100, budget_usd: float | None = None) -> None:
    man, items, payloads = _items(name)
    dest = data_dir() / man["area"] / f"MODAL_{name}"
    dest.mkdir(parents=True, exist_ok=True)
    log = dest / "results.pkl"
    have = {r["key"] for r in read_log(log)} if log.exists() else set()
    t0, n_new, cpu_s = time.time(), 0, 0.0
    for pkey in man["payload_keys"]:
        todo = [j for k, j in items if k == pkey and j["key"] not in have]
        if not todo:
            continue
        be = LedgerModalBackend(cpu=1.0, memory_mb=int(MEM_GIB * 1024), max_containers=max_containers, timeout_s=3600, retries=1)

        def sink(r, _log=log):
            nonlocal n_new, cpu_s
            if isinstance(r, Exception) or not isinstance(r, dict) or "key" not in r:
                return
            with open(_log, "ab") as fh:
                pickle.dump(r, fh, protocol=pickle.HIGHEST_PROTOCOL)
            n_new += 1
            cpu_s += float(r.get("job_wall_s") or 0.0)
        be.map_stream(run_job, todo, shared=payloads[pkey], sink=sink)
    est = cpu_s / 3600 * (PRICE_CORE_H + MEM_GIB * PRICE_GIB_H)
    with open(SPEND_LOG, "a") as fh:
        fh.write(json.dumps({"campaign": name, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "new_results": n_new,
                             "job_cpu_s": round(cpu_s, 1), "est_usd": round(est, 4), "wall_s": round(time.time() - t0, 1)}) + "\n")
    got = {r["key"] for r in read_log(log)}
    print(json.dumps({"campaign": name, "new_results": n_new, "have": len(got), "expected": man["n_jobs"],
                      "missing": len(set(man["keys"]) - got), "est_usd_this_call": round(est, 3), "spent_total_est": round(spent(), 2)}))
    if budget_usd is not None and spent() > budget_usd:
        print("WARNING: estimated spend above the per-call budget")


def trust() -> dict:
    """Run 2's 100 locked trust jobs (the `trust-run4` campaign packed for GitHub) on Modal; every digest must equal the locked one."""
    name = "trust-run4"
    run(name, max_containers=50)
    man, items, _ = _items(name)
    new = {r["key"]: r for r in read_log(data_dir() / man["area"] / f"MODAL_{name}" / "results.pkl")}
    origin = {j["key"]: j["origin"] for _, j in items}
    orig = {o: {r["key"]: r for r in read_log(data_dir() / o / "results.pkl")} for o in sorted(set(origin.values()))}
    ident = sum(1 for k in man["keys"] if k in new and new[k]["digest"] == orig[origin[k]][k]["digest"])
    hosts = sorted({str((r.get("host") or {}).get("cpu", {}).get("cpu_model")) for r in new.values()})
    out = {"platform": "Modal (run 1's pinned image and numerics environment, run 4's entry point)", "n": len(man["keys"]),
           "identical": ident, "different": sorted(k for k in man["keys"] if k in new and new[k]["digest"] != orig[origin[k]][k]["digest"]),
           "missing": sorted(set(man["keys"]) - set(new)), "cpu_models": hosts,
           "verdict": "identical" if ident == len(man["keys"]) else "fail"}
    GATES4.mkdir(parents=True, exist_ok=True)
    with open(GATES4 / "TRUST_GATE_v4_modal.json", "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "different"}))
    return out


def main() -> None:
    cmd, a = sys.argv[1:2], sys.argv[2:]
    if cmd == ["trust"]:
        trust()
    elif cmd == ["run"]:
        run(a[0], int(a[a.index("--max-containers") + 1]) if "--max-containers" in a else 100,
            float(a[a.index("--budget-usd") + 1]) if "--budget-usd" in a else None)
    elif cmd == ["estimate"]:
        estimate(a[0], float(a[a.index("--s-per-job") + 1]))
    elif cmd == ["spent"]:
        print(round(spent(), 3))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
