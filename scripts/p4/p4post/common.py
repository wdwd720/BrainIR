"""Paths, guards, system resolution and Modal submission helpers of the post-lock drivers (ORCHESTRATOR SIDE).

HIDDEN-DATA GUARD (`guard`). The post-lock studies run on the confirmation tier ('conf') and the real Level C sets ('real_levelc')
only after research/phase4/METHOD_LOCK.json exists and `method_lock_p4.py --check` passes (`require_postlock`); before the lock the
only admissible tiers are the development tier and the toy tiers (dry runs; `PRELOCK_TIERS`), plus the PUBLIC real data. The Level B
selection tier 'val' is refused (these studies never select). Every hidden run writes a START row before it submits anything and a
DONE row after its outputs are written (`HiddenRunLog`), in the orchestrator's hidden-evaluation log.

VAL DRY-RUN ALLOWANCE (`val_dry_run_guard`, CLI --dry-run-on-val; the orchestrator's instruction of 2026-09-27 while the dev tier's
evaluation part is rebuilt), narrowly scoped, every condition enforced here and tested (phase4/tests/test_postlock_drivers.py):
(1) pre-lock only: refused once research/phase4/METHOD_LOCK.json exists; (2) stand-in methods only: every method of the run must be a
registered method of the stand-in packages (scripts/p4/standin_methods, scripts/p4/levelc_standin/methods) or the frozen Phase 3
baseline, and the methods directory must BE a stand-in package or a byte-identical snapshot of one (never the locked methods package
phase4/src/brainir_causal/methods, never a room or a developer's method); (3) the val tier only, no real level: conf, real_levelc and
every other hidden tier stay behind the method lock exactly as before; (4) outputs are marked dry-run and written only under the
dry-run roots (research/phase4/postlock_dryrun, C:/Dev/BrainIR_p4run/postlock_dryrun), never the official locations; no val result
is released or used for any decision; (5) the run record carries the flag, the tier and the stand-in (`run_marks`). The official
path of `guard` is unchanged.

REMOTE LAYOUT. Systems resolve to container paths of the Phase 4 volumes (`suites.REMOTE`): fit data (public part) on the fit volume,
held-out parts / truth / internal records on the eval volume. Custom item sets (`itemsets`) are built into CUSTOM TIERS of the same
layout (`custom_tier`), always orchestrator-held (eval volume), never public.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "phase4" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import suites as SU  # noqa: E402

#: the drivers' run-artefact base: P4_RUN_BASE overrides the Windows default (the Linux driver container, scripts/p4/linux_driver.py;
#: the same variable levelc_lib.RUN_BASE and tournament.RUN read)
RUN_BASE = Path(os.environ.get("P4_RUN_BASE") or "C:/Dev/BrainIR_p4run")
RUN_ROOT = RUN_BASE / "postlock"                              # OFFICIAL bulky artefacts (model bytes, full evaluations); never in git
RUN_DRY_ROOT = RUN_BASE / "postlock_dryrun"                   # dry-run bulky artefacts
OUT_ROOT = ROOT / "research" / "phase4" / "postlock"          # post-lock summaries (ANSWER-BEARING: never into a room)
DRY_ROOT = ROOT / "research" / "phase4" / "postlock_dryrun"   # dry-run summaries (development data; never into a room)
DRY_ROOTS = (DRY_ROOT, RUN_DRY_ROOT)
HIDDEN_LOG = ROOT / "research" / "phase4" / "HIDDEN_EVALUATIONS.md"
MODAL_RUNS = ROOT / "research" / "phase4" / "MODAL_RUNS.md"
METHOD_LOCK = ROOT / "research" / "phase4" / "METHOD_LOCK.json"
LOCKED_METHODS = ROOT / "phase4" / "src" / "brainir_causal" / "methods"
STANDIN_METHODS = ROOT / "scripts" / "p4" / "standin_methods"
#: the dry-run stand-in packages (never a candidate, never in a room) and the frozen Phase 3 baseline (a public module of the benchmark)
STANDIN_DIRS = (STANDIN_METHODS, ROOT / "scripts" / "p4" / "levelc_standin" / "methods")
FROZEN_STANDIN = "frozen_brainir_state_v1"
BENCH = ROOT / "benchmarks" / "causal_state_v1"
REAL_INTERNAL = BENCH / "hidden" / "real_systems_internal.json"

PRELOCK_TIERS = ("dev", "toy", "toyC")
HIDDEN_SYN_TIERS = ("conf", "trap")               # "trap": review G's new trap systems (hidden like conf: after the lock only)
REFUSED_TIERS = ("val",)
REAL_LEVELS = ("public", "C")                      # public real data (dry runs) / the real hidden test (post-lock)
SCRIPTS_REL = "scripts/p4"                          # baked into the iso images (isolation.ISO_SCRIPT_DIRS): p4post_iso.py + p4post/
SCRIPTS_CONTAINER = "/repo/scripts/p4"
ISO_TARGET = "p4post_iso"                          # the module file whose functions the iso "call" jobs name
GENERATOR_PKG = "p4synth"
CUSTOM_PREFIX = "pl_"                              # custom tiers of the post-lock studies


# ================================================================================================================ small I/O
def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def dump_json(obj, path: Path | str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(jsonable(obj), indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")


def load_json(path: Path | str, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def jsonable(o):
    """Plain JSON (numpy scalars / arrays -> Python; non-finite floats -> None; private '_' keys kept: callers strip them)."""
    import numpy as np
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return v if math.isfinite(v) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def method_key(m: str) -> str:
    """File / directory name of a method (as scripts/p4/tournament.py: ':' -> '__', path separators -> '_')."""
    return m.replace(":", "__").replace("/", "_").replace("\\", "_")


def sha256_file(p: Path) -> str:
    b = p.read_bytes()
    if p.suffix in (".py", ".md", ".txt", ".json", ".jsonl", ".toml"):
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()


# ================================================================================================================ guard
def is_hidden(tier: str, real_level: str | None) -> bool:
    return tier in HIDDEN_SYN_TIERS or real_level == "C"


def require_postlock(what: str) -> dict:
    """The method lock exists AND its checker passes (scripts/p4/method_lock_p4.py --check). Returns the lock's summary fields."""
    SU.require_lock(what)
    chk = ROOT / "scripts" / "p4" / "method_lock_p4.py"
    r = subprocess.run([sys.executable, str(chk), "--check"], capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode != 0:
        raise PermissionError(f"{what}: the method lock check failed:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    lock = load_json(METHOD_LOCK, {}) or {}
    return {k: lock.get(k) for k in ("method", "version", "designer", "commit", "created_utc") if k in lock}


def guard(tier: str | None, real_level: str | None, *, what: str, dry_run_on_val: bool = False, methods=(),
          methods_dir: str | Path | None = None) -> dict:
    """The admissibility rule of the module docstring. Returns {"hidden": bool, "lock": {...}, "dry_run": bool, ...}; raises
    PermissionError. `dry_run_on_val` selects the narrowly scoped VAL DRY-RUN ALLOWANCE (`val_dry_run_guard`); `methods` /
    `methods_dir` are checked there only. Otherwise the official rule applies unchanged."""
    if dry_run_on_val:
        return val_dry_run_guard(tier, real_level, what=what, methods=methods, methods_dir=methods_dir)
    if tier in REFUSED_TIERS:
        raise PermissionError(f"{what}: the Level B selection tier {tier!r} is never used by the post-lock studies")
    if real_level is not None and real_level not in REAL_LEVELS:
        raise PermissionError(f"{what}: real level {real_level!r} is not admissible (public | C)")
    if tier is not None and tier not in PRELOCK_TIERS + HIDDEN_SYN_TIERS:
        raise PermissionError(f"{what}: unknown tier {tier!r}")
    hidden = is_hidden(tier or "", real_level)
    lock = require_postlock(what) if hidden else {}
    return {"hidden": hidden, "lock": lock, "dry_run": not hidden, "dry_run_on_val": False}


def _py_hashes(d: Path) -> dict:
    return {q.relative_to(d).as_posix(): sha256_file(q) for q in sorted(Path(d).rglob("*.py")) if "__pycache__" not in q.parts}


def standin_dir_of(methods_dir: str | Path | None) -> Path | None:
    """The stand-in package that `methods_dir` IS, or of which it is a byte-identical snapshot (same .py files, same sha256); else
    None. The locked methods package is never a stand-in."""
    if methods_dir is None:
        return None
    d = Path(methods_dir).resolve()
    if not d.is_dir() or d == LOCKED_METHODS.resolve():
        return None
    for sd in STANDIN_DIRS:
        if sd.is_dir() and (d == sd.resolve() or _py_hashes(d) == _py_hashes(sd)):
            return sd
    return None


def standin_names() -> dict[str, set]:
    """{"plain": {registered names}, "qualified": {"<module>:<name>"}} of the methods registered (`@register` classes with a
    `name = "..."` attribute) in the stand-in packages; parsed, never imported."""
    import ast
    plain, qual = set(), set()
    for sd in STANDIN_DIRS:
        for f in sorted(Path(sd).rglob("*.py")) if Path(sd).is_dir() else []:
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            mod = ".".join(f.relative_to(sd).with_suffix("").parts)
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                if not any((isinstance(d_, ast.Name) and d_.id == "register") or (isinstance(d_, ast.Attribute) and d_.attr == "register")
                           for d_ in node.decorator_list):
                    continue
                for st in node.body:
                    if (isinstance(st, ast.Assign) and any(isinstance(tg, ast.Name) and tg.id == "name" for tg in st.targets)
                            and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str)):
                        plain.add(st.value.value)
                        qual.add(f"{mod}:{st.value.value}")
    return {"plain": plain, "qualified": qual}


def is_standin_method(name: str) -> bool:
    if name == FROZEN_STANDIN:
        return True
    names = standin_names()
    return name in names["qualified"] or (":" not in name and name in names["plain"])


def val_dry_run_guard(tier: str | None, real_level: str | None, *, what: str, methods=(), methods_dir: str | Path | None = None) -> dict:
    """The VAL DRY-RUN ALLOWANCE (module docstring, conditions 1-3 enforced here; 4-5 by `RunDirs` / `run_marks`)."""
    if SU.locked():
        raise PermissionError(f"{what}: --dry-run-on-val is refused once research/phase4/METHOD_LOCK.json exists (pre-lock dry runs only)")
    if tier != "val" or real_level is not None:
        raise PermissionError(f"{what}: --dry-run-on-val opens the val tier only (no real level, never conf / real_levelc); got tier "
                              f"{tier!r}, real level {real_level!r}")
    if methods_dir is not None and Path(methods_dir).resolve() == LOCKED_METHODS.resolve():
        raise PermissionError(f"{what}: --dry-run-on-val never runs the locked methods package")
    sd = standin_dir_of(methods_dir)
    if sd is None:
        raise PermissionError(f"{what}: --dry-run-on-val needs --methods-dir naming a stand-in package ({', '.join(str(x.relative_to(ROOT)) for x in STANDIN_DIRS)}) "
                              f"or a byte-identical snapshot of one; got {methods_dir!r}")
    ms = [str(m) for m in methods if m]
    bad = [m for m in ms if not is_standin_method(m)]
    if not ms or bad:
        raise PermissionError(f"{what}: --dry-run-on-val runs stand-in methods only; not stand-ins: {bad or '(no method given)'}")
    return {"hidden": False, "lock": {}, "dry_run": True, "dry_run_on_val": True, "tier": "val",
            "stand_in": {"methods_dir": str(methods_dir), "standin_package": sd.relative_to(ROOT).as_posix(), "methods": ms}}


def run_marks(g: dict, tier: str | None, real_level: str | None) -> dict:
    """The run-record fields of condition (5): dry-run flag, the val allowance, the tier, the stand-in."""
    out = {"dry_run": bool(g.get("dry_run", not g.get("hidden"))), "dry_run_on_val": bool(g.get("dry_run_on_val")), "tier": tier,
           "real_level": real_level}
    if g.get("dry_run_on_val"):
        out["stand_in"] = g.get("stand_in")
        out["not_a_result"] = ("DRY RUN on the Level B selection tier with stand-in models, before the lock: not a result; never released, "
                               "never used for any decision")
    return out


def marks_of(record: dict) -> dict:
    """The run-record marks a summary repeats (condition 4 / 5)."""
    return {k: record.get(k) for k in ("dry_run", "dry_run_on_val", "tier", "real_level", "stand_in", "not_a_result") if k in record}


def dry_banner(record: dict) -> list[str]:
    """Markdown banner of a dry-run summary (empty for official runs)."""
    if not record.get("dry_run", not record.get("hidden")):
        return []
    what = "val tier (Level B selection tier), " if record.get("dry_run_on_val") else ""
    return [f"**DRY RUN** ({what}stand-in models, before the lock): not a result; never released, never used for any decision.", ""]


def is_dry_path(p: str | Path) -> bool:
    q = Path(p).resolve()
    return any(q == r.resolve() or r.resolve() in q.parents for r in DRY_ROOTS)


LEDGER = OUT_ROOT / "LEDGER.json"


def ledger_claim(study: str, run_id: str, *, new_run_reason: str | None = None, ledger: Path | None = None) -> dict:
    """Register an OFFICIAL (hidden) run of a post-lock study (goal5 section 70: hidden data are evaluated once; no repeated probing).
    The same run id resumes (infrastructure only); a DIFFERENT run id of a study that already ran is refused unless a reason is given,
    which is logged. Dry runs never claim."""
    led_p = Path(ledger or LEDGER)
    led = load_json(led_p, {"runs": []}) or {"runs": []}
    prior = [r for r in led["runs"] if r["study"] == study]
    mine = [r for r in prior if r["run_id"] == run_id]
    if mine:
        return mine[0]
    if prior and not new_run_reason:
        raise PermissionError(f"the post-lock study {study!r} already ran as {[r['run_id'] for r in prior]}; a new run needs a logged "
                              "reason (--new-run-reason); repeated probing of hidden results is not allowed (goal5 section 70)")
    rec = {"study": study, "run_id": run_id, "started_utc": utc(), "reason": new_run_reason}
    led["runs"].append(rec)
    dump_json(led, led_p)
    return rec


class HiddenRunLog:
    """START row before, DONE (or FAILED) row after a hidden run, in the orchestrator's hidden-evaluation log (the table of the Level C
    driver: time | phase | run | what | detail). A no-op for dry runs."""

    def __init__(self, hidden: bool, study: str, run_id: str, what: str, *, log: Path = HIDDEN_LOG):
        self.hidden, self.study, self.run_id, self.what, self.log = hidden, study, run_id, what, Path(log)
        self.t0 = None

    def _row(self, phase: str, detail: dict) -> None:
        if not self.hidden:
            return
        if not self.log.exists():
            self.log.parent.mkdir(parents=True, exist_ok=True)
            self.log.write_text("# Phase 4 hidden evaluations (causal_state_v1; PROTOCOL.md section 12)\n\nEvery hidden run: START before, "
                                "DONE after.\n\n| time (UTC) | phase | run | what | detail |\n|---|---|---|---|---|\n", encoding="utf-8",
                                newline="\n")
        d = json.dumps(detail, sort_keys=True, default=str).replace("|", "/")
        with open(self.log, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(f"| {utc()} | {phase} | postlock/{self.study}/{self.run_id} | {self.what.replace('|', '/')} | {d[:1500]} |\n")

    def __enter__(self):
        self.t0 = time.time()
        self._row("START", {"study": self.study})
        return self

    def __exit__(self, et, ev, tb):
        wall = round(time.time() - self.t0, 1)
        if et is None:
            self._row("DONE", {"study": self.study, "wall_s": wall})
        else:
            self._row("FAILED", {"study": self.study, "wall_s": wall, "error": f"{et.__name__}: {str(ev)[:200]}"})
        return False


# ================================================================================================================ systems
def custom_tier(study: str, run_id: str, part: str, *, hidden: bool) -> str:
    """Name of a custom tier (a directory under the volumes' data/suites or data/real). A dry run's tiers carry "dry_", so an official
    run can never read items a dry run built (e.g. on the public real systems), whatever run ids are chosen."""
    safe = "".join(c if c.isalnum() else "_" for c in f"{'' if hidden else 'dry_'}{study}_{run_id}_{part}")
    return f"{CUSTOM_PREFIX}{safe}"[:80]


def real_ids(level: str) -> list[str]:
    ints = load_json(REAL_INTERNAL, {}) or {}
    return sorted(ints)


def synthetic_ids(tier: str) -> list[str]:
    p = SU.tier_dirs(tier, SU.SUITES)["base"] / "internal_records.json"
    if not p.exists():
        raise FileNotFoundError(f"{p} is missing: build the {tier} tier first (scripts/p4/build_on_modal.py)")
    return sorted(json.loads(p.read_text(encoding="utf-8")))


def system_paths(sid: str, kind: str, *, tier: str | None = None, real_level: str | None = None) -> dict:
    """Container paths of one system (suites.REMOTE layout). Synthetic: public part of `tier` on the fit volume, held-out part on the
    eval volume. Real: the public real data for fits; the evaluation sets of `real_level` ('public': the public evaluation subset in the
    public part; 'C': the hidden test)."""
    if kind == "synthetic":
        pub_root, held_root = PurePosixPath(SU.REMOTE["fit"]) / "suites", PurePosixPath(SU.REMOTE["eval"]) / "suites"
        return {"kind": kind, "fit_data": str(pub_root / tier / "public" / SU._safe(sid)), "public_root": str(pub_root),
                "public_tier": tier, "heldout_root": str(held_root), "heldout_tier": tier, "part": "eval",
                "internal_path": str(held_root / tier / "internal_records.json"), "tier": tier}
    pub_root, held_root = PurePosixPath(SU.REMOTE["fit"]) / "real", PurePosixPath(SU.REMOTE["eval"]) / "real"
    pt = SU.REAL_TIERS["public"]
    if real_level == "public":
        h_root, h_tier, part = pub_root, pt, "public"
    else:
        h_root, h_tier, part = held_root, SU.REAL_TIERS[real_level], "eval"
    return {"kind": kind, "fit_data": str(pub_root / pt / "public" / SU._safe(sid)), "public_root": str(pub_root), "public_tier": pt,
            "heldout_root": str(h_root), "heldout_tier": h_tier, "part": part, "internal_path": str(held_root / "real_systems_internal.json"),
            "tier": h_tier, "real_level": real_level}


def resolve_systems(tier: str | None, real_level: str | None = None, systems: list[str] | None = None) -> dict[str, dict]:
    """{sid: system_paths(...)} of a synthetic tier and / or a real level, filtered by `systems`."""
    out: dict[str, dict] = {}
    if tier:
        for s in synthetic_ids(tier):
            out[s] = system_paths(s, "synthetic", tier=tier)
    if real_level:
        for s in real_ids(real_level):
            out[s] = system_paths(s, "real", real_level=real_level)
    if systems:
        want = set(systems)
        out = {s: v for s, v in out.items() if s in want}
        missing = sorted(want - set(out))
        if missing:
            raise SystemExit(f"systems not in the selection: {missing[:10]}")
    return out


def plan_records(tier: str | None, real_level: str | None, sids: list[str]) -> dict[str, dict]:
    """{sid: {"pub", "internal"}}: the public and internal records the planners need. Synthetic systems: from the tier's plan made
    on the REFERENCE PLATFORM (data/phase4/suites/<tier>/_plan/jobs.json; the generator's system hashes differ on the development
    host, LOG P4-D32, so records are never recomputed here). Real systems: brainir_causal.systems."""
    out: dict[str, dict] = {}
    want = set(sids)
    if tier:
        jp = SU.tier_dirs(tier, SU.SUITES)["base"] / "_plan" / "jobs.json"
        if not jp.exists():
            raise FileNotFoundError(f"{jp} is missing (the reference-platform plan of the {tier} tier)")
        for j in json.loads(jp.read_text(encoding="utf-8")):
            if j["sid"] in want:
                out[j["sid"]] = {"pub": j["pub"], "internal": j["internal"]}
    if real_level:
        from brainir_causal.systems import load_real_internal, public_view
        ints = load_real_internal()
        for s in sids:
            if s in ints:
                out[s] = {"pub": public_view(ints[s]), "internal": ints[s]}
    missing = sorted(want - set(out))
    if missing:
        raise SystemExit(f"no planning records for {missing[:10]}")
    return out


# ================================================================================================================ jobs
def generator_for(kind: str) -> list | None:
    return [SU.GENERATOR_CONTAINER, GENERATOR_PKG] if kind == "synthetic" else None


ISO_STAGE_ROOT = RUN_BASE / "_iso_stage"


def stage_iso_code() -> Path:
    """An immutable, content-addressed copy of the trusted container code these drivers need (scripts/p4/p4post_iso.py and
    scripts/p4/p4post/), baked at /repo/scripts/p4 (a directory of `isolation.ISO_SCRIPT_DIRS`). Baking the live scripts/p4 would
    include every other script and fail when another process edits one during the image build ("... was modified during build")."""
    src = ROOT / "scripts" / "p4"
    files = [src / "p4post_iso.py"] + sorted(q for q in (src / "p4post").rglob("*.py") if "__pycache__" not in q.parts)
    h = hashlib.sha256()
    for f in files:
        h.update(f.relative_to(src).as_posix().encode())
        h.update(f.read_bytes())
    dst = ISO_STAGE_ROOT / h.hexdigest()[:16]
    if not (dst / "p4post_iso.py").exists():
        tmp = ISO_STAGE_ROOT / f".tmp_{h.hexdigest()[:16]}_{time.time_ns()}"
        for f in files:
            q = tmp / f.relative_to(src)
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_bytes(f.read_bytes())
        try:
            tmp.rename(dst)
        except OSError:                                   # a concurrent driver staged the same content first
            shutil.rmtree(tmp, ignore_errors=True)
    return dst


def extra_dirs(synthetic: bool) -> dict[str, str]:
    """Directories baked into the Modal images: the staged trusted iso code at /repo/scripts/p4 (`stage_iso_code`) and, for synthetic
    systems, the hash-locked generator (iso images require /repo destinations: root-only after the lockdown)."""
    d = {str(stage_iso_code()): SCRIPTS_CONTAINER}
    if synthetic:
        d[SU.GENERATOR_REL] = SU.GENERATOR_CONTAINER
    return d


def eval_job(sid: str, sysd: dict, *, lift: bool = True, n_boot: int = 2000, seed: int = 0, families=None,
             heldout_tier: str | None = None, heldout_root: str | None = None, part: str | None = None, threads: int = 2) -> dict:
    """An evaluation job of `harness.evaluate_job` / `harness.system_context` in the remote layout (optionally on a custom tier)."""
    j = {"sid": sid, "heldout_root": heldout_root or sysd["heldout_root"], "heldout_tier": heldout_tier or sysd["heldout_tier"],
         "public_root": sysd["public_root"], "public_tier": sysd["public_tier"], "internal_path": sysd["internal_path"],
         "store_root": "/tmp/p4m/evalstore", "store_read_roots": [SU.REMOTE["eval_store"], SU.REMOTE["store"]],
         "generator": generator_for(sysd["kind"]), "lift": bool(lift), "n_boot": int(n_boot), "seed": int(seed), "threads": int(threads),
         "part": part or sysd.get("part", "eval")}
    if families:
        j["families"] = list(families)
    return j


def custom_heldout_root(sysd: dict) -> str:
    """Held-out root of the custom tiers of a system's kind (always the EVAL volume)."""
    sub = "suites" if sysd["kind"] == "synthetic" else "real"
    return str(PurePosixPath(SU.REMOTE["eval"]) / sub)


def snapshot_methods(src: Path, dst: Path) -> dict:
    """Copy a methods package (a room's `brainir_causal/methods`, the locked copy, or the stand-in package) into a run directory;
    returns {relative path: sha256} of its .py files."""
    src, dst = Path(src), Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))
    return {p.relative_to(dst).as_posix(): sha256_file(p) for p in sorted(dst.rglob("*.py"))}


