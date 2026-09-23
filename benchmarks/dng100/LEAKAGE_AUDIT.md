# LEAKAGE AUDIT — dng100-benchmark-v1

Checked 2026-09-23T10:14:23Z by `benchmarks/dng100/cleanroom/leakage_check.py`. Overall: **PASS**.

## What counts as leakage

The oracle (published core neurons, their labels, roles and essentiality) must not be recoverable from anything a
discovery method receives: the public bundle, the `brainir` library, or prompts/documents handed to it. Body IDs of
oracle neurons legitimately occur in the bundle as ordinary network members (every neuron is listed); leakage would
be any file that singles them out, any published cell-type name in the blind tier, or any oracle label anywhere.

## Results

| bundle | tier | manifest verifies | text hits | parquet hits |
|---|---|---|---|---|
| public | B | True | 0 | 0 |
| public_blind | A | True | 0 | 0 |

- library import scan (`src/brainir` importing benchmarks/oracle/evaluator): none
- pytest leakage guard (`tests/test_leakage_guard.py`): passed
- node lists: 0 suspicious hits

## Clean-room protocol

1. A discovery method runs through `benchmarks/dng100/cleanroom/run_method.py`, which copies one bundle into a fresh
   directory, executes the method in a subprocess with `BRAINIR_BUNDLE` pointing at that copy, an environment stripped
   of secrets, and no access to `benchmarks/dng100/oracle`, `benchmarks/dng100_walking_cpg` or `research/literature`
   (the method runs under the audit-hook sandbox `_sandbox.py`: file access is confined to the bundle copy, the output
   directory, the Python installation and temp, so the repository, the oracle, tier B and user files are unreadable; no
   subprocesses, sockets or ctypes calls; imports of `benchmarks`/`oracle`/`evaluate` are refused statically; the method's
   declared inputs (`MethodInfo.inputs`) are recorded, not verified). This stops inadvertent and casual leakage; it is not
   OS-level isolation.
2. The method writes `prediction.json` (schema `brainir.benchmark.prediction`, version 1.0.0). Its SHA-256 and the bundle
   SHA-256 are recorded before evaluation.
3. `benchmarks/dng100/evaluator/evaluate.py` is the only code that reads the oracle. It writes metric families separately;
   no aggregate score exists.

## Answer-bearing locations (never expose to a method)

`benchmarks/dng100/oracle/`, `benchmarks/dng100_walking_cpg/`, `research/literature/`, `goal1.md`, `goal2.md`,
`PHASE0_REPORT.md` §13, and any evaluation output.
