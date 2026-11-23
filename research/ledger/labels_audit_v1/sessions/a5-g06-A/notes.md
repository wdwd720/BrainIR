# Session a5-g06-A notes (label audit, run 5)

Assigned types: DNa15, DNg02, DNg03, DNg16, DNg55, DNg69, DNp01, DNp02, DNp07, DNp10, DNp13, DNp17, DNp42.
I read all four assigned sources from local files only. No web access.

## Ros et al. 2024 (10.1016/j.cub.2023.12.047)
- DNae014 is DNa15 (driver_lines.csv: DNae014-splitGal4 VT025718-x-R56G08 = DNa15). It was activated unilaterally (focal 2-photon CsChrimson, and SPARC CsChrimson with 617 nm pulses) only in rigidly tethered flying flies. The readout was wingstroke amplitude (saccades). Legs are never described, so no record. Figures are not present locally, but the legends in text.txt describe only wing measures.

## Ceballos et al. 2026 iScience (10.1016/j.isci.2026.115624)
- Optogenetic activation of GF (DNp01) in intact and headless flies, and of AN08B098 (Axc, ascending), was read out only by TTM/DLM muscle potentials in wax-mounted flies. No leg movement was observed, so no record.
- The paper has its own LIF connectome simulations (GF excitability). This is the paper's own model, not a Pugliese-type rhythm score. No records for DNp01, so saw_simulation_score does not apply.

## Ache et al. 2019 (10.1038/s41593-019-0413-4)
- 7 records: DNp07 (SS01549 flight; SS02276 non-flight; SS02276 Fig. 2j-k), DNp10 (SS01608 x3), and DNp13 (SS01549 off-target, Supp. Fig. 1b).
- All outcomes are landing-like extensions of all six legs, a single movement, so every leg-rhythm field is `no`, with `effect_on_walking` = `not_assessed`.
- The DNp13 record is weak evidence. DNp13 has only weak expression in SS01549, does not innervate leg neuropils, and SS02276 (no DNp13) gives the same phenotype. I gave it labeler_confidence medium.
- The paper says it screened 133 DN split-GAL4 lines during tethered flight, but it names only the two positive types. The supplement text does not list the other lines, so no screen records could be written for the others.
- Discrepancy: the Methods give SS01608 as VT031084-p65ADZp; 48E11-ZpGDBD, while the kit's driver_lines.csv gives AD_DBD R94E01-x-VT031084. I did not resolve it.

## Zung et al. 2025 eLife (10.7554/elife.107450)
- Anatomy and line catalogue only. Activation is mentioned only in the Discussion, citing other papers. No records.

## Simulation sightings
- None of the Pugliese-type activation screen. No sightings.csv rows.
