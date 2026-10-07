# Host-gate study: can AVX-512 hosts run the benchmark bit-identically? (fork P9, 2026-09-27)

Question. The host gate (`p4modal/gate.py`: admissible = no AVX-512, AVX2 present; LOG P3-D26 / P3-D27 / P4-D32) refuses every Modal
host with AVX-512, and refusals are now the main source of wall-time variance (P1: 932-3530 refusals in one dev round). Can AVX-512
hosts produce BIT-IDENTICAL results to the admissible hosts when every numerical library is pinned to its AVX2 code paths?

Answer: **no — keep the gate.** No pin set tried makes any AVX-512 host class bit-identical on every workload; on the most common
AVX-512 class the only pin that aligns OpenBLAS crashes the frozen baseline. The current gate itself is VALIDATED: every admissible
host class met on Modal (two AMD models) is bit-identical on every workload, at 1 and 4 threads.

## Method
- Battery (`scripts/p4/p9_gate_battery.py`, fixed seeds, sha256 of every output array; each workload in its own process in rounds 2-3):
  - gen: the synthetic generator, one development system per type (25 types), nominal and kick runs with the full state,
    true_state and true_latent_effect (construction single-threaded, as the benchmark);
  - real: the real engine on real:A:m1 (nominal + kick) and real:A:full (nominal);
  - refs: reference learner v2 (torch float64): FULL-STATE and TRUE-STATE fits on the toy system, encodings and rollouts;
  - eval: effects (class-balanced jackknife), mediation (ridge, cross-fitting), closure and microstate (whitening, SVD) on the
    toy evaluation data, exact and missing-state models;
  - v1: a fit of the frozen earlier method (BrainIR State v1) with encodings and rollouts.
- Drivers: `scripts/p4/p9_gate_study.py` (round 1) and `scripts/p4/p9_gate_study2.py` (rounds 2-3). A separate Modal app per round,
  never the official classes, with NO gate (every host kind on purpose), one input per container (fresh hosts), three shapes
  (4 / 16 / 32 CPU), the official image (`full_image`: the pinned stack and the official pins `NPY_DISABLE_CPU_FEATURES=X86_V4
  AVX512_ICL AVX512_SPR`, `ATEN_CPU_CAPABILITY=avx2`), extra pins per variant. Run from the Linux driver container.
- Reference: the admissible hosts under the SAME pin set and thread count (they must agree among themselves; they always did).

## Host classes met (174 containers)
| class (vendor / cpuid model / ISA) | containers | gate |
|---|---|---|
| AMD model 1 (Zen 3), AVX2 | 108 | admissible |
| AMD model 49 (Zen 2), AVX2 | 12 | admissible |
| AMD model 17 (Zen 4), AVX-512 | 40 | refused |
| Intel model 85 (Skylake-SP / Cascade Lake), AVX-512 | 10 | refused |
| Intel model 106 (Ice Lake-SP), AVX-512 | 4 | refused |
The admissible share varied by run (19/24, 50/60, 51/90), not reliably by container shape (4 CPU 76 %, 16 CPU 74 %, 32 CPU 57 %).

## Evidence
Pin sets: base (official pins only); mkl (+ `MKL_ENABLE_INSTRUCTIONS=AVX2`, `MKL_CBWR=AVX2`, `ONEDNN_MAX_CPU_ISA=AVX2`); ob
(`OPENBLAS_CORETYPE=Haswell`, the kernels OpenBLAS picks on the admissible AMD hosts); mkl + ob; mkl with `MKL_CBWR=COMPATIBLE` + ob;
mkl with `MKL_CBWR=AVX2,STRICT` + ob; (round 1 also `OPENBLAS_CORETYPE=Zen`, equivalent to Haswell). "=" identical to the same-pin
admissible reference, "≠" different, "crash" SIGSEGV.

