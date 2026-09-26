# Level B evaluation log (synthetic heldout / final; PROTOCOL.md sections 9-10)

| time (UTC) | round | suite | methods | result file |
|---|---|---|---|---|
| 2026-09-25T16:01:08Z | r1_sd | heldout | sd_shared, sd_lowrank | research/phase3/tournament/r1_sd/ |
| 2026-09-25T16:05:08Z | r1_cb | heldout | cb_interchange, cb_psr, cb_cegar | research/phase3/tournament/r1_cb/ |
| 2026-09-25T16:13:11Z | r1_ks | heldout | ks_sindy, ks_edmd, ks_kae, ks_hankel | research/phase3/tournament/r1_ks/ |
| 2026-09-25T16:16:12Z | r1_lin | heldout | lin_subspace, lin_balanced, lin_pcadyn, lin_dmdc, lin_falds | research/phase3/tournament/r1_lin/ |
| 2026-09-25T16:54:21Z | r1_nn | heldout | nn_closed, nn_pred_bottleneck, nn_aelin, nn_rssm, nn_seqbottleneck | research/phase3/tournament/r1_nn/ |
| 2026-09-25T17:24:33Z | r2_ks_hankel | heldout | ks_hankel | research/phase3/tournament/r2_ks_hankel/ |
| 2026-09-25T17:26:02Z | r2_lin_falds | heldout | lin_falds | research/phase3/tournament/r2_lin_falds/ |
| 2026-09-25T17:30:41Z | r2_lin_subspace | heldout | lin_subspace | research/phase3/tournament/r2_lin_subspace/ |
| 2026-09-25T17:31:25Z | r2_cb_cegar | heldout | cb_cegar | research/phase3/tournament/r2_cb_cegar/ |
| 2026-09-25T17:31:35Z | r2_lin_dmdc | heldout | lin_dmdc | research/phase3/tournament/r2_lin_dmdc/ |
| 2026-09-25T17:32:07Z | r2_ks_edmd | heldout | ks_edmd | research/phase3/tournament/r2_ks_edmd/ |
| 2026-09-25T17:33:15Z | r2_ks_sindy | heldout | ks_sindy | research/phase3/tournament/r2_ks_sindy/ |
| 2026-09-25T17:36:34Z | r2_nn_closed | heldout | nn_closed | research/phase3/tournament/r2_nn_closed/ |
| 2026-09-25T17:40:51Z | r2_lin_balanced | heldout | lin_balanced | research/phase3/tournament/r2_lin_balanced/ |
| 2026-09-25T18:10:34Z | r2_nn_aelin | heldout | nn_aelin | research/phase3/tournament/r2_nn_aelin/ |
| 2026-09-25T21:16:17Z | r3_brainir_state_v1 | heldout | brainir_state_v1 | research/phase3/tournament/r3_brainir_state_v1/ |
| 2026-09-25T23:28:20Z | r3v3_lin_subspace | heldout | lin_subspace | research/phase3/tournament/r3v3_lin_subspace/ |
| 2026-09-25T23:32:45Z | r3v3_lin_falds | heldout | lin_falds | research/phase3/tournament/r3v3_lin_falds/ |
| 2026-09-25T23:34:05Z | r3v3_ks_edmd | heldout | ks_edmd | research/phase3/tournament/r3v3_ks_edmd/ |
| 2026-09-25T23:34:10Z | r3v3_ks_hankel | heldout | ks_hankel | research/phase3/tournament/r3v3_ks_hankel/ |
| 2026-09-25T23:34:13Z | r3v3_ks_sindy | heldout | ks_sindy | research/phase3/tournament/r3v3_ks_sindy/ |
| 2026-09-25T23:34:27Z | r3v3_nn_closed | heldout | nn_closed | research/phase3/tournament/r3v3_nn_closed/ |
| 2026-09-25T23:35:14Z | r3v3_lin_balanced | heldout | lin_balanced | research/phase3/tournament/r3v3_lin_balanced/ |
| 2026-09-25T23:35:58Z | r3v3_cb_cegar | heldout | cb_cegar | research/phase3/tournament/r3v3_cb_cegar/ |
| 2026-09-25T23:36:03Z | r3v3_nn_aelin | heldout | nn_aelin | research/phase3/tournament/r3v3_nn_aelin/ |
| 2026-09-25T23:39:15Z | r3v3_lin_pcadyn | heldout | lin_pcadyn | research/phase3/tournament/r3v3_lin_pcadyn/ |
| 2026-09-25T23:42:06Z | r3v3_lin_dmdc | heldout | lin_dmdc | research/phase3/tournament/r3v3_lin_dmdc/ |

Note (2026-09-25, orchestrator): the row `r3v3_lin_dmdc` at 23:42:06Z is INVALID. Every evaluation of that attempt failed at import
time in the Modal containers (a NameError in `scripts/p3/p3modal/remote.py` introduced by re-lock 1: a decorator used before its
definition). An infrastructure failure, not a result of the method. Its output was moved to
`research/phase3/tournament/_failed/r3v3_lin_dmdc_attempt2_infra/`. The first attempt of that part (23:2x) had died on a Modal client
SSL error before writing results. The part is re-run after re-lock 2 (execution only), with the same cached fits.
| 2026-09-25T23:46:46Z | r3v3_nn_aelin_t | heldout | nn_aelin_t | research/phase3/tournament/r3v3_nn_aelin_t/ |
| 2026-09-25T23:48:09Z | r3v3_lin_dmdc | heldout | lin_dmdc | research/phase3/tournament/r3v3_lin_dmdc/ |
| 2026-09-25T23:55:03Z | r3v3_ks_hankel_t | heldout | ks_hankel_t | research/phase3/tournament/r3v3_ks_hankel_t/ |
| 2026-09-25T23:58:01Z | r3v3_nn_seqbottleneck | heldout | nn_seqbottleneck | research/phase3/tournament/r3v3_nn_seqbottleneck/ |
| 2026-09-25T23:58:45Z | r3v3_lin_dmdc_t | heldout | lin_dmdc_t | research/phase3/tournament/r3v3_lin_dmdc_t/ |
| 2026-09-25T23:58:59Z | r3v3_lin_pcadyn_t | heldout | lin_pcadyn_t | research/phase3/tournament/r3v3_lin_pcadyn_t/ |
| 2026-09-26T00:05:36Z | r3v3_nn_rssm | heldout | nn_rssm | research/phase3/tournament/r3v3_nn_rssm/ |

Note (2026-09-25, orchestrator): the row `r3v3_nn_aelin_t` at 23:46:46Z is INVALID for the same infrastructure reason (every fit of
that first launch failed at import in the Modal containers under re-lock 1: 95 of 95 fits failed, no evaluation ran). Its output was
moved to `research/phase3/tournament/_failed/r3v3_nn_aelin_t_launch1_infra/`; the part was relaunched under re-lock 2. The other
tuned-variant parts of that first launch were stopped before writing results.
