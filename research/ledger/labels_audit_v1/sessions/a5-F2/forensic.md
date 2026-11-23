# Forensic report: DNg100 (BDN2), exam 1 front-leg label "no" (best preparation headless)

Session: a5-F2. Evidence used: only the files in this room. I also tried to fetch the one permitted DOI
(10.1038/s41586-026-11195-y). nature.com redirected to an authentication page. Europe PMC reports the article
as "Subscription required" and not in PMC (PMID 42951971). I therefore had only the abstract
(`sources/10_1038_s41586_026_11195_y/text.txt`), which reports no headless experiment with DNg100.

## 0. How the "no" was produced (summary)

`exam1_records_DNg100.jsonl` has 28 records. Only 5 have `saw_simulation_score: false` and are therefore eligible
(`aggregate.py.txt` `eligible()`, lines 148-150). All 5 have mapping confidence high and a MANC type. The 23 others
come from the two dedicated sources (Pugliese 2025 bioRxiv 10.1101/2025.09.12.675944; Sapkal 2026, 10.64898/2026.04.29.721658)
and carry `saw_simulation_score: true`, so the blind rule (BLIND_RULE.md, L4/L6) set them aside.

| # (line) | record_id | doi | prep | front leg | conf | line_specificity |
|---|---|---|---|---|---|---|
| 1 | pass1-walking_stopping-r0-01-0017 | 10.1038/s41586-024-07854-7 | intact_free | yes | medium | unknown |
| 2 | pass1-walking_stopping-r0-01-0019 | 10.1038/s41586-024-07854-7 | headless | yes | **low** | unknown |
| 3 | pass1-walking_stopping-r0-01-0020 | 10.1038/s41586-024-07854-7 | headless | yes | high | unknown |
| 4 | pass1-walking_stopping-r0-01-0042 | 10.1038/s41586-024-07854-7 | headless | **no** | high | **minor_offtarget** |
| 5 | pass1-recent_broad-r0-03-0011 | 10.64898/2026.05.03.722293 | headless | yes | medium | unknown |

Below, the consensus rule (`_tier`, aggregate.py.txt lines 153-163) is applied to the front-leg field:
1. Some records have high or medium confidence, so record 2 (low) is dropped.
2. No record is `multi_dn`, so nothing is dropped.
3. Best preparation = headless (rank 0), so record 1 (intact_free) is dropped. That leaves records 3, 4 and 5. Then the best
   specificity is kept: record 4 is `minor_offtarget` (rank 1), and records 3 and 5 are `unknown` (rank 2). **Only record 4 survives.**
4. All remaining values are "no", so the **label is "no"**.

So the whole label rests on one record: the **BDN2 + BRK co-activation** experiment. Three headless "yes" records for
DNg100 activated alone are dropped, and so is one low-confidence "yes". The reason is that those records' line specificity
was coded `unknown`, while the co-activation record was coded `minor_offtarget`. All of them use the same DNg100 split line
(VT058557 x R85F12).

## 1. The records behind the "no" (eligible records at the best preparation = headless)

**Record 2: pass1-walking_stopping-r0-01-0019** (10.1038/s41586-024-07854-7, Extended Data Fig. 6e). Recorded front leg: yes.
- Source (text.txt line 110): "Even decapitated oDN1 and BDN2 activated flies initiated robust forward walking (Extended Data Fig. 6e)
  suggesting that unlike P9, the VNC outputs of these DNs are sufficient for forward walking."
- ED Fig. 6e legend (line 92): "Trial averaged translational velocity (left) and angular velocity (right) of decapitated, tethered
  flies while activating P9, oDN1, or BDN2. 3 s light stimulation ... n = 7-10 flies per genotype".
- My reading: **agree (yes), with reservations.** The readout is ball velocity only. Forward walking on the ball implies stepping,
  but no front-leg kinematics are shown. Methods (line 300) say that younger flies (7-10 days) used here had "lower and more variable
  expression levels". Low confidence is appropriate. The rule dropped this record at step 1.

**Record 3: pass1-walking_stopping-r0-01-0020** (10.1038/s41586-024-07854-7, Fig. 4e-j, BDN2 alone). Recorded front leg: yes.
- Source (line 128): "We performed a complementary analysis for forward walking while activating BDN2 or BDN2 + BRK in decapitated
  flies. In contrast to backward walking, during forward walking the SIZ for front-leg Fe-Ti lies in flexed angle values (Fig. 4g,
  SIZ is Fe-Ti less than 68°, Methods)."
