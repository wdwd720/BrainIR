"""Exam 2 pipeline (PREREG v3 S2-S7): refuses unless the h1 flag, the gate's second run and the locks all check out; then runs
the primary analysis (`primary`) or the secondary analyses (`secondary`), each once, and writes `results/run3/<run>.json`.

Flag `research/ledger/UNBLIND_h1.json` (exam 1's flag is retired and never read):
    {"authorised_by": "...", "utc": "...", "predictions_lock": "LOCK_predictions_h1.json", "predictions_lock_sha256": "...",
     "labels_lock": "LOCK_labels_h1.json", "labels_lock_sha256": "..."}
Locks: `LOCK_predictions_h1.json` section `arms_locked` -> {arm: {repo path: sha256}}; `LOCK_labels_h1.json` section `labels`
-> {repo path: sha256}.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from . import (DIMS, BlindErrorH1, bootstrap_ci, decide, identification, lab_as_prediction, observed, paired_bootstrap,
               per_dim_auroc, permutation_p, standardise)

RUNS = ("primary", "secondary")
HS_ARMS = ["H-S-k0"] + [f"H-S-k{k}-{s}" for k in (1, 2, 3) for s in ("signed", "unsigned")]  # PREREG v3 P3
HD_ARMS = [f"H-D-{c}" for c in (128, 256, 384, 512)]
HC_ARMS = [f"H-C-rewire-{s}" for s in (101, 102, 103, 104, 105)] + [f"H-C-classshuffle-{s}" for s in (201, 202, 203, 204, 205)]
SENS_ARMS = [f"H-M-S-{g}" for g in ("all", "post", "T1", "T2", "T3", "L", "R")]
MATCHED = "H-M-s0-3"  # H-M from seeds 0..3 only: the comparator of the four-seed arms (H-C, sensitivity groups; PREREG v3 S4.5)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def preconditions(research: Path, flag_path: Path) -> dict:
    if not flag_path.exists():
        raise BlindErrorH1("no UNBLIND_h1.json: exam 2 is not unblinded")
    flag = json.loads(flag_path.read_text())
    gate = research / "gates_v3" / "UNBLINDING_GATE_h1_run2.json"
    if not gate.exists() or not json.loads(gate.read_text()).get("all_conditions_hold"):
        raise BlindErrorH1("the gate's second run does not report that all conditions hold")
    locks = {}
    for k in ("predictions", "labels"):
        name = flag.get(f"{k}_lock")
        lp = research / str(name)
        if name not in (f"LOCK_{k}_h1.json",) or not lp.exists() or _sha(lp) != flag.get(f"{k}_lock_sha256"):
            raise BlindErrorH1(f"flag names a wrong or changed {k} lock")
        locks[k] = json.loads(lp.read_text())
    return {"flag": flag, "locks": locks, "gate_sha256": _sha(gate)}


def _read_locked(repo: Path, rel: str, section: dict) -> pd.DataFrame:
    p = repo / rel
    if rel not in section or not p.exists() or _sha(p) != section[rel]:
        raise BlindErrorH1(f"{rel} is not the locked file")
    return pd.read_csv(p, dtype={"unit": str})


def _pred(repo: Path, locks: dict, arm: str, units: list[str]) -> pd.DataFrame | None:
    """A locked arm's standardised predictions; its table must hold exactly the unit list (no silent filling: PREREG v3 S7)."""
    sec = (locks["predictions"].get("arms_locked") or {}).get(arm)
    if sec is None:
        return None
    P = _read_locked(repo, f"research/ledger/predictions_h1/{arm}/predicted.csv", sec).set_index("unit")
    if sorted(P.index) != sorted(units) or P.index.duplicated().any():
        raise BlindErrorH1(f"{arm}: predicted.csv does not hold exactly the {len(units)} units")
    if P[DIMS].isna().any().any():
        raise BlindErrorH1(f"{arm}: missing predicted values")
    return standardise(P.loc[units])


