# pass2-recent_broad — notes

## What I did
- Read PROTOCOL.md, schema and kit files. Labelled all 39 experiment rows of `experiments_to_label.csv` from my own
  reading: 39 records, every row found, so `not_found.csv` has only its header. All rows had n_siblings = 1.
- Records are not in exp_id order in records.jsonl (they were saved as sources became reachable). Each record_id
  number matches its exp_id number.
- Full texts: Europe PMC REST `fullTextXML` (PMC6135764, PMC7710706, PMC8926844, PMC6097840, PMC9849133, PMC6828327,
  PMC8298091); bioRxiv full text / JATS XML for the preprints (2025.07.22.666129 v1, 2024.06.27.601106 v1,
  2025.12.13.693955 v1, 2026.01.04.697356 v1, 2026.02.26.708359 v1, 2026.05.03.722293).
- The text was read through a fetch tool that summarises long pages in chunks. Quotes are the verbatim sentences it
  returned. Long documents were sometimes only partly covered (see "not accessed").
- bioRxiv returned HTTP 429 (rate limit) many times; I waited and retried.

## Accidental exposure to a simulation result (PROTOCOL section 6)
- While running a general web search for an open copy of 10.64898/2026.05.03.722293 (the query mentioned DNg100/BDN2),
  the search engine's summary included text from Pugliese et al. (a forbidden source) with a model/simulation-based claim
  about DNg100. I did not open that source, did not use it, and stopped reading. Every DNg100 record is marked
  `saw_simulation_score = true`. No other DN type appeared in that snippet with a model score. After this I stopped
  open web searches on DN types.

## Not accessed / not read
- Supplementary tables with genotypes/driver-line IDs: Nat Commun 2020 Suppl. Table 2 (MDN genotypes), Nature 2023
  Suppl. Table 2 (DNp02/04/06/11 lines), Liessem 2025 Supplemental Table 1 (landing DN lines), Dallmann 2026 Suppl.
  Table 2. So `driver_lines` is `[]` where the paper text names none.
- Supplementary video captions were mostly not available in the text (e.g. Supp. Video 6 of 2024.06.27.601106).
- 2024.06.27.601106: labelled from v1 ("A central steering circuit in Drosophila"), as the locators say "(v1)"; v2 is
  retitled.

## Uncertain points / deviations from pass1 inputs
- 0001 DNp09 / SS01540: the kit lists the line as AMBIGUOUS (DNp09;DNp71). Kept DNp09, mapping medium. Behaviour is
  freezing, preceded by a brief speed-up.
- 0002-0004 MDN (Nat Commun 2020): the headless surface (ball) is inferred from Methods, which say decapitated flies used
  the same tethered-ball protocol.
- 0007: Video S4 shows MDN3-GAL4 decapitated flies; I could not confirm that VT50660-GAL4 was also tested headless. Both
  lines kept as listed.
- 0009: SS01613 = "Split3" (larval MDN line) in the source.
- 0010: the light intensity (~4.6 uW/mm2) comes from Methods; pass1 had "not stated". Expression coded stochastic
  because the extra labelled neurons varied between brains.
- 0011/0012 DNp17 / SS02553: kit AMBIGUOUS (DNp17;DNut046). The line labels about 7 other neuron types (none named as
  DNs), so I coded minor_offtarget, although the off-target labelling is substantial. The authors attribute the speed
  increase mainly to DopaMeander, not DNp17, so I coded the SPARC record as no clear effect with low confidence.
- 0013-0020 (Dombrovski 2023): rows for the combination lines are coded multi_dn. aSP22 (0033, Liessem) has no
  type-specific sentence; landing is inferred from "all but one DN ... elicited landing" plus DNb05 being named as the
  exception.
- 0022 quote: the fetch tool returned this sentence as two consecutive fragments, split at "... MDN>CsChrimson animals" /
  "or antennal grooming in aDN>CsChrimson animals". I joined them, so the junction should be re-checked against the
  source.
- 0038 DNg100 (whole-body 3D kinematics, v1): sex and n not stated; `saw_simulation_score` = true (see above).
- 0022 aDN: paper says "aDN"; the kit maps line R76F12-AD;R18C11-DBD to aDN2 = DNfl023 (medium). Antennal grooming is
  coded as front legs = yes, middle/hind = unclear.
- 0023-0028 (steering): flies were walking on the ball when stimulated, so per the convention the leg-rhythm fields are
  not_assessed and effect_on_walking = turns. 0025 (headless DNa11): legs unclear, low confidence.
- 0029-0034 (landing DNs): flies were flying and pin-tethered. Landing extension is a single movement, so legs = no.
  For DNp10, I could not confirm VT031084-LexA as the behavioural driver.
- 0036/0037 Pair1: not in the kit; the paper gives no adult DN type name, so UNMAPPED.
- 0039: driver written "VT50600.p65AD" in the source (MDN hemidriver is elsewhere VT50660); the paper also lists
  SS03131.
- New line-to-type pairings are recorded in proposed_driver_lines.csv (SS77821, SS84990, SS96514, SS94676).
