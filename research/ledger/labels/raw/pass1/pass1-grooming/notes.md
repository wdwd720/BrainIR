# pass1-grooming: notes

Session `pass1-grooming`, pass `pass1`. Source family: grooming and other limb-cleaning DNs.
39 records in `out/records.jsonl` (p1-grooming-0001 … 0039).

## Simulation exposure
- I saw no model or simulation score or prediction for any DN type. `saw_simulation_score` = false on every record.
- I did not open Özdil et al. 2024 (bioRxiv 10.1101/2024.12.17.628844, "Centralized brain networks underlie body part
  coordination during grooming"). Its metadata shows it is built around a neuromechanical model and connectome network
  analysis (PROTOCOL §6). It may also contain real-fly DN activation. A session allowed to screen it should check.
- When fetching papers that might contain model content (Braun 2024, Calle-Schuler 2026, Syed 2024/2026), I told the
  extraction tool to report only real-fly experiments and to leave out any model or simulation results.

## What I searched
- Europe PMC (REST search and full-text XML), bioRxiv, PubMed metadata and web search, for: Hampel/Seeds lab grooming papers,
  Simpson lab grooming papers (Guo 2022, Zhang & Simpson 2022, Ravbar 2021, Yoshikawa 2024, Syed 2024/2026), and
  general queries ("descending neuron" + grooming + optogenetic/activation; DNg11/DNg12/aDN).
- I could not load eLife and PMC HTML pages (JS/browser check), so I read the same text through Europe PMC fullTextXML.

## Sources with records
- **Hampel et al. 2015 eLife** (13 records): five spGAL4 pairs with dTrpA1 (Fig. 2): aDN1-spGAL4-1, aDN2-spGAL4-2/3/4 and
  aBN1/aDN1-spGAL4. The paper says five pairs target single DNs, but I could identify only four single-DN pair names in the
  text (no "aDN2-spGAL4-1" or second aDN1 pair appears); Supplementary file 1 was not opened. Also R18C11-GAL4
  ("aDN-GAL4", three aDNs plus other neurons) and aDN-LexA (three aDNs), each split into one record per aDN, and
  CsChrimson activation of aDN1-spGAL4-1 and aDN2-spGAL4-2 (Fig. 7). The antennae-amputated condition gave the same
  behaviour, so it is noted, not recorded separately.
- **Guo, Zhang & Simpson 2022 Curr Biol** (20 records): the journal version is paywalled. I first coded it from the GSA 2022
  conference abstract (abstract only), then found the NSF PAR accepted manuscript. I read it through a public
  text-extraction reader (r.jina.ai; only the public PAR URL was sent) and replaced the abstract-based records with
  full-text records, so the same experiments are not counted twice. Experiments: DNg12 (SS02608 + Otd-FLP), DNg11
  (SS01550, plus Fig. S1 lines SS02391/SS01579/SS02617), aDN (R18C11-GAL4), fly-on-a-ball DNg12/aDN, unilateral
  DNg12/aDN1/DNg11 clones, and DNg11+aDN co-activation.
- **Braun et al. 2024 Nature** (6 records): only the grooming-related DNs, aDN2, aDN1 and DNg11, each intact-tethered and
  headless on a ball. The paper's other DNs belong to the walking_stopping family and are not recorded here.

## Sources checked with no qualifying experiment
Yoshikawa 2024 (MGT, a VNC neuron), Syed 2024/2026 (13A/13B), Zhang & Simpson 2022 (wPN1, VNC), Ravbar 2021 (bristle
sensory), Seeds 2014 (GAL4 screen, no DN lines identified), Hampel 2017, Hampel 2020 and Eichler 2024 (sensory neurons),
Calle-Schuler 2026 (LB23/aBN2 lines, not described as DN lines). Some long texts were checked only in the first
100k characters (Seeds 2014, Hampel 2017/2020, Eichler 2024, Ravbar 2021). Results sections fall inside that range, but a
DN line mentioned only in the Methods could have been missed.

## Mapping issues and uncertainty
- **aDN2**: synonyms.csv gives aDN2 → DNfl023 (unique), so mapping is `high`. Note that driver_lines.csv has conflicting
  rows for aDN2-spGAL4-2/3/4 giving "DNg127", which is not a MANC type (UNMAPPED). I followed the paper name.
- **DNg12**: the name DNg12 is a MANC type, but synonyms.csv flags it as ambiguous (DNfl028 through a MaleCNS string
  conflict), and SS02608 is AMBIGUOUS (DNfl028;DNg12) in driver_lines.csv. I chose the same-named type DNg12 at `medium`.
- **SS02617**: the paper uses it as a DNg11 line. Per the kit (Namiki annotation "DNg11, DNg12") it also labels DNg12, so it
  gets a second `low`-confidence DNg12 record (0019).
- **"aDN" / R18C11-GAL4 / aDN-LexA**: these label three aDNs (aDN1, aDN2, aDN3). Each gets one record per aDN; aDN3 has no
  MANC mapping (UNMAPPED). For aDN-LexA and the Guo fly-on-a-ball aDN experiment, the neuron identities and driver are
  assumed, so mapping is `low`.
- **Legs**: none of these papers tracked middle or hind legs. Following the grooming convention, front legs are `yes`
  and middle/hind legs are `unclear`, because no paper says the flies stood still. Unilateral head sweeps (one front
  leg) are still coded front = `yes`, with a note.
- **Headless aDN2 (Braun)**: "front leg approach" without grooming is coded as a single movement (front = `no`), category `other`.
- **Headless aDN1 (Braun)**: "uncoordinated front leg movements" is coded front = `unclear`.
- **n flies**: the "n ≥ 9" symbols in Guo 2022 were garbled in the extracted text, so I recorded 9 with a note.
- The Braun line IDs (aDN1 18C11-p65AD;R71D01-DBD, aDN2 R76F12-AD;R18C11-DBD, DNg11 SS01550) come from the kit's
  driver_lines.csv (Braun supplementary). I did not open the supplement myself.

## Not covered (other families)
The Cande et al. 2018 atlas reports grooming for many DN lines (e.g. SS02635 DNg07/DNg08 head grooming). That belongs to
the atlas family and was not opened or recorded here.
