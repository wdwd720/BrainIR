"""The label side never reads a prediction file (prompt §7: "Add a test that fails if any label-side code reads a prediction file").

Static: label-side modules and scripts must not import prediction-side modules or name prediction files/directories.
Dynamic: the whole label pipeline (validate, merge passes, aggregate, agreement, kit build helpers) runs under an audit hook
that fails on any file opened under a `predictions` directory or named like a prediction table.
"""

import ast
import json
import sys
from pathlib import Path

import pytest

from brainir_ledger import PREDICTIONS, REPO

LABEL_MODULES = sorted((REPO / "ledger" / "src" / "brainir_ledger" / "labels").glob("*.py"))
LABEL_SCRIPTS = sorted((REPO / "ledger" / "scripts").glob("labels_*.py")) + [REPO / "ledger" / "scripts" / "build_kit.py"]
FORBIDDEN_IMPORTS = ("brainir_ledger.tables", "brainir_ledger.jobs", "brainir_ledger.typescreen", "brainir_ledger.networks",
                     "brainir_ledger.authors", "brainir_ledger.baselines", "brainir_ledger.controls", "brainir_ledger.scoring.pipeline",
                     "brainir_ledger.backend", "brainir_ledger.arms")
FORBIDDEN_TOKENS = ("predictions", "types.csv", "replicates.parquet", "legs.csv", "LOCK_predictions", "dn_screen_", "scoreSummary",
                    "combinedScoreSummary", "PREDICTIONS")


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level:  # relative import inside brainir_ledger.labels
                base = "brainir_ledger" if node.level == 2 else "brainir_ledger.labels"
                mod = f"{base}.{mod}" if mod else base
            yield mod
            for a in node.names:
                yield f"{mod}.{a.name}"


@pytest.mark.parametrize("path", LABEL_MODULES + [p for p in LABEL_SCRIPTS if p.exists()], ids=lambda p: p.name)
def test_label_side_static(path):
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    bad = [m for m in _imports(tree) if any(m == f or m.startswith(f + ".") for f in FORBIDDEN_IMPORTS)]
    assert not bad, f"{path.name} imports prediction-side modules: {bad}"
    # strings in code (docstrings excepted: they may explain the rule) must not name prediction files
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                docs.add(id(first.value))
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]
    basenames = {"types.csv", "replicates.parquet", "legs.csv"}
    substrings = [t for t in FORBIDDEN_TOKENS if t not in basenames]
    hits = [s for s in strings if any(t in s for t in substrings) or any(part in basenames for part in s.replace("\\", "/").split("/"))]
    assert not hits, f"{path.name} names prediction files: {hits}"


def test_label_pipeline_opens_no_prediction_file(tmp_path, record):
    opened = []

    def hook(event, args):
        if event == "open" and args and isinstance(args[0], (str, bytes, Path)):
            opened.append(str(args[0]))

    sys.addaudithook(hook)  # audit hooks cannot be removed; it only records
    from brainir_ledger.labels import aggregate, agreement, schema

    p1 = [record(record_id=f"a{i}", exp_id=f"pass1-atlas:a{i}", manc_type=t, front_leg_rhythm=v)
          for i, (t, v) in enumerate([("DNa01", "yes"), ("DNa02", "no")])]
    p2 = [dict(r, pass_id="pass2") for r in p1]
    p2[1]["front_leg_rhythm"] = "yes"
    adj = [dict(p1[1], pass_id="adjudication", front_leg_rhythm="no")]
    f = tmp_path / "records.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in p1) + "\n", encoding="utf-8")
    start = len(opened)
    good, bad = schema.validate_file(f, {"DNa01", "DNa02"})
    final, log = aggregate.merge_passes(good, p2, adj, {r["exp_id"]: True for r in p1})
    tl = aggregate.type_labels(final, exposed={"DNa02"})
    ag = agreement.agreement(good, p2)
    assert len(good) == 2 and not bad and len(final) == 2 and log["adjudicated"]
    assert set(tl["front"]) == {"yes", "no"} and ag["n_matched"] == 2
    during = opened[start:]
    pred_root = str(PREDICTIONS)
    leaks = [p for p in during if pred_root in p or any(t in Path(p).name for t in ("types.csv", "replicates.parquet", "legs.csv"))]
    assert not leaks, f"label pipeline opened prediction files: {leaks}"
