"""Replicates the ranking rule of extra/scripts/tournament.py:294-302 / merge_rounds.py:41-47 verbatim."""
import numpy as np
KEYS = ("S1_A_over_full","S2_C_heldout","S3_D_micro_gain","S4_E_ratio","S5_K_r2_rff","S6_dim_rate","S7_abstention","S8_sharing_correct")
LOW = {"S1_A_over_full","S2_C_heldout","S3_D_micro_gain","S4_E_ratio"}
def rank(profiles, elig):
    ranks = {m: [] for m in elig}
    for key in KEYS:
        vals = {m: profiles[m].get(key, float("nan")) for m in elig}
        order = sorted(elig, key=lambda m: (np.inf if not np.isfinite(vals[m]) else (vals[m] if key in LOW else -vals[m])))
        for r, m in enumerate(order):
            ranks[m].append(r + 1)
    return {m: float(np.mean(v)) for m, v in ranks.items()}
# (a) four IDENTICAL candidates, pilot round (S8 = NaN for all: --pilot sets skip_shared)
prof = {"S1_A_over_full":1.2,"S2_C_heldout":0.9,"S3_D_micro_gain":0.02,"S4_E_ratio":0.01,"S5_K_r2_rff":0.8,"S6_dim_rate":0.5,"S7_abstention":0.75,"S8_sharing_correct":float("nan")}
P = {m: dict(prof) for m in ["m_a","m_b","m_c","m_d"]}
print("(a) identical profiles, list order a,b,c,d:", rank(P, ["m_a","m_b","m_c","m_d"]))
print("    same, list order d,c,b,a:        ", rank(P, ["m_d","m_c","m_b","m_a"]))
# (b) S2 NaN for a method that abstains on every held-out intervention (C ratio NaN -> excluded from median; if all NaN -> ranked last)
# (c) S6/S7 coarse: pilot has few non-compressible systems -> S7 in {0.5*(r + 1-fa)}
# (d) an irrelevant third candidate changes the order of two others (rank aggregation is not IIA)
P2 = {"X": dict(prof, S1_A_over_full=1.0, S2_C_heldout=0.80, S3_D_micro_gain=0.05),
      "Y": dict(prof, S1_A_over_full=1.1, S2_C_heldout=0.85, S3_D_micro_gain=0.01)}
print("(d) X vs Y only:", rank(P2, ["X","Y"]))
P2["Z"] = dict(prof, S1_A_over_full=1.05, S2_C_heldout=0.82, S3_D_micro_gain=0.00)
print("    with Z added:", rank(P2, ["X","Y","Z"]))
print("(d') X vs Y, list order Y,X:", rank(P2, ["Y","X"]))
# (e) Y better than X on 3 of 3 differing metrics by tiny margins but listed last; 5 tied metrics
P3 = {"X": dict(prof), "Y": dict(prof, S1_A_over_full=1.19, S2_C_heldout=0.89, S3_D_micro_gain=0.019)}
print("(e) Y strictly better on S1-S3, tied elsewhere; order X,Y:", rank(P3, ["X","Y"]))
