"""Post-lock Modal runs (LOG L145): `modal4.run` unchanged, with the spend cap raised to the user's latest authorisation.

`modal4.py` is hashed by LOCK_reliability_v2 and is never amended after that lock, so the cap is set here: $15 (user, 2026-11-21) +
$14 (user, 2026-11-22 ~09:55 PST; amendment 7) + $12 (user, 2026-11-22 ~13:40 PST: "u can use another 12$ of modal") = $41. Everything
else (trust gate, estimate refused before spending, spend log) is `modal4.run`'s.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/modal4b_v4.py CAMPAIGN --s-per-job S [--max-containers N]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import modal4 as M  # noqa: E402

M.CAP_USD = 41.0

if __name__ == "__main__":
    a = sys.argv[1:]
    M.run(a[0], int(a[a.index("--max-containers") + 1]) if "--max-containers" in a else 100, None,
          float(a[a.index("--s-per-job") + 1]))
