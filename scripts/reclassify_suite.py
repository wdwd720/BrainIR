"""Upgrade an already-audited synthetic suite to the participation-aware truth (reviews A and G), without searching again.

    uv run python scripts/reclassify_suite.py data/synthetic/mechanisms_v1_final [--backend modal] [--workers 3]

For every (instance, network) of the suite: unplanted alternatives whose members do not participate in the intact network (mean rate
in the analysis window below max(0.05 Hz, 1 % of the planted core's median)) are moved to ``latent_backups_positions``, and the
silencing pass fraction of every planted-alternative node is added (``essential_pass_fraction_positions``). The original truth files
are copied to ``truth/pre_reclassify/`` first; ``truth/RECLASSIFY_REPORT.json`` records what moved. Truth stays under truth/ only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from brainir.compute.backend import Shared, split_failures
from brainir.discovery.problem import pack_bundle
from brainir.discovery.remote import get_discovery_backend as get_backend
from brainir.discovery.suite_audit import reclassify_job


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("suite", type=Path)
    ap.add_argument("--backend", choices=["local", "modal"], default="local")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--containers", type=int, default=100)
    args = ap.parse_args(argv)
    tdir = args.suite / "truth"
    if (tdir / "RECLASSIFY_REPORT.json").exists():
        print(f"{args.suite.name}: already reclassified")
        return 0
    jobs, packs = [], {}
    for tp in sorted(tdir.glob("*.json")):
        inst = args.suite / "instances" / tp.stem
        if not inst.exists():
            continue
        truth = json.loads(tp.read_text(encoding="utf-8"))
        for net, tnet in truth["networks"].items():
            jobs.append((str(inst), net, tnet, None))
        if args.backend == "modal":
            pack: dict[str, bytes] = {}
            for net in truth["networks"]:
                pack.update(pack_bundle(inst, net))
            packs[tp.stem] = pack
    t0 = time.time()
    if args.backend == "modal":
        backend = get_backend("modal", cpu=1.0, memory_mb=3072, timeout_s=3600, max_containers=args.containers)
        results, failed = split_failures(backend.map(reclassify_job, [(*j[:3], Shared("packs")) for j in jobs], shared={"packs": packs}))
    elif args.workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            results, failed = list(ex.map(reclassify_job, jobs)), []
    else:
        results, failed = [reclassify_job(j) for j in jobs], []
    if failed:
        print(f"{len(failed)} jobs failed, nothing written: {failed[:2]}")
        return 1
    backup = tdir / "pre_reclassify"
    backup.mkdir(exist_ok=True)
    by: dict[str, dict] = {}
    for r in results:
        by.setdefault(r["instance"], {})[r["network"]] = r["result"]
    report = {"suite": args.suite.name, "n_jobs": len(jobs), "moved_to_latent": {}, "calls": 0, "wall_s": None}
    for name, nets in by.items():
        tp = tdir / f"{name}.json"
        shutil.copyfile(tp, backup / tp.name)
        truth = json.loads(tp.read_text(encoding="utf-8"))
        for net, res in nets.items():
            truth["networks"][net] = res["truth_net"]
            report["calls"] += int(res["calls"])
            if res["moved_to_latent"]:
                report["moved_to_latent"][f"{name}/{net}"] = res["moved_to_latent"]
        tp.write_text(json.dumps(truth, indent=1) + "\n", encoding="utf-8", newline="\n")
    report["wall_s"] = round(time.time() - t0, 1)
    report["n_moved"] = sum(len(v) for v in report["moved_to_latent"].values())
    (tdir / "RECLASSIFY_REPORT.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{args.suite.name}: {len(jobs)} networks, {report['n_moved']} unplanted sets moved to latent backups, {report['calls']} calls, "
          f"{report['wall_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
