"""PREREG v5 Part R: replication across the two flies, from the locked per-type tables only (descriptive; POST HOC: the thresholds
and categories were chosen after the replication pattern was seen, RUN5_PROMPT sections 1 and 5).

    uv run --project ledger --no-sync python ledger/scripts/replication_v1.py build      # -> research/ledger/replication_v1/R_*

Inputs: `research/ledger/pertype_v1/` (LOCK_pertype_v1.json). Outputs are written once (the command refuses if they exist).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from brainir_ledger import RESEARCH  # noqa: E402

PERTYPE = RESEARCH / "pertype_v1"
OUT = RESEARCH / "replication_v1"
DRIVER, NONDRIVER, NEAR_LO = 0.5, 0.05, 0.3           # G2; R1 (near-replicated: 0.3 <= other < 0.5; single-fly hit: other < 0.3)
BOOT_SEED, BOOT_N = 20261501, 10_000                  # R2.2
HALF_FLY = ("MANC_L", "MANC_R", "MaleCNS_L", "MaleCNS_R")
CONFIRMED = ("DNg100", "DNb08")                       # R2.6
CATS = ("replicated", "near_replicated", "single_fly_manc", "single_fly_malecns", "stable_non_driver", "neither")
POSTHOC = "POST HOC (PREREG v5 Part R: thresholds and categories chosen after the replication pattern was seen)"


def load(name: str, pertype: Path | None = None) -> pd.DataFrame:
    d = pd.read_csv((pertype or PERTYPE) / f"{name}.csv", dtype={"manc_type": str})
    if d["manc_type"].duplicated().any() and name != "A0_copies":
        raise SystemExit(f"{name}: duplicate manc_type rows")
    return d


def tables(pertype: Path | None = None) -> dict[str, pd.DataFrame]:
    t = {n: load(n, pertype).set_index("manc_type") for n in ("B1r", "B2r", "A1", *HALF_FLY, "match_confidence")}
    t["A0_copies"] = load("A0_copies", pertype)
    return t


def common_types(T: dict, x: str = "B1r") -> list[str]:
    """G3: types in both the MANC whole-type screen `x` and B2r."""
    return sorted(set(T[x].index) & set(T["B2r"].index))


def categorise(sx: float, sy: float, half: list[float] | None) -> str:
    """R1 for one type: sx = MANC whole-type score (B1r or A1), sy = B2r score, half = the four half-fly scores (None if the type is
    missing from any half-fly table, so it cannot be a stable non-driver)."""
    dx, dy = sx >= DRIVER, sy >= DRIVER
    if dx and dy:
        return "replicated"
    if (dx and NEAR_LO <= sy < DRIVER) or (dy and NEAR_LO <= sx < DRIVER):
        return "near_replicated"
    if dx and sy < NEAR_LO:
        return "single_fly_manc"
    if dy and sx < NEAR_LO:
        return "single_fly_malecns"
    if sx < NONDRIVER and sy < NONDRIVER and half is not None and all(h < NONDRIVER for h in half):
        return "stable_non_driver"
    return "neither"


def categories(T: dict, x: str = "B1r", confidence: tuple[str, ...] | None = None) -> pd.DataFrame:
    rows = []
    for t in common_types(T, x):
        conf = T["match_confidence"].loc[t, "confidence"] if t in T["match_confidence"].index else "none"
        if confidence is not None and conf not in confidence:
            continue
        half = [float(T[h].loc[t, "score"]) for h in HALF_FLY if t in T[h].index]
        half_ok = half if len(half) == len(HALF_FLY) else None
        sx, sy = float(T[x].loc[t, "score"]), float(T["B2r"].loc[t, "score"])
        row = {"manc_type": t, "category": categorise(sx, sy, half_ok), x: sx, "B2r": sy, "match_confidence": conf,
               "match_flag": "low or medium match" if conf in ("low", "medium") else "", f"{x}_n_usable": int(T[x].loc[t, "n_usable"]),
               "B2r_n_usable": int(T["B2r"].loc[t, "n_usable"])}
        if x != "B1r":
            row["B1r"] = float(T["B1r"].loc[t, "score"]) if t in T["B1r"].index else None
        if x != "A1":
            row["A1"] = float(T["A1"].loc[t, "score"]) if t in T["A1"].index else None
        for h in HALF_FLY:
            row[h] = float(T[h].loc[t, "score"]) if t in T[h].index else None
        rows.append(row)
    return pd.DataFrame(rows)


def one_fly_only(T: dict, x: str = "B1r") -> dict[str, list]:
    return {f"{x}_only": [[t, float(T[x].loc[t, "score"])] for t in sorted(set(T[x].index) - set(T["B2r"].index))],
            "B2r_only": [[t, float(T["B2r"].loc[t, "score"])] for t in sorted(set(T["B2r"].index) - set(T[x].index))]}


def _j(a: np.ndarray, b: np.ndarray) -> float:
    u = np.sum(a | b)
    return float(np.sum(a & b) / u) if u else float("nan")


def _oc(a: np.ndarray, b: np.ndarray) -> float:
    m = min(np.sum(a), np.sum(b))
    return float(np.sum(a & b) / m) if m else float("nan")


def _overlap_stats(F: dict[str, np.ndarray], idx: np.ndarray) -> dict[str, float]:
    """R2.2 statistics on one (re)sample of types: full-screen J and OC and replication rates; matched-noise cross-half values, split-half
    ceilings and ratios for OC and J (NaN where undefined)."""
    g = {k: v[idx] for k, v in F.items()}
    out = {"J_full": _j(g["x"], g["y"]), "OC_full": _oc(g["x"], g["y"]),
           "rate_x_in_y": float(np.sum(g["x"] & g["y"]) / np.sum(g["x"])) if np.sum(g["x"]) else float("nan"),
           "rate_y_in_x": float(np.sum(g["x"] & g["y"]) / np.sum(g["y"])) if np.sum(g["y"]) else float("nan")}
    for name, f in (("OC", _oc), ("J", _j)):
        cross = (f(g["x1"], g["y2"]) + f(g["x2"], g["y1"])) / 2          # NaN if either is undefined
        ceil_ = (f(g["x1"], g["x2"]) + f(g["y1"], g["y2"])) / 2
        ok = np.isfinite(cross) and np.isfinite(ceil_) and ceil_ > 0
        out.update({f"{name}_cross_half": float(cross), f"{name}_ceiling": float(ceil_), f"{name}_ratio": float(cross / ceil_) if ok else float("nan")})
    return out


def overlap(T: dict, x: str = "B1r", types: list[str] | None = None) -> dict:
    """R2.2-R2.4 on the given common types: list sizes, both, the hypergeometric expectation, replication rates, J with its size limit, OC;
    matched-noise cross-half values against split-half ceilings; 95 % percentile bootstrap over types (fresh generator, seed 20261501;
    shared resamples; undefined resamples dropped per statistic and counted)."""
    import warnings  # noqa: PLC0415

    types = types if types is not None else common_types(T, x)
    X, Y = T[x].loc[types], T["B2r"].loc[types]
    F = {"x": X["score"].to_numpy() >= DRIVER, "y": Y["score"].to_numpy() >= DRIVER,
         "x1": X["score_h1"].to_numpy() >= DRIVER, "x2": X["score_h2"].to_numpy() >= DRIVER,
         "y1": Y["score_h1"].to_numpy() >= DRIVER, "y2": Y["score_h2"].to_numpy() >= DRIVER}
    n = len(types)
    point = _overlap_stats(F, np.arange(n))
    rng = np.random.default_rng(BOOT_SEED)
    boot = {k: [] for k in point}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for _ in range(BOOT_N):
            st = _overlap_stats(F, rng.integers(0, n, n))
            for k, v in st.items():
                boot[k].append(v)
    ci = {}
    for k, v in boot.items():
        a = np.asarray(v, float)
        fin = a[np.isfinite(a)]
        ci[k] = {"lo": float(np.percentile(fin, 2.5)) if fin.size else None, "hi": float(np.percentile(fin, 97.5)) if fin.size else None,
                 "n_undefined": int((~np.isfinite(a)).sum())}
    nx, ny, nxy = int(F["x"].sum()), int(F["y"].sum()), int((F["x"] & F["y"]).sum())
    return {"screen_x": x, "n_types": n, "n_drivers_x": nx, "n_drivers_B2r": ny, "n_both": nxy,
            "expected_both_if_independent": nx * ny / n if n else None, "J_max_for_these_sizes": (min(nx, ny) / max(nx, ny)) if max(nx, ny) else None,
            "drivers_both": sorted(np.asarray(types)[F["x"] & F["y"]].tolist()),
            "split_half_drivers": {k: int(F[k].sum()) for k in ("x1", "x2", "y1", "y2")},
            "point": point, "bootstrap_95": ci, "bootstrap": {"seed": BOOT_SEED, "n": BOOT_N, "unit": "type (resampled with replacement)",
                                                              "interval": "percentile 2.5-97.5"}}


def a0_concordance(T: dict) -> dict:
    """R2.5: copy concordance in the authors' single-neuron screen (A0), types with at least one copy on each side."""
    a = T["A0_copies"]
    out = {}
    for label, sel in (("copies_on_both_sides", (a["members_L"] >= 1) & (a["members_R"] >= 1)),
                       ("one_copy_each_side", a["type_one_each_side"].astype(str).str.lower() == "true")):
        d = a[sel]
        rows = []
        for t, g in d.groupby("manc_type"):
            drv = g["score"] >= DRIVER
            rows.append({"manc_type": t, "n_copies": len(g), "n_driver_copies": int(drv.sum()), "any": bool(drv.any()), "all": bool(drv.all()),
                         "copies": [[int(b), s, float(x)] for b, s, x in zip(g["bodyId"], g["side"], g["score"])]})
        anyd = [r for r in rows if r["any"]]
        alld = [r for r in rows if r["all"]]
        out[label] = {"n_types": len(rows), "n_with_a_driver_copy": len(anyd), "n_all_copies_drivers": len(alld),
                      "concordance_share": len(alld) / len(anyd) if anyd else None, "concordant_over_all_types": len(alld) / len(rows) if rows else None,
                      "concordant_types": [{k: r[k] for k in ("manc_type", "n_copies", "copies")} for r in alld],
                      "discordant_types": [{k: r[k] for k in ("manc_type", "n_copies", "n_driver_copies", "copies")} for r in anyd if not r["all"]]}
    return out


