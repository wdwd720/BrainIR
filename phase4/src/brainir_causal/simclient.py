"""Client of the budgeted simulation service (the only simulator access inside a Phase 4 room).

    from brainir_causal.simclient import SimClient
    out = SimClient().run([protocol, ...])     # list of {"ok", "error", "t", "x", "u", "y", "key", "cached", "family"}
    SimClient().budget()                       # {"budget", "used", "ledger"} after the last request

Protocols follow `brainir_causal.protocol` (format p4-protocol-1). The service accepts only PUBLIC development protocols of the
system (its split record's families_train on its public targets and edges, within the development ranges of its capability
record, public seeds, the public input range; see docs/PROTOCOL_V2.md) and charges each accepted trajectory to your budget. It
returns the observed quantities only (x, u, y). `key` is the trajectory's content key; you may restart from any trajectory you were
served or any public trajectory with r0 = {"kind": "restart", "key": key, "t": t}.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import numpy as np


class SimClient:
    def __init__(self, queue: Path | str | None = None, agent: str | None = None):
        root = Path(os.environ.get("P4_CLEAN_ROOT") or Path.cwd())
        self.q = Path(queue) if queue else root / "simq"
        self.agent = agent or os.environ.get("P4_AGENT_NAME", "unknown")
        self.last_meta: dict = {}

    def run(self, protocols: list[dict], timeout: float = 7200.0, poll: float = 0.5) -> list[dict]:
        rid = uuid.uuid4().hex
        req = self.q / "requests" / f"{rid}.json"
        req.parent.mkdir(parents=True, exist_ok=True)
        tmp = req.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"agent": self.agent, "protocols": protocols}), encoding="utf-8")
        os.replace(tmp, req)
        res_json = self.q / "results" / f"{rid}.json"
        t0 = time.time()
        while not res_json.exists():
            if time.time() - t0 > timeout:
                raise TimeoutError("the simulation service did not answer (is it running?)")
            time.sleep(poll)
        meta = json.loads(res_json.read_text(encoding="utf-8"))
        self.last_meta = meta
        arrays = {}
        npz = self.q / "results" / f"{rid}.npz"
        if npz.exists():
            with np.load(npz) as z:
                arrays = {k: z[k] for k in z.files}
        if meta.get("status") == "error":
            raise RuntimeError(meta.get("error"))
        out = []
        for it in meta.get("items", []):
            j = it["i"]
            rec = {"ok": it["ok"], "error": it.get("error"), "key": it.get("key"), "cached": it.get("cached"), "family": it.get("family")}
            if it["ok"]:
                rec.update({k: arrays[f"i{j}_{k}"] for k in ("t", "x", "u", "y")})
            out.append(rec)
        return out

    def budget(self) -> dict:
        return {"budget": self.last_meta.get("budget"), "used": self.last_meta.get("used"), "ledger": self.last_meta.get("ledger")}
