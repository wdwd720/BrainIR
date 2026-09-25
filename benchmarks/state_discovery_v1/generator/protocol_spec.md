# Protocol specification (shared with the real circuits)

Reference implementation: `reference/protocol.py` (validate, canonical form, hashing). A protocol is a JSON-serialisable
description of ONE trajectory of a physical system:

```
{"system": "<system id>",
 "params_seed": int,                                # draw of the system's own parameters
 "weight_noise": {"sd": float, "seed": int} | null, # structural parameter perturbation, fixed for the whole trajectory
 "r0": {"kind": "zero"} | {"kind": "state", "values": {"<neuron>": value, ...}},
 "t_end": float, "dt": float,                       # duration and output sampling
 "stimulus": [[t_start, value], ...],               # piecewise-constant input; value = scalar (scales the nominal input
                                                    #   pattern) or a list of length input_dim
 "events": [event, ...]}
```

Events (times snapped to the output grid; neurons named by id = column of x in 0..N-1 for synthetic systems):

```
{"kind": "kick", "t": t, "delta": {"<neuron>": d}}                   instantaneous state offset
{"kind": "current", "t0": a, "t1": b, "targets": {"<neuron>": I}}    extra input current into neurons during [a, b)
{"kind": "silence", "t0": a, "t1": b | null, "targets": [neurons]}   remove the neurons during [a, b)
{"kind": "edge_remove", "t0": a, "t1": b | null, "edges": [[post, pre], ...]}
```

Recording convention: the sample at a kick's time is the PRE-kick state; the kick acts immediately after it, so the jump appears
between t and t + dt.

Synthetic systems additionally accept the evaluator-only latent events described in CONTRACT.md section 3
(`latent_set`, `latent_impulse`). `reference/protocol.py` validates only the four microscopic kinds; extend validation in your
own package for the latent kinds.
