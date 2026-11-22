"""The forward ledger (PREREG v4 Part E): calibrated predictions for experiments not yet done.

Labels are used for one thing only (RUN4_PROMPT hard limit 4): the one-variable logistic fit that turns each source's score into a
probability of rhythmic front-leg stepping (E3) — training on past results to predict future ones, stated as such in the outputs.

    uv run --project ledger --no-sync python ledger/scripts/forward_v1.py build [--robust FIX]   # -> research/ledger/forward/*
    uv run --project ledger --no-sync python ledger/scripts/forward_v1.py decisive                 # -> forward/DECISIVE.csv (+ availability)

Outputs are written once (mode "x").
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))
import gha4  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import agree as AG  # noqa: E402
from brainir_ledger import mirror as MR  # noqa: E402
from brainir_ledger import pooled  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402
from brainir_ledger.scoring import stats as ST  # noqa: E402
from brainir_ledger.scoring_v2.pipeline_v2 import exposed_set_v2  # noqa: E402

FWD = RESEARCH / "forward"
P1, P2 = RESEARCH / "predictions", RESEARCH / "predictions_v2"
HONESTY = ("These predictions are made after both exams were unblinded. They are clean with respect to the experiments they predict, "
           "because those have not been done.")
TRAINING = ("Probabilities come from a one-variable logistic fit of exam 1's labels on each source's score: training on past results to "
            "predict future ones (RUN4_PROMPT hard limit 4).")
ATLAS = ("Atlas caveat: 21 of exam 1's 25 'yes' types rest on the intact-fly atlas alone, and the atlas gives no 'no'; the fit inherits "
         "that confound.")
PROTOCOL = ["Cross the driver line to UAS-CsChrimson; raise adults on food with 0.4 mM all-trans-retinal for 3-5 days, in the dark.",
            "Decapitate the fly under cold anaesthesia and let it recover for 5-10 min, tethered or free on a flat surface.",
            "Deliver 1 s pulses of 617 nm light (several intensities), at least 10 pulses per fly, at least 8 flies per genotype.",
            "Record the front legs at >= 100 frames/s; score each pulse for rhythmic front-leg stepping blind to genotype.",
            "Controls: the empty split-GAL4 crossed to UAS-CsChrimson, and flies of the same cross raised without retinal."]


def _out(name: str, text: str) -> None:
    FWD.mkdir(parents=True, exist_ok=True)
    with open(FWD / name, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote forward/" + name, flush=True)


# ----------------------------------------------------------------------------------------------------------------- inputs
def a1_types() -> pd.Series:
    t = pd.read_csv(P1 / "A1" / "types.csv").set_index("manc_type")["primary_score"].astype(float)
    if len(t) != 321:
        raise SystemExit("A1 must have 321 types")
    return t


def s2_scores() -> pd.Series:
    return pd.read_csv(P1 / "S" / "types.csv").set_index("manc_type")["S2_twohop_signed"].astype(float)


def labels_v2() -> pd.DataFrame:
    return pd.read_csv(RESEARCH / "labels_v2" / "type_labels.csv", dtype={"manc_type": str})


def primary_set() -> pd.Series:
    """Run 2's primary set (RESULTS_1): clear front-leg label, among A1's 321, not in the v2 exposed set. 1 = yes."""
    tl = labels_v2()
    ex = exposed_set_v2(RESEARCH)
    a1 = set(a1_types().index)
    t = tl[tl["front"].isin(["yes", "no"]) & tl["manc_type"].isin(a1) & ~tl["manc_type"].isin(ex)]
    return pd.Series((t["front"] == "yes").astype(int).to_numpy(), index=t["manc_type"].to_numpy())


def headless_set() -> pd.Series:
    tl = labels_v2().set_index("manc_type")
    y = primary_set()
    return y[[t for t in y.index if str(tl.loc[t, "best_preparation"]) == "headless"]]


def ledger_types() -> list[str]:
    """E1: A1's types with an unambiguous kit driver line and no clear front-leg label in exam 1."""
    dl = pd.read_csv(RESEARCH / "kit_v2" / "driver_lines.csv", dtype=str, keep_default_na=False)
    with_line = set(dl["manc_type"]) - {"AMBIGUOUS", ""}
    tl = labels_v2().set_index("manc_type")
    clear = {t for t in tl.index if tl.loc[t, "front"] in ("yes", "no")}
    return sorted(t for t in a1_types().index if t in with_line and t not in clear)


def lines_of(t: str) -> list[str]:
    dl = pd.read_csv(RESEARCH / "kit_v2" / "driver_lines.csv", dtype=str, keep_default_na=False)
    return sorted(set(dl.loc[dl["manc_type"] == t, "line_id"]))


