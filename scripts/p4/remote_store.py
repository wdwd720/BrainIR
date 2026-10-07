"""Remote storage of large, rebuildable Phase 4 data in PRIVATE Hugging Face Storage Buckets (ORCHESTRATOR SIDE ONLY; the user's
directive of 2026-09-28: minimal local disk, no Modal; research/phase4/LOCAL_EXECUTION_PLAN.md section 7).

Runs OUTSIDE the project environment (the phase4 environment is hash-locked), with the orchestrator's own Hugging Face login:
    UVX=%LOCALAPPDATA%/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe/uvx.exe
    $UVX --from huggingface_hub python scripts/p4/remote_store.py push --prefix <p> --local <dir> [--evict]
    $UVX --from huggingface_hub python scripts/p4/remote_store.py pull --prefix <p> --local <dir> [--paths a,b]
    $UVX --from huggingface_hub python scripts/p4/remote_store.py ls [--prefix <p>]

TWO BUCKETS, SEPARATED BY RULE (goal5 sections 4-6: storage never widens access): `wdwd720/brainir-p4-public` holds ONLY material
that may enter a room (the dev tier's public part, public real data, archives of them); `wdwd720/brainir-p4-heldout` holds everything
else (val / conf tiers, eval and truth parts, real Level B / C sets, store records, calibration and run outputs). The bucket is chosen
from the prefix (`bucket_for`); a held-out prefix can never go to the public bucket. No agent ever gets a token: the buckets are read
and written only by this orchestrator script; rooms keep receiving data through the room builder from local copies.

VERIFICATION BEFORE ANY DELETION: every file's SHA256 and Xet content hash are computed locally; after the upload, the bucket's size
and Xet hash of every path must equal them (the Xet hash is a hash of the file's bytes, computed identically on both sides), and a
manifest {path: [sha256, bytes, xet]} is stored beside the data (<prefix>/_manifest.json) and locally under
research/phase4/remote_store/. `--evict` deletes the local files only when every file of the push verified. Content addressing: Xet
stores content by hash, so identical bytes (a re-pushed file, a file shared by two prefixes) are never uploaded twice; unchanged paths
are skipped. `pull` downloads and checks every file's SHA256 against the manifest (a mismatch is an error, the file is removed)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMESPACE = "wdwd720"
BUCKETS = {"public": f"{NAMESPACE}/brainir-p4-public", "heldout": f"{NAMESPACE}/brainir-p4-heldout"}
#: the ONLY prefixes the public bucket may hold (material that may enter a room)
PUBLIC_PREFIXES = ("tiers/dev/public/", "real/public/", "archive/dev_public_v3.2/", "archive/dev_public_interim/")
RECORDS = ROOT / "research" / "phase4" / "remote_store"
BATCH = 64


def bucket_for(prefix: str) -> str:
    p = prefix.strip("/") + "/"
    return BUCKETS["public"] if p.startswith(PUBLIC_PREFIXES) else BUCKETS["heldout"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def local_manifest(base: Path) -> dict:
    from hf_xet import hash_files
    files = sorted(p for p in base.rglob("*") if p.is_file() and not p.name.endswith((".part", ".tmp")))
    out = {}
    for i in range(0, len(files), 256):
        chunk = files[i: i + 256]
        xs = hash_files([str(p) for p in chunk])
        for p, x in zip(chunk, xs, strict=True):
            out[p.relative_to(base).as_posix()] = [_sha256(p), int(x.file_size), str(x.hash)]
    return out


def remote_info(api, bucket: str, paths: list[str]) -> dict:
    out = {}
    for i in range(0, len(paths), 500):
        for f in api.get_bucket_paths_info(bucket, paths[i: i + 500]):
            out[f.path] = (int(f.size), str(f.xet_hash))
    return out


def _record(bucket: str, prefix: str, rec: dict) -> None:
    d = RECORDS / bucket.split("/")[1]
    d.mkdir(parents=True, exist_ok=True)
    (d / (prefix.strip("/").replace("/", "__") + ".json")).write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")


def cmd_push(args) -> int:
    import huggingface_hub as h
    api = h.HfApi()
    base, prefix = Path(args.local), args.prefix.strip("/")
    bucket = bucket_for(prefix)
    if args.bucket and BUCKETS[args.bucket] != bucket:
        raise SystemExit(f"prefix {prefix!r} belongs in {bucket}, not {BUCKETS[args.bucket]} (public / held-out separation)")
    if not base.is_dir():
        raise SystemExit(f"{base} is not a directory")
    info = api.bucket_info(bucket)
    if not info.private:
        raise SystemExit(f"{bucket} is not private: refusing to upload")
    t0 = time.time()
    man = local_manifest(base)
    paths = {rel: f"{prefix}/{rel}" for rel in man}
    have = remote_info(api, bucket, list(paths.values()))
    todo = [rel for rel, (sha, size, xet) in man.items() if have.get(paths[rel]) != (size, xet)]
    for i in range(0, len(todo), BATCH):
        api.batch_bucket_files(bucket, add=[(str(base / rel), paths[rel]) for rel in todo[i: i + BATCH]])
        print(f"  uploaded {min(i + BATCH, len(todo))} / {len(todo)} files", flush=True)
    have = remote_info(api, bucket, list(paths.values()))
    bad = sorted(rel for rel, (sha, size, xet) in man.items() if have.get(paths[rel]) != (size, xet))
    mjson = json.dumps({"prefix": prefix, "files": man}, indent=0, sort_keys=True).encode()
    api.batch_bucket_files(bucket, add=[(mjson, f"{prefix}/_manifest.json")])
    rec = {"bucket": bucket, "prefix": prefix, "local": str(base), "files": len(man), "bytes": sum(v[1] for v in man.values()),
           "uploaded": len(todo), "skipped_unchanged": len(man) - len(todo), "verified": not bad, "mismatch": bad[:20],
           "wall_s": round(time.time() - t0, 1), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "evicted": False}
    if args.evict and not bad:
        for rel in man:
            (base / rel).unlink()
        for d in sorted((p for p in base.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
            try:
                d.rmdir()
            except OSError:
                pass
        rec["evicted"] = True
    _record(bucket, prefix, dict(rec, manifest=man))
    print(json.dumps(rec), flush=True)
    return 0 if not bad else 1


def cmd_pull(args) -> int:
    import huggingface_hub as h
    api = h.HfApi()
    prefix, base = args.prefix.strip("/"), Path(args.local)
    bucket = bucket_for(prefix)
    tmp = base / ".manifest.tmp"
    base.mkdir(parents=True, exist_ok=True)
    api.download_bucket_files(bucket, [(f"{prefix}/_manifest.json", str(tmp))], raise_on_missing_files=True)
    man = json.loads(tmp.read_text(encoding="utf-8"))["files"]
    tmp.unlink()
    want = [p for p in (args.paths.split(",") if args.paths else man) if p]
    todo = [rel for rel in want if not ((base / rel).exists() and _sha256(base / rel) == man[rel][0])]
    for i in range(0, len(todo), BATCH):
        part = todo[i: i + BATCH]
        for rel in part:
            (base / rel).parent.mkdir(parents=True, exist_ok=True)
        api.download_bucket_files(bucket, [(f"{prefix}/{rel}", str(base / rel)) for rel in part], raise_on_missing_files=True)
    bad = []
    for rel in todo:
        if _sha256(base / rel) != man[rel][0]:
            (base / rel).unlink(missing_ok=True)
            bad.append(rel)
    print(json.dumps({"bucket": bucket, "prefix": prefix, "requested": len(want), "downloaded": len(todo), "sha256_ok": not bad,
                      "bad": bad[:20]}), flush=True)
    return 0 if not bad else 1


def cmd_ls(args) -> int:
    import huggingface_hub as h
    api = h.HfApi()
    for key, b in BUCKETS.items():
        i = api.bucket_info(b)
        print(f"{b}: private={i.private} files={i.total_files} bytes={i.size}")
        if args.prefix and bucket_for(args.prefix) == b:
            for f in api.list_bucket_tree(b, prefix=args.prefix.strip("/"), recursive=False):
                print("  ", getattr(f, "path", f), getattr(f, "size", ""))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("push")
    p.add_argument("--prefix", required=True)
    p.add_argument("--local", required=True)
    p.add_argument("--bucket", choices=sorted(BUCKETS), default=None, help="optional: assert the bucket the prefix maps to")
    p.add_argument("--evict", action="store_true", help="delete the local files once EVERY file verified remotely")
    q = sub.add_parser("pull")
    q.add_argument("--prefix", required=True)
    q.add_argument("--local", required=True)
    q.add_argument("--paths", default="")
    s = sub.add_parser("ls")
    s.add_argument("--prefix", default="")
    args = ap.parse_args(argv)
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    return {"push": cmd_push, "pull": cmd_pull, "ls": cmd_ls}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
