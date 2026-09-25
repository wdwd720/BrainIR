"""Audit every Phase 3 agent's event stream and guard log (goal4 sections 3, 69 review F; LEAKAGE_POLICY.md section 4).

    uv run python scripts/p3agent/audit_transcripts.py [--audit C:\\Dev\\BrainIR_p3audit] [--out research/phase3/reviews/transcript_audit.json]

For each agent stream (P3_AUDIT_DIR/agents/*.jsonl) it reports: tool calls by kind, every tool input naming a path outside the
agent's room or a forbidden location, every tool OUTPUT containing a forbidden token, web queries, calls to blocked tools, and the
guard's denials. Forbidden tokens: dataset / circuit / paper names, Phase 2 artefact names, and the answer's own identifiers read at
audit time from the Phase 1 oracle (published types, core body ids, tier-A tokens and positions of core neurons) — they are counted,
never printed.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NAMES = re.compile(r"(?i)(dng100|\bbdn2\b|pugliese|walking\s*cpg|malecns|male[-\s]?cns|\bmanc\b|neuprint|flywire|drosophila|"
                   r"phase2_report|hidden_eval|blind_eval|oracle\.json|tier_a_ids|dng100_walking_cpg|goal[1-4]\.md)")
PATHS = re.compile(r"(?i)(dev[\\/]+brainir(?!_p3)|brainir_p2clean|\.claude[\\/]+projects[\\/]+c--dev-brainir[\\/]|\.credentials|\.modal\.toml)")


def answer_tokens() -> tuple[set[str], set[int]]:
    """Published types, core body ids and the core's tier-A tokens (strings) and tier-A positions (ints > 16)."""
    o = json.loads((ROOT / "benchmarks" / "dng100" / "oracle" / "oracle.json").read_text(encoding="utf-8"))
    toks = {v["type"] for v in o["labels"].values()}
    pos: set[int] = set()
    for net, n in o["networks"].items():
        members = {**n["core"], **(n.get("core_contralateral_copies") or {})}
        toks |= {str(b) for b in members.values()}
        with open(ROOT / "benchmarks" / "dng100" / "oracle" / "tier_a_ids" / f"ids_{net}.csv", encoding="utf-8") as fh:
            pos_of = {int(r["source_id"]): int(r["position"]) for r in csv.DictReader(fh)}
        p = {pos_of[int(b)] for b in members.values() if int(b) in pos_of}
        pos |= {x for x in p if x > 16}
        nd = pd.read_parquet(ROOT / "benchmarks" / "dng100" / "public_blind" / "networks" / net / "neurons.parquet", columns=["position", "cell_type"])
        tok = dict(zip(nd["position"].astype(int), nd["cell_type"]))
        toks |= {str(tok[x]) for x in p if tok.get(x) is not None}
    return toks, pos


def _guard_for(room: str, allow_web: bool = False):
    """The CURRENT guard's decision function configured for one room (retroactive re-check of executed tool calls)."""
    import importlib.util
    import os
    os.environ["P3_CLEAN_ROOT"] = room
    os.environ["P3_ALLOW_WEB"] = "1" if allow_web else "0"
    os.environ.setdefault("P3_AUDIT_DIR", str(Path(__file__).resolve().parent / ".audit_replay_sink"))
    os.environ["P3_AGENT_NAME"] = "audit_replay"
    spec = importlib.util.spec_from_file_location(f"guard_replay_{abs(hash((room, allow_web)))}", Path(__file__).resolve().parent / "guard_hook.py")
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    return g


def audit(audit_dir: Path) -> dict:
    toks, _pos = answer_tokens()
    tok_re = re.compile("|".join(rf"(?<![0-9A-Za-z#]){re.escape(t)}(?![0-9A-Za-z])" for t in sorted(toks, key=len, reverse=True)))
    report = {}
    for stream in sorted((audit_dir / "agents").glob("*.jsonl")):
        name = stream.name.split(".")[0]
        r = report.setdefault(name, {"streams": [], "tool_calls": Counter(), "web_queries": [], "forbidden_path_inputs": 0,
                                     "forbidden_name_inputs": 0, "outputs_with_forbidden_names": 0, "outputs_with_answer_tokens": 0,
                                     "blocked_tool_uses": 0, "events": 0})
        r["streams"].append(stream.name)
        meta = stream.with_name(stream.name.replace(".jsonl", ".meta.json"))
        mj = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
        room = mj.get("clean")
        g = _guard_for(room, bool(mj.get("allow_web"))) if room else None
        r.setdefault("denied_by_current_guard", [])
        for line in stream.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            r["events"] += 1
            msg = ev.get("message") or {}
            for c in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
                if c.get("type") == "tool_use":
                    tool, ti = c.get("name", ""), json.dumps(c.get("input", {}))
                    r["tool_calls"][tool] += 1
                    if tool in ("WebSearch", "WebFetch"):
                        r["web_queries"].append((c.get("input") or {}).get("query") or (c.get("input") or {}).get("url"))
                    if PATHS.search(ti):
                        r["forbidden_path_inputs"] += 1
                    if NAMES.search(ti):
                        r["forbidden_name_inputs"] += 1
                    if tool in ("ListAgents", "SendMessage", "RemoteTrigger", "PushNotification") or tool.startswith("mcp__"):
                        r["blocked_tool_uses"] += 1
                    if g is not None:
                        ok, why = g.decide({"tool_name": tool, "tool_input": c.get("input") or {}, "cwd": room})
                        if not ok:
                            r["denied_by_current_guard"].append({"tool": tool, "reason": why[:120], "input": ti[:300]})
                elif c.get("type") == "tool_result":
                    text = json.dumps(c.get("content"))
                    if NAMES.search(text):
                        r["outputs_with_forbidden_names"] += 1
                    mt = tok_re.search(text)
                    if mt:
                        r["outputs_with_answer_tokens"] += 1
                        # the token class, never its value (the value is answer-bearing): a short numeric token can coincide with
                        # an unrelated number (file sizes, counts); non-numeric tokens are the real alarm
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
                except json.JSONDecodeError:   # concurrent hook processes may interleave a line
                    bad += 1
            r["guard_log_unparsable_lines"] = bad
            r["guard_denials"] = sum(1 for x in rows if x["decision"] == "deny")
            r["guard_denial_reasons"] = Counter(x["reason"].split(":")[0][:60] for x in rows if x["decision"] == "deny")
    for r in report.values():
        r["tool_calls"] = dict(r["tool_calls"])
        r["guard_denial_reasons"] = dict(r.get("guard_denial_reasons", {}))
        r["n_web_queries"] = len(r["web_queries"])
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", type=Path, default=Path(r"C:\Dev\BrainIR_p3audit"))
    ap.add_argument("--out", type=Path, default=ROOT / "research" / "phase3" / "reviews" / "transcript_audit.json")
    args = ap.parse_args(argv)
    rep = audit(args.audit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    for name, r in rep.items():
        print(f"{name}: events {r['events']}, tools {sum(r['tool_calls'].values())}, web {r['n_web_queries']}, forbidden-path inputs "
              f"{r['forbidden_path_inputs']}, forbidden-name inputs {r['forbidden_name_inputs']}, outputs with names "
              f"{r['outputs_with_forbidden_names']}, outputs with ANSWER TOKENS {r['outputs_with_answer_tokens']}, blocked tools "
              f"{r['blocked_tool_uses']}, guard denials {r.get('guard_denials', 0)}, "
              f"tool calls the CURRENT guard would deny {len(r.get('denied_by_current_guard', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
