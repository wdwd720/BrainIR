# Naive-reader review: PREPRINT_v1 and SUPPLEMENT_v1

I am a fly neuroscientist new to this project. I read the preprint once, then the supplement and figures, and nothing
else. Items follow reading order. Tags: T term, N number, L logic, F figure, P pre-registration, C conclusion. Default
fix: supply what the item says is missing (a definition, fact, label or conclusion) at first use. The abstract is at
its cap, so its fixes must be swaps.

**Most confusing (fix first):** 10, then 11, 3, 7 and 12.

## Abstract

1. [TN] "agree at 0.63 of the screen's agreement with itself". What agrees: the ranks of type scores? Why would a
   screen disagree with itself: random draws?
2. [T] "current-setting procedure failed its positive control ... current sweep"; "for a single DNb08 neuron"; "12
   experiments to test them". Nothing says a current must be chosen. DNb08's relevance appears only in Results 4, and
   "them" lacks an antecedent.
3. [C] "the first two animals' hit lists overlap at chance (post hoc)". That is true only under the current-setting
   procedure. Under the sweep, used for the third animal, 14 of MANC's 18 hits recur in MaleCNS (6 expected). I came away
   believing the opposite. Fix: name the procedure.
4. [L] "the gap was confirmed in the third animal". Left-right, or between animals? Confirmed against what? Fix:
   "agreement between animals was also below the ceiling in BANC".
5. [C] "our own lists recurred above chance, while the authors' list recurred at chance (1 of 6)". Results 3 says this
   test lacks power, so the contrast is unsupported. The Discussion drops that caveat.
6. [TC] "stability under synapse-count noise predicted its score ... a second attempt". "Stability" is undefined, and
   Results 5 calls the result fragile. Fix: "nominally".

## Introduction

7. [TN] "scored how rhythmic the front-leg motor neurons became". The score is never defined: its range, what 0.5
   means, or whether grooming-like rhythm scores like walking. Without DNg100's known role in flies, I could not judge
   it as the positive control.
8. [TL] "left and right copies". "Copy" means a homolog here, a resampled network in Results 2, and a "member" or
   "position" in the supplement. The premise, that mirror homologs should score alike, is implicit. The "qualitatively
   similar for the left and right front legs" paragraph made sense only after Results 1. Fix: use "homolog", state the
   premise, move the paragraph.
9. [L] "These results hold up, and they are the authors'". On what basis? The Discussion says "we did not re-test
   them", yet Methods re-tests them in BANC as a gate. FANC is introduced, then dropped without explanation.

## Results

10. [LT] ★ Results 4, "Our current-setting procedure has one free setting". The abstract and Results 1-3 use this
    procedure before it is described. The paper never says how the authors chose their own current ("their current"),
    so I could not tell why a new procedure was needed. Four regimes appear: the authors' current; ours ("Tuned
    current" in Fig. 3, "K = 1" in S1); the "original procedure", which I took to be the authors' (S1: ours, K = 0); and
    the sweep. Many numbers omit their regime: the one-sided left-right ratios, including BANC's 0.58 (S3 makes the
    sweep primary only "for the cross-animal tests"); the count-noise tests; "10 of their 11"; and DNb08's BANC "(0.00)",
    which is 0.25 under the sweep. Fix: before Results 1, explain how each screen sets its stimulus. Name each regime
    once, and label every number with it.
11. [P] What was pre-registered? The Limitations list the third-animal tests and the MaleCNS check "(Methods)", but
    neither Methods nor Results 4 marks that check. Outside the Limitations' list: "by our pre-registered rule" (Results
    1); "a pre-registered test of our previous analysis" (Results 2), though Fig. 2 contrasts "MANC: previous analysis;
    BANC: pre-registered"; "two blind tests" (Results 6); and "Before any of these tests" (Results 7). The Introduction
    freezes rules "before the data they concern", then mentions post hoc analyses. Fix: a table of claims and their
    status.
