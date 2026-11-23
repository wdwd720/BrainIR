# Session a5-g14-A notes (audit, run 5)

Assigned types: DNb08, DNfl023 (aDN2), DNg100 (BDN2), DNg62 (aDN1), DNp01 (GF).

## Sources
- **10.1038/s41586-026-11195-y (Pugliese et al. 2026)**: the cached text was abstract-only. Following the task's permission, I fetched it from nature.com. That gave only the subscription preview (abstract, figure titles, some legends, supplementary video legends); Europe PMC lists no full text (subscription). Two records:
  - DNg100: headless flies. Source is the Supplementary Video 1 legend ("Optogenetic activation of DNg100 neurons drives walking in headless flies.") and the Extended Data Fig. 10 legend. This quote is from the web page as returned by the fetch tool, not from text.txt.
  - DNb08: headless flies. Source is the abstract sentence in text.txt, plus the Fig. 5 title and Supplementary Video 2 legend ("oscillatory leg movements in headless flies"). The abstract says "behaving flies"; the figure title and video legend say headless.
  - Not accessible: driver lines, effector, light parameters, headless surface, n, frequency, which legs move for DNb08. Leg fields for DNb08 are coded `unclear`; confidence is low.
  - Simulation scores seen: the abstract calls DNg100 the strongest simulated driver of rhythmic leg activity, and simulations predicted that DNb08 drives rhythm. `saw_simulation_score` = true on those two records. Neither was used as evidence.
- **10.7554/elife.08758 (Hampel et al. 2015)**: full text, figures and Supplementary file 1 read. Records for aDN1→DNg62 and aDN2→DNfl023:
  - split lines with dTrpA1 (Fig. 2)
  - R18C11 aDN-GAL4 and aDN-LexA with dTrpA1 (multi_dn: aDN1, aDN2, aDN3)
  - CsChrimson (Fig. 7 / Fig. 7–S1)
  - Not recorded: broad GAL4 lines R71D01, R76F12, R70H02, R34C03 and R11B11 (Fig. 2–S1A). The paper does not state that these GAL4 patterns contain the aDNs (only their enhancers were used in splits).
  - Not recorded: the GCaMP imaging in isolated CNS, which is not a behavioural experiment.
- **10.7554/elife.87602**: aDNs mentioned only in the Discussion; no qualifying experiment.

No source tested DNp01 (GF). BDN2 is not mentioned in any source; DNg100 is.

## Uncertainties
- **Antennal grooming leg coding.** Front legs are coded `yes` because the paper says antennal grooming consists of front-leg movements. Middle and hind legs are `unclear` because they are not described.
- **aDN2 mapping conflict.** synonyms.csv maps aDN2 to DNfl023. driver_lines.csv also lists the aDN2 split lines as UNMAPPED (DNg127 per the Zung/Namiki table). I used DNfl023 with `mapping_confidence` medium.
- **Off-target cells.** Off-target cells for the aDN2 split lines were read approximately from the Fig. 2I grid.
- **DNg100 walking direction.** Direction is not stated in the accessible text, so `behaviour_category` = `other`.
