"""OS-level immutability of room files (early review F, F-B4 a): the NTFS deny ACEs the room builder sets on every allowlisted file and
directory and on the outside sbx copy (scripts/p4agent/ntfs_protect.py).

An agent-like process (another process of the same Windows user: Python, the Git Bash file tools, a Docker sandbox container) cannot
write, append, rename, delete or create files under a protected path, and the agent's command routes to ACL tools (icacls, PowerShell,
host interpreters) are refused by the guard; reads keep working; the builder removes and restores the ACEs around a sync and before
deleting a room. Residual (LEAKAGE_POLICY.md section 4): the OWNER keeps an implicit WRITE_DAC, so a same-user process that is NOT
under the guard could edit the ACL; room agents have no such process.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.name != "nt", reason="NTFS only")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


ACL = _load("p4_ntfs_under_test", REPO / "scripts" / "p4agent" / "ntfs_protect.py") if os.name == "nt" else None

PROBE = r"""
import json, os, sys
d = sys.argv[1]
res = {}
def t(name, fn):
    try:
        fn(); res[name] = "ALLOWED"
    except OSError as e:
        res[name] = f"refused({e.errno})"
t("read", lambda: open(os.path.join(d, "a.md")).read())
t("list", lambda: os.listdir(os.path.join(d, "docs")))
t("write", lambda: open(os.path.join(d, "a.md"), "w").write("x"))
t("append", lambda: open(os.path.join(d, "a.md"), "a").write("x"))
t("rename", lambda: os.replace(os.path.join(d, "a.md"), os.path.join(d, "renamed.md")))
t("delete", lambda: os.remove(os.path.join(d, "docs", "b.md")))
t("new_file_in_dir", lambda: open(os.path.join(d, "docs", "new.md"), "w").write("x"))
t("rename_dir", lambda: os.replace(os.path.join(d, "docs"), os.path.join(d, "docs2")))
t("set_readonly_attr", lambda: os.chmod(os.path.join(d, "a.md"), 0o444))
t("work_write", lambda: open(os.path.join(d, "runs", "w.txt"), "w").write("x"))
t("new_top_level_entry", lambda: open(os.path.join(d, "new_top.txt"), "w").write("x"))
t("replace_via_rename", lambda: (open(os.path.join(d, "runs", "evil.md"), "w").write("evil"),
                                 os.replace(os.path.join(d, "runs", "evil.md"), os.path.join(d, "a.md"))))
