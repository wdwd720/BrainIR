import pytest

from brainir_causal import families as F
from brainir_causal.systems import REAL_CAPABILITY

SYS = {"capability": REAL_CAPABILITY}            # kick max 50, current max 60, pulse <= 0.15 s, sustained >= 0.3 s
NOMINAL_SEED_SYS = {"capability": {**REAL_CAPABILITY, "params": {"public_seed_max": 10**9, "nominal_seed": 0}}}


def proto(events=(), **kw):
    p = {"system": "s", "params_seed": 3, "t_end": 2.0, "dt": 0.001, "stimulus": [[0.0, 0.0], [0.05, 1.0]], "events": list(events)}
    p.update(kw)
    return p


def fam(events=(), sysrec=SYS, **kw):
    return F.family_of(proto(events, **kw), sysrec)


def K(t, **d):
    return {"kind": "kick", "t": t, "delta": {str(k[1:]): v for k, v in d.items()}}


def C(t0, t1, **d):
    return {"kind": "current", "t0": t0, "t1": t1, "targets": {str(k[1:]): v for k, v in d.items()}}


def test_observational_families_and_precedence():
    assert fam() == "obs.nominal"
    assert fam(stimulus=[[0.0, 1.0]]) == "obs.nominal"
    assert fam(stimulus=[[0.0, 0.0], [0.5, 1.0]]) == "obs.stim"            # onset later than max_onset
    assert fam(stimulus=[[0.0, 0.0], [0.05, 1.2]]) == "obs.stim"
    assert fam(stimulus=[[0.0, 0.0], [0.05, 1.0], [1.5, 0.0]]) == "obs.stim"
    assert fam(r0={"kind": "state", "values": {"1": 3.0}}) == "obs.init"
    assert fam(r0={"kind": "state", "values": {"1": 3.0}}, stimulus=[[0.0, 1.3]]) == "obs.init"
    assert fam(weight_noise={"sd": 0.05, "seed": 1}, r0={"kind": "state", "values": {"1": 3.0}}) == "obs.wnoise"
    # parameter draws are a family only when the record names a nominal draw
    assert fam(params_seed=7) == "obs.nominal"
    assert fam(params_seed=7, sysrec=NOMINAL_SEED_SYS) == "obs.param"
    assert fam(params_seed=0, sysrec=NOMINAL_SEED_SYS) == "obs.nominal"
    assert fam(obs_noise={"sd": 0.1, "seed": 2}) == "obs.nominal"          # observation noise does not change the family
    # a counterfactual twin keeps the intervened run's breakpoints as no-op stimulus steps: still nominal
    from brainir_causal import protocol as P
    tw = P.counterfactual(proto([K(0.5, u1=10.0), C(1.0, 1.05, u2=5.0)]))
    assert len(tw["stimulus"]) > 2 and F.family_of(tw, SYS) == "obs.nominal"


def test_kicks():
    assert fam([K(0.5, u1=10.0)]) == "kick.1"
    assert fam([K(0.5, u1=-50.0)]) == "kick.1"
    assert fam([K(0.5, u1=80.0)]) == "kick.hi"
    assert fam([K(0.5, u1=10.0, u2=5.0)]) == "kick.2"
    assert fam([K(0.5, u1=10.0, u2=5.0, u3=1.0)]) == "kick.g"
    # two simultaneous single kicks are one paired kick; repeated independent kicks keep the single family
    assert fam([K(0.5, u1=10.0), K(0.5, u2=5.0)]) == "kick.2"
    assert fam([K(0.5, u1=10.0), K(1.0, u2=5.0), K(1.5, u1=-3.0)]) == "kick.1"
    assert fam([K(0.5, u1=10.0), K(1.0, u2=5.0, u3=2.0)]) == "comp.seq"


