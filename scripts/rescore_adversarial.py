"""Re-score finished tournament runs on an adversarial suite under the generator author's CURRENT truth definition, without
re-running any method (the set-based fields change; the simulation-based fields are kept from the original scoring).

    uv run python scripts/rescore_adversarial.py research/phase2/tournament/adv_h_v10.json.gz --suite data/synthetic/adversarial_heldout \
        --label adv_h_v10_rescored

Why: on 2026-09-24 the adversarial generator's author (review G) fixed a truth inconsistency: every acceptable core now contains
every measured-essential node (``adversarial.normalize_truth_network``; only the identical_decoy/nfc_band variant changes). Runs
scored before the fix are re-scored here so that every method is compared under one definition. Stored results carry the top-100
inclusion probabilities only; probabilities beyond them count as 0 in the calibration items (a negligible change).
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

from brainir.discovery.adversarial import score_adversarial, summarize_adversarial
from brainir.discovery.interface import DiscoveryResult
from brainir.discovery.tournament import _json_default, adversarial_view, score_structure, summarize, to_markdown

SIM_FIELDS = ("participation", "core_keep_only_pass", "intact_pass", "core_frequency_hz", "intact_frequency_hz", "fidelity_error")
# computed from the FULL inclusion probabilities at the original scoring (stored results keep only the top 100, so a large core would
# lose members' probabilities); they do not depend on the truth definition, except the calibration targets of the few essential
# nodes the definition moves (identical_decoy/nfc_band gate and latch)
KEPT_FIELDS = SIM_FIELDS + ("confident", "brier_contested", "calibration_items", "exchangeable_gap")


def _result(d: dict) -> DiscoveryResult:
    return DiscoveryResult(core=[int(p) for p in d.get("core") or []],
                           inclusion_probability={int(k): float(v) for k, v in (d.get("inclusion_probability") or {}).items()},
                           roles={int(k): (v[0], float(v[1])) for k, v in (d.get("roles") or {}).items()},
                           essential={int(k): v for k, v in (d.get("essential") or {}).items()},
                           alternatives=[[int(p) for p in a] for a in d.get("alternatives") or []], diagnostics=d.get("diagnostics") or {},
                           fidelity=d.get("fidelity") or {})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", type=Path)
    ap.add_argument("--suite", type=Path, required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", type=Path, default=Path("research/phase2/tournament"))
    args = ap.parse_args(argv)
    raw = gzip.open(args.results, "rt", encoding="utf-8").read() if args.results.suffix == ".gz" else args.results.read_text(encoding="utf-8")
    d = json.loads(raw)
    truths: dict[str, dict] = {}
    changed = 0
    for r in d["records"]:
        if "adversarial" not in r or "result" not in r:
            continue
        name = r["instance"]
        if name not in truths:
            truths[name] = json.loads((args.suite / "truth" / f"{name}.json").read_text(encoding="utf-8"))
        tnet_raw = truths[name]["networks"][r["network"]]
        res = _result(r["result"])
        new = score_adversarial(res, tnet_raw)
        for k in KEPT_FIELDS:
            if k in r["adversarial"]:
                new[k] = r["adversarial"][k]
        new["confident_wrong"] = bool(new.get("confident") and not new["correct"])
        changed += int(new["correct"] != r["adversarial"].get("correct"))
        r["adversarial"] = new
        st = score_structure(res, adversarial_view(tnet_raw))
        for k in ("brier_inclusion", "brier_contested", "brier_contested_any_alternative"):  # full-probability values from the run
            if k in (r.get("structure") or {}):
                st[k] = r["structure"][k]
        st["success_intact"] = bool(st["success"] and (r.get("intact") or {}).get("core_participates", False)
                                    and st["essential_recall"] in (None, 1.0))
        r["structure"] = st
    methods = sorted({r["method"] for r in d["records"] if "method" in r})
    d["summary"] = summarize(d["records"])
    d["adversarial"] = {}
    for m in methods:
        rs = [r for r in d["records"] if r.get("method") == m]
        scored = [r["adversarial"] for r in rs if "adversarial" in r]
        s = summarize_adversarial(scored) if scored else {"per_trap": {}, "n_runs": 0}
        n_failed = sum(1 for r in rs if "adversarial" not in r)
        s["n_failed"] = n_failed
        if scored:
            s["correct_incl_failures"] = float(s["correct"] * len(scored) / (len(scored) + n_failed))
        d["adversarial"][m] = s
    d["label"] = args.label
    d["rescored_from"] = args.results.name
    d["rescore_note"] = "set-based fields re-scored under adversarial.DEFINITION (acceptable cores contain every essential node); simulation fields kept"
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{args.label}.json").write_text(json.dumps(d, indent=1, default=_json_default) + "\n", encoding="utf-8", newline="\n")
    (args.out / f"{args.label}.md").write_text(to_markdown(d), encoding="utf-8", newline="\n")
    print(f"{args.label}: {changed} runs changed their 'correct' verdict")
    return 0


if __name__ == "__main__":
    sys.exit(main())
