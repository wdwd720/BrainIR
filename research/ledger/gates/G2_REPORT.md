# Gate G2: agreement of BrainIR's type-level screen (B1) with the authors' (A1)

B1 kept lower bound 10 by the pre-registered rule (Spearman with A1: 0.792 at 10, 0.784 at 5; difference < 0.01 -> the
authors' value 10). `G2_agreement.json` has the full comparison.

| arm vs A1 | Spearman | top-10 overlap | band agreement |
|---|---|---|---|
| B1 (lower 10) | 0.792 | 8 | 0.85 |
| B1-alt (lower 5) | 0.784 | 10 | 0.85 |
| A1-lo10 (authors, usable >= 10) | 1.000 | 10 | 0.997 |
| A0 (authors' single-neuron screen, per-type max) | 0.755 | 6 | 0.78 |
| B0 (BrainIR single-neuron, per-type max) | 0.656 | 6 | 0.75 |

The correlation is just below the 0.8 investigation threshold, so the cause was investigated (no fly data involved):
1. **Noise ceiling.** Split-half reliability (Spearman-Brown) of the 16-replicate type means: A1 0.933, B1 0.920, so two
   independent measurements of the same ranking could agree up to about 0.93. Pearson A1 vs B1 = 0.913; much of the rank
   gap sits among the ~216 near-zero types.
2. **Read-out (138 vs 144 MNs):** re-scoring every usable B1 replicate on the authors' 138 module-labelled MNs from the
   stored traces changes the Spearman from 0.7920 to 0.7921 (485 of 4,526 usable replicates had one of the six extra MNs
   active).
3. **Usability rule:** 23 types are usable in A1 but never usable in B1 (17 too weak, 6 too strong). On the 293 types
   usable in both, the Spearman is **0.864**. The difference is procedural and documented: BrainIR's tuner (the locked
   `screen_candidate`, mirrored) accepts only a run inside the bounds, including the cap of 200 neurons above 100 Hz,
   whereas the authors' synchronous engine applies its last adjustment untested and their notebook filters afterwards on
   5 <= nActive <= 1500 without the high-firing cap.
4. Remaining differences are consistent with float32 GPU vs float64 CPU integration and independent parameter draws.

No code bug was found (the pre-registered remedy is limited to demonstrated bugs). **B1 is locked as it is; the
disagreement is reported here.** A1 remains the primary prediction.
