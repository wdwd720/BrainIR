"""The frozen intervention-family vocabulary (research/phase4/INTERFACES.md section 2) and `family_of(protocol, system_record)`.

Every protocol maps to exactly ONE label. The thresholds come from the system's capability record (INTERFACES section 3):

    capability["kick"]["max"]                      development kick maximum |delta|         (kick.1 vs kick.hi)
    capability["current"]["max"]                   development current maximum |I|          (pulse.1 vs pulse.hi)
    capability["current"]["pulse_max_duration"]    D_p: a finite current lasting <= D_p is a PULSE
    capability["current"]["sustained_min_duration"]  D_s >= D_p: a current lasting >= D_s, or persistent, is SUSTAINED; a finite
                                                   current lasting strictly between D_p and D_s is unclassified ('other')
    capability["stimulus"]["nominal_level"]        the nominal stimulus value (per channel)
    capability["stimulus"]["max_onset"]            latest onset of a nominal stimulus
    capability["params"]["nominal_seed"]           the nominal parameter draw, or null (then parameter draws are not a family)

Rules (applied in this order):

1. No events -> observational family, first match of: `obs.wnoise` (weight noise), `obs.init` (r0 not rest), `obs.stim` (stimulus
   schedule not nominal), `obs.param` (params_seed != the nominal draw, only when the record names one), `obs.nominal`. A nominal
   schedule is [[0, level]] or [[0, 0], [t_on, level]] with t_on <= max_onset (every channel at the nominal level), after
   removing no-op steps (a value equal to the one in force: the breakpoints a counterfactual twin keeps).
2. Events of the same kind with IDENTICAL timing (kicks at the same t; windows with the same t0 and t1; edge scalings also need the
   same factor) are merged into one event whose targets are the union (two simultaneous single kicks = one paired kick).
3. Each (merged) event gets an event family:
   - kick: 1 target -> `kick.1` (|delta| <= kick max) or `kick.hi` (above); 2 -> `kick.2`; >= 3 -> `kick.g`
   - current, pulse (finite, duration <= D_p): 1 target -> `pulse.1` / `pulse.hi` (|I| above the current max); 2 -> `pulse.2`;
     >= 3 -> `pulse.g`
   - current, sustained (duration >= D_s, or persistent): 1 target, I > 0 -> `act.1`, I < 0 -> `inh.1`; otherwise `other`
   - current lasting strictly between D_p and D_s: `other`
   - current_seq: see rule 5
   - silence: 1 target -> `sil.1` (temporary) / `sil.1p` (persistent); 2 -> `sil.2`; >= 3 -> `sil.g`
   - edge_scale: factor 0 -> `edge.rm`; 0 < factor < 1 -> `edge.w`; factor >= 1 (strengthening / no-op) -> `other`
   - param: 1 target -> `param.1`; more -> `other`
   - latent_set / latent_kick -> `latent` (synthetic truth events; never a development family)
4. One event -> its event family. Several events:
   - all of them current PULSES: 2 -> `seq.pp`; >= 3 with identical targets, amplitudes and durations -> `seq.train` if the onsets are
     equally spaced, else `seq.prbs`; >= 3 otherwise -> `comp.seq` (no overlap) / `comp.sim` (overlap)
   - all with the same event family and pairwise non-overlapping windows -> that family (repeated independent events)
   - otherwise: any two windows overlap -> `comp.sim`; none overlap -> `comp.seq`
   Windows: kicks occupy [t, t + dt); finite events [t0, t1); persistent events [t0, t_end); sequences [t0, t0 + m seg).
5. A current_seq event: the distinct values across all its targets' segments are its LEVELS.
   - >= 3 levels -> `seq.chirp` (a multi-level, frequency-swept pattern)
   - the single level 0 -> `other` (a flat sequence at 0 does nothing)
   - one non-zero level -> the equivalent single `current` event over the whole sequence (rule 3)
   - two levels: the ON segments are those at the non-zero level (when 0 is a level) or at the higher level (two non-zero
     levels); the pulses are the maximal ON runs. 1 run: with a zero baseline -> the equivalent single `current` event over that run
     (rule 3); with a non-zero baseline -> `other`. 2 runs -> `seq.pp`; >= 3 runs -> `seq.train` if all runs have equal length and
     all gaps equal length, else `seq.prbs`
6. `other` anywhere -> `other` (not a vocabulary family: the development policy refuses it).

Split records (PROTOCOL.md section 3): `HIDDEN_ONLY`, `REAL_TRAIN`, `ROTATIONS`, `supported_families(capability)`,
`split_record(train, supported)`, `rotation_split(rotation, capability)`, `shift_kind(family, families_train)` (near / far).

The magnitude of a multi-target event does not change its label (the policy checks magnitudes separately). Neither do
`params_spread`, `process_noise` and `obs_noise`: they are test / robustness conditions, checked by the development policy.
"""

