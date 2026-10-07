"""The reference-platform gate of benchmark simulations (LOG P4-D32; review H round 3, NEW-1): the gate's constants equal the pinned
image record and the Modal pins, a fingerprint off the platform is named for every reason, and `run_job` refuses a benchmark system
outside the platform (test tiers still run anywhere)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brainir_causal import protocol as P
from brainir_causal.p4modal import gate as G
from brainir_causal.simservice import TEST_TIERS, needs_reference_platform, run_job

IMAGE_JSON = Path(__file__).resolve().parents[2] / "docker" / "p4sandbox" / "image.json"


def _fp(**kw):
    fp = {"os": "Linux", "admissible": True, "pins": dict(G.REFERENCE_PINS), "python": "3.12.14", "numpy": "2.5.3", "scipy": "1.18.1",
          "torch": "2.14.0+cpu"}
    fp.update(kw)
    return fp


def test_the_gate_constants_equal_the_image_record_and_the_modal_pins():
    from brainir_causal.p4modal.images import CPU_PINS, PINNED, TORCH
    assert G.REFERENCE_PINS == CPU_PINS
    assert f"numpy=={G.REFERENCE_STACK['numpy']}" in PINNED and f"scipy=={G.REFERENCE_STACK['scipy']}" in PINNED
    assert TORCH == f"torch=={G.REFERENCE_STACK['torch']}"
    if not IMAGE_JSON.exists():
        pytest.skip("the image record is not in this tree")
    stack = json.loads(IMAGE_JSON.read_text(encoding="utf-8"))["stack"]
    assert stack["numpy"] == G.REFERENCE_STACK["numpy"] and stack["scipy"] == G.REFERENCE_STACK["scipy"]
    assert stack["torch"].split("+")[0] == G.REFERENCE_STACK["torch"]
    assert ".".join(stack["python"].split(".")[:2]) == G.REFERENCE_STACK["python"]


def test_reference_fingerprints_pass_and_every_deviation_is_named():
    assert G.reference_platform_problems(_fp()) == []
    assert G.reference_platform_problems(_fp(torch="2.14.0", python="3.12.3")) == []      # Modal GPU image: CUDA torch, debian python
    assert G.reference_platform_problems(_fp(torch=None)) == []                            # torch absent from the process
    bad = G.reference_platform_problems(_fp(os="Windows", admissible=False, pins={}, python="3.13.1", numpy="2.4.0", scipy="1.17.0",
                                            torch="2.13.0"))
    assert len(bad) == 8 and any("Windows" in b for b in bad) and any("gate" in b for b in bad)
    assert sum(b.startswith("pin ") for b in bad) == 2


def test_run_job_refuses_a_benchmark_system_off_the_reference_platform(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "reference_platform_problems", lambda fp=None: ["os Windows (reference: Linux)"])
    q = P.validate({"system": "syn:dev:0", "params_seed": 0, "t_end": 1.0, "dt": 0.01, "stimulus": [[0.0, 1.0]]})
    for sysdef in ({"kind": "synthetic", "tier": "dev", "suite_seed": 1, "system_id": "syn:dev:0"},
                   {"kind": "real", "system_id": "real:X:mech", "network": "net0", "system_hash": "h" * 64}):
        assert needs_reference_platform(sysdef)
        with pytest.raises(RuntimeError, match="reference platform"):
            run_job({"sysdef": sysdef, "protocol": q, "store_root": str(tmp_path / "store"), "bundle": None})
    assert not (tmp_path / "store" / "rec").exists()                                      # refused before anything was stored
    assert all(not needs_reference_platform({"kind": "synthetic", "tier": t}) for t in TEST_TIERS)


def test_the_service_cli_refuses_benchmark_systems_without_the_docker_pool(tmp_path, monkeypatch):
    from brainir_causal import simservice as S
    monkeypatch.setattr(G, "reference_platform_problems", lambda fp=None: ["os Windows (reference: Linux)"])
    systems = tmp_path / "systems.json"
    systems.write_text(json.dumps({"syn:dev:0": {"kind": "synthetic", "tier": "dev", "suite_seed": 1, "system_id": "syn:dev:0"}}),
                       encoding="utf-8")
    with pytest.raises(SystemExit, match="--docker"):
        S.main(["--room", str(tmp_path / "room"), "--systems", str(systems), "--store", str(tmp_path / "store"),
                "--ledger-dir", str(tmp_path / "ledger"), "--tokens", str(tmp_path / "tokens.json")])
