<!--
ANSWER-KEY-ADJACENT MATERIAL. This file documents the simulation model and procedures of the published
DNg100 walking-CPG paper. It deliberately does NOT name the interneurons of the published minimal circuits
(those identities are in pugliese_walking_cpg_detailed_notes.md). Like everything under research/literature/,
it must never be used as an input, prior, prompt, feature or training signal for a BrainIR discovery algorithm.
See benchmarks/dng100_walking_cpg/README.md.

Compiled 2026-09-22 by a Claude research agent from a read-only inspection of the authors' repository at commit
10e7661 (see section 1). Every claim carries a file:line reference into that commit. Where the code is
ambiguous the text says so instead of guessing. No wet-lab results are included.
-->

# Pugliese et al. walking-CPG rate model: specification extracted from the authors' code

Companion to `pugliese_walking_cpg_detailed_notes.md` (paper-centred). This document is code-centred: it states,
with file and line references, exactly what the released simulation code computes, so that an independent
implementation can be checked against it line by line. Section 11 lists every disagreement found between the
code, the paper text, and the existing notes.

Conventions

- `authors' repository @ 10e7661` = the public GitHub repository `smpuglie/Pugliese_2026` at the commit given in
  section 1. Paths such as `src/simulation/vnc_sim.py` are relative to its root. `L123` means line 123 of the
  file named in the same sentence.
- `paper` = bioRxiv 10.1101/2025.09.12.675944 v2 (PMC13142387 v2), Methods and Results as converted to text in
  the existing notes' sources.
- `notes` = `pugliese_walking_cpg_detailed_notes.md` in this directory.
- N = number of neurons (4604 for the MANC front-leg network), n_rep = `experiment.n_replicates`.
- "float32": the runner disables 64-bit JAX (`src/run_hydra.py` L21), so every JAX array in a run is float32
  (or bool/int32). Notebook code does not enable x64 either, so JAX defaults to float32 there too.

---

## 1. Provenance

| item | value | source |
|---|---|---|
| repository | `smpuglie/Pugliese_2026` (renamed from `Pugliese_cpg_2025`, which the paper cites) | `git remote -v`; README.md L18; paper "Data and Code Availability" |
| commit | `10e7661bf414ba7b4c2edf795cd36d0f878c17c0` | `git rev-parse HEAD` |
| commit date | 2026-09-15T16:46:54-07:00, message "new revision and readme update" | `git log -1` |
| history | 254 commits; first "basic setup" commit 2025-06-24; simulation core reorganised 2025-09-05 (`8950908`, files moved from `src/*.py` to `src/simulation/`, `src/utils/`) | `git log` |
| licence statement | README.md L215-216: "This project is licensed under the terms of the MIT license."; `pyproject.toml` L10 `license = {text = "MIT"}` and L19 classifier. **No `LICENSE` file exists in the tree.** The README sentence was added in commit `2160352` (2026-09-08). | file listing; `git log -S` |
| data licence | Zenodo record 10.5281/zenodo.22260924 (published 2026-09-15) holds the simulation outputs (`ckpt/*_Rs.npz`, `ckpt/neuron_params.h5`, per-run Hydra configs). Not downloaded for this document. | `zenodo.json` in the scratchpad |
| pinned deps | `environment.yaml` L19-25: `hydra-core>=1.3,<2.0`, `diffrax==0.7.0`, `jax>=0.6.2,<0.10`, `omegaconf>=2.3,<2.4`, `sparse>=0.17.0,<0.19`, `python<3.14` | environment.yaml |

Source files read in full (line counts from `wc -l`):

| file | lines | role |
|---|---|---|
| `src/simulation/vnc_sim.py` | 2038 | ODE, batching, stimulus adjustment, pruning (synchronous engine) |
| `src/simulation/async_vnc_sim.py` | 3335 | "streaming" engine: per-simulation pruning and per-simulation stimulus adjustment |
| `src/utils/sim_utils.py` | 365 | truncated-normal sampler, size scaling, rhythmicity score, loaders, `make_input` |
| `src/utils/shuffle_utils.py` | 91 | class/NT index extraction and weight-matrix shuffle |
| `src/data/data_classes.py` | 103 | `NeuronParams`, `SimParams`, `Pruning_state`, `SimulationConfig`, `CheckpointState` |
| `src/run_hydra.py` | 380 | Hydra entry point, dispatch sync/streaming, saving |
| `src/memory/checkpointing.py`, `src/memory/adaptive_memory.py` | 602, 297 | checkpoint I/O, memory heuristics (no model maths) |
| `src/utils/path_utils.py`, `src/utils/io_dict_to_hdf5.py`, `src/utils/plot_utils.py` | 379, 101, 274 | paths, HDF5, plotting (`get_active_data` L35-36 uses `max(R,1) > 0`) |
| `src/lif_model/lif_dynamics.py` | 58 | LIF control model (Extended Data), not used by the rate simulations |
| `configs/config.yaml`, `configs/sim/*.yaml` (6), `configs/neuron_params/default.yaml`, `configs/experiment/*.yaml` (15), `configs/paths/*.yaml` (5) | 40; 23-28 each; 11; 16-28 each; 7-10 each | Hydra configuration |
| `slurm_run.py`, `test_configs.py`, `setup.py`, `pyproject.toml`, `README.md` | 109, 17, 10, 65, 216 | launcher, packaging, docs |
| notebooks: `Tutorial 1`, `Tutorial 2`, `Figure 1`-`Figure 5`, `Extended Data Figure 1,2,3,4,5,8,9`, `Anipose data figures` | 1536, 1401, 1942, 2072, 4681, 1684, 3459, 2614, 2587, 1096, 253, 1062, 896, 1103, 1116 (JSON lines) | analysis; code and markdown cells extracted with a JSON reader, not executed |

Data files shipped in `data/` (read-only inspection with pandas/numpy):

| directory | files | shape / notes |
|---|---|---|
| `manc t1 connectome data` | `W_20250813_DNtoMN_unsorted.csv`, `wTable_20250813_DNtoMN_unsorted_withModules.csv` | 4604 x 4604; the network used by every MANC experiment config |
| `fanc t1l connectome data` | `W_BDN2toMN_20250107_corrected.npy`, `wTable_BDN2toMN_20250107_corrected.csv` | 803 x 803 |
| `manc t1l minicircuit` | `W_20241118_T1Lminicircuit.npy`, `wTable_...csv` | 123 x 123 (LIF notebook only) |
| `manc full vnc data` | `W_20251006.feather`, `wTable_20251006.feather`, `W_20260522_allSynapses.npz`, `wTable_20260522_allSynapses.feather` | 23532 x 23532 and 23628 x 23628; **not loadable by `load_W`/`load_wTable` at this commit** (section 2.1) |
| `imac t1 connectome data` | `W_20251110.csv`, `W_20260210_vncRoisOnly.csv`, two tables | 4377 and 4310 neurons ("IMAC" = male CNS) |
| `banc t1 premotor` | `W_20251217.npz`, `W_20260217.npz`, several tables | 4956 / 4963 neurons; `.npz` **not loadable by `load_W`** at this commit |

Provenance caveats found while reading

1. The figure notebooks call helpers that do not exist anywhere in `src/` at this commit: `load_Rs_npz`,
   `Rs_npz_info` (Extended Data Figure 2 cells 5, 31; Figure 5 cell 11), `plot_lif_spikes` (Extended Data
   Figure 4 cell 6), the keyword `dataset=` of `plot_R_traces_stacked_by_module` (Figure 2 cell 17), the module
   `feather` (Extended Data Figure 8 cell 4), and `from src.utils.sim_utils import run_LIF_network` (Extended
   Data Figure 4 cell 1; the function lives in `src/lif_model/lif_dynamics.py` L4). The notebooks were therefore
   executed against a different, unreleased revision of `src/`. Their stored outputs are still informative
   (they show array shapes and batch layouts) and are used below with that caveat.
2. No experiment config exists for the mCNS, BANC, full-MANC or FANC-DNb08 runs referenced by the notebooks
   (`DNg100_Stim_IMAC_vncOnly`, `DNg100_Stim_BANC_vncOnly`, `DNg100_Stim_fullManc`, `DNb08_Stim_FANC`,
   `DNb08_Stim_CoreCPG_1/2`, and the `*_Prune_*`/`*_Silence_*` variants). Only the Zenodo run directories hold them.
3. Published run identifiers (SLURM job ids such as 28123286) cannot be mapped to commits from the repository.
   Several relevant code changes are dated between the earliest and latest job ids (section 11, rows 24-26).

---

## 2. Weight-matrix construction

### 2.1 Loading

`load_W(wPath)` (`src/utils/sim_utils.py` L330-341):

- `.npy` -> `jnp.load(wPath)` (L333-334), used as-is.
- `.csv` -> `pd.read_csv(wPath).drop(columns="bodyId_pre").to_numpy().astype(float)` (L335-336).
- any other extension -> `ValueError("Cannot read W file type.")` (L337-338). So `.feather`/`.npz` matrices in
  `data/` cannot be read by this function at this commit.

`load_wTable(dfPath)` (L349-359): `.pkl` -> `pd.read_pickle`; `.csv` -> `pd.read_csv(dfPath, index_col=0)`;
otherwise `ValueError`. The table index is therefore the CSV's first column.

