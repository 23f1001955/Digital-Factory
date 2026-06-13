import os
import sys
import json
import time
import base64
import logging
from typing import Optional

import httpx

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL = "gemini-2.0-flash-exp"
STITCH_API_URL = "https://stitch.googleapis.com/mcp"
VERCEL_API_BASE = "https://api.vercel.com"


def _call_gemini(prompt: str, api_key: str) -> Optional[bytes]:
    """Generate an image using Gemini 2.0 Flash (image generation). Returns PNG bytes or None."""
    url = f"{GEMINI_API_BASE}/{GEMINI_MODEL}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["image"]},
    }
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()
        for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            if "inlineData" in part and part["inlineData"].get("mimeType", "").startswith("image/"):
                return base64.b64decode(part["inlineData"]["data"])
        logger.warning("Gemini returned no image data")
        return None
    except Exception as e:
        logger.warning(f"Gemini image generation failed: {e}")
        return None


def _generate_images(niche: str, output_dir: str, gemini_key: str) -> dict:
    """Generate cover image + optional mockups. Returns dict of paths."""
    os.makedirs(output_dir, exist_ok=True)
    images = {}

    cover_prompt = (
        f"A premium, professional product cover image for a digital product about '{niche}'. "
        f"Clean white background, minimalist design, 16:9 aspect ratio. "
        f"The composition should feel modern and trustworthy. "
        f"Use a warm, inviting color palette. No text overlay."
    )
    cover_bytes = _call_gemini(cover_prompt, gemini_key)
    if cover_bytes:
        cover_path = os.path.join(output_dir, "cover.png")
        with open(cover_path, "wb") as f:
            f.write(cover_bytes)
        images["cover"] = cover_path
        logger.info(f"Cover image generated: {cover_path}")
    else:
        logger.warning("Cover image generation failed")

    return images


def _build_stitch_prompt(job_spec: JobSpec, images: dict, gumroad_url: str) -> str:
    """Build a Stitch design prompt from product info and image URLs."""
    cover_url = images.get("cover", "")
    parts = [
        f"Design a premium landing page for a digital product called '{job_spec.display_name or job_spec.niche}'.",
        f"Product type: {job_spec.product_type.replace('_', ' ').title()}",
        f"Niche: {job_spec.niche}",
        f"Theme: {getattr(job_spec, 'theme', 'default')}",
        "",
        "Sections:",
        "1. Hero section with the cover image, product title, and a call-to-action button",
        "2. Features section highlighting key benefits",
        "3. Pricing section showing the product value",
        "4. Footer with minimal branding",
        "",
        f"Cover image URL: {cover_url}",
        f"CTA text: {getattr(job_spec, 'call_to_action', 'Buy Now on Gumroad')}",
        f"Gumroad product URL: {gumroad_url}",
        "",
        "Design requirements:",
        "- Clean, modern, professional aesthetic",
        "- Mobile-responsive layout",
        "- Fast loading (minimal external dependencies)",
        "- Use a cohesive color palette appropriate for the niche",
        "- The CTA button should be prominently visible in the hero section",
    ]
    return "\n".join(parts)


