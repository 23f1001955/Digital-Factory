from pydantic import BaseModel, Field


class LandingPattern(BaseModel):
    name: str = ""
    section_order: list[str] = Field(default_factory=list)
    cta_placement: str = ""
    color_strategy: str = ""
    recommended_effects: str = ""


class DesignBrief(BaseModel):
    design_vibe: str = "default"
    landing_pattern: LandingPattern | None = None
    system_prompt_block: str = ""
