# Review F — reproducibility, provenance, documentation and report consistency (Phase 1)

Date: 2026-09-23. Reviewer: independent read-only review (Fable 5.1 session). Brief: reproducibility chain of every
committed artefact, provenance rules (CLAUDE.md 3–4), PHASE1_REPORT.md ↔ artefact consistency, the freeze design,
compute accounting, test inventory. Nothing outside this file was written. No answer-key token (published interneuron
type or body id) appears here; oracle labels E1–E5 / I1 / I2 are used where needed.

Repository state reviewed: the tree moved under the review. Start: HEAD `ee68aac`. Probes ran at `558e958`, `876082c`,
`fe1e524` and finally `0333a36` (02:39 local); the numbers below refer to the working tree at `0333a36` unless a
commit is named. At that point `benchmarks/dng100/BENCHMARK_LOCK.json` existed but was **untracked** (`frozen_utc`
2026-09-23T09:37:33Z, `code_commit` = `fe1e524`, `lock_sha256` `78c988cd…`), **no git tag existed**, and the baseline
campaign was still running (`baselines/results/`: 8 runs, 7 evaluations, no `null_distributions.*`, no
`baselines_summary.*`). Reviews A–E were read first; their findings are not repeated except where a claimed fix is
contradicted by the tree.

## 1. Verdict

The reproducibility chain is in good shape where it was built by tooling and weak where it depends on prose. Everything
hash-linked verifies: all 34 bundle files match both `manifest.json`s and `bundle_build.json`; every dataset-manifest
hash referenced by the bundles, the two mapping summaries, `oracle/cross_connectome_reference.json` and the lock equals
the committed manifest; all six registry records point at result files whose SHA-256 and size match; the oracle's
BrainIR statistics equal the cited result files; the four dataset manifests carry a pipeline fingerprint identical to
HEAD's `_code_fingerprint()`, and their parquet hashes are byte-identical to the hashes recorded by the pre-Phase-1
builds (`b671f42`), which is the strongest determinism evidence in the repository (two code versions, same bytes). The
committed tree contains no secrets, no user paths, no answer token in any clean document (28 oracle-derived tokens
scanned against README, CLAUDE.md, docs/, the research notes, `data/manifests/*.json`, the five reviews, `src/`,
`tests/`, `scripts/`), and 361 fast tests pass (38.7 s). What is not yet defensible, and must be fixed before the tag
is placed: (1) the frozen bundle manifests attribute the bundles to commit `8cf0673`, whose exporter did not yet write
salted-permutation positions — the code that produced them was committed five minutes later (`ee68aac`); (2) the
report's §8 baseline paragraph and PROTOCOL §5's "bar" rest on the superseded pre-hardening campaign (already
contradicted by the fresh evaluations) and the lock excludes `baselines/results/**`, so the artefacts the protocol
makes normative are neither present nor pinned; (3) PHASE1_REPORT §6 still states the under-estimated dt-reference floor
that the repository's own `n1_ref1e-10` run refutes, while §10 claims the report was reworded; (4) §8's readout counts
(144 / 144 / 135) contradict the frozen bundles (144 / 142 / 130); (5) 12 of 18 committed result files (all local
stimulation and robustness runs) carry no code commit, fingerprint or registry record, so WS22 is met only for the four
Modal campaigns; (6) `research/cross_connectome_mapping.md` is stale against the 1.1.0 summaries it is supposed to
describe. The lock design covers the benchmark files but not the library code the evaluator executes, and `--check`
verifies only the file map. All of this is cheap to fix; none of it changes a scientific number.

## 2. Findings (ranked)

Severity: **blocker** = must be fixed before the tag/lock is committed (fixing afterwards forces a benchmark v2);
**major** = a stated guarantee does not hold or a report number is contradicted by an artefact; **minor** = gap or
staleness, cheap fix; **note** = observation.

### Blockers (before the tag)

