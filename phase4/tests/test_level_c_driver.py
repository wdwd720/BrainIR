"""Level C driver (scripts/p4/level_c.py, levelc_lib.py, levelc_remote.py): guards, the job graph, the executor with a fake backend,
the projection, and the stand-in's dimension rule. No Modal call, no hidden data (the lock is absent in the development repository)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p4"))

import levelc_lib as L  # noqa: E402
import levelc_remote as R  # noqa: E402


@pytest.fixture(autouse=True)
def _hermetic_git(monkeypatch):
    """Test infrastructure: the ledger and the guard read git through `levelc_lib._git`. These tests check the driver's rules, not
    git (no test here reaches a real lock tag), so git is replaced by a fixed answer on every machine: `rev-parse HEAD` returns a
    fixed commit and every other query "not found". The sharded Modal runner has neither git nor the repository's .git."""
    import subprocess

    def fake_git(*args: str) -> subprocess.CompletedProcess:
        if args and args[0] == "rev-parse" and args[-1] == "HEAD":
            return subprocess.CompletedProcess(["git", *args], 0, stdout="0" * 40 + "\n", stderr="")
        return subprocess.CompletedProcess(["git", *args], 1, stdout="", stderr="fake git (tests): not found")
    monkeypatch.setattr(L, "_git", fake_git)


# ================================================================================================================ guards
def test_official_guard_refuses_without_lock(monkeypatch, tmp_path):
    monkeypatch.setattr(L, "METHOD_LOCK", tmp_path / "METHOD_LOCK.json")
    with pytest.raises(L.LevelCRefused, match="no method lock"):
        L.official_guard()
    with pytest.raises(L.LevelCRefused):
        L.system_specs(L.Mode.official())


def test_hidden_tiers_refuse_to_plan_before_the_lock(monkeypatch, tmp_path):
    from brainir_causal import suites as SU
    monkeypatch.setattr(SU, "METHOD_LOCK", tmp_path / "METHOD_LOCK.json")
    with pytest.raises(PermissionError, match="after the method lock"):
        SU.plan_remote_job("synthetic", "syn-x", tier="conf")
    with pytest.raises(PermissionError, match="after the method lock"):
        SU.plan_remote_job("real", "real:A:full", level="C")


def test_dry_payload_audit():
    ok = {"job": {"heldout_root": "/evalvol/data/suites", "heldout_tier": "dev", "internal_path": "/evalvol/data/suites/dev/internal_records.json",
                  "real": "/fitvol/data/real/real_public/public/real_A_full"}, "model": b"\x00\x01"}
    L.assert_dry_payloads([ok])
    L.assert_dry_payloads([{"args": [{"parts": [{"specs": [{"split": "val", "role": "d1"}]}], "tier": "toyC"}]}])   # the 'val' SPLIT is fine
    for bad in ({"job": {"heldout_tier": "conf"}}, {"job": {"p": "/evalvol/data/suites/conf/eval/x"}},
                {"job": {"heldout_tier": "real_levelc"}}, {"job": {"p": "/evalvol/data/real/real_levelb/eval"}}, {"args": ["the salt"]}):
        with pytest.raises(L.LevelCRefused):
            L.assert_dry_payloads([bad])


def test_ledger_allows_resume_and_refuses_a_second_run(tmp_path, monkeypatch):
    led = tmp_path / "LEDGER.json"
    a = L.ledger_claim("C1", "levelc_run", ledger=led)
    assert L.ledger_claim("C1", "levelc_run", ledger=led) == a                       # the same run id resumes
    with pytest.raises(L.LevelCRefused, match="already ran"):
        L.ledger_claim("C2", "levelc_run", ledger=led)
    rec = L.ledger_claim("C2", "levelc_run", new_run_reason="infrastructure: the first run's app was killed", ledger=led)
    assert rec["reason"].startswith("infrastructure")
    assert L.ledger_claim("C1", "levelc_claims", ledger=led)["stage"] == "levelc_claims"


def test_hidden_log_rows(tmp_path):
    log = tmp_path / "HIDDEN_EVALUATIONS.md"
    L.log_hidden("START", "C1", "Level C run", {"a": 1}, log=log)
    L.log_hidden("DONE", "C1", "Level C run", {"wall_s": 3.0, "x": "a|b"}, log=log)
    rows = [x for x in log.read_text(encoding="utf-8").splitlines() if x.startswith("| 20")]
    assert [r.split(" | ")[1] for r in rows] == ["START", "DONE"]
    assert "a/b" in rows[1]                                                           # table separators escaped


# ================================================================================================================ the job graph
def _spec(sid, kind="synthetic", cls="syn", **kw):
    base = {"sid": sid, "kind": kind, "cls": cls, "tier": "dev", "fit_data": f"/fitvol/data/suites/dev/public/{sid}", "public_root": "/fitvol/data/suites",
            "public_tier": "dev", "heldout_root": "/evalvol/data/suites", "heldout_tier": "dev", "part": "eval",
            "internal_path": "/evalvol/data/suites/dev/internal_records.json", "generator": None, "type": 1, "trap": None, "k_true": 2,
            "d_draw": 0, "compressible": True, "group": None, "group_members": [], "unrelated": [], "families_train": ["obs.nominal", "kick.1", "pulse.1"],
            "n_obs": 20, "lineage": None}
    base.update(kw)
    return base


def _plan(**kw):
    specs = {"syn-a": _spec("syn-a", group="g1", group_members=["syn-b"], unrelated=["syn-c"]),
             "syn-b": _spec("syn-b", group="g1", group_members=["syn-a"], unrelated=["syn-c"]),
             "syn-c": _spec("syn-c", compressible=None, k_true="none", type=20),
             "real:A:full": _spec("real:A:full", kind="real", cls="full", compressible=None, k_true=None, lineage="A", families_train=["kick.1", "sil.1"]),
             "real:A:m1": _spec("real:A:m1", kind="real", cls="mech", compressible=None, k_true=None, lineage="A", families_train=["kick.1"])}
    described = {"M": {"device": "cpu", "has_designer": True, "supported_sharing": ["auto", "independent", "shared"], "supports_adaptation": True},
                 "S": {"device": "cpu", "has_designer": False, "supported_sharing": ["auto", "independent"], "supports_adaptation": False}}
    p = L.Plan(run_id="T", mode=L.Mode.dry(toy=False), specs=specs, method="M", limpo_method="M", baselines=["S"], fixed={}, described=described,
               **kw)
    return L.build_plan(p)


def test_plan_structure():
    p = _plan()
    J = p.jobs
    by = {}
    for j in J.values():
        by[j.stage] = by.get(j.stage, 0) + 1
    n = len(p.specs)
    assert by["fit"] == 5 * n and by["refit"] == 5 * n and by["eval"] == n and by["refs"] == n and by["stability"] == n
    assert by["bfit"] == n and by["beval"] == n
    assert by["calib"] == 2                                                           # compressible synthetic systems only
    assert by["loio_fit"] == 2 + 2 + 2 + 2 + 1 and by["loio_eval"] == by["loio_fit"]   # trained intervention families (obs.* excluded)
    assert by["loop"] == n * len(L.DESIGNERS) * len(L.LOOP_SEEDS)
    # 5.14: the group (2 held-out implementations) and its unrelated-pair null (syn-a with syn-c)
    kinds = sorted(g["kind"] for g in p.groups)
    assert kinds == ["group", "null"]
    assert by["limpo_shared"] == 4 and by["limpo_adapt"] == 4 and by["limpo_scratch"] == 4 and by["limpo_eval"] == 4
    assert by["share_fit"] == 2 and by["share_eval"] == 4                             # model B (shared) per unit; A = the per-system fits
    # dependencies
    assert J["eval__syn-a"].deps == ["fit__syn-a__s0"]
    assert J["loop__syn-a__random_matched__l1"].deps == ["loop__syn-a__own__l1"]
    assert J["loop__real_A_full__own__l0"].meta["budget"] == L.BUDGET_FULL and J["loop__real_A_m1__own__l0"].meta["budget"] == L.BUDGET
    assert set(J["stability__syn-a"].soft) == {f"fit__syn-a__s{s}" for s in range(5)} | {f"refit__syn-a__b{b}" for b in range(5)}
    assert J["limpo_adapt__grp_g1__syn-a"].deps == ["limpo_shared__grp_g1__syn-a"]
    assert J["limpo_shared__grp_g1__syn-a"].meta["systems"] == ["syn-b"]