def collection_of(line: str) -> str:
    """E6: the collection named by the line."""
    u = line.upper()
    if u.startswith("SS") or u.startswith("MB") and "SS" in u:
        return "Janelia FlyLight split-GAL4 collection"
    if u.startswith("VT"):
        return "Vienna Tiles (VDRC)"
    if u.startswith("R") and any(ch.isdigit() for ch in u[:3]) or u.startswith("GMR"):
        return "Janelia GAL4 (Bloomington)"
    return "as written in the source"


def robust_scores(fix: str) -> pd.Series:
    """The robust model's exam 1 whole-type screen (Part D campaign dx-<fix>, seeds 0..7), G5 type score; fix 1: best in-bounds grid
    score; fix 2: pooled score of B1r's stored runs (seeds 0..7)."""
    a1 = list(a1_types().index)
    if fix == "2":
        res = read_log(data_dir() / "arms" / "GHA_b1r" / "results.pkl")
        rows = [{"type": r["key"].split("|")[1], "seed": int(r["seed"]), "usable": bool(r.get("usable")), "score": pooled.pooled_score(r)}
                for r in res if "error" not in r and int(r["seed"]) < 8]
    else:
        res = read_log(data_dir() / "reliability_v2" / f"GHA_dx-{fix}-run4" / "results.pkl")
        rows = []
        for r in res:
            if "error" in r:
                continue
            t, s = r["key"].split("|")[1], int(r["key"].split("|")[2][1:])
            if fix == "1":
                ib = [x["score"] for x in r["runs"] if x["in_bounds"]]
                rows.append({"type": t, "seed": s, "usable": True, "score": max(ib) if ib else 0.0})
            else:
                rows.append({"type": t, "seed": s, "usable": bool(r.get("usable")), "score": r.get("score")})
    return AG.type_scores(pd.DataFrame(rows), list(range(8)), a1)


# ------------------------------------------------------------------------------------------------------------- calibration
def pct_rank(s: pd.Series) -> pd.Series:
    """E3: percentile rank with average ties: (number below + half the number equal) / n."""
    v = s.to_numpy(float)
    out = [(np.sum(v < x) + 0.5 * np.sum(v == x)) / len(v) for x in v]
    return pd.Series(out, index=s.index)


def _newton(x: np.ndarray, y: np.ndarray, firth: bool = False, iters: int = 100) -> tuple[np.ndarray, bool]:
    X = np.column_stack([np.ones_like(x), x])
    b = np.zeros(2)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ b)))
        w = p * (1 - p)
        info = X.T @ (X * w[:, None])
        if firth:
            hinv = np.linalg.pinv(info)
            h = np.einsum("ij,jk,ik->i", X * np.sqrt(w)[:, None], hinv, X * np.sqrt(w)[:, None])
            grad = X.T @ (y - p + h * (0.5 - p))
        else:
            grad = X.T @ (y - p)
        step = np.linalg.pinv(info) @ grad
        b = b + step
        if np.max(np.abs(step)) < 1e-10:
            return b, True
    return b, False


def fit_logistic(x: np.ndarray, y: np.ndarray) -> dict:
    """E3: maximum likelihood by Newton; Firth's bias-reduced likelihood if it fails to converge in 100 iterations or |b| > 100."""
    b, ok = _newton(x, y)
    if ok and abs(b[1]) <= 100:
        return {"a": float(b[0]), "b": float(b[1]), "method": "maximum likelihood"}
    b, ok = _newton(x, y, firth=True)
    return {"a": float(b[0]), "b": float(b[1]), "method": "Firth" + ("" if ok else " (not converged)")}


def prob(fit: dict, x) -> np.ndarray:
    return 1 / (1 + np.exp(-(fit["a"] + fit["b"] * np.asarray(x, float))))


def loo(x: np.ndarray, y: np.ndarray) -> dict:
    n = len(y)
    p, base = np.zeros(n), np.zeros(n)
    for i in range(n):
        m = np.arange(n) != i
        p[i] = prob(fit_logistic(x[m], y[m]), x[i])
        base[i] = y[m].mean()
    eps = 1e-12
    bins = [(0, 1 / 3), (1 / 3, 2 / 3), (2 / 3, 1.0 + 1e-9)]
    rel = [{"bin": [round(lo, 3), round(min(hi, 1.0), 3)], "n": int(((p >= lo) & (p < hi)).sum()),
            "mean_p": float(p[(p >= lo) & (p < hi)].mean()) if ((p >= lo) & (p < hi)).any() else None,
            "observed_yes": float(y[(p >= lo) & (p < hi)].mean()) if ((p >= lo) & (p < hi)).any() else None} for lo, hi in bins]
    return {"n": n, "brier_loo": float(np.mean((p - y) ** 2)), "brier_base_rate_loo": float(np.mean((base - y) ** 2)),
            "log_loss_loo": float(-np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps))),
            "auroc_loo": float(ST.auroc(p, y)), "reliability_3_bins": rel}


