# Session a5-g20-A notes (audit, run 5)

Assigned types: DNg100 (BDN2), DNp01 (GF / Giant Fiber), MDN (DNp50). There were three assigned sources, all with full text.

## Feng et al. 2020 (10.1038/s41467-020-19936-x)
- I read the main text, Supplementary Information (figure legends, Supplementary Tables 1-2 genotypes) and the source-data CSVs for Fig. 1j, Supp. Fig. 5c and Fig. 7e-g. I also viewed the Supp. Fig. 5 page image.
- 4 MDN records:
  - Fig. 1 + Supp. Fig. 5b,c: intact tethered, MDN-1-GAL4.
  - Supp. Fig. 5a,c: decapitated, MDN-1-GAL4.
  - Fig. 4b: Fly Bowl, MDN split-LexA, Empty-SS negative control.
  - Fig. 7: decapitated, MDN split-LexA, control trials.
- The Fig. 1i,j tarsal-amputation data are on the same line and preparation as Fig. 1, so I folded them into record 0001 rather than writing a separate record.
- The MDN split-LexA (VT049484-LexADBD; VT050660-AD) is described as labelling MDNs and MANs. I coded it `minor_offtarget` because MAN is an ascending neuron, not a DN.
- Uncertain: Fig. 7 tracked only the hindlegs. I coded all legs `yes` under the walking convention, with medium confidence.
- Videos were not downloaded. That doesn't affect the records.

## Jones et al. 2025 (10.1101/2025.10.28.684868)
- DNp01/GF and DNg100 appear only in connectome diagrams (Ext. Data Fig. S6). No DN activation experiments, so disposition `no_qualifying_experiment`.
- The genotype table is image-only. Nothing in the text suggests a DN line was used.

## Dallmann et al. 2026 (10.64898/2026.01.04.697356)
- One MDN record from the gap-crossing assay. The driver is VT044845-DBD; VT050660-AD (= MDN-1).
- DNp50/MDN also appears in the paper's own connectome net-excitation ranking (Supp. Fig. 2b). I did not view that panel. It is not a Pugliese-type activation simulation, so `saw_simulation_score` is false.

No simulation scores, ranks or driver calls were seen for any assigned type. There are no proposed synonyms or driver lines.
