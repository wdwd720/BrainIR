# BrainIR prediction ledger: pre-registration, version 3 (run 3, exam 2: hemilineages)

Status: **version 3**, frozen by the git tag `ledger-prereg-v3`, which points at the commit holding `LOCK_prereg_v3.json` and
`LOCK_labelcode_h1.json` (written by `ledger/scripts/lock3.py prereg` and `lock3.py labelcode`, in that order, before the tag). The
label-code lock hashes the label side (kit v3, the label scripts, the gate script, the label core and their tests, the label plan
and session specs). The prereg lock hashes this file, `RUN3_PROMPT.md`, the unit list (`hl_units/`), the motor map (`motor_map/`), the Stage 0
diagnosis (`diag_v3/`), the gate and review files present at the freeze (`gates_v3/`, `reviews_v3/`), every earlier lock, and every
ledger code file (`lock2.CODE_GLOBS`): the prediction-side code (group screen, job kinds, runner, workflow, campaign builders, unit
groups, motor-pool rules, wiring baselines, table writer), the exam 2 scoring code and its tests, and the lock tool itself. Spec:
`RUN3_PROMPT.md`. Decisions: `LOG.md` L70+. Reviews: `reviews_v3/`.

**What v3 is.** A new exam on a new unit, the hemilineage, with its own predictions (h1), labels (h1), gate and unblinding flag.
Exam 1 (rulebooks v1, v2; predictions v1, v2; labels v1, v1.1, v2; results 1) is closed and unchanged. Where v3 reuses run 2's
machinery it says so; everything else here is new. A stranger should be able to run the exam from this text, the files it names
and the code its lock hashes.

---

## Part D. Disclosure

1. The published hemilineage results are public. Their authors' summaries may be in the training of the model that wrote this
   document and of the models that will read the papers. The user has read published outcomes for about six hemilineages (9A,
   12A, 8A, 21A, 5B, 6B) and did not repeat them. The blind is therefore **procedural**: every definition below is frozen before
   the first hemilineage simulation, and nothing is tuned afterwards.
2. Repository search for hemilineage activation outcomes already written down (`reviews_v3/HL_OUTCOME_LOCATIONS.md`): a fresh agent
   reported 29 locations with hemilineage names and a category only, never an outcome: 15 repository notes (exam 1 label notes and
   source lists naming 13A/13B, 9A and 12B; one literature note on 19A/19B) and 14 papers downloaded during exam 1's label
   collection (git-ignored). The orchestrator did not open any of them, and none is used for predictions. What the orchestrator
   knows from the list is which names occur near activation, silencing or function statements, and where.
3. Before this freeze no hemilineage group was simulated in any run. The only groups simulated in run 3 before the freeze are
   DNg100 (Stage 0 diagnosis; P7 regression), DNb08 and the random synthetic groups of P7 (pipeline test). The run registry (keys of
   every `results.pkl` under the data directory, the GitHub campaign manifests and tags) and the git history show it; the Stage 2
   reviewer checks it. The hemilineage campaign builders refuse to build a job until the tag `ledger-prereg-v3` exists.
4. The orchestrator knows exam 1's results (`results/RESULTS_1.md`), including that wiring baselines and the authors' model did
   poorly on descending neurons, and the Stage 0 diagnosis (`diag_v3/`; LOG L70, L72). Nothing about hemilineage outcomes informed
   any choice here.
5. Before this freeze the three main sources (Harris 2015, Soffers 2025, Cheong 2024) were downloaded into the git-ignored
   `data/ledger/sources_h1/` by run 2's mechanical downloader (no language model), their DOIs having been found from Crossref
   metadata with field selection (no abstract), and frame montages of their supplementary videos were made by a script. Nobody in
   the orchestrator's session opened any of these files or images; only counts and download status were read.
6. The location list's folder names (exam 1 session families) tie 13A, 13B and 12B to "grooming" and 9A to "walking_stopping"; the
   orchestrator and the rulebook auditor saw those names.

---

## Part U. Units and groups

**U1. Unit.** The hemilineage as annotated in the authors' full-cord network (MANC `hemilineage`, their node table; LOG L10). The
unit list is fixed here (`hl_units/UNITS_v1.csv`, made by `ledger/scripts/hl_units_v3.py` from annotations only): **43 units**,
every hemilineage label with at least one neuron with soma in T1-T3, except `TBD`. Three labels are merged units (`20A.22A`,
`20B.21B.22B`, `24B.25B`); five are lineages without an A/B assignment in the annotation (`17X`, `18X`, `21X`, `26X`, `27X`).

**U2. Transmitter class** (descriptive; used for the "by class" analysis): `motor` if at least half the thoracic members are motor
neurons (fly motor neurons are glutamatergic, so the transmitter rule alone would call them inhibitory); otherwise `excitatory`
if at least 60 % are cholinergic (predicted transmitter); `inhibitory` if at least 60 % are GABAergic or glutamatergic; otherwise
`mixed`. Result: 14 excitatory, 24 inhibitory, 5 motor, 0 mixed.

Thoracic counts (primary group), per segment, per side (`midline` = neither; only 00A and 00B), over all segments, postembryonic
(MANC birthtime `secondary` or `early_secondary`), transmitter make-up (thoracic members), motor neurons, class:

