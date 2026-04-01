import unittest
import json
from pathlib import Path
import sexpdata

from pyfreerouting.rules import (
    AnyRule,
    ClearanceRule,
    Circuit,
    NetClass,
    OnOff,
    Padstack,
    PadShape,
    PCBRules,
    PreferredDirection,
    SnapAngle,
    Via,
    ViaRule,
    WidthRule,
)
from pyfreerouting import parser
from pyfreerouting.parser import parse_rules
from pyfreerouting import writer


class TestFreeRoutingRules(unittest.TestCase):
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load(self, sexp: str, key: str) -> list:
        """Parse a wrapper s-expression and find the first child by key."""
        return parser._find(sexpdata.loads(sexp), key)

    def test_parse_name(self):
        result = parse_rules("(rules PCB test-name.dsn\n)")
        self.assertEqual(result.design_name, "test-name.dsn")

    def test_parse_snap_angle(self):
        result = parse_rules("(rules PCB test-name.dsn (snap_angle fortyfive_degree))")
        self.assertEqual(result.snap_angle, SnapAngle.fortyfive_degree)

    # ------------------------------------------------------------------
    # ClearanceRule
    # ------------------------------------------------------------------

    def test_parse_clearance_default(self):
        """(clearance 200.0) → subtype is None."""
        node = self._load("(root (clearance 200.0))", "clearance")
        result = parser._parse_clearance(node)
        self.assertEqual(result, ClearanceRule(value_um=200.0, subtype=None))

    def test_parse_clearance_with_subtype(self):
        """(clearance 50.0 (type smd)) → subtype='smd'."""
        node = self._load("(root (clearance 50.0 (type smd)))", "clearance")
        result = parser._parse_clearance(node)
        self.assertEqual(result, ClearanceRule(value_um=50.0, subtype="smd"))

    def test_parse_clearance_quoted_subtype(self):
        """(clearance 200.0 (type \"kicad_default\")) → subtype='kicad_default'."""
        node = self._load(
            '(root (clearance 200.0 (type "kicad_default")))', "clearance"
        )
        result = parser._parse_clearance(node)
        self.assertEqual(result, ClearanceRule(value_um=200.0, subtype="kicad_default"))

    # ------------------------------------------------------------------
    # WidthRule / _parse_rule
    # ------------------------------------------------------------------

    def test_parse_rule_width_only(self):
        node = self._load("(root (rule (width 200.0)))", "rule")
        result = parser._parse_rule(node)
        self.assertEqual(result, [WidthRule(width_um=200.0)])

    def test_parse_rule_mixed(self):
        """Top-level rule block: one width + four clearances."""
        node = self._load(
            """(root (rule
                (width 200.0)
                (clearance 200.0)
                (clearance 100.0 (type smd_to_turn_gap))
                (clearance 50.0 (type smd))
                (clearance 200.0 (type "kicad_default"))
            ))""",
            "rule",
        )
        result = parser._parse_rule(node)
        self.assertEqual(
            result,
            [
                WidthRule(width_um=200.0),
                ClearanceRule(value_um=200.0, subtype=None),
                ClearanceRule(value_um=100.0, subtype="smd_to_turn_gap"),
                ClearanceRule(value_um=50.0, subtype="smd"),
                ClearanceRule(value_um=200.0, subtype="kicad_default"),
            ],
        )

    def test_parse_rule_no_width(self):
        """A rule block with only clearances and no width."""
        node = self._load("(root (rule (clearance 150.0)))", "rule")
        result = parser._parse_rule(node)
        self.assertEqual(result, [ClearanceRule(value_um=150.0, subtype=None)])

    # ------------------------------------------------------------------
    # PadShape / Padstack
    # ------------------------------------------------------------------

    def test_parse_padshape(self):
        circle = self._load("(root (shape (circle F.Cu 600.0 0.0 0.0)))", "shape")
        result = parser._parse_padshape(parser._find(circle, "circle"))
        self.assertEqual(
            result,
            PadShape(layer="F.Cu", diameter_um=600.0, x=0.0, y=0.0),
        )

    def test_parse_padstack(self):
        node = self._load(
            '(root (padstack "Via[0-1]_600:300_um"'
            "  (shape (circle F.Cu 600.0 0.0 0.0))"
            "  (shape (circle B.Cu 600.0 0.0 0.0))"
            "  (attach off)"
            "))",
            "padstack",
        )
        result = parser._parse_padstack(node)
        self.assertEqual(
            result,
            Padstack(
                name="Via[0-1]_600:300_um",
                shapes=[
                    PadShape(layer="F.Cu", diameter_um=600.0, x=0.0, y=0.0),
                    PadShape(layer="B.Cu", diameter_um=600.0, x=0.0, y=0.0),
                ],
                attach=OnOff.off,
            ),
        )

    # ------------------------------------------------------------------
    # Via / ViaRule
    # ------------------------------------------------------------------

    def test_parse_via_unquoted_net_class(self):
        node = self._load(
            '(root (via "Via[0-1]_600:300_um" "Via[0-1]_600:300_um" default))',
            "via",
        )
        result = parser._parse_via(node)
        self.assertEqual(
            result,
            Via(
                padstack_name="Via[0-1]_600:300_um",
                padstack_ref="Via[0-1]_600:300_um",
                net_class="default",
            ),
        )

    def test_parse_via_quoted_net_class(self):
        node = self._load(
            '(root (via "Via[0-1]_600:300_um-kicad_default"'
            '           "Via[0-1]_600:300_um" "kicad_default"))',
            "via",
        )
        result = parser._parse_via(node)
        self.assertEqual(
            result,
            Via(
                padstack_name="Via[0-1]_600:300_um-kicad_default",
                padstack_ref="Via[0-1]_600:300_um",
                net_class="kicad_default",
            ),
        )

    def test_parse_via_rule(self):
        node = self._load('(root (via_rule default "Via[0-1]_600:300_um"))', "via_rule")
        result = parser._parse_via_rule(node)
        self.assertEqual(
            result, ViaRule(net_class="default", via_name="Via[0-1]_600:300_um")
        )

    def test_parse_via_rule_quoted(self):
        node = self._load(
            '(root (via_rule "kicad_default" "Via[0-1]_600:300_um-kicad_default"))',
            "via_rule",
        )
        result = parser._parse_via_rule(node)
        self.assertEqual(
            result,
            ViaRule(
                net_class="kicad_default",
                via_name="Via[0-1]_600:300_um-kicad_default",
            ),
        )

    # ------------------------------------------------------------------
    # Circuit
    # ------------------------------------------------------------------

    def test_parse_circuit(self):
        node = self._load("(root (circuit (use_layer F.Cu B.Cu)))", "circuit")
        result = parser._parse_circuit(node)
        self.assertEqual(result, Circuit(use_layers=["F.Cu", "B.Cu"]))

    def test_parse_circuit_empty(self):
        node = self._load("(root (circuit))", "circuit")
        result = parser._parse_circuit(node)
        self.assertEqual(result, Circuit(use_layers=[]))

    # ------------------------------------------------------------------
    # NetClass
    # ------------------------------------------------------------------

    def test_parse_net_class_default(self):
        """'default' class has no bare net names."""
        node = self._load(
            """(root (class default
                (clearance_class default)
                (via_rule default)
                (rule (width 200.0))
                (circuit (use_layer F.Cu B.Cu))
            ))""",
            "class",
        )
        result = parser._parse_net_class(node)
        self.assertEqual(
            result,
            NetClass(
                name="default",
                nets=[],
                clearance_class="default",
                via_rule="default",
                rules=[WidthRule(width_um=200.0)],
                circuit=Circuit(use_layers=["F.Cu", "B.Cu"]),
            ),
        )

    def test_parse_net_class_with_nets(self):
        """'kicad_default' class carries bare net names before sub-blocks."""
        node = self._load(
            '(root (class "kicad_default"'
            '  GND "NET_2" "NET_3"'
            '  (clearance_class "kicad_default")'
            '  (via_rule "kicad_default")'
            "  (rule (width 200.0))"
            "  (circuit (use_layer F.Cu B.Cu))"
            "))",
            "class",
        )
        result = parser._parse_net_class(node)
        self.assertEqual(result.name, "kicad_default")
        self.assertEqual(result.nets, ["GND", "NET_2", "NET_3"])
        self.assertEqual(result.clearance_class, "kicad_default")
        self.assertEqual(result.via_rule, "kicad_default")
        self.assertEqual(result.rules, [WidthRule(width_um=200.0)])
        self.assertEqual(result.circuit, Circuit(use_layers=["F.Cu", "B.Cu"]))

    # ------------------------------------------------------------------
    # Full file smoke test
    # ------------------------------------------------------------------

    def test_smoke_test(self):
        sample_text = (
            Path(__file__).parent / "data" / "rules-2-layers.rules"
        ).read_text()
        result = parse_rules(sample_text)

        self.assertIsInstance(result, PCBRules)
        self.assertEqual(result.design_name, "board.dsn")
        self.assertEqual(result.snap_angle, SnapAngle.fortyfive_degree)

        # autoroute_settings
        ar = result.autoroute_settings
        self.assertEqual(ar.via_costs, 50)
        self.assertEqual(ar.start_pass_no, 1)
        self.assertEqual(len(ar.layer_rules), 2)
        self.assertEqual(ar.layer_rules[0].layer_name, "F.Cu")
        self.assertEqual(
            ar.layer_rules[1].preferred_direction, PreferredDirection.horizontal
        )

        # top-level rules
        self.assertEqual(len(result.rules), 5)
        self.assertIsInstance(result.rules[0], WidthRule)
        self.assertEqual(result.rules[0].width_um, 200.0)
        self.assertIsInstance(result.rules[1], ClearanceRule)
        self.assertIsNone(result.rules[1].subtype)
        self.assertEqual(result.rules[3].subtype, "smd")

        # padstacks
        self.assertEqual(len(result.padstacks), 1)
        ps = result.padstacks[0]
        self.assertEqual(ps.name, "Via[0-1]_600:300_um")
        self.assertEqual(len(ps.shapes), 2)
        self.assertEqual(ps.shapes[0].layer, "F.Cu")
        self.assertEqual(ps.shapes[0].diameter_um, 600.0)

        # vias
        self.assertEqual(len(result.vias), 2)
        self.assertEqual(result.vias[0].net_class, "default")
        self.assertEqual(result.vias[1].net_class, "kicad_default")

        # via_rules
        self.assertEqual(len(result.via_rules), 2)
        self.assertEqual(result.via_rules[0].net_class, "default")
        self.assertEqual(
            result.via_rules[1].via_name, "Via[0-1]_600:300_um-kicad_default"
        )

        # net classes
        self.assertEqual(len(result.net_classes), 2)
        default_cls = result.net_classes[0]
        self.assertEqual(default_cls.name, "default")
        self.assertEqual(default_cls.nets, [])
        self.assertEqual(default_cls.circuit.use_layers, ["F.Cu", "B.Cu"])

        kicad_cls = result.net_classes[1]
        self.assertEqual(kicad_cls.name, "kicad_default")
        self.assertIn("GND", kicad_cls.nets)
        self.assertEqual(len(kicad_cls.nets), 39)

    def test_round_trip(self):
        sample_text = (
            Path(__file__).parent / "data" / "rules-2-layers.rules"
        ).read_text()
        result = parse_rules(sample_text)
        result_text = writer.write_rules(rules=result)
        print(result_text)
        reparsed_result = parse_rules(result_text)
        print(result)
        print(reparsed_result)
        self.assertEqual(result, reparsed_result)


if __name__ == "__main__":
    unittest.main()
