# HANDOFF 5: run 5 of the BrainIR prediction ledger

## 1. What exists now

All four tags exist and were pushed to `origin` (branch `ledger/v1` only; `main` untouched; no force push):

| Tag | Lock | SHA-256 | Timestamp proof |
|---|---|---|---|
| `ledger-pertype-v1` | `LOCK_pertype_v1.json` | 40a4c521c257787de7b0ef9de82b9a7f57bd4a833a678caf6c3e988e8b30c044 | Bitcoin-attested |
| `ledger-prereg-v5` | `LOCK_prereg_v5.json` | 779b3b5373b37352537e94594d3b8bec513ceba8253dfee1b101427878be4ddc | Bitcoin-attested |
| `ledger-replication-v1` | `LOCK_replication_v1.json` | bd858b3efd201b20614029a91672fd1db760d614e8bec100be7b694b2c5b3dc1 | Bitcoin-attested (block 977206) |
| `ledger-forward-v2` | `LOCK_forward_v2.json` | 760413aa049ae7ec84b01bfd671a565d85d1e990bf83b82bb1480498cead6fb9 | Bitcoin-attested (blocks 977205, 977206) |

All four proofs (`LOCK_*.json.ots`) are committed.

Documents: `results/RESULTS_4.md`, `LABEL_AUDIT_v1.md`, `paper/PREPRINT_v0.md` (figures 1-4; `paper/CLAIMS.md`, 42 rows),
`BRIEF_v2.md` (two pages, measured), the three outreach drafts (recipients blank), and the reviews with addenda in `reviews_v5/`.

Nothing was sent, posted or uploaded.

## 2. Departures from the prompt

Reasons in full: `PREREG_v5.md` Part D.

1. **Part T** ran B1r's procedure with one copy stimulated, in both flies: no single-neuron procedure is validated on MaleCNS.
2. **Part R:** replication rates and the overlap coefficient carry the words, not Jaccard, which lists of 15 and 29 drivers cap.
3. **Part L:** a census of all 39 primary-set types beside the sample of 15 (either above 10 % triggers), to remove sampling error.
4. **Part L:** the atlas re-coded with exam 1's own procedure, reader disagreements adjudicated and unclear outcomes verified, so that audit noise is not counted as exam 1 error; every Part R type with a kit line added, so that Part F rests on the audit.
5. **Part L:** readers used run 2's web exception for 24 sources that are abstract-only or unreachable in the cache.
6. **Part S:** the primary replicated set is the prompt's (from the locked B2r table); the high-confidence version is a sensitivity.
7. **Part F:** replication vs counting and single-connectome vs counting added, since the prompt's comparison has at most 4 informative
   types (inconclusive by construction, stated in advance); power is given per number of informative types.
8. **Part F list:** at most 9 non-control types, only types with an available line, A1 hits first among single-fly hits (to keep 12 with
   the controls); "not already tested" uses the audit or exam 1, the stricter test.
9. **"If time runs short":** a fixed checkpoint, against optional stopping (never triggered).
10. **Sessions ran in run 2's tool mode:** the sandbox also stopped sessions writing their outputs, so the pre-specified fallback applied.
11. **Paper:** exam numbers come from tagged, timestamped scorecard commits, not locks; claims about the original paper cite it; two
    reviewer findings appear in words, marked "not locked"; headings softened per the overclaim review. The prompt's "our rebuild for the
    second fly" is corrected: our rebuild is MANC's (identical to the authors'); the MaleCNS network is theirs, its screen ours.
12. **Operational:** the rulebook was audited twice (23 and 15 findings, all fixed); amendment rows for four code files; Part T
    re-packed; the replication lock's first draft failed its own check and was rewritten before commit (LOG L170); the brief changed once
    after its review, for the referee's DNg100 finding.

## 3. Part R: replication (post hoc)

The thresholds were chosen after the pattern was seen. Driver means a score of at least 0.5.

| | high-confidence match (215 types) | all matched (310) |
|---|---|---|
| replicated | DNg100, DNb08 | + DNit013 (low-confidence match) |
| near-replicated | 10 | 10 |
| single-fly hit, MANC | 7 | 10 |
| single-fly hit, MaleCNS | 13 | 18 |
| stable non-driver | 50 | 83 |
| drivers in B1r / B2r / both (expected) | 11 / 23 / 2 (1.2) | 15 / 29 / 3 (1.4) |
| replication rate, B1r to B2r | 0.18 (0.00-0.44) | 0.20 (0.00-0.43) |
| overlap across flies / within a fly (overlap coefficient) | 0.26 (0.00-0.55) | 0.27 (0.04-0.53) |

