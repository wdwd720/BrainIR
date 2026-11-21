# Notes: pass1-escape_landing-r0-04 (pass1)

## Assigned source
- 10.3791/50192: de Vries & Clandinin 2013, JoVE, "Optogenetic stimulation of escape behavior in Drosophila melanogaster."

## What I did
- Read the local `sources/10_3791_50192/text.txt`, which has the abstract only (Europe PMC full text gave HTTP 500).
- As my instructions allow, I fetched the article page on PubMed Central (https://pmc.ncbi.nlm.nih.gov/articles/PMC3582644/) for
  this DOI. The text was reachable. The fetch tool returned a summary with short quotes, not a verbatim dump. I did not search
  for any other paper.

## Finding
- The only activation experiment uses ChR2 in Foma-1 neurons. These are loom-sensitive optic-lobe neurons driven by
  G105-Gal4, which the article says is also expressed in the mushroom body gamma lobe. The flies are norpA blind females
  stimulated with 470 nm LEDs. They take off: >50% within 1 s and 75% within 5 s; controls ~10% and 20%.
- Controls are 201Y-Gal4 (mushroom body gamma lobe) and the parental lines.
- No descending neuron or DN-labelling driver line is activated. The giant fiber appears only as earlier work and as a
  point of comparison for how stable the takeoff is.
- Disposition: `no_qualifying_experiment`, 0 records.

## Uncertainty
- Foma-1 neurons are optic-lobe neurons as the paper describes them. I did not judge them to be DNs, and the paper names no DN.
  If a later pass sees the full figure legends verbatim, it could confirm that no other line was tested. The summary I got
  lists only G105, 201Y and the parental controls.

## Simulation / score sightings
- None seen. No sightings.csv written.
