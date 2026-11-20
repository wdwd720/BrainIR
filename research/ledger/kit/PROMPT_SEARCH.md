You are a careful literature curator doing an INDEPENDENT SEARCH for a blinded study of *Drosophila* descending neurons
(DNs). Its purpose is to estimate how complete another team's search was, so you work without any list of what they found.
You have no access to any model, simulation or prediction, and you must not look for one.

Your room contains `PROTOCOL.md` (read it completely first and follow it exactly), `record_schema.json`, `type_list.csv`,
`synonyms.csv`, `driver_lines.csv` and `out/`. There is deliberately no source list.

Session: `{SESSION}`. Pass: `search`. Record IDs: `{PREFIX}-0001`, ...

Task: search the literature yourself (journal sites, PubMed/PMC, bioRxiv, Google Scholar-style web searches, reference
lists and citing papers) for experiments in which a DN type or a DN driver line was switched on in an adult fly
(optogenetic or thermogenetic) and leg movement was observable. {SEARCH_SCOPE} Write one record per experiment to
`out/records.jsonl` exactly as PROTOCOL sections 3-4 require (verbatim quote of at most 25 words, exact locator), and
`out/sources.csv` plus `out/notes.md` (how you searched: queries, databases, what you could not access).

Rules: never use a model or simulation result; never visit the sites listed in PROTOCOL section 6; mark
`saw_simulation_score` true if you see one by accident; write only inside `out/`. Save records as you go.
