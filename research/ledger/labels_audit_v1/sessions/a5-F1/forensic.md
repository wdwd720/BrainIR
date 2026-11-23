# Forensic report: DNg100 (BDN2), exam 1 front-leg label "no" (best preparation headless)

Session: a5-F1. Evidence comes only from files in this room. One permitted web fetch was tried: the Nature page for
10.1038/s41586-026-11195-y redirected to a login page (idp.nature.com), and Europe PMC lists the paper as
`isOpenAccess: N`, `inEPMC: N`, "Subscription required". So only the abstract of that source (`sources/10_1038_s41586_026_11195_y/text.txt`)
was used.

## 0. How the "no" came out (replaying `aggregate.py.txt` on `exam1_records_DNg100.jsonl`)

- The file has 28 DNg100 records. 23 have `saw_simulation_score: true`: all records from Sapkal 2026 (10.64898/2026.04.29.721658)
  and from Pugliese 2025 (10.1101/2025.09.12.675944). `eligible()` drops them (BLIND_RULE L4/L6).
- That leaves **5 eligible records**: `-0017` (intact_free), `-0019`, `-0020`, `-0042` (headless, Sapkal 2024,
  10.1038/s41586-024-07854-7), and `-0011` (headless, 10.64898/2026.05.03.722293).
- `_tier` on `front_leg_rhythm`:
  1. Confidence: `-0019` is `low` and the others are high or medium, so `-0019` (yes) is dropped.
  2. No `multi_dn` records.
  3. Best preparation is headless (rank 0), so `-0017` (intact_free, yes) is dropped. Left: `-0020` (yes, `unknown`),
     `-0011` (yes, `unknown`), `-0042` (**no**, `minor_offtarget`).
  4. Best specificity: `minor_offtarget` (rank 1) beats `unknown` (rank 2), so **only `-0042` survives**. The value set is {no}, giving **"no"**.
- So the type label depends on **one record, `-0042`**. That record is the **BDN2 + BRK co-activation** experiment, not BDN2
  activation alone.

## 1. The eligible records at the best preparation (headless)

| record | source | locator | recorded quote | recorded front | my reading | agree? |
|---|---|---|---|---|---|---|
| pass1-walking_stopping-r0-01-0019 | 10.1038/s41586-024-07854-7 | ED Fig. 6e | "Even decapitated oDN1 and BDN2 activated flies initiated robust forward walking" | yes | yes, weakly supported | partly |
| pass1-walking_stopping-r0-01-0020 | 10.1038/s41586-024-07854-7 | Fig. 4e–j | "We performed a complementary analysis for forward walking while activating BDN2 or BDN2 + BRK in decapitated flies." | yes | yes | yes |
| pass1-walking_stopping-r0-01-0042 | 10.1038/s41586-024-07854-7 | Fig. 4e–j; ED Fig. 6g,h | "Despite this difference, coactivation with BRK interrupted forward walking" | no | no **for BDN2+BRK**; this is not a reading of DNg100 activation | value yes, attribution no |
| pass1-recent_broad-r0-03-0011 | 10.64898/2026.05.03.722293 | §2.5; Fig. 5c–d | "Illuminating the arena with a red LED reliably elicited sustained running bouts, which we tracked with a modified headless skeleton" | yes | yes | yes |

Notes from my reading:

- **-0019.** The quote is in `text.txt:110`. However, the BDN2 trace in ED Fig. 6e (`figures/41586_2024_7854_Fig12_ESM.jpg`, panel e) is hard
  to make out next to the oDN1 trace. The Methods (`text.txt:300`) say: "In the case of BDN2 activation in decapitated flies, we observed
  robust walking when we restricted to testing older flies (10–12 days old, for Fig. 4e–j) flies compared to the 7–10-day-old age range
  that was used for initial experiments (Extended Data Fig. 6e), probably due to lower and more variable expression levels in younger
  flies." The only readout is ball velocity, with no leg tracking. So the text supports "yes", but the front-leg rhythm is inferred from walking. The
  low confidence is justified.