def test_build_barrier_on_packed_classes(tmp_path):
    """Packed containers reload the volumes once, at their start (P1's freshness rule): with packed classes every job waits for EVERY
    build; unpacked jobs reload per job and wait only for their own system's build."""
    packed = _plan(build_jobs={"syn-a": {}, "syn-b": {}})
    assert packed.jobs["fit__syn-c__s0"].deps == ["build__syn-a", "build__syn-b"]
    assert packed.jobs["refs__syn-a"].deps == ["build__syn-a", "build__syn-b"]
    unpacked = _plan(build_jobs={"syn-a": {}, "syn-b": {}}, class_map=dict(L.UNPACKED))
    assert unpacked.jobs["fit__syn-c__s0"].deps == [] and unpacked.jobs["fit__syn-a__s0"].deps == ["build__syn-a"]
    assert unpacked.jobs["fit__syn-a__s0"].cls == "iso_fit_s" and unpacked.jobs["loop__syn-a__own__l0"].cls == "iso_loop"
    # packed jobs never commit a volume (P1's rule 1): the references' cache stays in the container
    p = L.payload_for(unpacked.jobs["refs__syn-a"], unpacked, L.RunStore(tmp_path / "store"))
    assert "commit" not in p and p["args"][0]["ref_cache"].startswith("/tmp/")


def test_plan_without_adaptation_or_designer():
    p = _plan()
    p.described["M"] = {"device": "cuda", "has_designer": False, "supported_sharing": ["auto", "independent"], "supports_adaptation": False}
    L.build_plan(p)
    stages = {j.stage for j in p.jobs.values()}
    assert "limpo_shared" not in stages and "limpo_adapt" not in stages and "share_fit" not in stages
    assert "limpo_scratch" in stages                                                  # the scratch fits still run (transfer untestable)
    assert not any(j.meta.get("designer") in ("own", "random_matched") for j in p.jobs.values() if j.stage == "loop")
    assert p.jobs["fit__syn-a__s0"].cls == L.GPU_PACKED                               # a CUDA method fits on the packed GPU class


class FakeFn:
    """A Modal function: `remote(p)` / `await remote.aio(p)` (the executor's synchronous invocations)."""

    def __init__(self, be, cls):
        self.be, self.cls = be, cls
        self.remote = _FakeRemote(self)

    def result(self, p):
        self.be.calls.append((self.cls, p.get("role") or p.get("kind"), p.get("__tag")))
        tag = p.get("__tag")
        if tag in self.be.refuse_once:                       # a host-gate refusal, re-submitted by the executor
            self.be.refuse_once.discard(tag)
            return {"__refused__": True}
        if self.be.stale.get(tag, 0) > 0:                    # a warm packed container that cannot see a staged input (P1)
            self.be.stale[tag] -= 1
            return {"__refused__": True, "stale_staging": ["0123456789abcdef"]}
        if tag in self.be.infra_once:                        # an infrastructure failure (retried and recorded)
            self.be.infra_once.discard(tag)
            raise RuntimeError("call failed repeatedly on Modal")
        return self.be._res(p)


class _FakeRemote:
    def __init__(self, fn):
        self.fn = fn

    def __call__(self, p):
        return self.fn.result(p)

    async def aio(self, p):
        return self.fn.result(p)


class FakeBackend:
    """Returns synthetic results for every job kind (no Modal): `fns[cls].spawn(payload).get(timeout=0)`."""

    def __init__(self, fail: set[str] | None = None, refuse_once: set[str] | None = None, infra_once: set[str] | None = None,
                 stale: dict | None = None):
        import collections
        self.stale = dict(stale or {})
        self.calls = []
        self.fail = fail or set()
        self.refuse_once = set(refuse_once or ())
        self.infra_once = set(infra_once or ())
        self.fns = collections.defaultdict(lambda: None)
        self.fns = _Fns(self)

    def _res(self, p):
        role = p.get("role")
        if role in ("fit",) or p.get("target", "").endswith(":fit_records"):
            j = p["job"]
            if j["method"] in self.fail:
                return {"error": "RuntimeError: planned failure"}
            body = {"model": b"MODEL", "side": {"info": {"k": {s: 2 for s in j["systems"]}}}}
            return body if role == "fit" else {"result": body, "iso": {}}
        if role == "loop":
            cps = p["job"]["checkpoints"]
            return {"loop_record": {"checkpoints": [{"budget": b, "ledger": {}} for b in cps]},
                    "files": {**{f"ckpt_{b:04d}.pkl": b"CK" for b in cps}, "experiments.jsonl": b"{}\n", "loop_record.json": b"{}"}}
        if role == "eval":
            return {"result": {"sid": p["job"]["sid"], "kind": "synthetic", "result": {"items": {}}}}
        if role == "call":
            return {"result": {"sid": p["job"].get("sid"), "models": {}}}
        return {"result": {"sid": (p.get("args") or [{}])[0].get("sid"), "results": {}}}


class _Fns(dict):
    def __init__(self, be):
        super().__init__()
        self.be = be

    def __missing__(self, cls):
        self[cls] = FakeFn(self.be, cls)
        return self[cls]


def test_executor_runs_the_whole_graph_and_resumes(tmp_path, monkeypatch):
    p = _plan()
    p.methods_key = "k"
    store = L.RunStore(tmp_path / "run")
    be = FakeBackend(fail={"S"})
    ex = L.Executor(be, p, store, caps={c: 4 for c in set(L.CLASS_OF.values()) | {L.GPU_PACKED}}, dry=True, progress_s=1e9)
    status = ex.run()
    ckpts = [j for j in p.jobs.values() if j.stage == "ckpt"]
    n_loops = sum(1 for j in p.jobs.values() if j.stage == "loop")
    assert len(ckpts) >= n_loops * 4                                                 # one evaluation per checkpoint of every loop
    assert all(status[j.id] == "ok" for j in ckpts)
    assert status["bfit__syn-a__S"] == "error" and status["beval__syn-a__S"] == "skipped"    # a failed fit blocks its evaluation only
    assert status["eval__syn-a"] == "ok" and status["stability__syn-a"] == "ok"
    assert store.model("fit__syn-a__s0") == b"MODEL" and store.model(ckpts[0].id) == b"CK"
    assert (store.dir / "loops" / "loop__syn-a__own__l0" / "experiments.jsonl").exists()
    n_calls = len(be.calls)
    # a restart finds every finished job (and the checkpoint jobs of the finished loops) and submits nothing
    p2 = _plan()
    p2.methods_key = "k"
    be2 = FakeBackend()
    ex2 = L.Executor(be2, p2, store, caps={c: 4 for c in set(L.CLASS_OF.values()) | {L.GPU_PACKED}}, dry=True, progress_s=1e9)
    ex2.run()
    assert not be2.calls, be2.calls[:5]
    assert n_calls > 0


