# Reviews A (causal) and G (adversarial): resolution

Reviews: `research/phase2/reviews/A_causal.md` (1 blocker, 3 major, 5 minor) and `research/phase2/reviews/G_adversarial.md`
(1 blocker, 6 major, 3 minor). Both reviews are oracle-free and were run in the clean room on the reviewers' own synthetic
instances. They reached the same blocker independently.

**The blocker.** BrainIR v1.0 chose among keep-only-sufficient sets without asking whether the intact network uses them.
- It returned latent backups, which are sufficient in isolation but kept silent in the intact network behind an inhibitory
  gate.
- It demoted neurons it had itself measured as essential.

**The major findings.**
- The group-silencing screen cleared essential inhibitors masked by what they gate.
- The inclusion probabilities were fixed evidence-class constants.
- The edge predictions were topological guesses.
- The tournament metrics scored all of these as successes.

**Who fixed what.**
- The orchestrator fixed the harness and the evaluation.
- The oracle-free composer fixed the method, as BrainIR v1.1 (commit e22db1f).
- The adversarial suite was written by a third party, the author of review G: generator, truth definition and scorer.

## Method (BrainIR v1.1)

| finding | resolution in v1.1 |
|---|---|
| A1 / G1 (blocker) | Admissibility before optimality. A candidate must validate, every member must participate in the intact network (graded rate, or measured necessity), and every neuron found essential anywhere joins every candidate. Dynamics fidelity is checked before size, and reliance at every size. Paired tests with the network's own noise band replace fixed margins. Latent backups are listed and keep at most 1 % of the probability mass. |
| A2 / G2 | The necessity screen single-silences flagged gates (a gate holding down a silent neuron that acts on the mechanism or the readout) and the most relevant candidates. The rest go through a second, interleaved partition. Isolates are admitted only by the pooled test. |
| A3 / G5 | Edge predictions are simulated (`SimQuery.remove_edges`). The confidence is the posterior, and a prediction without simulation is `None`. |
| A4 / G3 | Inclusion probabilities come from Beta posteriors over the counts, mixed over the unresolved candidates. Measured necessity is a floor and silence a ceiling. Jointly necessary groups are reported. |
| G4 | Adaptive validation, flagged "undecided" when not decisive. Sufficiency is reported both unconditionally and conditionally, plus the intact pass rate, on reserved seeds. Degenerate and distributed mechanisms are flagged, and "no_validated_mechanism" replaces a failed candidate. |
| A5–A8, G8 | Essential claims for every neuron tested, the size–error curve with members and the actual rationale, roles conditioned on interventions, final fidelity on reserved seeds, graded participation. |
| G9 | Property tests: latent backups never returned, masked gates found, distributed drive flagged, the backup-copy controller keeps its essential neurons. |
| G10 | Hashes are recorded in the method document. brainir_v1.py sha256 `94ea1f8e…`. |

## Harness and evaluation (orchestrator)

| finding | resolution |
|---|---|
| G8 | `Outcome.mean_rate_hz` / `peak_rate_hz` (graded activity in the analysis window). |
| A3 / G5 | `SimQuery.remove_edges`: an edge-removal intervention, one call per replicate, part of the cache key. |
| A9 / G6 | Participation-aware truth audit: a sufficient set whose members are near-silent in the intact network is a latent backup, not an alternative. The six held-out and final suites were re-audited (`scripts/reclassify_suite.py`); only 2 latent backups exist there, so the generator families rarely contain these structures. New metrics: `success_intact`, essential recall, missed-essential and latent-backup rates, silent core members, the intact pass fraction with the core silenced, the contested-neuron Brier score against the best set and against the non-circular "any sufficient set" target, and unambiguous essential accuracy. |
| G6 / G7 | The adversarial trap suite (`brainir.discovery.adversarial`), by a third party: latent backups, masked gates, distributed drive, function on a subset of draws, identical decoys, fragile vs robust; 21 variants over five criteria, with its own scorer. `adversarial_heldout` and `adversarial_final` (66 instances each) are built with secret seeds and have never been in the clean room. The generator's author later fixed one truth inconsistency: acceptable cores now contain every measured-essential node, which changes identical_decoy/nfc_band only. Every held-out run was re-scored under the fixed definition. |
| — | Protocol amendment §8, written before any confirmation run: `success_intact` joins decision rule (a), and the interpretation rule for v1's confidence is added (at least 90 % of high-confidence answers must be correct on `adversarial_final`). |

## Evaluation (held-out, selection role)

Held-out adversarial suite, 66 instances × 2 node orders × 3 seeds, budget 1,000, under the fixed truth definition:

| method | correct | confident-wrong | notes |
|---|---|---|---|
| greedy_plus | 0.73 | 0.22 | |
| group_probe | 0.65 | 0.26 | |
| BrainIR v1.0 | 0.41 | 0.50 | before the fixes |
| greedy_reference | 0.08 | 0.92 | |
| **BrainIR v1.1** | **0.98** | **0.02** | 338 of 396 runs confident; 97.9 % of them correct |

**v1.1 by trap** (correct / confident-wrong):
- latent_backup 1.00 / 0.00;
- masked_gate 1.00 / 0.00;
- identical_decoy 1.00 / 0.00;
- fragile_vs_robust 1.00 / 0.00;
- distributed_drive 1.00 / 0.00 (flagged as degenerate);
- subset_of_draws 0.78 / 0.19, the remaining weakness.

**Calibration** (stated P → observed membership):
- < 0.05 → 0.01;
- 0.60–0.85 → 0.67;
- ≥ 0.85 → 0.94.

**Other held-out suites (v1.1):**
- **Mechanisms**, 342 runs: structural and causal success 1.00, planted 1.00, `success_intact` 1.00, identity Jaccard 0.97 / identical 0.95, mean calls 147. Paired against greedy_reference: success +0.26, 157 fewer calls, Jaccard +0.13, robustness +0.2; the §5 rule passes on all three advantages. Against greedy_plus: identical cores +0.19, but 38 more calls.
- **Easy pairs:** 0.96 structural and intact success; identity claims 90/90 correct.
- **Hard pairs:** 0.96 structural and intact success; identity claims 18/18 correct; no false claims on null, shift or decoy pairs.
- **The only structural failures** are 6 runs on memory-switch pair networks. The fidelity rule prefers a hub pair over the planted latch; the hub pair is sufficient, but the intact network passes with it silenced. This limitation remains.

**Cost of the fixes.** v1.1 uses more calls than v1.0: 147 vs 106 on the held-out mechanisms and 187 on the adversarial suite. Wall time on the real networks is about 3×. The extra calls pay for the single-silencing evidence the reviews asked for.
