"""Within-phase memory of a model worker (review F round 2, N-m3): a worker process keeps module state across the calls of a phase,
so a memorising model could look up a history's continuation in a LONGER history of the same trajectory it was given earlier. The
driver (`isolation.RemoteFresh`) sends such a call to a FRESH worker process; calls in increasing onset order never restart."""

from __future__ import annotations

import textwrap

import numpy as np
import pytest

from brainir_causal import isolation as I

# a MEMORISING method: its encoder counts the earlier histories (module state of the worker process) that contain this history's
# last row followed by more samples, i.e. the histories from which it could read this history's continuation
MEMO_METHOD = textwrap.dedent("""
    import numpy as np
    from brainir_causal.api import CausalStateMethod, CausalStateModel, register

    SEEN = []

    class Memo(CausalStateModel):
        def __init__(self):
            self.k = {"toy": 1}
        def encode(self, sid, x, u, dt):
            x = np.asarray(x, float)
            last = x[-1]
            hits = sum(1 for h in SEEN if any(np.array_equal(h[i], last) for i in range(len(h) - 1)))
            SEEN.append(x.copy())
            return np.array([float(hits)])
        def rollout(self, sid, z0, u_future, events, dt):
            n = len(u_future)
            return {"z": np.zeros((n, 1)), "y": np.zeros((n, 1))}
        def readout(self, sid, z, u):
            return np.zeros((np.atleast_2d(z).shape[0], 1))
        def info(self):
            return {"k": dict(self.k)}

    @register
    class MemoMethod(CausalStateMethod):
        name = "memo_method"
        def fit(self, data, *, systems, config=None, seed=0):
            return Memo()
""")


@pytest.fixture(scope="module")
def memo(tmp_path_factory):
    work = tmp_path_factory.mktemp("iso_memo")
    mdir = work / "methods"
    (mdir / "mm").mkdir(parents=True)
    (mdir / "__init__.py").write_text("", encoding="utf-8")
    (mdir / "mm" / "__init__.py").write_text("", encoding="utf-8")
    (mdir / "mm" / "memo_method.py").write_text(MEMO_METHOD, encoding="utf-8")        # a developer's own package (N-M2 layout)
    I.build_pubdir(work / "pub")
    tr = I.LocalUnsafeTransport(pubdir=work / "pub", method_dir=mdir)
    blob = I.fit_records(tr, method="memo_method", records=[], systems={"toy": {}}, config={})["model"]
    return tr, blob


def test_a_history_whose_continuation_the_worker_saw_goes_to_a_fresh_process(memo):
    tr, blob = memo
    rng = np.random.default_rng(3)
    long = rng.standard_normal((100, 3))
    short = long[:40].copy()                          # its continuation (rows 40-99) is inside `long`
    u = np.zeros((100, 1))
    rf = I.RemoteFresh(blob, tr, threads=1)
    try:
        assert rf.encode("toy", long, u, 0.01)[0] == 0
        assert rf.encode("toy", short, u[:40], 0.01)[0] == 0          # without the guard the worker would report 1 hit
        assert rf.n_restarts == 1
        assert rf.encode("toy", short, u[:40], 0.01)[0] == 0          # the same history again: no conflict, no restart
        other = rng.standard_normal((30, 3))
        assert rf.encode("toy", other, u[:30], 0.01)[0] == 0
        assert rf.n_restarts == 1
        rec = rf.record()
        assert rec["worker_restarts"] == 1 and rec["phases"]["A"]["restarts"] == 1 and rec["phases"]["A"]["n_calls"] == 4
    finally:
        rf.close()


def test_increasing_onsets_never_restart(memo):
    tr, blob = memo
    rng = np.random.default_rng(4)
    traj = rng.standard_normal((120, 2))
    u = np.zeros((120, 1))
    rf = I.RemoteFresh(blob, tr, threads=1)
    try:
        for t in (20, 50, 80, 119):
            assert rf.encode("toy", traj[:t], u[:t], 0.01)[0] == 0
        assert rf.n_restarts == 0
    finally:
        rf.close()


def test_a_restart_trajectory_starting_at_the_history_end_is_detected(memo):
    """A trajectory restarted from the history's last state begins with that state: the process that saw it may hold the
    continuation (e.g. a twin restarted from an item's onset state)."""
    tr, blob = memo
    rng = np.random.default_rng(5)
    hist = rng.standard_normal((50, 3))
    cont = np.vstack([hist[-1:], rng.standard_normal((30, 3))])
    u = np.zeros((60, 1))
    rf = I.RemoteFresh(blob, tr, threads=1)
    try:
        rf.encode("toy", cont, u[:31], 0.01)
        assert rf.encode("toy", hist, u[:50], 0.01)[0] == 0
        assert rf.n_restarts == 1
    finally:
        rf.close()


def test_every_last_row_is_tracked():
    """Review F round 3, N3-m2: no exemption (constant rows, histories that end where they started, one-row histories)."""
    whole, last, rows = I.history_digests(np.zeros((10, 4)))
    assert last is not None and len(rows) == 1                        # a constant (e.g. silent) row is tracked too
    whole2, last2, _ = I.history_digests(np.array([[1.0, 2.0], [3.0, 4.0], [1.0, 2.0]]))
    assert last2 is not None                                           # ends where it started: tracked
    _, last1, rows1 = I.history_digests(np.array([[1.0, 2.0]]))
    assert last1 is not None and rows1 == set()                        # a one-row history: its row is tracked, nothing follows it
    _, last3, rows3 = I.history_digests(np.array([[1.0, 2.0], [3.0, 5.0]]))
    assert last3 is not None and len(rows3) == 1 and whole != whole2
