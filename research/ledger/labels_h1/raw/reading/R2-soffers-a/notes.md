# Session R2-soffers-a — curation notes

## Source read in this session
- 10.7554/eLife.106042 — Soffers JHM, Beck E, Sytkowski DJ, Maughan ME, Devarakonda D, Zhu Y,
  Wilson BA, Chen YD, Erclik T, Truman JW, Skeath JB, Lacin H. eLife 2025;14:RP106042.
- Read: `text.txt` (full Europe PMC XML rendering, incl. all figure/table/video legends),
  `supp/article.txt` (PDF text, used for the page numbers in locators),
  `supp/elife-106042-supp1__Table1.csv` (driver coverage descriptions → `coverage_notes`),
  `supp/elife-106042-supp5__Sheet1.csv` (genotypes per figure and video),
  `fulltext.xml` including the six sub-articles (eLife assessment, three referee reports, author
  response) — these contain no additional activation results,
  `figures/elife-106042-fig6.jpg`, and video frame montages.
- Everything needed was present locally. Nothing was unreachable.

## Where the activation experiments are
- **Table 2** (PDF pp. 16–18) is the backbone: one row per hemilineage with the split-GAL4
  genotype and the behaviour on optogenetic activation in intact and/or decapitated adults.
- **Results subsections** on 8B, 9A, 12A, 21A (pp. 15–17) give more detail for those four.
- **Figure 6** panels C–G.
- **Figure 3—videos 1–55** frame montages; frames are labelled "ON" during stimulation.
- Effector throughout: 20XUAS-CsChrimson-mVenus (14A used CsChrimson-tdTomato; the 12A clonal and
  Figure 6B–D experiments used 20XUAS>dsFRT>CsChrimson-mVenus), red light 620–625 nm or white
  light, 0.2 mM all-trans retinal in food, 22–25 °C, 2–10 days post-eclosion (Methods, p. 23).

## Scope outcome
41 records for 18 of my 24 hemilineages. Six yielded none:
- **00B and 04A**: these names do not occur anywhere in the source. The paper's hemilineage set
  (Table 1) has no 0B or 4A row.
- **03A, 03B, 06A, 12B**: present only in Table 1 and in the Figure 3—figure supplement 1
  expression panels (anatomy / driver expression). None has a Table 2 row, a video, or any
  reported behaviour, so none gives a record.

## Hard cases and how I handled them

**1. Table 2 rows describe intact and decapitated flies in one sentence.** Preparation is part of
the record tuple, so I split these into one record per preparation, each citing its own video, and
repeated the shared quote. Where a clause applies to only one preparation (e.g. 13A's postural
change, stated for intact flies only) I did not carry it over to the other record.

**2. The "8A" in the Figure 6 legend.** The legend text begins "(A–D) Optogenetic activation of
hemilineage 8 A in the VNC triggers jump behavior", but the figure image's own panel header reads
**"8B>CsChrimson"**, the body text describes 8B (lim3/c15 + tsh), and Supplementary file 5 gives
the 8B genotype for those panels. I treated the legend wording as a typo and coded panels A–D as
8B (records 0021, 0022), noting it in each record.

**3. The Results section on 8B cites Figure 3—videos 19 and 20**, but Table 2 and Supplementary
file 5 both assign videos 19/20 to **8A** (ey/ems) and videos 21/22 to 8B. I treated this as a
mis-citation: the 8A records (0017, 0018) cite videos 19/20 per Table 2, the 8B Table 2 records
(0019, 0020) cite videos 21/22. Noted in the records.

**4. 8B was tested with two different genetic set-ups** — the plain C15/Lim3 split-GAL4 (Table 2,
videos 21/22) and the same pair layered with tsh-lexA/FlpL to restrict CsChrimson to the VNC
(Results, Figure 6B–D). Different driver construct, so four records rather than two.

**5. Driver-name discrepancies between Table 2 and Supplementary file 5.** For 4B, Table 2 names
ap-p65.AD + HGTX-GAL4-DBD while supp5 gives ap-p65.AD + fkh for videos 7/8. For 10B, Table 2 names
Hb9-p65-AD + sens-2-GAL4-DBD while supp5 gives knot-p65.AD + hb9-GAL4-DBD for videos 28/29. In
both cases I recorded the driver **as printed in Table 2** and flagged the discrepancy in `notes`.

