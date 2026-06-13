import os
import json
import time
import base64
import logging
from typing import Optional, TypedDict

import httpx

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL = "gemini-2.0-flash-exp"


class ImageRequirement(TypedDict):
    id: str
    purpose: str
    aspect_ratio: str


def _call_gemini(prompt: str, api_key: str) -> Optional[bytes]:
    """Generate an image using Gemini. Returns PNG bytes or None."""
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


def _call_imagen(prompt: str, api_url: str, api_key: str, aspect_ratio: str = "16:9") -> Optional[bytes]:
    """Generate an image using the Imagen Cloudflare Worker (nano-banana-2). Returns JPEG bytes or None."""
    payload = {
        "model": "google/nano-banana-2",
        "prompt": prompt,
        "negative_prompt": "no plastic skin, no CGI, no airbrushing, no studio lighting, no beauty filters, no skin smoothing, no stylized realism, no digital art",
        "aspect_ratio": aspect_ratio,
        "resolution": "4K",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(api_url, headers=headers, json=payload, timeout=120.0)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "image" in content_type or len(resp.content) > 1024:
            return resp.content
        logger.warning(f"Imagen returned non-image response: {resp.text[:200]}")
        return None
    except Exception as e:
        logger.warning(f"Imagen image generation failed: {e}")
        return None


def _generate_placeholder(output_path: str, text: str, width: int, height: int):
    """Generate a simple SVG placeholder when Gemini fails."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#667eea"/>
      <stop offset="100%" style="stop-color:#764ba2"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#bg)"/>
  <text x="50%" y="50%" text-anchor="middle" dy=".1em"
        font-family="sans-serif" font-size="{min(width, height) // 15}px"
        fill="white" font-weight="600">{text}</text>
</svg>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg)
    logger.info(f"Placeholder SVG generated: {output_path}")


def generate_from_prompt(prompt_text: str, output_path: str, aspect_ratio: str = "1:1") -> str:
    """Generate a single image from an existing prompt text (no LLM step).

    Uses Imagen → Gemini → SVG fallback chain.
    Returns the file path actually written (may be .jpg, .png, or .svg).

    Useful for agents that already have pre-generated prompts (e.g. visual_agent).
    """
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    imagen_url = os.getenv("IMAGEN_API_URL")
    imagen_key = os.getenv("IMAGEN_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    aspect_sizes = {
        "16:9": (1920, 1080), "1:1": (800, 800), "2:3": (1000, 1500),
        "9:16": (1080, 1920), "4:5": (1000, 1250), "3:2": (1500, 1000),
    }
    width, height = aspect_sizes.get(aspect_ratio, (800, 800))

    if imagen_url and imagen_key:
        img_bytes = _call_imagen(prompt_text, imagen_url, imagen_key, aspect_ratio)
        if img_bytes:
            path = output_path.rsplit(".", 1)[0] + ".jpg"
            with open(path, "wb") as f:
                f.write(img_bytes)
            logger.info(f"Generated image via Imagen: {path}")
            return path

    if gemini_key:
        img_bytes = _call_gemini(prompt_text, gemini_key)
        if img_bytes:
            path = output_path.rsplit(".", 1)[0] + ".png"
            with open(path, "wb") as f:
                f.write(img_bytes)
            logger.info(f"Generated image via Gemini: {path}")
            return path

    path = output_path.rsplit(".", 1)[0] + ".svg"
    _generate_placeholder(path, "Visual", width, height)
    return path


def _generate_prompt_for_requirement(req: ImageRequirement, niche: str, product_type: str, theme: str, research_data: dict = None) -> str:
    """Use LLM to generate a detailed image prompt for a single requirement."""
    from agents.llm_client import generate_text as llm_call
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader("prompts"))
    template = env.get_template("image_gen.j2")
    llm_prompt = template.render(
        niche=niche,
        product_type=product_type,
        theme=theme,
        purpose=req.get("purpose", ""),
        aspect_ratio=req.get("aspect_ratio", "16:9"),
        market_research=json.dumps(research_data, indent=2)[:3000] if research_data else None,
        all_images=False,
    )

    try:
        result = llm_call(llm_prompt)
        result = result.strip().strip('"').strip("'")
        if result and len(result) > 20:
            return result
    except Exception as e:
        logger.warning(f"LLM prompt generation failed for '{req['id']}': {e}")

    return f"A premium {product_type} image for {niche}, {req['purpose']}, {req['aspect_ratio']}, professional, clean, modern"


def generate_images(
    requirements: list[ImageRequirement],
    niche: str,
    product_type: str,
    theme: str = "default",
    research_data: dict = None,
    output_dir: str = "",
) -> dict[str, str]:
    """Generate images for arbitrary runtime requirements.

    Each requirement produces one image via Imagen → Gemini → SVG fallback chain.
    Returns {req['id'] → absolute file path}.

    Any agent can import and call this directly.
    """
    os.makedirs(output_dir, exist_ok=True)

    imagen_url = os.getenv("IMAGEN_API_URL")
    imagen_key = os.getenv("IMAGEN_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    aspect_sizes = {
        "16:9": (1920, 1080),
        "1:1": (800, 800),
        "2:3": (1000, 1500),
        "9:16": (1080, 1920),
        "4:5": (1000, 1250),
        "3:2": (1500, 1000),
    }

    results: dict[str, str] = {}

    for req in requirements:
        img_id = req["id"]
        ar = req.get("aspect_ratio", "16:9")
        width, height = aspect_sizes.get(ar, (800, 800))

        prompt_text = _generate_prompt_for_requirement(req, niche, product_type, theme, research_data)

        if imagen_url and imagen_key:
            img_bytes = _call_imagen(prompt_text, imagen_url, imagen_key, ar)
            if img_bytes:
                file_path = os.path.join(output_dir, f"{img_id}.jpg")
                with open(file_path, "wb") as f:
                    f.write(img_bytes)
                results[img_id] = file_path
                logger.info(f"Generated '{img_id}' via Imagen")
                continue

        if gemini_key:
            img_bytes = _call_gemini(prompt_text, gemini_key)
            if img_bytes:
                file_path = os.path.join(output_dir, f"{img_id}.png")
                with open(file_path, "wb") as f:
                    f.write(img_bytes)
                results[img_id] = file_path
                logger.info(f"Generated '{img_id}' via Gemini")
                time.sleep(60)
                continue

        file_path = os.path.join(output_dir, f"{img_id}.svg")
        _generate_placeholder(file_path, f"{niche}\n{img_id}", width, height)
        results[img_id] = file_path

    return results


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        slug = job_spec.slug
        output_dir = os.path.join("outputs", slug, "assets")
        os.makedirs(output_dir, exist_ok=True)

        research_data = None
        research_path = context.get("market_research")
        if research_path and os.path.exists(research_path):
            with open(research_path, "r", encoding="utf-8") as f:
                research_data = json.load(f)

        requirements: list[ImageRequirement] = [
            {"id": "cover", "purpose": "Product cover image for Gumroad listing", "aspect_ratio": "16:9"},
            {"id": "thumbnail", "purpose": "Square product thumbnail for Gumroad preview", "aspect_ratio": "1:1"},
        ]

        images = generate_images(
            requirements=requirements,
            niche=job_spec.niche,
            product_type=job_spec.product_type,
            theme=getattr(job_spec, "theme", "default"),
            research_data=research_data,
            output_dir=output_dir,
        )

        output = {
            "status": "done",
            "images": images,
        }
        output_path = os.path.join("outputs", slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Image agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
