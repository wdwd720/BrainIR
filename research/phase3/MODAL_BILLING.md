# Phase 3 Modal billing (billed, not estimated)

Source: Modal workspace billing report, hourly, 2026-09-25T03:00:00+00:00 to the last complete hour 2026-09-26T11:00Z (`scripts/p3/modal_billing.py`).

**Total billed: $136.03** over 126 apps.

| stage | USD |
|---|---|
| lock hour 01:00 UTC (end of round 3 + start of the FINAL confirmation) | 11.09 |
| post-lock (FINAL, hidden data, Level C, sweeps, ablations, reviews G) | 79.80 |
| pre-lock (development, calibration, Level B) | 45.14 |

| app name | USD |
|---|---|
| brainir-p3-tournament | 86.09 |
| brainir-p3-levelc-fast | 39.20 |
| brainir-p3-devrun | 5.00 |
| brainir-p3-postlock | 3.47 |
| brainir-p3-quota-probe | 2.23 |
| brainir-p3-devdata-sync | 0.04 |
| brainir-p3-upload-view | 0.00 |

| hour (UTC) | USD by app name |
|---|---|
| 2026-09-25T09:00Z | brainir-p3-tournament 0.01 |
| 2026-09-25T10:00Z | brainir-p3-tournament 1.41 |
| 2026-09-25T11:00Z | brainir-p3-tournament 2.40, brainir-p3-upload-view 0.00 |
| 2026-09-25T15:00Z | brainir-p3-tournament 2.88 |
| 2026-09-25T16:00Z | brainir-p3-tournament 3.02 |
| 2026-09-25T17:00Z | brainir-p3-tournament 9.68 |
| 2026-09-25T18:00Z | brainir-p3-tournament 1.20 |
| 2026-09-25T20:00Z | brainir-p3-tournament 0.24 |
| 2026-09-25T21:00Z | brainir-p3-postlock 0.00, brainir-p3-tournament 0.96 |
| 2026-09-25T22:00Z | brainir-p3-tournament 3.00, brainir-p3-postlock 0.00 |
| 2026-09-25T23:00Z | brainir-p3-tournament 10.30, brainir-p3-devrun 0.01, brainir-p3-devdata-sync 0.04 |
| 2026-09-26T00:00Z | brainir-p3-tournament 5.00, brainir-p3-devrun 4.99 |
| 2026-09-26T01:00Z | brainir-p3-tournament 11.09 |
| 2026-09-26T02:00Z | brainir-p3-tournament 13.12 |
| 2026-09-26T05:00Z | brainir-p3-tournament 3.08 |
| 2026-09-26T06:00Z | brainir-p3-tournament 9.58, brainir-p3-postlock 1.28 |
| 2026-09-26T07:00Z | brainir-p3-levelc-fast 25.94, brainir-p3-quota-probe 2.23, brainir-p3-tournament 2.07, brainir-p3-postlock 0.74 |
| 2026-09-26T08:00Z | brainir-p3-levelc-fast 13.08, brainir-p3-postlock 1.44, brainir-p3-tournament 4.41 |
| 2026-09-26T09:00Z | brainir-p3-tournament 1.76, brainir-p3-levelc-fast 0.18 |
| 2026-09-26T10:00Z | brainir-p3-tournament 0.24 |
| 2026-09-26T11:00Z | brainir-p3-tournament 0.64 |

Billed amounts (measured usage). The job records' list-price estimates assume a 2-core / 6 GiB reservation per container and overstate the bill; they remain the per-task attribution.