def test_currents_pulses_and_sustained():
    assert fam([C(0.5, 0.6, u1=30.0)]) == "pulse.1"
    assert fam([C(0.5, 0.65, u1=-30.0)]) == "pulse.1"                     # exactly the pulse maximum
    assert fam([C(0.5, 0.6, u1=61.0)]) == "pulse.hi"
    assert fam([C(0.5, 0.6, u1=3.0, u2=4.0)]) == "pulse.2"
    assert fam([C(0.5, 0.6, u1=3.0, u2=4.0, u3=1.0)]) == "pulse.g"
    assert fam([C(0.5, 0.9, u1=20.0)]) == "act.1"
    assert fam([C(0.5, None, u1=-20.0)]) == "inh.1"
    assert fam([C(0.5, 0.7, u1=20.0)]) == "other"                         # between 0.15 and 0.3 s: unclassified
    assert fam([C(0.5, 0.9, u1=20.0, u2=1.0)]) == "other"                 # multi-target sustained: not a vocabulary family
    assert fam([C(0.5, 0.9, u1=0.0)]) == "other"


def test_pulse_patterns():
    assert fam([C(0.5, 0.55, u1=10.0), C(0.8, 0.85, u2=12.0)]) == "seq.pp"
    train = [C(0.2 + 0.2 * i, 0.25 + 0.2 * i, u1=10.0) for i in range(4)]
    assert fam(train) == "seq.train"
    irregular = [C(0.2, 0.25, u1=10.0), C(0.35, 0.40, u1=10.0), C(0.8, 0.85, u1=10.0)]
    assert fam(irregular) == "seq.prbs"
    mixed = [C(0.2, 0.25, u1=10.0), C(0.5, 0.55, u2=10.0), C(0.8, 0.85, u1=20.0)]
    assert fam(mixed) == "comp.seq"
    assert fam([C(0.2, 0.3, u1=10.0), C(0.25, 0.35, u2=10.0)]) == "comp.sim"


def test_current_sequences():
    def S(vals, seg=0.01, t0=0.2):
        return {"kind": "current_seq", "t0": t0, "seg": seg, "targets": {"1": vals}}
    assert fam([S([10, 0, 0, 10, 0, 0, 10, 0, 0, 10])]) == "seq.train"
    assert fam([S([10, 10, 0, 10, 0, 0, 0, 10, 10, 10])]) == "seq.prbs"
    assert fam([S([10, 0, 0, 0, 10])]) == "seq.pp"
    assert fam([S([0, 5, -5, 10, -10, 5])]) == "seq.chirp"
    assert fam([S([-10, 10, -10, 10, -10, 10])]) == "seq.train"          # bipolar binary: ON = the higher level
    assert fam([S([0, 0, 30, 30, 0])]) == "pulse.1"                       # one run with a zero baseline = one pulse
    assert fam([S([20] * 50, seg=0.01)]) == "act.1"                       # a constant level over 0.5 s = sustained current
    assert fam([S([0, 0, 0])]) == "other"
    assert fam([S([5, 5, 10, 10])]) == "other"                            # one switch between two non-zero levels


def test_silencing_edges_params():
    def Sil(t0, t1, *u):
        return {"kind": "silence", "t0": t0, "t1": t1, "targets": list(u)}
    assert fam([Sil(0.5, 0.8, 1)]) == "sil.1"
    assert fam([Sil(0.5, None, 1)]) == "sil.1p"
    assert fam([Sil(0.5, 0.8, 1, 2)]) == "sil.2"
    assert fam([Sil(0.5, None, 1, 2, 3)]) == "sil.g"
    assert fam([Sil(0.5, 0.8, 1), Sil(0.5, 0.8, 2)]) == "sil.2"           # same window -> merged
    assert fam([Sil(0.5, 0.8, 1), Sil(0.6, 0.9, 2)]) == "comp.sim"        # overlapping, different windows
    assert fam([Sil(0.2, 0.3, 1), Sil(0.6, 0.9, 2)]) == "sil.1"           # repeated, separated

    def E(f, *edges):
        return {"kind": "edge_scale", "t0": 0.5, "t1": None, "edges": [list(e) for e in edges], "factor": f}
    assert fam([E(0.0, (1, 2))]) == "edge.rm"
    assert fam([E(0.4, (1, 2), (3, 4))]) == "edge.w"
    assert fam([E(1.5, (1, 2))]) == "other"
    assert fam([{"kind": "param", "t0": 0.5, "t1": 0.9, "targets": {"1": {"gain": 1.3}}}]) == "param.1"
    assert fam([{"kind": "param", "t0": 0.5, "t1": 0.9, "targets": {"1": {"gain": 1.3}, "2": {"tau": 0.8}}}]) == "other"


