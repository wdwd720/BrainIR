# Hemilineage activation-outcome locations in the repository (PREREG v3 Part D, item 2)

Made by a fresh agent (run 3, Stage 1, 2026-11-21) that searched the working tree of `ledger/v1`, including the git-ignored
`data/ledger/`, and reported **locations, hemilineage names and a category only, never an outcome**. The orchestrator did not open
any of these locations. Copied from the agent's report; two lines naming harness-internal scratch files (absolute paths) are
omitted.

Format: `path: lines; hemilineage(s); category`. Categories: A = activation outcome stated; S = silencing outcome stated;
G = general claim about hemilineage function; U = unclear. A downloaded-paper entry also covers every other text copy of that
paper in its folder and in `.raw/<slug>/`.

## Repository notes
1. research/ledger/labels_v2/raw/pass1/pass1-grooming-r0-02/notes.md: 12-16, 24-27; 13A, 13B; U
2. research/ledger/labels_v2/raw/pass1/pass1-grooming-r0-02/dispositions.csv: 2; 13A, 13B; U
3. research/ledger/labels_v2/raw/pass1/pass1-grooming-r0-02/sources.csv: 2; 13A, 13B; G
4. research/ledger/labels/raw/pass1/pass1-grooming/sources.csv: 7; 13A, 13B; G
5. research/ledger/labels_v1_1/sources.csv: 62; 13A, 13B; G
6. research/ledger/labels/raw/pass1/pass1-recent_broad/notes.md: 31-32; 13A, 13B; G
7. research/ledger/labels_v2/raw/search/search-bycitation-r2/notes.md: 58; 13A, 13B; G
8. research/ledger/labels_v2/raw/search/search-bybehaviour-r2/notes.md: 87; 13A, 13B; G
9. research/ledger/labels/raw/pass1/pass1-grooming/notes.md: 37; 13A, 13B; U
10. research/ledger/labels_v2/raw/search/search-bydriverline-r2/notes.md: 37; 13A, 13B; U
11. research/ledger/labels_v2/raw/search/search-bytypename-r2/notes.md: 64; 13A, 13B; U
12. research/ledger/labels_v2/raw/pass1/pass1-walking_stopping-r1-01/notes.md: 11; 9A; U
13. research/ledger/labels_v2/raw/pass1/pass1-walking_stopping-r1-01/dispositions.csv: 2; 9A; U
14. research/ledger/labels_v2/raw/pass1/pass1-grooming-r0-01/dispositions.csv: 2; 12B; U
15. research/literature/pugliese_walking_cpg_detailed_notes.md: 798; 19A, 19B; G

## Downloaded papers (git-ignored, from exam 1's label collection)
16. data/ledger/sources_v2/10_7554_elife_106446/text.txt: 10-300; 13A, 13B (also 3B, 0A at 44); A, S
17. data/ledger/sources_v2/10_1038_s41586_025_09554_2/text.txt: 72, 80-108, 267-268; 9A; S, G, U
18. data/ledger/sources_v2/10_7554_elife_108044/text.txt: 10-287; 23b (LB23); A, G
19. data/ledger/sources_v2/10_1038_s41586_024_07523_9/supp/41586_2024_7523_MOESM3_ESM.txt: 882-885; 12A; A
20. data/ledger/sources_v2/10_1101_2025_10_28_684868/text.txt: 56; none named (cites Harris 2015); A
21. data/ledger/sources_v2/10_1101_2025_09_12_675944/text.txt: 106; 13A, 13B; G
22. data/ledger/sources_v2/10_1038_s41586_025_08925_z/text.txt: 10, 142-146, 154; 08B; G
23. data/ledger/sources_v2/10_64898_2026_04_29_721658/text.txt: 154-164, 188-196; 19A, 19B; G
24. data/ledger/sources_v2/10_64898_2026_01_04_697356/text.txt: 52; 17A, 16B, 9A; U
25. data/ledger/sources_v2/10_64898_2026_01_04_697356/supp/697356_file19__Sheet1.csv: 175-198; 17A, 16B, 9A; U
26. data/ledger/sources_v2/10_1016_j_cub_2024_04_003/text.txt: 66-68; 12B; U
27. data/ledger/sources_v2/10_1016_j_isci_2026_114902/text.txt: 141-143; 5B, 10B; U
28. data/ledger/sources_v2/10_1038_s41467_020_19936_x/text.txt: 80; 14B; U
29. data/ledger/sources_v2/10_1101_2025_07_22_666129/text.txt: 88, 92; 8B/10B; U

## How the agent searched
- Scope: the whole working tree, including ignored `data/ledger/`; skipped `data/raw`, `data/processed`, `data/cache`, `.venv`,
  caches and binaries (PDF, images, xlsx, docx, zip). Not searched: the label rooms outside the repository, which may hold copies
  of these papers.
- Patterns: `hemi[- ]?lineage`; name tokens `(0?[0-9]|1[0-9]|2[0-7]) ?[ABX]` (figure references excluded); `20A.22A`- and
  `8B/10B`-style forms; `lineage N`; `NB\d-\d`; tokens within 200 characters of activation or silencing terms or behaviour terms;
  author names (Harris, Soffers, Shepherd, Truman, Lacin, Cheong, Marin, Syed, "ground plan") and numbered citations of Harris 2015.
- Every hit read in context; connectivity, transmitter, annotation, simulation-only and figure hits excluded.
- Total: 29 locations (15 repository notes, 14 downloaded-paper files), duplicates not counted.

## What the orchestrator knows from this list
Only which hemilineage names occur near activation, silencing or function statements, and in which files; no outcome. None of
these files is used to make predictions; the exam-2 label sessions find and read sources themselves (PREREG v3 T1, T6).
