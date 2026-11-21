# Session pass1-recent_broad-r0-01 — notes

Pass `pass1`, source family "other activation studies, especially 2018-2026". I read PROTOCOL.md (v2) in full, then only the 6 assigned sources from their local copies in `sources/`. I used no web access and did not open any model, simulation, GitHub or Zenodo resource. GitHub links printed in two papers' data-availability sections were not followed.

## Per-source summary

| DOI | disposition | records | what was read |
|---|---|---|---|
| 10.1016/j.conb.2023.102822 (Simpson 2024 review) | no_qualifying_experiment | 0 | full text + Fig. 1. It is a review: it cites DN activation results from other papers (MDN, DNp09, DNg11/12, etc.) but has no primary experiment, so I wrote no records from it. |
| 10.1016/j.cub.2022.01.035 (Israel 2022) | records | 7 | full text, figures gr1-gr7, Document S1 (Figs S1-S4, Table S2), Table S1 (stats CSV). Videos not downloaded. |
| 10.1016/j.cub.2026.09.056 (Cao & Anderson 2026) | records | 5 | text, legends and key resources table. **No figure images and no supplement** (Figs S1-S7, Tables S1-S2) were available locally. |
| 10.1016/j.isci.2026.114902 (Guo 2026, LegPN) | no_qualifying_experiment | 0 | full text and legends. The activated neurons are LegPNs (ascending, AN05B100), LegPLs and LegPCs (VNC interneurons). No DN line was activated. |
| 10.1016/j.isci.2026.115624 (axo-axonic DN synapses) | no_qualifying_experiment | 0 | relevant results/methods. Giant fiber CsChrimson activation (intact and headless) was read out only as TTM/DLM muscle potentials in wax-mounted flies, so leg movement was not observable. Axc = AN08B098 (ascending). |
| 10.1016/j.neuron.2020.07.032 (Bidaye 2020) | records | 9 | text, legends and key resources table from PMC XML. **No figure images and no supplementary figures** were available locally. |

## Uncertainties and decisions

- **Israel 2022:** GH146II-, NP225- and NP5288-GAL4 drive backward walking through MooSEZ, which is an SEZ interneuron and not a DN. The paper does not say these lines label any DN, so I wrote no records for them. VT50660-GAL4 is the paper's "broad MDN driver", but it never names the other cells it labels, so I set `line_specificity` = unknown. I coded the decapitated MDN flies on the flat arena floor as `headless_surface` = other. Fig. 3B and Fig. 7H are control or long-duration MDN activations in separate figures, so each got its own record as section 1 requires. Walking was measured by centroid tracking only (Ctrax), with no leg tracking.
- **Cao & Anderson 2026:** I mapped DNpe050 to DNxn183 through the kit synonym. All DN effects are on the wings (wing elevation, pump). The legs were not described beyond "turning and charging not elicited", so I set the leg-rhythm fields to `not_assessed` and `effect_on_walking` to none. The coactivation of DNp60-split2 with four other DNpe050 split lines (Fig. S4C-D) is not recorded: the lines are not named in the main text and the supplement is missing. AVLP491 and AVLP710m are interneurons, so they were not recorded.
- **Bidaye 2020: systematic screen not fully recorded.** The paper screened 156 DN lines by CsChrimson activation (Fig. 1A-B, Fig. S1A, n=12-16 per genotype per condition). Per-line results exist only in those figures, which are not available here, and the text says genotype details are "available on request". **A session with web access should fetch Fig. 1B and Fig. S1A** so that records can be added for every screened line, including lines with no effect. SS02635 is listed in the key resources table and may be the third primary hit that failed on retest. That is unconfirmed, so I wrote no record for it.
- **Bidaye 2020: SS01587 mapping.** The paper says SS01587 "labels DN0p28 and 7 other neuronal types". "DN0p28" looks like a typo. The kit's driver_lines.csv maps SS01587 to DNp29 (Namiki 2018). I coded DNp29 with low mapping confidence and explained the conflict. The paper's mosaic analysis attributes the walking to BPN, a non-DN higher-brain type, so the DN record has low labeler confidence.
- **Bidaye 2020: P9/DNp09.** The kit lists DNp09 as ambiguous (it is also the hemibrain name of DNp71). I chose DNp09 with medium confidence, based on the paper's anatomy. I proposed "P9" as a synonym. For the Fig. S2F freezing genotype I assumed SS01540 (Methods mention gamma-lobe off-target expression only in SS01540); it could not be verified without Fig. S2.
- I set `effect_on_walking` = not_assessed for walking-initiation experiments in non-walking (grooming or copulating) flies, because the test was initiation rather than modulation of ongoing walking.

## Score sightings

None. I saw no Pugliese-type rhythm score, rank or driver call. Source 10.1016/j.isci.2026.115624 contains its own leaky integrate-and-fire VNC simulation of Axc→GF excitability. Section 8 says another paper's own model does not count, and it gives no DN rhythm scores. Cao & Anderson 2026 cites the Sapkal 2026 preprint only as a reference; I did not open it. No `sightings.csv` was written.

## Validation

`records.jsonl` has 21 records, one JSON object per line, with record IDs pass1-recent_broad-r0-01-0001 to -0021. I wrote them by hand against record_schema.json; no shell was available to run a schema validator. All quotes were copied verbatim and are 25 words or fewer.
