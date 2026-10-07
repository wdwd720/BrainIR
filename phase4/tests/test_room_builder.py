"""The Phase 4 room builder (scripts/make_phase4_cleanroom.py; goal5 sections 5-6; early review F): refusal list, the content scanner
(also after removing regex escapes), line-level redaction, manifest records (the in-room copy holds paths, hashes and sizes only), the
sandbox wrapper (read-only room mount, explicit work areas, per-agent areas, no bytecode), scan / audit findings (modified, unexpected,
forbidden, links, planted control files, interpreter hooks, bytecode), sync with interrupted-sync recovery and cache cleaning. Runs on
a fake repository in a temporary directory (no Docker, no OS protection: test_room_acl.py covers that). Every name comes from the
orchestrator's names config; this file carries none."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod                # dataclasses resolve string annotations through sys.modules
    spec.loader.exec_module(mod)
    return mod


N = _load("p4names_room_tests", REPO / "scripts" / "p4config" / "names.py")
TV = N.TEST_VECTORS
WORD = N.DATASET_WORDS[0]


@pytest.fixture()
def B(tmp_path, monkeypatch):
    b = _load("p4builder_under_test", REPO / "scripts" / "make_phase4_cleanroom.py")
    fake = tmp_path / "repo"
    files = {
        "phase4/src/brainir_causal/protocol.py": "def validate(p):\n    return p\n",
        "phase4/src/brainir_causal/api.py": "class CausalStateModel:\n    pass\n",
        "research/phase4/contracts/room_CLAUDE.md": "# rules\nRun code with sbx only.\n",
        "benchmarks/causal_state_v1/PROTOCOL.md": "# protocol\nThe salt stays offline until after Level C. Phase 3 format is translated.\n",
        "notes/leaky.md": f"see {REPO}\\research for details\n",
        "notes/dataset.md": f"trained on the {WORD.upper()} data\n",
        "notes/regex.py": f'PAT = r"\\b{WORD}\\b"\n',
        "phase4/src/brainir_causal/orch.py": f'import re\nOK = 1\nPAT = re.compile(r"\\b{WORD}\\b")\nALSO_OK = 2\n',
    }
    for rel in TV["answer_files"]:
        files[rel] = "answer-bearing\n"
    for rel, text in files.items():
        p = fake / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    monkeypatch.setattr(b, "ROOT", fake)
    monkeypatch.setattr(b, "AUDIT", tmp_path / "audit")
    monkeypatch.setattr(b, "P4", tmp_path / "p4research")
    return b


def _spec(B, tmp_path, work_areas=("runs/", "notes/", "src/brainir_causal/methods/", ".tmp/"), name="clean"):
    items = B._isolation_items("research/phase4/contracts/room_CLAUDE.md", None) + [
        B.Item("phase4/src/brainir_causal/protocol.py", "src/brainir_causal/protocol.py", "public module", "generic-public"),
        B.Item("phase4/src/brainir_causal/api.py", "src/brainir_causal/api.py", "public module", "generic-public"),
        B.Item("benchmarks/causal_state_v1/PROTOCOL.md", "docs/PROTOCOL.md", "protocol", "benchmark-public"),
        B.Item(None, "src/brainir_causal/methods/__init__.py", "empty package", "generated", content='"""methods"""\n'),
    ]
    return B.RoomSpec(name, tmp_path / "BrainIR_p4unit", tmp_path / "manifests" / "M.json", items, work_areas,
                      rw_nested=("src/brainir_causal/methods",), dirs=("runs", "notes", ".tmp"))


def _build(B, spec):
    return B.build(spec, spec.dest, docker_check=False, protect=False)


def test_refusal_list(B):
    for rel in TV["answer_files"] + ("research/LOG.md", "research/phase4/PLAN.md", "research/phase4/reviews/A.md",
                                     "benchmarks/causal_state_v1/hidden/salt_commitment.json", "data/phase4/hidden/x.npz",
                                     "CLAUDE.md", "data/phase4/suites/val/sys1/truth/z.npz", "scripts/p4config/names.py",
                                     "scripts/p4agent/canary.txt"):
        assert B.refused(rel), rel
    for rel in ("phase4/src/brainir_causal/protocol.py", "benchmarks/causal_state_v1/PROTOCOL.md", "data/phase4/suites/dev/public/a.npz",
                "research/phase4/contracts/METHOD_DEV_CONTRACT.md", "scripts/p4agent/guard_hook.py"):
        assert B.refused(rel) is None, rel


def test_scanner_sees_names_also_as_regex_sources(B):
    for w in N.DATASET_WORDS:
        assert B.scan_text(f"trained on {w}"), w
        assert B.scan_text(w.upper()), w
        assert B.scan_text(re.escape(w)), w                        # escaped spaces and hyphens
        assert B.scan_text(rf"\b{w}\b"), w                          # a word between two word-boundary escapes
        assert B.scan_text(rf"(?i)\b{w.replace(' ', r'\s*')}\b"), w
    assert B.scan_text(f"see {REPO}\\research")
    assert B.scan_text(f"path /{str(REPO)[0].lower()}/{str(REPO)[3:].replace(chr(92), '/')}/x")
    assert B.scan_text(f"copied from {TV['other_rooms'][0]}")
    for rel in TV["answer_files"][:2]:
        assert B.scan_text(f"the {rel} says"), rel
    for ok in ("the salt stays offline until Level C", "ground truth", "Phase 3 protocol format", "room C:/Dev/BrainIR_p4clean/sbx",
               r"re.compile(r'\bsbx\b')", "manchester", "fly ash", "a walking stick"):
        assert B.scan_text(ok) is None, ok


def test_redaction_is_line_level_and_leaves_no_fragment(B):
    text, n = B.redacted_text(B.ROOT / "phase4" / "src" / "brainir_causal" / "orch.py")
    assert n == 1
    lines = text.split("\n")
    assert lines[:2] == ["import re", "OK = 1"] and lines[2] == B.REDACTED and lines[3] == "ALSO_OK = 2"
    assert B.scan_text(text) is None and WORD not in text.lower()


def test_check_source_refuses_and_accepts(B, tmp_path):
    spec = _spec(B, tmp_path)
    fake = B.ROOT
    assert B.check_source(fake / TV["answer_files"][0], "docs/x.md", spec)
    assert B.check_source(fake / "notes" / "leaky.md", "docs/x.md", spec)           # absolute repository path in the text
    assert B.check_source(fake / "notes" / "dataset.md", "docs/x.md", spec)         # dataset name
    assert B.check_source(fake / "notes" / "regex.py", "docs/x.py", spec)           # dataset name as a regex source
    assert B.check_source(fake / "phase4" / "src" / "brainir_causal" / "protocol.py", "src/brainir_causal/realsim.py", spec)  # name
    assert B.check_source(fake / "phase4" / "src" / "brainir_causal" / "protocol.py", "src/brainir_causal/protocol.py", spec) is None


def test_build_manifest_sandbox_and_mount_model(B, tmp_path):
    spec = _spec(B, tmp_path)
    m = _build(B, spec)
    room = spec.dest
    for rec in m["files"]:
        assert set(rec) >= {"path", "source", "destination", "sha256", "reason", "classification", "bytes"}, rec
        assert rec["destination"] == f"$ROOMS/{room.name}/{rec['path']}"
        assert rec["source"].startswith(("$REPO/", "generated"))
    for p in ("CLAUDE.md", "CLAUDE.local.md", ".mcp.json", ".claude/README.md", "sbx", "CLEANROOM_MANIFEST.json"):
        assert (room / p).exists(), p
    inroom = json.loads((room / "CLEANROOM_MANIFEST.json").read_text(encoding="utf-8"))
    assert all(set(e) == {"path", "sha256", "bytes"} for e in inroom["files"])     # no sources, no source hashes (F-B5, F-M1)
    outside = B.AUDIT / "sbx_bin" / room.name / "sbx"
    assert outside.read_bytes() == (room / "sbx").read_bytes()
    text = (room / "sbx").read_text(encoding="utf-8")
    assert "--network none" in text and "seccomp=" in text and not re.findall(r"@[A-Z_]+@", text)
    assert f"type=bind,source=$ROOM_MOUNT,target=/room,readonly" in text                       # the room root is read-only (F-M3)
    assert "PYTHONDONTWRITEBYTECODE=1" in text and "PYTHONPYCACHEPREFIX=/tmp/pyc" in text
    assert "RW_PATHS=('notes' 'runs' 'src/brainir_causal/methods')" in text
    assert "AGENT_AREAS=('.tmp')" in text and "tmpfs-mode=555" in text and "FREE_ROOM=0" in text
    assert "sim_opts=(-e P4_SIM_TOKEN)" in text and '"${sim_opts[@]}"' in text          # the launcher's token, env only
    prot = json.loads((B.AUDIT / f"protected_{room.name}.json").read_text(encoding="utf-8"))
    assert "docs/PROTOCOL.md" in prot["files"] and "CLEANROOM_MANIFEST.json" in prot["files"]
    assert prot["work_areas"] == ["runs", "notes", "src/brainir_causal/methods", ".tmp"] and prot["agent_areas"] == [".tmp"]
    assert prot["sbx_sha256"] == next(e["sha256"] for e in m["files"] if e["path"] == "sbx")
    assert Path(prot["manifest"]) == spec.manifest and prot["acl"] is False
    assert B.scan(room, m, spec) == [] and B.scan_planted(room, m) == []


def test_owned_areas_are_bound_per_agent_and_the_token_directory_is_outside(B, tmp_path):
    """Review F round 2 (N-M2, N-M1): a shared area owned per agent is not bound read-write as a whole: the wrapper binds only
    <area>/<agent> over the read-only room mount; the guard reads the owned areas from the protected record; each agent's simulation
    token comes from a directory outside the room."""
    spec = _spec(B, tmp_path)
    spec.owned_areas = ("src/brainir_causal/methods", "runs", "notes")
    m = _build(B, spec)
    room = spec.dest
    text = (room / "sbx").read_text(encoding="utf-8")
    assert "RW_PATHS=()" in text and "AGENT_AREAS=('.tmp')" in text
    assert "OWNED_AREAS=('src/brainir_causal/methods' 'runs' 'notes')" in text
    assert 'mounts+=(--mount "type=bind,source=$ROOM_MOUNT/$a/$area,target=/room/$a/$area")' in text
    assert "type=tmpfs,target=/room/$a," in text                        # only the PRIVATE areas are hidden behind a tmpfs
    tdir = B.token_dir(room)
    assert f"TOKEN_DIR='{B._posix(tdir)}'" in text and room not in tdir.parents and B.AUDIT in tdir.parents
    assert 'tok="$(tr -cd \'0-9a-f\' < "$TOKEN_DIR/$area.token")"' in text and "unset tok" in text
    prot = json.loads((B.AUDIT / f"protected_{room.name}.json").read_text(encoding="utf-8"))
    assert prot["owned_areas"] == ["src/brainir_causal/methods", "runs", "notes"] and prot["agent_areas"] == [".tmp"]
    assert m["sandbox"]["owned_areas"] == prot["owned_areas"] and m["sandbox"]["rw_areas"] == []
    for rel in ("runs/lin/exp.py", "notes/nn/n.md", "src/brainir_causal/methods/lin/__init__.py"):
        (room / rel).parent.mkdir(parents=True, exist_ok=True)
        (room / rel).write_text("x = 1\n", encoding="utf-8")
    assert B.scan(room, m, spec) == []                                  # the agents' own subdirectories are free work areas


def test_scan_finds_tampering_leaks_links_and_planted_files(B, tmp_path):
    import _winapi
    spec = _spec(B, tmp_path)
    m = _build(B, spec)
    room = spec.dest
    (room / "docs" / "PROTOCOL.md").write_text("changed\n", encoding="utf-8")
    (room / "stray.txt").write_text("x", encoding="utf-8")
    (room / "runs" / "x").mkdir(parents=True)
    (room / "runs" / "x" / "note.md").write_text(f"reading {REPO}\\{TV['answer_files'][0]}\n", encoding="utf-8")
    (room / "runs" / "x" / "CLAUDE.md").write_text("instructions\n", encoding="utf-8")
    (room / "runs" / "x" / "sitecustomize.py").write_text("import os\n", encoding="utf-8")
    (room / "runs" / "x" / "evil.pth").write_text("import os\n", encoding="utf-8")
    (room / "src" / "brainir_causal" / "__pycache__").mkdir()
    (room / "src" / "brainir_causal" / "__pycache__" / "api.cpython-312.pyc").write_bytes(b"\x00")
    (room / ".claude" / "settings.local.json").write_text("{}", encoding="utf-8")
    (room / ".tmp" / "a").mkdir(parents=True)
    (room / ".tmp" / "a" / ".claude").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _winapi.CreateJunction(str(outside), str(room / "runs" / "lnk"))
    probs = "\n".join(B.scan(room, m, spec))
    for needle in ("modified: docs/PROTOCOL.md", "unexpected file: stray.txt", "forbidden content in runs/x/note.md",
                   "unexpected file: .claude/settings.local.json", "link / junction: runs/lnk"):
        assert needle in probs, (needle, probs)
    planted = "\n".join(B.scan_planted(room, m))
    for needle in ("Claude control file: runs/x/CLAUDE.md", "Claude control file: .claude/settings.local.json",
                   "interpreter hook: runs/x/sitecustomize.py", "interpreter hook: runs/x/evil.pth",
                   "bytecode directory: src/brainir_causal/__pycache__", "nested .claude directory: .tmp/a/.claude"):
        assert needle in planted, (needle, planted)
    os.rmdir(room / "runs" / "lnk")


def test_sync_updates_changed_sources_recovers_and_cleans_caches(B, tmp_path):
    spec = _spec(B, tmp_path)
    spec.manifest.parent.mkdir(parents=True, exist_ok=True)
    _build(B, spec)
    room = spec.dest
    (room / "src" / "brainir_causal" / "__pycache__").mkdir()
    (room / "src" / "brainir_causal" / "__pycache__" / "api.cpython-312.pyc").write_bytes(b"\x00")
    src = B.ROOT / "phase4" / "src" / "brainir_causal" / "api.py"
    src.write_text("class CausalStateModel:\n    version = 2\n", encoding="utf-8")
    r = B.sync(spec, room, "api v2", protect=False)
    assert r["changed"] == ["src/brainir_causal/api.py"] and r["caches_removed"] >= 1
    assert not (room / "src" / "brainir_causal" / "__pycache__").exists()
    man = json.loads(spec.manifest.read_text(encoding="utf-8"))
    assert man["syncs"][-1]["reason"] == "api v2"
    # interrupted sync: the file was copied but the manifest was not written
    src.write_text("class CausalStateModel:\n    version = 3\n", encoding="utf-8")
    (room / "src" / "brainir_causal" / "api.py").write_bytes(src.read_bytes())
    assert "modified: src/brainir_causal/api.py" in "\n".join(B.scan(room, json.loads(spec.manifest.read_text(encoding="utf-8")), spec))
    r = B.sync(spec, room, "recover", protect=False)
    assert r["changed"] == ["src/brainir_causal/api.py"]
    assert B.scan(room, json.loads(spec.manifest.read_text(encoding="utf-8")), spec) == []
    # a refused source is never synced
    spec.items.append(B.Item(TV["answer_files"][0], "docs/report.md", "x", "x"))
    with pytest.raises(SystemExit):
        B.sync(spec, room, "bad", protect=False)


def test_redacted_copies_record_source_hashes_only_outside(B, tmp_path):
    spec = _spec(B, tmp_path, name="review")
    spec.items.append(B.Item("phase4/src/brainir_causal/orch.py", "extra/brainir_causal/orch.py", "orchestrator module", "orchestrator-code",
                             redact=True))
    spec.names_orchestrator_exempt = ("extra/",)
    m = _build(B, spec)
    e = next(e for e in m["files"] if e["path"] == "extra/brainir_causal/orch.py")
    assert e["redacted_lines"] == 1 and "source_sha256" in e
    inroom = (spec.dest / "CLEANROOM_MANIFEST.json").read_text(encoding="utf-8")
    assert "source_sha256" not in inroom and e["source_sha256"] not in inroom
    assert B.REDACTED in (spec.dest / "extra" / "brainir_causal" / "orch.py").read_text(encoding="utf-8")


def test_audit_lists_unmanifested_files(B, tmp_path):
    spec = _spec(B, tmp_path)
    _build(B, spec)
    (spec.dest / "runs" / "a.py").write_text("x = 1\n", encoding="utf-8")
    rep = B.audit(spec, spec.dest)
    assert rep["ok"] and "runs/a.py" in rep["unmanifested"] and rep["unmanifested_by_top"]["runs"] == 1


def test_free_workspace_room(B, tmp_path):
    spec = _spec(B, tmp_path, work_areas=None, name="bench")
    spec.seed_files = ("calibration_report.json",)
    m = _build(B, spec)
    assert (spec.dest / "calibration_report.json").exists() and "calibration_report.json" not in {e["path"] for e in m["files"]}
    (spec.dest / "p4synth").mkdir()
    (spec.dest / "p4synth" / "systems.py").write_text("x = 1\n", encoding="utf-8")
    assert B.scan(spec.dest, m, spec) == []                     # the author's own files are free (but still content-scanned)
    (spec.dest / "p4synth" / "leak.md").write_text(f"{WORD}\n", encoding="utf-8")
    assert any("forbidden content" in p for p in B.scan(spec.dest, m, spec))
    (spec.dest / "docs" / "extra.md").write_text("x\n", encoding="utf-8")                # inside an orchestrator entry
    assert any("unexpected file: docs/extra.md" in p for p in B.scan(spec.dest, m, spec))
    text = (spec.dest / "sbx").read_text(encoding="utf-8")
    assert "FREE_ROOM=1" in text and "RW_PATHS=()" in text and "'docs'" in text and "'CLAUDE.md'" in text


def test_real_room_specs_are_consistent():
    b = _load("p4builder_real", REPO / "scripts" / "make_phase4_cleanroom.py")
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
    assert b.rw_areas(rooms["clean"]) == []                     # every shared work area is owned per agent (review F round 2, N-M2)
    assert rooms["clean"].owned_areas == ("src/brainir_causal/methods", "tests/methods", "runs", "notes")
    assert rooms["clean"].agent_areas == (".tmp", "simq")
    assert b.rw_areas(rooms["review"]) == [] and rooms["review"].owned_areas == ("reviews", "runs", "notes")
    for rs in rooms.values():
        assert set(rs.owned_areas) <= {w.rstrip("/") for w in (rs.work_areas or ())}, rs.name
        assert not set(rs.owned_areas) & set(rs.agent_areas), rs.name
    review = {it.path for it in rooms["review"].items}
    assert "extra/scripts/devrun4_site/sitecustomize.py" in review and "extra/scripts/p4config/names.py" in review
    assert not any("canary" in p for p in review)
    placeholder = next(it for it in rooms["review"].items if it.path == "extra/scripts/p4config/names.py").content
    assert b.scan_text(placeholder) is None


def test_builder_and_tests_carry_no_names():
    b = _load("p4builder_scan", REPO / "scripts" / "make_phase4_cleanroom.py")
    for f in ("scripts/make_phase4_cleanroom.py", "phase4/tests/test_room_builder.py", "phase4/tests/test_room_acl.py",
              "scripts/p4/devrun4.py", "scripts/p4/devrun4_site/sitecustomize.py", "phase4/src/brainir_causal/systems.py"):
        hits = [(i, h) for i, line in enumerate((REPO / f).read_text(encoding="utf-8").split("\n"), 1) if (h := b.scan_text(line))]
        assert not hits, (f, hits)


def test_trees_skip_transients_and_sync_purges_and_removes_stale_files(B, tmp_path):
    data = B.ROOT / "data" / "toyset"
    (data / "sys1").mkdir(parents=True)
    (data / "sys1" / "index.jsonl").write_text('{"k": 1}\n', encoding="utf-8")
    (data / ".partial_upload.tar").write_bytes(b"x" * 10)
    (data / "sys1" / "pool.npz.tmp").write_bytes(b"x")
    items = B._tree("data/toyset", "data/toy", "toy data", "benchmark-public")
    assert [it.path for it in items] == ["data/toy/sys1/index.jsonl"]                # no hidden / transient file
    spec = _spec(B, tmp_path)
    spec.items += items
    spec.manifest.parent.mkdir(parents=True, exist_ok=True)
    _build(B, spec)
    room = spec.dest
    (data / "sys1" / "index.jsonl").write_text('{"k": 2}\n', encoding="utf-8")
    (data / "sys2").mkdir()
    (data / "sys2" / "index.jsonl").write_text('{"k": 3}\n', encoding="utf-8")
    spec.items = [it for it in spec.items if not it.path.startswith("data/")] + B._tree("data/toyset", "data/toy", "toy", "benchmark-public")
    r = B.sync(spec, room, "rebuild the toy copy", protect=False, purge=("data/toy",))
    assert set(r["removed"]) == {"data/toy/sys1/index.jsonl"} and set(r["changed"]) >= {"data/toy/sys1/index.jsonl", "data/toy/sys2/index.jsonl"}
    assert (room / "data" / "toy" / "sys1" / "index.jsonl").read_text(encoding="utf-8") == '{"k": 2}\n'
    spec.items = [it for it in spec.items if it.path != "data/toy/sys2/index.jsonl"]                 # an item leaves the allowlist
    r = B.sync(spec, room, "drop sys2", protect=False)
    assert r["removed"] == ["data/toy/sys2/index.jsonl"] and not (room / "data" / "toy" / "sys2").exists()
    assert B.scan(room, json.loads(spec.manifest.read_text(encoding="utf-8")), spec) == []
    with pytest.raises(SystemExit):
        B.sync(spec, room, "bad purge", protect=False, purge=("runs",))                                   # a work area


def test_binary_sources_are_scanned(B, tmp_path):
    import io
    import zipfile
    import numpy as np
    good, bad, raw = B.ROOT / "good.npz", B.ROOT / "bad.npz", B.ROOT / "raw.bin"
    np.savez_compressed(good, x=np.arange(10))
    buf = io.BytesIO()
    np.savez_compressed(buf, x=np.arange(3), meta=np.array([f"simulator {N.DATASET_WORDS[1]}_rate_v1"]))
    bad.write_bytes(buf.getvalue())
    raw.write_bytes(b"\x00\x01" + N.DATASET_WORDS[1].encode() + b"\x02")
    spec = _spec(B, tmp_path)
    assert B.check_source(good, "data/good.npz", spec) is None
    assert "binary" in B.check_source(bad, "data/bad.npz", spec)
    assert "binary" in B.check_source(raw, "data/raw.bin", spec)
    short = [w for w in N.DATASET_WORDS if len(w) < B.BINARY_MIN_HIT][0]
    raw.write_bytes(b"\x00" + short.encode() + b"\x00")                    # short words are not searched in binary data
    assert B.check_source(raw, "data/raw.bin", spec) is None
    assert all(len(a) >= B.BINARY_MIN_HIT for a in B.BINARY_ANCHORS)
    import time
    blob = B.ROOT / "big.bin"
    blob.write_bytes(os.urandom(4_000_000))
    t0 = time.perf_counter()
    assert B.check_source(blob, "data/big.bin", spec) is None                 # fast and no false positive on random bytes
    assert time.perf_counter() - t0 < 2.0


def test_every_method_room_module_passes_the_builders_source_check():
    """Every module the clean room lists (src/brainir_causal/*.py, incl. the cost ledger and the public sampler) passes check_source for
    that room, so the method room can be built as specified (review F round 3b, NF-2)."""
    b = _load("p4builder_modules", REPO / "scripts" / "make_phase4_cleanroom.py")
    clean = b.room_specs()["clean"]
    mods = [it for it in clean.items if it.source and it.path.startswith("src/brainir_causal/") and it.path.endswith(".py")]
    names = {it.path.rsplit("/", 1)[-1][:-3] for it in mods}
    assert {"accounting", "sampling", "refs", "loop", "designers"} <= names and "suites" not in names
    bad = {it.path: b.check_source(REPO / it.source, it.path, clean, it.redact) for it in mods}
    assert not {k: v for k, v in bad.items() if v}, bad
