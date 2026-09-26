"""Build / check / audit / rebuild the Phase 4 rooms from explicit allowlists (goal5 sections 5-6; research/phase4/ROOM_ALLOWLISTS.md).

    uv run --project phase4 python scripts/make_phase4_cleanroom.py --room bench --build             # C:\\Dev\\BrainIR_p4bench
    uv run --project phase4 python scripts/make_phase4_cleanroom.py --room clean --build             # C:\\Dev\\BrainIR_p4clean
    uv run --project phase4 python scripts/make_phase4_cleanroom.py --room review --build            # C:\\Dev\\BrainIR_p4review
    ... --room R --check                  # verify the room against its manifest (missing / modified / unexpected / forbidden / links)
    ... --room R --check FILE             # may this repository file enter room R? (refusal list, names, content scan)
    ... --room R --audit                  # --check + unmanifested-file list + full content scan of agent files -> room_audits/
    ... --room R --sync "<reason>"        # copy changed allowlisted files (work areas untouched), record the sync, rescan
    ... --room R --destroy-and-rebuild    # delete the room (work areas are lost) and build again

Every file that enters a room has a manifest record {path, source, destination, sha256, reason, classification, bytes}; the
manifest is written outside the room (research/phase4/CLEANROOM_MANIFEST.json for the clean room, CLEANROOM_MANIFEST_<room>.json for
the others) and a copy inside. Sources are refused when they match the REFUSAL list (all Phase 2-3 answer-bearing material, reports,
goal files, the Phase 4 plan, hidden directories, memory files, the main CLAUDE.md) or when their name or text matches the forbidden
classes of the content scanner.

Isolation files placed by the builder (all read-only for agents):
- `sbx` at the room root and an identical copy OUTSIDE the room (C:\\Dev\\BrainIR_p4audit\\sbx_bin\\<room>\\sbx, put on PATH by
  scripts/p4agent/launch.py): the Docker sandbox wrapper through which agents run all code. The container mounts the room with every
  allowlisted path READ-ONLY (work areas read-write), no network, no capabilities, a seccomp profile without symlink creation.
- `.claude/` (empty), `CLAUDE.local.md` and `.mcp.json` placeholders: they exist so that the sandbox can mount them read-only (code in
  a container must not be able to plant Claude settings, hooks or instructions that the host session would load).
- C:\\Dev\\BrainIR_p4audit\\protected_<room>.json: the paths the PreToolUse guard refuses to modify on the host.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = Path(r"C:\Dev\BrainIR_p4audit")
P4 = ROOT / "research" / "phase4"
IMAGE_JSON = ROOT / "docker" / "p4sandbox" / "image.json"
SECCOMP_SRC = ROOT / "docker" / "p4sandbox" / "seccomp_nolinks.json"
SBX_TEMPLATE = ROOT / "scripts" / "p4agent" / "sbx_template.sh"
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".jsonl", ".toml", ".cfg", ".yaml", ".yml", ".csv", ".sh", ".ini", ".rst", ".tsv"}
MAX_SCAN_BYTES = 20_000_000

# ------------------------------------------------------------------------------------------------ refusal list (all rooms)
# repository-relative source paths that may NEVER enter any Phase 4 room (research/phase4/ROOM_ALLOWLISTS.md, "Refusal list")
REFUSE = [re.compile(p, re.IGNORECASE) for p in (
    r"(^|/)PHASE\d+_REPORT\.md$", r"(^|/)goal\d*\.md$", r"^research/LOG\.md$", r"^research/phase2/", r"^research/phase3/",
    r"^research/phase4/PLAN\.md$", r"^research/phase4/reviews/", r"^research/phase4/HIDDEN_EVALUATIONS\.md$",
    r"^research/literature/", r"^benchmarks/dng100_walking_cpg/", r"^benchmarks/dng100/(oracle|evaluator|baselines)/",
    r"^benchmarks/state_discovery_v1/hidden/", r"^benchmarks/causal_state_v1/hidden/", r"^data/phase3/", r"^data/phase4/hidden/",
    r"^data/phase4/suites/(val|conf)[^/]*/(.*/)?truth/", r"(^|/)MEMORY\.md$", r"(^|/)\.claude/", r"^CLAUDE\.md$",
    r"(^|/)\.modal\.toml$", r"(^|/)\.credentials", r"(^|/)SALT(_REVEAL)?[^/]*$", r"(^|/)salt(\.json|\.txt|\.bin)?$",
)]

# file NAMES forbidden anywhere in a room (agent files included)
NAMES_ALWAYS = re.compile(r"(?i)(phase\d_report|hidden_eval|blind_eval|(^|/)oracle|salt_reveal|real_hidden|real_name_map|"
                          r"systems_internal|salt_commitment|(^|/)goal\d+\.md$|dng100|benchmark_lock|method_lock|state_discovery_v1|"
                          r"(^|/)memory\.md$|postlock_|report_working)")
# file names forbidden among the ALLOWLISTED files of the method rooms (orchestrator-side modules; the review room's extra/ is exempt)
NAMES_ORCHESTRATOR = re.compile(r"(?i)(^|/)(realsim|realgen|simservice|synthadapter|synthsim|suites|suite_eval|evaluate_truth|calibrate|"
                                r"runguard|runner|tournament|feedback|p4modal|store|systems|accounting)(\.py|/)|(^|/)calibration\.json$")
# TEXT forbidden anywhere in a room: dataset / circuit / paper names, Phase 1-3 answer phrases and artefact names, absolute paths of
# the main repository or of Phase 2-3 rooms
CONTENT_ALWAYS = re.compile(
    r"(?i)(inhibitory slot|e-core recall|excitatory core recall|published core|published circuit|published answer|\bE1/E2\b|I1\|I2|"
    r"core_contralateral|answer key|dng100|pugliese|\bmanc\b|male-?cns|\bneuprint\b|\bflywire\b|\bhemibrain\b|\bdrosophila\b|"
    r"hidden_eval_log|phase[0-3]_report|hidden_evaluations\.md|salt_reveal|real_hidden|brainir-p3-(eval|fit|devdata)|"
    r"postlock_[a-z]|report_working|state_discovery_v1[\\/]+hidden|research[\\/]+phase[23]\b|data[\\/]+phase3\b|"
    r"(?<![\w$])[a-z]:[\\/]+dev[\\/]+brainir(?=[\\/'\"\s)]|$)|(?<![\w$])/[a-z]/dev/brainir(?=[\\/'\"\s)]|$)|brainir_p[23][a-z_]*)")

GENERIC_CLAUDE_MD = """# BrainIR Phase 4 clean development room (causal state models trained with interventions)

