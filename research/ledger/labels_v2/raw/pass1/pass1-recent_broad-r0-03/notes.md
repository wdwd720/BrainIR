# Notes — session pass1-recent_broad-r0-03 (pass1)

## What I did
- Read PROTOCOL.md (v2) in full, then each of the 6 assigned sources from its local folder (`sources/<slug>/`): text.txt, the
  relevant figure images, and the supplementary text where it existed. I used no web access and no search, and opened no
  model or simulation material.
- No score sightings: no Pugliese-type rhythm score, rank or driver call was seen, so there is no `sightings.csv`.
  `saw_simulation_score` = false on all records.

## Per-source summary
1. **10.1038/s42003-025-09344-6 (Israel & Parnas 2025)**: The paper studies MooSEZ, which in the adult is a brain-intrinsic
   neuron, not a DN. I wrote 3 low-confidence records (UNMAPPED) only for adult activation lines the paper explicitly says
   co-label *unnamed SEZ descending neurons*:
   - the VT032768-AD ∩ R60F09-DBD split (Fig. 3F: "a bilateral pair of SEZ descending neurons"; Supp. Fig. 3E);
   - R60F09-GAL4 (Fig. 3A);
   - R60F09-GAL4 restricted to SEZ/VNC with Otd-FLP and GAL80 (Supp. Fig. 2F-G).
   All give backward walking, which the authors attribute to MooSEZ. These are borderline inclusions. A reviewer may prefer
   to drop them.
   - Not recorded:
     - GH146II, NP225 and NP5288 (broad PN lines; the paper does not say they label DNs);
     - R11E07-GAL4 (broad, no DN statement);
     - the AMB split (labels one lateral horn neuron in adults);
     - the MooSEZ-only VT020742 split;
     - the immortalization and SPARC experiments (no DN identified);
     - all larval experiments.
2. **10.1371/journal.pbio.3003553 (2025)**: 1 record. GF (DNp01) split > CsChrimson drives escape (jump then flight) in
   males across ages (Fig. 4A-B). The Results text says "50 ms red-light flash" but Methods say 2-s pulses; both are noted in
   the record. LC4 and LPLC2 activations are not DNs.
3. **10.1523/jneurosci.0142-24.2024 (Tao et al. 2024)**: 3 records for an unidentified DN pair co-labelled by L320 (no
   hemibrain match per the authors):
   - freely moving whole-line activation (aggressive actions);
   - head-fixed whole-line activation (wings only measured);
   - DMD spot activation restricted to the DN (no wingspan change).

   Leg movement during the DMD experiments was not reported, so legs are `not_assessed`. CL062-split, L188 and L2193 do not
   label DNs.
4. **10.64898/2026.02.26.708359 (Lee et al. 2026, bioRxiv)**: 3 records, one per figure (Figs. 1C, 2K, 3M), for control MDN
   activation (backward walking). Some details:
   - Knockdowns of Hb, Lar and Inx8 in MDN abolish backward walking: Hb and Lar knockdowns give net forward movement, and
     Inx8 knockdown gives pausing. These are genetic perturbations of the DN, so I described them in record notes rather
     than writing separate records.
   - The n values for Figs. 1C and 2K are estimates from plotted points, so `n_flies` is null.
   - The paper writes the driver as VT50600; the kit lists MDN-1 as VT50660 × VT44845. This is likely a typo in the paper,
     so I proposed no new mapping.
5. **10.64898/2026.05.03.722293 (2026, bioRxiv)**: 1 record. DNg100 split > CsChrimson in decapitated flies gives sustained
   running with 3D leg kinematics (Fig. 5c-d).
   - Number of flies not stated.
   - The surface is the chamber floor, coded `other`.
   - The white strobe illumination also activates CsChrimson, per the authors.
6. **10.7554/elife.107450 (Zung et al. 2025)**: `no_qualifying_experiment`. It is an anatomical split-GAL4 catalogue that
   only cites earlier activation work. The supplementary tables were not in the folder (`supp/` empty), but they are
   line/annotation lists, not behaviour.

## Uncertainties
- Unnamed DNs (sources 1 and 3) are `UNMAPPED`; I proposed no synonyms for them.
- For leg-rhythm coding, backward and forward walking were coded `yes` for all legs per convention. Except for source 5,
  none of these studies tracked legs: they measured centroid velocity or distance.
- Proposed driver lines: the GF split 17A04-AD;68A06-DBD → DNp01, and the DNg100 split (written AD/DBD form) → DNg100.
