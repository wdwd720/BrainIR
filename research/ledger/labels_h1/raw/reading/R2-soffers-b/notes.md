# Session R2-soffers-b — curation notes

Source: Soffers et al. 2025, eLife 14:RP106042, doi 10.7554/eLife.106042 — "A library of lineage-specific
driver lines connects developing neuronal circuits to behavior in the *Drosophila* ventral nerve cord."
One assigned source; it was fully reachable.

## What I read

- `text.txt` (full article text with all figure, table and video legends), start to finish.
- `supp/article.txt` (PDF text) to check Table 2 against the XML rendering — the two agree.
- Table 1 (lineage → clusters → driver combinations) and Table 2 (behavioural phenotypes on optogenetic
  activation, 26 hemilineages).
- Supplementary file 1 (detailed description of what each driver line covers) — used for `coverage_notes`
  and for the `record_type` decisions.
- Supplementary file 5 (genotypes per figure and video) — used for the effector and to check driver
  attribution for the videos.
- Supplementary files 2 and 3 (Giant Fiber synaptic inputs/outputs) — connectome connectivity tables only.
- Video frame montages and frame-time files for the videos of the hemilineages in my scope
  (Figure 3—videos 42, 43, 44, 48 viewed as images; legends for 42–55 read).
- Figure 6 and its legend (8B, 9A, 12A, 21A behaviour panels).

## Scope result

Of my 23 hemilineages, this source reports adult activation experiments for **7**: 14A, 15B, 16B, 17A,
19A, 21A, 23B → 15 records. The others are `not_in_source`:

- **18B**: mentioned, but the source says it is the one hemilineage with no assigned scRNAseq cluster and
  Table 1 / Supplementary file 1 record "No line" / "N/A". It appears again only in the Giant Fiber
  connectivity analysis (Figure 6—figure supplement 1, Supplementary file 3). No activation experiment.
- **19B**: Table 1 "No line"; Supplementary file 1 "No specific line". No activation experiment.
- **20A / 22A**: the source only ever writes these together as "20/22 A". Driver lines were built and the
  expression pattern imaged (Table 1, Figure 3—figure supplement 1M, Supplementary file 1), but there is
  no Table 2 row and no activation video. Anatomy only, so no record.
- **24B**: driver line ems-GAL4-DBD, twit-p65.AD built and imaged (Figure 3—figure supplement 1O/P,
  Supplementary file 1). No Table 2 row, no activation video. Anatomy only. (24B motor neurons are also
  mentioned as likely contaminants of some 6A and 8A drivers, which is again not an activation result.)
- **14B, 17B, 17X, 18X, 20B, 21B, 21X, 22B, 25B, 26X, 27X**: do not occur anywhere in the article text,
  tables, supplementary files or video legends. This source uses the 34-hemilineage scheme without the
  X designations.

## How I handled hard cases

- **Table 2 as the unit of coding.** Most Table 2 cells describe both an intact and a decapitated
  experiment in one sentence ("in both intact and decapitated flies..."). I wrote one record per
  preparation, repeating the same quote, because the protocol's record key includes preparation.
- **`record_type`.** I used `whole_two_sided` only where Supplementary file 1 reports good coverage with
  no additional labelled cells named (17A, 19A). Where the source itself names contaminating cells that
  could matter — extra motor neurons (14A, 15B, 16B, 21A-tj), interneurons from other lineages (15B, 16B),
  a cluster that likely contains 14A neurons (21A-ey), chordotonal sensory neurons (23B) — I used
  `partial_or_mixed` and quoted the source's wording in `coverage_notes`. This is a judgement call: another
  curator reading "Very specific and good coverage" as the headline might code several of these
  `whole_two_sided`.