You develop methods that learn low-dimensional CAUSAL state models of simulated neural systems with interventions as part of the
learning problem: an encoder from the observed microstate x (and input u) to a latent z, controlled latent dynamics, an explicit
intervention read-in, a readout, a native lift (latent change -> physical interventions) and an experiment designer. Start with
docs/METHOD_DEV_CONTRACT.md, then docs/PROTOCOL.md (the frozen evaluation), docs/PROTOCOL_V2.md, docs/API.md and
docs/METHODS_REVIEW.md.

Rules (enforced technically; do not try to get around them):
1. Work only inside this directory. Nothing outside it is reachable.
2. Run ALL code through the Docker sandbox: `sbx python ...`, `sbx pytest -q tests/methods` (or `./sbx ...` from this directory).
   Host interpreters (python, uv, pip, node, ...) are refused. Inside the sandbox this room is mounted at /room; the room's public
   files are read-only there, your work areas are writable; there is no network.
3. Simulation only through the budgeted service: `from brainir_causal.simclient import SimClient` (public policy only).
4. Datasets: data/ (public development data; no ground truth).
5. Put your method in src/brainir_causal/methods/<prefix>_*.py, its tests in tests/methods/, experiments in runs/<prefix>/, notes in
   notes/<prefix>_*.md. Several developers share this room: never modify another developer's files.
