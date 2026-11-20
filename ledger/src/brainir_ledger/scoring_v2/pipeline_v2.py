"""Scoring v2 (run 2, PREREG v2 Part S): the four pre-declared runs P, S-a, S-b and S-c, built on the FROZEN v1 scoring code
(`brainir_ledger.scoring`: `verify_inputs`, `check_type_labels`, `primary`, `secondary`, `evaluate`, the statistics and their
seeds 20261120 / 20261121 / 20261122), which is imported and never edited.

    uv run --project ledger --no-sync python ledger/scripts/score_v2.py --run P      # then S-a, S-b, S-c; each run once

Flag file `research/ledger/UNBLIND.json`, created only by the person who authorises unblinding (after the gate, PREREG v2 S5);
one entry per run. As in PREREG v1 section 1 each entry names its two locks by plain file name and by SHA-256, plus
`authorised_by` and `utc` (these two may instead be given once at the top level):

    {"runs": {"P":   {"predictions_lock": "LOCK_predictions_v1.json", "labels_lock": "LOCK_labels_v2.json",
                      "predictions_lock_sha256": "<sha256>", "labels_lock_sha256": "<sha256>",
                      "authorised_by": "...", "utc": "..."},
              "S-a": {...}, "S-b": {...}, "S-c": {...}}}

| run | predictions lock | labels lock | exposed set (PREREG v2 L6, S4) | analyses |
|---|---|---|---|---|
| P   | LOCK_predictions_v1.json | LOCK_labels_v2.json   | kit_v2 list + labels_v2/exposed_v2.csv | frozen `primary` (PREREG v1 section 7) |
| S-a | LOCK_predictions_v1.json | LOCK_labels_v1_1.json | kit (v1) list                          | frozen `primary` |
| S-b | LOCK_predictions_v1.json | LOCK_labels_v2.json   | v2 set                                 | frozen `secondary` (PREREG v1 section 8, 1-14) |
| S-c | LOCK_predictions_v2.json | LOCK_labels_v2.json   | v2 set                                 | PREREG v2 S3 (`analyses_s3`) |

Order of operations, each enforced in code:
1. the flag file exists (the first statement of `run`); it lists the run; the run names exactly its S4 locks, as plain file
   names whose SHA-256 match; a run whose result file already exists is refused (S4: each run once);
2. every file read is verified against the locks: the frozen `verify_inputs` (P, S-a, S-b; S-c see below);
3. the exposed set is formed from its files, never from the table's own column; the kit list must be hashed by the labels
   lock (`kit_v2` / `kit` section) and `exposed_v2.csv` by its `labels` section; the frozen `check_type_labels` recomputes
   `type_labels` from `records.jsonl` with that set and requires it to equal `type_labels.csv`;
4. the analyses run; each reports a status (ok / not_locked / input_missing / error); one failure never stops another;
5. one JSON per run, research/ledger/results/run2/<run>.json (the folder is created then).

S-c and the two prediction locks. `LOCK_predictions_v2.json` is additive and holds no A1, which the frozen `verify_inputs`
requires, while the primary set is defined on A1's types (S1). So S-c (a) requires the SHA-256 of `LOCK_predictions_v1.json`
to equal the one recorded in `LOCK_predictions_v2.json` (`v1_locks`), (b) runs the frozen `verify_inputs` on
`LOCK_predictions_v1.json` + `LOCK_labels_v2.json`, (c) verifies every v2 arm file with the frozen rules (each listed file
exists and matches; each arm lists its `types.csv`), and (d) reads only the `manc_type` column of A1.

Assumed table formats of the v2 arms (no writer exists yet for B1r/B2r/B3 tables):
- B1r, B2r: `types.csv` with `manc_type`, `primary_score`, `band` (PREREG v1 section 11, `tables.TYPES_COLUMNS`);
- B3: `legs.csv` in the long format of PREREG v1 section 11 (`manc_type`, `leg`, `score`, ...); the rows with `leg` in
  front / middle / hind are the segment-pair scores; the file must be listed in the lock; a non-finite score drops the type
  from that segment's set (counted in `n_dropped_nonfinite`, as the frozen `evaluate` does);
- B4v2: `types.csv` with `manc_type`, `call_128` (values of PREREG v2 P3; anything else is an error).
"""

