"""Reproduce the paper's in-silico intervention claims with BrainIR's simulator (ANSWER-KEY-ADJACENT: uses the oracle IDs).

Claims checked (Pugliese et al., Fig. 3j / Fig. 3g-h; oracle.json `essential` and `modal_circuit`):
  * silencing E1 or E2 alone abolishes the DNg100-driven motor rhythm (MANC: mean score 0.000 / 0.005);
  * silencing the inhibitory partner alone does not (MANC I1: 0.938; mCNS I2: 0.952);
  * the isolated core (E1, E2, I1 in MANC; E1, E2, I2 in mCNS) + stimulus + motor neurons still oscillates.
Results become `brainir_simulation` evidence in the oracle.

    uv run python benchmarks/dng100_walking_cpg/reproduce_interventions.py --dataset manc --version v1.2.1 --n 64 --workers 6
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from brainir.compute import ExperimentRecord, artifact_record, content_hash, get_backend, register_run
from brainir.sim import Intervention, ModelConfig
from brainir.sim.experiments import stimulation_experiment

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reproduce_dynamics import STIM_CURRENT, paper_network  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
REGISTRY = HERE.parent / "dng100" / "manifests" / "experiments"
ORACLE = json.loads((HERE.parent / "dng100" / "oracle" / "oracle.json").read_text(encoding="utf-8"))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="manc")
    ap.add_argument("--version", default="v1.2.1")
    ap.add_argument("--nt", choices=["paper", "brainir"], default="paper")
    ap.add_argument("--n", type=int, default=64)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--t-end", type=float, default=1.0)
    ap.add_argument("--backend", choices=["local", "modal"], default="local")
    ap.add_argument("--containers", type=int, default=64)
    args = ap.parse_args(argv)
    net_name = f"{args.dataset}_{args.version}"
    onet = ORACLE["networks"][net_name]
    wt, net, readout = paper_network(args.dataset, args.version, args.nt)
    stim_pos = [int(net.index_of([onet["stimulus_source_ids"][0]])[0])]  # the benchmark's stimulus neuron (oracle)
    assert net.table["cell_type"].iloc[stim_pos[0]] == "DNg100"
    backend = get_backend("modal", cpu=1.0, memory_mb=3072, timeout_s=1800, max_containers=args.containers) if args.backend == "modal" else None
    core = onet["core"]
    pos = {lab: int(net.index_of([i])[0]) for lab, i in core.items() if int(i) in set(net.ids.tolist())}
    cfg = ModelConfig(t_end=args.t_end)
    seeds = list(range(args.n))
    cur = STIM_CURRENT[args.dataset]
    mn_positions = tuple(int(p) for p in np.flatnonzero(readout))
    conditions = {"intact": None}
    for lab in ("E1", "E2", "I1", "I2", "E3"):
        if lab in pos:
            conditions[f"silence_{lab}"] = Intervention(silence=(pos[lab],))
    modal = onet["modal_circuit"]
    always = tuple(stim_pos) + mn_positions
    conditions["keep_only_modal_core"] = Intervention(keep_only=tuple(pos[lab] for lab in modal if lab in pos), always_keep=always)
    alt = [lab for lab in ("E1", "E2", "I2" if "I1" in modal else "I1") if lab in pos]
    conditions["keep_only_alternative_core"] = Intervention(keep_only=tuple(pos[lab] for lab in alt), always_keep=always)
    conditions["keep_only_E1_E2"] = Intervention(keep_only=(pos["E1"], pos["E2"]), always_keep=always)
    out = {"dataset": args.dataset, "version": args.version, "nt": args.nt, "n": args.n, "t_end": args.t_end, "current": cur,
           "core_positions": pos, "modal_circuit": modal, "backend": args.backend, "network": net.meta, "conditions": {}}
    t0 = time.time()
    for name, iv in conditions.items():
        res = stimulation_experiment(net, stim_pos, cur, cfg, seeds, readout, intervention=iv, n_workers=args.workers, name=name, backend=backend)
        s = res.summary()
        out["conditions"][name] = {"summary": s, "scores": [round(r.score, 4) for r in res.replicates],
                                   "frequencies_hz": [None if r.mean_frequency_hz is None else round(r.mean_frequency_hz, 2) for r in res.replicates],
                                   "n_active_readout": [r.n_active_readout for r in res.replicates]}
        print(f"{name:28s} mean={s['score_mean']:.3f} median={s['score_median']:.3f} frac>=0.5={s['fraction_ge_threshold']:.3f} "
              f"f={s['frequency_median_hz']} activeMN={s['active_readout_median']} ({time.time() - t0:.0f}s)")
    out["paper_reference"] = {"silencing": onet.get("silencing_paper"), "essential": onet["essential"], "modal_prevalence": onet["modal_prevalence"]}
    RESULTS.mkdir(exist_ok=True)
    name = f"interventions_{net_name}_nt-{args.nt}_n{args.n}"
    (RESULTS / f"{name}.json").write_text(json.dumps(out, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    lines = [f"# Intervention reproduction — {net_name} (nt={args.nt}, n={args.n}, T={args.t_end} s)", "",
             "| condition | mean score | median | fraction >= 0.5 | median f (Hz) | median active MNs | paper |", "|---|---|---|---|---|---|---|"]
    ref = onet.get("silencing_paper") or {}
    paper_intact = (onet.get("stimulation_statistics_paper") or {}).get("mean_score", "")
    for cname, c in out["conditions"].items():
        s = c["summary"]
        lab = cname.replace("silence_", "")
        if cname.startswith("silence_"):
            pref = ref.get(lab, {}).get("mean_score", "")
        else:
            pref = paper_intact if cname == "intact" else ""
        fmed = "" if s["frequency_median_hz"] is None else round(s["frequency_median_hz"], 2)
        lines.append(f"| {cname} | {s['score_mean']:.3f} | {s['score_median']:.3f} | {s['fraction_ge_threshold']:.3f} | "
                     f"{fmed} | {s['active_readout_median']} | {pref} |")
    (RESULTS / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    stats = backend.last_stats.to_dict() if backend is not None and backend.last_stats else {"backend": "local", "n_workers": args.workers}
    rec = ExperimentRecord(name=name, config={"model": cfg.to_dict(), "network": net.meta, "current": cur, "conditions": list(conditions),
                                              "core_positions": pos}, seeds=seeds, inputs={"network_hash": content_hash(net.meta)},
                           backend={**stats, "note": "backend stats are those of the last condition's map; each condition was one map call"},
                           artifacts={"results": artifact_record(RESULTS / f"{name}.json")},
                           summary={k: round(v["summary"]["score_mean"], 4) for k, v in out["conditions"].items()})
    print("registered", register_run(rec, REGISTRY).name)


if __name__ == "__main__":
    main()
