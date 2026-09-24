"""Truth-completeness audit of a synthetic instance: find UNPLANTED sufficient sets (goal3 section 7).

A generator plants a mechanism, but its complications can create other sets that satisfy the functional criterion on their own:
under an activity-band criterion a strongly driven hub or high-centrality distractor projecting onto the readout can drive the
readout into the band alone; under a selectivity criterion keep-only removes the competitor, so the winner alone suffices; a
backup copy can stand in for the member it copies. Scoring against the planted sets alone would punish a method for a correct
answer. The audit tests, on the true simulator and the verification seed ensemble, (1) every single candidate with a direct
synapse onto the readout, (2) every complication node and the complication sets, (3) every planted alternative with one member
replaced by its backup copy; each passing set is reduced to a 1-minimal subset.

A passing set is an unplanted ALTERNATIVE only if it participates in the intact network: every member's mean rate in the
analysis window of the intact runs is at least ``participation_threshold`` (max(0.05 Hz, 1 % of the planted core's median
rate)). A keep-only-sufficient set that the intact network keeps (near-)silent — e.g. a backup held off by an inhibitory gate —
is recorded as a LATENT BACKUP instead: sufficient in isolation, not the mechanism the network uses (review G finding 6).
The audit can only find what it tests: the tournament's functional-success metric covers sufficient sets it did not try.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from .interventions import keep_only
from .problem import DiscoveryProblem, path_basename, unpack_bundle
from .simulator import BudgetedSimulator

AUDIT_SEEDS = (0, 1, 2, 3)
PASS_THRESHOLD = 0.8
PARTICIPATION_MIN_HZ = 0.05
PARTICIPATION_REL = 0.01


def intact_mean_rates(problem: DiscoveryProblem, sim: BudgetedSimulator, seeds) -> np.ndarray:
    """Per-neuron mean rate in the analysis window, averaged over the intact runs that pass the criterion (all runs if none
    passes)."""
    outs = sim.evaluate(None, list(seeds))
    use = [o for o in outs if o.passed] or outs
    return np.mean([np.asarray(o.mean_rate_hz, dtype=float) for o in use], axis=0)


def participation_threshold(rates: np.ndarray, planted_core) -> float:
    core = [int(p) for p in planted_core]
    ref = float(np.median(rates[core])) if core else 0.0
    return max(PARTICIPATION_MIN_HZ, PARTICIPATION_REL * ref)


def participates(rates: np.ndarray, members, threshold: float) -> bool:
    return bool(len(members) == 0 or float(np.min(rates[[int(p) for p in members]])) >= threshold)


def _complications(comp: dict) -> tuple[set[int], list[frozenset[int]], dict | None]:
    nodes: set[int] = set()
    sets: list[frozenset[int]] = []
    hubs = [int(x) for x in comp.get("hub_distractor", []) or []]
    nodes |= set(hubs)
    if hubs:
        sets.append(frozenset(hubs))
    mc = comp.get("misleading_centrality")
    if isinstance(mc, (int, np.integer)):
        nodes.add(int(mc))
        if hubs:
            sets.append(frozenset([*hubs, int(mc)]))
    backup = comp.get("backup_copy") if isinstance(comp.get("backup_copy"), dict) else None
    if backup:
        nodes.add(int(backup["copy"]))
    return nodes, sets, backup


def find_unplanted_alternatives(problem: DiscoveryProblem, truth_net: dict, *, seeds=AUDIT_SEEDS, pass_threshold: float = PASS_THRESHOLD,
                                max_singles: int = 600) -> dict:
    sim = BudgetedSimulator(problem, max_calls=10 ** 9)
    old_unplanted = {frozenset(int(p) for p in a) for a in truth_net.get("unplanted_alternatives_positions", [])}
    planted = [frozenset(int(p) for p in a) for a in truth_net["alternatives_positions"]]
    planted = [a for a in planted if a not in old_unplanted]
    always = set(int(p) for p in problem.always_keep())
    readout = problem.readout_positions
    proj = np.flatnonzero(np.asarray(problem.C[readout, :].sum(axis=0)).ravel() > 0)
    singles = {int(p) for p in proj if int(p) not in always}
    comp_nodes, comp_sets, backup = _complications(truth_net.get("complication_positions", {}) or {})
    singles |= comp_nodes - always
    candidates: list[frozenset[int]] = [frozenset([s]) for s in sorted(singles)[:max_singles]] + comp_sets
    if backup:
        of, cp = int(backup["of"]), int(backup["copy"])
        candidates += [frozenset((a - {of}) | {cp}) for a in planted if of in a]
    seen: set[frozenset[int]] = set()
    found: list[frozenset[int]] = []
    tested = 0

    def passes(s) -> bool:
        return sim.pass_fraction(keep_only(problem, sorted(s)), list(seeds)) >= pass_threshold

    for s in candidates:
        if s in seen or any(p <= s for p in planted):
            continue
        seen.add(s)
        tested += 1
        if not passes(s):
            continue
        m = set(s)
        changed = True
        while changed and len(m) > 1:  # reduce to a 1-minimal subset
            changed = False
            for v in sorted(m):
                if passes(m - {v}):
                    m.discard(v)
                    changed = True
                    break
        fm = frozenset(m)
        if fm not in found and fm not in planted:
            found.append(fm)
    rates = intact_mean_rates(problem, sim, seeds)
    thr = participation_threshold(rates, truth_net["core_positions"])
    valid = [f for f in found if participates(rates, f, thr)]
    latent = [f for f in found if f not in valid]
    return {"tested": tested, "found": [sorted(int(x) for x in f) for f in valid], "latent_backups": [sorted(int(x) for x in f) for f in latent],
            "seeds": list(seeds), "pass_threshold": pass_threshold, "n_singles": len(singles), "calls": sim.calls,
            "participation_threshold_hz": thr, "planted_participation": [participates(rates, a, thr) for a in planted]}


def apply_audit(truth_net: dict, audit: dict) -> dict:
    """Return a copy of the truth network entry with the unplanted alternatives recorded (idempotent)."""
    t = dict(truth_net)
    old_unplanted = {tuple(sorted(int(p) for p in a)) for a in t.get("unplanted_alternatives_positions", [])}
    planted = [sorted(int(p) for p in a) for a in t["alternatives_positions"] if tuple(sorted(int(p) for p in a)) not in old_unplanted]
    unplanted = [a for a in audit["found"] if tuple(a) not in {tuple(p) for p in planted}]
    t["alternatives_positions"] = planted + unplanted
    t["unplanted_alternatives_positions"] = unplanted
    t["latent_backups_positions"] = [a for a in audit.get("latent_backups", []) if tuple(a) not in {tuple(p) for p in planted}]
    t["alternatives_audit"] = {k: audit[k] for k in ("tested", "seeds", "pass_threshold", "n_singles", "calls", "participation_threshold_hz",
                                                        "planted_participation") if k in audit}
    return t


def reclassify_participation(problem: DiscoveryProblem, truth_net: dict, *, seeds=AUDIT_SEEDS) -> dict:
    """Upgrade an ALREADY-audited truth network entry without searching again: move unplanted alternatives that do not
    participate in the intact network to ``latent_backups_positions``, and add the silencing pass fraction (sigma) of every node
    of a planted alternative where it is missing (``essential_pass_fraction_positions``; the verification recorded only
    sigma < 0.2). Returns the new entry plus a small report."""
    from .interventions import silence

    t = dict(truth_net)
    sim = BudgetedSimulator(problem, max_calls=10 ** 9)
    rates = intact_mean_rates(problem, sim, seeds)
    thr = participation_threshold(rates, t["core_positions"])
    unplanted = [sorted(int(p) for p in a) for a in t.get("unplanted_alternatives_positions", [])]
    keep = [a for a in unplanted if participates(rates, a, thr)]
    latent = [a for a in unplanted if a not in keep] + [a for a in t.get("latent_backups_positions", []) if a not in unplanted]
    planted = [sorted(int(p) for p in a) for a in t["alternatives_positions"] if sorted(int(p) for p in a) not in unplanted]
    t["alternatives_positions"] = planted + keep
    t["unplanted_alternatives_positions"] = keep
    t["latent_backups_positions"] = latent
    if not t.get("essential_pass_fraction_positions"):
        nodes = sorted({int(p) for a in planted for p in a})
        t["essential_pass_fraction_positions"] = {p: sim.pass_fraction(silence([p]), list(seeds)) for p in nodes}
    audit = dict(t.get("alternatives_audit") or {})
    audit.update(participation_threshold_hz=thr, planted_participation=[participates(rates, a, thr) for a in planted],
                 reclassified=True, reclassify_seeds=list(seeds))
    t["alternatives_audit"] = audit
    return {"truth_net": t, "moved_to_latent": [a for a in unplanted if a not in keep], "threshold_hz": thr, "calls": sim.calls}


def reclassify_job(args) -> dict:
    """(instance_dir, network, truth_net, packs) -> {instance, network, result}; module-level so backends can run it."""
    inst_dir, network, truth_net, packs = args
    inst_dir = Path(inst_dir)
    name = path_basename(inst_dir)
    if not inst_dir.exists() and packs is not None:
        inst_dir = unpack_bundle(packs[name], Path(tempfile.mkdtemp(prefix="brainir_reclass_")) / name)
    problem = DiscoveryProblem.from_bundle(inst_dir, network)
    return {"instance": name, "network": network, "result": reclassify_participation(problem, truth_net)}


def audit_job(args) -> dict:
    """(instance_dir, network, truth_net, packs) -> {instance, network, audit}; module-level so backends can run it."""
    inst_dir, network, truth_net, packs = args
    inst_dir = Path(inst_dir)
    name = path_basename(inst_dir)
    if not inst_dir.exists() and packs is not None:
        inst_dir = unpack_bundle(packs[name], Path(tempfile.mkdtemp(prefix="brainir_audit_")) / name)
    problem = DiscoveryProblem.from_bundle(inst_dir, network)
    return {"instance": name, "network": network, "audit": find_unplanted_alternatives(problem, truth_net)}


def audit_suite(suite_root: Path | str, *, backend=None, workers: int = 1, instances: list[str] | None = None) -> dict:
    """Audit every (instance, network) of a suite and rewrite its truth files with the unplanted alternatives."""
    from ..compute.backend import Shared, split_failures
    from .problem import pack_bundle

    suite_root = Path(suite_root)
    jobs, packs = [], {}
    for tpath in sorted((suite_root / "truth").glob("*.json")):
        if tpath.name in ("SALT.txt",) or not (suite_root / "instances" / tpath.stem).exists():
            continue
        if instances and tpath.stem not in set(instances):
            continue
        truth = json.loads(tpath.read_text(encoding="utf-8"))
        inst = suite_root / "instances" / tpath.stem
        for net, tnet in truth["networks"].items():
            jobs.append((str(inst), net, tnet, None))
        if backend is not None:
            pack: dict[str, bytes] = {}
            for net in truth["networks"]:
                pack.update(pack_bundle(inst, net))
            packs[tpath.stem] = pack
    if backend is not None:
        results, failed = split_failures(backend.map(audit_job, [(*j[:3], Shared("packs")) for j in jobs], shared={"packs": packs}))
    elif workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as ex:
            results, failed = list(ex.map(audit_job, jobs)), []
    else:
        results, failed = [audit_job(j) for j in jobs], []
    by_inst: dict[str, dict[str, dict]] = {}
    for r in results:
        by_inst.setdefault(r["instance"], {})[r["network"]] = r["audit"]
    n_found = 0
    for name, audits in by_inst.items():
        tpath = suite_root / "truth" / f"{name}.json"
        truth = json.loads(tpath.read_text(encoding="utf-8"))
        for net, a in audits.items():
            truth["networks"][net] = apply_audit(truth["networks"][net], a)
            n_found += len(a["found"])
        tpath.write_text(json.dumps(truth, indent=1) + "\n", encoding="utf-8", newline="\n")
    return {"n_jobs": len(jobs), "n_failed": len(failed), "failed": failed[:5], "n_unplanted_found": n_found,
            "instances_with_unplanted": sorted(n for n, a in by_inst.items() if any(x["found"] for x in a.values()))}