- Fig. 4 legend (line 120): "e, Averaged translational velocity during BRK + MDN (top) or BRK + BDN2 stimulation in decapitated flies
  (bottom) ... g, Fe-Ti joint angle values at swing initiation onset ... h, Number of times per trial when front-leg Fe-Ti joint angle
  value entered the swing initiation zone (SIZ) ... j, Percentage of swings initiated after the front-leg Fe-Ti joint entered SIZ."
- Fig. 4 image (`figures/41586_2024_7854_Fig4_HTML.jpg`): in panel e (bottom), the BDN2 trace sits at about 4 mm/s during the light. In panels g-j,
  the BDN2 column shows many front-leg swing initiations, with the SIZ entered often (h) and swings in SIZ near 100% (j).
- Methods (line 300): "we observed robust walking when we restricted to testing older flies (10-12 days old, for Fig. 4e-j)".
- My reading: **agree (yes).** This is a direct front-leg kinematic readout of DNg100 activated alone in headless flies. The rule
  dropped this record at step 3 only because its specificity was `unknown`.

**Record 4: pass1-walking_stopping-r0-01-0042** (10.1038/s41586-024-07854-7, Fig. 4e-j BDN2 + BRK; ED Fig. 6g,h). Recorded front leg: no.
- Source (line 128): "Despite this difference, coactivation with BRK interrupted forward walking (Fig. 4e and Extended Data Fig. 6g,h)
  in a similar manner to that seen for backward walking".
- Methods (line 300): "for BDN2 and BDN2 + BRK experiments (Fig. 4e-j) ... chose the particular intensity at which that individual
  fly showed some degree of intention for forward walking (if BDN2 expression is weak, BRK dominates the phenotype and legs do not
  show any movement)."
- ED Fig. 6g legend (line 92): "Light microscopy images of combined split-Gal4 lines for co-labelling BRK and BDN2".
- Fig. 4 image: panel e (bottom) shows the BDN2 + BRK trace (red) at about 0 mm/s. Panels h-j show few front-leg SIZ entries and a low
  percentage of swings.
