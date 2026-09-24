# Adversarial synthetic suite — design note (review G follow-up)

**Module and tests**
- Module: `src/brainir/discovery/adversarial.py`, suite id `synthetic-adversarial-v1`.
- Tests: `tests/test_adversarial.py`.

**Who built it.** The review G reviewer, as the third party that review G recommended. The composer of BrainIR v1 had no part in it.

**Rules it follows**
- It imports no method and reads no benchmark data.
- It is **truth-bearing**. Add `brainir.discovery.adversarial` to `TRUTH_BEARING_MODULES` in `tests/test_budget_integrity.py` when it is
  imported into the main repository. `tests/test_adversarial.py` already checks that no method module mentions it.

## 1. What it is for

The regular synthetic suites plant one mechanism per instance and score a result by keep-only sufficiency. That scoring could not see
the failures review G found:
- a latent backup chosen instead of the circuit that runs;
- an essential gate lost to group silencing;
- a distributed drive reported as a compact core;
- a function that exists on only part of the parameter draws.

This suite plants those structures on purpose. Each instance carries a truth that says which answer is right *in the intact network*.
The scorer reports correctness, confident errors and calibration.

## 2. Construction (common to all traps)

- **Background.**
  - Each instance starts from `synthetic.build_instance(InstanceSpec(base_family, n_total, seed, ...))`, so the background, the planted
    motif and the criterion are those of the public generator.
  - Trap nodes are background neurons whose edges are all cut before they are rewired.
  - Signs stay column-consistent, and synapse counts are integers.
  - Default: no generator complications. They may add sufficient sets the adversarial truth does not list; use `suite_audit` if you
    turn them on.
- **Parameters.**
  - Every numeric trap parameter is drawn from `default_rng([seed, salt])` inside the range in `PARAM_RANGES` (section 4).
  - Trap nodes are chosen by a second seeded stream.
  - A fresh seed therefore gives a new background, new trap nodes and new weights.
  - `AdversarialSpec.knobs` pins any parameter. The draw still happens, so pinning one parameter never shifts the others.
  - The drawn values are stored in the truth as `params`.
- **Variant.** `AdversarialSpec.family` names the variant, which fixes the base family and hence the criterion. If it is `None`, the
  variant is drawn from the seed.
- **Label.** Readable by default: `adv__<trap>__<variant>__n<N>__s<seed>`. **Held-out and final suites must set `name=` to an
  anonymised token.** The label becomes the instance directory name and the manifest's `instance` field.
- **Verification.** `verify_adversarial(inst, seeds=range(8))` simulates the trap's defining properties (section 4) and records the
  measured truth. `build_verified(spec, max_tries=8)` re-draws the seed until an instance verifies, keeping the variant.
- **Export.** `export_adversarial(inst, ver, root, salt)` calls `synthetic.export_instance` unchanged:
  - public bundle with node-order variants `main` and `order1`, and tokens salted by `salt`;
  - it then adds the adversarial truth to `root/truth/<label>.json` only;
  - the public files keep the regular suite's format and ids, so nothing in them marks an instance as adversarial;
  - `criterion.json` carries the (calibrated) criterion, as every instance does.

## 3. Thresholds and truth fields

**Thresholds**

| constant | value | meaning |
|---|---|---|
| `PASS_MIN` | 0.8 | "works": pass fraction ≥ 0.8 over the verification seeds |
| `FAIL_MAX` | 0.2 | "breaks"; also the **essential** threshold, as in `synthetic.verify_instance` |
| `SILENT_HZ` | 0.05 Hz | "silent": median over seeds of the mean rate in the criterion's analysis window |
| `ACTIVE_HZ` | 1 Hz | "active", and "participating" in the scorer |
| `CONFIDENT_P` | 0.85 | a core is confident when all its members have P ≥ 0.85 |
| — | seeds 0–7 | verification |
| `CALIBRATION_SEEDS` | 1000–1011 | build-time calibration |
| `SCORE_SEEDS` | 5500–5507 | scorer default: outside the methods' < 5000 and the tournament's 5000–5003 |

**Truth fields.** `inst.truth["adversarial"]` uses canonical nodes. After export, `truth["networks"][name]["adversarial"]` holds every
node field in that network's public positions.