print(json.dumps(res))
"""


def _tree(tmp_path) -> Path:
    d = tmp_path / "BrainIR_p4acltest"
    (d / "docs").mkdir(parents=True)
    (d / "runs").mkdir()
    (d / "a.md").write_text("original\n", encoding="utf-8")
    (d / "docs" / "b.md").write_text("original\n", encoding="utf-8")
    return d


def _protected(d: Path) -> list:
    """As the builder does: files FILE_MASK, an orchestrator directory DIR_MASK, and the room root (open for new entries)
    PARENT_MASK, because NTFS lets FILE_DELETE_CHILD on a parent delete, rename or replace a file whose own DELETE is denied."""
    return [(str(d / "a.md"), ACL.FILE_MASK), (str(d / "docs"), ACL.DIR_MASK), (str(d / "docs" / "b.md"), ACL.FILE_MASK),
            (str(d), ACL.PARENT_MASK)]


def test_protected_paths_refuse_every_write_of_another_process_but_not_reads(tmp_path):
    d = _tree(tmp_path)
    try:
        assert ACL.protect_paths(_protected(d)) == 4
        assert ACL.check_paths(_protected(d)) == []
        assert ACL.deny_mask_of(str(d / "a.md")) == ACL.FILE_MASK and ACL.deny_mask_of(str(d / "docs")) == ACL.DIR_MASK
        out = subprocess.run([sys.executable, "-c", PROBE, str(d)], capture_output=True, text=True, timeout=60)
        res = json.loads(out.stdout.strip().splitlines()[-1])
        assert res["read"] == res["list"] == res["work_write"] == res["new_top_level_entry"] == "ALLOWED", res
        for k in ("write", "append", "rename", "delete", "new_file_in_dir", "rename_dir", "set_readonly_attr", "replace_via_rename"):
            assert res[k].startswith("refused"), (k, res)
        assert (d / "a.md").read_text(encoding="utf-8") == "original\n"
    finally:
        ACL.unprotect_paths(_protected(d))
    # the builder (the owner) removes the ACEs and writes again
    assert ACL.check_paths(_protected(d)) == [p for p, _ in _protected(d)]
    (d / "a.md").write_text("changed by the builder\n", encoding="utf-8")
    shutil.rmtree(d)


def test_git_bash_file_tools_cannot_modify_protected_files(tmp_path):
    bash = shutil.which("bash") or r"C:\Program Files\Git\bin\bash.exe"
    if not Path(bash).exists():
        pytest.skip("Git Bash not available")
    d = _tree(tmp_path)
    ACL.protect_paths(_protected(d))
    try:
        cmds = {"cp": "cp runs/../a.md docs/b.md", "sort_o": "sort -o a.md docs/b.md", "sed_i": "sed -i s/o/x/ a.md",
                "sed_w": "sed -n 'w a.md' docs/b.md", "redirect": "echo x >> a.md", "mv": "mv a.md runs/a.md", "rm": "rm docs/b.md",
                "touch_new": "touch docs/new.md", "tee": "echo x | tee a.md"}
        for name, c in cmds.items():
            subprocess.run([bash, "-c", c], cwd=str(d), capture_output=True, text=True, timeout=60)
            assert (d / "a.md").read_text(encoding="utf-8") == "original\n", name
            assert (d / "docs" / "b.md").read_text(encoding="utf-8") == "original\n", name
            assert not (d / "docs" / "new.md").exists() and (d / "a.md").exists(), name
    finally:
        ACL.unprotect_paths(_protected(d))


def test_the_agents_routes_to_acl_tools_are_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("P4_CLEAN_ROOT", str(tmp_path))
    monkeypatch.setenv("P4_AUDIT_DIR", str(tmp_path / "audit"))
    g = _load("p4guard_acltest", REPO / "scripts" / "p4agent" / "guard_hook.py")
    for c in ("icacls a.md /grant Everyone:F", "icacls a.md /reset", "cacls a.md /e /g x:f", "takeown /f a.md", "attrib -r a.md",
              "powershell -c Set-Acl a.md", "python -c \"import ctypes\"", "sbx icacls a.md", "cmd /c icacls a.md"):
        ok, why = g.decide({"tool_name": "Bash", "tool_input": {"command": c}, "cwd": str(tmp_path)})
        if c.startswith("sbx "):
            continue                                  # (inside the Linux sandbox there is no NTFS ACL tool; see the container test)
        assert not ok, c
    assert not g.decide({"tool_name": "PowerShell", "tool_input": {"command": "Get-Acl a.md"}, "cwd": str(tmp_path)})[0]


def _docker_image() -> str | None:
    try:
        img = json.loads((REPO / "docker" / "p4sandbox" / "image.json").read_text(encoding="utf-8"))["id"]
        out = subprocess.run(["docker", "image", "inspect", img, "--format", "{{.Id}}"], capture_output=True, text=True, timeout=60)
        return img if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, KeyError, ValueError):
        return None


def test_sandbox_containers_cannot_modify_protected_files_even_through_a_writable_mount(tmp_path):
    img = _docker_image()
    if img is None:
        pytest.skip("Docker or the sandbox image is not available")
    d = _tree(tmp_path)
    ACL.protect_paths(_protected(d))
    script = ("import json, os\nres = {}\n"
              "def t(n, f):\n    try:\n        f(); res[n] = 'ALLOWED'\n    except OSError as e:\n        res[n] = 'refused'\n"
              "t('read', lambda: open('/r/a.md').read())\n"
              "t('write', lambda: open('/r/a.md', 'w').write('x'))\n"
              "t('append', lambda: open('/r/a.md', 'a').write('x'))\n"
              "t('rename', lambda: os.rename('/r/a.md', '/r/x.md'))\n"
              "t('unlink', lambda: os.unlink('/r/docs/b.md'))\n"
              "t('newfile', lambda: open('/r/docs/n.md', 'w').write('x'))\n"
              "t('chmod', lambda: os.chmod('/r/a.md', 0o777))\n"
              "t('work', lambda: open('/r/runs/w.txt', 'w').write('x'))\n"
              "print(json.dumps(res))\n")
    try:
        out = subprocess.run(["docker", "run", "--rm", "--network", "none", "--user", "1000:1000", "--pull", "never",
                              "--mount", f"type=bind,source={d.as_posix()},target=/r", img, "python", "-c", script],
                             capture_output=True, text=True, timeout=300, env=dict(os.environ, MSYS_NO_PATHCONV="1"))
        res = json.loads(out.stdout.strip().splitlines()[-1])
        assert res["read"] == "ALLOWED" and res["work"] == "ALLOWED", res
        for k in ("write", "append", "rename", "unlink", "newfile"):
            assert res[k] == "refused", (k, res)
        assert (d / "a.md").read_text(encoding="utf-8") == "original\n"
        assert ACL.check_paths(_protected(d)) == []                     # a container chmod cannot remove the NTFS ACE
    finally:
        ACL.unprotect_paths(_protected(d))


def test_builder_protects_syncs_and_destroys(tmp_path, monkeypatch):
    b = _load("p4builder_acl", REPO / "scripts" / "make_phase4_cleanroom.py")
    fake = tmp_path / "repo"
    for rel, text in {"phase4/src/brainir_causal/api.py": "x = 1\n", "research/phase4/contracts/room_CLAUDE.md": "# rules\n"}.items():
        (fake / rel).parent.mkdir(parents=True, exist_ok=True)
        (fake / rel).write_text(text, encoding="utf-8")
    monkeypatch.setattr(b, "ROOT", fake)
    monkeypatch.setattr(b, "AUDIT", tmp_path / "audit")
    monkeypatch.setattr(b, "P4", tmp_path / "p4research")
    items = b._isolation_items("research/phase4/contracts/room_CLAUDE.md", None) + [
        b.Item("phase4/src/brainir_causal/api.py", "src/brainir_causal/api.py", "public module", "generic-public")]
    spec = b.RoomSpec("clean", tmp_path / "BrainIR_p4acl", tmp_path / "manifests" / "M.json", items, ("runs/", ".tmp/"),
                      dirs=("runs", ".tmp"))
    m = b.build(spec, spec.dest, docker_check=False, protect=True)
    room = spec.dest
    assert m["acl"]["enabled"] and b.check_protection(spec, room, m) == []
    for p in ("CLAUDE.md", "CLAUDE.local.md", ".mcp.json", "sbx", "CLEANROOM_MANIFEST.json", "src/brainir_causal/api.py"):
        assert ACL.is_protected(str(room / p)), p
    for p in ("", "src", "src/brainir_causal", ".claude"):
        assert ACL.is_protected(str(room / p)), p                         # the root of a room with declared work areas included
    assert ACL.is_protected(str(b.AUDIT / "sbx_bin" / room.name / "sbx"))
    assert ACL.deny_mask_of(str(room / "runs")) == ACL.deny_mask_of(str(room / ".tmp")) == ACL.ANCHOR_MASK   # work-area roots:
    (room / ".tmp" / "agent").mkdir()                                                   # fixed in place, their content free
    with pytest.raises(PermissionError):
        (room / "src" / "brainir_causal" / "api.py").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(PermissionError):
        (room / "new_top.txt").write_text("x", encoding="utf-8")
    (room / "runs" / "ok.txt").write_text("work areas stay writable\n", encoding="utf-8")
    # sync: lift, copy, protect again
    (fake / "phase4" / "src" / "brainir_causal" / "api.py").write_text("x = 2\n", encoding="utf-8")
    r = b.sync(spec, room, "api v2")
    assert r["changed"] == ["src/brainir_causal/api.py"]
    assert (room / "src" / "brainir_causal" / "api.py").read_text(encoding="utf-8") == "x = 2\n"
    m2 = json.loads(spec.manifest.read_text(encoding="utf-8"))
    assert m2["acl"]["enabled"] and b.check_protection(spec, room, m2) == [] and b.scan(room, m2, spec) == []
    # a removed ACE is reported by --check
    ACL.unprotect(str(room / "sbx"))
    assert any("OS protection missing" in p and p.endswith("sbx") for p in b.check_protection(spec, room, m2))
    # destroy lifts every ACE first
    b.destroy(spec, room)
    assert not room.exists()
