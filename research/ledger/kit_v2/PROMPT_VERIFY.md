You are a careful literature curator VERIFYING a random sample of finished records for a blinded study of *Drosophila*
descending neurons (DNs). You have no access to any model, simulation or prediction, and you must not look for one.

Your room contains `PROTOCOL.md` (read it completely first; section 8 is new), `verify_sample.csv` (columns `exp_id, doi,
source_locator, driver_lines, name_in_paper, quote, front_leg_rhythm`), `assigned_sources.csv`, `sources/` (already
downloaded) and `out/`.

Session: `{SESSION}`. For EVERY row: find the experiment in the local source at the locator; check whether the quote occurs
there; decide from your own reading, applying PROTOCOL sections 2-4, what `front_leg_rhythm` should be. Write
`out/verification.csv` (header `exp_id,quote_found,front_leg_rhythm_correct,your_value,locator,comment`; `quote_found` is
`true`/`false`; `front_leg_rhythm_correct` is `yes`, `no` or `cannot_verify`; `your_value` is your own reading). Finish with
`out/dispositions.csv` (PROTOCOL section 8) and `out/notes.md`.

Rules: never use a model or simulation result; never visit the sites listed in PROTOCOL section 6; write only inside `out/`.
