# Synthetic causal-state benchmark workspace

You are building generic synthetic systems for a benchmark that judges methods learning low-dimensional CAUSAL state models of
simulated neural populations with interventions. Read docs/SYNTHETIC_BENCHMARK_CONTRACT.md first; it is your full task description.
docs/PROTOCOL_V2.md fixes the protocol format, the intervention families and the system records; docs/PROTOCOL.md is the benchmark's
evaluation protocol (context: how your systems will be used); docs/CALIBRATION_TARGETS.md and ref/calibration_targets.json give the
generic statistics to match; ref/ holds reference code (protocol validation, family classification, calibration statistics).

Rules:
1. Work only inside this directory. Tools that touch anything outside it are blocked by a guard; do not try to get around it.
2. Run code ONLY through the Docker sandbox wrapper: `sbx python ...`, `sbx python -m pytest -q tests`. Host interpreters are
   blocked. The sandbox has numpy, scipy, pandas, pyarrow, pydantic, scikit-learn, torch (CPU) and pytest; no network; 2 CPUs.
3. The benchmark is generic: do not model any specific biological circuit, dataset or published result. You have no web access.
4. Keep ground truth separate from anything a method developer would receive (contract sections 1, 4).
5. Write down what you built and how you tested it in SYNTHETIC_BENCHMARK.md. Report limitations honestly.
