"""Level C driver library (ORCHESTRATOR SIDE; benchmarks/causal_state_v1/PROTOCOL.md sections 4, 5, 9, 11 and 12; goal5 sections 69-77).
Used by scripts/p4/level_c.py; the container-side functions are in scripts/p4/levelc_remote.py (iso role "call"). Design, guards and
dry-run numbers: research/phase4/LEVEL_C_DRIVER.md.

THE RUN (one process, resumable; every job's result is stored as it arrives and a restarted run skips finished jobs)
  Stage A  hidden data (official runs only, after the method lock): the confirmation tier (3 systems per type, salted) and review G's
           trap tier (salted; its catalog research/phase4/review_g/review_g.py is hashed by the lock) planned on the reference platform
           and the real Level C sets planned locally, then one build job per system; per-system Stage B jobs start as soon as that
           system's build is done (packed classes: after every build).
  Stage B  fits: the locked method on every system with fit seeds 0-4 (seed 0 = the primary fit; 0-4 for 5.11), the 5 bootstrap
           refits of the training interventions (5.10), the leave-one-intervention-out refits (5.13), the leave-one-implementation-out
           shared / adapted / scratch fits and the sharing models (5.14, synthetic implementation groups and unrelated-pair nulls), the
           Level B-fixed baselines (the strongest baseline S, a full-state or ID baseline when one is the fixed bound or comparator, and
           any other baseline asked for), the benchmark references (trusted, once per system; RANDOM-k / PCA-k with the method's k).
  Stage C  evaluation: every metric family of the primary model and of every baseline (`harness.evaluate_job` through model workers);
           5.11 stability; the P_t / P_m - P_t item set (`levelc_remote.same_items`); LOIO and LOImplO item-subset EE; the experiment
           loops of 5.17 (every designer x 3 loop seeds; the magnitude-matched control after the method's own loop) and the evaluation
           of every checkpoint (EE, SMS, k, lift success).
  Stage D  claims (local): per-system verdicts with the frozen tolerances, the Level B-fixed bounds and the refits' k; the primary
           family (H1-H6 x (suite + 3 real full networks), Holm); P_m, P_t, P_m - P_t on one item set and the conclusion with charged
           missing results; real verdicts by lineage; the sensitivity table at both CI ends of every tolerance; 5.12-5.17 summaries;
           the review-G trap evaluation (`trap_evaluation`: descriptive, never part of the suite statistics); a machine-readable
           results bundle.
TRAP SYSTEMS (set "trap") get the verdict stages only (TRAP_STAGES: the primary fit, the 5 bootstrap refits, the baselines, the
references, the evaluation, the same-items row); 5.11 / 5.13 / 5.14 / 5.17 are defined on the confirmation suite and the real systems.

GUARDS: no hidden tier, salt or Level C set is planned, built, read or evaluated unless the method lock verifies (`official_guard`:
METHOD_LOCK.json present, `method_lock_p4.py --check` clean, the lock tag an ancestor of HEAD, LEVEL_B_FIXED.json and the Level C
scripts matching the lock's hashes when it records them). A dry run (`mode="dry"`) maps the confirmation tier to the DEV tier and the
real Level C sets to the real PUBLIC evaluation subset and refuses any job whose payload names a hidden tier (`assert_dry_payloads`);
it has no trap tier (built only after the lock): `--trap-standins` marks dev systems as the trap set (Stage D's trap section on
stand-in results) and `level_c.py trap-probe` loads a DUMMY catalog baked at the catalog's container path (the image layout).
Every official run is logged START before and DONE after in research/phase4/HIDDEN_EVALUATIONS.md, and research/phase4/level_c/
LEDGER.json refuses a second official evaluation run of the same hidden data (goal5 section 70: run once) unless its reason is
logged; resuming the same run id is infrastructure only (finished jobs are never recomputed).
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import heapq
import json
import math
import pickle
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "phase4" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import suites as SU  # noqa: E402

BENCH = ROOT / "benchmarks" / "causal_state_v1"
#: the driver's working area (run directories, the staged iso script / catalog copies): P4_RUN_BASE overrides the Windows default
#: (e.g. a driver in a Linux container: research/phase4/LEVEL_C_DRIVER.md section 9)
RUN_BASE = Path(os.environ.get("P4_RUN_BASE") or "C:/Dev/BrainIR_p4run")
RUN_ROOT = RUN_BASE / "levelc"
OUT_ROOT = ROOT / "research" / "phase4" / "level_c"
HIDDEN_LOG = ROOT / "research" / "phase4" / "HIDDEN_EVALUATIONS.md"
LEDGER = OUT_ROOT / "LEDGER.json"
LEVEL_B_FIXED = ROOT / "research" / "phase4" / "LEVEL_B_FIXED.json"
SELF_AUDIT_CONFIG = ROOT / "research" / "phase4" / "SELF_AUDIT_CONFIG.json"
P3_STANDIN_METHODS = ROOT / "scripts" / "p4" / "standin_methods"
#: the self-audit's comparator roles (research/phase4/POSTLOCK_DRIVERS.md 4.5; scripts/p4/self_audit_p4.py): every role whose source is
#: "baseline:<name>" is a baseline of the Level C run (fits + evaluations), so Q1-Q3, Q14 and the Phase 3 regime row are testable
SELF_AUDIT_ROLES = ("method", "id_reference", "id_baseline", "input_only", "readout_history", "linear_controlled", "full_state_bound",
                    "strongest_baseline", "phase3")
#: the dry run's stand-ins of those comparator baselines (P3's scripts/p4/standin_methods; section 88's Phase 3 method is the real one)
DRY_ROLE_BASELINES = {"id_baseline": "p3stand.refstand:p3stand_idshortcut", "input_only": "p3stand.refstand:p3stand_noeffect",
                      "readout_history": "p3stand.refstand:p3stand_idshortcut", "linear_controlled": "p3stand.refstand:p3stand_fullstate"}
METHOD_LOCK = ROOT / "research" / "phase4" / "METHOD_LOCK.json"
LOCK_TAG = "brainir-causal-state-v1-preblind"
LOCKED_METHODS = ROOT / "phase4" / "src" / "brainir_causal" / "methods"
STANDIN_METHODS = ROOT / "scripts" / "p4" / "levelc_standin" / "methods"
STANDIN_METHOD = "standin.pca_standin:levelc_standin_pca"
FROZEN_V1 = "frozen_brainir_state_v1"
SCRIPTS = ("scripts/p4/level_c.py", "scripts/p4/levelc_lib.py", "scripts/p4/levelc_remote.py")
REMOTE_MODULE = "levelc_remote"
ISO_SCRIPT_CONTAINER = "/repo/scripts/p4"          # isolation.ISO_SCRIPT_DIRS
#: review G's TRAP tier (goal5 sections 41 / 84; synthadapter.TRAP_TIER; LOG P4-D50): hidden and salted, built after the lock like the
#: confirmation tier. Its catalog module (synthadapter.TRAP_CATALOG_REL, hashed by the method lock) is baked ROOT-ONLY at the path
#: synthadapter.trap_catalog_path() resolves in a container, into every image of a run that holds trap systems (the builds, the
#: references, the evaluations construct its systems)
TRAP_TIER = "trap"
TRAP_CATALOG_REL = "research/phase4/review_g/review_g.py"            # synthadapter.TRAP_CATALOG_REL (a test checks they agree)
TRAP_CATALOG_CONTAINER = "/repo/" + str(PurePosixPath(TRAP_CATALOG_REL).parent)
#: the DRY RUN's dummy catalog (NOT review G's traps; `level_c.py trap-probe` bakes it at TRAP_CATALOG_CONTAINER)
DUMMY_TRAP_CATALOG = ROOT / "scripts" / "p4" / "levelc_standin" / "dummy_trap_catalog" / "review_g.py"
#: the stages of a trap system: the per-system verdict (with criterion F's 5 bootstrap refits and the Level B-fixed bounds) and the
#: truth diagnostics. 5.11 stability, 5.13 LOIO, 5.14 sharing and the 5.17 loops are defined on the confirmation suite and the real
#: systems (PROTOCOL 5.11-5.17), not on the trap tier
TRAP_STAGES = ("fit", "refit", "bfit", "beval", "refs", "eval", "calib")


def _stage_file(src: Path, d: Path) -> str:
    """Copy `src` alone into the staging directory `d` (any other file there is removed); returns the sha256 of its bytes."""
    d.mkdir(parents=True, exist_ok=True)
    for f in d.iterdir():
        if f.is_file() and f.name != src.name:
            f.unlink()
    data = src.read_bytes()
    tgt = d / src.name
    if not tgt.exists() or tgt.read_bytes() != data:
        tgt.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def stage_remote_module(dest: Path | None = None, *, trap_catalog: Path | None = None) -> tuple[dict, str]:
    """({repository-relative or absolute dir: container path} for Backend(extra_dirs=...), sha256 of levelc_remote.py): the generator
    and a staging directory holding ONLY levelc_remote.py, baked at /repo/scripts/p4 (the iso "call" script directory). Baking the whole
    scripts/p4 would pick up other drivers' files, and a file edited during the image build aborts the build.
    trap_catalog: a catalog FILE (official: research/phase4/review_g/review_g.py, verified against the lock by the caller; a dry probe:
    DUMMY_TRAP_CATALOG), staged ALONE as review_g.py and baked at TRAP_CATALOG_CONTAINER (root-only in iso images: images.iso_image)."""
    d = Path(dest) if dest else RUN_ROOT.parent / "_iso_scripts"
    sha = _stage_file(ROOT / "scripts" / "p4" / f"{REMOTE_MODULE}.py", d)
    extra = {SU.GENERATOR_REL: SU.GENERATOR_CONTAINER, str(d): ISO_SCRIPT_CONTAINER}
    if trap_catalog is not None:
        src = Path(trap_catalog)
        if src.name != PurePosixPath(TRAP_CATALOG_REL).name:
            raise ValueError(f"a trap catalog file must be named {PurePosixPath(TRAP_CATALOG_REL).name}: {src}")
        official = src.resolve() == (ROOT / TRAP_CATALOG_REL).resolve()
        td = d.parent / ("_trap_catalog" if official else "_trap_catalog_dummy")
        _stage_file(src, td)
        extra[str(td)] = TRAP_CATALOG_CONTAINER
    return extra, sha


EXTRA_DIRS = {SU.GENERATOR_REL: SU.GENERATOR_CONTAINER, "scripts/p4": ISO_SCRIPT_CONTAINER}     # the layout (tests); runs stage

# ---------------------------------------------------------------------------------------------------------------- protocol numbers
FIT_SEEDS = (0, 1, 2, 3, 4)          # METHOD_LOCK "seeds": seed 0 = every primary fit; seeds 0-4 = representation stability (5.11)
N_REFITS = 5                         # bootstrap refits 0-4 of the training interventions, fit seed 0 (5.10)
LOOP_SEEDS = (0, 1, 2)               # 5.17
DESIGNERS = ("own", "random", "uniform", "magnitude_sweep", "greedy_error", "structural", "passive", "fixed", "random_matched")
REF_DESIGNERS = tuple(d for d in DESIGNERS if d not in ("own", "random_matched"))
BUDGET, BUDGET_FULL = 200, 100       # 5.17: real full networks stop at 100 experiments
CKPT_FAMILIES = ("items", "mediation", "truth", "lift")      # 5.17 checkpoint quality: EE, SMS, k, lift success
LIMPO_FRAC, LIMPO_SEED = 0.25, 0
SHARING_CONFIG = {"B": "shared", "C": "partial"}             # 5.14 model A = the independent per-system fits; model D has no
                                                             # CONFIG_KEYS value ('auto' / 'independent' / 'shared' / 'partial')
HIDDEN_TIER_NAMES = ("conf", "val", "trap", "real_levelb", "real_levelc")       # suites.HIDDEN_TIERS / SALTED_TIERS (a test checks)
DRY_TIERS = ("dev", "real_public", "toyC")
STORE_ROOT_C = "/tmp/p4m/evalstore"

#: approximate job durations (s) used only to ORDER the queue (longest first) until measured values exist (`profile_from_run`)
DEFAULT_EXPECTED_S = {
    "build": {"syn": 1800, "mech": 1500, "full": 1800, "toy": 300},
    "fit": {"syn": 300, "mech": 200, "full": 900, "toy": 60}, "refit": {"syn": 300, "mech": 200, "full": 900, "toy": 60},
    "bfit": {"syn": 600, "mech": 300, "full": 1500, "toy": 120}, "refs": {"syn": 900, "mech": 600, "full": 1800, "toy": 120},
    "eval": {"syn": 900, "mech": 600, "full": 2400, "toy": 200}, "beval": {"syn": 900, "mech": 600, "full": 2400, "toy": 200},
    "stability": {"syn": 1200, "mech": 600, "full": 3600, "toy": 200}, "calib": {"syn": 1200, "toy": 300},
    "loio_fit": {"syn": 300, "mech": 200, "full": 900, "toy": 60}, "loio_eval": {"syn": 300, "mech": 200, "full": 900, "toy": 60},
    "limpo_shared": {"syn": 900}, "limpo_adapt": {"syn": 300}, "limpo_scratch": {"syn": 300}, "limpo_eval": {"syn": 400},
    "share_fit": {"syn": 900}, "share_eval": {"syn": 600},
    "loop": {"syn": 1800, "mech": 1200, "full": 5400, "toy": 300}, "ckpt": {"syn": 500, "mech": 400, "full": 1800, "toy": 100},
}
#: the Modal class of each job kind (packed classes: research/phase4/LEVEL_B_EXECUTION.md; `Backend.run_iso_packed` / `run_packed`)
CLASS_OF = {"build": "build", "fit": "iso_pack_fit", "refit": "iso_pack_fit", "bfit": "iso_pack_fit", "loio_fit": "iso_pack_fit",
            "limpo_shared": "iso_pack_fit", "limpo_adapt": "iso_pack_fit", "limpo_scratch": "iso_pack_fit", "share_fit": "iso_pack_fit",
            "refs": "pack_xl", "eval": "iso_pack_eval", "beval": "iso_pack_eval", "stability": "iso_pack_eval", "calib": "iso_pack_eval",
            "loio_eval": "iso_pack_eval", "limpo_eval": "iso_pack_eval", "share_eval": "iso_pack_eval", "ckpt": "iso_pack_eval",
            "loop": "iso_pack_loop"}
GPU_PACKED = "iso_pack_gpu_rtx6000"
#: the UNPACKED equivalents (one job per container; the classes the Level B rounds used before packing), for `Plan.class_map`
UNPACKED = {"iso_pack_fit": "iso_fit_s", "iso_pack_eval": "iso_eval_l", "iso_pack_loop": "iso_loop", "pack_xl": "eval_l",
            GPU_PACKED: "iso_gpu_rtx6000"}
FIT_STAGES = ("fit", "refit", "bfit", "loio_fit", "limpo_shared", "limpo_adapt", "limpo_scratch", "share_fit")
#: model bytes a payload may carry inline (Modal's 2 MiB inline limit on block_network containers, less a margin for the rest of the
#: payload); above it the model travels as a STAGED ref (`Backend.stage_put` / `isolation.read_staged`)
INLINE_MODELS_MAX = 2 * 1024 * 1024 - 256 * 1024


def safe(s: str) -> str:
    return SU._safe(str(s)).replace("/", "_")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(p: Path) -> str:
    b = Path(p).read_bytes()
    if Path(p).suffix in (".py", ".md", ".json", ".txt", ".jsonl"):
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()


# ================================================================================================================ guards
class LevelCRefused(PermissionError):
    pass


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def official_guard(*, need_fixed: bool = True) -> dict:
    """Every check an OFFICIAL Level C action needs (goal5 section 69: nothing hidden before the lock). Raises LevelCRefused."""
    if not METHOD_LOCK.exists():
        raise LevelCRefused("no method lock (research/phase4/METHOD_LOCK.json): hidden data are generated only after the lock")
    lock = json.loads(METHOD_LOCK.read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "scripts" / "p4"))
    import method_lock_p4 as ML
    if ML.check() != 0:
        raise LevelCRefused("method_lock_p4.py --check failed: the locked method or its inputs changed")
    tag = _git("rev-parse", "-q", "--verify", f"refs/tags/{LOCK_TAG}")
    if tag.returncode != 0:
        raise LevelCRefused(f"the lock tag {LOCK_TAG} does not exist")
    anc = _git("merge-base", "--is-ancestor", tag.stdout.strip(), "HEAD")
    if anc.returncode != 0:
        raise LevelCRefused(f"the lock tag {LOCK_TAG} is not an ancestor of HEAD")
    inputs = lock.get("inputs_sha256") or {}
    drivers = lock.get("afterlock_drivers_sha256") or {}
    bad = []
    for rel in (*SCRIPTS, LEVEL_B_FIXED.relative_to(ROOT).as_posix(), TRAP_CATALOG_REL):
        want = inputs.get(rel) or drivers.get(rel)
        if want is not None and (not (ROOT / rel).exists() or sha256_file(ROOT / rel) != want):
            bad.append(rel)
    if bad:
        raise LevelCRefused(f"files changed since the method lock: {bad}")
    if need_fixed and not LEVEL_B_FIXED.exists():
        raise LevelCRefused("research/phase4/LEVEL_B_FIXED.json (the Level B-fixed bounds, S and delta_NI) is missing")
    # review G's trap catalog: part of every official run (the trap tier), so the lock must have fixed it before any hidden evaluation
    if TRAP_CATALOG_REL not in inputs:
        raise LevelCRefused(f"the method lock does not hash review G's trap catalog ({TRAP_CATALOG_REL}): the trap tier cannot run")
    return {"lock_method": lock.get("method"), "lock_sha256": sha256_file(METHOD_LOCK), "tag_commit": tag.stdout.strip(),
            "head": _git("rev-parse", "HEAD").stdout.strip(), "scripts_hashed_by_lock": sorted(r for r in SCRIPTS if r in inputs or r in drivers),
            "level_b_fixed_hashed_by_lock": LEVEL_B_FIXED.relative_to(ROOT).as_posix() in inputs,
            "trap_catalog_sha256": inputs[TRAP_CATALOG_REL]}


TIER_KEYS = ("tier", "heldout_tier", "public_tier")


def assert_dry_payloads(payloads: list) -> None:
    """A dry run never names a hidden tier or the salt in any job (the dev tier, the real public data and the toy tiers only): no tier
    field (TIER_KEYS) with a hidden tier, no path with a hidden tier's directory, no key or string mentioning the salt. ('val' is
    also the name of the public validation SPLIT, so only tier fields and path segments are checked, not every string.)"""
    def walk(o, key=None):
        if isinstance(o, dict):
            for k, v in o.items():
                if "salt" in str(k).lower():
                    raise LevelCRefused(f"dry run: a job carries the key {k!r}")
                walk(v, str(k))
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v, key)
        elif isinstance(o, str):
            if key in TIER_KEYS and o in HIDDEN_TIER_NAMES:
                raise LevelCRefused(f"dry run: a job names the hidden tier {o!r} ({key})")
            segs = o.replace("\\", "/").split("/")
            if len(segs) > 1 and any(s in HIDDEN_TIER_NAMES for s in segs):
                raise LevelCRefused(f"dry run: a job's path names a hidden tier: {o[:200]}")
            if "salt" in o.lower():
                raise LevelCRefused("dry run: a job mentions the salt")
    for p in payloads:
        walk(p)


def log_hidden(phase: str, run_id: str, what: str, detail: dict, log: Path = HIDDEN_LOG) -> None:
    """A START / DONE row of the hidden-evaluation log (PROTOCOL 12)."""
    if not log.exists():
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("# Phase 4 hidden evaluations (causal_state_v1; PROTOCOL.md section 12)\n\nEvery hidden run: START before, DONE "
                       "after (scripts/p4/level_c.py).\n\n| time (UTC) | phase | run | what | detail |\n|---|---|---|---|---|\n",
                       encoding="utf-8", newline="\n")
    d = json.dumps(detail, sort_keys=True, default=str).replace("|", "/")
    with open(log, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"| {now_utc()} | {phase} | {run_id} | {what} | {d[:1500]} |\n")


def ledger_has(run_id: str, stage: str, ledger: Path = LEDGER) -> bool:
    """Whether the ledger already holds this run id for this stage (a resume)."""
    led = json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {"runs": []}
    return any(r["stage"] == stage and r["run_id"] == run_id for r in led["runs"])


def ledger_claim(run_id: str, stage: str, *, new_run_reason: str | None = None, ledger: Path = LEDGER) -> dict:
    """Register an official run of `stage` (goal5 section 70: once per frozen protocol). The same run id resumes; a DIFFERENT run id
    of an already-started stage is refused unless `new_run_reason` is given (then logged)."""
    led = json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {"runs": []}
    prior = [r for r in led["runs"] if r["stage"] == stage]
    mine = [r for r in prior if r["run_id"] == run_id]
    if mine:
        return mine[0]
    if prior and not new_run_reason:
        raise LevelCRefused(f"stage {stage!r} already ran as {[r['run_id'] for r in prior]}; a new run needs a logged reason "
                            "(--new-run-reason), and repeated probing of hidden results is not allowed (goal5 section 70)")
    rec = {"run_id": run_id, "stage": stage, "started_utc": now_utc(), "reason": new_run_reason, "head": _git("rev-parse", "HEAD").stdout.strip()}
    led["runs"].append(rec)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps(led, indent=1) + "\n", encoding="utf-8", newline="\n")
    return rec


# ================================================================================================================ systems
def _real_public() -> dict:
    return json.loads((BENCH / "public" / "systems_real_public.json").read_text(encoding="utf-8"))


def _real_public_records() -> dict:
    d = _real_public()
    return d.get("systems", d) if isinstance(d, dict) else {r["system_id"]: r for r in d}


def real_class(sid: str, pub: dict | None = None) -> str:
    """'full' (a full network) or 'mech' (a candidate mechanism)."""
    mode = (pub or {}).get("mode")
    if mode:
        return "mech" if mode == "mech" else "full"
    return "full" if sid.endswith(":full") else "mech"


@dataclass
class Mode:
    """official: conf + review G's trap tier + real Level C; dry: dev + the real public evaluation subset (+ toyC for the Level C design
    path; no trap tier: it exists only after the lock)."""
    name: str                                       # "official" | "dry"
    syn_tier: str
    real_heldout_tier: str
    real_part: str
    real_heldout_volume: str                        # "eval" | "fit"
    toy_tier: str | None = None
    trap_tier: str | None = None

    @classmethod
    def official(cls) -> Mode:
        return cls("official", "conf", SU.REAL_TIERS["C"], "eval", "eval", trap_tier=TRAP_TIER)

    @classmethod
    def dry(cls, toy: bool = True) -> Mode:
        return cls("dry", "dev", SU.REAL_TIERS["public"], "public", "fit", "toyC" if toy else None)


def system_set(spec: dict) -> str:
    """'suite' (the confirmation suite; a dry run's dev and toy systems stand in for it), 'trap' (review G's trap tier; a dry run's
    --trap-standins) or 'real'."""
    return "real" if spec.get("kind") == "real" else str(spec.get("set") or "suite")


def in_suite(spec: dict) -> bool:
    """A synthetic system of the confirmation suite (P_m, P_t, the primary family, 5.14 / 5.17): never a trap system."""
    return spec.get("kind") == "synthetic" and system_set(spec) == "suite"


def _syn_spec(sid: str, tier: str, internal: dict, truth: dict) -> dict:
    pub_root, held_root = PurePosixPath(SU.REMOTE["fit"]) / "suites", PurePosixPath(SU.REMOTE["eval"]) / "suites"
    tr = truth.get(sid) or {}
    k = tr.get("k")
    toy = tier in ("toy", "toyC")
    return {"sid": sid, "kind": "synthetic", "cls": "toy" if toy else "syn", "tier": tier, "set": "trap" if tier == TRAP_TIER else "suite",
            "expected_verdict": tr.get("expected_verdict"), "trap_grade": tr.get("trap_grade"),
            "fit_data": str(pub_root / tier / "public" / SU._safe(sid)), "public_root": str(pub_root), "public_tier": tier,
            "heldout_root": str(held_root), "heldout_tier": tier, "part": "eval",
            "internal_path": str(held_root / tier / "internal_records.json"), "generator": None if toy else [SU.GENERATOR_CONTAINER, "p4synth"],
            "type": tr.get("type"), "trap": tr.get("trap"), "k_true": k, "d_draw": tr.get("d_draw"),
            "compressible": (None if k is None else str(k) != "none"), "group": tr.get("implementation_group"),
            "group_members": list(tr.get("group_members") or []), "unrelated": list(tr.get("unrelated_systems") or []),
            "families_train": list(((internal.get(sid) or {}).get("split") or {}).get("families_train") or []),
            "n_obs": len((internal.get(sid) or {}).get("observed") or [])}


def real_lineage(pub: dict | None, internal: dict | None) -> str | None:
    """A real system's LINEAGE (PROTOCOL 2.1: the builds of one reconstruction are one lineage; mechanisms are nested in their
    network): the public record's lineage when it is set, else the reconstruction named by the internal record's network without its
    build version (manc_v1.2.1 and manc_v1.2.3 -> "manc"; male-cns_v1.0 -> "male-cns"). The benchmark's public records carry lineage
    null (dry run S3: "real verdicts by lineage" was one group "None"), so this orchestrator-side rule does the grouping."""
    import re
    lin = (internal or {}).get("lineage") or (pub or {}).get("lineage")   # the internal record's explicit lineage first (hidden;
    if lin:                                                                 # the public records keep it null: real systems are blinded)
        return str(lin)
    net = str((internal or {}).get("network") or "")
    return (re.split(r"_v\d", net, maxsplit=1)[0] or None) if net else None


def _real_spec(sid: str, mode: Mode, internal: dict, pubrecs: dict) -> dict:
    pub_root = PurePosixPath(SU.REMOTE["fit"]) / "real"
    held_root = PurePosixPath(SU.REMOTE[mode.real_heldout_volume]) / "real"
    rec = pubrecs.get(sid) or internal.get(sid) or {}
    return {"sid": sid, "kind": "real", "cls": real_class(sid, rec), "tier": mode.real_heldout_tier,
            "fit_data": str(pub_root / SU.REAL_TIERS["public"] / "public" / SU._safe(sid)), "public_root": str(pub_root),
            "public_tier": SU.REAL_TIERS["public"], "heldout_root": str(held_root), "heldout_tier": mode.real_heldout_tier,
            "part": mode.real_part, "internal_path": str(PurePosixPath(SU.REMOTE["eval"]) / "real" / "real_systems_internal.json"),
            "generator": None, "type": None, "trap": None, "k_true": None, "d_draw": None, "compressible": None, "group": None,
            "group_members": [], "unrelated": [], "lineage": real_lineage(pubrecs.get(sid), internal.get(sid)),
            "families_train": list(((internal.get(sid) or {}).get("split") or {}).get("families_train") or []),
            "n_obs": len((internal.get(sid) or {}).get("observed") or [])}


def tier_meta(tier: str) -> tuple[dict, dict]:
    """(internal records, truth summaries) of a synthetic tier from the orchestrator's local copies (written by the builds)."""
    base = SU.tier_dirs(tier, SU.SUITES)["base"]
    ints = json.loads((base / "internal_records.json").read_text(encoding="utf-8"))
    tp = base / "truth" / "systems_truth.json"
    truth = json.loads(tp.read_text(encoding="utf-8")) if tp.exists() else {}
    return ints, truth


