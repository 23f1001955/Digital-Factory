import os
import json
import re
import urllib.parse
import logging

import httpx

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

GUMROAD_API_BASE = "https://api.gumroad.com/v2"


def _gumroad_form_api(method: str, path: str, data: dict | None = None) -> dict | None:
    """Call Gumroad API with form-encoded data and access_token."""
    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        logger.warning("GUMROAD_ACCESS_TOKEN not set")
        return None
    url = f"{GUMROAD_API_BASE}/{path.lstrip('/')}"
    form_data = {"access_token": token}
    if data:
        form_data.update(data)
    try:
        if method == "GET":
            resp = httpx.request(method, url, params=form_data, timeout=60.0)
        else:
            resp = httpx.request(method, url, data=form_data, timeout=60.0)
        if resp.status_code == 200:
            return resp.json()
        logger.warning(
            f"Gumroad API {method} {path} -> {resp.status_code}: {resp.text[:300]}"
        )
        return None
    except Exception as e:
        logger.warning(f"Gumroad API call failed ({method} {path}): {e}")
        return None


def _to_rails_params(obj, prefix=""):
    """Convert nested dict/list to Rails-style form params list of (key, value) tuples."""
    items = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            new_prefix = f"{prefix}[{key}]" if prefix else key
            items.extend(_to_rails_params(val, new_prefix))
    elif isinstance(obj, list):
        for val in obj:
            items.extend(_to_rails_params(val, f"{prefix}[]"))
    elif obj is None:
        pass
    elif isinstance(obj, bool):
        items.append((prefix, "true" if obj else "false"))
    else:
        items.append((prefix, str(obj)))
    return items



def _generate_tags(niche: str, product_type: str) -> list[str]:
    """Generate product tags from niche and product type."""
    tags = set()
    for kw in niche.lower().split():
        cleaned = kw.strip(",.!?")
        if cleaned:
            tags.add(cleaned)
    ptype_readable = product_type.replace("_", " ").title()
    tags.add(ptype_readable)
    tags.add("Digital Product")
    tags.add("Download")
    return sorted(tags)[:8]



def _get_gumroad_username() -> str:
    """Get Gumroad username from env var or derive from API."""
    username = os.getenv("GUMROAD_USERNAME")
    if username:
        return username
    user_data = _gumroad_form_api("GET", "user")
    if user_data and "user" in user_data:
        return user_data["user"].get("subdomain", "")
    return ""


def _run_research(
    component: ComponentSpec, job_spec: JobSpec, context: dict
) -> AgentResult:
    niche = job_spec.niche

    products_data = _gumroad_form_api("GET", "products")
    niche_products = []
    if products_data and "products" in products_data:
        for p in products_data["products"]:
            name = (p.get("name") or "").lower()
            desc = (p.get("description") or "").lower()
            if any(kw in name or kw in desc for kw in niche.lower().split()):
                niche_products.append(p)

    type_keywords = {
        "operating_system": ["operating system", "os", "workflow system", "dashboard"],
        "research_pack": ["research", "report", "market analysis", "guide"],
        "visual_pack": ["visual", "design", "template pack", "assets", "graphics"],
        "workflow_kit": ["workflow", "automation", "pipeline", "sop"],
        "blog_kit": ["blog", "content pack", "article", "seo"],
        "course_launch": [
            "course",
            "training",
            "workshop",
            "masterclass",
            "curriculum",
        ],
        "saas_docs": ["documentation", "api docs", "developer", "technical"],
    }
    type_distribution = {}
    for p in niche_products:
        name = (p.get("name") or "").lower()
        matched = False
        for ptype, kws in type_keywords.items():
            if any(kw in name for kw in kws):
                type_distribution[ptype] = type_distribution.get(ptype, 0) + 1
                matched = True
                break
        if not matched:
            type_distribution["research_pack"] = (
                type_distribution.get("research_pack", 0) + 1
            )

    recommended_type = (
        max(type_distribution, key=type_distribution.get)
        if type_distribution
        else "research_pack"
    )

    research = {
        "niche": niche,
        "products_analyzed": len(niche_products),
        "product_type_distribution": type_distribution,
        "recommended_product_type": recommended_type,
        "top_products": [
            {
                "name": p.get("name", ""),
                "price": p.get("price", 0),
                "sales": p.get("sales_count", 0),
                "description_length": len(p.get("description", "") or ""),
            }
            for p in niche_products[:10]
        ],
        "competitor_count": len(niche_products),
    }

    try:
        from agents.llm_client import generate_text as llm_call
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader("prompts"))
        template = env.get_template("gumroad_research.j2")
        llm_prompt = template.render(
            gumroad_data_json=(
                json.dumps(products_data, indent=2)[:8000]
                if products_data
                else "No products found"
            ),
            niche=niche,
            product_type=job_spec.product_type.replace("_", " ").title(),
        )
        llm_analysis = llm_call(llm_prompt)
        research["llm_analysis"] = llm_analysis
        logger.info("LLM-powered Gumroad research analysis completed")
    except Exception as e:
        logger.warning(f"LLM research analysis failed (non-blocking): {e}")
        research["llm_analysis"] = None

    output_path = os.path.join("outputs", job_spec.slug, component.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(research, f, indent=2)

    logger.info(
        f"Gumroad research: {len(niche_products)} products found, recommended type: {recommended_type}"
    )
    return AgentResult(status="done", output_path=output_path, error=None)



def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    if component.id == "gumroad_research":
        return _run_research(component, job_spec, context)
    if component.id == "gumroad_publish":
        return AgentResult(status="skipped", error="gumroad_publish moved to GumroadChannel")
    raise ValueError(f"Unknown gumroad component id: {component.id}")
