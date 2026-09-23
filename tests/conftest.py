"""Shared fixtures: a synthetic MaleCNS-shaped dataset built once per session."""

from __future__ import annotations

from pathlib import Path

import pytest

from brainir.testing.synthetic import build_synthetic_dataset as build_synthetic


@pytest.fixture(scope="session")
def synthetic_build(tmp_path_factory) -> dict:
    return build_synthetic(tmp_path_factory.mktemp("synthetic"))


@pytest.fixture(scope="session")
def synthetic_out(synthetic_build) -> Path:
    return Path(synthetic_build["out_dir"])


@pytest.fixture(scope="session")
def cx(synthetic_out):
    from brainir.graph import Connectome
    return Connectome(synthetic_out)


def pytest_configure(config):
    config.addinivalue_line("markers", "real_data: needs the processed MaleCNS v1.0 build under data/processed")
    config.addinivalue_line("markers", "modal: launches Modal containers (opt-in: set BRAINIR_TEST_MODAL=1; costs cents)")
