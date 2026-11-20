# Notes — session pass2-pugliese_dedicated (pass2)

## Sources opened
- Pugliese et al., bioRxiv 10.1101/2025.09.12.675944 v1 full-text HTML (only the first ~100k of ~172k characters were read; Results, Fig. 2/4 legends, Methods, Supplementary Video legends were covered). Nature version not opened.
- Sapkal et al., bioRxiv 10.64898/2026.04.29.721658 v2 full-text HTML (all chunks). bioRxiv returned HTTP 429 many times before access succeeded. Also used the bioRxiv API (metadata only) and Europe PMC (metadata/abstract only).
- One web search for the Sapkal title. The results listed an arXiv paper ("How much of fly walking is written in the wiring?") that appears to be about simulations. I did **not** open it.
- I did not visit GitHub, Zenodo or any model/simulation resource.

## Simulation exposure
- In Pugliese et al. I saw a sentence saying that **simulated oscillations** "roughly matched the stepping frequency of real walking flies (~7–15 Hz)". The context was DNg100 walking. I saw no numeric per-type score. To be safe, I set `saw_simulation_score` = true on **every DNg100 record** (Pugliese and Sapkal). I saw no simulation score for DNb08, DNg97, MDN, DNg16, DNg55 or DNg75, so those records are false.
- In Sapkal et al. I asked the fetch tool only for experimental content. The abstract mentions a "connectome search"; I saw no scores.

## Uncertainties
- All 36 rows were found; `not_found.csv` contains only the header. All rows have n_siblings = 1, so no sibling assignment was needed.
- Reading was done through a summarising fetch tool that returned short verbatim excerpts. All quotes are excerpts the tool gave as verbatim, but the punctuation (curly vs straight quotes/apostrophes) may differ slightly from the source.
- **Pugliese DNb08 (0002):** the surface is coded `air` because the text says DNb08 evoked movements more reliably with the treadmill removed and the legs were not in contact with the substrate. Sex (female) comes from the general Methods. Hind legs were not measured.
- **Pugliese DNg100 (0001):** the split line ID was not given in the text I read, so `driver_lines` is [].
- **Sapkal reduced-feedback conditions (DNg97 0008–0010, MDN 0012–0014):** the text describes slippery, air and amputated conditions together. Per-condition, per-leg values are only in Fig. 1e, which I could not read numerically. DNg97: front yes, mid unclear ("to a smaller extent"), hind no. MDN: hind yes, front/mid unclear.
- **Sapkal driver lines:** only the DNg100 split (VT058557-p65ADZp; R85F12-ZpGDBD) is named in the Methods text I read. The others are in Supplementary Tables 1–2, which I did not read. For co-activation records `driver_lines` lists only the DNg100 split.
- **DNg16:** the kit's common DNg16 line SS01543 is re-annotated as DNg69 in one table. Sapkal's DNg16 driver was not identified, so I kept DNg16 with high confidence based on the paper's name. An adjudicator may want to check this.
- **Ext. Data Fig. 7e (0021–0024):** the surface is not stated in the legend. I inferred ball from the forward-velocity measure. "Did not induce any walking" is coded `no_visible_effect` / legs `no` at medium confidence; other leg movements were not described.
- **Air co-activation (0033–0036):** I took "~22 Hz front legs" from the tool's summary of the Results, not from a verbatim quote.
- **Amputated condition (0006):** legs were amputated at mid-femur. I did not verify how stepping was tracked.
- **effect_on_walking:** for headless flies that start walking on the ball I used `speeds`, matching record 0001. For air/slippery conditions I used `not_assessed`. MDN backward walking is `not_assessed` because there is no fitting value.
- No proposed synonyms or driver lines.
