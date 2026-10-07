"""The MODEL WORKER: the only process that ever runs method / designer code (research/phase4/EVAL_ARCHITECTURE.md).

A worker is a fresh Python process that the trusted DRIVER (`brainir_causal.isolation`) starts for ONE job role of one (method,
system): a fit, an experiment loop, or one phase of an evaluation. On Linux it runs as an unprivileged uid with a scrubbed
environment and an empty private working directory, in a container without network; on the development machine it runs in the Docker
sandbox. It imports only the PUBLIC modules of `brainir_causal` (a copy in their own read-only directory), the frozen earlier baseline
and the method snapshot. It never sees held-out data, truth, the salt, the synthetic generator, the store, other methods or
credentials: the driver sends it exactly the arguments of the calls it must answer (and, for fits and loops, the public training
records).

Wire protocol (over pipes; each frame = 8-byte big-endian length + payload):
  driver -> worker   pickle of {"id", "op", ...} (the driver is trusted; only the worker unpickles)
  worker -> driver   SAFE encoding (`encode_safe`): a JSON header describing the value (dicts, lists, str, numbers, None, bools) with
                     numeric numpy arrays and raw bytes carried in an UNCOMPRESSED .npz. The driver decodes it with json and
                     `np.load(allow_pickle=False)` only (`decode_safe`: compressed or oversized members, object arrays, unknown markers
                     and deep nesting are refused), so nothing a worker sends can execute code in the driver.
The worker writes frames on a private duplicate of its original stdout; fd 1 and sys.stdout go to stderr and fd 0 to /dev/null
before any method code runs, so prints cannot corrupt the protocol.

Ops: init (mount the method snapshot, thread limits, pre-import of the scientific stack, the runguard TRIPWIRE), describe (the
method's declared name, version, device, designer), load_model (the pristine model bytes; every later call runs on a FRESH unpickled
copy, PROTOCOL.md section 5), call / calls (CausalStateModel API calls; allow-listed names only), capacity (the section 5.15 record
on a fresh copy), fit (a method fit: returns the model BYTES and a side record, never an object), loop_init / loop_fit / loop_update /
loop_propose / loop_call / loop_info / loop_bytes (the method side of an experiment loop whose driver, policy check, budget accounting
and simulator are trusted and live elsewhere), stats, ping, shutdown.
"""

from __future__ import annotations

import importlib
import io
import json
import os
import pickle
import struct
import sys
import time
import traceback
import types
import zipfile
from pathlib import Path

import numpy as np

METHODS_PKG = "brainir_causal.methods"
MAGIC = b"P4W1"
MAX_HEADER = 512 * 1024 * 1024
MAX_FRAME = 8 * 1024 ** 3
MAX_DEPTH = 64
#: the CausalStateModel API the evaluator may call on a model (anything else is refused)
API_CALLS = ("encode", "rollout", "readout", "supports", "step", "read_in", "intervention_effect", "lift", "uncertainty", "validity",
             "info", "schema")
#: optional API methods whose override the driver's proxy mirrors (evaluate_lift.lift_supported checks the class of the model)
OVERRIDABLE = ("lift", "read_in", "uncertainty", "validity", "step", "intervention_effect", "supports")
#: the public modules of brainir_causal a worker may import: the clean room's public modules (make_phase4_cleanroom.CLEAN_MODULES),
#: the worker itself, the tripwire and the cost accounting the public modules import. `isolation.build_pubdir` copies exactly these
PUBLIC_MODULES = ("__init__", "api", "protocol", "families", "data", "evalio", "fresh", "stats", "evaluate", "evaluate_mediation",
                  "evaluate_micro", "evaluate_lift", "evaluate_stability", "evaluate_transfer", "verdict", "refs", "harness", "loop",
                  "designers", "capacity", "calibstats", "equiv", "simclient", "select", "frozen_v1", "worker", "runguard", "accounting",
                  "sampling")                 # the public-policy sampler designers import (review H round 3, NEW-3); never `suites`


