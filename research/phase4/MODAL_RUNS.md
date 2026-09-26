# Phase 4 Modal runs (fork E4: backend, GPU benchmark, equivalence)

Every Modal app run by the Phase 4 backend work, in order. Costs are rough list-price estimates at the time of the run (container
seconds x modal.com/pricing standard rates); the billed amounts come from the workspace billing report (`scripts/p3/modal_billing.py`
pattern) at the end of the phase. No `brainir-p3-*` volume is mounted by any of these apps.

| # | UTC start | app (id) | purpose | containers / resources | cost | notes |
|---|---|---|---|---|---|---|
| 1 | 2026-09-26T17:17Z | brainir-p4-gpubench-probe (ap-oCI4WV4mIm53XxWEkaoILI) | GPU type-string probe (`gpu_benchmark.py probe`): nvidia-smi in a bare image | 12 x (1 GPU, 1 core, 2 GiB) | billed $1.06 | all 12 strings accepted (A10G = alias of A10); RTX-PRO-6000 waited ~8 min for capacity |
| 2 | 2026-09-26T17:26Z | brainir-p4-gpubench (ap-mOdsMR5OXIC9AXaCVLIb14) | benchmark pipeline check (`run --devices cpu8,L4 --quick`) | 4 x cpu8 (16 GiB), 1 x L4 | billed $0.19 | end to end OK; one OOM on L4 (gru 200/16 T=2000 B=256) |
| 3 | 2026-09-26T17:31Z | brainir-p4-gpubench (ap-ciplWhOEdsnMPSUsr7fvX8) | GPU / CPU benchmark (`gpu_benchmark.py run`, 16 devices x 4 workload kinds x 8 shapes) | 20 CPU containers (4-64 cores, gated; 127 AVX-512 refusals re-submitted), 11 GPU containers (T4 ... B300, 4 cores / 32 GiB) | billed $13.14 (list-price estimate of compute time $10.84) | `research/phase4/GPU_BENCHMARK.{json,md}` (+ `.raw.json`); 3 OOM cases recorded |
| 4 | 2026-09-26T17:44Z | brainir-p4 (ap-YcHuyhg10DqogEf6dtVAmM) | simulation smoke test (`modal_p4.py smoke-sim`): 21 protocols (1 full network, 2 mechanisms; every event kind of protocol v2), cache pass, restarts, full-record path | class `sim` (8 cores, 32 GiB, gated), `util` | billed $0.031 | all bit-identical to the local engine; 19 AVX-512 refusals re-submitted; `research/phase4/modal_smoke_sim.json`; smoke records in the store volume under `smoke_20260926T104445/` (not the production sub-store) |
| 5 | 2026-09-26T17:46Z | brainir-p4-equiv (ap-tH8Q2U6lKH4CJNObaECQLL) | CPU / GPU equivalence, first version (float32-initialised reference trainer) | 5 GPU classes (L4, A10, A100-80GB, H100, B200), 4 cores / 32 GiB | billed $0.58 | SUPERSEDED by run 9: GPU vs CPU passed, but the float32 initialisation made local Windows vs Linux differ by ~1e-7 (diagnosed in runs 6-8) |
| 6 | 2026-09-26T17:53Z | brainir-p4 (ap-23qX72eDLkEHEC5nQkhdQ7) | numerics diagnostic: the reference trainer's CPU run in `fit_s` (gated, pinned), `util` (ungated, pinned) and `gpu_l4` (CUDA image, CPU path) | 3 containers | billed $0.015 | the three Linux CPU runs identical; all differ from local Windows from the first loss |
| 7 | 2026-09-26T17:55Z | brainir-p4 (ap-kSXwSwLGwFwnTr8MgFL3GA) | numerics diagnostic: float64 kernels (tanh, exp, matmul, linear, rollout losses) Linux vs local | 1 x fit_s | billed $0.001 | exp <= 8 ulp; matmul ~2e-13; losses from the float32 initialisation |
| 8 | 2026-09-26T17:56Z | brainir-p4 (ap-Xd8Ki87qinobSHsOj4c8DC) | numerics diagnostic after the fix (float64 initialisation): local vs Linux CPU, 0 and 50 steps | 1 x fit_s | billed $0.031 | float64 agreement 1e-16 (rollout) / 2e-15 (GRU) after 50 steps |
| 9 | 2026-09-26T17:57Z | brainir-p4-equiv (ap-Ft0S1xqUC7XA9RhDEZ9htQ) | CPU / GPU equivalence (`modal_p4.py equiv-gpu`), float64-initialised reference trainer | 6 GPU classes (L4, A10, A100-80GB, H100, B200, RTX-PRO-6000) | billed $0.51 | all pass; GPU run to run bitwise identical everywhere; `research/phase4/GPU_BENCHMARK.equiv.json` and the equivalence section of GPU_BENCHMARK.md |
| 10 | 2026-09-26T18:04Z | brainir-p4 (ap-gHUfrOBaB9gQYjWsV3XE1W) | guarded method-job smoke test, first version | 1 x fit_s, 1 x eval_s | ~$0.005 (estimate) | fit guard refused numpy's ctypes.dlopen at first import; eval guard left /proc/1/environ readable. Fixed in the container sitecustomize (numerical stack imported before the guard; other processes' /proc refused) |
| 11 | 2026-09-26T18:06Z | brainir-p4 (ap-mhi8JwwI9dmqKRjR8rCPo8) | guarded method-job smoke test, after the fixes | 1 x fit_s, 1 x eval_s | ~$0.005 (estimate) | fit and eval guards: every forbidden access blocked (volumes, repository, other jobs, other processes' /proc incl. chdir and /proc/self/root routes, processes, network); per-job simulation service works (hidden seed refused) |
| 12 | 2026-09-26T18:07Z | brainir-p4 (ap-pWCOpLBX0j5Rn7VZ00LI4B) | the same + a full network through the per-job service twice (volume cache across jobs) | 3 x fit_s, 1 x eval_s | ~$0.006 (estimate) | first full-network job computed 1 trajectory in the container, the second was served from the store volume; `research/phase4/modal_smoke_method.json` |

Billed total of runs 1-9 (billing report, hour 17:00 UTC): $15.56. Runs 10-12 fall in the 18:00 UTC hour (not billed yet at the time of writing).

Volume contents written by these runs: `brainir-p4-store` holds the smoke sub-store `smoke_20260926T104445/` (run 4; orchestrator
test protocols) and ONE public-policy record in the production sub-store `store/` (run 12: a kick on a public target of a full
network, public seed 5, 0.3 s); `brainir-p4-fit` holds the smoke method snapshot tar under `methods/`; `brainir-p4-eval` is empty.
All three volumes were created as VolumeFS v2 volumes on 2026-09-26.