- My reading: **agree that "no" is a correct reading of this experiment, but disagree that it describes DNg100 activation.**
  The experiment deliberately co-activates BRK, an ascending "brake" neuron that the paper shows arrests leg movement on its own and
  with MDN (line 126: "decapitated MDN + BRK stimulated flies remained stationary"). The "no" reports the BRK brake phenotype
  overriding BDN2. It is not the effect of DNg100 activation. The record lists BRK in `other_cell_types` ("deliberately
  co-activated") but codes `line_specificity` = `minor_offtarget`. Deliberate co-activation of a second neuron class with an opposing
  function is not a minor off-target expression. This record should not decide a DNg100-activation label.

**Record 5: pass1-recent_broad-r0-03-0011** (10.64898/2026.05.03.722293, Section 2.5, Fig. 5c-d). Recorded front leg: yes.
- Source (text.txt line 80): "We expressed CsChrimson in DNg100, a descending neuron previously identified as a command neuron sufficient
  to drive rhythmic running in headless flies [57, 58]. Illuminating the arena with a red LED reliably elicited sustained running
  bouts, which we tracked with a modified headless skeleton (Fig. 5c, Supplementary Video 5)."
- Fig. 5c,d legend (line 84): "Tracking running behavior of optogenetically induced locomotion (DNg100>CsChrimson) in a decapitated fly
  ... Flexion at the tibia and femur is reduced during induced running"; "n=50 running cycles per condition, speed matched."
- Methods (line 174): flies "were cold-anesthetized, decapitated"; Supplementary Video 5 (line 250): "The fly speeds up when the red
  light turns on".
- My reading: **agree (yes).** This is free-moving headless running with whole-body (including leg) 3D tracking, so step cycles exist.
  It is weaker evidence: the n of flies is not stated ("a decapitated fly"), and the fly may already be moving before the light
  because of the white strobe. The rule dropped this record at step 3 because of `unknown` specificity.

## 2. Sources describing DNg100 activation

### 2a. Headless (decapitated) flies

| Source | Locator | What it reports for the front legs |
|---|---|---|
| 10.1038/s41586-024-07854-7 (Sapkal 2024, Nature) | ED Fig. 6e; text line 110 | "Even decapitated oDN1 and BDN2 activated flies initiated robust forward walking". Velocity only, no leg tracking. |
| same | Fig. 4e-j (BDN2 alone); lines 120, 128, 300 | Front-leg Fe-Ti kinematics during forward walking with swing initiations: **front legs step (yes)**. |
| same | Fig. 4e-j (BDN2 + BRK); lines 128, 300 | "coactivation with BRK interrupted forward walking"; "BRK dominates the phenotype and legs do not show any movement": **no, but a co-activation with a brake neuron**. |
| 10.1101/2025.09.12.675944 (Pugliese 2025 preprint) | Fig. 2h-j; text lines 46, 50, 336; ED Fig. 3 (line 393) | Line 46: "h, Example coxa-femur and femur-tibia joint kinematics of front left leg during optogenetic activation of DNg100 neurons in a tethered headless fly walking on a spherical treadmill ... j, Stepping frequency of the left front leg increased with laser intensity". Line 336: "DNg100 activation produced forward walking on the ball, but at a lower speed than is typical of wild-type flies ... They generally exhibited a tetrapod coordination pattern". **Front leg: yes** (n = 7 flies). Set aside by the blind rule (simulation scores in the same paper). |
| 10.64898/2026.04.29.721658 (Sapkal 2026 preprint) | Fig. 1d-e, ED Fig. 1c; text line 62 | "In case of DNg100 stimulation, all six legs show rhythmic forward-stepping across all four conditions" (ball, slippery surface, air, amputated). Line 60: "while control decapitated flies do not show stepping in any of the conditions, the DN stimulated decapitated flies, showed rhythmic stepping across all four conditions". **Front leg: yes.** |
| same | ED Fig. 1f-h; line 62 | Proximal front-leg joints glued: "we observed robust Fe-Ti oscillations indicating that sensory feedback from these proximal hair-plates is not a requirement for DNg100 induced stepping". **Front leg: yes.** |
| same | ED Fig. 7a-c; line 134 | Intensity titration: slower stepping at low intensity on the ball. In air, "a much more variable and often a binary response (stepping at high frequency, or no stepping)". **Yes at effective intensity; dose-dependent.** |
| same | Fig. 3g (unilateral), Fig. 4 (DNg100 alone and co-activations) | Ipsilateral front leg steps when one DNg100 is activated. With DNg100 alone, "all legs step at ∼11 Hz" in air (record 25 quote). **Yes.** |
| 10.64898/2026.05.03.722293 (whole-body 3D kinematics, 2026) | Sec. 2.5, Fig. 5c-d; lines 80, 84, 174, 250 | Decapitated, freely moving: "reliably elicited sustained running bouts"; step cycles tracked. **Yes.** |
| 10.1038/s41586-026-11195-y (Pugliese 2026, Nature) | abstract only | The abstract calls DNg100 "a known command neuron for walking" and reports simulations. Its abstract describes no headless DNg100 experiment. I could not read the full text (paywalled). |

No source here reports that activating DNg100 *alone* at an effective stimulus in headless flies fails to produce front-leg
stepping. The only front-leg "no" in headless flies is the BDN2 + BRK co-activation. There are also two narrow, partial
negatives inside the "yes" experiments: (i) some low-intensity or air trials show no stepping (Sapkal 2026, line 134); (ii) in
unilateral activation on the ball, "little to no stepping in contralateral legs" (record 13). In (ii) the ipsilateral front leg steps.

### 2b. Intact (head-on) flies

| Source | Locator | What it reports |
|---|---|---|
| 10.1038/s41586-024-07854-7 | Fig. 3j; text lines 102, 110 | "Optogenetically activating oDN1 and BDN2 drove walking initiation, with BDN2 showing a much stronger phenotype (Fig. 3j)". Fig. 3j legend: "translational velocity of stationary grooming flies induced to walk on optogenetic activation of oDN1 or BDN2. n = 12-17 flies". Freely moving, velocity only, no leg tracking. Front leg implied yes (record 1). |
| same | Fig. 3k, 3l (line 102, 110) | Silencing and imaging, not activation: "only BDN2-silenced flies showed a reduction in forward velocity"; "BDN2 activity is strongly correlated to forward (but not angular) velocity". |
| 10.64898/2026.04.29.721658 | ED Fig. 7e; line 136 | "DNg100 stimulation could never drive higher velocity walking, even if we tested “head-intact” flies or flies with double copy numbers of transgenes". Head-intact tethered flies walk, but only at about 0-8 mm/s. Ball velocity only (record 18). |
| 10.1038/s41586-025-09554-2 | text lines 80, 170, 275-276 (ED Fig. 10) | DNg100 activated in tethered flies (decapitation not stated) while the tibia was moved passively. The readout is hook-axon calcium ("After the end of the optogenetic activation, calcium signals in hook axons increased, indicating a release from inhibition"). **Front-leg stepping not assessed.** |

Other sources only mention DNg100 or BDN2 in connectivity or acknowledgement contexts, with no activation behaviour:
10.1038/s41586-024-07523-9 (line 142: "BDN2 and oDN1 ... recently discovered comDNs that drive walking"), 10.1016/j.cub.2026.09.056
(line 86), 10.1038/s41586-025-08925-z (line 300) and 10.1101/2025.10.28.684868 (line 120).

## 3. Explanation of the label

**(a) Mapping error: not chosen.** All 28 records map BDN2/DNg100 → DNg100 through the paper's own name or the kit synonym, using the
same split line VT058557 x R85F12. No record of another DN is mapped to DNg100, and no DNg100 record is lost to another type.
Record 4 does contain a second neuron (BRK). BRK is an ascending neuron (AN19A009 per the record), not a DN, so the DN-type
mapping itself is correct. The problem with record 4 is how the experiment was classed and coded (b, d, e), not the name mapping.

**(b) Consensus rule: chosen (decisive mechanism).** The rule's specificity tie-break (step 3, "then the best specificity rank",
`_tier` lines 162-163) keeps only the `minor_offtarget` record among the headless records. That discards the two eligible
higher-quality "yes" records (3, 5) and leaves a single "no". The rule has no step that sets aside co-activation experiments or
weighs the number of agreeing records. One record at a marginally better specificity rank overrides all others.