`prepare_neuron_params` then does `W = jnp.array(load_W(cfg.experiment.wPath))` (`vnc_sim.py` L1686). Under
x64-disabled JAX this converts the float64 numpy array to **float32** (integers up to 946 are exact).

Facts established on the MANC file (read-only inspection, 2026-09-22):

- CSV header is `bodyId_pre,0,1,...,4603`; 4604 data rows; the `bodyId_pre` column equals the `bodyId`
  column of the table row by row, and the table index is exactly `0..4603` (a RangeIndex).
- All entries are integers; |w| in {5, ..., 946}; 196,535 nonzero entries (density 0.00927); 103,794
  positive, 92,741 negative; diagonal all zero (no autapses); 148 all-zero rows; 325 all-zero columns.
- Every row has a single sign. Row sign versus `predictedNt`: acetylcholine rows are non-negative (2408 rows
  with outputs, 11 all-zero), gaba rows non-positive (1050 / 27), glutamate rows non-positive (998 / 97),
  `unknown` (9) and `unclear` (4) rows are **all zero**. 3645 columns contain both signs.

### 2.2 Orientation

The file is stored **pre x post**: `W_file[j, i]` = signed synapse count from presynaptic neuron j (row,
`bodyId_pre`) to postsynaptic neuron i (column, positional index). The model transposes it once:

```
reweight_connectivity(W, exc_mult, inh_mult):        # vnc_sim.py L47-53
    Wt    = W.T                                       # L50  -> Wt[i, j] = W_file[j, i]  (post x pre)
    W_exc = max(Wt, 0); W_inh = min(Wt, 0)            # L51-52
    return exc_mult * W_exc + inh_mult * W_inh        # L53
```

and the ODE uses `jnp.dot(weighted_W, R)` (L40), i.e. input to neuron i = sum_j weighted_W[i, j] R_j. So in the
simulation the effective matrix is `b_sign · W_file^T`, indexed [post, pre]. All masking, shuffling and noise
operate on the un-transposed file orientation (rows = pre) before `reweight_connectivity` is applied (L143-144,
L167-168, L213-214).

### 2.3 Sign assignment and thresholding

**Neither is performed in the repository.** The code consumes matrices that are already signed and already
floored; `reweight_connectivity` merely splits the stored sign into the positive and negative parts (L51-52).
The file-level facts above are consistent with the paper's rule (sign of the presynaptic neuron's `predictedNt`;
cholinergic positive, GABAergic and glutamatergic negative) and with the paper's "floor of 5 synapses"
(minimum |w| = 5). Because counts are non-negative, the floor is necessarily on the count magnitude; whether it
was applied per ROI or after summation cannot be determined from the code. `unknown`/`unclear` neurons keep
their rows in the matrix with zero outputs, so they receive input but never emit it; the paper's statement that
neurons without a neurotransmitter prediction were filtered out does not describe these 13 rows. The FANC
`.npy` (803 x 803, |w| in {1, ..., 815}, no floor) is single-signed per row in agreement with its table's `sign`
column (409 negative rows and 382 positive rows with outputs; 12 all-zero rows). The only sign-related
operation in the code is the FANC-style class extraction in `extract_shuffle_indices` (section 9) and the
optional glutamate rescaling below.

### 2.4 Scaling (b)

`SimParams.exc_multiplier = float(cfg.neuron_params.excitatoryMultiplier)` and `inh_multiplier` likewise
(`vnc_sim.py` L1805-1806). `configs/neuron_params/default.yaml` L11-12 sets both to `0.03`. Hence
weighted_W = 0.03 · W_file^T for every experiment that uses the default neuron parameters.

Optional third multiplier (`vnc_sim.py` L1688-1695): if `cfg.neuron_params.glutamateMultiplier` exists,
`gluRatio = glutamateMultiplier / inhibitoryMultiplier` and every **row** of `W` whose table `predictedNt ==
"glutamate"` is multiplied by `gluRatio` before anything else. After `reweight_connectivity` a glutamatergic
weight therefore equals `w · glutamateMultiplier`. No shipped config sets this key; the Extended Data Figure 2
notebook (cells 37-40) reads it from per-run `.hydra/config.yaml` overrides (`neuron_params.excitatoryMultiplier`,
`neuron_params.inhibitoryMultiplier`, `neuron_params.glutamateMultiplier` swept jointly). The scaled `W` is
stored in `NeuronParams.W`, so shuffle, noise and masks all see the rescaled matrix.

### 2.5 Size normalisation

`set_sizes(sizes, a, threshold)` (`sim_utils.py` L73-84):

```
sizes    = copy(sizes)                       # L75
normSize = nanmedian(sizes)                  # L76   median over the rows of the loaded table
sizes[isnan(sizes)] = normSize               # L77
sizes[sizes == 0]   = normSize               # L78
s        = sizes / normSize                  # L79
a        = a / s[None, :]                    # L82   gain divided by relative size
theta    = theta * s[None, :]                # L83   threshold multiplied by relative size
```

Column choice (`vnc_sim.py` L1722-1725): `W_table["size"]` if the table has a `size` column, otherwise
`W_table["surf_area_um2"]`. MANC/mCNS tables have `size` (neuPrint voxel count; MANC median 666,270,409, no
NaN or zero); FANC/BANC tables have `surf_area_um2` (FANC: 2 NaN replaced by the median 4183.823234). The
median is over the **loaded network table**, not the full dataset. Applied after sampling (section 3.3) and
before the input currents are built; `fr_cap` and `tau` are not size-scaled.

### 2.6 Ordering, removal, keepOnly, and what `stimNeurons` indexes

- Row/column order is the file order; nothing is re-sorted (the file name says "unsorted"; the tutorial's
  `wTable.loc[wTable["type"]=="DNg100"]` shows positional indices 31 and 132 for the two DNg100 neurons).
