"""Planning numbers and frozen type sets stated in PREREG v6 before any BANC screen (RUN6_PROMPT section 6: "state its power or its
smallest attainable p before running"; audit findings 1, 3, 7, 8, 10). Uses only the first two animals' locked tables (post hoc data),
BANC's annotations (allowed by hard limit 2) and simulated statistics; reads no BANC result (none exists) and no BANC wiring.

Outputs: `gates_v6/TYPE_SETS_v6.json` (every annotation-only type set the tests use; the analysis reads it) and
`gates_v6/PLANNING_v6.json`.

    uv run --project ledger --no-sync python ledger/scripts/prereg6_planning.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger import agree as AG  # noqa: E402
from brainir_ledger import banc as B  # noqa: E402

RNG = 20261699
C8_ALL = ["DNa07", "DNb08", "DNg100", "DNg54", "DNg63", "DNit013", "DNp02", "DNp41", "DNp63", "DNxl101", "DNxl102", "DNxl110", "DNxl121"]


def type_sets() -> dict:
    mc = pd.read_csv(RESEARCH / "pertype_v1" / "match_confidence.csv")
    b1r = set(pd.read_csv(RESEARCH / "pertype_v1" / "B1r.csv")["manc_type"])
    b2r = set(pd.read_csv(RESEARCH / "pertype_v1" / "B2r.csv")["manc_type"])
    bc = B.match_confidence()
    bg, bh = set(bc["manc_type"]), set(bc.loc[bc["confidence"] == "high", "manc_type"])
    same = set(bc.loc[bc["same_name"], "manc_type"])
    mh = set(mc.loc[mc["confidence"] == "high", "manc_type"])
    mm = b1r & set(mc["manc_type"])
    base = {"three_animal": b1r & mh & bh, "manc_banc_high": b1r & bh, "manc_banc_all": b1r & bg, "mcns_banc_high": b2r & mh & bh,
            "mcns_banc_all": b2r & bg, "manc_mcns_high": mm & mh, "manc_mcns_all": mm, "three_animal_same_name": b1r & mh & bh & same}
    out = {"rule": "PREREG v6 G5 (annotation-only; type lists sorted by MANC type name; the '_noDNg100' sets carry Part C's words)"}
    for k, v in base.items():
        out[k] = sorted(v)
        out[k + "_noDNg100"] = sorted(v - {"DNg100"})
    out["C8"] = {"with_DNg100": sorted(C8_ALL), "primary": sorted(set(C8_ALL) - {"DNg100"}),
                 "without_DNb08": sorted(set(C8_ALL) - {"DNg100", "DNb08"})}
    return out


def _ranks(M):
    return stats.rankdata(M, axis=-1)


def _rho_rows(a, b):
    a = a - a.mean(-1, keepdims=True)
    b = b - b.mean(-1, keepdims=True)
    return (a * b).sum(-1) / np.sqrt((a * a).sum(-1) * (b * b).sum(-1))


def c6_pooling(sA, sB, sT, n_boot=1000, seed=0) -> dict:
    """C6 as revised (audit finding 1): d_M = rho(mean(A, B), T) - rho(A, T), d_C = rho(mean(A, B), T) - rho(B, T), same resamples."""
    rng = np.random.default_rng(seed)
    n = len(sA)
    idx = rng.integers(0, n, size=(n_boot, n))
    P = _ranks((sA[idx] + sB[idx]) / 2)
    A, Bb, T = _ranks(sA[idx]), _ranks(sB[idx]), _ranks(sT[idx])
    rp = _rho_rows(P, T)
    dM, dC = rp - _rho_rows(A, T), rp - _rho_rows(Bb, T)
    lo = lambda x: float(np.nanpercentile(x, 2.5))  # noqa: E731
    return {"dM_lo": lo(dM), "dC_lo": lo(dC), "helps": bool(lo(dM) > 0 and lo(dC) > 0)}


def c6_planning(ts: list[str]) -> dict:
    b1r = pd.read_csv(RESEARCH / "pertype_v1" / "B1r.csv").set_index("manc_type")["score"].reindex(ts).to_numpy(float)
    b2r = pd.read_csv(RESEARCH / "pertype_v1" / "B2r.csv").set_index("manc_type")["score"].reindex(ts).to_numpy(float)
    rng = np.random.default_rng(RNG)
    null = [c6_pooling(b1r, b2r, rng.permutation(b2r), seed=i)["helps"] for i in range(40)]
    r_ab = float(stats.spearmanr(b1r, b2r).statistic)
    power = {}
    for r in (0.25, 0.37, 0.5):
        cov = np.array([[1, r_ab, r], [r_ab, 1, r], [r, r, 1]])
        hits = []
        for i in range(150):
            x = rng.multivariate_normal(np.zeros(3), cov, size=len(ts))
            hits.append(c6_pooling(x[:, 0], x[:, 1], x[:, 2], seed=1000 + i)["helps"])
        power[f"r_to_banc_{r}"] = round(float(np.mean(hits)), 3)
    exp = {f"{r}": round(float((2 * r / np.sqrt(2 * (1 + r_ab))) - r), 3) for r in (0.25, 0.37, 0.5)}
    return {"statistic": "d_M = rho(mean(MANC, MaleCNS), BANC) - rho(MANC, BANC); d_C likewise with MaleCNS; 'pooling helps' iff both "
                         "95 % lower ends > 0 (same type resamples)",
            "n_types": len(ts), "r_manc_mcns": round(r_ab, 3),
            "expected_gain_if_r_to_banc": exp,
            "null_check": {"what": "BANC replaced by B2r shuffled over types (no information), 40 shuffles, 1,000 resamples each",
                           "share_pooling_helps": round(float(np.mean(null)), 3)},
            "power_simulated": {"what": "trivariate normal, r(MANC, MaleCNS) as observed, equal r to BANC, 150 data sets x 1,000 resamples; "
                                        "ignores the ties of real scores (optimistic)", **power}}


def c8_critical(n: int, n_perm: int = 400_000, seed: int = RNG) -> float:
    rng = np.random.default_rng(seed)
    base = np.arange(n, dtype=float)
    P = np.argsort(rng.random((n_perm, n)), axis=1).astype(float)
    r = _rho_rows(np.broadcast_to(base, P.shape), P)
    return float(np.quantile(r, 0.95))


def c8_power(n: int, crit: float, rhos=(0.3, 0.5, 0.7), n_sim=4000, seed=RNG) -> dict:
    rng = np.random.default_rng(seed)
    out = {"n": n, "critical_rho_one_sided_0.05": round(crit, 3)}
    for rho in rhos:
        r = 2 * np.sin(np.pi * rho / 6)
        x = rng.multivariate_normal([0, 0], [[1, r], [r, 1]], size=(n_sim, n))
        rr = _rho_rows(_ranks(x[..., 0]), _ranks(x[..., 1]))
        out[f"power_at_rho_{rho}"] = round(float(np.mean(rr >= crit)), 3)
    out["note"] = "no ties assumed; BANC scores of 0 tie and lower the power further"
    return out


def c4_planning(sets: dict) -> dict:
    out = {}
    for name, f, key in (("B1r", "B1r.csv", "manc_banc_high_noDNg100"), ("A1", "A1.csv", "manc_banc_high_noDNg100"),
                         ("B2r", "B2r.csv", "mcns_banc_high_noDNg100")):
        s = pd.read_csv(RESEARCH / "pertype_v1" / f).set_index("manc_type")["score"]
        ts = sets[key]
        N, nx = len(ts), int((s.reindex(ts).fillna(0) >= 0.5).sum())
        rows = {}
        for nb in (15, 25, 35):
            ks = [k for k in range(nx + 1) if stats.hypergeom.sf(k - 1, N, nb, nx) < 0.05]
            kc = min(ks) if ks else None
            rows[f"n_banc_drivers_{nb}"] = {"chance": round(nx * nb / N, 2), "k_needed": kc,
                                            **{f"power_if_share_{p}": (None if kc is None else round(float(stats.binom.sf(kc - 1, nx, p)), 3))
                                               for p in (0.3, 0.5)}}
        out[name] = {"set": key, "N": N, "n_x_drivers": nx, **rows}
    return out


def wiring_reference(ts: list[str]) -> dict:
    """Audit finding 7: the two-step signed count per type (run 3's S2 baseline: signed two-step paths from the type's members to the
    front-leg motor neurons), MANC against MaleCNS, on the three-animal set without DNg100 (post hoc; the BANC side runs after the freeze)."""
    import scipy.sparse as sp  # noqa: PLC0415

    from brainir_ledger import baselines as BL  # noqa: PLC0415
    from brainir_ledger import mirror as MR  # noqa: PLC0415

    fm, fc = MR.fly("MANC"), MR.fly("MaleCNS")
    s2m = BL.compute(fm.C, sp.csr_matrix(fm.net.W, dtype=float), fm.readout, fm.groups, []).set_index("manc_type")["S2_twohop_signed"]
    s2c = BL.compute(fc.C, sp.csr_matrix(fc.net.W, dtype=float), fc.readout, fc.groups, []).set_index("manc_type")["S2_twohop_signed"]
    rho = AG.spearman(s2m.reindex(ts).to_numpy(float), s2c.reindex(ts).to_numpy(float))
    return {"S2_twohop_signed_spearman_MANC_MaleCNS": round(float(rho), 3), "n_types": len(ts),
            "caveat_floor": 0.71, "caveat_floor_source": "the lowest of run 4's seven wiring summaries across sides and animals (WIRING_A4.json)"}


def main() -> None:
    sets = type_sets()
    (RESEARCH / "gates_v6" / "TYPE_SETS_v6.json").write_text(json.dumps(sets, indent=1) + "\n")
    ts = sets["three_animal_noDNg100"]
    out = {"type_set_sizes": {k: len(v) for k, v in sets.items() if isinstance(v, list)},
           "C4": c4_planning(sets), "C6": c6_planning(ts),
           "C8": {"primary": c8_power(12, c8_critical(12)), "with_DNg100": c8_power(13, c8_critical(13)),
                  "without_DNb08": c8_power(11, c8_critical(11))},
           "C7": {"rule": "n* = 4 (1 - rbar) / rbar; n* = 1 if rbar >= 0.8; infinity if rbar <= 0",
                  "n_star_if_rbar": {f"{x:.2f}": round(4 * (1 - x) / x, 1) for x in (0.2, 0.3, 0.38, 0.5, 0.6, 0.8)}},
           "wiring_reference": wiring_reference(ts)}
    (RESEARCH / "gates_v6" / "PLANNING_v6.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
