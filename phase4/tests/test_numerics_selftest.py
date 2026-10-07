"""The container-start NUMERICS SELF-TEST (p4modal.selftest, p4modal.gate.numerics_selftest; research/phase4/LEVEL_B_EXECUTION.md
section 9): the verdict rules, the container callable's refusal on a mismatch (stop_fetching_inputs, host fingerprint and the
mismatching items recorded), once per container, a stale reference as an infrastructure fault, the Backend's bounds on self-test
refusals, and the checked-in reference against its builder."""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
import time
from pathlib import Path

import pytest

from brainir_causal.p4modal import gate as G
from brainir_causal.p4modal import selftest as S

ROOT = Path(__file__).resolve().parents[2]
ADMISSIBLE = {"model": "unknown", "vendor": "AuthenticAMD", "avx512f": False, "avx2": True, "fma": True}
AVX512 = {"model": "unknown", "vendor": "AuthenticAMD", "avx512f": True, "avx2": True, "fma": True}


def _ref(**kw) -> dict:
    ref = {"battery_id": "b1", "versions": {"python": "3.12.10", "numpy": "2.5.3", "scipy": "1.18.1", "torch": "2.14.0+cpu"},
           "items": {k: f"h-{k}" for k in S.item_names()}, "reference_hosts": [{"class": "AuthenticAMD/fam25/model1/avx2", "containers": 3}]}
    ref.update(kw)
    return ref


def _run(ref: dict, **kw) -> dict:
    run = {"battery_id": ref["battery_id"], "versions": dict(ref["versions"]), "items": dict(ref["items"]), "absent": [], "errors": {},
           "s": 1.0, "wall_s": 1.5}
    run.update(kw)
    return run


# ---------------------------------------------------------------- the verdict
def test_compare_rules():
    ref = _ref()
    assert S.compare(_run(ref), ref) == {"ok": True, "stale": None, "mismatch": [], "errors": {}}
    bad = _run(ref, items=dict(ref["items"], **{"numpy/blas/t3": "other"}))
    v = S.compare(bad, ref)
    assert not v["ok"] and v["mismatch"] == ["numpy/blas/t3"] and not v["stale"]
    # a failing item or part is never a pass
    assert not S.compare(_run(ref, errors={"part:torch": "exit -11"}), ref)["ok"]
    missing = _run(ref, items={k: v for k, v in ref["items"].items() if k != "engine"})
    assert S.compare(missing, ref)["mismatch"] == ["engine"]
    # only an OPTIONAL item may be absent (the generator where it is not baked)
    no_gen = _run(ref, items={k: v for k, v in ref["items"].items() if k != "generator"}, absent=["generator"])
    assert S.compare(no_gen, ref)["ok"]
    no_engine = _run(ref, items={k: v for k, v in ref["items"].items() if k != "engine"}, absent=["engine"])
    assert S.compare(no_engine, ref)["mismatch"] == ["engine"]
    assert S.compare(_run(ref, items=dict(ref["items"], extra="x")), ref)["mismatch"] == ["extra"]
    # stale: another battery or another library stack is a configuration fault, never a host verdict
    assert S.compare(_run(ref, battery_id="b2"), ref)["stale"]
    assert S.compare(_run(ref, versions=dict(ref["versions"], numpy="2.5.4")), ref)["stale"]
    # the base image's python patch release may move (the compiled libraries are the pinned wheels)
    assert S.compare(_run(ref, versions=dict(ref["versions"], python="3.12.11")), ref)["ok"]
    assert S.compare(_run(ref, versions=dict(ref["versions"], python="3.13.1")), ref)["stale"]


def test_item_names_are_the_battery():
    names = S.item_names()
    assert len(names) == len(set(names)) == 3 + 3 * len(S.THREADS)
    assert {f"torch/t{t}" for t in S.THREADS} <= set(names) and set(S.OPTIONAL) <= set(names)
    assert S.THREADS == (1, 2, 3, 4)             # the job kinds' thread counts (simulation 1, calibration 2, fits / drivers 3, references 4)


def test_a_crashed_part_is_recorded_as_an_error(monkeypatch):
    import subprocess

    class _Proc:
        def __init__(self, cmd, **kw):
            self.part = cmd[-1]
            self.returncode = -11 if self.part == "torch" else 0
            kw["stderr"].write(b"Fatal Python error: Segmentation fault" if self.part == "torch" else b"")

        def communicate(self, timeout=None):
            if self.part == "torch":
                return "", None
            return json.dumps({"battery_id": "b1", "versions": {"python": "3.12.10"}, "items": {f"{self.part}-item": "h"},
                               "absent": [], "errors": {}, "s": 0.5}) + "\n", None

        def kill(self):
            pass
    monkeypatch.setattr(subprocess, "Popen", _Proc)
    run = S.run_battery(5.0)
    assert set(run["items"]) == {"main-item", "engine-item"} and "Segmentation fault" in run["errors"]["part:torch"]
    assert not S.compare(run, _ref(battery_id="b1"))["ok"]


