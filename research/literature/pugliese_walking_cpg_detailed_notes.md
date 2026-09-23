<!--
ANSWER-KEY MATERIAL. This file describes the published solution of the DNg100 walking-CPG benchmark
(neuron types and body IDs of the minimal circuits). It must never be used as an input, prior, prompt,
feature, or training signal for any BrainIR discovery algorithm. See benchmarks/dng100_walking_cpg/README.md.

Provenance: compiled 2026-09-22 by a Claude research agent from the primary sources listed in section 0,
then spot-checked by the Phase 0 session. Tags: [PAPER] verbatim quote, [REPO] verified in code/data,
[DERIVED] recomputed by the agent, [NOT STATED], [UNVERIFIED].
-->

# Pugliese et al. — "Connectome simulations identify a central pattern generator circuit for fly walking"
## Research notes for BrainIR (compiled 2026-09-22)

---

## 0. Provenance, what was read, and conventions

**Sources read in full**
- **bioRxiv v2** (posted 2026-04-30): the PMC/Europe PMC JATS XML (PMCID PMC13142387, PMC version 2) was converted to text (`paper_pmc.txt`). I cross-checked it against bioRxiv's own v2 source XML (`v2.txt`). The content is identical; only formatting differs.
- **bioRxiv v1** (posted 2025-09-12): the bioRxiv source XML (`v1.txt`) and the full PDF (`v1.pdf` → `v1_pdf.txt`). The PDF also holds v1 Supplementary Tables 1–6.
- **v2 Supplementary Information PDF** (`supp/NIHPP2025.09.12.675944v2-supplement-3.pdf`): legends for Supplementary Videos 1–2 and Supplementary Tables 1–10. I re-extracted the table cells using word coordinates, because plain `pdftotext -layout` shifts the columns of Supplementary Tables 9 and 10.
- **Code**: `github.com/smpuglie/Pugliese_cpg_2025` now redirects to **`smpuglie/Pugliese_2026`** (the repository was renamed). I cloned the full history. HEAD = `10e7661bf414ba7b4c2edf795cd36d0f878c17c0` (2026-09-15, "new revision and readme update"). I read all `configs/*.yaml`, `src/simulation/vnc_sim.py`, `src/utils/sim_utils.py`, `src/utils/shuffle_utils.py`, `src/lif_model/lif_dynamics.py` and `src/run_hydra.py`, plus the code cells and text outputs of every figure notebook. I loaded and inspected every connectivity matrix and neuron table in `data/`.
- **Zenodo** record 10.5281/zenodo.22260924: metadata only. I did not download the ~170 GB of simulation archives (27 zip files).
- The bioRxiv API version history, Europe PMC/PubMed metadata, and the PMC landing page.
- **Follow-up**: Sapkal et al., bioRxiv 10.64898/2026.04.29.721658 v2. I read the source XML in full (`followup_v2.txt`).

**Tags used below**
- **[PAPER]**: verbatim quote. The source is bioRxiv v2 (= PMC) unless it is marked v1.
- **[REPO]**: verified by reading the code or data at commit 10e7661.
- **[DERIVED]**: my own computation from the repository data. The paper does not state it.
- **[NOT STATED]**: the paper and the repository do not give this.
- **[UNVERIFIED]**: I could not confirm it.

Equations: bioRxiv's HTML and XML render display math as images, so Eq. 1 and the inline formulas below are transcribed from the PMC MathML.

---

## 1. Biological question and main claims

**Question**
- [PAPER, Abstract] "Animal locomotion relies on rhythmic body movements driven by central pattern generators (CPGs): neural circuits that produce oscillating output without oscillating input. However, the circuit structure of a CPG for walking is not known in any animal."
- [PAPER, Introduction] "Here, we seek to identify the cellular components of CPG circuits that underlie walking in the fruit fly, Drosophila, using a computational modeling approach enabled by comprehensive datasets of neural connectivity."

**Main claims**
1. *DN screen.* [PAPER, Abstract] "A computational activation screen of descending neurons from the central brain identified DNg100—a known command neuron for walking—as the top driver of rhythmic leg motor activity."
   - ⚠ Caveat [PAPER, Supp. Table 1; REPO recomputed exactly]: in the v2 128-replicate screen the two individual DNg100 neurons rank **3rd (10093, 0.850086)** and **4th (10339, 0.836744)**. They sit behind DNp41 18153 (0.921685) and DNxl091 16683 (0.854303).
   - DNg100 is ranked first only at the **cell-type level**. My recomputed type means: DNg100 0.843, then DNit011 0.777. In the type-coactivation screen (Extended Data Fig. 1c data) DNg100 scores 0.896 and DNa07 0.843 [DERIVED].
   - In **v1** (16 replicates, saturation cap 500 neurons) the two DNg100 neurons were literally ranked #1 (10339, 0.983) and #2 (10093, 0.979) [v1 Supp. Table 1].
   - The paper's own justification for focusing on DNg100/DNb08 is type-level: [PAPER, Results §1] "we focus on two descending neuron types, DNg100 and DNb08, because every DN of these two types produced among the highest rhythmicity scores across all simulation replicates."
2. *Minimal circuit.* [PAPER, Abstract] "Simulated network pruning isolated a minimal rhythm-generating circuit consisting of one inhibitory and two excitatory interneurons; this three-neuron circuit was necessary and sufficient for motor rhythms across all six legs and in four connectome datasets."
   - ⚠ Only E1 and E2 were individually necessary. I1 was not: [PAPER, Results, "A core CPG circuit…"] "neither I1 nor I2 was individually necessary within the full network (Fig. 3j)."
   - The canonical E1-E2-**I1** triplet is the modal minimal circuit **only in MANC**. In mCNS and BANC the modal circuit is E1-E2-**I2**, and in FANC it is E1-E2-E3-I2 (Supp. Tables 3–6; see §6).
3. *DNb08.* [PAPER, Abstract] "Simulations also predicted that a separate descending pathway (DNb08) drives rhythmic leg movements, which we confirmed experimentally using optogenetics in behaving flies."
4. *Mechanism.* [PAPER, Discussion] "Because the cells in our model lacked intrinsic bursting, plateau potentials, and post-inhibitory rebound properties, we predict the core CPG operates as a network oscillator."
5. *Stimulus strength sets frequency.* [PAPER, Results] "This experiment confirmed predictions from our connectome simulations and suggests that the oscillation frequency of the CPG for walking is controlled by the strength of descending input from DNg100."
6. *Shared core.* [PAPER, Results, DNb08 section] "the convergence between the DNg100 and DNb08 minimal oscillating circuits (Fig. 5j) reveals that descending neurons supporting distinct behaviors can recruit overlapping VNC subnetworks that share a rhythm-generating core."
7. *Interleg coordination is not reproduced.* [PAPER, Results, "Motor rhythms in all six legs"] "These results suggest that descending drive from DNg100 alone is sufficient to generate within-leg motor coordination but not realistic interleg coordination."

---

## 2. Connectome datasets (names, versions, access, thresholds, neurons)

**Overview** — [PAPER, Methods, "VNC connectome datasets"] "Our VNC connectome simulations were constructed based on four published datasets, the male (MANC, [28]) and female (FANC, [29]) adult nerve cord connectome datasets and the male (mCNS, [31]) and female (BANC, [30]) adult central nervous system datasets. Unless stated otherwise, simulation results throughout the manuscript are from the front leg motor subnetwork within the MANC dataset."

**Dataset versions.**
- ⚠ **The paper does not state a version, materialization or snapshot for any of the four datasets [NOT STATED].**
- The repository contains only pre-extracted matrices and tables; it has no neuPrint or CAVE query code, and no file or commit names a version.
- The follow-up paper (Sapkal et al.) states *its own* versions: MANC v1.2.3, MaleCNS v0.9, BANC v626. **These are not evidence for what Pugliese et al. used.**

### 2.1 MANC (male adult nerve cord; Takemura et al. 2024 eLife [28])

**Construction**
- [PAPER, Methods] "we first selected all front leg motor neurons (class "motor neuron", subclass "fl"). Next we added all front leg premotor neurons by querying for any neuron that made synaptic outputs onto any of those leg motor neurons. Finally, we added all descending neurons (class "descending neuron") that made any synaptic outputs onto the front leg premotor neurons. After collecting this initial set of neuron IDs, we filtered for neurons that were proofread and had been assigned a neurotransmitter prediction."
- [PAPER, Methods] "To remove very weak connections and a small number of neurons that made only very weak connections to this network, we imposed a floor of 5 synapses."
- [PAPER, Methods] "This front leg motor subnetwork in MANC consisted of 4,604 neurons, making up 57% of all cells in the front leg neuropils and 20% of cells in the entire connectome dataset."
- [PAPER, Results §1] "4,604 neurons, including 1,318 descending neurons (DNs), 144 leg motor neurons, and 3,142 premotor neurons within the VNC, which we defined as all non-descending neurons that synapse onto leg motor neurons [32]. The 3,817,772 synapses among these neurons formed elements of a weight matrix W".
- **Access route**: neuPrint is implied but not said explicitly for MANC. The mCNS paragraph says "a very similar procedure… given the shared data infrastructure through neuPrint [81]."

