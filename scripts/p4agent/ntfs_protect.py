"""OS-level immutability of room files: NTFS deny ACEs for Everyone (early review F, finding F-B4; LEAKAGE_POLICY.md section 2).

The room builder calls `protect_paths` after a build / sync and `unprotect_paths` / `unprotect_tree` before it changes anything;
`check_paths` verifies that every protected path still carries its ACE (room check / audit, launcher, guard for the outside sbx).

Rights denied to Everyone (S-1-1-0), non-inherited, exactly (no SYNCHRONIZE, no READ_CONTROL, so reads keep working):
    FILE_MASK    files: FILE_WRITE_DATA | FILE_APPEND_DATA | FILE_WRITE_EA | FILE_WRITE_ATTRIBUTES | DELETE | WRITE_OWNER
    DIR_MASK     orchestrator directories: the same (no new file, no new subdirectory, no rename / delete of the directory itself)
                 | FILE_DELETE_CHILD (no deletion or rename of an entry)
    PARENT_MASK  directories that stay open for new entries but hold protected entries (the root of a free room, a work area that
                 holds a generated file): FILE_DELETE_CHILD | DELETE | WRITE_OWNER. NTFS lets a caller with FILE_DELETE_CHILD on the
                 PARENT delete or rename (and so replace) a file whose own DELETE is denied (measured: `sed -i` replaced a protected
                 file in an unprotected directory), so every protected entry's parent must deny FILE_DELETE_CHILD.
    ANCHOR_MASK  work-area roots: DELETE | WRITE_OWNER (the directory cannot be renamed or removed; its content stays free).
`icacls /deny ...:(W,D,...)` cannot be used: it always adds SYNCHRONIZE to the deny ACE, and a denied SYNCHRONIZE blocks every
synchronous open, i.e. READS (measured 2026-09-26).

WRITE_DAC is NOT denied: the OWNER of a file holds it implicitly, so a deny ACE does not take it away, except when an OWNER RIGHTS ACE
(S-1-3-4) is present (e.g. inherited from a directory Python created with mode 0o700), where it would lock the builder itself out
(measured). Residual (stated in LEAKAGE_POLICY.md section 4): a process of the same Windows user CAN therefore remove the ACE with an
ACL tool (icacls, PowerShell Set-Acl, a Python / .NET program). Room agents cannot run any such tool: the host guard refuses every
interpreter and every non-allowlisted command, and code in the Docker sandbox cannot change NTFS ACLs (Docker Desktop's file sharing
performs its accesses under the same ACL checks, so a container write to a protected file fails). `check_paths` detects a removed ACE.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
from pathlib import Path

if os.name != "nt":                                   # pragma: no cover - Windows only (rooms live on the Windows host)
    raise ImportError("ntfs_protect works on Windows only")

_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

SE_FILE_OBJECT = 1
DACL_SECURITY_INFORMATION = 0x00000004
FILE_WRITE_DATA, FILE_APPEND_DATA, FILE_WRITE_EA = 0x2, 0x4, 0x10
FILE_DELETE_CHILD, FILE_WRITE_ATTRIBUTES = 0x40, 0x100
DELETE, WRITE_DAC, WRITE_OWNER = 0x10000, 0x40000, 0x80000
FILE_MASK = FILE_WRITE_DATA | FILE_APPEND_DATA | FILE_WRITE_EA | FILE_WRITE_ATTRIBUTES | DELETE | WRITE_OWNER
DIR_MASK = FILE_MASK | FILE_DELETE_CHILD
PARENT_MASK = FILE_DELETE_CHILD | DELETE | WRITE_OWNER
ANCHOR_MASK = DELETE | WRITE_OWNER
NO_INHERITANCE = 0
DENY_ACCESS, REVOKE_ACCESS = 3, 4
NO_MULTIPLE_TRUSTEE, TRUSTEE_IS_SID, TRUSTEE_IS_WELL_KNOWN_GROUP = 0, 0, 5
ACCESS_DENIED_ACE_TYPE = 1
EVERYONE_SID = "S-1-1-0"


class _TRUSTEE_W(ctypes.Structure):
    _fields_ = [("pMultipleTrustee", ctypes.c_void_p), ("MultipleTrusteeOperation", ctypes.c_int), ("TrusteeForm", ctypes.c_int),
                ("TrusteeType", ctypes.c_int), ("ptstrName", ctypes.c_void_p)]


class _EXPLICIT_ACCESS_W(ctypes.Structure):
    _fields_ = [("grfAccessPermissions", wt.DWORD), ("grfAccessMode", ctypes.c_int), ("grfInheritance", wt.DWORD),
                ("Trustee", _TRUSTEE_W)]


class _ACL_SIZE_INFORMATION(ctypes.Structure):
    _fields_ = [("AceCount", wt.DWORD), ("AclBytesInUse", wt.DWORD), ("AclBytesFree", wt.DWORD)]


class _ACE_HEADER(ctypes.Structure):
    _fields_ = [("AceType", ctypes.c_ubyte), ("AceFlags", ctypes.c_ubyte), ("AceSize", wt.WORD)]


class _ACCESS_DENIED_ACE(ctypes.Structure):
    _fields_ = [("Header", _ACE_HEADER), ("Mask", wt.DWORD), ("SidStart", wt.DWORD)]


_advapi32.ConvertStringSidToSidW.argtypes = [wt.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
_advapi32.ConvertStringSidToSidW.restype = wt.BOOL
_advapi32.GetNamedSecurityInfoW.argtypes = [wt.LPCWSTR, ctypes.c_int, wt.DWORD, ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
_advapi32.GetNamedSecurityInfoW.restype = wt.DWORD
_advapi32.SetNamedSecurityInfoW.argtypes = [wt.LPWSTR, ctypes.c_int, wt.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.c_void_p]
_advapi32.SetNamedSecurityInfoW.restype = wt.DWORD
_advapi32.SetEntriesInAclW.argtypes = [wt.ULONG, ctypes.POINTER(_EXPLICIT_ACCESS_W), ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
_advapi32.SetEntriesInAclW.restype = wt.DWORD
_advapi32.GetAclInformation.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.c_int]
_advapi32.GetAclInformation.restype = wt.BOOL
_advapi32.GetAce.argtypes = [ctypes.c_void_p, wt.DWORD, ctypes.POINTER(ctypes.c_void_p)]
_advapi32.GetAce.restype = wt.BOOL
_advapi32.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_advapi32.EqualSid.restype = wt.BOOL
_advapi32.InitializeAcl.argtypes = [ctypes.c_void_p, wt.DWORD, wt.DWORD]
_advapi32.InitializeAcl.restype = wt.BOOL
_advapi32.AddAce.argtypes = [ctypes.c_void_p, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD]
_advapi32.AddAce.restype = wt.BOOL
ACL_REVISION_DS = 4
MAXDWORD = 0xFFFFFFFF
_kernel32.LocalFree.argtypes = [ctypes.c_void_p]
_kernel32.LocalFree.restype = ctypes.c_void_p

_EVERYONE = ctypes.c_void_p()
if not _advapi32.ConvertStringSidToSidW(EVERYONE_SID, ctypes.byref(_EVERYONE)):     # pragma: no cover
    raise OSError(ctypes.get_last_error(), "ConvertStringSidToSidW failed")


def _ea(mode: int, mask: int) -> _EXPLICIT_ACCESS_W:
    t = _TRUSTEE_W(None, NO_MULTIPLE_TRUSTEE, TRUSTEE_IS_SID, TRUSTEE_IS_WELL_KNOWN_GROUP, _EVERYONE)
    return _EXPLICIT_ACCESS_W(mask, mode, NO_INHERITANCE, t)


def _apply(path: str, mode: int, mask: int) -> None:
    dacl, sd = ctypes.c_void_p(), ctypes.c_void_p()
    rc = _advapi32.GetNamedSecurityInfoW(path, SE_FILE_OBJECT, DACL_SECURITY_INFORMATION, None, None, ctypes.byref(dacl), None,
                                         ctypes.byref(sd))
    if rc:
        raise OSError(rc, f"GetNamedSecurityInfoW failed for {path}")
    try:
        ea = _ea(mode, mask)
        new = ctypes.c_void_p()
        rc = _advapi32.SetEntriesInAclW(1, ctypes.byref(ea), dacl, ctypes.byref(new))
        if rc:
            raise OSError(rc, f"SetEntriesInAclW failed for {path}")
        try:
            rc = _advapi32.SetNamedSecurityInfoW(path, SE_FILE_OBJECT, DACL_SECURITY_INFORMATION, None, None, new, None)
            if rc:
                raise OSError(rc, f"SetNamedSecurityInfoW failed for {path}")
        finally:
            _kernel32.LocalFree(new)
    finally:
        _kernel32.LocalFree(sd)


def deny_mask_of(path: str) -> int:
    """The combined mask of the explicit (non-inherited) deny ACEs for Everyone on path (0 = none)."""
    dacl, sd = ctypes.c_void_p(), ctypes.c_void_p()
    rc = _advapi32.GetNamedSecurityInfoW(path, SE_FILE_OBJECT, DACL_SECURITY_INFORMATION, None, None, ctypes.byref(dacl), None,
                                         ctypes.byref(sd))
    if rc:
        raise OSError(rc, f"GetNamedSecurityInfoW failed for {path}")
    try:
        if not dacl.value:
            return 0
        info = _ACL_SIZE_INFORMATION()
        if not _advapi32.GetAclInformation(dacl, ctypes.byref(info), ctypes.sizeof(info), 2):     # AclSizeInformation
            raise OSError(ctypes.get_last_error(), "GetAclInformation failed")
        mask = 0
        for i in range(info.AceCount):
            p = ctypes.c_void_p()
            if not _advapi32.GetAce(dacl, i, ctypes.byref(p)):
                continue
            ace = ctypes.cast(p, ctypes.POINTER(_ACCESS_DENIED_ACE)).contents
            if ace.Header.AceType != ACCESS_DENIED_ACE_TYPE or (ace.Header.AceFlags & 0x10):          # 0x10 = INHERITED_ACE
                continue
            sid = ctypes.c_void_p(p.value + _ACCESS_DENIED_ACE.SidStart.offset)
            if _advapi32.EqualSid(sid, _EVERYONE):
                mask |= ace.Mask
        return mask
    finally:
        _kernel32.LocalFree(sd)


def protect(path: str | Path, mask: int | None = None) -> None:
    """Deny `mask` (default: DIR_MASK for a directory, FILE_MASK for a file) to Everyone; an earlier ACE of ours is replaced."""
    p = str(Path(path))
    want = mask if mask is not None else (DIR_MASK if os.path.isdir(p) else FILE_MASK)
    have = deny_mask_of(p)
    if have == want:
        return
    if have:
        unprotect(p)
    _apply(p, DENY_ACCESS, want)


def unprotect(path: str | Path) -> None:
    """Remove every explicit (non-inherited) DENY ACE for Everyone: the DACL is rebuilt without them (SetEntriesInAcl's
    REVOKE_ACCESS removes allow ACEs only)."""
    p = str(Path(path))
    dacl, sd = ctypes.c_void_p(), ctypes.c_void_p()
    rc = _advapi32.GetNamedSecurityInfoW(p, SE_FILE_OBJECT, DACL_SECURITY_INFORMATION, None, None, ctypes.byref(dacl), None,
                                         ctypes.byref(sd))
    if rc:
        raise OSError(rc, f"GetNamedSecurityInfoW failed for {p}")
    try:
        if not dacl.value:
            return
        info = _ACL_SIZE_INFORMATION()
        if not _advapi32.GetAclInformation(dacl, ctypes.byref(info), ctypes.sizeof(info), 2):
            raise OSError(ctypes.get_last_error(), "GetAclInformation failed")
        keep, drop = [], 0
        for i in range(info.AceCount):
            ap = ctypes.c_void_p()
            if not _advapi32.GetAce(dacl, i, ctypes.byref(ap)):
                raise OSError(ctypes.get_last_error(), "GetAce failed")
            ace = ctypes.cast(ap, ctypes.POINTER(_ACCESS_DENIED_ACE)).contents
            ours = (ace.Header.AceType == ACCESS_DENIED_ACE_TYPE and not (ace.Header.AceFlags & 0x10)
                    and _advapi32.EqualSid(ctypes.c_void_p(ap.value + _ACCESS_DENIED_ACE.SidStart.offset), _EVERYONE))
            if ours:
                drop += 1
            else:
                keep.append((ap.value, ace.Header.AceSize))
        if not drop:
            return
        size = 8 + sum(s for _, s in keep) + 8
        buf = ctypes.create_string_buffer(size)
        if not _advapi32.InitializeAcl(buf, size, ACL_REVISION_DS):
            raise OSError(ctypes.get_last_error(), "InitializeAcl failed")
        for addr, s in keep:
            if not _advapi32.AddAce(buf, ACL_REVISION_DS, MAXDWORD, ctypes.c_void_p(addr), s):
                raise OSError(ctypes.get_last_error(), "AddAce failed")
        rc = _advapi32.SetNamedSecurityInfoW(p, SE_FILE_OBJECT, DACL_SECURITY_INFORMATION, None, None, buf, None)
        if rc:
            raise OSError(rc, f"SetNamedSecurityInfoW failed for {p}")
    finally:
        _kernel32.LocalFree(sd)


def is_protected(path: str | Path, mask: int | None = None) -> bool:
    p = str(Path(path))
    want = mask if mask is not None else (DIR_MASK if os.path.isdir(p) else FILE_MASK)
    return (deny_mask_of(p) & want) == want


def _items(paths):
    """paths: plain paths (default mask by type) or (path, mask) pairs."""
    for x in paths:
        yield (str(x[0]), x[1]) if isinstance(x, tuple) else (str(x), None)


def protect_paths(paths) -> int:
    n = 0
    for p, mask in _items(paths):
        if os.path.lexists(p):
            protect(p, mask)
            n += 1
    return n


def unprotect_paths(paths) -> int:
    n = 0
    for p, _ in _items(paths):
        if os.path.lexists(p):
            try:
                unprotect(p)
                n += 1
            except OSError:
                pass
    return n


def check_paths(paths) -> list[str]:
    """Paths that exist but no longer carry their full deny ACE."""
    return [p for p, mask in _items(paths) if os.path.lexists(p) and not is_protected(p, mask)]


def unprotect_tree(root: str | Path) -> int:
    """Remove our ACE from root and everything below it (before deleting a room)."""
    n = 0
    root = Path(root)
    if not root.exists():
        return 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        for name in dirnames + filenames:
            q = os.path.join(dirpath, name)
            try:
                if deny_mask_of(q):
                    unprotect(q)
                    n += 1
            except OSError:
                pass
    try:
        if deny_mask_of(str(root)):
            unprotect(root)
            n += 1
    except OSError:
        pass
    return n
