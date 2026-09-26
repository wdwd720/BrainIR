"""The Phase 4 Modal backend (goal5 sections 62-65, 97).

- `images`   Modal images (pinned numerical stack; CPU images with the development machine's kernel pins; CUDA images for GPU jobs).
- `gate`     the host gate for bit-reproducible CPU numerics (no AVX-512 hosts), container side.
- `remote`   container-side job kinds: host-gated simulation batches (content-addressed store on a volume), orchestrator calls,
             guarded method jobs (fit / eval mode, optional per-job simulation service), volume utilities.
- `jobproc`  the fresh-interpreter entry point of every subprocess job.
- `app`      orchestrator side: the app, its worker classes and volumes, and `Backend` (simulate / call / run jobs with refusal
             re-submission, cost records, uploads) incl. the `remote_backend` hook of `brainir_causal.simservice.SimServer`.
- `benchwork` the representative training workloads of the GPU benchmark and the equivalence harness.
The repository never runs `remote` / `jobproc` itself; they run in containers.
"""
