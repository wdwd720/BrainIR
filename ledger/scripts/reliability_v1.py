"""Reliability study v1 (PREREG v3 Part R; RUN3_PROMPT section 8): descriptive, no labels. Why do the two flies disagree?

    uv run --project ledger --no-sync python ledger/scripts/reliability_v1.py r1     # existing data (B1r vs B2r, split halves)
    uv run --project ledger --no-sync python ledger/scripts/reliability_v1.py r2     # wiring baselines S1-S7 on both flies
    uv run --project ledger --no-sync python ledger/scripts/reliability_v1.py r3     # weight-noise campaigns r3-<k>-run3
    uv run --project ledger --no-sync python ledger/scripts/reliability_v1.py r4     # left vs right campaign r4-run3
    -> research/ledger/reliability_v1/R1.json ... R4.json, RELIABILITY.md (summary)

Type score = `primary_score` as in run 2's tables (`tables.type_row`): the mean of the usable replicates' scores, 0 when none is
usable. Rank agreement = Spearman. No label of any kind is read.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))
from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

OUT = RESEARCH / "reliability_v1"
P2 = RESEARCH / "predictions_v2"
BANDS = ("non_driver", "indeterminate", "driver")


def band(x: float) -> str:
    return "driver" if x >= 0.5 else ("non_driver" if x < 0.05 else "indeterminate")


def rho(a, b) -> dict:
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.all(a == a[0]) or np.all(b == b[0]):
        return {"n": int(len(a)), "spearman": None}
    r = spearmanr(a, b)
    return {"n": int(len(a)), "spearman": float(r.statistic)}


def type_scores(rep: pd.DataFrame, seeds=None) -> pd.Series:
    """primary_score per type from replicate rows (columns manc_type, seed, usable, score)."""
    r = rep if seeds is None else rep[rep["seed"].isin(list(seeds))]
    def one(g):
        u = g[g["usable"].astype(bool)]
        return float(u["score"].mean()) if len(u) else 0.0
    return r.groupby("manc_type").apply(one, include_groups=False)


def topk(a: pd.Series, b: pd.Series, k: int) -> float:
    ra = sorted(a.index, key=lambda t: (-a[t], t))[:k]
    rb = sorted(b.index, key=lambda t: (-b[t], t))[:k]
    return len(set(ra) & set(rb)) / k


def kappa3(x: list[str], y: list[str]) -> float | None:
    n = len(x)
    if not n:
        return None
    po = sum(a == b for a, b in zip(x, y)) / n
    pe = sum((x.count(c) / n) * (y.count(c) / n) for c in BANDS)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def high_confidence_types() -> set[str]:
    """MANC types whose every MaleCNS member maps through a curated body match (mancBodyid), as in `arms.malecns_network`."""
    import glob

    import pyarrow.feather as feather
    from brainir import paths
    from brainir_ledger import arms as AR
    from brainir_ledger import networks as N

    net, groups, _ = AR.malecns_network()
    ann = feather.read_table(glob.glob(str(paths.data_root() / "raw" / "external" / "malecns_v1.0_body_annotations" / "*.feather"))[0]) \
        .to_pandas().set_index("bodyId")
    body2type = {**dict(zip(N.full_cord().table["bodyId"].astype(int), N.full_cord().table["type"])),
                 **dict(zip(N.front_leg().table["bodyId"].astype(int), N.front_leg().table["type"]))}
    ids = net.table["bodyId"].astype(int).to_numpy()
    out = set()
    for t, members in groups.items():
        ok = True
        for i in members:
            b = int(ids[i])
            r = ann.loc[b] if b in ann.index else None
            if r is None or pd.isna(r.get("mancBodyid")) or int(r["mancBodyid"]) not in body2type:
                ok = False
                break
        if ok:
            out.add(t)
    return out


def r1() -> dict:
    t1 = pd.read_csv(P2 / "B1r" / "types.csv").set_index("manc_type")["primary_score"]
    t2 = pd.read_csv(P2 / "B2r" / "types.csv").set_index("manc_type")["primary_score"]
    common = sorted(set(t1.index) & set(t2.index))
    a, b = t1[common], t2[common]
    nz = [t for t in common if a[t] != 0 or b[t] != 0]
    hc = sorted(set(common) & high_confidence_types())
    ba, bb = [band(a[t]) for t in common], [band(b[t]) for t in common]
    halves = {}
    for arm in ("B1r", "B2r"):
        rep = pd.read_parquet(P2 / arm / "replicates.parquet")
        h1, h2 = type_scores(rep, range(0, 8)), type_scores(rep, range(8, 16))
        ts = sorted(set(h1.index) & set(h2.index))
        halves[arm] = rho(h1[ts], h2[ts])
    out = {"common_types": len(common), "all": rho(a, b), "nonzero_in_either": rho(a[nz], b[nz]),
           "high_confidence_match": rho(a[hc], b[hc]), "band_agreement": sum(x == y for x, y in zip(ba, bb)) / len(common),
           "band_kappa": kappa3(ba, bb), "top10_overlap": topk(a, b, 10), "top30_overlap": topk(a, b, 30),
           "split_half_ceiling": halves}
    return out


def r2() -> dict:
    from brainir_ledger import arms as AR
    from brainir_ledger import baselines as BL
    from brainir_ledger import networks as N

    fl = N.front_leg()
    g1 = N.type_groups(fl.table)
    net2, g2, _ = AR.malecns_network()
    C2 = net2.C if getattr(net2, "C", None) is not None else abs(net2.W)
    b1 = BL.compute(fl.C, fl.W, fl.readout, g1, []).set_index("manc_type")
    b2 = BL.compute(C2, net2.W, net2.readout, g2, []).set_index("manc_type")
    common = sorted(set(b1.index) & set(b2.index))
    t1 = pd.read_csv(P2 / "B1r" / "types.csv").set_index("manc_type")["primary_score"]
    t2 = pd.read_csv(P2 / "B2r" / "types.csv").set_index("manc_type")["primary_score"]
    cs = sorted(set(common) & set(t1.index) & set(t2.index))
    out = {"common_types": len(cs), "simulation_cross_fly": rho(t1[cs], t2[cs]),
           "wiring_cross_fly": {c: rho(b1.loc[cs, c], b2.loc[cs, c]) for c in BL.BASELINES if c != "S8_informed"}}
    return out


def _campaign_scores(name: str) -> pd.DataFrame:
    rs = read_log(data_dir() / "reliability" / f"GHA_{name}" / "results.pkl")
    rows = [{"arm": r["key"].split("|")[0], "manc_type": r["key"].split("|")[1], "seed": int(r["seed"]), "usable": bool(r["usable"]),
             "score": r.get("score")} for r in rs if "error" not in r]
    return pd.DataFrame(rows)


def r3(cross_fly: float | None) -> dict:
    base = type_scores(pd.read_parquet(P2 / "B1r" / "replicates.parquet"), range(4))
    per = {}
    for s in (5, 10, 20):
        vals = []
        for n in (1, 2, 3):
            name = f"r3-{s * 10 + n}-run3"
            try:
                d = _campaign_scores(name)
            except FileNotFoundError:
                continue
            sc = type_scores(d)
            ts = sorted(set(sc.index) & set(base.index))
            vals.append({"noise_seed": n, **rho(sc[ts], base[ts])})
        ok = [v["spearman"] for v in vals if v["spearman"] is not None]
        per[s] = {"runs": vals, "mean_spearman": float(np.mean(ok)) if ok else None}
    xs = [(s / 100, per[s]["mean_spearman"]) for s in (5, 10, 20) if per[s]["mean_spearman"] is not None]
    eq = None
    if cross_fly is not None and xs:
        if cross_fly > xs[0][1]:
            eq = "below 5 %"
        elif cross_fly < xs[-1][1]:
            eq = "above 20 %"
        else:
            for (x0, y0), (x1, y1) in zip(xs, xs[1:]):
                if y1 <= cross_fly <= y0:
                    eq = x0 + (y0 - cross_fly) * (x1 - x0) / (y0 - y1) if y0 != y1 else x0
                    break
    return {"by_sigma_percent": per, "cross_fly_spearman": cross_fly, "noise_level_matching_cross_fly": eq}


def r4() -> dict:
    d = _campaign_scores("r4-run3")
    left, right = type_scores(d[d["arm"] == "R4L"]), type_scores(d[d["arm"] == "R4R"])
    ts = sorted(set(left.index) & set(right.index))
    return {"types": len(ts), "left_vs_right": rho(left[ts], right[ts]),
            "top10_overlap": topk(left[ts], right[ts], 10), "top30_overlap": topk(left[ts], right[ts], 30)}


def main() -> None:
    what = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    if what == "r1":
        res = r1()
    elif what == "r2":
        res = r2()
    elif what == "r3":
        r1p = OUT / "R1.json"
        cf = json.loads(r1p.read_text())["all"]["spearman"] if r1p.exists() else None
        res = r3(cf)
    else:
        res = r4()
    with open(OUT / f"{what.upper()}.json", "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, indent=1, default=str) + "\n")
    print(json.dumps(res, default=str)[:1500])


if __name__ == "__main__":
    main()