**F-B1. The frozen bundle manifests attribute the bundles to a commit whose exporter would produce a different tier-A bundle.**
`benchmarks/dng100/public/manifest.json` and `public_blind/manifest.json`: `created_utc` 2026-09-23T09:25:11Z /
09:25:18Z, `code_commit` = `8cf0673…`. The salted random permutation of tier-A positions (LOG D40 (a), review C B1) was
committed in `ee68aac` at 09:30:24Z, i.e. the bundles were exported from the dirty working tree of `8cf0673`. The
manifest has no `src_dirty` flag and no exporter fingerprint (`src/brainir/benchmark/bundle.py:270-280` writes only
`created_utc`, `brainir_version`, `code_commit`, `files`), so a reader who checks out `code_commit` and re-runs
`build_public_bundle.py` obtains a tier-A bundle with different positions and a different `bundle_sha256`. The same
dirty-tree attribution applies to `manifests/bundle_build.json` (no commit at all) and to
`oracle/cross_connectome_reference.json` (`created_utc` only, no commit). Why it matters: the whole point of the lock is
that `code_commit` + hashes reproduce the frozen inputs; this is the one field the lock will pin wrongly and cannot be
corrected later without a version bump. Fix: after the final code commit and before `freeze.py`, re-run
`build_public_bundle.py` (the data files are unchanged, so `bundle_sha256` — computed over the data files only,
`bundle.py:270,279` — must come back identical: `3cf5a561…` / `efc33d77…`; treat any difference as a defect), re-run
`leakage_check.py --write-audit`, regenerate `cross_connectome_reference.json`, then freeze. Also add `src_dirty` and
the SHA-256 of `bundle.py` to the bundle manifest, and record the commit in `bundle_build.json` and the reference file.

**F-B2. The protocol's normative baseline/null artefacts are absent, unpinned, and the report's §8 numbers come from the superseded campaign.**
`PROTOCOL.md` §5 requires "outside the null distributions (`baselines/results/null_distributions.md`, empirical
p < 0.05 against the matched null)" and "baselines set the bar … (`baselines/results/baselines_summary.md`)".
At review time neither file existed (the campaign restarted at 02:28 after `ee68aac`; the earlier `results/` were
deleted), and `freeze.py:30` (`EXCLUDE_PARTS = ("__pycache__", "results")`) excludes them from the lock permanently.
`PHASE1_REPORT.md:296-310` quotes the deleted campaign (p ≈ 0.006–0.01, p = 0.002, 70–90 s per network, E-core recall
mean ≤ 0.005, 0.4–3.2 %, 8/8, 3/3): none of these can be traced to a file, and the fresh evaluations already contradict
the prose — `community` now scores E-core recall 0.5 in `male-cns_v1.0` and `kcore_scc` scores type-level recall 0.5
in both MANC networks (`baselines/results/eval/{community,kcore_scc}.json`), whereas the report says both "recover
nothing of the published core in any network". Why it matters: "results are comparable only within one lock"
(PROTOCOL §6) is vacuous if the bar itself is outside the lock, and the report is the acceptance artefact (goal2 §32).
Fix: (a) wait for `run_all_baselines.py` and `null_distributions.py` to finish; (b) add
`baselines/results/baselines_summary.json`, `baselines_summary.md`, `null_distributions.json`, `null_distributions.md`
and every `results/eval/*.json` to the lock (either drop `"results"` from `EXCLUDE_PARTS` and exclude only
`results/runs/*/stdout*`, or list them in `FROZEN_FILES`); (c) rewrite §8 from the final files, per family, and cite
their hashes; (d) make `run_all_baselines.summarise()` refuse mixed `oracle_sha256` / `evaluator_sha256` /
`bundle_sha256` (review D-M5; `run_all_baselines.py:113-114` copies them without comparing).

### Major

**F-M1. PHASE1_REPORT §6 repeats the under-estimated reference-error floor that review B-1 flagged, and §10 claims it was reworded.**
`PHASE1_REPORT.md:121-122`: "reference RK45 rtol 1e-8 / atol 1e-11 whose own error is ≈ 6e-4 Hz". The repository's own
`results/robust_dt_convergence_manc_v1.2.1_nt-paper_n1_ref1e-10.md` (Part A, row "RK45 rtol 1e-8 atol 1e-11")
*measures* that reference's error against a 1e-10/1e-13 reference: max |Δr| 7.21e-3 Hz whole run, 3.97e-4 Hz for
t ≤ 0.3 s, RMS 6.74e-5 Hz — 12× the quoted figure at the maximum. `PHASE1_REPORT.md:337` (review table, row B) states
"report reworded to the measured floor". Related mixed sourcing in the same paragraph: "Euler at 1 ms … score by up to
0.09" is the n = 1 run's value (the 6-seed run says 1.2e-1, `…_n6.md` Part A), and "segment-wise and single-interval
integration agree to 0.07 Hz" is not a quantity in either file (each differs from the reference by ≤ 6.6e-2 / 6.2e-2 Hz,
`…_n6.md` Part B). Fix: quote the measured floor (7.2e-3 Hz max / 6.7e-5 Hz RMS, n = 1) and state which run each number
comes from; the headline that survives is the decision-level invariance (score, MN frequency, active-MN set identical
across RK45 / DOP853 / RK4 ≤ 1 ms; Euler 1 ms alone deviates).

