# Notes: pass1-pugliese_dedicated

## Sources read
- **Pugliese et al.**: Nature 10.1038/s41586-026-11195-y is paywalled (nature.com redirects to login; Europe PMC says not open access). Instead I read the full text of bioRxiv 10.1101/2025.09.12.675944 **v1 and v2** through WebFetch, asking only for real-fly content. There are two real-fly activation experiments:
  - DNg100>CsChrimson in headless flies on a ball (v1 Fig. 2h-k, v2 Fig. 2h-j / ED Fig. 3). The driver line is cited only by reference and no ID is given.
  - DNb08 (SS70620>CsChrimson) in headless flies (v1 Fig. 4c-e, v2 Fig. 5c-e). It is unclear whether the quantified trials were on the ball or with the treadmill removed, so `headless_surface` = `other`. Hind legs are not reported.
- **Sapkal et al. 2026**: I read the full text of bioRxiv 10.64898/2026.04.29.721658 **v2**. v1 was not read separately because of bioRxiv HTTP 429 rate limiting. Records cover:
  - DNg100, DNg97 and MDN in 4 sensory conditions (ball, slippery, air, amputated-in-air): Fig. 1, Fig. 3.
  - DNg100 with FeCO silencing (ED Fig. 1d-e), with front-leg joints glued (ED Fig. 1f-h), unilateral stochastic expression on the ball and in air (Fig. 3g-h), leg removal (ED Fig. 6), intensity titration (ED Fig. 7a-b), and head-intact flies (ED Fig. 7e).
  - DNg16, DNg55 and DNg75 activated alone (no walking; ED Fig. 7e).
  - Co-activation of DNg100 with DNg16, DNg55, DNg75 and DNg97 (Fig. 4). Each combination gets one record per DN type (`multi_dn`).
- The Transmitter news article was opened only as a lead. No record rests on it.

## Not recorded
- BPN (Bolt protocerebral neuron): this is a brain neuron, not a DN, used only as a reference in Sapkal Fig. 4.
- The "DNg100 alone" reference data in Sapkal Fig. 4: this is the same genotype and conditions as Fig. 1, so I did not duplicate it.
- FeCO-silenced DNg100 in the ball and amputated conditions (ED Fig. 1d-e / ED Fig. 3): there is no condition-specific quote. Only the air condition is recorded.
- Pugliese ref. 47/50 (earlier DNg100 headless walking work) was not opened. It is outside this family.

## Uncertainties
- **Driver lines:** Sapkal Supplementary Table 2 (xlsx) downloaded only as compressed binary and could not be read, because I have no shell. Driver IDs are therefore missing for most Sapkal records. The DNg100 split (VT058557-p65ADZp; R85F12-ZpGDBD) is named in the Methods for the stochastic unilateral experiment and matches the kit's DNg100 entry. I did not assume it for the other experiments. No new mappings were needed, so `proposed_*.csv` contain headers only.
- **Quotes:** WebFetch returns short quotes extracted by a summarizer. They were presented as verbatim but could not be checked character by character against the PDF.
- **Sex:** Sapkal Methods: "Male flies were used for all experiments unless otherwise indicated". FeCO-silencing flies were female. Pugliese used female flies.
- **Inferred details** (records set to medium confidence):
  - The ball surface for ED Fig. 7e (single DNg16/DNg55/DNg75 and head-intact DNg100).
  - The leg sets in the leg-removal and glued-joint experiments.
  - Mid-leg stepping "to a smaller extent" for DNg97 in reduced-feedback conditions, coded `unclear`.
- **effect_on_walking:** `not_assessed` for walking induced in non-walking headless flies. For co-activations, the field codes the change relative to DNg100-alone walking.

## Simulation exposure
- **DNg100:** a web-search summary and the Europe PMC abstract summary of Pugliese stated that the computational DN activation screen ranked DNg100 as the top driver of rhythmic leg activity. So `saw_simulation_score` = true on all DNg100 records.
- **DNb08:** the Europe PMC abstract summary stated a model-derived claim that DNb08 drives rhythmic leg movement. So `saw_simulation_score` = true on the DNb08 record.
- **DNg97 and DNg62:** a fetch summary of Pugliese v2 mentioned that they appear in that paper's simulation screen table, but no score or rank was shown. DNg97 records are set to false; this exposure is noted here. No records were written for DNg62.
- Other types (MDN, DNg16, DNg55, DNg75): no simulation scores were seen.
- I did not visit GitHub or Zenodo. GitHub issue links appeared in search results; I read only their search snippets, which contained no scores, and I did not open them. I also did not open an arXiv modeling paper that appeared in the search results.
