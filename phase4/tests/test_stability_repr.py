"""Dimension stability and representation stability (brainir_causal.evaluate_stability; PROTOCOL 5.10-5.11)."""

from __future__ import annotations

import numpy as np
from test_lift_toysys import DT, ExactModel, ToyLinear, make_records

from brainir_causal.evaluate_stability import bootstrap_interventions, dimension_stability, intervention_items, representation_stability


class Transformed(ExactModel):
    """The exact toy model in other latent coordinates z_b = A z + c (an invertible affine map): the same causal model."""

    def __init__(self, sysm, A, c):
        super().__init__(sysm)
        self.Am, self.c, self.Ai = np.asarray(A, float), np.asarray(c, float), np.linalg.inv(A)

    def encode(self, sid, x_hist, u_hist, dt):
        return self.Am @ super().encode(sid, x_hist, u_hist, dt) + self.c

    def rollout(self, sid, z0, u_future, events, dt):
        r = super().rollout(sid, self.Ai @ (np.asarray(z0, float) - self.c), u_future, events, dt)
        return {"z": r["z"] @ self.Am.T + self.c, "y": r["y"]}


def _kick_rank(records, lag: int = 60, rel_tol: float = 0.05) -> int:
    """A tiny dimension rule: the rank of the kick-effect matrix (intervened minus twin observed state, `lag` samples after the kick)."""
    by = {r["key"]: r for r in records}
    rows = []
    for r in records:
        tw = r["meta"].get("twin_of")
        if not tw or tw not in by:
            continue
        ri = by[tw]
        ev = ri["protocol"]["events"]
        if not ev or ev[0]["kind"] != "kick":
            continue
        i0 = round(ev[0]["t"] / DT)
        rows.append((ri["x"][i0 + lag] - r["x"][i0 + lag]) / abs(float(next(iter(ev[0]["delta"].values())))))
    sv = np.linalg.svd(np.stack(rows), compute_uv=False)
    return int(np.sum(sv > rel_tol * sv[0]))


def test_bootstrap_k_is_stable_on_a_system_with_a_clear_k():
    s = ToyLinear()
    recs, _ = make_records(s, seed=0, full=False)
    refits = bootstrap_interventions(recs, n=5, seed=3)
    items, passive = intervention_items(recs)
    for rs in refits:
        its, pas = intervention_items(rs)
        assert len(its) == len(items) and len(pas) == len(passive)
        keys = [r["key"] for r in rs]
        assert len(keys) == len(set(keys))                       # duplicated items are renamed consistently
        twins = {r["meta"]["twin_of"] for r in rs if r["meta"].get("twin_of")}
        assert twins <= set(keys)
    ks = [_kick_rank(rs) for rs in refits]
    d = dimension_stability(ks, [2, 2], k_true=2, n_obs=5)
    assert ks == [2] * 5 and d["stable"] and d["modal_equals_true"] and d["verdict"] == "stable: k = 2"


def test_dimension_stability_rules():
    assert dimension_stability([2, 2, 2, 2, 3], [2, 3])["stable"]
    un = dimension_stability([2, 2, 3, 3, 4], [2, 4])
    assert not un["stable"] and un["verdict"] == "dimension unresolved: 2-4"
    assert not dimension_stability([2, 2, 2, 2, 3], [2, 2])["stable"]           # a refit outside the reported range
    assert not dimension_stability([2, 2, 2, 2, None], [2, 3])["stable"]        # a refit that selected nothing
    assert not dimension_stability([2, 2, 2, 2, 3])["stable"]                   # no range: every refit must equal the modal k
    assert dimension_stability([3] * 5, None, n_obs=10)["compact"] is False
    assert dimension_stability([2] * 5, None, n_obs=10)["compact"] is True
    assert dimension_stability([2] * 5, None, n_obs=10, mode="mech")["compact"] is None
    # Level B: the 3 fit seeds must agree, or all lie within the reported range
    assert dimension_stability([2, 2, 2], None, level="B")["stable"]
    assert not dimension_stability([2, 2, 3], None, level="B")["stable"]
    assert dimension_stability([2, 3, 3], [2, 3], level="B")["stable"]
    assert not dimension_stability([2, 3, 4], [2, 3], level="B")["stable"]
    assert not dimension_stability([2, None, 2], [2, 3], level="B")["stable"]
    # the same three values at Level C (modal 2 of 3 < 80 %) are unresolved
    assert not dimension_stability([2, 3, 3], [2, 3], level="C")["stable"]


def test_representation_stability_is_invariant_to_affine_reparametrisation():
    s = ToyLinear()
    val, _ = make_records(s, n_passive=6, n_kick=6, n_pulse=2, seed=11, full=False)
    test, _ = make_records(s, n_passive=6, n_kick=8, n_pulse=4, seed=12, full=False)
    a = ExactModel(s)
    b = Transformed(s, [[2.0, 0.5], [-0.3, 1.2]], [1.0, -2.0])
    res = representation_stability([a, b], "toy", val, test, horizon_short_s=0.05, horizon_s=0.25, floor=0.01)
    p = res["pairs"][0]
    assert res["k_agree"] and p["r2_min"] > 0.999 and p["cca_mean_padded"] > 0.999
    assert p["procrustes_residual"] < 1e-6 and p["affine_residual"] < 1e-6
    assert p["disagreement"] < 1e-12 and p["flow_r2"] > 0.999 and p["flow_cos_mean"] > 0.999


def test_representation_stability_detects_a_different_latent():
    s = ToyLinear()
    val, _ = make_records(s, n_passive=6, n_kick=6, n_pulse=2, seed=11, full=False)
    test, _ = make_records(s, n_passive=6, n_kick=8, n_pulse=4, seed=12, full=False)
    res = representation_stability([ExactModel(s), ExactModel(s, wrong=True)], "toy", val, test, horizon_short_s=0.05,
                                   horizon_s=0.25, floor=0.01)
    p = res["pairs"][0]
    assert p["disagreement"] > 0.05 and p["r2_min"] < 0.999


class FlakyEncoder(ExactModel):
    """The exact toy model whose encoder fails on histories of 41 samples (a model crash on some states; deterministic in the input,
    since the evaluator calls fresh copies)."""

    def encode(self, sid, x_hist, u_hist, dt):
        if len(x_hist) == 41:
            raise RuntimeError("encoder failure")
        return super().encode(sid, x_hist, u_hist, dt)


def test_latent_flows_keep_the_latent_width_when_some_encodings_fail():
    """A failed re-encoding gives a NaN row of the latent width (k > 1), never a crash of the whole metric (Level C smoke, P2)."""
    from brainir_causal.evaluate_stability import latent_flows
    s = ToyLinear()
    recs, _ = make_records(s, n_passive=6, n_kick=0, n_pulse=0, seed=13, full=False)
    where = [(ri, 40 + 10 * j) for ri in range(len(recs)) for j in range(2)]
    fl = latent_flows(FlakyEncoder(s), "toy", recs, where, horizon_s=0.1)       # states at sample 40 fail, at 50 succeed
    k = np.size(ExactModel(s).encode("toy", np.asarray(recs[0]["x"] if isinstance(recs[0], dict) else recs[0].x)[:41],
                                     np.asarray(recs[0]["u"] if isinstance(recs[0], dict) else recs[0].u)[:41], DT))
    assert k > 1 and fl.shape == (len(where), k)
    bad = ~np.all(np.isfinite(fl), 1)
    assert 0 < bad.sum() < len(where) and np.all(np.isnan(fl[bad]))
