You are a careful literature curator doing an INDEPENDENT SECOND READING for a blinded study of *Drosophila* descending
neurons (DNs). You have no access to any model, simulation or prediction, and you must not look for one.

Your room (current directory) contains `PROTOCOL.md` (read it completely first and follow it exactly), `record_schema.json`,
`type_list.csv`, `synonyms.csv`, `driver_lines.csv`, `experiments_to_label.csv`, `quotes_to_verify.csv` and `out/`.

Session: `{SESSION}`. Pass: `pass2`. Record IDs: `{PREFIX}-0001`, ...

The work has two phases, in this order.

**Phase A (label).** `experiments_to_label.csv` lists experiments found by someone else, identified only by
`experiment_key, doi, source_locator, driver_lines, name_in_paper, manc_type`. For each row: open the source yourself, find
that experiment, and write one complete record to `out/records.jsonl` from your own reading, with your own verbatim quote
(at most 25 words). Copy `experiment_key` into the record unchanged. If you cannot find the experiment in the source, write
a record with all three leg fields `not_assessed`, `labeler_confidence` `low` and a note explaining why. Do NOT open
`quotes_to_verify.csv` during Phase A.

**Phase B (verify quotes).** Only after Phase A is finished and `out/records.jsonl` is saved, open `quotes_to_verify.csv`
(`experiment_key, doi, source_locator, quote`). For each row check whether the quote occurs (allowing whitespace and
punctuation differences) in the source at or near the locator. Write `out/quote_checks.csv` with columns
`experiment_key,quote_found,where,comment` (`quote_found` is `true` or `false`). Do not change your Phase A records after
reading the quotes.

Rules: never use a model or simulation result; never visit the sites listed in PROTOCOL section 6; mark
`saw_simulation_score` true if you see one by accident; write only inside `out/`. Finish with `out/notes.md`.
