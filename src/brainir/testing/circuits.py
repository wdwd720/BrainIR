"""Small synthetic circuits with analytically or numerically established behaviour under a firing-rate model.

The model (Pugliese et al. style) has a non-negative rate ``r_i`` (Hz) per neuron::

    tau_i dr_i/dt = max( r_max_i * tanh( (a_i / r_max_i) * ( I_i(t) + b * sum_j W[i, j] r_j - theta_i ) ), 0 ) - r_i

with ``W`` a real ``post x pre`` matrix (``W[i, j]`` = signed synapse count from presynaptic ``j`` onto
postsynaptic ``i``; excitatory columns positive, inhibitory columns negative, one sign per column),
``b = 0.03`` and the paper's default parameter means ``tau = 0.020 s``, ``a = 1``, ``theta = 7.5``,
``r_max = 200 Hz`` (:data:`DEFAULT_PARAMS`). ``I_i(t)`` is a constant current on ``stim_neurons`` from
``stim_onset_s`` (0.02 s) to the end; ``r(0) = 0``.

:func:`reference_simulate` is the reference integrator (scipy RK45, rtol 2e-6, atol 5e-9, sampled on a
1 ms grid). Its oscillation frequencies change by < 0.01 Hz when the tolerances are tightened to 1e-10, so
the ``expected`` numbers are converged solutions of the ODE, not integrator artefacts. BrainIR's own simulator
is implemented elsewhere and must reproduce ``expected``.

These are synthetic *model* fixtures, not anatomy. They contain no connectome identifiers.

``expected`` keys (used consistently across circuits)::

    behavior            one of BEHAVIORS
    is_rhythmic         bool: sustained oscillation on readout_neurons within analysis_window_s
    frequency_hz        float | None (dominant frequency of the sustained oscillation)
    frequency_tol_hz    float | None (5 % of frequency_hz for deterministic oscillators)
    readout_neurons     tuple[int, ...]: which rates to analyse
    analysis_window_s   (t0, t1): window (after transients) on which the claims hold
    steady_state_hz     tuple of steady rates for readout_neurons (fixed-point behaviours only)

plus circuit-specific keys documented in each builder (amplitude_hz, transient_frequency_hz, winner, ...).

Findings about the model that shaped these circuits (all verified with :func:`reference_simulate`):

* Single-neuron / feedforward / winner-take-all steady states are closed forms of the rectified tanh
  (:func:`rate_function`), because the input to each neuron is then known.
* A *symmetric* ring of three mutually inhibiting neurons under equal drive never oscillates from
  ``r(0) = 0``: its symmetric fixed point is unstable for ``b*w > 2`` (repressilator-like Hopf at
  ``b*w = 2``, ``f = sqrt(3)/(2 pi tau) = 13.8 Hz``), but with identical inputs the trajectory stays exactly
  on the symmetric invariant manifold. Unequal driver weights (40/36/32) break the symmetry and the ring
  settles on a rotating-wave limit cycle (``sustained_oscillator``). Noise would do the same in practice.
  The same pitfall makes the symmetric ``bistable_pair`` sit on its saddle when neither member is favoured.
* A 2-neuron E-I pair with equal time constants oscillates sustainably only with strong E self-excitation
  (``b*w_EE > 2`` at the fixed point); the tanh saturation then bounds the cycle (``ei_pair_oscillator``).
  With weaker self-excitation the same motif only rings (``damped_oscillator``, eigenvalues
  ``-13.5 +/- 128.4i`` per second at the fixed point, i.e. 20.4 Hz decaying with a 74 ms time constant).
* Delays are realised as chains of first-order stages: an excitatory relay chain closed by one inhibitory
  neuron gives a negative feedback loop that oscillates when the loop gain exceeds ``sec(pi/n)^n``
  (``delayed_inhibitory_oscillator``: n = 5 stages, 5.7 Hz relaxation cycle with a 176 ms period).
* A seeded random sparse signed network with mostly excitatory columns converges to a fixed point for every
  seed tried; ``random_recurrent`` therefore documents its fixed point as a regression fingerprint.
* Integrator accuracy matters at these frequencies: forward Euler with dt = 1 ms reproduces the two fast
  oscillators with frequencies 6 % too low (ring 12.86 Hz, E-I pair 10.94 Hz) and amplitudes 12 % too high
  (the 5.7 Hz loop is only 1 % low), which the 5 % tolerances reject on purpose; Euler with dt <= 0.25 ms or
  any adaptive method passes.
* The rectification kink at zero lets RK45 undershoot 0 Hz by up to ~1e-3 Hz on the output grid; tests
  should allow that tolerance rather than clip.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "BEHAVIORS",
    "CIRCUITS",
    "DEFAULT_PARAMS",
    "MODEL_PARAM_KEYS",
    "RANDOM_RECURRENT_SEED",
    "STIM_ONSET_S",
    "SyntheticCircuit",
    "get_circuit",
    "rate_function",
    "reference_simulate",
]

DEFAULT_PARAMS: dict[str, float] = {"tau": 0.020, "a": 1.0, "theta": 7.5, "r_max": 200.0, "b": 0.03}
MODEL_PARAM_KEYS: tuple[str, ...] = ("tau", "a", "theta", "r_max", "b")
STIM_ONSET_S = 0.02
BEHAVIORS: tuple[str, ...] = ("fixed_point", "propagation", "saturation", "winner_take_all", "damped_oscillation",
                              "sustained_oscillation", "bounded_chaos_or_fixed_point")
RANDOM_RECURRENT_SEED = 0


def rate_function(u, a=DEFAULT_PARAMS["a"], r_max=DEFAULT_PARAMS["r_max"]):
    """Rectified saturating gain: ``max(r_max * tanh(a * u / r_max), 0)``. ``u`` is the net input (current units)."""
    return np.maximum(r_max * np.tanh(a * np.asarray(u, dtype=np.float64) / r_max), 0.0)


@dataclass(frozen=True)
class SyntheticCircuit:
    name: str
    W: np.ndarray  # post x pre, float64, read-only
    stim_neurons: tuple[int, ...]  # indices receiving the input current
    stim_current: float
    t_end: float  # seconds to simulate
    params: dict = field(default_factory=dict)  # per-circuit overrides of DEFAULT_PARAMS (float or per-neuron array) + documentation keys
    expected: dict = field(default_factory=dict)
    description: str = ""
    stim_onset_s: float = STIM_ONSET_S

    @property
    def n(self) -> int:
        return int(self.W.shape[0])

    def model_params(self) -> dict:
        """Defaults merged with ``params``; ``tau``/``a``/``theta``/``r_max`` broadcast to shape ``(n,)``, ``b`` a float."""
        out = {}
        for k in ("tau", "a", "theta", "r_max"):
            v = self.params.get(k, DEFAULT_PARAMS[k])
            out[k] = np.broadcast_to(np.asarray(v, dtype=np.float64), (self.n,)).copy()
        out["b"] = float(self.params.get("b", DEFAULT_PARAMS["b"]))
        return out

    def input_current(self, t: float) -> np.ndarray:
        """External current vector at time ``t`` (constant pulse on ``stim_neurons`` from ``stim_onset_s`` onwards)."""
        i = np.zeros(self.n)
        if t >= self.stim_onset_s:
            i[list(self.stim_neurons)] = self.stim_current
        return i


def reference_simulate(circuit: SyntheticCircuit, *, dt_out: float = 1e-3, rtol: float = 2e-6, atol: float = 5e-9) -> tuple[np.ndarray, np.ndarray]:
    """Reference integration: scipy RK45 with the stimulus step at a segment boundary, sampled on a ``dt_out`` grid.

    Returns ``(t, r)`` with ``r`` shaped ``[len(t), N]``; ``t`` runs from 0 to ``t_end`` inclusive.
    """
    from scipy.integrate import solve_ivp  # local import keeps the fixture module light

    p = circuit.model_params()
    tau, a, theta, r_max, b = p["tau"], p["a"], p["theta"], p["r_max"], p["b"]
    W = np.asarray(circuit.W, dtype=np.float64)
    n = circuit.n
    n_steps = int(round(circuit.t_end / dt_out))
    grid = np.arange(n_steps + 1, dtype=np.float64) * dt_out
    r_out = np.zeros((len(grid), n))
    t_on = float(circuit.stim_onset_s)

    def make_rhs(i_ext):
        def rhs(_t, r):
            return (rate_function(i_ext + b * (W @ r) - theta, a, r_max) - r) / tau
        return rhs

    state = np.zeros(n)
    segments = []
    if t_on > 0.0:
        segments.append((0.0, min(t_on, circuit.t_end), np.zeros(n)))
    if circuit.t_end > t_on:
        i_on = np.zeros(n)
        i_on[list(circuit.stim_neurons)] = circuit.stim_current
        segments.append((t_on, circuit.t_end, i_on))
    for t0, t1, i_ext in segments:
        mask = (grid >= t0 - 1e-12) & (grid <= t1 + 1e-12)
        t_eval = np.unique(np.concatenate([np.clip(grid[mask], t0, t1), [t0, t1]]))
        sol = solve_ivp(make_rhs(i_ext), (t0, t1), state, method="RK45", rtol=rtol, atol=atol, t_eval=t_eval)
        if not sol.success:
            raise RuntimeError(f"reference_simulate({circuit.name}) failed: {sol.message}")
        idx = np.searchsorted(sol.t, np.clip(grid[mask], t0, t1))
        r_out[mask] = sol.y[:, idx].T
        state = sol.y[:, -1]
    return grid, r_out


# --------------------------------------------------------------------------------------------------
# helpers for closed forms
# --------------------------------------------------------------------------------------------------

_B = DEFAULT_PARAMS["b"]
_THETA = DEFAULT_PARAMS["theta"]


def _f(u: float) -> float:
    return float(rate_function(u))


def _frozen(W) -> np.ndarray:
    W = np.array(W, dtype=np.float64)
    if W.ndim != 2 or W.shape[0] != W.shape[1]:
        raise ValueError("W must be square")
    for j in range(W.shape[1]):
        col = W[:, j]
        if (col > 0).any() and (col < 0).any():
            raise ValueError(f"presynaptic column {j} mixes signs")
    W.setflags(write=False)
    return W


def _picard_fixed_point(W: np.ndarray, i_ext: np.ndarray, iters: int = 2000) -> np.ndarray:
    """Fixed point by iterating r <- f(I + b W r - theta) from 0 (only used where this iteration converges)."""
    r = np.zeros(W.shape[0])
    for _ in range(iters):
        r_new = rate_function(i_ext + _B * (W @ r) - _THETA)
        if np.max(np.abs(r_new - r)) < 1e-12:
            return r_new
        r = r_new
    raise RuntimeError("Picard iteration did not converge")


def _bisect_decreasing(g, lo: float, hi: float, iters: int = 200) -> float:
    """Root of a decreasing function ``g`` on ``[lo, hi]`` with ``g(lo) > 0 > g(hi)``."""
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if g(mid) > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------------------------------
# circuits
# --------------------------------------------------------------------------------------------------

def _fixed_point_single() -> SyntheticCircuit:
    i_ext = 250.0
    ss = _f(i_ext - _THETA)  # 200 tanh(242.5 / 200) = 167.486 Hz
    return SyntheticCircuit(
        name="fixed_point_single", W=_frozen([[0.0]]), stim_neurons=(0,), stim_current=i_ext, t_end=0.3,
        expected={
            "behavior": "fixed_point", "is_rhythmic": False, "frequency_hz": None, "frequency_tol_hz": None,
            "readout_neurons": (0,), "analysis_window_s": (0.2, 0.3), "steady_state_hz": (ss,),
            # r(t) = ss * (1 - exp(-(t - t_on) / tau)) exactly, so r(t_on + tau) = ss * (1 - 1/e)
            "time_constant_s": DEFAULT_PARAMS["tau"], "rate_at_one_tau_hz": ss * (1.0 - np.exp(-1.0)),
        },
        description="One driven neuron, no recurrence: exponential approach (tau = 20 ms) to the closed-form steady state "
                    "r* = r_max tanh((I - theta) / r_max).",
    )


def _feedforward_chain() -> SyntheticCircuit:
    n, w, i_ext = 5, 50.0, 250.0
    W = np.zeros((n, n))
    for k in range(1, n):
        W[k, k - 1] = w
    ss = [_f(i_ext - _THETA)]
    for _ in range(1, n):
        ss.append(_f(_B * w * ss[-1] - _THETA))  # per-stage gain b*w = 1.5 keeps every stage active
    return SyntheticCircuit(
        name="feedforward_chain", W=_frozen(W), stim_neurons=(0,), stim_current=i_ext, t_end=0.4,
        expected={
            "behavior": "propagation", "is_rhythmic": False, "frequency_hz": None, "frequency_tol_hz": None,
            "readout_neurons": tuple(range(n)), "analysis_window_s": (0.3, 0.4), "steady_state_hz": tuple(ss),
            "onset_order": tuple(range(n)),  # strictly increasing onset times along the chain
            "onset_threshold_hz": 1.0, "monotone_rise": True,
            # onset times (first 1 ms sample > 1 Hz) measured with reference_simulate
            "onset_times_s": (0.021, 0.023, 0.029, 0.037, 0.046),
        },
        description="Five-neuron excitatory chain 0 -> 1 -> 2 -> 3 -> 4 (w = 50, per-stage gain 1.5). Activity propagates with one "
                    "first-order lag per stage: monotone rises, strictly ordered onsets, closed-form steady states.",
    )


def _recurrent_excitation_saturating() -> SyntheticCircuit:
    W = np.array([[0.0, 100.0], [100.0, 0.0]])
    i_ext = np.array([250.0, 0.0])
    ss = _picard_fixed_point(W, i_ext)  # (199.909, 198.931): both within 0.6 % of r_max
    return SyntheticCircuit(
        name="recurrent_excitation_saturating", W=_frozen(W), stim_neurons=(0,), stim_current=250.0, t_end=0.3,
        expected={
            "behavior": "saturation", "is_rhythmic": False, "frequency_hz": None, "frequency_tol_hz": None,
            "readout_neurons": (0, 1), "analysis_window_s": (0.2, 0.3), "steady_state_hz": tuple(float(v) for v in ss),
            "saturation_fraction_min": 0.99,  # every readout rate >= 0.99 r_max at steady state
        },
        description="Mutual excitation (w = 100, loop gain 9) drives both neurons to within 1 % of r_max; the tanh saturation, "
                    "not the drive, sets the level.",
    )


def _bistable_pair() -> SyntheticCircuit:
    w_drive, w_inh, i_ext = 40.0, 60.0, 100.0
    W = np.zeros((3, 3))
    W[1, 0] = W[2, 0] = w_drive  # common drive from the relay neuron 0
    W[1, 2] = W[2, 1] = -w_inh  # mutual inhibition (b*w = 1.8 > 1: winner-take-all is bistable)
    driver = _f(i_ext - _THETA)  # 86.424 Hz
    common = _B * w_drive * driver - _THETA  # 96.2 units of net drive to each pair member
    winner = _f(i_ext + common)  # 150.703 Hz: the member that also receives the stimulus
    alone = _f(common)  # 89.4 Hz: a winner that gets no direct stimulus (mirror/symmetric variants)
    saddle = _bisect_decreasing(lambda r: _f(common - _B * w_inh * r) - r, 0.0, alone)  # 34.24 Hz
    return SyntheticCircuit(
        name="bistable_pair", W=_frozen(W), stim_neurons=(0, 1), stim_current=i_ext, t_end=0.4,
        expected={
            "behavior": "winner_take_all", "is_rhythmic": False, "frequency_hz": None, "frequency_tol_hz": None,
            "readout_neurons": (1, 2), "analysis_window_s": (0.3, 0.4), "steady_state_hz": (winner, 0.0),
            "winner": 1, "loser": 2, "loser_max_hz": 1.0, "driver_steady_state_hz": driver,
            # stimulating (0, 2) instead makes neuron 2 win with the same rates (the pair is symmetric)
            "mirror_stim_neurons": (0, 2),
            # with the stimulus on the relay only, both members get identical input and the deterministic trajectory
            # stays on the unstable symmetric saddle r = f(common - b*w*r) instead of picking a winner
            "symmetric_stim_neurons": (0,), "symmetric_saddle_hz": saddle,
            "pair_alone_steady_state_hz": alone,
        },
        description="Relay neuron 0 (stimulated) drives neurons 1 and 2 equally; 1 and 2 inhibit each other with b*w = 1.8, so both "
                    "single-winner states are stable. Neuron 1 also receives the stimulus and wins; the loser is silenced (0 Hz) "
                    "despite 96 units of net drive. Stimulating (0, 2) mirrors the outcome.",
    )


def _damped_oscillator() -> SyntheticCircuit:
    W = np.array([[50.0, -100.0], [100.0, 0.0]])  # E self-excitation 50, E -> I 100, I -> E -100
    return SyntheticCircuit(
        name="damped_oscillator", W=_frozen(W), stim_neurons=(0,), stim_current=250.0, t_end=0.8,
        expected={
            "behavior": "damped_oscillation", "is_rhythmic": False, "frequency_hz": None, "frequency_tol_hz": None,
            "readout_neurons": (0, 1), "analysis_window_s": (0.4, 0.8),
            "steady_state_hz": (33.273, 86.276),  # fsolve on the fixed-point equations, confirmed by the reference run
            "transient_frequency_hz": 20.43,  # imag(eigenvalue) / 2 pi at the fixed point; peak spacing 49 ms
            "transient_frequency_tol_hz": 1.0,
            "decay_rate_per_s": 13.5,  # -real(eigenvalue)
            "first_peak_hz": 95.0, "first_peak_time_s": 0.041,  # E overshoot right after onset
            "overshoot_ratio_min": 2.0,  # first E peak / E steady state (= 2.85)
            "late_amplitude_max_hz": 1.0,  # peak-to-trough of any readout rate inside analysis_window_s (measured 0.41)
        },
        description="E-I pair with moderate E self-excitation (b*w_EE = 1.5 < 2): the step response overshoots to 95 Hz and rings at "
                    "20.4 Hz with a 74 ms decay time, then settles to (33.3, 86.3) Hz. Not a sustained rhythm.",
    )


def _ring_W() -> np.ndarray:
    W = np.zeros((4, 4))
    W[1, 0], W[2, 0], W[3, 0] = 40.0, 36.0, 32.0  # unequal excitatory drive breaks the ring symmetry
    W[2, 1] = W[3, 2] = W[1, 3] = -100.0  # 1 -| 2 -| 3 -| 1 (b*w = 3 > 2: symmetric state unstable)
    return W


_RING_EXPECTED = {
    "behavior": "sustained_oscillation", "is_rhythmic": True, "frequency_hz": 13.73, "frequency_tol_hz": 0.7,
    "readout_neurons": (1, 2, 3), "analysis_window_s": (0.5, 2.0),
    "amplitude_hz": (64.9, 56.8, 59.6),  # peak-to-trough per readout neuron on the analysis window
    "amplitude_tol_fraction": 0.2, "mean_rate_hz": (52.5, 36.7, 48.4), "mean_rate_tol_fraction": 0.1,
    "period_s": 0.0728, "driver_steady_state_hz": 167.486,
    "peak_order": (1, 3, 2),  # rotating wave: after neuron 1 peaks, 3 peaks next, then 2
    "euler_1ms_frequency_hz": 12.86,  # what forward Euler with dt = 1 ms gives (biased low, outside tolerance)
}


def _sustained_oscillator() -> SyntheticCircuit:
    return SyntheticCircuit(
        name="sustained_oscillator", W=_frozen(_ring_W()), stim_neurons=(0,), stim_current=250.0, t_end=2.0,
        expected=dict(_RING_EXPECTED),
        description="Stimulated excitatory driver 0 -> inhibitory ring 1 -| 2 -| 3 -| 1 (w = -100, driver weights 40/36/32). "
                    "Repressilator-like negative cyclic feedback with delays realised as first-order stages: a rotating-wave "
                    "limit cycle at 13.7 Hz (period 72.8 ms) with peak-to-trough amplitudes of 57-65 Hz.",
    )


def _noisy_oscillator() -> SyntheticCircuit:
    exp = dict(_RING_EXPECTED)
    exp.update({"frequency_tol_hz": 1.5, "amplitude_tol_fraction": 0.35, "mean_rate_tol_fraction": 0.15})
    return SyntheticCircuit(
        name="noisy_oscillator", W=_frozen(_ring_W()), stim_neurons=(0,), stim_current=250.0, t_end=2.0,
        params={
            # Documentation for stochastic runs (the reference simulation ignores it and stays deterministic): add
            # independent Gaussian white current noise to every neuron's I_i, drawn once per 1 ms step and held over the
            # step, with this standard deviation in the units of stim_current. For another step size dt scale the
            # per-step standard deviation by sqrt(0.001 / dt) to keep the same noise power. At this level the ring keeps
            # its 13.7 Hz rhythm (frequency shift < 0.1 Hz, peak-to-trough amplitude up by ~15 %).
            "noise_std": 20.0,
            "noise_model": "gaussian_white_current_per_1ms_step",
        },
        expected=exp,
        description="The sustained_oscillator ring with a documented input-noise level (params['noise_std']) for stochastic "
                    "simulations; the reference run is deterministic and identical to sustained_oscillator.",
    )


def _delayed_inhibitory_oscillator() -> SyntheticCircuit:
    n, w_fwd, w_inh = 5, 50.0, 100.0
    W = np.zeros((n, n))
    for k in range(1, n):
        W[k, k - 1] = w_fwd  # 0 -> 1 -> 2 -> 3 -> 4 (excitatory relays)
    W[0, n - 1] = -w_inh  # 4 -| 0 (delayed feedback inhibition)
    return SyntheticCircuit(
        name="delayed_inhibitory_oscillator", W=_frozen(W), stim_neurons=(0,), stim_current=250.0, t_end=2.0,
        expected={
            "behavior": "sustained_oscillation", "is_rhythmic": True, "frequency_hz": 5.68, "frequency_tol_hz": 0.3,
            "readout_neurons": (0, 4), "analysis_window_s": (0.5, 2.0),
            "amplitude_hz": (114.9, 111.7), "amplitude_tol_fraction": 0.2, "mean_rate_hz": (40.6, 84.1), "mean_rate_tol_fraction": 0.1,
            "period_s": 0.176, "euler_1ms_frequency_hz": 5.62,
        },
        description="Stimulated excitatory neuron 0 excites a 3-neuron relay chain whose last member (4, inhibitory) feeds back "
                    "onto 0: a 5-stage negative feedback loop (gain 1.5^4 * 3 = 15 > sec(pi/5)^5 = 2.9). Relaxation-type "
                    "limit cycle at 5.68 Hz (period 176 ms); neuron 0 is silenced to ~0.6 Hz in every cycle.",
    )


def _ei_pair_oscillator() -> SyntheticCircuit:
    W = np.array([[100.0, -100.0], [100.0, 0.0]])  # strong E self-excitation (b*w_EE = 3 > 2) + E-I loop
    return SyntheticCircuit(
        name="ei_pair_oscillator", W=_frozen(W), stim_neurons=(0,), stim_current=250.0, t_end=2.0,
        expected={
            "behavior": "sustained_oscillation", "is_rhythmic": True, "frequency_hz": 11.68, "frequency_tol_hz": 0.6,
            "readout_neurons": (0, 1), "analysis_window_s": (0.5, 2.0),
            "amplitude_hz": (84.5, 80.5), "amplitude_tol_fraction": 0.2, "mean_rate_hz": (58.4, 122.8), "mean_rate_tol_fraction": 0.1,
            "period_s": 0.0856, "euler_1ms_frequency_hz": 10.94,
        },
        description="Two neurons only: E with self-excitation 100 drives I (100) which inhibits E (-100). The fixed point is an "
                    "unstable focus (b*w_EE = 3 > 2 at the linear gain) and the tanh saturation bounds the orbit: a "
                    "Wilson-Cowan-type limit cycle at 11.7 Hz with equal time constants.",
    )


def _random_recurrent() -> SyntheticCircuit:
    n, density, p_exc = 30, 0.2, 0.6
    rng = np.random.default_rng(RANDOM_RECURRENT_SEED)
    sign = np.where(rng.random(n) < p_exc, 1.0, -1.0)  # one sign per presynaptic column (13 of 30 excitatory for seed 0)
    mask = rng.random((n, n)) < density
    np.fill_diagonal(mask, False)
    counts = rng.integers(1, 30, size=(n, n))
    W = mask * counts * sign[None, :]
    # fixed point reached by the reference run (regression fingerprint, 0.01 Hz resolution); 14 neurons stay active
    fixed_point = (173.69, 185.74, 171.81, 31.84, 0.0, 82.08, 0.0, 0.0, 94.31, 0.0, 103.23, 0.0, 0.0, 68.15, 28.88,
                   0.0, 36.82, 0.0, 0.0, 0.0, 0.0, 55.45, 0.0, 0.0, 0.0, 9.21, 0.0, 0.0, 18.35, 25.63)
    return SyntheticCircuit(
        name="random_recurrent", W=_frozen(W), stim_neurons=(0, 1, 2), stim_current=250.0, t_end=1.5,
        expected={
            "behavior": "bounded_chaos_or_fixed_point", "is_rhythmic": False, "frequency_hz": None, "frequency_tol_hz": None,
            "readout_neurons": tuple(range(n)), "analysis_window_s": (1.0, 1.5),
            "seed": RANDOM_RECURRENT_SEED, "n_excitatory_columns": int((sign > 0).sum()), "n_edges": int(mask.sum()),
            "steady_state_hz": fixed_point, "n_active_neurons": sum(1 for v in fixed_point if v > 1.0),
            "late_amplitude_max_hz": 0.5,
        },
        description="Seeded random sparse signed network (N = 30, density 0.2, each column excitatory with probability 0.6, integer "
                    "counts 1-29), three neurons stimulated. Rates stay bounded in [0, r_max] and converge to a fixed point.",
    )


def _build() -> dict[str, SyntheticCircuit]:
    circuits = [
        _fixed_point_single(), _feedforward_chain(), _recurrent_excitation_saturating(), _bistable_pair(), _damped_oscillator(),
        _sustained_oscillator(), _delayed_inhibitory_oscillator(), _ei_pair_oscillator(), _noisy_oscillator(), _random_recurrent(),
    ]
    out = {}
    for c in circuits:
        if c.expected["behavior"] not in BEHAVIORS:
            raise ValueError(f"{c.name}: unknown behavior {c.expected['behavior']!r}")
        out[c.name] = c
    return out


CIRCUITS: dict[str, SyntheticCircuit] = _build()


def get_circuit(name: str) -> SyntheticCircuit:
    try:
        return CIRCUITS[name]
    except KeyError:
        raise KeyError(f"unknown circuit {name!r}; choose from {tuple(CIRCUITS)}") from None
