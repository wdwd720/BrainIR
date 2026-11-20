"""Local side of the GitHub Actions campaigns (run 2, LOG L50; prompt section 4). Modal is not used in run 2.

A campaign is packed locally into `data/ledger/gha/<name>/` (manifest, run-1-style shared payloads, chunks of jobs), published
as the assets of a GitHub release `ledgerdata-<name>` (inputs only: public connectome matrices and job specs, no result), and
started by pushing the tag `gha-run-<name>` ALONE (the workflow `.github/workflows/ledger-gha.yml` runs one matrix job per
chunk). Each chunk's results come back as an artifact encrypted to `.github/ledger_gha_pub.pem` (hybrid AES-256 + RSA-OAEP); the
private key lives only in `data/cache/ledger_gha_key/` (git-ignored). `collect` downloads, decrypts, checks every key against
the manifest and appends new results to the append-only log `data/ledger/<area>/<name>/results.pkl` (run 1 format).

    uv run --project ledger --no-sync python ledger/scripts/gha.py pack trust          # the trust gate sample (prompt section 4)
    uv run --project ledger --no-sync python ledger/scripts/gha.py publish trust
    uv run --project ledger --no-sync python ledger/scripts/gha.py collect trust [--wait]
    uv run --project ledger --no-sync python ledger/scripts/gha.py trust-compare
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "ledger" / "src"))
sys.path.insert(0, str(HERE))
from brainir.compute.backend import pack_shared  # noqa: E402
from brainir_ledger import data_dir  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

GHA = data_dir() / "gha"
KEY = REPO / "data" / "cache" / "ledger_gha_key" / "private.pem"
OPENSSL = "/opt/homebrew/bin/openssl"
TRUST_SEED = 20261201


def sh(*args, check=True, capture=True) -> str:
    r = subprocess.run(list(args), cwd=REPO, capture_output=capture, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}: {r.stderr.strip()[-800:]}")
    return (r.stdout or "").strip()


# ----------------------------------------------------------------------------------------------------- campaign builders
def build_trust() -> tuple[list[tuple[dict, list[dict]]], str]:
    """100 locked run 1 jobs spread over the arms, plus full-cord DNg100 seeds of gate G3 (seeded pick)."""
    import calibrate_dng100 as CAL
    import run_arms as RA

    rng = np.random.default_rng(TRUST_SEED)
    plan = [("B1-lo10", 15), ("B1-lo5", 10), ("B5", 10), ("B4", 15), ("B2", 15), ("B1-ctl-rewire-102", 3), ("B1-ctl-rewire-104", 3),
            ("B1-ctl-classshuffle-201", 3), ("B1-ctl-classshuffle-203", 3), ("B1-ctl-classshuffle-205", 3)]
    groups = []
    for camp, n in plan:
        jobs, shared = RA._jobs_for(camp)
        pick = sorted(rng.choice(len(jobs), n, replace=False))
        groups.append((shared, [dict(jobs[i], origin=f"arms/{camp}") for i in pick]))
    jobs, shared = CAL._full_jobs([380.0], range(64), 2.0, "g3")
    pick = sorted(rng.choice(len(jobs), 20, replace=False))
    groups.append((shared, [dict(jobs[i], origin="calibration/g3_v1") for i in pick]))
    return groups, "arms"


def _nets():
    from brainir.sim.model import ModelConfig
    from brainir_ledger import arms as AR
    from brainir_ledger import networks as N

    fl = N.front_leg()
    g1 = N.type_groups(fl.table)
    net2, g2, _ = AR.malecns_network()
    return AR, ModelConfig, (fl, g1), (net2, g2)


def _v2_jobs(arm: str, groups: dict, k: int, AR, ModelConfig, seeds=None) -> list[dict]:
    jobs = AR.group_jobs(arm, groups, AR.b1_screen_cfg(10), ModelConfig(t_end=1.0), seeds=seeds or AR.SEEDS)
    return [dict(j, kind="group_v2", k_min=int(k)) for j in jobs]


def build_calibk(k=None):
    """PREREG v2 P1: the DNg100 pair (both members) under tuner v2 for K in {1, 2, 3, 5, 10}, seeds 0..15, on the MANC and the
    MaleCNS front-leg networks. DNg100 only."""
    AR, MC, (fl, g1), (net2, g2) = _nets()
    out = []
    for tag, net, grp in (("MANC", fl, g1), ("MaleCNS", net2, g2)):
        shared = {"W": net.W, "sizes": net.sizes, "readout": net.readout}
        jobs = []
        for kk in (1, 2, 3, 5, 10):
            jobs += [dict(j, key=f"calibK|{tag}|K{kk}|DNg100|s{j['seed']}") for j in _v2_jobs("x", {"DNg100": grp["DNg100"]}, kk, AR, MC)]
        out.append((shared, jobs))
    return out, "calibration"


def build_regress(k=None):
    """PREREG v2 P1 tuner regression: K = 0 on 30 random B1 types (seed 20261204) x 16 seeds; keys = B1-lo10 keys."""
    AR, MC, (fl, g1), _ = _nets()
    rng = np.random.default_rng(20261204)
    types = sorted(rng.choice(sorted(g1), 30, replace=False))
    jobs = _v2_jobs("B1-lo10", {t: g1[t] for t in types}, 0, AR, MC)
    return [({"W": fl.W, "sizes": fl.sizes, "readout": fl.readout}, jobs)], "arms"


def build_b1r(k):
    AR, MC, (fl, g1), _ = _nets()
    return [({"W": fl.W, "sizes": fl.sizes, "readout": fl.readout}, _v2_jobs("B1r", g1, k, AR, MC))], "arms"


def build_b2r(k):
    AR, MC, _, (net2, g2) = _nets()
    return [({"W": net2.W, "sizes": net2.sizes, "readout": net2.readout}, _v2_jobs("B2r", g2, k, AR, MC))], "arms"


def build_g3v2(k=None):
    """PREREG v2 P2: G3 re-run (both DNg100 at 380, T = 2 s, seeds 0..63, run 1's job specs) and item 5 (the B3 procedure,
    PREREG v1 3.7 / LOG L14, on the DNg100 type, seeds 0..15). DNg100 only."""
    import calibrate_dng100 as CAL
    from brainir.compute.backend import Shared
    from brainir.sim.model import ModelConfig
    from brainir.sim.screen import ScreenConfig

    jobs, shared = CAL._full_jobs([380.0], range(64), 2.0, "g3v2")
    dng = list(jobs[0]["stim_indices"])
    scfg = ScreenConfig(n_active_lower=100, n_active_upper=7667, n_high_fr_upper=1022)
    item5 = [{"key": f"g3v2item5|DNg100|s{s}", "kind": "group", "W": Shared("W"), "sizes": Shared("sizes"), "readout": Shared("readout"),
              "members": dng, "seed": s, "model": ModelConfig(t_end=1.0).to_dict(), "screen": scfg.to_dict(),
              "extras": {"legs": Shared("legs"), "readout_traces": True, "watch": dng}} for s in range(16)]
    return [(shared, jobs + item5)], "calibration"


BUILDERS = {"trust": build_trust, "calibk": build_calibk, "regress": build_regress, "b1r": build_b1r, "b2r": build_b2r,
            "g3v2": build_g3v2}


# ----------------------------------------------------------------------------------------------------- pack / publish
def pack(name: str, chunk_jobs: int, k: int | None = None) -> None:
    b = BUILDERS[name.split("-")[0]]
    groups, area = b() if b is build_trust else b(k)
    out = GHA / name
    out.mkdir(parents=True, exist_ok=True)
    items, files, keys = [], {}, []
    for shared, jobs in groups:
        blob, pkey = pack_shared(shared)
        p = out / f"payload_{pkey}.bin"
        p.write_bytes(blob)
        files[p.name] = hashlib.sha256(blob).hexdigest()
        for j in jobs:
            items.append((pkey, j))
            keys.append(j["key"])
    if len(keys) != len(set(keys)):
        raise SystemExit("duplicate job keys")
    order = np.random.default_rng(0).permutation(len(items))  # mix heavy and light jobs across chunks
    items = [items[i] for i in order]
    chunks = [items[i:i + chunk_jobs] for i in range(0, len(items), chunk_jobs)]
    for i, ch in enumerate(chunks):
        p = out / f"chunk_{i}.pkl"
        p.write_bytes(pickle.dumps(ch, protocol=pickle.HIGHEST_PROTOCOL))
        files[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    man = {"campaign": name, "area": area, "n_jobs": len(items), "n_chunks": len(chunks), "payload_keys": sorted({k for k, _ in items}),
           "files": files, "keys_sha256": hashlib.sha256("\n".join(sorted(keys)).encode()).hexdigest(), "keys": sorted(keys),
           "git_head": sh("git", "rev-parse", "HEAD"), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (out / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    print(json.dumps({k: man[k] for k in ("campaign", "n_jobs", "n_chunks", "payload_keys")}))


def publish(name: str, attempt: int) -> None:
    out = GHA / name
    head = sh("git", "rev-parse", "HEAD")
    if sh("git", "rev-parse", "origin/ledger/v1") != head:
        raise SystemExit("push the branch first: the workflow code at HEAD must be on origin")
    rel = f"ledgerdata-{name}"
    if subprocess.run(["gh", "release", "view", rel], cwd=REPO, capture_output=True).returncode != 0:
        assets = [str(p) for p in sorted(out.iterdir()) if p.is_file()]
        sh("gh", "release", "create", rel, *assets, "--target", head, "--title", rel, "--prerelease",
           "--notes", "BrainIR ledger run 2: inputs of a GitHub Actions campaign (public connectome matrices and job specs only; "
                      "no result). Results come back encrypted. See research/ledger/LOG.md.")
    tag = f"gha-run-{name}" + (f"-r{attempt}" if attempt else "")
    sh("git", "tag", tag, head)
    sh("git", "push", "origin", tag)
    print("published", rel, "and pushed", tag)


# ----------------------------------------------------------------------------------------------------- collect
def _decrypt(d: Path) -> dict:
    with tempfile.TemporaryDirectory() as td:
        k = Path(td) / "k.bin"
        sh(OPENSSL, "pkeyutl", "-decrypt", "-inkey", str(KEY), "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256",
           "-in", str(d / "k.bin.enc"), "-out", str(k))
        pk = Path(td) / "res.pkl"
        sh(OPENSSL, "enc", "-d", "-aes-256-cbc", "-md", "sha256", "-pbkdf2", "-iter", "200000", "-in", str(d / "res.pkl.enc"), "-out", str(pk), "-pass",
           f"file:{k}")
        return pickle.loads(pk.read_bytes())


def runs_for(name: str) -> list[dict]:
    q = sh("gh", "api", "repos/{owner}/{repo}/actions/runs?per_page=50&event=push")
    runs = json.loads(q)["workflow_runs"]
    return [r for r in runs if r["head_branch"].startswith(f"gha-run-{name}")]


def collect(name: str, wait: bool) -> dict:
    man = json.loads((GHA / name / "manifest.json").read_text())
    runs = runs_for(name)
    while wait and (not runs or any(r["status"] != "completed" for r in runs)):
        time.sleep(30)
        runs = runs_for(name)
    dest = data_dir() / man["area"] / f"GHA_{name}"
    dest.mkdir(parents=True, exist_ok=True)
    log = dest / "results.pkl"
    have = {r["key"] for r in read_log(log)} if log.exists() else set()
    want, new, metas = set(man["keys"]), 0, []
    for run in runs:
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["gh", "run", "download", str(run["id"]), "-D", td], cwd=REPO, capture_output=True)
            for d in sorted(Path(td).glob("res-*")):
                payload = _decrypt(d)
                metas.append({**payload["meta"], "run_id": run["id"]})
                with open(log, "ab") as fh:
                    for r in payload["results"]:
                        if r["key"] not in want:
                            raise SystemExit(f"unexpected key {r['key']}")
                        if r["key"] in have or "error" in r:
                            continue
                        pickle.dump(r, fh, protocol=pickle.HIGHEST_PROTOCOL)
                        have.add(r["key"])
                        new += 1
    with open(dest / "gha_meta.jsonl", "a") as fh:
        for m in metas:
            fh.write(json.dumps({k: (v if k != "probe" else {"numerics_digest": v["numerics_digest"], "host": v["host"]}) for k, v in m.items()},
                                default=str) + "\n")
    st = {"campaign": name, "runs": [(r["id"], r["status"], r["conclusion"]) for r in runs], "new_results": new, "have": len(have),
          "expected": len(want), "missing": len(want - have),
          "chunk_numerics_digests": sorted({m["probe"]["numerics_digest"][:12] for m in metas})}
    print(json.dumps(st))
    return st


# ----------------------------------------------------------------------------------------------------- trust gate
def trust_compare() -> dict:
    man = json.loads((GHA / "trust" / "manifest.json").read_text())
    new = {r["key"]: r for r in read_log(data_dir() / "arms" / "GHA_trust" / "results.pkl")}
    items = []
    for f in sorted((GHA / "trust").glob("chunk_*.pkl")):
        items += pickle.loads(f.read_bytes())
    origin = {j["key"]: j["origin"] for _, j in items}
    orig_logs: dict[str, dict] = {}
    for o in sorted(set(origin.values())):
        orig_logs[o] = {r["key"]: r for r in read_log(data_dir() / o / "results.pkl")}
    rows, ident, rounding, bad = [], 0, 0, []
    for k in man["keys"]:
        a, b = orig_logs[origin[k]].get(k), new.get(k)
        if b is None:
            bad.append((k, "missing on runner"))
            continue
        if a["digest"] == b["digest"]:
            ident += 1
            continue
        same_flags = a.get("usable") == b.get("usable") and a.get("current") == b.get("current") and a.get("n_tuning_runs") == b.get("n_tuning_runs")
        ds = abs(float(a.get("score") or 0) - float(b.get("score") or 0))
        if same_flags and ds < 1e-3:
            rounding += 1
        else:
            bad.append((k, f"usable/current/runs equal {same_flags}, score diff {ds:.4g}"))
    out = {"n": len(man["keys"]), "identical": ident, "rounding_only": rounding, "different": len(bad), "different_keys": bad,
           "by_origin": {o: sum(1 for k in man["keys"] if origin[k] == o) for o in sorted(set(origin.values()))},
           "verdict": "identical" if ident == len(man["keys"]) else ("rounding" if not bad else "fail")}
    print(json.dumps(out, indent=1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack")
    p.add_argument("name")
    p.add_argument("--chunk-jobs", type=int, default=25)
    p.add_argument("--k", type=int, default=None)
    p = sub.add_parser("publish")
    p.add_argument("name")
    p.add_argument("--attempt", type=int, default=0)
    p = sub.add_parser("collect")
    p.add_argument("name")
    p.add_argument("--wait", action="store_true")
    sub.add_parser("trust-compare")
    a = ap.parse_args()
    if a.cmd == "pack":
        pack(a.name, a.chunk_jobs, a.k)
    elif a.cmd == "publish":
        publish(a.name, a.attempt)
    elif a.cmd == "collect":
        collect(a.name, a.wait)
    else:
        trust_compare()


if __name__ == "__main__":
    main()
