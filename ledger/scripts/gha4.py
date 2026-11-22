"""Run 4 campaigns on GitHub Actions (RUN4_PROMPT hard limit 7, PREREG v4 Part X): registers run 4's builders with the frozen
`gha.py` (pack) and adds run 4's publish / collect / feeder / gate helpers. The frozen `gha.py`, `gha3.py`, `gha3r.py`, their
runners and workflows are not edited.

- Every run 4 campaign runs through run 4's runner and workflow (`gha_runner4.py`, `.github/workflows/ledger-gha4.yml`, tags
  `gha4-run-<name>`), published with `publish4`; run 4's runner passes `group_v2` (Part A, R4's kind) and run 1's `fixed` jobs to the
  older entry points unchanged.
- Hard limit 1 (declare first): every run 4 builder refuses before the tag `ledger-prereg-v4` exists and `LOCK_prereg_v4.json` verifies.
- Hard limit 7: `feeder` publishes queued campaigns only while the account's GitHub jobs that are queued or running, plus the next
  campaign's jobs (its chunks + the plan job), stay at or below 20.

Campaign names: `<prefix>-<label>-run4`, the prefix selecting the builder and `--k` its variant (1 = MANC, 2 = MaleCNS unless stated).

    uv run --project ledger --no-sync python ledger/scripts/gha4.py pack pa-manc-run4 --chunk-jobs 950 --k 1
    uv run --project ledger --no-sync python ledger/scripts/gha4.py publish4 pa-manc-run4
    uv run --project ledger --no-sync python ledger/scripts/gha4.py feeder pa-manc-run4 pa-mcns-run4 r4rep-run4
    uv run --project ledger --no-sync python ledger/scripts/gha4.py collect4 pa-manc-run4 [--wait]
    uv run --project ledger --no-sync python ledger/scripts/gha4.py trust-compare trust-run4      # -> gates_v4/TRUST_GATE_v4.json
"""

from __future__ import annotations

import json
import pickle
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gha as G  # noqa: E402

from brainir.compute.backend import Shared  # noqa: E402
from brainir.sim.model import ModelConfig  # noqa: E402
from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import arms as AR  # noqa: E402
from brainir_ledger import mirror as MR  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

GATES4 = RESEARCH / "gates_v4"
REL2 = RESEARCH / "reliability_v2"
FREEZE_TAG = "ledger-prereg-v4"
FLY = {1: "MANC", 2: "MaleCNS"}
A_SEEDS = tuple(range(16))
B_SEEDS = tuple(range(8))
GRID = tuple(float(4.0 * 2 ** (k / 2)) for k in range(19))   # PREREG v4 B1.1: 4.0 ... 2048
R4_REP_SEED = 20261404
DET_SEED = 20261405
PERM_SEED = 20261403
MAX_JOBS = 20


# ------------------------------------------------------------------------------------------------------------------ guards
def _tagged() -> bool:
    return subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{FREEZE_TAG}"], cwd=G.REPO, capture_output=True).returncode == 0


def require_freeze(what: str) -> None:
    """Hard limit 1: the tag must exist and be an ancestor of HEAD, and the prereg v4 lock must verify."""
    if not _tagged():
        raise SystemExit(f"{what}: refused before the tag {FREEZE_TAG} (RUN4_PROMPT hard limit 1); nothing built")
    anc = subprocess.run(["git", "merge-base", "--is-ancestor", FREEZE_TAG, "HEAD"], cwd=G.REPO, capture_output=True).returncode == 0
    ok = subprocess.run([sys.executable, str(HERE / "lock4.py"), "check", str(RESEARCH / "LOCK_prereg_v4.json")], cwd=G.REPO,
                        capture_output=True).returncode == 0
    if not (anc and ok):
        raise SystemExit(f"{what}: the tag {FREEZE_TAG} is not an ancestor of HEAD or LOCK_prereg_v4.json does not verify; refused")


def _write_once(path: Path, obj: dict) -> None:
    """Gate files are written once (a later check writes a new file)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, indent=1, default=str) + "\n")


# ------------------------------------------------------------------------------------------------------------- job helpers
def _v2_jobs(arm: str, groups: dict, seeds) -> list[dict]:
    """R4's job specification exactly (`gha._v2_jobs`: run 2's group_v2, K = 1, B1's screen, readout traces stored)."""
    return G._v2_jobs(arm, groups, 1, AR, ModelConfig, seeds=list(seeds))


