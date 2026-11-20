# Labeler transcript audit

| session | transcripts | tool calls | fetches | searches | BREACHES | blocked attempts | model/score phrases |
|---|---|---|---|---|---|---|---|
| adjudication-dedicated | 1 | 49 | 36 | 2 | 0 | 0 | 53 |
| adjudication-general | 1 | 94 | 76 | 1 | 0 | 1 | 4 |
| pass1-atlas | 1 | 40 | 22 | 1 | 3 | 0 | 8 |
| pass1-catalogue | 1 | 86 | 58 | 6 | 0 | 1 | 8 |
| pass1-escape_landing | 1 | 101 | 52 | 19 | 0 | 1 | 11 |
| pass1-grooming | 1 | 102 | 61 | 7 | 0 | 1 | 9 |
| pass1-pugliese_dedicated | 1 | 70 | 46 | 2 | 0 | 0 | 27 |
| pass1-recent_broad | 1 | 153 | 71 | 38 | 0 | 0 | 19 |
| pass1-steering | 1 | 99 | 52 | 10 | 0 | 1 | 9 |
| pass1-walking_stopping | 1 | 49 | 30 | 2 | 1 | 0 | 14 |
| pass2-catalogue | 1 | 54 | 36 | 1 | 0 | 0 | 4 |
| pass2-escape_landing | 1 | 84 | 56 | 2 | 0 | 2 | 5 |
| pass2-grooming | 1 | 49 | 29 | 2 | 0 | 1 | 5 |
| pass2-pugliese_dedicated | 1 | 76 | 52 | 1 | 0 | 0 | 159 |
| pass2-recent_broad | 1 | 183 | 133 | 7 | 0 | 0 | 13 |
| pass2-steering | 1 | 80 | 54 | 4 | 0 | 0 | 4 |
| search-search_behaviour | 1 | 141 | 92 | 6 | 0 | 1 | 4 |
| search-search_names | 1 | 83 | 52 | 6 | 1 | 0 | 4 |

