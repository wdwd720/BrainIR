"""Run 4 (PREREG v4 G4, G8, B2-B3, X2): mirror map, hybrids, paired draws and the v4 job kinds on SYNTHETIC circuits only."""

from __future__ import annotations

import types

import numpy as np
import pytest
import scipy.sparse as sp
from brainir.sim.model import ModelConfig, sample_neuron_params
from brainir.sim.screen import ScreenConfig

from brainir_ledger import jobs as J
from brainir_ledger import jobs_v2 as V2
from brainir_ledger import jobs_v4 as V4
from brainir_ledger import mirror as MR


def _synthetic_fly(seed: int = 0, asym: float = 0.3) -> MR.Fly:
    """Two sides x (2 'DN' members of type D, 8 interneurons of types I0..I3, 3 motor neurons of type MN) + 1 midline neuron; one
    unmatched interneuron on the right; a symmetric core with left-right asymmetries."""
    rng = np.random.default_rng(seed)
    side, ntype, gid = [], [], []
    for s in ("L", "R"):
        for k in range(2):
            side.append(s); ntype.append("D"); gid.append(f"d{k}")
        for k in range(8):
            side.append(s); ntype.append(f"I{k % 4}"); gid.append(f"i{k}")
        for k in range(3):
            side.append(s); ntype.append("MN"); gid.append(f"m{k}")
    side.append("R"); ntype.append("I0"); gid.append(None)      # unmatched right interneuron
    side.append("M"); ntype.append("Mid"); gid.append(None)     # midline neuron
    n = len(side)
    half = 13
    base = (rng.random((half, half)) < 0.35) * rng.integers(5, 40, (half, half))
    np.fill_diagonal(base, 0)
    C = np.zeros((n, n))
    C[:half, :half] = base
    C[half:2 * half, half:2 * half] = base * (1 + asym * rng.normal(size=base.shape)).clip(0.2) * (rng.random(base.shape) > 0.15)
    cross = (rng.random((half, half)) < 0.08) * rng.integers(5, 20, (half, half))
    C[half:2 * half, :half] = cross
    C[:half, half:2 * half] = cross.T
    C[2 * half, rng.integers(0, 2 * half, 5)] = 12      # unmatched neuron receives
    C[rng.integers(0, 2 * half, 5), 2 * half] = 9       # and sends
    C[2 * half + 1, :] = (rng.random(n) < 0.2) * 7      # midline
    np.fill_diagonal(C, 0)
    C = np.round(C)
    sign = np.array([1.0] * 2 + [1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, 1.0] + [1.0] * 3)
    sign = np.concatenate([sign, sign, [1.0, -1.0]])
    sizes = rng.uniform(0.5e9, 2e9, n)
    sizes[3] = np.nan
    readout = np.array([t == "MN" for t in ntype])
    net = types.SimpleNamespace(sizes=sizes, W=sp.csr_matrix(C * sign[None, :]))
    side_a = np.array(side, dtype=object)
    groups = {"D": [0, 1, half, half + 1]}
    return MR.Fly("SYN", net, groups, side_a, np.full(n, "-", dtype=object), side_a.copy(), np.zeros(n, bool), np.zeros(n, bool), {},
                  np.array(gid, dtype=object), np.array(ntype, dtype=object), sign, sp.csr_matrix(C), readout)


CFG = ModelConfig(t_end=0.4)
SCREEN = ScreenConfig(n_active_lower=1, n_active_upper=1500, n_high_fr_upper=200)


def test_paired_params_identity_reproduces_sample_neuron_params_bitwise():
    rng = np.random.default_rng(3)
    for n in (7, 50, 401):
        sizes = rng.uniform(1e8, 3e9, n)
        sizes[rng.integers(0, n, 3)] = np.nan
        sizes[rng.integers(0, n, 2)] = 0.0
        for seed in (0, 5, 15):
            a = sample_neuron_params(ModelConfig(), n, seed, sizes)
            b = MR.paired_params(ModelConfig(), seed, n, sizes, np.arange(n), sizes)
            for f in ("tau", "a", "theta", "r_max", "size_scale"):
                assert np.array_equal(getattr(a, f), getattr(b, f)), (n, seed, f)


