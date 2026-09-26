"""Audit every Phase 4 agent's event stream and guard log (goal5 sections 5, 83 review F; research/phase4/LEAKAGE_POLICY.md section 4).

    uv run --no-sync --project phase4 python scripts/p4agent/audit_transcripts.py [--audit C:\\Dev\\BrainIR_p4audit]
                                                     [--out research/phase4/transcript_audit.json]
    uv run --no-sync --project phase4 python scripts/p4agent/audit_transcripts.py --replay-p3 C:\\Dev\\BrainIR_p3audit
                                                     [--out research/phase4/guard_replay_p3.json]

For each agent stream (<audit>/agents/*.jsonl) it reports: tool calls by kind; tool inputs naming a path outside the agent's room or a
forbidden location; tool inputs / OUTPUTS containing a forbidden name; the CLASSES of Phase 2-3 answer-bearing artefact names found in
tool outputs (class and count only, never the matched text); tokens of the Phase 1 answer (counted by class: numeric length /
non-numeric, never printed); web queries; blocked tools; the guard's denials; and every executed tool call the CURRENT guard would deny.

--replay-p3 re-checks the Phase 3 agents' recorded tool calls with the Phase 4 guard (each stream against its own Phase 3 room) and
reports only counts per decision reason (no command text): the expected new denials are direct host interpreter calls, which Phase 4
agents must run through the Docker sandbox.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMES = re.compile(r"(?i)(dng100|\bbdn2\b|pugliese|walking\s*cpg|malecns|male[-\s]?cns|\bmanc\b|neuprint|flywire|drosophila|"
                   r"phase[0-3]_report|hidden_eval|blind_eval|oracle\.json|tier_a_ids|dng100_walking_cpg|goal[1-5]\.md)")
PATHS = re.compile(r"(?i)(dev[\\/]+brainir(?!_p4)|brainir_p[23]\w*|\.claude[\\/]+projects[\\/]+c--dev-brainir[\\/]|\.credentials|"
                   r"\.modal\.toml)")
# Phase 2-3 answer-bearing artefact CLASSES (reported as class -> count, never the matched text)
ANSWER_CLASSES = {
    "PHASE2_REPORT": r"phase2_report", "PHASE3_REPORT": r"phase3_report", "HIDDEN_EVAL_LOG": r"hidden_eval_log",
    "HIDDEN_EVALUATIONS": r"hidden_evaluations", "SALT_REVEAL": r"salt_reveal", "level_c": r"level_c", "real_hidden": r"real_hidden",
    "brainir-p3-eval": r"brainir-p3-eval", "POSTLOCK_": r"postlock_", "REPORT_WORKING": r"report_working",
    "state_discovery_v1/hidden": r"state_discovery_v1[\\/]+hidden",
}
ANSWER_RE = {k: re.compile(v, re.IGNORECASE) for k, v in ANSWER_CLASSES.items()}


def answer_tokens() -> set[str]:
    """Published types, core body ids and the core's tier-A tokens (strings) of the Phase 1 answer (orchestrator side only)."""
    o = json.loads((ROOT / "benchmarks" / "dng100" / "oracle" / "oracle.json").read_text(encoding="utf-8"))
    toks = {v["type"] for v in o["labels"].values()}
    import pandas as pd
    for net, n in o["networks"].items():
        members = {**n["core"], **(n.get("core_contralateral_copies") or {})}
        toks |= {str(b) for b in members.values()}
        with open(ROOT / "benchmarks" / "dng100" / "oracle" / "tier_a_ids" / f"ids_{net}.csv", encoding="utf-8") as fh:
            pos_of = {int(r["source_id"]): int(r["position"]) for r in csv.DictReader(fh)}
        p = {pos_of[int(b)] for b in members.values() if int(b) in pos_of}
        nd = pd.read_parquet(ROOT / "benchmarks" / "dng100" / "public_blind" / "networks" / net / "neurons.parquet", columns=["position", "cell_type"])
        tok = dict(zip(nd["position"].astype(int), nd["cell_type"]))
        toks |= {str(tok[x]) for x in p if tok.get(x) is not None}
    return toks


