# pass2-general-04 — notes (phase 1)

Session `pass2-general-04`, pass `pass2`. This is an independent second reading of the 19 experiments in
`experiments_to_label.csv`, using only the local copies in `sources/`. I used no web access and opened no model or
simulation output.

## Output
- `records.jsonl`: 19 records (`pass2-general-04-0001` … `-0019`), one for each row of `experiments_to_label.csv`, in file order.
- `not_found.csv`: header only, because every experiment was found in its source.
- `dispositions.csv`: all 6 assigned sources have the disposition `records`.
- `sources.csv`, `proposed_driver_lines.csv` (2 rows), `sightings.csv` (header only).

## What I read
For each source I read `text.txt` (Results, legends and Methods), the relevant figures, and the supplementary tables
(PDF text in `supp/article.txt` or the CSVs). I did not watch any videos, because they were not downloaded. Fly counts
come from these tables: S1 Data Fig. 4A (pbio), Supplemental Table 2 (693955) and Supplementary Table 3 (697356).

## Judgement calls and uncertainties
- **GF (pbio.3003553):** the Methods give the stimulus as 2 s pulses at 594 nm, but the Results say a 50 ms flash. Both are
  recorded. Escape is scored only as a binary response, so I coded it `takeoff_or_jump` with legs `no`. The split
  combination 17A04-AD;68A06-DBD is not in the kit, so I proposed it as a DNp01 line because the paper says it is GF-selective.
- **L320 (jneurosci):** the DN in this line matched no hemibrain DN, so it is `UNMAPPED`. The line also labels LH, CL062
  and PVLP077/078 neurons, and the paper attributes the behaviour to CL062. `minor_offtarget` is the closest available
  value, but the off-target expression is actually major (stated in the notes of each record). In the DN-targeted DMD
  experiment only wingspan was measured. I coded it `no_visible_effect` with legs `not_assessed` and confidence `low`.
- **SS81942 (693955):** the paper names only DNg79 for this line. The kit lists DNg31 + DNg79. Row `-0005` (name
  DNg79) → DNg79. Row `-0006` (name given as the line ID `SS81942`) → DNg31, with medium mapping confidence. The paper
  never mentions DNg31, so the behaviour fields of that record simply repeat the DNg79 experiment.
- **DNp47 (693955):** the driver is the Gen-1 GAL4 GMR70C09 (BDSC #39524; the table's short-name column reads
  "SS39524"), so specificity is `unknown`. I proposed it as a driver line.
- **DNb05 'data not shown' lines (693955, row `-0012`):** I kept this as one record listing all 5 lines, as it was
  given. The effector, stimulus and preparation are inferred from the main experiment, so confidence is `low`.
- **Walking-fly wing flicking (693955, Fig. S2-2G):** only wing flicking was scored, so legs are `not_assessed`. DNp07
  produced no flicking and is coded `no_visible_effect` with low confidence.
- **Landing experiments (693955):** these were tethered flying flies with DeepLabCut leg tracking. Landing leg
  extension is a single movement, so every leg-rhythm field is `no`, and `effect_on_walking` is `not_assessed`.
- **MDN (708359):** the hemidriver is printed as "VT50600", presumably a typo for VT50660 (Bidaye 2014, which the paper
  cites). I copied the driver string as written. Group sizes are not stated in the text, so `n_flies` is null and the
  approximate dot counts are given in `n_flies_note`. Backward movement was scored as net distance without leg
  tracking, so confidence is `medium`.
- **MDN (697356):** behaviour in the gap-crossing assay was annotated by hand. I set `effect_on_walking` to
  `not_assessed` because the flies were standing or climbing at stimulus onset; backward walking was induced, not a
  change in ongoing walking.
- **DNg100 (722293):** headless flies on the floor of the closed recording chamber, so `headless_surface` = `other`. The
  paper does not report the number of flies or the stepping frequency.
- **Preparation:** I kept every `preparation` value as given; none was contradicted by its source.

## Score sightings
None. The only mentions of Pugliese et al. (2025 bioRxiv) and Sapkal et al. are reference-list citations in 697356,
722293 and 693955. 722293 also cites them in its text for the statement that DNg100 drives rhythmic running in headless
flies. No rhythm score, rank or driver call from a connectome activation screen is printed in any assigned source.
693955 runs its own leaky integrate-and-fire model of VPN→DN recruitment. That is the paper's own model, which under
section 8 does not count as a sighting, and I did not use it for any label. `saw_simulation_score` = `false` on every record.
