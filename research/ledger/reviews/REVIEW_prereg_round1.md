# Independent review of Stage 0, round 1 (before the prereg freeze)

Reviewer: a fresh subagent that did not write the code; read-only; reviewed at `76a451e` (PREREG, labels, scoring and kit
unchanged since `2938fdc`). Probe scripts were kept in the orchestrator's scratchpad. Verdict: **do not freeze yet**.
Findings (condensed from the report; each is resolved in the commit that follows, see `RESOLUTION_prereg_round1.md`).

## Blockers
1. **Experiment keys collide** (`schema.experiment_key` = doi|locator|lines|name). PROTOCOL itself requires several records
   with the same key (headless and intact of one line, one record per condition, one per DN type of a multi-type line);
   every consumer keeps the first record per key, so records are lost or overwritten (shown: the second type of a two-type
   line never reaches pass 2; an adjudication turned an intact "no" into a headless "yes"; identical passes agree 0.5).
2. **The one-shot scoring run can crash or silently drop analyses**: one non-finite score aborts the run before anything is
   written; missing arms/columns silently skip analyses; §8 item 10 always empty (A1 has no frequency); item 8 has no code;
   no end-to-end test of the secondary branches.
3. **Exposed list in code contradicts PREREG §2** ("a name that maps to several MANC types exposes all of them"): the code
   skipped the synonym map when the name is itself a MANC type; DNg12, DNp09 and DNa01 also appear as names of DNfl028,
   DNp71 and DNxl022, which are therefore exposed under the written rule.
4. **Driver-line map empty in the frozen kit; mapping never checked independently**: ambiguous names mapped to the
   alphabetically first type without a flag (137 synonym names map to several types; 84 type names are synonyms of other
   types); pass 2 is handed pass 1's `manc_type`, and `manc_type` is not a compared field, so the join key is read once.

## Major
5. Merge copies only disputed fields: dependent fields (preparation/surface) split, pass 1's confidence carried onto an
   adjudicated reading, a pass-2/adjudicator "saw a score" not propagated, merged records not re-validated.
6. Guard does not check the scored bytes: `score_tables` runs without a flag; inputs not hashed against the locks;
   type labels not recomputed from records; missing `quote_verified` treated as verified; flag paths unconstrained;
   `LOCK_labels`/`UNBLIND.json` formats undefined in PREREG.
7. Consensus order gives surprising labels (a low-confidence abstract-only headless "yes" beats three high-confidence clean
   intact "no"; a multi-DN headless line beats a clean intact line; a clean headless "unclear" is discarded). Suggested:
   drop low-confidence when better exists; drop multi-DN when other records exist; then tier preparation, specificity over
   yes/no/unclear; unanimous yes/no -> label, else unclear/conflicting.
8. Open decisions that would otherwise be made with outcomes in view: dedicated pass 2 / adjudication for the two banned
   sources; repair of invalid records; handling of audit breaches and of sessions that saw scores; recording of the
   model actually used (fallback); the G2 "investigate" remedy; the orchestrator viewing only aggregate label counts.
9. "Adds value beyond wiring" not gated on "the model predicts"; baseline tie-break undeclared; permutation p's role.
10. Labelers' web exposure: the owner's GitHub handle named in PROTOCOL; subdomain coverage of the deny rule unverified;
    WebSearch not blocked; the predictions would be pushed before Stage 2; labelers are language models that may have read
    the preprint in training; audit treats `~` / `..` paths as inside the room.

## Minor
Status tie rule text vs code; wrong protocol section reference; search-only records and the capture-recapture definition;
pass-2 "not found" would need an invented quote; numeric fields with ranges invalidate records; `expression` lacks
`unknown`; schema lacks cross-field rules; `quotes_to_verify.csv` present during Phase A; validator echoes label values;
stop call tiering by preparation regardless of stop information; B4 "halts" with one background-rhythmic replicate; phase
lag range text; LOG L15 omissions; no assertion on A1's type names.