# ------------------------------------------------------------------------------------------------------------------- flags
def _band(v: float) -> str:
    return "driver" if v >= 0.5 else ("non_driver" if v < 0.05 else "indeterminate")


def _tercile(s: pd.Series) -> pd.Series:
    q = s.rank(pct=True, method="average")
    return pd.Series(np.where(q <= 1 / 3, 0, np.where(q <= 2 / 3, 1, 2)), index=s.index)


def flags(types: list[str], fix: str | None) -> dict[str, dict[str, dict[str, str]]]:
    """E5: per type and source, `agree` / `disagree` / `not computed` for the two flies and the two sides."""
    from brainir_ledger import baselines as BL  # noqa: PLC0415

    out = {t: {} for t in types}
    b1 = pd.read_csv(P2 / "B1r" / "types.csv").set_index("manc_type")["primary_score"]
    b2 = pd.read_csv(P2 / "B2r" / "types.csv").set_index("manc_type")["primary_score"]
    pa = gha4.part_a_results("MANC")
    df = {s: pd.DataFrame([{"type": t, "seed": se, "usable": bool(r.get("usable")), "score": r.get("score")}
                           for (side, t, se), r in pa.items() if side == s]) for s in ("L", "R")}
    hm = MR.fly("MANC").halves()
    tl = [t for t in types if t in hm["L"]]
    sl, sr = AG.type_scores(df["L"], None, tl), AG.type_scores(df["R"], None, tl)
    fm, fc = MR.fly("MANC"), MR.fly("MaleCNS")
    s2m = BL.compute(fm.C, sp.csr_matrix(fm.net.W, dtype=float), fm.readout, fm.groups, []).set_index("manc_type")["S2_twohop_signed"]
    s2c = BL.compute(fc.C, sp.csr_matrix(fc.net.W, dtype=float), fc.readout, fc.groups, []).set_index("manc_type")["S2_twohop_signed"]
    common = sorted(set(s2m.index) & set(s2c.index))
    tm_, tc_ = _tercile(s2m[common]), _tercile(s2c[common])
    s2l = BL.compute(fm.C, sp.csr_matrix(fm.net.W, dtype=float), fm.readout_side("L"), hm["L"], []).set_index("manc_type")["S2_twohop_signed"]
    s2r = BL.compute(fm.C, sp.csr_matrix(fm.net.W, dtype=float), fm.readout_side("R"), hm["R"], []).set_index("manc_type")["S2_twohop_signed"]
    sides_common = sorted(set(s2l.index) & set(s2r.index))
    tl_, tr_ = _tercile(s2l[sides_common]), _tercile(s2r[sides_common])
    rob = None
    if fix is not None and fix not in ("1", "2"):
        res = read_log(data_dir() / "reliability_v2" / f"GHA_cx-{fix}-run4" / "results.pkl")
        rob = {}
        for k in ("MANC-L", "MANC-R", "MCNS-L", "MCNS-R"):
            rows = [{"type": r["key"].split("|")[1], "seed": int(r["key"].split("|")[2][1:]), "usable": bool(r.get("usable")),
                     "score": r.get("score")} for r in res if "error" not in r and r["key"].split("|")[0] == f"CX-{fix}-{k}"]
            d = pd.DataFrame(rows)
            rob[k] = AG.type_scores(d, None, None) if len(d) else pd.Series(dtype=float)
    for t in types:
        f1 = "agree" if (t in b1.index and t in b2.index and _band(b1[t]) == _band(b2[t])) else ("disagree" if t in b1.index and t in b2.index else "not computed")
        f2 = "agree" if (t in sl.index and _band(sl[t]) == _band(sr[t])) else ("disagree" if t in sl.index else "not computed")
        out[t]["authors_model"] = {"two_flies": f1, "two_sides": f2}
        g1 = ("agree" if tm_[t] == tc_[t] else "disagree") if t in tm_.index else "not computed"
        g2 = ("agree" if tl_[t] == tr_[t] else "disagree") if t in tl_.index else "not computed"
        out[t]["two_step_count"] = {"two_flies": g1, "two_sides": g2}
        if rob is not None:
            have = all(t in rob[k].index for k in rob)
            r1 = ("agree" if _band(rob["MANC-L"][t]) == _band(rob["MCNS-L"][t]) and _band(rob["MANC-R"][t]) == _band(rob["MCNS-R"][t])
                  else "disagree") if have else "not computed"
            r2 = ("agree" if _band(rob["MANC-L"][t]) == _band(rob["MANC-R"][t]) else "disagree") if have else "not computed"
            out[t]["robust_model"] = {"two_flies": r1, "two_sides": r2}
        elif fix is not None:
            out[t]["robust_model"] = {"two_flies": "not computed", "two_sides": "not computed"}
    return out


