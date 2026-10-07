"""Review v3.3 (N8): the control margin is guaranteed at construction on EVERY tier and seed, not only on the tested ones.

Twelve type-20 / 21 systems of tiers and seeds no other test builds (the reviewers' audit case build_suite("audit", 1, 4), type 20,
all four indices; audit seeds 101 and 202, types 20 and 21, two indices each): truth()["control_margin"] reports a simulated margin
>= 1.5 at the primary (0.25 s) and the long (1 s) horizon, and an independent recomputation of controls.simulated_margin (no
cache) reproduces it and meets the bound."""

import os

from p4synth.controls import MARGIN_ACCEPT, simulated_margin
from p4synth.suite import build_system

CASES = [("audit", 1, 20, j, 4) for j in range(4)] + [("audit", sd, t, j, 2) for sd in (101, 202) for t in (20, 21) for j in (0, 1)]


def test_controls_meet_margin_on_unseen_audit_seeds():
    rows = []
    for tier, seed, t, j, n in CASES:
        s = build_system(tier, seed, t, j, n)
        cm = s.truth(include_draw=False)["control_margin"]
        env = os.environ.pop("P4SYNTH_CACHE_DIR", None)
        try:
            sim = simulated_margin(s)                  # independent recomputation, no cache
        finally:
            if env is not None:
                os.environ["P4SYNTH_CACHE_DIR"] = env
        rows.append((tier, seed, t, s.info["variant"], len(s.observed), cm["primary"], cm["1s"], cm["attempt"]))
        assert abs(sim[0.25]["ratio"] - cm["primary"]) < 1e-3 and abs(sim[1.0]["ratio"] - cm["1s"]) < 1e-3
        assert sim[0.25]["ratio"] >= MARGIN_ACCEPT and sim[1.0]["ratio"] >= MARGIN_ACCEPT, rows[-1]
    for r in rows:
        print(r)
    assert len(rows) >= 10
