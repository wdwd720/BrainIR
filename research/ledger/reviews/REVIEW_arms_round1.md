# Independent review of the prediction arms, round 1 (before the predictions lock)

Reviewer: a fresh subagent that did not write the code (read-only; probes in its own scratch directory; no Modal jobs).
Started 2026-11-19 ~23:25 PST on commit 48edd9a, while the control, B5, B4 and B2 campaigns were still running; findings
returned ~23:55 PST. Brief: audit the stimulation code, the aggregation into tables, the outputs present, outcome leakage,
and anything that would make the lock or the one-shot scoring fail. Its report follows (lightly condensed; every finding
and verification kept). The resolution of each finding is in `RESOLUTION_arms_round1.md`.

**Verdict: LOCK**, once the campaigns complete, the checks listed at the end pass, G4 passes for every locked simulated
campaign, G5 passes, and the post-tag tracked-and-hashed check (finding 2) is done. No blocker, no outcome leakage.

## Findings

1. **major (gate pending)**, PREREG 9 / `run_arms.py` g4. G4 had not yet run for any locked simulated campaign
   (`G4_B1-lo10` was queued behind the 100-container cap; 3 of 3 digests identical so far). Fix: run `g4 --only` on B1-lo5,
   B1-lo10, each control, B5, B4, B2; lock only arms that pass; record how many re-runs landed on the other host type.
2. **major (procedural)**, `.gitignore` (`*.parquet`), `lock.py` (check), `scoring/pipeline.py` (verify_inputs).
   `lock.py check` notices neither a locked file that git does not track (the lock hashes `replicates.parquet`, which is
   git-ignored) nor an arm with no files (a misspelled arm name gives `{}` and `verify_inputs` then raises for the whole
   scoring run). Fix (lock.py is frozen): `git add -f` the parquet files; after tagging, check out the tag in a clean
   worktree, assert every locked path is tracked and hash-equal and every arm has `types.csv`; run `verify_inputs` on the
   real lock with a placeholder labels lock.
3. **minor**, `backend.py` NUMERICS_ENV, PREREG 10, LOG L12. "NumPy AVX-512 dispatch disabled" is not what the job records
   show: pinned AVX-512 hosts still report AVX512F/CD/SKX/CLX/CNL enabled (only AVX512_ICL/SPR disappear). Determinism holds
   anyway: 4,303 B1-lo5/B1-lo10 job pairs with identical tuning paths, 1,914 of them AVX-512 against non-AVX-512 hosts, have
   identical digests. Fix: log the discrepancy, describe the environment as it is, cite the cross-host test.
4. **minor**, `lock.py` (frozen), `run_arms.py` writers. The predictions lock records no environment, though the prompt
   asks for platform, Python and library versions; B4/B5/B2/control provenance has no environment record. Fix: write
   `research/ledger/gates/ENVIRONMENT.json` (hashed through `gates/`) with a per-campaign host summary.
5. **minor**, `run_arms.py` (A0, B0 writers) vs PREREG 11 ("one row per type and seed"). A0's `replicates.parquet` was the
   per-neuron table (933 rows), not 933 x 128; B0's had no `manc_type`. Scoring reads neither. Fix: write the long A0 table
   and add `manc_type` to B0, or state the layout in `config.json`.
6. **minor**, `arms.py` (B5). B5's `mean_score` held the maximum over strengths. Fix: set it to None or document it.
7. **minor (limitation; follows the rule)**, B2 mapping. In 278 of 1,215 body-matched MaleCNS DNs the curated `mancType`
   string names a different MANC type than the matched body's v1.2.1 type (body-first gives the v1.2.1 key, which is right
   for the join; the strings probably use newer MANC names, unverified). 21 DNs are mapped through the string fallback; two
   cholinergic ones land in groups that disagree with their body-matched type-mates (32832 -> "DNg05" vs DNut050;
   924718 -> "DNut064", not a v1.2.1 type, vs DNut054). 18 B2 groups are not A1 types. Fix: none in code; list these in the
   B2 provenance and the handoff.
