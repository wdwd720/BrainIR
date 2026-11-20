"""Per-control check of the ten B1 control campaigns (the round-2 arms reviewer's check, LOG L34; committed in run 2, L49,
because L48 found it missing from git). Read-only: it writes only into a temporary folder that it deletes.

    uv run --project ledger --no-sync python ledger/scripts/controls_check.py

PASS per control requires all of: log read to EOF; 5,136 records = 5,136 unique keys = the expected key set; 0 error records;
every logged run's shared-payload key = the key of that control's own matrix; replicates.parquet one row per key with the
log's digest; types.csv and replicates.parquet byte-identical to a fresh re-aggregation; results_log_sha256 matches; 321
types, no NaN primary; G4 json present with pass=true and its re-runs' digests equal the originals in the logs."""

import collections
import hashlib
import json
import pickle
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ledger" / "src"))
from brainir.compute.backend import pack_shared  # noqa: E402
from brainir_ledger import arms as AR  # noqa: E402
from brainir_ledger import controls as CT  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402
from brainir_ledger.tables import write_csv, write_parquet  # noqa: E402

D = REPO / "data" / "ledger" / "arms"
P = REPO / "research" / "ledger" / "predictions"
G = REPO / "research" / "ledger" / "gates"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


fl = N.front_leg()
groups = N.type_groups(fl.table)
tmp = Path(tempfile.mkdtemp(prefix="ledger_controls_check_"))
summary = {}
for name in CT.control_names():
    if not (P / name / "types.csv").exists():
        summary[name] = "not finished (no types.csv)"
        continue
    probs = []
    log = D / name / "results.pkl"
    recs, size = [], log.stat().st_size
    with open(log, "rb") as fh:
        while True:
            try:
                recs.append(pickle.load(fh))
            except EOFError:
                break
            except Exception as e:  # noqa: BLE001
                probs.append(f"log unreadable at byte {fh.tell()}: {e}")
                break
        if fh.tell() != size:
            probs.append("log not read to EOF")
    exp = {f"{name}|{t}|s{s}" for t in groups for s in AR.SEEDS}
    keys = collections.Counter(r["key"] for r in recs)
    last = {r["key"]: r for r in recs}
    if len(recs) != 5136 or len(keys) != 5136 or set(keys) != exp:
        probs.append(f"records {len(recs)}, unique {len(keys)}, missing {len(exp - set(keys))}, extra {len(set(keys) - exp)}")
    if any("error" in r for r in last.values()):
        probs.append("error records")
    Wc, _ = CT.build(fl, name)
    want = pack_shared({"W": Wc, "sizes": fl.sizes, "readout": fl.readout})[1]
    bs = D / name / "backend_stats.jsonl"
    logged = [json.loads(x)["stats"]["settings"]["shared_payload_key"] for x in bs.read_text().splitlines()] if bs.exists() else []
    if not logged or any(k != want for k in logged):
        probs.append(f"payload keys {logged} != expected {want}")
    rep = pd.read_parquet(P / name / "replicates.parquet")
    rk = [f"{name}|{t}|s{int(s)}" for t, s in zip(rep["manc_type"], rep["seed"])]
    if len(set(rk)) != 5136 or set(rk) != exp or any(last[k]["digest"] != d for k, d in zip(rk, rep["digest"])):
        probs.append("replicates.parquet is not one row per key with the log's digest")
    t, r = AR.aggregate_group_arm(name, f"{fl.name}+{name}", fl, groups, last, AR.b1_screen_cfg(10))
    if write_csv(t, tmp / name / "types.csv") != sha(P / name / "types.csv") or write_parquet(r, tmp / name / "r.parquet") != sha(P / name / "replicates.parquet"):
        probs.append("tables not byte-identical to a fresh re-aggregation")
    prov = json.loads((P / name / "provenance.json").read_text())
    if prov.get("results_log_sha256") != sha(log):
        probs.append("results_log_sha256 mismatch")
    tt = pd.read_csv(P / name / "types.csv")
    if len(tt) != 321 or tt["manc_type"].nunique() != 321 or tt["primary_score"].isna().any():
        probs.append("types.csv shape/NaN")
    g4 = G / f"G4_{name}.json"
    if not g4.exists():
        probs.append("G4 json missing")
    else:
        gj = json.loads(g4.read_text())
        rr = {x["key"]: x for x in read_log(D / f"G4_{name}" / "results.pkl")}
        same = sum(x["digest"] == last[k]["digest"] for k, x in rr.items() if "error" not in x)
        if not gj.get("pass") or gj.get("n") != 100 or same != 100:
            probs.append(f"G4: json pass {gj.get('pass')}, n {gj.get('n')}, identical in logs {same}")
    seg = collections.Counter(r["host"]["env"]["OPENBLAS_NUM_THREADS"] for r in last.values())
    summary[name] = {"PASS": not probs, "problems": probs, "results_by_thread_env": dict(seg),
                     "drivers": int((tt["band"] == "driver").sum()), "never_usable": int((tt["status"] != "ok").sum())}
shutil.rmtree(tmp)
for k, v in summary.items():
    print(k, v)
