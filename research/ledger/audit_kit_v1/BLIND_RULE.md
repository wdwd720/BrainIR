# The blind rule of exam 1 (verbatim excerpts)

Source: `research/ledger/PREREG_v2.md` Part L, rules L4 and L6, and `research/ledger/PREREG.md` section 6 (the dedicated family and the passes). Copied verbatim; nothing added.

**L4. Score sighting.** A sighting is seeing a rhythm score, a rank or a driver/non-driver call for a DN type from the
Pugliese-type connectome activation screen, wherever printed (the Pugliese papers, the simulation part of the 2026 Sapkal
preprint, any BrainIR output). Another paper's own model does not count. The reader sets `saw_simulation_score = true` on the
affected records and writes `out/sightings.csv` (`doi, locator, what_was_seen` in {rhythm_score, rank, driver_call},
`types_as_printed`). Records with a sighting are not eligible.


**L6. Eligibility.** A record is eligible whatever session found it once it has passed the second reading (Phase A, Phase B)
and, where the readings disagree, adjudication, and is eligible under the frozen consensus rule (no sighting, mapping
confidence not `low`, a mapped MANC type). **Exposed by nature:** a type whose eligible records all come from dedicated
sessions is added to the exposed set (`labels_v2/exposed_v2.csv`), so it never enters the primary set. The v2 exposed set =
`kit_v2/exposed_types.csv` (unchanged from v1) plus `exposed_v2.csv`.

- **Passes.** Pass 1 finds and labels experiments (eight sessions split by source family, `kit/families.json`). Pass 2
  independently re-labels the same experiments given identifiers only (`exp_id`, DOI, locator, driver lines, name used,
  preparation, effector, stimulation; never a label, quote or MANC type) and maps the name to a MANC type itself (Phase A);
  only after Phase A is saved does it receive the pass-1 quotes and check each against the source (Phase B,
  `quote_checks.csv`); experiments it cannot find go to `not_found.csv`. Compared fields: `manc_type`, the three leg-rhythm
  fields, `effect_on_walking`, `line_specificity`. Two independent search sessions look for experiments without any list
  (capture-recapture). A third blind session adjudicates every compared field on which passes 1 and 2 disagree
  (readings in seeded random order, seed 20261125); the experiments of the dedicated family (Pugliese 2026, Sapkal 2026)
  have their own pass-2 and adjudication sessions, the only ones allowed to open those two sources. Phase B starts only
  after the Phase A run has ended; the Phase A records and not-found list are copied and hashed before the quotes enter the
  room, and those snapshots (not later versions) are what the merge uses; a later change is flagged.
