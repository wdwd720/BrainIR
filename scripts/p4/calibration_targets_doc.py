"""Prose and documentation of the calibration targets (ORCHESTRATOR SIDE; LOG P4-D38): templated rationales whose numbers come from
the data, the version-3 texts (dataset design v2: no explicit initial states), and research/phase4/CALIBRATION_TARGETS.md generated
from a targets JSON.

    uv run --no-sync --project phase4 python scripts/p4/calibration_targets_doc.py prose --targets T.json --base-prose-from V2.json --out P.json
    uv run --no-sync --project phase4 python scripts/p4/calibration_targets_doc.py md --targets T.json --groups-from OLD.md --out DOC.md
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------------------------------------ number formatting
def sig(v: float, n: int = 2) -> str:
    """v with n significant figures, never in exponent notation for 1e-4 <= |v| < 1e5."""
    if v is None or not math.isfinite(float(v)):
        return "n/a"
    v = float(v)
    if v == 0:
        return "0"
    d = n - 1 - math.floor(math.log10(abs(v)))
    r = round(v, d)
    if not (1e-4 <= abs(r) < 1e5):
        return f"{r:.{n - 1}e}"
    return f"{r:.{max(d, 0)}f}"


def rng(lo: float, hi: float, f) -> str:
    a, b = f(lo), f(hi)
    return a if a == b else f"{a}-{b}"


FMT = {
    "x": lambda v: sig(v),
    "n": lambda v: str(int(round(float(v)))),
    "pct": lambda v: sig(100.0 * float(v)),
    "ms": lambda v: sig(1000.0 * float(v)),
    "hz": lambda v: sig(v),
    "g": lambda v: f"{float(v):g}",
    "msg": lambda v: f"{1000.0 * float(v):g}",
}
SUFFIX = {"x": "", "n": "", "g": "", "pct": " %", "ms": " ms", "msg": " ms", "hz": " Hz"}


def fill(template: str, ent: dict) -> str:
    """{F:fmt} / {M:fmt} / {A:fmt} = the full / mechanism / all range; {Amax:fmt} = the all-systems maximum."""
    def rep(m):
        grp, fmt = m.group(1), m.group(2)
        key = {"F": "real_full", "M": "real_mechanism", "A": "real_all", "Amax": "real_all"}[grp]
        s = ent.get(key) or {}
        if s.get("min") is None:
            return "n/a"
        if grp == "Amax":
            return FMT[fmt](s["max"]) + SUFFIX[fmt]
        return rng(s["min"], s["max"], FMT[fmt]) + SUFFIX[fmt]
    return re.sub(r"\{(Amax|F|M|A):(x|n|g|pct|msg|ms|hz)\}", rep, template)


#: rationale templates of the checked statistics (the qualitative text of version 2; every number from the data)
RATIONALE = {
    "n_obs": "The real systems come in two regimes ({M:n} and {F:n} observed units). The suite must contain both.",
    "dt": "Real timescales are 10-60 ms; an output step above ~5 ms under-resolves them.",
    "frac_readout_active": "Part of the readout is silent in the small systems ({M:pct} active); in the large ones {F:pct} of it is active.",
    "rate_active_rel_p50": "Median activity of active units is {A:pct} of the rate scale (sparse, bursty activity).",
    "peak_rate_rel_p50": "Per-unit peaks are {A:x} x the rate scale.",
    "frac_samples_at_floor": "Rectification: the large systems spend {F:pct} of active-unit samples at the floor, the small ones {M:pct}.",
    "kick_clipped_frac_all": "{A:pct} of all kick offsets are clipped at the floor (negative kicks on units at or near rest).",
    "dim_x_traj_pr": "Single trajectories are low-dimensional (participation ratio {A:x}).",
    "dim_x_traj_n95": "{A:n} components hold 95 % of a single trajectory's variance.",
    "dim_x_pooled_obs_n95": ("Pooled over conditions (parameter draws, input schedules, restarts from nominal trajectories) the large systems need "
                             "{F:n} components for 95 % of the variance, the small ones {M:n}."),
    "dim_y_traj_pr": "The readout of a single trajectory is low-dimensional (participation ratio {A:x}).",
    "dim_effect_x_pr": "Intervention effects span more directions in the large systems (participation ratio {F:x}) than in the small ones ({M:x}).",
    "dim_effect_x_n95": "{F:n} components for 95 % of the pooled effect energy in the large systems, {M:n} in the small ones.",
    "effect_energy_outside_passive95": ("Up to {Amax:pct} of the intervention-effect energy lies outside the subspace holding 95 % of the passive "
                                        "variance ({F:pct} in the large systems, {M:pct} in the small ones). The suite must include systems where "
                                        "interventions excite directions that passive activity does not visit, and systems where they do not."),
    "acf_decay_s_median": "Decorrelation within {A:ms} (a quarter period of the oscillation where one is present).",
    "onset_latency_10pct_s": "Responses to the input onset start within {A:ms}.",
    "spec_x_f_peak": ("The real systems oscillate, with dominant frequencies of {A:hz}. At least a quarter of the synthetic systems should have "
                      "their dominant frequency in the target band; types that do not oscillate by construction are exempt."),
    "spec_x_oscillatory_frac": ("{A:pct} of the event-free trajectories of the real systems are oscillatory; at least a quarter of the synthetic "
                                "systems should be."),
    "eff_rel_x_p50": "Median intervention effect relative to the twin's own variability: {F:x} in the large systems, {M:x} in the small ones.",
    "eff_rel_y_p50": "The same for the readout: {F:x} (large), {M:x} (small).",
    "frac_eff_rel_y_below_0.01": ("Near-zero readout effects: {F:pct} of the interventions change the readout by less than 1 % of its variability "
                                  "in the large systems, {M:pct} in the small ones. The suite must contain both regimes."),
    "eff_rms_x_rel_scale_p50": "Effect RMS relative to the rate scale: {F:pct} in the large systems, {M:pct} in the small ones.",
    "resp_frac_1pct_mean": ("Response sparsity: a single-target intervention moves {F:pct} of the other observed units by more than 1 % of the "
                            "scale in the large systems, {M:pct} in the small ones. Both regimes must be present."),
    "resp_frac_1pct_any": ("Fraction of single-target interventions that move at least one other unit by more than 1 % of the scale: {F:x} (large), "
                           "{M:x} (small)."),
    "decay_x_s_median": "Transient effects decay to 1/e within {A:ms} after the event ends.",
    "latency_y_peak_s_median": "Readout effects peak {A:ms} after the intervention onset (delayed consequences; goal5 section 44).",
    "effect_end_over_peak_median": "Part of the effect persists to the end of the window ({A:pct} of its peak).",
    "persistence_ratio_kick": "The network's effect decays {A:x} x as slowly as the kicked unit's own effect.",
    "kick_rel_scale_p50": "Median kick offsets are {A:x} x the system's rate scale.",
    "snr_param_x_median": "Intervention effects relative to the spread across parameter draws: {F:x} (large), {M:x} (small).",
    "snr_param_y_median": "The same for the readout: {F:x} (large), {M:x} (small).",
    "params_param_spread_x_rel_level": "Parameter draws change trajectories substantially (spread {A:x} of the mean level).",
    "params_param_spread_x_rel_dynamics": ("The spread across parameter draws is {A:x} x the dynamic range of the draw-averaged trajectory "
                                           "(draws dephase oscillations)."),
    "input_gain_elasticity_x": "Nonlinear input response: RMS activity grows as the {A:x}th power of the input scale over the design's input levels.",
    "input_gain_elasticity_y": "The readout's input elasticity is {A:x}.",
}


def fill_many(template: str, st: dict) -> str:
    """{statistic|F:fmt} / {statistic|M:fmt} / {statistic|A:fmt} / {statistic|Amax:fmt}: `fill` with a named statistic."""
    return re.sub(r"\{([A-Za-z0-9_.]+)\|(Amax|F|M|A):(x|n|g|pct|msg|ms|hz)\}",
                  lambda m: fill("{" + m.group(2) + ":" + m.group(3) + "}", st.get(m.group(1)) or {}), template)


#: "The real systems in brief" (the qualitative text of version 2, every number from the data; the persistent-state bullet rewritten
#: for dataset design v2)
BRIEF_SYSTEM = [
    ("**Two regimes.** {N_FULL} large recurrent networks ({n_obs|F:n} observed units, {n_y|F:n} readout units, one input) and {N_MECH} small "
     "sub-circuits of them ({n_obs|M:n} observed units, the same readout and input). Output sampling {dt|A:msg}, trajectories {duration_s|A:g} s."),
    ("**Oscillation.** Every system oscillates, with dominant frequencies of {spec_x_f_peak|A:hz} and 95 % of the spectral power below "
     "{spec_x_f95|Amax:hz}; decorrelation within {acf_decay_s_median|A:ms}; responses to the input onset start within {onset_latency_10pct_s|A:ms}."),
    ("**Rectified, sparse activity.** Active units of the large systems sit at the floor for {frac_samples_at_floor|F:pct} of samples, those of "
     "the small ones for {frac_samples_at_floor|M:pct}. Part of the readout is silent in the small systems ({frac_readout_active|M:pct} of "
     "readout units active)."),
    ("**Low-dimensional trajectories.** One trajectory has a participation ratio of {dim_x_traj_pr|A:x} ({dim_x_traj_n95|A:n} components for "
     "95 % of its variance); the readout's participation ratio is {dim_y_traj_pr|A:x}."),
    "**Relaxation.** Transient intervention effects decay to 1/e within {decay_x_s_median|A:ms} after the event ends.",
]
BRIEF_DESIGN = [
    ("**Initial conditions and persistent states.** Restarts at 25-90 % of nominal trajectories leave the large systems in their nominal "
     "regime: their late activity is {init_late_rms_ratio_x_median|F:x} x the nominal (readout {init_late_rms_ratio_y_median|F:x} x), and "
     "{init_high_state_frac_x|F:pct} of the restarts end in a persistent high-activity state ({init_high_state_frac_x|M:pct} in the small "
     "systems). The explicit initial states of version 2 had moved two of the three large systems into such a state in about 70 % of the "
     "records and thereby set their rate scales; the scales now come from nominal activity (s_x {s_x|F:x}, s_y {s_y|F:x} in the large systems)."),
    ("**Condition diversity.** Pooled over parameter draws, input schedules and restarts the large systems need {dim_x_pooled_obs_n95|F:n} "
     "components for 95 % of the variance (small systems {dim_x_pooled_obs_n95|M:n}). Parameter draws change trajectories substantially "
     "(spread {params_param_spread_x_rel_level|A:x} of the mean level; {params_param_spread_x_rel_dynamics|A:x} x the dynamic range of the "
     "draw-averaged trajectory, because draws dephase the oscillation)."),
    ("**Interventions reveal more than passive activity.** Pooled intervention effects need {dim_effect_x_n95|F:n} components for 95 % of "
     "their energy in the large systems, and {effect_energy_outside_passive95|A:pct} of their effect energy lies OUTSIDE the subspace that "
     "holds 95 % of the passive variance ({effect_energy_outside_passive95|F:pct} in the large systems, "
     "{effect_energy_outside_passive95|M:pct} in the small ones)."),
    ("**Effect sizes under this design.** In the large systems most interventions are invisible at the readout: "
     "{frac_eff_rel_y_below_0.01|F:pct} change it by less than 1 % of its own variability, and a single-target intervention moves only "
     "{resp_frac_1pct_mean|F:pct} of the other observed units by more than 1 % of the scale. In the small systems "
     "{resp_frac_1pct_mean|M:pct} of the other units respond. Median effects relative to the counterfactual twin's variability: x "
     "{eff_rel_x_p50|F:x} (large), {eff_rel_x_p50|M:x} (small); readout {eff_rel_y_p50|F:x} (large), {eff_rel_y_p50|M:x} (small). Relative to "
     "the spread across parameter draws, readout effects are {snr_param_y_median|F:x} (large) and {snr_param_y_median|M:x} (small)."),
    ("**Delayed consequences.** Readout effects peak {latency_y_peak_s_median|A:ms} after the intervention onset, and part of the effect "
     "persists to the end of the trajectory ({effect_end_over_peak_median|A:pct} of its peak)."),
    ("**Clipping.** {kick_clipped_frac_all|A:pct} of all kick offsets are clipped at the floor (negative kicks on units at or near rest); such "
     "a kick can have no effect at all. A clipped kick item is labelled by its realized size."),
    ("**Input nonlinearity.** Activity grows as the {input_gain_elasticity_x|A:x}th power of the input scale over the input levels of the "
     "design (readout {input_gain_elasticity_y|A:x})."),
    ("**Noise.** The simulations are deterministic and twins share their item's integration pieces, so the difference before an event is "
     "exactly 0; the only floor is the float32 storage resolution. Observation noise is a benchmark parameter."),
]
_WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}


def brief(t: dict) -> list[str]:
    st, ns = t["statistics"], t.get("n_systems") or {}
    subs = {"{N_FULL}": _WORDS.get(ns.get("full"), str(ns.get("full"))), "{N_MECH}": _WORDS.get(ns.get("mechanism"), str(ns.get("mechanism"))).lower()}

    def one(s):
        for k, v in subs.items():
            s = s.replace(k, v)
        return "- " + fill_many(s, st)
    return (["System properties (stable across intervention designs):\n"] + [one(s) for s in BRIEF_SYSTEM]
            + ["\nProperties revealed by the design, or scaled by it:\n"] + [one(s) for s in BRIEF_DESIGN])


def prose_v3(targets: dict, base: dict) -> dict:
    """The version-3 prose (dataset design v2, LOG P4-D36) from the v2 prose `base` and the new statistics."""
    st = targets["statistics"]
    p = {k: json.loads(json.dumps(base.get(k))) for k in ("check_rule", "coverage_rule", "classes", "dependence_classes", "labels", "caveats")}
    # "initial states" named the explicit states of design v1; the design element is now the initial condition
    p["dependence_classes"] = {k: v.replace("initial states", "initial conditions") for k, v in (p["dependence_classes"] or {}).items()}
    p["source"] = ("PUBLIC real-system trajectories only, built with the benchmark's dataset design v2 (LOG P4-D36): passive sets (nominal input "
                   "over parameter draws, input schedules, restarts from nominal passive trajectories for initial-condition variability, "
                   "structural weight noise), reference interventions (single-target kicks, current pulses and temporary silencing on public "
                   "targets, four magnitude classes, onsets in the first half of the trajectory) each with its counterfactual twin, public "
                   "validation and test items, and pool-source trajectories. No explicit initial states, no hidden data, no hidden targets, no "
                   "evaluation output.")
    d = json.loads(json.dumps(base.get("design") or {}))
    d["initial_states"] = ("no explicit initial states (setting a unit's initial value is a kick at t = 0): initial-condition variability comes "
                           "from 'obs.init' restarts at 25-90 % of a nominal passive trajectory of the same parameter draw; the pools' 'init' "
                           "sources restart from the first (nominal) source of their draw")
    d["twins"] = ("every intervention record has a counterfactual twin with the same parameters, initial condition (rest or restart source) and "
                  "input and no event; twins keep their item's integration pieces (no-op input breakpoints at the event times)")
    if d.get("magnitude_classes") and "realized" not in d["magnitude_classes"]:
        d["magnitude_classes"] += "; a kick clipped at the floor is labelled by its realized size"
    p["design"] = d
    p["note"] = ("Computed from the public real data built with the benchmark's OWN dataset design, version 2 (no explicit initial states; "
                 "initial-condition variability from restarts of nominal trajectories; LOG P4-D36), the design that also builds the synthetic "
                 "tiers, so a synthetic suite built by the same design is directly comparable. Supersedes "
                 "calibration_targets_v2_explicit_init_design.json (design v1: explicit initial states on half the observed units), which in "
                 "turn superseded calibration_targets_v1_earlier_design.json. Statistics marked 'design' or 'mixed' (dependence.class) depend "
                 "on the design; the change columns compare with version 2.")
    hs = st.get("init_high_state_frac_x") or {}
    full, mech = hs.get("real_full") or {}, hs.get("real_mechanism") or {}
    cav = [c.replace("initial states", "initial conditions") if c.startswith("Design dependence:") else c for c in p["caveats"]]
    cav = [c for c in cav if not c.startswith("Strong initial states")]
    if full.get("max") is not None and mech.get("max") is not None:
        cav.insert(2, (f"Initial-condition variability now comes from restarts of nominal trajectories: the share of 'obs.init' records that end in "
                       f"a persistent high-activity state is {rng(full['min'], full['max'], FMT['pct'])} % in the large systems and "
                       f"{rng(mech['min'], mech['max'], FMT['pct'])} % in the small ones (init_high_state_frac_x). In version 2 the explicit "
                       f"initial states moved two of the three large systems into that state in about 70 % of the records, which set their rate "
                       f"scales (s_x, s_y) and every statistic normalised by them."))
    eo = st.get("effect_energy_outside_passive95") or {}
    if (eo.get("real_all") or {}).get("min", 0) > 0:
        cav = [(f"effect_energy_outside_passive95 is above 0 in every system ({fill('{A:pct}', eo)}). In version 2 it was 0 in the four small "
                f"systems with 3 observed units: with the explicit initial states, their passive 95 % subspace spanned every observed "
                f"direction.") if c.startswith("effect_energy_outside_passive95 is 0") else c for c in cav]
    osc, oscf = st.get("spec_x_f_peak") or {}, (st.get("spec_x_oscillatory_frac") or {}).get("real_all") or {}
    who = "every real system oscillates" if oscf.get("min", 0) >= 0.5 else "the real systems oscillate"
    cav = [(f"Oscillation: {who} ({fill('{A:hz}', osc)}). The autocorrelation decay is then about a quarter period, not a "
            f"memory time.") if c.startswith("Oscillation:") else c for c in cav]
    p["caveats"] = cav
    p["rationale"] = {nm: fill(RATIONALE.get(nm, ""), e) for nm, e in st.items() if e.get("check")}
    acf, dec = (st.get("acf_decay_s_median") or {}).get("real_all") or {}, (st.get("decay_x_s_median") or {}).get("real_all") or {}
    if "dt" in p["rationale"] and acf.get("min") is not None and dec.get("max") is not None:
        p["rationale"]["dt"] = (f"Real timescales are {FMT['ms'](acf['min'])}-{FMT['ms'](dec['max'])} ms (autocorrelation decay to effect decay); "
                                f"an output step above ~5 ms under-resolves them.")
    return p


# ------------------------------------------------------------------------------------------------ markdown
def g3(v) -> str:
    if v is None:
        return "n/a"
    v = float(v)
    return f"{v:.3g}" if (v == 0 or 1e-3 <= abs(v) < 1e5) else f"{v:.2e}"


def change_str(c: dict | None, with_max: bool = False) -> str:
    if not c:
        return "-"
    parts = []
    if c.get("ratio_median") is not None:
        parts.append(f"{c['ratio_median']:.2f}" + (f" ({c['ratio_max']:.3g})" if with_max and c.get("ratio_max") is not None else ""))
    if c.get("n_from_zero"):
        parts.append(f"{c['n_from_zero']} from 0")
    if c.get("n_to_zero"):
        parts.append(f"{c['n_to_zero']} to 0")
    return "; ".join(parts) or "-"


def groups_from_md(md: str) -> dict[str, list[str]]:
    """{group heading: [statistic names]} of the 'All statistics, by group' section of an earlier document."""
    out: dict[str, list[str]] = {}
    sec = md.split("## All statistics, by group", 1)[-1].split("\n## ", 1)[0]
    cur = None
    for line in sec.splitlines():
        if line.startswith("### "):
            cur = line[4:].strip()
            out[cur] = []
        elif cur and line.startswith("| `"):
            out[cur].append(line.split("`")[1])
    return out


def to_md(t: dict, groups: dict[str, list[str]]) -> str:
    st = t["statistics"]
    L = []
    ver = t["version"].rsplit("/", 1)[-1]
    L.append("# Calibration targets for the synthetic causal-state suite (goal5 section 8)\n")
    L.append("Generic summary statistics of ten simulated real systems, computed from PUBLIC trajectories built with the benchmark's OWN "
             "dataset design (version 2: no explicit initial states; LOG P4-D36), the same generic protocol design (passive sets, reference "
             "interventions with counterfactual twins, validation and test items, pool sources) that builds the synthetic tiers. A synthetic "
             "suite built by the same design is therefore directly comparable, including on the statistics that depend on the design. The "
             "suite should be distributionally realistic: its systems should span these ranges, not copy any single system.\n")
    L.append(f"Machine-readable targets: `benchmarks/causal_state_v1/public/calibration_targets.json` (version {ver}), built by "
             "`scripts/p4/calibration_targets.py` from the public real data with the documented rules below; this document is generated by "
             "`scripts/p4/calibration_targets_doc.py`. The statistics are computed by `brainir_causal.calibstats` (`load_dataset_dir`, "
             "`compute_all`; `compare` checks a suite against the targets for acceptance criterion 11; `dependence` says whether a statistic is a "
             "system property or depends on the design). Earlier versions: `calibration_targets_v2_explicit_init_design.json` (design with "
             "explicit initial states) and `calibration_targets_v1_earlier_design.json`.\n")
    L.append("## The data design behind these numbers\n")
    for k, v in (t.get("design") or {}).items():
        if isinstance(v, dict):
            v = "; ".join(f"{kk} systems {vv}" for kk, vv in v.items())
        L.append(f"- {k.replace('_', ' ')}: {v}")
    p5, p95 = ((st.get(f"design_current_duration_s_{q}") or {}).get("real_all") for q in ("p5", "p95"))
    if p5 and p95:
        L.append(f"- pulse durations: {FMT['ms'](p5['min'])}-{FMT['ms'](p95['max'])} ms (5th-95th percentile)")
    L.append(f"- record selection: {t.get('record_selection')}\n")
    L.append("## The real systems in brief\n")
    L += brief(t)
    L.append("")
    L.append("## Checked statistics and recommended target ranges\n")
    L.append("`class`: system property / design-dependent / mixed. `min in` = the minimum fraction of synthetic systems that must fall inside the "
             "target range; `coverage [a, b]` = the suite must contain a system with value <= a and one with value >= b. Ranges: " +
             "; ".join(f"`{k}` {v}" for k, v in (t.get("rules") or {}).items()) + ". " + (t.get("coverage_rule") or "") + "\n")
    L.append("| statistic | class | real, large systems | real, small systems | target range | min in | coverage | why |")
    L.append("|---|---|---|---|---|---|---|---|")
    checked = [nm for nm in st if st[nm].get("check")]
    for nm in checked:
        e = st[nm]
        f, m, tr = e["real_full"], e["real_mechanism"], e["target_range"]
        cov = e.get("coverage")
        L.append(f"| `{nm}` | {e['dependence']['class']} | {g3(f['min'])} - {g3(f['max'])} | {g3(m['min'])} - {g3(m['max'])} | "
                 f"{g3(tr[0])} - {g3(tr[1])} | {e['min_inside_frac']} | {('[' + ', '.join(g3(c) for c in cov) + ']') if cov else '-'} | "
                 f"{e.get('rationale', '')} |")
    moved = []
    for nm in checked:
        e = st[nm]
        c, ed = e.get("change_vs_earlier_design") or {}, e.get("earlier_design") or {}
        if ((c.get("ratio_median") or 1.0) >= 1.1 or (c.get("ratio_max") or 1.0) >= 2.0 or c.get("n_from_zero") or c.get("n_to_zero")
                or (ed.get("coverage") or None) != (e.get("coverage") or None)):
            moved.append(((c.get("ratio_median") or 1.0), nm))
    if moved:
        L.append("\n## Largest changes from version 2 (checked statistics)\n")
        L.append("Checked statistics with a median per-system change of at least 1.1, a largest change of at least 2, a value moving from or "
                 "to 0, or a new coverage condition, by median change; version 2 = the design with explicit initial states.\n")
        L.append("| statistic | class | change vs version 2 | target range, version 2 | target range | coverage, version 2 | coverage |")
        L.append("|---|---|---|---|---|---|---|")
        for _, nm in sorted(moved, reverse=True):
            e = st[nm]
            ed, tr = e.get("earlier_design") or {}, e["target_range"]
            t2, c2, c3 = ed.get("target_range"), ed.get("coverage"), e.get("coverage")
            L.append(f"| `{nm}` | {e['dependence']['class']} | {change_str(e.get('change_vs_earlier_design'), True)} | "
                     f"{(g3(t2[0]) + ' - ' + g3(t2[1])) if t2 else '-'} | {g3(tr[0])} - {g3(tr[1])} | "
                     f"{('[' + ', '.join(g3(v) for v in c2) + ']') if c2 else '-'} | {('[' + ', '.join(g3(v) for v in c3) + ']') if c3 else '-'} |")
    L.append("\n## Design dependence: system properties and design-dependent statistics\n")
    for k, v in (t.get("dependence_classes") or {}).items():
        L.append(f"- **{k}**: {v}")
    L.append("\nThe `change` columns compare every statistic with version 2 of the targets (the same systems under the design with explicit "
             "initial states): exp(median over systems of |log(current / earlier)|), with the largest per-system change in brackets; "
             "'N from 0' / 'N to 0' count systems where the earlier / current value is 0.\n")
    for cls in ("system", "mixed", "design"):
        L.append(f"### Checked statistics: {cls}\n")
        L.append("| statistic | change vs version 2 | why |")
        L.append("|---|---|---|")
        for nm in checked:
            e = st[nm]
            if e["dependence"]["class"] == cls:
                L.append(f"| `{nm}` | {change_str(e.get('change_vs_earlier_design'), True)} | {e['dependence']['reason']} |")
        L.append("")
    L.append("## Definitions of the checked statistics\n")
    for nm in checked:
        L.append(f"- `{nm}`: {st[nm]['definition']}")
    L.append("\n## All statistics, by group\n")
    L.append("Real range over all ten systems, then large / small systems, the class and the change vs version 2. Units: x and y in the "
             "simulator's rate units, times in seconds, frequencies in Hz.\n")
    seen = set()
    for g, names in list(groups.items()) + [("Other", sorted(set(st) - {n for v in groups.values() for n in v}))]:
        names = [n for n in names if n in st and n not in seen]
        if not names:
            continue
        L.append(f"### {g.replace('Initial states', 'Initial conditions')}\n")
        L.append("| statistic | all (min - max; median) | large | small | class | change |")
        L.append("|---|---|---|---|---|---|")
        for nm in names:
            e = st[nm]
            a, f, m = e["real_all"], e.get("real_full") or {}, e.get("real_mechanism") or {}
            L.append(f"| `{nm}` | {g3(a['min'])} - {g3(a['max'])}; {g3(a['median'])} | {g3(f.get('min'))} - {g3(f.get('max'))} | "
                     f"{g3(m.get('min'))} - {g3(m.get('max'))} | {e['dependence']['class']} | {change_str(e.get('change_vs_earlier_design'))} |")
            seen.add(nm)
        L.append("")
    L.append("## Caveats\n")
    for c in t.get("caveats") or []:
        L.append(f"- {c}")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prose")
    p.add_argument("--targets", type=Path, required=True)
    p.add_argument("--base-prose-from", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    m = sub.add_parser("md")
    m.add_argument("--targets", type=Path, required=True)
    m.add_argument("--groups-from", type=Path, required=True)
    m.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    t = json.loads(args.targets.read_text(encoding="utf-8"))
    if args.cmd == "prose":
        import importlib.util
        spec = importlib.util.spec_from_file_location("ct", Path(__file__).with_name("calibration_targets.py"))
        ct = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ct)
        base = ct.prose_of(json.loads(args.base_prose_from.read_text(encoding="utf-8")))
        args.out.write_text(json.dumps(prose_v3(t, base), indent=1) + "\n", encoding="utf-8", newline="\n")
        return 0
    groups = groups_from_md(args.groups_from.read_text(encoding="utf-8"))
    args.out.write_text(to_md(t, groups), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
