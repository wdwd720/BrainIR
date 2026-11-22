"""PREREG v4 G3-G4 and Part Q: side and matching QA from annotations and wiring only (no simulation, no score).

Writes research/ledger/diag_v4/SIDE_QA.json once:
  - per fly: the DN side rule (annotation vs output side; reliability; corrections), type counts (matched, one-sided), mirror-map
    counts by step;
  - MaleCNS: the root side of the curated MANC match against the output side (for information);
  - handedness: non-DN MaleCNS neurons with a curated MANC match, MaleCNS soma side vs the matched MANC body's soma side;
  - non-DN soma-position check: 200 neurons per fly (default_rng(20261451)) with an annotated L/R side and a soma position, the side
    of the soma x relative to the midline (midpoint of the sample network's mean left and mean right soma x).

    uv run --project ledger --no-sync python ledger/scripts/side_qa_v4.py
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from brainir_ledger import REPO, RESEARCH  # noqa: E402
from brainir_ledger import mirror as MR  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402

OUT = RESEARCH / "diag_v4" / "SIDE_QA.json"
SAMPLE_SEED = 20261451


def _crosstab(a, b) -> dict:
    t = pd.crosstab(pd.Series(a, name="annotation").fillna("NA"), pd.Series(b, name="other").replace("", "undefined"))
    return {str(r): {str(c): int(t.loc[r, c]) for c in t.columns} for r in t.index}


def _position_check(side: np.ndarray, x: np.ndarray, candidates: np.ndarray) -> dict:
    ok = [i for i in candidates if side[i] in ("L", "R") and np.isfinite(x[i])]
    rng = np.random.default_rng(SAMPLE_SEED)
    pick = sorted(rng.choice(ok, size=min(200, len(ok)), replace=False).tolist())
    xl = np.mean([x[i] for i in ok if side[i] == "L"])
    xr = np.mean([x[i] for i in ok if side[i] == "R"])
    x0 = (xl + xr) / 2
    pos = ["L" if (x[i] - x0) * np.sign(xl - xr) > 0 else "R" for i in pick]
    agree = sum(1 for i, p in zip(pick, pos) if side[i] == p)
    return {"candidates": len(ok), "sample": len(pick), "agree": agree, "share": agree / len(pick) if pick else None,
            "midline_x": float(x0), "left_mean_x": float(xl), "right_mean_x": float(xr)}


def main() -> None:
    import pyarrow.feather as feather  # noqa: PLC0415

    from brainir import paths  # noqa: PLC0415

    out = {"note": "annotations and wiring only; no simulation, no score (PREREG v4 Part Q)"}
    ann = feather.read_table(glob.glob(str(paths.data_root() / "raw" / "external" / "malecns_v1.0_body_annotations" / "*.feather"))[0]
                             ).to_pandas().set_index("bodyId")
    fct = N.full_cord().table.set_index("bodyId")
    for name in ("MANC", "MaleCNS"):
        f = MR.fly(name)
        members = sorted({i for m in f.groups.values() for i in m})
        rec = {"rule": f.reliability, "dn_annotation_vs_output_side": _crosstab(f.side_annot[members], f.out_side[members]),
               "type_counts": f.type_counts(), "mirror_counts": MR.mirror_map(f).counts}
        dn_mask = np.zeros(f.n, bool)
        dn_mask[members] = True
        nondn = np.flatnonzero(~dn_mask & np.isin(f.side_annot, ["L", "R"]))
        if name == "MANC":
            v0 = pd.read_parquet(REPO / "data" / "processed" / "manc" / "v1.0" / "neurons.parquet", columns=["source_id", "soma_x"])
            x = f.net.table["bodyId"].astype(np.int64).map(v0.set_index("source_id")["soma_x"]).to_numpy(dtype=float)
            rec["nondn_soma_position_check"] = _position_check(f.side_annot, x, nondn)
            rec["nondn_soma_position_source"] = "processed manc:v1.0 soma_x by bodyId"
        else:
            loc = ann["somaLocation"].reindex(f.net.table["bodyId"].astype(np.int64).to_numpy())
            x = np.array([float(v[0]) if isinstance(v, np.ndarray) and len(v) == 3 else np.nan for v in loc])
            rec["nondn_soma_position_check"] = _position_check(f.side_annot, x, nondn)
            rec["nondn_soma_position_source"] = "MaleCNS body annotations somaLocation (x)"
            mb = ann["mancBodyid"].reindex(f.net.table["bodyId"].astype(np.int64).to_numpy()).to_numpy()
            root = fct["rootSide"].map({"LHS": "L", "RHS": "R"})
            ms = np.array([root.get(int(v)) if pd.notna(v) and int(v) in root.index else None for v in mb], dtype=object)
            rec["dn_matched_manc_root_side_vs_output_side"] = _crosstab(ms[members], f.out_side[members])
            soma = fct["somaSide"].map({"LHS": "L", "RHS": "R", "Midline": "M"})
            mss = np.array([soma.get(int(v)) if pd.notna(v) and int(v) in soma.index else None for v in mb], dtype=object)
            sel = np.flatnonzero(~dn_mask & (f.net.table["superclass"].to_numpy() != "descending_neuron") & pd.notna(mss))
            rec["handedness_nondn_vs_matched_manc_soma_side"] = _crosstab(f.side_annot[sel], mss[sel])
            lr = [i for i in sel if f.side_annot[i] in ("L", "R") and mss[i] in ("L", "R")]
            same = sum(1 for i in lr if f.side_annot[i] == mss[i])
            rec["handedness_summary"] = {"both_sided": len(lr), "same_side": same, "share": same / len(lr) if lr else None}
        out[name] = rec
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1, default=str) + "\n")
    for name in ("MANC", "MaleCNS"):
        r = out[name]
        print(name, json.dumps(r["rule"]), json.dumps(r["nondn_soma_position_check"]), json.dumps(r.get("handedness_summary")))


if __name__ == "__main__":
    main()