def confirmed(T: dict, cats: pd.DataFrame, cats_a1: pd.DataFrame) -> dict:
    """R2.6: where the two experimentally confirmed drivers fall (with the selection caveats stated beside them in the report)."""
    out = {}
    a = T["A0_copies"]
    for t in CONFIRMED:
        row = {"category_B1r_x_B2r": cats.set_index("manc_type")["category"].get(t), "category_A1_x_B2r": cats_a1.set_index("manc_type")["category"].get(t),
               "match_confidence": T["match_confidence"]["confidence"].get(t)}
        for s in ("B1r", "B2r", "A1", *HALF_FLY):
            row[s] = float(T[s].loc[t, "score"]) if t in T[s].index else None
        row["A0_copies"] = [[int(b), sd, float(x)] for b, sd, x in zip(a.loc[a["manc_type"] == t, "bodyId"], a.loc[a["manc_type"] == t, "side"],
                                                                      a.loc[a["manc_type"] == t, "score"])]
        out[t] = row
    out["caveats"] = ["DNg100 is the neuron the model was calibrated and built around (the tuner's K was chosen on it).",
                      "The original authors chose DNb08 themselves.", "Both are exposed types.", "Two confirmed neurons are a tiny sample."]
    return out


def summary(cats: pd.DataFrame) -> dict:
    return {c: {"n": int((cats["category"] == c).sum()), "types": sorted(cats.loc[cats["category"] == c, "manc_type"])} for c in CATS}


