# Addendum: answer to the third overclaim review of the brief (`BRIEF_OVERCLAIM_REVIEW_3.md`)

**The review.**
- **Who wrote it.** A fresh reviewer: a newly started agent on the default model, not a fork of the orchestrating session.
- **What it was given.** The files to read, a read-only instruction and the brief's rules, including the two-page limit, so that
  every suggested wording had to keep the brief the same length or shorter.
- **What it reviewed.** The final two-page brief (`BRIEF.md` at 70329c9). No file it read was changed while it worked.
- **Commit.** It wrote its report once, at the end. The report is committed once, unchanged (cde9bc5).
- **Result.** Every number in the brief matches its source. It marked 3 items and listed observations that did not meet its marking
  tests.

This file is the answer (RUN4_PROMPT hard limit 6).

## Items

1. **"The 15 where they disagree most" was wrong.** Accepted, and confirmed from `forward/LEDGER.csv`.
   - The pre-registered rule E6 ranks only types whose stability flags read `agree` for both sources on both flags (sides and flies).
   - 20 of the 63 types qualify, and `forward/DECISIVE.csv` is exactly the top 15 of those 20.
   - Over all 63 types, the two largest gaps are DNg35 (0.305) and DNa13 (0.296). Both are excluded because the authors' model's
     two-fly flag reads "disagree".
   - The brief now reads: "Of the 20 types stable across sides and flies, the 15 most divergent, by only 0.05-0.28".
   - The same restriction is now stated in RESULTS_3 section 6, handoff section 9 and evidence-map row 24.
   - All earlier versions of the brief had the same error, and the two earlier reviewers did not mark it.
2. **Block 1 in MANC.** Accepted, with the reviewer's wording: "...closes 0.36 of the gap in MaleCNS (0.08-0.61), partly by lowering
   seed noise (...), but not demonstrably any in MANC."
   - This corrects `BRIEF_OVERCLAIM_ADDENDUM_2.md` section 4, which listed the first review's item 8 as kept after the two-page cut
     had removed the words that kept it.
3. **Block 3 closures side by side.** Accepted. The sentence now ends "none suffices (the classes interact)".
   - This also completes the first review's item 11, which section 4 of addendum 2 listed as kept although it held only in part.

## Observations adopted (at no cost in length)

- **The ask's order.**
  - It now reads "feed all-trans-retinal, decapitate", as in the locked protocol (`forward/DECISIVE.csv` `protocol`).
  - The earlier order was a slip: a decapitated fly cannot feed.
- **"No fix passed"** replaces "No fix worked", matching C6.
- **The figure caption** now says what the wiring points are: "wiring = type-level two-hop sums". The figure's own legend gives the
  colour key. Addendum 2 section 4 had claimed the caption gave the wiring points' scale; that held only in part, and this completes it.
- **"Amendments are recorded in `AMENDMENTS_v4.jsonl`"** replaces "Departures are recorded". The file holds the amendments; the
  departures from the prompt are in the handoff, section 2.
- **"Causes and fixes: a subset"** replaces "a budget-cut subset". Only the analysed set's random part was cut for budget (41 to 25);
  its informative part (237 types) is complete.

## Not adopted

- **The B4.5 difference itself.** Result 3 still states only the pre-registered verdict, and keeps "almost as much" and the post-hoc
  qualification that the reviewer found sufficient.
- **The four non-driver types mapped above the base rate** (scores 0.01-0.04, probabilities 0.68-0.72). "None is a driver (highest
  0.13)" gives the reader what is needed, as the reviewer notes.
- **Result 1's type set** (250 types with one member per side). It nearly coincides with the homolog-consistent set. The evidence map
  names the field.

## Length

The brief prints to 2 pages (`ledger/scripts/posthoc/brief_pages_v4.py`: "pages: 2"), with the figure embedded and about five lines to
spare. Both pages were rendered and inspected after these changes.
