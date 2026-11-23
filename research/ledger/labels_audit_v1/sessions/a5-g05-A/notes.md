# Session a5-g05-A notes (label audit, run 5)

## Sources
- **10.1101/2025.09.12.675944** (Pugliese et al., bioRxiv v2): read text.txt, the genotype table in supp/article.txt (page 29), and Figs. 2, 5 and ED3. There are two experiments on real flies, both with CsChrimson in decapitated females:
  - DNg100 (VT058557-AD x R85F12-DBD) on a ball: forward walking whose speed and step frequency rise with laser intensity.
  - DNb08 (SS70620): rhythmic front and middle leg movements, more reliable with the treadmill removed.
  The DNb08 data give two records: unloaded/air, and on-ball (all leg pairs unclear). It is uncertain which surface the Fig. 5e data come from; the schematic shows no ball.
  The other assigned types (DNg97/oDN1, DNg74/web, DNg12, DNg62/aDN1) appear only in the Discussion and Supplementary Tables 9 and 10 (connectivity and simulation scores), not in experiments.
  I saw simulation rhythmicity scores (Fig. 1e, Fig. 2, Fig. 5a-b, Supp. Tables 1/10 headers), so saw_simulation_score = true on all records. Allowed under AUDIT_NOTE; I did not use them as evidence.
- **10.7554/elife.58942** (Schretter et al. 2020): DNa02, DNa03 and the giant fiber appear only in connectome analysis. No DN activation, so no_qualifying_experiment.
- **10.1016/j.cub.2020.07.083** (Wang et al. 2020, DNp13): the fetch was allowed but failed. doi.org redirects to linkinghub, which gave only a "Redirecting" stub. cell.com and sciencedirect returned 403. Europe PMC REST says subscription only, not in PMC. Marked unreachable. The abstract alone says DNp13 are "command-type neurons for ovipositor extrusion" but gives no activation method or leg outcome, so I wrote no record.
- **10.1016/j.neuron.2017.05.036** (von Reyn et al. 2017, GF): the fetch was allowed but failed. cell.com returned 403, the PMC idconv lookup found nothing, and Europe PMC REST says subscription only (the first attempt timed out, the second returned 503 before succeeding). Marked unreachable. The abstract has no activation experiment with a leg outcome.

## Uncertainties
- For DNg100, frequency_hz (5.5) is read by eye from the Fig. 2j medians.
- Expression and line specificity are not stated for either line, so I coded them as unknown.