| AVX-512 class | pin set | gen | real | eval | v1 | refs (torch) |
|---|---|---|---|---|---|---|
| AMD m17 (10 in r1-r2) | base / mkl | ≠ (rel. 1e-4) | ≠ (2e-5) | ≠ | ≠ (6e-16) | ≠ (3e-16) |
| AMD m17 | any with `OPENBLAS_CORETYPE` forced | = | = | = | **crash** (SIGSEGV in numpy's OpenBLAS: `X.T @ X` / `solve` in the frozen method's `ridge_solve`) | ≠ |
| Intel m85 (4) | base / mkl | ≠ | ≠ | ≠ | ≠ | ≠ |
| Intel m85 | any with `OPENBLAS_CORETYPE` forced | = | = | = | = | **≠** under every MKL mode incl. COMPATIBLE |
| Intel m106 (1) | base | ≠ | ≠ | ≠ | ≠ | ≠ |
| Intel m106 | any with `OPENBLAS_CORETYPE` forced | = | = | = | = | **≠** under every MKL mode |

Micro tests (round 2, each in its own process): on AMD m17 even `np_matmul` (257x257 @ 257x131) and `scipy.linalg.solve` differ with
the Haswell core type forced (np.linalg.svd / lstsq and torch matmul agree); on Intel all numpy / scipy micro tests agree with the core
type forced, and torch matmul agrees only under `MKL_CBWR=COMPATIBLE`, yet the torch reference-learner fits still differ there.

Admissible classes under the official pins (round 3, "gatecheck": every admissible container ran the full battery): 51 containers
(42 AMD m1 + 9 AMD m49), keys gen / real / refs / eval / v1 at 1 thread and refs / eval / v1 at 4 threads: **51 / 51 identical on every
key**. Across rounds, all admissible containers agreed under every pin set tried. Results do depend on the THREAD COUNT (1 vs 4 differ
on refs, eval, v1 on every host), so thread counts must stay fixed per job kind, as the lock and the execution layer already require.

## Proposal
**Keep the gate unchanged.** Reasons:
1. No AVX-512 class reaches bit-identity on every workload under any pin set: torch-based reference fits differ on every AVX-512 model
   (MKL's COMPATIBLE mode aligns torch's matmul but not the fits), and developers' methods will use torch far more broadly than this
   battery; a battery cannot certify arbitrary future method code on a host class that already differs on the benchmark's own code.
2. The largest refused pool (AMD Zen 4, 40 of 54 AVX-512 containers) crashes the frozen baseline whenever OpenBLAS is pinned to its
   AVX2 kernels (a library fault, the same one Phase 3 recorded), and differs without the pin.
3. Intel models 85 / 106 are a small share of the refused pool (14 of 54) and still fail the torch workload.

Hardening worth considering (not an expansion; the orchestrator decides): the gate admits "no AVX-512, AVX2" hosts it has not tested.
Both admissible classes met are verified here, but a future host model that passes the flag test could differ. A container-start
self-test (a fixed micro battery whose hashes must equal the recorded reference; refuse otherwise) would turn the flag rule into a
verified rule at a cost of a few seconds per container.
(Implemented by P1 on 2026-09-27 for every gated class: `p4modal/selftest.py`, research/phase4/LEVEL_B_EXECUTION.md section 9.)

Operational mitigations that keep numerics unchanged: refusals are already cheap (a refusing container stops fetching inputs; P1
re-submits refused inputs at once); keep refusal handling fast and budget for 25-45 % refused placements in wall-time plans.

## Costs (approximate list price from container seconds)
pilot ap-uvz4EtXMDrEEN3c3uyEMMb $0.15; r1 ap-ToyrqRCQHkqLF2m3Nu3x8Z $11.49; r2 ap-JBvO7QUTDgANpAS0seoCOd $6.21; r3
ap-EqqlZaBZ4B73pI54hL5Hvs $7.24; total about $25.1 (research/phase4/MODAL_RUNS.md rows P9-1 to P9-4).
Raw results: research/phase4/host_gate_study/raw_{pilot1,r1,r2,r3}.json; analyses: analysis_{r1,r2,r3}.json.
