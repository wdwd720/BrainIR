# Session a5-g06-B (audit, run 5)

Assigned types: DNa15, DNg02, DNg03, DNg16, DNg55, DNg69, DNp01, DNp02, DNp07, DNp10, DNp13, DNp17, DNp42.
I read only the four assigned sources in this room. I did no web access and no searching beyond them.

## Per source
- **10.1038/s41593-019-0413-4 (Ache et al. 2019)**: 7 records.
  - DNp07 (SS01549 Fig. 1e; SS02276 Fig. 2j-k and non-flying activation).
  - DNp10 (SS01608: Fig. 1e, Fig. 2j-k, non-flying activation).
  - DNp13 (one multi_dn record: SS01549 has weaker off-target expression in DNp13, Supp. Fig. 1b).
  - The phenotype is always a single landing-like extension of all six legs, so the leg-rhythm fields are `no`.
  - The paper also mentions activating 133 DN split lines during flight, but it does not list the per-line results. I therefore did not code it as a systematic screen.
  - Which DNp07 line was used for the non-flying and Fig. 2 experiments is inferred from the Methods: "DNp07-split-GAL4-1 was used for all other experiments".
  - The Methods give the SS01608 DBD hemidriver as 48E11, while driver_lines.csv gives R94E01 for the AD. I kept the line ID as printed.
- **10.1016/j.cub.2023.12.047 (Ros et al. 2024)**: no record.
  - DNae014 = DNa15 (driver_lines.csv: DNae014-splitGal4 -> DNa15; the paper says DNae014 = hemibrain PS017_R).
  - DNae014 was activated (2-photon focal CsChrimson, SPARC CsChrimson) only during tethered flight, with wing readouts. No leg behaviour is reported.
- **10.1016/j.isci.2026.115624 (axo-axonic synapses, iScience 2026)**: no record.
  - GF (DNp01) was activated by CsChrimson in intact and headless flies, but the flies were mounted in dental wax and the only readout was intracellular TTM/DLM muscle potentials. No leg movement was observed, so this fails "leg movement observable".
  - The Axc (AN08B098) activation targets an ascending neuron, not a DN.
  - The paper contains its own LIF VNC simulations of GF excitability. These are not a Pugliese-type rhythm score or driver call.
- **10.7554/elife.107450 (Zung et al. 2025 catalogue)**: no record. It is an anatomical driver-line catalogue with no activation experiments.

## Simulation scores
I saw no Pugliese-type rhythm score, rank or driver call for any assigned type. `saw_simulation_score` = false on all records.

## Uncertain
- DNp13 record: the authors attribute the effect to DNp07, and DNp13 does not innervate the leg neuropils. I set `labeler_confidence` = low.
- Borderline exclusion: the iScience GF muscle recordings (TTM is a leg/jump muscle) could be argued to count as a leg readout. I excluded them because no leg movement was observed.