**F-M2. Report §8 readout counts contradict the frozen bundles.** `PHASE1_REPORT.md:281-282`: "readout = front-leg
motor neurons (144 / 144 / 135)". Both bundle manifests: `readout_n` 144 (`manc_v1.2.1`), **142** (`manc_v1.2.3`), **130**
(`male-cns_v1.0`); the stimulation result and §7.2 itself say 130. Already flagged as D-m7; not fixed. Fix: 144 / 142 /
130, and say why v1.2.3 has 142 (two front-leg MNs retyped in the 2025-10-26 snapshot) and MaleCNS 130 (the published
network's `fl` MNs; 135 exist in the dataset).

**F-M3. Local reproductions carry no code provenance (goal2 WS22).** Of the 18 committed result files, only the four
Modal campaigns (`pruning_*_n1024`, `pruning_*_n64_seed0_DOP853…`, `dn_screen_*`, `interventions_*` ×2,
`cross_connectome_eval_n64`) have registry records; three of those records were created retroactively (see F-m2). The
12 others — `stim_dng100_*` (×4) and `robust_*` (×8) — contain no `commit`, no fingerprint, no `run_id` and no
`estimated_cost` (grep of every results JSON for commit/git/run_id/fingerprint/sha256 keys: empty, except the mapping
table sha in the cross-connectome file). `reproduce_dynamics.py` and `robustness_experiments.py` never call
`register_run` (the four drivers that do: `reproduce_{pruning,dn_screen,interventions}.py`, `cross_connectome_eval.py`).
These 12 files feed PHASE1_REPORT §6, §7.2, §7.7 and the oracle's `stimulation_statistics_brainir*` blocks. Why it
matters: WS22 asks that "every significant benchmark run" record commit, dataset hashes, seeds, backend; a future reader
cannot tell which `model.py` produced the n = 1024 statistics (they were run at ~00:59 and 01:44, before the fixed-step
fix — irrelevant to RK45 results, but that is exactly what a record would prove). Fix: give both drivers the same
`register_run` call (config, seeds, `network_hash`, `LocalBackend` stats, artefact hash) and re-register the existing
files retroactively with `notes: "record created retroactively"` as was done for the interventions; add `commit` /
`brainir_version` / `created_utc` to the result JSONs themselves so the link is two-directional.

**F-M4. `research/cross_connectome_mapping.md` is stale against the committed 1.1.0 summaries it documents.**
The note is the human-readable half of WS4. Header (`:3`) says "mapping schema 1.0.0"; §4.1 (`:74-75`) says unmatched
"2 | 2" and confidence none "1,167 / 1,169"; §6 (`:180-186`) lists 449,958 / 243,378 rows and table hashes `e0e18526…`
/ `67d51352…` and manifest hashes `84ccb241…` / `cea1472c…` / `ca8962d5…`. The committed summaries
(`data/manifests/mapping_*.summary.json`, 02:25) say schema 1.1.0, 449,984 / 243,404 rows, unmatched 28 / 28, none
1,193 / 1,195, table sha `81699b6b…` / `e6e8cc64…`, manifest hashes `e52ccb18…` / `117d93c7…` / `8d4ef4a2…` — the
values PHASE1_REPORT §4 and `cross_connectome_reference.json` use. §3 explains the 26-neuron scope change but the tables
were not regenerated (file mtime 02:13 < summaries 02:25). Fix: regenerate §4.1, §4.2 and §6 from the summaries, bump
the header to 1.1.0, and make the test count in §6 (`10 tests`) match `tests/test_mapping.py` (13).

**F-M5. Lock design: `--check` verifies only the file map, and the lock omits the code the evaluator executes.**
`benchmarks/dng100/freeze.py`: `check()` (`:81-86`) compares `files` only — it does not re-verify
`dataset_manifests_sha256`, `code_commit` (already stale: the lock says `fe1e524`, HEAD is `0333a36`, and the commit
that adds the lock can never be in it), `oracle_sha256`/`evaluator_sha256` (subsumed by `files`, fine) or the lock's
own `lock_sha256` (a hand-edited lock passes). Not hashed at all: `src/brainir/sim/*`, `src/brainir/metrics/rhythm.py`,
`src/brainir/benchmark/{bundle,prediction}.py` (the functional, robustness and transfer families run this code; a
tolerance or metric change alters every functional score while `--check` passes), `pyproject.toml` / `uv.lock`
(the scipy version fixes the RK45 step sequence), `build_cross_connectome_reference.py`, `manifests/bundle_build.json`,
and `baselines/results/**` (F-B2). Legitimately-changing content *is* hashed: `LEAKAGE_AUDIT.md` line 3 ("Checked
<timestamp>"), `oracle/cross_connectome_reference.json` (`created_utc`), `public*/manifest.json` (`created_utc`,
`code_commit`) — a content-identical regeneration of any of them breaks the lock, so the protocol must say "never
regenerate after the tag" or the timestamp lines must be excluded. `brainir_version` is `0.0.1` and has never been
bumped, so it identifies nothing. No test runs `freeze.py --check` (goal2 WS29 "hash locking, freeze detection"; grep of
`tests/` for freeze/BENCHMARK_LOCK: none). Fix: hash `src/brainir/{sim,metrics,benchmark}/**/*.py`, `pyproject.toml`
and `uv.lock` into `files` (or a `code` block); make `--check` also verify `dataset_manifests_sha256`, recompute
`lock_sha256`, and warn when `git merge-base --is-ancestor <code_commit> HEAD` fails; add
`tests/test_freeze_lock.py` (skips when the lock is absent) and a note in PROTOCOL §6 that the tag is placed on the
commit that adds the lock (so `code_commit` = tag^). Bump `brainir.__version__` to 0.1.0 at the tag.

**F-M6. Anticipatory status statements committed before the facts.** `CLAUDE.md:5-7` and `README.md:7-12` (committed in
`0333a36`) say the package is "locked by `BENCHMARK_LOCK.json` and git tag `dng100-benchmark-v1`"; `research/LOG.md` §10
(added in `fe1e524`) says "BENCHMARK_LOCK.json written and the tree tagged `dng100-benchmark-v1`; PHASE1_REPORT.md
finalised". At `0333a36`: the lock is untracked, `git tag -l` is empty, and PHASE1_REPORT carries eight `[PENDING]`
markers (`:8` "lock hash `[PENDING: final lock]`", `:30-35` five table rows, `:341` review F) next to the status line
"complete and frozen … six independent reviews closed". This self-resolves only if the tag is actually placed; a fresh
session reading CLAUDE.md before then would trust a lock that does not exist in git. Fix: commit the lock, tag, then
update the three documents with the real lock hash and tag commit in that order; re-date the LOG §10 entry.

### Minor

**F-m1. Dataset manifests record a dirty pre-commit state.** All four `data/manifests/*.manifest.json`:
`build.git.commit` = `8cf0673`, `src_dirty: true` (rebuilt 02:13–02:21 from the working tree that became `ee68aac`).
Attribution is rescued by `pipeline_code.combined_sha256` = `ab0e92f8…` = HEAD's `_code_fingerprint()` (all 10
fingerprinted files identical), and the parquet hashes equal those in the `b671f42`-era manifests (fingerprint
`85ce8c98…` / `022fa608…`): review A-A1 is closed in substance. But nothing tests this, and the report's "second build
byte-identical" (`PHASE1_REPORT.md:68-69`) is not recorded in any manifest. Fix: add the test review A proposed
(`pipeline_code.files == _code_fingerprint()["files"]` for every committed manifest) and state in LOG that the final
rebuild reproduced the `b671f42` parquet hashes exactly (that *is* the two-build evidence).

