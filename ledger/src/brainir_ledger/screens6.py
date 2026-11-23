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
DX1_SHA256 = "1db9b231d9eca92f7b3082e55aee51a78b0a8cfff8a3084af55ef785f832ab42"   # PREREG v6 Part Q 6 (hashed by LOCK_prereg_v6)


def _manifest_keys(campaign: str | None) -> list[str]:
    if campaign is None:
        return []
    m = data_dir() / "gha" / campaign / "manifest.json"
    if not m.exists():
        return []
    import json  # noqa: PLC0415

    return json.loads(m.read_text())["keys"]


def campaigns(area: str, prefix: str) -> list[str]:
    """Every collected part of a run 6 campaign (`<prefix>-...-run6`) in an area (PREREG v6 X1: campaigns may be split into parts)."""
    return sorted(p.name[len("GHA_"):] for p in (data_dir() / area).glob(f"GHA_{prefix}-*run6") if (p / "results.pkl").exists())


def merged(area: str, prefix: str) -> tuple[dict[str, dict], list[str], list[str]]:
    """Results of every part, the union of their packed keys, and the part names."""
    names = campaigns(area, prefix)
    if not names:
        raise FileNotFoundError(f"{area}: no collected {prefix}-*-run6 campaign")
    res: dict[str, dict] = {}
    keys: list[str] = []
    for n in names:
        res.update(results(area, n))
        keys += _manifest_keys(n)
    return res, keys, names


def _fill(rows: list[dict], res: dict, prefix: str, keys: list[str], label: str | None) -> list[dict]:
    """PREREG v6 X3 (as v5 S8): a packed key still without a result after at most two re-publications counts as a not-usable seed
    (score 0); it is listed in `MISSING`."""
    miss = [k for k in keys if k.split("|")[0] == prefix and k not in res]
    for k in miss:
        _, t, s = k.split("|")
        rows.append({"type": t, "seed": int(s[1:]), "usable": False, "score": 0.0})
    if label is not None:
        MISSING[f"{label}:{prefix}"] = sorted(miss)
    return rows


def missing_report() -> dict[str, list[str]]:
    return {k: v for k, v in MISSING.items() if v}


def _tuned_rows(res: dict[str, dict], prefix: str, keys: list[str] | None = None, label: str | None = None) -> pd.DataFrame:
    rows = []
    for k, r in res.items():
        arm, t, s = k.split("|")
        if arm != prefix:
            continue
        ok = ("error" not in r) and bool(r.get("usable")) and r.get("score") is not None  # run 2's group_v2 field, as B1r / B2r
        rows.append({"type": t, "seed": int(s[1:]), "usable": bool(ok), "score": float(r["score"]) if ok else 0.0})
    rows = _fill(rows, res, prefix, keys or [], label)
    return pd.DataFrame(rows, columns=COLS).sort_values(["type", "seed"]).reset_index(drop=True)


def _sweep_rows(res: dict[str, dict], prefix: str, keys: list[str] | None = None, label: str | None = None) -> pd.DataFrame:
    rows = []
    for k, r in res.items():
        arm, t, s = k.split("|")
        if arm != prefix:
            continue
        ib = [x["score"] for x in (r.get("runs") or []) if x.get("in_bounds") and x.get("score") is not None]
        rows.append({"type": t, "seed": int(s[1:]), "usable": True, "score": float(max(ib)) if ib else 0.0})
    rows = _fill(rows, res, prefix, keys or [], label)
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
    """MANC's whole-type sweep; its log must match the SHA-256 fixed before the freeze (audit re-check N6)."""
    import hashlib  # noqa: PLC0415

    p = results_path("reliability_v2", "dx-1-run4", "MODAL")
    got = hashlib.sha256(p.read_bytes()).hexdigest()
    if got != DX1_SHA256:
        raise RuntimeError(f"dx-1-run4 results.pkl sha256 {got} != {DX1_SHA256} (PREREG v6 Part Q 6)")
    return _sweep_rows(results("reliability_v2", "dx-1-run4", "MODAL"), "DX-1")


def _part_rows(area: str, prefix: str, arm: str, sweep: bool = False) -> pd.DataFrame:
    res, keys, names = merged(area, prefix)
    return (_sweep_rows if sweep else _tuned_rows)(res, arm, keys, "+".join(names))


def sweep_mcns() -> pd.DataFrame:
    return _part_rows("posthoc_v6", "ms", "MS", sweep=True)


def banc_tuned() -> pd.DataFrame:
    return _part_rows("thirdfly_v1", "bt", "BT")


def banc_singles() -> pd.DataFrame:
    return _part_rows("thirdfly_v1", "bt", "BT1")


def banc_sweep() -> pd.DataFrame:
    return _part_rows("thirdfly_v1", "bs", "BS", sweep=True)


def banc_side(side: str) -> pd.DataFrame:
    return _part_rows("thirdfly_v1", "bh", f"BH-{side}")


def banc_copy(i: int) -> pd.DataFrame:
    return _part_rows("thirdfly_v1", "bn", f"BN-c{i}")


def partv_results() -> tuple[dict[str, dict], list[str]]:
    """Part V's results and packed keys (a missing key scores 0, audit re-check N4)."""
    res, keys, _ = merged("thirdfly_v1", "pv")
    return res, keys
