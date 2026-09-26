# Counterexample search: real_public_lin_dmdc_t_effect

- method: lin_dmdc_t; suite: real / final; hidden material: False; objective: effect
- strategies ['random', 'evolve', 'structured', 'bo'], seeds [0, 1, 2], budget 60 per search, init-state True; backend modal

| system | searches | scored | random median | worst | worst / median | candidates | distinct | broken immediately |
|---|---|---|---|---|---|---|---|---|
| real:net1:full | 12 | 465 | 3.94 | 4.06e+08 | 1.03e+08 | 94 | 77 | 0.5 |
| real:net1:mech:02fa13b8 | 12 | 446 | 0.726 | 3.11e+06 | 4.28e+06 | 77 | 50 | 0.5 |
| real:net1:mech:cce0c6c4 | 12 | 500 | 1.01 | 1.38e+07 | 1.37e+07 | 65 | 55 | 0.333 |
| real:net2:full | 12 | 497 | 1.48 | 6.33e+10 | 4.29e+10 | 104 | 74 | 0.75 |
| real:net2:mech:3aa95ab7 | 12 | 486 | 0.848 | 6.01e+05 | 7.09e+05 | 31 | 26 | 0.0833 |
| real:net2:mech:3e8f8895 | 12 | 538 | 1 | 5.73e+07 | 5.73e+07 | 82 | 67 | 0.333 |
| real:net2:mech:6883ab7b | 12 | 545 | 0.927 | 742 | 801 | 45 | 20 | 0.417 |
| real:net3:full | 12 | 460 | 6.3 | 2.36e+07 | 3.75e+06 | 97 | 87 | 0.667 |
| real:net3:mech:362044b4 | 12 | 499 | 1 | 2.45e+11 | 2.45e+11 | 59 | 56 | 0.333 |
| real:net3:mech:92614efe | 12 | 455 | 0.744 | 1.67e+08 | 2.24e+08 | 60 | 52 | 0.417 |

Overall: {"n_systems": 10, "n_systems_with_counterexamples": 10, "n_distinct_total": 564, "median_worst_over_random_median": 35521523.42877738, "systems_broken_immediately": 4}
