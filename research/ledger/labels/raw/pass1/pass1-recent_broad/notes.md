# Notes — session pass1-recent_broad (pass1)

Source family: other activation studies, especially 2018–2026 (excluding Cande 2018, Namiki 2018, the 2025 DN driver
collection, Lillvis 2024, Simpson-lab grooming papers, Bidaye 2014/2020, Sapkal 2024, Braun 2024, Rayshubskiy,
Yang 2024, Ache 2019, von Reyn 2014/2017, Pugliese 2026, Sapkal 2026).

Output: 39 records in `records.jsonl` (IDs 0001–0039; 0020 is the last line because records were inserted before it).

## What I searched
Web searches on: optogenetic or thermogenetic DN activation and walking (2024–2026 bioRxiv); MDN follow-up studies;
DNp09 freezing; takeoff and landing DNs; steering DNs (DNa11/DNa03); grooming DNs outside the Simpson lab; courtship
(aSP22, DNp13, pIP10, vpoDN); egg-laying (oviDN); feeding (Bract, Rounddown, Fudog); flight (DNg02); pose-tracking
methods papers (DeepFly3D, LiftPose3D, NeuroMechFly); thermogenetic TrpA1 DN studies; Pair1.
Full text came mainly from the Europe PMC REST API (fullTextXML) and bioRxiv full-text pages. bioRxiv returned HTTP 429
repeatedly; every bioRxiv source was eventually read after retries.

## Simulation and model exposure (important)
- I did not open Pugliese et al. (Nature 2026 / bioRxiv 2025.09.12.675944) or Sapkal et al. 2026, and I opened no model papers.
- Two **web-search result summaries** described the Pugliese bioRxiv by accident. They said its computational activation
  screen ranked **DNg100** as the top driver of rhythmic leg activity, and they mentioned **DNb08** (SS70620) in that context.
  So `saw_simulation_score` = true on the one DNg100 record (0038). I wrote no DNb08 record; any future DNb08 record from
  this session should carry the flag too.
- Search summaries also gave experimental (non-model) statements from Sapkal 2026 about DNg100 stepping in decapitated flies.
  I did not use them.
- I skipped Ozdil et al. (bioRxiv 2024.12.17.628844 / Nat Commun 2026) because it contains an in-silico activation screen
  of the grooming network. It may contain real activation experiments; a dedicated reader should decide.
- The Ceballos et al. iScience 2026 paper has in-silico parts. I asked only for in vivo content, and no DN scores were seen.

## Excluded or zero-record sources
- Rayshubskiy et al. eLife RP102230 (DNa02 ReaChR): I opened it before seeing it was an excluded family. No records.
- Simpson-lab grooming papers found and skipped: Yoshikawa, Tang & Simpson 2024 (MGT), and Syed, Ravbar & Simpson 2026
  (13A/13B inhibitory circuits, eLife 106446).
- No leg outcome reported, so outside the family: Namiki 2022 (DNg02 wing screen), Shiu 2022 (proboscis), Cury & Axel 2023,
  oviDN / vpoDN / DNp13 genital-behaviour papers (Wang 2020/2021, Mezzera 2020; not opened in full) and DNg02 optomotor
  preprints.
- Chen et al. 2018 (VNC imaging): no activation. Israel & Parnas 2025 Comms Biol: no adult DN activation.
- LiftPose3D reuses DeepFly3D data, so I made no duplicate records.

## Could not access
- McKellar et al. 2019 (aSP22 courtship; leg lifting is reported in secondary sources). The journal is paywalled, the
  Simpson-lab PDF failed with a TLS certificate error, and the abstract has no leg sentence, so I wrote no record. A full-text
  reader should add it; aSP22 activation is described as producing foreleg lifting and simultaneous movement of all legs.
- Sen et al. 2017 (MDN, including stochastic single-MDN activation and turning): paywalled (403), and the abstract has no
  quotable activation result.
- Kohatsu et al. 2011 (P2b courtship initiation, dTrpA1): I saw only the abstract. Legs are not described, so no record.
- Supplementary tables with line IDs for Dombrovski 2023 and Liessem 2025: not opened, so `driver_lines` is empty for those.

## Uncertain coding decisions
- 0001 DNp09 (Zacarias): a running bout followed by freezing, with freezing depending on the fly's speed. Legs coded `unclear`;
  category `halting`, with secondary `forward_walking`.
- 0012 DNp17 SPARC: the authors say DNp17 alone raises speed "only slightly, if at all", so this is coded as an unclear/weak
  effect with low confidence. The SS02553 speed-up (0011) is attributed mainly to DopaMeander, a non-DN in the same line.
- 0004, 0025: headless surface inferred as `ball` from the rig description. 0007, 0038: decapitated flies in an arena, so `other`.
- 0015: DNp02 "alone" is inferred from the sentence "activation of DNp02 (including combinations…) promoted backward leaning".
  Low confidence.
- 0016–0020: Dombrovski combination drivers → one record per DN type, marked `multi_dn`.
- 0022: aDN mapped to DNfl023 through the kit line R76F12-AD;R18C11-DBD (medium). Front leg coded `yes` for antennal grooming,
  but the text read does not name the legs.
- 0023/0024: DNa11 Fig. 2c is turning only (legs `not_assessed`). Fig. 5 has six-leg stepping kinematics (legs `yes`), and
  whether flies were stationary at onset is not stated.
- 0033: aSP22's landing response rests on the "all but one" statement; no aSP22-specific sentence was read.
- 0036/0037: Pair1 is UNMAPPED (no kit entry); R75C02-Gal4 is proposed with `UNMAPPED`.
- 0039: the MDN driver is written "VT50600" in the preprint, probably a typo for VT50660.
- DNp09, DNp17: kit names also map to DNp71 and DNut046 (ambiguous). Namiki types were chosen, with medium confidence.
