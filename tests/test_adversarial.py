"""Adversarial suite (brainir.discovery.adversarial): every trap type builds, verifies and exports; the truth fields are consistent in
both node orders; parameters come from the seed within their documented ranges; the scorer's definitions hold on hand-made results.
Fast: one small verified instance per trap, four verification seeds, no discovery method is run."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from brainir import paths
from brainir.discovery import DiscoveryProblem
from brainir.discovery import adversarial as A
from brainir.discovery.synthetic import MOTIFS

FAST_SEEDS = [0, 1, 2, 3]
FAST = {  # one quick variant per trap for the build / verify / export fixture (the calibration of every variant is in the design note)
    "latent_backup": ("band", {}),
    "masked_gate": ("nfc_band", {}),
    "distributed_drive": ("identical", {"n_relays": 12}),
    "subset_of_draws": ("latch_persistence", {}),
    "identical_decoy": ("ffd_band", {}),
    "fragile_vs_robust": ("band", {}),
}


EXTRA = {"identical_decoy/nfc_band": ("identical_decoy", "nfc_band")}  # releasing its decoy overdrives the band: gate and latch essential
KEYS = [*FAST, *EXTRA]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("adversarial_suite")
    out = {}
    jobs = [(trap, trap, variant, knobs) for trap, (variant, knobs) in FAST.items()] + [(key, t, v, {}) for key, (t, v) in EXTRA.items()]
    for k, (key, trap, variant, knobs) in enumerate(jobs):
        spec = A.AdversarialSpec(trap, variant, n_total=50, seed=10 + 20 * k, knobs=knobs)
        inst, ver, used = A.build_verified(spec, seeds=FAST_SEEDS, max_tries=8)
        info = A.export_adversarial(inst, ver, root, salt="test-salt")
        truth = json.loads((root / "truth" / f"{used.label}.json").read_text(encoding="utf-8"))
        out[key] = {"inst": inst, "ver": ver, "spec": used, "dir": Path(info["dir"]), "truth": truth, "root": root}
    return out


@pytest.mark.parametrize("trap", A.TRAPS)
def test_every_trap_builds_verifies_and_exports(built, trap):
    b = built[trap]
    assert b["ver"]["verified"] and all(c["ok"] for c in b["ver"]["checks"].values()), b["ver"]["checks"]
    d = b["dir"]
    for net in ("main", "order1"):
        for f in ("neurons.parquet", "edges.parquet", "stimulus.json", "readout.json", "criterion.json", "network.json"):
            assert (d / "networks" / net / f).exists(), (net, f)
        DiscoveryProblem.from_bundle(d, net)  # loads as a public problem
    # truth only under root/truth; nothing in the public instance names the trap or the adversarial suite
    public = [p for p in d.rglob("*") if p.is_file()]
    assert not any("truth" in p.name.lower() for p in public)
    for p in public:
        if p.suffix == ".json" and p.name != "manifest.json":
            text = p.read_text(encoding="utf-8").lower()
            assert "adversarial" not in text and trap not in text, p
    assert b["truth"]["suite"] == A.SUITE_ID and b["truth"]["adversarial"]["trap"] == trap and b["truth"]["adversarial"]["verified"] is True


@pytest.mark.parametrize("trap", A.TRAPS)
def test_truth_is_consistent_in_every_node_order(built, trap):
    b = built[trap]
    adv = b["inst"].truth["adversarial"]
    n = b["inst"].W.shape[0]
    nodes = lambda sets: {int(p) for s in sets for p in s}  # noqa: E731
    # canonical truth
    assert set(adv) >= {"mechanism", "essential", "latent_backups", "acceptable", "degenerate", "subset_of_draws", "contested", "targets"}
    assert adv["mechanism"] and all(0 <= p < n for p in nodes(adv["mechanism"]) | set(adv["contested"].values()))
    assert set(adv["essential"]) <= set(adv["silence_pass"]) and all(adv["silence_pass"][p] <= A.FAIL_MAX for p in adv["essential"])
    assert all(t is None or 0.0 <= t <= 1.0 for t in adv["targets"].values()) and set(adv["contested"].values()) <= set(adv["targets"])
    for p in adv["silent_members"]:
        assert adv["rates_hz"][p] <= A.SILENT_HZ, (p, adv["rates_hz"][p])
    if adv["acceptable"]:  # a compact mechanism exists: it is the correct answer, and no silent node belongs to it
        assert adv["acceptable"] == adv["mechanism"] and not (set(adv["silent_members"]) & nodes(adv["acceptable"]))
    # trap-specific definitions
    if trap in ("latent_backup", "identical_decoy"):
        assert adv["latent_backups"] and set(adv["silent_members"]) <= nodes(adv["latent_backups"])
        assert all(adv["rates_hz"][p] >= A.ACTIVE_HZ for p in nodes(adv["acceptable"]))  # the planted mechanism is what fires
    if trap == "masked_gate":
        S = adv["contested"]["gate"]
        assert S in adv["essential"] and S in adv["acceptable"][0] and adv["contested"]["relay"] in adv["silent_members"]
    if trap == "distributed_drive":
        deg = adv["degenerate"]
        relays = nodes(adv["mechanism"])
        assert deg["flag"] and not adv["acceptable"] and 2 <= deg["min_set_size"] < len(relays)
        assert set(deg["membership_frequency"]) == relays and adv["exchangeable"] == [sorted(relays)]
    if trap == "subset_of_draws":
        sod = adv["subset_of_draws"]
        assert sod["flag"] and 0.25 <= sod["intact_pass"] <= 0.92 and len(sod["copy_keep_only_pass"]) == len(adv["copies"])
        assert adv["acceptable"] == [sorted(nodes(adv["copies"]))] and adv["exchangeable"]
    if trap == "fragile_vs_robust":
        assert adv["fragile_alternatives"] and not (nodes(adv["fragile_alternatives"]) & nodes(adv["acceptable"]))
    # exported truth: the same fields in each network's public positions
    for net in ("main", "order1"):
        tnet = b["truth"]["networks"][net]
        perm = np.asarray(tnet["perm"])
        ta = tnet["adversarial"]
        for name, pos in ta["contested"].items():
            assert int(perm[int(pos)]) == adv["contested"][name]
        for key in ("mechanism", "acceptable", "latent_backups", "fragile_alternatives", "exchangeable"):
            assert [sorted(int(perm[p]) for p in s) for s in ta[key]] == [sorted(s) for s in adv[key]], key
        assert sorted(int(perm[p]) for p in ta["essential"]) == sorted(adv["essential"])
        assert tnet["alternatives_positions"] == (ta["acceptable"] or ta["mechanism"])


@pytest.mark.parametrize("key", KEYS)
def test_every_acceptable_core_contains_every_essential_node(built, key):
    """The truth definition (A.DEFINITION), the same for every trap: every acceptable core and every mechanism set contains every
    measured-essential node, essential nodes are membership targets 1, and the exported truth is a fixed point of the migration."""
    b = built[key]
    adv = b["inst"].truth["adversarial"]
    E = set(adv["essential"])
    assert adv["definition"] == A.DEFINITION
    assert all(E <= set(a) for a in adv["acceptable"]) and all(E <= set(m) for m in adv["mechanism"])
    assert all(adv["targets"][p] == 1.0 for p in E)
    assert all(set(d) <= set(a) for d, a in zip(adv["acceptable_designed"], adv["acceptable"]))
    for net in ("main", "order1"):
        tn = b["truth"]["networks"][net]
        ta = tn["adversarial"]
        assert ta["definition"] == A.DEFINITION and all(set(ta["essential"]) <= set(a) for a in ta["acceptable"] + ta["mechanism"])
        assert all(ta["targets"][str(p)] == 1.0 for p in ta["essential"])
        assert A.normalize_truth_network(tn) == tn  # already in the current definition


def test_reported_case_gate_and_latch_are_part_of_the_correct_core(built):
    tn = built["identical_decoy/nfc_band"]["truth"]["networks"]["main"]
    ta = tn["adversarial"]
    gate, latch = ta["contested"]["gate"], ta["contested"]["latch"]
    assert {gate, latch} <= set(ta["essential"]) and ta["silence_pass"][str(gate)] <= A.FAIL_MAX
    motif = ta["acceptable_designed"][0]
    full = ta["acceptable"][0]
    assert set(full) == set(motif) | set(ta["essential"]) and {gate, latch} <= set(full)
    principled = A.score_adversarial(_result(full, {p: 0.95 for p in full}), tn)
    assert principled["correct"] and not principled["confident_wrong"] and principled["essential_recall"] == 1.0
    motif_only = A.score_adversarial(_result(motif, {p: 0.95 for p in motif}), tn)
    assert not motif_only["correct"] and motif_only["confident_wrong"] and set(motif_only["essential_missed"]) >= {gate, latch}


def test_normalize_truth_network_migrates_an_old_entry(built):
    new = built["identical_decoy/nfc_band"]["truth"]["networks"]["main"]
    na = new["adversarial"]
    old = copy.deepcopy(new)  # the same entry as exported before the definition: designed sets only, gate and latch targets 0
    oa = old["adversarial"]
    for k in ("acceptable_designed", "mechanism_designed", "definition"):
        oa.pop(k)
    oa["acceptable"], oa["mechanism"] = copy.deepcopy(na["acceptable_designed"]), copy.deepcopy(na["mechanism_designed"])
    for name in ("gate", "latch"):
        oa["targets"][str(oa["contested"][name])] = 0.0
    extra = [10 ** 6]  # an alternative added by someone else (e.g. a suite audit) is kept after the migrated ones
    old["alternatives_positions"] = [list(a) for a in oa["acceptable"]] + [extra]
    old["core_positions"] = list(oa["acceptable"][0])
    snapshot = json.dumps(old, sort_keys=True)
    norm = A.normalize_truth_network(old)
    assert json.dumps(old, sort_keys=True) == snapshot  # pure: the input is unchanged
    for k in ("acceptable", "mechanism", "acceptable_designed", "mechanism_designed", "definition", "targets", "essential"):
        assert norm["adversarial"][k] == na[k], k
    assert norm["alternatives_positions"] == new["alternatives_positions"] + [extra] and norm["core_positions"] == new["core_positions"]
    assert A.normalize_truth_network(norm) == norm  # idempotent
    result = _result(na["acceptable"][0], {p: 0.95 for p in na["acceptable"][0]})
    assert A.score_adversarial(result, old)["correct"] and A.score_adversarial(result, old) == A.score_adversarial(result, new)
    assert A.normalize_truth_network({"perm": [0, 1]}) == {"perm": [0, 1]}  # not adversarial: an unchanged copy


def test_parameters_come_from_the_seed_within_documented_ranges():
    for trap in A.TRAPS:
        for variant in sorted(A.VARIANTS[trap]):
            seen = []
            for seed in range(4):
                inst = A.build_adversarial(A.AdversarialSpec(trap, variant, n_total=50, seed=seed)) if trap not in (
                    "distributed_drive", "fragile_vs_robust") else None
                if inst is None:  # these two calibrate a threshold by simulation at build time: check their draws on two seeds only
                    if seed > 1:
                        continue
                    inst = A.build_adversarial(A.AdversarialSpec(trap, variant, n_total=50, seed=seed, knobs={"n_relays": 12}))
                params = inst.truth["adversarial"]["params"]
                seen.append(inst.W.tobytes())
                for name, rng in A.PARAM_RANGES[trap].items():
                    if name in params and rng[0] in ("int", "real") and not (trap == "distributed_drive" and name == "n_relays"):
                        v = params[name]
                        if name == "jitter" and variant == "identical":
                            assert v == 0.0
                            continue
                        if name == "extra_drive" and variant == "ei_rhythm":
                            assert 0 <= v <= 5
                            continue
                        assert rng[1] <= v <= rng[2], (trap, variant, name, v, rng)
            assert len(set(seen)) == len(seen), (trap, variant)  # every seed gives a different network


def test_fresh_seed_gives_a_different_instance_and_knobs_pin_one_parameter():
    s1 = A.AdversarialSpec("latent_backup", "band", n_total=50, seed=7)
    s2 = A.AdversarialSpec("latent_backup", "band", n_total=50, seed=8)
    i1, i2 = A.build_adversarial(s1), A.build_adversarial(s2)
    assert i1.truth["adversarial"]["params"] != i2.truth["adversarial"]["params"] and not np.array_equal(i1.W, i2.W)
    again = A.build_adversarial(A.AdversarialSpec("latent_backup", "band", n_total=50, seed=7))
    assert np.array_equal(i1.W, again.W) and i1.truth["adversarial"] == again.truth["adversarial"]  # deterministic
    pinned = A.build_adversarial(A.AdversarialSpec("latent_backup", "band", n_total=50, seed=7, knobs={"gate_out": 150}))
    p0, p1 = i1.truth["adversarial"]["params"], pinned.truth["adversarial"]["params"]
    assert p1["gate_out"] == 150 and {k: v for k, v in p0.items() if k != "gate_out"} == {k: v for k, v in p1.items() if k != "gate_out"}


def test_spec_label_variant_and_default_design():
    s = A.AdversarialSpec("masked_gate", None, seed=3)
    assert s.variant in A.VARIANTS["masked_gate"] and s.label == f"adv__masked_gate__{s.variant}__n60__s3"
    assert A.AdversarialSpec("masked_gate", "ei_rhythm", seed=3, name="inst_7f3a").label == "inst_7f3a"
    with pytest.raises(ValueError):
        A.AdversarialSpec("no_such_trap")
    specs = A.adversarial_specs()
    assert {s.trap for s in specs} == set(A.TRAPS) and {(s.trap, s.variant) for s in specs} == {(t, v) for t in A.TRAPS for v in A.VARIANTS[t]}
    assert {s.n_total for s in specs} == {60, 150, 1500} and len({s.seed for s in specs}) == len(specs)
    criteria = {MOTIFS[A.VARIANTS[s.trap][s.variant]]().criterion["type"] for s in specs}
    assert criteria == {"rhythm", "activity_band", "ramp", "persistence", "selectivity"}


def _result(core, probs, essential=None, diagnostics=None):
    return {"core": list(core), "inclusion_probability": {str(k): v for k, v in probs.items()}, "essential": essential or {},
            "diagnostics": diagnostics or {}, "fidelity": {"keep_only_pass_fraction": 1.0}}


def test_scorer_definitions_on_hand_made_results(built):
    # latent backup: the planted chain is correct; the silent backup is a confident wrong answer
    tn = built["latent_backup"]["truth"]["networks"]["main"]
    ta = tn["adversarial"]
    planted, backup = ta["acceptable"][0], ta["latent_backups"][0]
    good = A.score_adversarial(_result(planted, {**{p: 0.95 for p in planted}, **{p: 0.1 for p in backup}}), tn)
    assert good["correct"] and good["exact"] and not good["confident_wrong"] and not good["latent_backup_returned"]
    bad = A.score_adversarial(_result(backup, {**{p: 0.9 for p in backup}, **{p: 0.15 for p in planted}}), tn)
    assert not bad["correct"] and bad["confident"] and bad["confident_wrong"] and bad["latent_backup_returned"]
    assert set(bad["latent_members_in_core"]) == set(ta["silent_members"]) and bad["brier_contested"] > good["brier_contested"]
    assert {int(n) for _, _, n in bad["calibration_items"]} >= {int(p) for p in ta["contested"].values()}
    # masked gate: the motif without the gate misses an essential node
    tn = built["masked_gate"]["truth"]["networks"]["main"]
    ta = tn["adversarial"]
    S = ta["contested"]["gate"]
    motif = [p for p in ta["acceptable"][0] if p != S]
    miss = A.score_adversarial(_result(motif, {**{p: 0.97 for p in motif}, S: 0.03}, essential={p: True for p in motif}), tn)
    assert not miss["correct"] and miss["confident_wrong"] and miss["essential_missed"] == [S] and miss["essential_recall"] < 1.0
    assert miss["essential_claims"]["wrong"] == 0
    # distributed drive: any compact core is wrong unless degeneracy is flagged
    tn = built["distributed_drive"]["truth"]["networks"]["main"]
    ta = tn["adversarial"]
    relays = ta["mechanism"][0]
    k = ta["degenerate"]["min_set_size"]
    probs = {**{p: 0.9 for p in relays[:k]}, **{p: 0.03 for p in relays[k:]}}
    plain = A.score_adversarial(_result(relays[:k], probs), tn)
    flagged = A.score_adversarial(_result(relays[:k], probs, diagnostics={"flags": ["degenerate"]}), tn)
    assert not plain["correct"] and plain["confident_wrong"] and flagged["correct"] and flagged["degenerate_flagged"]
    assert plain["exchangeable_gap"] == pytest.approx(0.87)
    # subset of draws: one copy alone is not the mechanism
    tn = built["subset_of_draws"]["truth"]["networks"]["main"]
    ta = tn["adversarial"]
    one = ta["copies"][0]
    r = A.score_adversarial(_result(one, {p: 0.97 for p in one}), tn)
    assert not r["correct"] and r["confident_wrong"] and r["subset_of_draws"] and r["exchangeable_gap"] > 0.5
    with pytest.raises(ValueError):
        A.score_adversarial(_result([], {}), {"perm": []})


def test_scorer_simulation_fields_and_summary(built):
    b = built["latent_backup"]
    tn = b["truth"]["networks"]["main"]
    ta = tn["adversarial"]
    problem = DiscoveryProblem.from_bundle(b["dir"], "main")
    bad = A.score_adversarial(_result(ta["latent_backups"][0], {p: 0.9 for p in ta["latent_backups"][0]}), tn, problem, seeds=[5500, 5501])
    good = A.score_adversarial(_result(ta["acceptable"][0], {p: 0.95 for p in ta["acceptable"][0]}), tn, problem, seeds=[5500, 5501])
    assert bad["participation"]["min_hz"] <= A.SILENT_HZ and bad["participation"]["fraction_active"] == 0.0
    assert good["participation"]["fraction_active"] == 1.0 and good["core_keep_only_pass"] >= 0.5 and good["intact_pass"] >= 0.5
    summary = A.summarize_adversarial([bad, good])
    assert summary["per_trap"]["latent_backup"]["n"] == 2 and summary["confident_wrong"] == 0.5 and summary["reliability"]


def test_module_is_generic_and_truth_bearing():
    root = paths.repo_root() / "src" / "brainir"
    src = (root / "discovery" / "adversarial.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(("." * node.level) + (node.module or ""))
        elif isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
    assert not any("methods" in m or "benchmark" in m for m in imported), imported
    assert "benchmarks" not in src and "dng100" not in src.lower()
    for path in sorted((root / "methods").glob("*.py")):  # method code must not reach the adversarial truth
        assert "adversarial" not in path.read_text(encoding="utf-8"), path.name
