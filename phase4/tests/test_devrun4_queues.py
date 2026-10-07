"""The remote runner's per-developer queues (scripts/p4/devrun4.py; review F round 2, N-M2): every developer's queue lives in its own
runs/<prefix>/_remote/, the daemon takes the prefix from the queue's directory, a request may run only a script of that same
runs/<prefix>/, and the code tar carries only that developer's runs/ subdirectory (never a queue)."""

from __future__ import annotations

import importlib.util
import io
import sys
import tarfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("p4devrun4_under_test", REPO / "scripts" / "p4" / "devrun4.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


D = _load()


@pytest.fixture()
def room(tmp_path):
    r = tmp_path / "room"
    for rel in ("runs/li/a.py", "runs/li/sub/b.py", "runs/nn/c.py", "runs/li/_remote/requests/r1.json", "runs/li/remote/j1/out.txt",
                "runs/_shared/x.py", "runs/.hidden/y.py", "src/brainir_causal/methods/li/m.py"):
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x = 1\n", encoding="utf-8")
    (r / "runs" / "stray.py").write_text("x = 1\n", encoding="utf-8")
    return r


def test_queues_are_the_developers_runs_subdirectories(room):
    qs = D._queues(room)
    assert set(qs) == {"li", "nn"}                                   # not _shared, .hidden or a file
    assert qs["li"] == room / "runs" / "li" / "_remote" and D._queue(room, "nn") == room / "runs" / "nn" / "_remote"


def test_a_request_runs_only_a_script_of_its_own_queue_owner(room):
    assert D._validate(room, {"script": "runs/li/a.py"}, "li")[:2] == ("runs/li/a.py", "li")
    assert D._validate(room, {"script": "runs/li/sub/b.py", "class": "medium"}, "li")[3] == "medium"
    for script in ("runs/nn/c.py", "runs/li/_remote/x.py", "runs/_shared/x.py", "runs/li/../nn/c.py", "src/brainir_causal/methods/li/m.py",
                   "runs/stray.py"):
        with pytest.raises(ValueError):
            D._validate(room, {"script": script}, "li")
    with pytest.raises(ValueError, match="own runs/<prefix>/"):
        D._validate(room, {"script": "runs/nn/c.py"}, "li")
    with pytest.raises(ValueError, match="args"):
        D._validate(room, {"script": "runs/li/a.py", "args": ["../x"]}, "li")


def test_the_code_tar_holds_only_the_owners_runs_and_never_a_queue(room):
    with tarfile.open(fileobj=io.BytesIO(D._code_tar(room, "li"))) as tf:
        names = set(tf.getnames())
    assert {"runs/li/a.py", "runs/li/sub/b.py", "src/brainir_causal/methods/li/m.py"} <= names
    assert not any(n.startswith(("runs/nn/", "runs/li/_remote/", "runs/li/remote/", "runs/_shared/")) for n in names)


def test_the_client_writes_into_its_own_queue_only():
    assert 'PREFIX = os.environ.get("P4_AGENT_SCRATCH", "")' in D.CLIENT
    assert 'Q = Path(__file__).resolve().parents[1] / "runs" / PREFIX / "_remote"' in D.CLIENT
    assert 'if not PREFIX or not script.startswith(f"runs/{PREFIX}/"):' in D.CLIENT
