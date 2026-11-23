# a5-adj-06: audit adjudication notes

Assigned type: **DNp09** (the paper names are P9, DNp09 and "P9 (DNp09)"). Four assigned sources; I read all of them. I did no web searches and opened no other sources.

## Mapping
- Every DNp09 record uses `manc_type` = DNp09 with `mapping_confidence` = medium. The kit marks the name "DNp09" as ambiguous: it is also the hemibrain name of DNp71. It also marks SS01540, P9S2 and VT023490;R38F04 as AMBIGUOUS DNp09;DNp71.
- All four papers use Namiki-2018 nomenclature or the Namiki split line. Sapkal et al. 2024 Supplementary Table 3 (FANC/MANC sheet) explicitly gives MANC type DNp09 for P9.
- No new synonyms or driver lines to propose.

## Where the readers differed and what I found (DNp09)

Readers A and B agreed on almost every leg-rhythm call. They differed mainly in which experiments they recorded and in a few codings.

### Bidaye et al. 2020 (Neuron)
- **Readers:** A and B agree on the main experiments: Fig. 1, Fig. 2C-E, P9S2 (Fig. S2E), the four-genotype freezing comparison (Fig. S2A-D/F), males (Fig. S2H-I) and the remote-controlled female (Fig. 4). All are coded yes/yes/yes.
- **Granularity:** A split Fig. 2 into a bilateral-mosaic record and a unilateral record; B merged them. I split them (0002 / 0003) because the expression and the turning outcome differ.
- **Fig. S5L (P9 + BPN co-activation):** only A recorded it. I keep it (0008) at low confidence. BPN is a deliberately co-activated non-DN, and the driver combination is not stated in the text.
- **What I found:** every P9 activation here starts walking from a non-walking state (grooming or copulating flies), so all leg pairs are `yes` under the walking convention. The one genotype that froze in the freezing assay still "initiate[d] walking" first, per the text.
- **Missing material:** figure images and Supplementary Figs S1/S2/S5 and Table S1 are not in the room. These records rest on the text and legends.

### Zacarias et al. 2018 (Nat Commun)
- **Readers:** both coded one record: freezing, legs no/no/no.
- **What I found:** I agree (0009). Fig. 6d shows that flies were already walking (~10 mm/s baseline). A brief running burst comes first, then freezing.
  - Under PROTOCOL 3, the freezing makes the legs `no` and the effect `stops`.
  - The running burst is a speed change in walking flies, so it is listed only as a secondary behaviour.

### Braun et al. 2024 (Nature, descending networks)
- **Reader B missed** ED Fig. 2a: DNp09 stimulation in trials where the fly was *not* walking forward beforehand, with forward-walking probability going from ~0 to ~1. I record it (0011, yes).
- **Agreed:**
  - Fig. 2a (walking-only trials) is `not_assessed`.
  - Fig. 4b intact and ED Fig. 1d are `yes`.
  - Headless (Fig. 4b,f) is `no`: there is no forward walking and only abdominal contraction is reported.
  - Homozygous flies freeze, so `no` (Methods).
  - ED Fig. 10 amputation is `yes`.
- **ED Fig. 1d intensity series:** both readers kept only the ≥21 µW condition. PROTOCOL 1 asks for one record per condition when the outcome differs, so I added 0013 for 2.3/10.5 µW. Walking is not reliable at those intensities, and the legs are `unclear`.
- **Not recorded:** the T1-severed preparation (ED Fig. 3) is an imaging experiment; flies hung freely with "no notable leg movements" attributed to the VNC injury. It is not a behavioural record.
- **Headless choice:** I chose `no` (medium confidence) over `unclear`. The fictive forward velocity stays at baseline, the classifier shows no walking, and the only reported response is abdominal.

### Sapkal et al. 2024 (Nature, halting)
- **Main disagreement with both readers: P9 alone (Fig. 2b,e,h,k).**
  - Both readers coded the legs `yes`.
  - These are "free-walking flies" stimulated without selecting for stationary starts; the baseline translational velocity is ~7 mm/s.
  - P9 raises translational velocity (~13 mm/s) and angular velocity. That is a speed/turning change in flies that were already walking.
  - PROTOCOL 3 says such changes go in `effect_on_walking`, with leg rhythm `not_assessed`. I followed it (0018).
- **Co-activation genotypes:** B recorded P9+BB, P9+FG, P9+FG+BB and P9+BRK; A did not. These are driver lines that label DNp09 together with halt neurons, and they report leg outcomes, so I record them (0019-0022).
  - P9+BB, P9+FG+BB and P9+BRK halt, so legs are `no`.
  - P9+FG pivots on the spot, which is turning in walking flies, so legs are `not_assessed` (B coded `unclear`).
  - Line specificity: `multi_dn` when BB (FlyWire DNg60) is included; `minor_offtarget` for FG (CB0890) and BRK (ascending neurons), which are not DNs. The deliberate co-activation is noted in each record.
- **Headless P9 (ED Fig. 6e):** both readers coded `unclear`, and so do I (0023). The ball shows only a tiny velocity bump, and the legs are not described.

## Overall reading for DNp09
- In intact flies that start from rest, DNp09/P9 activation reliably starts forward walking with turning. This holds across two labs, two lines (SS01540, P9S2), males and females, and freely moving and tethered flies.
- Strong expression (homozygous) or the Zacarias protocol gives running and then freezing.
- In headless flies, DNp09 activation does not produce walking in either the Braun or the Sapkal data.

## Simulation scores
- Sapkal et al. 2024 runs its own connectome spiking-model simulations of P9 activation: firing-rate heatmaps and Δfiring rates of downstream DNs in Fig. 3a-d, ED Fig. 6b-c, ED Fig. 10a and Fig. 5c.
- These are not a rhythm score, rank or driver call for DNp09, so `saw_simulation_score` = false. They were not used as evidence.
- No Pugliese-type scores appear in any assigned source, so there is no `sightings.csv`.

## Not available in the room
- Supplementary videos for all papers.
- Bidaye 2020 figure images, Figs S1/S2/S5 and Table S1.
- Braun 2024 Supplementary Table 6.
