"""Pre-freeze checklist (ORCHESTRATOR SIDE; research/phase4/PREFREEZE_TODO.md; CRITICAL_PATH_PLAN N10 / N11). Runs every check the
benchmark freeze needs and records PASS / FAIL / MISSING per item in research/phase4/PREFREEZE_CHECK.json; exit 1 unless all pass.

    uv run --no-sync --project phase4 python scripts/p4/prefreeze_check.py --modal-tests <modal_pytest phase4 json>
        --generator-tests <modal_pytest generator json> --host-tests <host-only pytest log> [--only item,item]

Items:
- protocol: PROTOCOL.md carries no DRAFT marker;
- generator: the benchmark's generator copy equals research/phase4/GENERATOR_DELIVERY_SHA256.txt (integrate_generator.py --check);
- public_docs: regenerating the public docs (make_public_docs.py) changes nothing;
- systems_public: benchmarks/causal_state_v1/public/systems_public.json exists and lists exactly the dev tier's and the real public systems;
- pilot: public/pilot_subset.json exists and names only systems of the current val tier;
- manifests: a build manifest exists for every system of dev / val / real public / real B, and the local copies verify
  (freeze_manifests.py --verify-local);
- locks: Phase 1 (freeze.py --check), Phase 2 (method_lock.py check), Phase 3 (method_lock_p3.py --check, freeze_benchmark.py --check);
- rooms: bench and review rooms match their manifests (make_phase4_cleanroom.py --check) and audit clean (--audit);
- transcripts: the transcript audit finds 0 answer tokens and 0 forbidden-path inputs in every Phase 4 agent stream;
- tests: the Modal phase4 and generator suites and the host-only files all passed, and every result is newer than the last change
  under phase4/src and the generator copy.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UV = os.environ.get("UV_EXE") or str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" /
                                     "astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe" / "uv.exe")
BENCH = ROOT / "benchmarks" / "causal_state_v1"
OUT = ROOT / "research" / "phase4" / "PREFREEZE_CHECK.json"


def sh(args: list[str], project: str | None = "phase4", timeout: float = 3600) -> tuple[int, str]:
    cmd = [UV, "run", "--no-sync"] + (["--project", project] if project else []) + ["python", *args]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    return r.returncode, (r.stdout[-3000:] + r.stderr[-2000:]).strip()


def newest_mtime(*dirs: Path) -> float:
    return max((p.stat().st_mtime for d in dirs for p in d.rglob("*") if p.is_file() and "__pycache__" not in p.parts), default=0.0)


def c_protocol(a):
    t = (BENCH / "PROTOCOL.md").read_text(encoding="utf-8")
    hits = [ln.strip()[:100] for ln in t.splitlines() if re.search(r"\bDRAFT\b", ln)]
    return (not hits), {"draft_lines": hits[:5]}


def c_generator(a):
    rc, out = sh(["scripts/p4/integrate_generator.py", "--check"])
    return rc == 0, {"out": out[-500:]}


def c_public_docs(a):
    docs = BENCH / "docs"
    before = {p.name: p.read_bytes() for p in docs.glob("*.md")}
    rc, out = sh(["scripts/p4/make_public_docs.py"])
    after = {p.name: p.read_bytes() for p in docs.glob("*.md")}
    changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    return rc == 0 and not changed, {"rc": rc, "changed_by_regeneration": changed}


def _dev_systems() -> list[str]:
    p = ROOT / "data" / "phase4" / "suites" / "dev" / "internal_records.json"
    return sorted(json.loads(p.read_text(encoding="utf-8"))) if p.exists() else []


def c_systems_public(a):
    p = BENCH / "public" / "systems_public.json"
    if not p.exists():
        return None, {"missing": str(p.relative_to(ROOT))}
    have = set(json.loads(p.read_text(encoding="utf-8")))
    real = set(json.loads((BENCH / "public" / "systems_real_public.json").read_text(encoding="utf-8")))
    want = set(_dev_systems()) | real
    return have == want, {"n": len(have), "missing": sorted(want - have)[:10], "extra": sorted(have - want)[:10]}


def c_pilot(a):
    p = BENCH / "public" / "pilot_subset.json"
    val = ROOT / "data" / "phase4" / "suites" / "val" / "internal_records.json"
    if not p.exists() or not val.exists():
        return None, {"pilot": p.exists(), "val_records": val.exists()}
    pil = json.loads(p.read_text(encoding="utf-8"))
    if not pil.get("synthetic"):
        return None, {"synthetic": "not resolved yet (select.write_pilot_subset on the final val tier)", "real": pil.get("real")}
    names = set(pil["synthetic"])
    vs = set(json.loads(val.read_text(encoding="utf-8")))
    hid = BENCH / "hidden" / "pilot_subset_resolved.json"
    return names <= vs and hid.exists(), {"n": len(names), "not_in_val": sorted(names - vs)[:10], "hidden_resolution": hid.exists(),
                                          "real": pil.get("real")}


def c_manifests(a):
    md = ROOT / "research" / "phase4" / "build_manifests"
    have = {p.stem for p in md.glob("*.json")}
    dev = _dev_systems()
    valp = ROOT / "data" / "phase4" / "suites" / "val" / "internal_records.json"
    val = sorted(json.loads(valp.read_text(encoding="utf-8"))) if valp.exists() else []
    from_name = lambda s: re.sub(r"[^A-Za-z0-9_.-]", "_", s)  # noqa: E731 - suites._safe
    missing = [f"syn_dev_{from_name(s)}" for s in dev if f"syn_dev_{from_name(s)}" not in have]
    missing += [f"syn_val_{from_name(s)}" for s in val if f"syn_val_{from_name(s)}" not in have]
    rc, out = sh(["scripts/p4/freeze_manifests.py", "--verify-local"], timeout=7200)
    return (not missing) and rc == 0 and bool(dev) and bool(val), {"missing": missing[:10], "n_missing": len(missing),
                                                                   "verify_local_rc": rc, "out": out[-600:]}


def c_locks(a):
    res = {"phase1": sh(["benchmarks/dng100/freeze.py", "--check"], project=None)[0],
           "phase2": sh(["scripts/method_lock.py", "check"], project=None)[0],
           "phase3_method": sh(["scripts/p3/method_lock_p3.py", "--check"], project="phase3")[0],
           "phase3_benchmark": sh(["scripts/p3/freeze_benchmark.py", "--check"], project="phase3")[0]}
    return all(v == 0 for v in res.values()), res


def c_rooms(a):
    res = {}
    for room in ("bench", "review"):
        res[f"{room}_check"] = sh(["scripts/make_phase4_cleanroom.py", "--room", room, "--check"], timeout=7200)[0]
        res[f"{room}_audit"] = sh(["scripts/make_phase4_cleanroom.py", "--room", room, "--audit"], timeout=7200)[0]
    return all(v == 0 for v in res.values()), res


def c_transcripts(a):
    out = ROOT / "research" / "phase4" / "transcript_audit.json"
    rc, txt = sh(["scripts/p4agent/audit_transcripts.py", "--out", str(out)], timeout=7200)
    if rc != 0 or not out.exists():
        return False, {"rc": rc, "out": txt[-600:]}
    d = json.loads(out.read_text(encoding="utf-8"))
    bad = {n: {"answer_tokens": v.get("outputs_with_answer_tokens", 0), "forbidden_path_inputs": v.get("forbidden_path_inputs", 0)}
           for n, v in d.items() if v.get("outputs_with_answer_tokens", 0) or v.get("forbidden_path_inputs", 0)}
    # the canary agents probe forbidden paths on purpose (their denials are the test); every other agent must be clean
    bad = {n: v for n, v in bad.items() if not n.startswith("canary") or v["answer_tokens"]}
    return not bad, {"agents": len(d), "problems": bad}


def c_tests(a):
    src_t = newest_mtime(ROOT / "phase4" / "src", BENCH / "generator")
    res, ok = {}, True
    for name, path in (("modal_phase4", a.modal_tests), ("modal_generator", a.generator_tests)):
        if not path or not Path(path).exists():
            res[name], ok = "missing", False
            continue
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        fresh = Path(path).stat().st_mtime > src_t
        good = not d.get("files_failing") and not d.get("collect_problems")
        res[name] = {"green": good, "newer_than_code": fresh, "totals": d.get("totals")}
        ok = ok and good and fresh
    hp = Path(a.host_tests) if a.host_tests else None
    if not hp or not hp.exists():
        res["host_only"], ok = "missing", False
    else:
        tail = hp.read_text(encoding="utf-8", errors="replace")[-3000:]
        good = bool(re.search(r"\d+ passed", tail)) and not re.search(r"\d+ (failed|error)", tail)
        fresh = hp.stat().st_mtime > src_t
        res["host_only"] = {"green": good, "newer_than_code": fresh, "summary": tail.strip().splitlines()[-1][:200] if tail.strip() else ""}
        ok = ok and good and fresh
    return ok, res


CHECKS = {"protocol": c_protocol, "generator": c_generator, "public_docs": c_public_docs, "systems_public": c_systems_public,
          "pilot": c_pilot, "manifests": c_manifests, "locks": c_locks, "rooms": c_rooms, "transcripts": c_transcripts, "tests": c_tests}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modal-tests", default="")
    ap.add_argument("--generator-tests", default="")
    ap.add_argument("--host-tests", default="")
    ap.add_argument("--only", default="")
    args = ap.parse_args(argv)
    only = [x for x in args.only.split(",") if x] or list(CHECKS)
    rec = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "items": {}}
    for name in only:
        t0 = time.time()
        try:
            ok, detail = CHECKS[name](args)
        except Exception as e:  # noqa: BLE001 - a crashing check is a failing check
            ok, detail = False, {"exception": f"{type(e).__name__}: {e}"[:500]}
        status = "PASS" if ok else ("MISSING" if ok is None else "FAIL")
        rec["items"][name] = {"status": status, "s": round(time.time() - t0, 1), "detail": detail}
        print(f"{status:7s} {name}  {json.dumps(detail)[:300]}", flush=True)
    rec["all_pass"] = all(v["status"] == "PASS" for v in rec["items"].values()) and set(only) == set(CHECKS)
    OUT.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{'ALL PASS' if rec['all_pass'] else 'NOT READY'}: {OUT.relative_to(ROOT)}")
    return 0 if rec["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