def _base_job(key: str, seed: int) -> dict:
    return {"key": key, "seed": int(seed), "k_min": 1, "model": ModelConfig(t_end=1.0).to_dict(), "screen": AR.b1_screen_cfg(10).to_dict()}


PAIRED = {"mode": "paired", "n_real": None, "src": Shared("src"), "sizes_real": Shared("sizes_real")}


def _paired(n_real: int) -> dict:
    return dict(PAIRED, n_real=int(n_real))


def analysed_set() -> dict:
    p = REL2 / "ANALYSED_SET.json"
    if not p.is_file():
        raise SystemExit("reliability_v2/ANALYSED_SET.json missing: run the Part A analysis first (G9)")
    return json.loads(p.read_text())


def part_a_results(fly: str) -> dict[tuple[str, str, int], dict]:
    """(side, type, seed) -> Part A replicate (MANC seeds 0..3 from R4, the rest from run 4's campaigns)."""
    out = {}
    if fly == "MANC":
        for r in read_log(data_dir() / "reliability" / "GHA_r4-run3" / "results.pkl"):
            arm, t, s = r["key"].split("|")
            out[(arm[-1], t, int(s[1:]))] = r
        logs = [data_dir() / "reliability_v2" / "GHA_pa-manc-run4" / "results.pkl"]
    else:
        logs = [data_dir() / "reliability_v2" / "GHA_pa-mcns-run4" / "results.pkl"]
    for p in logs:
        for r in read_log(p):
            arm, t, s = r["key"].split("|")
            out[(arm[-1], t, int(s[1:]))] = r
    return out


# ------------------------------------------------------------------------------------------------------------------ Part A
def build_pa(k=None):
    """PREREG v4 A1: the one-sided screen (R4's specification) on both halves of fly k; MANC seeds 4..15 (0..3 are R4's), MaleCNS
    seeds 0..15."""
    require_freeze("Part A")
    fly = FLY[int(k)]
    f = MR.fly(fly)
    halves = f.halves()
    if fly == "MANC":
        import gha3r  # noqa: PLC0415  (R4's builder: the groups must be R4's exactly)

        _, _, (fl, g1), _ = G._nets()
        r4 = gha3r.r4_groups(fl, g1)
        if r4 != halves:
            raise SystemExit("MANC halves differ from R4's groups; refused")
    seeds = A_SEEDS[4:] if fly == "MANC" else A_SEEDS
    shared = {"W": f.net.W, "sizes": f.net.sizes, "readout_L": f.readout_side("L"), "readout_R": f.readout_side("R")}
    tag = "MANC" if fly == "MANC" else "MCNS"
    jobs = []
    for side in ("L", "R"):
        jobs += [dict(j, readout=Shared(f"readout_{side}")) for j in _v2_jobs(f"A-{tag}-{side}", halves[side], seeds)]
    return [(shared, jobs)], "reliability_v2"


def build_r4rep(k=None):
    """PREREG v4 A1: 100 of R4's locked jobs drawn with default_rng(20261404), re-run through run 4's runner (same keys)."""
    require_freeze("R4 reproduction")
    import gha3r  # noqa: PLC0415

    (shared, jobs), _ = gha3r.build_r4()[0][0], None
    keys = sorted(j["key"] for j in jobs)
    pick = set(np.random.default_rng(R4_REP_SEED).choice(keys, 100, replace=False).tolist())
    return [(shared, [j for j in jobs if j["key"] in pick])], "reliability_v2"