def _cons(repo: Path, locks: dict, rel: str, units: list[str]) -> pd.DataFrame:
    """A locked consensus table. `d7p` is derived per final record before the consensus (PREREG v3 V2), so it must be present;
    every unit named must be in the unit list (a label for an unknown name is an assembly error, never dropped here)."""
    c = _read_locked(repo, rel, locks["labels"].get("labels") or {}).set_index("unit")
    missing = [d for d in DIMS if d not in c.columns]
    if missing:
        raise BlindErrorH1(f"{rel}: columns missing {missing}")
    unknown = sorted(set(c.index) - set(units))
    if unknown or c.index.duplicated().any():
        raise BlindErrorH1(f"{rel}: units not in the unit list or repeated: {unknown}")
    bad = set(c[DIMS].stack().unique()) - {"yes", "no", "unclear", "not_assessed", "conflicting"}
    if bad:
        raise BlindErrorH1(f"{rel}: values outside the cell vocabulary: {sorted(bad)}")
    return c.reindex(units)


def _ident(Z, O) -> dict:
    r = identification(Z, O)
    return {k: v for k, v in r.items() if not k.startswith("_")}


def run(name: str, research: Path, flag_path: Path) -> dict:
    if name not in RUNS:
        raise BlindErrorH1(f"unknown run {name}")
    research = Path(research)
    repo = research.parents[1]
    out_p = research / "results" / "run3" / f"{name}.json"
    if out_p.exists():
        raise BlindErrorH1(f"results/run3/{name}.json exists (each run once)")
    pre = preconditions(research, flag_path)
    locks = pre["locks"]
    units = pd.read_csv(research / "hl_units" / "UNITS_v1.csv", dtype={"unit": str})
    U = units["unit"].tolist()
    cons = _cons(repo, locks, "research/ledger/labels_h1/consensus.csv", U)
    O = observed(cons)
    n_ge3 = int((O.notna().sum(axis=1) >= 3).sum())
    res: dict = {"run": name, "flag": pre["flag"], "gate_sha256": pre["gate_sha256"], "n_units": len(U), "n_units_ge3_coded": n_ge3}
    ZM = _pred(repo, locks, "H-M", U)
    if ZM is None:
        raise BlindErrorH1("H-M is not locked")
    if name == "primary":
        r = identification(ZM, O)
        p = permutation_p(r) if r["n"] else None
        ci = bootstrap_ci(r["pr"].values()) if r["n"] else None
        hs = {}
        for arm in HS_ARMS:
            Z = _pred(repo, locks, arm, U)
            if Z is not None:
                hs[arm] = identification(Z, O)
        best = max(hs, key=lambda a: hs[a]["mean_pr"] or -1) if hs else None
        vs = paired_bootstrap(r["pr"], hs[best]["pr"]) if best and r["n"] else None
        res.update({"H-M": {k: v for k, v in r.items() if not k.startswith("_")}, "p": p, "ci": ci,
                    "H-S": {a: {k: v for k, v in x.items() if not k.startswith("_")} for a, x in hs.items()},
                    "best_H-S": best, "vs_best_H-S": vs, "decision": decide(r, p if p is not None else 1.0, ci or {"lo": 0}, n_ge3, vs)})
    else:
        sec: dict = {}
        labs = sorted(r for r in (locks["labels"].get("labels") or {}) if r.startswith("research/ledger/labels_h1/lab_"))
        lab_O = {Path(r).stem: observed(_cons(repo, locks, r, U)) for r in labs}
        sec["each_lab"] = {lab: _ident(ZM, Ol) for lab, Ol in lab_O.items()}
        sec["ceiling"] = {}
        for a in lab_O:
            for b in lab_O:
                if a != b:
                    both = [u for u in U if lab_O[a].loc[u].notna().sum() >= 3 and lab_O[b].loc[u].notna().sum() >= 3]
                    sec["ceiling"][f"{a}->{b}"] = _ident(lab_as_prediction(lab_O[a], U), lab_O[b].loc[both]) if both else {"n": 0}
        sec["per_dim_auroc"] = per_dim_auroc(ZM, O)
        cls = units.set_index("unit")["nt_class"]
        sec["by_class"] = {c: _ident(ZM, O.loc[[u for u in U if cls[u] == c]]) for c in sorted(cls.unique())}
        for group in ([MATCHED], HD_ARMS, HC_ARMS, SENS_ARMS, HS_ARMS):
            for arm in group:
                Z = _pred(repo, locks, arm, U)
                sec[arm] = _ident(Z, O) if Z is not None else {"status": "not_locked"}
        rel2 = "research/ledger/labels_h1/consensus_secondary.csv"
        if rel2 in (locks["labels"].get("labels") or {}):
            sec["secondary_record_types"] = _ident(ZM, observed(_cons(repo, locks, rel2, U)))
        res["secondary"] = sec
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    return res
