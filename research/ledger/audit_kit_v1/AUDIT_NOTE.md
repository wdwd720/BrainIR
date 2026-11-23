# Audit note (label audit, run 5): what changes from PROTOCOL.md

This task is an **audit** of an earlier label collection. Both earlier exams are finished, so the rules that kept earlier readers
away from simulation results do not apply. Where this note and `PROTOCOL.md` differ, this note wins.

- **Sections 1-4 of PROTOCOL.md apply as written:** what counts as a record, what "rhythmic leg movement" means, the coding
  conventions, the fields and their vocabularies. Section 8's "Local sources" and "Session contract" also apply.
- **Section 5 (sources and access):** read only the sources assigned to you (`assigned_sources.csv`). Do not search for others.
  Proposed synonyms or lines may still go into `out/proposed_synonyms.csv` / `out/proposed_driver_lines.csv`.
- **Section 6, first and second bullets, and section 8's "Score sighting" do NOT apply.** You may read every assigned source in
  full, including the papers that report connectome simulations and their scores. Do not stop reading when you see a score.
  Still fill `saw_simulation_score` truthfully (`true` if you saw a simulation score, rank or driver call for that type), but
  record only what experiments on real flies show; a simulation result is never evidence for a record.
- **Section 6, third and fourth bullets, still apply:** never use your own memory of what a neuron does as evidence (every record
  rests on a source in this room, with a quote), and write files only inside `out/`.
- **Quotes:** copy the quote character for character from `text.txt` (at most 25 words). If the result is visible only in a figure,
  a page image or a supplementary file, give its locator, put the visible words in `quote`, and start `notes` with `figure:`.
- `pass_id` = `audit`; `session` = the session name in your task; `record_id` = `<session>-0001`, `<session>-0002`, ...