def system_specs(mode: Mode, *, systems: list[str] | None = None, include_real: bool = True, toy_meta: tuple | None = None,
                 trap_meta: tuple | None = None, trap_standins: list[str] | None = None) -> dict:
    """{sid: spec} of a Level C run: container paths of the fit data, the held-out part and the internal records, and the
    orchestrator-held facts Stage D needs (type, truth k, d_draw, compressibility, implementation group, lineage, trained families,
    the system set). The official mode adds review G's trap tier (set "trap"); trap_standins (DRY RUN ONLY) marks dev systems as the
    trap set, so the trap plan and Stage D's trap evaluation run on stand-in results before the lock."""
    if mode.name == "official":
        official_guard()
    ints, truth = tier_meta(mode.syn_tier)
    out = {sid: _syn_spec(sid, mode.syn_tier, ints, truth) for sid in sorted(ints)}
    if mode.toy_tier:
        tints, ttruth = toy_meta if toy_meta is not None else tier_meta(mode.toy_tier)
        out.update({sid: _syn_spec(sid, mode.toy_tier, tints, ttruth) for sid in sorted(tints)})
    if mode.trap_tier:
        pints, ptruth = trap_meta if trap_meta is not None else tier_meta(mode.trap_tier)
        clash = sorted(set(pints) & set(out))
        if clash:
            raise ValueError(f"trap system ids clash with the confirmation tier's: {clash}")
        out.update({sid: _syn_spec(sid, mode.trap_tier, pints, ptruth) for sid in sorted(pints)})
    if trap_standins:
        if mode.name != "dry":
            raise LevelCRefused("trap stand-ins exist only in a dry run (the official trap set is review G's tier)")
        for sid in trap_standins:
            if sid not in out or out[sid]["kind"] != "synthetic":
                raise ValueError(f"trap stand-in {sid!r} is not a synthetic system of the dry run")
            out[sid] = {**out[sid], "set": "trap", "trap_standin": True}
    if include_real:
        rint = json.loads((BENCH / "hidden" / "real_systems_internal.json").read_text(encoding="utf-8"))
        pubrecs = _real_public_records()
        out.update({sid: _real_spec(sid, mode, rint, pubrecs) for sid in sorted(rint)})
    if systems:
        keep = set(systems)
        out = {s: v for s, v in out.items() if s in keep}
    return out


def implementation_groups(specs: dict) -> list[dict]:
    """5.14 units: every implementation group with at least 2 members in the run ("group"), and one unrelated-pair NULL per group
    (its first member with its first unrelated system in the run; the correct sharing verdict of a null is "rejected"). Suite systems
    only (a trap system is never a 5.14 unit)."""
    groups: dict[str, list[str]] = {}
    for sid, sp in specs.items():
        if in_suite(sp) and sp.get("group"):
            groups.setdefault(sp["group"], []).append(sid)
    out = []
    for g, members in sorted(groups.items()):
        members = sorted(members)
        if len(members) < 2:
            continue
        out.append({"id": f"grp_{g}", "kind": "group", "members": members})
        first = members[0]
        unrel = [u for u in specs[first].get("unrelated") or [] if u in specs and in_suite(specs[u])]
        if unrel:
            out.append({"id": f"null_{g}", "kind": "null", "members": sorted([first, unrel[0]])})
    return out


def trained_intervention_families(spec: dict) -> list[str]:
    return sorted(f for f in spec.get("families_train") or [] if not str(f).startswith("obs."))


# ================================================================================================================ jobs
@dataclass
class Job:
    id: str
    stage: str
    kind: str                     # "iso" | "trusted"
    cls: str
    sid: str | None
    deps: list[str] = field(default_factory=list)
    soft: list[str] = field(default_factory=list)      # dependencies whose failure does not block this job
    expected_s: float = 60.0
    meta: dict = field(default_factory=dict)


@dataclass
class Plan:
    """Everything a run needs besides the results: the specs, the jobs and the run facts (methods, keys, fixed choices)."""
    run_id: str
    mode: Mode
    specs: dict
    method: str
    limpo_method: str
    baselines: list[str]
    fixed: dict
    described: dict
    methods_key: str | None = None
    budget: int = BUDGET
    loop_seeds: tuple = LOOP_SEEDS
    designers: tuple = DESIGNERS
    fit_seeds: tuple = FIT_SEEDS
    n_refits: int = N_REFITS
    n_boot: int = 2000
    threads: int = 4
    fit_timeout_s: dict = field(default_factory=lambda: {"syn": 900, "mech": 900, "full": 1800, "toy": 900})
    jobs: dict = field(default_factory=dict)
    groups: list = field(default_factory=list)
    run_dir: Path | None = None
    build_jobs: dict = field(default_factory=dict)          # sid -> planned build job (Stage A / the dry run's toy tier)
    class_map: dict = field(default_factory=dict)           # e.g. UNPACKED: run every job kind on its unpacked class
    time_limit_scale: float = 1.0                           # the locked method's cost against the stand-in profile (time_limit_s)

    def cls(self, c: str) -> str:
        return self.class_map.get(c, c)

    def expected(self, stage: str, spec: dict | None) -> float:
        tab = DEFAULT_EXPECTED_S.get(stage) or {}
        c = (spec or {}).get("cls", "syn")
        return float(tab.get(c) or tab.get("syn") or 300)


def fit_cls(plan: Plan, method: str) -> str:
    return GPU_PACKED if (plan.described.get(method) or {}).get("device") == "cuda" else "iso_pack_fit"


def budget_of(spec: dict, plan: Plan) -> int:
    return min(plan.budget, BUDGET_FULL) if (spec["kind"] == "real" and spec["cls"] == "full") else plan.budget


