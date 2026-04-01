import unittest
import json
from pathlib import Path
import sexpdata

from pyfreerouting.rules import (
    ClearanceRule,
    PCBRules,
    PreferredDirection,
    SnapAngle,
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
