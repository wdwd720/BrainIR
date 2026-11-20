"""One-shot scoring (run 2): join frozen predictions with frozen labels and compute PREREG sections 7-8.

    uv run --project ledger --no-sync python -m brainir_ledger.scoring.pipeline --out research/ledger/score_v1

Order of operations (each enforced in code):
1. `require_unblind`: research/ledger/UNBLIND.json exists, is well formed, and names both lock files by SHA-256.
2. `verify_inputs`: every prediction file and label file that is read is hashed and must equal its entry in the locks.
3. The type labels are recomputed from `records.jsonl` and must equal `type_labels.csv`.
4. The primary analysis is computed and written to `<out>/score_primary.json` before anything else.
5. Every pre-registered secondary analysis runs in isolation and is reported with a status: ok, not_locked (arm not in the
   predictions lock), input_missing, or error (with the message). One failure never stops the others.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

from .. import LABELS, PREDICTIONS, RESEARCH
from ..labels import aggregate as AGG
from . import BlindError, require_unblind
from . import stats as ST

UNINFORMED_BASELINES = ["S1_direct_mn", "S2_twohop_signed", "S3_twohop_abs", "S4_total_out", "S5_out_partners", "S6_premotor",
                        "S7_n_members"]
INFORMED_BASELINE = "S8_informed"
SEEDS = {"boot": 20261120, "perm": 20261121, "paired": 20261122}
NOT_LOCKED_IN_RUN1 = {"B3": "G3 failed (PREREG 9)", "B6": "depends on B3"}
B4_NON_CALLS = ("background_not_rhythmic", "no_effect_low_n")


class NotLocked(Exception):
    """The analysis needs an arm that the predictions lock does not contain."""


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_inputs(flag: dict, research: Path, pred_dir: Path, labels_dir: Path) -> dict:
    """Hash every file the scoring reads against the two locks; returns {'arms_locked': [...], 'verified_files': n}."""
    plock = json.loads((research / flag["predictions_lock"]).read_text(encoding="utf-8"))
    llock = json.loads((research / flag["labels_lock"]).read_text(encoding="utf-8"))
    n = 0
    arms = sorted((plock.get("arms_locked") or {}).keys())
    for arm, files in (plock.get("arms_locked") or {}).items():
        if not any(Path(rel).name == "types.csv" for rel in files):
            raise BlindError(f"predictions lock lists arm {arm} without its types.csv")
        for rel, sha in files.items():
            p = pred_dir / arm / Path(rel).name
            if not p.exists() or _sha(p) != sha:
                raise BlindError(f"prediction file {arm}/{Path(rel).name} missing or changed since the predictions lock")
            n += 1
    for rel, sha in (llock.get("labels") or {}).items():
        p = labels_dir / Path(rel).name
        if not p.exists() or _sha(p) != sha:
            raise BlindError(f"label file {Path(rel).name} missing or changed since the labels lock")
        n += 1
    for need in ("type_labels.csv", "records.jsonl"):
        if not any(Path(r).name == need for r in (llock.get("labels") or {})):
            raise BlindError(f"labels lock does not cover {need}")
    if "A1" not in arms:
        raise BlindError("predictions lock does not cover A1 (primary prediction)")
    return {"arms_locked": arms, "verified_files": n}


def kit_exposed(research: Path) -> set[str] | None:
    p = research / "kit" / "exposed_types.csv"
    if not p.exists():
        return None
    ex = pd.read_csv(p)
    return {t for s in ex["manc_types"].dropna() for t in str(s).split(";") if t}


def check_type_labels(labels_dir: Path, exposed_expected: set[str] | None = None) -> pd.DataFrame:
    tl = pd.read_csv(labels_dir / "type_labels.csv")
    recs = AGG.read_records(labels_dir / "records.jsonl")
    exposed = exposed_expected if exposed_expected is not None else set(tl.loc[tl["exposed"].astype(bool), "manc_type"])
    re_tl = AGG.type_labels(recs, exposed=exposed, type_list=list(tl["manc_type"]))
    cols = ["manc_type", "front", "middle", "hind", "stop_call", "walking_effect", "n_records", "exposed", "freq_hz"]
    def canon(df):
        d = df[cols].sort_values("manc_type").reset_index(drop=True).copy()
        d["freq_hz"] = pd.to_numeric(d["freq_hz"], errors="coerce").round(6)
        d["exposed"] = d["exposed"].astype(str).str.lower()
        return d.astype(str)
    a, b = canon(tl), canon(re_tl)
    if not a.equals(b):
        raise BlindError("type_labels.csv differs from the labels recomputed from records.jsonl")
    return tl


def load_arm(pred_dir: Path, arm: str, locked: list[str]) -> pd.DataFrame:
    if arm in NOT_LOCKED_IN_RUN1 or arm not in locked:
        raise NotLocked(arm)
    p = pred_dir / arm / "types.csv"
    if not p.exists():
        raise FileNotFoundError("input_missing")
    return pd.read_csv(p).set_index("manc_type", drop=False)


def labeled_set(type_labels: pd.DataFrame, field: str = "front", include_exposed: bool = False) -> pd.Series:
    t = type_labels[type_labels[field].isin(["yes", "no"])]
    if not include_exposed:
        t = t[~t["exposed"].astype(bool)]
    return pd.Series((t[field] == "yes").astype(int).to_numpy(), index=t["manc_type"].to_numpy())


def evaluate(scores: pd.Series, y: pd.Series, *, n_boot: int = 10_000, n_perm: int = 10_000) -> dict:
    s_all = pd.to_numeric(scores, errors="coerce")
    common = [t for t in y.index if t in s_all.index]
    vals = s_all.reindex(common).to_numpy(dtype=float)
    keep = np.isfinite(vals)
    n_drop = int((~keep).sum())
    common = [t for t, k in zip(common, keep) if k]
    s = vals[keep]
    yy = y.reindex(common).to_numpy()
    out = {"n": len(common), "n_pos": int(yy.sum()), "n_neg": int(len(yy) - yy.sum()), "n_dropped_nonfinite": n_drop, "_set": common}
    if out["n_pos"] == 0 or out["n_neg"] == 0:
        out["auroc"] = None
        return out
    out.update({"auroc": ST.auroc(s, yy), "boot": ST.bootstrap_auroc(s, yy, n_boot=n_boot, seed=SEEDS["boot"]),
                "perm": ST.permutation_p(s, yy, n_perm=n_perm, seed=SEEDS["perm"]), "bands": ST.precision_npv(s, yy),
                "calibration": ST.calibration(s, yy)})
    return out


def _clean(x):
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items() if k != "_set"}
    return x


def _run(name: str, fn, results: dict) -> None:
    try:
        results[name] = {"status": "ok", "result": _clean(fn())}
    except NotLocked as e:
        arm = str(e)
        results[name] = {"status": "not_locked", "arm": arm, "reason": NOT_LOCKED_IN_RUN1.get(arm, "arm not in the predictions lock")}
    except FileNotFoundError:
        results[name] = {"status": "input_missing"}
    except Exception as e:  # noqa: BLE001 - one analysis never stops the others
        results[name] = {"status": "error", "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-2000:]}


def primary(pred_dir: Path, tl: pd.DataFrame, locked: list[str], *, n_boot: int, n_perm: int) -> dict:
    a1 = load_arm(pred_dir, "A1", locked)
    y = labeled_set(tl)
    y = y[y.index.isin(a1.index)]
    prim = evaluate(a1["primary_score"], y, n_boot=n_boot, n_perm=n_perm)
    prim["set_definition"] = "front-leg consensus yes/no, among A1's 321 types, exposed excluded, finite A1 score"
    common = prim.pop("_set")
    base_status = "not_run"
    if prim.get("auroc") is not None:
        try:
            base = load_arm(pred_dir, "S", locked)
            yy = y.reindex(common).to_numpy()
            a1s = a1["primary_score"].reindex(common).to_numpy(dtype=float)
            bvals = {b: base[b].reindex(common).astype(float).to_numpy() for b in UNINFORMED_BASELINES + [INFORMED_BASELINE] if b in base}
            bad = [b for b, v in bvals.items() if not np.all(np.isfinite(v))]
            if bad:
                raise ValueError(f"baselines {bad} have missing or non-finite values on the analysis set")
            aucs = {b: ST.auroc(bvals[b], yy) for b in UNINFORMED_BASELINES if b in bvals}
            top = max(aucs.values())
            best = next(b for b in UNINFORMED_BASELINES if b in aucs and aucs[b] == top)  # tie -> first in S1..S7 order
            prim.update(baselines_auroc=aucs, best_baseline=best,
                        vs_best_baseline=ST.paired_bootstrap_diff(a1s, bvals[best], yy, n_boot=n_boot, seed=SEEDS["paired"]))
            if INFORMED_BASELINE in bvals:
                prim["informed_auroc"] = ST.auroc(bvals[INFORMED_BASELINE], yy)
                prim["vs_informed"] = ST.paired_bootstrap_diff(a1s, bvals[INFORMED_BASELINE], yy, n_boot=n_boot, seed=SEEDS["paired"])
            base_status = "ok"
        except NotLocked:
            base_status = "not_locked: S is not in the predictions lock, so 'adds value beyond wiring' cannot be tested"
        except Exception as e:  # noqa: BLE001 - the AUROC and the first decision survive a baseline failure
            base_status = f"error: {type(e).__name__}: {e}"
    prim["baseline_comparison_status"] = base_status
    lo = prim["boot"]["lo"] if prim.get("auroc") is not None else float("nan")
    prim["decision"] = ST.primary_decision(prim["n"], prim["n_pos"], prim["n_neg"], lo, prim.get("vs_best_baseline", {}).get("lo"))
    return prim


def secondary(pred_dir: Path, labels_dir: Path, tl: pd.DataFrame, locked: list[str], *, n_boot: int, n_perm: int) -> dict:
    R: dict = {}
    y = labeled_set(tl)
    y_all = labeled_set(tl, include_exposed=True)
    exposed = set(tl.loc[tl["exposed"].astype(bool), "manc_type"])

    def a1():
        return load_arm(pred_dir, "A1", locked)

    _run("exposed_included", lambda: evaluate(a1()["primary_score"], y_all[y_all.index.isin(a1().index)], n_boot=n_boot, n_perm=n_perm), R)
    _run("exposed_only", lambda: evaluate(a1()["primary_score"], y_all[y_all.index.isin(a1().index) & y_all.index.isin(exposed)],
                                          n_boot=n_boot, n_perm=n_perm), R)

    def nu_excl():
        df = a1()
        ok = df[df["status"] == "ok"]
        return evaluate(ok["primary_score"], y[y.index.isin(ok.index)], n_boot=n_boot, n_perm=n_perm)
    _run("never_usable_excluded", nu_excl, R)
    for arm in ("B1", "B1-alt", "A1-lo10", "B2", "B5"):
        _run(arm, lambda arm=arm: (lambda df: evaluate(df["primary_score"], y[y.index.isin(df.index)], n_boot=n_boot, n_perm=n_perm))
             (load_arm(pred_dir, arm, locked)), R)

    def a1_b1():
        x, b = a1(), load_arm(pred_dir, "B1", locked)
        common = x.index.intersection(b.index)
        return {"n": int(len(common)), "spearman": ST.spearman(x.loc[common, "primary_score"], b.loc[common, "primary_score"])}
    _run("A1_vs_B1_spearman", a1_b1, R)
    for arm in ("A0", "B0"):
        for col in ("type_max", "type_mean"):
            _run(f"{arm}_{col}", lambda arm=arm, col=col: (lambda df: evaluate(pd.to_numeric(df[col], errors="coerce").fillna(0.0),
                                                                               y[y.index.isin(df.index)], n_boot=n_boot, n_perm=n_perm))
                 (load_arm(pred_dir, arm, locked)), R)

    def controls():
        names = sorted(a for a in locked if a.startswith("B1-ctl-"))
        if not names:
            raise NotLocked("B1-controls")
        aucs = {c: evaluate(load_arm(pred_dir, c, locked)["primary_score"], y, n_boot=200, n_perm=200).get("auroc") for c in names}
        v = [a for a in aucs.values() if a is not None]
        return {"per_control": aucs, "mean": float(np.mean(v)) if v else None, "min": min(v) if v else None, "max": max(v) if v else None}
    _run("controls", controls, R)

    def baselines():
        base = load_arm(pred_dir, "S", locked)
        return {b: evaluate(base[b].astype(float), y[y.index.isin(base.index)], n_boot=n_boot, n_perm=n_perm)
                for b in UNINFORMED_BASELINES + [INFORMED_BASELINE] if b in base}
    _run("baselines", baselines, R)
    recs = AGG.read_records(labels_dir / "records.jsonl")
    for name, flt in {"headless_only": lambda r: r["preparation"] == "headless",
                      "intact_only": lambda r: r["preparation"] in ("intact_free", "intact_tethered"),
                      "clean_lines": lambda r: r["line_specificity"] in ("clean", "minor_offtarget"),
                      "nonspecific_lines": lambda r: r["line_specificity"] in ("multi_dn", "unknown"),
                      "systematic_only": lambda r: r["source_type"] == "systematic_screen"}.items():
        def sub(flt=flt):
            ys = labeled_set(AGG.type_labels(recs, flt=flt, exposed=exposed))
            df = a1()
            return evaluate(df["primary_score"], ys[ys.index.isin(df.index)], n_boot=n_boot, n_perm=n_perm)
        _run(name, sub, R)

    def not_locked_b3():
        raise NotLocked("B3")

    def not_locked_b6():
        raise NotLocked("B6")
    _run("B3_pairs", not_locked_b3, R)
    _run("B6_legs_that_move", not_locked_b6, R)

    def b2_band():
        b1, b2 = load_arm(pred_dir, "B1", locked), load_arm(pred_dir, "B2", locked)
        common = b1.index.intersection(b2.index)
        dis = [t for t in common if b1.loc[t, "band"] != b2.loc[t, "band"]]
        return {"n_matched_types": int(len(common)), "n_band_disagreements": len(dis), "types_band_disagree": sorted(dis),
                "spearman": ST.spearman(b1.loc[common, "primary_score"], b2.loc[common, "primary_score"]) if len(common) > 2 else None}
    _run("B2_vs_B1_bands", b2_band, R)

    def frequency():
        b1 = load_arm(pred_dir, "B1", locked)
        t = tl.dropna(subset=["freq_hz"]).set_index("manc_type")
        f = pd.to_numeric(b1["median_freq_hz"], errors="coerce").dropna()
        common = [k for k in t.index if k in f.index and k not in exposed]
        return {"n": len(common), "spearman": ST.spearman(f.loc[common], t.loc[common, "freq_hz"]) if len(common) >= 3 else None,
                "definition": "B1 median frequency of rhythmic usable replicates vs the label-side median reported frequency"}
    _run("frequency", frequency, R)

    def b4_stop():
        b4 = load_arm(pred_dir, "B4", locked)
        t = tl.set_index("manc_type")
        cand = [k for k in b4.index if k in t.index and t.loc[k, "stop_call"] in ("stops", "no_stop") and k not in exposed]
        common = [k for k in cand if b4.loc[k, "call_128"] not in B4_NON_CALLS]
        pred = ["stops" if b4.loc[k, "call_128"] == "halts" else "no_stop" for k in common]
        true = [t.loc[k, "stop_call"] for k in common]
        return {"n": len(common), "n_excluded_non_calls": len(cand) - len(common),
                "raw_agreement": float(np.mean([p == q for p, q in zip(pred, true)])) if common else None,
                "kappa": ST.cohen_kappa(pred, true) if common else None,
                "confusion": pd.crosstab(pd.Series(pred, name="pred"), pd.Series(true, name="label")).to_dict() if common else {}}
    _run("B4_stop", b4_stop, R)

    def b4_mod():
        b4 = load_arm(pred_dir, "B4", locked)
        t = tl.set_index("manc_type")
        cmap = {"halts": "stops", "speeds_up": "speeds", "slows_down": "slows", "no_effect": "none"}
        labelled = [k for k in b4.index if k in t.index and k not in exposed]
        n_turns = sum(1 for k in labelled if t.loc[k, "walking_effect"] == "turns")
        cand = [k for k in labelled if t.loc[k, "walking_effect"] in ("stops", "slows", "speeds", "none")]
        common = [k for k in cand if b4.loc[k, "call_128"] in cmap]
        pred = [cmap[b4.loc[k, "call_128"]] for k in common]
        true = [t.loc[k, "walking_effect"] for k in common]
        return {"n": len(common), "n_excluded_non_calls": len(cand) - len(common), "n_label_turns_excluded": n_turns,
                "raw_agreement": float(np.mean([p == q for p, q in zip(pred, true)])) if common else None,
                "kappa": ST.cohen_kappa(pred, true) if common else None}
    _run("B4_modulation", b4_mod, R)

    def b5_strengths():
        b5 = load_arm(pred_dir, "B5", locked)
        return {c: evaluate(pd.to_numeric(b5[c], errors="coerce").fillna(0.0), y[y.index.isin(b5.index)], n_boot=n_boot, n_perm=n_perm)
                for c in sorted(b5.columns) if c.startswith("score_I")}
    _run("B5_per_strength", b5_strengths, R)
    return R


PREREGISTERED_SECONDARY = ["exposed_included", "exposed_only", "never_usable_excluded", "B1", "B1-alt", "A1-lo10", "B2", "B5",
                           "A1_vs_B1_spearman", "A0_type_max", "A0_type_mean", "B0_type_max", "B0_type_mean", "controls", "baselines",
                           "headless_only", "intact_only", "clean_lines", "nonspecific_lines", "systematic_only", "B3_pairs",
                           "B6_legs_that_move", "B2_vs_B1_bands", "frequency", "B4_stop", "B4_modulation", "B5_per_strength"]


def score_tables(pred_dir: Path, labels_dir: Path, research: Path, out: Path, *, n_boot: int = 10_000, n_perm: int = 10_000) -> dict:
    flag = require_unblind(research / "UNBLIND.json", research)
    ver = verify_inputs(flag, research, pred_dir, labels_dir)
    tl = check_type_labels(labels_dir, kit_exposed(research))
    out.mkdir(parents=True, exist_ok=True)
    res: dict = {"prereg": "research/ledger/PREREG.md v1", "unblind_flag": flag, "inputs": ver}
    try:
        res["primary"] = primary(pred_dir, tl, ver["arms_locked"], n_boot=n_boot, n_perm=n_perm)
    except Exception as e:  # noqa: BLE001
        res["primary"] = {"status": "error", "error": f"{type(e).__name__}: {e}"}
    (out / "score_primary.json").write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    res["analyses"] = secondary(pred_dir, labels_dir, tl, ver["arms_locked"], n_boot=n_boot, n_perm=n_perm)
    missing = [k for k in PREREGISTERED_SECONDARY if k not in res["analyses"]]
    if missing:
        res["analyses_missing_from_code"] = missing
    (out / "score.json").write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    return res


def run_scoring(out: Path, pred_dir: Path = PREDICTIONS, labels_dir: Path = LABELS, research: Path = RESEARCH) -> dict:
    return score_tables(pred_dir, labels_dir, research, out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    run_scoring(a.out)


if __name__ == "__main__":
    main()
