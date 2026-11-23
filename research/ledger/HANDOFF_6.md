# HANDOFF 6: run 6, a third animal (BANC)

The run started at 10:19 PST on 23 November 2026 and ended about 15:50 PST. Decisions are in LOG L176-L191 and the current state in
`STATE.md`.

## 1. What exists now

Everything is pushed to `ledger/v1`; `main` is untouched. All four tags are on the remote.

| Tag | Lock file, sha256 | Timestamp |
|---|---|---|
| `ledger-prereg-v6` | `LOCK_prereg_v6.json`, 08f1ad754ac2d53cbc28d6288d4be43a293f9162c7e3d256f2a9755c7c51bd20 | Bitcoin-attested |
| `ledger-posthoc-v6` | `LOCK_posthoc_v6.json`, 4b680b1f960f368adf1e9d73d402efd0cfea23eba39f5af6d075252b088f7c50 | attested |
| `ledger-thirdfly-v1` | `LOCK_thirdfly_v1.json`, b8ef3e6810fa6ff6efa26425c3499a8cb04291621fc1865c0c2a791634bcf395 | attested |
| `ledger-paper-posthoc-v1` | `LOCK_paper_posthoc_v1.json`, 3dcb99d0a3143db1d98a7925e0ca30c9950b033c27eb332d4fc52d66f1fb4b20 | pending; a retry is running |

**Final baseline:** all 25 earlier lock checks and all 4 run-6 checks pass. The ledger suite passes 302 tests; the BrainIR suite passes
532, with the one known failure (L5).

**Deliverables:** RESULTS_5; the paper (draft PDF and DOCX), its supplement and claims table; the four reviews with addenda; the study
guide, hand-check kit, brief and outreach drafts.

Nothing was sent or posted.

## 2. Departures from the prompt

1. **The rulebook's 16 departures** (`PREREG_v6.md` Part D), all fixed before any BANC screen:
   - (1) the BANC table that the authors' configuration names;
   - (2) 139 motor neurons, with the neck motor neurons left out;
   - (3) C1 on label-consistent types;
   - (4) C2 by the cross-half statistic, without a mirror network, because BANC has no bilateral annotation;
   - (5) exact intervals;
   - (6) verdicts on the sets without DNg100;
   - (7) C6's verdict with BANC as the only target, because the prompt's average is positive by construction;
   - (8) C8 with 12 types, because 3 of the 16 have no BANC group;
   - (9) 2-s runs for the DNb08 check, and (10) its 130 motor neurons;
   - (11) the locked original-procedure screens;
   - (12) MANC's stored sweep, which no earlier lock covered;
   - (13) a wiring check with a fixed caveat;
   - (14) a same-name subset;
   - (15) DNg100 judged even if no BANC screen is valid;
   - (16) campaigns split into parts.
2. **A fourth lock and tag, `ledger-paper-posthoc-v1`.** It holds post hoc numbers the revised paper needed: the corrected three-animal
   counts and C7's estimate for each pair alone (L189).
3. **A locked script was edited after its locks.** `posthoc/paper_figures_v6.py` got label edits. The pre-revision lock check caught it;
   the file was restored, and the edits moved to a new script (L188).
4. **RESULTS_5, which no lock covers, was corrected in place**, with the originals struck through and dated (L190).
5. **Poppler was installed with Homebrew**, only to render PDF pages; the prompt names pandoc only.
6. **The title options** are in a source comment, not in the printed paper.
7. **The primary procedure for the cross-animal tests is the sweep.** By the validity rule, the sweep replaced the failed current-setting
   procedure for C3, C4 and C6-C8.
8. **FANC was not screened.** No network with all its descending neurons exists on Zenodo.
9. **Time.** The run took about 5.5 hours, not 12 to 20.
10. **Final review fixes (L192):** Part V back in the Limitations; claims paths resolved (row 37 fixed); counts with DNg100 in RESULTS_5
    and the brief; the study guide's questions now include the referee's.

## 3. The BANC build

- **Sources.** The authors' `W_20260217.npz` (4,963 neurons, no synapse threshold) and their `wTable_20260217_fullData.csv`, both pinned
  by SHA-256; their configurations came from Zenodo.
- **Build.** The matrix is used as released: signs agree with the transmitter rule on all 4,863 rows it covers, and sizes come from
  surface area. There are 922 excitatory descending neurons, and the read-out is the 139 front-leg motor neurons.
- **Build check** (specified before it ran). DNg100 at the authors' current scored 0.994 (authors 0.984). With E1, E2 and I2 silenced
  it scored 0.000, 0.028 and 0.993 (authors 0.014, 0.035, 0.993). **Passed.**
- **Matching.** 309 MANC types; high confidence 206, medium 103. **Three-animal set: 182 types (181 without DNg100).** Output sides
  are used, because annotations agree with them for only 62.7 % of neurons.

## 4. C1 to C8 (verdicts on the sets without DNg100)