def _call_stitch(prompt: str, stitch_key: str) -> Optional[dict]:
    """Call Google Stitch API to generate a landing page. Returns dict with 'html' and 'screenshot_url'."""
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": stitch_key}
    payload = {
        "tool": "generate_screen_from_text",
        "input": {"text": prompt},
    }
    try:
        sys.stderr.write("  ⏳ Calling Stitch API (1-3 minutes)...\n")
        sys.stderr.flush()
        resp = httpx.post(STITCH_API_URL, headers=headers, json=payload, timeout=300.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Stitch API call failed: {e}")
        return None


def _refine_html(raw_html: str, gumroad_url: str, cta_text: str) -> str:
    """Basic HTML refinement: inject Gumroad CTA button if not present."""
    if 'href="' not in raw_html and gumroad_url:
        cta_button = (
            f'<a href="{gumroad_url}" '
            f'style="display:inline-block;padding:16px 32px;background-color:#000;color:#fff;'
            f'text-decoration:none;border-radius:8px;font-size:18px;font-weight:600;'
            f'margin-top:24px;">{cta_text}</a>'
        )
        if "</body>" in raw_html:
            raw_html = raw_html.replace("</body>", f"{cta_button}\n</body>")
        else:
            raw_html += cta_button
    return raw_html


def _deploy_vercel(html_content: str, slug: str, vercel_token: str) -> Optional[str]:
    """Deploy HTML to Vercel. Returns deployment URL or None."""
    headers = {
        "Authorization": f"Bearer {vercel_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "name": f"df-{slug}",
        "project": f"df-{slug}",
        "files": [
            {
                "file": "index.html",
                "data": base64.b64encode(html_content.encode("utf-8")).decode("utf-8"),
            }
        ],
    }
    try:
        resp = httpx.post(
            f"{VERCEL_API_BASE}/v12/deployments",
            headers=headers,
            json=payload,
            timeout=60.0,
        )
        resp.raise_for_status()
        result = resp.json()
        return result.get("url")
    except Exception as e:
        logger.warning(f"Vercel deploy failed: {e}")
        return None


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        slug = job_spec.slug
        output_dir = os.path.join("outputs", slug, "landing")
        os.makedirs(output_dir, exist_ok=True)

        # 1. Get Gumroad URL from context
        gumroad_publish_path = context.get("gumroad_publish")
        gumroad_url = ""
        if gumroad_publish_path and os.path.exists(gumroad_publish_path):
            with open(gumroad_publish_path, "r", encoding="utf-8") as f:
                publish_data = json.load(f)
            gumroad_url = publish_data.get("product_url", "")

        # 2. Generate images via Gemini
        gemini_key = os.getenv("GEMINI_API_KEY")
        images = {}
        if gemini_key:
            images = _generate_images(job_spec.niche, os.path.join(output_dir, "images"), gemini_key)
        else:
            logger.warning("GEMINI_API_KEY not set -- skipping image generation")

        # 3. Build Stitch prompt
        stitch_prompt = _build_stitch_prompt(job_spec, images, gumroad_url)

        # 4. Call Stitch API
        stitch_key = os.getenv("STITCH_API_KEY")
        stitch_result = None
        if stitch_key:
            stitch_result = _call_stitch(stitch_prompt, stitch_key)
        else:
            logger.warning("STITCH_API_KEY not set -- skipping Stitch API call")

        # 5. Refine HTML
        html_content = ""
        if stitch_result and "html" in stitch_result:
            raw_html = stitch_result["html"]
            html_content = _refine_html(raw_html, gumroad_url, job_spec.call_to_action)
        else:
            # Fallback: use basic template
            from jinja2 import Environment, FileSystemLoader
            env = Environment(loader=FileSystemLoader("templates"))
            template = env.get_template("landing/basic.html.j2")
            html_content = template.render(
                title=job_spec.display_name or job_spec.niche,
                niche=job_spec.niche,
                product_type=job_spec.product_type.replace("_", " ").title(),
                gumroad_url=gumroad_url,
                cta_text=job_spec.call_to_action,
            )

        # Save HTML locally
        html_path = os.path.join(output_dir, "index.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Landing page HTML saved: {html_path}")

        # 6. Deploy to Vercel
        vercel_token = os.getenv("VERCEL_TOKEN")
        deployed_url = None
        if vercel_token:
            deployed_url = _deploy_vercel(html_content, slug, vercel_token)
        else:
            logger.warning("VERCEL_TOKEN not set -- skipping deploy")

        # 7. Write result
        result = {
            "status": "done",
            "html_path": html_path,
            "deployed_url": deployed_url or None,
            "images_generated": list(images.keys()),
            "stitch_used": stitch_result is not None,
        }
        output_path = os.path.join("outputs", slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        logger.info(f"Landing page result: {deployed_url or 'local only'}")
        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Landing agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