def test_mirror_map_involution_ghosts_and_hybrids():
    f = _synthetic_fly()
    mm = MR.mirror_map(f)
    assert np.array_equal(mm.m[mm.m], np.arange(mm.n_ext))
    assert mm.counts["ghost_slots"] == 1 and mm.counts["self_mapped"] == 1
    e = MR.extend(f.C, f.sign, f.net.sizes, mm)
    em = MR.mirror(e, mm)
    assert abs(MR.mirror(em, mm).C - e.C).max() == 0
    cache = MR.entry_classes(e, em, mm)
    h_all = MR.hybrid(e, em, mm, {1, 2, 3, 4, 5}, cache=cache)
    assert abs(h_all.C - em.C).max() == 0 and np.array_equal(h_all.sign, em.sign) and np.array_equal(h_all.present, em.present)
    assert np.array_equal(np.nan_to_num(h_all.sizes, nan=-1), np.nan_to_num(em.sizes, nan=-1))
    h0 = MR.hybrid(e, em, mm, set(), cache=cache)
    assert abs(h0.C - e.C).max() == 0 and np.array_equal(h0.present, e.present)
    # each class changes something and classes 1-3 partition the differing entries
    U, a, b, cls = cache
    assert set(np.unique(cls[a != b]).tolist()) <= {1, 2, 3}
    # Block 2: own + rest are complementary
    slots = MR.left_slots(mm, [0, 1], [13, 14])
    own = MR.columns_from(e, em, slots)
    rest = MR.columns_from(em, e, slots)
    assert abs(own.C[:, slots] - em.C[:, slots]).max() == 0
    keep = [j for j in range(mm.n_ext) if j not in slots]
    assert abs(rest.C[:, keep] - em.C[:, keep]).max() == 0 and abs(rest.C[:, slots] - e.C[:, slots]).max() == 0


def _job(W, sizes, members, readout, seed, P, **kw):
    j = {"key": f"t|s{seed}", "kind": "group_v4", "seed": seed, "k_min": 1, "model": CFG.to_dict(), "screen": SCREEN.to_dict(),
         "W": W, "sizes": sizes, "members": members, "readout": readout, "params": P}
    j.update(kw)
    return j


def test_left_screen_on_mirror_equals_right_screen_on_W_and_relabelling():
    f = _synthetic_fly(seed=1)
    mm = MR.mirror_map(f)
    e = MR.extend(f.C, f.sign, f.net.sizes, mm)
    em = MR.mirror(e, mm)
    real = mm.real_of()
    roL = f.readout[real] & (mm.side == "L")
    roR = f.readout[real] & (mm.side == "R")
    P = {"mode": "paired", "n_real": mm.n_real, "src": MR.paired_source(mm), "sizes_real": f.net.sizes}
    slots = MR.left_slots(mm, [0, 1], [13, 14])
    perm = np.random.default_rng(7).permutation(mm.n_ext)
    for seed in range(4):
        r_w = V4.run_job(_job(e.W(), e.sizes, [13, 14], roR, seed, P))
        l_m = V4.run_job(_job(em.W(), em.sizes, MR.stimulated(slots, em.present), roL, seed, P))
        assert "error" not in r_w and "error" not in l_m, (r_w.get("error"), l_m.get("error"))
        for k in ("usable", "current", "n_tuning_runs", "n_active_all", "n_high_fr", "n_active_readout", "verdict"):
            assert r_w.get(k) == l_m.get(k), (seed, k)
        assert abs((r_w["score"] or 0) - (l_m["score"] or 0)) < 1e-9
        l_w = V4.run_job(_job(e.W(), e.sizes, MR.stimulated(slots, e.present), roL, seed, P))
        l_q = V4.run_job(_job(e.W(), e.sizes, MR.stimulated(slots, e.present), roL, seed, P, perm=perm))
        for k in ("usable", "current", "n_tuning_runs", "n_active_all", "n_high_fr", "n_active_readout", "verdict"):
            assert l_w.get(k) == l_q.get(k), (seed, k)
        assert abs((l_w["score"] or 0) - (l_q["score"] or 0)) < 1e-9
        # identity hybrid (nothing replaced) is bit-identical to W
        ed = {"C": e.C, "sign": e.sign, "sizes": e.sizes, "present": e.present}
        l_id = V4.run_job(_job(None, None, None, roL, seed, P, hybrid={"base": ed, "other": ed, "cols": slots, "slots": slots}))
        assert l_id["digest"] == l_w["digest"] and l_id["digest_v4"] == l_w["digest_v4"]


