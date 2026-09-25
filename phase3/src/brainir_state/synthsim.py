"""Orchestrator-side access to the synthetic generator (NEVER in a clean room: the generator holds the ground truth).

The generator package `p3synth` (written by the oracle-free benchmark author in C:\\Dev\\BrainIR_p3bench) is copied, hash-locked,
to benchmarks/state_discovery_v1/generator/. Suites are identified by (tier, suite seed); the dev suite's seed is public, the
held-out and final seeds derive from the secret salt of the benchmark (scripts/p3/build_synthetic_suites.py).
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GEN_DIR = ROOT / "benchmarks" / "state_discovery_v1" / "generator"

# public development policy for synthetic systems (mirrors the generator's hold-out design; see PROTOCOL.md section 3)
SYNTH_TRAIN_PARAMS = range(0, 8)
SYNTH_TRAIN_WEIGHT_NOISE_SD = 0.05
SYNTH_TRAIN_WEIGHT_NOISE_SEEDS = 10_000
SYNTH_ALLOWED_DT = (0.005, 0.01, 0.02)
SYNTH_MAX_T_END = 8.0
SYNTH_MAX_STIM = 3.0


def p3synth():
    if str(GEN_DIR) not in sys.path:
        sys.path.insert(0, str(GEN_DIR))
    import p3synth as mod  # noqa: PLC0415
    return mod


@lru_cache(maxsize=8)
def suite_systems(tier: str, seed: int) -> dict:
    """{system_id: SyntheticSystem} of one suite (the same construction as build_suite)."""
    mod = p3synth()
    from p3synth.systems import build_all  # noqa: PLC0415
    _ = mod
    return {s.system_id: s for s in build_all(int(seed), tier)}


def simulate(tier: str, seed: int, system_id: str, protocol: dict, full: bool = False) -> dict:
    s = suite_systems(tier, int(seed))[system_id]
    return s.simulate(protocol, full=full)


def check_public_synth(q: dict, sysdef: dict) -> str | None:
    """None if a (p3synth-validated) protocol is allowed for development on this synthetic system, else the reason. What is refused
    is exactly what the suites' test split holds out: held-out parameter draws and structural-noise levels, group interventions,
    edge removal, events on held-out targets, arbitrary initial microstates, latent events."""
    if int(q["params_seed"]) not in SYNTH_TRAIN_PARAMS:
        return "params_seed must be one of the development draws 0-7"
    wn = q.get("weight_noise")
    if wn is not None and (float(wn["sd"]) > SYNTH_TRAIN_WEIGHT_NOISE_SD + 1e-12 or not (0 <= int(wn["seed"]) < SYNTH_TRAIN_WEIGHT_NOISE_SEEDS)):
        return f"weight_noise must have sd <= {SYNTH_TRAIN_WEIGHT_NOISE_SD} and a seed < {SYNTH_TRAIN_WEIGHT_NOISE_SEEDS}"
    if q["t_end"] > SYNTH_MAX_T_END or not any(abs(q["dt"] - d) < 1e-12 for d in SYNTH_ALLOWED_DT):
        return f"t_end <= {SYNTH_MAX_T_END} s and dt in {SYNTH_ALLOWED_DT} only"
    for _, v in q["stimulus"]:
        vals = v if isinstance(v, list) else [v]
        if any(abs(float(x)) > SYNTH_MAX_STIM for x in vals):
            return f"stimulus values must satisfy |u| <= {SYNTH_MAX_STIM}"
    if q["r0"]["kind"] != "zero":
        return "initial microstates other than the rest state are not development protocols (use inputs and kicks)"
    targets = {int(n) for n in sysdef["targets_public"]}
    kick_scale = float(sysdef.get("kick_max", 5.0))
    cur_scale = float(sysdef.get("current_max", 5.0))
    windows = {"current": [], "silence": []}
    kick_times = []
    for e in q["events"]:
        k = e["kind"]
        if k in ("edge_remove", "latent_set", "latent_impulse"):
            return f"{k} is not a development intervention"
        if k == "kick":
            if len(e["delta"]) != 1 or not {int(n) for n in e["delta"]} <= targets or any(abs(v) > kick_scale for v in e["delta"].values()):
                return f"kicks: one public target per event, |delta| <= {kick_scale:.3g}"
            kick_times.append(e["t"])
        elif k == "current":
            if len(e["targets"]) != 1 or not {int(n) for n in e["targets"]} <= targets or any(abs(v) > cur_scale for v in e["targets"].values()):
                return f"currents: one public target per event, |I| <= {cur_scale:.3g}"
            windows["current"].append((e["t0"], e["t1"]))
        elif k == "silence":
            if len(e["targets"]) != 1 or int(e["targets"][0]) not in targets:
                return "silencing: one public target per event"
            windows["silence"].append((e["t0"], q["t_end"] if e["t1"] is None else e["t1"]))
    if len(kick_times) != len(set(round(t, 9) for t in kick_times)):
        return "simultaneous kicks (group kicks) are held out"
    for kind, w in windows.items():
        w.sort()
        for (a0, a1), (b0, _) in zip(w, w[1:]):
            if b0 < a1:
                return f"overlapping {kind} windows (group interventions) are held out"
    return None
