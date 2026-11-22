Verdict: freeze after fixes

# PREREG v4 audit (fresh reviewer, RUN4_PROMPT section 5 "Freeze")

Audited at commit 5826b84. Tests `test_v4_*` and `test_lock4`: 57 passed. Wiring-only checks on both real flies (sets and structure;
no simulation, no weight correlation, no score). Fix finding 1 before the tag, and the MAJOR findings too.

## Mirroring code audit (G4, G8, B2.1, B3.1)

**What holds (MANC and MaleCNS):**
- m is an involution on the extended slots.
- m maps the right read-out slots present in W exactly onto the left read-out slots present in M (72/72 and 63/63). No matched
  front-leg motor neuron has a non-motor-neuron partner.
- "All five classes" gives M exactly (counts, signs, sizes, presence), and "nothing" gives W exactly.
- In all ten Block 3 hybrids, every absent slot has no row or column entry, so it is silent: theta > 0 and r0 = 0 keep it at 0.
- G8: src[i] = src[m(i)] for every slot, so the parameters of L on M are a relabelling of those of R on W. The no-pairing case
  reproduces `sample_neuron_params` bit for bit.
- The workflow and runner copies differ from run 3's only in the tag prefix, the runner and the hex key.

**What fails:** findings 1 and 2. The synthetic tests miss both, because their fly has no unmatched member of a stimulated type
and no cross-type pair.

## Findings

1. **BLOCKER. "L on M = R on W" is false for some types** (B2.1; `mirror.left_slots` mirror.py:385-388; gha4.py:224-226).
   - **What I found.** The stimulated set of L on M, `stimulated(left_slots(t), M.present)`, differs from m(R_t) for 44 of 250
     MaleCNS types and 2 of 308 MANC types (DNit005, DNxn108).
   - **Cause.** MaleCNS half-fly groups use B2's MANC types, but the map pairs neurons by MaleCNS `group`. Example: "DNfl018" =
     a DNge100 on the left (group 12422) plus a DNge057 on the right (group 15254), and each of them is paired with a DNfl020
     member. In all, 53 right members of 34 types are paired with a member of another type.
   - **Consequences.**
     - B2.3(ii) will probably fail on MaleCNS, and the cure (a new slot definition or map) is a rule change, which X4 forbids
       after the tag. On MANC, the tolerance may pass the gate with 2 wrong types.
     - Block 2-3 hybrids of these types stimulate something other than the mirror of R.
     - Part A's MaleCNS-L vs MaleCNS-R compares non-homologs (by MaleCNS's own groups). The uncorrected-types check misses this:
       27 of the 53 pairs involve no corrected neuron.
   - **Fix.** Either pair members within their half-fly type first, or use only the types with m(R_t) = L_t plus its ghosts.
     - The first makes "L on M = R on W" hold. But for MaleCNS types whose within-type pairs are not MaleCNS `group` pairs, class
       1-2 differences are then differences between non-homologs.
     - So flag those types, and report Part A and Blocks 2-3 with and without them. Say now which is primary.
     - Either way, assert S_M == m(R_t) in `build_b2`, `build_b3` and `build_fl`.

2. **MAJOR. Block 2 hybrids create neurons that exist in neither W nor M** (`columns_from` mirror.py:368-382; G4 line 101).
   - **What I found.** Only columns, size, sign and presence are swapped; rows (inputs) are not. This matters for listed slots
     whose presence flips (unmatched members and their ghosts).
   - In H_own:
     - a now-present slot's inputs differ from its source network M (MANC 8 types, MaleCNS 7);
     - a now-absent slot keeps its inputs (6 / 9).
   - In H_rest: present slots whose inputs differ from W (6 / 9), and absent slots with input (8 / 7).
   - So G4's "ghost and absent slots have no input" is false here, and absent but driven slots count in the tuner's active totals.
   - **Fix.** For these slots, take rows as well as columns from the network that supplies their presence. Add a test with an
     unmatched DN member.

3. **MAJOR. G7's words lean towards the hypothesis** (lines 127-128; agree.py:452-461).
   - **What I found.** Anything not "at the ceiling" is called "a real gap", even when the ratio's interval contains 1 (e.g.
     0.85 [0.6, 1.1]). This word decides A7, whether closures are reported, and B3.3's "needed".
   - **Fix.** Add "inconclusive" (point < 0.90 and upper end >= 1.00). Call it "a real gap" only when the upper end < 1.00, and
     state now which branch "inconclusive" takes in A7.

4. **MAJOR. C6 criterion 2 has no floor on the ceiling** (line 379; reliability_v2_bc.py:442, 450).
   - **What I found.** A fix that makes the screen noisy lowers c and can pass rho_x / c >= 0.80 on tiny numbers. G7's c < 0.2
     "not judged" rule is not applied.
   - **Fix.** Criterion 2 fails whenever its c < 0.2, and rho_x is reported beside the ratio.

5. **MAJOR. The robust model has three definitions.**
   - Line 387 says "C2 or C3". The prompt says any passing fix. `cmd_c` (bc.py:496) includes fixes 1 and 2.
   - `forward_v1.flags` computes no flags for fixes 1 and 2 (line 228), so they could never enter E6. `robust_scores` has no
     fix 9 path.
   - **Fix.** Adopt the prompt's definition in the text and implement fixes 1, 2 and 9 in `forward_v1`.

