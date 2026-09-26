"""CPU / GPU numerical equivalence of seeded training (goal5 section 63 and acceptance criterion 39). Orchestrator tool; the training
runs themselves are ordinary torch code and run anywhere (locally, in a CPU container, on a GPU container).

A run is described by a BUILDER, "module:function", called as `builder(config, dtype, device, seed)` and returning a trainer with
    step() -> float                 one optimisation step, returns the loss
    state() -> {name: np.ndarray}   the parameters (float64 copies)
    predict() -> np.ndarray         predictions on a fixed held-out batch
The builder must initialise the parameters and the data on the CPU from `seed` and only then cast / move them, so that every device
starts from the same numbers (`reference_trainer` does this).

`run_training` fixes the determinism settings (deterministic algorithms, cuDNN deterministic and no autotuning, TF32 off for
matmul and cuDNN, a fixed cuBLAS workspace), runs `steps` steps and returns the loss curve, the final parameters and the held-out
predictions. `compare(ref, other, dtype)` measures the differences against TOLERANCES, stated before any GPU run:

- float64: the loss curve, the parameters (norm-wise) and the predictions (norm-wise) must agree to 1e-9 / 1e-8 / 1e-8 relative.
  Different devices sum in different orders, so bitwise identity is not expected; float64 rounding differences (~1e-16 per
  operation) amplified over tens of optimisation steps stay orders of magnitude below these bounds.
- float32 (TF32 off): 1e-3 relative for the loss curve, the parameters and the predictions (float32 rounding ~1e-7 per operation,
  amplified by the optimiser; 1e-3 is still far below any difference a method comparison could resolve).
A method that trains on a GPU passes criterion 39 if its own builder passes `compare` against a CPU run at the dtype it uses, and if
two GPU runs of the same seed are bitwise identical (run-to-run determinism on one GPU class).
"""

from __future__ import annotations

import importlib
import os
import time

import numpy as np

TOLERANCES = {
    "float64": {"loss_rel": 1e-9, "param_rel": 1e-8, "pred_rel": 1e-8},
    "float32": {"loss_rel": 1e-3, "param_rel": 1e-3, "pred_rel": 1e-3},
}


def set_determinism(device: str) -> dict:
    """Deterministic execution settings; returns the PREVIOUS settings (for `restore_determinism`). CUBLAS_WORKSPACE_CONFIG must be
    set before the first cuBLAS call of the process (it is set here, before any CUDA work of this module)."""
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    import torch
    prev = {"det": torch.are_deterministic_algorithms_enabled(), "cudnn_det": torch.backends.cudnn.deterministic,
            "cudnn_bench": torch.backends.cudnn.benchmark, "tf32_mm": torch.backends.cuda.matmul.allow_tf32,
            "tf32_cudnn": torch.backends.cudnn.allow_tf32}
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    return prev


def restore_determinism(prev: dict) -> None:
    import torch
    torch.use_deterministic_algorithms(prev["det"])
    torch.backends.cudnn.deterministic = prev["cudnn_det"]
    torch.backends.cudnn.benchmark = prev["cudnn_bench"]
    torch.backends.cuda.matmul.allow_tf32 = prev["tf32_mm"]
    torch.backends.cudnn.allow_tf32 = prev["tf32_cudnn"]


SETTINGS = {"deterministic_algorithms": True, "cudnn_deterministic": True, "cudnn_benchmark": False, "tf32": False,
            "cublas_workspace": ":4096:8"}


def _builder(name: str):
    mod, _, fn = name.partition(":")
    return getattr(importlib.import_module(mod), fn)


def run_training(builder: str, config: dict, device: str, dtype: str, seed: int = 0, steps: int = 50) -> dict:
    import torch
    prev = set_determinism(device)
    try:
        tr = _builder(builder)(dict(config), dtype, device, int(seed))
        t0 = time.perf_counter()
        losses = [float(tr.step()) for _ in range(int(steps))]
        if device == "cuda":
            torch.cuda.synchronize()
        wall = time.perf_counter() - t0
        params, pred = tr.state(), tr.predict()
    finally:
        restore_determinism(prev)
    from .p4modal.benchwork import device_info
    return {"builder": builder, "config": config, "device": device, "dtype": dtype, "seed": int(seed), "steps": int(steps),
            "losses": losses, "params": params, "pred": pred, "train_wall_s": round(wall, 4),
            "settings": dict(SETTINGS, cublas_workspace=os.environ.get("CUBLAS_WORKSPACE_CONFIG")), "info": device_info(device)}


def _flat(params: dict) -> np.ndarray:
    return np.concatenate([np.asarray(params[k], dtype=np.float64).ravel() for k in sorted(params)])


def compare(ref: dict, other: dict, dtype: str | None = None) -> dict:
    """Relative differences of two runs of the same builder / config / seed, and whether they are within TOLERANCES[dtype]."""
    dtype = dtype or ref["dtype"]
    tol = TOLERANCES[dtype]
    la, lb = np.asarray(ref["losses"], dtype=np.float64), np.asarray(other["losses"], dtype=np.float64)
    loss_rel = float(np.max(np.abs(la - lb) / np.maximum(np.abs(la), 1e-300))) if la.size else 0.0
    pa, pb = _flat(ref["params"]), _flat(other["params"])
    param_rel = float(np.linalg.norm(pa - pb) / max(np.linalg.norm(pa), 1e-300))
    per_tensor = {k: float(np.max(np.abs(np.asarray(ref["params"][k], dtype=np.float64) - np.asarray(other["params"][k], dtype=np.float64)))
                           / max(float(np.max(np.abs(np.asarray(ref["params"][k], dtype=np.float64)))), 1e-300))
                  for k in sorted(ref["params"])}
    ya, yb = np.asarray(ref["pred"], dtype=np.float64), np.asarray(other["pred"], dtype=np.float64)
    pred_rel = float(np.linalg.norm(ya - yb) / max(np.linalg.norm(ya), 1e-300))
    bitwise = bool(np.array_equal(la, lb) and np.array_equal(pa, pb) and np.array_equal(ya, yb))
    out = {"dtype": dtype, "tolerances": tol, "loss_rel_max": loss_rel, "param_rel": param_rel, "param_rel_max_tensor": max(per_tensor.values()),
           "pred_rel": pred_rel, "bitwise_identical": bitwise, "final_loss": [float(la[-1]), float(lb[-1])] if la.size else None,
           "devices": [ref["device"], other["device"]]}
    out["pass"] = bool(loss_rel <= tol["loss_rel"] and param_rel <= tol["param_rel"] and pred_rel <= tol["pred_rel"])
    return out


