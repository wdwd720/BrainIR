# pass2-grooming notes (pass2, phase 1)

## What I did
- Read PROTOCOL.md, schema, and kit files (type_list, synonyms, driver_lines). There is no `sources_seed.csv` in this room. As instructed, I did not look for other input files.
- Opened each source myself through the Europe PMC REST API (full-text XML), plus Crossref, PubMed and web search for access checks.
- I wrote 19 records (`out/records.jsonl`) and 20 not-found rows (`out/not_found.csv`).

## Could not access
- **Guo, Zhang & Simpson 2022, Curr Biol, 10.1016/j.cub.2021.12.055** (exp rows p1-grooming-0014 to 0033). The paper is subscription-only (Europe PMC availability code S, no PMCID). cell.com and sciencedirect.com returned HTTP 403. No bioRxiv preprint or eScholarship copy turned up (Crossref has no preprint relation). The PubMed page did not render. The abstract (from Europe PMC) names no DN type, line or figure. So I could not find any of these experiments or a supporting quote, and I wrote no records for them. If someone can get the full text, these 20 rows need labelling.

## Uncertainties
- **Antennal grooming coding:** following the convention, front legs = `yes` and middle/hind = `unclear` (neither paper says the other legs stood still). Neither source counts cycles, so ">= 3 cycles" is inferred from the behaviour being described as grooming or rubbing.
- **Hampel 2015, aDN1-spGAL4-1 (dTrpA1):** the effect is weak (4.8% of time grooming). The text still says aDN1 and aDN2 are each "sufficient to induce antennal grooming".
- **Hampel 2015, aDN2-spGAL4-3/-4 and aBN1/aDN1-spGAL4:** the quote comes from the antenna-amputation test sentence ("...show increased grooming"). I did not retrieve the Fig. 2 legend line by line.
- **aBN1/aDN1-spGAL4:** co-labels aBN1, a brain interneuron that is itself a grooming command neuron. I coded it `minor_offtarget` because aBN1 is not a DN, but the grooming cannot be attributed to aDN1.
- **Split-line specificity (Hampel and Braun lines):** set to `unknown`. Hampel's wording implies the aDN1 and aDN2 split combinations are exclusive, but I did not see an explicit statement.
- **R18C11-GAL4 rows (0006–0008):** the supporting legend says "three GAL4 lines". That R18C11 is one of them comes from the same legend's expression-pattern sentence and from the Results statement that the line came from the grooming screen.
- **aDN-LexA sibling group (0009–0011):** the paper says aDN-LexA "targets three aDN neurons". I assumed these are aDN1, aDN2 and aDN3, based on the shared R18C11 enhancer and co-expression with the aDN1/aDN2 split lines (Fig. 4-fig supp 2E,F). Alphabetical MANC order: DNfl023 (aDN2) = sibling 1, DNg62 (aDN1) = sibling 2, UNMAPPED (aDN3) = sibling 3. aDN3 has no kit mapping.
- **aDN2 mapping:** one driver_lines.csv row (another source) lists the aDN2 split lines with previous name DNg127/UNMAPPED. I used the synonym aDN2 -> DNfl023 (unique in synonyms.csv).
- **Braun 2024 headless surface:** recorded as `ball`, from the Video 4 legend ("headless on the spherical treadmill"). The paper also tested headless flies hanging without ground contact. I could not confirm which condition Extended Data Fig. 5b/6b show.
- **Braun 2024 aDN2 headless (0035):** antennal grooming was lost, but the "front leg approach" remained. I coded that as a single reaching movement (front = `no`, category `other`). The verbatim sentence about the lost grooming is slightly longer than 25 words, so it is in `notes` and the quote is from the Fig. 4g legend.
- **Braun 2024 aDN1:** the power for aDN1 was not found in the text I read. n_flies = 3 comes from the supplementary video legends, not the figures.
- The WebFetch tool returned short verbatim excerpts rather than raw text. Quotes were requested character-for-character, but small punctuation differences (e.g. en-dashes, the μ sign) are possible.

## Simulation / model exposure
- None seen. One web-search results list showed the title of a connectome-simulation paper (ResearchGate). I did not open it and saw no scores. `saw_simulation_score` = false on all records.
