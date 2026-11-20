Phase B (quote verification). Your Phase A records are saved; do not change `out/records.jsonl` or `out/not_found.csv`
from now on.

A new file is now in your room: `quotes_to_verify.csv` with columns `exp_id, doi, source_locator, quote` (quotes written by
the first reader). For each row, check in the local copy of the source (`sources/`) whether the quote occurs at or near the
locator (allow differences in whitespace, punctuation, line breaks and ligatures; do not allow different words). Write
`out/quote_checks.csv`, a CSV file whose first line is the header `exp_id,quote_found,where,comment`, where `quote_found` is
exactly `true` or `false` and `where` names the place you found it (or where you looked). Same rules as before: no model or
simulation results, no banned sites, write only inside `out/`.
