# Notes: session pass1-walking_stopping-r1-01 (pass1)

I used only local copies in `sources/`. I did no web access and searched for nothing.

## 10.1038/s41586-025-09554-2 (Dallmann et al. 2025, Nature)
- Read: the full text.txt (PMC author-manuscript XML: main text, Methods, all main and Extended Data figure legends). No figure
  images, supplementary tables, Supplementary Discussion or videos were downloaded (meta.json: 0 figures, 0 supp files).
- DN activation: DNg100 (CsChrimson, 625 nm LED, about 4 s) in **fully restrained** females with all legs glued except one
  front leg. The magnet moved that front leg passively while hook-flexion axons were imaged (Ext. Data Fig. 10, Methods).
  This was not a behavioural readout and no leg movement could be seen, so it is not a record.
- Other activation: CsChrimson in 9A interneurons (not DNs) on the ball. Not a record.
- The paper runs a connectome-constrained LIF model (Shiu et al. 2024) of chief 9A recruitment by DNg100, DNg12 and DNg74 (Fig. 5i).
  This is the paper's own model and gives no rhythm score, rank or driver call, so it is **not a sighting** under section 8. Nothing
  from it was used.
- Disposition: no_qualifying_experiment.

## 10.1073/pnas.2426180122 (Iwasaki et al. 2025, PNAS)
- Read: text.txt, article text, Fig. 8 image, and the SI Appendix text (methods, Tables S1-S3).
- One possible record: Fig. 8F-J formation control. CsChrimson in "foxglove halting neurons" (genotype in Table S1:
  `w; UAS-CsChrimson/VT022244-p65ADZp(attp40); VT019012-ZpGDBD(attp2)/+`, BDSC 87367), red laser switched on when a
  freely walking fly reached its goal, which stops it.
- **Uncertainty:** neither the paper nor the kit establishes that foxglove is a descending neuron. type_list.csv and
  synonyms.csv have no "foxglove". driver_lines.csv row SS40909 (foxglove, VT019012-AD;VT022244-DBD, i.e. the same
  hemidrivers swapped AD/DBD) is UNMAPPED with the comment "the table does not state whether this named neuron is a
  descending neuron". I wrote the record as `UNMAPPED`, mapping `low`, labeler confidence `low`, so adjudication can
  keep it or drop it. I proposed no mapping because I have no source-based MANC type. Possible follow-up: check whether
  BDSC 87367 is the same as SS40909 and whether the line labels a DN.
- The stop is read only from centroid tracking used as a tool (flies staying in goal regions). There was no per-fly
  quantification and no control.
- Orco-Gal4 activation (olfactory turning) and the MBON screen (MB052B, MB077B, MB112C, MB083C, MB080C) do not target DNs and are not records.

## Sightings
None. I saw no Pugliese-type rhythm score, rank or driver call. I did not open the Pugliese or Sapkal 2026 papers.
