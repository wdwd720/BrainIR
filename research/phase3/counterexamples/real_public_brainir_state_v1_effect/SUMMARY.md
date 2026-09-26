# Counterexample search: real_public_brainir_state_v1_effect

- method: brainir_state_v1; suite: real / final; hidden material: False; objective: effect
- strategies ['random', 'evolve', 'structured', 'bo'], seeds [0, 1, 2], budget 60 per search, init-state True; backend modal

| system | searches | scored | random median | worst | worst / median | candidates | distinct | broken immediately |
|---|---|---|---|---|---|---|---|---|
| real:net1:full | 12 | 446 | 4.92 | 1.28e+08 | 2.6e+07 | 107 | 90 | 0.333 |
| real:net1:mech:02fa13b8 | 12 | 0 | - | - | - | 0 | 0 | 0 |
| real:net1:mech:cce0c6c4 | 12 | 478 | 0.856 | 1.13e+08 | 1.32e+08 | 85 | 58 | 0.5 |
| real:net2:full | 12 | 434 | 1.09 | 4.37e+08 | 4.02e+08 | 88 | 69 | 0.583 |
| real:net2:mech:3aa95ab7 | 12 | 0 | - | - | - | 0 | 0 | 0 |
| real:net2:mech:3e8f8895 | 12 | 475 | 0.951 | 1.97e+03 | 2.07e+03 | 42 | 19 | 0.25 |
| real:net2:mech:6883ab7b | 12 | 0 | - | - | - | 0 | 0 | 0 |
| real:net3:full | 12 | 391 | 1.03 | 8.63e+05 | 8.37e+05 | 114 | 78 | 0.583 |
| real:net3:mech:362044b4 | 12 | 463 | 0.923 | 5.48e+04 | 5.94e+04 | 75 | 60 | 0.5 |
| real:net3:mech:92614efe | 12 | 466 | 0.632 | 1.73e+03 | 2.74e+03 | 74 | 56 | 0.667 |

Overall: {"n_systems": 10, "n_systems_with_counterexamples": 7, "n_distinct_total": 430, "median_worst_over_random_median": 836976.3921485222, "systems_broken_immediately": 5}
