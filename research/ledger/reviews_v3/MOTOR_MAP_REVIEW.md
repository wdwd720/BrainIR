# Motor map v1: fresh reviewer check

Reviewed (2026-11-21): `MOTOR_MAP_v1.csv` / `.json`, `motor_map_v3.py`, `networks.py` and its full-cord table. The table's
`instance` column (e.g. `MNwm19_PDMNa_R`) gives each MN's exit nerve and a side suffix, which I used as a cross-check.
"(summary)" marks a source seen only as a web-search summary; FBbt pages without that mark were read directly.

## Verdict: approve with changes

No blocker. One major issue changes pool membership; the rest are labels, documentation and use notes.

## Findings

**F1. STTMm (MNwm01, MNwm02; 4 rows, T2) is mislabelled as a sternotrochanter MN. Severity: major.**
- *Issue:* The map labels them `leg_sternotrochanter_meso` and puts them in pools `any_body;middle_leg` only.
- *Evidence:*
  - FlyBase FBbt:00053058 lists `STTMm` as an exact synonym of "satellite tergotrochanter muscle motor neuron". It is smaller than the TTM MN, "also innervates the mesothoracic tergotrochanter muscle", has a mesothoracic soma, exits the PDMN, and there are two per side (Bacon & Strausfeld 1986). The table matches: PDMNp, T2, one of each type per side, the same nerve as TTMn.
  - FBbt_00053153 groups STTMm with TTMn as mesothoracic extracoxal trochanter depressor MNs, and notes that Miller (1950) has no mesothoracic sternotrochanter muscle.
  - The leg-nerve `Sternotrochanter MN` (MNml08/22; FBbt_00053572) is a different type, already in `middle_leg_extensor`.
  - The FlyBase entry also cites the excluded MANC premotor paper, which coined the name STTMm. I read only FlyBase's anatomical wording, not the paper.
- *Consequence:* If STTMm are TTM MNs, `jump` holds only 2 of 6 TTM MNs. If they are sternotrochanter MNs, they belong in `middle_leg_extensor`. "`middle_leg` only" fits neither reading, though keeping them out of the wing pools is right.
- *Linked inconsistency:* TTMn drives the same leg muscle (FBbt:00007406: muscle 66, extracoxal trochanter depressor) but has `body_part` = `wing` and is not in `middle_leg`.
- *Correction:*
  - STTMm: action `jump_TTM_satellite`, pools `any_body;jump`.
  - TTMn and STTMm: `body_part` = `middle_leg`.
  - Decide once whether all six TTM MNs also count in `middle_leg` / `middle_leg_extensor`.
  - If `jump` is meant to be the large TTMn only, say so in the PREREG.

**F2. `segment` and `side` are the soma's, not always the muscle's. Severity: minor.**
- *Leg MNs are correct:* For all 391 leg MNs, the soma segment is the leg's segment and the soma side is the leg's side. None disagree.
- *Exceptions (non-leg):*
  - DLMn a,b (MN5, 2 rows): soma contralateral to its muscle (Ikeda & Koenig 1988, summary). The instance suffix is opposite.
  - DLMn c-f (8) and DVMn 3a,b (4): T1 somata, mesothoracic muscles.
  - MNad26/28/29 (6): T3 somata, exit via abdominal nerve AbN1.
  - Abdominal MNs: 31 contralateral (MNad02, 06, 17, 49, 53, 63, 69), 1 bilateral (MNad50) and 12 with no side.
  - The neck MNs ADNM1/2 are also contralateral.
- *Impact:* No pool is split by side or segment, so nothing changes now.
- *Correction:* Rename the columns `soma_segment` / `soma_side`, and add `target_side` from the instance suffix.

**F3. The abdomen pool includes terminal-segment MNs. Severity: minor, but major if "abdomen movement" is predicted from any pool activity.**
- *Composition:* Of the 229 abdominal MNs, 164 exit via AbN1–4 and 65 via the abdominal nerve trunk (AbNT). Of the 65, 49 have A8–A10 somata.
- *Evidence:* FBbt:00047365 ("adult abdominal doublesex (male) neuron") states that some of these neurons "innervate the internal genitalia via the abdominal nerve trunk". So part of the pool may drive terminalia or internal reproductive muscles rather than the abdominal wall. This rests on nerve and neuromere annotation, not on identified muscles.
- *Correction:* Keep the membership, add sub-labels `abdomen_wall` (AbN1–4) and `abdomen_terminal` (AbNT), and check that the predictions do not hinge on the AbNT MNs.

**F4. Module coverage and pool sizes are uneven. Severity: minor.**
- *Coverage:* MNs with no module (`leg_unassigned`): 0/141 front, 24/119 middle, 38/131 hind. `tarsus_control` exists only in T1. So the middle and hind flexor pools (41, 39) and extensor pools (14, 16) are lower bounds; the front-leg pools (51, 20) are complete.
- *Sizes:* Pools range from 2 (`jump`) to 702 (`any_body`: 56% leg, 33% abdominal MNs). A mean over `any_body` would hide wing or haltere activity.
- *Correction:* Normalise before comparing legs. Summarise `any_body` as an OR or max over the body-part pools.

