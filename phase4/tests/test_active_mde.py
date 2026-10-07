"""The pre-freeze MDE of the active-design rule (brainir_causal.active_mde, scripts/p4/active_mde.py): the lazy reference-learner
adapter, one reference loop with evaluated checkpoints on a tiny toy tier, the PACKED path (phase 1 + checkpoint tasks) against the
unpacked loop bit for bit, the memory-aware scheduler, the crashed-pool retry, the parallel summary, the planner, and the TRUE-STATE
draw context (reference learner v2: preflight, fits and registrations with draws, refusals) on a toy generator whose trajectories
carry their draw."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from brainir_causal import active_mde as AM
from brainir_causal import suites as S
from brainir_causal.refs import LearnerConfig, fit_reference

TINY = {"B_MAIN": {"synthetic": 3, "full": 3, "mech": 3}, "D0_DESIGN": {"obs.nominal": 2, "obs.stim": 1, "obs.init": 1, "obs.wnoise": 1},
        "POOL_DRAWS": 2, "POOL_TRAJ": 3, "POOL_STATES": 2, "POOL_FLOOR_STATES": 2, "N_PASSIVE_TEST": 2, "CELLS_PER_FAMILY": 1,
        "STATES_PER_CELL": 2, "ITEMS_PER_CATEGORY": 1, "N_EQUIV_STATES": 1, "N_LIFT_CASES": 2}
FAST = {"hidden": 16, "hidden_full": 16, "steps_one": 30, "steps_multi": 10, "readout_steps": 30, "batch": 64, "max_passive_rows": 3000,
        "shrink_pairs": 4, "threads": 1}
FIELDS = ("EE", "EE_ci95", "EE_pooled", "n_cells", "n_items", "n_abstained", "n_failed", "n_records", "experiments", "trajectories", "spent",
          "n_probe_encodes")
REPO = Path(__file__).resolve().parents[2]


def _driver():
    spec = importlib.util.spec_from_file_location("p4_active_mde_driver", REPO / "scripts" / "p4" / "active_mde.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def toy_tier(tmp_path_factory):
    root = tmp_path_factory.mktemp("amde")
    salt = "ab" * 32
    (root / "salt.txt").write_text(salt, encoding="utf-8")
    (root / "commit.json").write_text(json.dumps({"sha256_of_salt": hashlib.sha256(salt.encode()).hexdigest()}), encoding="utf-8")
    saved = {k: getattr(S, k) for k in list(TINY) + ["SALT_FILE", "COMMITMENT"]}
    for k, v in TINY.items():
        setattr(S, k, v)
    S.SALT_FILE, S.COMMITMENT = root / "salt.txt", root / "commit.json"
    try:
        S.build_tier("toy", workers=1, systems=["syn:toy:0"], root=root / "suites", store_root=root / "store", parts=S.TIER_PARTS["toy"])
    finally:
        for k, v in saved.items():
            setattr(S, k, v)
    return root


def _job(root, learner, designer, seed=0, tag=""):
    return {"sid": "syn:toy:0", "learner": learner, "designer": designer, "seed": seed, "budget": 4, "checkpoints": [2, 4], "batch": 2,
            "heldout_root": str(root / "suites"), "heldout_tier": "toy", "public_root": str(root / "suites"), "public_tier": "toy",
            "internal_path": str(root / "suites" / "toy" / "internal_records.json"),
            "store_root": str(root / f"loopstore{tag}_{learner}_{designer}_{seed}"), "store_read_roots": [str(root / "store")],
            "generator": None, "learner_cfg": FAST, "n_boot": 50,
            "pred": {"s0": 10.0, "s1": 0.0, "g0": 0.1, "g1": 1.0, "n_obs": 5, "rows": 101}}


def test_lazy_reference_equals_an_eager_fit(toy_tier):
    from brainir_causal.data import ExperimentSet
    es = ExperimentSet.load(S.tier_dirs("toy", toy_tier / "suites")["public"] / "syn_toy_0", lazy=True)
    recs = [es.load(r) for r in es.rows if r.get("split") == "train"][:8]
    sysrec = es.systems["syn:toy:0"]
    cfg = LearnerConfig(**FAST)
    learner = AM.ReferenceLearner("full_state", "syn:toy:0", sysrec, cfg=cfg)
    lazy = learner.update(learner.fit(recs[:4], seed=3), recs[4:], data_all=recs, seed=3)
    assert learner.n_fits == 0                                      # nothing fitted before first use
    eager = fit_reference("full_state", "syn:toy:0", recs, sysrec, cfg=LearnerConfig(**{**FAST, "seed": 3}))
    r = recs[0]
    za = lazy.encode("syn:toy:0", r.x[:20], r.u[:20], float(r.protocol["dt"]))
    zb = eager.encode("syn:toy:0", r.x[:20], r.u[:20], float(r.protocol["dt"]))
    ya = lazy.rollout("syn:toy:0", za, r.u[19:40], [], float(r.protocol["dt"]))["y"]
    yb = eager.rollout("syn:toy:0", zb, r.u[19:40], [], float(r.protocol["dt"]))["y"]
    assert learner.n_fits == 1 and np.array_equal(np.asarray(za), np.asarray(zb)) and np.array_equal(np.asarray(ya), np.asarray(yb))
    with pytest.raises(ValueError):
        AM.ReferenceLearner("true_state", "syn:toy:0", sysrec)      # the true state is required


def test_deferred_model_refuses_queries():
    m = AM.DeferredLearner().fit([], seed=0)
    assert m.info()["train_cost"]["deferred"] is True
    with pytest.raises(RuntimeError):
        m.encode("s", None, None, 0.01)


@pytest.mark.parametrize("learner,designer", [("full_state", "random"), ("true_state", "fixed")])
def test_reference_loop_job_evaluates_every_checkpoint(toy_tier, learner, designer):
    out = AM.reference_loop_job(_job(toy_tier, learner, designer))
    rows = out["rows"]
    assert [r["budget"] for r in rows] == [2, 4]
    for r in rows:
        assert r["system"] == "syn:toy:0" and r["learner"] == learner and r["designer"] == designer and r["loop_seed"] == 0
        assert "error" not in r, r.get("traceback")
        assert np.isfinite(r["EE"]) and r["n_items"] > 0 and r["experiments"] >= r["budget"]
    assert out["loop"]["n_fits"] == 2                                 # only the two checkpoint models were fitted
    if learner == "true_state":
        assert all(r["n_probe_encodes"] == 0 for r in rows)          # every evaluated history had its true state registered
        assert all(r["draw_required"] is False and r["draw_context"] is False and r["draw_context_reason"] == AM.NO_DRAWS
                   for r in rows)                                    # the plain toy carries no draws


def _unpacked(job):
    return AM.reference_loop_job(job)


# ------------------------------------------------------------------------------------------------ the draw context (learner v2)
DRAW_GEN = '''"""Test generator: the toy system with its trajectory's effective draw (its time constant tau) as truth["draw"]."""
import hashlib
import json

