# Forward ledger v1 (PREREG v4 Part E)

These predictions are made after both exams were unblinded. They are clean with respect to the experiments they predict, because those have not been done.

Probabilities come from a one-variable logistic fit of exam 1's labels on each source's score: training on past results to predict future ones (RUN4_PROMPT hard limit 4).

Atlas caveat: 21 of exam 1's 25 'yes' types rest on the intact-fly atlas alone, and the atlas gives no 'no'; the fit inherits that confound.

Types: 63 (E1). Sources: the authors' model (A1), two-step signed synapse counting (S2).

The authors' model's stability flags come from our replication of it (B1r vs B2r for the two flies, Part A's MANC halves for the two sides), not from the authors' own runs (E5).

Scoring rule (E7): when results arrive, each source is scored by its Brier score against a base-rate guesser that says 0.641 for every type (exam 1's base rate on the fit set).
