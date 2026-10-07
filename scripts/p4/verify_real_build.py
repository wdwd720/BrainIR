"""Verify the downloaded PUBLIC real data of causal_state_v1 (ORCHESTRATOR SIDE; task: bit-identity and public policy).

    uv run --no-sync --project phase4 python scripts/p4/verify_real_build.py [--root data/phase4/real/real_public/public]
        [--records-per-system 2] [--pool-states-per-system 1] [--seed 0] [--workers 8] [--out FILE]

For every system of the public part:
  1. the whitelists (`suites.assert_public_part`: files, record / row / meta / info / pool / lift keys, public futures keys);
  2. the PUBLIC POLICY of every protocol: every row of the set (restart keys = the set's own store keys: 'obs.init' rows restart
     from nominal trajectories of the same set, LOG P4-D36) and every pool future (each state x each sequence, plus the floor
     repeat), rebuilt from pool.json (`suites.pool_future_protocol`) and checked with `simservice.check_public` (restart keys = the
     pool's own source trajectories); no row has an explicit initial state;
  2b. ONSET / TWIN (review H, N1): every intervention item equals its twin in x and y up to and including its onset sample;
  3. BIT-IDENTITY on this machine (a gated host, the development machine): a seeded random sample of stored records is re-simulated
     locally (`suites.SimContext`, fresh local store) and its x, u, y and store key compared with the stored ones; for a seeded sample
     of pool states the source trajectory is re-simulated and the stored futures (no intervention incl. x and u, one sequence, the floor
     repeat) are re-simulated from its restart and compared.
Appends its record to research/phase4/REAL_DATA_BUILD.json (or writes --out FILE); exit code 1 on any failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import protocol as P  # noqa: E402
from brainir_causal import suites as SU  # noqa: E402
from brainir_causal.simservice import check_public  # noqa: E402

DEFAULT_ROOT = ROOT / "data" / "phase4" / "real" / "real_public" / "public"
BUILD_RECORD = ROOT / "research" / "phase4" / "REAL_DATA_BUILD.json"


def policy_check(d: Path, pub: dict) -> dict:
    rows = [json.loads(line) for line in (d / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    bad = []
    own_keys = {r["meta"]["store_key"] for r in rows}
    for r in rows:
        q = P.validate(r["protocol"])
        why = check_public(q, pub, allowed_restart_keys=own_keys)
        if q["r0"]["kind"] == "state":
            why = why or "explicit initial state"
        if why:
            bad.append({"key": r["key"][:16], "why": why})
    n_fut = 0
    pj = d / "pools" / "pool.json"
    if pj.exists():
        pool = json.loads(pj.read_text(encoding="utf-8"))
        keys = {st["store_key"] for st in pool["states"]}
        floor_ids = set(pool.get("floor_states") or [])
        for st in pool["states"]:
            seqs = [[]] + [sq["events"] for sq in pool["sequences"].values()]
            protos = [SU.pool_future_protocol(pub, st, ev, pool["level"]) for ev in seqs]
            if st["state_id"] in floor_ids:
                protos.append(SU.pool_future_protocol(pub, st, [], pool["level"], floor=True))
            for q in protos:
                n_fut += 1
                why = check_public(P.validate(q), pub, allowed_restart_keys=keys)
                if why:
                    bad.append({"state": st["state_id"], "why": why})
    return {"rows": len(rows), "pool_futures": n_fut, "violations": len(bad), "first": bad[:5]}


def onset_check(d: Path) -> dict:
    """Every intervention item vs its twin up to and including the onset sample (stored observed arrays)."""
    rows = [json.loads(line) for line in (d / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    twins = {(r.get("meta") or {}).get("twin_of"): r for r in rows if r["split"] == "twin"}
    n = 0
    bad = []
    for r in rows:
        tw = twins.get(r["key"])
        if tw is None:
            continue
        n += 1
        a, b = _load(d, r["key"]), _load(d, tw["key"])
        why = SU.onset_mismatch(r["protocol"], (r.get("meta") or {}).get("model_events"), a, b)
        if why:
            bad.append({"key": r["key"][:16], "family": r["family"], "why": why})
    return {"items": n, "mismatches": len(bad), "first": bad[:5]}


def _load(d: Path, key: str) -> dict:
    with np.load(d / "traj" / f"{key}.npz") as z:
        return {k: z[k] for k in z.files}


def _same(a: np.ndarray, b: np.ndarray) -> bool:
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and np.array_equal(a.astype(np.float32), b.astype(np.float32))


def replay_system(sid: str, d: Path, internal: dict, *, n_rec: int, n_pool: int, rng: np.random.Generator, store_root: Path,
                  workers: int) -> dict:
    """Re-simulate a sample of the system's stored records and pool futures locally; compare bit for bit."""
    rows = [json.loads(line) for line in (d / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    pool = json.loads((d / "pools" / "pool.json").read_text(encoding="utf-8"))
    with np.load(d / "pools" / "futures.npz") as z:
        fut = {k: z[k] for k in z.files}
    by_key = {r["key"]: r for r in rows}
    by_store = {r["meta"]["store_key"]: r for r in rows}
    cand = [r for r in rows if r["split"] in ("train", "val", "test", "twin")]
    pick = [cand[i] for i in rng.choice(len(cand), size=min(n_rec, len(cand)), replace=False)]
    # restart records ('obs.init', pool 'init' sources) are replayed after their sources (fresh store)
    pre: list[dict] = []
    for r in pick:
        r0 = r["protocol"].get("r0") or {}
        if r0.get("kind") == "restart" and r0.get("key") in by_store and by_store[r0["key"]] not in pre:
            pre.append(by_store[r0["key"]])
    floor_ids = set(pool.get("floor_states") or [])
    states = [(si, st) for si, st in enumerate(pool["states"]) if st["state_id"] in floor_ids] or list(enumerate(pool["states"]))
    pstates = [states[i] for i in rng.choice(len(states), size=min(n_pool, len(states)), replace=False)]
    backend = SU.LocalBackend({sid: internal}, tier="real_public", seed=0, generator=None, store_root=store_root, workers=workers)
    out = {"records": [], "pool": []}
    try:
        pool_src = [by_key[st["key"]] for _, st in pstates]
        for r in pool_src:
            r0 = r["protocol"].get("r0") or {}
            if r0.get("kind") == "restart" and r0.get("key") in by_store and by_store[r0["key"]] not in pre:
                pre.append(by_store[r0["key"]])
        t0 = time.time()
        if pre:
            pres = backend.run([(sid, r["protocol"], {"role": "verify_source"}) for r in pre])
            out["sources_replayed"] = [{"key": r["key"][:16], "ok": ("error" not in g) and g["store_key"] == r["meta"]["store_key"]}
                                       for r, g in zip(pre, pres)]
        jobs = [(sid, r["protocol"], {"role": "verify"}) for r in pick]
        jobs += [(sid, r["protocol"], {"role": "verify_pool_src"}) for r in pool_src]
        res = backend.run(jobs)
        for r, got in zip(pick + [by_key[st["key"]] for _, st in pstates], res):
            if "error" in got:
                out["records"].append({"key": r["key"][:16], "ok": False, "error": got["error"][:300]})
                continue
            want = _load(d, r["key"])
            checks = {a: _same(got[a], want[a]) for a in ("x", "u", "y")}
            checks["t"] = bool(np.array_equal(np.asarray(got["t"], np.float64), want["t"]))
            checks["store_key"] = got["store_key"] == r["meta"]["store_key"]
            checks["dataset_key"] = got["key"] == r["key"]
            out["records"].append({"key": r["key"][:16], "split": r["split"], "family": r["family"], "ok": all(checks.values()), **checks})
        out["records_s"] = round(time.time() - t0, 1)
        seqs = pool["sequences"]
        jobs, owners = [], []
        for si, st in pstates:
            name1 = sorted(seqs)[0] if seqs else None
            for name, ev, floor in [("none", [], False)] + ([(name1, seqs[name1]["events"], False)] if name1 else []) + [("floor", [], True)]:
                if f"s{si}_{name}_y" not in fut:
                    continue
                jobs.append((sid, SU.pool_future_protocol(pub_of(d, sid), st, ev, pool["level"], floor=floor), {"role": "verify_future",
                                                                                                                "no_store": True}))
                owners.append((si, name))
        t1 = time.time()
        res = backend.run(jobs)
        for (si, name), got in zip(owners, res):
            if "error" in got:
                out["pool"].append({"state": si, "future": name, "ok": False, "error": got["error"][:300]})
                continue
            checks = {"y": _same(got["y"], fut[f"s{si}_{name}_y"])}
            if name == "none":
                checks["x"] = _same(np.asarray(got["x"])[: len(fut[f"s{si}_none_x"])], fut[f"s{si}_none_x"])
                if f"s{si}_none_u" in fut:
                    checks["u"] = _same(got["u"], fut[f"s{si}_none_u"])
            out["pool"].append({"state": si, "future": name, "restart": True, "ok": all(checks.values()), **checks})
        out["pool_s"] = round(time.time() - t1, 1)
    finally:
        backend.close()
    return out


_PUB: dict = {}


def pub_of(d: Path, sid: str) -> dict:
    if sid not in _PUB:
        _PUB[sid] = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["systems"][sid]
    return _PUB[sid]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--records-per-system", type=int, default=2)
    ap.add_argument("--pool-states-per-system", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--systems", default="")
    ap.add_argument("--skip-replay", action="store_true")
    ap.add_argument("--out", type=Path, default=None, help="write the record here instead of appending it to REAL_DATA_BUILD.json")
    args = ap.parse_args(argv)
    from brainir_causal.systems import load_real_internal
    internals = load_real_internal()
    sids = sorted(s for s in internals if (args.root / SU._safe(s) / "index.jsonl").exists())
    if args.systems:
        sids = [s for s in sids if s in set(args.systems.split(","))]
    if not sids:
        raise SystemExit(f"no public real system under {args.root}")
    rng = np.random.default_rng(args.seed)
    rr = args.root.resolve()
    root_rec = ("$DATA/" + rr.relative_to(ROOT / "data").as_posix()) if (ROOT / "data") in rr.parents else rr.name
    rec = {"what": "verification of the public real data", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "root": root_rec, "seed": args.seed, "systems": {}}
    from brainir_causal.p4modal.gate import host_fingerprint
    rec["host"] = host_fingerprint()
    ok_all = True
    with tempfile.TemporaryDirectory(prefix="p4verify_", dir=str(ROOT / "data" / "phase4")) as td:
        for sid in sids:
            d = args.root / SU._safe(sid)
            t0 = time.time()
            one = {"whitelists": SU.assert_public_part(d), "policy": policy_check(d, pub_of(d, sid)), "onset": onset_check(d)}
            if not args.skip_replay:
                one["replay"] = replay_system(sid, d, internals[sid], n_rec=args.records_per_system, n_pool=args.pool_states_per_system,
                                              rng=rng, store_root=Path(td) / SU._safe(sid), workers=args.workers)
            rp = one.get("replay") or {"records": [], "pool": []}
            one["ok"] = (one["policy"]["violations"] == 0 and one["onset"]["mismatches"] == 0 and all(r["ok"] for r in rp["records"])
                         and all(r["ok"] for r in rp["pool"]) and all(r["ok"] for r in rp.get("sources_replayed") or []))
            one["n_replayed"] = len(rp["records"]) + len(rp["pool"])
            one["seconds"] = round(time.time() - t0, 1)
            ok_all &= one["ok"]
            rec["systems"][sid] = one
            print(f"{sid}: ok={one['ok']} rows={one['policy']['rows']} futures={one['policy']['pool_futures']} "
                  f"violations={one['policy']['violations']} onset_items={one['onset']['items']} onset_mismatches={one['onset']['mismatches']} "
                  f"replayed={one['n_replayed']} ({one['seconds']} s)", flush=True)
    rec["n_replayed_total"] = sum(v["n_replayed"] for v in rec["systems"].values())
    rec["ok"] = bool(ok_all)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    else:
        runs = json.loads(BUILD_RECORD.read_text(encoding="utf-8"))["runs"] if BUILD_RECORD.exists() else []
        BUILD_RECORD.write_text(json.dumps({"runs": runs + [rec]}, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"ok": rec["ok"], "n_replayed_total": rec["n_replayed_total"]}), flush=True)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