**F-m2. Three registry records are retroactive estimates.** `manifests/experiments/{f16168e9…,640d0dd3…,1e7d2430…}.json`
(interventions ×2, cross-connectome n64): `notes` say "created retroactively from the result file (Review F)",
`wall_time_s` null, `inputs: {}` (no `network_hash`), costs 0.25 / 0.25 / 0.23 USD rounded by hand rather than computed
by `ModalBackend` (`backend.py:187-190`). Fine as estimates, but the report should say "≈" and the records should carry
the network hash. `PHASE1_REPORT.md:319` "cross-connectome transfer (two runs) ≈ $0.5" is backed by one record ($0.23);
the n = 8 pilot (deleted) and the two Modal smokes (LOG D34/D37, ≈ $0.015) have no record.

**F-m3. Superseded or pilot outputs without a marker.** `results/stim_dng100_manc_v1.2.1_nt-paper_n128.*` (00:33; pilot
of the n = 1024 run, mean 0.975 vs 0.973) and `results/robust_weight_noise_*_n8.*` (pilot; the report does mention it)
are indistinguishable from final results by name. `results/robust_dt_convergence_*_n6.md:242` ("In part B the
fixed-step schemes evaluate the pulse indicator at the stage times, so the k4 stage … see the other side of the
switch") describes the pre-fix behaviour in the present tense although the file was produced after the fix (08:55Z; its
own Part B shows a zero onset error); the `n1_ref1e-10` file carries the corrected sentence. Fix: a `status:
superseded_by <file>` line in the pilot JSON/MD (or a `results/pilots/` folder) and regenerate the n6 markdown text.