def analyse(T: dict) -> dict:
    res = {"label": POSTHOC, "rule": "PREREG v5 Part R (R1, R2)", "inputs": "research/ledger/pertype_v1 (LOCK_pertype_v1.json)",
           "leading_version": "high (RUN5_PROMPT section 8; PREREG v5 R2)"}
    for x in ("B1r", "A1"):
        key = "B1r_x_B2r" if x == "B1r" else "A1_x_B2r"
        sec = {}
        for label, conf in (("high", ("high",)), ("all", None), ("high_medium", ("high", "medium"))):
            cats = categories(T, x, conf)
            sec[label] = {"categories": summary(cats), "overlap": overlap(T, x, sorted(cats["manc_type"])),
                          "table": json.loads(cats.to_json(orient="records"))}
        sec["one_fly_only"] = one_fly_only(T, x)
        c = categories(T, x)
        flagged = c[(c["match_flag"] != "") & (c["category"] != "neither")]
        sec["flagged_low_or_medium_match"] = {k: sorted(g["manc_type"]) for k, g in flagged.groupby("category")}
        res[key] = sec
    res["A0_copy_concordance"] = a0_concordance(T)
    res["confirmed_drivers"] = confirmed(T, categories(T, "B1r"), categories(T, "A1"))
    return res


def _fmt(v) -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "n/a"
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def _ci(o: dict, k: str) -> str:
    c = o["bootstrap_95"][k]
    return f"{_fmt(o['point'][k])} [{_fmt(c['lo'])}, {_fmt(c['hi'])}]"


