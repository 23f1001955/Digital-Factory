import json
import pytest
from orchestrator.scoring import ScoringMetric, ScoredOffer, ScoringFramework, run


def test_scoring_metric_model():
    m = ScoringMetric(name="search_demand", weight=0.25, score=0.8, reasoning="High trend", data={"avg_interest": 65})
    assert m.name == "search_demand"
    assert m.weight == 0.25
    assert m.score == 0.8
    assert m.weighted_score == 0.2


def test_scored_offer_model():
    offer = ScoredOffer(
        product_type="research_pack",
        display_name="Research Pack",
        total_score=78.5,
        confidence=0.85,
        metrics=[
            ScoringMetric(name="search_demand", weight=0.25, score=0.8, reasoning="High trend", data={}),
            ScoringMetric(name="competition", weight=0.25, score=0.7, reasoning="Moderate", data={}),
        ],
        reasoning="Good fit across all metrics",
    )
    assert offer.total_score == 78.5
    assert len(offer.metrics) == 2


def test_search_demand_score_high():
    research_data = {
        "google_trends": {
            "interest_over_time": {
                "2025-06-01": 80, "2025-07-01": 85, "2025-08-01": 90,
            },
            "trend_direction": "rising",
        },
    }
    from orchestrator.scoring import _calc_search_demand
    metric = _calc_search_demand(research_data)
    assert metric.score > 0.7
    assert "rising" in metric.reasoning.lower()


def test_search_demand_score_low():
    research_data = {}
    from orchestrator.scoring import _calc_search_demand
    metric = _calc_search_demand(research_data)
    assert metric.score == 0.5
    assert metric.weight == 0.25


def test_competition_score_low_competitors():
    research_data = {
        "competitor_landscape": {
            "direct_competitors": [
                {"name": "Comp A", "price": 29},
            ],
        },
    }
    from orchestrator.scoring import _calc_competition
    metric = _calc_competition(research_data)
    assert metric.score > 0.6


def test_competition_score_many_competitors():
    research_data = {
        "competitor_landscape": {
            "direct_competitors": [
                {"name": f"Comp {i}", "price": 20} for i in range(20)
            ],
        },
    }
    from orchestrator.scoring import _calc_competition
    metric = _calc_competition(research_data)
    assert metric.score < 0.5


def test_market_viability_score():
    research_data = {
        "competitor_landscape": {
            "direct_competitors": [
                {"name": "Comp A", "price": 10},
                {"name": "Comp B", "price": 15},
            ],
            "pricing_tiers": {"budget": "$5-15", "mid": "$15-35", "premium": "$35-100"},
            "recommended_price": 29,
            "quality_gaps": ["No comprehensive guides available"],
        },
    }
    from orchestrator.scoring import _calc_market_viability
    metric = _calc_market_viability(research_data)
    assert metric.weight == 0.20


def test_content_fit_score():
    research_data = {
        "content_recommendations": {
            "tone": "professional",
            "key_themes": ["quality", "expertise", "results"],
            "seo_keywords": ["test niche"],
        },
    }
    from orchestrator.scoring import _calc_content_fit
    metric = _calc_content_fit(research_data, "research_pack")
    assert metric.weight == 0.15


def test_trend_momentum_score():
    research_data = {
        "google_trends": {
            "trend_direction": "rising",
        },
    }
    from orchestrator.scoring import _calc_trend_momentum
    metric = _calc_trend_momentum(research_data)
    assert metric.score > 0.5


def test_trend_momentum_score_declining():
    research_data = {
        "google_trends": {
            "trend_direction": "declining",
        },
    }
    from orchestrator.scoring import _calc_trend_momentum
    metric = _calc_trend_momentum(research_data)
    assert metric.score < 0.5


def test_community_signals_score():
    research_data = {
        "reddit_discussions": [
            {"title": "Post 1", "score": 50, "num_comments": 10},
            {"title": "Post 2", "score": 100, "num_comments": 25},
        ],
    }
    from orchestrator.scoring import _calc_community_signals
    metric = _calc_community_signals(research_data)
    assert metric.weight == 0.05


def test_community_signals_no_data():
    research_data = {}
    from orchestrator.scoring import _calc_community_signals
    metric = _calc_community_signals(research_data)
    assert metric.score == 0.5


def test_run_scoring():
    research_data = {
        "niche": "test niche",
        "google_trends": {"trend_direction": "rising", "interest_over_time": {"2025-01-01": 50}},
        "competitor_landscape": {
            "direct_competitors": [{"name": "Comp", "price": 29}],
            "pricing_tiers": {"budget": "$5-15", "mid": "$15-35", "premium": "$35-100"},
            "quality_gaps": ["Gap"],
            "recommended_price": 20,
        },
        "content_recommendations": {"tone": "professional", "key_themes": ["test"], "seo_keywords": ["test"]},
    }
    framework = run(research_data, schemas_dir=None)
    assert len(framework.offers) > 0
    for offer in framework.offers:
        assert offer.total_score >= 0
        assert offer.total_score <= 100
        assert len(offer.metrics) == 6
    scores = [o.total_score for o in framework.offers]
    assert scores == sorted(scores, reverse=True)


def test_run_with_empty_data():
    framework = run({}, schemas_dir=None)
    assert len(framework.offers) > 0
    for offer in framework.offers:
        assert offer.confidence == 0.5