8. **minor**, LOG L16. L16 says the G3 thresholds were not changed after 8782b73; two definitions changed in 2938fdc (the
   commit recording the G3 evaluation): minimum coupling n 4 -> 8 (cannot change the verdict: all seven pairs had n >= 8)
   and the offset window (-P, P) -> [-P, P-1] (effect not tested). B3/B6 are not locked. Fix: a correcting LOG entry.
9. **minor**, `run_arms.py` select-b1. `select-b1` refreshes the B1 provenance hashes before writing `selection.json`, so
   `B1/provenance.json` does not hash it (the lock will). Fix: optional.
10. **minor (procedural)**, `arms.py` write_arm. `provenance.json` embeds `written_utc`; re-running any writer after the
    lock changes file hashes and scoring will refuse. Fix: run no writer after the lock.

## Verified, no finding (condensed)

- `typescreen.screen_group` matches the locked `screen_candidate` statement for statement except the stimulated set;
  simulation code unchanged since the prereg snapshot; frozen-code hashes intact.
- Network from `paper_network`: 933 excitatory DNs in 321 groups (the authors' `dns_by_type` rule); A1 type names equal the
  groups; 9 mixed-sign types (+ DNit007 mixing GABA and glutamate only).
- A1, A1-lo10, A0, B0, S, B1, B1-alt, B1-lo5, B1-lo10: 321 unique types each, PREREG 11 columns, no NaN primary scores,
  never-usable types score 0 with band `non_driver`, bands match scores. B1/B1-alt recomputed from the replicates and
  re-aggregated byte-identically from `results.pkl`; 12 replicates re-scored from stored traces agree within 7e-8. A1 and
  A1-lo10 rebuilt independently from the raw CSVs; A0/B0 per-type max and mean rebuilt from raw files.
- B1 selection: Spearman 0.78373 (lower 5) vs 0.79200 (lower 10), difference 0.0083 < 0.01 -> 10 kept; B1 = B1-lo10
  apart from the `arm` column.
- Baselines S1-S5, S7, S8 match for all 321 types from the authors' raw matrix; S6 matches the count-matrix definition;
  two-hop sums brute-forced for 3 types.
- Controls: class shuffle uses the authors' 5 classes; rewiring preserves in/out degree and column signs; both rebuild
  deterministically. B4/B5/B2 code matches PREREG 3.9/3.10/3.8; B2 network 4,310 neurons, 130 readout MNs, 328 groups
  with 885 members, every pair carries the `consensusNt` sign. B5 fixed runs equal B1's accepted runs (score, activity,
  frequency) at the same type, seed and current in 6,842 of 6,842 cases.
- Scoring compatibility: the frozen `score_tables` ran end to end in the reviewer's scratch directory on copies of the 9
  real arms plus B2/B4/B5/control tables built by the real aggregation code from fabricated results and synthetic random
  labels: primary ok, 25 secondary analyses ok, 2 not locked (B3, B6).

## Leakage

No outcome leakage found. A1 usability (authors' notebook), B1 cap and lower bound (authors' run config 32818378), the
B1 5-vs-10 choice (model against model, tie rule fixed in PREREG), B4/B5 strengths and calls (prompt defaults), controls
(benchmark generators), S8 core neurons (labelled informed): none tied to a named DN's real-fly phenotype. Runs before the
freeze used DNg100/DNb08 and numeric probes only. The G2 investigation named types including an exposed one, but no model
or procedure change followed. The status flips between arm variants contain no exposed type. Hard-coded DN names in ledger
code: only the exposed list in `build_kit.py`.

## Checks listed for the pending arms

Zero error records and the expected key counts per campaign (5,136 per control, 25,680 B5, 22,816 B4, 5,248 B2); no solver
failure in B4/B5; B5 DNg100 `score_I256` >= 0.5 and B5 = B1 on the full B5; B4 `n_base_rhythmic_128` >= 8; B2 DNg100
group with 2 members and status ok; the scoring dry run repeated on the real B2/B4/B5/control tables and the real lock.
