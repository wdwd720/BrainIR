"""The synthetic generator at the reference numerics and the restart-source check (LOG P4-D50).

A validation system's evaluation refused every lift: the evaluation process ran 2-4 BLAS threads, the generator then constructed the
system with another content hash, and the restarts from the lift cases' stored records failed the same-system check. Now:
- `synthadapter.suite_systems` constructs every generator system with ONE BLAS thread and wraps it (`SingleThreadedSystem`) so that
  every later call runs with one thread too, whatever the caller's thread settings;
- `suites.SimContext` refuses a process whose recomputed content hash differs from the system's record;
- the builder checks every restart source of a part (rows' restarts, lift cases, pool states, truth-equivalent carriers) against the
  store (`suites.restart_source_problems`) and stops on a foreign or incomplete record.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import textwrap

import numpy as np
import pytest
from test_suites_review_fixes import TINY
from threadpoolctl import threadpool_info, threadpool_limits

from brainir_causal import suites as S
from brainir_causal import synthadapter as SA
from brainir_causal.store import TrajectoryStore

FAKE = textwrap.dedent('''
    """A fake generator package: records the BLAS thread count of the process at construction and in a method."""
    from threadpoolctl import threadpool_info

    def _threads():
        n = [d.get("num_threads") for d in threadpool_info() if d.get("user_api") == "blas"]
        return max(n) if n else None

    class FakeSystem:
        engine_id = "fake-1"

        def __init__(self, sid):
            self.system_id = sid
            self.built_with = _threads()

        def content_hash(self):
            return f"h-{self.system_id}-{self.built_with}"

        def threads_now(self):
            return _threads()

    def build_suite(tier, seed, n_per_type=None):
        return {f"syn-{tier}-{j}": FakeSystem(f"syn-{tier}-{j}") for j in range(2)}
''')


def _blas_available() -> bool:
    return any(d.get("user_api") == "blas" for d in threadpool_info())


@pytest.fixture()
def fake_generator(tmp_path):
    pkg = tmp_path / "gen" / "p4synth_fake"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(FAKE, encoding="utf-8")
    SA.register_generator(tmp_path / "gen", "p4synth_fake", name="fake")
    yield "fake"
    SA._GENERATORS.pop("fake", None)
    SA.suite_systems.cache_clear()


@pytest.mark.skipif(not _blas_available(), reason="no BLAS library visible to threadpoolctl")
def test_generator_systems_are_built_and_called_with_one_blas_thread(fake_generator):
    with threadpool_limits(4):                                   # the caller runs more threads (an evaluation job)
        systems = SA.suite_systems("dev", 1, fake_generator)
        s = systems["syn-dev-0"]
        assert isinstance(s, SA.SingleThreadedSystem)
        assert s.built_with == 1 and s.threads_now() == 1        # construction and every call at one thread
        assert s.content_hash() == "h-syn-dev-0-1" and s.engine_id == "fake-1" and s.system_id == "syn-dev-0"
        assert not hasattr(s, "draw_effective")                   # a missing truth method stays missing
        after = [d.get("num_threads") for d in threadpool_info() if d.get("user_api") == "blas"]
        assert max(after) > 1                                      # the caller's own setting is restored after each call
    s2 = pickle.loads(pickle.dumps(s))
    assert isinstance(s2, SA.SingleThreadedSystem) and s2.content_hash() == s.content_hash()


def test_simcontext_refuses_a_process_that_computes_another_content_hash(tmp_path):
    class Sys:
        engine_id = "e"

        def content_hash(self):
            return "a" * 64

    rec = {"system_id": "syn-x", "kind": "synthetic", "system_hash": "b" * 64}
    with pytest.raises(RuntimeError, match="reference numerics"):
        S.SimContext(rec, store_root=tmp_path / "store", synthetic_system=Sys())
    ok = S.SimContext(dict(rec, system_hash="a" * 64), store_root=tmp_path / "store", synthetic_system=Sys())
    assert ok.system_hash == "a" * 64


def _put(store: TrajectoryStore, key: str, sid: str, h: str, state: bool = True) -> None:
    rec = {"t": np.arange(3.0), "x": np.zeros((3, 2)), "u": np.zeros((3, 1)), "y": np.zeros((3, 1)),
           "info": {"system_id": sid, "system_hash": h}}
    if state:
        rec["state"] = np.zeros((3, 4))
    store.put(key, rec, {"system_id": sid})


def test_restart_source_problems_names_foreign_incomplete_and_missing_records(tmp_path):
    st = TrajectoryStore(tmp_path / "store")
    _put(st, "a" * 64, "syn-1", "H1")
    _put(st, "b" * 64, "syn-2", "H2")                               # another system
    _put(st, "c" * 64, "syn-1", "H9")                               # this system's id, another content hash
    _put(st, "d" * 64, "syn-1", "H1", state=False)                 # no full state
    bad = S.restart_source_problems(tmp_path / "store", "syn-1", "H1", ["a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64, "a" * 64],
                                    need_state=True)
    assert {b[:12] for b in bad} == {"b" * 12, "c" * 12, "d" * 12, "e" * 12}           # the foreign record fails on id and hash
    assert any("syn-2" in b for b in bad) and any("system hash" in b for b in bad)
    assert any("full state" in b for b in bad) and any("not in the store" in b for b in bad)
    assert S.restart_source_problems(tmp_path / "store", "syn-1", "H1", ["a" * 64], need_state=True) == []


def test_the_build_stops_on_a_lift_case_that_restarts_from_another_systems_record(tmp_path, monkeypatch):
    salt = "ab" * 32
    (tmp_path / "salt.txt").write_text(salt, encoding="utf-8")
    (tmp_path / "commit.json").write_text(json.dumps({"sha256_of_salt": hashlib.sha256(salt.encode()).hexdigest()}), encoding="utf-8")
    for k, v in TINY.items():
        monkeypatch.setattr(S, k, v)
    monkeypatch.setattr(S, "SALT_FILE", tmp_path / "salt.txt")
    monkeypatch.setattr(S, "COMMITMENT", tmp_path / "commit.json")
    foreign = "f" * 64
    _put(TrajectoryStore(tmp_path / "store"), foreign, "syn:toy:1", "another-hash")
    real_pick = S.pick_lift_cases

    def pick(src, rng):
        cases = real_pick(src, rng)
        return cases[:-1] + [dict(cases[-1], store_key=foreign)]
    monkeypatch.setattr(S, "pick_lift_cases", pick)
    with pytest.raises(RuntimeError, match="restart sources are not records of this system"):
        S.build_tier("toy", workers=1, systems=["syn:toy:0"], root=tmp_path / "suites", store_root=tmp_path / "store",
                     parts=S.TIER_PARTS["toy"][:1])


# ------------------------------------------------------------------------------------------------ review G's trap tier
CATALOG = textwrap.dedent('''
    """A fake review G catalog: relative imports resolve against the registered generator package."""
    from . import FakeSystem

    def review_g_catalog(seed):
        return [FakeSystem(f"trap-G-{c}-{seed % 7}") for c in "AB"]
''')


def test_the_trap_tier_loads_review_gs_catalog_outside_the_generator(fake_generator, tmp_path, monkeypatch):
    cat = tmp_path / "review_g" / "review_g.py"
    cat.parent.mkdir()
    cat.write_text(CATALOG, encoding="utf-8")
    monkeypatch.setenv("P4_TRAP_CATALOG", str(cat))
    import sys
    sys.modules.pop("p4synth_fake.review_g", None)
    systems = SA.suite_systems(SA.TRAP_TIER, 12, fake_generator)
    assert sorted(systems) == ["trap-G-A-5", "trap-G-B-5"]
    assert all(isinstance(s, SA.SingleThreadedSystem) for s in systems.values())
    assert systems["trap-G-A-5"].engine_id == "fake-1"


def test_the_trap_tier_is_salted_hidden_and_locked(tmp_path, monkeypatch):
    salt = "cd" * 32
    (tmp_path / "salt.txt").write_text(salt, encoding="utf-8")
    (tmp_path / "commit.json").write_text(json.dumps({"sha256_of_salt": hashlib.sha256(salt.encode()).hexdigest()}), encoding="utf-8")
    monkeypatch.setattr(S, "SALT_FILE", tmp_path / "salt.txt")
    monkeypatch.setattr(S, "COMMITMENT", tmp_path / "commit.json")
    monkeypatch.setattr(S, "METHOD_LOCK", tmp_path / "METHOD_LOCK.json")          # no lock
    assert "trap" in S.HIDDEN_TIERS and "trap" in S.SALTED_TIERS and S.LEVEL_OF_TIER["trap"] == "C"
    assert S.tier_seed("trap") != S.tier_seed("conf") and S.tier_seed("trap") != S.DEV_SEED
    with pytest.raises(PermissionError):
        S.build_tier("trap", workers=1, root=tmp_path / "suites", store_root=tmp_path / "store")
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("p4post_common_under_test",
                                                  Path(__file__).resolve().parents[2] / "scripts" / "p4" / "p4post" / "common.py")
    C = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(C)
    assert C.is_hidden("trap", None)
    monkeypatch.setattr(C.SU, "METHOD_LOCK", tmp_path / "METHOD_LOCK.json")
    with pytest.raises(PermissionError):
        C.guard("trap", None, what="a trap-tier study")                           # refused before the lock
