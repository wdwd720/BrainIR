"""Experiment cost accounting (research/phase4/INTERFACES.md section 7; goal5 section 28). Shared by the simulation service and the
experiment loop, so budgets are counted identically everywhere.

    experiment_cost(protocol, system_record) -> {
        "experiment": 1 if the protocol carries an intervention event else 0,
        "trajectories": 1,
        "simulated_s": t_end,
        "units": the system's budget units per trajectory (system_record["cost_units"], default 1),
        "targets": sorted units any event acts on,
        "magnitude": {kind: ...}  per event kind, in the kind's own units:
            kick         sum |delta|                            (a kick's magnitude does NOT scale with dt; early numerics review)
            current      sum over targets |I| x duration       (persistent: until t_end)
            current_seq  sum over targets and segments |I_j| x seg
            silence      number of targets x duration          (unit-seconds)
            edge_scale   number of edges x |1 - factor| x duration
            param        sum over targets (|gain - 1| + |tau - 1| + |threshold|) x duration
        "magnitude_total": the sum over kinds (MIXED units: descriptive only; no rule uses it; kinds are reported separately)}

`Ledger` accumulates costs per agent / designer: experiments, trajectories, simulator calls (computed, not cached), simulated seconds,
unique targets (system, unit), magnitude per kind, budget units.
"""

from __future__ import annotations

from . import protocol as P

MAG_KINDS = ("kick", "current", "current_seq", "silence", "edge_scale", "param")


def experiment_cost(proto: dict, sysrec: dict | None = None, *, allow_truth: bool = False) -> dict:
    q = P.validate(proto, allow_truth=allow_truth)
    t_end, dt = q["t_end"], q["dt"]
    mag = {k: 0.0 for k in MAG_KINDS}
    for e in q["events"]:
        k = e["kind"]
        if k == "kick":
            mag[k] += sum(abs(float(v)) for v in e["delta"].values())
        elif k == "current_seq":
            mag[k] += sum(abs(float(v)) for lst in e["targets"].values() for v in lst) * float(e["seg"])
        elif k in ("current", "silence", "edge_scale", "param"):
            dur = (t_end if e["t1"] is None else e["t1"]) - e["t0"]
            if k == "current":
                mag[k] += sum(abs(float(v)) for v in e["targets"].values()) * dur
            elif k == "silence":
                mag[k] += len(e["targets"]) * dur
            elif k == "edge_scale":
                mag[k] += len(e["edges"]) * abs(1.0 - float(e["factor"])) * dur
            else:
                mag[k] += sum(abs(float(v.get("gain", 1.0)) - 1.0) + abs(float(v.get("tau", 1.0)) - 1.0) + abs(float(v.get("threshold", 0.0)))
                              for v in e["targets"].values()) * dur
    return {"experiment": 1 if q["events"] else 0, "trajectories": 1, "simulated_s": float(t_end),
            "units": int((sysrec or {}).get("cost_units", 1)), "targets": sorted(P.intervened_units(q, allow_truth=allow_truth)),
            "magnitude": mag, "magnitude_total": float(sum(mag.values()))}


class Ledger:
    """Cumulative costs of one agent / designer (JSON-serialisable via `to_dict` / `from_dict`)."""

    def __init__(self):
        self.experiments = 0
        self.trajectories = 0
        self.sim_calls = 0
        self.cached = 0
        self.simulated_s = 0.0
        self.units = 0
        self.targets: set[tuple[str, int]] = set()
        self.magnitude = {k: 0.0 for k in MAG_KINDS}

    def add(self, system_id: str, cost: dict, computed: bool) -> None:
        self.experiments += int(cost["experiment"])
        self.trajectories += int(cost["trajectories"])
        self.simulated_s += float(cost["simulated_s"])
        self.units += int(cost["units"])
        self.sim_calls += int(bool(computed))
        self.cached += int(not computed)
        self.targets |= {(system_id, int(u)) for u in cost["targets"]}
        for k, v in cost["magnitude"].items():
            self.magnitude[k] = self.magnitude.get(k, 0.0) + float(v)

    def to_dict(self) -> dict:
        return {"experiments": self.experiments, "trajectories": self.trajectories, "sim_calls": self.sim_calls, "cached": self.cached,
                "simulated_s": self.simulated_s, "units": self.units, "unique_targets": len(self.targets),
                "targets": sorted([list(t) for t in self.targets]), "magnitude": dict(self.magnitude),
                "magnitude_total": float(sum(self.magnitude.values()))}

    @classmethod
    def from_dict(cls, d: dict) -> Ledger:
        led = cls()
        led.experiments, led.trajectories = int(d.get("experiments", 0)), int(d.get("trajectories", 0))
        led.sim_calls, led.cached = int(d.get("sim_calls", 0)), int(d.get("cached", 0))
        led.simulated_s, led.units = float(d.get("simulated_s", 0.0)), int(d.get("units", 0))
        led.targets = {(str(a), int(b)) for a, b in d.get("targets", [])}
        led.magnitude = {k: float(d.get("magnitude", {}).get(k, 0.0)) for k in MAG_KINDS}
        return led
