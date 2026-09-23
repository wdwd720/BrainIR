# Phase 2 contract: cross-connectome shared-mechanism discovery (component F)

You are implementing the **generic cross-network component** of BrainIR v1: given two networks that may implement
the same abstract mechanism with different neurons, discover the mechanism in both and align it at the level of
roles — using only public evidence, and with every simulation counted. Read `METHOD_DEV_CONTRACT.md` first: all of
its rules apply (benchmark-generic, budget honesty, uncertainty, robustness, no answer-seeking, never read outside
your clean development directory).

## 1. What you have

- `brainir.discovery.correspondence`: candidate counterparts of A neurons in B from **anchor fingerprints** (synaptic
  contact with labelled anchor types shared by both networks) plus annotation agreement (`hemilineage`,
  `soma_neuromere`, `side`, `sign`, `sub_class`); z-scores against all other candidates; `mutual_best`;
  `null_match_scores`. Interneuron tokens are NOT shared across networks; only labelled anchors and annotations are.
- `brainir.discovery.transfer`: `transfer_core` (top-k mapping with a separately accounted adaptation budget),
  `null_transfer` (sign-matched random sets), `role_graph` / `role_graph_similarity` (abstract mechanism = roles +
  signed role->role interactions).
- `brainir.discovery.synthetic_pairs`: generate your own pairs (`PairSpec`, `build_pair`, `verify_pair`,
  `export_pair`) — same mechanism family in two independent backgrounds, shared inert anchors, noisy annotations,
  `implementation_shift` (b implements the family's other alternative: role-level correspondence only),
  `anchor_decoy` (a distractor in b copies a member's anchor profile). The evaluation pair suite
  (`data/synthetic/pairs_v1/instances/<label>/networks/{a,b}`) has its truth withheld.
- Every registered discovery method (`brainir.methods`, `MethodRegistry`) as a base method; `greedy_reference` is
  always available. Methods accept `config["prior"]` = {position: prior inclusion probability in [0, 1]} (developers
  were asked to honour it: use it to initialise/bias candidate ranking; treat absence as uniform).

## 2. What you must deliver

`src/brainir/discovery/joint.py` with

```python
@dataclass
class PairResult:
    result_a: DiscoveryResult
    result_b: DiscoveryResult
    correspondence: list[tuple[int, int, float]]      # (pos_a, pos_b, confidence) for members you claim correspond
    role_alignment: dict                              # {role: {"a": [positions], "b": [positions]}} + role-graph similarity
    budget: dict                                      # {"a": calls, "b": calls, "adaptation": calls, "total": calls}
    diagnostics: dict

def discover_pair(a: DiscoveryProblem, b: DiscoveryProblem, method_name: str, *, budget_a: int, budget_b: int, seed: int,
                  mode: str, config: dict | None = None, workers: int = 1) -> PairResult
```

with modes

| mode | meaning |
|---|---|
| `independent` | base method on A (budget_a) and on B (budget_b), no information shared — the baseline |
| `transfer` | base method on A; B's mechanism = `transfer_core` of A's core with adaptation budget = budget_b (no discovery on B) |
| `prior` | base method on A; then on B with `config["prior"]` built from the correspondence of A's result (budget_b) — does shared structure reduce B's calls? |
| `joint` | your design: discover in both with a shared role structure (goal: reliability on BOTH networks at the same total budget as `independent`); e.g. alternate rounds, share posterior mass across corresponding candidates, penalise role-graph disagreement, stop when both pass |

`discover_pair` must go through `BudgetedSimulator` for every simulation (one simulator per network; adaptation calls
reported separately) and must never exceed `budget_a + budget_b` in total. Provide `python -m brainir.discovery.joint
--pair <instance dir> --method NAME --mode MODE --budget-a B --budget-b B --seed S --out result.json`.

Also deliver `tests/test_joint.py` (deterministic under seed; budgets respected; all four modes run on a tiny pair you
generate; `joint`/`prior` recover both cores on it) and `research/phase2/methods/joint.md` (algorithm, role-alignment
objective, how the prior is formed, adaptation accounting, failure modes, your own pair experiments with commands).

## 3. What is measured (by the hidden-truth scorer, per pair instance, per mode)

success on A, success on B (recall 1 against some sufficient alternative), transfer success (B core hits an
alternative of B), correspondence precision/recall of your claimed pairs vs the truth (identity level, where defined),
role-alignment accuracy (role level, incl. implementation-shift pairs), role-graph similarity a↔b, calls on A / on B /
adaptation / total, calls-to-success on B with and without the prior, and the same for the null transfer.

## 4. Pitfalls to design around

- Anchor decoys: a distractor can look identical to a member in every anchor and annotation; only dynamics tell.
- Implementation shift: no one-to-one member correspondence exists; align roles, not identities.
- Do not turn `transfer` into a full re-discovery on B; do not spend B's budget silently.
- Correspondence scores are ranks, not identities — carry their uncertainty into the prior.
