# pass2-steering: notes (independent second reading)

All 14 rows in `experiments_to_label.csv` were found in their sources; 14 records written and none in `not_found.csv`.
I saw no model or simulation scores (`saw_simulation_score` = false everywhere). I did not visit GitHub, Zenodo or the excluded papers.

## Access
- **eLife 102230 (Rayshubskiy et al.)**: the elifesciences.org page failed to load, so I read it via PMC12279373. The fetch tool refused to return full long sentences, so the quote is a fragment I confirmed in two separate fetches.
- **Cell 2024 (Yang et al.)**: cell.com returned 403 and the PMC page hit a captcha. I read it via Europe PMC `fullTextXML` and confirmed the quotes verbatim.
- **Current Biology 2017 MDN (Sen et al.)**: cell.com, ScienceDirect and the PDF all returned 403, PubMed was blocked and there is no PMC copy. The record is **abstract-only** (confidence low). Effector, light, n, turn direction and figure were not visible. `effector_kind` = optogenetic is unverified: it comes from a search-engine summary, not from the source.
- **bioRxiv 2024.06.27.601106 (Feng et al.)**: I read both v1 and v2 (v2, May 2026, retitled "Hierarchical Transformation of Navigational Variables into Coordinated Turning"). Supplementary Table 1 (genotypes), the supplementary videos and the separate supplementary figures were not accessed.
- **bioRxiv 2025.07.22.666129 (Dahlhoff et al.)**: read the v1 full text. The abstract mentions computational models; I deliberately asked only about experimental content and did not read the modelling parts. The published version (Curr Biol 2026, 10.1016/j.cub.2026.06.045) was not opened.
- bioRxiv rate-limited many requests (HTTP 429). All of them eventually succeeded.

## Uncertainties and judgment calls
- **Version and figure numbers (Feng et al.)**: the pass1 locators "Fig. 5a-c" and "Fig. 5d-k" match v1. In v2 the same panels are Fig. 6. Supplementary Fig. S14e-h (DNa06) exists only in v2. Line IDs SS84990/SS96514 (DNa03), SS94676 (DNae003) and SS77821 (DNa11) are confirmed only in v1 Supplementary Fig. 2. They are added to `proposed_driver_lines.csv`. I could not tell which DNa03 line was used for Fig. 2c.
- **DNae003 → DNxn123**: via the kit's flywire/malecns synonym (one type, not ambiguous).
- **DNp17 (SS02553)**: the kit lists this name as ambiguous (DNp17 vs DNut046). The paper's anatomy (6 cells per hemisphere, wing/haltere neuropils) did not settle it. I chose the exact-name match DNp17 at medium confidence. The line labels 7 non-DN types (including the dopaminergic DopaMeander). The authors conclude that DopaMeander, not DNp17, drives the forward-walking and turning phenotype. So the whole-line record (p2-steering-0013, speeds/forward walking) should not be read as a DNp17-specific effect. For the SPARC2 record (p2-steering-0014) I coded no_visible_effect/none at low confidence. That is an interpretation: in the text I read, DNp17-only flies were not statistically compared with no-expression controls.
- **DNa11 leg rhythm (p2-steering-0009/0010)**: coded `yes` because all six legs were tracked stepping during activation and the Discussion says DNa11 "can simultaneously initiate stepping". I could not confirm that flies were standing at light onset, so confidence is medium. The amputation record keeps preparation `other`.
- **Headless DNa11 (p2-steering-0011)**: the text does not state the surface (the video was not viewed). `headless_surface` = `other` is a placeholder only to satisfy the schema; it is probably the ball, but unverified. Legs are `unclear`.
- **DNa06 (p2-steering-0012)**: the main effect is head/neck turning with minimal body turning. Coded behaviour `other` and effect_on_walking `none`, legs not_assessed. No driver line ID was found in the text.
- **Turning experiments on the ball (DNa02, DNa03, DNae003, DNa11 Fig. 2c)**: flies were already walking, so the leg-rhythm fields are `not_assessed` by convention.
- **Sex**: Feng et al. say "In most of the experiments, only females were used", so I coded `unknown`. Dahlhoff et al. do not state sex for the activation experiments.
