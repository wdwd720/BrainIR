"""Clean-room runner: execute a discovery method against ONE public bundle and produce prediction.json files.

    uv run python benchmarks/dng100/cleanroom/run_method.py --method path/to/method.py --bundle benchmarks/dng100/public_blind \
        --out runs/<name> [--network manc_v1.2.1 ...] [--seed 0] [--method-args "..."]

Contract for a method file: a Python script that reads the environment variables
    BRAINIR_BUNDLE      path of the bundle copy (read-only for the method)
    BRAINIR_NETWORK     network name inside the bundle
    BRAINIR_OUT         path where it must write prediction.json (schema brainir.benchmark.prediction 1.0.0)
    BRAINIR_SEED        integer seed
and imports only the standard library, numpy/scipy/pandas/networkx and `brainir` (never `benchmarks`).

The runner: copies the bundle to a fresh directory (so the method cannot see the rest of the repository through relative
paths), strips the environment of everything but PATH/system variables, runs the method with cwd = the copy, verifies
the produced predictions parse, records SHA-256 of the bundle, the method file and each prediction, and writes
run_record.json. It never touches the oracle; evaluation is a separate step.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from brainir.benchmark.bundle import verify_bundle
from brainir.benchmark.prediction import BrainIRMechanismPrediction

SAFE_ENV_KEYS = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT", "PROGRAMDATA", "LOCALAPPDATA",
                 "APPDATA", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "HOME", "LANG", "LC_ALL", "PYTHONIOENCODING", "VIRTUAL_ENV",
                 "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE")
FORBIDDEN_IMPORT = re.compile(r"^\s*(from|import)\s+(benchmarks|oracle|evaluate)\b", re.M)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(method: Path, bundle: Path, out: Path, networks: list[str], seed: int, method_args: str = "", timeout_s: int = 7200) -> dict:
    method = method.resolve()
    src = method.read_text(encoding="utf-8")
    if FORBIDDEN_IMPORT.search(src):
        raise SystemExit(f"{method}: forbidden import of benchmarks/oracle/evaluator code")
    v = verify_bundle(bundle)
    if not v["ok"]:
        raise SystemExit(f"bundle does not verify: {v}")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    out = out.resolve()  # the method runs with a different cwd: hand it absolute paths
    out.mkdir(parents=True, exist_ok=True)
    env = {k: v_ for k, v_ in os.environ.items() if k.upper() in SAFE_ENV_KEYS}
    env["PYTHONIOENCODING"] = "utf-8"
    records = []
    with tempfile.TemporaryDirectory(prefix="brainir_cleanroom_") as tmp:
        copy = Path(tmp) / "bundle"
        shutil.copytree(bundle, copy)
        for net in networks:
            pred_path = out / f"prediction_{net}.json"
            e = {**env, "BRAINIR_BUNDLE": str(copy), "BRAINIR_NETWORK": net, "BRAINIR_OUT": str(pred_path), "BRAINIR_SEED": str(seed)}
            t0 = time.time()
            proc = subprocess.run([sys.executable, str(method), *method_args.split()], cwd=copy, env=e, capture_output=True, text=True,
                                  timeout=timeout_s)
            rec = {"network": net, "returncode": proc.returncode, "wall_time_s": round(time.time() - t0, 1),
                   "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-2000:]}
            if proc.returncode == 0 and pred_path.exists():
                pr = BrainIRMechanismPrediction.from_json(pred_path.read_text(encoding="utf-8"))  # validates the schema
                rec.update(prediction=pred_path.name, prediction_sha256=pr.digest(), n_core=len(pr.core_neurons),
                           method_name=pr.method.name)
            records.append(rec)
    record = {"created_utc": _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
              "method_file": method.name, "method_sha256": _sha(method), "bundle": {"root": str(bundle.name), "tier": manifest["tier"],
              "bundle_sha256": manifest["bundle_sha256"], "benchmark_id": manifest["benchmark_id"]},
              "seed": seed, "runs": records}
    (out / "run_record.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8", newline="\n")
    return record


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", type=Path, required=True)
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--network", action="append", default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--method-args", default="")
    ap.add_argument("--timeout", type=int, default=7200)
    args = ap.parse_args(argv)
    manifest = json.loads((args.bundle / "manifest.json").read_text(encoding="utf-8"))
    nets = args.network or [n["name"] for n in manifest["networks"]]
    rec = run(args.method, args.bundle, args.out, nets, args.seed, args.method_args, args.timeout)
    for r in rec["runs"]:
        print(r["network"], "rc", r["returncode"], r.get("prediction_sha256", "")[:12], r.get("n_core"), f"{r['wall_time_s']}s")


if __name__ == "__main__":
    main()