def test_refusals_and_infrastructure_failures_are_retried(tmp_path):
    p = _plan()
    p.methods_key = "k"
    store = L.RunStore(tmp_path / "run")
    be = FakeBackend(refuse_once={"fit__syn-a__s0"}, infra_once={"eval__syn-a"})
    ex = L.Executor(be, p, store, caps={c: 8 for c in set(L.CLASS_OF.values()) | {L.GPU_PACKED}}, dry=True, progress_s=1e9, idle_s=0.0)
    status = ex.run()
    assert status["fit__syn-a__s0"] == "ok" and status["eval__syn-a"] == "ok"
    rows = {r["id"]: r for r in store.rows() if r.get("status") == "ok"}
    assert rows["fit__syn-a__s0"]["refusals"] == 1 and rows["eval__syn-a"]["attempts"] == 2
    assert "call failed repeatedly" in str(store.get("eval__syn-a").get("infrastructure_retries"))
    assert sum(1 for c in be.calls if c[2] == "eval__syn-a") == 2


def test_stale_staging_refusals_are_resubmitted_and_bounded(tmp_path):
    from brainir_causal.p4modal.app import MAX_STALE
    p = _plan()
    p.methods_key = "k"
    store = L.RunStore(tmp_path / "run")
    be = FakeBackend(stale={"eval__syn-a": 2, "eval__syn-b": MAX_STALE + 1})
    ex = L.Executor(be, p, store, caps={c: 8 for c in set(L.CLASS_OF.values()) | {L.GPU_PACKED}}, dry=True, progress_s=1e9, idle_s=0.0)
    status = ex.run()
    rows = {r["id"]: r for r in store.rows() if r.get("stage") == "eval"}
    assert status["eval__syn-a"] == "ok" and rows["eval__syn-a"]["stale_refusals"] == 2
    assert status["eval__syn-b"] == "error" and "not visible after" in rows["eval__syn-b"]["error"]
    assert sum(1 for c in be.calls if c[2] == "eval__syn-b") == MAX_STALE + 1


def test_call_payloads_list_their_staged_inputs(tmp_path):
    import hashlib

    class StageBE:
        def stage_put(self, data):
            return {"stage": hashlib.sha256(data).hexdigest(), "size": len(data), "vol": "store"}
    p = _plan()
    store = L.RunStore(tmp_path / "run")
    store.be = StageBE()
    for x in range(5):
        L.collect(p.jobs[f"fit__syn-a__s{x}"], {"model": b"m" * (600 * 1024), "side": {}}, p, store)
    st = L.payload_for(p.jobs["stability__syn-a"], p, store)
    assert len(st["input_refs"]) == 5 and all(r in st["input_refs"] for r in st["models"].values())


def test_staged_artefacts_are_fetched_and_passed_as_refs(tmp_path):
    """P1's volume staging (block_network: nothing above 2 MiB inline): a staged fit model is fetched and later payloads carry its ref;
    a staged evaluation record is unpickled; staged loop files are fetched; too-large inline model sets travel as refs."""
    import hashlib
    import pickle

    class StageBE:
        def __init__(self):
            self.blobs = {}

        def stage_put(self, data):
            sha = hashlib.sha256(data).hexdigest()
            self.blobs[sha] = data
            return {"stage": sha, "size": len(data), "vol": "store"}

        def stage_get(self, ref):
            return self.blobs[ref["stage"]]

    be = StageBE()
    p = _plan()
    store = L.RunStore(tmp_path / "run")
    store.be = be
    big = b"M" * (3 * 1024 * 1024)
    ref = be.stage_put(big)
    L.collect(p.jobs["fit__syn-a__s0"], {"model_ref": ref, "side": {"info": {"k": {"syn-a": 2}}}}, p, store)
    assert store.model("fit__syn-a__s0") == big and store.ref("fit__syn-a__s0") == ref
    ev = L.payload_for(p.jobs["eval__syn-a"], p, store)
    assert ev["model_ref"] == ref and "model" not in ev                               # the ref travels, not the bytes
    rec = {"sid": "syn-a", "kind": "synthetic", "result": {"items": {}}}
    L.collect(p.jobs["eval__syn-a"], {"result_ref": be.stage_put(pickle.dumps(rec))}, p, store)
    assert store.get("eval__syn-a")["result"] == rec
    ck = b"C" * (2 * 1024 * 1024)
    lres = {"loop_record": {"checkpoints": [{"budget": 10}]}, "files": {"experiments.jsonl": b"{}\n"},
            "file_refs": {"ckpt_0010.pkl": be.stage_put(ck)}}
    new = L.collect(p.jobs["loop__syn-a__own__l0"], lres, p, store)
    assert [j.id for j in new] == ["ckpt__syn-a__own__l0__b10"] and store.model(new[0].id) == ck and store.ref(new[0].id)
    # a call job whose models together exceed the inline limit: every model becomes a ref
    for x in range(1, 5):
        L.collect(p.jobs[f"fit__syn-a__s{x}"], {"model": b"m" * (600 * 1024), "side": {}}, p, store)
    st = L.payload_for(p.jobs["stability__syn-a"], p, store)
    assert all(isinstance(v, dict) and "stage" in v for v in st["models"].values()) and len(st["models"]) == 5
    small = _plan()
    s2 = L.RunStore(tmp_path / "run2")
    s2.be = be
    L.collect(small.jobs["fit__syn-b__s0"], {"model": b"x" * 1000, "side": {}}, small, s2)
    assert L.payload_for(small.jobs["eval__syn-b"], small, s2)["model"] == b"x" * 1000        # small models stay inline


def test_loop_rows_charge_failed_loops(tmp_path):
    p = _plan()
    store = L.RunStore(tmp_path / "run")
    rows = L.loop_rows(p, store)                                                       # nothing ran: every planned checkpoint charged
    assert rows and all(np.isnan(r["EE"]) and r.get("loop_failed") for r in rows)
    full = [r for r in rows if r["system"] == "real:A:full"]
    assert max(r["budget"] for r in full) == L.BUDGET_FULL


def test_fixed_from_levelb_gives_numbers(tmp_path, monkeypatch):
    """LEVEL_B_FIXED.json from a final Level B round: the suite-level bound / comparator, the real systems' own choices, S and delta_NI
    = 0.2 x S's median seed-averaged EE on the round's synthetic systems, a NUMBER (PROTOCOL 11)."""
    monkeypatch.setattr(L, "METHOD_LOCK", tmp_path / "no_lock.json")
    rd = tmp_path / "r4"
    rd.mkdir()
    (rd / "BOUNDS.json").write_text(json.dumps({"full_state": {"s1": "ref:full_state", "s2": "baseline:linear_fullstate", "s3": "ref:full_state",
                                                               "real:A:full": "baseline:linear_fullstate"},
                                                "id_shortcut": {"s1": "ref:id_shortcut", "s2": "ref:id_shortcut", "s3": "ref:id_shortcut",
                                                                "real:A:full": "ref:id_shortcut"}}), encoding="utf-8")
    (rd / "DECISION.json").write_text(json.dumps({"order": ["m1", "base_b", "base_a"]}), encoding="utf-8")
    (rd / "ROUND.json").write_text(json.dumps({"round": "r4", "baselines": ["base_a", "base_b"]}), encoding="utf-8")

    def row(ee):
        return {"seeds": {"0": {"verdict": {"metrics": {"EE": {"point": ee}}}}, "1": {"verdict": {"metrics": {"EE": {"point": ee + 0.1}}}}}}
    (rd / "base_b.json").write_text(json.dumps({"per_system": {"s1": {**row(0.5), "kind": "synthetic"}, "s2": {**row(0.7), "kind": "synthetic"},
                                                              "s3": {**row(0.9), "kind": "synthetic"}, "real:A:full": {**row(0.2), "kind": "real"}}}),
                                    encoding="utf-8")
    f = L.fixed_from_levelb(rd)
    assert f["strongest_baseline"] == "base_b"                                        # the best baseline of the decision order
    assert f["full_state_bound"]["default"] == "ref:full_state" and f["full_state_bound"]["per_system"] == {"real:A:full": "baseline:linear_fullstate"}
    assert isinstance(f["delta_NI"], float) and abs(f["delta_NI"] - 0.2 * 0.75) < 1e-9
    assert f["source"]["n_synthetic"] == 3


