# Notes: session pass1-walking_stopping-r1-02 (pass1)

Web fetching was allowed for the three assigned DOIs only. I did not search for other papers. I did not open GitHub, Zenodo, Pugliese et al. or Sapkal et al. I saw no simulation scores, ranks or driver calls, so there is no sightings.csv.

## 10.1038/nmeth.2973 (FlyMAD, Bath et al. 2014)
- The local folder had only the abstract. nature.com shows only a subscription preview: the abstract, figure titles and supplementary item legends. The article is not in PMC, and Europe PMC REST calls returned 500.
- What I read: the Fig. 2 image (media.springernature.com, full size) and the supplementary video legend "Activating Moonwalker neurons with TrpA1" (MOESM214), genotype VT50660-Gal4; UAS-TrpA1.
- I downloaded the supplementary PDF (MOESM210, 23 pages), but I could not read it: there is no PDF renderer here and the text streams are compressed. It may hold the methods and the n for the MDN experiment, so a future session should re-check it.
- 1 record: Moonwalker (MDN) > TrpA1, freely walking, backward walking.
  - Fig. 2c also shows Moonwalker > CsChrimson with the same outcome. PROTOCOL 1 calls for one record per figure when outcomes agree, so CsChrimson is only mentioned in the notes field.
  - Sex and n were not visible.
  - Confidence is low because the article is paywalled.
- Uncertain: effect_on_walking is `not_assessed`. The vocabulary has no value for "direction reversed"; forward velocity goes negative.

## 10.1016/j.cub.2026.06.045 (Liessem et al. 2026, Current Biology)
- Crossref lists a CC BY licence, but cell.com, sciencedirect.com and linkinghub returned 403 or redirect stubs, and the Elsevier API returned 400 without a key. The article is not in PMC; PMID is 42442357.
- I read the abstract from PubMed. MDNs are characterised there by in vivo electrophysiology; optogenetic activation is described only for DopaMeander dopaminergic neurons, which are not DNs. The abstract also mentions "computational models", which are the paper's own models. That does not count as a sighting, and no per-type scores were shown.
- Disposition: unreachable. The full text probably contains MDN activation experiments and should be fetched by another route.

## 10.1073/pnas.2618114123 (Lee et al. 2026, PNAS)
- PMC13552653 exists, but the full text is embargoed until 2027-03-02: efetch returned front matter only and the PMC HTML returned 403. pnas.org HTML and PDF both returned 403.
- The abstract does not explicitly describe an activation experiment (it is about MDN cell-body clustering, Lar/Dlp/Hunchback, and Inx8/ShakB). Disposition: unreachable.
