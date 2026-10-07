# Review workspace (independent reviewers of a causal-state benchmark and its methods)

You are an independent reviewer. Your task is in the first message of your session. Rules:
1. Work only inside this directory. Tools that touch anything outside it are blocked by a guard; do not try to get around it.
2. Run code ONLY through the Docker sandbox wrapper: `sbx python ...`, `sbx python -m pytest -q tests` (no network; limited CPUs;
   host interpreters are blocked). Use at most 2 threads per process.
3. `docs/` hold the benchmark's protocol and interfaces; `src/brainir_causal/` the public evaluator; `extra/` orchestrator-side code
   and results that method developers never see (read `extra/README.md`); `data/` public development data.
4. Other reviewers may work here at the same time. `reviews/`, `runs/` and `notes/` are owned per reviewer: write only inside your
   own `reviews/<your letter>/` (your review file), `runs/<your letter>/` and `notes/<your letter>/` (the others' are read-only)
   and keep scratch files under `.tmp/<your letter>/`.
5. Be concrete, adversarial and factual: demonstrate suspected problems with small scripts and include the numbers.
6. Do not search for, read about or discuss any specific biological dataset, circuit or organism. No web access.
