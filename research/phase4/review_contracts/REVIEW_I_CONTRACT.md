# Contract: Review I — claims (goal5 section 86), after the one-time hidden evaluation

You review the CLAIMS of a completed study: causal state models of simulated neural systems trained with interventions, locked before
a one-time hidden evaluation. Your room contains the report draft (`report/PHASE4_REPORT_DRAFT.md`), the machine-readable results
bundle it cites (`report/results/`), the frozen protocol (`docs/PROTOCOL.md`) and the locked method's notes.

Separate, for every claim in the draft:
1. SIMULATOR RESULT: what the simulations show (a statement about the benchmark's systems and simulators only);
2. METHODOLOGICAL RESULT: what it shows about the method and the evaluation (e.g. that interventional training improves mediation);
3. NEUROSCIENCE INFERENCE: what it would suggest about neural computation, stated as an inference from simulations;
4. BIOLOGICAL CLAIM: any statement about real organisms (the study makes none directly; flag every sentence that reads like one).

Check that: every number in the draft matches the results bundle; the pre-registered conclusion rule (PROTOCOL section 9) is applied
exactly (P_m, P_t on one item set, the lineage rule for real systems, the primary family with Holm); non-binding criteria, untestable
criteria, abstentions, charged failures and the sensitivity table at both CI ends of every tolerance are reported where they matter;
the claim language matches the evidence (supported / partially supported / unsupported; "simulator-relative"); limitations and
negative results are not buried; selection-induced optimism is not presented as performance.

Write `reviews/I/I_review.md`: a verdict, BLOCKERS (a claim the evidence does not support, a number that does not match, a misapplied
rule), MAJOR, minor, and a table claim -> category (1-4) -> evidence -> verdict. Reply with the blockers and majors.
