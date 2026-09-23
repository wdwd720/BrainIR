# MANC provenance and release notes (verified against primary sources)

Purpose: every provenance fact BrainIR relies on for the MANC (Drosophila Male Adult Nerve Cord) connectome,
versions v1.0 (2023), v1.2 / v1.2.1 (2024) and v1.2.3 (2025), checked against primary sources.
Written 2026-09-22/23. Unless marked otherwise, every URL below was retrieved on 2026-09-22; items marked
`[2026-09-23]` were retrieved on 2026-09-23.

Conventions
- **VERIFIED**: read directly from the cited source; quotations are verbatim (typos in the source preserved).
- **COMPUTED**: derived by us from public primary data (method stated); not a statement made by the data providers.
- **UNVERIFIED**: could not be confirmed from a primary source; what was tried is stated.
- No credentials were used. Everything here was reached anonymously. Where a resource requires a login
  (neuPrint Explorer / most neuPrint API routes) this is stated and nothing further was attempted.
- Local files under `data/raw/manc/v1.0/...` were read only to count things; they are byte-identical copies of the
  bucket objects named below (their GCS `md5Hash`/`generation` are listed in section 3.6).

---------------------------------------------------------------------------------------------------------------------

## 1. Citations (all DOIs resolved through the Crossref REST API, `https://api.crossref.org/works/<doi>`)

### 1.1 Takemura et al. — reconstruction paper — VERIFIED
- Title: **A Connectome of the Male Drosophila Ventral Nerve Cord**
- Authors (84): Shin-ya Takemura, Kenneth J Hayworth, Gary B Huang, Michal Januszewski, Zhiyuan Lu, Elizabeth C Marin,
  Stephan Preibisch, C Shan Xu, … , Gerald M Rubin, Louis K Scheffer, Jan Funke, Stephan Saalfeld, Harald F Hess,
  Stephen M Plaza, Gwyneth M Card, Gregory SXE Jefferis, Stuart Berg.
- eLife **Reviewed Preprint v1, 23 May 2024**. DOI of that version: `10.7554/eLife.97769.1`; the version-independent
  DOI `10.7554/eLife.97769` resolves to it (Crossref record type `posted-content`, `is-same-as` 10.7554/eLife.97769.1;
  `is-version-of` bioRxiv 10.1101/2023.06.05.543757).
- **No Version of Record exists** (Crossref has no `journal-article` record; `https://elifesciences.org/articles/97769`
  returns HTTP 404; the reviewed-preprint page says "Reviewed Preprint v1 May 23, 2024 Not revised").
- eLife page (https://elifesciences.org/reviewed-preprints/97769): "You can cite all versions using the DOI
  https://doi.org/10.7554/eLife.97769. This DOI represents all versions, and will always resolve to the latest one."
  License on page: "This article is distributed under the terms of the Creative Commons Attribution License, which
  permits unrestricted use and redistribution provided that the original author and source are credited."
- Suggested citation: Takemura S, Hayworth KJ, Huang GB, et al. (2024) A Connectome of the Male Drosophila Ventral
  Nerve Cord. eLife 13:RP97769 (Reviewed Preprint v1). https://doi.org/10.7554/eLife.97769
  (the "13:RP97769" volume/eLocator form is eLife's convention for reviewed preprints of 2024; Crossref itself lists
  no volume for this posted-content record — so cite the DOI, not the volume, when in doubt).

### 1.2 Marin et al. — systematic annotation paper — VERIFIED
- Title: **Systematic annotation of a complete adult male Drosophila nerve cord connectome reveals principles of
  functional organisation**
- Authors (23): Elizabeth C Marin, Billy J Morris, Tomke Stürner, Andrew S Champion, Dominik Krzeminski,
  Griffin Badalamente, Marina Gkantia, Christopher R Dunne, Katharina Eichler, Shin-ya Takemura, Imaan FM Tamimi,
  Siqi Fang, Sung Soo Moon, Han SJ Cheong, Feng Li, Philipp Schlegel, Sebastian E Ahnert, Stuart Berg,
  Janelia FlyEM Project Team, Gwyneth M Card, Marta Costa, David Shepherd, Gregory SXE Jefferis.
- eLife **Reviewed Preprint v1, 22 July 2024**; DOI `10.7554/eLife.97766.1`; version-independent DOI
  `10.7554/eLife.97766` (Crossref `posted-content`, `is-version-of` bioRxiv 10.1101/2023.06.05.543407).
- **No Version of Record** (Crossref has none; `https://elifesciences.org/articles/97766` is HTTP 404; page says
  "Reviewed Preprint v1 July 22, 2024 Not revised"). Same CC BY sentence as above on
  https://elifesciences.org/reviewed-preprints/97766.

### 1.3 Cheong et al. — descending/premotor organisation paper — VERIFIED (VOR exists; title changed across versions)
- Version of Record title: **Organization of circuits linking descending input to motor output in the Drosophila
  Male Adult Nerve Cord connectome**
- Authors (16): Han SJ Cheong, Katharina Eichler, Tomke Stürner, Samuel K Asinof, Andrew S Champion,
  Elizabeth C Marin, Tess B Oram, Marissa Sumathipala, Lalanti Venkatasubramanian, Shigehiro Namiki, Igor Siwanowicz,
  Marta Costa, Stuart Berg, Janelia FlyEM Project Team, Gregory SXE Jefferis, Gwyneth M Card.
- **eLife 13:RP96084, Version of Record published 20 July 2026**, DOI `10.7554/eLife.96084` (Crossref
  `journal-article`, volume 13, article-number RP96084, `is-same-as` 10.7554/eLife.96084.3, CC BY 4.0 `vor` license).
  https://elifesciences.org/articles/96084 lists: "Reviewed Preprint version 1: March 18, 2024 / Reviewed Preprint
  version 2: July 21, 2025 / Version of Record published: July 20, 2026".
- Earlier versions had different titles (Crossref):
  - v1 (`10.7554/eLife.96084.1`, 2024-03-18): "Transforming descending input into behavior: The organization of
    premotor circuits in the Drosophila Male Adult Nerve Cord connectome" (this is the title still shown on the Janelia
    MANC page).
  - v2 (`10.7554/eLife.96084.2`, 2025-07-21): "Transforming descending input into motor output: An analysis of the
    Drosophila Male Adult Nerve Cord connectome".
  - bioRxiv preprint: 10.1101/2023.06.07.543976.
