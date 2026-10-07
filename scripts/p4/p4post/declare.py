"""The ablation contract (brainir_causal.api: ABLATION_SWITCHES, config "ablate", info "ablation_switches" / "ablated"; goal5
sections 87-89) as the post-lock ablation driver enforces it. Everything here FAILS LOUDLY (AblationContractError lists every problem):

- DECLARATION (`check_declaration`): info()["ablation_switches"] of the full fit must name EVERY switch of the vocabulary, each either
  honoured or not applicable WITH a non-empty reason; unknown names are errors. Accepted spellings: "honoured" / "honored" / True /
  {"status": "honoured"}; {"status": "not_applicable", "reason": r} / ("not_applicable", r) / "not_applicable: r" (also "- r", "(r)").
  Declarations may differ between systems (e.g. shared dynamics in a single-system fit) but are recorded per system.
- APPLICATION (`check_applied`): a fit with config {"ablate": [s]} must report info()["ablated"] == [s] (as a set) and must declare
  s honoured; a switch declared honoured but not applied, or applied without being requested, is an error.
"""

from __future__ import annotations

import re

from brainir_causal.api import ABLATION_SWITCHES

HONOURED = "honoured"
NOT_APPLICABLE = "not_applicable"
#: the two critical ablations (goal5 sections 88-89; SELF_AUDIT_PLAN Q20 / Q21)
CRITICAL = ("interventional_training", "state_bottleneck")
_NA_TEXT = re.compile(r"^\s*not[ _-]?applicable\s*(?:[:\-(]\s*(?P<reason>.*?)\)?\s*)?$", re.IGNORECASE | re.DOTALL)


class AblationContractError(RuntimeError):
    pass


def parse_switch(value) -> tuple[str, str]:
    """(status, reason) of one declared value; raises ValueError for anything that is neither honoured nor not applicable with a
    reason."""
    if value is True:
        return HONOURED, ""
    if isinstance(value, str):
        v = value.strip()
        if v.lower() in ("honoured", "honored"):
            return HONOURED, ""
        m = _NA_TEXT.match(v)
        if m:
            reason = (m.group("reason") or "").strip()
            if not reason:
                raise ValueError("declared not applicable without a reason")
            return NOT_APPLICABLE, reason
        raise ValueError(f"unrecognised declaration {value!r}")
    if isinstance(value, (list, tuple)) and len(value) == 2 and isinstance(value[0], str):
        head = value[0].strip().lower().replace("-", "_").replace(" ", "_")
        if head in ("honoured", "honored"):
            return HONOURED, ""
        if head == NOT_APPLICABLE:
            reason = str(value[1] or "").strip()
            if not reason:
                raise ValueError("declared not applicable without a reason")
            return NOT_APPLICABLE, reason
        raise ValueError(f"unrecognised declaration {value!r}")
    if isinstance(value, dict):
        st = str(value.get("status", value.get("state", ""))).strip().lower().replace("-", "_").replace(" ", "_")
        if st in ("honoured", "honored"):
            return HONOURED, ""
        if st == NOT_APPLICABLE:
            reason = str(value.get("reason") or "").strip()
            if not reason:
                raise ValueError("declared not applicable without a reason")
            return NOT_APPLICABLE, reason
        raise ValueError(f"unrecognised declaration status {value.get('status', value.get('state'))!r}")
    raise ValueError(f"unrecognised declaration {value!r}")


def check_declaration(info: dict | None, where: str) -> dict[str, dict]:
    """{switch: {"status", "reason"}} of a fitted model's info(); raises AblationContractError listing every problem."""
    problems: list[str] = []
    decl = (info or {}).get("ablation_switches")
    if not isinstance(decl, dict):
        raise AblationContractError(f"{where}: info()['ablation_switches'] is missing or not a mapping (got {type(decl).__name__}); "
                                    f"the method must declare every switch of api.ABLATION_SWITCHES")
    out: dict[str, dict] = {}
    for name in ABLATION_SWITCHES:
        if name not in decl:
            problems.append(f"switch {name!r} not declared")
            continue
        try:
            st, reason = parse_switch(decl[name])
            out[name] = {"status": st, "reason": reason}
        except ValueError as e:
            problems.append(f"switch {name!r}: {e}")
    for name in sorted(set(decl) - set(ABLATION_SWITCHES)):
        problems.append(f"unknown switch {name!r} declared")
    if problems:
        raise AblationContractError(f"{where}: " + "; ".join(problems))
    return out


def check_applied(info: dict | None, requested: list[str], declaration: dict[str, dict], where: str) -> None:
    """A fit with config {"ablate": requested}: every requested switch declared honoured, info()['ablated'] == requested (as sets)."""
    problems: list[str] = []
    for s in requested:
        if s not in ABLATION_SWITCHES:
            problems.append(f"{s!r} is not an ablation switch")
        elif (declaration.get(s) or {}).get("status") != HONOURED:
            problems.append(f"{s!r} requested but not declared honoured")
    applied = (info or {}).get("ablated")
    if not isinstance(applied, (list, tuple)):
        problems.append(f"info()['ablated'] missing or not a list (got {type(applied).__name__})")
    else:
        a, r = {str(x) for x in applied}, set(requested)
        if a != r:
            if r - a:
                problems.append(f"requested but not applied: {sorted(r - a)}")
            if a - r:
                problems.append(f"applied but not requested: {sorted(a - r)}")
    if problems:
        raise AblationContractError(f"{where}: " + "; ".join(problems))


def switch_plan(declarations: dict[str, dict[str, dict]]) -> dict[str, dict]:
    """Per switch: the systems where it is honoured (one ablated fit each) and where it is not applicable (with the reason)."""
    out: dict[str, dict] = {}
    for name in ABLATION_SWITCHES:
        hon = sorted(s for s, d in declarations.items() if d[name]["status"] == HONOURED)
        na = {s: d[name]["reason"] for s, d in declarations.items() if d[name]["status"] == NOT_APPLICABLE}
        out[name] = {"honoured_on": hon, "not_applicable_on": na, "definition": ABLATION_SWITCHES[name]}
    return out
