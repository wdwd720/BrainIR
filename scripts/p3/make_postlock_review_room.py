"""Build the POST-LOCK review room for reviewers S, C, Y and R (goal4 section 70; research/phase3/review_contracts/POSTLOCK_*.txt).

    uv run --project phase3 --no-sync python scripts/p3/make_postlock_review_room.py [--dest C:\\Dev\\BrainIR_p3postreview]
        [--report PHASE3_REPORT.md] [--update] [--sync-env] [--prompts DIR] [--allow-missing]
    uv run --project phase3 --no-sync python scripts/p3/make_postlock_review_room.py --check [--dest ...]

Reviewer L (leakage, answer-aware) works in the main repository and needs no room.

The room holds what research/phase3/review_contracts/POSTLOCK_COMMON.txt promises. Everything is copied from the explicit source list
INCLUDE; nothing else of the repository is walked:
- docs/PROTOCOL.md (the frozen protocol, benchmark version 3), docs/review_contracts/ (POSTLOCK_COMMON and the S, C, Y, R tasks; never
  L's) and docs/goal4.md. goal4.md names earlier benchmarks in its header, so the room gets only the sections the post-lock contracts
  cite (GOAL4_SECTIONS), redacted like every other text;
- METHOD_LOCK.json and PHASE3_REPORT.md (the draft: --report, default PHASE3_REPORT.md, else research/phase3/REPORT_WORKING.md);
- src/brainir_state/ (phase3/src/brainir_state: the evaluator, the orchestrator modules, and methods/ = the LOCKED copy written by
  method_lock_p3.py, baselines included) and scripts/ (scripts/p3);
- results/:
  - tournament/: every Level B round incl. the confirmation round and the failed attempts. The reference-control cache _refcache/
    (0.4 GB of per-system controls) is left out; no reported number needs it;
  - level_c/, ablations/, counterexamples/, postlock_infra/;
  - review_g/: the trap results and the trap descriptions;
  - benchmark/: calibration, tolerances, the public system descriptions, the benchmark lock;
  - SELF_AUDIT.{json,md}, COMPUTE_SUMMARY.{json,md}, LEVELB_LOG.md, COSTS_LEDGER.md;
  - EVALUATION_LOG.md = research/phase3/HIDDEN_EVALUATIONS.md, renamed: the agents' tool guard refuses paths containing that name;
- pyproject.toml / .python-version (the clean room's standalone project; `uv run` works after --sync-env), a reviewer CLAUDE.md,
  README.md, and the work areas reviews/ and .tmp/.

Five layers keep answer-bearing material out:
1. DENY: a source-path denylist applied to every file a directory or glob entry would copy:
   - the Phase 0-2 reports, research/phase2/**, research/LOG.md, the repository CLAUDE.md;
   - benchmarks/dng100_walking_cpg/**, benchmarks/dng100/{oracle,evaluator,baselines}/**;
   - data/, the Phase 3 benchmark's hidden/ and generator/ directories, truth directories, salts, the network map, the internal system
     table, the synthetic suites' record;
   - the pre-lock reviews (research/phase3/reviews/**) and reviewer L's task.
2. Text files only. Every text file is redacted: dataset, paper and circuit names, and the clean-room answer-content class, become
   REDACTED. This is the pre-lock review builder's class plus the transcript audit's source names. Code must still parse. Binary
   files are not copied; they are listed in the manifest.
3. Scan of the built room (in a staging directory; a failed build never replaces the room):
   - names: the pre-lock review class minus the lock files and goal4.md, plus hidden/ directories and tier-A id files;
   - content: the redaction class;
   - answer tokens: the Phase 1 oracle's published types, core body ids and tier-A tokens, read at build time, with the rule of
     self_audit.py check I7 (non-numeric hits and numeric hits of 8 digits or more fail). Only classes and counts are recorded, never
     tokens.
4. Guard readability: every file outside scripts/ and src/ must be readable through the agents' tool guard
   (scripts/p3agent/guard_hook.py). Guard-blocked code files are listed.
5. --check re-verifies every hash against the manifest, flags unexpected files outside the work areas, and re-runs the scans.

Manifest: research/phase3/POSTLOCK_REVIEW_ROOM_MANIFEST[_<room>].json. It records the sha256 and source of every file, redaction
counts, exclusions, skipped binaries and the answer scan's classes. A copy without the answer-scan details goes to MANIFEST.json in
the room. A failed build writes ...FAILED.json instead and leaves the room untouched. --update rebuilds the content and keeps
reviews/, .tmp/ and the environment. --prompts DIR writes each reviewer's prompt (COMMON + task + room notes) for
scripts/p3agent/launch.py --prompt-file; DIR must be outside every room.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _d in ("scripts", "scripts/p3", "scripts/p3agent"):
    if str(REPO / _d) not in sys.path:
        sys.path.insert(0, str(REPO / _d))
import audit_transcripts as AT  # noqa: E402
import make_phase3_cleanroom as MK  # noqa: E402
import make_review_room as MR  # noqa: E402

DEST_DEFAULT = Path(r"C:\Dev\BrainIR_p3postreview")
WORK_AREAS = ("reviews/", ".tmp/", ".venv/", ".pytest_cache/")
ENV_FILES = ("uv.lock",)                                  # written by `uv sync` in the room
SKIP_WALK = (".venv", ".pytest_cache")
# goal4 sections the post-lock contracts cite:
#   7 success criteria, 53 counterexamples, 59 cost accounting, 68 statistics, 70 post-lock reviews, 84 reporting,
#   85 acceptance criteria, 86 method lock / tag, 87 self-audit, 88 claim language, 91 final response
GOAL4_SECTIONS = (7, 53, 59, 68, 70, 84, 85, 86, 87, 88, 91)
REVIEWERS = ("S", "C", "Y", "R")
EVAL_LOG = "results/EVALUATION_LOG.md"

# (source relative to the repository, destination relative to the room, required for a real post-lock build)
INCLUDE: list[tuple[str, str, bool]] = [
    ("benchmarks/state_discovery_v1/PROTOCOL.md", "docs/PROTOCOL.md", True),
    ("research/phase3/review_contracts/POSTLOCK_COMMON.txt", "docs/review_contracts/POSTLOCK_COMMON.txt", True),
    *[(f"research/phase3/review_contracts/POSTLOCK_{x}_TASK.txt", f"docs/review_contracts/POSTLOCK_{x}_TASK.txt", True) for x in REVIEWERS],
    ("research/phase3/METHOD_LOCK.json", "METHOD_LOCK.json", True),
    ("phase3/src/brainir_state", "src/brainir_state", True),
    ("scripts/p3", "scripts", True),
    ("research/phase3/tournament", "results/tournament", True),
    ("research/phase3/level_c", "results/level_c", True),
    ("research/phase3/ablations", "results/ablations", True),
    ("research/phase3/counterexamples", "results/counterexamples", True),
    ("research/phase3/postlock_infra", "results/postlock_infra", False),
    ("research/phase3/review_g/results_*.json", "results/review_g", False),
    ("research/phase3/review_g/REVIEW_G_TRAPS.md", "results/review_g/REVIEW_G_TRAPS.md", False),
    ("benchmarks/state_discovery_v1/calibration.json", "results/benchmark/calibration.json", True),
    ("benchmarks/state_discovery_v1/public/tolerances.json", "results/benchmark/tolerances.json", True),
    ("benchmarks/state_discovery_v1/public/systems_public.json", "results/benchmark/systems_public.json", True),
    ("benchmarks/state_discovery_v1/public/synthetic_dev_suite.json", "results/benchmark/synthetic_dev_suite.json", False),
    ("benchmarks/state_discovery_v1/BENCHMARK_LOCK.json", "results/benchmark/BENCHMARK_LOCK.json", True),
    ("research/phase3/SELF_AUDIT.json", "results/SELF_AUDIT.json", True),
    ("research/phase3/SELF_AUDIT.md", "results/SELF_AUDIT.md", True),
    ("research/phase3/COMPUTE_SUMMARY.json", "results/COMPUTE_SUMMARY.json", False),
    ("research/phase3/COMPUTE_SUMMARY.md", "results/COMPUTE_SUMMARY.md", True),
    ("research/phase3/HIDDEN_EVALUATIONS.md", EVAL_LOG, True),
    ("research/phase3/LEVELB_LOG.md", "results/LEVELB_LOG.md", True),
    ("research/phase3/COSTS_LEDGER.md", "results/COSTS_LEDGER.md", False),
    ("phase3/cleanroom/pyproject.toml", "pyproject.toml", True),
    (".python-version", ".python-version", True),
]

# layer 1: source paths that never enter (checked on every file a directory or glob entry expands to)
DENY = re.compile(r"(?i)((^|/)phase[0-2]_report\.md$|^claude\.md$|^research/phase2/|^research/log\.md$|^benchmarks/dng100_walking_cpg/|"
                  r"^benchmarks/dng100/(oracle|evaluator|baselines)/|^data/|^benchmarks/state_discovery_v1/(hidden|generator)/|"
                  r"(^|/)truth(/|$)|salt|network_map|systems_internal|synthetic_suites\.json|(^|/)_refcache(/|$)|"
                  r"^research/phase3/reviews/|postlock_l_task|(^|/)__pycache__(/|$)|\.pyc$|(^|/)\.pytest_cache(/|$))")


def _alternatives(pattern: str) -> list[str]:
    """Top-level alternatives of a '(?i)(a|b|...)' pattern (groups and character classes kept whole)."""
    body = pattern[len("(?i)("):-1]
    out, cur, depth, in_class, esc = [], "", 0, False, False
    for ch in body:
        if esc:
            cur, esc = cur + ch, False
            continue
        if ch == "\\":
            cur, esc = cur + ch, True
            continue
        if in_class:
            in_class = ch != "]"
        elif ch == "[":
            in_class = True
        elif ch in "()":
            depth += 1 if ch == "(" else -1
        elif ch == "|" and depth == 0:
            out.append(cur)
            cur = ""
            continue
        cur += ch
    return out + [cur]


# layer 2: the pre-lock review builder's redaction class plus the transcript audit's dataset / organism / source names (the names that
# self_audit.py I7 fails in any room; its file-name references such as the evaluation log's name are not source names)
_REF_LIKE = re.compile(r"phase2_report|hidden_eval|blind_eval|oracle|tier_a_ids|goal")
SOURCE_NAMES = [a for a in _alternatives(AT.NAMES.pattern) if not _REF_LIKE.search(a)]
REDACT = re.compile(MR.REDACT.pattern + "|" + "|".join(SOURCE_NAMES))
# layer 3 (names): the pre-lock review room's class minus what this room legitimately holds (the method and benchmark locks, goal4.md),
# plus hidden/ directories and tier-A id files
_NAME_DROP = {"method_lock", "benchmark_lock", r"goal[1-4]\.md"}
POSTLOCK_FORBIDDEN_NAMES = re.compile("(?i)(" + "|".join([a for a in _alternatives(MR.REVIEW_FORBIDDEN_NAMES.pattern) if a not in _NAME_DROP]
                                                        + [r"goal[1-3]\.md", r"(^|[\\/])hidden([\\/]|$)", r"tier_a_ids"]) + ")")

CLAUDE_MD = """# Phase 3 post-lock review room

