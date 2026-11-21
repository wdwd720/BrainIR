# Notes: session pass1-escape_landing-r2-01 (pass1)

## Sources
One assigned source: 10.1371/journal.pone.0267834 (Luo et al. 2022, PLoS ONE). Local copy has full text (Europe PMC XML and
PDF). I read text.txt, the PDF text (supp/article.txt), Table 1 (genotypes), Figs 2 and 3 (images), and the supplement
listing. S1 Fig, S2 Fig and S1 Table cover the device and materials only; S1 File is Arduino code. I did not run or open any
of the code. I used no web tools.

## Records (2)
- 0001 GF / DNp01 (GF-split-Gal4 = R17A04-p65ADZp; R68A06-ZpGdbd), tethered intact fly: takeoff (middle leg extension, wing
  depression, flight). Legs coded `no` (single movement). n = 24 per group.
- 0002 SS1540 (kit ID SS01540), named DNp09 by the paper, tethered intact fly: freezing (leg movement stops). Coded
  `halting` / `stops`, legs `no`. n = 80.

## Uncertainties
- **DNp09 mapping.** The kit marks the name DNp09 as ambiguous (DNp09 or DNp71, because of the hemibrain name). The paper uses
  Namiki nomenclature and cites Namiki 2018 for the line, so I chose MANC DNp09 with `medium` confidence.
- **What SS1540 activates.** The paper itself says the neurons behind freezing are unknown and suggests that other neurons in
  SS1540, not DNp09, may cause it (citing Bidaye 2020). I marked the line `minor_offtarget` and left those cells unnamed.
  Downstream users should not take freezing as a DNp09-specific phenotype.
- **Freezing in controls.** 20% of non-retinal SS1540>CsChrimson flies also froze. The authors suggest trace β-carotene in
  the food.
- **Penetrance.** I read the values (about 83% and about 62%) from bar heights; the text gives no numbers.
- **Driver ID for GF.** The paper gives no SS ID for GF-split-Gal4, so I recorded the hemidriver pair as written. I proposed
  a driver-line mapping to DNp01 in proposed_driver_lines.csv.
- **Not separate records.** The high-school workshop runs used the same two genotypes but report no per-genotype behaviour
  data.
- **Not downloaded.** S1/S2 Movies (MP4) and peer-review attachments. They are not needed for the records.
- **Repository not visited.** The paper's data repository is on GitHub, which this protocol blocks.

## Simulation scores
None seen. No sightings.csv written.
