import json
import os
import pytest
from unittest import mock
from orchestrator.models import ComponentSpec, JobSpec, AgentResult
from orchestrator.scoring import ScoringFramework, ScoredOffer, ScoringMetric
from agents.offer_scoring_agent import run


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

    result = run(component, job_spec, context)

    assert result.status == "failed"
    assert "not found" in (result.error or "").lower()


def test_offer_scoring_agent_with_mocked_scoring(tmp_path, monkeypatch):
    """Unit test: mock scoring framework to return controlled output."""
    from agents.offer_scoring_agent import run as agent_run
    from orchestrator.scoring import ScoringFramework, ScoredOffer, ScoringMetric

    research = {"niche": "test"}
    research_path = tmp_path / "data" / "market_research.json"
    os.makedirs(research_path.parent, exist_ok=True)
    with open(research_path, "w") as f:
        json.dump(research, f)

    mock_offer = ScoredOffer(
        product_type="checklist",
        display_name="Checklist",
        total_score=92.0,
        confidence=0.9,
        metrics=[ScoringMetric(name="test", weight=1.0, score=0.92, reasoning="Mocked")],
        reasoning="Mocked best offer",
    )
    mock_framework = ScoringFramework(offers=[mock_offer], source_data=research)

    import agents.offer_scoring_agent as osa_mod
    monkeypatch.setattr(osa_mod, "run_scoring", lambda d, schemas_dir=None: mock_framework)

    component = ComponentSpec(
        id="offer_scoring", agent="offer_scoring_agent",
        output="data/market_research.json", depends_on=["market_research"],
    )
    job_spec = JobSpec(slug="test-slug", product_type="discovery", niche="test")
    context = {"market_research": str(research_path)}

    result = agent_run(component, job_spec, context)
    assert result.status == "done"

    with open(research_path) as f:
        updated = json.load(f)
    assert updated["recommended_product_type"] == "checklist"
    assert updated["recommendation_confidence"] == 0.9
    assert len(updated["scored_recommendations"]) == 1
    assert updated["scored_recommendations"][0]["total_score"] == 92.0