You are a post-lock reviewer. Your task is in your first message. The contracts are in docs/review_contracts/, the layout is in
README.md, and every file's source is in MANIFEST.json.

Rules:
1. Work only inside this directory.
2. Write your review to reviews/POSTLOCK_<your letter>.md. Put scratch files in .tmp/.
3. Do not modify docs/, src/, scripts/, results/, METHOD_LOCK.json, PHASE3_REPORT.md, README.md or MANIFEST.json.
4. Use `uv run python ...` with at most 3 threads. The environment is synced; do not install packages. The modules that drive the
   real-circuit simulator need a library that is not in this room: read them, do not run them.
5. No web access.

{room_notes}"""

ROOM_NOTES = """Differences from the contracts' wording:
- The hidden-evaluation log, called HIDDEN_EVALUATIONS.md in the contracts, is results/EVALUATION_LOG.md here. The room's tool guard
  refuses paths that contain the original name.
- Dataset, paper and circuit names in the copies are replaced by REDACTED (counts per file in MANIFEST.json). Nothing else differs
  from the sources.
- docs/goal4.md holds only the sections the contracts cite.
"""

README_MD = """# Post-lock review room: layout

| path | content | source |
|---|---|---|
| docs/PROTOCOL.md | the frozen, pre-registered evaluation protocol (benchmark version 3) | benchmarks/state_discovery_v1/PROTOCOL.md |
| docs/goal4.md | the phase specification: sections {sections} (the ones the contracts cite) | goal4.md |
| docs/review_contracts/ | the post-lock review contracts (common part; tasks S, C, Y, R) | research/phase3/review_contracts/ |
| METHOD_LOCK.json | the method lock (source hashes, configuration, seeds, budgets, environment) | research/phase3/METHOD_LOCK.json |
| PHASE3_REPORT.md | the DRAFT report under review | {report} |
| src/brainir_state/ | the evaluator and the orchestrator modules; methods/ = the locked method and the baselines | phase3/src/brainir_state/ |
| scripts/ | orchestration and analysis: tournament, method lock, Level C, ablations, counterexamples, self-audit, compute summary | scripts/p3/ |
| results/tournament/ | every Level B round incl. the confirmation round and failed attempts (per-candidate results, aggregates, decisions, Modal costs) | research/phase3/tournament/ |
| results/level_c/ | Level C: level_c/<attempt>/level_c_results.json, plus the Modal backend checks | research/phase3/level_c/ |
| results/ablations/, results/counterexamples/ | ablation and counterexample runs (SUMMARY.json per run; jobs/ per search) | research/phase3/ |
| results/postlock_infra/ | local vs Modal equivalence checks of the post-lock tools | research/phase3/postlock_infra/ |
| results/review_g/ | the adversarial trap suite: results and trap descriptions | research/phase3/review_g/ |
| results/benchmark/ | calibration, tolerances, public system descriptions, the benchmark lock | benchmarks/state_discovery_v1/ |
| results/EVALUATION_LOG.md | the log of every hidden evaluation (HIDDEN_EVALUATIONS.md in the contracts) | research/phase3/HIDDEN_EVALUATIONS.md |
| results/SELF_AUDIT.*, COMPUTE_SUMMARY.*, LEVELB_LOG.md, COSTS_LEDGER.md | self-audit, compute and cost summary, tournament log, cost ledger | research/phase3/ |
| reviews/, .tmp/ | your work areas | |

