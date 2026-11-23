# Session a5-g18-B (label audit, run 5)

Assigned types: DNa01, DNa02, DNg62 (aDN1), DNxl022, MDN (DNp50). Assigned sources: 2. Both were read in full from local files; no web access was used.

## 10.1016/j.cub.2022.01.035 (Israel et al. 2022, Curr Biol)
- I read text.txt, Fig. 2-4 and 7 images, and the supplementary text mmc1 (Fig. S2A legend). The videos were not downloaded; I used their legends only.
- MDN activation experiments recorded (7):
  - ChR2-XXM, intact, Fig. 2/S2A: VT50660-GAL4 and MDN3-GAL4.
  - ChR2-XXM, headless, Fig. 4B: the same two lines.
  - VT50660>CsChrimson positive control in Fig. 3B (figure-only result).
  - VT50660>CsChrimson with 30-s stimulation, Fig. 7H.
  - MDN+MAN-LexA>CsChrimson, Fig. 3E (MANs co-labelled, so minor_offtarget).
- Not recorded:
  - Fig. 3D: MDN+MAN activation while MDNs are silenced with TNT.
  - GH146II, NP225 and NP5288 lines and MooSEZ activation: these are not assigned types. The paper also shows that MDNs are not labelled by these lines.
  - TNT silencing and calcium imaging experiments.
- DNa01 and DNa02 appear only in the hemibrain connectivity analysis (Fig. 7K). They were not activated, so they have no records. The name "DNa01" (hemibrain) is ambiguous in the kit (DNa01 or DNxl022), but this did not matter.
- Uncertainties:
  - `effect_on_walking`: the vocabulary has no term for a forward-to-backward reversal. I used `slows` for intact flies and explained this in each record's notes.
  - Headless flies walked on the open-arena floor, so `headless_surface` = `other`.
  - Line specificity is `unknown` for VT50660-GAL4 ("broad") and MDN3-GAL4 ("narrow"), because the paper names no other labelled cells.

## 10.1101/2024.12.17.628844 (Özdil et al. 2024, bioRxiv)
- The only real-fly activation is aJO-GAL4-1 (GMR60E02-GAL4) > CsChrimson, which targets JO-F sensory neurons (Table 1 in supp/article.txt).
- aDN1 (= DNg62) appears only in the connectome-derived network. It is also a hit in this paper's own simulated activation screen (Fig. 6E, 6H), which models antennal motor neuron output, not legs. I saw that simulation result. It is not a Pugliese-type score, and no record was written for DNg62.
- Disposition: no_qualifying_experiment.

## Simulation sightings
- No Pugliese-type or BrainIR rhythm score, rank or driver call was seen for any assigned type.
