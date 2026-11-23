# Forward ledger v2 (PREREG v5 Part F)

Made after both exams were unblinded and after the replication pattern was seen (post hoc categories, PREREG v5 Part R). Clean with respect to the experiments it predicts, which have not been done.

Forward ledger v1 (`research/ledger/forward/`) stays as locked; it is superseded for the ask by this list.

## Protocol (forward ledger v1's, unchanged)

1. Cross the driver line to UAS-CsChrimson (LexAop-CsChrimson for a LexA line); raise adults on food with 0.4 mM all-trans-retinal for 3-5 days, in the dark.
2. Decapitate the fly under cold anaesthesia and let it recover for 5-10 min, tethered or free on a flat surface.
3. Deliver 1 s pulses of 617 nm light (several intensities), at least 10 pulses per fly, at least 8 flies per genotype.
4. Record the front legs at >= 100 frames/s; score each pulse for rhythmic front-leg stepping blind to genotype.
5. Controls: the empty split-GAL4 crossed to UAS-CsChrimson, and flies of the same cross raised without retinal.

## Decision rule (PREREG v5 F5)

Each tested type's outcome is the lab's own call (yes / no / no clear outcome), recorded verbatim before the readings are compared. For readings X and Y: D = tested types with a yes/no outcome on which they disagree, n = |D|, k = the number X gets right, q(n) = the smallest k with one-sided binomial P(K >= k | n, 1/2) <= 0.05. X is supported over Y if k >= q(n); Y over X if n - k >= q(n); otherwise inconclusive (always when n <= 4). Comparisons: A replication vs single-connectome (inconclusive by construction with these lines), B replication vs counting, C single-connectome vs counting. Expected n and power: `DECISION_RULE.json`.

Files: `CANDIDATES.csv` (F1-F2), `AVAILABILITY.csv` (F4), `SHORTLIST.csv` (F3), `CANDIDATES_WHY.csv` (why a candidate is not listed), `DECISION_RULE.json` (F5).
