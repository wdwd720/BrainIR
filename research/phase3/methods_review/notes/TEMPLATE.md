# Shared instructions for area notes

## Target problem (from CONTRACT.md, generic)
Simulated population of N units (N ~10 to ~5,000; typically ~100 active), state x(t), external input u(t), readout y(t).
The simulator can be run with arbitrary initial states, input sequences, parameter draws and microscopic interventions
(state offsets, input currents into units, removing units or connections). Goal: encoder z = phi(x) with small k,
transition z(t+dt) = f(z, u), readout y = g(z, u), such that z is:
 (1) predictively sufficient over multiple horizons, (2) approximately Markov (closed), (3) interventionally sufficient
 (predicts effects of held-out perturbations, incl. unseen intervention types and targets), (4) microstate-invariant
 (microstates with equal z have equal futures), (5) minimal in dimension, (6) stable across seeds and estimation procedures,
 (7) shared across different physical implementations of the same computation (implementation-specific encoders, one shared f),
 (8) able to abstain when no compact state exists. Latent coordinates identifiable only up to transformations.

## Rules
- Work only inside C:\Dev\BrainIR_p3lit. Write only to your assigned notes/ file.
- METHODS ONLY. Never search for, read about or discuss any specific biological circuit, organism, connectome or dataset.
  Keep search queries purely methodological (e.g. "LFADS latent factor analysis dynamical systems arXiv", not queries naming
  brain regions, species or datasets). If a paper's experiments use a specific biological dataset, do not describe it.
- Cite only what you actually opened (WebFetch of arXiv abstract page, PDF, proceedings page, docs, or repo). For each reference
  give: title, authors (first 3 + et al.), year, venue, URL, and a tag: [read-full] (read substantial body text),
  [read-abstract] (abstract/landing page only), [repo/docs] (read code repo or docs), or [unverified] (from memory; not opened).
- For licences: check the repo's LICENSE file or GitHub licence badge; write "licence not verified" if you could not.
- Mark claims you could not verify with "(unverified)".
- Judge methods on the properties (1)-(8), not on fashion.

## Entry format (one per method; use exactly these fields)

### <Method name> (<key acronym>)
- **Core idea:** 1-3 sentences.
- **Assumptions:**
- **Identifiability:** (what is recovered, up to which transformation class)
- **Intervention support:** (inputs/controls, do-interventions, perturbation data; can it predict held-out interventions?)
- **Nonlinear capacity:**
- **Interpretability:**
- **Scaling (N, T, data size):** (compute/memory complexity, sample requirements)
- **Failure modes:**
- **Relevance to problem (props 1-8):** (brief, per relevant property)
- **Open-source implementations:** package - URL - maturity (active/stale, stars approx if seen) - licence
- **From-scratch simplicity:** (simple / moderate / hard, and why; key numerical pitfalls)
- **References:** list with tags

## End of each area file, add:
## Area synthesis hints
- Tournament candidates from this area (with a concrete recipe: data generation from the simulator, training objective,
  hyperparameters to sweep, how to choose k).
- Baselines from this area and how to implement each well (numerical details, regularisation, pitfalls).
- Evaluation measures relevant to properties (1)-(8) and known pitfalls (time leakage, output copying, input copying,
  future leakage, parameter-identity leakage, memorisation, dimension cheating through pathological encodings).
- Open problems where literature gives no good answer.
