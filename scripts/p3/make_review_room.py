"""Build a pre-lock review room for reviews A-E and H (orchestrator; research/phase3/REVIEW_PLAN.md).

    uv run --project phase3 python scripts/p3/make_review_room.py [--src C:\\Dev\\BrainIR_p3clean] [--dest C:\\Dev\\BrainIR_p3review]
        [--extras eh] [--update]

The review room is a snapshot of the clean room:
- the public modules, docs and data (data files hard-linked);
- the candidate methods, notes, tests and runs;
- the aggregate tournament feedback;
- an empty reviews/ directory and a reviewer CLAUDE.md.

`--extras eh` adds, under extra/, the orchestrator-side material that reviews E (statistics) and H (numerical methods) need:
- the evaluation and simulation modules the methods never see;
- the statistics / tournament / Level C scripts;
- the synthetic generator;
- the public calibration;
- the frozen rate-model integrator.
Nothing hidden enters: no salt, truth, network map, internal system table or hidden suite. Dataset, paper and bundle names are replaced
by REDACTED in these copies (the code is otherwise byte-identical; the count per file is in extra/README.md), so the reviewers stay
blind to which real circuits are simulated.

`--update` re-syncs an existing room from the clean room: new and changed methods, notes, tests and feedback. The reviewers' own files
(reviews/, .tmp/) are kept. Nothing is deleted.

Every file is scanned with the clean-room builder's answer-content class. Names are checked against the forbidden-name class, minus the
orchestrator module names the review plan gives to review H. The manifest (every non-data file with its hash) goes to
research/phase3/REVIEW_ROOM_MANIFEST[_<room>].json.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import make_phase3_cleanroom as MK  # noqa: E402

REVIEW_CLAUDE_MD = """# Phase 3 pre-lock review room

