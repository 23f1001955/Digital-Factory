"""Platform-specific content strategy rules and adaptation."""

from agents.social.models import SocialPost

PLATFORM_RULES: dict = {
    "instagram": {
        "max_hashtags": 30, "image_required": True,
        "character_limit": 2200,
        "best_times": ["7-9am", "6-8pm"],
        "content_style": "visual_first",
    },
    "facebook": {
        "max_hashtags": 10, "image_required": False,
        "character_limit": 63206,
        "best_times": ["9-11am", "1-3pm"],
        "content_style": "conversational",
    },
    "threads": {
        "max_hashtags": 10, "image_required": False,
        "character_limit": 500,
        "best_times": ["8-10am", "7-9pm"],
        "content_style": "text_first",
    },
    "pinterest": {
        "max_hashtags": 20, "image_required": True,
        "character_limit": 500,
        "best_times": ["8-11am", "2-4pm"],
        "content_style": "evergreen",
    },
}


def get_best_posting_times(platform: str) -> list[str]:
    rules = PLATFORM_RULES.get(platform)
    return rules.get("best_times", []) if rules else []


def get_platform_limits(platform: str) -> dict:
    defaults = {"max_hashtags": 30, "image_required": False, "character_limit": 5000, "best_times": []}
    rules = PLATFORM_RULES.get(platform)
    if not rules:
        return defaults
    return {k: rules.get(k, defaults[k]) for k in defaults}


def adapt_post_for_platform(post: SocialPost, platform: str) -> SocialPost:
    limits = get_platform_limits(platform)
    max_chars = limits.get("character_limit", 5000)
    max_tags = limits.get("max_hashtags", 30)
    adapted = SocialPost(
        id=post.id,
        platform=platform,
        content=post.content[:max_chars] if len(post.content) > max_chars else post.content,
        media_urls=post.media_urls,
        hashtags=post.hashtags[:max_tags],
        scheduled_at=post.scheduled_at,
        sequence=post.sequence,
        day=post.day,
        status=post.status,
        angle=post.angle,
    )
    return adapted