class RunDirs:
    """Official (hidden) runs: bulky artefacts RUN_ROOT/<study>/<run_id>, summaries OUT_ROOT/<study>/<run_id>. Dry runs: RUN_DRY_ROOT and
    DRY_ROOT only (condition 4: a dry run never writes an official location)."""

    def __init__(self, study: str, run_id: str, hidden: bool, *, run_root: Path | None = None, out_root: Path | None = None):
        self.study, self.run_id, self.hidden = study, run_id, hidden
        self.run = Path(run_root or (RUN_ROOT if hidden else RUN_DRY_ROOT)) / study / run_id
        self.out = Path(out_root or (OUT_ROOT if hidden else DRY_ROOT)) / study / run_id
        if not hidden and not (is_dry_path(self.run) and is_dry_path(self.out)):
            raise PermissionError(f"a dry run writes only under the dry-run roots {[str(r) for r in DRY_ROOTS]}")
        self.run.mkdir(parents=True, exist_ok=True)
        self.out.mkdir(parents=True, exist_ok=True)

    def variant(self, name: str) -> Path:
        d = self.run / method_key(name)
        d.mkdir(parents=True, exist_ok=True)
        return d


# ================================================================================================================ margins
def margins() -> dict:
    """The calibrated tolerances and suite margins (benchmarks/causal_state_v1/public/tolerances.json), or the provisional values
    (flagged "calibrated": False) while the calibration does not exist. Suite margins fall back to the per-system values (flagged)."""
    from brainir_causal import harness as H
    p = BENCH / "public" / "tolerances.json"
    raw = load_json(p, None)
    if raw is None:
        tol, calibrated = dict(H.PROVISIONAL_TOLERANCES), False
        suite = {}
    else:
        tol, calibrated = dict(raw.get("tolerances", raw)), True
        suite = dict(raw.get("suite_margins") or {})
    for k in ("delta_C_suite", "tau_SMS_suite"):
        if suite.get(k) is None and tol.get(k) is not None:
            suite[k] = tol[k]
    fallback = [k for k in ("delta_C_suite", "tau_SMS_suite") if suite.get(k) is None]
    for k in fallback:
        suite[k] = tol[k.replace("_suite", "")]
    return {"tolerances": tol, "suite": suite, "calibrated": calibrated, "suite_fallback_per_system": fallback, "source": str(p)}