**F5. Tension muscles are labelled as steering muscles. Severity: minor.**
- *Issue:* tp1, tp2, tpn, ps1 and ps2 (10 rows) are labelled "direct (steering) flight muscle". tpn is treated as tergopleural by name only.
- *Evidence:* Tergopleural muscles are tension muscles (Wisser & Nachtigall 1984, cited in FBbt_00003386). The pleurosternal muscle is an indirect muscle that sets thoracic tension (FBbt_00003393). Both from summaries.
- *Impact:* None on pools. They are correctly in `wing_any` and not in `wing_power`.
- *Correction:* Use the action `wing_tension`.

**F6. The `xm` MNs are excluded without stated reasons. Severity: minor.**
- *Issue:* MNxm01 shares exit nerve, soma segment (T1) and hemilineage (03B) with DLMn c-f. MNxm02/03 exit via the dorsal metathoracic nerve. Both point to dorsal thoracic muscles, but the targets are unknown.
- *Correction:* Excluding them from every pool, including `any_body`, is defensible. Record it as deliberate.

## Items

1. **Checked.** Every subclass → body-part assignment is right, and exit nerves agree (fl prothoracic nerves; ml MesoLN; hl MetaLN, plus AbN1 for 8; hm AbN1; wm ADMN/PDMN/MesoAN; ad AbN1–4/AbNT; nm CvN/DProN, rightly in no pool since the fly is headless; xm PDMNa/DMetaN). Exception: TTMn/STTMm (F1).
2. **Checked.** Correct: DLMn (MN1–4 one fibre each, MN5 two; summary) and DVMn (7 per side) as `wing_power`; TTMn in `jump`, not a wing pool; the steering names, with MNwm35/36 in `wing_any`; hDVM as the haltere power muscle and hi1/hi2/hiii2 among its seven steering muscles (Dickerson et al. 2019, summary). Wrong: STTMm (F1), tension labels (F5).
3. **Checked.** Right: tibia and trochanter flexors/extensors plus the extracoxal trochanter depressors (FBbt_00053152 family) fold or extend the leg. Coxa muscles (move the whole leg at the thorax), femur reductor (rotation), ltm (claw grip) and tarsal muscles are rightly excluded. Coverage caveat: F4.
4. **Checked.** Both columns are soma-based. None of the 391 leg MNs disagree with their leg's segment or side; exceptions are non-leg MNs only (F2).
5. **Checked.** The JSON counts equal the CSV, and the CSV equals the table for 732/732 rows. `any_body` = 732 − 24 nm − 6 xm. The only mis-pooled MNs are STTMm (F1).
6. **Checked.** F3, F4.

## Sightings

- **Copulation circuitry and descending neurons.** A search summary (AbNT/genitalia query) described the copulation roles of abdominal dsx glutamatergic MNs and GABAergic neurons (eLife 20713). It also stated in one line that some descending neurons control copulation and oviposition. Not opened; I stopped that topic.
- **Haltere muscles.** A summary of Dickerson et al. 2019 gave the outcome of activating the haltere steering muscles (changes in wing steering). I used only the muscle names.
- **TTMn FlyBase page.** FBbt:00007406 has behavioural and song content, which the fetch tool skipped.
- **MANC premotor preprint.** eLife RP 96084v2 appeared in search results; not opened.

No hemilineage activation or silencing outcome was seen. F3's FBbt:00047365 citation was reached through the same search as the copulation content; only its anatomical sentence was read. Nothing else here informed a finding.

## Confirmation of applied changes

Confirmation: confirmed

Checked on 2026-11-21 against the version I reviewed (commit 0a0def8) and the annotation table. The map files on disk equal HEAD (8735f04). No new sources were consulted.
- **What changed.** Exactly 16 rows changed:
  - TTMn (2) and STTMm (4): body part `middle_leg`, actions `jump_TTM` / `jump_STTM`, pools `any_body;middle_leg;jump`.
  - ps1, ps2, tp1, tp2, tpn (10): action `wing_tension`, pools `any_body;wing_any`.

  Nothing else changed.
- **F1 resolved.** `jump` = 6 and `middle_leg` = 125. None of the six TTM MNs is in a flexor or extensor pool, so all six are treated alike.
- **Counts.** The JSON counts equal the CSV. The CSV equals the table for 732/732 rows.
- **Soma side and segment.** All 397 leg MNs, including the six TTM MNs, have their soma in their leg's segment and on its side. The JSON note claiming this holds.
- **F2, F4, F6.** The JSON notes document them.
- **F3.** Scoring as the fraction of all 229 MNs keeps it minor. The terminal-segment MNs alone can reach at most 65/229 (28%).
- **Nit (no pool effect).** The `wing_tension` basis still says "direct flight muscle", but FBbt_00003393 (summary) classes the pleurosternal muscle as indirect. Suggest "flight control (tension) muscle".
- **Open usage point (outside the map).** If `any_body` is also scored as a fraction of 702 MNs, wing and haltere activity is diluted (F4).
