"""Suite builder: data format, no truth leakage, split hold-outs, truth completeness, reproducibility."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

from p3synth import build_suite
from p3synth.protocol import intervened_neurons
from p3synth.suite import FAMILY_DOC, TEST_PARAMS, TRAIN_PARAMS
from p3synth.systems import FAMILIES, TRAPS, catalog, get_system

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.data import Dataset  # noqa: E402

NAMES = ["leaky", "groupA_impl1", "time_index", "output_shortcut", "nuisance_ou"]
TRAIN_TYPES = {"kick", "current", "silence_single", "nominal", "init", "stim", "param_draw", "weight_noise"}


@pytest.fixture(scope="module")
def suite(tmp_path_factory):
    root = tmp_path_factory.mktemp("suite")
    res = build_suite(root / "public", root / "truth", seed=0, tier="dev", scale=0.5, workers=3, names=NAMES)
    return root, res


def test_format_readable_with_reference_loader(suite):
    root, res = suite
    ds = Dataset(root / "public")
    assert len(ds.index) == res["n_traj"] and set(ds.manifest["splits"]) == {"train", "val", "test", "twin"}
    for sid, meta in ds.systems.items():
        assert meta["kind"] == "synthetic" and meta["group"] is None and meta["readout"] == []
        for tr in ds.iter(system_id=sid, split="test"):
            assert tr.x.shape == (len(tr.t), len(meta["observed"])) and tr.u.shape[1] == meta["input_dim"]
            assert tr.y.shape[1] == meta["readout_dim"] and tr.x.dtype == np.float32
    for row in ds.index[:20]:
        with np.load(root / "public" / "traj" / f"{row['key']}.npz") as z:
            assert set(z.files) == {"t", "x", "u", "y"}


def test_no_truth_leak_in_public(suite):
    root, _ = suite
    pub = root / "public"
    text = (pub / "manifest.json").read_text() + (pub / "index.jsonl").read_text()
    forbidden = [d.name for d in catalog()] + [d.latent_key for d in catalog()] + list(FAMILIES.values()) + \
        list(TRAPS.values()) + ["latent_set", "latent_impulse", "grp-", "trap", "implementation_group", "theta"]
    for word in forbidden:
        assert not re.search(r"(?<![A-Za-z0-9_])" + re.escape(word) + r"(?![A-Za-z0-9_])", text), word
    assert not re.search(r'"k"\s*:', text)
    ds = Dataset(pub)
    for sid in ds.systems:
        assert re.fullmatch(r"syn-[0-9a-f]{10}", sid)
    assert {r["family"] for r in ds.index} <= set(FAMILY_DOC)
    assert all(set(r["info"]) - {"pair"} == {"simulator", "n_samples"} for r in ds.index)
    assert not any(p.name in ("truth.json", "latents", "systems") for p in pub.rglob("*"))


def test_split_holdouts(suite):
    root, _ = suite
    ds = Dataset(root / "public")
    truth = json.loads((root / "truth" / "truth.json").read_text())
    for sid in ds.systems:
        design = truth["suite"]["split_design"][sid]
        tr_t, te_t = set(design["train_targets"]), set(design["test_targets"])
        assert not (tr_t & te_t) and tr_t | te_t == set(range(truth["systems"][sid]["n"]))
        rows = ds.select(system_id=sid)
        types = {"train": set(), "val": set(), "test": set(), "twin": set()}
        for r in rows:
            p, split = r["protocol"], r["split"]
            touched = intervened_neurons(p)
            if split in ("train", "val"):
                assert touched <= tr_t
                assert r["family"] in TRAIN_TYPES
                assert p["params_seed"] in TRAIN_PARAMS
                for e in p["events"]:
                    assert e["kind"] != "edge_remove"
                    n = len(e.get("delta") or e.get("targets") or [])
                    assert n == 1
                if p["weight_noise"]:
                    assert p["weight_noise"]["sd"] == 0.05 and p["weight_noise"]["seed"] < 10_000
            else:
                assert touched <= te_t
            for e in p["events"]:
                kind = e["kind"] + ("_group" if len(e.get("delta") or e.get("targets") or [0]) > 1 else "")
                types[split].add(kind)
        assert {"silence_group", "kick_group", "current_group"} <= types["test"]
        assert not ({"silence_group", "kick_group", "current_group", "edge_remove"} & (types["train"] | types["val"]))
        test_ps = {r["protocol"]["params_seed"] for r in rows if r["family"] in ("param_heldout", "combined_heldout")}
        assert test_ps and test_ps <= set(TEST_PARAMS)
        wn = [r["protocol"]["weight_noise"] for r in rows if r["family"] == "noise_heldout"]
        assert wn and all(w["sd"] == 0.12 and w["seed"] >= 10_000 for w in wn)


def test_heldout_initial_states(suite):
    root, _ = suite
    ds = Dataset(root / "public")
    truth = json.loads((root / "truth" / "truth.json").read_text())
    sid = next(s for s, t in truth["systems"].items() if t["name"] == "leaky")
    r_train, r_test = [], []
    for r in ds.select(system_id=sid):
        with np.load(root / "truth" / "latents" / f"{r['key']}.npz") as z:
            z0 = abs(float(z["z"][0, 0]))
        if r["family"] == "init":
            r_train.append(z0)
        if r["family"] in ("init_heldout", "combined_heldout"):
            r_test.append(z0)
    assert max(r_train) < 1.05 and min(r_test) > 0.95


def test_truth_complete_and_consistent(suite):
    root, _ = suite
    truth = json.loads((root / "truth" / "truth.json").read_text())
    tidx = [json.loads(line) for line in (root / "truth" / "truth_index.jsonl").read_text().splitlines()]
    ds = Dataset(root / "public")
    assert {r["key"] for r in tidx} == {r["key"] for r in ds.index}
    assert len({r["key"] for r in ds.index}) == len(ds.index)                    # no duplicate trajectories
    for sid, t in truth["systems"].items():
        for field in ("family", "trap", "k", "f", "g", "observation_map", "implementation_group", "observability",
                      "controllability", "neuron_roles", "interventions"):
            assert field in t
        with np.load(root / "truth" / "systems" / f"{sid}.npz") as z:
            assert np.allclose(z["D"] @ z["E"], np.eye(z["E"].shape[1]), atol=1e-9)
    groups = truth["suite"]["implementation_groups"]
    assert "grp-A" in groups
    # re-simulating a published protocol reproduces the public arrays and the truth latent exactly
    by_name = {t["name"]: sid for sid, t in truth["systems"].items()}
    for name in ("time_index", "groupA_impl1"):
        s = get_system(name, 0, "dev")
        assert s.system_id == by_name[name]
        rows = [r for r in ds.select(system_id=s.system_id) if r["protocol"]["events"]][:2]
        for r in rows:
            out = s.simulate(r["protocol"])
            tr = ds.load(r)
            assert np.array_equal(out["x"].astype(np.float32), tr.x) and np.array_equal(out["y"].astype(np.float32), tr.y)
            with np.load(root / "truth" / "latents" / f"{r['key']}.npz") as z:
                assert np.array_equal(out["z"].astype(np.float32), z["z"])


def test_truth_dir_must_be_separate(tmp_path):
    with pytest.raises(ValueError):
        build_suite(tmp_path / "pub", tmp_path / "pub" / "truth", seed=0, tier="dev", names=["leaky"], workers=1)


def test_noise_seeds_and_twins(suite):
    root, _ = suite
    ds = Dataset(root / "public")
    rows = {r["key"]: r for r in ds.index}
    truth_keys = {json.loads(l)["key"] for l in (root / "truth" / "truth_index.jsonl").read_text().splitlines()}
    assert all(isinstance(r["protocol"].get("noise_seed"), int) and r["protocol"]["noise_seed"] >= 0 for r in ds.index)
    intervened = [r for r in ds.index if r["split"] == "test" and r["protocol"]["events"]]
    twins = [r for r in ds.index if r["split"] == "twin"]
    assert intervened and len(twins) == len(intervened)
    for r in intervened:
        assert r["info"]["pair"] == r["key"]
    for tw in twins:
        pk = tw["info"]["pair"]
        iv = rows[pk]
        assert iv["split"] == "test" and tw["family"] == iv["family"] and tw["protocol"]["events"] == []
        assert tw["protocol"] == dict(iv["protocol"], events=[])
        assert tw["key"] in truth_keys
        # shared noise realisation: bitwise identical up to (and including) the first event time
        t_first = min(e.get("t", e.get("t0")) for e in iv["protocol"]["events"])
        i = int(round(t_first / iv["protocol"]["dt"]))
        a, b = ds.load(tw), ds.load(iv)
        assert np.array_equal(a.x[: i + 1], b.x[: i + 1]) and np.array_equal(a.y[: i + 1], b.y[: i + 1])
        with np.load(root / "truth" / "latents" / f"{tw['key']}.npz") as za, \
                np.load(root / "truth" / "latents" / f"{pk}.npz") as zb:
            assert np.array_equal(za["z"][: i + 1], zb["z"][: i + 1])
    # every other row has no pair
    assert all("pair" not in r["info"] for r in ds.index if r["split"] in ("train", "val") or
               (r["split"] == "test" and not r["protocol"]["events"]))


def test_targets_public(suite):
    root, _ = suite
    ds = Dataset(root / "public")
    truth = json.loads((root / "truth" / "truth.json").read_text())
    for sid, meta in ds.systems.items():
        tp = meta["targets_public"]
        assert tp == sorted(truth["suite"]["split_design"][sid]["train_targets"])
        for r in ds.select(system_id=sid):
            if r["split"] in ("train", "val"):
                assert intervened_neurons(r["protocol"]) <= set(tp)
    text = (root / "public" / "manifest.json").read_text() + (root / "public" / "index.jsonl").read_text()
    assert "test_targets" not in text and "train_targets" not in text and "split_design" not in text
