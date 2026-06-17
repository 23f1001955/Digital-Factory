"""DM/comment automation webhooks and auto-reply."""

import os
import logging

import httpx

logger = logging.getLogger(__name__)

FACEBOOK_API_BASE = "https://graph.facebook.com/v21.0"

SUPPORTED_COMMENT_PLATFORMS = ["facebook", "instagram"]
SUPPORTED_DM_PLATFORMS = ["facebook", "instagram"]

TRIGGER_PHRASES = ["price", "how much", "cost", "discount", "link", "where", "help", "buy", "tutorial"]


def register_comment_webhook(
    platform: str,
    callback_url: str,
    trigger_phrases: list[str] | None = None,
) -> dict:
    if platform not in SUPPORTED_COMMENT_PLATFORMS:
        return {"status": "unsupported", "platform": platform, "message": f"{platform} comment webhooks not supported"}

    token = os.getenv("FACEBOOK_PAGE_TOKEN")
    if not token:
        return {"status": "failed", "message": "FACEBOOK_PAGE_TOKEN not set"}

    try:
        page_id = os.getenv("FACEBOOK_PAGE_ID", "me")
        url = f"{FACEBOOK_API_BASE}/{page_id}/subscribed_apps"
        resp = httpx.post(url, data={
            "access_token": token,
            "subscribed_fields": "feed,comments",
        }, timeout=30.0)
        if resp.status_code == 200:
            return {"status": "registered", "platform": platform, "callback_url": callback_url}
        return {"status": "failed", "message": resp.text}
    except Exception as e:
        logger.warning(f"Comment webhook registration failed: {e}")
        return {"status": "failed", "message": str(e)}


def register_dm_webhook(
    platform: str,
    callback_url: str,
) -> dict:
    if platform not in SUPPORTED_DM_PLATFORMS:
        return {"status": "unsupported", "platform": platform, "message": f"{platform} DM webhooks not supported"}

    token = os.getenv("FACEBOOK_PAGE_TOKEN")
    if not token:
        return {"status": "failed", "message": "FACEBOOK_PAGE_TOKEN not set"}

    try:
        page_id = os.getenv("FACEBOOK_PAGE_ID", "me")
        url = f"{FACEBOOK_API_BASE}/{page_id}/subscribed_apps"
        resp = httpx.post(url, data={
            "access_token": token,
            "subscribed_fields": "conversations,messages",
        }, timeout=30.0)
        if resp.status_code == 200:
            return {"status": "registered", "platform": platform, "callback_url": callback_url}
        return {"status": "failed", "message": resp.text}
    except Exception as e:
        logger.warning(f"DM webhook registration failed: {e}")
        return {"status": "failed", "message": str(e)}


def auto_reply(platform: str, message: str, reply_template: str) -> str:
    msg_lower = message.lower()
    for phrase in TRIGGER_PHRASES:
        if phrase in msg_lower:
            url = os.getenv("GUMROAD_PRODUCT_URL", "")
            return reply_template.replace("{url}", url)
    return reply_template
