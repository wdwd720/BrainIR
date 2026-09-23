"""Guard against leaking the DNg100 benchmark answer into BrainIR library code.

BrainIR discovery algorithms must never be given the published minimal circuit.
The library (src/brainir) may know about DNg100 only as a generic neuron type
(it is the *stimulus* of the benchmark, not its answer) and must not contain
the names/IDs of the published rhythm-generating interneurons, nor import the
benchmark answer key.
"""

from __future__ import annotations

import re
from pathlib import Path

from brainir import paths

SRC = paths.repo_root() / "src" / "brainir"
ANSWER_KEY_TOKENS = [
    # published CPG interneuron types (Pugliese et al.)
    "IN17A001", "INXXX466", "IN16B036", "IN19A007", "IN19B012", "IN03A006", "INXXX464",
    # MaleCNS body IDs reported for the minimal circuits (mCNS extraction used by the paper)
    "800173", "800863", "801884", "800374", "800216", "800663", "800286",
    # MANC body IDs of the canonical circuit
    "10707", "11751", "13905",
]


def _library_files() -> list[Path]:
    return [p for p in SRC.rglob("*.py")]


def test_library_contains_no_answer_key_tokens():
    offenders = []
    for p in _library_files():
        text = p.read_text(encoding="utf-8")
        for tok in ANSWER_KEY_TOKENS:
            if re.search(rf"(?<![0-9A-Za-z]){re.escape(tok)}(?![0-9A-Za-z])", text):
                offenders.append((p.relative_to(SRC).as_posix(), tok))
    assert not offenders, f"answer-key tokens found in library code: {offenders}"


CLEAN_DOCS = ["README.md", "CLAUDE.md", "docs", "research/data_ecosystem.md", "research/connectome_ecosystem_survey.md",
              "research/LOG.md", "data/README.md"]


def test_non_answer_docs_are_clean():
    """Docs that a future (LLM-based) component might read as context must not carry the answer."""
    root = paths.repo_root()
    offenders = []
    for rel in CLEAN_DOCS:
        p = root / rel
        files = [p] if p.is_file() else sorted(p.rglob("*.md")) if p.is_dir() else []
        for f in files:
            text = f.read_text(encoding="utf-8")
            for tok in ANSWER_KEY_TOKENS:
                if re.search(rf"(?<![0-9A-Za-z]){re.escape(tok)}(?![0-9A-Za-z])", text):
                    offenders.append((f.relative_to(root).as_posix(), tok))
    assert not offenders, f"answer-key tokens in non-answer docs: {offenders}"


def test_library_does_not_import_benchmarks_or_research():
    pat = re.compile(r"^\s*(from|import)\s+(benchmarks|research)\b", re.M)
    offenders = [p.relative_to(SRC).as_posix() for p in _library_files() if pat.search(p.read_text(encoding="utf-8"))]
    assert not offenders, offenders


def test_benchmark_answer_key_is_labelled():
    bench = paths.repo_root() / "benchmarks" / "dng100_walking_cpg"
    readme = bench / "README.md"
    assert readme.exists(), "benchmark README with leakage policy is required"
    assert "ANSWER KEY" in readme.read_text(encoding="utf-8").upper()
