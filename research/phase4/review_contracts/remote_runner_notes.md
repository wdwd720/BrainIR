# Remote runner for development experiments (CPU and GPU)

Heavy development experiments (sweeps over many systems or seeds, large neural models, anything that needs a GPU) run on remote
containers instead of this machine.

What a remote job is:
- ONE of your Python scripts in your work area (`runs/<your prefix>/...py`), run with `python <script> <args>` from the room root;
- the room's `src/` and `baselines/` and your `runs/<prefix>/` are copied in (files over 25 MB and your `runs/<prefix>/remote/` are
  left out); `PYTHONPATH` contains `src/` and `baselines/`;
- `data/` is an exact copy of this room's `data/` (the same public development data; nothing else);
- the network is blocked and no other program may be started; the simulation service is NOT available (scripts that use SimClient
  must run in the sandbox here);
- numerics: the same pinned numerical stack as the sandbox; CPU classes use the development machine's kernel settings; GPU classes
  run PyPI's CUDA build of the same torch version (GPU results can differ from CPU results in the last digits; seed and report).

Resource classes (`--class`): small = 2 CPUs / 8 GB; medium = 4 CPUs / 16 GB; large = 8 CPUs / 32 GB; xlarge = 8 CPUs / 64 GB; xxlarge = 16 CPUs / 128 GB; gpu-t4 = 4 CPUs / 32 GB + 1 T4; gpu-l4 = 4 CPUs / 32 GB + 1 L4; gpu-a10g = 4 CPUs / 32 GB + 1 A10G; gpu-l40s = 8 CPUs / 64 GB + 1 L40S; gpu-a100-40gb = 8 CPUs / 64 GB + 1 A100-40GB; gpu-a100-80gb = 8 CPUs / 64 GB + 1 A100-80GB; gpu-h100 = 8 CPUs / 64 GB + 1 H100; gpu-h200 = 8 CPUs / 128 GB + 1 H200; gpu-b200 = 8 CPUs / 128 GB + 1 B200.
Inside the job, `P4_REMOTE_CPUS` holds the CPU count (threads are set to it) and `P4_REMOTE_GPU` the GPU type (empty on CPU classes).

Usage (from the room root, through the sandbox):

    sbx python tools/remote_run.py submit runs/<prefix>/exp.py --class gpu-l4 --timeout 3600 -- --system s1 --seed 1
    sbx python tools/remote_run.py wait <job_id> [<job_id> ...]
    sbx python tools/remote_run.py status <job_id>

Results: every new or changed file under your `runs/<prefix>/` comes back under `runs/<prefix>/remote/<job_id>/runs/<prefix>/...`,
with the job's exit code, stdout / stderr tails, peak memory and wall time (`runs/_remote/queue/results/`). Write outputs under
`runs/<prefix>/`. Never end your turn to wait for a job: poll with `wait`.
