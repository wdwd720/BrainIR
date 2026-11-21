"""EXPLORATORY post-mortem of exam 1 (ledger run 2): recomputes every number in research/ledger/results/POSTMORTEM_1.md.

Not pre-registered. Written after the unblinding. It explains exam 1; it changes no rule, label, prediction or verdict.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/postmortem_1.py [--json OUT.json]

Pure analysis. The script writes nothing unless --json is given (put OUT.json outside the repository). It prints the
post-mortem's tables as markdown.

Inputs, all exam 1, every directory named explicitly:
- the locks LOCK_predictions_v1.json, LOCK_predictions_v2.json, LOCK_labels_v2.json and LOCK_labels_v1_1.json (every file
  read below is hashed against them first);
- predictions/<arm>/types.csv for the v1 arms, predictions/{A1,B1}/replicates.parquet, and
  predictions_v2/{B1r,B2r,B4v2}/types.csv;
- labels_v2/type_labels.csv and labels_v2/records.jsonl (record fields used: doi, preparation, source_type,
  front_leg_rhythm, manc_type and the frozen eligibility fields);
- labels_v1_1/type_labels.csv, for run S-a only;
- results/run2/{P,S-a,S-b,S-c}.json, used only for the equality check.

Frozen code, imported and never edited:
- brainir_ledger.scoring.pipeline: primary, secondary, evaluate and labeled_set;
- brainir_ledger.scoring.stats;
- brainir_ledger.labels.aggregate: type_labels and eligible;
- brainir_ledger.scoring_v2.pipeline_v2.analyses_s3.
The seeds are the frozen ones: bootstrap 20261120, permutation 20261121, paired 20261122, with 10,000 draws each.

The script first re-runs the four stored run-2 analyses (P, S-a, S-b, S-c) and stops if any number differs from
results/run2/*.json. Every subset AUROC goes through the frozen `evaluate` on A1's primary_score. Every label subset is the
frozen `type_labels` consensus recomputed from labels v2 records under a record filter, with the v2 exposed set taken from
the locked type table.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from brainir_ledger.labels import aggregate as AGG  # noqa: E402
from brainir_ledger.scoring import pipeline as PL  # noqa: E402
from brainir_ledger.scoring import stats as ST  # noqa: E402
from brainir_ledger.scoring_v2 import pipeline_v2 as P2  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
R = REPO / "research" / "ledger"
PRED1 = R / "predictions"
PRED2 = R / "predictions_v2"
LAB2 = R / "labels_v2"
LAB11 = R / "labels_v1_1"
RUN2 = R / "results" / "run2"
NB = NP = 10_000
ATLAS_DOI = "10.7554/elife.34275"  # Cande et al. 2018 optogenetic atlas, DOI as normalised in labels v2 (PREREG v2 L7)
BASELINES = PL.UNINFORMED_BASELINES + [PL.INFORMED_BASELINE]
OUT: dict = {}


# ----------------------------------------------------------------------------------------------------------- utilities
def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def jsonable(x):
    return json.loads(json.dumps(x, default=str))


def differences(a, b, path: str = "", out: list | None = None) -> list[str]:
    """Recursive equality; floats equal within 1e-12 and NaN == NaN."""
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: present on one side only")
            else:
                differences(a[k], b[k], f"{path}/{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: lengths {len(a)} and {len(b)}")
        else:
            for i, (u, v) in enumerate(zip(a, b)):
                differences(u, v, f"{path}[{i}]", out)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        fa, fb = float(a), float(b)
        if not ((math.isnan(fa) and math.isnan(fb)) or abs(fa - fb) <= 1e-12):
            out.append(f"{path}: {a} vs {b}")
    elif a != b:
        out.append(f"{path}: {a!r} vs {b!r}")
    return out


def underpowered(n: int, n_pos: int, n_neg: int) -> bool:
    """The pre-registered rule (PREREG v1 section 7, `stats.primary_decision`): fewer than 20 types or fewer than 5 per class."""
    return n < 20 or n_pos < 5 or n_neg < 5


def f3(x) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.3f}"


def auroc_row(name: str, r: dict) -> str:
    """One markdown row; "(u)" marks a row underpowered by the pre-registered rule. The permutation p of each row is kept in
    the --json output."""
    n, pos, neg = r["n"], r["n_pos"], r["n_neg"]
    if r.get("auroc") is None or (isinstance(r["auroc"], float) and math.isnan(r["auroc"])):
        return f"| {name} | {n} ({pos}/{neg}) | n/a | n/a |"
    b = r.get("boot") or {}
    ci = f"{f3(b.get('lo'))}-{f3(b.get('hi'))}" if b else "n/a"
    flag = " (u)" if underpowered(n, pos, neg) else ""
    return f"| {name} | {n} ({pos}/{neg}) | {f3(r['auroc'])}{flag} | {ci} |"


HEAD = "| analysis | n (yes/no) | AUROC | 95 % interval |\n|---|---|---|---|"


def yn(types, y: pd.Series) -> str:
    types = list(types)
    return f"{len(types)} ({int(sum(y[t] for t in types))}/{int(sum(1 - y[t] for t in types))})"


# ----------------------------------------------------------------------------------------------------------- 0. inputs
def verify_hashes() -> int:
    """Every file this script reads, against the exam-1 locks."""
    n = 0

    def check(rel: str, want: str) -> None:
        nonlocal n
        if sha(REPO / rel) != want:
            raise SystemExit(f"{rel} differs from its lock")
        n += 1
    p1 = json.loads((R / "LOCK_predictions_v1.json").read_text(encoding="utf-8"))
    for files in p1["arms_locked"].values():
        for rel, h in files.items():
            check(rel, h)
    p2 = json.loads((R / "LOCK_predictions_v2.json").read_text(encoding="utf-8"))
    check("research/ledger/LOCK_predictions_v1.json", p2["v1_locks"]["research/ledger/LOCK_predictions_v1.json"])
    for files in p2["arms_locked"].values():
        for rel, h in files.items():
            check(rel, h)
    l2 = json.loads((R / "LOCK_labels_v2.json").read_text(encoding="utf-8"))["labels"]
    for name in ("type_labels.csv", "records.jsonl"):
        check(f"research/ledger/labels_v2/{name}", l2[f"research/ledger/labels_v2/{name}"])
    l11 = json.loads((R / "LOCK_labels_v1_1.json").read_text(encoding="utf-8"))["labels"]
    check("research/ledger/labels_v1_1/type_labels.csv", l11["research/ledger/labels_v1_1/type_labels.csv"])
    return n


def reproduce_run2(tl: pd.DataFrame, locked: list[str]) -> dict:
    """The four stored run-2 analyses, recomputed with the frozen functions; any difference stops the script."""
    res = {"P": PL._clean(PL.primary(PRED1, tl, locked, n_boot=NB, n_perm=NP)),
           "S-a": PL._clean(PL.primary(PRED1, pd.read_csv(LAB11 / "type_labels.csv"), locked, n_boot=NB, n_perm=NP)),
           "S-b": PL.secondary(PRED1, LAB2, tl, locked, n_boot=NB, n_perm=NP)}
    p2 = json.loads((R / "LOCK_predictions_v2.json").read_text(encoding="utf-8"))
    ver = {"arms_locked": sorted(p2["arms_locked"]), "arms_not_locked": p2.get("arms_not_locked") or {}}
    res["S-c"] = P2.analyses_s3(R, PRED2, tl, ver, n_boot=NB, n_perm=NP)
    res = jsonable(res)
    stored = {k: json.loads((RUN2 / f"{k}.json").read_text(encoding="utf-8")) for k in ("P", "S-a", "S-b", "S-c")}
    diffs = (differences(res["P"], stored["P"]["primary"]["result"], "P")
             + differences(res["S-a"], stored["S-a"]["primary"]["result"], "S-a")
             + differences(res["S-b"], stored["S-b"]["analyses"], "S-b")
             + differences(res["S-c"], stored["S-c"]["analyses"], "S-c"))
    if diffs:
        raise SystemExit("recomputation differs from results/run2:\n" + "\n".join(diffs[:20]))
    return res


# ----------------------------------------------------------------------------------------------------------- 1. tables
def section1(run: dict) -> str:
    P, Sa, Sb, Sc = run["P"], run["S-a"], run["S-b"], run["S-c"]
    A = {k: v["result"] for k, v in Sb.items() if v.get("status") == "ok"}
    rows = [auroc_row("A1, primary set (P)", P)]
    for key, name in [("exposed_included", "exposed included"), ("exposed_only", "exposed only"),
                      ("never_usable_excluded", "never-usable excluded"), ("intact_only", "intact only"),
                      ("headless_only", "headless only"), ("systematic_only", "systematic sources only"),
                      ("clean_lines", "clean lines only"), ("nonspecific_lines", "non-specific lines")]:
        rows.append(auroc_row(f"A1, {name}", A[key]))
    rows.append(auroc_row("A1, labels v1.1 (S-a)", Sa))
    for key, name in [("A0_type_max", "A0 type max"), ("A0_type_mean", "A0 type mean"), ("B0_type_max", "B0 type max"),
                      ("B0_type_mean", "B0 type mean"), ("B1", "B1 (= B1-lo10)"), ("B1-alt", "B1-alt (= B1-lo5)"),
                      ("A1-lo10", "A1-lo10"), ("B2", "B2 (MaleCNS)"), ("B5", "B5 (max over strengths)")]:
        rows.append(auroc_row(name, A[key]))
    for arm in ("B1r", "B2r"):
        rows.append(auroc_row(f"{arm} (S-c)", Sc[arm]["result"]))
    for b in BASELINES:
        rows.append(auroc_row(b + (" (informed)" if b == PL.INFORMED_BASELINE else ""), A["baselines"][b]))
    ctl = A["controls"]
    vals = ", ".join(f"{c.replace('B1-ctl-', '')} {f3(v)}" for c, v in sorted(ctl["per_control"].items()))
    rows.append(f"| ten controls | 39 (25/14) | mean {f3(ctl['mean'])} | range {f3(ctl['min'])}-{f3(ctl['max'])} |")
    b5 = ", ".join(f"I = {k.split('_I')[1]} {f3(A['B5_per_strength'][k]['auroc'])}"
                   for k in ("score_I32", "score_I64", "score_I128", "score_I256", "score_I512"))
    # identical-arm check behind "B1 = B1-lo10" and "B1-alt = B1-lo5"
    def same_arm(a, b):
        x = pd.read_csv(PRED1 / a / "types.csv").drop(columns=["arm"])
        z = pd.read_csv(PRED1 / b / "types.csv").drop(columns=["arm"])
        return bool(x.equals(z))
    assert same_arm("B1", "B1-lo10") and same_arm("B1-alt", "B1-lo5"), "B1-lo10/B1-lo5 are not copies of B1/B1-alt"
    vb, vi = P["vs_best_baseline"], P["vs_informed"]
    b2b1, two, a1b1 = A["B2_vs_B1_bands"], Sc["B1r_vs_B2r"]["result"], A["A1_vs_B1_spearman"]
    s4, s4a, s4b, m4 = A["B4_stop"], Sc["B4v2_stop_lost_excluded"]["result"], Sc["B4v2_stop_lost_as_non_halts"]["result"], A["B4_modulation"]
    m4v2 = Sc["B4v2_modulation"]["result"]
    notes = [
        f"- Paired with the best wiring baseline ({P['best_baseline']}): A1 minus baseline {vb['diff']:.3f} "
        f"({vb['lo']:.3f} to {vb['hi']:.3f}); with S8_informed: {vi['diff']:.3f} ({vi['lo']:.3f} to {vi['hi']:.3f}). 39 types.",
        f"- Controls, one by one: {vals}.",
        f"- B5 per strength (39 types): {b5}.",
        f"- Agreement between arms (no labels): A1 against B1, Spearman {a1b1['spearman']:.3f} over {a1b1['n']} types. "
        f"B2 against B1: Spearman {b2b1['spearman']:.3f} and band disagreements {b2b1['n_band_disagreements']} over "
        f"{b2b1['n_matched_types']} types. B1r against B2r: Spearman {two['spearman']:.3f} over {two['n_common_types']} types, "
        f"top-10 overlap {two['top10_overlap']}, band agreement {two['band_agreement']:.3f}.",
        f"- Stop calls (raw agreement, kappa):",
        f"  - B4 v1: {s4['n']} types, {s4['raw_agreement']:.3f}, {s4['kappa']:.3f}.",
        f"  - B4 v2 with saturates and rhythm_lost_other excluded: {s4a['n']} types, {s4a['raw_agreement']:.3f}, "
        f"{s4a['kappa']:.3f}.",
        f"  - B4 v2 with both counted as non-halts: {s4b['n']} types, {s4b['raw_agreement']:.3f}, {s4b['kappa']:.3f}.",
        f"- Walking modulation: B4 v1 {m4['n']} types, kappa {m4['kappa']:.3f}; B4 v2 {m4v2['n']} types, kappa "
        f"{m4v2['kappa']:.3f}. Frequency: n = {A['frequency']['n']}.",
    ]
    OUT["section1"] = {"P": P, "S-a": Sa, "S-b": Sb, "S-c": Sc}
    return HEAD + "\n" + "\n".join(rows) + "\n\n" + "\n".join(notes)


# ----------------------------------------------------------------------------------------------------------- 2. zeros
def section2(y: pd.Series, a1: pd.DataFrame) -> str:
    rep = pd.read_parquet(PRED1 / "A1" / "replicates.parquet")
    b1rep = pd.read_parquet(PRED1 / "B1" / "replicates.parquet")
    b1 = pd.read_csv(PRED1 / "B1" / "types.csv").set_index("manc_type")
    b1r = pd.read_csv(PRED2 / "B1r" / "types.csv").set_index("manc_type")
    b5 = pd.read_csv(PRED1 / "B5" / "types.csv").set_index("manc_type")
    s = a1["primary_score"].reindex(y.index).astype(float)
    zero, nonzero = [t for t in y.index if s[t] == 0.0], [t for t in y.index if s[t] > 0.0]
    n_use = rep[rep.usable].groupby("manc_type").size().reindex(y.index).fillna(0).astype(int)
    never = [t for t in zero if n_use[t] == 0]
    uzero = [t for t in zero if n_use[t] > 0]
    assert all(a1.loc[t, "status"].startswith("never_usable") for t in never) and all(a1.loc[t, "status"] == "ok" for t in uzero)
    # every usable replicate of a usable-zero type scored exactly 0
    assert all((rep[(rep.manc_type == t) & rep.usable].score == 0).all() for t in uzero)
    med_act = {t: float(rep[(rep.manc_type == t) & rep.usable].n_active_notebook.median()) for t in uzero + nonzero}
    act_never = {t: (float(rep[rep.manc_type == t].n_active_notebook.min()), float(rep[rep.manc_type == t].n_active_notebook.max()))
                 for t in never}
    low = [t for t in uzero if med_act[t] <= 25]
    # B1 (BrainIR replication) records the read-out: active front-leg MNs in the accepted run
    b1_never, b1_silent, b1_active = [], [], []
    for t in uzero:
        u = b1rep[(b1rep.manc_type == t) & b1rep.usable]
        if len(u) == 0:
            b1_never.append(t)
        elif (u.n_active_readout.fillna(0) == 0).all():
            b1_silent.append(t)
        else:
            b1_active.append(t)
    b1_active_max = max(float(b1.loc[t, "primary_score"]) for t in b1_active)
    b1_never_a1 = {t: (float(rep[(rep.manc_type == t) & rep.usable].n_active_notebook.min()),
                       float(rep[(rep.manc_type == t) & rep.usable].n_active_notebook.max()), int(n_use[t])) for t in b1_never}
    readout = {arm: json.loads((PRED1 / arm / "config.json").read_text(encoding="utf-8"))["readout"] for arm in ("A1", "B1")}
    b1_active_reps = {t: (int((b1rep[(b1rep.manc_type == t) & b1rep.usable].n_active_readout > 0).sum()),
                          int(((b1rep.manc_type == t) & b1rep.usable).sum())) for t in b1_active}
    # reachability arms
    r_never = [t for t in zero if b1r.loc[t, "status"].startswith("never_usable")]
    r_pos = [t for t in zero if b1r.loc[t, "status"] == "ok" and b1r.loc[t, "primary_score"] > 0]
    r_zero = [t for t in zero if b1r.loc[t, "status"] == "ok" and b1r.loc[t, "primary_score"] == 0]
    strengths = ["score_I32", "score_I64", "score_I128", "score_I256", "score_I512"]
    b5_allzero = [t for t in zero if (b5.loc[t, strengths].astype(float) == 0).all()]
    b1r_zero_primary = [t for t in y.index if t in b1r.index and float(b1r.loc[t, "primary_score"]) == 0]
    # exact decomposition of the tie-averaged AUROC (Mann-Whitney)
    yz = [t for t in zero if y[t] == 1]
    nz_ = [t for t in zero if y[t] == 0]
    ynz = [t for t in nonzero if y[t] == 1]
    nnz = [t for t in nonzero if y[t] == 0]
    wins_nz = sum((s[a] > s[b]) + 0.5 * (s[a] == s[b]) for a in ynz for b in nnz)
    total = len(ynz) * len(nz_) + 0.5 * len(yz) * len(nz_) + wins_nz
    pairs = int(y.sum()) * int((1 - y).sum())
    assert abs(total / pairs - ST.auroc(s.to_numpy(), y.to_numpy())) < 1e-12
    nz_eval = PL._clean(PL.evaluate(a1["primary_score"], y[nonzero], n_boot=NB, n_perm=NP))
    OUT["section2"] = dict(zero=zero, never=never, usable_zero=uzero, median_nactive=med_act, nactive_never=act_never,
                           le25=low, b1_never=b1_never, b1_silent=b1_silent, b1_active=b1_active, b1_active_reps=b1_active_reps,
                           b1r_never=r_never, b1r_pos=r_pos, b1r_zero=r_zero, b5_allzero=b5_allzero, nonzero_eval=nz_eval,
                           b1r_zero_primary=b1r_zero_primary)
    med = lambda ts: float(np.median([med_act[t] for t in ts]))  # noqa: E731
    rng = lambda ts: f"{min(med_act[t] for t in ts):g}-{max(med_act[t] for t in ts):g}"  # noqa: E731
    lo_never = min(a for a, _ in act_never.values())
    hi_never = max(b for _, b in act_never.values())
    lines = [
        "| A1 score (primary set) | types (yes/no) | active neurons per usable replicate: median of type medians (range) |",
        "|---|---|---|",
        f"| above 0 | {yn(nonzero, y)} | {med(nonzero):g} ({rng(nonzero)}) |",
        f"| 0, never usable | {yn(never, y)} | no usable replicate ({lo_never:g}-{hi_never:g} active) |",
        f"| 0, usable | {yn(uzero, y)} | {med(uzero):g} ({rng(uzero)}); at most 25 in {yn(low, y)} |",
        "",
        f"- Read-out (locked configs): A1 {readout['A1']!r}; B1 {readout['B1']!r}.",
        f"- Usable-zero types in B1, the replication, which also records read-out counts ({yn(uzero, y)}):",
        f"  - never usable in B1: {yn(b1_never, y)} ("
        + ", ".join(f"{t}: A1 usable replicates {k}, active neurons {a:g}-{b:g}" for t, (a, b, k) in b1_never_a1.items()) + ");",
        f"  - read-out silent, i.e. no active front-leg MN in any usable replicate: {yn(b1_silent, y)};",
        f"  - read-out active in at least one usable replicate but not rhythmic (B1 score at most {b1_active_max:.4f}): "
        f"{yn(b1_active, y)}.",
        f"- The 25 A1-zero types in the arms built for reachability:",
        f"  - B1r (tuner v2, at least 1 active front-leg MN): never usable {yn(r_never, y)} ({', '.join(r_never)}); "
        f"usable at 0 {yn(r_zero, y)}; above 0 {yn(r_pos, y)}.",
        f"  - B5 (fixed currents 32 to 512, no tuner): exactly 0 at all five currents {yn(b5_allzero, y)}.",
        f"- B1r gives exactly 0 to {yn(b1r_zero_primary, y)} of the 39 primary-set types.",
        f"- AUROC decomposition over the {pairs} yes-no pairs:",
        f"  - non-zero yes above zero no: {len(ynz)} x {len(nz_)} = {len(ynz) * len(nz_)} pairs won;",
        f"  - zero yes below non-zero no: {len(yz)} x {len(nnz)} = {len(yz) * len(nnz)} pairs lost;",
        f"  - zero against zero: {len(yz)} x {len(nz_)} = {len(yz) * len(nz_)} ties, credited {0.5 * len(yz) * len(nz_):g};",
        f"  - non-zero against non-zero: {wins_nz:g} of {len(ynz) * len(nnz)} won.",
        f"  - AUROC = ({len(ynz) * len(nz_)} + {0.5 * len(yz) * len(nz_):g} + {wins_nz:g}) / {pairs} = {total / pairs:.4f}.",
        f"- Non-zero types only: {auroc_row('A1', nz_eval)}",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------------------------- 3. sources
def section3(y: pd.Series, a1: pd.DataFrame, tl: pd.DataFrame, recs: list[dict]) -> str:
    exposed = set(tl.loc[tl["exposed"].astype(bool), "manc_type"])
    el = [r for r in recs if AGG.eligible(r)]
    atlas_alone = {t for t in y.index if all(r["doi"] == ATLAS_DOI for r in el if r["manc_type"] == t)}

    def labels(flt, incl_exposed=False) -> pd.Series:
        ys = PL.labeled_set(AGG.type_labels(recs, flt=flt, exposed=exposed), include_exposed=incl_exposed)
        return ys[ys.index.isin(a1.index)]

    def ev(ys):
        return PL._clean(PL.evaluate(a1["primary_score"], ys, n_boot=NB, n_perm=NP))
    is_atlas = lambda r: r["doi"] == ATLAS_DOI  # noqa: E731
    intact = lambda r: r["preparation"] in ("intact_free", "intact_tethered")  # noqa: E731
    subsets = [
        ("primary set, all records", y),
        ("types not labelled from the atlas alone", y[~y.index.isin(atlas_alone)]),
        ("atlas records removed", labels(lambda r: not is_atlas(r))),
        ("atlas records only", labels(is_atlas)),
        ("targeted studies only", labels(lambda r: r["source_type"] == "targeted_study")),
        ("other systematic screens only", labels(lambda r: r["source_type"] == "systematic_screen" and not is_atlas(r))),
        ("headless records only", labels(lambda r: r["preparation"] == "headless")),
        ("intact records only", labels(intact)),
        ("intact, atlas removed", labels(lambda r: intact(r) and not is_atlas(r))),
        ("atlas removed, exposed included", labels(lambda r: not is_atlas(r), True)),
        ("headless only, exposed included", labels(lambda r: r["preparation"] == "headless", True)),
    ]
    rows, res = [], {}
    score = a1["primary_score"].astype(float)
    for name, ys in subsets:
        r = ev(ys)
        nz_yes = sum(1 for t in ys.index if ys[t] == 1 and score[t] > 0)
        nz_no = sum(1 for t in ys.index if ys[t] == 0 and score[t] > 0)
        res[name] = {"eval": r, "yes": sorted(ys.index[ys == 1]), "no": sorted(ys.index[ys == 0]),
                     "nonzero_A1_yes": nz_yes, "nonzero_A1_no": nz_no}
        rows.append(auroc_row(name, r) + f" {nz_yes}/{nz_no} |")

    def change(ys: pd.Series) -> str:
        common = [t for t in ys.index if t in y.index]
        to_no = [t for t in common if y[t] == 1 and ys[t] == 0]
        to_yes = [t for t in common if y[t] == 0 and ys[t] == 1]
        gone = [t for t in y.index if t not in ys.index]
        new = [t for t in ys.index if t not in y.index]
        return (f"yes->no {to_no or 'none'}, no->yes {to_yes or 'none'}, dropped {yn(gone, y)}"
                + (f" {sorted(gone)}" if len(gone) <= 5 else "") + (f", added {sorted(new)}" if new else ""))
    rec_atlas = pd.Series([r["front_leg_rhythm"] for r in el if is_atlas(r)]).value_counts().to_dict()
    rec_other = pd.Series([r["front_leg_rhythm"] for r in el if not is_atlas(r)]).value_counts().to_dict()
    at = AGG.type_labels(recs, flt=is_atlas, exposed=exposed).set_index("manc_type")
    no_types = [t for t in y.index if y[t] == 0]
    atlas_on_no = {t: (at.loc[t, "front"] if t in at.index else "no atlas record") for t in no_types}
    counts = pd.Series(list(atlas_on_no.values())).value_counts().to_dict()
    OUT["section3"] = dict(subsets=res, atlas_alone=sorted(atlas_alone), eligible_atlas_front=rec_atlas,
                           eligible_other_front=rec_other, atlas_consensus_on_no_types=atlas_on_no)
    head3 = HEAD.replace("| 95 % interval |\n", "| 95 % interval | A1 > 0 (yes/no) |\n").replace("|---|---|---|---|",
                                                                                            "|---|---|---|---|---|")
    groups: dict[str, list[str]] = {}
    for t, v in atlas_on_no.items():
        groups.setdefault(v, []).append(t)
    nz_yes_all = [t for t in y.index if y[t] == 1 and score[t] > 0]
    yes_alone = [t for t in y.index if y[t] == 1 and t in atlas_alone]
    yes_other = [t for t in y.index if y[t] == 1 and t not in atlas_alone]
    no_all = [t for t in y.index if y[t] == 0]
    nz = lambda ts: sum(1 for t in ts if score[t] > 0)  # noqa: E731
    lines = [head3, *rows, "",
             f"- Types labelled from the atlas alone: {yn(sorted(atlas_alone), y)}. Non-zero yes types labelled from the atlas "
             f"alone: {sum(t in atlas_alone for t in nz_yes_all)} of {len(nz_yes_all)}.",
             f"- A1 > 0 for {nz(yes_alone)} of the {len(yes_alone)} atlas-alone yes types, {nz(yes_other)} of the {len(yes_other)} "
             f"other-source yes types and {nz(no_all)} of the {len(no_all)} no types.",
             f"- Eligible atlas records ({sum(rec_atlas.values())}), front-leg field: {rec_atlas}.",
             f"- Eligible records from other papers ({sum(rec_other.values())}): {rec_other}.",
             f"- Atlas-only consensus for the 14 'no' types: {counts}; "
             + "; ".join(f"{k}: {', '.join(v)}" for k, v in sorted(groups.items())) + ".",
             f"- Atlas removed against the primary set: {change(labels(lambda r: not is_atlas(r)))}.",
             f"- Intact only against the primary set: {change(labels(intact))}.",
             f"- Headless only against the primary set: {change(labels(lambda r: r['preparation'] == 'headless'))}."]
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------------------------- 4. wiring
def section4(y: pd.Series, a1: pd.DataFrame, recs: list[dict]) -> str:
    S = pd.read_csv(PRED1 / "S" / "types.csv").set_index("manc_type")
    cols = BASELINES
    Sp = S.loc[y.index, cols].astype(float)
    yy = y.to_numpy()
    s2, s3 = Sp["S2_twohop_signed"].to_numpy(), Sp["S3_twohop_abs"].to_numpy()
    rho39 = {c: ST.spearman(Sp["S2_twohop_signed"], Sp[c]) for c in cols if c != "S2_twohop_signed"}
    Sall = S[cols].astype(float)
    rho321 = {c: ST.spearman(Sall["S2_twohop_signed"], Sall[c]) for c in cols if c != "S2_twohop_signed"}
    a1s = a1["primary_score"].reindex(y.index).astype(float)
    rho_a1 = {"S2_twohop_signed": ST.spearman(a1s, Sp["S2_twohop_signed"]), "S7_n_members": ST.spearman(a1s, Sp["S7_n_members"])}
    ratio = np.where(s3 > 0, s2 / np.where(s3 > 0, s3, 1.0), 0.0)
    mag_auc = {c: ST.auroc(Sp[c].to_numpy(), yy) for c in ("S3_twohop_abs", "S4_total_out", "S5_out_partners", "S6_premotor")}
    auc = {"S2": ST.auroc(s2, yy), "sign(S2)": ST.auroc(np.sign(s2), yy), "S2/S3": ST.auroc(ratio, yy)}
    grp = {}
    for lab, name in ((1, "yes"), (0, "no")):
        m = yy == lab
        grp[name] = {"n": int(m.sum()), "S2>0": int((s2[m] > 0).sum()), "S2=0": int((s2[m] == 0).sum()), "S2<0": int((s2[m] < 0).sum()),
                     "median S2": float(np.median(s2[m])), "median |S2|": float(np.median(np.abs(s2[m]))),
                     "median S3": float(np.median(s3[m])), "median S4": float(np.median(Sp["S4_total_out"][m])),
                     "median S7": float(np.median(Sp["S7_n_members"][m]))}
    # per-type influence on S2's AUROC
    base = ST.auroc(s2, yy)
    infl = []
    for i, t in enumerate(y.index):
        keep = np.arange(len(yy)) != i
        other = s2[yy != yy[i]]
        share = (np.mean(s2[i] > other) + 0.5 * np.mean(s2[i] == other)) if yy[i] == 1 else (np.mean(other > s2[i]) + 0.5 * np.mean(other == s2[i]))
        infl.append({"type": t, "label": "yes" if yy[i] else "no", "S2": float(s2[i]), "share": float(share),
                     "loo_auroc": ST.auroc(s2[keep], yy[keep]), "delta": ST.auroc(s2[keep], yy[keep]) - base})
    infl = sorted(infl, key=lambda d: d["S2"])
    neg_no = [d for d in infl if d["label"] == "no" and d["S2"] < 0]
    pos_no = [d for d in infl if d["label"] == "no" and d["S2"] > 0]
    neg_yes_strong = [d for d in infl if d["label"] == "yes" and d["share"] < 0.5]
    # does magnitude track source as well as label?
    el = [r for r in recs if AGG.eligible(r)]
    atlas_alone = {t for t in y.index if all(r["doi"] == ATLAS_DOI for r in el if r["manc_type"] == t)}
    other_src = [t for t in y.index if t not in atlas_alone]
    src = np.array([0 if t in atlas_alone else 1 for t in y.index])
    med_s3 = {"atlas-alone yes": float(np.median(S.loc[sorted(atlas_alone), "S3_twohop_abs"])),
              "other-source yes": float(np.median(S.loc[[t for t in other_src if y[t] == 1], "S3_twohop_abs"])),
              "other-source no": float(np.median(S.loc[[t for t in other_src if y[t] == 0], "S3_twohop_abs"]))}
    yo = y[other_src].to_numpy()
    within = {c: ST.auroc(S.loc[other_src, c].astype(float).to_numpy(), yo)
              for c in ("S2_twohop_signed", "S3_twohop_abs", "S4_total_out", "S7_n_members")}
    s3_source = ST.auroc(s3, src)
    yes_t = [t for t in y.index if y[t] == 1]
    s3_source_yes = ST.auroc(S.loc[yes_t, "S3_twohop_abs"].astype(float).to_numpy(), np.array([0 if t in atlas_alone else 1 for t in yes_t]))
    multi = [t for t in y.index if float(S.loc[t, "S7_n_members"]) > 2]
    multi_atlas = [t for t in multi if t in atlas_alone]
    OUT["section4"] = dict(spearman_S2_primary=rho39, spearman_S2_all321=rho321, spearman_A1=rho_a1, auroc=auc, groups=grp,
                           influence=infl, median_S3_by_source=med_s3, within_other_source=within, S3_separates_source=s3_source,
                           S3_source_within_yes=s3_source_yes,
                           more_than_2_members=multi, more_than_2_members_atlas_alone=multi_atlas)
    short = lambda c: c.split("_")[0]  # noqa: E731
    g = grp
    lines = [
        "| Spearman of S2 with | " + " | ".join(short(c) for c in rho39) + " |",
        "|---|" + "---|" * len(rho39),
        "| 39 primary-set types | " + " | ".join(f"{v:.3f}" for v in rho39.values()) + " |",
        "| all 321 types | " + " | ".join(f"{v:.3f}" for v in rho321.values()) + " |",
        "",
        "| primary set | S2 > 0 / = 0 / < 0 | median S2 | median abs(S2) | median S3 | median S4 | median S7 (members) |",
        "|---|---|---|---|---|---|---|",
        *[f"| {k} ({v['n']}) | {v['S2>0']} / {v['S2=0']} / {v['S2<0']} | {v['median S2']:,.0f} | {v['median |S2|']:,.0f} | "
          f"{v['median S3']:,.0f} | {v['median S4']:,.0f} | {v['median S7']:g} |" for k, v in g.items()],
        "",
        f"- AUROC (39 types): S2 {auc['S2']:.3f}, sign(S2) alone {auc['sign(S2)']:.3f}, and S2/S3, the net sign balance with "
        f"magnitude divided out, {auc['S2/S3']:.3f}.",
        f"- Median ratio no/yes: S3 {g['no']['median S3'] / g['yes']['median S3']:.1f}x, S4 {g['no']['median S4'] / g['yes']['median S4']:.1f}x. "
        f"AUROC range of S3-S6: {min(mag_auc.values()):.3f}-{max(mag_auc.values()):.3f}.",
        f"- Spearman of A1 with S2 {rho_a1['S2_twohop_signed']:.3f}; with S7 {rho_a1['S7_n_members']:.3f}. 39 types.",
        f"- 'No' types with S2 < 0 ({len(neg_no)}) and the share of the 25 yes types above each:",
        f"  {', '.join(f'{d['type']} {d['share']:.2f}' for d in neg_no)}.",
        f"- 'No' types with S2 > 0 ({len(pos_no)}) and the same share: {', '.join(f'{d['type']} {d['share']:.2f}' for d in pos_no)} "
        f"(i.e. above {', '.join(f'{100 * (1 - d['share']):.0f} %' for d in pos_no)} of the yes types).",
        f"- Yes types below most no types (share of no types below them): "
        f"{', '.join(f'{d['type']} {d['share']:.2f}' for d in neg_yes_strong)} "
        f"(i.e. below {', '.join(f'{100 * (1 - d['share']):.0f} %' for d in neg_yes_strong)} of the no types).",
        f"- Leave-one-out AUROC of S2 runs from {min(d['loo_auroc'] for d in infl):.3f} to {max(d['loo_auroc'] for d in infl):.3f}.",
        f"  - Largest rises: {', '.join(d['type'] for d in infl if abs(d['delta'] - max(e['delta'] for e in infl)) < 1e-12)}.",
        f"  - Largest falls: {', '.join(d['type'] for d in infl if abs(d['delta'] - min(e['delta'] for e in infl)) < 1e-12)}.",
        f"- Median S3 by source and label: {', '.join(f'{k} {v:,.0f}' for k, v in med_s3.items())}.",
        f"- S3 separates other-source from atlas-alone types with AUROC {s3_source:.3f} ({len(other_src)} against {len(atlas_alone)}); "
        f"among yes types only, {s3_source_yes:.3f} ({sum(1 for t in yes_t if t not in atlas_alone)} other-source against "
        f"{sum(1 for t in yes_t if t in atlas_alone)} atlas-alone).",
        f"- Within the {yn(other_src, y)} other-source types, yes against no: "
        f"{', '.join(f'{short(k)} {v:.3f}' for k, v in within.items())} (underpowered).",
        f"- Types with more than 2 members: {yn(multi, y)}; {len(multi_atlas)} of them are labelled from the atlas alone "
        f"({', '.join(f'{t} {int(S.loc[t, 'S7_n_members'])}' for t in multi)}).",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", type=Path, help="also write every number to this JSON file (outside the repository)")
    a = ap.parse_args()
    n_files = verify_hashes()
    tl = pd.read_csv(LAB2 / "type_labels.csv")
    exposed = set(tl.loc[tl["exposed"].astype(bool), "manc_type"])
    PL.check_type_labels(LAB2, exposed)  # the consensus path used in section 3 reproduces the locked type table
    locked = sorted(json.loads((R / "LOCK_predictions_v1.json").read_text(encoding="utf-8"))["arms_locked"])
    run = reproduce_run2(tl, locked)
    a1 = pd.read_csv(PRED1 / "A1" / "types.csv").set_index("manc_type", drop=False)
    y = PL.labeled_set(tl)
    y = y[y.index.isin(a1.index)]
    recs = AGG.read_records(LAB2 / "records.jsonl")
    print(f"EXPLORATORY post-mortem of exam 1. Inputs: {n_files} files match their locks; runs P, S-a, S-b and S-c recomputed "
          f"with the frozen code equal results/run2 exactly. Primary set {yn(y.index, y)}.\n")
    for title, body in (("1. Secondary tables", section1(run)), ("2. Zeros", section2(y, a1)),
                        ("3. Source confound", section3(y, a1, tl, recs)), ("4. Wiring", section4(y, a1, recs))):
        print(f"## EXPLORATORY {title}\n\n{body}\n")
    if a.json:
        a.json.write_text(json.dumps(jsonable(OUT), indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
