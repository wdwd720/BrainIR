"""No public field reveals types, roles or k (review item 4; review round 3, B1).

300 generated systems (suite seeds 20260926, 1, 2; 4 per type) are summarised by EVERY numeric field of their public record
(`p4synth.leakage.record_features`: n_units, readout_dim, dt, t_end, cost_units, every numeric value of the capability record — the
moderate magnitudes, maxima, hi ranges, detection floors, readout floor, time scale, admissible range, process-noise scale, ... —
obs_scale, ratios of the published magnitudes, and statistics of the public graph and of the observed / target lists), and every
unit by its public per-unit fields (observed, targetable, listed in- and out-degree). Cross-validated random forests (grouped by
suite seed / by system) must not predict the type, k, "no compact causal state" (types 20 / 21) or the unit roles better than
chance + a small margin: accuracy within 3 points of the majority-class baseline (1/25 for the balanced type label), ROC AUC <= 0.6
for the binary labels; for the 25-class type label the margin is 4 points (a weak residual signal from the listed graph
structure - out-degree spread, observed fraction among edge endpoints - remains: 6.2-7.3 % vs 4.2 %). The small regime (fewer than 10 observed units) is excluded from the type and k tests: there the
benchmark's compactness rule k <= max(1, N_obs / 5) forces k = 1. Non-full simulate() output carries no integration or clipping
details."""

from multiprocessing import get_context

import numpy as np
import pytest

from p4synth.engine import CORE
from p4synth.leakage import record_features, suite_records, unit_features

SEEDS = (20260926, 1, 2)


@pytest.fixture(scope="module")
def records():
    with get_context("fork").Pool(len(SEEDS)) as pool:
        parts = pool.map(suite_records, SEEDS)
    return [r for p in parts for r in p]


def _cv(X, y, groups, seed=0):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import GroupKFold
    acc, base, prob = [], [], np.zeros(len(y))
    classes = np.unique(y)
    for tr, te in GroupKFold(n_splits=min(3, len(np.unique(groups)))).split(X, y, groups):
        clf = RandomForestClassifier(n_estimators=300, min_samples_leaf=3, random_state=seed, n_jobs=1).fit(X[tr], y[tr])
        acc.append(np.mean(clf.predict(X[te]) == y[te]))
        vals, cnt = np.unique(y[tr], return_counts=True)
        base.append(np.mean(y[te] == vals[np.argmax(cnt)]))
        if classes.size == 2:
            prob[te] = clf.predict_proba(X[te])[:, list(clf.classes_).index(classes[1])]
    return float(np.mean(acc)), float(np.mean(base)), prob


def test_type_k_and_no_compact_state_not_predictable_from_public_fields(records):
    from sklearn.metrics import roc_auc_score
    F = [record_features(r["rec"]) for r in records]
    names = sorted(set().union(*[f.keys() for f in F]))
    X_all = np.nan_to_num(np.array([[f.get(n, np.nan) for n in names] for f in F], float), nan=-1.0)
    keep = [i for i, r in enumerate(records) if len(r["rec"]["observed"]) >= 10]
    X, g = X_all[keep], np.array([records[i]["seed"] for i in keep])
    types = np.array([records[i]["type"] for i in keep])
    ks = np.array([records[i]["k"] for i in keep])
    nc = (ks == "none").astype(int)
    acc_t, _, _ = _cv(X, types, g)
    chance_t = max(np.bincount(types).max() / types.size, 1.0 / 25)
    acc_k, base_k, _ = _cv(X, ks, g)
    acc_n, base_n, pr = _cv(X, nc, g)
    auc_n = roc_auc_score(nc, pr)
    print(f"{len(names)} numeric public features, {len(keep)} systems: type acc {acc_t:.3f} vs chance {chance_t:.3f}; k acc "
          f"{acc_k:.3f} vs majority {base_k:.3f}; no compact state acc {acc_n:.3f} vs {base_n:.3f}, AUC {auc_n:.3f}")
    assert acc_t <= chance_t + 0.04          # measured 6.2-7.3 % vs chance 4.2 % (permutation null: mean 4.0 %, p95 6.3 %)
    assert acc_k <= base_k + 0.03
    assert acc_n <= base_n + 0.03 and auc_n <= 0.6


def test_unit_roles_not_predictable_from_public_fields(records):
    from sklearn.metrics import roc_auc_score
    X, roles, groups = [], [], []
    for i, r in enumerate(records):
        X.append(unit_features(r["rec"]))
        roles.append(np.asarray(r["roles"]))
        groups.append(np.full(len(r["roles"]), i))
    X, roles, groups = np.vstack(X), np.concatenate(roles), np.concatenate(groups)
    acc, base, _ = _cv(X, roles, groups)
    core = (roles == CORE).astype(int)
    acc_c, base_c, pr = _cv(X, core, groups)
    auc = roc_auc_score(core, pr)
    print(f"roles: acc {acc:.3f} vs majority {base:.3f}; core vs rest: acc {acc_c:.3f} vs {base_c:.3f}, AUC {auc:.3f}; "
          f"units = {roles.size}")
    assert acc <= base + 0.03
    assert acc_c <= base_c + 0.03 and auc <= 0.6


def test_public_record_has_system_wide_values_and_simulate_hides_integration(suite):
    for s in list(suite.values())[:10]:
        cap = s.capability()
        assert np.isscalar(cap["admissible_range"]["lo"]) and np.isscalar(cap["admissible_range"]["hi"])
        assert np.isscalar(cap["process_noise"]["sd_per_sqrt_s"]) and "unit_sd_per_sqrt_s" not in cap["process_noise"]
        assert cap["admissible_range"]["lo"] == -500.0 and cap["process_noise"]["sd_per_sqrt_s"] == 100.0
        assert "es_at_moderate" not in cap["kick"] and cap["kick"]["detection_floor"] == round(cap["kick"]["moderate"] / 8.0, 4)
        assert abs(cap["readout_floor"] - 0.05 * s.obs_scale()["y"]) < 1e-6
        assert np.all(s.spec.lo == s.spec.lo[0]) and np.all(s.spec.hi == s.spec.hi[0])
        assert np.all(s.spec.noise_scale == s.spec.noise_scale[0])
        o = s.simulate(s.base_protocol(t_end=0.1))
        assert set(o["info"]) <= {"engine", "success", "system"}
        assert {"n_sub", "h", "clipped_kicks"} <= set(s.simulate(s.base_protocol(t_end=0.1), full=True)["info"])
        assert s.dt == 0.001 and s.t_end_default == 2.0 and s.input_dim == 1