| Test | Pre-registered words | Numbers |
|---|---|---|
| Validity | current-setting procedure invalid; sweep primary | DNg100: 11 of 16 draws (bar 12); sweep 8 of 8 |
| C1 left vs right | a real gap | 0.58 (0.38-0.77) |
| C2 count noise | does not reproduce it | 0.78 (0.64-0.89) vs 0.58 |
| C3 across animals | confirmed in the third animal, with the wiring caveat | MANC-BANC 0.35 (0.20-0.49); MaleCNS-BANC 0.50 (0.38-0.62); MANC-MaleCNS 0.31 (post hoc); wiring 0.61 and 0.63 vs 0.82 |
| C4 our MANC list | above chance | 5 of 17 (1.7 expected; p = 0.016) |
| C4 authors' whole-type list | at chance at the authors' cut | 1 of 6 (0.6 expected; p = 0.47); the test has low power |
| C4 our MaleCNS list | above chance | 12 of 60 (6.3 expected; p = 0.004) |
| C5 DNg100 | pass | 0.64; sweep 0.92 |
| C5 DNb08 | (no prediction) | 0.00 under the current-setting procedure, 0.25 under the sweep |
| C6 pooling | not shown | +0.20 over MANC; +0.02 (-0.03 to 0.07) over MaleCNS |
| C7 animals needed | (estimate) | about 7 (4.3-9.7) |
| C8 stability | stability under count noise predicts the third animal | Spearman 0.57, p = 0.029; fragile |

Two sentences fixed in advance go with these words.

- **C3's caveat:** "BANC's wiring of these types agrees with the other animals' less than the first two animals' wiring agreed, so
  part of the gap may come from the build or the type match."
- **C4's "at chance":** "'At chance' means the overlap could not be told apart from chance by this test, whose power is low; it does
  not show that the hits fail to recur."

## 5. Hits across animals, DNg100 and DNb08

These counts are post hoc and corrected after the reviews. Under the sweep, 71 of the 182 three-animal types are hits in at least one
animal, 22 in at least two and 4 in all three:

| Type | MANC | MaleCNS | BANC |
|---|---|---|---|
| DNg100 | 0.81 | 0.98 | 0.92 |
| DNxl134 | 0.56 | 0.97 | 0.76 |
| DNa13 | 0.74 | 0.84 | 0.56 |
| DNxl092 | 0.75 | 0.85 | 0.54 |

Under the current-setting procedure only DNg100 is a hit in all three.

- **DNg100.** It passed its prediction in BANC (0.64) but missed the bar on draws, so the sweep became primary. It is never counted as
  evidence.
- **DNb08.** It is not a hit in BANC, as the authors report.

## 6. Part V

- **DNg100** at the authors' MaleCNS configuration **reproduces** their result: 0.985 against their 0.985.
- **DNb08** **reproduces the authors' reported result at current 250**, with their neuron in 2-s runs: 15 of 16 draws reached 0.5 (mean
  0.86; theirs 0.80).
- Every copy reaches the bar within its own range of currents. So our earlier miss came from our current-setting procedure.

## 7. Part H in three lines

- Under the current-setting procedure, the first two animals share 1 hit at 0.5 where 1.0 is expected; at 0.3 they share 14 where 6
  are expected.
- Under the sweep, 14 of MANC's 18 hits recur in MaleCNS (6.0 expected), yet agreement over all types is no better (0.33 against 0.41).
- Under the original procedure, only DNb08 is shared. All post hoc.

## 8. The paper

**Title:** *How reproducible is a simulated screen's hit list? A front-leg rhythm screen tested across three fly connectomes.*

**Abstract (218 words):** Connectome simulations help choose experiments. We asked how reproducible one such hit list is: the
rate-model screen of Pugliese et al. (2026) for descending neurons driving front-leg rhythm in *Drosophila*. Unless marked post hoc,
tests were pre-registered. In the authors' published screen, a cell type's left and right copies agree at 0.63 of the screen's agreement
with itself. Our reimplementation shows a similar gap in two male connectomes and in a female connectome, BANC, not screened until our
rules were frozen (0.58). Screens of different animals agree at 0.31 (post hoc) to 0.50 of this ceiling. For BANC the verdict fixed in
advance is "confirmed", but its agreement was no lower than between the first two animals, and its wiring matched theirs less, so part
of the gap may come from the build or the type match. Hit lists depend on how the stimulus is set: at the authors' threshold, the first
two animals' lists overlap at chance under our current-setting procedure but above chance under a current sweep (post hoc), and under
the sweep our lists recurred in BANC above chance. In the male CNS, our model reproduces the authors' DNg100 result and their
single-DNb08 result, which our current-setting procedure had missed. In the one interpretable literature test, the simulation added
nothing beyond the best wiring count.

**Length.** Introduction to Limitations: 4,096 words. Through Methods and Use of AI: 4,967.

**References and figures.** 18 references, all checked by full title and in order of first citation; 81 numeric claims checked against
locked files; six figures; every page viewed.

## 9. The four reviews

**Referee.**
- *Strongest point:* the answer depends on the procedure. Hit lists overlap at chance under ours, but 14 of 18 recur under the sweep.
- *Answer:* accepted: hit lists lead with the sweep, and Table 2 shows both procedures.

