# Session a5-g12-A notes (audit, run 5)

## Sources read
- 10.1038/s41586-024-07854-7 (Sapkal et al. 2024, Nature). I read the full text.txt, all main and ED figure images relevant to DN activation (Figs 2, 3, 4, ED Fig 6), Supplementary Table 1 (genotypes/n), Table 2 (reagents) and Table 3 (FlyWire / FANC-MANC IDs), and the reporting summary. The videos were not downloaded.
- 10.1101/2024.06.27.601106 (Feng et al. 2024, bioRxiv v2). I read the full text.txt, Figs 2 and 6, Figs S3 and S14, and the Supplementary Information (video legends, Supplementary Table 1 genotypes, part of Table 2). The videos were not downloaded.

## Assigned types with records
- DNp09 (P9), MDN, DNg97 (oDN1), DNg100 (BDN2): Sapkal 2024.
- DNa11, DNa03, DNa02, DNxl022 (via the paper's "DNae003"): Feng 2024.
- No activation experiments were found for DNa15, DNfl028, DNg12, DNg13, DNg75 (cDN1), DNp71 or DNxl022 under other names. DNg12, DNg13, cDN1 and DNa15/DNae014 are mentioned only in connectome or simulation context, or as cited work.

## Decisions / uncertainties
- **Coactivations not recorded.** Sapkal 2024 coactivates walk neurons (P9, MDN) with halt neurons (BB, FG, BRK) in Fig 2 and ED Fig 4, and coactivates MDN+BRK and BDN2+BRK in headless flies in Fig 4e-j. I recorded only the single-walk-neuron conditions. In the coactivations the leg outcome is driven by the co-activated halt neuron. BRK is an ascending neuron, and FG/BB have no MANC type in the paper's table.
- **P9 intact (0001).** Free-walking flies, centroid tracking only. I coded the legs yes under the forward-walking convention at medium confidence. A stricter reading of the "already walking" rule would give not_assessed.
- **P9 headless (0009).** The paper says the phenotype is absent and the velocity trace is near zero, but the legs are not described, so they are coded unclear at low confidence.
- **Sapkal MANC types conflict with the kit.** The paper's Supplementary Table 3 gives MANC types DNxl058 for BDN2 and DNxl054 for oDN1. The kit maps BDN2 to DNg100 and oDN1 to DNg97, and I followed the kit.
- **Sex for headless kinematics (Sapkal Fig 4e-j).** Coded male because the reporting summary says males were used for the high-resolution leg kinematics. ED6e sex is unknown.
- **Feng 2024 "DNae003".** The Methods say this is the earlier FlyWire name for what is now FlyWire DNae001. The kit maps DNae001 to DNxl022 but maps the string DNae003 to DNxn123, so I mapped it to DNxl022 at medium confidence and proposed a synonym.
- **Feng 2024 Fig 2c records (DNa02, DNa03, DNae003, DNa11).** Only ball angular velocity is reported, so I applied the turning convention and set the legs to not_assessed. For DNa11, Fig 6 gives leg kinematics for the same line and preparation (all six legs step at ~3 Hz, and stepping is initiated), so it has its own record with yes for all legs. The amputation and decapitated DNa11 experiments are also separate records.
- **DNa03 tethered flight (Feng Fig 2d).** Not recorded: the legs cannot reach the ball and are not reported.
- **Out of scope.** DNa06 activation (Feng Fig S14e-h) is not an assigned type, and LAL013/ExR7 are not DNs.

## Simulation sightings
- Sapkal 2024 uses its own connectome LIF model (Shiu et al.). I saw simulated firing rates for P9 (stimulated in silico), oDN1, BDN2, DNa02, DNa11, DNg13, cDN1 and others (Fig 3a-h, Fig 5c-d, ED Fig 6b-c, ED Fig 10). None of these is a Pugliese-type rhythm score, rank or driver call. Still, to answer truthfully, I set saw_simulation_score = true on records for DNp09, DNg97, DNg100, DNa11 and DNa02. MDN, DNa03 and DNxl022 are false: I saw no simulated values for them.
- No simulation results were used as evidence.
