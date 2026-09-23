"""Reproduce the paper's pruning ("computational sufficiency") screen with BrainIR's simulator (ANSWER-KEY-ADJACENT).

    uv run python benchmarks/dng100_walking_cpg/reproduce_pruning.py --dataset manc --version v1.2.1 --n 4 --backend local
    uv run python benchmarks/dng100_walking_cpg/reproduce_pruning.py --dataset manc --version v1.2.1 --n 1024 --backend modal

Each screen = one parameter replicate (seed) of `brainir.sim.prune.prune_screen` on the paper's front-leg network with
the DNg100 stimulus; prunable = every non-readout neuron except the stimulus. Results are aggregated into circuits
(sets of kept interneurons, labelled with the oracle's names where they match) and compared with the published
prevalence table (oracle.json `modal_circuit` / `other_circuits`). Runs are registered in
benchmarks/dng100/manifests/experiments/.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

import numpy as np

from brainir.compute import ExperimentRecord, Shared, artifact_record, content_hash, get_backend, register_run, split_failures
from brainir.sim import ModelConfig, Stimulus
from brainir.sim.prune import PRUNE_ALGORITHM_ID, PruneConfig, run_prune_job

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reproduce_dynamics import STIM_CURRENT, paper_network  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
REGISTRY = HERE.parent / "dng100" / "manifests" / "experiments"
ORACLE = json.loads((HERE.parent / "dng100" / "oracle" / "oracle.json").read_text(encoding="utf-8"))


def label_circuit(ids: list[int], onet: dict, types: dict[int, str]) -> tuple[str, ...]:
    """Kept interneuron ids -> sorted labels (oracle label if the id is a published core member, else cell type or id)."""
    inv = {int(v): k for k, v in onet["core"].items()}
    out = []
    for i in ids:
        out.append(inv.get(int(i)) or (types.get(int(i)) or str(i)))
    return tuple(sorted(out))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="manc")
    ap.add_argument("--version", default="v1.2.1")
    ap.add_argument("--nt", choices=["paper", "brainir"], default="paper")
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--max-iterations", type=int, default=200)
    ap.add_argument("--t-end", type=float, default=1.0)
    ap.add_argument("--backend", choices=["local", "modal"], default="local")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--containers", type=int, default=100)
    ap.add_argument("--report-set", choices=["structural", "activity"], default="activity",
                    help="which circuit definition to tabulate (the published tables match the activity-based set)")
    args = ap.parse_args(argv)
    net_name = f"{args.dataset}_{args.version}"
    onet = ORACLE["networks"][net_name]
    wt, net, readout = paper_network(args.dataset, args.version, args.nt)
    stim_pos = int(net.positions_of_type("DNg100")[0])
    assert int(net.ids[stim_pos]) == onet["stimulus_source_ids"][0]
    cfg = ModelConfig(t_end=args.t_end)
    pcfg = PruneConfig(max_iterations=args.max_iterations)
    stim = Stimulus((stim_pos,), (STIM_CURRENT[args.dataset],))
    prunable = np.ones(net.n, bool)
    seeds = list(range(args.seed0, args.seed0 + args.n))
    shared = {"W": net.W, "readout": readout, "prunable": prunable, "sizes": net.sizes}
    jobs = [(Shared("W"), cfg, stim, Shared("readout"), Shared("prunable"), Shared("sizes"), s, pcfg) for s in seeds]
    backend = get_backend(args.backend, n_workers=args.workers, cpu=1.0, memory_mb=3072, timeout_s=3600, max_containers=args.containers)
    t0 = time.time()
    results, failed = split_failures(backend.map(run_prune_job, jobs, shared=shared))
    wall = time.time() - t0
    if failed:
        print(f"WARNING: {len(failed)} of {len(jobs)} screens failed; first: {failed[0]}")
    types = dict(zip(net.table["source_id"].astype(int), net.table["cell_type"].astype(object)))
    stim_id = int(net.ids[stim_pos])
    circuits = collections.Counter()
    per_screen = []
    for r in results:
        kept = r.active_kept_positions if args.report_set == "activity" else r.kept_positions
        ids = [int(net.ids[p]) for p in kept if int(net.ids[p]) != stim_id]
        lab = label_circuit(ids, onet, types)
        circuits[lab] += 1
        per_screen.append({"seed": r.seed, "converged": r.converged, "iterations": r.iterations, "n_simulations": r.n_simulations,
                           "final_score": round(r.final_score, 4), "final_frequency_hz": r.final_frequency_hz,
                           "n_kept_structural": len([p for p in r.kept_positions if int(net.ids[p]) != stim_id]),
                           "n_kept_active": len([p for p in r.active_kept_positions if int(net.ids[p]) != stim_id]),
                           "kept_ids": ids, "labels": list(lab), "wall_time_s": r.wall_time_s})
    n_conv = sum(p["converged"] for p in per_screen)
    labels_all = collections.Counter(lab for p in per_screen for lab in p["labels"])
    core_labels = set(onet["core"])
    with_e1e2 = sum(1 for p in per_screen if {"E1", "E2"} <= set(p["labels"]))
    with_inh = sum(1 for p in per_screen if {"E1", "E2"} <= set(p["labels"]) and set(p["labels"]) & set(onet["inhibitory_slot"]))
    summary = {
        "algorithm": PRUNE_ALGORITHM_ID, "dataset": args.dataset, "version": args.version, "nt": args.nt, "n_screens": len(results),
        "converged": n_conv, "median_iterations": float(np.median([p["iterations"] for p in per_screen])),
        "median_simulations": float(np.median([p["n_simulations"] for p in per_screen])),
        "report_set": args.report_set,
        "circuits": [{"labels": list(k), "count": v, "fraction": v / len(results)} for k, v in circuits.most_common(15)],
        "fraction_with_E1_and_E2": with_e1e2 / len(results), "fraction_E1_E2_plus_inhibitory_slot": with_inh / len(results),
        "label_prevalence": {k: v / len(results) for k, v in labels_all.most_common(25)},
        "published": {"modal_circuit": onet["modal_circuit"], "modal_prevalence": onet["modal_prevalence"], "other_circuits": onet.get("other_circuits")},
        "size_distribution": dict(collections.Counter(p["n_kept_active"] for p in per_screen)),
        "wall_time_s": round(wall, 1), "backend": backend.last_stats.to_dict(), "core_labels_known": sorted(core_labels),
        "n_failed_screens": len(failed), "failed_screens": failed[:50],
    }
    RESULTS.mkdir(exist_ok=True)
    name = f"pruning_{net_name}_nt-{args.nt}_n{args.n}_seed{args.seed0}"
    (RESULTS / f"{name}.json").write_text(json.dumps({"summary": summary, "screens": per_screen, "model_config": cfg.to_dict(),
                                                       "prune_config": pcfg.to_dict()}, indent=1, default=float) + "\n",
                                          encoding="utf-8", newline="\n")
    lines = [f"# Pruning reproduction — {net_name} (nt={args.nt}, n={args.n}, T={args.t_end} s, {args.report_set} set)", "",
             f"converged {n_conv}/{len(results)}; median iterations {summary['median_iterations']:.0f}; wall {wall:.0f} s on {args.backend}.", "",
             "| circuit (labels) | count | fraction |", "|---|---|---|"]
    for c in summary["circuits"]:
        lines.append(f"| {', '.join(c['labels'])} | {c['count']} | {c['fraction']:.3f} |")
    lines += ["", f"E1 and E2 both kept: {summary['fraction_with_E1_and_E2']:.3f}; plus an inhibitory-slot member: "
              f"{summary['fraction_E1_E2_plus_inhibitory_slot']:.3f}. Published modal circuit {onet['modal_circuit']} at {onet['modal_prevalence']}.", ""]
    (RESULTS / f"{name}.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))
    rec = ExperimentRecord(name=name, config={"model": cfg.to_dict(), "prune": pcfg.to_dict(), "network": net.meta, "stimulus": stim_pos,
                                              "current": STIM_CURRENT[args.dataset]},
                           seeds=seeds, inputs={"network_hash": content_hash(net.meta)}, backend=backend.last_stats.to_dict(),
                           artifacts={"results": artifact_record(RESULTS / f"{name}.json")}, summary={k: summary[k] for k in
                           ("n_screens", "converged", "fraction_with_E1_and_E2", "fraction_E1_E2_plus_inhibitory_slot")})
    print("registered", register_run(rec, REGISTRY).name)


if __name__ == "__main__":
    main()
