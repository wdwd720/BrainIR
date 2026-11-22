# Resolution of the rulebook v4 audit (`PREREG_AUDIT_v4.md`, verdict "freeze after fixes")

Every finding was acted on before the freeze. Code and text changes are in the commits after 5826b84; the audit file itself is
committed unchanged.

| # | finding | resolution |
|---|---|---|
| 1 | BLOCKER: L on M != R on W for 44 MaleCNS and 2 MANC types (the map paired across types) | G4 step 0: the members of each stimulated type are paired within the type (extras unmatched, never paired outside it); `mirror_map` asserts it. `gha4._assert_mirror_stim` refuses to build Blocks 2-3 or floors unless the stimulated set on M is m(R_t) and on W is L_t for every type. The wiring check `gates_v4/MIRROR_CHECK_v2.json` holds this for all 308 MANC and 250 MaleCNS matched types. Primary type set = the homolog-consistent types (every within-type pair shares an annotated group: MANC 307, MaleCNS 214); every Part A-C analysis is repeated on all matched types (G9). |
| 2 | Block 2 hybrids: slots present without inputs or absent with them | `columns_from` takes a presence-changing slot's row from the same network as its presence, and clears every absent slot's row and column (a transplanted connection onto a non-existent neuron is dropped, counted per type and reported, B2.1, B2.5). Synthetic test with an unmatched member and a cross-type group; MIRROR_CHECK_v2 checks it on both flies. The first version of the check (`MIRROR_CHECK.json`) was written before this fix and failed; it stays (LOG L109). |
| 3 | G7 called an interval that reaches 1 "a real gap" | New word "inconclusive" (point < 0.90, upper end >= 1.00); "a real gap" only when the upper end is < 1.00 (`agree.words`). A7: "inconclusive" runs the blocks on the left-right gap and says so plainly; the cross-fly branch only if "at the ceiling". Closures are reported only for "a real gap"; "needed" (B3.3) requires "a real gap". |
| 4 | C6 criterion 2 had no ceiling floor | Criterion 2 requires c >= 0.2 (cross-fly and, where required, left-right); rho_x reported beside the ratio. |
| 5 | Three definitions of the robust model | Any passing fix (1-9), highest SR, ties to the lower fix number (C6; `cmd_c`); `forward_v1` handles fixes 1, 2 and 9 (scores and stability flags from the fix's own runs). |
| 6 | Fixes 1 and 2 at a gain != 1 scored on gain-1 runs; `build_cx(k=2)` crashed | C4: such a fix is screened anew at its gain (four half-flies and the rewired control); `build_cx` / `build_dx` build procedure fixes from the unfixed network plus the gain; no `apply_fix("2")`. |
| 7 | The robust model's whole-type screen could be dropped with Part D | E2 and X9: it belongs to Part E and is never dropped. |
| 8 | MANC's 90 % threshold chosen after seeing 92.4 %, no sensitivity | G3: MANC's left-right comparison and one-bad-side analysis also reported on the 260 side-concordant types. |
| 9 | No rule for when analysis code may be amended | X4: analysis code only before the first collection of the campaigns it reads; any later fix is a recorded amendment with both outputs reported. |
| 10 | B3.1 text vs code (self-mapped partners) | Text now "each matched or self-mapped, not both self-mapped". |
| 11 | B2.3(i) builder check not in `cmd_b2` | `gates_v4/MIRROR_CHECK_v2.json` (written before the freeze, passes on both flies) is part of B2.3(i), and `cmd_b2` requires it. |
| 12 | B1.3 / B1.4 text vs code; winner's curse | Text aligned (transplant on the types accepted on both sides in all 8 seeds, at least 10); the primary procedure measure is the best in-bounds score, fixed now; the others are secondary. |
| 13 | Thresholds only in code | Written into the text: uncorrected / side-concordant sets need at least 10 types; Wilcoxon needs at least 10 non-tied types; all bootstraps use 10,000 resamples (code changed from 2,000); B3.3's "contributes" and "disagree" defined by interval ends, and the disagreements listed. |
| 14 | Dropped MaleCNS members entered the mirror map | They map to themselves. |
| 15 | G7 closure when both screens change | Written into G7. |
| 16 | C6.4 asymmetric; "few = 2" from another procedure | Stated: if the unfixed one-sided rewired control has more than 2 drivers, criterion 4 can be met only by a fix that lowers it; SR uses the left pair because the rewired control is run on the left only. |
| 17 | Part E loose ends | G10 names E9's seed 20261461; E3 "at least 15 headless-labelled types including at least one yes and one no"; E5 states that the authors'-model flags come from our replication; the protocol uses LexAop-CsChrimson for a LexA line. |
| 18 | B4.5 is a failure-to-reject test | The observed minus copy-vs-copy difference is reported with its bootstrap interval, as the number to read. |
| 19 | B5 incomplete | A MaleCNS type-to-type connection no MANC member pair carries is spread over all MANC member pairs of the two types. |
| 20 | `posthoc/*.py` not hashed by the prereg lock | `lock4.CODE_GLOBS` adds `ledger/scripts/posthoc/*.py`. |

Also changed at the same time, on the user's instruction in chat (not an audit finding): Modal may be used for speed, about $15, under
the same trust gate (X1, departure 12).
