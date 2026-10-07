"""Phase 4 SELF-AUDIT executor (goal5 section 91; research/phase4/SELF_AUDIT_PLAN.md: Q1-Q21 with the pass rules fixed there before
any Level C evidence exists). ORCHESTRATOR SIDE; hashed by the method lock.

    uv run --no-sync --project phase4 python scripts/p4/self_audit_p4.py probes --config research/phase4/SELF_AUDIT_CONFIG.json
    uv run --no-sync --project phase4 python scripts/p4/self_audit_p4.py run --config research/phase4/SELF_AUDIT_CONFIG.json
        -> research/phase4/SELF_AUDIT.json / SELF_AUDIT.md (post-lock; ANSWER-BEARING)
    uv run --no-sync --project phase4 python scripts/p4/self_audit_p4.py prep --config <dry-run config>     # dry runs: missing fits
                                                                                                           # / evaluations / refits

INPUTS (the configuration, written BEFORE the lock; roles named from the Level B results):
    {"tier": "conf", "real_level": "C", "seed": 0, "method": <locked name>, "methods_dir": <locked package>,
     "dirs": {role: <directory with evals/<sid>_s<seed>.pkl (full harness.evaluate_job outputs, private units included),
                     fits/<sid>_s<seed>.json (side records), refits/<sid>_b<b>.json (Level C bootstrap refits, criterion F)>},
              roles: method, id_reference, id_baseline, input_only, readout_history, linear_controlled, full_state_bound,
                     strongest_baseline, phase3 (the Level C run's per-method directories <levelc_run>/<method_key>),
     "refs_dir": <levelc_run>/refs (optional: <sid>.pkl = {reference name: result}),
     "verdicts": <assemble_round's <method_key>.json> (optional; else computed here with the configured bounds),
     "studies": {"ablations": <out dir>, "counterexamples": <out dir>},
     "loops_summary": <PROTOCOL 5.17 summary JSON> (Q10), "sharing": <PROTOCOL 5.14 sharing JSON> (Q18),
     "calibration_check": <calibstats compare of the confirmation suite> (Q16), "probes_dir": <out>/probes}
Every check reads Level C results only (plus the post-lock studies and the probes, which run on the same hidden data after the lock).
A missing input makes a check NOT_TESTABLE (never PASS); a sub-condition that cannot be tested (e.g. no real network) makes the check
PARTIAL. "FAIL weakens the central claim and is reported, never hidden."

PROBES (`probes`, custom isolated jobs of p4post.isojob on the locked method's fits): memo_probe (Q4 a / b; a subset of systems),
encodings (Q5; every system), readin_probe (Q7; synthetic systems), lift_jitter (Q8 / Q9; every system).
OPERATIONALISATIONS fixed here (the plan's wording left them open): Q1 comparators = every available ID comparator (the ID-SHORTCUT
reference, the best ID baseline) and each must be beaten; "method better" = one-sided 95 % upper bound of the paired difference < 0
(suite: mean over compressible systems, unstratified system bootstrap; networks: identity-cell interval); Q11 below-detection
false confidence = the share of covered below-class items whose PREDICTED effect is detectable (pred ES >= 1); Q4 d = an AST scan of
the locked source for `global` statements, module-level mutable containers mutated in functions, and memoisation decorators
(PASS only with no finding; findings are listed for review).
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p4"))
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from p4post import common as C  # noqa: E402
from p4post import execute as X  # noqa: E402
from p4post import pairstats as PS  # noqa: E402

from brainir_causal.evalio import HELDOUT_KINDS, PRIMARY, SHORTCUT_KINDS, VERDICT_KINDS  # noqa: E402

PASS, FAIL, PARTIAL, NOT_TESTABLE, REPORT, NA = "PASS", "FAIL", "PARTIAL", "NOT_TESTABLE", "REPORT", "NOT_APPLICABLE"
QUESTIONS = {
    "Q1": ("Could intervention ID alone explain results?", "paired EE vs the ID-shortcut comparators on target-shift and held-out-family "
           "items; SMS with the ID features alone", "method better (upper CI < 0) on the confirmation suite and on >= 2 of 3 real full "
           "networks; SMS_ID upper CI <= tau_SMS on >= 50 % of systems"),
    "Q2": ("Could stimulus alone explain results?", "paired EE vs the input-only baseline",
           "method better on the confirmation suite and on >= 2 of 3 full networks"),
    "Q3": ("Could readout history explain results?", "paired EE and passive NMSE vs the readout-history baseline",
           "method better on EE on the confirmation suite and on >= 2 of 3 full networks"),
    "Q4": ("Did future data leak?", "(a) truncated-history encodings bitwise equal after the worker saw the future; (b) decoy encodings "
           "change no prediction; (c) no refused event in the fit / evaluation sandboxes; (d) code audit for global state", "all four hold"),
    "Q5": ("Does the latent state collapse?", "participation ratio of the encodings over the pool vs k; whitening floor",
           "PR >= min(k, 1.5) on >= 80 % of systems with k >= 2; floor binds on < 5 %"),
    "Q6": ("Does residual microstate predict intervention outcomes?", "ICG_y and SMS with x_res alone",
           "upper CI <= tolerance on >= 60 % of compressible confirmation systems and on the real full networks where testable"),
    "Q7": ("Are intervention operators state-dependent?", "read-in dz for one event at many states vs the true state-dependence",
           "descriptive; flag where the model's read-in is state-independent but the truth's state-dependence explains > 30 %"),
    "Q8": ("Does the lift exploit simulator quirks?", "lift success under +-10 % amplitude jitter; share of successful lifts at clipping "
           "bounds or beyond the development range", "success drops by < 50 % relative; < 20 % saturating / out-of-range"),
    "Q9": ("Do multiple lifts diverge later?", "multiple-lift divergence at the long vs the medium horizon",
           "long / medium ratio <= 2 on >= 60 % of testable systems"),
    "Q10": ("Does active design just choose large-effect interventions?", "designed vs magnitude-matched random design at the same budgets",
            "if active design succeeds (PROTOCOL 5.17) it must also beat magnitude-matched random at >= 2 budgets"),
    "Q11": ("Does causal state fail under weak effects?", "EE and abstention per detectability class",
            "weak class: upper CI of EE < 1, or abstention >= 50 %; below-detection class: false-confidence rate <= tau_FC"),
    "Q12": ("Does performance disappear on unseen intervention types?", "EE on far-shift families vs in-family",
            "far-shift EE upper CI < 1 on >= 50 % of systems"),
    "Q13": ("Does k change wildly across resamples?", "bootstrap-refit k (PROTOCOL 5.10)", "stable on >= 70 % of confirmation systems"),
    "Q14": ("Does a simple linear controlled model perform equally well?", "paired EE vs the best linear controlled baseline",
            "report; FAIL = not significantly better (goal5 94 D)"),
    "Q15": ("Does the full-state model itself fail?", "the full-state bound's EE and criterion A per system",
            "report; where it fails, the compact-state failure is attributed to excitation / data (goal5 94 B)"),
    "Q16": ("Does the synthetic benchmark resemble real response statistics?", "calibstats compare of the confirmation suite vs the public "
            "real targets", "required statistics in range (acceptance criterion 11)"),
    "Q17": ("False compact causal states on non-compressible systems?", "CAUSAL STATE SUPPORTED on types 20 / 21",
            "at most 1 of their confirmation systems"),
    "Q18": ("Does shared dynamics fail when systems are unrelated?", "sharing rule on unrelated pairs", "rejected on every unrelated pair"),
    "Q19": ("Can adversarial counterexample search break the model immediately?", "counterexample search, 50 evaluations per system",
            "found on <= 50 % of confirmation systems"),
    "Q20": ("Does intervention training matter?", "the locked method with all interventional training removed",
            "removal worsens EE significantly (paired, system bootstrap)"),
    "Q21": ("Is the state bottleneck needed?", "the locked method without the state bottleneck",
            "report 'outcomes predictable but compact causal abstraction unsupported' if the direct model predicts and the compact one "
            "does not"),
}


# ================================================================================================================ inputs
class Inputs:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.seed = int(cfg.get("seed", 0))
        self.tier, self.real_level = cfg.get("tier"), cfg.get("real_level")
        self.systems = C.resolve_systems(self.tier, self.real_level, cfg.get("systems") or None)
        self._cache: dict = {}
        self.truth = C.load_json(C.SU.tier_dirs(self.tier, C.SU.SUITES)["base"] / "truth" / "systems_truth.json", {}) if self.tier else {}
        self.mg = C.margins()

    def dir(self, role: str) -> Path | None:
        """The role's directory in the studies' layout, or a sentinel path for a role served by the Level C run."""
        d = (self.cfg.get("dirs") or {}).get(role)
        if d:
            return Path(d)
        if self.store is not None and (self.cfg.get("roles") or {}).get(role):
            return Path(f"levelc:{self.cfg['roles'][role]}")
        return None

    @property
    def store(self):
        if "_store" not in self._cache:
            from p4post.levelc_io import LevelCStore
            lc = self.cfg.get("levelc_run")
            self._cache["_store"] = LevelCStore(lc) if lc else None
        return self._cache["_store"]

    def ev(self, role: str, sid: str) -> dict | None:
        key = (role, sid)
        if key not in self._cache:
            d = (self.cfg.get("dirs") or {}).get(role)
            src = (self.cfg.get("roles") or {}).get(role)
            if d:
                p = Path(d) / "evals" / f"{C.SU._safe(sid)}_s{self.seed}.pkl"
                if p.exists():
                    import pickle
                    with open(p, "rb") as fh:
                        self._cache[key] = pickle.load(fh)
                else:
                    self._cache[key] = None
            elif src and self.store is not None:
                from p4post.levelc_io import fixed, resolve_eval
                self._cache[key] = resolve_eval(self.store, src, sid, self._cache.setdefault("_fixed", fixed()))
            else:
                self._cache[key] = None
        return self._cache[key]

    def res(self, role: str, sid: str) -> dict | None:
        e = self.ev(role, sid)
        return (e or {}).get("result")

    def side(self, role: str, sid: str) -> dict | None:
        d = (self.cfg.get("dirs") or {}).get(role)
        if d:
            return C.load_json(Path(d) / "fits" / f"{C.SU._safe(sid)}_s{self.seed}.json")
        if role == "method" and self.store is not None:
            return self.store.fit_side(sid, self.seed)
        return None

    def refit_ks(self, role: str, sid: str, n: int = 5) -> list:
        d = (self.cfg.get("dirs") or {}).get(role)
        out = []
        for b in range(n):
            if d:
                s = C.load_json(Path(d) / "refits" / f"{C.SU._safe(sid)}_b{b}.json")
            elif role == "method" and self.store is not None:
                s = self.store.refit_side(sid, b)
            else:
                s = None
            k = ((s or {}).get("info") or {}).get("k", {}).get(sid) if s else None
            out.append(None if k is None else int(k))
        return out

    def ref(self, sid: str, name: str) -> dict | None:
        if self.store is not None:
            return self.store.refs(sid).get(name)
        return None

    @property
    def synthetic(self) -> list[str]:
        return sorted(s for s, d in self.systems.items() if d["kind"] == "synthetic")

    def noncompressible(self, sid: str) -> bool:
        e = self.ev("method", sid)
        if e is not None and e.get("truth_noncompressible") is not None:
            return bool(e["truth_noncompressible"])
        return str((self.truth.get(sid) or {}).get("k")) == "none"

    @property
    def compressible(self) -> list[str]:
        return [s for s in self.synthetic if not self.noncompressible(s)]

    @property
    def networks(self) -> list[str]:
        return sorted(s for s, d in self.systems.items() if d["kind"] == "real" and ":full" in s)

    def study(self, name: str, file: str) -> dict | None:
        d = (self.cfg.get("studies") or {}).get(name)
        return C.load_json(Path(d) / file) if d else None

    def probe(self, role: str) -> dict | None:
        d = self.cfg.get("probes_dir")
        return C.load_json(Path(d) / f"{role}.json") if d else None


# ================================================================================================================ helpers
def _st(ok: bool | None) -> str:
    return NOT_TESTABLE if ok is None else (PASS if ok else FAIL)


def _combine(parts: list[bool | None]) -> str:
    if not parts or all(p is None for p in parts):
        return NOT_TESTABLE
    if any(p is False for p in parts):
        return FAIL
    return PARTIAL if any(p is None for p in parts) else PASS


def _paired_vs(inp: Inputs, role: str, kinds, metric_kinds_name: str, seed: int) -> dict:
    """The method better than `role`: suite (compressible systems) and per real full network."""
    if inp.dir(role) is None:
        return {"available": False}
    comp = inp.compressible
    a = {s: PS.metric({"items": {"effects": ((inp.res("method", s) or {}).get("items") or {}).get("effects")}}, metric_kinds_name) for s in comp}
    b = {s: PS.metric({"items": {"effects": ((inp.res(role, s) or {}).get("items") or {}).get("effects")}}, metric_kinds_name) for s in comp}
    suite = PS.suite_paired(a, b, comp, worst=10.0, direction="lower", seed=seed) if comp else None
    nets = {n: PS.system_ee_diff(inp.res("method", n), inp.res(role, n), kinds=kinds, seed=seed + 1) for n in inp.networks}
    suite_ok = None if suite is None or suite.get("point") is None else bool(suite["upper95"] is not None and suite["upper95"] < 0)
    n_better = sum(1 for r in nets.values() if r.get("upper95") is not None and r["upper95"] < 0)
    nets_ok = None if len(inp.networks) < 3 else bool(n_better >= 2)
    return {"available": True, "suite": suite, "suite_better": suite_ok, "networks": nets, "networks_better": n_better,
            "networks_ok": nets_ok, "n_networks": len(inp.networks)}


# ================================================================================================================ checks
def q1(inp: Inputs) -> dict:
    comps = [r for r in ("id_comparator", "id_reference", "id_baseline") if inp.dir(r) is not None]
    rows = {r: _paired_vs(inp, r, SHORTCUT_KINDS, "EE_shortcut", 101) for r in comps}
    sms_ok = []
    tau = float(inp.mg["tolerances"]["tau_SMS"])
    for s in inp.compressible + inp.networks:
        m = ((inp.res("method", s) or {}).get("mediation") or {}).get("SMS_id") or {}
        ci = m.get("ci95") or [None, None]
        if m and ci[1] is not None:
            sms_ok.append(bool(ci[1] <= tau))
    share = (sum(sms_ok) / len(sms_ok)) if sms_ok else None
    parts = [v.get("suite_better") for v in rows.values()] + [v.get("networks_ok") for v in rows.values()]
    parts.append(None if share is None else share >= 0.5)
    return {"status": _combine(parts) if rows else NOT_TESTABLE, "comparators": rows, "SMS_id_share_within_tau": share,
            "n_sms": len(sms_ok), "tau_SMS": tau}


def _simple_vs(inp: Inputs, role: str, seed: int, extra=None) -> dict:
    r = _paired_vs(inp, role, VERDICT_KINDS, "EE", seed)
    if not r.get("available"):
        return {"status": NOT_TESTABLE, "reason": f"no evaluations of the role {role!r}"}
    out = {"status": _combine([r["suite_better"], r["networks_ok"]]), **r}
    if extra:
        out.update(extra(inp))
    return out


def q3_nmse(inp: Inputs) -> dict:
    comp = inp.compressible
    a = {s: PS.metric(inp.res("method", s), "obs_nmse") for s in comp}
    b = {s: PS.metric(inp.res("readout_history", s), "obs_nmse") for s in comp}
    return {"passive_nmse_suite_method_minus_baseline": PS.suite_paired(a, b, comp, worst=10.0, seed=303) if comp else None}


def _audit_source(mdir: Path) -> list[dict]:
    """Q4 d: an AST scan for global state (module docstring)."""
    findings = []
    mutators = {"append", "extend", "insert", "update", "add", "setdefault", "pop", "popitem", "clear", "remove", "discard",
                "appendleft", "__setitem__"}
    for p in sorted(Path(mdir).rglob("*.py")):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError as e:
            findings.append({"file": str(p), "line": e.lineno, "kind": "syntax error"})
            continue
        mod_mut = {}
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                val = node.value
                is_mut = isinstance(val, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)) or (
                    isinstance(val, ast.Call) and isinstance(val.func, (ast.Name, ast.Attribute))
                    and (getattr(val.func, "id", None) or getattr(val.func, "attr", None)) in ("list", "dict", "set", "defaultdict", "deque",
                                                                                                 "OrderedDict", "Counter"))
                for t in targets:
                    if isinstance(t, ast.Name) and is_mut:
                        mod_mut[t.id] = node.lineno
        for node in ast.walk(tree):
            if isinstance(node, ast.Global):
                findings.append({"file": p.relative_to(mdir).as_posix(), "line": node.lineno, "kind": "global statement", "names": node.names})
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    name = getattr(dec, "attr", None) or getattr(dec, "id", None) or getattr(getattr(dec, "func", None), "attr", None) or \
                        getattr(getattr(dec, "func", None), "id", None)
                    if name in ("lru_cache", "cache", "cached_property"):
                        findings.append({"file": p.relative_to(mdir).as_posix(), "line": node.lineno, "kind": f"memoisation ({name})",
                                         "function": node.name})
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and isinstance(sub.func.value, ast.Name) \
                            and sub.func.value.id in mod_mut and sub.func.attr in mutators:
                        findings.append({"file": p.relative_to(mdir).as_posix(), "line": sub.lineno, "kind": "module-level container mutated",
                                         "name": sub.func.value.id, "defined_line": mod_mut[sub.func.value.id]})
                    if isinstance(sub, (ast.Assign, ast.AugAssign)):
                        tg = sub.targets if isinstance(sub, ast.Assign) else [sub.target]
                        for t in tg:
                            if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id in mod_mut:
                                findings.append({"file": p.relative_to(mdir).as_posix(), "line": sub.lineno,
                                                 "kind": "module-level container item assigned", "name": t.value.id})
    return findings


def _tripwire_scan(inp: Inputs) -> dict:
    hits, fatal, n_fit, n_eval = [], [], 0, 0

    def walk(o, where):
        if isinstance(o, dict):
            if o.get("tripwire_hits"):
                hits.append({"where": where, "hits": o.get("tripwire_hits"), "first": o.get("tripwire_first")})
            if o.get("fatal"):
                fatal.append({"where": where, "fatal": str(o.get("fatal"))[:200]})
            for k, v in o.items():
                walk(v, where)
        elif isinstance(o, list):
            for v in o:
                walk(v, where)
    for s in inp.systems:
        side = inp.side("method", s)
        if side is not None:
            n_fit += 1
            walk(side.get("isolation"), f"fit {s}")
        r = inp.res("method", s)
        if r is not None:
            n_eval += 1
            walk(r.get("isolation"), f"eval {s}")
    return {"n_fits_scanned": n_fit, "n_evals_scanned": n_eval, "tripwire_hits": hits[:20], "fatal_workers": fatal[:20],
            "ok": (n_fit + n_eval) > 0 and not hits and not fatal}


def q4(inp: Inputs) -> dict:
    memo = inp.probe("memo_probe") or {}
    a = [v.get("a_all_equal") for v in memo.values() if isinstance(v, dict) and "a_all_equal" in v]
    b = [v.get("b_all_equal") for v in memo.values() if isinstance(v, dict) and "b_all_equal" in v]
    a_ok = None if not a else all(a)
    b_ok = None if not b else all(b)
    scan = _tripwire_scan(inp)
    c_ok = scan["ok"] if (scan["n_fits_scanned"] + scan["n_evals_scanned"]) else None
    mdir = inp.cfg.get("methods_dir")
    findings = _audit_source(Path(mdir)) if mdir and Path(mdir).exists() else None
    d_ok = None if findings is None else not findings
    return {"status": _combine([a_ok, b_ok, c_ok, d_ok]), "a_truncation": {"ok": a_ok, "n_systems": len(a)},
            "b_decoys": {"ok": b_ok, "n_systems": len(b)}, "c_sandbox": scan, "d_code_audit": {"ok": d_ok, "findings": findings}}


def q5(inp: Inputs) -> dict:
    enc = inp.probe("encodings") or {}
    rows = {s: v for s, v in enc.items() if isinstance(v, dict) and "pr_pool" in v}
    k2 = {s: v for s, v in rows.items() if v.get("k") is not None and int(v["k"]) >= 2 and v.get("pr_pool") is not None}
    ok_pr = [bool(v["pr_pool"] >= min(float(v["k"]), 1.5)) for v in k2.values()]
    binds = [bool(v.get("floor_binds")) for v in rows.values()]
    share_pr = (sum(ok_pr) / len(ok_pr)) if ok_pr else None
    share_bind = (sum(binds) / len(binds)) if binds else None
    return {"status": _combine([None if share_pr is None else share_pr >= 0.8, None if share_bind is None else share_bind < 0.05]),
            "share_pr_ok": share_pr, "n_k_ge_2": len(k2), "share_floor_binds": share_bind, "n_systems": len(rows),
            "per_system": {s: {"k": v.get("k"), "pr_pool": v.get("pr_pool"), "floor_binds": v.get("floor_binds")} for s, v in rows.items()}}


def q6(inp: Inputs) -> dict:
    tol = inp.mg["tolerances"]
    out, ok_syn, ok_net = {}, [], []
    for s in inp.compressible + inp.networks:
        r = inp.res("method", s) or {}
        sms = (r.get("mediation") or {}).get("SMS_x_res") or {}
        icg = (r.get("closure") or {}).get("ICG_y") or {}
        su, iu = (sms.get("ci95") or [None, None])[1], (icg.get("ci95") or [None, None])[1]
        if su is None or iu is None:
            out[s] = {"testable": False}
            continue
        ok = bool(su <= float(tol["tau_SMS"]) and iu <= float(tol["tau_ICG"]))
        out[s] = {"SMS_x_res_upper": su, "ICG_y_upper": iu, "ok": ok}
        (ok_net if s in inp.networks else ok_syn).append(ok)
    share = (sum(ok_syn) / len(ok_syn)) if ok_syn else None
    return {"status": _combine([None if share is None else share >= 0.6, None if not ok_net else all(ok_net)]), "share_syn": share,
            "n_syn": len(ok_syn), "networks_ok": ok_net, "per_system": out}


def q7(inp: Inputs) -> dict:
    pr = inp.probe("readin_probe") or {}
    rows = {s: v for s, v in pr.items() if isinstance(v, dict) and v.get("testable")}
    flags = [s for s, v in rows.items() if (v.get("truth_share") or 0) > 0.3 and v.get("model_share") is not None and v["model_share"] < 0.05]
    return {"status": REPORT if rows else NOT_TESTABLE, "n_testable": len(rows), "flagged_state_independent": flags,
            "per_system": {s: {k: v.get(k) for k in ("model_share", "truth_share", "truth_mapped_share", "n_states")} for s, v in rows.items()},
            "rule": "flag: truth state-dependence share > 0.3 and model share < 0.05 (whitened coordinates)"}


def q8(inp: Inputs) -> dict:
    lj = inp.probe("lift_jitter") or {}
    rows = {s: v for s, v in lj.items() if isinstance(v, dict) and v.get("success_rate") is not None}
    s0 = [v["success_rate"] for v in rows.values()]
    s1 = [v.get("success_rate_jitter") or 0.0 for v in rows.values()]
    m0, m1 = (float(np.mean(s0)) if s0 else None), (float(np.mean(s1)) if s1 else None)
    drop = (1.0 - m1 / m0) if (m0 and m1 is not None and m0 > 0) else None
    exact = [v["exact_per_lift"]["share_saturating_or_beyond"] for v in rows.values() if (v.get("exact_per_lift") or {}).get("share_saturating_or_beyond") is not None]
    proxy = [v["share_saturating_or_beyond"] for v in rows.values() if v.get("share_saturating_or_beyond") is not None]
    sat = float(np.mean(exact)) if exact else (float(np.mean(proxy)) if proxy else None)
    lift_any = bool(m0 and m0 > 0)
    return {"status": (_combine([None if drop is None else drop < 0.5, None if sat is None else sat < 0.2]) if lift_any
                       else (NOT_TESTABLE if not rows else FAIL)),
            "mean_success": m0, "mean_success_jitter": m1, "relative_drop": drop, "share_saturating_or_beyond": sat,
            "saturation_measure": "per successful lift (evaluator hook)" if exact else "all simulated candidates (conservative proxy)",
            "n_systems": len(rows), "note": "no successful lift at all is a FAIL of the native lift, not of this check" if not lift_any and rows else ""}


def q9(inp: Inputs) -> dict:
    lj = inp.probe("lift_jitter") or {}
    ratios = {s: v.get("consistency_long_over_medium") for s, v in lj.items() if isinstance(v, dict) and v.get("consistency_long_over_medium") is not None}
    share = (sum(1 for r in ratios.values() if r <= 2.0) / len(ratios)) if ratios else None
    return {"status": _st(None if share is None else share >= 0.6), "share_ratio_le_2": share, "n_testable": len(ratios), "ratios": ratios}


def q10(inp: Inputs) -> dict:
    p = inp.cfg.get("loops_summary")
    if not p:
        designer = inp.cfg.get("designer")
        if designer in (None, "none"):
            return {"status": NA, "reason": "the locked method has no designer of its own (no active-design claim to audit)"}
        return {"status": NOT_TESTABLE, "reason": "no loops summary configured"}
    s = C.load_json(p, None)
    if s is None:
        return {"status": NOT_TESTABLE, "reason": f"missing {p}"}
    succeeds = s.get("active_design_succeeds", s.get("succeeds"))
    per_b = s.get("budgets") or {}
    beats = [b for b, v in per_b.items() if (v.get("own_vs_random_matched") or {}).get("upper95") is not None
             and v["own_vs_random_matched"]["upper95"] < 0]
    if succeeds is None:
        return {"status": NOT_TESTABLE, "reason": "the loops summary has no success flag"}
    if not succeeds:
        return {"status": REPORT, "note": "active design did not succeed (PROTOCOL 5.17): nothing to explain", "budgets_beating_matched": beats}
    ok = len(beats) >= 2
    return {"status": PASS if ok else FAIL, "budgets_beating_matched": beats,
            "report": None if ok else "large-effect selection explains the gain"}


def _class_rows(res: dict | None):
    eff = ((res or {}).get("items") or {}).get("effects") or {}
    return eff.get("_scores") or []


def q11(inp: Inputs) -> dict:
    tau_fc = float(inp.mg["tolerances"].get("tau_FC", 0.2))
    weak_ee, weak_abst, below_fc = {}, {}, {}
    for s in inp.compressible + inp.networks:
        sc = _class_rows(inp.res("method", s))
        if not sc:
            continue
        weak = [x for x in sc if getattr(x, "dclass", None) == "weak" and PRIMARY in x.num]
        if weak:
            weak_ee[s] = float(sum(x.num[PRIMARY] for x in weak) / max(sum(x.den[PRIMARY] for x in weak), 1e-300))
            weak_abst[s] = float(np.mean([bool(x.abstain) for x in weak]))
        below = [x for x in sc if getattr(x, "dclass", None) == "below" and x.covered]
        if below:
            below_fc[s] = float(np.mean([float(x.pred_es) >= 1.0 for x in below]))
    syn = [s for s in inp.compressible if s in weak_ee]
    e = PS.suite_mean(weak_ee, syn, worst=10.0) if syn else None
    ab = float(np.mean([weak_abst[s] for s in syn])) if syn else None
    weak_ok = None if e is None else bool((e.get("upper95") is not None and e["upper95"] < 1.0) or (ab is not None and ab >= 0.5))
    fcs = [below_fc[s] for s in inp.compressible if s in below_fc]
    fc_mean = float(np.mean(fcs)) if fcs else None
    below_ok = None if fc_mean is None else fc_mean <= tau_fc
    return {"status": _combine([weak_ok, below_ok]), "weak_EE_suite": PS.strip_private(e) if e else None, "weak_abstention_mean": ab,
            "below_false_confidence_mean": fc_mean, "tau_FC": tau_fc, "n_weak_systems": len(syn), "n_below_systems": len(fcs),
            "below_definition": "share of covered below-detection items whose predicted effect is detectable (pred ES >= 1)"}


def q12(inp: Inputs) -> dict:
    from brainir_causal import evaluate as EV
    out, oks = {}, []
    for s in inp.compressible + inp.networks:
        u = PS.units_of(inp.res("method", s))
        if not u:
            continue
        far = EV.ee_cb(u, PRIMARY, ("far",), "class", 2000, 7)
        inf = EV.ee_cb(u, PRIMARY, ("in",), "class", 2000, 8)
        if not np.isfinite(far.point):
            out[s] = {"testable": False}
            continue
        ok = bool(far.ci95[1] is not None and np.isfinite(far.ci95[1]) and far.ci95[1] < 1.0)
        out[s] = {"EE_far": float(far.point), "EE_far_upper": float(far.ci95[1]), "EE_in": float(inf.point) if np.isfinite(inf.point) else None,
                  "ok": ok}
        oks.append(ok)
    share = (sum(oks) / len(oks)) if oks else None
    return {"status": _st(None if share is None else share >= 0.5), "share": share, "n_testable": len(oks), "per_system": out}


def q13(inp: Inputs) -> dict:
    from brainir_causal.verdict import dimension_status
    rows, oks = {}, []
    for s in inp.synthetic:
        r = inp.res("method", s) or {}
        ks = inp.refit_ks("method", s)
        if all(k is None for k in ks):
            continue
        d = dimension_status(r.get("k"), r.get("compact_limit"), ks, tuple(r["k_range"]) if r.get("k_range") else None, "C")
        rows[s] = {"k": r.get("k"), "refits": ks, "stable": d.get("stable")}
        oks.append(bool(d.get("stable")))
    share = (sum(oks) / len(oks)) if oks else None
    return {"status": _st(None if share is None else share >= 0.7), "share_stable": share, "n_systems": len(oks), "per_system": rows}


def q14(inp: Inputs) -> dict:
    r = _paired_vs(inp, "linear_controlled", VERDICT_KINDS, "EE", 1401)
    if not r.get("available"):
        return {"status": NOT_TESTABLE, "reason": "no evaluations of the linear controlled baseline"}
    better = r["suite_better"]
    return {"status": REPORT if better else FAIL, "method_significantly_better_on_suite": better, **r,
            "if_fail": "goal5 section 94 D: the simple linear controlled model is to be used"}


def q15(inp: Inputs) -> dict:
    thr = 1.0 - float(inp.mg["tolerances"]["delta_A"])
    if inp.dir("full_state_bound") is None:
        return {"status": NOT_TESTABLE, "reason": "no evaluations of the full-state bound"}
    from brainir_causal import evaluate as EV
    rows, fails = {}, []
    for s in inp.compressible + inp.networks:
        u = PS.units_of(inp.res("full_state_bound", s))
        if not u:
            rows[s] = {"missing": True}
            fails.append(s)
            continue
        e = EV.ee_cb(u, PRIMARY, VERDICT_KINDS, "class", 2000, 15)
        a_ok = bool(np.isfinite(e.ci95[1]) and e.ci95[1] < thr)
        rows[s] = {"EE": float(e.point), "EE_upper": float(e.ci95[1]), "A": a_ok}
        if not a_ok:
            fails.append(s)
    return {"status": REPORT, "threshold_A": thr, "n_systems": len(rows), "n_fullstate_fails_A": len(fails), "fails": fails,
            "attribution": "on these systems a compact-state failure is attributed to excitation / data (goal5 section 94 B)", "per_system": rows}


def q16(inp: Inputs) -> dict:
    p = inp.cfg.get("calibration_check")
    s = C.load_json(p, None) if p else None
    if s is None:
        return {"status": NOT_TESTABLE, "reason": f"no calibration compare of the confirmation suite ({p})"}
    sc = s.get("suite_compare") or {}
    n_t, n_ok = sc.get("n_tested"), sc.get("n_ok")
    missing = sc.get("missing") or (s.get("summary") or {}).get("missing") or []
    failing = (s.get("summary") or {}).get("failing") or [k for k, v in (sc.get("statistics") or {}).items() if not v.get("ok")]
    ok = bool(n_t and n_ok == n_t and not missing)
    return {"status": PASS if ok else FAIL, "n_tested": n_t, "n_ok": n_ok, "failing": failing, "missing": missing, "source": p,
            "tier": s.get("what")}


def _verdict_category(inp: Inputs, sid: str) -> str | None:
    vf = inp.cfg.get("verdicts")
    if vf:
        rows = (C.load_json(vf, {}) or {}).get("per_system") or {}
        v = (((rows.get(sid) or {}).get("seeds") or {}).get(str(inp.seed)) or {}).get("verdict") or {}
        cat = (v.get("verdict") or {}).get("category") or v.get("category")        # assemble_round rows nest the verdict once more
        if cat:
            return cat
    from brainir_causal import harness as H
    ev = inp.ev("method", sid)
    if ev is None:
        return None
    tol = inp.mg["tolerances"]
    fb = H.verdict_effects(inp.res("full_state_bound", sid)) if inp.dir("full_state_bound") else None
    idc = H.verdict_effects(inp.res("id_comparator", sid)) if inp.dir("id_comparator") else None
    av = H.assemble_verdict(ev, None, tol, calibrated=inp.mg["calibrated"], fullbound_eff=fb, idshortcut_eff=idc,
                            k_refits=inp.refit_ks("method", sid), level="C", n_boot=1000)
    return ((av.get("verdict") or {}).get("verdict") or {}).get("category") or (av.get("verdict") or {}).get("category")


def q17(inp: Inputs) -> dict:
    types = {s: str((inp.truth.get(s) or {}).get("type", "")) for s in inp.synthetic}
    targets = [s for s in inp.synthetic if inp.noncompressible(s)]
    if not targets:
        return {"status": NOT_TESTABLE, "reason": "no non-compressible confirmation system"}
    cats = {s: _verdict_category(inp, s) for s in targets}
    n_sup = sum(1 for c in cats.values() if c == "causal state supported")
    return {"status": PASS if n_sup <= 1 else FAIL, "n_noncompressible": len(targets), "n_supported": n_sup, "categories": cats,
            "types": {s: types.get(s) for s in targets}}


def q18(inp: Inputs) -> dict:
    p = inp.cfg.get("sharing")
    if not p:
        side = inp.side("method", inp.synthetic[0]) if inp.synthetic else None
        decl = ((side or {}).get("info") or {}).get("ablation_switches", {}).get("shared_dynamics")
        if decl is not None and "not_applicable" in json.dumps(decl):
            return {"status": NA, "reason": f"the method declares shared dynamics not applicable: {decl}"}
        return {"status": NOT_TESTABLE, "reason": "no sharing results configured"}
    s = C.load_json(p, None)
    if s is None:
        return {"status": NOT_TESTABLE, "reason": f"missing {p}"}
    pairs = [x for x in (s.get("pairs") or []) if x.get("related") is False]
    if not pairs:
        return {"status": NOT_TESTABLE, "reason": "no unrelated pair in the sharing results"}
    rejected = [bool(x.get("rejected", not x.get("shared", True))) for x in pairs]
    return {"status": PASS if all(rejected) else FAIL, "n_unrelated_pairs": len(pairs), "n_rejected": sum(rejected)}


def q19(inp: Inputs) -> dict:
    s = inp.study("counterexamples", "COUNTEREXAMPLES.json")
    if s is None:
        return {"status": NOT_TESTABLE, "reason": "no counterexample study configured"}
    q = s.get("Q19") or {}
    return {"status": q.get("status", NOT_TESTABLE), **{k: q.get(k) for k in ("share_found", "n_systems", "n_found", "systems_with_fewer_evaluations")},
            "source_run": s.get("run_id")}


def q20(inp: Inputs) -> dict:
    s = inp.study("ablations", "ABLATIONS.json")
    if s is None:
        return {"status": NOT_TESTABLE, "reason": "no ablation study configured"}
    q = s.get("Q20") or {}
    st = q.get("status") if q.get("status") in (PASS, FAIL) else NOT_TESTABLE
    return {"status": st, "reason": q.get("reason"), "suite": q.get("suite"), "source_run": s.get("run_id"),
            "consequence_if_fail": q.get("consequence_if_fail")}


def q21(inp: Inputs) -> dict:
    s = inp.study("ablations", "ABLATIONS.json")
    if s is None:
        return {"status": NOT_TESTABLE, "reason": "no ablation study configured"}
    q = s.get("Q21") or {}
    rep = q.get("report")
    return {"status": REPORT if rep and rep != "NOT TESTABLE" else NOT_TESTABLE, "report": rep, "source_run": s.get("run_id"),
            "levelb_fullstate_baseline": (q.get("levelb_fullstate_baseline") or {}).get("report")}


CHECKS = {"Q1": q1, "Q2": lambda i: _simple_vs(i, "input_only", 201), "Q3": lambda i: _simple_vs(i, "readout_history", 301, q3_nmse),
          "Q4": q4, "Q5": q5, "Q6": q6, "Q7": q7, "Q8": q8, "Q9": q9, "Q10": q10, "Q11": q11, "Q12": q12, "Q13": q13, "Q14": q14,
          "Q15": q15, "Q16": q16, "Q17": q17, "Q18": q18, "Q19": q19, "Q20": q20, "Q21": q21}


# ================================================================================================================ commands
def _methods_of(cfg: dict) -> list[str]:
    return [m for m in [cfg.get("method")] + list((cfg.get("role_methods") or {}).values()) if m]


def _guard(cfg: dict, what: str, methods_dir) -> dict:
    return C.guard(cfg.get("tier"), cfg.get("real_level"), what=what, dry_run_on_val=bool(cfg.get("dry_run_on_val")),
                   methods=_methods_of(cfg), methods_dir=methods_dir)


def _out_dir(cfg: dict, args, g: dict) -> Path:
    """Official (post-lock, hidden) runs: research/phase4 (SELF_AUDIT.{json,md}). Dry runs: only under the dry-run roots."""
    if g.get("hidden"):
        return Path(args.out) if args.out else ROOT / "research" / "phase4"
    d = Path(args.out or cfg.get("out_dir") or (C.DRY_ROOT / "self_audit"))
    if not C.is_dry_path(d):
        raise PermissionError(f"a dry-run self-audit writes only under the dry-run roots {[str(r) for r in C.DRY_ROOTS]}; got {d}")
    return d


def cmd_run(args) -> int:
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    g = _guard(cfg, "the self-audit", cfg.get("methods_dir"))
    out = _out_dir(cfg, args, g)                                    # refused before any check runs (condition 4)
    t0 = time.time()
    inp = Inputs(cfg)
    results = {}
    for qid, fn in CHECKS.items():
        try:
            r = fn(inp)
        except Exception as e:  # noqa: BLE001 - a crashing check is reported, never skipped
            import traceback
            r = {"status": NOT_TESTABLE, "error": f"{type(e).__name__}: {e}"[:500], "traceback": traceback.format_exc()[-1500:]}
        q, test, rule = QUESTIONS[qid]
        results[qid] = {"question": q, "test": test, "pass_rule": rule, **PS.strip_private(r)}
    counts = {}
    for r in results.values():
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    rec = {"what": "Phase 4 self-audit (goal5 section 91; research/phase4/SELF_AUDIT_PLAN.md)", "created_utc": C.utc(), "hidden": g["hidden"],
           **C.run_marks(g, cfg.get("tier"), cfg.get("real_level")),
           "lock": g["lock"], "tier": cfg.get("tier"), "real_level": cfg.get("real_level"), "method": cfg.get("method"),
           "n_systems": len(inp.systems), "n_compressible": len(inp.compressible), "n_networks": len(inp.networks),
           "tolerances_calibrated": inp.mg["calibrated"], "status_counts": counts, "checks": results, "config": cfg,
           "wall_s": round(time.time() - t0, 1)}
    C.dump_json(rec, out / "SELF_AUDIT.json")
    L = ["# Phase 4 self-audit (goal5 section 91)", ""] + C.dry_banner(rec) + [f"Method `{cfg.get('method')}` on {cfg.get('tier')}"
         f"{' + real ' + str(cfg.get('real_level')) if cfg.get('real_level') else ''}; {len(inp.systems)} systems "
         f"({len(inp.compressible)} compressible synthetic, {len(inp.networks)} real full networks); tolerances "
         f"{'calibrated' if inp.mg['calibrated'] else 'PROVISIONAL'}. Status counts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + ".",
         "", "| id | question | status | pass rule | key evidence |", "|---|---|---|---|---|"]
    for qid, r in results.items():
        L.append(f"| {qid} | {r['question']} | **{r['status']}** | {r['pass_rule']} | {_evidence(qid, r)} |")
    L += ["", "FAIL weakens the central claim and is reported, never hidden; NOT_TESTABLE / PARTIAL name the missing inputs in "
          "SELF_AUDIT.json."]
    (out / "SELF_AUDIT.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"out": str(out), "status_counts": counts}, indent=1), flush=True)
    return 0


def _evidence(qid: str, r: dict) -> str:
    def f(x, nd=3):
        return "-" if x is None else (f"{x:.{nd}g}" if isinstance(x, float) else str(x))
    if r.get("reason"):
        return str(r["reason"])[:160]
    if r.get("error"):
        return "check crashed: " + str(r["error"])[:120]
    if qid == "Q1":
        parts = [f"{k}: suite diff {f((v.get('suite') or {}).get('point'))} (upper {f((v.get('suite') or {}).get('upper95'))})"
                 for k, v in (r.get("comparators") or {}).items()]
        return "; ".join(parts) + f"; SMS_id within tau on {f(r.get('SMS_id_share_within_tau'))}"
    if qid in ("Q2", "Q3", "Q14"):
        s = r.get("suite") or {}
        return f"suite diff {f(s.get('point'))} (upper {f(s.get('upper95'))}); networks better {r.get('networks_better')}/{r.get('n_networks')}"
    if qid == "Q4":
        return (f"a {r['a_truncation']['ok']}, b {r['b_decoys']['ok']}, c {r['c_sandbox']['ok']} "
                f"({r['c_sandbox']['n_fits_scanned']} fits, {r['c_sandbox']['n_evals_scanned']} evals), d {r['d_code_audit']['ok']} "
                f"({len(r['d_code_audit']['findings'] or [])} findings)")
    if qid == "Q5":
        return f"PR ok on {f(r.get('share_pr_ok'))} of {r.get('n_k_ge_2')}; floor binds on {f(r.get('share_floor_binds'))}"
    if qid == "Q6":
        return f"within tolerance on {f(r.get('share_syn'))} of {r.get('n_syn')} synthetic"
    if qid == "Q7":
        return f"{r.get('n_testable')} testable; flagged {len(r.get('flagged_state_independent') or [])}"
    if qid == "Q8":
        return f"success {f(r.get('mean_success'))} -> {f(r.get('mean_success_jitter'))} (drop {f(r.get('relative_drop'))}); saturating {f(r.get('share_saturating_or_beyond'))}"
    if qid == "Q9":
        return f"ratio <= 2 on {f(r.get('share_ratio_le_2'))} of {r.get('n_testable')}"
    if qid == "Q11":
        return f"weak EE upper {f((r.get('weak_EE_suite') or {}).get('upper95'))}, weak abstention {f(r.get('weak_abstention_mean'))}; below FC {f(r.get('below_false_confidence_mean'))}"
    if qid == "Q12":
        return f"far-shift EE upper < 1 on {f(r.get('share'))} of {r.get('n_testable')}"
    if qid == "Q13":
        return f"stable on {f(r.get('share_stable'))} of {r.get('n_systems')}"
    if qid == "Q15":
        return f"full-state bound fails A on {r.get('n_fullstate_fails_A')} of {r.get('n_systems')}"
    if qid == "Q16":
        return f"{r.get('n_ok')}/{r.get('n_tested')} in range; failing {r.get('failing')}"
    if qid == "Q17":
        return f"{r.get('n_supported')} of {r.get('n_noncompressible')} supported"
    if qid == "Q19":
        return f"found on {f(r.get('share_found'))} of {r.get('n_systems')}"
    if qid == "Q20":
        s = r.get("suite") or {}
        return f"EE_ablated - EE_full {f(s.get('point'))} (lower {f(s.get('lower95'))}, p {f(s.get('p_a_worse'))})"
    if qid == "Q21":
        return str(r.get("report"))
    return ""


def cmd_probes(args) -> int:
    """Run the custom probes (p4post.isojob) on the method's fits: memo_probe, encodings, readin_probe, lift_jitter."""
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    g = _guard(cfg, "the self-audit probes", cfg.get("methods_dir"))
    t0 = time.time()
    inp = Inputs(cfg)
    mdir = Path(cfg["methods_dir"])
    probes_dir = Path(cfg["probes_dir"])
    if not g.get("hidden") and not C.is_dry_path(probes_dir):
        raise PermissionError(f"dry-run probes write only under the dry-run roots; got {probes_dir}")
    probes_dir.mkdir(parents=True, exist_ok=True)
    from p4post.levelc_io import model_source
    mdirs = (cfg.get("dirs") or {}).get("method")
    models = {s: model_source(s, inp.seed, fits_from=mdirs, levelc_run=None if mdirs else cfg.get("levelc_run")) for s in inp.systems}
    models = {s: p for s, p in models.items() if p is not None}
    roles = [r for r in args.roles.split(",") if r]
    syn = [s for s in inp.synthetic if s in models]
    memo_sys = (syn[:: max(1, len(syn) // args.memo_systems)][: args.memo_systems] if syn else []) + [s for s in inp.networks if s in models]
    plan = {"memo_probe": memo_sys, "encodings": sorted(models), "readin_probe": syn, "lift_jitter": sorted(models)}
    rec = {"created_utc": C.utc(), **C.run_marks(g, cfg.get("tier"), cfg.get("real_level")), "roles": roles,
           "n": {r: len(plan[r]) for r in roles}, "modal": {}}
    real = any(inp.systems[s]["kind"] == "real" for s in models)
    packed = not args.unpacked
    classes = [X.PACK_EVAL] if packed else sorted({"iso_eval_s"} | ({"iso_eval_l"} if real else set()))
    with C.HiddenRunLog(g["hidden"], "self_audit", "probes", f"{cfg.get('method')}: {', '.join(roles)}"):
        with C.backend(classes, synthetic=bool(syn), app_name="brainir-p4-post-audit", max_containers=args.max_containers) as be:
            key = be.methods_key(mdir)
            for role in roles:
                specs = []
                for s in plan[role]:
                    job = C.eval_job(s, inp.systems[s], lift=False, n_boot=args.n_boot, seed=inp.seed)
                    job.update({"call_timeout_s": 900, "n_items": 6, "n_decoys": 8})
                    specs.append({"sid": s, "sysd": inp.systems[s], "job": job, "model_path": models[s]})
                tr = time.time()
                res = X.run_custom(be, role, specs, key=key, packed=packed, label=f"audit-{role}", done_dir=probes_dir / "_done" / role)
                out = {}
                for sp, (val, err) in zip(specs, res):
                    out[sp["sid"]] = PS.strip_private({k: v for k, v in (val or {}).items() if k != "isolation"}) if val else {"error": err}
                C.dump_json(out, probes_dir / f"{role}.json")
                rec["modal"][role] = {"wall_s": X.wall(tr), "n": len(specs), "n_errors": sum(1 for v in out.values() if v.get("error"))}
                print(f"[audit probes] {role}: {len(specs)} systems in {rec['modal'][role]['wall_s']} s, errors {rec['modal'][role]['n_errors']}",
                      flush=True)
            rec["modal"]["cost"] = be.cost_summary()
    rec["wall_s"] = X.wall(t0)
    C.dump_json(rec, probes_dir / "PROBES_RUN.json")
    return 0


def cmd_prep(args) -> int:
    """DRY RUNS (or gaps post-lock, logged as hidden runs): fit and evaluate every configured role whose evaluations are missing, and
    the method's Level C bootstrap refits (criterion F), with the roles' methods from cfg['role_methods']."""
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    g = _guard(cfg, "the self-audit preparation", cfg.get("prep_methods_dir"))
    t0 = time.time()
    inp = Inputs(cfg)
    run = Path(cfg["prep_run_dir"])
    if not g.get("hidden") and not (C.is_dry_path(run) and (inp.dir("method") is None or C.is_dry_path(inp.dir("method")))):
        raise PermissionError(f"a dry-run preparation writes only under the dry-run roots; got {run} / {inp.dir('method')}")
    mdir = Path(cfg["prep_methods_dir"])
    fit_specs, eval_specs = [], []
    for role, m in (cfg.get("role_methods") or {}).items():
        d = inp.dir(role)
        if d is None or d.parent != run:
            continue
        for s, sysd in inp.systems.items():
            if inp.ev(role, s) is None:
                fit_specs.append({"variant": d.name, "method": m, "sid": s, "sysd": sysd, "seed": inp.seed, "config": {}})
                eval_specs.append({"variant": d.name, "sid": s, "sysd": sysd, "seed": inp.seed})
    if args.refits:
        # the method's Level C bootstrap refits (criterion F) go to <method dir>/refits/<sid>_b<b>.json (side records only)
        mrun, mvar = inp.dir("method").parent, inp.dir("method").name
        for s, sysd in inp.systems.items():
            for b in range(5):
                fit_specs.append({"variant": mvar, "method": cfg["method"], "sid": s, "sysd": sysd, "seed": inp.seed, "config": {},
                                  "bootstrap": b, "run_root": str(mrun)})
    rec = {"created_utc": C.utc(), **C.run_marks(g, cfg.get("tier"), cfg.get("real_level")), "n_fits": len(fit_specs),
           "n_evals": len(eval_specs), "modal": {}}
    packed = not args.unpacked
    real = any(d["kind"] == "real" for d in inp.systems.values())
    classes = X.classes_for(real, packed)
    with C.HiddenRunLog(g["hidden"], "self_audit", "prep", f"{len(fit_specs)} fits and refits"):
        with C.backend(classes, synthetic=True, app_name="brainir-p4-post-auditprep", max_containers=args.max_containers) as be:
            key = be.methods_key(mdir)
            tf = time.time()
            if fit_specs:                                     # ONE wave: the roles' fits and the method's refits together
                X.run_fits(be, fit_specs, key=key, run=run, timeout_s=3600, packed=packed, label="prep-fits")
            rec["modal"]["fits_wall_s"] = X.wall(tf)
            te = time.time()
            if eval_specs:
                X.run_evals(be, eval_specs, key=key, run=run, packed=packed)
            rec["modal"]["evals_wall_s"] = X.wall(te)
            rec["modal"]["cost"] = be.cost_summary()
    rec["wall_s"] = X.wall(t0)
    C.dump_json(rec, run / "PREP_RUN.json")
    print(json.dumps({k: v for k, v in rec.items() if k != "modal"} | {"usd": rec["modal"]["cost"].get("usd_approx_total")}, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--config", required=True)
    r.add_argument("--out", default=None)
    p = sub.add_parser("probes")
    p.add_argument("--config", required=True)
    p.add_argument("--roles", default="memo_probe,encodings,readin_probe,lift_jitter")
    p.add_argument("--memo-systems", type=int, default=8)
    p.add_argument("--n-boot", type=int, default=200)
    p.add_argument("--max-containers", type=int, default=40)
    p.add_argument("--unpacked", action="store_true")
    q = sub.add_parser("prep")
    q.add_argument("--config", required=True)
    q.add_argument("--refits", action="store_true")
    q.add_argument("--max-containers", type=int, default=40)
    q.add_argument("--unpacked", action="store_true")
    args = ap.parse_args(argv)
    return {"run": cmd_run, "probes": cmd_probes, "prep": cmd_prep}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
