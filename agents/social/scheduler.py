"""Post scheduling and dispatch."""

import os
import json
import logging
from datetime import datetime
from agents.social.models import SocialPost, ContentCalendar, PostResult

logger = logging.getLogger(__name__)

POST_QUEUE_DIR = "outputs/{slug}/social/queue"


def queue_posts(calendar: ContentCalendar, slug: str = "") -> None:
    queue_dir = POST_QUEUE_DIR.format(slug=slug)
    os.makedirs(queue_dir, exist_ok=True)
    for post in calendar.posts:
        post_path = os.path.join(queue_dir, f"{post.id}.json")
        try:
            with open(post_path, "w", encoding="utf-8") as f:
                json.dump({
                    "id": post.id,
                    "platform": post.platform,
                    "content": post.content,
                    "media_urls": post.media_urls,
                    "hashtags": post.hashtags,
                    "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
                    "sequence": post.sequence,
                    "day": post.day,
                    "status": post.status,
                    "angle": post.angle,
                }, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to queue post {post.id}: {e}")


def dequeue_due(slug: str = "") -> list[SocialPost]:
    queue_dir = POST_QUEUE_DIR.format(slug=slug)
    if not os.path.isdir(queue_dir):
        return []

    now = datetime.now()
    due: list[SocialPost] = []

    for fname in os.listdir(queue_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(queue_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read queue file {fpath}: {e}")
            continue

        scheduled_str = data.get("scheduled_at")
        if scheduled_str:
            try:
                scheduled = datetime.fromisoformat(scheduled_str)
            except (ValueError, TypeError):
                scheduled = now
        else:
            scheduled = now

        if scheduled <= now:
            due.append(SocialPost(
                id=data.get("id", ""),
                platform=data.get("platform", ""),
                content=data.get("content", ""),
                media_urls=data.get("media_urls", []),
                hashtags=data.get("hashtags", []),
                scheduled_at=scheduled,
                sequence=data.get("sequence", "launch"),
                day=data.get("day", 0),
                status=data.get("status", "draft"),
                angle=data.get("angle", ""),
            ))
            try:
                os.remove(fpath)
            except OSError:
                pass

    return due


def dispatch(post: SocialPost) -> PostResult:
    try:
        from agents.social_agent import _post_to_facebook, _post_to_instagram, _post_to_threads, _post_to_pinterest

        platform = post.platform
        content = post.content
        media_url = post.media_urls[0] if post.media_urls else ""

        result: dict | None = None
        if platform == "facebook":
            fb_token = os.getenv("FACEBOOK_PAGE_TOKEN")
            fb_page_id = os.getenv("FACEBOOK_PAGE_ID", "me")
            if fb_token:
                result = _post_to_facebook(fb_page_id, fb_token, content, media_url)
        elif platform == "instagram":
            fb_token = os.getenv("FACEBOOK_PAGE_TOKEN")
            ig_id = os.getenv("INSTAGRAM_USER_ID")
            if fb_token and ig_id:
                result = _post_to_instagram(ig_id, fb_token, content, media_url)
        elif platform == "threads":
            fb_token = os.getenv("FACEBOOK_PAGE_TOKEN")
            threads_id = os.getenv("THREADS_USER_ID")
            if fb_token and threads_id:
                result = _post_to_threads(threads_id, fb_token, content, media_url)
        elif platform == "pinterest":
            pin_token = os.getenv("PINTEREST_TOKEN")
            board_id = os.getenv("PINTEREST_BOARD_ID", "")
            if pin_token and board_id:
                result = _post_to_pinterest(pin_token, board_id, content[:100], content, media_url, "")

        external_id = None
        if result:
            external_id = result.get("id", result.get("post_id", ""))

        return PostResult(
            post_id=post.id,
            platform=platform,
            status="posted" if result else "failed",
            external_id=external_id,
            posted_at=datetime.now() if result else None,
        )
    except Exception as e:
        logger.warning(f"Dispatch failed for {post.id}: {e}")
        return PostResult(post_id=post.id, platform=post.platform, status="failed", error=str(e))
