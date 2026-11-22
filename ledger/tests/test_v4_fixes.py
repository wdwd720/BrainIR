"""PREREG v4 B4, C2, C4, C5 (`brainir_ledger.fixes`): tiny synthetic networks with hand-computed answers, plus one real-data wiring
check (floor 5 of the MANC floor-1 counts reproduces B1r's matrix).

Nothing here simulates. The real-data test compares no left and right weights and computes no dispersion (PREREG v4 Part Q).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import scipy.sparse as sp

from brainir_ledger import controls
from brainir_ledger import fixes as F
from brainir_ledger import mirror as MI
from brainir_ledger import networks as N  # also puts the benchmark directory on sys.path (`_real_data_ready`)

NAN = float("nan")


# ----------------------------------------------------------------------------------------------------------------- helpers
def make_fly(n, entries, *, sign, ntype=None, side=None, gid=None, sizes=None, name="MANC", with_w=False, meta=None):
    """A tiny Fly; `entries` = (post, pre, count) triples (C is post x pre). `net` carries only `sizes` (and `W` if asked), so any
    fix that touched `net.W` / `net.C` would fail here."""
    rows = np.array([e[0] for e in entries], dtype=np.int64)
    cols = np.array([e[1] for e in entries], dtype=np.int64)
    vals = np.array([e[2] for e in entries], dtype=np.float64)
    C = sp.csr_matrix((vals, (rows, cols)), shape=(n, n))
    side = np.array(side if side is not None else ["L"] * n, dtype=object)
    sign = np.array(sign, dtype=np.float64)
    net = SimpleNamespace(sizes=None if sizes is None else np.array(sizes, dtype=np.float64))
    if with_w:
        net.W = C.multiply(sign[None, :]).tocsr()
    return MI.Fly(name=name, net=net, groups={}, side_annot=side.copy(), out_side=np.full(n, "-", dtype=object), side=side,
                  corrected=np.zeros(n, bool), dropped=np.zeros(n, bool), reliability={},
                  gid=np.array(gid if gid is not None else [None] * n, dtype=object),
                  ntype=np.array(ntype if ntype is not None else [None] * n, dtype=object), sign=sign, C=C,
                  readout=np.zeros(n, bool), meta=dict(meta or {}))


def dense(entries, n):
    D = np.zeros((n, n))
    for i, j, v in entries:
        D[i, j] = v
    return D


def snapshot(fly):
    z = fly.net.sizes
    return (fly.C.data.copy(), fly.C.indices.copy(), fly.C.indptr.copy(), fly.sign.copy(), None if z is None else z.copy())


def assert_unchanged(fly, snap):
    d, ind, ptr, s, z = snap
    assert np.array_equal(fly.C.data, d) and np.array_equal(fly.C.indices, ind) and np.array_equal(fly.C.indptr, ptr)
    assert np.array_equal(fly.sign, s)
    assert (fly.net.sizes is None) if z is None else np.array_equal(fly.net.sizes, z, equal_nan=True)


def assert_canonical(M):
    assert isinstance(M, sp.csr_matrix) and M.dtype == np.float64
    assert F._same(M, F._canon(M)), "not canonical (sorted, summed, no explicit zeros)"
    assert (M.data != 0).all()


# --------------------------------------------------------------------------------------------------------- fix 4 (C2.4)
def sym_fly():
    """0 L / 1 R (group a), 2 L / 3 R (group b), 4 midline (self-mapped), 5 left with no partner (unmatched)."""
    entries = [(2, 0, 4), (3, 1, 2),      # both sides present -> 3, 3
               (0, 2, 6),                 # mirror (1, 3) absent -> 3 on both
               (1, 0, 10),                # contralateral L->R; mirror (0, 1) absent -> 5 on both
               (4, 0, 8),                 # onto the self-mapped neuron; mirror (4, 1) absent -> 4 on both
               (0, 4, 2), (1, 4, 6),      # from the self-mapped neuron -> 4, 4
               (5, 0, 7), (2, 5, 9)]      # an unmatched neuron's entries: unchanged
    return make_fly(6, entries, sign=[1, -1, 1, 1, -1, 1], ntype=["A", "A", "B", "B", "MID", "X"],
                    side=["L", "R", "L", "R", "M", "L"], gid=["a", "a", "b", "b", None, None], sizes=[1, 2, 3, 4, 5, 6])


def test_symmetrised_averages_homologous_entries_and_leaves_unmatched_alone():
    fly = sym_fly()
    mm = MI.mirror_map(fly)
    assert list(mm.status[:6]) == ["g1", "g1", "g1", "g1", "self", "unmatched"]
    snap = snapshot(fly)
    W, sizes = F.fix_symmetrised(fly, mm)
    want_c = dense([(2, 0, 3), (3, 1, 3), (0, 2, 3), (1, 3, 3), (1, 0, 5), (0, 1, 5), (4, 0, 4), (4, 1, 4), (0, 4, 4), (1, 4, 4),
                    (5, 0, 7), (2, 5, 9)], 6)
    np.testing.assert_array_equal(W.toarray(), want_c * fly.sign[None, :])  # signs unchanged: column j times sign[j]
    assert W[3, 5] == 0 and W[5, 1] == 0  # nothing mirrored onto the unmatched neuron's (ghost) partner
    np.testing.assert_array_equal(sizes, [1, 2, 3, 4, 5, 6])
    assert sizes is not fly.net.sizes
    assert_canonical(W)
    assert not np.shares_memory(W.data, fly.C.data)
    assert_unchanged(fly, snap)


def test_symmetrised_entry_between_self_mapped_neurons_is_its_own_pair():
    fly = make_fly(3, [(1, 0, 5), (2, 0, 4)], sign=[1, 1, 1], side=["M", "U", "L"], ntype=["P", "Q", "Z"], sizes=[1, 1, 1])
    mm = MI.mirror_map(fly)
    assert list(mm.status[:3]) == ["self", "self", "unmatched"]
    W, _ = F.fix_symmetrised(fly, mm)
    np.testing.assert_array_equal(W.toarray(), fly.C.toarray())


# --------------------------------------------------------------------------------------------------------- fix 5 (C2.5)
def pool_fly():
    """Types A (0 L, 1 R, 5 L) and B (2 L, 3 R, 4 midline); 6 and 7 untyped (left)."""
    entries = [(2, 0, 2), (2, 5, 4),      # A_L -> B_L
               (3, 1, 6),                 # A_R -> B_R
               (3, 0, 8),                 # A_L -> B_R
               (2, 1, 10),                # A_R -> B_L
               (4, 0, 12), (4, 1, 3),     # A -> B midline (unsided relation)
               (2, 6, 1), (2, 7, 5),      # two untyped neurons -> B_L: each its own type, never pooled together
               (7, 6, 2), (6, 7, 4)]
    return make_fly(8, entries, sign=[1, -1, 1, 1, 1, 1, 1, 1], ntype=["A", "A", "B", "B", "B", "A", None, None],
                    side=["L", "R", "L", "R", "M", "L", "L", "L"], sizes=np.arange(8.0))


def test_type_pooled_within_side_vs_across_sides():
    fly = pool_fly()
    snap = snapshot(fly)
    W5a, s5a = F.fix_type_pooled(fly, within_side=True)
    W5b, s5b = F.fix_type_pooled(fly, within_side=False)
    want_5a = dense([(2, 0, 3), (2, 5, 3), (3, 1, 6), (3, 0, 8), (2, 1, 10), (4, 0, 12), (4, 1, 3), (2, 6, 1), (2, 7, 5), (7, 6, 2),
                     (6, 7, 4)], 8)
    want_5b = dense([(2, 0, 4), (2, 5, 4), (3, 1, 4),            # (A, B, same side): mean of 2, 4, 6
                     (3, 0, 9), (2, 1, 9),                       # (A, B, different sides): mean of 8, 10
                     (4, 0, 7.5), (4, 1, 7.5),                   # (A, B, involves an unsided neuron): mean of 12, 3
                     (2, 6, 1), (2, 7, 5), (7, 6, 2), (6, 7, 4)], 8)
    np.testing.assert_array_equal(W5a.toarray(), want_5a * fly.sign[None, :])
    np.testing.assert_array_equal(W5b.toarray(), want_5b * fly.sign[None, :])
    for W in (W5a, W5b):  # the set of connections is unchanged
        np.testing.assert_array_equal(W.toarray() != 0, fly.C.toarray() != 0)
        assert_canonical(W)
    np.testing.assert_array_equal(s5a, np.arange(8.0))
    np.testing.assert_array_equal(s5b, np.arange(8.0))
    assert_unchanged(fly, snap)


# --------------------------------------------------------------------------------------------------------- fix 6 (C2.6)
def test_input_normalised_scales_e_and_i_to_the_type_mean():
    # types: B = 0, 1, 2; E = 3, 6 (excitatory); I = 4 (inhibitory, no input); 5 untyped
    entries = [(0, 3, 2), (0, 6, 2), (0, 4, 1),   # E_0 = 4, I_0 = 1
               (1, 3, 8), (1, 4, 3),              # E_1 = 8, I_1 = 3
               (2, 4, 2),                         # E_2 = 0 (keeps 0), I_2 = 2
               (3, 4, 5),                         # type E: E_3 = 0, I_3 = 5
               (6, 3, 4),                         # type E: E_6 = 4, I_6 = 0
               (5, 3, 7)]                         # untyped: unchanged
    fly = make_fly(7, entries, sign=[1, 1, 1, 1, -1, 1, 1], ntype=["B", "B", "B", "E", "I", None, "E"], sizes=np.ones(7))
    snap = snapshot(fly)
    W, sizes = F.fix_input_normalised(fly)
    # B: target_E = (4 + 8 + 0) / 3 = 4, target_I = (1 + 3 + 2) / 3 = 2; E: target_E = (0 + 4) / 2 = 2, target_I = (5 + 0) / 2 = 2.5
    want = dense([(0, 3, 2), (0, 6, 2), (0, 4, -2), (1, 3, 4), (1, 4, -2), (2, 4, -2), (3, 4, -2.5), (6, 3, 2), (5, 3, 7)], 7)
    np.testing.assert_allclose(W.toarray(), want, rtol=1e-12, atol=0)
    D = W.toarray()
    e, i = np.where(D > 0, D, 0).sum(axis=1), -np.where(D < 0, D, 0).sum(axis=1)
    np.testing.assert_allclose(e[[0, 1]], [4, 4], rtol=1e-12)        # members with input now carry the type mean
    np.testing.assert_allclose(i[[0, 1, 2]], [2, 2, 2], rtol=1e-12)
    assert e[2] == 0 and e[3] == 0 and i[6] == 0                       # zero input stays zero
    assert not D[4].any()                                              # a neuron with no input at all is unchanged
    np.testing.assert_array_equal(sizes, np.ones(7))
    assert_canonical(W)
    assert_unchanged(fly, snap)


# --------------------------------------------------------------------------------------------------------- fix 7 (C2.7)
def test_consensus_sizes_and_signs_with_ties():
    ntype = ["A"] * 3 + ["B"] * 2 + ["C"] * 3 + ["D"] * 3 + [None] + ["G"] * 3
    sign = [1, 1, -1,  1, -1,  0, 0, 1,  1, -1, 0,  -1,  0, 1, 1]
    sizes = [10, NAN, 30,  NAN, NAN,  1, 2, 4,  5, 7, NAN,  3,  1, 1, NAN]
    entries = [(11, 2, 5),    # 2: -1 -> +1 (A's majority)
               (11, 3, 2), (11, 4, 2),   # B: tie +1 / -1 -> each keeps its own
               (11, 7, 3),    # 7: +1 -> 0 (C's majority is 0) -> vanishes from W
               (0, 11, 4),    # untyped: unchanged
               (0, 5, 6),     # sign 0 stays 0
               (0, 12, 3)]    # 12: 0 -> +1 (G's majority): its counts (kept in C) appear in W
    fly = make_fly(15, entries, sign=sign, ntype=ntype, sizes=sizes)
    snap = snapshot(fly)
    W, new_sizes = F.fix_consensus(fly)
    np.testing.assert_array_equal(new_sizes, [20, 20, 20, NAN, NAN, 2, 2, 2, 6, 6, 6, 3, 1, 1, 1])
    want_sign = np.array([1, 1, 1, 1, -1, 0, 0, 0, 1, -1, 0, -1, 1, 1, 1], dtype=float)  # D: three-way tie keeps own
    np.testing.assert_array_equal(W.toarray(), fly.C.toarray() * want_sign[None, :])
    assert W[11, 2] == 5 and W[11, 3] == 2 and W[11, 4] == -2 and W[11, 7] == 0 and W[0, 11] == -4 and W[0, 5] == 0 and W[0, 12] == 3
    assert_canonical(W)
    assert_unchanged(fly, snap)


# ---------------------------------------------------------------------------------------------------- fix 8 (C2.8): order
def all_fly():
    """A: 0 L / 1 R (group a) and 4 L (unmatched); B: 2 L / 3 R (group b)."""
    entries = [(2, 0, 4), (3, 1, 2), (3, 0, 6), (2, 4, 8), (0, 2, 5), (1, 3, 1), (3, 4, 9)]
    return make_fly(5, entries, sign=[1, -1, -1, -1, 1], ntype=["A", "A", "B", "B", "A"], side=["L", "R", "L", "R", "L"],
                    gid=["a", "a", "b", "b", None], sizes=[10, 20, 5, NAN, 60])


def test_fix_all_applies_7_4_5b_6_in_that_order():
    fly = all_fly()
    mm = MI.mirror_map(fly)
    assert list(mm.status[:5]) == ["g1", "g1", "g1", "g1", "unmatched"]
    snap = snapshot(fly)
    W, sizes = F.fix_all(fly, mm)
    # by hand: 7 -> signs A +1 (2 of 3), B -1; sizes A 20, B 5.
    # 4 -> (2,0)=(3,1)=3, (3,0)=(2,1)=3, (0,2)=(1,3)=3, unmatched 4's (2,4)=8 and (3,4)=9 kept.
    # 5b -> (A,B,same) {3,3,8} -> 14/3; (A,B,diff) {3,3,9} -> 5; (B,A,same) {3,3} -> 3.
    # 6 -> A rows: I = 3, 3, 0 -> target 2; B rows: E_2 = 43/3, E_3 = 44/3 -> target 14.5 (row 2 x 87/86, row 3 x 87/88).
    want = dense([(0, 2, -2), (1, 3, -2), (2, 0, 203 / 43), (2, 1, 435 / 86), (2, 4, 203 / 43), (3, 0, 435 / 88), (3, 1, 203 / 44),
                  (3, 4, 435 / 88)], 5)
    np.testing.assert_allclose(W.toarray(), want, rtol=1e-12, atol=0)
    assert W[2, 0] == pytest.approx(14 / 3 * 14.5 / (43 / 3), rel=1e-14)  # one entry by hand, step by step
    np.testing.assert_array_equal(sizes, [20, 20, 5, 5, 20])
    assert_canonical(W)
    assert_unchanged(fly, snap)
    np.testing.assert_array_equal(F.apply_fix("8", fly, mm)[0].toarray(), W.toarray())
    # the example is sensitive to the order: other orders give other networks
    C, nt, side, s0 = fly.C, fly.ntype, fly.side, fly.sign
    s7, _ = F._consensus(s0, fly.net.sizes, nt)
    swap_4_5b = F._input_normalise(F.signed(F._symmetrise(F._type_pool(C, nt, side, False), mm), s7), nt)
    norm_before_consensus = F.signed(abs(F._input_normalise(F.signed(F._type_pool(F._symmetrise(C, mm), nt, side, False), s0), nt)), s7)
    norm_before_pool = F.signed(F._type_pool(abs(F._input_normalise(F.signed(F._symmetrise(C, mm), s7), nt)), nt, side, False), s7)
    for alt in (swap_4_5b, norm_before_consensus, norm_before_pool):
        assert not np.allclose(alt.toarray(), want, rtol=1e-9, atol=0)


def test_apply_fix_dispatch_and_unknown_name():
    fly = all_fly()
    mm = MI.mirror_map(fly)
    pairs = {"4": F.fix_symmetrised(fly, mm), "5a": F.fix_type_pooled(fly, True), "5b": F.fix_type_pooled(fly, False),
             "6": F.fix_input_normalised(fly), "7": F.fix_consensus(fly), "8": F.fix_all(fly, mm)}
    for name, (W, s) in pairs.items():
        W2, s2 = F.apply_fix(name, fly, mm)
        assert F._same(W2, W) and np.array_equal(s2, s, equal_nan=True), name
    with pytest.raises(ValueError, match="unknown fix"):
        F.apply_fix("9", fly, mm)


def test_fixes_never_modify_the_fly_and_return_canonical_copies():
    fly = all_fly()
    mm = MI.mirror_map(fly)
    snap = snapshot(fly)
    for name in ("4", "5a", "5b", "6", "7", "8"):
        W, sizes = F.apply_fix(name, fly, mm)
        assert_canonical(W)
        assert not np.shares_memory(W.data, fly.C.data) and not np.shares_memory(sizes, fly.net.sizes)
        assert_unchanged(fly, snap)


def test_mirror_map_of_another_size_is_refused():
    fly = all_fly()
    with pytest.raises(ValueError, match="mirror map"):
        F.fix_symmetrised(fly, MI.mirror_map(sym_fly()))


# ----------------------------------------------------------------------------------------------------- floors (C2.3, B4.4)
def test_floor_fixes_refuse_malecns_and_controls():
    male = make_fly(3, [(1, 0, 5)], sign=[1, 1, 1], name="MaleCNS", sizes=[1, 1, 1])
    mm = MI.mirror_map(male)
    with pytest.raises(ValueError, match="MANC only"):
        F.fix_floor(1, male)
    for name in ("3a", "3b"):
        with pytest.raises(ValueError, match="MANC only"):
            F.apply_fix(name, male, mm)
    ctl = make_fly(3, [(1, 0, 5)], sign=[1, 1, 1], sizes=[1, 1, 1], meta={"control": F.REWIRE_CONTROL})
    with pytest.raises(ValueError, match="no pre-floor counts"):
        F.apply_fix("3a", ctl, mm)


# --------------------------------------------------------------------------------------------------------------- gain (C4)
def test_gain_multiplies_every_weight():
    W = sp.csr_matrix(np.array([[0.0, 2.0], [-3.0, 0.0]]))
    keep = W.data.copy()
    np.testing.assert_array_equal(F.gain(W, 1.5).toarray(), [[0, 3], [-4.5, 0]])
    assert F._same(F.gain(W, 1), F._canon(W))
    assert_canonical(F.gain(W, 0.5))
    assert np.array_equal(W.data, keep) and not np.shares_memory(F.gain(W, 2).data, W.data)


# ----------------------------------------------------------------------------------------------------------- B4: counts
def test_at_floor_keeps_entries_at_or_above_the_floor():
    rows, cols, vals = [0, 0, 1, 2, 0, 1], [1, 1, 0, 0, 2, 2], [1.0, 2.0, 3.0, 5.0, 10.0, 4.0]  # (0, 1) given twice: 1 + 2 = 3
    C1 = sp.coo_matrix((vals, (rows, cols)), shape=(3, 3))
    want = {1: [(0, 1, 3), (1, 0, 3), (2, 0, 5), (0, 2, 10), (1, 2, 4)], 4: [(2, 0, 5), (0, 2, 10), (1, 2, 4)], 5: [(2, 0, 5), (0, 2, 10)],
            11: []}
    for f, entries in want.items():
        out = F.at_floor(C1, f)
        np.testing.assert_array_equal(out.toarray(), dense(entries, 3))
        assert isinstance(out, sp.csr_matrix) and (out.data >= f).all() and (out.data != 0).all()
    assert np.array_equal(C1.data, vals)


def big_counts(value, seed=0, n=150, density=0.6):
    rng = np.random.default_rng(seed)
    mask = rng.random((n, n)) < density
    return sp.csr_matrix(np.where(mask, float(value), 0.0))


def test_poisson_copy_is_deterministic_canonical_and_has_mean_c():
    C1 = big_counts(1000)
    keep = C1.data.copy()
    a, b, c = F.poisson_copy(C1, 20261411), F.poisson_copy(C1, 20261411), F.poisson_copy(C1, 20261412)
    assert F._same(a, b) and not F._same(a, c)
    assert np.array_equal(C1.data, keep)
    assert_canonical(a)
    assert np.array_equal(a.data, np.round(a.data))
    assert abs(a.data.mean() - 1000) < 1.0  # 13,500 draws: standard error 0.27
    assert abs(a.data.var() / 1000 - 1) < 0.05
    # the draws follow the canonical order, whatever order, duplicates or explicit zeros the input carries:
    # (1) shuffled COO with the last entry split into two duplicates and an explicit zero
    coo = C1.tocoo()
    order = np.random.default_rng(3).permutation(coo.nnz)
    r, cc, v = coo.row[order], coo.col[order], coo.data[order]
    zero_col = int(np.flatnonzero(C1[0].toarray().ravel() == 0)[0])
    messy = sp.coo_matrix((np.concatenate([v[:-1], [v[-1] - 400.0, 400.0, 0.0]]),
                           (np.concatenate([r, [r[-1], 0]]), np.concatenate([cc, [cc[-1], zero_col]]))), shape=C1.shape)
    assert messy.nnz == C1.nnz + 2
    assert F._same(F.poisson_copy(messy, 20261411), a)
    # (2) CSR whose column indices run backwards within each row
    p = C1.indptr
    unsorted = sp.csr_matrix((np.concatenate([C1.data[p[i]:p[i + 1]][::-1] for i in range(C1.shape[0])]),
                              np.concatenate([C1.indices[p[i]:p[i + 1]][::-1] for i in range(C1.shape[0])]), p.copy()), shape=C1.shape)
    assert not unsorted.has_sorted_indices
    assert F._same(F.poisson_copy(unsorted, 20261411), a)


def test_poisson_copy_removes_zero_draws_and_refuses_signed_input():
    C1 = big_counts(1)
    out = F.poisson_copy(C1, 5)
    assert out.nnz < C1.nnz and (out.data > 0).all()  # about e^-1 of the entries draw 0 and are removed
    with pytest.raises(ValueError, match=">= 1"):
        F.poisson_copy(-C1, 5)


def nb_fly_and_counts():
    """0 L / 1 R (group a), 2 L / 3 R (group b), 4 midline and 5 unsided (self-mapped), 6 left unmatched."""
    fly = make_fly(7, [], sign=np.ones(7), ntype=["A", "A", "B", "B", "MID", "UNS", "X"], side=["L", "R", "L", "R", "M", "U", "L"],
                   gid=["a", "a", "b", "b", None, None, None], sizes=np.ones(7))
    raw = [(2, 0, 1), (3, 1, 3),    # c 1 / 3: mbar 2, excess 4/2 - 2 = 0
           (0, 2, 4),               # c 4 / 0: mbar 2, excess 16/2 - 2 = 6
           (4, 0, 2), (4, 1, 2),    # self-mapped x matched: mbar 2, excess -2
           (1, 0, 2), (0, 1, 2),    # (i, m(i)) and its image (m(i), i): mbar 2, excess -2
           (2, 1, 10),              # c 10 / 0: mbar 5, excess 100/2 - 5 = 45
           (5, 4, 3),               # both self-mapped: the entry is its own image, left out
           (6, 0, 9), (0, 6, 7)]    # unmatched neuron: left out
    rows, cols, vals = zip(*raw)
    C1 = sp.csr_matrix((np.array(vals, float), (np.array(rows), np.array(cols))), shape=(7, 7))
    return fly, C1


def test_nb_inverse_k_on_a_constructed_example():
    fly, C1 = nb_fly_and_counts()
    mm = MI.mirror_map(fly)
    assert list(mm.status[:7]) == ["g1", "g1", "g1", "g1", "self", "self", "unmatched"]
    out = F.nb_inverse_k(C1, mm)
    # sum(excess * mbar^2) = 4 * (0 + 6 - 2 - 2) + 25 * 45 = 1133; sum(mbar^4) = 4 * 16 + 625 = 689; each pair once
    assert out == {"inv_k": pytest.approx(1133 / 689, rel=1e-14), "n_pairs": 5}
    assert set(out) == {"inv_k", "n_pairs"}
    empty = F.nb_inverse_k(sp.csr_matrix((7, 7)), mm)
    assert np.isnan(empty["inv_k"]) and empty["n_pairs"] == 0


def test_nb_copy_falls_back_to_poisson_and_has_the_nb_moments():
    C1 = big_counts(100, seed=1)
    for inv_k in (0.0, -0.4):
        assert F._same(F.nb_copy(C1, inv_k, 20261421), F.poisson_copy(C1, 20261421))
    with pytest.raises(ValueError, match="finite"):
        F.nb_copy(C1, NAN, 20261421)
    keep = C1.data.copy()
    a, b = F.nb_copy(C1, 0.5, 20261421), F.nb_copy(C1, 0.5, 20261421)
    assert F._same(a, b) and not F._same(a, F.nb_copy(C1, 0.5, 20261422)) and not F._same(a, F.poisson_copy(C1, 20261421))
    assert np.array_equal(C1.data, keep)
    assert_canonical(a)
    # mean c = 100, variance c + c^2 / k = 100 + 0.5 * 100^2 = 5100 (zero draws are removed: count them back as zeros)
    x = np.concatenate([a.data, np.zeros(C1.nnz - a.nnz)])
    assert abs(x.mean() - 100) < 3.0 and abs(x.var() / 5100 - 1) < 0.1


# ------------------------------------------------------------------------------------------------------- rewired control (C5)
def rewire_fly():
    rng = np.random.default_rng(4)
    n = 30
    mask = (rng.random((n, n)) < 0.25) & ~np.eye(n, dtype=bool)
    r, c = np.nonzero(mask)
    entries = [(int(i), int(j), float(v)) for i, j, v in zip(r, c, rng.integers(5, 40, len(r)))]
    sign = rng.choice([1.0, -1.0], n)
    sign[7] = 0.0
    entries = [e for e in entries if e[1] != 7]  # like W-built controls: a sign-0 neuron has no output in W
    side = ["L" if i % 2 == 0 else "R" for i in range(n)]
    gid = [f"g{i // 2}" for i in range(n)]
    ntype = [f"T{i // 4}" for i in range(n)]
    return make_fly(n, entries, sign=sign, ntype=ntype, side=side, gid=gid, sizes=np.arange(1.0, n + 1), with_w=True)


def test_rewired_fly_keeps_signs_and_annotations_and_uses_the_real_mirror_map():
    fly = rewire_fly()
    mm = MI.mirror_map(fly)
    snap = snapshot(fly)
    rf = F.rewired_fly(fly)
    W_r = F._canon(controls.build(fly.net, F.REWIRE_CONTROL)[0])
    assert F._same(rf.C, F._canon(abs(W_r))) and not F._same(rf.C, F._canon(fly.C))
    assert F._same(F.signed(rf.C, rf.sign), W_r)
    assert np.array_equal(rf.sign, fly.sign) and rf.side is fly.side and rf.ntype is fly.ntype and rf.net is fly.net
    assert rf.readout is fly.readout and rf.meta["control"] == F.REWIRE_CONTROL and "control" not in fly.meta
    assert_unchanged(fly, snap)
    W4, sizes = F.apply_fix("4", rf, mm)  # the real network's mirror map
    assert F._same(W4, F.signed(F._symmetrise(rf.C, mm), rf.sign))
    np.testing.assert_array_equal(sizes, fly.net.sizes)
    for name in ("3a", "3b"):
        with pytest.raises(ValueError, match="no pre-floor counts"):
            F.apply_fix(name, rf, mm)
    with pytest.raises(ValueError, match="real MANC fly only"):
        F.rewired_fly(rf)
    with pytest.raises(ValueError, match="real MANC fly only"):
        F.rewired_fly(make_fly(3, [(1, 0, 5)], sign=[1, 1, 1], name="MaleCNS", with_w=True))


def test_rewired_fly_refuses_a_column_with_the_wrong_sign(monkeypatch):
    fly = rewire_fly()
    W_bad = F._canon(fly.net.W)
    W_bad.data[0] = -W_bad.data[0]
    monkeypatch.setattr(controls, "build", lambda net, name: (W_bad, {}))
    with pytest.raises(RuntimeError, match="sign"):
        F.rewired_fly(fly)


# --------------------------------------------------------------------------------------------------- real data (wiring only)
def _real_data_ready() -> bool:
    """The MANC builds (v1.0 sizes, v1.2.1 network, v1.2.3 groups / full cord) and the pinned authors' files are present locally
    (`front_leg()` would otherwise download them)."""
    try:  # `networks` (imported at the top) has put the benchmark directory on sys.path
        from brainir import paths
        from reproduce_manc_connectivity import EXT_DIR, EXTERNAL
    except Exception:  # noqa: BLE001
        return False
    builds = (("manc", "v1.0"), ("manc", "v1.2.1"), ("manc", "v1.2.3"))
    if not all((paths.processed_dir(d, v) / "connections.parquet").exists() for d, v in builds):
        return False
    return all((EXT_DIR / Path(rel).name).exists() for rel, _sha in EXTERNAL.values())


@pytest.mark.skipif(not _real_data_ready(), reason="real-data test: MANC builds or the pinned authors' files are absent")
def test_real_data_manc_raw_counts_at_floor_5_reproduce_b1r():
    fl = N.front_leg()
    C1 = F.manc_raw_counts()  # raises by itself unless floor 5 reproduces B1r and every column's sign is the fly's
    assert C1.shape == (fl.n, fl.n) and C1.data.min() >= 1 and np.array_equal(C1.data, np.round(C1.data))
    C5 = F.at_floor(C1, 5)
    assert F._same(C5, F._canon(fl.C)) and C1.nnz > C5.nnz
    W5, sizes = F.fix_floor(5)
    assert F._same(W5, F._canon(fl.W))
    np.testing.assert_array_equal(sizes, np.asarray(fl.sizes, dtype=float))
    C1.data[:] = 0  # the cached build hands out copies
    assert F._same(F.at_floor(F.manc_raw_counts(), 5), F._canon(fl.C))
