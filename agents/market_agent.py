import os
import json
import logging

from orchestrator.models import ComponentSpec, JobSpec, AgentResult
from agents.research_tools import (
    brave_search,
    duckduckgo_search,
    reddit_search,
    gdelt_news,
    newsapi_headlines,
    pytrends_data,
    firecrawl_scrape,
)

logger = logging.getLogger(__name__)


def _generate_research(
    niche: str, product_type: str, real_data: dict, job_spec: JobSpec
) -> dict:
    """Generate market research using LLM + real data from all sources."""
    from agents.llm_client import generate_text as llm_call
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader("prompts"))
    template = env.get_template("market_research.j2")
    prompt = template.render(
        niche=niche,
        product_type=product_type,
        seller_products=[],
        notion_sync=job_spec.notion_sync,
        real_data=real_data,
    )

    try:
        result = llm_call(prompt)
        import re

        match = re.search(r"\{.*\}", result, re.DOTALL)
        if match:
            research = json.loads(match.group())
            competitors = research.get("competitor_landscape", {}).get(
                "direct_competitors", []
            )
            logger.info(
                f"Market research generated: {len(competitors)} competitors from real data"
            )
            return research
    except Exception as e:
        logger.warning(f"LLM market research failed: {e}")

    return _fallback_research(niche, product_type)


def _fallback_research(niche: str, product_type: str) -> dict:
    """Minimal fallback when LLM is unavailable."""
    return {
        "niche": niche,
        "product_type": product_type,
        "recommended_product_type": "research_pack",
        "recommendation_confidence": 0.3,
        "recommendation_reasoning": "Insufficient data for recommendation \u2014 falling back to research_pack",
        "recommended_formats": {},
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

        real_data = {}
        sources_used = []

        search_results = brave_search(
            f"{niche} {product_type.replace('_', ' ')} tools market", 10
        )
        search_source = "Brave Search"
        if not search_results:
            search_results = duckduckgo_search(
                f"{niche} {product_type.replace('_', ' ')} tools market", 10
            )
            search_source = "DuckDuckGo"
        if search_results:
            real_data["web_search"] = search_results
            sources_used.append(search_source)
            competitor_urls = [r["url"] for r in search_results[:5] if r.get("url")]
            firecrawl_max = int(os.getenv("FIRECRAWL_MAX_PER_RUN", "3"))
            firecrawl_data = {}
            for url in competitor_urls[:firecrawl_max]:
                content = firecrawl_scrape(url)
                if content:
                    firecrawl_data[url] = content
            if firecrawl_data:
                real_data["firecrawl_pages"] = firecrawl_data
                sources_used.append("Firecrawl")

        reddit_results = reddit_search(f"{niche}", 10)
        if reddit_results:
            real_data["reddit_discussions"] = reddit_results
            sources_used.append("Reddit")

        gdelt_results = gdelt_news(niche, 10)
        if gdelt_results:
            real_data["gdelt_news"] = gdelt_results
            sources_used.append("GDelt")

        news_results = newsapi_headlines(niche, 10)
        if news_results:
            real_data["newsapi_articles"] = news_results
            sources_used.append("NewsAPI")

        product_keywords = niche.lower().split()[:3]
        trends_data = pytrends_data(product_keywords)
        if trends_data:
            real_data["google_trends"] = trends_data
            sources_used.append("Google Trends")

        research = _generate_research(niche, product_type, real_data, job_spec)

        research["niche"] = niche
        research["product_type"] = product_type
        research["sources_used"] = sources_used
        research["data_sources"] = real_data

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(research, f, indent=2)

        logger.info(
            f"Market research written to {output_path} (sources: {', '.join(sources_used) or 'none'})"
        )
        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Market agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
