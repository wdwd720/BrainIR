# Session cheong-1: notes

## Scope
For this session I was told to code only the Cheong et al. (eLife 2024, doi 10.7554/eLife.96084) **published summary** of the
Harris et al. 2015 hemilineage activation results. Doing this sets aside PROTOCOL §1, which excludes results a source restates from
another study. I did not code anything else from the paper. The paper performs no activation experiments of its own. I did not
open Harris 2015.

## Where the summary is
- **Figure 8B, bottom panel**, titled "Activation phenotype*", with the footnote "*Summarized from Harris et al., 2015". It is in
  `figures/elife-96084-fig8.webp` and on article page 19 (`pages/article_p019.png`).
- Legend, Figure 8 (B): "Hemilineage composition of DN downstream and MN upstream partners, compared to hemilineage motor
  activation phenotype as summarized from Harris et al., 2015. Motor phenotypes are marked '+' if ≥50% of flies display it upon
  hemilineage activation in Harris et al., 2015."
- Rows: posture shift, unc. leg mv., walking, wing wave, wing buzz, takeoff. Columns: hemilineages, in the same order as the
  connectivity heatmap above them (42 labels, some of them combined, e.g. "20A.22A", "24B.25B", "20B.21B.22B").

## How I read the format
- `+` means ≥50% of flies showed the phenotype. I coded these as `yes` and put the threshold in `penetrance`.
- `-` means the phenotype was scored but fewer than 50% of flies showed it. That does not say the behaviour never happened, so I
  coded `-` as **`unclear`**, not `no`. (Protocol: `yes` applies at any penetrance, so <50% cannot be read as absent.)
- **Grey cells** cover whole columns. I read them as "no activation data summarised for this hemilineage". The main text (p. ~20)
  refers to "hemilineages with no activation information", which fits that reading. No records were made for grey columns. They
  are listed as `not_in_source` in `coverage.csv`. 22 columns are grey: 16B, 19B, 08B, 00A, 17A, 03A, 13A, 04B, 00B, 27X, 14A,
  09B, 14B, 24B.25B, 21X, 15B, 01B, 04A, 18X, 17B, 26X, 20B.21B.22B, 17X.
- 20 columns have data and got one record each (cheong-1-0001 … 0020).

## How summary columns map to the dimensions
- posture shift `+` → d1 yes. The summary gives no direction (flex or extend) and no body part, so d5 and d6 are always `unclear`.
- unc. leg mv. → d7. walking → d8. wing buzz → d13 (and d11). wing wave → d11. takeoff → d10.
- d12 (wings held raised): set to `unclear` where wing wave is `+`, because "wave" is not described as a held posture. Otherwise
  it is `not_assessed`.
- d2–d4: the summary never says which legs, so they are `unclear` in every record.
- d9 (grooming), d14 (haltere) and d15 (abdomen) have no column in the summary, so they are `not_assessed`.
- d1 is `yes` in every record, because every coded column has at least one `+`.
- preparation: the legend does not mention decapitation, so it is `other` / "as summarised". effector: the summary names none,
  so it is "". (The main text elsewhere calls Harris 2015 an "optogenetic activation study". I did not use that, because it is
  not part of the summary.) driver: "". record_type: `whole_two_sided`, per instruction. The summary says nothing about coverage.

## Uncertainty
- The grid is small in the figure image; the best available file is 1600 px wide. I matched each `+`/`-` to its column by
  horizontal position under the column labels, and checked against page 19. Two statements in the main text agree with my
  reading. (1) Of 6A, 7B, 2A, 19B, 12A and 3B, "four" have wing phenotypes; I read 07B, 02A, 12A and 03B as wing `+`, and 19B as
  grey. (2) 6A and 6B "largely cause uncoordinated leg movements"; I read unc. leg mv. `+` for both. Even so, an error of one
  column for a single symbol cannot be ruled out. A second reader at higher zoom should check the takeoff row for block
  06A/07B/02A and the unc. leg mv. row for 12A/03B.

## Sightings
None. Figure 8G–J ("Bayesian graph traversal") is a connectivity-distance analysis, not a prediction of what activation does. I
did not count it as a sighting. No `sightings.csv` was written.
