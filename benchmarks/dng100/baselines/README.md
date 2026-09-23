# DNg100 benchmark — non-BrainIR baselines and null distributions

Reference points for the discovery task of `benchmarks/dng100`: what simple structural heuristics, a statistical
enrichment test, and a simulation-guided pruning search recover when they see exactly what a method sees (the public
bundle, tier A by default) and nothing else. None of them is a BrainIR discovery method.

## Methods (`<name>.py`, one clean-room method each)

All nine follow the contract of `benchmarks/dng100/cleanroom/run_method.py`: they read the bundle named by
`BRAINIR_BUNDLE` / `BRAINIR_NETWORK`, write one `BrainIRMechanismPrediction` (schema 1.0.0) to `BRAINIR_OUT`, are
deterministic under `BRAINIR_SEED`, and import only the standard library, numpy / scipy / pandas / networkx and `brainir`.
Each predicts a core of k interneurons (`role_class == vnc_intrinsic`; k = 3 by default, `--k N` or `BRAINIR_TOPK`), takes
each neuron's role from the network's own `sign` column (positive → excitatory, negative → inhibitory, 0 → unknown),
claims `essential` only where it has a basis (the simulation-based baseline; `None` elsewhere), and records inputs,
seed and compute in `MethodInfo`. The stimulus and readout come from `stimulus.json` / `readout.json`; nothing is
hard-coded. Synapse counts are treated as anatomical estimates used as graph weights, never as physiological strength.

| file | idea | randomness |
|---|---|---|
| `random_matched.py` | k random interneurons within 2 hops downstream of the stimulus, sign composition fixed (2 E + 1 I for k = 3) | seed |
| `degree_topk.py` | most synapses shared with the stimulus (direct targets), ties by weighted degree | none |
| `pagerank.py` | personalized PageRank restarting at the stimulus on the count-weighted directed graph | none |
| `betweenness_stim_to_readout.py` | betweenness restricted to stimulus → readout pairs (edge length 1 / count, ≥ 5 synapses, 3-hop subgraph) | none |
| `kcore_scc.py` | largest SCC reachable from the stimulus → max k-core → weighted in + out degree | none |
| `recurrence_loop.py` | heaviest direct target + its excitatory and inhibitory reciprocal (2-cycle) partners | none |
| `community.py` | Louvain community of the heaviest direct target, ranked by within-community weighted degree | seeded Louvain |
| `statistical_motif.py` | z-scores of stimulus input and reciprocity vs 100 degree-matched endpoint shuffles, rank-normal sum | seed |
| `greedy_prune_sim.py` | `brainir.sim` keep-only backward elimination from the highest-degree 2-hop interneurons (pool expanded until rhythmic), essential = single-neuron silencing in the full network | seeded replicates |

Every module exposes pure helpers (`select_core(neurons, edges, stimulus_ids, readout_ids, k, seed)`, `build_prediction`)
that `tests/test_baselines_contract.py` runs on a 12-neuron synthetic network; the same test checks the clean-room import
rules on the source text. Edges whose `signed_weight` is 0 (unknown presynaptic sign) are legitimate anatomical edges:
graph baselines use `synapse_count`, the simulation uses `signed_weight` (no model effect), and neither depends on the
bundle's edge counts or hashes.

## Driver and nulls (evaluator side)

```
uv run python benchmarks/dng100/baselines/run_all_baselines.py            # run + evaluate all (greedy_prune_sim last)
uv run python benchmarks/dng100/baselines/run_all_baselines.py --summary-only
uv run python benchmarks/dng100/baselines/null_distributions.py --n 500     # structural nulls, no simulation
```

`run_all_baselines.py` calls `cleanroom/run_method.py` and `evaluator/evaluate.py` as subprocesses (defaults:
`--n-replicates 8 --workers 4 --t-end 1.0`, seed 0, bundle `public_blind`) and writes `results/baselines_summary.{json,md}`
(scalar metrics only). `null_distributions.py` imports the evaluator's scoring functions — it is answer-bearing and is
never run by or shown to a method — and writes `results/null_distributions.{json,md}` with, per network and k ∈ {3, 4, 5},
the structural metrics of 500 random interneuron sets (uniform, 2-hop downstream, sign-matched 2-hop) and the empirical
p-value of each baseline against its matched null.

## Results layout (small JSON / MD only; regenerate rather than edit)

- `results/runs/<method>/prediction_<network>.json`, `run_record.json` — method output, hashes of bundle / method / prediction, wall time
- `results/eval/<method>.{json,md}` — frozen-evaluator output: **answer-bearing, never expose to a method**
- `results/baselines_summary.{json,md}`, `results/null_distributions.{json,md}`, `results/run_log.json`

Budget on the development laptop: the structural baselines take seconds to ~15 s per network; `greedy_prune_sim` is
capped at 300 s per network (`--budget-s`); each evaluation with simulation takes about 1–2 min per method.