def test_sweep_matches_fixed_run_and_delegation():
    f = _synthetic_fly(seed=2)
    W = sp.csr_matrix(f.net.W)
    ro = f.readout & (f.side == "L")
    cur = [8.0, 32.0, 128.0]
    sw = V4.run_job({"key": "s", "kind": "sweep_v4", "seed": 3, "k_min": 1, "model": CFG.to_dict(), "screen": SCREEN.to_dict(), "W": W,
                     "sizes": f.net.sizes, "members": [0, 1], "readout": ro, "params": {"mode": "standard"}, "currents": cur})
    assert "error" not in sw, sw.get("error")
    for c, r in zip(cur, sw["runs"]):
        fx = J.run_job({"key": "x", "kind": "fixed", "seed": 3, "model": CFG.to_dict(), "screen": SCREEN.to_dict(), "W": W, "sizes": f.net.sizes,
                        "readout": ro, "stim_indices": [0, 1], "currents": [c, c]})
        for k in ("verdict", "n_active_all", "n_high_fr", "n_active_readout"):
            assert fx[k] == r[k]
        assert fx["score"] == r["score"]
        assert r["in_bounds"] == (r["verdict"] == "ok" and r["n_active_readout"] >= 1)
    g = {"key": "g", "kind": "group_v2", "seed": 1, "k_min": 1, "model": CFG.to_dict(), "screen": SCREEN.to_dict(), "W": W,
         "sizes": f.net.sizes, "members": [0, 1], "readout": ro, "extras": {"readout_traces": True}}
    a, b = V4.run_job(dict(g)), V2.run_job(dict(g))
    assert a["digest"] == b["digest"]


def test_output_side_rule():
    C = sp.csr_matrix(np.array([[0, 5, 0], [0, 0, 0], [0, 9, 0]], dtype=float))  # neuron 1 outputs 5 onto 0 (L) and 9 onto 2 (R)
    side = np.array(["L", "U", "R"], dtype=object)
    out = MR.output_side(C, side, [0, 1, 2])
    assert out[1] == "R" and out[0] == "" and out[2] == ""
    s, corr, drop, rel = MR._apply_rule("x", np.array(["L", "L", "R"], dtype=object), out, [1])
    assert not rel["reliable"] and s[1] == "R" and corr[1]


@pytest.mark.parametrize("n_ext_equal", [True])
def test_extend_without_ghosts(n_ext_equal):
    f = _synthetic_fly()
    mm = MR.mirror_map(f)
    e = MR.extend(f.C, f.sign, f.net.sizes, mm)
    assert abs(e.W()[: f.n, : f.n] - sp.csr_matrix(f.C.multiply(f.sign[None, :]))).max() == 0


