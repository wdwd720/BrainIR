# joint — cross-connectome shared-mechanism discovery (component F)

Code: `src/brainir/discovery/joint.py` (`discover_pair`, `PairResult`, CLI `python -m brainir.discovery.joint`). Tests:
`tests/test_joint.py`. Contract: `research/phase2/CROSS_CONNECTOME_CONTRACT.md`. Everything below was developed on the
author's own synthetic pairs (`brainir.discovery.synthetic_pairs`, truth written under the author's own `truth/` directory);
no evaluation-suite truth, no real-circuit knowledge and no literature about the benchmark datasets was used.

## 1. What the component does

Two networks (two connectomes, or the two halves `a`/`b` of a synthetic pair) may implement the same abstract mechanism
with different neurons. `discover_pair(a, b, method_name, budget_a=, budget_b=, seed=, mode=)` runs a registered base
discovery method and shares structure between the networks through PUBLIC evidence only:

* **anchor-fingerprint correspondence** (`brainir.discovery.correspondence`): ranked counterpart candidates with z-scores —
  hypotheses, never identities;
* **public wiring**: the signed edges among mechanism members (structural alignment, role graphs of
  `brainir.discovery.transfer`).

Every simulation goes through a `BudgetedSimulator` of the network it runs on; the total never exceeds
`budget_a + budget_b`; calls spent testing a mechanism carried over from the other network are reported as `adaptation`.

| mode | what happens |
|---|---|
| `independent` | base method on A (budget_a), base method on B (budget_b); nothing shared (the baseline) |
| `transfer` | base method on A; B's mechanism = `transfer_core(A's core)` with adaptation budget = budget_b; no discovery on B |
| `prior` | base method on A; base method on B (budget_b) with `config["prior"]` = A's inclusion probabilities carried through the correspondence (Section 4) |
| `joint` | cross-verified discovery (Section 2) |

The base method is any method registered with `MethodRegistry` (`get_method` also imports a module
`brainir.methods.<name>` on demand, so methods not yet listed in `brainir/methods/__init__.py` work too); it is run
unchanged through its public `discover(problem, sim, seed, config)`; `config["method_config"]` (both networks) and
`config["method_config_a"/"_b"]` are merged over its `default_config`, and `config["prior"]` is added in `prior` / `joint`.
Methods that ignore the prior (greedy_reference) simply behave as in `independent`.

`PairResult` = `result_a`, `result_b` (`DiscoveryResult`), `correspondence` [(pos_a, pos_b, confidence)],
`role_alignment` {role: {"a": [...], "b": [...]}, "role_graph_similarity": float}, `budget`
{"a", "b", "adaptation", "total", "adaptation_a", "adaptation_b", "limit", "by_kind", "phases", "cache_hits"} with
`total = a + b + adaptation <= budget_a + budget_b`, and `diagnostics` (per-step trace, prior summary, role graphs, config).

## 2. The joint mode (plain language)

The idea is invariance: the planted mechanism is the one that works in BOTH networks with a consistent
correspondence, while a background set that happens to satisfy the criterion in one network (a hub driving the readout into
its band, a distractor loop) has no counterpart that works in the other. So every mechanism carried across is checked by
simulation in the receiving network, and between two sufficient mechanisms a network keeps the one that aligns with the
other network's mechanism.

1. **Lead.** The network with fewer candidates leads (discovery is cheaper there; tie → a). The base method solves it with
   the lead's own budget, in a fresh simulator — so the lead's first result is exactly the `independent` result.
2. **Verified transfer lead → follower** (adaptation calls). The lead's core is mapped into the follower and tested with
   cheap keep-only probes, in this order: the *structural image* (Section 3), the top-1 fingerprint image, the union of the
   top-k images. The first passing set is minimised by group elimination (a group is removed only if keep-only of the rest
   still passes AND silencing the group in the full network keeps the function, so members that are essential in the full
   network but redundant under keep-only — e.g. the inhibitor that silences a competitor — survive), completed with a
   counterpart of every lead member the base method found essential (candidates tested by silencing), each member's
   essentiality is tested, and the set is validated on fresh seeds. The allowance is funded by the lead's unused calls,
   clipped to [10 %, 30 %] of the follower's budget.
3. If the transfer verifies, the follower's mechanism is that set (no discovery on the follower), and the lead's core is
   **consistency-pruned**: members whose counterparts were eliminated are dropped if keep-only of the rest still passes and
   silencing them keeps the function.
4. Otherwise the base method runs on the **follower with the transported prior** (damped ×0.5 because the transfer failed)
   and with every call the pool has left, minus a small reserve for step 5 taken only from the surplus above the follower's
   own budget (the follower never gets less than its independent budget while the pool allows).
5. **Alternating verified transfers** (after 3 or 4), follower → lead first, at most `max_rounds` = 3: the receiving
   network compares its current mechanism with the carried-over one by the alignment objective (Section 5) and keeps the
   better one (the other becomes an alternative); the loop stops as soon as the two mechanisms are each other's image (every
   member of both in a mutual structural pair — checked without calls), a transfer fails, or the receiving network keeps its
   own. The source of the last accepted transfer is consistency-pruned. After step 3 this carries the verified, minimised
   follower mechanism back into the lead — which corrects a lead whose own core was wrong but still contained enough of the
   mechanism for its image to be completed in the follower (observed: feedforward pairs with greedy_reference, Section 9).

### Pseudocode

```
joint(A, B):
    L = argmin_net |candidates|;  F = other
    R[L] = M(L, budget_L)                                   # identical to independent on L
    tr = verified_transfer(L -> F, R[L], cap = clip(budget_L - used_L, .1 budget_F, .3 budget_F))
    if tr.accepted:
        R[F] = tr.core;  R[L] = consistency_prune(L, R[L], tr)
    else:
        R[F] = M(F, prior = transport(R[L], rho * 0.5), budget = pool_left - reserve)
    src, dst = F, L
    repeat up to 3 times:
        if consistent(R[a], R[b]) or not R[src]: break
        tr = verified_transfer(src -> dst, R[src]);  if not tr.accepted: break
        if tr.core != R[dst]:
            if J(tr.core | R[src]) beats J(R[dst] | R[src]):  R[dst] = tr.core  (old R[dst] -> alternatives)
            else: break
        src, dst = dst, src
    consistency_prune(source of the last accepted transfer)

