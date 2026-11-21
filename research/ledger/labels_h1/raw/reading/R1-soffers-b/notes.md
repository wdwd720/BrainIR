# Session R1-soffers-b — curator notes

Source: Soffers et al. 2025, eLife 14:RP106042, doi 10.7554/eLife.106042, "A library of lineage-specific
driver lines connects developing neuronal circuits to behavior in the *Drosophila* ventral nerve cord."
One assigned source; status `full_text`.

## What I read
- `sources/.../text.txt` (full article text with all figure, table and video legends), start to finish.
- `supp/article.txt` and the page images `pages/article_p016.png`–`p017.png` for Table 2, which is the
  main behavioural table (it spans pages 16–17 and is badly linearised in the plain text; I checked the
  page image to be sure of row boundaries and of which hemilineages have rows).
- Figures 3, 3—figure supplement 1, 6 and 6—figure supplement 1.
- `supp/elife-106042-supp1__Table1.csv` (Supplementary file 1: detailed expression/coverage of each driver
  combination) — used for `coverage_notes` and for `record_type`.
- `supp/elife-106042-supp5__Sheet1.csv` (Supplementary file 5: genotypes per figure and per video).
- Video frame montages and frame-time files for Figure 3—videos 42–55, i.e. every video belonging to a
  hemilineage in my scope (14A: 42, 43; 15B: 44, 45; 16B: 46, 47; 17A: 48, 49; 19A: 50, 51; 21A: 52, 53;
  23B: 54, 55). The montages carry an "ON" overlay on the frames taken during optogenetic stimulation, so
  they can be used to tell what happened *during* activation.

## Scope and what was found
Hemilineages in my scope with activation experiments in this source: **14A, 15B, 16B, 17A, 19A, 21A, 23B**
(all in Table 2, "Overview of behavioral phenotypes upon optogenetic activation of specific hemilineages",
plus the "Hemilineage 21A" Results section and Figure 6H–J for 21A). 16 records written.

The other hemilineages in my scope are **not** in any activation experiment here:
- 18B, 19B: appear in Table 1 only, both with "No line" (18B is additionally the one hemilineage that
  could not be assigned to an scRNAseq cluster). No behaviour.
- 20/22A and 24B: driver combinations exist and their expression patterns are shown (Table 1,
  Figure 3—figure supplement 1M, 1O, Supplementary file 1), but they have no row in Table 2 and no
  behavioural experiment anywhere in the paper.
- 14B, 17B, 17X, 18X, 20B, 21B, 21X, 22B, 25B, 26X, 27X: not mentioned at all (the paper uses the 34
  major post-embryonic hemilineage set and does not use X-type names).
All of these are listed in `coverage.csv` as `not_in_source`.

## Decisions on hard cases
- **One record per (hemilineage, driver, preparation).** Table 2 usually describes the intact and the
  decapitated preparation in one row; these are two different experiments, so each row gave two records.
- **21A has four records.** The Results section says two driver lines were used (Dr-GAL4AD + ey-GAL4DBD and
  Dr-GAL4AD + tj-GAL4DBD), that both target most 21A neurons and that "both lines showed consistent
  results", with "stimulation of either intact or decapitated animals" forcing the legs into a specific
  geometry. I therefore wrote line × preparation = 4 records (0011–0014). *Caveat:* Table 2 gives
  tj-GAL4-DBD as the genotype for Figure 3—videos 52/53, while Supplementary file 5 lists ey-DBD for the
  same two videos; the source is internally inconsistent about which video belongs to which line. The
  video-based detail is cited in the tj records and Figure 6H–J (genotype ey-DBD in Supplementary file 5)
  in the ey record. A second curator may reasonably have coded 21A as two records instead.
- **Other genotype mismatches between Table 2 and Supplementary file 5**: 15B (Table 2: HGTX-GAL4-DBD;
  Supp. 5 for videos 44–45: nkx6-GAL4-DBD) and 16B (Table 2: Bi-GAL4-DBD; Supp. 5 for videos 46–47:
  VGluT-GAL4-DBD). Both variants are recorded in the `driver` field; Supplementary file 1 describes both
  members of each pair as targeting the same hemilineage.
- **d5/d6 (held postures).** Table 2 often says "flexion" without saying whether it was sustained. I coded
  d5 `yes` only where the text itself says the posture was held ("until after light stimulation ended",
  "stay in this position", "sustained flexion or extension") or where the ON frames of the corresponding
  montage show the posture maintained for the whole stimulus (14A decapitated, 16B, 17A, 21A). For 19A
  decapitated the ON/OFF difference in the montage is too subtle to judge and the text does not say
  "sustained", so d5 is `unclear`.
- **Which legs (d2–d4).** "the legs", "all the legs", "the leg segments" → d2–d4 `yes`. "uncoordinated leg
  movements" or a named joint without a named leg → `unclear`, unless the montage resolves it (16B
  decapitated, where the profile view shows all three leg pairs flexing with the body lowered; the top-view
  intact video of the same line does not, so that record is `unclear`).
- **d8 `no`** was used only where the source explicitly negates coordination ("flies remained uncoordinated
  until the cessation of the stimulus": 14A intact, 23B). Where locomotion is simply not discussed I used
  `not_assessed`.
- **d11 `unclear` for 15B.** During the stimulus the flies collapse onto their side/back and the wings look
  spread in the montage, but the roll of the body confounds this and the text says nothing about wings, so
  the montage does not decide.
- **Comparisons with Harris et al., 2015** appear in several Table 2 rows (e.g. the 19A leg-waving of T2
  legs). These are restatements of another study and gave no records; I noted the 19A one in
  `other_observation`.
- **Not coded**: the UAS-hid ablation of 21A (Figure 6K–L) — not an activation experiment; all anatomy,
  neurotransmitter and developmental (larval/pupal) figures; the 12A clonal and 8B/9A experiments (outside
  my scope).

## Missing / limitations
- The actual movie files were not downloaded (`videos/` holds only frame montages and legends), and
  Figure 3—videos 42–55 have **no legend text** in the XML (`*_legend.txt` reads "no legend found"); the
  only legends for these videos are the one-line titles in `text.txt` ("hemilineage 15B activation on a
  decapitated animal, 50FPS" etc.), which is what I used to assign preparation per video.
- Table 2 gives no penetrance or sample sizes for any hemilineage in my scope, so `penetrance` is empty in
  every record.
- No model, simulation or connectome-prediction material was read. Figure 6—figure supplement 1 is a
  description of measured Giant Fiber connectivity from the MANC connectome (counts of synapses per
  hemilineage); that is a connectivity description, not a simulation prediction of what activating a
  hemilineage does, so it is not a sighting and no `sightings.csv` was written. The Methods mention a
  GitHub URL for the scRNAseq analysis code; I did not visit it.
