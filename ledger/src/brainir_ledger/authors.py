"""The authors' own screen numbers (arms A0, A1, A1-lo10), rebuilt by script from their released files, pinned by SHA-256.

Files: GitHub `smpuglie/Pugliese_2026` @ 10e7661 (canonical bytes from raw.githubusercontent.com); run configurations from
Zenodo 10.5281/zenodo.22260924 (read by `ledger/scripts/zenodo_remote_zip.py`). PREREG sections 3.1-3.2.
"""

from __future__ import annotations

import hashlib
import os
import stat
import urllib.parse
from pathlib import Path

import numpy as np
import pandas as pd
import requests

REPO_ID = "smpuglie/Pugliese_2026"
COMMIT = "10e7661bf414ba7b4c2edf795cd36d0f878c17c0"
FILES = {
    "a0_score": ("figures/DN_Screen-hyak-combined128reps/combinedScoreSummary.csv",
                 "0e1651bf17e277e80c2d3512ace837ab77dc0ed54ff0adb73e4964b39efe1aa1"),
    "a0_activity": ("figures/DN_Screen-hyak-combined128reps/combinedActivitySummary.csv",
                    "1b6a0e7bbda92e9830fa0c52e2cf22d46c4429b662bf34e663247a9f9b6a6ac4"),
    "a1_score": ("figures/DN_Screen-hyak-run_id=32818378/scoreSummary.csv",
                 "c93255a84316a87819b50b31ebcae137f6bef13deeb7f32db107a824feab2106"),
    "a1_activity": ("figures/DN_Screen-hyak-run_id=32818378/activitySummary.csv",
                    "c877904acefbe9a7cac468e37f3954ba141a95611a790b7b22b80ba079c0dd7b"),
    "full_scores_alllegs": ("figures/DNg100_Stim_fullManc-hyak-30662613-33195857-33195876-33195882/scores_allLegs.csv",
                            "8c9a014420ebc629bc47cad68f0671e6fb62a1e40a38f4a499f4b3c14d526647"),
    "full_nmns_alllegs": ("figures/DNg100_Stim_fullManc-hyak-30662613-33195857-33195876-33195882/nMnsActive_allLegs.csv",
                          "c67873234033a8e8f41d7e96360abebb9243312e2f52dab1619b5ccdb2c73d06"),
}
ZENODO_CONFIGS = {  # member path inside the Zenodo archive -> sha256 (read with ledger/scripts/zenodo_remote_zip.py)
    "DN_Screen__fig1_edf1.zip:simulations/DN_Screen/hyak/run_id=32818378/logs/run_config.yaml":
        "26e02175972215b84c986ec867a31d05adbbccb06c72eaf226e234623ae82c10",
    "DN_Screen__fig1_edf1.zip:simulations/DN_Screen/hyak/run_id=32818378/.hydra/overrides.yaml":
        "a1e572bfc40b81a628be530120dac50847fbf34ede182f93205d8d00ff300721",
    "DN_Screen__fig1_edf1.zip:simulations/DN_Screen/hyak/run_id=33160051/logs/run_config.yaml":
        "49d875ea49a8c63b90d4b56304375380d0b2ab74f2d010baa95b07d4a83068ed",
    "DNg100_Stim_fullManc.zip:simulations/DNg100_Stim_fullManc/hyak/run_id=33195876/logs/run_config.yaml":
        "081df1cf7e13ce5aaf5c2cea1166f9096eb66e669412000b47db6e3b6d61c516",
    "DNg100_Stim_fullManc.zip:simulations/DNg100_Stim_fullManc/hyak/run_id=30662613/logs/run_config.yaml":
        "f230e5b6ebd83142d2be001e1a11c3ad4653f18914e275ac1134c203b85dbcbe",
}
USABLE_LO, USABLE_HI = 5, 1500


def ext_dir() -> Path:
    from brainir import paths

    d = paths.data_root() / "raw" / "external" / "pugliese_2026" / COMMIT[:10] / "figures_ledger"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetch() -> dict[str, Path]:
    out = {}
    for key, (rel, sha) in FILES.items():
        dest = ext_dir() / rel.replace("/", "__")
        if not dest.exists():
            url = f"https://raw.githubusercontent.com/{REPO_ID}/{COMMIT}/{urllib.parse.quote(rel)}"
            r = requests.get(url, timeout=600)
            r.raise_for_status()
            if hashlib.sha256(r.content).hexdigest() != sha:
                raise RuntimeError(f"{rel}: sha256 mismatch")
            tmp = dest.with_suffix(".partial")
            tmp.write_bytes(r.content)
            os.replace(tmp, dest)
            os.chmod(dest, stat.S_IREAD)
        elif hashlib.sha256(dest.read_bytes()).hexdigest() != sha:
            raise RuntimeError(f"{dest} does not match its pinned sha256")
        out[key] = dest
    return out


