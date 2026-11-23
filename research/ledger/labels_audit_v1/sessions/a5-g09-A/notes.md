# a5-g09-A notes (audit, run 5)

I read all three assigned sources from local files only. I did no web access and did not search for other sources.

- **10.1038/s41467-018-05875-1 (Zacarias et al. 2018):** I read the full text, the Fig. 6 image and the supplementary text (grepped for activation). There is one activation experiment: DNp09 > CsChrimson (SS01540) in freely walking females, which produced an initial run followed by freezing. I coded it as halting with legs `no` under the stopping convention. The initial speed increase happened in flies that were already walking (baseline about 10 mm/s), so I did not treat it as evidence for leg rhythm. The name "DNp09" is ambiguous in synonyms.csv (it is also the hemibrain name for DNp71). I mapped it to MANC DNp09 with medium confidence because the paper uses Namiki nomenclature. The line has "weak off-target labeling", which I coded as `minor_offtarget`. The reviewer comments in the peer-review file (MOESM2) are not the paper's claims and were not used.
- **10.1038/s41586-025-08925-z (Stürner et al. 2025):** This is a connectomics paper with no fly experiments of its own. Behavioural statements (for example, DNa12 activation) are cited from earlier work, so it has no record.
- **10.1038/s41593-023-01332-5 (Cury & Axel 2023):** Optogenetic activation is used only on PU sensory neurons and CMU motor neurons. oviDNs are discussed from the literature only. No record.

I saw no simulation scores, ranks or driver calls for any assigned type.
