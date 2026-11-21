# ADJ-harris adjudication notes

Source: Harris, Pfeiffer, Rubin & Truman 2015, eLife 4:e04493 (doi 10.7554/eLife.04493). This is the only assigned source.
19 disputes: 18 `cells` (D0001-D0018) and 1 `unmatched` (D0019). Every dispute is decided in `out/adjudications.jsonl`.

## What I read
- `PROTOCOL.md` in full; `record_schema.json`; `hemilineage_names.csv`; `assigned_sources.csv`; `disputes.jsonl`.
- `text.txt` in full: Results for every hemilineage, the Discussion, the Methods behaviour sections, and all figure and video legends.
- `supp/elife04493s001.txt` (Supplementary file 1: genotypes and off-target expression).
- Figure images 5, 6, 7 and 9, and page image p. 26 (Figure 9).
- Video 2 frame montage: low resolution, and it shows nothing beyond the text, so I did not use it as evidence. The videos themselves were not downloaded (the legends say so).
- `article.pdf` could not be rendered (pdftoppm not installed). The page PNGs and figure JPGs were enough.

No model, simulation or prediction was opened or seen. **No sightings**, so `out/sightings.csv` was not created, and `saw_model_prediction` is false.

## How I handled recurring issues
1. **Figure 9A as evidence for `no`.** Figure 9A is the source's summary of all six behaviour categories (posture change, uncoordinated leg movement, walking, wing wave, wing buzz, takeoff) for every tested line, with 15-25 flies each. Where the text is silent and a column is clearly empty, I treat that category as assessed and absent (`no`). The mapping is: posture → d5/d6; uncoordinated leg movement → d7; walking → d8; wing wave → d11/d12; wing buzz → d13; takeoff → d10.
2. **Figure 9A resolution limit.** Small bars, apart from the large ones, are thin marks that are hard to tell from the row baseline at the resolution available (figure JPG and page PNG only). Where the text is silent and only such a small mark is at stake, I coded `unclear`. This applies to 6A and 6B d10; 10B d5/d6; 12B d8, d11 and d12; 13B d8. Where a small mark agrees with text wording I used it as support (7B walking, 1A wing marks, 10B takeoff). A sharper copy of Figure 9 could settle these cells.
3. **"little" = some.** The authors use "little" for behaviour that did occur at low frequency: for 10B, "little in the way of wing movement" sits next to "Wing flicking and wing buzzing occasionally occurred". So 7B "little walking behavior" gives d8 yes, and 1A "little in the way of wing movement" gives d11 yes. The wing type for 1A is not stated, so d12/d13 are unclear.
4. **"the legs" / "their legs" = all legs** (protocol convention). This applies to 3B, 6A, 8A, 1A ("the limbs") and 21A (Figure 7Q legend "their legs frozen"). Unspecified "leg movements" or grooming with no legs named are coded unclear for d2-d4 (2A; 7B front and hind legs).
5. **"splay".** For 9A and 5B the source says only "splayed out", so d6 (and d5 for 9A) is unclear. Where the source itself says "extended" (20A/22A, 13B), I coded extension. 13B d5 is yes because the body was "resting on their coxae", which is the body lowered and held.
6. **Going airborne = takeoff (d10 yes)** for 2A and 10B. The source's Takeoff category is the fly "launching into the air", and Figure 9A scores these lines under Takeoff.
7. **t2 legs in takeoff jumps (d3 yes) for 18B and 11A/B.** This rests on the source's statement that high-speed video "confirmed the role of the t2 legs in producing the takeoff jump" in the lines where takeoff was common. Both lines are among them and have high-speed videos or figures.
8. **Grooming-associated wing movements count for d11** (6B: "no wing movements except for those associated with occasional grooming bouts"). The protocol counts any wing movement.

## Hard cases / flags for the study team
- **D0018 / D0019 (11A/B) are the same experiment.** Same R26B05 flip-on TRPA1 driver, decapitated flies, 24-37 °C ramp. The curators labelled the hemilineage differently, so one of them left a record unmatched. I answered D0019 `exists: true`, because the source does report this experiment, and coded the record identically to my D0018 decision. **The two should be merged, not counted twice.** One curator's quote/locator for D0018 is from the tsh-GAL80 control. That control removes lineage-11 expression and spares only descending neurons, so I did not treat it as a hemilineage-activation record. I set record_type to `partial_or_mixed` because the source flags descending-interneuron expression that "might be responsible for driving the takeoff behavior".
- Several cells are decided with a value that neither curator gave, because the source supports a third value:
  - D0001: d11 yes
  - D0007: d10 unclear
  - D0013: d5 no
  - D0014: d5 yes
  - D0018: d3 yes
- Supplementary file 1 labels the R50G08 rows "2B", but the text, Video 3 and Figure 9A all call this line 2A. I kept "2A" as the disputed record names it. Not decision-relevant.
- Video 10 legend says a 24-32 °C ramp, but Figure 5M frames are labelled 37 °C. Similarly, Video 16 says 32 °C but Figures 6S,T say 37 °C. These mismatches don't change any disputed cell.
