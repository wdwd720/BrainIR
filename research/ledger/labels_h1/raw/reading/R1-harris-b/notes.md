# Session R1-harris-b: notes

## Source
- **10.7554/eLife.04493**: Harris, Pfeiffer, Rubin & Truman 2015, *eLife*, "Neuron hemilineages provide the functional ground plan for the Drosophila ventral nervous system." (only assigned source; status full_text).

## What I read
- `text.txt` in full (abstract, digest, introduction, all Results sections, all figure and video legends, Discussion, Methods). The peer-review sub-articles are left out of text.txt. I searched them in `fulltext.xml` and they name no scope hemilineage.
- `supp/elife04493s001.txt` (Supplementary file 1: genotypes for anatomy and behaviour, plus off-target expression).
- `supp/article.txt` (PDF text), used to check driver names in video legends and to get PDF page numbers for locators.
- Figure 7 (hemilineages 15B to 24B) and Figure 9 (summary of behaviour categories), both as the figure JPEGs and on PDF page 26 (150 dpi).
- Video montages for videos 17 to 22 (18B, 19A, 20A/22A, 21A, 23B, 24B). The `*_legend.txt` files say "(no legend found in the article XML)", so I took the video legends from text.txt/PDF. The montages are low resolution and match the text. Video 17 shows a decapitated fly launching (side view). The others show groups of decapitated flies mostly staying in place. The montages added no behaviour that the text does not describe, and I coded nothing from the montages alone.
- The original video files were not downloaded (meta.json "skipped"), so only the montages were available.

## Scope results
| Hemilineage | Outcome |
|---|---|
| 18B | coded (0001) |
| 19A | coded (0002) |
| 20A, 22A | coded as one record "20A/22A" (0003): the source cannot tell them apart and treats them as one unit |
| 21A | coded (0004) |
| 23B | coded (0005) |
| 24B | coded (0006): motoneuron hemilineage |
| 14A | not_in_source: anatomy only; "Our best line for 14A interneurons had major contamination with the 2A hemilineage, so we do not have behavioral data" |
| 15B | not_in_source: anatomy only; "Our best 15B lines had contamination ... we do not have behavioral observations" |
| 19B | not_in_source: anatomy only; "massive contamination from the haltere afferents and so we have no behavioral data" |
| 16B, 17A | not_in_source: "hemilineages 0A, 4A, 16B and 17A are not addressed in this study" |
| 14B | not_in_source: mentioned only as mostly dying ("most of the 14B neurons die") |
| 17B, 17X, 18X, 20B, 21B, 21X, 22B, 25B, 26X, 27X | not_in_source: not mentioned (searched the text, PDF text and XML) |

All experiments: dTRPA1 heat ramp (24 C to 32 or 37 C), decapitated adult females, video at 60 or 30 fps. There were no intact-fly experiments for scope hemilineages. The tethered intact fly experiment was on 5B, which is outside my scope.

## How I handled hard cases
- **Figure 9A** gives the share of flies (0-100% bar scale, n = 15-25 per group) in six categories: Delta posture, Uncoordinated leg movements, Walking, Wing wave, Wing buzz, Takeoff. It scored every tested hemilineage in all six. So:
  - A clearly empty cell for a category was coded `no` for the matching dimension (Uncoord → d7, Walking → d8, Takeoff → d10, Wing wave/buzz → d11-d13, Delta posture → d5/d6).
  - Large bars with no text description of their kind were coded `unclear` (for example, 23B Delta posture, where the source never says whether legs flexed or extended).
  - Thin marks were also coded `unclear` when the text was silent. At the available resolution (150-dpi page image, figure JPEG) I could not reliably read their size, and for 20A/22A not even their column. Exact percentages cannot be read from the figure.
- **record_type**: every line in my scope lists some off-target expression in Supplementary file 1 (except 20A/22A and 23B, which list "none"). The source states "In all cases, the predominant expression in the line was from the target hemilineage", and it never says a line covers only part of a hemilineage. Following PROTOCOL §1, I used `whole_two_sided` and quoted the off-target notes in `coverage_notes`.
- **d2-d4**: "leg movements" with no legs named was coded `unclear`. "the legs"/"their legs" was coded `yes`. For 19A the source names the legs (T2 yes; T1/T3 explicitly no).
- **18B d3**: coded `yes` from the general Results statement that high-speed video confirmed "the role of the t2 legs in producing the takeoff jump" in lines where takeoff was common. 18B is one of these lines (Figure 7E high-speed frames). This is the one place where I applied a general statement to a specific hemilineage, and I flag it.
- **Inconsistencies within the source** (recorded in the record notes, not resolved):
  - 24B: the text and Supplementary file 1 name R15A03. The Video 22 legend (XML and PDF) says "TRPA1 under control of R22G11", which is the 1A driver. The Supplementary file 1 behaviour genotype ends in "LexAop>STOP>GFP" rather than TRPA1. The text also once calls the lineage "Hemilineage 24A", and Figure 7 labels it "Hemilineage 24".
  - 21A: the text says "R51H05-GAL4", while Supplementary file 1 gives a split-GAL4 (R26H05-AD; R51H05-DBD). Figure 7Q legend ("Eventually the flies become immobile ...", "transient hyperkinetic leg movements") does not fully agree with the text ("incessant during the stimulation").
  - 23B: the Figure 7T frame is labelled 36 C, but the Video 21 legend gives a 24-32 C ramp.
  - The Figure 7 legend for panels J/K, titled "Hemilineage 19B", says "The major representation of the 19A cells", which looks like a typo. There is no behaviour data for 19B either way.

## Model predictions
I saw none. There are no simulation or connectome-prediction results in this 2015 source, so there is no `sightings.csv`. No web access was used, and no files were written outside `out/`.
