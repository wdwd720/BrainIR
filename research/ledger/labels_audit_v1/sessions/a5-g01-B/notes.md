# Session a5-g01-B — label audit notes (run 5)

## What I did
Read `PROTOCOL.md` and `AUDIT_NOTE.md` first (the note wins), then all four assigned sources in
`assigned_sources.csv`, against the 16 assigned DN types (DNa01, DNa13, DNb05, DNg79, DNp01, DNp02, DNp03,
DNp04, DNp06, DNp07, DNp10, DNp11, DNp17, DNp47, DNxl022, MDN). Nine records written; see
`dispositions.csv`.

## Source by source

**10.64898/2025.12.13.693955 (Liessem et al., landing/takeoff ensembles).** Main source of records.
Read `text.txt` in full, the supplement text (including Supplemental Table 1, which gives the driver line
IDs), and figures 1, 2, S1-1, S2-1, S2-2. CsChrimson activation (625 nm, 50 ms, 150 µW/mm²) in
pin-tethered flying females with DeepLabCut leg tracking: DNp07 (SS02276 and SS02612), DNp10 (SS01608),
DNp47 (GMR70C09-GAL4, BDSC #39524), DNg79 (SS81942), DNb05 (SS01051 plus three further lines).
All produce a landing response — one simultaneous extension of all six legs — not cyclic stepping, so every
leg-rhythm field is `no` per PROTOCOL section 3 ("single movements … `no`"). DNb05 drove no response at all
(`no_visible_effect`), which I recorded as a negative result since the screen reports it explicitly.
Takeoff DNs (DNp01, DNp02, DNp04, DNp06, DNp11) and DNa01, DNa13, MDN appear only in connectome/clustering
analysis in this paper, with no fly activation experiment, so no records for them.
Two caveats recorded in the records themselves: (a) `driver_lines.csv` lists SS81942 as labelling
"DNg31, DNg79", so the DNg79 record is `multi_dn`; the paper itself treats it as a DNg79 line.
(b) the DNp47 line is a plain GAL4 line, so `line_specificity` is `unknown`.

**10.1101/2025.07.22.666129 (Dahlhoff et al., walking direction).** Two DNp17 records, both from the
SS02553 split-GAL4 line: whole-line CsChrimson activation in the UFO free-walking arena (Fig. 2) and
stochastic SPARC2-CsChrimson activation of subsets (Fig. 3D-E). SS02553 labels eight neuron types, so both
records are `multi_dn` with the other types named. The paper's own conclusion is that DopaMeander, a
dopaminergic brain interneuron in the same line, and not DNp17, drives the fast/meandering walking; I kept
the records because the line does label DNp17 and the protocol requires one record per DN type labelled by
a non-specific line, and noted the authors' conclusion in `notes`.
MDN is treated at length in this paper, but only through Kir2.1 silencing, patch-clamp recordings and
linear-nonlinear modelling — no MDN activation experiment — so no MDN record.

**10.1016/j.cell.2005.02.004 (Lima & Miesenböck).** Cached copy is abstract-only. I was permitted to
fetch this DOI; cell.com, cell.com/action/showFullText and sciencedirect.com all returned HTTP 403, and the
paper is not open access in Europe PMC (inEPMC N, no PMCID). Labelled from the abstract: giant fiber system
photostimulation elicited jumping, wing beating and flight. Jump = single movement, so all leg rhythms `no`;
`labeler_confidence` `low` as required for abstract-only. The effector is P2X2/caged-ATP photolysis rather
than a channelrhodopsin; I coded `effector_kind` as `optogenetic` since the schema has only
optogenetic/thermogenetic, and said so in the record notes. Mapping "giant fiber system" → DNp01 is
`medium`, since the abstract names a system rather than a single cell type.

**10.1073/pnas.2618114123 (Lee et al., MDN cell body position).** Cached copy is abstract-only. I was
permitted to fetch it; pnas.org and pnas.org/doi/full both returned HTTP 403, and Europe PMC (PMID 42685078)
lists it as subscription-only with no PMC copy and no preprint link. The abstract almost certainly summarises
MDN activation experiments ("command neurons for backward locomotion, must maintain cell body contact to
initiate backward walking") but states no activation experiment result I could quote verbatim as a leg
outcome, with no driver line, effector or preparation. I therefore gave it `unreachable` rather than
`no_qualifying_experiment`: I could not read the text, and asserting it has no qualifying experiment would
be wrong. A session with publisher access should retry it — MDN records are likely there.

## Simulation sightings
Per `AUDIT_NOTE.md` I read every assigned source in full, including simulation sections. The Liessem landing
paper (10.64898/2025.12.13.693955) runs a connectome-constrained leaky integrate-and-fire model (Shiu et al.)
predicting landing-DN recruitment by LPLC4 clusters (Fig. S4-1B), and reports predicted per-DN responses. That
is the paper's own model, not a Pugliese-type rhythm score, rank or driver call, but it is a simulation result
printed for the assigned types, so I set `saw_simulation_score` = `true` on all six records from that source
and recorded nothing from it as evidence. No sightings file was written since no rhythm score, rank or
driver/non-driver call from a connectome activation screen was seen; `out/sightings.csv` is therefore absent.
The Dahlhoff paper's linear-nonlinear models are fits to its own electrophysiology, not a DN activation
screen, so `saw_simulation_score` = `false` on its records.

## Uncertainties
- DNp17 records rest on a line the authors themselves argue is not responsible for the phenotype. Coded as
  written, `mapping_confidence` `medium` (SS02553 is AMBIGUOUS: DNp17;DNut046 in `driver_lines.csv`),
  `labeler_confidence` `medium` (centroid tracking only, no leg tracking).
- Leg-rhythm fields for the two walking records are inferred from "increased locomotion" without leg
  tracking, as PROTOCOL section 3 directs.
- No new synonyms or driver lines needed proposing, so `proposed_synonyms.csv` and
  `proposed_driver_lines.csv` were not written.