Not here: raw data (trajectories), fitted models and other binary files ({n_binary} listed in MANIFEST.json), truth files, seeds and
salts, the per-system reference-control cache, earlier reviews, and all Phase 1-2 material.
{guard_note}"""


# ------------------------------------------------------------------------------------------------ helpers
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _is_text(p: Path) -> bool:
    return p.suffix.lower() in MK.TEXT_SUFFIXES or p.name == ".python-version"


def _redact(text: str) -> tuple[str, int]:
    return REDACT.subn("REDACTED", text)


def _walk(base: Path) -> list[str]:
    """Files under base (relative, POSIX), without descending into the environment."""
    out = []
    for d, dirs, files in os.walk(base):
        dirs[:] = sorted(x for x in dirs if not (Path(d) == base and x in SKIP_WALK))
        out += [(Path(d) / f).relative_to(base).as_posix() for f in files]
    return sorted(out)


def _in_work_area(rel: str) -> bool:
    return rel.startswith(WORK_AREAS) or rel in ENV_FILES or rel == "MANIFEST.json"


def _manifest_path(root: Path, dest: Path, failed: bool = False) -> Path:
    name = "POSTLOCK_REVIEW_ROOM_MANIFEST" + ("" if dest.name == DEST_DEFAULT.name else f"_{dest.name}")
    return root / "research" / "phase3" / (name + (".FAILED.json" if failed else ".json"))


def _room_manifest_text(man: dict) -> str:
    """The room's copy: the answer scan reduced to its status (its classes stay with the orchestrator), redacted like every text."""
    room = {**man, "answer_scan": {"status": man["answer_scan"]["status"]}}
    return _redact(json.dumps(room, indent=1) + "\n")[0]


