"""Networks, read-outs and stimulation groups for the ledger arms.

* MANC front-leg network (4,604): built by the SAME helper as the saved screen B0, ``paper_network("manc", "v1.2.1", "paper")``
  in ``benchmarks/dng100_walking_cpg/reproduce_dynamics.py`` (imported read-only), so the matrix is identical to B0's.
* MANC full nerve cord (23,532): the authors' full-cord node list (pinned file) on the ``manc:v1.2.3`` build, paper NT
  labels, floor 5, the authors' 16 autapses kept and the authors' sizes (their full-cord matrix and table, reproduced
  exactly; ledger LOG L10). Gate G0 showed every pair and count equal to the authors' matrix; `full_cord` re-checks the
  signed matrix pair by pair and refuses to return a network that differs.
* Groups: the authors' type grouping (``dns_by_type``): excitatory DNs (authors' table: class "descending neuron", predictedNt
  "acetylcholine") grouped by the authors' ``type`` column. All-member groups (every DN of a type, any transmitter) are used
  by the walking-background arm B4.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

from . import REPO

_BENCH = REPO / "benchmarks" / "dng100_walking_cpg"
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))

DN_CLASS = "descending neuron"
EXC_NT = "acetylcholine"
E1_TYPE = "IN17A001"  # the published core excitatory interneuron; its per-leg copies are the paper's six-leg phase signal


@dataclass
class LedgerNetwork:
    name: str
    W: object                 # scipy CSR, post x pre, signed counts
    sizes: np.ndarray | None
    table: pd.DataFrame       # authors' table, row order = network positions (RangeIndex)
    readout: np.ndarray       # bool mask of the main read-out (front-leg MNs / all module MNs)
    meta: dict

    @property
    def n(self) -> int:
        return int(self.W.shape[0])


@lru_cache(maxsize=1)
def front_leg() -> LedgerNetwork:
    from reproduce_dynamics import paper_network  # noqa: PLC0415 - read-only import of benchmark tooling

    wt, net, readout = paper_network("manc", "v1.2.1", "paper")
    wt = wt.reset_index(drop=True)
    if not (wt["bodyId"].to_numpy() == net.ids).all():
        raise RuntimeError("authors' table order != network order")
    meta = dict(net.meta)
    meta.update(network="manc_v1.2.1_frontleg_paper", builder="benchmarks/dng100_walking_cpg/reproduce_dynamics.py::paper_network",
                readout="role vnc_motor & sub_class fl (144)", n_readout=int(readout.sum()))
    return LedgerNetwork("manc_v1.2.1_frontleg", net.W, net.sizes, wt, np.asarray(readout, bool), meta)


@lru_cache(maxsize=1)
def full_cord() -> LedgerNetwork:
    from brainir.graph import Connectome
    from brainir.sim import build_network
    from reproduce_manc_connectivity import authors_full, fetch_external  # noqa: PLC0415

    files = fetch_external()
    wt, pairs = authors_full(files)
    wt = wt.reset_index(drop=True)
    ids = wt["bodyId"].to_numpy().astype(np.int64)
    cx = Connectome.open("manc", "v1.2.3")
    # sizes: the authors' own full-cord table (every neuron has one). manc:v1.0 lacks 207 of these bodies and differs for 57
    # more, which would also shift the median used for size scaling (ledger LOG L10).
    sizes = wt.set_index("bodyId")["size"].astype("float64").to_dict()
    override = wt.set_index("bodyId")["predictedNt"].to_dict()
    # remove_autapses=False: unlike their front-leg matrix, the authors' full-cord matrix keeps 16 (inhibitory) autapses;
    # the ledger reproduces the authors' full-cord network exactly (ledger LOG L10)
    net = build_network(cx, ids, floor=5, sign_basis="nt_body_prediction", nt_override=override, sizes=sizes,
                        size_source="authors' full-cord table column 'size' (wTable_20251006)", remove_autapses=False)
    # re-check the signed matrix against the authors' pair table (pre, post, signed count)
    pos = {int(b): i for i, b in enumerate(ids)}
    W = net.W.tocoo()
    mine = pd.DataFrame({"pre_id": ids[W.col], "post_id": ids[W.row], "w": W.data.astype(np.int64)})
    auth = pairs.rename(columns={"w_signed": "w"})[["pre_id", "post_id", "w"]]
    auth = auth[auth["w"] != 0]
    m = mine.merge(auth, on=["pre_id", "post_id"], how="outer", suffixes=("_b", "_a"), indicator=True)
    n_equal = int(((m["_merge"] == "both") & (m["w_b"] == m["w_a"])).sum())
    check = {"pairs_brainir": int(len(mine)), "pairs_authors": int(len(auth)), "pairs_equal_signed": n_equal}
    if not (n_equal == len(mine) == len(auth)):
        raise RuntimeError(f"full-cord signed matrix differs from the authors': {check}")
    size_auth = wt["size"].astype("float64").to_numpy()
    size_used = np.array([sizes.get(int(i), np.nan) for i in ids])
    mod = wt["motor module"].fillna("").astype(str).to_numpy()
    readout = mod != ""
    meta = dict(net.meta)
    meta.update(network="manc_v1.2.3_fullcord_paper", authors_check=check, n_readout=int(readout.sum()),
                readout="authors' module-labelled MNs (329), per leg by somaNeuromere x somaSide",
                sizes_equal_authors=int(np.sum(np.isclose(size_auth, size_used))), n=int(len(ids)), n_autapses_kept=int(len(pos) and
                                                                                                             (net.W.diagonal() != 0).sum()))
    return LedgerNetwork("manc_v1.2.3_fullcord", net.W, net.sizes, wt, readout, meta)


def exc_dn_mask(table: pd.DataFrame) -> np.ndarray:
    return ((table["class"] == DN_CLASS) & (table["predictedNt"] == EXC_NT)).to_numpy()


def dn_mask(table: pd.DataFrame) -> np.ndarray:
    return (table["class"] == DN_CLASS).to_numpy()


def type_groups(table: pd.DataFrame, *, excitatory_only: bool = True, side: str | None = None) -> dict[str, list[int]]:
    """{type: sorted member positions}; the authors' grouping when ``excitatory_only``. ``side`` = 'LHS'/'RHS' keeps members
    whose ``rootSide`` matches (full cord only)."""
    m = exc_dn_mask(table) if excitatory_only else dn_mask(table)
    if side is not None:
        m = m & (table["rootSide"] == side).to_numpy()
    sub = table.loc[m & table["type"].notna().to_numpy()]
    out: dict[str, list[int]] = {}
    for t, g in sub.groupby("type", sort=True):
        out[str(t)] = sorted(int(i) for i in g.index)
    return out


def leg_setup(net: LedgerNetwork) -> dict:
    """Per-leg MN masks, leg-signal groups and E1 copy positions for a network with the authors' full-cord columns."""
    from . import legs as L

    masks = L.leg_masks(net.table, net.n)
    groups = L.leg_signal_groups(net.table)
    e1 = net.table.loc[net.table["type"] == E1_TYPE]
    e1_pos = {}
    for i, r in e1.iterrows():
        leg = L.leg_of(r["somaNeuromere"], r["somaSide"])
        if leg is None or leg in e1_pos:
            raise RuntimeError(f"unexpected E1 copy layout at row {i}")
        e1_pos[leg] = int(i)
    if set(e1_pos) != set(L.LEGS):
        raise RuntimeError(f"E1 copies found for {sorted(e1_pos)} only")
    return {"masks": masks, "groups": groups, "e1": e1_pos}
