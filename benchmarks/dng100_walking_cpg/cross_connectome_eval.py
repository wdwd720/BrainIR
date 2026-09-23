"""Cross-connectome evaluation of the DNg100 circuit in both directions, MANC <-> MaleCNS (ANSWER-KEY-ADJACENT).

    uv run python benchmarks/dng100_walking_cpg/cross_connectome_eval.py --n 32 --workers 6

Two questions, answered with BrainIR's mapping layer (`brainir.mapping`, built without any circuit knowledge) and the
simulator:

1. **Correspondence.** For every published core neuron (oracle labels E1..E5, I1, I2) and the stimulus, what does the
   mapping table say in each direction (MANC v1.2.1 -> MaleCNS v1.0 via `reverse_lookup`; MaleCNS -> MANC via
   `forward_lookup`): mapping kind, confidence, ambiguity, the candidate ids, and whether the oracle's published
   correspondence (paper: matched by cell-type annotation) is among the candidates. This measures whether a method that
   found the circuit in one connectome could name its counterpart in the other with the public mapping alone.
2. **Functional transfer.** Take the modal circuit of one network (oracle), map it to the other network, and simulate
   the mapped circuit there *keep-only* (stimulus + mapped core + readout motor neurons; everything else silenced). If the
   rhythm survives, the mechanism transfers across animals/datasets; the intact-network and the network's own published
   modal circuit are simulated alongside as references. Both directions are run; n parameter replicates each.

Outputs results/cross_connectome_eval_n<n>.json/.md. Uses the oracle (labels, ids) and is therefore benchmark-only code.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from brainir.compute import get_backend
from brainir.mapping import forward_lookup, load_mapping, load_summary, reverse_lookup
from brainir.sim import Intervention, ModelConfig
from brainir.sim.experiments import stimulation_experiment

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reproduce_dynamics import STIM_CURRENT, paper_network  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
ORACLE = json.loads((HERE.parent / "dng100" / "oracle" / "oracle.json").read_text(encoding="utf-8"))
A = ("male-cns", "v1.0")
B = ("manc", "v1.2.1")


def _rows(df: pd.DataFrame, id_col: str) -> list[dict]:
    out = []
    for _, r in df.iterrows():
        cid = r[id_col]
        out.append({"candidate_id": None if pd.isna(cid) else int(cid), "kind": str(r["mapping_kind"]), "confidence": str(r["confidence"]),
                    "ambiguity": int(r["ambiguity"]), "candidate_type": None if pd.isna(r["b_cell_type" if id_col == "b_source_id" else "a_cell_type"])
                    else str(r["b_cell_type" if id_col == "b_source_id" else "a_cell_type"]), "notes": str(r["notes"])})
    return out


def correspondence(table: pd.DataFrame) -> dict:
    """Both directions for every oracle label (+ stimulus), against the oracle's published pairs."""
    pairs = {p["label"]: (int(p["a"][2]), int(p["b"][2])) for p in ORACLE["cross_connectome"]["pairs"]}
    core_b = ORACLE["networks"]["manc_v1.2.1"]["core"]
    core_a = ORACLE["networks"]["male-cns_v1.0"]["core"]
    labels = ["stimulus", *core_b]
    out = {}
    for lab in labels:
        b_id = ORACLE["networks"]["manc_v1.2.1"]["stimulus_source_ids"][0] if lab == "stimulus" else int(core_b[lab])
        a_id = ORACLE["networks"]["male-cns_v1.0"]["stimulus_source_ids"][0] if lab == "stimulus" else int(core_a[lab])
        b2a = _rows(reverse_lookup(table, b_id), "a_source_id")
        a2b = _rows(forward_lookup(table, a_id), "b_source_id")
        best_b2a = b2a[0] if b2a else None
        best_a2b = a2b[0] if a2b else None
        out[lab] = {
            "manc_id": b_id, "malecns_id": a_id, "published_pair": pairs.get(lab),
            "manc_to_malecns": {"n_candidates": len(b2a), "best": best_b2a,
                                "published_counterpart_among_candidates": any(r["candidate_id"] == a_id for r in b2a),
                                "unique_high_confidence": len([r for r in b2a if r["confidence"] == "high"]) == 1},
            "malecns_to_manc": {"n_candidates": len(a2b), "best": best_a2b,
                                "published_counterpart_among_candidates": any(r["candidate_id"] == b_id for r in a2b),
                                "unique_high_confidence": len([r for r in a2b if r["confidence"] == "high"]) == 1},
        }
    return out


def _keep_only(net, readout, keep_ids: list[int], stim_pos: int, current: float, cfg, seeds, workers, name: str, sizes, backend=None):
    idx = {int(i): p for p, i in enumerate(net.ids)}
    core_pos = tuple(idx[i] for i in keep_ids if i in idx)
    always = (stim_pos, *[int(p) for p in np.flatnonzero(readout)])
    inter = Intervention(keep_only=core_pos, always_keep=always)
    res = stimulation_experiment(net, (stim_pos,), current, cfg, seeds, readout, intervention=inter, name=name, sizes=sizes, n_workers=workers,
                                 readout_description="front-leg motor neurons", backend=backend)
    s = res.summary()
    return {"kept_core_ids": [i for i in keep_ids if i in idx], "missing_ids": [i for i in keep_ids if i not in idx], "n_kept_positions": len(core_pos),
            "mean_score": s["score_mean"], "median_score": s["score_median"], "fraction_ge_0_5": s["fraction_ge_threshold"],
            "median_frequency_hz": s["frequency_median_hz"], "median_n_active_readout": s["active_readout_median"],
            "active_readout_range": s["active_readout_range"]}