from __future__ import annotations

from . import protocol as P

OBS = ("obs.nominal", "obs.stim", "obs.init", "obs.param", "obs.wnoise")
SINGLE = ("kick.1", "kick.2", "kick.g", "kick.hi", "pulse.1", "pulse.2", "pulse.g", "pulse.hi", "act.1", "inh.1",
          "sil.1", "sil.2", "sil.g", "sil.1p", "edge.w", "edge.rm", "param.1")
SEQ = ("seq.train", "seq.prbs", "seq.chirp", "seq.pp")
COMP = ("comp.seq", "comp.sim")
VOCABULARY = OBS + SINGLE + SEQ + COMP
INTERVENTION_FAMILIES = SINGLE + SEQ + COMP
SPECIAL = ("other", "latent")
PULSES = ("pulse.1", "pulse.2", "pulse.g", "pulse.hi")

#: event kind -> the families it can produce (a system supports a family when it supports its kind)
KIND_FAMILIES = {
    "kick": ("kick.1", "kick.2", "kick.g", "kick.hi"),
    "current": ("pulse.1", "pulse.2", "pulse.g", "pulse.hi", "act.1", "inh.1", "seq.train", "seq.prbs", "seq.pp"),
    "current_seq": ("seq.train", "seq.prbs", "seq.chirp", "seq.pp"),
    "silence": ("sil.1", "sil.2", "sil.g", "sil.1p"),
    "edge_scale": ("edge.w", "edge.rm"),
    "param": ("param.1",),
}
#: never simulatable in development on any system (PROTOCOL.md section 3)
HIDDEN_ONLY = ("comp.seq", "comp.sim", "seq.chirp")
#: real systems: the trained families (on the public targets; PROTOCOL.md section 3)
REAL_TRAIN = ("obs.nominal", "obs.stim", "obs.init", "obs.param", "obs.wnoise", "kick.1", "pulse.1", "sil.1")
#: synthetic rotations: families_train besides every obs.* family (PROTOCOL.md section 3)
ROTATIONS = {
    "R1": ("sil.1", "pulse.1"),
    "R2": ("kick.1", "act.1", "edge.w"),
    "R3": ("pulse.1", "param.1", "seq.train"),
    "R4": ("kick.1", "pulse.1", "sil.1", "sil.2"),
}
#: the event kind GROUP of each single-event / pattern family, for near vs far shifts (current sequences are currents)
FAMILY_KIND = {**{f: "kick" for f in KIND_FAMILIES["kick"]}, **{f: "current" for f in KIND_FAMILIES["current"] + KIND_FAMILIES["current_seq"]},
               **{f: "silence" for f in KIND_FAMILIES["silence"]}, **{f: "edge_scale" for f in KIND_FAMILIES["edge_scale"]},
               **{f: "param" for f in KIND_FAMILIES["param"]}}

_EPS = 1e-9


def supported_families(capability: dict) -> list[str]:
    """Every vocabulary family a system with this capability record can produce (obs.* always; comp.* when at least one event
    kind is supported)."""
    kinds = [k for k, fams in KIND_FAMILIES.items() if (capability.get(k) or {}).get("supported")]
    out = set(OBS)
    for k in kinds:
        out |= set(KIND_FAMILIES[k])
    if kinds:
        out |= set(COMP)
    return [f for f in VOCABULARY if f in out]


def split_record(train: list | tuple, supported: list | tuple, rotation: str | None = None) -> dict:
    """{families_train, families_heldout, hidden_only, rotation}: held out = supported - train - hidden-only."""
    sup = set(supported)
    bad = [f for f in train if f not in sup or f in HIDDEN_ONLY]
    if bad:
        raise ValueError(f"families not trainable on this system: {bad}")
    tr = [f for f in VOCABULARY if f in set(train)]
    return {"families_train": tr, "families_heldout": [f for f in VOCABULARY if f in sup and f not in set(tr) and f not in HIDDEN_ONLY],
            "hidden_only": [f for f in HIDDEN_ONLY if f in sup], "rotation": rotation}


def rotation_split(rotation: str, capability: dict) -> dict:
    """The split record of a synthetic system with this rotation (PROTOCOL.md section 3)."""
    return split_record(list(OBS) + list(ROTATIONS[rotation]), supported_families(capability), rotation=rotation)


def shift_kind(family: str, families_train: list | tuple) -> str:
    """'near' (same event kind as a trained family), 'far' (a kind never trained on the system) or 'in' (trained)."""
    if family in families_train:
        return "in"
    kind = FAMILY_KIND.get(family)
    trained_kinds = {FAMILY_KIND.get(f) for f in families_train}
    return "near" if kind is not None and kind in trained_kinds else "far"


