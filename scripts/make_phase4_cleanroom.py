"""Build / check / audit / rebuild the Phase 4 rooms from explicit allowlists (goal5 sections 5-6; research/phase4/ROOM_ALLOWLISTS.md).

    uv run --project phase4 python scripts/make_phase4_cleanroom.py --room bench --build             # C:\\Dev\\BrainIR_p4bench
    uv run --project phase4 python scripts/make_phase4_cleanroom.py --room clean --build             # C:\\Dev\\BrainIR_p4clean
    uv run --project phase4 python scripts/make_phase4_cleanroom.py --room review --build            # C:\\Dev\\BrainIR_p4review
    ... --room R --check                  # verify the room against its manifest (missing / modified / unexpected / forbidden / links /
                                          # planted files / OS protection)
    ... --room R --check FILE             # may this repository file enter room R? (refusal list, names, content scan)
    ... --room R --audit                  # --check + unmanifested-file list + full content scan of agent files -> room_audits/
    ... --room R --sync "<reason>"        # copy changed allowlisted files (work areas untouched), record the sync, rescan
    ... --room R --destroy-and-rebuild    # delete the room (work areas are lost) and build again

Every file that enters a room has a manifest record {path, source, destination, sha256, reason, classification, bytes}; the full
manifest is written OUTSIDE the room (research/phase4/CLEANROOM_MANIFEST.json for the clean room, CLEANROOM_MANIFEST_<room>.json for
the others); the in-room copy holds paths, hashes and sizes only (early review F, F-B5). Sources are refused when they match the
REFUSAL list or when their name or text matches the content scanner (applied to the text as it is AND after removing regex escapes,
F-M1). Every name the refusal list and the scanner need lives in ONE orchestrator config that never enters a room
(scripts/p4config/names.py; F-M1): this file carries none.

Isolation placed by the builder (early review F, F-B4 / F-M3):
- `sbx` (the Docker sandbox wrapper) at the room root and an identical copy OUTSIDE the room (C:\\Dev\\BrainIR_p4audit\\sbx_bin\\<room>\\
  sbx, put first on PATH by scripts/p4agent/launch.py). Agents run only the outside copy (bare `sbx`); the guard refuses every path
  spelling of sbx and checks the outside copy's hash on every call. The container mounts the room READ-ONLY and binds only the work
  areas read-write (free rooms: every top-level entry that is not allowlisted); /room/.tmp is a private tmpfs with only the agent's
  own .tmp/<agent> bound in; no bytecode is written into the room (PYTHONDONTWRITEBYTECODE, PYTHONPYCACHEPREFIX=/tmp/pyc).
- OS-level immutability: every allowlisted file, every directory that holds only allowlisted content, the room root of rooms with
  declared work areas, the outside sbx copy and its seccomp profile carry an NTFS deny ACE for Everyone (write, append, attributes,
  delete, delete-child, change permissions, take ownership; scripts/p4agent/ntfs_protect.py). The builder lifts it around --sync /
  --destroy-and-rebuild and --check verifies it.
- `.claude/` (empty), `CLAUDE.local.md` and `.mcp.json` placeholders (read-only), so no code can plant Claude settings, hooks or
  instructions that the host session would load; the scan reports every Claude control file, sitecustomize / usercustomize module,
  *.pth file and *.pyc file anywhere else in the room.
- C:\\Dev\\BrainIR_p4audit\\protected_<room>.json: the protected paths, work areas, the sbx hash and the outside manifest (the guard
  and the launcher read it).
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REAL_ROOT = ROOT                                    # tests monkeypatch ROOT; the config and the ACL module stay in the real repo
AUDIT = Path(r"C:\Dev\BrainIR_p4audit")
P4 = ROOT / "research" / "phase4"
IMAGE_JSON = ROOT / "docker" / "p4sandbox" / "image.json"
SECCOMP_SRC = ROOT / "docker" / "p4sandbox" / "seccomp_nolinks.json"
SBX_TEMPLATE = ROOT / "scripts" / "p4agent" / "sbx_template.sh"
#: the machine-wide sandbox slot shared by every room's wrapper (the machine owner's rule, 2026-09-27/28: ONE agent sandbox at a
#: time on the development PC, started only with at least SBX_MIN_FREE_GB free; tests: phase4/tests/test_sbx_machine_slot.py)
SBX_SLOT_DIR = AUDIT / "sbx_slot"
SBX_MAX_SLOTS = 1
SBX_MIN_FREE_GB = 4
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".jsonl", ".toml", ".cfg", ".yaml", ".yml", ".csv", ".sh", ".ini", ".rst", ".tsv"}
MAX_SCAN_BYTES = 20_000_000


def _load_names():
    """The names config (orchestrator only). The review room ships a PLACEHOLDER config next to its copy of this script."""
    here = Path(__file__).resolve().parent
    for cand in (here / "p4config" / "names.py", here.parent / "p4config" / "names.py"):
        if cand.exists():
            spec = importlib.util.spec_from_file_location("p4config_names_builder", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("the names config scripts/p4config/names.py (orchestrator only) is missing")


_N = _load_names()


def _load_acl():
    try:
        spec = importlib.util.spec_from_file_location("p4_ntfs_protect", Path(__file__).resolve().parent / "p4agent" / "ntfs_protect.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except (ImportError, OSError, FileNotFoundError):             # not Windows / module absent: OS protection unavailable
        return None


ACL = _load_acl()

# ------------------------------------------------------------------------------------------------ refusal list and scanner
# repository-relative source paths that may NEVER enter any Phase 4 room (research/phase4/ROOM_ALLOWLISTS.md, "Refusal list")
REFUSE = [re.compile(p, re.IGNORECASE) for p in _N.REFUSE]
# file NAMES forbidden anywhere in a room (agent files included)
NAMES_ALWAYS = re.compile("(?i)(" + "|".join(_N.FILE_NAMES) + ")")
# file names forbidden among the ALLOWLISTED files of the method rooms (orchestrator-side modules; the review room's extra/ is exempt)
# orchestrator-side module names never allowed in a method room (`accounting`, the public cost ledger that refs / loop import, is a
# method-room module: review F round 3b, NF-2)
NAMES_ORCHESTRATOR = re.compile(r"(?i)(^|/)(realsim|realgen|simservice|synthadapter|synthsim|suites|suite_eval|evaluate_truth|calibrate|"
                                r"runguard|runner|tournament|feedback|p4modal|store|systems)(\.py|/)|(^|/)calibration\.json$")
# TEXT forbidden anywhere in a room
CONTENT_ALWAYS = re.compile("(?i)(" + "|".join(_N.CONTENT) + ")")
WORD_PATTERNS = [re.compile(r"(?<![a-z0-9])" + re.sub(r"[\s-]+", r"[\\s_-]*", re.escape(w).replace(r"\ ", " ")) + r"(?![a-z0-9])")
                 for w in _N.DATASET_WORDS]

GENERIC_CLAUDE_MD = """# BrainIR clean development room (causal state models trained with interventions)

You develop methods that learn low-dimensional CAUSAL state models of simulated neural systems with interventions as part of the
learning problem: an encoder from the observed microstate x (and input u) to a latent z, controlled latent dynamics, an explicit
intervention read-in, a readout, a native lift (latent change -> physical interventions) and an experiment designer. Start with
docs/METHOD_DEV_CONTRACT.md, then docs/PROTOCOL.md (the frozen evaluation), docs/PROTOCOL_V2.md, docs/API.md and
docs/METHODS_REVIEW.md.

Rules (enforced technically; do not try to get around them):
1. Work only inside this directory. Nothing outside it is reachable.
2. Run ALL code through the Docker sandbox with the bare command `sbx`: `sbx python ...`, `sbx pytest -q tests/methods`. Path
   spellings of the wrapper (./sbx, ...) and host interpreters (python, uv, pip, node, ...) are refused. Inside the sandbox this room
   is mounted read-only at /room; only the work areas below and your own .tmp/<your name>/ are writable; there is no network.
3. Simulation only through the budgeted service: `from brainir_causal.simclient import SimClient` (public policy only).
4. Datasets: data/ (public development data; no ground truth).
5. Work areas (the only writable places), each developer in its OWN subdirectory (<prefix> = your prefix, which is also your
   sandbox scratch name): src/brainir_causal/methods/<prefix>/ (your package: __init__.py + modules), tests/methods/<prefix>/,
   runs/<prefix>/, notes/<prefix>/, and your private simq/<prefix>/ (service queue) and .tmp/<prefix>/. Other developers'
   subdirectories are readable but never writable (enforced).
6. Methods must be generic: no special cases for particular systems, no hard-coded latent dimension, no per-system lookup tables.
7. Never use the readout y as encoder input; never let an encoder see future samples.
8. Heavy or GPU experiments: the remote runner (docs/REMOTE_RUNNER.md). No web access.
"""

REVIEW_README = """# extra/ (orchestrator-side code for reviewers)

Orchestrator-side modules and tools that method developers never see: the real-system engine and system definitions (public parts),
the trajectory store, the simulation service, the synthetic-generator adapter and suite builder, truth-level evaluation, calibration,
the fit sandbox and runner, the tournament driver and feedback, the Modal backend, the synthetic generator with its tests, the room
builder, the agent isolation stack and the remote runner with its job guard. No salt, no validation or confirmation truth data, no
hidden data.

Also: extra/tests/ (the orchestrator's full test suite, incl. the engine's bit-identity and restart tests), extra/results/ (the
Modal simulation smoke test, the CPU / GPU equivalence results, the GPU benchmark, the isolation canary test, the calibration
targets from public real data). The real-system internal records (network, keep sets, hidden targets) are NOT here.

