"""Modal test of LARGE-ARTEFACT STAGING (research/phase4/LEVEL_B_EXECUTION.md; fork P1). Every iso class is block_network, and Modal
cannot move an input or output above 2 MiB inline on such a container, so a fitted model, a large evaluation record or a loop's
checkpoint files above `isolation.STAGE_THRESHOLD` travel through a volume (`isolation.stage_blob` / `read_staged`,
`Backend.stage_put` / `stage_get`): content-addressed, hash-checked, under roots the container lockdown makes 0700.

    uv run --no-sync --project phase4 python scripts/p4/smoke_stage_modal.py --room <stand-in room> [--small-system S] [--big-system B]
        [--method p1_standin_fullstate] [--tier val] [--out research/phase4/stage_smoke_modal.json]

Checks, on the UNPACKED classes (iso_fit_s / iso_eval_s) and on the PACKED classes (iso_pack_fit / iso_pack_eval), both kinds at once:
  1. the same fit (small system, seed 0) returned INLINE (stage_threshold 10 MiB) and FORCED THROUGH STAGING (stage_threshold 0); the
     model FILES are compared byte for byte for information only (the stand-in embeds its own train_cost wall / CPU seconds, so two fits
     differ in those bytes whatever the path);
  2. the GATE: the evaluation of the inline model, of the forced-staged model passed BY REF, and of the inline model with its RESULT
     forced through staging are identical records (timing and host fields removed, `compare_rounds._norm`), within each kind and between
     the packed and the unpacked kind;
  3. (--with-big) a fit of the large system whose model exceeds 2 MiB: staged on both kinds, evaluated by ref, the two records equal.
The normalised records are saved in the output JSON.
Fits and evaluations only touch the tier's public data and its evaluation parts through the trusted driver, as a Level B round does.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "p4"))

from brainir_causal import suites as SU  # noqa: E402


def _paths(sid: str, tier: str) -> dict:
    import tournament as T
    return T.modal_system_paths(sid, "real" if sid.startswith("real:") else "synthetic", tier)


def fit_payload(method: str, sid: str, tier: str, key: str, thr: int | None) -> dict:
    p = {"role": "fit", "job": {"method": method, "systems": [sid], "data": [_paths(sid, tier)["fit_data"]], "seed": 0, "config": {},
                                "threads": 3, "timeout_s": 3600}, "methods_key": key, "reload": ["fit"]}
    if thr is not None:
        p["stage_threshold"] = thr
    return p


def eval_payload(sid: str, tier: str, key: str, model: dict, thr: int | None, n_boot: int) -> dict:
    import tournament as T
    pa = _paths(sid, tier)
    sysd = {"kind": "real" if sid.startswith("real:") else "synthetic"}
    j = T.base_eval_job({**sysd, **pa}, sid, store_root="/tmp/p4m/evalstore", ref_cache="/evalvol/refcache_p1stage", gen=
                        [SU.GENERATOR_CONTAINER, "p4synth"] if sysd["kind"] == "synthetic" else None, lift=True, n_boot=n_boot)
    j.update({"store_read_roots": [SU.REMOTE["eval_store"], SU.REMOTE["store"]], "seed": 0})
    p = {"role": "eval", "job": j, "methods_key": key, "reload": ["fit", "eval", "store"], **model}
    if thr is not None:
        p["stage_threshold"] = thr
    return p


def model_of(be, r) -> tuple[bytes | None, str]:
    if isinstance(r, dict) and isinstance(r.get("model"), bytes):
        return r["model"], "inline"
    if isinstance(r, dict) and isinstance(r.get("model_ref"), dict):
        return be.stage_get(r["model_ref"]), "staged"
    return None, f"error: {str((r or {}).get('error') if isinstance(r, dict) else r)[:300]}"


def record_of(be, r):
    if isinstance(r, dict) and "result" in r:
        return r["result"], "inline"
    if isinstance(r, dict) and isinstance(r.get("result_ref"), dict):
        return pickle.loads(be.stage_get(r["result_ref"])), "staged"
    return None, f"error: {str((r or {}).get('error') if isinstance(r, dict) else r)[:300]}"


def norm(rec):
    import compare_rounds as CR
    return CR._norm(rec)


def digest(rec) -> str:
    return hashlib.sha256(json.dumps(norm(rec), sort_keys=True, default=str).encode("utf-8")).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", required=True)
    ap.add_argument("--tier", default="val")
    ap.add_argument("--small-system", default="syn-7021c9527755")
    ap.add_argument("--big-system", default="syn-b7013ac667eb")
    ap.add_argument("--method", default="p1_standin_fullstate")
    ap.add_argument("--n-boot", type=int, default=200)
    ap.add_argument("--with-big", action="store_true", help="also the > 2 MiB model of the large system (the comparison rounds cover it)")
    ap.add_argument("--out", default=str(ROOT / "research" / "phase4" / "stage_smoke_modal.json"))
    args = ap.parse_args(argv)
    from brainir_causal.isolation import STAGE_THRESHOLD
    from brainir_causal.p4modal.app import Backend
    kinds = {"unpacked": ("iso_fit_s", "iso_eval_s"), "packed": ("iso_pack_fit", "iso_pack_eval")}
    classes = sorted({c for pair in kinds.values() for c in pair})
    extra = {SU.GENERATOR_REL: SU.GENERATOR_CONTAINER}
    mdir = Path(args.room) / "src" / "brainir_causal" / "methods"
    rep = {"what": "large-artefact staging: inline vs staged, packed vs unpacked", "tier": args.tier, "stage_threshold": STAGE_THRESHOLD,
           "small_system": args.small_system, "big_system": args.big_system, "method": args.method, "checks": {}, "kinds": {}}
    t0 = time.time()
    with Backend(classes=classes, extra_dirs=extra, app_name="brainir-p4-p1-stage") as be:
        key = be.methods_key(mdir)

        def run(cls, payloads, label):
            from brainir_causal.p4modal.app import CLASSES
            return (be.run_iso_packed(payloads, cls, expected_s=[1.0] * len(payloads), label=label) if CLASSES[cls].get("slots")
                    else be.run_iso(payloads, cls, label))

        def one_kind(kind, fcls, ecls):
            k = {}
            # 1. fits: small inline, small forced through staging, big (staged by size)
            fits = [fit_payload(args.method, args.small_system, args.tier, key, 10 * 1024 * 1024),
                    fit_payload(args.method, args.small_system, args.tier, key, 0)]
            if args.with_big:
                fits.append(fit_payload(args.method, args.big_system, args.tier, key, None))
            fr = run(fcls, fits, f"stage:{kind}:fits")
            got = [model_of(be, r) for r in fr]
            (m_in, how_in), (m_st, how_st) = got[0], got[1]
            m_big, how_big = got[2] if args.with_big else (b"", "skipped")
            k["fit"] = {"small_inline": {"how": how_in, "size": len(m_in or b"")}, "small_forced": {"how": how_st, "size": len(m_st or b"")},
                        "big": {"how": how_big, "size": len(m_big or b"")}}
            k["small_model_bytes_identical_info"] = bool(m_in is not None and m_in == m_st)
            if m_in is None or m_st is None or (args.with_big and m_big is None):
                k["error"] = "a fit failed"
                return kind, k
            # 2. evaluations: model inline / model by ref / result forced through staging; 3. the big model by ref
            ref_st = be.stage_put(m_st, vol="store")        # the forced-staged model, passed BY REF
            small_inline = {"model": m_in} if len(m_in) <= 2 * 1024 * 1024 - 256 * 1024 else {"model_ref": be.stage_put(m_in, vol="store")}
            evs = [eval_payload(args.small_system, args.tier, key, small_inline, 10 * 1024 * 1024, args.n_boot),   # inline model, result
                   eval_payload(args.small_system, args.tier, key, {"model_ref": ref_st}, 10 * 1024 * 1024, args.n_boot),  # by ref
                   eval_payload(args.small_system, args.tier, key, small_inline, 0, args.n_boot)]   # result forced through staging
            if args.with_big:
                evs.append(eval_payload(args.big_system, args.tier, key, {"model_ref": be.stage_put(m_big, vol="store")}, None, args.n_boot))
            er = run(ecls, evs, f"stage:{kind}:evals")
            recs = [record_of(be, r) for r in er]
            k["eval"] = [{"how": h, "digest": digest(x) if x is not None else None} for x, h in recs]
            k["records"] = [norm(x) if x is not None else None for x, _h in recs]
            ds = [e["digest"] for e in k["eval"][:3]]
            k["small_eval_identical"] = bool(ds[0] is not None and len(set(ds)) == 1)
            if args.with_big:
                k["big_eval_digest"] = k["eval"][3]["digest"]
                k["big_model_sha"] = hashlib.sha256(m_big).hexdigest()
            return kind, k

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as ex:        # bounded: one thread per class kind
            for kind, k in ex.map(lambda kv: one_kind(kv[0], *kv[1]), kinds.items()):
                rep["kinds"][kind] = k
        u, pk = rep["kinds"].get("unpacked", {}), rep["kinds"].get("packed", {})
        ud, pd = (u.get("eval") or [{}])[0].get("digest"), (pk.get("eval") or [{}])[0].get("digest")
        rep["checks"] = {
            "small_eval_inline_equals_ref_equals_staged_result": {"unpacked": u.get("small_eval_identical"),
                                                                  "packed": pk.get("small_eval_identical")},
            "small_eval_packed_equals_unpacked": bool(ud and ud == pd),
            "small_model_bytes_identical_info": {"unpacked": u.get("small_model_bytes_identical_info"),
                                                 "packed": pk.get("small_model_bytes_identical_info")},
        }
        if args.with_big:
            rep["checks"]["big_model_over_2mib"] = {kd: (rep["kinds"].get(kd, {}).get("fit", {}).get("big", {}).get("size", 0) > 2 * 1024 * 1024)
                                                   for kd in kinds}
            rep["checks"]["big_eval_packed_equals_unpacked"] = bool(u.get("big_eval_digest") and u.get("big_eval_digest") == pk.get("big_eval_digest"))
        c = rep["checks"]
        rep["pass"] = bool(all(c["small_eval_inline_equals_ref_equals_staged_result"].values()) and c["small_eval_packed_equals_unpacked"]
                           and (not args.with_big or (all(c["big_model_over_2mib"].values()) and c["big_eval_packed_equals_unpacked"])))
        rep["modal_cost"] = be.cost_summary()
    rep["wall_s"] = round(time.time() - t0, 1)
    Path(args.out).write_text(json.dumps(rep, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": rep["pass"], "checks": rep["checks"], "wall_s": rep["wall_s"],
                      "cost": (rep.get("modal_cost") or {}).get("usd_approx_total")}, indent=1, default=str))
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