Breaches (exclude the session's records, PREREG 6):

- pass1-atlas: {"kind": "file_outside_room", "tool": "Read", "path": "$HOME/.claude/projects/-HOME-ledger-rooms-run1-pass1-atlas/63e89206-9241-40c3-9a2c-8b636422025e/tool-results/webfetch-1795194372791-l00hpx.jpg"}
- pass1-atlas: {"kind": "file_outside_room", "tool": "Read", "path": "$HOME/.claude/projects/-HOME-ledger-rooms-run1-pass1-atlas/63e89206-9241-40c3-9a2c-8b636422025e/tool-results/webfetch-1795194382561-umak2w.jpg"}
- pass1-atlas: {"kind": "file_outside_room", "tool": "Read", "path": "$HOME/.claude/projects/-HOME-ledger-rooms-run1-pass1-atlas/63e89206-9241-40c3-9a2c-8b636422025e/tool-results/webfetch-1795194581978-pqp5y5.jpg"}
- pass1-walking_stopping: {"kind": "file_outside_room", "tool": "Read", "path": "$HOME/.claude/projects/-HOME-ledger-rooms-run1-pass1-walking-stopping/215cd3af-6451-42ad-b1a8-cc72a63aae38/tool-results/webfetch-1795194813944-1dzt3m.jpg"}
- search-search_names: {"kind": "file_outside_room", "tool": "Read", "path": "$HOME/.claude/projects/-HOME-ledger-rooms-run1-search-search-names/6f0f0102-a539-4ca4-83ea-f03e4a0b9cb9/tool-results/webfetch-1795193538733-qca666.jpg"}

Blocked attempts (denied by the tool permissions; not breaches):

- adjudication-general: {"kind": "file_outside_room", "tool": "Read", "path": "$HOME/.claude/projects/-HOME-ledger-rooms-run1-adjudication-general/9beacdb8-63d7-42fb-9d8c-2c8563bcfb65/tool-results/webfetch-1795198197584-ltpsma.jpg"}
- pass1-catalogue: {"kind": "file_outside_room", "tool": "Read", "path": "$HOME/.claude/projects/-HOME-ledger-rooms-run1-pass1-catalogue/2ffa0f3d-4237-4482-a6df-4bb13ae712c9/tool-results/webfetch-1795194865043-c07rdr.pdf"}
- pass1-escape_landing: {"kind": "file_outside_room", "tool": "Read", "path": "$HOME/.claude/projects/-HOME-ledger-rooms-run1-pass1-escape-landing/bf6132c1-e75c-41fb-b228-8a5f11d67c22/tool-results/webfetch-1795194422896-n1jnhr.pdf"}
- pass1-grooming: {"kind": "file_outside_room", "tool": "Read", "path": "$HOME/.claude/projects/-HOME-ledger-rooms-run1-pass1-grooming/594d9aab-ae9f-49b4-94d1-ea6941a12dfc/tool-results/webfetch-1795195517976-9am5ce.pdf"}
- pass1-steering: {"kind": "file_outside_room", "tool": "Read", "path": "$HOME/.claude/projects/-HOME-ledger-rooms-run1-pass1-steering/fc9261ab-b6d4-4e4e-8ef4-b5f68cd49824/tool-results/webfetch-1795193845795-baacl4.pdf"}
- pass2-escape_landing: {"kind": "file_outside_room", "tool": "Read", "path": "$HOME/.claude/projects/-HOME-ledger-rooms-run1-pass2-escape-landing/a978a34a-f395-4340-b9c0-e225af9ba6f3/tool-results/webfetch-1795196557223-w3dmjy.pdf"}
- pass2-escape_landing: {"kind": "file_outside_room", "tool": "Read", "path": "$HOME/.claude/projects/-HOME-ledger-rooms-run1-pass2-escape-landing/a978a34a-f395-4340-b9c0-e225af9ba6f3/tool-results/webfetch-1795197088904-l6khos.pdf"}
- pass2-grooming: {"kind": "file_outside_room", "tool": "Read", "path": "$HOME/.claude/projects/-HOME-ledger-rooms-run1-pass2-grooming/9b89dc07-bfec-42fb-ad2c-e2c1f92b722b/tool-results/toolu_018ZioAZbY7MRVcaMvH3ATtE.txt"}
- search-search_behaviour: {"kind": "file_outside_room", "tool": "Read", "path": "$HOME/.claude/projects/-HOME-ledger-rooms-run1-search-search-behaviour/4ed3d2b7-b410-48d6-97b5-9d7c2604b9b8/tool-results/webfetch-1795195272076-wk48n2.pdf"}

Model/simulation phrases seen in tool results (reported only; records are excluded only through the readers' own saw_simulation_score flag or a breach):

- adjudication-dedicated: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- adjudication-dedicated: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- adjudication-dedicated: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- adjudication-dedicated: 'effector,stimulation,sibling_index,n_siblings,field,reading_A,reading_B\n2\tpass1-pugliese_dedicated:p1-pugliese_dedicated-0001,10.1101/2025.09.12.675944,"bioRxiv v1 Fig.'
- adjudication-dedicated: 'ibling_index,n_siblings,field,reading_A,reading_B\n2\tpass1-pugliese_dedicated:p1-pugliese_dedicated-0001,10.1101/2025.09.12.675944,"bioRxiv v1 Fig. 2h-k (v2 Fig. 2h-j, E'
- adjudication-dedicated: 'n per 15 s trial",1,1,effect_on_walking,"""speeds""","""not_assessed"""\n3\tpass1-pugliese_dedicated:p1-pugliese_dedicated-0002,10.1101/2025.09.12.675944,bioRxiv v1 Fig. '
- adjudication-dedicated: 'effect_on_walking,"""speeds""","""not_assessed"""\n3\tpass1-pugliese_dedicated:p1-pugliese_dedicated-0002,10.1101/2025.09.12.675944,bioRxiv v1 Fig. 4c-e (v2 Fig. 5c-e); S'
- adjudication-dedicated: 'stim-off trials per fly",1,1,line_specificity,"""unknown""","""clean"""\n4\tpass1-pugliese_dedicated:p1-pugliese_dedicated-0003,10.64898/2026.04.29.721658,"bioRxiv v2 Fig'
- adjudication-general: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- adjudication-general: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- adjudication-general: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- adjudication-general: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- pass1-atlas: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- pass1-atlas: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- pass1-atlas: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- pass1-atlas: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- pass1-atlas: 'ote\n2\tCande et al. (eLife) optogenetic DN behaviour atlas,2018,atlas,systematic activation screen,leads from memory: verify title and DOI\n3\tNamiki et al. (eLife) DN organisation'
- pass1-atlas: 'argeted,verify\n16\tvon Reyn et al. escape,2017,escape_landing,targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted'
- pass1-atlas: 'targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted,dedicated session only\n18\tSapkal et al. (bioRxiv) doi 10.648'
- pass1-atlas: 'ted session only\n18\tSapkal et al. (bioRxiv) doi 10.64898/2026.04.29.721658,2026,pugliese_dedicated,targeted,dedicated session only\n19\tCheong et al. (MANC DNs and naming'
- pass1-catalogue: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- pass1-catalogue: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- pass1-catalogue: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- pass1-catalogue: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- pass1-catalogue: 'ote\n2\tCande et al. (eLife) optogenetic DN behaviour atlas,2018,atlas,systematic activation screen,leads from memory: verify title and DOI\n3\tNamiki et al. (eLife) DN organisation'
- pass1-catalogue: 'argeted,verify\n16\tvon Reyn et al. escape,2017,escape_landing,targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted'
- pass1-catalogue: 'targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted,dedicated session only\n18\tSapkal et al. (bioRxiv) doi 10.648'
- pass1-catalogue: 'ted session only\n18\tSapkal et al. (bioRxiv) doi 10.64898/2026.04.29.721658,2026,pugliese_dedicated,targeted,dedicated session only\n19\tCheong et al. (MANC DNs and naming'
- pass1-escape_landing: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- pass1-escape_landing: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- pass1-escape_landing: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- pass1-escape_landing: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- pass1-escape_landing: 'ote\n2\tCande et al. (eLife) optogenetic DN behaviour atlas,2018,atlas,systematic activation screen,leads from memory: verify title and DOI\n3\tNamiki et al. (eLife) DN organisation'
- pass1-escape_landing: 'argeted,verify\n16\tvon Reyn et al. escape,2017,escape_landing,targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted'
- pass1-escape_landing: 'targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted,dedicated session only\n18\tSapkal et al. (bioRxiv) doi 10.648'
- pass1-escape_landing: 'ted session only\n18\tSapkal et al. (bioRxiv) doi 10.64898/2026.04.29.721658,2026,pugliese_dedicated,targeted,dedicated session only\n19\tCheong et al. (MANC DNs and naming'
- pass1-grooming: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- pass1-grooming: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- pass1-grooming: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- pass1-grooming: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- pass1-grooming: 'ote\n2\tCande et al. (eLife) optogenetic DN behaviour atlas,2018,atlas,systematic activation screen,leads from memory: verify title and DOI\n3\tNamiki et al. (eLife) DN organisation'
- pass1-grooming: 'argeted,verify\n16\tvon Reyn et al. escape,2017,escape_landing,targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted'
- pass1-grooming: 'targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted,dedicated session only\n18\tSapkal et al. (bioRxiv) doi 10.648'
- pass1-grooming: 'ted session only\n18\tSapkal et al. (bioRxiv) doi 10.64898/2026.04.29.721658,2026,pugliese_dedicated,targeted,dedicated session only\n19\tCheong et al. (MANC DNs and naming'
- pass1-pugliese_dedicated: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- pass1-pugliese_dedicated: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- pass1-pugliese_dedicated: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- pass1-pugliese_dedicated: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- pass1-pugliese_dedicated: 'ote\n2\tCande et al. (eLife) optogenetic DN behaviour atlas,2018,atlas,systematic activation screen,leads from memory: verify title and DOI\n3\tNamiki et al. (eLife) DN organisation'
- pass1-pugliese_dedicated: 'argeted,verify\n16\tvon Reyn et al. escape,2017,escape_landing,targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted'
- pass1-pugliese_dedicated: 'targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted,dedicated session only\n18\tSapkal et al. (bioRxiv) doi 10.648'
- pass1-pugliese_dedicated: 'ted session only\n18\tSapkal et al. (bioRxiv) doi 10.64898/2026.04.29.721658,2026,pugliese_dedicated,targeted,dedicated session only\n19\tCheong et al. (MANC DNs and naming'
- pass1-recent_broad: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- pass1-recent_broad: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- pass1-recent_broad: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- pass1-recent_broad: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- pass1-recent_broad: 'ote\n2\tCande et al. (eLife) optogenetic DN behaviour atlas,2018,atlas,systematic activation screen,leads from memory: verify title and DOI\n3\tNamiki et al. (eLife) DN organisation'
- pass1-recent_broad: 'argeted,verify\n16\tvon Reyn et al. escape,2017,escape_landing,targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted'
- pass1-recent_broad: 'targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted,dedicated session only\n18\tSapkal et al. (bioRxiv) doi 10.648'
- pass1-recent_broad: 'ted session only\n18\tSapkal et al. (bioRxiv) doi 10.64898/2026.04.29.721658,2026,pugliese_dedicated,targeted,dedicated session only\n19\tCheong et al. (MANC DNs and naming'
- pass1-steering: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- pass1-steering: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- pass1-steering: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- pass1-steering: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- pass1-steering: 'ote\n2\tCande et al. (eLife) optogenetic DN behaviour atlas,2018,atlas,systematic activation screen,leads from memory: verify title and DOI\n3\tNamiki et al. (eLife) DN organisation'
- pass1-steering: 'argeted,verify\n16\tvon Reyn et al. escape,2017,escape_landing,targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted'
- pass1-steering: 'targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted,dedicated session only\n18\tSapkal et al. (bioRxiv) doi 10.648'
- pass1-steering: 'ted session only\n18\tSapkal et al. (bioRxiv) doi 10.64898/2026.04.29.721658,2026,pugliese_dedicated,targeted,dedicated session only\n19\tCheong et al. (MANC DNs and naming'
- pass1-walking_stopping: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- pass1-walking_stopping: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- pass1-walking_stopping: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- pass1-walking_stopping: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- pass1-walking_stopping: 'ote\n2\tCande et al. (eLife) optogenetic DN behaviour atlas,2018,atlas,systematic activation screen,leads from memory: verify title and DOI\n3\tNamiki et al. (eLife) DN organisation'
- pass1-walking_stopping: 'argeted,verify\n16\tvon Reyn et al. escape,2017,escape_landing,targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted'
- pass1-walking_stopping: 'targeted,verify\n17\tPugliese et al. (Nature) doi 10.1038/s41586-026-11195-y,2026,pugliese_dedicated,targeted,dedicated session only\n18\tSapkal et al. (bioRxiv) doi 10.648'
- pass1-walking_stopping: 'ted session only\n18\tSapkal et al. (bioRxiv) doi 10.64898/2026.04.29.721658,2026,pugliese_dedicated,targeted,dedicated session only\n19\tCheong et al. (MANC DNs and naming'
- pass2-catalogue: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- pass2-catalogue: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- pass2-catalogue: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- pass2-catalogue: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- pass2-escape_landing: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- pass2-escape_landing: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- pass2-escape_landing: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- pass2-escape_landing: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- pass2-escape_landing: 'D or a PMC URL.\n\n**Main findings:**\n- **The landing neurons:** A DN optogenetic activation screen identified two neurons, DNp07 and DNp10, whose activation caused tethered flies'
- pass2-grooming: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- pass2-grooming: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- pass2-grooming: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- pass2-grooming: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- pass2-grooming: '":"https://www.biorxiv.org/content/10.1101/2023.09.11.557103v1.full"},{"title":"Connectome simulations identify a central pattern generator circuit for fly walking","url":"https://w'
- pass2-pugliese_dedicated: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- pass2-pugliese_dedicated: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- pass2-pugliese_dedicated: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- pass2-pugliese_dedicated: 'name_in_paper,preparation,effector,stimulation,sibling_index,n_siblings\n2\tpass1-pugliese_dedicated:p1-pugliese_dedicated-0001,10.1101/2025.09.12.675944,"bioRxiv v1 Fig.'
- pass2-pugliese_dedicated: 'ion,effector,stimulation,sibling_index,n_siblings\n2\tpass1-pugliese_dedicated:p1-pugliese_dedicated-0001,10.1101/2025.09.12.675944,"bioRxiv v1 Fig. 2h-k (v2 Fig. 2h-j, E'
- pass2-pugliese_dedicated: 'e; 0.03, 0.09, 0.33 mW/mm2 (strongest 0.33); 5 s on per 15 s trial",1,1\n3\tpass1-pugliese_dedicated:p1-pugliese_dedicated-0002,10.1101/2025.09.12.675944,bioRxiv v1 Fig. '
- pass2-pugliese_dedicated: '/mm2 (strongest 0.33); 5 s on per 15 s trial",1,1\n3\tpass1-pugliese_dedicated:p1-pugliese_dedicated-0002,10.1101/2025.09.12.675944,bioRxiv v1 Fig. 4c-e (v2 Fig. 5c-e); S'
- pass2-pugliese_dedicated: 'sity for DNb08 not stated; 8 stim-on and 4 stim-off trials per fly",1,1\n4\tpass1-pugliese_dedicated:p1-pugliese_dedicated-0003,10.64898/2026.04.29.721658,"bioRxiv v2 Fig'
- pass2-recent_broad: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- pass2-recent_broad: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- pass2-recent_broad: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- pass2-recent_broad: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- pass2-recent_broad: 'e neurons are called RRNs. The team found them through an extensive optogenetic activation screen of sparse genetic driver lines. Activating one driver line produced especially '
- pass2-recent_broad: ':"https://www.biorxiv.org/content/10.64898/2026.05.03.722293v1.full"},{"title":"Connectome simulations identify a central pattern generator circuit for fly walking","url":"https://w'
- pass2-recent_broad: 'osophila","url":"https://www.nature.com/articles/s41586-024-07854-7"},{"title":"Connectome simulations identify a central pattern generator ...","url":"https://faculty.washington.ed'
- pass2-recent_broad: 'ntral pattern generator ...","url":"https://faculty.washington.edu/tuthill/docs/Pugliese_cpg_2025.pdf"},{"title":"Connectome simulations identify a central pattern ..."'
- pass2-steering: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- pass2-steering: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- pass2-steering: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- pass2-steering: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- search-search_behaviour: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- search-search_behaviour: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- search-search_behaviour: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- search-search_behaviour: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
- search-search_names: 'for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive wal'
- search-search_names: 'al model, simulation, connectome-simulation result, "rhythmicity score",\n108\t  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub o'
- search-search_names: ' work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026\n110\t  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025'
- search-search_names: '1\t{\n2\t "$schema": "https://json-schema.org/draft/2020-12/schema",\n3\t "title": "BrainIR ledger label record v1",\n4\t "type": "object",\n5\t "required": [\n6\t  "access",\n7\t'