The isolation stack loads every forbidden name from ONE orchestrator config that never enters a room. extra/scripts/p4config/names.py
here is a PLACEHOLDER with dummy words, so that the guard, the builder and the audit tool can be run. Lines of orchestrator code that
still name a dataset / circuit / earlier artefact are replaced by `<redacted line>` (fallback; the manifest counts them).

EARLY ROUND (before the benchmark freeze): the synthetic generator and the development tier may not exist yet; data/toy_example holds
the public part of two small toy systems (the adapter's test systems) as example data. They arrive later by a logged sync.
"""

PLACEHOLDER_NAMES = '''"""PLACEHOLDER names config for the review room (the real one never enters a room). Same structure, dummy words."""
DATASET_WORDS = ("forbiddenword-one", "forbiddenword-two")
ROOMS = ("BrainIR_pXroomA", "BrainIR_pXroomB")
PATHS = {"public_bundle": "benchmarks/placeholder/public_blind", "phase1_oracle_json": "benchmarks/placeholder/oracle.json",
         "phase1_tier_a_ids": "benchmarks/placeholder/tier_a_ids", "p3_package": "placeholder/src/earlier_package",
         "p3_method_lock": "placeholder/METHOD_LOCK.json", "p3_bench_lock": "placeholder/BENCHMARK_LOCK.json"}
FROZEN_CONTENT_EXEMPT = {}
REFUSE = (r"^secret/", r"(^|/)FORBIDDEN_REPORT\\.md$")
FILE_NAMES = (r"forbiddenword", r"hidden_thing")
CONTENT = (r"forbiddenword-one", r"forbiddenword-two")
GUARD_TEXT = (r"forbiddenword", r"\\.credentials")
WEB_BLOCK = (r"forbiddenword",)
AUDIT_NAMES = (r"forbiddenword",)
AUDIT_PATHS = (r"brainir_pX\\w*",)
ORACLE_KEYS = {"core_extra": "placeholder_key"}
ANSWER_CLASSES = {"PLACEHOLDER": r"hidden_thing"}
TEST_VECTORS = {"answer_files": ("secret/FORBIDDEN_REPORT.md",), "other_rooms": ("BrainIR_pXroomA",),
                "web_queries": ("forbiddenword-one circuit",), "text_hits": ("forbiddenword",)}


def load():
    import sys
    return sys.modules[__name__]
'''


# ------------------------------------------------------------------------------------------------ room specifications
@dataclass
class Item:
    source: str | None          # repository-relative source path (None = generated)
    path: str                   # room-relative destination
    reason: str
    classification: str
    required: bool = True
    content: str | None = None  # generated content
    verify: dict | None = None  # {"lock": "<repo-relative lock json>", "key": "<json key>"}: sha256 must match a locked hash
    redact: bool = False        # review-room copies of orchestrator code: lines with a scanner hit replaced (fallback, F-M1)


@dataclass
class RoomSpec:
    name: str
    dest: Path
    manifest: Path
    items: list[Item]
    work_areas: tuple[str, ...] | None       # None = free workspace (every non-allowlisted top-level entry is the agent's)
    rw_nested: tuple[str, ...] = ()          # work areas beneath read-only allowlisted directories
    names_orchestrator_exempt: tuple[str, ...] = ()
    max_cpus: int = 4
    max_mem_gb: int = 12
    dirs: tuple[str, ...] = ()               # empty directories to create
    agent_areas: tuple[str, ...] = (".tmp",)  # per-agent areas: each agent reads and writes only <area>/<agent> (host guard, sandbox)
    owned_areas: tuple[str, ...] = ()        # shared areas owned per agent: every agent READS all of <area>/ but WRITES only
                                             # <area>/<agent>/ (review F round 2, N-M2; host guard + sandbox mounts)
    seed_files: tuple[str, ...] = ()         # empty work-area files created when missing (free rooms: the sandbox cannot create
                                             # top-level entries); not manifested, never protected
    notes: list[str] = field(default_factory=list)


def _glob(pattern: str) -> list[Path]:
    return sorted(p for p in ROOT.glob(pattern) if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")


TRANSIENT = (".pyc", ".tmp", ".part", ".tar", ".sync_tmp", ".lock", ".partial")


def _tree(src_dir: str, dst_dir: str, reason: str, cls: str, required: bool = True, pattern: str = "**/*") -> list[Item]:
    """Every regular file below src_dir, except caches, hidden files and transient build artefacts (a tree item never copies an
    in-progress tar / tmp file of a builder that is still writing the tree)."""
    base = ROOT / src_dir
    files = sorted(p for p in base.glob(pattern) if p.is_file() and "__pycache__" not in p.parts
                   and not any(part.startswith(".") for part in p.relative_to(base).parts)
                   and not p.name.lower().endswith(TRANSIENT)) if base.exists() else []
    if not files:
        return [Item(f"{src_dir}/{pattern}", f"{dst_dir}/", reason, cls, required)]   # recorded as missing when required
    return [Item(p.relative_to(ROOT).as_posix(), f"{dst_dir}/{p.relative_to(base).as_posix()}", reason, cls) for p in files]


def _isolation_items(claude_md_source: str | None, claude_md_text: str | None) -> list[Item]:
    items = []
    if claude_md_source:
        items.append(Item(claude_md_source, "CLAUDE.md", "room rules", "contract"))
    else:
        items.append(Item(None, "CLAUDE.md", "room rules (generic)", "generated", content=claude_md_text))
    items += [
        Item(None, "CLAUDE.local.md", "placeholder: exists so that the sandbox mounts it read-only (no planted instructions)", "generated",
             content="<!-- intentionally empty (read-only placeholder) -->\n"),
        Item(None, ".mcp.json", "placeholder: no MCP servers (read-only in the sandbox)", "generated", content='{"mcpServers": {}}\n'),
        Item(None, ".claude/README.md", "placeholder: the room's Claude settings directory is read-only for agents", "generated",
             content="Read-only. Agent sessions are configured by the orchestrator's launcher, never from this directory.\n"),
    ]
    return items


P3_PKG = _N.PATHS["p3_package"]                    # the earlier phase's package and its two locks (paths from the names config)
P3_METHOD_LOCK = _N.PATHS["p3_method_lock"]
P3_BENCH_LOCK = _N.PATHS["p3_bench_lock"]
P3_SUPPORT = ("__init__", "api", "data", "evaluate")   # what the frozen v1 imports (brainir_causal.frozen_v1.V1_SOURCES; closure checked)
P3_V1_METHOD_FILES = ("__init__", "brainir_state_v1", "ks_core", "ks_sindy", "ks_abstain", "ks_share")


def _p3_baseline_items() -> list[Item]:
    items = []
    for m in P3_SUPPORT:
        src = f"{P3_PKG}/{m}.py"
        items.append(Item(src, f"baselines/brainir_state_v1/brainir_state/{m}.py", "earlier public module imported by the locked method",
                          "baseline-frozen", verify={"lock": P3_BENCH_LOCK, "key": "files"}))
    for m in P3_V1_METHOD_FILES:          # ONLY the locked v1 and the modules it imports (not the other earlier candidates)
        rel = f"{P3_PKG}/methods/{m}.py"
        items.append(Item(rel, f"baselines/brainir_state_v1/brainir_state/methods/{m}.py", "locked earlier method (frozen baseline)",
                          "baseline-frozen", verify={"lock": P3_METHOD_LOCK, "key": "source_sha256"}))
    return items


CLEAN_MODULES = ("__init__", "api", "protocol", "families", "data", "evalio", "fresh", "stats", "evaluate", "evaluate_mediation",
                 "evaluate_micro", "evaluate_lift", "evaluate_stability", "evaluate_transfer", "verdict", "refs", "harness", "loop",
                 "designers", "capacity", "calibstats", "equiv", "simclient", "select", "frozen_v1",
                 # refs / loop import the cost ledger; designers import the public-policy sampler, which lives in the public module
                 # `sampling` (moved out of the orchestrator module `suites`, which never enters a method room; review H round 3, NEW-3)
                 "accounting", "sampling")
REVIEW_EXTRA_MODULES = ("realsim", "systems", "store", "simservice", "synthadapter", "evaluate_truth", "calibrate", "runguard",
                        "runner", "feedback", "worker", "isolation", "simdocker", "suites")
REVIEW_DEV_SUBSET = 10          # systems of the public development data copied into the review room (sorted directory names)
REVIEW_EXTRA_SCRIPTS = ("tournament", "calibrate", "modal_p4", "freeze_benchmark_p4", "make_public_docs", "build_on_modal", "method_lock_p4",
                        "frozen_v1_smoke", "strip_row_field", "verify_real_build", "calibration_check_real", "probe_isolation", "plan_synthetic",
                        "smoke_isolation_modal", "gpu_benchmark", "smoke_pack_modal", "smoke_stage_modal")

CLEAN_PYPROJECT = """[project]
name = "brainir-p4clean"
version = "0.1.0"
description = "Clean development room: public modules of brainir_causal, the frozen earlier baseline, method work areas."
requires-python = ">=3.12,<3.13"
# The code runs in the Docker sandbox image (sbx), which pins this stack exactly.
dependencies = ["numpy==2.5.3", "scipy==1.18.1", "pandas==3.0.6", "pyarrow==25.0.1", "pydantic==2.13.5", "scikit-learn==1.9.1",
                "threadpoolctl==3.7.0", "torch==2.14.0"]
"""


def room_specs() -> dict[str, RoomSpec]:
    bench_items = _isolation_items("research/phase4/contracts/p4bench_CLAUDE.md", None) + [
        Item("research/phase4/contracts/SYNTHETIC_BENCHMARK_CONTRACT.md", "docs/SYNTHETIC_BENCHMARK_CONTRACT.md", "the author's contract", "contract"),
        Item("benchmarks/causal_state_v1/PROTOCOL.md", "docs/PROTOCOL.md", "benchmark protocol (how the systems are used)", "benchmark-public"),
        Item("benchmarks/causal_state_v1/docs/PROTOCOL_V2.md", "docs/PROTOCOL_V2.md", "protocol format, families, system records", "benchmark-public"),
        Item("research/phase4/CALIBRATION_TARGETS.md", "docs/CALIBRATION_TARGETS.md", "generic calibration targets from public data", "public-derived"),
        Item("phase4/src/brainir_causal/protocol.py", "ref/protocol.py", "reference protocol validation", "generic-public"),
        Item("phase4/src/brainir_causal/families.py", "ref/families.py", "reference family classification", "generic-public"),
        Item("phase4/src/brainir_causal/calibstats.py", "ref/calibstats.py", "reference calibration statistics", "generic-public"),
        Item("benchmarks/causal_state_v1/public/calibration_targets.json", "ref/calibration_targets.json", "calibration target values", "public-derived"),
    ]
    clean_items = _isolation_items(None, GENERIC_CLAUDE_MD) + [
        Item(".python-version", ".python-version", "interpreter version", "generic-public"),
        Item(None, "pyproject.toml", "standalone project description (pinned stack; no path dependency)", "generated", content=CLEAN_PYPROJECT),
        Item(None, "src/brainir_causal/methods/__init__.py", "empty package for the developers' methods", "generated",
             content='"""Method implementations (clean-room work area)."""\n'),
    ]
    for m in CLEAN_MODULES:
        clean_items.append(Item(f"phase4/src/brainir_causal/{m}.py", f"src/brainir_causal/{m}.py", "public Phase 4 module", "generic-public"))
    clean_items += _p3_baseline_items()
    clean_items += [
        Item("benchmarks/causal_state_v1/PROTOCOL.md", "docs/PROTOCOL.md", "the frozen public evaluation protocol", "benchmark-public"),
        Item("benchmarks/causal_state_v1/docs/PROTOCOL_V2.md", "docs/PROTOCOL_V2.md", "protocol format and families", "benchmark-public"),
        Item("benchmarks/causal_state_v1/docs/API.md", "docs/API.md", "method / model / designer API", "benchmark-public"),
        Item("research/phase4/contracts/METHOD_DEV_CONTRACT.md", "docs/METHOD_DEV_CONTRACT.md", "development contract", "contract"),
        Item("research/phase4/METHODS_REVIEW.md", "docs/METHODS_REVIEW.md", "methods-only literature review", "methods-literature"),
        Item("research/phase4/REFERENCES.md", "docs/REFERENCES.md", "references of the literature review", "methods-literature"),
        Item("research/phase4/review_contracts/remote_runner_notes.md", "docs/REMOTE_RUNNER.md", "remote runner instructions", "generic-public",
             required=False),
        Item("research/phase4/review_contracts/remote_run_client.py", "tools/remote_run.py", "remote runner client (writes request files "
             "into the developer's own runs/<prefix>/_remote/requests)", "generic-public", required=False),
        Item("benchmarks/causal_state_v1/public/systems_public.json", "data/systems_public.json", "merged public system records", "benchmark-public"),
        Item("benchmarks/causal_state_v1/public/tolerances.json", "data/tolerances.json", "calibrated tolerances (values only)", "benchmark-public"),
        Item("benchmarks/causal_state_v1/public/calibration_targets.json", "data/calibration_targets.json", "calibration targets", "public-derived"),
    ]
    clean_items += _tree("data/phase4/suites/dev/public", "data/synthetic_dev", "synthetic development data (no truth)", "benchmark-public")
    clean_items += _tree("data/phase4/real/real_public/public", "data/real_public", "Phase 4 public real data", "benchmark-public")
    clean_items += _tree("phase4/tests/public", "tests", "public module tests (run without orchestrator-side modules)", "generic-public",
                         required=False)
    # the review room is built BEFORE the freeze for the early reviews (LEAKAGE_POLICY.md section 5): sources that exist only later
    # (the dev tier, the generator, the merged public records, the calibrated tolerances) are optional there and arrive by --sync
    optional_in_review = ("data/phase4/suites/dev/public", "data/phase4/real/real_public/public", "benchmarks/causal_state_v1/public/systems_public.json",
                          "benchmarks/causal_state_v1/public/tolerances.json")
    review_items = []
    for it in clean_items:
        if it.path == "CLAUDE.md":
            continue
        if it.source and any(it.source.startswith(s) for s in optional_in_review):
            it = Item(it.source, it.path, it.reason, it.classification, False, it.content, it.verify)
        review_items.append(it)
    # the review room holds the public development data of REVIEW_DEV_SUBSET systems only (disk; reviewers build more systems with
    # the generator in extra/ when they need them); the clean room holds all of them
    dev_dirs = sorted({it.path.split("/")[2] for it in review_items if it.path.startswith("data/synthetic_dev/") and it.path.count("/") >= 3})
    keep_dev = set(dev_dirs[:REVIEW_DEV_SUBSET])
    review_items = [it for it in review_items if not (it.path.startswith("data/synthetic_dev/") and it.path.count("/") >= 3
                                                      and it.path.split("/")[2] not in keep_dev)]
    review_items.append(Item("research/phase4/review_contracts/p4review_CLAUDE.md", "CLAUDE.md", "review room rules", "contract"))
    review_items += _tree("data/phase4/suites/toy/public", "data/toy_example", "public part of the two toy systems (example data for "
                          "the early reviews; no truth)", "benchmark-public", required=False)
    for m in REVIEW_EXTRA_MODULES:
        review_items.append(Item(f"phase4/src/brainir_causal/{m}.py", f"extra/brainir_causal/{m}.py", "orchestrator-side module (review)",
                                 "orchestrator-code", redact=True))
    review_items += _tree("phase4/src/brainir_causal/p4modal", "extra/brainir_causal/p4modal", "Modal backend (review)", "orchestrator-code")
    review_items += _tree("benchmarks/causal_state_v1/generator", "extra/generator", "synthetic generator and its tests (review)",
                          "orchestrator-code", required=False)
    review_items += [
        Item("benchmarks/causal_state_v1/public/calibration.json", "extra/calibration.json", "calibration outputs (review)", "orchestrator-code",
             required=False),
        Item("scripts/make_phase4_cleanroom.py", "extra/scripts/make_phase4_cleanroom.py", "room builder (review)", "orchestrator-code"),
        Item("scripts/p4/devrun4.py", "extra/scripts/devrun4.py", "remote runner (review)", "orchestrator-code"),
        Item("scripts/p4/devrun4_site/sitecustomize.py", "extra/scripts/devrun4_site/sitecustomize.py", "remote runner job guard (review)",
             "orchestrator-code"),
        *[Item(f"scripts/p4/{x}.py", f"extra/scripts/{x}.py", "orchestrator script (review)", "orchestrator-code", required=False)
          for x in REVIEW_EXTRA_SCRIPTS],
        Item(None, "extra/README.md", "what extra/ holds", "generated", content=REVIEW_README),
        Item(None, "extra/scripts/p4config/names.py", "PLACEHOLDER names config (dummy words; the real one never enters a room)",
             "generated", content=PLACEHOLDER_NAMES),
    ]
    review_items += _tree("scripts/p4agent", "extra/scripts/p4agent", "agent isolation stack (review)", "orchestrator-code",
                          pattern="**/*.py")
    review_items.append(Item("scripts/p4agent/sbx_template.sh", "extra/scripts/p4agent/sbx_template.sh", "sandbox wrapper template (review)",
                             "orchestrator-code"))
    # the orchestrator's tests are OPTIONAL items of the review room: a test the content scanner refuses (e.g. one that names the
    # artefacts a guard protects) is left out and reported, instead of aborting the sync
    review_items += [dataclasses.replace(it, required=False) for it in _tree("phase4/tests", "extra/tests",
                                                                              "the orchestrator's test suite (review)", "orchestrator-code",
                                                                              pattern="*.py")]
    for src, dst in (("research/phase4/modal_smoke_sim.json", "extra/results/modal_smoke_sim.json"),
                     ("research/phase4/GPU_BENCHMARK.equiv.json", "extra/results/cpu_gpu_equivalence.json"),
                     ("research/phase4/GPU_BENCHMARK.md", "extra/results/GPU_BENCHMARK.md"),
                     ("research/phase4/CANARY_TEST.md", "extra/results/CANARY_TEST.md"),
                     ("research/phase4/CALIBRATION_TARGETS.md", "extra/results/CALIBRATION_TARGETS.md"),
                     ("research/phase4/REAL_DATA_BUILD.md", "extra/results/REAL_DATA_BUILD.md"),
                     ("research/phase4/devrun4_isolation_smoke.json", "extra/results/devrun4_isolation_smoke.json"),
                     ("research/phase4/isolation_smoke_modal.json", "extra/results/isolation_smoke_modal.json"),
                     ("research/phase4/isolation_probe_modal.json", "extra/results/isolation_probe_modal.json"),
                     # packed / staged isolated classes (LEAKAGE_POLICY 2.13; review F round 3b, NF-4): results where they exist
                     ("research/phase4/pack_smoke_modal.json", "extra/results/pack_smoke_modal.json"),
                     ("research/phase4/stage_smoke_modal.json", "extra/results/stage_smoke_modal.json"),
                     ("research/phase4/LEVEL_B_EXECUTION.md", "extra/LEVEL_B_EXECUTION.md"),
                     ("research/phase4/GENERATOR_DELIVERY_SHA256.txt", "extra/results/GENERATOR_DELIVERY_SHA256.txt"),
                     # the final dev tier's criterion 11 and the active-design MDE (review E's last pre-freeze check)
                     ("research/phase4/CALIBRATION_CHECK_dev.json", "extra/results/CALIBRATION_CHECK_dev.json"),
                     ("research/phase4/ACTIVE_MDE.md", "extra/results/ACTIVE_MDE.md"),
                     ("research/phase4/ACTIVE_MDE.json", "extra/results/ACTIVE_MDE.json"),
                     ("research/phase4/EVAL_ARCHITECTURE.md", "extra/EVAL_ARCHITECTURE.md"),
                     ("research/phase4/LEAKAGE_POLICY.md", "extra/LEAKAGE_POLICY.md"),
                     ("research/phase4/contracts/SYNTHETIC_BENCHMARK_CONTRACT.md", "extra/SYNTHETIC_BENCHMARK_CONTRACT.md")):
        review_items.append(Item(src, dst, "evidence for the reviewers", "orchestrator-code", required=False))
    for it in review_items:                 # every orchestrator-side copy is a REDACTED copy (fallback; normally nothing is redacted)
        if it.path.startswith("extra/") and it.source:
            it.redact = True
    # work areas (early review F, F-M3): the room root is read-only in the sandbox and for the host guard; only these are writable.
    # `simq/` and `.tmp/` are per-agent: an agent sees and writes only simq/<agent>/ and .tmp/<agent>/. The shared areas are owned
    # per agent (review F round 2, N-M2): every agent reads them but writes only <area>/<agent>/.
    return {
        "bench": RoomSpec("bench", Path(r"C:\Dev\BrainIR_p4bench"), P4 / "CLEANROOM_MANIFEST_bench.json", bench_items, None,
                          dirs=(".tmp",), seed_files=("calibration_report.json",)),
        "clean": RoomSpec("clean", Path(r"C:\Dev\BrainIR_p4clean"), P4 / "CLEANROOM_MANIFEST.json", clean_items,
                          ("src/brainir_causal/methods/", "tests/methods/", "runs/", "notes/", "simq/", ".tmp/"),
                          rw_nested=("src/brainir_causal/methods", "tests/methods"), agent_areas=(".tmp", "simq"),
                          owned_areas=("src/brainir_causal/methods", "tests/methods", "runs", "notes"),
                          dirs=("runs", "notes", "tests/methods", "simq", ".tmp")),
        "review": RoomSpec("review", Path(r"C:\Dev\BrainIR_p4review"), P4 / "CLEANROOM_MANIFEST_review.json", review_items,
                           ("reviews/", "runs/", "notes/", ".tmp/"), names_orchestrator_exempt=("extra/",),
                           owned_areas=("reviews", "runs", "notes"), dirs=("reviews", "runs", "notes", ".tmp")),
    }


# ------------------------------------------------------------------------------------------------ helpers
def _sha_bytes(b: bytes, text: bool) -> str:
    return hashlib.sha256(b.replace(b"\r\n", b"\n") if text else b).hexdigest()


def _sha(p: Path) -> str:
    return _sha_bytes(p.read_bytes(), p.suffix.lower() in TEXT_SUFFIXES or p.name in ("sbx", "CLAUDE.md"))


def _is_text(p: Path) -> bool:
    return p.suffix.lower() in TEXT_SUFFIXES or p.name in ("sbx",) or (p.suffix == "" and p.stat().st_size < 2_000_000)


def refused(rel_source: str) -> str | None:
    """Why a repository-relative source may not enter any room (None = not on the refusal list)."""
    rel = rel_source.replace("\\", "/")
    for i, pat in enumerate(REFUSE):
        if pat.search(rel):
            return f"refusal list (rule {i})"
    return None


# FROZEN files copied verbatim and hash-verified against an earlier lock (they may not be edited): the ONLY content hits they may carry
# (room path -> exact hit strings, lower case; from the names config). Every other scanner class still applies to them. Tracked in
# LEAKAGE_POLICY.md section 4.
FROZEN_CONTENT_EXEMPT = {k: {s.lower() for s in v} for k, v in getattr(_N, "FROZEN_CONTENT_EXEMPT", {}).items()}


def normalise(text: str) -> str:
    """Text with regex escapes removed, so a regex SOURCE (e.g. a word between two word-boundary escapes, or with an optional
    separator class) reads like the word it matches (early review F, F-M1)."""
    t = re.sub(r"\\[bBAZ]", "", text)
    t = re.sub(r"\\[sS](\{\d*,?\d*\}|[*+?])?", " ", t)
    t = re.sub(r"\[\\s_?-?\]|\[-\\s_?\]|\[\\s\]|\[-_\\s\]|\[_\\s-\]", " ", t)
    t = re.sub(r"(?<=\w)[-_ ]\?", " ", t)
    t = t.replace("\\", "")
    return t


def scan_text(text: str, room_path: str | None = None) -> str | None:
    """The first forbidden hit of the text (as it is, then with regex escapes removed, then the word list), or None."""
    allowed = FROZEN_CONTENT_EXEMPT.get(room_path or "", set())
    for cand in (text, normalise(text)):
        for m in CONTENT_ALWAYS.finditer(cand):
            if m.group(0).lower() not in allowed:
                return m.group(0)
    low = normalise(text).lower()
    for rx in WORD_PATTERNS:
        m = rx.search(low)
        if m:
            return m.group(0)
    return None


REDACTED = "<redacted line>"


def redacted_text(src: Path) -> tuple[str, int]:
    """Fallback redaction for the review room's orchestrator-side copies: every LINE with a scanner hit (as it is or after removing
    regex escapes, or a listed word) is replaced by REDACTED (keeping its indentation); returns (text, number of lines replaced).
    Line-level, so no fragment of a name and no regex source survives; no source hash is ever recorded inside a room."""
    text = src.read_bytes().decode("utf-8", errors="ignore").replace("\r\n", "\n")
    out, n = [], 0
    for line in text.split("\n"):
        if scan_text(line):
            out.append(line[: len(line) - len(line.lstrip())] + REDACTED)
            n += 1
        else:
            out.append(line)
    return "\n".join(out), n


def _materialise_file(it: Item, src: Path, dst: Path) -> int:
    """Copy (or redact-copy) src to dst; returns the number of redacted lines."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".sync_tmp")
    if it.redact and src.suffix.lower() in TEXT_SUFFIXES:
        text, n = redacted_text(src)
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, dst)
        return n
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)
    return 0


