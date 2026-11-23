# The consensus rule of exam 1 (verbatim excerpts)

Source: `research/ledger/PREREG.md` section 6 (rulebook v1), carried unchanged into labels v2 by `PREREG_v2.md` L2. Copied verbatim; nothing added.

- **Final record** = the pass-1 record (quote found by pass 2, not in `not_found.csv`) with each disputed field group
  replaced by the adjudicator's reading (groups: MANC type with mapping confidence and basis; line specificity with other
  cell types; each leg field; effect on walking); `labeler_confidence` = the lowest of the readers who contributed;
  `saw_simulation_score` = true if any reader saw a score; re-validated (invalid -> dropped). A dispute without an
  adjudicated record -> dropped. All drops are logged in `labels/merge_log.json`.
- **Type consensus (per leg pair: front, middle, hind; `brainir_ledger.labels.aggregate`):** eligible records are final
  records with `saw_simulation_score` false, mapping confidence not `low` and a mapped MANC type. For a leg field, take the
  eligible records whose value is yes, no or unclear, then
  1. if any has confidence high or medium, drop the low-confidence ones;
  2. if any has line specificity other than `multi_dn`, drop the `multi_dn` ones;
  3. keep the best preparation rank (headless 0; intact_free / intact_tethered 1; other 2), then the best specificity rank
     (clean 0; minor_offtarget 1; unknown 2; multi_dn 3);
  4. all remaining `yes` -> yes; all `no` -> no; both yes and no present -> `conflicting`; otherwise (some unclear) ->
     `unclear`;
  5. no record with yes, no or unclear -> `not_assessed`.
  **Stop call** (`stop_call`): each eligible record gives `stops` (effect `stops` or category `halting`), `no_stop`
  (front-leg rhythm yes, or effect none / slows / speeds / turns) or nothing; over the records that give something, apply
  steps 1-3 above; one value -> that value, two -> `conflicting`, none -> `not_assessed`. **Walking effect**
  (`walking_effect`): the same with the record's `effect_on_walking` (not_assessed records give nothing). **Reported
  frequency** (`freq_hz`): median of the numeric `frequency_hz` of eligible records with front-leg rhythm yes. These are
  reported, never used in the primary analysis.
- Duplicate records of one experiment found by two pass-1 sessions count once (identity and de-duplication rule above).
- **Primary truth** = front-leg consensus label in {yes, no}. Unclear, conflicting, not assessed: excluded.