**F-m4. §6/§7.7 small mis-statements.** `PHASE1_REPORT.md:253` "Parameter spread … (n = 8)": the widen = 0 row has
n = 2 (`robust_param_sweep_*_n8.md`). `:256-257` "θ 5 … 10 → … with 13.3 → 9.0 Hz": the sequence is 13.25 / 11.91 /
10.39 / 8.98 / 9.17 Hz (not monotonic at θ = 10). `:186` "isolated cores run faster (15–17 Hz)": the range is
14.9–16.7 Hz.

**F-m5. Oracle cites result files by path only.** Seven `source`/`see` strings in `oracle/oracle.json` name result
files (two also name registry runs) without a hash. The numbers match today (checked: MaleCNS stimulation block =
`stim_dng100_male-cns_v1.0_nt-paper_n128.md`; pruning block = summary of the n1024 JSON; DN-screen block = registry
summary). Add `source_sha256` so drift is detectable; the lock hashes the oracle but not the cited files.

**F-m6. `cross_connectome_reference.json` bookkeeping.** `a.n_nodes` = 4310 (node-list rows) while the benchmark
network has 4,309 neurons (one absent body); no code commit recorded. Pairs 3,717 + 3,717 = 7,434 (matches
PHASE1_REPORT §4). Add `code_commit` and `n_network_neurons`.

**F-m7. Documentation staleness (commands exist, numbers drift).** Every command in CLAUDE.md resolves
(`brainir --help` lists the 12 sub-commands; `mapping build --a/--b`, `ingest --dataset/--version`, the driver flags
`--containers`, `--replicates`, `--n`, `--method/--rtol/--atol` exist). But: `CLAUDE.md:26` "~25 s" and `README.md:35`
"~20 s" vs 38.7 s measured (361 tests); `CLAUDE.md:39-40` "~$25" / "~$10" vs recorded $15.45 / $18.55;
`CLAUDE.md:74-77` lists four of the seven reproduction drivers (missing `reproduce_pruning.py`,
`reproduce_dn_screen.py`, `cross_connectome_eval.py`, which the Commands block does list); `README.md:16-27` "What
exists" still names only the MaleCNS registry and `ingest/malecns.py` and has no MANC / simulator / benchmark-package
rows; the README quickstart omits the MANC acquire/ingest lines that `data/README.md` has.

**F-m8. Leakage-guard scope.** `tests/test_leakage_guard.py:62` globs `*.md` inside directories, so
`data/manifests/*.json` and `*.summary.json` are never scanned by the guard (my scan of them with the same 28 tokens
found nothing). Add `*.json` (and `research/audit/`) to the glob.