**Verified in the repository**
- [REPO] Files: `data/manc t1 connectome data/W_20250813_DNtoMN_unsorted.csv` and `wTable_20250813_DNtoMN_unsorted_withModules.csv`.
- [REPO] The matrix is 4604×4604, with **rows = presynaptic** (index `bodyId_pre`).
- [REPO] Entries are signed synapse counts: Σ|w| = **3,817,772**, which matches v2 exactly; 196,535 nonzero connections; min |w| = 5, which confirms the floor.
- [REPO] Every row has a single sign (Dale's law is imposed by presynaptic NT).
- [REPO] Class counts: 1,318 DNs (933 ACh, 272 GABA, 113 Glu); 144 MNs (all subclass `fl`, 72 LHS and 72 RHS); 2,471 intrinsic, 375 ascending, 283 sensory, 4 neck MNs, 2 glia, plus others.
- [REPO] **"Premotor neurons" therefore includes sensory axons (283) and ascending neurons.**
- [REPO] Neurons whose NT is "unknown" (9) or "unclear" (4) are all in the table with **zero output rows**. 11 of them are MNs. These neurons can receive input but never output.
- [REPO] Table columns: `bodyId, type, class, subclass, hemilineage, size, predictedNt, predictedNtProb, ntAcetylcholineProb, ntGabaProb, ntGlutamateProb, somaSide, motor module, step contribution`.

**Full-MANC model (Fig. 4)**
- [PAPER, Methods] "For our simulations in the full MANC dataset in Figure 4, we simulated all neurons whose proofreading status was Traced."
- [PAPER, Results] "(23,532 neurons, including all six leg neuropils, DN axons, sensory axons, and VNC regions associated with the wings, halteres, and abdomen)."
- [REPO] `data/manc full vnc data/W_20251006.feather` is 23,532², with min |w| = 5, Σ|w| = 24,149,548 and 1,372,404 connections. The repository also has a later `W_20260522_allSynapses.npz` (23,628², no floor, Σ|w| = 30,930,102). That file does not appear in v2.

**Version evidence (indirect only) [UNVERIFIED]**
- The BANC table in the repository carries codex cross-reference columns named `manc_121_cell_type` and `manc_121_match_id`. These map BANC neurons onto MANC bodyIds 10093 (DNg100), 11751 (E2), 13905 (I1), 10242 (I2) and 10715 (E3). This is consistent with a MANC v1.2.x bodyId space.
- An older repository extraction (`data/manc t1l minicircuit/wTable_20241118_T1Lminicircuit.csv`) gives **different type labels for the same bodyIds**: 10093 = "BDN2", 11751 = "IN15A001" (hemilineage "15A"), 13905 = "IN16B007". The current table has 11751 = INXXX466 (hemilineage "TBD") and 13905 = IN16B036.
- The core synapse counts are identical between the two extractions. So the connectome itself did not change, but the annotation release did.

**Synapse confidence threshold**: [NOT STATED].

### 2.2 FANC (female adult nerve cord; Azevedo et al. 2024 Nature [29])

**Construction**
- [PAPER, Methods] "we restricted the network to the left front leg because this neuropil is the most thoroughly proofread and annotated [29, 32]. We started with front left leg motor neurons (from motor neuron table v7 CAVE annotation table), then added local premotor neurons (i.e., those with neurites constrained to the front left leg neuropil, from left t1 local premotor table v6), and the single descending neuron DNg100, for a total of 803 neurons. We added the two left DNb08 neurons to the dataset to produce the results in Figure 5."

**Sign assignment**
- [PAPER, Methods] "Unlike the other datasets, the FANC dataset does not have an automated classifier to predict the neurotransmitter for each neuron. However, the developmental hemilineage of neurons with somas within the VNC can be determined anatomically and is highly predictive of the neurotransmitter released by each neuron [32]. We used the hemilineage annotations from the corresponding CAVE tables [82] to assign a positive or negative sign to each cell's output."
- **Manual override of four neurons**
  - [PAPER, Methods] "Specifically, 4 neurons (segIDs 72905112552773752, 72975481296715415, 72975481363813393, 72905112552782067) are grouped with glutamatergic hemilineages in FANC so would be considered inhibitory, but the same cells in MANC (bodyIDs 162543, 11751, 13246, 15115) have an indeterminate hemilineage assignment of "TBD." In MANC, an independent neurotransmitter classifier predicted that all 4 of these neurons, belonging to types INXXX464 (E5), INXXX466 (E2), and INXXX468, are cholinergic (with probability >0.81), so they would be excitatory… Therefore, we assigned their output synapse weights to be positive."
  - [PAPER, Methods] "Once the mCNS and BANC datasets were available, we confirmed that they also show the predicted neurotransmitters of these cells to be acetylcholine."
  - [REPO] In the FANC table these four neurons have `classification_system` 08A (72905112552773752 = E5; 72975481363813393) or 16B (72975481296715415 = **E2**; 72905112552782067). Their `w_type` is set to "TBD" and `sign` to +1.
  - [REPO] **FANC's hemilineage label for E2 was 16B**, and **I1 (72905112619913957) is labelled 08A in FANC** (it is 16B in MANC and BANC). Both labels are glutamatergic, so sign −1 either way.

**Synapse floor**
- [PAPER, Methods, BANC paragraph] "One small difference between the datasets in the BANC and FANC as opposed to the mCNS datasets is that we did not impose a minimum synapse count of 5, so all detected synapses were included in W."
- [REPO] FANC W is `data/fanc t1l connectome data/W_BDN2toMN_20250107_corrected.npy` (803×803, rows = pre). Min |w| = 1 (no floor); Σ|w| = 431,811; 65,606 connections.

**Neuron table and IDs** [REPO]
- Table: `wTable_BDN2toMN_20250107_corrected.csv`, with CAVE columns `id, created, valid, classification_system, cell_type, pt_supervoxel_id, pt_root_id, pt_position…, w_type, sign, surf_area_um2, motor module, class`.
- Composition: 1 DN ("BDN2", neck connective left), 733 intrinsic neurons, 69 MNs (all with motor-module labels).
- The **"segIDs" the paper gives for FANC are `pt_supervoxel_id` values**, which are stable. The table also stores the `pt_root_id` (648518346…) at the extraction date (file dated 2025-01-07).
- The FANC materialization version is [NOT STATED]. The synapse table/cleft threshold is [NOT STATED].
- The FANC DNb08 table and IDs for Fig. 5 are **not in the repository**.

### 2.3 mCNS / "Male CNS" (Berg et al. 2025 bioRxiv [31])

- [PAPER, Methods] "We followed a very similar procedure in the Male CNS (mCNS) dataset, given the shared data infrastructure through neuPrint [81]. The only differences were that we used the new property of "consensusNt" rather than "predictedNt" to assign neurotransmitter identities and valence, and we only queried synapses inside the VNC regions of interest to exclude descending-descending and descending-ascending connectivity within the brain that was present in this dataset but not the MANC dataset. This gave us a dataset of 4,310 neurons for the mCNS simulations."

**Verified in the repository**
- [REPO] `data/imac t1 connectome data/W_20260210_vncRoisOnly.csv` + `wTable_20260210_vncRoisOnly.csv`. "IMAC/imac" is the repository's internal name; the notebooks label these runs "Male CNS".
- [REPO] The matrix is 4,310² (rows = pre), with min |w| = 5 (floor applied), Σ|w| = 2,190,257 and 118,920 connections.
- [REPO] Composition: 1,236 DNs and 130 MNs (129 with module labels; 67 L, 62 R).
- [REPO] An earlier all-ROI extraction `W_20251110.csv` (4,377 neurons) is also present.

**Version**: [NOT STATED]. The neuPrint dataset string (e.g. "male-cns:v0.9") is [UNVERIFIED].

### 2.4 BANC (brain-and-nerve-cord; Bates et al. 2025 bioRxiv [30])

- [PAPER, Methods] "To construct our network from the BANC dataset, we selected the same subset of cells, except that we included all descending neurons for simplicity (n = 1,314). As in the mCNS dataset, we excluded synapses within cells in our subnetwork but outside of the VNC (i.e., in the central brain), in this case by using a bounding box on the coordinates of the VNC within the EM volume. To assign neurotransmitters, we used the "neurotransmitter verified" property within the codex annotations CAVE table wherever it was available for a neuron, and for neurons without a verified neurotransmitter, we used "neurotransmitter predicted" instead… The BANC subnetwork we used totaled 4,963 neurons."

**Verified in the repository**
- [REPO] `data/banc t1 premotor/W_20260217.npz` (4,963², rows = pre). Min |w| = 1 (no floor); Σ|w| = 2,231,398; 496,041 connections.
- [REPO] Table `wTable_20260217_fullData_consistentColumns.csv`. It has codex-style columns including `fafb_783_*`, `fanc_1116_*`, `hemibrain_121_*` and `manc_121_*` cross-matches, `neurotransmitter_verified`, `neurotransmitter_predicted` and `surf_area_um2`.
- [REPO] An earlier `W_20251217.npz` (4,956 neurons) is also present.

**Version**: [NOT STATED].

### 2.5 FlyWire / hemibrain

These datasets were **not simulated**. The paper cites them only in the Introduction ([26], [27]). FlyWire and hemibrain IDs appear in the repository only as BANC cross-reference columns.

### 2.6 Size data used for normalisation

- [PAPER, Methods] "In MANC and the mCNS, we used the available volume property. In FANC and the BANC, we accessed the neuron meshes in the reconstruction to calculate the surface area of each cell."
- [REPO] MANC and mCNS use the neuPrint `size` column (voxel counts). FANC and BANC use `surf_area_um2`.

---

## 3. Simulation model

### 3.1 Neuron model and equation

**Model type**
- [PAPER, Results §1] "We chose a rate model in part because many neurons in the insect VNC, including premotor neurons active during walking, are nonspiking [41, 42, 43, 44]."
- [PAPER, Methods] "We report the output of this model as a rate in units of Hz, but as the model itself does not spike, this rate is interpreted as an abstract quantification of activity. The inputs to the DNs in the network are in arbitrary units."

**Eq. 1** (from PMC MathML):

    τ_i · dr_i/dt = max( r_i^max · tanh( (a_i / r_i^max) · ( I_i(t) + b · Σ_j w_ij r_j(t) − θ_i ) ), 0 ) − r_i(t)

- [PAPER, Methods] "The form of this equation is modified from a standard formulation of a rate model [83]" (Dayan & Abbott).
- [PAPER, Methods] "We chose the input nonlinearity to be a positive-rectified hyperbolic tangent function max(tanh(x), 0)… In particular, r^max is the upper bound, θ is the minimal input needed to produce a nonzero output, and a is the slope at this threshold value".
- ⚠ The inline g(x) formula in the Methods reads `g(x) = max(r^max tanh((a/r^max)x − θ), 0)`, which puts θ outside the a/r^max factor. That is inconsistent with Eq. 1 and with the code. **The code implements Eq. 1** [REPO `src/simulation/vnc_sim.py` L34–44]:
  - `total_input = I + jnp.dot(weighted_W, R)`
  - `activation = jnp.maximum(fr_cap * jnp.tanh((a / fr_cap) * (total_input - threshold)), 0)`
  - `return (activation - R) / tau`

**Active neuron.** [PAPER, Methods] "we considered neurons to be "active" or "recruited" in a simulation if their rate r_i(t) exceeds 0.01 Hz at any time point."

### 3.2 Weights and signs

**Weight definition**
- [PAPER] "the entries w_ij are the signed synapse counts from presynaptic neuron j to postsynaptic neuron i".
- [PAPER] "A constant b scaled the synaptic inputs relative to the external input and had the same value for all neurons."
- [PAPER, Methods] "the synaptic scaling parameter b = 0.03".
- [REPO] `configs/neuron_params/default.yaml` sets `excitatoryMultiplier: 0.03` and `inhibitoryMultiplier: 0.03`.
- [REPO] `reweight_connectivity` transposes the stored pre×post matrix and multiplies positive entries by `exc_mult` and negative entries by `inh_mult` (`vnc_sim.py` L47–53).
- [REPO] A separate b_Glu (used only in Extended Data Fig. 2e) is implemented by rescaling rows of glutamatergic neurons (`glutamateMultiplier`, `vnc_sim.py` L1688–1695).

**Sign rule (MANC)**
- [PAPER, Results §1] "excitatory (cholinergic) cells had positive weights and inhibitory (GABAergic, glutamatergic) cells had negative weights."
- [PAPER, Methods] "The sign of w_ij was assigned to be positive if the presynaptic neuron j was predicted to be cholinergic and negative if neuron j was predicted to be GABAergic or glutamatergic (according to the "predictedNt" property)."

**Exceptions and special cases**
- The four FANC overrides (§2.2).
- mCNS uses `consensusNt`; BANC uses verified NT, falling back to predicted NT.
- [REPO] MANC neurons with "unknown"/"unclear" predictedNt have zero outgoing weights.
- [REPO] MANC **MNs are mostly predicted glutamatergic (125/144), so their VNC output synapses are negative.** This is only 1,933 synapses (0.05% of the network) from 43 MNs [DERIVED].
- Other NTs (octopamine, serotonin, histamine, dopamine) in mCNS/BANC: how they are signed is [NOT STATED].

### 3.3 Biophysical parameters and randomisation

**Distributions**
- [PAPER, Methods, "Biophysical parameter distributions"] "the gain (before size normalization) was a* ∼ 𝒩(1, 0.1), the threshold (before size normalization) was θ* ∼ 𝒩(7.5, 0.6), the maximum rate was r^max ∼ 𝒩(200, 10) Hz, and the time constant was τ ∼ 𝒩(0.02, 0.002) sec."
- [PAPER] The distributions are "truncated at zero".
- [REPO] `sample_trunc_normal` draws from a truncated normal on [0, mean+100·sd] by inverse-CDF sampling (`sim_utils.py` L14–71).
- [REPO] Parameters are drawn for every neuron from `PRNGKey(experiment.seed)`. The main runs use `seed: 1`; the FANC silencing runs used seed 159 and the mCNS silencing runs seed 732, as shown in the notebooks.

**Size normalisation**
- [PAPER] "a_i* was divided by the median-normalized size of each neuron i, and θ_i* was multiplied by the median-normalized size of each neuron i".
- [PAPER] Rationale: "larger neurons have proportionally lower input resistance and are therefore less excitable [45]… postsynaptic potential amplitudes scale linearly with the number of synapses per unit area in Drosophila neurons [46]."
- [PAPER] Importance: "without adjusting a and θ for size, the network does not produce robust oscillations in response to DNg100 input even when this input is adjusted down in magnitude to compensate (Extended Data Fig. 2d)."
- [REPO] `set_sizes`: `normSize = np.nanmedian(sizes)`; NaN or zero sizes are set to the median; `a/size_ratio` and `threshold*size_ratio` (`sim_utils.py` L73–84).
- ⚠ The median is taken over the **simulated network table**, not the whole dataset as the text says ("median cell size in the dataset").
- [DERIVED] Mean-parameter values for key cells (MANC): size/median = DNg100 10.69, E1 5.91, E2 3.27, I1 1.97, I2 7.93. This gives thresholds of ~80, 44, 25, 15 and 60 respectively.
- [DERIVED] With I = 250 and mean parameters, DNg100 fires ≈16 Hz before recurrence. Comparable values: FANC ≈20 Hz (I = 150), mCNS ≈17 Hz (I = 400), BANC ≈25 Hz (I = 400).

**No hand-tuning**
- [PAPER, Results §1] "Rather than fine-tuning parameters, we simulated large numbers of replicates with independently drawn biophysical parameters, so that consistent dynamics across replicates indicate that the functions arise from synaptic connectivity structure rather than precise knowledge of any of the 18,416 parameters in the network."
- [PAPER, Results §1] "Note that no neuron in our models had intrinsic bursting or other longer-timescale membrane properties—all dynamics emerged from the rate model rather than relying on specialized cellular properties."

**How the values were chosen**
- [PAPER, Methods] "In our hyperparameter search, we evaluated a grid of values for the four biophysical parameters as well as the synaptic scaling constant b on a set of simple monosynaptic connections. In this test network, we chose ranges of values that produced consistent activity in downstream neurons when stimulated with input and ensured this activity also decayed to quiescence after input was removed."

### 3.4 Noise, initial state, integration and duration

**Noise and initial state**
- **Noise**: none in the dynamics. [REPO] The input-noise term is commented out in `rate_equation_half_tanh`. [PAPER] "Because the model had no spontaneous activity, activating inhibitory DNs alone could not recruit downstream neurons".
- **Initial state**: [PAPER, Fig. 2a caption] "the simulation begins as a quiescent network (rates at t = 0 s are 0 Hz)". [REPO] `R0 = jnp.zeros(...)`.

**Integration**
- [PAPER, Methods, "Implementation of numerical simulations"] "we implemented a numerical differential equation solver using the GPU-accelerated numerical computing library JAX [85]. Our solver used Diffrax [86] with the Runge-Kutta integration method of order 5(4) (diffrax.Dopri5()). Error tolerances were chosen to be rtol=2e–6 and atol=5e–9… Run on 4 Nvidia L40s GPUs, 1,024 replicates of the DNg100 activation in the full front leg MANC model typically ran in ∼18 minutes."
- [REPO] Solver details: PIDController(rtol, atol), `max_steps=100000`, `throw=False`, initial dt0 = 1 ms. Output is saved on a **1 ms grid** (`sim.dt: 0.001`).
- [REPO] Inf/NaN outputs are set to 0 and rates are clipped to [0, 1000] Hz (`vnc_sim.py` L73–122).

**Duration**
- [PAPER] DN screen and pruning simulations: "1 second in duration, with the tonic input stimulus onset at 20 ms".
- [REPO] The main DNg100/DNb08 activation runs (Figs 2, 3j, 5) use `sim/default.yaml`: **T = 2.0 s**, pulse 0.02–1.999 s. The saved MANC results have shape (1024, 4604, **2001**). **The paper does not state the 2-s duration [NOT STATED in paper].**

### 3.5 Other model variants

**LIF check**
- [PAPER, Methods, "Leaky integrate-and-fire model"] "V_rest = −52 mV, V_reset = −52 mV, V_thresh = −45 mV, t_refractory = 2.2 ms, τ_membrane = 20 ms, τ_synaptic = 5 ms, w_synaptic = 0.275 mV, t_delay = 1.8 ms, V_init = −52 mV, dt = 0.01 ms, simulation time = 3 s, network input = 0.15 nA", with parameters from Shiu et al. [37] "without tuning or training specific to our circuit or validation against the physiology of these cells".
- [REPO] The notebook uses `simulation_time = 0.3` s (not 3 s) and `membrane_conductance = 10 nS`. It uses raw signed synapse counts × 0.275 mV, with no size normalisation and no b. It keeps DNg100 10093, E1, E2, I1 and one MN (12686, a coxa promotor MN), and zeroes MN outputs.

**Linearisation**
- [PAPER, Methods] "we simplified the dynamical system equation to τ dh/dt = −h + ϕ(Wh + I), then discretized and linearized it to h_{t+dt} = (1 − α + αgW) h_t + αgI, where α = dt/τ".
- [PAPER] "multiplied by an overall gain factor of 0.75… Calculations used an average time constant of τ = 20 ms and a timestep dt = 0.01 ms… the eigenvalues of W* were {0.9908 + 0.0879j, 0.9908 − 0.0879j, 0.8683, 0.95}… approximately 14 Hz."
- [DERIVED] I reproduced these eigenvalues (0.9907±0.0876j, 0.8686, 0.95 → 14.04 Hz) **only with dt = 1 ms** (the eigenvalue 0.95 = 1−α requires α = 0.05). With dt = 0.01 ms the frequency is ~13.95 Hz, but the eigenvalues are ≈0.9999±0.0009j. **The stated dt = 0.01 ms appears to be a typo for 1 ms.**

---

## 4. Inputs: what is stimulated, how, and the DN screen

### 4.1 DNg100 (= BDN2)

**Identity**
- [PAPER, Results] "DNg100 is the only cell type in Drosophila known to function as descending command neurons for walking; optogenetic stimulation of DNg100 neurons initiates forward walking, even in headless flies ([50], where DNg100 is referred to as BDN2)."
- [PAPER, Methods] "Unless otherwise noted, we simulated activation of the DNg100 neuron innervating the left leg neuropils. We refer to this as the "left DNg100," reflecting its target neuropil rather than its soma location in the right hemisphere, as we only consider connectivity within the VNC."

**Stimulated neuron per dataset** [REPO]
- MANC: bodyId **10093** (wTable index 31; `rootSide` LHS in the full-MANC table). The other DNg100 is 10339 (rootSide RHS).
- FANC: supervoxel **73115599907537415** (root 648518346459693060; "BDN2", "neck connective (left)").
- mCNS: bodyId **10056** ("DNg100_R", somaSide R). This is the neuron excluded as "DNg100" in the pruning tally; the other is 10045 ("DNg100_L").
- BANC: root **720575941500851362** (side "right"; `manc_121_match_id` = 10093). The other is 720575941626500746 (side left; match 10339).

**Protocol**
- [PAPER] "a single sustained input was applied to the DNg100 neuron innervating the left side of the VNC"; "a tonic input to a single descending neuron with an onset at 20 ms".
- [PAPER, Methods] Amplitudes: "For DNg100 activation, I_stim = 250 in MANC, 150 in FANC, and 400 in the two CNS datasets (these activations have arbitrary units…)".
- [PAPER] Why the CNS datasets need more: "The descending neurons have larger volumes in the two CNS datasets due to their arbors in the brain being preserved, which is why the DNg100 input needed to be of a higher magnitude in these datasets."
- [REPO] The input is a step into the DN's own summed input `I` (before the DN's nonlinearity), active for pulse_start ≤ t ≤ pulse_end (`vnc_sim.py` L38–40). `make_input` sets the stimulated index to I_stim (`sim_utils.py` L362–365).
- **Bilateral stimulation (Fig. 4)**: [PAPER] "Bilateral activation of the two DNg100 axons". The amplitude for the full-MANC and front-leg bilateral runs is [NOT STATED]. [REPO] The sweep config `DNg100_Stim_Sweep.yaml` uses both DNg100s (indices 31, 132) with I from 180 to 340.
- **Input-strength sweep (Fig. 2g)**: [REPO] run 28914803 used I = 180, 220, 260, 300, 340 (512 replicates each).

