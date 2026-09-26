"""Representative Phase 4 training workloads (goal5 section 63), used by the GPU benchmark (scripts/p4/gpu_benchmark.py) and as the
reference model of the CPU / GPU equivalence harness (brainir_causal.equiv). Depends only on torch, so it runs in any container.

Four workload types, all latent controlled state-space models of the Phase 4 form (encoder x -> z, controlled transition with an
explicit intervention read-in r(z, a) that acts only while an intervention is active, readout z -> y, decoder z -> x):
- `rollout`  MLP encoder on a history window, then a SEQUENTIAL latent rollout over the whole trajectory (latency-bound: many small
             kernels per time step);
- `gru`      GRU filter over the whole trajectory (cuDNN on GPUs) and a multi-horizon one-step-ahead latent loss computed in
             parallel over all start times (throughput-bound);
- `ens8`     8 rollout models trained in one batched pass (batched weights, torch.baddbmm);
- `node`     a control-affine neural ODE dz/dt = f(z, u) + G(z) P a, integrated with RK4 (4 vector-field evaluations per step).
Data are random tensors of the shapes of the benchmark's systems (content does not change the cost of these computations).
"""

from __future__ import annotations

import math
import os
import platform
import time

import torch
from torch import nn

N_U, N_Y, HIST = 2, 8, 10
EPOCH_TRAJ = 1024          # trajectories per "epoch" in the reported epoch times


def mlp(sizes: list[int]) -> nn.Sequential:
    layers: list[nn.Module] = []
    for i in range(len(sizes) - 1):
        layers.append(nn.Linear(sizes[i], sizes[i + 1]))
        if i < len(sizes) - 2:
            layers.append(nn.Tanh())
    return nn.Sequential(*layers)


def _active(a_t: torch.Tensor) -> torch.Tensor:
    """1 where an intervention acts at this step (any non-zero entry), else 0: the read-in is silent without an intervention."""
    return (a_t.abs().sum(-1, keepdim=True) > 0).to(a_t.dtype)


class RolloutSSM(nn.Module):
    def __init__(self, n_x: int, k: int, width: int = 128, hist: int = HIST, dt: float = 0.1):
        super().__init__()
        self.hist, self.dt = hist, dt
        self.enc = mlp([hist * (n_x + N_U), width, width, k])
        self.f = mlp([k + N_U, width, width, k])
        self.r = mlp([k + n_x, 64, k])
        self.g = nn.Linear(k, N_Y)
        self.dec = nn.Linear(k, n_x)

    def forward(self, x, u, a):
        b, t_len, _ = x.shape
        h = self.hist
        z = self.enc(torch.cat([x[:, :h], u[:, :h]], -1).reshape(b, -1))
        ys, xs = [], []
        for t in range(h, t_len):
            z = z + self.dt * self.f(torch.cat([z, u[:, t]], -1)) + _active(a[:, t]) * self.r(torch.cat([z, a[:, t]], -1))
            ys.append(self.g(z))
            xs.append(self.dec(z))
        return torch.stack(ys, 1), torch.stack(xs, 1)

    def loss(self, batch):
        x, u, a, y = batch
        yp, xp = self(x, u, a)
        h = self.hist
        return ((yp - y[:, h:]) ** 2).mean() + ((xp - x[:, h:]) ** 2).mean()


class GRUFilter(nn.Module):
    def __init__(self, n_x: int, k: int, width: int = 128, horizon: int = 16, dt: float = 0.1):
        super().__init__()
        self.horizon, self.dt = horizon, dt
        self.gru = nn.GRU(n_x + N_U, width, batch_first=True)
        self.to_z = nn.Linear(width, k)
        self.f = mlp([k + N_U, width, width, k])
        self.r = mlp([k + n_x, 64, k])
        self.g = nn.Linear(k, N_Y)

    def loss(self, batch):
        x, u, a, y = batch
        hseq, _ = self.gru(torch.cat([x, u], -1))
        z = self.to_z(hseq)
        t_len, hz = z.shape[1], self.horizon
        zz = z[:, : t_len - hz]
        loss = ((self.g(z) - y) ** 2).mean()
        for j in range(hz):
            ut, at = u[:, j: t_len - hz + j], a[:, j: t_len - hz + j]
            zz = zz + self.dt * self.f(torch.cat([zz, ut], -1)) + _active(at) * self.r(torch.cat([zz, at], -1))
            loss = loss + ((self.g(zz) - y[:, j + 1: t_len - hz + j + 1]) ** 2).mean() / hz
            loss = loss + ((zz - z[:, j + 1: t_len - hz + j + 1].detach()) ** 2).mean() / hz
        return loss


