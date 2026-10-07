"""The simulation service registers synthetic generators in EVERY worker process (a fresh spawned pool does not inherit the
parent's registry): a generator package outside the adapter is served through a real process pool."""

import textwrap

import numpy as np
import pytest

from brainir_causal import families as F
from brainir_causal.simservice import SimServer
from brainir_causal.synthadapter import ToySystem

FAKEGEN = textwrap.dedent('''
    """A stand-in synthetic generator (tests): the adapter's toy systems under another tier name."""
    from brainir_causal.synthadapter import ToySystem


    def build_suite(tier, seed, n_per_type=None):
        return {s.system_id: s for s in (ToySystem(int(seed), j) for j in range(2))}
''')


def _sysdef(gen_name: str) -> dict:
    rec = ToySystem(3, 0).public_record()
    rec.update({"tier": "fake", "suite_seed": 3, "generator": gen_name, "targets_public": [0, 1, 2], "edges_public": [[0, 1], [1, 0]],
                "split": F.rotation_split("R4", rec["capability"])})
    return rec


def _req():
    p = {"system": "syn:toy:0", "params_seed": 0, "t_end": 1.0, "dt": 0.01, "stimulus": [[0.0, 1.0]],
         "events": [{"kind": "kick", "t": 0.5, "delta": {"1": 0.5}}]}
    return {"agent": "a", "protocols": [p]}


@pytest.fixture()
def spawn_pools():
    """Worker pools start with 'spawn' on every platform (Windows' only start method). With 'fork' (Linux's default) a worker inherits
    the parent's generator registration, so these tests could not tell an initializer that registers the generator from one that does
    not."""
    import multiprocessing as mp
    prev = mp.get_start_method(allow_none=True)
    mp.set_start_method("spawn", force=True)
    try:
        yield mp.get_context("spawn")
    finally:
        mp.set_start_method(prev, force=True)


@pytest.fixture()
def fakegen(tmp_path):
    d = tmp_path / "gen"
    (d / "fakegen").mkdir(parents=True)
    (d / "fakegen" / "__init__.py").write_text(FAKEGEN, encoding="utf-8")
    return d


def test_generators_are_registered_in_every_worker(tmp_path, fakegen, spawn_pools):
    srv = SimServer(tmp_path / "room", {"syn:toy:0": _sysdef("g")}, tmp_path / "store", workers=2,
                    generators={"g": (str(fakegen), "fakegen")}, default_budget=100)
    try:
        arrays, meta = srv.handle_request(_req())
    finally:
        srv.pool.shutdown()
    item = meta["items"][0]
    assert item["ok"], item
    ref = ToySystem(3, 0).simulate({**_req()["protocols"][0], "params_spread": 1.0, "weight_noise": None, "process_noise": None,
                                    "r0": {"kind": "rest"}, "obs_noise": None}, full=False)
    assert np.allclose(arrays["i0_y"], np.asarray(ref["y"], np.float32))


def test_missing_generator_is_refused_at_construction(tmp_path):
    with pytest.raises(ValueError, match="need generators"):
        SimServer(tmp_path / "room", {"syn:toy:0": _sysdef("nowhere")}, tmp_path / "store", pool="inline")


def test_unregistered_worker_pool_fails_the_request(tmp_path, fakegen, spawn_pools):
    """What the fix prevents: a caller-supplied pool without the generator initializer cannot simulate synthetic systems."""
    from concurrent.futures import ProcessPoolExecutor
    pool = ProcessPoolExecutor(max_workers=1, mp_context=spawn_pools)
    srv = SimServer(tmp_path / "room", {"syn:toy:0": _sysdef("g")}, tmp_path / "store", pool=pool,
                    generators={"g": (str(fakegen), "fakegen")}, default_budget=100)
    try:
        _, meta = srv.handle_request(_req())
    finally:
        pool.shutdown()
    # the client sees a generic failure; the reason is logged outside the room (review F, minor 5)
    assert not meta["items"][0]["ok"] and meta["items"][0]["error"].startswith("simulation failed (reference ")
    assert "generator" in srv.errors_path.read_text(encoding="utf-8")
