# ===========================================================================
# S-expression walker
# ===========================================================================
# Requires:  pip install sexpdata
#
# The `sexpdata` library parses s-expressions into nested Python lists.
# Atoms are represented as sexpdata.Symbol objects (for unquoted tokens) or
# plain Python str/int/float for literals.
# ===========================================================================

from .rules import *
import sexpdata  # type: ignore


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


def _parse_layer_rule(node: list) -> LayerRule:
    # (layer_rule <name> (active ...) (preferred_direction ...) ...)
    layer_name = _sym(node[1])
    active = OnOff(_sym(_find(node, "active")[1]))
    pdir = PreferredDirection(_sym(_find(node, "preferred_direction")[1]))
    pd_cost = float(_find(node, "preferred_direction_trace_costs")[1])
    apd_cost = float(_find(node, "against_preferred_direction_trace_costs")[1])
    return LayerRule(
        layer_name=layer_name,
        active=active,
        preferred_direction=pdir,
        preferred_direction_trace_costs=pd_cost,
        against_preferred_direction_trace_costs=apd_cost,
    )


def _parse_autoroute_settings(node: list) -> AutorouteSettings:
    return AutorouteSettings(
        fanout=OnOff(_sym(_find(node, "fanout")[1])),
        autoroute=OnOff(_sym(_find(node, "autoroute")[1])),
        postroute=OnOff(_sym(_find(node, "postroute")[1])),
        vias=OnOff(_sym(_find(node, "vias")[1])),
        via_costs=int(_find(node, "via_costs")[1]),
        plane_via_costs=int(_find(node, "plane_via_costs")[1]),
        start_ripup_costs=int(_find(node, "start_ripup_costs")[1]),
        start_pass_no=int(_find(node, "start_pass_no")[1]),
        layer_rules=[_parse_layer_rule(lr) for lr in _find_all(node, "layer_rule")],
    )


def _parse_clearance(node: list) -> ClearanceRule:
    # (clearance <value> [(type <name>)])
    value = float(node[1])
    type_node = _find(node, "type")
    ctype = _sym(type_node[1]) if type_node else None
    return ClearanceRule(value_um=value, subtype=ctype)


def _parse_rule(node: list) -> list[AnyRule]:
    width_node = _find(node, "width")

    rules = []
    if width_node:
        rules.append(WidthRule(width_um=float(width_node[1])))
    rules.extend(_parse_clearance(c) for c in _find_all(node, "clearance"))
    return rules


def _parse_padshape(node: list) -> PadShape:
    # (circle <layer> <diameter> <x> <y>)
    return PadShape(
        layer=_sym(node[1]),
        diameter_um=float(node[2]),
        x=float(node[3]),
        y=float(node[4]),
    )


def _parse_padstack(node: list) -> Padstack:
    # (padstack <name> (shape (circle ...)) ... (attach on|off))
    name = _sym(node[1])
    shapes = [
        _parse_padshape(_find(shape_node, "circle"))
        for shape_node in _find_all(node, "shape")
    ]
    attach = OnOff(_sym(_find(node, "attach")[1]))
    return Padstack(name=name, shapes=shapes, attach=attach)


def _parse_via(node: list) -> Via:
    # (via <padstack_name> <padstack_ref> <net_class>)
    return Via(
        padstack_name=_sym(node[1]),
        padstack_ref=_sym(node[2]),
        net_class=_sym(node[3]),
    )


def _parse_via_rule(node: list) -> ViaRule:
    # (via_rule <net_class> <via_name>)
    return ViaRule(net_class=_sym(node[1]), via_name=_sym(node[2]))


def _parse_circuit(node: list) -> Circuit:
    use_layer_node = _find(node, "use_layer")
    layers = [_sym(t) for t in use_layer_node[1:]] if use_layer_node else []
    return Circuit(use_layers=layers)


def _parse_net_class(node: list) -> NetClass:
    """
    (class <name>
      [<net_name> ...]       ← bare atoms that are net names
      (clearance_class ...)
      (via_rule ...)
      (rule ...)
      (circuit ...)
    )
    """
    name = _sym(node[1])

    # Collect bare net-name atoms (everything between the class name and the
    # first sub-list that is a recognised keyword sub-block).
    sub_keywords = {"clearance_class", "via_rule", "rule", "circuit"}
    nets: list[str] = []
    for token in node[2:]:
        if isinstance(token, list):
            break  # hit first sub-block → stop
        nets.append(_sym(token))

    clearance_class = _sym(_find(node, "clearance_class")[1])
    via_rule = _sym(_find(node, "via_rule")[1])
    rule = _parse_rule(_find(node, "rule"))
    circuit = _parse_circuit(_find(node, "circuit"))

    return NetClass(
        name=name,
        nets=nets,
        clearance_class=clearance_class,
        via_rule=via_rule,
        rules=rule,
        circuit=circuit,
    )


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def parse_rules(sexp_text: str) -> PCBRules:
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
    rules = PCBRules(design_name=design_name)
    try:
        rules.snap_angle = SnapAngle(_sym(_find(node, "snap_angle")[1]))
    except TypeError:
        pass
    try:
        rules.autoroute_settings = _parse_autoroute_settings(
            _find(node, "autoroute_settings")
        )
    except TypeError:
        pass
    try:
        rules.rules = _parse_rule(_find(node, "rule"))
    except TypeError:
        pass
    try:
        rules.padstacks = [_parse_padstack(p) for p in _find_all(node, "padstack")]
    except TypeError:
        pass
    try:
        rules.vias = [_parse_via(v) for v in _find_all(node, "via")]
    except TypeError:
        pass
    try:
        rules.via_rules = [_parse_via_rule(vr) for vr in _find_all(node, "via_rule")]
    except TypeError:
        pass
    try:
        rules.net_classes = [_parse_net_class(c) for c in _find_all(node, "class")]
    except TypeError:
        pass

    return rules
