# Review C — leakage, blinding, clean room, protocol (dng100-benchmark-v1)

Reviewer: independent adversarial review, 2026-09-23. Scope: `benchmarks/dng100/` (tiers A/B, clean room, evaluator,
protocol) and the library guard. Stance: attacker first, then auditor. No answer-key token (published interneuron
type name or oracle body id), no salt value and no machine path appears in this document; oracle labels are referred to by
their generic slot names (E1, E2, I1, I2, E3–E5) as the evaluator itself prints them.

Line numbers refer to HEAD 5de3e7c. While this review was running, another session was editing the working tree
(uncommitted: `evaluator/evaluate.py` +8 lines from line 64, `src/brainir/benchmark/bundle.py` +1 line at 135,
`oracle/oracle.json`, `oracle/tier_a_ids/*.csv` (a `cell_type` column was added), `tests/test_leakage_guard.py`
CLEAN_DOCS, `src/brainir/schema/vocab.py`, `src/brainir/cli.py`). Where those edits touch a finding it is said so.

## 1. Verdict

Tier A is blind against exactly one adversary: a method that *remembers type names and body ids* but has nothing else.
It is not blind against anyone who holds (i) the paper's public node lists — the positional ids are their row order
(MANC) or their ascending sort (MaleCNS), so position -> body id is one `enumerate`; (ii) the tier-B bundle — it is
row-aligned with tier A and carries `position` next to `source_id`; (iii) the public neuPrint databases — `size_voxels`
is an exact, 100 % unique per-body fingerprint; or (iv) the paper's connectivity figures — the bundle reproduces the
published synapse counts exactly, and the mutual count pair between the two excitatory core neurons is unique among all
ordered pairs of each network. The clean room does not confine the method: a "method" that imports only `brainir`
passes every check of `run_method.py`, opens `oracle.json`, the tier-A id maps and the tier-B bundle from inside the
run, and receives operator-supplied `--method-args` that the run record does not mention (demonstrated, section 3).
The freeze that PROTOCOL.md step 1 depends on does not exist yet (no `BENCHMARK_LOCK.json`, no tag). Consequently an
"independent recovery" claim under PROTOCOL.md section 5 would today rest entirely on the honesty of the method author
and on an unverified `inputs_used` list, not on the bundle or the runner. It should not be made before the blockers
below are fixed; after them, the residual limit must be disclosed explicitly: tier A blinds *identifiers*, not
*structure*. Structural knowledge of the answer ("the strongest excitatory direct target of the stimulus and its
heaviest reciprocal partner") cannot be blinded, and it is also what two-line degree heuristics recover (excitatory
core recall 1.0 without any simulation, section 3). The credible bar for a claim is therefore the part degree does
not give: the inhibitory slot, functional sufficiency and necessity, beaten baselines and a null — with the freeze,
the enforced hash chain and an access-logged runner in place.

## 2. Findings (ranked)

### Blockers

**B1 — Positional ids are a public function of the paper's node lists.**
`src/brainir/benchmark/bundle.py:117` (`tab["position"] = np.arange(net.n)`), `:134-135` (id map = `net.ids` in
build order), `src/brainir/sim/weights.py:95` ("their order is kept"), `benchmarks/dng100/nodes/README.md:3-5` (node
lists are the published repository files). Verified against `oracle/tier_a_ids/`: for both MANC networks the position
sequence *is* the node-list file order; for MaleCNS it is the ascending body-id order of the published list (one absent
body dropped). Impact: D32's stated purpose ("body IDs appear in the paper's supplementary tables ... positional ids
remove that channel") is not achieved — anyone with the paper's repository inverts every position offline, so the
`tier_a_ids/` maps protect nothing. Fix: draw a secret permutation per network from the salt
(`np.random.default_rng(int(salt, 16) ^ hash(network))`), apply it to rows, edges, stimulus and readout before
assigning positions, and keep only the permuted map in `oracle/`. Re-export both tiers and re-run baselines.

**B2 — Tier B is the tier-A id map.** `bundle.py:137-138` writes `position` (== row index, identical order in both
tiers) beside the body-id `source_id` into tier-B `neurons.parquet`. PROTOCOL.md section 2 treats tier B as a
legitimate public setting, so publishing both tiers publishes position -> body id. Fix: independent secret permutation
for tier A (B1) and drop `position` from tier B (positions are meaningless there).