from __future__ import annotations

import hashlib
import json
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

from ..scoring import BlindError
from ..scoring import stats as ST
from ..scoring.pipeline import (
    B4_NON_CALLS,
    PREREGISTERED_SECONDARY,
    NotLocked,
    _clean,
    check_type_labels,
    evaluate,
    kit_exposed,
    labeled_set,
    primary,
    secondary,
    verify_inputs,
)

RUNS = {
    "P": {"predictions_lock": "LOCK_predictions_v1.json", "labels_lock": "LOCK_labels_v2.json", "analysis": "primary"},
    "S-a": {"predictions_lock": "LOCK_predictions_v1.json", "labels_lock": "LOCK_labels_v1_1.json", "analysis": "primary"},
    "S-b": {"predictions_lock": "LOCK_predictions_v1.json", "labels_lock": "LOCK_labels_v2.json", "analysis": "secondary"},
    "S-c": {"predictions_lock": "LOCK_predictions_v2.json", "labels_lock": "LOCK_labels_v2.json", "analysis": "s3"},
}
PRED_DIRS = {"LOCK_predictions_v1.json": "predictions", "LOCK_predictions_v2.json": "predictions_v2"}
LABEL_DIRS = {"LOCK_labels_v2.json": "labels_v2", "LOCK_labels_v1_1.json": "labels_v1_1"}
FLAG_KEYS = ("predictions_lock", "labels_lock", "predictions_lock_sha256", "labels_lock_sha256", "authorised_by", "utc")
V1_PREDICTIONS_LOCK_KEY = "research/ledger/LOCK_predictions_v1.json"  # the key under which lock2.py records it (`v1_locks`)
SEGMENTS = ("front", "middle", "hind")
B4V2_CALLS = ("halts", "saturates", "rhythm_lost_other", "speeds_up", "slows_down", "no_effect", "no_effect_low_n",
              "background_not_rhythmic")
B4V2_LOST = ("saturates", "rhythm_lost_other")
B4_MODULATION = {"halts": "stops", "speeds_up": "speeds", "slows_down": "slows", "no_effect": "none"}  # PREREG v1 section 8, 12
PREREGISTERED_S3 = ["B1r", "B2r", "B1r_vs_B2r", "B3_segment_pairs", "B4v2_stop_lost_excluded", "B4v2_stop_lost_as_non_halts",
                    "B4v2_modulation"]
