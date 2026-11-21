# Verifier notes — session verify-2

## What I read
- PROTOCOL.md (all of it) and to_verify.jsonl (30 lines: V001–V012 from 10.7554/eLife.04493, V013–V030 from 10.7554/eLife.106042).
- **eLife.04493 (Harris et al. 2015):** I read text.txt in full (Results, legends, Discussion, Methods) and Supplementary file 1 (genotypes and off-target expression). I looked at Figures 4, 5, 6, 7 and 9 (Fig 9 also on page image p. 26) and the montage for video 2 (1A) and video 15 (12B).
- **eLife.106042 (Soffers et al. 2025):** I read text.txt (Results incl. Table 1, Table 2, the 8B/9A/12A/21A sections, Methods 'Behavioral analysis') and Supplementary file 5 (genotypes). I looked at Figure 6 and the montages for Figure 3 videos 10, 11, 13, 16, 17, 18, 21, 24, 25, 27, 28, 31, 43, 51 and 55. I did not open the montages for videos 35 and 40; the text was decisive for those lines. The video legend files in this source contain no legends, only the video titles from the text.

## Conventions I applied
- I coded the 13 cells the task lists (d1–d6, d7, d8, d10, d11, d13, d14, d15). The task text says 'twelve', but it names 13.
- **Leg cells (d2–d4):** I coded yes when the source says "the legs", "their legs" or "their limbs" as a set. I coded unclear for "leg movements", "walking" or a jump where no legs are named. This is a judgement call: for V001, V004, V006 and V007 a stricter reader could code d2–d4 unclear.
- **Harris 2015 Figure 9A** is a six-category bar summary per hemilineage (0–100%). A category with no bar was read as assessed and absent, so `no`. The figure is low resolution, so small ticks are hard to tell apart from the baseline. Where a tick seemed visible but the text was silent, I coded `unclear` and said so. Where the text explicitly denied a behaviour (e.g. 5B "no walking or wing associated behaviors"), I followed the text.
- "Splayed" legs (Harris 9A and 5B) were not treated as extension unless the source says "extended" (it does for 20A/22A).
- d14 (halteres) and d15 (abdomen) are never mentioned for these hemilineages in Harris 2015, so `not_assessed`.

## Discrepancies found in the sources (worth checking against the curators' records)
- Harris 2015 Supplementary file 1 labels the R50G08 rows "2B". The text, figures and video call it 2A (V002).
- Harris 2015 text cites "Figure 6D" for 6A; the panel is Figure 5D (V004).
- Harris 2015 effector temperatures: video legends say 24–32 °C, but some figure frames are labelled 36–37 °C (8A V006, 23B V012).
- Soffers 2025 Supplementary file 5 genotypes conflict with Table 2:
  - 7B videos 16–18 are given as mab21-GAL4-DBD/unc-4-p65.AD, not sv-p65.AD/unc-4-GAL4-DBD (V015, V016).
  - 10B videos 28–29 are given as knot-p65.AD/hb9-GAL4-DBD, not Hb9-AD/sens-2-DBD (V023, V024).
  - 5B videos 9–13 list a myr::GFP reporter instead of CsChrimson (V013, V014).
- Soffers 2025: the 8B Results paragraph cites Figure 3-videos 19/20, which are titled 8A. The Figure 6 legend title says "8 A" though the panels are 8B (V018, V019).
- Soffers 2025: the V017 locator includes Figure 3-video 22, which its title says is an intact animal, but the record is decapitated.
- Soffers 2025 video 24 is titled "decapitated", but its montage frames appear to show a head. I could not resolve this.

## Hard cases
- V013/V014 (5B arrest): d1 is `unclear` because of "halts almost every movement". The other movement cells are `no` from the blanket statement.
- V022 (9B intact): negatives rest on "did not lead to any robust behavior", which is a qualified negative.
- V024 (10B decapitated): d11 is `yes` from the video montage only (wings raised in ON frames). The text mentions only leg extension and body twisting.
- V030 (23B intact): "sustained flexion or extension" was coded d5/d6 `unclear`.

## Model predictions
No model or simulation prediction was seen. Soffers 2025 Figure 6—figure supplement 1 and the Discussion describe Giant Fiber connectome connectivity (synapse counts). Under PROTOCOL §5 that is connectivity, not a sighting, so there is no `sightings.csv` row. I opened no external resources.
