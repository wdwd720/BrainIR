"""Gate G0: the MANC rebuilds on this machine agree with the committed manifests.

    uv run --no-sync python ledger/scripts/g0_check.py            # after `brainir ingest` of manc v1.0 / v1.2.1 / v1.2.3

`brainir ingest` rewrites `data/manifests/*.json|md` (committed files). This script compares the rebuilt manifests with the
committed ones (`git show HEAD:...`), field by field where it matters:

* raw inputs: every acquired file's SHA-256 (documentation snapshots of web pages are excluded: they are re-fetched at
  acquisition time and are not pipeline inputs);
* processed outputs: SHA-256, row count and column schema of every table;
* graph statistics and annotation coverage (exact equality of the JSON values);
* validation summary (pass / fail / warn counts).

It writes `research/ledger/g0/G0_REPORT.{json,md}`, keeps a copy of the rebuilt manifests under the data root
(`cache/ledger_g0/`), and finally restores `data/manifests/` to the committed state (`git checkout -- data/manifests`), so no
regenerated manifest is ever committed on the ledger branch.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from brainir import paths  # noqa: E402

BUILDS = ["manc_v1.0", "manc_v1.2.1", "manc_v1.2.3"]
OUT = REPO / "research" / "ledger" / "g0"


def git_show(rel: str) -> str:
    return subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=REPO, check=True, capture_output=True, text=True).stdout


def compare_build(name: str) -> dict:
    rel = f"data/manifests/{name}.manifest.json"
    old = json.loads(git_show(rel))
    new = json.loads((REPO / rel).read_text(encoding="utf-8"))
    rep: dict = {"build": name, "problems": [], "notes": []}
    # raw inputs
    of = {f["key"]: f for f in old["acquisition"]["files"]}
    nf = {f["key"]: f for f in new["acquisition"]["files"]}
    rep["raw_files_compared"] = len(of)
    if set(of) != set(nf):
        rep["problems"].append(f"raw file keys differ: only committed {sorted(set(of) - set(nf))}, only rebuilt {sorted(set(nf) - set(of))}")
    for k in sorted(set(of) & set(nf)):
        if of[k].get("sha256") != nf[k].get("sha256"):
            rep["problems"].append(f"raw file {k}: sha256 {of[k].get('sha256')} != {nf[k].get('sha256')}")
    # processed outputs
    rows = []
    for t, o in old["processed_outputs"].items():
        n = new["processed_outputs"].get(t)
        if n is None:
            rep["problems"].append(f"output {t} missing in rebuild")
            continue
        same_sha = o.get("sha256") == n.get("sha256")
        same_rows = o.get("rows") == n.get("rows")
        same_schema = o.get("schema") == n.get("schema")
        rows.append({"table": t, "rows_committed": o.get("rows"), "rows_rebuilt": n.get("rows"), "sha256_equal": same_sha,
                     "rows_equal": same_rows, "schema_equal": same_schema, "sha256_committed": o.get("sha256"), "sha256_rebuilt": n.get("sha256")})
        if not same_rows:
            rep["problems"].append(f"output {t}: rows {o.get('rows')} != {n.get('rows')}")
        if not same_schema:
            rep["problems"].append(f"output {t}: schema differs")
        if not same_sha:
            rep["notes"].append(f"output {t}: file sha256 differs (rows and schema equal: {same_rows and same_schema}); content check needed")
    rep["outputs"] = rows
    for sec in ("graph_statistics", "annotation_coverage", "definitions", "transformations"):
        if old.get(sec) != new.get(sec):
            rep["problems"].append(f"section {sec} differs")
    vo, vn = old["validation"]["summary"], new["validation"]["summary"]
    rep["validation_committed"], rep["validation_rebuilt"] = vo, vn
    if vo != vn:
        rep["problems"].append(f"validation summary differs: {vo} vs {vn}")
    rep["environment_rebuilt"] = new["build"].get("environment")
    rep["environment_committed"] = old["build"].get("environment")
    rep["pass"] = not rep["problems"] and all(r["sha256_equal"] for r in rows)
    rep["pass_content"] = not rep["problems"]
    return rep


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    keep = paths.data_root() / "cache" / "ledger_g0" / "rebuilt_manifests"
    keep.mkdir(parents=True, exist_ok=True)
    reports = []
    for b in BUILDS:
        for suf in (".manifest.json", ".validation.json", ".validation.md"):
            src = REPO / "data" / "manifests" / f"{b}{suf}"
            if src.exists():
                shutil.copy2(src, keep / src.name)
        reports.append(compare_build(b))
    res = {"gate": "G0", "builds": reports, "all_pass_bytes": all(r["pass"] for r in reports),
           "all_pass_content": all(r["pass_content"] for r in reports)}
    (OUT / "G0_REPORT.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    md = ["# Gate G0: MANC rebuilds on this machine vs the committed manifests", "",
          "Rebuilt with `uv run brainir ingest --dataset manc --version <v>` on this Mac; compared with `git show HEAD:data/manifests/...` "
          "by `ledger/scripts/g0_check.py`. Documentation snapshots of web pages are not pipeline inputs and are not compared.", ""]
    for r in reports:
        md.append(f"## {r['build']}: {'PASS (byte-identical outputs)' if r['pass'] else ('PASS on content' if r['pass_content'] else 'FAIL')}")
        md.append("")
        md.append(f"- raw input files compared by SHA-256: {r['raw_files_compared']}")
        md.append(f"- validation: committed {r['validation_committed']}, rebuilt {r['validation_rebuilt']}")
        md.append("")
        md.append("| table | rows committed | rows rebuilt | schema equal | file sha256 equal |")
        md.append("|---|---|---|---|---|")
        for o in r["outputs"]:
            md.append(f"| {o['table']} | {o['rows_committed']} | {o['rows_rebuilt']} | {o['schema_equal']} | {o['sha256_equal']} |")
        md.append("")
        for p in r["problems"]:
            md.append(f"- PROBLEM: {p}")
        for n in r["notes"]:
            md.append(f"- note: {n}")
        md.append("")
    (OUT / "G0_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(md))
    subprocess.run(["git", "checkout", "--", "data/manifests"], cwd=REPO, check=True)
    print("restored data/manifests to HEAD; rebuilt copies kept in", keep)


if __name__ == "__main__":
    main()
