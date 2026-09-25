# Remote runner for development experiments (from the orchestrator)

Heavy development experiments (sweeps over many systems or seeds, real full systems) can run on remote containers instead of
this machine. The runner exists because the local machine ran out of memory.

What a remote job is:
- ONE of your Python scripts in your work area (`runs/<your prefix>/...py`), run with `python <script> <args>` from the room root;
- the room's `src/` and your `runs/<prefix>/` are copied in (files over 25 MB and your `runs/<prefix>/remote/` are left out);
- `data/` is an exact copy of this room's `data/` (the same public development data; nothing else);
- the network is blocked; the budgeted simulation service is NOT available (scripts that use SimClient must run locally);
- numerics: the same pinned numerical stack as the evaluation (last-digit differences from this machine are possible in dense
  linear algebra).

Resource classes (`--class`): small = 2 CPUs / 8 GB, medium = 4 CPUs / 16 GB, large = 8 CPUs / 32 GB, xlarge = 8 CPUs / 64 GB.
Inside the job, `P3_REMOTE_CPUS` holds the CPU count; threads (OMP / MKL / OpenBLAS) are set to it. The one-process-and-3-threads
rule of this room does not apply to remote jobs: use the container's CPUs. Several jobs may run in parallel (split a sweep into one
job per system or seed).

Usage:

    uv run python runs/_remote/remote_run.py submit runs/<prefix>/exp.py --class medium --timeout 3600 -- --system syn-xxx --seed 1
    uv run python runs/_remote/remote_run.py wait <job_id> [<job_id> ...]
    uv run python runs/_remote/remote_run.py status <job_id>

Results: every new or changed file under your `runs/<prefix>/` comes back under `runs/<prefix>/remote/<job_id>/runs/<prefix>/...`,
next to the job's exit code, the tails of stdout / stderr, the peak memory and the wall time (`runs/_remote/queue/results/`).
Write your outputs under `runs/<prefix>/` so that they come back. Never end your turn to wait for a job: poll with `wait` (it blocks
in the foreground).