def check_source(src: Path, room_path: str, spec: RoomSpec, redact: bool = False) -> str | None:
    """None if this repository file may enter the room at room_path, else the reason."""
    try:
        rel = src.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return "source outside the repository"
    why = refused(rel)
    if why:
        return why
    if NAMES_ALWAYS.search(room_path) or NAMES_ALWAYS.search(rel):
        return f"forbidden name: {room_path}"
    if spec.name in ("bench", "clean") and NAMES_ORCHESTRATOR.search(room_path):
        return f"orchestrator-side module name in a method room: {room_path}"
    if not redact and src.suffix.lower() in TEXT_SUFFIXES and src.stat().st_size < MAX_SCAN_BYTES:
        hit = scan_text(src.read_text(encoding="utf-8", errors="ignore"), room_path)
        if hit:
            return f"forbidden content {hit!r}"
    elif src.suffix.lower() not in TEXT_SUFFIXES:
        hit = scan_binary(src)
        if hit:
            return f"forbidden content in a binary file {hit!r}"
    return None


BINARY_MIN_HIT = 6          # random bytes spell a given 4-letter word in ~1 of 4e9 positions; 6+ characters: never in practice
# literal anchors (names config; a placeholder config falls back to its dataset words), lower case, at least BINARY_MIN_HIT long
BINARY_ANCHORS = [a.lower().encode("latin-1") for a in (getattr(_N, "BINARY_ANCHORS", None) or _N.DATASET_WORDS)
                  if len(a) >= BINARY_MIN_HIT]


