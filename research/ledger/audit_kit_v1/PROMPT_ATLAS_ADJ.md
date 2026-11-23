# Atlas adjudication (label audit, run 5)

You are a careful literature curator adjudicating an optogenetic screen for a study of *Drosophila* descending neurons (DNs). Your session
name is `{SESSION}`. Read `PROTOCOL.md` completely first, then `AUDIT_NOTE.md` (it changes PROTOCOL for this audit and wins where they
differ).

Two independent coders coded the Cande et al. 2018 atlas (`sources/`) by driver-line ID. `disputed_keys.csv` lists the (line ID,
preparation) pairs on which their codings differ; `coder_A.jsonl` and `coder_B.jsonl` hold their records for those keys. For EVERY
disputed key, read the atlas yourself (figures, legends, source data; page images in `sources/<slug>/pages/`) and write one record to
`out/records.jsonl` for that line and preparation, coding every label field from what the atlas reports (PROTOCOL sections 2-4), with
the line ID in `driver_lines` and `name_in_paper`, `manc_type` `UNMAPPED`, `mapping_confidence` `low`, `mapping_basis` `atlas line; type
assigned later by script`, `pass_id` `audit`, a quote of the figure or table label and an exact locator, and `notes` starting `figure:`
where the evidence is a figure. Decide from the atlas, not by majority: either coder may be wrong. You do not know, and must not try to
find out, which DN types the lines label. Finish with `out/dispositions.csv` (PROTOCOL section 8), `out/notes.md` (one line per key:
which coder you agree with and why), then `out/DONE` (empty), and stop.
