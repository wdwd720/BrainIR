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


# ------------------------------------------------------------------------------------------------------------- determinism
def det_campaigns(stage: int) -> list[str]:
    """PREREG v4 X3: the campaigns re-sampled by the determinism campaign of a stage (only those that exist when it is packed)."""
    plan = {1: ["pa-manc-run4", "pa-mcns-run4"],
            2: ["b1s-manc-run4", "b1s-mcns-run4", "b2-manc-run4", "b2-mcns-run4"],
            3: ["b3-manc-run4", "b3-mcns-run4", "cn-run4", "fl-1-run4", "fl-3-run4", "fl-10-run4"],
            4: ["cg-run4", "crw-run4"] + [f"cx-{x}-run4" for x in ("1", "3a", "3b", "4", "5a", "5b", "6", "7", "8", "9")],
            5: [f"dx-{x}-run4" for x in ("1", "3a", "3b", "4", "5a", "5b", "6", "7", "8", "9")]}[int(stage)]
    return [c for c in plan if (G.GHA / c / "manifest.json").is_file()]


def build_det4(k=None):
    """PREREG v4 X3: 20 jobs of every campaign of stage k drawn with default_rng(20261405) from its packed jobs, re-run with the same
    specification and payload; keys prefixed `D4~<campaign>~`."""
    import zlib  # noqa: PLC0415

    require_freeze("determinism")
    groups = []
    for c in det_campaigns(int(k)):
        items = []
        for f in sorted((G.GHA / c).glob("chunk_*.pkl")):
            items += pickle.loads(f.read_bytes())
        keys = sorted(j["key"] for _, j in items)
        pick = set(np.random.default_rng(DET_SEED).choice(keys, size=min(20, len(keys)), replace=False).tolist())
        by_payload: dict[str, list] = {}
        for pkey, j in items:
            if j["key"] in pick:
                by_payload.setdefault(pkey, []).append(dict(j, key=f"D4~{c}~{j['key']}", origin_campaign=c, origin_key=j["key"]))
        for pkey, jobs in by_payload.items():
            shared = pickle.loads(zlib.decompress((G.GHA / c / f"payload_{pkey}.bin").read_bytes()))
            groups.append((shared, jobs))
    return groups, "reliability_v2"


def det_compare(stage: int) -> dict:
    """Digests of the determinism re-runs against the originals (`digest_v4` where the kind has it, else run 1's `digest`)."""
    name = f"det4-{stage}-run4"
    new = {r["key"]: r for r in read_log(data_dir() / "reliability_v2" / f"GHA_{name}" / "results.pkl")}
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    rows, ok = {}, True
    cache: dict[str, dict] = {}
    for k in man["keys"]:
        _, c, ok_key = k.split("~", 2)
        if c not in cache:
            area = json.loads((G.GHA / c / "manifest.json").read_text())["area"]
            cache[c] = {r["key"]: r for r in read_log(data_dir() / area / f"GHA_{c}" / "results.pkl")}
        a, b = cache[c].get(ok_key), new.get(k)
        fld = "digest_v4" if (a is not None and "digest_v4" in a) else "digest"
        same = a is not None and b is not None and a.get(fld) == b.get(fld)
        rows.setdefault(c, {"n": 0, "identical": 0})
        rows[c]["n"] += 1
        rows[c]["identical"] += int(same)
        ok &= same
    out = {"campaign": name, "by_campaign": rows, "verdict": "identical" if ok else "fail"}
    _write_once(GATES4 / f"DETERMINISM_stage{stage}.json", out)
    print(json.dumps(out, indent=1))
    return out


# ------------------------------------------------------------------------------------------------------------- count noise
NOISE_SEEDS = {"P1": 20261411, "P2": 20261412, "N1": 20261421, "N2": 20261422}


def _noise_ext(C, f, mm):
    e = MR.extend(C, f.sign, f.net.sizes, mm)
    return e