**B3 — The clean room does not confine the method.** `benchmarks/dng100/cleanroom/run_method.py:40,50-51` (a regex
over the method file's *text* for `import benchmarks|oracle|evaluate` at line start), `:58-59` (environment
whitelist), `:66-69` (subprocess with `sys.executable` = the repository venv, full filesystem, network). No path,
import, socket or write restriction exists at run time. Demonstrated with a reviewer method (scratchpad, not in the
repo) that imports only `brainir` and the standard library: `brainir.paths.repo_root()` and
`Path(sys.executable).parents[2]` both yield the repository; `__import__("ora"+"cle")` after a `sys.path.insert`
loads the oracle module (7 labels read); `oracle/tier_a_ids/ids_<net>.csv` and `public/networks/<net>/neurons.parquet`
are readable; the bundle copy is writable; the runner reported `rc 0` and hashed the prediction as if clean. Sibling
modules next to the method (`sys.path[0]`), `importlib`, `exec`, and any `open()` with an absolute path are equally
invisible to the regex; `tests/test_baselines_contract.py:212-235` has the same text-level blind spot. Impact: the
"clean" status in `run_record.json` is unverifiable; the protocol's independence claim reduces to trust. Fix
(layered): (a) run the method in a separate interpreter that has `brainir` installed from a wheel, no repository
checkout, `BRAINIR_DATA_DIR` pointing at an empty directory, and — for tier-A claims — no network (container/Modal with
only the bundle mounted, as goal2 WS10 asks); (b) launch the method through a wrapper that installs
`sys.addaudithook` for `open`, `os.*`, `socket.*` and `import` events and writes an access log; the runner fails the
run if any path outside {bundle copy, interpreter, site-packages, `BRAINIR_OUT`} was opened or any socket created;
(c) record `sys.modules` at method exit and refuse `oracle`, `evaluate`, `benchmarks*`, `null_distributions`.

**B4 — Nothing is frozen.** `BENCHMARK_LOCK.json` does not exist, `git tag` is empty, `PROTOCOL.md:36-37` (step 1:
compare `bundle_sha256` with the lock) cannot be executed, `.gitignore:27` refers to hashes "in BENCHMARK_LOCK.json",
`benchmarks/dng100/baselines/` is untracked, and both manifests record `code_commit` 247d0f4 while HEAD is 5de3e7c
(PHASE1_REPORT.md:32 marks the freeze as pending). Impact: "results are comparable only within one lock" is currently
vacuous, and the LEAKAGE_AUDIT PASS is not tied to a hash. Fix: fix B1/B2/M2 first (they change the bundles), finish
the baselines, run `freeze.py`, commit, tag; add `freeze.py --check` to the test suite; exclude the `checked_utc`
line from what the lock hashes (`freeze.py:28` freezes `LEAKAGE_AUDIT.md`, whose first line changes at every re-audit).

### Major

