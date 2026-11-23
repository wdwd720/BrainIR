# Reading task (label audit, BrainIR prediction ledger run 5)

You are a reader in a fresh session. This folder (your room) is all you may use. Read only the files in it; do not try to reach anything
outside it. You have no shell, and no web unless the end of this task says otherwise.

**Your task.** For each descending-neuron (DN) type listed in `assigned_types.csv` (each with its other names; `driver_lines.csv` maps driver lines to types), read every source in
`assigned_sources.csv` (full text in `sources/<slug>/text.txt`, page images in `sources/<slug>/pages/`, figures in
`sources/<slug>/figures/`, supplements in `sources/<slug>/supp/`) and find every experiment that **activates** that type
(thermogenetically or optogenetically, through a driver line or otherwise) and reports what the legs do. For each such experiment write
one record. Some sources report computer simulations; a simulation is not an experiment: record only experiments on flies. You may read
everything in these sources, including simulation results; they do not make a record invalid here.

The large optogenetic atlas of Cande et al. 2018 is coded separately; if it is not among your sources, do not look for it.

**Record format.** One JSON object per line in `out/records.jsonl`, using the field names and vocabularies of `record_schema.json` and the
conventions of `PROTOCOL.md` as changed by `AUDIT_NOTE.md` (read both first; the note wins where they differ). At least these fields: `doi`, `source_locator` (section, figure or page), `quote` (the exact
words from `text.txt` that state the result; copy them exactly), `name_in_paper`, `manc_type` (from `type_list.csv` / `synonyms.csv`),
`mapping_confidence`, `driver_lines`, `effector`, `effector_kind`, `stimulation`, `preparation` (`headless` if the fly was decapitated,
`intact_tethered` or `intact_free` otherwise), `line_specificity`, `other_cell_types`, `front_leg_rhythm`, `middle_leg_rhythm`,
`hind_leg_rhythm` (each `yes`, `no`, `unclear` or `not_assessed`, as PROTOCOL sections 2-3: does activation produce rhythmic stepping of those legs?), `effect_on_walking`,
`labeler_confidence`, `saw_simulation_score`, `notes`. If the result is stated only in a figure or page image, give the figure and
page in `source_locator`, put the visible words in `quote`, and start `notes` with `figure:`. Write separate records for headless and
intact flies when a source tests both. If a source mentions the type but reports no such experiment, write no record for it.

**Dispositions.** Write `out/dispositions.csv` with the header `doi,disposition,n_records,reason`, one row per assigned source,
`disposition` one of `records`, `no_qualifying_experiment`, `unreachable` (the text is missing or unreadable). Your session name is
`{SESSION}`.

Work carefully and completely; there is no time limit. When every source has a disposition, write `out/DONE` (empty) and stop.
