"""Method-snapshot provenance of every post-lock run (post-lock review L, m4). ORCHESTRATOR SIDE; reporting only.

The post-lock records (Level C, ablations, counterexample sweeps, review G, the FINAL parts) do not all record which method snapshot
they ran. This script records, for the locked directory and for each confirmation part's snapshot:
- the Modal methods key (the same deterministic tar hash that modal_tournament._methods_key uploads; computed offline here);
- the raw and the LF-normalised sha256 of every file, compared with METHOD_LOCK.json (which stores LF-normalised hashes; the working
  tree has CRLF line endings in 19 of the 30 files, so raw and LF hashes differ while the code is identical).
The run-to-snapshot assignment comes from the commands in the orchestrator transcript, as verified by review L: Level C, the
ablations, the sweeps and review G used `phase3/src/brainir_state/methods`; the FINAL parts used their `final_b_<m>/methods` copies.

    uv run --project phase3 --no-sync python scripts/p3/postlock_provenance.py  ->  research/phase3/POSTLOCK_PROVENANCE.json
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P3 = ROOT / "research" / "phase3"
RUN = Path(r"C:\Dev\BrainIR_p3run")
LOCKED = ROOT / "phase3" / "src" / "brainir_state" / "methods"


def methods_key(mdir: Path) -> str:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for p in sorted(q for q in mdir.rglob("*") if q.is_file() and "__pycache__" not in q.parts and q.suffix != ".pyc"):
            data = p.read_bytes()
            ti = tarfile.TarInfo("methods/" + p.relative_to(mdir).as_posix())
            ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
            tf.addfile(ti, io.BytesIO(data))
    return hashlib.sha256(buf.getvalue()).hexdigest()[:16]


def file_hashes(mdir: Path) -> dict:
    out = {}
    for p in sorted(q for q in mdir.rglob("*.py") if "__pycache__" not in q.parts):
        b = p.read_bytes()
        out[p.relative_to(mdir).as_posix()] = {"raw": hashlib.sha256(b).hexdigest(),
                                               "lf": hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()}
    return out


def main() -> int:
    lock = json.loads((P3 / "METHOD_LOCK.json").read_text(encoding="utf-8"))
    src = lock.get("source_sha256") or lock.get("sources") or {}
    locked_lf = {k.split("methods/", 1)[-1]: v for k, v in src.items()}
    ref = file_hashes(LOCKED)
    lf_match = sum(1 for k, v in ref.items() if locked_lf.get(k) == v["lf"])
    tag_commit = subprocess.run(["git", "rev-list", "-n", "1", "brainir-state-v1-preblind"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rec = {"script": "scripts/p3/postlock_provenance.py", "method_lock_tag": "brainir-state-v1-preblind", "tag_commit": tag_commit,
           "locked_dir": {"path": "phase3/src/brainir_state/methods", "methods_key": methods_key(LOCKED), "n_py_files": len(ref),
                          "lf_hashes_matching_METHOD_LOCK": lf_match, "n_files_with_crlf": sum(1 for v in ref.values() if v["raw"] != v["lf"])},
           "snapshots": {}, "runs": {
               "Level C (level_c/01)": "phase3/src/brainir_state/methods (--method-dir)",
               "ablations_final, ablations_dev": "phase3/src/brainir_state/methods",
               "counterexample sweeps (7)": "phase3/src/brainir_state/methods, with the final_b_* or level_c_01 fits",
               "review G on the locked method": "phase3/src/brainir_state/methods",
               "FINAL confirmation parts (13)": "$ROOMS/BrainIR_p3run/final_b_<m>/methods (copies of the locked tree)",
               "family H extraction (final_b_H)": "$ROOMS/BrainIR_p3run/final_b_<m>/methods"},
           "source_of_assignment": "orchestrator transcript commands, verified by post-lock review L (POSTLOCK_L.md m4, item 4)"}
    for d in sorted(RUN.glob("final_b_*/methods")):
        h = file_hashes(d)
        rec["snapshots"][d.parent.name] = {"methods_key": methods_key(d), "raw_identical_to_locked": all(h.get(k, {}).get("raw") == v["raw"] for k, v in ref.items())
                                           and len(h) == len(ref)}
    (P3 / "POSTLOCK_PROVENANCE.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"locked": rec["locked_dir"], "snapshots_identical": all(v["raw_identical_to_locked"] for v in rec["snapshots"].values()),
                      "keys": sorted({v["methods_key"] for v in rec["snapshots"].values()}), "n_snapshots": len(rec["snapshots"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