def test_self_audit_config_roles_and_summaries(tmp_path, monkeypatch):
    """SELF_AUDIT_CONFIG.json (before the lock) names Level C sources for every role; its baseline roles become baselines of the Level C
    run; Stage D's loops / sharing summaries have the shapes self_audit_p4 Q10 / Q18 read."""
    monkeypatch.setattr(L, "LEVEL_B_FIXED", tmp_path / "LEVEL_B_FIXED.json")
    fixed = {"strongest_baseline": "bl_linear", "delta_NI": 0.1}
    cfg = L.self_audit_config(method="li.ssm:li_ssm", fixed=fixed, run_id="C1",
                              roles={"id_baseline": "bl_id", "input_only": "bl_input", "readout_history": "bl_readout",
                                     "linear_controlled": "bl_linear"})
    r = cfg["roles"]
    assert r["method"] == "method" and r["id_reference"] == "ref:id_shortcut" and r["full_state_bound"] == "fixed:full_state_bound"
    assert r["phase3"] == f"baseline:{L.FROZEN_V1}" and r["strongest_baseline"] == "baseline:bl_linear"
    assert set(L.role_baselines(cfg)) == {"bl_id", "bl_input", "bl_readout", "bl_linear", L.FROZEN_V1}
    assert cfg["levelc_run"].endswith("C1") and cfg["loops_summary"].endswith("C1/LOOPS_SUMMARY.json")
    active = {"confirmation_suite": {"active_success": {"success": True, "alpha": 0.025, "matched_control": {
        "designer": "random_matched", "fixed_budget": {"per_budget": {10: {"random_matched": {"upper_bound": -0.1, "diff": -0.2}}}}}}}}
    ls = L.loops_summary(active)
    assert ls["active_design_succeeds"] is True and ls["budgets"]["10"]["own_vs_random_matched"]["upper95"] == -0.1
    limpo = {"grp_g": {"kind": "group", "members": ["a", "b"], "sharing": {"models": {"B": {"verdict": "supported"}}}, "transfer": []},
             "null_g": {"kind": "null", "members": ["a", "c"], "sharing": {"models": {"B": {"verdict": "rejected"}}}, "transfer": []}}
    sh = L.sharing_summary(limpo)
    rows = {x["unit"]: x for x in sh["pairs"]}
    assert rows["null_g"]["related"] is False and rows["null_g"]["rejected"] is True
    assert rows["grp_g"]["related"] is True and rows["grp_g"]["shared"] is True


# ================================================================================================================ small pieces
def test_simulate_makespan_longest_first():
    dur = {"a": 10.0, "b": 5.0, "c": 5.0, "d": 1.0}
    deps = {"d": ["a"]}
    cls = {k: "x" for k in dur}
    r = L.simulate_makespan(dur, deps, {"x": 2}, cls)
    assert r["makespan_s"] == 11.0                                                   # a on one slot then d; b and c on the other
    r1 = L.simulate_makespan(dur, deps, {"x": 1}, cls)
    assert r1["makespan_s"] == 21.0
    r2 = L.simulate_makespan({**dur, "e": 2.0}, {**deps, "e": ["b"]}, {"x": 2}, {**cls, "e": "nope"})
    assert r2["unscheduled"] == 1 and r["unscheduled"] == 0                            # a class without slots never runs


def _makespan_reference(durations, deps, capacity, cls_of):
    """The first (quadratic) implementation of simulate_makespan: one global ready heap re-filled at every event."""
    import heapq
    indeg = {j: 0 for j in durations}
    kids = {j: [] for j in durations}
    for j, ds in deps.items():
        for d in ds:
            indeg[j] += 1
            kids[d].append(j)
    ready = [(-durations[j], j) for j, n in indeg.items() if n == 0]
    heapq.heapify(ready)
    free, running, t, waiting = dict(capacity), [], 0.0, []
    while ready or running or waiting:
        for item in waiting:
            heapq.heappush(ready, item)
        waiting = []
        while ready:
            negd, j = heapq.heappop(ready)
            if free.get(cls_of[j], 0) > 0:
                free[cls_of[j]] -= 1
                heapq.heappush(running, (t + durations[j], j))
            else:
                waiting.append((negd, j))
        if not running:
            break
        t, j = heapq.heappop(running)
        free[cls_of[j]] += 1
        for k in kids[j]:
            indeg[k] -= 1
            if indeg[k] == 0:
                heapq.heappush(ready, (-durations[k], k))
    return round(t, 1)


def test_simulate_makespan_matches_the_reference_schedule():
    rng = np.random.default_rng(3)
    for trial in range(5):
        n = 300
        jobs = [f"j{i:03d}" for i in range(n)]
        dur = {j: float(rng.integers(1, 100)) for j in jobs}
        cls = {j: ("a", "b", "c")[int(rng.integers(0, 3))] for j in jobs}
        deps = {}
        for i, j in enumerate(jobs):
            if i and rng.random() < 0.6:
                deps[j] = sorted({jobs[int(x)] for x in rng.integers(0, i, size=int(rng.integers(1, 4)))})
        cap = {"a": 3, "b": 5, "c": 2}
        assert L.simulate_makespan(dur, deps, cap, cls)["makespan_s"] == _makespan_reference(dur, deps, cap, cls), trial


def test_only_infrastructure_failures_are_retried():
    assert L.infrastructure_error(RuntimeError("call failed repeatedly on Modal"))
    assert L.infrastructure_error({"error": "RuntimeError: container lockdown failed for ['/fitvol: 0o755']; refusing"})
    assert L.infrastructure_error({"error": "FileNotFoundError: [Errno 2] No such file or directory: '/fitvol/methods/ab12.tar'"})
    assert L.infrastructure_error({"error": "ValueError: all input arrays must have the same shape"}) is None      # the job's own failure
    assert L.infrastructure_error({"result": {"sid": "x"}}) is None


def test_the_iso_image_bakes_only_the_remote_module(tmp_path):
    import hashlib
    extra, sha = L.stage_remote_module(tmp_path / "stage")
    (tmp_path / "stage" / "stray.py").write_text("x = 1\n", encoding="utf-8")
    extra, sha2 = L.stage_remote_module(tmp_path / "stage")
    assert sorted(p.name for p in (tmp_path / "stage").iterdir()) == ["levelc_remote.py"]              # nothing else is baked
    assert sha == sha2 == hashlib.sha256((ROOT / "scripts" / "p4" / "levelc_remote.py").read_bytes()).hexdigest()
    assert extra[str(tmp_path / "stage")] == "/repo/scripts/p4"


def test_units_primary():
    eff = {"_units": {"item": ["i1", "i2"], "family": ["kick.1", "sil.1"], "num_medium": [1.0, 2.0], "den_medium": [2.0, 4.0],
                      "num_short": [0.0, 0.0], "den_short": [1.0, 1.0]}}
    u, f = R.units_primary(eff)
    assert u == {"i1": (1.0, 2.0), "i2": (2.0, 4.0)} and f == {"i1": "kick.1", "i2": "sil.1"}