### 4.2 DN activation screen

**Scope and procedure**
- [PAPER, Results §1] "we conducted a computational activation screen of all 933 excitatory DNs (i.e., DNs predicted to release acetylcholine)… We activated each DN with a step input and evaluated average output rhythmicity of leg motor neurons over 128 random simulation replicates".
- [PAPER, Methods, "Descending neuron activation screen"] "we automatically tuned I_stim over a range of values depending on if the simulation was underactive or oversaturated. Underactive simulations were defined as having fewer than 5 neurons recruited in the whole network, and oversaturated simulations were defined as having more than 1500 neurons recruited… If the simulation was underactive, I_stim was doubled, or set to the midpoint to the next highest value that had been tried. If it was oversaturated, I_stim was halved… repeated up to a maximum of 10 times… If after these 10 iterations the simulation was still underactive or oversaturated, it was considered uninterpretable and the motor rhythmicity score for this replicate was not computed (set to NaN)."
- **Ranking metric**: [PAPER] "Reported motor rhythmicity scores for each neuron (Fig. 1e, Supplementary Tables 1 and 10) were the mean score of the feasible replicates."

**Code details not in the paper** [REPO]
- The starting I_stim is **128** (`configs/experiment/DN_Screen.yaml`).
- The adjustment also counts as "oversaturated" any simulation with **>100 neurons exceeding 100 Hz** (`n_high_fr_upper: 100`, `high_fr_threshold: 100.0`; `vnc_sim.py` L1190). The paper does not mention this.
- Each run used 16 replicates. The 128 replicates are 8 runs combined.

**Results**
- [PAPER] "Out of the 933 DNs activated, 74 (7.9%) produced unstable simulations in all replicates so could not be scored… Of the 859 remaining, 332 (38.6%…) had an average score of 0, and 207 more scored below 0.025 on average… Only 29 DNs (3.4%, or 3.1% of total) had an average score greater than 0.5 (Supplementary Table 1)."
- [PAPER, Methods] "233 DNs, representing 27.1% of the DNs with any usable replicates and 25.0% of the DNs overall" had at least one replicate scoring >0.5.
- [DERIVED] I recomputed every one of these numbers **exactly** from `figures/DN_Screen-hyak-combined128reps/*.csv`, applying the notebook's rule of NaN when active <5 or >1500: 74 / 859 / 845 (≥50 usable) / 332 / 207 / 29 / 233.

**Supplementary Table 1** (all 29 DNs with mean >0.5; bodyId type score)

| bodyId | type | score | bodyId | type | score | bodyId | type | score |
|---|---|---|---|---|---|---|---|---|
| 18153 | DNp41 | .922 | 16683 | DNxl091 | .854 | **10093** | **DNg100** | **.850** |
| **10339** | **DNg100** | **.837** | 30919 | DNg12 | .794 | 18279 | DNp41 | .791 |
| 44321 | DNit011 | .777 | 32815 | DNg12 | .739 | 23461 | DNfl031 | .731 |
| **14061** | **DNb08** | **.727** | 19821 | DNg54 | .697 | 37139 | DNit013 | .677 |
| **14966** | **DNb08** | **.657** | 10291 | DNxl134 | .651 | 12221 | DNxl121 | .644 |
| 11164 | DNa13 | .642 | 25931 | DNa07 | .638 | 30130 | DNxn167 | .621 |
| **13892** | **DNb08** | **.618** | 10896 | DNxl133 | .616 | 16264 | DNxn159 | .605 |
| 10101 | DNg15 | .586 | 23962 | DNxn127 | .584 | 11145 | DNa13 | .582 |
| **14680** | **DNb08** | **.576** | 32742 | DNg12 | .558 | 22194 | DNxn171 | .520 |
| 10967 | DNa13 | .519 | 11930 | DNp43 | .516 | | | |

**Robustness variants**
- [PAPER] "DN activation screen results were qualitatively similar across a wide range of model parameters and configurations, including activating DNs of the same cell type (rather than one-by-one, Extended Data Fig. 1c), combinatorially activating multiple DNs (Extended Data Fig. 1e and Supplementary Table 2), and increasing the variance of all four biophysical parameter distributions (Extended Data Fig. 2c)."
- **Type-level screen**: [PAPER, ED Fig. 1c] "n = 16 replicates, 321 excitatory DN types"; Methods: "we increased our lower bound on active neurons to 10 neurons". [DERIVED] Top types by mean: DNg100 0.896, DNa07 0.843, DNit011 0.763, DNit013 0.693, … DNb08 0.628.
- **Combinatorial screen**: [PAPER, Methods] "We used a Dirichlet distribution parameterized by a constant parameter α… from a single DNs receiving the majority of the stimulus α = 10⁻⁴ to almost all DNs sharing a fair share of the total stimulus amplitude α = 10… approximately 60,000–80,000 simulations for each point in a grid… 14/29 of these top rhythmic DNs were also among the highest-scoring DNs in the individual screen, and 2/29 were GABAergic neurons". Supp. Table 2 lists 29 DNs; DNg100 10093 and DNb08 14680 and 14966 are among them. ⚠ **[REPO] No code for the Dirichlet screen was found in the repository**, and the ED Fig. 1 notebook covers panels a–d only.
- **Framing**: [PAPER] "this computational screen works as a discovery tool, analogous to a forward genetic screen… we do not interpret low scores as evidence against a DN's role in rhythm generation."
- **Inhibitory DNs**: excluded from the single-DN screen and included only in the combinatorial screen.

---

## 5. Outputs: readout neurons and rhythmicity quantification

### 5.1 Readout neurons

- [PAPER] Rhythmicity is computed on "leg motor neurons", averaging "all active motor neurons". [PAPER, ED Fig. 1c] "As in other analyses, scores do not distinguish whether active motor neurons belong to one or both legs."
- [REPO] The analysis notebooks score MNs defined as `wTable["motor module"].notna()`:
  - MANC front-leg network: 138 MNs (69 L + 69 R) of the 144.
  - FANC: 69 (T1L only).
  - mCNS: 129.
  - BANC: 156 rows. ⚠ **In the BANC table, 27 of these rows are not MNs.** They have NaN cell_type, are labelled "tarsus control", and have class DN/AN/IN/NaN/glia. Separately, 22 class-MN rows lack a module. This looks like a merge artefact, and it would contaminate the BANC MN readout if this table was used. I could not verify which table the final BANC runs used [UNVERIFIED impact].
- [REPO] The **pruning code** uses `class == "motor neuron"` to define MNs (`shuffle_utils.extract_shuffle_indices`). Those neurons are never pruned and are the ones scored inside `update_single_sim_state`.

### 5.2 Motor rhythmicity score

