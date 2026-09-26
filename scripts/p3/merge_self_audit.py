"""Merge the Phase 3 self-audit runs into research/phase3/SELF_AUDIT.{json,md} (ANSWER-BEARING). ORCHESTRATOR SIDE.

Inputs: the full run (research/phase3/self_audit_full), the Q19 re-run made after the hidden-draw sweep finished
(research/phase3/self_audit_q19) and the I14 re-run made after PHASE3_REPORT.md was written (research/phase3/self_audit_i14).
Every check keeps its own status and evidence exactly as `scripts/p3/self_audit.py` (hashed in the benchmark lock) computed them.
Orchestrator notes are added where a check fails as written although its property holds (I3, I8, I11), and where the post-lock
reviews (research/phase3/reviews/POSTLOCK_*.md, section 18.1 of the report) showed that a check does not test what it seems to
test. `reported_status` differs from `status` only for Q9 (n/a: nothing was shared, so capacity could not be tested).

    uv run --project phase3 --no-sync python scripts/p3/merge_self_audit.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

P3 = Path(__file__).resolve().parents[2] / "research" / "phase3"

NOTES = {
    "I3": "FAILS AS WRITTEN (check artefact): it compares the working benchmark lock with the copy at tag state-discovery-benchmark-v3, "
          "but the two logged execution-only re-locks rewrote the lock after that tag. The property holds: freeze_benchmark.py --check "
          "passes, tag state-discovery-benchmark-v3-relock2 holds the current lock file exactly, and the salt matches its commitment.",
    "I8": "FAILS AS WRITTEN (check artefact): the only problem it lists is 'Level C attempt _refcache has no log row'. _refcache is the "
          "reference-control cache directory that the frozen Level C driver creates next to its attempts, not an attempt. Attempt 01 has "
          "START and DONE rows, and all 13 confirmation parts are logged. (Post-lock review R later found other rows missing: DONE rows "
          "of the 4 FINAL sweeps and the ablation re-run, and the 2 public-draw sweeps; they were appended retrospectively, marked.)",
    "I11": "FAILS AS WRITTEN (check artefact): the check's list of allowed top-level entries of the Modal fit volume lacks 'bundles'. "
           "bundles/dng100_public_blind holds exactly the 18 files of the public tier-A bundle (byte-identical, verified 2026-09-26), "
           "staged under the logged version-3 amendment of the leakage policy (section 3.1) for Level C's fit-time simulator. _incoming "
           "is empty, and every view holds only train / val splits.",
    "Q5": "Post-lock review Y: tested on synthetic systems only, where the native time step equals the model grid; the down-sampling of "
          "the real 1 ms data to the model grid (about 5 ms) is untested.",
    "Q6": "Post-lock review R: passes on the synthetic fraction not closed (0.22); on the real systems 7 of 10 are not closed, which would "
          "fail the same threshold.",
    "Q8": "Post-lock reviews C and R: the check decides only on the fraction of FINAL systems whose held-out C upper CI is >= 1 (19 of 46 "
          "= 0.41 < 0.5); it is not a held-out vs in-distribution comparison. Its recorded real CIs are read at the first window (100 ms), "
          "not the primary 250 ms. On the real full networks held-out C is no better than no effect on 3 of 3.",
    "Q9": "Post-lock reviews Y and R: VACUOUS, reported as n/a. The method never returned a shared model (its internal test declined to "
          "share everywhere), so no model with a different capacity exists to test.",
    "Q12": "Post-lock review S: the 18 systems pool 8 synthetic (k agrees on 4) and 10 real (k agrees on 2) systems.",
    "Q14": "Post-lock reviews Y and R: the recorded median is NaN (4 real systems have no defined ratio) and NaN > 3 is false. Over the "
           "6 finite ratios the median is 1.12 (a pass), but 2 exceed 3: 5.8 (net1 mechanism b) and 6.7 (net2 mechanism b).",
    "Q16": "Post-lock reviews S, C, Y and R: the REAL-SYSTEM EVIDENCE IS VOID. It compares PCA-k's first A key (10 ms) with the method's "
           "verdict A (250 ms). At matched horizons (primary 250 ms) PCA-k is significantly better on 2 of 10 real systems (both on net2), "
           "the method on 6 (research/phase3/reviews/POSTLOCK_NUMBERS.json). The pass rests on the synthetic criterion, which uses "
           "matched keys.",
    "Q17": "Post-lock review Y: the unrelated pairs are rejected, but so are the true implementation groups (one untestable, one "
           "rejected) because the method never returns a shared law; the rejection does not discriminate.",
    "Q18": "Post-lock review R: no compact claim on the two FINAL controls, but abstention on only 1 of 2 (the other returned k = 3), and "
           "on review G's non-compressible G10 the method rates 'partially supported' with k = 1.",
    "Q19": "Post-lock reviews S, Y and R: pooled over four sweeps (116 system-runs; 0.185 over the 108 searchable). Per sweep: FINAL "
           "effect 0.19, FINAL post 0.06, real hidden draws 0.30, real public draws 0.50: the real public-draw sweep alone reaches the "
           "fail threshold.",
}
REPORTED = {"Q9": "n/a"}


def main() -> int:
    full = json.loads((P3 / "self_audit_full" / "SELF_AUDIT.json").read_text(encoding="utf-8"))
    q19 = json.loads((P3 / "self_audit_q19" / "SELF_AUDIT.json").read_text(encoding="utf-8"))
    new_q19 = next(c for c in q19["checks"] if c["id"] == "Q19")
    i14p = P3 / "self_audit_i14" / "SELF_AUDIT.json"
    i14 = json.loads(i14p.read_text(encoding="utf-8")) if i14p.exists() else None
    checks = []
    for c in full["checks"]:
        if c["id"] == "Q19":
            c = dict(new_q19, provenance=f"re-run {q19['generated_utc']} with all four sweeps of the locked method (incl. the hidden-draw "
                                         "real sweep that finished after the full run); replaces the full run's Q19")
        elif c["id"] == "I14" and i14:
            c = dict(next(x for x in i14["checks"] if x["id"] == "I14"), provenance=f"re-run {i14['generated_utc']} after PHASE3_REPORT.md was written")
        else:
            c = dict(c, provenance=f"full run {full['generated_utc']}")
        if c["id"] in NOTES:
            c["orchestrator_note"] = NOTES[c["id"]]
        c["reported_status"] = REPORTED.get(c["id"], c["status"])
        checks.append(c)

    def count(key):
        return {g: {s: sum(1 for r in checks if r["group"] == g and r[key] == s) for s in ("pass", "fail", "n/a")} for g in ("integrity", "science")}
    counts, reported = count("status"), count("reported_status")
    rec = dict(full, generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), counts=counts, counts_reported=reported, checks=checks,
               merged_from=["research/phase3/self_audit_full/SELF_AUDIT.json", "research/phase3/self_audit_q19/SELF_AUDIT.json"]
               + (["research/phase3/self_audit_i14/SELF_AUDIT.json"] if i14 else []),
               thresholds_fixed_at="commit d056d35 (scripts/p3/self_audit.py hashed in the benchmark lock, tag "
                                   "state-discovery-benchmark-v3-relock2), before the method lock and before any post-lock evidence")
    (P3 / "SELF_AUDIT.json").write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Phase 3 self-audit (goal4 section 87)", "",
             f"Merged {rec['generated_utc']} from the full run ({full['generated_utc']}), a Q19 re-run ({q19['generated_utc']}) made after "
             "the last counterexample sweep finished" + (f" and an I14 re-run ({i14['generated_utc']})" if i14 else "") + ". Each check TESTS a "
             "question; 'fail' weakens the claim and is reported; 'n/a' means its evidence does not exist. Thresholds: "
             + rec["thresholds_fixed_at"] + ". Orchestrator notes are not check output.", "",
             f"Counts as computed: {json.dumps(counts)}", f"Counts as reported after the post-lock reviews: {json.dumps(reported)}", "",
             "| id | status (computed) | reported | check | criteria | orchestrator note |", "|---|---|---|---|---|---|"]
    for r in checks:
        note = (r.get("orchestrator_note") or "").replace("|", "/")
        lines.append(f"| {r['id']} | {r['status']} | {r['reported_status']} | {r['title']} | {', '.join(str(x) for x in r['criteria'])} | {note} |")
    (P3 / "SELF_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"computed": counts, "reported": reported}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