You review a state-discovery method and its evaluation before the method is locked. Your task is in your first message. This room is a
snapshot of the method developers' room:
- src/brainir_state (the public evaluator, the method API and the candidate methods);
- notes/ (the developers' notes);
- docs/ (PROTOCOL.md, the development contract, the methods review);
- data/ (public data);
- notes/_tournament_feedback.md (aggregate held-out results, once the tournament has run).
{extra}
Rules:
1. Work only inside this directory; nothing outside it is reachable.
2. Write your review to reviews/<your letter>_review.md.
3. Do not modify src/, notes/, docs/, extra/ or data/.
4. Use `uv run` (environment already synced) with at most 3 threads.
5. No web access.
"""

EXTRA_NOTE = """- extra/ (orchestrator-side code the method developers never see: the evaluation driver, the simulators, the synthetic generator,
  the statistics and tournament scripts, the public calibration; see extra/README.md).
"""

SKIP = (".venv/", "simq/", ".tmp/", ".pytest_cache/", "reviews/")

# the clean-room builder's forbidden-name class minus the orchestrator module names (realsim, realgen, simservice, synthsim,
# suite_eval, evaluate_synth) and the public calibration, which the review plan gives to reviews E and H
REVIEW_FORBIDDEN_NAMES = re.compile(r"(?i)(phase2_report|phase1_report|phase0_report|hidden_eval|blind_eval|oracle|method_lock|"
                                    r"benchmark_lock|(^|[\\/])truth([\\/]|$)|build_report|audit_report|synthetic_truth|salt|"
                                    r"synthetic_suites\.json|network_map|systems_internal|goal[1-4]\.md|dng100_walking)")
# redaction in the extra copies: real-data identities (dataset, paper, bundle names) and the answer-content class
assert MK.FORBIDDEN_CONTENT.pattern.startswith("(?i)(") and MK.FORBIDDEN_CONTENT.pattern.endswith(")")
REDACT = re.compile(r"(?i)\bmanc[\w.]*|male[-_]?cns[\w.]*|\bdng\d+\w*|pugliese\w*|" + MK.FORBIDDEN_CONTENT.pattern[5:-1])

P3 = "phase3/src/brainir_state/"
EXTRAS = {
    "eh": [
        *[(P3 + m, "extra/orchestrator/brainir_state/" + m) for m in (
            "evaluate_synth.py", "realgen.py", "realsim.py", "runguard.py", "runner.py", "simservice.py", "store.py", "suite_eval.py",
            "synthsim.py")],
        *[(f"scripts/p3/{s}", f"extra/scripts/{s}") for s in (
            "build_synthetic_suites.py", "calibrate.py", "counterexamples.py", "feedback.py", "generate_real_data.py",
            "generate_real_hidden.py", "level_c.py", "merge_rounds.py", "precompute_refs.py", "simservice_systems.py", "tournament.py")],
        *[(f"phase3/tests/{t}", f"extra/tests/{t}") for t in ("test_evaluate.py", "test_phase3_infra.py", "test_protocol_store.py")],
        ("benchmarks/state_discovery_v1/calibration.json", "extra/benchmark/calibration.json"),
        ("benchmarks/state_discovery_v1/public/tolerances.json", "extra/benchmark/tolerances.json"),
        ("benchmarks/state_discovery_v1/public/synthetic_dev_suite.json", "extra/benchmark/synthetic_dev_suite.json"),
        ("src/brainir/sim/model.py", "extra/frozen_rate_model/model.py"),
        ("benchmarks/state_discovery_v1/generator", "extra/generator"),
    ],
}

EXTRA_README = """# extra/ (orchestrator-side material for reviews E and H)

Copied by scripts/p3/make_review_room.py --extras eh. The method developers never see these files.

- orchestrator/brainir_state/: the modules that run next to the public evaluator, which is in src/brainir_state:
  - suite_eval.py (fits in the sandbox, evaluation jobs, reference controls);
  - evaluate_synth.py (K latent recovery, L abstention);
  - realsim.py / realgen.py (piecewise real-circuit engine, real protocol generation);
  - synthsim.py (synthetic dispatch);
  - simservice.py / store.py (budgeted simulation service);
  - runner.py / runguard.py (sandboxed fit and evaluation).
- scripts/: the tournament driver, round merging, developer feedback, the calibration, the suite builder with the microstate pools,
  real public / hidden data generation, reference precompute, the Level C driver and the counterexample search.
- tests/: the evaluator and infrastructure tests.
- benchmark/: the public calibration (dev suite only), the tolerances and the public dev-suite record.
- frozen_rate_model/model.py: the frozen rate-model integrator that realsim.py composes piece by piece.
- generator/: the synthetic benchmark generator (p3synth), its tests and documentation. Held-out and final suites are this catalogue
  under secret seeds; neither the seeds nor any truth file is here.

Imports: these modules import `brainir_state` (installed here) and, for the real engine, the frozen `brainir` package (not installed
here), so the real engine cannot run in this room; read it. The generator runs:
`uv run python -c "import sys; sys.path.insert(0, 'extra/generator'); import p3synth"`.

Redaction: dataset, paper and bundle names are replaced by REDACTED. Nothing else differs from the source.

| file | replacements |
|---|---|
{rows}
"""


def _redact(text: str) -> tuple[str, int]:
    out, n = REDACT.subn("REDACTED", text)
    return out, n


def _copy_extras(dest: Path, key: str) -> tuple[list[str], list[tuple[str, int]]]:
    files, counts = [], []
    for src_rel, dst_rel in EXTRAS[key]:
        src = ROOT / src_rel
        items = ([(src, dest / dst_rel)] if src.is_file() else
                 [(p, dest / dst_rel / p.relative_to(src)) for p in sorted(src.rglob("*"))
                  if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"])
        for s, d in items:
            d.parent.mkdir(parents=True, exist_ok=True)
            if s.suffix in MK.TEXT_SUFFIXES:
                text, n = _redact(s.read_text(encoding="utf-8"))
                if s.suffix == ".py":
                    ast.parse(text)                                   # redaction must keep the code valid
                d.write_text(text, encoding="utf-8", newline="\n")
                if n:
                    counts.append((d.relative_to(dest).as_posix(), n))
            else:
                shutil.copy2(s, d)
            files.append(d.relative_to(dest).as_posix())
    rows = "\n".join(f"| {f} | {n} |" for f, n in counts) or "| (none) | 0 |"
    (dest / "extra" / "README.md").write_text(EXTRA_README.format(rows=rows), encoding="utf-8", newline="\n")
    files.append("extra/README.md")
    return files, counts


def _snapshot(src: Path, dest: Path, update: bool) -> list[str]:
    files = []
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(src).as_posix()
        if rel.startswith(SKIP) or "/__pycache__/" in f"/{rel}" or rel == "CLAUDE.md":
            continue
        out = dest / rel
        files.append(rel)
        if update and out.exists() and (rel.startswith("data/") or out.read_bytes() == p.read_bytes()):
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            out.unlink()
        if rel.startswith("data/"):
            os.link(p, out)
        else:
            shutil.copy2(p, out)
    return files


def _scan(dest: Path, files: list[str]) -> list[str]:
    probs = []
    for rel in files:
        if REVIEW_FORBIDDEN_NAMES.search(rel):
            probs.append(f"forbidden name {rel}")
        p = dest / rel
        if p.suffix in MK.TEXT_SUFFIXES and p.stat().st_size < 20_000_000:
            text = p.read_text(encoding="utf-8", errors="ignore")
            m = MK.FORBIDDEN_CONTENT.search(text) or (REDACT.search(text) if rel.startswith("extra/") else None)
            if m:
                probs.append(f"forbidden content {m.group(0)!r} in {rel}")
    return probs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(MK.CLEAN))
    ap.add_argument("--dest", default=r"C:\Dev\BrainIR_p3review")
    ap.add_argument("--extras", choices=sorted(EXTRAS), default=None)
    ap.add_argument("--update", action="store_true", help="re-sync an existing room (keeps reviews/)")
    args = ap.parse_args(argv)
    src, dest = Path(args.src), Path(args.dest)
    if dest.exists() and not args.update:
        raise SystemExit(f"{dest} exists (use --update to re-sync)")
    if args.update and not dest.exists():
        raise SystemExit(f"{dest} does not exist")
    files = _snapshot(src, dest, args.update)
    redactions = []
    if args.extras:
        extra_files, redactions = _copy_extras(dest, args.extras)
        files += extra_files
    elif args.update and (dest / "extra").exists():
        files += [p.relative_to(dest).as_posix() for p in sorted((dest / "extra").rglob("*")) if p.is_file()]
    has_extra = (dest / "extra").exists()
    (dest / "CLAUDE.md").write_text(REVIEW_CLAUDE_MD.format(extra=EXTRA_NOTE if has_extra else ""), encoding="utf-8", newline="\n")
    (dest / "reviews").mkdir(exist_ok=True)
    probs = _scan(dest, files)
    man = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "room": "$EXTERNAL/" + dest.name,
           "source_room": "$EXTERNAL/" + src.name, "extras": args.extras, "update": args.update, "n_files": len(files),
           "scan_problems": probs, "redactions": dict(redactions),
           "files": {rel: hashlib.sha256((dest / rel).read_bytes()).hexdigest() for rel in files if not rel.startswith("data/")},
           "data_files": sum(1 for rel in files if rel.startswith("data/"))}
    name = "REVIEW_ROOM_MANIFEST.json" if dest.name == "BrainIR_p3review" else f"REVIEW_ROOM_MANIFEST_{dest.name}.json"
    (ROOT / "research" / "phase3" / name).write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8", newline="\n")
    if probs:
        raise SystemExit(f"scan problems: {probs[:5]}")
    print(f"{'updated' if args.update else 'built'} {dest}: {len(files)} files; {sum(n for _, n in redactions)} redactions; scan clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
