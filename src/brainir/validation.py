"""Validation report framework.

A build records every check it performs (passing or not). ``fail`` means the
processed data must not be trusted; ``warn`` means a documented discrepancy or
caveat that analyses must take into account; ``info`` records a measurement
(e.g. graph statistics, coverage).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

PASS, FAIL, WARN, INFO = "pass", "fail", "warn", "info"
_STATUSES = (PASS, FAIL, WARN, INFO)


def _jsonable(x: Any) -> Any:
    """Convert numpy/pandas scalars and containers into plain JSON types."""
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_jsonable(v) for v in x]
    if hasattr(x, "item") and callable(x.item):
        try:
            return x.item()
        except (ValueError, TypeError):
            pass
    if isinstance(x, float) and x != x:  # NaN
        return None
    return x


@dataclass
class Check:
    check_id: str
    category: str
    description: str
    status: str
    observed: Any = None
    expected: Any = None
    details: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in _STATUSES:
            raise ValueError(f"invalid status {self.status!r}")
        self.observed = _jsonable(self.observed)
        self.expected = _jsonable(self.expected)
        self.details = _jsonable(self.details)


@dataclass
class ValidationReport:
    title: str
    checks: list[Check] = field(default_factory=list)
    context: dict = field(default_factory=dict)

    def add(self, check_id: str, category: str, description: str, status: str,
            observed: Any = None, expected: Any = None, **details: Any) -> Check:
        if any(c.check_id == check_id for c in self.checks):
            raise ValueError(f"duplicate check id {check_id}")
        c = Check(check_id, category, description, status, observed, expected, details)
        self.checks.append(c)
        return c

    def expect_equal(self, check_id: str, category: str, description: str, observed: Any, expected: Any,
                     *, on_mismatch: str = FAIL, **details: Any) -> Check:
        status = PASS if _jsonable(observed) == _jsonable(expected) else on_mismatch
        return self.add(check_id, category, description, status, observed, expected, **details)

    def expect_true(self, check_id: str, category: str, description: str, condition: bool,
                    observed: Any = None, *, on_false: str = FAIL, **details: Any) -> Check:
        return self.add(check_id, category, description, PASS if condition else on_false, observed, True, **details)

    def summary(self) -> dict[str, int]:
        out = {s: 0 for s in _STATUSES}
        for c in self.checks:
            out[c.status] += 1
        return out

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if c.status == FAIL]

    def to_dict(self) -> dict:
        return {"title": self.title, "summary": self.summary(), "context": _jsonable(self.context),
                "checks": [asdict(c) for c in self.checks]}

    def write(self, json_path: Path, md_path: Path | None = None) -> None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        # LF newlines on every OS so reports are byte-identical across platforms
        json_path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=False) + "\n", encoding="utf-8", newline="\n")
        if md_path is not None:
            md_path.write_text(self.to_markdown() + "\n", encoding="utf-8", newline="\n")

    def to_markdown(self) -> str:
        s = self.summary()
        lines = [f"# {self.title}", "",
                 f"**Summary:** {s[PASS]} pass, {s[FAIL]} fail, {s[WARN]} warn, {s[INFO]} info", ""]
        if self.context:
            lines += ["## Context", "", "```json", json.dumps(_jsonable(self.context), indent=2), "```", ""]
        cats: dict[str, list[Check]] = {}
        for c in self.checks:
            cats.setdefault(c.category, []).append(c)
        icon = {PASS: "PASS", FAIL: "**FAIL**", WARN: "WARN", INFO: "info"}
        for cat, checks in cats.items():
            lines += [f"## {cat}", "", "| status | check | observed | expected | description |",
                      "|---|---|---|---|---|"]
            for c in checks:
                obs = _short(c.observed)
                exp = "" if c.expected is None else _short(c.expected)
                lines.append(f"| {icon[c.status]} | `{c.check_id}` | {obs} | {exp} | {c.description} |")
            lines.append("")
            detailed = [c for c in checks if c.details]
            for c in detailed:
                lines += [f"<details><summary><code>{c.check_id}</code> details</summary>", "", "```json",
                          json.dumps(c.details, indent=2)[:6000], "```", "</details>", ""]
        return "\n".join(lines)


def _short(v: Any, n: int = 80) -> str:
    s = json.dumps(v) if not isinstance(v, str) else v
    s = s.replace("|", "\\|")
    return s if len(s) <= n else s[: n - 3] + "..."
