"""
Pydantic models for the Freerouting DSN (Design Space Notation) `rules` block,
as exported by KiCad for use with the Freerouting autorouter.

Mirrors the s-expression structure:
  (rules PCB <design_name> ...)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Discriminator, Field, NonNegativeFloat


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SnapAngle(str, Enum):
    fortyfive_degree = "fortyfive_degree"
    ninety_degree = "ninety_degree"


class OnOff(str, Enum):
    on = "on"
    off = "off"


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
    active: OnOff = Field(
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

    fanout: OnOff = OnOff.on
    autoroute: OnOff = OnOff.on
    postroute: OnOff = OnOff.on
    vias: OnOff = OnOff.on
    via_costs: int = 100
    plane_via_costs: int = 100
    start_ripup_costs: int = 25
    start_pass_no: int = 20
    layer_rules: list[LayerRule] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Clearance / Rule
# ---------------------------------------------------------------------------
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field


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
# Padstack
# ---------------------------------------------------------------------------


class PadShape(BaseModel):
    """(circle <layer> <diameter_um> <x> <y>)"""

    layer: str
    diameter_um: float
    x: float = 0.0
    y: float = 0.0


class Padstack(BaseModel):
    """
    (padstack <name>
      (shape (circle ...)) ...
      (attach on|off)
    )
    """

    name: str
    shapes: list[PadShape] = Field(default_factory=list)
    attach: OnOff


# ---------------------------------------------------------------------------
# Via / ViaRule
# ---------------------------------------------------------------------------


class Via(BaseModel):
    """(via <padstack_name> <padstack_ref> <net_class>)"""

    padstack_name: str
    padstack_ref: str
    net_class: str


class ViaRule(BaseModel):
    """(via_rule <net_class> <via_name>)"""

    net_class: str
    via_name: str


# ---------------------------------------------------------------------------
# Circuit / NetClass
# ---------------------------------------------------------------------------


class Circuit(BaseModel):
    """(circuit (use_layer <layer> ...))"""

    use_layers: list[str] = Field(default_factory=list)


class NetClass(BaseModel):
    """
    (class <name>
      [<net_name> ...]           ← NEW: nets assigned to this class
      (clearance_class <name>)
      (via_rule <name>)
      (rule ...)
      (circuit ...)
    )

    `nets` holds the bare net names that appear before the sub-blocks,
    e.g. GND, "NET_2", etc.
    """

    name: str
    nets: list[str] = Field(
        default_factory=list,
        description="Net names assigned to this class (appear before sub-blocks).",
    )
    clearance_class: str
    via_rule: str
    rules: list[AnyRule]
    circuit: Circuit


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
    """

    design_name: str
    snap_angle: SnapAngle = SnapAngle.fortyfive_degree
    autoroute_settings: AutorouteSettings = Field(
        default_factory=lambda: AutorouteSettings()
    )
    rules: list[AnyRule] = Field(default_factory=list)
    padstacks: list[Padstack] = Field(default_factory=list)
    vias: list[Via] = Field(default_factory=list)
    via_rules: list[ViaRule] = Field(default_factory=list)
    net_classes: list[NetClass] = Field(default_factory=list)
