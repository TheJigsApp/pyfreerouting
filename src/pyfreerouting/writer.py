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
    Circuit,
    ClearanceRule,
    LayerRule,
    NetClass,
    PCBRules,
    Padstack,
    PadShape,
    Via,
    ViaRule,
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
        _inline("active", lr.active.value),
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
        _inline("fanout", ar.fanout.value),
        _inline("autoroute", ar.autoroute.value),
        _inline("postroute", ar.postroute.value),
        _inline("vias", ar.vias.value),
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


def _write_padshape(shape: PadShape) -> str:
    # (shape (circle <layer> <diameter> <x> <y>))
    circle = _inline(
        "circle",
        _atom(shape.layer),
        _fmt_float(shape.diameter_um),
        _fmt_float(shape.x),
        _fmt_float(shape.y),
    )
    return _inline("shape", circle)


def _write_padstack(ps: Padstack) -> str:
    return _block(
        f"padstack {_atom(ps.name)}",
        *(_write_padshape(s) for s in ps.shapes),
        _inline("attach", ps.attach.value),
    )


def _write_via(via: Via) -> str:
    return _inline(
        "via",
        _atom(via.padstack_name),
        _atom(via.padstack_ref),
        _atom(via.net_class),
    )


def _write_via_rule(vr: ViaRule) -> str:
    return _inline("via_rule", _atom(vr.net_class), _atom(vr.via_name))


def _write_circuit(circuit: Circuit) -> str:
    if not circuit.use_layers:
        return "(circuit)"
    return _block(
        "circuit", _inline("use_layer", *(_atom(l) for l in circuit.use_layers))
    )


def _write_net_class(nc: NetClass) -> str:
    # (class <name>
    #   [net ...]          ← bare atoms, wrapped at column 80
    #   (clearance_class ...)
    #   (via_rule ...)
    #   (rule ...)
    #   (circuit ...)
    # )
    children: list[str] = []

    if nc.nets:
        # Wrap long net lists the same way KiCad does: groups of ~8 per line.
        chunk_size = 8
        for i in range(0, len(nc.nets), chunk_size):
            children.append(" ".join(_atom(n) for n in nc.nets[i : i + chunk_size]))

    children.append(_inline("clearance_class", _atom(nc.clearance_class)))
    children.append(_inline("via_rule", _atom(nc.via_rule)))
    if nc.rules:
        children.append(_write_rule_block(nc.rules))
    children.append(_write_circuit(nc.circuit))

    return _block(f"class {_atom(nc.name)}", *children)


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

    children.extend(_write_padstack(ps) for ps in rules.padstacks)
    children.extend(_write_via(v) for v in rules.vias)
    children.extend(_write_via_rule(vr) for vr in rules.via_rules)
    children.extend(_write_net_class(nc) for nc in rules.net_classes)

    return _block(f"rules PCB {_atom(rules.design_name)}", *children)
