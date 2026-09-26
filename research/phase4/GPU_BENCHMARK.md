# Phase 4 GPU / CPU benchmark (goal5 section 63)

Generated 2026-09-26T18:03:40Z by `scripts/p4/gpu_benchmark.py` (app `brainir-p4-gpubench`, wall 1215.6 s). Workloads: `brainir_causal.p4modal.benchwork` (latent controlled SSMs with an intervention read-in; float32, TF32 off, Adam). Step = forward + backward + optimiser step, median after warm-up; epoch = 1,024 trajectories. Cost per epoch at Modal list prices (standard, preemptible; container CPU and memory included): GPU containers 4 cores / 32 GiB; CPU containers run gated (no AVX-512) with the AVX2 kernel pins (the reproducible production configuration).

## Recommendation

Geometric-mean speed-up over the 8 shapes, relative to an 8-core CPU container (gated, AVX2 pins):

| workload kind | fastest | 2nd | H100 | best CPU | cheapest per epoch |
|---|---|---|---|---|---|
| `rollout` (sequential latent rollout, latency-bound) | B200 3.9x | RTX-PRO-6000 3.7x | 2.1x | cpu4 / cpu8 1.0x | cpu4 ($0.0014 per epoch: 3.7x slower than RTX-PRO-6000 at a third of its cost per epoch) |
| `node` (control-affine neural ODE, RK4) | B200 4.1x | RTX-PRO-6000 4.0x | 2.0x | cpu8 1.0x | cpu4 ($0.0074) |
| `ens8` (8-model batched ensemble) | B200 6.1x | RTX-PRO-6000 6.0x | 3.2x | cpu8 1.0x | cpu4 ($0.0029) |
| `gru` (GRU filter, parallel multi-horizon loss) | RTX-PRO-6000 127x | B200 122x | 115x | cpu32 1.25x | RTX-PRO-6000 ($0.0003) |

