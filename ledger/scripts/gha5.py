"""Run 5 campaigns on GitHub Actions (RUN5_PROMPT hard limit 7; PREREG v5 Part X): registers run 5's builders with the frozen `gha.py`
(pack) and runs them through run 4's runner and workflow unchanged (`gha_runner4.py`, `.github/workflows/ledger-gha4.yml`, tags
`gha4-run-<name>`), published with `publish5` and collected with run 4's `collect4`. No frozen file is edited: run 4's helpers are
used as they are, with module attribute swaps at run time where a name check would refuse a run 5 campaign.

- The trust gate (Stage 0) is run 1's 100 locked jobs packed and published with the frozen `gha.py` (run 2's workflow); `trust-compare`
  writes `gates_v5/TRUST_GATE_v5.json`.
- Hard limit 1 (declare first): every run 5 builder refuses before the tag `ledger-prereg-v5` exists and `LOCK_prereg_v5.json` verifies.
- Hard limit 7: at most 20 GitHub jobs queued or running (the campaign's chunks + its plan job count); `publish5` refuses otherwise.

    uv run --project ledger --no-sync python ledger/scripts/gha5.py trust-compare trust-run5     # -> gates_v5/TRUST_GATE_v5.json
    uv run --project ledger --no-sync python ledger/scripts/gha5.py pack s0-run5 --chunk-jobs 120            # Part S regression + timing
    uv run --project ledger --no-sync python ledger/scripts/gha5.py pack ps-b1-run5 --chunk-jobs 300 --k 1    # Part S copies (block k = copies 4k-3 .. 4k)
    uv run --project ledger --no-sync python ledger/scripts/gha5.py pack pt-manc-run5 --chunk-jobs 300 --k 1  # Part T (k 1 MANC; pt-mcns-run5 --k 2 MaleCNS)
    uv run --project ledger --no-sync python ledger/scripts/gha5.py publish5 s0-run5
    uv run --project ledger --no-sync python ledger/scripts/gha5.py collect5 s0-run5 [--wait]
    uv run --project ledger --no-sync python ledger/scripts/gha5.py active-jobs
    uv run --project ledger --no-sync python ledger/scripts/gha5.py runner-hours     # hard limit 7 (step time, LOG L102)

Campaign names: `<prefix>-<label>-run5`; prefixes s0 (PREREG v5 S0), ps (S1-S4; --k b = copies 4b-3 .. 4b), pt (Part T; --k 1 MANC,
2 MaleCNS), det5 (X4; --k = stage in DET5_STAGES), psr / ptr (S8: full re-runs of a ps / pt campaign under another name).
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gha as G  # noqa: E402
import gha4 as G4  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

GATES5 = RESEARCH / "gates_v5"
MAX_JOBS = 20
PERTYPE = RESEARCH / "pertype_v1"
COPY_SEEDS = tuple(range(20261511, 20261527))   # PREREG v5 S1: copies 1..16
SAMPLE_SEED_S = 20261527                         # S2: the 40 non-drivers
DET_SEED = 20261529                              # X4: 20 random jobs per campaign
S_SEEDS = tuple(range(8))                        # S3
T_SEEDS = tuple(range(16))                       # Part T
DET5_STAGES: dict[int, list[str]] = {            # X4: the campaigns re-sampled by each determinism re-run (20 jobs each)
    1: ["s0-run5", "ps-b1-run5", "ps-b2-run5", "ps-b3-run5", "ps-b4-run5"],
    2: ["pt-manc-run5", "pt-mcns-run5"],
}


def require_freeze5(what: str) -> None:
    """PREREG v5 X1 / RUN5_PROMPT hard limit 1: nothing governed by the rulebook runs before the freeze."""
    import subprocess  # noqa: PLC0415

    if subprocess.run(["git", "rev-parse", "-q", "--verify", "refs/tags/ledger-prereg-v5"], cwd=G.REPO, capture_output=True).returncode != 0:
        raise SystemExit(f"{what}: the tag ledger-prereg-v5 does not exist; refused (declare first)")
    import lock5  # noqa: PLC0415

    if lock5.check(RESEARCH / "LOCK_prereg_v5.json") != 0:
        raise SystemExit(f"{what}: LOCK_prereg_v5.json does not verify; refused")


def part_s_types() -> dict[str, list[str]]:
    """PREREG v5 S2: every B1r or A1 driver (pertype tables), plus 40 drivers of neither (frame = A1's 321 types minus those)."""
    import numpy as np  # noqa: PLC0415
    import pandas as pd  # noqa: PLC0415

    b1 = pd.read_csv(PERTYPE / "B1r.csv", dtype={"manc_type": str}).set_index("manc_type")["score"]
    a1 = pd.read_csv(PERTYPE / "A1.csv", dtype={"manc_type": str}).set_index("manc_type")["score"]
    drivers = sorted(set(b1[b1 >= 0.5].index) | set(a1[a1 >= 0.5].index))
    frame = sorted(set(a1.index) - set(drivers))
    sample = sorted(np.random.default_rng(SAMPLE_SEED_S).choice(frame, 40, replace=False).tolist())
    return {"drivers": drivers, "b1r_drivers": sorted(b1[b1 >= 0.5].index), "a1_drivers": sorted(a1[a1 >= 0.5].index),
            "nondriver_sample": sample, "frame_size": len(frame)}


_NETS = None


def nets():
    """The frozen `gha._nets()` (B1r's MANC front-leg network and type groups, B2r's MaleCNS network and groups), loaded once."""
    global _NETS  # noqa: PLW0603
    if _NETS is None:
        _NETS = G._nets()
    return _NETS


def b1r_jobs(prefix: str, groups: dict, seeds) -> list[dict]:
    """PREREG v5 S3: B1r's job specification exactly (`gha._v2_jobs`: run 2's kind `group_v2`, tuner v2 with K = 1, B1's screen
    configuration `b1_screen_cfg(10)`, T = 1 s, read-out traces as B1r), keys `<prefix>|<group>|s<seed>`."""
    AR, MC, _, _ = nets()
    return G._v2_jobs(prefix, groups, 1, AR, MC, seeds=[int(s) for s in seeds])


def manc_matrix(seed: int | None):
    """B1r's signed matrix rebuilt from MANC's raw counts at floor 5 (seed None; must equal B1r's matrix entry for entry, same CSR
    structure) or of the Poisson copy with that seed, floor 5 applied after resampling (PREREG v5 S1), as float64 CSR."""
    import numpy as np  # noqa: PLC0415

    from brainir_ledger import fixes as FX  # noqa: PLC0415
    from brainir_ledger import mirror as MR  # noqa: PLC0415

    C1 = FX.manc_raw_counts()
    raw = C1 if seed is None else FX.poisson_copy(C1, int(seed))
    W = FX.signed(FX.at_floor(raw, 5), MR.fly("MANC").sign).tocsr().astype(np.float64)
    W.sort_indices()
    if seed is None:
        fl = nets()[2][0]
        A = fl.W
        same = (A.shape == W.shape and A.nnz == W.nnz and np.array_equal(A.indptr, W.indptr) and np.array_equal(A.indices, W.indices)
                and np.array_equal(A.data, W.data))
        if not same:
            raise SystemExit("floor 5 of MANC's raw counts does not reproduce B1r's signed matrix exactly; refused")
    return W


def build_s0(k=None):
    """PREREG v5 S0: B1r's job specification on the matrix rebuilt from the raw counts at floor 5 (= B1r's matrix), every Part S
    type, seeds 0..7; compared with B1r's stored per-seed results by `s0-compare` (digest identity)."""
    require_freeze5("Part S regression")
    _, _, (fl, g1), _ = nets()
    types = part_s_types()
    sh = {"W": manc_matrix(None), "sizes": fl.sizes, "readout": fl.readout}
    jobs = b1r_jobs("S0", {t: g1[t] for t in types["drivers"] + types["nondriver_sample"]}, S_SEEDS)
    return [(sh, jobs)], "replication_v1"


X3_FILE = GATES5 / "X3_BUDGET.json"


def x3_decide(projected_runner_hours: float, reason: str) -> dict:
    """PREREG v5 X3, after S0 and before any copy campaign is published: 16 copies unless the projection passes 95 runner-hours (then 8);
    Part T only if it stays at or below 80. Written once."""
    out = {"rule": "PREREG v5 X3", "projected_runner_hours_remaining": projected_runner_hours, "copies": 8 if projected_runner_hours > 95 else 16,
           "part_t": projected_runner_hours <= 80, "reason": reason, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    _write_once(X3_FILE, out)
    print(json.dumps(out, indent=1))
    return out


def build_ps(k=None):
    """PREREG v5 S1-S3: copies 4k-3 .. 4k (seeds COPY_SEEDS), every Part S type, B1r's job specification, seeds 0..7. Refuses before the
    S0 gate has passed and before X3's decision is written, and beyond X3's number of copies (S8)."""
    require_freeze5("Part S copies")
    s0 = GATES5 / "S0_REGRESSION.json"
    if not s0.exists() or json.loads(s0.read_text())["verdict"] not in ("identical", "equivalent"):
        raise SystemExit("Part S copies: the S0 regression gate has not passed; refused")
    if not X3_FILE.exists():
        raise SystemExit("Part S copies: X3's budget decision is not written (gha5.py x3 HOURS --reason TEXT); refused")
    if 4 * int(k) > json.loads(X3_FILE.read_text())["copies"]:
        raise SystemExit(f"Part S copies: X3 chose {json.loads(X3_FILE.read_text())['copies']} copies; block {k} refused")
    _, _, (fl, g1), _ = nets()
    types = part_s_types()
    groups = []
    for c in range(4 * int(k) - 3, 4 * int(k) + 1):
        sh = {"W": manc_matrix(COPY_SEEDS[c - 1]), "sizes": fl.sizes, "readout": fl.readout}
        groups.append((sh, b1r_jobs(f"PS-c{c:02d}", {t: g1[t] for t in types["drivers"] + types["nondriver_sample"]}, S_SEEDS)))
    return groups, "replication_v1"


def part_t_types() -> list[str]:
    """PREREG v5 Part T: every type that is a driver in B1r, B2r or A1 (pertype tables)."""
    import pandas as pd  # noqa: PLC0415

    out = set()
    for arm in ("B1r", "B2r", "A1"):
        d = pd.read_csv(PERTYPE / f"{arm}.csv", dtype={"manc_type": str})
        out |= set(d.loc[d["score"] >= 0.5, "manc_type"])
    return sorted(out)


def build_pt(k=None):
    """PREREG v5 Part T: every copy of every Part T type stimulated alone with B1r's job specification, seeds 0..15, on the real
    network of fly k (1 = B1r's MANC front-leg network, 2 = B2r's MaleCNS network, as `gha.build_b1r` / `build_b2r`); group key
    `<type>#<bodyId>`. Refuses unless X3 allowed Part T."""
    require_freeze5("Part T")
    if not X3_FILE.exists() or not json.loads(X3_FILE.read_text())["part_t"]:
        raise SystemExit("Part T: X3's decision is missing or dropped Part T; refused")
    _, _, (fl, g1), (net2, g2) = nets()
    net, g, tag = (fl, g1, "MANC") if int(k) == 1 else (net2, g2, "MCNS")
    bid = net.table["bodyId"].to_numpy()
    groups = {f"{t}#{int(bid[m])}": [int(m)] for t in part_t_types() if t in g for m in g[t]}
    return [({"W": net.W, "sizes": net.sizes, "readout": net.readout}, b1r_jobs(f"PT-{tag}", groups, T_SEEDS))], "replication_v1"


def build_det5(k=None):
    """PREREG v5 X4: 20 jobs of every campaign of determinism stage k, drawn with default_rng(20261529) from its packed jobs, re-run
    with the same specification and payload; keys prefixed `D5~<campaign>~` (as run 4's `build_det4`)."""
    import zlib  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415

    require_freeze5("determinism re-run")
    groups = []
    for c in DET5_STAGES[int(k)]:
        items = []
        for f in sorted((G.GHA / c).glob("chunk_*.pkl")):
            items += pickle.loads(f.read_bytes())
        keys = sorted(j["key"] for _, j in items)
        pick = set(np.random.default_rng(DET_SEED).choice(keys, size=min(20, len(keys)), replace=False).tolist())
        by_payload: dict[str, list] = {}
        for pkey, j in items:
            if j["key"] in pick:
                by_payload.setdefault(pkey, []).append(dict(j, key=f"D5~{c}~{j['key']}", origin_campaign=c, origin_key=j["key"]))
        for pkey, jobs in by_payload.items():
            shared = pickle.loads(zlib.decompress((G.GHA / c / f"payload_{pkey}.bin").read_bytes()))
            groups.append((shared, jobs))
    return groups, "replication_v1"


def det_compare(stage: int) -> dict:
    """X4: the re-runs' digests against the originals' (`digest_v4` where the kind has it, else run 2's `digest`)."""
    name = f"det5-{stage}-run5"
    new = {r["key"]: r for r in read_log(data_dir() / "replication_v1" / f"GHA_{name}" / "results.pkl")}
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    rows, ok, cache = {}, True, {}
    for key in man["keys"]:
        _, c, okey = key.split("~", 2)
        if c not in cache:
            area = json.loads((G.GHA / c / "manifest.json").read_text())["area"]
            cache[c] = {r["key"]: r for r in G4.load_results(c, area)}
        a, b = cache[c].get(okey), new.get(key)
        fld = "digest_v4" if (a is not None and "digest_v4" in a) else "digest"   # group_v2 jobs carry run 2's digest only
        same = a is not None and b is not None and a.get(fld) == b.get(fld)
        rows.setdefault(c, {"n": 0, "identical": 0})
        rows[c]["n"] += 1
        rows[c]["identical"] += int(same)
        ok &= same
    out = {"campaign": name, "by_campaign": rows, "verdict": "identical" if ok else "fail"}
    _write_once(GATES5 / f"DETERMINISM_v5_stage{stage}.json", out)
    print(json.dumps(out, indent=1))
    return out


S0_FIELDS = ("usable", "current", "n_tuning_runs", "n_active_all", "n_high_fr", "n_active_readout", "n_active_notebook", "frequency_hz")


def _same_field(a, b) -> bool:
    import math  # noqa: PLC0415

    fa = None if a is None or (isinstance(a, float) and math.isnan(a)) else a
    fb = None if b is None or (isinstance(b, float) and math.isnan(b)) else b
    if fa is None or fb is None:
        return fa is None and fb is None
    if isinstance(fa, bool) or isinstance(fb, bool):
        return bool(fa) == bool(fb)
    return float(fa) == float(fb)


def s0_compare(name: str = "s0-run5") -> dict:
    """PREREG v5 S0: every regression job against B1r's stored per-seed result. Pass = digest identical, or (digest differs) every stored
    field equal and |score difference| < 1e-9 ('equivalent', differing fields shown); anything else fails. Also the job times (X2)."""
    import statistics  # noqa: PLC0415

    import pandas as pd  # noqa: PLC0415

    new = {r["key"]: r for r in G4.load_results(name, "replication_v1")}
    b1 = pd.read_parquet(RESEARCH / "predictions_v2" / "B1r" / "replicates.parquet").set_index(["manc_type", "seed"])
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    ident, equiv, bad = 0, [], []
    for key in man["keys"]:
        _, t, s = key.split("|")
        a, b = b1.loc[(t, int(s[1:]))], new.get(key)
        if b is None or "error" in b:
            bad.append({"key": key, "problem": "missing" if b is None else f"error: {b.get('error')}"})
            continue
        if b.get("digest") == a["digest"]:
            ident += 1
            continue
        ex = b.get("extras") or {}
        got = {f: (ex.get(f) if f == "n_active_notebook" and f not in b else b.get(f)) for f in S0_FIELDS}
        diff = [f for f in S0_FIELDS if not _same_field(a[f], got[f])]
        sa = 0.0 if pd.isna(a["score"]) else float(a["score"])
        sb = float(b.get("score") or 0.0)
        row = {"key": key, "differing_fields": diff, "score_diff": abs(sa - sb)}
        (equiv if (not diff and abs(sa - sb) < 1e-9) else bad).append(row)
    walls = sorted(float(r["job_wall_s"]) for r in new.values() if "job_wall_s" in r)
    n = len(man["keys"])
    out = {"campaign": name, "rule": "PREREG v5 S0", "n": n, "digest_identical": ident, "equivalent": equiv, "failed": bad,
           "job_wall_s": {"n": len(walls), "mean": sum(walls) / len(walls) if walls else None, "median": statistics.median(walls) if walls else None,
                          "p90": walls[int(0.9 * len(walls))] if walls else None, "max": walls[-1] if walls else None},
           "verdict": "identical" if ident == n else ("equivalent" if not bad else "fail")}
    _write_once(GATES5 / "S0_REGRESSION.json", out)
    print(json.dumps({k: (v if k not in ("equivalent", "failed") else len(v)) for k, v in out.items()}, indent=1))
    return out


RUN5_BUILDERS = {"s0": build_s0, "ps": build_ps, "pt": build_pt, "det5": build_det5,
                 "psr": build_ps, "ptr": build_pt}   # S8 / X4: a full re-run after a determinism failure, as a separately named campaign
G.BUILDERS.update(RUN5_BUILDERS)
RUN5_PREFIXES = set(RUN5_BUILDERS)


def publish5(name: str, attempt: int = 0) -> None:
    """Run 4's `publish4` for a run 5 campaign (its prefix check swapped at run time; gha4.py unchanged), after the 20-job check."""
    if name.split("-")[0] not in RUN5_PREFIXES:
        raise SystemExit(f"{name}: not a run 5 campaign")
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    active = G4.active_jobs()
    if active + man["n_chunks"] + 1 > MAX_JOBS:
        raise SystemExit(f"{name}: {active} jobs active + {man['n_chunks']} chunks + plan > {MAX_JOBS}; wait (hard limit 7)")
    orig = G4.RUN4_PREFIXES
    G4.RUN4_PREFIXES = orig | RUN5_PREFIXES
    try:
        G4.publish4(name, attempt)
    finally:
        G4.RUN4_PREFIXES = orig


def runner_hours(suffix: str = "run5") -> dict:
    """Hard limit 7: runner time of this run's workflow runs by run 3's step-time rule (LOG L102): per job, first step start to last
    step end, unique job ids over all attempts; runs whose head branch or tag name ends with `suffix`."""
    import calendar  # noqa: PLC0415

    def t(x):
        return calendar.timegm(time.strptime(x, "%Y-%m-%dT%H:%M:%SZ")) if x else None

    runs, page = [], 1
    while True:
        r = json.loads(G.sh("gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs?per_page=100&page={page}"))["workflow_runs"]
        runs += [x for x in r if str(x.get("head_branch") or "").endswith(suffix)]
        if len(r) < 100 or page >= 10:
            break
        page += 1
    seen, total, n_jobs, per_run = set(), 0.0, 0, {}
    for run in runs:
        for att in range(1, int(run.get("run_attempt") or 1) + 1):
            jobs = json.loads(G.sh("gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs/{run['id']}/attempts/{att}/jobs?per_page=100"))["jobs"]
            for j in jobs:
                if j["id"] in seen:
                    continue
                seen.add(j["id"])
                st = [x for x in j.get("steps") or [] if x.get("started_at") and x.get("completed_at")]
                if not st:
                    continue
                h = (max(t(x["completed_at"]) for x in st) - min(t(x["started_at"]) for x in st)) / 3600
                total += h
                n_jobs += 1
                per_run[run["head_branch"]] = per_run.get(run["head_branch"], 0.0) + h
    out = {"rule": "step time (LOG L102)", "runner_hours": round(total, 2), "n_jobs_with_steps": n_jobs,
           "by_tag": {k: round(v, 2) for k, v in sorted(per_run.items())}, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    print(json.dumps(out, indent=1))
    return out


def _write_once(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as fh:  # written once; never overwritten
        fh.write(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")


def trust_compare(name: str) -> dict:
    """Run 2's trust comparison for a campaign of another name (as `gha4.trust_compare`, written to gates_v5): every re-run job's
    digest against the locked run 1 result it reproduces."""
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
           "git_head_packed": man.get("git_head"), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "verdict": "identical" if ident == len(man["keys"]) else "fail"}
    _write_once(GATES5 / ("TRUST_GATE_v5.json" if name == "trust-run5" else f"TRUST_GATE_v5_{name}.json"), out)
    print(json.dumps({k: v for k, v in out.items() if k != "different_keys"}, indent=1))
    return out


def main() -> None:
    cmd, a = sys.argv[1:2], sys.argv[2:]
    if cmd == ["trust-compare"]:
        trust_compare(a[0])
    elif cmd == ["pack"]:
        name = a[0]
        if name.split("-")[0] not in RUN5_BUILDERS:
            raise SystemExit(f"{name}: no run 5 builder for this prefix")
        G.pack(name, int(a[a.index("--chunk-jobs") + 1]), int(a[a.index("--k") + 1]) if "--k" in a else None)
    elif cmd == ["publish5"]:
        publish5(a[0], int(a[a.index("--attempt") + 1]) if "--attempt" in a else 0)
    elif cmd == ["collect5"]:
        G4.collect4(a[0], "--wait" in a)
    elif cmd == ["active-jobs"]:
        print(G4.active_jobs())
    elif cmd == ["runner-hours"]:
        runner_hours()
    elif cmd == ["x3"]:
        x3_decide(float(a[0]), a[a.index("--reason") + 1])
    elif cmd == ["det-compare"]:
        det_compare(int(a[0]))
    elif cmd == ["s0-compare"]:
        s0_compare(*(a[:1] or []))
    elif cmd == ["part-s-types"]:
        print(json.dumps(part_s_types(), indent=1))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
