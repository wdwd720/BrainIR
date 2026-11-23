# Notes — session a5-g04c-B (audit, run 5)

Assigned types: DNp29, DNp31, DNp71 (hemibrain DNp09; "DNp09" is ambiguous DNp09/DNp71), DNxl022 (hemibrain DNa01; "DNa01" is ambiguous DNa01/DNxl022), MDN.

## Sources
- **10.7554/elife.34272 (Namiki 2018)**: read the full text and searched all supplementary CSVs. This is an anatomy / split-GAL4 resource. DNp29 (SS02618, SS01587), DNp31 (SS00733, SS02621), DNp09 (SS01540) and DNa01 (SS00731) appear only as anatomy and key-resources entries. CsChrimson was used only to visualize expression. The Discussion's MDN activation sentence cites Sen et al. 2017. No records.
- **10.7554/elife.71679 (Sterne 2021)**: SEZ split-GAL4 anatomy. No activation or behaviour experiments. No records.
- **10.1016/j.cub.2017.02.008 (Sen 2017)**: local copy is the abstract only. WebFetch to cell.com and sciencedirect returned HTTP 403, and Europe PMC has no PMCID or open full text. I wrote one low-confidence record from the abstract (unilateral MDN activation, which supports backward walking with turning). The abstract gives no effector, stimulus, line or preparation: `effector_kind` is set to null instead of guessed, which does not validate against the schema enum, and `preparation` = `other`. A session with full-text access should recode this source. In particular, check whether bilateral MDN activation was also tested, and whether headless or tethered preparations were used.
- **10.1016/j.cub.2019.01.079 (Ache 2019)**: no local text. Publisher pages returned 403 (cell.com, sciencedirect, linkinghub), and Europe PMC (PMID 30827912) has no PMCID. Only an abstract summary was seen (LPLC2/LC4 to giant fiber). Marked unreachable.

No simulation scores, ranks or driver calls were seen for any assigned type.