**F-m9. Test coverage gaps in benchmark tooling (goal2 WS29).** No test imports or runs `evaluator/evaluate.py`
(review D noted this; still none), `cleanroom/run_method.py` / `_sandbox.py` (the "escape test fails as intended" in
`PHASE1_REPORT.md:338` was a reviewer's scratch script, not a test), or `freeze.py`; `brainir.sim.weights.signed_matrix`
and the export path of `brainir.benchmark.bundle` are exercised only through real data or the committed bundles;
`brainir.validation`, `brainir.paths`, `brainir.manifest` only indirectly. Cheapest additions: a synthetic tier-A
bundle round-trip (export → evaluate the example method → assert the type-level family is non-zero), a sandbox test
that a method opening a path outside the bundle copy is refused, and `freeze.py --check` on the committed lock.

### Notes

- F-n1. **Compute accounting.** Registry total = $37.75 (pruning 15.4508 + DN screen 18.5507 + DOP853 pruning 3.0227 +
  interventions 0.25 + 0.25 + cross-connectome 0.23), consistent with PHASE1_REPORT §9 "≈ $38" and the status line.
  Unrecorded: the two Modal smokes (≈ $0.015, LOG D34/D37), the deleted n = 8 cross-connectome pilot, any aborted
  attempt, image builds and idle time. The brief's expectation of ≈ $60–70 is not supported by any record; if that
  figure comes from the Modal dashboard, record the billed total once in §9 next to the list-price estimates.
- F-n2. **Test suite.** `uv run --no-sync pytest -m "not real_data" -q`: 361 passed, 18 deselected, 38.66 s (with the
  baseline campaign running). 25 test files; inventory in §5.
- F-n3. **Answer-token scan clean.** 28 tokens read from `oracle.json` (7 types, 21 ids incl. contralateral copies):
  no hit in README.md, CLAUDE.md, docs/, `research/{LOG,data_ecosystem,connectome_ecosystem_survey,
  cross_connectome_mapping,manc_release_notes}.md`, `research/audit/**`, `data/README.md`, `data/manifests/**`
  (JSON and MD), `benchmarks/dng100/{PROTOCOL,LEAKAGE_AUDIT}.md`, the bundle/baseline/node READMEs, `src/`, `tests/`,
  `scripts/`. The pytest guard passes.
- F-n4. **Secrets / paths.** No `ak-`/`as-` strings, no `MODAL_TOKEN` value (name only, `backend.py:254`), no user name
  or local app-data path in any tracked file; `$DATA/` (19–28 per manifest) and `$REPO/` placeholders used throughout.
  `C:\Dev\BrainIR` (repo root, no user name) appears in `PHASE0_REPORT.md:15,28,41` and `research/LOG.md` D1 — the
  letter of rule 4 says otherwise. `oracle/tier_a_salt.txt` is tracked by design (review C m8); `.gitignore`'s
  `*token*.txt` does not cover it, which is intended. `git ls-files`: parquet only under `public*/` (locked), no
  feather/logs; the largest committed result is `dn_screen_*.json` (3.9 MB).
- F-n5. **Hash chain verified.** Bundle `files` (17 + 17) all match; `bundle_build.json` hashes = manifest hashes;
  every `source_tables.manifest_sha256`, both mapping summaries' manifest hashes, the reference file's mapping-table
  hashes and the lock's `dataset_manifests_sha256` equal the committed manifests; six registry `artifacts.results`
  hashes and sizes match; the fresh baseline evaluations carry the current oracle (`26966194…`) and evaluator
  (`3c116470…`, version 1.1.0) hashes and the tier-A bundle hash. `freeze.py --check` passes at `0333a36`.
- F-n6. **Report numbers verified against files** (all of §2.2, §4, §7.1–§7.7 except the items in §4 below):
  build statistics and validation counts (four manifests); 24,162 / 449,984 / 18,555 / 4,414 (78 / 4,336) / 1,165 / 28 /
  97.0 / 96.0 / 91.5 % / 4,022 (21.7 %) / 3,717; 196,535 / 1,372,404 / 118,920 / 118,729 / 118,488 (99.84 %) /
  116,424 / 4,280 / 99.44 %; the n = 1024 and n = 128 stimulation tables; every intervention cell; 68.1 / 16.5 / 8.1 /
  99.5 %, 780 / 191 / 53 (recomputed from `n_kept_active`), median 101 simulations, 16.7 Hz (median over the 697
  modal-circuit screens = 16.667), 17.6 min, $15.5, 1,018; DOP853: 59/64, 49/64 = 76.6 %, 50 / 9 / 3 on the same RK45
  seeds (recomputed), 10.8 min, $3.0; DN screen 31 / 134 (14.4 %) / ranks 1, 2 / 0.981, 0.911 / 0.946 / 14,928 / 42 min
  / $18.6; cross-connectome 0.983 / 0.795 / 0.765 (15.2 Hz) / 0.969 / 0.978 / 0.857 (14.9 Hz) / null 0.000; every
  robustness, input-sweep, weight-noise and negative-control figure; 361 / 18 tests; lock: 68 files and the three hashes
  in §8.

## 3. goal2.md final-report requirements

| requirement (goal2 "PHASE 1 REPORT should cover") | status | evidence / gap |
|---|---|---|
| what was built | pass | §1 table; five rows still `[PENDING]` at review time (F-M6) |
| exact MANC dataset/version; relationship to the paper version | pass | §2.1, LOG D21, `manc_reproduction.md`; the 4,600/4,604 and 4,593 type-agreement counts trace to LOG prose only |
| storage | pass | §2.2 pointers to manifests; `data/README.md` layout |
| processing | pass | §2.2, adapters; manifests carry fingerprint = HEAD (F-m1) |
| validation | pass | §2.2 counts equal the four validation reports |
| cross-connectome mappings | pass (doc stale) | §4 equals the committed summaries; the human-readable note is stale (F-M4) |
| reproduction of published connectivity | pass | §7.1 = `manc_reproduction.md` / `tables/manc_reproduction_summary.json` |
| reproduction of published dynamics | pass | §7.2–7.6 all traced (F-n6); local runs lack provenance records (F-M3) |
| simulator equations | pass | §6 |
| numerical details | fail (text) | §6 quotes a refuted reference floor and mixes two runs (F-M1); the underlying files are sound |
| rhythm metrics | pass | §6, D30 |
| baseline methods | pass | §8 list of nine; code locked |
| baseline results | unverifiable | superseded campaign quoted; fresh campaign incomplete and unpinned (F-B2) |
| null results | unverifiable | `null_distributions.*` absent at review time; excluded from the lock (F-B2) |
| negative controls | pass | §7.7 = `robust_negative_controls_*_n8.md` |
| robustness/sensitivity results | pass | §7.7 = `robust_param_sweep`, `robust_input_sweep`, `robust_weight_noise_*_n64`; n = 2 caveat (F-m4) |
| benchmark public/oracle separation | pass | §8; bundles verify; oracle read by evaluator only |
| leakage audit | pass | `LEAKAGE_AUDIT.md` PASS dated after the export; token scan clean (F-n3) |
| benchmark lock/version | fail at review time | lock untracked, `code_commit` stale, no tag; design gaps (F-M5, F-B1) |
| Modal/cloud usage | pass (estimates) | §9 ≈ $38 = registry $37.75; three records retroactive (F-m2) |
| tests | pass | 361 / 18 confirmed |
| independent reviews | pass (A–E) / pending (F) | §10 table; one claimed fix contradicted by §6 (F-M1) |
| unresolved uncertainties | pass | §12 |
| scientific limitations | pass | §11: model-derived vs wet-lab, two animals, curated vs derived correspondences all stated; no overclaim found in §7–§8 prose beyond the review-table claim of F-M1 |
| exact recommended Phase 2 objective | pass | §13 |
| acceptance 1 (Phase 0 reproducible) | pass | MaleCNS parquet hashes identical across the Phase 0 and final builds |
| acceptance 4 (checksums/provenance recorded) | pass (minor) | dirty-commit attribution (F-m1) |
| acceptance 25 (experiment provenance machine-readable) | partial | Modal campaigns yes; 12 local result files no (F-M3) |
| acceptance 27 (all tests pass) | pass | 361 passed; real-data suite not run here (data directory shared with running jobs) |
| acceptance 28–29 (audits completed, serious findings fixed) | partial | A–E fixes verified in code except F-M1's report text and F-M2 (D-m7) |
| acceptance 30 (artefacts cryptographically locked) | not yet | lock exists but is untracked and does not cover the protocol's bar or the evaluator's library code |
| acceptance 31 (tag) | not yet | no tag at `0333a36` |
| acceptance 32 (report sufficient for a fresh session) | almost | after F-B2, F-M1, F-M2, F-M6 |

## 4. Report numbers I could not trace to an artefact (or that an artefact contradicts)

1. §1 status line / §8: lock hash `[PENDING]` while `BENCHMARK_LOCK.json` says `78c988cd…` (untracked); "tag
   `dng100-benchmark-v1`" — no tag exists.
2. §1: "32 files, 5.0 GB" for MANC acquisition — the manifests list 11 (v1.0) + 18 (v1.2) = 29 acquisition files;
   32 is not in any manifest or LOG entry.
3. §2.1: type agreement "4,600/4,604" and "4,593" — LOG D21 prose only, no table or script output.
4. §2.2: "HR-only: 5,666,874" — LOG D24 prose only (the manc_v1.0 manifest does not contain the number); "every build
   was run twice and the second build is byte-identical" — no manifest field; indirectly supported by the identical
   parquet hashes across `b671f42` and `0333a36` manifests.
5. §2.3: 314 `RT Orphan`, 23,188 traced-adjacency bodies, 72/4,604 relabelled neurons — LOG §3.12–3.13 prose (the v1.0
   validation report may carry the first two as cross-source checks; not verified here).
6. §6: "reference … own error ≈ 6e-4 Hz" — **contradicted** by `…_n1_ref1e-10.md` (7.21e-3 Hz max, 6.74e-5 RMS);
   "agree to 0.07 Hz" — not a reported quantity; "score by up to 0.09" — n = 1 value, the 6-seed run gives 0.12;
   "10 synthetic circuits, 16 labelled signal kinds" — not counted here (`CIRCUITS` / `SIGNAL_KINDS` registries exist).
7. §7.2: "135 exist in MaleCNS" — LOG §3.18 prose; "138 module-labelled MNs" — `pugliese_model_spec_from_code.md` only.
8. §7.7: "(n = 8)" for the parameter-spread series — widen = 0 has n = 2.
9. §8: "144 / 144 / 135" — **contradicted** by both bundle manifests (144 / 142 / 130).
10. §8 baselines: p ≈ 0.006–0.01, p = 0.002, 70–90 s per network, 8/8, 3/3, precision 1.0, E-core recall mean ≤ 0.005,
    0.4–3.2 % — no file at review time (superseded campaign deleted; fresh one incomplete); "k-core/SCC …
    community … recover nothing … in any network" — **contradicted** by the fresh `community.json` (E-core 0.5 in
    MaleCNS) and `kcore_scc.json` (type-level 0.5 in both MANC networks).