- **-0020.** Fig. 4e (bottom, `figures/41586_2024_7854_Fig4_HTML.jpg`) shows decapitated flies with BDN2 alone at about 4 mm/s
  translational velocity. Fig. 4h,j show many front-leg Fe–Ti entries into the swing-initiation zone, and almost all of them lead to
  swings ("BDN2" column). Front-leg stepping is measured directly, so I agree with **yes**.
- **-0042.** The record correctly reads what happened in the BDN2+BRK experiment. Fig. 4e (red trace) shows velocity near 0, Fig. 4h–j show few SIZ
  entries, long dwell and few swings. The legend says "e, Averaged translational velocity during BRK + MDN (top) or BRK + BDN2 stimulation in
  decapitated flies (bottom)" (`text.txt:120`). The Methods (`text.txt:300`) say "if BDN2 expression is weak, BRK dominates the phenotype
  and legs do not show any movement". BRK is a separate ascending "brake" neuron. The paper says "BRK activation suppressed backward walking driven
  by MDN" and "BRK activation led the flies to resist both flexion and extension at the Fe–Ti joint" (`text.txt:112,128`). So the
  "no" describes the BRK brake overriding DNg100, not the effect of activating DNg100. The record also codes `line_specificity`
  as `minor_offtarget` and lists BRK as "deliberately co-activated". Meanwhile the BDN2-alone record from the same figure (`-0020`) is coded
  `unknown`. That inconsistency is what lets `-0042` win the tie-break.
- **-0011.** Fig. 5c (`figures/722293v2_fig5.jpg`) shows a decapitated DNg100>CsChrimson fly standing before "red light ON" and then
  repeated L1 (left front) tarsus-tip step arcs. The legend reads: "c, Tracking running behavior of optogenetically induced locomotion
  (DNg100>CsChrimson) in a decapitated fly" (`text.txt:84`). I agree with **yes**. Caveats: n is not stated, and the light intensity is not stated.

## 2. What the sources report

### 2a. DNg100 activation in headless (decapitated) flies

| source | locator | front legs | quote |
|---|---|---|---|
| Sapkal 2024, 10.1038/s41586-024-07854-7 | text.txt:110; ED Fig. 6e | forward walking (ball velocity only) | "Even decapitated oDN1 and BDN2 activated flies initiated robust forward walking (Extended Data Fig. 6e) suggesting that unlike P9, the VNC outputs of these DNs are sufficient for forward walking." |
| same | text.txt:128; Fig. 4e–j | **BDN2 alone: front-leg swings (yes)**; BDN2+BRK: walking interrupted | "We performed a complementary analysis for forward walking while activating BDN2 or BDN2 + BRK in decapitated flies. ... Despite this difference, coactivation with BRK interrupted forward walking" |
| Pugliese 2025 preprint, 10.1101/2025.09.12.675944 (set aside: simulation scores) | text.txt:46, 50, 336; Fig. 2h–j; ED Fig. 3 | **yes**: front-left-leg stepping, frequency rises with intensity | "h, Example coxa-femur and femur-tibia joint kinematics of front left leg during optogenetic activation of DNg100 neurons in a tethered headless fly walking on a spherical treadmill"; "j, Stepping frequency of the left front leg increased with laser intensity"; "DNg100 activation produced forward walking on the ball, but at a lower speed than is typical of wild-type flies" |
| Pugliese 2026 Nature, 10.1038/s41586-026-11195-y (abstract only) | abstract | no headless experiment described | "DNg100-a known command neuron for walking" (the experimental confirmation in the abstract concerns DNb08) |
| Sapkal 2026 preprint, 10.64898/2026.04.29.721658 (set aside: simulation part) | text.txt:60, 62; Fig. 1b,d,e; ED Fig. 1c | **yes**: all six legs step on ball, slippery surface, air and amputated stumps | "In case of DNg100 stimulation, all six legs show rhythmic forward-stepping across all four conditions (Fig. 1d-e, Extended Data Fig. 1c, Supplementary Video 1)." |
| same | text.txt:62; ED Fig. 1f–h | **yes**: front-leg Fe–Ti oscillates with proximal joints glued | "we observed robust Fe-Ti oscillations indicating that sensory feedback from these proximal hair-plates is not a requirement for DNg100 induced stepping" |
| same | text.txt:68 | **yes** | "in sensory-deprived conditions different DNs drive stepping across different sets of legs (DNg100: all six legs, DNg97: front legs, MDN: hind legs)" |
| same | text.txt:124; Fig. 3g | unilateral: ipsilateral front leg steps; air: contralateral front leg steps too | "in addition to stepping in all ipsilateral legs, we also observed stepping in contralateral front and hind legs" |
| same | text.txt:134; ED Fig. 7a–c | **yes**, graded with intensity; in air, sometimes binary | "By titrating optogenetic light intensity, we could get DNg100 stimulated flies to walk slower"; "a much more variable and often a binary response (stepping at high frequency, or no stepping)" |
| Whole-body 3D kinematics, 10.64898/2026.05.03.722293 | text.txt:80, 84; Fig. 5c–d | **yes**: freely moving decapitated fly, L1 tarsus steps | "Illuminating the arena with a red LED reliably elicited sustained running bouts"; "c, Tracking running behavior of optogenetically induced locomotion (DNg100>CsChrimson) in a decapitated fly." |