def _binary_hit(blob: bytes) -> str | None:
    """The first anchor found in the lower-cased bytes, or in the same bytes with NULs removed (UTF-16 / UTF-32 strings; numpy stores
    str arrays as UTF-32). Plain substring search: about 100 times faster than the text scanner on binary data."""
    low = blob.lower()
    stripped = low.replace(b"\x00", b"")
    for a in BINARY_ANCHORS:
        if a in low or a in stripped:
            return a.decode("latin-1")
    return None


def scan_binary(src: Path, cap: int = 64_000_000) -> str | None:
    """A forbidden name inside a binary file: zip / npz members (decompressed) and tar members with their names, else the raw bytes.
    Only the names config's literal anchors of at least BINARY_MIN_HIT characters count."""
    try:
        if zipfile.is_zipfile(src):
            with zipfile.ZipFile(src) as z:
                for info in z.infolist():
                    hit = _binary_hit(info.filename.encode("utf-8", "ignore"))
                    if hit is None and info.file_size <= cap:
                        hit = _binary_hit(z.read(info))
                    if hit:
                        return hit
            return None
        if tarfile.is_tarfile(src):
            with tarfile.open(src) as tf:
                for m in tf.getmembers():
                    hit = _binary_hit(m.name.encode("utf-8", "ignore"))
                    if hit is None and m.isfile() and m.size <= cap:
                        fh = tf.extractfile(m)
                        hit = _binary_hit(fh.read()) if fh else None
                    if hit:
                        return hit
            return None
        with open(src, "rb") as fh:
            return _binary_hit(fh.read(cap))
    except (OSError, zipfile.BadZipFile, tarfile.TarError, EOFError) as e:
        return f"unreadable ({type(e).__name__})"