| unit | thoracic | T1 | T2 | T3 | L | R | all segments | postembryonic | ACh | GABA | Glu | other | MNs | class |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 00A | 228 | 87 | 88 | 53 | 0 | 0 | 257 | 214 | 0 | 205 | 23 | 0 | 0 | inhibitory |
| 00B | 14 | 4 | 7 | 3 | 0 | 0 | 58 | 0 | 0 | 3 | 11 | 0 | 0 | inhibitory |
| 01A | 341 | 123 | 126 | 92 | 170 | 171 | 405 | 319 | 340 | 0 | 1 | 0 | 0 | excitatory |
| 01B | 479 | 165 | 162 | 152 | 240 | 239 | 487 | 449 | 6 | 468 | 5 | 0 | 0 | inhibitory |
| 02A | 244 | 85 | 82 | 77 | 121 | 123 | 310 | 216 | 7 | 0 | 234 | 3 | 0 | inhibitory |
| 03A | 572 | 192 | 191 | 189 | 284 | 288 | 572 | 550 | 572 | 0 | 0 | 0 | 0 | excitatory |
| 03B | 407 | 161 | 216 | 30 | 204 | 203 | 492 | 369 | 14 | 304 | 86 | 3 | 26 | inhibitory |
| 04A | 12 | 4 | 4 | 4 | 6 | 6 | 12 | 6 | 12 | 0 | 0 | 0 | 0 | excitatory |
| 04B | 562 | 195 | 187 | 180 | 278 | 284 | 562 | 536 | 547 | 0 | 15 | 0 | 0 | excitatory |
| 05B | 302 | 99 | 111 | 92 | 149 | 153 | 380 | 234 | 36 | 264 | 1 | 1 | 0 | inhibitory |
| 06A | 456 | 161 | 145 | 150 | 227 | 229 | 604 | 426 | 0 | 348 | 108 | 0 | 4 | inhibitory |
| 06B | 429 | 139 | 187 | 103 | 215 | 214 | 451 | 387 | 2 | 391 | 35 | 1 | 0 | inhibitory |
| 07B | 501 | 154 | 183 | 164 | 251 | 250 | 631 | 446 | 461 | 0 | 39 | 1 | 0 | excitatory |
| 08A | 353 | 110 | 141 | 102 | 175 | 178 | 353 | 327 | 0 | 9 | 344 | 0 | 14 | inhibitory |
| 08B | 488 | 172 | 162 | 154 | 244 | 244 | 496 | 447 | 474 | 4 | 10 | 0 | 0 | excitatory |
| 09A | 499 | 165 | 170 | 164 | 248 | 251 | 529 | 471 | 0 | 487 | 12 | 0 | 0 | inhibitory |
| 09B | 152 | 42 | 58 | 52 | 76 | 76 | 226 | 118 | 46 | 0 | 106 | 0 | 0 | inhibitory |
| 10B | 441 | 144 | 151 | 146 | 221 | 220 | 443 | 381 | 438 | 0 | 3 | 0 | 0 | excitatory |
| 11A | 192 | 87 | 105 | 0 | 95 | 97 | 192 | 190 | 162 | 2 | 28 | 0 | 0 | excitatory |
| 11B | 167 | 14 | 149 | 4 | 83 | 84 | 169 | 159 | 2 | 139 | 26 | 0 | 0 | inhibitory |
| 12A | 297 | 173 | 122 | 2 | 147 | 150 | 317 | 275 | 268 | 0 | 29 | 0 | 0 | excitatory |
| 12B | 554 | 195 | 185 | 174 | 277 | 277 | 556 | 518 | 0 | 528 | 26 | 0 | 0 | inhibitory |
| 13A | 429 | 140 | 145 | 144 | 215 | 214 | 429 | 366 | 0 | 377 | 52 | 0 | 0 | inhibitory |
| 13B | 429 | 141 | 143 | 145 | 215 | 214 | 435 | 397 | 0 | 394 | 35 | 0 | 0 | inhibitory |
| 14A | 486 | 163 | 162 | 161 | 242 | 244 | 504 | 456 | 0 | 6 | 480 | 0 | 0 | inhibitory |
| 14B | 39 | 17 | 10 | 12 | 19 | 20 | 39 | 21 | 0 | 18 | 21 | 0 | 0 | inhibitory |
| 15B | 162 | 60 | 55 | 47 | 81 | 81 | 162 | 150 | 3 | 11 | 140 | 8 | 162 | motor |
| 16B | 509 | 190 | 166 | 153 | 255 | 254 | 513 | 457 | 2 | 7 | 493 | 7 | 60 | inhibitory |
| 17A | 377 | 58 | 223 | 96 | 188 | 189 | 387 | 359 | 328 | 0 | 49 | 0 | 0 | excitatory |
| 17B | 26 | 2 | 12 | 12 | 13 | 13 | 44 | 12 | 0 | 26 | 0 | 0 | 0 | inhibitory |
| 17X | 14 | 4 | 4 | 6 | 7 | 7 | 14 | 6 | 0 | 0 | 14 | 0 | 14 | motor |
| 18B | 160 | 10 | 67 | 83 | 80 | 80 | 188 | 129 | 150 | 0 | 10 | 0 | 0 | excitatory |
| 18X | 2 | 0 | 2 | 0 | 1 | 1 | 2 | 0 | 1 | 0 | 1 | 0 | 2 | motor |
| 19A | 605 | 202 | 210 | 193 | 297 | 308 | 629 | 557 | 48 | 501 | 53 | 3 | 6 | inhibitory |
| 19B | 340 | 42 | 188 | 110 | 170 | 170 | 426 | 306 | 334 | 0 | 5 | 1 | 0 | excitatory |
| 20A.22A | 812 | 282 | 276 | 254 | 407 | 405 | 812 | 812 | 784 | 0 | 28 | 0 | 0 | excitatory |
| 20B.21B.22B | 31 | 11 | 10 | 10 | 16 | 15 | 31 | 19 | 0 | 0 | 30 | 1 | 31 | motor |
| 21A | 409 | 131 | 138 | 140 | 200 | 209 | 411 | 327 | 48 | 1 | 360 | 0 | 0 | inhibitory |
| 21X | 4 | 4 | 0 | 0 | 2 | 2 | 4 | 0 | 0 | 0 | 4 | 0 | 0 | inhibitory |
| 23B | 416 | 143 | 146 | 127 | 208 | 208 | 440 | 402 | 411 | 0 | 5 | 0 | 0 | excitatory |
| 24B.25B | 50 | 18 | 16 | 16 | 24 | 26 | 50 | 50 | 1 | 0 | 49 | 0 | 50 | motor |
| 26X | 18 | 6 | 6 | 6 | 9 | 9 | 18 | 0 | 0 | 17 | 1 | 0 | 0 | inhibitory |
| 27X | 56 | 28 | 14 | 14 | 28 | 28 | 58 | 0 | 7 | 21 | 28 | 0 | 0 | inhibitory |

Total 13,064 thoracic members. Birthtime is missing for 4 thoracic members (they are in no postembryonic group).

**U3. Primary group.** Every neuron of the unit with soma in T1, T2 or T3, both sides (and midline), every class (intrinsic,
ascending, motor, efferent). **Stimulation:** every member receives the same current, whatever its transmitter; outputs keep the
sign the model already assigns (acetylcholine +, GABA and glutamate -, as in every earlier arm). This mirrors an experiment that
depolarises every labelled cell. Code: `groups_h1.members(table, birthtime, unit, "primary")`.