def _cap(sysrec: dict | None, kind: str, key: str, default=None):
    return ((sysrec or {}).get("capability") or {}).get(kind, {}).get(key, default)


def is_nominal_stimulus(stimulus: list, sysrec: dict | None) -> bool:
    level = float(_cap(sysrec, "stimulus", "nominal_level", 1.0))
    max_onset = float(_cap(sysrec, "stimulus", "max_onset", 0.15))

    def at(v, x):
        vals = v if isinstance(v, list) else [v]
        return all(abs(float(a) - x) <= _EPS for a in vals)

    # no-op steps (a value equal to the one in force, e.g. a counterfactual twin's breakpoints) do not change the schedule
    collapsed = []
    for t, v in stimulus:
        if not collapsed or v != collapsed[-1][1]:
            collapsed.append([t, v])
    stimulus = collapsed
    if len(stimulus) == 1:
        return at(stimulus[0][1], level)
    if len(stimulus) == 2:
        (t0, v0), (t1, v1) = stimulus
        return t0 == 0.0 and at(v0, 0.0) and at(v1, level) and t1 <= max_onset + _EPS
    return False


def _obs_family(q: dict, sysrec: dict | None) -> str:
    if q["weight_noise"] is not None and float(q["weight_noise"]["sd"]) > 0:
        return "obs.wnoise"
    if q["r0"]["kind"] != "rest":
        return "obs.init"
    if not is_nominal_stimulus(q["stimulus"], sysrec):
        return "obs.stim"
    nominal_seed = _cap(sysrec, "params", "nominal_seed", None)
    if nominal_seed is not None and int(q["params_seed"]) != int(nominal_seed):
        return "obs.param"
    return "obs.nominal"


def _window(e: dict, t_end: float, dt: float) -> tuple[float, float]:
    return P.event_start(e), P.event_end(e, t_end, dt)


def merge_simultaneous(events: list[dict]) -> list[dict]:
    """Rule 2: merge events of the same kind with identical timing into one group event (the union of the targets)."""
    out: list[dict] = []
    index: dict[tuple, int] = {}
    for e in events:
        k = e["kind"]
        if k == "kick":
            sig = (k, e["t"])
        elif k in ("current", "silence", "param"):
            sig = (k, e["t0"], e["t1"])
        elif k == "edge_scale":
            sig = (k, e["t0"], e["t1"], e["factor"])
        else:
            sig = None
        if sig is None or sig not in index:
            if sig is not None:
                index[sig] = len(out)
            out.append({kk: (dict(v) if isinstance(v, dict) else (list(v) if isinstance(v, list) else v)) for kk, v in e.items()})
            continue
        g = out[index[sig]]
        if k == "kick":
            for u, d in e["delta"].items():
                g["delta"][u] = g["delta"].get(u, 0.0) + d
        elif k in ("current", "param"):
            for u, v in e["targets"].items():
                if k == "current":
                    g["targets"][u] = g["targets"].get(u, 0.0) + v
                else:
                    g["targets"][u] = {**g["targets"].get(u, {}), **v}
        elif k == "silence":
            g["targets"] = sorted(set(g["targets"]) | set(e["targets"]))
        elif k == "edge_scale":
            g["edges"] = [list(x) for x in sorted({tuple(x) for x in g["edges"]} | {tuple(x) for x in e["edges"]})]
    return out


def _current_family(targets: dict, t0: float, t1: float | None, t_end: float, sysrec: dict | None) -> str:
    n = len(targets)
    dur = (t_end if t1 is None else t1) - t0
    d_pulse = float(_cap(sysrec, "current", "pulse_max_duration", 0.15))
    d_sust = float(_cap(sysrec, "current", "sustained_min_duration", d_pulse))
    cmax = float(_cap(sysrec, "current", "max", float("inf")))
    if t1 is not None and dur <= d_pulse + _EPS:
        if n == 1:
            return "pulse.hi" if abs(float(next(iter(targets.values())))) > cmax + _EPS else "pulse.1"
        return "pulse.2" if n == 2 else "pulse.g"
    if t1 is not None and dur < d_sust - _EPS:
        return "other"                  # between the pulse maximum and the sustained minimum: unclassified
    if n == 1:
        v = float(next(iter(targets.values())))
        return "act.1" if v > 0 else ("inh.1" if v < 0 else "other")
    return "other"


def _runs(on: list[bool]) -> tuple[list[int], list[int], list[int]]:
    """(starts, lengths, gaps between consecutive runs) of the True runs."""
    starts, lengths = [], []
    i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]:
                j += 1
            starts.append(i)
            lengths.append(j - i)
            i = j
        else:
            i += 1
    gaps = [starts[k + 1] - (starts[k] + lengths[k]) for k in range(len(starts) - 1)]
    return starts, lengths, gaps


