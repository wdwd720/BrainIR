# Notes: pass2-dedicated-web-01 (pass2), phase 1

## Sources and access
- Assigned source: Pugliese et al. 2026, Nature, 10.1038/s41586-026-11195-y. The local copy (`sources/.../text.txt`) is the abstract only, with no figures or supplements.
- Web attempts:
  - nature.com redirects to the idp.nature.com login page. I did not follow it.
  - Europe PMC REST returned HTTP 500 and 504.
  - bioRxiv `.full` pages returned HTTP 429 many times.
  - The bioRxiv API (api.biorxiv.org/details) gave me the JATS XML URLs. After several 429 retries, the v2 XML (`biorxiv.org/content/early/2026/04/30/2025.09.12.675944.source.xml`) was read in three chunks through WebFetch (offsets 0, 100000 and 300000), plus one targeted chunk at offset 0 to check exact wording. The 200000 chunk contained only references and computational methods, and only a contents summary was returned for it.
  - I also made one malformed Europe PMC URL request (`europepmc.org/api/fulltextRepo?pprId=PPR...`) by mistake. It contained no personal data and failed.
- Not seen: figure images, Supplementary Videos and the genotype table (Table 1 is an image). Because of this:
  - the DNg100 driver line is not named in the text, so `driver_lines` is `[]`;
  - the DNb08 laser intensity is not stated;
  - I could not tell whether DNb08 trials in Fig. 5 were on the ball or with the ball removed.
- WebFetch returns text through a summarizing model. The quotes are the sentences it returned as verbatim, but they were checked differently:
  - The DNb08 quote (Results) came back with the same wording in two separate requests.
  - The DNg100 quote (Supplementary Video 1 legend) was returned only once, from the offset-300000 chunk, and was not re-checked.

  Both should be verified against the PDF.

## Records
- 0001, DNg100: headless, on ball, walking. Forward velocity and stepping frequency rose with intensity. n=7, female. I applied the walking convention, so all three leg pairs are `yes`. Confidence is medium because only the front left leg was tracked and I did not view the figures.
- 0002, DNb08 (SS70620): headless. Rhythmic, searching-like oscillation of the front and middle legs. n=10, female. Hind legs `not_assessed` because they are not reported. Category `other`, since this is not walking.
- No experiment was missing, so `not_found.csv` contains only its header.

## Simulation sightings (see sightings.csv)
- The abstract (local copy, and the first thing read) calls DNg100 the "strongest driver" of rhythmic leg motor activity in the computational activation screen. I logged this as both a rank and a driver call. It also says simulations "predicted" that DNb08 drives rhythmic leg movements, which is a driver call. `saw_simulation_score` = true on both records.
- The fetch summary also said the DNg100 experiment "confirmed predictions from our connectome simulations" and mentioned a ~14 Hz oscillation frequency of the simulated circuit. Neither is a score, rank or driver call, and neither was used for labeling.
- No simulation result was used for any label. The labels rest only on the experimental Results text, legends and Methods.
