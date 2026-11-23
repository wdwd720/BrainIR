"""Referee test 3: exam 2, the simulation against each wiring baseline, with the 'best baseline' chosen inside each resample.

Input (locked): results/run3/primary.json (per-hemilineage percentile ranks of H-M and of the eight H-S baselines, 27 units).
Reports, over 10,000 paired bootstrap resamples of the 27 units (default_rng(1)): the model minus each baseline (mean and 95 %
interval, share of resamples with model > baseline), and the model minus the best of the eight re-chosen in every resample
(the draft compares with a baseline picked as best on the same labels; this shows how much that pick favours wiring).
Usage: uv run --project ledger --no-sync python research/ledger/reviews_v5/referee_tests/t3_exam2_baselines.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".out.json")


def main() -> None:
    d = json.loads((ROOT / "results/run3/primary.json").read_text())
    units = sorted(d["H-M"]["pr"])
    model = np.array([d["H-M"]["pr"][u] for u in units])
    names = sorted(d["H-S"])
    base = np.array([[d["H-S"][b]["pr"][u] for u in units] for b in names])
    rng = np.random.default_rng(1)
    n = len(units)
    idx = rng.integers(0, n, size=(10000, n))
    m = model[idx].mean(1)
    b = base[:, idx].mean(2)  # (8, 10000)
    out = {"n_units": n, "model_mean_pr": round(float(model.mean()), 4),
           "baselines_mean_pr": {nm: round(float(base[i].mean()), 4) for i, nm in enumerate(names)}, "paired": {}}
    for i, nm in enumerate(names):
        diff = m - b[i]
        out["paired"][nm] = {"diff": round(float(model.mean() - base[i].mean()), 4),
                             "ci95": [round(float(np.percentile(diff, 2.5)), 4), round(float(np.percentile(diff, 97.5)), 4)],
                             "share_model_above": round(float((diff > 0).mean()), 3)}
    best = b.max(0)
    which = np.array(names)[b.argmax(0)]
    dbest = m - best
    out["best_of_8_rechosen"] = {"mean_diff": round(float(dbest.mean()), 4),
                                 "ci95": [round(float(np.percentile(dbest, 2.5)), 4), round(float(np.percentile(dbest, 97.5)), 4)],
                                 "share_model_above": round(float((dbest > 0).mean()), 3),
                                 "how_often_each_is_best": {k: int((which == k).sum()) for k in names}}
    # expected inflation of the best-of-8 pick: mean over resamples of (max baseline) minus (the k2-signed baseline)
    k2 = names.index("H-S-k2-signed")
    out["selection_inflation_best_minus_k2signed_mean"] = round(float((best - b[k2]).mean()), 4)
    out["n_baselines_model_beats_point"] = int(sum(model.mean() > base[i].mean() for i in range(len(names))))
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