def _seq_family(e: dict, t_end: float, dt: float, sysrec: dict | None) -> str:
    vals = e["targets"]
    m = len(next(iter(vals.values())))
    levels = sorted({round(float(v), 12) for lst in vals.values() for v in lst})
    if len(levels) >= 3:
        return "seq.chirp"
    zero_base = 0.0 in levels
    if levels == [0.0]:
        return "other"                                   # a flat sequence at 0 does nothing
    high = next(v for v in levels if v != 0.0) if zero_base else levels[-1]
    on = [any(abs(round(float(lst[j]), 12) - high) <= 1e-12 for lst in vals.values()) for j in range(m)]
    starts, lengths, gaps = _runs(on)
    if len(starts) == 1:
        b = P.seq_boundaries(e, dt)
        if not zero_base:
            if len(levels) == 1:                         # one constant non-zero level: a single current over the whole sequence
                return _current_family({u: float(lst[0]) for u, lst in vals.items()}, b[0], b[-1], t_end, sysrec)
            return "other"                               # a single switch between two non-zero levels is not a vocabulary pattern
        a0, a1 = b[starts[0]], b[starts[0] + lengths[0]]
        tg = {u: float(lst[starts[0]]) for u, lst in vals.items() if float(lst[starts[0]]) != 0.0}
        return _current_family(tg, a0, a1, t_end, sysrec)
    if len(starts) == 2:
        return "seq.pp"
    if len(set(lengths)) == 1 and len(set(gaps)) == 1:
        return "seq.train"
    return "seq.prbs"


def event_family(e: dict, t_end: float, dt: float, sysrec: dict | None) -> str:
    k = e["kind"]
    if k in P.TRUTH_KINDS:
        return "latent"
    if k == "kick":
        n = len(e["delta"])
        if n == 1:
            kmax = float(_cap(sysrec, "kick", "max", float("inf")))
            return "kick.hi" if abs(float(next(iter(e["delta"].values())))) > kmax + _EPS else "kick.1"
        return "kick.2" if n == 2 else "kick.g"
    if k == "current":
        return _current_family(e["targets"], e["t0"], e["t1"], t_end, sysrec)
    if k == "current_seq":
        return _seq_family(e, t_end, dt, sysrec)
    if k == "silence":
        n = len(e["targets"])
        if n == 1:
            return "sil.1p" if e["t1"] is None else "sil.1"
        return "sil.2" if n == 2 else "sil.g"
    if k == "edge_scale":
        f = float(e["factor"])
        return "edge.rm" if f == 0.0 else ("edge.w" if f < 1.0 else "other")
    if k == "param":
        return "param.1" if len(e["targets"]) == 1 else "other"
    return "other"


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[0] < b[1] - _EPS and b[0] < a[1] - _EPS


def _pulse_signature(e: dict) -> tuple:
    return (tuple(sorted(e["targets"].items())), round(float(e["t1"]) - float(e["t0"]), 9))


def family_of(protocol: dict, sysrec: dict | None = None, *, allow_truth: bool = False) -> str:
    """The family label of a protocol (see the module docstring)."""
    q = P.validate(protocol, allow_truth=allow_truth)
    if not q["events"]:
        return _obs_family(q, sysrec)
    t_end, dt = q["t_end"], q["dt"]
    evs = merge_simultaneous(q["events"])
    fams = [event_family(e, t_end, dt, sysrec) for e in evs]
    if "latent" in fams:
        return "latent"
    if "other" in fams:
        return "other"
    if len(evs) == 1:
        return fams[0]
    wins = [_window(e, t_end, dt) for e in evs]
    any_overlap = any(_overlap(wins[i], wins[j]) for i in range(len(wins)) for j in range(i + 1, len(wins)))
    if all(f in PULSES for f in fams) and all(e["kind"] == "current" for e in evs):
        if len(evs) == 2:
            return "seq.pp" if not any_overlap else "comp.sim"
        if not any_overlap and len({_pulse_signature(e) for e in evs}) == 1:
            onsets = sorted(float(e["t0"]) for e in evs)
            spacing = {round(b - a, 9) for a, b in zip(onsets, onsets[1:])}
            return "seq.train" if len(spacing) == 1 else "seq.prbs"
        return "comp.sim" if any_overlap else "comp.seq"
    if len(set(fams)) == 1 and not any_overlap:
        return fams[0]
    return "comp.sim" if any_overlap else "comp.seq"


def family_detail(protocol: dict, sysrec: dict | None = None, *, allow_truth: bool = False) -> dict:
    """The family plus per-event families after merging and the number of (merged) events."""
    q = P.validate(protocol, allow_truth=allow_truth)
    evs = merge_simultaneous(q["events"])
    return {"family": family_of(q, sysrec, allow_truth=allow_truth), "n_events": len(evs),
            "event_families": [event_family(e, q["t_end"], q["dt"], sysrec) for e in evs]}