6. Methods must be generic: no special cases for particular systems, no hard-coded latent dimension, no per-system lookup tables.
7. Never use the readout y as encoder input; never let an encoder see future samples.
8. Heavy or GPU experiments: the remote runner (docs/REMOTE_RUNNER.md). No web access.
"""

REVIEW_README = """# extra/ (orchestrator-side code for reviewers)

Orchestrator-side modules and tools that method developers never see: the real-system engine and system definitions (public parts),
the trajectory store, the simulation service, the synthetic-generator adapter and suite builder, truth-level evaluation, calibration,
the fit sandbox and runner, the tournament driver and feedback, the Modal backend, the synthetic generator with its tests, the room
builder and the agent isolation stack. No salt, no validation or confirmation truth data, no hidden data.
"""


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


@dataclass
class RoomSpec:
    name: str
    dest: Path
    manifest: Path
    items: list[Item]
    work_areas: tuple[str, ...] | None       # None = free workspace (every non-allowlisted path is the agent's)
    rw_nested: tuple[str, ...] = ()          # work areas beneath read-only allowlisted directories
    names_orchestrator_exempt: tuple[str, ...] = ()
    max_cpus: int = 4
    max_mem_gb: int = 12
    dirs: tuple[str, ...] = ()               # empty directories to create
    notes: list[str] = field(default_factory=list)


def _glob(pattern: str) -> list[Path]:
    return sorted(p for p in ROOT.glob(pattern) if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")


def _tree(src_dir: str, dst_dir: str, reason: str, cls: str, required: bool = True, pattern: str = "**/*") -> list[Item]:
    base = ROOT / src_dir
    files = sorted(p for p in base.glob(pattern) if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc") \
        if base.exists() else []
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


P3_METHOD_LOCK = "research/phase3/METHOD_LOCK.json"
P3_BENCH_LOCK = "benchmarks/state_discovery_v1/BENCHMARK_LOCK.json"
P3_SUPPORT = ("__init__", "api", "data", "evaluate", "refmodels")        # what the locked methods import (closure checked in build)


def _p3_baseline_items() -> list[Item]:
    items = []
    for m in P3_SUPPORT:
        src = f"phase3/src/brainir_state/{m}.py"
        items.append(Item(src, f"baselines/brainir_state_v1/brainir_state/{m}.py", "Phase 3 public module imported by the locked method",
                          "baseline-frozen", verify={"lock": P3_BENCH_LOCK, "key": "files"}))
    for p in _glob("phase3/src/brainir_state/methods/*.py"):
        rel = p.relative_to(ROOT).as_posix()
        items.append(Item(rel, f"baselines/brainir_state_v1/brainir_state/methods/{p.name}", "Phase 3 locked method package (frozen baseline)",
                          "baseline-frozen", verify={"lock": P3_METHOD_LOCK, "key": "source_sha256"}))
    items += _tree("phase4/baselines/brainir_state_v1_adapter", "baselines/brainir_state_v1/adapter",
                   "Phase 4 adapter of the frozen Phase 3 method", "baseline-frozen", required=False)
    return items


CLEAN_MODULES = ("__init__", "api", "protocol", "families", "data", "evalio", "fresh", "stats", "evaluate", "evaluate_mediation",
                 "evaluate_micro", "evaluate_lift", "evaluate_stability", "evaluate_transfer", "verdict", "refs", "harness", "loop",
                 "designers", "capacity", "calibstats", "equiv", "simclient", "select")
REVIEW_EXTRA_MODULES = ("realsim", "systems", "store", "simservice", "synthadapter", "suites", "evaluate_truth", "calibrate", "runguard",
                        "runner", "tournament", "feedback", "accounting")

CLEAN_PYPROJECT = """[project]
name = "brainir-p4clean"
version = "0.1.0"
description = "Phase 4 clean development room: public modules of brainir_causal, the frozen Phase 3 baseline, method work areas."
requires-python = ">=3.12,<3.13"
# The code runs in the Docker sandbox image brainir-p4-sandbox:1 (sbx), which pins this stack exactly.
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
             "into runs/_remote/queue)", "generic-public", required=False),
        Item("benchmarks/causal_state_v1/public/systems_public.json", "data/systems_public.json", "merged public system records", "benchmark-public"),
        Item("benchmarks/causal_state_v1/public/tolerances.json", "data/tolerances.json", "calibrated tolerances (values only)", "benchmark-public"),
        Item("benchmarks/causal_state_v1/public/calibration_targets.json", "data/calibration_targets.json", "calibration targets", "public-derived"),
    ]
    clean_items += _tree("data/phase4/suites/dev/public", "data/synthetic_dev", "synthetic development data (no truth)", "benchmark-public")
    clean_items += _tree("data/phase4/real_public", "data/real_public", "Phase 4 public real data", "benchmark-public")
    clean_items += _tree("phase4/tests/public", "tests", "public module tests (run without orchestrator-side modules)", "generic-public",
                         required=False)
    review_items = list(clean_items)
    review_items = [it for it in review_items if it.path != "CLAUDE.md"] + [
        Item("research/phase4/review_contracts/p4review_CLAUDE.md", "CLAUDE.md", "review room rules", "contract")]
    for m in REVIEW_EXTRA_MODULES:
        review_items.append(Item(f"phase4/src/brainir_causal/{m}.py", f"extra/brainir_causal/{m}.py", "orchestrator-side module (review)",
                                 "orchestrator-code"))
    review_items += _tree("phase4/src/brainir_causal/p4modal", "extra/brainir_causal/p4modal", "Modal backend (review)", "orchestrator-code")
    review_items += _tree("benchmarks/causal_state_v1/generator", "extra/generator", "synthetic generator and its tests (review)",
                          "orchestrator-code")
    review_items += [
        Item("benchmarks/causal_state_v1/public/calibration.json", "extra/calibration.json", "calibration outputs (review)", "orchestrator-code",
             required=False),
        Item("scripts/make_phase4_cleanroom.py", "extra/scripts/make_phase4_cleanroom.py", "room builder (review)", "orchestrator-code"),
        Item("scripts/p4/devrun4.py", "extra/scripts/devrun4.py", "remote runner (review)", "orchestrator-code"),
        Item(None, "extra/README.md", "what extra/ holds", "generated", content=REVIEW_README),
    ]
    review_items += _tree("scripts/p4agent", "extra/scripts/p4agent", "agent isolation stack (review)", "orchestrator-code")
    return {
        "bench": RoomSpec("bench", Path(r"C:\Dev\BrainIR_p4bench"), P4 / "CLEANROOM_MANIFEST_bench.json", bench_items, None,
                          dirs=(".tmp",)),
        "clean": RoomSpec("clean", Path(r"C:\Dev\BrainIR_p4clean"), P4 / "CLEANROOM_MANIFEST.json", clean_items,
                          ("src/brainir_causal/methods/", "runs/", "notes/", "tests/methods/", "simq/", ".tmp/", ".pytest_cache/"),
                          rw_nested=("src/brainir_causal/methods", "tests/methods"),
                          dirs=("runs/_remote/queue/requests", "runs/_remote/queue/results", "notes", "tests/methods", "simq/requests",
                                "simq/results", ".tmp")),
        "review": RoomSpec("review", Path(r"C:\Dev\BrainIR_p4review"), P4 / "CLEANROOM_MANIFEST_review.json", review_items,
                           ("reviews/", "runs/", "notes/", "tests/methods/", "src/brainir_causal/methods/", "simq/", ".tmp/", ".pytest_cache/"),
                           rw_nested=("src/brainir_causal/methods", "tests/methods"), names_orchestrator_exempt=("extra/",),
                           dirs=("reviews", "runs", "notes", "tests/methods", ".tmp")),
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
    for pat in REFUSE:
        if pat.search(rel):
            return f"refusal list: {pat.pattern}"
    return None


def scan_text(text: str) -> str | None:
    m = CONTENT_ALWAYS.search(text)
    return None if m is None else m.group(0)


def check_source(src: Path, room_path: str, spec: RoomSpec) -> str | None:
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
    if src.suffix.lower() in TEXT_SUFFIXES and src.stat().st_size < MAX_SCAN_BYTES:
        hit = scan_text(src.read_text(encoding="utf-8", errors="ignore"))
        if hit:
            return f"forbidden content {hit!r}"
    return None


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
        return f"sandbox image {expect_id} not present locally (docker build -t brainir-p4-sandbox:1 docker/p4sandbox)"
    return None


def ro_paths(spec: RoomSpec, paths: list[str]) -> list[str]:
    """Top-level room entries that hold only allowlisted / generated files -> mounted read-only in the sandbox. A top-level directory
    that also contains a work area is split into its allowlisted children (files and subdirectories)."""
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
        # read-only per second-level child that is not (and does not contain) a work area
        seconds = sorted({"/".join(m.split("/")[:2]) for m in members})
        for s in seconds:
            if not any(w == s or w.startswith(s + "/") for w in works):
                out.append(s)
            else:
                deeper = sorted({"/".join(m.split("/")[:3]) for m in members if m.startswith(s + "/")})
                out += [d for d in deeper if not any(w == d or w.startswith(d + "/") for w in works)]
    return sorted(set(out))


def render_sbx(spec: RoomSpec, dest: Path, ro: list[str], seccomp_win: str) -> str:
    img = _image()
    t = SBX_TEMPLATE.read_text(encoding="utf-8")

    def q(xs):
        return " ".join("'" + x.replace("'", "") + "'" for x in xs)
    rw = [p for p in spec.rw_nested]
    rep = {"@ROOM_POSIX@": _posix(dest), "@ROOM_MOUNT@": str(dest).replace("\\", "/"), "@ROOM_NAME@": dest.name,
           "@IMAGE_ID@": img["id"], "@DOCKER@": _docker_exe(), "@SECCOMP@": seccomp_win, "@MAX_CPUS@": str(spec.max_cpus),
           "@MAX_MEM_GB@": str(spec.max_mem_gb), "@RO_PATHS@": q(ro), "@RW_PATHS@": q(rw)}
    for k, v in rep.items():
        t = t.replace(k, v)
    left = re.findall(r"@[A-Z_]+@", t)
    if left:
        raise SystemExit(f"sbx template placeholders left: {left}")
    return t


def install_sbx(spec: RoomSpec, dest: Path, ro: list[str]) -> dict:
    """Write the wrapper at the room root and the identical outside copy (+ seccomp profile) under AUDIT/sbx_bin/<room>/."""
    bindir = AUDIT / "sbx_bin" / dest.name
    bindir.mkdir(parents=True, exist_ok=True)
    sec = bindir / "seccomp_nolinks.json"
    shutil.copyfile(SECCOMP_SRC, sec)
    text = render_sbx(spec, dest, ro, str(sec).replace("\\", "/"))
    for p in (dest / "sbx", bindir / "sbx"):
        p.write_text(text, encoding="utf-8", newline="\n")
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return {"sbx_sha256": _sha(dest / "sbx"), "outside_copy": "$AUDIT/sbx_bin/" + dest.name + "/sbx",
            "seccomp_sha256": _sha(sec), "image": _image()["id"]}


def write_protected(spec: RoomSpec, dest: Path, manifest: dict) -> Path:
    prot = {"room": dest.name, "generated_utc": manifest.get("created_utc"),
            "files": sorted(e["path"] for e in manifest["files"]),
            "read_only_dirs": manifest["sandbox"]["ro_paths"], "rw_nested": list(spec.rw_nested),
            "work_areas": list(spec.work_areas) if spec.work_areas is not None else None}
    out = AUDIT / f"protected_{dest.name}.json"
    AUDIT.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(prot, indent=1) + "\n", encoding="utf-8", newline="\n")
    return out


