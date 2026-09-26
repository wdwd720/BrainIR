# Level C Modal backend: equivalence check on PUBLIC data (benchmark version 3, before the method lock)

No hidden data were used. The stand-in "hidden" set is PUBLIC real validation data: val rows renamed to hidden family names (split
"test") with their public twins (`modal_tournament.build_equiv_hidden`). It was staged at `/evalvol/suites/real_equiv/hidden`.

## Staging (once; `modal_tournament.py upload-real --what view,bundle,internal`)

| item | volume | files | size | upload |
|---|---|---|---|---|
| public real fit view (train / val) | fit: `views/real` | 2,754 | 1,240 MB | 621 s (tar + remote extract) |
| public blind bundle | fit: `bundles/dng100_public_blind` | 18 | 3 MB | 17 s |
| internal system definitions | eval: `suites/real_internal` | 1 | 20 kB | 1 s |

The per-file sha256 digests are recorded in `modal_staging.json`. The hidden real data are staged only after the lock
(`--what hidden`), and only on the EVAL volume; fit containers mount only the fit volume.

## Checks (method `lin_dmdc`; snapshot `BrainIR_p3run/r2_lin_dmdc/methods`; systems `real:net1:mech:02fa13b8`, `real:net2:mech:6883ab7b`)

1. **Heterogeneous Modal hosts change floating-point results unless numerics are pinned.**
   - Without pinning, 4 of 10 containers ran on AVX-512 hosts. On those hosts numpy dispatches to X86_V4 and OpenBLAS uses SkylakeX
     kernels.
   - The real engine then deviated from the stored public trajectory in 2 of 12 simulations: by up to 0.108 Hz (x) and 0.057 Hz (y)
     on `real:net2:mech:6883ab7b`, and 0.034 Hz / 0.013 Hz on `real:net1:full`.
   - Lifting metrics consequently differed by up to 1.3 % relative.
   - **Fix:** the Modal image now sets `NPY_DISABLE_CPU_FEATURES="X86_V4 AVX512_ICL AVX512_SPR"`, `OPENBLAS_CORETYPE=Haswell` and
     `ATEN_CPU_CAPABILITY=avx2`. These are the AVX2 code paths of the development machine.
   - With pinning, 24 of 24 simulations on Modal equal the stored and local trajectories bitwise
     (`modal_sim_hardware_check.json`).
   - **Later change (same day, benchmark v3 before any use):** `OPENBLAS_CORETYPE` was dropped again because it made workers on
     some hosts die with SIGSEGV (`modal_pinning_crash_experiment.json`; research/LOG.md section 11.3). numpy and torch stay pinned.
     The real engine's bit-identity was re-checked with the final image: the Modal backend of the hidden-data generator reproduced
     30 of 30 public records bitwise (`hidden_generator_modal_smoke.json`). Dense linear algebra in fits and evaluation statistics
     may now differ between Modal hosts in the last digits (PROTOCOL.md section 10).
2. **Evaluation of a given fitted model is bitwise identical between local and Modal.**
   - This covers every family, including lifting through the real engine: 0 mismatching leaves out of 490 and 622.
   - The evaluator code tag was the same on both sides (`modal_equivalence.json`, `same_evaluator_code: true`).
3. **Fits are bitwise reproducible across Modal hosts.**
   - Three repeats per system gave identical parameters; only the recorded fit timings differ.
   - Linux and Windows fits differ in their parameters at about 1e-13 relative (compiler and libm level), and give the same k.
   - Evaluated, those fits differ by at most 3e-4 relative in point estimates (the D micro-gain). One D CI endpoint near 0 differs by
     0.0026 absolute: the inner cross-validated choice of the ridge penalty in D is discrete and amplifies float-level differences.
     Four and two of the leaves differed, respectively.
   - **Consequence:** all fits of one Level C run must come from ONE environment. The Modal backend runs every fit on Modal.
4. The bundle-backed simulation service (SimServer + real engine) in a Modal container reproduces the local engine exactly.

Modal cost of all staging and checks: about $0.16. Container-seconds per call are recorded in the JSON files.
