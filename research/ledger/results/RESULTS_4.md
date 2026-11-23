**Stability under synapse-count noise was not shown to predict which hits replicate in the second fly (exact one-sided rank test, p = 0.11; with only three replicated types, this null is uninformative).**

# BrainIR prediction ledger, results 4 (run 5)

Rules: `PREREG_v5.md` (tag `ledger-prereg-v5`). Inputs: the per-type tables `pertype_v1/` (tag `ledger-pertype-v1`). Locks: Parts R, S,
T and L in `LOCK_replication_v1.json` (tag `ledger-replication-v1`); the forward ledger in `LOCK_forward_v2.json` (tag `ledger-forward-v2`).

## 1. Replication across the two flies (Part R; POST HOC)

**Everything in this section is post hoc:** the thresholds and categories were chosen after the replication pattern was seen. Driver =
whole-type score of at least 0.5; B1r = our MANC screen, B2r = our MaleCNS screen, A1 = the authors' MANC list. The high-confidence version
(types whose cross-fly match is high confidence) leads; all matched types stand beside it. Source: `replication_v1/R_tables.md`.

| category (B1r x B2r) | high-confidence match (215 types) | all matched types (310) |
|---|---|---|
| replicated (driver in both) | 2: DNg100, DNb08 | 3: + DNit013 (low-confidence match) |
| near-replicated (driver in one, 0.3-0.5 in the other) | 10 | 10 |
| single-fly hit, MANC (driver in B1r, < 0.3 in B2r) | 7 | 10 |
| single-fly hit, MaleCNS (driver in B2r, < 0.3 in B1r) | 13 | 18 |
| stable non-driver (< 0.05 in both and in all four half-fly screens) | 50 | 83 |

| overlap of the driver lists (95 % bootstrap interval over types) | high confidence | all matched types |
|---|---|---|
| drivers in B1r / B2r / both (expected if independent) | 11 / 23 / 2 (1.2) | 15 / 29 / 3 (1.4) |
| replication rate, B1r drivers that are B2r drivers | 0.18 (0.00-0.44) | 0.20 (0.00-0.43) |
| replication rate, B2r drivers that are B1r drivers | 0.09 (0.00-0.22) | 0.10 (0.00-0.23) |
| overlap coefficient, cross-fly halves / within-fly halves | 0.26 (0.00-0.55) | 0.27 (0.04-0.53) |
| Jaccard index, full screens (maximum for these list sizes) | 0.06 (0.48) | 0.07 (0.52) |

With the authors' list (A1 x B2r): 2 of 6 high-confidence A1 drivers replicate (DNg100, DNb08), 3 of 11 over all matched types. In the
authors' single-neuron screen, DNg100 and DNb08 are the only 2 of 18 types with a driver copy (among 308 types with copies on both sides)
whose every copy is a driver. **The two experimentally confirmed drivers are the replicated set**, with the selection caveats beside them: DNg100's replication is guaranteed by our calibration (rulebook v2 chose the tuner's one setting to
make DNg100 a driver in both connectomes), so DNb08 is the informative case; the original authors chose DNb08 themselves; both are exposed types; two
confirmed neurons are a tiny sample.

## 2. Part S: does stability under count noise predict replication? (pre-registered, confirmatory)

Sixteen Poisson copies of MANC's raw synapse counts (floor of 5 applied after resampling; seeds 20261511-26) were screened with B1r's exact
job specification (8 seeds each; 7,168 jobs on GitHub Actions, none missing). Before any copy ran, a regression gate reproduced all 448 of
B1r's stored per-seed results digest for digest; a determinism re-run of 100 jobs was identical.

**Power statement (fixed before the test, PREREG v5 S7).** Only 3 of the 15 B1r drivers replicate. The smallest attainable p is 1/455 =
0.0022, reached only if they are strictly the three most stable; ties at the top raise it, and with seven or more perfectly stable drivers p
cannot fall below 0.05. A null result is uninformative; a positive one would rest on three types, two of them the confirmed drivers and one
on a low-confidence match.

| test (exact one-sided rank test) | B1r list (15 drivers; S1, carries the words) | A1 list (11; secondary) |
|---|---|---|
| S1: stability (fraction of 16 copies with copy score >= 0.5) | **p = 0.114** (52 of 455 subsets) | 0.273 |
| (i) high-confidence matches only | 0.127 | 0.200 (cannot reach 0.05) |
| (ii) mean copy score | 0.035 | 0.139 |
| (iii) mean fraction rhythmic | 0.033 | 0.127 |
| (iv) without DNg63 and DNxl121 (few usable B1r replicates) | 0.182 | 0.273 |
| (v) reference: real-network B1r score, seeds 0..7 / 0..15 | 0.367 / 0.317 | 0.248 / 0.248 |

