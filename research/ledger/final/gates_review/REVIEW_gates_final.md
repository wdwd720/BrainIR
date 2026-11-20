# Gate review of the 22 locked prediction arms (run 1)

**Every locked arm passed the gates that apply to it and the independent review: yes.** Qualifications:
- G2 was met by investigation; B1 never reached 0.8.
- G1 is exact on decisions, not every score (prompt line 255 allows this).
- Eight controls were cleared only conditionally.
- B2 and B4 carry validity failures that no gate tests.

**My checks** (read-only; `verify_*.json` here):
- All 182 hashed files are in tag `ledger-predictions-v1` with locked hashes; none unhashed.
- All 15 simulated campaigns:
  - complete logs, with 0 errors;
  - locked digests equal to the logs and recomputable from them;
  - byte-identical re-aggregation;
  - G4 run on the pre-registered sample (seed 20261127), 100/100 identical.
- A1, A1-lo10, A0, B0 and S rebuild byte-identically.

| arms | gates | result | review |
|---|---|---|---|
| A1, A1-lo10, A0, B0, S | G4 (rebuild, hashes), G5 | pass | rounds 1-2 |
| B1 (=lo10), B1-alt (=lo5) | G1, G2 (B1), G4, G5 | pass; G2 0.792/0.784, investigated pre-lock | rounds 1-2 |
| B5, B4, B2 | G1 (B4/B5 indirect), G4, G5 | pass | round 2 |
| ten controls | G1, G4, G5 | pass | 2 fully, 8 conditionally |

- **G1:** flags, currents and tuning paths match in 480/480 runs; scores are exact in 390/417 (max difference 0.00088). No host type reproduces 10 of the 27 differences.
- **G1 for B4/B5:** these arms use `fixed_run`, which G1 never ran. B5 equals B1 on 7,091/7,091 shared runs.
- **G3** applies to B3 only.
- **G5:** `gates/G5_REPORT.md` PASS; nothing outside `ledger/`, `research/ledger/` differs from `main`.

**Controls.**
- Round 2 fully checked only rewire-101/102 (rewire-103: log read, re-aggregation and G4 outstanding); seven came later.
- L34 records the conditions as met via `r2_controls_check.py`, which is not in git.
- I re-verified every condition except the scoring dry run with all ten controls. It rests on L34 and the post-tag `.verify.json` (91 inputs pass).
- After round 2, stimulation and aggregation code was unchanged; only batching (covered by G4) and round-2 fixes changed.

## Point 2: G2
Met before the lock.
- **Timing:** `gates/G2_REPORT.md` was committed in aaf5dca (11-19 23:08 PST), 9.6 h before lock commit e8bc214. It is hashed in the lock and identical in the tag.
- **Content:** it names four causes (noise ceiling, 138 vs 144 MNs, usability rule, numerics) and applies PREREG §9's remedy: no code bug, so lock as is.
- **Reproduced:**
  - 0.792 and 0.784; Pearson 0.913;
  - 0.864 on the 293 types usable in both;
  - 23 types usable only in A1 (17 weak, 6 strong);
  - split-half 0.93 (A1), about 0.92 (B1).
- **Not reproduced:** the 138-MN re-score. The numerics cause is asserted, not shown.

## Point 3: B2
No gate in the prompt (lines 222, 253-260) or PREREG (3.8, §9) makes DNg100 a condition for B2.
- **Positive control:** DNg100 scores 0.059 (B1 0.828, A1 0.896). All 16 replicates were accepted at 256, 15 of them with 0-1 active MNs.
- **Gates:** B2 passed G1, G4 and G5. Round 2 said "lock as pre-registered".
- **Not validated:** its one arm-specific sanity check failed (line 121), so B2 is gate-compliant only.
- **Departure (L9):** built from the authors' hash-pinned matrix at 50 GiB free, despite §6.3 ("skip MaleCNS (arm B2)").

## Point 4: B4
The calls follow line 238.
- **Recomputed:** 0 mismatches over 475 types at each strength. The halts rule was applied literally. The speed rule used PREREG's both-rhythmic pairing, because the prompt names no subset.
- **Over-excitation:** 199 of 207 "halts" lose the rhythm with as many or more active MNs. DNg100 itself "halts".
- **Gates:** none tests a call's meaning; the weakness was recorded before labels (ARM_DIAGNOSTICS, L29).

## Point 5: B3/B6
Neither is locked or has a folder. G3 item 4 fails (3 of 7 leg pairs coupled), and line 257 says not to lock B3. B6 reuses the B3 procedure (PREREG 3.11, L18).

## Point 6: DONE_CHECKLIST.md
**Confirmed:** tags (also on origin), predictions lock, gate figures, B5 = B1, B4 recomputation.

**To correct:**
- Lines 7, 12: the gates are in prompt §8, not §9.
- Lines 14, 27-28: they overstate G1 for B4/B5.
- Line 22: "unchanged" holds only for `types.csv`; A0's replicates and `neurons.csv` were rewritten after round 1.
- Line 30: the reviewer fully checked only two controls.

**Cannot confirm:** label-side rows, citations to L36 and later, `lock_verify` before tagging, the scoring dry runs, the handoff.

## Disclosures
- My grep for the L36 boundary printed row L36 (session logistics, no outcome); unused.
- A check created `phase3/.venv`; I removed it.
- Two label-review files under `final/` carry uncommitted edits by another process. I did not open them.
