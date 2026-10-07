"""The remote-build path (plan LOCALLY, build in a container: `suites.plan_remote_job` -> `suites.build_system_job`) writes exactly
what the local builder writes, publishes its store records, writes the synthetic onset states, and keeps the salt local (a planned
job carries protocols and seeds, never the salt)."""

import json
from pathlib import Path

import numpy as np
import pytest

from brainir_causal import suites as SU
from brainir_causal.data import ExperimentSet
from brainir_causal.store import TrajectoryStore


def _small(job: dict, n: int = 12) -> dict:
    """A quick job: the first n specs of each part, without pool sources (pool futures are covered by the full builds)."""
    job = json.loads(json.dumps(job))
    for part in job["parts"]:
        part["specs"] = [s for s in part["specs"] if s["split"] != "pool_src"][:n]
        part["sets"] = [s for s in part["sets"] if s != "pool_src"]
    return job


def _redirect(job: dict, root: Path) -> dict:
    job = dict(job)
    job["dirs"] = {k: str(root / "vol" / k) for k in ("base", "public", "eval", "truth")}
    job["store_root"] = str(root / "cstore")
    job["publish_store"] = str(root / "vstore")
    job["workers"] = 1
    job["cleanup_store"] = False
    return job


def _records(d: Path) -> dict:
    s = ExperimentSet.load(d, lazy=True)
    out = {}
    for r in s.rows:
        tr = s.load(r)
        out[r["key"]] = (r["split"], r["family"], json.dumps(r["protocol"], sort_keys=True), tr.x.tobytes(), tr.y.tobytes(), tr.u.tobytes())
    return out


@pytest.fixture(scope="module", autouse=True)
def _test_salt(tmp_path_factory):
    """A hermetic test salt for every test of this module (phase4/tests/_hermetic.py): the real salt never leaves the orchestrator host,
    and the salted code paths run unchanged with another salt."""
    from _hermetic import hermetic_salt
    with hermetic_salt(tmp_path_factory.mktemp("salt")) as salt:
        yield salt


def test_remote_job_equals_local_build(tmp_path):
    job = _small(SU.plan_remote_job("synthetic", "syn:toy:0", tier="toy"))
    assert "salt" not in json.dumps(job).lower()
    out = SU.build_system_job(_redirect(job, tmp_path / "remote"))
    # the same plan through the local builder
    pub, internal = job["pub"], job["internal"]
    truth = SU._synthetic_systems("toy", SU.tier_seed("toy"), None)["syn:toy:0"]
    dirs = {k: tmp_path / "local" / k for k in ("base", "public", "eval", "truth")}
    be = SU.LocalBackend({"syn:toy:0": internal}, tier="toy", seed=SU.tier_seed("toy"), store_root=tmp_path / "lstore", workers=1)
    try:
        for part in job["parts"]:
            SU.build_system(pub, internal, tier="toy", seed=SU.tier_seed("toy"), level=job["level"], run=be.run, dirs=dirs,
                            dest=part["dest"], sets=tuple(part["sets"]), policy=part["policy"], truth_system=truth,
                            store_root=tmp_path / "lstore", specs=[SU.spec_from_dict(d) for d in part["specs"]])
    finally:
        be.close()
    for part in job["parts"]:
        a = _records(tmp_path / "remote" / "vol" / part["dest"] / "syn_toy_0")
        b = _records(dirs[part["dest"]] / "syn_toy_0")
        assert a == b and len(a) > 0
    # onset states for every intervention test item with a stored full state, and the published store
    onset = np.load(tmp_path / "remote" / "vol" / "truth" / "syn_toy_0" / "onset_states.npz")
    held = ExperimentSet.load(tmp_path / "remote" / "vol" / "eval" / "syn_toy_0", lazy=True)
    n_int = sum(1 for r in held.rows if r["split"] == "test" and r["protocol"].get("events"))
    assert len(onset.files) == n_int == out["onset_states"]["n"]
    pubd = TrajectoryStore(tmp_path / "remote" / "vstore")
    assert out["published"]["new"] == len(list((tmp_path / "remote" / "cstore" / "rec").rglob("*.npz"))) > 0
    k = next(iter(onset.files))
    row = next(r for r in held.rows if r["key"] == k)
    assert pubd.get(row["meta"]["store_key"]) is not None
    assert set(out["manifest"]) >= {"public", "eval", "truth"}


def test_remote_dirs_are_posix_volume_paths():
    d = SU.remote_dirs("real_public", kind="real")
    assert d["public"] == "/fitvol/data/real/real_public/public" and d["eval"].startswith("/evalvol/data/real/real_public")
    s = SU.remote_dirs("val", kind="synthetic")
    assert s["public"].startswith("/fitvol/") and s["truth"].startswith("/evalvol/")
