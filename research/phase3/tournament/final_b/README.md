# final_b: the Level B confirmation on the synthetic FINAL suite (ANSWER-BEARING)

Run once after the method lock (research/phase3/HIDDEN_EVALUATIONS.md), as 13 parallel parts with one Modal app each
(`research/phase3/tournament/final_b_<method>/`, one driver per method, the same design; the merge checks the design). This
directory holds:
- `AGGREGATE_developer_facing.json`: the merge of the 13 parts (`scripts/p3/merge_rounds.py --parts final_b_* --out final_b`,
  without --decide: nothing is selected on the confirmation suite);
- `<method>.json`: byte-identical copies of each part's per-method result file, so that the tools reading one confirmation round
  (level_c.py K test, self_audit.py, ablations.py --full-from) find every method in one place.

The fitted models stay in the parts' run directories (`$RUN/final_b_<method>/<method>/`, outside the repository).
