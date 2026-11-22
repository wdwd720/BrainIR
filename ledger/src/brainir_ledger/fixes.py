"""Run 4 (PREREG v4 B4, C2, C4, C5): MANC pre-floor counts and count-noise copies, the network-level fixes 3-8, gain, and the
rewired control that every fix is also applied to.

Wiring only: nothing here simulates. Every function returns new objects and never modifies its inputs. This matters: a `Fly`'s
`C` can share its arrays with the cached `networks.front_leg()` matrix (`sp.csr_matrix(X, dtype=float64)` does not copy), so
every matrix is copied (`_canon`) before any in-place operation.

Conventions
-----------
* Matrices are post x pre (row i = the inputs of neuron i, column j = the outputs of neuron j), as everywhere in BrainIR.
* A network state is (C, sign, sizes): unsigned counts C, presynaptic sign per neuron (+1 / -1 / 0) and sizes; the signed matrix
  is W = C x sign[column] (`signed`). The fixes compose on this state (C2.8), so a sign changed by fix 7 also applies to the
  counts of a neuron whose sign was 0 (MANC's C keeps those connections; W drops them only because of the sign).
* The fixes read only `fly.C`, `fly.sign`, `fly.net.sizes`, `fly.ntype` and `fly.side`, never `fly.net.W` / `fly.net.C`
  (for the rewired control `net` is still the real network).
* Every returned matrix is canonical CSR float64 (duplicates summed, explicit zeros removed, indices sorted).
* Mirror map (G4, `mirror.mirror_map`): a real neuron i is "matched or self-mapped" iff its status is g1 / g2 / t / self; its real
  partner is m[i] (< n; i itself when self-mapped). Unmatched neurons (partner = a ghost slot) are left out of every homologous
  pairing (fix 4, B4.3).
* Neuron type = `fly.ntype` (the network table's `type`); a neuron without a type is its own type (fixes 5-7).
"""

from __future__ import annotations

import dataclasses
from functools import lru_cache

import numpy as np
import scipy.sparse as sp

from . import controls
from . import mirror as MI
from . import networks as N

MATCHED_OR_SELF = ("g1", "g2", "t", "self")
REWIRE_CONTROL = "B1-ctl-rewire-101"  # C5: run 1's degree-preserving generator, network seed 101
FIXES = ("3a", "3b", "4", "5a", "5b", "6", "7", "8")
FLOOR_OF_FIX = {"3a": 1, "3b": 3}  # C2.3
B1R_FLOOR = 5
_SIDE_CODE = {"L": 0, "R": 1, "M": 2}  # anything else -> 3 (U), as `mirror.mirror_map` normalises sides
_BUILD_KEYS = ("dataset", "version", "n", "remove_autapses", "sign_basis", "sign_rule", "nt_overrides", "roi_restrict", "size_source")


# ----------------------------------------------------------------------------------------------------------------- helpers
def _canon(X) -> sp.csr_matrix:
    """A canonical CSR float64 COPY of X (duplicates summed, explicit zeros removed, column indices sorted)."""
    C = sp.csr_matrix(X, dtype=np.float64, copy=True)
    C.sum_duplicates()
    C.eliminate_zeros()
    C.sort_indices()
    return C


def _same(A: sp.csr_matrix, B: sp.csr_matrix) -> bool:
    """Exact equality of two canonical CSR matrices: shape, pattern and values."""
    return (A.shape == B.shape and np.array_equal(A.indptr, B.indptr) and np.array_equal(A.indices, B.indices)
            and np.array_equal(A.data, B.data))


def signed(C, sign) -> sp.csr_matrix:
    """W = C x sign of the presynaptic neuron (column j times sign[j]); columns of sign-0 neurons vanish. Canonical copy."""
    C = _canon(C)
    s = np.asarray(sign, dtype=np.float64)
    if s.shape != (C.shape[1],):
        raise ValueError(f"sign has shape {s.shape}, matrix has {C.shape[1]} columns")
    C.data = C.data * s[C.indices]
    C.eliminate_zeros()
    return C