def _deny_prefix(file_rel: str) -> str:
    """The shortest leading part of an excluded path that the denylist matches (the manifest counts exclusions per prefix)."""
    parts = file_rel.split("/")
    for i in range(1, len(parts) + 1):
        pre = "/".join(parts[:i])
        if i < len(parts) and DENY.search(pre + "/"):
            return pre + "/"
        if DENY.search(pre):
            return pre
    return file_rel


def goal4_sections(text: str, wanted: tuple[int, ...]) -> tuple[str, list[int]]:
    """The top-level sections of goal4.md (a title line 'N. TITLE' between two '=====' lines) whose number is wanted."""
    lines = text.splitlines()
    heads = []
    for i in range(len(lines) - 2):
        if re.fullmatch(r"=+", lines[i].strip()) and re.fullmatch(r"=+", lines[i + 2].strip()):
            m = re.match(r"^(\d+)\.\s+\S", lines[i + 1].strip())
            if m:
                heads.append((int(m.group(1)), i))
    out, found = [], []
    for k, (num, start) in enumerate(heads):
        if num in wanted:
            end = heads[k + 1][1] if k + 1 < len(heads) else len(lines)
            out.extend(lines[start:end])
            found.append(num)
    header = (f"# goal4.md: the sections the post-lock review contracts cite ({', '.join(str(n) for n in found)})\n\n"
              "Only these sections are copied here, redacted like every text in this room.\n\n")
    return header + "\n".join(out).strip() + "\n", found


