import os
import json
import logging
from typing import Optional

import httpx

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

FACEBOOK_API_BASE = "https://graph.facebook.com/v21.0"
PINTEREST_API_BASE = "https://api.pinterest.com/v5"


def _post_to_facebook(page_id: str, page_token: str, message: str, image_url: str = "") -> Optional[dict]:
    """Post to Facebook Page."""
    url = f"{FACEBOOK_API_BASE}/{page_id}/photos" if image_url else f"{FACEBOOK_API_BASE}/{page_id}/feed"
    data = {
        "access_token": page_token,
        "message": message,
    }
    if image_url:
        data["url"] = image_url
    try:
        resp = httpx.post(url, data=data, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Facebook post failed: {e}")
        return None


def _post_to_instagram(ig_user_id: str, page_token: str, caption: str, image_url: str) -> Optional[dict]:
    """Post to Instagram Business Account via Graph API."""
    try:
        create_url = f"{FACEBOOK_API_BASE}/{ig_user_id}/media"
        create_data = {
            "access_token": page_token,
            "image_url": image_url,
            "caption": caption,
        }
        resp = httpx.post(create_url, data=create_data, timeout=30.0)
        resp.raise_for_status()
        container_id = resp.json().get("id")
        if not container_id:
            return None

        publish_url = f"{FACEBOOK_API_BASE}/{ig_user_id}/media_publish"
        publish_data = {
            "access_token": page_token,
            "creation_id": container_id,
        }
        resp = httpx.post(publish_url, data=publish_data, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Instagram post failed: {e}")
        return None


def _post_to_threads(threads_user_id: str, page_token: str, text: str) -> Optional[dict]:
    """Post to Threads via Graph API."""
    try:
        url = f"{FACEBOOK_API_BASE}/{threads_user_id}/threads"
        data = {
            "access_token": page_token,
            "text": text,
        }
        resp = httpx.post(url, data=data, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Threads post failed: {e}")
        return None


def _post_to_pinterest(pinterest_token: str, board_id: str, title: str, description: str, image_url: str, link: str) -> Optional[dict]:
    """Post a Pin to Pinterest."""
    url = f"{PINTEREST_API_BASE}/pins"
    headers = {"Authorization": f"Bearer {pinterest_token}"}
    data = {
        "board_id": board_id,
        "title": title,
        "description": description,
        "media_source": {"source_type": "image_url", "url": image_url},
        "link": link,
    }
    try:
        resp = httpx.post(url, headers=headers, json=data, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Pinterest post failed: {e}")
        return None


def _generate_social_copy(job_spec: JobSpec, gumroad_url: str) -> dict:
    """Generate platform-specific copy using LLM. Falls back to template-based copy if LLM unavailable."""
    from agents.llm_client import generate_text as llm_call

    prompt_lines = [
        f"You are a social media marketing expert. Generate promotional posts for a digital product.",
        f"",
        f"Product: {job_spec.display_name or job_spec.niche}",
        f"Type: {job_spec.product_type.replace('_', ' ').title()}",
        f"Niche: {job_spec.niche}",
        f"Product URL: {gumroad_url}",
        f"CTA: {getattr(job_spec, 'call_to_action', 'Buy Now on Gumroad')}",
        f"",
        f"Generate 4 posts as a JSON object with keys 'instagram', 'threads', 'facebook', 'pinterest'.",
        f"Each value is an object with: 'caption' (string), 'hashtags' (array of strings).",
        f"Pinterest additionally needs a 'title' field.",
        f"",
        f"Instagram: 2-3 sentence caption, 8-12 hashtags, emoji-friendly",
        f"Threads: 1-2 sentence thought-starter, 3-5 hashtags",
        f"Facebook: Paragraph-length post, 5-8 hashtags, link-friendly",
        f"Pinterest: SEO title (max 100 chars), 200-300 char description, 3-5 hashtags",
        f"",
        f"Return ONLY valid JSON, no markdown, no code blocks.",
    ]

    try:
        result = llm_call("\n".join(prompt_lines))
        import re
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        logger.warning(f"Social copy LLM generation failed: {e}")

    cta = getattr(job_spec, 'call_to_action', 'Buy Now on Gumroad')
    name = job_spec.display_name or job_spec.niche
    return {
        "instagram": {
            "caption": f"Introducing {name}! 🚀 Perfect for {job_spec.niche}. {cta} today!",
            "hashtags": ["digitalproduct", job_spec.niche.lower().replace(" ", ""), "gumroad", "productivity"],
        },
        "threads": {
            "caption": f"Just launched {name} -- built for {job_spec.niche}. Check it out!",
            "hashtags": ["digital", job_spec.niche.lower().replace(" ", ""), "newlaunch"],
        },
        "facebook": {
            "caption": f"We're excited to announce {name}, a premium {job_spec.product_type.replace('_', ' ')} for {job_spec.niche}. {cta} at {gumroad_url}",
            "hashtags": ["newproduct", "digitalproducts", job_spec.niche.lower().replace(" ", ""), "gumroad"],
        },
        "pinterest": {
            "title": f"{name} -- {job_spec.product_type.replace('_', ' ').title()} for {job_spec.niche}",
            "caption": f"Discover {name}, the ultimate {job_spec.product_type.replace('_', ' ')} for {job_spec.niche}. Perfect for professionals and creators. {cta}",
            "hashtags": ["digitalproduct", job_spec.niche.lower().replace(" ", ""), "gumroad"],
        },
    }


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        slug = job_spec.slug
        output_dir = os.path.join("outputs", slug, "landing")
        os.makedirs(output_dir, exist_ok=True)

        landing_page_path = context.get("landing_page")
        landing_page_url = ""
        gumroad_url = ""
        if landing_page_path and os.path.exists(landing_page_path):
            with open(landing_page_path, "r", encoding="utf-8") as f:
                landing_data = json.load(f)
            landing_page_url = landing_data.get("deployed_url", "")

        gumroad_publish_path = context.get("gumroad_publish")
        if gumroad_publish_path and os.path.exists(gumroad_publish_path):
            with open(gumroad_publish_path, "r", encoding="utf-8") as f:
                publish_data = json.load(f)
            gumroad_url = publish_data.get("product_url", "")

        copies = _generate_social_copy(job_spec, gumroad_url)

        facebook_token = os.getenv("FACEBOOK_PAGE_TOKEN")
        page_id = os.getenv("FACEBOOK_PAGE_ID", "me")
        ig_user_id = os.getenv("INSTAGRAM_USER_ID", "")
        threads_user_id = os.getenv("THREADS_USER_ID", "")
        pinterest_token = os.getenv("PINTEREST_TOKEN")
        pinterest_board_id = os.getenv("PINTEREST_BOARD_ID", "")

        results = {}

        if facebook_token and copies.get("facebook"):
            fb_result = _post_to_facebook(
                page_id, facebook_token,
                copies["facebook"]["caption"] + "\n\n" + " ".join(f"#{h}" for h in copies["facebook"]["hashtags"]),
            )
            results["facebook"] = "posted" if fb_result else "failed"

        if facebook_token and ig_user_id and copies.get("instagram"):
            ig_result = _post_to_instagram(
                ig_user_id, facebook_token,
                copies["instagram"]["caption"] + "\n\n" + " ".join(f"#{h}" for h in copies["instagram"]["hashtags"]),
                landing_page_url or "",
            )
            results["instagram"] = "posted" if ig_result else "failed"

        if facebook_token and threads_user_id and copies.get("threads"):
            threads_result = _post_to_threads(
                threads_user_id, facebook_token,
                copies["threads"]["caption"] + "\n\n" + " ".join(f"#{h}" for h in copies["threads"]["hashtags"]),
            )
            results["threads"] = "posted" if threads_result else "failed"

        if pinterest_token and pinterest_board_id and copies.get("pinterest"):
            pin_result = _post_to_pinterest(
                pinterest_token, pinterest_board_id,
                copies["pinterest"]["title"],
                copies["pinterest"]["caption"] + "\n\n" + " ".join(f"#{h}" for h in copies["pinterest"]["hashtags"]),
                landing_page_url or "",
                gumroad_url,
            )
            results["pinterest"] = "posted" if pin_result else "failed"

        result = {
            "status": "done",
            "platforms": results,
            "copies": copies,
        }
        output_path = os.path.join("outputs", slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        posted = sum(1 for v in results.values() if v == "posted")
        logger.info(f"Social promotion: {posted}/{len(results)} platforms posted")
        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Social agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
