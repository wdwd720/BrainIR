# pass1-steering: notes

Session `pass1-steering`, pass `pass1`. Family: steering and turning. 14 records (`p1-steering-0001` to `0014`).

## What I searched
- Web searches: Rayshubskiy/Wilson DNa02 steering; Yang 2024 steering; "A central steering circuit" (Feng/Dickson); generic searches for unilateral/SPARC DN activation and turning in walking flies; MDN unilateral backward turning (Sen et al.); DNb05/DNb06/DNa01/DNa03 turning; optomotor DNs.
- Full texts read through the Europe PMC REST full-text XML (PMC12279373, PMC12778575, PMC10614758) because PMC/eLife HTML pages returned a captcha or failed to load. Read bioRxiv HTML for Feng v1 and v2, Dahlhoff 2025, Dallmann 2026, and Rayshubskiy preprint v2.
- I did not visit GitHub or Zenodo. I did not open Pugliese 2026 or Sapkal 2026.

## Sources and decisions
- **Rayshubskiy et al. (eLife 2025 VoR; bioRxiv 2020):** One DN activation: stochastic unilateral ReaChR in DNa02 (SS00730) on a ball, giving a small ipsilateral steering bias. Bilateral siblings were the bootstrap null. The authors attribute forward-velocity changes under symmetric light to visual startle, so I wrote no bilateral record. The preprint has the same experiment, so I did not duplicate it. The 2025 v3 preprint was not opened separately because the VoR supersedes it.
- **Yang et al. (Cell 2024):** DNa02 SPARC-CsChrimson, unilateral (turn, n=8) and bilateral (slowing, n=3), written as two records because the outcomes differ. DNg13 was perturbed only by current injection, so it is not a record. The preprint repeats the same experiments.
- **Feng et al. (bioRxiv v1 2024 / v2 2026):** v1 gives unilateral SPARC activation of DNa11, DNa03, DNae003 (mapped to DNxn123) and DNa02 on a ball (all ipsilateral turns, with very different potency). It also has DNa11 6-leg kinematics, a leg-amputation series, and decapitated flies. v2 adds DNa06 (neck turn, minimal body turning). Per-type n values appear only in figure images, which I could not read. Sex: v2 Methods say "In most of the experiments, only females were used", so I left sex `unknown` for v1. Which DNa03 line (SS96514 or SS84990) was used in Fig. 2c is unconfirmed. bioRxiv rate-limited (HTTP 429) many requests; v2 was eventually read.
- **Dahlhoff et al. (bioRxiv 2025):** SS02553 bilateral activation drives forward walking with more turning. The same paper's SPARC analysis assigns the phenotype to DopaMeander (a dopaminergic local brain interneuron, not a DN) rather than DNp17. Both DNp17 records are low confidence. The kit lists SS02553 as AMBIGUOUS (DNp17;DNut046); I used the paper's name DNp17.
- **Sen et al. 2017 (Curr Biol):** Paywalled. This is an abstract-only, low-confidence record for unilateral/asymmetric MDN activation and backward turning. The effector, preparation, line and turn direction are not verified. Secondary sources disagree about turn direction, so I did not record one.
- **Dallmann et al. 2026 (forward walking, RRN):** Its only DN activation is MDN in a gap-crossing assay (backward walking). That is out of the steering family, so I wrote no record. It is passed on as a lead for the walking/search pass.

## Leads not recorded (other families or no leg readout)
- Bidaye et al. 2020 (DNp09/P9 unilateral, ipsilateral turning) and Braun et al. 2024 (DNa01/DNa02 turning) report DN-driven turning but belong to the walking_stopping family's assigned sources. I did not open them, to avoid duplication. The search pass should check that they are covered.
- Cande et al. 2018 (atlas family) also reports DNa01/DNa02 locomotion effects.
- Flight-only steering DN papers (Ros et al. 2024 for DNae014/DNb01; Buchsbaum & Schnell 2025 for DNp03; DNa03 in flight in Feng et al.) have no leg readout, so they are not records.
- Westeinde et al. 2024 (Nature) activates PFL2/PFL3, not DNs. I did not open it because it contains a steering model.
- Israel et al. 2022 (MooSEZ) activates SEZ neurons, not DNs.

## Simulation / model exposure
- A web-search result summary (I did not open the page) described the Westeinde et al. 2024 PFL3→DNa02/DNa03 steering network model: the steering signal is the L-R difference in DNa02, and DNa03→DNa02 weights are stronger. This is model structure, not a leg-behaviour score or rhythmicity prediction. To be conservative I set `saw_simulation_score` = true on every DNa02 record (0001, 0002, 0003, 0007) and DNa03 record (0005). All other types are false.
- I told the fetch tool to skip model/simulation content for Feng v2, Dahlhoff and Dallmann. It reported none.
- The "simulated fly" in the Rayshubskiy Fig. 8 legend is a bootstrap null, not a DN model.

## Uncertainties
- Quotes come from the fetch tool's verbatim extraction of the source text. I could not view figure images or supplementary videos.
- Turning in already-walking flies is coded with leg fields `not_assessed` (PROTOCOL 3). The DNa11 amputation (0009) and decapitated (0010) records involve stepping during activation, but initiation is not stated. An adjudicator may want to revisit these.
- The `line_specificity` vocabulary lacks a "major non-DN off-target" value. For SS02553 I used `minor_offtarget` with the off-target cells listed, and the notes say the off-target cells probably cause the phenotype.
- Proposed driver lines (`proposed_driver_lines.csv`): SS77821 (DNa11), SS94676 (DNae003→DNxn123), SS96514 and SS84990 (DNa03), and the Yang hemidriver combination R75C10AD;R87D07DBD (DNa02). No new synonyms were needed.