def build_cn(k=None):
    """PREREG v4 B4.2-B4.3 (MANC): two Poisson copies and two negative-binomial copies (dispersion 1/k measured from the left-right
    homologous raw counts, recorded in gates_v4/NB_DISPERSION.json at pack time), floor 5, the left screen on each (paired draws,
    seeds 0..7, analysed types)."""
    require_freeze("count noise")
    from brainir_ledger import fixes as FX  # noqa: PLC0415

    f = MR.fly("MANC")
    mm = MR.mirror_map(f)
    C1 = FX.manc_raw_counts()
    nb = FX.nb_inverse_k(C1, mm)
    p = GATES4 / "NB_DISPERSION.json"
    if not p.exists():
        _write_once(p, {"rule": "PREREG v4 B4.3", **nb})
    halves = f.halves()
    types = [t for t in analysed_set()["analysed"] if t in halves["L"]]
    shared0 = {"src": MR.paired_source(mm), "sizes_real": np.asarray(f.net.sizes, np.float64),
               "ro_L": f.readout[mm.real_of()] & (mm.side == "L")}
    P = _paired(mm.n_real)
    groups = []
    for name, seed in NOISE_SEEDS.items():
        raw = FX.poisson_copy(C1, seed) if name[0] == "P" else FX.nb_copy(C1, nb["inv_k"], seed)
        e = _noise_ext(FX.at_floor(raw, 5), f, mm)
        sh = dict(shared0, W=e.W(), sizes=e.sizes)
        jobs = []
        for t in types:
            mem = MR.stimulated(MR.left_slots(mm, halves["L"][t], halves["R"][t]), e.present)
            for s in B_SEEDS:
                j = _base_job(f"CN-{name}|{t}|s{s}", s)
                j.update(kind="group_v4", W=Shared("W"), sizes=Shared("sizes"), members=mem, readout=Shared("ro_L"), params=P)
                jobs.append(j)
        groups.append((sh, jobs))
    return groups, "reliability_v2"


def build_fl(k=None):
    """PREREG v4 B4.4 (MANC): the network rebuilt at floor k (1, 3 or 10) from the raw counts; L on W_f and L on M_f (= R on W_f),
    paired draws, seeds 0..7, analysed types."""
    require_freeze("floors")
    from brainir_ledger import fixes as FX  # noqa: PLC0415

    fl_ = int(k)
    if fl_ not in (1, 3, 10):
        raise SystemExit("--k must be 1, 3 or 10 (floor 5 is Block 2's baseline)")
    f = MR.fly("MANC")
    mm = MR.mirror_map(f)
    e = _noise_ext(FX.at_floor(FX.manc_raw_counts(), fl_), f, mm)
    em = MR.mirror(e, mm)
    halves = f.halves()
    types = [t for t in analysed_set()["analysed"] if t in halves["L"]]
    sh = {"W": e.W(), "M": em.W(), "sizes_W": e.sizes, "sizes_M": em.sizes, "src": MR.paired_source(mm),
          "sizes_real": np.asarray(f.net.sizes, np.float64), "ro_L": f.readout[mm.real_of()] & (mm.side == "L")}
    P = _paired(mm.n_real)
    jobs = []
    for t in types:
        slots = MR.left_slots(mm, halves["L"][t], halves["R"][t])
        for s in B_SEEDS:
            for arm, W, sz, pres in (("LW", "W", "sizes_W", e.present), ("LM", "M", "sizes_M", em.present)):
                j = _base_job(f"FL-{fl_}-{arm}|{t}|s{s}", s)
                j.update(kind="group_v4", W=Shared(W), sizes=Shared(sz), members=MR.stimulated(slots, pres), readout=Shared("ro_L"), params=P)
                jobs.append(j)
    return [(sh, jobs)], "reliability_v2"


# ------------------------------------------------------------------------------------------------------------------ Part C
NET_FIXES = ("3a", "3b", "4", "5a", "5b", "6", "7", "8")
GAINS = (1.0, 0.5, 0.75, 1.5, 2.0, 3.0)
FIX_K = {31: "3a", 32: "3b", 4: "4", 51: "5a", 52: "5b", 6: "6", 7: "7", 8: "8", 1: "1", 2: "2", 9: "9"}