# ================================================================================================================ framing
def read_frame(fh, max_frame: int = MAX_FRAME) -> bytes | None:
    """One frame, or None at a clean end of stream."""
    head = _read_exact(fh, 8)
    if head is None:
        return None
    if len(head) < 8:
        raise EOFError("truncated frame header")
    (n,) = struct.unpack(">Q", head)
    if n > max_frame:
        raise ValueError(f"frame of {n} bytes exceeds the limit of {max_frame}")
    body = _read_exact(fh, n)
    if body is None or len(body) < n:
        raise EOFError("truncated frame")
    return body


def _read_exact(fh, n: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < n:
        chunk = fh.read(n - len(buf))
        if not chunk:
            return None if not buf else bytes(buf)
        buf += chunk
    return bytes(buf)


def write_frame(fh, payload: bytes) -> None:
    fh.write(struct.pack(">Q", len(payload)))
    fh.write(payload)
    fh.flush()


# ================================================================================================================ safe codec
def _sanitize(o, arrays: list, depth: int = 0):
    """A JSON-able description of o; numeric arrays and bytes go to `arrays` (never pickled)."""
    if depth > MAX_DEPTH:
        raise ValueError("value nested too deeply")
    if o is None or isinstance(o, bool):
        return o
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        v = int(o)
        return v if abs(v) < 2 ** 63 else float(v)
    if isinstance(o, (float, np.floating)):
        return float(o)
    if isinstance(o, str):
        return str(o)
    if isinstance(o, (bytes, bytearray, memoryview)):
        arrays.append(np.frombuffer(bytes(o), dtype=np.uint8))
        return {"__b__": len(arrays) - 1}
    if isinstance(o, np.ndarray):
        if o.dtype.kind not in "biufc":
            raise TypeError(f"array of dtype {o.dtype} cannot be returned (numeric arrays only)")
        arrays.append(np.ascontiguousarray(o))
        return {"__nd__": len(arrays) - 1}
    if isinstance(o, dict):
        return {"__d__": [[_sanitize(k, arrays, depth + 1) if (k is None or isinstance(k, (str, int, float, bool))) else str(k),
                           _sanitize(v, arrays, depth + 1)] for k, v in o.items()]}
    if isinstance(o, (list, tuple)):
        return [_sanitize(x, arrays, depth + 1) for x in o]
    if isinstance(o, (set, frozenset)):
        return [_sanitize(x, arrays, depth + 1) for x in sorted(o, key=repr)]
    dump = getattr(o, "model_dump", None)                     # pydantic models (e.g. schema())
    if callable(dump):
        return _sanitize(dump(), arrays, depth + 1)
    if hasattr(o, "__dataclass_fields__"):
        return _sanitize({k: getattr(o, k) for k in o.__dataclass_fields__}, arrays, depth + 1)
    if type(o).__module__ == "torch" or type(o).__name__ == "Tensor":
        try:
            return _sanitize(o.detach().cpu().numpy(), arrays, depth + 1)
        except Exception:  # noqa: BLE001, S110 - falls through to the repr
            pass
    return {"__repr__": repr(o)[:500]}


def encode_safe(obj) -> bytes:
    arrays: list[np.ndarray] = []
    head = json.dumps(_sanitize(obj, arrays), allow_nan=True, separators=(",", ":")).encode("utf-8")
    buf = io.BytesIO()
    if arrays:
        np.savez(buf, **{f"a{i}": a for i, a in enumerate(arrays)})
    return MAGIC + struct.pack(">Q", len(head)) + head + buf.getvalue()


def decode_safe(blob: bytes, max_array_bytes: int = MAX_FRAME):
    """The inverse of encode_safe using json and np.load(allow_pickle=False) only. Refuses compressed or oversized archive members
    (decompression bombs), object arrays, unknown markers and excessive nesting."""
    if blob[:4] != MAGIC or len(blob) < 12:
        raise ValueError("not a worker reply")
    (n,) = struct.unpack(">Q", blob[4:12])
    if n > MAX_HEADER or 12 + n > len(blob):
        raise ValueError("malformed reply header")
    head = json.loads(blob[12: 12 + n].decode("utf-8"))
    arrays: dict = {}
    body = blob[12 + n:]
    if body:
        zf = zipfile.ZipFile(io.BytesIO(body))
        total = 0
        for info in zf.infolist():
            if info.compress_type != zipfile.ZIP_STORED:
                raise ValueError("compressed archive members are refused")
            total += info.file_size
            if info.file_size > max_array_bytes or total > max_array_bytes:
                raise ValueError("reply arrays exceed the size limit")
        with np.load(io.BytesIO(body), allow_pickle=False) as z:
            arrays = {k: z[k] for k in z.files}

    def dec(o, depth=0):
        if depth > MAX_DEPTH:
            raise ValueError("reply nested too deeply")
        if o is None or isinstance(o, (bool, int, float, str)):
            return o
        if isinstance(o, list):
            return [dec(x, depth + 1) for x in o]
        if isinstance(o, dict):
            if set(o) == {"__nd__"}:
                a = arrays[f"a{int(o['__nd__'])}"]
                if a.dtype.kind not in "biufc":
                    raise ValueError("non-numeric array in a reply")
                return a
            if set(o) == {"__b__"}:
                return arrays[f"a{int(o['__b__'])}"].astype(np.uint8).tobytes()
            if set(o) == {"__d__"}:
                out = {}
                for pair in o["__d__"]:
                    if not isinstance(pair, list) or len(pair) != 2:
                        raise ValueError("malformed dict in a reply")
                    k = pair[0]
                    k = k if (k is None or isinstance(k, (str, int, float, bool))) else str(k)
                    out[k] = dec(pair[1], depth + 1)
                return out
            if set(o) == {"__repr__"}:
                return {"__repr__": str(o["__repr__"])[:500]}
            raise ValueError("unknown marker in a reply")
        raise ValueError(f"unexpected value of type {type(o).__name__} in a reply")
    return dec(head)


# ================================================================================================================ the method package
def mount_methods(method_dir: str | Path) -> None:
    """`brainir_causal.methods` resolves to method_dir (the method snapshot)."""
    import brainir_causal
    method_dir = str(Path(method_dir).resolve())
    for k in [k for k in sys.modules if k == METHODS_PKG or k.startswith(METHODS_PKG + ".")]:
        del sys.modules[k]
    mod = types.ModuleType(METHODS_PKG)
    mod.__path__ = [method_dir]
    mod.__package__ = METHODS_PKG
    sys.modules[METHODS_PKG] = mod
    brainir_causal.methods = mod


def method_modules(method_dir: str | Path) -> list[str]:
    """Dotted module names (relative to the methods package) of every module of the snapshot: top-level modules and the modules of
    the developers' own packages methods/<prefix>/ (review F round 2, N-M2: one package per developer), in sorted path order."""
    root = Path(method_dir)
    out = []
    for p in sorted(root.rglob("*.py")):
        rel = p.relative_to(root)
        if "__pycache__" in rel.parts or any(part.startswith(".") for part in rel.parts):
            continue
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
            if not parts:
                continue
        if all(part.isidentifier() for part in parts):
            out.append(".".join(parts))
    return out


def import_method(method_dir: str | None, name: str):
    """The registered method `name` ("module:name" with a dotted module path such as "li.ssm:li_ssm", or a plain name; the frozen
    earlier baseline is built in). A plain name is looked up in the module of the same name, else every module of the package
    (developers' subpackages included) is imported (a module that fails is skipped)."""
    from .api import get_method, registered
    if name == "frozen_brainir_state_v1":
        importlib.import_module("brainir_causal.frozen_v1")
        return get_method(name)
    if ":" in name:
        module, meth = name.split(":", 1)
        importlib.import_module(f"{METHODS_PKG}.{module}")
        return get_method(meth)
    try:
        importlib.import_module(f"{METHODS_PKG}.{name}")
    except ModuleNotFoundError as e:
        if e.name != f"{METHODS_PKG}.{name}" and not str(e.name or "").startswith(f"{METHODS_PKG}.{name}."):
            raise
    if name not in registered() and method_dir:
        for mod in method_modules(method_dir):
            if name in registered():
                break
            try:
                importlib.import_module(f"{METHODS_PKG}.{mod}")
            except Exception:  # noqa: BLE001, S112 - another developer's broken module must not hide a registered method
                continue
    return get_method(name)


def overrides(model) -> dict:
    """Which optional API methods the model's class overrides."""
    from .api import CausalStateModel
    return {n: getattr(type(model), n, None) is not getattr(CausalStateModel, n, None) for n in OVERRIDABLE}


def _threads(n: int) -> None:
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[var] = str(n)
    try:
        import threadpoolctl
        threadpoolctl.threadpool_limits(int(n))
    except Exception:  # noqa: BLE001, S110
        pass
    try:
        import torch
        torch.set_num_threads(int(n))
    except Exception:  # noqa: BLE001, S110
        pass


def platform_record() -> dict:
    """Where the worker runs (goal5 section 63: the fits of one evaluation run on one platform and, for GPU methods, one GPU class)."""
    import platform
    rec = {"python": sys.version.split()[0], "platform": platform.platform(), "machine": platform.machine(), "n_cpu": os.cpu_count(),
           "uid": getattr(os, "getuid", lambda: None)()}
    try:
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", encoding="utf-8") as fh:
                rec["cpu"] = next((line.split(":", 1)[1].strip() for line in fh if line.startswith("model name")), None)
    except OSError:
        rec["cpu"] = None
    try:
        import torch
        rec["torch"] = torch.__version__
        rec["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            rec["gpu"] = torch.cuda.get_device_name(0)
    except Exception:  # noqa: BLE001
        rec["torch"] = None
    return rec


def _peak_mb() -> float | None:
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:  # noqa: BLE001 - Windows
        return None


# ================================================================================================================ ops
class State:
    def __init__(self):
        self.method_dir: str | None = None
        self.pristine: bytes | None = None
        self.loop: dict = {}
        self.tripwire = None
        self.n_calls = 0
        self.platform: dict | None = None


def _fresh(st: State):
    if st.pristine is None:
        raise RuntimeError("no model loaded")
    return pickle.loads(st.pristine)


def _call(model, name: str, args, kwargs):
    if name not in API_CALLS:
        raise PermissionError(f"{name!r} is not a model API call")
    return getattr(model, name)(*(args or ()), **(kwargs or {}))


def op_init(st: State, m: dict) -> dict:
    st.method_dir = m.get("method_dir") or None
    _threads(int(m.get("threads", 2)))
    pre = {}
    if m.get("preimport", True):
        from .runguard import preimport
        pre = preimport(st.method_dir)
    if st.method_dir:
        mount_methods(st.method_dir)
    plat = st.platform = platform_record()            # before the tripwire (platform.uname() may start `uname -p`)
    if m.get("tripwire", True):
        from .runguard import install_tripwire
        st.tripwire = install_tripwire(list(m.get("allowed") or []) + ([st.method_dir] if st.method_dir else []) + [os.getcwd()])
    return {"platform": plat, "preimport": {"n_imported": len(pre.get("imported", [])), "failed": pre.get("failed", [])},
            "tripwire": st.tripwire is not None}


def op_describe(st: State, m: dict) -> dict:
    if st.method_dir is None and m["method"] != "frozen_brainir_state_v1":
        raise RuntimeError("no method snapshot mounted")
    method = import_method(st.method_dir, m["method"])
    return {"name": getattr(method, "name", m["method"]), "version": str(getattr(method, "version", "?")),
            "device": str(getattr(method, "device", "cpu") or "cpu"), "has_designer": method.designer() is not None,
            "supported_sharing": list(getattr(method, "supported_sharing", ()) or ()),
            "supports_adaptation": bool(getattr(method, "supports_adaptation", False))}


def op_load_model(st: State, m: dict) -> dict:
    blob = bytes(m["blob"])
    model = pickle.loads(blob)
    st.pristine = blob
    try:
        info = model.info() or {}
    except Exception as e:  # noqa: BLE001
        info = {"info_error": f"{type(e).__name__}: {e}"[:300]}
    k_attr = getattr(model, "k", None)
    return {"class": f"{type(model).__module__}.{type(model).__qualname__}", "overrides": overrides(model), "info": info,
            "k_attr": dict(k_attr) if isinstance(k_attr, dict) else {}}


def op_call(st: State, m: dict):
    st.n_calls += 1
    return _call(_fresh(st), m["name"], m.get("args"), m.get("kwargs"))


def op_calls(st: State, m: dict) -> list:
    out = []
    for c in m["calls"]:
        st.n_calls += 1
        try:
            out.append({"ok": _call(_fresh(st), c["name"], c.get("args"), c.get("kwargs"))})
        except Exception as e:  # noqa: BLE001 - per call
            out.append({"error": f"{type(e).__name__}: {str(e)[:300]}"})
    return out


def op_capacity(st: State, m: dict) -> dict:
    from .capacity import capacity_record
    return capacity_record(_fresh(st), list(m["sids"]))


def _model_bytes(model) -> bytes:
    """The model as saved by its own save() (the API default is a pickle of the object), read back as bytes."""
    p = Path(os.getcwd()) / f".model_{os.getpid()}_{time.time_ns()}.pkl"
    try:
        if hasattr(model, "save"):
            model.save(p)
        else:
            with open(p, "wb") as fh:
                pickle.dump(model, fh, protocol=pickle.HIGHEST_PROTOCOL)
        return p.read_bytes()
    finally:
        p.unlink(missing_ok=True)


def op_fit(st: State, m: dict) -> dict:
    from .capacity import ComputeMeter
    method = import_method(st.method_dir, m["method"])
    config = dict(m.get("config") or {})
    if m.get("adapt_from") is not None:
        config["adapt_from"] = pickle.loads(bytes(m["adapt_from"]))
    t0 = time.time()
    with ComputeMeter() as meter:
        model = method.fit(list(m["records"]), systems=dict(m["systems"]), config=config, seed=int(m.get("seed", 0)))
    blob = _model_bytes(model)
    try:
        info = model.info() or {}
    except Exception as e:  # noqa: BLE001
        info = {"info_error": repr(e)[:300]}
    return {"model": blob, "side": {"method": m["method"], "method_version": str(getattr(method, "version", "?")),
                                    "device": str(getattr(method, "device", "cpu") or "cpu"), "fit_wall_s": round(time.time() - t0, 2),
                                    "compute": meter.as_dict(), "info": info, "platform": st.platform, "peak_mb": _peak_mb(),
                                    "n_train": len(m["records"])}}


def op_loop_init(st: State, m: dict) -> dict:
    method = import_method(st.method_dir, m["method"])
    designer = None
    if m.get("own_designer"):
        designer = method.designer()
        if designer is None:
            raise RuntimeError(f"{m['method']} has no designer of its own")
    st.loop = {"method": method, "designer": designer, "model": None, "data": [], "systems": dict(m["systems"]),
               "config": dict(m.get("config") or {}), "seed": int(m.get("seed", 0))}
    return {"designer": None if designer is None else str(getattr(designer, "name", type(designer).__name__)),
            "device": str(getattr(method, "device", "cpu") or "cpu"), "platform": st.platform}


def op_loop_fit(st: State, m: dict) -> dict:
    L = st.loop
    c0 = time.process_time()
    L["data"] = list(m["records"])
    L["model"] = L["method"].fit(L["data"], systems=L["systems"], config=dict(L["config"]), seed=L["seed"])
    return {"n": len(L["data"]), "cpu_s": time.process_time() - c0}


def op_loop_update(st: State, m: dict) -> dict:
    L = st.loop
    c0 = time.process_time()
    new = list(m["records"])
    L["data"] += new
    L["model"] = L["method"].update(L["model"], new, data_all=L["data"], systems=L["systems"], config=dict(L["config"]), seed=L["seed"])
    return {"n": len(L["data"]), "cpu_s": time.process_time() - c0}


def op_loop_propose(st: State, m: dict) -> dict:
    L = st.loop
    if L.get("designer") is None:
        raise RuntimeError("the loop has no worker-side designer")
    c0 = time.process_time()
    rng = np.random.default_rng(int(m["rng_seed"]))
    props = L["designer"].propose(m["system_id"], dict(m["sysrec"]), L["model"], L["data"], int(m["n"]), int(m["budget_left"]), rng)
    return {"proposals": [dict(p) for p in (props or [])], "cpu_s": time.process_time() - c0}


def op_loop_call(st: State, m: dict):
    return _call(st.loop["model"], m["name"], m.get("args"), m.get("kwargs"))


def op_loop_info(st: State, m: dict) -> dict:
    return dict(st.loop["model"].info() or {})


def op_loop_bytes(st: State, m: dict) -> dict:
    return {"model": _model_bytes(st.loop["model"])}


def op_stats(st: State, m: dict) -> dict:
    hits = st.tripwire.hits if st.tripwire is not None else None
    return {"pid": os.getpid(), "n_calls": st.n_calls, "peak_mb": _peak_mb(), "tripwire_hits": None if hits is None else len(hits),
            "tripwire_first": None if hits is None else [list(h) for h in hits[:5]]}


OPS = {"init": op_init, "describe": op_describe, "load_model": op_load_model, "call": op_call, "calls": op_calls, "capacity": op_capacity,
       "fit": op_fit, "loop_init": op_loop_init, "loop_fit": op_loop_fit, "loop_update": op_loop_update, "loop_propose": op_loop_propose,
       "loop_call": op_loop_call, "loop_info": op_loop_info, "loop_bytes": op_loop_bytes, "stats": op_stats,
       "ping": lambda st, m: {"pid": os.getpid(), "t": time.time()}}


def main() -> int:
    out_fd = os.dup(1)
    in_fd = os.dup(0)
    os.dup2(2, 1)                                    # prints (Python or native) go to stderr, never into the protocol
    try:
        null = os.open(os.devnull, os.O_RDONLY)
        os.dup2(null, 0)
        os.close(null)
    except OSError:
        pass
    sys.stdout = sys.stderr
    fin = os.fdopen(in_fd, "rb", buffering=0)
    fout = os.fdopen(out_fd, "wb", buffering=0)
    st = State()
    while True:
        raw = read_frame(fin)
        if raw is None:
            return 0
        msg = pickle.loads(raw)                      # from the trusted driver
        rid = msg.get("id")
        if msg.get("op") == "shutdown":
            write_frame(fout, encode_safe({"id": rid, "ok": op_stats(st, msg)}))
            return 0
        try:
            res = OPS[msg["op"]](st, msg)
            try:
                payload = encode_safe({"id": rid, "ok": res})
            except Exception as e:  # noqa: BLE001 - an unencodable result is an error of the call
                payload = encode_safe({"id": rid, "error": f"unencodable result: {type(e).__name__}: {e}"[:1000]})
        except BaseException as e:  # noqa: BLE001 - every failure is reported to the driver, never fatal to the protocol
            payload = encode_safe({"id": rid, "error": f"{type(e).__name__}: {e}"[:2000], "traceback": traceback.format_exc()[-4000:]})
        write_frame(fout, payload)


if __name__ == "__main__":
    raise SystemExit(main())
