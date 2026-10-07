"""The generator integration tool (scripts/p4/integrate_generator.py) and the build-class split of build_on_modal.py: a delivery is
diffed, refused on links / absolute host paths / oversized files, replaced atomically with its sha256 record, and `--check` detects
drift; slow systems go to the 32-core class longest first."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def gi(tmp_path, monkeypatch):
    m = _load("integrate_generator_under_test", "scripts/p4/integrate_generator.py")
    monkeypatch.setattr(m, "DEST", tmp_path / "bench" / "generator")
    monkeypatch.setattr(m, "RECORD", tmp_path / "research" / "GENERATOR_DELIVERY_SHA256.txt")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    m.RECORD.parent.mkdir(parents=True)
    return m


def _room(root: Path, version: str) -> Path:
    for rel, text in {"SYNTHETIC_BENCHMARK.md": f"# docs {version}\n", "calibration_report.json": "{}\n",
                      "src/p4synth/__init__.py": f"VERSION = {version!r}\n", "src/p4synth/engine.py": "x = 1\n",
                      "tests/test_a.py": "def test_a():\n    assert True\n", "ref/calibstats.py": "# ref\n"}.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    (root / "src" / "p4synth" / "__pycache__").mkdir(exist_ok=True)
    (root / "src" / "p4synth" / "__pycache__" / "engine.cpython-312.pyc").write_bytes(b"\0")
    (root / "notes").mkdir(exist_ok=True)
    (root / "notes" / "scratch.md").write_text("author notes (not delivered)\n", encoding="utf-8")
    return root


def test_apply_replaces_the_copy_and_writes_a_record_that_check_verifies(gi, tmp_path, capsys):
    r1 = _room(tmp_path / "room1", "1")
    gi.DEST.mkdir(parents=True)
    (gi.DEST / "stale.txt").write_text("left over\n", encoding="utf-8")
    assert gi.main(["--room", str(r1)]) == 0 and not (gi.DEST / "src").exists()          # dry run: nothing changes
    assert gi.main(["--room", str(r1), "--apply"]) == 0
    got = sorted(p.relative_to(gi.DEST).as_posix() for p in gi.DEST.rglob("*") if p.is_file())
    assert got == ["SYNTHETIC_BENCHMARK.md", "calibration_report.json", "ref/calibstats.py", "src/p4synth/__init__.py",
                   "src/p4synth/engine.py", "tests/test_a.py"]                               # caches, notes and stale files are gone
    rec = gi.RECORD.read_text(encoding="utf-8").splitlines()
    assert len(rec) == 6 and all(line.split(" ", 1)[1].startswith("*./") for line in rec)
    assert gi.main(["--check"]) == 0
    (gi.DEST / "src" / "p4synth" / "engine.py").write_text("x = 2\n", encoding="utf-8", newline="\n")
    assert gi.main(["--check"]) == 1                                                          # drift is detected
    r2 = _room(tmp_path / "room2", "2")
    capsys.readouterr()
    assert gi.main(["--room", str(r2)]) == 0
    out = capsys.readouterr().out
    assert "~ SYNTHETIC_BENCHMARK.md" in out and "~ src/p4synth/__init__.py" in out and "~ src/p4synth/engine.py" in out


def test_a_delivery_with_an_absolute_host_path_or_an_oversized_file_is_refused(gi, tmp_path, monkeypatch):
    r = _room(tmp_path / "room", "1")
    (r / "src" / "p4synth" / "paths.py").write_text('DATA = r"C:\\Dev\\BrainIR\\data"\n', encoding="utf-8")
    assert gi.main(["--room", str(r), "--apply"]) == 2 and not gi.DEST.exists()
    (r / "src" / "p4synth" / "paths.py").unlink()
    monkeypatch.setattr(gi, "MAX_BYTES", 10)
    assert gi.main(["--room", str(r), "--apply"]) == 2 and not gi.DEST.exists()


def test_slow_systems_go_to_the_32_core_class_longest_first(tmp_path, monkeypatch):
    B = _load("build_on_modal_under_test", "scripts/p4/build_on_modal.py")
    rec = tmp_path / "SYNTHETIC_DATA_BUILD.json"
    rec.write_text(json.dumps({"runs": [
        {"what": "synthetic tier dev", "systems": {"a": {"container_wall_s": 100.0}, "b": {"container_wall_s": 900.0}}},
        {"what": "synthetic tier val", "systems": {"c": {"container_wall_s": 700.0}}},
        {"what": "synthetic tier dev", "systems": {"a": {"container_wall_s": 50.0}, "b": {"container_wall_s": 1400.0},
                                                   "d": {"wall_s": 650.0}}}]}), encoding="utf-8")
    monkeypatch.setattr(B, "SYN_RECORD", rec)
    prev = B.previous_build_seconds("dev")
    assert prev == {"a": 50.0, "b": 1400.0, "d": 650.0}                                        # the most recent build of the tier
    assert B.previous_build_seconds("conf") == {}
    calls = []

    class FakeBackend:
        def __init__(self, classes, **kw):
            assert {"build", "build_xl"} <= set(classes)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def call(self, target, arg_lists, cls, **kw):
            calls.append((cls, [a[0]["sid"] for a in arg_lists], [a[0].get("workers") for a in arg_lists]))
            return [{"result": {"manifest": {}}, "sid": a[0]["sid"]} for a in arg_lists]

        def cost_summary(self):
            return {}

    import brainir_causal.p4modal.app as app
    monkeypatch.setattr(app, "Backend", FakeBackend)
    jobs = [{"sid": s, "workers": 16} for s in ("a", "b", "d", "e")]
    out, _, _ = B.run_builds(jobs, extra_dirs=None, label="t", previous_s=prev)
    assert set(out) == {"a", "b", "d", "e"}
    by = {c[0]: c for c in calls}
    assert by["build_xl"][1] == ["b", "d"] and by["build_xl"][2] == [B.XL_WORKERS, B.XL_WORKERS]   # longest first, 32 workers
    assert by["build"][1] == ["a", "e"] and by["build"][2] == [16, 16]
