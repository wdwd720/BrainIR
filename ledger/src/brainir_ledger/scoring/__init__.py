"""The join of predictions and labels (run 2 only). Every entry point calls `require_unblind()` first."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .. import RESEARCH, UNBLIND_FLAG


class BlindError(RuntimeError):
    pass


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def require_unblind(flag: Path | None = None, research: Path | None = None) -> dict:
    """Refuse unless `research/ledger/UNBLIND.json` exists and names the SHA-256 of both frozen lock files.

    The flag must contain {"predictions_lock_sha256": ..., "labels_lock_sha256": ..., "authorised_by": ..., "utc": ...}; the
    hashes must equal those of `LOCK_predictions_v*.json` / `LOCK_labels_v*.json` named in it (keys `predictions_lock`,
    `labels_lock`, paths relative to research/ledger)."""
    flag = flag or UNBLIND_FLAG
    research = research or RESEARCH
    if not flag.exists():
        raise BlindError(f"scoring refused: {flag.name} does not exist (predictions and labels stay blind until it is created "
                         "by the person who authorises unblinding)")
    d = json.loads(flag.read_text(encoding="utf-8"))
    for k in ("predictions_lock", "labels_lock", "predictions_lock_sha256", "labels_lock_sha256", "authorised_by", "utc"):
        if k not in d:
            raise BlindError(f"scoring refused: {flag.name} lacks '{k}'")
    for side in ("predictions", "labels"):
        name = str(d[f"{side}_lock"])
        if "/" in name or "\\" in name or ".." in name or not name.startswith(f"LOCK_{side}_v") or not name.endswith(".json"):
            raise BlindError(f"scoring refused: {side}_lock must be a plain file name LOCK_{side}_v<k>.json in research/ledger")
        p = research / name
        if not p.exists() or _sha(p) != d[f"{side}_lock_sha256"]:
            raise BlindError(f"scoring refused: {side} lock {p.name} missing or its SHA-256 differs from {flag.name}")
    return d
