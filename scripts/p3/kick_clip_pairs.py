"""Synthetic kick-clip pairs (ORCHESTRATOR / TRUTH side; benchmark version 3, pre-lock review D M2 and review H M1).

    uv run --project phase3 --no-sync python scripts/p3/kick_clip_pairs.py --tier dev [--workers 8] [--splits test]

The synthetic generator applies a kick in the recorded state x = phi(v). It clips x_j + delta into the bijection's open range
(relative eps 1e-6 of the neuron's scale) and inverts it (p3synth.core, Implementation.simulate). A kick that pushes x_j outside the
range (scaled tanh: |x| >= s (1 - eps); scaled logistic: x <= s eps or x >= s (1 - eps); identity neurons never) therefore injects a
very large activation jump (arctanh / logit next to the boundary). This is an artefact of the generator. This script replays every
kick of the intervention trajectories of the listed splits on the generator. It uses the trajectory's own protocol (with its
events), so the pre-kick state is exact, and it lists the trajectories with at least one kick that leaves the range.

Output: <tier truth dir>/kick_clip_pairs.json. It is used for a pre-registered DESCRIPTIVE sensitivity of held-out C (these pairs
excluded). The file is truth-side and never goes into a clean room. The suite seed is derived as in build_synthetic_suites.py and is
never written out.

Format (p3-kick-clip-pairs-1):
    {"format", "tier", "splits", "generator_eps", "criterion",
     "n_trajectories_with_kicks", "n_clipped",
     "counts": {family: {"n_with_kicks", "n_clipped", "n_kicked_neurons", "n_outside_neurons"}},
     "clipped_keys": [sorted keys of the intervened (test) trajectories with >= 1 kick leaving the range],
     "pairs": [{"system_id", "family", "split", "key", "pair", "twin_key", "n_kick_events", "n_kicked_neurons", "n_outside",
                "max_abs_dv_over_scale"} for every clipped trajectory]}
The evaluator's per-pair units (brainir_state.evaluate.eval_intervention "_units") are keyed by the intervened trajectory's key, so
`clipped_keys` is the exclusion set.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p3"))
sys.path.insert(0, str(ROOT / "phase3" / "src"))
sys.path.insert(0, str(ROOT / "benchmarks" / "state_discovery_v1" / "generator"))      # p3synth (= build_synthetic_suites.GEN)

EPS = 1e-6                     # the generator's clip (p3synth.core.Phi.inv / clip default)
FORMAT = "p3-kick-clip-pairs-1"
_SYSTEMS: dict = {}


def kick_leaves_range(kind: int, scale: float, x_new: float, eps: float = EPS) -> bool:
    """True when the kicked recorded state lies outside the open range the generator's inverse accepts (p3synth.core.Phi)."""
    from p3synth.core import PHI_LOGI, PHI_TANH
    if kind == PHI_TANH:
        return abs(x_new) >= scale * (1 - eps)
    if kind == PHI_LOGI:
        return not (scale * eps < x_new < scale * (1 - eps))
    return False


def replay_kicks(phi, v_pre_by_step: dict[int, np.ndarray], protocol: dict, eps: float = EPS) -> dict:
    """Replay the protocol's kicks on the pre-event activations v (per step, as the generator records them before applying the step's
    events), in the protocol's event order, exactly as Implementation.simulate applies them. Returns counts and the largest
    activation jump |dv_j| / scale_j of a neuron whose kicked state left the range."""
    dt = float(protocol["dt"])
    by_step: dict[int, list] = defaultdict(list)
    for e in protocol.get("events") or []:
        if e["kind"] == "kick":
            by_step[int(round(e["t"] / dt))].append(e)
    n_ev = n_neu = n_out = 0
    worst = 0.0
    for i, evs in sorted(by_step.items()):
        v = np.array(v_pre_by_step[i], float, copy=True)
        for e in evs:
            x_now = phi.fwd(v)
            for j, d in e["delta"].items():
                x_now[int(j)] += d
            v_new = phi.inv(phi.clip(x_now, eps), eps)
            n_ev += 1
            for j in e["delta"]:
                j = int(j)
                n_neu += 1
                if kick_leaves_range(int(phi.kind[j]), float(phi.scale[j]), float(x_now[j]), eps):
                    n_out += 1
                    worst = max(worst, abs(float(v_new[j] - v[j])) / float(phi.scale[j]))
            v = v_new
    return {"n_kick_events": n_ev, "n_kicked_neurons": n_neu, "n_outside": n_out, "max_abs_dv_over_scale": worst}


