Verdict: freeze after these fixes

# Narrow re-check of the v4 audit fixes (`git diff 5826b84 697cb31`)

Fresh reviewer; text and code of 5826b84..697cb31. `test_v4_*` and `test_lock4` pass (58). Wiring-only checks on both flies (no
simulation, score or agreement), all on 697cb31's `mirror.py`: the working-tree copy changed during this review (not by me).

**What holds.** S_W = L_t and S_M = m(R_t) for all 308 MANC and 250 MaleCNS matched types. Homolog-consistent counts reproduce
(307, 214) and the side-concordant count reproduces (260). The 25 dropped MaleCNS members map to themselves, and no neuron is in two
types. Absent slots have no entries in any H_own/H_rest or in the ten Block 3 hybrids, and presence-flipped slots carry their
source rows. `words`, c >= 0.2, B1.3/B1.4, B3.3, `_diff_interval`, 10,000 resamples, E3/E5/E6, and `lock4._code()` with
`posthoc/` all match the resolution. `FIX_K` has 9, `_std` stores traces, and fixes 1/2 at a gain other than 1 are rebuilt from the
unfixed network. RUN4_PROMPT §3: Modal is the authorised departure; the only new tension is finding 4.

## Findings

1. **MAJOR. Fix 9's left-right criterion is never required** (C6.2 "and 9 if its parts are"; `reliability_v2_bc.py` `_evaluate_fix`,
   `"required": fix in SIDES_DISTINCT`, and `SIDES_DISTINCT` lacks "9"). Fix 9 can become the robust model under a weaker test than
   the text sets.
   *Fix:* `required = fix in SIDES_DISTINCT or (fix == "9" and gha4._fix_parts("9")[1] in SIDES_DISTINCT)`.

2. **MAJOR. A7's new "inconclusive" branch contradicts G7 on closures.** A7 says "every closure read as attribution of whatever
   difference exists". G7 (and the resolution) say a closure is reported only when its before-pair is a real gap. In a plausible
   branch, closures could then be read or suppressed after they are seen. B1.4's "closes the whole gap" (code: `closes_whole_gap`
   only) can likewise fire on an inconclusive before-pair and trigger the reduced plan.
   *Fix:* in A7 write "each block's closures follow G7 on that block's own before-pair; 'closes the whole gap' also requires a
   real-gap before-pair", and make `block1_closes_whole_gap` require `reported`.

3. **MAJOR. X1's Modal safeguards exist only in text.**
   - `gha4.load_results` compares `digest`, which `sweep_v4` results do not carry (`jobs_v4.py`: only `runs_digest`/`digest_v4`).
     The GitHub-vs-Modal refusal is therefore None == None for every sweep (Block 1, fix 1, its gains, dx-1).
   - `modal4.run` and `load_results` never check `TRUST_GATE_v4_modal.json`.
   - `CAP_USD` is unused, and `--budget-usd` only warns after spending.
   *Fix:* compare `digest_v4` (else `digest`) and refuse results with neither; refuse to run or load Modal results unless the Modal
   gate says "identical"; refuse `run` when spent + estimate > $15.

4. **MINOR. Modal hours outside the 300-hour cap create a later choice** (X9: Modal "does not count toward the 300 runner-hours").
   At modal4's prices, $15 is about 235 core-hours. Which campaigns move to Modal, and when, decides whether X9's drops trigger and
   whether exam 2's "60 runner-hours remain" holds.
   *Fix:* fix the Modal allocation at the post-Part-A re-budget, decide drops on GitHub plus Modal-equivalent hours, and state the
   enlarged envelope in departure 12.

5. **MINOR. `dropped_by_presence` omits `columns_from`'s row swap, so it differs from what `columns_from` drops.**
   - It differs in 19 of 616 MANC and 22 of 500 MaleCNS H_own/H_rest hybrids (e.g. MANC DNfl028: 11 vs 4; MaleCNS DNfl036: 14
     vs 6).
   - It feeds B2.5's reported count and the write-once `MIRROR_CHECK_v2.json`.
   - The new synthetic test has no unmatched right member, so no ghost becomes present and row-taking goes untested.
   - The gate omits the B3 hybrids that G4 now names. Both hold on the real flies.
   *Fix:* count nnz before and after the clearing inside `columns_from`, test that count and the ghost case, and write a superseding
   `MIRROR_CHECK_v3.json` (adding the B3 hybrids) before the tag; point B2.3(i) and `_b2_sanity` at it.

6. **MINOR. The primary type set is computed at analysis time by code that X4's analysis clause does not cover.**
   `mirror.homolog_consistent_types` is not on X4's list (`reliability_v2*.py`, `agree.py`, `forward_v1.py`, `rescore_v4.py`), nor
   are `side_concordant_types`, `pooled.py`, or `gha4.load_results`/`c_gains*`. An amendment after collection could move A7's
   branch.
   *Fix:* write the primary, side-concordant and uncorrected type lists to a gates_v4 file before the tag, have the analyses read
   it, and add those modules to X4's list.

7. **MINOR. Step 0's Hungarian ignores annotated groups within a type.** Seven MaleCNS types (DNg09, DNg92, DNg94, DNp16,
   DNut058, DNxn128, DNxn144) leave the primary set although a fully group-consistent within-type pairing exists. "Homolog-
   consistent" therefore partly reflects profile tie-breaking. Separately, unmatched extras' groups are never checked.
   *Fix (text only, keeps 214 and the gate):* state both facts in G9 and list the seven types.

8. **MINOR. A7 omits "not judged" (c < 0.2).** The code (`reliability_v2.py` `A7_branch`) then silently runs the blocks on the
   left-right gap.
   *Fix:* add "if not judged, the blocks run on the left-right gap and the report says the ceiling is too low".