def guard_for(room: str, allow_web: bool = False, audit_dir: str | None = None):
    """The CURRENT Phase 4 guard's decision function configured for one room."""
    os.environ["P4_CLEAN_ROOT"] = room
    os.environ["P4_ALLOW_WEB"] = "1" if allow_web else "0"
    os.environ["P4_AUDIT_DIR"] = audit_dir or str(Path(__file__).resolve().parent / ".audit_replay_sink")
    os.environ["P4_AGENT_NAME"] = "audit_replay"
    spec = importlib.util.spec_from_file_location(f"p4guard_replay_{abs(hash((room, allow_web)))}", Path(__file__).resolve().parent / "guard_hook.py")
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    return g


def _tool_uses(stream: Path):
    for line in stream.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = ev.get("message") or {}
        content = msg.get("content") if isinstance(msg.get("content"), list) else []
        yield ev, content


def audit(audit_dir: Path, with_answer_tokens: bool = True) -> dict:
    tok_re = None
    if with_answer_tokens:
        toks = answer_tokens()
        tok_re = re.compile("|".join(rf"(?<![0-9A-Za-z#]){re.escape(t)}(?![0-9A-Za-z])" for t in sorted(toks, key=len, reverse=True)))
    report = {}
    for stream in sorted((audit_dir / "agents").glob("*.jsonl")):
        name = stream.name.split(".")[0]
        r = report.setdefault(name, {"streams": [], "tool_calls": Counter(), "web_queries": [], "forbidden_path_inputs": 0,
                                     "forbidden_name_inputs": 0, "outputs_with_forbidden_names": 0, "outputs_with_answer_tokens": 0,
                                     "answer_artefact_classes_in_outputs": Counter(), "answer_artefact_classes_in_inputs": Counter(),
                                     "blocked_tool_uses": 0, "events": 0, "denied_by_current_guard": []})
        r["streams"].append(stream.name)
        meta = stream.with_name(stream.name.replace(".jsonl", ".meta.json"))
        mj = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
        room = mj.get("room") or mj.get("clean")
        g = guard_for(room, bool(mj.get("allow_web"))) if room else None
        for _ev, content in _tool_uses(stream):
            r["events"] += 1
            for c in content:
                if c.get("type") == "tool_use":
                    tool, ti = c.get("name", ""), json.dumps(c.get("input", {}))
                    r["tool_calls"][tool] += 1
                    if tool in ("WebSearch", "WebFetch"):
                        r["web_queries"].append((c.get("input") or {}).get("query") or (c.get("input") or {}).get("url"))
                    if PATHS.search(ti):
                        r["forbidden_path_inputs"] += 1
                    if NAMES.search(ti):
                        r["forbidden_name_inputs"] += 1
                    for k, rx in ANSWER_RE.items():
                        if rx.search(ti):
                            r["answer_artefact_classes_in_inputs"][k] += 1
                    if tool in ("ListAgents", "SendMessage", "RemoteTrigger", "PushNotification", "PowerShell") or tool.startswith("mcp__"):
                        r["blocked_tool_uses"] += 1
                    if g is not None:
                        ok, why = g.decide({"tool_name": tool, "tool_input": c.get("input") or {}, "cwd": room})
                        if not ok:
                            r["denied_by_current_guard"].append({"tool": tool, "reason": why[:120]})
                elif c.get("type") == "tool_result":
                    text = json.dumps(c.get("content"))
                    if NAMES.search(text):
                        r["outputs_with_forbidden_names"] += 1
                    for k, rx in ANSWER_RE.items():
                        if rx.search(text):
                            r["answer_artefact_classes_in_outputs"][k] += 1
                    if tok_re is not None:
                        mt = tok_re.search(text)
                        if mt:
                            r["outputs_with_answer_tokens"] += 1
                            tok = mt.group(0)
                            cls = f"numeric-{len(tok)}-digits" if tok.isdigit() else "non-numeric"
                            r.setdefault("answer_token_hit_classes", Counter())[cls] += 1
        glog = audit_dir / f"guard_{name}.jsonl"
        if glog.exists():
            rows, bad = [], 0
            for x in glog.read_text(encoding="utf-8", errors="replace").splitlines():
                if not x.strip():
                    continue
                try:
                    rows.append(json.loads(x))
                except json.JSONDecodeError:
                    bad += 1
            r["guard_log_unparsable_lines"] = bad
            r["guard_denials"] = sum(1 for x in rows if x["decision"] == "deny")
            r["guard_denial_reasons"] = Counter(x["reason"].split(":")[0][:60] for x in rows if x["decision"] == "deny")
    for r in report.values():
        for k in ("tool_calls", "answer_artefact_classes_in_outputs", "answer_artefact_classes_in_inputs"):
            r[k] = dict(r[k])
        r["guard_denial_reasons"] = dict(r.get("guard_denial_reasons", {}))
        if "answer_token_hit_classes" in r:
            r["answer_token_hit_classes"] = dict(r["answer_token_hit_classes"])
        r["n_web_queries"] = len(r["web_queries"])
    return report