The other sources here mention DNg100/BDN2 only for connectivity or simulation, with no headless activation experiment:
10.1038/s41586-024-07523-9 (text.txt:142, ED Fig. 8), 10.1038/s41586-025-08925-z (acknowledgement, text.txt:300),
10.1016/j.cub.2026.09.056 (connectomic downstream target, text.txt:86), and 10.1101/2025.10.28.684868 (circuit diagram, text.txt:120).

### 2b. DNg100 activation in intact (head-on) flies

| source | locator | what it reports | quote |
|---|---|---|---|
| Sapkal 2024 | text.txt:102, 110; Fig. 3j | free, powdered, stationary grooming flies start walking (centroid velocity, no leg tracking) | "Optogenetically activating oDN1 and BDN2 drove walking initiation, with BDN2 showing a much stronger phenotype (Fig. 3j)." |
| Sapkal 2026 preprint | text.txt:136; ED Fig. 7e | head-intact tethered flies walk forward, but slowly (≤ ~8 mm/s) | "But DNg100 stimulation could never drive higher velocity walking, even if we tested “head-intact” flies or flies with double copy numbers of transgenes (Extended Data Fig. 7e)." |
| 10.1038/s41586-025-09554-2 | text.txt:80, 170; ED Fig. 10 | DNg100 activated during imaging with passive tibia movement; no stepping readout | "we optogenetically activated one pair of descending neurons (DNg100) while imaging hook flexion axons in the VNC during passive leg movements" |

In no source here does activating DNg100 alone stop the front legs or fail to produce stepping, in either preparation. The one exception is a subset of low-intensity or
air-condition trials in the Sapkal 2026 titration (ED Fig. 7b–c), which is a dose effect.

## 3. Explanation of the label

- **(a) Mapping error: no.** All five eligible records name BDN2 or DNg100. The sources equate the two: "DNg100 (also referred to as BDN246)"
  (Sapkal 2026, text.txt:26) and "DNg100 ... where DNg100 is referred to as BDN2" (Pugliese 2025, text.txt:42). The driver line is
  the same split (VT058557 × R85F12) in every record. No record of another neuron was mapped to DNg100. Record `-0042` concerns DNg100
  plus a co-activated non-DN (BRK); that is an attribution problem, covered under (d) and (e), not a type-mapping error.
