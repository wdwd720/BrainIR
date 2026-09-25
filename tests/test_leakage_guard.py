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


TIER_A_IDS = paths.repo_root() / "benchmarks" / "dng100" / "oracle" / "tier_a_ids"
BLIND = paths.repo_root() / "benchmarks" / "dng100" / "public_blind" / "networks"
METHOD_CODE = [SRC / "methods", SRC / "discovery", paths.repo_root() / "scripts" / "cleanroom_entry"]
CLEANROOM = paths.repo_root().parent / "BrainIR_p2clean"


def _answer_tier_a() -> tuple[set[int], set[str], set[str]]:
    """Tier-A positions and tier-A type tokens of every answer neuron (core and contralateral copies), and the oracle's labels,
    read at test time (review D, finding D7). Failure messages below never print these values."""
    import csv
    import json

    import pandas as pd

    o = json.loads(ORACLE.read_text(encoding="utf-8"))
    positions: set[int] = set()
    tokens: set[str] = set()
    labels: set[str] = set()
    for net, n in o["networks"].items():
        with open(TIER_A_IDS / f"ids_{net}.csv", encoding="utf-8") as fh:
            pos_of = {int(r["source_id"]): int(r["position"]) for r in csv.DictReader(fh)}
        members = {**n["core"], **(n.get("core_contralateral_copies") or {})}
        labels |= set(n["core"])
        pos = {pos_of[int(b)] for b in members.values() if int(b) in pos_of}
        positions |= pos
        nd = pd.read_parquet(BLIND / net / "neurons.parquet", columns=["position", "cell_type"])
        tok = dict(zip(nd["position"].astype(int), nd["cell_type"]))
        tokens |= {str(tok[p]) for p in pos if tok.get(p) is not None}
    return positions, tokens, labels


def test_method_code_has_no_answer_positions_tokens_or_labels():
    """No integer literal equal to an answer neuron's tier-A position (> 16; small integers are everywhere), no string literal
    containing an answer neuron's tier-A token and no oracle label ("E1", "I2", ...) in the method, discovery and clean-room entry
    code (goal3 section 4; review D, D7)."""
    import ast

    positions, tokens, labels = _answer_tier_a()
    big = {p for p in positions if p > 16}
    assert big and tokens and labels, "the oracle could not be read"
    offenders = []
    for root in METHOD_CODE:
        for f in sorted(root.rglob("*.py")):
            for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Constant):
                    continue
                v = node.value
                if isinstance(v, int) and not isinstance(v, bool) and v in big:
                    offenders.append((f.name, node.lineno, "integer equal to an answer tier-A position"))
                elif isinstance(v, str) and (v.strip() in labels or any(t in v for t in tokens)):
                    offenders.append((f.name, node.lineno, "oracle label or answer tier-A token"))
    assert not offenders, f"answer-derived literals in method code (values withheld): {offenders}"


def _token_offenders(files: list[Path], root: Path) -> list[tuple[str, str]]:
    offenders = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for tok in ANSWER_KEY_TOKENS:
            if re.search(rf"(?<![0-9A-Za-z]){re.escape(tok)}(?![0-9A-Za-z])", text):
                offenders.append((f.relative_to(root).as_posix(), "published type or core body id"))
    return offenders


def test_scripts_and_tests_contain_no_answer_key_tokens():
    """Scripts and tests carry no published type or core body id either (review D, D7); this file reads them at test time."""
    root = paths.repo_root()
    files = sorted((root / "scripts").rglob("*.py")) + [p for p in sorted((root / "tests").rglob("*.py")) if p.name != Path(__file__).name]
    offenders = _token_offenders(files, root)
    assert not offenders, f"answer-key tokens in scripts/tests (values withheld): {offenders}"


def test_cleanroom_code_and_docs_contain_no_answer_key_tokens():
    """The oracle-free development directory, when present on this machine: no published type or core body id in its code and
    documents (review D, D7). Method outputs (JSON predictions) are not scanned: a method may legitimately return any neuron."""
    import pytest

    if not CLEANROOM.exists():
        pytest.skip("no clean room on this machine")
    files = [p for p in sorted(CLEANROOM.rglob("*")) if p.is_file() and p.suffix in (".py", ".md", ".txt")
             and ".venv" not in p.parts and p.stat().st_size < 5_000_000]
    offenders = _token_offenders(files, CLEANROOM)
    assert not offenders, f"answer-key tokens in the clean room (values withheld): {offenders}"


def test_benchmark_answer_key_is_labelled():
    bench = paths.repo_root() / "benchmarks" / "dng100_walking_cpg"
    readme = bench / "README.md"
    assert readme.exists(), "benchmark README with leakage policy is required"
    assert "ANSWER KEY" in readme.read_text(encoding="utf-8").upper()
