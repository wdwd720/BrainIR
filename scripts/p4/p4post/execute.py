"""Fits and evaluations of the post-lock studies on Modal through the ISOLATED classes only (ORCHESTRATOR SIDE).

Every job is an iso "call" job of `scripts/p4/p4post_iso.py` run by the container's trusted driver: fits run the benchmark's
`isolation.fit_job` (or the critical ablation's passive-only data rule) in a fit worker (`fit_c`); evaluations run the benchmark's
unchanged `harness.evaluate_job` (every metric family) in model workers (`eval_c`); custom per-item jobs run `p4post.isojob`. The
wrappers exist for Modal's 2 MiB inline limit, which an isolated (block_network) container cannot exceed: large models travel through
the fit volume, large outputs lzma-compressed (p4post_iso docstring). The model bytes are never loaded here.

SCHEDULING. PACKED by default (research/phase4/LEVEL_B_EXECUTION.md): `Backend.run_iso_packed` on the 32-CPU packed iso classes (8
jobs per container, each in its own slot: own uid block, group and worker namespaces), one queue per class submitted LONGEST EXPECTED
FIRST (real full networks, then real mechanisms, then synthetic systems; state-bottleneck variants first). Every result is PERSISTED
AS IT ARRIVES (`on_result`), so an interrupted wave resumes without recomputation. Unpacked classes (`packed=False`) are the fallback.
PACKED-CLASS RULES (P1, 2026-09-27): a packed container reloads its volumes ONCE, when its first input arrives, and packed jobs never
write or commit a volume. Everything a packed wave reads (method tars through `methods_key`, datasets, custom item sets built by the
unpacked build class) must therefore be on the volumes BEFORE the wave's containers start; a driver that builds new data between
waves (the counterexample rounds) opens a NEW app per wave so no warm container serves stale volume state. The payloads' "reload"
lists name the volumes a container reloads at its start (fits: fit; evaluations and custom jobs: fit, eval, store).

LAYOUT (resumable: a present, successful fit / evaluation is reused unless `refit`): <run>/<variant>/fits/<sid>_s<seed>.pkl (model
bytes), .json (side record) or .fitlog.json (the error); <run>/<variant>/evals/<sid>_s<seed>.pkl (the full evaluation, private units
included) or .evallog.json.
"""

from __future__ import annotations

import json
import pickle
import time
from pathlib import Path

from brainir_causal import suites as SU

from . import common as C

FIT_CLS = {"synthetic": "iso_fit_s", "real": "iso_fit_m"}
EVAL_CLS = {"synthetic": "iso_eval_s", "real": "iso_eval_l"}
PACK_FIT, PACK_EVAL, PACK_GPU = "iso_pack_fit", "iso_pack_eval", "iso_pack_gpu_rtx6000"
GPU_FIT_CLS = "iso_gpu_rtx6000"
#: expected durations (s), used only to ORDER the queues (longest first)
EXPECTED = {"fit": {"full": 1800, "mech": 600, "syn": 600}, "eval": {"full": 2400, "mech": 900, "syn": 900},
            "custom": {"full": 1800, "mech": 600, "syn": 600}}
#: infrastructure failures (retried when a run is resumed); every other persisted failure is the job's own RESULT (a scientific failure:
#: never retried, charged downstream), as in the Level C driver (levelc_lib.INFRA_PATTERNS)
INFRA_PATTERNS = ("no result returned", "not completed after", "no admissible host", "call failed repeatedly", "container lockdown failed",
                  "PackInfraError", "packed child driver", "ClientConnectorDNSError", "Temporary failure in name resolution",
                  "No such file or directory: '/fitvol/methods/", "model download failed", "packed isolation needs",
                  "refusing to run model workers", "InfraFault")   # isolation.InfraFault (P1, 2026-09-27): never the job's own result


def infrastructure(err: str | None) -> bool:
    return bool(err) and any(pat in str(err) for pat in INFRA_PATTERNS)


def _cached_failure(path: Path) -> str | None:
    """The persisted error of a job when it was the job's own failure (then the job is not resubmitted), else None."""
    if not path.exists():
        return None
    try:
        err = json.loads(path.read_text(encoding="utf-8")).get("error")
    except (json.JSONDecodeError, OSError):
        return None
    return None if infrastructure(err) else (err or "failed")


