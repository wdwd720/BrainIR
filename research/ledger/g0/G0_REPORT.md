# Gate G0: MANC rebuilds on this machine vs the committed manifests

Rebuilt with `uv run brainir ingest --dataset manc --version <v>` on this Mac; compared with `git show HEAD:data/manifests/...` by `ledger/scripts/g0_check.py`. Documentation snapshots of web pages are not pipeline inputs and are not compared.

## manc_v1.0: PASS (byte-identical outputs)

- raw input files compared by SHA-256: 11
- validation: committed {'pass': 48, 'fail': 0, 'warn': 3, 'info': 26}, rebuilt {'pass': 48, 'fail': 0, 'warn': 3, 'info': 26}

| table | rows committed | rows rebuilt | schema equal | file sha256 equal |
|---|---|---|---|---|
| neurons | 23514 | 23514 | True | True |
| connections | 5275519 | 5275519 | True | True |
| connection_neuropils | 6206370 | 6206370 | True | True |
| neuron_neuropils | 104433 | 104433 | True | True |
| neuropils | 61 | 61 | True | True |
| neuron_annotations_source | 102369 | 102369 | True | True |


## manc_v1.2.1: PASS (byte-identical outputs)

- raw input files compared by SHA-256: 18
- validation: committed {'pass': 32, 'fail': 0, 'warn': 1, 'info': 23}, rebuilt {'pass': 32, 'fail': 0, 'warn': 1, 'info': 23}

| table | rows committed | rows rebuilt | schema equal | file sha256 equal |
|---|---|---|---|---|
| neurons | 24143 | 24143 | True | True |
| connections | 5338378 | 5338378 | True | True |
| connection_neuropils | 6272749 | 6272749 | True | True |
| neuron_neuropils | 106118 | 106118 | True | True |
| neuropils | 61 | 61 | True | True |
| neuron_annotations_source | 24143 | 24143 | True | True |


## manc_v1.2.3: PASS (byte-identical outputs)

- raw input files compared by SHA-256: 18
- validation: committed {'pass': 33, 'fail': 0, 'warn': 1, 'info': 24}, rebuilt {'pass': 33, 'fail': 0, 'warn': 1, 'info': 24}

| table | rows committed | rows rebuilt | schema equal | file sha256 equal |
|---|---|---|---|---|
| neurons | 23665 | 23665 | True | True |
| connections | 5305638 | 5305638 | True | True |
| connection_neuropils | 6239883 | 6239883 | True | True |
| neuron_neuropils | 105391 | 105391 | True | True |
| neuropils | 61 | 61 | True | True |
| neuron_annotations_source | 23665 | 23665 | True | True |


## Connectivity against the authors' matrices (`benchmarks/dng100_walking_cpg/reproduce_manc_connectivity.py`)

Run on this Mac on the rebuilt builds; the authors' files were fetched by `fetch_external()` and verified against their
pinned SHA-256. Result (copies of the regenerated outputs: `manc_reproduction_rebuilt_on_mac.md`,
`manc_reproduction_summary_rebuilt_on_mac.json`; the committed files were restored afterwards):

| authors' network | BrainIR build | pairs (authors / BrainIR) | exact counts | total synapses |
|---|---|---|---|---|
| MANC front-leg (4,604; 2025-08-13) | `manc:v1.2.1` | 196,535 / 196,535 | 196,535 (100 %) | 3,817,772 / 3,817,772 |
| MANC full cord (23,532; 2025-10-06) | `manc:v1.2.3` | 1,372,404 / 1,372,404 | 1,372,404 (100 %) | 24,149,548 / 24,149,548 |

Sign rule on the authors' `predictedNt`: 100 % agreement for both networks. The regenerated report differs from the
committed one only by the missing MaleCNS rows (MaleCNS is not built on this machine, LOG L9); every MANC row is identical.

**G0: PASS** for both networks the core arms need. The MaleCNS part is not run (see LOG L9).
