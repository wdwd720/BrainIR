# Addendum: answer to the adversarial review of RESULTS_3 (`ADVERSARIAL_REVIEW_v4.md`)

The review is committed once, unchanged (6b32514). This file is the answer to it (RUN4_PROMPT section 8; hard limit 6).

## The strongest objection, and the answer

**Objection.** The headline's near-equality (two Poisson copies agree at 0.40, the two sides at 0.37) rests on one pair of copies,
and its interval holds both copies fixed. Over all six pairings of the four noise copies the run stored (P1, P2 Poisson; N1, N2
negative binomial; same seeds, types and runners), copy-to-copy agreement is 0.38-0.54 (mean 0.456), every pairing above the observed
0.372; pooled, count noise reproduces about 86 % of the left-right gap (0.66-1.14), not demonstrably all of it.

**Answer: accepted.** The pre-registered test (B4.5, applied to P1-P2 and N1-N2 as locked) is met as written, and every pooled interval
in the review includes 0. But the reviewer is right that the pre-registered pair is a low draw, so the honest statement is "count
noise reproduces most of the gap", and "agree no better than" overstates it. The six-pair pooling is the reviewer's post-hoc analysis
(B4.2-B4.3 fixed one pair per model), so it is reported as exploratory, and, as the reviewer notes, its interval still omits
between-copy variance and should be read as too narrow.

**Changes made in response** (the reviewed versions stay in git: `results/RESULTS_3.md` at 6f19b7f, `BRIEF.md` at 5219488):

1. RESULTS_3's first line and section 3.4: "agree no better than" becomes "agree almost as poorly as"; the pre-registered pair is kept,
   and the six-pair figure is added and marked post hoc, with the review as its source.
2. BRIEF.md, result 3: "enough to produce the gap" becomes "produces most of the gap", with the same added sentence.
3. EVIDENCE_MAP.md, row 10: the caveat now names the low draw and the six-pair figure, with the review as its source.

## Other points of the review

- **"Counting noise" may suggest reconstruction error (its point 8).** Agreed that the words can mislead: Poisson resampling changes
  about a third of the connections between two copies, variability on the scale of the real left-right differences, not of EM counting
  error. The documents now say "Poisson-scale noise in synapse counts". Whether reconstruction-scale noise moves the screen was not
  tested.
- **Choice of comparator (its point 7).** Without paired draws the left-right agreement is 0.403 instead of 0.372; this points the same
  way as the main objection (noise reproduces most, not all) and is smaller. Noted, no change.
- **"Cause found" claims more than sufficiency (its point 9).** Already stated in RESULTS_3's caveat 1, the brief's caveat to result 3
  and EVIDENCE_MAP row 10; the first line keeps "in part".
- **Saturation (its point 4).** The reviewer's own check (Block 3 hybrids graded from 0.77 to 0.37) shows the statistic is not pegged;
  no change.
