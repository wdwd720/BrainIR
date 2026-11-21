# Session pass1-recent_broad-r1-01 — notes

Pass `pass1`. Source family: other activation studies, 2018-2026. I read only the four sources in `assigned_sources.csv`,
using the local copies in `sources/`. I did no web searches, opened no model or simulation material and did not visit
GitHub or Zenodo. **No score sightings**, so there is no `sightings.csv`. Every record has `saw_simulation_score` = false.

## Overall result
14 records from 4 sources, and every source has a disposition of `records`. **No assigned source reports leg movement
during DN activation.** All four are egg-laying or female-receptivity studies. Their activation outcomes are abdomen,
ovipositor or wing actions (abdomen bend, ovipositor extrusion, egg pushing or expulsion, vaginal plate opening, wing
spreading). Under the abdomen/wing convention (PROTOCOL section 3), all leg-rhythm fields are `not_assessed` and
`effect_on_walking` = `not_assessed`. I included these experiments as records because the flies were adult, intact or
headless, free or walking on a wheel, and filmed, so leg movement was observable even though the papers do not describe it.

## Per source
- **10.1038/s41586-023-06271-6 (Vijayan et al. 2023).** Full text, figures and supplementary tables were available; the
  videos were not. Two records: Fig. 2 (5 s high-intensity stimulation) and Extended Data Fig. 5o-s (prolonged gentle
  stimulation), both with oviDN-SS1 > CsChrimson in head-fixed females on the wheel. I did not record Extended Data
  Fig. 6 (electrophysiology/imaging with CsChrimson, no behavioural readout; in the abdominal-ganglion preparation the
  abdomen was glued). Fig. 2a plots wheel position, but locomotion during stimulation is not analysed.
- **10.1038/s41586-020-2055-9 (Wang et al. 2020).** Only text and legends from XML. Figure images, Supplementary
  Tables 1-2 and videos were not downloaded. Because of this:
  - the stock IDs of oviDN-SS1/SS2 cannot be confirmed from this source. oviDN-SS1 = VT050660 x VT028160 (= SS46540)
    comes from Vijayan 2023 Supplementary Table 1.
  - the driver line used for Fig. 2 is not named in the text (`driver_lines` = [], `line_specificity` = unknown).
  - Fig. 2 virgin and mated conditions are split into two records because the egg-deposition outcome differs.
    Extended Data Fig. 6 appears to show the same mated dataset and was folded into the Fig. 2 mated record.

  The paper also mentions a Gen-1 GAL4 activation screen of several hundred lines, but it does not report lines
  individually, so I wrote no screen records. I did not record activations of SAG, SPSN, pC1 or oviEN neurons because
  they are not DNs.
- **10.1038/s41467-024-53610-w (Li, Chen et al. 2024).** Text is extracted from the PDF and page images were available.
  The supplementary information (including Supp. Fig. 5a, Supp. Table 1 and the movies) was not reachable (HTTP 500 in
  meta). Specific points:
  - **Other species:** I recorded only *D. melanogaster* experiments. The same dsx-brain activations in *D. santomea*
    (robust wing spreading; leaning/flipping over) and *D. yakuba* (wing movement with female song) were not recorded,
    because MANC types are *D. melanogaster*. A later pass may decide otherwise.
  - **vpoDN-SS1 and vpoDN-SS3:** these were tested for VPO, but their results are only in Supp. Fig. 5a (unavailable).
    The text says only that SS2 "had the most robust abdomen extension phenotype". I wrote no records for SS1/SS3
    rather than guess their outcome. **A fetch session should retrieve Supp. Fig. 5a.**
  - **vpoDN (pMN2) is UNMAPPED:** it is not in `type_list.csv`/`synonyms.csv`. `driver_lines.csv` lists vpoDN lines
    (SS50200, SS50795, ...) only as DNp37/UNMAPPED. It is female-specific and likely absent from male MANC.
  - **DNp13 (pMN1)** maps exactly.
  - **Decapitated flies** stood in the acrylic arena, so I coded `headless_surface` = `other`.
  - The Methods say that activation responses "such as grooming, jumping and turning" were scored as invalid events.
    These leg-related responses were not quantified or attributed, so they are not coded.
- **10.1038/s41598-023-48109-1 (Oliveira-Ferreira et al. 2023).** Text is extracted from the PDF, with page images. The
  supplementary files were not available.
  - The OvAbg, OvAbg/Cha, OvAbg/VGlut and OvAbg/Gad1 lines label abdominal-ganglion-intrinsic neurons (not DNs), so
    they are not recorded. The same applies to the VT038154-LexA activation (Supp. Fig. 7f,g) and the split-GAL4
    "activation screen" selected for abdominal-ganglion expression (not a DN screen, and lines not reported).
  - Two records come from Fig. 7i,j: oviDN-GAL4 activation alone (treatment 1) and with VT038154-LexA silencing
    (treatment 2). Percentages were read from the bar charts in the page image.
  - oviDN-GAL4 specificity in this paper is in Supp. Fig. 7a,b, which is unavailable.

## Mapping issues / uncertainties
- `oviDN` is itself a MANC type in the kit. I mapped all oviDN lines (labelling oviDNa + oviDNb) to that one type with
  `line_specificity` = clean where the paper says only oviDNs are labelled. I proposed oviDNa/oviDNb as synonyms of
  `oviDN`.
- **Kit conflict:** `synonyms.csv` lists pMP1 as a synonym of oviDN (Wang 2020a). Wang et al. 2020 (Nature, this
  session) calls pMP1 an *unrelated* cell that oviDN-SS2 labels weakly and that is present in both sexes. Please review.
- I proposed driver-line rows for oviDN-SS1, oviDN-GAL4, oviDN-SS2 and the dsx-GAL4 ∩ Otd-Flp intersection.
- `labeler_confidence` is `medium` throughout: the full text was read, but leg behaviour is not described and some
  figures/supplements were missing.
- I could not run a JSON validator in this session (no shell). I checked by eye that `out/records.jsonl` has one JSON
  object per line (14 lines) and that every quote is at most 25 words.