# ================================================================================================================ Modal helpers
def backend(classes: list[str], *, synthetic: bool, app_name: str, max_containers: int = 40):
    """A Backend (ephemeral app) with this package and, for synthetic systems, the generator baked into the images. max_containers
    bounds EACH class (the workspace runs about 100 containers at once; critical-path campaigns share it)."""
    from brainir_causal.p4modal.app import Backend
    be = Backend(classes=classes, max_containers=max_containers, extra_dirs=extra_dirs(synthetic), app_name=app_name)
    be.p4post_max_containers = int(max_containers)          # bounds the jobs in flight of `execute.run_eager`
    return be


def iso_call_payload(role: str, job: dict, key: str, *, model: bytes | None = None, reload=("fit", "eval", "store"),
                     commit=()) -> dict:
    """An ISOLATED job of the iso "call" role (isolation.run_iso_payload): the trusted function p4post_iso:<role> runs in the
    container's driver with the job's transport; the model bytes travel opaque to the model workers. `commit` only for UNPACKED
    classes (packed jobs never write volumes)."""
    p = {"kind": "iso", "role": "call", "target": f"{ISO_TARGET}:{role}", "job": dict(job), "methods_key": key, "reload": list(reload)}
    if model is not None:
        p["models"] = {"model": model}
    if commit:
        p["commit"] = list(commit)
    return p


