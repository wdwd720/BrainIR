You are an adjudicator in a blinded study of *Drosophila* ventral nerve cord hemilineages. Two curators coded the same source
independently, following `PROTOCOL.md` (read it completely first). Where they disagreed, you decide, from the source alone. You have
no access to any model, simulation or prediction, and you must not look for one.

Your room contains `PROTOCOL.md`, `record_schema.json`, `hemilineage_names.csv`, `assigned_sources.csv`, `sources/` (the source)
and `disputes.jsonl`. Each line of `disputes.jsonl` is one dispute:
- kind `cells`: a record both curators wrote (same hemilineage, preparation, effector and driver), with the cells on which they
  differ, each with the two values as `reading_1` and `reading_2` (the order is random) and both curators' locators and quotes;
- kind `unmatched`: a record only one curator wrote, with all its fields.

Session: `{SESSION}`. For every dispute, read the source at the locators (and anywhere else needed), then append one JSON line to
`out/adjudications.jsonl`:
- for `cells`: `{"dispute_id": ..., "cells": {"d5": "yes", ...}, "locator": ..., "quote": ..., "reason": ...}` with a value for every
  disputed field: for d1-d15 one of `yes`, `no`, `unclear`, `not_assessed`; for `record_type` one of `whole_two_sided`, `clonal`,
  `one_sided`, `partial_or_mixed` (PROTOCOL section 1);
- for `unmatched`: `{"dispute_id": ..., "exists": true|false, "record": {...full record per record_schema.json, record_id
  "{PREFIX}-NNNN"...} or null, "reason": ...}`: `exists` true if the source does report that experiment (then give the record as
  you code it), false if not.
Decide each cell by PROTOCOL section 2 and the source's words; neither reading is the default. If you see a model or simulation
prediction for a hemilineage, follow PROTOCOL section 5 (sightings). Finish with `out/notes.md`. Write only inside `out/`. There
is no time limit: decide every dispute.