# ---------------------------------------------------------------- the container callable
class _Env:
    """A container: the host, the reference and the battery's result are faked; counts the battery runs, the stop_fetching_inputs
    calls and the dispatched jobs."""

    def __init__(self, monkeypatch, host=ADMISSIBLE, ref=None, run=None, ref_error=None, battery_s=0.0):
        import types

        import modal

        from brainir_causal.p4modal import remote
        self.ref = ref if ref is not None else _ref()
        self.run_rec = run if run is not None else _run(self.ref)
        self.n_battery, self.n_stop, self.jobs = 0, 0, []
        monkeypatch.setattr(G, "_SELFTEST", None)
        monkeypatch.setattr(G, "host_cpu", lambda cpuinfo=None: dict(host))
        monkeypatch.setattr(G, "host_class", lambda cpuinfo=None: {"key": "AuthenticAMD/fam25/model99/avx2"})
        monkeypatch.setattr(G, "host_fingerprint", lambda: {"cpu": dict(host), "numpy": "2.5.3"})

        def load_reference(path=None):
            if ref_error is not None:
                raise ref_error
            return self.ref

        def run_battery(timeout_s=180.0, python=None):
            self.n_battery += 1
            time.sleep(battery_s)
            return self.run_rec

        def stop():
            self.n_stop += 1

        def dispatch(p):
            self.jobs.append(p)
            return {"ok": True}
        monkeypatch.setattr(S, "load_reference", load_reference)
        monkeypatch.setattr(S, "run_battery", run_battery)
        # a fake modal.experimental, never the real one (importing it would bind it on the package for later tests' fakes)
        fake = types.SimpleNamespace(stop_fetching_inputs=stop)
        monkeypatch.setitem(sys.modules, "modal.experimental", fake)
        monkeypatch.setattr(modal, "experimental", fake, raising=False)
        monkeypatch.setattr(remote, "dispatch", dispatch)


def _job(gated=True, slots=0):
    from brainir_causal.p4modal import app as A
    return A._container_callable(gated, slots)


def test_a_faked_mismatch_refuses_the_host_like_the_flag_gate(monkeypatch):
    ref = _ref()
    env = _Env(monkeypatch, ref=ref, run=_run(ref, items=dict(ref["items"], **{"torch/t3": "zen9"})))
    job = _job()
    r = job({"kind": "call", "__tag": 7})
    assert G.is_refusal(r) and r["__tag"] == 7 and r["host"] == ADMISSIBLE
    st = r["selftest"]
    assert st["mismatch"] == ["torch/t3"] and st["fingerprint"]["cpu"] == ADMISSIBLE and st["host_class"].endswith("/avx2")
    assert env.n_stop == 1 and env.jobs == []                  # the container stops fetching inputs; the job never runs here
    r2 = job({"kind": "call", "__tag": 8})                      # a later input of the same container: the cached verdict
    assert G.is_refusal(r2) and r2["selftest"]["mismatch"] == ["torch/t3"] and env.n_battery == 1 and env.jobs == []


def test_a_passing_host_runs_the_job_and_the_battery_once_per_container(monkeypatch):
    env = _Env(monkeypatch)
    job = _job()
    r1, r2 = job({"kind": "call", "__tag": 1}), job({"kind": "call", "__tag": 2})
    assert r1["ok"] and r2["ok"] and len(env.jobs) == 2 and env.n_battery == 1 and env.n_stop == 0
    assert r1["__selftest"]["ok"] and r1["__selftest"]["cached"] is False and r2["__selftest"]["cached"] is True
    assert r1["__selftest"]["reference_class"] is False          # a class the reference was not built on passes on its numerics


def test_packed_inputs_wait_for_one_battery(monkeypatch):
    env = _Env(monkeypatch, battery_s=0.3)
    job = _job(slots=8)
    out = []
    ths = [threading.Thread(target=lambda k=k: out.append(job({"kind": "call", "__tag": k}))) for k in range(8)]
    for th in ths:
        th.start()
    for th in ths:
        th.join()
    assert env.n_battery == 1 and len(env.jobs) == 8 and sum(r["__selftest"]["cached"] is False for r in out) == 1