- **Authors' own list (A1):** 2 of its 6 high-confidence hits replicate.
- **A0:** DNg100 and DNb08 are the only two of 308 two-sided types whose every copy is a driver.
- **Caveat:** DNg100's replication is guaranteed by our calibration (section 9), so DNb08 is the informative case.

## 4. Part S: does count-noise stability predict replication?

**Not shown.** The exact one-sided rank test gives p = 0.114 (52 of 455 subsets).

Stability across 16 Poisson copies:

| Type | Stability | Replicated? |
|---|---|---|
| DNg100 | 1.00 | yes |
| DNxl133 | 0.88 | |
| DNg54 (A1 only) | 0.81 | |
| DNxl102 | 0.81 | |
| DNit013 | 0.75 | yes |
| DNp02 | 0.75 | |
| DNit011 | 0.56 | |
| DNa07 | 0.50 | |
| DNb08 | 0.44 | yes |
| DNxl053, DNp63, DNxl110 | 0.44 each | |
| DNxl101 | 0.25 | |
| DNp41 | 0.19 | |
| DNxl121 | 0.06 | |
| DNg63 | 0.00 | |

- **A1 list:** p = 0.27.
- **Sensitivities (no words):** high-confidence 0.13; mean copy score 0.035; mean fraction rhythmic 0.033; without the two low-usability
  drivers 0.18; reference test on the real network's score 0.37 and 0.32.

- **False hits:** 26 of 640 type-copies of the 40 sampled non-hits (4.1 %); 7 of 40 types had a driver copy, none in half the copies.
- **Checks:** regression gate 448 of 448 digest-identical; determinism 100 of 100.
- **Power statement (fixed in advance):** with three replicated types, this null is uninformative.

## 5. Part T: single copies (descriptive)

- DNg100's copies drive in both flies: MANC 0.98 and 0.97; MaleCNS 0.86 and 0.78.
- DNb08's four copies drive in MANC (0.66-0.79), but none drives alone in MaleCNS (0.00-0.48), although the whole type does (0.78).
- MANC single-copy scores track the authors' A0 at a Spearman correlation of 0.65 (120 copies).
- Determinism re-run: 40 of 40 identical.

## 6. Part L: label audit

**DNg100.** Two independent forensic sessions agree: the only "no" is a record of DNg100 activated together with a brake neuron, coded
as more line-specific than two plain DNg100 "yes" records, so the consensus rule's tie-break let it decide; the blind rule had set aside
23 concordant records from the simulation papers (22 headless "yes"). Not a mapping error; the correct label is **yes** (high confidence).

**Re-reading:** 68 sessions, no breach; the readers agreed on 67 of 73 types and the atlas coders on 107 of 120 keys; 372 of 375
quotes were found verbatim (the other 3 read from a figure).

**Error rates.**

| Set | Errors | Rate (interval) |
|---|---|---|
| Sample of 15 | 1 (DNg30) | 6.7 % |
| Census of 39 | 3 (DNg30, DNp03, DNp05) | 7.7 % (1.6-20.9 %) |
| Atlas-only types | 0 of 21 | |
| Types read from papers | 3 of 18 | |

- DNg30's error comes from the audit's own scope rule, not from any record.
- DNp03 and DNp05 come from one source's confidence coding; no defect was named.
- The tie-breaks decide 30 of the 54 compared labels (by design, reported).

**Consequence:** exam 1 stands, with an erratum for six exposed types:
- DNg100: no -> yes;
- DNa01, DNa02, DNg13: no -> unclear;
- DNg62: yes -> unclear;
- MDN: yes -> conflicting.

**Exploratory re-score:** AUROC 0.559 against the locked 0.577.

## 7. Part F: the short list

R/S/C: the replication, single-connectome and counting readings. Lines: listed as available today (clean ones in brackets).