def _expand(root: Path, src_rel: str) -> list[tuple[Path, str]]:
    """Files of one INCLUDE source: (path, path relative to the repository)."""
    if any(c in src_rel for c in "*?["):
        base = root / Path(src_rel).parent
        return [(p, p.relative_to(root).as_posix()) for p in sorted(base.glob(Path(src_rel).name)) if p.is_file()]
    src = root / src_rel
    if src.is_file():
        return [(src, src_rel)]
    if src.is_dir():
        return [(src / rel, f"{src_rel}/{rel}") for rel in _walk(src)]
    return []


def _dest_rel(src_entry: str, dst_entry: str, file_rel: str) -> str:
    if any(c in src_entry for c in "*?["):
        return f"{dst_entry}/{Path(file_rel).name}"
    return dst_entry if file_rel == src_entry else f"{dst_entry}/{file_rel[len(src_entry) + 1:]}"


# ------------------------------------------------------------------------------------------------ scans
def scan(dest: Path, files: list[str]) -> list[str]:
    """Layer 3 (names and content classes). Problems name the file, never the matched text."""
    probs = []
    for rel in files:
        if POSTLOCK_FORBIDDEN_NAMES.search(rel):
            probs.append(f"forbidden name: {rel}")
        p = dest / rel
        if _is_text(p) and p.stat().st_size < 200_000_000:
            text = p.read_text(encoding="utf-8", errors="ignore")
            if MK.FORBIDDEN_CONTENT.search(text) or REDACT.search(text):
                probs.append(f"forbidden content class in {rel}")
    return probs


def load_answer_tokens() -> set[str]:
    """The Phase 1 oracle's published types, core body ids and tier-A tokens (the transcript audit's loader; answer-aware)."""
    toks, _positions = AT.answer_tokens()
    return {str(t) for t in toks if str(t)}


def answer_token_regex(tokens: set[str]) -> re.Pattern | None:
    toks = sorted({t for t in tokens if t}, key=len, reverse=True)
    if not toks:
        return None
    return re.compile("|".join(rf"(?<![0-9A-Za-z#]){re.escape(t)}(?![0-9A-Za-z])" for t in toks))


def answer_scan(dest: Path, files: list[str], tok_re: re.Pattern | None) -> dict:
    """The rule of self_audit.py I7 on every text file of the room. Non-numeric hits and numeric hits of 8 digits or more fail;
    shorter numeric hits are coincidences and are only counted. Classes and counts only; the tokens never leave this function."""
    if tok_re is None:
        return {"status": "skipped"}
    classes: Counter = Counter()
    failing = []
    for rel in files:
        p = dest / rel
        if not _is_text(p) or p.stat().st_size >= 200_000_000:
            continue
        bad = False
        for m in tok_re.finditer(p.read_text(encoding="utf-8", errors="ignore")):
            t = m.group(0)
            classes[f"numeric-{len(t)}-digits" if t.isdigit() else "non-numeric"] += 1
            bad |= (not t.isdigit()) or len(t) >= 8
        if bad:
            failing.append(rel)
    return {"status": "FAIL" if failing else "clean", "classes": dict(sorted(classes.items())), "failing_files": failing}