@pytest.mark.parametrize("case", ["battery", "versions", "missing"])
def test_a_stale_or_missing_reference_is_an_infrastructure_fault(monkeypatch, case):
    ref = _ref()
    if case == "battery":
        env = _Env(monkeypatch, ref=ref, run=_run(ref, battery_id="another"))
    elif case == "versions":
        env = _Env(monkeypatch, ref=ref, run=_run(ref, versions=dict(ref["versions"], torch="2.15.0+cpu")))
    else:
        env = _Env(monkeypatch, ref_error=FileNotFoundError("numerics_reference.json"))
    r = _job()({"kind": "call", "__tag": 3})
    assert r.get("__infra__") and "InfraFault (numerics reference)" in r["error"] and not G.is_refusal(r)
    assert env.n_stop == 0 and env.jobs == []
    from brainir_causal.p4modal import app as A  # noqa: F401 - the tournament's rule: an __infra__ result is never charged
    sys.path.insert(0, str(ROOT / "scripts" / "p4"))
    try:
        spec = importlib.util.spec_from_file_location("p4_tournament_for_selftest", ROOT / "scripts" / "p4" / "tournament.py")
        T = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(T)
    finally:
        sys.path.pop(0)
    assert T.infra_failure(r) and T.infra_failure(RuntimeError("InfraFault (numerics self-test): input refused by it on 8 containers"))


def test_the_flag_gate_refuses_first_and_ungated_classes_skip_the_battery(monkeypatch):
    env = _Env(monkeypatch, host=AVX512)
    r = _job()({"kind": "call", "__tag": 1})
    assert G.is_refusal(r) and "selftest" not in r and env.n_battery == 0
    env = _Env(monkeypatch, host=AVX512)
    r = _job(gated=False)({"kind": "call", "__tag": 1})
    assert r["ok"] and "__selftest" not in r and env.n_battery == 0
    env = _Env(monkeypatch)
    r = _job()({"kind": "call", "__tag": 1, "ungated": True})
    assert r["ok"] and env.n_battery == 0


# ---------------------------------------------------------------- the Backend's bounds
def _backend():
    from brainir_causal.p4modal.app import Backend
    be = Backend.__new__(Backend)
    be.verbose = False
    be.costs, be.refusals, be.hosts, be.app_id = [], {}, {}, None
    return be


class _Fn:
    """Every input is refused by the self-test, except those in `passing` (a fresh container that passed)."""

    def __init__(self, passing=()):
        self.n = 0
        self.passing = set(passing)
        self.lock = threading.Lock()

    def map(self, batch, order_outputs=False, return_exceptions=True):
        for p in batch:
            with self.lock:
                self.n += 1
            if p.get("i") in self.passing:
                yield {"ok": True, "__tag": p["__tag"], "__selftest": {"ok": True, "cached": False}}
            else:
                yield {"__refused__": True, "__tag": p["__tag"], "host": ADMISSIBLE,
                       "selftest": {"mismatch": ["numpy/blas/t4"], "errors": {}, "host_class": "AuthenticAMD/fam26/model2/avx2"}}

    def remote(self, p):
        raise AssertionError("never one call per input")

    def spawn(self, p):
        raise AssertionError("never the async path")


def test_backend_gives_up_an_input_the_selftest_refuses_repeatedly(monkeypatch):
    from brainir_causal.p4modal import app as A
    be = _backend()
    fn = _Fn(passing={1})
    be.fns = {"fit_s": fn}
    monkeypatch.setattr(be, "_cost", lambda *a, **k: None)
    res = A.Backend.run(be, [{"i": 0}, {"i": 1}], "fit_s", poll_s=0.01, batch_s=0.01)
    assert isinstance(res[0], RuntimeError) and "InfraFault (numerics self-test)" in str(res[0]) and "fam26" in str(res[0])
    assert res[1]["ok"] and fn.n == A.MAX_SELFTEST_REFUSALS + 1
    summary = be.cost_summary()
    assert summary["selftest_counts"]["fit_s"] == {"passed": 1, "refused": A.MAX_SELFTEST_REFUSALS}
    assert summary["selftest_refusals"][0]["mismatch"] == ["numpy/blas/t4"] and summary["selftest_refusals"][0]["cls"] == "fit_s"


