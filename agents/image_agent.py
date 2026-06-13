import os
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


def _generate_prompts(niche: str, product_type: str, theme: str, research_data: dict = None) -> list:
    """Use LLM to generate 3 image prompts."""
    from agents.llm_client import generate_text as llm_call
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader("prompts"))
    template = env.get_template("image_gen.j2")
    prompt = template.render(
        niche=niche,
        product_type=product_type,
        theme=theme,
        market_research=json.dumps(research_data, indent=2) if research_data else None,
    )

    try:
        result = llm_call(prompt)
        import re
        match = re.search(r'\[.*\]', result, re.DOTALL)
        if match:
            prompts = json.loads(match.group())
            if len(prompts) == 3:
                return prompts
    except Exception as e:
        logger.warning(f"LLM image prompt generation failed: {e}")

    return [
        {"id": "cover", "prompt": f"A premium product cover image for {niche}, 16:9, minimalist, professional", "style": "modern"},
        {"id": "thumbnail", "prompt": f"A square product thumbnail for {niche}, 1:1, clean, bold", "style": "modern"},
        {"id": "social", "prompt": f"A vertical promotional image for {niche}, 2:3, engaging, vibrant", "style": "modern"},
    ]


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

        gemini_key = os.getenv("GEMINI_API_KEY")
        image_prompts = _generate_prompts(
            job_spec.niche, job_spec.product_type,
            getattr(job_spec, "theme", "default"),
            research_data,
        )

        sizes = {"cover": (1920, 1080), "thumbnail": (800, 800), "social": (1000, 1500)}
        results = {}

        for img_def in image_prompts:
            img_id = img_def["id"]
            prompt_text = img_def["prompt"]
            width, height = sizes.get(img_id, (800, 800))

            if gemini_key:
                img_bytes = _call_gemini(prompt_text, gemini_key)
                if img_bytes:
                    file_path = os.path.join(output_dir, f"{img_id}.png")
                    with open(file_path, "wb") as f:
                        f.write(img_bytes)
                    results[img_id] = file_path
                    logger.info(f"Generated {img_id}")
                    time.sleep(60)
                    continue

            file_path = os.path.join(output_dir, f"{img_id}.svg")
            _generate_placeholder(file_path, f"{job_spec.niche}\n{img_id}", width, height)
            results[img_id] = file_path

        output = {
            "status": "done",
            "images": results,
            "prompts_used": [p["prompt"] for p in image_prompts],
        }
        output_path = os.path.join("outputs", slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Image agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