# ----------------------------------------------------------------------------------------------------------------- Block 1
def build_b1s(k=None):
    """PREREG v4 B1.1 + B1.3: per analysed type, side and seed 0..7, one sweep job: the 19 grid currents, then (transplant) the
    side's own accepted current and the other side's accepted current of the same seed when accepted; standard parameters (the Part
    A replicate of that seed)."""
    require_freeze("Block 1")
    fly = FLY[int(k)]
    f = MR.fly(fly)
    halves = f.halves()
    types = [t for t in analysed_set()["analysed"] if t in halves["L"]]
    pa = part_a_results(fly)
    shared = {"W": f.net.W, "sizes": f.net.sizes, "readout_L": f.readout_side("L"), "readout_R": f.readout_side("R")}
    tag = "MANC" if fly == "MANC" else "MCNS"
    jobs = []
    for side in ("L", "R"):
        other = "R" if side == "L" else "L"
        for t in types:
            for s in B_SEEDS:
                own, oth = pa[(side, t, s)], pa[(other, t, s)]
                extra = [float(own["current"]) if own.get("usable") else None, float(oth["current"]) if oth.get("usable") else None]
                cur = list(GRID) + [c for c in extra if c is not None]
                j = _base_job(f"B1-{tag}-{side}|{t}|s{s}", s)
                j.update(kind="sweep_v4", W=Shared("W"), sizes=Shared("sizes"), readout=Shared(f"readout_{side}"), members=halves[side][t],
                         params={"mode": "standard"}, currents=cur, transplant={"own": extra[0], "other": extra[1]})
                jobs.append(j)
    return [(shared, jobs)], "reliability_v2"


# ------------------------------------------------------------------------------------------------------------ Blocks 2 and 3
def _ext_payload(fly: str):
    f = MR.fly(fly)
    mm = MR.mirror_map(f)
    e = MR.extend(f.C, f.sign, f.net.sizes, mm)
    em = MR.mirror(e, mm)
    real = mm.real_of()
    ro = {s: f.readout[real] & (mm.side == s) for s in ("L", "R")}
    sizes_real = np.asarray(f.net.sizes, np.float64)
    shared = {"src": MR.paired_source(mm), "sizes_real": sizes_real, "ro_L": ro["L"], "ro_R": ro["R"]}
    return f, mm, e, em, shared


def _ext_dict(e) -> dict:
    return {"C": e.C, "sign": e.sign, "sizes": e.sizes, "present": e.present}


def build_b2(k=None):
    """PREREG v4 B2.2-B2.4 (paired draws, seeds 0..7, analysed types): L on W, R on W, L on M, L on H_own(t), L on H_rest(t), L on
    the relabelling control, and 50 identity-hybrid jobs (B2.3 i)."""
    require_freeze("Block 2")
    fly = FLY[int(k)]
    f, mm, e, em, shared = _ext_payload(fly)
    halves = f.halves()
    types = [t for t in analysed_set()["analysed"] if t in halves["L"]]
    perm = np.random.default_rng(PERM_SEED).permutation(mm.n_ext)
    shared.update(W=e.W(), M=em.W(), sizes_W=e.sizes, sizes_M=em.sizes, eW=_ext_dict(e), eM=_ext_dict(em), perm=perm)
    tag = "MANC" if fly == "MANC" else "MCNS"
    P = _paired(mm.n_real)
    jobs, lw = [], []
    for t in types:
        slots = MR.left_slots(mm, halves["L"][t], halves["R"][t])
        for s in B_SEEDS:
            b = lambda arm: _base_job(f"B2-{tag}-{arm}|{t}|s{s}", s)  # noqa: E731
            j = b("LW")
            j.update(kind="group_v4", W=Shared("W"), sizes=Shared("sizes_W"), members=MR.stimulated(slots, e.present), readout=Shared("ro_L"), params=P)
            jobs.append(j)
            lw.append((t, s, slots))
            j = b("RW")
            j.update(kind="group_v4", W=Shared("W"), sizes=Shared("sizes_W"), members=list(halves["R"][t]), readout=Shared("ro_R"), params=P)
            jobs.append(j)
            j = b("LM")
            j.update(kind="group_v4", W=Shared("M"), sizes=Shared("sizes_M"), members=MR.stimulated(slots, em.present), readout=Shared("ro_L"),
                     params=P)
            jobs.append(j)
            for arm, base, other in (("OWN", "eW", "eM"), ("REST", "eM", "eW")):
                j = b(arm)
                j.update(kind="group_v4", hybrid={"base": Shared(base), "other": Shared(other), "cols": slots, "slots": slots},
                         readout=Shared("ro_L"), params=P)
                jobs.append(j)
            j = b("PERM")
            j.update(kind="group_v4", W=Shared("W"), sizes=Shared("sizes_W"), members=MR.stimulated(slots, e.present), readout=Shared("ro_L"),
                     params=P, perm=Shared("perm"))
            jobs.append(j)
    rng = np.random.default_rng(DET_SEED)
    for i in sorted(rng.choice(len(lw), size=min(50, len(lw)), replace=False).tolist()):
        t, s, slots = lw[i]
        j = _base_job(f"B2-{tag}-ID|{t}|s{s}", s)
        j.update(kind="group_v4", hybrid={"base": Shared("eW"), "other": Shared("eW"), "cols": slots, "slots": slots}, readout=Shared("ro_L"),
                 params=P)
        jobs.append(j)
    return [(shared, jobs)], "reliability_v2"


