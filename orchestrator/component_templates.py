from typing import List, Dict, Optional, Any
from orchestrator.models import ComponentSpec

COMPONENT_TEMPLATES: Dict[str, dict] = {
    "case_study": {
        "agent": "content_agent",
        "output": "content/{slug}/case_study.md",
        "delivery": ["zip", "gumroad"],
    },
    "comparison_table": {
        "agent": "content_agent",
        "output": "content/{slug}/comparison_table.md",
        "delivery": ["zip", "gumroad"],
    },
    "faq_section": {
        "agent": "content_agent",
        "output": "content/{slug}/faq.md",
        "delivery": ["zip", "gumroad"],
    },
    "resource_list": {
        "agent": "catalog_agent",
        "output": "content/{slug}/resources.json",
        "delivery": ["zip", "gumroad"],
    },
    "step_by_step_guide": {
        "agent": "content_agent",
        "output": "content/{slug}/guide.md",
        "delivery": ["zip", "gumroad"],
    },
    "checklist": {
        "agent": "content_agent",
        "output": "content/{slug}/checklist.md",
        "delivery": ["zip", "gumroad"],
    },
}

LOCKED_FIELDS = {"id", "agent", "output"}


def validate_template(name: str) -> bool:
    return name in COMPONENT_TEMPLATES


def list_templates() -> List[str]:
    return sorted(COMPONENT_TEMPLATES.keys())


def resolve_template(name: str, overrides: Optional[Dict[str, Any]] = None) -> ComponentSpec:
    if name not in COMPONENT_TEMPLATES:
        raise ValueError(f"Unknown template: {name}")
    tmpl = COMPONENT_TEMPLATES[name]
    overrides = overrides or {}
    allowed_overrides = {k: v for k, v in overrides.items() if k not in LOCKED_FIELDS}
    return ComponentSpec(
        id=name,
        agent=tmpl["agent"],
        output=tmpl["output"],
        depends_on=allowed_overrides.get("depends_on", []),
        delivery=allowed_overrides.get("delivery", list(tmpl["delivery"])),
        format=allowed_overrides.get("format", "full"),
        template=name,
    )