12. [T] "our previous analysis" (Results 2, 4 and 5; Figs. 2 and 5; "run 5" in Fig. 5) is never introduced or cited.
13. [NL] Results 1, "agreement against a ceiling". What is random appears only in Methods. "divided by each screen's
    agreement with itself": by their product, mean or geometric mean? Raw values appear only as S3's "rho_x". Most of
    Fig. 1 sits at zero, so does 0.63 reflect disagreement among hits or the ordering of near-zero types?
14. [NL] Results 2. How can a redraw "add" a sub-threshold connection? In BANC, 1-synapse connections redraw to 0
    about a third of the time, which is removal, despite "does not add or remove". MANC left-right is 0.59 in Results 1
    but "0.47 ... in the same design" here. S3's "paired draws" and "cross-half form" are undefined. Why
    Poisson?
15. [N] The type sets are 250, 232, 214, 206, 202, 182, 181, 180 and 12. "182" is the three-animal set in Fig. 4 but the
    MaleCNS-BANC set in "60 of 182". Adjacent Results 3 sentences give "14 ... 6 expected" for different procedures.
    MANC-MaleCNS agreement appears as 0.40, 0.31, 0.41 and 0.33. Fix: a table of sets; set, procedure and threshold
    beside each number.
16. [NT] Results 3, "signed count of two-step paths", also Results 6's best baseline. Does it count paths or sum
    synapse products, and are direct connections included? Which of S3's four BANC values are "0.61 and 0.63"? Two carry
    the undefined label "floor5". "(0.71)" appears nowhere else.
17. [C] "Both BANC comparisons are a real gap, so the gap between animals was confirmed". Below-ceiling agreement
    seemed expected for any two networks. This gap is never compared with the left-right gap under one procedure, yet
    the Discussion says a type "disagrees more" across animals. BANC-MaleCNS (0.50) exceeds MANC-MaleCNS (0.31) despite
    weaker wiring agreement, and "points to part of each" (Discussion) lost me.
18. [C] "5 of 17 ... 12 of 60 recur". This is above chance, yet most hits do not recur, and I had no benchmark: S3's "OC
    ratio" uses an undefined "within-animal overlap". The sweep makes a third of MaleCNS types hits, but a tenth
    elsewhere. Why? "recovers more shared hits" (Discussion) sits beside lower whole-ranking agreement (0.31-0.33,
    against 0.40-0.41).
19. [N] The authors' list: "1 of its 6 hits" (Results 3), "10 of their 11" (Discussion), and 5 (S5). Their whole-type
    screen is never introduced (S1: "A1"). Fix: introduce it, and explain how 11 becomes 6.
20. [L] Results 4. DNg100 in BANC is a hit ("score 0.64") yet misses "the pre-registered bar of 12"; I had to reread to
    see two criteria. "Two versions do not depend on this calibration", yet Fig. 4's sweep caption says "DNg100's
    recurrence is built into our calibration". The DNb08 check changed both current and run length ("2-s runs";
    Methods: "1 s"), so "The earlier failure came from our current-setting procedure" did not follow. "All four DNb08
    copies reach the bar": which bar? Two never reach 12 of 16. "Three types are hits in all three animals": a shortlist?
    Pre-registered?
21. [TN] Results 5. "Two graded versions": graded how? "12 hits of our MANC screen or the authors' list": which
    procedure, and why not Results 3's 17? A mean over resampled copies reads as a smoothed score, not
    stability. S3 adds an undefined "stability fraction", and "partial correlation 0.56" lacks an interval. "about 7
    animals": per pooled screen, or in total?
22. [LN] Results 6. Test 2 comes before test 1, and I could not reconstruct it. How is a hemilineage "switched on" in a
    model that stimulates descending neurons? What output is "move the legs most"? What are "the right group", "0 of 27"
    and "mean percentile rank"? The eight baselines are unnamed; were they fixed in advance? S4 says test 1's best was
    "picked on these labels". "blind" to what? Why does an "erratum for six excluded types" matter? (S4: DNg100
    had been labelled "no".) Fix: three sentences on the design.