class BLinear(nn.Module):
    """E independent linear layers applied to (E, B, in) in one batched matmul."""

    def __init__(self, e: int, n_in: int, n_out: int):
        super().__init__()
        self.w = nn.Parameter(torch.randn(e, n_in, n_out) / math.sqrt(n_in))
        self.b = nn.Parameter(torch.zeros(e, 1, n_out))

    def forward(self, x):
        return torch.baddbmm(self.b, x, self.w)


def bmlp(e: int, sizes: list[int]) -> nn.Sequential:
    layers: list[nn.Module] = []
    for i in range(len(sizes) - 1):
        layers.append(BLinear(e, sizes[i], sizes[i + 1]))
        if i < len(sizes) - 2:
            layers.append(nn.Tanh())
    return nn.Sequential(*layers)


class EnsembleRollout(nn.Module):
    def __init__(self, n_x: int, k: int, members: int = 8, width: int = 64, hist: int = HIST, dt: float = 0.1):
        super().__init__()
        self.e, self.hist, self.dt = members, hist, dt
        self.enc = bmlp(members, [hist * (n_x + N_U), width, width, k])
        self.f = bmlp(members, [k + N_U, width, width, k])
        self.r = bmlp(members, [k + n_x, 32, k])
        self.g = BLinear(members, k, N_Y)
        self.dec = BLinear(members, k, n_x)

    def loss(self, batch):
        x, u, a, y = batch
        b, t_len, _ = x.shape
        e, h = self.e, self.hist
        xe = x.unsqueeze(0).expand(e, -1, -1, -1)
        ue = u.unsqueeze(0).expand(e, -1, -1, -1)
        ae = a.unsqueeze(0).expand(e, -1, -1, -1)
        z = self.enc(torch.cat([xe[:, :, :h], ue[:, :, :h]], -1).reshape(e, b, -1))
        loss = z.new_zeros(())
        for t in range(h, t_len):
            z = z + self.dt * self.f(torch.cat([z, ue[:, :, t]], -1)) + _active(ae[:, :, t]) * self.r(torch.cat([z, ae[:, :, t]], -1))
            loss = loss + ((self.g(z) - y[:, t].unsqueeze(0)) ** 2).mean() + ((self.dec(z) - x[:, t].unsqueeze(0)) ** 2).mean()
        return loss / (t_len - h)


class NeuralODE(nn.Module):
    def __init__(self, n_x: int, k: int, width: int = 128, m: int = 8, hist: int = HIST, dt: float = 0.05):
        super().__init__()
        self.k, self.m, self.hist, self.dt = k, m, hist, dt
        self.enc = mlp([hist * (n_x + N_U), width, width, k])
        self.f = mlp([k + N_U, width, width, k])
        self.G = mlp([k, 64, k * m])
        self.P = nn.Linear(n_x, m, bias=False)
        self.g = nn.Linear(k, N_Y)

    def vf(self, z, u_t, ap):
        return self.f(torch.cat([z, u_t], -1)) + torch.einsum("bkm,bm->bk", self.G(z).view(-1, self.k, self.m), ap)

    def loss(self, batch):
        x, u, a, y = batch
        b, t_len, _ = x.shape
        h, dt = self.hist, self.dt
        z = self.enc(torch.cat([x[:, :h], u[:, :h]], -1).reshape(b, -1))
        loss = z.new_zeros(())
        for t in range(h, t_len):
            ut, ap = u[:, t], self.P(a[:, t])
            k1 = self.vf(z, ut, ap)
            k2 = self.vf(z + 0.5 * dt * k1, ut, ap)
            k3 = self.vf(z + 0.5 * dt * k2, ut, ap)
            k4 = self.vf(z + dt * k3, ut, ap)
            z = z + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
            loss = loss + ((self.g(z) - y[:, t]) ** 2).mean()
        return loss / (t_len - h)


MODELS = {"rollout": RolloutSSM, "gru": GRUFilter, "ens8": EnsembleRollout, "node": NeuralODE}


