"""The host-gated Modal execution of the frozen hidden-data generator (scripts/p3/hidden_gen_gate.py; LOG P3-D26): CPU flag parsing, the
gate's refusal on AVX-512 hosts, the re-submission of refused and failed inputs, the stop on a worker error, and that the frozen
run_modal really calls the replaceable module-level _modal_calls. Nothing contacts Modal."""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p3"))

CPU_AVX512 = """processor\t: 0
vendor_id\t: GenuineIntel
model name\t: Intel(R) Xeon(R) Platinum 8375C CPU @ 2.90GHz
flags\t\t: fpu sse sse2 avx avx2 fma avx512f avx512dq avx512bw
processor\t: 1
flags\t\t: fpu sse sse2 avx avx2 fma avx512f
"""
CPU_AVX2 = """processor\t: 0
vendor_id\t: AuthenticAMD
model name\t: AMD EPYC 7R13 Processor
flags\t\t: fpu sse sse2 avx avx2 fma bmi2
"""


def _gate():
    sys.modules.pop("hidden_gen_gate", None)
    return importlib.import_module("hidden_gen_gate")


def test_host_cpu_parses_model_vendor_and_flags():
    g = _gate()
    a = g.host_cpu(CPU_AVX512)
    assert a == {"model": "Intel(R) Xeon(R) Platinum 8375C CPU @ 2.90GHz", "vendor": "GenuineIntel", "avx512f": True, "avx2": True, "fma": True}
    b = g.host_cpu(CPU_AVX2)
    assert b["avx512f"] is False and b["avx2"] is True and b["vendor"] == "AuthenticAMD"
    assert g.host_cpu("")["avx512f"] is False


def test_gate_refuses_on_avx512_before_computing(monkeypatch):
    g = _gate()
    host = g.host_cpu(CPU_AVX512)
    monkeypatch.setattr(g, "host_cpu", lambda cpuinfo=None: host)
    r = g.gated("no_such_function", [], tag=7)          # refused before the (non-existent) target is looked up
    assert r == {"tag": 7, "refused": True, "host": host}


class _Call:
    def __init__(self, result):
        self.result = result

    def get(self, timeout=None):
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class _FakeFn:
    """map: odd inputs are refused on their first attempt and input 2 fails on Modal once; spawn: accepted."""

    def __init__(self):
        self.spawned = []

    @staticmethod
    def _accept(p):
        target, args, tag, mode = p["args"]
        assert mode == "refuse" and p["module"] == "hidden_gen_gate" and p["func"] == "gated" and p["kind"] == "call_commit"
        return {"result": {"tag": tag, "refused": False, "host": {"model": "m", "avx512f": False, "avx2": True}, "value": args[0] * 10},
                "container_wall_s": 1.0}

    def map(self, payloads, order_outputs=True, return_exceptions=False):
        for p in payloads:
            tag = p["args"][2]
            if tag % 2 == 1:
                yield {"result": {"tag": tag, "refused": True, "host": {"model": "m", "avx512f": True, "avx2": True}}, "container_wall_s": 0.1}
            elif tag == 2:
                yield RuntimeError("container lost")
            else:
                yield self._accept(p)

    def spawn(self, p):
        self.spawned.append(p["args"][2])
        return _Call(self._accept(p))


def test_gated_calls_resubmit_refused_and_failed_inputs(monkeypatch):
    g = _gate()
    import modal_tournament as MT
    fake = _FakeFn()
    monkeypatch.setitem(MT._STATE, "eval_fn", fake)
    monkeypatch.setattr(MT, "_cost", lambda recs, label: None)
    g._HOSTS.clear()
    res = g.gated_modal_calls("remote_sim_batch", [[0], [1], [2], [3]], commit=True)
    assert res == [0, 10, 20, 30]
    assert sorted(fake.spawned) == [1, 2, 3]
    s = g._host_summary()
    assert s["any_avx512"] is False and s["calls"] == 4
    assert s["stages"][-1]["refused"] == 2 and s["stages"][-1]["failed_calls"] == 1


def test_gated_calls_stop_on_a_worker_error(monkeypatch):
    g = _gate()
    import modal_tournament as MT

    class _ErrFn:
        def map(self, payloads, order_outputs=True, return_exceptions=False):
            yield {"error": "evaluation worker exit 1", "stderr": "Traceback ..."}

    monkeypatch.setitem(MT._STATE, "eval_fn", _ErrFn())
    with pytest.raises(SystemExit, match="failed"):
        g.gated_modal_calls("remote_micro_batch", [[1]], commit=True)


def test_frozen_run_modal_calls_the_module_level_modal_calls():
    import generate_real_hidden as G
    src = inspect.getsource(G.run_modal)
    for f in ("remote_sim_batch", "remote_micro_batch", "remote_assemble", "remote_tar"):
        assert f'_modal_calls("{f}"' in src
    assert "_modal_calls" in G.__dict__
