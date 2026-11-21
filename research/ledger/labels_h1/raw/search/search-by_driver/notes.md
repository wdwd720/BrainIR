# Notes: session search-by_driver

## Scope
Searched by driver: hemilineage-specific GAL4, split-GAL4 and LexA lines, lineage driver libraries, and studies that used such lines to activate neurons in adult flies.
Known sources were excluded: Harris 2015, Soffers/Lacin 2025 (eLife 106042, bioRxiv 2024.11.27.625713), and Cheong 2024.
Nothing was coded here; `leads.csv` only identifies candidates.

## Queries (WebSearch)
1. hemilineage-specific split-GAL4 ventral nerve cord Drosophila activation behavior adult
2. Drosophila hemilineage CsChrimson activation leg movement headless flies
3. lineage-specific GAL4 drivers Drosophila thoracic neuroblast hemilineage dTrpA1 behavior
4. "hemilineage" optogenetic activation adult Drosophila VNC split-GAL4 lines behavior 2023
5. Lacin Truman hemilineage activation Chrimson decapitated flies leg
6. "hemilineage 13A" OR "hemilineage 19A" OR "hemilineage 12A" activation flies behavior
7. wing premotor hemilineage split-GAL4 activation flight takeoff 6A 7B 18B
8. hemilineage 9A proprioceptive neurons optogenetic activation walking
9. hemilineage-restricted activation jump escape 8A 23B 11A
10. Dallmann presynaptic inhibition Nature 2025 doi
11. "secondary neurons" hemilineage activation TrpA1 headless Truman Shepherd
12. VNC "lineage" GAL4 activation "decapitated" CsChrimson hemilineage 2024 2025 bioRxiv
13. Pop Ramdya Williams 2020 undead neurons walking headless
14. Lacin unc-4 take-off circuit 7B activation
15. TN1 12A hemilineage dsx activation wing extension song
16. hemilineage Hox gene leg interneurons activation 2022
17. Shirangi 2016 Dev Cell 12A split-GAL4 activation (two queries)
18. "hemilineage" walking optogenetic split-GAL4 Bidaye/Ramdya/Card
19. "hemilineage 3A/19B/2A/6A" activation behavior
20. hemilineage transcription factor knock-in split-GAL4 Lacin 2025/2026 new preprint
21. Proprioceptive limit detectors, hemilineage activation
22. grooming hemilineage 23B/9B/20A/22A CsChrimson
23. flp-out clones hemilineage TrpA1 clonal activation
24. hemilineage TrpA1/CsChrimson abdominal/haltere/leg posture 2021-2023
25. lineage 0 / 0A / 1A activation walking

The last 5–6 queries returned only sources that were already found, so I stopped.

## Pages opened (WebFetch)
- PMC12844901 (Syed et al. eLife 106446): opened.
- PMC7752136 (Agrawal 2020): opened.
- PMC10634730 (Dallmann preprint): opened.
- Europe PMC full text of PMC7535934 (Pop 2020): opened.
- PMC11153019 (Ye 2024): opened.
- Europe PMC full text of PMC12933626 (Guo 2026): opened.
- Europe PMC full text of PMC10312520 (Ehrhardt): opened.
- bioRxiv 2024.02.11.579841 (Sproston): opened.

## Not accessible
- elifesciences.org article pages (106446, 60299, 59566) returned a site-load error; I used PMC or Europe PMC instead.
- The Pop 2020 PDF on epfl.ch could not be parsed.
- bioRxiv 626465 returned HTTP 429.
- PubMed pages were blocked by a cookie wall.
- pmc.ncbi PMC7535934 was blocked by browser verification.
- Shirangi 2016 (Dev Cell, cell.com) returned 403 and is not open access. Whether it activated 12A is still **unverified**.
- The Nature version of Dallmann 2025 was not opened; I read only the preprint.
- Lillvis 2024 (nested circuits) was not opened, and its journal DOI is not verified. The leads file lists the bioRxiv DOI.

## Other items seen
- Harris PhD thesis, "Form and function of the secondary hemilineages in the adult Drosophila thoracic nervous system" (Univ. Washington repository). It includes a TrpA1 activation chapter, but it is a thesis, not a journal article or preprint, and probably overlaps Harris 2015. It is not in `leads.csv`; this flag is for the coordinators.
- Reviews that only restate Harris 2015 (Curr Opin Neurobiol 2019 VNC development review, PMC6551290; Allen et al. 2020 VNC atlas) are not leads.
- The Janelia split-GAL4 resource (eLife 98405) is not organised by hemilineage, and no hemilineage activation was seen in snippets.

## Model/simulation exposure
- Search result lists included titles of computational papers: arXiv 2609.38665 ("How much of fly walking is written in the wiring?"), arXiv 2610.33881, and arXiv 2509.06426 (musculoskeletal simulation). **None were opened.**
- One auto-generated search summary paraphrased 2609.38665 at an aggregate level: a connectome model failed a 12-hemilineage benchmark, and a transmitter-sign rule matched 9 of 12. No per-hemilineage prediction was shown, so I judged this **not a sighting** under PROTOCOL §5 and wrote no `sightings.csv`. Coordinators may want to re-check this.
- Search-tool summaries also mixed in unverified claims (for example, attributing results to Harris 2015 "from memory"). I did not use them as evidence. Every lead's details come from a page I opened, or are marked as unverified.

## Assessment
None of the new candidates clearly activates a *whole* hemilineage. The strongest leads activate named subsets of hemilineages in adults, which could be `partial_or_mixed` or `one_sided` records if coordinators accept subsets:
- Syed et al. 2026 (13A/13B)
- Agrawal et al. 2020 (9Aα/10Bα/13Bα)
- Dallmann et al. 2025 (9A, one-sided subset)
- Pop et al. 2020 (undead 0B clones)