- [PAPER, Methods, "Motor rhythmicity score"] "The motor rhythmicity score assigned to each simulation was computed as the average of rhythmicity scores for all active motor neurons. A motor neuron was included if its r_i(t) > 0.01 at any time after t = 250 ms… This trace was normalized so that it is between −1 and 1… We then computed the autocorrelation of r̂ and detected peaks in this autocorrelation, with a prominence threshold of 0.05. The "raw score" for this neuron was assigned as the smaller of the maximum peak height (magnitude above zero) and the maximum peak prominence (magnitude between peak and valley). Using the time shift Δt value at which the most prominent peak occurred as the period of the dominant rhythm, we then computed the same score for a reference sinusoidal waveform with the same frequency and total duration. To normalize the rhythmicity score between 0 and 1, we divided the raw score by the reference score… If a motor neuron is active, but there is no prominent peak in the autocorrelation, the neuron received a score of 0."
- [PAPER] "a number between 0 and 1, where 0 is not rhythmic and 1 corresponds to perfectly periodic oscillations".
- **Design goal**: "repeating signals would receive high scores even if they were not necessarily symmetric waveforms (e.g., both a sine wave and a sawtooth would receive a high score)."
- ⚠ The PMC MathML normalisation is `r̂(t) = 2·(r − min r)/max r − 1`. **The code uses `2*(r − min)/(max − min) − 1`** (`sim_utils.py` L156–165), so the paper's formula has a typo.

**Code details** [REPO `sim_utils.py` L87–311]
- Values are rounded to 1e-10.
- The autocorrelation is computed with FFT `correlate(mode='full')`, normalised by max |autocorr|, and only non-negative lags are kept.
- Peaks are detected with a custom JAX routine. Prominence = height − max(minimum of everything to the left, minimum of everything to the right), threshold ≥ 0.05. Lag 0 is excluded.
- The reference score is the maximum of the sine and cosine reference scores.
- The final score is rounded to 6 decimals and clipped to [0, 1].
- A simulation with no active MNs scores 0.

### 5.3 Frequency and threshold for "rhythmic"

**Frequency**
- [PAPER, Methods, "Oscillation frequency and phase analysis"] "the period T_i = 1/f_i was defined as the time shift (Δt) of the highest peak in the autocorrelation of the normalized activity trace after 250 ms. The overall motor neuron frequency for a simulation was defined as the mean frequency across all oscillating motor neurons."
- **Phase**: from the cross-correlation peak within ±T_i, normalised to T_i and wrapped to [−π, π]. The control is replicate-shuffled.
- **Walking-relevant frequency range**: [PAPER] "roughly matched the stepping frequency of real walking flies (∼7–15 Hz, [52, 53])".

**What counts as "rhythmic"**
- The pruning threshold is score **≥ 0.5** ([PAPER, Methods] "(≥ 0.5)"; the Results text says ">0.5"). [REPO] `oscillation_threshold: 0.5`, with `>=` in code.
- The screen reports means and highlights DNs with mean >0.5.
- No frequency band criterion is applied to the rhythmicity score itself [REPO].
- The kinematic version for experiments applies a 1-Hz floor: [PAPER] "Traces for which the detected peak frequency was slower than 1 Hz were assigned a score of 0."

---

## 6. Pruning (computational sufficiency screen)

### 6.1 Algorithm as described

- [PAPER, Results] "At each iteration, we stochastically silenced one interneuron, selected with a probability inversely proportional to its activity. If leg motor oscillations persisted (rhythmicity score >0.5), that cell was pruned from the network. However, if the oscillations ceased (rhythmicity <0.5), the cell was restored (Fig. 3b…). Each replicate of the screen terminated when none of the remaining cells could be pruned without disrupting leg motor neuron rhythms."
- [PAPER, Methods, "Computational sufficiency screen with iterative pruning"] "We started with a full intact network and one random seed for the biophysical parameters of its cells (these parameters were frozen for all iterations in one pruning procedure)… First, all neurons that were not active were pruned from the network. Thereafter, at each step, one additional neuron was chosen to be silenced, with a probability inversely proportional to its maximum rate at the last iteration… If the motor rhythmicity score of this pruned network still exceeded a threshold value (≥ 0.5), this silenced neuron, along with any inactive neurons, were permanently pruned in the next iteration… the stopping criterion was when no neuron in the pruned network could be removed without producing a motor rhythmicity score below threshold… Because the biophysical parameters and the choices of neurons to silence were stochastic, we repeated the screen 1024 times for each full network activated by each DN (DNg100 and DNb08)."
- [PAPER, Methods] Settings: "simulations were 1 second in duration… For DNg100 activation, I_stim = 250 in MANC, 150 in FANC, and 400 in the two CNS datasets… For DNb08 activation, I_stim = 65 in MANC and 180 in FANC. Leg motor neurons were not considered by the pruning screen, so they all remain present in all simulated networks."

### 6.2 What the code does [REPO `vnc_sim.py` `update_single_sim_state` L252–492; `_run_with_pruning` L1448–1652]

1. **Candidates** are all non-MN neurons (`interneuron_mask` = not in `mn_idxs`). This includes the stimulated DN and every other DN. Silent DNs are removed at the first step.
2. **Silencing is deletion.** A W_mask zeroes both the row and the column of the neuron.
3. **Scoring window.** Scores and max rates are computed from t ≥ 250 ms (`clip_start = pulse_start/dt + 230` = 250 samples).
4. **Removal probability** ∝ 1/max_rate (t ≥ 250 ms). Neurons with max = 0 get weight 1. Already-removed and put-back neurons are excluded. The draw uses `jax.random.categorical`.
5. **Accept or reject.** If score ≥ 0.5 ("continue" branch), every interneuron with max rate ≤ 0 is also removed permanently. If score < 0.5 or NaN ("reset" branch), the last removed neuron is restored and added to `neurons_put_back`, and another neuron is drawn.
6. **Rounds** ("levels"). When no candidates remain, a new round starts and the put-back set is reset.
7. **Convergence** = a new round is needed **and** this round's put-back set equals the previous round's. On convergence the state reverts to the most recent state that scored ≥ threshold.
8. **Iteration cap.** `max_pruning_iterations` = 200 for DNg100 and 250 for DNb08 (configs). The replicates in a batch iterate in lockstep. Non-converged replicates stay large; the paper excludes them from the histograms as ">15 interneurons".
9. The async ("streaming") runner reuses the same `update_single_sim_state`.

**MNfl10 anomaly**
- Supp. Tables 3 and 7 list **MNfl10 (bodyId 17664; class "motor neuron", no motor-module label)** as a member of some "minimal circuits". This implies that in those runs MNs were defined by motor-module annotation, as in the archived code (`mnIdxs = wTable.loc[wTable["motor module"].notna()].index`, removed in commit 61e22eb, 2025-08-16).
- Current code defines MNs by class. Which definition the published runs used is [UNVERIFIED]. The run configs are on Zenodo only.

### 6.3 Results: DNg100 pruning (1024 screens per dataset; Supplementary Tables 3–6; counts ≥10 shown)

**Headline results**
- [PAPER] "In MANC, independent computational sufficiency screens repeatedly converged to a minimal circuit of just three neurons, two excitatory and one inhibitory (Fig. 3c). Over 60 percent (636/1024) of pruning screens converged to this same circuit."
- [PAPER] "In FANC, screens converged to a four-interneuron circuit (70.4% of 1024 replicates) that retained E1 and E2 but identified a different inhibitory neuron, "I2" (IN19A007), and one additional excitatory interneuron, "E3" (IN19B012, Fig. 3d). In the two full CNS connectomes, pruning screens converged to circuits containing either I1 or I2 alongside E1 and E2 (Fig. 3e,f). Despite the stochastic nature of the pruning procedure and differences across datasets, the minimal circuits nearly always included both E1 and E2, and either I1 or I2 (3521/4096 screens, or 86.0%)."
- [REPO, Figure 3 notebook] Per dataset, the fraction of screens containing E1+E2+(I1 or I2) is MANC 754 (73.6%), FANC 938 (91.6%), mCNS 839 (81.9%) and BANC 990 (96.7%). The sum is 3,521 ✓.
- [PAPER, Fig. 3c–f captions] Non-converged screens: "5 screens that did not converge to 15 or fewer interneurons are excluded" (MANC); "1 outlier of 18 interneurons not shown" (FANC). The notebook shows 0 for mCNS and 5 for BANC.

**MANC (bodyIds)**

| count | circuit |
|---|---|
| **636** | 10707, 11751, 13905 = IN17A001 (E1), INXXX466 (E2), IN16B036 (I1) |
| 123 | E1, 10715 IN19B012 (E3), E2, 12026 IN13A010 (−), 17664 MNfl10 (−) |
| 102 | 10242 IN19A007 (I2), E1, E2 |
| 33 | E1, E3, E2, IN13A010 (−) |
| 11 | E1, E2, 11799 IN19A020 (−), MNfl10 (−), 162543 INXXX464 (E5) |

**FANC (supervoxel IDs)**

| count | circuit |
|---|---|
| **721** | 72483380721505294 IN19A007 (I2), 72834674820722635 IN17A001 (E1), 72975481296715415 INXXX466 (E2), 73820799177797612 IN19B012 (E3) |
| 89 | I2, E1, 72905112552773752 INXXX464 (E5), E2 |
| 36 | 72694075576809644 IN13A010 (−), E1, E2, E3 |
| 25 | I2, E1, E5, E2, 72975481364113281 "8A (−)" |
| 15 | E1, 72905112619913957 IN16B036 (I1), E2, E3 |
| 13 | I2, E1, E2, 73891167921933971 "19B (+)" |
| 13 | I2, E1, E5, E2, 73468887542677672 "12B (−)" |

**mCNS (bodyIds)**

| count | circuit |
|---|---|
| **655** | 800173 IN17A001 (E1), 800374 IN19A007 (I2), 800863 INXXX466 (E2) |
| 181 | E1, E2, 801884 IN16B036 (I1) |
| 61 | E1, 800216 IN19B012 (E3), E2, 809385 IN13A010 (−), 902491 IN19A020 (−) |
| 22 | E1, E3, E2, IN13A010 |
| 17 | E1, E3, E2, IN19A020 |
| 13 | E1, E3, E2, 801568 IN19A024 (−), IN19A020 |
| 10 | E1, E3, E2, IN19A024, IN13A010 |

**BANC (root IDs)**

| count | circuit |
|---|---|
| **681** | 720575941469024064 INXXX466 (E2), 720575941504247575 IN17A001 (E1), 720575941569601650 IN19A007 (I2) |
| 231 | E2, E1, 720575941544954556 IN16B036 (I1) |
| 36 | E2, E1, 720575941542442076 IN19B012 (E3), I2 |
| 18 | E2, E1, 720575941520072883 IN19A020 (−), E3 |
| 15 | E2, E1, I2, 720575941571519483 INXXX464 (E5) |

⚠ **Takeaway**: the named three-neuron circuit **E1-E2-I1** is the modal solution only in MANC. The modal solution is **E1-E2-I2** in mCNS and BANC, and **E1-E2-E3-I2** in FANC. E1 and E2 are present in essentially every solution.

**Right DNg100 (MANC)**: [PAPER, ED Fig. 6c] "Circuits identified by pruning (n = 1024 replicates, right DNg100, MANC)… (14 screens did not converge to 15 or fewer interneurons and are not shown)". The circuit identities are shown only graphically [not tabulated].

### 6.4 Results: DNb08 pruning

- [PAPER] "The most common minimal circuit, identified in nearly half (45.4%) of the 1024 replicates, consisted of five interneurons (Fig. 5f,h, Supplementary Table 7): the same E1, E2, and I2 neurons from the core walking CPG, plus two additional excitatory neurons "E4" (IN03A006) and "E5" (INXXX464)."
- [PAPER] "Replication of the pruning screen in FANC converged to the same E1-E2-E4-E5-I2 circuit as the most common solution (246/1024 replicates…)".

**MANC (Supp. Table 7)**

| count | circuit |
|---|---|
| **465** | 10242 I2, 10707 E1, 11751 E2, 12021 IN03A006 (E4), 162543 INXXX464 (E5) |
| 129 | 10715 E3, E2, E4, 13905 I1, E5 (the "second convergent circuit") |
| 26 | E1, E2, E4, I1, 17664 MNfl10 (−), E5 |
| 21 | E1, E2, E4, I1, 162539 IN13A001 (−), E5 |
| 12 | E1, E2, E4, I1, E5 |
| 12 | I2, E1, E2, 21162 IN20A.22A036 (+), E5 |
| 10 | I2, E1, E2, E4, IN20A.22A036, E5 |

**FANC (Supp. Table 8)**

| count | circuit |
|---|---|
| **246** | I2 72483380721505294, E4 72624462142676168, E1, E5 72905112552773752, E2 |

The remaining FANC rows add "3A (+)" 72624462142673647/72624462142690635, "22A (+)" 72413150020127131, "8A (−)" 72905181339304184/72905112619846398, or "12B (−)" 72976099705187525. One row labels 72905112619846398 as "8A (+)" and others as "8A (−)", which looks like a table inconsistency.

**Non-convergence**: [PAPER] "37 screens did not converge to 15 or fewer interneurons" (MANC, Fig. 5f); "54 screens did not converge…" (FANC, Fig. 5g).

---

## 7. The discovered circuit: E1, E2, I1 (and I2, E3, E4, E5)

### 7.1 Naming and identity

