"""Frozen evaluator of the DNg100 benchmark (reads the ORACLE; never imported by discovery code).

    uv run python benchmarks/dng100/evaluator/evaluate.py prediction.json [more.json ...] --bundle benchmarks/dng100/public \
        --out results/eval_<name>.json [--n-replicates 16] [--workers 6] [--no-simulation]

Metric families (reported separately; there is deliberately NO single aggregate score):

structural   exact-neuron overlap with the published core (E1, E2 + the inhibitory slot I1|I2), precision against all
             published labels, compactness.
type_role    the same at the cell-type level (credits same-type neurons, e.g. contralateral copies) and role (sign) agreement.
functional   ORACLE-FREE, computed with BrainIR's simulator on the bundle network: (a) sufficiency — does the stimulus
             still drive a rhythm when only the predicted core (+ stimulus + readout) is kept? (b) necessity — for each
             neuron the prediction calls essential/non-essential, does silencing it in the full network abolish the
             rhythm? (c) predicted frequency / active-MN count vs simulated values.
mechanism    motif sanity on the bundle graph (are the claimed loop neurons connected in a cycle?), sign consistency with
             the network's NT labels, compactness.
cross_connectome  agreement of correspondences claimed across networks with the oracle's label correspondence (type-level).
robustness   stability of the sufficiency result under weight noise and across parameter replicates.

Every number is accompanied by the seeds and simulation settings that produced it. The evaluator's own code hash and the
oracle hash are recorded so results are attributable to a frozen benchmark version.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

from brainir.benchmark.prediction import BrainIRMechanismPrediction
from brainir.metrics.rhythm import ACTIVE_RATE_HZ, DEFAULT_PROMINENCE, network_oscillation_score
from brainir.sim.model import Intervention, ModelConfig, Stimulus, sample_neuron_params, simulate

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))
from oracle import EVIDENCE_LEVELS, OracleNetwork, load_oracle, oracle_sha256  # noqa: E402

HERE = Path(__file__).resolve().parent
EVALUATOR_VERSION = "1.0.0"
RHYTHMIC = 0.5
ANALYSIS_START_S = 0.25


# ---------------------------------------------------------------------------- bundle access
class BundleNetwork:
    """A bundle network with REAL body IDs restored (tier A bundles carry positional ids; the oracle directory holds the map)."""

    def __init__(self, bundle_root: Path, name: str):
        d = Path(bundle_root) / "networks" / name
        self.name = name
        self.info = json.loads((d / "network.json").read_text(encoding="utf-8"))
        self.neurons = pd.read_parquet(d / "neurons.parquet")
        self.edges = pd.read_parquet(d / "edges.parquet")
        self.stimulus = json.loads((d / "stimulus.json").read_text(encoding="utf-8"))
        self.readout = json.loads((d / "readout.json").read_text(encoding="utf-8"))
        self.positional = self.info.get("id_semantics", "").startswith("positional")
        self.public_to_real = None
        if self.positional:
            m = pd.read_csv(Path(__file__).resolve().parents[1] / "oracle" / "tier_a_ids" / f"ids_{name}.csv")
            self.public_to_real = dict(zip(m["position"].astype(int), m["source_id"].astype(int)))
            real = np.array([self.public_to_real[int(p)] for p in self.neurons["position"]], dtype=np.int64)
            self.neurons = self.neurons.assign(source_id=real)
            self.edges = self.edges.assign(pre_id=[self.public_to_real[int(p)] for p in self.edges["pre_position"]],
                                           post_id=[self.public_to_real[int(p)] for p in self.edges["post_position"]])
            self.stimulus = {**self.stimulus, "source_ids": [self.public_to_real[int(p)] for p in self.stimulus["positions"]]}
        self.ids = self.neurons["source_id"].to_numpy().astype(np.int64)
        self.pos = {int(i): k for k, i in enumerate(self.ids)}
        n = len(self.ids)
        self.W = sp.csr_matrix((self.edges["signed_weight"].to_numpy(dtype=np.float64),
                                (self.edges["post_position"].to_numpy(), self.edges["pre_position"].to_numpy())), shape=(n, n))
        self.W.eliminate_zeros()  # observed pairs from unknown-NT presynaptic neurons carry signed_weight 0
        self.sizes = self.neurons["size_voxels"].to_numpy(dtype=np.float64)
        self.readout_mask = self.neurons["is_readout"].to_numpy(dtype=bool)
        self.stim_positions = [int(p) for p in self.stimulus["positions"]]
        self.current = float(self.stimulus["current"])

    @property
    def n(self) -> int:
        return len(self.ids)

    def has(self, source_id: int) -> bool:
        return int(source_id) in self.pos

    def realize(self, pred: BrainIRMechanismPrediction) -> BrainIRMechanismPrediction:
        """Translate a tier-A prediction (positional ids) into real body IDs; identity for tier B."""
        if not self.positional:
            return pred
        m = self.public_to_real

        def tr(i):
            if int(i) not in m:
                raise ValueError(f"prediction references position {i}, outside the network")
            return m[int(i)]

        d = pred.model_dump(mode="json")
        d["stimulus_source_ids"] = [tr(i) for i in d["stimulus_source_ids"]]
        for c in d["core_neurons"]:
            c["source_id"] = tr(c["source_id"])
        d["mechanism"]["loop_neurons"] = [tr(i) for i in d["mechanism"]["loop_neurons"]]
        for c in d["cross_connectome"]:
            c["source_id"] = tr(c["source_id"])  # other_source_id is translated by the other network's evaluator
        return BrainIRMechanismPrediction.model_validate(d)

    def type_of(self, source_id: int) -> str | None:
        v = self.neurons.loc[self.pos[int(source_id)], "cell_type"] if self.has(source_id) else None
        return None if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)

    def sign_of(self, source_id: int) -> int:
        return int(self.neurons.loc[self.pos[int(source_id)], "sign"]) if self.has(source_id) else 0


# ---------------------------------------------------------------------------- simulation helpers
def _run(net: BundleNetwork, cfg: ModelConfig, seed: int, intervention: Intervention | None) -> dict:
    params = sample_neuron_params(cfg, net.n, seed, net.sizes)
    traj = simulate(net.W, params, cfg, Stimulus(tuple(net.stim_positions), (net.current,)), intervention)
    win = traj.window(ANALYSIS_START_S)
    peak = win.max(axis=0)
    mask = (peak > ACTIVE_RATE_HZ) & net.readout_mask
    score, f, _, _ = network_oscillation_score(win, mask, DEFAULT_PROMINENCE)
    dt = float(traj.t[1] - traj.t[0])
    return {"seed": seed, "score": score, "frequency_hz": (f / dt) if f > 0 else None, "n_active_readout": int(mask.sum()),
            "success": bool(traj.info.get("success", True))}


def _batch(net: BundleNetwork, cfg: ModelConfig, seeds: list[int], intervention: Intervention | None, workers: int) -> list[dict]:
    jobs = [(net, cfg, s, intervention) for s in seeds]
    if workers > 1 and len(jobs) > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as ex:
            return list(ex.map(_run_star, jobs))
    return [_run_star(j) for j in jobs]


def _run_star(args):
    return _run(*args)


def _summ(rows: list[dict]) -> dict:
    s = np.array([r["score"] for r in rows])
    f = np.array([np.nan if r["frequency_hz"] is None else r["frequency_hz"] for r in rows])
    act = np.array([r["n_active_readout"] for r in rows])
    return {"n": int(len(rows)), "score_mean": float(s.mean()), "score_median": float(np.median(s)),
            "fraction_rhythmic": float((s >= RHYTHMIC).mean()), "frequency_median_hz": float(np.nanmedian(f)) if np.isfinite(f).any() else None,
            "active_readout_median": float(np.median(act)), "solver_failures": int(sum(not r["success"] for r in rows))}


# ---------------------------------------------------------------------------- metric families
def structural(pred: BrainIRMechanismPrediction, onet: OracleNetwork) -> dict:
    core = set(pred.core_ids())
    e_ids = onet.core_ids(("E1", "E2"))
    inh_ids = onet.core_ids(onet.inhibitory_slot)
    all_pub = onet.core_ids()
    inh_hit = sorted(core & inh_ids)
    reference = e_ids | (set(inh_hit) if inh_hit else onet.core_ids((onet.inhibitory_slot[0],)))
    inter = core & reference
    return {
        "n_predicted": len(core),
        "excitatory_core_recall": len(core & e_ids) / len(e_ids) if e_ids else None,
        "inhibitory_slot_filled": bool(inh_hit),
        "inhibitory_slot_members_found": [onet.label_of(i) for i in inh_hit],
        "precision_vs_all_published_labels": (len(core & all_pub) / len(core)) if core else None,
        "jaccard_vs_reference_core": (len(inter) / len(core | reference)) if (core | reference) else None,
        "published_labels_found": sorted({onet.label_of(i) for i in core & all_pub}),
        "modal_circuit_recovered": onet.core_ids(onet.modal_circuit) <= core,
        "compactness": {"n_core": len(core), "within_10": len(core) <= 10},
        "evidence_level_of_reference": onet.evidence.get("core"),
    }


def type_role(pred: BrainIRMechanismPrediction, onet: OracleNetwork, bnet: BundleNetwork, oracle_raw: dict) -> dict:
    labels = oracle_raw["labels"]
    type_to_label = {v["type"]: k for k, v in labels.items()}
    pred_types = {c.source_id: bnet.type_of(c.source_id) for c in pred.core_neurons}
    found = {type_to_label[t] for t in pred_types.values() if t in type_to_label}
    e_found = found & {"E1", "E2"}
    inh_found = found & set(onet.inhibitory_slot)
    # role agreement for neurons that are published core members (by ID)
    role_ok, role_n = 0, 0
    for c in pred.core_neurons:
        lab = onet.label_of(c.source_id)
        if lab is not None and c.role != "unknown":
            role_n += 1
            role_ok += int(c.role == onet.roles.get(lab))
    # sign consistency with the bundle's own NT label (oracle-free)
    sign_ok, sign_n = 0, 0
    for c in pred.core_neurons:
        if c.role != "unknown" and bnet.has(c.source_id):
            s = bnet.sign_of(c.source_id)
            if s != 0:
                sign_n += 1
                sign_ok += int((s > 0) == (c.role == "excitatory"))
    return {
        "type_level_excitatory_recall": len(e_found) / 2, "type_level_inhibitory_slot_filled": bool(inh_found),
        "published_types_found": sorted(found), "n_predicted_with_type": int(sum(t is not None for t in pred_types.values())),
        "role_agreement_with_oracle": {"n": role_n, "agree": role_ok, "fraction": (role_ok / role_n) if role_n else None},
        "role_consistent_with_network_sign": {"n": sign_n, "agree": sign_ok, "fraction": (sign_ok / sign_n) if sign_n else None},
        "note": "type-level credit counts any neuron of a published core type (e.g. a contralateral copy); tier A predictions "
                "still carry source_ids, so this layer is computed from the evaluator's own type table",
    }


def functional(pred: BrainIRMechanismPrediction, bnet: BundleNetwork, cfg: ModelConfig, seeds: list[int], workers: int) -> dict:
    core_pos = [bnet.pos[i] for i in pred.core_ids() if bnet.has(i)]
    missing = [i for i in pred.core_ids() if not bnet.has(i)]
    intact = _batch(bnet, cfg, seeds, None, workers)
    keep = tuple(core_pos)
    always = tuple(bnet.stim_positions) + tuple(int(p) for p in np.flatnonzero(bnet.readout_mask))
    suff = _batch(bnet, cfg, seeds, Intervention(keep_only=keep, always_keep=always), workers) if core_pos else []
    necessity = []
    for c in pred.core_neurons:
        if c.essential is None or not bnet.has(c.source_id):
            continue
        rows = _batch(bnet, cfg, seeds, Intervention(silence=(bnet.pos[c.source_id],)), workers)
        s = _summ(rows)
        abolished = s["fraction_rhythmic"] < 0.5
        necessity.append({"source_id": c.source_id, "claimed_essential": c.essential, "silenced_fraction_rhythmic": s["fraction_rhythmic"],
                          "silenced_score_mean": s["score_mean"], "observed_essential": abolished, "correct": abolished == c.essential})
    nec_correct = [x["correct"] for x in necessity]
    si, ss = _summ(intact), (_summ(suff) if suff else None)
    dyn = pred.dynamics
    freq_err = None
    if dyn.frequency_hz is not None and si["frequency_median_hz"] is not None:
        freq_err = abs(dyn.frequency_hz - si["frequency_median_hz"])
    return {
        "settings": {"n_replicates": len(seeds), "seeds": seeds, "t_end": cfg.t_end, "rhythmic_threshold": RHYTHMIC,
                     "keep_only_always_keeps": "stimulus + readout motor neurons"},
        "intact_network": si,
        "sufficiency_keep_only_core": ss,
        "sufficiency_pass": (ss is not None and ss["fraction_rhythmic"] >= 0.5),
        "core_neurons_missing_from_network": missing,
        "necessity": necessity,
        "necessity_accuracy": (sum(nec_correct) / len(nec_correct)) if nec_correct else None,
        "dynamics_claims": {"predicted_frequency_hz": dyn.frequency_hz, "simulated_frequency_median_hz": si["frequency_median_hz"],
                            "frequency_abs_error_hz": freq_err, "predicted_rhythmic": dyn.rhythmic,
                            "simulated_fraction_rhythmic": si["fraction_rhythmic"],
                            "predicted_n_active_readout": dyn.n_active_readout, "simulated_active_readout_median": si["active_readout_median"]},
    }


def mechanism(pred: BrainIRMechanismPrediction, bnet: BundleNetwork) -> dict:
    loop = [i for i in pred.mechanism.loop_neurons if bnet.has(i)]
    cyc = None
    if len(loop) >= 2:
        import networkx as nx
        g = nx.DiGraph()
        sub = bnet.edges[bnet.edges["pre_id"].isin(loop) & bnet.edges["post_id"].isin(loop)]
        g.add_nodes_from(loop)
        g.add_edges_from(zip(sub["pre_id"], sub["post_id"]))
        cyc = nx.is_strongly_connected(g)
    core = pred.core_ids()
    sub = bnet.edges[bnet.edges["pre_id"].isin(core) & bnet.edges["post_id"].isin(core)]
    stim_to_core = bnet.edges[bnet.edges["pre_id"].isin([bnet.ids[p] for p in bnet.stim_positions]) & bnet.edges["post_id"].isin(core)]
    core_to_readout = bnet.edges[bnet.edges["pre_id"].isin(core) & bnet.edges["post_id"].isin(bnet.ids[bnet.readout_mask])]
    return {"n_core": len(core), "internal_edges": int(len(sub)), "internal_synapses": int(sub["synapse_count"].sum()) if len(sub) else 0,
            "loop_claimed": pred.mechanism.loop_neurons, "loop_is_strongly_connected": cyc,
            "core_receives_stimulus_directly": bool(len(stim_to_core)), "core_projects_to_readout": bool(len(core_to_readout)),
            "motif_text": pred.mechanism.motif}


def cross_connectome(preds: dict[str, BrainIRMechanismPrediction], onets: dict[str, OracleNetwork], oracle_raw: dict) -> dict:
    """Do predictions on different networks name the same published labels, and do claimed correspondences match?"""
    labels_by_net = {}
    for name, p in preds.items():
        on = onets[name]
        labels_by_net[name] = {on.label_of(i) for i in p.core_ids() if on.label_of(i) is not None}
    names = sorted(labels_by_net)
    common = set.intersection(*labels_by_net.values()) if labels_by_net else set()
    pair_checks = []
    for name, p in preds.items():
        for cc in p.cross_connectome:
            other = next((n for n, o in onets.items() if (o.dataset, o.version) == (cc.other_dataset, cc.other_version)), None)
            la = onets[name].label_of(cc.source_id)
            lb = onets[other].label_of(cc.other_source_id) if other else None
            pair_checks.append({"from": name, "source_id": cc.source_id, "to": other, "other_source_id": cc.other_source_id,
                                "labels": [la, lb], "consistent": (la is not None and la == lb)})
    return {"networks_evaluated": names, "published_labels_per_network": {k: sorted(v) for k, v in labels_by_net.items()},
            "labels_recovered_in_all_networks": sorted(common),
            "excitatory_core_in_all": {"E1", "E2"} <= common if len(names) > 1 else None,
            "claimed_correspondences": pair_checks,
            "claimed_correspondence_accuracy": (sum(c["consistent"] for c in pair_checks) / len(pair_checks)) if pair_checks else None}


def robustness(pred: BrainIRMechanismPrediction, bnet: BundleNetwork, cfg: ModelConfig, seeds: list[int], workers: int) -> dict:
    core_pos = [bnet.pos[i] for i in pred.core_ids() if bnet.has(i)]
    if not core_pos:
        return {"skipped": "no predicted core neuron is in the network"}
    always = tuple(bnet.stim_positions) + tuple(int(p) for p in np.flatnonzero(bnet.readout_mask))
    out = {}
    for sd in (0.1, 0.3):
        rows = _batch(bnet, cfg, seeds, Intervention(keep_only=tuple(core_pos), always_keep=always, weight_noise_sd=sd, weight_noise_seed=7), workers)
        out[f"keep_only_core_weight_noise_{sd}"] = _summ(rows)
    wide = ModelConfig(**{**cfg.to_dict(), "tau_sd": cfg.tau_sd * 2, "a_sd": cfg.a_sd * 2, "theta_sd": cfg.theta_sd * 2, "r_max_sd": cfg.r_max_sd * 2})
    out["keep_only_core_parameter_sd_x2"] = _summ(_batch(bnet, wide, seeds, Intervention(keep_only=tuple(core_pos), always_keep=always), workers))
    return out


# ---------------------------------------------------------------------------- driver
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(pred_paths: list[Path], bundle: Path, *, n_replicates: int = 16, workers: int = 4, simulate_flag: bool = True,
             t_end: float = 1.0) -> dict:
    oracle_raw, onets = load_oracle()
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    preds: dict[str, BrainIRMechanismPrediction] = {}
    for p in pred_paths:
        pr = BrainIRMechanismPrediction.from_json(p.read_text(encoding="utf-8"))
        name = next((n["name"] for n in manifest["networks"] if (n["dataset"], n["version"]) == (pr.dataset, pr.dataset_version)), None)
        if name is None:
            raise ValueError(f"{p}: no network for {pr.dataset}:{pr.dataset_version} in the bundle")
        if pr.benchmark_id != manifest["benchmark_id"]:
            raise ValueError(f"{p}: benchmark_id {pr.benchmark_id!r} != bundle {manifest['benchmark_id']!r}")
        preds[name] = pr
    cfg = ModelConfig(t_end=t_end)
    seeds = list(range(1000, 1000 + n_replicates))
    per_net = {}
    t0 = time.time()
    bnets = {name: BundleNetwork(bundle, name) for name in preds}
    raw_digests = {name: pr.digest() for name, pr in preds.items()}
    for name in list(preds):  # translate positional ids (tier A) to body IDs before any comparison
        preds[name] = bnets[name].realize(preds[name])
        if preds[name].cross_connectome:
            fixed = []
            for c in preds[name].cross_connectome:
                other = next((n for n, o in onets.items() if (o.dataset, o.version) == (c.other_dataset, c.other_version)), None)
                if other in bnets and bnets[other].positional:
                    c = c.model_copy(update={"other_source_id": bnets[other].public_to_real[int(c.other_source_id)]})
                fixed.append(c)
            preds[name] = preds[name].model_copy(update={"cross_connectome": fixed})
    for name, pr in preds.items():
        bnet = bnets[name]
        onet = onets[name]
        if set(pr.stimulus_source_ids) != set(bnet.stimulus["source_ids"]):
            raise ValueError(f"{name}: prediction stimulus {pr.stimulus_source_ids} != bundle stimulus {bnet.stimulus['source_ids']}")
        res = {"prediction_sha256": raw_digests[name], "method": pr.method.model_dump(mode="json"),
               "structural": structural(pr, onet), "type_role": type_role(pr, onet, bnet, oracle_raw), "mechanism": mechanism(pr, bnet)}
        if simulate_flag:
            res["functional"] = functional(pr, bnet, cfg, seeds, workers)
            res["robustness"] = robustness(pr, bnet, cfg, seeds, workers)
        per_net[name] = res
    return {
        "evaluator_version": EVALUATOR_VERSION, "evaluator_sha256": _sha(Path(__file__)), "oracle_sha256": oracle_sha256(),
        "bundle": {"root": bundle.name, "benchmark_id": manifest["benchmark_id"], "bundle_sha256": manifest["bundle_sha256"], "tier": manifest["tier"]},
        "evidence_levels": EVIDENCE_LEVELS, "networks": per_net,
        "cross_connectome": cross_connectome(preds, onets, oracle_raw) if len(preds) > 1 else None,
        "simulation": {"enabled": simulate_flag, "n_replicates": n_replicates, "seeds": seeds, "t_end": t_end, "model_config": cfg.to_dict()},
        "wall_time_s": round(time.time() - t0, 1),
    }


def to_markdown(ev: dict) -> str:
    b = ev["bundle"]
    lines = [f"# Evaluation — {b['benchmark_id']} (tier {b['tier']})", "",
             f"evaluator {ev['evaluator_version']} `{ev['evaluator_sha256'][:12]}` · oracle `{ev['oracle_sha256'][:12]}` · "
             f"bundle `{b['bundle_sha256'][:12]}`", ""]
    for name, r in ev["networks"].items():
        s, t = r["structural"], r["type_role"]
        lines += [f"## {name} — method `{r['method']['name']}`", "", "| family | metric | value |", "|---|---|---|",
                  f"| structural | predicted core size | {s['n_predicted']} |",
                  f"| structural | excitatory core recall (E1, E2) | {s['excitatory_core_recall']} |",
                  f"| structural | inhibitory slot filled | {s['inhibitory_slot_filled']} {s['inhibitory_slot_members_found']} |",
                  f"| structural | precision vs published labels | {s['precision_vs_all_published_labels']} |",
                  f"| structural | Jaccard vs reference core | {s['jaccard_vs_reference_core']} |",
                  f"| type/role | type-level excitatory recall | {t['type_level_excitatory_recall']} |",
                  f"| type/role | role agreement with oracle | {t['role_agreement_with_oracle']} |",
                  f"| type/role | role consistent with network sign | {t['role_consistent_with_network_sign']} |",
                  f"| mechanism | internal edges / loop strongly connected | {r['mechanism']['internal_edges']} / "
                  f"{r['mechanism']['loop_is_strongly_connected']} |"]
        if "functional" in r:
            f = r["functional"]
            suff = f["sufficiency_keep_only_core"]
            suff_frac = None if suff is None else suff["fraction_rhythmic"]
            lines += [f"| functional | intact network fraction rhythmic | {f['intact_network']['fraction_rhythmic']} |",
                      f"| functional | keep-only core fraction rhythmic (sufficiency) | {suff_frac} → pass={f['sufficiency_pass']} |",
                      f"| functional | necessity accuracy | {f['necessity_accuracy']} ({len(f['necessity'])} claims) |",
                      f"| functional | frequency abs error (Hz) | {f['dynamics_claims']['frequency_abs_error_hz']} |"]
            for k, v in r["robustness"].items():
                if isinstance(v, dict) and "fraction_rhythmic" in v:
                    lines.append(f"| robustness | {k} | fraction rhythmic {v['fraction_rhythmic']} |")
        lines.append("")
    if ev.get("cross_connectome"):
        c = ev["cross_connectome"]
        lines += ["## cross-connectome", "", f"labels recovered in all networks: {c['labels_recovered_in_all_networks']}; "
                  f"claimed correspondence accuracy: {c['claimed_correspondence_accuracy']}", ""]
    return "\n".join(lines)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions", nargs="+", type=Path)
    ap.add_argument("--bundle", type=Path, default=HERE.parents[0] / "public")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n-replicates", type=int, default=16)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--t-end", type=float, default=1.0)
    ap.add_argument("--no-simulation", action="store_true")
    args = ap.parse_args(argv)
    ev = evaluate(args.predictions, args.bundle, n_replicates=args.n_replicates, workers=args.workers,
                  simulate_flag=not args.no_simulation, t_end=args.t_end)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ev, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    args.out.with_suffix(".md").write_text(to_markdown(ev), encoding="utf-8", newline="\n")
    print(to_markdown(ev))


if __name__ == "__main__":
    main()
