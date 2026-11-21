# Reliability study v1 (PREREG v3 Part R; RUN3_PROMPT section 8) — descriptive, no labels

Question: when the same procedure gives different answers for two flies, is that the animals, the reconstruction or the simulation?
Type score = run 2's `primary_score` (mean of usable replicate scores, 0 if none); agreement = Spearman over types.

| test | what is compared | n types | Spearman |
|---|---|---|---|
| R1 ceiling | same fly, same members, seeds 0-7 vs 8-15 (MANC B1r / MaleCNS B2r) | 321 / 328 | 0.86 / 0.93 |
| R1 | MANC (B1r) vs MaleCNS (B2r), all common types | 310 | 0.37 |
| R1 | ... types non-zero in either fly | 240 | 0.15 |
| R1 | ... types matched by curated body match | 303 | 0.37 |
| R2 | wiring baselines S1-S7, MANC vs MaleCNS (same types) | 310 | 0.78-0.97 (S1 0.88, S2 0.78, S3 0.95, S4 0.96, S5 0.97, S6 0.95, S7 0.82) |
| R3 | MANC vs MANC with 5 % multiplicative weight noise (3 noise seeds; seeds 0..3) | 321 | 0.82 (0.81-0.83) |
| R3 | ... 10 % | 321 | 0.76 (0.71-0.79) |
| R3 | ... 20 % | 321 | 0.65 (0.59-0.72) |
| R4 | left members (left MN read-out) vs right members (right read-out), one fly | 308 | 0.43 |

R1 also: band agreement 0.63 (kappa 0.26); top-10 overlap 0.10, top-30 overlap 0.27. R4: top-10 overlap 0.20, top-30 0.37.
Noise level at which agreement equals the cross-fly 0.37: above 20 % (interpolation impossible; every level agrees more).

**Reading (descriptive).** The two flies' wiring summaries agree closely (0.78-0.97). The simulated screen reproduces itself
across seeds (0.86-0.93, seeds 0-7 against 8-15) and averages 0.65 or more under up to 20 % random multiplicative weight noise
(lowest single noise seed 0.59; 4-seed means against the unperturbed seeds 0-3). Yet the two flies' simulated type scores agree only at 0.37, and the left and right
members of the same types in one fly, each side read out on its own front-leg motor neurons (seeds 0-3), agree only at 0.43.

Two limits. R4 has no matched ceiling: no split-half of the one-sided screen was run, and halving both the stimulated group and the
read-out may by itself lower agreement. R3 tests only independent noise on existing synapse counts, not missing or extra synapses or
neurons. Within those limits: a difference between animals is not needed to produce disagreement as low as the cross-fly one, since
the two sides of one fly disagree almost as much; random count noise of up to 20 % is too small to produce it; and wiring summaries
that agree closely across the flies go with simulated scores that do not. One hypothesis, not tested here, is that the screen
amplifies structured differences between near-copies of a circuit (which partners a type contacts) into different rhythm calls.

Files: `R1.json`, `R2.json`, `R3.json`, `R4.json`; code `ledger/scripts/reliability_v1.py` (one recorded amendment, LOG L94),
campaigns `r3-<k>-run3`, `r4-run3` (GitHub, run 3 runner).
