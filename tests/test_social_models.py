from datetime import datetime, timedelta
from agents.social.models import (
    SocialPost,
    ContentCalendar,
    PostResult,
    EngagementMetrics,
    PlatformConfig,
)


def test_social_post_defaults():
    p = SocialPost()
    assert p.id
    assert len(p.id) == 12
    assert p.status == "draft"
    assert p.platform == ""


def test_social_post_with_values():
    p = SocialPost(platform="instagram", content="Hello", status="scheduled")
    assert p.platform == "instagram"
    assert p.content == "Hello"
    assert p.status == "scheduled"


def test_content_calendar_defaults():
    cal = ContentCalendar(niche="ai", product_type="research_pack")
    assert cal.niche == "ai"
    assert cal.days == 14
    assert cal.posts == []


def test_content_calendar_with_posts():
    posts = [SocialPost(platform="facebook"), SocialPost(platform="instagram")]
    cal = ContentCalendar(niche="test", product_type="pack", posts=posts)
    assert len(cal.posts) == 2


def test_post_result_defaults():
    r = PostResult()
    assert r.status == "failed"


def test_post_result_success():
    r = PostResult(post_id="abc", platform="twitter", status="posted", external_id="123")
    assert r.status == "posted"
    assert r.external_id == "123"


def test_engagement_metrics_defaults():
    m = EngagementMetrics()
    assert m.likes == 0
    assert m.comments == 0


def test_platform_config_defaults():
    c = PlatformConfig(platform="instagram")
    assert c.platform == "instagram"
    assert c.max_hashtags == 30


def test_social_post_with_hashtags_and_angle():
    p = SocialPost(platform="instagram", content="Post", hashtags=["#ai", "#tech"], angle="statistic")
    assert p.hashtags == ["#ai", "#tech"]
    assert p.angle == "statistic"
