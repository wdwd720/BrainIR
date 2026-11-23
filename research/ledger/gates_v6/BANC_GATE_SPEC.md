# BANC build gate: specification (written before the gate runs; RUN6_PROMPT Stage 1)

**What it tests.** That our build of the authors' BANC front-leg network (`ledger/src/brainir_ledger/banc.py`) behaves as the authors
report for DNg100, using only their published DNg100 results. Nothing else in BANC is stimulated before `ledger-prereg-v6`
(RUN6_PROMPT hard limit 2).

**Runs** (`gha6.py`, campaign `bg-banc-run6`, GitHub Actions; the Mac runs no simulation): the authors' BANC DNg100 (position 1605,
root 720575941500851362; their config, Zenodo run 33241778) stimulated alone at their current 400, T = 2.0 s, the authors' neuron
parameter priors (as every ledger screen), seeds 0..63, on four networks:
- intact;
- E1 silenced (position 1689, IN17A001, root 720575941504247575);
- E2 silenced (position 910, INXXX466, root 720575941469024064);
- I2 silenced (position 3334, IN19A007, root 720575941569601650; descriptive only).

A silenced neuron's row (outputs) and column (inputs) are set to zero; it stays a state variable, as in the authors' `removeNeurons`
mask (their run 34106247 used exactly these three positions). Score = the published rhythm score over the active front-leg motor
neurons (139; t >= 0.25 s; active = peak > 0.01 Hz; prominence 0.05), as every ledger job. A replicate whose solver fails counts as
score 0.

**The authors' published results used** (their notebooks, n = 1,024 each; `research/literature/pugliese_walking_cpg_detailed_notes.md`
sections 8.1 and 9): intact mean 0.984 to 0.987, 99.3 % of replicates >= 0.5, median 6 recruited motor neurons (range 1 to 13);
E1 silenced 0.014; E2 silenced 0.035; I2 silenced 0.993.

**Pass criteria (all three required):**
1. **DNg100 drives front-leg rhythm:** intact mean score >= 0.90 and at least 90 % of the 64 seeds score >= 0.5.
2. **Silencing E1 abolishes it:** mean score <= 0.10 and at most 10 % of seeds score >= 0.5.
3. **Silencing E2 abolishes it:** mean score <= 0.10 and at most 10 % of seeds score >= 0.5.

**Reported beside the criteria, without a pass rule:** I2 silenced (the authors report it does not abolish the rhythm); the number of
active front-leg motor neurons per seed against the authors' median 6 (1 to 13); per-side read-out activity; wall time per job.

**Saved outputs.** The authors' saved per-replicate rate traces (`DNg100_Stim_BANC_vncOnly_Rs.npz`, 702 MB) are part of a whole-run
archive and are not downloaded (RUN6_PROMPT Stage 1). The run log (read, 468 KB) records only a per-replicate maximum firing rate,
which our results do not store; it is not compared. The comparison is therefore with the published summaries above.

**If the gate fails:** one pre-specified diagnostic re-run with the read-out widened to the authors' class-based motor-neuron set
(all 151 `super_class == 'motor'` neurons, neck motor neurons included); no other setting is changed (the matrix is used as released
and K is never touched). If it still fails, no BANC screen is run; the results and the handoff say so in their first line.