def report_md(res: dict) -> str:
    L = [f"# Part R: replication across the two flies ({POSTHOC})", "",
         "Every table and number in this file is post hoc. Source: `research/ledger/pertype_v1/` (LOCK_pertype_v1.json). Rules: PREREG v5 "
         "Part R. Driver >= 0.5; replicated = driver in both B1r (or A1) and B2r; near-replicated = driver in one and 0.3-0.5 in the other; "
         "single-fly hit = driver in one and < 0.3 in the other; stable non-driver = < 0.05 in both and in all four half-fly screens. "
         "The high-confidence version (types whose cross-fly match is high) leads; all types stand beside it.", ""]
    for key, title in (("B1r_x_B2r", "B1r (our MANC screen) x B2r (our MaleCNS screen)"), ("A1_x_B2r", "A1 (the authors' MANC list) x B2r")):
        sec = res[key]
        L += [f"## {title} (post hoc)", "", "| category | high-confidence match | all types | high + medium |", "|---|---|---|---|"]
        for c in CATS:
            L.append(f"| {c} | {sec['high']['categories'][c]['n']} | {sec['all']['categories'][c]['n']} | {sec['high_medium']['categories'][c]['n']} |")
        L.append("")
        for lv in ("high", "all"):
            for c in CATS[:-1]:
                L.append(f"- **{c}** ({lv}): {', '.join(sec[lv]['categories'][c]['types']) or 'none'}")
            L.append("")
        L.append("Members flagged for a low or medium match (both directions): " +
                 ("; ".join(f"{c}: {', '.join(v)}" for c, v in sec["flagged_low_or_medium_match"].items()) or "none") + ".")
        L += ["", "| overlap of the driver lists (95 % bootstrap interval) | high-confidence | all types | high + medium |", "|---|---|---|---|"]
        for k, lab in (("rate_x_in_y", f"replication rate: {sec['all']['overlap']['screen_x']} drivers that are B2r drivers"),
                       ("rate_y_in_x", "replication rate: B2r drivers that are MANC drivers"), ("OC_full", "overlap coefficient, full screens"),
                       ("OC_cross_half", "OC, cross-fly matched halves"), ("OC_ceiling", "OC ceiling: within-fly split halves"),
                       ("OC_ratio", "OC cross-half / ceiling"), ("J_full", "Jaccard, full screens"), ("J_cross_half", "Jaccard, cross-fly halves"),
                       ("J_ceiling", "Jaccard ceiling"), ("J_ratio", "Jaccard ratio")):
            L.append(f"| {lab} | " + " | ".join(_ci(sec[lv]["overlap"], k) for lv in ("high", "all", "high_medium")) + " |")
        for lv in ("high", "all"):
            o = sec[lv]["overlap"]
            L.append(f"- {lv}: {o['n_drivers_x']} drivers in {o['screen_x']}, {o['n_drivers_B2r']} in B2r, {o['n_both']} in both (expected "
                     f"{_fmt(o['expected_both_if_independent'])} if independent) over {o['n_types']} common types; the Jaccard index cannot exceed "
                     f"{_fmt(o['J_max_for_these_sizes'])} with these list sizes.")
        L.append("")
    a = res["A0_copy_concordance"]
    L += ["## Copy concordance in the authors' single-neuron screen A0 (post hoc)", ""]
    for lab, d in a.items():
        L.append(f"- {lab}: {d['n_types']} types; {d['n_with_a_driver_copy']} with at least one driver copy; {d['n_all_copies_drivers']} with every copy a "
                 f"driver ({', '.join(r['manc_type'] for r in d['concordant_types']) or 'none'}); share {_fmt(d['concordance_share'])} of the types with "
                 f"a driver copy, {_fmt(d['concordant_over_all_types'])} of all.")
    c = res["confirmed_drivers"]
    L += ["", "## The two experimentally confirmed drivers (post hoc)", ""]
    for t in CONFIRMED:
        r = c[t]
        L.append(f"- **{t}**: {r['category_B1r_x_B2r']} (A1 x B2r: {r['category_A1_x_B2r']}); match {r['match_confidence']}; B1r {_fmt(r['B1r'])}, "
                 f"B2r {_fmt(r['B2r'])}, A1 {_fmt(r['A1'])}; half-flies " + ", ".join(f"{h} {_fmt(r[h])}" for h in HALF_FLY) +
                 "; A0 copies " + ", ".join(f"{b} ({s}) {x:.2f}" for b, s, x in r["A0_copies"]) + ".")
    L += ["", "Selection caveats: " + " ".join(c["caveats"]), ""]
    return "\n".join(L)


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in ("R_replication.json", "R_tables.md"):
        if (OUT / f).exists():
            raise SystemExit(f"{OUT / f} exists; written once")
    res = analyse(tables())
    with open(OUT / "R_replication.json", "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, indent=1, sort_keys=True, default=str) + "\n")
    with open(OUT / "R_tables.md", "x", encoding="utf-8", newline="\n") as fh:
        fh.write(report_md(res))
    print(report_md(res))


if __name__ == "__main__":
    if sys.argv[1:] == ["build"]:
        build()
    else:
        raise SystemExit(__doc__)