# ================================================================================================================ large payloads
#: models / outputs above this size never travel inline (Modal's inline limit is 2 MiB; larger payloads are blobs that an isolated,
#: block_network container cannot up- or download; p4post_iso docstring)
INLINE_MAX = 1_500_000
#: INPUT models of iso "call" payloads above this size go through the fit volume (`ModelStager`). Lower than INLINE_MAX because the
#: backend's pre-submission check (`p4modal.app._payload_bytes`, P1, 2026-09-27) estimates the payload's "models" bytes by their JSON
#: repr (about 3.6 x their size): a 1.14 MB model was refused as 4.08 MB (toyC packed smoke). Raise it again once that check counts
#: nested bytes by length.
MODEL_INLINE_MAX = 500_000
MODEL_DIR = "/p4post/models"                         # on the fit volume (content-addressed <sha256>.bin)
MODEL_DIR_CONTAINER = "/fitvol/p4post/models"


def decode_output(val):
    """A trusted container output: decompress p4post_iso.pack_output's {"lzma_pickle": ...} (never a worker's bytes)."""
    if isinstance(val, dict) and isinstance(val.get("lzma_pickle"), (bytes, bytearray)):
        import lzma
        import pickle
        out = pickle.loads(lzma.decompress(val["lzma_pickle"]))
        if isinstance(out, dict) and val.get("dropped"):
            out.setdefault("_transport", {})["dropped"] = list(val["dropped"])
        return out
    return val