def test_composition_and_truth():
    assert fam([K(0.5, u1=10.0), C(1.0, 1.05, u2=5.0)]) == "comp.seq"
    assert fam([K(0.55, u1=10.0), C(0.5, 0.6, u2=5.0)]) == "comp.sim"    # the kick falls inside the pulse window
    assert F.family_of(proto([{"kind": "latent_kick", "t": 0.5, "dz": [1.0]}]), SYS, allow_truth=True) == "latent"
    d = F.family_detail(proto([K(0.5, u1=1.0), K(0.5, u2=1.0), C(1.0, 1.05, u2=5.0)]), SYS)
    assert d == {"family": "comp.seq", "n_events": 2, "event_families": ["kick.2", "pulse.1"]}


def test_every_vocabulary_family_is_reachable():
    seen = {fam(), fam(stimulus=[[0.0, 1.2]]), fam(r0={"kind": "state", "values": {"1": 1.0}}), fam(params_seed=5, sysrec=NOMINAL_SEED_SYS),
            fam(weight_noise={"sd": 0.05, "seed": 1})}
    seen |= {fam([K(0.5, u1=1.0)]), fam([K(0.5, u1=1.0, u2=1.0)]), fam([K(0.5, u1=1.0, u2=1.0, u3=1.0)]), fam([K(0.5, u1=99.0)])}
    seen |= {fam([C(0.5, 0.6, u1=1.0)]), fam([C(0.5, 0.6, u1=1.0, u2=1.0)]), fam([C(0.5, 0.6, u1=1.0, u2=1.0, u3=1.0)]),
             fam([C(0.5, 0.6, u1=99.0)]), fam([C(0.5, None, u1=1.0)]), fam([C(0.5, None, u1=-1.0)])}
    seen |= {fam([{"kind": "silence", "t0": 0.5, "t1": t1, "targets": tg}]) for t1, tg in ((0.6, [1]), (None, [1]), (0.6, [1, 2]), (0.6, [1, 2, 3]))}
    seen |= {fam([{"kind": "edge_scale", "t0": 0.5, "t1": None, "edges": [[1, 2]], "factor": f}]) for f in (0.0, 0.5)}
    seen |= {fam([{"kind": "param", "t0": 0.5, "t1": None, "targets": {"1": {"tau": 1.2}}}])}
    seq = [[10, 0, 10, 0, 10], [10, 10, 0, 10, 0, 0, 10], [0, 3, -3, 6], [10, 0, 0, 10]]
    seen |= {fam([{"kind": "current_seq", "t0": 0.5, "seg": 0.01, "targets": {"1": v}}]) for v in seq}
    seen |= {fam([K(0.5, u1=1.0), C(1.0, 1.05, u2=5.0)]), fam([K(0.55, u1=1.0), C(0.5, 0.6, u2=5.0)])}
    assert set(F.VOCABULARY) <= seen


def test_split_records():
    sup = F.supported_families(REAL_CAPABILITY)
    assert set(sup) == set(F.VOCABULARY)
    real = F.split_record(F.REAL_TRAIN, sup)
    assert real["families_train"] == list(F.REAL_TRAIN)
    assert set(real["hidden_only"]) == set(F.HIDDEN_ONLY)
    assert not set(real["families_heldout"]) & set(F.HIDDEN_ONLY)
    assert set(real["families_train"]) | set(real["families_heldout"]) | set(real["hidden_only"]) == set(F.VOCABULARY)
    for rot in F.ROTATIONS:
        r = F.rotation_split(rot, REAL_CAPABILITY)
        assert set(F.OBS) <= set(r["families_train"]) and r["rotation"] == rot
    cap_no_edges = {**REAL_CAPABILITY, "edge_scale": {"supported": False}}
    with pytest.raises(ValueError):
        F.rotation_split("R2", cap_no_edges)
    assert F.shift_kind("sil.2", ["sil.1"]) == "near" and F.shift_kind("pulse.hi", ["pulse.1"]) == "near"
    assert F.shift_kind("act.1", ["pulse.1"]) == "near" and F.shift_kind("seq.train", ["pulse.1"]) == "near"
    assert F.shift_kind("edge.w", ["sil.1", "pulse.1"]) == "far" and F.shift_kind("sil.1", ["sil.1"]) == "in"
