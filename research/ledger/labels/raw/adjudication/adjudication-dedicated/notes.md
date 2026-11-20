# Adjudication notes — session `adjudication-dedicated`, pass `adjudication`

## Scope
- 14 experiments and 15 disputed fields from `disagreements.csv` (exp 0019 has two disputed fields).
- Output: 14 records in `records.jsonl` (one per experiment) and 15 rows in `decisions.csv`.
- Every `exp_id` was copied unchanged from `disagreements.csv`.

## Sources opened
- **Pugliese et al.**
  - PMC13142387 (accepted manuscript): main text, then a second read from offset 100000 for Methods and the Extended Data Fig. 3 legend.
  - bioRxiv 10.1101/2025.09.12.675944 v1 full text.
  - The Nature URL redirected to a login page, so I did not use it.
  - The Tuthill lab PDF was too large to fetch.
- **Sapkal et al.:** bioRxiv 10.64898/2026.04.29.721658 v2 full text.
  - The site returned HTTP 429 about 15 times before it loaded.
  - The section of the text from character 200000 onward was not read.
  - Supplementary Tables 1-2 (genotypes and n per genotype) were not read.
- Europe PMC REST metadata, for both preprints.
- Two web searches.

## Simulation scores seen (PROTOCOL §6)
- **DNg100:** A web-search summary on my first search said Pugliese et al.'s computational screen found DNg100 to be "the strongest driver of rhythmic leg motor activity". The search summary also mentioned that a third-party GitHub project exists; I did not visit it. I stopped reading those parts. `saw_simulation_score` = true on all 9 DNg100 records:
  - adj-dedicated-0001, 0003, 0005, 0006, 0007, 0008, 0009, 0011, 0013
- **DNb08:** A page summary said simulation results for DNb08 appear in Pugliese et al. I did not read a score, but I set `saw_simulation_score` = true on adj-dedicated-0002 to be conservative.
- **DNg97 and DNg75:** A page summary of Sapkal et al. named DNg97, DNg75, DNg100, DNb08 and MDN as having "connectome/model-related" results. Sapkal's computational work is described as connectome searches, and I saw no score for these types.
  - `saw_simulation_score` = false for DNg97 (0004, 0014), DNg75 (0012) and DNg16 (0010).
  - A stricter reader could set the DNg97 and DNg75 records to true.
- A search result listed an arXiv paper, "How much of fly walking is written in the wiring?". It looked computational, so I did not open it.
- None of my decisions used any model or simulation result.

## Coding rule used for `effect_on_walking` (applied consistently)
- **`speeds`:** Used when walking speed was measured on a substrate (ball forward velocity) and stimulation made a resting headless fly walk forward.
  - Sapkal et al. state that decapitated flies "did not induce any walking" with non-walking DNs, which shows the pre-stimulus state is rest.
  - Pugliese et al. say DNg100 "initiates forward walking, even in headless flies".
- **`not_assessed`:** Used in two cases:
  - Air-stepping, because there is no substrate and so no speed (Fig. 4g-i: 0033-0036).
  - Head-intact flies (Extended Data Fig. 7e). Those flies can walk on their own, and only the velocity during the light was reported.
- **`turns`:** Used for unilateral stochastic activation (Fig. 3g / Extended Data Fig. 5).
- **Co-activation siblings (0025 DNg100 and 0026 DNg16, ball):** Both are coded `speeds`, as the experiment's outcome measured against rest.
  - Measured against DNg100 alone there was no speed-up (a slight decrease). This is stated in the notes of both records.
  - A reader who codes against the DNg100-alone control would choose `none`. This is the least certain decision.

## Other uncertainties
- **DNb08 (adj-dedicated-0002):**
  - The text does not say whether the quantified trials were on the ball or with the ball removed. It says movements were "evoked more reliably when the spherical treadmill was removed", so `headless_surface` = `other`.
  - Hind legs were not reported, so `hind_leg_rhythm` = `not_assessed`.
  - `behaviour_category` = `other`: the authors describe searching-like oscillations, not walking.
- **Line specificity:**
  - **SS70620 (DNb08):** coded `unknown`. The kit lists it as DNb08 only (quality B), but the paper makes no specificity statement.
  - **Sapkal single-DN lines (DNg100, DNg97):** coded `clean`, because the authors call them "highly specific split-Gal4 reagents".
  - **hsFlp stochastic DNg100:** coded `minor_offtarget`. The Extended Data Fig. 5 IHC counts "non-DNg100 cell types" per fly, but does not name them.
- **0021 (intact flies):** Leg rhythms are coded `yes` because forward velocity during activation was reported. The supporting quote is weak: it only says head-intact flies were tested. Confidence is medium.
- **0019 (leg removal, hind legs):** `yes`, inferred from hind-leg (i3-c3) coupling being quantified. The legend does not state outright that the hind legs stepped.
- **0001:** The DNg100 genotype was taken from the PMC version (VT058557-GAL4.AD; R85F12-GAL4.DBD).
- No proposed synonyms or driver lines; all names mapped through `type_list.csv` and `synonyms.csv` at high confidence.
