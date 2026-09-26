**Reading the self-audit.**

*Science checks.* 16 of 19 pass. Three fail, and each failure is a finding reported in the sections above:
- **Q11, implementation memorisation.** Leave-one-implementation-out adaptation never beats a fit from scratch: 0 of 3 comparisons,
  worse in 2 of 3. The locked method's adaptation code also crashes when sharing is rejected. Nothing supports an
  implementation-independent latent law.
- **Q12, seed stability.** k agrees across seeds in only a third of the tested systems (median min R^2 0.80). The representation is
  not stable enough to be called unique.
- **Q13, parameter uncertainty.** On the parameter trap H the method claims a compact causal state with k = 2 where the truth is 1.
  Two of three real full networks are not closed. The latent's parameter-identity probe decodes the hidden parameter draw well
  above chance (0.30-0.81 against 0.17). Parameter uncertainty is therefore partly carried in the state rather than cleanly
  separated from it.

The 16 passes include:
- time, stimulus and output-history shortcuts ruled out (Q1-Q3);
- no future leak into the encoder (Q4, probe);
- neuron-order equivariance (Q10, permutation probe);
- unrelated systems correctly not aligned (Q17);
- no "compact" claim on the two non-compressible controls (Q18; abstention recall is only 1 of 2, and 52 % of all systems are
  neither abstained on nor interventional and closed);
- intervention fidelity not collapsing on unseen perturbation types relative to in-distribution ones (Q8);
- the counterexample search not breaking the model immediately on most systems (Q19; fraction 0.17 < 0.5, although the worst
  cases are extreme, sections 9 and 16).

**Q16 ("is PCA equally good?") passes on its synthetic criterion but not on the real systems.** On the synthetic FINAL suite,
PCA with the method's k is as good in both prediction and interventions on only 8 % of the systems. On the REAL systems, a
PCA latent of the same dimension predicts the held-out readout BETTER than the locked method on 9 of 10 systems:
- full networks: 0.018 vs 0.024, 0.24 vs 0.51, 0.004 vs 0.006;
- mechanisms: up to 0.024 vs 0.21.

The locked method's compact state therefore adds no predictive value over PCA on the real circuits. On the synthetic suite
the dimension is over-estimated on 35 % of the systems (Q5).

Q8 and Q19 pass on relative criteria. They do not contradict the absolute finding that real held-out C never falls below the
no-effect value (section 14).

*Integrity checks.* I3, I8 and I11 fail as written, and in all three the checked property holds; the evidence is in each row:
- **I3:** the benchmark tag moved to the re-lock tags;
- **I8:** the reference-cache directory is counted as a Level C attempt;
- **I11:** the public bundle directory is missing from the allowlist.

The checks are hashed with the benchmark and were not edited.
