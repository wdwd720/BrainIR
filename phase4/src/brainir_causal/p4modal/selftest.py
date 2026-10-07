"""Container-start NUMERICS SELF-TEST (research/phase4/HOST_GATE_STUDY.md "Hardening"; research/phase4/LEVEL_B_EXECUTION.md section 9).

The host gate admits a Modal host by its CPU flags (no AVX-512, AVX2 present). P9 verified the two admissible host classes met so far
(AMD Zen 2 and Zen 3: bit-identical on every benchmark workload), but a host model Modal adds later could pass the flag rule and still
compute differently. This fixed micro battery turns the flag rule into a VERIFIED rule: it runs once per container (p4modal.gate.
numerics_selftest, in a fresh process with the container's pins, cached), and its output hashes must equal the recorded reference
(numerics_reference.json, built by scripts/p4/build_numerics_reference.py on admissible hosts, which must all agree); otherwise the
container refuses the host exactly as the flag gate does.

Items (fixed seeds; sha256 of every output array; BLAS / torch items at the job kinds' fixed thread counts THREADS):
  numpy/simd        numpy's SIMD-dispatched ufuncs and reductions (exp, log1p, sin, cos, tanh, sqrt, power, arctan2, expm1, sums)
  numpy/blas/t<n>   numpy's OpenBLAS: GEMM, A.T A, solve, lstsq, SVD, eigh, Cholesky, inverse, GEMV
  scipy/t<n>        scipy's own OpenBLAS / LAPACK (solve, lstsq, Cholesky, eigh, QR), sparse mat-vec, solve_ivp RK45
  torch/t<n>        torch CPU: float64 / float32 GEMM (two sizes), LAPACK (solve, lstsq, Cholesky, eigh), an MLP fitted by 20 Adam
                    steps in float64 and float32
  engine            the rate-model simulator of the real engine (brainir.sim.model.simulate, RK45 on a sparse signed network)
  generator         the synthetic generator (p4synth): one system of two types built and simulated, nominal and kick, single
                    BLAS thread as the benchmark; OPTIONAL (only where the generator is baked; recorded as absent elsewhere)

    python -m brainir_causal.p4modal.selftest [--part main|torch|engine|all] -> prints ONE JSON line: {"battery_id", "versions", "items",
                                                                           "absent", "errors", "s"}
    run_battery()                                                          -> the PARTS at once in fresh processes, merged
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

#: the thread counts of the job kinds (simulation workers 1, calibration 2, fits and evaluation drivers 3, references 4)
THREADS = (1, 2, 3, 4)
REFERENCE = Path(__file__).with_name("numerics_reference.json")
#: where the generator is baked in the images (suites.GENERATOR_CONTAINER; not imported from suites: this module stays light)
GENERATOR_DIRS = ("/repo/benchmarks/causal_state_v1/generator/src",)


def battery_id() -> str:
    """The identity of this battery: the sha256 of this module's source (line endings normalised). Any change of the battery needs a
    rebuilt reference (tests/test_numerics_selftest.py checks that the reference was built by this battery)."""
    src = Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(src).hexdigest()[:16]


def _sha(a) -> str:
    import numpy as np
    arr = np.ascontiguousarray(np.asarray(a))
    return hashlib.sha256(arr.dtype.str.encode() + repr(arr.shape).encode() + arr.tobytes()).hexdigest()


def _digest(arrays: list) -> str:
    h = hashlib.sha256()
    for a in arrays:
        h.update(_sha(a).encode())
    return h.hexdigest()


def versions(mods=("numpy", "scipy", "torch")) -> dict:
    out = {"python": sys.version.split()[0]}
    for mod in mods:
        try:
            out[mod] = __import__(mod).__version__
        except Exception:  # noqa: BLE001
            out[mod] = None
    return out


# ------------------------------------------------------------------------------------------------------------------ items
def item_numpy_simd() -> str:
    import numpy as np
    x = np.random.default_rng(11).standard_normal(4099)
    ax = np.abs(x)
    outs = [np.exp(x / 3.0), np.log1p(ax), np.sin(x), np.cos(x), np.tanh(x), np.sqrt(ax), np.power(ax, 1.7), np.arctan2(x, x[::-1]),
            np.expm1(x / 5.0), np.cumsum(x), np.array([np.sum(x), np.sum(ax), np.mean(x), np.std(x), np.linalg.norm(x),
                                                       np.max(x), np.prod(1.0 + x[:40] / 10.0)])]
    return _digest(outs)


def item_numpy_blas() -> str:
    import numpy as np
    rng = np.random.default_rng(12)
    A, B, v = rng.standard_normal((384, 384)), rng.standard_normal((384, 131)), rng.standard_normal(384)
    AtA = A.T @ A
    outs = [A @ B, AtA, A @ v, np.dot(v, v), np.linalg.solve(A + 384.0 * np.eye(384), B),
            np.linalg.lstsq(A[:, :60], B[:, :7], rcond=None)[0], np.linalg.svd(A[:96, :64], compute_uv=False),
            np.linalg.eigh(AtA[:80, :80])[0], np.linalg.cholesky(AtA[:64, :64] + np.eye(64)), np.linalg.inv(A[:50, :50] + 50.0 * np.eye(50))]
    return _digest(outs)


def item_scipy() -> str:
    import numpy as np
    import scipy.linalg as SL
    import scipy.sparse as SP
    from scipy.integrate import solve_ivp
    rng = np.random.default_rng(13)
    A, B = rng.standard_normal((256, 256)), rng.standard_normal((256, 17))
    S = A.T @ A + np.eye(256)
    cf = SL.cho_factor(S[:128, :128])
    M = SP.random(300, 300, density=0.03, random_state=np.random.RandomState(14), format="csr")
    vec = rng.standard_normal(300)
    L = -np.eye(6) + 0.3 * rng.standard_normal((6, 6))
    sol = solve_ivp(lambda t, y: L @ y + np.sin(3.0 * t), (0.0, 2.0), np.ones(6), method="RK45", rtol=1e-8, atol=1e-10,
                    t_eval=np.linspace(0.0, 2.0, 41))
    outs = [SL.solve(A + 256.0 * np.eye(256), B), SL.lstsq(A[:, :40], B)[0], SL.cho_solve(cf, B[:128]), SL.eigh(S[:60, :60])[0],
            SL.qr(A[:64, :48], mode="economic")[1], M @ vec, M.T @ (M @ vec), sol.y]
    return _digest(outs)


def item_torch(threads: int) -> str:
    """torch CPU kernels: float64 / float32 GEMM (small and large: MKL / oneDNN pick kernels by size), LAPACK (solve, lstsq,
    Cholesky, eigh), and an MLP fitted by 20 Adam steps in float64 and float32 with the backward pass and the Adam update written out
    in torch ops (the same GEMM, tanh and elementwise kernels as autograd, without its ~2.5 s engine start-up)."""
    import numpy as np
    import torch
    torch.set_num_threads(int(threads))
    rng = np.random.default_rng(15)
    outs = []
    for m_, k_, n_ in ((192, 160, 96), (640, 512, 384)):
        A, B = torch.from_numpy(rng.standard_normal((m_, k_))), torch.from_numpy(rng.standard_normal((k_, n_)))
        outs += [(A @ B).numpy(), (A.float() @ B.float()).numpy(), torch.nn.functional.linear(A.float(), B.float().T).numpy()]
    S = torch.from_numpy(rng.standard_normal((256, 256)))
    SPD = S.T @ S + 256.0 * torch.eye(256, dtype=torch.float64)
    Bv = torch.from_numpy(rng.standard_normal((256, 9)))
    outs += [torch.linalg.solve(SPD, Bv).numpy(), torch.linalg.lstsq(S[:, :40], Bv).solution.numpy(),
             torch.linalg.cholesky(SPD[:96, :96]).numpy(), torch.linalg.eigh(SPD[:64, :64])[0].numpy()]
    for dtype in (torch.float64, torch.float32):
        X = torch.from_numpy(rng.standard_normal((1024, 16))).to(dtype)
        Y = torch.from_numpy(rng.standard_normal((1024, 4))).to(dtype)
        P = [torch.from_numpy(rng.standard_normal(s) * 0.3).to(dtype) for s in ((16, 64), (64,), (64, 4), (4,))]
        m = [torch.zeros_like(p) for p in P]
        v = [torch.zeros_like(p) for p in P]
        lr, b1, b2, eps = 1e-2, 0.9, 0.999, 1e-8
        losses = []
        for step in range(1, 21):
            H = torch.tanh(X @ P[0] + P[1])
            R = H @ P[2] + P[3] - Y
            losses.append(float(torch.mean(R * R)))
            G = 2.0 * R / R.numel()
            dH = (G @ P[2].T) * (1.0 - H * H)
            grads = [X.T @ dH, dH.sum(0), H.T @ G, G.sum(0)]
            for k, g in enumerate(grads):
                m[k] = b1 * m[k] + (1.0 - b1) * g
                v[k] = b2 * v[k] + (1.0 - b2) * g * g
                P[k] = P[k] - lr * (m[k] / (1.0 - b1 ** step)) / (torch.sqrt(v[k] / (1.0 - b2 ** step)) + eps)
        outs += [p.numpy() for p in P] + [np.array(losses)]
    return _digest(outs)


def item_engine() -> str:
    import numpy as np
    import scipy.sparse as SP
    from brainir.sim.model import ModelConfig, Stimulus, sample_neuron_params, simulate
    n = 60
    rng = np.random.default_rng(16)
    W = SP.random(n, n, density=0.12, random_state=np.random.RandomState(17), format="csr")
    W.data = np.round(W.data * 40.0) * np.where(rng.random(W.data.size) < 0.3, -1.0, 1.0)
    cfg = ModelConfig(t_end=0.08)
    params = sample_neuron_params(cfg, n, seed=3)
    tr = simulate(W, params, cfg, Stimulus((0, 1, 2), (12.0,)))
    return _digest([tr.r])


def item_generator() -> str | None:
    """None when the generator is not baked in this container. The systems are of a tier name no suite uses ("selftest"), so the battery
    builds no benchmark system."""
    import numpy as np
    root = next((d for d in GENERATOR_DIRS if os.path.isdir(os.path.join(d, "p4synth"))), None)
    if root is None:
        return None
    if root not in sys.path:
        sys.path.insert(0, root)
    from p4synth.suite import build_system
    from threadpoolctl import threadpool_limits

    from brainir_causal import protocol as P
    outs = []
    with threadpool_limits(1):                     # the benchmark's reference numerics for the generator (one BLAS thread)
        for t in (1, 6):
            s = build_system("selftest", 1, t, 0, 1)
            dt = float(s.dt)                        # (not public_record(): 1-2 s of capability bookkeeping, no numerics of interest)
            q0 = P.validate({"system": s.system_id, "params_seed": 3, "t_end": 0.3, "dt": dt, "stimulus": [[0.0, 1.0]]})
            r0 = s.simulate(q0, full=True)
            outs += [r0[k] for k in ("x", "y", "z") if k in r0]
            q1 = P.validate({"system": s.system_id, "params_seed": 3, "t_end": 0.3, "dt": dt, "stimulus": [[0.0, 1.0]],
                             "events": [{"kind": "kick", "t": 0.1, "delta": {"0": 1.0}}]})
            r1 = s.simulate(q1, full=True)
            outs += [r1[k] for k in ("x", "y", "z") if k in r1]
    return _digest([np.asarray(o, dtype=np.float64) for o in outs])


#: the battery runs as three processes AT ONCE (their imports overlap: numpy + scipy ~2-3 s, torch ~2.5 s, the real engine's package
#: ~3 s; the items themselves take well under a second): "main" (numpy, scipy, generator), "torch" and "engine"
PARTS = ("main", "torch", "engine")
#: items recorded as "absent" where their code is not in the image (never a mismatch there)
OPTIONAL = ("generator",)


def item_names() -> list[str]:
    """Every item of the battery, in run order."""
    return (["numpy/simd"] + [f"{k}/t{t}" for t in THREADS for k in ("numpy/blas", "scipy", "torch")] + ["engine", "generator"])


def battery(part: str = "all") -> dict:
    """The items of `part` (one of PARTS, or "all"); an item that raises is recorded in "errors" (a host where the reference's code
    fails is not admissible)."""
    t0 = time.time()
    from threadpoolctl import threadpool_limits
    items: dict = {}
    errors: dict = {}
    absent: list = []

    def run(name, fn, *a):
        try:
            v = fn(*a)
            if v is None:
                absent.append(name)
            else:
                items[name] = v
        except Exception as e:  # noqa: BLE001 - recorded: compared as a mismatch
            errors[name] = f"{type(e).__name__}: {str(e)[:200]}"
    main_part, torch_part, engine_part = (part in (x, "all") for x in PARTS)
    if main_part:
        run("numpy/simd", item_numpy_simd)
    for t in THREADS:
        with threadpool_limits(int(t)):
            if main_part:
                run(f"numpy/blas/t{t}", item_numpy_blas)
                run(f"scipy/t{t}", item_scipy)
            if torch_part:
                run(f"torch/t{t}", item_torch, t)
    if engine_part:
        with threadpool_limits(1):
            run("engine", item_engine)
    if main_part:
        run("generator", item_generator)
    mods = (("numpy", "scipy") if main_part else ()) + (("torch",) if torch_part else ())
    return {"battery_id": battery_id(), "versions": versions(mods), "items": items, "absent": sorted(absent), "errors": errors,
            "s": round(time.time() - t0, 3)}


def run_battery(timeout_s: float = 180.0, python: str | None = None) -> dict:
    """The whole battery in FRESH processes (the container's pins, the pools sized by `subprocess_env`), its PARTS at once; the
    merged record, with "wall_s". A part that crashes (e.g. SIGSEGV in a BLAS kernel) or times out is recorded in "errors"."""
    import contextlib
    import subprocess
    import tempfile
    t0 = time.time()
    out: dict = {"battery_id": None, "versions": {}, "items": {}, "absent": [], "errors": {}, "s": 0.0}
    with contextlib.ExitStack() as stack:
        errs = {p: stack.enter_context(tempfile.TemporaryFile()) for p in PARTS}   # stderr to files: never blocks on a full pipe
        procs = {p: subprocess.Popen([python or sys.executable, "-m", "brainir_causal.p4modal.selftest", "--part", p],
                                     stdout=subprocess.PIPE, stderr=errs[p], text=True, env=subprocess_env()) for p in PARTS}
        for p, proc in procs.items():
            try:
                so, _ = proc.communicate(timeout=max(1.0, timeout_s - (time.time() - t0)))
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                out["errors"][f"part:{p}"] = f"timeout after {timeout_s:.0f} s"
                continue
            lines = [ln for ln in (so or "").splitlines() if ln.startswith("{")]
            if proc.returncode != 0 or not lines:
                errs[p].seek(0)
                out["errors"][f"part:{p}"] = f"exit {proc.returncode}: {errs[p].read().decode('utf-8', 'replace')[-400:]}"
                continue
            r = json.loads(lines[-1])
            out["battery_id"] = r["battery_id"]
            out["versions"].update(r.get("versions") or {})
            out["items"].update(r.get("items") or {})
            out["absent"] += list(r.get("absent") or [])
            out["errors"].update(r.get("errors") or {})
            out["s"] = max(out["s"], float(r.get("s") or 0.0))
    out["absent"] = sorted(out["absent"])
    out["wall_s"] = round(time.time() - t0, 3)
    return out


def subprocess_env() -> dict:
    """The battery's process environment: the container's (its numerics pins), with every BLAS / OpenMP pool sized for the largest of
    THREADS (the pools are fixed when the libraries load; the items then limit them per thread count)."""
    env = dict(os.environ)
    n = str(max(THREADS))
    env.update({"OMP_NUM_THREADS": n, "OPENBLAS_NUM_THREADS": n, "MKL_NUM_THREADS": n})
    return env


def load_reference(path: Path | str | None = None) -> dict:
    return json.loads(Path(path or REFERENCE).read_text(encoding="utf-8"))


def stack(v: dict | None) -> dict:
    """The library stack a reference is valid for: numpy / scipy / torch exactly, python by major.minor (the base image's patch release
    may move; the compiled libraries are the pinned wheels either way)."""
    v = dict(v or {})
    if v.get("python"):
        v["python"] = ".".join(str(v["python"]).split(".")[:2])
    return v


def compare(run: dict, ref: dict) -> dict:
    """{"ok", "stale", "mismatch", "errors"}: stale = the reference was not built by this battery or this library stack (a
    configuration fault, never a host verdict); mismatch = the items whose hashes differ from the reference (or that failed). Only an
    OPTIONAL item may be absent."""
    if run.get("battery_id") != ref.get("battery_id"):
        return {"ok": False, "stale": f"battery {run.get('battery_id')} != the reference's {ref.get('battery_id')}"}
    if stack(run.get("versions")) != stack(ref.get("versions")):
        return {"ok": False, "stale": f"library versions {run.get('versions')} != the reference's {ref.get('versions')}"}
    absent = set(run.get("absent") or []) & set(OPTIONAL)
    mism = sorted(k for k, v in (ref.get("items") or {}).items() if k not in absent and run.get("items", {}).get(k) != v)
    extra = sorted(k for k in (run.get("items") or {}) if k not in (ref.get("items") or {}))
    return {"ok": not mism and not extra and not run.get("errors"), "stale": None, "mismatch": mism + extra,
            "errors": dict(run.get("errors") or {})}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=("all",) + PARTS, default="all")
    args = ap.parse_args(argv)
    print(json.dumps(battery(args.part)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
