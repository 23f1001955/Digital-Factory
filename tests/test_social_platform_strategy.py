from agents.social.models import SocialPost
from agents.social.platform_strategy import (
    adapt_post_for_platform, get_best_posting_times, get_platform_limits, PLATFORM_RULES
)


def test_platform_rules_defined():
    assert "instagram" in PLATFORM_RULES
    assert "facebook" in PLATFORM_RULES
    assert "threads" in PLATFORM_RULES
    assert "pinterest" in PLATFORM_RULES


def test_get_best_posting_times():
    times = get_best_posting_times("instagram")
    assert isinstance(times, list)
    assert len(times) > 0


def test_get_best_posting_times_unknown():
    times = get_best_posting_times("tiktok")
    assert times == []


def test_get_platform_limits():
    limits = get_platform_limits("instagram")
    assert limits["max_hashtags"] == 30
    assert limits["image_required"] is True
    assert limits["character_limit"] == 2200


def test_get_platform_limits_unknown():
    limits = get_platform_limits("unknown")
    assert limits["max_hashtags"] == 30
    assert limits["image_required"] is False
    assert limits["character_limit"] == 5000
    assert limits["best_times"] == []


def test_adapt_post_truncates_content():
    post = SocialPost(content="A" * 5000, platform="instagram")
    adapted = adapt_post_for_platform(post, "instagram")
    assert len(adapted.content) <= 2200


def test_adapt_post_threads_limit():
    post = SocialPost(content="B" * 1000, platform="threads")
    adapted = adapt_post_for_platform(post, "threads")
    assert len(adapted.content) <= 500


def test_adapt_post_no_truncation():
    post = SocialPost(content="Short post", platform="facebook")
    adapted = adapt_post_for_platform(post, "facebook")
    assert adapted.content == "Short post"


def test_adapt_post_returns_post():
    post = SocialPost(content="Test", platform="instagram")
    adapted = adapt_post_for_platform(post, "instagram")
    assert isinstance(adapted, SocialPost)
    assert adapted.platform == "instagram"


def test_adapt_post_truncates_hashtags():
    post = SocialPost(content="Test", platform="facebook", hashtags=[f"#tag{i}" for i in range(20)])
    adapted = adapt_post_for_platform(post, "facebook")
    assert len(adapted.hashtags) <= 10