def _usable(act: pd.DataFrame, lo: int) -> pd.DataFrame:
    return (act >= lo) & (act <= USABLE_HI)


def _status(act_row: pd.Series, lo: int) -> str:
    n_weak = int((act_row < lo).sum())
    n_strong = int((act_row > USABLE_HI).sum())
    return "never_usable_weak" if n_weak >= n_strong else "never_usable_strong"


def a1_types(lo: int = USABLE_LO, files: dict | None = None) -> pd.DataFrame:
    """A1 (lo=5, primary) / A1-lo10 (lo=10): one row per type, PREREG 3.1 / 5."""
    from .tables import band, finish_types

    files = files or fetch()
    sc = pd.read_csv(files["a1_score"], index_col=0)
    ac = pd.read_csv(files["a1_activity"], index_col=0)
    if not (sc.index == ac.index).all() or sc.shape != (321, 16):
        raise RuntimeError("unexpected A1 table layout")
    use = _usable(ac, lo)
    rows = []
    for t in sc.index:
        s = sc.loc[t][use.loc[t]].astype(float).to_numpy()
        mean = float(s.mean()) if len(s) else None
        primary = mean if mean is not None else 0.0
        rows.append({"arm": "A1" if lo == USABLE_LO else f"A1-lo{lo}", "network": "authors_manc_frontleg_2025-08-13", "manc_type": str(t),
                     "n_members": None, "member_ids": None, "n_replicates": 16, "n_usable": int(len(s)), "mean_score": mean,
                     "median_score": float(np.median(s)) if len(s) else None, "frac_ge_0_5": float((s >= 0.5).mean()) if len(s) else None,
                     "best_score": float(s.max()) if len(s) else None, "median_freq_hz": None, "median_current": None,
                     "median_n_active_readout": None, "status": "ok" if len(s) else _status(ac.loc[t], lo), "band": band(primary),
                     "primary_score": primary, "median_n_active_all": float(ac.loc[t].median())})
    return finish_types(rows)


def a1_replicates(lo: int = USABLE_LO, files: dict | None = None) -> pd.DataFrame:
    files = files or fetch()
    sc = pd.read_csv(files["a1_score"], index_col=0)
    ac = pd.read_csv(files["a1_activity"], index_col=0)
    use = _usable(ac, lo)
    rows = [{"manc_type": str(t), "replicate": int(r), "score": float(sc.loc[t, r]), "n_active_notebook": float(ac.loc[t, r]),
             "usable": bool(use.loc[t, r])} for t in sc.index for r in sc.columns]
    return pd.DataFrame(rows)


def a0_neurons(table: pd.DataFrame, files: dict | None = None) -> pd.DataFrame:
    """Per neuron (index = row of the authors' front-leg table): mean over usable of 128 replicates, and counts of unusable
    replicates that were too weak (nActive < 5) or too strong (> 1500)."""
    files = files or fetch()
    sc = pd.read_csv(files["a0_score"], index_col=0)
    ac = pd.read_csv(files["a0_activity"], index_col=0)
    use = _usable(ac, USABLE_LO)
    rows = []
    for i in sc.index:
        s = sc.loc[i][use.loc[i]].astype(float).to_numpy()
        rows.append({"row": int(i), "bodyId": int(table.loc[int(i), "bodyId"]), "manc_type": str(table.loc[int(i), "type"]),
                     "n_usable": int(len(s)), "mean_score": float(s.mean()) if len(s) else None,
                     "n_weak": int((ac.loc[i] < USABLE_LO).sum()), "n_strong": int((ac.loc[i] > USABLE_HI).sum())})
    return pd.DataFrame(rows)


def per_type_from_neurons(neur: pd.DataFrame, arm: str, network: str) -> pd.DataFrame:
    """A0/B0 per type: maximum and mean of member-neuron means (never-usable members ignored; no usable member -> None)."""
    from .tables import band, finish_types

    rows = []
    for t, g in neur.groupby("manc_type", sort=True):
        m = g["mean_score"].dropna()
        tmax = float(m.max()) if len(m) else None
        tmean = float(m.mean()) if len(m) else None
        primary = tmax if tmax is not None else 0.0
        rows.append({"arm": arm, "network": network, "manc_type": t, "n_members": int(len(g)),
                     "member_ids": ";".join(str(int(b)) for b in g["bodyId"]), "n_replicates": None, "n_usable": int(g["n_usable"].sum()),
                     "mean_score": tmean, "median_score": None, "frac_ge_0_5": None, "best_score": tmax, "median_freq_hz": None,
                     "median_current": None, "median_n_active_readout": None,
                     "status": "ok" if len(m) else ("never_usable_weak" if g["n_weak"].sum() >= g["n_strong"].sum() else "never_usable_strong"),
                     "band": band(primary), "primary_score": primary, "type_max": tmax, "type_mean": tmean})
    return finish_types(rows)
