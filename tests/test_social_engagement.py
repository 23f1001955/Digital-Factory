from agents.social.models import SocialPost, PostResult, EngagementMetrics
from agents.social.engagement import track_post, get_post_metrics, calculate_engagement_rate


def test_track_post_returns_metrics():
    post = SocialPost(id="p1", platform="instagram", content="Test")
    result = PostResult(post_id="p1", platform="instagram", status="posted", external_id="ext123")
    metrics = track_post(post, result)
    assert isinstance(metrics, EngagementMetrics)
    assert metrics.post_id == "p1"
    assert metrics.platform == "instagram"


def test_track_post_failed():
    post = SocialPost(id="p2", platform="facebook")
    result = PostResult(post_id="p2", platform="facebook", status="failed")
    metrics = track_post(post, result)
    assert metrics.likes == 0


def test_get_post_metrics_no_token(monkeypatch):
    monkeypatch.delenv("FACEBOOK_PAGE_TOKEN", raising=False)
    metrics = get_post_metrics("ext_id", "facebook")
    assert isinstance(metrics, EngagementMetrics)
    assert metrics.likes == 0
    assert metrics.impressions == 0


def test_get_post_metrics_unknown_platform():
    metrics = get_post_metrics("ext_id", "unknown")
    assert metrics.likes == 0


def test_calculate_engagement_rate():
    metrics = EngagementMetrics(likes=100, comments=20, shares=30, impressions=10000)
    rate = calculate_engagement_rate(metrics)
    assert rate == 1.5


def test_calculate_engagement_rate_zero_impressions():
    metrics = EngagementMetrics()
    rate = calculate_engagement_rate(metrics)
    assert rate == 0.0


def test_calculate_engagement_rate_no_interactions():
    metrics = EngagementMetrics(impressions=5000)
    rate = calculate_engagement_rate(metrics)
    assert rate == 0.0
