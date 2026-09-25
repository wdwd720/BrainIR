"""Phase 3 self-audit (goal4 section 87: TEST the questions, do not only answer them; support for the acceptance criteria of section
85). ORCHESTRATOR SIDE. Runs at any time; before the lock most checks are not yet applicable.

    uv run --project phase3 --no-sync python scripts/p3/self_audit.py [--method NAME] [--final-round NAME] [--level-c ATTEMPT]
        [--cex RUN[,RUN]] [--ablations ROUND] [--run-tests] [--run-root-tests] [--modal-checks]
        [--probe-prefix --probe-method-dir DIR --probe-model-pattern ".../{sid}_s0.pkl" --probe-systems s1,s2]
        [--probe-permutation --probe-method-dir DIR --probe-systems s1,s2] [--out-dir research/phase3]

Writes SELF_AUDIT.json and SELF_AUDIT.md (research/phase3/ by default). Every check returns 'pass', 'fail' or 'n/a' (not yet
applicable, or its evidence does not exist yet) with its evidence and the acceptance criteria it supports.
- INTEGRITY checks (I1-I15): locks, tags, clean room, answer-bearing files and answer tokens in the rooms, hidden-evaluation log,
  lock-before-hidden ordering, tests, the Modal fit volume, reviews, costs, report.
- SCIENCE checks (Q1-Q19): the 19 questions of goal4 section 87. Each is mapped to an executable test on the post-lock evidence:
  - the Level B confirmation round on the synthetic FINAL suite, with truth and traps;
  - Level C on the real hidden data;
  - the counterexample sweeps and the ablations;
  - two probes that this script runs itself (the encoder's history slicing and prefix determinism, and neuron-order equivariance).
  'fail' means the test weakens the central claim. It is reported, never hidden. 'pass' means the claim survived that test.
The thresholds (TH) were fixed before any post-lock evidence existed.
Leakage scans report classes and counts only, never the matched text or a token's value (values are answer-bearing).
The outputs are ANSWER-BEARING once the post-lock evidence exists (they summarise hidden results); never copy them into a room.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "p3"))

P3 = ROOT / "research" / "phase3"
DATA = ROOT / "data" / "phase3"
BENCH = ROOT / "benchmarks" / "state_discovery_v1"
ROOMS = {"clean": Path(r"C:\Dev\BrainIR_p3clean"), "review": Path(r"C:\Dev\BrainIR_p3review")}
ROOT_PY = ROOT / ".venv" / "Scripts" / "python.exe"
PASS, FAIL, NA = "pass", "fail", "n/a"
FULL_VERDICTS = ("compact causal state discovered", "compact causal state discovered (microstate equivalence untestable)")
# pre-declared thresholds (fixed before the post-lock evidence exists; changing them later must be logged with a reason)
TH = {
    "trap_k_handled": 0.8,          # a trap is handled if the method abstains or recovers the true latent (min R^2 both ways >= this)
    "trap_k_fooled": 0.5,           # ... and FOOLED if it claims a compact causal state while min R^2 < this
    "beats_control_frac": 0.5,      # Q2 / Q3: the method's A must be significantly below the shortcut control on >= this fraction
    "underestimate_frac": 0.25,     # Q5: k < k_true on more than this fraction of compressible systems fails
    "underestimate_fast_frac": 0.5,  # Q5: ... or on at least this fraction of the fast-relaxation / multi-timescale systems
    "not_closed_frac": 0.5,         # Q6: 'closed' False on more than this fraction fails
    "not_equivalent_frac": 0.5,     # Q7: microstate equivalence False on more than this fraction of testable systems fails
    "c_collapse_frac": 0.5,         # Q8: held-out C upper CI >= 1 on more than this fraction fails
    "loio_worse_frac": 0.5,         # Q11: encoder-only adaptation worse than scratch on at least this fraction fails
    "g_r2_min": 0.8,                # Q12: median r2_min_mean across seeds below this fails
    "g_k_agree_frac": 0.5,          # Q12: ... or seeds agreeing on k on fewer than this fraction of systems
    "transient_ratio": 3.0,         # Q14: median post-intervention NMSE / unperturbed A at the same horizon above this fails
    "pca_as_good_frac": 0.5,        # Q16: PCA-k at least as good in A AND in C on at least this fraction fails
    "broken_immediately_frac": 0.5,  # Q19: 'broken immediately' on at least this fraction of searched systems fails
    "perm_a_rel": 0.05,             # Q10 probe: |dA| / A within this and identical k pass
}
FAST_TYPES = ("slow_fast", "bifurcation", "winner_take_all", "bistable_switch", "hysteresis_memory")
TRAPS = {"A": "nuisance", "B": "output_shortcut", "C": "time_index", "D": "stimulus_copy", "E": "redundant", "F": "hysteresis",
         "G": "nonmarkov", "H": "parameter_trap", "I": "multicycle", "J": "transient_cycle", "K": "bifurcation", "L": "distributed"}


# ------------------------------------------------------------------------------------------------ helpers
def sha(p: Path) -> str:
    b = p.read_bytes()
    if p.suffix in {".py", ".md", ".txt", ".json", ".jsonl", ".toml", ".cfg", ".lock"}:
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()


def run(cmd: list[str], timeout: float = 1800, cwd: Path = ROOT) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout + "\n" + p.stderr)
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout:.0f} s"
    except FileNotFoundError as e:
        return 127, repr(e)


def git(*args: str) -> tuple[int, str]:
    return run(["git", *args], timeout=120)


def md_rows(path: Path) -> list[list[str]]:
    """Rows of the first markdown table of a file (header and separator skipped)."""
    if not path.exists():
        return []
    rows = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.startswith("|") and not set(ln.replace("|", "").strip()) <= set("-: "):
            rows.append([c.strip() for c in ln.strip().strip("|").split("|")])
    return rows[1:] if rows else []


def utc(s: str) -> float | None:
    try:
        return time.mktime(time.strptime(s.strip(), "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
    except (ValueError, AttributeError):
        return None


def frac(xs) -> float | None:
    xs = [bool(x) for x in xs]
    return float(np.mean(xs)) if xs else None


def k_min_r2(rec: dict) -> float | None:
    k = rec.get("K") or {}
    try:
        return min(float(k["r2_true_from_model_rff"]), float(k["r2_model_from_true_rff"]))
    except (KeyError, TypeError, ValueError):
        return None


def abstained(rec: dict) -> bool:
    ab = ((rec.get("verdict") or {}).get("abstention")) or {}
    return bool(ab.get("no_compact_state") or ab.get("causal_equivalence_failed"))


# ------------------------------------------------------------------------------------------------ evidence
class Ctx:
    def __init__(self, a):
        self.a = a
        self.lock = json.loads((P3 / "METHOD_LOCK.json").read_text(encoding="utf-8")) if (P3 / "METHOD_LOCK.json").exists() else None
        self.method = a.method or (self.lock or {}).get("method")
        self.baseline = (self.lock or {}).get("strongest_baseline")
        self.levelb_rows = md_rows(P3 / "LEVELB_LOG.md")
        self.hidden_rows = md_rows(P3 / "HIDDEN_EVALUATIONS.md")
        finals = [r[1] for r in self.levelb_rows if len(r) > 2 and r[2] == "final"]
        self.final_round = a.final_round or (finals[-1] if finals else None)
        self._final = None
        self._truth = None
        self._lc = None

    # the Level B confirmation round (per-method files) and the final suite's truth
    def final(self) -> dict:
        if self._final is None:
            self._final = {}
            d = P3 / "tournament" / (self.final_round or "_none_")
            if d.exists():
                for f in d.glob("*.json"):
                    if f.name.startswith(("AGGREGATE", "ROUND_DECISION", "modal_costs")):
                        continue
                    try:
                        self._final[f.stem] = json.loads(f.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        pass
        return self._final

    def mfinal(self) -> dict | None:
        return self.final().get(self.method) if self.method else None

    def truth(self) -> dict:
        if self._truth is None:
            f = DATA / "synthetic" / "final" / "truth" / "truth.json"
            self._truth = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        return self._truth

    def level_c(self) -> dict | None:
        if self._lc is None:
            base = P3 / "level_c"
            att = self.a.level_c or (sorted(p.name for p in base.iterdir() if (p / "level_c_results.json").exists())[-1:] or [None])[0] \
                if base.exists() else self.a.level_c
            f = base / str(att) / "level_c_results.json"
            self._lc = json.loads(f.read_text(encoding="utf-8")) if att and f.exists() else {}
        return self._lc or None

    def cex(self) -> list[dict]:
        base = P3 / "counterexamples"
        runs = [r for r in (self.a.cex or "").split(",") if r] or (sorted(p.name for p in base.iterdir() if p.is_dir()) if base.exists() else [])
        out = []
        for r in runs:
            f = base / r / "SUMMARY.json"
            if f.exists():
                out.append(json.loads(f.read_text(encoding="utf-8")))
        return out

    def ablations(self) -> dict | None:
        base = P3 / "ablations"
        rnd = self.a.ablations or next((p.name for p in sorted(base.iterdir()) if (p / "SUMMARY.json").exists() and "final" in p.name), None) \
            if base.exists() else self.a.ablations
        f = base / str(rnd) / "SUMMARY.json"
        return json.loads(f.read_text(encoding="utf-8")) if rnd and f.exists() else None

    def trap_systems(self, letter: str) -> list[str]:
        return sorted(s for s, v in (self.truth().get("systems") or {}).items() if v.get("trap") == letter)


CHECKS: list[tuple[str, str, str, tuple, object]] = []


def check(cid: str, group: str, title: str, criteria: tuple = ()):
    def deco(fn):
        CHECKS.append((cid, group, title, criteria, fn))
        return fn
    return deco


def res(status: str, note: str = "", **evidence) -> dict:
    return {"status": status, "note": note, "evidence": evidence}


# ------------------------------------------------------------------------------------------------ INTEGRITY
@check("I1", "integrity", "Phase 1 benchmark remains frozen (benchmarks/dng100/freeze.py --check)", (1,))
def i1(ctx):
    if not ROOT_PY.exists():
        return res(NA, "root environment missing")
    rc, out = run([str(ROOT_PY), "benchmarks/dng100/freeze.py", "--check"], timeout=1800)
    return res(PASS if rc == 0 else FAIL, "", exit_code=rc, tail=out.strip().splitlines()[-2:])


@check("I2", "integrity", "Phase 2 locked method unchanged (method_lock.py check; no change under src/brainir since brainir-v1-preblind)", (2, 3))
def i2(ctx):
    if not ROOT_PY.exists():
        return res(NA, "root environment missing")
    rc, out = run([str(ROOT_PY), "scripts/method_lock.py", "check"], timeout=600)
    rd, diff = git("diff", "--name-only", "brainir-v1-preblind", "--", "src/brainir")
    rs, st = git("status", "--porcelain", "--", "src/brainir")
    changed = [x for x in diff.splitlines() if x.strip()] + [x for x in st.splitlines() if x.strip()]
    ok = rc == 0 and rd == 0 and not changed
    return res(PASS if ok else FAIL, "", lock_check_exit=rc, changed_or_untracked=changed[:20])


@check("I3", "integrity", "Phase 3 benchmark lock, tag and salt commitment", (9, 10))
def i3(ctx):
    rc, out = run([sys.executable, "scripts/p3/freeze_benchmark.py", "--check"], timeout=1800)
    lock = json.loads((BENCH / "BENCHMARK_LOCK.json").read_text(encoding="utf-8"))
    ver = lock.get("benchmark_version")
    tag = lock.get("git_tag") or f"state-discovery-benchmark-v{ver}"
    rt, tagged = git("show", f"{tag}:benchmarks/state_discovery_v1/BENCHMARK_LOCK.json")
    working = (BENCH / "BENCHMARK_LOCK.json").read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    tag_matches = rt == 0 and tagged.replace("\r\n", "\n").strip() == working
    salt = DATA / "hidden" / "salt.txt"
    salt_ok = salt.exists() and hashlib.sha256(salt.read_text(encoding="utf-8").strip().encode()).hexdigest() == lock.get("salt_sha256")
    if not salt_ok and salt.exists():   # the commitment may hash the raw bytes
        salt_ok = hashlib.sha256(salt.read_bytes()).hexdigest() == lock.get("salt_sha256")
    ok = rc == 0 and tag_matches and salt_ok
    return res(PASS if ok else FAIL, "fails while a new benchmark version is being prepared (before its re-lock)", check_exit=rc,
               benchmark_version=ver, tag=tag, tag_lock_matches_working_copy=tag_matches, salt_commitment_matches=salt_ok,
               check_tail=[x for x in out.strip().splitlines()[-3:]])


@check("I4", "integrity", "Phase 3 method lock (METHOD_LOCK.json hashes, tag brainir-state-v1-preblind)", (18, 19, 46))
def i4(ctx):
    if ctx.lock is None:
        return res(NA, "no method lock yet")
    rc, out = run([sys.executable, "scripts/p3/method_lock_p3.py", "--check"], timeout=600)
    tag = ctx.lock.get("tag", "brainir-state-v1-preblind")
    rt, tagged = git("show", f"{tag}:research/phase3/METHOD_LOCK.json")
    same = rt == 0 and tagged.replace("\r\n", "\n").strip() == (P3 / "METHOD_LOCK.json").read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    ok = rc == 0 and same
    return res(PASS if ok else FAIL, "", check_exit=rc, tag=tag, tag_holds_this_lock=same, method=ctx.method, baseline=ctx.baseline)


@check("I5", "integrity", "Clean room matches its allowlist and holds no forbidden file (make_phase3_cleanroom.py --check)", (4, 5, 6, 7))
def i5(ctx):
    rc, out = run([sys.executable, "scripts/make_phase3_cleanroom.py", "--check"], timeout=1800)
    classes: dict[str, int] = {}
    for ln in out.splitlines():
        for key in ("forbidden name", "forbidden content", "missing", "modified", "unexpected"):
            if ln.strip().lower().startswith(key):
                classes[key] = classes.get(key, 0) + 1
    return res(PASS if rc == 0 and not classes else FAIL, "problem lines are counted by class only (matched text is never copied)",
               exit_code=rc, problem_classes=classes)


# HIDDEN tier: hidden results, oracles and hidden generators; never in ANY room (method, review). DEVELOPER tier: selection-time
# evidence about held-out systems (reviews, per-method tournament results, review G results); never in the method room (the review
# room legitimately holds the reviewers' own reports).
HIDDEN_TIER = ["PHASE2_REPORT.md", "PHASE3_REPORT.md", "research/phase2/HIDDEN_EVAL_LOG.md", "research/phase2/hidden_eval_ledger.json",
               "research/phase3/HIDDEN_EVALUATIONS.md", "research/phase3/level_c/**/*.json", "benchmarks/dng100/oracle/**/*",
               "benchmarks/state_discovery_v1/hidden/*.json", "research/phase3/SELF_AUDIT.json", "research/phase3/counterexamples/**/*.json",
               "research/phase3/ablations/**/*.json"]
DEVELOPER_TIER = ["research/phase3/reviews/*.md", "research/phase3/review_g/results*.json", "research/phase3/tournament/*/*.json"]
HIDDEN_NAMES = {"PHASE2_REPORT.md", "PHASE3_REPORT.md", "HIDDEN_EVAL_LOG.md", "HIDDEN_EVALUATIONS.md", "level_c_results.json", "oracle.json",
                "hidden_eval_ledger.json", "SELF_AUDIT.json"}


def _tier_files(pats: list[str]) -> list[Path]:
    out = []
    for p in pats:
        for f in ROOT.glob(p):
            if f.is_file() and not f.name.startswith("AGGREGATE_developer_facing"):
                out.append(f)
    return out


def _answer_bearing_files() -> list[Path]:
    return _tier_files(HIDDEN_TIER + DEVELOPER_TIER)


@check("I6", "integrity", "No answer-bearing file (by content hash or name) in the rooms (hidden tier: any room; developer tier: method room)", (5, 6))
def i6(ctx):
    def hashes(files):
        h = {}
        for f in files:
            try:
                h[sha(f)] = f.relative_to(ROOT).as_posix()
            except OSError:
                pass
        return h
    hid, dev = hashes(_tier_files(HIDDEN_TIER)), hashes(_tier_files(DEVELOPER_TIER))
    hits = {}
    for room, base in ROOMS.items():
        if not base.exists():
            continue
        forbidden = {**hid, **(dev if room == "clean" else {})}
        matches, by_name = [], []
        for f in base.rglob("*"):
            if not f.is_file() or any(x in f.parts for x in (".venv", "__pycache__", ".git")):
                continue
            if f.name in HIDDEN_NAMES:
                by_name.append(f.relative_to(base).as_posix())
            try:
                if f.stat().st_size < 50_000_000:
                    s = sha(f)
                    if s in forbidden:
                        matches.append({"room_file": f.relative_to(base).as_posix(), "equals": forbidden[s]})
            except OSError:
                continue
        hits[room] = {"by_hash": matches[:20], "n_by_hash": len(matches), "by_name": by_name[:20]}
    ok = all(v["n_by_hash"] == 0 and not v["by_name"] for v in hits.values())
    return res(PASS if ok else FAIL, "file names and paths only (never contents)", n_hidden_tier=len(hid), n_developer_tier=len(dev), rooms=hits)


@check("I7", "integrity", "No answer token or forbidden name in the rooms' text files (classes and counts only)", (5, 6, 7))
def i7(ctx):
    sys.path.insert(0, str(ROOT / "scripts" / "p3agent"))
    from audit_transcripts import NAMES, answer_tokens
    toks, _ = answer_tokens()
    tok_re = re.compile("|".join(rf"(?<![0-9A-Za-z#]){re.escape(t)}(?![0-9A-Za-z])" for t in sorted(toks, key=len, reverse=True)))
    # the transcript audit's name list mixes dataset / organism / source names (a leak in any room file) with FILE-NAME references
    # (hidden_eval, phase2_report, goal4.md, ...), which the public protocol legitimately mentions: only the former fail here
    alts = NAMES.pattern[len("(?i)("):-1].split("|")
    ref_like = re.compile(r"phase2_report|hidden_eval|blind_eval|oracle|tier_a_ids|goal")
    src_names = re.compile("(?i)(" + "|".join(a for a in alts if not ref_like.search(a)) + ")")
    ref_names = re.compile("(?i)(" + "|".join(a for a in alts if ref_like.search(a)) + ")")
    text_ext = {".py", ".md", ".txt", ".json", ".jsonl", ".toml", ".cfg", ".yaml", ".yml", ".csv"}
    out = {}
    fail = False
    for room, base in ROOMS.items():
        if not base.exists():
            continue
        r = {"files_scanned": 0, "token_classes": {}, "source_name_hits": 0, "file_reference_hits": 0, "files_with_source_names": []}
        for f in base.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in text_ext or any(x in f.parts for x in (".venv", "__pycache__", ".git", "tmp")):
                continue
            try:
                if f.stat().st_size > 200_000_000:
                    continue
                txt = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            r["files_scanned"] += 1
            area = "data" if (f.suffix.lower() in (".json", ".jsonl", ".csv") and "data" in f.relative_to(base).parts[:1]) else "code_notes"
            for m in tok_re.finditer(txt):
                t = m.group(0)
                cls = f"{area}:numeric-{len(t)}-digits" if t.isdigit() else f"{area}:non-numeric"
                r["token_classes"][cls] = r["token_classes"].get(cls, 0) + 1
                if not t.isdigit() or (area == "code_notes" and len(t) >= 8):
                    fail = True
            n = len(src_names.findall(txt))
            r["source_name_hits"] += n
            r["file_reference_hits"] += len(ref_names.findall(txt))
            if n:
                r["files_with_source_names"].append(f.relative_to(base).as_posix())
                fail = True
        out[room] = r
    return res(FAIL if fail else PASS, "numeric hits shorter than 8 digits, and numeric hits in public data files, are reported as "
               "coincidences (counts, sizes); non-numeric hits, long numeric hits in code or notes, and dataset / organism / source "
               "names fail; references to file names (e.g. the hidden-evaluation log) are counted only", rooms=out)


@check("I8", "integrity", "Hidden-evaluation log is complete and consistent (every Level C / confirmation run logged; attempts counted)", (17, 47, 48))
def i8(ctx):
    rows = ctx.hidden_rows
    lc_dirs = sorted(p.name for p in (P3 / "level_c").iterdir() if p.is_dir()) if (P3 / "level_c").exists() else []
    finals = [r[1] for r in ctx.levelb_rows if len(r) > 2 and r[2] == "final"]
    if not rows and not lc_dirs and not finals:
        return res(NA, "no hidden evaluation yet")
    problems = []
    for d in lc_dirs:
        if not any(len(r) > 2 and r[1] == d and "Level C" in r[2] for r in rows):
            problems.append(f"Level C attempt {d} has no log row")
    for f in finals:
        if not any(f in " ".join(r) for r in rows):
            problems.append(f"Level B confirmation round {f} has no HIDDEN_EVALUATIONS row")
    starts = [r for r in rows if len(r) > 2 and "Level C START" in r[2]]
    if len(starts) > 1:
        reasons = [r[4] for r in starts[1:] if len(r) > 4]
        if any(not x or x == "first and only planned Level C evaluation" for x in reasons):
            problems.append("a repeated Level C attempt has no specific reason")
    return res(FAIL if problems else PASS, "", n_rows=len(rows), level_c_attempts=lc_dirs, confirmation_rounds=finals, problems=problems)


@check("I9", "integrity", "No hidden evaluation or hidden real data before the method lock", (17, 46))
def i9(ctx):
    rows = ctx.hidden_rows
    hid = DATA / "real_hidden" / "manifest.json"
    if ctx.lock is None:
        early = [r[0] for r in rows] + ([hid.as_posix()] if hid.exists() else []) + [r[1] for r in ctx.levelb_rows if len(r) > 2 and r[2] == "final"]
        return res(FAIL if early else NA, "before the lock nothing hidden may exist", hidden_items_before_lock=early[:10])
    t_lock = utc(ctx.lock.get("locked_utc", ""))
    before = [r[0] for r in rows if utc(r[0]) is not None and t_lock is not None and utc(r[0]) < t_lock]
    if hid.exists() and t_lock is not None and hid.stat().st_mtime < t_lock:
        before.append("data/phase3/real_hidden/manifest.json (mtime)")
    return res(FAIL if before else PASS, "", locked_utc=ctx.lock.get("locked_utc"), items_before_lock=before)


@check("I10", "integrity", "Test suites green (Phase 3 tests; root tests when requested)", (42, 43))
def i10(ctx):
    if not (ctx.a.run_tests or ctx.a.run_root_tests):
        return res(NA, "not run (use --run-tests / --run-root-tests)")
    ev, ok = {}, True
    if ctx.a.run_tests:
        rc, out = run([sys.executable, "-m", "pytest", "-q", "phase3/tests"], timeout=3600)
        ev["phase3"] = {"exit": rc, "summary": [x for x in out.splitlines() if " passed" in x or " failed" in x][-1:]}
        ok &= rc == 0
    if ctx.a.run_root_tests and ROOT_PY.exists():
        rc, out = run([str(ROOT_PY), "-m", "pytest", "-q", "-m", "not real_data"], timeout=7200)
        ev["root"] = {"exit": rc, "summary": [x for x in out.splitlines() if " passed" in x or " failed" in x][-1:]}
        ok &= rc == 0
    return res(PASS if ok else FAIL, "", **ev)


@check("I11", "integrity", "The Modal fit volume holds only public fit views, method snapshots and fitted models", ())
def i11(ctx):
    if not ctx.a.modal_checks:
        return res(NA, "not run (use --modal-checks)")
    import modal
    vol = modal.Volume.from_name("brainir-p3-fit")
    top = sorted(e.path.strip("/") for e in vol.listdir("/"))
    bad_top = [t for t in top if t not in ("views", "methods", "models", "_incoming")]
    views, bad_splits = [], {}
    for e in vol.listdir("/views"):
        v = e.path.strip("/").split("/")[-1]
        views.append(v)
        try:
            data = b"".join(vol.read_file(f"/views/{v}/index.jsonl"))
            splits = {json.loads(x)["split"] for x in data.decode("utf-8").splitlines() if x.strip()}
        except Exception as ex:  # noqa: BLE001
            splits = {f"unreadable: {ex!r}"[:80]}
        if not splits <= {"train", "val"}:
            bad_splits[v] = sorted(splits)
    ok = not bad_top and not bad_splits
    return res(PASS if ok else FAIL, "", top_level=top, views=views, views_with_non_public_splits=bad_splits)


@check("I12", "integrity", "Reviews A-H complete, blockers resolved before the lock; post-lock reviews after it", (44, 45))
def i12(ctx):
    rv = P3 / "reviews"
    have = {p.name for p in rv.glob("*.md")} if rv.exists() else set()
    need = {"A": "A_prelock.md", "B": "B_prelock.md", "C": "C_prelock.md", "D": "D_prelock.md", "E": "E_early.md", "F": "F_leakage.md",
            "H": "H_early.md"}
    missing = [k for k, f in need.items() if f not in have]
    g_ok = (P3 / "review_g" / "REVIEW_G_TRAPS.md").exists()
    resolutions = {"EH": "EH_early_resolution.md" in have, "F": "F_resolution.md" in have,
                   "ABCD": any(n.startswith("ABCD") and "resolution" in n for n in have)}
    post = sorted(n for n in have if n.upper().startswith("POSTLOCK"))
    ok = not missing and g_ok and all(resolutions.values())
    note = "" if ctx.lock is None else ("post-lock reviews present" if post else "post-lock reviews not yet present")
    return res(PASS if ok else FAIL, note, missing_reviews=missing, review_g_traps=g_ok, resolutions=resolutions, postlock_reviews=post)


@check("I13", "integrity", "Compute and costs recorded (COSTS_LEDGER.md, COMPUTE_SUMMARY, per-run Modal records)", (41,))
def i13(ctx):
    ledger = (P3 / "COSTS_LEDGER.md").exists()
    summ = (P3 / "COMPUTE_SUMMARY.md").exists()
    rounds = [p.parent.name for p in (P3 / "tournament").glob("*/modal_costs.json")]
    return res(PASS if ledger and summ else FAIL, "run scripts/p3/compute_summary.py to (re)write COMPUTE_SUMMARY.md", ledger=ledger,
               compute_summary=summ, rounds_with_modal_records=len(rounds))


@check("I14", "integrity", "PHASE3_REPORT.md exists, is marked answer-bearing and states one of the three conclusions", (49, 50))
def i14(ctx):
    f = ROOT / "PHASE3_REPORT.md"
    if not f.exists():
        return res(NA, "report not written yet")
    t = f.read_text(encoding="utf-8")
    marked = "ANSWER-BEARING" in t.upper()
    concl = [c for c in ("compact causal state discovered", "partially supported", "not supported") if c in t.lower()]
    return res(PASS if marked and concl else FAIL, "", marked_answer_bearing=marked, conclusions_named=concl)


@check("I15", "integrity", "Phase 2 candidates regenerated from public evidence (provenance recorded)", (8,))
def i15(ctx):
    d = P3 / "candidates"
    prov = d / "regeneration_provenance.json"
    ok = (d / "regenerated_candidates_public.json").exists() and prov.exists()
    return res(PASS if ok else FAIL, "", files=sorted(p.name for p in d.glob("*.json")) if d.exists() else [])


# ------------------------------------------------------------------------------------------------ SCIENCE (goal4 section 87)
def _trap(ctx, letter: str) -> dict:
    m = ctx.mfinal()
    if not m:
        return {"status": NA}
    rows = []
    for s in ctx.trap_systems(letter):
        rec = (m.get("per_system") or {}).get(s) or {}
        v = (rec.get("verdict") or {}).get("verdict")
        r2 = k_min_r2(rec)
        ab = abstained(rec)
        handled = ab or (r2 is not None and r2 >= TH["trap_k_handled"])
        fooled = (not ab) and v in FULL_VERDICTS and (r2 is None or r2 < TH["trap_k_fooled"])
        rows.append({"system": s, "verdict": v, "k": rec.get("k"), "k_true": rec.get("k_true"), "k_min_r2": r2, "abstained": ab,
                     "handled": handled, "fooled": fooled, "error": rec.get("error")})
    if not rows:
        return {"status": NA}
    return {"status": FAIL if any(r["fooled"] for r in rows) else PASS, "rows": rows}


def _control_fraction(ctx, name: str) -> dict:
    m = ctx.mfinal()
    if not m:
        return {}
    comp = [s for s, v in (ctx.truth().get("systems") or {}).items() if v.get("k") != "none"]
    beats = []
    for s in comp:
        v = ((m.get("per_system") or {}).get(s) or {}).get("verdict") or {}
        d = v.get(f"A_minus_{name}") or {}
        try:
            beats.append(float(d["ci95"][1]) < 0)
        except (KeyError, TypeError, ValueError, IndexError):
            beats.append(False)
    return {"fraction_beating": frac(beats), "n": len(beats)}


def _level_c_rows(ctx) -> dict:
    lc = ctx.level_c() or {}
    return {s: r for s, r in (lc.get("systems") or {}).items()}


@check("Q1", "science", "Could time alone explain the latent state? (time-index trap C on the final suite)", (14, 28))
def q1(ctx):
    t = _trap(ctx, "C")
    return res(t["status"], "fooled = a compact causal state claimed while the true latent is not recovered", trap=t.get("rows"))


@check("Q2", "science", "Could stimulus alone explain it? (stimulus-copy trap D; A against the input-only control)", (21, 22))
def q2(ctx):
    t = _trap(ctx, "D")
    fr = _control_fraction(ctx, "input_only")
    if t["status"] == NA and not fr:
        return res(NA, "no Level B confirmation yet")
    real = {s: (((r.get(ctx.method) or {}).get("verdict") or {}).get("A_minus_input_only") or {}).get("ci95") for s, r in _level_c_rows(ctx).items()}
    ok = t["status"] != FAIL and (fr.get("fraction_beating") or 0) >= TH["beats_control_frac"]
    return res(PASS if ok else FAIL, "", trap=t.get("rows"), synthetic=fr, real_A_minus_input_only_ci95=real)


@check("Q3", "science", "Could output history alone explain it? (output-shortcut trap B; A against the readout-history control)", (21, 22))
def q3(ctx):
    t = _trap(ctx, "B")
    fr = _control_fraction(ctx, "readout_hist")
    if t["status"] == NA and not fr:
        return res(NA, "no Level B confirmation yet")
    ok = t["status"] != FAIL and (fr.get("fraction_beating") or 0) >= TH["beats_control_frac"]
    return res(PASS if ok else FAIL, "real systems: the readout-history control is descriptive (benchmark version 3)", trap=t.get("rows"),
               synthetic=fr)


class _RecordingModel:
    """Stub state model recording the history lengths the evaluator passes to encode()."""
    uses_readout = False

    def __init__(self):
        self.seen = []

    def encode(self, sid, x_hist, u_hist, dt):
        self.seen.append((len(x_hist), len(u_hist)))
        return np.zeros(1)


def _probe_prefix_job(job: dict) -> dict:
    """Worker (fresh process, eval guard): encodings of intervened trajectories and their twins at the pre-event sample must be
    identical (identical histories; no future, no state kept between calls), and repeated encodings must be bit-identical."""
    from brainir_state.evaluate import encode_at, first_event_time, idx
    from brainir_state.harness import hidden_sets
    from brainir_state.runguard import install_eval_guard
    from brainir_state.runner import load_model
    from brainir_state.suite_eval import SuiteData
    sd = SuiteData(job["public_dir"], kind="synthetic")
    hs = hidden_sets(sd.hid, job["sid"])
    install_eval_guard([job["method_dir"]], allowed=[str(Path(job["model_path"]).parent)])
    model = load_model(job["method_dir"], job["model_path"])
    worst, n = 0.0, 0
    for prs in hs["pairs"].values():
        for tr, tw in prs[:4]:
            t_ev = first_event_time(tr)
            if t_ev is None:
                continue
            i0 = idx(t_ev, tr.dt)
            if not np.array_equal(tr.x[: i0 + 1], tw.x[: i0 + 1]):
                continue
            z1 = encode_at(model, job["sid"], tr, i0)
            z2 = encode_at(model, job["sid"], tw, i0)
            z3 = encode_at(model, job["sid"], tr, i0)
            worst = max(worst, float(np.max(np.abs(z1 - z2))), float(np.max(np.abs(z1 - z3))))
            n += 1
    return {"sid": job["sid"], "n_pairs": n, "max_abs_diff": worst}


@check("Q4", "science", "Did future information leak into the encoder? (history slicing of the evaluator; prefix determinism of the model)", (22, 23))
def q4(ctx):
    from brainir_state.data import Trajectory
    from brainir_state.evaluate import encode_at
    t = np.arange(0, 1.0, 0.01)
    tr = Trajectory(key="probe", system_id="probe", split="test", family="probe", protocol={"dt": 0.01, "events": []}, t=t,
                    x=np.random.default_rng(0).normal(size=(len(t), 3)), u=np.zeros((len(t), 1)), y=np.zeros((len(t), 1)))
    rec = _RecordingModel()
    ok_slice = True
    for i in (0, 10, 57, len(t) - 1):
        encode_at(rec, "probe", tr, i)
        ok_slice &= rec.seen[-1] == (i + 1, i + 1)
    ev = {"evaluator_passes_only_the_history": ok_slice}
    status = PASS if ok_slice else FAIL
    if ctx.a.probe_prefix:
        import multiprocessing as mp
        from concurrent.futures import ProcessPoolExecutor
        systems = [s for s in (ctx.a.probe_systems or "").split(",") if s]
        jobs = [{"public_dir": str(DATA / "synthetic_dev"), "sid": s, "method_dir": ctx.a.probe_method_dir,
                 "model_path": ctx.a.probe_model_pattern.format(sid=s, sid_=s.replace(":", "_"))} for s in systems]
        with ProcessPoolExecutor(max_workers=max(1, min(4, len(jobs))), mp_context=mp.get_context("spawn"), max_tasks_per_child=1) as ex:
            out = list(ex.map(_probe_prefix_job, jobs))
        ev["prefix_probe"] = out
        if any(o["max_abs_diff"] != 0.0 for o in out):
            status = FAIL
    else:
        ev["prefix_probe"] = "not run (--probe-prefix)"
    return res(status, "the stub check always runs; the prefix probe needs a fitted locked-method model on dev systems", **ev)


@check("Q5", "science", "Is the latent dimension underestimated because of smoothing? (k vs true k; fast-relaxation systems)", (19, 28))
def q5(ctx):
    m = ctx.mfinal()
    truth = ctx.truth().get("systems") or {}
    if not m or not truth:
        return res(NA, "no Level B confirmation yet")
    under, under_fast, over = [], [], []
    for s, v in truth.items():
        if v.get("k") == "none":
            continue
        rec = (m.get("per_system") or {}).get(s) or {}
        k = rec.get("k")
        if k is None:
            continue
        under.append(int(k) < int(v["k"]))
        over.append(int(k) > int(v["k"]))
        if str(v.get("dynamics_type", "")).startswith(FAST_TYPES):
            under_fast.append(int(k) < int(v["k"]))
    fu, ff = frac(under), frac(under_fast)
    fail = (fu or 0) > TH["underestimate_frac"] or (ff is not None and ff >= TH["underestimate_fast_frac"])
    return res(FAIL if fail else PASS, "", underestimated_fraction=fu, overestimated_fraction=frac(over), n=len(under),
               fast_systems_underestimated_fraction=ff, n_fast=len(under_fast))


def _verdict_fraction(ctx, key: str, value=False, skip_none=True) -> tuple[float | None, int]:
    m = ctx.mfinal()
    truth = ctx.truth().get("systems") or {}
    xs = []
    for s, v in truth.items():
        if v.get("k") == "none":
            continue
        vd = ((m.get("per_system") or {}).get(s) or {}).get("verdict") or {}
        if key not in vd or (skip_none and vd[key] is None):
            continue
        xs.append(vd[key] == value)
    return frac(xs), len(xs)


@check("Q6", "science", "Does discarded neural state still predict future behavior? ('closed': micro / history gain, closure gap, Markov)", (24, 25))
def q6(ctx):
    if not ctx.mfinal():
        return res(NA, "no Level B confirmation yet")
    f, n = _verdict_fraction(ctx, "closed", False)
    real = {s: ((r.get(ctx.method) or {}).get("verdict") or {}).get("closed") for s, r in _level_c_rows(ctx).items()}
    return res(FAIL if (f or 0) > TH["not_closed_frac"] else PASS, "", synthetic_not_closed_fraction=f, n=n, real_closed=real)


@check("Q7", "science", "Do two microstates with the same z actually diverge? (E, microstate equivalence)", (25,))
def q7(ctx):
    if not ctx.mfinal():
        return res(NA, "no Level B confirmation yet")
    f, n = _verdict_fraction(ctx, "microstate_equivalent", False)
    real = {s: ((r.get(ctx.method) or {}).get("verdict") or {}).get("microstate_equivalent") for s, r in _level_c_rows(ctx).items()}
    return res(FAIL if (f or 0) > TH["not_equivalent_frac"] else PASS, "None = untestable", synthetic_not_equivalent_fraction=f,
               n_testable=n, real=real)


@check("Q8", "science", "Does intervention fidelity collapse on unseen perturbations? (held-out C; held-out vs in-distribution on real)", (23,))
def q8(ctx):
    m = ctx.mfinal()
    if not m:
        return res(NA, "no Level B confirmation yet")
    truth = ctx.truth().get("systems") or {}
    up = []
    for s, v in truth.items():
        if v.get("k") == "none":
            continue
        vd = ((m.get("per_system") or {}).get(s) or {}).get("verdict") or {}
        try:
            up.append(float(vd["C_ci95"][1]) >= 1.0)
        except (KeyError, TypeError, ValueError, IndexError):
            up.append(True)
    def c_of(rr: dict, block: str):
        d = rr.get(block) or {}
        key = next((k for k in d if k.startswith("C_effect_error_w")), None)
        return (d.get(key) or {}).get("ci95") if key else None

    real = {}
    for s, r in _level_c_rows(ctx).items():
        rr = ((r.get(ctx.method) or {}).get("res")) or {}
        real[s] = {"heldout_ci95": c_of(rr, "C_heldout"), "indist_ci95": c_of(rr, "C_indist")}
    f = frac(up)
    return res(FAIL if (f or 0) > TH["c_collapse_frac"] else PASS, "held-out C upper CI >= 1 = no better than predicting no effect",
               synthetic_heldout_no_better_than_null_fraction=f, n=len(up), real=real)


@check("Q9", "science", "Does shared cross-connectome dynamics only work because capacity is huge? (J: parameters, capacity)", (32, 33))
def q9(ctx):
    lc = ctx.level_c()
    if not lc:
        return res(NA, "no Level C yet")
    rows = {}
    bad = False
    for pair, r in (lc.get("J") or {}).items():
        comp = r.get("comparison") or {}
        sp, ip = comp.get("shared_params") or {}, comp.get("independent_params") or {}
        rows[pair] = {"verdict": r.get("verdict"), "fewer_parameters": comp.get("fewer_parameters"), "shared_total": sp.get("total"),
                      "independent_total": ip.get("total"), "note": r.get("note")}
        if r.get("verdict") == "supported" and not comp.get("fewer_parameters"):
            bad = True
    note = "no shared cross-connectome dynamics supported: nothing to attribute to capacity" if not any(
        v["verdict"] == "supported" for v in rows.values()) else ""
    return res(FAIL if bad else PASS, note, J=rows)


def _probe_perm_job(job: dict) -> dict:
    """Fit the locked method on a system and on a copy with the observed neurons in a permuted order; compare k and A."""
    from brainir_state import evaluate as E
    from brainir_state.harness import SYNTH_CFG, SYNTH_ROLES, evaluate_system, hidden_sets, pca_basis
    from brainir_state.runner import load_model
    from brainir_state.suite_eval import SuiteData, fit_sandboxed
    out = {"sid": job["sid"]}
    for tag, pub in (("original", job["orig_dir"]), ("permuted", job["perm_dir"])):
        sd = SuiteData(pub, kind="synthetic")
        view = sd.fit_view(Path(job["work"]) / f"view_{tag}")
        mp = Path(job["work"]) / tag / f"{job['sid']}.pkl"
        rec = fit_sandboxed(Path(job["method_dir"]), job["method"], [view], [job["sid"]], mp, seed=0, timeout_s=3600)
        if "error" in rec:
            out[tag] = {"error": rec["error"]}
            continue
        model = load_model(job["method_dir"], mp)
        train = sd.train_only(job["sid"])
        r = evaluate_system(model, job["sid"], hidden_sets(sd.hid, job["sid"]), E.readout_scale(train), pca_basis(train), SYNTH_CFG,
                            families=("A",), roles=SYNTH_ROLES)
        key = f"A_nmse_h{int(round(SYNTH_CFG.primary_horizon_s * 1000))}ms"
        out[tag] = {"k": (model.info().get("k") or {}).get(job["sid"]), "A": ((r.get("A_B") or {}).get(key) or {}).get("mean")}
    return out


def _permuted_copy(src: Path, dst: Path, sid: str, seed: int = 0) -> None:
    """A copy of one system's rows of a synthetic suite with the observed neurons in a permuted column order (the neuron ids travel
    with their columns, so events keep their meaning); pools / micro files copied unchanged."""
    import shutil
    man = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(x) for x in (src / "index.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = [r for r in rows if r["system_id"] == sid]
    obs = list(man["systems"][sid]["observed"])
    perm = np.random.default_rng(seed).permutation(len(obs))
    (dst / "traj").mkdir(parents=True, exist_ok=True)
    for r in rows:
        with np.load(src / "traj" / f"{r['key']}.npz", allow_pickle=False) as z:
            arrs = {k: z[k] for k in z.files}
        if "x" in arrs:
            arrs["x"] = arrs["x"][:, perm]
        np.savez_compressed(dst / "traj" / f"{r['key']}.npz", **arrs)
    man = dict(man)
    man["systems"] = {sid: dict(man["systems"][sid], observed=[obs[i] for i in perm])}
    (dst / "index.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8", newline="\n")
    (dst / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    for f in ("micro_index.json", "micro_futures.npz"):
        if (src / f).exists():
            shutil.copy2(src / f, dst / f)


@check("Q10", "science", "Does alignment rely on neuron identity? (neuron-order permutation probe: same k and A)", (30, 32))
def q10(ctx):
    if not ctx.a.probe_permutation:
        return res(NA, "probe not run (--probe-permutation with --probe-method-dir, --probe-systems on dev systems)")
    import multiprocessing as mp
    import tempfile
    from concurrent.futures import ProcessPoolExecutor
    systems = [s for s in (ctx.a.probe_systems or "").split(",") if s]
    method = ctx.method or ctx.a.method
    work = Path(tempfile.mkdtemp(prefix="p3perm_", dir=str(DATA)))
    jobs = []
    for s in systems:
        perm = work / f"perm_{s}"
        _permuted_copy(DATA / "synthetic_dev", perm, s, seed=1)
        jobs.append({"sid": s, "orig_dir": str(DATA / "synthetic_dev"), "perm_dir": str(perm), "work": str(work / s),
                     "method_dir": ctx.a.probe_method_dir, "method": method})
    with ProcessPoolExecutor(max_workers=max(1, min(4, len(jobs))), mp_context=mp.get_context("spawn"), max_tasks_per_child=1) as ex:
        out = list(ex.map(_probe_perm_job, jobs))
    bad = []
    for o in out:
        a, b = o.get("original") or {}, o.get("permuted") or {}
        if "error" in a or "error" in b or a.get("k") != b.get("k") or not a.get("A") or \
                abs((b.get("A") or np.inf) - a["A"]) / abs(a["A"]) > TH["perm_a_rel"]:
            bad.append(o["sid"])
    return res(FAIL if bad else PASS, "the permuted copies are under data/phase3/p3perm_* (public dev data; delete after the audit)",
               probes=out, not_equivariant=bad)


@check("Q11", "science", "Does the latent model memorize the physical implementation? (leave-one-implementation-out adaptation)", (31, 34))
def q11(ctx):
    m = ctx.mfinal()
    if not m:
        return res(NA, "no Level B confirmation yet")
    lo = [x for r in (m.get("I") or []) if r.get("kind") == "group" for x in (r.get("loio") or [])]
    if not lo:
        return res(NA, "no leave-one-implementation-out result (the method cannot adapt, or no groups)")
    worse = frac(x.get("adapted_worse") for x in lo)
    beats = frac(x.get("adapted_beats_scratch") for x in lo)
    return res(FAIL if (worse or 0) >= TH["loio_worse_frac"] else PASS, "", n=len(lo), adapted_worse_fraction=worse,
               adapted_beats_scratch_fraction=beats, group_verdicts=[r.get("verdict") for r in (m.get("I") or []) if r.get("kind") == "group"])


@check("Q12", "science", "Does the representation change completely across random seeds? (G: R^2 both ways, k agreement, predictions)", (29,))
def q12(ctx):
    m = ctx.mfinal()
    lc = ctx.level_c()
    rows = {s: g for s, g in ((m or {}).get("G") or {}).items()}
    real = {s: (g.get("G") or {}) for s, g in ((lc or {}).get("G") or {}).items()}
    if not rows and not real:
        return res(NA, "no G results yet")
    r2 = [g.get("r2_min_mean") for g in list(rows.values()) + list(real.values()) if g.get("r2_min_mean") is not None]
    agree = [len({x for x in (g.get("k") or []) if x is not None}) == 1 for g in list(rows.values()) + list(real.values()) if g.get("k")]
    med = float(np.median(r2)) if r2 else None
    fa = frac(agree)
    fail = (med is not None and med < TH["g_r2_min"]) or (fa is not None and fa < TH["g_k_agree_frac"])
    return res(FAIL if fail else PASS, "", median_r2_min_mean=med, k_agree_fraction=fa, n=len(r2),
               prediction_disagreement_median=float(np.median([g["prediction_disagreement_nmse"] for g in list(rows.values()) + list(real.values())
                                                               if g.get("prediction_disagreement_nmse") is not None])) if r2 else None)


@check("Q13", "science", "Does parameter uncertainty require extra hidden state? (parameter trap H; closure on real draws; draw probe)", (35,))
def q13(ctx):
    t = _trap(ctx, "H")
    lc = _level_c_rows(ctx)
    if t["status"] == NA and not lc:
        return res(NA, "no Level B confirmation / Level C yet")
    full = {s: r for s, r in lc.items() if r.get("mode") == "full"}
    closed = [((r.get(ctx.method) or {}).get("verdict") or {}).get("closed") for r in full.values()]
    probe = {s: ((r.get(ctx.method) or {}).get("res") or {}).get("P_param_probe") for s, r in lc.items()}
    fail = t["status"] == FAIL or (closed and sum(1 for c in closed if c is False) > len(closed) / 2)
    return res(FAIL if fail else PASS, "", trap=t.get("rows"), real_full_closed=closed, param_probe=probe)


@check("Q14", "science", "Does the model fail after transient perturbation? (post-intervention error vs unperturbed A; transient trap J)", (23, 36))
def q14(ctx):
    t = _trap(ctx, "J")
    ratios = {}
    for s, r in _level_c_rows(ctx).items():
        rr = ((r.get(ctx.method) or {}).get("res")) or {}
        ch = rr.get("C_heldout") or {}
        post = [(int(k.split("_w")[1].rstrip("ms")), (v or {}).get("mean")) for k, v in ch.items() if k.startswith("C_post_nmse_w")]
        ab = rr.get("A_B") or {}
        if not post:
            continue
        w, val = max(post)
        a = (ab.get(f"A_nmse_h{w}ms") or {}).get("mean")
        if val is not None and a:
            ratios[s] = float(val) / float(a)
    if t["status"] == NA and not ratios:
        return res(NA, "no Level B confirmation / Level C yet")
    med = float(np.median(list(ratios.values()))) if ratios else None
    fail = t["status"] == FAIL or (med is not None and med > TH["transient_ratio"])
    return res(FAIL if fail else PASS, "", trap=t.get("rows"), real_post_over_unperturbed=ratios, median=med)


def _paired_median(ctx, other: str, key: str) -> dict | None:
    from brainir_state.evaluate_cross import LOWER_IS_BETTER, system_values
    m, o = ctx.mfinal(), ctx.final().get(other)
    if not m or not o:
        return None
    truth = ctx.truth().get("systems") or {}
    comp = [s for s, v in truth.items() if v.get("k") != "none"]
    d = []
    for s in comp:
        a, b = system_values(m.get("per_system") or {}, s)[key], system_values(o.get("per_system") or {}, s)[key]
        if a is not None and b is not None and np.isfinite(a) and np.isfinite(b):
            d.append(a - b)       # method - other
    if not d:
        return None
    d = np.array(d)
    rng = np.random.default_rng(0)
    bm = np.median(d[rng.integers(0, len(d), (2000, len(d)))], axis=1)
    lo, hi = float(np.percentile(bm, 2.5)), float(np.percentile(bm, 97.5))
    better = hi < 0 if key in LOWER_IS_BETTER else lo > 0
    return {"median_diff_method_minus_other": float(np.median(d)), "ci95": [lo, hi], "method_significantly_better": bool(better), "n": len(d)}


@check("Q15", "science", "Is a simple linear model equally good? (paired S1-S5 against every linear method of the confirmation round)", (15, 16))
def q15(ctx):
    lins = [n for n in ctx.final() if n.startswith("lin_") and n != ctx.method]
    if not lins or not ctx.mfinal():
        return res(NA, "no linear method in a Level B confirmation round yet")
    out, any_better = {}, {}
    for n in lins:
        out[n] = {k: _paired_median(ctx, n, k) for k in ("S1_A_over_full", "S2_C_heldout", "S3_D_micro_gain", "S4_E_ratio", "S5_K_r2_rff")}
        any_better[n] = any((v or {}).get("method_significantly_better") for v in out[n].values())
    fail = not all(any_better.values())
    return res(FAIL if fail else PASS, "fail = some linear method is not significantly worse on any component (the added value over "
               "linear models is not supported)", per_linear_method=out)


@check("Q16", "science", "Is PCA equally good? (the PCA-k control with the method's k: A and C per system)", (39,))
def q16(ctx):
    rows = {}
    for s, r in _level_c_rows(ctx).items():
        mm = r.get(ctx.method) or {}
        refs = mm.get("references") or {}
        v = mm.get("verdict") or {}
        pa = ((refs.get("pca_k") or {}).get("A_B") or {})
        key = next((k for k in pa if k.startswith("A_nmse_h")), None)
        a_pca = (pa.get(key) or {}).get("mean") if key else None
        rows[s] = {"A_method": v.get("A"), "A_pca_k": a_pca}
    fin = []
    m = ctx.mfinal()
    if m:
        from brainir_state.harness import SYNTH_CFG, key_a
        from brainir_state.suite_eval import evaluator_code_tag
        ct, ka = evaluator_code_tag(), key_a(SYNTH_CFG)
        for s, rec in (m.get("per_system") or {}).items():
            k = rec.get("k")
            f = P3 / "tournament" / "_refcache" / "final" / f"refs_{s.replace(':', '_')}_k{int(k) if k else 1}_s0_{ct}.json"
            if not f.exists():
                continue
            ref = json.loads(f.read_text(encoding="utf-8")).get("pca_k") or {}
            v = rec.get("verdict") or {}
            kc = next((x for x in (ref.get("C_heldout") or {}) if x.startswith("C_effect_error_w")), None)
            a_p = ((ref.get("A_B") or {}).get(ka) or {}).get("mean")
            c_p = ((ref.get("C_heldout") or {}).get(kc) or {}).get("ratio") if kc else None
            if a_p is not None and v.get("A") is not None and c_p is not None and v.get("C") is not None:
                fin.append(a_p <= v["A"] and c_p <= v["C"])
    if not rows and not fin:
        return res(NA, "no Level B confirmation / Level C yet")
    f = frac(fin)
    return res(FAIL if (f or 0) >= TH["pca_as_good_frac"] else PASS, "", synthetic_pca_as_good_in_A_and_C_fraction=f, n=len(fin), real=rows)


@check("Q17", "science", "Can unrelated synthetic systems be falsely aligned? (unrelated pairs must be rejected)", (33, 34))
def q17(ctx):
    m = ctx.mfinal()
    if not m:
        return res(NA, "no Level B confirmation yet")
    pairs = [r for r in (m.get("I") or []) if r.get("kind") == "pair"]
    if not pairs:
        return res(NA, "no shared fits on unrelated pairs in the confirmation round")
    false = [r.get("members") for r in pairs if r.get("verdict") == "supported"]
    return res(FAIL if false else PASS, "", n_pairs=len(pairs), falsely_supported=false, verdicts=[r.get("verdict") for r in pairs])


@check("Q18", "science", "Does the method find low-dimensional states in the non-compressible controls? (family L)", (13, 38))
def q18(ctx):
    m = ctx.mfinal()
    if not m:
        return res(NA, "no Level B confirmation yet")
    truth = ctx.truth().get("systems") or {}
    wrong = []
    for s, v in truth.items():
        if v.get("k") != "none":
            continue
        rec = (m.get("per_system") or {}).get(s) or {}
        if not abstained(rec) and ((rec.get("verdict") or {}).get("verdict") in FULL_VERDICTS):
            wrong.append(s)
    return res(FAIL if wrong else PASS, "", compact_claims_on_noncompressible=wrong, abstention=m.get("abstention"))


@check("Q19", "science", "Can the counterexample search break it immediately? (post-lock sweeps)", (37,))
def q19(ctx):
    sums = [s for s in ctx.cex() if s.get("hidden_material") or s.get("tier") in ("final", "heldout")]
    if not sums:
        return res(NA, "no post-lock counterexample sweep yet")
    per = {}
    for s in sums:
        for sid, v in (s.get("systems") or {}).items():
            per[f"{s.get('run')}:{sid}"] = v.get("broken_immediately_fraction")
    vals = [v for v in per.values() if v is not None]
    f = frac(v >= 0.5 for v in vals)
    return res(FAIL if (f or 0) >= TH["broken_immediately_frac"] else PASS, "", systems_broken_immediately_fraction=f, n=len(vals),
               overall=[s.get("overall") for s in sums])


# ------------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", default="")
    ap.add_argument("--final-round", default="")
    ap.add_argument("--level-c", default="")
    ap.add_argument("--cex", default="")
    ap.add_argument("--ablations", default="")
    ap.add_argument("--run-tests", action="store_true")
    ap.add_argument("--run-root-tests", action="store_true")
    ap.add_argument("--modal-checks", action="store_true")
    ap.add_argument("--probe-prefix", action="store_true")
    ap.add_argument("--probe-permutation", action="store_true")
    ap.add_argument("--probe-method-dir", default="")
    ap.add_argument("--probe-model-pattern", default="")
    ap.add_argument("--probe-systems", default="")
    ap.add_argument("--only", default="", help="comma list of check ids")
    ap.add_argument("--out-dir", default=str(P3))
    a = ap.parse_args(argv)
    ctx = Ctx(a)
    only = {x for x in a.only.split(",") if x}
    results = []
    for cid, group, title, crit, fn in CHECKS:
        if only and cid not in only:
            continue
        t0 = time.time()
        try:
            r = fn(ctx)
        except Exception as e:  # noqa: BLE001 - a crashing check is a failure of the audit, reported as such
            r = res(FAIL, f"check crashed: {e!r}"[:300])
        r.update(id=cid, group=group, title=title, criteria=list(crit), seconds=round(time.time() - t0, 1))
        results.append(r)
        print(f"{cid:4s} {r['status']:5s} {title[:100]}", flush=True)
    counts = {g: {s: sum(1 for r in results if r["group"] == g and r["status"] == s) for s in (PASS, FAIL, NA)} for g in ("integrity", "science")}
    rec = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "method": ctx.method, "final_round": ctx.final_round,
           "locked": ctx.lock is not None, "thresholds": TH, "counts": counts, "checks": results}
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "SELF_AUDIT.json").write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Phase 3 self-audit (goal4 section 87)", "",
             f"Generated {rec['generated_utc']}; method {ctx.method}; confirmation round {ctx.final_round}; locked {rec['locked']}.",
             "Each check TESTS a question; 'fail' weakens the claim and is reported, 'n/a' means its evidence does not exist yet. "
             "Thresholds were fixed before the post-lock evidence (listed in SELF_AUDIT.json).", "",
             f"Counts: {json.dumps(counts)}", "", "| id | status | check | criteria | note |", "|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['id']} | {r['status']} | {r['title']} | {', '.join(str(c) for c in r['criteria'])} | {r['note'][:160]} |")
    (out / "SELF_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
