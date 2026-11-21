# Session R1-soffers-a — curation notes

## Source
- `10.7554/eLife.106042` — Soffers et al. 2025, eLife 14:RP106042, "A library of lineage-specific
  driver lines connects developing neuronal circuits to behavior in the *Drosophila* VNC."
- Read in this session: `text.txt` (full Europe PMC XML rendering, incl. Table 1, Table 2, all
  figure legends and the 55 `Figure 3—video` titles), `supp/article.txt` (PDF text, used to
  cross-check Table 2 — identical wording to the XML), Supplementary file 1 (driver-line coverage
  descriptions), Supplementary file 5 (genotypes per figure/video), Figure 6 (behaviour panels),
  the video `_legend.txt` / `_frames.txt` files, and video frame montages.

## Where the activation experiments live
All adult activation experiments in this paper are optogenetic (CsChrimson, red/white light;
Methods "Behavioral analysis": 0.2 mM all-trans retinal, 620–625 nm red LED or halogen white
light, tested at 22–25 °C, 2–10 days post-eclosion). They are reported in:
- **Table 2** — one row per hemilineage, giving driver genotype and phenotype for intact and/or
  decapitated flies. This is the primary record source.
- Four narrative sections (8B, 9A, 12A, 21A) and **Figure 6**, which add detail for those four.
- **Figure 3—videos 1–55**, whose one-line titles state hemilineage and preparation.

## How I split records
Protocol §1: one record = (source, hemilineage, driver/method, preparation, effector). Table 2
rows routinely report **both** intact and decapitated flies for one driver, so most hemilineages
in scope yield **two** records (one `intact`, one `decapitated`) from a single Table 2 row. Where
the source describes a further distinct preparation (tethered, feeding, tethered flight) or a
distinct stimulus intensity, I wrote an additional record, because preparation is part of the
record key and light intensity was reported as a separate experimental condition (11A).

## Hard cases and how I handled them

- **0A.** Table 2 reports "No apparent behavioral response observed in response to acute
  optogenetic activation" with no video. Protocol §1 says to write a record when activation had no
  visible effect, and §2 says d1 = `no` when the source says the flies showed no phenotype. The
  row does not state the preparation and cites no video. I coded `preparation` = `other` with
  `preparation_detail` saying the preparation is not stated, one record, and d1–d15 all `no`:
  protocol §2 says a "no phenotype"/"no visible effect" statement that covers a dimension makes it
  `no`, and "no apparent behavioral response" is a blanket statement covering every body part and
  behaviour. This is the one record where I let a single sentence set all fifteen cells, so it is
  worth a second curator's attention.

- **Halting / inhibition phenotypes (5B, 6B, 9B, 13A).** These hemilineages are reported as
  *stopping* ongoing movement during activation. That is an observation about the activation
  period, so it is codeable, but it is evidence of movement *ceasing*, not of movement occurring.
  I coded the halted behaviours as `no` for the activation period (the source says walking,
  grooming, flight, feeding stop), and coded `yes` only for movements the source positively
  reports during activation (e.g. 6B "a subtle change in the posture"; 13A "femur-coxa extension"
  and "buzz their wings"). Where the source says a behaviour halts but does not say the body part
  was still, I used `unclear`.

- **2A.** The intact-fly and decapitated-fly results differ in the same row (intact: high-frequency
  wing flapping; decapitated: no wing buzzing, only halteres moved ventrally). Two records. For the
  decapitated record, "no wing buzzing was observed" is an assessment of d13 → `no`; d14 → `yes`.

- **12A.** The whole-hemilineage driver (unc-4-GAL4DBD, TfAP2-GAL4AD) was **lethal** — "no
  surviving adults" — so there is no adult activation experiment for that driver and no record for
  it. The codeable experiment is the **clonal** one (FLP-based lineage clones, TfAP-2-GAL4,
  decapitated): `record_type` = `clonal`, and for the dissected cases also effectively one-sided
  (T1, one side). The source additionally lists phenotypes seen in undissected clone animals (high
  frequency wing beating, abdominal extension and bending, backward walking after stimulus
  termination). I kept those in one `clonal` record for the undissected animals, and put the
  backward walking in `other_observation` because the source says it occurred *after* stimulus
  termination (protocol §2: code during activation only).