def test_backend_breaker_stops_a_systematic_selftest_failure(monkeypatch):
    from brainir_causal.p4modal import app as A
    be = _backend()
    fn = _Fn()
    be.fns = {"fit_s": fn}
    monkeypatch.setattr(be, "_cost", lambda *a, **k: None)
    n = 3 * A.SELFTEST_BREAKER
    res = A.Backend.run(be, [{"i": i} for i in range(n)], "fit_s", poll_s=0.01, batch_s=0.01)
    assert all(isinstance(r, RuntimeError) and "systematic" in str(r) for r in res)
    assert fn.n == n                          # the first wave only: nothing is re-submitted once the breaker has tripped
    assert be.selftest_counts["fit_s"]["passed"] == 0


# ---------------------------------------------------------------- the checked-in reference and its builder
def _builder():
    spec = importlib.util.spec_from_file_location("p4_build_numerics_reference", ROOT / "scripts" / "p4" / "build_numerics_reference.py")
    B = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(B)
    return B


def test_the_reference_matches_its_builder():
    from brainir_causal.p4modal import images
    ref = S.load_reference()
    assert ref["battery_id"] == S.battery_id(), "the battery changed: rebuild the reference (scripts/p4/build_numerics_reference.py)"
    assert sorted(ref["items"]) == sorted(S.item_names())
    pinned = dict(p.split("==") for p in images.PINNED)
    v = ref["versions"]
    assert v["numpy"] == pinned["numpy"] and v["scipy"] == pinned["scipy"] and v["torch"] == images.TORCH.split("==")[1] + "+cpu"
    assert S.stack(v)["python"] == G.REFERENCE_STACK["python"]
    assert ref["reference_hosts"] and all(h["class"].endswith("/avx2") and h["containers"] > 0 for h in ref["reference_hosts"])
    assert ref["built"]["builder"] == "scripts/p4/build_numerics_reference.py" and ref["built"]["containers_admissible"] >= 30
    # the builder, applied to the recorded probe (its report's rows), writes exactly the checked-in file
    B = _builder()
    rec = json.loads((ROOT / ref["built"]["report"]).read_text(encoding="utf-8"))
    rebuilt, _ = B.build(rec["rows"], rec["meta"])
    # ... then the recorded single-item re-references (scripts/p4/rereference_generator_item.py, LOG P4-D71), in order, each
    # replacing exactly the value it names as old, and only the generator item (the only item that depends on benchmark code)
    for e in ref.get("rereferenced", []):
        assert e["item"] == "generator" and e["builder"] == "scripts/p4/rereference_generator_item.py"
        assert rebuilt["items"][e["item"]] == e["old"] and e["new"] != e["old"] and e["runs"] >= 3
        rebuilt["items"][e["item"]] = e["new"]
        rebuilt.setdefault("rereferenced", []).append(e)
    assert B.reference_text(rebuilt) == S.REFERENCE.read_text(encoding="utf-8")


def test_the_builder_refuses_disagreement_errors_and_thin_evidence():
    B = _builder()
    items = {k: f"h-{k}" for k in S.item_names()}
    ver = {"python": "3.12.10", "numpy": "2.5.3", "scipy": "1.18.1", "torch": "2.14.0+cpu"}

    def row(adm=True, it=None, errors=None, cls="AuthenticAMD/fam25/model1/avx2"):
        return {"shape": "full4", "class": cls if adm else "AuthenticAMD/fam25/model17/avx512", "admissible": adm, "items": it or items,
                "errors": errors or {}, "absent": [], "versions": ver, "battery_id": S.battery_id(), "wall_s": 4.0}
    meta = {"app_id": "ap-x", "utc": "2026-09-27T00:00:00Z", "shapes": {}}
    ok = [row() for _ in range(20)] + [row(cls="AuthenticAMD/fam23/model49/avx2") for _ in range(5)]
    avx512 = [row(adm=False, it=dict(items, **{"torch/t1": "other"}))]
    ref, rep = B.build(ok + avx512, meta)
    assert ref is not None and ref["items"] == items and ref["built"]["containers_admissible"] == 25
    assert {h["class"] for h in ref["reference_hosts"]} == {"AuthenticAMD/fam25/model1/avx2", "AuthenticAMD/fam23/model49/avx2"}
    assert rep["non_admissible"][0]["items_equal"] == len(items) - 1
    assert B.build(ok + [row(it=dict(items, engine="other"))], meta)[0] is None                 # admissible hosts disagree
    assert B.build(ok + [row(errors={"engine": "boom"})], meta)[0] is None                      # an admissible host failed an item
    assert B.build(ok[:10], meta)[0] is None                                                     # too few admissible containers
    no_gen = {k: v for k, v in items.items() if k != "generator"}
    assert B.build([row(it=no_gen) for _ in range(25)], meta)[0] is None                         # the generator must be baked
