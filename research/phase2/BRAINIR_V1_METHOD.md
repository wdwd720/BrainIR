# BrainIR v1.2 — order-invariant canonical group elimination, enumerated alternatives and an admissibility-first causal selection

Method file `src/brainir/methods/brainir_v1.py` (registered as `brainir_v1`, version 1.2.0; the registry imports it), with its
sha256 in `src/brainir/methods/_brainir_v1_sha256.py`. Tests: `tests/test_method_brainir_v1.py`. Composed by an oracle-free developer from the five Phase 2 candidates (`greedy_plus`,
`cem_search`, `group_probe`, `surrogate_search`, `evo_pareto`) and the cross-connectome component (`brainir.discovery.joint`).
Version 1.0 was built on the evidence of the held-out selection suite (`research/phase2/selection_results/`, aggregates only) and my
own plain synthetic experiments. Version 1.1 answers reviews A (`research/phase2/reviews/A_causal.md`, causal identification) and G
(`research/phase2/reviews/G_adversarial.md`, adversarial traps), and the coordinator's held-out adversarial aggregates (66 instances,
aggregates only). It was developed on adversarial instances I built myself with the third-party generator
(`brainir.discovery.adversarial`, my own seeds) and on my plain suites (section 12). Version 1.2 answers review B
(`research/phase2/reviews/B_optimisation.md`, search, objective and budget). Nothing in the method refers to a dataset, a cell type, a
neuron id, a mechanism size, a trap or a threshold tuned to an instance. The frozen file hashes are in section 7.

## 0. What versions 1.1 and 1.2 changed

### 0.1 Version 1.2 (review B)

Review B (`research/phase2/reviews/B_optimisation.md`, on v1.1 `94ea1f8e`) found 0 blockers, 1 major and 8 minor findings and accepted
v1.1 for the lock once B2 is fixed. Version 1.2.0 changes the selection's statistics and bookkeeping only; the search, the screen, the
enumeration and the probability model are those of v1.1. On my adversarial suites v1.2 returns v1.1's core in 175 of 176 runs (the other is a distributed drive flagged
as such by both) and on the plain small suite in 276 of 282 runs; on the real bundle it returns v1.1's cores at the default, and the
one core that changes with `decisive` (MANC at 0.975) comes out as a tie (section 12.10).

| finding (severity) | what v1.1 did | what v1.2 does (section) | evidence (section 12.10) |
|---|---|---|---|
| B2 (major): on the real MANC network the returned mechanism was decided at the threshold (posterior 0.954 against 0.95) by a t test on a bimodal statistic, and `decisive` = 0.975 flipped it | reliance = (failure indicator + readout change) per member, one paired t test, decisive at 0.95 | reliance tested in two parts: function failures as paired discordant counts (the rule of the sufficiency comparison), the readout change per member against the noise band on replicates where neither silencing fails; every paired comparison (fidelity, reliance, union, stress) decides only beyond a tie band — tail mass below half of 1 − `decisive` (P > 0.975); a posterior whose tail mass lies within a factor of two of 1 − `decisive` (0.90–0.975) is extended to the cap and is then a tie that shares the mass, and a later key (Occam, stress) may not overrule a reliance posterior in the band that leans the other way (§2) | real bundle at `decisive` 0.90 / 0.95 / 0.975: the default cores are v1.1's on both networks; MaleCNS returns the same core (and the same tie) at all three settings; the MANC replacement now rests on 5 against 0 failures (P = 0.984) and holds at 0.90 and 0.95; at 0.975 that posterior lies inside the setting's band and the canonical set is returned tied with the replacement (weights 0.5 / 0.5) — the only core that changes, and it comes out as a tie |
| B9: an incumbent tournament with a non-transitive comparator; a candidate that beat the winner could be filed as tied; reliance depended on the whole candidate set | sequential challenger–incumbent comparisons; distinctive members = outside the intersection of all candidates | round robin over every pair; the winner is undefeated (the canonical candidate among the undefeated, else most wins minus defeats, then canonical rank); a cycle keeps the canonical candidate, ties all and flags `selection_cycle`; reliance on each pair's own distinctive members (§2) | order independence tested; no selection cycle in 1,092 runs; 15 of 145 recorded pairwise reliance comparisons at 1,000 calls decided (all by the readout part), none with a posterior in the tie band |
| B8: the 1-minimality rounds stopped after 3 even when the third removed a member; a certificate removal needed only a ≥ 1/2 pass rate | 3 rounds; removal on "not decisively needed and passes ≥ 1/2" | rounds (and certificate passes) repeat until one removes nothing, at most \|kept\|, else `minimality_unverified`; a removal stands only if the reduced core validates decisively (§4) | unit test (a chain that needs five rounds); no `minimality_unverified` in 1,092 runs; one certificate removal, validated; none rejected |
| B1: the code did not identify itself; §12.9 misstated the MANC comparison; two v1.0 hashes unexplained | `version = "1.1"` for every variant | version 1.2.0; the method file's sha256 in `diagnostics["code"]` and in every prediction's method info (via `_brainir_v1_sha256.py`, checked by a test); §12.9 corrected; `9ca36c4d` and `3a07cf80` differ only by the identifier rename `Oracle`/`oracle` → `Prober`/`prober` (renaming back reproduces `3a07cf80` byte for byte) | test |
| B6: at low budgets the certificate was starved by the screen and the enumeration, and a budget-decided answer looked like a preferred one | no certificate reserve; out-of-budget phases recorded only as errors of a phase | the certificate's calls are reserved before the screen and the enumeration; every phase cut by the budget or its own call cap is listed in `diagnostics["budget_limited_phases"]` with the flag `budget_limited` (§4) | at 50 and 100 calls 108 of 110 runs each are flagged `budget_limited`, with their phases; on the medium suite at 150 / 200 / 300 calls the reserve gives the certificate its calls before the screen (8–17 instead of 1 in the runs v1.1 starved at 150), the cores equal v1.1's in all 48 run pairs, and a certificate that needs more than its reserve is still cut (3, 1 and 0 runs, as in v1.1) — and flagged |
| B7: the seed → replicate map has period 16 | silent | seeds ≥ 16 record a warning in `diagnostics["warnings"]` (§4) | test |
| B5 (optional): calls that changed no core | stress probes for every compared candidate | stress probes only for equal-size pairs that reliance leaves tied (the only pairs they can decide; by construction the same cores) | identical cores and probabilities in all 198 runs with the saving switched off; 108 stress calls saved |
| B3, B4 and the rest of B5 | — | not adopted (they save calls only where they can also change a core, or weaken the essential claims); recorded in §5 and §9 | — |

### 0.2 Version 1.1 (reviews A and G)

The coordinator's held-out adversarial suite (66 instances, v1.0): correct 0.38, confident-wrong 0.51, success_intact 0.41, runs
missing an essential neuron 0.55, latent backup returned 0.15; greedy_plus 0.70 / 0.25 / 0.73 / 0.18 / 0.03, group_probe 0.60 / 0.31 /
0.65 / 0.05 / 0.15. v1.0's contested calibration: p < 0.05 → observed 0.24, 0.05–0.30 → 0.80, 0.30–0.60 → 0.56, ≥ 0.85 → 0.76. No
method flagged degeneracy or handled a function present on a subset of draws. Every row below is a general change; none is an
instance-specific patch.

