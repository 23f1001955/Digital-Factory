from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LandingPattern:
    name: str
    section_order: list[str] = field(default_factory=list)
    cta_placement: str = ""
    color_strategy: str = ""
    recommended_effects: str = ""


@dataclass
class DesignBrief:
    design_vibe: str = "default"
    landing_pattern: Optional[LandingPattern] = None
    system_prompt_block: str = ""
    source: str = "design-intelligence"
