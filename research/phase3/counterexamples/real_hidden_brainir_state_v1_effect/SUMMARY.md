# Counterexample search: real_hidden_brainir_state_v1_effect

- method: brainir_state_v1; suite: real / final; hidden material: True; objective: effect
- strategies ['random', 'evolve', 'structured', 'bo'], seeds [0, 1, 2], budget 60 per search, init-state True; backend local

| system | searches | scored | random median | worst | worst / median | candidates | distinct | broken immediately |
|---|---|---|---|---|---|---|---|---|
| real:net1:full | 12 | 393 | 4.53 | 1e+10 | 2.21e+09 | 91 | 67 | 0.583 |
| real:net1:mech:02fa13b8 | 12 | 0 | - | - | - | 0 | 0 | 0 |
| real:net1:mech:cce0c6c4 | 12 | 437 | 0.803 | 1.82e+03 | 2.27e+03 | 106 | 45 | 0.5 |
| real:net2:full | 12 | 434 | 1.08 | 1.8e+07 | 1.67e+07 | 102 | 74 | 0.417 |
| real:net2:mech:3aa95ab7 | 12 | 0 | - | - | - | 0 | 0 | 0 |
| real:net2:mech:3e8f8895 | 12 | 460 | 0.986 | 1.82e+03 | 1.84e+03 | 72 | 24 | 0.417 |
| real:net2:mech:6883ab7b | 12 | 0 | - | - | - | 0 | 0 | 0 |
| real:net3:full | 12 | 423 | 1.06 | 1.75e+05 | 1.65e+05 | 127 | 95 | 0.583 |
| real:net3:mech:362044b4 | 12 | 521 | 0.88 | 3.09e+05 | 3.51e+05 | 86 | 65 | 0.333 |
| real:net3:mech:92614efe | 12 | 458 | 0.716 | 1.93e+04 | 2.7e+04 | 77 | 46 | 0.417 |

Overall: {"n_systems": 10, "n_systems_with_counterexamples": 7, "n_distinct_total": 416, "median_worst_over_random_median": 165452.73526914138, "systems_broken_immediately": 3}
