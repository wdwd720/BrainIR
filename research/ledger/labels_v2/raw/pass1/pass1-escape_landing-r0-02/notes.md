# Notes: session pass1-escape_landing-r0-02 (pass1)

## Sources
One assigned source: 10.64898/2025.12.13.693955 (Liessem, Asinof et al., bioRxiv 2025, "Parallel neuronal ensembles
control behavior across sensorimotor levels in Drosophila"). Read the local `text.txt` (JATS full text, legends, methods),
`supp/article.txt` (PDF text including Supplemental Tables 1-5), and figure images Fig. 1, 2, 4, S1-1, S2-1, S2-2 and S3-2.
I did not use the web (per section 8). Disposition: `records` (10 records).

## What was recorded
- CsChrimson activation (625 nm, 150 uW/mm2, 50 ms) in pin-tethered **flying** female flies, with DeepLabCut leg tracking:
  DNp07_1 (SS02276), DNp07_2 (SS02612), DNp10 (SS01608), DNp47 (R70C09-GAL4), DNg79 (SS81942), DNb05 (SS01051).
  All except DNb05 drove the landing leg extension (single movement, so legs coded `no` for rhythm). DNb05 had no effect.
- DNb05 null result "confirmed (data not shown)" with multiple other lines: written as one combined low-confidence record
  listing the five additional DNb05 lines in Supplemental Table 1. The paper does not say exactly which ones were tested.
- Open-field **walking** flies (Fig. S2-2G, Video S9), DNp07_1 and DNp10: only wing flicking was scored. Legs coded
  `not_assessed`.
- Wingbeat and flight cessation (Fig. 2J-K, S2-2C-F) and abdominal deflection (Fig. 2M, S2-2I-J) came from the same
  pin-tethered setup. I folded them into the leg records as secondary behaviours instead of writing separate records.

## Not recorded (and why)
- Optogenetic activation of visual projection neurons (LPLC4, LLPC1/2/3, LPLC2, LC22, etc.): they are not DNs.
- Kir2.1 silencing, patch-clamp of DNp10, connectomics: not activation experiments.
- aSP22: only cited (McKellar et al. 2019), not tested here. DNg19871: the paper says it has no driver line.
- Supplemental Table 3 lists DNp07_1/DNp10 under "Fig. S3 B-E", but no DN data appear in Fig. S3-2. I assumed a table
  artefact and wrote no record.
- DNb04 (SS01582) is listed in Supplemental Table 1, but the paper reports no experiment with it.

## Uncertainties
- **SS81942** is annotated in the kit as labelling DNg31 and DNg79. The paper calls it DNg79 only and says DNg79 has two
  left-right pairs. Per section 1 I wrote two records, DNg79 (high) and DNg31 (medium mapping, low labeler confidence),
  both `multi_dn`. An adjudicator should check whether the two annotations are really the two DNg79 pairs.
- **DNp47 line**: genotype GMR70C09-GAL4 (BDSC #39524), but the paper lists the identifier "SS39524". I coded it as
  `R70C09` and proposed it in `proposed_driver_lines.csv`. Specificity is `unknown`.
- **SS02612**: the kit notes about 2 background off-target cell types, which the paper does not mention. Specificity is
  `unknown`.
- DNp10 penetrance (Fig. 1F) was read from the bar plot (slightly below 100%). No exact value is in the text.
- Light wavelength: Fig. 1D says 653 nm and Methods say 625 nm.
- Expression is coded `bilateral` because these are standard non-stochastic driver lines; the paper does not say so
  explicitly.
- Videos S1-S21 were not downloaded. I used text, legends and figures only.

## Model / simulation exposure
The paper has its own connectome analyses (cosine similarity, ShREC, consensus clustering) and its own leaky
integrate-and-fire simulation of LPLC4 -> landing DN responses (Fig. S4-1B, described in the text; I did not open that
image). Under section 8 another paper's own model does not count as a sighting. I saw no Pugliese-type rhythm score,
rank or driver call. No `sightings.csv` was written, and `saw_simulation_score` = false on all records.
