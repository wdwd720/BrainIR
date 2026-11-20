# Run 1: the prompt's "Done means" list (RUN1_PROMPT section 12), item by item, with evidence

**Independently verified** by a fresh reviewer with no access to labels (`final/gates_review/REVIEW_gates_final.md`, with its
evidence files): "Every locked arm passed the gates that apply to it and the independent review: **yes**." Its
qualifications are kept below, and the corrections it asked for are made in this version (LOG L48).

| item | status | evidence |
|---|---|---|
| G0 passed, or the fallback is documented | met | `g0/` (byte-identical MANC builds; authors' matrices exact), LOG L7-L10 |
| `ledger-prereg-v1`, `ledger-predictions-v1`, `ledger-labels-v1` exist, each with hashes and a timestamp proof | met | tags on 2c831da / e8bc214 / 4a015bd, pushed; `LOCK_*_v1.json` + `.ots`; all locks clean in a clean checkout (L42, L44). Labels v1.1 (tag `ledger-labels-v1.1`, a21a380) is a later bug-fix version (L47) |
| every locked arm passed its gates and the independent review | met | per-arm table below; confirmed by the independent gate review |
| the label tables validate against the schema; the agreement report exists | met | 0 invalid records in every session (L38-L40); `labels/agreement.md` (v1) and `labels_v1_1/agreement.md` (corrected completeness statistic); consensus independently reproduced (`final/REVIEW_labels_round1.md`) |
| the baseline checks still pass | met | `gates/G5_REPORT.md` (pre-lock), `final/G5_END_REPORT.md` (end): identical to the Stage S baseline |
| no label was joined to any prediction | met | `UNBLIND.json` absent everywhere (L44); scoring never run on real labels; handoff section 10 |

## Every locked arm against the gates that apply to it (prompt section 8)

The gates as the prompt defines them:

- **G1:** the new screen code reproduces B0 in single-neuron mode. It holds exactly on every decision and within 0.00088 on
  scores; the prompt allows explained small score differences.
- **G2:** compare B1 with A1, and "if the rank correlation is below about 0.8, find out why before locking".
- **G3:** the full cord on DNg100. It applies to B3 only; it failed, so B3 and B6 are not locked, as the prompt says.
- **G4:** re-running a sample gives identical output, and every output is hashed.
- **G5:** nothing broken.

The prompt sets no positive-control gate for B2 and no gate on what B4's calls mean. Those are validity weaknesses no gate tests,
reported before labels existed (L29).

| arm(s) | G1 | G2 | G4 | G5 | independent review |
|---|---|---|---|---|---|
| A1, A1-lo10, A0 (authors' tables) | n/a (no BrainIR screen) | A1 is the reference | built from hash-pinned author files; rebuilt independently by the round-1 reviewer and again byte-identically by the gate reviewer; A0's long replicate table and `neurons.csv` were rewritten after round 1 (writer fix) and round 2 checked every raw cell; hashed | pass | rounds 1-2, LOCK |
| B0 (saved screen, frozen as is) | is G1's reference | n/a | file hash pinned; rebuilt byte-identically by the gate reviewer; hashed | pass | rounds 1-2, LOCK |
| S (anatomical baselines) | n/a | n/a | deterministic; rebuilt byte-identically by the gate reviewer; hashed | pass | rounds 1-2, LOCK |
| B1 = B1-lo10 | PASS (`gates/G1_REPORT.md`) | met by investigation before the lock: 0.792, `gates/G2_REPORT.md` committed 9.6 h before the lock commit and hashed by it; no code bug; 0.864 on the 293 types usable in both. B1 never reached 0.8 | `G4_B1-lo10.json` 100/100 | pass | rounds 1-2, LOCK |
| B1-alt = B1-lo5 | PASS (same screen code) | 0.784, same investigation | `G4_B1-lo5.json` 100/100 | pass | rounds 1-2, LOCK |
| B5 (fixed-strength grid) | indirect: uses `fixed_run`, which G1 did not exercise; B5 equals B1 on 7,091 of 7,091 shared runs | n/a | `G4_B5.json` 100/100 | pass | round 2, LOCK |
| B4 (walking background) | indirect: uses `fixed_run`; calls recomputed independently, 0 mismatches over 475 types at each strength | n/a | `G4_B4.json` 100/100 | pass | round 2 item 7: "agree, lock as pre-registered" |
| B2 (MaleCNS) | PASS (same screen code) | n/a | `G4_B2.json` 100/100 | pass | round 2 item 7: "B2 passed G4 and the network check at the paper's current"; "agree, lock as pre-registered". Gate-compliant only: its positive control fails (0.059) |
| 10 controls | PASS (same screen code) | n/a | `G4_B1-ctl-*.json` 100/100 each | pass | round 2 fully checked rewire-101 and -102. The other eight were cleared through round 2's stated conditions (per-control check incl. G4, L34); the gate reviewer re-verified every condition, and the scoring dry run with all ten controls is reproducible from the repo (`ledger/scripts/scoring_dryrun_synthetic.py` -> `final/SCORING_DRYRUN.txt`: 91 files, 10 controls evaluated, synthetic labels only) |

Not locked: B3 (G3 failed), B6 (depends on B3).

## Label side

- **Labels v1:** an independent review after the lock (`final/REVIEW_labels_round1.md`) found them usable with caveats, with no blocker.
- **Finding 2** (wrong completeness statistic): resolved by labels **v1.1**, the prompt's "new version" route. The reviewer verified it: finding resolved, nothing wrong, scoring inputs byte-identical to v1.
- **Finding 1** (coverage loss): not a bug. It cannot be repaired by re-processing and needs new labeling under a new pre-registration (labels v2, handoff section 9).
