# Review G — adversarial: can BrainIR v1 be made confident and wrong?

Independent, oracle-free review. Dates 2026-09-23/24.
- **Where I worked.** I read and ran code only inside `C:\Dev\BrainIR_p2clean`. My scratch scripts and outputs are in my own
  subdirectory of the session scratchpad (`scratchpad\g\`).
- **What I did not touch.** I read no literature, benchmark answer, evaluator, oracle or real bundle.
- **Truth used.** Only the truth of instances I built myself: generator seeds 880001–881099, salt `review-g`.
- **What I wrote.** No code changed; this file is the only thing I wrote in the clean room.
- **Disclosure.** Before the coordinator's housekeeping note, I listed the scratchpad root once while creating my subdirectory. I saw
  file names only and opened none of those files.

**Code under test**

| file | sha256 (prefix) | note |
|---|---|---|
| `src/brainir/methods/brainir_v1.py` | `9ca36c4d…` | unchanged throughout the review (mtime 21:59) |
| `joint.py` | `38609d27…` | |
| `simulator.py` | `149b606b…` | |
| `tournament.py` | `58f6047d…` | |
| `suite_audit.py` | `dcb2d2bb…` | |

BRAINIR_V1_METHOD.md §7 names a different hash for the frozen v1 (finding 10).

**Files re-synced by someone else during the review.** At 22:23, about 10 minutes after I started, `guard.py` (now `65dadb9a…`),
`pair_tournament.py` and `tests/test_budget_integrity.py` were re-synced. `brainir_v1.py` was not.
- My trap runs used the new `guard.py`. Its hook and deny rules are unchanged, and v1 reads no files, so this cannot affect any result
  here.
- `pair_tournament.py` is not used by single-network runs.

**Question.** Try hard to make v1 return a *confident but wrong* mechanism. For each case, report:
- the core and its inclusion probabilities;
- the essential claims and the fidelity;
- whether the confidence was warranted.

Then quantify the calibration failures and recommend general fixes.

**Scope.** Single-network discovery. Review E already covers the cross-connectome step, so I did not re-test it.

## Summary

| severity | count | findings |
|---|---|---|
| blocker | 1 | 1 |
| major | 6 | 2–7 |
| minor | 3 | 8–10 |

**Where v1 works.** On the plain generator families (my own instances), v1:
- recovered 10 of 10 cores;
- made 24 of 24 correct single-silencing predictions;
- resisted three of my trap types: a fragile smaller implementation next to a robust one, an identical-structure decoy (for the core
  itself), and the winner-take-all context member.

**Four ways to make it confidently wrong.** The tournament's functional and causal-functional metrics count the first two as successes
in every run.

1. **Latent backup.** A sufficient set that the intact network keeps silent behind an inhibitory gate.
   - v1 returns the silent backup at P = 0.90.
   - It demotes the circuit that actually runs to P = 0.15, including neurons that its own silencing test found essential.
   - This happened in 17 of 22 runs: activity band 6/6, activity band at n = 1,500 4/4, rhythm 3/6 and 4/6.
   - greedy_plus, whose ranking v1 re-ordered, is right in 23 of 24 runs on the same instances.
2. **Masked inhibitory gate.** An inhibitory neuron whose single silencing destroys the function in 100 % of draws.
   - The group-silencing screen clears it when it is silenced together with the excitation it gates, and v1 reports P = 0.03.
   - This happened in 28 of 28 runs at n ≥ 150, across activity band, rhythm, ramp and persistence, and in 6 of 6 ramp runs at n = 60.
   - group_probe's single-neuron screen finds the gate in 12 of 12 runs.
3. **No compact mechanism** (distributed drive).
   - v1 returns an arbitrary 16–18-neuron subset of 24 interchangeable relays at P = 0.90 and gives the other relays 0.03.
   - Three of six of these cores fail on fresh draws (true sufficiency 0.20–0.40).
   - The six runs return five different cores.
4. **Function present on only a subset of parameter draws.**
   - Of two identical latches, v1 reports one at 0.97 and the other at 0.03.
   - It returns cores that fail its own fresh-seed validation (0.33) at P ≥ 0.90.

**Calibration on the contested neurons of my traps** (842 probabilities, 122 runs):
- Neurons given 0.15 are mechanism members 69 % of the time.
- Neurons given ≤ 0.05 are members 21 % of the time.
- Of 101 runs whose whole core was reported at ≥ 0.85, 42 returned the right mechanism.
- The tournament's Brier score averages over every assessed neuron. In the wrong runs it is 0.001–0.007 for the masked gates at
  n ≥ 150. For the latent backup it falls from 0.06–0.11 at n = 60 to 0.0025 at n = 1,500: the same wrong answer scores 25× better on
  a larger network. On the contested neurons of the same runs the Brier score is 0.23–0.75.

**Pre-registered edge predictions** are wrong on textbook edges of the plain families: 8 of 48. All 8 say "function preserved" at
confidence 0.6, while removing the edge breaks the function in 100 % of draws.

## What I read

**Documents**
- `CLAUDE.md` and `README.md`.
- In `research/phase2/`:
  - `COMPOSER_CONTRACT.md` and `SELECTION_PROTOCOL.md`, including the §7 amendment;
  - `BRAINIR_V1_METHOD.md`, in full;
  - `reviews/E_cross_connectome.md`, to avoid overlap.
- In `research/phase2/selection_results/`:
  - `SELECTION_RESULTS.md`, `ANTI_GAMING_candidates.md` and `CURVE_cem_search.md`;
  - the head of `REAL_TRANSFER_greedy_plus.md`;
  - the key structure of `selection_aggregates.json`.

**Code** (all read in full)
- `src/brainir/methods/brainir_v1.py`.
- `tests/test_method_brainir_v1.py`.
- `src/brainir/discovery/`: `simulator.py`, `interventions.py`, `criteria.py`, `interface.py`, `guard.py`, `tournament.py`,
  `problem.py`, `synthetic.py`, `suite_audit.py`, `run.py`, `__init__.py`.
- `src/brainir/sim/model.py`.

**Not read**
- The other method modules. I ran greedy_plus and group_probe only as black-box comparators.
- `joint.py`, `correspondence.py`, `synthetic_pairs.py`.
- The other contracts.

## How I tested

- **Instances.**
  - Each trap starts from a public generator instance (`synthetic.build_instance` with my own seeds).
  - I cut every edge of a few background neurons and wired them as trap nodes, keeping signs column-consistent.
  - The truth (which set is the mechanism) is mine. For each trap I justify it by simulation on fresh parameter draws.
  - Instances are exported with `export_instance` in two node orders (`main`, `order1`).
- **Runs.**
  - `MethodRegistry.get("brainir_v1").discover` with a budget of 1,000 calls and the default configuration.
  - Every run is inside `truth_guard` and `count_real_simulations`.
  - Seeds 0–2 (0–5 for trap 3), on both node orders.
  - 152 runs in total. In all 152, real simulations equal charged calls, and no run exceeded its budget. Calls ranged from 56 to 906
    (median 93), and there were no internal errors.
- **Scoring.** I used two scorers:
  - the tournament's own `score_structure` and `score_function` (score seeds 5000–5003);
  - my ground truth on fresh seeds 5100–5139 and 5300–5339: keep-only pass fraction of the returned core, firing rates in the intact
    network's analysis window, and single-silencing pass fractions on 40 draws.
- **Comparators.** `greedy_plus` on 8 of the trap instances and `group_probe` on 4, 6 runs each, with the same seeds and budget.
- **Ablations**, as diagnostics only (not as proposed fixes):
  - `reliance_margin = reliance_rel_margin = 0`;
  - `max_alternatives = 0`;
  - `initial_chunk_fraction = 0.05`.
- **Compute.** At most 2 local processes.

## Case results

Names in the table:
- "planted" is the mechanism the intact network runs.
- "decoy" or "backup" is the trap set.
- σ is the single-silencing pass fraction in the intact network.
- "fid" is v1's own `keep_only_pass_fraction`.
- "gt ko" is the keep-only pass fraction on 40 fresh draws.

| # | trap (criterion, n) | runs | what v1 returned | P claimed | essential claims | fid | ground truth | confidence warranted? |
|---|---|---|---|---|---|---|---|---|
| 1a | latent backup H behind a gate, planted 3-chain (band, 60) | 6 | {H} 6/6 | H 0.90; chain 0.15 | H: not essential | 1.00 (stress 1.00) | H fires 0.0006 Hz (chain 164–170 Hz); silencing the chain passes 1.00 because H takes over | **no** |
| 1a | same (band, 1,500) | 4 | {H} 4/4 | same | same | 1.00 | same | **no** |
| 1b | E–I decoy behind a latched gate, planted 5-neuron delayed oscillator (rhythm, 60) | 6 | decoy 3/6, planted 3/6 | decoy 0.90 and planted 0.15, or the reverse | decoy: none essential; v1's own test found planted m1–m4 essential (σ = 0.00) | 1.00; core 9.9–11.9 Hz vs intact 5.6–5.7 Hz | decoy fires 0.00006 Hz; m1–m4 σ = 0.00 | **no** in 3/6 |
| 1c | same with a planted 4-neuron ring (rhythm, 60) | 6 | decoy 4/6 | same pattern | v1's own test: m0, m1, m2 essential | 1.00; core 11.5–12.3 Hz vs intact 13.3–14.7 Hz | decoy fires 0.0002 Hz; m0, m1 σ = 0.00 | **no** in 4/6 |
| 2 | gated disruptor: gate S masked by drivers D1↔D2 (band, rhythm, ramp, persistence; 150) | 24 | motif without S, 24/24 | S 0.03; motif 0.97 | motif essential; no claim for S | 1.00 | S: σ = 0.00 in 40/40 draws | **no** |
| 2 | same (rhythm, 1,500) and (ramp, 60) | 10 | motif without S, 10/10 | same | same | 1.00 | same | **no** |
| 2 | same (band and rhythm at 60; selectivity at 60 and 150) | 24 | motif + S, 24/24 | S 0.97 | correct | 1.00 | — | yes |
| 3 | fragile E–I pair (keep-only 0.65) + robust ring (rhythm, 60) | 12 | ring 12/12 | ring 0.90–0.97; pair 0.15 or 0.03 | ring members' flags vary between runs | 1.00 | ring σ 0.45–0.78 | yes (the flags are noisy) |
| 4 | two identical marginal latches (persistence, 60) | 6 | one latch (L2 in 4 runs, L1 in 2) | chosen latch 0.90–0.97, other 0.03 | chosen latch essential in 4/6 | 0.33–1.00; `None` once | each latch σ 0.28; returned core 0.30–0.48; intact 0.45–0.55 | **no** |
| 5 | 24 identical weak relays, about 17 needed (band, 80) | 6 | 16–18 relays; 5 distinct cores | 14–17 relays at 0.90; 4–8 identical relays at 0.03 | none essential | 0.33–0.67 | returned core 0.20–0.90 (3/6 below 0.5) | **no** |
| 7 | identical-structure silent decoy (rhythm, 60; decoy drive +1, +10, +25 synapses) | 18 | planted 18/18 | tie 0.45 / 0.485 in 11/18; 0.90–0.97 otherwise | planted I essential | 1.00 | decoy fires 0.00008 Hz; I σ = 0.00 | core yes; probabilities no |

**Scale.** Traps 1 and 2 behave the same at n = 1,500.

**Comparators on the same instances**
- Trap 1 (1a at 60 and 1,500, 1b, 1c):
  - greedy_plus is right in 23 of 24 runs;
  - v1 in 5 of 22;
  - group_probe falls for 1a (5 of 6) but not for 1b (6 of 6).
- Trap 2 (the four n = 150 instances):
  - greedy_plus is right in 19 of 24;
  - v1 in 0 of 24;
  - group_probe in 12 of 12 (band and ramp).

**Ablations**
- With a reliance margin of 0, v1 returns the planted set in 12 of 12 runs (1a, 1b).
- With `max_alternatives = 0`, it does so in 6 of 6 (1b).
- With `initial_chunk_fraction = 0.05`, it finds S in 6 of 6 (band, n = 150), at a cost of 22 extra calls.

## Calibration (pooled over 20 valid trap instances, 122 runs)

**Contested neurons** are the named trap nodes: the planted members, the decoys, the gates and drivers, the latches and the relays.

**How membership was defined**
- Trap 1: planted set = member; backup, gate and latch = non-member.
- Trap 2: motif + S = member.
- Trap 3: ring = member.
- Trap 4: both latches = member.
- Trap 5: every relay = member.
- Trap 7: planted pair = member.
- Excluded: the invalid persistence variant of trap 2, in which S is not essential. The early trap-2 winner-take-all run was rescored
  against the generator's {A, IA} + S.

| P given by v1 | n | mean P | observed member frequency |
|---|---|---|---|
| ≥ 0.85 | 324 | 0.935 | 0.926 |
| 0.30–0.60 (tie shares) | 64 | 0.449 | 0.656 |
| 0.10–0.30 (the loser weight 0.15) | 90 | 0.150 | **0.689** |
| ≤ 0.05 | 364 | 0.025 | **0.209** |

**Scores**
- Brier score on the contested neurons: 0.185. A constant predictor at the base rate scores 0.245.
- Tournament Brier score (all assessed neurons), median per run: 0.0072. The contested-neuron Brier, median per run: 0.314.

**Run level.** In 101 runs every core member was reported at ≥ 0.85. The core was the right mechanism in 42 of them (0.42):

| trap | confident runs | right | wrong |
|---|---|---|---|
| 1 | 22 | 5 | 17 |
| 2 | 52 | 18 | 34 |
| 3 | 12 | 12 | 0 |
| 4 | 6 | 0 | 6 |
| 5 | 2 | 0 | 2 |
| 7 | 7 | 7 | 0 |

A confident wrong run carries the same probabilities as a confident right one.

## Findings

### 1. [blocker] A latent backup that the intact network keeps silent is returned as the mechanism at P = 0.90; the circuit that runs is demoted to 0.15, essential members included

**Evidence**

- **Trap 1a (activity band)**
  - Design:
    - planted chain T1→T2→T3→readout;
    - backup H, wired stimulus → H → readout;
    - an inhibitory gate G, driven by T3, silences H.
  - Ground truth on fresh draws:
    - H fires 0.0006 Hz (mean in the analysis window), against 164–170 Hz for the chain members;
    - keep-only {H} passes 1.00;
    - silencing the whole chain passes 1.00, because G stops and H takes over at almost the same readout rate (118 → 122 Hz).
  - v1's output:
    - core {H} in 6 of 6 runs at n = 60 and 4 of 4 at n = 1,500;
    - P(H) = 0.90; the chain gets 0.15 ("decisively worse", trace key `size`);
    - roles are inverted: H is labelled `output_driver` and T1–T3 `redundant_backup`;
    - fidelity 1.0; H's `silence_alone` prediction is "preserved" (pass 1.0).
  - v1's own per-member reliance: chain 0.0046–0.0144, H exactly 0.
    - The intact network relied more on the chain on every paired replicate, but by less than the fixed 0.05 margin.
- **Traps 1b and 1c (rhythm)**
  - Design:
    - planted mechanism: a 5-neuron delayed inhibitory oscillator (1b) or a 4-neuron ring (1c);
    - decoy: an E–I pair E′, I′;
    - gate: G is driven by a latch L that a planted member switches on, and G keeps the decoy silent.
  - Ground truth:
    - the decoy fires 0.00006–0.0002 Hz;
    - keep-only of the decoy passes 0.975, at 11.8 Hz against the intact network's 5.8 Hz (1b), and at 11.9 against 13.9 Hz (1c);
    - silencing planted m1–m4 (1b) or m0, m1 (1c) passes 0.00.
  - v1's output: the decoy in 3 of 6 runs (1b) and 4 of 6 (1c), at P = 0.90 per member, with the planted members at 0.15.
  - **v1 contradicts its own evidence.** I wrapped `_Run.necessity` in my own script (no file changed) and logged every verdict:
    - 1b `main` seed 0: v1's pooled test found m1–m4 essential (pass 0.00 on 6 replicates each) and E′, I′ irrelevant (pass 1.00).
      It still reported {E′, I′} at 0.90 and m1–m4 at 0.15.
    - 1c: m0, m1, m2 essential (pass 0.00, 0.00, 0.29), reported at 0.15.
  - The mismatch is visible in v1's own output:
    - `fidelity.core_frequency_hz` is 9.9–11.9 Hz, against `predicted_frequency_hz` of 5.6–5.7 Hz (1b);
    - every `silence_alone` prediction for the decoy says "preserved" (pass 1.0), so v1 reports a mechanism none of whose members
      matters in the intact network;
    - in 5 of the 7 decoy runs, v1 chose a decoy with stress pass 0.5–0.75 over a planted set with 1.0, because robustness is
      consulted only between sets of equal size (brainir_v1.py:1207–1209).
- **Official scoring hides it.**
  - `functional_success` and `functional_success_causal` are True in all 17 decoy runs.
  - `suite_audit.find_unplanted_alternatives` records {H} as an unplanted sufficient set in trap 1a. The audited tournament would
    therefore score v1's wrong answer as structural success (finding 6).
- **Where the error enters.**
  - The canonical elimination found the planted set in 1b and 1c (`elimination.final`).
  - The enumeration and the selection turned it into the decoy.
  - The decoy comes back through the silent-filler path: its kind is `replacement_for_<planted member>`.

**Code**
- `alternatives()` admits fillers from the whole network, silent neurons included: brainir_v1.py:1103–1106, "a filler may be silent
  in the intact network".
- `compare()` treats any difference in size as decisive (1202–1206) unless `relied_more` holds:
  - every replicate must agree, and the mean per-member difference must be at least max(0.05, 0.25 × the larger) (1184–1192).
- Reliance silences the candidate in the intact network (1154–1165). Compensation by the backup hides it.
- `probabilities()` gives every member of a losing set the loser weight 0.15, whatever its essentiality (1326–1343).
- v1 behaves as its docstring objective (iii) specifies: "relied on decisively more, else the simplest". It is the objective that fails
  on latent backups.
- COMPOSER_CONTRACT §2 requires that "Compactness must never remove a member whose removal breaks the function". Here compactness
  replaced four essential members by two silent ones.
- BRAINIR_V1_METHOD.md §9.3 mentions that a sufficient hub can be reported with the planted set at 0.15. The cases here are worse: the
  reported set never fires, and the demoted set contains neurons v1 itself found essential.

**Fix** (general)
1. **Participation.**
   - The simulator should return graded activity (finding 8).
   - A candidate whose members are near-silent in the intact network, or whose joint silencing leaves the intact readout unchanged
     (reliance ≈ 0 while another candidate's reliance is consistently > 0), may not be preferred to a candidate the network uses.
   - Report such a candidate as a latent backup.
2. **Essential consistency.** A candidate that lacks a neuron with a failing single-silencing verdict is inadmissible as the mechanism
   of the intact network. It can neither win nor tie.
3. **Dynamics fidelity before Occam.** Prefer the candidate whose keep-only readout statistics (frequency, rate, score) match the
   intact network's. v1 already computes both.
4. **Paired test.** Replace the fixed per-member margin with a paired test over replicates.
   - Apply Occam, and robustness, only among candidates whose participation, reliance and fidelity cannot be told apart.
   - Weigh robustness against size.
5. **Fillers.** Draw replacement fillers from neurons active in the intact network, or label silent-filler sets as latent backups.

### 2. [major] The group-silencing screen misses an essential inhibitory gate when it is silenced with the excitation it gates (P = 0.03): systematically, and more often at scale

**Evidence**

- **Trap 2 ("gated disruptor")**
  - Design:
    - D1↔D2 are strongly recurrent, stimulus-driven excitatory neurons;
    - they drive a relay X that would break the criterion: X targets the readout (band, ramp), the motif's inhibitor (rhythm), or the
      latch, with X inhibitory (persistence);
    - an inhibitory gate S, stimulus-driven (and also driven by the latch for persistence), holds X silent.
  - Ground truth in every instance:
    - S fires at about 180 Hz and X at 0 Hz;
    - silencing S alone passes 0.00 (40 of 40 draws fail);
    - silencing {S, D1, D2} passes 1.00.
- **v1 at n = 150.**
  - S was cleared in 6 of 6 runs each for band, rhythm, ramp and persistence (24 of 24).
  - It was also cleared in 4 of 4 runs at n = 1,500 (rhythm) and 6 of 6 at n = 60 (ramp).
  - P(S) = 0.03. The core is the motif without S, at 0.97. Fidelity 1.0.
  - v1 spent 56–75 of its 1,000 calls.
- **Where v1 found S.**
  - At n = 60 for band and rhythm (6 of 6 each). There the first chunk, round(0.25 × 9) = 2, cannot hold S and both drivers.
  - For selectivity (12 of 12).
- **What the screen did** (ramp, n = 60):
  - the pool held 11 neurons and the screen ran 3 tests;
  - the relevance order starts [S, D2, D1, …], so the first chunk {S, D2, D1} passes and is cleared as a whole.
- **Official scoring hides it.**
  - Functional and causal-functional success are True in every missed run.
  - The all-neuron Brier score is 0.0072 at n = 150 and 0.0011 at n = 1,500.
- **Comparators.**
  - greedy_plus, with its random chunk order, finds S in 19 of 24 runs on the n = 150 instances.
  - group_probe, with its single-neuron screen, finds it in 12 of 12.
  - v1's deterministic canonical order turns a chance miss into a systematic one.
- **Ablation.** `initial_chunk_fraction = 0.05` finds S in 6 of 6 runs.

**Code**
- `necessity_screen` clears a passing group as a whole (brainir_v1.py:509–512) and bisects only failing groups.
- The pool is sorted most relevant first (986), so a gate and the drivers it opposes, which sit next to each other structurally, share
  the first chunk.
- The chunk is 25 % of the pool. On the real bundle (87–121 candidates, BRAINIR_V1_METHOD.md §12.5) that is about 20–30 neurons.
- By v1's own definition, context members E = {x ∉ M : σ({x}) < 1/2} (BRAINIR_V1_METHOD.md §2), S belongs to the mechanism. The
  generator's winner-take-all truth includes its context member for the same reason.

**Fix**
- Do not read a passing group as proof that none of its members is individually necessary. Either:
  - re-test the members of every passing group in a second, independent partition, for example interleaved by relevance rank, or
    stratified so that inhibitory neurons and the excitatory neurons converging on the same targets fall into different groups; or
  - single-silence every active inhibitory candidate that projects onto an intact-silent excitatory neuron with a path to the readout
    (a structural signature of disinhibition).
- Use the unspent budget. A single-neuron necessity pass over the restricted pool costs about 2–3 calls per candidate.

### 3. [major] The inclusion probabilities contradict v1's own causal evidence and are badly calibrated below 0.9

**Evidence**

- **Loser weight.** Every member of a decisively worse candidate gets 0.15 (brainir_v1.py:1341–1342). That includes neurons whose
  single silencing v1 itself measured to fail on every replicate (finding 1: m1–m4 at 0.15).
- **Ties halve essential members.**
  - Trap 7: the essential inhibitor I (v1's own test: pass 0.00) is reported at 0.485, and the silent decoy's members at 0.45, in 11
    of 18 runs.
  - Trap 2's winner-take-all instance at n = 60: the essential winner A is reported at 0.485, tied with a set in which a weakly
    connected background neuron (0.45) replaces A.
- **Interchangeable neurons get extreme and unequal values.**
  - Trap 4: two latches with identical wiring get 0.97 and 0.03.
  - Trap 5: 24 identical relays get 0.90 or 0.03, depending on an arbitrary elimination order.
- **Pooled calibration** (table above):
  - neurons given 0.15 are members 69 % of the time;
  - neurons given ≤ 0.05 are members 21 % of the time;
  - tie shares of 0.45–0.485 correspond to 66 %;
  - the contested-neuron Brier score (0.185) barely beats a constant (0.245).
- **The documented calibration** (Brier 0.0009–0.004) is computed over all assessed neurons (tournament.py:57–60). Thousands of
  trivially excluded neurons at P = 0.002 or 0.01 dominate it.

**Fix**
- Make causal evidence a floor and a ceiling:
  - a neuron with a failing single-silencing verdict keeps at least P_ESSENTIAL, whatever the selection;
  - a neuron that is silent and whose silencing passes cannot exceed the cleared value.
- Weight the candidate mechanisms by their evidence (paired reliance, participation, fidelity) instead of an ordinal rule with a fixed
  0.15 floor.
- Compute membership as an average over the enumerated equivalent sets, so that interchangeable neurons get equal probability.
- Recalibrate on an adversarial suite (finding 6). Report the contested-neuron Brier score and a reliability diagram.

### 4. [major] Marginal and degenerate evidence is reported as certainty

**Evidence**

- **Distributed drive** (trap 5: 24 identical weak relays; 16–18 are needed at lo = 35 Hz).
  - v1 returns 16–18 relays: 14–17 of them at 0.90, and 4–8 identical relays at 0.03.
  - True keep-only sufficiency of the returned cores: 0.575, 0.575, 0.40, 0.90, 0.20 and 0.225, so 3 of 6 are below 0.5.
  - v1's own fidelity: 0.33–0.67, from 3 seeds.
  - The six runs return five different cores (mean Jaccard 0.71). Two of the cores contain a background neuron.
  - Cost: 550–906 calls.
  - Every member is non-essential and replaceable, yet each gets 0.90. v1 has no notion that no compact mechanism exists.
- **Subset of parameter draws** (trap 4: two latches, each persisting on about 40 % of draws; the intact network passes 0.45–0.55).
  - v1 returns one latch, at 0.97 (claimed essential in 4 runs) or 0.90, and gives the other latch 0.03.
  - True keep-only sufficiency of the returned latch: 0.30–0.475.
  - In 2 of 6 runs the core *failed v1's own* fresh validation (0.33).
  - In 1 of 6 runs no validation replicate was usable (`keep_only_pass_fraction = None`).
  - P was ≥ 0.90 in every run.
- **Why this happens.**
  - `validate` counts a passing replicate even when the intact network fails on it, and discards replicates where both fail
    (brainir_v1.py:841–864). The fraction is therefore conditional and biased upward.
  - Three fresh replicates cannot tell 0.33 from 0.67.
  - When no candidate validates, the canonical one is returned (1166) with unchanged probabilities.
- **Decision cliffs.** Four fixed thresholds decide the outcome: the reliance margin of 0.05, the majority of 3–5, the validation
  margin of 0.5 on 3 replicates, and stress 4/4 against 0/4. As a result:
  - answers flip between seeds and node orders: trap 1b in 3 of 6 runs, trap 1c in 4 of 6, trap 4 between two answers, trap 5 among
    five;
  - each of those answers is reported at 0.90–0.97;
  - in trap 3, ring members with σ ≈ 0.45–0.48 are called essential in some runs and not in others.
- **The promise is not kept visibly.** BRAINIR_V1_METHOD.md §1 promises the same mechanism "from any node order and any seed unless the
  evidence itself is marginal". The output never says when the evidence is marginal.

**Fix**
- Report every decisive key with its margin and its uncertainty: the reliance difference with a CI, the validation count k/n with a CI,
  and the stress counts. A key within its noise band is a tie (shared mass), not a decision.
- Validate adaptively until the CI of the pass fraction excludes 0.5.
- Report unconditional and conditional (intact-passing) sufficiency separately, together with the intact pass rate.
- Detect degeneracy: when every member is non-essential and each has fillers, report the mechanism as distributed.
  - Set membership to the frequency over the enumerated minimal sets.
  - Give the core a low confidence and flag it.
- Never report a candidate that failed validation at P ≥ P_NECESSARY. Return an explicit "no validated mechanism" instead.

### 5. [major] Pre-registered edge-removal predictions are wrong on textbook edges

**Evidence**

- **Setup.**
  - v1 ran on the 10 plain generator families (n = 50, my seeds, `main`, seed 0).
  - It recovered all 10 cores, and its 24 single-silencing predictions were all correct.
  - For each predicted "strongest in-core edge", I zeroed that one entry of W myself and simulated 20 fresh draws. I did this in the
    intact network and in keep-only of the core.
- **Intact network: 20 of 24 correct.** Four were wrong:
  - the E–I self-excitation (E→E);
  - the negative-feedback controller's E→I drive of its gain-control inhibitor;
  - the winner-take-all A→IA drive, twice.

  All four were predicted "preserved" at confidence 0.6. All four break the function in 20 of 20 draws, and all four are listed as
  critical edges in the generator truth.
- **Keep-only core: 20 of 24 correct.** Four were wrong: the E–I self-loop, the redundant oscillator's self-loop, the
  two-implementations I→E, and the negative-feedback controller's E→I. All were predicted preserved; all broke in 20 of 20 draws.
- **Calibration.** In the intact network, "preserved" claims were right in 4 of 8 cases (claimed confidence 0.6). "Breaks" claims were
  right in 16 of 16 (claimed 0.75).

**Code**
- The rule asks only whether the *presynaptic* member loses its in-core route to the readout, or its loop (brainir_v1.py:700–706).
- It ignores two cases:
  - the edge may be the only drive of a necessary postsynaptic member (E→I, A→IA);
  - self-excitation may be needed for the oscillation even though another loop remains.
- Between edges of equal weight, the first one in core position order wins (687). Which edge gets predicted therefore depends on the
  node order.

**Fix**
- Add an edge-removal intervention to the library: zero one entry of W, charged as one call per replicate.
- Back each edge prediction with simulations, about 3–6 calls per member.
- Otherwise:
  - predict "breaks" when the edge is the only in-core input of a necessary or essential member;
  - abstain (`None`) where the rule has no information;
  - calibrate the confidences on the synthetic suites.

### 6. [major] The evaluation would count these failures as successes

**Evidence**

- **The audit accepts silent sets.** `suite_audit.find_unplanted_alternatives` (suite_audit.py:47–104) adds to the truth any
  keep-only-sufficient set found among readout-projecting single neurons and the complication nodes. It does not check that the set
  participates in the intact network.
  - On trap 1a it records {H} as an unplanted alternative, although H fires at 0.0006 Hz.
  - After the audit, `score_structure` scores v1's wrong answer as structural success.
- **Functional success is blind to both failures.**
  - `functional_success` (keep-only sufficient and 1-minimal, tournament.py:121) is True for all 17 latent-backup cores and all 34
    cores missing an essential gate.
  - So is `functional_success_causal`, which checks only removable members (86–97).
  - Neither metric looks at participation in the intact network or at essential neurons outside the core.
- **The Brier score is dominated by easy negatives.** It averages over every assessed neuron (tournament.py:57–60):
  - 0.0011–0.0074 in the masked-gate runs at n ≥ 150, where the only contested truth member sits at 0.03;
  - 0.06–0.11 for the latent backup at n = 60, but 0.0025 at n = 1,500: the same wrong answer looks 25× better on a larger network;
  - against a contested-neuron Brier of 0.23–0.75 in the same wrong runs.
- **Two definitions of "essential".** The truth uses f_sil < 0.2 (synthetic.py:423); v1 claims essential when σ < 0.5, i.e. when more
  than half of the pooled replicates fail. "Essential accuracy" mixes the two, and in trap 3 ring members with σ ≈ 0.45 that v1 called
  essential were scored as wrong.
- **The confirmation cannot see these failures.** The confirmation rule (SELECTION_PROTOCOL §5) uses success, reliability, efficiency
  and robustness on a suite built by the same generator and audited the same way. Findings 1–4 would not appear there.

**Fix**
- Add a participation check to the audit. A sufficient set whose members are silent in the intact network is recorded as a latent
  backup, not as a valid answer.
- Add a causal-completeness metric: the fraction of intact-essential neurons, among the structurally possible active candidates, that
  the core contains. The generator can compute it once per instance.
- Report the contested-neuron Brier score and reliability diagrams.
- Use one definition of "essential".
- Add an adversarial component to the evidence recorded at the lock: latent backups, masked gates, distributed drive and
  subset-of-draws regimes. Someone other than the composer should build it.

### 7. [major] The selection evidence cannot justify dropping the components that prevent findings 1 and 2

**Evidence**

- **Two components were dropped.** v1 made two composition choices (BRAINIR_V1_METHOD.md §2 and the §5 table):
  - it re-ordered greedy_plus's ranking into "Occam unless decisively more relied on";
  - it dropped group_probe's single-neuron necessity screen for cost (§5, "Dropped").
- **Those two components are what protects against findings 1 and 2.** On my trap instances:
  - greedy_plus is right on trap 1 in 23 of 24 runs, where v1 is right in 5 of 22;
  - greedy_plus is right on trap 2 in 19 of 24 runs, where v1 is right in 0 of 24;
  - group_probe is right on trap 2 in 12 of 12 runs.
- **The evidence behind the choices cannot see these cases.** It comes from three sources:
  - the held-out selection suite;
  - the anti-gaming checks in `ANTI_GAMING_candidates.md` (edge reordering, token re-salting, stripped annotations, sink distractors,
    widened parameters), all of which preserve meaning;
  - v1's own development suite.

  All three are generated from the same families. None contains a latent backup, a masked gate or a distributed drive, so none can
  measure what the two dropped components buy.

**Fix**
- Before the freeze, re-run the component choices on an adversarial suite.
- Keep a reliance-first or participation-first rule, and a single-neuron necessity pass, unless that evidence shows they are not
  needed.
- Report v1 against greedy_plus and group_probe on that suite.

### 8. [minor] Activity is binary at 0.01 Hz, so "silent" cannot be told from "participating"

**Evidence**
- `criteria._common` (criteria.py:63) marks a neuron active if its peak rate in the analysis window exceeds `active_rate_hz` = 0.01 Hz.
- Trap 1a's gated backup H has a mean rate of 0.0006 Hz and a median peak of 0.016 Hz, a decaying onset transient. That makes it
  "active" in 70 % of draws, so v1 keeps it as a candidate.
- Trap 1b and 1c's decoys are "silent" in 55–90 % of draws. They come back anyway through the silent-filler path (finding 1).
- `Outcome` exposes only `active_positions` (simulator.py:83–94), so no method can measure participation.

**Fix**
- Add graded per-neuron activity to `Outcome`: the mean and peak rate in the analysis window, optionally sparse.
- Use a participation threshold relative to the network's own activity distribution.

### 9. [minor] The tests contain no adversarial property

**Evidence.** `tests/test_method_brainir_v1.py` covers the generator families, budgets, switches, determinism, meaning-preserving
perturbations and the cross-connectome rules. It does not check that:
- the core's members participate in the intact network;
- every neuron v1 finds essential keeps P ≥ P_ESSENTIAL;
- a gate masked by its drivers is found;
- a distributed drive is flagged.

**Fix.** Add these general properties as tests on small hand-built instances like the traps here. They run in seconds.

### 10. [minor] The documented frozen hash does not match the code

**Evidence**
- BRAINIR_V1_METHOD.md §7 (line 232) and §12.3 (line 420) give `brainir_v1.py` sha256 `3a07cf80…`.
- The file in the clean room hashes to `9ca36c4d…`, with or without CR stripping. It did not change during my review.
- `joint.py` (`38609d27…`) and `correspondence.py` (`11acef92…`) do match the document.

**Fix.** Re-hash at the freeze, record the hash in METHOD_LOCK.json, and state for every table which hash produced it.

## What held

- **Plain families.** 10 of 10 cores and 24 of 24 single-silencing predictions correct.
- **Fragile smaller implementation next to a robust larger one** (two implementations, with the E–I pair tuned to keep-only pass 0.65):
  - the ring was returned in 12 of 12 runs, at 0.90–0.97, with the pair at 0.15 or 0.03;
  - reliance was decisive in 9 of 12 runs; in the other 3 the pair was never enumerated.
  - It held because silencing the ring fails on some draws. Robustness itself played no part (finding 1).
- **Identical-structure decoys.** The planted pair was the core in 18 of 18 runs. Only the probabilities were diluted (finding 3).
- **Winner-take-all context member.** Found in every run: my trap-2 instances at n = 60 and 150, and an unmodified generator instance at
  n = 500 (4 of 4).
- **Transient trigger for persistence.** I did not attempt it after a calculation showed it cannot be built. A neuron driven to 100–170
  Hz needs τ·ln(r / 0.01) ≈ 0.18–0.19 s to fall below 0.01 Hz. Any trigger active near the 0.15 s window start therefore still counts
  as active, and v1's verified activity filter keeps it.
- **Integrity.** Budget integrity held in 152 of 152 runs. Re-running the same seed reproduced the output. There were no internal
  errors.

## Recommendations (general; no instance-specific patches)

1. **Admissibility before optimality** (findings 1, 3, 8).
   - A candidate mechanism must participate in the intact network (graded activity).
   - It must contain every neuron with a failing single-silencing verdict.
   - Its keep-only dynamics must match the intact network's.
   - Only admissible, statistically indistinguishable candidates are compared by size, robustness and canonical order.
2. **Uncertainty-aware keys** (findings 1, 4). Use paired tests with confidence intervals, and treat a key inside its noise band as a
   tie. Validate adaptively. Report unconditional sufficiency.
3. **A necessity screen that survives non-monotone effects** (finding 2). Use a second, independent partition for passing groups, a
   single-silencing pass over structurally flagged gates, and part of the budget v1 leaves unused: over 90 % in these runs, and 63–75 %
   of the pooled budget on the real bundle (BRAINIR_V1_METHOD.md §12.5).
4. **Degeneracy-aware probabilities** (findings 3, 4). Base membership on the enumerated sufficient sets, give interchangeable neurons
   equal probability, flag distributed mechanisms, and treat essential evidence as a floor.
5. **Simulated edge predictions** (finding 5), through a library edge-removal intervention; abstain where there is no evidence.
6. **An evaluation that can fail these cases** (findings 6, 7): a participation-aware audit, causal completeness, the contested-neuron
   Brier score, one "essential" definition, and an adversarial suite built by a third party in the lock evidence. Include greedy_plus
   and group_probe as comparators there.
7. **Property tests** for the above (finding 9).

## Verdict

**Not ready to lock as a method whose confidence can be taken at face value.**

- **The search.** v1's search is sound on the generator families.
- **The selection rule and the probability model.** Small, biologically ordinary motifs drive them into confident errors:
  - a latent backup behind an inhibitory gate makes v1 report, at P = 0.90, a mechanism the intact network never fires;
  - a disinhibitory gate makes v1 exclude an essential neuron at P = 0.03.
- **The evaluation** would score these outputs as successes.

**What must happen before the lock**
- Finding 1 must be fixed.
- Findings 2, 3, 6 and 7 should be fixed, or at least measured on an adversarial suite, before the confirmation run.

Until then, two things should not be read as evidence: v1's choice among sufficient sets, and its inclusion probabilities below 0.9.

Its essential verdicts, where it made them, were right whenever a neuron's silencing clearly failed or clearly passed (σ = 0 or 1).
They flip near σ ≈ 0.5 (finding 4), and a masked gate never receives one (finding 2).

## Appendix: scripts and commands

All in my scratch subdirectory `<scratchpad>\g\`. Every command runs from `C:\Dev\BrainIR_p2clean` as `uv run --no-sync python`, with
`G` = that directory.

**Scripts**

| script | role |
|---|---|
| `glib.py` | builders (`repurpose`, `finalize`, `export`), direct dynamics checks, and `run_v1`, which runs discover under the guards and applies the official scorer and the ground truth |
| `traps.py` | trap builders: `t1_band`, `t1_rhythm`, `t2_disruptor`, `t2_persist`, `t3_fragile`, `t4_subset`, `t5_distributed`, `t7_identical`, `plain` |
| `run_traps.py` | networks × seeds for one trap; writes the records and prints a summary |
| `summ.py`, `calib.py`, `gt.py` | summaries, the pooled calibration, and the ground-truth tables |
| `edge_check.py` | finding 5 |
| `other_method.py` | greedy_plus and group_probe comparisons |
| `instr.py` | logs v1's necessity verdicts by wrapping `_Run.necessity` |
| `t1_design.py`, `t2_design.py`, `t2p_design.py`, `t3_design.py`, `t3_scan2.py`, `t4_scan.py`, `t5_design.py` | design checks and parameter scans |

**Results**
- `res/*.records.json`, with `res/instances/` and `res/truth/`;
- `res/gt_tables.json`;
- `res_abl/`;
- `edges/edge_rows.json`.

**Commands**

```
run_traps.py $G/res t1_band --seeds 0,1,2 --workers 2
run_traps.py $G/res t1_band --seeds 0,1 --kw '{"n": 1500, "n_readout": 20}' --label t1_band1500
run_traps.py $G/res t1_rhythm --kw '{"family": "delayed_inhibitory_oscillator"}' --label t1_rhythm_dio
run_traps.py $G/res t1_rhythm --kw '{"family": "ring_oscillator"}' --label t1_rhythm_ring
run_traps.py $G/res t2_disruptor --kw '{"family": "negative_feedback_controller", "target": "readout", "n": 150}' --label t2_nfc150
run_traps.py $G/res t2_disruptor --kw '{"family": "ei_pair_oscillator", "target": 1, "wX": 60.0, "n": 150}' --label t2_ei150
run_traps.py $G/res t2_disruptor --kw '{"family": "integrator", "target": "readout", "n": 150}' --label t2_integ150
run_traps.py $G/res t2_persist --label t2_persist150
run_traps.py $G/res t2_disruptor --seeds 0,1 --kw '{"family": "ei_pair_oscillator", "target": 1, "wX": 60.0, "n": 1500, "n_readout": 20}' --label t2_ei1500
run_traps.py $G/res t3_fragile --seeds 0,1,2,3,4,5 --label t3_fragile
run_traps.py $G/res t4_subset --label t4_subset
run_traps.py $G/res t5_distributed --label t5_dist
run_traps.py $G/res t7_identical --kw '{"extra": 10.0}' --label t7_ident_x10      (also extra 1 and 25)
run_traps.py $G/res_abl t1_band --config '{"reliance_margin": 0.0, "reliance_rel_margin": 0.0}' --label abl_t1_band_m0
edge_check.py $G/edges
gt.py $G t1_band t1_rhythm_dio t1_rhythm_ring t2_nfc150 t2_ei150 t2_integ150 t2_persist150 t2_integ t3_fragile t4_subset t7_ident
calib.py $G
other_method.py $G greedy_plus t1_band t1_rhythm_dio t1_rhythm_ring t2_nfc150
instr.py $G t1_rhythm_dio main 0
```