import numpy as np

from brainir_causal.synthadapter import ToySystem


class DrawToyBase(ToySystem):
    engine_id = "toy-linear-2-drawtest"

    def __init__(self, seed, j=0):
        super().__init__(seed, j)
        self.system_id = f"syn:dtoy:{j}"

    def content_hash(self):
        return hashlib.sha256(json.dumps({"drawtoy": self.engine_id, "seed": self.seed, "j": self.j}).encode()).hexdigest()


class DrawToy(DrawToyBase):
    def draw_effective(self, protocol):
        sp = protocol.get("params_spread")
        return np.array([self._params(protocol["params_seed"], 1.0 if sp is None else float(sp))["tau"][0]])


def build_suite(tier, seed, n_per_type=None):
    return {s.system_id: s for s in (DrawToy(int(seed), j) for j in range(2))}
'''
NODRAW_GEN = '''"""The same systems (same content hashes) WITHOUT draw_effective: a generator whose new trajectories carry no draw."""
from drawtoy import DrawToyBase


def build_suite(tier, seed, n_per_type=None):
    return {s.system_id: s for s in (DrawToyBase(int(seed), j) for j in range(2))}
'''
CONST_GEN = '''"""Test generator: toy systems whose trajectories all share ONE parameter draw (constant draws: z alone is exact given it)."""
import numpy as np

from drawtoy import DrawToyBase


class ConstDrawToy(DrawToyBase):
    engine_id = "toy-linear-2-drawtest-const"            # another engine, so another content hash

    def _params(self, seed, spread=1.0):
        return super()._params(0, 0.0)

    def draw_effective(self, protocol):
        return np.array([self._params(0)["tau"][0]])


def build_suite(tier, seed, n_per_type=None):
    return {s.system_id: s for s in (ConstDrawToy(int(seed), j) for j in range(2))}
