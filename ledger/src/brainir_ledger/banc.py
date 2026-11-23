"""BANC, the third animal (RUN6_PROMPT Stage 1; LOG L177+): the authors' female brain-and-nerve-cord front-leg network, used as
released.

Sources (Pugliese et al. 2026 repository at the commit pinned in `authors.py`, checked by SHA-256):
- `data/banc t1 premotor/W_20260217.npz`: 4,963 x 4,963 signed synapse counts, rows = presynaptic, no synapse floor;
- `wTable_20260217_fullData.csv`: the table named by the authors' BANC DNg100 run config (Zenodo run 33241778);
- `wTable_20260217_fullData_consistentColumns.csv`: the same rows plus `predictedNt` and `class` (fetched for the record; the
  match columns are identical in both).

Build, the authors' way (`vnc_sim.py` as documented in `research/literature/pugliese_model_spec_from_code.md`):
- the released signed matrix as it is, transposed to post x pre; its signs are checked against the transmitter rule (verified, else
  predicted; acetylcholine +, GABA and glutamate -) and every exception is reported, not changed;
- sizes = `surf_area_um2` (NaN or 0 -> the median, as the model does);
- excitatory descending neurons: `super_class == 'descending'` and acetylcholine by `neurotransmitter_verified`, else
  `neurotransmitter_predicted` (the authors' rule for BANC-style tables);
- read-out: the 139 front-leg motor neurons (`cell_class == 'leg_motor_neuron'`, `body_part_effector == 'front_leg'`), sides from
  `side`; the 12 neck motor neurons are left out, as in the MANC and MaleCNS read-outs.

Type matching (fixed before any screen; same spirit as run 5's MaleCNS rule, LOG L160): each BANC descending neuron is mapped to a
MANC type through `manc_121_match_id` (a MANC v1.2.1 bodyId whose type is known in the ledger's MANC front-leg or full-cord tables),
else through the `manc_121_cell_type` string. Per MANC type (its BANC excitatory members): **high** = every member matched by ID, no
ID match conflicting with the type name, and one-to-one naming (the members' BANC labels map only to this MANC type, and the MANC type
receives exactly one BANC label, over all mapped BANC descending neurons); **low** = any member whose ID match conflicts with its
`manc_121_cell_type` string (or whose IDs resolve to two MANC types); **medium** = the rest.
"""

from __future__ import annotations

import hashlib
import re
import urllib.parse
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import scipy.sparse as sp
from brainir import paths

from . import authors as A
from . import networks as N

FILES = {
    "W_20260217.npz": "83197529fa336b5f9ce400cf689f299fa3e8f6f5379947ae7df5ec004869141f",
    "wTable_20260217_fullData.csv": "b4b9affd59916abed5723a84baf4ea2f765e0684d6387fe87f52fb3520c8ec33",
    "wTable_20260217_fullData_consistentColumns.csv": "6f87bf62227e160754523418bfbac35fc8971a90e4ed54574bf769b08332e285",
}
REL = "data/banc t1 premotor/"
EXC_NT = "acetylcholine"
# the authors' run configs (Zenodo 10.5281/zenodo.22260924): DNg100 at 400 on position 1605; silencing positions 1689 (E1,
# IN17A001), 910 (E2, INXXX466), 3334 (I2, IN19A007), run 34106247
AUTHORS_DNG100_POS = 1605
AUTHORS_STIM_I = 400.0
CIRCUIT = {"E1": 1689, "E2": 910, "I2": 3334}
CIRCUIT_ROOT = {"E1": 720575941504247575, "E2": 720575941469024064, "I2": 720575941569601650}


def ext_dir() -> Path:
    d = paths.data_root() / "raw" / "external" / "pugliese_2026" / A.COMMIT[:10] / "banc"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetch() -> dict[str, Path]:
    out = {}
    for name, sha in FILES.items():
        p = ext_dir() / name
        if not p.exists():
            url = f"https://raw.githubusercontent.com/{A.REPO_ID}/{A.COMMIT}/{urllib.parse.quote(REL + name)}"
            r = requests.get(url, timeout=600)
            r.raise_for_status()
            p.write_bytes(r.content)
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if got != sha:
            raise RuntimeError(f"{name}: sha256 {got} != pinned {sha}")
        out[name] = p
    return out


