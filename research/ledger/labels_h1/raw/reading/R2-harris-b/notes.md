# Session R2-harris-b: curator notes

## Source
One assigned source: Harris, Pfeiffer, Rubin & Truman 2015, eLife 4:e04493 (doi 10.7554/eLife.04493), status full_text.

## What I read
- `text.txt` in full: abstract, digest, all Results sections, Discussion, Methods and all figure and video legends.
- `supp/article.txt` (the PDF text), used to assign page numbers; locators use PDF page numbers ("p. N of 34").
- `supp/elife04493s001.txt` (Supplementary file 1: genotypes and off-target expression).
- Figure 7 (`figures/elife04493f007.jpg`) and Figure 9 (both the `figures/elife04493f009.jpg` image and the page render `pages/article_p026.png`).
- Video montages, frame-time files and legend files for Videos 17-22 (in-scope hemilineages). The `_legend.txt` files say "no legend found"; the video legends were taken from the article text instead.
- No model, simulation or prediction was looked for or seen. **No sighting**, so there is no `sightings.csv`. Only the local files in `sources/` were used; no web access.

## Scope result
| hemilineage | result |
|---|---|
| 18B | coded (R2-harris-b-0001) |
| 19A | coded (0002) |
| 20A, 22A | coded as one record "20A/22A" (0003); the source could not separate the two and treats them as one unit |
| 21A | coded (0004) |
| 23B | coded (0005) |
| 24B | coded (0006) |
| 14A | not_in_source: "Our best line for 14A interneurons had major contamination with the 2A hemilineage, so we do not have behavioral data" (anatomy only) |
| 15B | not_in_source: "Our best 15B lines had contamination ... we do not have behavioral observations" |
| 19B | not_in_source: "massive contamination from the haltere afferents and so we have no behavioral data" |
| 16B, 17A | not_in_source: "hemilineages 0A, 4A, 16B and 17A are not addressed in this study" |
| 14B, 20B, 22B | not_in_source: mentioned only in developmental context (cells die or become motoneurons); no activation |
| 17B, 17X, 18X, 21B, 21X, 25B, 26X, 27X | not mentioned in the source |

## How I handled hard cases
- **All experiments:** dTRPA1 activation with a 24 C to 32 or 37 C heat ramp in decapitated adult females, one line per hemilineage. The ramp range comes from each video legend.
- **Record type:** all coded as `whole_two_sided`. The source never says a behaviour line covers only part of its hemilineage, and the Discussion says that "In all cases, the predominant expression in the line was from the target hemilineage". The off-target expression listed in Supplementary file 1 is quoted in `coverage_notes` for each record.
- **Figure 9A:** Figure 9A is a bar chart giving the percentage of flies (0-100% scale, 15-25 flies per group) in six categories: change in posture, uncoordinated leg movement, walking, wing wave, wing buzz and takeoff. I used it as follows:
  - Where a column is clearly empty for a row, I coded the matching dimension `no`.
  - Where a column has a large bar, I took it as support for what the text says.
  - Where a column seems to have only a very thin bar that I cannot read with confidence at the available resolution (page render 150 dpi), and the text says nothing about that behaviour, I coded `unclear` and said so in `notes`. This affects 20A/22A (walking, wing buzz), 21A (wing wave, wing buzz) and 23B (walking, wing buzz).
  - The exact percentages cannot be read, so `penetrance` is empty for every record.
  - A second curator with a sharper image may read these thin bars differently.
- **Change-in-posture bars:** where the text does not say flexion or extension (19A small bar, 21A "legs frozen at unusual angles", 23B large bar, 24B "held at awkward angles"), d5 and d6 are both `unclear`.
- **Which legs:** "their legs" and "movements of the legs" are read as all legs (d2-d4 `yes`), per the protocol. "Limb movements" and "walking" without naming legs give d2-d4 `unclear`.
  - For 18B, the general Results statement that high-speed video confirmed "the role of the t2 legs in producing the takeoff jump" is not tied to 18B specifically, so d3 stays `unclear`.
- **Video montages:** used only to check that they agree with the text, not to code new movements. The Video 21 (23B) montage shows flies moving position in later frames, while the source says they "basically stay in place". This is recorded in `other_observation` and supports leaving d8 `unclear`.

## Inconsistencies in the source (recorded, not resolved)
- **24B:**
  - The text names driver R15A03-GAL4, but the Video 22 legend says "under control of R22G11" (R22G11 is the 1A driver).
  - Supplementary file 1's "Behav" genotype for 24B ends in LexAop>STOP>GFP rather than TRPA1.
  - The section header says 24B, but its first sentence says "Hemilineage 24A ... all of the B daughters are leg motoneurons".
  - 24B is absent from Figure 9A.
- **23B:** the Video 21 legend gives a 24-32 C ramp, but the Figure 7T frame is labelled 36 C.
- **21A:** the text calls the leg movements "incessant during the stimulation", while the Figure 7Q legend says the flies "eventually ... become immobile with their legs frozen".
- **19B:** the Figure 7 (J, K) legend says "The major representation of the 19A cells", apparently meaning 19B. Not relevant to any record.

## Missing material
The original supplementary videos (.mov/.mp4) were not downloaded; only the frame montages were available. The two peer-review sub-articles in the XML are not included in `text.txt` and were not read.