def guard_blocked(room: Path, files: list[str]) -> list[str]:
    """Room files whose path the agents' tool guard refuses (its substring classes), so a reviewer could not open them with a tool.
    The guard module is loaded privately, configured for this room; the guard used by running agents is not touched."""
    spec = importlib.util.spec_from_file_location("_postlock_guard_probe", REPO / "scripts" / "p3agent" / "guard_hook.py")
    mod = importlib.util.module_from_spec(spec)
    old = os.environ.get("P3_CLEAN_ROOT")
    os.environ["P3_CLEAN_ROOT"] = str(room)
    try:
        spec.loader.exec_module(mod)
    finally:
        if old is None:
            os.environ.pop("P3_CLEAN_ROOT", None)
        else:
            os.environ["P3_CLEAN_ROOT"] = old
    return [rel for rel in files if mod._forbidden_text(rel)]


# ------------------------------------------------------------------------------------------------ build / check
def build(root: Path, dest: Path, report: str | None = None, update: bool = False, allow_missing: bool = False,
          answer_tokens: set[str] | None = None, prompts: Path | None = None) -> dict:
    """Build (or with update=True, rebuild) the room. answer_tokens=None loads them from the Phase 1 oracle; an empty set skips the
    answer scan (tests, dry runs)."""
    root, dest = root.resolve(), dest.resolve()
    if dest.exists() and not update:
        raise SystemExit(f"{dest} exists (use --update to rebuild its content; reviews/ and .tmp/ are kept)")
    if update and not dest.is_dir():
        raise SystemExit(f"{dest} does not exist (build it first)")
    if prompts is not None and prompts.resolve().is_relative_to(dest):
        raise SystemExit("--prompts must be outside the room")
    stage = dest.with_name(dest.name + ".staging")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    files: dict[str, dict] = {}
    excluded: Counter = Counter()
    skipped_binary, absent, probs = [], [], []

    def put_text(rel: str, text: str, source: str) -> None:
        red, n = _redact(text)
        if rel.endswith(".py"):
            try:
                ast.parse(red)
            except SyntaxError as e:
                probs.append(f"{rel} does not parse after redaction (line {e.lineno})")
        out = stage / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(red, encoding="utf-8", newline="\n")
        files[rel] = {"sha256": _sha(out), "source": source, **({"redactions": n} if n else {})}

    def copy_file(p: Path, file_rel: str, rel: str) -> None:
        if not _is_text(p):
            skipped_binary.append(f"$REPO/{file_rel}")
            return
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            probs.append(f"not UTF-8 text: $REPO/{file_rel}")
            return
        put_text(rel, text, f"$REPO/{file_rel}")

    try:
        for src_rel, dst_rel, required in INCLUDE:
            items = _expand(root, src_rel)
            if not items:
                absent.append(src_rel)
                if required and not allow_missing:
                    raise SystemExit(f"required source missing: {src_rel} (--allow-missing builds a partial room)")
                continue
            for p, file_rel in items:
                if DENY.search(file_rel):
                    excluded[_deny_prefix(file_rel)] += 1
                    continue
                copy_file(p, file_rel, _dest_rel(src_rel, dst_rel, file_rel))
        rep = next((c for c in ([report] if report else []) + ["PHASE3_REPORT.md", "research/phase3/REPORT_WORKING.md"]
                    if (root / c).is_file()), None)
        if rep:
            copy_file(root / rep, rep, "PHASE3_REPORT.md")
        else:
            absent.append(report or "PHASE3_REPORT.md")
            if not allow_missing:
                raise SystemExit("no report draft (PHASE3_REPORT.md or research/phase3/REPORT_WORKING.md)")
        found: list[int] = []
        if (root / "goal4.md").is_file():
            g4, found = goal4_sections((root / "goal4.md").read_text(encoding="utf-8"), GOAL4_SECTIONS)
            missing = sorted(set(GOAL4_SECTIONS) - set(found))
            if missing and not allow_missing:
                raise SystemExit(f"goal4.md: sections {missing} not found")
            put_text("docs/goal4.md", g4, f"$REPO/goal4.md (sections {found})")
        else:
            absent.append("goal4.md")
            if not allow_missing:
                raise SystemExit("goal4.md missing")
        code = ("scripts/", "src/")
        blocked = guard_blocked(dest, sorted(files))
        probs += [f"not readable through the agents' tool guard: {rel}" for rel in blocked if not rel.startswith(code)]
        blocked_code = [rel for rel in blocked if rel.startswith(code)]
        guard_note = ("\nNot readable with the tools (the tool guard refuses their names; they are the Python guards of the Modal and "
                      "remote-runner jobs and play no part in the results): " + ", ".join(blocked_code) + "\n") if blocked_code else ""
        put_text("CLAUDE.md", CLAUDE_MD.format(room_notes=ROOM_NOTES), "generated")
        put_text("README.md", README_MD.format(sections=", ".join(str(n) for n in found) or "(none)", report=rep or "(absent)",
                                               n_binary=len(skipped_binary), guard_note=guard_note), "generated")
        for w in ("reviews", ".tmp"):
            (stage / w).mkdir(exist_ok=True)
        rels = sorted(files)
        probs += scan(stage, rels)
        tok_re = answer_token_regex(load_answer_tokens() if answer_tokens is None else answer_tokens)
        ans = answer_scan(stage, rels, tok_re)
        if ans["status"] == "FAIL":
            probs.append(f"answer tokens in {len(ans['failing_files'])} file(s) (classes in the orchestrator's manifest)")
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    removed = sorted(rel for rel in (_walk(dest) if update else []) if rel not in files and not _in_work_area(rel))
    man = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "builder": "$REPO/scripts/p3/make_postlock_review_room.py",
           "room": "$EXTERNAL/" + dest.name, "source_root": "$REPO", "update": update, "status": "FAILED" if probs else "ok",
           "n_files": len(files), "files": dict(sorted(files.items())),
           "redactions_total": sum(e.get("redactions", 0) for e in files.values()),
           "excluded_sources": dict(sorted(excluded.items())), "skipped_binary": sorted(skipped_binary), "absent_sources": sorted(absent),
           "goal4_sections": found, "report_source": rep, "guard_unreadable_code": blocked_code, "removed_on_update": removed,
           "scan_problems": probs, "answer_scan": ans}
    good, bad = _manifest_path(root, dest), _manifest_path(root, dest, failed=True)
    good.parent.mkdir(parents=True, exist_ok=True)
    if probs:
        shutil.rmtree(stage, ignore_errors=True)
        bad.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8", newline="\n")
        raise SystemExit(f"room NOT built ({len(probs)} problems; see {bad.relative_to(root).as_posix()}): {probs[:5]}")
    if update:
        for rel in _walk(dest):
            if not _in_work_area(rel):
                (dest / rel).unlink()
        content_dirs = []
        for d, dirs, _files in os.walk(dest):
            if Path(d) == dest:
                dirs[:] = [x for x in dirs if x + "/" not in WORK_AREAS]
            else:
                content_dirs.append(Path(d))
        for d in sorted(content_dirs, key=lambda p: len(p.parts), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
        for rel in files:
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage / rel, dest / rel)
        for w in ("reviews", ".tmp"):
            (dest / w).mkdir(exist_ok=True)
        shutil.rmtree(stage)
    else:
        stage.rename(dest)
    (dest / "MANIFEST.json").write_text(_room_manifest_text(man), encoding="utf-8", newline="\n")
    good.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8", newline="\n")
    bad.unlink(missing_ok=True)
    if prompts is not None:
        write_prompts(dest, prompts)
    return man


