"""Run 3, Stage 0 diagnosis (RUN3_PROMPT section 4): why T1R-T2R coupling differs between our full-cord DNg100 runs and the
authors' run 33195857. DNg100 ONLY, stored simulations only (run 1's 64 runs `calibration/g3_v1`, identical to run 2's GitHub
re-run; the authors' 32 replicates from their Zenodo traces). No hemilineage group is simulated.

Compares, per leg, which motor neurons become active (rate > 0.01 after 0.25 s, the rule both read-outs use), how many, and the
T1R-T2R phase offsets.

    uv run --project ledger --no-sync python ledger/scripts/diag_v3_coupling.py   # -> research/ledger/diag_v3/COUPLING_DIAG.json
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
from scipy.stats import pearsonr, spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))
import g3v2_evaluate as E  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import legs as L  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402


def authors_activity(mn_all: list[int]) -> tuple[np.ndarray, list[dict]]:
    """(replicates x MNs active matrix, per-replicate leg scores) from the authors' traces."""
    from brainir import paths
    from brainir.metrics.rhythm import network_oscillation_score

    member = f"simulations/DNg100_Stim_fullManc/hyak/run_id={E.RUN}/ckpt/DNg100_Stim_fullManc_Rs.npz"
    raw = (paths.data_root() / "raw" / "external" / "pugliese_2026_zenodo" / "DNg100_Stim_fullManc" / member).read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as nz:
        arrs = {n.removesuffix(".npy"): np.load(io.BytesIO(nz.read(n)), allow_pickle=False) for n in nz.namelist()}
    coords, data, shape = arrs["coords"], arrs["data"], tuple(int(x) for x in arrs["shape"])
    if len(shape) == 4:
        coords = np.vstack([coords[0] * shape[1] + coords[1], coords[2], coords[3]])
        shape = (shape[0] * shape[1], shape[2], shape[3])
    n_sims, _, n_t = shape
    pos = {m: i for i, m in enumerate(mn_all)}
    sel = np.isin(coords[1], mn_all)
    sub = np.zeros((n_sims, len(mn_all), n_t), dtype=np.float32)
    sub[coords[0][sel], np.array([pos[int(x)] for x in coords[1][sel]]), coords[2][sel]] = data[sel]
    win = sub[:, :, 250:]
    act = win.max(axis=2) > 0.01
    return act, n_sims


def main() -> None:
    fc = N.full_cord()
    ls = N.leg_setup(fc)
    mn_idx = {leg: [int(i) for i in np.flatnonzero(ls["masks"][leg])] for leg in L.LEGS}
    mn_all = sorted({i for v in mn_idx.values() for i in v})
    pos = {m: i for i, m in enumerate(mn_all)}

    ours, _ = E.load_g3(data_dir() / "calibration" / "g3_v1" / "results.pkl", "g3|")
    act_o = np.zeros((len(ours), len(mn_all)), bool)
    for r, run in enumerate(ours):
        for m in run["extras"]["active_readout_positions"]:
            if int(m) in pos:
                act_o[r, pos[int(m)]] = True
    act_a, n_a = authors_activity(mn_all)

    f_o, f_a = act_o.mean(0), act_a.mean(0)
    out = {"what": "DNg100 full cord, stored runs only: our 64 runs (run 1 g3, seeds 0..63) vs the authors' 32 replicates (run 33195857)",
           "n_ours": len(ours), "n_authors": int(n_a), "n_leg_mns": len(mn_all),
           "mn_activation_frequency": {"pearson": float(pearsonr(f_o, f_a)[0]), "spearman": float(spearmanr(f_o, f_a)[0]),
                                       "mns_ever_active_ours": int((f_o > 0).sum()), "mns_ever_active_authors": int((f_a > 0).sum()),
                                       "mns_active_ge_25pct_ours": int((f_o >= 0.25).sum()), "mns_active_ge_25pct_authors": int((f_a >= 0.25).sum())},
           "per_leg": {}}
    big = []
    for leg in L.LEGS:
        ii = [pos[m] for m in mn_idx[leg]]
        no, na = act_o[:, ii].sum(1), act_a[:, ii].sum(1)
        out["per_leg"][leg] = {"n_mns": len(ii), "median_active_ours": float(np.median(no)), "median_active_authors": float(np.median(na)),
                               "mean_active_ours": float(no.mean()), "mean_active_authors": float(na.mean()),
                               "freq_corr_pearson": float(pearsonr(f_o[ii], f_a[ii])[0]) if f_o[ii].std() and f_a[ii].std() else None}
        for k in ii:
            if abs(f_o[k] - f_a[k]) >= 0.25:
                big.append({"leg": leg, "mn_index": mn_all[k], "freq_ours": round(float(f_o[k]), 3), "freq_authors": round(float(f_a[k]), 3)})
    out["discordant_mns_abs_freq_diff_ge_0_25"] = big
    # T1R-T2R offsets (as in item 4'): per replicate, when both legs rhythmic
    pairs, k, c4p, _ = E.item4p(ours)
    out["coupling_item4p_from_preview_inputs"] = {kk: {x: (round(y, 4) if isinstance(y, float) else y) for x, y in v.items()} for kk, v in pairs.items()}
    d = RESEARCH / "diag_v3"
    d.mkdir(parents=True, exist_ok=True)
    (d / "COUPLING_DIAG.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in out.items() if k not in ("coupling_item4p_from_preview_inputs",)}, indent=1)[:4000])


if __name__ == "__main__":
    main()