**(c) Sources set aside by the blind rule: chosen (contributing).** The 23 records from Pugliese 2025 and Sapkal 2026 have
`saw_simulation_score: true` and are ineligible (L4, L6). 13 of them are headless, DNg100 alone, `minor_offtarget`,
high or medium confidence, with front leg "yes" (records at lines 7-17, 19, 20). Those 13 would have shared record 4's
specificity tier. If they had been eligible, the same rule would have returned `conflicting` (13 yes vs 1 no), not "no". The
multi-DN co-activations would be dropped at step 2, and record 18 at step 3. So the blind rule's exclusion is what lets the single
"no" stand alone. Restoring those sources alone would not give "yes"; it would give "conflicting".

**(d) Correct reading of a narrower experiment: chosen.** Record 4's "no" is a faithful reading of Fig. 4e-j: BDN2 + BRK flies stop,
and the front legs rarely swing. But the experiment has a different stimulation (DNg100 plus the brake neuron BRK). The paper itself
describes the outcome as BRK's VNC brake overriding BDN2 ("if BDN2 expression is weak, BRK dominates the phenotype and legs do not
show any movement", line 300). It does not test whether DNg100 activation produces front-leg stepping. In the same panel, the
BDN2-alone control shows that it does.

**(e) Other: chosen (line-specificity coding).** The same driver line (VT058557 x R85F12) was coded `unknown` by the walking_stopping
and recent_broad sessions for the DNg100-alone records (3, 5, also 2). It was coded `minor_offtarget` in the dedicated session
(records 7-20) and for the BDN2 + BRK record (4). Record 4's `minor_offtarget` reflects a *deliberately co-activated* second cell
class, which is a more serious confound than unknown specificity, yet it ranks better under SPEC_RANK. Under either consistent
coding, the "no" could not have won alone:
- If records 3 and 5 had been coded `minor_offtarget`, like the same line elsewhere, the eligible headless tier would be {3 yes, 4 no, 5 yes}, giving `conflicting`.
- If record 4 had been coded as a co-activation, i.e. no better than DNg100 alone, record 4 would drop or tie and the label would be `conflicting` or "yes".

## 4. Correct label for DNg100 front legs in headless flies

**yes**: activating DNg100 in headless flies produces rhythmic front-leg stepping.

Evidence: four independent experimental sources report front-leg (or all-leg) stepping in decapitated flies when DNg100/BDN2 is
activated alone. Sapkal 2024 Fig. 4 has front-leg kinematics. Pugliese 2025 Fig. 2h-j reports front-left-leg stepping frequency,
n = 7. Sapkal 2026 reports all six legs in four sensory conditions, plus glued-joint and leg-removal variants. The 2026 whole-body
kinematics paper (722293) reports running. They use different labs' rigs, surfaces, and free versus tethered preparations. The only
headless "no" is a co-activation with a brake neuron. The only other negatives are dose-dependent: no stepping at the lowest
intensities, or in younger, low-expression flies.

Confidence: **high** (about 90-95%). The remaining uncertainty is not about whether the front legs step. It concerns:
- dose and age dependence: robust walking needs older flies and sufficient light (07854-7 line 300; 675944 line 334; 721658 line 134);
- the minor ectopic VNC expression of the split line (721658 ED Fig. 5a, per the records);
- the fact that two of the four sources are the dedicated or blind-excluded ones.

Even using only the eligible, non-dedicated sources (07854-7 Fig. 4 BDN2 alone; 722293), and excluding the co-activation
record, the answer is "yes".