def functional_transfer(table: pd.DataFrame, n: int, workers: int, t_end: float, backend=None) -> dict:
    """Map each network's modal circuit into the other network and simulate it keep-only there."""
    cfg = ModelConfig(t_end=t_end)
    seeds = list(range(n))
    nets = {}
    for ds, ver in (B, A):
        wt, net, readout = paper_network(ds, ver, "paper")
        onet = ORACLE["networks"][f"{ds}_{ver}"]
        stim_pos = int(net.index_of([onet["stimulus_source_ids"][0]])[0])
        nets[ds] = (net, readout, stim_pos, onet)
    out = {}
    for src, dst in ((B[0], A[0]), (A[0], B[0])):
        net_s, _, _, onet_s = nets[src]
        net_d, readout_d, stim_d, onet_d = nets[dst]
        modal_src = [int(onet_s["core"][lab]) for lab in onet_s["modal_circuit"]]
        mapped, detail = [], []
        for i in modal_src:
            df = reverse_lookup(table, i) if src == "manc" else forward_lookup(table, i)
            col = "a_source_id" if src == "manc" else "b_source_id"
            cands = [int(c) for c in df[col].dropna().astype(int).tolist()]
            hi = [int(c) for c, conf in zip(df[col].tolist(), df["confidence"].astype(str).tolist()) if conf == "high" and not pd.isna(c)]
            chosen = hi if hi else cands
            mapped.extend(chosen)
            detail.append({"source_id": i, "n_candidates": len(cands), "n_high": len(hi), "used": chosen})
        mapped = sorted(set(mapped))
        current = STIM_CURRENT[dst]
        t0 = time.time()
        rows = {
            "intact_network": _keep_only(net_d, readout_d, [int(i) for i in net_d.ids], stim_d, current, cfg, seeds, workers, "intact", net_d.sizes,
                                         backend),
            "own_modal_circuit_keep_only": _keep_only(net_d, readout_d, [int(onet_d["core"][lab]) for lab in onet_d["modal_circuit"]], stim_d, current,
                                                      cfg, seeds, workers, "own_modal", net_d.sizes, backend),
            "mapped_modal_circuit_keep_only": _keep_only(net_d, readout_d, mapped, stim_d, current, cfg, seeds, workers, "mapped_modal", net_d.sizes,
                                                         backend),
        }
        out[f"{src}_to_{dst}"] = {"source_modal_circuit": onet_s["modal_circuit"], "source_ids": modal_src, "mapping_detail": detail,
                                  "mapped_ids": mapped, "destination_modal_circuit": onet_d["modal_circuit"], "destination_current": current,
                                  "results": rows, "wall_time_s": round(time.time() - t0, 1)}
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=32)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--t-end", type=float, default=1.0)
    ap.add_argument("--skip-simulation", action="store_true")
    ap.add_argument("--backend", choices=["local", "modal"], default="local")
    ap.add_argument("--containers", type=int, default=64)
    args = ap.parse_args(argv)
    table = load_mapping(A, B)
    summary = load_summary(A, B)
    corr = correspondence(table)
    res = {"mapping": {"a": summary["a"], "b": summary["b"], "rules": summary["rules"], "table_sha256": summary.get("table", {}).get("sha256")},
           "correspondence": corr}
    if not args.skip_simulation:
        backend = get_backend("modal", cpu=1.0, memory_mb=3072, timeout_s=1800, max_containers=args.containers) if args.backend == "modal" else None
        res["functional_transfer"] = functional_transfer(table, args.n, args.workers, args.t_end, backend)
        res["model_config"] = ModelConfig(t_end=args.t_end).to_dict()
        res["backend"] = args.backend
    RESULTS.mkdir(exist_ok=True)
    name = f"cross_connectome_eval_n{args.n}"
    (RESULTS / f"{name}.json").write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Cross-connectome evaluation — MANC v1.2.1 <-> MaleCNS v1.0", "",
             "## Correspondence of the published core through the public mapping table", "",
             "| label | MANC id | MaleCNS id | MANC->MaleCNS best (kind/conf/amb) | published among cands | MaleCNS->MANC best | published among cands |",
             "|---|---|---|---|---|---|---|"]
    for lab, c in corr.items():
        b1, b2 = c["manc_to_malecns"]["best"], c["malecns_to_manc"]["best"]
        f1 = f"{b1['candidate_id']} {b1['kind']}/{b1['confidence']}/{b1['ambiguity']}" if b1 else "none"
        f2 = f"{b2['candidate_id']} {b2['kind']}/{b2['confidence']}/{b2['ambiguity']}" if b2 else "none"
        lines.append(f"| {lab} | {c['manc_id']} | {c['malecns_id']} | {f1} | {c['manc_to_malecns']['published_counterpart_among_candidates']} | {f2} | "
                     f"{c['malecns_to_manc']['published_counterpart_among_candidates']} |")
    if "functional_transfer" in res:
        lines += ["", f"## Functional transfer (keep-only simulations, n = {args.n}, T = {args.t_end} s)", ""]
        for k, v in res["functional_transfer"].items():
            lines += [f"### {k}: source modal circuit {v['source_modal_circuit']} -> mapped ids {v['mapped_ids']} (destination's own modal circuit "
                      f"{v['destination_modal_circuit']}, I = {v['destination_current']})", "",
                      "| condition | kept | mean score | median | frac >= 0.5 | median f (Hz) | median active MNs |", "|---|---|---|---|---|---|---|"]
            for cond, r in v["results"].items():
                lines.append(f"| {cond} | {r['n_kept_positions']} | {r.get('mean_score', float('nan')):.3f} | {r.get('median_score', float('nan')):.3f} | "
                             f"{r.get('fraction_ge_0_5', float('nan')):.3f} | {r.get('median_frequency_hz')} | {r.get('median_n_active_readout')} |")
            lines.append("")
    (RESULTS / f"{name}.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