# ----------------------------------------------------------------------------------------------------------------- build
def build(fix: str | None) -> None:
    gha4.require_freeze("forward ledger")
    names = {"authors_model": "the authors' model (A1)", "two_step_count": "two-step signed synapse counting (S2)"}
    raw = {"authors_model": a1_types(), "two_step_count": s2_scores().reindex(a1_types().index)}
    if fix is not None:
        raw["robust_model"] = robust_scores(fix)
        names["robust_model"] = f"the robust model (fix {fix})"
    y_all = primary_set()
    y_head = headless_set()
    use_head = len(y_head) >= 15 and y_head.nunique() == 2
    y = y_head if use_head else y_all
    cal, fits = {}, {}
    for src, s in raw.items():
        x = pct_rank(s)
        xf, yf = x[y.index].to_numpy(), y.to_numpy()
        fits[src] = fit_logistic(xf, yf)
        cal[src] = {"fit": fits[src], **loo(xf, yf)}
    types = ledger_types()
    fl = flags(types, fix)
    rows, sent = [], []
    for t in types:
        for src, s in raw.items():
            x = float(pct_rank(s)[t])
            p = float(prob(fits[src], x))
            lines = lines_of(t)
            sentence = (f"Activating {t} (lines: {', '.join(lines)}) in a decapitated fly: {names[src]} gives a {round(100 * p)} % chance "
                        f"of rhythmic front-leg stepping.")
            rows.append({"type": t, "source": src, "score": float(s[t]), "percentile_rank": x, "p_rhythmic": p,
                         "flag_two_flies": fl[t][src]["two_flies"], "flag_two_sides": fl[t][src]["two_sides"], "lines": ";".join(lines),
                         "sentence": sentence})
            sent.append(sentence)
    led = pd.DataFrame(rows)
    _out("LEDGER.csv", led.to_csv(index=False, lineterminator="\n"))
    base = float(y.mean())
    _out("CALIBRATION.json", json.dumps({"fit_set": "headless-labelled types" if use_head else "all labelled types (exam 1 primary set)",
                                         "n_fit": int(len(y)), "n_yes": int(y.sum()), "n_headless": int(len(y_head)),
                                         "base_rate": base, "training_note": TRAINING, "atlas_caveat": ATLAS, "sources": cal},
                                        indent=1, default=float) + "\n")
    _out("SENTENCES.md", "# Forward ledger: one sentence per prediction (generated by script from LEDGER.csv)\n\n" + HONESTY + "\n\n"
         + TRAINING + "\n\n" + "\n".join(f"- {x}" for x in sent) + "\n")
    _out("README.md", "# Forward ledger v1 (PREREG v4 Part E)\n\n" + HONESTY + "\n\n" + TRAINING + "\n\n" + ATLAS + "\n\n"
         + f"Types: {len(types)} (E1). Sources: {', '.join(names.values())}.\n\n"
         + f"Scoring rule (E7): when results arrive, each source is scored by its Brier score against a base-rate guesser that says "
           f"{base:.3f} for every type (exam 1's base rate on the fit set).\n")


def decisive() -> None:
    """E6: the 15 types that best separate the sources, counting a pair of sources only if both are flagged `agree` twice."""
    gha4.require_freeze("decisive experiments")
    led = pd.read_csv(FWD / "LEDGER.csv")
    srcs = sorted(led["source"].unique())
    rows = []
    for t, g in led.groupby("type"):
        g = g.set_index("source")
        best, pair = -1.0, None
        for i, a in enumerate(srcs):
            for b in srcs[i + 1:]:
                if a in g.index and b in g.index and all(g.loc[s, f] == "agree" for s in (a, b) for f in ("flag_two_flies", "flag_two_sides")):
                    gap = abs(g.loc[a, "p_rhythmic"] - g.loc[b, "p_rhythmic"])
                    if gap > best:
                        best, pair = gap, (a, b)
        if pair is not None:
            rows.append({"type": t, "gap": best, "pair": f"{pair[0]} vs {pair[1]}", "lines": g.iloc[0]["lines"],
                         **{f"p_{s}": float(g.loc[s, "p_rhythmic"]) for s in srcs if s in g.index}})
    top = sorted(rows, key=lambda r: (-r["gap"], r["type"]))[:15]
    for r in top:
        r["collections"] = ";".join(sorted({collection_of(x) for x in str(r["lines"]).split(";") if x}))
        r["protocol"] = " | ".join(PROTOCOL)
    _out("DECISIVE.csv", pd.DataFrame(top).to_csv(index=False, lineterminator="\n"))


def main() -> None:
    cmd, a = sys.argv[1:2], sys.argv[2:]
    if cmd == ["build"]:
        build(a[a.index("--robust") + 1] if "--robust" in a else None)
    elif cmd == ["decisive"]:
        decisive()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