def test_mirror_trajectories_match_slot_for_slot_and_tuner_moves():
    """Strong check: with paired draws, simulating M with the left slots stimulated gives, for every slot i, the trace that
    simulating W with the mirrored slots stimulated gives for slot m(i); and with tight bounds the tuner moves (so the job-level
    comparison is not trivial) and the left and right screens of W differ."""
    from brainir.sim.model import Stimulus, simulate  # noqa: PLC0415

    f = _synthetic_fly(seed=4, asym=0.6)
    mm = MR.mirror_map(f)
    e = MR.extend(f.C, f.sign, f.net.sizes, mm)
    em = MR.mirror(e, mm)
    src = MR.paired_source(mm)
    pw = MR.paired_params(CFG, 2, mm.n_real, f.net.sizes, src, e.sizes)
    pm = MR.paired_params(CFG, 2, mm.n_real, f.net.sizes, src, em.sizes)
    for fld in ("tau", "a", "theta", "r_max"):
        assert np.array_equal(getattr(pm, fld), getattr(pw, fld)[mm.m])
    slots = MR.stimulated(MR.left_slots(mm, [0, 1], [13, 14]), em.present)
    tm = simulate(em.W(), pm, CFG, Stimulus(tuple(slots), (60.0,)))
    tw = simulate(e.W(), pw, CFG, Stimulus(tuple(int(mm.m[i]) for i in slots), (60.0,)))
    assert tm.r.shape == tw.r.shape
    # equal up to the adaptive solver's tolerance (rtol 2e-6): a relabelled system sums in another order (PREREG v4 B2.3-B2.4)
    assert np.max(np.abs(tm.r - tw.r[:, mm.m])) <= 1e-5 * np.max(np.abs(tw.r))
    assert np.max(tw.r) > 1.0  # the network is active
    tight = ScreenConfig(n_active_lower=3, n_active_upper=12, n_high_fr_upper=200)
    real = mm.real_of()
    roL = f.readout[real] & (mm.side == "L")
    roR = f.readout[real] & (mm.side == "R")
    P = {"mode": "paired", "n_real": mm.n_real, "src": src, "sizes_real": f.net.sizes}
    moved = differs = 0
    for seed in range(6):
        jl = _job(e.W(), e.sizes, MR.stimulated(MR.left_slots(mm, [0, 1], [13, 14]), e.present), roL, seed, P, screen=tight.to_dict())
        jr = _job(e.W(), e.sizes, [13, 14], roR, seed, P, screen=tight.to_dict())
        jm = _job(em.W(), em.sizes, slots, roL, seed, P, screen=tight.to_dict())
        a, b, c = V4.run_job(jl), V4.run_job(jr), V4.run_job(jm)
        moved += int(b["n_tuning_runs"] > 1)
        differs += int((a["current"], a["n_active_all"], a["n_high_fr"]) != (b["current"], b["n_active_all"], b["n_high_fr"]))
        for k in ("usable", "current", "n_tuning_runs", "n_active_all", "n_high_fr", "n_active_readout", "verdict"):
            assert b.get(k) == c.get(k), (seed, k)
    assert moved > 0 and differs > 0


def _fly_with_cross_type_group():
    """Type E has 2 left members and 1 right member; E's right member shares an annotated group with a left member of type D (a
    cross-type group, as in MaleCNS); D has 2 + 2 members. Audit findings 1 and 2."""
    f = _synthetic_fly(seed=5)
    n = f.n
    gid = f.gid.copy()
    # members: D = 0, 1 (L), 13, 14 (R); make E = 2, 3 (L, interneuron slots) and 15 (R)
    gid[15] = gid[0]          # cross-type group: E's right member grouped with D's left member 0
    ntype = f.ntype.copy()
    ntype[[2, 3, 15]] = "E"
    groups = {"D": [0, 1, 13, 14], "E": [2, 3, 15]}
    return MR.Fly("SYN2", f.net, groups, f.side_annot, f.out_side, f.side, f.corrected, f.dropped, {}, gid, ntype, f.sign, f.C, f.readout), n


def test_stimulated_set_on_mirror_is_mirror_of_right_members_and_hybrids_have_no_driven_absent_slots():
    f, n = _fly_with_cross_type_group()
    mm = MR.mirror_map(f)
    e = MR.extend(f.C, f.sign, f.net.sizes, mm)
    em = MR.mirror(e, mm)
    for t, mem in f.groups.items():
        L = [i for i in mem if f.side[i] == "L"]
        R = [i for i in mem if f.side[i] == "R"]
        slots = MR.left_slots(mm, L, R)
        assert sorted(MR.stimulated(slots, em.present)) == sorted(int(mm.m[j]) for j in R), t   # S_M == m(R_t)
        assert sorted(MR.stimulated(slots, e.present)) == sorted(L), t                          # S_W == L_t
        for j in L + R:   # step 0: partners stay within the type (or are ghosts)
            assert mm.status[j] == "unmatched" or int(mm.m[j]) in mem
        own, rest = MR.columns_from(e, em, slots), MR.columns_from(em, e, slots)
        for h in (own, rest):
            absent = np.flatnonzero(~h.present)
            assert abs(h.C[absent, :]).sum() == 0 and abs(h.C[:, absent]).sum() == 0   # absent slots have no input and no output
        # complementarity outside the slots whose presence differs between W and M (their entries are dropped where absent)
        import scipy.sparse as sp_  # noqa: PLC0415

        D = sp_.diags((e.present == em.present).astype(float))
        assert abs(D @ ((own.C + rest.C) - (e.C + em.C)) @ D).max() == 0
    assert mm.counts["unmatched_stimulated_type_members"] == 1
