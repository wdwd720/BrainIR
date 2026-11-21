# Notes: session pass1-walking_stopping-r0-01

## Sources
One source was assigned: Sapkal et al. 2024, *Nature*, doi 10.1038/s41586-024-07854-7 (full text, local copy).
What I read: text.txt (Europe PMC XML full text, all legends); figures Fig. 1, 2, 4, ED Fig. 1, 4, 6;
Supplementary Table 1 (genotypes and n), Table 2 (key resources), Table 3 (FlyWire and FANC/MANC IDs); the reporting
summary; source-data CSVs for Fig. 3j and ED Fig. 6e. No web access was used. The supplementary videos were not
downloaded, so they could not be checked.

## Simulation content and sightings
- This paper contains its own connectome-constrained spiking model (Shiu et al. LIF model): Fig. 3a-h,
  Fig. 5a,c,d, ED Fig. 6b,c, ED Fig. 8e, ED Fig. 9c and ED Fig. 10. These are the paper's own firing-rate
  simulations of halt/walk interactions. They are not a Pugliese-type rhythm score, rank or driver call, so under
  PROTOCOL section 8 they are **not a sighting**. No sightings.csv was written, and every record has
  `saw_simulation_score = false`.
- I did not use any simulation result as evidence. I did not open the Fig. 3, Fig. 5, ED Fig. 9 or ED Fig. 10
  images. ED Fig. 10c is described in its legend as marking "predicted walk/halt neurons", and I did not look at it.
  For Fig. 3j (oDN1/BDN2 activation) I used the text, the legend and the source-data CSV.
- I opened the ED Fig. 6 image to read panel e (headless P9/oDN1/BDN2). Its panels b-c are the paper's own scatter
  of simulated firing-rate changes, i.e. which DNs FG and BB inhibit. They are not a walking-driver prediction or a
  rhythm score, and I did not use them.

## Scope decisions (please review)
- **BRK** is an ascending neuron (MANC AN19A009, per Supp. Table 3), not a DN. I wrote no BRK-only records: Fig. 1
  and 4, ED Fig. 1d, 2, 3, 7 and 9e are all excluded. The three BRK Gal4 lines in the ED Fig. 1a screen (R37F06, R36G02,
  VT012408) are also excluded, because the paper does not say they label DNs.
- **BPN** is described as a "higher brain neuron", not a DN. The BPN-alone and BPN+BRK records are therefore omitted.
  BPN+BB, BPN+FG and BPN+FG+BB are recorded for the BB and FG DN-like neurons.
- **Co-activation lines** (walk DN + halt neuron) were recorded as driver lines labelling DNs. Following PROTOCOL
  section 1, there is one record per DN type in the line (MDN, DNp09, BB, FG, BDN2), each flagged "Co-activation
  experiment" in `notes`. For partners that are not DNs (BRK, BPN), `line_specificity` is `minor_offtarget`, with the
  partner named in `other_cell_types` as "deliberately co-activated". These records describe interaction phenotypes.
  Downstream users may want to filter them out of the single-DN tables (records 0021-0042).
- **FG (Foxglove)**: the paper says FG and BB "stochastically descend until the anterior tip of the nerve cord".
  FG is FlyWire CB0890 with no MANC match, and it is not in the kit. I treated FG as DN-like and wrote its records as
  `UNMAPPED` / `low`.
- **BB (Bluebell)**: the kit lists it as ambiguous (DNg60 / DNxn073). The paper identifies BB as FlyWire type DNg60
  (Supp. Table 3). In the kit, FlyWire DNg60 is the flywire type of MANC **DNxn073**, while MANC DNg60 corresponds to
  FlyWire DNge096, so I chose DNxn073 with `medium` confidence. This is proposed in proposed_synonyms.csv.
- **ED Fig. 1a halting screen**: the paper reports only the 11 hit lines, so it is not a systematic screen and is
  coded `targeted_study`. Records were written for the labelled hits that may label DNs: SS31369, SS31366, SS44893
  and SS31341 (kit: ambiguous DNg60/DNxn073, 'mesa'/'bluebell...') and SS31388 (not in kit; hemidrivers are the BB
  pair swapped). All are `UNMAPPED`. SS31326, SS40909 and SS31328 are folded into the Fig. 1 and ED Fig. 1b records.
  Supp. Table 1 also lists SS40926, SS44892, SS44898 and SS44896 under ED Fig. 1a, but I could not find them labelled
  in the figure heatmap and no outcome is stated, so I wrote no records for them. The text says "11 genetic drivers",
  which matches the 11 labelled rows.

## Mapping discrepancies
- The paper's Supp. Table 3 MANC labels for oDN1 (**DNxl054**) and BDN2 (**DNxl058**) are not in type_list.csv. I
  used the kit synonyms (oDN1 -> DNg97, BDN2 -> DNg100, both unambiguous, `high`) and proposed the paper labels as
  synonyms.
- P9 / DNp09: the kit lists DNp09 as also a hemibrain synonym of DNp71, and the P9 line as AMBIGUOUS. The paper's
  Supp. Table 3 gives MANC DNp09, so I chose DNp09 with `medium` confidence.
- The MDN line ID as written in Supp. Table 2 (VT044845-AD;VT050660-DBD) is UNMAPPED in the kit. I mapped it by name
  (MDN, `high`) and proposed the line mapping. Note that Supp. Table 1 writes the hemidriver halves in the opposite
  AD/DBD order.

## Other uncertainties
- Sex for decapitated tethered experiments (Fig. 4e-j, ED Fig. 6e) is not stated and is coded `unknown`. Intact
  tethered kinematics used males; free-walking experiments used females.
- Headless P9 (ED Fig. 6e): the text only says forward turning is absent. The figure shows a small transient
  increase in translational velocity, so legs are coded `unclear` and the category `other`.
- Headless BDN2 in ED Fig. 6e used 7-10-day-old flies. Methods say robust walking needed 10-12-day-old flies (as
  used in Fig. 4), so the ED Fig. 6e BDN2 effect may be weaker than the text implies.
- MDN+FG+BB (records 0025-0027) is not discussed in the text. Its outcome comes from the figures, and the quote is
  the ED Fig. 4 legend phrase naming the experiment, so confidence is `low`.
- Muscle-imaging activations (Fig. 4k-n, ED Fig. 7) were done with legs glued, so leg movement could not be
  observed. No records.
- Supp. Table 1 (Fig. 5e-h, ED Fig. 8j) appears to swap the BB/FG hemidriver genotypes for the silencing rows. This
  is silencing data only and does not affect any record.