**Headline (my own adversarial sets, 2 x 88 runs, section 12.2; scored before the scorer's truth definition changed).** v1.1: correct
0.92 (dev) and 0.95 (held out), confident-wrong 0.05 — all of it one trap on which the generator's acceptable core left out two neurons
its own measurement finds essential (failure mode 10; the current scorer counts those runs as correct: 0.97 and 1.00, confident-wrong
0.00) — latent backups returned 0.00, runs missing an essential neuron 0.02 / 0.00, contested Brier 0.023. On the same instances v1.0
reproduces the coordinator's held-out numbers (0.38–0.41 correct, 0.44–0.49 confident-wrong), greedy_plus scores 0.70–0.72 / 0.20–0.22
and group_probe 0.66 / 0.23–0.26. On the plain generator suites v1.1 keeps v1.0's success and consistency except for one instance where
the new fidelity rule changes the answer (and gains the planted mechanism in one medium instance), at +18 % median calls on the
small suite, +65 % on the medium suite and +107 % on the large suite — mostly the masking-robust screen (section 12.4).

| finding (severity) | what v1.0 did | what v1.1 does (section) | evidence (my instances, section 12) |
|---|---|---|---|
| A1 / G1 (blocker): the choice among sufficient sets ignored intact-network necessity; a silent latent backup won at P = 0.90 | keep-only validation → Occam → stress → canonical order; reliance only between sizes, with a fixed margin; essential results not an input; silent fillers allowed | **admissibility first** (§2): a candidate must validate, every member must participate in the intact network (graded rate relative to the canonical mechanism, or measured necessity), every neuron found essential anywhere is added to every candidate (members of alternatives are tested too), dynamics fidelity is checked before size, reliance decides at every size; paired tests with the network's own noise band instead of fixed margins; latent candidates keep 1 % of their weight and are listed in `diagnostics["latent_backups"]` | latent-backup trap correct in 40 of 40 runs, dev and held out (v1.0 on the same instances: 14 of 40); no latent backup returned in any v1.1 run (v1.0: 0.12–0.17 of the runs); runs missing an essential neuron: 1 of 176 (a subset-of-draws copy not recovered; v1.0: 0.56–0.57 of the runs with an essential neuron); regression tests for a latent backup and for a controller with a backup copy |
| A2 / G2 (major): the group-silencing screen cleared an essential gate silenced together with what it gates | passing groups cleared as a whole, most relevant first, first group 25 % of the pool | single silencing of every active inhibitory candidate that projects onto the canonical set or holds down a silent neuron acting on the mechanism or the readout (its release would lift that neuron's mean input above threshold), and of the most relevant active candidates; a second partition interleaved by relevance rank (cleared only if both groups pass); isolates admitted by the pooled test; cap 40 % (§4) | masked-gate trap correct in 56 of 56 runs (v1.0 on the same instances: 15 of 56); ablations in §12.3 |
| A3 / G5 (major): edge-removal predictions were topological guesses | reachability / cycle rule, confidence 0.6 / 0.75, first edge in position order | simulated with the library's edge intervention (`SimQuery.remove_edges`) on the working replicates, in the intact network and in keep-only of the core; confidence = posterior of the predicted side; ties broken by the canonical key; abstention (`None`) when not simulated (§4) | agreement with 8 fresh seeds outside the method: in keep-only of the core 108 of 108 (plain) and 97 of 105 (adversarial), in the intact network 106 of 108 and 93 of 105; stated confidence ≥ 0.8 → observed 0.99 / 0.93 (§12.7); real bundle 13 of 14 conditions (v1.0: 5 of 14, review A; §12.9) |
| A4 / G3 (major): probabilities were evidence-class constants (0.97 / 0.90 / 0.45 / 0.15 / 0.03 …), essential neurons demoted to 0.15 | class values averaged over tied sets; fixed 0.15 loser floor | Beta posteriors of the counts actually held (validation, leave-one-out, necessity), mixed over the candidates by validity × the confidence of the comparison that ranked them; measured necessity is a floor, silence a ceiling; no loser floor; jointly necessary groups reported (§2, §4) | contested Brier 0.023 pooled over my 176 adversarial runs (v1.0 on the same instances: 0.218); reliability in §12.2; equal probabilities for exchangeable relays (distributed drive: gap 0.00) |
| G4 (major): marginal and degenerate evidence reported as certainty | 3 validation seeds, conditional fraction, the canonical set returned when nothing validated; no notion of a distributed mechanism | sequential validation until the posterior is decisive (else `undecided`); paired keys extended while neither decisive for nor against; union of exchangeable, marginally sufficient copies; degeneracy flag (`degenerate`, `distributed`, `no_compact_mechanism`) with membership = pool fraction; unconditional and conditional sufficiency and the intact pass rate on reserved seeds; `no_validated_mechanism` instead of a failed candidate at P ≥ 1/2 (§2, §4) | distributed drive flagged in 16 of 16 runs (v1.0, greedy_plus, group_probe: never); subset of draws correct in 13 of 16 runs, never confident-wrong (v1.0: 0 of 16, 12 confident-wrong) |
| G6 (major) / A9 (minor): the evaluation counted these failures as successes | — | (the harness now scores `success_intact`, missing essentials, latent backups, contested Brier; not method code) — every table here reports them | §12.2, §12.4 |
| G7 (major): the component choices were never tested on adversarial instances | — | every v1.1 component ablated on my adversarial dev suite; greedy_plus and group_probe on the same instances (§12.2, §12.3) | §12.3 |
| A5 (minor): essential claims only for core members | — | claims, pass fraction, `n` and posterior for every neuron tested (`essential`, `diagnostics["essential_tests"]`) | tests |
| A6 (minor): the size–error rationale was a fixed string, points without members | — | every point carries its members; the candidates are on the curve; `why` is generated from the selection record (§4) | tests |
| A7 (minor): roles ignored the interventions (`redundant_backup` on essential neurons) | — | `redundant_backup` only for non-essential members of a validated, participating competing candidate; role probability ≤ inclusion probability (§4) | — |
| A8 (minor): validation, certificate, curve and fidelity reused the selection seeds | — | final fidelity on reserved seeds (offsets 200–229) no selection step touches (§4) | — |
| G8 (minor): binary activity at 0.01 Hz | — | graded mean / peak rates, participation threshold relative to the network's own mechanism (§2) | — |
| G9 (minor): no adversarial property tests | — | tests: a latent backup is never returned and core members participate; a masked gate is found and measured necessity is a probability floor; a distributed drive is flagged with equal, low probabilities; a controller with a backup copy keeps every essential neuron (§12.11) | 31 tests pass (v1.1; 32 in v1.2) |
| G10 (minor): the documented hash did not match the code | — | hashes recorded at the freeze for every file and every table (§7, §12.11) | — |

## 1. What v1 is, in one paragraph

v1 restricts the candidates to the neurons that can possibly shape the readout (exact reachability and signs, then a verified
activity filter), orders them by a permutation-equivariant structural relevance, and runs adaptive group elimination over keep-only sets
in that fixed order until the kept set is 1-minimal (the canonical set). Every accept/reject decision is a sequential strict majority
over parameter replicates on which the intact network works, extended when they disagree. It then measures necessity in the intact
network — a pooled single-silencing test of every canonical member, and a screen of the other active candidates that cannot be fooled by
masking (flagged inhibitory neurons and the most relevant ones silenced alone, the rest in two independent partitions) — and enumerates
the other sufficient sets deterministically, testing the necessity of their members too. Every candidate is completed with every neuron
found essential anywhere in the run. The selection is **admissibility first**: a candidate may become THE mechanism only if its
sufficiency is validated sequentially on fresh replicates until the posterior is decisive, every member participates in the intact
network (graded activity above a threshold relative to the network's own mechanism, or measured necessity), and its keep-only dynamics
are not decisively further from the intact network's than another candidate's (paired test beyond the network's own between-draw noise
band). Among the admissible sets every pair is compared (a round robin, independent of the candidate order) on the intact network's
reliance on the pair's own distinctive members — function failures as paired counts, graded readout changes per member against the noise
band — then Occam, then robustness; the winner is a candidate no other beats decisively. A key inside its noise band, or a posterior at
the edge of the decisiveness threshold (tail mass within a factor of two of the threshold's), is a tie — a later key may not overrule
such a posterior when it leans the other way — and tied sets share the probability mass. Exchangeable copies that are each only marginally sufficient
are merged when their union validates decisively better; a mechanism whose members are all exchangeable with active neurons outside it
is flagged as degenerate (no compact mechanism). The inclusion probabilities are computed from the evidence counts (Beta posteriors of
validation, leave-one-out and necessity decisions, mixed over the candidates by their validity and the confidence of the comparison
that ranked them), with measured necessity as a floor and silence as a ceiling. A paired minimality certificate, a final fidelity on
reserved fresh replicates that the selection never saw, a size–error curve with the actual reason for the choice, essential claims for
every neuron tested, roles conditioned on the interventions, simulated edge-removal predictions and, when the bundle holds a network of
another dataset, identity claims from a verified transfer of the final core (from the same budget pool, never changing the core)
complete the result. The search itself is unchanged from v1.0: canonical, deterministic given the seed, independent of the node order
up to exact automorphisms.

## 2. Formulation

Let `U` be the candidate neurons (everything except stimulus and readout) and `θ ~ P` the model's parameter replicates. For `S ⊆ U`,
`keep(S)` keeps only `S` (plus stimulus and readout) and `sil(A)` silences `A` in the intact network. The functional criterion turns a
simulation into a verdict `pass ∈ {0, 1}`. A replicate is *working* if the intact network passes on it; on the others no member can be
told from a non-member. Write

* `π(S) = P_θ[pass(keep(S)) | pass(intact)]` (conditional sufficiency; the selection's quantity), `π_u(S) = P_θ[pass(keep(S))]`
  (unconditional sufficiency; reported by the final fidelity) and `ι = P_θ[pass(intact)]` (the intact pass rate);
* `σ(A) = P_θ[pass(sil(A)) | pass(intact)]` (function surviving the silencing of `A` in the intact network).

Every rate the method reports or compares is estimated from counts `k` of `n` with a uniform prior, i.e. the posterior
`Beta(1 + k, 1 + n − k)`, and states the posterior probability of its side of 1/2, `P(rate > 1/2 | k, n)`. The elimination's
accept/reject decisions and the pooled necessity verdict remain strict majorities (below and section 4) and carry their posteriors;
validation and the certificate are *decisive* at `D = 0.95`. A **paired comparison** between two candidates (fidelity, reliance, union,
stress) decides only when the tail mass of its posterior is below half of the threshold's, `1 − P < (1 − D) / 2` (`P > 0.975`); a
posterior in the **tie band** `[1 − 2(1 − D), 1 − (1 − D)/2]` = `[0.90, 0.975]` does not decide (review B finding B2). The general
ground: a threshold is a convention for an acceptable error rate, and error rates within a factor of two of `1 − D` (2.5–10 %) are
equally conventional — the ±50 % perturbation of review B's sensitivity analysis. A comparison that one of these equally defensible
thresholds would reverse is not decided by the evidence, so it is extended to the replicate cap and, if its posterior is still in the
band, reported as a tie that shares the probability mass (`decisive_margin` = 2 is this factor). In the lexicographic comparison of
candidates (below) the band also binds the keys that come after reliance: when a reliance posterior lies in the band, Occam or
robustness decides the pair only if it agrees with the side the evidence leans to; against it the pair is tied. As the evidence for
the larger of two candidates grows, the answer therefore moves from the smaller one (Occam) through a tie to the larger one
(reliance) — never by a jump at the band's edge.

Definitions:

* `S` is **sufficient** if `π(S) > 1/2`; **1-minimal** if in addition `π(S \ {x}) < 1/2` for every `x ∈ S`, as decided by the
  elimination's strict majorities (section 4).
* `x` is **essential** if `σ({x}) < 1/2`, decided by the *pooled necessity test*: all working replicates of the run (no early stop;
  a split is extended to up to 5), pooled with up to 3 fresh validation replicates on which the intact network passes — essential iff
  more than half of the pooled replicates fail. Its evidence is `p_ess(x) = P(fail rate > 1/2 | n_fail, n)`. Every neuron the run
  tests is reported with its pass fraction, `n` and `p_ess` (`diagnostics["essential_tests"]`, `essential`). `Ess` = the neurons found
  essential anywhere in the run (canonical members, screen isolates, members of alternatives).
* **Participation.** `r̄_i` and `r̂_i` = the mean and peak rate of neuron `i` in the analysis window, averaged over the working
  replicates (graded activity, `Outcome.mean_rate_hz` / `peak_rate_hz`). `i` participates if `r̄_i ≥ τ`, or `r̂_i ≥ 10 τ` (a transient
  member), or `i ∈ Ess` (a neuron whose silencing breaks the function is used whatever its rate); `τ = max(0.05 Hz, 0.01 × median r̄`
  over the canonical set's members with `r̄ ≥ 0.05 Hz)` — relative to the network's own mechanism, not an absolute activity bit.
* A **candidate** is `C = S ∪ Ess` with `S` the canonical set or an enumerated alternative (section 3). Measured necessity is
  therefore a hard constraint: no candidate can win without a neuron the run found essential.
* **Validation status** of `C`: its keep-only on fresh validation replicates on which the intact network passes, sequentially (at least
  3, at most 12) until `v(C) = P(π(C) > 1/2 | k, n)` is decisive: *validated* if `v ≥ D`, *failed* if `v ≤ 1 − D`, else *undecided*.
* `C` is **admissible** if it is validated and every member participates. A validated candidate with a non-participating member is a
  **latent backup** (sufficient in isolation, not what the intact network uses).
* **Fidelity** of `C` against the best admissible candidate `B` (highest validation, then lowest mismatch): (i) sufficiency — the
  discordant replicates of the two validations, `P(π(B) > π(C)) = P(rate > 1/2 | n_BC, n_BC + n_CB)`; (ii) dynamics — on the
  replicates where both pass, `m_C(θ) = Δ(readout | intact(θ), keep(C; θ))`, the mean relative difference (each term in `[0, 1]`) of the
  readout statistics (criterion score, readout peak / mean / range, active readout count, frequency, criterion-specific means), and a
  paired t test that `m_C − m_B` exceeds the noise band `δ`. `C` is **decisively less faithful** if either confidence is beyond the
  tie band (> 0.975; the dynamics test needs ≥ 3 common replicates). A comparison that is neither decisive for nor against
  (`0.025 < P ≤ 0.975`) is extended: both candidates are validated on 4 more common replicates at a time, up to 12.
* **Noise band** `δ = √2 × median_{θ ≠ θ'} Δ(readout | intact(θ), intact(θ'))` over 12 intact-passing replicates (the working seeds and
  the first intact-passing validation seeds, simulated if needed): the intact network's own between-draw variability of the readout
  statistics. A per-replicate mismatch or reliance varies on that scale, a difference of two on `√2` times it; a paired difference
  inside `δ` is a tie, not a decision.
* **Reliance** of the intact network, pair by pair (review B findings B2, B9): for candidates `A`, `B` the distinctive members are the
  pair's own, `D_A = A \ B` and `D_B = B \ A` (adding an unrelated candidate cannot change the comparison). On each replicate both
  sets are silenced in the intact network, and the two parts of the evidence are tested as what they are:
  - **failures** — `n_AB` replicates on which silencing `D_A` breaks the function and silencing `D_B` does not, `n_BA` the reverse:
    `P(A is relied on more) = P(rate > 1/2 | n_AB, n_AB + n_BA)`, the paired discordance rule of the sufficiency comparison. A function
    failure is an event of the whole network, not scaled by the number of neurons silenced: a set whose silencing never breaks the
    function is not needed by the intact network on those draws, whatever its size;
  - **readout** — on the replicates on which neither silencing breaks the function, the relative readout change per distinctive member,
    `Δ(readout | intact(θ), sil(D_A; θ)) / |D_A| − Δ(readout | intact(θ), sil(D_B; θ)) / |D_B|` (a larger set must change the readout
    proportionally more), a paired t test beyond `δ`.
  The failures decide first; the readout part decides only if the failures do not point the other way; either needs a posterior beyond
  the tie band. Measured on the 5 working replicates, then extended with intact-passing validation replicates (4 at a time, up to 12)
  for every pair that is undecided with a part of its evidence in the undecided zone. (Version 1.1 tested the sum of both parts per
  member with a t model — a bimodal statistic whose mean was carried by a few failing replicates, review B finding B2.)
* **Robustness** `r(C)`: keep-only passes under a stress ensemble (half the probes with every parameter sd doubled, half with
  multiplicative weight noise sd 0.2), `k/n` with independent Beta posteriors; decisive only beyond the tie band of `0.99` (> 0.995: 4/4
  against 0/4). Measured only for equal-size pairs that reliance leaves tied — the only pairs it can decide.

**Objective.** Return `M* = argmax` over the candidates in this lexicographic, uncertainty-aware order:

1. **admissibility** (validated and participating). If no candidate is admissible, the undecided participating candidates compete and
   the result is flagged `undecided`; if none of those exists either, the best available set is reported at low probability with the
   flag and diagnostic `no_validated_mechanism` — a failed or latent candidate is never returned at `P ≥ 1/2`;
2. **minimality**: an admissible candidate that strictly contains another admissible one drops out;
3. **fidelity before size**: candidates decisively less faithful than the best drop out;
4. a **round robin** (review B finding B9): every pair of the remaining candidates is compared on the first key that separates them —
   **reliance** (failures, then readout, beyond the tie band; any size), then **Occam** (fewer members), then **robustness**, where a
   later key does not overrule a reliance posterior in the tie band that leans the other way (the pair is then tied) — and the
   winner is a candidate that no other candidate beats decisively: the canonical candidate if it is undefeated, else the undefeated one
   with the most wins minus defeats, then the canonical rank of its members. The other undefeated candidates are *tied* with it and share
   the probability mass; a defeated candidate keeps the weight of its strongest defeat. If every candidate is defeated by some other (a
   cycle of decisive comparisons — the keys are of different kinds, so the comparator need not be transitive), the canonical candidate is
   kept, every candidate is tied and the result is flagged `selection_cycle`. The winner therefore never loses decisively to anyone, and
   it does not depend on the order of the candidate list;
5. **union of exchangeable copies**: if `M*` fails on validation replicates on which the intact network works, the intact network uses
   something else there (section 4); the union replaces `M*` only if it is validated, participates and validates decisively better on
   the same replicates (paired discordance);
6. **minimality with evidence** (paired, sequential certificate, section 4); essential and union members are exempt; a removal stands
   only if the reduced core validates decisively under the same sequential rule as every candidate (review B finding B8);
7. **degeneracy**: `M*` has ≥ 3 members, none essential, and its members are exchangeable — at least half of them share a structural
   signature (identical presynaptic and postsynaptic partner sets) with other members and with active candidates outside the core, or
   every canonical member whose replacement was searched (≥ 2) has a one-for-one filler. Then no compact mechanism exists: the result
   is flagged `degenerate`, `distributed`, `no_compact_mechanism`, and every neuron of the exchangeable pool gets the fraction of the pool
   the core uses (section 4).

**Uncertainty model.** For every candidate `C` (the competitors, the fidelity-excluded, the non-minimal, the latent and the failed),
`P(C) = v(C) × w(C) / Σ_{C' participating} w(C')` if every member participates, else `v(C) × 0.01`, with the preference `w = 1` for the
winner and the tied candidates, `w = 1 − conf` for a candidate a paired key ranked below another candidate (reliance, fidelity,
stress, union: the confidence of that test; the strongest of its defeats), `w = 0.5^{Δsize}` when only Occam separated them (Δ relative
to the candidate that beat it; also for a candidate that strictly contains an admissible one), and `w = 1 − P(winner validates better)` (paired discordance) for a participating candidate outside the competition
(failed or undecided while the winner validated). Then

`p_i = min(0.99, Σ_C P(C) q_i(C))`, with `q_i(C) = P(i is needed in C)` = the paired certificate's `P(core better than core \ {i})` for
the returned core, the posterior of the elimination's failed leave-one-out decision for the other candidates, `p_ess(i)` if larger, 1
for members of an adopted union and for returned members no test addressed after a complete search, 0.60 if the budget ran out first.
**Floors and ceilings:** an essential neuron keeps at least `min(0.99, p_ess(i))`; a neuron silent in every working replicate and
cleared by the verified activity filter keeps at most 0.01, a neuron cleared by a passing group or leave-one-out decision at most 0.03
unless a candidate holds it, a structurally excluded one 0.002. A degenerate pool shares `fraction_needed × max(v(M*), 1/2)` equally.
Interchangeable neurons therefore get equal or nearly equal probabilities (they sit in equally supported candidates; their need
posteriors differ only by the number of replicates each was tested on), a latent backup never reaches 0.5, a candidate that failed
validation contributes at most 5 % of its weight, and no probability is a fixed class constant apart from the three ceilings of
neurons outside every candidate.

## 3. Algorithm

```
discover(problem, sim, seed, cfg):
  working <- replicate seeds b+17.. (b = (seed mod 16) x 300) on which the intact network passes (3; more on demand)
  r̄, r̂ <- graded activity of the intact network on the working replicates
  K <- U ∩ {excitatory-reachable from the stimulus} ∩ {reaches the readout} ∩ {sign != 0}        # exact, no calls
  if decide(K \ silent_in_intact): K <- K \ silent_in_intact                                      # verified activity filter
  key(i) <- (log relevance(i) [+ w·logit(prior_i)], weighted degree(i)) on the subgraph K ∪ stimulus ∪ readout  # equivariant
  M1 <- eliminate(K, order = sort(K, key) ascending)                                             # canonical 1-minimal set
  if validate(M1) failed: add a failing replicate to the working seeds; M1 <- eliminate(K, ...)
  τ <- max(0.05 Hz, 0.01 x median r̄ over M1)                                                     # participation threshold
  necessity(x) for x in M1                                        # pooled single silencing, essential claims with k/n
  reserve the certificate's calls ((validation_seeds + 1) x non-essential members of M1, at most 20 % of the budget)
  screen(K \ M1):                                                 # robust to masking
      singles: every active inhibitory candidate q with an edge onto M1, or onto a held-down neuron x (silent; x is a readout
               neuron or projects onto M1 or the readout; its mean input from the active network is below its mean threshold and
               would exceed it without q's inhibition), plus the max(4, min(15 %, 4 x |M1|)) most relevant active candidates
               -> silenced alone; a failure goes to the pooled test
      partition 1: adaptive group silencing of the rest (failing groups bisected down to single neurons -> pooled test)
      partition 2: members of passing groups re-tested in groups interleaved by relevance rank; cleared only if both groups passed
  alternatives <- disjoint(K \ M1) ∪ replacements(x) for non-essential x in M1  # deterministic enumeration (fillers may be silent)
  necessity(x) for every member x of every alternative
  C <- [M1 ∪ Ess] + [A ∪ Ess for A in alternatives]
  select(C)                                   # admissibility -> minimality -> fidelity -> round robin (section 2): every pair on
                                              # reliance (failures as paired counts, readout per member), Occam, stress (equal
                                              # sizes only); undefeated winner; undecided keys get more replicates, up to 12;
                                              # a reliance posterior in the tie band: tie unless Occam /
                                              # stress agree with its lean
  M* <- union_repair(M*)                      # exchangeable copies, each marginally sufficient
  necessity(x) for x in M*;  degeneracy(M*)
  M* <- certify(M*) unless degenerate;  jointly necessary groups {x} ∪ fillers(x)
  final fidelity on reserved fresh replicates; size-error curve; probabilities (section 2)
  roles conditioned on the interventions; simulated edge-removal predictions
  return M*, p, essential (every neuron tested), alternatives, roles, loop, dynamics of the intact network, fidelity,
         diagnostics (selection record, pairwise reliance, latent backups, flags, essential tests, predictions, curve,
         budget-limited phases, code identity), [cross-connectome claims]

eliminate(K, order):                                  # greedy_plus's adaptive group testing, deterministic order (unchanged)
  queue <- order; chunk <- 25 % of the queue
  while queue:
    X <- next chunk; if decide(K \ X): K <- K \ X; chunk *= 2; move neurons silent in the passing runs to the front
    else: bisect X (keep the half whose removal passes removed) down to one necessary neuron; chunk /= 2
  repeat until a round removes nothing (at most |K| rounds; else flag minimality_unverified):   # 1-minimality
      for x in order: if decide(K \ {x}): K <- K \ {x}
  return K

decide(S): run the working replicates one at a time until the strict majority of 3 is determined; if they disagreed,
           continue with further working replicates until the strict majority of 5 is determined (adaptive replication)

replacements(x): excluded <- {x}; up to 2 times:
    start <- K \ excluded (or U \ excluded if that fails: a filler may be silent -> the set is a labelled latent backup)
    A <- eliminate(start, protected = M1 \ excluded); record A; excluded <- excluded ∪ (A \ M1)

union_repair(M*):
    U <- M* ∪ one-for-one fillers of its members (replacement candidates that swap one member for <= 2 neurons)
    up to 3 rounds: F <- validation replicates on which the intact network passes and U fails
                    U <- U ∪ eliminate(K, working seeds = F, protected = U)
    adopt U iff validated, participating and P(π(U) > π(M*)) > 0.975 on the common replicates (extended to 24 while 0.8 <= P <= 0.975)

certify(M*):  repeat until a pass removes nothing (at most |M*| passes): for x in M* \ (Ess ∪ union), least relevant first:
    compare M* and M* \ {x} on the working seeds, then on fresh intact-passing replicates one at a time (up to 12):
    keep x as soon as P(M* better) >= 0.95 after >= 3 fresh replicates; remove x only if never decisive, M* \ {x} passes >= 1/2
    and validate(M* \ {x}) is decisive (else the unreduced core stands)
```

Cross-connectome step (section 10; only when the bundle holds a network of ANOTHER dataset, only after the core is final and
validated, never changing the core):

```
  allowance <- min(calls left, 0.25 x declared budget, 60 x (|M*| + 2));  skip if < 30          # same budget pool as the core
  aux <- sim.spawn(other network, max_calls=allowance)                                            # counted in sim.total_calls()
  tr <- joint verified transfer of M*   # image -> keep-only probes -> minimisation -> counterparts of essential members
                                        # -> reliance of the other intact network -> validation on >= 2 fresh replicates
  if tr verified (validated, completely minimised, essential structure reproduced, relied on by the other intact network):
      if the matched, mutually aligned pairs pair up all members of M* and of the image one to one:
          identity claims <- those pairs whose fingerprint evidence beats 'none' in BOTH directions;
                             confidence = calibrated identity probability sigmoid(a + b logit(w_ab w_ba) + c edges)
  elif calls left in the allowance >= 60: own v1 discovery of the other network (no identity claims), with the transported
                                          prior unless the image was rejected on causal grounds
  role_alignment <- roles and signed role graphs of M* and the other network's mechanism (separate output)
```

## 4. Decisions, acquisition and stopping

* **Decisions** (unchanged from v1.0). Sequential strict majority over working replicates (greedy_plus): 2 agreeing replicates settle
  a decision, a split goes to 3, and a split verdict is re-decided by the strict majority of up to 5 working replicates (adaptive
  replication; the same replicates for every decision, so outcomes are shared through the cache).
* **Validation** is sequential (review G finding 4): keep-only of a candidate on the validation replicates on which the intact network
  passes (the intact run of each replicate is shared by every candidate and by the pooled necessity tests), at least 3, stopping as
  soon as `P(π > 1/2)` is ≥ 0.95 or ≤ 0.05, at most 12 (then *undecided*). Paired keys need common replicates, so every admissible
  candidate is validated on the same number of replicates, and the winner on as many as any participating candidate (on 12 when the
  intact network fails on some draw: the replicates on which the winner fails while the intact network works are the evidence of the
  union repair). 3/3 is not decisive (`P = 0.9375`): a clean candidate needs 4/4.
* **Necessity screen** (review A finding 2, review G finding 2): a passing group silenced together is not evidence that each member is
  individually unnecessary (a gate silenced with the excitation it gates, a competitor with its suppressor). (1) Singles: every active
  inhibitory candidate `q` with an edge onto a canonical member, or onto a *held-down* neuron `x` — silent in the intact network, acting
  directly on the mechanism (a readout neuron, or an edge onto a canonical member or a readout neuron), whose mean input from the active
  network (intact mean rates x the model's synaptic scales `b_exc`, `b_inh`) is below its mean firing threshold (`theta_mean` x its size
  scaling) but would exceed it without `q`'s inhibition — the signature of disinhibition, computed from public model parameters and the
  intact rates without a call; plus the most relevant active candidates, 15 % of the pool but at least 4 and at most 4 per canonical
  member (the neighbourhood of a compact mechanism does not grow with the network); all silenced alone; (2) partition 1: adaptive group
  silencing of the rest, failing groups bisected (both halves tested) down to single neurons; (3) partition 2: the members of every
  passing multi-neuron group re-tested in groups interleaved by relevance rank, so that neighbours in the structural order (a gate and its
  drivers) fall into different groups — a neuron is cleared only if both of its groups passed. Every isolated neuron is admitted only by
  the pooled test. Cap: 40 % of the budget. The groups of both partitions are in `diagnostics["necessity_screen"]`.
* **Acquisition.** The probe sequence is fixed by the canonical order and the outcomes: the chunk doubles after a passing group and
  halves after a failing one; bisection isolates one necessary neuron per failing chunk (about `k log2(n/k)` decisions for a `k`-member
  mechanism among `n` candidates); neurons that fall silent in a passing probe are queued first. Full-network probes are used for what
  keep-only probes cannot see: essentiality, the screen, reliance, joint necessity and edge removal. There is no random order, restart
  or sample anywhere.
* **Union repair** (review G finding 4, subset of draws): the elimination is re-run from the whole restricted pool on the replicates on
  which the current set fails while the intact network works (the current set protected), for up to three rounds; together with the
  winner's one-for-one fillers this gives a union. It replaces the winner only if it validates, participates and validates decisively
  better (paired discordant replicates, beyond the tie band; extended to 24 replicates while `0.8 ≤ P ≤ 0.975`). Union members are needed on some draws, not
  on most, so they are exempt from the leave-one-out certificate. A validated union that was not adopted is reported as a larger
  alternative.
* **Minimality certificate** (paired, sequential, lazy): for every member that is neither essential nor part of an adopted union, the
  core and the core without it are compared on the same replicates — the working seeds, then fresh intact-passing validation replicates
  one at a time. The member is kept as soon as the core is decisively better (after at least 3 fresh replicates; a member needed on only
  part of the draws is kept), and removed only when all fresh replicates show no decisive disadvantage, the reduced set passes on at
  least half of them (Occam) and the reduced set validates decisively under the same sequential rule as every candidate — otherwise the
  unreduced core stands and the rejected removal is recorded (`removals_rejected`; review B finding B8). The check repeats after a
  removal until a pass removes nothing (at most |core| passes; `minimality_verified`). The posterior `P(core better)` is the member's
  `q_i`.
* **Jointly necessary groups** (review A finding 4): for every non-essential core member with one-for-one fillers, the group {member,
  fillers} is silenced together on all working replicates; a failing group is reported as "at least one of these is necessary" with its
  pass fraction, `n` and posterior (`diagnostics["jointly_necessary"]`).
* **Selection** (review B findings B2, B9): after the fidelity filter, every pair of candidates is compared (round robin) on reliance
  (the pair's own distinctive members; failures as paired counts, then the readout change per member against the noise band; each
  pair extended by 4 intact-passing replicates at a time, up to 12, while undecided), then Occam, then stress (probes only for
  equal-size pairs still tied). Every comparison decides only beyond the tie band, and a reliance posterior inside the band blocks a
  later key that points the other way (the pair is then tied, key `tie band` in the selection trace). The winner is undefeated; the
  record of every pair (counts, posteriors, whether a posterior was in the tie band and which way it leans) is in
  `diagnostics["reliance_pairs"]` and the wins and defeats in `diagnostics["selection"]["round_robin"]`.
* **Stopping rule.** The elimination stops when the kept set is 1-minimal (its leave-one-out rounds repeat until one removes nothing, at
  most |kept| rounds; a cap reached while rounds still remove members flags `minimality_unverified`, review B finding B8); the
  enumeration when no further sufficient set exists
  outside the exclusions, or after 4 alternatives / 2 fillers per member / half of the remaining budget; validation as above. The method
  stops when all phases are done — never because the budget is used up; unspent budget is not used. If the budget does run out, the
  current passing set (every removal verified) is returned with 0.60 for untested members and `budget_exhausted` in the diagnostics;
  finishing phases are guarded (running out ends the phase, an unexpected error is recorded, the mechanism found is kept).
* **Budget reserves and budget-limited answers** (review B finding B6): each phase keeps back the calls later phases need — the final
  fidelity (2 x 4 + 2 calls, at most 10 % of the budget) throughout, and, from the screen on, the certificate ((validation_seeds + 1)
  calls per non-essential canonical member, at most 20 % of the budget), because the certificate is evidence about the returned core
  while the screen and the enumeration select among alternatives. Every phase in which a simulation was refused for budget reasons
  (or whose own call cap ended it) is listed in `diagnostics["budget_limited_phases"]`, with the flag `budget_limited`: a low-budget
  answer is visibly one that the budget, not the evidence, may have decided.
* **Final fidelity** (review A finding 8): keep-only of the returned core and the intact network on RESERVED fresh replicates that no
  selection step used (block offsets 200–229), until 4 intact-passing replicates: unconditional sufficiency `π_u` with its 90 % interval,
  conditional sufficiency `π`, the intact pass rate `ι`, frequencies; plus the selection's own validation (status, k/n), reliance, stress
  and dynamics mismatch of the core (`result.fidelity`).
* **Size–error curve** (review A finding 6, `diagnostics["size_error_curve"]`): validation error of three passing sets along the
  canonical search path, of every candidate (with kind, status and participation), of the returned core and of the core without each
  member (certificate) — every point with its member list. The returned point carries `why`, generated from the selection record: context
  members added because their silencing breaks the function, latent backups excluded, candidates excluded for worse dynamics, the key that
  ranked the other candidates (reliance, size, stress, union), ties, the union.
* **Intervention predictions** (review A finding 3, review G finding 5; `diagnostics["intervention_predictions"]`): for every core
  member, (a) silencing it alone in the intact network — the pooled test, with pass fraction, `n` and confidence `max(p_ess, 1 − p_ess)`;
  (b) removing its strongest in-core edge (outgoing, else incoming, self-loop included; ties broken by the canonical key of the other
  end, so the choice does not depend on the node order) — simulated with the library's edge intervention (`SimQuery.remove_edges`, one
  call per replicate) on the working replicates, in the intact network and in keep-only of the core, each a sequential strict majority
  with the posterior of its side of 1/2 as the confidence. At most 8 members (most relevant first) are simulated; a prediction that was
  not simulated is `None` (abstention), never a structural guess.
* **Roles** (review A finding 7): the generic role rules of v1.0 (sign, core wiring, criterion) for core members; `redundant_backup`
  only for non-essential members of a validated, participating competing candidate; every role probability is capped at the neuron's
  inclusion probability.
* **Seeds.** Replicate seeds of one run live in a block `b = (seed mod 16) × 300`: working `b+17..b+96`, selection validation
  `b+120..b+199` (also pooled into the necessity tests and the certificate), final fidelity `b+200..b+229` (reserved), stress
  `b+230..b+269`. Every seed is below 5,000 (5,000+ is reserved for independent scoring), below 1,000 at seed 0, never in 1000–1015
  (offsets 97–119 are never used, so block 900 skips 997–1019); joint's seeds use `seed mod 4`. A node-order variant assigns the
  per-neuron parameters of a seed differently, so the replicates of two node orders are different draws. The map from seed to block
  has period 16: seeds that agree modulo 16 give the same run, and a seed ≥ 16 records a warning in `diagnostics["warnings"]` (review B
  finding B7) — a reliability sweep over more than 16 seeds would otherwise count duplicated runs as agreement.
* **Code identity** (review B finding B1): every result records `diagnostics["code"]` = {method, version 1.2.0, sha256 of the method
  file}, and the method info of every prediction carries `method_file_sha256` and `method_version`. A method module may not read files,
  so the sha256 is written into `_brainir_v1_sha256.py` when the method file is frozen; a test checks that it matches the file.

## 5. Where each component comes from, and the evidence

Selection-suite numbers are from `SELECTION_RESULTS.md` (57 held-out instances x 2 node orders x 3 seeds, 1,000 calls; "identity"
= mean pairwise Jaccard / fraction of instances whose 6 runs agree). Adversarial numbers are from my own adversarial instances
(section 12.2; review G's traps, built with the third-party generator) and the ablations of section 12.3.

| component | source | evidence for it |
|---|---|---|
| exact restriction (excitatory reachability from the stimulus, reachability of the readout, sign) + verified activity filter | greedy_plus (reachability, verified activity pruning), group_probe (excitatory reachability, sign 0) | every candidate that uses it reaches structural success 1.00; on the real network it leaves ~90 of 4,459 candidates (greedy_plus: 87) |
| canonical deterministic order (structural relevance, least relevant removed first) | group_probe (the only candidate without a random search order); relevance = surrogate_search's random-walk mass, restricted to excitatory forward flow | identity 0.95 / 0.86 for group_probe vs 0.88 / 0.75 greedy_plus (seeded random order), 0.91 / 0.81 cem_search, 0.86 / 0.68 evo_pareto, 0.85 / 0.63 surrogate_search, 0.83 / 0.63 greedy_reference; at 50 calls group_probe keeps ~0.91 identical cores, greedy_plus ~0.69 |
| adaptive group elimination with bisection and activity queue; 1-minimality rounds | greedy_plus | median 88 calls (68 small / 192 medium / 244 large), success 1.00 at every budget from 50 to 2,000 calls |
| sequential strict majority over 3 working replicates, adaptive replication of split decisions (up to 5) | greedy_plus; racing / Hoeffding argument (methods_review §4) | best robust pass (0.93) of all candidates; the extension fires where replicates disagree |
| graded participation with a threshold relative to the network's own mechanism; latent backups weighted by 0.01 and listed | new in v1.1 (review G findings 1 and 8; the library's graded `Outcome` rates) | latent-backup trap: 10 of 10 main-order dev runs with it, 8 of 10 without (a latent backup returned twice; §12.3); 40 of 40 on my dev and held-out sets |
| measured necessity as a hard constraint (every candidate completed with `Ess`; members of alternatives tested) | new in v1.1 (review A finding 1, review G finding 1) | review A's fix 1 (a neuron essential only in an alternative's context constrains every candidate); no effect on my trap instances (§12.3) |
| sequential validation to a decisive posterior; undecided / no-validated-mechanism outcomes | new in v1.1 (review G finding 4) | a failed or latent candidate is never returned at P ≥ 0.5 (by construction: a failed candidate keeps at most 5 % of its weight, a latent one 1 %; every core returned on my suites came from a validated candidate) |
| fidelity before size (paired sufficiency discordance, paired dynamics mismatch beyond the noise band) | new in v1.1 (review G finding 1, fix 3) | fragile-vs-robust trap: 4 of 4 with it, 3 of 4 without (§12.3); excludes the planted latch of one plain instance (failure mode 3) |
| reliance at every size, pair by pair: failures as paired discordant counts, readout change per member against the noise band | greedy_plus's reliance-first ranking, restored at every size (review A finding 1, review G finding 7); per-member normalisation of the readout part from v1.0; the split into failure counts and readout (review B finding B2) | review A's fix 3; no effect on my trap instances, where participation and fidelity decide first (§12.3); decides the real MANC core at P = 0.984 on 5 against 0 discordant failures instead of a t posterior of 0.954 (§12.10) |
| round robin with an undefeated winner (the canonical candidate among the undefeated) | review B finding B9 (the v1.1 incumbent tournament could file a candidate that beat the winner as tied and depended on the candidate order) | order independence is tested (`test_round_robin_winner_does_not_depend_on_the_candidate_order`); no selection cycle on my suites (§12.10) |
| tie band for paired comparisons (tail mass within a factor of two of 1 − decisive); a later key does not overrule a reliance posterior in the band that leans the other way | review B finding B2 | the real-bundle cores at decisive 0.90 / 0.95 / 0.975: the only core that changes is a tie at the setting that changes it (§12.10); no dev run had a reliance posterior in the band (§12.10) |
| Occam, then stress robustness (independent binomials, beyond the tie band of 0.99), probes only for equal-size pairs reliance leaves tied | greedy_plus's ranking; the lazy probes from review B finding B5 | between equal-size redundant pairs, 3–4 stress probes cannot decide anything smaller than 4/4 vs 0/4 (v1.0 development); the lazy probes return the same cores in every run of my suites (§12.10) |
| single silencing of flagged gates (held-down neurons acting on the mechanism) and of the most relevant candidates before the group screen | group_probe's single-neuron screen (re-adopted in part, review G finding 7); the disinhibition signature from review G finding 2 | masked-gate trap: 14 of 14 with the singles, 13 of 14 with only the second partition, 4 of 14 with neither (§12.3); 56 of 56 on my dev and held-out sets |
| second, interleaved partition of the group screen | review G finding 2 | backs up the singles (13 of 14 masked gates without them); covers masking by non-inhibitory competitors (§12.3) |
| union of exchangeable, marginally sufficient copies | new in v1.1 (review G finding 4) | subset-of-draws trap: 4 of 4 main-order dev runs with it, 0 of 4 without (§12.3); 13 of 16 on my dev and held-out sets, never confident-wrong |
| degeneracy detection (structural signatures, one-for-one fillers) | new in v1.1 (review G finding 4) | distributed-drive trap: 4 of 4 flagged with it, 0 of 4 without (2 then confident-wrong; §12.3); 16 of 16 on my dev and held-out sets |
| deterministic enumeration of alternatives (disjoint complements, per-member replacements, iterated exclusion of found fillers) | greedy_plus (disjoint + replacement), group_probe (backup search per non-essential member), evo_pareto / group_probe §8 (hitting-set exclusion levels) | two_implementations functional success 0.98 (greedy_plus) and 1.00 (surrogate); the enumeration replaces greedy_plus's randomized restart |
| paired sequential minimality certificate on fresh replicates | cem_search / surrogate (verify after cleanup), greedy_plus (leave-one-out); pairing and the sequential rule new in v1.1 | a member needed on only part of the draws is kept (the v1.0 majority rule removed exchangeable latches) |
| evidence-count probabilities mixed over the candidates, floors and ceilings | cem_search (verified-set mixture); Beta posteriors (review A finding 4, review G finding 3) | contested Brier 0.023 pooled over my 176 adversarial runs (v1.0 on the same instances: 0.218; reliability in §12.2) |
| final fidelity on reserved fresh seeds | review A finding 8 | no selection step touches offsets 200–229 |
| generic roles from sign, core wiring and criterion, conditioned on the interventions | greedy_plus; review A finding 7 | role accuracy 0.95 (greedy_plus, selection suite) |
| simulated edge-removal predictions | review A finding 3, review G finding 5; the library's `SimQuery.remove_edges` | agreement with 8 fresh seeds outside the method: 214 of 216 plain predictions, 190 of 210 adversarial ones (section 12.7) and 13 of 14 on the real bundle (section 12.9); v1.0's structural rule was wrong on 27 % (review A) and 17 % (review G) of its predictions |
| verified cross-connectome transfer of the final core, from the same budget pool; identity claims only from a verified transfer | joint (verified transfer, correspondence), reworked after review E | section 12.8 |

**Dropped, and why.**

* *Surrogate model* (surrogate_search): no predictive skill where it would matter (pre-registered Brier 0.218 vs base rate 0.212 at
  n = 500), lowest identity consistency (0.85 / 0.63), functional success 0.27 at 50 calls.
* *Cross-entropy sampling* (cem_search): stochastic samples make the path seed-dependent (0.91 / 0.81) and it has the lowest planted
  success (0.93). Its exoneration idea is kept as the activity queue.
* *NSGA-II evolution* (evo_pareto): 823 median calls, identity 0.86 / 0.68. Its knee / MDL framing survives as the size–error curve.
* *Randomized restarts and random chunk order* (greedy_plus): the source of its lower consistency (0.88 / 0.75); replaced by the
  canonical order and the deterministic enumeration. (Review G noted that the random chunk order found a masked gate by chance in 19 of
  24 runs where the canonical order missed it systematically; v1.1 finds it deterministically through the flagged singles.)
* *Bernoulli posterior and max-entropy group choice* (group_probe): not needed once the order is canonical. *Spend-down and a full
  single-neuron screen of the whole pool* (group_probe): the large-graph cost (706 calls, 851 s median); v1.1 re-adopts single
  silencing only for the flagged and most relevant candidates and tests the rest in two partitions.
* *v1.0's fixed margins* (reliance 0.05 / 25 %, validation 0.5, stress 1.0) and its fixed loser floor 0.15: replaced by paired tests
  with the noise band and by evidence-weighted candidates (reviews A 1 / 4, G 3 / 4).
* *v1.1's reliance statistic* (failure indicator plus readout change, per member, one t test) and its incumbent tournament: replaced in
  v1.2 by the two-part pairwise test and the round robin (review B findings B2, B9).
* *Not adopted from review B* (they would change results, or save calls only on instances where they could also change a core): a
  sequential stop of the pooled necessity test (essential claims keep the full pooled test), shorter screening simulations and ranked
  gates (B3), seeded replacement searches and an aborted disjoint search (B4), skipping the pooled re-test of an alternative's member
  the screen already cleared (B5: the pooled test adds replicates and can reverse a clean screen pass on a marginal neuron). The
  choice among equally sufficient, admissible 1-minimal sets stays a heuristic (fidelity, reliance, Occam) without a success
  guarantee; where it is not decisive the candidates are reported tied (B4).

## 6. Switches (every component can be turned off by configuration)

Every switch, turned off, runs and returns a valid result within the budget: the search switches alone, the finishing-phase switches
(each only skips its own phase) in three groups (`test_every_switched_off_configuration_runs_within_budget`).

| switch (default) | off means |
|---|---|
| `structural_pruning` (True) | every candidate enters the pool (no reachability / sign exclusion); probabilities 0.002 are not assigned |
| `activity_pruning` (True) | neurons silent in the intact runs stay in the pool (more elimination decisions) |
| `use_structural_prior` (True) | seeded random removal order instead of the canonical one: the choice among equivalent sets depends on the seed and node order |
| `use_group_testing` (True) | one candidate per probe (plain backward elimination, `O(n)` decisions) |
| `use_active_selection` (True) | fixed chunk size (no doubling / halving) and no activity-guided queue; bisection of failing chunks remains |
| `n_seeds_per_decision` (3) | replicates per decision (strict majority) |
| `adaptive_replication` (True) | split decisions are not extended beyond `n_seeds_per_decision` |
| `minimality_cleanup` (True) | no 1-minimality rounds after the group phase, no certificate and no certificate reserve |
| `member_essentiality` (True) | members are not silenced alone: `essential` is None, no replacement searches, no necessity constraint from members |
| `necessity_screen` (True) | no screen of the other active candidates (context members and masked gates are missed) |
| `screen_singles` (True) | no single silencing before the group screen (v1.0's screen, plus the second partition if on) |
| `second_partition` (True) | members of a passing group are cleared with it (v1.0) |
| `necessity_of_alternatives` (True) | the members of alternatives are not tested: a neuron essential only in an alternative is not a constraint |
| `max_alternatives` (4) | 0: no alternatives, the canonical set (with `Ess`) is the answer |
| `participation_check` (True) | candidates with non-participating members compete as if they participated (latent backups can win) |
| `fidelity_check` (True) | no fidelity filter before reliance and Occam |
| `reliance_tiebreak` (True) | no reliance key: Occam, then robustness |
| `robust_objective` (True) | no stress probes |
| `stress_only_for_ties` (True) | stress probes for every compared candidate (v1.1); the returned core is the same by construction |
| `decisive_margin` (2.0) | 1.0: no tie band — a paired comparison decides at the plain threshold and no lean blocks a later key (v1.1's rule) |
| `union_repair` (True) | no union of exchangeable copies (subset-of-draws functions keep one marginal copy) |
| `degeneracy_detection` (True) | no degeneracy flag; a distributed drive is reported as an ordinary (arbitrary) core |
| `joint_necessity` (True) | no jointly necessary groups |
| `simulate_edge_predictions` (True) | every edge prediction abstains (`None`) |
| `uncertainty_model` ("posterior") | "point": probability 1 for the core, 0 elsewhere |
| `use_cross_connectome` (True) | single-network run: no auxiliary simulations, no cross-connectome claims |
| `cross_fallback_discovery` (True) | if the verified transfer fails, no own discovery on the other network (no role alignment; never claims) |
| `joint_config` (see section 7) | joint.py's own switches, passed through (`require_essential_structure`, `require_reliance`, `claims_require_verified_link`, `claims_require_complete_image`, `adoption`, `consistency_prune`) |

## 7. Hyper-parameters (defaults; none tuned on hidden instances)

The default configuration below is FROZEN with the final code: `brainir_v1.py` sha256 `4bfcf816…`, `joint.py` `38609d27…`,
`correspondence.py` `11acef92…` (full hashes in section 12.11; `_brainir_v1_sha256.py` records the method file's). Every final number in section 12 comes from it unless a table says
otherwise. The only value fitted on data is the identity calibration (my dev pairs, section 12.8); everything else was set from first
principles or changed only as section 12.6 records.

| name | default | meaning, evidence |
|---|---|---|
| `n_seeds_per_decision`, `max_decision_seeds`, `max_seed_trials` | 3, 5, 10 | strict majority of 3, extended to 5 on a split (greedy_plus; robust pass 0.93); intact runs tried to collect working replicates |
| `validation_seeds`, `max_validation_seeds` | 3, 12 | sequential validation: at least 3, at most 12 intact-passing fresh replicates |
| `decisive` | 0.95 | posterior probability that makes a validation verdict or a certificate decision decisive |
| `decisive_margin` | 2.0 | a paired comparison decides only if its tail mass is below (1 − decisive) / 2 (P > 0.975); tail masses within a factor of two of 1 − decisive (P in 0.90–0.975) are equally conventional thresholds, so such a posterior is a tie after extension, and a later key may not overrule a reliance posterior in the band that leans the other way (section 2) |
| `decisive_stress` | 0.99 | stress probes are high-variance: only 4/4 against 0/4 decides (0.996 > 0.995 with the margin) |
| noise band | `√2 × median` between-draw readout change | not a free parameter: the intact network's own variability (section 2) |
| `occam_factor` | 0.5 | prior odds per extra member when only Occam separated two admissible sets (probabilities only) |
| participation | `max(0.05 Hz, 1 % of the median rate of the canonical mechanism)`, or a peak ≥ 10x that | relative to the network's own activity (review G finding 8); 0.05 Hz = the adversarial generator's "silent" level |
| `fidelity_seeds` | 4 | intact-passing reserved replicates of the final fidelity |
| `relevance_hops`, `relevance_damping` | 6, 0.6 | random-walk horizon; 6 hops reach the far end of a 5-neuron relay loop |
| `initial_chunk_fraction` | 0.25 | first group size (greedy_plus) |
| `necessity_screen_fraction` | 0.4 | call cap of the screen (v1.0: 0.3; the singles and the second partition need more) |
| `screen_singles_fraction`, `screen_min_singles`, `screen_singles_per_member` | 0.15, 4, 4 | most relevant active candidates silenced alone: 15 % of the pool, at least 4, at most 4 per canonical member (plus every flagged gate) |
| `max_alternatives`, `max_fillers_per_member`, `alternatives_budget_fraction` | 4, 2, 0.5 | enumeration caps |
| `stress_probes`, `stress_sd_factor`, `stress_noise_sd` | 4, 2.0, 0.2 | the tournament's robustness definitions |
| union repair | 3 rounds; extended to 24 replicates while 0.8 ≤ P ≤ 0.975 | section 4 |
| 1-minimality rounds, certificate passes | until one removes nothing, at most \|kept\| | section 4 (v1.1: at most 3 rounds) |
| certificate reserve | (validation_seeds + 1) x non-essential canonical members, at most 20 % of the budget | kept back from the screen and the enumeration (section 4) |
| degeneracy | ≥ 3 members, none essential; ≥ 50 % structurally equivalent, or ≥ 2 members all with one-for-one fillers | section 2 |
| `edge_prediction_members` | 8 | members (most relevant first) whose strongest edge is simulated |
| probability constants | `P_MAX` 0.99, `P_UNTESTED` 0.60, `P_CLEARED` 0.03, `P_SILENT` 0.01, `P_STRUCTURAL` 0.002, `P_LATENT` 0.01 | ceilings of neurons outside every candidate; the weight factor of a latent candidate |
| `size_error_points` | 3 | search-path points of the size–error curve |
| `aux_budget_fraction`, `aux_calls_per_member`, `aux_min_calls` | 0.25, 60, 30 | allowance of the cross-connectome step from the same pool; skipped below 30 |
| `cross_fallback_min_calls` | 60 | calls left in the allowance needed for v1's own discovery on the other network after a failed transfer |
| `joint_config` | `identity_calibration` fitted (section 12.8) | joint's verified-transfer and claim settings |
| `t_end` | None | the bundle's protocol for every simulation |
| (seed layout) | fixed | section 4, "Seeds" |
| `prior`, `prior_weight` | absent, 1.0 | optional `{position: p}`: adds `w·logit(p)` to the canonical order key; it never decides membership |

## 8. Complexity

With `n` candidates after restriction, a `k`-member mechanism and `a` alternatives: canonical elimination ≈ `k (log2(n/k) + 2)`
decisions of 2–3 calls (keep-only); essentiality of every member of every candidate ≈ `(k + a k)` pooled tests of 3–5 full-network
calls plus 3 fresh ones; screen ≈ `max(4, min(0.15 |K \ M|, 4k))` + flagged-gate singles of 2–3 calls, `|K \ M| / g*` group
decisions per partition and `2 log2 g*` per isolate (full network; capped at 40 % of the budget); each alternative one more
elimination (keep-only); selection: sequential validation (4–12 keep-only calls per candidate, the intact runs shared), reliance
2 full-network calls per pair and replicate (5, extended to at most 12 while undecided; with `c` candidates `c(c − 1)/2` pairs, most
silenced sets shared through the cache) and 4 stress calls per candidate of an equal-size pair left tied; certificate 3–15 keep-only
calls per non-essential member; final fidelity 8 calls;
curve 3 × 3; edge predictions ~4 calls per member (≤ 8 members). No-call parts: two BFS, six sparse mat-vecs and the statistics.
Memory: the simulator's trajectory. Wall time is dominated by full-network simulations on large graphs.

## 9. Known failure modes

1. **Exact structural symmetry.** Two mechanisms related by a graph automorphism (e.g. two identical E–I pairs) cannot be told apart by
   any permutation-invariant quantity; the canonical order then falls back to the node position, so the reported core is the same for
   every seed of one node order but can differ between node orders. The probabilities say so (the two mechanisms share the mass).
2. **Marginal mechanisms.** When a set passes on about half of the replicates, the sequential validation ends undecided after 12
   replicates and the result is flagged `undecided` with probabilities below 0.95 × the preference share; the core can still differ
   between seeds. Function carried by exchangeable copies on different draws is merged into a union only when the union is decisively
   better on the same replicates; with fewer than about 12 informative replicates it may stay one copy (subset-of-draws dev instances,
   section 12.2).
3. **Fidelity excludes compact but dynamically different mechanisms.** Rule (c) rejects a sufficient set whose keep-only dynamics differ
   from the intact network's beyond the noise band on paired replicates — even when the planted generator motif is that set. Measured
   case (my plain suite): the memory switch with hub distractors, where the planted single latch reproduces the intact readout less
   faithfully than two-hub sets (mismatch 0.19–0.20 against 0.12–0.13, paired confidence ≥ 0.99 in every run); v1.1 returns a hub pair
   in all 6 runs (4 count as structural successes because the suite audit lists that pair as an unplanted sufficient set, 2 as failures
   because it lists another one; v1.0 returned the latch by Occam). This is the rule doing what it says; whether the intact network
   "uses" the latch or the hubs is exactly what the paired dynamics measure, and the latch keeps a probability near 0.
4. **Reliance and fidelity are statistics of the readout.** They cannot separate candidates whose silencing or keep-only runs change the
   readout identically; then Occam, robustness and finally the canonical candidate decide, and the probabilities are shared. The choice
   among several admissible, equally sufficient 1-minimal sets is a heuristic without a success guarantee (review B finding B4); where
   it is not decisive, the result says so with tied candidates.
5. **Decisions at the edge are ties, and a tie keeps the canonical candidate.** A paired posterior in the tie band (0.90–0.975) is not a
   decision (review B finding B2), so a comparison whose evidence sits at the threshold's edge returns the canonical candidate with the
   probability shared, while a run whose replicates push the posterior beyond the band returns the other candidate. Across seeds, such an
   instance can therefore return different cores, each reported with the honest weights (measured case: one jittered redundant
   oscillator of my plain suite, whose fidelity comparison reaches 0.969 at the cap in one of six runs and 0.991–0.994 in the others,
   section 12.10). The same holds across settings of `decisive`: on the real MANC network the replacement of the canonical set rests
   on 5 against 0 failures (P = 0.984), decisive at 0.90 and 0.95 and inside the band at 0.975, where the canonical set is returned
   tied with the replacement (section 12.10).
6. **Participation is relative, not absolute.** A mechanism member firing below 1 % of the canonical mechanism's median rate (and never
   peaking above 10x that) counts as non-participating unless its silencing breaks the function; a latent backup with sustained weak
   activity above the threshold counts as participating and is then judged by fidelity and reliance.
7. **The screen is bounded.** Flagged gates and the most relevant candidates are silenced alone; the rest in two partitions. The gate
   flag is computed from the intact mean rates, the model's synaptic scales and its mean threshold: a gate whose released neuron acts
   on the mechanism only through a further silent relay, or whose effect shows in the dynamics but not in the mean input, is not
   flagged and relies on the second partition. A neuron masked in both of its groups, or beyond the 40 % call cap, keeps its
   sufficiency-based probability (`unscreened`).
8. **Degeneracy detection is a structural / causal heuristic.** It needs ≥ 3 non-essential members that are either structurally
   equivalent (identical presynaptic and postsynaptic partner sets, whatever the weights) to active neurons outside the core, or all
   replaceable one for one; a distributed drive whose relays differ in their partner sets and whose fillers were not searched is not
   flagged (then the core is reported with its ordinary, evidence-based probabilities).
9. **Non-monotone effects** inside a chunk can make the group phase isolate a neuron that is needed only in that context; the
   1-minimality rounds and the certificate remove it again at extra cost.
10. **Truth definitions differ at the margin.** v1 calls a neuron essential when more than half of the pooled intact-passing
   replicates fail (`σ < 1/2`); the adversarial generator's truth uses `σ ≤ 0.2`. Until 2026-09-24 its acceptable cores could also
   exclude neurons it listed as essential: on the identical-decoy trap on the negative-feedback controller (`identical_decoy /
   nfc_band`, 2 instances x 2 node orders in each of my adversarial sets) the gate and the latch that keep the decoy silent fail the
   generator's own silencing test (pass 0.00), v1 puts them in the core (4 members at P ≥ 0.96), and the old scorer counted every such
   run as confident-wrong — all of v1.1's confident-wrong runs on my sets. The coordinator has since changed the scorer's truth
   definition (every acceptable core contains every measured-essential node; `adversarial.normalize_truth_network`); under it these runs
   are correct and every adversarial number in section 12 is re-scored with it. The tournament's `success_intact` still reads the
   acceptable cores as exported, so it counts these 8 runs per set as failures while the adversarial scorer counts them as correct.
11. **Cross-connectome.** As in v1.0 (section 10): claims only from a verified, complete transfer; the identity calibration is an
    extrapolation on real data.
12. **Edge predictions** cover one edge per member (its strongest in-core edge), decided on 2–3 working replicates, and abstain beyond
    8 members or when the budget is exhausted. Where the function itself is marginal (subset-of-draws instances) the stated confidences
    (0.69–0.875) are too high (section 12.7).
13. **Cost on large graphs.** Wall time is dominated by full-network simulations (intact runs, essentiality, screen, reliance, edge
    predictions, the cross-connectome step); the method runs in one process (the clean-room sandbox forbids subprocesses). Every flagged
    gate is silenced alone, and a large background holds many of them: v1.1 needs about 2x v1.0's calls on my 3,000-neuron instances and
    18–26 minutes per real network (v1.0: 6–10), still well inside 1,000 calls (sections 12.4, 12.9).

## 10. Cross-connectome decision

**The step is kept, but only as a verified, budgeted, calibrated add-on that never changes the core.** Evidence for joint
discovery (held-out pair tournament `sel_pairs_b1000`, 26 pairs x 2 seeds, 1,000 + 1,000 calls): for the strong base methods
there is no success gain (greedy_plus 0.98 → 1.00, group_probe and cem_search 1.00 → 1.00; greedy_reference 0.71 → 0.96), only an
efficiency gain (about 40 % fewer total calls: greedy_plus 174 → 104, group_probe 246 → 143, cem_search 184 → 115), and transfer
alone solves only ~0.70 of the pairs. Review E showed that this gain comes from a synthetic design in which the motif wiring is
identical in both networks, that the claimed correspondence confidence was a structural-alignment score (identity claims were
made across different implementations and under a destroyed correspondence), that "verified" transfers could be unvalidated, and
that role-graph similarity 1.00 is what joint's objective maximises, not evidence. On the real bundle, greedy_plus's MaleCNS core
transferred to MANC in 3 / 3 runs with 2 destination calls, the reverse direction in 2 / 3 (REAL_TRANSFER_greedy_plus.md). The
core therefore stays single-network (identical with and without a partner network, as in the reliability sweeps whose variant
bundles hold one network), and the cross-connectome step only adds claims, with these rules (review E findings 1, 2, 3, 6, 8, 9):

* **Partner.** The first network of the bundle from ANOTHER dataset (`problem.other_dataset_networks()`, loaded with
  `problem.load_network`); two networks of the same dataset (the same animal) are never paired.
* **Budget.** One pool per run: the step runs after the core is final and only if its final fidelity on the reserved replicates
  (conditional keep-only pass fraction) is at least 1/2, from the calls left, with an allowance of min(left, 0.25 x declared budget,
  60 x (|core| + 2)), and is skipped below 30 calls. Its simulator is spawned from the primary
  one (`sim.spawn`), so `sim.total_calls()` never exceeds the declared budget; its calls and simulated seconds are reported in
  `diagnostics["auxiliary_budget"]`, and exhaustion ends the step without claims.
* **Verification.** joint's verified transfer (structural image from anchor fingerprints plus reproduced signed member edges, then
  top-1, then the union of the top-k images; keep-only probes; minimisation that keeps full-network-essential members;
  counterparts of the core's essential members). It counts as verified only if (i) its validation passes on at least half of at
  least two fresh replicates, (ii) the minimisation completed (an incomplete one is a superset, not a mechanism), (iii) every core
  member essential in the primary network has an essential counterpart in the image, and (iv) the other network's intact
  simulation relies on the image (a member is essential there, or silencing the whole image breaks the function). (iii) and (iv)
  were added after my pair experiments (section 12.8): keep-only sufficiency alone accepts sufficient sets the other network does
  not use — a hub that can drive the readout alone, a silent structural copy, or, on a pair whose second network implements
  another family, some sufficient set near the image.
* **Identity claims** (`diagnostics["cross_connectome"]`, turned into schema claims): only for a verified transfer, only for member
  pairs the transfer matched (a member and a candidate image of it that survived in the verified set) that the structural alignment
  also pairs in both directions, and only when the fingerprint evidence ranks the partner above the 'none' option in BOTH
  directions (the 'none' logit is the typical best-match z of the other network's tokenised interneurons). Confidence = calibrated
  identity probability sigmoid(a + b · logit(w_ab · w_ba) + c · e): w_ab, w_ba are the two softmax weights of the pair (top-5
  candidates plus 'none'), their product (dual softmax) is high only when both directions agree, and e counts the signed member
  edges the pair reproduces — edges can raise the confidence only of a pair the fingerprints already support. (a, b, c) were fitted
  on my own synthetic pairs and checked on held-out pairs (section 12.8). Roles play no part in identity.
* **Role alignment** (`diagnostics["role_alignment"]`): the roles and signed role graphs of the core and of the other network's
  mechanism (the verified image, or v1's own discovery of the other network — with the transported prior unless the image was
  rejected on causal grounds — when the transfer does not
  verify) — a separate, role-level output, never an identity claim.
* **joint.py** (which this composition now owns) implements the same rules for `discover_pair`: `verified_transfer` accepts only
  a validated, completely minimised image with the source's essential structure that the destination relies on;
  `result_from_transfer` sets no `predicted_function_preserved` without validation; identity claims (`PairResult.correspondence`)
  are made only between two cores linked by a verified transfer (independent, prior and transfer modes claim nothing) and only for
  matched pairs; in the alternating rounds a network keeps its own validated mechanism unless its OWN evidence prefers the
  carried-over one — its own mechanism fails validation, the carried-over set is a strict subset, or its intact network relies
  decisively more on the carried-over set (silencing the distinctive members, per member, every replicate agreeing, margin
  max(0.05, 0.25 x the larger reliance)); a set that drops a member it found essential is never adopted, and role-graph similarity
  or correspondence confidence (agreement with the other network) are no longer evidence. Every switch is recorded in
  `diagnostics["switches"]`. `correspondence.null_match_scores` draws its null from tokenised interneurons only. The coordinator's
  smoke test (a NULL pair on which joint mode replaced network b's correct mechanism and independent mode claimed two identities)
  is covered by these rules and by `test_joint.py::test_null_pair_keeps_each_network_own_mechanism_and_claims_no_identity`.

## 11. Integrity and budget rules

* Every simulation of the primary network goes through the `BudgetedSimulator` the method is given; the other network of a bundle
  is simulated only through `sim.spawn(other, max_calls=allowance, kind="auxiliary")`, whose calls count against the same budget
  (`sim.total_calls()`; if the library offers no `spawn`, the cross-connectome step is skipped and says so). The method never
  constructs a simulator, never assigns a simulator attribute, never imports `brainir.sim.*` or `scipy.integrate`, never exceeds
  `sim.remaining` (each phase reserves the calls later phases need; `BudgetExhausted` cannot escape).
* Weight-noise probes always carry an explicit noise seed; `cfg_override` only widens the four parameter sds; `t_end` is the
  bundle's.
* Parameter seeds: every seed the method queries is below 5,000 (section 4, "Seeds"; below 1,000 at seed 0, joint's seeds included)
  and never in 1000–1015; the tests check it for seeds 0, 3 (the block next to 1000–1015), 15 and 31 (the highest block).
* Edge interventions: the edge predictions use the library's `SimQuery.remove_edges` (one synapse removed, one call per replicate,
  counted like every other call); no other part of the method uses it.
* The method reads no file itself: it uses the public problem (matrix, counts, signs, sizes, stimulus, readout, criterion, model
  configuration) and, for the cross-connectome step, the first network of ANOTHER dataset offered by
  `problem.other_dataset_networks()`, loaded with `problem.load_network(name)` (which refuses a network of the same dataset); that
  network's files are added to `inputs_used`. It never reads instance names, manifests or any truth, and imports no truth-bearing
  module — `brainir.discovery.adversarial` included (the static test of `test_budget_integrity.py` checks method modules, joint.py and correspondence.py). No component was
  tuned on any hidden instance; the development used my own instances only (section 12).

## 12. Experiments

All commands run inside `C:\Dev\BrainIR_p2clean` with `uv run --no-sync` (at most 3 of my processes at a time on a shared machine;
wall times are inflated by other users' jobs). Development scripts (not deliverables) live in `data/synthetic/dev_v1/`; records in
`data/synthetic/dev_v1/results/<label>.jsonl`. Every number below is on my own instances with my own truth; nothing was tuned on a
hidden instance, and the coordinator's held-out and final adversarial suites never entered the clean room (their v1.0 aggregates in
section 0 are the coordinator's).

### 12.1 Suites and scoring

* **Plain generator suite** (`mech`, as in v1.0): `brainir.discovery.synthetic.default_specs()` with every background seed shifted by
  13,000,000, verified by simulation, two node orders: 47 small (n = 50–60), 8 medium (n = 500) and 3 large (n = 3,000) instances,
  all ten families, five criterion types.
* **Adversarial suites** built by me with the third-party generator (`data/synthetic/dev_v1/build_adv.py`, review G's traps: latent
  backup, masked gate, distributed drive, subset of draws, identical decoy, fragile vs robust — every variant at n = 60 and n = 150):
  `adv_dev` (seed0 91,000,000; 44 of 44 verified) for development and `adv_holdout` (seed0 92,000,000; 44 of 44 verified; its
  results were first looked at with the final design, and the only change after that is the crash fix of section 12.6). Two node
  orders each; a node-order variant also draws different per-neuron parameters, so the two orders are two different sets of draws.
* **Scoring**: the tournament's `run_one` (score seeds 5000–5003; `--no-robust` on the adversarial suites) with the causal metrics of
  reviews A and G — `success_intact` (a listed sufficient set whose members participate in the intact network and which contains every
  truly essential neuron), runs missing an essential neuron, latent backup returned, contested Brier (the neurons in question only) —
  and, on trap instances, the third-party scorer `score_adversarial` (its own score seeds 5500–5507): *correct* (an acceptable core,
  or a flagged distributed drive), *confident-wrong* (a wrong core with every member at P ≥ 0.85), the pooled contested Brier and a
  reliability diagram.

### 12.2 Adversarial suites: v1.2 and v1.1 against v1.0, greedy_plus and group_probe

Budget 1,000 calls, seed 0, both node orders (88 runs per method and suite); `--no-robust`. Records: `adv_v12_dev`, `adv_v12_hold`
(v1.2, final code), `adv_v11_dev`, `adv_v11_hold` (v1.1 `94ea1f8e`), `adv_v10_dev`, `adv_v10_holdout` (the reviewed v1.0 code
`9ca36c4d`, run by the dev harness `run_legacy.py` under another name), `adv_cmp_dev`, `adv_cmp_holdout` (greedy_plus and group_probe).
**Scorer.** On 2026-09-24 the coordinator changed the third-party scorer's truth definition: every acceptable core now contains every
measured-essential node (`adversarial.normalize_truth_network`; failure mode 10). Every number below uses the current scorer; the
records of the earlier runs are re-scored from their stored results (`data/synthetic/dev_v1/rescore_adv.py`, suffix `_rs`; the method
is not re-run, the simulation-based fields are re-simulated on the scorer's seeds). Under the old definition v1.1 scored 0.92 / 0.05
(dev) and 0.95 / 0.05 (held out) — the difference is exactly the 8 identical-decoy runs per set of failure mode 10.

| method (suite) | runs | correct | confident-wrong | latent backup returned | runs missing an essential | success_intact | contested Brier (pooled) | calls median / mean |
|---|---|---|---|---|---|---|---|---|
| v1.0 (coordinator's held-out suite, 66 instances; aggregates, old scorer) | — | 0.38 | 0.51 | 0.15 | 0.55 | 0.41 | — | — |
| greedy_plus (coordinator's held-out suite, old scorer) | — | 0.70 | 0.25 | 0.03 | 0.18 | 0.73 | — | — |
| group_probe (coordinator's held-out suite, old scorer) | — | 0.60 | 0.31 | 0.15 | 0.05 | 0.65 | — | — |
| **v1.2, my dev set** (44 instances x 2 orders) | 88 | **0.97** | **0.00** | **0.00** | 0.02 | 0.88 | 0.013 | 162 / 186 |
| **v1.2, my held-out set** (44 x 2) | 88 | **1.00** | **0.00** | **0.00** | 0.00 | 0.91 | 0.005 | 158 / 196 |
| v1.1, my dev set | 88 | 0.97 | 0.00 | 0.00 | 0.02 | 0.88 | 0.013 | 162 / 184 |
| v1.1, my held-out set (first looked at with v11f) | 88 | 1.00 | 0.00 | 0.00 | 0.00 | 0.91 | 0.005 | 158 / 198 |
| v1.0 (reviewed code `9ca36c4d`), my dev set | 88 | 0.42 | 0.49 | 0.17 | 0.57 | 0.42 | 0.230 | 124 / 143 |
| v1.0, my held-out set | 88 | 0.43 | 0.44 | 0.12 | 0.56 | 0.43 | 0.188 | 108 / 156 |
| greedy_plus, my dev set | 88 | 0.74 | 0.18 | 0.02 | 0.12 | 0.74 | 0.063 | 118 / 160 |
| greedy_plus, my held-out set | 88 | 0.75 | 0.17 | 0.02 | 0.14 | 0.75 | 0.062 | 125 / 163 |
| group_probe, my dev set | 88 | 0.70 | 0.18 | 0.08 | 0.00 | 0.70 | 0.102 | 144 / 153 |
| group_probe, my held-out set | 88 | 0.70 | 0.22 | 0.10 | 0.03 | 0.70 | 0.095 | 151 / 161 |

"Runs missing an essential" is over the runs whose truth has an essential neuron; "calls" are all calls charged to the budget;
`success_intact` is the tournament's (it still reads the acceptable cores as exported, so it counts the 8 identical-decoy runs per set
as failures, failure mode 10). The comparators and v1.0 ran with their frozen defaults on exactly the same instances, orders and seed.
v1.0 on my sets reproduces the coordinator's held-out aggregates (correct 0.38–0.43, confident-wrong 0.44–0.51, missing essentials
0.55–0.57, success_intact 0.41–0.43), and so does its calibration ([0, 0.05) → 0.23, [0.05, 0.3) → 0.78, [0.3, 0.6) → 0.58, [0.85, 1]
→ 0.81, pooled over my 176 runs, against 0.24 / 0.80 / 0.56 / 0.76): my sets measure the same failure modes. v1.2 returns v1.1's core in
175 of the 176 runs (the other is a jittered distributed drive, flagged degenerate and correct in both), with probabilities that differ
by at most 0.08.

Per trap, correct / confident-wrong (runs):

| trap | v1.2 dev | v1.2 held out | v1.0 dev | v1.0 held out | greedy_plus dev | greedy_plus held out | group_probe dev | group_probe held out |
|---|---|---|---|---|---|---|---|---|
| latent backup | 1.00 / 0.00 (20) | 1.00 / 0.00 (20) | 0.25 / 0.75 (20) | 0.45 / 0.55 (20) | 1.00 / 0.00 (20) | 1.00 / 0.00 (20) | 0.80 / 0.20 (20) | 0.65 / 0.35 (20) |
| masked gate | 1.00 / 0.00 (28) | 1.00 / 0.00 (28) | 0.32 / 0.68 (28) | 0.21 / 0.71 (28) | 0.86 / 0.14 (28) | 0.86 / 0.14 (28) | 1.00 / 0.00 (28) | 0.96 / 0.04 (28) |
| distributed drive | 1.00 / 0.00 (8) | 1.00 / 0.00 (8) | 0.00 / 0.25 (8) | 0.00 / 0.25 (8) | 0.00 / 0.25 (8) | 0.00 / 0.25 (8) | 0.00 / 0.12 (8) | 0.00 / 0.12 (8) |
| subset of draws | 0.62 / 0.00 (8) | 1.00 / 0.00 (8) | 0.00 / 0.75 (8) | 0.00 / 0.75 (8) | 0.00 / 0.88 (8) | 0.00 / 0.88 (8) | 0.12 / 0.62 (8) | 0.38 / 0.62 (8) |
| identical decoy | 1.00 / 0.00 (16) | 1.00 / 0.00 (16) | 1.00 / 0.00 (16) | 0.94 / 0.00 (16) | 0.81 / 0.19 (16) | 0.88 / 0.12 (16) | 0.81 / 0.19 (16) | 0.88 / 0.12 (16) |
| fragile vs robust | 1.00 / 0.00 (8) | 1.00 / 0.00 (8) | 0.88 / 0.12 (8) | 1.00 / 0.00 (8) | 1.00 / 0.00 (8) | 1.00 / 0.00 (8) | 0.50 / 0.38 (8) | 0.62 / 0.38 (8) |

**What the numbers say.**

* **v1 is never confidently wrong on my adversarial sets** (0 of 176 runs, v1.1 and v1.2); greedy_plus and group_probe are confidently
  wrong in 31 and 35 of their 176 runs, v1.0 in 82.
* **Latent backups are never returned** (0 of 176 runs; v1.0: 0.12–0.17 of the runs on my sets, 0.15 on the coordinator's),
  **masked gates are always found** (56 of 56; v1.0: 15), **distributed drives are always flagged** (16 of 16; neither v1.0 nor a
  comparator flags any), **fragile implementations never win** (16 of 16). Only one run of 176 misses a truly essential neuron (a
  subset-of-draws instance at n = 60, one node order, where the third exchangeable copy was not recovered).
* **Subset of draws** is the hardest trap: correct in 5 of 8 dev runs and 8 of 8 held-out runs. The 3 dev failures return one or two
  of the copies at probabilities that are not all ≥ 0.85 (the scorer's confidence level), so none is confidently wrong; greedy_plus and
  group_probe are confidently wrong there in 14 and 10 of their 16 runs.
* **Calibration** of the contested probabilities (v1.2, dev + held out, 176 runs, 1,145 neuron probabilities; bin: n, mean stated
  probability → observed frequency of membership): [0, 0.05): 452, 0.020 → 0.009; [0.05, 0.3): 2, 0.28 → 0.00; [0.3, 0.6): 16, 0.52 →
  0.63; [0.6, 0.85): 132, 0.78 → 0.69; [0.85, 1]: 543, 0.976 → 0.982; contested Brier 0.009 (v1.1: identical bins). v1.0 on the
  coordinator's held-out suite: p < 0.05 → 0.24, 0.05–0.30 → 0.80, 0.30–0.60 → 0.56, ≥ 0.85 → 0.76. On my sets (dev + held out):
  greedy_plus [0, 0.05): 364, 0.025 → 0.12 and [0.85, 1]: 578, 0.944 → 0.93; group_probe 366, 0.001 → 0.085 and 541, 0.973 → 0.89.
* **Cost.** v1.2 spends a median 158–162 calls per adversarial run (mean 186–196), against a median 120 (mean 161) for greedy_plus
  and 147 (157) for group_probe. Per run (dev, mean): alternatives 40.0, screen 25.4, elimination 23.2, essentiality 19.9 (+ 6.6 for the
  alternatives' members), fidelity and curve 16.2, validation 10.6, selection 10.5, edge predictions 9.5, union repair 7.9, certificate
  7.0, reliance 2.2, stress 1.1.

### 12.3 Component ablations on the adversarial dev suite (review G finding 7)

Each row switches one v1.1 component off (v1.1 final code `94ea1f8e` otherwise; `adv_dev`, main order, seed 0, 44 runs; records
`abl2_*`, re-scored with the current scorer as `abl2_*_rs`, section 12.2). v1.2 changes none of these components; its own switches
(`stress_only_for_ties`, `decisive_margin`) are exercised by the unit tests and, for the stress probes, on the dev suites (section 12.10).

| switched off | correct | confident-wrong | latent returned | runs missing an essential | contested Brier | calls median | latent backup (10) | masked gate (14) | distributed drive (4) | subset of draws (4) | identical decoy (8) | fragile vs robust (4) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| — (v1.1) | 1.00 | 0.00 | 0.00 | 0.00 | 0.004 | 160 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| `participation_check` | 0.95 | 0.00 | 0.05 | 0.00 | 0.033 | 169 | **0.80** | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| `fidelity_check` | 0.98 | 0.00 | 0.00 | 0.00 | 0.011 | 162 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | **0.75** |
| `reliance_tiebreak` | 1.00 | 0.00 | 0.00 | 0.00 | 0.004 | 160 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| `screen_singles` | 0.98 | 0.02 | 0.00 | 0.04 | 0.008 | 148 | 1.00 | **0.93** | 1.00 | 1.00 | 1.00 | 1.00 |
| `second_partition` | 1.00 | 0.00 | 0.00 | 0.00 | 0.004 | 154 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| `screen_singles` + `second_partition` (v1.0's screen) | **0.77** | **0.23** | 0.00 | **0.36** | 0.038 | 140 | 1.00 | **0.29** | 1.00 | 1.00 | 1.00 | 1.00 |
| `necessity_of_alternatives` | 1.00 | 0.00 | 0.00 | 0.00 | 0.004 | 150 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| `union_repair` | 0.91 | 0.00 | 0.00 | 0.04 | 0.033 | 155 | 1.00 | 1.00 | 1.00 | **0.00** | 1.00 | 1.00 |
| `degeneracy_detection` | 0.91 | 0.05 | 0.00 | 0.00 | 0.023 | 160 | 1.00 | 1.00 | **0.00** | 1.00 | 1.00 | 1.00 |

Every component aimed at a trap is needed for it on these instances: without the participation check a latent backup is returned in 2
of the 10 latent-backup runs and the contested Brier score rises from 0.004 to 0.033; without the fidelity filter a fragile implementation wins
in 1 of 4 runs; without the union repair no subset-of-draws run is correct; without degeneracy detection no distributed drive is
flagged and 2 of the 4 become confident-wrong; with neither masking protection of the screen (v1.0's screen) the masked gate is missed
in 10 of 14 runs, 36 % of the runs miss an essential neuron and 23 % are confident-wrong. The two masking protections back each other
up: the single silencing alone finds every gate, the second partition alone 13 of 14. Three components change nothing on these runs:
the second partition when the singles are on, the necessity tests of the alternatives' members, and reliance (on these traps
participation and fidelity decide before reliance is consulted). They stay, at 0–10 calls per run (median): the second partition covers masking
that the flagged-inhibitor rule does not (an excitatory competitor silenced together with what it drives; review A's winner-take-all
case), the alternatives' necessity is review A's fix 1 (a neuron essential only in an alternative's context must constrain every
candidate), and reliance at every size is review A's fix 3.

### 12.4 Plain generator suite: v1.2 and v1.1 against v1.0

Budget 1,000 calls, both node orders, seeds 0–2 (small, medium) or 0–1 (large); scorer `tournament.run_one` with independent score
seeds 5000–5003 and the robust / weight-noise / minimality / causal-minimality checks. v1.0 = the frozen v1.0 records (`final5_*`,
code `3a07cf80`), re-scored with the harness's causal metrics (`data/synthetic/dev_v1/rescore_v10.py`: the stored results against the
same truth, participation measured on score seeds 5000–5003); v1.1 = `v11_small`, `v11_medium`, `v11_large` (code `94ea1f8e`); v1.2 =
`v12_small`, `v12_medium`, `v12_large` (final code; section 12.10 compares it run by run with v1.1).

| suite | version | runs | structural success | planted | success_intact | runs missing an essential | contested Brier | causal functional | identity Jaccard / identical | calls median / mean | role acc | essential acc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| small (n = 50–60) | v1.0 | 282 | 1.00 | 1.00 | 1.00 | 0.00 | 0.031 | 1.00 | 0.99 / 0.98 | 76 / 90 | 0.88 | 1.00 |
| small | v1.1 | 282 | 0.99 | 0.98 | 0.99 | 0.00 | 0.028 | 1.00 | 0.98 / 0.96 | 90 / 118 | 0.90 | 1.00 |
| small | **v1.2** | 282 | 0.99 | 0.98 | 0.99 | 0.00 | 0.030 | 1.00 | 0.98 / 0.96 | 90 / 117 | 0.90 | 1.00 |
| medium (n = 500) | v1.0 | 48 | 1.00 | 0.88 | 1.00 | 0.00 | 0.020 | 1.00 | 1.00 / 1.00 | 130 / 144 | 0.86 | 1.00 |
| medium | v1.1 | 48 | 1.00 | 1.00 | 1.00 | 0.00 | 0.012 | 1.00 | 1.00 / 1.00 | 215 / 230 | 0.88 | 1.00 |
| medium | **v1.2** | 48 | 1.00 | 1.00 | 1.00 | 0.00 | 0.012 | 1.00 | 1.00 / 1.00 | 215 / 230 | 0.88 | 1.00 |
| large (n = 3,000) | v1.0 | 12 | 1.00 | 1.00 | 1.00 | 0.00 | 0.009 | 1.00 | 1.00 / 1.00 | 138 / 197 | 1.00 | 0.96 |
| large | v1.1 | 12 | 1.00 | 1.00 | 1.00 | 0.00 | 0.011 | 1.00 | 1.00 / 1.00 | 285 / 337 | 1.00 | 0.96 |
| large | **v1.2** | 12 | 1.00 | 1.00 | 1.00 | 0.00 | 0.011 | 1.00 | 1.00 / 1.00 | 292 / 338 | 1.00 | 0.96 |

v1.2 returns v1.1's core in 276 of the 282 small, 48 of 48 medium and 12 of 12 large runs (the six differences are described in
section 12.10), at the same cost; everything below compares v1.1 with v1.0.

By criterion type (small suite, v1.1; calls median, v1.0 in brackets): rhythm 162 runs, structural 1.00, identity 0.98 / 0.96, calls 126 (106);
activity band 42, 1.00, 1.00 / 1.00, 76 (63); persistence 36, 0.94, 0.96 / 0.83, 66 (50); selectivity 30, 1.00, 1.00 / 1.00,
75 (64); ramp 12, 1.00, 1.00 / 1.00, 46 (36).

**Where v1.1 differs from v1.0 on the plain families.** (i) *Success*: every structural non-success of the small suite is the memory
switch with hub distractors (failure mode 3): the fidelity rule excludes the planted single latch in all 6 runs and returns a hub pair
(2 runs count as failures, 4 as successes through the audit's unplanted set). Nothing else changed: every other instance gives the
planted (or an audited) mechanism in every run, no run misses an essential neuron, every core participates. (ii) *Consistency*: 45 of
47 small instances give the identical core in all 6 runs (v1.0: 46 of 47): the exactly automorphic redundant oscillator differs
between node orders as in v1.0 (failure mode 1), and in the memory switch one of the three hub pairs wins in 1 of 6 runs (its reliance
advantage, 0.009 per member, sits at the edge of that network's noise band). The sequential extension of undecided paired keys (v11f)
removed the two other seed-dependent choices of v11c–v11e (a jittered redundant oscillator and a jittered two-implementations
instance). The medium suite gains planted success (0.88 → 1.00: in the feed-forward driver with hubs v1.0 returned a single hub
that can drive the readout alone in all 6 runs, v1.1 the planted 3-neuron chain in all 6) and keeps identical cores in every run. (iii) *Calls*: on the small suite median
76 → 90 (+18 %), mean 90 → 118 (+31 %). The search costs the same (elimination 16.4 and alternatives 18.2 calls per run in both
versions); the difference is the evidence the reviews asked for — simulated edge predictions 9.2 calls per run (new), the
masking-robust screen 14.9 (v1.0: 6.4), the final fidelity on reserved
replicates together with the curve 14.8 (8.0), sequential validation on intact-passing replicates 8.1 (about 3), reliance at every size
with its sequential extension 5.1 (2.0), the necessity of the alternatives' members 2.7 (new) — while the lazy paired certificate (3.2
vs 7.2), the members' pooled tests (15.0 vs 18.7) and the selection (5.8 vs 6.8) are cheaper. On the medium suite (n = 500) the
median goes from 130 to 215 calls (+65 %): the screen costs 71 calls per run there (v1.0: 6), mostly the single silencing of flagged
gates — in a 500-neuron background 15–30 active inhibitory neurons hold down a silent neuron that projects onto the readout — while
every other phase costs what it did in v1.0 (alternatives 46.9 and elimination 34.9 in both versions) plus the new evidence (fidelity
16.4, edges 9.5, validation 8.2). On the large suite (n = 3,000) the median goes from 138 to 285 calls
(+107 %) and the median wall time from 77 s to 282 s, again mostly the screen (117 calls per run): in a 3,000-neuron background with 40
readout neurons many active inhibitory neurons hold down a silent neuron that projects onto the readout, and each is silenced alone.
Ranking these gates by how strongly their release would drive the mechanism, and silencing only the strongest, is the obvious next
economy; it is not in v1.1. Every one of these components has its switch (section 6).

### 12.5 Low budgets

Small + medium suites, both node orders, seed 0 (`v11_b50`, `v11_b100`; v1.0: `final5_b50`, `final5_b100`; v1.2: `v12_b50`,
`v12_b100`). No run exceeded its budget.

| budget | version | runs | structural | planted | success_intact | causal functional | identity Jaccard / identical (55 instances) | calls median / mean |
|---|---|---|---|---|---|---|---|---|
| 50 | v1.0 | 110 | 0.99 | 0.96 | — | 0.95 | 0.97 / 0.95 | 50 / 49 |
| 50 | v1.1 | 110 | 0.99 | 0.96 | 0.99 | 0.95 | 0.97 / 0.95 | 50 / 50 |
| 50 | v1.2 | 110 | 0.99 | 0.96 | 0.99 | 0.95 | 0.97 / 0.95 | 50 / 50 |
| 100 | v1.0 | 110 | 0.99 | 0.96 | — | 1.00 | 0.98 / 0.98 | 64 / 69 |
| 100 | v1.1 | 110 | 0.99 | 0.96 | 0.99 | 1.00 | 0.98 / 0.98 | 97 / 85 |
| 100 | v1.2 | 110 | 0.99 | 0.96 | 0.99 | 1.00 | 0.98 / 0.98 | 97 / 85 |

At 50 and 100 calls v1.1 returns v1.0's quality exactly: the search comes first and is unchanged, and every finishing phase runs only
with the calls it can afford (the reserves of section 4); at 100 calls v1.1 spends more of the budget on the evidence phases (median 97
against 64). The single structural failure at both budgets is, for both versions, the memory switch with hub distractors in one node
order (a hub pair; at 1,000 calls v1.0 finds the planted latch there and v1.1 excludes it by fidelity, failure mode 3). At 50 calls
the medium suite drops to causal functional 0.81 in both versions (the minimality rounds do not fit).

### 12.6 How the v1.1 development went

Every v1.1 version was run on the same 88 adversarial dev runs (`adv_dev`, both orders, seed 0) and, from v11c on, on the same 282
plain small-suite runs (47 instances x 2 orders x 3 seeds); the held-out adversarial set (`adv_holdout`) was built after v11e and
first looked at with v11f.

| version | change | adversarial dev: correct / confident-wrong / success_intact / calls median | plain small: success / planted / identity Jaccard / identical / calls median / mean |
|---|---|---|---|
| v1.0 (`9ca36c4d`) | — | 0.38 / 0.49 / 0.42 / 124 (run afterwards; coordinator's held-out suite: 0.38 / 0.51 / 0.41) | 1.00 / 1.00 / 0.99 / 0.98 / 76 / 90 |
| v11a | admissibility-first selection (validation, participation, `Ess` in every candidate, fidelity, reliance at every size, paired tests), masking-robust screen, evidence probabilities, sequential validation, simulated edges, reserved fidelity seeds, roles and claims | 0.81 / 0.12 / 0.85 / 160 (distributed drive never flagged, fragile vs robust 0.88) | — |
| v11b, v11c | fixes found on the dev instances over these two versions: degeneracy judged on the canonical set and by structural signatures; probabilities as validity x preference share (the old normalisation inflated undecided ties); union repair on the replicates where the winner fails; the paired sequential certificate (the majority certificate removed exchangeable latches; union members exempt); paired keys on equal numbers of replicates; fidelity split into sufficiency discordance and dynamics on the replicates where both pass (a failing replicate had inflated the dynamics variance and let a fragile relay through) | v11b 0.92 / 0.05 / 0.88 / 166; v11c 0.92 / 0.05 / 0.88 / 180 | v11c: 0.996 / 0.979 / 0.96 / 0.91 / 105 / 129 |
| v11d | noise band (the intact network's between-draw readout variability) on the paired dynamics and reliance keys: tiny but consistent differences had flipped redundant pairs between seeds | 0.92 / 0.05 / 0.88 / 176 | 0.993 / 0.979 / 0.97 / 0.91 / 105 / 129 |
| v11e | band √2 x that variability (a difference of two per-replicate statistics); lazy certificate (a member is kept as soon as it is decisively needed) | 0.92 / 0.05 / 0.88 / 168 | 0.993 / 0.979 / 0.97 / 0.91 / 89 / 116 |
| v11f (`665ac1b0`) | band estimated from 12 intact replicates; the paired fidelity and reliance keys extended sequentially (4 more replicates at a time, up to 12) while neither decisive for nor against | 0.92 / 0.05 / 0.88 / 168 | 0.993 / 0.979 / 0.98 / 0.96 / 89 / 118 |
| v11g (`e75afc76`) | two robustness fixes found on the first held-out run: the noise band read an add-back seed from the wrong table (a `KeyError` in 1 of 88 held-out runs), and an unexpected failure inside the selection now falls back to the canonical candidate instead of losing the run | identical to v11f in all 88 runs (cores, probabilities, calls); held-out set 0.95 / 0.05 / 0.91 / 172 | identical to v11f in all 282 runs; medium suite (partial run): 2–4x v1.0's calls, the screen alone 280–340 calls per run |
| **final** (`94ea1f8e`) | leaner gate flagging, found on the medium suite: in a 500-neuron background almost every active inhibitory neuron touches some silent neuron with a path to the readout, so the old rule flagged 50–60 gates per run; a gate is now flagged only if it holds down a silent neuron that acts directly on the mechanism or the readout (its release would lift that neuron's mean input above threshold), and the relevance singles are capped at 4 per canonical member | 0.92 / 0.05 / 0.88 / 162 (the same cores and probabilities as v11f in all 88 runs, fewer calls); held-out set 0.95 / 0.05 / 0.91 / 158 | 0.993 / 0.979 / 0.98 / 0.96 / 90 / 118 (the same cores and probabilities as v11f in all 282 runs); medium suite 215 / 230 calls |

Also changed during the development: validation runs keep-only only on replicates where the intact network passes (the intact runs
are shared by every candidate, the pooled necessity tests and the certificate), and the winner is validated on the full cap of 12
only when the intact network itself fails on some draw (9 of 282 plain runs); the screen's relevance singles were reduced to
`max(4, 15 %)` of the pool during v11a–c and capped at 4 per canonical member in the final version. Two cases were left as they are and are reported instead (section 9): the planted
latch of one memory-switch instance, which the fidelity rule excludes, and the identical-decoy trap on the negative-feedback
controller, where the generator's acceptable core excluded two neurons its own measurement finds essential (the coordinator has since
changed the scorer's truth definition, failure mode 10).

### 12.7 Intervention predictions checked on fresh seeds

`data/synthetic/dev_v1/edge_check11.py` re-simulates every recorded prediction outside the method on 8 fresh seeds (7001–7008), counting
only the seeds on which the intact network passes (the method's own semantics), with the edge zeroed in a copy of the weight matrix
(intact network and keep-only of the core) or the member silenced. Main node order, seed 0, v1.1 (`94ea1f8e`); v1.2's records
(`v12_small`, `adv_v12_dev`, final code) give exactly the same counts in every cell:

| population | edge removal, keep-only core | edge removal, intact network | silencing alone | abstained | stated confidence ≥ 0.8: observed |
|---|---|---|---|---|---|
| plain small suite (47 runs) | 108 / 108 (breaks 103 / 103, preserved 5 / 5) | 106 / 108 (79 / 81, 27 / 27) | 116 / 117 | 0 | 214 / 216 (0.99) |
| adversarial dev set (44 runs) | 97 / 105 (81 / 85, 16 / 20) | 93 / 105 (74 / 82, 19 / 23) | 170 / 179 | 0 | 177 / 191 (0.93); [0.6, 0.8): 13 / 19 |

The wrong plain predictions are two edges of one delayed-oscillator instance with a backup copy, whose removal fails on 2 of 2 working
replicates (stated confidence 0.875) but passes on 5 of 8 fresh ones: a marginal effect. On the adversarial set 18 of the 20 wrong edge
predictions are on subset-of-draws instances, where the function itself exists on only part of the draws and 2–3 working replicates
cannot settle an edge's effect (fresh pass fractions 0.25–1.00), the other 2 on one fragile-vs-robust instance (fresh pass 0.75); the
stated confidences there (0.69–0.875) are too high, which is the price of deciding on the working replicates only. For comparison, v1.0's structural rule was wrong
on 34 of 126 predictions of review A's generator runs and on 8 of 48 of review G's (all "preserved" at 0.6, on textbook edges such as an
E–I pair's self-excitation).

### 12.8 Cross-connectome pairs

The cross-connectome step is unchanged in v1.1 (`joint.py` `38609d27…`, `correspondence.py` `11acef92…`); only the core it carries
over comes from the v1.1 selection, and the step now starts only if the core's conditional fidelity on the reserved seeds is at least
1/2. Pairs (v1.0 development, `data/synthetic/dev_v1/build_pairs.py`): the harder review-E design of
`synthetic_pairs.hard_pair_specs()` (blank hemilineage, weaker and noisier anchors, homologous backgrounds, jittered and rewired motif
wiring in b, structural decoys with sign-consistent anchor decoys, NULL pairs whose b implements another family, implementation
shifts) plus the easier design of `default_pair_specs()`, every seed shifted by 4,500,000 (dev), 4,600,000 (held out) or 4,700,000
(large): 50 dev pairs (26 plain, 5 decoy, 5 structural decoy, 8 null, 6 shift) and 52 held-out pairs (26 / 6 / 6 / 8 / 6). Truth:
`pair_tournament.identity_truth`; on a null pair every identity claim is false, under a shift only the retained alternative's members
correspond.

**Identity calibration (v1.0, unchanged).** The raw dual-softmax probability w_ab·w_ba is badly under-confident for claims (Brier
0.58–0.61; mean 0.27 while the claims were ~99 % correct). (a, b, c) of sigmoid(a + b·logit(w_ab·w_ba) + c·edges) were fitted by
penalised logistic regression (ridge 0.5·|θ − (0, 1, 0)|², b ≥ 0 and c ≥ 0) on the 90 claimable member pairs of the DEV pairs (v1.0's
claims plus joint.py's claims with greedy_plus in joint mode and with destroyed cues, 89 correct), giving **a = 1.2988, b = 0.2166,
c = 1.8127** (a claim with no reproduced member edge and w_ab·w_ba = 0.3 gets 0.75, one edge 0.95), and checked on the held-out pairs
without refitting (v1.0: 35 claims, 35 correct, Brier 0.0015; joint.py 45 of 45).

**v1.1 on the pairs** (network a, 1,000 calls, seed 0; records `pairs_dev_v11`, `pairs_holdout_v11`):

| pairs | version | runs | success on network a | verified transfers | identity claims | correct | false on null / shift / structural decoy | Brier (claims) | mean confidence | total calls median / mean |
|---|---|---|---|---|---|---|---|---|---|---|
| dev | v1.0 (`pairs_dev_v4`; Brier and confidence with the final calibration, as documented for v1.0) | 50 | 0.96 | 25 | 37 | 37 | 0 / 0 / 0 | 0.0012 | 0.976 | 137 / 156 |
| dev | v1.1 | 50 | 1.00 | 25 | 37 | 37 | 0 / 0 / 0 | 0.0012 | 0.976 | 181 / 201 |
| held out | v1.0 (`pairs_holdout_v4`; idem) | 52 | 0.96 | 27 | 35 | 35 | 0 / 0 / 0 | 0.0015 | 0.970 | 145 / 161 |
| held out | v1.1 | 52 | 0.98 | 26 | 34 | 34 | 0 / 0 / 0 | 0.0014 | 0.971 | 191 / 215 |

v1.1's cores on the pairs' networks a are at least as good as v1.0's (success 1.00 / 0.98 against 0.96 / 0.96), and every one of its
71 identity claims is correct: none on a null pair, none across an implementation shift, none on a structural decoy. The claims come
from 25 + 26 verified transfers in 102 runs (v1.0: 25 + 27); the calls include the cross-connectome step (same pool).

The joint-discovery experiments of v1.0 (greedy_plus in joint mode, the null-pair smoke test of the coordinator, the large pairs) do
not involve v1's selection and are unchanged: joint mode solved both networks of every dev pair (50 / 50) and of 50 of 52 held-out
pairs (the 2 failures are base-method failures in every mode) with 18 % (dev) and 10 % (held out) fewer mean calls than independent
discovery, made 98 identity claims of which one was false (a null pair with destroyed cues, confidence 0.92), and no longer
loses a network on null pairs.

### 12.9 Real bundle (clean room, oracle-free)

**Version 1.2 (final code) returns v1.1's answer on both networks.** At the default configuration it returns the same core, essential
claims, alternatives, role labels and edge predictions (the latter with the same confidences) as the v1.1 runs tabulated below,
so the fresh-seed evaluations of this section hold for it. The MaleCNS probabilities differ by less than 0.0001; on MANC 1126 and 1220
go from 0.948 to 0.977 and 3310 from 0.039 to 0.013, because the replacement now rests on failure counts (5 against 0, P = 0.984) instead of a t posterior at the threshold (0.954;
review B finding B2). Calls: MANC 334 / 518 (primary / total), MaleCNS 348 / 365. The runs at `decisive` 0.90 and 0.975 are in section
12.10. The table is the v1.1 record, with its MANC selection entry corrected (review B finding B1: v1.1's reliance test ran over 12
replicates, not 5).

The v1.1 runs (`real/v11_*`, code `94ea1f8e`) were run exactly as the method is locked, as for v1.0:

```
uv run --no-sync python benchmarks/dng100/cleanroom/run_method.py --method scripts/cleanroom_entry/brainir_discovery_entry.py \
    --bundle benchmarks/dng100/public_blind --out <dir> --network <network> --seed 0 --method-args "--method brainir_v1 --budget 1000"
```

(plus `--result-json` for the diagnostics; `data/synthetic/dev_v1/real_run.sh`), then `real_eval.py` (fresh seeds 5000–5007: keep-only
fidelity nominal / sd x2 / weight noise 0.2, single-member removal, single silencing of every member) and `real_edge_check.py` (the
edge predictions on fresh seeds 7001–7008, the edge zeroed in a copy of the matrix). No answer is involved. Two of my processes ran in
parallel.

| | `manc_v1.2.1` | `male-cns_v1.0` |
|---|---|---|
| restriction (structurally excluded / silent in intact / candidates) | 1,066 / 3,306 / 87 | 1,318 / 2,739 / 121 |
| core (positions) | [1126, 1220, 2825, 2973] — v1.0's core | [653, 1052, 2152] — v1.0's core |
| essential (pooled test, every neuron tested) | 2825, 2973 (0 of 6 pass); not 1220 (4 of 8 pass), 1126, 3310 (6 of 6) | 653, 1052 (0 of 6); not 2152, 2948, 2779, 3262, 3682, 4196 (6 of 6) |
| inclusion probability | 2825, 2973: 0.99; 1126, 1220: 0.95; 3310: 0.04 | 653, 1052: 0.99; 2152: 0.47 and 2948: 0.42 (tied); members of a 6-member replacement: 0.01 |
| selection | canonical [2825, 2973, 3310] replaced by [1126, 1220, 2825, 2973]: the intact network relies on {1126, 1220} 0.41 per member against 0.03 on {3310}, by a paired t test over 12 replicates (5, extended twice by 4 while undecided) beyond the noise band 0.21, confidence 0.954 — at the threshold, on a bimodal statistic: silencing {1126, 1220} breaks the function in 5 of the 12 replicates (0.74–0.82 per member) and changes the readout by 0.12–0.21 per member in the other 7. v1.2: failures 5 against 0 (P = 0.984), the readout part inside the band; decisive at 0.90 and 0.95, a tie at 0.975 (section 12.10). Both validated 12 of 12 | canonical kept; [653, 1052, 2948] tied: reliance 0.27 against 0.08 per member differs by less than the noise band (0.22), and silencing {2152, 2948} together passes 3 of 3 (neither is needed); a 6-member replacement ranked below by reliance (0.975) |
| screen | pool 84: 27 single silencings (23 flagged gates), two partitions; no context member | pool 118: 27 single silencings (20 flagged gates); none |
| calls by phase (primary) | screen 90, alternatives 84, elimination 40, selection 28, reliance 26, essentiality 18 + 4, edges 16, fidelity 14, minimality 9, validation 8 | alternatives 98, screen 66, elimination 42, reliance 36, selection 13, essentiality 18 + 22, fidelity 17, edges 12, minimality 8, validation 8 |
| cross-connectome (same pool) | transfer to MaleCNS failed at the probes (6 calls); v1 on MaleCNS with the transported prior: [653, 1052, 2152] (178 calls); role alignment only, no claim | transfer to MANC verified in 17 calls: image [2825, 2973, 3310]; 1 claim 653 ↔ MANC 2825 (confidence 0.9997) |
| calls primary / total, CPU s, wall (method) | 342 / 526, 962 s, 1,550 s (v1.0: 226 / 366, 355 s, 571 s) | 352 / 369, 1,041 s, 1,084 s (v1.0: 232 / 249, 339 s, 366 s) |
| keep-only fidelity on fresh seeds 5000–5007: nominal / sd x2 / weight noise 0.2 | 1.00 / 0.625 / 0.50 (as v1.0) | 0.875 / 0.75 / 0.50 (as v1.0) |
| single silencing on 8 fresh seeds | 1126 1.00, 1220 0.875, 2825 0.00, 2973 0.00: every claim holds | 653 0.00, 1052 0.00, 2152 1.00: every claim holds |
| leave-one-out on fresh seeds | every member necessary (0.00) | every member necessary (0.00) |
| edge predictions on fresh seeds 7001–7008 | 7 of 8 correct: 1126→1220 and 1220→1126 preserved / breaks in the core (fresh 1.00 / 0.00), 2973→2825 breaks / breaks (0.00 / 0.00); 2825→1220 breaks in the core (0.00) but in the intact network it failed on 2 of 2 working replicates and passes on 7 of 8 fresh ones (stated confidence 0.875: wrong) | 6 of 6 correct: 653→2152 preserved / breaks in the core (fresh 1.00 / 0.00), 1052→653 breaks / breaks (0.00 / 0.00), 2152→1052 preserved / breaks (1.00 / 0.00) |

Both cores are v1.0's, and so are the fresh-seed fidelities and the identity claim; what changed is the evidence behind them. The
edge predictions, which review A found wrong in 9 of 14 conditions on these networks (v1.0's structural rule), are now right in 13 of
14; the wrong one rests on 2 working replicates. On MANC
the replacement of the canonical set is now a paired reliance decision with its confidence (v1.0: a fixed margin), and the canonical
set keeps 0.04 instead of 0.15. On MaleCNS the tie is the case review A finding 1 cited (reliance 0.27 against 0.06 per member, every
replicate agreeing, reported at 0.45 each because v1.0 never compared reliance at equal size): v1.1 does compare it, but the
difference lies inside the network's own between-draw readout variability, and silencing both together does not break the function —
the intact network needs neither — so the two share the mass. Essential claims are now made for every neuron tested (13 claims, all
consistent with the fresh silencing where re-measured). The cost is 1.5x v1.0's primary calls and 3x its wall time, mostly the screen
(27 single silencings of the full 4,500-neuron network on each) and the extended reliance and validation comparisons.

### 12.10 Version 1.2 against version 1.1 (review B)

Final code (`brainir_v1.py` `4bfcf816…`); the v1.1 records are those of sections 12.2–12.9 (adversarial ones re-scored with the current
scorer). Budget 1,000 calls unless stated; the plain suites with score seeds 5000–5003, the adversarial ones `--no-robust`.

**Same answers where the evidence is clear.**

| suite | runs | identical core to v1.1 | what changed | v1.2 success / success_intact / identical cores / calls median (mean) | v1.1 |
|---|---|---|---|---|---|
| adversarial dev | 88 | 88 | — | correct 0.97, confident-wrong 0.00 / 0.88 / — / 162 (186) | 0.97, 0.00 / 0.88 / — / 162 (184) |
| adversarial held out | 88 | 87 | a jittered distributed drive: another arbitrary subset of the relays (flagged degenerate in both, correct in both) | 1.00, 0.00 / 0.91 / — / 158 (196) | 1.00, 0.00 / 0.91 / — / 158 (198) |
| plain small (n = 50–60) | 282 | 276 | memory switch with hubs (5 runs) and a jittered redundant oscillator (1 run), next paragraphs | 0.989 / 0.989 / 45 of 47 / 90 (117) | 0.993 / 0.993 / 45 of 47 / 90 (118) |
| plain medium (n = 500) | 48 | 48 | — | 1.00 / 1.00 / 8 of 8 / 215 (230) | the same |
| plain large (n = 3,000) | 12 | 12 | — | 1.00 / 1.00 / 3 of 3 / 292 (338) | 1.00 / 1.00 / 3 of 3 / 285 (337) |
| low budget 50 / 100 (small + medium) | 110 / 110 | 110 / 110 | — | 0.99 / 0.99 / 52 and 54 of 55 / 50 (50) and 97 (85) | the same |
| cross-connectome pairs, dev / held out (network a) | 50 / 52 | 50 / 52 | — | success 1.00 / 0.98; 37 + 34 identity claims, all correct (none on a null pair, a shift or a structural decoy) | the same claims |

**Where v1.2 answers differently on the plain suite.**
- *Memory switch with hub distractors* (`memory_switch__n60__hub_distractor+misleading_centrality__s13000025`). The planted latch is
  excluded by fidelity in every run of both versions (failure mode 3); three sufficient hub pairs remain. v1.1 compared them on a
  statistic whose distinctive members depended on all three candidates and returned one of two hub pairs depending on the run
  (canonical [17, 34] in 5 runs, [32, 34] in 1). v1.2 compares each pair on its own distinctive members — a single hub against a single
  hub — and the readout change per member decides beyond the noise band in every run (P ≥ 0.9998): the same hub pair (canonical
  [32, 34]) in all 6 runs of both node orders. The suite audit lists that pair as an unplanted sufficient set in the main node order only
  (the audit is not exhaustive), so the scorer counts 3 successes instead of v1.1's 4; the returned pair is sufficient and participates
  in all 6 runs.
- *Jittered redundant oscillator* (`redundant_oscillator__n60__weight_jitter+unknown_signs__s13000011`, main order, seed 0). The fidelity
  comparison between the two planted copies reaches 0.969 at the 12-replicate cap: inside the tie band, so the copies tie and the
  canonical copy is kept (probabilities 0.50 and 0.44); in the other five runs it reaches 0.991–0.994 and excludes the canonical copy.
  Both copies are planted mechanisms (success in all 6 runs); the instance returns the other copy in one of six runs — failure mode 5,
  the price of not deciding at the threshold's edge. The v1.1 records returned the non-canonical copy in all 6 runs.

**B2 on the real bundle: `decisive` 0.90, 0.95 (default) and 0.975.** Public blind bundle, seed 0, 1,000 calls, clean-room runner
(`data/synthetic/dev_v1/real_run2.sh`), otherwise identical:

| network | `decisive` (tie band) | returned core | how the candidates were separated | probabilities of the distinctive members | calls primary / total |
|---|---|---|---|---|---|
| `manc_v1.2.1` | 0.90 ([0.80, 0.95]) | [1126, 1220, 2825, 2973] | replaces the canonical [2825, 2973, 3310] on reliance failures: silencing {1126, 1220} breaks the function on 4 replicates on which silencing {3310} does not, never the reverse (9 replicates; P = 0.969 > 0.95) | 1126, 1220: 0.962; 3310: 0.027 | 328 / 511 |
| | **0.95** ([0.90, 0.975]) | [1126, 1220, 2825, 2973] (v1.1's) | the same, 5 against 0 over 12 replicates, P = 0.984 > 0.975; the readout part (−0.13 per member against the band 0.21) inside the band | 1126, 1220: 0.977; 3310: 0.013 | 334 / 518 |
| | 0.975 ([0.95, 0.9875]) | **[2825, 2973, 3310], tied with [1126, 1220, 2825, 2973]** | the same counts (P = 0.984) lie inside this setting's tie band: a tie; the canonical set is kept (Occam prefers it but may not overrule a lean inside the band) | 3310: 0.496; 1126, 1220: 0.437 (weights 0.5 / 0.5) | 344 / 360 |
| `male-cns_v1.0` | 0.90 ([0.80, 0.95]) | [653, 1052, 2152], tied with [653, 1052, 2948] | the tie: readout difference 0.20 per member inside the band 0.22, no failure on either side; a 6-member replacement ranked below on the readout part (P = 0.952, 9 replicates) | 2152: 0.483; 2948: 0.426; the replacement's four: 0.019 | 353 / 370 |
| | **0.95** ([0.90, 0.975]) | the same (v1.1's) | the tie as above; the 6-member replacement below on the readout part (P = 0.975, 12 replicates) | 0.475; 0.419; 0.010 | 348 / 365 |
| | 0.975 ([0.95, 0.9875]) | the same | the tie as above; the replacement's readout posterior (0.975) is inside this tie band and leans the way Occam points, so Occam ranks it below | 0.466; 0.411; 0.051 | 364 / 381 |

**Does a returned core change?** On MaleCNS, no: the same core and the same tie at all three settings; only the weight of the
6-member replacement follows the strength of its defeat (0.019 / 0.010 / 0.051). On MANC the core is the same at 0.90 and 0.95 and
changes at 0.975, and there it comes out as a tie: the failure counts (5 against 0, P = 0.984) that decide beyond the default's band
lie inside the stricter setting's band [0.95, 0.9875]; the canonical set is kept, the replacement is listed as tied
(`selection.tied`; key `tie band` in the selection trace; `why`: "tied with 1 candidate(s) (probability shared; a reliance posterior
within the tie band)"), and the two share the mass (weights 0.5 / 0.5; no distinctive member at P ≥ 0.85). The two neurons both
candidates share (2825, 2973) are essential and at 0.99 at every setting, and so are MaleCNS's 653 and 1052. At the default every paired
decision needs P > 0.975, so it holds for every threshold in review B's ±50 % range of the tail mass (0.90–0.975); a run with
`decisive` = 0.975 moves that range to 0.95–0.9875, and the MANC evidence falls inside it. (v1.1 decided the MANC replacement with a t
posterior of 0.954 on the bimodal statistic and, at 0.975, returned the canonical set through Occam with the replacement filed as worse.)

The margin (factor 2) was fixed on the general ground of section 2 before these runs and was not changed after them. One rule was added
after the first run at 0.975 (build `d1be0ca6`): there the in-band reliance comparison fell through to Occam, which preferred the
smaller canonical set and filed the replacement as worse by size (probabilities 0.66 against 0.29) — a jump at the band's edge by
another route. The final code does not let a later key overrule a reliance posterior in the tie band that leans the other way (section
2). The rule acts only on posteriors inside the band; none of the 1,026 dev runs of `d1be0ca6` had one (174 recorded pairs), and the
final code, re-run on every dev suite, reproduces that build's 1,026 records run for run (identical cores, probabilities, essential
claims, flags and calls); on the real bundle it changes only the MANC run at 0.975. Wall time per run: 15–23 min with three runs in parallel (CPU 813–932
s).

**B6: low budgets.** At 50 and 100 calls (small + medium suites, both orders, seed 0, 110 runs each) v1.2 returns v1.1's core in every
run, and 108 of the 110 runs at each budget are flagged `budget_limited`, with their phases (at 50 calls: edge predictions in 104 runs,
final fidelity 102, alternatives 100, necessity screen 92, certificate 56, essentiality 41 and 38 (canonical set, selected core),
selection 21, validation 11, elimination 8, union repair 2; at 100 calls: alternatives 108, edge predictions 46, final fidelity 30,
necessity screen 26, certificate 13, essentiality 4 and 2, union repair 2, selection 1). At these budgets the reserve cannot help the
certificate: the elimination, the validation and the essentiality tests of the canonical set use the budget before the screen starts,
so the certificate is still cut in 56 and 13 runs, as in v1.1.

Where the certificate competes with the screen and the enumeration — the medium suite (n = 500) at 150, 200 and 300 calls, v1.1 and
v1.2 on the same 16 runs each (`b6_medium_b150` / `b200` / `b300`, the v1.1 code run by `data/synthetic/dev_v1/run_legacy.py`):

| budget | version | runs | structural | success_intact | certificate cut by the budget | flagged `budget_limited` | calls: screen / alternatives / certificate (mean) | calls median / mean | same core as the other version |
|---|---|---|---|---|---|---|---|---|---|
| 150 | v1.1 | 16 | 1.00 | 1.00 | 3 | — | 53.0 / 1.0 / 1.2 | 148 / 138 | 16 of 16 |
| 150 | v1.2 | 16 | 1.00 | 1.00 | 3 | 16 | 51.0 / 1.0 / 3.7 | 148 / 138 | 16 of 16 |
| 200 | v1.1 | 16 | 1.00 | 1.00 | 1 | — | 68.1 / 1.0 / 4.9 | 160 / 161 | 16 of 16 |
| 200 | v1.2 | 16 | 1.00 | 1.00 | 1 | 16 | 68.1 / 1.0 / 4.9 | 160 / 161 | 16 of 16 |
| 300 | v1.1 | 16 | 1.00 | 1.00 | 0 | — | 70.9 / 9.7 / 4.8 | 192 / 186 | 16 of 16 |
| 300 | v1.2 | 16 | 1.00 | 1.00 | 0 | 8 | 70.9 / 7.9 / 5.1 | 190 / 183 | 16 of 16 |

The reserve works as intended where it binds: at 150 calls the three runs whose certificate v1.1 cut after a single call give it 8–17
calls in v1.2, taken from the screen (51 → 35 and 57 → 41 calls) or the union repair (20 → 12) — but the lazy certificate of a
two- or four-member core with non-essential members can need more than its reserve ((validation_seeds + 1) calls per non-essential member), and those three runs are still cut, as is one run at 200
calls in both versions. Every one of these runs is flagged, and so is every other run whose phases the budget cut (at 300 calls 8 of 16,
where the enumeration of alternatives reached its budget share; v1.1 recorded that phase as out of budget in 6 of these runs,
without a flag, and not at all in the other 2, where the enumeration absorbed the refused call). The returned cores do not change in any of the 48 pairs of runs: at these budgets the search, not the certificate, decides the core.

**B5 (optional saving): stress probes only for equal-size pairs that reliance leaves tied.** Switched off (`stress_only_for_ties` =
False, every compared candidate probed as in v1.1) on the adversarial dev suite (88 runs) and on the small and medium plain suites
(seed 0, 110 runs): identical cores and identical probabilities in all 198 runs; the stress probes cost 94 instead of 98 calls on the
adversarial runs and 131 instead of 235 on the plain runs (mean calls per run 185.5 against 185.6 and 134.1 against 135.0; 15 runs
cheaper, none dearer). The saving is small because the probes were rare already; it is kept because it cannot change a core.

**B8.** No run of the final code was flagged `minimality_unverified` (1,092 runs): every elimination and every certificate ended
with a round that removed nothing, within |kept| rounds. The certificate removed a member in one run (a subset-of-draws latch, n = 150,
one node order: 112 removed from [77, 112], as in v1.1); the reduced core validated decisively, so the removal stands; no removal was
rejected in any run. The unit test builds an elimination that needs five rounds (each removal makes the next member removable),
checks that the loop reaches the 1-minimal set, and that a cap of three rounds reports `minimality_verified` = False.

**B9.** The round robin found no cycle in any run (no `selection_cycle` flag in 1,092 runs of the final code: 1,086 dev runs,
including the switch-off and low-budget ones, and the 6 real-bundle runs). On the plain suites (small, medium and large) the reliance of
a pair decided 14 of 103 comparisons (all by the readout part; no pair was decided by failure counts there) and left 89 tied, none with
a posterior in the tie band; on the pairs suites 1 of 18 decided (readout); on the adversarial suites none of the 24 recorded
comparisons decided anything (participation and fidelity decide first; the harness truncated the selection records of 6 of the 176
runs). The unit test reverses the candidate list of a redundant-mechanism run and checks that the winner, the tied set and the losers
are unchanged.

### 12.11 Tests, lint and hashes

Final code, in the clean room (pytest's temporary files kept inside it with `--basetemp`):

```
uv run --no-sync ruff check src/brainir/methods/brainir_v1.py src/brainir/methods/_brainir_v1_sha256.py \
    tests/test_method_brainir_v1.py src/brainir/discovery/joint.py src/brainir/discovery/correspondence.py   # All checks passed
uv run --no-sync pytest tests/test_budget_integrity.py tests/test_method_brainir_v1.py tests/test_discovery_infra.py -q
        # 59 passed, 1 skipped (clean-room builder not in this checkout), 130 s; the 2 RuntimeWarnings (mean of an empty list) come
        # from the infrastructure's tournament.summarize in test_failures_stay_in_the_denominators, not from the method
uv run --no-sync pytest tests/test_joint.py tests/test_discovery_cross.py tests/test_pairs_v2.py -q    # 21 passed, 68 s
uv run --no-sync pytest tests/test_method_brainir_v1.py -q                                            # 32 passed, 116 s
```

`test_method_brainir_v1.py` (32 tests, own synthetic instances only; under 3 minutes): registration, every switch present and the v1.0
fixed margins gone; recovery of an E–I pair with roles, essential claims, simulated edge predictions (with confidences), the size–error
curve with member lists, participation and reserved fidelity seeds, the code identity and no budget-limited phase at 1,000 calls, and a
schema-valid prediction; determinism under the seed and independence of the node order; redundant mechanisms reported with shared
probability and `redundant_backup` roles; a context member found by full-network necessity (and missed without the screen); **a
controller with a backup copy keeps every neuron it finds essential in the core with its necessity posterior as a probability floor**
(review A finding 1); activity-band and persistence mechanisms; the budget is never exceeded (budgets 1, 4, 12, 30) and every run the
budget cut says so (`budget_limited` with its phases, review B finding B6); every switch off (the search switches, the finishing-phase
switches in three groups) runs within budget with a valid, independently re-checked core; the budget-integrity rules (static checks,
seeds below 5,000 and never in 1000–1015 at seeds 0, 3 and 15, seeded noise, `cfg_override` whitelist); meaning-preserving
perturbations keep the core; the prior only orders the search; the cross-connectome step shares the budget pool and claims only
verified, matched, complete identities; no identity claim across implementations under a shift or on a null pair; the run entry point;
the adversarial properties of reviews A and G on small trap instances built with the third-party generator (**a latent backup is never
returned and every core member participates**; **a gate masked by its drivers is found and every positive necessity verdict is in the
core with its posterior as a floor, with claims for every neuron tested**; **a distributed drive is flagged, with no core member at
P ≥ 0.85 and equal probabilities for the exchangeable relays**); and the review-B properties: **the method file's sha256 is current and
recorded** in the diagnostics and the method info, and a seed ≥ 16 records the period-16 warning (B1, B7); **reliance tests function
failures as paired counts** — the real MANC pattern, 5 against 0 discordant replicates, decides at `decisive` 0.90 and 0.95 and is a tie
at 0.975, where Occam may not overrule its lean while a preference that agrees with the lean still decides — the readout part is tested
against the noise band, and a readout part that contradicts the failures decides nothing (B2); **the minimality rounds repeat until one
removes nothing** (a chain that needs five rounds) and a cap reached while rounds still remove members is reported (B8); **the round
robin's winner, tied set and losers do not depend on the order of the candidate list** (B9).

**Final hashes (sha256).**

| file | sha256 |
|---|---|
| `src/brainir/methods/brainir_v1.py` (v1.2.0, final) | `4bfcf81628aba7684688fefd113eddd705a13e250f119caea2050cd65d84d2a7` |
| `src/brainir/methods/_brainir_v1_sha256.py` (new in v1.2: the method file's hash, which the method records) | `07df449ee6fd09e9c23c595ffa37686dffde36ae3fd53bd3fb9b717253b7c7e9` |
| `src/brainir/discovery/joint.py` (unchanged since v1.1) | `38609d27eb6e0e9e2445f60970d0be151bb8526d0dd773cc59a0ce6477737687` |
| `src/brainir/discovery/correspondence.py` (unchanged since v1.1) | `11acef92bf1e86ceffeb2636cc3c61a4f81fb361ca6b5c1d8658c8b739aa599e` |
| `tests/test_method_brainir_v1.py` | `5c95a3857297c703caf0f89c2e1420d074e1558806905c5071283d0330b7beab` |
| `src/brainir/methods/brainir_v1.py` v1.1 (reference) | `94ea1f8ebd5396f386f23b05ea8114812d7e5645caa8df792c1505b4124b812c` |

Every v1.2 number in sections 0, 9, 12.9 and 12.10 comes from `4bfcf816…` — records `adv_v12_dev`, `adv_v12_hold`, `v12_small`,
`v12_medium`, `v12_large`, `v12_b50`, `v12_b100`, `adv_v12_dev_allstress`, `v12_allstress`, `pairs_dev_v12`, `pairs_holdout_v12`,
`b6_medium_b150` / `b200` / `b300` and `real/v12_*`, each of which carries the hash in `diagnostics["code"]` — except the account of the
first build `d1be0ca6` in section 12.10 (records `d1be_*`). Every v1.1 number comes from `94ea1f8e…` (records `adv_v11_dev`,
`adv_v11_hold`, `abl2_*`, `v11_small`, `v11_medium`, `v11_large`, `v11_b50`, `v11_b100`, `pairs_dev_v11`, `pairs_holdout_v11`,
`real/v11_*`), except the development history (section 12.6), which names its own versions; the adversarial records of v1.0, v1.1
and the comparators are re-scored with the current scorer (suffix `_rs`, section 12.2).