def fixed_network(fix: str, fly: str):
    """(W, sizes) of fly `fly` under network fix `fix` ('0' = unfixed), PREREG v4 C2 (`brainir_ledger.fixes`)."""
    import scipy.sparse as sp  # noqa: PLC0415

    from brainir_ledger import fixes as FX  # noqa: PLC0415

    f = MR.fly(fly)
    if fix in ("0", "1", "2"):
        return sp.csr_matrix(f.net.W, dtype=np.float64), np.asarray(f.net.sizes, np.float64)
    return FX.apply_fix(fix, f, MR.mirror_map(f))


def _std(job: dict, gain: float) -> dict:
    job.update(kind="group_v4", params={"mode": "standard"}, gain=float(gain), extras={"readout_traces": True})
    return job


def build_cg(k=None):
    """PREREG v4 C4: DNg100 (both members, whole type, all front-leg motor neurons), seeds 0..15, every fix at every gain, both flies
    (3a/3b MANC only). Network fixes: the screen on the fixed network times the gain; fix 2: the screen with traces on the unfixed
    network times the gain (pooled score from the traces); fix 1: grid sweeps on the unfixed network times the gain."""
    require_freeze("Part C gains")
    groups = []
    for fly in ("MANC", "MaleCNS"):
        f = MR.fly(fly)
        tag = "MANC" if fly == "MANC" else "MCNS"
        dng = f.groups["DNg100"]
        for fix in ("0",) + NET_FIXES:
            if fix in ("3a", "3b") and fly != "MANC":
                continue
            W, sizes = fixed_network(fix, fly)
            sh = {"W": W, "sizes": sizes, "readout": f.readout}
            jobs = []
            for g in GAINS:
                names = ("1", "2") if fix == "0" else (fix,)
                for nm in names:
                    for s in A_SEEDS:
                        j = _base_job(f"CG-{nm}-g{g:g}-{tag}|DNg100|s{s}", s)
                        j.update(W=Shared("W"), sizes=Shared("sizes"), readout=Shared("readout"), members=list(dng))
                        if nm == "1":
                            j.update(kind="sweep_v4", params={"mode": "standard"}, gain=float(g), currents=list(GRID))
                        else:
                            _std(j, g)
                        jobs.append(j)
            groups.append((sh, jobs))
    return groups, "reliability_v2"


def c_gains(name: str = "cg-run4") -> dict:
    """PREREG v4 C4 from the DNg100-only campaign: per fix the gain used (1 if it passes, else the smallest passing gain of 0.5, 0.75,
    1.5, 2, 3), or 'fails'. Pass = score >= 0.5 in >= 12 of 16 seeds on both flies (3a/3b: MANC only), unusable = < 0.5; fix 1 uses
    the best in-bounds grid score, fix 2 the pooled score of the summed read-out signal."""
    from brainir_ledger import pooled  # noqa: PLC0415

    res = {r["key"]: r for r in read_log(data_dir() / "reliability_v2" / f"GHA_{name}" / "results.pkl")}

    def score(r, nm):
        if nm == "1":
            ib = [x["score"] for x in r["runs"] if x["in_bounds"]]
            return max(ib) if ib else 0.0
        if not r.get("usable"):
            return 0.0
        return pooled.pooled_score(r) if nm == "2" else float(r["score"] or 0.0)

    out = {}
    for nm in ("1", "2") + NET_FIXES:
        flies = ("MANC",) if nm in ("3a", "3b") else ("MANC", "MCNS")
        per_gain = {}
        for g in GAINS:
            ok = {}
            for tag in flies:
                vals = [score(res[f"CG-{nm}-g{g:g}-{tag}|DNg100|s{s}"], nm) for s in A_SEEDS]
                ok[tag] = int(sum(v >= 0.5 for v in vals))
            per_gain[f"{g:g}"] = {"n_ge_0.5": ok, "pass": all(v >= 12 for v in ok.values())}
        if per_gain["1"]["pass"]:
            chosen = 1.0
        else:
            passing = [g for g in GAINS[1:] if per_gain[f"{g:g}"]["pass"]]
            chosen = min(passing) if passing else None
        out[nm] = {"per_gain": per_gain, "gain": chosen, "verdict": "pass" if chosen is not None else "fails"}
    _write_once(GATES4 / "C_GAINS.json", {"rule": "PREREG v4 C4", "fixes": out})
    print(json.dumps({k: (v["gain"], v["verdict"]) for k, v in out.items()}))
    return out