def make_data(batch: int, t_len: int, n_x: int, seed: int = 0, dtype=torch.float32, device="cpu"):
    """Random data of the benchmark's shapes, generated on the CPU (identical on every device), then moved. Interventions: 1-3
    pulses of 20 steps on random units per trajectory (sparse, as in the benchmark's intervention trajectories)."""
    g = torch.Generator().manual_seed(seed)
    x = 0.5 * torch.randn(batch, t_len, n_x, generator=g, dtype=torch.float64)
    u = 0.5 * torch.randn(batch, t_len, N_U, generator=g, dtype=torch.float64)
    y = 0.5 * torch.randn(batch, t_len, N_Y, generator=g, dtype=torch.float64)
    a = torch.zeros(batch, t_len, n_x, dtype=torch.float64)
    n_p = torch.randint(1, 4, (batch,), generator=g)
    for i in range(batch):
        for _ in range(int(n_p[i])):
            t0 = int(torch.randint(HIST, max(HIST + 1, t_len - 20), (1,), generator=g))
            unit = int(torch.randint(0, n_x, (1,), generator=g))
            a[i, t0: t0 + 20, unit] = float(torch.rand(1, generator=g)) * 2.0 - 1.0
    return tuple(v.to(dtype=dtype, device=device) for v in (x, u, a, y))


def device_info(device: str) -> dict:
    info = {"torch": torch.__version__, "python": platform.python_version(), "threads": torch.get_num_threads(), "cpu_model": _cpu_model(),
            "cpu_count": os.cpu_count()}
    if device == "cuda" and torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        info.update(gpu=torch.cuda.get_device_name(0), gpu_mem_gb=round(p.total_memory / 2**30, 1), cuda=torch.version.cuda,
                    cudnn=torch.backends.cudnn.version(), capability=f"{p.major}.{p.minor}",
                    tf32_matmul=torch.backends.cuda.matmul.allow_tf32, tf32_cudnn=torch.backends.cudnn.allow_tf32)
    return info


def _cpu_model() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


def _sync(device: str) -> None:
    if device == "cuda":
        torch.cuda.synchronize()


def time_workload(kind: str, n_x: int, k: int, t_len: int, batch: int, device: str, warmup: int = 2, min_steps: int = 3,
                  max_steps: int = 20, budget_s: float = 30.0, step_cap_s: float = 90.0, seed: int = 0) -> dict:
    """Seconds per training step (forward + backward + Adam) after `warmup` steps; timed steps continue until `budget_s` or
    `max_steps` (at least `min_steps` unless one step exceeds `step_cap_s`)."""
    torch.manual_seed(seed)
    model = MODELS[kind](n_x, k).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    batch_data = make_data(batch, t_len, n_x, seed=seed, device=device)
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    times: list[float] = []
    t_start = time.perf_counter()
    n = 0
    loss_v = float("nan")
    while True:
        _sync(device)
        t0 = time.perf_counter()
        opt.zero_grad(set_to_none=True)
        loss = model.loss(batch_data)
        loss.backward()
        opt.step()
        _sync(device)
        dt = time.perf_counter() - t0
        loss_v = float(loss.detach())
        n += 1
        if n > warmup:
            times.append(dt)
        if dt > step_cap_s and n >= 1:
            break
        if len(times) >= max_steps or (len(times) >= min_steps and time.perf_counter() - t_start > budget_s):
            break
    times_sorted = sorted(times) if times else [dt]
    step_s = times_sorted[len(times_sorted) // 2]
    out = {"kind": kind, "n_x": n_x, "k": k, "t_len": t_len, "batch": batch, "device": device, "step_s_median": step_s,
           "step_s_mean": sum(times) / len(times) if times else dt, "n_timed": len(times), "warmup": warmup,
           "epoch_s": step_s * EPOCH_TRAJ / batch, "traj_per_s": batch / step_s, "loss_finite": math.isfinite(loss_v),
           "n_params": sum(p.numel() for p in model.parameters())}
    if device == "cuda":
        out["peak_mem_gb"] = round(torch.cuda.max_memory_allocated() / 2**30, 3)
    return out


CONFIGS = [(n_x, k, t_len, b) for (n_x, k) in ((20, 4), (200, 16)) for t_len in (500, 2000) for b in (64, 256)]


def run_suite(kinds: list[str], device: str, threads: int | None = None, configs=None, **kw) -> dict:
    """Every (kind, config) on one device; errors are recorded per case, never fatal."""
    if threads:
        torch.set_num_threads(int(threads))
    rows = []
    t0 = time.time()
    for kind in kinds:
        for (n_x, k, t_len, b) in (configs or CONFIGS):
            try:
                rows.append(time_workload(kind, n_x, k, t_len, b, device, **kw))
            except Exception as e:  # noqa: BLE001
                rows.append({"kind": kind, "n_x": n_x, "k": k, "t_len": t_len, "batch": b, "device": device, "error": repr(e)[:500]})
            if device == "cuda":
                torch.cuda.empty_cache()
    return {"info": device_info(device), "rows": rows, "wall_s": round(time.time() - t0, 1)}
