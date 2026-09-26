"""The Phase 4 room builder (scripts/make_phase4_cleanroom.py; goal5 sections 5-6): refusal list, content scanner, manifest records,
sandbox wrapper and read-only mounts, scan / audit findings (modified, unexpected, forbidden, links, planted Claude files), sync with
interrupted-sync recovery. Runs on a fake repository in a temporary directory (no Docker needed)."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def B(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("p4builder_under_test", REPO / "scripts" / "make_phase4_cleanroom.py")
    b = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = b                  # dataclasses resolve string annotations through sys.modules
    spec.loader.exec_module(b)
    fake = tmp_path / "repo"
    for rel, text in {
        "phase4/src/brainir_causal/protocol.py": "def validate(p):\n    return p\n",
        "phase4/src/brainir_causal/api.py": "class CausalStateModel:\n    pass\n",
        "research/phase4/contracts/room_CLAUDE.md": "# rules\nRun code with ./sbx only.\n",
        "benchmarks/causal_state_v1/PROTOCOL.md": "# protocol\nThe salt stays offline until after Level C. Phase 3 format is translated.\n",
        "PHASE3_REPORT.md": "answer-bearing\n",
        "goal5.md": "spec\n",
        "research/phase3/HIDDEN_EVALUATIONS.md": "x\n",
        "research/phase4/PLAN.md": "x\n",
        "benchmarks/causal_state_v1/hidden/salt_commitment.json": "{}\n",
        "data/phase4/hidden/x.npz": "x",
        "notes/leaky.md": "see C:\\Dev\\BrainIR\\research for details\n",
        "notes/dataset.md": "trained on the MANC connectome\n",
    }.items():
        p = fake / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    monkeypatch.setattr(b, "ROOT", fake)
    monkeypatch.setattr(b, "AUDIT", tmp_path / "audit")
    monkeypatch.setattr(b, "P4", tmp_path / "p4research")
    return b


def _spec(B, tmp_path, work_areas=("runs/", "notes/", "src/brainir_causal/methods/"), name="clean"):
    items = B._isolation_items("research/phase4/contracts/room_CLAUDE.md", None) + [
        B.Item("phase4/src/brainir_causal/protocol.py", "src/brainir_causal/protocol.py", "public module", "generic-public"),
        B.Item("phase4/src/brainir_causal/api.py", "src/brainir_causal/api.py", "public module", "generic-public"),
        B.Item("benchmarks/causal_state_v1/PROTOCOL.md", "docs/PROTOCOL.md", "protocol", "benchmark-public"),
        B.Item(None, "src/brainir_causal/methods/__init__.py", "empty package", "generated", content='"""methods"""\n'),
    ]
    return B.RoomSpec(name, tmp_path / "BrainIR_p4unit", tmp_path / "manifests" / "M.json", items, work_areas,
                      rw_nested=("src/brainir_causal/methods",), dirs=("runs", "notes", ".tmp"))


def test_refusal_list_and_scanner(B):
    for rel in ("PHASE3_REPORT.md", "PHASE2_REPORT.md", "goal5.md", "research/phase3/HIDDEN_EVALUATIONS.md", "research/LOG.md",
                "research/phase4/PLAN.md", "research/phase4/reviews/A.md", "benchmarks/causal_state_v1/hidden/salt_commitment.json",
                "benchmarks/state_discovery_v1/hidden/x.json", "data/phase4/hidden/x.npz", "data/phase3/real_public/a.npz",
                "benchmarks/dng100/oracle/oracle.json", "benchmarks/dng100_walking_cpg/README.md", "CLAUDE.md",
                "data/phase4/suites/val/sys1/truth/z.npz", "research/phase4/HIDDEN_EVALUATIONS.md"):
        assert B.refused(rel), rel
    for rel in ("phase4/src/brainir_causal/protocol.py", "benchmarks/causal_state_v1/PROTOCOL.md", "data/phase4/suites/dev/public/a.npz",
                "research/phase4/contracts/METHOD_DEV_CONTRACT.md"):
        assert B.refused(rel) is None, rel
    assert B.scan_text("trained on the MANC connectome")
    assert B.scan_text("see C:\\Dev\\BrainIR\\research")
    assert B.scan_text("path /c/Dev/BrainIR/x")
    assert B.scan_text("the PHASE3_REPORT.md says")
    assert B.scan_text("copied from BrainIR_p3clean")
    for ok in ("the salt stays offline until Level C", "ground truth", "Phase 3 protocol format", "room C:/Dev/BrainIR_p4clean/sbx"):
        assert B.scan_text(ok) is None, ok


def test_check_source_refuses_and_accepts(B, tmp_path):
    spec = _spec(B, tmp_path)
    fake = B.ROOT
    assert B.check_source(fake / "PHASE3_REPORT.md", "docs/x.md", spec)
    assert B.check_source(fake / "notes" / "leaky.md", "docs/x.md", spec)           # absolute repository path in the text
    assert B.check_source(fake / "notes" / "dataset.md", "docs/x.md", spec)         # dataset name
    assert B.check_source(fake / "phase4" / "src" / "brainir_causal" / "protocol.py", "src/brainir_causal/realsim.py", spec)  # name
    assert B.check_source(fake / "phase4" / "src" / "brainir_causal" / "protocol.py", "src/brainir_causal/protocol.py", spec) is None


def test_build_manifest_sandbox_and_readonly_mounts(B, tmp_path):
    spec = _spec(B, tmp_path)
    m = B.build(spec, spec.dest, docker_check=False)
    room = spec.dest
    for rec in m["files"]:
        assert set(rec) >= {"path", "source", "destination", "sha256", "reason", "classification", "bytes"}, rec
        assert rec["destination"] == f"$ROOMS/{room.name}/{rec['path']}"
        assert rec["source"].startswith(("$REPO/", "generated"))
    for p in ("CLAUDE.md", "CLAUDE.local.md", ".mcp.json", ".claude/README.md", "sbx", "CLEANROOM_MANIFEST.json"):
        assert (room / p).exists(), p
    outside = B.AUDIT / "sbx_bin" / room.name / "sbx"
    assert outside.read_bytes() == (room / "sbx").read_bytes()
    text = (room / "sbx").read_text(encoding="utf-8")
    import re
    assert "--network none" in text and "seccomp=" in text and not re.findall(r"@[A-Z_]+@", text)
    ro = m["sandbox"]["ro_paths"]
    for p in (".claude", ".mcp.json", "CLAUDE.local.md", "CLAUDE.md", "docs", "sbx", "src/brainir_causal/api.py", "src/brainir_causal/protocol.py"):
        assert p in ro, (p, ro)
    assert not any(p.startswith(("runs", "notes", "src/brainir_causal/methods")) for p in ro), ro
    prot = json.loads((B.AUDIT / f"protected_{room.name}.json").read_text(encoding="utf-8"))
    assert "docs/PROTOCOL.md" in prot["files"] and prot["rw_nested"] == ["src/brainir_causal/methods"]
    assert B.scan(room, m, spec) == []


def test_scan_finds_tampering_leaks_links_and_planted_claude_files(B, tmp_path):
    import _winapi
    spec = _spec(B, tmp_path)
    m = B.build(spec, spec.dest, docker_check=False)
    room = spec.dest
    (room / "docs" / "PROTOCOL.md").write_text("changed\n", encoding="utf-8")
    (room / "stray.txt").write_text("x", encoding="utf-8")
    (room / "runs" / "x").mkdir(parents=True)
    (room / "runs" / "x" / "note.md").write_text("reading C:/Dev/BrainIR/goal5.md\n", encoding="utf-8")
    (room / "runs" / "x" / "CLAUDE.md").write_text("instructions\n", encoding="utf-8")
    (room / ".claude" / "settings.local.json").write_text("{}", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    _winapi.CreateJunction(str(outside), str(room / "runs" / "lnk"))
    probs = "\n".join(B.scan(room, m, spec))
    for needle in ("modified: docs/PROTOCOL.md", "unexpected file: stray.txt", "forbidden content", "runs/x/note.md",
                   "unexpected Claude control file: runs/x/CLAUDE.md", "file in the read-only .claude directory", "link / junction: runs/lnk"):
        assert needle in probs, (needle, probs)
    os.rmdir(room / "runs" / "lnk")


def test_sync_updates_changed_sources_and_recovers_an_interrupted_sync(B, tmp_path):
    spec = _spec(B, tmp_path)
    spec.manifest.parent.mkdir(parents=True, exist_ok=True)
    B.build(spec, spec.dest, docker_check=False)
    room = spec.dest
    src = B.ROOT / "phase4" / "src" / "brainir_causal" / "api.py"
    src.write_text("class CausalStateModel:\n    version = 2\n", encoding="utf-8")
    r = B.sync(spec, room, "api v2")
    assert r["changed"] == ["src/brainir_causal/api.py"]
    man = json.loads(spec.manifest.read_text(encoding="utf-8"))
    assert man["syncs"][-1]["reason"] == "api v2"
    # interrupted sync: the file was copied but the manifest was not written
    src.write_text("class CausalStateModel:\n    version = 3\n", encoding="utf-8")
    (room / "src" / "brainir_causal" / "api.py").write_bytes(src.read_bytes())
    assert "modified: src/brainir_causal/api.py" in "\n".join(B.scan(room, json.loads(spec.manifest.read_text(encoding="utf-8")), spec))
    r = B.sync(spec, room, "recover")
    assert r["changed"] == ["src/brainir_causal/api.py"]
    assert B.scan(room, json.loads(spec.manifest.read_text(encoding="utf-8")), spec) == []
    # a refused source is never synced
    spec.items.append(B.Item("PHASE3_REPORT.md", "docs/report.md", "x", "x"))
    with pytest.raises(SystemExit):
        B.sync(spec, room, "bad")


def test_audit_lists_unmanifested_files(B, tmp_path):
    spec = _spec(B, tmp_path)
    B.build(spec, spec.dest, docker_check=False)
    (spec.dest / "runs" / "a.py").write_text("x = 1\n", encoding="utf-8")
    rep = B.audit(spec, spec.dest)
    assert rep["ok"] and "runs/a.py" in rep["unmanifested"] and rep["unmanifested_by_top"]["runs"] == 1


def test_free_workspace_room_and_ro_split(B, tmp_path):
    spec = _spec(B, tmp_path, work_areas=None, name="bench")
    m = B.build(spec, spec.dest, docker_check=False)
    (spec.dest / "p4synth").mkdir()
    (spec.dest / "p4synth" / "systems.py").write_text("x = 1\n", encoding="utf-8")
    assert B.scan(spec.dest, m, spec) == []                     # the author's own files are free (but still content-scanned)
    (spec.dest / "p4synth" / "leak.md").write_text("DNg100\n", encoding="utf-8")
    assert any("forbidden content" in p for p in B.scan(spec.dest, m, spec))
    assert "src" in m["sandbox"]["ro_paths"]                     # no work area beneath src in a free room: the whole top is read-only


def test_real_room_specs_are_consistent():
    spec = importlib.util.spec_from_file_location("p4builder_real", REPO / "scripts" / "make_phase4_cleanroom.py")
    b = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = b
    spec.loader.exec_module(b)
    rooms = b.room_specs()
    assert set(rooms) == {"bench", "clean", "review"}
    for name, rs in rooms.items():
        dests = [it.path for it in rs.items]
        assert len(dests) == len(set(dests)), name
        for it in rs.items:
            if it.source:
                assert b.refused(it.source) is None, (name, it.source)
    clean = {it.path for it in rooms["clean"].items}
    assert not any(p.startswith("extra/") for p in clean)
    for mod in ("realsim", "simservice", "store", "runguard", "tournament", "synthadapter"):
        assert f"src/brainir_causal/{mod}.py" not in clean