- Cheong VOR data statement (https://elifesciences.org/articles/96084, Materials and methods): "Connectome data was
  queried from MANC v1.2.3 (here) via the neuPrint API using the neuprintr package"; the "here" link is
  `https://neuprint.janelia.org/?dataset=manc%3Av1.2.3&qt=findneurons`. Data availability: "The MANC connectome,
  including annotations of DNs and MNs described in this work, are publically available at https://neuprint.janelia.org."

### 1.4 neuPrint paper — VERIFIED
- Plaza SM, Clements J, Dolafi T, Umayam L, Neubarth NN, Scheffer LK, Berg S (2022). **neuPrint: An open access tool
  for EM connectomics.** Frontiers in Neuroinformatics 16:896292, published 2022-07-20.
  DOI `10.3389/fninf.2022.896292` (Crossref; CC BY 4.0). Page read: https://www.frontiersin.org/articles/10.3389/fninf.2022.896292/full

### 1.5 Neurotransmitter-prediction and nomenclature papers cited below — VERIFIED
- Eckstein N, Bates AS, Champion A, Du M, et al. (2024). Neurotransmitter classification from electron microscopy images
  at synaptic sites in Drosophila melanogaster. **Cell 187(10):2574–2594.e23** (May 2024).
  DOI `10.1016/j.cell.2024.03.016` (Crossref; `has-preprint` 10.1101/2020.06.12.148775). Open-access text read at
  https://pmc.ncbi.nlm.nih.gov/articles/PMC11106717/ ("This is an open access article under the CC BY license").
  The MANC papers cite the 2023 bioRxiv version as "Eckstein et al., 2023".
- Court R, Namiki S, Armstrong JD, et al. (2020). A Systematic Nomenclature for the Drosophila Ventral Nerve Cord.
  **Neuron 107(6):1071–1079.e2** (Sept 2020), DOI `10.1016/j.neuron.2020.08.005` (Crossref) [2026-09-23]. Text read
  from the bioRxiv version https://www.biorxiv.org/content/10.1101/122952v2.full.

### 1.6 How neuPrint itself cites the papers (public dataset descriptions, section 8) — VERIFIED
`https://neuprint.janelia.org/api/dbmeta/datasets` returns, for manc:v1.0, manc:v1.2.1 and manc:v1.2.3, the identical
description text: "The MANC connectome from the Janelia FlyEM Team Project and the Cambridge Drosophila Connectomics
Group, and Google Connectomics.\nThe male adult Drosophila nerve cord; 23k neurons." with citations
"[Takemura et al. (2024)](https://doi.org/10.7554/eLife.97769.1)", "[Marin et al. (2024)](https://doi.org/10.7554/eLife.97766.1)",
"[Cheong et al. (2025)](https://doi.org/10.7554/eLife.96084.2)".

Consequence for `src/brainir/sources/registry.py`: the three eLife DOIs it carries "from memory" are correct; the
Cheong entry should be updated to the VOR (2026, eLife 13:RP96084) and the note "verify against the landing page" can
be resolved.

---------------------------------------------------------------------------------------------------------------------

## 2. License — VERIFIED (visible text says "CC-BY"; the link target is the CC BY 4.0 deed)

- Janelia MANC release page https://www.janelia.org/project-team/flyem/manc-connectome, exact sentence:
  **"The MANC is licensed under CC-BY ."** (the words "CC-BY" are a hyperlink whose `href` is
  `https://creativecommons.org/licenses/by/4.0/`). The page carries no other license text.
  Wayback Machine copies of the page from 2024-04-13, 2024-07-13, 2025-01-22 and 2025-09-11
  (`http://web.archive.org/web/<timestamp>id_/https://www.janelia.org/project-team/flyem/manc-connectome`) contain the
  identical sentence, so the license statement has been stable since at least April 2024.
- neuPrint dataset descriptions (public API, section 8) contain **no license statement**.
- Neither `gs://flyem-manc-exports/` nor `gs://flyem-manc-exports/v1.0/` has a README/LICENSE object
  (`https://storage.googleapis.com/flyem-manc-exports/README`, `.../v1.0/README`, `.../v1.0/README.md`,
  `.../v1.0/README.txt` all return `NoSuchKey`). The two READMEs that exist (section 3.2) say nothing about licensing.
- The three eLife papers are CC BY (eLife statement quoted in 1.1; Crossref license URL
  `https://creativecommons.org/licenses/by/4.0/` on all three records).
- Recommended registry wording: `The MANC is licensed under CC-BY.` (Janelia FlyEM MANC page, link to CC BY 4.0),
  rather than the current paraphrase "released under CC BY 4.0 (Janelia FlyEM MANC release page / neuPrint)", since
  neuPrint does not state it.

---------------------------------------------------------------------------------------------------------------------

## 3. Release history

### 3.1 Official statements — VERIFIED
- Janelia page "News" block (only two lines, verbatim): **"2023-06-06: MANC v1.0 released"** and
  **"2024-03-11: MANC v1.2 released"**. Wayback copies show the v1.2 line was added between 2024-07-13 (absent) and
  2025-01-22 (present); the 2024-04-13 and 2024-07-13 copies list only v1.0 and link only `?dataset=manc:v1.0`.
  The 2025-01-22 and 2025-09-11 copies link `?dataset=manc:v1.2.1` and the neuroglancer state
  `gs://manc-seg-v1p2/manc-v1.2.1-neuprint-layers.json`. The live page (2026-09-22) links
  `https://neuprint.janelia.org/?dataset=manc:v1.2.1&qt=findneurons` (neuPrint, "Explore the dataset using neuPrint")
  and `https://neuroglancer-demo.appspot.com/#!gs://manc-seg-v1p2/manc-v1.2.3-neuprint-layers.json` (neuroglancer),
  i.e. the page still points neuPrint users at v1.2.1 while pointing neuroglancer users at v1.2.3.
  Other page text: "With about 23,000 neurons, 10 million pre-synaptic sites, and 74 million post-synaptic densities,
  the male adult nerve cord (MANC) connectome is a densely reconstructed map of synaptic connections in the fruit fly
  nerve cord"; "It captures more synaptic connectivity than any other public connectome at the time of its release in
  June 2023."; "The complete MANC connectome can be downloaded as flat files from this public google bucket."
  (link `https://console.cloud.google.com/storage/browser/flyem-manc-exports`).
- neuPrint public dataset list (`https://neuprint.janelia.org/api/dbmeta/datasets`, HTTP 200 without a token): the
  MANC datasets served are exactly **`manc:v1.0`, `manc:v1.2.1`, `manc:v1.2.3`** (the full list on 2026-09-22:
  hemibrain:v1.2.1, male-cns:v0.9, male-cns:v1.0, manc:v1.0, manc:v1.2.1, manc:v1.2.3, mushroombody,
  optic-lobe:v1.0.1, optic-lobe:v1.1). Per-dataset fields:
  - `manc:v1.0`: `"last-mod": "2023-05-31 23:54:01"`, `"uuid": "59b37970bc7a4341b9a3a965a0d6b402"`, 61 ROIs.
  - `manc:v1.2.1`: `"last-mod": "2024-02-01 00:07:45.885983601-05:00"`, `"uuid": "7b5e8f7f805c4314bee37b75b4ff9292"`, 59 ROIs.
  - `manc:v1.2.3`: `"last-mod": "2024-02-01 00:07:45.885983601-05:00 / 2024-08-31 00:00:00.000000000-05:00 (segment
    property update)"`, `"uuid": "7b5e8f7f805c4314bee37b75b4ff9292"` (same DVID node as v1.2.1), 59 ROIs (identical
    list to v1.2.1). Note: the "2024-08-31 … segment property update" text predates every v1.2.3 object in the bucket
    (2025-09-26 onwards, see 3.4); what it refers to is UNVERIFIED.
- Marin et al. (RP v1, 2024-07-22), verbatim: "It is important to note that MANC annotations were improved
  substantially between the version of the dataset (manc:v1.0) that accompanied our initial preprints and the current
  version (manc:v1.2.1). In particular, hemilineage “05A” was merged into hemilineage “05B” as a minority
  neurotransmitter subpopulation and the tentative hemilineage designation “15A” was removed. Neurons of VNC origin and
  sensory neurons were also systematically retyped to emphasise serial homology across neuromeres while retaining finer
  resolution within neuromeres. Figures featuring type-specific information have been updated or created using current
  annotations and types (manc:v1.2.1). Researchers who have accessed the original dataset are strongly encouraged to
  refer to the annotations and type names featured in the current version of the dataset in any publications" and
  "This is a living dataset, with annotations still expected to improve incrementally over time with input from the
  larger Drosophila research community. Barring major proofreading corrections, bodyids are stable and the best way to
  track particular neurons of interest. Future updates to annotations, including cell type matches to the light level
  literature, will be provided in periodic patches to Neuprint and new versions of Clio Neuroglancer."
- natverse/malevnc (git history of https://github.com/natverse/malevnc, cloned 2026-09-22): commit 43174e0
  (2024-03-25) "make manc:v1.2.1 the public default" changes `R/datasets.R` from `malevnc.neuprint_dataset="manc:v1.0"`
  to `"manc:v1.2.1"` (tag v0.3.1, 2024-03-25; NEWS: "* make manc:v1.2.1 the public default"; tag v0.3 the same day:
  "Version 0.3 provides stable access to the public manc data release."). Commit 7e82dc2 (2025-12-15) "switch to
  manc:v1.2.3 as default dataset" changes it to `"manc:v1.2.3"` (tag v0.3.3, 2025-12-15; NEWS: "* switch to
  manc:v1.2.3 as default public dataset"). No commit ever referenced `manc:v1.1`, `v1.2.0` or `v1.2.2`.
- janelia-flyem/flyem-snapshot README (https://github.com/janelia-flyem/flyem-snapshot, HEAD 2218084, 2026-09-21):
  the worked example is "Go to the snapshot directory: `cd workspace/snapshot-configs/manc/v1.2.1`" / "Start the job:
  `flyem-snapshot -c manc-v1.2.1-release.yaml`" and "Ingest the snapshot into neo4j:
  `ingest-neuprint-snapshot-using-apptainer 2024-02-01-3ddc3f`" — consistent with the neuPrint `last-mod` of
  2024-02-01 for manc:v1.2.1.
- Cheong et al. VOR (2026-07-20) used "MANC v1.2.3" (quote in 1.3).

### 3.2 v1.0 bucket contents — VERIFIED (GCS JSON API, `https://storage.googleapis.com/storage/v1/b/flyem-manc-exports/o`)
19 objects, all under `v1.0/`, created 2023-06-02 … 2023-06-12, none modified since (`metageneration` = 1):
- 2023-06-02: `manc-synapse-partners-2023-05-03-215e08-minconf-0.0.feather.bz2` (1,117,661,989 B);
  `manc-traced-adjacencies-v1.0/{README, traced-neurons.csv, traced-connections.csv, traced-connections2.csv,
  traced-connections-per-roi.csv}`.
- 2023-06-05: `manc-v1.0-neuron-properties.feather`; `neuprint_manc_v1.0/README`; all `neuprint_manc_v1.0_ftr/*.ftr`
  except `Neuprint_Neurons_manc_v1.ftr`.
- 2023-06-12: `neuprint_manc_v1.0/neuprint_manc_v1.0_csv.tar.gz` (5,291,966,339 B) and
  `neuprint_manc_v1.0_ftr/Neuprint_Neurons_manc_v1.ftr` (917,907,106 B).
- `neuprint_manc_v1.0/README` (verbatim, complete): "neuprint_manc_v1.0_csv.tar contains csv files and command to
  build the neuprint database in neo4j 4. / neuprint_manc_v1.0_ftr contains feather file representations of all the
  neuprint neo4j nodes and relationships of the manc database. Use these to load the date into a pandas dataframe."
- `manc-traced-adjacencies-v1.0/README` (verbatim excerpts): "This directory contains the exported adjacency table for
  all Traced Neurons in the MANC v1.0 dataset from https://neuprint.janelia.org." / "traced-connections.csv … where
  'weight' corresponds to the total synapse count in the connections between each neuron pair." /
  "traced-connections-per-roi.csv … Only "primary" ROIs are referenced. Synapses falling outside the primary ROIs are
  listed with roi "NotPrimary"." / "These results were obtained via the neuprint-python[1] library (v0.4.25) as follows:
  >>> client = Client('neuprint.janelia.org', 'manc:v1.0') >>> traced_df, roi_conn_df =
  fetch_traced_adjacencies('manc-traced-adjacencies-v1.0')".
- The v1.0 neuPrint `:Meta` node (`Neuprint_Meta_manc_v1.ftr`, local copy) has `tag = v1.0`,
  `uuid = 59b37970bc7a4341b9a3a965a0d6b402` (same as the public API), `lastDatabaseEdit = 2023-05-02 23:54:01`
  (the API's `last-mod` is 2023-05-31 23:54:01 — different day, same time-of-day; which one is authoritative is
  UNVERIFIED), `latestMutationId = 1000097500`, `totalPreCount = 10343391`, `totalPostCount = 74456993`,
  `info = https://www.janelia.org/project-team/flyem/hemibrain` (a hemibrain leftover), `logo = public/VNC_all_neuropils.png`.

### 3.3 v1.1 — no public trace found (UNVERIFIED whether it existed internally)
Searched: neuPrint public dataset list (only v1.0, v1.2.1, v1.2.3); both buckets (no `v1.1` object or prefix);
Janelia page and its Wayback copies (no v1.1 news line); malevnc git history (`git log -S'v1.1'` → nothing);
flyem-snapshot repo; the three papers (Takemura/Marin mention only manc:v1.0 and manc:v1.2.1; Cheong VOR only v1.2.3).

### 3.4 v1.2 / v1.2.1 / v1.2.3 in `gs://manc-seg-v1p2/` — VERIFIED (GCS JSON API; `timeCreated` = when the current
content generation was written, `updated` also moves on metadata-only edits, see 3.6)
Top-level objects:
| object | timeCreated (UTC) | size (B) |
|---|---|---|
| `manc-v1.2-synapse-partners-minconf-0.0.feather` | 2024-03-11T18:51:11 | 1,937,212,010 |
| `manc-v1.2.1-neuprint-layers.json` | 2024-09-27T16:01:10 | 11,633 |
| `manc-v1.2.3-neuprint-layers.json` | 2025-09-26T03:16:36 | 10,898 |
| `manc-v1.2.3-clio.json` | 2025-10-20T16:46:13 | 10,174 |
| `manc-v1.2.3.json` | 2025-10-20T16:46:24 | 11,054 |
Prefixes: `manc-seg-v1.2/` and `manc-v1.2-synapse-partners-minconf-0.0.precomputed/`. There is **no**
`manc-v1.2-neuprint-layers.json` and **no** `manc-v1.2.2-*` object (both `NoSuchKey`).

Inside `manc-seg-v1.2/` (the segmentation):
- scale shards, e.g. `manc-seg-v1.2/16_16_16/004f.shard`: created **2024-02-19** (sampled from the first 1000 listed
  objects; all sampled shards share that date; `updated` 2025-11-01 = metadata).
- `manc-seg-v1.2/manc-v1.2-snapshot-superdecimated-meshes/*`: created 2024-03-12.
- `manc-seg-v1.2/info` (neuroglancer precomputed info): (re)created **2025-09-26T02:14:59**, metageneration 1; content:
  `{"@type": "neuroglancer_multiscale_volume", "data_type": "uint64", "segment_properties": "segment_properties_v1.2.3",
  "mesh": "mesh-multi-res", "skeleton": "skeleton", "type": "segmentation"}`, 8 scales from 8×8×8 nm
  (size 42944×56064×82304) to 1024 nm.
- Annotation snapshots (neuroglancer `segment_properties`):
  - `segment_properties/info` — created **2024-09-16T20:51:42** (1,939,689 B): 27,046 ids; properties `type` (label,
    23,608 non-empty), `PreSyn`, `PostSyn`, `tags` (929 tags incl. `_has_group`, `_has_type`).
  - `segment_properties_v1.2.1/info` — created **2024-09-27T15:51:58** (1,736,018 B): 24,143 ids; `type` (23,608
    non-empty), `PreSyn`, `PostSyn`, `tags` (927). COMPUTED [2026-09-23]: its body→type map is **identical** to the
    2024-09-16 base snapshot (same 23,608 typed bodies, same labels), so "v1.2 base" and "v1.2.1" differ only in the
    two `_has_*` helper tags and the id list.
  - `segment_properties_v1.2.3/info` — created **2025-09-26T02:07:03** (3,903,950 B): 102,158 ids; `type` (23,610
    non-empty), `PreSyn`, `PostSyn`, `tags` (269).
  - `segment_properties_v1.2.3/{combined_properties,instance_property,numeric_properties,tags_property,
    type_and_group_property,type_property}/info` — created **2025-10-26T20:02:59–20:03:03**. `type_property/info`:
    23,665 ids, all typed. `combined_properties/info`: 23,665 ids with `type`, `group` (18,735), `serial` (5,916),
    `cluster` (5,937), `origin` (23,479), `vfbId` (23,665, e.g. `VFB_jrcv07ps`), `syn_post`, `syn_pre`,
    `syn_downstream`, `syn_connections`, `tags` (265).
- Neuroglancer states (both read in full):
  - `manc-v1.2.1-neuprint-layers.json` (title `manc-v1.2`): segmentation layer named `manc:v1.2.1` with source
    `precomputed://gs://manc-seg-v1p2/manc-seg-v1.2`.
  - `manc-v1.2.3-neuprint-layers.json` (title `manc-v1.2.3-neuprint-layers`): segmentation layer named `manc:v1.2.3`
    with sources `precomputed://gs://manc-seg-v1p2/manc-seg-v1.2` **plus**
    `precomputed://gs://manc-seg-v1p2/manc-seg-v1.2/segment_properties_v1.2.3/type_property/`.
  - Both states share every other layer: EM `precomputed://gs://flyem-vnc-2-26-213dba213ef26e094c16c860ae7f4be0/v3_emdata_clahe_xy/jpeg`;
    ROI layers `all-vnc-roi`, `synaptic-neuropil`, `roi-202208` (neuropils), `nerve-roi-202301` (nerves) and
    `court-et-al-systematic-manc_tracts` in `gs://flyem-vnc-roi-d5f392696f7a48e27f49fa1a9db5ee3b/`; synapse annotation
    layers `precomputed://gs://manc-seg-v1p2/manc-v1.2-synapse-partners-minconf-0.0.precomputed`; `voxel-classes` and
    `initial-supervoxels` in `gs://vnc-v3-seg-3d2f1c08fd4720848061f77362dc6c17/`.

### 3.5 Did the segmentation change between v1.2.1 and v1.2.3? — VERIFIED: no evidence of any change
1. neuPrint reports the **same DVID UUID** `7b5e8f7f805c4314bee37b75b4ff9292` and the same primary `last-mod`
   (2024-02-01) for `manc:v1.2.1` and `manc:v1.2.3` (public API, 3.1).
2. Both neuroglancer states point at the **same** segmentation volume `precomputed://gs://manc-seg-v1p2/manc-seg-v1.2`
   (3.4); the segmentation shards were written 2024-02-19 and only the `info` pointer file was rewritten on 2025-09-26
   to select `segment_properties_v1.2.3`.
3. The same synapse-partner table (`manc-v1.2-synapse-partners-minconf-0.0.feather`, generation 1710183071419668 of
   2024-03-11) serves both; its content generation has never changed (3.6).
4. The v1.2.3 datasets differ from v1.2.1 only in annotations (3.7). No document states "the segmentation is
   unchanged" in words — the statement above is an inference from the identical identifiers.

### 3.6 GCS metadata caveat — VERIFIED
Several objects show 2026 `updated` timestamps although their content generation is old; GCS bumps `updated` on
metadata edits (`metageneration` > 1) without changing `generation`/`md5Hash`. Recorded on 2026-09-22:
| object | generation | metageneration | timeCreated | updated | md5Hash |
|---|---|---|---|---|---|
| `manc-seg-v1p2/manc-v1.2-synapse-partners-minconf-0.0.feather` | 1710183071419668 | 4 | 2024-03-11 | 2026-08-20 | `B2Np+rqyLEhmTIhWvNyesQ==` |
| `manc-seg-v1p2/manc-seg-v1.2/segment_properties/info` | 1726519902371262 | 10 | 2024-09-16 | 2026-08-20 | `5F8FS0O8dyl9qg8M5en8Dg==` |
| `manc-seg-v1p2/manc-seg-v1.2/segment_properties_v1.2.1/info` | 1727452318850851 | 3 | 2024-09-27 | 2026-08-02 | `KCOpMbGDP7bVMdSd/gMr8w==` |
| `manc-seg-v1p2/manc-seg-v1.2/segment_properties_v1.2.3/info` | 1758852423072514 | 1 | 2025-09-26 | 2025-09-26 | `ieqXnF6xpiUgh31oo8lvag==` |
| `manc-seg-v1p2/manc-seg-v1.2/segment_properties_v1.2.3/combined_properties/info` | 1761508981164722 | 4 | 2025-10-26 | 2026-08-20 | `XYoI7RtD/sZt/ZaMw+BCSg==` |
| `manc-seg-v1p2/manc-seg-v1.2/segment_properties_v1.2.3/instance_property/info` | 1761508983605612 | 5 | 2025-10-26 | 2026-04-17 | `Xi03EqQ88Wf7mrBwQne/jQ==` |
| `manc-seg-v1p2/manc-seg-v1.2/segment_properties_v1.2.3/type_property/info` | 1761508982184485 | 1 | 2025-10-26 | 2025-10-26 | `oaOUH3diSt/afPncP+bA2A==` |
| `manc-seg-v1p2/manc-v1.2.1-neuprint-layers.json` | 1727452870346236 | 1 | 2024-09-27 | 2024-09-27 | `U1M6vpxfrv6ucE98iyqTQQ==` |
| `manc-seg-v1p2/manc-v1.2.3-neuprint-layers.json` | 1758856596600762 | 1 | 2025-09-26 | 2025-09-26 | `ED613PnWWkqDk+rJKJMvDg==` |
| `flyem-manc-exports/v1.0/neuprint_manc_v1.0/neuprint_manc_v1.0_ftr/Neuprint_Meta_manc_v1.ftr` | 1685999470391208 | 1 | 2023-06-05 | 2023-06-05 | `5trku1Xgkb0ya+U2IbWhGw==` |
| `flyem-manc-exports/v1.0/manc-v1.0-neuron-properties.feather` | 1685939278333965 | 1 | 2023-06-05 | 2023-06-05 | `9GcxF1WcxyfhvvywIrahQw==` |
| `flyem-manc-exports/v1.0/manc-synapse-partners-2023-05-03-215e08-minconf-0.0.feather.bz2` | 1685678232545414 | 1 | 2023-06-02 | 2023-06-02 | `XC2FAlJnU/cHHGNSPsHnmw==` |
Registry pins should therefore key on `generation`/`md5Hash`, not on `updated`.

### 3.7 What changed between v1.2.1 and v1.2.3 — no written changelog exists (UNVERIFIED as a provider statement);
COMPUTED diff of the public snapshots [2026-09-23]
Searched for release notes: Janelia page (+ Wayback), neuPrint public API descriptions (identical text for all
three datasets), neuprint-python changelog, flyem-snapshot repo, malevnc NEWS.md, the three papers, web search for
neuPrint Google-group announcements — none describes the v1.2.1→v1.2.3 annotation patch.
Comparing `segment_properties_v1.2.1/info` (2024-09-27) with `segment_properties_v1.2.3/type_property/info` and
`combined_properties/info` (2025-10-26):
- Typed bodies 23,608 → 23,665 (23,546 typed in both; 62 typed only in v1.2.1; 119 typed only in v1.2.3).
- Distinct type names 4,076 → 4,082. Names only in v1.2.3 (12): `AN01A089, AN05B107, AN06B088, AN06B089, AN06B090,
  AN07B106, EA00B007, IN06B088, IN19A018, INXXX470, INXXX471, ~`. Names only in v1.2.1 (6): `AN05B094, EN00B007,
  IN06B084, INXXX007, MNfl10, MNml10`.
- 29 shared bodies changed type; the renamings are (old → new: bodies): AN27X017→AN27X018: 4; IN06B015→IN06B088: 2;
  INXXX007→INXXX470: 2; AN06B023→AN06B089: 2; MNml10→INXXX471: 2; MNfl10→INXXX471: 2; AN05B094→AN05B107: 2;
  AN01A055→AN01A089: 2; IN06B084→IN06B065: 2; IN19A006→IN19A018: 2; AN06B031→AN06B090: 2; AN06B015→AN06B088: 2;
  AN07B015→AN07B106: 2; EN00B007→EA00B007: 1. So the "INXXX4xx" names are exactly `INXXX470` and `INXXX471` (four
  bodies, two of them former leg motor-neuron types MNfl10/MNml10 reclassified as intrinsic neurons of unknown
  hemilineage); there is no larger new series.
- Tag vocabulary: v1.2.1 uses snake_case keys (`class, subclass, hemilineage, birthtime, soma_side, soma_neuromere,
  entry_nerve, exit_nerve, long_tract, modality, serial_motif, origin, target`); v1.2.3 uses camelCase (`somaSide,
  somaNeuromere, entryNerve, exitNerve, longTract, serialMotif`) and adds `transmission` (4 values), `receptorType` (8),
  `rootSide` (5) and `celltypePredictedNt` (`acetylcholine, gaba, glutamate, unclear, unknown`); `origin` moved from a
  tag to a string property and `target` tags are gone from the snapshot.
Marin et al.'s documented changes (05A→05B merge, 15A removed, systematic retyping) concern **v1.0 → v1.2.1**, not
v1.2.1 → v1.2.3.

---------------------------------------------------------------------------------------------------------------------

## 4. neuPrint synapse-count semantics for MANC: `weight`, `weightHP`, `weightHR`

### 4.1 Threshold values — VERIFIED (two independent primary sources)
- The MANC v1.0 `:Meta` node (`Neuprint_Meta_manc_v1.ftr`, official export): **`postHighAccuracyThreshold = 0.4`,
  `postHPThreshold = 0.7`, `preHPThreshold = 0.7`**.
- janelia-flyem/flyem-snapshot, `flyem_snapshot/outputs/neuprint/meta.py` (config schema, verbatim):
  - `postHighAccuracyThreshold`: "Which confidence threshold to use when calculating each connection's standard 'weight'.
    This is determined by finding a 'balanced' point on our synapse precision/recall curve. For hemibrain we used 0.5;
    for MANC we used 0.4"
  - `postHPThreshold`: "Which confidence threshold to use when calculating each connection's weightHP This is determined
    via analysis of our on our synapse precision/recall curve to select a point that favors higher precision at the
    expense of lower recall. For both hemibrain and MANC, we used 0.7"
  - `preHPThreshold`: "Deprecated. Do not set."
- The neuPrint public API does not expose these Meta properties without a login (`/api/npexplorer/...` → HTTP 401
  `{"message":"authentication required"}`), so the v1.2.1/v1.2.3 values could not be re-read from the live databases
  (UNVERIFIED for v1.2.x from neuPrint itself; flyem-snapshot's "for MANC we used 0.4 / 0.7" is the pipeline that
  produced the v1.2.1 snapshot per its README).

### 4.2 Definitions — VERIFIED
- flyem-snapshot `outputs/neuprint/segment.py`, `export_neuprint_segment_connections` (verbatim code):
  `partner_df['conf_cat'] = 'low'` … `partner_df.loc[partner_df['conf_post'] >= balanced_confidence, 'conf_cat'] = 'med'`
  … `partner_df.loc[partner_df['conf_post'] >= hp_confidence, 'conf_cat'] = 'high'` …
  `connectome['weightHR'] = connectome[['low', 'med', 'high']].sum(axis=1)` /
  `connectome['weight'] = connectome[['med', 'high']].sum(axis=1)` / `connectome['weightHP'] = connectome['high']`.
  I.e. **only the postsynaptic confidence is thresholded** (`>=`, inclusive): `weight` = PSDs with
  `conf_post >= postHighAccuracyThreshold` (0.4 for MANC); `weightHP` = PSDs with `conf_post >= postHPThreshold` (0.7);
  `weightHR` = all PSDs that survived the input `min-confidence` pre-filter. Comments: "Unlike weightHR/weight/weightHP,
  we don't bother computing separate high-recall/high-precision variants of the compartment breakdown"; in
  `neuprint.py`: "# TODO: weightHP, and get rid of weightHR (a failed experiment, I think.) If I don't get rid if it,
  then I need to avoid pre-filtering by min-confidence, and apply that filter before neuron/weight export (but not
  synapse export)." `inputs/synapses.py` `min-confidence`: "Before generating any results, exclude synapse predictions
  which fall below this confidence level. Note: This pre-filters the synapse table, so it is effectively a minimum
  bound on the confidence threshold for neuprint exports." (default 0.0). `segment.py` also filters bodies' pre/post
  counts with `partner_df.query('conf_post >= @balanced_confidence')` ("Filter out low-confidence PSDs before computing
  weights.").
- connectome-neuprint/neuPrint `pgmspecs.md` (https://raw.githubusercontent.com/connectome-neuprint/neuPrint/master/pgmspecs.md):
  "weight: number of postsynaptic densities per connection"; "weightHP: number of high-precision postsynaptic densities
  per connection"; `preHPThreshold`/`postHPThreshold`: "threshold at which the synapse classifier acheives high
  precision" [sic]. `weightHR` is not in this spec.
- neuPrint user manual (https://neuprint.janelia.org/public/neuprintuserguide.pdf, 18 pp., undated, hemibrain-era):
  "weight: number of connections … weightHP: high confidence number of connections"; Meta example "Threshold for high
  confidence (weightHP) synapses in the Hemibrain dataset MATCH (m:Meta) RETURN m.postHPThreshold, m.preHPThreshold".
- neuprint-python changelog (https://connectome-neuprint.github.io/neuprint-python/docs/changelog.html):
  0.4.23 (2022-06-14): "In recent neuprint databases, some `:ConnectsTo` relationships may have a `weight` of `0`. In
  such cases, the relationship will have a non-zero `weightHR` (high-recall weight), but all of the relevant synapses
  are low-confidence." 0.4.25 (2022-09-15): "In live-updated neuprint databases, it is possible that an edge's `weight`
  can become out-of-sync with its `roiInfo` totals." 0.6.3 (2026-07-20): `weight_props` parameter "to optionally fetch
  alternative `:ConnectsTo` weight properties (`weightHP`, `weightAxonAxon`, …)"; "Behavior change: `weight_props`
  defaults to `'all'` for `fetch_adjacencies()` and `fetch_simple_connections()`".
- neuprint-python source (`neuprint/queries/synapsecriteria.py`, master, 2026-09-22), `SynapseCriteria.confidence`
  docstring: "Limit results to synapses of at least this confidence rating. By default, use the dataset's default
  synapse confidence threshold, which will include the same synapses that were counted in each neuron-neuron `weight`
  (as opposed to `weightHP` or `weightHR`)." Code: `confidence = client.meta.get('postHighAccuracyThreshold', 0.0)` and
  the Cypher condition `({matchvar}.confidence > {confidence})` — note the **strict `>`** here versus flyem-snapshot's
  `>=`; with float32-stored confidences the two can differ at the boundary (relevant to BrainIR's `CountRule` inference).
- Plaza et al. 2022: "Each synapse contains a confidence field, typically computed by automatic synapse prediction,
  that can be used to model confidence for certain neuron connections." No numeric thresholds.

### 4.3 Takemura et al. Methods on thresholds — VERIFIED that no numbers are given
Section 2.6: "Synapse prediction was performed as described in hemibrain project[Scheffer et al., 2020]. Through careful
selection of training and validation data spanning the VNC ROIs, we were able to achieve desired performance with a
single network for detecting pre-synaptic T-bars, and did not require the cascaded approach as used in previous work.
The post-synaptic partners were found using the procedures used for the hemibrain[Scheffer et al., 2020]. The
precision-recall plots for synapse identification are shown in Fig. 4." The text nowhere mentions 0.4/0.7, weightHP or
weightHR. Cheong et al. apply analysis thresholds on top of `weight` (e.g. "≥1% synapse input threshold", "Synapse weight
(neuron-to-neuron mean) is thresholded at ≥20").

---------------------------------------------------------------------------------------------------------------------

## 5. Neuron definition: neurons vs fragments, status values, counts

### 5.1 Statements — VERIFIED
- Takemura et al.: "Our VNC sample contains roughly 23 thousand traced neurons, 10 million TBars, 74 million PSDs, and
  44m of neuronal cable." Table 1 caption: "Counts are the number of objects found within the region; percentage is the
  fraction in traced neurons. Connection completion percentage is the fraction of all TBar-PSD pairs where both are in
  traced neurons." Section 2.8: "The primary completion metric used is called the completeness, which is the percentage
  of all synapses in a region where both the pre- and post-synaptic partners belong to identified neurons." Section 2.14:
  "Reconstructed neurons can be divided into four large categories: (1) Descending neurons … (2) Sensory neurons …
  (3) Motor neurons … (4) Other neurons with somas in the VNC cortex, comprising intrinsic neurons, ascending neurons,
  and efferent neurons." and "Complete details for identification and typing of descending neurons and motor neurons
  (total n=2065) are described in Cheong, Eichler, Stürner et al. Sensory neurons and intrinsic neurons of the VNC other
  than motor neurons (total n=21683) are described in detail in Marin et al." The paper does not define "Traced"
  operationally; it inherits the hemibrain proofreading procedure ("Proofreading was largely performed as in the
  hemibrain").
- Marin et al.: "The MANC connectome (Takemura et al., 2023) is composed of ∼15.8K central neurons and ∼6.5K sensory
  neurons … (Glia were not systematically reconstructed or typed, but 348 bodies have been annotated as class “glia”.)
  1328 descending neurons (DN) … 5927 sensory neurons (SN) … 535 sensory ascending neurons (SA) … 13,060 intrinsic
  neurons (IN) are restricted to the VNC, and 1865 ascending neurons (AN) …"
- Cheong et al. VOR: "In total, we found 733 MNs in MANC, with 362 exiting left side nerves, 361 exiting right side
  nerves, and 10 that exited through the abdominal trunk nerve (AbNT)"; Discussion: "a DN cell count of 1328 … the AN cell
  count of 1864 … We also found and annotated 737 MNs in MANC" (733 vs 737 appear in the same paper).
- `manc-traced-adjacencies-v1.0/README`: "the exported adjacency table for all Traced Neurons in the MANC v1.0 dataset";
  neuprint-python `fetch_traced_adjacencies` (source, `queries/connectivity.py`): "Convenience function that calls
  `fetch_adjacencies()` for all `Traced`, non-`cropped` neurons." implemented as
  `NeuronCriteria(status="Traced", cropped=False)`.
- neuPrint user manual glossary (hemibrain-era; the only official prose definition found): "Traced A body more complete
  than ‘Roughly traced’ (usually traced by a lab) and validated by a biological expert (Shin-ya Takemura, Kazunori
  Shinomiya)"; "Orphan A body that can’t be traced and does not exit the volume"; "Unimportant A body irrelevant to
  reconstructing neurons and the connectome such as glial profiles and out-of-bounds bodies"; "Assign Small body that is
  within the set required for a 0.5 connectome - Has approximately ≥ 2 T-bars or ≥ 10 PSDs"; "Bodies are manual
  proofread to correct errors made by the automatic segmentation algorithm and then assigned a status depending on
  their size/completeness."
- MANC v1.0 `:Meta.statusDefinitions` (verbatim JSON): `{"Roughly traced":"neuron high-level shape correct and validated
  by biological expert", "Prelim Roughly traced": "neuron high-level shape most likely correct or nearly complete, not yet
  validated by biological expert", "Anchor":"Big segment that has not been roughly traced", "0.5assign":"Segment fragment
  that is within the set required for a 0.5 connectome"}`. flyem-snapshot `meta.py` on this field: "This is what the
  hemibrain/MANC neuprint repos had stored: These are not 'status' values, but rather 'statusLabel', and this list is
  incomplete." (the field is now "Deprecated").
- `:Segment` vs `:Neuron` label rule in the current pipeline (flyem-snapshot `neuprint.py`, `neuron-label-criteria`):
  "In neuprint, all synaptic bodies are :Segment nodes, but only 'important' ones also become :Neuron nodes." Defaults:
  `synweight` ≥ 100, `pre` ≥ 100, `post` ≥ 100, non-empty `["rootLocation", "somaLocation", "class", "type", "instance",
  "group", "somaSide", "synonyms"]`, `status` in `["Traced", "Anchor"]`, `excluded-status` `["Unimportant", "Glia"]`
  ("These should be neuprint 'status' values, not 'statusLabel' values."). pgmspecs (hemibrain): "All Segment nodes with
  >=2 t-bars, >=10 psds, a name, a status, or a soma are labeled Neuron". The rule actually used for MANC v1.0 (2023,
  pre-flyem-snapshot) is not documented anywhere found → UNVERIFIED; the v1.0 export shows 102,369 `:Neuron`-labelled
  segments (below).

### 5.2 Counts in the official v1.0 exports — COMPUTED [2026-09-23] from local copies of the bucket objects
- `Neuprint_Neurons_manc_v1.ftr` (2023-06-12 database): 24,522,126 segments; 102,369 carry the `Neuron` label.
  `status` over all segments: null 24,495,501; **Traced 23,514**; Unimportant 1,530; Assign 889; Orphan 251;
  PRT Orphan 245; Anchor 196 (every non-null status is on a `:Neuron`-labelled segment). `statusLabel` of the Traced
  bodies: Roughly traced 18,305; Prelim Roughly traced 4,895; RT Orphan 314.
- `manc-v1.0-neuron-properties.feather` (2023-06-05): 102,369 rows; `status`: Traced 23,200; RT Orphan 314; the rest as
  above — i.e. the 314 "RT Orphan" bodies of 2023-06-05 are "Traced" (statusLabel "RT Orphan") in the 2023-06-12
  database (already noted in `research/LOG.md`). `predictedNt`: acetylcholine 11,701; glutamate 8,037; gaba 6,147;
  unknown 502; null 75,982 (so 26,387 bodies carry a body-level NT call, more than the 23,514 Traced).
- Public v1.2.x snapshots: 23,608 typed bodies (v1.2 base and v1.2.1), 23,665 (v1.2.3) — section 3.7.

---------------------------------------------------------------------------------------------------------------------

## 6. Neurotransmitter predictions

### 6.1 Method and provenance — VERIFIED
- Takemura et al. §2.10 (verbatim): "Computer vision prediction of neurotransmitter for each presynaptic location was
  performed using the procedures and software from [Eckstein et al., 2023] for the three most common neurotransmitters -
  acetylcholine, GABA, and glutamate. Ground truth neurotransmitter labels for 187 neurons (67 acetylcholine, 55 GABA,
  65 glutamate) were annotated based on morphological identification with light level data. Neurons were partitioned
  into disjoint training and validation sets of 80% and 20%, respectively, optimizing for similar class frequency in
  each partition. Models included an additional class to indicate non-synaptic or unrecognized structures, trained by
  sampling random locations in the bounding box of all synaptic locations. Predictions from the validation-selected
  model were aggregated for each neuron as the mean of probabilities of all presynaptic sites. The maximum likelihood
  predicted probability for each neuron was annotated as the predicted neurotransmitter." and "In NeuPrint, the computed
  probability of each neuro transmitter type is attached to the TBar component of each synapse. For a synapse s, these
  can be found as s.ntAcetylcholineProb, s.ntGabaProb, and s.ntGlutamateProb, and s.ntUnknownProb yields the probability
  that s matches none of those three. The value ranges from 0 (impossible) to 1.0 (certain). The values sum to 1 and
  should be interpreted as relative probabilities, as other transmitters are possible." Author contributions: "AC, JF,
  and GSXEJ predicted neurotransmitters" (Andrew S Champion, Jan Funke, Gregory SXE Jefferis); Acknowledgements: "We thank
  Barry Dickson and his lab for providing ground truth data used for neurotransmitter prediction."
  So: classes = acetylcholine / GABA / glutamate + an "unknown" (non-synaptic/unrecognized) class; body-level
  `predictedNt` = argmax of the per-body mean of T-bar probabilities (the v1.0 export's `predictedNtProb` is that maximum;
  BrainIR's `types.nt_argmax_consistency` check tests exactly this).
- Eckstein et al. 2024 (Cell; PMC11106717): the network predicts "acetylcholine, glutamate, GABA, serotonin, dopamine,
  octopamine" for FAFB/hemibrain, and states "Our results for a full ventral nerve cord (MaleVNC, 82% accuracy, limited to
  acetylcholine, glutamate, and GABA) are reported elsewhere." — i.e. the Cell paper is the method; the MANC application
  (3 classes + unknown) is reported in Takemura et al.
- Marin et al.: "Fast-acting neurotransmitter predictions were made for every neuron in the dataset (Eckstein et al.,
  2023; Takemura et al., 2023)"; "We generated a neurotransmitter prediction for every neuron in MANC … There were
  exceptions, however - most commonly due to a paucity of chemical presynapses in the MANC volume because of class (e.g.,
  ascending or motor neuron), transmission mode (e.g., putative electrical), or incomplete reconstruction".
- Cheong et al. VOR: "Takemura et al., 2024 predicted ACh, GABA, or Glu neurotransmitter type for all MANC neurons using
  a convolutional neural network."; Figure 18 legend: "Neurotransmitter predictions are thresholded at ≥0.7 probability
  and assigned to the unknown (unk.) category if below threshold." (an analysis choice, not a database field).

### 6.2 Changes between v1.0 and v1.2.x — UNVERIFIED (no documentation); indirect evidence
- No source describes a re-run of NT prediction for v1.2.x. flyem-snapshot (`inputs/neurotransmitters.py`) says of the
  older pipeline: "For older datasets (MANC, hemibrain), we didn't compute a top body prediction and associated
  confidence score. Instead, we just exported the mean NT prediction scores for each body as Neuron properties." and
  "For manc, the body prediction was the one with the highest mean tbar score. But going forward, we pick the most
  frequent max tbar score." `bin/update_neuprint_annotations.py`: "Neurotransmitters are supposed to be computed anew
  for each neuprint snapshot, not loaded into clio. But for historical reasons, we did upload NT predictions into the
  MANC clio. We do NOT want to use those clio NT values to overwite neuprint NT values."
- COMPUTED [2026-09-23]: the v1.2.3 neuroglancer snapshot carries `celltypePredictedNt:{acetylcholine, gaba, glutamate,
  unclear, unknown}` tags that do not exist in the v1.2.1 snapshot (flyem-snapshot's `min-celltype-presyn` rule yields
  "unclear" when a type has too few T-bars), so v1.2.3 exposes a **cell-type-level** NT field in addition to the
  body-level one. Whether body-level `predictedNt` values differ between manc:v1.0, v1.2.1 and v1.2.3 cannot be checked
  without a neuPrint login (the public snapshots do not include body-level NT).

---------------------------------------------------------------------------------------------------------------------

## 7. ROI naming: LegNp vs IntNp, Ov vs AMNp

### 7.1 Anatomical definitions — VERIFIED
- Court et al. 2020 (bioRxiv text): "The leg neuropil, between the VAC and the tectulum, is called 'intermediate
  neuropil' (IntNp) because it occupies most of the central third of the dorsoventral area in transverse section." and
  "The AMNp also contains a dense synaptic neuropil…that corresponds to a structure called the ovoid by Merritt and
  Murphey (1992)." (AMNp = accessory mesothoracic neuropil; the ovoid is a structure within it).
- Marin et al.: "In the thorax, the six leg neuropils (LegNp) each consist of two sensory neuropils - the ventral
  association centre (VAC, not labelled) and medial ventral association centre (mVAC) - along with the intermediate
  neuropil (IntNp)." and "The second thoracic neuromere (T2) or mesothorax includes the specialised wing and notum sensory
  neuropil called the ovoid (Ov)".
- Takemura et al. Table 1 caption: "Neuropils contained and defined in the ventral nerve cord, following the naming
  conventions of [Court et al., 2020] with the addition of (R) and (L) to specify the side of the soma for that region.
  … LegNP = leg neuropil; ANm = abdominal neuromeres; mVAC=medial ventral association center; Ov = ovoid neuropil; NTct
  = neck tectulum; WTct=wing tectulum; HTct = haltere tectulum; IntTct = intermediate tectulum; LTct = lower tectulum".
  §2.7: "The synaptic neuropils were defined using synapse point clouds (as this was performed before segmentation). The
  region boundaries including the fiber bundles were hand-drawn based on the grayscale data. The standard nomenclature
  system for the VNC [Court et al., 2020] was used to identify the neuropils and fiber bundles, although some structures
  were not identifiable from the point cloud data."

### 7.2 What the databases and volumes actually use — VERIFIED
- neuPrint public ROI lists: manc:v1.0 (61 ROIs), manc:v1.2.1 and manc:v1.2.3 (59 ROIs each, identical) all contain
  `LegNp(T1)(L)`…`LegNp(T3)(R)`, `Ov(L)`, `Ov(R)`, `mVAC(Tn)(S)`, `IntTct`, `LTct`, `NTct(UTct-T1)(S)`,
  `WTct(UTct-T2)(S)`, `HTct(UTct-T3)(S)`, `ANm` and the nerves; **none contains `IntNp*` or `AMNp*`**. The only v1.0 vs
  v1.2.x difference is that v1.0 also lists `GF(L)` and `GF(R)` (COMPUTED from the API output).
- The neuroglancer neuropil ROI volume used by both v1.2.x states,
  `gs://flyem-vnc-roi-d5f392696f7a48e27f49fa1a9db5ee3b/roi-202208/segment_properties/info`, names its segments
  `4 CV, 5 LegNp(T1)(L), 6 LegNp(T1)(R), 7 LegNp(T2)(L), 8 LegNp(T2)(R), 9 LegNp(T3)(L), 10 LegNp(T3)(R), 11 Ov(L),
  12 Ov(R), 13 IntTct, 14 LTct, 15–20 NTct/WTct/HTct(UTct-Tn)(S), 21 ANm, 22–27 mVAC(Tn)(S)` — again LegNp/Ov, not
  IntNp/AMNp.
- MANC v1.0 `:Meta` (official export): `primaryRois`, `superLevelRois`, `neuropilRois`, `nerveRois` and `roiInfo` use
  `LegNp(Tn)(S)` / `Ov(S)`, whereas `roiHierarchy` is a flat list under `"ventral nerve cord"` whose neuropil entries are
  `CV, IntNp(T1)(L), IntNp(T1)(R), IntNp(T2)(L), IntNp(T2)(R), IntNp(T3)(L), IntNp(T3)(R), AMNp(L), AMNp(R), IntTct,
  LTct, NTct(UTct-T1)(L/R), WTct(UTct-T2)(L/R), HTct(UTct-T3)(L/R), ANm, mVAC(Tn)(L/R)` followed by the nerves; it has
  **no** `LegNp*` or `Ov*` entries.

### 7.3 Interpretation — inferred; UNVERIFIED as an explicit provider statement
The six `IntNp(Tn)(S)` and two `AMNp(S)` names in the v1.0 `roiHierarchy` occupy exactly the slots of the six
`LegNp(Tn)(S)` and two `Ov(S)` ROIs in every other list (same count, same sides, same neuromeres, every other ROI name
identical), and Court et al.'s definitions make IntNp the main (non-VAC/mVAC) part of the leg neuropil and Ov the dense
synaptic core of the AMNp. The ROI volumes therefore appear to have been named `IntNp`/`AMNp` internally (Court et al.
parent-structure names) and published as `LegNp`/`Ov`, with the v1.0 `roiHierarchy` string never updated. No document
found states this renaming explicitly (searched: the three papers, neuPrint manual, pgmspecs, flyem-snapshot,
malevnc docs, web search for "IntNp" + neuPrint). BrainIR should treat `IntNp(Tn)(S)` ↔ `LegNp(Tn)(S)` and `AMNp(S)`
↔ `Ov(S)` as an alias mapping applied only when reading the v1.0 `roiHierarchy`, and record it as an inference. Note also
that the MANC "LegNp" ROI excludes the separately-listed `mVAC` ROIs, so it is narrower than Court et al.'s LegNp
(VAC + mVAC + IntNp) — consistent with it being the IntNp (+ unlabelled VAC) volume.

---------------------------------------------------------------------------------------------------------------------

## 8. neuPrint access without credentials — VERIFIED (2026-09-22)
- `https://neuprint.janelia.org/` renders only the single-page app ("neuPrintExplorer"); no dataset text is visible
  without logging in. Takemura et al.: "The VNC connectome is publicly available to anyone with a google account at
  https://neuprint.janelia.org, dataset MANC." Marin et al.: "Authentication via is required but this is available to
  anyone with a Google account."
- `GET https://neuprint.janelia.org/api/dbmeta/datasets` → HTTP 200 (JSON with `last-mod`, `uuid`, `ROIs`,
  `superLevelROIs`, `info`, `hidden`, `logo`, `description` per dataset) — **public**.
- `GET https://neuprint.janelia.org/api/dbmeta/version` → HTTP 200 `{"Version":"0.5.0"}`.
- `GET https://neuprint.janelia.org/api/npexplorer/roiconnectivity?dataset=manc:v1.2.1` → HTTP 401
  `{"message":"authentication required"}`. Stopped there; no token was used.
- neuprint-python docs index (https://connectome-neuprint.github.io/neuprint-python/docs/) has no dataset-specific
  MANC release notes; the changelog is quoted in 4.2.
- Janelia FlyEM "Tools and Data Release" page (https://www.janelia.org/project-team/flyem/tools-and-data-release) does
  not mention MANC at all.

---------------------------------------------------------------------------------------------------------------------

## 9. Summary of UNVERIFIED items (what was tried)
1. Existence of an internal MANC v1.1 or v1.2.2 — no public trace anywhere (3.3, 3.4).
2. A provider-written changelog for v1.2.1 → v1.2.3 — none found; only our COMPUTED snapshot diff (3.7) and the
   meaning of neuPrint's "2024-08-31 … (segment property update)" string (3.1).
3. `postHighAccuracyThreshold` / `postHPThreshold` values stored in the live manc:v1.2.1 and manc:v1.2.3 `:Meta` nodes
   — require login; supported only by flyem-snapshot's docstring "for MANC we used 0.4 / 0.7" (4.1).
4. Whether body-level `predictedNt` was recomputed between v1.0 and v1.2.x (6.2).
5. An explicit statement that `IntNp`→`LegNp` and `AMNp`→`Ov` are renamings (7.3) — inferred only.
6. The `:Segment`→`:Neuron` promotion rule used for the 2023 v1.0 build (5.1) — only the current flyem-snapshot
   defaults and the hemibrain-era pgmspecs rule are documented.
7. Which of `lastDatabaseEdit = 2023-05-02 23:54:01` (v1.0 Meta) and `last-mod = 2023-05-31 23:54:01` (public API) is
   the true v1.0 snapshot time (3.2).
8. Cheong et al.'s MN count: the VOR states both 733 and 737 (5.1).

## 10. Sources read (URL, date)
- https://www.janelia.org/project-team/flyem/manc-connectome (2026-09-22; raw HTML) and Wayback copies
  `http://web.archive.org/web/{20240413000406,20240713214832,20250122033402,20250911205810}id_/https://www.janelia.org/project-team/flyem/manc-connectome`
  (2026-09-22; CDX index also lists 2023-06-06, 2023-09-14, 2025-04-02, 2025-05-12, 2025-06-29, 2025-10-02,
  2025-12-10, 2026-01-22, 2026-05-11, 2026-06-07, 2026-09-08 captures; the 2023-09-14, 2025-10-02, 2025-12-10 and
  2026-09-08 captures returned ~15 kB shells without the page body and were not used).
- https://www.janelia.org/project-team/flyem/tools-and-data-release (2026-09-22).
- https://elifesciences.org/reviewed-preprints/97769, https://elifesciences.org/reviewed-preprints/97766,
  https://elifesciences.org/articles/96084 (full text, 2026-09-22); https://elifesciences.org/articles/97769 and
  /articles/97766 (HTTP 404, 2026-09-22); https://pmc.ncbi.nlm.nih.gov/articles/PMC13384506/ (Cheong VOR, 2026-09-22).
- https://api.crossref.org/works/{10.7554/eLife.97769, .97769.1, .97769.2 (404), .97766, .97766.1, .97766.2 (404),
  .96084, .96084.1, .96084.2, .96084.3, 10.3389/fninf.2022.896292, 10.1016/j.cell.2024.03.016} (2026-09-22);
  10.1016/j.neuron.2020.08.005 (2026-09-23).
- https://www.frontiersin.org/articles/10.3389/fninf.2022.896292/full (2026-09-22).
- https://pmc.ncbi.nlm.nih.gov/articles/PMC11106717/ (Eckstein et al. 2024, 2026-09-22).
- https://www.biorxiv.org/content/10.1101/122952v2.full (Court et al., 2026-09-22).
- https://neuprint.janelia.org/, https://neuprint.janelia.org/api/dbmeta/datasets, …/api/dbmeta/version,
  …/api/npexplorer/roiconnectivity?dataset=manc:v1.2.1 (2026-09-22); https://neuprint.janelia.org/public/neuprintuserguide.pdf (2026-09-22).
- https://connectome-neuprint.github.io/neuprint-python/docs/ and …/docs/changelog.html (2026-09-22);
  https://raw.githubusercontent.com/connectome-neuprint/neuprint-python/master/neuprint/queries/{connectivity,synapsecriteria}.py (2026-09-22);
  https://raw.githubusercontent.com/connectome-neuprint/neuPrint/master/pgmspecs.md (2026-09-22).
- https://github.com/janelia-flyem/flyem-snapshot (README + clone, HEAD 2218084291111da470ff1c2d74d9d74cddcce65c, 2026-09-22).
- https://github.com/natverse/malevnc (NEWS.md + full clone, HEAD d24c795, tags v0.2.0…v0.4.0, 2026-09-22).
- GCS JSON API: `https://storage.googleapis.com/storage/v1/b/flyem-manc-exports/o`,
  `https://storage.googleapis.com/storage/v1/b/manc-seg-v1p2/o` (with prefix/delimiter listings and per-object metadata,
  2026-09-22); object reads `https://storage.googleapis.com/flyem-manc-exports/v1.0/{neuprint_manc_v1.0/README,
  manc-traced-adjacencies-v1.0/README}`, `https://storage.googleapis.com/manc-seg-v1p2/{manc-v1.2.1-neuprint-layers.json,
  manc-v1.2.3-neuprint-layers.json, manc-seg-v1.2/info, manc-seg-v1.2/segment_properties/info,
  manc-seg-v1.2/segment_properties_v1.2.1/info, manc-seg-v1.2/segment_properties_v1.2.3/info,
  manc-seg-v1.2/segment_properties_v1.2.3/{type_property,combined_properties}/info}` (2026-09-22/23);
  `https://storage.googleapis.com/flyem-vnc-roi-d5f392696f7a48e27f49fa1a9db5ee3b/roi-202208/{info,segment_properties/info}` (2026-09-22).
- Local read-only copies (same objects as the bucket, section 3.6): `$DATA/raw/manc/v1.0/neuprint_manc_v1.0/neuprint_manc_v1.0_ftr/Neuprint_Meta_manc_v1.ftr`,
  `.../Neuprint_Neurons_manc_v1.ftr`, `$DATA/raw/manc/v1.0/manc-v1.0-neuron-properties.feather` (2026-09-22/23).