def build_plan(plan: Plan) -> Plan:
    """Fill plan.jobs with every Stage B / C job of the run (ids are stable, so a restarted run finds its finished jobs)."""
    J: dict[str, Job] = {}
    M, M5 = plan.method, plan.limpo_method
    dM, d5 = plan.described.get(M) or {}, plan.described.get(M5) or {}

    def add(j: Job) -> None:
        if j.id in J:
            raise ValueError(f"duplicate job id {j.id}")
        J[j.id] = j

    for sid in plan.build_jobs:
        add(Job(f"build__{safe(sid)}", "build", "trusted", CLASS_OF["build"], sid, [], expected_s=plan.expected("build", plan.specs.get(sid))))
    # FRESHNESS (packed classes, research/phase4/LEVEL_B_EXECUTION.md): a packed container reloads the volumes ONCE, at its start, so
    # no packed job may start before every build has committed (a barrier); unpacked jobs reload per job and stream per system
    from brainir_causal.p4modal.app import CLASSES
    packed = any(CLASSES.get(plan.cls(c), {}).get("slots") for c in ("iso_pack_fit", "iso_pack_eval", "iso_pack_loop", "pack_xl"))
    all_builds = [f"build__{safe(x)}" for x in plan.build_jobs]
    for sid, sp in plan.specs.items():
        s = safe(sid)
        pre = list(all_builds) if packed else ([f"build__{s}"] if sid in plan.build_jobs else [])
        trap = system_set(sp) == "trap"
        for seed in (plan.fit_seeds[:1] if trap else plan.fit_seeds):        # a trap system: the primary fit (seed 0) only
            add(Job(f"fit__{s}__s{seed}", "fit", "iso", fit_cls(plan, M), sid, list(pre), expected_s=plan.expected("fit", sp),
                    meta={"method": M, "seed": seed}))
        for b in range(plan.n_refits):
            add(Job(f"refit__{s}__b{b}", "refit", "iso", fit_cls(plan, M), sid, list(pre), expected_s=plan.expected("refit", sp),
                    meta={"method": M, "seed": 0, "bootstrap": b}))
        for bl in plan.baselines:
            add(Job(f"bfit__{s}__{safe(bl)}", "bfit", "iso", fit_cls(plan, bl), sid, list(pre), expected_s=plan.expected("bfit", sp),
                    meta={"method": bl, "seed": 0}))
            add(Job(f"beval__{s}__{safe(bl)}", "beval", "iso", CLASS_OF["beval"], sid, [f"bfit__{s}__{safe(bl)}"],
                    expected_s=plan.expected("beval", sp), meta={"method": bl}))
        add(Job(f"refs__{s}", "refs", "trusted", CLASS_OF["refs"], sid, list(pre), soft=[f"fit__{s}__s0"],
                expected_s=plan.expected("refs", sp)))
        add(Job(f"eval__{s}", "eval", "iso", CLASS_OF["eval"], sid, [f"fit__{s}__s0"], expected_s=plan.expected("eval", sp)))
        if sp["kind"] == "synthetic" and sp.get("compressible"):
            add(Job(f"calib__{s}", "calib", "iso", CLASS_OF["calib"], sid, [f"fit__{s}__s0"],
                    soft=[f"refit__{s}__b{b}" for b in range(plan.n_refits)], expected_s=plan.expected("calib", sp)))
        if trap:                                            # TRAP_STAGES: no 5.11 / 5.13 / 5.17 jobs (and no 5.14 unit)
            continue
        add(Job(f"stability__{s}", "stability", "iso", CLASS_OF["stability"], sid,
                [], soft=[f"fit__{s}__s{x}" for x in plan.fit_seeds] + [f"refit__{s}__b{b}" for b in range(plan.n_refits)],
                expected_s=plan.expected("stability", sp)))
        for fam in trained_intervention_families(sp):
            f = safe(fam)
            add(Job(f"loio_fit__{s}__{f}", "loio_fit", "iso", fit_cls(plan, M), sid, list(pre), expected_s=plan.expected("loio_fit", sp),
                    meta={"method": M, "family": fam}))
            add(Job(f"loio_eval__{s}__{f}", "loio_eval", "iso", CLASS_OF["loio_eval"], sid, [f"fit__{s}__s0", f"loio_fit__{s}__{f}"],
                    expected_s=plan.expected("loio_eval", sp), meta={"family": fam}))
        designers = [d for d in plan.designers if d != "own" or dM.get("has_designer")]
        if "own" not in designers:
            designers = [d for d in designers if d != "random_matched"]
        for d in designers:
            for ls in plan.loop_seeds:
                deps = list(pre) + ([f"loop__{s}__own__l{ls}"] if d == "random_matched" else [])
                add(Job(f"loop__{s}__{d}__l{ls}", "loop", "iso", CLASS_OF["loop"], sid, deps, expected_s=plan.expected("loop", sp)
                        * budget_of(sp, plan) / BUDGET, meta={"designer": d, "loop_seed": ls, "budget": budget_of(sp, plan)}))
                # checkpoint evaluations are created when the loop's result arrives (their number depends on the loop)
    # 5.14: implementation groups and unrelated-pair nulls (the 5.14 method: the locked method; a dry run may name another)
    plan.groups = implementation_groups(plan.specs)
    sharing = [m for m, v in SHARING_CONFIG.items() if v in (d5.get("supported_sharing") or [])]
    can_adapt = bool(d5.get("supports_adaptation")) and "shared" in (d5.get("supported_sharing") or [])
    for g in plan.groups:
        gid = safe(g["id"])
        members = g["members"]
        a_src = {h: (f"fit__{safe(h)}__s0" if M5 == M else f"bfit__{safe(h)}__{safe(M5)}") for h in members}
        for h in members:
            sh = safe(h)
            spec = plan.specs[h]
            if can_adapt:
                add(Job(f"limpo_shared__{gid}__{sh}", "limpo_shared", "iso", fit_cls(plan, M5), h,
                        [f"build__{safe(x)}" for x in members if x in plan.build_jobs], expected_s=plan.expected("limpo_shared", spec),
                        meta={"method": M5, "group": g["id"], "heldout": h, "systems": [x for x in members if x != h]}))
                add(Job(f"limpo_adapt__{gid}__{sh}", "limpo_adapt", "iso", fit_cls(plan, M5), h, [f"limpo_shared__{gid}__{sh}"],
                        expected_s=plan.expected("limpo_adapt", spec), meta={"method": M5, "group": g["id"], "heldout": h}))
            add(Job(f"limpo_scratch__{gid}__{sh}", "limpo_scratch", "iso", fit_cls(plan, M5), h,
                    [f"build__{sh}"] if h in plan.build_jobs else [], expected_s=plan.expected("limpo_scratch", spec),
                    meta={"method": M5, "group": g["id"], "heldout": h}))
            add(Job(f"limpo_eval__{gid}__{sh}", "limpo_eval", "iso", CLASS_OF["limpo_eval"], h, [],
                    soft=[f"limpo_scratch__{gid}__{sh}"] + ([f"limpo_adapt__{gid}__{sh}"] if can_adapt else []),
                    expected_s=plan.expected("limpo_eval", spec), meta={"group": g["id"], "heldout": h, "adapted": can_adapt}))
        for m in sharing:
            add(Job(f"share_fit__{gid}__{m}", "share_fit", "iso", fit_cls(plan, M5), members[0],
                    [f"build__{safe(x)}" for x in members if x in plan.build_jobs], expected_s=plan.expected("share_fit", plan.specs[members[0]]),
                    meta={"method": M5, "group": g["id"], "model": m, "sharing": SHARING_CONFIG[m], "systems": members}))
        for sid in members:
            add(Job(f"share_eval__{gid}__{safe(sid)}", "share_eval", "iso", CLASS_OF["share_eval"], sid, [],
                    soft=[a_src[sid]] + [f"share_fit__{gid}__{m}" for m in sharing], expected_s=plan.expected("share_eval", plan.specs[sid]),
                    meta={"group": g["id"], "models": ["A", *sharing], "a_source": a_src[sid]}))
        if M5 != M:
            for sid in members:
                if f"bfit__{safe(sid)}__{safe(M5)}" not in J:
                    raise ValueError(f"the 5.14 method {M5} must also be a baseline of the run (its per-system fits are model A)")
    for j in J.values():
        for d in list(j.deps) + list(j.soft):
            if d not in J:
                raise ValueError(f"{j.id}: unknown dependency {d}")
        j.cls = plan.cls(j.cls)
    plan.jobs = J
    return plan


