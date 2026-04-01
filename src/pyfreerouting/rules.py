"""
Pydantic models for the Freerouting DSN (Design Space Notation) `rules` block,
as exported by KiCad for use with the Freerouting autorouter.

Mirrors the s-expression structure:
  (rules PCB <design_name> ...)
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field
from pydantic import BeforeValidator, PlainSerializer


def parse_onoff(v):
    if isinstance(v, str):
        if v == "on":
            return True
        if v == "off":
            return False
    return v


def serialize_onoff(v: bool):
    return "on" if v else "off"


OnOffBool = Annotated[
    bool,
    BeforeValidator(parse_onoff),
    PlainSerializer(serialize_onoff, return_type=str),
]

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SnapAngle(str, Enum):
    fortyfive_degree = "fortyfive_degree"
    ninety_degree = "ninety_degree"


class PreferredDirection(str, Enum):
    horizontal = "horizontal"
    vertical = "vertical"


# ---------------------------------------------------------------------------
# autoroute_settings
# ---------------------------------------------------------------------------


class LayerRule(BaseModel):
    """
    (layer_rule <layer_name>
      (active on|off)
      (preferred_direction horizontal|vertical)
      (preferred_direction_trace_costs <float>)
      (against_preferred_direction_trace_costs <float>)
    )
    """

    layer_name: str = Field(
        description="Copper layer identifier, e.g. 'F.Cu' or 'B.Cu'."
    )
    active: OnOffBool = Field(
        description="Whether the autorouter is allowed to use this layer."
    )
    preferred_direction: PreferredDirection = Field(
        description="Preferred trace direction on this layer."
    )
    preferred_direction_trace_costs: float = Field(
        description="Cost multiplier for traces running in the preferred direction."
    )
    against_preferred_direction_trace_costs: float = Field(
        description="Cost multiplier for traces running against the preferred direction."
    )


class AutorouteSettings(BaseModel):
    """
    (autoroute_settings
      (fanout on|off)
      (autoroute on|off)
      (postroute on|off)
      (vias on|off)
      (via_costs <int>)
      (plane_via_costs <int>)
      (start_ripup_costs <int>)
      (start_pass_no <int>)
      (layer_rule ...) ...
    )
    """

    fanout: OnOffBool = True
    autoroute: OnOffBool = True
    postroute: OnOffBool = True
    vias: OnOffBool = True
    via_costs: int = 100
    plane_via_costs: int = 100
    start_ripup_costs: int = 25
    start_pass_no: int = 20
    layer_rules: list[LayerRule] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Clearance / Rule
# ---------------------------------------------------------------------------


class ClearanceRule(BaseModel):
    """
    (clearance <value_um> [(type <clearance_type>)])
    """

    type: Literal["clearance"] = "clearance"
    value_um: float = Field(description="Minimum clearance distance in micrometres.")
    subtype: Optional[str] = Field(
        default=None,
        description="Optional named clearance context. None = default clearance.",
    )


class WidthRule(BaseModel):
    """
    (width <width_um>)
    """

    type: Literal["width"] = "width"
    width_um: float = Field(description="Default trace width in micrometres.")


AnyRule = Annotated[
    Union[ClearanceRule, WidthRule],
    Field(discriminator="type"),
]

# ---------------------------------------------------------------------------
# Top-level Rules block
# ---------------------------------------------------------------------------


class PCBRules(BaseModel):
    """
    (rules PCB <design_name>
      (snap_angle ...)
      (autoroute_settings ...)
      (rule ...)
      (padstack ...) ...
      (via ...) ...
      (via_rule ...) ...
      (class ...) ...
    )
    We ignore the via types and net rules here as those are set directly in kicad and exported in the DSN
    """

    design_name: str = "default"
    snap_angle: SnapAngle = SnapAngle.fortyfive_degree
    autoroute_settings: AutorouteSettings = Field(
        default_factory=lambda: AutorouteSettings()
    )
    rules: list[AnyRule] = Field(default_factory=list)


class FreeroutingCmdLine(BaseModel):
    """
    -de : input file
    -di : input directory
    -do : output file
    -dr : rules file
    -mp : max passes: int
    -mt : max number of threads: int
    -oit : optimization_improvement_threshold: float
    -us : update strategy: str
    -is : item selection strategy
    -hr : hybrid_ratio
    -l : language: str
    -im : snapshots: int
    -test :
    -dl : disable logging
    -da : disable analytics
    -host : ?
    -help
    -inc : ignore_net_classes
    -dct : dialog_confirmation_timeout
    """

    max_passes: int = 100
    max_number_of_threads: Optional[int] = None
    optimization_improvement_threshold: float = 0.5
    update_strategy: Literal["Greedy", "Global", "Hybrid"] = "Greedy"
    hybrid_ratio: tuple[int, int] = (2, 1)
    item_selection_strategy: Literal["sequential", "random", "prioritized"] = (
        "prioritized"
    )
    language: str = "en"
    snapshots: int = 0
    disable_logging: bool = False
    disable_analytics: bool = False
    ignore_net_classes: bool = False
    dialog_confirmation_timeout: float = 0

    def to_flags(self) -> list[str]:
        flag_map = {
            "max_passes": "-mp",
            "max_number_of_threads": "-mt",
            "optimization_improvement_threshold": "-oit",
            "update_strategy": "-us",
            "item_selection_strategy": "-is",
            "hybrid_ratio": "-hr",
            "language": "-l",
            "snapshots": "-im",
            "disable_logging": "-dl",
            "disable_analytics": "-da",
            "ignore_net_classes": "-inc",
            "dialog_confirmation_timeout": "-dct",
        }

        flags: list[str] = []

        for field, flag in flag_map.items():
            value = getattr(self, field)

            # Skip None
            if value is None:
                continue

            # hr ration
            if isinstance(value, tuple):
                flags.append(f"{value[0]}:{value[1]}")
                continue

            # Booleans → flag only if True
            if isinstance(value, bool):
                if value:
                    flags.append(flag)
                continue

            # Everything else → flag + value
            flags.extend([flag, str(value)])

        return flags
