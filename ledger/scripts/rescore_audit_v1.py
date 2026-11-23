"""PREREG v5 L7 (EXPLORATORY, reported once): exam 1's primary statistic recomputed with the audit's labels substituted for audited
primary-set types, by the frozen scoring code. Not label-side code (it reads the prediction lock), so it lives apart from
`labels_audit_v1.py`. Exam 1 stays closed; its locked result is unchanged.

    uv run --project ledger --no-sync python ledger/scripts/rescore_audit_v1.py     # -> labels_audit_v1/RESCORE_exploratory.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit5_rooms as AR  # noqa: E402

from brainir_ledger import RESEARCH  # noqa: E402

OUT = RESEARCH / "labels_audit_v1"


def rescore() -> None:
    """L7 (exploratory, once): exam 1's primary statistic with audited labels substituted for audited primary-set types whose audited
    label at exam 1's preparation scope is yes or no; every other type keeps exam 1's label. Frozen scoring code (`scoring.pipeline.primary`)."""
    from brainir_ledger.scoring import pipeline as P  # noqa: PLC0415

    import forward_v1 as F1  # noqa: PLC0415

    if (OUT / "RESCORE_exploratory.json").exists():
        raise SystemExit("RESCORE_exploratory.json exists; reported once")
    cmp_ = pd.read_csv(OUT / "comparison_with_exam1.csv", dtype={"manc_type": str})
    tl = pd.read_csv(RESEARCH / "labels_v2" / "type_labels.csv", dtype={"manc_type": str})
    primary = set(F1.primary_set().index)
    sub = cmp_[cmp_["manc_type"].isin(primary) & cmp_["audited"].isin(["yes", "no"])].set_index("manc_type")["audited"]
    tl2 = tl.copy()
    changed = []
    for t, v in sub.items():
        old = tl2.loc[tl2["manc_type"] == t, "front"].iloc[0]
        if old != v:
            changed.append([t, old, v])
        tl2.loc[tl2["manc_type"] == t, "front"] = v
    lock = json.loads((RESEARCH / "LOCK_predictions_v1.json").read_text(encoding="utf-8"))
    locked = sorted(lock["arms_locked"])   # as the frozen scoring's verify_inputs (the arms of LOCK_predictions_v1.json)
    res = {"label": "EXPLORATORY (PREREG v5 L7; exam 1 stays closed; reported once)", "substituted_types": sorted(sub.index),
           "changed": changed, "locked_arms_used": locked}
    res["exam1_locked"] = P._clean(P.primary(P.PREDICTIONS, tl, locked, n_boot=10_000, n_perm=10_000))
    res["audited"] = P._clean(P.primary(P.PREDICTIONS, tl2, locked, n_boot=10_000, n_perm=10_000))
    AR._write_once(OUT / "RESCORE_exploratory.json", json.dumps(res, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: res[k] for k in ("substituted_types", "changed")}, indent=1),
          "\nlocked AUROC", res["exam1_locked"].get("auroc"), "audited AUROC", res["audited"].get("auroc"))


if __name__ == "__main__":
    rescore()
