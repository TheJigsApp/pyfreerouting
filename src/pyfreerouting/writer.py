# ===========================================================================
# S-expression writer
# ===========================================================================
# Mirrors parser.py exactly: one private _write_<model> function per parser,
# plus a public write_rules(PCBRules) -> str entry point.
# ===========================================================================

from __future__ import annotations

import re
from typing import get_args

from .rules import (
    AnyRule,
    AutorouteSettings,
    ClearanceRule,
    LayerRule,
    PCBRules,
    WidthRule,
)

# ---------------------------------------------------------------------------
# Formatting primitives
# ---------------------------------------------------------------------------

_SAFE_ATOM = re.compile(r"^[A-Za-z0-9_.:]+$")


def _atom(value: str) -> str:
    """Quote a string if it contains whitespace or special characters."""
    if _SAFE_ATOM.match(value):
        return value
    return f'"{value}"'


def _fmt_float(value: float) -> str:
    """
    Emit the most compact lossless decimal representation.
    Freerouting expects at least one decimal place (200.0 not 200).
    """
    s = f"{value:.10g}"
    if "." not in s and "e" not in s:
        s += ".0"
    return s


def _indent(block: str, spaces: int = 2) -> str:
    """Indent every line of *block* by *spaces* spaces."""
    pad = " " * spaces
    return "\n".join(pad + line for line in block.splitlines())


def _block(head: str, *children: str) -> str:
    """
    Render a multi-line s-expression block:

        (head
          child1
          child2
        )
    """
    inner = "\n".join(_indent(c) for c in children)
    return f"({head}\n{inner}\n)"


def _inline(head: str, *atoms: str) -> str:
    """Render a single-line s-expression: (head atom1 atom2 ...)"""
    parts = " ".join(atoms)
    return f"({head} {parts})" if parts else f"({head})"


# ---------------------------------------------------------------------------
# Individual writers  (mirror _parse_* in parser.py)
# ---------------------------------------------------------------------------


def _write_layer_rule(lr: LayerRule) -> str:
    # (layer_rule <name>
    #   (active on|off)
    #   (preferred_direction horizontal|vertical)
    #   (preferred_direction_trace_costs <float>)
    #   (against_preferred_direction_trace_costs <float>)
    # )
    return _block(
        f"layer_rule {_atom(lr.layer_name)}",
        _inline("active", "on" if lr.active else "off"),
        _inline("preferred_direction", lr.preferred_direction.value),
        _inline(
            "preferred_direction_trace_costs",
            _fmt_float(lr.preferred_direction_trace_costs),
        ),
        _inline(
            "against_preferred_direction_trace_costs",
            _fmt_float(lr.against_preferred_direction_trace_costs),
        ),
    )


def _write_autoroute_settings(ar: AutorouteSettings) -> str:
    return _block(
        "autoroute_settings",
        _inline("fanout", "on" if ar.fanout else "off"),
        _inline("autoroute", "on" if ar.autoroute else "off"),
        _inline("postroute", "on" if ar.postroute else "off"),
        _inline("vias", "on" if ar.vias else "off"),
        _inline("via_costs", str(ar.via_costs)),
        _inline("plane_via_costs", str(ar.plane_via_costs)),
        _inline("start_ripup_costs", str(ar.start_ripup_costs)),
        _inline("start_pass_no", str(ar.start_pass_no)),
        *(_write_layer_rule(lr) for lr in ar.layer_rules),
    )


def _write_clearance(rule: ClearanceRule) -> str:
    # (clearance <value> [(type <subtype>)])
    if rule.subtype is None:
        return _inline("clearance", _fmt_float(rule.value_um))
    return _inline(
        "clearance", _fmt_float(rule.value_um), _inline("type", _atom(rule.subtype))
    )


def _write_width(rule: WidthRule) -> str:
    return _inline("width", _fmt_float(rule.width_um))


def _write_any_rule(rule: AnyRule) -> str:  # type: ignore[valid-type]
    if isinstance(rule, ClearanceRule):
        return _write_clearance(rule)
    if isinstance(rule, WidthRule):
        return _write_width(rule)
    raise TypeError(f"Unknown rule type: {type(rule)}")


def _write_rule_block(rules: list) -> str:
    # (rule
    #   (width ...)
    #   (clearance ...) ...
    # )
    return _block("rule", *(_write_any_rule(r) for r in rules))


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def write_rules(rules: PCBRules) -> str:
    """
    Serialise a :class:`PCBRules` instance back to its s-expression text
    representation, suitable for writing to a ``.rules`` file.

    The output is intended to round-trip cleanly through :func:`parse_rules`.
    """
    children: list[str] = [
        _block("snap_angle", rules.snap_angle.value),
        _write_autoroute_settings(rules.autoroute_settings),
    ]

    if rules.rules:
        children.append(_write_rule_block(rules.rules))

    return _block(f"rules PCB {_atom(rules.design_name)}", *children)
