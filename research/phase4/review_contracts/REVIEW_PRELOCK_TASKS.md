# Pre-lock review tasks (appended to REVIEW_PRELOCK_COMMON.txt; one per reviewer)

## A — causal representation (goal5 section 78)
Your review file is reviews/A_review.md. Does z actually mediate interventions (state mediation score, interventional closure,
microstate equivalence under intervention, multiple-lift consistency), or does the candidate route intervention effects around z
(e.g. a direct intervention-to-output path, intervention-ID memorisation, history hidden in the encoder or in a large recurrent
memory)? Is the intervention read-in identifiable from the training families and targets, and does it transfer to unseen targets
and kinds through structure rather than lookup? Are shortcut models (intervention-ID, input-only, readout-history) excluded by the
evaluation and by the method's own behaviour? Are the causal claims the method's notes make warranted by the evidence?

## B — system identification / control (goal5 section 79)
Your review file is reviews/B_review.md. Are the training input and intervention designs persistently exciting for the model class?
Is observability adequate (which latent directions are excited by passive data vs interventions)? Is the latent dimension
identifiable and is the dimension rule sound, generic and stable (bootstrap of training interventions)? Is the controlled dynamics
model correctly specified (control-affine / bilinear / nonlinear; instantaneous vs finite vs persistent intervention semantics;
state-dependent read-in)? Is the native lift a well-posed inverse problem (conditioning, constraints, distinctness of lifts)?

## C — computational neuroscience (goal5 section 80)
Your review file is reviews/C_review.md. Are the perturbations meaningful for the simulated circuits (magnitudes, timing,
durations, silencing / connection / parameter semantics in a rate model)? Are conclusions stated as simulator-relative? Are
timescales and dynamics interpreted honestly (e.g. an oscillation phase vs a state; persistent vs transient effects; readout
sparsity)? What would and would not transfer to biological claims?

## D — active experiment design (goal5 section 81)
Your review file is reviews/D_review.md. Does the acquisition function actually improve information efficiency (quality vs
experiments vs simulator cost, with CIs at matched budgets)? Is the random baseline fair (same budget, same candidate space, same
learner, same seeds)? Does the designer merely choose large-effect interventions? Is the active policy overfitting the synthetic
families (does it rely on properties of the development systems that need not hold elsewhere)? Is the success rule of PROTOCOL
section 5.17 applied correctly?

## E — statistics, follow-up (goal5 section 82)
Your review file is reviews/E2_review.md. Re-check the statistics on the composed candidate and the tournament: units, CIs, paired
comparisons, multiplicity, the selection rule's application in every round, selection-induced optimism, the primary family and
non-inferiority margins that will be used at Level C, and the power of the active-design comparison.

## H — numerics / compute, follow-up (goal5 section 85)
Your review file is reviews/H2_review.md. Solver accuracy and determinism of the candidate's fits; CPU / GPU equivalence of any GPU
path (equiv.py); caching correctness of the loop's experiments; reproducibility across hosts; intervention timing inside the
candidate's rollouts and read-in (onsets, offsets, persistent events, sequences).

## G — adversarial traps (goal5 sections 41, 84): separate contract REVIEW_G_CONTRACT.md
