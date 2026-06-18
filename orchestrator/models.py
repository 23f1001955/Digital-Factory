from typing import Any, List, Literal, Dict, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class ComponentSpec(BaseModel):
    id: str
    agent: str
    output: str
    depends_on: List[str] = Field(default_factory=list)
    uses_renderer: bool = False
    template: Optional[str] = None
    format: Literal["full", "guide", "notion", "prompt", "resource"] = "full"
    delivery: List[str] = Field(default_factory=lambda: ["zip"])
    capabilities: List[str] = Field(default_factory=list)
    active_formats: List[str] = Field(default_factory=list)


class ProductSchema(BaseModel):
    product_type: str
    display_name: str
    components: List[ComponentSpec]
    notion_sync: bool = False
    notion_structure: Optional[dict] = None


class JobSpec(BaseModel):
    slug: str
    product_type: str
    niche: str
    display_name: Optional[str] = None
    theme: str = "default"
    notion_sync: bool = False
    notion_only: bool = False
    notion_parent_page_id: Optional[str] = None
    landing_page_enabled: bool = False
    social_promotion_enabled: bool = False
    channels: List[ChannelConfig] = Field(default_factory=lambda: [ChannelConfig(name="gumroad", enabled=True)])
    landing_page_url: Optional[str] = None
    call_to_action: str = "Buy Now on Gumroad"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("channels", mode="before")
    @classmethod
    def _validate_channels(cls, v: Any) -> Any:
        if isinstance(v, list):
            return [ChannelConfig(**item) if isinstance(item, dict) else item for item in v]
        return v


class AgentResult(BaseModel):
    status: Literal["pending", "running", "done", "failed", "skipped"]
    output_path: Optional[str] = None
    error: Optional[str] = None
    output_paths: Optional[Dict[str, str]] = None


class PipelineComponent(BaseModel):
    id: str
    agent: str
    output: str
    depends_on: List[str] = Field(default_factory=list)
    uses_renderer: bool = False
    template: Optional[str] = None
    format: Literal["full", "guide", "notion", "prompt", "resource"] = "full"
    delivery: List[str] = Field(default_factory=lambda: ["zip"])
    capabilities: List[str] = Field(default_factory=list)
    active_formats: List[str] = Field(default_factory=list)


class PipelinePlan(BaseModel):
    components: List[PipelineComponent]


class JobState(BaseModel):
    slug: str
    components: Dict[str, AgentResult] = Field(default_factory=dict)


class ChannelConfig(BaseModel):
    name: str
    enabled: bool = True
    config: dict = Field(default_factory=dict)


class QualityIssue(BaseModel):
    category: str = "general"
    severity: str = "warning"  # "error" | "warning" | "info"
    message: str
    location: Optional[str] = None


class QualityReport(BaseModel):
    component_id: str
    score: float = 0.0
    threshold: float = 0.6
    issues: List[QualityIssue] = Field(default_factory=list)
    hallucination_flags: List[str] = Field(default_factory=list)
    needs_human_review: bool = False
    fix_prompt: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.score >= self.threshold