6. **MAJOR. Fixes 1 and 2 at a gain other than 1 are scored on gain-1 runs** (C4: "used for every run of that fix";
   bc.py:366-390 reuses Part A traces and Block 1 sweeps).
   - `build_cx(k=2)` raises at `apply_fix("2")` (gha4.py:584).
   - This case is plausible: summing motor neurons that fire in antiphase can lower DNg100's pooled score.
   - **Fix.** State that such a fix gets new half-fly and rewired runs at its gain, and implement that.

7. **MAJOR. The forward ledger's third source can be cut after the fact** (X9 lines 495-498 against E2 line 412).
   - **What I found.** The robust model's whole-type exam 1 screen (the dx campaign) is an input to E2. But "Part D" is on the
     drop list, while the forward ledger is never dropped. A budget call made after Part C could remove an unwelcome robust model.
   - **Fix.** That campaign belongs to Part E and is never dropped.

8. **MAJOR. MANC's side threshold was set after seeing the data, with no sensitivity analysis** (G3 lines 73-77; Part Q).
   - **What I found.** The 90 % threshold was chosen after MANC's 92.4 % was seen, and it keeps the annotations and R4's reuse. 48
     of 308 MANC matched types contain a DN whose root side differs from its output side.
   - **Fix.** Declare now that every MANC Part A left-right analysis is also reported on the 260 types without such a member.

9. **MAJOR. X4 does not say when analysis code may be amended** (line 470).
   - **What I found.** Results are decrypted on the Mac before the analysis scripts run, and several rules exist only in code
     (finding 13). A "bug fix" could therefore follow a look at raw scores.
   - **Fix.** Allow amendments to analysis code (`reliability_v2*.py`, `agree.py`, `forward_v1.py`, `rescore_v4.py`) only before
     the first `collect4` of the campaigns they read. Report any later amendment with both outputs.

10. **MINOR. B3.1's text does not match the code** (lines 275-276).
    - The text restricts classes 1-2 to entries with both ends matched. The code also classes there the entries between a
      self-mapped and a matched neuron (MANC 3,324, MaleCNS 6,836), and "all five = M" needs this.
    - **Fix.** Write "each matched or self-mapped, not both self-mapped".

11. **MINOR. B2.3(i)'s bit-for-bit builder check is not in `cmd_b2`**, which compares only 50 digests.
    - **Fix.** Record a check that hybrid(nothing) = W and hybrid(all) = M as a gate file before Block 2 is read. Both hold on both
      flies.

12. **MINOR. B1.3 and B1.4 differ from the code** (bc.py:172-191).
    - The code keeps only types accepted in all 8 seeds on both sides, and only when there are at least 10 of them. The text says
      per-seed skipping, counted.
    - "The transplant" becomes two candidates.
    - "Procedure share" is the maximum of four noisy closures, and "closes the whole gap" holds if any of them does.
    - **Fix.** Align the text with the code and add a winner's-curse caveat.

13. **MINOR. Some thresholds exist only in code; align them with the text or write them into it.**
    - The uncorrected-types analysis covers only MaleCNS L vs R, and only with at least 10 types (reliability_v2.py:169). G3
      promises "every Part A analysis".
    - A3 runs Wilcoxon only with at least 10 non-tied types (:187).
    - The per-current comparisons and copy1-vs-L on W use 2,000 resamples (bc.py:131, 338), not G6's 10,000.
    - B3.3 "excludes 0" is coded as lower end > 0 (bc.py:299), and "which pairs disagree" is not implemented.

14. **MINOR. Dropped MaleCNS DN members still enter the mirror map.**
    - 17 of the 25 keep their unreliable annotated side, get matched and can take partners.
    - **Fix.** Map them to themselves.

15. **MINOR. G7 says "the same Y", but B1.2 and B4.4 change both screens** (`closure(..., Y_after)`). Write that form into G7.

16. **MINOR. C6.4 is asymmetric and its "few = 2" comes from another procedure.**
    - SR uses only the left pair, while criterion 2 averages both pairs.
    - "Few = 2" comes from whole-type B1 controls on 321 types.
    - **Fix.** State that if the unfixed one-sided rewired control has more than 2 drivers, criterion 4 cannot be met by any fix.

17. **MINOR. Part E loose ends.** G10 says no randomness, but E9 uses 20261461. E3's "at least 15 with both classes" is ambiguous.
    E5's "authors' model" flags come from our re-implementation. One kit line is LexA, which the UAS protocol does not fit.

18. **MINOR. B4.5 is a failure-to-reject test** (a noisier model passes more easily). Also report observed minus copy-vs-copy, with
    an interval.

19. **MINOR. B5 is incomplete.** It does not place a MaleCNS type-to-type connection that no MANC member pair carries.

20. **MINOR. `ledger/scripts/posthoc/*.py` (`rescore_v4.py`) is not hashed by the prereg lock.** `lock2.globs` uses
    `REPO.glob("ledger/scripts/*.py")`, which does not recurse. Add the folder to lock4's code globs before the tag.
