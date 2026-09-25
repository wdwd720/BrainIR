"""state_discovery_v1: real systems and PUBLIC real trajectories (orchestrator; before method development).

    uv run --project phase3 python scripts/p3/generate_real_data.py [--workers 12]

1. systems: for each network, the full system and one keep-only system per VALIDATED regenerated candidate
   (research/phase3/candidates/regenerated_candidates.json); populations by the public probe rule (brainir_state.realgen);
   networks anonymised as net1 / net2 / net3 (mapping -> benchmarks/state_discovery_v1/hidden/network_map.json, never public);
2. writes benchmarks/state_discovery_v1/hidden/systems_internal.json (for the simulation service and the hidden generator) and
   benchmarks/state_discovery_v1/public/systems_public.json (populations, public targets A, local signed graph, signs; no dataset
   names) and research/phase3/candidates/regenerated_candidates_public.json (sanitised candidates);
3. creates the secret salt for the hidden test (data/phase3/hidden/salt.txt, git-ignored) and records only its sha256;
4. generates the public train / val trajectories (families of PROTOCOL.md section 3, public seeds) through the content-addressed
   store and writes the dataset data/phase3/real_public/ (brainir_state.data format).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from brainir_state import data as D
from brainir_state import protocol as P
from brainir_state.realgen import (INTERVENTION_FAMILIES, PUBLIC_FAMILIES, Sampler, build_systems, counterfactual, family_protocol, mech_id,
                                   split_targets)
from brainir_state.realsim import ENGINE_VERSION, RealEngine, RealSystem, dense
from brainir_state.store import TrajectoryStore

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "benchmarks" / "dng100" / "public_blind"
BENCH = ROOT / "benchmarks" / "state_discovery_v1"
DATA = ROOT / "data" / "phase3"
NET_MAP = {"manc_v1.2.1": "net1", "male-cns_v1.0": "net2", "manc_v1.2.3": "net3"}
COUNTS_FULL = {"train": {"nominal": 40, "stim_amp": 60, "init_state": 60, "kick_A": 60, "pulse_A": 40, "silence1_A": 60, "weight_noise": 20},
               "val": {"nominal": 10, "stim_amp": 15, "init_state": 15, "kick_A": 15, "pulse_A": 10, "silence1_A": 15, "weight_noise": 5}}
COUNTS_MECH = {s: {f: max(3, n // 2) for f, n in c.items()} for s, c in COUNTS_FULL.items()}


def _public_seed(*parts) -> int:
    return int(hashlib.sha256("|".join(str(p) for p in ("public",) + parts).encode()).hexdigest()[:12], 16) % (10**9)


def sysdef(s: RealSystem, bundle_sha: str) -> dict:
    A, B = split_targets(s)
    return {"system_id": s.system_id, "network": s.network, "mode": s.mode, "keep": list(s.keep), "observed": list(s.observed),
            "readout": list(s.readout), "stimulus": list(s.stimulus), "targets_public": A, "targets_heldout": B,
            "system_hash": s.content_hash(bundle_sha), "meta": s.meta}


def _run_one(args):
    sd, proto, store_root = args
    s = RealSystem(system_id=sd["system_id"], network=sd["network"], mode=sd["mode"], keep=tuple(sd["keep"]), observed=tuple(sd["observed"]),
                   readout=tuple(sd["readout"]), stimulus=tuple(sd["stimulus"]))
    global _ENG
    try:
        _ENG
    except NameError:
        _ENG = {}
    if sd["network"] not in _ENG:
        _ENG[sd["network"]] = RealEngine(BUNDLE, sd["network"])
    key, rec, _ = TrajectoryStore(store_root).get_or_run(_ENG[sd["network"]], s, proto, sd["system_hash"], meta={"source": "public"})
    return key, {"t": rec["t"], "x": dense(rec, sd["observed"]), "u": rec["u"], "y": dense(rec, sd["readout"])}, rec["info"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args(argv)
    cands = json.loads((ROOT / "research" / "phase3" / "candidates" / "regenerated_candidates.json").read_text(encoding="utf-8"))
    bundle_sha = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))["bundle_sha256"]
    internal, public, cand_public = {}, {}, {"rule": "every candidate of the locked Phase 2 method at seed 0 (final core + enumerated "
                                                      "alternatives) that passes keep-only on >= 4 of 8 fresh public seeds", "networks": {}}
    for net, anon in NET_MAP.items():
        eng = RealEngine(BUNDLE, net)
        rows = [c for c in cands["networks"][net]["candidates"] if c["validated"]]
        systems = build_systems(BUNDLE, net, [c["members"] for c in rows], engine=eng)
        # public ids: the network name is replaced by its anonymous label
        for s in systems:
            pub_id = s.system_id.replace(f"real:{net}:", f"real:{anon}:")
            s2 = RealSystem(system_id=pub_id, network=net, mode=s.mode, keep=s.keep, observed=s.observed, readout=s.readout,
                            stimulus=s.stimulus, meta=s.meta)
            d = sysdef(s2, bundle_sha)
            internal[pub_id] = d
            nodes = sorted(set(s.observed) | set(s.readout) | set(s.stimulus) | set(s.keep))
            W = eng.problem.W.tocsr()
            sub = W[nodes][:, nodes].tocoo()
            public[pub_id] = {"system_id": pub_id, "network": anon, "mode": s.mode, "members": list(s.keep), "observed": list(s.observed),
                              "readout": list(s.readout), "stimulus": list(s.stimulus), "targets_public": d["targets_public"],
                              "input_dim": max(1, len(s.stimulus)), "dt": 0.001, "t_end_default": 2.0,
                              "local_graph": {"nodes": nodes, "edges_post_pre_signed_count": [[nodes[i], nodes[j], float(v)] for i, j, v in
                                                                                                zip(sub.row, sub.col, sub.data)]},
                              "signs": {str(n): int(eng.problem.signs[n]) for n in nodes}}
        cand_public["networks"][anon] = [{"system_id": mech_id(anon, c["members"]), "label": c["label"], "members": c["members"],
                                          "size": c["size"], "keep_only_pass_fraction": c["keep_only_pass_fraction"]} for c in rows]
    (BENCH / "hidden").mkdir(parents=True, exist_ok=True)
    (BENCH / "public").mkdir(parents=True, exist_ok=True)
    (BENCH / "hidden" / "network_map.json").write_text(json.dumps(NET_MAP, indent=1) + "\n", encoding="utf-8", newline="\n")
    (BENCH / "hidden" / "systems_internal.json").write_text(json.dumps(internal, indent=1) + "\n", encoding="utf-8", newline="\n")
    (BENCH / "public" / "systems_public.json").write_text(json.dumps(public, indent=1) + "\n", encoding="utf-8", newline="\n")
    (ROOT / "research" / "phase3" / "candidates" / "regenerated_candidates_public.json").write_text(json.dumps(cand_public, indent=1) + "\n",
                                                                                                   encoding="utf-8", newline="\n")
    salt_path = DATA / "hidden" / "salt.txt"
    salt_path.parent.mkdir(parents=True, exist_ok=True)
    if not salt_path.exists():
        salt_path.write_text(secrets.token_hex(32), encoding="utf-8")
    (BENCH / "hidden" / "salt_commitment.json").write_text(json.dumps({"sha256_of_salt": hashlib.sha256(salt_path.read_text().encode()).hexdigest(),
                                                                       "note": "salt revealed after the Level C evaluation"}, indent=1) + "\n",
                                                           encoding="utf-8", newline="\n")
    # ---- public trajectories
    jobs, rows_meta = [], []
    for sid, d in internal.items():
        A, _ = d["targets_public"], d["targets_heldout"]
        counts = COUNTS_FULL if d["mode"] == "full" else COUNTS_MECH
        sysobj = RealSystem(system_id=sid, network=d["network"], mode=d["mode"], keep=tuple(d["keep"]), observed=tuple(d["observed"]),
                            readout=tuple(d["readout"]), stimulus=tuple(d["stimulus"]))
        for split, fams in counts.items():
            for fam in PUBLIC_FAMILIES:
                rng = np.random.default_rng(_public_seed(sid, split, fam))
                smp = Sampler(sysobj, rng, seed_fn=lambda r=rng: int(r.integers(0, 10**9)), state_pool=None)
                for j in range(fams.get(fam, 0)):
                    proto = P.validate(family_protocol(fam, smp, A, []))
                    jobs.append((d, proto, str(DATA / "store")))
                    if split == "val" and fam in INTERVENTION_FAMILIES:
                        # validation interventions get a counterfactual twin (same seed / state / inputs, no events) so that the
                        # public evaluator's family C can be computed on public data
                        pair = f"{fam}:{j}"
                        rows_meta.append({"system_id": sid, "split": split, "family": fam, "pair": pair})
                        jobs.append((d, P.validate(counterfactual(proto)), str(DATA / "store")))
                        rows_meta.append({"system_id": sid, "split": "twin", "family": fam, "pair": pair})
                    else:
                        rows_meta.append({"system_id": sid, "split": split, "family": fam})
    print(f"{len(internal)} systems; {len(jobs)} public trajectories", flush=True)
    items = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for (key, arrs, info), meta, (d, proto, _) in zip(ex.map(_run_one, jobs, chunksize=4), rows_meta, jobs):
            info_row = {"success": info.get("success"), "engine": ENGINE_VERSION}
            if meta.get("pair"):
                info_row["pair"] = meta["pair"]
            items.append(({"key": key, **{k: v for k, v in meta.items() if k != "pair"}, "protocol": proto, "info": info_row}, arrs))
    manifest = {"dataset_id": "state_discovery_v1/real_public", "version": "1", "dt": 0.001,
                # the full public definition (incl. the local signed graph) is what a method receives at fit time (systems=...)
                "systems": {sid: dict(public[sid]) | {"kind": "real"} for sid in public},
                "splits": ["train", "val", "twin"], "families": list(PUBLIC_FAMILIES),
                "notes": "split 'twin': the counterfactual twin (same seed, state and inputs, no events) of a validation intervention "
                         "trajectory; info.pair links the two"}
    D.write_dataset(DATA / "real_public", manifest, items)
    n_fail = sum(1 for r, _ in items if not r["info"]["success"])
    print(f"wrote {len(items)} trajectories to data/phase3/real_public ({n_fail} integration warnings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
