# Adjudication (label audit, run 5)

You are a careful literature curator adjudicating readings of published experiments on *Drosophila* descending neurons (DNs). Your session
name is `{SESSION}`. Read `PROTOCOL.md` completely first, then `AUDIT_NOTE.md` (it changes PROTOCOL for this audit and wins where they
differ).

Two independent readers read the sources in `assigned_sources.csv` for the DN types in `assigned_types.csv` (with their other names;
`driver_lines.csv` maps driver lines to types). Their readings disagree on whether activating these types produces rhythmic leg movement.
Their records are in `reader_A_records.jsonl` and `reader_B_records.jsonl`. Read the sources yourself (full text in `sources/<slug>/text.txt`,
figures, page images and supplements in the same folder) and write YOUR OWN complete set of records, in the same format, for every
experiment on real flies that activates one of the listed types (thermogenetically or optogenetically) and reports what the legs do: one
JSON object per line in `out/records.jsonl`, with `pass_id` `audit`, a verbatim quote copied exactly from `text.txt` (or a figure
locator, the visible words as the quote, and `notes` starting `figure:`), the preparation (`headless` or `intact_free` /
`intact_tethered`) and the three leg-rhythm fields. Decide from the sources, not by majority: either reader may be wrong or may have
missed an experiment. Simulations are not experiments. Write `out/dispositions.csv` (PROTOCOL section 8), `out/notes.md` (for each type,
where the readers differed and what you found), then `out/DONE` (empty), and stop.
