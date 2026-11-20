# Run 1: the prompt's "Done means" list (RUN1_PROMPT section 12), item by item, with evidence

| item | status | evidence |
|---|---|---|
| G0 passed, or the fallback is documented | met | `g0/` (byte-identical MANC builds; authors' matrices exact), LOG L7-L10 |
| `ledger-prereg-v1`, `ledger-predictions-v1`, `ledger-labels-v1` exist, each with hashes and a timestamp proof | met | tags on 2c831da / e8bc214 / 4a015bd (pushed); `LOCK_*_v1.json` + `.ots`; all three locks clean in a clean checkout (LOG L42, L44) |
| every locked arm passed its gates and the independent review | met (table below) | the gates of prompt section 9 as written, per arm; arms review rounds 1-2 verdict LOCK, conditions met (L34) |
| the label tables validate against the schema; the agreement report exists | met | 0 invalid records in every session (L38-L40); `labels/agreement.md`; consensus independently reproduced (`final/REVIEW_labels_round1.md`) |
| the baseline checks still pass | met | `gates/G5_REPORT.md` (pre-lock), `final/G5_END_REPORT.md` (end): identical to the Stage S baseline |
| no label was joined to any prediction | met | `UNBLIND.json` absent everywhere (L44); scoring never run; handoff section 10 |

## Every locked arm against the gates that apply to it (prompt section 9)

The gates as the prompt defines them: G1 = the new screen code reproduces B0 in single-neuron mode (a property of the BrainIR
screen code, so it covers every arm simulated with it); G2 = compare B1 with A1 and, if the rank correlation is below about 0.8,
"find out why before locking"; G3 = full cord on DNg100 (B3 only; failed, so B3 and B6 are NOT locked, as the prompt says);
G4 = re-running a sample gives identical output and every output is hashed; G5 = nothing broken. The prompt sets no
positive-control gate for B2 and no gate on what B4's calls mean; those weaknesses are reported, not gates (LOG L29).

| arm(s) | G1 | G2 | G4 | G5 | independent review |
|---|---|---|---|---|---|
| A1, A1-lo10, A0 (authors' tables) | n/a (no BrainIR screen) | A1 is the reference | built from hash-pinned author files; rebuilt independently from the raw CSVs by the reviewer (round 1); unchanged since (round 2: byte-identical); hashed in the lock | pass | rounds 1-2: verified, LOCK |
| B0 (saved screen, frozen as is) | is G1's reference | n/a | file hash pinned; per-type tables rebuilt from the raw file by the reviewer (round 1); hashed | pass | rounds 1-2: verified, LOCK |
| S (anatomical baselines) | n/a | n/a | deterministic computation; unchanged between reviews (round 2: byte-identical); hashed | pass | rounds 1-2: verified, LOCK |
| B1 = B1-lo10 | PASS (`gates/G1_REPORT.md`) | done as required: 0.792, cause found before the lock, no code bug, 0.864 on types usable in both (`gates/G2_REPORT.md`, hashed by the predictions lock) | `G4_B1-lo10.json` 100/100 | pass | rounds 1-2: LOCK |
| B1-alt = B1-lo5 | PASS (same code) | 0.784, same investigation | `G4_B1-lo5.json` 100/100 | pass | rounds 1-2: LOCK |
| B5 (fixed-strength grid) | PASS (same code) | n/a | `G4_B5.json` 100/100 | pass | round 2: verified (B5 = B1 on 7,091 shared runs), LOCK |
| B4 (walking background) | PASS (same code) | n/a | `G4_B4.json` 100/100 | pass | round 2 item 7: calls recompute exactly; "agree, lock as pre-registered" |
| B2 (MaleCNS) | PASS (same code) | n/a | `G4_B2.json` 100/100 | pass | round 2 item 7: "B2 passed G4 and the network check at the paper's current"; "agree, lock as pre-registered" |
| 10 controls (rewire-101..105, classshuffle-201..205) | PASS (same code) | n/a | `G4_B1-ctl-*.json` 100/100 each | pass | round 2 conditions: 10/10 pass the per-control check incl. G4 (LOG L34) |

Not locked: B3 (G3 failed), B6 (depends on B3).

## Label side

Independent review after the lock (`final/REVIEW_labels_round1.md`): usable with caveats, no blocker. Its two majors are
resolved as far as the frozen rules allow (`final/RESOLUTION_labels_round1.md`): the wrong completeness statistic is
recomputed in `final/COMPLETENESS_ADDENDUM.json` (`ledger/scripts/completeness_addendum.py`, frozen inputs, two defects
varied: 181.6 as reported, 197.1 with the eLife DOI fix, 125.0 also excluding the breaching search session); the coverage
loss cannot be repaired inside v1 (PREREG 12) and is the reason for the labels v2 recommended in the handoff.