class ModelStager:
    """Model bytes for a wave: inline when small, else uploaded (content-addressed, ONE batch) to the fit volume BEFORE the wave's
    containers start; `fetch` downloads a model a volume-writing fit left there (sha256-checked)."""

    def __init__(self, be):
        self.be = be
        self._present: set | None = None

    def present(self) -> set:
        if self._present is None:
            try:
                self._present = {Path(e.path).name for e in self.be.vols["fit"].listdir(MODEL_DIR)}
            except Exception:  # noqa: BLE001 - the directory does not exist yet
                self._present = set()
        return self._present

    def stage_many(self, blobs: list[bytes]) -> list[dict]:
        """[{"inline": bytes} | {"model_path": container path, "model_sha256": sha}] in input order."""
        import io
        out, todo = [], {}
        for b in blobs:
            if len(b) <= MODEL_INLINE_MAX:
                out.append({"inline": b})
                continue
            sha = hashlib.sha256(b).hexdigest()
            if f"{sha}.bin" not in self.present():
                todo[sha] = b
            out.append({"model_path": f"{MODEL_DIR_CONTAINER}/{sha}.bin", "model_sha256": sha})
        if todo:
            with self.be.vols["fit"].batch_upload(force=True) as bu:
                for sha, b in todo.items():
                    bu.put_file(io.BytesIO(b), f"{MODEL_DIR}/{sha}.bin")
            self._present |= {f"{s}.bin" for s in todo}
        return out

    def fetch(self, ref_path: str, sha: str) -> bytes:
        import io
        rel = ref_path[len("/fitvol"):] if ref_path.startswith("/fitvol") else ref_path
        buf = io.BytesIO()
        self.be.vols["fit"].read_file_into_fileobj(rel, buf)
        blob = buf.getvalue()
        if hashlib.sha256(blob).hexdigest() != sha:
            raise RuntimeError(f"model {ref_path}: sha256 mismatch after download")
        return blob


