# Session a5-g05-B notes (audit, run 5)

- 10.1016/j.cub.2020.07.083 (Wang et al. 2020, DNp13): the local copy is the abstract only. I tried fetching it, as permitted: cell.com fulltext gave 403, sciencedirect gave 403, the linkinghub redirect returned only a "Redirecting" page, and Europe PMC REST says subscription only with no PMCID. Disposition: unreachable. The abstract calls DNp13 command-type neurons for ovipositor extrusion but describes no leg result, so I wrote no abstract-only record.
- 10.1016/j.neuron.2017.05.036 (von Reyn et al. 2017, GF/DNp01): the local copy is the abstract only. cell.com gave 403, and Europe PMC says subscription only with no PMCID. Disposition: unreachable.
- 10.7554/elife.58942 (Schretter et al. 2020): read in full. DNa02, DNa03 and the giant fiber appear only in hemibrain connectivity (Fig. 10, 11). The paper has no DN activation experiment.
- 10.1101/2025.09.12.675944 (Pugliese et al.): read in full, including the simulation results, as AUDIT_NOTE allows. There are two fly experiments, both headless, female, CsChrimson:
  - DNg100 (VT058557-AD x R85F12-DBD): forward walking on the ball, faster with higher intensity, tetrapod-like coordination.
  - DNb08 (SS70620): rhythmic femur-tibia movement of the front and middle legs, quantified for the left legs only. Hind legs were not reported. The movements looked like searching and were more reliable with the treadmill removed. I coded the surface as air, but this is uncertain because the paper says the treadmill was removed for some trials and does not say which.
  - I saw simulation scores and rank calls for DNg100 and DNb08, so `saw_simulation_score` = true on both records. Supplementary Table 10 (scores for DNg97, DNg62 and others) exists only as a page image. I did not open it, and those types have no experiment records.
- Line specificity is coded `unknown` on both records because the paper does not state it.
