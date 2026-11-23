"""Replicate tables of every screen PREREG v6 compares (columns type, seed, usable, score; the format `brainir_ledger.agree` reads).

- MANC: tuned B1r (`predictions_v2/B1r`), original procedure K = 0 (`predictions/B1-lo10`), sweep `dx-1-run4` (rulebook v4 fix 1), the
  authors' A1 (their replicates 0..15 as seeds).
- MaleCNS: tuned B2r (`predictions_v2/B2r`), K = 0 (`predictions/B2`), sweep `ms-mcns-run6`.
- BANC (run 6): tuned `bt-banc-run6` (`BT|`), single members (`BT1|`), sweep `bs-banc-run6`, one-sided `bh-banc-run6` (`BH-L|`,
  `BH-R|`), copies `bn-banc-run6` (`BN-c1|`, `BN-c2|`).

Sweep score (PREREG v6 G4): per replicate the best in-bounds score over the grid currents, 0 if none is in bounds; usable always.
A tuned replicate is usable if its job returned without error and its result says so (run 2's `group_v2` field `usable`
and a score), as B1r / B2r's `replicates.parquet`. A packed key without a result counts as a not-usable seed with score 0
(PREREG v6 X3), for the run 6 campaigns whose manifests are read.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import RESEARCH, data_dir
from .backend import read_log

COLS = ["type", "seed", "usable", "score"]


def _parquet(rel: str) -> pd.DataFrame:
    d = pd.read_parquet(RESEARCH / rel / "replicates.parquet")
    return d.rename(columns={"manc_type": "type"})[COLS].astype({"type": str, "seed": "int64", "usable": bool, "score": float})


@lru_cache(maxsize=None)
def results(area: str, campaign: str, source: str = "GHA") -> dict[str, dict]:
    p = data_dir() / area / f"{source}_{campaign}" / "results.pkl"
    if not p.exists():
        raise FileNotFoundError(p)
    return {r["key"]: r for r in read_log(p) if isinstance(r, dict) and "key" in r}


def results_path(area: str, campaign: str, source: str = "GHA") -> Path:
    return data_dir() / area / f"{source}_{campaign}" / "results.pkl"


MISSING: dict[str, list[str]] = {}


def _manifest_keys(campaign: str | None) -> list[str]:
    if campaign is None:
        return []
    m = data_dir() / "gha" / campaign / "manifest.json"
    if not m.exists():
        return []
    import json  # noqa: PLC0415

    return json.loads(m.read_text())["keys"]


def _fill(rows: list[dict], res: dict, prefix: str, campaign: str | None) -> list[dict]:
    """PREREG v6 X3 (as v5 S8): a packed key still without a result after at most two re-publications counts as a not-usable seed
    (score 0); it is listed in `MISSING`."""
    miss = [k for k in _manifest_keys(campaign) if k.split("|")[0] == prefix and k not in res]
    for k in miss:
        _, t, s = k.split("|")
        rows.append({"type": t, "seed": int(s[1:]), "usable": False, "score": 0.0})
    if campaign is not None:
        MISSING[f"{campaign}:{prefix}"] = sorted(miss)
    return rows


def missing_report() -> dict[str, list[str]]:
    return {k: v for k, v in MISSING.items() if v}


def _tuned_rows(res: dict[str, dict], prefix: str, campaign: str | None = None) -> pd.DataFrame:
    rows = []
    for k, r in res.items():
        arm, t, s = k.split("|")
        if arm != prefix:
            continue
        ok = ("error" not in r) and bool(r.get("usable")) and r.get("score") is not None  # run 2's group_v2 field, as B1r / B2r
        rows.append({"type": t, "seed": int(s[1:]), "usable": bool(ok), "score": float(r["score"]) if ok else 0.0})
    rows = _fill(rows, res, prefix, campaign)
    return pd.DataFrame(rows, columns=COLS).sort_values(["type", "seed"]).reset_index(drop=True)


def _sweep_rows(res: dict[str, dict], prefix: str, campaign: str | None = None) -> pd.DataFrame:
    rows = []
    for k, r in res.items():
        arm, t, s = k.split("|")
        if arm != prefix:
            continue
        ib = [x["score"] for x in (r.get("runs") or []) if x.get("in_bounds") and x.get("score") is not None]
        rows.append({"type": t, "seed": int(s[1:]), "usable": True, "score": float(max(ib)) if ib else 0.0})
    rows = _fill(rows, res, prefix, campaign)
    return pd.DataFrame(rows, columns=COLS).sort_values(["type", "seed"]).reset_index(drop=True)


def b1r() -> pd.DataFrame:
    return _parquet("predictions_v2/B1r")


def b2r() -> pd.DataFrame:
    return _parquet("predictions_v2/B2r")


def k0_manc() -> pd.DataFrame:
    return _parquet("predictions/B1-lo10")


def k0_mcns() -> pd.DataFrame:
    return _parquet("predictions/B2")


def a1() -> pd.DataFrame:
    from . import authors as A  # noqa: PLC0415

    d = A.a1_replicates().rename(columns={"manc_type": "type", "replicate": "seed"})
    return d[COLS].astype({"type": str, "seed": "int64", "usable": bool, "score": float}).sort_values(["type", "seed"]).reset_index(drop=True)


def sweep_manc() -> pd.DataFrame:
    return _sweep_rows(results("reliability_v2", "dx-1-run4", "MODAL"), "DX-1")


def sweep_mcns() -> pd.DataFrame:
    return _sweep_rows(results("posthoc_v6", "ms-mcns-run6"), "MS", "ms-mcns-run6")


def banc_tuned() -> pd.DataFrame:
    return _tuned_rows(results("thirdfly_v1", "bt-banc-run6"), "BT", "bt-banc-run6")


def banc_singles() -> pd.DataFrame:
    return _tuned_rows(results("thirdfly_v1", "bt-banc-run6"), "BT1", "bt-banc-run6")


def banc_sweep() -> pd.DataFrame:
    return _sweep_rows(results("thirdfly_v1", "bs-banc-run6"), "BS", "bs-banc-run6")


def banc_side(side: str) -> pd.DataFrame:
    return _tuned_rows(results("thirdfly_v1", "bh-banc-run6"), f"BH-{side}", "bh-banc-run6")


def banc_copy(i: int) -> pd.DataFrame:
    return _tuned_rows(results("thirdfly_v1", "bn-banc-run6"), f"BN-c{i}", "bn-banc-run6")
