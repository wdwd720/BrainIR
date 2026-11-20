"""Diagnostic for gate G3 item 4 (does not change the gate): apply the pre-registered coupling test (PREREG 4.7) to the
AUTHORS' own full-cord DNg100 traces (Zenodo 10.5281/zenodo.22260924, DNg100_Stim_fullManc.zip, one run of 32 replicates).

    uv run --project ledger --no-sync python ledger/scripts/g3_authors_coupling.py [run_id]

Reads only the six E1 rows and the per-leg MN rows from the run's sparse trace array (pydata-sparse COO npz: coords, data,
shape) after extracting the member with HTTP range requests. Output: research/ledger/gates/G3_authors_coupling_<run>.json.
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from brainir.metrics.rhythm import network_oscillation_score  # noqa: E402
from zenodo_remote_zip import open_archive  # noqa: E402

from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger import legs as L  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402


def main() -> None:
    run = sys.argv[1] if len(sys.argv) > 1 else "33195857"
    member = f"simulations/DNg100_Stim_fullManc/hyak/run_id={run}/ckpt/DNg100_Stim_fullManc_Rs.npz"
    z, f = open_archive("DNg100_Stim_fullManc.zip")
    raw = z.read(member)
    fc = N.full_cord()
    ls = N.leg_setup(fc)
    e1 = [ls["e1"][leg] for leg in L.LEGS]
    mn_idx = {leg: np.flatnonzero(ls["masks"][leg]) for leg in L.LEGS}
    keep_rows = sorted(set(e1) | {int(i) for v in mn_idx.values() for i in v})
    with zipfile.ZipFile(io.BytesIO(raw)) as nz:
        names = nz.namelist()
        arrs = {n.removesuffix(".npy"): np.load(io.BytesIO(nz.read(n)), allow_pickle=False) for n in names}
    coords, data, shape = arrs["coords"], arrs["data"], tuple(int(x) for x in arrs["shape"])
    n_sims, n_neur, n_t = shape
    sel = np.isin(coords[1], keep_rows)
    sub = np.zeros((n_sims, len(keep_rows), n_t), dtype=np.float32)
    rowpos = {r: i for i, r in enumerate(keep_rows)}
    rp = np.array([rowpos[int(x)] for x in coords[1][sel]])
    sub[coords[0][sel], rp, coords[2][sel]] = data[sel]
    start = 250
    per_rep = []
    for s in range(n_sims):
        win = sub[s][:, start:].T   # time x kept rows
        legscore = {}
        for leg in L.LEGS:
            cols = [rowpos[int(i)] for i in mn_idx[leg]]
            w = win[:, cols]
            mask = w.max(axis=0) > 0.01
            sc, _, _, _ = network_oscillation_score(w, mask, 0.05)
            legscore[leg] = sc
        per_rep.append({"legs": legscore, "e1": {leg: win[:, rowpos[e1[i]]].astype(np.float64) for i, leg in enumerate(L.LEGS)}})
    pairs = {}
    for a, b in L.REPORTED_PAIRS:
        elig = [r for r in per_rep if r["legs"][a] >= 0.5 and r["legs"][b] >= 0.5]
        pairs[f"{a}-{b}"] = L.coupling([r["e1"][a] for r in elig], [r["e1"][b] for r in elig], n_null=1000, seed=20261123)
    out = {"run": run, "n_replicates": n_sims, "T_samples": n_t, "leg_median_scores": {leg: float(np.median([r["legs"][leg] for r in per_rep]))
                                                                                     for leg in L.LEGS},
           "coupling_v1": pairs, "n_coupled": sum(bool(v["coupled"]) for v in pairs.values()),
           "bytes_read": f.n_bytes}
    d = RESEARCH / "gates"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"G3_authors_coupling_{run}.json").write_text(json.dumps(out, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in out.items() if k != "coupling_v1"}, indent=1))
    for k, v in pairs.items():
        print(k, v)


if __name__ == "__main__":
    main()