- **Which legs (d2–d4).** I followed the convention literally. "The legs" / "all legs" → yes (15B, 19A
  intact, 21A). A named joint without naming the legs ("flexion at the femur-tibia joint", 16B; "flexion
  at the tibia-tarsus joint", 19A decapitated) → unclear. "Uncoordinated leg movements" / "the leg
  segments" (14A intact, 23B) → unclear.
  - **17A is the one I am least sure of.** "Flexion of all the leg segments" could mean all segments of a
    leg rather than all six legs. I coded d2–d4 `yes`, because the lateral view in Figure 3—video 48 shows
    front, middle and hind legs all drawn in under the body through the frames marked "ON", and the fly
    stands normally again in the frames after the stimulus. I flagged the alternative reading in the
    record's `notes`.
- **d5 vs d7.** Flexion/lowering described without any word implying repetition was coded as held (d5).
  23B is the only record where the source reports both a held posture ("sustained flexion or extension")
  and uncoordinated repeated movement, so d5, d6 and d7 are all `yes` there.
- **14A decapitated (record 0001)** — "femur-tibia joint to move anteriorly, most pronounced in the middle
  legs. We also observed flexion of the legs." The second sentence says "the legs", so I coded d2–d4 `yes`
  rather than restricting to middle legs.
- **21A driver attribution is inconsistent in the source.** Table 2 labels the 21A row
  "Dr-p65.AD, tj-GAL4-DBD" and cites Figure 3—videos 52 and 53, but Supplementary file 5 gives the
  genotype of videos 52/53 as `Dr-p65.AD/+; ey-DBD/+`. The Results section says both combinations were
  used and "both lines showed consistent results". I wrote three records: tj/decapitated and
  tj/intact-tethered from Table 2, and ey/intact-tethered from Figure 6H–J (whose genotype Supplementary
  file 5 gives unambiguously as the ey line). I did not write a fourth, ey/decapitated record, because I
  could not tell from the source whether video 52 is a separate experiment or the same one relabelled.
- **15B driver attribution**: Table 2 names VGlut-p65.AD, HGTX-GAL4-DBD; Supplementary file 5 gives
  `VGluT-p65.AD/...;nkx6-GAL4-DBD/+` for videos 44/45. Both are listed in Table 1 as 15B drivers. I kept
  Table 2's name in `driver` and recorded the discrepancy there.
- **Not coded**: the Harris et al. 2015 phenotypes restated in Table 2 (1A, 2A, 7B, 8A, 10B, 11B, 19A) are
  other studies' results. The UAS-hid elimination of 21A neurons (Figure 6K, L) is an ablation, not an
  activation. Larval 5B locomotion halting is not an adult experiment. None of these are in my scope
  anyway except the 19A and 21A mentions, which I noted inside those records.
- **Effector wording.** The article's Methods give only "0.2 mM all-trans retinal" food and "white light
  ... or red light (620–625 nm)"; no intensity or pulse protocol, except that 11A (out of scope) used
  "low"/"high" intensity. Genotypes in Supplementary file 5 give the CsChrimson transgene, which I used.
  No penetrance figures are given anywhere in Table 2, so `penetrance` is empty on every record.

## Missing / limitations

- The video files themselves were not downloaded (`videos/` holds frame montages, frame times and legend
  stubs). Most `_legend.txt` files read "(no legend found in the article XML)"; the real one-line legends
  are in `text.txt` as the Figure 3—video entries, which is what I used for locators.
- Table 2 gives no sample sizes, no penetrance and no statistics, so d-cells that the source simply does
  not mention are `not_assessed` rather than `no`. I used `no` nowhere: the source never states that a
  body part was checked and did not move for any hemilineage in my scope. (The only clear "no effect"
  statement in Table 2 is for 0A, which is out of my scope.)

## Model predictions

No model, network-simulation or prediction result was seen. Figure 6—figure supplement 1 and
Supplementary files 2–3 are counts of Giant Fiber synapses from the MANC connectome — a description of
connectivity, which the protocol says is not a sighting. `saw_model_prediction` is `false` on all 15
records and no `sightings.csv` was written. I did not open any of the sources listed in PROTOCOL
section 5 and used no web access.
