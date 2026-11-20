# Adjudication notes — session `adjudication-general`, pass `adjudication`

## Scope
`disagreements.csv` lists 26 experiments from 12 sources (42 disputed field rows). I adjudicated **23 experiments (33 field rows)**.
Each one has a record in `records.jsonl` and decision rows in `decisions.csv`.
**3 experiments (9 field rows) are NOT adjudicated**. See "Unresolved" below.

Record IDs follow the order of the experiments in `disagreements.csv`. IDs `adj-general-0018`, `-0024` and `-0025` are
reserved for the three unresolved DNa11 experiments, so the numbering has gaps.

## Unresolved: DNa11, Feng et al. bioRxiv 10.1101/2024.06.27.601106
- Experiments: `pass1-recent_broad:p1-recent_broad-0024`, `pass1-steering:p1-steering-0008`, `pass1-steering:p1-steering-0009`
  (disputed: front/middle/hind_leg_rhythm, `yes` vs `not_assessed`).
- bioRxiv returned HTTP 429 (rate limit) on every attempt over the whole session: v1 .full, .full-text, .full.pdf, v2
  .full and the JATS source XML. The Europe PMC preprint full text (PPR875582) returned HTTP 500, and ResearchGate
  returned 403.
- A web-search result snippet gave a second-hand summary (single remaining leg stepping after amputation). I did **not** use it.
  It is not the source text, and the protocol requires a source I opened plus a verbatim quote. So I wrote no records
  and no decisions for these three experiments. They should be re-run when bioRxiv access works.
- Points to check when re-run: whether flies were walking before light onset (if so, the leg fields would be
  `not_assessed` under the turning/speed-change convention), and what Fig. 5d-k / Suppl. Fig. 10 report for each remaining
  leg after amputation (`preparation` = `other`).

## Key judgement calls
- **DNp09 (Zacarias 2018):** activation caused freezing in 61.5% of trials. A brief DNp09-induced running bout came first,
  which is a speed change in flies already moving. I applied the stopping/freezing convention and set legs to `no` and
  `effect_on_walking` to `stops`, with confidence `medium`. Running and jumping are noted as secondary behaviours. Readers
  had split `unclear`/`no`.
- **P2b (Kohatsu 2011):** paywalled and not in PMC, so abstract only. The abstract describes courtship acts but not the legs,
  so the legs are `not_assessed`. `P2b` maps to two kit types (DNxl053, pIP10), and nothing in the abstract chooses
  between them, so `manc_type` is `UNMAPPED`.
- **aDN lines (Hampel 2015):** the text says which aDN each split pair targets but never states whether cells outside the
  aDN set are labelled. The expression-summary panel (Fig. 2-figure supplement 2J) is image-only, and I could not open the
  image files. So `line_specificity` = `unknown` for all six. If someone can read panel J, this may change.
- **VT50660-GAL4 (Israel 2022):** the paper calls it "the broad MDN driver" in contrast to "the more specific split-GAL4,
  MDN3-GAL4". I coded VT50660 as `minor_offtarget`, with the other cells marked "unnamed" because the paper names none.
  MDN3-GAL4 is `unknown`: "more specific" is only relative.
- **Carreira-Rosario 2018:** both adult intersections show named off-target labelling (Fig. 8F projection; Fig. 8H
  "four off target neurons"), so both are `minor_offtarget`.
- **DNp17 (Dahlhoff 2025):** SS02553 labels seven or eight non-DN types, and the paper attributes the walking phenotype to
  DopaMeander. For the bilateral experiment (Fig. 2), activation increased locomotion with no leg tracking, so the legs are
  `yes` at `medium` confidence. For the SPARC experiment (Fig. 3), DNp17-labelled flies without DopaMeander were never
  compared with no-expression flies. So the legs are `unclear` and `effect_on_walking` is `not_assessed`, not `none`.
- **DNa02 (Yang 2024, Rayshubskiy 2025):** both papers report off-target expression (lobula visual neurons and abdominal
  ganglion cells; optic lobe and VNC types), so all three experiments are `minor_offtarget`.
- **DNg100 headless (Ispizua 2026):** "reliably elicited sustained running bouts" and "The fly speeds up" give
  `effect_on_walking` = `speeds`. `headless_surface` = `other` (free, glass-floored chamber). n is not stated.
- **MDN (Lee/Doe 2026; DeepFly3D 2019):** neither source states anything about driver specificity, so both are `unknown`.

## Other
- `out/proposed_synonyms.csv` and `out/proposed_driver_lines.csv` were not needed.
- I saw no model, simulation or prediction score for any DN type (`saw_simulation_score` = false throughout). I did not
  open Pugliese 2026, Sapkal 2026, GitHub or Zenodo.
- Quotes came from WebFetch extraction of the full text, which enforces short-quote limits. Some quotes are sentence
  fragments, kept verbatim.
