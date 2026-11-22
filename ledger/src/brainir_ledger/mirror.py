"""Run 4 (PREREG v4 G3, G4, G8, Blocks 2-3): sides, the left-right mirror map, the mirror network, hybrids and paired draws.

Everything here is wiring and annotation only; nothing simulates. The mirror map m is an involution on an extended slot set
(real neurons, then one ghost slot per unmatched neuron), so the mirror network M[i, j] = W[m(i), m(j)] is an exact relabelling of W:
the left screen on M is the right screen on W (G4). Hybrids take chosen items (entries, sizes, signs, presence) from M and the rest
from W (B2.1, B3.1).
"""

from __future__ import annotations

import glob
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.optimize import linear_sum_assignment

from . import REPO
from . import networks as N

SIDES = ("L", "R")
OPP = {"L": "R", "R": "L"}
RELIABLE = 0.90  # G3: annotation reliable if it agrees with the output side for >= 90 % of DN members


# ------------------------------------------------------------------------------------------------------------------ flies
@dataclass
class Fly:
    name: str                      # "MANC" or "MaleCNS"
    net: object                    # LedgerNetwork
    groups: dict                   # whole-type groups (B1r / B2r): type -> member positions
    side_annot: np.ndarray         # G3 annotation side per neuron: L / R / M / U
    out_side: np.ndarray           # output side per neuron (DN members only; '' undefined, '-' not a DN member)
    side: np.ndarray               # side used (after the reliability rule)
    corrected: np.ndarray          # bool: DN member whose side was changed by the rule
    dropped: np.ndarray            # bool: DN member left out (corrected fly, undefined output side)
    reliability: dict              # agreement counts of G3
    gid: np.ndarray                # bilateral group id per neuron (object; None if missing)
    ntype: np.ndarray              # neuron type for matching (object; None if missing)
    sign: np.ndarray               # presynaptic sign per neuron (+1 / -1 / 0)
    C: sp.csr_matrix               # unsigned counts after the floor (post x pre)
    readout: np.ndarray            # front-leg motor neurons (bool)
    meta: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return int(self.C.shape[0])

    def halves(self) -> dict[str, dict[str, list[int]]]:
        """G4 / G9: per side, type -> that side's members (dropped members left out); only matched types (both sides)."""
        out = {"L": {}, "R": {}}
        for t, m in sorted(self.groups.items()):
            left = [i for i in m if self.side[i] == "L" and not self.dropped[i]]
            right = [i for i in m if self.side[i] == "R" and not self.dropped[i]]
            if left and right:
                out["L"][t], out["R"][t] = left, right
        return out

    def type_counts(self) -> dict:
        h = self.halves()
        lonly = rightonly = 0
        for t, m in self.groups.items():
            left = [i for i in m if self.side[i] == "L" and not self.dropped[i]]
            right = [i for i in m if self.side[i] == "R" and not self.dropped[i]]
            lonly += bool(left and not right)
            rightonly += bool(right and not left)
        equal = sum(1 for t in h["L"] if len(h["L"][t]) == len(h["R"][t]))
        return {"types": len(self.groups), "matched": len(h["L"]), "left_only": lonly, "right_only": rightonly,
                "equal_member_counts": equal, "one_member_each_side": sum(1 for t in h["L"] if len(h["L"][t]) == 1 == len(h["R"][t]))}

    def readout_side(self, s: str) -> np.ndarray:
        return self.readout & (self.side_annot == s)


def output_side(C: sp.csr_matrix, side: np.ndarray, idx) -> np.ndarray:
    """G3: for neurons `idx`, the side (L/R) holding the majority of their output counts onto neurons whose side is L or R;
    '' if they have no such output or exactly half."""
    Cc = C.tocsc()
    out = np.full(len(side), "-", dtype=object)
    isL, isR = side == "L", side == "R"
    for i in idx:
        lo, hi = Cc.indptr[i], Cc.indptr[i + 1]
        rows, vals = Cc.indices[lo:hi], Cc.data[lo:hi]
        cl, cr = float(vals[isL[rows]].sum()), float(vals[isR[rows]].sum())
        out[i] = "" if cl + cr == 0 or cl == cr else ("L" if cl > cr else "R")
    return out


