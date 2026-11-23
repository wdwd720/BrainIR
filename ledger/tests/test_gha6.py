"""Run 6 builders and the BANC build (RUN6_PROMPT Stages 1-3). The freeze guard is bypassed only for builders that touch no wiring of
BANC descending neurons (RUN6_PROMPT hard limit 2); the one-sided and copy builders are checked with a stand-in side table."""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

B = pytest.importorskip("brainir_ledger.banc")
try:
    B.fetch()
except Exception:  # noqa: BLE001
    pytest.skip("BANC sources not available on this machine", allow_module_level=True)

import gha6 as G6  # noqa: E402


@pytest.fixture()
def unfrozen(monkeypatch):
    monkeypatch.setattr(G6, "require_freeze6", lambda what: None)


def _strip(j: dict) -> dict:
    return {k: v for k, v in j.items() if k not in ("key", "members", "W", "sizes", "readout", "seed")}


def test_banc_build_facts():
    net = B.network()
    assert net.n == 4963 and int(net.readout.sum()) == 139
    sc = B.sign_check()
    assert sc["rows_mixed_sign"] == 0 and sc["rule_rows_agreeing"] == sc["rule_rows_with_outputs"] == 4863 and sc["autapses"] == 0
    assert len(B.groups()) == 309
    c = B.match_confidence()
    assert c["confidence"].value_counts().to_dict() == {"high": 206, "medium": 103}
    assert B.groups()["DNg100"] == [1605, 4284]


def test_tuned_spec_is_b2rs(unfrozen):
    groups, area = G6.build_bt()
    sh, jobs = groups[0]
    b2r = pickle.loads((G6.G.GHA / "b2r" / "chunk_0.pkl").read_bytes())[0][1]
    assert _strip(jobs[0]) == _strip(b2r) and area == "thirdfly_v1"
    n_types = len(B.groups())
    assert len(jobs) == 16 * n_types + 16 * 6  # whole types + 4 DNb08 and 2 DNg100 members alone
    assert sh["W"].shape == (4963, 4963) and int(sh["readout"].sum()) == 139


def test_sweep_spec_is_dx1s(unfrozen):
    (sh, jobs), = G6.build_bs()[0]
    dx1 = pickle.loads((G6.G.GHA / "dx-1-run4" / "chunk_0.pkl").read_bytes())[0][1]
    assert _strip(jobs[0]) == _strip(dx1)
    assert len(jobs) == 8 * len(B.groups())
    (sh2, jobs2), = G6.build_ms()[0]
    assert _strip(jobs2[0]) == _strip(dx1) and len(jobs2) == 8 * 328


def test_part_v(unfrozen):
    (sh, jobs), = G6.build_pv()[0]
    assert len(jobs) == 64 + 4 * 20 * 16
    v2 = [j for j in jobs if j["key"].startswith("V2|DNb08-391|I250|")]
    assert len(v2) == 16 and v2[0]["stim_indices"] == [391] and v2[0]["currents"] == [250.0] and v2[0]["model"]["t_end"] == 2.0


def test_copy_identity_and_properties():
    W = B.network().W
    c1, c2 = G6.banc_copy(G6.COPY_SEEDS[0]), G6.banc_copy(G6.COPY_SEEDS[1])
    for c in (c1, c2):
        assert c.shape == W.shape and c.nnz <= W.nnz
        A = W.multiply(c)  # signs never flip: every surviving entry has the same sign as the original
        assert (A.data > 0).all()
    assert (c1 != c2).nnz > 0


def test_one_sided_jobs_with_stand_in_sides(unfrozen, monkeypatch):
    g = B.groups()
    fake = {"L": {t: m[:1] for t, m in g.items() if len(m) >= 2}, "R": {t: m[1:2] for t, m in g.items() if len(m) >= 2}}
    monkeypatch.setattr(B, "halves", lambda: fake)
    (sh, jobs), = G6.build_bh()[0]
    assert len(jobs) == 2 * 8 * len(fake["L"])
    from brainir.compute.backend import Shared  # noqa: PLC0415

    assert {j["key"].split("|")[0] for j in jobs} == {"BH-L", "BH-R"}
    for j in jobs:
        side = j["key"].split("|")[0][-1]
        assert isinstance(j["readout"], Shared) and j["readout"].key == f"readout_{side}"
    assert set(sh) == {"W", "sizes", "readout", "readout_L", "readout_R"}
    assert int(sh["readout_L"].sum()) == 68 and int(sh["readout_R"].sum()) == 71
    out, area = G6.build_bn()
    assert len(out) == 2 and all(len(j) == 8 * len(fake["L"]) for _, j in out)