- **Default GPU class for Phase 4 neural training: `RTX-PRO-6000`** (backend class `gpu_rtx6000`). It is the fastest or within 5 % of the fastest on every kind, and among the fast classes the cheapest per epoch (55-60 % of B200's cost; $3.03/h list vs $6.25/h). Only the slow T4 / A10 are cheaper per epoch on the latency-bound kinds (by 1-28 %), at 1.8-2.4x the wall time; on the GRU kind it is also the cheapest of all devices. Fall back to `B200` (`gpu_b200`) when RTX-PRO-6000 capacity is short (the probe waited ~8 min for one), and use `H100` / `H200` / `B200` for large-batch throughput-bound training (GRU, T = 2,000, B = 256: 0.14 s per step on all three; it does not fit in the 15-24 GB of T4 / L4 / A10).
- **Sequential rollouts are latency-bound**: kernel-launch latency, not FLOPs, sets the step time (the 20/4 and 200/16 shapes cost nearly the same on every GPU), so the newest datacenter GPUs gain only 2-4x over a CPU and older / smaller GPUs (L4, A100-80GB, T4) barely beat 8 CPU cores. Larger batches are nearly free on GPUs (B = 64 -> 256 at the same step time): batch many trajectories or many systems per step.
- **CPU never wins on speed; it wins on cost for small latency-bound jobs**: 4-8 physical cores is the sweet spot; 16-64 cores are SLOWER for these model sizes (thread overhead; 0.6-0.9x of cpu8). Linear / closed-form system identification (DMDc, subspace ID, SINDy) was not part of this benchmark and belongs on CPU (goal5 section 63).
- **Caveats**: each device was measured in ONE container (host-to-host variability not sampled; differences under ~20 % between devices are not meaningful, e.g. A100-40GB vs A100-80GB); float32 with TF32 disabled (TF32 or bf16 would be faster on Ampere and later, but change numerics); no `torch.compile` / CUDA graphs (which could remove much of the launch latency of the sequential kinds and should be benchmarked by any method that relies on long rollouts); list prices; the billed cost of the run comes from the billing report.

## Seconds per training step

| workload (kind, N_obs, k, T, batch) | cpu4 | cpu8 | cpu16 | cpu32 | cpu64 | T4 | L4 | A10 | L40S | A100-40GB | A100-80GB | RTX-PRO-6000 | H100 | H200 | B200 | B300 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ens8 20/4 T=500 B=64 | 1.38 | 1.3 | 1.41 | 1.38 | 1.72 | 0.957 | 1.29 | 0.718 | 0.923 | 0.875 | 1.29 | 0.306 | 0.599 | 0.509 | 0.318 | 0.604 |
| ens8 20/4 T=500 B=256 | 2.28 | 2.05 | 2.18 | 3.39 | 5.13 | 0.959 | 1.29 | 0.73 | 0.929 | 0.875 | 1.58 | 0.33 | 0.602 | 0.492 | 0.304 | 0.592 |
| ens8 20/4 T=2000 B=64 | 5.84 | 5.69 | 6.13 | 5.78 | 7.31 | 4.09 | 5.28 | 3 | 3.86 | 3.56 | 6.31 | 1.38 | 2.54 | 2.09 | 1.34 | 2.58 |
| ens8 20/4 T=2000 B=256 | 10.4 | 9.31 | 9.84 | 14.6 | 22.1 | 3.97 | 5.31 | 2.99 | 3.86 | 3.58 | 5.65 | 1.41 | 2.55 | 2.18 | 1.35 | 2.61 |
| ens8 200/16 T=500 B=64 | 1.62 | 1.71 | 1.9 | 1.79 | 2.24 | 0.965 | 1.27 | 0.734 | 0.937 | 0.872 | 1.38 | 0.316 | 0.596 | 0.509 | 0.334 | 0.669 |
| ens8 200/16 T=500 B=256 | 2.7 | 2.6 | 2.83 | 3.79 | 5.39 | 0.978 | 1.3 | 0.732 | 0.934 | 0.877 | 1.41 | 0.317 | 0.599 | 0.52 | 0.323 | 0.654 |
| ens8 200/16 T=2000 B=64 | 6.73 | 7.35 | 7.97 | 7.74 | 9.58 | 4.02 | 5.3 | 3.01 | 3.92 | 3.59 | 5.8 | 1.39 | 2.77 | 2.1 | 1.25 | 2.68 |
| ens8 200/16 T=2000 B=256 | 15.9 | 13.9 | 13.6 | 18 | 26.1 | 4.04 | 5.3 | 3.01 | 3.84 | 3.59 | 5.42 | 1.39 | 2.67 | 2.1 | 1.35 | 2.42 |
| gru 20/4 T=500 B=64 | 1.58 | 1.22 | 1.14 | 1.03 | 1.03 | 0.0601 | 0.043 | 0.034 | 0.033 | 0.0308 | 0.0467 | 0.0131 | 0.0218 | 0.0181 | 0.0151 | 0.0237 |
| gru 20/4 T=500 B=256 | 6.06 | 3.97 | 3.76 | 3.07 | 3.53 | 0.22 | 0.16 | 0.119 | 0.0617 | 0.0734 | 0.0693 | 0.0302 | 0.0333 | 0.0335 | 0.0349 | 0.0345 |
| gru 20/4 T=2000 B=64 | 7.1 | 4.83 | 4.48 | 3.9 | 4.07 | 0.226 | 0.166 | 0.121 | 0.0637 | 0.0765 | 0.0719 | 0.0332 | 0.0355 | 0.0357 | 0.0374 | 0.037 |
| gru 20/4 T=2000 B=256 | 32.8 | 22.8 | 23.5 | 19.2 | 22.6 | 0.884 | 0.685 | 0.42 | 0.267 | 0.262 | 0.248 | 0.123 | 0.105 | 0.105 | 0.107 | 0.105 |
| gru 200/16 T=500 B=64 | 2.3 | 1.42 | 1.31 | 1.11 | 1.13 | 0.0845 | 0.0491 | 0.0454 | 0.0321 | 0.031 | 0.0491 | 0.0145 | 0.022 | 0.0183 | 0.017 | 0.0249 |
| gru 200/16 T=500 B=256 | 8.23 | 4.8 | 4.37 | 3.67 | 4.04 | 0.322 | 0.235 | 0.165 | 0.0846 | 0.0944 | 0.0892 | 0.0415 | 0.0437 | 0.0439 | 0.0439 | 0.0433 |
| gru 200/16 T=2000 B=64 | 8.33 | 5.79 | 5.27 | 4.47 | 4.77 | 0.329 | 0.242 | 0.168 | 0.0873 | 0.0968 | 0.0925 | 0.0443 | 0.0461 | 0.0463 | 0.0466 | 0.0459 |
| gru 200/16 T=2000 B=256 | 40.1 | 24.2 | 23.4 | 20.2 | 23.7 | err | err | err | 0.385 | 0.347 | 0.328 | 0.176 | 0.144 | 0.146 | 0.145 | 0.143 |
| node 20/4 T=500 B=64 | 4.62 | 3.72 | 3.54 | 3.82 | 4.26 | 3.1 | 3.93 | 2.24 | 2.78 | 2.62 | 3.84 | 1.1 | 2.2 | 1.72 | 1.1 | 1.94 |
| node 20/4 T=500 B=256 | 6.09 | 5.22 | 5.52 | 5.82 | 6.68 | 3.09 | 3.92 | 2.27 | 2.85 | 2.67 | 4 | 1.09 | 2.27 | 1.75 | 1.09 | 1.92 |
| node 20/4 T=2000 B=64 | 17.1 | 15.4 | 15 | 16.7 | 19 | 12.5 | 16.7 | 9.25 | 11.9 | 11.1 | 16.1 | 4.71 | 9.29 | 7.2 | 4.54 | 8.19 |
| node 20/4 T=2000 B=256 | 23.2 | 20.6 | 23.2 | 23.3 | 23.4 | 12.8 | 16.6 | 9.21 | 11.8 | 11.4 | 17 | 4.54 | 9.31 | 7.35 | 5.09 | 8.76 |
| node 200/16 T=500 B=64 | 4.21 | 3.63 | 3.9 | 4.22 | 4.33 | 3.09 | 4.04 | 2.2 | 2.78 | 2.67 | 4.13 | 1.17 | 2.29 | 1.8 | 1.05 | 2.01 |
| node 200/16 T=500 B=256 | 6.26 | 5.35 | 6.31 | 6.55 | 6.38 | 3.04 | 3.95 | 2.21 | 2.77 | 2.74 | 4 | 1.11 | 2.31 | 1.89 | 1.04 | 1.96 |
| node 200/16 T=2000 B=64 | 17.7 | 15.6 | 15.8 | 17.1 | 18 | 13.2 | 17 | 9.37 | 11.8 | 11.3 | 16.5 | 4.78 | 9.09 | 7.41 | 4.45 | 8.51 |
| node 200/16 T=2000 B=256 | 28.7 | 24.7 | 27.8 | 27.8 | 28.5 | 13.6 | 16.8 | 9.33 | 11.7 | 11.3 | 16.5 | 4.83 | 9.17 | 7.68 | 4.56 | 9.44 |
| rollout 20/4 T=500 B=64 | 0.752 | 0.791 | 0.978 | 1.04 | 1.23 | 0.648 | 0.891 | 0.492 | 0.634 | 0.605 | 0.816 | 0.27 | 0.486 | 0.399 | 0.246 | 0.431 |
| rollout 20/4 T=500 B=256 | 1.03 | 1.1 | 1.78 | 1.52 | 1.74 | 0.67 | 0.903 | 0.477 | 0.655 | 0.633 | 0.871 | 0.276 | 0.461 | 0.377 | 0.246 | 0.456 |
| rollout 20/4 T=2000 B=64 | 3.02 | 3.29 | 4.31 | 4.2 | 4.72 | 2.71 | 3.73 | 1.97 | 2.69 | 2.5 | 3.41 | 1.14 | 2.09 | 1.5 | 1.08 | 1.86 |
| rollout 20/4 T=2000 B=256 | 4.49 | 4.67 | 6.79 | 6.33 | 7.76 | 2.8 | 3.71 | 2.14 | 2.71 | 2.61 | 3.51 | 1.18 | 2.09 | 1.6 | 1.12 | 1.94 |
| rollout 200/16 T=500 B=64 | 0.996 | 0.887 | 1.14 | 1.15 | 1.27 | 0.672 | 0.904 | 0.504 | 0.662 | 0.617 | 0.839 | 0.285 | 0.516 | 0.382 | 0.271 | 0.456 |
| rollout 200/16 T=500 B=256 | 1.37 | 1.33 | 1.93 | 1.71 | 1.98 | 0.669 | 0.903 | 0.511 | 0.673 | 0.628 | 0.865 | 0.284 | 0.523 | 0.381 | 0.274 | 0.455 |
| rollout 200/16 T=2000 B=64 | 3.86 | 3.78 | 4.98 | 4.76 | 5.87 | 2.77 | 3.71 | 2.14 | 2.74 | 2.56 | 3.53 | 1.1 | 2.04 | 1.61 | 1.12 | 1.89 |
| rollout 200/16 T=2000 B=256 | 5.71 | 5.74 | 9.75 | 7.42 | 8.02 | 2.77 | 3.71 | 2.16 | 2.77 | 2.6 | 3.67 | 1.13 | 2 | 1.6 | 1.09 | 1.93 |

## USD per epoch (1,024 trajectories)

| workload | cpu4 | cpu8 | cpu16 | cpu32 | cpu64 | T4 | L4 | A10 | L40S | A100-40GB | A100-80GB | RTX-PRO-6000 | H100 | H200 | B200 | B300 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ens8 20/4 T=500 B=64 | 0.0019 | 0.0029 | 0.0063 | 0.011 | 0.027 | 0.0044 | 0.0071 | 0.0049 | 0.0098 | 0.0099 | 0.017 | 0.0047 | 0.012 | 0.011 | 0.0095 | 0.02 |
| ens8 20/4 T=500 B=256 | 0.0008 | 0.0012 | 0.0025 | 0.0066 | 0.02 | 0.0011 | 0.0018 | 0.0013 | 0.0025 | 0.0025 | 0.0052 | 0.0013 | 0.0029 | 0.0027 | 0.0023 | 0.005 |
| ens8 20/4 T=2000 B=64 | 0.0082 | 0.013 | 0.028 | 0.045 | 0.11 | 0.019 | 0.029 | 0.021 | 0.041 | 0.04 | 0.083 | 0.021 | 0.05 | 0.046 | 0.04 | 0.086 |
| ens8 20/4 T=2000 B=256 | 0.0037 | 0.0052 | 0.011 | 0.029 | 0.087 | 0.0046 | 0.0073 | 0.0051 | 0.01 | 0.01 | 0.018 | 0.0055 | 0.012 | 0.012 | 0.01 | 0.022 |
| ens8 200/16 T=500 B=64 | 0.0023 | 0.0038 | 0.0085 | 0.014 | 0.035 | 0.0044 | 0.007 | 0.005 | 0.01 | 0.0099 | 0.018 | 0.0049 | 0.012 | 0.011 | 0.0099 | 0.022 |
| ens8 200/16 T=500 B=256 | 0.00095 | 0.0015 | 0.0032 | 0.0074 | 0.021 | 0.0011 | 0.0018 | 0.0013 | 0.0025 | 0.0025 | 0.0046 | 0.0012 | 0.0029 | 0.0029 | 0.0024 | 0.0055 |
| ens8 200/16 T=2000 B=64 | 0.0095 | 0.016 | 0.036 | 0.061 | 0.15 | 0.018 | 0.029 | 0.021 | 0.042 | 0.041 | 0.076 | 0.021 | 0.054 | 0.046 | 0.037 | 0.09 |
| ens8 200/16 T=2000 B=256 | 0.0056 | 0.0078 | 0.015 | 0.035 | 0.1 | 0.0046 | 0.0073 | 0.0052 | 0.01 | 0.01 | 0.018 | 0.0054 | 0.013 | 0.012 | 0.01 | 0.02 |
| gru 20/4 T=500 B=64 | 0.0022 | 0.0027 | 0.0051 | 0.0081 | 0.016 | 0.00028 | 0.00024 | 0.00023 | 0.00035 | 0.00035 | 0.00061 | 0.0002 | 0.00042 | 0.0004 | 0.00045 | 0.00079 |
| gru 20/4 T=500 B=256 | 0.0021 | 0.0022 | 0.0042 | 0.006 | 0.014 | 0.00025 | 0.00022 | 0.0002 | 0.00016 | 0.00021 | 0.00023 | 0.00012 | 0.00016 | 0.00018 | 0.00026 | 0.00029 |
| gru 20/4 T=2000 B=64 | 0.01 | 0.011 | 0.02 | 0.031 | 0.064 | 0.001 | 0.00092 | 0.00083 | 0.00068 | 0.00086 | 0.00094 | 0.00051 | 0.00069 | 0.00079 | 0.0011 | 0.0012 |
| gru 20/4 T=2000 B=256 | 0.012 | 0.013 | 0.026 | 0.038 | 0.089 | 0.001 | 0.00095 | 0.00072 | 0.00071 | 0.00074 | 0.00081 | 0.00047 | 0.00051 | 0.00058 | 0.0008 | 0.00088 |
| gru 200/16 T=500 B=64 | 0.0032 | 0.0032 | 0.0059 | 0.0087 | 0.018 | 0.00039 | 0.00027 | 0.00031 | 0.00034 | 0.00035 | 0.00064 | 0.00022 | 0.00043 | 0.0004 | 0.00051 | 0.00083 |
| gru 200/16 T=500 B=256 | 0.0029 | 0.0027 | 0.0049 | 0.0072 | 0.016 | 0.00037 | 0.00032 | 0.00028 | 0.00022 | 0.00027 | 0.00029 | 0.00016 | 0.00021 | 0.00024 | 0.00033 | 0.00036 |
| gru 200/16 T=2000 B=64 | 0.012 | 0.013 | 0.024 | 0.035 | 0.075 | 0.0015 | 0.0013 | 0.0012 | 0.00093 | 0.0011 | 0.0012 | 0.00068 | 0.0009 | 0.001 | 0.0014 | 0.0015 |
| gru 200/16 T=2000 B=256 | 0.014 | 0.014 | 0.026 | 0.04 | 0.093 | err | err | err | 0.001 | 0.00098 | 0.0011 | 0.00068 | 0.0007 | 0.00081 | 0.0011 | 0.0012 |
| node 20/4 T=500 B=64 | 0.0065 | 0.0084 | 0.016 | 0.03 | 0.067 | 0.014 | 0.022 | 0.015 | 0.03 | 0.03 | 0.05 | 0.017 | 0.043 | 0.038 | 0.033 | 0.065 |
| node 20/4 T=500 B=256 | 0.0021 | 0.0029 | 0.0062 | 0.011 | 0.026 | 0.0036 | 0.0054 | 0.0039 | 0.0076 | 0.0076 | 0.013 | 0.0042 | 0.011 | 0.0097 | 0.0081 | 0.016 |
| node 20/4 T=2000 B=64 | 0.024 | 0.034 | 0.068 | 0.13 | 0.3 | 0.057 | 0.092 | 0.064 | 0.13 | 0.13 | 0.21 | 0.073 | 0.18 | 0.16 | 0.13 | 0.27 |
| node 20/4 T=2000 B=256 | 0.0082 | 0.012 | 0.026 | 0.046 | 0.092 | 0.015 | 0.023 | 0.016 | 0.031 | 0.032 | 0.055 | 0.018 | 0.045 | 0.041 | 0.038 | 0.073 |
| node 200/16 T=500 B=64 | 0.0059 | 0.0082 | 0.018 | 0.033 | 0.068 | 0.014 | 0.022 | 0.015 | 0.03 | 0.03 | 0.054 | 0.018 | 0.045 | 0.04 | 0.031 | 0.067 |
| node 200/16 T=500 B=256 | 0.0022 | 0.003 | 0.0071 | 0.013 | 0.025 | 0.0035 | 0.0055 | 0.0038 | 0.0074 | 0.0077 | 0.013 | 0.0043 | 0.011 | 0.01 | 0.0077 | 0.016 |
| node 200/16 T=2000 B=64 | 0.025 | 0.035 | 0.071 | 0.13 | 0.28 | 0.061 | 0.094 | 0.064 | 0.13 | 0.13 | 0.22 | 0.074 | 0.18 | 0.16 | 0.13 | 0.29 |
| node 200/16 T=2000 B=256 | 0.01 | 0.014 | 0.031 | 0.055 | 0.11 | 0.016 | 0.023 | 0.016 | 0.031 | 0.032 | 0.054 | 0.019 | 0.045 | 0.043 | 0.034 | 0.079 |
| rollout 20/4 T=500 B=64 | 0.0011 | 0.0018 | 0.0044 | 0.0081 | 0.019 | 0.003 | 0.0049 | 0.0034 | 0.0068 | 0.0068 | 0.011 | 0.0042 | 0.0095 | 0.0088 | 0.0073 | 0.014 |
| rollout 20/4 T=500 B=256 | 0.00036 | 0.00062 | 0.002 | 0.003 | 0.0068 | 0.00077 | 0.0012 | 0.00082 | 0.0017 | 0.0018 | 0.0028 | 0.0011 | 0.0023 | 0.0021 | 0.0018 | 0.0038 |
| rollout 20/4 T=2000 B=64 | 0.0042 | 0.0074 | 0.019 | 0.033 | 0.074 | 0.012 | 0.021 | 0.014 | 0.029 | 0.028 | 0.045 | 0.018 | 0.041 | 0.033 | 0.032 | 0.062 |
| rollout 20/4 T=2000 B=256 | 0.0016 | 0.0026 | 0.0076 | 0.012 | 0.03 | 0.0032 | 0.0051 | 0.0037 | 0.0072 | 0.0074 | 0.011 | 0.0045 | 0.01 | 0.0089 | 0.0083 | 0.016 |
| rollout 200/16 T=500 B=64 | 0.0014 | 0.002 | 0.0051 | 0.009 | 0.02 | 0.0031 | 0.005 | 0.0035 | 0.0071 | 0.007 | 0.011 | 0.0044 | 0.01 | 0.0085 | 0.0081 | 0.015 |
| rollout 200/16 T=500 B=256 | 0.00048 | 0.00075 | 0.0022 | 0.0034 | 0.0078 | 0.00077 | 0.0012 | 0.00088 | 0.0018 | 0.0018 | 0.0028 | 0.0011 | 0.0026 | 0.0021 | 0.002 | 0.0038 |
| rollout 200/16 T=2000 B=64 | 0.0054 | 0.0085 | 0.022 | 0.037 | 0.092 | 0.013 | 0.021 | 0.015 | 0.029 | 0.029 | 0.046 | 0.017 | 0.04 | 0.036 | 0.033 | 0.063 |
| rollout 200/16 T=2000 B=256 | 0.002 | 0.0032 | 0.011 | 0.015 | 0.031 | 0.0032 | 0.0051 | 0.0037 | 0.0074 | 0.0074 | 0.012 | 0.0044 | 0.0097 | 0.0088 | 0.0081 | 0.016 |

## Fastest and cheapest per workload

| workload | fastest | step s | cheapest per epoch | USD | best CPU | best GPU | CPU wins |
|---|---|---|---|---|---|---|---|
| ens8 20 4 500 64 | RTX-PRO-6000 | 0.306 | cpu4 | 0.0019 | cpu8 (1.296) | RTX-PRO-6000 (0.306) | no |
| ens8 20 4 500 256 | B200 | 0.304 | cpu4 | 0.0008 | cpu8 (2.054) | B200 (0.304) | no |
| ens8 20 4 2000 64 | B200 | 1.34 | cpu4 | 0.0082 | cpu8 (5.689) | B200 (1.34) | no |
| ens8 20 4 2000 256 | B200 | 1.35 | cpu4 | 0.0037 | cpu8 (9.308) | B200 (1.351) | no |
| ens8 200 16 500 64 | RTX-PRO-6000 | 0.316 | cpu4 | 0.0023 | cpu4 (1.621) | RTX-PRO-6000 (0.316) | no |
| ens8 200 16 500 256 | RTX-PRO-6000 | 0.317 | cpu4 | 0.00095 | cpu8 (2.599) | RTX-PRO-6000 (0.317) | no |
| ens8 200 16 2000 64 | B200 | 1.25 | cpu4 | 0.0095 | cpu4 (6.729) | B200 (1.253) | no |
| ens8 200 16 2000 256 | B200 | 1.35 | T4 | 0.0046 | cpu16 (13.647) | B200 (1.348) | no |
| gru 20 4 500 64 | RTX-PRO-6000 | 0.0131 | RTX-PRO-6000 | 0.0002 | cpu32 (1.028) | RTX-PRO-6000 (0.013) | no |
| gru 20 4 500 256 | RTX-PRO-6000 | 0.0302 | RTX-PRO-6000 | 0.00012 | cpu32 (3.068) | RTX-PRO-6000 (0.03) | no |
| gru 20 4 2000 64 | RTX-PRO-6000 | 0.0332 | RTX-PRO-6000 | 0.00051 | cpu32 (3.901) | RTX-PRO-6000 (0.033) | no |
| gru 20 4 2000 256 | H100 | 0.105 | RTX-PRO-6000 | 0.00047 | cpu32 (19.158) | H100 (0.105) | no |
| gru 200 16 500 64 | RTX-PRO-6000 | 0.0145 | RTX-PRO-6000 | 0.00022 | cpu32 (1.111) | RTX-PRO-6000 (0.015) | no |
| gru 200 16 500 256 | RTX-PRO-6000 | 0.0415 | RTX-PRO-6000 | 0.00016 | cpu32 (3.672) | RTX-PRO-6000 (0.041) | no |
| gru 200 16 2000 64 | RTX-PRO-6000 | 0.0443 | RTX-PRO-6000 | 0.00068 | cpu32 (4.469) | RTX-PRO-6000 (0.044) | no |
| gru 200 16 2000 256 | B300 | 0.143 | RTX-PRO-6000 | 0.00068 | cpu32 (20.227) | B300 (0.143) | no |
| node 20 4 500 64 | RTX-PRO-6000 | 1.1 | cpu4 | 0.0065 | cpu16 (3.539) | RTX-PRO-6000 (1.096) | no |
| node 20 4 500 256 | B200 | 1.09 | cpu4 | 0.0021 | cpu8 (5.221) | B200 (1.092) | no |
| node 20 4 2000 64 | B200 | 4.54 | cpu4 | 0.024 | cpu16 (15.048) | B200 (4.536) | no |
| node 20 4 2000 256 | RTX-PRO-6000 | 4.54 | cpu4 | 0.0082 | cpu8 (20.568) | RTX-PRO-6000 (4.542) | no |
| node 200 16 500 64 | B200 | 1.05 | cpu4 | 0.0059 | cpu8 (3.633) | B200 (1.055) | no |
| node 200 16 500 256 | B200 | 1.04 | cpu4 | 0.0022 | cpu8 (5.345) | B200 (1.037) | no |
| node 200 16 2000 64 | B200 | 4.45 | cpu4 | 0.025 | cpu8 (15.589) | B200 (4.446) | no |
| node 200 16 2000 256 | B200 | 4.56 | cpu4 | 0.01 | cpu8 (24.712) | B200 (4.563) | no |
| rollout 20 4 500 64 | B200 | 0.246 | cpu4 | 0.0011 | cpu4 (0.752) | B200 (0.246) | no |
| rollout 20 4 500 256 | B200 | 0.246 | cpu4 | 0.00036 | cpu4 (1.025) | B200 (0.246) | no |
| rollout 20 4 2000 64 | B200 | 1.08 | cpu4 | 0.0042 | cpu4 (3.018) | B200 (1.083) | no |
| rollout 20 4 2000 256 | B200 | 1.12 | cpu4 | 0.0016 | cpu4 (4.493) | B200 (1.12) | no |
| rollout 200 16 500 64 | B200 | 0.271 | cpu4 | 0.0014 | cpu8 (0.887) | B200 (0.271) | no |
| rollout 200 16 500 256 | B200 | 0.274 | cpu4 | 0.00048 | cpu8 (1.332) | B200 (0.274) | no |
| rollout 200 16 2000 64 | RTX-PRO-6000 | 1.1 | cpu4 | 0.0054 | cpu8 (3.78) | RTX-PRO-6000 (1.1) | no |
| rollout 200 16 2000 256 | B200 | 1.09 | cpu4 | 0.002 | cpu4 (5.713) | B200 (1.092) | no |

## CPU / GPU equivalence (brainir_causal.equiv; goal5 acceptance criterion 39)

Builder `brainir_causal.equiv:reference_trainer` (a latent controlled SSM with an intervention read-in, `rollout`, and a GRU filter, `gru`; cuDNN on GPUs), 50 Adam steps from the same seed, parameters and data created on the CPU and then moved. In one GPU container: a CPU run and two GPU runs. Tolerances, stated before any GPU run: float64 loss / parameters / predictions 1e-09 / 1e-08 / 1e-08 relative; float32 (TF32 off) 0.001 / 0.001 / 0.001. Determinism: deterministic algorithms, cuDNN deterministic without autotuning, cuBLAS workspace :4096:8. App `ap-Ft0S1xqUC7XA9RhDEZ9htQ`; all pass: **True**.

| GPU class | model | dtype | GPU vs CPU (same container): loss, params, predictions | GPU run to run | container CPU vs local (Windows) CPU: params | criterion 39 |
|---|---|---|---|---|---|---|
| L4 (NVIDIA L4) | rollout | float64 | 3.6e-16, 4.1e-16, 3.1e-16 | bitwise identical | 4.2e-16 | pass |
| L4 (NVIDIA L4) | rollout | float32 | 2.1e-07, 1.9e-07, 1.8e-07 | bitwise identical | 1.5e-07 | pass |
| L4 (NVIDIA L4) | gru | float64 | 4.2e-16, 1.3e-15, 1.9e-15 | bitwise identical | 2.1e-15 | pass |
| L4 (NVIDIA L4) | gru | float32 | 2.3e-07, 9.0e-07, 1.9e-06 | bitwise identical | 7.5e-08 | pass |
| A10 (NVIDIA A10) | rollout | float64 | 2.2e-16, 4.7e-16, 2.6e-16 | bitwise identical | 4.1e-16 | pass |
| A10 (NVIDIA A10) | rollout | float32 | 2.0e-07, 1.6e-07, 1.6e-07 | bitwise identical | 1.5e-07 | pass |
| A10 (NVIDIA A10) | gru | float64 | 4.2e-16, 7.0e-16, 1.2e-15 | bitwise identical | 1.5e-15 | pass |
| A10 (NVIDIA A10) | gru | float32 | 2.9e-07, 1.3e-06, 2.2e-06 | bitwise identical | 6.1e-07 | pass |
| A100-80GB (NVIDIA A100 80GB PCIe) | rollout | float64 | 3.7e-16, 3.5e-16, 2.8e-16 | bitwise identical | 4.2e-16 | pass |
| A100-80GB (NVIDIA A100 80GB PCIe) | rollout | float32 | 2.0e-07, 2.1e-07, 1.6e-07 | bitwise identical | 1.5e-07 | pass |
| A100-80GB (NVIDIA A100 80GB PCIe) | gru | float64 | 3.0e-16, 4.5e-16, 1.3e-15 | bitwise identical | 2.1e-15 | pass |
| A100-80GB (NVIDIA A100 80GB PCIe) | gru | float32 | 2.3e-07, 9.1e-07, 1.9e-06 | bitwise identical | 7.5e-08 | pass |
| H100 (NVIDIA H100 80GB HBM3) | rollout | float64 | 2.2e-16, 3.7e-16, 2.6e-16 | bitwise identical | 4.1e-16 | pass |
| H100 (NVIDIA H100 80GB HBM3) | rollout | float32 | 2.0e-07, 1.9e-07, 1.8e-07 | bitwise identical | 1.5e-07 | pass |
| H100 (NVIDIA H100 80GB HBM3) | gru | float64 | 4.1e-16, 1.1e-15, 1.4e-15 | bitwise identical | 1.5e-15 | pass |
| H100 (NVIDIA H100 80GB HBM3) | gru | float32 | 2.9e-07, 1.3e-06, 2.3e-06 | bitwise identical | 6.1e-07 | pass |
| B200 (NVIDIA B200) | rollout | float64 | 2.2e-16, 3.5e-16, 2.5e-16 | bitwise identical | 4.1e-16 | pass |
| B200 (NVIDIA B200) | rollout | float32 | 2.0e-07, 1.6e-07, 1.8e-07 | bitwise identical | 1.5e-07 | pass |
| B200 (NVIDIA B200) | gru | float64 | 4.1e-16, 1.1e-15, 1.4e-15 | bitwise identical | 1.5e-15 | pass |
| B200 (NVIDIA B200) | gru | float32 | 2.9e-07, 1.1e-06, 2.1e-06 | bitwise identical | 6.1e-07 | pass |
| RTX-PRO-6000 (NVIDIA RTX PRO 6000 Blackwell Server Edition) | rollout | float64 | 3.6e-16, 4.1e-16, 3.1e-16 | bitwise identical | 4.2e-16 | pass |
| RTX-PRO-6000 (NVIDIA RTX PRO 6000 Blackwell Server Edition) | rollout | float32 | 2.0e-07, 1.7e-07, 1.6e-07 | bitwise identical | 1.5e-07 | pass |
| RTX-PRO-6000 (NVIDIA RTX PRO 6000 Blackwell Server Edition) | gru | float64 | 4.2e-16, 1.5e-15, 2.0e-15 | bitwise identical | 2.1e-15 | pass |
| RTX-PRO-6000 (NVIDIA RTX PRO 6000 Blackwell Server Edition) | gru | float32 | 2.3e-07, 8.4e-07, 1.9e-06 | bitwise identical | 7.5e-08 | pass |

Platform note (2026-09-26, diagnostic apps ap-23qX72eDLkEHEC5nQkhdQ7 and ap-Xd8Ki87qinobSHsOj4c8DC). The Linux CPU runs of every container kind (gated with the AVX2 pins, ungated with the pins, the CUDA image's CPU path) agree with each other exactly. A first version of the reference trainer initialised its parameters in float32 and cast them to float64: the development machine (Windows) then differed from Linux by about 1e-7 relative from the first loss on, because the initialisers' float32 uniform transform rounds differently on the two platforms (compiled with / without fused multiply-add: one float32 rounding, ~6e-8). With the parameters initialised in float64 (the committed trainer), local Windows and Linux runs agree to ~1e-16 in float64 after 50 steps (rollout 4e-16, GRU 2e-15) and to ~1e-7 in float32. Consequences for methods: (1) GPU and CPU training agree within the stated tolerances; (2) float32 initialisation or float32 arithmetic makes local and Modal results differ at the float32 level, which is harmless for comparisons but not bit-reproducible across platforms, so locked fits run on ONE platform (as in Phase 3); (3) elementary float64 kernels differ at the last digits across platforms (exp up to 8 ulp; matmul summation order), which recurrent rollouts do not amplify noticeably over 50 steps here.

## GPU type strings (probe)

| string | accepted | nvidia-smi |
|---|---|---|
| T4 | yes | Tesla T4, 15360 MiB, 610.57.04 |
| L4 | yes | NVIDIA L4, 23034 MiB, 580.95.05 |
| A10 | yes | NVIDIA A10, 23028 MiB, 580.95.05 |
| A10G | yes | NVIDIA A10, 23028 MiB, 580.95.05 |
| L40S | yes | NVIDIA L40S, 46068 MiB, 580.95.05 |
| A100-40GB | yes | NVIDIA A100-SXM4-40GB, 40960 MiB, 580.95.05 |
| A100-80GB | yes | NVIDIA A100-SXM4-80GB, 81920 MiB, 580.95.05 |
| RTX-PRO-6000 | yes | NVIDIA RTX PRO 6000 Blackwell Server Edition, 97887 MiB, 580.95.05 |
| H100 | yes | NVIDIA H100 80GB HBM3, 81559 MiB, 580.95.05 |
| H200 | yes | NVIDIA H200, 143771 MiB, 580.95.05 |
| B200 | yes | NVIDIA B200, 183359 MiB, 580.95.05 |
| B300 | yes | NVIDIA B300 SXM6 AC, 275040 MiB, 580.95.05 |

## Devices

- cpu4: unknown (torch 2.14.0+cpu, CUDA None, threads 4, host unknown)
- cpu16: unknown (torch 2.14.0+cpu, CUDA None, threads 16, host unknown)
- cpu8: unknown (torch 2.14.0+cpu, CUDA None, threads 8, host unknown)
- cpu32: unknown (torch 2.14.0+cpu, CUDA None, threads 32, host unknown)
- cpu64: unknown (torch 2.14.0+cpu, CUDA None, threads 64, host unknown)
- RTX-PRO-6000: NVIDIA RTX PRO 6000 Blackwell Server Edition (torch 2.14.0+cu130, CUDA 13.0, threads 4, host unknown)
- H200: NVIDIA H200 (torch 2.14.0+cu130, CUDA 13.0, threads 4, host unknown)
- H100: NVIDIA H200 (torch 2.14.0+cu130, CUDA 13.0, threads 4, host unknown)
- A10: NVIDIA A10 (torch 2.14.0+cu130, CUDA 13.0, threads 4, host unknown)
- B300: NVIDIA B300 SXM6 AC (torch 2.14.0+cu130, CUDA 13.0, threads 4, host unknown)
- A100-40GB: NVIDIA A100-SXM4-40GB (torch 2.14.0+cu130, CUDA 13.0, threads 4, host unknown)
- L40S: NVIDIA L40S (torch 2.14.0+cu130, CUDA 13.0, threads 4, host unknown)
- T4: Tesla T4 (torch 2.14.0+cu130, CUDA 13.0, threads 4, host unknown)
- A100-80GB: NVIDIA A100-SXM4-80GB (torch 2.14.0+cu130, CUDA 13.0, threads 4, host unknown)
- L4: NVIDIA L4 (torch 2.14.0+cu130, CUDA 13.0, threads 4, host unknown)
- B200: NVIDIA B200 (torch 2.14.0+cu130, CUDA 13.0, threads 4, host unknown)

## Failed cases (recorded, not retried)

- A10 gru 200/16 T=2000 B=256: OutOfMemoryError('CUDA out of memory. Tried to allocate 124.00 MiB. GPU 0 has a total capacity of 22.06 GiB of which 139.94 MiB is free. Process 1 has 21.91 GiB
- T4 gru 200/16 T=2000 B=256: OutOfMemoryError('CUDA out of memory. Tried to allocate 248.00 MiB. GPU 0 has a total capacity of 14.57 GiB of which 203.50 MiB is free. Process 1 has 14.37 GiB
- L4 gru 200/16 T=2000 B=256: OutOfMemoryError('CUDA out of memory. Tried to allocate 420.00 MiB. GPU 0 has a total capacity of 22.03 GiB of which 43.12 MiB is free. Process 1 has 21.98 GiB 
