"""POST HOC numbers needed by the revised paper (PREPRINT_v1 after its four reviews), and their lock.

Not pre-registered. Every number is computed from screens already locked by LOCK_prereg_v6 / LOCK_posthoc_v6 / LOCK_thirdfly_v1, and the
script asserts that it reproduces their locked values before writing anything.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/paper_posthoc_v1.py build   # writes research/ledger/paper_posthoc_v1/
    uv run --project ledger --no-sync python ledger/scripts/posthoc/paper_posthoc_v1.py lock    # writes research/ledger/LOCK_paper_posthoc_v1.json
    uv run --project ledger --no-sync python ledger/scripts/posthoc/paper_posthoc_v1.py check   # exit 1 if any hashed file changed

What it computes:
1. Per-type scores of the 182 three-animal types (gates_v6/TYPE_SETS_v6.json, with DNg100) under the current sweep and under the
   current-setting procedure, in all three animals; how many animals each type is a hit in (score >= 0.5); the counts with and
   without DNg100. (Numbers review P1: the paper had read C5.driver_table, which lists only current-setting hits.)
2. C7's Spearman-Brown arithmetic applied to each animal pair alone (n* = (0.8 / 0.2) (1 - r) / r, the formula behind C7's locked
   6.27), from the locked C3 sweep ratios.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ledger" / "src"))

import pandas as pd  # noqa: E402

from brainir_ledger import RESEARCH, agree, data_dir, screens6  # noqa: E402

OUT = RESEARCH / "paper_posthoc_v1"
LOCK = RESEARCH / "LOCK_paper_posthoc_v1.json"
MARKING = "POST HOC (paper revision after the four reviews; not pre-registered; computed from locked screens)"
CUT = 0.5
CHAINED = ("LOCK_prereg_v6.json", "LOCK_posthoc_v6.json", "LOCK_thirdfly_v1.json")


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _inputs() -> dict[str, Path]:
    """Every file the numbers come from (bulk result logs under the data root, tables in the repository)."""
    d = data_dir()
    out = {"$DATA/ledger/reliability_v2/MODAL_dx-1-run4/results.pkl": screens6.results_path("reliability_v2", "dx-1-run4", "MODAL")}
    for area, prefix in (("posthoc_v6", "ms"), ("thirdfly_v1", "bs"), ("thirdfly_v1", "bt")):
        for c in screens6.campaigns(area, prefix):
            p = screens6.results_path(area, c)
            out["$DATA/" + str(p.relative_to(d.parent))] = p
    for rel in ("predictions_v2/B1r/replicates.parquet", "predictions_v2/B2r/replicates.parquet", "gates_v6/TYPE_SETS_v6.json",
                "thirdfly_v1/C_tests.json"):
        out["research/ledger/" + rel] = RESEARCH / rel
    return out


def build() -> dict:
    ts = json.loads((RESEARCH / "gates_v6" / "TYPE_SETS_v6.json").read_text())
    C = json.loads((RESEARCH / "thirdfly_v1" / "C_tests.json").read_text())
    three = list(ts["three_animal"])
    assert len(three) == 182 and "DNg100" in three
    screens = {
        "MANC_sweep": screens6.sweep_manc(), "MaleCNS_sweep": screens6.sweep_mcns(), "BANC_sweep": screens6.banc_sweep(),
        "MANC_current_setting": screens6.b1r(), "MaleCNS_current_setting": screens6.b2r(), "BANC_current_setting": screens6.banc_tuned(),
    }
    t = pd.DataFrame({k: agree.type_scores(v, None, three) for k, v in screens.items()})
    t.index.name = "manc_type"

    # 1. Reproduce the locked per-type values of C5.driver_table (types in the three-animal set).
    col = {"MANC_sweep": "MANC_sweep", "MaleCNS_sweep": "MaleCNS_sweep", "BANC_sweep": "BANC_sweep", "B1r": "MANC_current_setting",
           "B2r": "MaleCNS_current_setting", "BANC_tuned": "BANC_current_setting"}
    n_cmp, worst = 0, 0.0
    for r in C["C5"]["driver_table"]:
        if r["manc_type"] not in t.index:
            continue
        for k_locked, k_here in col.items():
            if r.get(k_locked) is None:
                continue
            worst = max(worst, abs(float(r[k_locked]) - float(t.loc[r["manc_type"], k_here])))
            n_cmp += 1
    assert n_cmp > 100 and worst < 1e-12, (n_cmp, worst)

    out: dict = {"marking": MARKING, "cut": CUT, "set": "three_animal (gates_v6/TYPE_SETS_v6.json; 182 types incl. DNg100)",
                 "reproduces_C5_driver_table": {"values_compared": n_cmp, "max_abs_difference": worst}}
    for proc in ("sweep", "current_setting"):
        cols = [f"{a}_{proc}" for a in ("MANC", "MaleCNS", "BANC")]
        hits = t[cols] >= CUT
        n = hits.sum(axis=1)
        t[f"n_animals_hit_{proc}"] = n
        blk = {}
        for label, mask in (("with_DNg100", t.index == t.index), ("without_DNg100", t.index != "DNg100")):
            nn = n[mask]
            blk[label] = {"n_types": int(mask.sum()),
                          "hits_per_animal": {c.split("_")[0]: int(hits.loc[mask, c].sum()) for c in cols},
                          "hit_in_at_least_one": int((nn >= 1).sum()), "hit_in_at_least_two": int((nn >= 2).sum()),
                          "hit_in_all_three": int((nn == 3).sum()), "all_three_types": sorted(nn.index[nn == 3]),
                          "at_least_two_types": sorted(nn.index[nn >= 2])}
        out[proc] = blk

    # 2. The all-three sweep set must equal the intersection of the locked C4 lists' shared hits (both with DNg100) on this set.
    c4m = set(C["C4"]["MANC sweep list"]["manc_banc_high"]["cuts"]["0.5"]["overlap"]["point"]["types_in_both"])
    c4c = set(C["C4"]["MaleCNS sweep list"]["mcns_banc_high"]["cuts"]["0.5"]["overlap"]["point"]["types_in_both"])
    from_locked = sorted((c4m & c4c) & set(three))
    assert from_locked == out["sweep"]["with_DNg100"]["all_three_types"], (from_locked, out["sweep"]["with_DNg100"]["all_three_types"])
    out["sweep"]["all_three_from_locked_C4_intersection"] = from_locked

    # 3. C7's arithmetic per pair (sweep, three-animal set without DNg100), checked against C7's locked n*.
    c7 = C["C7"]
    f = lambda r: (0.8 / 0.2) * (1.0 - r) / r  # noqa: E731
    assert abs(f(c7["rbar"]) - c7["n_star"]) < 1e-9
    out["C7_per_pair"] = {"formula": "n* = (0.8 / 0.2) (1 - r) / r (Spearman-Brown; reproduces C7's locked n* from its rbar)",
                          "ratios": c7["ratios"], "n_star": {k: f(v) for k, v in c7["ratios"].items()},
                          "range": [min(f(v) for v in c7["ratios"].values()), max(f(v) for v in c7["ratios"].values())],
                          "pairs": {"MB": "MANC-BANC", "CB": "MaleCNS-BANC", "MC": "MANC-MaleCNS (post hoc reference)"}}

    OUT.mkdir(exist_ok=True)
    t = t.sort_values(["n_animals_hit_sweep", "MANC_sweep"], ascending=[False, False])
    t.round(6).to_csv(OUT / "THREE_ANIMAL_SCORES.csv")
    out["inputs_sha256"] = {k: _sha(p) for k, p in sorted(_inputs().items())}
    (OUT / "PAPER_POSTHOC.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("sweep", "current_setting")}, indent=1)[:2500])
    print("C7 per pair:", {k: round(v, 2) for k, v in out["C7_per_pair"]["n_star"].items()})
    return out


def _hashed() -> dict[str, Path]:
    files = {"ledger/scripts/posthoc/paper_posthoc_v1.py": Path(__file__).resolve(),
             "ledger/src/brainir_ledger/screens6.py": ROOT / "ledger/src/brainir_ledger/screens6.py",
             "ledger/src/brainir_ledger/agree.py": ROOT / "ledger/src/brainir_ledger/agree.py",
             "research/ledger/paper_posthoc_v1/PAPER_POSTHOC.json": OUT / "PAPER_POSTHOC.json",
             "research/ledger/paper_posthoc_v1/THREE_ANIMAL_SCORES.csv": OUT / "THREE_ANIMAL_SCORES.csv"}
    files.update({"research/ledger/" + n: RESEARCH / n for n in CHAINED})
    files.update(_inputs())
    return files


def lock() -> None:
    if LOCK.exists():
        raise SystemExit(f"{LOCK.name} exists: a lock is never rewritten")
    rec = {"lock": LOCK.name, "marking": MARKING, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "tag": "ledger-paper-posthoc-v1", "sha256": {k: _sha(p) for k, p in sorted(_hashed().items())}}
    LOCK.write_text(json.dumps(rec, indent=1) + "\n")
    print(LOCK.name, _sha(LOCK))


def check() -> int:
    rec = json.loads(LOCK.read_text())
    paths = _hashed()
    changed = [k for k, v in rec["sha256"].items() if k not in paths or not paths[k].exists() or _sha(paths[k]) != v]
    extra = sorted(set(paths) - set(rec["sha256"]))
    print(json.dumps({"lock": LOCK.name, "n_checked": len(rec["sha256"]), "changed_or_missing": changed, "unrecorded": extra}))
    return 1 if changed or extra else 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "lock":
        lock()
    elif cmd == "check":
        raise SystemExit(check())
    else:
        raise SystemExit(__doc__)