11. §9: "cross-connectome transfer (two runs) ≈ $0.5" — one registry record ($0.23); "baseline campaign (~1 h)" — no
    record; "smokes < $0.1" — LOG D34/D37 prose ($0.007 + $0.008).
12. §10 review table, row B: "report reworded to the measured floor" — not true of §6 (item 6); row C: "escape test
    fails as intended" — no such test in `tests/`.

## 5. What I ran (read-only; no ingestion, acquisition, Modal or real-network simulation)

- `uv run --no-sync pytest -m "not real_data" -q -p no:cacheprovider` → 361 passed, 18 deselected, 38.66 s. (`uv` is
  not on PATH in the tool shells; the WinGet path documented in CLAUDE.md works.)
- Test inventory (file — what it covers): `test_acquire_offline` (registry pins, offline verify);
  `test_baselines_contract` (nine baselines: import rules, forbidden words, no absolute paths, schema-valid output);
  `test_benchmark_package` (prediction schema, blind tokens, bundle verification, one real-data tier-A check);
  `test_cli` (CLI on the synthetic build); `test_compute_backend` (LocalBackend map, shared payload, registry record
  round-trip); `test_determinism` (byte-identical synthetic rebuild); `test_docs` (evidence descriptions, generated
  schema doc current); `test_graph` (Connectome API, nullable ints); `test_ingest_manc_synthetic` /
  `test_ingest_synthetic` (adapters against hand-derived truth); `test_invalid_inputs` (MaleCNS bad inputs);
  `test_leakage_check` (benchmark leakage checks, audit current); `test_leakage_guard` (tokens from the oracle vs
  `src/` and clean docs, no benchmark imports, answer-key README); `test_mapping` (rules, confidence, ambiguity,
  writer); `test_metrics_rhythm` (published score, gates); `test_provenance` (registry/acquisition/manifest records, no
  machine paths); `test_real_data` (18 smoke tests, deselected); `test_robustness_experiments` (control constructions);
  `test_schema` (tables, vocab, sign rule); `test_sim_model` (rate model vs closed forms and the reference integrator,
  interventions, fixed-step pulse edge); `test_sim_prune_screen` (embedded oscillator recovered); `test_synapses`
  (synapse extraction); `test_synthetic_circuits` / `test_synthetic_signals` (fixture truths). Modules with no direct
  test import: `brainir.validation`, `brainir.paths`, `brainir.manifest` (indirect only), `brainir.sim.weights`
  (`scaled_weights` only), `brainir.benchmark.bundle` export path; no test for `evaluate.py`, `run_method.py`,
  `_sandbox.py`, `freeze.py` (F-m9).