def _gain_of(fix: str) -> float:
    g = json.loads((GATES4 / "C_GAINS.json").read_text())["fixes"][fix]["gain"]
    if g is None:
        raise SystemExit(f"fix {fix} failed its DNg100 control at every gain: not screened (C4)")
    return float(g)


def build_crw(k=None):
    """PREREG v4 C5: the unfixed rewired control (B1-ctl-rewire-101's network), left side, analysed types, seeds 0..7, R4's job
    specification (traces stored, for fix 2)."""
    require_freeze("Part C rewired control")
    from brainir_ledger import fixes as FX  # noqa: PLC0415

    f = MR.fly("MANC")
    rf = FX.rewired_fly(f)
    halves = f.halves()
    types = [t for t in analysed_set()["analysed"] if t in halves["L"]]
    import scipy.sparse as sp  # noqa: PLC0415

    W = sp.csr_matrix(rf.C.multiply(rf.sign[None, :]), dtype=np.float64)
    shared = {"W": W, "sizes": f.net.sizes, "readout_L": f.readout_side("L")}
    jobs = [dict(j, readout=Shared("readout_L")) for j in _v2_jobs("CRW-MANC-L", {t: halves["L"][t] for t in types}, B_SEEDS)]
    return [(shared, jobs)], "reliability_v2"


def build_cx(k=None):
    """PREREG v4 C5: one fix (k: 31 = 3a, 32 = 3b, 4, 51 = 5a, 52 = 5b, 6, 7, 8; 1 = fix 1's rewired-control sweep) at its gain from
    gates_v4/C_GAINS.json: the four half-flies (MaleCNS except 3a/3b) and the rewired control (left), analysed types, seeds 0..7,
    standard parameters."""
    require_freeze("Part C fix screens")
    import scipy.sparse as sp  # noqa: PLC0415

    from brainir_ledger import fixes as FX  # noqa: PLC0415

    fix = FIX_K[int(k)]
    g = _gain_of(fix)
    types_all = analysed_set()["analysed"]
    groups = []
    fm = MR.fly("MANC")
    rf = FX.rewired_fly(fm)
    if fix == "1":
        hm = fm.halves()
        types = [t for t in types_all if t in hm["L"]]
        W = sp.csr_matrix(rf.C.multiply(rf.sign[None, :]), dtype=np.float64)
        sh = {"W": W, "sizes": fm.net.sizes, "readout_L": fm.readout_side("L")}
        jobs = []
        for t in types:
            for s in B_SEEDS:
                j = _base_job(f"CX-1-RW-MANC-L|{t}|s{s}", s)
                j.update(kind="sweep_v4", W=Shared("W"), sizes=Shared("sizes"), readout=Shared("readout_L"), members=hm["L"][t],
                         params={"mode": "standard"}, gain=g, currents=list(GRID))
                jobs.append(j)
        return [(sh, jobs)], "reliability_v2"
    for fly in ("MANC", "MaleCNS"):
        if fix in ("3a", "3b") and fly != "MANC":
            continue
        f = MR.fly(fly)
        h = f.halves()
        types = [t for t in types_all if t in h["L"]]
        W, sizes = fixed_network(fix, fly)
        sh = {"W": W, "sizes": sizes, "readout_L": f.readout_side("L"), "readout_R": f.readout_side("R")}
        tag = "MANC" if fly == "MANC" else "MCNS"
        jobs = []
        for side in ("L", "R"):
            for t in types:
                for s in B_SEEDS:
                    j = _base_job(f"CX-{fix}-{tag}-{side}|{t}|s{s}", s)
                    j.update(W=Shared("W"), sizes=Shared("sizes"), readout=Shared(f"readout_{side}"), members=h[side][t])
                    jobs.append(_std(j, g))
        groups.append((sh, jobs))
    # the rewired control with the fix applied (left side); not for the floors: a rewired network has no pre-floor counts (C2.3)
    if fix in ("3a", "3b"):
        return groups, "reliability_v2"
    W, sizes = FX.apply_fix(fix, rf, MR.mirror_map(fm))
    sh = {"W": W, "sizes": sizes, "readout_L": fm.readout_side("L")}
    hm = fm.halves()
    jobs = []
    for t in [t for t in types_all if t in hm["L"]]:
        for s in B_SEEDS:
            j = _base_job(f"CX-{fix}-RW-MANC-L|{t}|s{s}", s)
            j.update(W=Shared("W"), sizes=Shared("sizes"), readout=Shared("readout_L"), members=hm["L"][t])
            jobs.append(_std(j, g))
    groups.append((sh, jobs))
    return groups, "reliability_v2"


