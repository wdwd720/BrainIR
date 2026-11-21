# Session R1-harris-a: notes

## Source
- 10.7554/eLife.04493: Harris, Pfeiffer, Rubin, Truman (2015) eLife. Status `full_text`.
- Read: `text.txt` in full (Results, figure, video and supplementary legends, Discussion, Methods); `supp/elife04493s001.txt` (Supplementary file 1, genotypes and off-target expression); Figures 4, 5, 6 and 9 (JPEGs); PDF page 26 (Figure 9 at page resolution) and page 24; `supp/article.txt`, used only to map passages to PDF page numbers (each page ends at the 'Harris et al. eLife 2015' footer line); video frame montages v002, v004, v015 and v016 as spot checks (they agree with the text).
- Missing: the video files themselves (not downloaded, as listed in meta.json). The `*_legend.txt` files say "no legend found", but the video legends are in text.txt and I used those. The two peer-review sub-articles were not included in text.txt, and I did not read them.
- No model, simulation or prediction content was seen. I opened no external site. No `sightings.csv` was written because there was nothing to report.

## Experiments in scope (all: TRPA1 heat ramp, decapitated adult females, unless noted)
| record | hemilineage | driver (behaviour genotype from Supp. file 1) |
|---|---|---|
| 0001 | 1A | R22G11-LexA > LexAop-TRPA1 |
| 0002 | 2A | R50G08-GAL4 > UAS-TRPA1 |
| 0003 | 3B | R23B05-LexA > LexAop-TRPA1 (the text calls it 'R23B05-GAL4') |
| 0004 | 5B | R86D02 immortalised line, decapitated |
| 0005 | 5B | same line, **tethered intact flies on a Styrofoam ball** (preparation `other`) |
| 0006 | 6A | R35A03 immortalised line |
| 0007 | 6B | R46C11 immortalised line |
| 0008 | 7B | R65A12 immortalised line (Videos 8 and 9 coded as one record) |
| 0009 | 8A | R69H11-GAL4 > UAS-TRPA1 |
| 0010 | 9A | R52E12-GAL4 > UAS-TRPA1 |
| 0011 | 10B | R13B08 immortalised line |
| 0012 | 11A/B | R26B05 immortalised line (whole lineage 11; one record listing 11A;11B) |
| 0013 | 12A | R24B02 immortalised line |
| 0014 | 12B | R15D11 immortalised line |
| 0015 | 13B | R41G09-GAL4 > UAS-TRPA1 |

## In-scope hemilineages with no activation experiment (`not_in_source`)
- 0A, 4A: 'hemilineages 0A, 4A, 16B and 17A are not addressed in this study'.
- 1B: line not used, because of expression in a dorsal hemilineage (6A per Supp. file 1). Anatomy only.
- 3A: line had sensory-neuron contamination and was not used for behaviour. Anatomy only.
- 8B: line had expression in other hemilineages and was not used for behaviour. Anatomy only.
- 13A: 'We did not have a clean enough line'. Anatomy only.
- 4B: mentioned only in anatomy/Discussion; no line and no activation.
- 00B, 09B: not mentioned as tested (9B does not survive per the text: 'the surviving 9A neurons').
- 11A and 11B: not tested separately. The single coverage row `11A/B` (1 record) covers both scope hemilineages 11A and 11B.

## Coding conventions and hard cases
- **Figure 9A** (bar chart of the % of flies in six categories, n = 15-25 per line) was used to code 'no' where a line had no bar in a category (e.g. no takeoff bar means d10 `no`). Many rows also have very small marks that I could not reliably tell apart from the row baseline at the available resolution. My rule:
  - a small mark that the text supports was coded `yes`;
  - a small mark that the text does not mention was coded `unclear`;
  - where the text explicitly says 'no' (5B wings, 6B wing buzzing), the explicit text took priority, and the possible mark is noted in the record.
  I did not enter penetrance values read off the bars.
- 'Posture change' without a direction was coded `unclear` for d5/d6 (8A, 9A, 11A/B, 10B small mark). 'Splayed out' legs (9A, 5B) are not called flexion or extension, so they are `unclear` unless the text says more. For 5B, d5 is `yes` (body 'closer to the ground'). For 13B, d6 is `yes` (legs extended to the side) and d5 is `yes` (body lowered and held, 'resting on their coxae').
- Grooming that is reported as continuing during the ramp was coded d9 `yes`, because the protocol codes what is reported during activation. The control decapitated flies also groom occasionally (Video 1 text). For 5B, grooming 'appeared to be suppressed', so d9 is `no`.
- Going airborne: 2A (text plus a takeoff bar in Figure 9A) and 10B (text 'Rarely a fly would go airborne' plus a small mark) were coded d10 `yes`. 12A ('careening into the air' with 'no organized jump', and no takeoff bar) was coded `unclear`.
- 11A/B: the tsh-GAL80 control removes the lineage-11 expression and leaves the descending neurons, so it is not an activation of the hemilineage. It is noted in `other_observation` (takeoff 9%, N = 22, vs 100%, N = 13) and not coded as a record.
- record_type: every line was coded `whole_two_sided`. The authors state that 'the predominant expression in the line was from the target hemilineage' and that the driver lines capture the neuropil features of the MARCM clones. Off-target expression from Supp. file 1 is quoted in `coverage_notes`. None of the behaviour lines is described by the source as partial.
- Body parts never mentioned (halteres d14, abdomen d15) are `not_assessed` throughout.

## Discrepancies inside the source (recorded, not resolved)
- Supp. file 1 labels the R50G08 row '2B', but the text and Video 3 use R50G08 for 2A. I coded it as 2A.
- The Figure 4 legend panel O says 'activation of the 3A', but the panel sits under the 3B heading and the 3A line was not used. I treated it as 3B.
- The text cites 'Figure 6D' for 6A; the panel is Figure 5D.
- The maximum ramp temperature differs between the video legend and the figure labels for 8A (32 vs 37 °C) and 13B (32 vs 37 °C).
- The Video 22 legend (24B, outside my scope) names driver R22G11, the 1A line. The text says R15A03 was used for 24B. Not coded by me.
- For 3B, the text names R23B05-GAL4, while Supp. file 1 lists R23B05-LexA/LexAop-TRPA1.
