# Session search-by_name: notes

Known sources (excluded as new leads): Harris et al. 2015 (10.7554/eLife.04493), Soffers et al. 2025 (10.7554/eLife.106042, incl. its
bioRxiv versions 10.1101/2024.11.27.625713), Cheong et al. 2024 (10.7554/eLife.96084). Most by-name queries led back to these.

## Queries run (WebSearch)
1. hemilineage activation ventral nerve cord Drosophila adult behavior CsChrimson
2. hemilineage dTrpA1 activation leg movement Drosophila thoracic hemilineage
3. "hemilineage 13A" OR "13A neurons" optogenetic activation grooming Drosophila
4. "hemilineage 8B" OR "8B neurons" activation Drosophila wing song ventral nerve cord
5. "hemilineage 23B" OR "23B neurons" Drosophila activation leg
6. "hemilineage 7B" OR "7B neurons" Drosophila activation takeoff wing
7. "hemilineage 9A" OR "9A neurons" Drosophila optogenetic activation walking proprioception
8. "hemilineage 12A" OR "12A neurons" Drosophila activation wing courtship song
9. "20A/22A" OR "hemilineage 20A" OR "hemilineage 22A" Drosophila activation legs
10. "hemilineage 2A" OR "hemilineage 11B" OR "hemilineage 18B" Drosophila wing buzzing activation
11. "hemilineage 10B" OR "10B neurons" Drosophila activation pausing walking
12. "hemilineage 19A" OR "19B" OR "3B" OR "6A" OR "6B" Drosophila activation behavior
13. "hemilineage 21A" OR "21A neurons" Drosophila activation leg flexion optogenetic
14. "hemilineage 0A" OR "1A" OR "1B" OR "14A" OR "17A" Drosophila activation
15. "13B neurons" activation Drosophila leg optogenetic headless
16. Drosophila hemilineage CsChrimson decapitated flies leg posture split-GAL4 lineage 2025 OR 2026 preprint
17. "A central somatotopic map of the fly leg" 23B bioRxiv
18. "A spinal substrate for modular control of natural behavior" Drosophila hemilineage
19. Shirangi 2016 Doublesex TN1 neurons hemilineage 12A activation sine song
20. Ehrhardt "wing premotor" split-GAL4 hemilineage activation CsChrimson
21. "hemilineage 5B" OR "4B" OR "24B" OR "15B" OR "3A" Drosophila activation behavior
22. Drosophila neuronal hemilineage thermogenetic activation adult behavior Truman Shepherd 2016-2023
23. "Extensive and diverse patterns of cell death sculpt neural networks in insects" undead hemilineage activation
24. Lacin 2019 neurotransmitter identity lineage-restricted activation behavior
25. hemilineage-specific activation adult Drosophila CsChrimson OR TrpA1 2026 bioRxiv leg wing
26. "lineage 8A" OR "8A neurons" OR "hemilineage 8A" Drosophila activation jump OR courtship

Names covered: every name in hemilineage_names.csv appeared in at least one query (00A/0A, 00B/0B via the undead-0B hit, 01A, 01B,
02A, 03A, 03B, 04A/04B, 05B, 06A, 06B, 07B, 08A, 08B, 09A, 09B (via library hits), 10B, 11A/11B, 12A, 12B (not separately
queried; only seen in connectome text), 13A, 13B, 14A, 14B (not separately), 15B, 16B (via library hits), 17A, 17B/17X/18X/21X/
26X/27X (not separately queried: X-hemilineages returned nothing specific in combined queries), 18B, 19A, 19B, 20A, 20B, 21A,
21B, 22A, 22B, 23B, 24B, 25B). The last ~6 queries gave no new candidates, so I stopped. Gap: I did not run separate queries for
12B, 14B, 17B, 20B, 21B, 22B, 25B or the X hemilineages, and I did not query "HL"-prefixed spellings separately.

## Pages fetched / access
- PMC7156266 (Lacin 2020, Unc-4): read in full (2 parts); activation only cited -> reject.
- PLoS ONE 10.1371/journal.pone.0155957 (Mellert 2016): first 100k chars read; activation only cited -> reject.
- bioRxiv 10.1101/626465v2 (Pop et al.): first 100k chars; Fig 5 TrpA1 activation of undead MARCM clones in decapitated flies.
- bioRxiv 10.1101/2023.05.31.542897v1 (Ehrhardt): first 100k of 472k chars only; remainder not read.
- Europe PMC REST: metadata/abstracts for Syed et al. (eLife.106446), Ye et al. 2024, Dallmann et al. 2023/2025.
- Could NOT access (error page / captcha / cookies): elifesciences.org pages (articles/55007, 106446, 59566/figures,
  reviewed-preprints/106548), PMC12844901 (reCAPTCHA), PubMed 38895414 (cookies), bioRxiv 10.64898/2026.03.12.711392 (HTTP 429;
  identified as a mouse study from search results instead).
- Not opened: Shirangi 2016 Dev Cell full text, Elabbady 2026 full text, Agrawal 2020 full text (details come from search snippets),
  the UW dissertation (not a journal article/preprint).

## Protocol-related notes
- Syed, Ravbar & Simpson (eLife.106446) contains a computational model of 13A/13B circuits. I deliberately did not open its
  full text; the search-result summaries mentioned that "a computational model backs this up" without describing any predicted
  activation outcome. I don't count this as a sighting (no predicted behaviour of hemilineage activation was shown), so no
  out/sightings.csv was written. The coder should be warned before opening this paper.
- No GitHub/Zenodo pages were visited. A GitHub wiki (FANC_auto_recon) showed up in search results and was not opened.
- Pugliese et al. 2026 and Sapkal et al. 2026 were not searched for or opened.
- My own memory was not used as evidence; everything in leads.csv rests on pages or search results seen in this session.