**U4. Sensitivity groups (declared now; secondary, descriptive):** S-all (every neuron of the unit in any segment, abdominal
included); S-post (thoracic members with birthtime `secondary` or `early_secondary`); S-T1, S-T2, S-T3 (one thoracic segment at a
time); S-L, S-R (one side only, by soma side; midline members excluded). A sensitivity group identical in membership to the
primary group is not simulated again (the primary arm's seeds 0..3 are used); a group with no member is not run and its predicted
row is **all zeros** (no stimulation, no movement), marked `empty` in its table.

**U5. Truth units (how a label reaches a unit).** A record names a hemilineage as its source does (`9A`, `09A`, "hemilineage 9A",
`20A/22A`). The assembly script maps it by name only: number zero-padded to two digits, letter upper-case, then (a) an exact unit
name (`09A`, `17X`, ...) maps to that unit; (b) a component of a merged unit (`20A`, `22A`; `20B`, `21B`, `22B`; `24B`, `25B`), or
a name joining only components of one merged unit (`20A/22A`), maps to the merged unit, and its records count as records of that
unit (so components whose records disagree make the cell `conflicting`, T4); (c) any other name (a hemilineage with no thoracic
member here, a lineage without a hemilineage letter, a name spanning two units) maps to no unit: its records are kept, listed in
the assembly report and enter no matrix. `21A` is its own unit; `21B` belongs to `20B.21B.22B`. A label never maps to an `X` unit
unless the source names that `X` unit.

---

## Part P. Prediction arms (exam 2, "h1")

**P1. H-M, the authors' model (primary arm).** The full-cord procedure of LOG L14 / PREREG v1 3.7, unchanged: the authors'
full-cord network exactly (23,532 neurons; `networks.full_cord()`), the autotuned screen (start current 128, at most 10 runs,
`n_active_lower = 100`, `n_active_upper = 7667`, `n_high_fr_upper = 1022`, high-rate threshold 100 Hz, activity threshold 0.01 Hz
after 0.25 s), T = 1.0 s, **seeds 0..15**, main score on the 329 module-labelled leg motor neurons, per-leg scores as in B3.
**Only the member list changes.** Code: `typescreen_v3.screen_group_v3` (run 1's `screen_group` line for line, plus read-outs),
job kind `group_v3` (`jobs_v3`). Read-out additions, none of which feeds back into tuning, acceptance or any run 1 field:
(a) `mn`: for the read-out run, the peak rate after 0.25 s of each of the 732 motor neurons (float64, the screen's own window and
threshold), the indices of those above 0.01 Hz, and their full traces (float16, compressed); (b) every replicate records the current
and classification of its last simulated run (`final_current`, `final_verdict`); (c) a replicate that is never accepted stores the
read-out (legs, `mn`) of its last simulated run in `final_run_extras`. Hemilineage jobs keep no `readout_traces` and no `watch` (the
`mn` traces cover every motor neuron). Run 1's digest is unchanged; `digest_v3` also covers (a)-(c). **Tuner outcome per
replicate:** `accepted`, `too_weak` (last run too weak) or `saturating` (last run too strong); reported as counts over a unit's
replicates and treated as the model's answer: no adjustment of the procedure for any group. Declared now: `accepted` means "at least
100 neurons active, the stimulated members included, and within the saturation limits", not "the unit drives the network"; units
with 100 or more members are therefore rarely `too_weak`. For a replicate whose bisection brackets a steep transition (as the
50-neuron P7 group did: 72 against 5,194 active neurons between two close currents), the last run is near-silent or network-wide
by the parity of the bisection; that read-out is the model's answer too.

**P2. H-D, dose.** The same network and read-out at fixed currents 128, 256, 384 and 512 (every member the same current), no
tuning, T = 1.0 s, seeds 0..7 (job kind `fixed_v3`: run 1's `fixed_run` with the `mn` read-out). The tuner's classification of the
run is recorded for information.

**P3. H-S, wiring only (eight baselines, no fitted parameter).** For group G with indicator vector s and the model's signed count
matrix W (post x pre; the matrix H-M simulates), the value of pool P is the mean over P's motor neurons of (W^k s): **k = 0**
(membership: the share of the pool's motor neurons that are in the group; units containing motor neurons move them directly in
H-M, and this baseline captures that triviality), k = 1 (direct), 2 (two-hop) and 3 (three-hop), each signed (W) and unsigned
(|W|): arms `H-S-k0`, `H-S-k1-signed`, `H-S-k1-unsigned`, ..., `H-S-k3-unsigned`; and **`H-S-lin`, the steady state of the
linearised model**: x = (I - A)^-1 (a * s) with A = diag(a) Wb, the model's mean size-scaled gains a (`mean_neuron_params`) and its
own coupling (`scaled_weights`, b = 0.03), the pool value being the mean of x over the pool's motor neurons. The linear operator's
spectral radius is 34.33 (`diag_v3/LINEAR_DIAG.json`, `ledger/scripts/diag_v3_linear.py`, wiring only), so this fixed point exists
(I - A factorises; test residual 8e-11) but is unstable under the linear dynamics; it is computed anyway, as the prompt asks, with
one sparse LU factorisation (COLAMD) and one solve per unit. Code: `groups_h1.hs_tables`, `hs_linear_values`.

**P4. H-C, controls.** H-M on five degree-preserving rewirings (seeds 101-105) and five class shuffles (seeds 201-205) of the full
cord, built with run 1's generators applied to the full cord (`groups_h1.control_network` -> `controls.build`: degree-preserving
target swaps, 10 per edge; the authors' five-class shuffle), **seeds 0..3** (four, not 16: runner hours and wall-clock; controls are
descriptive). Each control is compared with **H-M-s0-3**, the H-M table computed from seeds 0..3 only, so seed count does not
separate them.

**P5. H-X, other animals: not run** (optional; first in the drop order). No verified full-cord network of another animal exists in
the repository, and building and verifying one would compete with the exam for time and quota. Stated, not hidden.

**P6. Sensitivity groups (U4):** the H-M procedure, seeds 0..3, compared with H-M-s0-3.

**P7. Pipeline test before the freeze (allowed groups only).** Campaign `p7-run3`: DNg100 (16 seeds) with the B3 read-out (watch =
the two DNg100, read-out traces) plus `mn` — the **procedure regression**: run 1 digests identical to run 2's `g3v2item5` jobs (the
B3 procedure on DNg100, seeds 0..15); DNb08 (16 seeds); five random synthetic groups (`numpy.random.default_rng(20261311)`, sizes
50, 150, 300, 600 and 1,000 drawn without replacement from all thoracic intrinsic neurons; seeds 0..3); two fixed-current jobs on
the 150-neuron group (128 and 512). It checks that the read-out and the Part M formulas run end to end, through the run 3 runner and
workflow. No threshold is set from it (Part M needs none). Output: `gates_v3/P7_REGRESSION.json` and a P7 table outside the
predictions folder.

**P8. Platform.** GitHub Actions hosted runners with run 2's pins and numerics environment. The frozen run 2 runner and workflow
cannot run the new job kinds, so run 3 uses copies with one change each (`gha_runner3.py` imports `jobs_v3.run_job`;
`.github/workflows/ledger-gha3.yml` runs on tags `gha3-*`; published with `gha3.py publish3`, collected with `collect3`). The run 3
trust gate (`gates_v3/TRUST_GATE_v3.json`: run 2's 100 locked jobs re-run through the run 2 workflow) passed, 100 of 100 identical;
the run 3 workflow is covered by the P7 regression (run 2's locked DNg100 digests reproduced through it) and by P9.3. The Mac is the
fallback under the same checks. At most 300 runner-hours (estimate for every arm here: about 70).

**P9. Gates before the predictions lock (RUN3_PROMPT Stage 2).**
1. Full cord accepted: on the build used (unchanged since run 2), G3 v2 items 1-3 and 5 still pass on the stored DNg100 runs
   (`g3v2_evaluate.py`), and P7's DNg100 jobs reproduce item 5's digests.
2. Procedure unchanged: the P7 regression (identical run 1 digests on DNg100 through the run 3 runner).
3. Determinism: 50 H-M jobs drawn with `default_rng(20261312)` from the H-M campaign, re-run as a separate GitHub campaign, give
   identical `digest_v3`.
4. Trust gate (P8).
5. Independent review: a fresh reviewer audits the group builder, the motor map, the prediction rules, the run registry and the git
   history, and confirms that no hemilineage simulation ran before the freeze.
An arm whose own campaign is incomplete (any job missing or in error after one re-run of the missing jobs) is not locked; the reason
is written down.

**P10. Outputs.** For each arm, written by `ledger/scripts/predict_h1.py`: `predictions_h1/<arm>/predicted.csv` (one row per unit:
`unit`, the twelve primary dimensions `d1 d2 d3 d4 d5 d6 d7p d10 d11 d13 d14 d15`, `n_members`, `n_replicates`, tuner outcome
counts), `pools.csv` (per unit, replicate and pool: fraction of active motor neurons and per-leg rhythm), `provenance.json` (campaign,
SHA-256 of the raw results file that holds the compressed motor-neuron traces, keys, digests). Arms: H-M, H-M-s0-3, H-D-128 ...
H-D-512, H-C-rewire-101 ... H-C-classshuffle-205, H-M-S-all ... H-M-S-R, H-S-k0 ... H-S-k3-unsigned, H-S-lin. **Locks:** `LOCK_predictions_h1.json` (`lock3.py predictions`) holds
the primary arms, H-M, H-M-s0-3 and all eight H-S arms (the lock tool refuses a subset), and is committed and OTS-stamped **before
the first h1 label session starts** (the lock tool refuses afterwards; gate condition 1 checks the commit times); tag
`ledger-predictions-h1`. `LOCK_predictions_h1b.json` (`lock3.py predictions-b`) holds the descriptive arms (H-D, H-C, sensitivity
groups), each locked or named with a reason, before `LOCK_labels_h1.json`. **Publishing order:** every simulation campaign of
Stages 2 and 4 (H-M, the determinism sample, H-D, H-C, the sensitivity groups, R3, R4) is published right after this freeze, before
any prediction file is committed; prediction files and both prediction locks are then committed locally only, and nothing is
pushed until `LOCK_labels_h1.json` exists (`gha3.py publish3` refuses while HEAD holds exam 2 predictions without that lock).

---

## Part V. The shared vocabulary

**V1. Dimensions** (a reader codes each for the activated flies of a record: `yes`, `no`, `unclear` or `not_assessed`):

| # | dimension | coded yes when the source reports, during activation |
|---|---|---|
| 1 | any visible movement | any movement of any body part |
| 2 | front legs move | movement of one or both front legs |
| 3 | middle legs move | movement of one or both middle legs |
| 4 | hind legs move | movement of one or both hind legs |
| 5 | legs flex or the body lowers, held | a sustained (not repeated) flexion of legs, or the body lowered and held |
| 6 | legs extend or the body rises, held | a sustained extension of legs, or the body raised and held |
| 7 | repeated leg movement without coordination | rhythmic or repeated leg movements that the source does not describe as coordinated walking |
| 8 | coordinated walking | walking or coordinated stepping (in decapitated flies too) |
| 9 | grooming-like leg rubbing | leg rubbing or grooming-like leg movements |
| 10 | jump or takeoff | a jump, takeoff or escape jump |
| 11 | any wing movement | any movement of the wings |
| 12 | wings raised or opened, held | wings held raised, extended or opened |
| 13 | wing buzzing or flight-like beating | wing vibration, buzzing or flight-like wing beating |
| 14 | haltere movement | haltere movement |
| 15 | abdomen movement | abdominal movement (bending, pumping, curling) |

`yes` = the source reports the effect in activated flies (any penetrance; penetrance recorded where given). `no` = the source
assessed that body part or behaviour and reports no such effect (including "no phenotype" statements that cover it). `unclear` =
the source's statement does not decide. `not_assessed` = the source does not say.

**V2. Primary dimensions (12):** 1, 2, 3, 4, 5, 6, **7'**, 10, 11, 13, 14, 15. **7'** (repeated leg movement, coordinated or not) is
derived **per record, from the final record's dimensions 7 and 8, before any consensus** and then enters the consensus like every
other dimension: `yes` if 7 or 8 is `yes`; else `no` if both are `no`; else `unclear` if either is `unclear`; else `not_assessed`.

**V3. Declared gaps (dropped from the primary analysis, still coded):** 8 alone (coordinated walking needs inter-leg coupling,
which the Stage 0 diagnosis shows the build does not reproduce; it enters only through 7'), 9 (grooming is a multi-joint sequence
with no validated motor-pool rule), 12 (a held wing posture depends on combinations of steering muscles that the motor map cannot
order). Neck motor neurons (no head in the preparation) and the 6 unannotated `xm` motor neurons feed no dimension.

---

## Part M. From model output to the vocabulary

**M1. Motor map** (`motor_map/MOTOR_MAP_v1.csv`, `ledger/scripts/motor_map_v3.py`; annotations and muscle names only; checked by
a fresh reviewer before this freeze, `reviews_v3/MOTOR_MAP_REVIEW.md`, whose corrections were applied: the 4 `STTMm` are
satellite motor neurons of the jump muscle, not sternotrochanter ones; tension muscles named apart from steering ones): each of the
732 motor neurons -> body part (front, middle, hind leg; wing; haltere; abdomen; neck; unknown), segment, side (the soma's; correct
for every leg motor neuron, unused for the other pools), action (leg: the MANC motor module, e.g. tibia flexor, femur/trochanter
extensor; jump muscle (TTMn, STTMm); wing: DLM or DVM power, steering, tension, unassigned; haltere: power, steering, unassigned;
abdominal) and pools:

| pool | members |
|---|---|
| any_body | every leg (incl. the jump-muscle MNs), wing, haltere and abdominal motor neuron (702); recorded, not used by a dimension |
| front_leg / middle_leg / hind_leg | leg motor neurons of that segment (141 / 125 / 131; the middle leg includes the 6 jump-muscle MNs) |
| per-leg flexor (T1L ... T3R) | tibia flexor + femur/trochanter flexor modules of that segment and side |
| per-leg extensor (T1L ... T3R) | tibia extensor + femur/trochanter extensor modules of that segment and side (MANC leg modules only; the jump-muscle MNs and the 24 middle- and 38 hind-leg MNs without a module are in no flexor/extensor pool) |
| jump | the jump-muscle (TTM) motor neurons: TTMn (2) and STTMm (4) |
| wing_any | wing motor neurons (60; the jump-muscle MNs, annotated in the wing subclass, are not wing MNs here) |
| wing_power | DLMn + DVMn (24) |
| haltere | haltere motor neurons (16) |
| abdomen | abdominal motor neurons (229) |

**M2. Per replicate** (the accepted run's read-out; for a replicate never accepted, its last simulated run's read-out, P1):
- act(P) = fraction of P's motor neurons whose rate exceeds 0.01 Hz at some time after 0.25 s (the screen's own activity rule; the
  `mn` read-out); 0 for an empty pool;
- rhy(leg) = the B3 per-leg rhythm score of that leg (T1L ... T3R: `network_oscillation_score`, prominence 0.05, over the leg's
  active module-labelled motor neurons; 0 when none is active; between 0 and 1).

**M3. Predicted value of each primary dimension** = the mean over the arm's replicates of the per-replicate value
(`groups_h1.replicate_dims`):

| dim | per-replicate value |
|---|---|
| 1 | max over the six body-part pools (front_leg, middle_leg, hind_leg, wing_any, haltere, abdomen) of act(pool): any body part moves |
| 2, 3, 4 | act(front_leg), act(middle_leg), act(hind_leg) |
| 5 | mean over the six legs of max(0, act(leg flexor) - act(leg extensor)) x (1 - rhy(leg)) |
| 6 | mean over the six legs of max(0, act(leg extensor) - act(leg flexor)) x (1 - rhy(leg)) |
| 7' | max over the six legs of rhy(leg) |
| 10 | act(jump) |
| 11 | act(wing_any) |
| 13 | act(wing_power) |
| 14 | act(haltere) |
| 15 | act(abdomen) (all 229 abdominal MNs, the terminal segments included; no variant) |

Held and rhythmic movement are told apart by the leg's rhythm score: a fully rhythmic leg contributes nothing to 5 or 6, a silent
or tonically active leg contributes fully. Flexion and extension are compared through the difference of the active fractions.

**M4. H-S values:** dims 2-4, 10, 11, 13, 14, 15 = the pool value of P3 for the same pools, dim 1 = the maximum of the six body-part
pool values; **dims 5, 6 and 7' get the constant 0**
(a wiring baseline cannot tell held from rhythmic movement; after standardisation a constant contributes nothing; intended).

**M5. Calibration.** None is needed: M2-M3 use only the screen's existing activity rule and rhythm score, and the primary statistic
uses continuous values (no threshold). The P7 test checks the code, not thresholds.

**M6. What the model can and cannot predict for inhibitory units.** The model is silent at rest (no spontaneous activity), and a
GABA or glutamate member can only lower the activity of its targets. Stimulating a unit drives motor neurons only through its
cholinergic members (the excitatory minority of a unit classed inhibitory counts) or through motor neurons that are members. So
for a unit whose members are all inhibitory and include no motor neuron, every predicted dimension is 0, and for units classed
inhibitory most predictions will be small. The model cannot predict effects that arise from releasing spontaneous activity
(disinhibition), rebound, or muscle relaxation. Inhibitory units that contain motor neurons (03B, 06A, 08A, 16B, 19A) move through
those motor neurons; the motor units (15B, 17X, 18X, 20B.21B.22B, 24B.25B) are mostly motor neurons.

---

## Part T. Truth

**T1. Sources.** Harris et al. 2015 (eLife, thermogenetic activation of hemilineages in decapitated flies) and Soffers et al. 2025
(eLife, a lineage driver library with optogenetic activation in decapitated and intact flies), plus every other study that
activates a whole hemilineage, found by blind search (T6). Registered by DOI; downloaded by run 2's mechanical downloader; given to
rooms as full text, tables, figure images and legends; supplementary videos as frame montages with their legends, made by a script
(the orchestrator does not look at them). The papers' own words are the primary evidence. Each source is one "lab" in T4.

**T2. Coding.** One record per (source, hemilineage, driver or clone, preparation, effector) experiment **that the source itself
performed** (an outcome a source only cites or restates from another study gives no record), with every V1 dimension coded `yes`,
`no`, `unclear` or `not_assessed`, and: preparation (`decapitated`, `intact`, `other`), effector, record type (`whole_two_sided` =
the driver or method targets the whole hemilineage, all thoracic segments the source covers and both sides, as the source describes
it; `clonal`; `one_sided` (one side or one segment by design); `partial_or_mixed` = the source says the driver covers only part of the
hemilineage or also labels other cells that may matter; a reader chooses `partial_or_mixed` over `whole_two_sided` only when the
source says so, and quotes it), penetrance where given, driver coverage notes, a locator and a quote of at most 25 words per record,
an optional free-text "other" observation, and `saw_model_prediction` (T7). Kit v3 (`kit_v3/PROTOCOL.md`) is the readers' version of
these rules.

**T3. Two readings, adjudication.** Two independent readings per source, working hemilineage by hemilineage, each blind to the
other; a reading of a large source may be split by hemilineage scope over several sessions (the two main sources: two halves of the
name list each), and a record written by two sessions of the same reading is kept once. **Pairing** (`labels_h1/core.py`): the
two readings' records are matched on (source, unit per U5 or the normalised name when no unit, preparation, effector class:
thermogenetic, optogenetic, other); where several records share that key, they are matched by driver name after normalisation
(lower case, letters and digits only), and a single leftover record on each side is paired. Every record of a reading carries its
source's registry DOI (a reader's typing variant is counted, not a new source). Matched pairs with any differing field among
d1-d15 and `record_type`, and records present in one reading only, go to an adjudicator (run 2's design; reading order by a coin,
`default_rng(20261306)`, per disputed record), who decides each disputed field (cells from the cell vocabulary, `record_type` from
the four record types), and for an unmatched record whether it exists in the source (and, if so, its full coding). The final record
takes the agreed fields and the adjudicated ones and must pass the schema; one repair round (`labels3_rooms.py repair`) is allowed
for a session whose records fail the schema.