def _systems(tier: str) -> dict:
    if tier not in _SYSTEMS:
        import build_synthetic_suites as B
        sys.path.insert(0, str(B.GEN))
        from p3synth.systems import build_all
        _SYSTEMS[tier] = {s.system_id: s for s in build_all(B.tier_seed(tier), tier)}
    return _SYSTEMS[tier]


def _system_worker(args) -> list[dict]:
    """All listed rows of one system: simulate each protocol (with its events, full microstate) and replay its kicks."""
    tier, sid, rows = args
    s = _systems(tier)[sid]
    out = []
    for r in rows:
        p = r["protocol"]
        sim = s.simulate(p, full=True)
        dt = float(p["dt"])
        steps = {int(round(e["t"] / dt)) for e in p.get("events") or [] if e["kind"] == "kick"}
        rep = replay_kicks(s.impl.phi, {i: sim["v_full"][i] for i in steps}, p)
        out.append({"system_id": sid, "family": r["family"], "split": r["split"], "key": r["key"], "pair": (r.get("info") or {}).get("pair"),
                    **rep})
    return out


def run(tier: str, splits: tuple[str, ...] = ("test",), workers: int = 8) -> dict:
    import build_synthetic_suites as B
    pub, truth = B.paths(tier)
    rows = [json.loads(line) for line in (pub / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    twins = {(r["system_id"], (r.get("info") or {}).get("pair")): r["key"] for r in rows if r["split"] == "twin"}
    todo = [r for r in rows if r["split"] in splits and any(e["kind"] == "kick" for e in r["protocol"].get("events") or [])]
    by_sys: dict[str, list] = defaultdict(list)
    for r in todo:
        by_sys[r["system_id"]].append(r)
    results = []
    with ProcessPoolExecutor(max_workers=max(1, workers)) as ex:
        for part in ex.map(_system_worker, [(tier, sid, rs) for sid, rs in sorted(by_sys.items())]):
            results += part
    counts: dict[str, dict] = {}
    for r in results:
        c = counts.setdefault(r["family"], {"n_with_kicks": 0, "n_clipped": 0, "n_kicked_neurons": 0, "n_outside_neurons": 0})
        c["n_with_kicks"] += 1
        c["n_clipped"] += int(r["n_outside"] > 0)
        c["n_kicked_neurons"] += r["n_kicked_neurons"]
        c["n_outside_neurons"] += r["n_outside"]
    clipped = sorted((r for r in results if r["n_outside"] > 0), key=lambda r: r["key"])
    for r in clipped:
        r["twin_key"] = twins.get((r["system_id"], r["pair"]))
    return {"format": FORMAT, "tier": tier, "splits": list(splits), "generator_eps": EPS,
            "criterion": "at least one kicked neuron whose recorded state x_j + delta leaves the open range of its bijection "
                         "(scaled tanh: |x| >= s (1 - eps); scaled logistic: x <= s eps or x >= s (1 - eps)); the generator then clips "
                         "and inverts it",
            "n_trajectories_with_kicks": len(results), "n_clipped": len(clipped), "counts": dict(sorted(counts.items())),
            "clipped_keys": [r["key"] for r in clipped],
            "pairs": [{k: r[k] for k in ("system_id", "family", "split", "key", "pair", "twin_key", "n_kick_events", "n_kicked_neurons",
                                         "n_outside", "max_abs_dv_over_scale")} for r in clipped]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", required=True, choices=("dev", "heldout", "final"))
    ap.add_argument("--splits", default="test")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args(argv)
    import build_synthetic_suites as B
    t0 = time.time()
    res = run(args.tier, tuple(s for s in args.splits.split(",") if s), args.workers)
    out = B.paths(args.tier)[1] / "kick_clip_pairs.json"
    out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{args.tier}: {res['n_clipped']} of {res['n_trajectories_with_kicks']} trajectories with kicks have a kick leaving the "
          f"range ({time.time() - t0:.0f} s) -> {out}")
    for fam, c in res["counts"].items():
        print(f"  {fam:18s} {c['n_clipped']:4d} / {c['n_with_kicks']:4d} trajectories; {c['n_outside_neurons']} / {c['n_kicked_neurons']} "
              "kicked neurons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
