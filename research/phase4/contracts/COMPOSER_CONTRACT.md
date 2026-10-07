# Composer contract — the composed causal state candidates (Phase 4 clean room)

You are the COMPOSER. Several developers built method families in this room (their code in `src/brainir_causal/methods/<prefix>/`,
their notes in `notes/<prefix>/`); the public tournament evaluated them on held-out validation systems and released AGGREGATE
feedback only (`notes/_tournament_feedback.md`). Your job is to compose the final candidates from the evidence:

- Candidate I, INTERVENTIONAL CAUSAL STATE MODEL: a fresh composition of the components the evidence supports (encoder, controlled
  dynamics, intervention read-in, readout, native lift, dimension rule, abstention and uncertainty, and an experiment-design policy),
  with every choice justified by public evidence (the aggregate feedback and your own experiments on the development data and the
  simulation service), never by guesses about held-out systems.
- Candidate J, SHARED-DYNAMICS CAUSAL MODEL: implementation-specific encoders / read-ins with a shared transition law f, used only
  where the evidence supports sharing (PROTOCOL section 5.14: cross-system sharing is interpreted only for systems whose within-system
  verdict is "causal state supported"; otherwise it reports "prerequisite failed").

Rules: everything in docs/METHOD_DEV_CONTRACT.md applies (generic methods only, no special cases for systems, kinds or suites; no
hard-coded dimension; explicit read-in semantics; every objective term defined with an ablation switch; the ABLATION SWITCHES of
`api.ABLATION_SWITCHES` declared and honoured; deterministic fits within the time limits; `info()` complete). Reuse developers' code
by importing it or copying it into your own package with attribution in your notes; do not modify their files. You may run the
public harness on the development data, the tournament's public evaluator on public data and the simulation service within your
budget. Your prefix is `cm`: your files are `src/brainir_causal/methods/cm/`, `tests/methods/cm/`, `runs/cm/`, `notes/cm/`.

Deliverables:
- `methods/cm/` with Candidate I and Candidate J registered (names `cm_causal_state` and `cm_shared_dynamics`), tests, and
- `notes/cm/COMPOSITION.md`: per component, which family it comes from, the public evidence for it (numbers), what was tried and
  rejected, the identifiability assumptions, the dimension and abstention rules, the ablation switches and what each removes, capacity
  per component, fit time, and the known weaknesses. Reply with a short report when done.
