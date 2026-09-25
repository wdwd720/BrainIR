# Phase 3 compute ledger (goal4 section 59)

Modal list prices used for the estimates: $0.192 per physical core-hour and $0.024 per GiB-hour. Containers have 2 cores and 6 GiB.
The per-job container seconds come from the jobs' own records: `modal_costs.json` per round, and the run logs.

## Modal

| time (PDT, 2026-09-25) | job | app | calls | container-s | ~USD |
|---|---|---|---|---|---|
| 02:48 | calibration smoke, 3 dev systems (first attempt crash-looped: module-level function pickled by reference; 0 containers ran) | ap-xAUUZwyI8kIuFXeNwWhN3n | 0 | 0 | 0.00 |
| 03:05 | calibration smoke, 3 dev systems (v2 code; Linux = Windows to ~1e-9) | ap-xxcC5GxuzBO5OuTwgwTJBH | 3 | 960 | 0.14 |
| 03:15 | CALIBRATION v2, 45 dev systems | ap-E6MBnFZtNmPTE89nrkCTdY | 45 | 14,303 | 2.10 |
| 03:50 | heldout suite extract (tar upload) | ap-IZtRekngNaKzQC5KTQsGZY | 2 | 57 | 0.01 |
| 04:00 | heldout reference controls (k-independent + k = 1), 48 systems | ap-nVT8iyPgdqMw9Ny79fCVGV | 48 | 9,242 | 1.36 |
| 04:05-04:40 | dev-suite smoke tournaments (2 failed attempts found two backend bugs, then a full run: lin_pcadyn, lin_dmdc with G and shared fits) | ap-a1a8RKTA2dmKo4MDM2UMSE, ... | ~560 | ~22,000 | 3.43 |
| 04:15 | final suite extract, fit views, review G suite upload | several | 6 | ~200 | 0.03 |

Running total so far: about **$7.1**.

## Local

- **Machine.** Ryzen 9 6900HX, 8 cores / 16 threads, shared by the method agents; wall-clock only.
- **Version 1 calibration.** 75 min on 7 workers (superseded).
- **Suite builds.** Synthetic suites and pools about 40 min; real public data about 40 min on 12 workers.
- **Root test suite.** 834 s under agent load.
