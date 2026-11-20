"""LABEL SIDE of the ledger. Modules here never read prediction files, never import prediction-side modules
(`tables`, `jobs`, `typescreen`, `networks`, `authors`, `baselines`, `controls`, `scoring.pipeline`) and never name the
predictions directory. `tests/test_label_isolation.py` enforces this statically and at run time."""
