# Session a5-g09-B (label audit, run 5)

I read only the three assigned sources in `sources/`; there was no web access. No simulation scores, ranks or driver calls from a connectome activation screen appeared for any assigned type, so `saw_simulation_score` = false.

## 10.1038/s41467-018-05875-1 (Zacarias et al. 2018)
- One record: DNp09 > CsChrimson (split line SS01540), freely moving females (Fig. 6, open loop plus closed loop by speed).
- Mapping: the kit lists SS01540 as AMBIGUOUS (DNp09;DNp71), and "DNp09" is also the hemibrain name of MANC DNp71. The paper uses Namiki 2018 nomenclature, so I chose MANC DNp09 at medium confidence.
- Coding uncertainty: activation produced a short increase in speed and then freezing. Baseline speed was about 10 mm/s (Fig. 6d), so most flies were already walking, and the speed-up lasted under 1 s. Under PROTOCOL 3 (freezing → `no`/`stops`; speed change in walking flies is not rhythm) I coded all legs `no`, with behaviour `halting` and secondary `forward_walking`. A reader who treats the induced "running" as evoked stepping could code the legs `yes`. Labeler confidence is medium because there was no leg tracking.
- The DN screen in the paper is Kir2.1 silencing (not records). Supplementary movies were not downloaded; they were not needed.

## 10.1038/s41586-025-08925-z (Stürner et al. 2025)
- Connectomics only. Behavioural statements (DNa12 activation, etc.) are cited from other work. No record.

## 10.1038/s41593-023-01332-5 (Cury & Axel 2023)
- Optogenetics targets PU sensory neurons and CMU motor neurons. oviDNs are discussed from prior work only. No assigned DN type is activated. No record.
