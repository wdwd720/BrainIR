"""Clean-room method file for registered BrainIR discovery methods (the file given to the frozen clean-room runner).

    uv run python benchmarks/dng100/cleanroom/run_method.py --method scripts/cleanroom_entry/brainir_discovery_entry.py \
        --bundle benchmarks/dng100/public_blind --out <dir> --network manc_v1.2.1 --seed 0 \
        --method-args "--method brainir_v1 --budget 1000"

It only forwards to `brainir.discovery.run`, which reads BRAINIR_BUNDLE / BRAINIR_NETWORK / BRAINIR_OUT / BRAINIR_SEED as set by
the runner. It lives alone in this directory because the clean-room sandbox makes the method file's directory readable.
"""

import sys

from brainir.discovery.run import main

if __name__ == "__main__":
    sys.exit(main())
