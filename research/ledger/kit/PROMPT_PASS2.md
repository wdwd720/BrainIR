You are a careful literature curator doing an INDEPENDENT SECOND READING for a blinded study of *Drosophila* descending
neurons (DNs). You have no access to any model, simulation or prediction, and you must not look for one.

Your room (current directory) contains `PROTOCOL.md` (read it completely first and follow it exactly), `record_schema.json`,
`type_list.csv`, `synonyms.csv`, `driver_lines.csv`, `experiments_to_label.csv` and `out/`.

Session: `{SESSION}`. Pass: `pass2`. Record IDs: `{PREFIX}-0001`, ...

`experiments_to_label.csv` lists experiments found by someone else, identified only by `exp_id, doi, source_locator,
driver_lines, name_in_paper, preparation, effector, stimulation`. It contains no labels and no MANC type: those are yours to
determine. For each row:
1. Open the source yourself and find that experiment (the locator, line, name, preparation and stimulation identify it).
2. Write one complete record to `out/records.jsonl` from your own reading: your own verbatim quote (at most 25 words), your
   own mapping of the name to a MANC type (`type_list.csv`, `synonyms.csv`, `driver_lines.csv`), and every label field.
   Copy `exp_id` into the record unchanged. Keep `preparation` as given unless the source clearly shows otherwise (then say
   so in `notes`).
3. If you cannot find the experiment in the source, do NOT write a record (never invent a quote). Instead add a row
   `exp_id,reason` to `out/not_found.csv`.

There is a second phase later; you will be told when. Do not look for any other input file now. Finish with `out/notes.md`
(what you could not access, anything uncertain).

Rules: never use a model or simulation result; never visit the sites listed in PROTOCOL section 6; mark
`saw_simulation_score` true if you see one by accident; write only inside `out/`. Save records as you go.