@lru_cache(maxsize=1)
def table() -> pd.DataFrame:
    t = pd.read_csv(fetch()["wTable_20260217_fullData.csv"], low_memory=False)
    if not (t["Unnamed: 0"].to_numpy() == np.arange(len(t))).all():
        raise RuntimeError("table index is not positional")
    t = t.drop(columns=["Unnamed: 0"])
    t["nt"] = t["neurotransmitter_verified"].where(t["neurotransmitter_verified"].notna(), t["neurotransmitter_predicted"])
    t["exc_dn"] = (t["super_class"] == "descending") & (t["nt"] == EXC_NT)
    t["front_leg_mn"] = (t["cell_class"] == "leg_motor_neuron") & (t["body_part_effector"] == "front_leg")
    t["side_lr"] = t["side"].map({"left": "L", "right": "R"}).fillna("M")
    return t


def parse_ids(s) -> list[int]:
    if not isinstance(s, str) or not s.strip():
        return []
    return [int(x) for x in re.findall(r"id:(\d+)", s)]


@lru_cache(maxsize=1)
def manc_body2type() -> dict[int, str]:
    """MANC v1.2.1 bodyId -> type, from the ledger's MANC full-cord table, the front-leg table taking precedence (as B2's mapping)."""
    fc = N.full_cord().table
    ft = N.front_leg().table
    return {**dict(zip(fc["bodyId"].astype(int), fc["type"].astype(str))), **dict(zip(ft["bodyId"].astype(int), ft["type"].astype(str)))}


@lru_cache(maxsize=1)
def dn_mapping() -> pd.DataFrame:
    """Every BANC descending neuron with its MANC type: by ID where the IDs resolve to one MANC type, else by the string."""
    t = table()
    b2t = manc_body2type()
    rows = []
    for i in np.flatnonzero((t["super_class"] == "descending").to_numpy()):
        r = t.iloc[i]
        ids = parse_ids(r["manc_121_match_id"])
        id_types = sorted({b2t[b] for b in ids if b in b2t})
        name = r["manc_121_cell_type"] if isinstance(r["manc_121_cell_type"], str) else None
        if len(id_types) == 1:
            mapped, by = id_types[0], "id"
        elif len(id_types) > 1:
            mapped, by = (name if name in id_types else id_types[0]), "id_ambiguous"
        elif name:
            mapped, by = name, "name"
        else:
            mapped, by = None, None
        conflict = bool((by == "id" and name is not None and name != mapped) or by == "id_ambiguous")
        rows.append({"pos": int(i), "pt_root_id": int(r["pt_root_id"]), "banc_label": str(r["cell_type"]), "side": r["side_lr"],
                     "nt": r["nt"], "exc_dn": bool(r["exc_dn"]), "ids": ";".join(map(str, ids)), "n_ids": len(ids),
                     "n_ids_resolved": sum(b in b2t for b in ids), "manc_121_cell_type": name, "manc_type": mapped, "mapped_by": by,
                     "id_conflict": conflict})
    return pd.DataFrame(rows)


@lru_cache(maxsize=1)
def network() -> N.LedgerNetwork:
    t = table()
    Wf = np.load(fetch()["W_20260217.npz"])["arr_0"]
    if Wf.shape != (len(t), len(t)):
        raise RuntimeError(f"matrix shape {Wf.shape} != table rows {len(t)}")
    W = sp.csr_matrix(Wf.T)  # post x pre
    W.eliminate_zeros()
    readout = t["front_leg_mn"].to_numpy()
    return N.LedgerNetwork("banc_frontleg_authors_W20260217", W, t["surf_area_um2"].astype(float).to_numpy(), t, readout,
                           {"network": "authors' BANC front-leg network (W_20260217.npz, wTable_20260217_fullData.csv), as released",
                            "n": int(len(t)), "n_readout": int(readout.sum()),
                            "n_readout_L": int((readout & (t["side_lr"] == "L").to_numpy()).sum()),
                            "n_readout_R": int((readout & (t["side_lr"] == "R").to_numpy()).sum())})