| Type | Group | R / S / C | Lines (clean) |
|---|---|---|---|
| DNp71 | near-replicated | yes / no / yes | 2 (1) |
| DNa13 | near-replicated | yes / no / no | 3 (3) |
| DNa07 | near-replicated | yes / yes / no | 9 (7) |
| DNa03 | near-replicated | yes / no / no | 1 (0; labels six other DNs) |
| DNp41 | MANC-only, A1 hit | no / yes / yes | 2 (0; one labels DNg100) |
| DNp02 | MANC-only | no / no / no | 10 (2) |
| DNg63 | MANC-only | no / no / yes | 1 (1) |
| DNg13 | MaleCNS-only | no / no / yes | 5 (4) |
| DNg21 | MaleCNS-only | no / no / yes | 4 (4) |
| DNp07 | control | no / no / yes | 5 (4) |
| DNg39 | control | no / no / yes | 2 (2) |
| DNp26 | control | no / no / yes | 7 (4) |

- **Collections:** of the short list's 70 lines, 63 are Janelia FlyLight split-GAL4, 5 Janelia GAL4 lines at Bloomington and 2 VDRC
  Vienna Tiles lines.
- **Availability:** 58 of the 78 lines checked are listed as available today. The 14 split lines available only through FlyBank are the weakest "yes".
- **Decision rule:** for two readings, take the tested types with a clear outcome on which they disagree. One reading is supported if it is right on enough of them for a one-sided binomial test at 0.05.

| Comparison | Informative types | Right answers needed | Power (80 % / 90 % accurate) |
|---|---|---|---|
| Replication vs counting | up to 10 | 9 | 0.38 / 0.74 |
| Single-connectome vs counting | up to 8 | 7 | 0.50 / 0.81 |
| Replication vs single-connectome | 4 | | inconclusive by construction |

## 8. The paper

**Title:** How far can a simulation of one connectome be trusted? Left-right, cross-animal and blind literature tests of a walking screen
in *Drosophila*.

**Abstract (192 words):**

Connectome-constrained simulations can suggest which neurons to test. We asked how far such suggestions can be trusted, using the
rate-model screen of Pugliese et al. (2026) for descending neurons that drive rhythmic leg activity in *Drosophila*, in a ledger of
analyses frozen and timestamped before they ran. In the authors' published screen, a neuron's left and right copies agree at 0.63 of the
screen's agreement with itself (95 % interval 0.53-0.72). Our reimplementation shares 10 of their 11 hits in the first connectome, but in a
second connectome few recur (post hoc): of 11 confidently matched hits, 2 do, the paper's experimentally supported drivers DNg100, whose
replication our calibration guarantees, and DNb08. In the first connectome, Poisson-scale noise in synapse counts reproduces the
left-right gap. A pre-registered test of whether stability under such noise predicts replication was not significant (p = 0.11;
uninformative with three replicated types). In two blind exams against published experiments, the model did no better than counting
two-step synaptic paths, although exam 1's labels are confounded with their sources; an audit upheld them, with an erratum for six excluded
types. We pre-register 12 experiments and a rule for reading them.

## 9. The reviews: strongest point and answer

| Review | Strongest point | Answer |
|---|---|---|
| Hostile referee (18 objections, 15 tested) | DNg100's replication is built in: rulebook v2 chose the tuner's one setting to make DNg100 a driver in both connectomes. Under the original procedure it scored 0.059 in MaleCNS. Also: exam 1's labels are confounded with their source. | Both accepted: the abstract, Results 3 and 6, the Discussion and the brief now say so; DNb08 is named as the informative case. |
| Overclaim (47 items) | The Discussion's "real signal" generalised a post hoc result about two neurons, one of them the calibration neuron, and the noise wording overreached. | All 47 accepted; the sentence was replaced by a model-specific, post hoc statement. |
| Numbers (196 checked) | No value was wrong, but 11 misdescribed their set or label ("11 hits" read as the authors'), and the original paper's numbers had no source. | All fixed; external claims cited; `CLAIMS.md` corrected and extended. |

## 10. The brief's first paragraph and the emails

**Brief, first paragraph:**

> A published rate model built from the fly's nerve-cord connectome (Pugliese et al., 2026) screens descending-neuron types for rhythmic
> leg activity. Run on a second animal's connectome, its hits mostly do not recur: of our MANC screen's 11 confidently matched hits, 2 are
> hits again, and **those two are the paper's experimentally supported drivers, DNg100 and DNb08** (**post hoc**: the pattern was seen
> before its rule; our calibration guarantees DNg100's replication, so DNb08 is the real test; two is a tiny sample). A pre-registered test
> of whether a hit's stability under synapse-count noise predicts its replication was **not significant** (p = 0.11; with three replicated
> types this is not evidence against). We pre-registered 12 experiments with listed driver lines, and a rule for reading their results
> against wiring counts.

