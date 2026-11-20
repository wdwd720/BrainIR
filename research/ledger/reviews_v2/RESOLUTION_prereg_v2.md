# Resolution of the PREREG v2 review (`REVIEW_prereg_v2.md`), before the freeze

| finding | resolution (where) |
|---|---|
| B1 G3 item 4' decided by seen data; Bonferroni loosens | Item 4' computed before the freeze from the stored run-1 G3 runs (sha256 named) and the authors' traces (sha256 named); table printed in P2. Governing rule = every evaluable pair p >= 0.01 (v1 4.7's alpha, no correction): **fails** (T1R-T2R p 0.0035). Bonferroni (passes) and status-match (fails) variants printed. B3 marked "gate chosen with inputs known". |
| B2 L3 vs frozen audit; family names | L3 restates all five breach kinds (incl. dedicated-source fetch, no transcript, URL tokens) and the audit-timing rule; family mapping `dedicated` -> `pugliese_dedicated` for the frozen audit; v2 dedupe order stated in L8. |
| B3 leak surface | v1 predictions' public status stated (change table); predictions v2 pushed only after labels v2 lock (P5); mirrors and tokens added to L3/L13; web tools only for search and `reader_web` sessions (C1, L13; launcher); reader family scopes neutral (kit); orchestrator and run-1 project folders and temp folders denied; second canary (`gates_v2/CANARY_v2b.json`): other sessions' project folders, the orchestrator's folder and the mirrors are blocked for reader and search flags. Tool-result text naming the repository, its owner or `smpuglie` is a breach (L3 kind 5). |
| B4 atlas path | UNMAPPED sentinel (C4); key, duplicates, Phase B by coder B, mapping confidence from the map, `other_cell_types` and C4 precedence over L10, single-reading map declared, `atlas_line_ids.csv` from the kit's Cande rows (L7, L8). |
| B5 gate 3-4 decidable after data | Verification frame and draw fixed; verifier blind to the recorded value; script comparison; dedicated records outside the frame (L11). Kappa defined as the frozen `agreement()["primary_field_all_values"]` on named inputs (S5.4). Identifiers neutralised with a fixed word list (L8). Each step once; a failed gate ends collection; no pooling (L1, L14). |
| M1 L10 fill | Literal: only `other_cells` decides (`multi_dn` if it names a DN type, else `minor_offtarget`); never `clean` by script; candidate-type ambiguity ignored; consensus after the fill. |
| M2 L9 recall | Leads carry `manc_type` (kit `PROMPT_SEARCH.md`); DOI normalisation named (v1.1 fix); breaching search leads dropped (L3). |
| M3 exclusion details | L3 consequences and L5 partial records stated; gate 2 covers every contributing session (S5.2). |
| M4 exposed by nature | Mechanism: `exposed_v2.csv` (L6), used by every v2 run (S4, S5.5). |
| M5 post-freeze code | All label code, the gate script and scoring v2 locked before the first v2 label session with `IMPLEMENTATION_v2.md`, checked by a fresh reviewer; bug-fix definition (L12). |
| M6 oversized outputs in tool-results | L3 kind 1 exception covers files whose path appears in the session's own earlier tool results (any tool). |
| M7 S4 flags; B3/B6 analyses | Flags per run (S4); B3 statistic defined; B6 not analysed in run 2 (S3). |
| M8 P1/P3 | P1 fallback and unusable seeds defined; positive control called tautological, DNb08 reported (P1). P3: in bounds = verdict not `strong`; `halts` needs every rhythm-losing run in bounds; `saturates` = more than half out of bounds; data = `results.pkl` by hash, checked against locked digests. |
| M9 disclosure | Disclosure lists the per-type B4/B2 split files, the pre-freeze item 4' computation and the trust gate; changelog has one row per change. |
| minor | v1 -> v2 change table; kit wording (sources_seed, C1 vs section 8, verify fields, sighting rule in verify, `assigned_sources.csv` columns in L5); gate 1 lists every lock and uses `lock2.py check` (existence + chained hashes). |
