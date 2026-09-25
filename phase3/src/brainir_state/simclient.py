"""Client of the budgeted simulation service (the only simulator access inside the clean room).

    from brainir_state.simclient import SimClient
    out = SimClient().run([protocol, ...])      # list of {"ok", "error", "t", "x", "u", "y", "key", "cached"}

Protocols follow brainir_state.protocol. The service accepts only PUBLIC development protocols (see the benchmark PROTOCOL.md:
public systems, public seed range, public stimulus range, kicks / current pulses / single silencing on public target neurons) and
charges each accepted trajectory to your agent's budget. `budget()` reports usage.
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
        root = Path(os.environ.get("P3_CLEAN_ROOT") or Path(__file__).resolve().parents[2])
        self.q = Path(queue) if queue else root / "simq"
        self.agent = agent or os.environ.get("P3_AGENT_NAME", "unknown")
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
        out = []
        for it in meta.get("items", []):
            j = it["i"]
            rec = {"ok": it["ok"], "error": it.get("error"), "key": it.get("key"), "cached": it.get("cached")}
            if it["ok"]:
                rec.update({k: arrays[f"i{j}_{k}"] for k in ("t", "x", "u", "y")})
            out.append(rec)
        if meta.get("status") == "error":
            raise RuntimeError(meta.get("error"))
        return out

    def budget(self) -> dict:
        return {"budget": self.last_meta.get("budget"), "used": self.last_meta.get("used")}