**Email to the authors (165 words):**

> To: / Cc: (blank)
>
> Subject: Your DNg100 / DNb08 screen across a second connectome: results, and a request to check our work
>
> Dear [names],
>
> We have spent the past weeks stress-testing the descending-neuron activation screen from your 2026 Nature paper, in a ledger whose
> analyses were frozen and timestamped before they ran (the replication pattern below is post hoc). The short version: your two
> experimentally supported drivers hold up. Re-running the screen on the MaleCNS connectome, DNg100 and DNb08 are the only confidently
> matched hits that remain hits (DNg100's by our calibration, so DNb08 is the real test), and in your single-neuron screen they are the
> only two-sided types whose every copy is a driver. Most other hits do not recur, and within MANC, Poisson-scale noise in synapse counts
> can produce the left-right disagreement we see. We did not test your rhythm-generating circuit.
>
> Everything is in [repository link], branch ledger/v1, with a preprint draft. Before anything is posted, would you be willing to point
> out errors, or places where we describe your work unfairly? We would much rather correct them now.
>
> With thanks and best wishes, [name]

**Email to a lab (118 words):**

> To: / Cc: (blank)
>
> Subject: Twelve descending-neuron lines to test in headless flies: a pre-registered prediction list
>
> Dear [name],
>
> We have pre-registered predictions for twelve Drosophila descending-neuron types that, as far as we can find, have not been tested in
> headless flies: switch each type on bilaterally (CsChrimson) and score rhythmic front-leg stepping, blind to genotype. Each has driver
> lines listed as available today. The list pits predictions from a connectome simulation, its replication across two connectomes, and
> simple synapse counts against each other, with a decision rule fixed in advance; three types are controls.
>
> Would your lab consider testing some of them, perhaps alongside experiments you already run? The list, lines, protocol and rule are in
> [repository link], branch ledger/v1 (forward_v2/). We would credit any contribution fully and share everything.
>
> With thanks, [name]

## 11. Compute and wall-clock

- **GitHub Actions:** 17.0 of 100 runner-hours (step time) over 51 runner jobs, at most 20 queued. Simulation jobs:
  - the trust gate (100, all identical);
  - S0 (448);
  - 16 copies (7,168);
  - Part T (3,824);
  - two determinism re-runs (140, all identical).
- **Modal and the Mac:** no Modal; no prediction ran on the Mac.
- **Label audit:** 68 sessions, $141 at list price.
- **Weekly usage:** about 0.87 of the account's seven-day window at last check (resets 25 November, 17:00).
- **Wall-clock:** 00:45 to about 06:10 PST, 23 November 2026 (the last 40 minutes waiting for Bitcoin confirmations).
- **Final baseline:** all 25 lock checks pass (the 21 earlier ones, the Phase 1-3 locks among them, and the 4 new ones); ledger
  suite 285 passed; BrainIR fast suite 532 passed and 1 failed, the same arm64 RK4 test as at the start of every run (LOG L5).

## 12. What worries me

- Half of the headline replication is built in: DNg100's replication is guaranteed by our calibration, so the pattern rests on DNb08, post
  hoc, and DNb08 is a driver in only 7 of 16 noisy copies, with no MaleCNS copy driving alone.
- Exam 1 cannot carry much weight: its labels are confounded with their sources, the tie-breaks decide most labels, and on the 18 types read
  from papers the audit's error rate (3 of 18) is above 10 %, though the pre-registered overall rate is not.
- The forward list cannot decide the prompt's comparison, and DNp41's two lines co-label other DNs (one DNg100).

## 13. What I would do next

1. Read the paper and the emails yourself before anyone else sees them. Fill in the recipients and the repository link.
2. Find lines for the 12 types on which the replication and single-connectome readings disagree but the kit has none (six A1 hits,
   six near-replicated; `forward_v2/CANDIDATES.csv`), or a clean DNp41 line, to make the prompt's comparison decidable.
3. If a lab tests the list, freeze its calls first, then score them with `forward_v2`'s rule.
4. A third connectome, or a MaleCNS screen calibrated on a neuron other than DNg100, would test replication without the built-in case.
