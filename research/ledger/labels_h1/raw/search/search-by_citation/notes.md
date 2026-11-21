# Session search-by_citation: notes

## Method
1. Resolved Harris et al. 2015 (eLife.04493) to PMID 26193122 through the Europe PMC REST search. Pulled its citation list:
   `europepmc/webservices/rest/MED/26193122/citations` (114 citing records).
2. Soffers et al. 2025 (eLife.106042), PMID 40492493: citation list via `MED/40492493/citations` (14 records). The preprint
   record PPR946410 had 0 citations.
3. Screened the titles of both lists. Plausible candidates were checked through abstracts (Europe PMC `resultType=core`) and, where
   needed, Europe PMC full-text XML (Agrawal 2020, Lacin 2020, Pop 2020, Ehrhardt 2023).
4. Free-text WebSearch queries to catch citers that Europe PMC has not indexed yet:
   - `hemilineage activation adult Drosophila ventral nerve cord CsChrimson behavior "hemilineage"`
   - `"Harris et al., 2015" hemilineage dTrpA1 activation leg movement ventral nerve cord`
   - `Syed "Inhibitory circuits control leg movements" 13A 13B activation ...`
   - `Lacin 2020 eLife "Unc-4 acts to promote neuronal identity" ...`
   - `Diamandi "Developmental remodeling repurposes larval neurons ..."`
   - `Agrawal 2020 eLife "Central processing of leg proprioception" ...`
   - `Dallmann "presynaptic inhibition" leg proprioception 9A ...`
   - `Girard 2026 "ShineGAL4" ...`, `Lai "Fd4 ..."`, `Israel 2025 Communications Biology ...`, `Drake 2025 "Fer3" ...`
   - `bioRxiv 2025 2026 hemilineage optogenetic activation decapitated flies ...`
   - `"hemilineage" activation "takeoff" OR "jump" OR "wing" adult Drosophila 2025 ...`
   - `"Hierarchical diversification of neurons regulating motivated behaviors" ...`
   - `Drosophila "hemilineage" neurons activated "headless" OR "decapitated" ...`
   - `"23B" OR "18B" OR "6A" hemilineage neurons optogenetic activation ...`
   - `Sproston "Hemilineage-specific" reaper grim undead ...`
   - `"Ascending nociceptive pathways ..."`, `Cachero 2026 Nature ...`
   - `"Soffers et al., 2025" hemilineage activation CsChrimson`
   - `2026 bioRxiv Drosophila hemilineage "optogenetic activation" ...`
   I stopped when the last four queries returned only papers already screened or the known sources.

## Result
Five leads in which the paper itself activates neurons named by hemilineage in adult flies: Syed 2026 (13A/13B subsets), Agrawal 2020
(13Bα/9Aα/10Bα), Dallmann 2025 (9A subset), Pop 2020 (MARCM clones of undead 0B), Elabbady 2026 (23B subsets).
**None of them activates a whole hemilineage** as Harris 2015 and Soffers 2025 do. All five are subsets, single cell types or
clones (`whole_hemilineage = no`), so they would be `partial_or_mixed` or `clonal` records at most, if they count at all. That call
is for the coders. Other screened citers were rejected; the reasons are in `leads.csv`.

## Titles rejected from the lists without opening them
Clearly not adult hemilineage activation: connectome or annotation papers (Berg 2026, Cheong 2023/2026, Marin 2023/2026,
Calle-Schuler, Lesser 2024, Phelps 2021, Moon, Dhawan flight atlas). Per protocol section 5 I did not open connectome-modelling
papers. The rest: descending-neuron studies (Braun 2024, Yang 2024, Guo 2022, Aymanns 2022, Carreira-Rosario 2018), larval or
embryonic or developmental work, reviews and commentaries (Lovick 2015 "Flies do the locomotion", Landgraf 2016, Sen 2019,
Hartenstein 2021, Venkatasubramanian 2019), non-neural papers (Kubrak, Malita, Weaver, Yoshinari), Meissner 2025 split-GAL4 resource,
Allen 2020 transcriptomic atlas, Lacin 2016/2019, Shepherd 2016/2019, Court 2020 nomenclature, Clark 2016 (larval), Syed 2016
(motor neuron development), Tuthill 2016, Chen CL 2018 (imaging), Cury 2023 (egg laying, brain), Sullivan 2019 (central complex),
Truman 2023 (mushroom body), Bello-Rojas 2022 (zebrafish), He 2016 (mouse), Kelly 2018 (mouse). Excluded on title alone; not
re-checked.

## Access problems
- eLife article and figure pages for 106446 returned a "required part of this site couldn't load" error. PMC (pmc.ncbi.nlm.nih.gov)
  served a reCAPTCHA. PubMed needed cookies. bioRxiv returned HTTP 429 (rate limit). I worked around this with Europe PMC REST and
  search-engine snippets.
- Syed 2026: details come from search snippets of the bioRxiv and eLife reviewed preprint versions. Full text not read.
- Dallmann 2025: what the 9A activation did is not confirmed (Extended Data). Full text not read.
- Elabbady 2026: details come from search snippets of the bioRxiv full text. I did not open it.
- Chen 2021, Luan 2020, Shirangi 2016: abstract only.
- Full-text XML reads stopped at the first 100k characters (Lacin 2020, Agrawal 2020, Pop 2020, Ehrhardt 2023). Those slices
  covered the results.

## Sightings / model exposure
No network-simulation prediction of what activating a hemilineage does was seen, so `out/sightings.csv` was not written.
Borderline items, noted for transparency:
- The Dallmann 2025 search summary said that, in the paper's model, stimulating descending neurons DNg100/DNg12 recruits chief 9A
  neurons. This is about recruitment of 9A by descending neurons, not about the effect of activating 9A, so I did not log it as a
  sighting.
- The Syed 2026 summaries said only that "a computational model reproduces major features of the behavior", with no
  hemilineage-activation prediction.
- A search result listed the title of a connectome-simulation preprint that protocol section 5 forbids opening. I did not open it.
- The Elabbady snippet said 23B activation drives grooming of "locations predicted by the connectome", which is connectivity, not
  a simulation.
