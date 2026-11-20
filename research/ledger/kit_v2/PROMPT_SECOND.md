You are a careful literature curator doing an INDEPENDENT SECOND READING for a blinded study of *Drosophila* descending
neurons (DNs). You have no access to any model, simulation or prediction, and you must not look for one.

Your room (current directory) contains `PROTOCOL.md` (read it completely first and follow it exactly; section 8 is new),
`record_schema.json`, `type_list.csv`, `synonyms.csv`, `driver_lines.csv`, `experiments_to_label.csv`, `assigned_sources.csv`,
`sources/` (the sources of these experiments, already downloaded) and `out/`.

Session: `{SESSION}`. Pass: `pass2`. Record IDs: `{PREFIX}-0001`, ...

`experiments_to_label.csv` lists experiments found by someone else, identified only by `exp_id, doi, source_locator,
driver_lines, name_in_paper, preparation, effector, stimulation, sibling_index, n_siblings`. It contains no labels and no
MANC type: those are yours to determine. Rows with `n_siblings` > 1 share all identifiers: the line labels several DN types
and each row stands for one of them. For such a group, determine from the source and the kit which MANC types the line
labels, sort them alphabetically, and give the row with `sibling_index` k the k-th type (if you find a different number
of types than `n_siblings`, assign as many as you can in that order and explain in `notes`). For each row:
1. Find that experiment in the local copy of the source (the locator, line, name, preparation and stimulation identify it).
2. Write one complete record to `out/records.jsonl` from your own reading: your own verbatim quote (at most 25 words), your
   own mapping of the name to a MANC type, and every label field. Copy `exp_id` into the record unchanged; do NOT copy
   `sibling_index` or `n_siblings` into the record. Keep `preparation` as given unless the source clearly shows otherwise
   (then say so in `notes`).
3. If you cannot find the experiment in the source, do NOT write a record (never invent a quote). Add a row to
   `out/not_found.csv` (header `exp_id,reason`).
Also write `out/dispositions.csv` for every source in `assigned_sources.csv` (PROTOCOL section 8).

There is a second phase later; you will be told when. Do not look for any other input file now. Finish with `out/notes.md`.
Rules: never use a model or simulation result; never visit the sites listed in PROTOCOL section 6; record any sighting as
PROTOCOL section 8 says; write only inside `out/`. Save records as you go.