# ------------------------------------------------------------------------------------------------ the reference trainer
class _Trainer:
    def __init__(self, model, data, held, lr: float, device: str):
        import torch
        self.model, self.data, self.held, self.device = model, data, held, device
        self.opt = torch.optim.Adam(model.parameters(), lr=lr)

    def step(self) -> float:
        import torch
        self.opt.zero_grad(set_to_none=True)
        loss = self.model.loss(self.data)
        loss.backward()
        self.opt.step()
        return float(loss.detach().to("cpu", dtype=torch.float64))

    def state(self) -> dict:
        return {k: v.detach().to("cpu").double().numpy().copy() for k, v in self.model.state_dict().items()}

    def predict(self):
        """Readout predictions on the held-out batch: the rollout's y for `rollout`, the filter's y = g(z_t) for `gru`."""
        import torch
        with torch.no_grad():
            x, u, a, _y = self.held
            if hasattr(self.model, "gru"):
                hseq, _ = self.model.gru(torch.cat([x, u], -1))
                yp = self.model.g(self.model.to_z(hseq))
            else:
                yp, _ = self.model(x, u, a)
        return yp.detach().to("cpu").double().numpy()


def reference_trainer(config: dict, dtype: str, device: str, seed: int):
    """A Phase 4-shaped model (brainir_causal.p4modal.benchwork: `rollout` = latent controlled SSM with an intervention read-in, or
    `gru` = GRU filter, cuDNN on GPUs) with parameters initialised in float64 and data created in float64 on the CPU from `seed`,
    then cast and moved (float32 runs start from the float32 rounding of the same numbers)."""
    import torch

    from .p4modal import benchwork as B
    tdt = {"float64": torch.float64, "float32": torch.float32}[dtype]
    # initialise IN float64: a float32 initialisation differs between platforms at the float32 rounding level (the uniform transform
    # of the initialisers is compiled with or without fused multiply-add), which a float64 comparison would then see as a 1e-8
    # "difference" of every later number
    prev = torch.get_default_dtype()
    torch.set_default_dtype(torch.float64)
    try:
        torch.manual_seed(int(seed))
        model = B.MODELS[config.get("kind", "rollout")](int(config.get("n_x", 20)), int(config.get("k", 4)))
    finally:
        torch.set_default_dtype(prev)
    model = model.to(dtype=tdt, device=device)
    shape = (int(config.get("batch", 16)), int(config.get("t_len", 100)), int(config.get("n_x", 20)))
    data = B.make_data(*shape, seed=int(seed), dtype=tdt, device=device)
    held = B.make_data(*shape, seed=int(seed) + 1, dtype=tdt, device=device)
    return _Trainer(model, data, held, float(config.get("lr", 1e-3)), device)


REFERENCE = "brainir_causal.equiv:reference_trainer"
REFERENCE_CONFIGS = [{"kind": "rollout", "n_x": 20, "k": 4, "t_len": 100, "batch": 16, "lr": 1e-3},
                     {"kind": "gru", "n_x": 20, "k": 4, "t_len": 100, "batch": 16, "lr": 1e-3}]


def container_pair(spec: dict) -> dict:
    """Container side (a GPU container): for every (config, dtype), a CPU run and two GPU runs of the same builder and seed, in this
    process; returns the raw runs (the orchestrator compares them, and also against its local CPU runs)."""
    out = []
    for cfg in spec["configs"]:
        for dt in spec["dtypes"]:
            cpu = run_training(spec["builder"], cfg, "cpu", dt, spec.get("seed", 0), spec.get("steps", 50))
            g1 = run_training(spec["builder"], cfg, "cuda", dt, spec.get("seed", 0), spec.get("steps", 50))
            g2 = run_training(spec["builder"], cfg, "cuda", dt, spec.get("seed", 0), spec.get("steps", 50))
            out.append({"config": cfg, "dtype": dt, "cpu": cpu, "gpu1": g1, "gpu2": g2})
    return {"runs": out}


def summarize_pair(pair: dict, local_cpu: dict | None = None) -> dict:
    """The comparisons of one (config, dtype) entry of container_pair: GPU vs the container's CPU (the equivalence test), GPU run to
    run (determinism), and optionally the container's CPU vs a local CPU run (platform difference, informational)."""
    dt = pair["dtype"]
    s = {"config": pair["config"], "dtype": dt, "gpu": pair["gpu1"]["info"].get("gpu"),
         "gpu_vs_cpu": compare(pair["cpu"], pair["gpu1"], dt), "gpu_run_to_run": compare(pair["gpu1"], pair["gpu2"], dt)}
    if local_cpu is not None:
        s["container_cpu_vs_local_cpu"] = compare(local_cpu, pair["cpu"], dt)
    s["criterion_39_pass"] = bool(s["gpu_vs_cpu"]["pass"] and s["gpu_run_to_run"]["bitwise_identical"])
    return s