def _apply_rule(name, side_annot, out_side, members) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    defined = [i for i in members if out_side[i] in SIDES]
    agree = sum(1 for i in defined if side_annot[i] == out_side[i])
    rel = {"fly": name, "dn_members": len(members), "output_side_defined": len(defined), "agree": agree,
           "share": agree / len(defined) if defined else float("nan")}
    rel["reliable"] = bool(defined and rel["share"] >= RELIABLE)
    side = side_annot.copy()
    corrected = np.zeros(len(side), bool)
    dropped = np.zeros(len(side), bool)
    if not rel["reliable"]:
        for i in members:
            if out_side[i] in SIDES:
                if out_side[i] != side_annot[i]:
                    corrected[i] = True
                side[i] = out_side[i]
            else:
                dropped[i] = True
    rel["corrected"] = int(corrected.sum())
    rel["dropped"] = int(dropped.sum())
    return side, corrected, dropped, rel


@lru_cache(maxsize=1)
def manc() -> Fly:
    fl = N.front_leg()
    t = fl.table
    root = N.full_cord().table.set_index("bodyId")["rootSide"]
    soma = t["somaSide"].map({"LHS": "L", "RHS": "R", "Midline": "M"})
    rs = t["bodyId"].map(root).map({"LHS": "L", "RHS": "R"})
    side_annot = soma.fillna(rs).fillna("U").to_numpy().astype(object)
    groups = N.type_groups(t)
    members = sorted({i for m in groups.values() for i in m})
    C = sp.csr_matrix(fl.C, dtype=np.float64)
    out = output_side(C, side_annot, members)
    side, corrected, dropped, rel = _apply_rule("MANC", side_annot, out, members)
    g3 = pd.read_parquet(REPO / "data" / "processed" / "manc" / "v1.2.3" / "neurons.parquet", columns=["source_id", "group_id"])
    gid = t["bodyId"].astype(np.int64).map(g3.set_index("source_id")["group_id"]).to_numpy().astype(object)
    gid = np.array([None if (x is None or (isinstance(x, float) and np.isnan(x))) else str(x) for x in gid], dtype=object)
    ntype = np.array([None if pd.isna(x) else str(x) for x in t["type"]], dtype=object)
    sign = _manc_sign(fl)
    return Fly("MANC", fl, groups, side_annot, out, side, corrected, dropped, rel, gid, ntype, sign, C, np.asarray(fl.readout, bool),
               {"network": fl.meta.get("network"), "group_source": "processed manc:v1.2.3 group_id by bodyId"})


def _manc_sign(fl) -> np.ndarray:
    """Presynaptic sign per neuron from the BrainIR network table (paper NT rule); checked against W = C x sign."""
    s = fl.btable["sign"].to_numpy().astype(np.float64)
    C = sp.csr_matrix(fl.C, dtype=np.float64)
    W = sp.csr_matrix(fl.W, dtype=np.float64)
    if abs(C.multiply(s[None, :]) - W).max() != 0:
        raise RuntimeError("MANC: W != C x presynaptic sign")
    return s