def build_dx(k=None):
    """PREREG v4 Part D (EXPLORATORY): exam 1's whole-type screen on the fixed MANC network at the fix's gain, all 321 B1r types, seeds
    0..7 (k as build_cx; fix 1: whole-type grid sweeps on the unfixed network; fix 2 needs no run: B1r's stored traces)."""
    require_freeze("Part D")
    fix = FIX_K[int(k)]
    g = _gain_of(fix)
    _, _, (fl, g1), _ = G._nets()
    W, sizes = fixed_network(fix if fix != "1" else "0", "MANC")
    sh = {"W": W, "sizes": sizes, "readout": fl.readout}
    jobs = []
    for t, m in sorted(g1.items()):
        for s in B_SEEDS:
            j = _base_job(f"DX-{fix}|{t}|s{s}", s)
            j.update(W=Shared("W"), sizes=Shared("sizes"), readout=Shared("readout"), members=list(m))
            if fix == "1":
                j.update(kind="sweep_v4", params={"mode": "standard"}, gain=g, currents=list(GRID))
            else:
                _std(j, g)
            jobs.append(j)
    return [(sh, jobs)], "reliability_v2"


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
           "sizes_real": f.net.sizes, "perm": np.random.default_rng(7).permutation(mm.n_ext), "Wreal": sp_csr(f.net.W),
           "ro_L_real": f.readout & (f.side == "L")}  # p4-run4 used ro_L (extended) for the sweep: a test-spec error (LOG)
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
        j.update(kind="sweep_v4", W=Shared("Wreal"), sizes=Shared("sizes_real"), members=[0, 1], readout=Shared("ro_L_real"), params={"mode": "standard"},
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
    _write_once(GATES4 / ("P4_PIPELINE.json" if name == "p4-run4" else f"P4_PIPELINE_{name}.json"), out)
    print(json.dumps(out, indent=1))
    return out


RUN4_BUILDERS = {"pa": build_pa, "r4rep": build_r4rep, "b1s": build_b1s, "b2": build_b2, "b3": build_b3, "p4": build_p4,
                 "p4b": build_p4, "cg": build_cg, "crw": build_crw, "cx": build_cx, "dx": build_dx, "cn": build_cn, "fl": build_fl,
                 "det4": build_det4}
G.BUILDERS.update(RUN4_BUILDERS)
RUN4_PREFIXES = set(RUN4_BUILDERS)


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
    elif cmd == ["c-gains"]:
        c_gains(*(a[:1] or []))
    elif cmd == ["det-compare"]:
        det_compare(int(a[0]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