- **(b) Consensus rule: yes.** The rule gave one record a veto over all others. Step 3 ranks by preparation and then by specificity. Because
  `-0042` was the only headless record coded better than `unknown`, the tie-break discarded the two other headless BDN2 records
  (`-0020`, `-0011`, both yes). A "best specificity" rule was meant to favour cleaner lines. Here it favoured a deliberately
  combined two-line experiment, and it turned a 1-vs-2 (or 1-vs-25) split into a unanimous "no". Counterfactual: if `-0042` were coded
  `unknown` like `-0020`, the result would be {yes, no}, i.e. "conflicting". If it were excluded as a combination experiment, the result would be "yes".
- **(c) Sources set aside by the blind rule: yes (contributing).** The 23 records from Pugliese 2025 and Sapkal 2026 were all
  `saw_simulation_score: true` and so were ineligible (BLIND_RULE L4: "the Pugliese papers, the simulation part of the 2026 Sapkal preprint").
  The 14 of these that are headless, DNg100-only and not `multi_dn` (13 from Sapkal 2026 plus Pugliese `-0001`) all have front leg = yes. The
  8 `multi_dn` co-activation records and the 1 head-intact record are also yes. The 13 Sapkal 2026 records are `minor_offtarget`, so they would sit in the same
  specificity tier as `-0042`. With them included the rule would give "conflicting", not "no". The blind rule removed the
  strongest direct front-leg evidence (3D kinematics of all six legs, front-leg-only preparations). This alone did not create the "no", but
  it is why the "no" was unopposed.
- **(d) Correct reading of a narrower experiment: yes (primary).** `-0042` is an accurate reading of BDN2 + BRK co-activation, a different
  stimulation from activating DNg100. BRK is a brake that "led the flies to resist both flexion and extension at the Fe–Ti joint" (text.txt:128), and
  stimulus intensity was chosen per fly from a sampled set (text.txt:300). The same figure's BDN2-alone condition shows front-leg stepping.
  The "no" is BRK's phenotype, recorded under DNg100.
- **(e) Other: yes.** There was a record-level coding inconsistency. The BRK co-activation was coded `line_specificity: minor_offtarget`, with
  BRK in `other_cell_types`, while the BDN2-alone record from the same paper, line and figure (`-0020`) was coded `unknown`. A deliberate second
  line is neither "minor" nor off-target; the schema has no category for a deliberate non-DN co-activation. This miscoding is what
  made `-0042` rank above the BDN2-alone records in step 3. Without it, (b) would have given "conflicting".

In summary: the label is "no" because a co-activation record (d) was coded with a better specificity than the plain BDN2 records (e).
The consensus tie-break then let that record alone decide (b), and the blind rule had already removed the many concordant "yes" records (c).

## 4. Correct label

**DNg100, front legs, headless: yes (rhythmic front-leg stepping).** Confidence: **high**.

Every headless experiment that activated DNg100 alone reports front-leg stepping. This holds across four papers, two
laboratories' write-ups (Sapkal 2024/2026; Pugliese 2025) plus the independent kinematics preprint, and several surfaces
(ball, slippery surface, air, amputated stumps, freely moving on a floor). Some of these measure front-leg kinematics directly (Sapkal 2024 Fig. 4h–j;
Pugliese 2025 Fig. 2h,j; Sapkal 2026 Fig. 1e and ED Fig. 1f–h; 722293 Fig. 5c). The only "no" is BDN2+BRK.

Caveats:
- All experiments use the same split line, VT058557 × R85F12. Sapkal 2026 reports 0–2 non-DNg100 VNC cells per fly.
- Penetrance depends on fly age and stimulus intensity (Sapkal 2024 Methods; Sapkal 2026 ED Fig. 7).
- I could not read the published Pugliese 2026 full text.

Even with only the eligible, non-sighted records, the label should be yes once the co-activation record is excluded or coded like `-0020`.
