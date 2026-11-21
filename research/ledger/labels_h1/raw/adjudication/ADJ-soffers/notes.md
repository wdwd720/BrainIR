# ADJ-soffers adjudication notes

Source: 10.7554/eLife.106042 (VNC hemilineage split-GAL4 library). 45 disputes in total: 40 `cells` and 5 `unmatched`. All 45 are decided in `out/adjudications.jsonl`.

## What I read
- PROTOCOL.md, record_schema.json, hemilineage_names.csv, assigned_sources.csv, disputes.jsonl.
- text.txt: the video legends, Table 2 (all rows), the Results sections on 8B, 9A, 12A and 21A, the behavioural-analysis intro, and the Figure 6 legend.
- Supplementary file 1 (driver coverage descriptions) and Supplementary file 5 (genotypes per figure and video).
- Video montages for videos 3, 21, 22, 23, 31, 33, 44, 45 and 50, checked where the text did not settle a cell.
- No video legend text was present in the `_legend.txt` files ("no legend found"). Video titles were taken from the legend list in text.txt.

## Rules applied consistently
- **Held posture reported in the opposite direction counts as `no`.** When the source reports leg extension or a taller fly, d5 is `no`. When it reports flexion or a lowered body, d6 is `no`. The posture was assessed, and the opposite was found. Applies to 1A, 4B, 8A, 10B decapitated, 13A intact and 13B decapitated.
- **Halting statements.** "Halt grooming" (5B, 9B and 13A decapitated) and "halted sporadic leg movements + subtle posture change" (6B) give `unclear`, not `no`, for d1-d4: the source speaks to the legs but never says the flies were motionless. For 5B intact, "halts *almost* every movement" is hedged. I coded the unnamed movement dimensions `unclear` and the held-posture dimensions (d5, d6, d12) `not_assessed`.
- **Legs not named → `unclear`.** Generic leg movement with no leg named gives d2-d4 `unclear` ("erratic walking", "uncoordinated leg movements", joint flexion without legs named). This covers 10B intact, 16B and 23B. "The legs" or "their legs" gives `yes` (13B intact, 9A tethered). For 1B, "most pronounced by the hind legs" presupposes the other legs move too, so d2 and d3 are `yes`.
- **Jumps with no leg description** (8B) give d2-d4 `not_assessed`. A take-off implies leg action, but the source does not describe the legs, and inferring it is barred.
- **record_type.** I chose `partial_or_mixed` only where the source itself says the coverage is partial, or that the labelled off-target cells matter or belong to another lineage:
  - 8B C15/Lim3 in intact flies: the source calls the brain expression "unwanted" and builds the tsh intersection to remove it.
  - 16B: Supplementary file 5 gives the video genotype as VGluT/hb9, which Supplementary file 1 describes as a 15B motor-neuron line.
  - 21A Dr/ey: "somewhat specific", with a cluster likely containing 14A.
  
  Drivers the source calls "specific/very specific, good coverage", with only a few stray cells, are `whole_two_sided`: 7B, 8A, 8B (decapitated and tsh), 13B, 14A, 21A Dr/tj and 23B.

## Uncertain or hard cases
- **15B wings (D0032, D0033).** The text is silent. The video stills show the wings swinging up or open while the fly falls. I coded `unclear` because the stills cannot tell an active wing movement from a passive one.
- **9A tethered (D0019).** Table 2 says "tethered intact", but the video 23 legend says "tethered decapitated". The Results sentence ("both decapitated and intact animals extended their legs", citing video 23) covers both, so d6 is `yes`.
- **5B 'other' record (D0009).** The curators' locators disagree (video 11 feeding vs. video 12 tethered flight). I treated the 'other' preparation as tethered flight. The feeding fly is an intact preparation.
- **Genotype mismatches in the source.** Supplementary file 5 differs from Table 2 for several hemilineages: 4B (ap/fkh), 6B (sens2/vg), 7B (mab21/unc-4), 10B (knot/hb9), 15B (VGluT/nkx6), 16B (VGluT/hb9) and 21A (Dr/ey). Only 16B changed a decision. These are flagged in the reasons.
- **12A clone records.**
  - **Duplicates:** the unmatched records are two curator-duplicated pairs: D0041 = D0044 (dissected T1 clones) and D0042 = D0045 (undissected clones). They failed to match only because the driver strings differ. I gave both members of each pair identical codings, with record_ids 0001/0004 and 0002/0005. **Downstream should keep one of each pair.**
  - **d13 split:** for the dissected clones I set d13 to `unclear`, against both curators' `yes`. Table 2 mentions "bilateral wing buzzing", but the Results attribute high-frequency wing beating to the undissected animals.
- **21A Dr/ey (D0043).** I coded it as its own record. The source also reports a tethered intact Dr/ey experiment (Figure 6H-J, video 53), which no dispute covers. It may be missing from the curated set.
- **Source error noted.** The 8B Results paragraph cites "Figure 3—video 19, 20", which are the 8A videos. The 8B videos are 21-22. The Figure 6 legend heading also says "hemilineage 8 A" for the 8B panels.

## Sightings
None. Figure 6—figure supplement 1 and Supplementary files 2-3 are connectome connectivity counts, not activation predictions, so they are not a sighting under PROTOCOL section 5. No model or simulation was opened. `saw_model_prediction` is false on all records.
