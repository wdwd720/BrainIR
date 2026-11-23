"""PREREG v6 Part H (ALL POST HOC): the first two animals' hit-list overlap at cuts 0.3-0.6 (G2), the graded version (G3) and each pair's
agreement (G1), for four pairs (MANC first): tuned B1r x B2r, the authors' A1 x B2r, the original procedure K = 0 (B1-lo10 x B2) and
the sweep (dx-1 x ms), on the MANC-MaleCNS high (215) and all (310) type sets, each with and without DNg100.

    uv run --project ledger --no-sync python ledger/scripts/posthoc_v6.py [--no-sweep]   # -> research/ledger/posthoc_v6/

`--no-sweep` (a test before `ms-mcns-run6` exists) skips the sweep pair and writes nothing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger import agree as AG  # noqa: E402
from brainir_ledger import overlap6 as O6  # noqa: E402
from brainir_ledger import screens6 as S6  # noqa: E402

OUT = RESEARCH / "posthoc_v6"
CUTS = (0.3, 0.4, 0.5, 0.6)
POSTHOC = "POST HOC (PREREG v6 Part H: the first two animals were seen before these cuts and summaries were chosen)"
H16 = (list(range(8)), list(range(8, 16)))
H8 = (list(range(4)), list(range(4, 8)))


def type_sets() -> dict[str, list[str]]:
    mc = pd.read_csv(RESEARCH / "pertype_v1" / "match_confidence.csv")
    b1r = set(pd.read_csv(RESEARCH / "pertype_v1" / "B1r.csv")["manc_type"])
    common = sorted(b1r & set(mc["manc_type"]))
    high = sorted(set(common) & set(mc.loc[mc["confidence"] == "high", "manc_type"]))
    return {"high": high, "all": common}


def vectors(X: pd.DataFrame, types: list[str], halves) -> tuple:
    f = AG.type_scores(X, None, types)
    h1 = AG.type_scores(X, halves[0], types)
    h2 = AG.type_scores(X, halves[1], types)
    return f.to_numpy(), h1.to_numpy(), h2.to_numpy()


def pair_block(X, Y, types, halves) -> dict:
    sx, sx1, sx2 = vectors(X, types, halves)
    sy, sy1, sy2 = vectors(Y, types, halves)
    out = {"n_types": len(types), "agreement": AG.compare(X, Y, types, halves), "cuts": {}}
    for z in CUTS:
        out["cuts"][f"{z:.1f}"] = {"overlap": O6.overlap(sx, sy, sx1, sx2, sy1, sy2, z, names=types),
                                   "graded": O6.graded(sx, sy, sx1, sx2, sy1, sy2, z)}
    return out


def screens(include_sweep: bool = True) -> dict[str, tuple]:
    out = {"tuned_B1r_x_B2r": (S6.b1r(), S6.b2r(), H16), "authors_A1_x_B2r": (S6.a1(), S6.b2r(), H16),
           "original_K0_B1lo10_x_B2": (S6.k0_manc(), S6.k0_mcns(), H16)}
    if include_sweep:
        out["sweep_dx1_x_ms"] = (S6.sweep_manc(), S6.sweep_mcns(), H8)
    return out


def analyse(include_sweep: bool = True) -> dict:
    sets = type_sets()
    res = {"marking": POSTHOC, "type_sets": {k: len(v) for k, v in sets.items()}, "pairs": {}}
    for name, (X, Y, halves) in screens(include_sweep).items():
        res["pairs"][name] = {}
        for sname, ts in sets.items():
            for dng in ("with_DNg100", "without_DNg100"):
                t = ts if dng == "with_DNg100" else [x for x in ts if x != "DNg100"]
                res["pairs"][name][f"{sname}|{dng}"] = pair_block(X, Y, t, halves)
    return res


def _r(v, n=2):
    return "-" if v is None else f"{v:.{n}f}"


def report_md(res: dict) -> str:
    L = [f"# Part H: the first two animals' hit lists ({POSTHOC})", "",
         "Type sets: MANC-MaleCNS high-confidence (215) and all matched (310). X = MANC screen, Y = MaleCNS screen. k = drivers in both;",
         "chance = n_X n_Y / N; p = hypergeometric P(K >= k); OC ratio = cross-half overlap coefficient / within-animal overlap (95 % interval).", ""]
    for name, blocks in res["pairs"].items():
        L += [f"## {name} (POST HOC)", "", "| set | cut | n_X | n_Y | k | chance | p | k / n_X | OC ratio (interval) | AUROC Y for X drivers (within X, Y) |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for key, b in blocks.items():
            for z, c in b["cuts"].items():
                o, g = c["overlap"]["point"], c["graded"]["point"]
                ob = c["overlap"]["bootstrap_95"]["OC_ratio"]
                L.append(f"| {key} | {z} | {o['n_x']} | {o['n_y']} | {o['k']} | {_r(o['chance_expectation'])} | {_r(o['hypergeom_p'], 3)} | "
                         f"{_r(o['rate_x_in_y'])} | {_r(o['OC_ratio'])} ({_r(ob['lo'])}-{_r(ob['hi'])}) | {_r(g['auroc_y_for_x_drivers'])} "
                         f"({_r(g['within_x'])}, {_r(g['within_y'])}) |")
        L += ["", "| set | agreement ratio (interval) | words |", "|---|---|---|"]
        for key, b in blocks.items():
            a = b["agreement"]
            L.append(f"| {key} | {_r(a['primary']['ratio'])} ({_r(a['bootstrap']['interval']['ratio'][0])}-"
                     f"{_r(a['bootstrap']['interval']['ratio'][1])}) | {a['words']} (post hoc) |")
        L.append("")
    return "\n".join(L) + "\n"


def build() -> None:
    res = analyse(True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "H_posthoc.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    (OUT / "H_tables.md").write_text(report_md(res))
    man = {"marking": POSTHOC, "inputs_locked": ["research/ledger/pertype_v1 (LOCK_pertype_v1)", "research/ledger/predictions_v2/B1r, B2r",
                                                  "research/ledger/predictions/B1-lo10, B2 (LOCK_predictions_v1)", "authors' A1 (authors.py)"],
           "untracked_inputs": [S6.results_path("reliability_v2", "dx-1-run4", "MODAL").relative_to(RESEARCH.parents[1]).as_posix(),
                                S6.results_path("posthoc_v6", "ms-mcns-run6").relative_to(RESEARCH.parents[1]).as_posix()],
           "code": ["ledger/scripts/posthoc_v6.py", "ledger/src/brainir_ledger/overlap6.py", "ledger/src/brainir_ledger/screens6.py"]}
    (OUT / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n")
    print(json.dumps({k: len(v) for k, v in res["pairs"].items()}))


if __name__ == "__main__":
    if "--no-sweep" in sys.argv:
        r = analyse(False)
        b = r["pairs"]["tuned_B1r_x_B2r"]["high|with_DNg100"]
        print(json.dumps({"n": b["n_types"], "cut0.5": b["cuts"]["0.5"]["overlap"]["point"], "ratio": b["agreement"]["primary"]["ratio"]},
                         default=str)[:1500])
    else:
        build()
