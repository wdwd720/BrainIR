"""Build the sandbox's seccomp profile: Docker's default profile (moby/profiles, seccomp/default.json, fetched 2026-09-26) with the
symbolic-link system calls removed (symlink, symlinkat -> EPERM). Hard links stay allowed: glibc sem_open (multiprocessing locks)
needs link(), and a hard link cannot leave the bind mount.

Why: code in a container can otherwise create symbolic links in the bind-mounted room, and Docker Desktop materialises them on the
Windows host as NTFS junctions that point OUTSIDE the room (tested 2026-09-26: a link to /c/Dev/BrainIR created in the container was
listable from the host). Host tools that follow such a junction would escape the room.

    python docker/p4sandbox/make_seccomp.py     # writes seccomp_nolinks.json + seccomp_nolinks.provenance.json
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "moby_seccomp_default.json"
BLOCK = ("symlink", "symlinkat")


def main() -> None:
    raw = SRC.read_bytes()
    prof = json.loads(raw)
    removed = 0
    for rule in prof["syscalls"]:
        if rule.get("action") == "SCMP_ACT_ALLOW":
            keep = [n for n in rule["names"] if n not in BLOCK]
            removed += len(rule["names"]) - len(keep)
            rule["names"] = keep
    prof["syscalls"] = [r for r in prof["syscalls"] if r["names"]]
    prof["syscalls"].append({"names": list(BLOCK), "action": "SCMP_ACT_ERRNO", "errnoRet": 1})
    out = HERE / "seccomp_nolinks.json"
    out.write_text(json.dumps(prof, indent=1) + "\n", encoding="utf-8", newline="\n")
    prov = {"source": "https://raw.githubusercontent.com/moby/profiles/main/seccomp/default.json", "fetched": "2026-09-26",
            "source_sha256": hashlib.sha256(raw).hexdigest(), "removed_from_allow_rules": removed, "errno_eperm": list(BLOCK),
            "output_sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
    (HERE / "seccomp_nolinks.provenance.json").write_text(json.dumps(prov, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(prov))


if __name__ == "__main__":
    main()