- [PAPER] "These three cells, which we refer to as "E1" (IN17A001), "E2" (INXXX466), and "I1" (IN16B036) for clarity, are interneurons local to the front left leg neuropil."
- [PAPER, ED Fig. 8] "Each of these cell types consists of exactly one neuron per leg neuropil."
- Types are MANC-style names. The hemilineage is encoded in the name (17A, 16B, 19A, 19B, 03A); "XXX" means hemilineage unknown ("TBD").

**Core-cell reference table** [REPO: MANC `wTable_20250813`; mCNS `wTable_20260210_vncRoisOnly`; FANC `wTable_BDN2toMN_20250107_corrected`; BANC `wTable_20260217_fullData_consistentColumns`]

| label | MANC type | MANC bodyId (T1L, used) | MANC predictedNt (prob) | MANC hemilineage | FANC supervoxel ID (T1L) | FANC root ID (at extraction) | FANC label → sign | mCNS bodyId (T1L) | mCNS consensusNt | BANC root ID (T1L) | BANC NT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **E1** | IN17A001 | **10707** | ACh (0.916) | 17A | 72834674820722635 | 648518346488234782 | 17A → +1 | 800173 | ACh | 720575941504247575 | ACh (verified) |
| **E2** | INXXX466 (older label IN15A001) | **11751** | ACh (0.904) | TBD (older label 15A) | 72975481296715415 | 648518346497857270 | 16B → overridden +1 | 800863 | ACh | 720575941469024064 | ACh (predicted) |
| **I1** | IN16B036 (older label IN16B007) | **13905** | **Glu** (0.954) | 16B | 72905112619913957 | 648518346483080678 | 08A → −1 | 801884 | Glu | 720575941544954556 | Glu (verified) |
| **I2** | IN19A007 | **10242** | **GABA** (0.691) | 19A | 72483380721505294 | 648518346510192422 | 19A → −1 | 800374 | GABA | 720575941569601650 | GABA (verified) |
| **E3** | IN19B012 (subclass BR, soma contralateral) | **10715** (soma RHS) | ACh (0.841) | 19B | 73820799177797612 | 648518346490998819 | 19B → +1 | 800216 (soma R) | ACh | 720575941542442076 (side right) | ACh (verified) |
| **E4** | IN03A006 | **12021** | ACh (0.820) | 03A | 72624462142676168 | 648518346494799159 | 03A → +1 | 800663 | ACh | 720575941481989059 | ACh (verified) |
| **E5** | INXXX464 | **162543** | ACh (0.816) | TBD | 72905112552773752 | 648518346481651905 | 08A → overridden +1 | 800286 | ACh | 720575941571519483 | ACh (predicted) |
| DNg100 (stimulated) | DNg100 ("BDN2") | **10093** | ACh (0.958) | — | 73115599907537415 | 648518346459693060 | +1 | 10056 (DNg100_R) | ACh | 720575941500851362 | ACh (predicted) |

Notes on the table:
- The MANC subclass is "IR" for E1, E2, I1, I2, E4 and E5. BANC's `cell_sub_class` spells this out as "ventral_nerve_cord_ipsilateral_restricted", and E3 as "…bilateral_restricted".
- The MANC→FANC type mapping is shown in the paper's tables. **The matching method for FANC is not described [NOT STATED]**; the FANC table itself carries only hemilineage labels such as "17A_dorsal_post".
- mCNS and BANC types come from each dataset's own `type`/`cell_type` annotations.

**Six-leg copies in MANC** (soma neuromere/side from the full-MANC table) [REPO]

| type | T1L | T1R | T2L | T2R | T3L | T3R |
|---|---|---|---|---|---|---|
| E1 IN17A001 | 10707 | 10690 | 10559 | 10072 | 10498 | 10558 |
| E2 INXXX466 | 11751 | 13698 | 11767 | 12107 | 12315 | 152696 |
| I1 IN16B036 | 13905 | 14096 | 13186 | 17322 | 12953 | 156245 |
| I2 IN19A007 | 10242 | 10427 | 11680 | 10252 | 10215 | 10346 |
| E3 IN19B012 (by soma side) | 154691 (soma L) | 10715 (soma R; in the T1L circuit) | 11109 | 11093 | 11984 | 10790 |
| E4 IN03A006 | 12021 | 11374 | 11236 | 11085 | 12058 | 11760 |
| E5 INXXX464 | 162543 | 10274 | 11450 | 100544 | 10927 | 10677 |
| INXXX468 (other FANC override) | 13246, 15115 | 14230, 14650 | 14432, 14588 | 13511, 30260 | 13323, 14084 | 13293, 13574 |

- DNg100: 10093 (rootSide LHS, "left DNg100") and 10339 (RHS).
- DNb08: 13892 and 14061 (LHS), 14680 and 14966 (RHS). **14061 is the one simulated** (config index 1211; ED Fig. 10b asterisk).

**Right-side (T1R) copies in the CNS datasets**
- mCNS: E1 800288, E2 903216, I1 803183, I2 800411, E3 801061 (soma L), E4 903211, E5 800375.
- BANC: E1 720575941554038555, E2 720575941519468654, I1 720575941441065919, I2 720575941461249747, E3 720575941689865880 (side left), E4 720575941354124592, E5 720575941603886582.

⚠ The claim "repeated in the neuropils of all six legs across all four connectome datasets (Extended Data Fig. 8)" is directly supported by the ED Fig. 8/9 captions **only for MANC (six legs) and FANC (T1L morphology)**. FANC was not modelled beyond T1L, and the CNS six-leg copies are not shown in the captions [UNVERIFIED for FANC, mCNS and BANC six-leg copies].

### 7.2 Connectivity (signed synapse counts, presynaptic row → postsynaptic column)

**What the paper says**
- [PAPER] "In the MANC minimal circuit, the three neurons E1, E2, and I1 are connected all-to-all, but with particularly strong connections from E1→E2, E2→I1, I1→E1, and I1→E2 (Fig. 3g). Only E1 receives direct synaptic input from DNg100."
- [PAPER] Synapse-share statistics: "Among the cumulative input synapses to E1, E2, and I1, 9.28% originate from within the circuit itself or from DNg100. Within this circuit, E1 is the primary recipient of DNg100 output (fifth-strongest output overall, accounting for 0.49% of DNg100 output synapses). E2 is both the strongest output of E1 and its strongest input (this connection accounts for 2.86% of E1 output synapses and 11.85% of E2 input synapses). I1 is the strongest inhibitory input to E1 (4.57% of E1 input synapses) and the fourth-strongest input to E2 (3.78% of E2 input synapses)."
- [DERIVED] Checked against the no-floor full-MANC matrix:
  - E1 is DNg100-10093's 5th target ✓.
  - E2 is E1's top target and E1 is E2's top input ✓.
  - I1 is E1's top input by magnitude ✓, and E2's 4th input ✓.
  - My percentages differ (e.g. 1.34% of DNg100 outputs, 12.3% of E2 inputs). The paper's denominators probably include synapses onto fragments or non-traced bodies [UNVERIFIED].
  - Each DNg100 has 1,426 (10093) or 1,474 (10339) postsynaptic partners, which confirms [PAPER, Discussion] "Each DNg100 neuron synapses onto more than 1,400 cells in the VNC".

**Signed counts in the simulated networks** [DERIVED from the repository matrices; MANC/mCNS ≥5 floor, FANC/BANC unfloored]

| edge | MANC | FANC | mCNS | BANC |
|---|---|---|---|---|
| DNg100→E1 | 187 | 200 | 155 | 198 |
| DNg100→E2 / →I1 | 0 / 0 | 2 / 1 | 0 / 0 | 1 / 2 |
| E1→E2 | 539 | 241 | 465 | 336 |
| E2→E1 | 19 | 12 | 11 | 26 |
| E1→I1 | 17 | 2 | 6 | 9 |
| E2→I1 | 71 | 29 | 38 | 50 |
| I1→E1 | −531 | −369 | −526 | −379 |
| I1→E2 | −172 | −93 | −121 | −116 |
| E1→I2 | 80 | 56 | 84 | 98 |
| E2→I2 | 231 | 145 | 215 | 164 |
| I2→E1 | −387 | −241 | −328 | −364 |
| I2→E2 | −101 | −42 | −56 | −92 |
| E2→E3 | 470 | 312 | 358 | 280 |
| E3→I2 | 274 | 225 | 187 | 222 |
| DNg100→E5 / E4 | 122 / 66 | 88 / 48 | — | 139 / — |

**DNb08 circuit (MANC, DNb08 14061)**
- [DERIVED] DNb08→E1 6, →E4 64, →E5 79; E4→E1 180; E5→E1 392; E5→I2 398; I2→E5 −346; I2→E4 −26; I2→E1 −387.
- [PAPER] "Unlike DNg100, which drives E1 directly, DNb08 is only weakly presynaptic to E1. Instead, E4 and E5 receive strong input from DNb08 and relay excitation to E1. I2 then provides strong feedback inhibition onto all four excitatory interneurons".

**Outputs to motor neurons** [DERIVED; MANC, left-leg MNs summed by module]
- E1 → coxa swing 20, femur reductor 20, substrate grip 20, tibia flex 10 (total 78).
- E2 → coxa swing 159, femur/tr flex 65, tibia extend 64, femur/tr extend 27, coxa stance 5 (total 330).
- I1 → −20 total.
- I2 → −304 total (femur/tr flex −126, tibia extend −89, …).
- DNg100 → 249 onto left MNs directly (coxa swing 120, coxa stance 38, tibia flex 36, …).
- Paper framing: [PAPER] "because both E1 and E2 connect to multiple motor neurons innervating muscles throughout the leg, their differential activation patterns drive motor neurons at consistent phase offsets relative to each other (Fig. 3g,h)." Also: "tracing pathways upstream of motor neurons would miss E1 and I1 because they are not strongly premotor."

### 7.3 Mechanism and theory

- [PAPER] "the predominant mechanism for rhythm generation is that DNg100 drives E1 to excite E2, amplifying the excitation, and E2 then recruits I1 to inhibit both excitatory neurons after some delay (corresponding to the time-constant parameter τ in our model). Since I1 receives no direct input from DNg100, the inhibition onto E1 is eventually released, allowing E1 to reactivate and restart the cycle."
- [PAPER] "a reduced model of the three-neuron circuit that retains only the E1→E2, E2→I1, and I1→E1 connections still produced oscillatory activity (Extended Data Fig. 4b)."
- [PAPER, Discussion, "Theory…"] "In a neural network of threshold-linear units, a three-neuron circuit with two excitatory cells and one inhibitory cell is a mathematically minimal model for rhythm generation… Because neurons in the fly CNS rarely form autapses [28, 29], a minimum of two cells that excite each other (e.g., E1, E2) is required… all minimal circuits identified by our pruning screens followed this E-E-I architecture."
- **Eigen analysis**: [PAPER] "The E1-E2-I1 circuit model has one complex-conjugate pair of eigenvalues with an oscillation frequency of ∼14 Hz (Extended Data Fig. 4c)." Reproduced: 14.04 Hz (see §3.5).

**E-E-I motif census**
- [PAPER] "we found 21,544 instances of this motif in the MANC front leg network, far exceeding the 307 ± 29 (mean ± std) expected from random shuffles of the weight matrix… Among all 21,544 instances… the E1-E2-I1 circuit has the highest intrinsic frequency (Extended Data Fig. 4f)."
- [PAPER] "most of them (19,799 out of 21,544, or 91.90%) contain imaginary eigenvalues".
- [PAPER] Shuffle method: "shuffling all the outgoing connections of each individual neuron, thus preserving the E/I identity of each neuron and its out-degree."
- [DERIVED] I re-ran the notebook's census (intrinsic neurons only; dt = 1 ms; gain 0.75 × median/size; b = 0.03):
  - 21,544 motifs and 19,799 oscillatory ✓.
  - E1-E2-I1 = 14.04 Hz, **rank 1/21,544** ✓.
  - E1-E2-I1 ranks 28/21,544 by the weakest of its four required edges (71 = E2→I1).
  - E1-E2-I2 = 11.48 Hz (rank 37).
  - The mean frequency of the oscillatory motifs is 2.10 ± 1.66 Hz (notebook output).

### 7.4 Inputs to the core from other DNs (Supp. Table 9; MANC, ≥10 synapses; pre→post, NT of pre, count)

Top rows, re-extracted with word coordinates:

| pre DN | → post | NT | synapses |
|---|---|---|---|
| DNg100 10093 (BDN2) | E1 | ACh | 187 |
| DNxl080 10097 | E2 | GABA | 173 |
| DNg74 10532 (web) | E1 | GABA | 160 |
| DNg105 10086 | E2 | GABA | 126 |
| DNxl130 10941 | E2 | ACh | 93 |
| DNxl049 10279 | E1 | ACh | 92 |
| DNfl031 23461 | E1 | ACh | 86 |
| DNfl023 27936 | I1 | ACh | 82 |
| DNg74 10107 (web) | E2 | GABA | 80 |
| DNxl134 10291 | E1 | ACh | 75 |
| DNfl036 19287 | E1 | ACh | 73 |
| DNfl025 27523 | E1 | ACh | 73 |
| DNg93 10420 | E1 | GABA | 72 |
| DNg12 22875 | I1 | ACh | 68 |
| … | | | |
| DNg62 24753 (aDN1) | E1 | ACh | 34 |
| DNg97 10656 (oDN1) | E1 | ACh | 32 |

