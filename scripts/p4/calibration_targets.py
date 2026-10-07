"""The calibration targets of the synthetic suite (goal5 section 8; PROTOCOL section 6), computed from PUBLIC real data (ORCHESTRATOR
SIDE; LOG P4-D25 / P4-D38). Reproducible replacement of the ad-hoc builder of version 2.

    uv run --no-sync --project phase4 python scripts/p4/calibration_targets.py build --root data/phase4/real/real_public/public
        --earlier benchmarks/causal_state_v1/public/calibration_targets_v2_explicit_init_design.json
        --version causal_state_v1/calibration_targets/3 --out FILE [--prose P.json | --prose-from T.json]
    uv run --no-sync --project phase4 python scripts/p4/calibration_targets.py apply-prose --targets T.json --prose P.json --out FILE
    uv run --no-sync --project phase4 python scripts/p4/calibration_targets.py compare A.json B.json [--tol 1e-12]   # field-by-field diff

RULES (exactly those documented in the targets file and research/phase4/CALIBRATION_TARGETS.md):
- per-system values: `calibstats.compute_all` on EVERY public record of the system (`calibstats.load_dataset_dir` without a cap; the
  per-trajectory statistics cap at 40 records per record kind inside compute_all); every numeric scalar output is a statistic;
- anonymous labels "real system N" in the fixed assignment of the earlier file (`LABELS`: 1-3 the full networks, 4-10 the mechanisms);
- summaries real_all / real_full / real_mechanism = {min, max, median, n} over the systems with a finite value (`calibstats.pool`);
- definition / dependence: `calibstats.describe` / `calibstats.dependence`;
- change_vs_earlier_design: exp(median / max over systems of |log(current / earlier)|) over the systems where both values are
  positive; n_from_zero / n_to_zero = systems where the earlier / current value is 0 (and the other is not);
- CHECKED statistics (the fixed set `CHECKED`, its range rule, min_inside_frac and whether it has a coverage condition):
  pos [min / 2, 2 max]; frac [max(0, min - 0.1), min(1, max + 0.1)]; dim [max(1, floor(min / 1.5)), ceil(1.5 max)];
  size [min, 1.25 max]; dt [min / 2, 5 max]; COVERAGE (only where flagged): with 'low' the class with the smaller median, a = the low
  class's maximum rounded UP to one significant figure and b = the high class's minimum rounded DOWN to one significant figure; if
  a >= b, a and b are the two class MEDIANS rounded the same way, with a at least 0.01; earlier_design = the earlier file's
  real_all / target_range / coverage of the statistic.
Prose (rationales, caveats, design text) is an input of the build (`--prose`, JSON), never computed; `apply-prose` replaces the
prose fields of a built file without recomputing anything; `compare` reports every difference of the computed fields.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import calibstats as CS  # noqa: E402

#: the fixed label assignment ("the same system-to-label assignment as in the earlier file"; recovered from version 2 by matching
#: all 311 per-system values of each label exactly to one system's recomputed values)
LABELS = {"real system 1": "real:B:full", "real system 2": "real:A:full", "real system 3": "real:C:full", "real system 4": "real:B:m2",
          "real system 5": "real:A:m1", "real system 6": "real:C:m2", "real system 7": "real:C:m1", "real system 8": "real:B:m1",
          "real system 9": "real:A:m2", "real system 10": "real:C:m3"}
RULES = {
    "pos": "[min / 2, 2 x max] (a factor-2 margin on both sides of the real range)",
    "frac": "[max(0, min - 0.1), min(1, max + 0.1)]",
    "dim": "[max(1, floor(min / 1.5)), ceil(1.5 x max)]",
    "size": "[min, 1.25 x max]",
    "dt": "[min / 2, 5 x max]",
}
#: the checked statistics: (rule, min_inside_frac, coverage condition)
CHECKED = {
    "n_obs": ("size", 0.0, True), "dt": ("dt", 0.5, False), "frac_readout_active": ("frac", 0.5, False),
    "rate_active_rel_p50": ("pos", 0.5, False), "peak_rate_rel_p50": ("pos", 0.5, False), "frac_samples_at_floor": ("frac", 0.5, False),
    "kick_clipped_frac_all": ("frac", 0.5, False), "dim_x_traj_pr": ("pos", 0.5, False), "dim_x_traj_n95": ("dim", 0.5, False),
    "dim_x_pooled_obs_n95": ("dim", 0.5, False), "dim_y_traj_pr": ("pos", 0.5, False), "dim_effect_x_pr": ("pos", 0.5, False),
    "dim_effect_x_n95": ("dim", 0.5, False), "effect_energy_outside_passive95": ("frac", 0.5, True),
    "acf_decay_s_median": ("pos", 0.5, False), "onset_latency_10pct_s": ("pos", 0.5, False), "spec_x_f_peak": ("pos", 0.25, False),
    "spec_x_oscillatory_frac": ("frac", 0.25, False), "eff_rel_x_p50": ("pos", 0.5, False), "eff_rel_y_p50": ("pos", 0.5, False),
    "frac_eff_rel_y_below_0.01": ("frac", 0.5, True), "eff_rms_x_rel_scale_p50": ("pos", 0.5, False),
    "resp_frac_1pct_mean": ("frac", 0.5, True), "resp_frac_1pct_any": ("frac", 0.5, False), "decay_x_s_median": ("pos", 0.5, False),
    "latency_y_peak_s_median": ("pos", 0.5, False), "effect_end_over_peak_median": ("frac", 0.5, False),
    "persistence_ratio_kick": ("pos", 0.5, False), "kick_rel_scale_p50": ("pos", 0.5, False), "snr_param_x_median": ("pos", 0.5, False),
    "snr_param_y_median": ("pos", 0.5, False), "params_param_spread_x_rel_level": ("pos", 0.5, False),
    "params_param_spread_x_rel_dynamics": ("pos", 0.5, False), "input_gain_elasticity_x": ("pos", 0.5, False),
    "input_gain_elasticity_y": ("pos", 0.5, False),
}
CHANGE_NOTE = ("exp(median / max over systems of |log(current / earlier)|) for the same systems where both values are positive; "
               "n_from_zero / n_to_zero = systems where the earlier / current value is 0")


def target_range(rule: str, lo: float, hi: float) -> list:
    if rule == "pos":
        return [lo / 2.0, 2.0 * hi]
    if rule == "frac":
        return [max(0.0, lo - 0.1), min(1.0, hi + 0.1)]
    if rule == "dim":
        return [max(1, math.floor(lo / 1.5)), math.ceil(1.5 * hi)]
    if rule == "size":
        return [lo, 1.25 * hi]
    if rule == "dt":
        return [lo / 2.0, 5.0 * hi]
    raise ValueError(rule)


def _sig1(x: float, up: bool) -> float:
    """x rounded to one significant figure, up or down (0 stays 0)."""
    if x == 0 or not math.isfinite(x):
        return 0.0
    e = math.floor(math.log10(abs(x)))
    q = 10.0 ** e
    v = (math.ceil if up else math.floor)(round(x / q, 12)) * q
    return float(round(v, 12 - e if e < 12 else 0))


def coverage(full: dict, mech: dict) -> list:
    lo_c, hi_c = (full, mech) if full["median"] < mech["median"] else (mech, full)
    a, b = _sig1(lo_c["max"], True), _sig1(hi_c["min"], False)
    if a >= b:
        a, b = max(0.01, _sig1(lo_c["median"], True)), _sig1(hi_c["median"], False)
    return [a, b]


def change(cur: dict, earlier: dict) -> dict:
    logs, n_from, n_to, n = [], 0, 0, 0
    for lab, v in cur.items():
        e = (earlier or {}).get(lab)
        if v is None or e is None or not (math.isfinite(float(v)) and math.isfinite(float(e))):
            continue
        v, e = float(v), float(e)
        n += 1
        if e == 0 and v != 0:
            n_from += 1
        elif v == 0 and e != 0:
            n_to += 1
        elif v == e:
            logs.append(0.0)
        elif v > 0 and e > 0:
            logs.append(abs(math.log(v / e)))
    return {"ratio_median": float(math.exp(np.median(logs))) if logs else None,
            "ratio_max": float(math.exp(max(logs))) if logs else None, "n_systems": n, "n_from_zero": n_from, "n_to_zero": n_to,
            "note": CHANGE_NOTE}


def per_system_values(root: Path, labels: dict) -> tuple[dict, dict, dict]:
    """({label: compute_all output}, {label: class}, counts) of every labelled system present under root."""
    per, classes, counts = {}, {}, {"records": 0, "per_system": {}}
    for lab, sid in labels.items():
        d = root / sid.replace(":", "_")
        rec, records = CS.load_dataset_dir(d)
        out = CS.compute_all(records, rec)
        per[lab] = {k: v for k, v in out.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
        classes[lab] = "full" if rec.get("mode") == "full" else "mechanism"
        counts["records"] += len(records)
        counts["per_system"][lab] = len(records)
        print(f"{lab} ({sid}): {len(records)} records", flush=True)
    return per, classes, counts


def build(per: dict, classes: dict, earlier: dict, prose: dict, *, version: str, counts: dict) -> dict:
    pooled = CS.pool(per, classes)
    est = earlier.get("statistics") or {}
    stats = {}
    for nm in sorted(pooled):
        ent = pooled[nm]
        cls, why = CS.dependence(nm)
        e = {"definition": CS.describe(nm), "dependence": {"class": cls, "reason": why}, "per_system": ent["per_system"],
             "real_all": ent["all"], "real_full": ent.get("full"), "real_mechanism": ent.get("mechanism"),
             "change_vs_earlier_design": change(ent["per_system"], (est.get(nm) or {}).get("per_system") or {})}
        if nm in CHECKED:
            rule, mif, cov = CHECKED[nm]
            lo, hi = ent["all"]["min"], ent["all"]["max"]
            e.update({"check": True, "rule": RULES[rule], "target_range": target_range(rule, lo, hi), "min_inside_frac": mif,
                      "coverage": coverage(ent["full"], ent["mechanism"]) if cov else None,
                      "rationale": (prose.get("rationale") or {}).get(nm, ""),
                      "earlier_design": {k: (est.get(nm) or {}).get(k) for k in ("real_all", "target_range", "coverage")}})
        else:
            e.update({"check": False, "target_range": None})
        stats[nm] = e
    n_rec = sorted(counts["per_system"].values())
    out = {"version": version, "n_systems": {"all": len(per), "full": sum(c == "full" for c in classes.values()),
                                              "mechanism": sum(c == "mechanism" for c in classes.values())},
           "systems": {lab: {"class": classes[lab]} for lab in per}, "stat_version": CS.STAT_VERSION,
           "code": "phase4/src/brainir_causal/calibstats.py (load_dataset_dir / compute_all / pool / compare / dependence)",
           "record_selection": (f"every public record of each system (calibstats.load_dataset_dir without a cap): {counts['records']} records, "
                                f"{n_rec[0]}-{n_rec[-1]} per system; per-trajectory statistics use at most {CS.MAX_RECORDS_PER_KIND} records "
                                "per record kind inside compute_all"),
           "rules": dict(RULES), "check_rule": prose["check_rule"], "coverage_rule": prose["coverage_rule"], "classes": prose["classes"],
           "dependence_classes": prose["dependence_classes"], "labels": prose["labels"], "source": prose["source"], "design": prose["design"],
           "note": prose["note"], "caveats": prose["caveats"], "statistics": stats}
    return out


def compare(a: dict, b: dict, *, tol: float = 0.0) -> list[str]:
    """Differences between two target files in every COMPUTED field (per statistic: per_system, summaries, dependence, definition,
    change, check, rule, target_range, min_inside_frac, coverage, earlier_design) and the statistic sets."""
    out = []
    sa, sb = a.get("statistics") or {}, b.get("statistics") or {}
    for nm in sorted(set(sa) ^ set(sb)):
        out.append(f"{nm}: only in {'first' if nm in sa else 'second'}")

    def same(x, y):
        if isinstance(x, dict) and isinstance(y, dict):
            return set(x) == set(y) and all(same(x[k], y[k]) for k in x)
        if isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
            return len(x) == len(y) and all(same(u, v) for u, v in zip(x, y))
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool) and not isinstance(y, bool):
            if math.isnan(float(x)) and math.isnan(float(y)):
                return True
            return abs(float(x) - float(y)) <= tol * max(1.0, abs(float(x)), abs(float(y)))
        return x == y
    for nm in sorted(set(sa) & set(sb)):
        for f in ("definition", "dependence", "per_system", "real_all", "real_full", "real_mechanism", "change_vs_earlier_design", "check",
                  "rule", "target_range", "min_inside_frac", "coverage", "earlier_design"):
            if f in sa[nm] or f in sb[nm]:
                if not same(sa[nm].get(f), sb[nm].get(f)):
                    out.append(f"{nm}.{f}: {json.dumps(sa[nm].get(f), default=str)[:160]} != {json.dumps(sb[nm].get(f), default=str)[:160]}")
    return out


PROSE_KEYS = ("check_rule", "coverage_rule", "classes", "dependence_classes", "labels", "source", "design", "note", "caveats")


def prose_of(targets: dict) -> dict:
    """The prose fields of a targets file (rationales keyed by statistic; the top-level texts)."""
    out = {k: targets.get(k) for k in PROSE_KEYS}
    out["rationale"] = {nm: e.get("rationale", "") for nm, e in (targets.get("statistics") or {}).items() if e.get("check")}
    return out


def apply_prose(targets: dict, prose: dict) -> dict:
    """A copy of `targets` with its prose fields (the top-level texts and the checked statistics' rationales) taken from `prose`;
    every computed field is untouched."""
    out = json.loads(json.dumps(targets))
    for k in PROSE_KEYS:
        out[k] = prose[k]
    for nm, e in out["statistics"].items():
        if e.get("check"):
            e["rationale"] = (prose.get("rationale") or {}).get(nm, "")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--root", type=Path, required=True)
    b.add_argument("--earlier", type=Path, required=True, help="the earlier targets file (change / earlier_design fields)")
    b.add_argument("--prose", type=Path, default=None, help="JSON prose fields (default: those of --prose-from)")
    b.add_argument("--prose-from", type=Path, default=None, help="take the prose fields from this targets file")
    b.add_argument("--version", required=True)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--labels", type=Path, default=None, help="JSON {label: system id} (default: LABELS)")
    c = sub.add_parser("compare")
    c.add_argument("a", type=Path)
    c.add_argument("b", type=Path)
    c.add_argument("--tol", type=float, default=0.0)
    a = sub.add_parser("apply-prose")
    a.add_argument("--targets", type=Path, required=True)
    a.add_argument("--prose", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.cmd == "compare":
        diffs = compare(json.loads(args.a.read_text(encoding="utf-8")), json.loads(args.b.read_text(encoding="utf-8")), tol=args.tol)
        print(json.dumps({"n_differences": len(diffs), "differences": diffs[:200]}, indent=1))
        return 0 if not diffs else 1
    if args.cmd == "apply-prose":
        t = json.loads(args.targets.read_text(encoding="utf-8"))
        out = apply_prose(t, json.loads(args.prose.read_text(encoding="utf-8")))
        assert not compare(t, out), "apply-prose changed a computed field"
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(out, indent=1, sort_keys=False, default=str) + "\n", encoding="utf-8", newline="\n")
        return 0
    earlier = json.loads(args.earlier.read_text(encoding="utf-8"))
    labels = json.loads(args.labels.read_text(encoding="utf-8")) if args.labels else dict(LABELS)
    if args.prose is not None:
        prose = json.loads(args.prose.read_text(encoding="utf-8"))
    else:
        prose = prose_of(json.loads((args.prose_from or args.earlier).read_text(encoding="utf-8")))
    t0 = time.time()
    per, classes, counts = per_system_values(args.root, labels)
    out = build(per, classes, earlier, prose, version=args.version, counts=counts)
    out["created_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=1, sort_keys=False, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"statistics": len(out["statistics"]), "checked": sum(bool(e.get("check")) for e in out["statistics"].values()),
                      "records": counts["records"], "seconds": round(time.time() - t0, 1)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
