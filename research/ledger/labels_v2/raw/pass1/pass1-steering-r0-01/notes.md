# Notes: session pass1-steering-r0-01 (pass1, source family: steering and turning)

## Scope and method
- Read PROTOCOL.md (v2, including section 8), record_schema.json and the kit mapping files.
- Worked only from the six local copies in `sources/` listed in `assigned_sources.csv`. No web access, no other sources.
  For each source I read the text (results, figure legends, methods), the relevant figure images and the
  supplementary tables/genotype files.
- No model, simulation, connectome-activation score, rank or driver call (Pugliese-type) was seen. Two sources run
  their own connectome analyses (Feng et al.: synaptic hierarchy; Dallmann et al.: "net excitation" onto DNs), and
  Dahlhoff et al. fit their own LN models to recordings. Per section 8, a paper's own model doesn't count as a
  sighting. I didn't use any of it for coding. `saw_simulation_score` is false everywhere, and there is no `sightings.csv`.

## Per-source decisions
- **10.1016/j.cell.2024.08.033 (Yang et al., Cell 2024)**: 3 records: DNa02 unilateral SPARC-CsChrimson (turn), DNa02 bilateral
  (slowing, n=3), and the DNg13-line (SS02259) SPARC note that light stopped locomotion. The authors attribute the
  stop to an off-target ascending neuron, not to DNg13. I recorded it with low confidence and explanatory notes so
  adjudication can decide whether to keep it. DNg13 current injection is not opto/thermo activation, so it is not
  a record. All analysed DNa02 trials required the fly to be walking already, so leg-rhythm fields are `not_assessed`.
- **10.1101/2023.10.15.562426**: bioRxiv preprint of the Cell paper. It has its own DOI, so I wrote parallel records
  (0006-0008). Each one's notes say it duplicates the Cell experiment, and adjudication may deduplicate them.
- **10.1101/2020.04.04.024703 (Rayshubskiy et al.)**: DNa02 stochastic ReaChR. The unilateral group shows an ipsiversive bias.
  For the bilateral group, the text only says forward-velocity changes were indistinguishable from no-expression
  flies (startle confound, "data not shown"). I coded it `no_visible_effect` with low confidence. n for the
  unilateral group is ambiguous (legend "16/17 flies (uni/bilateral)" vs Methods 9+8 unilateral brains), so
  n_flies is null with a note.
- **10.1101/2024.06.27.601106 (Feng et al.)**: 9 records. The DNa11 Fig. 2c (angular velocity) and Fig. 6 (leg kinematics)
  results are separate records because they are separate figures. Stepping frequency (~3 Hz) was read from the
  Fig. 6f/6g plots, so it is approximate. The DNa11 headless record rests on the Supplementary Video 6 legend
  (8/8 flies). I couldn't watch the video, so leg fields are `unclear`. DNa03-SS2 (SS84990) appears only in
  Fig. S3 distributions, so its quote is the general Results sentence covering Fig. 2c and Fig. S3.
  **Not recorded:** the bilateral-expression groups in Fig. 2c (DNa11 n=3, DNa03 n=11, DNae003 n=5, DNa02 n=10)
  and Fig. S14e (DNa06 n=10), because no sentence in the text describes them and their signed angular velocity
  is uninterpretable when turn direction is random. Fig. S3 suggests broadened turning for bilateral DNa11. Also
  not recorded: DNa03 tethered-flight turning (no leg readout), GtACR silencing/epistasis, and the LAL013 and ExR7
  activations (not DNs). The VT002063 "optogenetic screen for locomotion phenotypes" is mentioned but its lines
  are not reported, so it is not a codable screen.
- **10.1101/2025.07.22.666129 (Dahlhoff et al.)**: SS02553 labels DNp17 plus 7 non-DN types, and SPARC shows the
  phenotype is due to DopaMeander (a non-DN dopaminergic neuron). The DNp17 records are marked `minor_offtarget`,
  the only enum value for non-DN off-target cells, but the notes stress that the off-target cells drive the
  phenotype. The authors say they also tested other "DNp lines" from Cande et al. that increased walking speed,
  but they name neither the lines nor the types, so no records are possible. MDN data in this paper are silencing
  and recordings only.
- **10.64898/2026.01.04.697356 (Dallmann et al.)**: This is not the Sapkal 2026 preprint (different DOI). RRN is a central-brain pair
  without VNC expression, so its activations (free, tethered, SPARC, chemogenetic) are not DN records. The only DN
  record is MDN>CsChrimson in the gap-crossing assay. The paper gives that line only as the hemidriver genotype
  VT050660-AD;VT044845-DBD, which matches kit line MDN-1.

## Mapping notes
- "DNp17" maps in the kit to DNp17 and DNut046 (ambiguous). I chose DNp17 at medium confidence: it is the identical
  MANC type name, and the paper describes ipsilateral descent to lower tectulum, haltere and neck neuropils.
- "DNae003" maps via synonyms.csv only to DNxn123, so mapping confidence is high.
- New line-to-type pairings are proposed in `proposed_driver_lines.csv` (SS77821 DNa11; SS94676 DNxn123/DNae003;
  SS96514 and SS84990 DNa03; R54E05-AD;VT025718-DBD DNa06). No new name synonyms were needed.

## Uncertainties / could not access
- Supplementary videos weren't available locally (DNa11 headless, gap-crossing, etc.), so those outcomes rest on
  the legends and text.
- Feng et al. don't state sex explicitly for the SPARC experiments. The Methods say "In most of the experiments, only
  females were used" and list exceptions, and the SPARC experiments are not among them, so I coded female.