- Three scratch Python probes (scratchpad, not committed) over the committed JSON artefacts: manifest fields vs
  `_code_fingerprint()`, parquet hashes vs the `8cf0673` / `b671f42` manifests via `git show`, bundle and
  `bundle_build.json` hash verification, mapping summaries ↔ manifests ↔ reference file ↔ cross-connectome result,
  registry records ↔ result files (hash, size), oracle structure and cited files, baseline eval/run-record hashes,
  pruning kept-set sizes and modal-circuit frequency, first-64-seed RK45 vs DOP853 counts, cost sums, a masked
  answer-token scan of the clean documents (tokens read from the oracle, printed only as indices), and
  `freeze.py --check`.
- `git ls-files`, `git status`, `git log`, `git tag -l`, `git grep` for absolute paths / user names / secret-like
  strings; `brainir --help` and the `mapping`, `ingest`, `acquire` sub-command help; argparse greps of the five drivers.
- Read in full: CLAUDE.md, README.md, PHASE1_REPORT.md (twice: `ee68aac` working tree and `0333a36`), goal2.md,
  PROTOCOL.md, LEAKAGE_AUDIT.md, research/LOG.md, research/cross_connectome_mapping.md, the five reviews, freeze.py,
  build_cross_connectome_reference.py, compute/registry.py, every `results/*.md`, both mapping summaries,
  `bundle_build.json`, all registry records, `manc_reproduction.md`, the answer-key README, data/README.md, the
  leakage-guard, benchmark-package, leakage-check and docs tests.
- Not run / not verified: the real-data suite, any rebuild, any simulation, the baseline campaign, Modal billing.