- [PAPER, Discussion] "The interneurons identified by our pruning screens receive input from other walking-related DNs, including DNg97 (oDN1, [50]) and DNg74 (web, [56]), as well as grooming-related neurons DNg12 [57] and DNg62 (aDN1, [58])."
- ⚠ Plain-text extraction of Supp. Table 9 shifts the NT and count columns by one row. The values above come from coordinate-aligned extraction.

---

## 8. Interventions and results

All numbers below come from the paper or were recomputed from the repository's `figures/*.csv`; n = replicates.

### 8.1 Silencing (deleting a neuron from W)

**DNg100 activation (Fig. 3j)**
- [PAPER] "silencing either E1 or E2 in the intact network abolished all rhythmic activity across all four datasets (Fig. 3j)".
- [PAPER, Fig. 3j caption] "individually silencing E1 and E2 abolished leg motor rhythms, but silencing I1 (MANC), I2 (FANC, mCNS, BANC), and E3 (FANC) did not."
- [DERIVED] Mean scores (fraction ≥0.5), n = 1024:

| dataset | intact | E1 silenced | E2 silenced | inhibitory cell silenced | E3 silenced |
|---|---|---|---|---|---|
| MANC | 0.974 (99.8%) | 0.000 (0%) | 0.005 (0.2%) | I1: 0.938 (99.7%) | — |
| FANC | 0.975 | 0.000 | 0.005 | I2: 0.968 (100%) | 0.510 (52.8%) |
| mCNS | 0.985 | 0.028 | 0.003 | I2: 0.952 | — |
| BANC | 0.987 | 0.014 | 0.035 | I2: 0.993 | — |

The silenced-neuron indices from the notebooks are: FANC E1 481, E2 413, I2 503, E3 525; mCNS E1 1580, E2 1705, I2 1617.

**DNb08 activation (Fig. 5i)**
- [PAPER] "silencing any of the four excitatory neurons abolished rhythmic motor patterns in the otherwise intact network while silencing I2 alone did not (Fig. 5i)"; caption "abolished or significantly degraded".
- [DERIVED] MANC: intact 0.914; E1 0.231, E2 0.469, E4 0.113, E5 0.251, **I2 0.642** (I2 silencing still degrades the rhythm partially).
- [DERIVED] FANC: intact 0.705; E1, E2 and E4 ≈0.001; E5 0.287; I2 0.960.

**DN screen with both E1s silenced (ED Fig. 1d, 16 replicates)**
- [PAPER] "many high-scoring DNs showed significant decreases in motor rhythmicity… This suggests that E1 is a critical node for rhythmic motor output across multiple descending pathways".
- [DERIVED] Collapsed to near 0: DNg100 (0.85/0.84 → 0.00), DNg12 (→ ~0), DNa07 (0.64 → 0.035), DNxn167 and DNxn127 (→ ≤0.10).
- [DERIVED] DNb08 dropped from 0.58–0.73 to 0.19–0.34.
- [DERIVED] ⚠ The top two individual DNs, **DNp41 18153 (0.92 → 0.88) and DNxl091 16683 (0.85 → 0.88), are E1-independent**, as are DNit011 and DNfl031.

### 8.2 Weight noise (Fig. 2f; MANC; n = 512 per σ)

- [PAPER] "Motor rhythms were robust up to 10% added noise (Fig. 2f), which is comparable to the estimated uncertainty in synapse counts…".
- [REPO] Implementation: `W + W*ε`, ε ~ truncated 𝒩(0, σ), ε ≥ −1, so signs and zeros are preserved.
- [DERIVED] Mean score (median) by σ: 0 → 0.974 (0.999); 0.05 → 0.965; 0.1 → 0.954 (0.999); 0.15 → 0.884; 0.2 → 0.814 (0.998); 0.3 → 0.669 (0.931); 0.5 → 0.435 (0.247).

### 8.3 Parameter variance (ED Fig. 2a–c)

- [PAPER] "Widening the initial distribution of all biophysical parameters decreased the overall motor rhythmicity scores for the top scoring DNs, but the ones we chose to focus on this paper (DNg100 and DNb08) were still among the highest scoring DNs… the most sensitive parameter was the gain."
- [DERIVED] DNg100 with 3× SD: mean 0.669 (70.8% ≥0.5). Restoring one parameter's SD gives: gain 0.862, threshold 0.754, τ 0.703, r^max 0.669.

### 8.4 Size normalisation removed (ED Fig. 2d)

"the size normalization was removed and the input to DNg100 was reduced to an amplitude of 12". This gives no robust oscillations (quote in §3.3).

### 8.5 b per neurotransmitter (ED Fig. 2e)

[PAPER] "Increasing b_ACh to 0.045 still produced viable oscillatory dynamics, but larger deviations resulted in either runaway network activity or insufficient neuron recruitment… At b_ACh = 0.03, a broad range of b_GABA and b_Glu values produced stable oscillatory outputs."

### 8.6 Isolated core circuit (Fig. 3h,i; ED Fig. 4a,b)

- [PAPER] "Motor rhythmicity scores of the three-neuron circuit were comparable to the full VNC network across independent simulation replicates (Fig. 3i)".
- [REPO] The core-only runs keep {DNg100, E1, E2, I1} plus all MNs (`keepOnly: [31, 277, 617, 1167]`).

### 8.7 Input strength and frequency (Fig. 2g; ED Fig. 4a; ED Fig. 10a)

**Full network**
- [PAPER] "increasing the magnitude of DNg100 stimulation increased the frequency of motor neuron oscillations in simulation (Fig. 2g)".
- [DERIVED] Median MN frequency, MANC full front-leg network: I = 220 → 9.6 Hz, 260 → 11.0, 300 → 12.0, 340 → 12.7. At I = 180 most replicates had no active MN.

**Core circuit only**
- [PAPER] "increasing DNg100 input magnitude did not modulate oscillation frequency in the reduced circuit (Extended Data Fig. 4a)".
- [DERIVED] Core-only median: 16.3 → 16.7 → 16.9 → 17.2 Hz, essentially flat and faster than the full network.

**DNb08**
- [PAPER] "Increasing the rate of DNb08 activity did not produce frequency scaling (Extended Data Fig. 10a)".
- [DERIVED] Medians: 13.0 (I = 55), 12.7 (65), 12.8 (75), 12.3 (85), 10.9 (95), 2.5 Hz (105).

### 8.8 Bilateral activation and phases (Fig. 4c–e)

- [PAPER] "Within each leg, we observed a consistent phase offset between antagonistic muscles (coxa promotor and remotor; Fig. 4d,e). However… no consistent phase relationship emerged between the left and right coxa promotor motor neurons".
- [REPO] The MNs used were left coxa promotor 12686 ("Tergopleural/Pleural promotor MN", coxa swing), left coxa remotor 12096 ("Pleural remotor/abductor MN", coxa stance) and right coxa promotor 12628.

### 8.9 Full MANC, six legs (Fig. 4a,b; n = 128)

- [PAPER] "Bilateral activation of the two DNg100 axons produced oscillatory activity in the core CPG neurons and a subset of motor neurons of all six legs… Motor rhythms were somewhat less robust in the hind legs".
- [PAPER] "phase coupling was absent across the six leg CPGs in the full connectome simulation (Extended Data Fig. 9b)".
- [DERIVED] Median score per leg: T1L 0.887, T1R 0.687, T2L 0.452, T2R 0.936, T3L 0.215, T3R 0.716; all legs 0.700.
- [DERIVED] Median active MNs per leg: 2, 1, 1, 2, 2, 13.

### 8.10 Right DNg100 (ED Fig. 6)

"DNg100 R activation consistently produces motor rhythms (n = 1024 replicates)"; pruning is summarised in §6.3.

### 8.11 LIF (ED Fig. 5)

[PAPER] "we simulated the same circuit using leaky integrate-and-fire neurons and found similar patterns of rhythmic spiking activity (Extended Data Fig. 5)".

---

## 9. Cross-connectome validation

**Which datasets.** MANC (male VNC), FANC (female VNC; T1L only), mCNS (male CNS; VNC synapses only), BANC (female brain+cord; VNC bounding box).

**How the circuit was identified in each dataset**
- The pruning screen was re-run independently in each dataset (1024 screens each). Resulting neurons were then labelled with MANC-style types.
- mCNS and BANC use native type annotations (`type`, `cell_type`). The BANC table also carries `manc_121_match_id` cross-references to MANC bodyIds.
- FANC has only hemilineage-level labels in the table. **How FANC neurons were matched to MANC types is not described [NOT STATED]** (morphology comparison is implied by ED Fig. 8).
- [PAPER, ED Fig. 4g] "Connectivity of the E1, E2, E3, I1, and I2 neurons in the front left leg neuropil of all four connectome datasets."

**DNg100 activation results** (Fig. 2e)
- [PAPER] "Across all four connectomes, DNg100 reliably drove rhythmic activity in front leg motor neurons (Fig. 2a–d), with comparable rhythmicity scores despite some variation in the number of recruited motor neurons (Fig. 2e)."
- [PAPER, Fig. 2e caption] "DNg100 typically recruited 2–10 leg MNs."
- [DERIVED] n = 1024 each:

| dataset | mean score | median | fraction ≥0.5 | median active MNs (range) |
|---|---|---|---|---|
| MANC | 0.974 | 0.999 | 99.8% | 3 (0–6) |
| FANC | 0.976 | 0.992 | 99.9% | 8 (4–10) |
| mCNS | 0.985 | 0.994 | 100% | 8 (6–16) |
| BANC | 0.984 | 0.999 | 99.3% | 6 (1–13) |

**Pruning** — see §6.3. The inhibitory partner differs across datasets: I1 in MANC; I2 in FANC, mCNS and BANC.

**DNb08 activation** (Fig. 5b)
- [PAPER] "DNb08 activation consistently produced leg motor rhythms in MANC, FANC, and mCNS, though not the BANC".
- [DERIVED] Mean (fraction ≥0.5): MANC 0.914 (96%), FANC 0.712 (85.5%), mCNS 0.803 (87.8%), **BANC 0.000 (0%)**.

**Stated discrepancies**
- [PAPER, Limitations] "Our key findings replicate across all four connectome datasets, but we observed some differences (Fig. 2e, Fig. 4b, Fig. 5b). Most notably, DNb08 failed to drive rhythmic activity in one of the four datasets. We also saw differences in the identities of recruited motor neurons, both across datasets of the same leg and across leg neuropils within the same dataset. These differences likely reflect multiple factors, including variation in motor neuron reconstruction fidelity and synapse detection (Extended Data Figs. 4g and 9a, also see [67])."
- [PAPER] Suggested remedy: "tuning the synaptic scaling parameter b separately for each dataset or neuropil."

**Methodological asymmetries between datasets** (my observations)
- The 5-synapse floor is applied in MANC/mCNS but not in FANC/BANC.
- Size is volume in MANC/mCNS and surface area in FANC/BANC.
- NT source: `predictedNt` (MANC), `consensusNt` (mCNS), verified-else-predicted (BANC), hemilineage plus overrides (FANC).
- FANC is T1L only, whereas the others contain both front legs.
- I_stim: MANC 250, FANC 150, CNS datasets 400.

---

## 10. Wet-lab validation

### 10.1 In this paper

**Only descending neurons were manipulated.** None of E1, E2, I1, I2 or E3–E5 was manipulated experimentally. [PAPER, Discussion] "Testing the remaining predictions will require the creation of new genetic driver lines that specifically label the core CPG interneurons. Chief among these predictions is that optogenetic silencing of E1 and/or E2 will abolish DNg100-driven leg motor rhythms."

**Genotypes** [PAPER, Methods table]
- DNg100>CsChrimson = `w[1118]/w[1118]; VT058557-GAL4.AD/+;R85F12-GAL4.DBD/20xUAS-CsChrimson-tdTomato su(Hw)attP1` (Figs. 2h–j, ED Fig. 3).
- SS70620>CsChrimson (DNb08) = `w[1118]/w[1118]; P{R94D12-p65.AD}attP40/+; P{VT031392-GAL4.DBD}attP2/20xUAS-CsChrimson-tdTomato su(Hw)attP1` (Fig. 5c–e).

**Methods** [PAPER, Methods, "Optogenetics experiments with 3D joint kinematics"]
- "female flies were cold-anesthetized, de-winged, decapitated, and tethered"; DNg100 flies were 10–12 days old and DNb08 flies 2–5 days old.
- DNg100 flies walked on "an air-supported spherical treadmill (0.13 g, 9.08 mm diameter)".
- Stimulation: "LED laser (638 nm, 1200 Hz, 30% duty cycle…) was focused at the body-coxa joint of the front left leg"; trials were 5 s pre / 5 s stim / 5 s post, in blocks of 8 stim and 4 control.
- Tracking: 6 cameras at 300 fps; DeepLabCut and Anipose; FicTrac at 30 FPS.
- Stepping frequency was measured from the tarsus-tip anterior–posterior position with `find_peaks` (prominence 0.15, minimum distance 50 ms).
- Laser intensities: 0.03, 0.09 and 0.33 mW/mm².

