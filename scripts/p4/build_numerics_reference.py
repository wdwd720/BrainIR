"""Build the reference of the container-start numerics self-test (p4modal/numerics_reference.json; research/phase4/LEVEL_B_EXECUTION.md
section 9). ORCHESTRATOR ONLY. Run from the Linux driver container (long Modal clients on the Windows host die of socket exhaustion):

    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py run scripts/p4/build_numerics_reference.py [--n 40] [--write]

A Modal app of its OWN (never the official classes; NO host gate and NO self-test, so every host kind shows up) with functions on
the two official images (`images.full_image` and `images.iso_image`, the synthetic generator baked, the official CPU pins) and two
container sizes (SHAPES: 4 and 32 CPU, the smallest and largest gated classes), one input per container (each input ends with
stop_fetching_inputs, so every input lands on a fresh container). Each input runs the battery exactly as the containers will
(`selftest.run_battery`: fresh processes, its parts at once) and returns the host's CPU record, whether the flag gate admits it, its
numerics fingerprint and the battery's record.

The reference = the battery record of the ADMISSIBLE hosts, which must ALL agree (every item, both images, every host model met): the
builder refuses to write otherwise and reports the groups. --write writes the reference file; the report (every host, and how many items
the non-admissible hosts reproduce: the battery's power to tell hosts apart) goes to research/phase4/numerics_selftest/build_report.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

REPORT_DIR = ROOT / "research" / "phase4" / "numerics_selftest"
GENERATOR = {"benchmarks/causal_state_v1/generator/src": "/repo/benchmarks/causal_state_v1/generator/src"}


def _probe_fn():
    def p4_selftest_probe(i):
        import os
        import time as _t

        from brainir_causal.p4modal import gate
        from brainir_causal.p4modal import selftest as S
        t0 = _t.time()
        h = gate.host_cpu()
        out = {"i": i, "task": os.environ.get("MODAL_TASK_ID"), "host": h, "host_class": gate.host_class(), "admissible": gate.admissible(h),
               "battery": S.run_battery(240.0)}
        try:
            out["fingerprint"] = gate.host_fingerprint()
        except Exception as e:  # noqa: BLE001
            out["fingerprint"] = {"error": repr(e)[:200]}
        out["wall_s"] = round(_t.time() - t0, 2)
        try:
            import modal.experimental as E
            E.stop_fetching_inputs()                # one input per container: the next input needs a fresh container
        except Exception:  # noqa: BLE001, S110
            pass
        return out
    return p4_selftest_probe


#: (name, image, CPU, memory MiB, share of the inputs)
SHAPES = (("full4", "full", 4.0, 8192, 0.4), ("iso4", "iso", 4.0, 8192, 0.4), ("full32", "full", 32.0, 32768, 0.2))


def run_probe(n: int, shapes: tuple[str, ...] | None = None) -> dict:
    """n inputs (= containers) in all, split over SHAPES (or only the named ones, in proportion to their shares)."""
    import modal
    from brainir_causal.p4modal import images
    app = modal.App("brainir-p4-numerics-ref")
    imgs = {"full": images.full_image(extra_dirs=GENERATOR), "iso": images.iso_image(extra_dirs=GENERATOR)}
    fns, counts = {}, {}
    use = [sh for sh in SHAPES if shapes is None or sh[0] in shapes]
    total = sum(sh[4] for sh in use)
    for name, kind, cpu, mem, share in use:
        fns[name] = app.function(image=imgs[kind], cpu=cpu, memory=mem, timeout=900, serialized=True, name=f"p4_selftest_ref_{name}",
                                 max_containers=40)(_probe_fn())
        counts[name] = max(1, round(n * share / total))
    t0 = time.time()
    utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    res: dict = {}
    with modal.enable_output(), app.run() as run:
        app_id = getattr(run, "app_id", None)

        def one(name):
            out = []
            for r in fns[name].map(range(counts[name]), order_outputs=False, return_exceptions=True):
                out.append(r if not isinstance(r, BaseException) else {"exception": repr(r)[:300]})
            return name, out
        with ThreadPoolExecutor(max_workers=len(fns)) as ex:  # bounded: one client thread per shape
            for name, out in ex.map(one, list(fns)):
                res[name] = out
    return {"app_id": app_id, "utc": utc, "wall_s": round(time.time() - t0, 1), "results": res,
            "shapes": {name: {"image": kind, "cpu": cpu, "memory_mib": mem, "inputs": counts[name]} for name, kind, cpu, mem, _ in use}}


def rows_of(probe: dict) -> list[dict]:
    """One row per container of a probe (the report keeps them: the reference is a function of these rows, `build`)."""
    rows = []
    for kind, out in probe["results"].items():
        for r in out:
            if "exception" in r:
                rows.append({"shape": kind, "exception": r["exception"]})
                continue
            b = r["battery"]
            rows.append({"shape": kind, "task": r.get("task"), "class": (r.get("host_class") or {}).get("key"),
                         "admissible": r["admissible"], "items": b.get("items"), "errors": b.get("errors"), "absent": b.get("absent"),
                         "versions": b.get("versions"), "battery_id": b.get("battery_id"), "s": b.get("s"), "wall_s": b.get("wall_s"),
                         "fingerprint": r.get("fingerprint")})
    return rows


def build(rows: list[dict], meta: dict, min_admissible: int = 20) -> tuple[dict | None, dict]:
    """(the reference or None, the report) from the probe's rows; meta = {"app_id", "utc", "wall_s", "shapes"} of the probe. The
    reference = the one result every ADMISSIBLE container computed (all must agree, none may fail, every item of the battery present)."""
    from brainir_causal.p4modal import selftest as S
    adm = [r for r in rows if r.get("admissible")]
    groups = Counter(json.dumps({"items": r["items"], "versions": r["versions"], "battery_id": r["battery_id"]}, sort_keys=True)
                     for r in adm if not r.get("errors"))
    report: dict = {"meta": meta, "n_containers": len(rows), "n_admissible": len(adm),
                    "admissible_with_errors": [r for r in adm if r.get("errors")][:5], "n_groups_admissible": len(groups),
                    "exceptions": [r for r in rows if "exception" in r][:5]}
    hosts = Counter((r.get("class"), r.get("admissible")) for r in rows if "class" in r)
    report["hosts"] = [{"class": k, "admissible": a, "containers": c} for (k, a), c in sorted(hosts.items(), key=str)]
    ref = None
    if len(groups) == 1 and len(adm) >= min_admissible and not report["admissible_with_errors"]:
        g = json.loads(next(iter(groups)))
        if sorted(g["items"]) == sorted(S.item_names()):
            ref = {"what": "numerics self-test reference (p4modal/selftest.py; research/phase4/LEVEL_B_EXECUTION.md section 9)",
                   "battery_id": g["battery_id"], "versions": g["versions"], "items": g["items"],
                   "reference_hosts": [{"class": k, "containers": c} for (k, a), c in sorted(hosts.items(), key=str) if a],
                   "built": {"utc": meta.get("utc"), "app_id": meta.get("app_id"), "shapes": meta.get("shapes"),
                             "containers_admissible": len(adm), "containers_total": len(rows),
                             "builder": "scripts/p4/build_numerics_reference.py",
                             "report": "research/phase4/numerics_selftest/build_report.json"}}
        else:
            report["refused"] = f"items {sorted(g['items'])} != the battery's {S.item_names()} (the builder must bake the generator)"
    else:
        report["refused"] = (f"{len(groups)} distinct admissible results (all must agree), {len(adm)} admissible containers "
                             f"(at least {min_admissible} needed), {len(report['admissible_with_errors'])} with errors")
    if ref is not None:                   # the battery's power: how many items each NON-admissible container reproduces (informational)
        report["non_admissible"] = [{"class": r["class"], "items_equal": sum(1 for k, v in (r.get("items") or {}).items()
                                                                              if ref["items"].get(k) == v),
                                     "items": len(ref["items"]), "errors": r.get("errors")}
                                    for r in rows if "class" in r and not r.get("admissible")]
    report["timing"] = {}
    for shape in sorted({r["shape"] for r in rows}):
        ws = sorted(r["wall_s"] for r in rows if r["shape"] == shape and r.get("wall_s") is not None)
        report["timing"][shape] = {"battery_wall_s_median": ws[len(ws) // 2] if ws else None, "battery_wall_s_max": ws[-1] if ws else None,
                                   "containers": len(ws)}
    report["rows"] = rows
    return ref, report


def reference_text(ref: dict) -> str:
    return json.dumps(ref, indent=1, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=80, help="inputs (= containers) in all, split over SHAPES")
    ap.add_argument("--min-admissible", type=int, default=20)
    ap.add_argument("--write", action="store_true", help="write phase4/src/brainir_causal/p4modal/numerics_reference.json")
    ap.add_argument("--from-report", action="store_true", help="rebuild the reference from the recorded report's rows (no Modal)")
    ap.add_argument("--shapes", default=None, help="comma-separated SHAPES names to use (a probe only; the reference uses all)")
    ap.add_argument("--report-name", default="build_report.json", help="the report's file name under research/phase4/numerics_selftest")
    args = ap.parse_args(argv)
    if args.from_report:
        rec = json.loads((REPORT_DIR / "build_report.json").read_text(encoding="utf-8"))
        ref, _ = build(rec["rows"], rec["meta"], args.min_admissible)
        if ref is None:
            return 1
        if args.write:
            from brainir_causal.p4modal import selftest as S
            S.REFERENCE.write_text(reference_text(ref), encoding="utf-8", newline="\n")
        print(reference_text(ref), end="")
        return 0
    if args.write and (args.shapes or args.report_name != "build_report.json"):
        raise SystemExit("--write builds the reference from every shape into build_report.json")
    probe = run_probe(args.n, tuple(args.shapes.split(",")) if args.shapes else None)
    ref, report = build(rows_of(probe), {k: probe.get(k) for k in ("app_id", "utc", "wall_s", "shapes")}, args.min_admissible)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / args.report_name).write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    summary = {k: report.get(k) for k in ("meta", "n_containers", "n_admissible", "n_groups_admissible", "refused", "hosts", "timing")}
    summary["non_admissible_items_equal"] = {f"{k[0]} ({k[1]} of {k[2]} items equal)": c for k, c in
                                             Counter((r["class"], r["items_equal"], r["items"]) for r in report.get("non_admissible") or []).items()}
    print(json.dumps(summary, indent=1, default=str), flush=True)
    if ref is None:
        return 1
    if args.write:
        from brainir_causal.p4modal import selftest as S
        S.REFERENCE.write_text(reference_text(ref), encoding="utf-8", newline="\n")
        print(f"wrote {S.REFERENCE}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
