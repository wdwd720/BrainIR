# Session a5-g11b-A notes (label audit, run 5)

Assigned types: DNp11, DNp16, DNp18, DNp42, DNp71, DNxl022, MDN. Assigned sources: Braun et al. 2024 (10.1038/s41586-024-07523-9) and Yang et al. 2023 bioRxiv (10.1101/2023.10.15.562426). Both were read from local files only; no web access was used.

## Braun et al. 2024
- MDN (SS03131, called "MDN3" in the paper): five records. These cover Fig. 2a, ED Fig. 1d-e, Fig. 4d intact, Fig. 4d headless (backward walking persists) and ED Fig. 10b (intact-leg flies; hindleg amputation abolishes backward walking).
- DNp42 (SS57807): two records from ED Fig. 5a. Intact flies back up. Headless flies show no effect on fictive velocity.
- **Ambiguous names not coded under my types:**
  - The paper's "DNp09" (SS01540) is ambiguous between DNp71 and DNp09 in the kit (DNp71's hemibrain synonym; driver_lines lists SS01540 as AMBIGUOUS DNp09;DNp71).
  - The paper's "DNa01" (SS00731) is ambiguous between DNxl022 and DNa01 in the kit (DNxl022's hemibrain synonym; driver_lines lists SS00731 as AMBIGUOUS DNa01;DNxl022).
  - In both cases the paper uses the Namiki 2018 names and lines (ref. 14). It also states that it found "DNp09, DNa01" in the MANC connectome under those names (Methods, 'Analysing DN–DN connectivity in the VNC'). The anatomy therefore supports MANC DNp09 and DNa01, not DNp71 or DNxl022, so I wrote no DNp71 or DNxl022 records.
  - Caveat: the paper's FAFB naming rule prefers the hemibrain_type attribute, so its connectome figures may show hemibrain-"DNp09" or "DNa01" cells. The behavioural experiments, though, use the Namiki split lines.
  - For an adjudicator: DNp09 shows forward walking intact (Fig. 2a, 4b) and none headless. DNa01 shows turning intact and none headless (ED Fig. 5c).
- No experiments on DNp11, DNp16, DNp18 or DNp71.
- Supplementary Videos 3, 4 and 6 are not in the room. Leg codes rest on velocity traces, behaviour-probability traces and text.

## Yang et al. 2023
- DNp11 (VT025392AD;VT057247DBD), DNp18 (VT064490AD;R69C11DBD), DNa01 and DNp09 were calcium-imaged only (Fig. 2, Fig. S2).
- The only activation experiments in the paper are DNa02 (SPARC2-D CsChrimson) and DNg13 (current injection). Disposition: no_qualifying_experiment.

## Simulation scores
I saw no Pugliese-type rhythm score, rank or driver call in either source. Braun et al.'s connectome-based "predictions" are counts of DN–DN connections, not simulation scores. saw_simulation_score = false for every record, and there is no sightings.csv.
