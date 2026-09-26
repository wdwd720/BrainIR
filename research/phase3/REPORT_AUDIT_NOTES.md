**Reading the self-audit.** The table above shows each check's own status, as computed by the hashed `scripts/p3/self_audit.py`,
and its orchestrator note where one exists. The thresholds (`TH`) were fixed in the script at commit d056d35. The script is hashed in
the benchmark lock at tag `state-discovery-benchmark-v3-relock2`, before the method lock at 01:32 UTC and before any post-lock
evidence existed. The post-lock reviews (section 18.1) found that some checks do not test what the first draft said they test.
Those corrections are orchestrator notes; the checks were not edited.

*Science checks: as computed, 16 pass and 3 fail; as reported after the post-lock reviews, 15 pass, 3 fail and 1 n/a.*

The three failures are findings reported in the sections above:
- **Q11, implementation memorisation.** Leave-one-implementation-out adaptation never beats a fit from scratch: 0 of 3 synthetic
  comparisons, and worse in every computable real case (section 14). The locked method's adaptation code also crashes when sharing is
  rejected. Nothing supports an implementation-independent latent law.
- **Q12, seed stability.** k agrees across seeds on 4 of 8 synthetic and 2 of 10 real systems (median r2_min_mean 0.80 over the 18).
  The representation is not stable enough to be called unique.
- **Q13, parameter uncertainty.**
  - On the parameter trap H the method claims a compact causal state with k = 2 where the truth is 1.
  - Two of three real full networks are not closed.
  - The latent's parameter-identity probe decodes the hidden parameter draw well above chance (0.30-0.81 over the 10 real systems;
    0.33-0.58 on the full networks; chance 0.17).

  Parameter uncertainty is therefore partly carried in the state rather than cleanly separated from it.

Corrected readings of passing checks:
- **Q9 (capacity) is reported as n/a.** It passes only because nothing is shared: the method never returned a shared model, so no
  model with a different capacity exists to test.
- **Q16 ("is PCA equally good?"): the check's real-system evidence is void.** The check compared PCA-k's first A key (10 ms) with the
  method's verdict A (250 ms), and the first draft's "PCA-k predicts better on 9 of 10 real systems" came from that mismatch. At
  matched horizons, and at the primary 250 ms, PCA-k is significantly better on 2 of 10 systems (both on net2), the method on 6, with
  no clear difference on 2 (section 14). The check's pass rests on its synthetic criterion, which uses matched keys: PCA with the
  method's k is as good in both prediction and interventions on only 8 % of the FINAL systems.
- **Q8 tests one thing only:** whether fewer than 50 % of the FINAL systems have a held-out C no better than no effect (19 of 46 =
  41 %). It is not a held-out against in-distribution comparison. Its recorded real CIs are read at the first window (100 ms), not
  the primary 250 ms. On the real full networks the held-out C is no better than no effect on 3 of 3.
- **Q6** passes on the synthetic fraction not closed (22 %). On the real systems 7 of 10 are not closed, which would fail the same
  threshold.
- **Q5** is tested on synthetic systems only, where the native time step equals the model grid. The down-sampling of the real 1 ms
  data to the model grid (about 5 ms) is untested.
- **Q14** records a median of NaN because 4 real systems have no defined ratio; NaN > 3 is false, so it passes. Over the 6 finite
  ratios the median is 1.12, still a pass, but 2 of the 6 exceed 3: after held-out interventions the error is 5.8 and 6.7 times the
  unperturbed error on net1 mechanism b and net2 mechanism b.
- **Q17** passes because the 3 unrelated pairs are rejected, but the true implementation groups are not supported either (one
  untestable, one rejected), because the method never returns a shared law. The rejection does not discriminate.
- **Q18** passes because no compact claim is made on the two FINAL controls. However, the method abstains on only 1 of 2 (on the
  other it returns k = 3), and on review G's non-compressible G10 it rates "partially supported" with k = 1.
- **Q19** passes on the pooled fraction 0.17 over four sweeps (116 system-runs; 0.185 over the 108 searchable ones). Per sweep: FINAL
  effect 0.19, FINAL post 0.06, real hidden draws 0.30, real public draws 0.50. The real public-draw sweep alone reaches the fail
  threshold. Q19's recorded result is a re-run (10:02 UTC) with all four sweeps, which replaced the full run's Q19 (the hidden-draw
  sweep had not finished then).

The other passes stand as tested:
- time, stimulus and output-history shortcuts ruled out on their traps and controls (Q1-Q3). The stimulus-copy trap D's compact
  verdict is, however, not state-mediated (section 8);
- no future leak into the encoder (Q4);
- microstate equivalence fails on 15 % of the 40 testable FINAL systems, below the 50 % threshold (Q7). On the real systems it fails
  on net1 full and net3 full;
- neuron-order equivariance (Q10);
- every linear baseline is significantly worse than the method on at least one component, prediction (Q15). Against the
  comparator the paired S2-S5 differences are not significant (section 8).

*Integrity checks.* I3, I8 and I11 fail as written. In all three the checked property holds, and the evidence is in each row's
orchestrator note:
- **I3:** the benchmark tag moved to the re-lock tags;
- **I8:** the reference-cache directory is counted as a Level C attempt;
- **I11:** the public bundle directory is missing from the check's list of allowed top-level entries of the Modal fit volume.

The notes are the orchestrator's, not the checks' output. The checks are hashed with the benchmark and were not edited.
