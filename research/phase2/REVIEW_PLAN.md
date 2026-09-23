# Phase 2 independent reviews (goal3 section 47): plan and contracts

Each review is done by a fresh agent with a written contract. Its findings are written to
`research/phase2/reviews/<letter>_<topic>.md`, and each finding carries a severity: blocker, major or minor.

Placement follows one rule: a review whose findings may still change the method runs BEFORE the method lock, in the
oracle-free clean room. A review that needs the hidden answer runs AFTER the lock, in the main repository; its findings
can invalidate the method but never tune it.

| review | question | when | where | inputs |
|---|---|---|---|---|
| A causal discovery | Does the method identify a causal mechanism (sufficiency + necessity under intervention), or only correlated importance? Are its essential/removable claims backed by interventions it actually ran? | pre-lock | clean room | v1 code + method doc, selection/confirmation aggregates, synthetic generators (the reviewer may build its own instances with truth) |
| B optimisation | Is the search/objective correct (budget use, stopping rule, minimality guarantee)? Would a simpler algorithm (greedy_plus alone, single-deletion) do as well at the same budget? | pre-lock | clean room | same as A + all candidate methods |
| C statistics | Are the comparisons paired, the CIs right, the multiplicity handled, the claims supported (synthetic, reliability, transfer, blind result)? | post-lock (after the blind evaluation) | main repo | every results file, SELECTION_PROTOCOL.md, PHASE2_REPORT draft |
| D leakage | Try to prove that hidden-oracle information influenced method design: answer ids/types/sizes in code or configs, clean-room contents and history, the BUILD_REPORT incident, orchestrator commits touching method files, tuning signs in the git history. | post-lock | main repo (oracle readable) | git history, clean room, METHOD_LOCK.json, HIDDEN_EVAL_LOG.md, oracle |
| E cross-connectome | Is transfer legitimate (public anchors, annotations and simulation only) or mapping leakage (curated identity smuggled in)? Is joint discovery's budget accounting honest? | pre-lock | clean room | joint.py, correspondence.py, transfer.py, pair-tournament aggregates, real-network transfer runs (oracle-free) |
| F computational | Are budgets accounted exactly (calls, simulated seconds, CPU, Modal cost)? Is the cache safe (keys, never charged free)? Is Modal reproducible (local vs remote)? Where does the time go? | pre-lock | main repo, but without reading the oracle (infrastructure only) | simulator.py, tournament.py, reliability.py, backend usage, registry records |
| G adversarial | Construct synthetic cases where BrainIR v1 returns a confident but wrong mechanism: high inclusion probability or essential=True on a non-member, missed alternatives, criterion-specific traps. | pre-lock | clean room | v1 code + synthetic generators; reviewer builds its own instances |

## Process

1. Blockers and majors found before the lock are fixed by the method's developer (a clean-room agent). The fix is then
   re-run on the SELECTION suite only; the confirmation suite is still used exactly once.
2. Findings of post-lock reviews are reported in PHASE2_REPORT.md. A method change after the lock creates a new method
   version with a new lock (goal3 section 29).
3. Every review states which files it read. Pre-lock reviewers must not read anything outside the clean room.