| field | meaning |
|---|---|
| `mechanism` | the set(s) the intact network actually uses: the designed set joined with every measured-essential node (section 3a) |
| `acceptable` | the cores that count as correct (exact match): the designed core joined with every measured-essential node (section 3a). Empty for `distributed_drive`, where no compact core exists. `alternatives_positions` and `core_positions` (the regular tournament scorer's fields) follow `acceptable`, or `mechanism` if it is empty. |
| `acceptable_designed`, `mechanism_designed`, `definition` | the sets as the trap was designed, before the essential rule; and the name of the rule applied (`acceptable-contains-essential/v2`) |
| `essential` / `non_essential` / `ambiguous` | measured single-silencing pass ≤ 0.2 / ≥ 0.8 / in between. Measured for the mechanism and the contested nodes only (at most 40 nodes). |
| `silence_pass`, `rates_hz` | measured silencing pass fraction, and median intact mean rate, of those nodes |
| `latent_backups`, `silent_members` | keep-only-sufficient sets the intact network does not use, and their silent nodes |
| `fragile_alternatives` | sufficient on only part of the draws; active but not relied on |
| `degenerate` | `{flag, min_set_size, fraction_needed, membership_frequency}` |
| `subset_of_draws` | `{flag, intact_pass, copy_keep_only_pass, union_keep_only_pass}` |
| `contested` | the named trap nodes `{name: node}` |
| `targets` | each contested node's membership target for calibration: 1 member, 0 non-member, a frequency for interchangeable relays, `None` where undefined |
| `exchangeable` | groups of functionally interchangeable nodes |
| `params`, `checks`, `verified` | at the top level of the truth file |

## 3a. Decision: every acceptable core contains every measured-essential node

Decided 2026-09-24 on the coordinator's question.

**The rule** (`DEFINITION = "acceptable-contains-essential/v2"`), the same for every trap:
- Every acceptable core and every mechanism set is the designed set joined with every node whose single silencing breaks the intact
  function (measured silencing pass ≤ `FAIL_MAX` = 0.2 on the verification seeds), whatever that node's role in the trap.
- Every essential node is a calibration target 1.
- For a degenerate instance (no acceptable core), a correct result must also contain every essential node, besides flagging
  degeneracy. This is vacuous in the current design, because no relay is essential.

**Why.**
- These traps define the mechanism *of the intact network*. A neuron whose silencing alone destroys the function is part of that
  mechanism, whatever it does: it may drive the function, or it may keep something else from disrupting it.
- The rule is not new:
  - `masked_gate` already put its essential gate S into the acceptable core;
  - the public generator's winner-take-all truth includes its context inhibitor;
  - v1 defines context members E = {x : σ({x}) < 1/2} as part of a candidate mechanism;
  - review G finding 1 recommends that a candidate lacking an essential neuron be inadmissible.
- The first definition applied that principle to `masked_gate` but not to `identical_decoy`. There, releasing the decoy copy of a
  negative-feedback controller overdrives the band's upper edge, so the gate and latch that hold the copy down are essential. The truth
  listed them as essential yet left them out of the acceptable core.
- Under that first definition, a method that followed the essential-consistency principle was scored wrong, and `confident_wrong` when
  confident. The harness's generic `success_intact` accepted the same answer. The two now agree.

**Scope.** I measured which nodes fall outside the designed core, over 88 builds (all 22 variants × 4 seeds, n = 60):
- **Essential:** the gate and latch of `identical_decoy/nfc_band` (4 of 4 builds). No other variant had any.
- **Ambiguous** (0.2 < σ < 0.8): no variant had any.

The rule therefore changes the acceptable core of `identical_decoy/nfc_band` only. For every other variant it is a no-op on these
builds, but it is applied everywhere.

**What changed**
- **Generator.** `verify_adversarial` applies the rule after measuring essentiality; the designed sets are kept, so re-verification is
  idempotent.
- **Migration.** `normalize_truth_network(truth_network)` migrates an entry exported before the rule, in public positions:
  - it is pure and idempotent, and keeps other alternatives (for example ones added by a suite audit) after the migrated ones;
  - on my 13 old end-to-end truth files it changed exactly the `identical_decoy/nfc_band` entry, in both node orders.
- **Scorer.** `score_adversarial` applies the migration to every truth it scores, so old and new truths are scored identically.

**Not changed.**
- Latent backups, silent members, fragile alternatives and every trap's design are unchanged.
- Ambiguous nodes are neither required nor accepted. None occurred outside a core in the 88 builds. If one does, a result that includes
  it is not an exact match, and the scorer reports it in `extra_members`. A harness that wants tolerance can accept extras that belong
  to `ambiguous`.

## 4. Traps

Parameter ranges are inclusive. Integer ranges are synapse counts. In the checks, "ko" is keep-only and "sil" is silencing in the
intact network.

### 4.1 `latent_backup`

**Design.** A backup that is smaller than the planted mechanism and sufficient in keep-only. An inhibitory gate G, driven by the planted
mechanism, keeps it silent in the intact network. Silencing the planted mechanism turns G off, and the backup takes over.

**Variants**

| variant | base | backup |
|---|---|---|
| `band` | feedforward chain | 1 or 2 neurons; the head is gated |
| `band_overlap` | feedforward chain | a gated head that drives the chain's output member; the backup = {head, output member} shares that member |
| `band_active_head` | feedforward chain | an *active*, ungated head drives a gated relay. This defeats a check that asks only whether any member is active. |
| `rhythm_delayed` | 5-neuron delayed inhibitory oscillator | a 2-neuron E–I pair behind a gate driven by a bistable latch that a planted excitatory member switches on |
| `rhythm_ring` | 4-neuron ring | as `rhythm_delayed` |

**Ranges**

| parameter | range |
|---|---|
| `backup_size` | {1, 2} |
| `backup_drive` | 40–60 |
| `backup_relay` | 45–60 |
| `backup_out` | 25–35 |
| `gate_source` | any planted excitatory member (overlap: not the output member) |
| `gate_in` | 40–60 |
| `gate_out` | 120–200 |
| `latch_in` | 50–70 |
| `latch_self` | 58–70 |
| `decoy_self`, `decoy_ei`, `decoy_ie` | 95–105 each |
| `decoy_drive` | 46–54 |
| `decoy_out` | 25–35 |

**Checks.**
- intact ≥ 0.8;
- ko(planted) ≥ 0.8 and ko(backup) ≥ 0.8;
- the backup's silent members are silent;
- **compensation**: sil(planted members not in the backup) ≥ 0.8;
- `band_active_head` also requires the head to be active.

**Correct.** The planted mechanism. Returning a latent backup is the failure.

### 4.2 `masked_gate`

**Design.**
- Drivers D (1–3 neurons, stimulus-driven, optionally recurrent: "strong recurrent excitation") drive a relay X that would break the
  criterion.
- An inhibitory gate S (stimulus-driven) holds X silent.
- S is essential alone. Silencing {S} ∪ D passes, so group silencing that puts S with its drivers clears it.
- Keep-only never sees X, because X is silent.

**Variants** (X's target and sign)

| variant | X acts on |
|---|---|
| `nfc_band` | the readout, overdriving it past the upper band edge |
| `ffd_band` | the readout, inhibiting it below the lower edge |
| `ei_rhythm`, `dio_rhythm` | the rhythm's inhibitor, driving it tonically |
| `integrator_ramp` | the readout, flattening the relative slope |
| `memory_persistence` | the latch, which X inhibits. The drivers are recurrent and self-sustaining, and S is also driven by the latch, so it stays on after the pulse. |
| `wta_selectivity` | readout group b |

**Ranges**

| parameter | range |
|---|---|
| `n_drivers` | {1, 2, 3} |
| `driver_rec` | 0 with probability 1/3, else 40–70 (persistence: 55–70 always) |
| `driver_drive` | 50–70 |
| `driver_to_x` | 30–50 |
| `gate_drive` | 50–70 |
| `gate_factor` | 1.4–2.2 (S→X = round(factor × n_drivers × driver_to_x)) |
| `x_out` | 30–60 |
| `gate_from_latch` | 50–70 |

**Checks.**
- intact ≥ 0.8;
- ko(motif ∪ {S}) ≥ 0.8;
- X silent;
- sil({S}) ≤ 0.2;
- **masking**: sil({S} ∪ D) ≥ 0.8.

**Correct.** The generator's planted core plus S. For winner-take-all that is {A, IA} + S.

### 4.3 `distributed_drive`

**Design.**
- The planted chain is removed.
- N weak parallel relays (stimulus → relay → every readout neuron) drive the readout into the band.
- `lo` is calibrated at build time: it is the median keep-only readout with k* = round(q·N) random relays (6 calibration seeds). So about
  k* relays are needed, and no small set suffices.
- **Variants.**
  - `identical`: the relays are interchangeable.
  - `jittered`: relay outputs carry a relative sd of 0.1–0.35.

**Ranges**

| parameter | range |
|---|---|
| `n_relays` | 12–32 (capped by the free background neurons) |
| `relay_drive` | 5–8 |
| `relay_out` | 5–7 |
| `fraction_needed` q | 0.5–0.8 |
| `jitter` | 0.1–0.35 (0 for `identical`) |

**Checks.**
- intact ≥ 0.8;
- ko(all relays) ≥ 0.8;
- ko(the strongest 60 % of k* relays) ≤ 0.2 (no compact subset);
- three relays each non-essential (sil ≥ 0.8).

**Correct.** The result must flag degeneracy. Every compact core is an arbitrary subset. `membership_frequency` = k*/N per relay for
`identical`, and is left undefined for `jittered`.

### 4.4 `subset_of_draws`

**Design.** c exchangeable copies of a motif at a marginal parameter. None is sufficient on most draws, and the intact network works on
only part of the draws.

**Variants**
- `latch_persistence`: self-exciting latches.
- `ei_rhythm`: E–I pairs.

**Ranges**

| parameter | range |
|---|---|
| `copies` | {2, 3} |
| `latch_self` | 36–37 |
| `ei_self` | 42–46 |

**Checks.** intact pass between 0.25 and 0.92; each of the first two copies ko ≤ 0.65.

**Correct.** The union of the copies. The copies are exchangeable, so their probabilities should be equal. `subset_of_draws.intact_pass`
is the benchmark for any claimed fidelity.

### 4.5 `identical_decoy`

**Design.**
- A copy of the planted motif with the same internal, drive and output counts, plus `extra_drive` stimulus synapses, so that the copy
  can win a structural ordering.
- The copy is kept silent by a gate driven by a bistable latch that a planted excitatory member switches on. The latch holds the gate on
  whatever the source's rate, and it never switches on when the planted mechanism is silenced.

**Variants:** `ei_rhythm`, `nfc_band`, `memory_persistence`, `ffd_band`.

**Ranges**

| parameter | range |
|---|---|
| `extra_drive` | 0–12 (`ei_rhythm`: 0–5; more drive takes an E–I copy out of its limit cycle) |
| `gate_in` | 40–60 |
| `gate_out` | 120–200 |
| `latch_in` | 50–70 |
| `latch_self` | 58–70 |

**Checks.** intact ≥ 0.8; ko(planted) ≥ 0.8; ko(decoy) ≥ 0.8; decoy silent.

**Correct.** The planted motif, plus every essential node (section 3a). In `nfc_band` those are the gate and the latch: releasing the
decoy overdrives the band's upper edge, so they are essential there. The decoy is a latent backup, and a calibrated method gives it a low
probability.

### 4.6 `fragile_vs_robust`

**Design.** A smaller implementation that is sufficient on only part of the draws, next to a robust larger one. The intact network
relies on the robust one: silencing it fails on some draws, while silencing the fragile one never matters.

**Variants**
- `two_impl_rhythm`: the generator's E–I pair + ring, with the E–I self-excitation lowered.
- `band`: a single strongly driven relay beside the planted chain.
  - Its readout drive dominates the background's input to the readout.
  - `lo` is the (1 − target) quantile of the relay-driven readout, pooled over keep-only of the relay and over the intact network
    without the chain (12 calibration seeds each).

**Ranges**

| parameter | range |
|---|---|
| `fragile_self` | 46–53 |
| `fragile_drive` | 40–60 |
| `fragile_out` | 12–20 |
| `target_pass` | 0.4–0.7 |

**Checks.**
- intact ≥ 0.8;
- ko(robust) ≥ 0.9;
- ko(fragile) between 0.2 and 0.9;
- sil(robust) ≤ 0.85 (the network relies on it);
- sil(fragile) ≥ 0.9.

**Correct.** The robust implementation. The fragile set is active, not latent. Its calibration target is 0.

## 5. Scorer (`score_adversarial(result, truth_network, problem=None, seeds=None)`)

**Inputs.**
- `result`: a DiscoveryResult or its `to_dict()`.
- `truth_network`: `truth["networks"][name]`.
- With `problem` (the network's DiscoveryProblem), the simulation fields are computed on `seeds` (default 5500–5507).

**Outputs**

| field | definition |
|---|---|
| `correct` | the core equals an acceptable core, which contains every essential node (section 3a). For a degenerate instance, the result must flag degeneracy and contain every essential node. The scorer first migrates the truth with `normalize_truth_network`, so truths exported before section 3a are scored the same way. |
| `exact`, `contains_mechanism`, `extra_members`, `missing_members` | lenient variants of `correct` |
| `latent_backup_returned` | a latent backup is a subset of the core |
| `latent_members_in_core` | silent trap nodes in the core |
| `fragile_returned` | a fragile alternative is a subset of the core |
| `essential_recall`, `essential_missed` | fraction of the truth-essential nodes in the core |
| `participation` | with `problem`: the median intact mean rate of every core member, the minimum, and the fraction ≥ 1 Hz |
| `core_keep_only_pass`, `intact_pass`, `core_frequency_hz`, `intact_frequency_hz` | with `problem`, on fresh seeds |
| `fidelity_error` | the result's claimed keep-only pass fraction minus the measured one |
| `brier_contested`, `calibration_items` | `[p, target, node]` over the contested nodes, the acceptable cores and the returned core. A missing probability counts as 0; targets `None` are skipped. |
| `confident` | every core member at P ≥ 0.85 |
| `confident_wrong` | confident and not correct |
| `degenerate_flagged` | the diagnostics carry `degenerate`, `distributed` or `no_compact_mechanism`, either as a truthy key or in `diagnostics["flags"]` (a list, dict or string). **Methods should use this convention to report "no compact mechanism".** |
| `exchangeable_gap` | the largest probability difference inside a group of interchangeable nodes |
| `essential_claims` | the result's essential claims against the measured silencing pass: correct / wrong / ambiguous (0.2 < σ < 0.8) / unknown |

`summarize_adversarial(scores)` pools the scores:
- per trap: the rates of correct, confident_wrong and latent_backup_returned; mean essential recall, participation, contested Brier and
  exchangeable gap;
- a reliability table of all calibration items, in bins [0, 0.05), [0.05, 0.3), [0.3, 0.6), [0.6, 0.85) and [0.85, 1].

## 6. Default design and calibration

`adversarial_specs(n_per_trap=1, sizes=(60, 150, 1500), seed0=0)` gives every variant at every size: 21 variants × 3 sizes = 63 specs.
Together they cover activity band, rhythm, ramp, persistence and selectivity. The readout has 12 neurons up to n = 200, 20 up to 1,000
and 40 above.

**Verification rates** of the final ranges, from my own seeds; each build uses 8 verification seeds:

| trap | variant | n = 60 | n = 150 | median build + verify (s, n = 60 / 150) |
|---|---|---|---|---|
| latent_backup | band / band_active_head / band_overlap | 5/5, 5/5, 8/8 | 4/4, 4/4, 4/4 | 4 / 8 |
| latent_backup | rhythm_delayed / rhythm_ring | 8/8, 7/8 | 4/4, 4/4 | 19 / 26, 11 / 20 |
| masked_gate | nfc_band, ffd_band, ei_rhythm, dio_rhythm, integrator_ramp, memory_persistence | 5/5, 8/8, 5/5, 5/5, 5/5, 5/5 | 4/4 each | 3–14 / 6–21 |
| masked_gate | wta_selectivity | 5/5 | 2/4 (the base winner-take-all fails to select on some seeds; rejected by `intact`) | 6 / 10 |
| distributed_drive | identical / jittered | 8/8, 8/8 | 4/4, 4/4 | 9–10 / 16–21 |
| subset_of_draws | latch_persistence / ei_rhythm | 7/8, 8/8 | 4/4, 4/4 | 3–7 / 8–12 |
| identical_decoy | ei_rhythm, nfc_band, memory_persistence, ffd_band | 8/8 each | 4/4 each | 4–9 / 6–13 |
| fragile_vs_robust | two_impl_rhythm / band | 5/5, 7/8 | 4/4, 3/4 | 11 / 20, 4 / 8 |

**Totals.** 226 of 233 builds verify: 146 of 149 at n = 60 and 80 of 84 at n = 150 (97 %). `build_verified` absorbs the rest by
re-drawing the seed. Variants whose code changed during calibration are counted only from their re-runs under the final code.

**Spot check at n = 1,500** (one seed per trap, readout of 40). 7 of 8 verified on the first seed:
- latent_backup/band, latent_backup/rhythm_ring, masked_gate/ei_rhythm, masked_gate/nfc_band, distributed_drive/identical,
  subset_of_draws/latch_persistence and identical_decoy/ffd_band all verified;
- fragile_vs_robust/two_impl_rhythm missed one check by one seed (sil(robust) 0.875 against 0.85) and would be re-drawn.

A build with verification takes 30–160 s at this size, on one CPU.

**Commands** (run from the clean room; my calibration script, not a deliverable):
- `build_verified(AdversarialSpec(trap, variant, n_total=n, seed=s))` for seeds 100–104 and 200–207 (n = 60), 300–307 and 600–607
  (n = 60, final ranges), 400–403 (n = 150) and 500 (n = 1,500).

## 7. End-to-end check (the path the harness will run)

**Setup.**
- One fresh instance per chosen variant, n = 60, seeds 7000–7051: 13 instances.
- `build_verified` → `export_adversarial` → `brainir_v1` (budget 1,000, seed 0, network `main`, inside `truth_guard`) →
  `score_adversarial(result, truth_network, problem, seeds=5500–5503)`.
- v1 is the code reviewed in `G_adversarial.md` (sha256 `9ca36c4d…`), before its promised fixes.

**Results.** 4 of 13 correct, and 8 of 13 confident and wrong, under the section 3a definition. Under the first definition it was 3 of
13 correct: the `identical_decoy/nfc_band` run was then scored wrong.

| trap | outcome |
|---|---|
| latent_backup (band, band_active_head, rhythm_ring) | 3/3 confident and wrong. v1 returned the silent backup (core participation 8e-5 to 9e-5 Hz), essential recall 0. |
| masked_gate (nfc_band, integrator_ramp, memory_persistence) | 3/3 confident and wrong. The gate was missed; essential recall 0.5–0.67. |
| distributed_drive/identical | not flagged, so wrong; exchangeable gap 0.87 |
| subset_of_draws | ei_rhythm: one copy returned at high confidence; its true keep-only pass was 0.25 against a claimed 1.0 (`fidelity_error` 0.75). latch_persistence: wrong, not confident. |
| identical_decoy | both correct. For nfc_band, v1 returned motif ∪ {gate, latch}, the section 3a core; the first definition had scored it wrong. |
| fragile_vs_robust | two_impl_rhythm correct. **band confident and wrong: v1 returned the fragile relay.** Its true pass was 0.75 against a claimed 1.0. |

**Pooled reliability.** Probabilities ≥ 0.85 were right 54 % of the time (n = 28). Probabilities around 0.15 were attached to members
85 % of the time (n = 16).

**Status.** These are single runs, reported to show that the harness path works end to end. They are not a measurement of v1.

## 8. Tests

`uv run --no-sync pytest tests/test_adversarial.py -q`: **27 passed in 22 s.** The tests cover:
- the section 3a rule, for every trap in both node orders, plus `identical_decoy/nfc_band`: acceptable cores and mechanism sets contain
  every essential node, essential targets are 1, and exported truth is a fixed point of the migration;
- the reported case: motif ∪ {gate, latch} is correct, and the motif alone is confident and wrong;
- `normalize_truth_network` on an old-style entry: pure, idempotent, migrated correctly, audit-added alternatives kept, and old and new
  truths scored identically;
- every trap building, verifying and exporting, with the public files free of truth and of the trap name;
- truth consistency in both node orders;
- parameters within their documented ranges, a fresh seed giving a different network, and knobs pinning one parameter;
- labels and the default design covering all traps, variants and five criteria;
- the scorer's definitions on hand-made results, and its simulation fields and summary;
- static checks that the module imports no method or benchmark code, and that no method module mentions it.

`tests/test_budget_integrity.py` still passes (12 of 12). No existing file was modified.

## 9. Known limitations

1. **Frame of the truth.** The truth is verified in the canonical node order. A node-order variant re-assigns the per-neuron parameter
   draws, so the pass fractions in each exported network are statistically, not exactly, the canonical ones. The regular suite has the
   same property.
2. **Scope of `essential`.** It covers the mechanism and the named trap nodes only, up to 40 nodes. Background neurons are not screened;
   by construction they should not be essential.
3. **Thresholds.** `lo` of `distributed_drive` and `fragile_vs_robust/band` is calibrated at build time, so their `criterion.json` shows
   non-default thresholds. Every instance publishes its criterion, so this does not reveal the trap.
4. **Labels.** The default label names the trap. Use `name=` for held-out suites.
5. **Correctness is a convention in two traps.** For `fragile_vs_robust`, correct = the robust implementation, because the intact network
   relies on it. For `subset_of_draws`, correct = the union of the copies, because no copy is sufficient on most draws. Both conventions
   are stated in the truth. A harness can re-target them from `calibration_items`.
6. **Traps are single-network.** No cross-connectome variant exists yet.
