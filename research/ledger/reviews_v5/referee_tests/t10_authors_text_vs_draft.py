"""Referee test 10 (documentary): what the authors' own text says about the screen, set against the draft and the ledger.

Input: the cached full text of the authors' preprint (data/ledger/sources_v2/10_1101_2025_09_12_675944/text.txt, bioRxiv
10.1101/2025.09.12.675944; the cached Nature version, 10.1038/s41586-026-11195-y, is abstract only, so passages below are the
preprint's and may differ from the published paper), and replication_v1/T_singlecopy.json (the ledger's single-copy screen).
Prints the passages on (1) how the screen's low scores are to be read, (2) why DNg100 and DNb08 were chosen, (3) the cross-dataset
tests of DNg100 and DNb08, (4) the weight-noise test; then the ledger's single-copy DNb08 / DNg100 scores in both flies.
Usage: uv run --project ledger --no-sync python research/ledger/reviews_v5/referee_tests/t10_authors_text_vs_draft.py
"""
from __future__ import annotations
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ROOT = REPO / "research/ledger"
TXT = REPO / "data/ledger/sources_v2/10_1101_2025_09_12_675944/text.txt"


def sentence_with(t: str, needle: str) -> str:
    i = t.find(needle)
    if i < 0:
        return f"[not found: {needle}]"
    a = max(t.rfind(". ", 0, i), t.rfind("\n", 0, i)) + 1
    b = t.find(". ", i)
    return re.sub(r"\s+", " ", t[a:b + 1]).strip()


def main():
    t = TXT.read_text(encoding="utf-8")
    needles = [
        "works as a discovery tool",
        "we do not interpret low scores as evidence",
        "because every DN of these two types produced",
        "rather than over-interpreting the low scores",
        "Only 29 DNs",
        "qualitatively similar across a wide range of model parameters",
        "Across all four connectomes, DNg100 reliably drove",
        "three of the four connectome datasets (MANC, FANC, and mCNS",
        "we optogenetically activated DNb08 neurons in decapitated flies",
        "robust to noise perturbations of weights",
        "We followed a very similar procedure in the Male CNS",
        "For DNg100 activation, Istim = 250 in MANC",
        "For DNb08 activation, Istim =",
    ]
    for n in needles:
        print(f"-- [{n}]\n   {sentence_with(t, n)}\n")
    d = json.loads((ROOT / "replication_v1/T_singlecopy.json").read_text())
    for typ in ("DNg100", "DNb08"):
        for fly in ("MANC", "MCNS"):
            v = d["focus"][typ][fly]
            print(f"ledger single-copy screen, {typ} in {fly}: copies {[(c, round(s, 3)) for c, s in v['copies']]}, driver copies {v['n_driver_copies']} of {v['n_copies']}")


if __name__ == "__main__":
    main()
