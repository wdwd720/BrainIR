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
ORACLE = paths.repo_root() / "benchmarks" / "dng100" / "oracle" / "oracle.json"


def _answer_key_tokens() -> list[str]:
    """Every published interneuron type and every core body id of every network, read from the oracle at test time
    (so this file itself carries no answer token)."""
    import json

    o = json.loads(ORACLE.read_text(encoding="utf-8"))
    toks = {v["type"] for v in o["labels"].values()}
    for n in o["networks"].values():
        toks |= {str(i) for i in n["core"].values()}
        toks |= {str(i) for i in (n.get("core_contralateral_copies") or {}).values()}
    return sorted(toks)


ANSWER_KEY_TOKENS = _answer_key_tokens()


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
              "research/LOG.md", "research/cross_connectome_mapping.md", "research/manc_release_notes.md", "data/README.md",
              "data/manifests"]


def test_non_answer_docs_are_clean():
    """Docs that a future (LLM-based) component might read as context must not carry the answer."""
    root = paths.repo_root()
    offenders = []
    for rel in CLEAN_DOCS:
        p = root / rel
        files = [p] if p.is_file() else sorted(f for f in p.rglob("*") if f.suffix in (".md", ".json", ".txt", ".csv", ".yaml", ".yml")) \
            if p.is_dir() else []
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
