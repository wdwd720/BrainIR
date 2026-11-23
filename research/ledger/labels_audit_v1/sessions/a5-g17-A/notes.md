# Session a5-g17-A notes (label audit, run 5)

Assigned types: DNfl023 (aDN2, DNge078), DNp01 (GF), DNp06 (AMMC-Di5), DNp103 (PVLP119), DNp13 (DN1, pMN1).
I searched both sources' text.txt (and supp/article.txt) for all names and synonyms, plus the driver-line IDs listed for these types in driver_lines.csv.

## 10.1523/jneurosci.0142-24.2024 (Tao et al. 2024)
- DNp06 and DNp103 (PVLP119) appear only in Table 3 (FlyWire neuron IDs) as DNs downstream of CL062 (connectomics, Figs. 13-14).
- DNp13 appears only as "pMN1/DNp13", citing Baker et al. 2022 as a weakly connected partner of CL062.
- The optogenetic experiments use L320, CL062-split, L188 and L2193. L320 labels one DN pair that the authors could not match in the hemibrain ("We were unable to identify the DN in the hemibrain"). DMD activation of that DN in head-fixed flies measured only wingspan. So there is no mapping to an assigned type and no leg readout.
- Disposition: no_qualifying_experiment.

## 10.7554/elife.108044 (Calle-Schuler et al. 2026)
- aDN2 (DNfl023) is mentioned only in connectivity: JO-F neurons and BMNs connect to aDN2 (Fig. 14F, Discussion). The aDN activation work is cited from earlier papers and not reported here.
- Fig. 13A lists earlier published lines that elicit grooming (R40F04-GAL4, R26B12-GAL4, aBN2-spGAL4-1/-2). These label aBN2/LB23 interneurons, not aDN2, and they are citations, not new experiments.
- The other assigned types are not mentioned.
- Disposition: no_qualifying_experiment.

## Simulation scores
Neither source contained a Pugliese-type connectome-simulation rhythm score, rank or driver call for any assigned type. Tao et al. use a "resistor circuit" equivalent-weight model of connectivity, which is not a simulation score. No records were written, so saw_simulation_score is not applicable.
