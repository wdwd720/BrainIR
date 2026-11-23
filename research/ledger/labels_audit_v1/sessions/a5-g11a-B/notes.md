# Session a5-g11a-B notes (label audit, run 5)

Sources read: the two assigned sources only, both full text. No web access was used.

## 10.1038/s41586-024-07523-9 (Braun et al., Nature 2024)
- Read: text.txt, all figures (Fig. 2, 4, 5 and Extended Data Figs 1, 5, 6, 10 inspected for the leg data), Supplementary Information (Supp. Table 2 gives the driver lines), and the peer-review file (searched).
- Supplementary Videos 1-6 were not downloaded, so behaviour described only in the videos is not coded (e.g. headless flies hanging without ground contact).
- Assigned types with records: DNp09, DNfl023 (aDN2), DNg62 (aDN1), DNa01, DNa02, DNg14, DNg74 (Web), DNg30, DNg16.
- BDN2 (DNg100), oDN1 (DNg97) and the giant fibre (DNp01) appear only in connectome analyses or literature citations; giant-fibre experiments were explicitly not repeated. No records for them.
- Uncertain coding:
  - Fig. 2 trials were restricted to flies already walking. DNp09 there is coded as a speed increase with legs not_assessed. aDN2 there is coded as grooming plus stopping.
  - Web, DNg30 and DNg16 were tested but excluded because they had neither a known intact behaviour nor a clear headless phenotype. They are coded as headless no_visible_effect with low confidence; no data are shown.
  - DNg16 has an extra intact record from the peer-review rebuttal ("only observed reliable retreat behaviors in DNp42"), low confidence.
  - For DNa01 and DNa02 (intact and headless), the legs were not tracked and the pre-stimulus state is not stated, so the leg fields are unclear.
- Mapping: the names DNp09 and DNa01 are listed as ambiguous in synonyms.csv (DNp71 and DNxl022 carry them as hemibrain names), so mapping_confidence is medium for those.
- No Pugliese-type rhythm score, rank or driver call was seen. The paper's own connectivity counts are not simulation scores. saw_simulation_score is false throughout.

## 10.1101/2023.10.15.562426 (Yang et al., bioRxiv 2023)
- Calcium imaging of 16 DN types (DNa01, DNa02, DNb05, DNb06, DNg13, DNg14, DNg15, DNg16, DNp05, DNp09, ...) and patch-clamp recordings are not activation experiments, so they get no records.
- DNg13 was perturbed by current injection (depolarisation lengthened contralateral strides and turned the fly toward the stimulated side). This is not optogenetic or thermogenetic activation and has no effector_kind in the schema, so it gets no record. An adjudicator may wish to reconsider this if "or otherwise" in the task is meant to include electrical stimulation.
- DNg13 SPARC-CsChrimson: light stopped locomotion whenever an off-target ascending neuron expressed CsChrimson, regardless of DNg13 expression. This is recorded with low confidence and flagged in the notes.
- DNa02 SPARC records come from flies already walking (forward velocity of at least 1 mm/s required), so leg rhythm is not_assessed; effect_on_walking is turns for unilateral and slows for bilateral activation.
- No simulation scores were seen.