- **`stimNeurons` values are 0-based positional indices into W (= the table's RangeIndex), not bodyIds.**
  `make_input(nNeurons, stimNeurons, stimI)` builds `zeros(N).at[stimNeurons].set(stimI)` (`sim_utils.py`
  L362-365). In the DN screen the indices come from `all_exc_dns.index.to_list()` (`vnc_sim.py` L1902), i.e.
  the same table index. The code relies on the table index being positional; `load_wTable` guarantees this only
  because the shipped CSVs store `0..N-1` in their first column.
- `stimNeurons` is a list of lists; each inner list is one "stimulus configuration" (`vnc_sim.py` L1749-1752).
  `stimI` is a parallel list; when the outer lists differ in length the shorter one is padded with copies of its
  first element (L1735-1746). An inner `stimI` list is assigned element-wise to the inner `stimNeurons` list
  (`.at[idx].set(vals)`), a scalar broadcasts. `input_currents` has shape `(n_stim_configs, n_rep, N)` and is
  initially identical across replicates (`jnp.tile`, L1750).
- **`removeNeurons`** (L1761-1764): `W_mask.at[:, idx, :].set(False)` and `W_mask.at[:, :, idx].set(False)`
  with `idx = jnp.asarray(cfg.experiment.removeNeurons)`; both the row (outputs) and the column (inputs) of every
  listed neuron are masked, in **all** replicates. Nested lists (`[[86, 1167]]`, `[[86],[1167]]`) index the same
  rows and columns, so all listed neurons are removed together; the code does not create one simulation per
  inner list. (Tutorial 1 cell 30 claims otherwise; see section 11 row 20.) Separate silencing conditions were
  produced with Hydra multirun over `experiment.removeNeurons` (Tutorial 2 cell 20; Figure 5 cells 44-51).
- **`keepOnly`** (L1765-1771, only consulted when `removeNeurons` is empty): `keep = zeros(N); keep[keepOnly] =
  True; keep |= isin(arange(N), mn_idxs)`; `W_mask = keep[:, None, :] & keep[:, :, None]`. So the listed
  neurons plus every neuron of class `motor neuron` are kept with all synapses among them (including MN->MN and
  MN->kept-IN synapses); everything else loses all inputs and outputs.
- The mask is applied as `W_masked = W * W_mask` (`vnc_sim.py` L213) inside the "Wmask" simulation type, which
  is selected whenever `prune_network`, `removeNeurons` or `keepOnly` is set (L1821-1822). Masked neurons still
  exist as ODE state variables and still receive any external input `I_i(t)`.

Columns actually read from the table: `predictedNt` (DN-screen filter, shuffle classes, glutamate hack),
`class` (DN screen, shuffle classes, MN set), `size` or `surf_area_um2` (size scaling); FANC/BANC fallbacks read
`sign`, `super_class`, `neurotransmitter_verified`, `neurotransmitter_predicted`; `type`/`cell_type` only for
`dns_by_type` (section 6). The notebooks additionally read `motor module`, `bodyId`, `somaSide`, `type`.

---

## 3. Neuron model

### 3.1 The ODE as coded

`rate_equation_half_tanh(t, R, args)` (`vnc_sim.py` L34-44):

```
inputs, pulse_start, pulse_end, tau, weighted_W, threshold, a, fr_cap, key, noise_stdv = args   # L37
pulse_active = (t >= pulse_start) & (t <= pulse_end)                                            # L38
I            = inputs * pulse_active   # noise term commented out                                # L39
total_input  = I + weighted_W @ R                                                                 # L40
activation   = max(fr_cap * tanh((a / fr_cap) * (total_input - threshold)), 0)                   # L41-43
return (activation - R) / tau                                                                    # L44
```

In mathematical form, for each neuron i:

$$
\tau_i \frac{dr_i}{dt} \;=\; \max\!\Big( r^{\max}_i \tanh\!\big( \tfrac{a_i}{r^{\max}_i}\,[\, I_i(t) + b\sum_j w_{ij} r_j(t) - \theta_i \,]\big),\; 0 \Big) - r_i(t),
\qquad
I_i(t) = \begin{cases} I^{\text{stim}}_i & t_{\text{start}} \le t \le t_{\text{end}} \\ 0 & \text{otherwise}\end{cases}
$$

where $w_{ij}$ is the file entry `W_file[j, i]` (pre j -> post i), $b$ = 0.03 for both signs, $\theta_i$ and
$a_i$ are the size-scaled parameters, and all quantities are float32. The threshold sits inside the `a/r_max`
factor (this matches the paper's Eq. 1 and disagrees with the paper's inline `g(x)` formula; section 11 row 1).
The nonlinearity has zero output for `total_input <= theta`, initial slope `a` at threshold and asymptote
`r_max`. The initial slope claim holds exactly because d/dx[r tanh((a/r)(x-theta))] at x = theta equals a.
No adaptation, delay, or synaptic filtering exists; the only time scale is $\tau_i$.

`key` and `noise_stdv` are passed but unused: the input-noise term is present only as a comment on L39
(commented out in commit `7c4386d`, 2025-09-06). `configs/sim/*.yaml` keys `noiseMean` and `noiseStdv` are
therefore dead (`noiseMean` is never read anywhere in `src/`; `noiseStdv` is carried through `SimParams` and
into `args` but never used).

### 3.2 Per-neuron parameters, sampling, seeds

`prepare_neuron_params` (`vnc_sim.py` L1697-1719):

```
keys = jax.random.split(jax.random.PRNGKey(cfg.experiment.seed), 5)            # L1700-1701
tau       = sample_trunc_normal(keys[0], tauMean,       tauStdv,       (n_rep, N))   # L1703-1706
a         = sample_trunc_normal(keys[1], aMean,         aStdv,         (n_rep, N))   # L1707-1710
threshold = sample_trunc_normal(keys[2], thresholdMean, thresholdStdv, (n_rep, N))   # L1711-1714
fr_cap    = sample_trunc_normal(keys[3], frcapMean,     frcapStdv,     (n_rep, N))   # L1715-1718
seeds     = jax.random.split(keys[4], n_rep)                                          # L1719
a, threshold = set_sizes(size_column, a, threshold)                                   # L1722-1725
```

Defaults (`configs/neuron_params/default.yaml` L3-10): `tauMean 0.02`, `tauStdv 0.002`, `aMean 1`, `aStdv 0.1`,
`thresholdMean 7.5`, `thresholdStdv 0.6`, `frcapMean 200`, `frcapStdv 10`. Every neuron in every replicate gets
its own draw; replicates share nothing but the connectome. Parameters are fixed for the whole simulation
(and for all iterations of a pruning run, since `neuron_params` is only re-created when `prepare_neuron_params`
is called).

`sample_trunc_normal(key, mean, stdev, shape, lower_bound=0.0)` (`sim_utils.py` L14-71), inverse-CDF method:

```
if not finite(mean, stdev, lower_bound) or stdev < 0:  return zeros(shape)             # L58-61, L18-19
if stdev < 1e-10:                                      return max(mean, 0) * ones     # L67, L22-24
upper = min(mean + min(100*stdev, 1e6), 1e10)                                          # L30
za = clip((lower_bound - mean)/stdev, -10, 10);  zb = clip((upper - mean)/stdev, -10, 10)   # L33-34
ca = clip(Phi(za), 1e-10, 1-1e-10);  cb = clip(Phi(zb), 1e-10, 1-1e-10);  cb = max(cb, ca+1e-10)   # L37-43
u  = uniform(key, shape, minval=ca, maxval=cb)                                         # L46   half-open [ca, cb)
z  = Phi^{-1}(clip(u, 1e-10, 1-1e-10))                                                 # L49
return clip(mean + stdev*z, -1e10, 1e10)                                              # L52-53
```

Consequences (checked numerically for the default parameters):

- The standardised bounds are clipped to [-10, 10], so the nominal truncation is `[max(lower, mean-10*sd),
  mean+10*sd]`: tau in [0, 0.04], a in [0, 2], theta in [1.5, 13.5] (the zero bound is 12.5 sd away and is
  replaced by -10 sd), r_max in [100, 300]. "Truncated at zero" (paper) is exact only for tau and a.
- In float32 the CDF clips are ineffective at the upper end (`1-1e-10` rounds to 1.0) and `Phi(-10)` is
  clipped up to `1e-10`, so the realised range of z is about [Phi^-1(1e-10), Phi^-1(1-2^-23)] = [-6.36, +5.2].
  This is a float32 artefact with probability mass around 1e-7 per draw; it matters only for bit-exact
  reproduction.
- One `uniform` call produces the whole `(n_rep, N)` array for a parameter; see section 10 for the consequence.

### 3.3 Initial conditions and input current

- `R0 = zeros(N)` (`vnc_sim.py` L92); the paper's "quiescent network" statement matches.
- `pulse_start = cfg.sim.pulseStart`, `pulse_end = cfg.sim.pulseEnd` (L1802-1803): 0.02 and 1.999 s for
  `sim/default.yaml` (L5-6), 0.02 and 0.999 s for `sim/DN_Screen.yaml` (L5-6) and `sim/Prune_Network*.yaml`
  (L4-5). The step is evaluated at the solver's internal times in float32 (`t >= 0.02` and `t <= pulse_end`).
- Stimulus amplitude per experiment config (`stimI`): `DNg100_Stim*` 250 into index 31; `DNb08_Stim*` 65 into
  index 1211; `DNg100_Stim_FANC*`/`_Silence_FANC`/`_Prune_FANC` 150 into index 0; `DN_Screen*` 128 (starting
  value for auto-tuning); `DNg100_Stim_Sweep` 180-340 into indices [31, 132] simultaneously;
  `DNg100_1000_replicates` 250 into index 25 (file paths in that config do not exist in `data/`).
- The DN itself fires only if `I_stim > theta_i * s_i`; with mean parameters and the MANC `size` ratio of
  index 31 (10.6936) the mean threshold is 80.2 and the mean gain 0.0935, so `250` yields
  `200 tanh(0.0935/200 * 169.8) = 15.8` Hz before recurrent input.

### 3.4 Noise options

- **Weight noise** (`sim.noise: True`, `sim/Noisy_W.yaml` L7-8): `add_noise_to_weights(W, key, stdv_prop)`
  (`vnc_sim.py` L56-60): `noise = sample_trunc_normal(key, mean=0, lower_bound=-1, stdev=stdv_prop,
  shape=W.shape)`; `return W + W*noise`. So each file entry becomes `w(1+eta)` with `eta` truncated-normal,
  `eta >= -1` (a weight can reach 0 but never change sign), upper bound `min(10, 100) sd = 10 sd`
  (float32 caveat above). The key is the replicate's `seeds[param_idx]` (L167, L680); zero entries stay zero.
  Noise is drawn on the raw counts, before transposition and before `b`. `noiseStdvProp = 0` hits the
  `stdev < 1e-10` branch and returns zero noise. The Figure 2 notebook (cell 66) shows the swept values
  0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5 (`sim.noiseStdvProp` overrides).
- **Input noise**: dead code (section 3.1). `sim/Noisy_Input.yaml` (`noiseStdv 0.1`) has no effect on the
  dynamics.
- **Shuffle** (`sim.shuffle: True`): section 9.

### 3.5 Post-processing of every solution

`run_single_simulation` L113-120: `result = solution.ys.T` (shape `(N, len(t_axis))`); `inf -> 0`, `nan -> 0`;
`clip(result, 0.0, 1000.0)`. Rates cannot exceed `r_max <= 300` in exact arithmetic (activation is bounded and
R starts at 0), so the clip acts only on numerical garbage; a solver failure (below) appears as trailing zeros.

---

## 4. Integration

`run_single_simulation` (`vnc_sim.py` L73-122):

| setting | value | line |
|---|---|---|
| library | Diffrax (pinned `diffrax==0.7.0`, `environment.yaml` L20) | L9 imports |
| method | `Dopri5()` (Dormand-Prince 5(4), FSAL) | L94 |
| step control | `PIDController(rtol=r_tol, atol=a_tol)`; all other controller arguments left at Diffrax defaults (proportional/derivative coefficients 0, integral coefficient 1, safety 0.9, factor limits 0.2 and 10, RMS error norm, no dtmin/dtmax) - defaults quoted from Diffrax 0.7 documentation, not overridden in code | L99 |
| tolerances | `rtol = cfg.sim.rtol = 2e-6`, `atol = cfg.sim.atol = 5e-9` in every shipped `sim/*.yaml` (`default.yaml` L19-20); Tutorial 1 loosens them to 1e-4/1e-7 for speed (cell 11) | L1808-1809 |
| interval | `t0 = 0`, `t1 = T`, `dt0 = dt` (initial step 0.001 s) | L104-105 |
| T | `sim.T`: 2.0 s (`default.yaml` L3, `Noisy_*.yaml`), 1.0 s (`DN_Screen.yaml` L3, `Prune_Network*.yaml` L2) | |
| output grid | `SaveAt(ts=t_axis)`, `t_axis = unique(clip(sort(arange(0, T + dt/2, dt, float32)), 0, T))` -> 2001 points for T = 2 and 1001 for T = 1 (`arange` in float32; e.g. `t[20] = 0.020000001`, `t[-2] = 1.9990001`, `t[-1] = 2.0`) | L95; L1790-1796 |
| max steps | `max_steps = 100000`, `throw = False` | L108 |
| failure handling | with `throw=False` a run that exhausts `max_steps` or fails does not raise; Diffrax leaves unreached output points as `inf`, which L117 turns into 0, so such a trace is silently zero after the failure point. `solution.result` is never inspected. The NaN/inf event (L64-70) is defined but disabled (L102, L109). | L108-118 |
| precision | float32 throughout (`run_hydra.py` L21) | |
| parallelism | `vmap` over a batch of simulation indices (L634-731), `pmap` over devices when `jax.device_count() > 1` (L1125-1126); results reshaped to `(n_stim_configs, n_rep, N, len(t_axis))` (L1442-1445) | |

Simulation index mapping (L642-643 and analogous): `param_idx = idx % n_rep`, `stim_idx = idx // n_rep`,
so all replicates of stimulus configuration 0 come first.

### 4.1 Automatic stimulus adjustment ("adjustStimI")

Parameters (`SimulationConfig`, `data_classes.py` L76-81; filled from `cfg.sim` in `vnc_sim.py` L1833-1838):
`max_adjustment_iters = 10`, `n_active_upper` (500 in `sim/default.yaml` L15; **1500** in `sim/DN_Screen.yaml`
L15), `n_active_lower = 5`, `n_high_fr_upper = 100`, `high_fr_threshold = 100.0`. `adjustStimI` is `True` only
in `sim/DN_Screen.yaml` (L13).

**Synchronous engine** (`_adjust_stimulation_for_batch`, `vnc_sim.py` L1143-1232), called once per batch
(L1306-1309) before that batch's final run:

```
next_highest = next_lowest = full(shape=(n_stim, n_rep), NaN)                                  # L1154-1155
for adjust_iter in range(10):                                                                   # L1157
    R_batch    = batch_func(params, sim_params, batch_indices)      # one full simulation per sim  # L1158
    max_rates  = max over time of R                                                              # L1162
    n_active   = number of neurons i with sum_t R_i(t) > 0          # "any positive value"        # L1163
    n_high_fr  = number of neurons with max_rates > 100.0                                        # L1164
    for each sim in batch (stim s, replicate r):                                                 # L1170-1216
        x = input_currents[s, r]                                    # vector over neurons
        if n_active > n_active_upper or n_high_fr > n_high_fr_upper:   # too strong                # L1190
            if isnan(next_lowest[s,r]): x_new = x / 2                                            # L1193-1194
            else: x_new = (x + x.at[x>0].set(next_lowest[s,r])) / 2   # midpoint with the last too-weak value
            next_highest[s,r] = max(x); needs_adjustment[sim] = True                              # L1198-1199
        elif n_active < n_active_lower:                              # too weak                   # L1200
            if isnan(next_highest[s,r]): x_new = x * 2                                           # L1203-1204
            else: x_new = (x + x.at[x>0].set(next_highest[s,r])) / 2                             # L1206-1207
            next_lowest[s,r] = max(x); needs_adjustment[sim] = True                               # L1208-1209
    params = params with input_currents := new_inputs                                            # L1219-1221
    if not any(needs_adjustment): break                                                          # L1226-1228
else: print warning "Maximum adjustment iterations reached"                                     # L1229-1230
return params
```

Definitions, exactly: **underactive** = fewer than 5 neurons with any positive rate anywhere in the saved
trace (whole network, all classes, stimulated DN included); **oversaturated** = more than `n_active_upper`
such neurons **or** more than 100 neurons whose peak rate exceeds 100.0 Hz. The second clause is not in the
paper. Note the criterion is `sum_t R > 0`, not the paper's `> 0.01` "active" definition. The bracketing
values are the maximum stimulated amplitude of the *current* vector (`jnp.max(sim_input)`), so with several
stimulated neurons of different amplitudes only the largest is tracked. When the loop exits by exhausting the
10 iterations, the **last adjustment is applied but never tested**: the final simulation of the batch
(L1381-1420) runs with an input that was not evaluated inside the loop. The code never sets a score to NaN;
the notebooks impose the usability filter afterwards (section 6).

**Streaming engine** (`_run_with_stimulation_adjustment`, `async_vnc_sim.py` L2631-3039): each simulation is
adjusted independently. After each completed run (L2819-2821: same `n_active`/`n_high_fr` definitions) the
simulation is re-queued with `x/2` (too strong, L2848) or `x*2` on the stimulated entries (too weak,
L2853-2857) while `current_iter < 10`, where `current_iter` counts completed runs including the first
(L2823-2837). There is **no midpoint/bisection** in this path, at most 10 runs per simulation, and the stored
result is always that of the last executed run (L2892-2900). `_adjust_stimulation_for_simulations`
(L2193-2283) is defined but never called.

**Which engine produced the published screen.** `sim/DN_Screen.yaml` L25 says `async_mode: "streaming"`
(changed from `"sync"` in commit `edb1851`, 2025-09-07), but the Figure 1 / Extended Data Figure 1-2 notebooks
load the screen results from `ckpt/checkpoints/results_final/Final_batch_Rs_{k}.npz` in batches of 256 with a
last batch of 80 (Extended Data Figure 2 cell 23 output; 933 x 16 = 14,928 = 58 x 256 + 80). Only the
synchronous path writes that layout (`vnc_sim.py` L1385, L1419, `batch_size: 256` in
`configs/experiment/DN_Screen.yaml` L7). The published screen therefore used the synchronous bisection
procedure above, with `async_mode` either overridden or predating the config change.

---

## 5. Rhythmicity ("motor rhythmicity" / "oscillation") score

All in `src/utils/sim_utils.py`. Everything is float32 under JIT.

### 5.1 Inputs and the active-MN mask

Callers pass `activity = R[..., 250:]` and a boolean neuron mask:

- pruning: `max_frs = max_t R[:, clip_start:]`, `active_mask = (max_frs > 0.01) & mn_mask`,
  `compute_oscillation_score(R[..., clip_start:], active_mask, prominence=0.05)` (`vnc_sim.py` L262-265) with
  `clip_start = int(pulse_start/dt) + 230 = 250` for the shipped configs (L1468; `async_vnc_sim.py` L210,
  L340) and `mn_mask = isin(arange(N), mn_idxs)` where `mn_idxs` = table rows with `class == "motor neuron"`
  (`shuffle_utils.py` L60; 144 neurons in MANC). Note `update_single_sim_state`'s own default `clip_start=230`
  (L252) is never used by the callers.
- notebooks: `activeMnsMaskPastTransient = (max(R[:, 250:], 1) > 0.01) & isin(arange(N), mnData.index)`
  with `mnData = wTable.loc[wTable["motor module"].notna()]` (**138** module-labelled MNs in MANC: the 144
  class-MNs minus 6 unlabelled ones, bodyIds 17664, 18483 (MNfl10) and 18006, 18579, 20615, 100515
  (Sternotrochanter MN)); then `compute_oscillation_score(R[..., 250:], mask)` (Figure 2 cell 6 and every
  analogous cell). So the MN set used by pruning-time decisions (144) differs from the one used in notebook
  scores (138).

The window is samples 250..end of the saved grid, i.e. t >= 0.250 s: 1751 samples for T = 2, 751 for T = 1.

### 5.2 Per-neuron raw score and frequency (`neuron_oscillation_score_helper_jax`, L144-229)

```
x = round(x * 1e10) / 1e10; x = clip(x, -1e6, 1e6)                      # L150, L153 (see note A)
rng = max(x) - min(x)
xn  = 2*(x - min(x))/rng - 1   if rng > 1e-6   else zeros               # L156-165  (NOT mean-subtracted)
ac  = correlate(xn, xn, mode="full", method="fft")                       # L168      jax.scipy.signal, length 2n-1
ac  = round(ac*1e10)/1e10; ac = clip(ac, -1e6, 1e6)                     # L171, L174
ac  = ac / max(|ac|)          if max(|ac|) > 1e-6                        # L177-182  -> ac[lag 0] = 1
ac  = ac[(2n-1)//2 :]         # non-negative lags, index k = lag k samples # L185-186
idx, height, prom, is_peak = find_peaks_1d(ac, prominence_threshold=0.05)   # L189-191
valid = is_peak & (idx > 0)                                              # L194
if not any(valid): return (0.0, 0.0)                                     # L197, L226-229
raw   = min( max(height[valid]), max(prom[valid]) )                      # L204-206  (may be two different peaks)
raw   = clip(round(raw*1e10)/1e10, 0, 1e6)                               # L209-212
best  = argmax(prom where valid else -inf)                               # L215
f     = 1 / idx[best]                                                    # L216      cycles per sample
f     = clip(round(f*1e10)/1e10, 1e-6, 1e6)                              # L219-222
return (raw, f)
```

`find_peaks_1d(x, prominence_threshold)` (L87-137):

```
is_peak[i] = x[i] > x[i-1] and x[i] > x[i+1]   for 1 <= i <= n-2  (strict; endpoints never peaks)   # L96-99
left_valley[i]  = min(x[0..i-1])   (inf for i = 0)                                                  # L109, L115
right_valley[i] = min(x[i+1..n-1]) (inf for i = n-1)                                                # L112, L116
prominence[i]   = x[i] - max(left_valley[i], right_valley[i])   for interior i, else 0             # L119-126
is_peak &= prominence >= prominence_threshold                                                       # L129
```

This prominence is "height above the higher of the two global side minima", not SciPy's window-bounded
prominence; for an autocorrelation that starts at 1 and whose first peak follows the deepest trough the two
agree, but they differ in general. Note A: `round(x*1e10)/1e10` does not achieve 10-decimal rounding in
float32 for O(1) values (the product 1e10 has spacing 1024 in float32); it perturbs values at the ulp level.
The 1e-6 rounding of the final score (below) is the only effective rounding.

### 5.3 Normalised per-neuron score (`neuron_oscillation_score`, L231-273)

```
raw, f = helper(x, prominence)
if raw > 1e-6 and isfinite(f):                                           # L259-263
    t        = arange(n, dtype=float32)                                  # n = len(x)
    ref_s, _ = helper(sin(2*pi*f*t), prominence)                         # L243, L246
    ref_c, _ = helper(cos(2*pi*f*t), prominence)                         # L244, L247
    ref      = max(ref_s, ref_c)                                         # L249
    score    = raw/ref  if ref > 1e-6  else 0                            # L252-256
else: score = 0
score = clip(round(score*1e6)/1e6, 0, 1)                                 # L268-271
return score, f                                                          # f is the raw-trace frequency, cycles/sample
```

### 5.4 Simulation score and mean frequency (`compute_oscillation_score`, L274-311)

```
scores, freqs = vmap(neuron_oscillation_score)(activity, prominence)     # every neuron, L279-282
scores = where(mask, scores, 0);  freqs = where(mask, freqs, nan)         # L285-286
n_act  = sum(mask)                                                        # L289
sim_score = sum(scores*mask)/n_act   if n_act > 0 else 0.0                # L293-301   plain mean over active MNs
mean_freq = nanmean(where(isinf(freqs) | freqs == 0, nan, freqs)) if n_act > 0 else 0.0    # L303-309
```

So a simulation with no active MN scores exactly 0 (not NaN); an active MN with no valid autocorrelation peak
contributes 0 to the mean; frequencies are averaged only over active MNs with a detected peak. Frequency is in
cycles per sample; notebooks convert with `mnFreq / overallParams.sim.dt` (Figure 2 cell 74), i.e. Hz =
1000 / (peak lag in ms) on the 1 ms grid, so resolvable frequencies are 1000/k Hz for integer k.

### 5.5 Threshold and "rhythmic"

- Pruning acceptance: `oscillation_score >= oscillation_threshold` (`vnc_sim.py` L284, L307) with
  `oscillation_threshold = cfg.experiment.oscillation_threshold = 0.5` in every experiment config
  (`parse_simulation_config` L1830; `SimulationConfig` default 0.5, `data_classes.py` L72).
- Screen reporting: notebooks count DNs with mean score `>= 0.5` (Figure 1 cell 27 `sum(mean>=0.5)`) and
  best-replicate `>= 0.5` (Extended Data Figure 1 cell 12); the paper text says "> 0.5".
- No frequency-band criterion is applied anywhere in the simulation code.

### 5.6 Re-implementation pseudo-code (single trace, values that should reproduce the code)

```
def rhythmicity(x_float32, dt=0.001, prominence=0.05):
    # x: trace samples from t = 0.250 s to the end of the saved grid (inclusive), float32
    raw, f = helper(x)                    # sections 5.2
    if raw <= 1e-6 or not finite(f): return 0.0, f
    n = len(x); t = arange(n, float32)
    ref = max(helper(sin(2*pi*f*t))[0], helper(cos(2*pi*f*t))[0])
    s = raw/ref if ref > 1e-6 else 0.0
    return clip(round(s*1e6)/1e6, 0, 1), f      # f in cycles/sample; Hz = f/dt
```

Bit-exact agreement additionally requires float32 arithmetic and the same FFT-based correlation as
`jax.scipy.signal.correlate(method="fft")`; a direct-summation correlation in float64 will differ at the
1e-6 level before the final rounding and can change the 6th decimal.

---

## 6. DN screen

Configuration: `configs/experiment/DN_Screen.yaml` (`dn_screen: True` L8, `n_replicates: 16` L6,
`batch_size: 256` L7, `stimNeurons: [[31]]` L9-10 (placeholder, replaced), `stimI: [[128]]` L14-15, `seed: 1`
L16) with `configs/sim/DN_Screen.yaml` (T = 1.0, pulse 0.02-0.999, `adjustStimI: True`, `n_active_upper 1500`,
`n_active_lower 5`, `n_high_fr_upper 100`, `high_fr_threshold 100.0`).

### 6.1 Candidate selection (`prepare_vnc_simulation_params`, `vnc_sim.py` L1878-1911)

```
try:  all_exc_dns = W_table[(class == "descending neuron") & (predictedNt == "acetylcholine")]      # L1880-1883
except: all_exc_dns = W_table[(super_class == "descending") &
          ((neurotransmitter_verified == "acetylcholine") |
           (neurotransmitter_verified.isna() & neurotransmitter_predicted == "acetylcholine"))]      # L1885-1889 (BANC-style tables)
if cfg.sim.dns_by_type:  stim_neurons = [rows of each non-NaN type (or cell_type)]                     # L1891-1900
else:                    stim_neurons = [[i] for i in all_exc_dns.index]                               # L1902
if cfg.sim.max_dn_test:  stim_neurons = stim_neurons[:max_dn_test]                                     # L1890, L1904-1907
stim_inputs = [cfg.experiment.stimI[0]] * len(stim_neurons)                                            # L1909
cfg.experiment.stimNeurons, cfg.experiment.stimI = stim_neurons, stim_inputs                           # L1910-1911
```

For the MANC table this yields 933 single-neuron stimulus configurations (rows with `class == "descending
neuron"` and `predictedNt == "acetylcholine"`), or 321 type groups when `dns_by_type` is set (checked on the
shipped table; matches the paper's 933 and 321). Each stimulated neuron receives 128 initially; in a type
group every member receives 128. `max_dn_test` and `dns_by_type` are read from `cfg.sim`, so
`configs/experiment/DN_Screen_Test.yaml` L15 (`max_dn_test` under `experiment`) has no effect. `run_hydra.py`
saves `run_config.yaml` before the substitution (L234-236), so the saved config still shows `[[31]]`; the
933 x 16 x N `input_currents` array in `ckpt/neuron_params.h5` (L350) is what the notebooks use to recover
which neuron each configuration stimulated (`np.where(inputs[nrnNo].sum(0) > 0)`, Figure 1 cell 8).

### 6.2 Replicates and tuning

16 replicates per run x 8 runs with different SLURM job ids = 128 (Figure 1 cells 0 and 10; the seed of
each run is in its Zenodo config, not in the repository). Total sims per run 933 x 16 = 14,928, processed in
59 synchronous batches of 256 with the bisection auto-tuning of section 4.1, then re-simulated with the tuned
inputs and saved per batch (`Final_batch_Rs_{k}.npz`). The `_Rs.npz` aggregate is not written for screens
(`run_hydra.py` L348-349).

### 6.3 Per-replicate criterion and aggregation (notebooks; Figure 1 cells 8-33, Extended Data Figure 1)

```
for each final trace R (N x 1001):
    nActive = number of neurons with max_t R > 0.01                       # whole 1 s, all neurons
    score   = compute_oscillation_score(R[:, 250:], (max R[:,250:] > 0.01) & moduleMN)
usable[dn, rep] = 5 <= nActive <= 1500   else NaN                          # cell 12 (notebook-side; the code never writes NaN)
mean[dn] = nanmean over 128 replicates                                     # cell 14
"rhythmic" DN: mean >= 0.5 (cell 27); Supplementary Table 1 = DNs sorted by mean, cut at mean > 0.5
also reported: number of DNs with >= 50 usable replicates (cell 20), median/IQR and 95th percentile
(ED Fig 1 cells 8-9), best replicate >= 0.5 (ED Fig 1 cells 11-14)
```

The type-level screen (ED Figure 1 cells 19-37) uses the same filter with `nActive < 5` (the paper's "lower
bound of 10" for that screen is not visible in code or notebook). The combinatorial (Dirichlet) screen of the
paper has no code in the repository.

---

## 7. Pruning ("computational sufficiency screen")

Configuration: `configs/experiment/DNg100_Stim_Prune.yaml` (`n_replicates 1024`, `stimNeurons [[31]]`, `stimI
[[250]]`, `seed 1`, `max_pruning_iterations 200`, `oscillation_threshold 0.5`) or `DNb08_Stim_Prune.yaml`
(`[[1211]]`, `[[65]]`, `max_pruning_iterations 250`), combined with `sim/Prune_Network.yaml` (sync) or
`sim/Prune_Network_Async.yaml` (streaming): T = 1.0, pulse 0.02-0.999, `prune_network: True`. The experiment
configs do not name a `sim` config; the launcher passes `sim=<name>` (`slurm_run.py` L47). Both engines call the
same `update_single_sim_state`; differences are listed in 7.4.

### 7.1 State and initialisation (`initialize_pruning_state`, `vnc_sim.py` L1019-1085; streaming analogue `async_vnc_sim.py` L97-156)

- `interneuron_mask` = every neuron not in `mn_idxs` (`class == "motor neuron"`), L1026-1032. **All
  non-MN neurons are prunable, including every descending neuron (the stimulated one too), sensory and
  ascending neurons, glia and the 4 "neck motor neuron" rows.** MNs are never eligible (probability 0).
- `W_mask` starts all-True (L1030): **any `removeNeurons`/`keepOnly` mask built in `prepare_neuron_params` is
  discarded in pruning mode.**
- `total_removed_neurons`, `removed_stim_neurons` ("removed by draw"), `neurons_put_back`, `prev_put_back`,
  `last_removed` all False; `level = 0`; `min_circuit = False`; `last_good_oscillation_score = -1.0`;
  `last_good_W_mask` zeros (L1033-1044, L1081).
- RNG key: sync `keys = seeds[:batch_size]` (L1051, position in batch, **not** replicate index); streaming
  `keys = seeds[sim_index]` (`async_vnc_sim.py` L131-135).

### 7.2 One iteration (`update_single_sim_state`, `vnc_sim.py` L252-492), given the simulation `R` run with the state's `W_mask`

```
max_frs  = max_t R[:, 250:]                                                  # L262
active   = (max_frs > 0.01) & mn_mask                                        # L263
score, _ = compute_oscillation_score(R[:, 250:], active, prominence=0.05)    # L265

# candidates and "new round" test (before any change)
excl     = ~interneuron | total_removed | put_back                           # L268
p_cur    = removal_probability(max_frs, excl)                                # L270  (below)
need_new_round = sum(~excl) <= 0 or not finite(sum(p_cur))                   # L274
converged = need_new_round and (put_back == prev_put_back) and
            (level > 0 or any(put_back) or any(total_removed))   or min_circuit   # L279-281

good = score >= 0.5 and finite(score)                                        # L284
if good: last_good_{removed, put_back, score, W_mask, key} := current values # L294-298
key, k_cont, k_reset = split(key, 3)                                         # L304
reset = score < 0.5 or isnan(score)                                          # L307

# ACCEPT branch (score >= 0.5): the previous removal stands
newly_silent = interneuron & (max_frs <= 0) & ~total_removed                 # L313-314   (max over t >= 250 ms, <= 0 not <= 0.01)
removed_c    = total_removed | newly_silent                                  # L315
p_c          = removal_probability(max_frs, ~interneuron | removed_c | put_back)      # L318-319
new_round_c  = need_new_round or no candidates left                          # L324
j            = categorical(k_cont, log(p_c + 1e-10))                         # L327
if not new_round_c: removed_c[j] = True; removed_by_draw[j] = True           # L330-339
last_removed_c = newly_silent (+ j if drawn)                                 # L342-347
if new_round_c: put_back := empty; prev_put_back := put_back; level += 1     # L350-360

# REJECT branch (score < 0.5): restore the last drawn neuron(s), draw another
restore      = last_removed & removed_by_draw       # silent-pruned neurons are NOT restored   # L364
removed_r    = total_removed & ~restore; removed_by_draw &= ~restore         # L367-368
put_back_r   = put_back | restore                                            # L371
p_r          = removal_probability(max_frs, ~interneuron | removed_r | put_back_r)    # L374-375  (max_frs from the FAILED simulation)
new_round_r  = no candidates left                                            # L380
j            = categorical(k_reset, log(p_r + 1e-10))                        # L383
if not new_round_r: removed_r[j] = True; removed_by_draw[j] = True; last_removed_r = {j}   # L386-402
if new_round_r: put_back_r := empty; prev_put_back := put_back; level += 1   # L405-415

state := reset ? REJECT values : ACCEPT values                               # L418-424
active_neurons = ~removed | put_back;  W_mask = outer(active_neurons, active_neurons)   # L428-429

# convergence override
if converged and last_good_score >= 0.5:  removed, put_back, W_mask := last_good values (W_mask rebuilt as outer product)   # L433-454
elif converged:                            keep the pre-update state (no change)
min_circuit := converged                                                     # L483
```

`removal_probability(max_frs, exclude)` (L228-239): `tmp = 1/where(max_frs > 0, max_frs, 1)` (silent neurons
weight 1), `tmp[~finite] = 0`, `tmp[exclude] = 0`, `p = tmp/sum(tmp)` (0 if the sum is 0). `jax_choice`
(L242-250) draws `random.categorical(key, log(p + 1e-10))`, so every excluded neuron (MNs included) retains a
relative weight of 1e-10 and can in principle be drawn (expected fewer than 0.1 such events per 1024-replicate
screen; not zero).

Reading of the procedure: at each accepted step one interneuron is removed **and** every interneuron that was
silent in the accepted simulation is removed for good; a rejected step restores only the drawn neuron, adds it
to the round's `put_back` set, and immediately draws another neuron using rates from the failed simulation. A
"round" (`level`) ends when no interneuron remains that is neither removed nor already put back in this round.
**Convergence** = a round ends **and** its `put_back` set equals the previous round's `put_back` set (and at
least one round or one removal has happened). On convergence the state reverts to the most recent
accepted (score >= 0.5) configuration. The paper's description ("terminated when none of the remaining cells
could be pruned") corresponds to two consecutive identical rounds in the code.

Also: the "first, all inactive neurons were pruned" statement (paper) is realised only as part of the first
**accepted** iteration; if the intact network scores below 0.5 the first iteration takes the reject branch
(nothing to restore) and no silent neuron is pruned in that iteration. The rhythmicity score at every step is
computed over `class == "motor neuron"` neurons (144 in MANC), the same set that is protected from pruning.

### 7.3 Loop, cap, final simulation, reporting

**Synchronous** (`_run_with_pruning`, `vnc_sim.py` L1448-1652): all replicates of a batch iterate in lockstep
(`while True`: break when `all(min_circuit)` or `iteration >= max_pruning_iterations`, L1532-1537; each
iteration = one simulation per replicate, L1556, then `batch_update`, L1562). After the loop, for each
replicate: `final_removed/put_back = last_good_* if last_good_score >= 0.5 else current` (L1593-1599);
`mini_circuit = ~final_removed | final_put_back` (L1600, **structural**: includes all MNs and every kept
neuron whether or not it fires); `W_mask = outer(mini_circuit)` (L1604); one more simulation (L1610) whose
rates are the saved `_Rs.npz`; `mini_circuit` is saved as `_mini_circuits.npz` (`run_hydra.py` L351-352).

**Streaming** (`_process_single_simulation`, `async_vnc_sim.py` L662-1035): per simulation, `while iteration
< max_pruning_iterations` (L759), break when `min_circuit` (L762-767); each iteration runs
`_run_single_pruning_iteration_with_tolerances` with the current `W_mask` (L787-796) and applies the same
update (L804-808). Afterwards `final_W_mask = last_good_W_mask` if `last_good_score > 0` else the current
`W_mask` (L860-884); one final simulation with that mask (L934-945) and its score is logged (L953-963);
**`mini_circuit = max_t R_final > 0.01` over the full 0-1 s trace for all neurons** (L998-1000, **activity
based**, includes the stimulated DN and active MNs, excludes kept-but-silent neurons); `final_W_mask` is
written into `NeuronParams.W_mask` (L1797) and thus into `ckpt/neuron_params.h5`.

**Notebook aggregation** (Figure 3 cells 6-12, Figure 5 cells 23-28, ED Figure 5 cells 16-23): load
`_mini_circuits.npz`, set the stimulated DN's column and all **module-labelled** MN columns to False, count
remaining True entries per replicate ("# interneurons"), list distinct sets with >= 10 occurrences, and report
per-neuron prevalence. Non-converged replicates are not removed; the figure captions exclude ">15
interneurons" from histograms. Because only module-labelled MNs are dropped, the six unlabelled class-MNs of
MANC would appear in **every** reported set under the synchronous structural output; the published
Supplementary Table 3 modal set contains none of them, whereas MNfl10 (17664) appears in some sets. This is
what the streaming, activity-based `mini_circuit` produces (an unlabelled MN appears only when it fired in the
final simulation). The published pruning outputs are therefore consistent with the streaming engine and with
MNs defined by `class`; they are inconsistent with the synchronous engine's structural output. (The notes'
hypothesis of a `motor module`-based MN definition in archived code is an alternative explanation that the
repository does not allow one to exclude; a `git log -S'motor module'` search restricted to `vnc_sim.py`,
`async_vnc_sim.py`, `sim_utils.py` and `shuffle_utils.py` (both their old top-level and current locations)
finds no such definition at any commit; the only hits are the deleted `src/Archive/*` files.)

### 7.4 Sync versus streaming differences that affect results

| aspect | synchronous (`vnc_sim.py`) | streaming (`async_vnc_sim.py`) |
|---|---|---|
| RNG key of replicate r | `seeds[position in batch]` (L1051), so depends on hardware-chosen batch size | `seeds[sim_index]` (L131-135) |
| final mask | rebuilt as outer product of `~removed \| put_back` (L1600-1604) | exact `last_good_W_mask` (L883) |
| reported circuit | structural membership (L1600) | neurons with peak rate > 0.01 in the final rerun (L1000) |
| fallback when no state ever scored >= 0.5 | current state (L1593-1599) | current `W_mask` (L874) |
| batch lockstep | yes; `max_pruning_iterations` counts lockstep iterations | per simulation |

---

## 8. Silencing / perturbation experiments

- **Mechanism**: `W_mask` zeroing of the neuron's row and column (section 2.6), applied as `W * W_mask`
  before `reweight_connectivity` (`vnc_sim.py` L213-214; `async_vnc_sim.py` L2059-2072). The neuron is not
  deleted: it keeps its ODE state and parameters (so the parameter draws and RNG stream of a silencing run are
  identical to the intact run with the same seed and `n_replicates`), and it would still receive external input
  if it were in `stimNeurons`. "Silenced", "removed" and "pruned" all denote this same operation; the paper's
  "silencing" is exactly `removeNeurons`.
- **Configs**: `DNg100_Stim_Silence.yaml` and `DNb08_Stim_Silence.yaml` ship with `removeNeurons: []`; the
  silenced index is supplied per run (`experiment.removeNeurons=[...]`), e.g. Hydra multirun subfolders
  `experiment.removeNeurons=[617]`, `[693]`, `[4458]`, `[86]` in Figure 5 cells 44-51, and
  `[481]`, `[413]`, `[503]`, `[525]` with `experiment.seed=159` for FANC in Figure 3 cells 79-87. Two-seed
  batches were combined for mCNS/BANC (Figure 3 cells 95, 106). `DNg100_Stim_CoreCPG.yaml` L13 uses `keepOnly`
  with four indices and `n_replicates 512`, run as a multirun over seeds and concatenated (Figure 3 cell 45).
- **Type resolution**: `sim_type` is `"shuffle"` if `sim.shuffle`, else `"noise"` if `sim.noise`, else
  `"Wmask"` if pruning or any `removeNeurons`/`keepOnly`, else `"baseline"` (L1816-1822). In the synchronous
  engine the "noise" and "shuffle" batch functions ignore `W_mask` (L659-708), so `removeNeurons` combined with
  `sim.noise` has no effect there; the streaming engine applies the mask before noise or shuffle
  (`async_vnc_sim.py` L1980-1994, L2023-2032).
- **Memory shape**: `W_mask` is `(n_rep, N, N)` bool (L1760); the streaming regular engine indexes it by the
  global `sim_index`, not `param_idx` (`async_vnc_sim.py` L2114-2115), which is only correct for a single
  stimulus configuration.
- Analysis of silencing runs recomputes scores exactly as in section 5.1 (notebooks), with no additional
  statistics beyond histograms of scores and of active-MN counts.

---

## 9. Shuffle controls (`src/utils/shuffle_utils.py`)

### 9.1 Simulation-time shuffle (`sim.shuffle: True`)

```
extract_shuffle_indices(W_table):                                   # L32-91
  if "predictedNt" in columns:                                      # MANC/mCNS tables
     exc_dn = class == "descending neuron" & predictedNt == "acetylcholine"      # L36-41
     inh_dn = class == "descending neuron" & ~(predictedNt == "acetylcholine")   # L42-47  (gaba, glutamate, unknown, unclear, NaN)
     exc_in = class not in {descending neuron, motor neuron} & predictedNt == ACh        # L48-53
     inh_in = class not in {descending neuron, motor neuron} & ~(predictedNt == ACh)     # L54-59
     mn     = class == "motor neuron"                                                     # L60
  elif "sign" in columns:                                           # FANC table
     exc_dn/inh_dn by class == "descending neuron" & sign == +1/-1  # L62-73
     exc_in/inh_in by class == "intrinsic neuron"  & sign == +1/-1  # L74-85   (other classes fall in no group)
     mn = class == "motor neuron"                                   # L86
  else: all five index arrays empty (prints "No valid indices found")   # L87-89

shuffle_W(W, key, idxs):  W.at[:, idxs].set(random.permutation(key, W[:, idxs], axis=1, independent=False))   # L6-10
full_shuffle(W, base_key, exc_dn, inh_dn, exc_in, inh_in, mn):                                              # L13-29
  keys = split(base_key, 5); apply shuffle_W to the five groups in that order with keys[0..4]
```

Semantics: `W[:, idxs]` is the sub-matrix (all presynaptic rows) x (postsynaptic columns in the group);
`permutation(..., axis=1, independent=False)` permutes those **columns as whole units**. So within each of the
five postsynaptic classes the complete input vectors are reassigned among the class members. Preserved
exactly: every entry's sign (rows are untouched and single-signed), every presynaptic neuron's multiset of
outputs to each class (row sums per class, out-degree), the multiset of input vectors of each class (hence
each class's in-degree and in-strength distribution and within-vector correlations), and the class
membership of every neuron. Destroyed: which specific postsynaptic neuron of a class receives a given input
vector (e.g. a recurrent pair's reciprocity). The shuffle is drawn per replicate from `seeds[param_idx]`
(`vnc_sim.py` L680; `async_vnc_sim.py` L1994) on the un-transposed, un-reweighted matrix (L143-144). In the
synchronous engine `W_mask` is not applied in this mode. No shipped experiment or notebook uses `sim.shuffle`.

### 9.2 Analysis-time shuffle (motif null model, Figure 3 cells 50-56; not in `src/`)

`wIN = W[intrinsic][:, intrinsic]` (rows = pre); for each of 100 seeds (`np.random.seed(11)`, then
`np.random.randint(0, 100000, 100)`), `np.random.seed(seed)` and `np.random.shuffle(row)` for every row
independently. This permutes each intrinsic neuron's outgoing weights among intrinsic targets, preserving each
row's multiset (out-degree, out-strength, sign) and nothing about columns. Motif counting
(`find_minicircuit_motifs`) classifies neurons as excitatory if all their outputs are >= 0 and inhibitory if
any output is < 0; the linearised frequency estimate uses `alpha = dt/tau` with `dt_s = 1e-3`, `tau = 20e-3`,
gain `0.75 * 0.03 * median_size/size` per neuron (cell 55).

---

## 10. Randomness

| RNG | derivation | consumer | reproducible? |
|---|---|---|---|
| `PRNGKey(experiment.seed)` | `seed: 1` in all main configs; other seeds appear in multirun folder names (e.g. 159, 732, 545, 61, 805, 102, 207, 81) | root | yes given seed |
| `keys[0..3] = split(root, 5)[0..3]` | one `uniform` draw of shape `(n_rep, N)` per parameter (`sim_utils.py` L46) | tau, a, theta, r_max | replicate r's draw is element `[r, :]` of that array; whether it is independent of `n_rep` depends on JAX's threefry mode (partitionable threefry, the default since JAX 0.5, derives each element from its flat index r·N+i and the key; the JAX version used for the published runs is not recorded) |
| `seeds = split(keys[4], n_rep)` | one key per replicate | weight noise (`add_noise_to_weights`), shuffle (`full_shuffle`, split 5), ODE `key` argument (unused), streaming pruning key, sync pruning key by batch position | as above; the sync pruning key additionally depends on the hardware-dependent `batch_size` (section 7.4) |
| pruning key evolution | `key, k_cont, k_reset = split(key, 3)` each iteration (`vnc_sim.py` L304); on convergence the key is frozen (L462) | `categorical` draws | yes given the initial key and the exact sequence of scores |
| notebook RNGs | `np.random.seed(11)` (motif shuffles), `np.random.default_rng(31668)`/`(86572)` (phase-offset shuffles, Figure 4 cell 35, ED Figure 8 cell 11) | analysis only | yes |

Sources of irreproducibility even with identical seeds: float32 GPU arithmetic in the `N x N` matrix-vector
products and FFT correlations (results depend on device, batch composition under `vmap`/`pmap`, and XLA
version); the adaptive step sequence of Dopri5, which amplifies any bit-level difference; the pruning draw,
which depends on every previous score through `>= 0.5` comparisons, so a single flipped comparison changes the
whole trajectory; `calculate_optimal_batch_size` (L753-1016) choosing batch sizes from detected memory. The
authors' own comments acknowledge device-dependent differences (`vnc_sim.py` L97-98; commit message of
`7c4386d`: "Small differences due to pid step?"). Exact reproduction of published per-replicate numbers is
therefore not expected; distributional reproduction is the realistic target.

---

## 11. Discrepancies

Legend: P = paper text (v2), C = code at 10e7661, N = existing notes, T = tutorial/notebook text.

| # | topic | what P / N / T say | what C does | refs |
|---|---|---|---|---|
| 1 | inline nonlinearity formula | P Methods: `g(x) = max(r tanh((a/r) x - theta), 0)` (theta outside) | theta inside: `tanh((a/r)(x - theta))` = Eq. 1 | `vnc_sim.py` L41-43; N already flags |
| 2 | trace normalisation | P: `2 (r - min r)/max r - 1` | `2 (r - min)/(max - min) - 1`, and zeros when range <= 1e-6 | `sim_utils.py` L156-165; N already flags |
| 3 | "truncated at zero" | P | truncation at `max(0, mean - 10 sd)` and `mean + 10 sd`; theta effectively truncated at 1.5, r_max at 100; float32 narrows this to about [-6.4, +5.2] sd | `sim_utils.py` L30-49 |
| 4 | pruning threshold | P Results "> 0.5", P Methods ">= 0.5" | `>=` | `vnc_sim.py` L284, L307 |
| 5 | "active"/"recruited" | P: rate > 0.01 Hz at any time | score masks use `> 0.01` after 250 ms; the stimulus tuner uses `sum_t R > 0`; silent-pruning uses `max <= 0`; `plot_utils.get_active_data` uses `max > 0` | L263, L1163, L313; `plot_utils.py` L36 |
| 6 | screen saturation rule | P: > 1500 recruited neurons | additionally > 100 neurons with peak > 100 Hz; starting amplitude 128 | L1190, `DN_Screen.yaml` L14-18; N flags |
| 7 | screen failure -> NaN | P: after 10 tuning iterations the score "was not computed (set to NaN)" | code never writes NaN; the last (untested) adjustment is simulated and saved; notebooks NaN-out replicates with `nActive < 5` or `> 1500` computed with `> 0.01`, not with the tuner's `> 0` | L1219-1230, L1381-1420; Figure 1 cell 12 |
| 8 | screen midpoint rule | P: doubled/halved "or set to the midpoint" | true only for the synchronous engine; the streaming engine only halves/doubles; file layout shows the synchronous engine was used although `DN_Screen.yaml` L25 says streaming | section 4.1 |
| 9 | type-level screen lower bound | P: raised to 10 active neurons | no config or notebook shows this (`n_active_lower 5`; ED Fig 1 cell 27 filters at 5) | `DN_Screen.yaml` L16 |
| 10 | `n_active_upper` | task query "500 vs 1500"; P v1 500, P v2 1500 (per N) | `sim/default.yaml` L15 = 500 (irrelevant unless `adjustStimI`), `sim/DN_Screen.yaml` L15 = 1500 (changed from 500 in commit `6cfd0bc`, 2025-08-19) | configs |
| 11 | simulation length | P: 1 s for screen and pruning; nothing about activation runs | main activation/silencing/noise runs use T = 2 s, pulse 0.02-1.999 s (saved shape 2001 points); screens/pruning T = 1 s, pulse 0.02-0.999 s | `sim/default.yaml` L3-6; N flags |
| 12 | pulse end | P: onset at 20 ms only | pulse ends 1 ms before T; in float32 the grid point 1.9990001 tests as after `pulse_end` | L38; section 4 |
| 13 | first pruning step | P: "First, all neurons that were not active were pruned" | silent interneurons are pruned only in accepted iterations (score >= 0.5), with `max <= 0`, never in a rejected iteration | L313-315 |
| 14 | removal probability source | P: "inversely proportional to its maximum rate at the last iteration" | in a rejected step the probabilities come from the failed simulation (with the restored neuron absent); silent-but-unremoved neurons weigh 1 | L374-375, L231 |
| 15 | stopping rule | P: no remaining neuron removable | two consecutive rounds with identical put-back sets, plus a hard cap of 200 (250 DNb08) simulations; non-converged replicates are reported | L279-281, L1536; `DNb08_Stim_Prune.yaml` L20 |
| 16 | what is protected from pruning | P: "leg motor neurons were not considered" | `class == "motor neuron"` only; DNs (including the stimulated one), neck MNs, sensory and ascending neurons are prunable; MNs retain a 1e-10 draw weight | L1026-1032, L250 |
| 17 | reported minimal circuit | P: "remaining cells in the network" | sync: structural set; streaming: neurons with peak rate > 0.01 in the final rerun; notebooks drop DN and module-MN columns; evidence favours streaming (section 7.3) | L1600 vs `async_vnc_sim.py` L1000 |
| 18 | MNfl10 in Supp. Table 3/7 | N: implies a `motor module` MN definition in archived code | also explained by activity-based reporting with `class`-based MNs; the sync structural output is excluded by the published tables | section 7.3 |
| 19 | MN set for scores | P: "all active motor neurons" | pruning-time: 144 class-MNs; notebook scores: 138 module-labelled MNs | section 5.1 |
| 20 | `removeNeurons` list nesting | T (Tutorial 1 cell 30): `[86, 1167]` or `[[86],[1167]]` "would specify two simulations" | all listed neurons are removed in all replicates regardless of nesting; separate conditions require multirun | L1761-1763 |
| 21 | weight-noise truncation | P: truncated so the sign cannot change | `eta >= -1` (weight may become exactly 0), upper bound 10 sd (float32 ~5 sd) | L56-60, `sim_utils.py` L30-34 |
| 22 | input noise | configs `noiseMean`, `noiseStdv`, `sim/Noisy_Input.yaml` | never used in the dynamics (term commented out since `7c4386d`) | L39 |
| 23 | `b` | P: b = 0.03 | `excitatoryMultiplier = inhibitoryMultiplier = 0.03`; optional `glutamateMultiplier` row scaling | `neuron_params/default.yaml` L11-12; L1688-1695 |
| 24 | engine used for pruning | not stated | undeterminable from repo; configs for both engines exist; `Prune_Network_Async.yaml` (streaming) is consistent with the published tables (section 7.3) | |
| 25 | code version of published runs | not stated | job ids span a period with relevant commits (noise term removed 2025-09-06; pruning convergence rewritten 2025-09-05/06; streaming default 2025-09-07); the 8 screen runs have ids 28340113 and 3316xxxx-3317xxxx | `git log` |
| 26 | notebooks vs `src` | N: notebooks read | notebooks import helpers absent from `src` at this commit (section 1) | |
| 27 | eigen-analysis dt | P: dt = 0.01 ms | notebook uses `dt_s = 1e-3` (1 ms) for the same computation, confirming N's inference | Figure 3 cell 55 |
| 28 | LIF duration | P: 3 s | notebook `simulation_time = 0.3` s | ED Figure 4 cell 4; N flags |
| 29 | size median | P: "median cell size in the dataset" | median over the loaded network table | `sim_utils.py` L76; N flags |
| 30 | `max_dn_test` | `DN_Screen_Test.yaml` places it under `experiment` | read from `cfg.sim`, so ignored | L1890 |
| 31 | dead/duplicate paths | - | `run_dn_screen_simulations` and the `dn_screen` branch of `run_streaming_regular_simulation` are unreachable (`SimulationConfig` has no `dn_screen` field); `_adjust_stimulation_for_simulations` unused; `nan_inf_event_func`, `autocorrelation_1d`, `stack_pruning_states`, `pad_state_for_devices` unused | `async_vnc_sim.py` L3134-3136, L3239; `data_classes.py` L68-84 |
| 32 | licence | README/pyproject say MIT | no LICENSE file in the tree | section 1 |

Items in the existing notes that this reading confirms: transposition and `b` split (N section 3.2), inverse-CDF
sampler (3.3), size scaling formula (3.3), solver settings and clipping (3.4), input as an additive step
(4.1), the 128 = 8 x 16 replicate structure and starting amplitude 128 (4.2), the score algorithm details and
`>=` threshold (5.2-5.3), pruning candidate set, deletion semantics, 1/max-rate probabilities, rounds,
convergence and iteration caps (6.2), and that the streaming runner reuses `update_single_sim_state`.

---

## 12. Open questions (not determinable from the repository)

1. Which engine (`sync` vs `streaming`) and which `sim` config each published run used; only the Zenodo
   `.hydra/config.yaml` and `logs/run_config.yaml` per run can answer this. The published pruning tables are
   consistent only with the streaming engine's activity-based circuit reporting (section 7.3).
2. The exact code revision behind each SLURM job id, and the JAX/XLA/Diffrax versions and GPU types used.
3. How the signed, floored matrices were built from neuPrint/CAVE: dataset versions, synapse confidence
   thresholds, ROI restriction, whether the 5-synapse floor was applied per ROI or after summation, and how
   the 13 `unknown`/`unclear` MANC neurons kept zero output rows.
4. Whether the published DN screen's eight runs were all executed with the bisection tuner and `n_active_upper
   = 1500` (the config changed on 2025-08-19), and which seeds they used.
5. The origin of the paper's "lower bound of 10 active neurons" for the type-level screen.
6. The combinatorial (Dirichlet) DN screen: no code.
7. The replicate counts and seeds of the noise sweep (paper n = 512 per condition; `Noisy_W.yaml` carries no
   `n_replicates`), of the input-amplitude sweep (5 amplitudes, n = 512), and of the CoreCPG multirun.
8. Whether any published run used `noiseStdv`/`noiseMean` before the input-noise term was commented out
   (2025-09-06).
9. The exact float32/GPU numerics: whether per-replicate scores are stable across devices at the 6th decimal
   after rounding (the authors' own final-simulation consistency check tolerates 0.1, `async_vnc_sim.py`
   L974-986).
10. For the mCNS, BANC and full-MANC experiments: the experiment configs (`stimNeurons`, `stimI = 400`,
    `removeNeurons` indices), the loader used for `.npz`/`.feather` matrices, and which BANC table (with its
    27 non-MN rows carrying a `motor module` label, per the notes) defined the MN readout.
