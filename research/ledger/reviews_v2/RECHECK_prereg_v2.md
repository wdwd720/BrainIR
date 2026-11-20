# Re-check of the PREREG v2 fixes (fresh reviewer, 2026-11-20)

Reviewed: the fixes as committed in `c3b4e70`; PREREG and kit were unchanged at the time of writing. `PREREG_v2.md` sha256 `214450934c74658f7eeff75407db3e1cde396c54249b02a9238ce0385099d778`. I opened no label, prediction, data or room file.

**Verdict: freeze after these small fixes.** Each is a sentence or two of text. Item 1 blocks the freeze as written.
1. Limit L3 kind 5 to web results (N1).
2. Give `reader_web` sources a downstream path (N2).
3. Make the atlas key separate headless from intact (N3).
4. Close P2's open branch and store the preview (N4).

Pasted as worded, these need no further text review. The L12 implementation reviewer should check N2's flags, which give web tools back to some second readers and adjudicators.

## First review, finding by finding

- **B1 resolved.** Item 4' is printed; the strict alpha governs and fails (T1R-T2R, p 0.0035). Residue: N4.
- **B2 resolved.** All five kinds, the token rule, the audit timing, the family mapping and the dedupe order are stated.
- **B3 partly.** Done except kind 5, which overshoots (N1).
- **B4 partly.** Done except the key, which contradicts PROTOCOL §1 (N3).
- **B5 resolved.** Frame, seed, blind verifier, script comparison, kappa inputs, word list, run once, no pooling.
- **M1–M2 resolved.**
- **M3 partly.** Partial records are kept while the source is re-read, so near-duplicates escape the exact-signature dedupe. Atlas coders are missing from L3's consequences.
- **M4 resolved.**
- **M5 partly.** The prediction-side v2 code (`typescreen_v2`, `jobs_v2`, `g3v2_evaluate`, `b4v2`) has no rule for changes after the freeze.
- **M6–M9 resolved.**
- **Minors resolved,** except that S5.1 keeps `lock.py check` for the v1 locks, which does not report missing raw files.

## New problems

**N1 (blocker). L3 kind 5 excludes every session.**
- Text: "a tool result whose text contains `wdwd720`, `smpuglie` or `BrainIR`".
- `kit_v2/PROTOCOL.md` §8 ("any BrainIR output") and the title of `record_schema.json` contain `BrainIR`.
- Every prompt orders a read of PROTOCOL.md, and `labels2_audit.scan` tests every tool's result.
- Fix: "5. a WebSearch or WebFetch result, or a read of the session's own tool-results file, containing …; files placed in the room are exempt."

**N2 (major). `reader_web` records cannot pass the second reading.**
- C1 gives second readers, adjudicators and the verifier no web tools, and L8 gives them "the same source files". For these sources that is metadata or an abstract.
- So Phase A writes `not_found`, Phase B finds no quote, and `merge_passes` drops the record. A sampled record would be `cannot_verify`, which counts as an error.
- What sends a source to `reader_web` is unstated, and L13 grants it WebSearch although its prompt forbids searching.
- Fix: "Sources the cache or a reader marks `unreachable` go to `reader_web` (WebFetch only, for those DOIs). Their second reading, Phase B and adjudication use the same flags, and their records are outside the verification frame. A reassigned source's earlier records are dropped."

**N3 (major). The atlas key contradicts PROTOCOL §1.**
- Text: "Key = the line ID … one record per line per coder".
- PROTOCOL §1, kept by L2, makes headless and intact tests of a line two records.
- Keeping "the first `record_id`" lets writing order decide which preparation survives, and headless ranks first in the consensus.
- A and B may then pair different experiments under one `exp_id`, creating false disagreements.
- Fix: key = (line ID, headless or not); `exp_id = atlas:<line>:<headless|intact>:<type>`. Not the exact preparation: coders may differ on intact_free versus intact_tethered.

**N4 (major). P2 leaves a branch undefined.**
- Text: "unless the formal run differs from this preview".
- `g3v2_evaluate.py` reads the GitHub re-simulation (`GHA_g3v2`), not the hashed `g3_v1` file. If the two differ, no rule says which governs.
- The Monte Carlo SE of p is about 0.0006, so only changed inputs could flip it.
- The hashes are truncated, and the preview's script and output are stored nowhere.
- Fix: "Item 4' is decided by this preview; B3 and B6 are not locked in run 2; the formal run is reported." Give full SHA-256 values, and put the preview script and its JSON in `gates_v2/` so that `LOCK_prereg_v2` hashes them.

**Minor.**
- L11: run the verification once, after `LOCK_labels_v2`, on the locked records.
- L8: state that the word list matches "whole words, case-insensitive".
- S5.4: restrict p2 to non-breaching sessions too.
- L13: deny `~/ledger_rooms_review*` and every other session's project folder.
- S5.1: use `lock2.py check` for every lock.

## For the implementation check (the code may lag)

- `build_room` copies `driver_lines.csv`, `type_list.csv` and `synonyms.csv` into the atlas-coder rooms. That is the type map L8 withholds.
- `lock2.check` skips the chained `*_lock_sha256` keys.
- P and S-b: PREREG v1 §1 recomputes exposure from `kit/exposed_types.csv` and requires equality with `type_labels.csv`, while L6 adds `exposed_v2.csv`.