def _entry(it: Item, dest: Path) -> dict:
    p = dest / it.path
    return {"path": it.path, "source": ("$REPO/" + it.source) if it.source else "generated by scripts/make_phase4_cleanroom.py",
            "destination": f"$ROOMS/{dest.name}/{it.path}", "sha256": _sha(p), "bytes": p.stat().st_size, "reason": it.reason,
            "classification": it.classification}


def _verify_locked(it: Item, src: Path) -> str | None:
    if not it.verify:
        return None
    lock = json.loads((ROOT / it.verify["lock"]).read_text(encoding="utf-8"))
    table = lock.get(it.verify["key"]) or {}
    want = table.get(it.source)
    if want is None:
        return f"{it.source} is not hashed in {it.verify['lock']}"
    if _sha(src) != want:
        return f"{it.source} differs from its locked hash in {it.verify['lock']}"
    return None


def _p3_closure_check() -> str | None:
    """The locked methods may import only the support modules copied with them (P3_SUPPORT)."""
    need = set()
    for p in _glob("phase3/src/brainir_state/methods/*.py"):
        for m in re.findall(r"(?m)^\s*from \.\.(\w+) import", p.read_text(encoding="utf-8", errors="ignore")):
            need.add(m)
    for m in list(need):
        src = ROOT / "phase3" / "src" / "brainir_state" / f"{m}.py"
        if src.exists():
            need |= set(re.findall(r"(?m)^\s*from \.(\w+) import", src.read_text(encoding="utf-8", errors="ignore")))
    extra = sorted(need - set(P3_SUPPORT))
    return f"locked methods import modules not copied: {extra}" if extra else None


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
        why = check_source(src, it.path, spec) or _verify_locked(it, src)
        if why:
            raise SystemExit(f"refused {it.source} -> {it.path}: {why}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        entries.append(_entry(it, dest))
    return entries, missing


def build(spec: RoomSpec, dest: Path, allow_missing: bool = False, docker_check: bool = True) -> dict:
    if dest.exists():
        raise SystemExit(f"{dest} exists: use --check / --sync or --destroy-and-rebuild")
    img = _image()
    if docker_check:
        why = verify_image(img["id"])
        if why:
            raise SystemExit(why)
    dest.mkdir(parents=True)
    try:
        entries, missing = materialise(spec, dest, allow_missing)
        for d in spec.dirs:
            (dest / d).mkdir(parents=True, exist_ok=True)
        paths = [e["path"] for e in entries] + ["sbx", "CLEANROOM_MANIFEST.json"]
        ro = ro_paths(spec, paths)
        sb = install_sbx(spec, dest, ro)
        entries.append({"path": "sbx", "source": "generated from scripts/p4agent/sbx_template.sh", "destination": f"$ROOMS/{dest.name}/sbx",
                        "sha256": sb["sbx_sha256"], "bytes": (dest / "sbx").stat().st_size, "reason": "Docker sandbox wrapper",
                        "classification": "generated"})
        manifest = {"room": dest.name, "room_kind": spec.name, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "builder": "scripts/make_phase4_cleanroom.py", "n_files": len(entries), "incomplete_missing_sources": missing,
                    "files": sorted(entries, key=lambda e: e["path"]),
                    "work_areas": list(spec.work_areas) if spec.work_areas is not None else "free (every non-allowlisted path)",
                    "sandbox": {"image": img["id"], "image_tag": img["tag"], "seccomp_sha256": sb["seccomp_sha256"], "ro_paths": ro,
                                "rw_nested": list(spec.rw_nested), "outside_copy": sb["outside_copy"], "max_cpus": spec.max_cpus,
                                "max_mem_gb": spec.max_mem_gb},
                    "refusal_list": [p.pattern for p in REFUSE], "syncs": []}
        problems = scan(dest, manifest, spec)
        manifest["build_scan_problems"] = problems
        _write_manifest(spec, dest, manifest)
        write_protected(spec, dest, manifest)
        if problems:
            raise SystemExit(f"build scan failed: {problems[:8]}")
        return manifest
    except BaseException:
        # never leave a half-built room behind silently: keep it for inspection but mark it
        (dest / "BUILD_FAILED.txt").write_text("build failed; see the builder output\n", encoding="utf-8")
        raise


def _write_manifest(spec: RoomSpec, dest: Path, manifest: dict) -> None:
    text = json.dumps(manifest, indent=1) + "\n"
    spec.manifest.parent.mkdir(parents=True, exist_ok=True)
    spec.manifest.write_text(text, encoding="utf-8", newline="\n")
    (dest / "CLEANROOM_MANIFEST.json").write_text(text, encoding="utf-8", newline="\n")


def _is_link(p: Path) -> bool:
    try:
        if p.is_symlink():
            return True
        return bool(getattr(os.lstat(p), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return False


def scan(dest: Path, manifest: dict, spec: RoomSpec, content_all: bool = True) -> list[str]:
    """Problems: allowlisted files missing / modified; links or junctions; Claude-control files other than the root placeholders;
    unexpected files outside the work areas; forbidden names; forbidden text in any text file (agent files included)."""
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
    works = spec.work_areas
    for dirpath, dirnames, filenames in os.walk(dest, followlinks=False):
        d = Path(dirpath)
        for name in list(dirnames):
            q = d / name
            rel = q.relative_to(dest).as_posix()
            if _is_link(q):
                probs.append(f"link / junction: {rel}")
                dirnames.remove(name)
            elif name == ".claude" and rel != ".claude":
                probs.append(f"nested .claude directory: {rel}")
        for name in filenames:
            q = d / name
            rel = q.relative_to(dest).as_posix()
            if _is_link(q):
                probs.append(f"link: {rel}")
                continue
            if name in ("CLAUDE.md", "CLAUDE.local.md", ".mcp.json") and rel not in listed:
                probs.append(f"unexpected Claude control file: {rel}")
            if rel.startswith(".claude/") and rel not in listed:
                probs.append(f"file in the read-only .claude directory: {rel}")
            in_work = works is None or any(rel.startswith(w) for w in works) or "/__pycache__/" in f"/{rel}"
            if rel not in listed and rel != "CLEANROOM_MANIFEST.json" and not in_work and rel != "BUILD_FAILED.txt":
                probs.append(f"unexpected file: {rel}")
            if NAMES_ALWAYS.search(rel):
                probs.append(f"forbidden name: {rel}")
            if rel in listed and spec.name in ("bench", "clean") and NAMES_ORCHESTRATOR.search(rel) and \
                    not any(rel.startswith(x) for x in spec.names_orchestrator_exempt):
                probs.append(f"orchestrator-side module name: {rel}")
            if content_all and not rel.startswith(".tmp/") and rel != "CLEANROOM_MANIFEST.json":
                try:
                    if _is_text(q) and q.stat().st_size < MAX_SCAN_BYTES:
                        hit = scan_text(q.read_text(encoding="utf-8", errors="ignore"))
                        if hit:
                            probs.append(f"forbidden content {hit!r} in {rel}")
                except OSError:
                    pass
    return probs


def sync(spec: RoomSpec, dest: Path, reason: str) -> dict:
    """Bring an existing room up to date with its allowlist: copy every allowlisted file whose source changed (or that is missing),
    update its manifest entry, record the sync, rescan. A file that is already identical but whose manifest entry is stale was copied
    by an interrupted sync: it is checked and recorded like any changed file. Work areas are untouched."""
    manifest = json.loads(spec.manifest.read_text(encoding="utf-8"))
    by_path = {e["path"]: e for e in manifest["files"]}
    changed = []
    for it in spec.items:
        dst = dest / it.path
        if it.source is None:
            content = (it.content or "").encode()
            if dst.exists() and _sha(dst) == _sha_bytes(content, True) and (by_path.get(it.path) or {}).get("sha256") == _sha(dst):
                continue
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
        if dst.exists() and _sha(dst) == _sha(src) and (by_path.get(it.path) or {}).get("sha256") == _sha(dst):
            continue
        why = check_source(src, it.path, spec) or _verify_locked(it, src)
        if why:
            raise SystemExit(f"refused {it.source} -> {it.path}: {why}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".sync_tmp")
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
        by_path[it.path] = _entry(it, dest)
        changed.append(it.path)
    paths = [p for p in by_path if p != "sbx"] + ["sbx", "CLEANROOM_MANIFEST.json"]
    ro = ro_paths(spec, paths)
    sb = install_sbx(spec, dest, ro)
    by_path["sbx"] = {"path": "sbx", "source": "generated from scripts/p4agent/sbx_template.sh", "destination": f"$ROOMS/{dest.name}/sbx",
                      "sha256": sb["sbx_sha256"], "bytes": (dest / "sbx").stat().st_size, "reason": "Docker sandbox wrapper",
                      "classification": "generated"}
    manifest["files"] = sorted(by_path.values(), key=lambda e: e["path"])
    manifest["n_files"] = len(manifest["files"])
    manifest["sandbox"].update({"ro_paths": ro, "seccomp_sha256": sb["seccomp_sha256"], "image": sb["image"]})
    manifest.setdefault("syncs", []).append({"time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "reason": reason,
                                             "files": changed})
    problems = scan(dest, manifest, spec)
    if problems:
        raise SystemExit(f"sync scan failed (manifest not written): {problems[:8]}")
    _write_manifest(spec, dest, manifest)
    write_protected(spec, dest, manifest)
    return {"changed": changed}


def audit(spec: RoomSpec, dest: Path) -> dict:
    manifest = json.loads(spec.manifest.read_text(encoding="utf-8"))
    problems = scan(dest, manifest, spec)
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
           "problems": problems, "ok": not problems}
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
        r = sync(spec, dest, args.sync)
        print(f"synced {dest}: {len(r['changed'])} files: {r['changed'][:50]}")
        return 0
    if args.audit:
        r = audit(spec, dest)
        print(json.dumps({k: v for k, v in r.items() if k != "unmanifested"}, indent=1))
        return 0 if r["ok"] else 1
    if args.destroy_and_rebuild:
        if dest.exists():
            if not re.match(r"(?i)^brainir_p4[a-z_]+$", dest.name):
                raise SystemExit(f"refusing to delete {dest}: not a Phase 4 room name")
            shutil.rmtree(dest)
        args.build = True
    if args.build:
        m = build(spec, dest, allow_missing=args.allow_missing, docker_check=not args.no_docker_check)
        print(f"built {dest}: {m['n_files']} files; scan clean; read-only in the sandbox: {m['sandbox']['ro_paths']}"
              + (f"; MISSING (test build): {m['incomplete_missing_sources']}" if m["incomplete_missing_sources"] else ""))
        return 0
    manifest = json.loads(spec.manifest.read_text(encoding="utf-8"))
    probs = scan(dest, manifest, spec)
    print("\n".join(probs) if probs else f"ok: {dest} matches its manifest ({manifest['n_files']} files) and holds no forbidden file")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
