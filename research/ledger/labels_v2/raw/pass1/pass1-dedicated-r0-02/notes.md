# Notes: session pass1-dedicated-r0-02 (pass1)

## Assigned source
- 10.1038/s41586-026-11195-y (Pugliese et al. 2026, Nature). Opening this paper was explicitly allowed for this session.

## What I accessed
- `sources/10_1038_s41586_026_11195_y/text.txt`: abstract only.
- nature.com article page: paywalled ("preview of subscription content"), no full text, no legends, no Methods.
- bioRxiv 10.1101/2025.09.12.675944 v1 `.full` and v2 `.full` (the preprint of the same paper, which the session instructions allow): full text,
  including Results, figure legends, Methods, Extended Data legends and supplementary video legends. I read the text through WebFetch,
  which summarises the page, so I re-checked the two quotes I used against the v2 text, character by character, and both were confirmed verbatim.
- The genotype or key-resources table was not visible in the page text (it shows only "View this table"). I did not fetch the supplementary files.
- I did not use Europe PMC or PMC for the full text, because there is no PMC copy (isOpenAccess N). I did not search for any other paper.

## Records
1. DNg100 > CsChrimson, headless female flies on a spherical treadmill. Forward walking whose velocity and front-leg stepping frequency go up with
   laser intensity. n = 7. Following the convention for evoked walking, all three leg pairs are coded `yes`. The split-GAL4 line is not
   named in the text I read (it cites a prior study), so `driver_lines` = [].
2. DNb08 (SS70620 > CsChrimson), headless female flies. Oscillatory femur-tibia movements of the front and middle legs, described as
   searching or flailing rather than walking. n = 10.
   - Hind legs are not mentioned, so they are coded `not_assessed`.
   - **Uncertain:** the text says the movements were "evoked more reliably when the spherical treadmill was removed", but it never says
     whether the data in Fig. 5d-e were recorded on the ball or in air. I therefore coded `headless_surface` = `other` and
     `labeler_confidence` = `medium`.

## Locators
- The figure numbers differ between preprint versions: the DNb08 experiment is Fig. 4c-e in v1 and Fig. 5c-e in v2. The DNg100
  experiment is Fig. 2h-k in v1 and Fig. 2h-j in v2.
- I used v2 numbering. The Nature numbering could not be checked because the article is paywalled.

## Simulation-score sightings
- The abstract itself, both in the local `text.txt` and in the published abstract, calls DNg100 "the strongest driver of rhythmic leg motor activity" in the computational
  activation screen. It also says that simulations "predicted" that DNb08 drives rhythmic leg movements. Both are logged in `sightings.csv`.
- `saw_simulation_score` = true on both records.
- I asked the fetch tool to leave out simulation results and avoided the simulation sections. One summary said that the supplementary legends include
  "activation screen rankings" and "rhythmicity scores", but it did not report any scores or types. I saw no other type-specific scores.

## No other qualifying experiments
- The text I read contains no other activation experiments in real flies.
