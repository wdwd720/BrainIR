"""Reproduce the published DNg100-activation dynamics on BrainIR's rebuilt MANC / MaleCNS networks.

ANSWER-KEY-ADJACENT benchmark tooling (never imported by src/). It runs the paper's protocol with BrainIR's independent
simulator and metric implementation and writes distributional summaries that are compared with the numbers the paper
reports (Fig. 2e: MANC mean score 0.974, median 0.999, 99.8% >= 0.5, median 3 active MNs (0-6); mCNS 0.985 / 0.994 /
100% / 8 (6-16)).

    uv run python benchmarks/dng100_walking_cpg/reproduce_dynamics.py stim --dataset manc --version v1.2.1 --n 128 --workers 8
    uv run python benchmarks/dng100_walking_cpg/reproduce_dynamics.py stim --dataset male-cns --version v1.0 --n 128

Network variants (``--nt``):
  paper    signs from the neurotransmitter labels in the authors' own table (exact reproduction of their W)
  brainir  signs from BrainIR's stored predictions (MANC: v1.0 body-level labels carried by ID; mCNS: consensusNt)

Outputs: results/<name>.json (summary + per-replicate scalars; no trajectories), results/<name>.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from brainir.graph import Connectome
from brainir.sim import ModelConfig, build_network
from brainir.sim.experiments import stimulation_experiment
from brainir.sim.weights import vnc_neuropils

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reproduce_manc_connectivity import authors_mcns, authors_t1, fetch_external  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"

PAPER_FIG2E = {  # dataset -> reported DNg100 activation statistics (n = 1024)
    "manc": {"mean": 0.974, "median": 0.999, "fraction_ge_0_5": 0.998, "active_mn_median": 3, "active_mn_range": [0, 6]},
    "male-cns": {"mean": 0.985, "median": 0.994, "fraction_ge_0_5": 1.0, "active_mn_median": 8, "active_mn_range": [6, 16]},
}
STIM_CURRENT = {"manc": 250.0, "male-cns": 400.0}  # the paper's amplitudes per dataset


def paper_network(dataset: str, version: str, nt: str):
    files = fetch_external()
    if dataset == "manc":
        wt, _ = authors_t1(files)
        nt_col, roi, sign_basis = "predictedNt", None, "nt_body_prediction"
        sizes_cx = Connectome.open("manc", "v1.0")  # v1.2.x builds carry no sizes; the authors' sizes equal v1.0's
    else:
        wt, _ = authors_mcns(files)
        nt_col, sign_basis = "consensusNt", "nt_consensus"
        sizes_cx = None
    cx = Connectome.open(dataset, version)
    ids = wt["bodyId"].to_numpy().astype(np.int64)
    # The authors' MaleCNS table predates the v1.0 release (2026-02-10 neuPrint state); bodies merged/split since then
    # are not neurons of v1.0 and are dropped here (recorded in net.meta). MANC tables match the builds exactly.
    dropped = [int(i) for i in ids if not cx.has(int(i))]
    if dropped:
        ids = np.array([i for i in ids if int(i) not in set(dropped)], dtype=np.int64)
    roi = vnc_neuropils(cx) if dataset == "male-cns" else None
    sizes = None
    if sizes_cx is not None:
        sizes = sizes_cx.neurons["size_voxels"].reindex(ids).astype("float64").to_dict()
    override = wt.set_index("bodyId")[nt_col].to_dict() if nt == "paper" else None
    net = build_network(cx, ids, floor=5, sign_basis=sign_basis, nt_override=override, roi_restrict=roi, sizes=sizes,
                        size_source=None if sizes is None else "manc:v1.0 size_voxels by body ID")
    net.meta["authors_table_rows"] = int(len(wt))
    net.meta["authors_ids_not_in_build"] = dropped
    if dropped:
        wt = wt[~wt["bodyId"].isin(dropped)].reset_index(drop=True)
    # readout = front-leg motor neurons (role vnc_motor = MANC super_class 'motor_neuron' / MaleCNS 'vnc_motor', subclass fl);
    # identical to the authors' 144 MNs for manc:v1.2.1; 135 in the MaleCNS front-leg network
    tab = net.table
    readout = (tab["role_class"].to_numpy() == "vnc_motor") & (tab["sub_class"].to_numpy() == "fl")
    if not readout.any():
        raise RuntimeError(f"no front-leg motor neurons found in {dataset}:{version} network")
    return wt, net, readout


def run_stim(args) -> None:
    wt, net, readout = paper_network(args.dataset, args.version, args.nt)
    dn = net.positions_of_type("DNg100")
    if args.stim_index is not None:  # positional index in the authors' table (31 = the neuron used for Fig. 2)
        pos = [int(args.stim_index)]
    else:
        pos = [int(dn[0])]
    cfg = ModelConfig(t_end=args.t_end)
    seeds = list(range(args.seed0, args.seed0 + args.n))
    t0 = time.time()
    res = stimulation_experiment(net, pos, STIM_CURRENT[args.dataset], cfg, seeds, readout, n_workers=args.workers,
                                 name=f"DNg100 stimulation {args.dataset}:{args.version} nt={args.nt}",
                                 readout_description="motor neurons with sub_class 'fl' (front leg)")
    wall = time.time() - t0
    summary = res.summary()
    out = res.to_dict()
    out["paper_reference"] = PAPER_FIG2E[args.dataset]
    out["stimulated"] = {"positions": pos, "source_ids": [int(net.ids[p]) for p in pos], "cell_type": "DNg100"}
    out["network_table_summary"] = {"n": net.n, "readout_n": int(readout.sum()), "sign_rows": {"positive": int((net.signs > 0).sum()),
                                    "negative": int((net.signs < 0).sum()), "zero": int((net.signs == 0).sum())}}
    out["wall_time_s_total"] = round(wall, 1)
    out["workers"] = args.workers
    RESULTS.mkdir(exist_ok=True)
    name = args.name or f"stim_dng100_{args.dataset}_{args.version}_nt-{args.nt}_n{args.n}"
    (RESULTS / f"{name}.json").write_text(json.dumps(out, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    ref = PAPER_FIG2E[args.dataset]
    rng_ = summary["active_readout_range"]
    freq_ref = "~10-11 (I = 250: 9.6 at 220, 11.0 at 260)" if args.dataset == "manc" else "n/a"
    md = [f"# {out['name']}", "", f"n = {args.n} replicates (seeds {seeds[0]}..{seeds[-1]}), I = {STIM_CURRENT[args.dataset]}, "
          f"T = {args.t_end} s, readout = {int(readout.sum())} front-leg motor neurons; wall {wall:.0f} s on {args.workers} workers.", "",
          "| statistic | BrainIR | paper (n = 1024) |", "|---|---|---|",
          f"| mean score | {summary['score_mean']:.3f} | {ref['mean']} |",
          f"| median score | {summary['score_median']:.3f} | {ref['median']} |",
          f"| fraction >= 0.5 | {summary['fraction_ge_threshold']:.3f} | {ref['fraction_ge_0_5']} |",
          f"| median active MNs (range) | {summary['active_readout_median']:.0f} ({rng_[0]}-{rng_[1]}) | "
          f"{ref['active_mn_median']} ({ref['active_mn_range'][0]}-{ref['active_mn_range'][1]}) |",
          f"| median MN frequency (Hz) | {summary['frequency_median_hz']:.2f} | {freq_ref} |",
          f"| solver failures | {summary['solver_failures']} | n/a |", ""]
    (RESULTS / f"{name}.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
    print("\n".join(md))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stim", help="DNg100 activation across parameter replicates")
    s.add_argument("--dataset", default="manc")
    s.add_argument("--version", default="v1.2.1")
    s.add_argument("--nt", choices=["paper", "brainir"], default="paper")
    s.add_argument("--n", type=int, default=128)
    s.add_argument("--seed0", type=int, default=0)
    s.add_argument("--t-end", type=float, default=2.0)
    s.add_argument("--workers", type=int, default=8)
    s.add_argument("--stim-index", type=int, default=None)
    s.add_argument("--name", default=None)
    s.set_defaults(func=run_stim)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
