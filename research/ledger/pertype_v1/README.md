# Per-type tables (run 5, Stage 0; RUN5_PROMPT section 4)

One tidy table per screen, made by `ledger/scripts/pertype_v1.py` from locked files (and, for Part A's half-fly screens, from the
replicate results whose summary statistics run 4 locked). `VERIFY.json` shows that each table reproduces the locked aggregate it came
from exactly: A0_copies.csv gives `reliability_v2/A0.json` (both comparisons, point estimates and bootstrap intervals); the four
half-fly tables give `reliability_v2/A.json`'s six agreements (primary and all matched types); B1r/B2r/A1 equal the locked
`types.csv` scores (to the 10 significant digits the CSV prints), bands, usable counts and member counts; match_confidence.csv reproduces the B2 arm's locked mapping counts.

- Type score: mean score over usable replicates, 0 if none (G5). `score_h1` / `score_h2`: the same on the two halves of the seeds
  (A0: replicates 0-63 / 64-127). Band: driver >= 0.5, non_driver < 0.05, else indeterminate.
- Sides and member counts: A0 by the full-cord root side (as Part A0); the half-fly and whole-type tables by G3 (MaleCNS sides are
  output sides, PREREG v4 G3). `members_other` counts members with no L/R side.
- `cross_fly_match`: the confidence of the MaleCNS -> MANC type match (match_confidence.csv; rule in MANIFEST.json and LOG L160):
  high = all members body-matched, no conflict with the `mancType` string, one-to-one naming; low = any conflict; medium = the rest;
  none = no MaleCNS group for this MANC type.
- `primary_run4` / `type_primary_run4`: run 4's primary (homolog-consistent) type set (`gates_v4/TYPE_SETS.json`).
