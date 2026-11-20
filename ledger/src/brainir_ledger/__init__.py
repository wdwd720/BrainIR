"""BrainIR prediction ledger (run 1): pre-registered DN-activation predictions and blind real-fly labels.

Layout
------
* prediction side: ``networks``, ``typescreen``, ``legs``, ``jobs``, ``backend``, ``authors``, ``baselines``,
  ``controls``, ``tables``, ``registry`` (they read the connectome and the simulator; they never read labels);
* label side: ``labels`` (record schema, validator, consensus aggregation, agreement; it never reads predictions; a test
  enforces this);
* the join: ``scoring`` (refuses to run unless ``research/ledger/UNBLIND.json`` exists).

Documents and tables live in ``research/ledger/``; bulk outputs under the data root (``ledger/`` sub-directory).
"""

from __future__ import annotations

from pathlib import Path

__version__ = "0.1.0"

_HERE = Path(__file__).resolve()
# inside a Modal container the package sits at /root/brainir_ledger, so there is no repository around it
REPO = _HERE.parents[3] if len(_HERE.parents) > 3 else _HERE.parent
RESEARCH = REPO / "research" / "ledger"
PREDICTIONS = RESEARCH / "predictions"
LABELS = RESEARCH / "labels"
KIT = RESEARCH / "kit"
UNBLIND_FLAG = RESEARCH / "UNBLIND.json"


def data_dir() -> Path:
    """Bulk outputs of the ledger (traces, raw job results) under the BrainIR data root."""
    from brainir import paths

    d = paths.data_root() / "ledger"
    d.mkdir(parents=True, exist_ok=True)
    return d