def readout_side(side: str) -> np.ndarray:
    t = table()
    return (t["front_leg_mn"] & (t["side_lr"] == side)).to_numpy()


@lru_cache(maxsize=1)
def groups() -> dict[str, list[int]]:
    """Excitatory BANC DNs grouped by their mapped MANC type (the whole-type screen's groups)."""
    m = dn_mapping()
    out: dict[str, list[int]] = {}
    for _, r in m[m["exc_dn"] & m["manc_type"].notna()].iterrows():
        out.setdefault(str(r["manc_type"]), []).append(int(r["pos"]))
    return {k: sorted(v) for k, v in sorted(out.items())}


def match_confidence() -> pd.DataFrame:
    """Per MANC type with BANC excitatory members: the evidence and the confidence (module docstring)."""
    m = dn_mapping()
    mapped = m[m["manc_type"].notna()]
    lab_to_manc: dict[str, set] = {}
    manc_to_lab: dict[str, set] = {}
    for _, r in mapped.iterrows():
        lab_to_manc.setdefault(r["banc_label"], set()).add(r["manc_type"])
        manc_to_lab.setdefault(r["manc_type"], set()).add(r["banc_label"])
    rows = []
    for mt, idx in groups().items():
        g = mapped.set_index("pos").loc[idx]
        by_id = (g["mapped_by"] == "id").to_numpy()
        cf = g["id_conflict"].to_numpy()
        labels = sorted(set(g["banc_label"]))
        one = len(manc_to_lab.get(mt, ())) == 1 and all(len(lab_to_manc[lab]) == 1 for lab in labels)
        conf = "low" if cf.any() else ("high" if (by_id.all() and one) else "medium")
        rows.append({"manc_type": mt, "banc_labels": ";".join(labels), "n_banc_members": len(idx),
                     "banc_L": int((g["side"] == "L").sum()), "banc_R": int((g["side"] == "R").sum()), "banc_M": int((g["side"] == "M").sum()),
                     "all_id_matched": bool(by_id.all()), "n_id_matched": int(by_id.sum()), "n_conflicts": int(cf.sum()),
                     "one_to_one_naming": bool(one), "same_name": all(lab == mt for lab in labels), "confidence": conf})
    return pd.DataFrame(rows)


def sign_check() -> dict:
    """Rows of the released matrix: single-signed, and their sign against the transmitter rule (reported, never changed)."""
    t = table()
    Wf = np.load(fetch()["W_20260217.npz"])["arr_0"]
    pos, neg = (Wf > 0).any(1), (Wf < 0).any(1)
    sign = np.where(pos, 1, np.where(neg, -1, 0))
    exp = t["nt"].map({"acetylcholine": 1, "gaba": -1, "glutamate": -1})
    ok = exp.notna().to_numpy() & (sign != 0)
    agree = int((sign[ok] == exp.to_numpy()[ok]).sum())
    other = t.loc[~exp.notna().to_numpy() & (sign != 0), "nt"].fillna("NaN").value_counts().to_dict()
    silent = t.loc[sign == 0, "nt"].fillna("NaN").value_counts().to_dict()
    return {"n_rows": int(len(t)), "rows_mixed_sign": int((pos & neg).sum()), "rows_with_outputs": int((sign != 0).sum()),
            "rule_rows_with_outputs": int(ok.sum()), "rule_rows_agreeing": agree, "other_nt_rows_with_outputs": other,
            "rows_without_outputs_by_nt": silent, "nnz": int((Wf != 0).sum()), "sum_abs": float(np.abs(Wf).sum()),
            "min_abs_nonzero": float(np.abs(Wf[Wf != 0]).min()), "autapses": int((np.diag(Wf) != 0).sum())}
