import json
import os
import pytest
from unittest import mock
from orchestrator.models import ComponentSpec, JobSpec, AgentResult


def test_offer_scoring_agent_enriches_market_research(tmp_path):
    """Agent reads market_research.json, adds scored_recommendations, writes back."""
    research = {
        "niche": "test niche",
        "product_type": "discovery",
        "google_trends": {"trend_direction": "rising", "interest_over_time": {"2025-01-01": 60}},
        "competitor_landscape": {
            "direct_competitors": [{"name": "Comp", "price": 29}],
            "pricing_tiers": {"budget": "$5-15", "mid": "$15-35", "premium": "$35-100"},
            "quality_gaps": ["Gap"],
            "recommended_price": 20,
        },
        "content_recommendations": {"tone": "professional", "key_themes": ["test"], "seo_keywords": ["test"]},
    }
    research_path = tmp_path / "data" / "market_research.json"
    os.makedirs(research_path.parent, exist_ok=True)
    with open(research_path, "w") as f:
        json.dump(research, f)

    component = ComponentSpec(
        id="offer_scoring",
        agent="offer_scoring_agent",
        output="data/market_research.json",
        depends_on=["market_research"],
    )
    job_spec = JobSpec(
        slug="test-slug",
        product_type="discovery",
        niche="test niche",
    )
    context = {"market_research": str(research_path)}

    from agents.offer_scoring_agent import run
    result = run(component, job_spec, context)

    assert result.status == "done"
    assert result.output_path == str(research_path)

    with open(research_path) as f:
        updated = json.load(f)

    assert "scored_recommendations" in updated
    recs = updated["scored_recommendations"]
    assert len(recs) > 0
    assert all("product_type" in r for r in recs)
    assert all("total_score" in r for r in recs)
    scores = [r["total_score"] for r in recs]
    assert scores == sorted(scores, reverse=True)


def test_offer_scoring_agent_missing_file(tmp_path):
    """If market_research.json doesn't exist, agent returns failed."""
    component = ComponentSpec(
        id="offer_scoring",
        agent="offer_scoring_agent",
        output="data/market_research.json",
        depends_on=["market_research"],
    )
    job_spec = JobSpec(
        slug="test-slug",
        product_type="discovery",
        niche="test niche",
    )
    context = {"market_research": str(tmp_path / "nonexistent.json")}

    from agents.offer_scoring_agent import run
    result = run(component, job_spec, context)

    assert result.status == "failed"
    assert "not found" in (result.error or "").lower()
