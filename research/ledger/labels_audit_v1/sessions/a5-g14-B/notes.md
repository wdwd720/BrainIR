# a5-g14-B notes

## Pugliese et al. 2026 (10.1038/s41586-026-11195-y)
- The cached text is the abstract only. I used WebFetch on nature.com (the article page and the pages for Fig. 2, Fig. 5 and Extended Data Fig. 10). These pages give the abstract, figure legends and video captions; the Results, Methods and Supplementary Information were not available.
- Quotes come from the fetched legends, not from text.txt, so their notes start with `figure:`.
- **DNg100 record:** the legend gives no driver line (only "DNg100 > CsChrimson"). Stimulation wavelength and duration are not given either.
- **DNb08 record:**
  - The driver is SS70620.
  - The legend reports front and middle legs only, so the hind legs are `not_assessed`.
  - The legend does not say what surface the headless flies were on, so `headless_surface` = `other`.
- The abstract reports simulation results for DNg100 (strongest simulated driver) and DNb08 (predicted to drive rhythm), so `saw_simulation_score` = true on both records. The records rest only on the fly experiments.
- No experiment on DNp01, DNg62 or DNfl023 was visible in the material I could fetch.

## Hampel et al. 2015 (10.7554/elife.08758)
- aDN1 maps to DNg62 and aDN2 maps to DNfl023 (synonyms.csv, high confidence).
- driver_lines.csv also lists aDN2-spGAL4-2/3/4 as DNg127 (UNMAPPED) from a different table. I followed synonyms.csv; this conflict should be checked.
- **Coding of antennal grooming:** front legs `yes`. Middle and hind legs `unclear`, because the paper does not describe them.
- **Lines not coded:** the broad GAL4 lines R71D01, R76F12, R70H02 and R34C03 (Fig. 2—figure supplement 1A). The paper does not say these GAL4 patterns contain aDN1 or aDN2; it only used their enhancers for the split lines. The paper also mentions "additional spGAL4 pairs" for aDN2 that are "not shown"; these were not coded either.
- Antenna amputation increased grooming for some lines but did not change the behaviour type, so I wrote one record per line.

## eLife 87602
- No activation experiment on any assigned DN type.

## Types with no records
- DNp01 (Giant Fiber): no qualifying experiment in the assigned sources.