def test_remote_functions_are_iso_targets():
    """Every container-side function resolves through the iso "call" hook's script-module rule (a module file in the script dir)."""
    from brainir_causal import isolation as I
    for fn in R.FUNCTIONS:
        assert callable(getattr(R, fn))
    assert "/repo/scripts/p4" in I.ISO_SCRIPT_DIRS and L.EXTRA_DIRS.get("scripts/p4") == "/repo/scripts/p4"
    with pytest.raises(PermissionError):
        I.resolve_iso_target("brainir_causal.methods.x:fit")


def test_standin_dimension_rule():
    sys.path.insert(0, str(ROOT / "scripts" / "p4" / "levelc_standin" / "methods" / "standin"))
    import pca_standin as P

    class Rec:
        def __init__(self, x):
            self.x = x
    rng = np.random.default_rng(0)
    lat = rng.standard_normal((5000, 2))
    x = lat @ rng.standard_normal((2, 40)) + 0.01 * rng.standard_normal((5000, 40))
    k, cap = P.choose_k([Rec(x)])
    assert cap == 8 and k == 2
    k1, cap1 = P.choose_k([Rec(x[:, :5])])
    assert cap1 == 1 and k1 == 1


# ================================================================================================================ review G's trap tier
def test_trap_tier_constants_agree_with_the_benchmark():
    """The driver's trap-tier names match synthadapter / suites / the method lock, and the container path it bakes the catalog at is
    the path synthadapter resolves inside an image (brainir_causal at /repo/phase4/src)."""
    from pathlib import PurePosixPath

    from brainir_causal import suites as SU
    from brainir_causal import synthadapter as SA
    assert L.TRAP_TIER == SA.TRAP_TIER == "trap" and L.TRAP_CATALOG_REL == SA.TRAP_CATALOG_REL
    assert set(SU.HIDDEN_TIERS) <= set(L.HIDDEN_TIER_NAMES) and L.TRAP_TIER in SU.LOCKED_TIERS
    resolved = PurePosixPath("/repo/phase4/src/brainir_causal/synthadapter.py").parents[3] / SA.TRAP_CATALOG_REL
    assert str(resolved) == f"{L.TRAP_CATALOG_CONTAINER}/{PurePosixPath(L.TRAP_CATALOG_REL).name}"
    import method_lock_p4 as ML
    assert L.TRAP_CATALOG_REL in ML.INPUTS                                             # fixed by the lock before any hidden run


def test_dry_payload_audit_refuses_the_trap_tier():
    for bad in ({"job": {"heldout_tier": "trap"}}, {"job": {"p": "/evalvol/data/suites/trap/eval/syn-x"}}):
        with pytest.raises(L.LevelCRefused):
            L.assert_dry_payloads([bad])


def test_trap_systems_get_the_verdict_stages_only():
    """A trap system: the primary fit, the 5 bootstrap refits, the baselines, the references, the evaluation and the same-items row;
    never 5.11 / 5.13 / 5.17 jobs, never a 5.14 unit or an unrelated-pair null partner."""
    p = _plan()
    p.specs["syn-t"] = _spec("syn-t", set="trap", trap="G-x", group="g1", group_members=["syn-a"])
    p.specs["syn-a"]["unrelated"] = ["syn-t", "syn-c"]
    L.build_plan(p)
    stages = sorted({j.stage for j in p.jobs.values() if j.sid == "syn-t"})
    assert set(stages) <= set(L.TRAP_STAGES) and {"fit", "refit", "eval", "refs", "calib", "bfit", "beval"} <= set(stages)
    assert [j.id for j in p.jobs.values() if j.sid == "syn-t" and j.stage == "fit"] == ["fit__syn-t__s0"]
    assert sum(1 for j in p.jobs.values() if j.sid == "syn-t" and j.stage == "refit") == L.N_REFITS
    assert all("syn-t" not in g["members"] for g in p.groups)
    assert [g["members"] for g in p.groups if g["kind"] == "null"] == [["syn-a", "syn-c"]]
    assert not L.in_suite(p.specs["syn-t"]) and L.in_suite(p.specs["syn-a"]) and L.system_set(p.specs["real:A:full"]) == "real"


def test_trap_outcomes():
    from brainir_causal import verdict as V
    cons = {"k_model": 3, "k_consistent": True, "d_draw": 0}
    assert L.trap_outcome(V.SUPPORTED, 3, cons)[0] == "handled"
    assert L.trap_outcome(V.SUPPORTED, 3, {"k_model": 5, "k_consistent": False, "d_draw": 0})[0] == "fooled"
    assert L.trap_outcome(V.PARTIAL, "none", {})[0] == "fooled"                          # a compact claim where there is none
    assert L.trap_outcome(V.SUPPORTED, None, cons)[0] == "fooled"                         # no k in the truth counts as "none"
    assert L.trap_outcome(V.PARTIAL, 3, cons)[0] == "claim_partial"
    assert L.trap_outcome(V.SUPPORTED, 3, {})[0] == "claim_partial"                       # consistency unknown: never "handled"
    assert L.trap_outcome(V.DECLARED, "none", {})[0] == "declared_correct"
    assert L.trap_outcome(V.DECLARED, 2, {})[0] == "false_alarm"
    assert L.trap_outcome(V.UNSUPPORTED, 2, cons)[0] == "no_claim"
    assert L.trap_outcome(None, 2, cons)[0] == "missing"


def test_category_of_reads_the_assembled_verdict_nesting():
    """A Stage D row holds harness.assemble_verdict(...)["verdict"] = {"metrics", "verdict": {"category", ...}, ...}: the category is
    one level deeper than a bare system verdict (dry run D1 read it one level up and got None for every system and baseline)."""
    from brainir_causal import verdict as V
    row = {"verdict": {"metrics": {"EE": {"point": 0.5}}, "verdict": {"category": V.PARTIAL, "failed": ["B"]}, "bounds": {}}}
    assert L.category_of(row) == V.PARTIAL and L.system_verdict_of(row)["failed"] == ["B"]
    assert L.category_of({"verdict": row["verdict"]}) == V.PARTIAL                    # an assembled verdict (baselines)
    assert L.category_of({"verdict": {"category": V.SUPPORTED}}) == V.SUPPORTED        # a bare system verdict
    assert L.category_of({"verdict": {"error": "no evaluation of the primary fit", "category": None}}) is None
    assert L.category_of({"verdict": {"error": "no result"}}) is None and L.category_of(None) is None


def test_trap_evaluation_is_descriptive_and_charges_missing():
    from brainir_causal import verdict as V
    p = _plan()
    p.specs["syn-t1"] = _spec("syn-t1", set="trap", trap="G-A", k_true=2, expected_verdict="compact causal state, k = 2")
    p.specs["syn-t2"] = _spec("syn-t2", set="trap", trap="G-P", k_true="none", compressible=False)
    p.specs["syn-t3"] = _spec("syn-t3", set="trap", trap="G-A", k_true=2)
    per = {"syn-t1": {"verdict": {"metrics": {}, "verdict": {"category": V.SUPPORTED, "failed": []}},       # the assembled nesting
                      "families": {"truth": {"dimension": {"k_model": 2, "k_consistent": True}, "latent_recovery": {"recovery": 0.9}}},
                      "references": {"true_state": {"EE": 0.2}}, "baselines": {"S": {"category": V.PARTIAL}}},
           "syn-t2": {"verdict": {"category": V.PARTIAL}, "families": {"truth": {"dimension": {"k_model": 3}}}},
           "syn-a": {"verdict": {"category": V.SUPPORTED}}}
    out = L.trap_evaluation(p, per, {"syn-t1": V.SUPPORTED})
    rows = out["per_system"]
    assert sorted(rows) == ["syn-t1", "syn-t2", "syn-t3"]                             # trap systems only
    assert rows["syn-t1"]["outcome"] == "handled" and rows["syn-t1"]["true_state_category_same_items"] == V.SUPPORTED
    assert rows["syn-t2"]["outcome"] == "fooled" and rows["syn-t3"]["outcome"] == "missing"
    s = out["summary"]
    assert s["n_traps"] == 3 and s["counts"]["fooled"] == 1 and s["missing_systems"] == ["syn-t3"]
    assert s["by_label"]["G-A"] == {"handled": 1, "missing": 1} and abs(s["fooled_fraction"] - 1 / 3) < 1e-12


