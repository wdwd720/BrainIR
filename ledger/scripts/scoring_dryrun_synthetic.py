"""Status-only dry run of the FROZEN scoring functions on copies of every locked prediction table with SYNTHETIC random labels
(LOG L48; the round-2 arms reviewer's dry run, made reproducible from the repository). Real labels are never read; no
`UNBLIND.json` is created (the frozen `verify_inputs` / `primary` / `secondary` are called directly with a flag dict, in a
temporary folder that is deleted). Prints only the status of each analysis and counts, never a value.

    uv run --project ledger --no-sync python ledger/scripts/scoring_dryrun_synthetic.py [--out research/ledger/final/SCORING_DRYRUN.txt]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ledger" / "src"))
sys.path.insert(0, str(REPO / "ledger" / "tests"))
from brainir_ledger import networks as N  # noqa: E402
from brainir_ledger.labels.aggregate import type_labels  # noqa: E402
from brainir_ledger.scoring import pipeline as PL  # noqa: E402
from conftest import make_record  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run() -> None:
    root = Path(tempfile.mkdtemp(prefix="ledger_dryrun_"))
    try:
        research = root / "research"
        pred, lab = research / "predictions", research / "labels"
        lab.mkdir(parents=True)
        real = REPO / "research" / "ledger" / "predictions"
        locked = sorted(json.loads((REPO / "research" / "ledger" / "LOCK_predictions_v1.json").read_text())["arms_locked"])
        for a in locked:
            shutil.copytree(real / a, pred / a)
        shutil.copytree(REPO / "research" / "ledger" / "kit", research / "kit")
        fl = N.front_leg()
        all_groups, groups = N.type_groups(fl.table, excitatory_only=False), N.type_groups(fl.table)
        rng = np.random.default_rng(2)
        types = sorted(all_groups)
        pick = list(rng.choice(sorted(groups), 150, replace=False)) + [t for t in types if t not in groups][:40]
        recs = []
        for i, t in enumerate(pick):
            y = rng.random() < 0.3
            recs.append(make_record(record_id=f"r{i}", exp_id=f"pass1-atlas:r{i}", manc_type=t, quote_verified=True,
                                    front_leg_rhythm="yes" if y else "no",
                                    effect_on_walking=["stops", "none", "speeds", "slows", "turns"][i % 5],
                                    frequency_hz=8.0 + (i % 7) if y else None, preparation="headless" if i % 2 else "intact_free",
                                    headless_surface="ball" if i % 2 else None))
        with open(lab / "records.jsonl", "w") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")
        type_labels(recs, exposed=PL.kit_exposed(research), type_list=types).to_csv(lab / "type_labels.csv", index=False)
        plock = {"arms_locked": {a: {f"research/ledger/predictions/{a}/{f.name}": sha(f) for f in sorted((pred / a).glob("*"))
                                     if f.is_file() and not f.name.startswith(".")} for a in locked},
                 "arms_not_locked": {"B3": "G3 failed", "B6": "depends on B3"}}
        llock = {"labels": {f"research/ledger/labels/{n}": sha(lab / n) for n in ("records.jsonl", "type_labels.csv")}}
        (research / "LOCK_predictions_v1.json").write_text(json.dumps(plock))
        (research / "LOCK_labels_v1.json").write_text(json.dumps(llock))
        flag = {"predictions_lock": "LOCK_predictions_v1.json", "labels_lock": "LOCK_labels_v1.json"}
        ver = PL.verify_inputs(flag, research, pred, lab)
        print("synthetic labels only (random, seed 2); real labels never read")
        print("verify_inputs:", ver["verified_files"], "files;", len(ver["arms_locked"]), "arms")
        tl2 = PL.check_type_labels(lab, PL.kit_exposed(research))
        prim = PL.primary(pred, tl2, ver["arms_locked"], n_boot=200, n_perm=200)
        print("primary: status ok; baseline comparison", prim.get("baseline_comparison_status"), "; decision keys", sorted(prim.get("decision", {})))
        sec = PL.secondary(pred, lab, tl2, ver["arms_locked"], n_boot=100, n_perm=100)
        for k in PL.PREREGISTERED_SECONDARY:
            v = sec.get(k, {"status": "MISSING"})
            extra = v.get("error", "")[:200] if v["status"] == "error" else (v.get("reason", "") if v["status"] == "not_locked" else "")
            if k == "controls" and v["status"] == "ok":
                extra = f"controls evaluated: {len(v['result']['per_control'])}"
            print(f"  {k:28s} {v['status']:11s} {extra}")
        print("UNBLIND.json under the dry-run folder:", len(list(root.rglob("UNBLIND.json"))))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("dry-run folder removed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    buf = io.StringIO()
    with redirect_stdout(buf):
        run()
    text = buf.getvalue()
    print(text, end="")
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