verified_transfer(src -> dst, S_src):
    for probe in [structural_image(S_src), top1_image(S_src), union_topk_images(S_src)]:
        if keep_only(probe) passes (majority of 3 seeds, sequential): break
    else: return rejected
    S = minimise(probe)       # groups of low support first; keep-only(rest) passes AND silence(group) passes
    S += counterpart of each src member essential in src (first candidate whose silencing fails)
    essential[v] = not passes(silence(v)) for untested v in S
    accepted = keep_only(S) pass fraction on 2 fresh seeds >= 0.5
```

## 3. Structural alignment (no calls)

`_Corr.assign(src, dst, members)` — beam search (width 64) over injective assignments member → candidate (each member's
top-`assign_k` = 6 fingerprint candidates, or "no counterpart") maximising

    sum_members z(member -> candidate)  +  edge_bonus * #(signed member edges reproduced between the assigned candidates)

with the "no counterpart" option scored at the null z (the mean best-match z of 50 random interneurons). Self-loops count
as edges. The anchor fingerprint alone can rank a decoy (a distractor that copies a member's anchor profile and
annotations) or a noisy look-alike above the true counterpart; the decoy does not reproduce the member's wiring to the other
members, the counterpart does. `edge_bonus` = 2 z-units per reproduced edge. The same alignment (restricted to the two final
cores, both directions) produces the claimed correspondence.

## 4. How the prior is formed (`prior` mode, and joint step 4)

For every source position p with inclusion probability q_p >= 0.1 (at most 64, highest first; core members always), its
top-k (k = 3) fingerprint candidates c get probabilities w(p -> c) = softmax(z / T) over the k candidates plus a "none of
these" option whose logit is the null z (T = 1). An indistinct favourite therefore gets little mass and two look-alikes (a
member and its decoy) share it; candidates of a source neuron without any anchor contact are down-weighted ×0.25. Then,
for every candidate c of the target network,

    prior(c) = 1 - (1 - base) * prod_p (1 - rho * q_p * w(p -> c))          base = 0.02, rho = 0.8

(noisy-OR). Every candidate gets a value, so "not pointed to" is expressed as the low base rate, not as the neutral 0.5
that methods assume for absent positions. The expected number of members under the prior is reported in diagnostics.

## 5. Role-alignment objective

For a network `n` with candidate mechanisms S (its own and the carried-over one) and the other network's current mechanism T:

    key(S) = ( validated(S),  J(S, T),  -|S| )        compared lexicographically, the larger wins
    J(S, T) = role_graph_similarity(G(S), G(T))  +  (1 / max(|S|, |T|)) * sum_{claimed pairs} confidence

`validated` = keep-only pass fraction >= 0.5 on the fresh validation seeds (the carried-over set is validated by
construction). `G` = role graph (roles + signed role→role interactions from the public matrix, `transfer.role_graph`);
roles come from the base method when it gives them, otherwise from the generic rules of `infer_roles` (sign, self-loop,
strongly connected component, all-excitatory cycle, projection onto the readout / readout groups / other members, criterion
type) — the same rules on both networks. Correspondence confidence of a claimed pair = mean fingerprint probability of the
two directions, raised by each reproduced edge the pair takes part in (1 - (1 - w)/2^edges), ×0.6 if the roles disagree.

## 6. Budget accounting

* One cache per network; each phase opens a fresh `BudgetedSimulator` sharing that cache (a base method always starts at
  calls = 0 with `remaining` = its allowance; a query is paid once). Opening a phase closes the previous one
  (`max_calls = calls`), and every allowance is <= the pool's remaining calls, so `total <= budget_a + budget_b` holds by
  construction; `_Ledger.report` asserts it.
* Categories: `discovery` (base method), `evaluation` (transfer mode's top-1 evaluation), `adaptation` (everything spent on
  a carried-over mechanism: probes, minimisation, essentiality of its members, its validation; transfer mode's re-assignment
  search), `validation` (fresh-seed validation of a network's own mechanism, consistency pruning). `budget["a"]` and
  `budget["b"]` exclude adaptation; `budget["adaptation"]` is reported separately (also per network).
* `independent`, `prior`, `transfer` never pool: each network is capped by its own budget. `joint` pools: the lead gets its
  own budget, the follower whatever remains (always >= its own budget minus the adaptation that its budget had to fund).

## 7. Hyper-parameters (`DEFAULT_CONFIG`)

| name | default | meaning |
|---|---|---|
| `method_config`, `method_config_a/_b` | {} | passed to the base method (merged over its `default_config`) |
| `k` | 3 | fingerprint candidates per member (prior spread, union probe, `transfer_core`'s k) |
| `assign_k`, `edge_bonus`, `beam` | 6, 2.0, 64 | structural alignment |
| `temperature`, `n_null` | 1.0, 50 | softmax temperature; random interneurons for the null z |
| `prior_rho`, `prior_base`, `prior_min_q`, `prior_max_members` | 0.8, 0.02, 0.1, 64 | prior formation |
| `prior_damp_failed_transfer` | 0.5 | rho multiplier in joint step 4 |
| `probe_seeds`, `validation_seeds`, `transfer_seeds` | 3, 2, 2 | seeds per decision (strict majority, sequential), fresh validation seeds, transfer-mode seeds |
| `adapt_min_fraction`, `adapt_max_fraction` | 0.1, 0.3 | adaptation allowance per transfer (fraction of the receiving network's budget) |
| `lead`, `max_rounds` | "auto", 3 | joint lead choice; alternating transfers |
| `consistency_prune`, `claim_min_confidence` | True, 0.1 | |

No parameter encodes a mechanism size, a family, a neuron id, a cell type or a dataset.

## 8. Complexity

No-call parts: fingerprints O(nnz(C) + n·anchors) per network, once; matching O(|S| · n_dst · anchors); the beam search
O(|S| · beam · assign_k · |S|). Calls: a verified transfer costs 1–3 probe decisions (2–3 calls each), the minimisation
about |S| + 2 log2|probe| decisions (plus one silencing decision per removed group), one silencing decision per member and 2
validation calls — typically 10–60 calls for |S| <= 6. Joint = one base-method run + one transfer when the mechanism carries
over; two base-method runs + up to 3 transfers otherwise.

## 9. The author's pair experiments

**Instances.** 34 verified pairs generated with `brainir.discovery.synthetic_pairs` from the author's own seeds (9000–9802,
bumped by +7000 steps when an instance failed verification; the evaluation suite uses other seeds), verified with
`verify_pair(pair, seeds=range(4))`, exported to `data/synthetic/dev_joint/pairs/{instances,truth}`:

* fast families (23 pairs): feedforward_driver 7, negative_feedback_controller 5, integrator 5, winner_take_all 4,
  memory_switch 2; kinds: plain 60×80 (9), anchor decoy 60×80 with meta_noise 0.3/0.6 (8), 80×60 with complications
  (hub_distractor in a; misleading_centrality + backup_copy in b) + decoy (5), **medium** 300×400 feedforward with
  hub_distractor + misleading_centrality in a, hub_distractor in b + decoy (1);
* oscillator families (10 pairs): ei_pair, ring, delayed_inhibitory (plain 60×80 and 80×60 complications + decoy each),
  two_implementations and redundant_oscillator with **implementation_shift** (with and without decoy).

Scoring (own truth only, `score()` in the harness): success = the core contains some sufficient alternative of that
network; correspondence precision/recall of the claimed pairs vs the identity correspondence (undefined under shift); role
accuracy = claimed role == truth role over the aligned members; role-graph similarity as reported; calls from `budget`.

**Commands** (inside the clean directory; the harness `data/synthetic/dev_joint/harness.py` — build / run / summary — and
`analyze.py` are development scripts next to the instances, not deliverables; every run is `discover_pair(...)` on one pair):

```
uv run --no-sync python data/synthetic/dev_joint/harness.py build --out data/synthetic/dev_joint/pairs --set all --workers 3
# E1: greedy_reference (ignores priors), budget 400 per network, fast families
uv run --no-sync python data/synthetic/dev_joint/harness.py run --suite data/synthetic/dev_joint/pairs \
    --filter feedforward negative_feedback winner_take_all integrator memory_switch --method greedy_reference --budget 400 --workers 2 --tag fast_gr400