@lru_cache(maxsize=1)
def malecns() -> Fly:
    import pyarrow.feather as feather  # noqa: PLC0415

    from brainir import paths  # noqa: PLC0415

    from . import arms as AR  # noqa: PLC0415

    net, groups, _info = AR.malecns_network()
    t = net.table
    side_annot = t["somaSide"].map({"L": "L", "R": "R", "M": "M"}).fillna("U").to_numpy().astype(object)
    W = sp.csr_matrix(net.W, dtype=np.float64)
    C = abs(W).tocsr()
    sign = t["consensusNt"].map({"acetylcholine": 1.0, "gaba": -1.0, "glutamate": -1.0}).fillna(0.0).to_numpy()
    if abs(C.multiply(sign[None, :]) - W).max() != 0:
        raise RuntimeError("MaleCNS: W != |W| x consensus sign")
    members = sorted({i for m in groups.values() for i in m})
    out = output_side(C, side_annot, members)
    side, corrected, dropped, rel = _apply_rule("MaleCNS", side_annot, out, members)
    ann = feather.read_table(glob.glob(str(paths.data_root() / "raw" / "external" / "malecns_v1.0_body_annotations" / "*.feather"))[0]
                             ).to_pandas().set_index("bodyId")
    b = t["bodyId"].astype(np.int64).to_numpy()
    gid = np.array([None if pd.isna(x) else str(x) for x in ann["group"].reindex(b).to_numpy()], dtype=object)
    ntype = np.array([None if pd.isna(x) else str(x) for x in t["type"]], dtype=object)
    return Fly("MaleCNS", net, groups, side_annot, out, side, corrected, dropped, rel, gid, ntype, sign, C, np.asarray(net.readout, bool),
               {"network": net.meta.get("network"), "group_source": "MaleCNS body annotations `group`",
                "C_note": "MaleCNS counts = |W| (the authors' matrix is signed; transmitter-0 connections are absent)"})


def fly(name: str) -> Fly:
    return {"MANC": manc, "MaleCNS": malecns}[name]()


# ------------------------------------------------------------------------------------------------------------- mirror map
@dataclass
class MirrorMap:
    n_real: int
    m: np.ndarray            # involution on the extended slots (n_real + n_ghost)
    status: np.ndarray       # per slot: g1 / g2 / t / unmatched / self / ghost
    side: np.ndarray         # per slot: L / R / M / U (ghost: opposite of its partner)
    ghost_of: np.ndarray     # per slot: the real neuron a ghost stands for (-1 for real slots)
    counts: dict

    @property
    def n_ext(self) -> int:
        return int(len(self.m))

    def unmatched_or_ghost(self) -> np.ndarray:
        return np.isin(self.status, ("unmatched", "ghost"))

    def real_of(self) -> np.ndarray:
        """For each slot, the real neuron whose properties it carries in W (itself, or a ghost's partner)."""
        return np.where(self.ghost_of >= 0, self.ghost_of, np.arange(self.n_ext))


def _profiles(C: sp.csr_matrix, pairs: np.ndarray, side: np.ndarray) -> sp.csr_matrix:
    """Per neuron x: counts to / from the partners of the step-1 pairs, ordered (ipsi, contra) relative to x's own side:
    [out to ipsi member, out to contra member, in from ipsi member, in from contra member] per pair."""
    n = C.shape[0]
    Cc, Cr = C.tocsc(), C.tocsr()
    left = np.array([a if side[a] == "L" else b for a, b in pairs], dtype=np.int64)
    right = np.array([b if side[a] == "L" else a for a, b in pairs], dtype=np.int64)
    outL, outR = Cr[left, :].T.tocsr(), Cr[right, :].T.tocsr()     # n x P: counts x -> left member / right member
    inL, inR = Cc[:, left].tocsr(), Cc[:, right].tocsr()           # n x P: counts left member -> x / right member -> x
    isR = sp.diags((side == "R").astype(float))
    isNR = sp.diags((side != "R").astype(float))
    # for a right-side neuron, "ipsi" is the right member
    out_ipsi = isNR @ outL + isR @ outR
    out_con = isNR @ outR + isR @ outL
    in_ipsi = isNR @ inL + isR @ inR
    in_con = isNR @ inR + isR @ inL
    P = sp.hstack([out_ipsi, out_con, in_ipsi, in_con]).tocsr()
    norms = np.sqrt(np.asarray(P.multiply(P).sum(axis=1)).ravel())
    norms[norms == 0] = 1.0
    return sp.diags(1.0 / norms) @ P


