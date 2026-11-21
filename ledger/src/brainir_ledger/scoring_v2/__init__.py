"""Scoring v2 (run 2, PREREG v2 Part S). New code on top of the frozen v1 scoring package `brainir_ledger.scoring`, which is
imported and never edited. Entry point: `pipeline_v2.run(name, research_dir, flags_file)`; it refuses (the frozen `BlindError`)
unless the flag file exists and lists the run with its two locks, the gate's run-2 report holds all conditions, the scoring lock
passes `lock2.check`, and (for S-a, S-b, S-c) run P has ended."""