B3_CLASSES = (1, 2, 3, 4, 5)


def b3_variants(only: list[str] | None = None) -> dict[str, set[int]]:
    v = {f"A{c}": {c} for c in B3_CLASSES}
    v.update({f"O{c}": set(B3_CLASSES) - {c} for c in B3_CLASSES})
    return {k: s for k, s in v.items() if only is None or k in only}


def build_b3(k=None):
    """PREREG v4 B3.2: the ten MANC hybrids (each class alone A1..A5, each left out O1..O5), left side, paired, seeds 0..7, analysed
    types. k = 1. MaleCNS repeats (B3.4) use k = 2 and the variant list in reliability_v2/B3_MALECNS_CHOICE.json."""
    require_freeze("Block 3")
    fly = FLY[int(k)]
    f, mm, e, em, base_shared = _ext_payload(fly)
    halves = f.halves()
    types = [t for t in analysed_set()["analysed"] if t in halves["L"]]
    only = None
    if fly == "MaleCNS":
        only = json.loads((REL2 / "B3_MALECNS_CHOICE.json").read_text())["variants"]
    cache = MR.entry_classes(e, em, mm)
    tag = "MANC" if fly == "MANC" else "MCNS"
    P = _paired(mm.n_real)
    groups = []
    for name, cls in b3_variants(only).items():
        h = MR.hybrid(e, em, mm, cls, cache=cache)
        sh = dict(base_shared, W=h.W(), sizes=h.sizes)
        jobs = []
        for t in types:
            slots = MR.left_slots(mm, halves["L"][t], halves["R"][t])
            mem = MR.stimulated(slots, h.present)
            if not mem:
                continue
            for s in B_SEEDS:
                j = _base_job(f"B3-{tag}-{name}|{t}|s{s}", s)
                j.update(kind="group_v4", W=Shared("W"), sizes=Shared("sizes"), members=mem, readout=Shared("ro_L"), params=P)
                jobs.append(j)
        groups.append((sh, jobs))
    return groups, "reliability_v2"