- **8B.** Table 2 and the narrative section plus Figure 6C,D agree. Two records (intact,
  decapitated). The lim3/c15 driver has broad brain expression; for the Figure 6 experiment the
  authors added a *tsh*-LexA/FLP intersection to restrict CsChrimson to the VNC. Supplementary
  file 5 shows Figure 3—videos 21/22 used the non-tsh genotype while Figure 6B–D used the tsh
  genotype, so the driver field records which one each record rests on.

- **9A.** Table 2 reports three preparations: intact, tethered intact, and decapitated. Three
  records. The narrative section and Figure 6E add that decapitated flies walked erratically with
  legs extended and that this stopped at stimulus end.

- **11A.** Two stimulus intensities are reported as separate conditions ("low intensity" vs "high
  intensity"), each with intact and decapitated animals. The row attributes the high-intensity
  result to "intact and decapitated animals" jointly but the low-intensity result without naming
  the preparation; the four videos (30–33) are strong/weak × decapitated/intact. I wrote four
  records, one per intensity × preparation, and said in `notes` where the table text is joint
  rather than per-preparation.

- **"Both intact and decapitated" rows with a single phenotype** (1B, 4B, 16B, 17A, 23B, 7B, 8A).
  Two records each, same coded cells, differing only in `preparation`; `notes` records that the
  source gives one phenotype statement for both preparations.

- **Record type.** I used `whole_two_sided` where Supplementary file 1 / Table 1 describe the
  combination as specific with good coverage of the hemilineage, and `partial_or_mixed` where the
  source itself flags contamination that may matter for behaviour — notably 13A ("around five
  larger cells … likely 19A neurons"; Table 2 says the wing buzzing is "likely arising from
  contaminating neurons"), 3A and 3B/12B (the only lines are multi-hemilineage: H15-p65.AD,
  ChAT-GAL4-DBD marks 3A + 7B + 12A; fer3-GAL4-DBD, cg4328-p65.AD marks 3B + 12B), 6B
  (mVUM efferents marked), and 15B/16B overlaps. Per protocol §1 I quoted the source's own
  coverage wording in `coverage_notes` and only chose `partial_or_mixed` where the source says so.

- **Hemilineages in my scope with a driver line but no activation experiment.** Table 1 and
  Figure 3—figure supplement 1 show driver lines for 3A, 3B, 6A, 12B that were characterised
  anatomically (expression pattern only). Table 2 contains **no** row for 3A, 3B, 6A or 12B, and
  there is no video for them. Anatomy-only is not a record (protocol §1), so these are
  `not_in_source` in coverage.csv. Likewise 11A/11B etc. are present — see coverage.csv for the
  per-hemilineage outcome.

- **Non-records I deliberately did not write.** (a) Harris et al. 2015 results restated in Table 2
  and in the introduction/discussion — these are another study's outcomes, excluded by protocol §1;
  I note them in `other_observation` only where the source contrasts them with its own result.
  (b) Silencing/ablation: 21A `UAS-hid` elimination (Figure 6K,L) and the larval 5B locomotion
  result (not an adult fly). (c) Anatomy, neurotransmitter and developmental (4B metamorphosis)
  experiments.

## Missing or unavailable
- The videos themselves were not downloaded (meta.json lists all 110 mp4 files as
  "video or audio … not downloaded"). What I had was frame montages plus time stamps. Every
  `_legend.txt` reads "(no legend found in the article XML)"; the only video legends are the
  one-line titles printed in `text.txt` (e.g. "Hemilineage 1 A activation on a decapitated
  animal, 60 FPS"). So video evidence is limited to the montages and those titles, and all my
  quotes are taken from Table 2, the narrative text or figure legends rather than from video.
- No penetrance figures, N values or statistics are given for any activation experiment; the
  `penetrance` field is empty except where the source gives a qualitative frequency
  ("only a few", "occasionally", "less penetrant"), which I reproduced verbatim.

## Model / simulation
No computational model, network simulation or activation prediction was seen. Figure 6—figure
supplement 1 and Supplementary files 2–3 are a **connectome connectivity analysis** of the Giant
Fiber (synapse counts from MANC2.1/neuPrint) — protocol §5 states that a description of
connectivity is not a sighting, so this is not one. I did not open it beyond the legend, and I did
not visit any code host, GitHub or Zenodo link mentioned in the paper (the scRNAseq analysis code
URL in Methods, and splitgal4.org, were left unvisited). `saw_model_prediction` is `false` on
every record and `out/sightings.csv` was not created.