**Verdict: not shown.** Sensitivities (ii) and (iii) fall below 0.05; they were pre-specified without words and are not a result.

Stability per driver: DNg100 1.00, DNxl133 0.88, DNg54 (A1 only) 0.81, DNxl102 0.81, DNit013 0.75, DNp02 0.75, DNit011 0.56, DNa07 0.50,
DNb08 0.44, DNxl053 0.44, DNp63 0.44, DNxl110 0.44, DNxl101 0.25, DNp41 0.19, DNxl121 0.06, DNg63 0.00. The replicated types are DNg100,
DNit013 and DNb08.

**S2 (40 sampled types that are drivers in neither screen):** 26 of 640 type-copies scored at least 0.5 (4.1 % per copy); 7 of 40 types
became drivers in at least one copy (95 % interval 7-33 %), and none in half the copies. By B1r band: 4 of 496 type-copies among the 31
non-drivers (< 0.05) and 22 of 144 among the 9 indeterminate types (0.05-0.5).

## 3. Part T: the single-copy screen in both flies (descriptive)

Every copy of the 43 types that are drivers in B1r, B2r or A1 was stimulated alone with B1r's procedure (16 seeds; 3,824 jobs, none
missing; `replication_v1/T_singlecopy.json`). This is our single-copy variant of the whole-type procedure, not the authors' single-neuron
notebook. In MANC, 19 of 42 types have at least one driver copy and 4 types with several copies have every copy a driver (DNa13, DNb08,
DNg100, DNp63); in MaleCNS, 31 of 43 and 7 (DNd05, DNfl015, DNg100, DNg109, DNg13, DNxl067, DNxn168). **DNg100**'s copies are drivers in
both flies (MANC 0.98 and 0.97; MaleCNS 0.86 and 0.78). **DNb08**'s four copies are all drivers in MANC (0.66-0.79) but none in MaleCNS
(0.00, 0.00, 0.07, 0.48), although its whole type is a driver there (B2r 0.78). Our single-copy MANC scores agree with the authors'
single-neuron screen copy by copy at a Spearman correlation of 0.65 (120 copies).

## 4. Label audit (Part L)

Fresh blind reader sessions re-read every relevant source for 73 types (two readers per source, adjudication of disagreements, the
atlas re-coded with exam 1's own procedure, verification of unclear outcomes; 68 sessions, no breach). DNg100's exam 1 label ("no" in
headless flies) is wrong: one record of DNg100 activated together with a brake neuron was coded as more line-specific than two plain
DNg100 records, the consensus rule let it decide, and the blind rule had set aside 23 concordant records from the simulation papers; the
audited label is "yes". Across all 39 primary-set types the audit counted 3 errors (7.7 %; 1 of 15 in the pre-registered sample), below the
10 % threshold, and no systematic fault, so **exam 1 stands as reported, with an erratum for six exposed types** (DNg100 no -> yes; DNa01,
DNa02, DNg13 no -> unclear; DNg62 yes -> unclear; MDN yes -> conflicting). The errors are not spread evenly: none among the 21 atlas-only types (re-coded with exam 1's own procedure) and 3 of the 18 types read
from papers. One of the three errors (DNg30) comes from the audit's scope rule, not from any record. Recomputed with audited labels (exploratory), exam 1's AUROC is 0.559 against the locked 0.577; two-step counting 0.713.
Details: `LABEL_AUDIT_v1.md`.

## 5. Three caveats

1. **The replication pattern is post hoc and tiny, and half of it is built in.** Two (or three) replicated types, seen before the rule; DNg100's replication is guaranteed by our calibration (rulebook v2 chose the tuner's setting to make DNg100 a driver in both connectomes; under the original procedure it scored 0.059 in MaleCNS), so DNb08, the authors' own pick, is the informative case; DNit013 replicates only under the calibrated procedure and on a low-confidence match.
2. **Part S's null says nothing either way.** Three replicated types cannot support a test at 0.05 unless they are strictly the most stable;
   DNb08 was not.
3. **The labels are inferred from papers and confounded with their sources.** Both exam 1 and the audit read the literature with
   language-model sessions of one family; all 21 atlas-only types are "yes" while the "no" labels come from other papers; the consensus
   rule's tie-breaks decide 30 of 54 audited labels.