# ================================================================================================================ results on disk
class RunStore:
    """<run_dir>/results/<key>.pkl (every finished job, atomically), models/<key>.bin, loops/<key>/<file>, jobs.jsonl (one line per
    finished attempt: status, wall, container seconds, class, host), plan.json."""

    def __init__(self, run_dir: Path):
        self.dir = Path(run_dir)
        for sub in ("results", "models", "loops"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.be = None                     # set by the Executor: staged artefacts are read / written through Backend.stage_get / stage_put
        rp = self.dir / "refs.json"
        self._refs: dict = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else {}

    # ---- large artefacts STAGED on a volume (P1: a block_network container cannot move more than 2 MiB inline)
    def ref(self, job_id: str) -> dict | None:
        """The staged ref {"stage", "size", "vol"} of a job's model (a staged fit model, a staged checkpoint file), if any."""
        return self._refs.get(job_id)

    def set_ref(self, job_id: str, ref: dict) -> None:
        with self._lock:
            self._refs[job_id] = dict(ref)
            tmp = self.dir / f"refs.{threading.get_ident()}.part"
            tmp.write_text(json.dumps(self._refs, indent=0) + "\n", encoding="utf-8")
            tmp.replace(self.dir / "refs.json")

    def fetch(self, ref: dict) -> bytes:
        if self.be is None:
            raise RuntimeError("no backend to fetch a staged artefact")
        return self.be.stage_get(ref)

    def stage(self, data: bytes) -> dict:
        if self.be is None:
            raise RuntimeError("no backend to stage an artefact")
        return self.be.stage_put(data)

    def path(self, job_id: str) -> Path:
        return self.dir / "results" / f"{job_id}.pkl"

    def done(self, job_id: str) -> bool:
        return self.path(job_id).exists()

    def put(self, job_id: str, res) -> None:
        p = self.path(job_id)
        tmp = p.with_suffix(f".{threading.get_ident()}.part")
        with open(tmp, "wb") as fh:
            pickle.dump(res, fh, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(p)

    def get(self, job_id: str):
        p = self.path(job_id)
        if not p.exists():
            return None
        with open(p, "rb") as fh:
            return pickle.load(fh)

    def model_path(self, job_id: str) -> Path:
        return self.dir / "models" / f"{job_id}.bin"

    def model(self, job_id: str) -> bytes | None:
        p = self.model_path(job_id)
        return p.read_bytes() if p.exists() else None

    def loop_dir(self, job_id: str) -> Path:
        return self.dir / "loops" / job_id

    def log(self, row: dict) -> None:
        with self._lock, open(self.dir / "jobs.jsonl", "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, default=str) + "\n")

    def log_timeout(self, row: dict) -> None:
        with self._lock, open(self.dir / "timeouts.jsonl", "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, default=str) + "\n")

    def timeout_rows(self) -> list[dict]:
        p = self.dir / "timeouts.jsonl"
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []

    def rows(self) -> list[dict]:
        p = self.dir / "jobs.jsonl"
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


#: container-level failures before a job's own code ran (retried on a fresh container, at most `Executor.max_infra_retries` times, and
#: recorded); every other error is the job's own result (a scientific failure: never retried, charged downstream)
INFRA_PATTERNS = ("container lockdown failed", "PackInfraError", "packed child driver", "No such file or directory: '/fitvol/methods/",
                  "not completed after", "no admissible host", "call failed repeatedly on Modal",
                  "InfraFault")         # isolation.InfraFault (a model worker that died twice, ...; P1, 2026-09-27): never the job's own result


#: PER-JOB TIME LIMITS (the executor's OUTER wall on each attempt of a job; research/phase4/LEVEL_C_DRIVER.md section 5).
#: limit = max(TIME_LIMIT_FLOOR_S, TIME_LIMIT_FACTOR x p95(stage, system class) x Plan.time_limit_scale) + the job's INNER limit.
#: INNER limits are the protocol's method limits, enforced inside the container by trusted code: every model call has a per-call
#: timeout (isolation.CALL_TIMEOUT_S; a model load INIT_TIMEOUT_S), a fit its timeout_s, a loop its timeout_s. A method call that HANGS
#: is killed there and the job RETURNS with that call recorded as the method's failure (charged per PROTOCOL: a failed prediction, fit
#: or loop). Because the outer limit adds one inner limit, one hung method call can never trip it: an OUTER timeout means the time went
#: outside any single method call (trusted code, the transport, the container, Modal) and is INFRASTRUCTURE. The first is cancelled
#: and resubmitted once; the second is final ("time limit" with both attempts, attribution "infrastructure"); Stage D charges the
#: missing result per PROTOCOL (never dropped). Every timeout is recorded (<run>/timeouts.jsonl, the job's row).
TIME_LIMIT_FACTOR = 4.0
TIME_LIMIT_FLOOR_S = 1800.0
#: p95 job wall (s, client-side, queueing included) per stage and system class of the PACKED dry runs S3 + D1 (2026-09-27, stand-in
#: method; the locked method's own costs enter through Plan.time_limit_scale); a stage / class without a measurement uses the largest
#: class of its stage, then 2 x DEFAULT_EXPECTED_S. stability "mech": the 10-model projection of the fixed job measured by the diagnostic
#: P2-DIAG1 (570 s per model, about 105 digest-rule worker restarts of 5.3 s each; the S3 attempts never completed)
PROFILE_P95_S = {
    "beval": {"full": 799, "mech": 643, "syn": 1895, "toy": 541}, "bfit": {"full": 656, "mech": 534, "syn": 656, "toy": 296},
    "build": {"toy": 534}, "calib": {"syn": 4108, "toy": 1120},
    "ckpt": {"full": 1448, "mech": 602, "syn": 490, "toy": 1524}, "eval": {"full": 1493, "mech": 1111, "syn": 1732, "toy": 904},
    "fit": {"full": 210, "mech": 177, "syn": 243, "toy": 46}, "limpo_adapt": {"syn": 189}, "limpo_eval": {"syn": 1142},
    "limpo_scratch": {"syn": 487}, "limpo_shared": {"syn": 634}, "loio_eval": {"full": 240, "mech": 391, "syn": 1268, "toy": 634},
    "loio_fit": {"full": 204, "mech": 178, "syn": 330, "toy": 75}, "loop": {"full": 1902, "mech": 1219, "syn": 1973, "toy": 740},
    "refit": {"full": 205, "mech": 173, "syn": 87, "toy": 69}, "refs": {"full": 2214, "mech": 1329, "syn": 3205, "toy": 729},
    "share_eval": {"syn": 1142}, "share_fit": {"syn": 1391}, "stability": {"full": 2712, "mech": 5732, "syn": 1897, "toy": 784},
}
EVAL_STAGES = ("eval", "beval", "ckpt", "stability", "calib", "loio_eval", "limpo_eval", "share_eval")


def profile_p95(stage: str, cls: str) -> float:
    tab = PROFILE_P95_S.get(stage) or {}
    if cls in tab:
        return float(tab[cls])
    if tab:
        return float(max(tab.values()))
    d = DEFAULT_EXPECTED_S.get(stage) or {}
    return 2.0 * float(d.get(cls) or d.get("syn") or 900)


def inner_limit_s(job: Job, plan: Plan) -> float:
    """The job's own method-side limit (see TIME_LIMIT_FLOOR_S): a fit's / loop's timeout_s, one model call (or model load) for an
    evaluation-type job, 0 for trusted jobs without method code (references, builds)."""
    from brainir_causal.isolation import CALL_TIMEOUT_S, INIT_TIMEOUT_S
    sp = plan.specs.get(job.sid) or {"cls": "syn"}
    if job.stage in ("limpo_shared", "share_fit"):
        return _fit_timeout(plan, sp, 2.0)
    if job.stage in FIT_STAGES:
        return _fit_timeout(plan, sp)
    if job.stage == "loop":
        return float(max(900.0, 4 * _fit_timeout(plan, sp)))
    if job.stage in EVAL_STAGES:
        return float(max(CALL_TIMEOUT_S, INIT_TIMEOUT_S))
    return 0.0


def time_limit_s(job: Job, plan: Plan) -> float:
    """The executor's outer wall for one attempt of `job` (TIME_LIMIT_FLOOR_S)."""
    cls = (plan.specs.get(job.sid) or {}).get("cls", "syn")
    base = TIME_LIMIT_FACTOR * profile_p95(job.stage, cls) * float(plan.time_limit_scale)
    return round(max(TIME_LIMIT_FLOOR_S, base) + inner_limit_s(job, plan), 1)


#: a DEAD MODAL CLIENT in this process: every later call fails at once (seen twice on the Windows driver host: WinError 10055, the
#: machine's socket buffers exhausted, killed the client's synchronizer thread). The executor then stops at once, without spending
#: retries or storing the in-flight calls (they run again on the resume), and the CLI exits with EXIT_CLIENT_DIED so a supervisor
#: (`level_c.py run --auto-resume N`) relaunches the run with the same run id
CLIENT_DEAD_PATTERNS = ("Synchronizer thread unexpectedly died", "ClientClosed", "WinError 10055")
EXIT_CLIENT_DIED = 75                   # EX_TEMPFAIL


class ClientDied(RuntimeError):
    pass


def client_dead(e) -> bool:
    """Whether an exception (or its cause / context chain) says this process's Modal client is dead (CLIENT_DEAD_PATTERNS)."""
    seen = 0
    while isinstance(e, BaseException) and seen < 8:
        if any(p in f"{type(e).__name__}: {e}" for p in CLIENT_DEAD_PATTERNS):
            return True
        e = e.__cause__ or e.__context__
        seen += 1
    return False


def infrastructure_error(res) -> str | None:
    """The reason a result is an INFRASTRUCTURE failure (an Exception from the client or Modal, or a container-level error of
    INFRA_PATTERNS), else None."""
    if isinstance(res, BaseException):
        return f"{type(res).__name__}: {res}"
    if isinstance(res, dict):
        err = str(res.get("error") or "")
        if err and any(p in err for p in INFRA_PATTERNS):
            return err
    return None


def job_error(res) -> str | None:
    """The error of a finished job (None when it succeeded): infrastructure (an Exception), a container-level error, or the job's own
    error inside its result."""
    if isinstance(res, BaseException):
        return f"infrastructure: {type(res).__name__}: {res}"[:1500]
    if not isinstance(res, dict):
        return f"unexpected result type {type(res).__name__}"
    if res.get("error"):
        return str(res["error"])[:1500]
    inner = res.get("result")
    if isinstance(inner, dict) and inner.get("error") and not inner.get("result"):
        return str(inner["error"])[:1500]
    return None


# ================================================================================================================ payloads
def sys_ctx(spec: dict, plan: Plan, **extra) -> dict:
    """The system-context keys of `harness.system_context` for one system (container paths)."""
    ctx = {"sid": spec["sid"], "heldout_root": spec["heldout_root"], "heldout_tier": spec["heldout_tier"], "public_root": spec["public_root"],
           "public_tier": spec["public_tier"], "part": spec["part"], "internal_path": spec["internal_path"], "store_root": STORE_ROOT_C,
           "store_read_roots": [SU.REMOTE["eval_store"], SU.REMOTE["store"]], "generator": spec["generator"]}
    ctx.update(extra)
    return ctx


def _fit_timeout(plan: Plan, spec: dict, factor: float = 1.0) -> float:
    return float(plan.fit_timeout_s.get(spec["cls"], 900)) * factor


def fit_side(store: RunStore, job_id: str) -> dict:
    r = store.get(job_id)
    return dict((r or {}).get("side") or {}) if isinstance(r, dict) else {}


def fit_k(store: RunStore, job_id: str, sid: str):
    k = ((fit_side(store, job_id).get("info") or {}).get("k") or {}).get(sid)
    return None if k is None else int(k)


def refit_ks(store: RunStore, plan: Plan, sid: str) -> list:
    """Criterion F's k list at Level C: the 5 bootstrap refits' k (None = a missing or failed refit; PROTOCOL 5.10)."""
    return [fit_k(store, f"refit__{safe(sid)}__b{b}", sid) for b in range(plan.n_refits)]


def model_arg(store: RunStore, src_id: str, *, force_ref: bool = False):
    """A model for a payload: its staged ref when it was staged (a large fit output), else its bytes; a model above the inline limit
    (or any model when force_ref) is staged first (`Backend.stage_put`). None when the model does not exist."""
    ref = store.ref(src_id)
    if ref is not None:
        return dict(ref)
    blob = store.model(src_id)
    if blob is None:
        return None
    if (force_ref or len(blob) > INLINE_MODELS_MAX) and store.be is not None:
        ref = store.stage(blob)
        store.set_ref(src_id, ref)
        return dict(ref)
    return blob


def iso_model(store: RunStore, src_id: str) -> dict | None:
    """{"model": bytes} or {"model_ref": ref} for an iso "eval" payload (None: no model)."""
    m = model_arg(store, src_id)
    if m is None:
        return None
    return {"model_ref": m} if isinstance(m, dict) else {"model": m}


def call_models(store: RunStore, sources: dict) -> dict:
    """{name: bytes | staged ref} for an iso "call" payload (levelc_remote resolves refs): inline while the models together stay under
    the inline limit, else every model travels as a ref. Missing models are left out."""
    sizes = {}
    for name, src in sources.items():
        if store.ref(src) is not None:
            sizes[name] = 0
        else:
            b = store.model_path(src)
            if b.exists():
                sizes[name] = b.stat().st_size
    force = sum(sizes.values()) > INLINE_MODELS_MAX
    out = {}
    for name in sizes:
        m = model_arg(store, sources[name], force_ref=force)
        if m is not None:
            out[name] = m
    return out


def payload_for(job: Job, plan: Plan, store: RunStore) -> dict | None:
    """The payload of a job whose dependencies are finished (None: the job cannot run, e.g. a model it needs is missing). A "call"
    payload whose models travel as staged refs lists them under "input_refs" (the packed freshness check; an eval payload's model_ref is
    checked by itself)."""
    p = _payload_for(job, plan, store)
    if isinstance(p, dict) and p.get("role") == "call":
        refs = [dict(v) for v in (p.get("models") or {}).values() if isinstance(v, dict) and "stage" in v]
        if refs:
            p["input_refs"] = refs
    return p


def _payload_for(job: Job, plan: Plan, store: RunStore) -> dict | None:
    sp = plan.specs.get(job.sid) if job.sid else None
    key = plan.methods_key
    iso = {"methods_key": key, "reload": ["fit", "eval", "store"]}
    st = job.stage
    if st == "build":
        return {"target": "brainir_causal.suites:build_system_job", "args": [plan.build_jobs[job.sid]], "timeout_s": 12 * 3600,
                "threads": 1, "reload": ["fit", "eval", "store"], "commit": ["fit", "eval", "store"]}
    if st in ("fit", "refit", "bfit"):
        j = {"method": job.meta["method"], "systems": [job.sid], "data": [sp["fit_data"]], "seed": int(job.meta.get("seed", 0)),
             "config": {}, "threads": plan.threads, "timeout_s": _fit_timeout(plan, sp)}
        if st == "refit":
            j["bootstrap"] = int(job.meta["bootstrap"])
        return {"role": "fit", "job": j, "methods_key": key, "reload": ["fit"]}
    if st in ("limpo_shared", "share_fit"):
        systems = list(job.meta["systems"])
        cfg = {"sharing": job.meta.get("sharing", "shared")}
        j = {"method": job.meta["method"], "systems": systems, "data": [plan.specs[x]["fit_data"] for x in systems], "seed": 0,
             "config": cfg, "threads": plan.threads, "timeout_s": _fit_timeout(plan, sp, 2.0)}
        return {"role": "fit", "job": j, "methods_key": key, "reload": ["fit"]}
    if st in ("loio_fit", "limpo_adapt", "limpo_scratch"):
        sel = ({"kind": "loio", "family": job.meta["family"]} if st == "loio_fit" else {"kind": "limpo", "frac": LIMPO_FRAC, "seed": LIMPO_SEED})
        j = {"method": job.meta["method"], "systems": [job.sid], "data": [sp["fit_data"]], "seed": 0, "config": {}, "select": sel,
             "threads": plan.threads, "timeout_s": _fit_timeout(plan, sp)}
        models = {}
        if st == "limpo_adapt":
            models = call_models(store, {"adapt_from": job.deps[0]})
            if "adapt_from" not in models:
                return None
        return {"role": "call", "target": f"{REMOTE_MODULE}:fit_records", "job": j, "models": models, "methods_key": key, "reload": ["fit"]}
    if st == "refs":
        j = sys_ctx(sp, plan, lift=False, n_boot=plan.n_boot, seed=0, ref_names=None, return_results=True,
                    ref_cache=f"/tmp/p4m/refcache/{sp['heldout_tier']}", k=fit_k(store, f"fit__{safe(job.sid)}__s0", job.sid))
        j.pop("ref_names")
        return {"target": "brainir_causal.harness:references_job", "args": [j], "timeout_s": 6 * 3600, "threads": plan.threads,
                "reload": ["fit", "eval", "store"]}
    if st in ("eval", "beval"):
        src = f"fit__{safe(job.sid)}__s0" if st == "eval" else f"bfit__{safe(job.sid)}__{safe(job.meta['method'])}"
        m = iso_model(store, src)
        if m is None:
            return None
        j = sys_ctx(sp, plan, lift=True, n_boot=plan.n_boot, seed=0, threads=2, call_timeout_s=900)
        return {"role": "eval", "job": j, **m, **iso}
    if st == "ckpt":
        m = iso_model(store, job.id)
        if m is None:
            return None
        j = sys_ctx(sp, plan, lift=True, n_boot=plan.n_boot, seed=0, threads=2, call_timeout_s=900, families=list(CKPT_FAMILIES))
        return {"role": "eval", "job": j, **m, **iso}
    if st == "stability":
        srcs = {f"s{x}": f"fit__{safe(job.sid)}__s{x}" for x in plan.fit_seeds}
        srcs.update({f"b{bb}": f"refit__{safe(job.sid)}__b{bb}" for bb in range(plan.n_refits)})
        order = list(srcs)
        models = call_models(store, srcs)
        if len(models) < 2:
            return None
        j = sys_ctx(sp, plan, model_order=order, threads=2, n_times=8)
        return {"role": "call", "target": f"{REMOTE_MODULE}:stability", "job": j, "models": models, **iso}
    if st == "calib":
        models = call_models(store, {"method": f"fit__{safe(job.sid)}__s0"})
        if "method" not in models:
            return None
        j = {"sid": job.sid, "tier_root": sp["heldout_root"], "tier": sp["heldout_tier"], "public_root": sp["public_root"],
             "k_refits": refit_ks(store, plan, job.sid), "n_boot": plan.n_boot, "seed": 0, "level": "C", "threads": 2,
             "k_true": sp.get("k_true"), "d_draw": sp.get("d_draw")}          # compactness given the truth (PROTOCOL 5.10)
        return {"role": "call", "target": f"{REMOTE_MODULE}:same_items", "job": j, "models": models, **iso}
    if st == "loio_eval":
        models = call_models(store, {"full": job.deps[0], "loio": job.deps[1]})
        if len(models) < 2:
            return None
        j = sys_ctx(sp, plan, model_order=["full", "loio"], items={"families": [job.meta["family"]]}, n_boot=plan.n_boot, seed=0, threads=2)
        return {"role": "call", "target": f"{REMOTE_MODULE}:eval_items", "job": j, "models": models, **iso}
    if st == "limpo_eval":
        gid, sh = safe(job.meta["group"]), safe(job.sid)
        srcs = {"scratch": f"limpo_scratch__{gid}__{sh}"}
        if job.meta.get("adapted"):
            srcs["adapted"] = f"limpo_adapt__{gid}__{sh}"
        models = call_models(store, srcs)
        if not models:
            return None
        j = sys_ctx(sp, plan, model_order=["adapted", "scratch"], items={"roles": ["near", "far", "hidden"]}, n_boot=plan.n_boot, seed=0,
                    threads=2, mediation=True)
        return {"role": "call", "target": f"{REMOTE_MODULE}:eval_items", "job": j, "models": models, **iso}
    if st == "share_eval":
        gid = safe(job.meta["group"])
        srcs = {"A": job.meta["a_source"], **{m: f"share_fit__{gid}__{m}" for m in job.meta["models"][1:]}}
        models = call_models(store, srcs)
        if not models:
            return None
        j = sys_ctx(sp, plan, model_order=list(job.meta["models"]), items={"roles": ["near", "far", "hidden"]}, n_boot=plan.n_boot, seed=0,
                    threads=2, mediation=True)
        return {"role": "call", "target": f"{REMOTE_MODULE}:eval_items", "job": j, "models": models, **iso}
    if st == "loop":
        d, ls = job.meta["designer"], int(job.meta["loop_seed"])
        from brainir_causal.loop import CHECKPOINTS, CHECKPOINTS_FULL
        cps = list(CHECKPOINTS_FULL if (sp["kind"] == "real" and sp["cls"] == "full") else CHECKPOINTS)
        cps = [c for c in cps if c <= int(job.meta["budget"])] or [int(job.meta["budget"])]
        j = sys_ctx(sp, plan, method=plan.method, designer=d, data=[sp["fit_data"]], budget=int(job.meta["budget"]), seed=ls, config={},
                    store_root="/tmp/p4m/loopstore", checkpoints=cps, threads=plan.threads, timeout_s=float(max(900.0, 4 * _fit_timeout(plan, sp))))
        p = {"role": "loop", "job": j, **iso}
        if d == "random_matched":
            own = store.loop_dir(f"loop__{safe(job.sid)}__own__l{ls}")
            files = {n: (own / n).read_bytes() for n in ("experiments.jsonl", "loop_record.json") if (own / n).exists()}
            if "experiments.jsonl" not in files:
                return None
            p["profile_files"] = files
        return p
    raise ValueError(f"no payload rule for stage {st}")


def unwrap(res):
    """The job's own output: iso "call" results are {"result": <fn output>, "iso": ...}; eval {"result": evaluation, ...}."""
    return res.get("result") if isinstance(res, dict) and isinstance(res.get("result"), dict) else res


def collect(job: Job, res, plan: Plan, store: RunStore) -> list[Job]:
    """Store a finished job (always: the result, with model bytes and loop files moved to their own files) and return the jobs it
    creates (the checkpoint evaluations of a loop)."""
    new: list[Job] = []
    if isinstance(res, BaseException):
        store.put(job.id, {"error": job_error(res), "infrastructure": True})
        return new
    if job_error(res):
        store.put(job.id, res)
        return new
    if job.stage in FIT_STAGES:
        body = res if job.stage in ("fit", "refit", "bfit", "limpo_shared", "share_fit") else unwrap(res)
        res_small = dict(res)
        if isinstance(body, dict) and isinstance(body.get("model_ref"), dict):
            # a STAGED model (above the inline limit): keep the ref for later payloads and download a local copy
            store.set_ref(job.id, body["model_ref"])
            store.model_path(job.id).write_bytes(store.fetch(body["model_ref"]))
        elif isinstance(body, dict) and isinstance(body.get("model"), bytes):
            store.model_path(job.id).write_bytes(body["model"])
            tag = f"<{len(body['model'])} bytes: models/{job.id}.bin>"
            if "model" in res_small:
                res_small["model"] = tag
            elif isinstance(res_small.get("result"), dict):
                res_small["result"] = {**res_small["result"], "model": tag}
        store.put(job.id, res_small)
        return new
    if isinstance(res, dict) and isinstance(res.get("result_ref"), dict):
        # a STAGED evaluation record: the trusted container driver's pickle of `harness.evaluate_job`'s output
        res = {**{k: v for k, v in res.items() if k != "result_ref"}, "result": pickle.loads(store.fetch(res["result_ref"])),
               "result_was_staged": dict(res["result_ref"])}
    if job.stage != "loop":
        store.put(job.id, res)
        return new
    if job.stage == "loop":
        ld = store.loop_dir(job.id)
        ld.mkdir(parents=True, exist_ok=True)
        files = dict(res.get("files") or {})
        refs = dict(res.get("file_refs") or {})
        for name, ref in refs.items():                   # STAGED files (a large checkpoint model): download, remember the ref
            files[name] = store.fetch(ref)
        for name, blob in files.items():
            (ld / Path(name).name).write_bytes(blob)
        rec = res.get("loop_record") or {}
        sp = plan.specs[job.sid]
        for e in rec.get("checkpoints") or []:
            b = int(e["budget"])
            fname = f"ckpt_{b:04d}.pkl"
            cid = f"ckpt__{safe(job.sid)}__{job.meta['designer']}__l{job.meta['loop_seed']}__b{b}"
            if fname in files and isinstance(files[fname], bytes):
                store.model_path(cid).write_bytes(files[fname])
            if fname in refs:
                store.set_ref(cid, refs[fname])
            new.append(Job(cid, "ckpt", "iso", plan.cls(CLASS_OF["ckpt"]), job.sid, [job.id], expected_s=plan.expected("ckpt", sp),
                           meta={"designer": job.meta["designer"], "loop_seed": job.meta["loop_seed"], "budget": b, "model_file": fname,
                                 "saved": fname in files}))
        store.put(job.id, {k: v for k, v in res.items() if k not in ("files", "file_refs")} | {"files": sorted(files), "staged_files": sorted(refs)})
    return new


# ================================================================================================================ executor
class Executor:
    """A dependency-driven, longest-first scheduler over Modal classes (ORCHESTRATOR SIDE).

    Each job is submitted to its class as soon as its dependencies are finished (a synchronous `Function.remote.aio` invocation on the
    executor's single event-loop thread; the container code path of `Backend.run_iso_packed` / `run_packed`: remote.dispatch -> run_iso
    / run_call, a packed slot when the class is packed), up to `caps[cls]` jobs in flight per class; among ready jobs the longest
    expected one goes first. ONE scheduler thread submits and finalises, polling local futures only. (One Modal map and one thread per
    job exhausted the Windows socket buffers at about 170 concurrent calls, WinError 10055; `Function.spawn` is an async invocation with
    an 8 KiB inline limit, which block_network containers cannot exceed: dry run S3.) A host-gate refusal is re-spawned at once; an INFRASTRUCTURE failure
    (`infrastructure_error`) is re-spawned at most `max_infra_retries` times and recorded; a job's own failure is its result (charged
    downstream, never retried). Finished jobs are stored (RunStore) and skipped on a restart."""

    def __init__(self, be, plan: Plan, store: RunStore, *, caps: dict, dry: bool, progress_s: float = 60.0, max_infra_retries: int = 2,
                 poll_threads: int = 8, idle_s: float = 3.0, max_refusals: int = 400, time_limits: bool = True,
                 retry_timeouts: bool = False, limit_fn=None):
        self.be, self.plan, self.store = be, plan, store
        store.be = be
        self.caps = dict(caps)
        self.dry = dry
        self.progress_s = progress_s
        self.max_infra_retries = max_infra_retries
        self.poll_threads = int(poll_threads)
        self.idle_s = float(idle_s)
        self.max_refusals = int(max_refusals)
        self.status: dict[str, str] = {}
        self.inflight: dict[str, int] = {}
        self.pending: dict[str, dict] = {}
        self.t0 = time.time()
        self.refusals = 0
        self.stale = 0
        self.timeouts = 0
        self.time_limits = bool(time_limits)
        self.retry_timeouts = bool(retry_timeouts)
        self.limit_fn = limit_fn or time_limit_s          # (job, plan) -> the outer wall of one attempt (s)

    def _slots(self, cls: str) -> int:
        from brainir_causal.p4modal.app import CLASSES
        return int(CLASSES[cls].get("slots") or 1)

    def _spawn(self, job: Job, payload: dict):
        """Submit one call: a SYNCHRONOUS invocation (`Function.remote.aio`) scheduled on the executor's event-loop thread; returns a
        concurrent.futures.Future. Not `Function.spawn`: an ASYNC invocation's inline limit is 8 KiB (modal MAX_ASYNC_OBJECT_SIZE_BYTES),
        so on a block_network container every output above 8 KiB would go through the blob store and fail (dry run S3); a synchronous
        invocation has the 2 MiB limit P1's staging is built around. One loop thread carries every call (no thread or socket per job)."""
        import asyncio
        import uuid
        p = dict(payload, kind="iso" if job.kind == "iso" else "call", __tag=job.id, job_id=uuid.uuid4().hex)
        return asyncio.run_coroutine_threadsafe(self._invoke(self.be.fns[job.cls], p), self._loop)

    @staticmethod
    async def _invoke(fn, p):
        remote = fn.remote
        aio = getattr(remote, "aio", None)
        if aio is not None:
            return await aio(p)
        import asyncio
        return await asyncio.get_running_loop().run_in_executor(None, remote, p)

    @staticmethod
    def _poll(rec: dict):
        """(result, None) | (None, "pending") | (None, exception) of a submitted call (a local future: no network call)."""
        f = rec["fc"]
        if not f.done():
            return None, "pending"
        try:
            return f.result(), None
        except BaseException as e:  # noqa: BLE001 - a failed call (an infrastructure failure unless it is the job's own result)
            return None, e

    def _start_loop(self) -> None:
        import asyncio
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True, name="levelc-calls")
        self._loop_thread.start()

    def _stop_loop(self) -> None:
        with contextlib.suppress(Exception):
            self._loop.call_soon_threadsafe(self._loop.stop)

    def _start(self, job: Job, payload: dict) -> None:
        rec = {"job": job, "payload": payload, "t0": time.time(), "attempts": 1, "refusals": 0, "stale": 0, "infra": [], "timeouts": [],
               "limit_s": float(self.limit_fn(job, self.plan)) if self.time_limits else None}
        try:
            self._submit(rec)
        except Exception as e:  # noqa: BLE001 - a failed spawn is an infrastructure failure of the client
            rec["fc"] = None
            rec["spawn_error"] = e
        self.pending[job.id] = rec

    def _submit(self, rec: dict) -> None:
        """(Re)submit a job's call; its attempt clock (the time limit) starts now."""
        rec["t_attempt"] = time.time()
        rec["fc"] = self._spawn(rec["job"], rec["payload"])

    def _timed_out(self, rec: dict) -> bool:
        return bool(self.time_limits and rec.get("limit_s") and rec.get("fc") is not None and not rec["fc"].done()
                    and time.time() - rec.get("t_attempt", time.time()) > float(rec["limit_s"]))

    def _timeout(self, jid: str) -> bool:
        """An attempt over its time limit: cancel the call and record it; resubmit ONCE, and the second timeout is final
        (infrastructure; the attribution rule is at TIME_LIMIT_FLOOR_S). True when the job left the pending set."""
        rec = self.pending[jid]
        job = rec["job"]
        with contextlib.suppress(Exception):
            rec["fc"].cancel()
        t = {"attempt": rec["attempts"], "wall_s": round(time.time() - rec["t_attempt"], 1), "limit_s": rec["limit_s"], "utc": now_utc()}
        rec["timeouts"].append(t)
        self.timeouts += 1
        final = len(rec["timeouts"]) >= 2
        self.store.log_timeout({"id": jid, "stage": job.stage, "sid": job.sid, "cls": job.cls, **t,
                                "action": "final: infrastructure" if final else "cancelled and resubmitted"})
        if not final:
            rec["attempts"] += 1
            try:
                self._submit(rec)
            except Exception as e:  # noqa: BLE001
                rec["fc"], rec["spawn_error"] = None, e
            return False
        del self.pending[jid]
        self._finish(rec, {"error": f"time limit: no result within {rec['limit_s']:.0f} s in 2 attempts (infrastructure)",
                           "infrastructure": True, "time_limit": {"final": True, "attribution": "infrastructure",
                                                                  "limit_s": rec["limit_s"], "timeouts": list(rec["timeouts"])}})
        return True

    def _finish(self, rec: dict, res) -> None:
        job = rec["job"]
        if rec["infra"] and isinstance(res, dict):
            res = dict(res, infrastructure_retries=rec["infra"])
        if isinstance(res, dict) and res.get("error") and infrastructure_error(res):
            res = dict(res, infrastructure=True)
        err = job_error(res)
        new: list[Job] = []
        try:
            new = collect(job, res, self.plan, self.store)
        except Exception as e:  # noqa: BLE001 - a storage failure is recorded
            if client_dead(e):          # a staged artefact could not be fetched: nothing stored, the job runs again on the resume
                raise ClientDied(f"collect {job.id}: {type(e).__name__}: {e}") from e
            err = f"collect: {type(e).__name__}: {e}"
            # never the job's own (scientific) failure: flagged as infrastructure, so a restarted run computes it again
            self.store.put(job.id, {"error": err, "infrastructure": True, "traceback": traceback.format_exc()[-2000:]})
        cws = float(res.get("container_wall_s") or 0.0) if isinstance(res, dict) else 0.0
        from brainir_causal.p4modal.app import usd_per_s
        self.store.log({"id": job.id, "stage": job.stage, "sid": job.sid, "cls": job.cls, "status": "error" if err else "ok", "error": err,
                        "attempts": rec["attempts"], "refusals": rec["refusals"], "stale_refusals": rec["stale"],
                        "timeouts": rec.get("timeouts") or [], "limit_s": rec.get("limit_s"),
                        "time_limit_final": bool(isinstance(res, dict) and (res.get("time_limit") or {}).get("final")),
                        "wall_s": round(time.time() - rec["t0"], 1),
                        "container_wall_s": round(cws, 1), "expected_s": job.expected_s,
                        "usd_approx": round(cws * usd_per_s(job.cls) / self._slots(job.cls), 4),
                        "host": ((res.get("__host__") or {}).get("model") if isinstance(res, dict) else None),
                        "peak_mb": res.get("peak_container_mb") if isinstance(res, dict) else None, "finished_utc": now_utc()})
        self.status[job.id] = "error" if err else "ok"
        self.inflight[job.cls] -= 1
        for nj in new:
            self.plan.jobs.setdefault(nj.id, nj)

    def _state(self, job: Job) -> str:
        """'ready' | 'wait' | 'blocked' for a job not yet started."""
        for d in job.deps:
            s = self.status.get(d)
            if s in (None, "running"):
                return "wait"
            if s != "ok":
                return "blocked"
        for d in job.soft:
            if self.status.get(d) in (None, "running"):
                return "wait"
        return "ready"

    def _handle(self, jid: str, res, why) -> bool:
        """Process one polled call; True when the call left the pending set."""
        rec = self.pending[jid]
        if why == "pending":
            return False
        if isinstance(why, BaseException) and client_dead(why):
            raise ClientDied(f"{jid}: {type(why).__name__}: {why}") from why
        if why is None and isinstance(res, dict) and res.get("__refused__"):
            if res.get("stale_staging"):
                # a WARM packed container could not see a staged input committed after its start-up reload: it drains, and a fresh
                # container picks the job up (P1's freshness rule); re-submitted like a host-gate refusal, at most MAX_STALE times
                from brainir_causal.p4modal.app import MAX_STALE
                rec["stale"] += 1
                self.stale += 1
                if rec["stale"] <= MAX_STALE:
                    self._submit(rec)
                    return False
                msg = f"staged input {res.get('stale_staging')} not visible after {rec['stale']} fresh containers"
            else:
                rec["refusals"] += 1
                self.refusals += 1
                if rec["refusals"] < self.max_refusals:
                    self._submit(rec)
                    return False
                msg = f"no admissible host after {rec['refusals']} refusals"
            # a bound reached is final: an error result, not another infrastructure retry
            del self.pending[jid]
            self._finish(rec, {"error": f"infrastructure (bounded): {msg}", "infrastructure": True})
            return True
        infra = infrastructure_error(why if why is not None else res)
        fatal_timeout = why is not None and "FunctionTimeout" in type(why).__name__        # the class timeout: the job's own failure
        if infra and not fatal_timeout and len(rec["infra"]) < self.max_infra_retries:
            rec["infra"].append(infra[:300])
            rec["attempts"] += 1
            try:
                self._submit(rec)
            except Exception as e:  # noqa: BLE001
                rec["fc"], rec["spawn_error"] = None, e
            return False
        del self.pending[jid]
        self._finish(rec, why if why is not None else res)
        return True

    def run(self, only: set[str] | None = None) -> dict:
        """Run every job (or the jobs in `only` and whatever they need) until nothing is left. A job stored as an INFRASTRUCTURE failure
        (never a scientific one) is run again on a restart."""
        J = self.plan.jobs
        for jid in [j for j in J if J[j].stage == "loop"]:          # the checkpoint jobs of finished loops first
            r = self.store.get(jid) if self.store.done(jid) else None
            if r is not None and not job_error(r):
                for nj in collect_resume(J[jid], r, self.plan, self.store):
                    J.setdefault(nj.id, nj)
        for jid in list(J):
            if self.store.done(jid):
                r = self.store.get(jid)
                if isinstance(r, dict) and r.get("infrastructure") and (self.retry_timeouts or not (r.get("time_limit") or {}).get("final")):
                    self.store.log({"id": jid, "stage": J[jid].stage, "sid": J[jid].sid, "status": "rerun",
                                    "error": f"re-running a stored infrastructure failure: {str(r.get('error'))[:300]}", "finished_utc": now_utc()})
                    continue
                self.status[jid] = "error" if job_error(r) else "ok"
        last = 0.0
        self._start_loop()
        try:
            while True:
                progressed = False
                heap: list = []
                for jid, j in list(J.items()):
                    if jid in self.status or (only is not None and not self._needed(jid, only)):
                        continue
                    st = self._state(j)
                    if st == "blocked":
                        self.status[jid] = "skipped"
                        self.store.log({"id": jid, "stage": j.stage, "sid": j.sid, "status": "skipped",
                                        "error": "a required dependency failed", "finished_utc": now_utc()})
                        progressed = True
                    elif st == "ready":
                        heapq.heappush(heap, (-j.expected_s, jid))
                while heap:
                    _neg, jid = heapq.heappop(heap)
                    j = J[jid]
                    if self.inflight.get(j.cls, 0) >= self.caps.get(j.cls, 8):
                        continue
                    self.status[jid] = "running"
                    self.inflight[j.cls] = self.inflight.get(j.cls, 0) + 1
                    progressed = True
                    try:
                        payload = payload_for(j, self.plan, self.store)
                        if payload is not None and self.dry:
                            assert_dry_payloads([payload])
                        err = "a model the job needs is missing"
                    except Exception as e:  # noqa: BLE001 - a payload that cannot be built is the job's failure
                        if client_dead(e):      # staging an input model needs the client
                            raise ClientDied(f"payload {jid}: {type(e).__name__}: {e}") from e
                        payload, err = None, f"payload: {type(e).__name__}: {e}"
                    if payload is None:
                        self.status[jid] = "skipped"
                        self.inflight[j.cls] -= 1
                        self.store.log({"id": jid, "stage": j.stage, "sid": j.sid, "status": "skipped", "error": err,
                                        "finished_utc": now_utc()})
                        continue
                    self._start(j, payload)
                # calls whose spawn failed count as an infrastructure failure of that attempt
                for jid, rec in list(self.pending.items()):
                    if rec.get("fc") is None:
                        e = rec.pop("spawn_error", RuntimeError("spawn failed"))
                        progressed |= self._handle(jid, None, e)
                for jid in [jid for jid, rec in self.pending.items() if rec.get("fc") is not None]:
                    if self._timed_out(self.pending[jid]):
                        progressed |= self._timeout(jid)
                        continue
                    res, why = self._poll(self.pending[jid])
                    progressed |= self._handle(jid, res, why)
                if time.time() - last > self.progress_s:
                    last = time.time()
                    self.print_progress()
                left = [jid for jid in J if jid not in self.status and (only is None or self._needed(jid, only))]
                if not self.pending and not left:
                    break
                if not progressed:
                    time.sleep(self.idle_s)
        except ClientDied as e:
            self.interrupted(e)
            raise
        finally:
            self._stop_loop()
        self.print_progress()
        return dict(self.status)

    def interrupted(self, e: BaseException) -> dict:
        """Record a dead client (<run dir>/interruptions.jsonl): the calls in flight, which are NOT stored (a resume runs them again)."""
        rec = {"utc": now_utc(), "elapsed_s": round(time.time() - self.t0, 1), "error": f"{type(e).__name__}: {e}"[:1000],
               "in_flight_not_stored": sorted(self.pending), "n_done": sum(1 for s in self.status.values() if s in ("ok", "error"))}
        with open(self.store.dir / "interruptions.jsonl", "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(rec) + "\n")
        with contextlib.suppress(Exception):
            self.print_progress()
        print(f"[levelc {self.plan.run_id}] MODAL CLIENT DIED ({rec['error'][:300]}): {len(rec['in_flight_not_stored'])} calls in flight "
              f"are not stored and run again on the resume", flush=True)
        return rec

    def _needed(self, jid: str, only: set[str]) -> bool:
        return jid in only or any(jid in self._closure(o) for o in only)

    def _closure(self, jid: str, _memo: dict = {}) -> set:  # noqa: B006 - per-process memo of dependency closures
        if jid in _memo:
            return _memo[jid]
        j = self.plan.jobs.get(jid)
        out = set()
        if j is not None:
            for d in list(j.deps) + list(j.soft):
                out.add(d)
                out |= self._closure(d)
        _memo[jid] = out
        return out

    def print_progress(self) -> None:
        by: dict[str, dict] = {}
        for jid, j in self.plan.jobs.items():
            s = self.status.get(jid, "pending")
            by.setdefault(j.stage, {}).setdefault(s, 0)
            by[j.stage][s] += 1
        cost = sum(float(r.get("usd_approx") or 0.0) for r in self.store.rows())
        print(f"[levelc {self.plan.run_id}] {time.time() - self.t0:7.0f} s  in flight {dict(self.inflight)}  refusals {self.refusals}  "
              f"stale {self.stale}  timeouts {self.timeouts}  "
              f"cost ~${cost:.2f}  " + "  ".join(f"{st}:{ '/'.join(f'{k}={v}' for k, v in sorted(d.items()))}" for st, d in sorted(by.items())),
              flush=True)


def collect_resume(job: Job, res, plan: Plan, store: RunStore) -> list[Job]:
    """On a restart: the checkpoint jobs of a finished loop (its files are already on disk)."""
    rec = (res or {}).get("loop_record") or {}
    files = set((res or {}).get("files") or [])
    sp = plan.specs[job.sid]
    out = []
    for e in rec.get("checkpoints") or []:
        b = int(e["budget"])
        fname = f"ckpt_{b:04d}.pkl"
        cid = f"ckpt__{safe(job.sid)}__{job.meta['designer']}__l{job.meta['loop_seed']}__b{b}"
        out.append(Job(cid, "ckpt", "iso", plan.cls(CLASS_OF["ckpt"]), job.sid, [job.id], expected_s=plan.expected("ckpt", sp),
                       meta={"designer": job.meta["designer"], "loop_seed": job.meta["loop_seed"], "budget": b, "model_file": fname,
                             "saved": fname in files}))
    return out


# ================================================================================================================ Stage D helpers
def _res(store: RunStore, job_id: str):
    r = store.get(job_id)
    return None if (r is None or job_error(r)) else r


def evaluation(store: RunStore, job_id: str) -> dict | None:
    """{"sid", "kind", "result", "truth_k", "truth_d_draw", "truth_noncompressible"} of an eval job (None when missing / failed)."""
    r = _res(store, job_id)
    ev = unwrap(r) if r is not None else None
    return ev if isinstance(ev, dict) and ev.get("result") is not None else None


def refs_results(store: RunStore, sid: str) -> tuple[dict, dict]:
    r = _res(store, f"refs__{safe(sid)}")
    out = unwrap(r) if r is not None else None
    if not isinstance(out, dict):
        return {}, {}
    return dict(out.get("results") or {}), {k: out.get(k) for k in ("truth_k", "truth_d_draw", "truth_noncompressible", "kind", "errors")}


def bound_effects(choice: str, sid: str, rr: dict, store: RunStore):
    """The effects (with units) of a fixed bound / comparator: 'ref:<name>' or 'baseline:<method>' (its seed-0 fit)."""
    from brainir_causal import harness as H
    kind, name = choice.split(":", 1)
    if kind == "ref":
        return H.verdict_effects(rr.get(name))
    ev = evaluation(store, f"beval__{safe(sid)}__{safe(name)}")
    return H.verdict_effects((ev or {}).get("result"))


def fixed_choice(fixed: dict, key: str, sid: str) -> str:
    v = fixed.get(key) or {}
    if isinstance(v, str):
        return v
    return (v.get("per_system") or {}).get(sid) or v.get("default") or {"full_state_bound": "ref:full_state", "id_comparator": "ref:id_shortcut"}[key]


def loop_rows(plan: Plan, store: RunStore) -> list[dict]:
    """Evaluated checkpoints {"system", "designer", "loop_seed", "budget", "EE", "SMS", "k_consistent", "k_correct", "lift_success",
    costs} (a failed checkpoint evaluation: EE NaN, charged by `loop.checkpoint_grid`)."""
    from brainir_causal.loop import CHECKPOINTS, CHECKPOINTS_FULL
    rows = []
    # a loop that failed (or never ran) has no checkpoint jobs: its planned checkpoints are rows with EE NaN, so
    # `loop.checkpoint_grid` charges them (review E, M7: never dropped)
    for jid, j in plan.jobs.items():
        if j.stage != "loop" or _res(store, jid) is not None:
            continue
        sp = plan.specs[j.sid]
        cps = CHECKPOINTS_FULL if (sp["kind"] == "real" and sp["cls"] == "full") else CHECKPOINTS
        for b in [c for c in cps if c <= int(j.meta["budget"])] or [int(j.meta["budget"])]:
            rows.append({"system": j.sid, "designer": j.meta["designer"], "loop_seed": int(j.meta["loop_seed"]), "budget": int(b),
                         "EE": float("nan"), "SMS": float("nan"), "k_consistent": None, "k_correct": None, "lift_success": None,
                         "evaluated": False, "loop_failed": True})
    for jid, j in plan.jobs.items():
        if j.stage != "ckpt":
            continue
        loop = _res(store, j.deps[0]) or {}
        entry = next((e for e in (loop.get("loop_record") or {}).get("checkpoints") or [] if int(e["budget"]) == int(j.meta["budget"])), {})
        ev = evaluation(store, jid)
        res = (ev or {}).get("result") or {}
        eff = ((res.get("items") or {}).get("effects") or {})
        dim = ((res.get("truth") or {}).get("dimension") or {})
        led = entry.get("ledger") or {}
        mb = entry.get("magnitude_budget") or {}
        d = j.meta["designer"]
        row = {"system": j.sid, "designer": d, "loop_seed": int(j.meta["loop_seed"]), "budget": int(j.meta["budget"]),
               "EE": float((eff.get("EE_cb_medium") or {}).get("point", float("nan"))) if ev else float("nan"),
               "SMS": float(((res.get("mediation") or {}).get("SMS") or {}).get("point", float("nan"))) if ev else float("nan"),
               "k_consistent": dim.get("k_consistent"), "k_correct": dim.get("k_correct"),
               "lift_success": (res.get("lift") or {}).get("success_rate") if ev else None,
               "sim_calls": _sum_nested(led, "sim_calls"), "simulated_s": _sum_nested(led, "simulated_s"),
               "learner_cpu_s": entry.get("learner_cpu_s"), "kick_magnitude": _sum_nested(mb, "kick_magnitude"),
               "current_dose": _sum_nested(mb, "current_dose"), "evaluated": ev is not None}
        rows.append(row)
    return rows


RULE_COMPARATORS = ("random", "fixed")          # PROTOCOL 5.17 rule (i): the two arms (own vs random, own vs fixed)
MATCHED_CONTROL = "random_matched"


def charge_loop_rows(rows: list[dict], *, own: str = "own", comparators: tuple = RULE_COMPARATORS, matched: str | None = MATCHED_CONTROL,
                     metric: str = "EE") -> tuple[list[dict], dict]:
    """PROTOCOL 5.17 (pre-registered, P4-D56): "A failed or missing loop of a system is charged at the worse of the two arms'
    comparator values, never dropped." Applied cell by cell (system, budget, loop seed) BEFORE `loop.active_success` / `loop.curves`,
    whose own charging would give a failed own cell MISSING_EE and EXCLUDE a system with a charged comparator:
      - a failed own cell            = the WORSE (higher EE) of the two arms' comparator values at the cell (random, fixed);
      - a failed comparator cell     = the LOWER of the own value and the other comparator values at the cell (random, fixed or the
                                       magnitude-matched control): charging a comparator must never favour the method, and the system
                                       must not be dropped;
      - a cell where no arm has a value: MISSING_EE for every failed arm (difference zero; the system stays).
    Failed = a non-finite value (a failed evaluation, or a failed / never-run loop: `loop_rows`). The other designers are descriptive
    (curves) and keep `loop.checkpoint_grid`'s charge. Returns (rows, record of the charged cells)."""
    import numpy as np

    from brainir_causal.loop import MISSING_EE
    arms = (own, *comparators, *((matched,) if matched else ()))
    cell: dict = {}
    for r in rows:
        v = r.get(metric)
        v = float(v) if v is not None and np.isfinite(float(v)) else float("nan")
        cell.setdefault((r["system"], int(r["budget"]), int(r.get("loop_seed", 0))), {})[r["designer"]] = v
    out, charged = [], {"own": 0, "comparator": 0, "all_arms_failed": 0, "by_pair": {}}
    for r in rows:
        v = r.get(metric)
        d = r["designer"]
        if d not in arms or (v is not None and np.isfinite(float(v))):
            out.append(r)
            continue
        vals = cell.get((r["system"], int(r["budget"]), int(r.get("loop_seed", 0)))) or {}
        if d == own:
            cand = [vals[c] for c in comparators if c in vals and np.isfinite(vals[c])]
            new, kind = (max(cand), "own") if cand else (MISSING_EE, "all_arms_failed")
        else:
            cand = [vals[c] for c in (own, *comparators) if c != d and c in vals and np.isfinite(vals[c])]
            new, kind = (min(cand), "comparator") if cand else (MISSING_EE, "all_arms_failed")
        charged[kind] += 1
        key = f"{r['system']}|{d}"
        charged["by_pair"][key] = charged["by_pair"].get(key, 0) + 1
        out.append({**r, metric: float(new), "charged": kind})
    return out, charged


def _sum_nested(d, key: str):
    """The value of `key` in a (possibly per-system nested) accounting record, summed over systems; None when absent."""
    if not isinstance(d, dict):
        return None
    if key in d and isinstance(d[key], (int, float)):
        return float(d[key])
    vals = [_sum_nested(v, key) for v in d.values() if isinstance(v, dict)]
    vals = [v for v in vals if v is not None]
    return float(sum(vals)) if vals else None


def system_verdict_of(v: dict | None) -> dict:
    """The `verdict.system_verdict` dict (criteria, category, failed, missing, ...) of a per-system row or an assembled verdict. A row's
    "verdict" is `harness.assemble_verdict(...)["verdict"]` = {"metrics", "verdict": {"category", ...}, "bounds", ...}, which nests the
    system verdict ONCE MORE (dry run D1: reading "category" one level up gave every system and baseline None); an error verdict and a
    bare system verdict carry "category" themselves."""
    ver = (v or {}).get("verdict") or {}
    if not isinstance(ver, dict):
        return {}
    if "category" in ver or "error" in ver:
        return ver
    inner = ver.get("verdict")
    return inner if isinstance(inner, dict) else {}


def category_of(v: dict | None) -> str | None:
    """The verdict category of a per-system row or an assembled verdict (`system_verdict_of`)."""
    return system_verdict_of(v).get("category")


_cat = category_of


def levelb_drop(round_dir: Path | None, method: str, per: dict, specs: dict) -> dict | None:
    """PROTOCOL 11 (review E, M6): the Level B -> Level C drop of the selected method. Level B = its seed-averaged verdict EE per system
    in the FINAL Level B round (<method>.json; optimistic: selected on it); Level C = its primary-fit EE here. Real systems are the
    same systems (fresh items): the per-system difference; synthetic: the medians over the validation and the confirmation suite."""
    import numpy as np
    if round_dir is None:
        return None
    p = Path(round_dir) / f"{method.replace(':', '__').replace('/', '_')}.json"
    if not p.exists():
        return {"error": f"{p.name} not in {round_dir}"}
    r = json.loads(p.read_text(encoding="utf-8"))
    b_ee: dict = {}
    for sid, v in (r.get("per_system") or {}).items():
        vals = [float((((sd or {}).get("verdict") or {}).get("metrics") or {}).get("EE", {}).get("point", 10.0) or 10.0)
                for sd in (v.get("seeds") or {}).values()]
        if vals:
            b_ee[sid] = (float(np.mean(vals)), v.get("kind"))
    c_ee = {s: ((((row.get("verdict") or {}).get("metrics") or {}).get("EE") or {}).get("point")) for s, row in per.items()}
    real = {s: {"level_b": b_ee[s][0], "level_c": c_ee.get(s), "drop": (None if c_ee.get(s) is None else float(c_ee[s]) - b_ee[s][0])}
            for s in b_ee if s in specs and specs[s]["kind"] == "real"}
    syn_b = [v for v, k in b_ee.values() if k == "synthetic"]
    syn_c = [float(c_ee[s]) for s, sp in specs.items() if in_suite(sp) and c_ee.get(s) is not None]
    return {"round": r.get("round") or Path(round_dir).name, "real_per_system": real,
            "synthetic_median_ee": {"validation_level_b": float(np.median(syn_b)) if syn_b else None,
                                    "confirmation_level_c": float(np.median(syn_c)) if syn_c else None},
            "note": "Level B values are optimistic (selection on the validation suite); real verdicts come from systems also used in "
                    "selection (fresh items)"}


#: the outcome of one trap system (`trap_outcome`), in reporting order
TRAP_OUTCOMES = ("handled", "declared_correct", "claim_partial", "no_claim", "false_alarm", "fooled", "missing")


def trap_outcome(category: str | None, k_true, dimension: dict | None) -> tuple[str, str]:
    """(outcome, reason) of one trap system from the method's verdict category, the truth's k ("none": no compact causal state) and
    the truth family's dimension record (`evaluate_truth.eval_dimension_truth`). DESCRIPTIVE (goal5 sections 41 / 84, criterion 33;
    no new threshold):
      handled           SUPPORTED with k consistent with the truth (k_true <= k <= k_true + d_draw)
      declared_correct  "no compact causal state" declared on a trap without one (the honest verdict there)
      claim_partial     PARTIAL with k consistent or of unknown consistency, or SUPPORTED with unknown consistency
      no_claim          UNSUPPORTED (no claim: not fooled, not handled)
      false_alarm       "no compact causal state" declared on a trap that has one
      fooled            a compact-state CLAIM (SUPPORTED or PARTIAL) on a trap without a compact causal state, or with k inconsistent
                        with the truth
      missing           no verdict (charged: never counted as handled)
    A truth without k counts as "none" (as `eval_dimension_truth` does)."""
    from brainir_causal import verdict as V
    if category is None:
        return "missing", "no evaluation of the primary fit"
    none = k_true is None or str(k_true) == "none"
    dim = dimension if isinstance(dimension, dict) else {}
    if category == V.DECLARED:
        return ("declared_correct", "declared no compact causal state; the truth has none") if none else \
            ("false_alarm", f"declared no compact causal state; the truth has k = {k_true}")
    if category in V.AT_LEAST_PARTIAL:
        if none:
            return "fooled", f"{category} on a trap without a compact causal state"
        kc = dim.get("k_consistent")
        if kc is False:
            return "fooled", (f"{category} with k = {dim.get('k_model')}, inconsistent with k_true = {k_true} "
                              f"(d_draw {dim.get('d_draw')})")
        if category == V.SUPPORTED and kc is True:
            return "handled", f"supported with k = {dim.get('k_model')} consistent with k_true = {k_true}"
        return "claim_partial", f"{category}; k consistency {kc}"
    return "no_claim", str(category)


def trap_evaluation(plan: Plan, per: dict, ts_cats: dict) -> dict:
    """Review G's trap tier (goal5 sections 41 / 84; criterion 33), DESCRIPTIVE: per trap system the method's verdict, its k against
    the truth, the truth family's diagnostics (k consistency, latent recovery, z_obs capture), the true-state reference's category on
    the items it supports (is the trap solvable on these items), the baselines' categories, the references' EE, the expected (honest)
    verdict of the truth and the outcome (`trap_outcome`); counts by outcome and by trap label. Never pooled into the suite's
    statistics (P_m, P_t, the primary family, 5.14, 5.17). A dry run's --trap-standins are flagged "standin"."""
    rows: dict = {}
    for sid, sp in sorted(plan.specs.items()):
        if system_set(sp) != "trap":
            continue
        row = per.get(sid) or {}
        ver = system_verdict_of(row)
        cat = category_of(row)
        truth = (row.get("families") or {}).get("truth") or {}
        dim = truth.get("dimension") if isinstance(truth.get("dimension"), dict) else {}
        lat = truth.get("latent_recovery") if isinstance(truth.get("latent_recovery"), dict) else {}
        outcome, why = trap_outcome(cat, sp.get("k_true"), dim)
        rows[sid] = {"trap": sp.get("trap"), "trap_grade": sp.get("trap_grade"), "type": sp.get("type"), "k_true": sp.get("k_true"),
                     "expected_verdict": sp.get("expected_verdict"), "standin": bool(sp.get("trap_standin")), "category": cat,
                     "outcome": outcome, "reason": why, "failed_criteria": ver.get("failed"), "missing_criteria": ver.get("missing"),
                     "k_model": dim.get("k_model"), "k_refits": row.get("k_refits"), "k_consistent": dim.get("k_consistent"),
                     "k_correct": dim.get("k_correct"), "latent_recovery": lat.get("recovery"),
                     "zobs_capture_r2_exposed_from_z": lat.get("zobs_capture_r2_exposed_from_z"),
                     "true_state_category_same_items": ts_cats.get(sid),
                     "references_EE": {n: (v or {}).get("EE") for n, v in (row.get("references") or {}).items()},
                     "baselines": {b: (v or {}).get("category") for b, v in (row.get("baselines") or {}).items()}}
    counts = {o: sum(1 for r in rows.values() if r["outcome"] == o) for o in TRAP_OUTCOMES}
    by_label: dict = {}
    for r in rows.values():
        d = by_label.setdefault(str(r["trap"]), {})
        d[r["outcome"]] = d.get(r["outcome"], 0) + 1
    n = len(rows)
    return {"per_system": rows,
            "summary": {"n_traps": n, "counts": counts, "by_label": by_label,
                        "fooled_fraction": (counts["fooled"] / n) if n else None,
                        "handled_or_declared_correct": counts["handled"] + counts["declared_correct"],
                        "missing_systems": sorted(s for s, r in rows.items() if r["outcome"] == "missing"),
                        "standins": bool(any(r["standin"] for r in rows.values()))},
            "rule": ("descriptive (`levelc_lib.trap_outcome`): a SUPPORTED or PARTIAL claim on a trap without a compact causal state, or "
                     "with k inconsistent with the truth, is 'fooled'; SUPPORTED with consistent k is 'handled'; a correct declaration "
                     "of no compact causal state is 'declared_correct'; a missing verdict is charged as 'missing'")}


def stage_d(plan: Plan, store: RunStore, *, tolerances_path: Path | None = None, calibration_path: Path | None = None,
            n_boot: int = 2000, levelb_round: Path | None = None) -> dict:
    """PROTOCOL 9 / 11 claims from the run's results (ORCHESTRATOR SIDE; frozen functions only). Returns the results bundle."""
    import numpy as np

    from brainir_causal import calibrate as CAL
    from brainir_causal import evaluate_transfer as ET
    from brainir_causal import harness as H
    from brainir_causal import loop as LP
    from brainir_causal import verdict as V
    t0 = time.time()
    tol, calibrated = H.tolerances_or_provisional(tolerances_path)
    tol_d = tol.as_dict()
    calp = Path(calibration_path) if calibration_path else BENCH / "calibration.json"
    cal = json.loads(calp.read_text(encoding="utf-8")) if calp.exists() else None
    capped = bool(cal is not None and cal.get("attainable") is False)
    fixed = plan.fixed
    per: dict = {}
    metrics_for_sens: dict = {}
    calib_rows = []
    primary_values = {h: {} for h in V.HYPOTHESES}
    networks: dict = {}
    for sid, sp in sorted(plan.specs.items()):
        s = safe(sid)
        ev = evaluation(store, f"eval__{s}")
        rr, rmeta = refs_results(store, sid)
        ks = refit_ks(store, plan, sid)
        fb = bound_effects(fixed_choice(fixed, "full_state_bound", sid), sid, rr, store)
        idc = bound_effects(fixed_choice(fixed, "id_comparator", sid), sid, rr, store)
        row: dict = {"kind": sp["kind"], "class": sp["cls"], "set": system_set(sp), "type": sp.get("type"), "lineage": sp.get("lineage"),
                     "k_refits": ks, "bounds": {"full_state_bound": fixed_choice(fixed, "full_state_bound", sid),
                                "id_comparator": fixed_choice(fixed, "id_comparator", sid)},
                     "missing_bound_effects": [n for n, e in (("full_state_bound", fb), ("id_comparator", idc)) if e is None]}
        if ev is None:
            row["verdict"] = {"error": "no evaluation of the primary fit", "category": None}
        else:
            res = ev["result"]
            ver = H.system_verdict_for(res, {"results": rr}, tol, fullbound_eff=fb, idshortcut_eff=idc, k_values=ks, level="C",
                                       truth_noncompressible=ev.get("truth_noncompressible"), n_boot=n_boot, seed=0)
            av = H.assemble_verdict(ev, {"results": rr}, tol, calibrated=calibrated, fullbound_eff=fb, idshortcut_eff=idc, k_refits=ks,
                                    level="C", fit_compute=fit_side(store, f"fit__{s}__s0").get("compute"), n_boot=n_boot)
            row["verdict"] = H.public_view(av["verdict"])
            row["selection_values"] = av["selection"]
            metrics_for_sens[sid] = (ver.get("metrics"), bool(res.get("compact_judged", True)))
            pub = H.public_view(res)
            row["families"] = {k: pub.get(k) for k in ("truth", "lift", "capacity", "micro", "bisimulation", "closure", "mediation")}
            items = pub.get("items") or {}
            row["families"]["items"] = {k: items.get(k) for k in ("ood", "composition", "calibration", "observational")}
            row["families"]["effects"] = {k: (items.get("effects") or {}).get(k) for k in ("EE_cb_medium", "EE_medium", "by_shift_kind",
                                                                                           "by_family", "n_items", "n_abstained")}
            row["isolation"] = (res.get("isolation") or {}).get("worker_restarts")
            # primary-family statistics (PROTOCOL 11): per-system estimates of the six hypotheses
            s_eff = bound_effects(f"baseline:{fixed.get('strongest_baseline')}", sid, rr, store) if fixed.get("strongest_baseline") else None
            eff_m = H.verdict_effects(res)
            if eff_m is not None:
                est = V.primary_estimates(eff_m, eff_id=idc, eff_fb=fb, eff_s=s_eff, mediation=res.get("mediation"), n_boot=n_boot, seed=0)
                row["primary_statistics"] = {h: (None if e is None else {"point": float(e.point), "ci95": [float(x) for x in e.ci95]})
                                             for h, e in est.items()}
                if in_suite(sp) and sp.get("compressible"):
                    for h, e in est.items():
                        primary_values[h][sid] = float(e.point) if e is not None and np.isfinite(e.point) else float("nan")
                if sp["kind"] == "real" and sp["cls"] == "full":
                    networks[sid] = est
            row["missing_primary_comparators"] = [n for n, e in (("id", idc), ("full_state_bound", fb), ("strongest_baseline", s_eff)) if e is None]
        # baselines (descriptive; the strongest baseline enters H6)
        row["baselines"] = {}
        for bl in plan.baselines:
            bev = evaluation(store, f"beval__{s}__{safe(bl)}")
            if bev is None:
                row["baselines"][bl] = {"error": "no evaluation"}
                continue
            bver = H.assemble_verdict(bev, {"results": rr}, tol, calibrated=calibrated, fullbound_eff=fb, idshortcut_eff=idc,
                                      k_refits=None, level="C", n_boot=n_boot)
            row["baselines"][bl] = {"category": _cat(bver), "EE": ((bver.get("verdict") or {}).get("metrics") or {}).get("EE")}
        # references (descriptive verdicts on all verdict items; P_t uses the calibration item set below)
        row["references"] = {n: {"EE": ((((r or {}).get("items") or {}).get("effects") or {}).get("EE_cb_medium") or {}).get("point")}
                             for n, r in rr.items()}
        row["reference_errors"] = rmeta.get("errors")
        trap = system_set(sp) == "trap"
        stab = None if trap else unwrap(_res(store, f"stability__{s}"))
        row["stability"] = ({"not_applicable": "5.11 is defined on the confirmation suite and the real systems (TRAP_STAGES)"} if trap else
                            H.public_view({k: v for k, v in (stab or {}).items() if k != "pairs"}) if stab else {"error": "missing"})
        c = unwrap(_res(store, f"calib__{s}"))
        if isinstance(c, dict) and c.get("sid"):
            calib_rows.append(c)
            row["same_items"] = {"n_supported_items": c.get("n_supported_items"), "abstention_share": c.get("abstention_share"),
                                 "errors": c.get("errors"), "loader": c.get("loader")}
        # 5.13
        full_u, lo_u, famof = {}, {}, {}
        for fam in ([] if trap else trained_intervention_families(sp)):
            le = unwrap(_res(store, f"loio_eval__{s}__{safe(fam)}"))
            if not isinstance(le, dict):
                lo_u.setdefault(fam, {})
                continue
            fm = (le.get("models") or {}).get("full") or {}
            lm = (le.get("models") or {}).get("loio") or {}
            full_u.update({k: tuple(v) for k, v in (fm.get("units") or {}).items()})
            lo_u[fam] = {k: tuple(v) for k, v in (lm.get("units") or {}).items()}
            famof.update(fm.get("families") or {})
        if trained_intervention_families(sp) and not trap:
            row["loio"] = ET.loio_summary(full_u, lo_u, famof, n_boot=n_boot, seed=0)
        elif trap:
            row["loio"] = {"not_applicable": "5.13 is defined on the confirmation suite and the real systems (TRAP_STAGES)"}
        per[sid] = row
    # 5.14 implementation groups
    limpo = {}
    for g in plan.groups:
        gid = safe(g["id"])
        rows_t = []
        for h in g["members"]:
            le = unwrap(_res(store, f"limpo_eval__{gid}__{safe(h)}"))
            if isinstance(le, dict) and "adapted" in (le.get("models") or {}) and "scratch" in (le.get("models") or {}):
                ad = {k: tuple(v) for k, v in (le["models"]["adapted"].get("units") or {}).items()}
                scr = {k: tuple(v) for k, v in (le["models"]["scratch"].get("units") or {}).items()}
                rows_t.append({"heldout": h, **ET.limpo_comparison(ad, scr, n_boot=n_boot, seed=0)})
        ee_units, sms, params = {}, {}, {}
        for sid in g["members"]:
            se = unwrap(_res(store, f"share_eval__{gid}__{safe(sid)}"))
            for m, r in ((se or {}).get("models") or {}).items():
                if r.get("error"):
                    continue
                ee_units.setdefault(m, {})[sid] = {k: tuple(v) for k, v in (r.get("units") or {}).items()}
                if r.get("SMS") and "point" in r["SMS"]:
                    sms.setdefault(m, {})[sid] = r["SMS"]
                params.setdefault(m, []).append(_n_params_total(r.get("n_params"), sid, shared=(m != "A")))
        par = {m: (None if any(v is None for v in vs) else (int(sum(vs)) if m == "A" else int(max(vs)))) for m, vs in params.items()}
        within = {sid: (_cat(per.get(sid)) or "missing") for sid in g["members"]}
        limpo[g["id"]] = {"kind": g["kind"], "members": g["members"], "transfer": rows_t,
                          "sharing": ET.sharing_comparison(ee_units, sms, par, rows_t or None, within_verdicts=within, n_boot=n_boot, seed=0),
                          "note": "model A = the independent per-system fits; model D is not expressible through CONFIG_KEYS"}
    # PROTOCOL 9: P_m, P_t (true state on its supported items), P_m - P_t on one item set, the conclusion (the confirmation suite only:
    # review G's trap systems are reported in their own section)
    syn_ids = [s for s, sp in plan.specs.items() if in_suite(sp)]
    comp = {s: bool(plan.specs[s].get("compressible")) for s in syn_ids if plan.specs[s].get("compressible") is not None}
    method_cats = {s: _cat(per[s]) for s in syn_ids if _cat(per[s])}
    tol_cal = {**tol_d}
    calib_all = calib_rows
    calib_rows = [r for r in calib_all if in_suite(plan.specs.get(str(r.get("sid")), {}))]      # the suite's rows (P_t, sensitivity)
    ts_cats = CAL.true_state_categories(calib_rows, tol_cal)
    same_cats = CAL.model_categories(calib_rows, tol_cal, "method") if calib_rows else None
    syn = {"method": method_cats, "truestate": ts_cats, "compressible": comp, "strata": {s: plan.specs[s].get("type") for s in syn_ids}}
    if same_cats is not None:
        syn["method_same_items"] = same_cats
    # a full network without a verdict is charged as UNSUPPORTED (the real part needs every full network of every lineage)
    real_full = {s: (_cat(per[s]) or V.UNSUPPORTED) for s, sp in plan.specs.items() if sp["kind"] == "real" and sp["cls"] == "full"}
    real_missing = sorted(s for s in real_full if not _cat(per[s]))
    real = {"full": real_full, "lineage": {s: plan.specs[s].get("lineage") for s in real_full}}
    conclusion = V.phase4_conclusion(syn if comp else None, real if real_full else None, n_boot=n_boot, seed=0,
                                     synthetic_capped_at_partial=capped)
    real_all = {s: {"category": _cat(per[s]), "class": sp["cls"], "lineage": sp.get("lineage")} for s, sp in plan.specs.items() if sp["kind"] == "real"}
    by_lineage: dict = {}
    for s, v in real_all.items():
        by_lineage.setdefault(str(v["lineage"]), {})[s] = v
    # PROTOCOL 11: the primary family
    sm = (cal or {}).get("suite_margins") or {}
    margins = {"delta_A": tol_d["delta_A"], "delta_C": tol_d["delta_C"], "tau_SMS": tol_d["tau_SMS"], "delta_NI": fixed.get("delta_NI"),
               "delta_C_suite": sm.get("delta_C_suite"), "tau_SMS_suite": sm.get("tau_SMS_suite")}
    if plan.mode.name == "dry" and (margins["delta_C_suite"] is None or margins["tau_SMS_suite"] is None):
        # DRY RUN ONLY: no calibration.json yet; the per-system margins stand in for the suite margins (flagged in the bundle)
        margins.update({"delta_C_suite": margins["delta_C"], "tau_SMS_suite": margins["tau_SMS"], "suite_margins_placeholder": True})
    suite = {"systems": sorted(s for s, c in comp.items() if c), "values": primary_values}
    try:
        primary = V.build_primary_family(suite if suite["systems"] else None, networks, margins, n_boot=n_boot, seed=0) \
            if margins["delta_NI"] is not None else {"error": "delta_NI missing (LEVEL_B_FIXED.json)"}
    except Exception as e:  # noqa: BLE001 - reported, never hidden
        primary = {"error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-2000:]}
    # the sensitivity table: every tolerance at both ends of its calibration CI (PROTOCOL 7)
    sens = {}
    cis = (cal or {}).get("tolerances_ci95_over_systems") or {}
    for key, ci in cis.items():
        for end, val in zip(("low", "high"), ci or []):
            if val is None or not np.isfinite(float(val)):
                continue
            t2 = V.Tolerances.from_dict({**tol_d, key: float(val)})
            cats = {s: V.system_verdict(m, t2, compact_judged=cj)["category"] for s, (m, cj) in metrics_for_sens.items() if m}
            syn2 = {"method": {s: c for s, c in cats.items() if s in comp}, "truestate": CAL.true_state_categories(calib_rows, t2.as_dict()),
                    "compressible": comp}
            if calib_rows:
                syn2["method_same_items"] = CAL.model_categories(calib_rows, t2.as_dict(), "method")
            real2 = {"full": {s: cats.get(s, V.UNSUPPORTED) for s in real_full}, "lineage": real["lineage"]}
            c2 = V.phase4_conclusion(syn2 if comp else None, real2 if real_full else None, n_boot=n_boot, seed=0, synthetic_capped_at_partial=capped)
            sens[f"{key}_{end}"] = {"value": float(val), "phase4": c2.get("phase4"), "synthetic": (c2.get("synthetic") or {}).get("status"),
                                    "real": (c2.get("real") or {}).get("status"), "categories": cats}
    # 5.17 active design
    rows = loop_rows(plan, store)
    active: dict = {"n_rows": len(rows), "n_unevaluated": sum(1 for r in rows if not r["evaluated"])}
    for part, sel in (("confirmation_suite", in_suite), ("real", lambda sp: sp["kind"] == "real")):
        rr_ = [r for r in rows if sel(plan.specs[r["system"]])]
        if not rr_:
            continue
        rr_, charged_cells = charge_loop_rows(rr_)             # PROTOCOL 5.17's charging rule (never dropped)
        out: dict = {"curves_EE": _safe_call(LP.curves, rr_, metric="EE", n_boot=n_boot), "charged_cells_EE": charged_cells}
        for metric in ("SMS", "lift_success"):
            out[f"curves_{metric}"] = _safe_call(LP.curves, [r for r in rr_ if r.get(metric) is not None], metric=metric, n_boot=n_boot)
        if any(r["designer"] == "own" for r in rr_):
            out["active_success"] = _safe_call(LP.active_success, rr_, own="own", comparators=RULE_COMPARATORS, metric="EE",
                                               matched=MATCHED_CONTROL, n_boot=n_boot, seed=0)
        else:
            out["active_success"] = {"note": "the method has no designer of its own: active design not applicable"}
        out["role"] = ("the rule's system set" if part == "confirmation_suite" else "reported beside the rule, descriptively (same "
                       "statistics; not part of the rule)")
        active[part] = out
    active["system_set_note"] = ("PROTOCOL 5.17 (pre-registered, P4-D56): the rule's system set is every synthetic confirmation-suite "
                                 "system, review G's traps excluded; the real systems are reported beside it descriptively; a failed "
                                 "or missing loop is charged at the worse comparator value, never dropped (`charge_loop_rows`)")
    # review G's trap tier (goal5 sections 41 / 84, criterion 33): descriptive, per trap, never pooled into the suite statistics
    traps = trap_evaluation(plan, per, CAL.true_state_categories([r for r in calib_all if system_set(plan.specs.get(str(r.get("sid")), {}))
                                                                   == "trap"], tol_cal))
    bundle = {"run_id": plan.run_id, "mode": plan.mode.name, "created_utc": now_utc(), "method": plan.method, "baselines": plan.baselines,
              "tolerances": tol_d, "tolerances_calibrated": calibrated, "calibration_file": str(calp) if cal else None,
              "synthetic_capped_at_partial": capped, "level_b_fixed": fixed, "per_system": per, "conclusion": conclusion,
              "real_by_lineage": by_lineage, "primary_family": H.public_view(primary), "margins": margins, "sensitivity": sens,
              "active_design": H.public_view(active), "implementation_groups": H.public_view(limpo),
              "level_b_to_c_drop": levelb_drop(levelb_round, plan.method, per, plan.specs),
              "self_audit_inputs": {"loops_summary": loops_summary(H.public_view(active)), "sharing": sharing_summary(H.public_view(limpo))},
              "trap_evaluation": H.public_view(traps),
              "charged": {"systems_without_primary_evaluation": sorted(s for s, v in per.items() if not _cat(v)),
                          "real_full_networks_charged_unsupported": real_missing, "calibration_rows": len(calib_rows),
                          "compressible_without_calibration_row": sorted(s for s, c in comp.items() if c and s not in ts_cats),
                          "trap_systems_without_primary_evaluation": (traps.get("summary") or {}).get("missing_systems", []),
                          # jobs whose every attempt hit the executor's time limit (attribution: infrastructure, TIME_LIMIT_FLOOR_S)
                          "time_limit_final": sorted({r["id"] for r in store.rows() if r.get("time_limit_final")}),
                          "time_limit_events": len(store.timeout_rows())},
              "stage_d_wall_s": round(time.time() - t0, 1)}
    return H.to_jsonable(bundle)


def _n_params_total(npar, sid: str, shared: bool):
    """Total parameters of a model for one system (encoder + read-in + readout of the system, + the transition; a SHARED model's
    transition is counted once for the group, which the caller does with max over the group's systems)."""
    if not isinstance(npar, dict):
        return None
    try:
        def part(k):
            v = npar.get(k)
            return int((v or {}).get(sid, 0)) if isinstance(v, dict) else int(v or 0)
        return part("encoder") + part("read_in") + part("readout") + int(npar.get("transition") or 0)
    except (TypeError, ValueError):
        return None


def _safe_call(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:  # noqa: BLE001 - reported, never hidden
        return {"error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-1500:]}


# ================================================================================================================ fixed at Level B
def fixed_from_levelb(round_dir: Path, *, strongest: str | None = None) -> dict:
    """LEVEL_B_FIXED.json from the FINAL Level B round (research/phase4/tournament/<round>/): the suite-level full-state bound and ID
    comparator (the better on the validation suite by the median over the round's synthetic systems of the seed-averaged verdict EE,
    PROTOCOL 8 / 9 / 11), the per-system choices of the real systems (BOUNDS.json; the same systems at Level C, fresh items), the
    strongest baseline S (the method lock's `strongest_baseline`, else the best baseline of DECISION.json's order) and delta_NI =
    0.2 x S's median seed-averaged class-balanced EE on the validation suite, a NUMBER (PROTOCOL 11)."""
    import numpy as np
    round_dir = Path(round_dir)
    bounds = json.loads((round_dir / "BOUNDS.json").read_text(encoding="utf-8"))
    dec = json.loads((round_dir / "DECISION.json").read_text(encoding="utf-8"))
    rnd = json.loads((round_dir / "ROUND.json").read_text(encoding="utf-8"))
    baselines = list(rnd.get("baselines") or [])
    if strongest is None and METHOD_LOCK.exists():
        strongest = json.loads(METHOD_LOCK.read_text(encoding="utf-8")).get("strongest_baseline") or None
    if strongest is None:
        strongest = next((m for m in dec.get("order") or [] if m in baselines), None)
    if strongest is None:
        raise ValueError("no strongest baseline: give it explicitly")

    def seed_avg_ee(method: str) -> dict:
        p = round_dir / f"{method.replace(':', '__').replace('/', '_')}.json"
        if not p.exists():
            return {}
        r = json.loads(p.read_text(encoding="utf-8"))
        out = {}
        for sid, v in (r.get("per_system") or {}).items():
            vals = []
            for sd in (v.get("seeds") or {}).values():
                e = (((sd or {}).get("verdict") or {}).get("metrics") or {}).get("EE") or {}
                vals.append(float(e.get("point")) if e.get("point") is not None else 10.0)
            if vals:
                out[sid] = (float(np.mean(vals)), v.get("kind"))
        return out
    s_ee = seed_avg_ee(strongest)
    syn_s = [v for v, kind in s_ee.values() if kind == "synthetic" and math.isfinite(v)]
    if not syn_s:
        raise ValueError(f"no synthetic seed-averaged EE of the strongest baseline {strongest} in {round_dir}")
    choices_full = sorted({v for v in (bounds.get("full_state") or {}).values()})
    choices_id = sorted({v for v in (bounds.get("id_shortcut") or {}).values()})

    def suite_best(choices: list[str], per_system: dict) -> str:
        """The candidate with the lower median verdict EE over the round's synthetic systems (a reference's EE from the per-system
        bound rows is not stored per candidate here, so the suite-level choice is the candidate chosen on MOST synthetic systems,
        ties broken by name; recorded)."""
        cnt: dict = {}
        for sid, c in per_system.items():
            if not str(sid).startswith("real:"):
                cnt[c] = cnt.get(c, 0) + 1
        return max(sorted(cnt), key=lambda c: cnt[c]) if cnt else (choices[0] if choices else "ref:full_state")

    fixed = {"full_state_bound": {"default": suite_best(choices_full, bounds.get("full_state") or {}),
                                  "per_system": {s: c for s, c in (bounds.get("full_state") or {}).items() if str(s).startswith("real:")}},
             "id_comparator": {"default": suite_best(choices_id, bounds.get("id_shortcut") or {}),
                               "per_system": {s: c for s, c in (bounds.get("id_shortcut") or {}).items() if str(s).startswith("real:")}},
             "strongest_baseline": strongest, "delta_NI": round(0.2 * float(np.median(syn_s)), 6),
             "delta_NI_rule": "0.2 x the strongest baseline's median seed-averaged class-balanced EE over the final round's synthetic systems",
             "suite_choice_rule": "the bound / comparator chosen per system (BOUNDS.json) on the most synthetic systems of the final round",
             "source": {"round": rnd.get("round"), "bounds_sha256": sha256_file(round_dir / "BOUNDS.json"),
                        "decision_sha256": sha256_file(round_dir / "DECISION.json"), "n_synthetic": len(syn_s)},
             "created_utc": now_utc()}
    return fixed


def role_baselines(cfg: dict | None) -> list[str]:
    """The baselines the self-audit's roles name ("baseline:<name>" sources), in role order without repeats."""
    out = []
    for role in SELF_AUDIT_ROLES:
        src = str(((cfg or {}).get("roles") or {}).get(role) or "")
        if src.startswith("baseline:") and src.split(":", 1)[1] not in out:
            out.append(src.split(":", 1)[1])
    return out


def self_audit_config(*, method: str, fixed: dict, roles: dict, run_id: str, designer: str | None = None,
                      tier: str = "conf", real_level: str = "C") -> dict:
    """research/phase4/SELF_AUDIT_CONFIG.json, written BEFORE the lock (and hashed by it) from the Level B-fixed choices: the roles of
    scripts/p4/self_audit_p4.py resolved to Level C sources ("method", "ref:<name>", "baseline:<name>", "fixed:<choice>"), the Level C
    run it reads (the official run id is chosen here, before any hidden data exist), and the summaries the Level C claims write for Q10
    (loops) and Q18 (sharing). `roles` gives the Level B baseline NAMES of id_baseline / input_only / readout_history /
    linear_controlled (the final round's own registered names; None = no such baseline, the check is then NOT_TESTABLE)."""
    base = {"method": "method", "id_reference": "ref:id_shortcut", "full_state_bound": "fixed:full_state_bound",
            "strongest_baseline": f"baseline:{fixed['strongest_baseline']}", "phase3": f"baseline:{FROZEN_V1}"}
    for role in ("id_baseline", "input_only", "readout_history", "linear_controlled"):
        name = roles.get(role)
        if name:
            base[role] = name if ":" in name and name.split(":", 1)[0] in ("ref", "baseline", "fixed") else f"baseline:{name}"
    out_rel = OUT_ROOT.relative_to(ROOT).as_posix()
    return {"tier": tier, "real_level": real_level, "seed": 0, "method": method, "designer": designer or "none",
            "methods_dir": LOCKED_METHODS.relative_to(ROOT).as_posix(), "levelc_run": str(RUN_ROOT / run_id), "roles": base,
            "loops_summary": f"{out_rel}/{run_id}/LOOPS_SUMMARY.json", "sharing": f"{out_rel}/{run_id}/SHARING_SUMMARY.json",
            "calibration_check": "research/phase4/CALIBRATION_CHECK_conf.json",
            "studies": {"ablations": f"research/phase4/postlock/ablations/{run_id}", "counterexamples": f"research/phase4/postlock/counterexamples/{run_id}"},
            "probes_dir": f"research/phase4/postlock/self_audit/{run_id}/probes", "out_dir": f"research/phase4/postlock/self_audit/{run_id}",
            "level_b_fixed_sha256": sha256_file(LEVEL_B_FIXED) if LEVEL_B_FIXED.exists() else None,
            "rule": "roles: the Level B-fixed choices (S, the full-state bound, the ID comparator) and the final round's baseline names for the "
                    "comparator roles; every baseline:<name> role is a baseline of the Level C run", "created_utc": now_utc()}


def loops_summary(active: dict) -> dict:
    """PROTOCOL 5.17 in the shape scripts/p4/self_audit_p4.py Q10 reads: the success flag of `loop.active_success` on the confirmation
    suite and, per budget, the own designer against the magnitude-matched random design (its one-sided upper bound at the rule's alpha)."""
    a = ((active or {}).get("confirmation_suite") or {}).get("active_success") or {}
    mc = ((a.get("matched_control") or {}).get("fixed_budget") or {}).get("per_budget") or {}
    matched = (a.get("matched_control") or {}).get("designer") or "random_matched"
    budgets = {str(b): {"own_vs_random_matched": {"upper95": (row.get(matched) or {}).get("upper_bound"),
                                                  "diff": (row.get(matched) or {}).get("diff")}} for b, row in mc.items()}
    return {"active_design_succeeds": a.get("success"), "success_fixed_budget": a.get("success_fixed_budget"),
            "success_fewer_experiments": a.get("success_fewer_experiments"), "budgets": budgets, "alpha": a.get("alpha"),
            "note": a.get("note") or a.get("error"), "source": "levelc stage_d active_design.confirmation_suite"}


def sharing_summary(limpo: dict) -> dict:
    """PROTOCOL 5.14 in the shape scripts/p4/self_audit_p4.py Q18 reads: one row per unit, an implementation group (related) or its
    unrelated-pair null, with the sharing verdict of every shared model (B / C), the hard gate and the transfer rows."""
    pairs = []
    for uid, g in (limpo or {}).items():
        models = ((g.get("sharing") or {}).get("models") or {})
        verdicts = {m: v.get("verdict") for m, v in models.items()}
        pairs.append({"unit": uid, "members": g.get("members"), "related": g.get("kind") == "group", "verdicts": verdicts,
                      "gate": (g.get("sharing") or {}).get("gate"),
                      "rejected": bool(verdicts) and all(v == "rejected" for v in verdicts.values()),
                      "shared": any(v == "supported" for v in verdicts.values()),
                      "n_transfer": len(g.get("transfer") or [])})
    return {"pairs": pairs, "note": "rejected = every shared model's verdict is 'rejected'; 'prerequisite failed' (the hard gate) is neither "
                                    "rejected nor shared", "source": "levelc stage_d implementation_groups"}


def dry_fixed(strongest: str, store: RunStore | None, plan: Plan | None) -> dict:
    """The dry run's stand-in of LEVEL_B_FIXED.json: the references as bound and comparator, the given baseline as S, and delta_NI =
    0.2 x S's median EE over the run's synthetic systems when its evaluations exist (a PLACEHOLDER; flagged)."""
    import numpy as np
    d_ni = None
    if store is not None and plan is not None:
        vals = []
        for sid, sp in plan.specs.items():
            if sp["kind"] != "synthetic":
                continue
            ev = evaluation(store, f"beval__{safe(sid)}__{safe(strongest)}")
            e = ((((ev or {}).get("result") or {}).get("items") or {}).get("effects") or {}).get("EE_cb_medium") or {}
            if e.get("point") is not None and math.isfinite(float(e["point"])):
                vals.append(float(e["point"]))
        if vals:
            d_ni = round(0.2 * float(np.median(vals)), 6)
    return {"full_state_bound": {"default": "ref:full_state", "per_system": {}}, "id_comparator": {"default": "ref:id_shortcut", "per_system": {}},
            "strongest_baseline": strongest, "delta_NI": d_ni if d_ni is not None else 0.2,
            "placeholder": "DRY RUN: not fixed at Level B; delta_NI from this run's own baseline evaluations (or 0.2 when none)"}


# ================================================================================================================ projection
def profile_from_run(store: RunStore) -> dict:
    """{stage: {system class: [measured job wall seconds]}} of a finished run (the ok jobs)."""
    out: dict = {}
    for r in store.rows():
        if r.get("status") != "ok" or r.get("wall_s") is None:
            continue
        out.setdefault(r["stage"], []).append(float(r["wall_s"]))
    return out


def simulate_makespan(durations: dict, deps: dict, capacity: dict, cls_of: dict) -> dict:
    """Longest-processing-time list schedule of a DAG on per-class capacities (slots): durations {job: s}, deps {job: [job]},
    capacity {class: slots}, cls_of {job: class}. Returns {"makespan_s", "busy_slot_s": {class: slot-seconds}, "unscheduled": jobs that
    never started (a class without slots, or waiting on such a job)}. Deterministic. One ready heap PER CLASS (longest first), filled
    only while the class has a free slot: O(N log N) (re-heaping every waiting job at every event took over 15 min on 16,000 jobs)."""
    indeg = {j: 0 for j in durations}
    kids: dict = {j: [] for j in durations}
    for j, ds in deps.items():
        for d in ds:
            if d in durations and j in durations:
                indeg[j] += 1
                kids[d].append(j)
    ready: dict = {}
    for j, n in indeg.items():
        if n == 0:
            ready.setdefault(cls_of[j], []).append((-durations[j], j))
    for h in ready.values():
        heapq.heapify(h)
    free = {c: int(n) for c, n in capacity.items()}
    running: list = []
    t = 0.0
    busy: dict = {}
    started = 0

    def start_ready() -> None:
        nonlocal started
        for c, h in ready.items():
            while h and free.get(c, 0) > 0:
                _negd, j = heapq.heappop(h)
                free[c] -= 1
                heapq.heappush(running, (t + durations[j], j))
                busy[c] = busy.get(c, 0.0) + durations[j]
                started += 1

    start_ready()
    while running:
        t, j = heapq.heappop(running)
        free[cls_of[j]] += 1
        for k in kids[j]:
            indeg[k] -= 1
            if indeg[k] == 0:
                heapq.heappush(ready.setdefault(cls_of[k], []), (-durations[k], k))
        start_ready()
    return {"makespan_s": round(t, 1), "busy_slot_s": {c: round(v, 1) for c, v in busy.items()}, "unscheduled": len(durations) - started}
