# Session a5-g08-A notes (audit, run 5)

Assigned types: DNp01, DNp09, DNp13, DNp71, MDN. Three assigned sources, all read in full (main text; supplements where present).

## 10.1016/j.neuron.2020.07.032 (Bidaye et al. 2020)
- 8 records, all for P9 = DNp09. Text is the PMC author manuscript. Figure images, supplementary figures (S1-S7), Table S1 (genotypes per figure) and videos are **not** in the room, so every record rests on main-text sentences and legends.
- Mapping: the paper writes "DNp09 (henceforth referred to as P9) (Namiki et al., 2018)". The kit marks the name DNp09 and the lines SS01540/P9S2 as AMBIGUOUS (DNp09;DNp71), because the hemibrain type "DNp09" maps to MANC DNp71. The paper uses Namiki 2018 nomenclature and a Namiki split line, so I chose DNp09 with `mapping_confidence` = medium. One caveat: the paper identifies P9 in the hemibrain as body 1228264951. If that body carries the hemibrain type DNp09 (= MANC DNp71), the mapping should be reconsidered. I could not check this from the room.
- Judgement calls:
  - All of Fig. 1 (continuous-light screen, grooming retest, copulation retest) is coded as one experiment, because the outcome is the same.
  - The bilateral mosaic (Fig. 2C) and unilateral (Fig. 2D-E) experiments are split into two records, because the turning outcome differs.
  - Fig. S2F covers four driver/reporter genotypes. One of them showed freezing after the walking began. They are coded as one record with `halting` as a secondary behaviour, because Table S1 is missing and the genotypes cannot be told apart.
  - The male experiment (S2H-I) and the P9+BPN co-activation (S5L) do not name their driver lines in the text, so `driver_lines` = [].
- MDN-1>CsChrimson was used only as a positive control to adjust light intensity. No leg outcome is reported for it, so there is no record.
- The screen covered 156 lines, including the Namiki DN split collection, but the text names only SS01540 and SS01587, so no records could be written for other assigned types (DNp01, DNp13, DNp71) that may have been tested. The Discussion says P9 were "the only DNs to initiate walking". That statement is not line-specific and was not used.

## 10.1038/s41467-024-53610-w (Li et al. 2024)
- dsx-GAL4 ∩ Otd-Flp activation labels DNp13 (pMN1) and vpoDN (plus other dsx brain neurons in intact flies). Intact and decapitated females of D. melanogaster, D. yakuba and D. santomea were tested.
- The only outcomes reported are abdomen extension and wing angle/spreading. No leg behaviour is described, SLEAP tracked no leg points, and the words leg/walk do not appear. The Methods do mention "leaning and flipping over" in D. santomea, which is too vague to code as a leg outcome. The task asks for experiments that report what the legs do, so I wrote no record (disposition `no_qualifying_experiment`).

## 10.1038/s42003-025-09344-6 (Israel & Parnas 2025)
- This paper activates MooSEZ (an SEZ/central-brain neuron upstream of MDN) and broad PN/AMB lines. MDN is only silenced (VT44845-LexA>LexAop-TNT, Supp. Fig. 3F-H). The split line VT032768∩R60F09 also labels "a bilateral pair of SEZ descending neurons", which are not identified as any assigned type. No record.

## Simulation scores
- I saw no connectome-simulation scores, ranks or driver calls in any source. `saw_simulation_score` = false on every record.
