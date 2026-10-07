# Transcript audit triage, 2026-09-28 (pre-freeze; orchestrator)

Audit: `scripts/p4agent/audit_transcripts.py --out research/phase4/transcript_audit.json` over every Phase 4 agent stream in
C:\Dev\BrainIR_p4audit\agents (author, reviewers E / F / H / T of every round, the literature agent, canaries, smoke). The run
included the first minutes of review_T_r3c. The audit is re-run at the freeze.

Pre-freeze criterion (prefreeze_check.py `transcripts`): 0 outputs with answer tokens and 0 forbidden-path inputs in every stream
except the canaries, which probe forbidden paths on purpose. **Met**: answer tokens 0 in every stream. The only forbidden-path input is
in `canary`, one of its deliberate probes.

Every other flag, read in context by the orchestrator (the matched text itself stays out of this file):

| stream | flag | what it was | verdict |
|---|---|---|---|
| review_F_early | 4 outputs with names; artefact classes HIDDEN_EVALUATIONS 3, POSTLOCK_ 2, state_discovery_v1/hidden 1, level_c 1 | F read the ROUND-1 room builder's refusal regexes, the manifest's refusal list and the audit script's class table: file-name PATTERNS only, no content of any answer-bearing file | benign; the cause is early review F's F-M1, fixed in round 1 (every name now lives in scripts/p4config/names.py, which never enters a room) |
| review_H_early, review_H_r3 | artefact class level_c (1 each) | the docstring of p4modal/gate.py named two Phase 3 execution scripts (the host-gate rule's origin) | benign (script names, no results); the docstring was cleaned before this audit |
| review_F_r2 | 1 forbidden-name input, 1 output | F's deliberate leakage grep over the room (the isolation review's job); the output match was a placeholder path in a test fixture's config | benign |
| p4lit | 3 forbidden-name inputs | the literature agent grepped its OWN notes for organism names while classifying papers; one organism name is on the audit's list | benign |
| every stream | "tool calls the current guard would deny" | re-evaluation of EVERY recorded call under today's guard: calls that were blocked at the time (e.g. all host `python3` calls, which the guard refused then too; their results read "BLOCKED by the ... room guard"), plus calls allowed under earlier rules and tightened since: the room-local `./sbx` spelling (62 of the author's 86; the outside copy has been mandatory since early review F, F-B4), the work-area layout (`reviews/<X>/...`, `.tmp/<agent>`), shell constructs (arithmetic, sed built from runtime data) and heredoc-parsing artefacts ("host command 'eof'") | no leak: the allowed ones ran in the Docker sandbox or wrote into the agent's own work area |

Conclusion: no answer content reached any Phase 4 agent; nothing to relay or quarantine.