23. [CT] Results 7. Are the "three readings" predictions? Neither "a rule for reading their outcomes" nor the
    headless-fly measurement is given. In S7 only DNa13 and DNg13 are BANC hits (sweep), while DNa07 ("replicated", on the
    authors' list) scores 0. What should I conclude?

## Limitations and Methods

24. [L] "no BANC type name conflicts with its ID match, which suggests both come from the same match". I read this
    three times. Fix: "BANC's names seem derived from the same IDs, so this check cannot fail there".
25. [NT] Methods omits the units of "a current of 128", what counts as "active", "neuron size scaling", draws without
    an "accepted run", whether the sweep's "best score" is per draw, and MANC's side rule. K is "one free setting", yet
    the bounds, starting current and run limit are choices too.
26. [T] Ledger jargon: "prediction ledger", "pre-registered words", "which test carries which words", "word-bearing
    set", "lock file", "trust gate", "campaign", "newly started agent" (before Use of AI), "isolated
    rooms". S3's "the run's instructions" and "prompt's D" imply an unexplained layer of instructions.

## Figures

27. [F] Fig. 1. Points are overplotted at zero, and without lines at 0.5 the hits are hard to count. The ceiling, and so
    0.63, cannot be seen.
28. [F] Fig. 2 invites comparisons the text does not make. Blue mixes the authors' two-leg readout with one-sided
    screens. Green MANC (0.48) belongs beside an unplotted 0.47, not blue's 0.59. Only orange names its procedure.
29. [F] Fig. 3. "Tuned current" is not the text's term, and the orange and green chance lines overlap. Shares resting
    on as few as 7 hits lack intervals, and the authors' list is absent.
30. [F] Fig. 4. The colour scale hides the 0.5 cut, so I could not check which cells are hits, and it has no take-home.
31. [F] Fig. 5. I could not see the correlation: ten points lie at 0-0.07, and the two named ones sit mid-range on x.
    DNxl102 (BANC about 0.98) is missing from Fig. 4's list of every hit. Is it a typo for DNxl092? The 12 types'
    matching rule is unstated.
32. [F] Fig. 6. "position 328" means nothing to me, and the axis says "runs" where the caption says "draws". The current
    our procedure chose is unmarked, so I could not see why it failed.

## Supplement

33. [T] S1's middle column is the paper's best glossary, but its third ("A0", "B1r", "Part S") means nothing
    outside. Words drift: draws, runs, replicates, seeds; hits, drivers; redrawn, resampled;
    single-neuron, single-fly, half-fly. Fix: a main-text glossary, one word per concept.
34. [TN] Undefined: S2's "E1", "E2" and "I2"; S3's AUROC (of what?), "d_M", "d_C", raw JSON and "16-replicate halves
    under either procedure"; S6's "0.12 (mean 0.14)"; S7's "near-replicated", "stable non-driver", "top counting" and
    "A1 driver".
35. [P] S3's departures, such as "a same-name subset" and "campaigns split into parts". I could not tell what each
    means, or whether each preceded the data.
36. Draft leftovers: "Title options" and "[[AUTHOR TO COMPLETE ...]]".

## What I think the paper shows

Pugliese et al.'s simulated screen ranks descending neurons by the front-leg rhythm they evoke. This paper finds the
ranking only partly a property of cell types. In all three connectomes, and in the authors' screen, the two neurons of a
bilateral pair score clearly differently, at about 0.6 of the screen's self-consistency. Agreement between animals is
lower (0.3-0.5), perhaps partly because BANC's wiring differs. Which hits recur depends heavily on how the current is
set, and only DNg100, DNa13 and DNxl092 are hits in all three. The model reproduces the authors' key results, but does no
better than path counting against experiments. My take-home: treat a one-connectome hit list as a noisy shortlist, and
check both homologs and a second connectome. I could not tell whether the lesson concerns such screens generally, or
this reimplementation's current-setting procedure.