def _reason_class(why: str) -> str:
    w = why.lower()
    if "may not run on the host" in w:
        m = re.search(r"'([^']+)' may not run", why)
        return f"host interpreter / tool refused ({m.group(1) if m else '?'})"
    if "not an allowed host command" in w:
        m = re.search(r"'([^']+)' is not an allowed", why)
        return f"host command not allowlisted ({m.group(1) if m else '?'})"
    return re.sub(r"[:(].*$", "", why)[:80]


def replay_p3(p3_audit: Path) -> dict:
    """Phase 3 agents' recorded tool calls re-checked by the Phase 4 guard, each against its own Phase 3 room; counts only."""
    out = {"source": "$EXTERNAL/" + p3_audit.name + "/agents", "streams": 0, "tool_calls": 0, "checked": 0, "denied": 0,
           "denied_by_tool": Counter(), "denied_by_reason": Counter(), "allowed_by_tool": Counter(), "rooms": Counter()}
    guards = {}
    for stream in sorted((p3_audit / "agents").glob("*.jsonl")):
        meta = stream.with_name(stream.name.replace(".jsonl", ".meta.json"))
        mj = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
        room = mj.get("clean")
        if not room:
            continue
        out["streams"] += 1
        out["rooms"][Path(room).name] += 1
        key = (room, bool(mj.get("allow_web")))
        if key not in guards:
            guards[key] = guard_for(room, key[1])
        g = guards[key]
        for _ev, content in _tool_uses(stream):
            for c in content:
                if c.get("type") != "tool_use":
                    continue
                out["tool_calls"] += 1
                tool = c.get("name", "")
                out["checked"] += 1
                ok, why = g.decide({"tool_name": tool, "tool_input": c.get("input") or {}, "cwd": room})
                pr = out.setdefault("per_room", {}).setdefault(Path(room).name, {"calls": 0, "denied": 0, "denied_host_interpreter": 0})
                pr["calls"] += 1
                if ok:
                    out["allowed_by_tool"][tool] += 1
                else:
                    out["denied"] += 1
                    pr["denied"] += 1
                    if "may not run on the host" in why:
                        pr["denied_host_interpreter"] += 1
                    out["denied_by_tool"][tool] += 1
                    out["denied_by_reason"][_reason_class(why)] += 1
    for k in ("denied_by_tool", "denied_by_reason", "allowed_by_tool", "rooms"):
        out[k] = dict(sorted(out[k].items(), key=lambda kv: -kv[1]))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", type=Path, default=Path(r"C:\Dev\BrainIR_p4audit"))
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--replay-p3", type=Path, default=None)
    ap.add_argument("--no-answer-tokens", action="store_true")
    args = ap.parse_args(argv)
    if args.replay_p3:
        rep = replay_p3(args.replay_p3)
        out = args.out or ROOT / "research" / "phase4" / "guard_replay_p3.json"
        out.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({k: rep[k] for k in ("streams", "tool_calls", "denied", "denied_by_tool")}, indent=1))
        print(json.dumps(dict(list(rep["denied_by_reason"].items())[:25]), indent=1))
        return 0
    rep = audit(args.audit, with_answer_tokens=not args.no_answer_tokens)
    out = args.out or ROOT / "research" / "phase4" / "transcript_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    for name, r in rep.items():
        print(f"{name}: events {r['events']}, tools {sum(r['tool_calls'].values())}, web {r['n_web_queries']}, forbidden-path inputs "
              f"{r['forbidden_path_inputs']}, forbidden-name inputs {r['forbidden_name_inputs']}, outputs with names "
              f"{r['outputs_with_forbidden_names']}, answer-artefact classes in outputs {r['answer_artefact_classes_in_outputs']}, "
              f"outputs with ANSWER TOKENS {r['outputs_with_answer_tokens']}, guard denials {r.get('guard_denials', 0)}, "
              f"tool calls the CURRENT guard would deny {len(r['denied_by_current_guard'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
