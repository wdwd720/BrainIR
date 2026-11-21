# Notes: session pass1-grooming-r0-02 (pass1)

## What was done
- Read PROTOCOL.md (v2, including section 8) in full before starting.
- Read the local copies of all 6 assigned sources (`sources/<slug>/text.txt`, plus `supp/article.txt` where useful). I checked the
  figure legends, Methods and key-resources tables for every driver line used, and searched each text for
  descending, aDN, DNg/DNp/DNa, command, CsChrimson, TrpA1 and GAL4/LexA.
- No web access was used. No other files outside the room were opened.

## Outcome
No records were written, so `out/records.jsonl` is empty. All six sources are `no_qualifying_experiment`:
- **10.7554/elife.106446** (Syed, Ravbar, Simpson 2026): activation experiments target 13A/13B VNC inhibitory
  interneurons only. DNg12 and aDN appear only in the Discussion, as connectome synapse counts onto 13A neurons.
  One split line (R35G04-DBD and GAD1-AD) has "ectopic expression ... in a few neurons in the brain". These neurons are
  not identified as DNs, and the authors show the phenotype persists in decapitated flies, so the line is not treated as
  a DN-labelling line. The paper includes its own neuromechanical model and genetic-algorithm fit. This is not a
  Pugliese-type score and I did not use it.
- **10.7554/elife.108044** (head BMN connectome): connectomic analysis only, with no new behavioural activation data.
- **10.7554/elife.28804** (Hampel 2017), **10.7554/elife.59976** (Hampel 2020), **10.7554/elife.71508** (Ravbar 2021),
  **10.7554/elife.87602** (Eichler 2024): every activation targets sensory neurons (bristle mechanosensory neurons,
  JONs, wing/haltere sensilla) or uses broad sensory GAL4 lines. None of these lines is described as labelling DNs.
  Eichler 2024 explicitly states its BMN lines label no other brain or VNC regions.

## Uncertainties
- Two lines label some cells the papers do not identify: the 13A/13B split line with a few brain neurons (106446) and
  the arrowed "non-JON" cells in JO-F-2 (59976). Neither paper identifies these cells as DNs. If a later pass identifies
  them as DNs, the line could be revisited, but the papers' own interpretation attributes the behaviour to the target
  neurons.
- Videos were not downloaded (per meta.json), but they were not needed because no DN experiment exists.

## Sightings
None. No Pugliese-type rhythm score, rank or driver call was seen, so there is no `sightings.csv`.
No proposed synonyms or driver lines.
