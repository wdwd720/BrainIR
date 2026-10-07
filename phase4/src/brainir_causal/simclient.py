"""Client of the budgeted simulation service (the only simulator access inside a Phase 4 room).

    from brainir_causal.simclient import SimClient
    out = SimClient().run([protocol, ...])     # list of {"ok", "error", "t", "x", "u", "y", "key", "family"}
    SimClient().budget()                       # {"budget", "used", "ledger"} after the last request
    SimClient().ledger()                       # your own ledger, fetched from the service

Protocols follow `brainir_causal.protocol` (format p4-protocol-1). The service accepts only PUBLIC development protocols of the
system (its split record's families_train on its public targets and edges, within the development ranges of its capability
record, public seeds, the public input range, the nominal dt; see docs/PROTOCOL_V2.md) and charges each accepted trajectory to your
budget. It returns the observed quantities only (x, u, y). `key` is the trajectory's key; you may restart from any trajectory of the
SAME system you were served or any public trajectory with r0 = {"kind": "restart", "key": key, "t": t} (t a sample time of it).

Identity: the service knows you by the secret token that the sandbox passes into your container as the environment variable
P4_SIM_TOKEN (or `token=`). The token is valid only through your own queue (simq/<your scratch name>/); the `agent` argument is a
label only. Every request is charged to the token's identity and budget.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import numpy as np

TOKEN_ENV = "P4_SIM_TOKEN"


def default_queue() -> Path:
    """Your own queue: <room>/simq/<scratch> (the sandbox shows you only that subdirectory of simq/; the launcher sets
    P4_AGENT_SCRATCH), or <room>/simq without a scratch name."""
    root = Path("/room") if os.environ.get("P4_SANDBOX") == "1" else Path(os.environ.get("P4_CLEAN_ROOT") or Path.cwd())
    scratch = os.environ.get("P4_AGENT_SCRATCH")
    return root / "simq" / scratch if scratch else root / "simq"


class SimClient:
    def __init__(self, queue: Path | str | None = None, agent: str | None = None, token: str | None = None):
        self.q = Path(queue) if queue else default_queue()
        self.agent = agent or os.environ.get("P4_AGENT_NAME", "unknown")          # a label (services without a token table)
        self.token = token if token is not None else os.environ.get(TOKEN_ENV)
        self.last_meta: dict = {}

    def _request(self, body: dict, timeout: float, poll: float) -> tuple[dict, dict]:
        rid = uuid.uuid4().hex
        req = self.q / "requests" / f"{rid}.json"
        req.parent.mkdir(parents=True, exist_ok=True)
        tmp = req.with_suffix(".json.tmp")
        payload = {"agent": self.agent, **body}
        if self.token:
            payload["token"] = self.token
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, req)
        res_json = self.q / "results" / f"{rid}.json"
        t0 = time.time()
        while not res_json.exists():
            if time.time() - t0 > timeout:
                raise TimeoutError("the simulation service did not answer (is it running?)")
            time.sleep(poll)
        meta = json.loads(res_json.read_text(encoding="utf-8"))
        arrays = {}
        npz = self.q / "results" / f"{rid}.npz"
        if npz.exists():
            with np.load(npz) as z:
                arrays = {k: z[k] for k in z.files}
        if meta.get("status") == "error":
            raise RuntimeError(meta.get("error"))
        self.last_meta = meta
        return meta, arrays

    def run(self, protocols: list[dict], timeout: float = 7200.0, poll: float = 0.5) -> list[dict]:
        meta, arrays = self._request({"protocols": protocols}, timeout, poll)
        out = []
        for it in meta.get("items", []):
            j = it["i"]
            rec = {"ok": it["ok"], "error": it.get("error"), "key": it.get("key"), "family": it.get("family")}
            if it["ok"]:
                rec.update({k: arrays[f"i{j}_{k}"] for k in ("t", "x", "u", "y")})
            out.append(rec)
        return out

    def budget(self) -> dict:
        return {"budget": self.last_meta.get("budget"), "used": self.last_meta.get("used"), "ledger": self.last_meta.get("ledger")}

    def ledger(self, timeout: float = 600.0, poll: float = 0.2) -> dict:
        """Your own ledger as the SERVICE counts it: {"budget", "used", "ledger"}."""
        meta, _ = self._request({"op": "ledger"}, timeout, poll)
        return {"budget": meta.get("budget"), "used": meta.get("used"), "ledger": meta.get("ledger")}

    def verify_ledger(self, own: dict, fields=("experiments", "trajectories", "units")) -> dict:
        """Compare a loop's own ledger (accounting.Ledger.to_dict()) with the service's ledger of this token (review F, M4): {"ok",
        "service", "own", "mismatch": [field, ...]}. Meaningful when the token belongs to this loop alone."""
        svc = (self.ledger().get("ledger") or {})
        mism = [f for f in fields if svc.get(f) != own.get(f)]
        return {"ok": not mism, "service": {f: svc.get(f) for f in fields}, "own": {f: own.get(f) for f in fields}, "mismatch": mism}