**6. 9A tethered preparation.** Table 2 says "Activation in tethered intact flies", but the title
of Figure 3—video 23 says "a tethered decapitated animal". I used `preparation` = `other` and put
both readings in `preparation_detail` rather than picking one.

**7. The 12A lethality.** Table 2 reports that the whole-hemilineage line (unc-4-GAL4DBD,
TfAP2-GAL4AD) with CsChrimson gave **no surviving adults**. With no adult flies there is no adult
activation experiment, so this yields no record; it is described in `coverage_notes` of the clonal
records instead. The two 12A records are the FLP-based lineage clones: one for the two animals
whose T1 clones were dissected and identified (0036), one for the animals showing further
phenotypes whose clones were *not* identified (0037).

**8. "12B" in the 12A Results section.** The sentence "We used the unc-4-GAL4DBD and TfAP2-GAL4AD
driver line to express CsChrimson in 12B neurons" sits inside the section headed "Hemilineage
12A", and Table 2's 12A row describes the same line and the same lethality. I read this as a typo
for 12A. Either way it gives no record, because no adults survived — so 12B remains
`not_in_source`.

**9. Halting / inhibition phenotypes (5B, 6B, 9B, 13A).** These report that behaviour *stops*
during activation. I coded the halted behaviour as `no` on its dimension (e.g. grooming halted →
d9 `no`). I used d1 `no` only where the source states that movement generally ceased ("halts
almost every movement in the animal", 5B intact). For 6B tethered flies, where only wing buzzing
and leg movement are said to be inhibited, I used d1 `unclear` rather than `no`, since the source
does not say the fly was motionless.

**10. "Only halteres moved" (2A, decapitated).** I read the word "only" as excluding the other
body parts and coded d2–d13 and d15 `no`, d14 `yes`, d1 `yes`. This is the same reading I applied
to the blanket "No apparent behavioral response" for 0A, where all fifteen dimensions are `no`.

**11. 0A has no stated preparation.** Its Table 2 row cites no video ("N/A") and does not say
whether flies were intact or decapitated. Since the schema has no "not stated" option I used
`other` and said so in `preparation_detail`.

**12. Which legs.** I followed the protocol convention strictly: "all the legs" / "their legs" →
d2–d4 `yes` (4B, 13B intact); an unqualified "leg extension" or "leg segments" → d2–d4 `unclear`
(1A, 8A, 10B decapitated, 13B decapitated). For walking I coded d2–d4 `yes`, since leg movement is
constitutive of walking rather than an inference about it. Where only one leg is named (12A clonal:
"right front leg") I coded d2 `yes` and left d3/d4 `not_assessed`.

**13. record_type.** I used the rule: `partial_or_mixed` when the source itself says the driver
covers only part of the hemilineage (2A: "significantly less neurons are marked in T1") or names
another labelled cell class in the adult VNC that could matter (motor neurons, sensory neurons, a
named other lineage) or attributes a phenotype to contamination (13A's wing buzzing). Unnamed "a
few non-specific cells" I treated as minor and left `whole_two_sided`. The Supplementary file 1
text is quoted verbatim in `coverage_notes` for every record so this call can be re-checked.

**14. After-effects.** 12A's "backward walking immediately after the stimulus termination" is
explicitly after the stimulus, so it went in `other_observation` and d8 stayed `not_assessed`
(protocol section 2).

## Model predictions / sightings
**None seen.** `saw_model_prediction` is `false` on all 41 records and **no `sightings.csv` was
created**. Figure 6—figure supplement 1 and Supplementary files 2–3 are a *connectivity* analysis
of the Giant Fiber (synapse counts from the MANC connectome via neuPrint), which protocol section
5 explicitly says is not a sighting. I did not open any code host, and the two excluded papers
(Pugliese et al.; Sapkal et al.) do not appear in this source's reference list.

## Uncertainties worth a second look by the other curator
- The split of 5B into three records (intact / decapitated / tethered flight). Videos 10, 11 and
  13 are all intact non-tethered assays (free, feeding, walking) and I merged them into one
  record; a curator who treats each assay as its own experiment would produce five.
- d1 for 9A tethered (record 0025): I used `unclear` because "restricted the legs to stay in a
  specific posture" describes a constraint rather than an observed movement.
- Whether 8B record 0020 should have d11 `no` rather than `unclear` — the source says only that
  wing *flapping* was never initiated after take-off, which does not strictly exclude other wing
  movement.
