"""Counterexample search against a fitted state model (goal4 sections 53-54, 87; acceptance criterion 37).

    uv run --project phase3 python scripts/p3/counterexamples.py --method-dir DIR --model PKL --system SID --kind real|synthetic
        [--budget 60] [--seed 0] [--hidden] [--out FILE] [--tier heldout]

Searches the space of protocols for the one where the model disagrees most with the simulator:
- stimulus schedule;
- 1-3 kicks on any observed neurons;
- 1-2 current pulses;
- silencing of 1-4 neurons;
- initial-state perturbations.

The objective is the model's normalised error over the future window after the first event (the protocol's post-event NMSE of the
readout, per readout variance from public training data), measured against the simulator's trajectory. Half the budget goes to
random protocols (the reference distribution), half to mutation of the current worst protocols (a (mu, lambda) evolutionary step).
The report is the random distribution against the worst errors found, and the top counterexamples.

With --hidden (after the lock), parameter draws come from the hidden range derived from the benchmark salt, so the counterexamples
are hidden evaluation material (logged in research/phase3/HIDDEN_EVALUATIONS.md). Without it, public draws are used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))


def _simulator(kind: str, sid: str, tier: str):
    if kind == "synthetic":
        from brainir_state.synthsim import simulate
        rec = json.loads((ROOT / "benchmarks" / "state_discovery_v1" / "hidden" / "synthetic_suites.json").read_text(encoding="utf-8"))[tier]
        return lambda p: simulate(tier, int(rec["seed"]), sid, p)
    from brainir_state.suite_eval import _simulator as real_sim
    spec = {"kind": "real", "systems_internal": str(ROOT / "benchmarks" / "state_discovery_v1" / "hidden" / "systems_internal.json"),
            "bundle": str(ROOT / "benchmarks" / "dng100" / "public_blind")}
    return real_sim(spec, sid)


def _rand_protocol(rng, sid, info, kind, t_end, dt, seed_fn):
    obs = [int(n) for n in info["observed"]]
    events = []
    t_ev = round(float(rng.uniform(0.3, 0.6) * t_end) / dt) * dt
    n_ev = int(rng.integers(1, 3))
    for j in range(n_ev):
        c = rng.random()
        tj = round(t_ev + j * float(rng.uniform(0.0, 0.15) * t_end) / 1.0 / dt) * dt
        tgt = [int(v) for v in rng.choice(obs, min(len(obs), int(rng.integers(1, 5))), replace=False)]
        if c < 0.4:
            amp = float(rng.uniform(5, 30)) if kind == "real" else float(rng.uniform(0.5, 3.0))
            events.append({"kind": "kick", "t": round(tj, 6), "delta": {str(n): float(rng.choice([-1, 1]) * amp) for n in tgt[:3]}})
        elif c < 0.7:
            amp = float(rng.uniform(5, 40)) if kind == "real" else float(rng.uniform(0.5, 3.0))
            events.append({"kind": "current", "t0": round(tj, 6), "t1": round(tj + float(rng.uniform(0.02, 0.15) * t_end), 6),
                           "targets": {str(n): float(rng.choice([-1, 1]) * amp) for n in tgt[:2]}})
        else:
            events.append({"kind": "silence", "t0": round(tj, 6), "t1": round(tj + float(rng.uniform(0.05, 0.3) * t_end), 6),
                           "targets": tgt})
    scale = float(rng.uniform(0.5, 1.5))
    stim = [[0.0, 0.0], [round(float(rng.uniform(0.01, 0.1) * t_end) / dt * dt, 6), scale]]
    if kind == "synthetic" and int(info.get("input_dim", 1)) > 1:
        stim = [[0.0, [0.0] * int(info["input_dim"])], [stim[1][0], [scale] * int(info["input_dim"])]]
    p = {"system": sid, "params_seed": seed_fn(), "t_end": t_end, "dt": dt, "stimulus": stim, "events": sorted(events, key=lambda e: e.get("t", e.get("t0"))),
         "r0": {"kind": "zero"}}
    if kind == "real":
        p["weight_noise"] = None
    return p


def _mutate(rng, p, info, kind, t_end, dt):
    q = json.loads(json.dumps(p))
    for e in q["events"]:
        if e["kind"] == "kick":
            for k in e["delta"]:
                e["delta"][k] *= float(np.exp(rng.normal(0, 0.3)))
        elif e["kind"] == "current":
            for k in e["targets"]:
                e["targets"][k] *= float(np.exp(rng.normal(0, 0.3)))
        key = "t" if "t" in e else "t0"
        shift = round(float(rng.normal(0, 0.03) * t_end) / dt) * dt
        e[key] = round(min(max(0.2 * t_end, e[key] + shift), 0.7 * t_end), 6)
        if e.get("t1") is not None:
            e["t1"] = round(min(max(e[key] + dt, e["t1"] + shift), 0.95 * t_end), 6)
    return q


def score(model, sid, p, sim, scale, horizon_s):
    """Post-event NMSE of the model's rollout (encoded at the first event time) against the simulator."""
    out = sim(p)
    dt = float(p["dt"])
    t_ev = min(e.get("t", e.get("t0")) for e in p["events"])
    i0 = int(round(t_ev / dt))
    n = int(round(horizon_s / dt))
    if i0 + n >= len(out["t"]):
        n = len(out["t"]) - i0 - 1
    from brainir_state.evaluate import shift_events
    kinds = {e["kind"] for e in p["events"]}
    if not all(model.supports(sid, k) for k in kinds):
        return None
    z0 = np.asarray(model.encode(sid, out["x"][: i0 + 1], out["u"][: i0 + 1], dt), float)
    ev = shift_events(p["events"], t_ev, n * dt)
    yp = np.asarray(model.rollout(sid, z0, out["u"][i0: i0 + n + 1], ev, dt)["y"], float)[1:]
    return float(np.mean((yp - out["y"][i0 + 1: i0 + n + 1]) ** 2 / scale))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method-dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--system", required=True)
    ap.add_argument("--kind", choices=("real", "synthetic"), required=True)
    ap.add_argument("--tier", default="heldout")
    ap.add_argument("--budget", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--hidden", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    from brainir_state import evaluate as E
    from brainir_state.runner import load_model
    from brainir_state.suite_eval import SuiteData
    model = load_model(args.method_dir, args.model)
    if args.kind == "real":
        sd = SuiteData(ROOT / "data" / "phase3" / "real_public", kind="real")
        t_end, dt, horizon = 1.2, 0.001, 0.25
    else:
        pub = ROOT / "data" / "phase3" / ("synthetic_dev" if args.tier == "dev" else f"synthetic/{args.tier}/public")
        sd = SuiteData(pub, kind="synthetic")
        t_end, dt, horizon = 4.0, 0.01, 1.0
    info = sd.sysinfo(args.system)
    scale = E.readout_scale(sd.train_only(args.system))
    sim = _simulator(args.kind, args.system, args.tier)
    rng = np.random.default_rng(args.seed)
    if args.hidden:
        salt = (ROOT / "data" / "phase3" / "hidden" / "salt.txt").read_text(encoding="utf-8").strip()
        counter = iter(range(10**6))
        seed_fn = lambda: int(hashlib.sha256(f"{salt}|cex|{args.system}|{next(counter)}".encode()).hexdigest()[:12], 16) % (2**31) + (10**9 if args.kind == "real" else 0)  # noqa: E731
        if args.kind == "synthetic":
            seed_fn = lambda: int(1000 + rng.integers(0, 8))  # noqa: E731  (held-out parameter draws of the synthetic suites)
    else:
        seed_fn = (lambda: int(rng.integers(0, 10**9))) if args.kind == "real" else (lambda: int(rng.integers(0, 8)))
    t0 = time.time()
    rows = []
    n_rand = args.budget // 2
    for _ in range(n_rand):
        p = _rand_protocol(rng, args.system, info, args.kind, t_end, dt, seed_fn)
        s = score(model, args.system, p, sim, scale, horizon)
        if s is not None:
            rows.append({"phase": "random", "err": s, "protocol": p})
    pop = sorted([r for r in rows], key=lambda r: -r["err"])[:5]
    while len(rows) < args.budget and pop:
        parent = pop[int(rng.integers(0, len(pop)))]
        p = _mutate(rng, parent["protocol"], info, args.kind, t_end, dt)
        s = score(model, args.system, p, sim, scale, horizon)
        if s is None:
            continue
        rows.append({"phase": "search", "err": s, "protocol": p})
        pop = sorted(pop + [rows[-1]], key=lambda r: -r["err"])[:5]
    rand = np.array([r["err"] for r in rows if r["phase"] == "random"])
    worst = sorted(rows, key=lambda r: -r["err"])[:5]
    rec = {"system": args.system, "kind": args.kind, "hidden": args.hidden, "budget": args.budget, "n_scored": len(rows),
           "random_median": float(np.median(rand)) if len(rand) else None, "random_p90": float(np.percentile(rand, 90)) if len(rand) else None,
           "worst": [{"err": r["err"], "phase": r["phase"], "events": [e["kind"] for e in r["protocol"]["events"]],
                      "n_targets": [len(e.get("delta", e.get("targets", []))) for e in r["protocol"]["events"]]} for r in worst],
           "worst_over_random_median": (worst[0]["err"] / float(np.median(rand))) if (worst and len(rand) and np.median(rand) > 0) else None,
           "wall_s": round(time.time() - t0, 1)}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in rec.items() if k != "worst"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