def write_prompts(dest: Path, out: Path) -> list[Path]:
    """One prompt per reviewer for launch.py --prompt-file: the room's (redacted) COMMON contract, the reviewer's task, the room notes."""
    out.mkdir(parents=True, exist_ok=True)
    common = (dest / "docs" / "review_contracts" / "POSTLOCK_COMMON.txt").read_text(encoding="utf-8")
    paths = []
    for x in REVIEWERS:
        task = (dest / "docs" / "review_contracts" / f"POSTLOCK_{x}_TASK.txt").read_text(encoding="utf-8")
        p = out / f"postlock_{x}.txt"
        p.write_text(common.rstrip() + "\n\n" + task.rstrip() + "\n\n" + ROOM_NOTES, encoding="utf-8", newline="\n")
        paths.append(p)
    return paths


def check(root: Path, dest: Path, answer_tokens: set[str] | None = None) -> list[str]:
    root, dest = root.resolve(), dest.resolve()
    mp = _manifest_path(root, dest)
    if not mp.exists():
        return [f"no manifest {mp.name}"]
    if not dest.is_dir():
        return [f"no room at {dest}"]
    man = json.loads(mp.read_text(encoding="utf-8"))
    probs = []
    for rel, e in man["files"].items():
        p = dest / rel
        if not p.is_file():
            probs.append(f"missing: {rel}")
        elif _sha(p) != e["sha256"]:
            probs.append(f"modified: {rel}")
    mr = dest / "MANIFEST.json"
    if not mr.is_file() or mr.read_text(encoding="utf-8") != _room_manifest_text(man):
        probs.append("MANIFEST.json in the room differs from the orchestrator's manifest")
    present = _walk(dest)
    probs += [f"unexpected: {rel}" for rel in present if rel not in man["files"] and not _in_work_area(rel)]
    probs += scan(dest, present)
    tok_re = answer_token_regex(load_answer_tokens() if answer_tokens is None else answer_tokens)
    ans = answer_scan(dest, present, tok_re)
    if ans["status"] == "FAIL":
        probs.append(f"answer tokens in {len(ans['failing_files'])} file(s): {ans['failing_files'][:10]}")
    return probs


