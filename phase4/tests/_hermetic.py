"""Test infrastructure: a HERMETIC salt for tests that build tiers.

The real Phase 4 salt lives only on the orchestrator host (data/phase4/hidden/salt.txt, git-ignored, never uploaded). Tests that
build a toy tier reach the salted code paths (e.g. the salted seeds of a non-public pool's intervention sequences, `pool_seq_seed_of`),
which read the salt through `suites.read_salt()`. That function reads the module globals `SALT_FILE` and `COMMITMENT` at call time,
so pointing them at a temporary test salt and its commitment runs exactly the same code on any machine (the sharded Modal runner
included): the same functions, the same HMAC derivations, only other seed values. The salted reads happen in the building process
(workers only simulate specs whose seeds are already set), so patching the parent's globals covers them on every start method.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path

from brainir_causal import suites as S

#: a fixed, public, test-only salt (64 hex characters like the real one); never the real salt
TEST_SALT = hashlib.sha256(b"brainir-p4-test-salt").hexdigest()


@contextmanager
def hermetic_salt(directory: Path):
    """Point suites' SALT_FILE / COMMITMENT at a test salt and its sha256 commitment in `directory` for the duration of the block."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    sf, cf = directory / "salt.txt", directory / "salt_commitment.json"
    sf.write_text(TEST_SALT + "\n", encoding="utf-8")
    cf.write_text(json.dumps({"sha256_of_salt": hashlib.sha256(TEST_SALT.encode()).hexdigest()}), encoding="utf-8")
    saved = (S.SALT_FILE, S.COMMITMENT)
    S.SALT_FILE, S.COMMITMENT = sf, cf
    try:
        yield TEST_SALT
    finally:
        S.SALT_FILE, S.COMMITMENT = saved