**DNg100 result**
- [PAPER] "Increasing laser intensity led to an increase in both forward velocity and stepping frequency (Fig. 2i–j)."
- Fig. 2i: "n = 7 flies, 8 trials per fly". Fig. 2j: "p = 0.032, 0.352, and 0.042 for paired t-tests comparing low-medium, medium-high, and low-high laser intensities".
- [PAPER] "DNg100 activation produced forward walking on the ball, but at a lower speed than is typical of wild-type flies [53]. They generally exhibited a tetrapod coordination pattern (Extended Data Fig. 3)."
- ⚠ The medium-versus-high comparison was not significant (p = 0.352).

**DNb08 result**
- [PAPER] "we optogenetically activated DNb08 neurons in decapitated flies and found that they reliably produced rhythmic leg movements (Fig. 5c–e…). However, these movements differed qualitatively from the coordinated walking driven by DNg100 stimulation—they resembled the searching movements that insects exhibit when their legs are not in contact with the ground [55]. Indeed, movements were evoked more reliably when the spherical treadmill was removed."
- Fig. 5e: "n = 10 flies, 8 stim-on and 4 stim-off trials per fly… p = 0.036, 0.004 for paired t-tests comparing stimulus on vs. off trials for front and middle leg".
- [REPO, Anipose notebook] "DNb08 was recorded off-ball".
- The driver comes from Zung et al. [54]. DNb08 is also "a descending output of the aggression-associated neuron AVLP491 in the male brain [66]".

### 10.2 Follow-up: Sapkal N, Kumar DS, Sunke S, Mancini N, Pitchford J, Murakami K, Bidaye SS, "Central versus peripheral neural control of a coordinated walking pattern in Drosophila", bioRxiv 10.64898/2026.04.29.721658

Version history: v1 2026-05-03, v2 2026-05-05; Max Planck Florida Institute for Neuroscience; CC BY-NC-ND 4.0. I read v2 in full.

**It does NOT experimentally test the E1/E2/I1 circuit**
- There are no VNC interneuron manipulations. Manipulations target DNs (split-GAL4 lines for DNg100, DNg97 and MDN, plus DNg16, DNg55, DNg75 and BPN co-stimulation) and FeCO proprioceptors (iav-LexA > GtACR1). Proximal joints were immobilised and legs amputated.
- **IN16B036 (I1) is never mentioned** ("16B" does not occur in the text).
- [FOLLOW-UP, Discussion] "these putative CPG motifs (from our work and the modeling study26) and the experimental assays established here, provide perfect entry points into functional characterization of the CPG neurons in future."
- [FOLLOW-UP, Introduction] Pugliese et al. "provides a putative single-leg stepping CPG circuit, where we know each neuronal type and all the connectivity26, yet it remains to be functionally verified."
- [FOLLOW-UP, Acknowledgments] "We thank John Tuthill and Bingni Brunton for sharing their CPG modeling results prior to publication."

**Relevant behavioural findings**
- [FOLLOW-UP, Results] Decapitated flies with optogenetic DN stimulation stepped in four conditions: ball, slippery surface, air, and air with legs amputated mid-femur.
- "In case of DNg100 stimulation, all six legs show rhythmic forward-stepping across all four conditions".
- Frequencies: "DNg100 (all legs step at ∼11 Hz) and DNg97 (only front legs step at ∼11 Hz)" in air. DNg100+DNg97 air-stepping front legs reached "∼22 Hz". MDN hind-leg air-stepping was 7.6 Hz versus 2 Hz on the ball.
- [FOLLOW-UP, Abstract] "We provide evidence that each leg is governed by its own CPG module with an inherent cycle period that is unmasked when proprioceptive feedback is reduced."
- This supports the Pugliese premise of per-leg central rhythm generators, and the ~11 Hz rate is close to the model's ~10–14 Hz. It does not test the identity of the rhythm-generating neurons.

**Their independent connectome search**
- [FOLLOW-UP, Methods] "Male Adult Nerve Cord (MANC v1.2.3)8 and Male Central Nervous System (MaleCNS v0.9)47 connectomes were accessed using the neuprint-python package (0.5.2)96. Brain And Nerve Cord v626 (BANC)48 synapse and neuron table was downloaded from https://codex.flywire.ai/api/download?dataset=banc."
- Criterion: the top-100 T1 outputs (≥5 synapses) of DNg100 and DNg97, rank-summed, top 10 per side, shared between left and right.
- [FOLLOW-UP, Methods] "we found 5 putative 'CPG-motif' neurons: IN03A006, INXXX464, IN12B003, IN17A001 and IN09A002".
- The "expanded CPG-motif" adds 8 neurons from a 2-hop CPG→MN path with ≥250 synapses from CPG neurons.

**Overlap with Pugliese et al.**
- [FOLLOW-UP, Discussion] "the CPG motif we identified based on our empirical data shares several neurons (IN17A001, IN3A006, INXX464 from main CPG-motif and INXX466, IN19A007 from expanded CPG-motif) with CPG candidates identified by Pugliese et al.26… while also presenting candidates that were not identified in the modelling study. (IN12B003 and IN9A002)."
- That is: E1, E4 and E5 are in their core motif; E2 and I2 are in their expanded motif; I1 is absent.
- [FOLLOW-UP] "We found that IN12B003 identified in our work, but absent from Pugliese et. al CPG-motif, has a strong influence on tibia-flexors, a walking-relevant group of motor neurons that did not show rhythmic activity in the modeling work. We therefore speculate that the actual CPG might comprise neurons beyond what are predicted in either of these studies."

**Other circuit proposals**
- Interleg coupling: 19B commissural (AN19B9, 19B5) → 19A local inhibitory for left–right alternation, and 19A intersegmental → 19A local for ipsilateral antiphase coupling.
- DNb08 is noted as providing direct input to their core CPG-motif (Extended Data Fig. 12).

---

## 11. Limitations and caveats

### 11.1 Stated by the authors

- **Missing biophysics.** [PAPER, Intro] "Existing fly connectome datasets lack important biophysical and molecular parameters, such as the expression of ion channels, receptors, neuromodulators, and gap junctions."
- **Muscle activation is not naturalistic.** [PAPER, Limitations] "other muscles likely active during walking, including the main tibia flexors [45], were either silent or non-rhythmic in our simulations. This suggests that although the feedforward signals from the CPG circuit may be sufficient to initiate cyclic stepping movements, the naturalistic pattern of muscle activation likely relies on additional factors: proprioceptive feedback, mechanical coupling, neuromodulation, or combinatorial activity of multiple DNs."
- **No tripod coordination.** [PAPER] "Our DNg100 simulations did not produce the tripod interleg coordination pattern characteristic of hexapod walking. Several VNC neurons connect the left and right CPG circuits disynaptically, but their inclusion was insufficient to couple the phase of the left and right legs."
- **Frequency scaling needs more than the core.** [PAPER] "This frequency scaling was absent in the minimal three-neuron CPG circuit, suggesting that additional interneurons in the full network contribute to frequency modulation beyond the core rhythm-generating mechanism."
- **Cross-dataset differences** (quote in §9).
- **No DN–DN interactions in the brain.** [PAPER] "DNs appear to be recruited as populations… Future models could therefore incorporate DN-to-DN connectivity".
- **Screen false negatives.** [PAPER, Methods] "likely include false negatives: DNs that drive biological rhythms but were missed by our screen due to parameter discrepancies with the true biological system, or because our approach specifically identified network oscillators and could not detect rhythms that rely on intrinsic cellular properties such as bursting."
- **Permissive success criterion.** [PAPER, Discussion] "our criteria for success, rhythmic activity of leg motor neurons, was deliberately permissive, making the results insensitive to precise parameter values."
- **Intrinsic properties untested.** [PAPER] "Direct electrophysiological recordings will be required to confirm or refute these intrinsic properties". v1 added: "it is also possible that cells in the circuit are intrinsically bursting or possess other membrane properties that contribute to rhythm generation."

### 11.2 Modelling assumption versus measured data (my assessment)

**Measured or annotated (data)**
- EM synapse counts from automated synapse detection. The error in these is acknowledged; ~10% noise tolerance was shown.
- Neuron size (voxels or mesh area).
- Cell-type and hemilineage annotations.
- MN muscle-module annotations (from prior studies [32]).
- NT *predictions* (MANC/mCNS classifiers; BANC "verified" where available).
- Behavioural optogenetics (DNg100 speed/frequency; DNb08 leg rhythms).

**Assumptions (not measured)**
1. **Sign equals predicted NT**: ACh is excitatory; GABA and **glutamate are inhibitory** (e.g. via GluCl) at every synapse. Excitatory glutamate receptors, co-transmission and classifier errors are ignored. I1 (Glu, 0.95) and I2 (GABA, prob. only 0.69 in MANC) are inhibitory only by this rule. FANC signs come from hemilineage with 4 hand overrides. The handling of octopamine, serotonin, histamine or dopamine neurons in mCNS/BANC is not stated.
2. **Weight = synapse count × one global scale b = 0.03**. There is no receptor, dendritic-location or plasticity weighting, and no synaptic time constants or delays. The only temporal filter is the cell τ (~20 ms).
3. **Excitability scaled by size** (gain ÷ size, threshold × size). The authors call this "critical", but it is a heuristic, not measured input resistance.
4. **Rate neurons with a rectified tanh.** There are no spikes and no intrinsic bursting, plateaus or post-inhibitory rebound. All oscillation is network-generated by construction.
5. **Parameter distributions** are chosen by hyperparameter search on toy monosynaptic networks. They are randomised, not fitted to physiology.
6. **No gap junctions** (absent from connectomes), **no neuromodulation**, **no sensory feedback or biomechanics** (sensory axons are nodes but receive no drive), and no noise or spontaneous activity.
7. **Stimulus**: a tonic step into one DN's input, in arbitrary units, with the amplitude hand-set per dataset (250/150/400) or auto-tuned in screens. DNg100's real firing is not modelled.
8. **Readout**: rhythm is judged only from MN rate autocorrelations averaged over all active MNs, pooled across both legs. The 0.5 threshold is arbitrary. MN outputs inside the VNC are signed negative (glutamate).
9. **Silencing is deletion** of all in- and out-synapses, which is stronger than experimental silencing.
10. **Minimal circuits are "sufficient" only within the model.** They depend on stochastic, greedy removal order and parameter seeds, and different datasets give different inhibitory partners.
11. **Dataset-specific preprocessing** (floor, size metric, NT source, subnetwork extent) differs across the four connectomes.
12. **Experimental validation covers the DN-level predictions** (DNg100 speed; DNb08 rhythmicity). **No interneuron-level prediction (E1/E2 necessity, I1/I2 redundancy) has been tested experimentally**, either here or in the Bidaye-lab follow-up.

---

## 12. Motor neurons and descending neurons

### Leg motor neurons (MANC front-leg network) [REPO]

**Counts**
- 144 MNs of subclass "fl" (72 left, 72 right).
- 138 carry a `motor module` label from Lesser/Azevedo et al. [32].
- Per side: tibia flex 15, femur/tr flex 11, substrate grip 9 (L) / 8 (R), tarsus control 7/8, coxa swing 7, coxa stance 6, femur reductor 6, femur/tr extend 6, tibia extend 2, unlabelled 3.
- The `step contribution` column is swing / stance / other.

**Left-leg MN names** (type column)
- Coxa swing: "Tergopleural/Pleural promotor MN" (12396, 12686, 13490, 19319), "Sternal anterior rotator MN", "Sternal adductor MN".
- Coxa stance: "Pleural remotor/abductor MN" (12096, 13628), "Sternal posterior rotator MN".
- Femur/tr extend: "Tergotr. MN", "Tr extensor MN".
- Femur/tr flex: "Tr flexor MN", "Acc. tr flexor MN".
- "Fe reductor MN".
- Tibia extend: "Ti extensor MN" (11657, 12704).
- Tibia flex: "Ti flexor MN", "Acc. ti flexor MN".
- Tarsus control: "Ta depressor/levator MN".
- Substrate grip: "ltm MN", "ltm1-tibia MN", "ltm2-femur MN".
- No module: MNfl10 (17664) and "Sternotrochanter MN" (18579, 100515).

**Predicted NT**: glutamate 125, GABA 6, ACh 2, unknown 7, unclear 4. Probabilities are low (~0.37–0.45 for the coxa MNs).

**Other datasets**: FANC has 69 T1L MNs, where tibia flex is split into A/B/C. mCNS has 130 MNs; BANC 151 by class (see the §5 caveat on BANC module labels).

