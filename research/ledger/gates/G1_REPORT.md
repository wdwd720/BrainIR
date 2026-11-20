# Gate G1: the ledger tuner in single-neuron mode reproduces the saved screen B0

30 excitatory DNs drawn with `default_rng(20261124).choice(933, 30)` (positions in `G1_summary.json`) x 16 seeds = 480 jobs,
B0's configuration (lower bound 5, high-firing cap 100), pinned ledger image and numerics environment.

| check | result |
|---|---|
| usable flag equal to B0 | 480 / 480 |
| tuned current equal to B0 | 480 / 480 |
| number of tuning runs equal to B0 | 480 / 480 |
| score exactly equal (replicates usable in both) | 390 / 417 |
| largest absolute score difference | 0.00088 (none > 0.01) |

**Cause of the 27 small differences (pre-registered test, `G1_cause_summary.json`):** each differing job was re-run 8 times
WITHOUT the numerics environment (stock-like numerics, spread over Modal hosts). On AVX-512 hosts 62 of 95 re-runs equal
B0 exactly and none equals the pinned ledger result; on hosts without AVX-512 none equals B0 and 95 of 121 equal the
pinned result. 17 of the 27 jobs are reproduced exactly by some host. B0 was produced unpinned on a mix of host types
(Phase 1), so its replicates carry host-dependent last-bit numerics; the remaining non-reproductions are consistent with
other microarchitecture-specific kernels. **B0 remains a fair stand-in**: identical decisions (usability, currents,
tuning paths) and scores within 0.001. **G1: PASS** (exact on all decisions; score differences explained).