def _cls(sysd: dict, sid: str) -> str:
    if sysd["kind"] != "real":
        return "syn"
    return "full" if ":full" in sid else "mech"


def classes_for(real: bool, packed: bool, gpu: bool = False) -> list[str]:
    """The classes a driver's Backend needs: packed fit / eval classes plus the UNPACKED fit class(es) of the large-model tier."""
    if packed:
        return [PACK_FIT, PACK_EVAL, "iso_fit_s"] + (["iso_fit_m"] if real else []) + ([PACK_GPU, GPU_FIT_CLS] if gpu else [])
    return sorted({"iso_fit_s", "iso_eval_s"} | ({"iso_fit_m", "iso_eval_l"} if real else set()) | ({GPU_FIT_CLS} if gpu else set()))


def _paths(run: Path, variant: str, sid: str, seed: int, sub: str) -> Path:
    d = Path(run) / variant / sub
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{SU._safe(sid)}_s{seed}"


def fit_side(run: Path, variant: str, sid: str, seed: int) -> dict | None:
    p = _paths(run, variant, sid, seed, "fits").with_suffix(".json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def fit_error(run: Path, variant: str, sid: str, seed: int) -> str | None:
    p = _paths(run, variant, sid, seed, "fits").with_suffix(".fitlog.json")
    return json.loads(p.read_text(encoding="utf-8")).get("error") if p.exists() else None


def model_path(run: Path, variant: str, sid: str, seed: int) -> Path:
    return _paths(run, variant, sid, seed, "fits").with_suffix(".pkl")


def load_eval(run: Path, variant: str, sid: str, seed: int) -> dict | None:
    p = _paths(run, variant, sid, seed, "evals").with_suffix(".pkl")
    if not p.exists():
        return None
    with open(p, "rb") as fh:
        return pickle.load(fh)


def eval_error(run: Path, variant: str, sid: str, seed: int) -> str | None:
    p = _paths(run, variant, sid, seed, "evals").with_suffix(".evallog.json")
    return json.loads(p.read_text(encoding="utf-8")).get("error") if p.exists() else None


def _order_key(s: dict) -> tuple:
    c = _cls(s["sysd"], s["sid"])
    return ({"full": 0, "mech": 1, "syn": 2}[c], 0 if "state_bottleneck" in s.get("variant", "") else 1, s["sid"])


def submit(be, items: list[tuple], *, packed: bool, kind: str, label: str, done_dir: Path | None = None, on_item=None) -> list:
    """items: [(payload, sysd, sid, key, unpacked class, packed class)] -> results in item order. Packed: one run_iso_packed queue per
    packed class (longest expected first; `done_dir` stores every result for idempotent re-submission, for SMALL results only);
    unpacked: one map per class (real systems first). on_item(item index, result) is called as each result arrives (persistence)."""
    out: list = [None] * len(items)
    groups: dict[str, list[int]] = {}
    for i, it in enumerate(items):
        groups.setdefault(it[5] if packed else it[4], []).append(i)
    done = _DoneFiles(done_dir) if done_dir is not None else None
    for cls, idx in groups.items():
        idx = sorted(idx, key=lambda i: ({"full": 0, "mech": 1, "syn": 2}[_cls(items[i][1], items[i][2])], i))
        if done is not None and not packed:
            # unpacked: reuse a stored result of the same job key (from any class: a run resumed after switching classes)
            left = []
            for i in idx:
                r = done.get(items[i][3])
                if r is None:
                    left.append(i)
                else:
                    out[i] = r
            idx = left
            if not idx:
                continue
        pls = [items[i][0] for i in idx]

        def got(j, r, idx=idx):
            if on_item is not None:
                try:
                    on_item(idx[j], r)
                except Exception as e:  # noqa: BLE001 - a persistence error must not lose the other results
                    print(f"  p4post: persisting result {idx[j]} failed: {type(e).__name__}: {e}", flush=True)
        if packed:
            exp = [EXPECTED[kind][_cls(items[i][1], items[i][2])] for i in idx]
            keys = [items[i][3] for i in idx]
            res = be.run_iso_packed(pls, cls, expected_s=exp, keys=keys, done_dir=(done_dir / cls) if done_dir else None,
                                    label=f"{label}:{cls}", on_result=got)
        else:
            def got_store(j, r, idx=idx, cls=cls):
                if done is not None and not isinstance(r, BaseException):
                    done.put(cls, items[idx[j]][3], r)
                got(j, r)
            res = run_eager(be, [dict(p, kind="iso") for p in pls], cls, f"{label}:{cls}", got_store)
        for i, r in zip(idx, res):
            out[i] = r
    return out


#: unpacked submission keeps at most (the class's container cap + EAGER_SLACK) jobs in flight
EAGER_SLACK = 4


def run_eager(be, payloads: list[dict], cls: str, label: str, on_result) -> list:
    """UNPACKED submission without wave tails: one single-job `Backend.run` per payload from a thread pool. `Backend.run` re-submits a
    host-gate refusal in its next wave, and a shared wave ends only with its slowest job, so every refused input of a large map waited
    for the whole wave (dry runs: 20 of 50 inputs refused in wave 1, re-submitted after 1,243 s); a wave of one job re-submits at once.
    The refusing container stops taking inputs (`gate.refusal`), so a re-submission lands on a fresh host. Results in input order;
    on_result(j, r) as each arrives; the per-job cost records are merged into one per label."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    n = len(payloads)
    if not n:
        return []
    cap = int(getattr(be, "p4post_max_containers", 0) or 24)
    out: list = [None] * n
    n0 = len(be.costs)
    verbose, be.verbose = be.verbose, False
    lock = threading.Lock()
    t0 = time.time()
    state = {"done": 0, "last": t0}

    def one(j: int) -> None:
        try:
            r = be.run([payloads[j]], cls, label)[0]
        except Exception as e:  # noqa: BLE001 - a failure of the submission itself: an infrastructure failure of this job
            r = RuntimeError(f"call failed repeatedly on Modal: {type(e).__name__}: {e}"[:800])
        out[j] = r
        try:
            on_result(j, r)
        finally:
            with lock:
                state["done"] += 1
                if verbose and (time.time() - state["last"] > 120 or state["done"] == n):
                    state["last"] = time.time()
                    print(f"  p4post {label}: {state['done']}/{n} done ({time.time() - t0:.0f} s, refusals {be.refusals.get(cls, 0)})",
                          flush=True)
    try:
        with ThreadPoolExecutor(max_workers=max(1, min(n, cap + EAGER_SLACK)), thread_name_prefix="p4post") as ex:
            list(ex.map(one, range(n)))
    finally:
        be.verbose = verbose
        new = be.costs[n0:]
        del be.costs[n0:]
        if new:
            peaks = [c["peak_container_mb_max"] for c in new if c.get("peak_container_mb_max") is not None]
            be.costs.append({"label": label, "class": cls, "calls": sum(int(c.get("calls") or 0) for c in new),
                             "container_s": round(sum(float(c.get("container_s") or 0.0) for c in new), 1),
                             "peak_container_mb_max": max(peaks) if peaks else None,
                             "usd_approx": round(sum(float(c.get("usd_approx") or 0.0) for c in new), 4), "eager": True})
    return out


class _DoneFiles:
    """Stored job results <done_dir>/<class>/<key file>.pkl (the naming of Backend.run_packed's done files), readable across classes."""

    def __init__(self, root: Path):
        from brainir_causal.p4modal.app import _key_file
        self.root, self._kf = Path(root), _key_file

    def get(self, key: str):
        name = f"{self._kf(key)}.pkl"
        for d in sorted(self.root.glob("*")) if self.root.exists() else []:
            f = d / name
            if f.exists():
                with open(f, "rb") as fh:
                    return pickle.load(fh)
        return None

    def put(self, cls: str, key: str, r) -> None:
        d = self.root / cls
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{self._kf(key)}.pkl"
        tmp = f.with_suffix(".part")
        with open(tmp, "wb") as fh:
            pickle.dump(r, fh, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(f)


def run_fits(be, specs: list[dict], *, key: str, run: Path, timeout_s: float = 3600, threads: int = 3, devices: dict | None = None,
             refit: bool = False, packed: bool = True, label: str = "fits") -> dict:
    """specs: [{"variant", "method", "sid", "sysd", "seed", "config", ["passive"], ["bootstrap"]}] -> {(variant, sid, seed[, b]):
    {"ok", "side" | "error"}}. Every fit runs `p4post_iso:fit_c` (the benchmark's `isolation.fit_job`, or the passive-only data rule).
    PACKED: TWO TIERS (p4post_iso, size limits): the packed wave returns small models inline; a model larger than the inline limit
    comes back as {"too_large"} (marked <base>.too_large, so a resumed run skips the packed tier for it) and is fitted again on the
    UNPACKED class, which writes it to the fit volume (committed) and returns its reference; the driver downloads it (sha256-checked).
    UNPACKED: one tier (every fit may write the fit volume). Bootstrap refits (criterion F) keep their side records only
    (<run>/<variant>/refits/)."""
    out: dict = {}
    todo = []
    for s in sorted(specs, key=_order_key):
        seed = int(s["seed"])
        b = s.get("bootstrap")
        k = (s["variant"], s["sid"], seed) + ((int(b),) if b is not None else ())
        rr = Path(s.get("run_root") or run)                   # a spec may name its own run root (e.g. the method's refits)
        base = (rr / s["variant"] / "refits" / f"{SU._safe(s['sid'])}_b{b}") if b is not None else _paths(rr, s["variant"], s["sid"], seed, "fits")
        base.parent.mkdir(parents=True, exist_ok=True)
        if base.with_suffix(".json").exists() and (b is not None or base.with_suffix(".pkl").exists()) and not refit:
            out[k] = {"ok": True, "side": json.loads(base.with_suffix(".json").read_text(encoding="utf-8")), "cached": True}
            continue
        fail = None if refit else _cached_failure(base.with_suffix(".fitlog.json"))
        if fail is not None:
            out[k] = {"ok": False, "error": fail, "cached": True}
            continue
        job = {"method": s["method"], "systems": [s["sid"]], "data": [s["sysd"]["fit_data"]], "seed": seed,
               "config": dict(s.get("config") or {}), "threads": threads, "timeout_s": timeout_s, "passive": bool(s.get("passive"))}
        if b is not None:
            job["bootstrap"] = int(b)
        todo.append((s, k, base, job))
    stager = C.ModelStager(be)

    def record(i: int, r, pool: list) -> str:
        """Persist one fit result; returns 'ok' | 'too_large' | 'failed'."""
        s, k, base, job = pool[i]
        val, err = C.iso_result(r, "result")
        val = C.decode_output(val)
        if isinstance(val, dict) and val.get("error") and "model" not in val and "model_ref" not in val:
            err, val = str(val.get("error"))[-3000:], None
        if isinstance(val, dict) and val.get("too_large"):
            return "too_large"
        blob = None
        if isinstance(val, dict) and isinstance(val.get("model"), bytes):
            blob = val["model"]
        elif isinstance(val, dict) and val.get("model_ref"):
            try:
                blob = b"" if s.get("bootstrap") is not None else stager.fetch(val["model_ref"], val["sha256"])
            except Exception as e:  # noqa: BLE001 - recorded as the fit's failure
                err = f"model download failed: {type(e).__name__}: {e}"
        if blob is not None:
            if s.get("bootstrap") is None:
                base.with_suffix(".pkl").write_bytes(blob)
            side = dict(val.get("side") or {})
            side["variant"] = s["variant"]
            side["modal_host"] = (r.get("__host__") or {}).get("model") if isinstance(r, dict) else None
            if val.get("model_ref"):
                side["model_ref"] = val["model_ref"]
            C.dump_json(side, base.with_suffix(".json"))
            base.with_suffix(".fitlog.json").unlink(missing_ok=True)
            out[k] = {"ok": True, "side": side}
            return "ok"
        msg = err or "no model"
        C.dump_json({"error": str(msg)[-4000:], "variant": s["variant"], "utc": C.utc()}, base.with_suffix(".fitlog.json"))
        out[k] = {"ok": False, "error": msg}
        return "failed"

    def items_of(pool: list, *, volume: bool) -> list:
        items = []
        for s, k, base, job in pool:
            gpu = (devices or {}).get(s["method"]) == "cuda"
            j = dict(job, model_dir=C.MODEL_DIR_CONTAINER) if volume else job
            p = C.iso_call_payload("fit_c", j, key, reload=("fit",), commit=("fit",) if volume else ())
            jkey = f"fit|{s['variant']}|{s['sid']}|{job['seed']}|{job.get('bootstrap')}|{json.dumps(job['config'], sort_keys=True)}"
            items.append((p, s["sysd"], s["sid"], jkey, GPU_FIT_CLS if gpu else FIT_CLS[s["sysd"]["kind"]], PACK_GPU if gpu else PACK_FIT))
        return items

    # specs flagged "large" (e.g. `--large-fits`: a method whose Level C models already exceed the inline limit) or found too large by an
    # earlier attempt (<base>.too_large) skip the packed tier; UNPACKED fits need no second tier at all (they may write the fit volume,
    # so they carry model_dir from the start; a model within the inline limit still comes back inline)
    def big(t) -> bool:
        return bool(t[0].get("large")) or t[2].with_suffix(".too_large").exists()
    large: list = [t for t in todo if big(t)] if packed else []
    small = [t for t in todo if not big(t)] if packed else todo
    if small:
        status: dict = {}

        def persist(i, r):
            status[i] = record(i, r, small)
            if status[i] == "too_large":
                small[i][2].with_suffix(".too_large").write_text(C.utc() + "\n", encoding="utf-8")
        submit(be, items_of(small, volume=not packed), packed=packed, kind="fit", label=label, on_item=persist)
        large += [small[i] for i in range(len(small)) if status.get(i) == "too_large"]
        for i in range(len(small)):
            if i not in status:
                record(i, RuntimeError("no result returned"), small)
    if large:
        # the large models: again on the UNPACKED class, which may write the fit volume (packed jobs never do)
        submit(be, items_of(large, volume=True), packed=False, kind="fit", label=f"{label}-large",
               on_item=lambda i, r: record(i, r, large))
    for s, k, base, job in todo:
        if k not in out:
            record_fail = {"ok": False, "error": "no result returned"}
            C.dump_json({"error": record_fail["error"], "variant": s["variant"], "utc": C.utc()}, base.with_suffix(".fitlog.json"))
            out[k] = record_fail
    return out


def stage_models(be, paths: list[Path]) -> list[dict]:
    """Stage local model files for one wave (`common.ModelStager`): [{"inline": bytes} | {"model_path", "model_sha256"}]."""
    return C.ModelStager(be).stage_many([Path(p).read_bytes() for p in paths])


def run_evals(be, specs: list[dict], *, key: str, run: Path, lift: bool = True, n_boot: int = 2000, refit: bool = False,
              packed: bool = True, label: str = "evals") -> dict:
    """specs: [{"variant", "sid", "sysd", "seed"}] (the model is read from the variant's fit) -> {(variant, sid, seed): ok / error}.
    Every evaluation runs `p4post_iso:eval_c`: the benchmark's unchanged `harness.evaluate_job` (every metric family) on the model
    (inline, or from the fit volume when large), its output lzma-compressed when large (p4post_iso, size limits)."""
    out: dict = {}
    pend, owners = [], []
    for s in sorted(specs, key=_order_key):
        k = (s["variant"], s["sid"], int(s["seed"]))
        epath = _paths(run, s["variant"], s["sid"], s["seed"], "evals").with_suffix(".pkl")
        if epath.exists() and not refit:
            out[k] = {"ok": True, "cached": True}
            continue
        fail = None if refit else _cached_failure(epath.with_suffix("").with_suffix(".evallog.json"))
        if fail is not None:
            out[k] = {"ok": False, "error": fail, "cached": True}
            continue
        mp = model_path(run, s["variant"], s["sid"], s["seed"])
        if not mp.exists():
            out[k] = {"ok": False, "error": "no fitted model"}
            continue
        pend.append((s, mp))
        owners.append((s, k))
    staged = stage_models(be, [mp for _, mp in pend]) if pend else []           # BEFORE the wave's containers start
    items = []
    for (s, mp), st in zip(pend, staged):
        job = C.eval_job(s["sid"], s["sysd"], lift=lift, n_boot=n_boot, seed=int(s["seed"]))
        job.update({k2: v for k2, v in st.items() if k2 != "inline"})
        p = C.iso_call_payload("eval_c", job, key, model=st.get("inline"))
        items.append((p, s["sysd"], s["sid"], f"eval|{s['variant']}|{s['sid']}|{s['seed']}|{int(lift)}", EVAL_CLS[s["sysd"]["kind"]], PACK_EVAL))

    def persist(i: int, r) -> None:
        s, k = owners[i]
        base = _paths(run, s["variant"], s["sid"], s["seed"], "evals")
        val, err = C.iso_result(r, "result")
        val = C.decode_output(val)
        if isinstance(val, dict) and "result" in val:
            tmp = base.with_suffix(".pkl.part")
            with open(tmp, "wb") as fh:
                pickle.dump(val, fh, protocol=pickle.HIGHEST_PROTOCOL)
            tmp.replace(base.with_suffix(".pkl"))
            base.with_suffix(".evallog.json").unlink(missing_ok=True)
            out[k] = {"ok": True}
        else:
            err = err or (str(val.get("error")) if isinstance(val, dict) and val.get("error") else "no result")
            C.dump_json({"error": str(err)[-4000:], "utc": C.utc()}, base.with_suffix(".evallog.json"))
            out[k] = {"ok": False, "error": err}
    if items:
        submit(be, items, packed=packed, kind="eval", label=label, on_item=persist)
    for i, (s, k) in enumerate(owners):
        if k not in out:
            persist(i, RuntimeError("no result returned"))
    return out


def run_custom(be, role: str, specs: list[dict], *, key: str, packed: bool = True, label: str | None = None,
               done_dir: Path | None = None) -> list:
    """Trusted iso "call" jobs (`p4post_iso:<role>`): specs [{"sid", "sysd", "job", "model_path"}] -> [(result | None, error | None)]
    in spec order. Models are staged (inline / fit volume) before the wave; outputs are decoded (lzma) when large."""
    staged = stage_models(be, [s["model_path"] for s in specs if s.get("model_path")]) if specs else []
    it = iter(staged)
    items = []
    for s in specs:
        st = next(it) if s.get("model_path") else {}
        job = dict(s["job"], **{k2: v for k2, v in st.items() if k2 != "inline"})
        p = C.iso_call_payload(role, job, key, model=st.get("inline"))
        jkey = f"{role}|{s['sid']}|{json.dumps(s['job'], sort_keys=True, default=str)[:400]}"
        items.append((p, s["sysd"], s["sid"], jkey, EVAL_CLS[s["sysd"]["kind"]], PACK_EVAL))
    res = submit(be, items, packed=packed, kind="custom", label=label or role, done_dir=done_dir) if items else []
    out = []
    for r in res:
        val, err = C.iso_result(r, "result")
        val = C.decode_output(val)
        if isinstance(val, dict) and val.get("error") and len(val) <= 3:
            out.append((None, str(val["error"])))
        else:
            out.append((val, None) if isinstance(val, dict) else (None, err or f"no result: {str(r)[:300]}"))
    return out


def describe(be, methods: list[str], key: str, packed: bool = True) -> dict:
    """{method: device} read in a worker (role describe)."""
    pls = [{"role": "describe", "job": {"method": m}, "methods_key": key} for m in methods]
    if packed:
        res = be.run_iso_packed(pls, PACK_FIT, label="describe")
    else:
        res = be.run([dict(p, kind="iso") for p in pls], "iso_fit_s", "describe")
    out = {}
    for m, r in zip(methods, res):
        d = ((r or {}).get("describe") or {}) if isinstance(r, dict) else {}
        out[m] = d.get("device", "cpu") if d else f"error: {str(r)[:300]}"
    return out


def wall(t0: float) -> float:
    return round(time.time() - t0, 1)
