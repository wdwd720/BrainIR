"""Planning numbers stated in PREREG v6 before any BANC screen (RUN6_PROMPT section 6: "state its power or its smallest attainable p
before running"; C6: "state the expected size of the gain from the Spearman-Brown formula"). Uses only the first two animals' locked
per-type tables (post hoc data) and simulated statistics; reads no BANC result (none exists). Output: `gates_v6/PLANNING_v6.json`.

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
from brainir_ledger import banc as B  # noqa: E402

RNG = 20261699


def three_animal_set() -> list[str]:
    mc = pd.read_csv(RESEARCH / "pertype_v1" / "match_confidence.csv")
    b1r = pd.read_csv(RESEARCH / "pertype_v1" / "B1r.csv")
    c = B.match_confidence()
    return sorted(set(b1r["manc_type"]) & set(mc.loc[mc["confidence"] == "high", "manc_type"]) & set(c.loc[c["confidence"] == "high", "manc_type"]))


def spearman_power(n: int, rhos=(0.3, 0.5, 0.7), alpha=0.05, n_sim=20000, n_perm=2000, seed=RNG) -> dict:
    """Power of the one-sided Spearman permutation test (C8) for n types under a bivariate normal with Pearson r chosen so that the
    population Spearman correlation is rho (r = 2 sin(pi rho / 6)); the permutation null approximated by its exact large-sample t form
    is replaced here by the permutation distribution of n ranks (n_perm draws, computed once)."""
    rng = np.random.default_rng(seed)
    base = np.arange(n, dtype=float)
    null = np.array([stats.spearmanr(base, rng.permutation(base)).statistic for _ in range(n_perm)])
    crit = float(np.quantile(null, 1 - alpha))
    out = {"n": n, "critical_rho_one_sided_0.05": round(crit, 3)}
    for rho in rhos:
        r = 2 * np.sin(np.pi * rho / 6)
        cov = [[1, r], [r, 1]]
        hits = 0
        for _ in range(n_sim // 10):
            x = rng.multivariate_normal([0, 0], cov, size=n)
            hits += stats.spearmanr(x[:, 0], x[:, 1]).statistic > crit
        out[f"power_at_rho_{rho}"] = round(hits / (n_sim // 10), 3)
    return out


def hypergeom_power(N: int, n_x: int, n_b: int, true_shares=(0.2, 0.3, 0.5), alpha=0.05) -> dict:
    """C4: the smallest overlap k with P(K >= k) < alpha under the hypergeometric null, and the power when each of X's drivers is a
    BANC driver with the given probability (k ~ Binomial(n_x, share))."""
    ks = [k for k in range(n_x + 1) if stats.hypergeom.sf(k - 1, N, n_b, n_x) < alpha]
    kc = min(ks) if ks else None
    out = {"N": N, "n_x": n_x, "n_banc_drivers_assumed": n_b, "chance_expectation": round(n_x * n_b / N, 2), "k_needed": kc,
           "smallest_attainable_p": float(stats.hypergeom.pmf(n_x, N, n_b, n_x)) if n_b >= n_x else float(stats.hypergeom.sf(n_b - 1, N, n_b, n_x))}
    for s in true_shares:
        out[f"power_if_share_{s}"] = None if kc is None else round(float(stats.binom.sf(kc - 1, n_x, s)), 3)
    return out


def main() -> None:
    ts = three_animal_set()
    b1r = pd.read_csv(RESEARCH / "pertype_v1" / "B1r.csv").set_index("manc_type")["score"]
    b2r = pd.read_csv(RESEARCH / "pertype_v1" / "B2r.csv").set_index("manc_type")["score"]
    r = float(stats.spearmanr(b1r.reindex(ts), b2r.reindex(ts)).statistic)
    gain = r * (np.sqrt(2 / (1 + r)) - 1)
    out = {"three_animal_set_n": len(ts),
           "C6": {"rule": "Spearman-Brown under exchangeable animals: corr(mean of two, third) = r sqrt(2 / (1 + r)); expected gain over "
                          "one animal = r (sqrt(2 / (1 + r)) - 1)",
                  "r_planning": round(r, 3), "r_source": "full-seed Spearman of B1r and B2r type scores on the three-animal set (post hoc)",
                  "expected_gain": round(float(gain), 3),
                  "expected_gain_if_r": {f"{x:.1f}": round(float(x * (np.sqrt(2 / (1 + x)) - 1)), 3) for x in (0.2, 0.3, 0.4, 0.5, 0.6)}},
           "C8": spearman_power(12), "C8_with_DNg100": spearman_power(13),
           "C4": {"B1r_high": hypergeom_power(len(ts), 11, 20), "B1r_high_nb30": hypergeom_power(len(ts), 11, 30),
                  "B2r_high": hypergeom_power(len(ts), 23, 20)},
           "C7": {"rule": "n* = 4 (1 - rbar) / rbar (Spearman-Brown: pooled agreement of n animals = n rbar / (1 + (n - 1) rbar) >= 0.8)",
                  "n_star_if_rbar": {f"{x:.2f}": round(4 * (1 - x) / x, 1) for x in (0.2, 0.3, 0.38, 0.5, 0.6, 0.8)}}}
    p = RESEARCH / "gates_v6" / "PLANNING_v6.json"
    p.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