def _posix(p: Path) -> str:
    s = str(p).replace("\\", "/")
    m = re.match(r"^([A-Za-z]):/(.*)$", s)
    return f"/{m.group(1).lower()}/{m.group(2)}" if m else s


def _docker_exe() -> str:
    exe = shutil.which("docker") or r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    p = Path(exe)
    if p.suffix == "":
        p = p.with_suffix(".exe")
    return _posix(p)


def _image() -> dict:
    return json.loads(IMAGE_JSON.read_text(encoding="utf-8"))


def verify_image(expect_id: str) -> str | None:
    try:
        out = subprocess.run(["docker", "image", "inspect", expect_id, "--format", "{{.Id}}"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"docker unavailable ({type(e).__name__})"
    if out.returncode != 0 or out.stdout.strip() != expect_id:
        return f"sandbox image {expect_id} not present locally (build docker/p4sandbox under a NEW tag and record it in image.json)"
    return None


def ro_paths(spec: RoomSpec, paths: list[str]) -> list[str]:
    """Top-level room entries that hold only allowlisted / generated files (read-only inside the sandbox; with the read-only room
    mount this is informational, and free rooms use it to decide which top-level entries are NOT work areas)."""
    tops: dict[str, list[str]] = {}
    for p in paths:
        tops.setdefault(p.split("/", 1)[0], []).append(p)
    out = []
    for top, members in sorted(tops.items()):
        works = [w.rstrip("/") for w in (spec.work_areas or ()) if w.split("/", 1)[0] == top]
        if not works:
            out.append(top)
            continue
        if any(w == top for w in works):
            continue                                      # the whole top-level entry is a work area
        seconds = sorted({"/".join(m.split("/")[:2]) for m in members})
        for s in seconds:
            if not any(w == s or w.startswith(s + "/") for w in works):
                out.append(s)
            else:
                deeper = sorted({"/".join(m.split("/")[:3]) for m in members if m.startswith(s + "/")})
                out += [d for d in deeper if not any(w == d or w.startswith(d + "/") for w in works)]
    return sorted(set(out))


def rw_areas(spec: RoomSpec) -> list[str]:
    """The read-write binds of a room with declared work areas (the per-agent and the per-agent-owned areas are bound per agent)."""
    per_agent = set(spec.agent_areas) | set(spec.owned_areas)
    return sorted({w.rstrip("/") for w in (spec.work_areas or ()) if w.rstrip("/") not in per_agent})


def token_dir(dest: Path) -> Path:
    """Where the launcher writes each agent's simulation token (outside the room; the sandbox wrapper forwards it into the container)."""
    return AUDIT / "simservice" / dest.name / "agent_tokens"


CONTROL_TOPS = ("sbx", "CLEANROOM_MANIFEST.json", "CLAUDE.md", "CLAUDE.local.md", ".mcp.json", ".claude")


def ro_tops(paths: list[str]) -> list[str]:
    """Top-level entries that belong to the orchestrator (allowlisted / generated files and the control files)."""
    return sorted({p.split("/", 1)[0] for p in paths} | set(CONTROL_TOPS))


def render_sbx(spec: RoomSpec, dest: Path, paths: list[str], seccomp_win: str) -> str:
    img = _image()
    t = SBX_TEMPLATE.read_text(encoding="utf-8")

    def q(xs):
        return " ".join("'" + x.replace("'", "") + "'" for x in xs)
    if spec.work_areas is None:
        doc = "every top-level entry that is not the orchestrator's"
    else:
        doc = ", ".join(rw_areas(spec) + [f"{a}/<agent> (shared)" for a in spec.owned_areas] +
                        [f"{a}/<agent> (private)" for a in spec.agent_areas])
    rep = {"@ROOM_POSIX@": _posix(dest), "@ROOM_MOUNT@": str(dest).replace("\\", "/"), "@ROOM_NAME@": dest.name,
           "@IMAGE_ID@": img["id"], "@DOCKER@": _docker_exe(), "@SECCOMP@": seccomp_win, "@MAX_CPUS@": str(spec.max_cpus),
           "@MAX_MEM_GB@": str(spec.max_mem_gb), "@RW_PATHS@": q(rw_areas(spec)), "@AGENT_AREAS@": q(spec.agent_areas),
           "@OWNED_AREAS@": q(spec.owned_areas), "@TOKEN_DIR@": _posix(token_dir(dest)),
           "@RO_TOPS@": q(ro_tops(paths)), "@FREE_ROOM@": "1" if spec.work_areas is None else "0", "@WORK_DOC@": doc,
           "@SLOT_DIR@": _posix(SBX_SLOT_DIR), "@MAX_SLOTS@": str(SBX_MAX_SLOTS), "@MIN_FREE_GB@": str(SBX_MIN_FREE_GB)}
    for k, v in rep.items():
        t = t.replace(k, v)
    left = re.findall(r"@[A-Z_]+@", t)
    if left:
        raise SystemExit(f"sbx template placeholders left: {left}")
    return t


def install_sbx(spec: RoomSpec, dest: Path, paths: list[str]) -> dict:
    """Write the wrapper at the room root and the identical outside copy (+ seccomp profile) under AUDIT/sbx_bin/<room>/."""
    bindir = AUDIT / "sbx_bin" / dest.name
    bindir.mkdir(parents=True, exist_ok=True)
    sec = bindir / "seccomp_nolinks.json"
    shutil.copyfile(SECCOMP_SRC, sec)
    text = render_sbx(spec, dest, paths, str(sec).replace("\\", "/"))
    for p in (dest / "sbx", bindir / "sbx"):
        p.write_text(text, encoding="utf-8", newline="\n")
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return {"sbx_sha256": _sha(dest / "sbx"), "outside_copy": "$AUDIT/sbx_bin/" + dest.name + "/sbx",
            "seccomp_sha256": _sha(sec), "image": _image()["id"]}


def write_protected(spec: RoomSpec, dest: Path, manifest: dict) -> Path:
    """C:\\Dev\\BrainIR_p4audit\\protected_<room>.json (outside the room): what the guard and the launcher need."""
    prot = {"room": dest.name, "generated_utc": manifest.get("created_utc"),
            "files": sorted(e["path"] for e in manifest["files"]) + ["CLEANROOM_MANIFEST.json"],
            "read_only_dirs": manifest["sandbox"]["ro_paths"], "ro_tops": ro_tops([e["path"] for e in manifest["files"]]),
            "rw_nested": list(spec.rw_nested),
            "work_areas": [w.rstrip("/") for w in spec.work_areas] if spec.work_areas is not None else None,
            "agent_areas": list(spec.agent_areas), "owned_areas": list(spec.owned_areas),
            "sbx_sha256": next((e["sha256"] for e in manifest["files"] if e["path"] == "sbx"), None),
            "outside_sbx": str(AUDIT / "sbx_bin" / dest.name / "sbx"), "image": manifest["sandbox"].get("image"),
            "manifest": str(spec.manifest), "acl": bool((manifest.get("acl") or {}).get("enabled"))}
    out = AUDIT / f"protected_{dest.name}.json"
    AUDIT.mkdir(parents=True, exist_ok=True)
    if ACL is not None and out.exists():
        ACL.unprotect(out)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(prot, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, out)
    return out


def _entry(it: Item, dest: Path, redactions: int | None = None) -> dict:
    p = dest / it.path
    e = {"path": it.path, "source": ("$REPO/" + it.source) if it.source else "generated by scripts/make_phase4_cleanroom.py",
         "destination": f"$ROOMS/{dest.name}/{it.path}", "sha256": _sha(p), "bytes": p.stat().st_size, "reason": it.reason,
         "classification": it.classification}
    if it.redact and it.source:
        e["redacted_lines"] = int(redactions or 0)
        e["source_sha256"] = _sha(ROOT / it.source)            # OUTSIDE manifest only (room_manifest_view drops it)
    return e


def _verify_locked(it: Item, src: Path) -> str | None:
    if not it.verify:
        return None
    lock = json.loads((ROOT / it.verify["lock"]).read_text(encoding="utf-8"))
    table = lock.get(it.verify["key"]) or {}
    want = table.get(it.source)
    if want is None:
        return f"{it.source} is not hashed in its lock"
    if _sha(src) != want:
        return f"{it.source} differs from its locked hash"
    return None


def _p3_closure_check() -> str | None:
    """The locked methods may import only the support modules copied with them (P3_SUPPORT)."""
    need = set()
    for p in [ROOT / P3_PKG / "methods" / f"{m}.py" for m in P3_V1_METHOD_FILES]:
        if not p.exists():
            continue
        for m in re.findall(r"(?m)^\s*from \.\.(\w+) import", p.read_text(encoding="utf-8", errors="ignore")):
            need.add(m)
    for m in list(need):
        src = ROOT / P3_PKG / f"{m}.py"
        if src.exists():
            need |= set(re.findall(r"(?m)^\s*from \.(\w+) import", src.read_text(encoding="utf-8", errors="ignore")))
    extra = sorted(need - set(P3_SUPPORT))
    return f"locked methods import modules not copied: {extra}" if extra else None


# ------------------------------------------------------------------------------------------------ OS-level protection (F-B4)
def _in_work(rel: str, spec: RoomSpec) -> bool:
    return spec.work_areas is not None and any(rel == w.rstrip("/") or rel.startswith(w.rstrip("/") + "/") for w in spec.work_areas)


def protected_targets(spec: RoomSpec, dest: Path, manifest: dict) -> list[tuple[str, int]]:
    """(absolute path, deny mask) of everything the builder protects (scripts/p4agent/ntfs_protect.py):
    FILE_MASK    every allowlisted file and the in-room manifest;
    DIR_MASK     every directory on the way to one of them that is not a work area; in rooms with declared work areas also the room
                 root and EVERY directory that is neither a work area nor inside one;
    PARENT_MASK  a work area or the root of a free room that holds an allowlisted entry (its FILE_DELETE_CHILD would otherwise let a
                 process delete, rename or replace that entry);
    ANCHOR_MASK  every other work-area root (cannot be renamed or removed; its content stays free);
    and the outside sbx copy, its seccomp profile (FILE_MASK) and their directory (DIR_MASK)."""
    if ACL is None:
        return []
    files = [e["path"] for e in manifest["files"]] + ["CLEANROOM_MANIFEST.json"]
    dirs, parents = set(), set()
    for f in files:
        parts = f.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            d = "/".join(parts[:i])
            if not _in_work(d, spec):
                dirs.add(d)
        parent = "/".join(parts)
        if parent == "" or _in_work(parent, spec):
            parents.add(parent)
    if spec.work_areas is not None and dest.exists():
        for dirpath, dirnames, _ in os.walk(dest, followlinks=False):
            for name in list(dirnames):
                rel = (Path(dirpath) / name).relative_to(dest).as_posix()
                if _in_work(rel, spec) or _is_link(Path(dirpath) / name):
                    dirnames.remove(name)
                else:
                    dirs.add(rel)
    out = [(str(dest / f), ACL.FILE_MASK) for f in sorted(set(files))] + [(str(dest / d), ACL.DIR_MASK) for d in sorted(dirs)]
    if spec.work_areas is not None:
        out.append((str(dest), ACL.DIR_MASK))
        parents.discard("")
    for d in sorted(parents):
        out.append((str(dest / d) if d else str(dest), ACL.PARENT_MASK))
    for w in (spec.work_areas or ()):
        w = w.rstrip("/")
        if w not in parents:
            out.append((str(dest / w), ACL.ANCHOR_MASK))
    bindir = AUDIT / "sbx_bin" / dest.name
    out += [(str(bindir / "sbx"), ACL.FILE_MASK), (str(bindir / "seccomp_nolinks.json"), ACL.FILE_MASK), (str(bindir), ACL.DIR_MASK)]
    return out


def protect_room(spec: RoomSpec, dest: Path, manifest: dict) -> dict:
    if ACL is None:
        return {"enabled": False, "reason": "ntfs_protect unavailable (not Windows)"}
    targets = protected_targets(spec, dest, manifest)
    n = ACL.protect_paths(targets)
    return {"enabled": True, "n_protected": n, "file_mask": hex(ACL.FILE_MASK), "dir_mask": hex(ACL.DIR_MASK),
            "parent_mask": hex(ACL.PARENT_MASK), "anchor_mask": hex(ACL.ANCHOR_MASK), "trustee": ACL.EVERYONE_SID}


def unprotect_room(spec: RoomSpec, dest: Path) -> int:
    """Lift the ACE from everything in the room outside the work areas (whatever an earlier build / sync protected, also under an
    earlier work-area layout) and from the outside sbx directory."""
    if ACL is None:
        return 0
    n = 0
    if dest.exists():
        stack = [dest]
        while stack:
            d = stack.pop()
            try:
                if ACL.deny_mask_of(str(d)):
                    ACL.unprotect(str(d))
                    n += 1
            except OSError:
                pass
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue
            for e in entries:
                rel = Path(e.path).relative_to(dest).as_posix()
                if _is_link(Path(e.path)):
                    continue
                if e.is_dir(follow_symlinks=False):
                    if not (_in_work(rel, spec) and rel.rstrip("/") not in [w.rstrip("/") for w in (spec.work_areas or ())]):
                        stack.append(Path(e.path))           # a work-area root itself may carry an old ACE; its content never does
                else:
                    try:
                        if ACL.deny_mask_of(e.path):
                            ACL.unprotect(e.path)
                            n += 1
                    except OSError:
                        pass
    return n + ACL.unprotect_tree(AUDIT / "sbx_bin" / dest.name)


def check_protection(spec: RoomSpec, dest: Path, manifest: dict) -> list[str]:
    if ACL is None or not (manifest.get("acl") or {}).get("enabled"):
        return []
    return [f"OS protection missing: {p}" for p in ACL.check_paths(protected_targets(spec, dest, manifest))]


# ------------------------------------------------------------------------------------------------ build
def materialise(spec: RoomSpec, dest: Path, allow_missing: bool) -> tuple[list[dict], list[str]]:
    """Copy / generate every item into dest; returns (manifest entries, missing sources)."""
    entries, missing = [], []
    seen = set()
    if spec.name in ("clean", "review"):
        why = _p3_closure_check()
        if why:
            raise SystemExit(why)
    for it in spec.items:
        if it.path in seen:
            raise SystemExit(f"duplicate destination {it.path}")
        seen.add(it.path)
        dst = dest / it.path
        if it.source is None:
            if scan_text(it.content or ""):
                raise SystemExit(f"generated file {it.path} would carry forbidden content")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(it.content or "", encoding="utf-8", newline="\n")
            entries.append(_entry(it, dest))
            continue
        src = ROOT / it.source
        if not src.is_file():
            if it.required and not allow_missing:
                raise SystemExit(f"required source missing: {it.source}")
            missing.append(it.source)
            continue
        why = check_source(src, it.path, spec, it.redact) or _verify_locked(it, src)
        if why and not it.required:
            REFUSED_OPTIONAL.append({"source": it.source, "path": it.path, "why": why})    # left out, reported (never copied)
            continue
        if why:
            raise SystemExit(f"refused {it.source} -> {it.path}: {why}")
        n_red = _materialise_file(it, src, dst)
        entries.append(_entry(it, dest, n_red))
    return entries, missing


REFUSED_OPTIONAL: list[dict] = []           # optional sources the scanner refused in this run (reported in the manifest, not copied)


def _work_dirs(spec: RoomSpec, dest: Path) -> None:
    for d in spec.dirs:
        (dest / d).mkdir(parents=True, exist_ok=True)
    for f in spec.seed_files:
        p = dest / f
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"")


def _sandbox_record(spec: RoomSpec, sb: dict, ro: list[str]) -> dict:
    img = _image()
    return {"image": img["id"], "image_tag": img["tag"], "seccomp_sha256": sb["seccomp_sha256"], "ro_paths": ro,
            "rw_areas": rw_areas(spec) if spec.work_areas is not None else "every top-level entry that is not allowlisted",
            "agent_areas": list(spec.agent_areas), "owned_areas": list(spec.owned_areas), "rw_nested": list(spec.rw_nested),
            "outside_copy": sb["outside_copy"],
            "max_cpus": spec.max_cpus, "max_mem_gb": spec.max_mem_gb, "room_mount": "read-only",
            "bytecode": "PYTHONDONTWRITEBYTECODE=1, PYTHONPYCACHEPREFIX=/tmp/pyc"}


def _sbx_entry(dest: Path, sb: dict) -> dict:
    return {"path": "sbx", "source": "generated from scripts/p4agent/sbx_template.sh", "destination": f"$ROOMS/{dest.name}/sbx",
            "sha256": sb["sbx_sha256"], "bytes": (dest / "sbx").stat().st_size, "reason": "Docker sandbox wrapper",
            "classification": "generated"}


def build(spec: RoomSpec, dest: Path, allow_missing: bool = False, docker_check: bool = True, protect: bool = True) -> dict:
    if dest.exists():
        raise SystemExit(f"{dest} exists: use --check / --sync or --destroy-and-rebuild")
    img = _image()
    if docker_check:
        why = verify_image(img["id"])
        if why:
            raise SystemExit(why)
    dest.mkdir(parents=True)
    try:
        if ACL is not None:
            ACL.unprotect_tree(AUDIT / "sbx_bin" / dest.name)       # a stale outside copy of an earlier room of this name
        entries, missing = materialise(spec, dest, allow_missing)
        _work_dirs(spec, dest)
        paths = [e["path"] for e in entries] + ["sbx", "CLEANROOM_MANIFEST.json"]
        ro = ro_paths(spec, paths)
        sb = install_sbx(spec, dest, paths)
        entries.append(_sbx_entry(dest, sb))
        manifest = {"room": dest.name, "room_kind": spec.name, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "builder": "scripts/make_phase4_cleanroom.py", "n_files": len(entries), "incomplete_missing_sources": missing,
                    "files": sorted(entries, key=lambda e: e["path"]),
                    "work_areas": list(spec.work_areas) if spec.work_areas is not None else "free (every non-allowlisted path)",
                    "sandbox": _sandbox_record(spec, sb, ro), "refusal_list": [p.pattern for p in REFUSE], "syncs": [],
                    "refused_optional": list(REFUSED_OPTIONAL)}
        _write_inroom_manifest(dest, manifest)
        problems = scan(dest, manifest, spec)
        manifest["build_scan_problems"] = problems
        if problems:
            _write_manifest(spec, dest, manifest)
            raise SystemExit(f"build scan failed: {problems[:8]}")
        manifest["acl"] = protect_room(spec, dest, manifest) if protect else {"enabled": False, "reason": "disabled (tests)"}
        _write_manifest(spec, dest, manifest, inroom=False)
        write_protected(spec, dest, manifest)
        return manifest
    except BaseException:
        # never leave a half-built room behind silently: keep it for inspection but mark it
        try:
            (dest / "BUILD_FAILED.txt").write_text("build failed; see the builder output\n", encoding="utf-8")
        except OSError:
            pass
        raise


def room_manifest_view(manifest: dict) -> dict:
    """The IN-ROOM copy of the manifest (early review F, F-B5 / F-M1): file paths, hashes and sizes only. Sources, source hashes,
    reasons, the refusal list and every other field stay in the OUTSIDE manifest (research/phase4/CLEANROOM_MANIFEST*.json)."""
    return {"room_kind": manifest.get("room_kind"), "created_utc": manifest.get("created_utc"), "n_files": manifest.get("n_files"),
            "files": [{"path": e["path"], "sha256": e["sha256"], "bytes": e.get("bytes")} for e in manifest.get("files", [])],
            "work_areas": manifest.get("work_areas"), "note": "in-room copy: paths, hashes and sizes only"}


def _write_inroom_manifest(dest: Path, manifest: dict) -> None:
    inroom = json.dumps(room_manifest_view(manifest), indent=1) + "\n"
    hit = scan_text(inroom)
    if hit:
        raise SystemExit("the in-room manifest would carry forbidden content")
    (dest / "CLEANROOM_MANIFEST.json").write_text(inroom, encoding="utf-8", newline="\n")


def _write_manifest(spec: RoomSpec, dest: Path, manifest: dict, inroom: bool = True) -> None:
    spec.manifest.parent.mkdir(parents=True, exist_ok=True)
    spec.manifest.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    if inroom:
        _write_inroom_manifest(dest, manifest)


def _is_link(p: Path) -> bool:
    try:
        if p.is_symlink():
            return True
        return bool(getattr(os.lstat(p), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return False


PLANTED_NAMES = {"sitecustomize.py", "usercustomize.py"}
CONTROL_NAMES = {"claude.md", "claude.local.md", ".mcp.json"}


def _outside_work(rel: str, spec: RoomSpec, tops: set[str]) -> bool:
    """Is a room-relative path outside the agents' work areas? (free rooms: inside an orchestrator top-level entry)"""
    if spec.work_areas is None:
        return rel.split("/", 1)[0].lower() in tops
    return not _in_work(rel, spec)


def scan(dest: Path, manifest: dict, spec: RoomSpec, content_all: bool = True) -> list[str]:
    """Blocking problems: allowlisted files missing / modified; links or junctions; unexpected files outside the work areas;
    forbidden names; forbidden text in any text file (agent files included; not the agents' .tmp)."""
    probs = []
    listed = {e["path"]: e["sha256"] for e in manifest["files"]}
    for path, h in listed.items():
        p = dest / path
        if path == "CLEANROOM_MANIFEST.json":
            continue
        if not p.exists():
            probs.append(f"missing: {path}")
        elif _sha(p) != h:
            probs.append(f"modified: {path}")
    tops = {t.lower() for t in ro_tops(list(listed))}
    for dirpath, dirnames, filenames in os.walk(dest, followlinks=False):
        d = Path(dirpath)
        for name in list(dirnames):
            q = d / name
            if _is_link(q):
                probs.append(f"link / junction: {q.relative_to(dest).as_posix()}")
                dirnames.remove(name)
        for name in filenames:
            q = d / name
            rel = q.relative_to(dest).as_posix()
            if _is_link(q):
                probs.append(f"link: {rel}")
                continue
            cache = "__pycache__" in rel.split("/") or name.endswith((".pyc", ".pyo")) or rel.split("/", 1)[0] == ".pytest_cache"
            if rel not in listed and rel not in ("CLEANROOM_MANIFEST.json", "BUILD_FAILED.txt") and not cache and \
                    _outside_work(rel, spec, tops):
                probs.append(f"unexpected file: {rel}")
            if NAMES_ALWAYS.search(rel):
                probs.append(f"forbidden name: {rel}")
            if rel in listed and spec.name in ("bench", "clean") and NAMES_ORCHESTRATOR.search(rel) and \
                    not any(rel.startswith(x) for x in spec.names_orchestrator_exempt):
                probs.append(f"orchestrator-side module name: {rel}")
            if content_all and not rel.startswith(".tmp/"):
                try:
                    if _is_text(q) and q.stat().st_size < MAX_SCAN_BYTES:
                        hit = scan_text(q.read_text(encoding="utf-8", errors="ignore"), rel)
                        if hit:
                            probs.append(f"forbidden content in {rel}")
                except OSError:
                    pass
    return probs


def scan_planted(dest: Path, manifest: dict) -> list[str]:
    """Reports (early review F, F-M3): every bytecode file / cache directory, every Claude control file other than the root
    placeholders, every nested .claude directory, every sitecustomize / usercustomize module and every *.pth file that is not an
    allowlisted file, anywhere in the room (agents' .tmp included)."""
    listed = {e["path"] for e in manifest["files"]}
    out = []
    for dirpath, dirnames, filenames in os.walk(dest, followlinks=False):
        d = Path(dirpath)
        for name in list(dirnames):
            rel = (d / name).relative_to(dest).as_posix()
            if _is_link(d / name):
                dirnames.remove(name)
            elif name.lower() == ".claude" and rel != ".claude":
                out.append(f"nested .claude directory: {rel}")
            elif name == "__pycache__":
                out.append(f"bytecode directory: {rel}")
        for name in filenames:
            rel = (d / name).relative_to(dest).as_posix()
            if rel in listed:
                continue
            low = name.lower()
            if low in CONTROL_NAMES or rel.lower().startswith(".claude/"):
                out.append(f"Claude control file: {rel}")
            elif low in PLANTED_NAMES or low.endswith(".pth"):
                out.append(f"interpreter hook: {rel}")
            elif low.endswith((".pyc", ".pyo")) and "/__pycache__/" not in f"/{rel}":
                out.append(f"bytecode file: {rel}")
    return out


def clean_caches(spec: RoomSpec, dest: Path) -> int:
    """Delete bytecode (__pycache__ directories, *.pyc / *.pyo files) anywhere but the agents' .tmp, and pytest caches outside the
    work areas (sandboxes earlier than the read-only room mount could write them; caches only)."""
    n = 0
    for dirpath, dirnames, filenames in os.walk(dest, followlinks=False):
        rel_dir = Path(dirpath).relative_to(dest).as_posix()
        if rel_dir == ".tmp" or rel_dir.startswith(".tmp/"):
            dirnames.clear()
            continue
        for name in list(dirnames):
            rel = f"{rel_dir}/{name}" if rel_dir != "." else name
            if name == "__pycache__" or (name == ".pytest_cache" and spec.work_areas is not None and not _in_work(rel, spec)):
                shutil.rmtree(Path(dirpath) / name, ignore_errors=True)
                dirnames.remove(name)
                n += 1
        for name in filenames:
            if name.endswith((".pyc", ".pyo")):
                try:
                    (Path(dirpath) / name).unlink()
                    n += 1
                except OSError:
                    pass
    return n


def sync(spec: RoomSpec, dest: Path, reason: str, protect: bool = True, purge: tuple[str, ...] = ()) -> dict:
    """Bring an existing room up to date with its allowlist: lift the OS protection; delete the allowlisted files below every `purge`
    directory (e.g. a data copy that must be rebuilt from scratch) and every allowlisted file whose item left the allowlist; copy every
    allowlisted file whose source changed (or that is missing), update its manifest entry, rewrite the sandbox wrapper, clean caches,
    record the sync, rescan, protect again. A file that is already identical but whose manifest entry is stale was copied by an
    interrupted sync: it is checked and recorded like any changed file. Work areas are untouched (except bytecode caches)."""
    manifest = json.loads(spec.manifest.read_text(encoding="utf-8"))
    previous = json.loads(json.dumps(manifest))
    # PRE-FLIGHT (LOG 12.2): scan every required item whose source changed BEFORE the room is touched, so a refused item stops the sync
    # with the room and its manifest unchanged (an abort midway once left a room with a stale manifest)
    pre_by_path = {e["path"]: e for e in manifest["files"]}
    pre_refused = []
    for it in spec.items:
        if it.source is None or not it.required:
            continue
        src = ROOT / it.source
        if not src.is_file():
            pre_refused.append(f"required source missing: {it.source}")
            continue
        prev = pre_by_path.get(it.path) or {}
        if prev.get("source_sha256") == _sha(src):
            continue
        why = check_source(src, it.path, spec, it.redact) or _verify_locked(it, src)
        if why:
            pre_refused.append(f"{it.source} -> {it.path}: {why}")
    if pre_refused:
        raise SystemExit(f"sync refused before any change ({len(pre_refused)} required items): {pre_refused[:10]}")
    unprotect_room(spec, dest)
    done = False
    try:
        by_path = {e["path"]: e for e in manifest["files"]}
        changed, removed = [], []
        wanted = {it.path for it in spec.items} | {"sbx", "CLEANROOM_MANIFEST.json"}
        for d in purge:
            d = d.strip("/")
            if not d or _in_work(d, spec) or d.split("/", 1)[0] in (".claude",) or ".." in d.split("/"):
                raise SystemExit(f"refusing to purge {d!r}: only orchestrator directories below the room root")
            for path in [q for q in by_path if q == d or q.startswith(d + "/")]:
                by_path.pop(path)
                removed.append(path)
            if (dest / d).exists():
                shutil.rmtree(dest / d)
        for path in [q for q in by_path if q not in wanted]:
            q = dest / path
            if q.is_file():
                q.unlink()
            by_path.pop(path)
            removed.append(path)
        for it in spec.items:
            dst = dest / it.path
            if it.source is None:
                content = (it.content or "").encode()
                if dst.exists() and _sha(dst) == _sha_bytes(content, True) and (by_path.get(it.path) or {}).get("sha256") == _sha(dst):
                    continue
                if scan_text(it.content or ""):
                    raise SystemExit(f"generated file {it.path} would carry forbidden content")
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(it.content or "", encoding="utf-8", newline="\n")
                by_path[it.path] = _entry(it, dest)
                changed.append(it.path)
                continue
            src = ROOT / it.source
            if not src.is_file():
                if it.required:
                    raise SystemExit(f"required source missing: {it.source}")
                continue
            prev = by_path.get(it.path) or {}
            if it.redact:
                if dst.exists() and prev.get("source_sha256") == _sha(src) and prev.get("sha256") == _sha(dst):
                    continue
            elif dst.exists() and _sha(dst) == _sha(src) and prev.get("sha256") == _sha(dst):
                continue
            why = check_source(src, it.path, spec, it.redact) or _verify_locked(it, src)
            if why and not it.required:
                REFUSED_OPTIONAL.append({"source": it.source, "path": it.path, "why": why,
                                         "room_copy": "kept (older, scanned version)" if it.path in by_path else "none"})
                continue
            if why:
                raise SystemExit(f"refused {it.source} -> {it.path}: {why}")
            n_red = _materialise_file(it, src, dst)
            by_path[it.path] = _entry(it, dest, n_red)
            changed.append(it.path)
        _work_dirs(spec, dest)
        paths = [p for p in by_path if p != "sbx"] + ["sbx", "CLEANROOM_MANIFEST.json"]
        ro = ro_paths(spec, paths)
        sb = install_sbx(spec, dest, paths)
        by_path["sbx"] = _sbx_entry(dest, sb)
        manifest["files"] = sorted(by_path.values(), key=lambda e: e["path"])
        manifest["n_files"] = len(manifest["files"])
        manifest["work_areas"] = list(spec.work_areas) if spec.work_areas is not None else "free (every non-allowlisted path)"
        manifest["sandbox"] = _sandbox_record(spec, sb, ro)
        manifest["refusal_list"] = [p.pattern for p in REFUSE]
        n_cache = clean_caches(spec, dest)
        for path in removed:
            parent = (dest / path).parent
            while parent != dest and parent.exists() and not any(parent.iterdir()) and not _in_work(parent.relative_to(dest).as_posix(),
                                                                                                         spec):
                parent.rmdir()
                parent = parent.parent
        planted = scan_planted(dest, manifest)
        manifest.setdefault("syncs", []).append({"time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "reason": reason,
                                                 "files": changed, "removed": removed, "purged": list(purge),
                                                 "caches_removed": n_cache, "planted_reports": planted[:200],
                                                 "refused_optional": list(REFUSED_OPTIONAL)})
        # the in-room copy is replaced BEFORE the scan (an older full-format copy would otherwise block its own replacement)
        _write_inroom_manifest(dest, manifest)
        problems = scan(dest, manifest, spec)
        if problems:
            raise SystemExit(f"sync scan failed (manifest not written): {problems[:8]}")
        done = True
    finally:
        if protect:
            if done:
                manifest["acl"] = protect_room(spec, dest, manifest)
            else:                        # a failed sync: protect whatever the last recorded and the attempted allowlists hold
                protect_room(spec, dest, previous)
                protect_room(spec, dest, manifest)
    if not protect:
        manifest["acl"] = {"enabled": False, "reason": "disabled (tests)"}
    _write_manifest(spec, dest, manifest, inroom=False)
    write_protected(spec, dest, manifest)
    return {"changed": changed, "removed": removed, "caches_removed": n_cache, "planted": planted,
            "refused_optional": list(REFUSED_OPTIONAL)}


def audit(spec: RoomSpec, dest: Path) -> dict:
    manifest = json.loads(spec.manifest.read_text(encoding="utf-8"))
    problems = scan(dest, manifest, spec) + check_protection(spec, dest, manifest)
    planted = scan_planted(dest, manifest)
    listed = {e["path"] for e in manifest["files"]} | {"CLEANROOM_MANIFEST.json"}
    unmanifested = []
    n_files = 0
    for p in sorted(dest.rglob("*")):
        if p.is_file() and not _is_link(p):
            n_files += 1
            rel = p.relative_to(dest).as_posix()
            if rel not in listed:
                unmanifested.append(rel)
    rep = {"room": dest.name, "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n_files": n_files,
           "n_manifest": len(listed), "n_unmanifested": len(unmanifested), "unmanifested_by_top": {},
           "problems": problems, "planted_reports": planted, "ok": not problems and not planted}
    for u in unmanifested:
        top = u.split("/", 1)[0] if "/" in u else "(root)"
        rep["unmanifested_by_top"][top] = rep["unmanifested_by_top"].get(top, 0) + 1
    rep["unmanifested"] = unmanifested[:5000]
    out = P4 / "room_audits" / f"{dest.name}_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
    try:
        rep["report"] = out.relative_to(ROOT).as_posix()
    except ValueError:
        rep["report"] = str(out)
    return rep


def destroy(spec: RoomSpec, dest: Path) -> None:
    if not re.match(r"(?i)^brainir_p4[a-z_]+$", dest.name):
        raise SystemExit(f"refusing to delete {dest}: not a Phase 4 room name")
    if ACL is not None:
        ACL.unprotect_tree(dest)
        ACL.unprotect_tree(AUDIT / "sbx_bin" / dest.name)
    shutil.rmtree(dest)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", choices=("bench", "clean", "review"), required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build", action="store_true")
    g.add_argument("--check", nargs="?", const="", default=None, metavar="FILE")
    g.add_argument("--audit", action="store_true")
    g.add_argument("--destroy-and-rebuild", action="store_true")
    g.add_argument("--sync", metavar="REASON")
    ap.add_argument("--dest", type=Path, default=None, help="override the room directory (tests / scratch builds)")
    ap.add_argument("--manifest", type=Path, default=None, help="override the manifest path (default with --dest: the audit dir)")
    ap.add_argument("--allow-missing", action="store_true", help="TESTS ONLY: build although required sources are missing")
    ap.add_argument("--no-docker-check", action="store_true", help="TESTS ONLY: do not verify the sandbox image")
    ap.add_argument("--no-protect", action="store_true", help="TESTS ONLY: do not set the OS-level deny ACEs")
    ap.add_argument("--purge", action="append", default=[], metavar="DIR",
                    help="with --sync: delete this room directory's allowlisted files first (it is copied again from its sources)")
    args = ap.parse_args(argv)
    spec = room_specs()[args.room]
    dest = args.dest or spec.dest
    if args.manifest is not None:
        spec.manifest = args.manifest
    elif args.dest is not None and args.dest != spec.dest:
        spec.manifest = AUDIT / "scratch_manifests" / f"{dest.name}.json"
    if args.check is not None and args.check != "":
        src = Path(args.check)
        src = src if src.is_absolute() else ROOT / src
        why = check_source(src, src.name, spec)
        print(f"REFUSED: {why}" if why else f"ok: {src} may enter room {args.room}")
        return 1 if why else 0
    if args.sync:
        r = sync(spec, dest, args.sync, protect=not args.no_protect, purge=tuple(args.purge))
        print(f"synced {dest}: {len(r['changed'])} files: {r['changed'][:50]}; removed: {len(r['removed'])} {r['removed'][:20]}; caches "
              f"removed: {r['caches_removed']}; planted-file reports: {len(r['planted'])} {r['planted'][:20]}")
        if r["refused_optional"]:
            print(f"REFUSED optional sources (left out; fix them at the source): {r['refused_optional']}")
        return 0
    if args.audit:
        r = audit(spec, dest)
        print(json.dumps({k: v for k, v in r.items() if k != "unmanifested"}, indent=1))
        return 0 if r["ok"] else 1
    if args.destroy_and_rebuild:
        if dest.exists():
            destroy(spec, dest)
        args.build = True
    if args.build:
        m = build(spec, dest, allow_missing=args.allow_missing, docker_check=not args.no_docker_check, protect=not args.no_protect)
        print(f"built {dest}: {m['n_files']} files; scan clean; OS protection: {m['acl']}; read-write in the sandbox: "
              f"{m['sandbox']['rw_areas']} + per agent {m['sandbox']['agent_areas']}"
              + (f"; MISSING (test build): {m['incomplete_missing_sources']}" if m["incomplete_missing_sources"] else ""))
        return 0
    manifest = json.loads(spec.manifest.read_text(encoding="utf-8"))
    probs = scan(dest, manifest, spec) + check_protection(spec, dest, manifest) + scan_planted(dest, manifest)
    print("\n".join(probs) if probs else f"ok: {dest} matches its manifest ({manifest['n_files']} files), holds no forbidden or "
          "planted file and carries its OS protection")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
