"""THE ONE PLACE for every name that must never appear in a Phase 4 room (early review F, F-M1; research/phase4/LEAKAGE_POLICY.md).

ORCHESTRATOR ONLY. This directory (scripts/p4config/) is on the room builder's refusal list and is never copied into any room, so the
code that enters rooms (the guard, the builder, the audit tool, the launcher, brainir_causal.systems) carries no dataset, organism,
circuit, paper or earlier-artefact names: they load them from here at run time.

Consumers: scripts/p4agent/guard_hook.py, scripts/p4agent/audit_transcripts.py, scripts/p4agent/launch.py,
scripts/make_phase4_cleanroom.py, the Phase 4 guard / room tests. Load with `load()` (by file path; works under `python -I`).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------------------------------------------- word lists
#: dataset, organism, circuit, paper and anatomy words (lower case; matched case-insensitively and after removing regex escapes)
DATASET_WORDS = (
    "dng100", "pugliese", "manc", "malecns", "male-cns", "male cns", "neuprint", "flywire", "hemibrain", "drosophila", "bdn2",
    "walking cpg", "walkingcpg", "ventral nerve cord",
)

#: earlier-phase and Phase 4 room directory names (the guard refuses every room but the agent's own)
ROOMS = (
    "BrainIR_p2clean", "BrainIR_p3audit", "BrainIR_p3audit_test", "BrainIR_p3bench", "BrainIR_p3clean", "BrainIR_p3guardtest",
    "BrainIR_p3lit", "BrainIR_p3postreview", "BrainIR_p3regen", "BrainIR_p3review", "BrainIR_p3reviewG", "BrainIR_p3run",
    "BrainIR_p3smoke", "BrainIR_p4clean", "BrainIR_p4bench", "BrainIR_p4lit", "BrainIR_p4review", "BrainIR_p4audit", "BrainIR_p4run",
    "BrainIR_p4guardtest", "BrainIR_p4canary", "BrainIR_p4canary_outside", "BrainIR_p4bench_test",
)

# ---------------------------------------------------------------------------------------------------------------- repository paths
PATHS = {
    "public_bundle": "benchmarks/dng100/public_blind",           # the public tier-A bundle of the real systems
    "phase1_oracle_json": "benchmarks/dng100/oracle/oracle.json",
    "phase1_tier_a_ids": "benchmarks/dng100/oracle/tier_a_ids",
    "p3_package": "phase3/src/brainir_state",                    # the earlier phase's package (frozen baseline sources)
    "p3_method_lock": "research/phase3/METHOD_LOCK.json",
    "p3_bench_lock": "benchmarks/state_discovery_v1/BENCHMARK_LOCK.json",
}

#: FROZEN files copied verbatim into rooms and hash-verified against an earlier lock (they cannot be edited): the ONLY scanner hits
#: they may carry (room path -> exact hit strings, lower case). Tracked in research/phase4/LEAKAGE_POLICY.md section 4.
FROZEN_CONTENT_EXEMPT = {
    "baselines/brainir_state_v1/brainir_state/evaluate.py": ("research/phase3",),   # one docstring path; imported by the locked v1
}

# ---------------------------------------------------------------------------------------------------------------- room builder
#: repository-relative source paths that may NEVER enter any Phase 4 room (research/phase4/ROOM_ALLOWLISTS.md, "Refusal list")
REFUSE = (
    r"(^|/)PHASE\d+_REPORT\.md$", r"(^|/)goal\d*\.md$", r"^research/LOG\.md$", r"^research/phase2/", r"^research/phase3/",
    r"^research/phase4/PLAN\.md$", r"^research/phase4/reviews/", r"^research/phase4/HIDDEN_EVALUATIONS\.md$",
    r"^research/literature/", r"^benchmarks/dng100_walking_cpg/", r"^benchmarks/dng100/(oracle|evaluator|baselines)/",
    r"^benchmarks/state_discovery_v1/hidden/", r"^benchmarks/causal_state_v1/hidden/", r"^data/phase3/", r"^data/phase4/hidden/",
    r"^data/phase4/suites/(val|conf)[^/]*/(.*/)?truth/", r"(^|/)MEMORY\.md$", r"(^|/)\.claude/", r"^CLAUDE\.md$",
    r"(^|/)\.modal\.toml$", r"(^|/)\.credentials", r"(^|/)SALT(_REVEAL)?[^/]*$", r"(^|/)salt(\.json|\.txt|\.bin)?$",
    r"^scripts/p4config/", r"(^|/)canary[^/]*\.txt$",
)
#: file NAMES forbidden anywhere in a room (agent files included)
FILE_NAMES = (
    r"phase\d_report", r"hidden_eval", r"blind_eval", r"(^|/)oracle", r"salt_reveal", r"real_hidden", r"real_name_map",
    r"systems_internal", r"salt_commitment", r"(^|/)goal\d+\.md$", r"dng100", r"benchmark_lock", r"method_lock", r"state_discovery_v1",
    r"(^|/)memory\.md$", r"postlock_", r"report_working",
)
#: TEXT forbidden anywhere in a room (every text file, agent files included): dataset / circuit / paper names, earlier answer phrases
#: and artefact names, absolute paths of the main repository or of earlier-phase rooms
CONTENT = (
    r"inhibitory slot", r"e-core recall", r"excitatory core recall", r"published core", r"published circuit", r"published answer",
    r"\bE1/E2\b", r"I1\|I2", r"core_contralateral", r"answer key", r"dng100", r"pugliese", r"\bmanc\b", r"male-?cns", r"male\s+cns",
    r"\bneuprint\b", r"\bflywire\b", r"\bhemibrain\b", r"\bdrosophila\b", r"\bbdn2\b", r"walking\s*cpg", r"ventral\s+nerve\s+cord",
    r"hidden_eval_log", r"phase[0-3]_report", r"hidden_evaluations\.md", r"salt_reveal", r"real_hidden", r"brainir-p3-(eval|fit|devdata)",
    r"postlock_[a-z]", r"report_working", r"state_discovery_v1[\\/]+hidden", r"research[\\/]+phase[23]\b", r"data[\\/]+phase3\b",
    r"(?<![\w$])[a-z]:[\\/]+dev[\\/]+brainir(?=[\\/'\"\s)]|$)", r"(?<![\w$])/[a-z]/dev/brainir(?=[\\/'\"\s)]|$)", r"brainir_p[23][a-z_]*",
)

#: literal anchors for BINARY sources (npz / zip / tar members and raw bytes, lower-cased, also with NUL bytes removed so UTF-16 /
#: UTF-32 strings count): at least 6 characters each, so random bytes never match (a 4-letter word would, about once per 4 GB)
BINARY_ANCHORS = (
    "dng100", "pugliese", "malecns", "male-cns", "male_cns", "male cns", "neuprint", "flywire", "hemibrain", "drosophila",
    "walkingcpg", "walking cpg", "walking_cpg", "walking-cpg", "ventral nerve cord", "ventral_nerve_cord",
    "phase0_report", "phase1_report", "phase2_report", "phase3_report", "hidden_eval", "blind_eval", "salt_reveal", "real_hidden",
    "brainir-p3-", "postlock_", "report_working", "state_discovery_v1", "research/phase2", "research/phase3", "research\\phase2",
    "research\\phase3", "data/phase3", "data\\phase3", "brainir_p2", "brainir_p3", "dev/brainir/", "dev\\brainir\\",
    "core_contralateral", "inhibitory slot", "excitatory core recall", "e-core recall", "published circuit", "published answer",
    "real_name_map", "systems_internal",
)

# ---------------------------------------------------------------------------------------------------------------- command guard
#: text patterns the PreToolUse guard refuses in any tool input (the room-specific ones are added by the guard itself)
GUARD_TEXT = (
    r"\.claude[\\/]", r"\.credentials", r"\.modal\.toml", r"\.claude\.json",
    r"phase\d_report", r"hidden_eval", r"blind_eval", r"dng100", r"[\\/]oracle", r"salt_reveal", r"real_hidden",
    r"state_discovery_v1[\\/]+hidden", r"brainir-p3-(eval|fit|devdata)", r"research[\\/]+phase[23]\b", r"data[\\/]+phase3\b",
    r"\bgoal\d+\.md\b", r"disableallhooks", r"\benv\s+-(i|u)\b", r"\bunset\b", r"remove-item\s+env:",
)
#: web queries naming the benchmark's circuit, organism, datasets or source paper (literature agents only have web access)
WEB_BLOCK = (
    r"dng100", r"\bbdn2\b", r"pugliese", r"walking\s*cpg", r"walking\s+central\s+pattern", r"malecns", r"male\s*cns", r"\bmanc\b",
    r"neuprint", r"flywire", r"ventral\s+nerve\s+cord", r"drosophila", r"\bfly\b.*\b(leg|walking|motor)", r"descending\s+neuron",
    r"front[-\s]?leg", r"hemibrain", r"connectome",
)

# ---------------------------------------------------------------------------------------------------------------- test vectors
#: name-bearing inputs of the Phase 4 guard / builder tests (the tests carry no names themselves)
TEST_VECTORS = {
    "answer_files": ("PHASE2_REPORT.md", "PHASE3_REPORT.md", "research/phase3/HIDDEN_EVALUATIONS.md", "goal3.md",
                     "benchmarks/state_discovery_v1/hidden/network_map.json", "benchmarks/dng100/oracle/oracle.json",
                     "research/phase4/HIDDEN_EVALUATIONS.md"),
    "other_rooms": ("BrainIR_p3postreview", "BrainIR_p2clean", "BrainIR_p3review", "BrainIR_p4bench"),
    "web_queries": ("DNg100 walking circuit", "Pugliese connectome model", "MANC ventral nerve cord", "Drosophila leg motor neurons"),
    "text_hits": ("dng100",),                                    # words the guard refuses in any tool input
}

# ---------------------------------------------------------------------------------------------------------------- transcript audit
AUDIT_NAMES = (
    r"dng100", r"\bbdn2\b", r"pugliese", r"walking\s*cpg", r"malecns", r"male[-\s]?cns", r"\bmanc\b", r"neuprint", r"flywire",
    r"drosophila", r"phase[0-3]_report", r"hidden_eval", r"blind_eval", r"oracle\.json", r"tier_a_ids", r"goal[1-5]\.md",
)
AUDIT_PATHS = (
    r"dev[\\/]+brainir(?!_p4)", r"brainir_p[23]\w*", r"\.claude[\\/]+projects[\\/]+c--dev-brainir[\\/]", r"\.credentials",
    r"\.modal\.toml",
)
#: keys of the earlier answer file that the transcript audit reads (orchestrator side only)
ORACLE_KEYS = {"core_extra": "core_contralateral_copies"}
#: earlier answer-bearing artefact CLASSES (reported as class -> count, never the matched text)
ANSWER_CLASSES = {
    "PHASE2_REPORT": r"phase2_report", "PHASE3_REPORT": r"phase3_report", "HIDDEN_EVAL_LOG": r"hidden_eval_log",
    "HIDDEN_EVALUATIONS": r"hidden_evaluations", "SALT_REVEAL": r"salt_reveal", "level_c": r"level_c", "real_hidden": r"real_hidden",
    "brainir-p3-eval": r"brainir-p3-eval", "POSTLOCK_": r"postlock_", "REPORT_WORKING": r"report_working",
    "state_discovery_v1/hidden": r"state_discovery_v1[\\/]+hidden",
}


def load():
    """This module as a namespace (import by file path, so it works under `python -I` and from any script)."""
    import sys
    return sys.modules[__name__]
