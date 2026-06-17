import pytest
from channels.base import AnalyticsData, ProductArtifact
from channels.gumroad_analytics import pull_analytics, score_listing_quality

SAMPLE_RESEARCH = {
    "competitors": [{"name": "Comp A", "price_cents": 1999}],
}

def test_pull_analytics_no_token(monkeypatch):
    monkeypatch.delenv("GUMROAD_ACCESS_TOKEN", raising=False)
    result = pull_analytics("prod_123")
    assert isinstance(result, AnalyticsData)
    assert result.views == 0
    assert result.sales == 0

def test_pull_analytics_returns_model():
    result = pull_analytics("prod_123")
    assert hasattr(result, "product_id")
    assert hasattr(result, "date")

def test_score_listing_quality_no_research():
    artifact = ProductArtifact(
        slug="test", product_type="research_pack", niche="test",
        display_name="Test", files=[],
        description="A" * 300,
        tags=["tag1", "tag2", "tag3", "tag4", "tag5"],
        cover_image="cover.png",
        price_cents=1999,
    )
    score = score_listing_quality(artifact)
    assert isinstance(score.overall_score, float)
    assert 0.0 <= score.overall_score <= 1.0

def test_score_listing_quality_poor():
    artifact = ProductArtifact(
        slug="test", product_type="research_pack", niche="test",
        display_name="Test", files=[],
        description="Short", tags=[], price_cents=0,
    )
    score = score_listing_quality(artifact)
    assert score.overall_score < 0.5
    assert len(score.issues) > 0

def test_score_listing_quality_good():
    artifact = ProductArtifact(
        slug="test", product_type="research_pack", niche="test",
        display_name="Test", files=[],
        description="Attention: This is a critical problem for many professionals who struggle daily. " * 60,  # 300+ words
        tags=["ai", "productivity", "automation", "workflow", "template"],
        cover_image="cover.png",
        price_cents=1999,
    )
    score = score_listing_quality(artifact, SAMPLE_RESEARCH)
    assert score.overall_score >= 0.4

def test_score_listing_quality_description_length():
    short = ProductArtifact(
        slug="test", product_type="research_pack", niche="test",
        display_name="Test", files=[], description="Short desc",
        tags=["a", "b", "c"], cover_image="x.png", price_cents=999,
    )
    score_short = score_listing_quality(short)
    assert score_short.description_score < 0.3

    long = ProductArtifact(
        slug="test", product_type="research_pack", niche="test",
        display_name="Test", files=[],
        description="Attention problem " * 100,
        tags=["a", "b", "c"], cover_image="x.png", price_cents=999,
    )
    score_long = score_listing_quality(long)
    assert score_long.description_score >= 0.5
