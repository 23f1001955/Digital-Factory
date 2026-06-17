"""Engagement tracking and metrics for social posts."""

import os
import logging
from datetime import datetime

import httpx

from agents.social.models import SocialPost, PostResult, EngagementMetrics

logger = logging.getLogger(__name__)

FACEBOOK_API_BASE = "https://graph.facebook.com/v21.0"


def track_post(post: SocialPost, result: PostResult) -> EngagementMetrics:
    return EngagementMetrics(
        post_id=post.id,
        platform=post.platform,
    )


def get_post_metrics(external_id: str, platform: str) -> EngagementMetrics:
    if platform in ("facebook", "instagram"):
        token = os.getenv("FACEBOOK_PAGE_TOKEN")
        if not token:
            return EngagementMetrics(post_id=external_id, platform=platform)
        try:
            url = f"{FACEBOOK_API_BASE}/{external_id}/insights"
            params = {
                "access_token": token,
                "metric": "likes,comments,shares,impressions,reach",
            }
            resp = httpx.get(url, params=params, timeout=30.0)
            if resp.status_code == 200:
                data = resp.json()
                likes = 0
                comments = 0
                shares = 0
                impressions = 0
                for item in data.get("data", []):
                    name = item.get("name", "")
                    values = item.get("values", [])
                    val = values[0].get("value", 0) if values else 0
                    if name == "likes":
                        likes = int(val)
                    elif name == "comments":
                        comments = int(val)
                    elif name == "shares":
                        shares = int(val)
                    elif name == "impressions":
                        impressions = int(val)
                return EngagementMetrics(
                    post_id=external_id,
                    platform=platform,
                    likes=likes,
                    comments=comments,
                    shares=shares,
                    impressions=impressions,
                )
        except Exception as e:
            logger.warning(f"Failed to get metrics for {external_id} on {platform}: {e}")

    return EngagementMetrics(post_id=external_id, platform=platform)


def calculate_engagement_rate(metrics: EngagementMetrics) -> float:
    if metrics.impressions <= 0:
        return 0.0
    total = metrics.likes + metrics.comments + metrics.shares
    if total <= 0:
        return 0.0
    return round((total / metrics.impressions) * 100, 2)
