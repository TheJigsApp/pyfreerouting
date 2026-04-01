import unittest
import json
from pathlib import Path
from pyfreerouting.rules import AutorouteSettings, LayerRule, OnOff, PCBRules, SnapAngle
from pyfreerouting.rules import *
from pyfreerouting.parser import parse_rules
from pyfreerouting import parser
import sexpdata


class TestFreeRoutingRules(unittest.TestCase):
    def test_parse_name(self):
        name = "test-name.dsn"
        result = parse_rules(f"(rules PCB {name}\n)")
        self.assertEqual(result.design_name, name)

    def test_parse_snap_angle(self):
        name = "test-name.dsn"
        result = parse_rules(f"""(rules PCB {name}
(snap_angle
    fortyfive_degree
)
)""")
        self.assertEqual(result.design_name, name)
        self.assertEqual(result.snap_angle, SnapAngle.fortyfive_degree)

    def test_parse_autoroute_settings(self):
        sexprs = sexpdata.loads("""(design (autoroute_settings
    (fanout off)
    (autoroute on)
    (postroute on)
    (vias off)
    (via_costs 50)
    (plane_via_costs 5)
    (start_ripup_costs 100)
    (start_pass_no 1)
    (layer_rule F.Cu
      (active on)
      (preferred_direction vertical)
      (preferred_direction_trace_costs 1.0)
      (against_preferred_direction_trace_costs 3.6)
    )
  ))""")

        node = parser._find(sexprs, "autoroute_settings")
        result = parser._parse_autoroute_settings(node)
        settings = AutorouteSettings(
            fanout=OnOff.off,
            autoroute=OnOff.on,
            postroute=OnOff.on,
            vias=OnOff.off,
            via_costs=50,
            plane_via_costs=5.0,
            start_ripup_costs=100.0,
            start_pass_no=1,
            layer_rules=[
                LayerRule(
                    layer_name="F.Cu",
                    active=OnOff.on,
                    preferred_direction=PreferredDirection.vertical,
                    preferred_direction_trace_costs=1.0,
                    against_preferred_direction_trace_costs=3.6,
                )
            ],
        )
        self.assertEqual(result, settings)

    @unittest.skip("")
    def test_smoke_test(self):
        sample_text = (
            Path(__file__).parent / "data" / "rules-2-layers.rules"
        ).read_text()
        self.assertGreater(len(sample_text), 0)
        self.assertIsInstance(sample_text, str)

        result = parse_rules(sample_text)
        self.assertIsInstance(result, PCBRules)
        print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    unittest.main()