'''


def _build_draw_tier(root: Path, pkg: str) -> Path:
    """A tiny tier ('dev' inside the temporary root) of the toy system syn:dtoy:0 built by the test generator package `pkg`."""
    gen = root / "gen"
    gen.mkdir()
    for name, src in (("drawtoy", DRAW_GEN), ("drawtoy_nd", NODRAW_GEN), ("drawtoy_const", CONST_GEN)):
        (gen / f"{name}.py").write_text(src, encoding="utf-8")
    salt = "cd" * 32
    (root / "salt.txt").write_text(salt, encoding="utf-8")
    (root / "commit.json").write_text(json.dumps({"sha256_of_salt": hashlib.sha256(salt.encode()).hexdigest()}), encoding="utf-8")
    saved = {k: getattr(S, k) for k in list(TINY) + ["SALT_FILE", "COMMITMENT"]}
    for k, v in TINY.items():
        setattr(S, k, v)
    S.SALT_FILE, S.COMMITMENT = root / "salt.txt", root / "commit.json"
    try:
        S.build_tier("dev", generator=(str(gen), pkg), workers=1, systems=["syn:dtoy:0"], root=root / "suites",
                     store_root=root / "store", parts=S.TIER_PARTS["dev"])
    finally:
        for k, v in saved.items():
            setattr(S, k, v)
    return root


@pytest.fixture(scope="module")
def draw_tier(tmp_path_factory):
    """Every trajectory has its own draw (its time constant) in the truth store."""
    return _build_draw_tier(tmp_path_factory.mktemp("amde_draw"), "drawtoy")


@pytest.fixture(scope="module")
def const_draw_tier(tmp_path_factory):
    """Every trajectory has the SAME draw in the truth store (the toy's parameters are not drawn)."""
    return _build_draw_tier(tmp_path_factory.mktemp("amde_cdraw"), "drawtoy_const")


def _djob(root, learner, designer, seed=0, tag="", pkg="drawtoy"):
    return {**_job(root, learner, designer, seed, tag), "sid": "syn:dtoy:0", "heldout_tier": "dev", "public_tier": "dev",
            "internal_path": str(root / "suites" / "dev" / "internal_records.json"), "generator": [str(root / "gen"), pkg]}


def test_the_draw_tier_passes_the_preflight_and_a_generator_without_draws_fails_it(draw_tier):
    pre = AM.draw_preflight(_djob(draw_tier, "true_state", "random"))
    assert pre["n_d0"] > 0 and pre["n_d0_with_draw"] == pre["n_d0"] == pre["n_d0_with_z"]
    assert pre["n_held_with_z"] > 0 and pre["n_held_with_draw"] == pre["n_held_with_z"] and pre["generator_draws"]
    assert pre["d0_draw_sizes"] == [1] and pre["d0_draw_varying"] == 1 and pre["d0_draw_finite"] is True   # tau varies over D0
    ok = AM.draw_verdict([pre], allow_no_draw=False)
    assert ok["ok"] and ok["draws"] is True and not ok["warnings"]
    nd = AM.draw_preflight(_djob(draw_tier, "true_state", "random", pkg="drawtoy_nd"))
    assert nd["generator_draws"] is False
    v = AM.draw_verdict([pre, nd], allow_no_draw=False)
    assert not v["ok"] and "draw_effective" in v["systems"]["syn:dtoy:0"]

    from brainir_causal.p4modal.app import CLASSES
    drv = _driver()
    assert CLASSES[drv.PRE_CLS]["gated"]          # the preflight constructs systems (hash-checked): reference numerics only

    class _FakeBackend:                        # the driver's draw_check (host-gated containers): one result and one failed container
        def call(self, fn, args, *, cls, **kw):
            assert fn == "brainir_causal.active_mde:draw_preflight" and cls == drv.PRE_CLS
            return [{"result": AM.draw_preflight(*a)} if i == 0 else RuntimeError("container lost") for i, a in enumerate(args)]
    job = _djob(draw_tier, "true_state", "random")
    pre2, v2 = drv.draw_check(_FakeBackend(), [job, job], allow_no_draw=False)
    assert pre2[0] == pre and pre2[1] == {"sid": "syn:dtoy:0", "error": "container lost"}
    assert not v2["ok"] and "preflight failed: container lost" in v2["systems"]["syn:dtoy:0"]


def test_true_state_fits_use_the_draws_and_packed_equals_unpacked(draw_tier, tmp_path):
    """TRUE-STATE on a tier with draws: every fit encodes [z, draw] (draw_context), every held-out history is registered with its
    draw, and the packed rows equal the unpacked loop's bit for bit (FULL-STATE of the same stream alongside)."""
    jobs_u = [_djob(draw_tier, "true_state", "random", 1, tag="du"), _djob(draw_tier, "full_state", "random", 1, tag="du")]
    jobs_p = [_djob(draw_tier, "true_state", "random", 1, tag="dp"), _djob(draw_tier, "full_state", "random", 1, tag="dp")]
    with ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context("spawn"), initializer=AM.pool_init, initargs=(1,)) as ex:
        unpacked = [row for out in ex.map(_unpacked, jobs_u) for row in out["rows"]]
    res = AM.reference_pack_job({"loops": jobs_p, "workers": 2, "threads": 1, "mem_budget_gb": 64, "work_dir": str(tmp_path / "w")})
    cmp = _driver().compare_rows(res["rows"], unpacked)
    assert cmp["bit_identical"] and cmp["n_rows"] == 4, cmp
    ts = [r for r in res["rows"] + unpacked if r["learner"] == "true_state"]
    assert len(ts) == 4
    for r in ts:
        assert "error" not in r, r.get("error")
        assert r["draw_required"] is True and r["draw_context"] is True and r["n_registered_without_draw"] == 0 and r["n_probe_encodes"] == 0
        assert r["static_context"]["kept"] == 1 and r["training_draws"] == "varying" and r["draw_context_reason"] is None
    assert not AM.draw_violations(res["rows"] + unpacked)


def test_a_simulator_without_draws_is_refused_when_the_tier_has_them(draw_tier, tmp_path):
    job = _djob(draw_tier, "true_state", "fixed", 2, tag="dn", pkg="drawtoy_nd")
    with pytest.raises(RuntimeError, match="have none"):
        AM.loop_phase1(job, str(tmp_path), capture_truth=True)


def test_constant_draws_switch_the_context_off_without_refusal(const_draw_tier):
    """Every trajectory shares one draw: each TRUE-STATE fit legitimately runs without the context (z alone is exact given that draw),
    recorded as draw_context False with the reason 'constant draws', and the run does not refuse (the orchestrator's decision)."""
    job = _djob(const_draw_tier, "true_state", "random", 0, tag="c", pkg="drawtoy_const")
    v = AM.draw_verdict([AM.draw_preflight(job)], allow_no_draw=False)
    assert v["ok"] and v["draws"] is True and "constant over D0" in v["warnings"]["syn:dtoy:0"]
    rows = AM.reference_loop_job(job)["rows"]
    assert [r["budget"] for r in rows] == [2, 4]
    for r in rows:
        assert "error" not in r, r.get("error")
        assert r["draw_required"] is True and r["draw_context"] is False and r["draw_context_reason"] == AM.CONSTANT_DRAWS
        assert r["training_draws"] == "constant" and "constant" in str(r["static_context"]) and np.isfinite(r["EE"])
        assert r["n_registered_without_draw"] == 0 and r["n_probe_encodes"] == 0
    assert not AM.draw_violations(rows)
    tally = _driver().draw_tally(rows)
    assert tally["n_constant_draws"] == 2 and tally["n_draw_context"] == 0 and tally["n_draw_required"] == 2


def test_varying_draws_without_the_context_are_refused(draw_tier, monkeypatch):
    """Training draws that VARY with a fit that reports no draw context (here a learner that drops the draws it is given) are
    refused; the same records with constant draws are not."""
    import brainir_causal.refs as R
    job = _djob(draw_tier, "true_state", "random")
    sysrec, d0 = AM.load_d0(job)
    tz, tdr = AM._truth_of(AM._truth_dir(job), [r.key for r in d0])
    assert AM.draw_requirement([r.key for r in d0], tdr) is True

    def learner(draws):
        return AM.ReferenceLearner("true_state", job["sid"], sysrec, truth_z=tz, truth_draw=draws, draw_required=True,
                                   cfg=LearnerConfig(**FAST))
    ok = learner(tdr).fit_now(d0, 0)
    assert ok.info()["draw_context"] is True
    assert ok.mde_draw_check == {"draw_context": True, "training_draws": "varying", "reason": None}
    flat = learner({k: np.array([0.1]) for k in tdr}).fit_now(d0, 0)
    assert flat.info()["draw_context"] is False and flat.mde_draw_check["reason"] == AM.CONSTANT_DRAWS
    real = R.fit_reference

    def drops_draws(name, sid, records, sysrec_, **kw):
        if name == "true_state":
            kw["truth"] = {**kw["truth"], "draw": None}
        return real(name, sid, records, sysrec_, **kw)
    monkeypatch.setattr(R, "fit_reference", drops_draws)
    with pytest.raises(RuntimeError, match="training draws vary"):
        learner(tdr).fit_now(d0, 0)


def test_draw_context_rules():
    class _Model:
        def __init__(self, on):
            self.on = on
            self.fit_notes = {"static_context": "off: test"}

        def info(self):
            return {"draw_context": self.on}
    vary, const = [np.array([0.1, 1.0]), np.array([0.2, 1.0])], [np.array([0.1, 1.0])] * 2
    assert AM.check_draw_context(_Model(True), vary) == {"draw_context": True, "training_draws": "varying", "reason": None}
    assert AM.check_draw_context(_Model(False), const) == {"draw_context": False, "training_draws": "constant",
                                                          "reason": AM.CONSTANT_DRAWS}
    with pytest.raises(RuntimeError, match="training draws vary"):
        AM.check_draw_context(_Model(False), vary)
    with pytest.raises(RuntimeError, match="lengths"):
        AM.check_draw_context(_Model(True), [np.array([0.1]), np.array([0.1, 0.2])])
    with pytest.raises(RuntimeError, match="non-finite"):
        AM.check_draw_context(_Model(True), [np.array([np.nan]), np.array([0.1])])
    recs = [SimpleNamespace(key="a"), SimpleNamespace(key="b")]
    AM._check_loop_draws(recs, {"a": np.array([0.1]), "b": np.array([0.2])})
    with pytest.raises(RuntimeError, match="have none"):
        AM._check_loop_draws(recs, {"a": np.array([0.1])})
    with pytest.raises(RuntimeError, match="inconsistent"):
        AM._check_loop_draws(recs, {"a": np.array([0.1]), "b": np.array([0.1, 0.2])})


def test_draw_rules():
    assert AM.draw_requirement(["a", "b"], {"a": 1, "b": 2}) is True
    assert AM.draw_requirement(["a", "b"], {}) is False
    with pytest.raises(RuntimeError, match="incomplete"):
        AM.draw_requirement(["a", "b"], {"a": 1})
    none = {"sid": "s", "n_d0": 5, "n_d0_with_z": 5, "n_d0_with_draw": 0, "n_held": 9, "n_held_with_z": 9, "n_held_with_draw": 0,
            "generator_draws": False}
    assert not AM.draw_verdict([none], allow_no_draw=False)["ok"] and AM.draw_verdict([none], allow_no_draw=True)["ok"]
    part = dict(none, n_d0_with_draw=5, n_held_with_draw=8, generator_draws=True, d0_draw_sizes=[3], d0_draw_varying=2)
    v = AM.draw_verdict([part], allow_no_draw=True)
    assert not v["ok"] and "held-out draws 8 of 9" in v["systems"]["s"]
    full = dict(part, n_held_with_draw=9)
    assert AM.draw_verdict([full], allow_no_draw=False)["ok"]
    assert "different lengths" in AM.draw_verdict([dict(full, d0_draw_sizes=[2, 3], d0_draw_varying=None)],
                                                  allow_no_draw=False)["systems"]["s"]
    flat = AM.draw_verdict([dict(full, d0_draw_varying=0)], allow_no_draw=False)       # constant over D0: a note, not a refusal
    assert flat["ok"] and "constant over D0" in flat["warnings"]["s"]
    assert "non-finite" in AM.draw_verdict([dict(full, d0_draw_finite=False)], allow_no_draw=False)["systems"]["s"]
    rows = [{"learner": "true_state", "system": "s", "designer": "random", "loop_seed": 0, "budget": 10, "draw_required": True,
             "draw_context": False},
            {"learner": "true_state", "system": "s", "designer": "random", "loop_seed": 0, "budget": 25, "draw_required": True,
             "draw_context": True, "n_registered_without_draw": 0},
            {"learner": "full_state", "system": "s", "designer": "random", "loop_seed": 0, "budget": 10}]
    assert len(AM.draw_violations(rows)) == 1 and not AM.draw_violations(rows[1:])
    assert not AM.draw_violations([dict(rows[0], draw_context_reason=AM.CONSTANT_DRAWS)])      # constant training draws: legitimate
    refused = dict(rows[1], draw_context=None, error="RuntimeError: TRUE-STATE fit without its draw context although its training "
                                                     "draws vary (1 of 1 coordinates; static_context: off)")
    assert len(AM.draw_violations([refused])) == 1
    assert len(AM.draw_violations([], [{"loop_id": "x", "error": "RuntimeError: the loop's effective draws are inconsistent"}])) == 1


def test_packed_rows_equal_unpacked_rows_bit_for_bit(toy_tier, tmp_path):
    """The packed path (phase 1 + checkpoint tasks on 2 workers) against the unpacked loop run in a worker with the same thread
    settings: every checkpoint row identical (each side simulates into its own store). Under machine load a worker can be killed (e.g.
    out of memory): such INFRASTRUCTURE failures (a broken pool, crash retries exhausted, an error row, a failed loop) fail the test
    with an explicit infrastructure message, never as a row difference; a crash that was retried successfully is not a failure (the
    retried task must still reproduce the unpacked row bit for bit, which is the stronger check under load)."""
    from concurrent.futures.process import BrokenProcessPool
    jobs_u = [_job(toy_tier, "full_state", "random", 1, tag="u"), _job(toy_tier, "true_state", "fixed", 1, tag="u")]
    jobs_p = [_job(toy_tier, "full_state", "random", 1, tag="p"), _job(toy_tier, "true_state", "fixed", 1, tag="p")]
    try:
        with ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context("spawn"), initializer=AM.pool_init, initargs=(1,)) as ex:
            unpacked = [row for out in ex.map(_unpacked, jobs_u) for row in out["rows"]]
    except (BrokenProcessPool, MemoryError) as exc:
        pytest.fail(f"INFRASTRUCTURE failure on the unpacked side (not a row difference): {type(exc).__name__}: {exc}")
    res = AM.reference_pack_job({"loops": jobs_p, "workers": 2, "threads": 1, "mem_budget_gb": 64, "work_dir": str(tmp_path / "w")})
    assert not (tmp_path / "w").exists()                              # the pack's working directory is removed
    cmp = _driver().compare_rows(res["rows"], unpacked)
    loop_errors = [lp for lp in res["loops"] if "error" in lp]
    if loop_errors or cmp["infrastructure"] or cmp["missing"]:
        pytest.fail("INFRASTRUCTURE failure (not a row difference): "
                    f"loop errors {loop_errors}; failed rows {cmp['infrastructure']}; missing rows {cmp['missing']}; "
                    f"crash retries {res['pack']['crash_retries']}; the {cmp['n_identical']} rows that completed on both sides are "
                    f"{'identical' if not cmp['diffs'] else 'DIFFERENT: ' + str(cmp['diffs'])}")
    assert not cmp["diffs"], f"VALUE DIFFERENCE between packed and unpacked rows: {cmp['diffs']}"
    assert cmp["bit_identical"] and cmp["n_rows"] == 4, cmp
    for r in res["rows"]:
        assert r["fit_wall_s"] > 0 and r["task_wall_s"] >= r["fit_wall_s"] and "error" not in r


def test_a_shared_stream_gives_both_learners_the_unpacked_rows(toy_tier, tmp_path):
    """FULL-STATE and TRUE-STATE loops of ONE data stream (same system, designer and seed): the pack runs phase 1 once (capturing the
    true states) and both learners' rows equal their unpacked loops bit for bit."""
    jobs_u = [_job(toy_tier, "full_state", "random", 3, tag="su"), _job(toy_tier, "true_state", "random", 3, tag="su")]
    jobs_p = [_job(toy_tier, "full_state", "random", 3, tag="sp"), _job(toy_tier, "true_state", "random", 3, tag="sp")]
    assert AM.stream_id(jobs_p[0]) == AM.stream_id(jobs_p[1])
    with ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context("spawn"), initializer=AM.pool_init, initargs=(1,)) as ex:
        unpacked = [row for out in ex.map(_unpacked, jobs_u) for row in out["rows"]]
    res = AM.reference_pack_job({"loops": jobs_p, "workers": 2, "threads": 1, "mem_budget_gb": 64, "work_dir": str(tmp_path / "w")})
    assert res["pack"]["n_streams_run"] == 1 and len(res["pack"]["phase1_wall_s"]) == 1
    cmp = _driver().compare_rows(res["rows"], unpacked)
    assert cmp["bit_identical"] and cmp["n_rows"] == 4, cmp


def test_a_shorter_budget_reproduces_the_first_checkpoints(toy_tier, tmp_path):
    """The in-run verification of scripts/p4/active_mde.py runs its sample loops unpacked at a SHORTER budget: the random and fixed
    designers ignore the remaining budget, so the shorter loop's checkpoint rows equal the packed full-budget loop's rows at the same
    checkpoints bit for bit."""
    short = dict(_job(toy_tier, "true_state", "random", 5, tag="bs"), budget=2, checkpoints=[2])
    full = _job(toy_tier, "true_state", "random", 5, tag="bf")                      # budget 4, checkpoints 2 and 4
    with ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context("spawn"), initializer=AM.pool_init, initargs=(1,)) as ex:
        unpacked = next(iter(ex.map(_unpacked, [short])))["rows"]
    res = AM.reference_pack_job({"loops": [full], "workers": 2, "threads": 1, "mem_budget_gb": 64, "work_dir": str(tmp_path / "w")})
    cmp = _driver().compare_rows([r for r in res["rows"] if r["budget"] <= 2], unpacked)
    assert cmp["bit_identical"] and cmp["n_rows"] == 1, cmp


def test_a_restarted_pack_resumes_from_its_progress_store(toy_tier, tmp_path):
    """A pack re-run with the same progress store (Modal re-runs a preempted input) returns the stored rows and runs nothing again."""
    jobs = [_job(toy_tier, "full_state", "fixed", 4, tag="r")]
    spec = {"dir": str(tmp_path / "progress"), "run": "r1"}
    first = AM.reference_pack_job({"loops": jobs, "workers": 2, "threads": 1, "mem_budget_gb": 64, "work_dir": str(tmp_path / "w1"),
                                   "progress": spec})
    assert first["pack"]["progress"] == "dir" and first["pack"]["n_resumed_rows"] == 0 and len(first["rows"]) == 2
    again = AM.reference_pack_job({"loops": jobs, "workers": 2, "threads": 1, "mem_budget_gb": 64, "work_dir": str(tmp_path / "w2"),
                                   "progress": spec})
    assert again["pack"]["n_resumed_rows"] == 2 and again["pack"]["n_streams_run"] == 0 and all(r["resumed"] for r in again["rows"])
    cmp = _driver().compare_rows(again["rows"], first["rows"])
    assert cmp["bit_identical"], cmp
    other = AM.reference_pack_job({"loops": jobs, "workers": 2, "threads": 1, "mem_budget_gb": 64, "work_dir": str(tmp_path / "w3"),
                                   "progress": {**spec, "run": "r2"}})             # another run id: nothing to resume
    assert other["pack"]["n_resumed_rows"] == 0 and other["pack"]["n_streams_run"] == 1


def test_pack_retries_a_crashed_worker_once(toy_tier, tmp_path):
    once = dict(_job(toy_tier, "full_state", "random", 2, tag="c1"), crash_for_test={"2": 1})    # dies on attempt 0 only
    twice = dict(_job(toy_tier, "full_state", "fixed", 2, tag="c2"), crash_for_test={"4": 2})    # dies on both attempts
    res = AM.reference_pack_job({"loops": [once, twice], "workers": 2, "threads": 1, "mem_budget_gb": 64, "work_dir": str(tmp_path / "w")})
    by = {(r["designer"], r["budget"]): r for r in res["rows"]}
    assert len(by) == 4 and res["pack"]["crash_retries"] >= 1
    assert "error" not in by[("random", 2)] and np.isfinite(by[("random", 2)]["EE"])
    assert "crashed twice" in by[("fixed", 4)]["error"] and not np.isfinite(by[("fixed", 4)]["EE"])


def test_schedule_respects_the_memory_budget_and_order():
    """A simulated clock: tasks finish after pred_s; the running tasks' predicted memory never exceeds the budget (a task larger
    than the budget runs alone), the longest task starts first, and every task completes once."""
    tasks = [{"id": i, "pred_s": s, "pred_gb": g} for i, (s, g) in enumerate([(50, 6), (40, 6), (40, 2), (30, 9), (20, 1), (10, 1), (5, 12)])]
    clock = {"t": 0.0}
    live: dict = {}
    starts, peak = [], [0.0]

    def submit(t):
        h = object()
        live[h] = (clock["t"] + t["pred_s"], t)
        starts.append(t["id"])
        mem = sum(x["pred_gb"] for _e, x in live.values())
        assert mem <= 10 or len(live) == 1
        peak[0] = max(peak[0], mem)
        return h

    def wait_any(handles):
        h = min(handles, key=lambda k: live[k][0])
        clock["t"] = live[h][0]
        del live[h]
        return [h], {h: "ok"}
    done, left = AM.schedule(tasks, submit, wait_any, slots=3, mem_budget_gb=10)
    assert starts[0] == 0 and not left and sorted(t["id"] for t, _ in done) == list(range(7)) and peak[0] <= 12


def test_schedule_stops_submitting_after_a_fatal_result():
    tasks = [{"id": i, "pred_s": 10 - i, "pred_gb": 1} for i in range(5)]
    subs = []

    def submit(t):
        subs.append(t["id"])
        return t["id"]

    def wait_any(handles):
        h = handles[0]
        return [h], {h: "boom" if h == 0 else "ok"}
    done, left = AM.schedule(tasks, submit, wait_any, slots=2, mem_budget_gb=100, is_fatal=lambda r: r == "boom")
    assert subs == [0, 1] and [t["id"] for t in left] == [2, 3, 4] and {t["id"] for t, _ in done} == {0, 1}


def _rows(n_sys=6, drop=None):
    rng = np.random.default_rng(0)
    rows = []
    for s in range(n_sys):
        base = 1.0 + 0.2 * s
        for d in ("random", "fixed"):
            for sd in range(3):
                if drop == (f"s{s}", d, sd):
                    continue
                off = rng.normal(0, 0.02)
                for b in (10, 25, 50, 100, 200):
                    rows.append({"system": f"s{s}", "learner": "full_state", "designer": d, "loop_seed": sd, "budget": b,
                                 "EE": float(base / np.log(b) + off + rng.normal(0, 0.01))})
    return rows


def test_summarize_reports_rules_nulls_exclusions_and_is_process_independent():
    rows = _rows(drop=("s5", "fixed", 1))                                # a missing benchmark loop: s5 is excluded
    kw = {"n_sim": 8, "n_boot": 50, "efficiencies": (1.0, 3.0), "null_fixed_offsets": (0.05, 0.1), "chunk": 4}
    a = AM.summarize(rows, workers=1, **kw)
    b = AM.summarize(rows, workers=2, **kw)
    assert a["per_learner"] == b["per_learner"]                          # chunk seeds do not depend on the process layout
    m = a["per_learner"]["full_state"]
    assert set(m["mde"]["mde"]) == {"fixed_budget", "budget_ratio", "either"}
    assert m["mde"]["false_positive_rate"] is not None and set(m["mde"]["false_positive_rate_weaker_fixed"]) == {"0.05", "0.1"}
    assert m["mde"]["n_systems"] == 5 and m["mde"]["n_excluded_systems"] == 1 and "s5" in m["excluded"]
    assert "sd_offset" in m["mde"]["noise_medians"] and "seeding" in m["mde"] and a["chunk"] == 4


def test_summary_chunks_merge_exactly_and_spread_over_containers():
    """The specs split over two 'containers' merge into the same summary as one process; a scenario's merged rate is the
    size-weighted mean of its chunks' rates (so 2 chunks of 4 = the rate over all 8 simulated suites)."""
    rows = _rows()
    kw = {"n_sim": 8, "n_boot": 50, "efficiencies": (1.0, 2.0), "null_fixed_offsets": (0.1,)}
    specs = AM.summary_specs(rows, chunk=4, **kw)
    assert len(specs) == 3 * 2 and len({sp["kw"]["seed"] for sp in specs}) == len(specs)
    parts = {**AM.summary_parts(rows, specs[0::2]), **AM.summary_parts(rows, specs[1::2])}
    merged = AM.summarize_from_parts(rows, specs, parts, **kw)
    assert merged["per_learner"] == AM.summarize(rows, chunk=4, **kw)["per_learner"]
    e1 = [sp for sp in specs if sp["kind"] == "e" and sp["value"] == 1.0]
    rates = [parts[sp["id"]]["table"][1.0]["either"] for sp in e1]
    assert merged["per_learner"]["full_state"]["mde"]["table"]["1.0"]["either"] == pytest.approx(sum(rates) / 2)


def test_planner_balances_containers_and_detects_row_differences():
    D = _driver()
    info_big = {"observed": list(range(200)), "t_end_default": 2.0, "dt": 0.001}
    info_small = {"observed": list(range(10)), "t_end_default": 2.0, "dt": 0.002}
    jobs = [D.loop_job(f"s{i}", ln, "random", 0, 200, 4, info_big if i < 2 else info_small) for i in range(8)
            for ln in ("full_state", "true_state")]
    packs = D.plan_packs(jobs, 4, 8)
    assert len(packs) == 4 and sorted(AM.loop_id(j) for p in packs for j in p) == sorted(AM.loop_id(j) for j in jobs)
    loads = [sum(D.pred_task_s(j) * len(j["checkpoints"]) for j in p) for p in packs]
    assert max(loads) - min(loads) <= max(D.pred_task_s(j) * 5 for j in jobs)
    lpt = D.predicted_makespan(packs, 8)
    assert lpt > 0 and lpt <= D.predicted_makespan([jobs], 8)             # four containers beat one
    one = [j for j in jobs if j["sid"] == "s0"]
    assert D.pack_makespan(one, 8) >= D.phase1_s(one[0]) + D.pred_task_s(one[0])   # phase 1 releases the tasks
    r = {"system": "s0", "learner": "full_state", "designer": "random", "loop_seed": 0, "budget": 10, "EE": 1.0}
    assert D.compare_rows([r], [dict(r)])["bit_identical"]
    assert not D.compare_rows([r], [dict(r, EE=1.0 + 1e-15)])["bit_identical"]
    assert not D.compare_rows([r], [])["bit_identical"]
    # an infrastructure failure (an error row: a killed worker, crash retries exhausted) is never reported as a value difference
    c = D.compare_rows([dict(r, EE=float("nan"), error="worker process crashed twice (memory?)")], [dict(r)])
    assert not c["bit_identical"] and c["verdict"] == "infrastructure failure" and not c["diffs"] and len(c["infrastructure"]) == 1
    c = D.compare_rows([r], [])
    assert c["verdict"] == "missing rows" and not c["diffs"] and c["missing"][0]["missing"] == "unpacked"
    c = D.compare_rows([r], [dict(r, EE=1.0 + 1e-15)])
    assert c["verdict"] == "value difference" and c["diffs"] and not c["infrastructure"]
