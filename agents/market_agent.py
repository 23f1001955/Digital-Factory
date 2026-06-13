import os
import json
import logging
from typing import Optional

import httpx

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

GUMROAD_API_BASE = "https://api.gumroad.com/v2"


def _fetch_seller_products() -> list:
    """Fetch the authenticated seller's products from Gumroad API."""
    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        logger.warning("GUMROAD_ACCESS_TOKEN not set -- skipping API fetch")
        return []
    try:
        url = f"{GUMROAD_API_BASE}/products"
        headers = {"Authorization": f"Bearer {token}"}
        resp = httpx.get(url, headers=headers, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        products = data.get("products", [])
        logger.info(f"Fetched {len(products)} seller products from Gumroad")
        return [
            {
                "name": p.get("name", ""),
                "price": p.get("price", 0),
                "sales": p.get("sales_count", 0),
                "url": p.get("short_url", ""),
            }
            for p in products
        ]
    except Exception as e:
        logger.warning(f"Gumroad API fetch failed: {e}")
        return []


def _generate_research(niche: str, product_type: str, seller_products: list) -> dict:
    """Generate market research using LLM."""
    from agents.llm_client import generate_text as llm_call
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader("prompts"))
    template = env.get_template("market_research.j2")
    prompt = template.render(
        niche=niche,
        product_type=product_type,
        seller_products=seller_products,
    )

    try:
        result = llm_call(prompt)
        import re
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            research = json.loads(match.group())
            logger.info(f"Market research generated: {len(research.get('competitor_landscape', {}).get('direct_competitors', []))} competitors found")
            return research
    except Exception as e:
        logger.warning(f"LLM market research failed: {e}")

    return _fallback_research(niche, product_type)


def _fallback_research(niche: str, product_type: str) -> dict:
    """Minimal fallback when LLM is unavailable."""
    return {
        "niche": niche,
        "product_type": product_type,
        "competitor_landscape": {
            "direct_competitors": [],
            "pricing_tiers": {"budget": "$5-15", "mid": "$15-35", "premium": "$35-100"},
            "recommended_price": 29,
            "quality_gaps": ["Research this niche for specific gaps"],
            "trending_keywords": [niche.lower().replace(" ", "_")],
        },
        "content_recommendations": {
            "tone": "professional",
            "key_themes": ["quality", "expertise", "results"],
            "seo_keywords": [niche.lower()],
        },
    }


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        niche = job_spec.niche
        product_type = job_spec.product_type

        seller_products = _fetch_seller_products()
        research = _generate_research(niche, product_type, seller_products)

        research["niche"] = niche
        research["product_type"] = product_type
        research["seller_products"] = seller_products

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(research, f, indent=2)

        logger.info(f"Market research written to {output_path}")
        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Market agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
