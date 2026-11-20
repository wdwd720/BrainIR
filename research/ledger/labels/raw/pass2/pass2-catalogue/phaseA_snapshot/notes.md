# pass2-catalogue: notes (phase 1)

Session `pass2-catalogue`, pass `pass2`. 15 experiment rows given, 15 records written (`p2-catalogue-0001` to `0015`).
`not_found.csv` has only its header: every experiment was located. No simulation scores or model predictions were seen
(`saw_simulation_score` = false everywhere). I did not visit GitHub, Zenodo or the excluded papers.

## Access
- **Zacarias et al. 2018 (Nat Commun)**: nature.com sits behind a cookie/IdP redirect, so I read the full text via Europe PMC (PMC6135764).
- **Dombrovski et al. 2023 (Nature)**: full text read via Europe PMC (PMC9849133). Supplementary Table 1 (n, P values) and
  Supplementary Table 2 (genotypes / split-GAL4 IDs) were not read, so `driver_lines` = [] and `n_flies` = null.
- **Lillvis et al. 2023 (bioRxiv)**: v1 and v2 full text read, despite heavy HTTP 429 rate limiting. Supplementary figure
  legends (Sup. Fig. 6, 7) and the genotype table were not read.
- **Sen et al. 2017 (Curr Biol)** and **Kohatsu et al. 2011 (Neuron)**: cell.com and ScienceDirect returned 403 and there is
  no PMC copy. Both are labelled from the abstract only, with `access` = `abstract_only` and confidence low.

## Uncertainties
- **0001 DNp09 (Zacarias)**:
  - Mapping: the kit marks the name DNp09 and SS01540 as ambiguous between DNp09 and DNp71. I mapped it to MANC DNp09 at medium confidence, because the paper uses Namiki 2018 naming.
  - Legs: I coded them `no` / halting under the stopping convention. However, the paper reports an initial DNp09-induced running bout before freezing and jumps at light offset. Whether this running is new stepping from standstill is not established, so the leg coding could arguably be `unclear`. It deserves adjudication.
- **0002 MDN (Sen)**:
  - Abstract only. The quote names "unilateral activation experiments that support these hypotheses"; the hypothesis (asymmetric MDN activation leads to turning while walking backward) is in the preceding sentence.
  - The effector is not in the abstract. `optogenetic` was inferred from a search-result summary of the paper's highlights, which I could not open.
  - Preparation kept as `other`, as given.
- **0011 P2b (Kohatsu)**: P2b is ambiguous in the kit (pIP10 vs DNxl053), and the abstract gives no anatomy to decide between them, so the record is `UNMAPPED`. The outcome ("initiation of courtship") does not describe the legs, so legs are `not_assessed`.
- **0012 pIP10 (Lillvis)**: the given locator says "Fig. 4D-E, H-I". In both preprint versions the Fig. 4 legend ends at E, and panels H-J (in Fig. 8) show pIP10+vPR9-SS1, a different genotype. I used Fig. 4D-E.
- **Lillvis records (0012-0015)**: song only, legs not described, so the leg fields are `not_assessed` and the category is `wing_or_flight`.
- **0003-0010 (Dombrovski)**: takeoff and postural lean are single movements, so legs are `no`. Expression was assumed bilateral, and specificity for the single lines is unknown. The DNp06 record comes only from the triple combination line, and the paper attributes the backward leaning to DNp02.
- No proposed synonyms or driver lines were added.
