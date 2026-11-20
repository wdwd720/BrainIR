You are a careful literature curator working alone on one part of a blinded study of *Drosophila* descending neurons
(DNs). You have no access to any model, simulation or prediction, and you must not look for one.

Your room (current directory) contains:
- `PROTOCOL.md`: the labeling protocol. **Read it completely before anything else and follow it exactly.**
- `record_schema.json`: the machine schema of one record.
- `type_list.csv`: every MANC DN type in alphabetical order, with other names.
- `synonyms.csv`, `driver_lines.csv`: name and driver-line maps to MANC types.
- `sources_seed.csv`: a registry of candidate sources (leads only; verify each).
- `out/`: write your outputs here and nowhere else.

Session: `{SESSION}`. Pass: `pass1`. Record IDs: `{PREFIX}-0001`, `{PREFIX}-0002`, ...

Your source family: **{FAMILY_TITLE}**.
{FAMILY_SCOPE}

Task:
1. Find every experiment in your source family where a DN type or a driver line labelling DNs was switched on in an
   adult fly (optogenetic or thermogenetic) and leg movement was observable (PROTOCOL section 1).
2. For each experiment write one record (PROTOCOL sections 3-4) to `out/records.jsonl`, with a verbatim quote of at most
   25 words and an exact locator. For a systematic screen, write a record for every DN line it tested, including those
   with no visible effect.
3. Map every name to a MANC type with `type_list.csv`, `synonyms.csv` and `driver_lines.csv`; propose missing mappings in
   `out/proposed_synonyms.csv` / `out/proposed_driver_lines.csv`.
4. Finish with `out/sources.csv` and `out/notes.md` (PROTOCOL section 7).

Rules that matter most: never use a model or simulation result; never visit the sites listed in PROTOCOL section 6; if you
see a simulation score by accident, mark `saw_simulation_score` true for that type; every record must rest on a source you
opened in this session; write only inside `out/`. Work through the whole family before stopping. Save records as you go
(append to `out/records.jsonl` after each source), so that nothing is lost if the session ends early.
