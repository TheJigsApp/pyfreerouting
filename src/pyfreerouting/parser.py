# ===========================================================================
# S-expression walker
# ===========================================================================
# Requires:  pip install sexpdata
#
# The `sexpdata` library parses s-expressions into nested Python lists.
# Atoms are represented as sexpdata.Symbol objects (for unquoted tokens) or
# plain Python str/int/float for literals.
# ===========================================================================

import contextlib

import sexpdata  # type: ignore

from . import rules as _rules


def _sym(token) -> str:
    """Coerce a Symbol or str token to a plain str."""
    if isinstance(token, sexpdata.Symbol):
        return token.value()
    return str(token)


def _find(node: list, key: str) -> list | None:
    """Return the first child list whose head matches *key*, or None."""
    for child in node:
        if isinstance(child, list) and child and _sym(child[0]) == key:
            return child
    return None


def _find_all(node: list, key: str) -> list[list]:
    """Return all child lists whose head matches *key*."""
    return [
        child
        for child in node
        if isinstance(child, list) and child and _sym(child[0]) == key
    ]


# ---------------------------------------------------------------------------
# Individual parsers
# ---------------------------------------------------------------------------


def _parse_layer_rule(node: list) -> _rules.LayerRule:
    # (layer_rule <name> (active ...) (preferred_direction ...) ...)
    layer_name = _sym(node[1])
    active = _sym(_find(node, "active")[1])
    pdir = _rules.PreferredDirection(_sym(_find(node, "preferred_direction")[1]))
    pd_cost = float(_find(node, "preferred_direction_trace_costs")[1])
    apd_cost = float(_find(node, "against_preferred_direction_trace_costs")[1])
    return _rules.LayerRule(
        layer_name=layer_name,
        active=active,
        preferred_direction=pdir,
        preferred_direction_trace_costs=pd_cost,
        against_preferred_direction_trace_costs=apd_cost,
    )


def _parse_autoroute_settings(node: list) -> _rules.AutorouteSettings:
    return _rules.AutorouteSettings(
        fanout=bool(_sym(_find(node, "fanout")[1])),
        autoroute=bool(_sym(_find(node, "autoroute")[1])),
        postroute=bool(_sym(_find(node, "postroute")[1])),
        vias=bool(_sym(_find(node, "vias")[1])),
        via_costs=int(_find(node, "via_costs")[1]),
        plane_via_costs=int(_find(node, "plane_via_costs")[1]),
        start_ripup_costs=int(_find(node, "start_ripup_costs")[1]),
        start_pass_no=int(_find(node, "start_pass_no")[1]),
        layer_rules=[_parse_layer_rule(lr) for lr in _find_all(node, "layer_rule")],
    )


def _parse_clearance(node: list) -> _rules.ClearanceRule:
    # (clearance <value> [(type <name>)])
    value = float(node[1])
    type_node = _find(node, "type")
    ctype = _sym(type_node[1]) if type_node else None
    return _rules.ClearanceRule(value_um=value, subtype=ctype)


def _parse_rule(node: list) -> list[_rules.AnyRule]:
    width_node = _find(node, "width")

    rules = []
    if width_node:
        rules.append(_rules.WidthRule(width_um=float(width_node[1])))
    rules.extend(_parse_clearance(c) for c in _find_all(node, "clearance"))
    return rules


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def parse_rules(sexp_text: str) -> _rules.PCBRules:
    """
    Parse a Freerouting DSN *rules* block from its s-expression text
    representation and return a validated :class:`PCBRules` instance.

    Parameters
    ----------
    sexp_text:
        The full s-expression string, e.g. the contents of a ``.rules`` file
        or the ``(rules ...)`` block extracted from a ``.dsn`` file.

    Returns
    -------
    PCBRules
    """
    # sexpdata.loads returns a list; the outer form is (rules PCB <name> ...)
    node: list = sexpdata.loads(sexp_text)

    # node[0] == Symbol("rules"), node[1] == Symbol("PCB"), node[2] == name
    design_name = _sym(node[2])
    rules = _rules.PCBRules(design_name=design_name)
    with contextlib.suppress(TypeError):
        rules.snap_angle = _rules.SnapAngle(_sym(_find(node, "snap_angle")[1]))
    with contextlib.suppress(TypeError):
        rules.autoroute_settings = _parse_autoroute_settings(
            _find(node, "autoroute_settings")
        )
    with contextlib.suppress(TypeError):
        rules.rules = _parse_rule(_find(node, "rule"))

    return rules
