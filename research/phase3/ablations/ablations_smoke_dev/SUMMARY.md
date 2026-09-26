# Ablations of brainir_state_v1 (dev suite, round ablations_smoke_dev)

- 1 switches x 2 systems (1 compressible), seed 0; locked: False; hidden material: False; backend modal
- Paired differences = variant minus full per compressible system (median [system-bootstrap 95 % CI]); S1-S4 lower is better, S5 higher is better; S6 = exact-k rate difference.

| variant | removes | S1 | S2 | S3 | S4 | S5 | S6 | verdicts (compressible) | failures |
|---|---|---|---|---|---|---|---|---|---|
| full | (the full locked method) | 0.922 | 0.981 | 0.0811 | 0.00781 | -0.172 | 0 | not supported: 1 | 0+0 |
| domain_clip | latent rollouts confined to the widened training box -> unco | 5.11e-15 [5.11e-15, 5.11e-15] | -9.99e-16 [-9.99e-16, -9.99e-16] | 4.13e-14 [4.13e-14, 4.13e-14] | 0 [0, 0] | 1.15e-14 [1.15e-14, 1.15e-14] | 0 [0, 0] | not supported: 1 | 0+0 |

The full method's row shows its profile values; the other rows show paired differences against it.
