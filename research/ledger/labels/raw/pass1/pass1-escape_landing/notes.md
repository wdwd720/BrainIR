# Notes: session pass1-escape_landing (pass1)

## Output
- `records.jsonl`: 23 records, p1-escape_landing-0001 to 0023, one JSON object per line.
- Sources with records: Ache et al. 2019 Nat Neurosci (4), von Reyn et al. 2014 (1, low confidence), Dombrovski et al. 2023 Nature (9), Lima & Miesenböck 2005 (1, abstract only), ALTOMS PNAS 2014 (1), Liessem et al. 2025 bioRxiv (7).
- `proposed_driver_lines.csv`: 12862-Gal4 -> DNp01.
- `proposed_synonyms.csv`: "giant fiber neurons" and "giant fiber system" -> DNp01.

## What I searched
- Seed leads: Ache 2019 (landing), von Reyn 2014, von Reyn 2017.
- Web searches on: GF/giant fiber CsChrimson/ChR2/P2X2/TrpA1 activation; takeoff/jump DNs (DNp02/04/06/11); landing DNs; reaching and leg extension; posture; headless jumping; Card-lab FlyPEZ papers; recent bioRxiv preprints on escape and landing.
- Full text came from Europe PMC REST (fullTextXML), pmc.ncbi.nlm.nih.gov, and bioRxiv HTML.

## Could not access, or unresolved
- **von Reyn et al. 2014 (Nat Neurosci):** paywalled. I fetched the Janelia-hosted PDF, but the tool could not decode it (no local PDF tools). Record 0005 rests on the phrase "produced only short-mode escapes", which an exact-phrase web search confirmed as text of that PDF (Fig. 2 legend). The n = 11, the CsChrimson genotype and the free-standing assay come from search-index excerpts only. The record is low confidence and should be verified by pass2.
- **von Reyn et al. 2017 (Neuron)** and **Williamson et al. 2018 (Cell Reports, FlyPEZ):** both paywalled and not in Europe PMC. Search snippets mention GF activation with split lines; no records written.
- **Dombrovski et al. 2023:** seven LC4-DNs were activated individually ("We optogenetically activated each DN"). The text names results only for GF, DNp04, DNp11 and DNp02, plus two combination lines. The remaining individually tested LC4-DNs (probably 3; names not stated in the text I read) and all line IDs are in Extended Data Fig. 1e and Supplementary Tables 1-2, which I could not read. The text implies their takeoff rates were not significantly above control, but posture was not stated, so I wrote no records for them. Pass2 should get Supplementary Table 1/2.
- **Ache et al. 2019:** "we optogenetically activated 133 ... split-GAL4 driver lines". Only DNp07 and DNp10 are reported; no per-line table was found, so I did not write records for the null lines. If a supplementary list exists, those lines would be "no landing-like extension" records. The figure-to-line assignment for the two DNp07 lines (SS02276 vs SS01549; the kit says SS01549 also labels DNp13) was not stated.
- **Liessem et al. 2025 (bioRxiv):** line IDs (Supplemental Table 1) and n were not read. I could not confirm that aSP22 was activated in this study (record 0022, low confidence): it is inferred from the "all but one DN in the putative landing ensemble" statement. Activation in walking flies (Video S9) was described only for wings (DNp10 raised the wings), so I wrote no walking record. I found no takeoff-ensemble activations in the text I read.
- **McKellar et al. 2019 (aSP22, courtship; reported foreleg lifting/extension):** the lab PDF failed with a certificate error, it is not open in Europe PMC, and the abstract contains no leg sentence, so no record. Worth a follow-up.
- **Peek 2018 PhD thesis (UChicago):** the 71 MB PDF was not parsed. It may list all LC4-DN lines tested.
- **Lima & Miesenböck 2005:** abstract only. The effector is P2X2 with photo-uncaged ATP, coded as optogenetic. News coverage mentions headless flies, but I wrote no headless record because I could not verify it.

## Exclusions (deliberate)
- **Cande et al. 2018** (DNp10 reaching, GF, DNb01 etc.) belongs to the atlas family, so I did not code it here.
- Namiki et al. 2022 (flight DN screen) and DNp03 2026 (flight saccades): activation in flight with no leg description, so no records.
- Tschida & Bhandawat 2015: activation by current injection or ATP/P2X2, not optogenetic/thermogenetic (protocol section 1).
- JoVE de Vries & Clandinin 2013 (Foma-1 neurons) and the nociception preprint (sensory/ascending neurons): no DN activation.
- 10.1101/2025.09.30.679458 (Ipsigoro DNs, rolling escape): larval, excluded.

## Simulation exposure (saw_simulation_score)
I did not open any model, simulation or prediction. I saw the following only in web-search result text, by accident:
1. **DNp01 (GF):** search summaries described von Reyn 2017's GF looming-integration model components (a ModelDB entry was listed), the von Reyn 2014 "dual-circuit model", and a result titled "A Computational Model of the Escape Response Latency in the Giant Fiber System" (not opened). A whole-brain spiking-model preprint snippet (bioRxiv 10.64898/2025.12.14.694122, not opened) described simulated DNp01 activity at takeoff. I set `saw_simulation_score` = true on all DNp01 records (0005, 0006, 0015, 0016).
2. **DNp04:** the same spiking-model snippet described simulated DNp04 ("postural module") activity at takeoff. I set it true on DNp04 records (0007, 0011, 0013).
3. **DNp02, DNp11:** a search result listed a GitHub pull request titled "Take-off direction from DNp02/DNp11 ..." in an apparent simulation repository (not opened; GitHub not visited). I set it true on DNp02/DNp11 records (0008, 0009, 0010, 0012) as a precaution.
None of these concerned rhythmic leg movement or walking. All recorded outcomes come from the experimental papers listed.

## Coding choices
- Landing leg extension, takeoff/jump and lean (posture) are single movements, so all leg-rhythm fields are "no".
- Combination lines in Dombrovski 2023 produce one record per labelled DN type, marked `multi_dn`.
- Driver-line IDs are left empty where the paper text I read did not give them. The kit's candidate lines (e.g. SS01544, SS02292) are mentioned in notes only, not asserted.