def _state(fly) -> tuple[sp.csr_matrix, np.ndarray, np.ndarray | None]:
    """(C, sign, sizes) of a fly, all copies (the fly is never modified)."""
    C = _canon(fly.C)
    if C.shape[0] != C.shape[1]:
        raise ValueError(f"{fly.name}: C is not square {C.shape}")
    if C.nnz and C.data.min() < 0:
        raise ValueError(f"{fly.name}: C must hold unsigned counts")
    sign = np.array(fly.sign, dtype=np.float64)
    if sign.shape != (C.shape[0],):
        raise ValueError(f"{fly.name}: sign has shape {sign.shape}, network has {C.shape[0]} neurons")
    sizes = None if fly.net.sizes is None else np.array(fly.net.sizes, dtype=np.float64)
    return C, sign, sizes


def _partners(mm: MI.MirrorMap, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """G4 on the real network: (ok, p, self_mapped). ok[i] = neuron i is matched (g1/g2/t) or self-mapped; p[i] = its real
    partner m[i] (i itself if self-mapped); p[i] = i for unmatched neurons (never used as a partner)."""
    if int(mm.n_real) != n:
        raise ValueError(f"mirror map is for {mm.n_real} neurons, the network has {n}")
    status = np.array([str(s) for s in mm.status[:n]], dtype=str)
    m = np.asarray(mm.m[:n], dtype=np.int64)
    ok = np.isin(status, MATCHED_OR_SELF)
    self_mapped = status == "self"
    if (m[ok] >= n).any():
        raise ValueError("mirror map: a matched or self-mapped neuron has a ghost partner")
    p = np.where(ok, m, np.arange(n))
    if not (np.array_equal(p[p], np.arange(n)) and ok[p[ok]].all() and (p[self_mapped] == np.flatnonzero(self_mapped)).all()):
        raise ValueError("mirror map is not an involution on the matched and self-mapped neurons")
    return ok, p, self_mapped


def _type_codes(ntype) -> np.ndarray:
    """Integer type per neuron: typed neurons by their type name (codes 0..T-1, names sorted); every untyped neuron gets its own
    code T + its index, so it cannot coincide with a named type or with another untyped neuron."""
    ntype = list(ntype)
    names = sorted({str(t) for t in ntype if t is not None})
    code = {t: k for k, t in enumerate(names)}
    return np.array([code[str(t)] if t is not None else len(names) + i for i, t in enumerate(ntype)], dtype=np.int64)


def _side_codes(side) -> np.ndarray:
    """L 0, R 1, M 2, anything else (U) 3."""
    return np.array([_SIDE_CODE.get(str(s), 3) for s in side], dtype=np.int64)


def _sizes_of(fly) -> np.ndarray | None:
    return None if fly.net.sizes is None else np.array(fly.net.sizes, dtype=np.float64)


# ------------------------------------------------------------------------------------------- B4: pre-floor counts and noise
@lru_cache(maxsize=1)
def _manc_raw_counts_cached() -> sp.csr_matrix:
    from brainir.graph import Connectome
    from brainir.sim import build_network

    fl = N.front_leg()
    wt = fl.table
    ids = wt["bodyId"].to_numpy().astype(np.int64)
    # exactly the arguments of reproduce_dynamics.paper_network("manc", "v1.2.1", "paper") except the floor: the authors' node
    # list and predictedNt labels (override), sign basis nt_body_prediction, no ROI restriction, the floor-5 build's sizes
    # (manc:v1.0 size_voxels by body ID) and its autapse handling
    override = wt.set_index("bodyId")["predictedNt"].to_dict()
    sizes = dict(zip(ids.tolist(), np.asarray(fl.sizes, dtype=np.float64).tolist()))
    net = build_network(Connectome.open("manc", "v1.2.1"), ids, floor=1, sign_basis="nt_body_prediction", nt_override=override,
                        roi_restrict=None, sizes=sizes, size_source=fl.meta.get("size_source"),
                        remove_autapses=bool(fl.meta["remove_autapses"]))
    diff = {k: (net.meta.get(k), fl.meta.get(k)) for k in _BUILD_KEYS if net.meta.get(k) != fl.meta.get(k)}
    if diff or not np.array_equal(net.ids, ids):
        raise RuntimeError(f"B4.1: the floor-1 build differs from B1r's build in its arguments: {diff}")
    if not np.array_equal(np.asarray(net.sizes, dtype=np.float64), np.asarray(fl.sizes, dtype=np.float64), equal_nan=True):
        raise RuntimeError("B4.1: the floor-1 build's sizes differ from B1r's")
    C1 = _canon(net.C)
    if C1.nnz and (C1.data.min() < 1 or (C1.data != np.round(C1.data)).any()):
        raise RuntimeError("B4.1: raw counts must be integers >= 1")
    # floor 5 must reproduce B1r's matrix exactly (pattern and values), unsigned and signed
    if not _same(at_floor(C1, B1R_FLOOR), _canon(fl.C)):
        raise RuntimeError("B4.1: the floor-1 counts at floor 5 do not reproduce B1r's count matrix")
    if not _same(signed(at_floor(C1, B1R_FLOOR), net.signs), _canon(fl.W)):
        raise RuntimeError("B4.1: the floor-1 counts at floor 5 do not reproduce B1r's signed matrix")
    # every column's sign is the presynaptic sign of the run 4 MANC fly
    sign = np.asarray(MI.fly("MANC").sign, dtype=np.float64)
    if not np.array_equal(np.asarray(net.signs, dtype=np.float64), sign):
        raise RuntimeError("B4.1: the floor-1 build's presynaptic signs differ from mirror.fly('MANC').sign")
    if not _same(_canon(net.W), signed(C1, sign)):
        raise RuntimeError("B4.1: a column of the floor-1 signed matrix disagrees with its neuron's sign")
    return C1


def manc_raw_counts() -> sp.csr_matrix:
    """B4.1: the MANC front-leg network's raw counts (`synapse_count` of the processed `manc:v1.2.1` connections, conf >= 0.4 =
    neuPrint `weight`) at floor 1, unsigned float64 CSR (post x pre) on exactly B1r's node order (`networks.front_leg()`).

    Built by BrainIR's `build_network` the way `reproduce_dynamics.paper_network` builds B1r (same ids, sign basis, NT override,
    sizes and autapse handling: autapses removed, as in B1r) with `floor=1`. Raises unless (C1 >= 5) equals `front_leg().C`
    exactly (and the signed floor-5 matrix equals `front_leg().W`) and every column's sign equals `mirror.fly("MANC").sign`.
    The build is cached; a copy is returned, so callers may modify it."""
    return _manc_raw_counts_cached().copy()


def at_floor(C1, f: float) -> sp.csr_matrix:
    """B4.4 / C2.3: keep the entries >= f (canonical copy)."""
    C = _canon(C1)
    C.data[C.data < f] = 0.0
    C.eliminate_zeros()
    return C


def _raw(C1) -> sp.csr_matrix:
    C = _canon(C1)
    if C.nnz and C.data.min() < 1:
        raise ValueError("raw counts must be >= 1 (an entry < 1: a signed or rescaled matrix?)")
    return C


def poisson_copy(C1, seed: int) -> sp.csr_matrix:
    """B4.2: every raw count c >= 1 replaced by a Poisson(c) draw of `numpy.random.default_rng(seed)`, one vectorised draw over
    the CSR data in canonical order (duplicates summed, explicit zeros removed, indices sorted, i.e. row-major); zero draws are
    removed. The floor is applied by the caller (`at_floor`). Seeds of record: 20261411, 20261412 (G10)."""
    C = _raw(C1)
    rng = np.random.default_rng(int(seed))
    C.data = rng.poisson(C.data).astype(np.float64)
    C.eliminate_zeros()
    return C


def nb_inverse_k(C1, mm: MI.MirrorMap) -> dict:
    """B4.3: the measured left-right dispersion 1/k of raw counts.

    Over unordered homologous pairs {(i, j), (m(i), m(j))} with i and j each matched or self-mapped (G4), not both self-mapped
    (then the two entries would be the same entry), counted once each, with c_L = C1[i, j], c_R = C1[m(i), m(j)] and at least one
    of them >= 1 (the pairs are taken on the union of the pattern and its mirror image, so a pair with one zero side counts):
    mbar = (c_L + c_R) / 2, excess = (c_L - c_R)^2 / 2 - mbar, and 1/k = sum(excess * mbar^2) / sum(mbar^4) (least squares
    through the origin of the excess variance on mbar^2). Returns {"inv_k", "n_pairs"}; inv_k is NaN when there is no pair.
    Unmatched neurons (partner = a ghost) are left out."""
    C = _canon(C1)
    if C.nnz and C.data.min() < 0:
        raise ValueError("counts must be unsigned")
    n = C.shape[0]
    ok, p, self_mapped = _partners(mm, n)
    coo = C.tocoo()
    keep = ok[coo.row] & ok[coo.col]
    A = sp.csr_matrix((coo.data[keep], (coo.row[keep], coo.col[keep])), shape=C.shape)
    Am = A[p][:, p]  # Am[i, j] = A[m(i), m(j)]
    U = _canon(A + Am).tocoo()  # union of the pattern and its mirror image (counts >= 0: nothing cancels)
    if U.nnz == 0:
        return {"inv_k": float("nan"), "n_pairs": 0}
    i, j = U.row.astype(np.int64), U.col.astype(np.int64)
    c_l = np.asarray(A[i, j], dtype=np.float64).ravel()
    c_r = np.asarray(Am[i, j], dtype=np.float64).ravel()
    lin, lin_m = i * n + j, p[i] * n + p[j]
    sel = ~(self_mapped[i] & self_mapped[j]) & (lin < lin_m) & ((c_l >= 1) | (c_r >= 1))  # lin < lin_m: once per pair
    c_l, c_r = c_l[sel], c_r[sel]
    mbar = (c_l + c_r) / 2.0
    excess = (c_l - c_r) ** 2 / 2.0 - mbar
    inv_k = float(np.sum(excess * mbar ** 2) / np.sum(mbar ** 4)) if len(mbar) else float("nan")
    return {"inv_k": inv_k, "n_pairs": int(sel.sum())}


def nb_copy(C1, inv_k: float, seed: int) -> sp.csr_matrix:
    """B4.3: every raw count c >= 1 replaced by a negative-binomial draw with mean c and size k = 1 / inv_k
    (`rng.negative_binomial(k, k / (k + c))`, variance c + c^2 / k), one vectorised draw in canonical order as `poisson_copy`;
    zero draws removed; the floor is applied by the caller. If inv_k <= 0 the dispersion model is Poisson (B4.3) and the result is
    exactly `poisson_copy(C1, seed)`. A non-finite inv_k (e.g. NaN from no pairs) raises. Seeds of record: 20261421, 20261422."""
    inv_k = float(inv_k)
    if not np.isfinite(inv_k):
        raise ValueError(f"inv_k must be finite, got {inv_k}")
    if inv_k <= 0:
        return poisson_copy(C1, seed)
    k = 1.0 / inv_k
    C = _raw(C1)
    rng = np.random.default_rng(int(seed))
    C.data = rng.negative_binomial(k, k / (k + C.data)).astype(np.float64)
    C.eliminate_zeros()
    return C


# --------------------------------------------------------------------------------------- C2: the network-level fixes (core)
def _symmetrise(C, mm: MI.MirrorMap) -> sp.csr_matrix:
    """C2.4 on counts: entries (i, j) with i and j matched or self-mapped -> (C[i, j] + C[m(i), m(j)]) / 2; the rest unchanged."""
    C = _canon(C)
    n = C.shape[0]
    ok, p, _ = _partners(mm, n)
    coo = C.tocoo()
    both = ok[coo.row] & ok[coo.col]
    A = sp.csr_matrix((coo.data[both], (coo.row[both], coo.col[both])), shape=C.shape)
    rest = sp.csr_matrix((coo.data[~both], (coo.row[~both], coo.col[~both])), shape=C.shape)
    Am = A[p][:, p]  # Am[i, j] = A[m(i), m(j)]; A and Am live on ok x ok, `rest` off it, so the sum below is exact
    return _canon((A + Am) * 0.5 + rest)


def _type_pool(C, ntype, side, within_side: bool) -> sp.csr_matrix:
    """C2.5 on counts: each existing connection -> the mean count of the existing connections of its class (same pattern)."""
    C = _canon(C)
    n = C.shape[0]
    tc, sc = _type_codes(ntype), _side_codes(side)
    if len(tc) != n or len(sc) != n:
        raise ValueError("ntype / side do not match the network")
    if C.nnz == 0:
        return C
    coo = C.tocoo()  # canonical (row-major) order: the class sums below run in a fixed order
    post, pre = coo.row.astype(np.int64), coo.col.astype(np.int64)
    if within_side:  # 5a: (presynaptic type, its side, postsynaptic type, its side)
        key = np.stack([tc[pre], sc[pre], tc[post], sc[post]], axis=1)
    else:  # 5b: (presynaptic type, postsynaptic type, same side 0 / different sides 1 / a side not L or R 2)
        both_sided = (sc[pre] <= 1) & (sc[post] <= 1)
        rel = np.where(both_sided, (sc[pre] != sc[post]).astype(np.int64), 2)
        key = np.stack([tc[pre], tc[post], rel], axis=1)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = np.asarray(inv).ravel()
    mean = np.bincount(inv, weights=coo.data) / np.bincount(inv)
    return _canon(sp.csr_matrix((mean[inv], (post, pre)), shape=C.shape))


def _input_normalise(W, ntype) -> sp.csr_matrix:
    """C2.6 on a signed matrix: per typed neuron i (row i = its inputs), positive entries x target_E / E_i and negative entries x
    target_I / I_i, where E_i / I_i = summed positive / |negative| input and the targets are the means over the type's members
    (all sides, zeros included); E_i = 0 (I_i = 0) keeps it; untyped neurons unchanged."""
    W = _canon(W)
    n = W.shape[0]
    rows = np.repeat(np.arange(n), np.diff(W.indptr))
    pos, neg = W.data > 0, W.data < 0
    E = np.bincount(rows[pos], weights=W.data[pos], minlength=n)
    I_ = np.bincount(rows[neg], weights=-W.data[neg], minlength=n)
    typed = np.array([t is not None for t in ntype], dtype=bool)
    if len(typed) != n:
        raise ValueError("ntype does not match the network")
    s_e, s_i = np.ones(n), np.ones(n)
    if typed.any():
        tc = _type_codes(ntype)  # typed neurons: codes 0..T-1
        k = tc[typed]
        T = int(k.max()) + 1
        cnt = np.bincount(k, minlength=T)
        t_e = np.bincount(k, weights=E[typed], minlength=T) / np.maximum(cnt, 1)
        t_i = np.bincount(k, weights=I_[typed], minlength=T) / np.maximum(cnt, 1)
        ok_e, ok_i = typed & (E > 0), typed & (I_ > 0)
        s_e[ok_e] = t_e[tc[ok_e]] / E[ok_e]
        s_i[ok_i] = t_i[tc[ok_i]] / I_[ok_i]
    W.data = W.data * np.where(pos, s_e[rows], np.where(neg, s_i[rows], 1.0))
    return _canon(W)


def _consensus(sign, sizes, ntype) -> tuple[np.ndarray, np.ndarray | None]:
    """C2.7: per type, size -> the median of the members' sizes (NaN ignored; all NaN keeps them) and sign -> the most frequent
    of the members' signs (+1 / -1 / 0) if it is unique, else (a tie) every member keeps its own; untyped neurons unchanged."""
    s0 = np.array(sign, dtype=np.float64)
    z0 = None if sizes is None else np.array(sizes, dtype=np.float64)
    s1 = s0.copy()
    z1 = None if z0 is None else z0.copy()
    members: dict[str, list[int]] = {}
    for i, t in enumerate(ntype):
        if t is not None:
            members.setdefault(str(t), []).append(i)
    for t in sorted(members):
        idx = np.asarray(members[t], dtype=np.int64)
        if z0 is not None:
            v = z0[idx]
            fin = ~np.isnan(v)
            if fin.any():
                z1[idx] = np.median(v[fin])
        vals, counts = np.unique(s0[idx], return_counts=True)
        top = counts == counts.max()
        if top.sum() == 1:
            s1[idx] = vals[top][0]
    return s1, z1


# ------------------------------------------------------------------------------------------------ C2: the fixes on a fly
def _check_floor_fly(fly) -> None:
    if fly.name != "MANC":
        raise ValueError(f"C2.3 / B4.4: floors need pre-floor counts, which exist for MANC only (got {fly.name})")
    if fly.meta.get("control"):
        raise ValueError(f"C2.3: no pre-floor counts exist for the control network {fly.meta['control']}; PREREG v4 defines no "
                         "rewired floor-1 / floor-3 network, so fixes 3a / 3b are not applied to it")


def fix_floor(f: int, fly: MI.Fly | None = None) -> tuple[sp.csr_matrix, np.ndarray | None]:
    """C2.3 (fixes 3a: f = 1, 3b: f = 3) and B4.4 (floors 1, 3, 5, 10): W = at_floor(manc_raw_counts(), f) x sign; sizes unchanged.

    MANC only: raises for MaleCNS (no pre-floor counts), for the rewired control (none for it either) and for any fly whose counts
    are not B1r's floor-5 matrix. `fly` defaults to `mirror.fly("MANC")`; its sign is the one `manc_raw_counts` was checked against."""
    fly = MI.fly("MANC") if fly is None else fly
    _check_floor_fly(fly)
    if f < 1:
        raise ValueError(f"floor must be >= 1, got {f}")
    C1 = manc_raw_counts()
    if C1.shape != fly.C.shape or not _same(at_floor(C1, B1R_FLOOR), _canon(fly.C)):
        raise ValueError("fix_floor applies only to the real MANC front-leg network (its counts must equal B1r's floor-5 matrix)")
    return signed(at_floor(C1, f), fly.sign), _sizes_of(fly)


def fix_symmetrised(fly: MI.Fly, mm: MI.MirrorMap) -> tuple[sp.csr_matrix, np.ndarray | None]:
    """C2.4 (fix 4): for every pair of homologous entries (i, j), (m(i), m(j)) with i and j matched or self-mapped, both counts ->
    their mean (a connection present on one side becomes half its count on both; an entry between two self-mapped neurons is its
    own pair and stays); entries with an unmatched neuron unchanged; signs and sizes unchanged. `mm` = the fly's mirror map (for
    the rewired control: the REAL network's map, see `rewired_fly`)."""
    C, sign, sizes = _state(fly)
    return signed(_symmetrise(C, mm), sign), sizes


def fix_type_pooled(fly: MI.Fly, within_side: bool) -> tuple[sp.csr_matrix, np.ndarray | None]:
    """C2.5 (fix 5): each existing connection's count -> the mean count of the existing connections of its class. 5a
    (`within_side=True`): class = (presynaptic type, its side, postsynaptic type, its side), sides L / R / M / U; 5b
    (`within_side=False`): class = (presynaptic type, postsynaptic type, relation) with relation = same side / different sides /
    involves a neuron whose side is not L or R. Sides are `fly.side` (after G3). A neuron without a type is its own type. The set
    of connections (the pattern of C, including connections of sign-0 neurons) is unchanged; signs and sizes unchanged."""
    C, sign, sizes = _state(fly)
    return signed(_type_pool(C, fly.ntype, fly.side, within_side), sign), sizes


def fix_input_normalised(fly: MI.Fly) -> tuple[sp.csr_matrix, np.ndarray | None]:
    """C2.6 (fix 6) on W = C x sign: for each neuron i of type B, its incoming excitatory weight E_i (sum of the positive entries
    of row i) and inhibitory weight I_i (sum of |negative entries|) are scaled to the mean over B's members (all sides, members
    with zero included); E_i = 0 (I_i = 0) keeps it; neurons without a type unchanged; sizes unchanged."""
    C, sign, sizes = _state(fly)
    return _input_normalise(signed(C, sign), fly.ntype), sizes


def fix_consensus(fly: MI.Fly) -> tuple[sp.csr_matrix, np.ndarray | None]:
    """C2.7 (fix 7): each typed neuron's size -> its type's median size (NaN ignored; a type whose sizes are all NaN keeps them)
    and its sign -> its type's majority sign, i.e. the most frequent of +1 / -1 / 0 among the members when that is unique (a tie
    keeps each neuron's own); neurons without a type unchanged. W = C x the new sign (C includes sign-0 neurons' connections)."""
    C, sign, sizes = _state(fly)
    sign7, sizes7 = _consensus(sign, sizes, fly.ntype)
    return signed(C, sign7), sizes7


def fix_all(fly: MI.Fly, mm: MI.MirrorMap) -> tuple[sp.csr_matrix, np.ndarray | None]:
    """C2.8 (fix 8): the network-level fixes that apply to both flies, in this order, each on the previous result: 7 (consensus
    sizes and signs), 4 (symmetrised counts), 5b (type-pooled across sides, on the symmetrised connection set), 6 (input-normalised,
    on the signed matrix with the consensus signs). Floors are excluded (C2.8)."""
    C, sign, sizes = _state(fly)
    sign7, sizes7 = _consensus(sign, sizes, fly.ntype)                    # 7
    C4 = _symmetrise(C, mm)                                               # 4
    C5 = _type_pool(C4, fly.ntype, fly.side, within_side=False)           # 5b
    return _input_normalise(signed(C5, sign7), fly.ntype), sizes7         # 6


def apply_fix(name: str, fly: MI.Fly, mm: MI.MirrorMap) -> tuple[sp.csr_matrix, np.ndarray | None]:
    """C2: the network-level fix `name` on `fly` -> (W signed float64 CSR, sizes). '3a' floor 1, '3b' floor 3 (MANC only), '4'
    symmetrised, '5a' / '5b' type-pooled within / across sides, '6' input-normalised, '7' consensus, '8' all of 7, 4, 5b, 6.
    The C4 gain is applied afterwards with `gain`."""
    if name in FLOOR_OF_FIX:
        return fix_floor(FLOOR_OF_FIX[name], fly)
    if name == "4":
        return fix_symmetrised(fly, mm)
    if name == "5a":
        return fix_type_pooled(fly, within_side=True)
    if name == "5b":
        return fix_type_pooled(fly, within_side=False)
    if name == "6":
        return fix_input_normalised(fly)
    if name == "7":
        return fix_consensus(fly)
    if name == "8":
        return fix_all(fly, mm)
    raise ValueError(f"unknown fix {name!r}; the network-level fixes are {FIXES}")


def gain(W, g: float) -> sp.csr_matrix:
    """C4: every synaptic weight times g (canonical copy)."""
    out = _canon(W)
    out.data = out.data * float(g)
    out.eliminate_zeros()
    return out


# --------------------------------------------------------------------------------------------------- C5: rewired control
def rewired_fly(fly: MI.Fly) -> MI.Fly:
    """C5: the rewired control as a Fly: MANC rewired by run 1's degree-preserving generator with network seed 101
    (W_r = `controls.build(fly.net, "B1-ctl-rewire-101")[0]`, the network of B1-ctl-rewire-101), C = |W_r|, the same per-neuron
    sign (checked: every nonzero entry of W_r has its presynaptic neuron's sign), everything else (sides, types, groups, sizes,
    readout, `net`) unchanged; `meta["control"]` names the control.

    The fixes are applied to this object with the REAL network's mirror map (`mirror.mirror_map(fly)` of the real MANC fly): the
    map pairs neurons by annotation and the real wiring, which the rewiring scrambles by construction. C = |W_r| has no
    connections of sign-0 neurons (the generator rewires W, where they are absent), unlike the real fly's C. `net` still refers to
    the real network; the fixes never read `net.W` / `net.C`. Floor fixes (3a / 3b) raise for this object: there are no pre-floor
    counts of a rewired network."""
    if fly.name != "MANC" or fly.meta.get("control"):
        raise ValueError(f"the rewired control is built from the real MANC fly only (got {fly.name}, control={fly.meta.get('control')})")
    sign = np.array(fly.sign, dtype=np.float64)
    if not _same(_canon(fly.net.W), signed(fly.C, sign)):
        raise RuntimeError("the fly's network W is not C x sign: the rewiring would not start from this fly's network")
    W_r, stats = controls.build(fly.net, REWIRE_CONTROL)
    W_r = _canon(W_r)
    if W_r.shape != fly.C.shape:
        raise RuntimeError(f"rewired matrix has shape {W_r.shape}, the fly {fly.C.shape}")
    bad = np.sign(W_r.data) != sign[W_r.indices]
    if bad.any():
        raise RuntimeError(f"{int(bad.sum())} entries of {REWIRE_CONTROL} have a sign other than their presynaptic neuron's")
    C = W_r.copy()
    C.data = np.abs(C.data)
    meta = {**fly.meta, "control": REWIRE_CONTROL, "control_stats": dict(stats),
            "control_note": "C = |W_r|; fixes use the REAL network's mirror map; floors (3a/3b) undefined"}
    return dataclasses.replace(fly, C=_canon(C), sign=sign, meta=meta)