def call_result(r) -> tuple[dict | None, str | None]:
    """(result, error) of a kind "call" job result (remote.run_call: {"result": value} or {"error": ...})."""
    if isinstance(r, BaseException):
        return None, f"{type(r).__name__}: {r}"[:2000]
    if not isinstance(r, dict):
        return None, f"no result: {str(r)[:500]}"
    if "error" in r and "result" not in r:
        return None, (str(r.get("error")) + " | " + str(r.get("stderr_tail", ""))[-1500:])[:3000]
    res = r.get("result")
    if isinstance(res, dict) and res.get("error") and not res.get("ok", True):
        return None, str(res.get("error"))[:3000]
    return res, None


def iso_result(r, key: str = "result") -> tuple[dict | None, str | None]:
    """(value, error) of an iso job result (isolation.run_iso_payload)."""
    if isinstance(r, BaseException):
        return None, f"{type(r).__name__}: {r}"[:2000]
    if not isinstance(r, dict):
        return None, f"no result: {str(r)[:500]}"
    if key in r:
        return r[key], None
    return None, str(r.get("error") or r)[:3000]


def modal_runs_row(study: str, run_id: str, app: str, purpose: str, resources: str, cost: dict | None, notes: str) -> str:
    usd = (cost or {}).get("usd_approx_total")
    return (f"| P3-{study}-{run_id} | {utc()} | {app} ({(cost or {}).get('app_id')}) | {purpose} | {resources} | "
            f"~${usd if usd is not None else '?'} (list price) | {notes} |")