def test_system_specs_trap_sets(monkeypatch):
    """Official: review G's tier joins as set "trap" (ids must not clash with the confirmation tier's); dry: --trap-standins marks dev
    systems (and is refused outside a dry run)."""
    conf = ({"syn-c1": {"split": {"families_train": ["kick.1"]}, "observed": list(range(10))}}, {"syn-c1": {"k": 2, "type": 1}})
    trap = ({"syn-g1": {"split": {"families_train": ["kick.1"]}, "observed": list(range(10))}},
            {"syn-g1": {"k": "none", "type": 21, "trap": "G-P", "expected_verdict": "no compact causal state"}})
    monkeypatch.setattr(L, "tier_meta", lambda tier: conf)
    monkeypatch.setattr(L, "official_guard", lambda **kw: {})
    sp = L.system_specs(L.Mode.official(), include_real=False, trap_meta=trap)
    assert sp["syn-c1"]["set"] == "suite" and sp["syn-g1"]["set"] == "trap" and sp["syn-g1"]["heldout_tier"] == "trap"
    assert sp["syn-g1"]["expected_verdict"] == "no compact causal state" and sp["syn-g1"]["compressible"] is False
    with pytest.raises(ValueError, match="clash"):
        L.system_specs(L.Mode.official(), include_real=False, trap_meta=conf)
    with pytest.raises(L.LevelCRefused):
        L.system_specs(L.Mode.official(), include_real=False, trap_meta=trap, trap_standins=["syn-c1"])
    dry = L.system_specs(L.Mode.dry(toy=False), include_real=False, trap_standins=["syn-c1"])
    assert dry["syn-c1"]["set"] == "trap" and dry["syn-c1"]["trap_standin"] is True
    with pytest.raises(ValueError, match="not a synthetic system"):
        L.system_specs(L.Mode.dry(toy=False), include_real=False, trap_standins=["syn-nope"])


def test_real_lineage_groups_builds_of_one_reconstruction():
    assert L.real_lineage({"lineage": None}, {"network": "manc_v1.2.3"}) == L.real_lineage(None, {"network": "manc_v1.2.1"}) == "manc"
    assert L.real_lineage({"lineage": None}, {"network": "male-cns_v1.0"}) == "male-cns"
    assert L.real_lineage({"lineage": "X"}, {"network": "manc_v1.2.3"}) == "X"                # a set public lineage wins
    assert L.real_lineage({}, {}) is None


def test_the_trap_catalog_is_baked_alone_at_the_container_path(tmp_path):
    extra, _sha = L.stage_remote_module(tmp_path / "stage", trap_catalog=L.DUMMY_TRAP_CATALOG)
    d = tmp_path / "_trap_catalog_dummy"
    assert extra[str(d)] == L.TRAP_CATALOG_CONTAINER and extra[str(tmp_path / "stage")] == "/repo/scripts/p4"
    assert [x.name for x in d.iterdir()] == ["review_g.py"] and (d / "review_g.py").read_bytes() == L.DUMMY_TRAP_CATALOG.read_bytes()
    other = tmp_path / "catalog.py"
    other.write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="named review_g.py"):
        L.stage_remote_module(tmp_path / "stage", trap_catalog=other)


def test_dummy_catalog_loads_through_the_trap_tier_path(monkeypatch):
    """The dry run's dummy catalog loads exactly as review G's will (synthadapter.suite_systems("trap", seed): the submodule
    p4synth.review_g, relative imports into the generator, single-threaded wrappers), for a PUBLIC seed."""
    from brainir_causal import suites as SU
    from brainir_causal import synthadapter as SA
    monkeypatch.setenv("P4_TRAP_CATALOG", str(L.DUMMY_TRAP_CATALOG))
    SA.register_generator(SU.ROOT / SU.GENERATOR_REL, "p4synth")
    sys.modules.pop("p4synth.review_g", None)                    # a catalog another test loaded is not reused
    SA.suite_systems.cache_clear()
    try:
        sy = SA.suite_systems(SA.TRAP_TIER, 7)
        truth = {sid: s.truth() for sid, s in sy.items()}
        assert len(sy) == 2 and all(type(s).__name__ == "SingleThreadedSystem" for s in sy.values())
        assert sorted(t["trap"] for t in truth.values()) == ["G-dummy-1", "G-dummy-2"]
        assert sorted(str(t["k"]) for t in truth.values()) == ["3", "none"]
    finally:
        SA.suite_systems.cache_clear()
        sys.modules.pop("p4synth.review_g", None)


# ================================================================================================================ a dead Modal client
def test_client_death_is_recognised_through_the_exception_chain():
    try:
        try:
            raise OSError("[WinError 10055] An operation on a socket could not be performed because the system lacked sufficient buffer")
        except OSError:
            raise RuntimeError("Synchronizer thread unexpectedly died")  # noqa: B904 - the implicit context is what is tested
    except RuntimeError as e:
        assert L.client_dead(e)
    assert L.client_dead(type("ClientClosed", (Exception,), {})("2553597371904"))
    assert not L.client_dead(RuntimeError("call failed repeatedly on Modal")) and not L.client_dead(None)


class DeadClientBackend(FakeBackend):
    """The Modal client dies when `dies_at` is submitted: that call and every later one raise the synchronizer error."""

    def __init__(self, dies_at: str):
        super().__init__()
        self.dies_at, self.dead = dies_at, False
        fb = self

        class _F(FakeFn):
            def result(self, p):
                if p.get("__tag") == fb.dies_at:
                    fb.dead = True
                if fb.dead:
                    fb.calls.append((self.cls, p.get("role"), p.get("__tag")))
                    raise RuntimeError("Synchronizer thread unexpectedly died")
                return FakeFn.result(self, p)

        class _Fs(dict):
            def __missing__(self, cls):
                self[cls] = _F(fb, cls)
                return self[cls]
        self.fns = _Fs()


