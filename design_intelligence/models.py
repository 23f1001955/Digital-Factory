from typing import Optional
from pydantic import BaseModel, Field


class LandingPattern(BaseModel):
    name: str = ""
    section_order: list[str] = Field(default_factory=list)
    cta_placement: str = ""
    color_strategy: str = ""
    recommended_effects: str = ""


class DesignBrief(BaseModel):
    design_vibe: str = "default"
    landing_pattern: Optional[LandingPattern] = None
    system_prompt_block: str = ""
    source: str = "design-intelligence"
