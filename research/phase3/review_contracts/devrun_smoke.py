"""Orchestrator smoke test of the remote runner (placed in the room as runs/zzorch/smoke.py): checks the isolation from inside a job."""
import json
import os
import socket
from pathlib import Path

out = {"cwd": os.getcwd(), "data_manifest": Path("data/synthetic_dev/manifest.json").exists(),
       "evalvol_visible": Path("/evalvol").exists(), "fitvol_visible": Path("/fitvol").exists(), "repo_visible": Path("/repo").exists(),
       "cpus": os.environ.get("P3_REMOTE_CPUS")}
try:
    socket.create_connection(("1.1.1.1", 443), timeout=5)
    out["network"] = "OPEN"
except Exception as e:  # noqa: BLE001
    out["network"] = "blocked (" + type(e).__name__ + ")"
from brainir_state.data import Dataset  # noqa: E402

out["n_dev_rows"] = len(Dataset("data/synthetic_dev").index)
out["n_real_rows"] = len(Dataset("data/real_public").index)
Path("runs/zzorch/out").mkdir(parents=True, exist_ok=True)
Path("runs/zzorch/out/smoke.json").write_text(json.dumps(out), encoding="utf-8")
print(json.dumps(out))