def test_a_dead_client_stops_the_run_and_the_resume_finishes_it(tmp_path):
    """No retries are spent on a dead client and the calls in flight are NOT stored (so they are not charged as failures): the run
    raises ClientDied, records the interruption, and a resumed run (same store) computes exactly the jobs that were not finished."""
    caps = {c: 8 for c in set(L.CLASS_OF.values()) | {L.GPU_PACKED}}
    p = _plan()
    p.methods_key = "k"
    store = L.RunStore(tmp_path / "run")
    be = DeadClientBackend("eval__syn-a")
    with pytest.raises(L.ClientDied):
        L.Executor(be, p, store, caps=caps, dry=True, progress_s=1e9, idle_s=0.0).run()
    assert sum(1 for c in be.calls if c[2] == "eval__syn-a") == 1                    # no retry on a dead client
    assert not store.done("eval__syn-a")
    intr = [json.loads(x) for x in (store.dir / "interruptions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(intr) == 1 and "eval__syn-a" in intr[0]["in_flight_not_stored"] and "Synchronizer" in intr[0]["error"]
    assert not any(r.get("status") == "error" and "Synchronizer" in str(r.get("error")) for r in store.rows())
    done_before = {j for j in p.jobs if store.done(j)}
    p2 = _plan()
    p2.methods_key = "k"
    be2 = FakeBackend()
    st = L.Executor(be2, p2, store, caps=caps, dry=True, progress_s=1e9, idle_s=0.0).run()
    assert st["eval__syn-a"] == "ok"
    assert not {c[2] for c in be2.calls} & done_before                                # nothing finished is recomputed


def test_a_collect_failure_is_infrastructure_and_reruns(tmp_path, monkeypatch):
    caps = {c: 8 for c in set(L.CLASS_OF.values()) | {L.GPU_PACKED}}
    real = L.collect
    boom = {"eval__syn-a"}

    def flaky(job, res, plan, st):
        if job.id in boom:
            boom.discard(job.id)
            raise KeyError("a staged artefact could not be fetched")
        return real(job, res, plan, st)
    monkeypatch.setattr(L, "collect", flaky)
    p = _plan()
    p.methods_key = "k"
    store = L.RunStore(tmp_path / "run")
    assert L.Executor(FakeBackend(), p, store, caps=caps, dry=True, progress_s=1e9, idle_s=0.0).run()["eval__syn-a"] == "error"
    assert store.get("eval__syn-a")["infrastructure"] is True
    p2 = _plan()
    p2.methods_key = "k"
    be2 = FakeBackend()
    assert L.Executor(be2, p2, store, caps=caps, dry=True, progress_s=1e9, idle_s=0.0).run()["eval__syn-a"] == "ok"
    assert [c[2] for c in be2.calls] == ["eval__syn-a"]


def test_the_supervisor_relaunches_only_on_a_dead_client():
    import level_c as C
    assert C.strip_supervisor_args(["run", "--dry-run-dev", "--run-id", "S3", "--auto-resume", "3", "--resume-wait-s=5", "--x"]) == \
        ["run", "--dry-run-dev", "--run-id", "S3", "--x"]

    def seq(codes):
        it, calls = iter(codes), []

        def call(cmd):
            calls.append(cmd)
            return next(it)
        return call, calls
    call, calls = seq([L.EXIT_CLIENT_DIED, L.EXIT_CLIENT_DIED, 0])
    assert C.supervise(["run", "--auto-resume", "2"], 2, 0.0, call=call, sleep=lambda s: None) == 0 and len(calls) == 3
    assert all("--auto-resume" not in c for c in calls)
    call, calls = seq([L.EXIT_CLIENT_DIED] * 5)
    assert C.supervise(["run"], 2, 0.0, call=call, sleep=lambda s: None) == L.EXIT_CLIENT_DIED and len(calls) == 3   # bounded
    call, calls = seq([1])
    assert C.supervise(["run"], 5, 0.0, call=call, sleep=lambda s: None) == 1 and len(calls) == 1        # other failures end it


# ================================================================================================================ per-job time limits
def test_time_limit_formula():
    """limit = max(floor, 4 x p95(stage, class) x scale) + the job's INNER (method-side) limit, so one hung method call never trips it."""
    from brainir_causal.isolation import CALL_TIMEOUT_S, INIT_TIMEOUT_S
    p = _plan()
    J = p.jobs
    call = max(CALL_TIMEOUT_S, INIT_TIMEOUT_S)
    fit_t = L._fit_timeout(p, p.specs["syn-a"])
    assert L.time_limit_s(J["fit__syn-a__s0"], p) == max(L.TIME_LIMIT_FLOOR_S, 4 * 243) + fit_t
    assert L.time_limit_s(J["eval__syn-a"], p) == 4 * 1732 + call
    assert L.time_limit_s(J["loop__syn-a__own__l0"], p) == 4 * 1973 + max(900.0, 4 * fit_t)
    assert L.time_limit_s(J["refs__syn-a"], p) == 4 * 3205                          # trusted: no method call inside
    assert L.time_limit_s(J["stability__real_A_m1"], p) == 4 * 5732 + call           # the diagnostic's projection of the fixed job
    assert L.time_limit_s(J["share_eval__grp_g1__syn-a"], p) == max(L.TIME_LIMIT_FLOOR_S, 4 * 1142) + call
    p.time_limit_scale = 3.0
    assert L.time_limit_s(J["fit__syn-a__s0"], p) == 4 * 243 * 3 + fit_t


class HangBackend(FakeBackend):
    """Calls of `hangs` {tag: n} never return for their first n attempts (a stuck container); `results` {tag: result} replaces a
    job's result (e.g. the job's own record of a hung METHOD call, caught by the in-container call timeout)."""

    def __init__(self, hangs: dict | None = None, results: dict | None = None):
        super().__init__()
        self.hangs, self.results = dict(hangs or {}), dict(results or {})
        fb = self

        class _R:
            def __init__(self, fn):
                self.fn = fn

            async def aio(self, p):
                import asyncio
                tag = p.get("__tag")
                fb.calls.append((self.fn.cls, p.get("role"), tag))
                if fb.hangs.get(tag, 0) > 0:
                    fb.hangs[tag] -= 1
                    await asyncio.sleep(3600)
                if tag in fb.results:
                    return fb.results[tag]
                return fb._res(p)

        class _F:
            def __init__(self, cls):
                self.cls = cls
                self.remote = _R(self)

        class _Fs(dict):
            def __missing__(self, cls):
                self[cls] = _F(cls)
                return self[cls]
        self.fns = _Fs()


def _ex(be, p, store, **kw):
    caps = {c: 8 for c in set(L.CLASS_OF.values()) | {L.GPU_PACKED}}
    return L.Executor(be, p, store, caps=caps, dry=True, progress_s=1e9, idle_s=0.0, limit_fn=lambda job, plan: 0.3, **kw)


def test_a_job_over_its_time_limit_is_resubmitted_once(tmp_path):
    p = _plan()
    p.methods_key = "k"
    store = L.RunStore(tmp_path / "run")
    st = _ex(HangBackend(hangs={"refs__syn-a": 1}), p, store).run()
    assert st["refs__syn-a"] == "ok"
    row = [r for r in store.rows() if r["id"] == "refs__syn-a"][-1]
    assert row["attempts"] == 2 and len(row["timeouts"]) == 1 and row["time_limit_final"] is False
    tr = store.timeout_rows()
    assert [(r["id"], r["action"]) for r in tr] == [("refs__syn-a", "cancelled and resubmitted")] and tr[0]["limit_s"] == 0.3


def test_a_second_timeout_is_final_infrastructure_and_not_rerun(tmp_path):
    p = _plan()
    p.methods_key = "k"
    store = L.RunStore(tmp_path / "run")
    st = _ex(HangBackend(hangs={"refs__syn-a": 5}), p, store).run()
    assert st["refs__syn-a"] == "error" and st["eval__syn-a"] == "ok"               # the other jobs are unaffected
    res = store.get("refs__syn-a")
    assert res["infrastructure"] is True and res["time_limit"]["final"] is True and res["time_limit"]["attribution"] == "infrastructure"
    assert len(res["time_limit"]["timeouts"]) == 2
    assert [r["action"] for r in store.timeout_rows()] == ["cancelled and resubmitted", "final: infrastructure"]
    assert [r for r in store.rows() if r["id"] == "refs__syn-a"][-1]["time_limit_final"] is True
    # a resume does not re-run a final time-limit failure unless asked
    be2 = HangBackend()
    p2 = _plan()
    p2.methods_key = "k"
    _ex(be2, p2, store).run()
    assert not any(c[2] == "refs__syn-a" for c in be2.calls)
    be3 = HangBackend()
    p3 = _plan()
    p3.methods_key = "k"
    assert _ex(be3, p3, store, retry_timeouts=True).run()["refs__syn-a"] == "ok"
    assert [c[2] for c in be3.calls] == ["refs__syn-a"]


def test_a_hung_method_call_is_the_methods_own_failure(tmp_path):
    """A method call that hangs is killed INSIDE the job by its per-call timeout; the job returns with that failure recorded: it is the
    method's failure (charged per PROTOCOL), never an infrastructure retry and never an executor timeout."""
    p = _plan()
    p.methods_key = "k"
    store = L.RunStore(tmp_path / "run")
    own = {"error": "WorkerTimeout: A worker (uid 10021 slot 1): no reply to 'call' within 900 s; stderr tail: "}
    be = HangBackend(results={"eval__syn-a": own})
    st = _ex(be, p, store).run()
    assert st["eval__syn-a"] == "error" and L.infrastructure_error(own) is None
    row = [r for r in store.rows() if r["id"] == "eval__syn-a"][-1]
    assert row["attempts"] == 1 and row["timeouts"] == [] and sum(1 for c in be.calls if c[2] == "eval__syn-a") == 1
    assert not store.timeout_rows()


# ================================================================================================================ 5.11 record / replay
class _LinModel:
    """A deterministic in-process model for evaluate_stability (module level: Fresh pickles it)."""

    def __init__(self, seed: int):
        self.W = np.random.default_rng(seed).standard_normal((3, 2))

    def encode(self, sid, x_hist, u_hist, dt):
        return np.asarray(x_hist, float)[-1] @ self.W

    def rollout(self, sid, z0, u_future, events, dt):
        return {"z": np.array([np.asarray(z0, float) * 0.99 ** i for i in range(len(u_future))])}

    def intervention_effect(self, sid, x_hist, u_hist, u_future, events, dt):
        n = len(u_future)
        return {"effect": np.outer(np.linspace(0.0, 1.0, n), self.W.sum(0))}


def _stab_records():
    rng = np.random.default_rng(0)
    t = np.arange(200) * 0.01

    def rec(key, kind, events=(), twin_of=None, split="test"):
        x = np.cumsum(rng.standard_normal((200, 3)), 0)
        return {"key": key, "split": split, "t": t, "x": x, "u": np.zeros((200, 1)), "y": x[:, :2],
                "protocol": {"dt": 0.01, "events": list(events)}, "meta": {"twin_of": twin_of} if twin_of else {"role": kind}}
    val = [rec(f"v{i}", "d1", split="val") for i in range(4)]
    test = []
    for i in range(3):
        test.append(rec(f"i{i}", "in", events=[{"t": 1.0, "kind": "kick", "target": 0, "value": 1.0}]))
        test.append(rec(f"tw{i}", "twin", twin_of=f"i{i}"))
    test.append(rec("p0", "passive"))
    return val, test


def test_stability_replay_equals_the_frozen_function():
    """levelc_remote.stability's orchestration (each model's calls recorded to completion, then the FROZEN representation_stability on
    replays) gives exactly what the frozen function gives on the models directly."""
    from brainir_causal.evaluate_stability import representation_stability
    from brainir_causal.fresh import Fresh
    val, test = _stab_records()
    models = [_LinModel(s) for s in range(3)]
    kw = dict(horizon_short_s=0.05, horizon_s=0.25, floor=1.0, n_times=8)
    direct = representation_stability([Fresh(m) for m in models], "s", val, test, **kw)
    recs = []
    for m in models:
        rec = R.recording(Fresh(m))
        R.record_stability_calls(rec, "s", val, test, n_times=8, horizon_s=0.25, horizon_short_s=0.05)
        recs.append(rec)
    reps = [R.replay(r.calls) for r in recs]
    via = representation_stability(reps, "s", val, test, **kw)
    assert json.dumps(direct, sort_keys=True, default=str) == json.dumps(via, sort_keys=True, default=str)
    assert all(r.exhausted() for r in reps) and recs[0].summary()["n_calls"] == len(recs[0].calls) > 0
    assert direct["pairs"][0]["n_items"] == 3                                          # the three intervention items


def test_a_replay_mismatch_and_a_deadline_are_never_swallowed():
    """ReplayMismatch / DeadlineReached are BaseExceptions: the frozen helpers' safe_call would otherwise score them as failed model
    calls and compute a wrong metric silently."""
    from brainir_causal import evaluate_stability as ES
    from brainir_causal.fresh import Fresh
    val, test = _stab_records()
    rec = R.recording(Fresh(_LinModel(0)))
    R.record_stability_calls(rec, "s", val, test, n_times=8, horizon_s=0.25, horizon_short_s=0.05)
    with pytest.raises(R.ReplayMismatch):
        ES.latent_samples(R.replay(rec.calls), "s", test, 8)                           # test histories where val was recorded
    late = R.recording(Fresh(_LinModel(0)), deadline=0.0)
    with pytest.raises(R.DeadlineReached):
        ES.latent_samples(late, "s", val, 8)


def test_models_of_one_job_share_a_worker_uid():
    """Why 5.11 runs one model at a time: every RemoteFresh of a job starts its role-A worker under the same uid, and a start kills
    every process of that uid (isolation.LinuxUidTransport.start)."""
    from brainir_causal import isolation as I
    assert I.role_uid("A", 3) == I.role_uid("A", 3) and I.role_uid("A", 3) != I.role_uid("A", 4)
    import inspect
    assert "kill_uids([uid])" in inspect.getsource(I.LinuxUidTransport.start)


# ================================================================================================================ 5.17 charging
def _loop_rows_grid(fail: dict):
    rows = []
    ee = {"own": 0.5, "random": 0.6, "fixed": 0.7}
    for s in ("s1", "s2", "s3", "s4"):
        for d, v in ee.items():
            for ls in (0, 1, 2):
                for b in (10, 25, 50, 100, 200):
                    bad = (s, d, ls) in fail
                    rows.append({"system": s, "designer": d, "loop_seed": ls, "budget": b, "EE": float("nan") if bad else v + 0.001 * b})
    return rows


def test_loop_charging_follows_protocol_5_17():
    """A failed own loop is charged at the WORSE of the two arms' comparator values; a failed comparator loop at the lower of the other
    arms' values (never favouring the method); no system is dropped by active_success."""
    from brainir_causal import loop as LP
    rows = _loop_rows_grid({("s1", "own", 0), ("s2", "random", 1), ("s3", "own", 2), ("s3", "random", 2), ("s3", "fixed", 2)})
    charged, rec = L.charge_loop_rows(rows)
    get = {(r["system"], r["designer"], r["loop_seed"], r["budget"]): r["EE"] for r in charged}
    assert get[("s1", "own", 0, 10)] == pytest.approx(0.7 + 0.01)                    # max(random, fixed) at the cell
    assert get[("s2", "random", 1, 10)] == pytest.approx(0.5 + 0.01)                 # min(own, fixed) at the cell
    assert get[("s3", "own", 2, 50)] == get[("s3", "random", 2, 50)] == LP.MISSING_EE   # every arm failed: no evidence, not dropped
    assert rec["own"] == 5 and rec["comparator"] == 5 and rec["all_arms_failed"] == 15
    raw = LP.active_success(rows, own="own", comparators=("random", "fixed"), matched=None, n_boot=50, seed=0)
    assert set(raw["excluded_systems"]) >= {"s2"}                                     # the frozen function alone DROPS a system
    ok = LP.active_success(charged, own="own", comparators=("random", "fixed"), matched=None, n_boot=50, seed=0)
    assert ok["excluded_systems"] == {} and ok["n_systems"] == 4