**Numbers and references.**
- *Strongest point:* four types, not three, are hits in all three animals; Fig. 4 had read the wrong table.
- *Answer:* accepted: a new post hoc lock, Fig. 4 redrawn, two titles fixed.

**Naive reader.**
- *Strongest point:* the paper never said how the current is set, or which procedure each number used.
- *Answer:* a new "How the screens work" section and a status table.

**Overclaim.**
- *Strongest point:* "our lists above chance, the authors' at chance" was a difference in power, not in recurrence.
- *Answer:* removed from the abstract and the Discussion; the fixed sentence now stands beside every "at chance".

## 10. Run 5's referee objections, and where the new paper answers each

| # | Objection | Where now |
|---|---|---|
| 1-2 | First literature test: classes from different experiments; counting's lead is size | R6, Supplement S4; out of the abstract |
| 3 | Tests a use the authors disclaimed | Introduction, R6, Discussion |
| 4 | MaleCNS screen calibrated on DNg100 | How the screens work, R4 |
| 5 | The audit "upheld" labels | Methods (0 of 21, 3 of 18) |
| 6 | "Barely overlap" is the 0.5 cut | R3, Table 2, Fig. 3, abstract |
| 7 | Beat seven of eight baselines | R6 |
| 8 | The title blames the connectome | title |
| 9 | Match rule written after seeing | Limitations |
| 10 | Left and right copies are two neurons | Introduction, R1 (answered, not changed) |
| 11 | "Half one-sided" is the floor | removed |
| 12 | "Reproduces dynamics" needs a qualifier | Methods |
| 13 | Resampling with a floor is structural | R2 |
| 14 | The null stability test in the abstract | R5; out of the abstract |
| 15 | Readers of one model family | Limitations; hand check pending |
| 16 | Read-outs differ | Methods |
| 17-18 | (refuted) reimplementation; matching | Discussion (DNg63, DNxl121 flagged); Supplement S1 |

## 11. What you must do by hand

1. Fill `paper/author.yaml`.
2. Do the hand check in `paper/HAND_CHECK.md` and fill the marked line in Use of AI. Then run `paper/build.sh` without `--draft`.
3. Read the paper once and pick the title.
4. Check the quotes against the Nature version [1] (we used preprint versions 1 and 2).
5. Decide on the three outreach drafts, fill their recipients and links, and send them yourself.
6. Commit `LOCK_paper_posthoc_v1.json.ots` once `ots upgrade` reports it complete (the retry may have written it).
7. Make sure readers can reach the cited branch and tags before posting.

## 12. The email to the authors

> Subject: Your descending-neuron screen across three connectomes: what holds up, and two questions
>
> Dear [names],
>
> We have tested how reproducible the hit list of the descending-neuron screen in your 2026 Nature paper is, freezing and timestamping
> each test before it ran. Much holds up in our hands: our model reproduces your DNg100 results in MANC, MaleCNS and BANC, your E1 and E2
> silencing in BANC, and your single-DNb08 result in MaleCNS at the configuration in your Zenodo record; like you, we find no DNb08 hit
> in BANC.
>
> Beyond your two neurons, hits recur less: left and right copies of a type, and the same type in different animals, agree well below a
> screen's agreement with itself. How far hit lists overlap depends on how the current is set; under a current sweep, our MANC and MaleCNS
> hits recurred in BANC above chance. Under our current-setting procedure DNg100's recurrence is built in, so we never count it.
>
> Two questions. Was position 391 at current 250 the configuration behind your single-DNb08 result in MaleCNS? And have you screened any
> dataset other than MANC?
>
> Everything is in [repository link], with a preprint draft. Before anything is posted, would you point out errors, or places where we
> describe your work unfairly?
>
> With thanks,
> [name]

## 13. Compute, agent sessions and time

- **Compute.** 14.88 of 150 GitHub Actions runner-hours (82 jobs). No Modal; the Mac ran no prediction.
- **Agent sessions.** 5 of 8: the rulebook auditor and four paper reviewers.
- **Time.** About 5.5 hours, from 10:19 to about 15:50 PST.

## 14. What worries me

1. **"Confirmed" could hardly fail.** Only agreement at the ceiling would have refuted it; the sizes and the wiring caveat are what
   inform.
2. **Both procedures have problems.** The current-setting procedure, which failed its control in BANC, produced the first two
   animals' lists and the forward list's readings; the sweep calls about three times as many hits.
3. **C8 is fragile.** A reviewer's unlocked check removes it by tying BANC scores below 0.10.
4. **Biology and reconstruction cannot be separated** in BANC.
5. **The labels were read by language models**, and the hand check is pending.
6. **A locked script was edited** after its locks; the lock check caught it, and the file was restored.
7. **The forward list has weak entries.** DNg21 and DNg39 had no usable MANC draw and DNg63 only one. The list is frozen, so this is
   disclosed, not fixed.
8. **No room in the word count.** The strict count is 4,967 of 5,000.