**Named MNs in figures**
- Fig. 4d,e: MN 1 = left coxa promotor (12686); left coxa remotor (12096); right coxa promotor (12628).
- ED Fig. 5 LIF MN = 12686.
- [PAPER] "the coxa promotor and remotor muscles, which swing the leg anteriorly during swing phase and posteriorly during stance, respectively, were active with a phase offset resembling that recorded in other walking insects [5]."
- [PAPER] "DNb08 recruits the tibia extensor but not the coxa remotor motor neuron (Fig. 5a)".

### DNg100 (BDN2)

- **Copies**: two, one per side (MANC 10093/10339; mCNS 10045/10056; BANC root IDs in §4.1). The FANC network includes only the left-VNC DNg100.
- **Neurotransmitter**: predicted cholinergic in all datasets that have predictions.
- **Side and projection**: the soma of the "left DNg100" is in the right brain hemisphere; the axon innervates the left leg neuropils ([PAPER, Methods]). Each DNg100 contacts >1,400 VNC cells.
- **Direct MN input**: [DERIVED] DNg100 synapses directly on left front-leg MNs (249 synapses, largely coxa swing).
- **Six legs**: [PAPER, Fig. 4a] bilateral activation drives the core CPG neurons in all six legs.
- **Output of core neurons**: [DERIVED] DNg100 also targets E4 and E5 (66/122 synapses in MANC).
- **Behaviour**: [PAPER] a known forward-walking command neuron [50]. [REPO] BANC annotation `other_names` = "BDN2".

### DNb08

- **Copies**: four, two per side (MANC 13892, 14061 LHS; 14680, 14966 RHS; mCNS 12044, 12075, 12189, 12550, instance names include VES082/VES083). All are ACh.
- [PAPER] "Although a study had created a genetic driver line for DNb08 neurons [54], their function had not been previously investigated."
- **Input to the core**: E4 and E5 receive strong DNb08 input.
- **Mechanosensory input**: [PAPER] "E4 and E5 receive substantially more mechanosensory input than E1 and E2 do" (ED Fig. 7c, FANC).

---

## 13. Version differences

**bioRxiv v1 (2025-09-12) versus v2 (2026-04-30)** [compared full texts]

1. **Abstract** rewritten. v1: "…including a command neuron for walking (DNg100). By synthetic pruning of the VNC network, we isolated a minimal three-neuron rhythm-generating circuit… A model of this core CPG circuit is sufficient to generate motor rhythms, and the two excitatory neurons are necessary in the VNC network model." v2 adds "top driver", "necessary and sufficient… across all six legs and in four connectome datasets".
2. **Datasets**: v1 used **MANC and FANC only**; v2 adds mCNS and BANC for Figs. 2, 3 and 5.
3. **DN screen**
   - Replicates: v1 **16**, v2 128.
   - Saturation cap: v1 **500**, v2 1500 neurons.
   - v1 results: "184 (19.7%) failed", "749 remaining, 455 (60.7%…) scored zero", "Only 37 DNs… >0.5".
   - v1 ranking: DNg100 10339 **#1 (0.983)**, 10093 **#2 (0.979)**, DNb08 14061 #3 (0.955). In v2 DNg100 is #3/#4.
4. **MANC synapse total**: v1 "3,780,908", v2 "3,817,772". The repository matrix (last modified 2025-08-14, before v1) sums to 3,817,772.
5. **E5 label**: v1 had a typo, "E5" (INXXX466); v2 corrects it to INXXX464.
6. **Additions in v2 only**
   - E-E-I motif census and synapse-share statistics; highest-intrinsic-frequency claim (ED Fig. 4e–g).
   - Type-level, combinatorial (Dirichlet) and E1-silenced DN screens (ED Fig. 1c–e).
   - 3×SD parameter tests, the no-size-normalisation control and the b-per-NT grid (ED Fig. 2).
   - Full-MANC six-leg simulation (Fig. 4, 23,532 neurons).
   - DNb08 in four datasets (fails in BANC); FANC DNb08 pruning (Supp. Table 8); DNb08 frequency sweep (ED Fig. 10a); second DNb08 circuit (ED Fig. 10e,f).
   - Mechanosensory inputs (ED Fig. 7c); Supp. Tables 2, 5, 6, 8.
   - New Methods subsections: "active" definition, frequency/phase, motif analysis, combinatorial screen.
7. **Removed or reorganised in v2**
   - v1 Supp. Fig. 1 (τ vs frequency: "oscillation frequencies were determined by the range of time constant parameters τ") is gone.
   - The v1 Fig. 2f bilateral-phase panel moved to v2 Fig. 4d,e.
   - v1 Fig. 4 (DNb08) became v2 Fig. 5; v1 Supp. Figs. 1–8 became v2 ED Figs. 1–10; v1 Supp. Tables 1–6 became v2 Supp. Tables 1–10.
   - v1 "Activation screen results were qualitatively similar for the left and right front legs" was dropped.
8. **Pruning details**
   - Right-DNg100 pruning: v1 n = 297; v2 n = 1024.
   - DNb08 MANC non-convergence: v1 "32 screens did not converge to 20 or fewer interneurons"; v2 "37… 15 or fewer".
   - The MANC and FANC DNg100 pruning tables (636/1024, 721 etc.) and the MANC DNb08 table are **identical** in v1 and v2, i.e. the same runs.
9. **Methods changes**
   - v2 adds the I_stim values 400 (CNS) and 180 (FANC DNb08).
   - v2 adds the FANC network size (803) and the DNb08 addition.
   - v2 LIF text adds "without tuning or training specific to our circuit or validation against the physiology of these cells".
10. **Other metadata**
    - v2 adds funding NIH R01NS145438 (J.C.T. and B.W.B.).
    - Author contributions for D.T. changed: v1 "developed the leaky integrate-and-fire neural model"; v2 "designed and implemented several extensions of the model".
    - Affiliation changed from "Neuroscience Graduate Program" to "Graduate Program in Neuroscience".
    - Copyright line changed from "© 2025, Posted by Cold Spring Harbor Laboratory" to "© 2026, Posted by openRxiv".

**PMC/PubMed versus bioRxiv**
- PMC13142387 (PMC version 2) / PMID 42094485 is the **NIH Preprint Pilot copy of bioRxiv v2**. It is not a journal publication. [PMC page] "This is a preprint. It has not yet been peer reviewed by a journal… bioRxiv [Preprint]. 2026 Apr 30:2025.09.12.675944. [Version 2]".
- PubMed/Europe PMC list the journal as "bioRxiv : the preprint server for biology", epub 2026-04-30, and pubType including "Preprint".
- Text content is identical to bioRxiv v2.
- The bioRxiv API reports `published: NA`. The first author's publication page lists it as a bioRxiv preprint.
- **No journal version found as of 2026-09-22.**

**Evidence of a newer, unreleased revision** [REPO + Zenodo] ⚠
- Repo commit 10e7661 (2026-09-15) is titled "new revision".
- The repo notebooks and the Zenodo record (published 2026-09-15) use **Extended Data numbering that differs from v2**. For example, Zenodo lists the DNb08 frequency sweep as "ED Fig 9a" (v2: ED Fig. 10a), the right-DNg100 pruning as "ED Fig 5c" (v2: 6c), the core-CPG input sweep as "ED Fig 3a" (v2: 4a), and the six-leg phase offsets as "ED Fig 8b" (v2: 9b).
- A v3 or journal revision probably exists but is not public. Its content is unknown [UNVERIFIED].

---

## 14. Bibliographic citations and licences

**Paper**
- **Pugliese SM, Chou GM, Abe ETT, Turcu D, Lancaster JK, Tuthill JC\*, Brunton BW\*.** "Connectome simulations identify a central pattern generator circuit for fly walking." *bioRxiv* 2025.09.12.675944. doi:**10.1101/2025.09.12.675944**. v1 posted 2025-09-12; v2 posted 2026-04-30.
- (\*co-senior and corresponding: bbrunton@uw.edu, tuthill@uw.edu.) Affiliations: University of Washington (Graduate Program in Neuroscience; Dept of Biology; Dept of Neurobiology & Biophysics) and the Allen Institute for Brain Science (Turcu).
- Also indexed as PMCID PMC13142387 (version 2) and PMID 42094485 (preprint record).
- **Paper licence**: **CC BY-NC-ND 4.0** (bioRxiv v1, v2 and PMC).

**Code**
- **github.com/smpuglie/Pugliese_2026** (the URL cited in the paper, `smpuglie/Pugliese_cpg_2025`, redirects here). HEAD 10e7661 (2026-09-15).
- **Code licence**: the README says "This project is licensed under the terms of the MIT license" and `pyproject.toml` declares `license = {text = "MIT"}`. However, **there is no LICENSE file**, and the GitHub API reports `license: null`.

**Data**
- **Zenodo "Pugliese et al. 2026 data"**, doi:10.5281/zenodo.22260924 (concept DOI 10.5281/zenodo.22260923), published 2026-09-15.
- **Licence CC-BY-4.0**. About 170 GB in 27 zip archives of simulation outputs (`ckpt/*_Rs.npz`, `neuron_params.h5`, Hydra configs) plus Anipose data.

**Follow-up**
- Sapkal N, Kumar DS, Sunke S, Mancini N, Pitchford J, Murakami K, Bidaye SS. "Central versus peripheral neural control of a coordinated walking pattern in Drosophila." *bioRxiv* 2026.04.29.721658; doi:10.64898/2026.04.29.721658. v1 2026-05-03; v2 2026-05-05. **CC BY-NC-ND 4.0**. Europe PMC record PPR1212118 (no full text there).

**Dataset papers cited by Pugliese et al.**
- MANC: Takemura et al. 2024 eLife [28].
- FANC: Azevedo et al. 2024 Nature 631:360 [29].
- BANC: Bates et al. 2025 bioRxiv "Distributed control circuits across a brain-and-cord connectome" [30].
- mCNS: Berg et al. 2025 bioRxiv "Sexual dimorphism in the complete connectome of the Drosophila male central nervous system" [31].
- Annotation papers: Lesser et al. 2024 [32], Stürner et al. 2025 [33], Marin et al. 2024 [34].
- Tools: neuPrint [81], CAVE [82].

---

## Appendix A — Paper-versus-code discrepancies and reproducibility caveats (my findings)

1. **Rhythmicity normalisation**: the paper's formula divides by max(r); the code divides by (max − min). The code is presumably what was run.
2. **g(x) inline formula** puts θ outside a/r^max; Eq. 1 and the code put it inside.
3. **Eigen-analysis dt**: the stated dt = 0.01 ms does not match the reported eigenvalues; dt = 1 ms reproduces them. The frequency (~14 Hz) is unaffected.
4. **LIF duration**: the paper says 3 s; the notebook uses 0.3 s.
5. **Pruning threshold**: the Results say ">0.5"; the Methods say "≥0.5", which is what the code does.
6. **"Inactive" neurons in pruning**: the code uses max rate ≤ 0 after 250 ms, whereas the paper's global definition of "active" is >0.01 Hz.
7. **Screen saturation**: the code also caps at >100 neurons above 100 Hz, and the starting I_stim is 128. Neither is in the paper.
8. **Size median**: taken over the simulated network, not the "dataset".
9. **MN definition**: current code uses class; the published tallies (MNfl10 appearing as a circuit member) imply a motor-module definition in those runs.
10. **BANC table** in the repository has 27 non-MN rows carrying a motor-module label and 22 MNs without one. This could affect BANC MN-based scoring if that table was used.
11. **File loaders**: `load_W` reads only .npy and .csv, and `load_wTable` only .csv and .pkl. The repository's BANC W (.npz) and full-MANC W/tables (.feather/.npz) therefore cannot be loaded by the shipped code without conversion. The exact inputs for those runs can only be confirmed from Zenodo run configs.
12. **Missing code**: the combinatorial (Dirichlet) DN screen (ED Fig. 1e); the FANC DNb08 network table; and the query code for all four datasets.
13. **The "four datasets × six legs" claim** is not fully supported by the displayed data (see §7.1).
14. **"Top driver" wording** conflicts with the v2 individual-neuron ranking (see §1).

## Appendix B — Verification log

- Recomputed from repository data with exact agreement: DN-screen statistics (74/859/845/332/207/29/233; Supp. Table 1 scores); MANC network size and synapse total (4,604; 3,817,772); sizes of the mCNS, BANC and FANC networks (4,310; 4,963; 803) and full MANC (23,532).
- Circuit tallies: Supp. Tables 3–6 (from notebook outputs); 3,521/4,096.
- Motif census (21,544; 19,799; E1-E2-I1 highest at 14.04 Hz) and eigenvalues (with dt = 1 ms).
- ">1,400 cells" per DNg100.
- Could not verify:
  - Dataset versions.
  - Synapse-confidence thresholds.
  - FANC→MANC matching method.
  - The paper's connectivity percentages (denominators differ).
  - Which BANC table and MN definition the final runs used.
  - Six-leg copies in FANC, mCNS and BANC.
  - Content of the unreleased revision.
  - The Zenodo simulation outputs themselves, which were not downloaded.
