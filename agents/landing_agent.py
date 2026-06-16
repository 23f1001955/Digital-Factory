import os
import json
import base64
import logging

import httpx

from orchestrator.models import ComponentSpec, JobSpec, AgentResult
from agents.image_agent import generate_images, ImageRequirement

logger = logging.getLogger(__name__)

VERCEL_API_BASE = "https://api.vercel.com"


def _generate_html(images: dict, gumroad_url: str, job_spec: JobSpec) -> str:
    """Generate landing page HTML using LLM and the landing_generate.j2 template."""
    from agents.llm_client import generate_text as llm_call
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader("prompts"))
    template = env.get_template("landing_generate.j2")
    prompt = template.render(
        display_name=job_spec.display_name or job_spec.niche,
        niche=job_spec.niche,
        product_type=job_spec.product_type.replace("_", " ").title(),
        images=images,
        cta_text=getattr(job_spec, "call_to_action", "Buy Now on Gumroad"),
        gumroad_url=gumroad_url,
    )
    result = llm_call(prompt)
    if result and ("<html" in result.lower() or "<!doctype" in result.lower()):
        return result
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("landing/basic.html.j2")
    return template.render(
        title=job_spec.display_name or job_spec.niche,
        niche=job_spec.niche,
        product_type=job_spec.product_type.replace("_", " ").title(),
        gumroad_url=gumroad_url,
        cta_text=job_spec.call_to_action,
    )


def _ensure_vercel_project(slug: str, vercel_token: str) -> bool:
    project_name = f"df-{slug}"
    headers = {
        "Authorization": f"Bearer {vercel_token}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(
            f"{VERCEL_API_BASE}/v11/projects",
            headers=headers,
            json={"name": project_name},
            timeout=30.0,
        )
        if resp.status_code in (200, 409):
            return True
        logger.warning(
            f"Vercel project creation returned {resp.status_code}: {resp.text[:200]}"
        )
        return False
    except Exception as e:
        logger.warning(f"Vercel project setup failed: {e}")
        return False


def _deploy_vercel(html_content: str, slug: str, vercel_token: str) -> str | None:
    _ensure_vercel_project(slug, vercel_token)
    project_name = f"df-{slug}"
    headers = {
        "Authorization": f"Bearer {vercel_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "name": project_name,
        "files": [
            {
                "file": "index.html",
                "data": base64.b64encode(html_content.encode("utf-8")).decode("utf-8"),
            }
        ],
        "projectSettings": {"framework": None},
    }
    try:
        resp = httpx.post(
            f"{VERCEL_API_BASE}/v13/deployments",
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


def _read_stitch_landing_html(context: dict) -> str | None:
    stitch_path = context.get("stitch_download")
    if not stitch_path or not os.path.exists(stitch_path):
        return None
    try:
        with open(stitch_path, encoding="utf-8") as f:
            manifest = json.load(f)
        landing_html = manifest.get("landing_page_html")
        if landing_html and os.path.exists(landing_html):
            with open(landing_html, encoding="utf-8") as f:
                content = f.read()
            if "<html" in content.lower() or "<!doctype" in content.lower():
                logger.info(f"Using Stitch-designed landing page: {landing_html}")
                return content
    except Exception as e:
        logger.warning(f"Failed to read Stitch landing HTML: {e}")
    return None


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        slug = job_spec.slug
        output_dir = os.path.join("outputs", slug, "landing")
        os.makedirs(output_dir, exist_ok=True)

        gumroad_url = ""
        gumroad_publish_path = context.get("gumroad_publish")
        if gumroad_publish_path and os.path.exists(gumroad_publish_path):
            with open(gumroad_publish_path, encoding="utf-8") as f:
                publish_data = json.load(f)
            gumroad_url = publish_data.get("product_url", "")

        research_data = None
        research_path = context.get("market_research")
        if research_path and os.path.exists(research_path):
            with open(research_path, encoding="utf-8") as f:
                research_data = json.load(f)

        html_content = None

        # Check if Stitch already made a landing page
        stitch_html = _read_stitch_landing_html(context)
        if stitch_html:
            html_content = stitch_html

        if not html_content:
            # Generate images for the landing page
            landing_requirements: list[ImageRequirement] = [
                {
                    "id": "hero_banner",
                    "purpose": "Hero section background for landing page",
                    "aspect_ratio": "16:9",
                },
                {
                    "id": "feature_showcase",
                    "purpose": "Feature highlight section image",
                    "aspect_ratio": "16:9",
                },
                {
                    "id": "benefit_visual",
                    "purpose": "Benefit or testimonial section image",
                    "aspect_ratio": "4:5",
                },
            ]
            images = generate_images(
                requirements=landing_requirements,
                niche=job_spec.niche,
                product_type=job_spec.product_type,
                theme=getattr(job_spec, "theme", "default"),
                research_data=research_data,
                output_dir=os.path.join(output_dir, "images"),
            )
            html_content = _generate_html(images, gumroad_url, job_spec)

        html_path = os.path.join(output_dir, "index.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Landing page HTML saved: {html_path}")

        import zipfile

        zip_path = os.path.join(output_dir, f"{slug}-landing.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(html_path, "index.html")
            images_dir = os.path.join(output_dir, "images")
            if os.path.isdir(images_dir):
                for img in os.listdir(images_dir):
                    img_full = os.path.join(images_dir, img)
                    if os.path.isfile(img_full):
                        zf.write(img_full, f"images/{img}")
        logger.info(f"Landing package created: {zip_path}")

        vercel_token = os.getenv("VERCEL_TOKEN")
        deployed_url = None
        if vercel_token:
            deployed_url = _deploy_vercel(html_content, slug, vercel_token)
        else:
            logger.warning("VERCEL_TOKEN not set -- skipping deploy")

        result = {
            "status": "done",
            "html_path": html_path,
            "zip_path": zip_path,
            "deployed_url": deployed_url or None,
            "source": "stitch" if stitch_html else "llm",
        }
        output_path = os.path.join("outputs", slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        logger.info(
            f"Landing page {'from Stitch' if stitch_html else 'from LLM'} — {deployed_url or 'local only'}"
        )
        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Landing agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