def sync_env(dest: Path) -> None:
    """`uv sync` in the room (the orchestrator runs it; agents cannot install packages)."""
    uv = shutil.which("uv") or str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" /
                                   "astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe" / "uv.exe")
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")}
    subprocess.run([uv, "sync"], cwd=str(dest), env=env, check=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(REPO), help="the repository to copy from (tests use a fake tree)")
    ap.add_argument("--dest", default=str(DEST_DEFAULT))
    ap.add_argument("--report", default=None, help="the report draft, relative to the repository")
    ap.add_argument("--update", action="store_true", help="rebuild the content of an existing room (reviews/, .tmp/, .venv/ kept)")
    ap.add_argument("--check", action="store_true", help="verify the room against its manifest and rescan it")
    ap.add_argument("--sync-env", action="store_true", help="run `uv sync` in the room after building it")
    ap.add_argument("--prompts", default=None, help="write the reviewers' prompt files here (outside every room)")
    ap.add_argument("--allow-missing", action="store_true", help="build even if required sources are absent (dry runs)")
    ap.add_argument("--no-answer-scan", action="store_true", help="skip the oracle answer-token scan (tests and dry runs only)")
    args = ap.parse_args(argv)
    root, dest = Path(args.root), Path(args.dest)
    tokens = set() if args.no_answer_scan else None
    if args.check:
        probs = check(root, dest, tokens)
        if probs:
            print("POST-LOCK REVIEW ROOM CHECK FAILED:\n  " + "\n  ".join(probs[:40]))
            return 1
        print(f"post-lock review room ok: {dest} (answer scan {'skipped' if args.no_answer_scan else 'clean'})")
        return 0
    man = build(root, dest, args.report, args.update, args.allow_missing, tokens, Path(args.prompts) if args.prompts else None)
    if args.sync_env:
        sync_env(dest)
    print(f"{'updated' if args.update else 'built'} {dest}: {man['n_files']} files, {man['redactions_total']} redactions in "
          f"{sum(1 for e in man['files'].values() if e.get('redactions'))} files, excluded {sum(man['excluded_sources'].values())} "
          f"source files ({', '.join(man['excluded_sources']) or 'none'}), {len(man['skipped_binary'])} binary files skipped, "
          f"absent: {man['absent_sources'] or 'none'}; goal4 sections {man['goal4_sections']}; answer scan {man['answer_scan']['status']}"
          + (f"; prompts in {args.prompts}" if args.prompts else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