def build_p4(k=None):
    """PREREG v4 X2, allowed before the freeze: the run 4 runner and workflow on (a) 4 locked B1r DNg100 jobs and 4 locked R4 jobs
    (digests must reproduce) and (b) the v4 kinds on the SYNTHETIC test circuit of `ledger/tests/test_v4_mirror.py` (must run
    without error). No real network is run with a new kind."""
    sys.path.insert(0, str(G.REPO / "ledger" / "tests"))
    import gha3r  # noqa: PLC0415
    import test_v4_mirror as T  # noqa: PLC0415

    AR_, MC, (fl, g1), _ = G._nets()
    b1r = G._v2_jobs("B1r", {"DNg100": g1["DNg100"]}, 1, AR, ModelConfig, seeds=[0, 1, 2, 3])
    for j in b1r:
        j["origin"] = "arms/GHA_b1r"
    r4_shared, r4_jobs = gha3r.build_r4()[0][0]
    pick = sorted(j["key"] for j in r4_jobs)[:: max(1, len(r4_jobs) // 4)][:4]
    r4 = [dict(j, origin="reliability/GHA_r4-run3") for j in r4_jobs if j["key"] in pick]
    f = T._synthetic_fly(seed=4, asym=0.6)
    mm = MR.mirror_map(f)
    e = MR.extend(f.C, f.sign, f.net.sizes, mm)
    em = MR.mirror(e, mm)
    real = mm.real_of()
    syn = {"W": e.W(), "M": em.W(), "sizes_W": e.sizes, "sizes_M": em.sizes, "eW": _ext_dict(e), "eM": _ext_dict(em),
           "ro_L": f.readout[real] & (mm.side == "L"), "ro_R": f.readout[real] & (mm.side == "R"), "src": MR.paired_source(mm),
           "sizes_real": f.net.sizes, "perm": np.random.default_rng(7).permutation(mm.n_ext), "Wreal": sp_csr(f.net.W)}
    slots = MR.left_slots(mm, [0, 1], [13, 14])
    P = _paired(mm.n_real)
    sj = []
    for s in range(2):
        j = _base_job(f"P4-SYN-LW|D|s{s}", s)
        j.update(kind="group_v4", W=Shared("W"), sizes=Shared("sizes_W"), members=MR.stimulated(slots, e.present), readout=Shared("ro_L"), params=P)
        sj.append(j)
        j = _base_job(f"P4-SYN-OWN|D|s{s}", s)
        j.update(kind="group_v4", hybrid={"base": Shared("eW"), "other": Shared("eM"), "cols": slots, "slots": slots}, readout=Shared("ro_L"), params=P)
        sj.append(j)
        j = _base_job(f"P4-SYN-PERM|D|s{s}", s)
        j.update(kind="group_v4", W=Shared("W"), sizes=Shared("sizes_W"), members=MR.stimulated(slots, e.present), readout=Shared("ro_L"),
                 params=P, perm=Shared("perm"))
        sj.append(j)
        j = _base_job(f"P4-SYN-SWEEP|D|s{s}", s)
        j.update(kind="sweep_v4", W=Shared("Wreal"), sizes=Shared("sizes_real"), members=[0, 1], readout=Shared("ro_L"), params={"mode": "standard"},
                 currents=[8.0, 64.0, 512.0])
        sj.append(j)
    fl_shared = {"W": fl.W, "sizes": fl.sizes, "readout": fl.readout}
    return [(fl_shared, b1r), (r4_shared, r4), (syn, sj)], "reliability_v2"


def sp_csr(W):
    import scipy.sparse as sp  # noqa: PLC0415

    return sp.csr_matrix(W, dtype=np.float64)


def p4_check(name: str = "p4-run4") -> dict:
    """Digests of the locked re-runs and errors of the synthetic jobs (gates_v4/P4_PIPELINE.json)."""
    new = {r["key"]: r for r in read_log(data_dir() / "reliability_v2" / f"GHA_{name}" / "results.pkl")}
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    items = []
    for f in sorted((G.GHA / name).glob("chunk_*.pkl")):
        items += pickle.loads(f.read_bytes())
    origin = {j["key"]: j.get("origin") for _, j in items}
    rows, ok = {}, True
    logs = {o: {r["key"]: r for r in read_log(data_dir() / o / "results.pkl")} for o in sorted({v for v in origin.values() if v})}
    for k in man["keys"]:
        r = new.get(k)
        if origin.get(k):
            same = r is not None and logs[origin[k]][k]["digest"] == r["digest"]
            rows[k] = "digest identical" if same else "DIFFERENT or missing"
            ok &= same
        else:
            good = r is not None and "error" not in r
            rows[k] = "ran" if good else f"ERROR {None if r is None else r.get('error')}"
            ok &= good
    meta = [json.loads(x) for x in (data_dir() / "reliability_v2" / f"GHA_{name}" / "gha_meta.jsonl").read_text().splitlines() if x.strip()]
    out = {"campaign": name, "jobs": rows, "numerics_digests": sorted({m["probe"]["numerics_digest"][:12] for m in meta}),
           "verdict": "pass" if ok else "fail"}
    _write_once(GATES4 / "P4_PIPELINE.json", out)
    print(json.dumps(out, indent=1))
    return out


RUN4_BUILDERS = {"pa": build_pa, "r4rep": build_r4rep, "b1s": build_b1s, "b2": build_b2, "b3": build_b3, "p4": build_p4}
G.BUILDERS.update(RUN4_BUILDERS)
RUN4_PREFIXES = set(RUN4_BUILDERS) | {"cn", "cg", "cx", "crw", "dx", "det4"}


# ------------------------------------------------------------------------------------------------ publish / collect / feeder
RUNNER_SIDE = [".github/workflows/ledger-gha4.yml", "ledger/scripts/gha_runner4.py", "ledger/src/brainir_ledger", "src/brainir",
               ".github/ledger_gha_pub.pem"]


def publish4(name: str, attempt: int = 0) -> None:
    if name.split("-")[0] not in RUN4_PREFIXES:
        raise SystemExit(f"{name}: not a run 4 campaign")
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    if man["n_chunks"] + 1 > MAX_JOBS:
        raise SystemExit(f"{name}: {man['n_chunks']} chunks + plan > {MAX_JOBS} jobs; re-pack with fewer chunks")
    G.sh("git", "fetch", "-q", "origin", "ledger/v1")
    origin = G.sh("git", "rev-parse", "origin/ledger/v1")
    if subprocess.run(["git", "diff", "--quiet", origin, "HEAD", "--", *RUNNER_SIDE], cwd=G.REPO).returncode != 0:
        raise SystemExit("runner-side code differs between origin/ledger/v1 and HEAD: push it first; refused")
    rel = f"ledgerdata-{name}"
    if subprocess.run(["gh", "release", "view", rel], cwd=G.REPO, capture_output=True).returncode != 0:
        assets = [str(p) for p in sorted((G.GHA / name).iterdir()) if p.is_file()]
        G.sh("gh", "release", "create", rel, *assets, "--target", origin, "--title", rel, "--prerelease",
             "--notes", "BrainIR ledger run 4: inputs of a GitHub Actions campaign (public connectome matrices and job specs only; "
                        "no result). Results come back encrypted. See research/ledger/LOG.md.")
    tag = f"gha4-run-{name}" + (f"-r{attempt}" if attempt else "")
    G.sh("git", "tag", tag, origin)
    G.sh("git", "push", "origin", tag)
    print("published", rel, "and pushed", tag, "at", origin[:12], "jobs", man["n_jobs"], "chunks", man["n_chunks"], flush=True)


def runs_for4(name: str) -> list[dict]:
    q = G.sh("gh", "api", "repos/{owner}/{repo}/actions/runs?per_page=100&event=push")
    runs = json.loads(q)["workflow_runs"]
    return [r for r in runs if r["head_branch"] == f"gha4-run-{name}" or r["head_branch"].startswith(f"gha4-run-{name}-r")]


def collect4(name: str, wait: bool) -> dict:
    """The frozen `gha.collect` with the run lookup pointed at run 4's tags (module attribute swap at run time; gha.py unchanged)."""
    G.runs_for = runs_for4
    return G.collect(name, wait)


def _campaign_of(branch: str) -> str:
    import re  # noqa: PLC0415

    for p in ("gha4-run-", "gha3-run-", "gha-run-"):
        if branch.startswith(p):
            return re.sub(r"-r[0-9]+$", "", branch[len(p):])
    return ""


def active_jobs() -> int:
    """Jobs of this repository's workflow runs that are not completed (every workflow), counted job by job. A campaign run whose
    matrix has not expanded yet (only its plan job listed) also counts its manifest's chunks; a run with no job listed yet counts
    MAX_JOBS + 1 (it blocks publishing until it expands)."""
    seen, n = set(), 0
    for st in ("queued", "in_progress", "waiting", "pending", "requested"):
        runs = json.loads(G.sh("gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs?per_page=100&status={st}"))["workflow_runs"]
        for r in runs:
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            jobs = json.loads(G.sh("gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs/{r['id']}/jobs?per_page=100"))["jobs"]
            if not jobs:
                n += MAX_JOBS + 1
                continue
            n += sum(1 for j in jobs if j["status"] != "completed")
            if all(j["name"] in ("plan", "probe") for j in jobs):
                man = G.GHA / _campaign_of(r["head_branch"]) / "manifest.json"
                n += json.loads(man.read_text())["n_chunks"] if man.is_file() else MAX_JOBS
    return n


def feeder(names: list[str], poll_s: int = 60) -> None:
    """Publish the named campaigns in order, each only when active jobs + its chunks + 1 <= 20 (hard limit 7)."""
    queue = [n for n in names]
    while queue:
        name = queue[0]
        need = json.loads((G.GHA / name / "manifest.json").read_text())["n_chunks"] + 1
        act = active_jobs()
        if act + need <= MAX_JOBS:
            publish4(name)
            queue.pop(0)
            time.sleep(45)  # let the run register before counting again
        else:
            print(time.strftime("%H:%M:%S"), f"active jobs {act}; waiting to publish {name} ({need} jobs)", flush=True)
            time.sleep(poll_s)


# ------------------------------------------------------------------------------------------------------------------- gates
def trust_compare(name: str) -> dict:
    """Run 2's trust comparison for a campaign of another name: every re-run job's digest against the locked result it reproduces
    (same logic as run 3's `gha3.trust_compare`, written to gates_v4)."""
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    new = {r["key"]: r for r in read_log(data_dir() / man["area"] / f"GHA_{name}" / "results.pkl")}
    items = []
    for f in sorted((G.GHA / name).glob("chunk_*.pkl")):
        items += pickle.loads(f.read_bytes())
    origin = {j["key"]: j["origin"] for _, j in items}
    orig = {o: {r["key"]: r for r in read_log(data_dir() / o / "results.pkl")} for o in sorted(set(origin.values()))}
    ident, bad = 0, []
    for k in man["keys"]:
        a, b = orig[origin[k]].get(k), new.get(k)
        if b is None:
            bad.append((k, "missing on runner"))
        elif a["digest"] == b["digest"]:
            ident += 1
        else:
            bad.append((k, "digest differs"))
    meta = [json.loads(x) for x in (data_dir() / man["area"] / f"GHA_{name}" / "gha_meta.jsonl").read_text().splitlines() if x.strip()]
    out = {"campaign": name, "n": len(man["keys"]), "identical": ident, "different": len(bad), "different_keys": bad,
           "by_origin": {o: sum(1 for k in man["keys"] if origin[k] == o) for o in sorted(set(origin.values()))},
           "numerics_digests": sorted({m["probe"]["numerics_digest"][:12] for m in meta}),
           "cpu_models": sorted({m["probe"]["host"]["cpu"]["cpu_model"] for m in meta}),
           "git_head_packed": man.get("git_head"),
           "verdict": "identical" if ident == len(man["keys"]) else "fail"}
    _write_once(GATES4 / "TRUST_GATE_v4.json", out)
    print(json.dumps({k: v for k, v in out.items() if k != "different_keys"}, indent=1))
    return out


def r4_compare(name: str = "r4rep-run4") -> dict:
    """PREREG v4 A1: the re-run R4 jobs against R4's locked digests."""
    new = {r["key"]: r for r in read_log(data_dir() / "reliability_v2" / f"GHA_{name}" / "results.pkl")}
    r4 = {r["key"]: r for r in read_log(data_dir() / "reliability" / "GHA_r4-run3" / "results.pkl")}
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    ident = sum(1 for k in man["keys"] if k in new and new[k]["digest"] == r4[k]["digest"])
    meta = [json.loads(x) for x in (data_dir() / "reliability_v2" / f"GHA_{name}" / "gha_meta.jsonl").read_text().splitlines() if x.strip()]
    out = {"campaign": name, "n": len(man["keys"]), "identical": ident, "missing": sorted(set(man["keys"]) - set(new)),
           "different": sorted(k for k in man["keys"] if k in new and new[k]["digest"] != r4[k]["digest"]),
           "numerics_digests": sorted({m["probe"]["numerics_digest"][:12] for m in meta}),
           "verdict": "identical" if ident == len(man["keys"]) else "fail"}
    _write_once(GATES4 / "R4_REPRODUCTION.json", out)
    print(json.dumps(out, indent=1))
    return out


def main() -> None:
    cmd = sys.argv[1:2]
    a = sys.argv[2:]
    if cmd == ["pack"]:
        name = a[0]
        if name.split("-")[0] not in RUN4_BUILDERS:
            raise SystemExit(f"{name}: no run 4 builder for this prefix")
        ch = int(a[a.index("--chunk-jobs") + 1])
        k = int(a[a.index("--k") + 1]) if "--k" in a else None
        G.pack(name, ch, k)
    elif cmd == ["publish4"]:
        publish4(a[0], int(a[a.index("--attempt") + 1]) if "--attempt" in a else 0)
    elif cmd == ["collect4"]:
        collect4(a[0], "--wait" in a)
    elif cmd == ["feeder"]:
        feeder(a)
    elif cmd == ["active-jobs"]:
        print(active_jobs())
    elif cmd == ["trust-compare"]:
        trust_compare(a[0])
    elif cmd == ["r4-compare"]:
        r4_compare(*(a[:1] or []))
    elif cmd == ["p4-check"]:
        p4_check(*(a[:1] or []))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