def _hungarian(prof: sp.csr_matrix, left: list[int], right: list[int]) -> list[tuple[int, int]]:
    if not left or not right:
        return []
    S = (prof[left] @ prof[right].T).toarray()
    r, c = linear_sum_assignment(S, maximize=True)
    return [(left[a], right[b]) for a, b in zip(r, c)]


def mirror_map(f: Fly) -> MirrorMap:
    """G4: steps 1 (1:1 annotated groups), 2 (Hungarian within groups), 3 (Hungarian within type), 4 (unmatched -> ghost)."""
    n = f.n
    side = np.array([s if s in ("L", "R", "M") else "U" for s in f.side], dtype=object)
    m = np.arange(n)
    status = np.array(["self" if side[i] not in SIDES else "" for i in range(n)], dtype=object)
    sided = [i for i in range(n) if side[i] in SIDES]
    # step 1
    by_g: dict[str, list[int]] = {}
    for i in sided:
        if f.gid[i] is not None:
            by_g.setdefault(f.gid[i], []).append(i)
    pairs1 = []
    for g, mem in sorted(by_g.items()):
        L = [i for i in mem if side[i] == "L"]
        R = [i for i in mem if side[i] == "R"]
        if len(L) == 1 and len(R) == 1:
            pairs1.append((L[0], R[0]))
    for a, b in pairs1:
        m[a], m[b] = b, a
        status[a] = status[b] = "g1"
    prof = _profiles(f.C, np.array(pairs1, dtype=np.int64).reshape(-1, 2), side)
    # step 2
    for g, mem in sorted(by_g.items()):
        L = [i for i in mem if side[i] == "L" and status[i] == ""]
        R = [i for i in mem if side[i] == "R" and status[i] == ""]
        for a, b in _hungarian(prof, L, R):
            m[a], m[b] = b, a
            status[a] = status[b] = "g2"
    # step 3
    by_t: dict[str, list[int]] = {}
    for i in sided:
        if status[i] == "" and f.ntype[i] is not None:
            by_t.setdefault(f.ntype[i], []).append(i)
    for t, mem in sorted(by_t.items()):
        L = [i for i in mem if side[i] == "L"]
        R = [i for i in mem if side[i] == "R"]
        for a, b in _hungarian(prof, L, R):
            m[a], m[b] = b, a
            status[a] = status[b] = "t"
    # step 4: ghosts
    um = [i for i in sided if status[i] == ""]
    n_ext = n + len(um)
    m_ext = np.concatenate([m, np.zeros(len(um), dtype=np.int64)])
    status_ext = np.concatenate([status, np.array(["ghost"] * len(um), dtype=object)])
    side_ext = np.concatenate([side, np.array([OPP[side[i]] for i in um], dtype=object)])
    ghost_of = np.full(n_ext, -1, dtype=np.int64)
    for k, i in enumerate(um):
        g = n + k
        m_ext[i], m_ext[g] = g, i
        status_ext[i] = "unmatched"
        ghost_of[g] = i
    assert np.array_equal(m_ext[m_ext], np.arange(n_ext)), "mirror map is not an involution"
    for i in range(n_ext):
        if status_ext[i] in ("g1", "g2", "t"):
            assert side_ext[m_ext[i]] == OPP[side_ext[i]]
    counts = {"neurons": n, "sided": len(sided), "self_mapped": int((status == "self").sum()),
              "pairs_step1_group_1to1": int(sum(1 for i in range(n) if status_ext[i] == "g1") // 2),
              "pairs_step2_group_hungarian": int(sum(1 for i in range(n) if status_ext[i] == "g2") // 2),
              "pairs_step3_type_hungarian": int(sum(1 for i in range(n) if status_ext[i] == "t") // 2),
              "unmatched_left": int(sum(1 for i in um if side[i] == "L")), "unmatched_right": int(sum(1 for i in um if side[i] == "R")),
              "ghost_slots": len(um)}
    return MirrorMap(n, m_ext, status_ext, side_ext, ghost_of, counts)


# ------------------------------------------------------------------------------------------------- extended and mirror nets
@dataclass
class Ext:
    """A network on the extended slot set: unsigned counts, presynaptic signs, sizes, presence."""
    C: sp.csr_matrix
    sign: np.ndarray
    sizes: np.ndarray
    present: np.ndarray

    def W(self) -> sp.csr_matrix:
        W = self.C.multiply(self.sign[None, :]).tocsr()
        W.eliminate_zeros()
        return W


def extend(C: sp.csr_matrix, sign: np.ndarray, sizes, mm: MirrorMap) -> Ext:
    """W on the extended slots: real neurons first, ghost slots isolated and absent (their size and sign are their partner's)."""
    n, ne = mm.n_real, mm.n_ext
    C = sp.csr_matrix(C, dtype=np.float64)
    if ne == n:
        Ce = C.copy()
    else:
        Ce = sp.csr_matrix(sp.bmat([[C, None], [None, sp.csr_matrix((ne - n, ne - n))]]), dtype=np.float64)
    Ce.sort_indices()
    real = mm.real_of()
    sz = np.full(n, np.nan) if sizes is None else np.asarray(sizes, dtype=np.float64)
    return Ext(Ce, np.asarray(sign, np.float64)[real], sz[real], np.arange(ne) < n)


def mirror(e: Ext, mm: MirrorMap) -> Ext:
    """M = P W P^T on the extended slots (an exact relabelling)."""
    m = mm.m
    Cm = e.C[m][:, m].tocsr()
    Cm.sort_indices()
    return Ext(Cm, e.sign[m], e.sizes[m], e.present[m])


def entry_classes(e: Ext, em: Ext, mm: MirrorMap) -> tuple[sp.coo_matrix, np.ndarray, np.ndarray, np.ndarray]:
    """B3.1: over the union of the nonzero patterns of W and M: (pattern, a = W count, b = M count, class 1/2/3 or 0)."""
    A = e.C.tocoo()
    U = (abs(e.C) + abs(em.C)).tocoo()  # union pattern (counts are >= 0)
    rows, cols = U.row, U.col
    a = np.asarray(e.C[rows, cols]).ravel()
    b = np.asarray(em.C[rows, cols]).ravel()
    ug = mm.unmatched_or_ghost()
    cls = np.zeros(len(rows), dtype=np.int8)
    third = ug[rows] | ug[cols]
    both = (a > 0) & (b > 0)
    one = (a > 0) ^ (b > 0)
    cls[~third & both] = 1
    cls[~third & one] = 2
    cls[third & ((a > 0) | (b > 0))] = 3
    del A
    return U, a, b, cls


def hybrid(e: Ext, em: Ext, mm: MirrorMap, classes: set[int], *, cache=None) -> Ext:
    """B3.1: items of the chosen classes from M (em), the rest from W (e)."""
    U, a, b, cls = cache if cache is not None else entry_classes(e, em, mm)
    take = np.isin(cls, list(classes)) if classes else np.zeros(len(cls), bool)
    val = np.where(take, b, a)
    ne = mm.n_ext
    C = sp.csr_matrix((val, (U.row, U.col)), shape=(ne, ne))
    C.eliminate_zeros()
    C.sort_indices()
    ug = mm.unmatched_or_ghost()
    matched = ~ug  # includes self-mapped
    sel_sign = (matched & (5 in classes)) | (ug & (3 in classes))
    sel_size = (matched & (4 in classes)) | (ug & (3 in classes))
    sel_pres = ug & (3 in classes)
    return Ext(C, np.where(sel_sign, em.sign, e.sign), np.where(sel_size, em.sizes, e.sizes), np.where(sel_pres, em.present, e.present))


def columns_from(base: Ext, other: Ext, cols) -> Ext:
    """B2.1: `base` with the columns `cols` (output connections), and those slots' sign, size and presence, taken from `other`."""
    cols = np.asarray(sorted(set(int(c) for c in cols)), dtype=np.int64)
    ne = base.C.shape[0]
    keep = np.ones(ne, bool)
    keep[cols] = False
    Bc, Oc = base.C.tocsc(), other.C.tocsc()
    D_keep = sp.diags(keep.astype(float))
    D_take = sp.diags((~keep).astype(float))
    C = (Bc @ D_keep + Oc @ D_take).tocsr()
    C.eliminate_zeros()
    C.sort_indices()
    sign, sizes, pres = base.sign.copy(), base.sizes.copy(), base.present.copy()
    sign[cols], sizes[cols], pres[cols] = other.sign[cols], other.sizes[cols], other.present[cols]
    return Ext(C, sign, sizes, pres)


def left_slots(mm: MirrorMap, members_left: list[int], members_right: list[int]) -> list[int]:
    """B2.1: the left slots of a type: its real left members plus the ghost slots of its unmatched right members."""
    ghosts = [int(mm.m[j]) for j in members_right if mm.status[j] == "unmatched"]
    return sorted(set(int(i) for i in members_left) | set(ghosts))


def stimulated(slots: list[int], present: np.ndarray) -> list[int]:
    """Only present slots are stimulated (G4)."""
    return [int(i) for i in slots if present[i]]


# ------------------------------------------------------------------------------------------------------------ paired draws
def paired_source(mm: MirrorMap) -> np.ndarray:
    """G8: for each extended slot, the real neuron whose raw draws it uses: matched pairs share the lower-indexed member's draws,
    ghosts take their partner's, everything else its own."""
    n = mm.n_real
    src = np.arange(mm.n_ext)
    for i in range(mm.n_ext):
        if mm.status[i] in ("g1", "g2", "t"):
            src[i] = min(i, int(mm.m[i]))
        elif mm.status[i] == "ghost":
            src[i] = int(mm.ghost_of[i])
    assert (src < n).all()
    return src


def paired_params(model_cfg, seed: int, n_real: int, sizes_real, src: np.ndarray, sizes_slots):
    """G8: raw draws exactly as `sample_neuron_params(cfg, n_real, seed, sizes)` draws them (one stream: tau, a, theta, r_max),
    shared per `src`, then size-scaled per slot relative to the real network's median (NaN or 0 -> scale 1)."""
    from brainir.sim.model import NeuronParams, sample_trunc_normal  # noqa: PLC0415

    rng = np.random.default_rng(int(seed))
    tau = sample_trunc_normal(rng, model_cfg.tau_mean, model_cfg.tau_sd, (n_real,))
    a = sample_trunc_normal(rng, model_cfg.a_mean, model_cfg.a_sd, (n_real,))
    theta = sample_trunc_normal(rng, model_cfg.theta_mean, model_cfg.theta_sd, (n_real,))
    r_max = sample_trunc_normal(rng, model_cfg.r_max_mean, model_cfg.r_max_sd, (n_real,))
    src = np.asarray(src, dtype=np.int64)
    if model_cfg.size_scaling and sizes_real is not None:
        sr = np.asarray(sizes_real, dtype=np.float64)
        med = np.nanmedian(sr) if np.isfinite(sr).any() else 1.0
        s = np.asarray(sizes_slots, dtype=np.float64).copy()
        s[~np.isfinite(s)] = med
        s[s == 0] = med
        s = s / med
    else:
        s = np.ones(len(src))
    p = NeuronParams(tau=tau[src], a=a[src] / s, theta=theta[src] * s, r_max=r_max[src], seed=int(seed), size_scale=s)
    p.validate()
    return p


def permute(e: Ext, perm: np.ndarray) -> Ext:
    """B2.4: relabel slot k as perm[k] (W_Q[perm[i], perm[j]] = W[i, j])."""
    inv = np.argsort(perm)
    C = e.C[inv][:, inv].tocsr()
    C.sort_indices()
    return Ext(C, e.sign[inv], e.sizes[inv], e.present[inv])
