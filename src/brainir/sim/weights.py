"""Signed synapse-count matrices for the rate model, built from a BrainIR Connectome.

This is the bridge from anatomy to the model layer, and every modelling assumption made here is explicit:

* ``synapse_count`` (anatomy) becomes a signed integer weight only through a *sign hypothesis* (rule
  :data:`brainir.schema.vocab.SIGN_RULE_ID` applied to a chosen neurotransmitter field, or externally supplied labels).
* A minimum synapse count per pair (``floor``) drops weak pairs (the paper used 5).
* Autapses are removed (the paper's matrices have an all-zero diagonal).
* Optionally only synapses inside a set of neuropils are counted (the paper restricted the MaleCNS network to VNC ROIs).

The result is a :class:`Network` (post x pre CSR matrix, positional ids, per-neuron sign/NT/size table, provenance).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import scipy.sparse as sp

from ..graph import NT_BASIS_ORDER, Connectome
from ..schema.vocab import SIGN_RULE_ID, sign_for_nt

PAPER_SIGN_RULE_ID = "pugliese2026.sign.predictedNt"
"""Cholinergic +1; GABAergic and glutamatergic -1; every other label (incl. 'unknown'/'unclear'/missing) -> 0 (no output)."""


def paper_sign(nt: str | None) -> int:
    return {"acetylcholine": 1, "gaba": -1, "glutamate": -1}.get(nt, 0)


def brainir_sign(nt: str | None) -> int:
    rule = sign_for_nt(nt)
    return 0 if rule is None or rule.sign is None else int(rule.sign)


@dataclass
class Network:
    ids: np.ndarray
    """Dataset-native neuron IDs in positional order (row/column i of W is ids[i])."""
    W: sp.csr_matrix
    """Signed synapse counts, post x pre (W[i, j] = synapses from ids[j] onto ids[i], signed by the sign of j)."""
    signs: np.ndarray
    """+1 / -1 / 0 per presynaptic neuron."""
    nt: np.ndarray
    """Neurotransmitter label each sign was derived from (object array; None where unknown)."""
    sizes: np.ndarray | None
    """Segment sizes (voxels) used for size scaling; None when not available."""
    table: pd.DataFrame
    """One row per neuron: source_id, cell_type, super_class, role_class, nt_used, sign, size, plus source columns."""
    meta: dict = field(default_factory=dict)
    C: sp.csr_matrix | None = None
    """Observed (unsigned) synapse counts, post x pre, same floor/autapse handling as W but INCLUDING the pairs whose
    presynaptic neuron has sign 0 (they vanish from W). Anatomy; W is anatomy x sign hypothesis."""

    @property
    def n(self) -> int:
        return int(len(self.ids))

    def index_of(self, ids: Iterable[int]) -> np.ndarray:
        pos = {int(i): k for k, i in enumerate(self.ids)}
        return np.array([pos[int(i)] for i in ids], dtype=np.int64)

    def positions_of_type(self, cell_type: str) -> np.ndarray:
        return np.flatnonzero(self.table["cell_type"].to_numpy() == cell_type)

    def positions_where(self, mask: np.ndarray | pd.Series) -> np.ndarray:
        return np.flatnonzero(np.asarray(mask, dtype=bool))

    def dense(self) -> np.ndarray:
        return self.W.toarray()


def vnc_neuropils(cx: Connectome) -> set[str]:
    """Primary neuropils whose top-level region is the VNC (all of them for MANC)."""
    np_ = cx.neuropils
    return set(np_.loc[np_["top_level_region"].eq("VNC") & np_["is_primary"], "name"])


def _counts(cx: Connectome, ids: np.ndarray, roi_restrict: set[str] | None) -> pd.DataFrame:
    if roi_restrict is None:
        e = cx.edges_between(ids, ids, annotate=False)[["pre_id", "post_id", "synapse_count"]]
        return e
    cn = cx.connection_neuropils(ids, ids)
    cn = cn[cn["neuropil"].isin(roi_restrict)]
    return cn.groupby(["pre_id", "post_id"], as_index=False)["synapse_count"].sum()


def signed_matrix(cx: Connectome, ids: Iterable[int], *, floor: int = 5, sign_basis: str = "auto",
                  nt_override: Mapping[int, str | None] | None = None, sign_rule: str = "paper",
                  remove_autapses: bool = True, roi_restrict: Iterable[str] | None = None,
                  sizes: Mapping[int, float] | pd.Series | None = None, size_source: str | None = None) -> Network:
    """Build the signed count matrix for the neurons ``ids`` (their order is kept).

    ``sign_basis``: NT field of the neurons table ('auto' = first non-null of NT_BASIS_ORDER per neuron).
    ``nt_override``: external NT labels by source_id (e.g. the labels a paper used), taking precedence.
    ``sign_rule``: 'paper' (ACh+, GABA/Glu-, else 0) or 'brainir' (SIGN_RULE_ID; None -> 0).
    ``roi_restrict``: count only synapses whose postsynaptic site lies in these neuropils.
    ``sizes``: external sizes by source_id (e.g. from another release when the build carries none)."""
    ids = np.asarray(list(ids), dtype=np.int64)
    if len(np.unique(ids)) != len(ids):
        raise ValueError("ids must be unique")
    missing = [int(i) for i in ids if not cx.has(int(i))]
    if missing:
        raise KeyError(f"{len(missing)} ids are not neurons of {cx.dataset}:{cx.version}: {missing[:10]}")
    n = len(ids)
    pos = pd.Series(np.arange(n), index=ids)
    neurons = cx.neurons.loc[ids]
    # neurotransmitter label per neuron
    if sign_basis == "auto":
        nt_used = pd.Series([None] * n, index=ids, dtype=object)
        basis_used = pd.Series([None] * n, index=ids, dtype=object)
        for b in NT_BASIS_ORDER:
            fill = nt_used.isna() & neurons[b].notna()
            nt_used[fill] = neurons.loc[fill, b]
            basis_used[fill] = b
    else:
        nt_used = neurons[sign_basis].astype(object).where(neurons[sign_basis].notna(), None)
        basis_used = pd.Series([sign_basis] * n, index=ids, dtype=object)
    n_override = 0
    if nt_override is not None:
        for i in ids:
            if int(i) in nt_override:
                nt_used[i] = nt_override[int(i)]
                basis_used[i] = "override"
                n_override += 1
    rule = paper_sign if sign_rule == "paper" else brainir_sign
    signs = np.array([rule(v) for v in nt_used], dtype=np.int8)
    roi = set(roi_restrict) if roi_restrict is not None else None
    e = _counts(cx, ids, roi)
    e = e[e["synapse_count"] >= floor]
    if remove_autapses:
        e = e[e["pre_id"] != e["post_id"]]
    pi = pos.loc[e["pre_id"].to_numpy()].to_numpy()
    qi = pos.loc[e["post_id"].to_numpy()].to_numpy()
    vals = e["synapse_count"].to_numpy().astype(np.float64) * signs[pi]
    W = sp.csr_matrix((vals, (qi, pi)), shape=(n, n))
    W.eliminate_zeros()
    C = sp.csr_matrix((e["synapse_count"].to_numpy().astype(np.float64), (qi, pi)), shape=(n, n))
    if sizes is not None:
        size_arr = np.array([float(sizes.get(int(i), np.nan)) if hasattr(sizes, "get") else float(sizes[int(i)]) for i in ids])
        src = size_source or "external"
    else:
        s = neurons["size_voxels"]
        size_arr = s.astype("float64").to_numpy() if s.notna().any() else None
        src = f"{cx.dataset}:{cx.version} size_voxels" if size_arr is not None else None
    table = pd.DataFrame({
        "source_id": ids, "cell_type": neurons["cell_type"].to_numpy(), "instance": neurons["instance"].to_numpy(),
        "super_class": neurons["super_class"].to_numpy(), "sub_class": neurons["sub_class"].to_numpy(),
        "role_class": neurons["role_class"].to_numpy(),
        "nt_used": nt_used.to_numpy(), "nt_basis": basis_used.to_numpy(), "sign": signs,
        "size": size_arr if size_arr is not None else np.nan,
        "out_pairs": np.bincount(pi, minlength=n), "in_pairs": np.bincount(qi, minlength=n),
    })
    meta = {"dataset": cx.dataset, "version": cx.version, "n": n, "floor": floor, "remove_autapses": remove_autapses,
            "sign_basis": sign_basis, "sign_rule": PAPER_SIGN_RULE_ID if sign_rule == "paper" else SIGN_RULE_ID,
            "nt_overrides": n_override, "roi_restrict": sorted(roi) if roi is not None else None,
            "n_pairs": int(W.nnz), "total_synapses": int(np.abs(W.data).sum()),
            "n_pairs_observed": int(C.nnz), "total_synapses_observed": int(C.data.sum()),
            "n_positive_rows": int((signs > 0).sum()), "n_negative_rows": int((signs < 0).sum()),
            "n_zero_rows": int((signs == 0).sum()), "size_source": src}
    return Network(ids=ids, W=W, signs=signs, nt=nt_used.to_numpy(), sizes=size_arr, table=table, meta=meta, C=C)


def build_network(cx: Connectome, ids: Iterable[int], **kw) -> Network:
    """Alias of :func:`signed_matrix` (kept for readability at call sites)."""
    return signed_matrix(cx, ids, **kw)
