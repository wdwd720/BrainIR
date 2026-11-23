# Session a5-g11b-B notes (label audit, run 5)

Assigned types: DNp11, DNp16, DNp18, DNp42, DNp71, DNxl022, MDN.
Assigned sources: Braun et al. 2024 (10.1038/s41586-024-07523-9) and Yang et al. 2023 bioRxiv (10.1101/2023.10.15.562426). I read both in full from the local files. I used no web access.

## Braun et al. 2024: 9 records
- **MDN** (line SS03131, called "MDN-spGAL4 / MDN3"). Records:
  - Fig. 2a (imaging preparation).
  - Ext. Data Fig. 1d,e (intensity and illumination-site series).
  - Fig. 4d, intact.
  - Fig. 4d, headless on ball.
  - Ext. Data Fig. 10b (hind-leg amputation; legs unclear).
  - Reviewer Figure 2 from the peer-review file (MOESM3), intact and headless flies hanging in air. For these, the hind-leg "in-air-stepping" / "backward stepping movements" are coded yes and the other legs not_assessed. Their quotes come from the supplementary file, not text.txt, so their notes start with `figure:`.
- **DNp42** (SS57807): Ext. Data Fig. 5a. Intact flies back up ("backing up" / "backwards retreat", coded as backward walking, medium confidence because only ball velocity was measured). Headless flies show no backward walking: legs coded no, medium confidence.
- Supplementary Table 2 gives SS03131's hemidrivers as VT023490-p65.AD; VT44845.GAL4DBD. The kit already lists this, with a note that the AD differs from other MDN sources. I recorded it as written.
- Backward walking is coded yes for all three leg pairs, following PROTOCOL section 3. The same paper's Ext. Data Fig. 10b shows that MDN-driven backward displacement depends on the hind legs. I mention this in the notes field but did not change the convention coding.

## Ambiguous names (DNp71, DNxl022): no records written
- The kit maps "DNp09" to DNp09 or DNp71 (SS01540 marked AMBIGUOUS) and "DNa01" to DNa01 or DNxl022 (SS00731 marked AMBIGUOUS).
- Braun et al. test both lines: DNp09 in Figs. 1-4 and Ext. Data Figs. 1-3 and 10; DNa01 in Ext. Data Fig. 5c. Their Methods say they searched MANC in neuPrint "based on their names" and "found all neurons that we used from ref. 14 (that is, DNp09, DNa01, and so on)". The paper's own anatomy therefore points to MANC DNp09 and DNa01, not to DNp71 or DNxl022.
- Following PROTOCOL section 4 (map ambiguous names to the type the paper's anatomy supports), these experiments belong to DNp09 and DNa01. Those types are not assigned to me, so I wrote no records for them.
- What a reviewer would find if the mapping were decided the other way:
  - DNp09, intact: forward walking (heterozygous; homozygous mostly freezing).
  - DNp09, headless: no walking, abdominal contraction only.
  - DNa01, intact: in-place turning.
  - DNa01, headless: turning lost.
- Yang et al. image DNa01 and DNp09 with the same hemidrivers but do not activate them.

## Other types
- DNp11 and DNp18 are only calcium-imaged in Yang et al. (Fig. S2).
- DNp16 (and its synonyms, e.g. PS226) does not appear in either source.
- Neither source has an activation experiment for these types.

## Simulation scores
- Neither source contains a Pugliese-type connectome activation score, rank or driver call.
- Braun et al.'s "connectome-based predictions" are counts of downstream DN partners, not simulations. `saw_simulation_score` = false on every record.

## Limitations
- Supplementary videos for Braun et al. were not downloaded, so I could not check video-only observations. One example is the "headless while hanging" condition of Supp. Videos 3-4, which has no reported figure result for MDN or DNp42.
- Yang et al.'s key resources table image was not available. This does not affect any assigned type.
