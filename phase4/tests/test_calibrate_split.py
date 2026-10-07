"""The SPLIT calibration (research/phase4/LEVEL_B_EXECUTION.md; P1) is bit-identical to the unsplit path. `split_from_inputs` fits the
models, PICKLES them across the fit-job -> eval-job boundary, recomputes the supported item set from the reloaded model, and evaluates;
its row must equal `calibrate_from_inputs`'s in every field except the wall-clock / CPU timings (the reference models' train_cost
cpu_s / wall_s and the row's seconds differ between ANY two runs, even two direct runs of the same inputs).

Each path gets FRESHLY built inputs, as in production (every calibration job loads its system's inputs itself), so the comparison is
not affected by anything one run may leave on shared input objects."""

from __future__ import annotations

import json

import pytest

from brainir_causal import calibrate as CAL

FAST = {"steps_one": 300, "steps_multi": 60, "readout_steps": 300}
TIMING = {"cpu_s", "wall_s", "seconds", "tracebacks"}


def _strip_timing(o):
    if isinstance(o, dict):
        return {k: _strip_timing(v) for k, v in o.items() if k not in TIMING}
    if isinstance(o, list):
        return [_strip_timing(v) for v in o]
    return o


def _kw(inp):
    return dict(pub=inp["pub"], sysc=inp["sysc"], train=inp["train"], items=inp["items"], pool=inp["pool"], k_true=2, truth=inp["truth"],
                register=list(inp["register"]), n_boot=64, seed=0, learner=FAST)


@pytest.mark.slow
def test_split_calibration_is_bit_identical_with_the_default_learner():
    """The OFFICIAL calibration configuration (the default LearnerConfig), one toy system: split == direct outside the timings. Also a
    second DIRECT run, so a difference is classified: direct != direct is nondeterminism of the calibration itself, not of the split."""
    from test_calibrate_toyinputs import toy_inputs
    kw = lambda inp: dict(_kw(inp), learner=None)                          # noqa: E731
    direct = json.loads(json.dumps(CAL.calibrate_from_inputs("toy", **kw(toy_inputs(seed=0))), default=str))
    direct2 = json.loads(json.dumps(CAL.calibrate_from_inputs("toy", **kw(toy_inputs(seed=0))), default=str))
    split = json.loads(json.dumps(CAL.split_from_inputs("toy", **kw(toy_inputs(seed=0))), default=str))
    assert _strip_timing(direct) == _strip_timing(direct2), "two DIRECT runs differ: the calibration itself is not deterministic"
    assert _strip_timing(direct) == _strip_timing(split), "split != direct outside the timing fields (default learner)"


def test_split_calibration_is_bit_identical_on_toy_systems():
    from test_calibrate_toyinputs import toy_inputs
    for seed in (0, 1):                                  # two systems (the directive's 2-system check, on the toy fixture)
        direct = json.loads(json.dumps(CAL.calibrate_from_inputs("toy", **_kw(toy_inputs(seed=seed))), default=str))
        split = json.loads(json.dumps(CAL.split_from_inputs("toy", **_kw(toy_inputs(seed=seed))), default=str))
        assert not direct["errors"] and not split["errors"], (direct["errors"], split["errors"])
        assert _strip_timing(direct) == _strip_timing(split), f"seed {seed}: split != direct outside the timing fields"


def test_calibration_refuses_a_z_only_true_state_when_the_truth_has_draws():
    """E13 (2026-09-27): the row records TRUE-STATE's draw_context; a system whose truth provides the effective draw parameters is
    REFUSED when the fitted TRUE-STATE does not encode them (a silent z-only fallback would weaken the calibration)."""
    from brainir_causal import calibrate as CAL

    class _TS:
        def __init__(self, dctx):
            self.dctx = dctx

        def info(self):
            return {"draw_context": self.dctx}

    def build(dctx, draw):
        prefit = {"models": {"true_state": _TS(dctx)}, "errors": {}, "missing_coordinate": None}
        return CAL._calib_build("syn-x", pub={}, sysc=None, train=[], items=[], pool=None, k_true=2,
                                truth={"z": None, "z_obs": None, "draw": draw}, corruptions=False, prefit=prefit, whiten_hists=[])
    assert build(True, {"k": [1.0]})["row"]["true_state_draw_context"] is True
    assert build(False, None)["row"]["true_state_draw_context"] is False        # no draws in the truth: recorded, allowed
    with pytest.raises(ValueError, match="draw_context"):
        build(False, {"k": [1.0]})
