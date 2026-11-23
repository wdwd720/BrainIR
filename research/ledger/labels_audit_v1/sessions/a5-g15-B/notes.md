# Session a5-g15-B notes (audit, run 5)

Sources: 2 assigned. Both are versions of Rayshubskiy et al. (bioRxiv 2020 v4; eLife 2025). I read the full text of both and looked at Figure 8 in each.

Assigned types: DNa01, DNa02, DNa03, DNa11, DNb05, DNb06, DNg13, DNp09, DNp71, DNxl022.

- **DNa02.** The only activation experiment on real flies is stochastic hsFLP ReaChR in SS00730, with intact tethered flies on a ball (Fig. 8A-C). Flies with unilateral expression showed a small ipsilateral turning bias. Flies with bilateral expression were the control group. In them, forward-velocity changes were indistinguishable from no-expression flies (startle), and the authors say the dataset cannot show how DNa02 activation affects forward velocity. I coded unilateral and bilateral as separate records because the expression condition differs. The bilateral records have low confidence, with legs and walking `not_assessed`.
  - Legs were not tracked in the activation experiment, and stimulation was given to flies that were walking on the treadmill. Following PROTOCOL 3, the leg-rhythm fields are `not_assessed` and the turning goes in `effect_on_walking`.
- **DNa01.** Recordings (electrophysiology) and GtACR1 silencing only. There was no activation, so there are no records.
- **Other types (DNa03, DNa11, DNb05, DNb06, DNg13, DNp09).** Mentioned only as citations of other studies (Cande 2018, Yang 2023, Feng 2024, Braun 2024, Bidaye 2020) or in connectome analysis. These papers report no activation experiment of their own for these types, so there are no records.
- **DNp71 and DNxl022.** Not mentioned under those names.
- **Fictive odour/heat (CsChrimson in Orco / Gr28b.d sensory neurons).** This activates sensory neurons, not DNs, so it is not a record.
- **Simulation scores.** I saw no connectome-simulation score, rank or driver call. The "simulation" in the text is a bootstrap null. `saw_simulation_score` = false.
- Small inconsistency in the source: the Fig. 8B legend gives "16/17 flies (uni/bilateral)", while the Methods give 17 unilateral and 47 bilateral brains. I used the legend numbers and explained this in `n_flies_note`.