NOT_ANALYSED_S3 = {"B6": "PREREG v2 S3: B6 is not analysed in run 2"}


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------------------------- the flag
def run_flag(name: str, research: Path, flags_file: Path) -> dict:
    """The run's entry of the flag file, checked as the frozen `require_unblind` checks the v1 flag, plus the S4 pairing."""
    if not Path(flags_file).exists():
        raise BlindError(f"scoring refused: {Path(flags_file).name} does not exist (predictions and labels stay blind until it is "
                         "created by the person who authorises unblinding)")
    if name not in RUNS:
        raise BlindError(f"scoring refused: unknown run {name!r} (PREREG v2 S4 declares {sorted(RUNS)})")
    try:
        d = json.loads(Path(flags_file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise BlindError(f"scoring refused: {Path(flags_file).name} is not readable JSON ({type(e).__name__})") from None
    runs = d.get("runs") if isinstance(d, dict) else None
    if not isinstance(runs, dict) or not isinstance(runs.get(name), dict):
        raise BlindError(f"scoring refused: run {name} is not listed in {Path(flags_file).name}")
    flag = {k: d[k] for k in ("authorised_by", "utc") if k in d} | runs[name]
    for k in FLAG_KEYS:
        if flag.get(k) in (None, ""):
            raise BlindError(f"scoring refused: the entry of run {name} in {Path(flags_file).name} lacks '{k}'")
    for side in ("predictions", "labels"):
        lock_name = str(flag[f"{side}_lock"])
        if "/" in lock_name or "\\" in lock_name or ".." in lock_name or not lock_name.startswith(f"LOCK_{side}_v") \
                or not lock_name.endswith(".json"):
            raise BlindError(f"scoring refused: {side}_lock must be a plain file name LOCK_{side}_v<k>.json in research/ledger")
        if lock_name != RUNS[name][f"{side}_lock"]:
            raise BlindError(f"scoring refused: run {name} uses {RUNS[name][f'{side}_lock']} (PREREG v2 S4); the flag names {lock_name}")
        p = Path(research) / lock_name
        if not p.exists() or _sha(p) != flag[f"{side}_lock_sha256"]:
            raise BlindError(f"scoring refused: {side} lock {lock_name} missing or its SHA-256 differs from the flag")
    return flag


# ------------------------------------------------------------------------------------------------------------- inputs
def _verify_arms(plock: dict, pred_dir: Path) -> tuple[int, dict[str, list[str]]]:
    """The frozen `verify_inputs` rules for prediction files (every listed file exists and matches; every arm lists its
    types.csv), without its A1 requirement: A1 is a v1 arm, verified through the v1 lock."""
    n, files = 0, {}
    for arm, fs in (plock.get("arms_locked") or {}).items():
        if not any(Path(rel).name == "types.csv" for rel in fs):
            raise BlindError(f"predictions lock lists arm {arm} without its types.csv")
        for rel, sha in fs.items():
            p = pred_dir / arm / Path(rel).name
            if not p.exists() or _sha(p) != sha:
                raise BlindError(f"prediction file {arm}/{Path(rel).name} missing or changed since the predictions lock")
            n += 1
        files[arm] = sorted(Path(rel).name for rel in fs)
    return n, files


def verify_run(flag: dict, research: Path) -> tuple[dict, Path, Path, dict]:
    """(verification record, prediction folder, label folder, labels lock) for a checked run entry."""
    labels_dir = research / LABEL_DIRS[flag["labels_lock"]]
    llock = json.loads((research / flag["labels_lock"]).read_text(encoding="utf-8"))
    if flag["predictions_lock"] == "LOCK_predictions_v1.json":
        pred_dir = research / PRED_DIRS["LOCK_predictions_v1.json"]
        return verify_inputs(flag, research, pred_dir, labels_dir), pred_dir, labels_dir, llock
    plock2 = json.loads((research / flag["predictions_lock"]).read_text(encoding="utf-8"))
    want = (plock2.get("v1_locks") or {}).get(V1_PREDICTIONS_LOCK_KEY)
    p1 = research / "LOCK_predictions_v1.json"
    if not want or not p1.exists() or _sha(p1) != want:
        raise BlindError("scoring refused: LOCK_predictions_v1.json is missing or differs from the SHA-256 recorded in "
                         f"{flag['predictions_lock']} (v1_locks); A1's type names cannot be verified")
    v1 = verify_inputs({"predictions_lock": "LOCK_predictions_v1.json", "labels_lock": flag["labels_lock"]}, research,
                       research / PRED_DIRS["LOCK_predictions_v1.json"], labels_dir)
    pred_dir = research / PRED_DIRS[flag["predictions_lock"]]
    n, files = _verify_arms(plock2, pred_dir)
    ver = {"arms_locked": sorted(files), "arm_files": files, "arms_not_locked": plock2.get("arms_not_locked") or {},
           "verified_files": n + v1["verified_files"],
           "v1_lock_chain": "LOCK_predictions_v1.json SHA-256 equals LOCK_predictions_v2.json v1_locks; frozen verify_inputs passed "
                            "on LOCK_predictions_v1.json + the labels lock",
           "v1_arms_verified": v1["arms_locked"], "a1_read": "manc_type column only (membership of the primary set)"}
    return ver, pred_dir, labels_dir, llock


def _require_hashed(llock: dict, research: Path, rel: str, sections: tuple[str, ...]) -> None:
    """`research/ledger/<rel>` must be hashed in one of the lock's `sections` and match."""
    key = f"research/ledger/{rel}"
    for sec in sections:
        want = (llock.get(sec) or {}).get(key)
        if want is not None:
            p = research / rel
            if not p.exists() or _sha(p) != want:
                raise BlindError(f"scoring refused: {rel} is missing or differs from its SHA-256 in the labels lock")
            return
    raise BlindError(f"scoring refused: the labels lock does not hash {rel} (sections {list(sections)})")


def exposed_set_v2(research: Path, labels_dir: Path | None = None) -> set[str]:
    """PREREG v2 L6: `kit_v2/exposed_types.csv` (column `manc_types`, ';'-separated; parsed exactly as the frozen
    `kit_exposed` and `labels2_collect.finalize` parse it) plus `labels_v2/exposed_v2.csv` (column `manc_type`; may be
    header-only). A missing file is an error, never an empty set (the frozen fallback would trust the table's own column)."""
    labels_dir = labels_dir or Path(research) / "labels_v2"
    kit = Path(research) / "kit_v2" / "exposed_types.csv"
    nat = Path(labels_dir) / "exposed_v2.csv"
    for p in (kit, nat):
        if not p.exists():
            raise BlindError(f"{p.parent.name}/{p.name} is missing: the v2 exposed set (PREREG v2 L6) cannot be formed")
    try:
        ex = pd.read_csv(kit)
        nv = pd.read_csv(nat, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError as e:
        raise BlindError(f"an exposed-set file is empty (not even a header): {e}") from None
    out = {t for s in ex["manc_types"].dropna() for t in str(s).split(";") if t}
    return out | {t for t in nv["manc_type"] if t}


def exposed_for_run(research: Path, labels_dir: Path, llock: dict) -> tuple[set[str], dict]:
    if labels_dir.name == "labels_v2":
        _require_hashed(llock, research, "kit_v2/exposed_types.csv", ("kit_v2",))
        _require_hashed(llock, research, f"{labels_dir.name}/exposed_v2.csv", ("labels",))
        ex = exposed_set_v2(research, labels_dir)
        return ex, {"definition": "kit_v2/exposed_types.csv + labels_v2/exposed_v2.csv (PREREG v2 L6)", "n_types": len(ex)}
    _require_hashed(llock, research, "kit/exposed_types.csv", ("kit",))
    ex = kit_exposed(research)
    if ex is None:
        raise BlindError("scoring refused: kit/exposed_types.csv is missing (S-a uses the v1 exposed list)")
    return ex, {"definition": "kit/exposed_types.csv, the v1 list (PREREG v2 S4, S-a)", "n_types": len(ex)}


# ------------------------------------------------------------------------------------------------------------- analyses
def _run_v2(name: str, fn, results: dict, not_locked: dict[str, str]) -> None:
    """The frozen `_run` with the v2 lock's `arms_not_locked` reasons (the frozen one names run-1 reasons for B3/B6)."""
    try:
        results[name] = {"status": "ok", "result": _clean(fn())}
    except NotLocked as e:
        arm = str(e)
        results[name] = {"status": "not_locked", "arm": arm, "reason": not_locked.get(arm, "arm not in the predictions lock")}
    except FileNotFoundError as e:
        results[name] = {"status": "input_missing", "detail": str(e)}
    except Exception as e:  # noqa: BLE001 - one analysis never stops the others
        results[name] = {"status": "error", "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-2000:]}


def _load_v2(pred_dir: Path, arm: str, locked: list[str]) -> pd.DataFrame:
    if arm not in locked:
        raise NotLocked(arm)
    p = pred_dir / arm / "types.csv"
    if not p.exists():
        raise FileNotFoundError(f"{arm}/types.csv")
    df = pd.read_csv(p)
    if df["manc_type"].duplicated().any():
        raise ValueError(f"{arm}/types.csv has more than one row for a manc_type")
    return df.set_index("manc_type", drop=False)


def _crosstab(rows, cols, row_name: str, col_name: str) -> dict:
    """{column value: {row value: count}} (the orientation of the frozen `pd.crosstab(...).to_dict()`), plain ints."""
    rows, cols = list(rows), list(cols)
    if not rows:
        return {}
    ct = pd.crosstab(pd.Series(rows, name=row_name), pd.Series(cols, name=col_name))
    return {str(c): {str(r): int(v) for r, v in ct[c].items()} for c in ct.columns}


def _agreement(pred: list[str], true: list[str]) -> dict:
    return {"raw_agreement": float(np.mean([p == q for p, q in zip(pred, true)])) if pred else None,
            "kappa": ST.cohen_kappa(pred, true) if pred else None}


def analyses_s3(research: Path, pred_dir: Path, tl: pd.DataFrame, ver: dict, *, n_boot: int, n_perm: int) -> dict:
    """PREREG v2 S3 on labels v2 (run S-c)."""
    R: dict = {}
    locked, files, reasons = ver["arms_locked"], ver.get("arm_files") or {}, ver.get("arms_not_locked") or {}
    exposed = set(tl.loc[tl["exposed"].astype(bool), "manc_type"])  # = the v2 set (checked by check_type_labels)
    a1_types = set(pd.read_csv(research / PRED_DIRS["LOCK_predictions_v1.json"] / "A1" / "types.csv", usecols=["manc_type"])["manc_type"])
    y_front = labeled_set(tl)
    y_primary = y_front[y_front.index.isin(a1_types)]
    t = tl.set_index("manc_type")

    def arm_auroc(arm: str) -> dict:
        df = _load_v2(pred_dir, arm, locked)
        r = evaluate(df["primary_score"], y_primary[y_primary.index.isin(df.index)], n_boot=n_boot, n_perm=n_perm)
        r["set_definition"] = ("primary set (front-leg consensus yes/no, among A1's types, not in the v2 exposed set) restricted "
                               "to the types the arm covers, finite score")
        r["n_primary_set"] = len(y_primary)
        return r
    for arm in ("B1r", "B2r"):
        _run_v2(arm, lambda arm=arm: arm_auroc(arm), R, reasons)

    def two_fly() -> dict:
        b1, b2 = _load_v2(pred_dir, "B1r", locked), _load_v2(pred_dir, "B2r", locked)
        common = sorted(set(b1.index) & set(b2.index))
        x = pd.to_numeric(b1.loc[common, "primary_score"], errors="coerce").astype(float)
        z = pd.to_numeric(b2.loc[common, "primary_score"], errors="coerce").astype(float)
        if not (np.isfinite(x.to_numpy()).all() and np.isfinite(z.to_numpy()).all()):
            raise ValueError("non-finite primary_score on a common type")
        k = min(10, len(common))

        def top(s: pd.Series) -> set:
            return set(sorted(s.index, key=lambda ty: (-float(s[ty]), ty))[:k])
        band1, band2 = b1.loc[common, "band"].astype(str).tolist(), b2.loc[common, "band"].astype(str).tolist()
        dis = [ty for ty, u, v in zip(common, band1, band2) if u != v]
        return {"n_common_types": len(common), "spearman": ST.spearman(x, z) if len(common) > 2 else None,
                "top_k": k, "top10_overlap": len(top(x) & top(z)),
                "band_agreement": (1.0 - len(dis) / len(common)) if common else None, "n_band_disagreements": len(dis),
                "types_band_disagree": dis, "band_crosstab": _crosstab(band1, band2, "B1r", "B2r"),
                "definition": "all types in both arms (no labels); primary_score; top 10 by score, ties broken by type name; "
                              "band = the arms' own band column"}
    _run_v2("B1r_vs_B2r", two_fly, R, reasons)

    def b3_segments() -> dict:
        if "B3" not in locked:
            raise NotLocked("B3")
        if "legs.csv" not in files.get("B3", []):
            raise FileNotFoundError("B3/legs.csv is not in the predictions lock")
        legs = pd.read_csv(pred_dir / "B3" / "legs.csv")
        seg = legs[legs["leg"].astype(str).isin(SEGMENTS)]
        if seg.duplicated(["manc_type", "leg"]).any():
            raise ValueError("B3/legs.csv has more than one row per (manc_type, segment pair)")
        wide = seg.pivot(index="manc_type", columns="leg", values="score")
        out = {}
        for s in SEGMENTS:
            if s not in wide.columns:
                raise ValueError(f"B3/legs.csv has no '{s}' rows")
            ys = labeled_set(tl, field=s)
            r = evaluate(pd.to_numeric(wide[s], errors="coerce"), ys[ys.index.isin(wide.index)], n_boot=n_boot, n_perm=n_perm)
            r["set_definition"] = f"{s} leg-pair consensus yes/no, not in the v2 exposed set, covered by B3, finite {s} score"
            out[s] = r
        return out
    _run_v2("B3_segment_pairs", b3_segments, R, reasons)

    def b4v2_calls() -> pd.Series:
        b4 = _load_v2(pred_dir, "B4v2", locked)
        calls = b4["call_128"].astype(str)
        unknown = sorted(set(calls) - set(B4V2_CALLS))
        if unknown:
            raise ValueError(f"B4v2 call_128 has values outside PREREG v2 P3: {unknown}")
        return calls

    def b4v2_stop(lost_as_non_halt: bool) -> dict:
        calls = b4v2_calls()
        cand = [k for k in calls.index if k in t.index and t.loc[k, "stop_call"] in ("stops", "no_stop") and k not in exposed]
        common = [k for k in cand if calls[k] not in B4_NON_CALLS and (lost_as_non_halt or calls[k] not in B4V2_LOST)]
        pred = ["stops" if calls[k] == "halts" else "no_stop" for k in common]
        true = [str(t.loc[k, "stop_call"]) for k in common]
        return {"n": len(common), "n_excluded_non_calls": sum(calls[k] in B4_NON_CALLS for k in cand),
                "n_saturates": sum(calls[k] == "saturates" for k in cand),
                "n_rhythm_lost_other": sum(calls[k] == "rhythm_lost_other" for k in cand),
                "saturates_and_rhythm_lost_other": "counted as non-halts (no_stop)" if lost_as_non_halt else "excluded",
                **_agreement(pred, true), "confusion": _crosstab(pred, true, "pred", "label"),
                "definition": "call_128 halts -> stops, other calls -> no_stop, against stop_call (stops / no_stop); exposed types "
                              "and non-calls (background_not_rhythmic, no_effect_low_n) excluded"}
    _run_v2("B4v2_stop_lost_excluded", lambda: b4v2_stop(False), R, reasons)
    _run_v2("B4v2_stop_lost_as_non_halts", lambda: b4v2_stop(True), R, reasons)

    def b4v2_modulation() -> dict:
        calls = b4v2_calls()
        labelled = [k for k in calls.index if k in t.index and k not in exposed]
        cand = [k for k in labelled if t.loc[k, "walking_effect"] in ("stops", "slows", "speeds", "none")]
        common = [k for k in cand if calls[k] in B4_MODULATION]
        pred = [B4_MODULATION[calls[k]] for k in common]
        true = [str(t.loc[k, "walking_effect"]) for k in common]
        return {"n": len(common), "n_excluded_non_calls": sum(calls[k] in B4_NON_CALLS for k in cand),
                "n_excluded_saturates_or_rhythm_lost_other": sum(calls[k] in B4V2_LOST for k in cand),
                "n_label_turns_excluded": sum(t.loc[k, "walking_effect"] == "turns" for k in labelled),
                **_agreement(pred, true), "confusion": _crosstab(pred, true, "pred", "label"),
                "definition": "halts->stops, speeds_up->speeds, slows_down->slows, no_effect->none against walking_effect; "
                              "saturates and rhythm_lost_other have no walking-effect counterpart and are excluded and counted"}
    _run_v2("B4v2_modulation", b4v2_modulation, R, reasons)
    return R


# ------------------------------------------------------------------------------------------------------------- one run
def run(name: str, research_dir: Path, flags_file: Path, *, n_boot: int = 10_000, n_perm: int = 10_000) -> dict:
    """One pre-declared run of PREREG v2 S4 -> research_dir/results/run2/<name>.json. Raises the frozen `BlindError` (nothing
    computed, nothing written) when the flag file is missing, does not list the run, names other locks than S4, or when any
    input differs from its lock."""
    if not Path(flags_file).exists():  # first: nothing is opened before the flag file is known to exist
        raise BlindError(f"scoring refused: {Path(flags_file).name} does not exist (predictions and labels stay blind until it is "
                         "created by the person who authorises unblinding)")
    research = Path(research_dir)
    flag = run_flag(name, research, Path(flags_file))
    out = research / "results" / "run2" / f"{name}.json"
    if out.exists():
        raise BlindError(f"scoring refused: {out.name} exists in results/run2; PREREG v2 S4 runs each analysis once")
    ver, pred_dir, labels_dir, llock = verify_run(flag, research)
    exposed, exposed_info = exposed_for_run(research, labels_dir, llock)
    tl = check_type_labels(labels_dir, exposed)
    here = Path(__file__).resolve().parent
    res: dict = {"prereg": "research/ledger/PREREG_v2.md Part S (S1-S4) with research/ledger/PREREG.md v1 sections 7-8", "run": name,
                 "run_definition": dict(RUNS[name]), "unblind_flag": flag, "inputs": ver, "exposed_set": exposed_info,
                 "type_labels_check": "type_labels recomputed from records.jsonl with this exposed set equals type_labels.csv",
                 "n_boot": n_boot, "n_perm": n_perm,
                 "code_sha256": {f"{p.parent.name}/{p.name}": _sha(p) for p in (here / "pipeline_v2.py", here.parent / "scoring" / "pipeline.py",
                                                                              here.parent / "scoring" / "stats.py")}}
    kind = RUNS[name]["analysis"]
    if kind == "primary":
        # PREREG v2 S4: an exception in the primary analysis is a crash (uncaught; the run is repeated once after the fix),
        # never an `error` result
        res["primary"] = {"status": "ok", "result": _clean(primary(pred_dir, tl, ver["arms_locked"], n_boot=n_boot, n_perm=n_perm))}
    elif kind == "secondary":
        # single secondary analyses record `error` inside the frozen `secondary`; an exception escaping it is a crash (S4)
        res["analyses"] = secondary(pred_dir, labels_dir, tl, ver["arms_locked"], n_boot=n_boot, n_perm=n_perm)
        missing = [k for k in PREREGISTERED_SECONDARY if k not in res["analyses"]]
        if missing:
            res["analyses_missing_from_code"] = missing
    else:
        res["analyses"] = analyses_s3(research, pred_dir, tl, ver, n_boot=n_boot, n_perm=n_perm)
        res["not_analysed"] = dict(NOT_ANALYSED_S3)
        missing = [k for k in PREREGISTERED_S3 if k not in res["analyses"]]
        if missing:
            res["analyses_missing_from_code"] = missing
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    return res