**T4. Consensus (per unit, per dimension, including 7'), by script, over any number of sources:**
1. Only final records of type `whole_two_sided` that are **eligible** enter the primary consensus: no session that produced the
   record (either reader, the adjudicator) breached, and the record carries no sighting (`clonal`, `one_sided`, `partial_or_mixed`
   form a secondary consensus by the same rules). A breaching reader's or adjudicator's session contributes nothing, and its scope is
   read or adjudicated again by a new session (run 2's rule).
2. **Preparation precedence, across all sources:** if any eligible record of the cell from a `decapitated` preparation is `yes` or
   `no`, only the decapitated records are used for that cell; otherwise all eligible records are used. Reason: the model has no
   head, RUN3_PROMPT states "decapitated observations outrank intact ones" without restricting it to one lab, and an intact-only
   observation is the weaker evidence about a headless preparation.
3. Per source, over the records kept by step 2: `yes` and `no` both present -> the source's cell is `conflicting`; only `yes` ->
   `yes`; only `no` -> `no`; else `unclear` if any `unclear`, else `not_assessed`.
4. Across sources: any source `conflicting`, or sources with `yes`/`no` that disagree -> `conflicting` (leaves the primary
   analysis); all sources with `yes`/`no` agree -> that value; none has `yes`/`no` -> `unclear` if any source is `unclear`, else
   `not_assessed`.
A cell is **coded** if its consensus is `yes` or `no`. Per-source matrices (steps 1-3, by the same preparation rule applied within
the source) are kept beside the consensus (`labels_h1/lab_<source>.csv`).

**T5. External check.** Cheong et al. 2024 (the MANC premotor paper) publishes a summary of Harris 2015. One session codes that
summary in the same vocabulary; it is used only to measure agreement with our coding of Harris (Cohen's kappa over primary cells
both code `yes`/`no`). Never truth.

**T6. Searches.** Fresh sessions with web tools search for other whole-hemilineage activation studies: by hemilineage name, by
driver, and by papers citing Harris 2015 or Soffers 2025; a lead qualifies only if it reports its **own** activation of a whole
hemilineage (or named hemilineages) in adult flies; `labels3_leads.py` registers, by script, every lead from a non-breaching search
session with a DOI, `adult_activation` = `yes` and `whole_hemilineage` = `yes` or `unclear` that is neither a known source nor a banned
one (the readers decide the record type); registered sources are downloaded and read by two readers like the main sources. One search round; a second only if the first adds a source with at least one `whole_two_sided` record.

**T7. Banned content and sightings.** Readers must not open connectome-simulation papers or this repository (run 2's deny rules
and audit, extended to the dedicated simulation papers of exam 1 and to any source whose title or abstract reports a network
simulation of hemilineages). A **sighting** is seeing a network-simulation prediction of a hemilineage's activation phenotype
(descriptions of connectivity are not sightings); a record with a sighting is excluded from every consensus. A session **breached** if
the transcript audit (run 2's, applied to run 3's sessions) finds an opened banned location (this repository, a prediction file, a
banned paper or host); all its records are excluded.

**T8. Machinery** (run 2's, unchanged unless stated): rooms launcher, outside-read block, canary (re-run once before the first h1
session, because the deny rules were extended after the last canary), mechanical downloader, session contract (dispositions per
source), the transcript audit (L3 of v2, with the dedicated tokens extended to simulation papers), the label review, the same model
as run 2, quota thresholds by slowing down. The **verification sample**: after assembly and before the labels lock, 30 final
`whole_two_sided` **eligible** records drawn with `default_rng(20261313)` from all such records sorted by record id (all of them if
fewer); a
fresh verifier, blind to the recorded values, codes their twelve primary dimensions from the source; a cell is in error when the
record's `yes`/`no` differs from the verifier's or the verifier marks it `cannot_verify`; error rate = cells in error / cells the
records code `yes`/`no`. Label-side code is new (`ledger/scripts/labels3_*.py`, `ledger/scripts/gate_h1.py`,
`labels_h1/core.py`, `kit_v3/`) and is locked (`LOCK_labelcode_h1.json`) at this freeze, together with the label plan and session
specs. The kit holds the dimension list, the cell vocabulary and a
hemilineage name list with synonyms, alphabetical and prediction-free.

**T9. Lock.** `LOCK_labels_h1.json` (`lock3.py labels`; consensus, per-source matrices, secondary consensus, final records, raw
readings, sessions, verification, review), tag `ledger-labels-h1`, OTS; then the three h1 locks (predictions, descriptive
predictions, labels) and their tags are pushed.

---

## Part S. Statistic, decisions, secondary analyses

**S1. Matrices.** Predicted matrix P (43 units x 12 primary dimensions) from an arm (M3, M4); each column standardised across the 43
units (mean 0, population sd 1; a column with sd 0 becomes 0). Observed matrix O: consensus cells, yes = 1, no = 0, missing
otherwise; each column centred over the units where that column is coded **within the set analysed** (the primary analysis: all units
with at least 3 coded primary dimensions; by class, the ceiling and each source: the units of that subset or source with at least 3
coded primary dimensions).

**S2. Identification (primary statistic).** For each unit h with **at least 3 coded primary dimensions**, score every candidate k of
the 43 units by `s_h(k) = sum over h's coded dimensions d of P[k, d] x O[h, d]`. Percentile rank
`pr(h) = (#{k != h: s_h(k) < s_h(h)} + 0.5 x #{k != h: s_h(k) = s_h(h)}) / 42` (1 = the true match scored highest; ties count half).
**The statistic is the mean of pr(h).** Scores within 1e-12 count as tied. Chance is reported as the permutation-null mean and
its 2.5-97.5 % range (for the mean rank, top-1 and top-3), not as 0.5: when the units with 3 or more coded dimensions share a pattern
(e.g. all move), the null mean exceeds 0.5 (audit finding 5).
- p-value: 10,000 permutations (`default_rng(20261301)`) of the hemilineage labels among those units (each permutation gives every
  such unit the observed vector of another; candidates and P unchanged); one-sided, p = (1 + #{perm >= observed}) / 10,001.
- 95 % interval: 10,000 bootstrap resamples (`default_rng(20261302)`) of those units, percentile interval of the mean.
- Top-1 and top-3: the true match's rank position `1 + #{k: s_h(k) > s_h(h)} + 0.5 x #{k != h: s_h(k) = s_h(h)}` is at most 1 or at
  most 3.
- The p-value, both bootstrap intervals and the chance band depend on the random draws as the frozen code makes them (unit order,
  draw calls, percentile method); they come only from the frozen pipeline. The independent recomputation of S6 checks the mean rank,
  top-1 and top-3.

**S3. Decision rules.**
- **Underpowered** if fewer than 20 units have at least 3 coded primary dimensions: report descriptively, claim nothing.
- **"The model predicts"** if the one-sided p < 0.05 and the interval's lower bound exceeds both 0.5 and the permutation-null mean
  (arm H-M; stricter than the prompt's "> 0.5", for the reason in S2).
- **"The simulation adds value beyond wiring"** only if "the model predicts" holds **and** H-M beats the best H-S baseline on a paired
  bootstrap: the best baseline is the one of the eight with the highest statistic on the same units (chosen after seeing it, which
  favours wiring; values within 1e-12 of the best count as tied, and a tie goes to the first in the order k0, k1 signed, k1 unsigned,
  ..., k3 unsigned, lin); 10,000 paired resamples
  (`default_rng(20261303)`) of those units; the 95 % percentile interval of (H-M minus best H-S) has a lower bound > 0. Without
  "predicts", a positive interval is reported only as "H-M ranks above the best wiring baseline". The scorer refuses unless all eight
  H-S arms are locked.

**S4. Secondary analyses (descriptive):**
1. The ceiling: each source's matrix as the predicted matrix (yes = 1, no = 0, missing = the column mean, then standardised)
   identifying another source's units, in both directions, on units both code with at least 3 primary dimensions.
2. Each source separately as truth (S2 on that source's matrix).
3. Per-dimension AUROC (predicted value against the coded cells over units) and a pooled AUROC (all coded cells, standardised
   predictions).
4. By class (U2): S2 restricted to excitatory, inhibitory and motor units (candidates still all 43).
5. H-M-s0-3; H-D per strength; H-C per control network; the sensitivity groups as alternative predicted matrices; the eight H-S
   baselines.
6. The secondary consensus (clonal, one-sided, partial or mixed records) as truth.
7. Agreement: Cohen's kappa between the two readings (primary cells both code `yes`/`no`, matched record pairs; kappa = 1 when chance
   agreement is 1), with the agreement over the full cell vocabulary and the record match rate per source beside it; our Harris coding
   against the Cheong summary (T5); between sources (cells both code).

**S5. The gate (RUN3_PROMPT section 9), computed from label files and unit names only; every condition must hold:**
1. All locks verify in a clean checkout (`lock3.py check` for the run 3 locks, with run 3's amendment rows only; `lock2.py check` for
   the v1 and v2 locks, the v1 locks also with `lock.py check`); from commit times only, the label-code lock and the primary
   predictions lock precede the first h1 label session, and the descriptive predictions lock precedes the labels lock.
2. No session that contributed a final record (either reader, the adjudicator) breached (T7), and every such session was audited.
3. The label review has no blocker, and the verification sample's error rate (T8) is at most 10 %.
4. Agreement between the two readings has a Cohen's kappa of at least 0.7 over coded cells: (matched record pair, primary dimension)
   cells that both readings code `yes` or `no`, over all matched pairs of non-breaching sessions.
5. At least 20 units have at least 3 coded primary dimensions.
6. A fresh reviewer signs a checklist confirming 1-5, that nothing has been joined (no prediction file was read by label-side code
   or put next to a label), that no hemilineage simulation predates the freeze, and that every honoured row of `AMENDMENTS_v3.jsonl`
   is a code bug fix.
**If any condition fails, nothing is unblinded**; the handoff reports label-only numbers. The gate runs twice (first run, then the
reviewer's check, then the second run whose file `gates_v3/UNBLINDING_GATE_h1_run2.json` the scoring requires).

**S6. Unblinding.** A flag file of its own, `research/ledger/UNBLIND_h1.json` (exam 1's flag is retired and never read), naming the
three h1 locks (predictions, descriptive predictions, labels) with their SHA-256; the gate's second report must have checked the
same lock hashes. The frozen pipeline (`score_h1.py --run primary`, then `--run secondary`) runs once each; a crash (an uncaught
exception, or a refusal of the pipeline after the flag exists, e.g. a file-format refusal) is fixed once in the reading code only,
recorded with `lock3.py amend --crash-fix` and logged, never a rule change. A fresh subagent recomputes the mean rank, top-1 and top-3
with its own code; they agree if they differ by at most 1e-9; if they do not, the frozen pipeline's numbers stand, both are reported
and the difference is examined in the exploratory section. The flag is retired afterwards (moved, unchanged, to
`results/run3/UNBLIND_h1_used.json`). Results: `results/RESULTS_2.md` (RUN3_PROMPT section 9), tag `ledger-scorecard-h1`.

**S7. Code and file formats.** `ledger/src/brainir_ledger/scoring_h1/` (S1-S4; refuses without `UNBLIND_h1.json`, a passing second
gate run and matching locks), `ledger/scripts/score_h1.py`, tests on synthetic data with known answers (`test_scoring_h1.py`) and a
test that fails if any label-side code references a prediction file (`test_label_side_isolation_h1.py`, which scans run 3's and run
2's label code). The scoring reads `predictions_h1/<arm>/predicted.csv` (must hold exactly the 43 units, no missing value) and
`labels_h1/consensus.csv`, `labels_h1/lab_<source>.csv`, `labels_h1/consensus_secondary.csv` (column `unit`, then `d1` ... `d15` and
`d7p`, values `yes`, `no`, `unclear`, `not_assessed`, `conflicting`; every unit in the unit list, rows may be absent for units without
records). Any departure from these formats is refused, never repaired; the scorer also requires the consensus files to carry
`d1` ... `d15` and `d7p`, and records the SHA-256 of its own code and the git HEAD in each result file.

---

## Part R. Reliability study (descriptive, no labels; RUN3_PROMPT section 8)

Question: when the same procedure gives different answers for two flies, is that the animals, the reconstruction or the simulation?
- **R1 (existing data).** B1r against B2r (predictions v2): Spearman of `primary_score` over all common types; over types non-zero in
  at least one fly; over types whose cross-fly match is high-confidence (every MaleCNS member of the type maps to it through a curated body
  match, `mancBodyid`, rather than only through a type-name annotation, `mancType`; B2's own mapping, `arms.malecns_network`); band agreement; top-10 and top-30 overlap. The ceiling: within-fly split-half agreement (seeds 0-7 vs 8-15 of each arm's
  replicates; Spearman of the halves' type means).
- **R2 (wiring).** The anatomical baselines S1-S7 of PREREG v1 3.5 computed for the same types on both flies; cross-fly Spearman of
  each baseline against the cross-fly Spearman of the simulation (B1r vs B2r).
- **R3 (noise equivalence).** The B1r screen (tuner v2, K = 1) on MANC with multiplicative weight noise (each nonzero count times
  1 + e, e ~ Normal(0, sigma), clipped at -0.99, sign kept) at sigma = 0.05, 0.10, 0.20, noise seeds 1, 2, 3, model seeds 0..3 (four,
  for runner hours); agreement (Spearman of type scores, 4-seed means) with the unperturbed B1r restricted to seeds 0..3; the noise
  level at which this agreement equals the cross-fly agreement (linear interpolation between levels; "below 5 %" or "above 20 %"
  if outside).
- **R4 (left vs right).** If the descending-neuron side annotation passes a check (at least 80 % of B1r types have at least one member
  on each side by `somaSide`, falling back to `rootSide` where `somaSide` is missing; descending neurons have no soma in the nerve
  cord, so their side is the root side of the authors' full-cord node table, matched by bodyId), the B1r screen with only the left
  members of each type, reading out the left front-leg motor neurons (72), and only the right members with the right front-leg
  motor neurons (72) (seeds 0..3); Spearman of the two sides' type scores over the types with members on both sides. Checked before
  this freeze from annotations alone: 308 of 321 B1r types (96 %) have members on both sides, every member has a root side, so R4
  runs (13 one-sided types are left out).
- Outputs locked as `LOCK_reliability_v1.json` (`lock3.py reliability`), tag `ledger-reliability-v1`. R3 and R4 simulate descending-
  neuron types (not hemilineages), after this freeze; their builders are new files.

---

## Part X. Process

- **Amendments** (`lock3.py amend`, run 3's own ledger `AMENDMENTS_v3.jsonl`; run 2's ledger never counts for a run 3 lock): code bug
  fixes only, recorded before the commit; never rules, labels or predictions; never a file a v1 or v2 lock hashes; once
  `LOCK_predictions_h1.json` exists, never the prediction-side or scoring code; once the first h1 label session has started, never the
  label code or the kit; after `UNBLIND_h1.json` exists, only the crash fix of S6. `lock3.py check` honours a row only if it obeys these
  rules both with the flags it recorded and with the commit times of the predictions lock, the flag and the first session; a row is
  timed by the later of its own time and the commit that first holds it, an uncommitted row never counts, a recorded unblinding counts
  only after the flag was committed, and the lock tool and its tests are never amended (a change to them is a new version).
- **Locks** are written once and never edited (exactly one commit touches each lock file; gate condition 1 checks it); lock commits
  are never rebased (their commit times are evidence).
- **Gate files** (`gates_v3/`) are written once; a later check writes a new file.
- **Pre-mortems** in the LOG before each irreversible step (this freeze, each lock, the unblinding).
- **Drop order if time runs short** (RUN3_PROMPT section 11): H-X (already not run), R3, H-D, R4, H-C, the post-mortem, R2. Never
  dropped: this rulebook, H-M and H-S, the labels, the gate.
- **Exam 1 post-mortem** (`results/POSTMORTEM_1.md`): exploratory throughout; it explains exam 1 and does not rescue it.
- **After unblinding nothing moves**; extra analyses only in a section marked exploratory.

**Departures from RUN3_PROMPT (each with its reason above):** (1) the membership baseline H-S-k0 is added (P3); (2) the
linearised steady state is computed although it is an unstable fixed point (P3); (3) H-C and the sensitivity groups use seeds 0..3
with a matched H-M-s0-3 comparator (P4, P6); (4) H-X is not run (P5); (5) the vocabulary is finalised with 7' = 7 or 8 and drops 8
alone, 9 and 12 (V2, V3); (6) the statistic uses units with at least 3 coded primary dimensions (S2); (7) decapitated precedence is
applied across sources (T4); (8) "the model predicts" also needs the interval above the permutation-null mean, and "beyond wiring"
needs "predicts" (S3); (9) the predictions lock is split into a primary lock before the label sessions and a descriptive lock
before the labels lock (P10); (10) the label code and kit are locked at the freeze, not later (Status); (11) dimension 1 is the
maximum over body-part pools (M3).

| version | date | change | data existing at the time |
|---|---|---|---|
| 3 | 2026-11-21 | exam 2 on hemilineages (Parts D, U, P, V, M, T, S, R, X) | exam 1 complete; no hemilineage simulation, prediction or label |