**M1 — Fingerprint channels defeat any identifier blinding.** `bundle.py:137-138,145-146`: `size_voxels` is
non-null for 99.5–100 % of neurons and unique for 100 % of them (also for 100 % of interneurons) in all three
networks; neuPrint exposes the same integer as `size`. `(in_pairs, out_pairs)` alone is unique for 87 % (MANC) / 73 %
(MaleCNS) of interneurons. Synapse counts are exact and equal the published matrices (LOG D21–D28), so the
(forward, backward) count pair between E1 and E2 matches exactly one ordered pair in each network. Impact: a method
with database access or the paper's figures re-identifies the core with no simulation; positional ids and tokens are
then decorative. Fix: (a) say so in PROTOCOL.md section 2 ("tier A blinds identifiers, not structure; a literature-
or database-aware method is NOT made blind by tier A; independence is established by the access log, not the
bundle"); (b) coarsen `size_voxels` to what the model consumes — publish the size-scaling factor rounded to two
significant digits, or rank-quantised sizes — since the model only needs `a/s` and `theta*s`; (c) keep counts as they
are (they are the data) but stop claiming that positions remove the literature channel.

**M2 — Tokens are per neuron, not per type; the `type_role` family is unattainable in tier A.** `bundle.py:95`
hashes `salt|dataset|version|source_id`, `:129-130` assigns one token per row: 2471/2471 (MANC) and 2378/2378
(MaleCNS) interneurons carry distinct tokens, so `cell_type` in tier A is a second unique id, equivalent to null.
The README (`bundle.py:226-227`, `public_blind/README.md:32-33`) says "cell types ... replaced by opaque tokens ...
consistent within a network", which reads as type-equivalence classes being preserved. Consequence in the evaluator:
`evaluator/evaluate.py:110-112` (`type_of` reads the bundle's `cell_type`) and `:176-181` map tokens through
`type_to_label` — no token ever matches, so `type_level_excitatory_recall` is 0.0 for every tier-A run (confirmed on
`baselines/results/eval/degree_topk.md` and on the example method: structural recall 0.5, type-level 0.0), contradicting
`PROTOCOL.md:55` ("credits same-type neurons such as contralateral copies") and the code's own note (`evaluate.py:203-204`
claims an "evaluator's own type table" that does not exist). Fix: decide one of (a) tokenise the *type name* (same
token for same-type neurons; document that type-frequency information is retained and that a token's frequency is a
weak fingerprint), or (b) keep per-neuron tokens and compute `type_role` from an evaluator-side type table (tier-B
`neurons.parquet` or the processed dataset). Update the README text either way. *Status at review time:* the
uncommitted working tree implements (b) — `bundle.py` writes a `cell_type` column into the private id maps and
`evaluate.py` reads it (`real_types`). That repairs the evaluator, but the README wording is unchanged, and every
tier-A evaluation under `baselines/results/eval/` predates the fix (type-level recall 0.0 is stale) and must be re-run
before the freeze.

**M3 — `method_args` is a smuggling channel and the run record omits it; the documented input verification does
not exist.** `run_method.py:68` forwards `--method-args` to the method's argv; `:77-80` records `method_file`,
`method_sha256`, `bundle`, `seed`, `runs` — not the args, not the environment handed over, not `MethodInfo.inputs_used`.
Demonstrated: `--method-args "--core 1 2 3"` arrived in `sys.argv` and left no trace in `run_record.json`.
`LEAKAGE_AUDIT.md:28-29` (generated at `leakage_check.py:148-149`) states the runner "verifies afterwards that none of
those paths were read by checking the method's declared inputs" — no such code exists anywhere. Fix: record
`method_args` and the exact environment; verify `inputs_used` is a subset of the bundle's files and fail otherwise;
correct the audit text (or implement the access log of B3 and make the sentence true).

**M4 — "Hash before evaluation" is documented, not enforced.** `evaluate.py:313-326` reads prediction files
directly and never looks at `run_record.json`; a prediction can be edited between run and evaluation; `results/runs/`
and `results/eval/` are siblings and excluded from the freeze (`freeze.py:30`). Fix: make the evaluator require a run
record (default `<prediction dir>/run_record.json`), refuse on `prediction_sha256` / `bundle_sha256` mismatch, and copy
the record's hashes into the evaluation output; have the runner write predictions read-only.

**M5 — PROTOCOL section 5 references artefacts that do not exist and an undefined comparison.** `PROTOCOL.md:68-72`
requires beating "every baseline in `baselines/results/`" and lying outside `baselines/results/null_distributions.md`;
neither `null_distributions.*` nor `baselines_summary.*` exists, `greedy_prune_sim` has no evaluation, and "beats" is
undefined for separate metric families with no aggregate (by design). Fix: define dominance per family (e.g. E-core
recall and I-slot not below any baseline, sufficiency pass, necessity accuracy = 1, empirical p < 0.01 against the
matched structural null), generate the files, then freeze.

**M6 — The library/doc leakage guard is incomplete and is itself an answer-bearing file.**
`tests/test_leakage_guard.py:18-25` lists 7/7 oracle types but only 3/7 MANC core body ids and 7/14 MaleCNS ids (the
contralateral copies are absent); 17 of the 34 type- or id-like tokens in `oracle.json` are covered.
`leakage_check.py:36-41` scans the *bundles* with the full oracle set, but `src/`, `docs/`, `README.md`, `LOG.md` are only
checked against the short list. The guard file holds all its tokens in clear text and is not in PROTOCOL's forbidden
list (`PROTOCOL.md:26-28`), so an LLM-based method that reads `tests/` obtains the answer. Fix: build the token list
from `oracle/oracle.json` at test time (types + every id under `core`, `core_contralateral_copies`, `other_circuits`,
`cross_connectome`) so the test file carries no token, and add `tests/test_leakage_guard.py` (or the whole
`benchmarks/dng100/oracle` import path) to the forbidden list. My repo-wide scan (excluding the declared
answer-bearing directories) found tokens only in `PHASE0_REPORT.md` section 13 (already forbidden), `goal1.md`
(forbidden), the node lists (complete tables, intended) and the guard itself.

**M7 — Evaluator magic numbers and a model mismatch, none stated in PROTOCOL.** `evaluate.py:46-47` (`RHYTHMIC = 0.5`,
analysis start 0.25 s), `:221` (necessity "abolished" = fraction rhythmic < 0.5), `:235` (sufficiency pass >= 0.5),
`:171` (compactness `within_10`), `:199` (`/ 2`), `:160` (the Jaccard *reference* depends on which inhibitory neuron
the prediction hit), `:167` (precision counts E3–E5, labels no other metric asks for), `:308-309` default
`t_end = 1.0` (used by all baseline evaluations) while `public_blind/model_config.json:16` hands methods `t_end 2.0`.
Impact: the functional verdict is computed under a model configuration different from the published one, and the
thresholds are discoverable only from code. Fix: an `evaluator_settings.json` (thresholds, seeds, t_end) referenced by
PROTOCOL.md and echoed in the bundle's `model_config.json`; Jaccard against the fixed modal circuit; either evaluate at
the published `t_end` or document the shortening in the bundle.

**M8 — The two MANC networks are the same network; cross-connectome credit between them is free.**
`manifest.json`: `networks/manc_v1.2.1/edges.parquet` and `networks/manc_v1.2.3/edges.parquet` have the same SHA-256;
the position -> body maps are identical; only tokens and a few annotations differ (readout 144 vs 142). Positions are
therefore consistent across the two networks although the README says tokens are not, and the `cross_connectome`
family (`evaluate.py:266-286`) rewards identity-by-position. Fix: independent permutations per network (B1) and a
sentence in PROTOCOL.md that the MANC pair is a re-annotation control, not a cross-connectome test; the meaningful
cross-connectome pair is MANC <-> MaleCNS.

### Minor

**m1** — README gives away `DynamicsClaim.rhythmic`: `bundle.py:207-208` / `public_blind/README.md:7-8` ("produces
rhythmic motor output in most parameter replicates"). Remove the sentence or stop scoring `rhythmic`.

**m2** — `BRAINIR_TOPK` is documented (`baselines/README.md`, `example_method.py:24`, `greedy_prune_sim.py` docstring)
but stripped by `SAFE_ENV_KEYS` (`run_method.py:37-39,58`); operators will reach for `--method-args` instead (M3).
Whitelist `BRAINIR_*` explicitly and record it.

**m3** — Free-text fields exist despite `prediction.py:6-7` ("no free-text 'paper says' fields"): `cell_type_claim`
(`:40`), `notes` (`:53`, 2000 chars), `description` (`:69`, 4000 chars). They are not scored, but they are also not
scanned. Cheap literature-use detector: the evaluator scans tier-A predictions for oracle type names / body ids and
disqualifies the run.

**m4** — `leakage_check.py:61-64` scans tier-A text for the core neurons' *body ids* (which cannot occur there) but not
for their *positions*; a README or JSON accidentally listing core positions would pass. `scan_parquet` (`:70-89`)
checks `cell_type` only, not `instance` / `hemilineage` of un-blinded roles. Load `tier_a_ids` and add positions to the
tier-A scan; scan every string column.

**m5** — The bundle copy is writable and shared by the per-network runs (`run_method.py:61-69`); `verify_bundle` runs
before, not after. Verify the copy after each run; set the copy read-only.

**m6** — Answer-shaped constants in baselines and nulls: the 2 E + 1 I composition (`random_matched.py:68-71`,
`recurrence_loop.py:100`, `null_distributions.py:10,50`) and `k = 3` mirror the published modal circuit. Acceptable for
baselines (it makes them stronger), but `baselines/README.md` should declare it as a paper-derived prior, and the
composition-free nulls (`uniform`, `two_hop`) must remain the ones an independence claim is tested against.

**m7** — `PROTOCOL.md:49` "evaluate.py is the only code that reads the oracle": `baselines/null_distributions.py:38`
and `cleanroom/leakage_check.py:35` read it too (both evaluator-side). Wording.

**m8** — Oracle, id maps and the salt are tracked in git (`git ls-files`). Consistent with the in-repo oracle design,
but the salt then adds nothing beyond `oracle.json` and rule 4 says "never commit tokens"; if the oracle ever moves out
of the repository, the salt must move with it. Note only. The salt value appears in no file outside `oracle/`.

**m9** — Retained labels: `hemilineage` is nulled for interneurons but kept for 52–55 % of the other roles;
`sub_class` for interneurons carries only coarse morphology codes (IR/BI/BR/CR/II/CI; two `fl` in v1.2.3). No
oracle-bearing value found; `soma_neuromere` and `side` are legitimately informative (section 3).

**m10** — `BLIND_ROLES` is a deny-list (`bundle.py:41`: tokenise `vnc_intrinsic`, `unknown`, null); every other role
keeps its cell type. The uncommitted `vocab.py` change adds a new role `vnc_unknown` (MaleCNS `vnc_tbc`, "to be
classified") that is not in the list, so after a re-ingest such bodies — which may well be interneurons — would keep
their release type names in tier A. Today's bundles contain no such role (checked), but the design is fragile. Fix:
make it an allow-list (labels kept only for `descending`, `vnc_motor`, `vnc_sensory`, `sensory_*`, `efferent`, `glia`)
and add a test that every role present in a tier-A bundle is either allow-listed or tokenised.

**m11** — Un-blinded types that the oracle mentions: two descending types and one motor type that appear in
oracle.json outside `labels` (DN-screen / wet-lab entries) are visible in tier A (`descending`, `vnc_motor` rows),
alongside the legitimate stimulus type. `leakage_check.py:36` scans only the seven label types. Not the mechanism, but
the scan should cover every type-like string in the oracle (minus the stimulus type) so that a future oracle addition
cannot silently become visible.

### Notes (checked, no problem found)

- Salt: 32 hex characters (128 bit, `secrets.token_hex(16)`), scheme `sha256(salt|dataset|version|body_id)[:10]`
  (`bundle.py:95`); not documented inside the bundle, not guessable, not present anywhere outside `oracle/`; tokens
  carry no ordering or type frequency (per-neuron). Token inversion is not a viable attack.
- `manifest.json`, `network.json`, `model_config.json`: provenance hashes, sign-row counts, ROI list, model settings —
  nothing answer-bearing. `stimulus.json` names the stimulus type and the left front-leg neuropil (task definition).
- `src/brainir` imports neither `benchmarks` nor `research`; `brainir.benchmark.bundle` knows the stimulus type, the
  readout rule, the paper's sign rule id and the "left-leg DNg100" stimulus choice (`bundle.py:39-40,82-91`) — all
  task definition, none of it the answer. `brainir.sim.prune` / `screen` constants (threshold 0.5, analysis start 0.25,
  200 iterations) are generic.
- What tier A hides relative to tier B is exactly: interneuron `cell_type`, `instance`, `hemilineage`, and body ids.
  Every other column is byte-for-byte the same information.

## 3. What an attacker recovers from tier A alone, and how

Using only `public_blind/` and pandas (no simulation), then checking candidates against the oracle:

- **Direct-target ranking.** Ranking interneurons by synapses received from the stimulus: E1 is the 3rd strongest
  direct target overall and the strongest *excitatory* direct target in all three networks; E5 is the 5th–8th overall
  (3rd–4th excitatory); E4 the 9th–18th (6th–9th excitatory). E2 and I1 receive no direct input from the stimulus;
  I2 is a weak direct target (rank 81–110). So a top-3 direct-target method (the example method, `degree_topk`) gets
  excitatory core recall 0.5 and never fills the inhibitory slot — matching the evaluations.
- **Reciprocity.** Among the 30 strongest direct targets, ordering reciprocal pairs by mutual synapse count puts the
  E1–E2 pair first (MaleCNS) or second (MANC). "Heaviest direct target plus its heaviest excitatory reciprocal partner"
  therefore yields E1 + E2 (excitatory core recall 1.0) in every network without simulation; this is essentially the
  `recurrence_loop` baseline. The inhibitory slot does not fall out of degree or reciprocity.
- **Retained labels.** All seven labelled neurons sit in the same neuromere as the stimulated leg (T1), six of seven on
  the left (the side named by the stimulus rule); they are large (74th–98th size percentile among interneurons) and
  high-degree (78th–99.5th in-degree percentile). Filtering to left-T1 interneurons leaves ~1060 candidates and 64–91
  direct targets, with E1 at rank 2. These are legitimate structural cues, but they show that the blinding hides names,
  not the neurons' salience.
- **With outside knowledge** (the tier-A threat model): position -> body id via the paper's node-list order (B1) or
  tier B (B2); body id via `size_voxels` and neuPrint (M1); E1/E2 via the unique mutual-count pair in the paper's
  connectivity figure (M1); the two MANC networks are linkable by position (M8).
- **Not recoverable:** the salt/tokens (128-bit random, per-neuron); anything from README/manifest/model_config beyond
  the `rhythmic` hint (m1).

## 4. What I ran

- Read: `CLAUDE.md`, `PROTOCOL.md`, `LEAKAGE_AUDIT.md`, `research/LOG.md` (D15, D19, D30–D39), `goal2.md` WS8/WS10/WS24
  and the review list, `PHASE1_REPORT.md` (status lines), every file of `public_blind/` and the tier-B README, all of
  `cleanroom/`, `evaluator/evaluate.py`, `oracle/oracle.py` and the *structure* of `oracle.json` (keys, labels, evidence
  fields; values not copied), `build_public_bundle.py`, `freeze.py`, `src/brainir/benchmark/*.py`, `src/brainir/paths.py`,
  `tests/test_leakage_guard.py`, `tests/test_baselines_contract.py` (import checks), `baselines/README.md`,
  `run_all_baselines.py`, heads of `greedy_prune_sim.py`, `recurrence_loop.py`, `random_matched.py`, `null_distributions.py`.
- Scratchpad script over the bundle parquet files: column inventory tier A vs B, token scheme verification, size/degree
  uniqueness, direct-target and reciprocity ranks of the oracle neurons (via `oracle/tier_a_ids/`), attribute percentiles,
  mutual-count uniqueness, MANC v1.2.1 vs v1.2.3 identity checks; order check of `tier_a_ids/` against `nodes/*.csv`.
- Scratchpad script comparing the guard's token list with `oracle.json` and scanning the repository (excluding declared
  answer-bearing directories, `data/`, `.venv`, `.git`) for oracle tokens; section-level localisation in
  `PHASE0_REPORT.md`, `PHASE1_REPORT.md`, `goal1.md`; grep for the salt value outside `oracle/`.
- Clean room: `cleanroom/run_method.py` with the example method on all three networks (about 2 s each; output to the
  scratchpad) and `evaluator/evaluate.py --no-simulation` on those predictions; the reviewer escape method through the
  runner on one network with `--method-args "--core 1 2 3"` (output to the scratchpad; it reads the oracle and prints
  only booleans and counts).
- `cleanroom/leakage_check.py` without `--write-audit` (PASS: 0 text hits, 0 parquet hits, manifests verify, guard passes),
  `pytest -m "not real_data" -q` (358 passed, 18 deselected, 54 s).
- `git tag`, `git ls-files`, `git status` for the freeze and tracking state; `git diff` of the concurrently edited
  files (answer tokens masked) to confirm which findings the uncommitted edits touch; re-verification of the positional
  order against the regenerated id maps. No simulation on real networks, no writes outside this report and the
  scratchpad, no access to `data/`.
