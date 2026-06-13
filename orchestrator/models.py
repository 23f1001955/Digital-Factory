from typing import List, Literal, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ComponentSpec(BaseModel):
    id: str
    agent: str
    output: str
    depends_on: List[str] = Field(default_factory=list)
    uses_renderer: bool = False
    template: Optional[str] = None
    format: Literal["full", "guide", "notion"] = "full"

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
    notion_parent_page_id: Optional[str] = None
    landing_page_enabled: bool = False
    social_promotion_enabled: bool = False
    gumroad_enabled: bool = False
    landing_page_url: Optional[str] = None
    call_to_action: str = "Buy Now on Gumroad"
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AgentResult(BaseModel):
    status: Literal["pending", "running", "done", "failed", "skipped"]
    output_path: Optional[str] = None
    error: Optional[str] = None

class JobState(BaseModel):
    slug: str
    components: Dict[str, AgentResult] = Field(default_factory=dict)
