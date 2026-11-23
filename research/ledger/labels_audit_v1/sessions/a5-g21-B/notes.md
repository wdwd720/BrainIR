# Notes: session a5-g21-B (label audit, run 5)

## Assigned types
DNb08, DNfl028, DNg100, DNg12, DNg16, DNg55, DNg62, DNg75, DNg97, DNp09, DNp71, MDN.

## Sources
1. **Özdil et al. 2026, Nat Commun (10.1038/s41467-026-72152-x).** Read text.txt, Supplementary Information (MOESM1), the peer-review file (MOESM20) and the key figure legends.
   - Flies were activated only via aJO-GAL4-1 (JO-F sensory neurons) and SS35281 (c23/asteroid brain interneuron).
   - aDN1 (= DNg62) appears only in the connectome network model and its simulated activation screen, where it is listed as a hit (Fig. 6E; Fig. 7A). That is a simulation result for DNg62, but it comes from this paper's own model, not from a Pugliese-type screen.
   - Peer-review file: activating aBN2/aDN1 unilaterally was "infeasible", and only c23 was tested experimentally.
   - Disposition: no_qualifying_experiment.
2. **Sapkal et al. 2026, bioRxiv v2 (10.64898/2026.04.29.721658).** Read the full text, all main and Extended Data figures relevant to activation, and Supplementary Tables 1 and 2. Supplementary Table 3 holds connectome data only.
   - Supplementary videos were not downloaded and are unavailable.
   - 39 records.

## Coding decisions
- **Fig. 1 conditions.** I wrote one record per condition (ball, slippery surface, air, amputated) for DNg100, DNg97 and MDN. Leg involvement differs between conditions for DNg97 and MDN, and each condition is a separate preparation with its own n. For DNg100 the outcome is the same in all four (all legs step); I still split them so that `headless_surface` stays consistent.
- **Amputated condition.** Coded as `headless_surface` = `air` (stumps air-stepping), with the amputation stated in `sensory_condition`.
- **DNg97 and MDN, "unclear" legs.** Several legs are coded `unclear` where Fig. 1e shows medians or spreads that are neither clearly stepping nor clearly zero. The authors' own criterion ("actively stepping" means more than 90% of flies) counts only front legs for DNg97 and only hind legs for MDN in the reduced-feedback conditions.
- **Co-activation genotypes (Fig. 4).** These carry two split-GAL4 drivers, so each counts as a line labelling two DN types: one record per type, `multi_dn`, for ball and for air.
  - DNg16, DNg55 and DNg75 alone produced no walking (Extended Data Fig. 7e), so the stepping in the co-activation records is attributable to DNg100; the notes say so.
  - The records for those three types alone are coded `no` with medium confidence, because only ball velocity was measured.
- **Line specificity.** DNg100, DNg97 and MDN are coded `clean` on the authors' description ("highly specific split-Gal4 reagents"). For DNg16 (0), DNg55 (1) and DNg75 (1), the ectopic VNC cell counts come from Extended Data Fig. 7d.
- **Mapping uncertainty.** The DNg16 line's mapping to SS86205 relies on the Bloomington number BDSC_88000.
- **Not coded separately:**
  - DNg97 alone in Extended Data Fig. 7e (the same genotype as in Fig. 1).
  - DNg100(h), homozygous (noted in record 0011).
  - BPN, which is not a DN.
  - Analyses in Figs 2-3 that reuse the Fig. 1 datasets.
- **No records for DNb08, DNg12, DNg62, DNp09, DNp71 or DNfl028.** In Sapkal these types appear only in connectome analyses (Extended Data Fig. 12) or the Discussion; DNg62 (aDN1) also appears in the Özdil simulations.

## Simulation sightings
- **DNg100 (`saw_simulation_score` = true on all 20 of its records).** The Sapkal Discussion cites the Pugliese et al. connectome model as "converting a constant DNg100 input into a phasic leg motor neurons output". This is in effect a model driver call for DNg100.
- **DNg62 (aDN1).** Özdil's own model activation screen calls aDN1 a hit for contralateral antennal motor neuron (aMN4) activity. This is not a Pugliese-type screen, and no DNg62 records were written.
- No rhythm scores or ranks were seen for any other assigned type.
