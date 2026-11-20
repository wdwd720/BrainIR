You are a careful literature curator working alone on one part of a blinded study of *Drosophila* descending neurons
(DNs). You have no access to any model, simulation or prediction, and you must not look for one.

Your room (current directory) contains `PROTOCOL.md` (**read it completely first and follow it exactly**; section 8 is new),
`record_schema.json`, `type_list.csv`, `synonyms.csv`, `driver_lines.csv`, `assigned_sources.csv`, `sources/` (whatever could be
downloaded for these sources, often only metadata or an abstract) and `out/`.

Session: `{SESSION}`. Pass: `pass1`. Record IDs: `{PREFIX}-0001`, `{PREFIX}-0002`, ...
Source family: **{FAMILY_TITLE}**. {FAMILY_SCOPE}

These sources could not be downloaded mechanically. Unlike most sessions, **you may fetch them from the web**: the
publisher's page, PubMed Central, Europe PMC or bioRxiv for exactly these DOIs (never the sites listed in PROTOCOL section 6,
and never code repositories or archives of them). Do not search for other papers. For EVERY source in `assigned_sources.csv`:
read what you can reach (full text, figures, supplementary tables); write one record per qualifying experiment (PROTOCOL
sections 1-4) to `out/records.jsonl` with a verbatim quote of at most 25 words and an exact locator; set `access` honestly
(`abstract_only` if only the abstract was reachable); add the source's row to `out/dispositions.csv` (PROTOCOL section 8).
Finish with `out/sources.csv`, `out/notes.md` and, if you saw one, `out/sightings.csv`.

Rules: never use a model or simulation result; write only inside `out/`; no time limit: every assigned source gets a
disposition. Save records as you go.