uv run --no-sync python data/synthetic/dev_joint/harness.py run ... --method greedy_reference --modes joint --tag fast_gr400_joint2   # final joint
uv run --no-sync python data/synthetic/dev_joint/analyze.py fast_gr400 --joint fast_gr400_joint2
# E2: greedy_plus (honours config["prior"]), budget 400, fast families
uv run --no-sync python data/synthetic/dev_joint/harness.py run ... --method greedy_plus --budget 400 --workers 3 --tag fast_gp400
# E3: greedy_plus, budget 400, oscillator families incl. implementation shift
uv run --no-sync python data/synthetic/dev_joint/harness.py run --suite data/synthetic/dev_joint/pairs \
    --filter ei_pair_oscillator__n60 ei_pair_oscillator__n80 ring_oscillator delayed two_implementations redundant --method greedy_plus \
    --budget 400 --workers 3 --tag osc_gp400
# one pair through the public CLI
uv run --no-sync python -m brainir.discovery.joint --pair data/synthetic/dev_joint/pairs/instances/<label> --method greedy_reference \
    --mode joint --budget-a 400 --budget-b 400 --seed 0 --out pair.json
```

### E1 — base method greedy_reference, 23 fast-family pairs, budget 400 + 400, seed 0

| mode | success a | success b | both | corr precision | corr recall | role acc | role-graph sim | calls a | calls b | adaptation | total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| independent | 0.43 | 0.35 | 0.26 | 0.43 | 0.38 | 0.97 | 0.34 | 219 | 266 | 0 | 485 |
| transfer | 0.43 | 0.48 | 0.39 | 0.30 | 0.49 | 0.92 | 0.51 | 219 | 2 | 47 | 268 |
| prior | 0.43 | 0.35 | 0.26 | 0.43 | 0.38 | 0.97 | 0.34 | 219 | 266 | 0 | 485 |
| **joint** | **0.74** | **0.70** | **0.70** | **0.95** | 0.73 | 1.00 | **0.83** | 182 | 142 | 30 | **354** |

Both-network success by kind (independent → joint): plain 0.33 → 0.78 (9 pairs), decoy 0.12 → 0.75 (8),
complicated + decoy 0.40 → 0.60 (5), medium 0 → 0 (1). greedy_reference ignores `config["prior"]`, so `prior` = `independent`
exactly (a check of the plumbing: identical cores and calls on all 23 pairs). The anchor decoy entered B's core in 0 of
14 decoy pairs under joint (1 under independent). The first joint version (no alternating rounds after a verified
lead → follower transfer) reached both = 0.52; carrying the verified follower mechanism back to the lead raised it to 0.70.

### E2 — base method greedy_plus, same 23 pairs, budget 400 + 400, seed 0

| mode | success a | success b | both | corr precision | corr recall | role acc | role-graph sim | calls a | calls b | adaptation | total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| independent | 0.96 | 0.91 | 0.87 | 1.00 | 0.80 | 1.00 | 0.87 | 89 | 84 | 0 | 173 |
| transfer | 0.96 | 0.87 | 0.87 | 0.89 | 0.80 | 1.00 | 0.87 | 89 | 2 | 2 | 93 |
| prior | 0.96 | 0.96 | 0.91 | 1.00 | 0.83 | 1.00 | 0.91 | 89 | 71 | 0 | 159 |
| **joint** | **1.00** | **1.00** | **1.00** | 1.00 | **0.91** | 1.00 | **1.00** | 61 | 18 | 13 | **91** |

**Prior vs independent on B** (paired, same seed and budget): mean calls on B 84.4 → 70.7, median 74 → 43; success on B
0.91 → 0.96; on the 21 pairs where B succeeds in both modes, 78.4 → 63.2 calls (mean relative reduction 20 %). The
medium pair (n 300×400): independent a ✓ b ✗ (415 calls), transfer a ✓ b ✗ (202), prior a ✓ b ✓ (433), joint a ✓ b ✓
with 212 calls (B solved by a verified transfer, 16 adaptation calls).

### E3 — base method greedy_plus, 10 oscillator pairs (incl. implementation shift), budget 400 + 400, seed 0

| mode | success a | success b | both | corr precision | corr recall | role acc | role-graph sim | calls a | calls b | adaptation | total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| independent | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.90 | 0.90 | 117 | 87 | 0 | 204 |
| transfer | 1.00 | 0.60 | 0.60 | 0.92 | 0.92 | 1.00 | 0.60 | 117 | 2 | 7 | 126 |
| prior | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.90 | 0.90 | 117 | 61 | 0 | 178 |
| **joint** | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.90 | **1.00** | 84 | 46 | 19 | **149** |

(correspondence precision/recall are averaged over the 6 non-shift pairs, where the identity correspondence is defined.)
By kind (both-network success, independent / transfer / prior / joint): plain 1.00 / 0.67 / 1.00 / 1.00 (3 pairs),
complications + decoy 1.00 / 1.00 / 1.00 / 1.00 (3), **implementation shift 1.00 / 0.25 / 1.00 / 1.00** (4). Plain
`transfer` fails on 3 of 4 shift pairs (A's mechanism has no working image in B) and on one plain ei_pair pair; joint
detects the failed transfer, discovers B with the prior and aligns the roles (role-graph similarity 1.00 on all 10 pairs vs
0.90 for independent). Prior vs independent on B: 87.2 → 61.2 calls (median 98 → 62; mean relative reduction 28 %), success
unchanged (10/10). Joint's total calls are 27 % below independent's (149 vs 204); on the two_implementations shift + decoy
pair joint needed slightly more than independent (348 vs 330: a rejected transfer, B's own discovery, a verified transfer
back to A).

### Summary across experiments (both-network success; mean total calls)

| base method, suite | independent | transfer | prior | joint |
|---|---|---|---|---|
| greedy_reference, 23 fast pairs | 0.26; 485 | 0.39; 268 | 0.26; 485 | **0.70; 354** |
| greedy_plus, 23 fast pairs | 0.87; 173 | 0.87; 93 | 0.91; 159 | **1.00; 91** |
| greedy_plus, 10 oscillator pairs (4 shift) | 1.00; 204 | 0.60; 126 | 1.00; 178 | **1.00; 149** |

Budgets were never exceeded (the ledger asserts `total <= budget_a + budget_b` on every run; 247 runs — E1 92 + 23 final
joint, E2 92, E3 40 — with 0 errors and 0 runs above the limit). Single seed (0) per pair: the success rates carry the
sampling uncertainty of 10–23 pairs.

## 10. Failure modes and limitations

1. **The base method never proposes a member.** Joint recombines and verifies what some base-method run proposed; it
   cannot invent a member no run contained. With greedy_reference on winner_take_all (keep-only of the winner alone passes,
   so the lateral inhibitor is eliminated and stays out), joint recovers the winner in both networks but both networks still
   fail (4/4 pairs). The essential-counterpart completion only acts on members the base method marked essential.
2. **Both base-method runs wrong and no transfer verifies.** (greedy_reference: the medium feedforward pair and one 80×60
   feedforward pair.) Nothing to recombine; joint = independent plus a few rejected probes (≈ 10 calls).
3. **Pool exhausted before the correcting transfer.** When the lead spends its whole budget on a wrong core and the
   follower's own discovery then spends everything left, the alternating transfer that would carry the follower's (right)
   mechanism back has no calls (greedy_reference, negative_feedback 80×60: lead b wrong with 400 calls, follower a right
   with 395, 1 call left). The reserve for the rounds is only taken from the surplus above the follower's own budget, by
   design (the follower's discovery keeps its independent budget); a larger guaranteed reserve would trade this case against
   exhausting the follower's discovery.
4. **A wrong mechanism whose image verifies.** The alignment objective prefers the carried-over mechanism when both are
   sufficient; if the follower's own mechanism is a background artefact AND its image in the lead passes keep-only while the
   lead's right mechanism did not transfer, the lead would switch to the artefact. Not observed in E1–E3 (it requires the
   same artefact to be sufficient in two independent backgrounds), but possible on real data where backgrounds are not
   independent.
5. **Weak correspondence.** On tiny networks the fingerprint rank of a true counterpart can be 4th–6th behind a decoy and
   look-alikes (observed: 30×36 feedforward pair). The structural alignment (reproduced member edges) and the union probe
   recover it; mechanisms without internal edges (a single member without a self-loop) rely on the fingerprint alone.
6. **Implementation shift is aligned at role level only.** When the two networks use different alternatives, the claimed
   identity correspondence is empty or partial and role alignment carries the comparison; roles are rule-based (Section 5)
   and, for redundant copies, cannot tell "primary" from "backup".
7. **Scale.** The structural alignment and the claims are cheap, but every verified transfer on a large network includes
   full-network silencing decisions (essentiality, group removal), which dominate wall time (seconds per call at 4,600 nodes).
8. **Deterministic tie-breaking** (support, position) decides between interchangeable members inside a minimisation; the
   result is sufficient and 1-minimal but may differ from the base method's choice among equivalent sets (both reported).

## 11. Evaluation pair suite

The component was not tuned on `data/synthetic/pairs_v1` (its truth is withheld) and no result on it is reported here.
